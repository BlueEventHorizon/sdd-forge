#!/usr/bin/env python3
"""check_startup.py（起動確認 CK-01）の単体テスト。"""

import importlib.util
import json
import os
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
    / "check_startup.py"
)

_SPEC = importlib.util.spec_from_file_location("check_startup", SCRIPT)
check_startup = importlib.util.module_from_spec(_SPEC)
sys.modules["check_startup"] = check_startup
_SPEC.loader.exec_module(check_startup)


def _plan(*statuses):
    return {
        "requirements_traceability": [],
        "design_traceability": [],
        "tasks": [
            {"task_id": f"TASK-{i:03d}", "status": s}
            for i, s in statuses_enumerated(statuses)
        ],
    }


def statuses_enumerated(statuses):
    return list(enumerate(statuses, start=1))


class StartupStateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.plan_path = self.dir / "feature_plan.json"

    def _write(self, data):
        self.plan_path.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def test_no_plan(self):
        self.assertEqual(
            check_startup.determine_startup_state(self.plan_path), {"state": "no_plan"}
        )

    def test_leftover_lists_in_progress_ids_in_plan_order(self):
        self._write(_plan("completed", "in_progress", "pending", "in_progress"))
        self.assertEqual(
            check_startup.determine_startup_state(self.plan_path),
            {"state": "leftover", "in_progress_task_ids": ["TASK-002", "TASK-004"]},
        )

    def test_clear_when_no_in_progress(self):
        self._write(_plan("completed", "pending", "implemented"))
        self.assertEqual(
            check_startup.determine_startup_state(self.plan_path), {"state": "clear"}
        )

    def test_failed_ids_are_listed_in_plan_order_with_clear(self):
        """失敗のタスクは選択されないため、クリアして再開するかを利用者が決める材料として返す。"""
        self._write(_plan("failed", "completed", "pending", "failed"))
        self.assertEqual(
            check_startup.determine_startup_state(self.plan_path),
            {"state": "clear", "failed_task_ids": ["TASK-001", "TASK-004"]},
        )

    def test_failed_ids_are_listed_with_leftover(self):
        self._write(_plan("in_progress", "failed"))
        self.assertEqual(
            check_startup.determine_startup_state(self.plan_path),
            {
                "state": "leftover",
                "in_progress_task_ids": ["TASK-001"],
                "failed_task_ids": ["TASK-002"],
            },
        )

    def test_failed_key_is_absent_when_no_failed(self):
        self._write(_plan("pending", "completed"))
        self.assertNotIn(
            "failed_task_ids", check_startup.determine_startup_state(self.plan_path)
        )

    def test_failed_without_task_id_is_error(self):
        self._write({"tasks": [{"status": "failed"}]})
        with self.assertRaises(check_startup.InvalidPlanError):
            check_startup.determine_startup_state(self.plan_path)

    def test_clear_when_no_tasks(self):
        self._write(_plan())
        self.assertEqual(
            check_startup.determine_startup_state(self.plan_path), {"state": "clear"}
        )

    def test_leftover_has_key_only_in_leftover(self):
        self._write(_plan("pending"))
        self.assertNotIn(
            "in_progress_task_ids",
            check_startup.determine_startup_state(self.plan_path),
        )

    def test_plan_is_not_modified(self):
        self._write(_plan("in_progress", "pending"))
        before = self.plan_path.read_bytes()
        mtime = self.plan_path.stat().st_mtime_ns
        check_startup.determine_startup_state(self.plan_path)
        self.assertEqual(self.plan_path.read_bytes(), before)
        self.assertEqual(self.plan_path.stat().st_mtime_ns, mtime)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["feature_plan.json"])

    def test_broken_json_is_error_not_no_plan(self):
        self.plan_path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(check_startup.PlanContractError):
            check_startup.determine_startup_state(self.plan_path)

    def test_unreadable_plan_path_is_error(self):
        self.plan_path.mkdir()  # 存在するが、ファイルとして読めない
        with self.assertRaises(check_startup.PlanContractError):
            check_startup.determine_startup_state(self.plan_path)

    def test_plan_whose_existence_cannot_be_checked_is_error_not_no_plan(self):
        if os.geteuid() == 0:
            self.skipTest("root は権限で拒否されない")
        locked = self.dir / "locked"
        locked.mkdir()
        self.addCleanup(os.chmod, locked, 0o700)
        os.chmod(locked, 0o000)
        with self.assertRaises(check_startup.PlanContractError):
            check_startup.determine_startup_state(locked / "feature_plan.json")

    def test_non_object_plan_is_error(self):
        self._write([])
        with self.assertRaises(check_startup.InvalidPlanError):
            check_startup.determine_startup_state(self.plan_path)

    def test_missing_tasks_is_error(self):
        self._write({"design_traceability": []})
        with self.assertRaises(check_startup.InvalidPlanError):
            check_startup.determine_startup_state(self.plan_path)

    def test_non_object_task_is_error(self):
        self._write({"tasks": ["TASK-001"]})
        with self.assertRaises(check_startup.InvalidPlanError):
            check_startup.determine_startup_state(self.plan_path)

    def test_in_progress_without_task_id_is_error(self):
        self._write({"tasks": [{"status": "in_progress"}]})
        with self.assertRaises(check_startup.InvalidPlanError):
            check_startup.determine_startup_state(self.plan_path)


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.plan_path = Path(self._tmp.name) / "feature_plan.json"

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_no_plan_exit_0(self):
        result = self._run("--plan-path", str(self.plan_path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"state": "no_plan"})

    def test_leftover_exit_0(self):
        self.plan_path.write_text(json.dumps(_plan("in_progress")), encoding="utf-8")
        result = self._run("--plan-path", str(self.plan_path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            json.loads(result.stdout),
            {"state": "leftover", "in_progress_task_ids": ["TASK-001"]},
        )

    def test_clear_exit_0(self):
        self.plan_path.write_text(json.dumps(_plan("completed")), encoding="utf-8")
        result = self._run("--plan-path", str(self.plan_path))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"state": "clear"})

    def test_broken_plan_exit_1_with_errors(self):
        self.plan_path.write_text("{ not json", encoding="utf-8")
        result = self._run("--plan-path", str(self.plan_path))
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertNotIn("state", payload)
        self.assertEqual(len(payload["errors"]), 1)
        self.assertIsInstance(payload["errors"][0], str)

    def test_missing_argument_exit_2(self):
        self.assertEqual(self._run().returncode, 2)


if __name__ == "__main__":
    unittest.main()
