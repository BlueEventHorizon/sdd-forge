#!/usr/bin/env python3
"""plan_contract.py（計画書の読み書き・スキーマ検証・グループ正規化）のテスト。

実行:
  python3 -m unittest tests.forge.plan.test_plan_contract -v
"""

import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "forge"
    / "scripts"
    / "plan"
    / "plan_contract.py"
)
_SPEC = importlib.util.spec_from_file_location("plan_contract", _MODULE_PATH)
plan_contract = importlib.util.module_from_spec(_SPEC)
sys.modules["plan_contract"] = plan_contract
_SPEC.loader.exec_module(plan_contract)


def _valid_task(**overrides):
    task = {
        "task_id": "TASK-001",
        "title": "Foo を実装する",
        "priority": 50,
        "status": "pending",
        "design_id": None,
        "depends_on": [],
        "group_id": None,
        "build_check": "per_task",
        "description": ["Foo を作る"],
        "acceptance_criteria": None,
        "required_reading": [],
    }
    task.update(overrides)
    return task


def _valid_plan(**overrides):
    plan = {
        "requirements_traceability": [],
        "design_traceability": [],
        "tasks": [_valid_task()],
    }
    plan.update(overrides)
    return plan


class LoadSavePlanTest(unittest.TestCase):
    def test_save_then_load_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_plan.json"
            data = _valid_plan()
            plan_contract.save_plan(path, data)
            loaded = plan_contract.load_plan(path)
            self.assertEqual(loaded, data)

    def test_save_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "dir" / "feature_plan.json"
            plan_contract.save_plan(path, _valid_plan())
            self.assertTrue(path.is_file())

    def test_load_missing_file_raises_contract_error(self):
        with self.assertRaises(plan_contract.PlanContractError):
            plan_contract.load_plan("/nonexistent/path/feature_plan.json")

    def test_load_invalid_json_raises_contract_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_plan.json"
            path.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(plan_contract.PlanContractError):
                plan_contract.load_plan(path)


class SavePlanAtomicTest(unittest.TestCase):
    def test_failure_during_write_keeps_existing_plan_and_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_plan.json"
            plan_contract.save_plan(path, _valid_plan())
            before = path.read_bytes()
            with mock.patch.object(
                plan_contract.json, "dump", side_effect=OSError("disk full")
            ):
                with self.assertRaises(OSError):
                    plan_contract.save_plan(path, _valid_plan(tasks=[]))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(
                [p.name for p in Path(tmp).iterdir()], ["feature_plan.json"]
            )

    def test_failure_during_replace_keeps_existing_plan_and_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_plan.json"
            plan_contract.save_plan(path, _valid_plan())
            before = path.read_bytes()
            with mock.patch.object(
                plan_contract.os, "replace", side_effect=OSError("boom")
            ):
                with self.assertRaises(OSError):
                    plan_contract.save_plan(path, _valid_plan(tasks=[]))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(
                [p.name for p in Path(tmp).iterdir()], ["feature_plan.json"]
            )

    def test_existing_plan_keeps_its_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_plan.json"
            plan_contract.save_plan(path, _valid_plan())
            os.chmod(path, 0o640)
            plan_contract.save_plan(path, _valid_plan(tasks=[]))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)

    def test_new_plan_follows_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_plan.json"
            old_umask = os.umask(0o022)
            try:
                plan_contract.save_plan(path, _valid_plan())
            finally:
                os.umask(old_umask)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_output_format_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_plan.json"
            data = {"tasks": [{"title": "日本語"}]}
            plan_contract.save_plan(path, data)
            expected = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            self.assertEqual(path.read_text(encoding="utf-8"), expected)


class ValidatePlanSchemaTest(unittest.TestCase):
    def test_valid_plan_has_no_errors(self):
        self.assertEqual(plan_contract.validate_plan_schema(_valid_plan()), [])

    def test_duplicate_task_ids_are_rejected(self):
        plan = _valid_plan(
            tasks=[_valid_task(), _valid_task(title="同じ ID の別タスク")]
        )
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("TASK-001" in e and "重複" in e for e in errors))

    def test_distinct_task_ids_are_accepted(self):
        plan = _valid_plan(tasks=[_valid_task(), _valid_task(task_id="TASK-002")])
        self.assertEqual(plan_contract.validate_plan_schema(plan), [])

    def test_task_ids_must_be_nonempty_strings(self):
        for task_id in (None, 1, [], {}, "", " "):
            with self.subTest(task_id=task_id):
                errors = plan_contract.validate_plan_schema(
                    _valid_plan(tasks=[_valid_task(task_id=task_id)])
                )
                self.assertTrue(any("task_id" in e for e in errors))

    def test_non_dict_plan_is_rejected(self):
        errors = plan_contract.validate_plan_schema(["not", "a", "dict"])
        self.assertTrue(errors)

    def test_missing_top_level_key_is_reported(self):
        plan = _valid_plan()
        del plan["design_traceability"]
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("design_traceability" in e for e in errors))

    def test_design_traceability_without_requirement_ids_is_reported(self):
        """requirement_ids が無いと要件のステータス更新が辿る経路が途切れる。"""
        plan = _valid_plan(
            design_traceability=[{"design_id": "DES-001", "task_ids": ["TASK-001"]}]
        )
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("requirement_ids" in e for e in errors))

    def test_design_traceability_with_required_fields_is_accepted(self):
        plan = _valid_plan(
            design_traceability=[
                {
                    "design_id": "DES-001",
                    "requirement_ids": ["FNC-001"],
                    "task_ids": ["TASK-001"],
                }
            ]
        )
        self.assertEqual(plan_contract.validate_plan_schema(plan), [])

    def test_unknown_top_level_key_is_reported(self):
        plan = _valid_plan(extra_key="not allowed")
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("extra_key" in e for e in errors))

    def test_feature_meta_key_is_rejected(self):
        plan = _valid_plan(
            _feature_meta={"feature_type": "temporary-feature", "feature_note": []}
        )
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("_feature_meta" in e for e in errors))

    def test_tasks_must_be_a_list(self):
        plan = _valid_plan(tasks="not a list")
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("tasks は配列" in e for e in errors))

    def test_task_missing_required_field_is_reported(self):
        task = _valid_task()
        del task["priority"]
        plan = _valid_plan(tasks=[task])
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("priority" in e for e in errors))

    def test_task_unknown_field_is_reported(self):
        task = _valid_task(unexpected_field="x")
        plan = _valid_plan(tasks=[task])
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("unexpected_field" in e for e in errors))

    def test_task_invalid_status_is_reported(self):
        task = _valid_task(status="not-a-status")
        plan = _valid_plan(tasks=[task])
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("status" in e for e in errors))

    def test_task_accepts_all_five_statuses(self):
        for status in ("pending", "in_progress", "implemented", "completed", "failed"):
            plan = _valid_plan(tasks=[_valid_task(status=status)])
            self.assertEqual(plan_contract.validate_plan_schema(plan), [], status)

    def test_task_rejects_other_statuses(self):
        for status in ("done", "skipped", "", None, "Pending"):
            plan = _valid_plan(tasks=[_valid_task(status=status)])
            errors = plan_contract.validate_plan_schema(plan)
            self.assertTrue(any("status" in e for e in errors), repr(status))

    def test_task_invalid_build_check_is_reported(self):
        task = _valid_task(build_check="invalid")
        plan = _valid_plan(tasks=[task])
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("build_check" in e for e in errors))

    def test_task_status_and_build_check_of_unhashable_type_are_reported(self):
        for field in ("status", "build_check"):
            with self.subTest(field=field):
                plan = _valid_plan(tasks=[_valid_task(**{field: ["x"]})])
                errors = plan_contract.validate_plan_schema(plan)
                self.assertTrue(any(field in e for e in errors))

    def test_validate_task_is_public_and_labels_the_index(self):
        errors = plan_contract.validate_task(3, _valid_task(build_check="invalid"))
        self.assertTrue(any(e.startswith("tasks[3]") for e in errors))

    def test_task_depends_on_must_be_list(self):
        task = _valid_task(depends_on="TASK-000")
        plan = _valid_plan(tasks=[task])
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("depends_on" in e for e in errors))

    def test_task_required_reading_must_be_list(self):
        task = _valid_task(required_reading="not a list")
        plan = _valid_plan(tasks=[task])
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("required_reading" in e for e in errors))

    def test_task_design_id_must_be_string_or_null(self):
        task = _valid_task(design_id=123)
        plan = _valid_plan(tasks=[task])
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("design_id" in e for e in errors))

    def test_requirement_traceability_invalid_status_is_reported(self):
        plan = _valid_plan(
            requirements_traceability=[
                {
                    "requirement_id": "REQ-001",
                    "title": "x",
                    "design_id": None,
                    "status": "bogus",
                }
            ]
        )
        errors = plan_contract.validate_plan_schema(plan)
        self.assertTrue(any("requirements_traceability[0].status" in e for e in errors))


class NormalizeGroupKeyTest(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(plan_contract.normalize_group_key(None))

    def test_strips_sequence_suffix(self):
        self.assertEqual(
            plan_contract.normalize_group_key("GROUP-001 (1/7)"), "GROUP-001"
        )

    def test_without_parentheses_returns_as_is(self):
        self.assertEqual(plan_contract.normalize_group_key("GROUP-001"), "GROUP-001")


if __name__ == "__main__":
    unittest.main()
