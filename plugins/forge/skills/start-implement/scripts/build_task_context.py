#!/usr/bin/env python3
"""タスクコンテキストを作る・削除する（文脈作成 CX-01・CX-03）。

`/forge:start-implement` の文脈作成のローカル操作入口。単一 SKILL が所有する決定論的な
実体ロジック（DES-024 §6.1「SKILL ローカル実体」）であり、他 SKILL へ再利用される共有
低レベル script ではない。executor agent が呼ぶ「解決する」（CX-02）は別の入口である。

タスクコンテキストは、executor agent に渡す、そのタスク専用の JSON（`TaskContext`）である。
計画書のタスク 1 件に、候補入力の値と、script が決める値（`verification.build`・
`spec_authority`）を加えて作る。他のタスクの情報を含めず、渡された値を変形しない。

置き場は、計画書と同じディレクトリの `tasks/{context_id}.json`。計画書・実装戦略書と同じ
ライフサイクルで扱い、全タスク完了時の存廃の確認で一緒に残すか消す。`context_id` は
`{task_id}-{8 桁の 16 進}` で、script が生成する（AI は組み立てない）。完成してから 1 回の
操作で公開し、上書きしない。識別値は、置き場に既にある値と衝突しないものだけを返す。

## モード

- `--create`: タスクコンテキストを作り、識別値を返す。
  `--project-root` / `--plan-path` / `--task-id` / `--input-file`
- `--delete`: 識別値のタスクコンテキストを削除する。既に無くても成功する。
  `--project-root` / `--plan-path` / `--context-id`

`--plan-path` は、プロジェクトルートからの相対パスか絶対パス。プロジェクトルートの外を
指す値は拒否する。

## 候補入力（`--create` の `--input-file`）

`.temp/forge/` 配下のプロジェクトルート相対パス。読んだ後、成否に関わらず削除される。
形は `templates/task_context_input.json`（本 script がテンプレートと同じフィールド集合を
要求する）。`collected_paths` は RD-01 が集めたパス（土台と補い）で、`required_reading` の
種別分けの検査にだけ使い、タスクコンテキストへは書かない。`verification` は `tests` と
`tests_reason` だけを持つ（`build` は計画書の `build_check` から決める）。

## 拒否（書かずに、標準出力の `errors` に自然文で返す）

- 単一行でない値（`scope_in`、`scope_out` の各値、`tests_reason`）、見出し・コードフェンスで始まる値
- `tests` が `required` 以外で `tests_reason` が空、`required` で理由がある
- `required_reading` が `RequiredReading` の形でない
- `collected_paths` のパスが、どの種別にも無い・複数の種別にある
- `required_reading` のパスが実在しない
- 並行状態を判定できない文書がある（`requirement_docs` / `design_docs` / `additional`）
- 計画書・タスク・`build_check` が不正、`task_id` が一致しない、識別値・計画書パスが不正

## 標準出力

0 のとき、`--create` は `{"context_id": "..."}`、`--delete` は `{}`。
1 のとき、`{"errors": ["自然文", ...]}`。

## 終了コード

| code | 意味                                                                 |
| ---- | -------------------------------------------------------------------- |
| 0    | 作った、または削除した（削除は、既に無かった場合も含む）             |
| 1    | 区別のないエラー（標準出力の `errors` に理由。拒否した入力を含む）   |
| 2    | 引数を受理できない（`argparse`）                                     |
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "plan"))
from plan_contract import (  # noqa: E402
    load_plan,
    PlanContractError,
    read_and_consume_candidate_input as _read_and_consume_input,
    validate_task,
)

sys.path.insert(
    0, str(Path(__file__).resolve().parents[3] / "scripts" / "doc_structure")
)
from feature_marker import classify_feature_marker as _classify_parallel_state  # noqa: E402

# 置き場の決め方・公開・エラーの返し方は、同じ型の置き場を持つ review の script と同じ部品を使う
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "review"))
import review_common  # noqa: E402


TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "templates" / "task_context_input.json"
)
with TEMPLATE_PATH.open(encoding="utf-8") as _template_file:
    CANDIDATE_TEMPLATE = json.load(_template_file)

TOP_LEVEL_FIELDS = set(CANDIDATE_TEMPLATE)
REQUIRED_READING_FIELDS = set(CANDIDATE_TEMPLATE["required_reading"])
VERIFICATION_FIELDS = set(CANDIDATE_TEMPLATE["verification"])
TESTS_STATES = {"required", "optional", "skipped"}

# `required_reading` の種別。`strategy_doc` だけがパス 1 件または null、他は配列
_LIST_KINDS = (
    "design_docs",
    "requirement_docs",
    "rule_docs",
    "reference_code",
    "additional",
)
_REQUIRED_READING_ORDER = (
    "design_docs",
    "requirement_docs",
    "strategy_doc",
    "rule_docs",
    "reference_code",
    "additional",
)

# 計画書の build_check から verification.build を決める（DES-088 6.2）
_BUILD_REQUIRED = {"per_task", "on_group_complete"}
_BUILD_SKIP_REASON = "計画書の build_check が skip である"

# 見出し行・コードフェンス開始行を fail-fast で拒否する（構造侵入対策）。
_STRUCTURE_LINE_RE = re.compile(r"^ {0,3}(?:#{1,6}(?:\s|$)|```|~~~)")

# 並行状態（差分 feature）の識別対象。`additional` は文書種別ではなく「上記に分類されない残り」の
# 受け皿であり、要件定義書・設計書が入りうるため含める。`strategy_doc` / `rule_docs` /
# `reference_code` は種別が固定で識別子を持たないため除く（DES-088 6.2）。
_SPEC_AUTHORITY_SOURCES = ("requirement_docs", "design_docs", "additional")

# 計画書と同じディレクトリに置くサブディレクトリ名（計画書・実装戦略書と同じライフサイクル）
_CONTEXT_SUBDIR = "tasks"
_CONTEXT_ID_SUFFIX_LEN = 8


def _field_set_errors(label, value, expected):
    if not isinstance(value, dict):
        return [f"{label} は object である必要があります"]
    actual = set(value)
    errors = []
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        errors.append(f"{label} に必須フィールドがありません: {missing}")
    if unknown:
        errors.append(f"{label} に未知フィールドがあります: {unknown}")
    return errors


def _check_nonempty_string(label, value, errors):
    """空でない文字列か検査する。値は変形しない。通れば True。"""
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} は空でない文字列である必要があります")
        return False
    return True


def _check_single_line(label, value, errors):
    """単一行で、見出し・コードフェンスで始まらないか検査する。値は変形しない。通れば True。"""
    if not _check_nonempty_string(label, value, errors):
        return False
    if "\n" in value or "\r" in value:
        errors.append(f"{label} は単一行である必要があります")
        return False
    if _STRUCTURE_LINE_RE.match(value):
        errors.append(f"{label} は見出し・コードフェンスで始められません")
        return False
    return True


def _check_string_list(label, value, errors):
    if not isinstance(value, list):
        errors.append(f"{label} は配列である必要があります")
        return
    for index, item in enumerate(value):
        _check_nonempty_string(f"{label}[{index}]", item, errors)


def _check_scope_out(value, errors):
    if not isinstance(value, list):
        errors.append("scope_out は配列である必要があります")
        return
    for index, entry in enumerate(value):
        label = f"scope_out[{index}]"
        entry_errors = _field_set_errors(
            label, entry, {"item", "owner_task_id", "reason"}
        )
        errors.extend(entry_errors)
        if entry_errors:
            continue
        for name in ("item", "owner_task_id", "reason"):
            _check_single_line(f"{label}.{name}", entry.get(name), errors)


def _check_required_reading(value, errors):
    shape_errors = _field_set_errors("required_reading", value, REQUIRED_READING_FIELDS)
    errors.extend(shape_errors)
    if not isinstance(value, dict):
        return
    strategy_doc = value.get("strategy_doc")
    if strategy_doc is not None:
        _check_nonempty_string("required_reading.strategy_doc", strategy_doc, errors)
    for name in _LIST_KINDS:
        if name in value:
            _check_string_list(f"required_reading.{name}", value[name], errors)


def _check_verification(value, errors):
    errors.extend(_field_set_errors("verification", value, VERIFICATION_FIELDS))
    if not isinstance(value, dict):
        return
    tests = value.get("tests")
    reason = value.get("tests_reason")
    if not isinstance(tests, str) or tests not in TESTS_STATES:
        errors.append(f"verification.tests は {sorted(TESTS_STATES)} のいずれかです")
        return
    if tests == "required":
        if reason is not None:
            errors.append(
                "verification.tests_reason は tests が required のとき null です"
            )
    else:
        _check_single_line("verification.tests_reason", reason, errors)


def _kind_paths(required_reading):
    """`(種別名, パス)` を、種別の宣言順に返す。`strategy_doc` が null なら含めない。"""
    pairs = []
    for name in _REQUIRED_READING_ORDER:
        value = required_reading[name]
        if name == "strategy_doc":
            if value is not None:
                pairs.append((name, value))
        else:
            pairs.extend((name, p) for p in value)
    return pairs


def _check_classification(required_reading, collected_paths, errors):
    """RD-01 のパスが、漏れなく、ちょうど 1 つの種別に入っているか検査する。"""
    kinds_of = {}
    for name, path in _kind_paths(required_reading):
        kinds = kinds_of.setdefault(path, [])
        if name not in kinds:
            kinds.append(name)
    for path in dict.fromkeys(collected_paths):
        kinds = kinds_of.get(path, [])
        if not kinds:
            errors.append(f"RD-01 のパスがどの種別にもありません: {path}")
        elif len(kinds) > 1:
            errors.append(f"RD-01 のパスが複数の種別にあります: {path} ({kinds})")


def _exists(project_root, path):
    return (Path(project_root) / path).exists()


def _check_paths_exist(project_root, required_reading, errors):
    """`required_reading` のパスが実在するか検査する。実在しないパスの集合を返す。"""
    missing = []
    for _, path in _kind_paths(required_reading):
        if path not in missing and not _exists(project_root, path):
            missing.append(path)
    if missing:
        errors.append(f"実在しないパスがあります: {missing}")
    return set(missing)


def _resolve_spec_authority(project_root, required_reading, skip):
    """`(並行状態にある文書のパス配列, 判定できない理由の配列)` を返す。`skip` のパスは判定しない。"""
    targets = []
    for name in _SPEC_AUTHORITY_SOURCES:
        for path in required_reading[name]:
            if path not in targets and path not in skip:
                targets.append(path)

    authority = []
    errors = []
    for path in targets:
        is_parallel, error = _classify_parallel_state(str(Path(project_root) / path))
        if error is not None:
            errors.append(error)
        elif is_parallel:
            authority.append(path)
    return authority, errors


def validate_candidate(raw, expected_task_id):
    """候補入力の形と値を検査し、違反の一覧を返す（空なら受理できる）。値は変形しない。"""
    errors = _field_set_errors("candidate", raw, TOP_LEVEL_FIELDS)
    if not isinstance(raw, dict):
        return errors

    if _check_nonempty_string("task_id", raw.get("task_id"), errors):
        if raw["task_id"] != expected_task_id:
            errors.append(
                f"task_id が起動対象と一致しません: expected={expected_task_id!r}, "
                f"actual={raw['task_id']!r}"
            )
    _check_single_line("scope_in", raw.get("scope_in"), errors)
    _check_scope_out(raw.get("scope_out"), errors)
    _check_required_reading(raw.get("required_reading"), errors)
    _check_string_list("collected_paths", raw.get("collected_paths"), errors)
    _check_nonempty_string(
        "implementation_instructions", raw.get("implementation_instructions"), errors
    )
    _check_verification(raw.get("verification"), errors)
    return errors


def _find_task(plan_path, task_id, errors):
    try:
        plan = load_plan(plan_path)
    except PlanContractError as exc:
        errors.append(str(exc))
        return None
    tasks = plan.get("tasks") if isinstance(plan, dict) else None
    if not isinstance(tasks, list):
        errors.append("計画書に tasks 配列がありません")
        return None
    for index, task in enumerate(tasks):
        if isinstance(task, dict) and task.get("task_id") == task_id:
            task_errors = validate_task(index, task)
            if task_errors:
                errors.extend(task_errors)
                return None
            return dict(task)
    errors.append(f"計画書に task_id={task_id!r} が見つかりません")
    return None


def _decide_build(task):
    """計画書の `build_check` から `verification` の build 側を決める（値は `_find_task` が検査済み）。"""
    if task["build_check"] in _BUILD_REQUIRED:
        return {"build": "required", "build_reason": None}
    return {"build": "skipped", "build_reason": _BUILD_SKIP_REASON}


def build_task_context(project_root, plan_path, task_id, candidate_raw):
    """`(タスクコンテキスト | None, errors)` を返す。違反があれば何も作らない。"""
    errors = []
    task = _find_task(plan_path, task_id, errors)
    errors.extend(validate_candidate(candidate_raw, task_id))
    if errors:
        return None, errors

    reading = candidate_raw["required_reading"]
    _check_classification(reading, candidate_raw["collected_paths"], errors)
    missing = _check_paths_exist(project_root, reading, errors)
    build = _decide_build(task)
    spec_authority, authority_errors = _resolve_spec_authority(
        project_root, reading, missing
    )
    errors.extend(authority_errors)
    if errors:
        return None, errors

    verification = {
        **build,
        "tests": candidate_raw["verification"]["tests"],
        "tests_reason": candidate_raw["verification"]["tests_reason"],
    }
    context = dict(task)
    context.update(
        {
            "scope_in": candidate_raw["scope_in"],
            "scope_out": candidate_raw["scope_out"],
            "required_reading": {
                name: reading[name] for name in _REQUIRED_READING_ORDER
            },
            "implementation_instructions": candidate_raw["implementation_instructions"],
            "verification": verification,
            "spec_authority": spec_authority,
        }
    )
    return context, []


def invalid_name(label, value):
    """ディレクトリ名・ファイル名 1 つでない値の理由を返す。正しければ ``None``。"""
    if (
        not isinstance(value, str)
        or value in ("", ".", "..")
        or "/" in value
        or "\\" in value
        or "\0" in value
    ):
        return f"{label} が不正です（名前 1 つでなければなりません）: {label}={value!r}"
    return None


def plan_path_error(project_root, plan_path):
    """計画書パスが空でなく、プロジェクトルートの中を指すことを確かめる。正しければ ``None``。"""
    if not isinstance(plan_path, str) or not plan_path.strip():
        return "plan-path が不正です（空です）"
    root = Path(project_root).resolve()
    resolved = (root / plan_path).resolve()
    if resolved == root or not resolved.is_relative_to(root):
        return (
            f"plan-path がプロジェクトルートの外を指しています: plan-path={plan_path!r}"
        )
    return None


def resolve_plan_path(project_root, plan_path):
    """計画書の絶対パスを返す（相対ならプロジェクトルート基準。実在は確かめない）。"""
    return (Path(project_root).resolve() / plan_path).resolve()


def context_dir(project_root, plan_path):
    """計画書と同じディレクトリの ``tasks/`` を返す（実在は確かめない）。"""
    return resolve_plan_path(project_root, plan_path).parent / _CONTEXT_SUBDIR


def context_path(project_root, plan_path, context_id):
    return context_dir(project_root, plan_path) / f"{context_id}.json"


def _new_context_id(task_id):
    """`{task_id}-{8 桁の 16 進}` を生成する。"""
    return f"{task_id}-{uuid.uuid4().hex[:_CONTEXT_ID_SUFFIX_LEN]}"


def publish_context(project_root, plan_path, task_id, context):
    """置き場に無い識別値を選び、完成したタスクコンテキストを 1 回の操作で公開して識別値を返す。"""
    directory = context_dir(project_root, plan_path)
    directory.mkdir(parents=True, exist_ok=True)
    while True:
        context_id = _new_context_id(task_id)
        path = directory / f"{context_id}.json"
        if path.exists() or path.is_symlink():
            continue  # 既存の識別値を再利用せず、上書きしない
        review_common.publish_json(path, context)
        return context_id


def cmd_create(args):
    reason = invalid_name("task-id", args.task_id) or plan_path_error(
        args.project_root, args.plan_path
    )
    if reason:
        # 入力ファイルは、成否に関わらず削除する契約
        _read_and_consume_input(args.input_file)
        return review_common.error(reason)
    raw, errors = _read_and_consume_input(args.input_file)
    if errors:
        return review_common.error(*errors)

    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        return review_common.error(
            f"プロジェクトルートがディレクトリではありません: {project_root}"
        )

    plan_path = str(resolve_plan_path(project_root, args.plan_path))
    context, errors = build_task_context(project_root, plan_path, args.task_id, raw)
    if errors:
        return review_common.error(*errors)
    try:
        context_id = publish_context(project_root, plan_path, args.task_id, context)
    except OSError as exc:
        return review_common.error(f"タスクコンテキストを書き込めません: {exc}")
    review_common.emit({"context_id": context_id})
    return 0


def cmd_delete(args):
    reason = invalid_name("context-id", args.context_id) or plan_path_error(
        args.project_root, args.plan_path
    )
    if reason:
        return review_common.error(reason)
    path = context_path(args.project_root, args.plan_path, args.context_id)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        return review_common.error(f"タスクコンテキストを削除できません: {exc}")
    review_common.emit({})
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="タスクコンテキストを作る・削除する")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--create", action="store_true", help="タスクコンテキストを作り、識別値を返す"
    )
    mode.add_argument(
        "--delete", action="store_true", help="識別値のタスクコンテキストを削除する"
    )
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--plan-path",
        required=True,
        help="計画書のパス（置き場は同じディレクトリの tasks/）",
    )
    parser.add_argument("--task-id", help="--create: タスク ID")
    parser.add_argument(
        "--input-file", help="--create: .temp/forge/ 配下の候補入力 JSON"
    )
    parser.add_argument("--context-id", help="--delete: 識別値")
    return parser


def run_cli(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.create:
        if not (args.task_id and args.input_file):
            parser.error("--create には --task-id と --input-file が必要です")
        return cmd_create(args)
    if not args.context_id:
        parser.error("--delete には --context-id が必要です")
    return cmd_delete(args)


if __name__ == "__main__":
    raise SystemExit(run_cli())
