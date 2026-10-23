#!/usr/bin/env python3
"""計画書から、実行可能なタスクを優先度順に選び、タスク実行単位の一覧にする（タスク選択 SEL-01）。

start-implement スキルのタスク選択の決定論的な実体。実行可能の判定・優先度順の整列・
タスクグループの展開は AI ではなく本 script が行う。計画書は変更しない。

## 選び方

- 実行可能なタスク: 状態が `pending` で、すべての `depends_on` の先行が `completed`、または
  同じタスクグループの `implemented` であるもの。待つタスク（先行が未完了）は選ばず、件数の枠も占めない。
  実行中・実装済み・失敗・完了のタスクは選ばない。
- 優先度の降順。同じ優先度は `task_id` の昇順。
- 先頭から `--count` 個（省略時は 1）選ぶ。すでに選んだ単位に含まれるタスクは、数えずに飛ばす。
- 選んだタスクがタスクグループに属するとき、同じグループの `pending` のメンバーのうち、先行が
  `completed`・`implemented`、または同じ単位の先行メンバーであるものを、同じ単位へ加える
  （件数に数えない）。条件を満たさないメンバーは単位に含めず、未着手のまま残す。同じグループの
  `implemented` のメンバーは `done_task_ids` に載せる。
- 単位の `task_ids` は `depends_on` の順に並べる。同順位は `group_id` の通し番号の順。
- 実行可能なタスクが無いときは、`units` を空にする（エラーではない）。

## 出力

標準出力に JSON を 1 つ書く。

    {"units": [
      {"kind": "task", "group_key": null, "task_ids": ["TASK-010"], "done_task_ids": []},
      {"kind": "group", "group_key": "GROUP-001",
       "task_ids": ["TASK-002", "TASK-003"], "done_task_ids": ["TASK-001"]}
    ]}

失敗時は `{"errors": ["自然文", ...]}`。

## 終了コード

| code | 意味                                         |
| ---- | -------------------------------------------- |
| 0    | 選択が完了した（実行可能なタスクが 0 件でも） |
| 1    | 区別のないエラー（計画書を受理できない）     |
| 2    | 引数を受理できない（`argparse`）             |
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "plan"))
from plan_contract import load_plan, normalize_group_key, PlanContractError  # noqa: E402

_SERIAL_RE = re.compile(r"\(\s*(\d+)\s*/\s*\d+\s*\)")


def _serial(task):
    """group_id の通し番号（"GROUP-001 (2/7)" の 2）。読めなければ末尾に回す。"""
    match = _SERIAL_RE.search(task.get("group_id") or "")
    return int(match.group(1)) if match else sys.maxsize


def _group_key(task):
    return normalize_group_key(task.get("group_id"))


def _is_executable(task, by_id, unit=frozenset()):
    """未着手で、先行がすべて completed、同じグループの implemented、または同じ単位（unit）のメンバーか。"""
    if task.get("status") != "pending":
        return False
    key = _group_key(task)
    for dep_id in task.get("depends_on") or []:
        dep = by_id.get(dep_id)
        if dep is None:
            return False
        status = dep.get("status")
        if status == "completed" or dep_id in unit:
            continue
        if status == "implemented" and key is not None and _group_key(dep) == key:
            continue
        return False
    return True


def _order_by_dependency(members, by_id):
    """単位のメンバーを depends_on の順に並べる。同順位は通し番号、次に task_id の順。"""
    ids = {t["task_id"] for t in members}
    remaining = {t["task_id"]: t for t in members}
    ordered = []
    while remaining:
        ready = [
            t
            for t in remaining.values()
            if not (set(t.get("depends_on") or []) & ids & set(remaining))
        ]
        if (
            not ready
        ):  # 循環は計画書の作成時に検出される。ここでは落とさず残りを通し番号順に置く
            ready = list(remaining.values())
        ready.sort(key=lambda t: (_serial(t), t["task_id"]))
        head = ready[0]
        ordered.append(head)
        del remaining[head["task_id"]]
    return [t["task_id"] for t in ordered]


def _build_group_unit(seed, tasks, by_id):
    key = _group_key(seed)
    members = [t for t in tasks if _group_key(t) == key]
    unit = {seed["task_id"]}
    changed = True
    while changed:
        changed = False
        for task in members:
            if task["task_id"] in unit:
                continue
            if _is_executable(task, by_id, unit):
                unit.add(task["task_id"])
                changed = True
    unit_tasks = [by_id[i] for i in unit]
    done = sorted(
        (t for t in members if t.get("status") == "implemented"),
        key=lambda t: (_serial(t), t["task_id"]),
    )
    return {
        "kind": "group",
        "group_key": key,
        "task_ids": _order_by_dependency(unit_tasks, by_id),
        "done_task_ids": [t["task_id"] for t in done],
    }


def select_tasks(plan_data, count=None):
    """(result | None, errors) を返す。result は {"units": [...]}。"""
    tasks = plan_data.get("tasks") if isinstance(plan_data, dict) else None
    if not isinstance(tasks, list):
        return None, ["計画書に tasks 配列がありません"]
    for index, task in enumerate(tasks):
        if not isinstance(task, dict) or "task_id" not in task:
            return None, [f"tasks[{index}] が task_id を持つオブジェクトではありません"]
    by_id = {t["task_id"]: t for t in tasks}

    if count is None:
        count = 1
    if count < 1:
        return None, [f"タスク数は 1 以上を指定してください: {count}"]

    executable = [t for t in tasks if _is_executable(t, by_id)]
    executable.sort(key=lambda t: (-t.get("priority", 0), t["task_id"]))

    units = []
    placed = set()
    for task in executable:
        if len(units) >= count:
            break
        if task["task_id"] in placed:
            continue
        if _group_key(task) is None:
            unit = {
                "kind": "task",
                "group_key": None,
                "task_ids": [task["task_id"]],
                "done_task_ids": [],
            }
        else:
            unit = _build_group_unit(task, tasks, by_id)
        placed.update(unit["task_ids"])
        units.append(unit)
    return {"units": units}, []


def _emit(payload):
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


def run_cli(argv=None):
    parser = argparse.ArgumentParser(
        description="タスク選択（タスク実行単位の一覧を返す）"
    )
    parser.add_argument("--plan-path", required=True)
    parser.add_argument("--count", type=int, help="選ぶタスクの数（省略時は 1）")
    args = parser.parse_args(argv)
    if args.count is not None and args.count < 1:
        parser.error("--count は 1 以上を指定してください")

    try:
        plan_data = load_plan(args.plan_path)
    except PlanContractError as exc:
        _emit({"errors": [str(exc)]})
        return 1

    result, errors = select_tasks(plan_data, count=args.count)
    if errors:
        _emit({"errors": errors})
        return 1

    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
