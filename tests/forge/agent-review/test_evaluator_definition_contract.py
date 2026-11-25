"""evaluator.md の契約テスト（DES-083 §7 の契約テスト対象）。

定義が持つ script の呼び方が、ラッパー（evaluator_*）と resolve_doc_structure.py の実際の引数と
一致することを確かめる。定義の呼び方を一時ディレクトリで実際に実行する。
Claude Code の実 Agent 起動は unittest の検証対象にしない。

文面だけを見る検査は `lint/provisional/lint_evaluator_definition.py` にある。
"""

import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import REPO_ROOT

PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
SCRIPT_DIR = PLUGIN_ROOT / "scripts" / "review"
EVALUATOR_PATH = PLUGIN_ROOT / "agents" / "evaluator.md"


class EvaluatorDefinitionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = EVALUATOR_PATH.read_text(encoding="utf-8")

    def _documented_commands(self):
        """evaluator.md のコードブロックにある ``python3`` の行を、スクリプト名 → 行 の対応で返す。"""
        commands = {}
        for line in self.text.splitlines():
            if not line.startswith('python3 "${CLAUDE_PLUGIN_ROOT}/'):
                continue
            name = re.search(r"/([A-Za-z0-9_]+)\.py\"", line).group(1)
            self.assertNotIn(name, commands, f"{name} の呼び方が複数ある")
            commands[name] = line
        return commands

    def _materialize(self, line, project_root, review_id):
        """定義に書かれた呼び方のプレースホルダを実値に置き換え、引数の列にする。"""
        line = line.replace("<<'REASON'", "")
        line = line.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT))
        line = line.replace("${CLAUDE_PROJECT_DIR}", str(project_root))
        line = line.replace("{review_id}", review_id).replace("{round_number}", "1")
        for placeholder, value in (
            ("{disposition}", "valid"),
            ("{severity}", "major"),
            ("{finding_id}", "1"),
            ("{confidence}", "confirmed"),
            ("{fix_confident}", "true"),
            ("{path}", "docs/specs/review/plan/tasks/TASK-005.json"),
        ):
            line = line.replace(placeholder, value)
        argv = shlex.split(line)
        self.assertEqual(argv[0], "python3")
        return [sys.executable, *argv[1:]]

    def _run_documented(self, commands, name, root, review_id, stdin=""):
        argv = self._materialize(commands[name], root, review_id)
        completed = subprocess.run(argv, input=stdin, capture_output=True, text=True)
        self.assertEqual(
            completed.returncode, 0, f"{name}: {completed.stdout}{completed.stderr}"
        )
        return json.loads(completed.stdout)

    def _publish_with_finding(self, root):
        target = root / "a.md"
        target.write_text("# a\n", encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "publish_request.py"),
                str(root),
                "--paths",
                str(target),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        review_id = json.loads(completed.stdout)["review_id"]
        for script, extra, stdin in (
            ("reviewer_add_finding.py", ["--location", f"{target}:1"], "所見\n"),
            ("reviewer_finish.py", [], ""),
        ):
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / script),
                    str(root),
                    review_id,
                    "1",
                    *extra,
                ],
                input=stdin,
                capture_output=True,
                text=True,
                check=True,
            )
        return review_id

    # --- script の呼び方 ---

    def test_documented_script_calls_are_exactly_the_evaluator_scripts(self):
        self.assertEqual(
            set(self._documented_commands()),
            {
                "evaluator_resolve_inputs",
                "evaluator_add_evaluation",
                "evaluator_finish",
                "resolve_doc_structure",
            },
        )

    def test_documented_script_calls_match_the_actual_arguments(self):
        """定義に書かれた呼び方を実際に実行して、引数が実際の script と一致することを確かめる。"""
        commands = self._documented_commands()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            review_id = self._publish_with_finding(root)
            inputs = self._run_documented(
                commands, "evaluator_resolve_inputs", root, review_id
            )
            self.assertTrue(Path(inputs["request"]).is_file())
            self.assertTrue(Path(inputs["findings"]).is_file())
            self.assertEqual(
                self._run_documented(
                    commands, "evaluator_add_evaluation", root, review_id, "根拠\n"
                ),
                {},
            )
            self.assertEqual(
                self._run_documented(commands, "evaluator_finish", root, review_id), {}
            )

        argv = self._materialize(commands["resolve_doc_structure"], REPO_ROOT, "unused")
        completed = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("doc_type", payload)

    def test_every_documented_option_exists_in_the_wrapper(self):
        """本文が挙げる ``--xxx`` が、ラッパーの実際の引数に存在すること（--new / --location を含む）。"""
        helps = ""
        for name in (
            "evaluator_resolve_inputs",
            "evaluator_add_evaluation",
            "evaluator_finish",
        ):
            helps += subprocess.run(
                [sys.executable, str(SCRIPT_DIR / f"{name}.py"), "--help"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        helps += subprocess.run(
            [
                sys.executable,
                str(
                    PLUGIN_ROOT
                    / "scripts"
                    / "doc_structure"
                    / "resolve_doc_structure.py"
                ),
                "--help",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        wrapper_section = self.text.split("## 入力の各項目の扱い")[0]
        documented = set(re.findall(r"`?(--[a-z][a-z-]*)", wrapper_section))
        self.assertIn("--new", documented)
        self.assertIn("--location", documented)
        for option in documented:
            self.assertIn(option, helps, f"{option} がラッパーに存在しない")

    def test_first_argument_is_the_project_dir_and_doc_structure_gets_project_root(
        self,
    ):
        commands = self._documented_commands()
        for name in (
            "evaluator_resolve_inputs",
            "evaluator_add_evaluation",
            "evaluator_finish",
        ):
            self.assertRegex(commands[name], r'\.py" "\$\{CLAUDE_PROJECT_DIR\}" ', name)
        self.assertIn(
            '--project-root "${CLAUDE_PROJECT_DIR}"', commands["resolve_doc_structure"]
        )


if __name__ == "__main__":
    unittest.main()
