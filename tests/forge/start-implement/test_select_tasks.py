#!/usr/bin/env python3
"""select_tasks.py の契約テスト（タスク実行単位の出力）。"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "forge"
    / "skills"
    / "start-implement"
    / "scripts"
    / "select_tasks.py"
)

_SPEC = importlib.util.spec_from_file_location("select_tasks", SCRIPT)
select_tasks_module = importlib.util.module_from_spec(_SPEC)
sys.modules["select_tasks"] = select_tasks_module
_SPEC.loader.exec_module(select_tasks_module)


def _task(task_id, priority=50, status="pending", depends_on=None, group_id=None):
    return {
        "task_id": task_id,
        "title": task_id,
        "priority": priority,
        "status": status,
        "design_id": None,
        "depends_on": depends_on or [],
        "group_id": group_id,
        "build_check": "per_task",
        "description": ["x"],
        "acceptance_criteria": None,
        "required_reading": [],
    }


def _task_ids(result):
    return [u["task_ids"] for u in result["units"]]


class SelectTasksFunctionTest(unittest.TestCase):
    def test_output_has_only_units_with_unit_fields(self):
        plan = {"tasks": [_task("TASK-001")]}
        result, errors = select_tasks_module.select_tasks(plan)
        self.assertEqual(errors, [])
        self.assertEqual(set(result), {"units"})
        self.assertEqual(
            result["units"],
            [
                {
                    "kind": "task",
                    "group_key": None,
                    "task_ids": ["TASK-001"],
                    "done_task_ids": [],
                }
            ],
        )
        for old in (
            "selected_task_ids",
            "executable_task_ids",
            "waiting_task_ids",
            "selected_tasks",
        ):
            self.assertNotIn(old, result)

    def test_default_selects_single_highest_priority(self):
        plan = {
            "tasks": [_task("TASK-001", priority=10), _task("TASK-002", priority=90)]
        }
        result, _ = select_tasks_module.select_tasks(plan)
        self.assertEqual(_task_ids(result), [["TASK-002"]])

    def test_count_selects_top_n_by_priority(self):
        plan = {
            "tasks": [
                _task("TASK-001", priority=10),
                _task("TASK-002", priority=90),
                _task("TASK-003", priority=50),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan, count=2)
        self.assertEqual(_task_ids(result), [["TASK-002"], ["TASK-003"]])

    def test_same_priority_ordered_by_task_id(self):
        plan = {
            "tasks": [
                _task("TASK-003", priority=50),
                _task("TASK-001", priority=50),
                _task("TASK-002", priority=50),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan, count=3)
        self.assertEqual(_task_ids(result), [["TASK-001"], ["TASK-002"], ["TASK-003"]])

    def test_non_pending_tasks_are_never_selected(self):
        plan = {
            "tasks": [
                _task("TASK-001", priority=90, status="completed"),
                _task("TASK-002", priority=90, status="in_progress"),
                _task("TASK-003", priority=90, status="implemented"),
                _task("TASK-004", priority=90, status="failed"),
                _task("TASK-005", priority=10),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan, count=10)
        self.assertEqual(_task_ids(result), [["TASK-005"]])

    def test_waiting_task_does_not_occupy_count_slot(self):
        plan = {
            "tasks": [
                _task("TASK-001", priority=10),
                _task("TASK-002", priority=99, depends_on=["TASK-001"]),
                _task("TASK-003", priority=50),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan, count=1)
        self.assertEqual(_task_ids(result), [["TASK-003"]])

    def test_task_with_completed_dependency_is_executable(self):
        plan = {
            "tasks": [
                _task("TASK-001", status="completed"),
                _task("TASK-002", depends_on=["TASK-001"]),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan)
        self.assertEqual(_task_ids(result), [["TASK-002"]])

    def test_implemented_dependency_outside_group_is_not_executable(self):
        plan = {
            "tasks": [
                _task("TASK-001", status="implemented", group_id="GROUP-001 (1/2)"),
                _task("TASK-002", depends_on=["TASK-001"]),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan)
        self.assertEqual(result["units"], [])

    def test_no_executable_tasks_returns_empty_units(self):
        plan = {"tasks": [_task("TASK-001", status="completed")]}
        result, errors = select_tasks_module.select_tasks(plan)
        self.assertEqual(errors, [])
        self.assertEqual(result, {"units": []})

    def test_incomplete_external_dependency_is_not_an_error(self):
        plan = {
            "tasks": [_task("TASK-001", depends_on=["TASK-002"]), _task("TASK-002")]
        }
        result, errors = select_tasks_module.select_tasks(plan, count=1)
        self.assertEqual(errors, [])
        self.assertEqual(_task_ids(result), [["TASK-002"]])

    def test_group_expands_pending_members_without_counting(self):
        plan = {
            "tasks": [
                _task("TASK-001", priority=90, group_id="GROUP-001 (1/2)"),
                _task("TASK-002", priority=10, group_id="GROUP-001 (2/2)"),
                _task("TASK-003", priority=50),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan, count=2)
        self.assertEqual(
            result["units"],
            [
                {
                    "kind": "group",
                    "group_key": "GROUP-001",
                    "task_ids": ["TASK-001", "TASK-002"],
                    "done_task_ids": [],
                },
                {
                    "kind": "task",
                    "group_key": None,
                    "task_ids": ["TASK-003"],
                    "done_task_ids": [],
                },
            ],
        )

    def test_group_members_ordered_by_dependency_then_serial(self):
        plan = {
            "tasks": [
                _task(
                    "TASK-001",
                    priority=90,
                    group_id="GROUP-001 (2/3)",
                    depends_on=["TASK-003"],
                ),
                _task(
                    "TASK-002",
                    priority=10,
                    group_id="GROUP-001 (1/3)",
                    depends_on=["TASK-001"],
                ),
                _task("TASK-003", priority=10, group_id="GROUP-001 (3/3)"),
            ]
        }
        # TASK-001 は先行 TASK-003 を待つので実行可能なのは TASK-003 だけ
        result, _ = select_tasks_module.select_tasks(plan)
        self.assertEqual(
            result["units"][0]["task_ids"], ["TASK-003", "TASK-001", "TASK-002"]
        )

    def test_group_member_with_unmet_predecessor_stays_out_of_unit(self):
        plan = {
            "tasks": [
                _task("TASK-001", priority=90, group_id="GROUP-001 (1/2)"),
                _task(
                    "TASK-002",
                    priority=10,
                    group_id="GROUP-001 (2/2)",
                    depends_on=["TASK-009"],
                ),
                _task("TASK-009", priority=5),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan)
        self.assertEqual(result["units"][0]["task_ids"], ["TASK-001"])

    def test_implemented_members_go_to_done_task_ids(self):
        plan = {
            "tasks": [
                _task("TASK-001", status="implemented", group_id="GROUP-001 (1/3)"),
                _task(
                    "TASK-002",
                    priority=80,
                    group_id="GROUP-001 (2/3)",
                    depends_on=["TASK-001"],
                ),
                _task(
                    "TASK-003",
                    priority=10,
                    group_id="GROUP-001 (3/3)",
                    depends_on=["TASK-002"],
                ),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan)
        self.assertEqual(
            result["units"],
            [
                {
                    "kind": "group",
                    "group_key": "GROUP-001",
                    "task_ids": ["TASK-002", "TASK-003"],
                    "done_task_ids": ["TASK-001"],
                }
            ],
        )

    def test_group_unit_is_not_duplicated_when_several_members_executable(self):
        plan = {
            "tasks": [
                _task("TASK-001", priority=90, group_id="GROUP-001 (1/2)"),
                _task("TASK-002", priority=80, group_id="GROUP-001 (2/2)"),
            ]
        }
        result, _ = select_tasks_module.select_tasks(plan, count=2)
        self.assertEqual(len(result["units"]), 1)

    def test_invalid_plan_is_error(self):
        result, errors = select_tasks_module.select_tasks({})
        self.assertIsNone(result)
        self.assertTrue(errors)

    def test_count_below_one_is_error(self):
        result, errors = select_tasks_module.select_tasks({"tasks": []}, count=0)
        self.assertIsNone(result)
        self.assertTrue(errors)


class RunCliTest(unittest.TestCase):
    def _run(self, plan_path, extra_args=None):
        args = [sys.executable, str(SCRIPT), "--plan-path", str(plan_path)]
        args.extend(extra_args or [])
        return subprocess.run(args, capture_output=True, text=True)

    def test_success_exit_code_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "foo_plan.json"
            plan_path.write_text(
                json.dumps({"tasks": [_task("TASK-001", priority=99)]}),
                encoding="utf-8",
            )
            result = self._run(plan_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["units"][0]["task_ids"], ["TASK-001"])
            self.assertNotIn("status", payload)

    def test_empty_selection_is_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "foo_plan.json"
            plan_path.write_text(json.dumps({"tasks": []}), encoding="utf-8")
            result = self._run(plan_path)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout), {"units": []})

    def test_missing_plan_file_is_exit_one_with_errors(self):
        result = self._run(Path("/nonexistent/plan.json"))
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["errors"])

    def test_argument_error_is_exit_two(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2)

    def test_count_zero_is_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "foo_plan.json"
            plan_path.write_text(json.dumps({"tasks": []}), encoding="utf-8")
            result = self._run(plan_path, ["--count", "0"])
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
