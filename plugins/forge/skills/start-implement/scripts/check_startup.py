#!/usr/bin/env python3
"""起動時の状態を判定する（起動確認 CK-01）。

`/forge:start-implement` の起動時に、計画書の有無と、実行中（`in_progress`）のまま残った
タスクの有無を判定し、`StartupState` を返す。計画書は読むだけで変更しない。

## 状態

- `no_plan`: 計画書のパスにファイルが存在しない
- `leftover`: 計画書があり、`in_progress` のタスクが残っている。`in_progress_task_ids` に
  そのタスク ID を計画書の順で持つ
- `clear`: 計画書があり、`in_progress` のタスクが残っていない

`leftover` と `clear` では、`failed` のタスクがあれば `failed_task_ids` に計画書の順で持つ
（無ければキーを持たない）。失敗のタスクは選択されないため、利用者がクリアして再開するかを
決めるための情報である。

計画書を読めない・JSON として壊れている・構造が不正なときは、状態を推測せず、
`{"errors": ["自然文", ...]}` を返す（フォールバックしない）。

## 使い方

    check_startup.py --plan-path <計画書のパス>

## 出力

標準出力に JSON を 1 つ書く。

    {"state": "no_plan"}
    {"state": "leftover", "in_progress_task_ids": ["TASK-004"]}
    {"state": "clear"}
    {"state": "clear", "failed_task_ids": ["TASK-002"]}

## 終了コード

| code | 意味                                                 |
| ---- | ---------------------------------------------------- |
| 0    | 状態を判定できた（`no_plan`・`leftover`・`clear`）   |
| 1    | 区別のないエラー（計画書を読めない・構造が不正）     |
| 2    | 引数を受理できない（`argparse`）                     |
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "plan"))
from plan_contract import PlanContractError, load_plan  # noqa: E402


class InvalidPlanError(Exception):
    """計画書の構造から状態を判定できない場合に送出する。"""


def determine_startup_state(plan_path):
    """計画書のパスから `StartupState`（dict）を返す。判定できなければ例外を送出する。

    計画書が存在しないことと、存在するが読めないことは区別する。後者は `no_plan` に
    せず、`PlanContractError` / `InvalidPlanError` を送出する。
    """
    path = Path(plan_path)
    try:
        path.lstat()
    except FileNotFoundError:
        return {"state": "no_plan"}
    except OSError as exc:
        raise PlanContractError(f"計画書の存在を確認できません: {exc}") from exc

    plan_data = load_plan(path)
    if not isinstance(plan_data, dict):
        raise InvalidPlanError("計画書は JSON オブジェクトである必要があります")
    tasks = plan_data.get("tasks")
    if not isinstance(tasks, list):
        raise InvalidPlanError("計画書に tasks 配列がありません")

    in_progress = []
    failed = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise InvalidPlanError(f"tasks[{index}] はオブジェクトである必要があります")
        status = task.get("status")
        if status in ("in_progress", "failed"):
            task_id = task.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                raise InvalidPlanError(
                    f"tasks[{index}] は {status} ですが task_id が文字列ではありません"
                )
            (in_progress if status == "in_progress" else failed).append(task_id)

    state = (
        {"state": "leftover", "in_progress_task_ids": in_progress}
        if in_progress
        else {"state": "clear"}
    )
    if failed:
        state["failed_task_ids"] = failed
    return state


def _emit(payload):
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


def run_cli(argv=None):
    parser = argparse.ArgumentParser(
        description="起動時の状態の判定（計画書なし・実行中が残っている・残りなし）"
    )
    parser.add_argument("--plan-path", required=True, help="計画書のパス")
    args = parser.parse_args(argv)

    try:
        _emit(determine_startup_state(args.plan_path))
    except (PlanContractError, InvalidPlanError) as exc:
        _emit({"errors": [str(exc)]})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
