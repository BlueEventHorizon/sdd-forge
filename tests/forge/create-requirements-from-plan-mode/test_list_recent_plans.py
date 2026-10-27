#!/usr/bin/env python3
"""list_recent_plans.py のテスト

実行:
  python3 -m unittest tests.forge.create-requirements-from-plan-mode.test_list_recent_plans -v
  （ハイフン入りパッケージ名のため、loader 経由で実行する）
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "forge"
    / "skills"
    / "create-requirements-from-plan-mode"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

from list_recent_plans import (  # noqa: E402
    PlansDirError,
    _extract_title,
    list_plans,
    main,
    resolve_plans_dir,
)


class TestExtractTitle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _write(self, name: str, body: str) -> Path:
        p = self.dir / name
        p.write_text(body, encoding="utf-8")
        return p

    def test_first_h1_extracted(self):
        p = self._write("a.md", "# Hello world\n\n本文\n")
        self.assertEqual(_extract_title(p), "Hello world")

    def test_h1_skips_non_heading_lines(self):
        p = self._write("a.md", "前置き\n\n# 本タイトル\n## サブ\n")
        self.assertEqual(_extract_title(p), "本タイトル")

    def test_no_heading_returns_stem(self):
        p = self._write("plain.md", "ただのテキスト\n## H2 only\n")
        self.assertEqual(_extract_title(p), "plain")

    def test_empty_h1_falls_back_to_stem(self):
        p = self._write("alpha.md", "# \n本文\n")
        self.assertEqual(_extract_title(p), "alpha")

    def test_unreadable_file_returns_stem(self):
        missing = self.dir / "ghost.md"
        # ファイルが存在しないケース。OSError は内部で握りつぶされ stem が返る
        self.assertEqual(_extract_title(missing), "ghost")


class TestListPlans(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _make(self, name: str, mtime: float, body: str = "# Title\n") -> Path:
        p = self.dir / name
        p.write_text(body, encoding="utf-8")
        os.utime(p, (mtime, mtime))
        return p

    def test_missing_dir(self):
        result = list_plans(self.dir / "does-not-exist", limit=5)
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["plans"], [])
        self.assertIsNone(result["latest"])

    def test_empty_dir(self):
        result = list_plans(self.dir, limit=5)
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["latest"])

    def test_sorted_descending_by_mtime(self):
        self._make("old.md", 1_700_000_000.0, "# Old\n")
        self._make("mid.md", 1_700_000_500.0, "# Mid\n")
        self._make("new.md", 1_700_001_000.0, "# New\n")

        result = list_plans(self.dir, limit=10)
        self.assertEqual(result["status"], "found")
        names = [Path(p["path"]).name for p in result["plans"]]
        self.assertEqual(names, ["new.md", "mid.md", "old.md"])
        self.assertEqual(Path(result["latest"]).name, "new.md")
        self.assertEqual(result["plans"][0]["title"], "New")

    def test_limit_truncates(self):
        for i in range(5):
            self._make(f"p{i}.md", 1_700_000_000.0 + i)

        result = list_plans(self.dir, limit=2)
        self.assertEqual(len(result["plans"]), 2)
        self.assertEqual(result["count"], 2)

    def test_only_md_files_listed(self):
        self._make("note.md", 1_700_000_000.0, "# md\n")
        # 非 .md は無視される
        (self.dir / "ignore.txt").write_text("# txt\n")
        (self.dir / "ignore.markdown").write_text("# markdown ext\n")

        result = list_plans(self.dir, limit=10)
        self.assertEqual(result["count"], 1)
        self.assertEqual(Path(result["plans"][0]["path"]).name, "note.md")


class TestResolvePlansDir(unittest.TestCase):
    """探索先の決定。優先順位は flag > env > settings（local > project > user）> default。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.root = base / "project"
        self.home = base / "home"
        (self.root / ".claude").mkdir(parents=True)
        (self.home / ".claude").mkdir(parents=True)

    def _write(self, where: Path, name: str, body) -> Path:
        """`<where>/.claude/<name>` に設定を書く。body が文字列ならそのまま、そうでなければ JSON にする。"""
        path = where / ".claude" / name
        path.write_text(
            body if isinstance(body, str) else json.dumps(body), encoding="utf-8"
        )
        return path

    def test_default_when_nothing_is_set(self):
        plans_dir, source = resolve_plans_dir(self.root, self.home, None, None)
        self.assertEqual(plans_dir, self.home / ".claude" / "plans")
        self.assertEqual(source, "default")

    def test_flag_beats_env_and_settings(self):
        self._write(self.root, "settings.json", {"plansDirectory": "from-settings"})
        plans_dir, source = resolve_plans_dir(
            self.root, self.home, str(self.root / "flag"), str(self.root / "env")
        )
        self.assertEqual(plans_dir, self.root / "flag")
        self.assertEqual(source, "flag")

    def test_env_beats_settings(self):
        self._write(self.root, "settings.json", {"plansDirectory": "from-settings"})
        plans_dir, source = resolve_plans_dir(
            self.root, self.home, None, str(self.root / "env")
        )
        self.assertEqual(plans_dir, self.root / "env")
        self.assertEqual(source, "env")

    def test_project_settings_is_relative_to_project_root(self):
        path = self._write(self.root, "settings.json", {"plansDirectory": "docs/plans"})
        plans_dir, source = resolve_plans_dir(self.root, self.home, None, None)
        self.assertEqual(plans_dir, self.root / "docs" / "plans")
        self.assertEqual(source, f"settings:{path}")

    def test_local_beats_project_and_user(self):
        self._write(self.home, "settings.json", {"plansDirectory": "user-plans"})
        self._write(self.root, "settings.json", {"plansDirectory": "project-plans"})
        path = self._write(
            self.root, "settings.local.json", {"plansDirectory": "local-plans"}
        )
        plans_dir, source = resolve_plans_dir(self.root, self.home, None, None)
        self.assertEqual(plans_dir, self.root / "local-plans")
        self.assertEqual(source, f"settings:{path}")

    def test_project_beats_user(self):
        self._write(self.home, "settings.json", {"plansDirectory": "user-plans"})
        self._write(self.root, "settings.json", {"plansDirectory": "project-plans"})
        plans_dir, _ = resolve_plans_dir(self.root, self.home, None, None)
        self.assertEqual(plans_dir, self.root / "project-plans")

    def test_user_settings_is_used_when_project_defines_nothing(self):
        self._write(self.root, "settings.json", {"model": "x"})
        path = self._write(self.home, "settings.json", {"plansDirectory": "user-plans"})
        plans_dir, source = resolve_plans_dir(self.root, self.home, None, None)
        self.assertEqual(plans_dir, self.root / "user-plans")
        self.assertEqual(source, f"settings:{path}")

    def test_unreadable_settings_is_an_error_not_a_fallback(self):
        self._write(self.root, "settings.json", "{ broken")
        with self.assertRaises(PlansDirError):
            resolve_plans_dir(self.root, self.home, None, None)

    def test_non_string_value_is_an_error(self):
        self._write(self.root, "settings.json", {"plansDirectory": 3})
        with self.assertRaises(PlansDirError):
            resolve_plans_dir(self.root, self.home, None, None)

    def test_empty_value_is_an_error(self):
        self._write(self.root, "settings.json", {"plansDirectory": "  "})
        with self.assertRaises(PlansDirError):
            resolve_plans_dir(self.root, self.home, None, None)

    def test_outside_project_root_is_an_error(self):
        self._write(self.root, "settings.json", {"plansDirectory": "../elsewhere"})
        with self.assertRaises(PlansDirError):
            resolve_plans_dir(self.root, self.home, None, None)


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_cli_with_plans_dir_flag(self):
        p = self.dir / "sample.md"
        p.write_text("# Sample plan\n", encoding="utf-8")

        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "list_recent_plans.py"),
                "--plans-dir",
                str(self.dir),
                "--limit",
                "5",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "found")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["plans"][0]["title"], "Sample plan")

    def test_cli_via_env_var(self):
        env = os.environ.copy()
        env["PLANS_DIR"] = str(self.dir)

        proc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "list_recent_plans.py")],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "empty")
        self.assertEqual(payload["plans_dir"], str(self.dir))

    def test_cli_reports_the_source_of_the_plans_dir(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "list_recent_plans.py"),
                "--plans-dir",
                str(self.dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(proc.stdout)["plans_dir_source"], "flag")

    def test_cli_reads_plans_directory_from_project_settings(self):
        project = self.dir / "project"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "settings.json").write_text(
            json.dumps({"plansDirectory": "my-plans"}), encoding="utf-8"
        )
        (project / "my-plans").mkdir()
        (project / "my-plans" / "x.md").write_text("# Configured\n", encoding="utf-8")

        env = os.environ.copy()
        env.pop("PLANS_DIR", None)
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "list_recent_plans.py"),
                "--project-root",
                str(project),
            ],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "found")
        self.assertEqual(payload["plans"][0]["title"], "Configured")
        self.assertTrue(payload["plans_dir_source"].startswith("settings:"))

    def test_cli_exits_1_with_errors_for_invalid_settings(self):
        project = self.dir / "project"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "settings.json").write_text("{ broken", encoding="utf-8")

        env = os.environ.copy()
        env.pop("PLANS_DIR", None)
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "list_recent_plans.py"),
                "--project-root",
                str(project),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(len(json.loads(proc.stdout)["errors"]), 1)

    def test_main_function_returns_zero(self):
        # main() 自体の戻り値と stdout 形式を確認
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--plans-dir", str(self.dir), "--limit", "3"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "empty")


if __name__ == "__main__":
    unittest.main()
