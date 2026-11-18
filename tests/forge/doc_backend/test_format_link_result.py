#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""format_link_result.py のユニットテスト。

検証項目:

- 実在するパスを、渡された順のまま `Required documents:` 形式にする
- 実在しないパスを除き、件数を `excluded_count` と `notices` で返す
- 絶対パスと、プロジェクトルートの外へ出るパスを除く
- 0 件（全件除外を含む）では空の `Required documents:` を返す
- CLI 契約（終了コード 0・JSON のみの出力）

実行:
  python3 -m unittest tests.forge.doc_backend.test_format_link_result -v
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tests import REPO_ROOT

_SCRIPT_PATH = (
    REPO_ROOT
    / "plugins"
    / "forge"
    / "scripts"
    / "doc_backend"
    / "format_link_result.py"
)

_spec = importlib.util.spec_from_file_location(
    "doc_backend_format_link_result", _SCRIPT_PATH
)
format_link_result = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(format_link_result)


class _Base(unittest.TestCase):
    """tempdir の project root と文書の配置を持つ基盤。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name).resolve()

    def tearDown(self):
        self._tmpdir.cleanup()

    def put(self, relative_path):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# doc\n", encoding="utf-8")


class RunTest(_Base):
    def test_existing_paths_keep_given_order(self):
        self.put("docs/rules/b.md")
        self.put("docs/rules/a.md")
        payload = format_link_result.run(
            ["docs/rules/b.md", "docs/rules/a.md"], self.root
        )
        self.assertEqual(
            payload["result"],
            "Required documents:\n\n- docs/rules/b.md\n- docs/rules/a.md\n",
        )
        self.assertEqual(payload["excluded_count"], 0)
        self.assertEqual(payload["notices"], [])

    def test_missing_path_is_excluded_and_counted(self):
        self.put("docs/rules/a.md")
        payload = format_link_result.run(
            ["docs/rules/a.md", "docs/rules/gone.md"], self.root
        )
        self.assertEqual(
            payload["result"], "Required documents:\n\n- docs/rules/a.md\n"
        )
        self.assertEqual(payload["excluded_count"], 1)
        self.assertEqual(len(payload["notices"]), 1)
        self.assertIn("1", payload["notices"][0])

    def test_absolute_path_is_excluded(self):
        self.put("docs/rules/a.md")
        payload = format_link_result.run(
            [str(self.root / "docs/rules/a.md")], self.root
        )
        self.assertEqual(payload["result"], "Required documents:\n")
        self.assertEqual(payload["excluded_count"], 1)

    def test_path_escaping_root_is_excluded(self):
        outside = self.root.parent / "outside_format_link_result.md"
        outside.write_text("# doc\n", encoding="utf-8")
        self.addCleanup(outside.unlink)
        payload = format_link_result.run([f"../{outside.name}"], self.root)
        self.assertEqual(payload["result"], "Required documents:\n")
        self.assertEqual(payload["excluded_count"], 1)

    def test_no_paths_returns_empty_header(self):
        payload = format_link_result.run([], self.root)
        self.assertEqual(payload["result"], "Required documents:\n")
        self.assertEqual(payload["excluded_count"], 0)
        self.assertEqual(payload["notices"], [])


class CliContractTest(_Base):
    def _run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), *args],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def test_cli_outputs_json_only(self):
        self.put("docs/specs/a.md")
        completed = self._run_cli(
            "--project-root", str(self.root), "docs/specs/a.md", "docs/specs/gone.md"
        )
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            payload["result"], "Required documents:\n\n- docs/specs/a.md\n"
        )
        self.assertEqual(payload["excluded_count"], 1)
        self.assertEqual(completed.stderr, "")

    def test_cli_without_paths_succeeds(self):
        completed = self._run_cli("--project-root", str(self.root))
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(
            json.loads(completed.stdout)["result"], "Required documents:\n"
        )


if __name__ == "__main__":
    unittest.main()
