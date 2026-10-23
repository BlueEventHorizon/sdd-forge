#!/usr/bin/env python3
"""計画書のタスクについて、必読文書の土台（RD-01）を集める。

`/forge:start-implement` の必読収集のローカル操作入口。単一 SKILL が所有する決定論的な
実体ロジック（DES-024 §6.1「SKILL ローカル実体」）であり、他 SKILL へ再利用される共有
低レベル script ではない。

集めるのは土台だけである。

1. 計画書のタスクの `required_reading` を、そのまま加える
2. タスクの `design_id` が `null` でなければ、設計書のパスを求めて加える
   （設計書の解決は `resolve_doc_structure.py` の `find_doc`、`--find-in design` と同じ）
3. その設計に対応する要件 ID を、計画書の `design_traceability`（`design_id` が一致する要素の
   `requirement_ids`）から求め、各要件定義書のパスを求めて加える
   （要件定義書の解決は `find_doc` の doc_type `requirement`）。計画書の `required_reading` に
   要件定義書が書かれていなくても、要件定義書は土台に入る
4. 重複を除き、実在しないパスの一覧を返す

補い（既存コードと、タスクに応じた実装ルール）は、この script では行わない。
オーケストレータが検索スキルと Grep で探す。

## 標準出力

0 のとき、結果の JSON（`status: ok`）。設計書・要件定義書が見つからない・複数見つかる・
実在しないパスがある、といった事実は、完了を妨げない結果の内容であり、
`design_lookup` / `requirement_lookup` / `missing_paths` / `problems` に載せて 0 で返す。
オーケストレータは、これらがあれば、任せる前にエラーとして扱い、失敗にする。

- `paths`: 重複を除いたパスの配列（プロジェクトルートからの相対パス）
- `design_lookup`: `{"status": "not_applicable" | "found" | "not_found" | "ambiguous", "design_id": ..., "matches": [...]}`
- `requirement_lookup`: 設計に対応する要件ごとの `{"status": "found" | "not_found" | "ambiguous", "requirement_id": ..., "matches": [...]}` の配列（設計が無いとき、対応する要件が無いときは空）
- `missing_paths`: 実在しないパスの配列
- `problems`: 上の事実を自然文にした配列（無ければ空）

1 のとき、エラーの JSON（`status: error`）。`errors` は自然文の配列。

## 終了コード

| code | 意味                                                                                         |
| ---- | -------------------------------------------------------------------------------------------- |
| 0    | 土台を集めた（設計書が見つからない・実在しないパスがあることも、結果の内容として 0 で返す）  |
| 1    | 区別のないエラー（計画書・タスク・`.doc_structure.yaml` を読めない・タスクの形が不正 等）    |
| 2    | 引数を受理できない（`argparse`）                                                             |
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "plan"))
from plan_contract import load_plan, PlanContractError  # noqa: E402

sys.path.insert(
    0, str(Path(__file__).resolve().parents[3] / "scripts" / "doc_structure")
)
from resolve_doc_structure import (  # noqa: E402
    find_doc,
    find_project_root,
    load_doc_structure,
    validate_doc_structure,
)

DESIGN_DOC_TYPE = "design"
REQUIREMENT_DOC_TYPE = "requirement"
DESIGN_CATEGORY = "specs"


def _find_task(plan, task_id, errors):
    tasks = (plan or {}).get("tasks")
    if not isinstance(tasks, list):
        errors.append("計画書に tasks 配列がありません")
        return None
    for task in tasks:
        if isinstance(task, dict) and task.get("task_id") == task_id:
            return task
    errors.append(f"計画書に task_id={task_id!r} のタスクが見つかりません")
    return None


def _task_required_reading(task, errors):
    reading = task.get("required_reading")
    if not isinstance(reading, list) or not all(
        isinstance(p, str) and p.strip() for p in reading
    ):
        errors.append(
            f"タスク {task.get('task_id')!r} の required_reading が空でない文字列の配列ではありません"
        )
        return []
    return [p.strip() for p in reading]


def _load_config(project_root, errors):
    """`.doc_structure.yaml` を読んで検証する。読めないとき `errors` に足して None を返す。"""
    try:
        config, raw_content = load_doc_structure(project_root)
    except FileNotFoundError as exc:
        errors.append(str(exc))
        return None
    validation = validate_doc_structure(config, raw_content)
    if not validation.get("valid"):
        errors.append(f".doc_structure.yaml が不正です: {validation.get('error')}")
        return None
    return config


def _find_one(config, doc_type, identifier, project_root, errors):
    """識別子から文書を探す。`(status, matches)` を返す。探せないとき `errors` に足す。"""
    found = find_doc(config, DESIGN_CATEGORY, doc_type, identifier, project_root)
    if found.get("status") != "ok":
        errors.append(str(found.get("message")))
        return None, None
    matches = list(found["matches"])
    status = {0: "not_found", 1: "found"}.get(len(matches), "ambiguous")
    return status, matches


def _requirement_ids(plan, design_id):
    """設計に対応する要件 ID を、計画書の設計の対応関係（design_traceability）から求める。"""
    for entry in (plan or {}).get("design_traceability") or []:
        if isinstance(entry, dict) and entry.get("design_id") == design_id:
            ids = entry.get("requirement_ids")
            if isinstance(ids, list):
                return [i for i in ids if isinstance(i, str) and i.strip()]
    return []


def _lookup_docs(plan, design_id, project_root, errors):
    """設計書と、その設計に対応する要件定義書のパスを求める。

    `(design_lookup, 設計書のパス | None, requirement_lookup, 要件定義書のパスの配列)` を返す。
    """
    if design_id is None:
        design_lookup = {"status": "not_applicable", "design_id": None, "matches": []}
        return design_lookup, None, [], []
    if not isinstance(design_id, str) or not design_id.strip():
        errors.append("タスクの design_id が null でも空でない文字列でもありません")
        return None, None, [], []
    design_id = design_id.strip()

    config = _load_config(project_root, errors)
    if config is None:
        return None, None, [], []

    status, matches = _find_one(
        config, DESIGN_DOC_TYPE, design_id, project_root, errors
    )
    if status is None:
        return None, None, [], []
    design_lookup = {"status": status, "design_id": design_id, "matches": matches}
    design_path = matches[0] if status == "found" else None

    requirement_lookup = []
    requirement_paths = []
    for requirement_id in _requirement_ids(plan, design_id):
        status, matches = _find_one(
            config, REQUIREMENT_DOC_TYPE, requirement_id, project_root, errors
        )
        if status is None:
            return None, None, [], []
        requirement_lookup.append(
            {"status": status, "requirement_id": requirement_id, "matches": matches}
        )
        if status == "found":
            requirement_paths.append(matches[0])
    return design_lookup, design_path, requirement_lookup, requirement_paths


def _design_problem(lookup):
    if lookup["status"] == "not_found":
        return f"設計の識別子 {lookup['design_id']} の設計書が見つかりません"
    if lookup["status"] == "ambiguous":
        return (
            f"設計の識別子 {lookup['design_id']} の設計書が複数見つかりました: "
            f"{lookup['matches']}"
        )
    return None


def _requirement_problem(lookup):
    if lookup["status"] == "not_found":
        return f"要件 {lookup['requirement_id']} の要件定義書が見つかりません"
    if lookup["status"] == "ambiguous":
        return (
            f"要件 {lookup['requirement_id']} の要件定義書が複数見つかりました: "
            f"{lookup['matches']}"
        )
    return None


def collect_required_reading(plan, task_id, project_root):
    """`(結果 | None, errors)` を返す。"""
    errors = []
    task = _find_task(plan, task_id, errors)
    if task is None:
        return None, errors
    base = _task_required_reading(task, errors)
    lookup, design_path, requirement_lookup, requirement_paths = _lookup_docs(
        plan, task.get("design_id"), project_root, errors
    )
    if errors:
        return None, errors

    paths = []
    for path in base + ([design_path] if design_path else []) + requirement_paths:
        if path not in paths:
            paths.append(path)

    missing = [p for p in paths if not os.path.exists(os.path.join(project_root, p))]

    problems = []
    design_problem = _design_problem(lookup)
    if design_problem:
        problems.append(design_problem)
    for item in requirement_lookup:
        requirement_problem = _requirement_problem(item)
        if requirement_problem:
            problems.append(requirement_problem)
    if missing:
        problems.append(f"実在しないパスがあります: {missing}")

    return {
        "paths": paths,
        "design_lookup": lookup,
        "requirement_lookup": requirement_lookup,
        "missing_paths": missing,
        "problems": problems,
    }, []


def _emit(payload):
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


def run_cli(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-path", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument(
        "--project-root",
        default=None,
        help="プロジェクトルートのパス（省略時: .git/.claude を遡って自動検出）",
    )
    args = parser.parse_args(argv)

    try:
        project_root = (
            os.path.abspath(args.project_root)
            if args.project_root
            else find_project_root()
        )
        plan = load_plan(args.plan_path)
    except (PlanContractError, RuntimeError) as exc:
        _emit({"status": "error", "errors": [str(exc)]})
        return 1

    result, errors = collect_required_reading(plan, args.task_id, project_root)
    if errors:
        _emit({"status": "error", "errors": errors})
        return 1

    _emit({"status": "ok", **result})
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
