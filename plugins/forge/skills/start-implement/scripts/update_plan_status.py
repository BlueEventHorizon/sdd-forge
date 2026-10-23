#!/usr/bin/env python3
"""計画書のタスクと要件の状態を遷移させる（DES-088 状態遷移 ST-01〜04）。計画書を書く唯一の処理。

`/forge:start-implement` のローカル操作入口。`--to` で 5 つのモードを選ぶ。

| `--to`        | 前の状態                                                       | 後の状態    |
| ------------- | -------------------------------------------------------------- | ----------- |
| `in_progress` | `pending` または `failed`                                      | `in_progress` |
| `implemented` | `in_progress`（タスクグループのメンバーのみ）                  | `implemented` |
| `completed`   | グループ外は `in_progress`、メンバーは `implemented`           | `completed`   |
| `failed`      | `in_progress` または `implemented`                             | `failed`      |
| `pending`     | `failed`（利用者の指示で失敗をクリアし、次の選択の対象に戻す） | `pending`     |

- 上表にない遷移は、計画書を変更せずエラーにする
- `pending` へ戻すとき、依存するタスクの状態は変えない（失敗にしたときに既に戻している）
- 指定した全タスクの検査を、書く前に済ませる。1 つでも不正なら何も書かない（全か無か）
- `failed` にするとき、指定したタスクに推移的に依存する `implemented` のタスクを `pending` に戻す。
  依存しない `implemented` は残す。戻したタスクの一覧を `reverted_task_ids` で返す
- `completed` にしたあと、`design_traceability` から要件に紐づくタスクを求め、1 件以上あり、
  すべてが `completed` の要件を `completed` にする。紐づくタスクが 1 件も無い要件は `completed` にしない
- 書き込みは `plan_contract.save_plan`（一時ファイルへ書いてから置き換える）で行う。排他の制御は持たない。
  並列に実行するタスク実行単位からも、呼び出し側が 1 回ずつ、前の呼び出しの完了を待って呼ぶ

## 終了コード

| code | 意味                                                         |
| ---- | ------------------------------------------------------------ |
| 0    | 遷移が完了し、計画書を書き込んだ                             |
| 1    | 区別のないエラー（計画書を読めない・遷移が許されない等）     |
| 2    | 引数を受理できない（`argparse`）                             |

エラーは標準出力の `errors`（自然文の配列）に載せる。
"""

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "plan"))
from plan_contract import load_plan, save_plan, PlanContractError  # noqa: E402


MODES = ("in_progress", "implemented", "completed", "failed", "pending")


def _group_member(task):
    """タスクグループのメンバーか（group_id を持つか）。"""
    return task.get("group_id") is not None


def _check_transition(task, to):
    """遷移が許されないとき、理由の自然文を返す。許されるなら None。"""
    task_id = task["task_id"]
    status = task.get("status")
    member = _group_member(task)
    if to == "in_progress":
        if status not in ("pending", "failed"):
            return f"{task_id} は {status} のため実行中にできません（未着手または失敗のときだけ可能です）"
    elif to == "implemented":
        if not member:
            return (
                f"{task_id} はタスクグループのメンバーではないため実装済みにできません"
            )
        if status != "in_progress":
            return f"{task_id} は {status} のため実装済みにできません（実行中のときだけ可能です）"
    elif to == "completed":
        required = "implemented" if member else "in_progress"
        if status != required:
            kind = (
                "タスクグループのメンバー"
                if member
                else "タスクグループに属さないタスク"
            )
            return (
                f"{task_id} は {status} のため完了にできません"
                f"（{kind}は {required} のときだけ可能です）"
            )
    elif to == "failed":
        if status not in ("in_progress", "implemented"):
            return f"{task_id} は {status} のため失敗にできません（実行中または実装済みのときだけ可能です）"
    elif to == "pending":
        if status != "failed":
            return f"{task_id} は {status} のため未着手に戻せません（失敗のときだけ可能です）"
    return None


def _dependents_closure(tasks, roots):
    """roots に推移的に依存するタスクの ID 集合（roots 自身は含まない）。入力は変更しない。"""
    reverse = {}
    for task in tasks:
        depends_on = task.get("depends_on")
        if not isinstance(depends_on, list):
            continue
        for dep in depends_on:
            if isinstance(dep, str):
                reverse.setdefault(dep, []).append(task["task_id"])
    found = set()
    stack = list(roots)
    while stack:
        current = stack.pop()
        for dependent in reverse.get(current, []):
            if dependent not in found and dependent not in roots:
                found.add(dependent)
                stack.append(dependent)
    return found


def _complete_requirements(plan):
    """全紐づくタスクが completed の要件を completed にし、新たに完了にした要件 ID を返す。"""
    by_id = {t["task_id"]: t for t in plan["tasks"]}
    requirement_to_task_ids = {}
    for entry in plan.get("design_traceability") or []:
        if not isinstance(entry, dict):
            continue
        task_ids = entry.get("task_ids") or []
        for requirement_id in entry.get("requirement_ids") or []:
            requirement_to_task_ids.setdefault(requirement_id, set()).update(task_ids)

    newly_completed = []
    for requirement in plan.get("requirements_traceability") or []:
        if not isinstance(requirement, dict):
            continue
        requirement_id = requirement.get("requirement_id")
        linked = requirement_to_task_ids.get(requirement_id, set())
        if not linked:
            continue
        if requirement.get("status") == "completed":
            continue
        if all(
            by_id.get(task_id, {}).get("status") == "completed" for task_id in linked
        ):
            requirement["status"] = "completed"
            newly_completed.append(requirement_id)
    return newly_completed


def transition_plan(plan_data, to, task_ids):
    """計画書を遷移させる。入力は変更しない。

    (更新後の計画書 | None, 結果 | None, errors) を返す。errors があるとき計画書は None
    （何も変更しない）。結果は `updated_tasks`（task_id から更新後の状態）・
    `reverted_task_ids`・`completed_requirement_ids`。
    """
    if to not in MODES:
        return None, None, [f"--to は {list(MODES)} のいずれかです（実際: {to!r}）"]
    tasks = plan_data.get("tasks") if isinstance(plan_data, dict) else None
    if not isinstance(tasks, list):
        return None, None, ["計画書に tasks 配列がありません"]

    ordered_ids = list(dict.fromkeys(task_ids))
    if not ordered_ids:
        return None, None, ["task_id が指定されていません"]

    plan = copy.deepcopy(plan_data)
    work_tasks = [
        t
        for t in plan["tasks"]
        if isinstance(t, dict) and isinstance(t.get("task_id"), str)
    ]
    by_id = {t["task_id"]: t for t in work_tasks}

    # 書く前に、指定された全タスクを検査する（全か無か）
    errors = []
    unknown = [task_id for task_id in ordered_ids if task_id not in by_id]
    if unknown:
        errors.append(f"計画書に存在しない task_id が指定されました: {unknown}")
    for task_id in ordered_ids:
        if task_id in by_id:
            reason = _check_transition(by_id[task_id], to)
            if reason:
                errors.append(reason)
    if errors:
        return None, None, errors

    for task_id in ordered_ids:
        by_id[task_id]["status"] = to

    reverted = []
    if to == "failed":
        dependents = _dependents_closure(work_tasks, set(ordered_ids))
        for task in work_tasks:
            if task["task_id"] in dependents and task.get("status") == "implemented":
                task["status"] = "pending"
                reverted.append(task["task_id"])

    completed_requirements = (
        _complete_requirements({**plan, "tasks": work_tasks})
        if to == "completed"
        else []
    )

    result = {
        "updated_tasks": {task_id: to for task_id in ordered_ids},
        "reverted_task_ids": reverted,
        "completed_requirement_ids": completed_requirements,
    }
    return plan, result, []


def _emit(payload):
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


def run_cli(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-path", required=True)
    parser.add_argument(
        "--to", required=True, choices=MODES, help="遷移先の状態（モード）"
    )
    parser.add_argument(
        "--task", required=True, help="遷移させるカンマ区切りの task_id 一覧"
    )
    args = parser.parse_args(argv)

    try:
        plan_data = load_plan(args.plan_path)
    except PlanContractError as exc:
        _emit({"errors": [str(exc)]})
        return 1

    task_ids = [t.strip() for t in args.task.split(",") if t.strip()]
    plan, result, errors = transition_plan(plan_data, args.to, task_ids)
    if errors:
        _emit({"errors": errors})
        return 1

    try:
        save_plan(args.plan_path, plan)
    except OSError as exc:
        _emit({"errors": [f"計画書を書き込めません: {exc}"]})
        return 1
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
