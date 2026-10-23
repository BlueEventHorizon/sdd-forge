#!/usr/bin/env python3
"""タスク実行単位の到達点と範囲外の導出を支える（範囲導出 SP-01 の Script 部分）。

`/forge:start-implement` の範囲導出のうち、決定論的な 2 つの処理を担う。範囲外の各項目の
理由を読み取って書く処理はオーケストレータ（AI）の責務であり、本 script は行わない。

## モード

- `--candidates --plan-path <計画書> --unit <task_id,...>`: 範囲外の候補を列挙する。
  タスク実行単位に含まれない、`completed` でないタスクのうち、単位のタスクと同じ
  `design_id`（`null` を除く）を持つもの、単位のタスクが `depends_on` に含めるもの、
  単位のタスクを `depends_on` に含めるものを、`task_id`・`title`・`description` で返す。
  設計 ID も依存も共有しないタスクは、今回の変更と関わりが無いため返さない。
- `--review-text --input-file <入力 JSON>`: レビュー用の本文を合成する。入力は
  `.temp/forge/` 配下のプロジェクトルート相対パスで、読んだ後に削除される。

入力 JSON（`--review-text`）:

    {"members": [
      {"task_id": "TASK-001", "scope_in": "到達点（単一行）",
       "scope_out": [{"item": "項目", "owner_task_id": "TASK-002", "reason": "計画上分離"}]}
    ]}

範囲外は、全メンバーの `scope_out` の和集合から、`owner_task_id` が同じ単位のメンバーである
項目を差し引いたもの（同じ項目と担当の組は重複を除く）。範囲外が無いときは、その旨の 1 文を返す。
各値は単一行で、見出し行・コードフェンス行・契約行に見えないこと（節の偽装を防ぐ）。

## 出力

標準出力に JSON を 1 つ書く。`--candidates` は `{"candidates": [...]}`、`--review-text` は
`{"review_text": "..."}`。失敗時は `{"errors": ["自然文", ...]}`。

## 終了コード

| code | 意味                                       |
| ---- | ------------------------------------------ |
| 0    | 依頼された導出が完了した（候補が 0 件でも） |
| 1    | 区別のないエラー（入力を受理できない）     |
| 2    | 引数を受理できない（`argparse`）           |
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "plan"))
from plan_contract import (  # noqa: E402
    PlanContractError,
    load_plan,
    read_and_consume_candidate_input,
)

# 本文が単一行であり、見出し行・コードフェンス行に見えないことを生成側で保証する。
# 受け取る側は生成元の保証を検証できないため、生成側でも独立に検査する。
_STRUCTURE_LINE_RE = re.compile(r"^ {0,3}(?:#{1,6}(?:\s|$)|```|~~~)")
# バックエンド固有のワイヤヘッダを持つ実行主体が現れたら、その接頭辞をここへ足す
# （現在の唯一の実行主体 `agent-review` はワイヤヘッダを持たない）。
_PROTOCOL_LINE_PREFIXES = ("REVIEW_RESULT:",)

_OUT_OF_SCOPE_HEADING = "以下は今回の範囲外である。担当タスクで実装される。"
_NO_OUT_OF_SCOPE = "範囲外の項目はない（今回の対象はこの範囲で最終形に到達する）。"


class InvalidInputError(Exception):
    """入力を受理できない場合に送出する。"""


def _single_line(label, value, required):
    """単一行で、構造行・契約行に見えない文字列を検証し、前後の空白を除いて返す。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise InvalidInputError(f"{label} は必須です")
        return None
    if not isinstance(value, str):
        raise InvalidInputError(f"{label} は文字列である必要があります: {value!r}")
    if "\n" in value or "\r" in value:
        raise InvalidInputError(f"{label} に改行を含む値は指定できません: {value!r}")
    stripped = value.strip()
    if _STRUCTURE_LINE_RE.match(stripped):
        raise InvalidInputError(
            f"{label} が見出し行・コードフェンス行に見えます（節の偽装を防ぐため拒否）: {value!r}"
        )
    for prefix in _PROTOCOL_LINE_PREFIXES:
        if stripped.startswith(prefix):
            raise InvalidInputError(
                f"{label} が契約行（{prefix}）で始まっています（偽装を防ぐため拒否）: {value!r}"
            )
    return stripped


def list_candidates(plan_data, unit_task_ids):
    """範囲外の候補（task_id・title・description）を計画書の順で返す。"""
    if not isinstance(plan_data, dict):
        raise InvalidInputError("計画書は JSON オブジェクトである必要があります")
    tasks = plan_data.get("tasks")
    if not isinstance(tasks, list):
        raise InvalidInputError("計画書に tasks 配列がありません")
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise InvalidInputError(
                f"tasks[{index}] はオブジェクトである必要があります"
            )
    by_id = {t["task_id"]: t for t in tasks if isinstance(t, dict) and "task_id" in t}

    if not unit_task_ids:
        raise InvalidInputError("--unit に task_id を 1 件以上指定してください")
    unknown = [t for t in unit_task_ids if t not in by_id]
    if unknown:
        raise InvalidInputError(
            f"計画書に存在しない task_id が指定されました: {unknown}"
        )

    unit = set(unit_task_ids)
    design_ids = {by_id[t].get("design_id") for t in unit} - {None}
    depended_by_unit = set()
    for task_id in unit:
        depended_by_unit.update(by_id[task_id].get("depends_on") or [])

    candidates = []
    for task in tasks:
        task_id = task.get("task_id")
        if task_id in unit or task.get("status") == "completed":
            continue
        shares_design = (
            task.get("design_id") is not None and task.get("design_id") in design_ids
        )
        is_dependency = task_id in depended_by_unit
        is_dependent = bool(unit & set(task.get("depends_on") or []))
        if shares_design or is_dependency or is_dependent:
            candidates.append(
                {
                    "task_id": task_id,
                    "title": task.get("title"),
                    "description": task.get("description"),
                }
            )
    return candidates


def _normalize_scope_out(task_id, raw):
    """1 メンバーの `scope_out` を検証済みのレコード列へ正規化する。"""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise InvalidInputError(f"{task_id} の scope_out は配列である必要があります")
    records = []
    for index, entry in enumerate(raw):
        label = f"{task_id} の scope_out[{index}]"
        if not isinstance(entry, dict):
            raise InvalidInputError(f"{label} はオブジェクトである必要があります")
        records.append(
            {
                "item": _single_line(f"{label}.item", entry.get("item"), required=True),
                "owner_task_id": _single_line(
                    f"{label}.owner_task_id", entry.get("owner_task_id"), required=False
                ),
                "reason": _single_line(
                    f"{label}.reason", entry.get("reason"), required=False
                ),
            }
        )
    return records


def compose_review_text(payload):
    """タスク実行単位のレビュー用本文（到達点と範囲外）を合成する。"""
    members = payload.get("members") if isinstance(payload, dict) else None
    if not isinstance(members, list) or not members:
        raise InvalidInputError("members は 1 件以上の配列である必要があります")

    normalized = []
    seen_ids = set()
    for index, member in enumerate(members):
        if not isinstance(member, dict):
            raise InvalidInputError(
                f"members[{index}] はオブジェクトである必要があります"
            )
        task_id = _single_line(
            f"members[{index}].task_id", member.get("task_id"), required=True
        )
        if task_id in seen_ids:
            raise InvalidInputError(f"members に重複した task_id があります: {task_id}")
        seen_ids.add(task_id)
        normalized.append(
            {
                "task_id": task_id,
                "scope_in": _single_line(
                    f"{task_id} の scope_in", member.get("scope_in"), required=True
                ),
                "scope_out": _normalize_scope_out(task_id, member.get("scope_out")),
            }
        )

    multiple = len(normalized) > 1
    in_lines = [
        f"- {m['task_id']}: {m['scope_in']}" if multiple else m["scope_in"]
        for m in normalized
    ]

    out_lines = []
    seen = set()
    for m in normalized:
        for record in m["scope_out"]:
            owner = record["owner_task_id"]
            if owner in seen_ids:
                continue  # 同じ単位の別メンバーが今回実装する → 範囲外ではない
            key = (record["item"], owner)
            if key in seen:
                continue
            seen.add(key)
            suffix = f" — {owner}" if owner else ""
            if record["reason"]:
                suffix += f"（{record['reason']}）"
            out_lines.append(f"- {record['item']}{suffix}")

    sections = ["\n".join(in_lines)]
    if out_lines:
        sections.append(_OUT_OF_SCOPE_HEADING + "\n\n" + "\n".join(out_lines))
    else:
        sections.append(_NO_OUT_OF_SCOPE)
    return "\n\n".join(sections)


def _emit(payload):
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


def run_cli(argv=None):
    parser = argparse.ArgumentParser(
        description="範囲導出（候補の列挙・レビュー用本文の合成）"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--candidates", action="store_true", help="範囲外の候補を列挙する"
    )
    mode.add_argument(
        "--review-text", action="store_true", help="レビュー用の本文を合成する"
    )
    parser.add_argument("--plan-path", help="--candidates: 計画書のパス")
    parser.add_argument(
        "--unit", help="--candidates: タスク実行単位のカンマ区切り task_id"
    )
    parser.add_argument(
        "--input-file", help="--review-text: .temp/forge/ 配下の入力 JSON"
    )
    args = parser.parse_args(argv)

    if args.candidates:
        if not args.plan_path or not args.unit:
            parser.error("--candidates には --plan-path と --unit が必要です")
    elif not args.input_file:
        parser.error("--review-text には --input-file が必要です")

    try:
        if args.candidates:
            plan_data = load_plan(args.plan_path)
            unit = [t.strip() for t in args.unit.split(",") if t.strip()]
            _emit({"candidates": list_candidates(plan_data, unit)})
        else:
            payload, errors = read_and_consume_candidate_input(args.input_file)
            if errors:
                _emit({"errors": errors})
                return 1
            _emit({"review_text": compose_review_text(payload)})
    except (PlanContractError, InvalidInputError) as exc:
        _emit({"errors": [str(exc)]})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
