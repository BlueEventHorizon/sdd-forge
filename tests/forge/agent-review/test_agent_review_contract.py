"""agent-review と reviewer 定義の契約テスト（DES-084 §7 の契約テスト対象）。

候補名と SKILL 名の対応が解決 script の定数と一致すること、reviewer.md に書かれた script の
呼び方が実際の引数と一致することを確かめる。定義の呼び方を一時ディレクトリで実際に実行する。
Claude Code の実 Agent 起動や read-only enforcement 自体は unittest の検証対象にしない。

文面だけを見る検査は `lint/provisional/lint_agent_review.py` にある。
"""

import importlib.util
import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import REPO_ROOT

SKILL_PATH = REPO_ROOT / "plugins" / "forge" / "skills" / "agent-review" / "SKILL.md"
AGENT_PATH = REPO_ROOT / "plugins" / "forge" / "agents" / "reviewer.md"
PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
RESOLVER_PATH = (
    PLUGIN_ROOT / "skills" / "review" / "scripts" / "resolve_review_backend.py"
)


class AgentReviewContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_PATH.read_text(encoding="utf-8")

    def test_backend_name_corresponds_to_the_resolver_candidates(self):
        """候補名と SKILL 名（`forge:<name>`）が 1 対 1 に対応する。

        本体は backend 名を同名の SKILL へ解決する。対応が崩れると、候補が常に不在として
        扱われる。
        """
        spec = importlib.util.spec_from_file_location(
            "forge_resolve_review_backend", RESOLVER_PATH
        )
        resolver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(resolver)
        self.assertIn(resolver.DEFAULT_ORDER[0], resolver.RETAINS_CONTEXT)
        for name in resolver.DEFAULT_ORDER:
            skill = PLUGIN_ROOT / "skills" / name / "SKILL.md"
            self.assertTrue(skill.is_file(), f"候補 {name} に対応する SKILL が無い")
            self.assertRegex(
                skill.read_text(encoding="utf-8"), rf"(?m)^name: {re.escape(name)}$"
            )
        self.assertEqual(resolver.RETAINS_CONTEXT["agent-review"], False)
        self.assertIn(
            '{"available": true, "missing": [], "retains_context": false}', self.skill
        )


class ReviewerDefinitionContractTest(unittest.TestCase):
    """reviewer.md の契約（DES-084 §7 の契約テスト対象）。"""

    @classmethod
    def setUpClass(cls):
        cls.agent = AGENT_PATH.read_text(encoding="utf-8")

    def _documented_commands(self):
        """reviewer.md のコードブロックにある ``python3`` の行を、スクリプト名 → 行 の対応で返す。"""
        commands = {}
        for line in self.agent.splitlines():
            if not line.startswith('python3 "${CLAUDE_PLUGIN_ROOT}/'):
                continue
            name = re.search(r"/([A-Za-z0-9_]+)\.py\"", line).group(1)
            self.assertNotIn(name, commands, f"{name} の呼び方が複数ある")
            commands[name] = line
        return commands

    def _materialize(self, line, project_root, review_id):
        """定義に書かれた呼び方のプレースホルダを実値に置き換え、引数の列にする。"""
        line = line.replace("<<'FINDING'", "")
        line = line.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT))
        line = line.replace("${CLAUDE_PROJECT_DIR}", str(project_root))
        line = line.replace("{review_id}", review_id).replace("{round_number}", "1")
        line = line.replace("{location}", "位置未確定")
        line = line.replace("{path}", "docs/specs/review/plan/tasks/TASK-005.json")
        argv = shlex.split(line)
        self.assertEqual(argv[0], "python3")
        return [sys.executable, *argv[1:]]

    def _publish(self, root):
        target = root / "a.md"
        target.write_text("# a\n", encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(PLUGIN_ROOT / "scripts" / "review" / "publish_request.py"),
                str(root),
                "--paths",
                str(target),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout)["review_id"]

    def test_documented_script_calls_are_exactly_the_reviewer_scripts(self):
        self.assertEqual(
            set(self._documented_commands()),
            {
                "reviewer_resolve_request",
                "reviewer_add_finding",
                "reviewer_finish",
                "reviewer_abort",
                "resolve_doc_structure",
            },
        )

    def test_documented_script_calls_match_the_actual_arguments(self):
        """定義に書かれた呼び方を実際に実行して、引数が実際の script と一致することを確かめる。"""
        commands = self._documented_commands()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            finishing = self._publish(root)
            aborting = self._publish(root)

            def run(name, review_id, stdin=""):
                argv = self._materialize(commands[name], root, review_id)
                completed = subprocess.run(
                    argv, input=stdin, capture_output=True, text=True
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"{name}: {completed.stdout}{completed.stderr}",
                )
                return json.loads(completed.stdout)

            self.assertTrue(
                Path(run("reviewer_resolve_request", finishing)["path"]).is_file()
            )
            self.assertEqual(
                run("reviewer_add_finding", finishing, "本文\n"), {"finding_id": 1}
            )
            self.assertEqual(run("reviewer_finish", finishing), {})
            self.assertEqual(run("reviewer_abort", aborting), {})

        # resolve_doc_structure.py は、本リポジトリの設定を引く（プロジェクトルートは実在する場所）
        argv = self._materialize(commands["resolve_doc_structure"], REPO_ROOT, "unused")
        completed = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("doc_type", payload)


if __name__ == "__main__":
    unittest.main()
