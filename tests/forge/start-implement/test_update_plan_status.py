#!/usr/bin/env python3
"""update_plan_status.py（状態遷移 ST-01〜04）の契約テスト。"""

import copy
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
    / "update_plan_status.py"
)

_SPEC = importlib.util.spec_from_file_location("update_plan_status", SCRIPT)
update_plan_status_module = importlib.util.module_from_spec(_SPEC)
sys.modules["update_plan_status"] = update_plan_status_module
_SPEC.loader.exec_module(update_plan_status_module)

transition_plan = update_plan_status_module.transition_plan


def _task(task_id, status="pending", depends_on=None, group_id=None):
    return {
        "task_id": task_id,
        "title": task_id,
        "priority": 50,
        "status": status,
        "design_id": None,
        "depends_on": depends_on or [],
        "group_id": group_id,
        "build_check": "per_task",
        "description": ["x"],
        "acceptance_criteria": None,
        "required_reading": [],
    }


def _plan(tasks, requirements=None, designs=None):
    return {
        "requirements_traceability": requirements or [],
        "design_traceability": designs or [],
        "tasks": tasks,
    }


def _status(plan, task_id):
    return next(t["status"] for t in plan["tasks"] if t["task_id"] == task_id)


class AllowedTransitionsTest(unittest.TestCase):
    def test_pending_to_in_progress(self):
        plan, result, errors = transition_plan(
            _plan([_task("T1")]), "in_progress", ["T1"]
        )
        self.assertEqual(errors, [])
        self.assertEqual(_status(plan, "T1"), "in_progress")
        self.assertEqual(result["updated_tasks"], {"T1": "in_progress"})

    def test_failed_to_in_progress_rerun(self):
        plan, _, errors = transition_plan(
            _plan([_task("T1", "failed")]), "in_progress", ["T1"]
        )
        self.assertEqual(errors, [])
        self.assertEqual(_status(plan, "T1"), "in_progress")

    def test_failed_to_pending_clear(self):
        """利用者の指示で失敗をクリアし、次の選択の対象に戻す。依存するタスクは変えない。"""
        tasks = [
            _task("T1", "failed"),
            _task("T2", "pending", depends_on=["T1"]),
            _task("T3", "implemented", depends_on=["T1"], group_id="GROUP-001 (1/1)"),
        ]
        plan, result, errors = transition_plan(_plan(tasks), "pending", ["T1"])
        self.assertEqual(errors, [])
        self.assertEqual(_status(plan, "T1"), "pending")
        self.assertEqual(_status(plan, "T2"), "pending")
        self.assertEqual(_status(plan, "T3"), "implemented")
        self.assertEqual(result["updated_tasks"], {"T1": "pending"})
        self.assertEqual(result["reverted_task_ids"], [])
        self.assertEqual(result["completed_requirement_ids"], [])

    def test_group_member_in_progress_to_implemented(self):
        plan, _, errors = transition_plan(
            _plan([_task("T1", "in_progress", group_id="GROUP-001 (1/2)")]),
            "implemented",
            ["T1"],
        )
        self.assertEqual(errors, [])
        self.assertEqual(_status(plan, "T1"), "implemented")

    def test_non_group_in_progress_to_completed(self):
        plan, _, errors = transition_plan(
            _plan([_task("T1", "in_progress")]), "completed", ["T1"]
        )
        self.assertEqual(errors, [])
        self.assertEqual(_status(plan, "T1"), "completed")

    def test_group_members_implemented_to_completed_together(self):
        tasks = [
            _task("T1", "implemented", group_id="GROUP-001 (1/2)"),
            _task("T2", "implemented", group_id="GROUP-001 (2/2)"),
        ]
        plan, _, errors = transition_plan(_plan(tasks), "completed", ["T1", "T2"])
        self.assertEqual(errors, [])
        self.assertEqual(_status(plan, "T1"), "completed")
        self.assertEqual(_status(plan, "T2"), "completed")

    def test_in_progress_and_implemented_to_failed(self):
        tasks = [
            _task("T1", "in_progress"),
            _task("T2", "implemented", group_id="GROUP-001 (1/1)"),
        ]
        plan, _, errors = transition_plan(_plan(tasks), "failed", ["T1", "T2"])
        self.assertEqual(errors, [])
        self.assertEqual(_status(plan, "T1"), "failed")
        self.assertEqual(_status(plan, "T2"), "failed")


class DisallowedTransitionsTest(unittest.TestCase):
    def _assert_rejected(self, task, to):
        original = _plan([task])
        before = copy.deepcopy(original)
        plan, result, errors = transition_plan(original, to, [task["task_id"]])
        self.assertIsNone(plan)
        self.assertIsNone(result)
        self.assertTrue(errors)
        self.assertEqual(original, before, "入力を変更してはならない")

    def test_in_progress_from_invalid_states(self):
        for status in ("in_progress", "implemented", "completed"):
            with self.subTest(status=status):
                self._assert_rejected(_task("T1", status), "in_progress")

    def test_pending_only_from_failed(self):
        for status in ("pending", "in_progress", "implemented", "completed"):
            with self.subTest(status=status):
                self._assert_rejected(_task("T1", status), "pending")

    def test_implemented_requires_group_member(self):
        self._assert_rejected(_task("T1", "in_progress"), "implemented")

    def test_implemented_requires_in_progress(self):
        for status in ("pending", "implemented", "completed", "failed"):
            with self.subTest(status=status):
                self._assert_rejected(
                    _task("T1", status, group_id="G (1/1)"), "implemented"
                )

    def test_completed_non_group_requires_in_progress(self):
        for status in ("pending", "implemented", "completed", "failed"):
            with self.subTest(status=status):
                self._assert_rejected(_task("T1", status), "completed")

    def test_completed_group_member_requires_implemented(self):
        for status in ("pending", "in_progress", "completed", "failed"):
            with self.subTest(status=status):
                self._assert_rejected(
                    _task("T1", status, group_id="G (1/1)"), "completed"
                )

    def test_failed_from_invalid_states(self):
        for status in ("pending", "completed", "failed"):
            with self.subTest(status=status):
                self._assert_rejected(_task("T1", status), "failed")

    def test_unknown_task_id(self):
        plan, _, errors = transition_plan(_plan([_task("T1")]), "in_progress", ["T9"])
        self.assertIsNone(plan)
        self.assertTrue(any("T9" in e for e in errors))

    def test_unknown_mode(self):
        plan, _, errors = transition_plan(_plan([_task("T1")]), "pending", ["T1"])
        self.assertIsNone(plan)
        self.assertTrue(errors)

    def test_empty_task_list(self):
        plan, _, errors = transition_plan(_plan([_task("T1")]), "in_progress", [])
        self.assertIsNone(plan)
        self.assertTrue(errors)

    def test_missing_tasks_array(self):
        plan, _, errors = transition_plan({}, "in_progress", ["T1"])
        self.assertIsNone(plan)
        self.assertTrue(errors)


class AllOrNothingTest(unittest.TestCase):
    def test_one_invalid_among_many_changes_nothing(self):
        original = _plan([_task("T1"), _task("T2", "completed"), _task("T3")])
        before = copy.deepcopy(original)
        plan, result, errors = transition_plan(
            original, "in_progress", ["T1", "T2", "T3"]
        )
        self.assertIsNone(plan)
        self.assertIsNone(result)
        self.assertEqual(len(errors), 1)
        self.assertIn("T2", errors[0])
        self.assertEqual(original, before)

    def test_all_invalid_reported_together(self):
        original = _plan([_task("T1", "completed"), _task("T2", "completed")])
        _, _, errors = transition_plan(original, "in_progress", ["T1", "T2", "T9"])
        self.assertEqual(len(errors), 3)

    def test_input_not_mutated_on_success(self):
        original = _plan([_task("T1")])
        before = copy.deepcopy(original)
        plan, _, errors = transition_plan(original, "in_progress", ["T1"])
        self.assertEqual(errors, [])
        self.assertEqual(original, before)
        self.assertEqual(_status(plan, "T1"), "in_progress")


class DependencyPropagationTest(unittest.TestCase):
    def test_failed_reverts_transitive_implemented_dependents(self):
        g = "GROUP-001 (1/3)"
        tasks = [
            _task("T1", "in_progress", group_id=g),
            _task("T2", "implemented", depends_on=["T1"], group_id=g),
            _task("T3", "implemented", depends_on=["T2"], group_id=g),
        ]
        plan, result, errors = transition_plan(_plan(tasks), "failed", ["T1"])
        self.assertEqual(errors, [])
        self.assertEqual(_status(plan, "T1"), "failed")
        self.assertEqual(_status(plan, "T2"), "pending")
        self.assertEqual(_status(plan, "T3"), "pending")
        self.assertEqual(sorted(result["reverted_task_ids"]), ["T2", "T3"])

    def test_independent_implemented_is_kept(self):
        g = "GROUP-001 (1/3)"
        tasks = [
            _task("T1", "in_progress", group_id=g),
            _task("T2", "implemented", depends_on=["T1"], group_id=g),
            _task("T3", "implemented", group_id=g),
        ]
        plan, result, _ = transition_plan(_plan(tasks), "failed", ["T1"])
        self.assertEqual(_status(plan, "T2"), "pending")
        self.assertEqual(_status(plan, "T3"), "implemented")
        self.assertEqual(result["reverted_task_ids"], ["T2"])

    def test_non_implemented_dependents_are_untouched(self):
        tasks = [
            _task("T1", "in_progress"),
            _task("T2", "pending", depends_on=["T1"]),
            _task("T3", "failed", depends_on=["T1"]),
            _task("T4", "completed", depends_on=["T1"]),
        ]
        plan, result, _ = transition_plan(_plan(tasks), "failed", ["T1"])
        self.assertEqual(_status(plan, "T2"), "pending")
        self.assertEqual(_status(plan, "T3"), "failed")
        self.assertEqual(_status(plan, "T4"), "completed")
        self.assertEqual(result["reverted_task_ids"], [])

    def test_specified_dependent_becomes_failed_not_reverted(self):
        g = "GROUP-001 (1/2)"
        tasks = [
            _task("T1", "implemented", group_id=g),
            _task("T2", "implemented", depends_on=["T1"], group_id=g),
        ]
        plan, result, _ = transition_plan(_plan(tasks), "failed", ["T1", "T2"])
        self.assertEqual(_status(plan, "T2"), "failed")
        self.assertEqual(result["reverted_task_ids"], [])

    def test_no_revert_for_other_modes(self):
        tasks = [
            _task("T1", "failed"),
            _task("T2", "implemented", depends_on=["T1"], group_id="G (1/1)"),
        ]
        plan, result, _ = transition_plan(_plan(tasks), "in_progress", ["T1"])
        self.assertEqual(_status(plan, "T2"), "implemented")
        self.assertEqual(result["reverted_task_ids"], [])

    def test_cyclic_dependencies_terminate(self):
        g = "G (1/3)"
        tasks = [
            _task("T1", "in_progress", depends_on=["T2"], group_id=g),
            _task("T2", "implemented", depends_on=["T1"], group_id=g),
        ]
        plan, result, errors = transition_plan(_plan(tasks), "failed", ["T1"])
        self.assertEqual(errors, [])
        self.assertEqual(result["reverted_task_ids"], ["T2"])


def _req(requirement_id, status="pending"):
    return {
        "requirement_id": requirement_id,
        "title": "x",
        "design_id": "DES-001",
        "status": status,
    }


def _design(requirement_ids, task_ids, design_id="DES-001"):
    return {
        "design_id": design_id,
        "title": "x",
        "requirement_ids": requirement_ids,
        "task_ids": task_ids,
    }


class RequirementCompletionTest(unittest.TestCase):
    def test_completed_when_all_linked_tasks_done(self):
        plan = _plan(
            [_task("T1", "in_progress"), _task("T2", "completed")],
            requirements=[_req("REQ-001")],
            designs=[_design(["REQ-001"], ["T1", "T2"])],
        )
        updated, result, errors = transition_plan(plan, "completed", ["T1"])
        self.assertEqual(errors, [])
        self.assertEqual(updated["requirements_traceability"][0]["status"], "completed")
        self.assertEqual(result["completed_requirement_ids"], ["REQ-001"])

    def test_stays_pending_when_some_linked_task_incomplete(self):
        plan = _plan(
            [_task("T1", "in_progress"), _task("T2")],
            requirements=[_req("REQ-001")],
            designs=[_design(["REQ-001"], ["T1", "T2"])],
        )
        updated, result, _ = transition_plan(plan, "completed", ["T1"])
        self.assertEqual(updated["requirements_traceability"][0]["status"], "pending")
        self.assertEqual(result["completed_requirement_ids"], [])

    def test_requirement_without_tasks_is_not_completed(self):
        plan = _plan(
            [_task("T1", "in_progress")],
            requirements=[_req("REQ-001"), _req("REQ-002")],
            designs=[_design(["REQ-001"], ["T1"])],
        )
        updated, _, _ = transition_plan(plan, "completed", ["T1"])
        statuses = {
            r["requirement_id"]: r["status"]
            for r in updated["requirements_traceability"]
        }
        self.assertEqual(statuses, {"REQ-001": "completed", "REQ-002": "pending"})

    def test_requirement_with_empty_task_ids_is_not_completed(self):
        plan = _plan(
            [_task("T1", "in_progress")],
            requirements=[_req("REQ-001")],
            designs=[_design(["REQ-001"], [])],
        )
        updated, _, _ = transition_plan(plan, "completed", ["T1"])
        self.assertEqual(updated["requirements_traceability"][0]["status"], "pending")

    def test_tasks_linked_across_multiple_designs(self):
        plan = _plan(
            [_task("T1", "in_progress"), _task("T2", "pending")],
            requirements=[_req("REQ-001")],
            designs=[
                _design(["REQ-001"], ["T1"], "DES-001"),
                _design(["REQ-001"], ["T2"], "DES-002"),
            ],
        )
        updated, _, _ = transition_plan(plan, "completed", ["T1"])
        self.assertEqual(updated["requirements_traceability"][0]["status"], "pending")

    def test_unknown_linked_task_blocks_completion(self):
        plan = _plan(
            [_task("T1", "in_progress")],
            requirements=[_req("REQ-001")],
            designs=[_design(["REQ-001"], ["T1", "T-GHOST"])],
        )
        updated, _, _ = transition_plan(plan, "completed", ["T1"])
        self.assertEqual(updated["requirements_traceability"][0]["status"], "pending")

    def test_other_modes_do_not_complete_requirements(self):
        plan = _plan(
            [_task("T1", "completed"), _task("T2", "pending")],
            requirements=[_req("REQ-001")],
            designs=[_design(["REQ-001"], ["T1"])],
        )
        updated, result, _ = transition_plan(plan, "in_progress", ["T2"])
        self.assertEqual(updated["requirements_traceability"][0]["status"], "pending")
        self.assertEqual(result["completed_requirement_ids"], [])


class RunCliTest(unittest.TestCase):
    def _run(self, plan_path, to, task_arg):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--plan-path",
                str(plan_path),
                "--to",
                to,
                "--task",
                task_arg,
            ],
            capture_output=True,
            text=True,
        )

    def _write(self, tmp, plan):
        plan_path = Path(tmp) / "foo_plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        return plan_path

    def test_success_writes_plan_and_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = self._write(tmp, _plan([_task("T1")]))
            result = self._run(plan_path, "in_progress", "T1")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["updated_tasks"], {"T1": "in_progress"})
            written = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(written["tasks"][0]["status"], "in_progress")

    def test_failed_reports_reverted_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = "G (1/2)"
            plan_path = self._write(
                tmp,
                _plan(
                    [
                        _task("T1", "in_progress", group_id=g),
                        _task("T2", "implemented", depends_on=["T1"], group_id=g),
                    ]
                ),
            )
            result = self._run(plan_path, "failed", "T1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["reverted_task_ids"], ["T2"])

    def test_disallowed_transition_exits_1_and_keeps_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = self._write(tmp, _plan([_task("T1"), _task("T2", "completed")]))
            before = plan_path.read_text(encoding="utf-8")
            result = self._run(plan_path, "in_progress", "T1,T2")
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertIsInstance(payload["errors"], list)
            self.assertNotIn("status", payload)
            self.assertEqual(plan_path.read_text(encoding="utf-8"), before)

    def test_missing_plan_file_exits_1(self):
        result = self._run(Path("/nonexistent/plan.json"), "in_progress", "T1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("errors", json.loads(result.stdout))

    def test_invalid_mode_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = self._write(tmp, _plan([_task("T1")]))
            result = self._run(plan_path, "bogus", "T1")
            self.assertEqual(result.returncode, 2)

    def test_missing_args_exits_2(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
