#!/usr/bin/env python3
"""plan_inspection.py（計画書検査 CH-01）の単体テスト。

5 種の違反（自己依存・存在しないタスクへの依存・依存の循環・設計 ID の不一致・
必読文書の型の誤り）がそれぞれ検出されること、違反が無ければ空の一覧を返すこと、
入力を変更しないことを検証する。
"""

import copy
import importlib.util
import unittest
from pathlib import Path


_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "forge"
    / "scripts"
    / "plan"
    / "plan_inspection.py"
)
_SPEC = importlib.util.spec_from_file_location("plan_inspection", _MODULE_PATH)
plan_inspection = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(plan_inspection)


def make_task(task_id, depends_on=None, design_id="DES-001", required_reading=None):
    return {
        "task_id": task_id,
        "title": task_id,
        "priority": 50,
        "status": "pending",
        "design_id": design_id,
        "depends_on": depends_on or [],
        "group_id": None,
        "build_check": "per_task",
        "description": ["x"],
        "acceptance_criteria": None,
        "required_reading": required_reading if required_reading is not None else [],
    }


def make_plan(tasks):
    return {
        "requirements_traceability": [],
        "design_traceability": [
            {
                "design_id": "DES-001",
                "requirement_ids": [],
                "task_ids": [t["task_id"] for t in tasks],
            }
        ],
        "tasks": tasks,
    }


class FindDependencyViolationsTest(unittest.TestCase):
    def test_no_violation_returns_empty_list(self):
        deps = {"A": [], "B": ["A"], "C": ["A", "B"]}
        self.assertEqual(plan_inspection.find_dependency_violations(deps), [])

    def test_self_dependency(self):
        result = plan_inspection.find_dependency_violations({"A": ["A"]})
        self.assertEqual(len(result), 1)
        self.assertIn("A", result[0])
        self.assertIn("自分自身", result[0])

    def test_unknown_dependency(self):
        result = plan_inspection.find_dependency_violations({"A": ["X"]})
        self.assertEqual(len(result), 1)
        self.assertIn("存在しない", result[0])
        self.assertIn("X", result[0])

    def test_cycle_of_two(self):
        result = plan_inspection.find_dependency_violations({"A": ["B"], "B": ["A"]})
        self.assertEqual(len(result), 1)
        self.assertIn("循環", result[0])
        self.assertIn("A", result[0])
        self.assertIn("B", result[0])

    def test_cycle_of_three_with_tail(self):
        deps = {"A": ["B"], "B": ["C"], "C": ["A"], "D": ["A"]}
        result = plan_inspection.find_dependency_violations(deps)
        self.assertEqual(len(result), 1)
        self.assertIn("循環", result[0])

    def test_self_dependency_is_not_reported_as_cycle(self):
        result = plan_inspection.find_dependency_violations({"A": ["A"]})
        self.assertFalse(any("循環" in message for message in result))

    def test_diamond_is_not_a_cycle(self):
        deps = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}
        self.assertEqual(plan_inspection.find_dependency_violations(deps), [])

    def test_long_chain_does_not_hit_recursion_limit(self):
        deps = {"T0": []}
        for i in range(1, 5000):
            deps[f"T{i}"] = [f"T{i - 1}"]
        self.assertEqual(plan_inspection.find_dependency_violations(deps), [])

    def test_does_not_mutate_input(self):
        deps = {"A": ["B", "A"], "B": ["A", "X"]}
        before = copy.deepcopy(deps)
        plan_inspection.find_dependency_violations(deps)
        self.assertEqual(deps, before)


class InspectPlanTest(unittest.TestCase):
    def test_valid_plan_returns_empty_list(self):
        plan = make_plan(
            [
                make_task("TASK-001", required_reading=["docs/a.md"]),
                make_task("TASK-002", depends_on=["TASK-001"]),
                make_task("TASK-003", design_id=None),
            ]
        )
        self.assertEqual(plan_inspection.inspect_plan(plan), [])

    def test_self_dependency(self):
        plan = make_plan([make_task("TASK-001", depends_on=["TASK-001"])])
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("自分自身", result[0])

    def test_unknown_dependency(self):
        plan = make_plan([make_task("TASK-001", depends_on=["TASK-999"])])
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("TASK-999", result[0])

    def test_cycle(self):
        plan = make_plan(
            [
                make_task("TASK-001", depends_on=["TASK-002"]),
                make_task("TASK-002", depends_on=["TASK-001"]),
            ]
        )
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("循環", result[0])

    def test_dependency_on_task_with_invalid_depends_on_is_not_reported_as_unknown(
        self,
    ):
        plan = make_plan(
            [
                make_task("TASK-001", depends_on=["TASK-002"]),
                make_task("TASK-002", depends_on="TASK-003"),
            ]
        )
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("TASK-002 の depends_on", result[0])

    def test_non_string_task_id_is_reported_as_task_id(self):
        plan = make_plan([make_task(123, depends_on=[])])
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("task_id は文字列", result[0])

    def test_design_id_not_in_traceability(self):
        plan = make_plan([make_task("TASK-001", design_id="DES-999")])
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("DES-999", result[0])
        self.assertIn("TASK-001", result[0])

    def test_null_design_id_is_allowed(self):
        plan = make_plan([make_task("TASK-001", design_id=None)])
        self.assertEqual(plan_inspection.inspect_plan(plan), [])

    def test_required_reading_not_list(self):
        plan = make_plan([make_task("TASK-001")])
        plan["tasks"][0]["required_reading"] = "docs/a.md"
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("required_reading", result[0])

    def test_required_reading_object_instead_of_array(self):
        plan = make_plan([make_task("TASK-001")])
        plan["tasks"][0]["required_reading"] = {"design_docs": ["docs/a.md"]}
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("required_reading", result[0])

    def test_required_reading_with_non_string_element(self):
        plan = make_plan([make_task("TASK-001", required_reading=["docs/a.md", 1])])
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("required_reading", result[0])

    def test_multiple_violations_are_all_reported(self):
        plan = make_plan(
            [
                make_task("TASK-001", depends_on=["TASK-001"], design_id="DES-999"),
                make_task("TASK-002", depends_on=["TASK-404"]),
            ]
        )
        self.assertEqual(len(plan_inspection.inspect_plan(plan)), 3)

    def test_does_not_mutate_input(self):
        plan = make_plan(
            [
                make_task(
                    "TASK-001", depends_on=["TASK-002", "TASK-001"], design_id="DES-999"
                ),
                make_task("TASK-002", depends_on=["TASK-001"]),
            ]
        )
        plan["tasks"][1]["required_reading"] = "bad"
        before = copy.deepcopy(plan)
        plan_inspection.inspect_plan(plan)
        self.assertEqual(plan, before)

    def test_requirement_traceable_to_task_returns_empty_list(self):
        plan = make_plan([make_task("TASK-001")])
        plan["requirements_traceability"] = [
            {"requirement_id": "REQ-001", "design_id": "DES-001", "status": "pending"}
        ]
        self.assertEqual(plan_inspection.inspect_plan(plan), [])

    def test_requirement_without_design_id(self):
        plan = make_plan([make_task("TASK-001")])
        plan["requirements_traceability"] = [
            {"requirement_id": "REQ-001", "status": "pending"}
        ]
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("REQ-001", result[0])
        self.assertIn("設計が", result[0])

    def test_requirement_with_design_not_in_traceability(self):
        plan = make_plan([make_task("TASK-001")])
        plan["requirements_traceability"] = [
            {"requirement_id": "REQ-001", "design_id": "DES-999", "status": "pending"}
        ]
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("REQ-001", result[0])

    def test_requirement_whose_design_has_no_task(self):
        plan = make_plan([make_task("TASK-001")])
        plan["design_traceability"][0]["task_ids"] = []
        plan["requirements_traceability"] = [
            {"requirement_id": "REQ-001", "design_id": "DES-001", "status": "pending"}
        ]
        result = plan_inspection.inspect_plan(plan)
        self.assertEqual(len(result), 1)
        self.assertIn("REQ-001", result[0])
        self.assertIn("DES-001", result[0])
        self.assertIn("タスクが 1 件も無", result[0])

    def test_non_dict_plan_and_non_list_tasks(self):
        self.assertEqual(len(plan_inspection.inspect_plan([])), 1)
        self.assertEqual(len(plan_inspection.inspect_plan({"tasks": {}})), 1)


if __name__ == "__main__":
    unittest.main()
