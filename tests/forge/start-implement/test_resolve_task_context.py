#!/usr/bin/env python3
"""resolve_task_context.py（文脈作成 CX-02）の契約テスト。

- 解決: CX-01（build_task_context.py --create）が返した識別値から、絶対パスだけが返る
- 本文は標準出力に載らない
- 対応するファイルが無い・置き場の外を指す・シンボリックリンク・通常ファイルでないものは、
  パスを返さずエラーになる
- cwd に依存しない
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "forge" / "skills" / "start-implement" / "scripts"
SCRIPT = SCRIPTS_DIR / "resolve_task_context.py"
BUILD_SCRIPT = SCRIPTS_DIR / "build_task_context.py"

SECRET = "本文にだけ現れる目印-7f3a9c"
PLAN_REL = "docs/foo_plan.json"
TASKS_DIR = ("docs", "tasks")  # 計画書と同じディレクトリの tasks/


def run(script, *args, cwd=REPO_ROOT):
    completed = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout) if completed.stdout.strip() else None
    return completed.returncode, payload, completed


class ResolveCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)
        self.temp_dir = REPO_ROOT / ".temp" / "forge" / "start-implement"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.input_path = self.temp_dir / "test_resolve_task_context_input.json"
        self.addCleanup(lambda: self.input_path.unlink(missing_ok=True))

    def create_context(self, plan_rel=PLAN_REL):
        """CX-01 の本物の入口で識別値を作る。"""
        for rel, text in (
            ("docs/req.md", "# 要件\n"),
            ("docs/des.md", "# 設計\n"),
            ("docs/rule.md", "# ルール\n"),
        ):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        plan = self.root / plan_rel
        plan.parent.mkdir(parents=True, exist_ok=True)
        task = {
            "task_id": "TASK-001",
            "title": "t",
            "priority": 70,
            "status": "in_progress",
            "design_id": "DES-001",
            "depends_on": [],
            "group_id": None,
            "build_check": "per_task",
            "description": ["d"],
            "acceptance_criteria": None,
            "required_reading": [],
        }
        plan.write_text(
            json.dumps({"tasks": [task]}, ensure_ascii=False), encoding="utf-8"
        )
        candidate = {
            "task_id": "TASK-001",
            "scope_in": "範囲",
            "scope_out": [],
            "required_reading": {
                "design_docs": ["docs/des.md"],
                "requirement_docs": ["docs/req.md"],
                "strategy_doc": None,
                "rule_docs": ["docs/rule.md"],
                "reference_code": [],
                "additional": [],
            },
            "collected_paths": ["docs/des.md", "docs/req.md", "docs/rule.md"],
            "implementation_instructions": SECRET,
            "verification": {"tests": "required", "tests_reason": None},
        }
        self.input_path.write_text(
            json.dumps(candidate, ensure_ascii=False), encoding="utf-8"
        )
        code, payload, _ = run(
            BUILD_SCRIPT,
            "--create",
            "--project-root",
            str(self.root),
            "--plan-path",
            str(plan),
            "--task-id",
            "TASK-001",
            "--input-file",
            str(self.input_path.relative_to(REPO_ROOT)),
        )
        self.assertEqual(code, 0, payload)
        return payload["context_id"]

    def resolve(self, context_id, plan_path=PLAN_REL, cwd=REPO_ROOT):
        return run(
            SCRIPT,
            "--project-root",
            str(self.root),
            "--plan-path",
            plan_path,
            "--context-id",
            context_id,
            cwd=cwd,
        )

    def assert_error_without_path(self, code, payload, completed):
        self.assertEqual(code, 1)
        self.assertEqual(set(payload), {"errors"})
        self.assertTrue(payload["errors"])
        self.assertNotIn("path", payload)


class ResolveTest(ResolveCase):
    def test_returns_absolute_path_of_the_created_context(self):
        context_id = self.create_context()
        code, payload, _ = self.resolve(context_id)
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"path"})
        path = Path(payload["path"])
        self.assertTrue(path.is_absolute())
        self.assertEqual(path, self.root.joinpath(*TASKS_DIR, f"{context_id}.json"))
        self.assertTrue(path.is_file())
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8"))["task_id"], "TASK-001"
        )

    def test_stdout_does_not_contain_the_body(self):
        context_id = self.create_context()
        _, _, completed = self.resolve(context_id)
        self.assertNotIn(SECRET, completed.stdout)
        self.assertNotIn("implementation_instructions", completed.stdout)

    def test_result_does_not_depend_on_cwd(self):
        context_id = self.create_context()
        with tempfile.TemporaryDirectory() as other:
            _, first, _ = self.resolve(context_id, cwd=REPO_ROOT)
            _, second, _ = self.resolve(context_id, cwd=other)
        self.assertEqual(first, second)

    def test_relative_project_root_resolves_to_absolute(self):
        context_id = self.create_context()
        code, payload, _ = run(
            SCRIPT,
            "--project-root",
            ".",
            "--plan-path",
            PLAN_REL,
            "--context-id",
            context_id,
            cwd=self.root,
        )
        self.assertEqual(code, 0)
        self.assertTrue(Path(payload["path"]).is_absolute())

    def test_plan_path_separates_contexts(self):
        """別の計画書の tasks/ からは解決できない。"""
        context_id = self.create_context()
        self.assert_error_without_path(
            *self.resolve(context_id, plan_path="docs/other/bar_plan.json")
        )


class RejectionTest(ResolveCase):
    def test_unknown_context_id_returns_error_without_path(self):
        self.create_context()
        result = self.resolve("TASK-001-00000000")
        self.assert_error_without_path(*result)
        self.assertTrue(any("識別値" in e for e in result[1]["errors"]))

    def test_missing_tasks_directory_returns_error(self):
        self.assert_error_without_path(
            *self.resolve("TASK-001-00000000", plan_path="docs/never/never_plan.json")
        )

    def test_deleted_context_is_not_resolved(self):
        context_id = self.create_context()
        run(
            BUILD_SCRIPT,
            "--delete",
            "--project-root",
            str(self.root),
            "--plan-path",
            PLAN_REL,
            "--context-id",
            context_id,
        )
        self.assert_error_without_path(*self.resolve(context_id))

    def test_context_id_pointing_outside_the_directory_is_rejected(self):
        outside = self.root / "docs" / "victim.json"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("{}", encoding="utf-8")
        for bad in ("..", ".", "../../victim", "../victim", "a/b", "a\\b", ""):
            with self.subTest(context_id=bad):
                result = self.resolve(bad)
                self.assert_error_without_path(*result)

    def test_plan_path_outside_the_project_root_is_rejected(self):
        for bad in ("", "../x_plan.json", "/x_plan.json"):
            with self.subTest(plan_path=bad):
                result = self.resolve("TASK-001-00000000", plan_path=bad)
                self.assert_error_without_path(*result)
                self.assertTrue(
                    any("plan-path" in e for e in result[1]["errors"]), result[1]
                )

    def test_symlink_is_not_accepted(self):
        target = self.root / "elsewhere.json"
        target.write_text("{}", encoding="utf-8")
        directory = self.root.joinpath(*TASKS_DIR)
        directory.mkdir(parents=True)
        (directory / "TASK-001-deadbeef.json").symlink_to(target)
        self.assert_error_without_path(*self.resolve("TASK-001-deadbeef"))

    def test_dangling_symlink_is_not_accepted(self):
        directory = self.root.joinpath(*TASKS_DIR)
        directory.mkdir(parents=True)
        (directory / "TASK-001-deadbeef.json").symlink_to(self.root / "nowhere.json")
        self.assert_error_without_path(*self.resolve("TASK-001-deadbeef"))

    def test_directory_is_not_accepted(self):
        directory = self.root.joinpath(*TASKS_DIR, "TASK-001-deadbeef.json")
        directory.mkdir(parents=True)
        self.assert_error_without_path(*self.resolve("TASK-001-deadbeef"))

    def test_project_root_that_is_not_a_directory_is_rejected(self):
        code, payload, _ = run(
            SCRIPT,
            "--project-root",
            str(self.root / "no_such_dir"),
            "--plan-path",
            PLAN_REL,
            "--context-id",
            "TASK-001-00000000",
        )
        self.assert_error_without_path(code, payload, None)


class ExitCodeTest(ResolveCase):
    def test_only_0_1_2_are_used(self):
        context_id = self.create_context()
        self.assertEqual(self.resolve(context_id)[0], 0)
        self.assertEqual(self.resolve("TASK-001-00000000")[0], 1)
        code, _, _ = run(SCRIPT, "--project-root", str(self.root), "--feature", "foo")
        self.assertEqual(code, 2)
        code, _, _ = run(SCRIPT)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
