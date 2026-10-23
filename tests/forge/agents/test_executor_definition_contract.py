"""executor.md の契約テスト（Role 制約と、結果の意味が契約と一致すること）。

定義が持つ script の呼び方が `resolve_task_context.py` の実際の引数と一致すること、
禁止事項が否定形で書かれていること、結果の各フィールドの説明が結果の契約
（`executor_result_contract.py`）のフィールド集合と一致すること、配布物の規約
（内部文書の ID・プロジェクト文書のパスを書かない）を守っていることを確かめる。
Claude Code の実 Agent 起動は unittest の検証対象にしない。
"""

import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
SCRIPT_DIR = PLUGIN_ROOT / "skills" / "start-implement" / "scripts"
EXECUTOR_PATH = PLUGIN_ROOT / "agents" / "executor.md"

sys.path.insert(0, str(SCRIPT_DIR))
import executor_result_contract  # noqa: E402


class ExecutorDefinitionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = EXECUTOR_PATH.read_text(encoding="utf-8")

    def _documented_commands(self):
        return [
            line
            for line in self.text.splitlines()
            if line.startswith('python3 "${CLAUDE_PLUGIN_ROOT}/')
        ]

    # --- Role 制約 ---

    def test_role_prohibitions_are_written_in_negative_form(self):
        for phrase in (
            "計画書（`{feature}_plan.json`）を変更しない",
            "設計書・要件定義書を変更しない",
            "他の Agent を起動しない",
            "Skill を実行しない",
            "利用者に質問しない",
            "範囲外に手を付けない",
            "次のタスクに進まない",
        ):
            self.assertIn(phrase, self.text)

    def test_prompt_is_not_treated_as_parent_instruction(self):
        self.assertIn("起動時の prompt は実装指示ではなく", self.text)
        self.assertIn("引き継いではなりません", self.text)

    def test_does_not_impose_an_edit_allowlist(self):
        self.assertIn("編集してよいファイルの一覧は、あらかじめ与えられない", self.text)

    def test_design_or_requirement_error_returns_failure_with_proposal(self):
        self.assertIn("誤りの内容と修正案", self.text)

    def test_retry_is_limited_to_one(self):
        self.assertIn("再検証は 1 回まで", self.text)

    def test_follows_spec_authority_regardless_of_contradiction(self):
        self.assertIn("`spec_authority`", self.text)
        self.assertIn("矛盾の有無に関わらず", self.text)

    # --- script の呼び方 ---

    def test_documented_script_is_exactly_resolve_task_context(self):
        commands = self._documented_commands()
        self.assertEqual(len(commands), 1)
        self.assertIn(
            "${CLAUDE_PLUGIN_ROOT}/skills/start-implement/scripts/resolve_task_context.py",
            commands[0],
        )

    def test_documented_script_call_matches_the_actual_arguments(self):
        """定義に書かれた呼び方を実際に実行して、引数が実際の script と一致することを確かめる。"""
        line = self._documented_commands()[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            context_id = "TASK-001-0123abcd"
            context_dir = (
                root / "docs" / "tasks"
            )  # 計画書 docs/x_plan.json と同じディレクトリ
            context_dir.mkdir(parents=True)
            (context_dir / f"{context_id}.json").write_text("{}", encoding="utf-8")
            line = line.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT))
            line = line.replace("${CLAUDE_PROJECT_DIR}", str(root))
            line = line.replace("{plan_path}", "docs/x_plan.json").replace(
                "{context_id}", context_id
            )
            argv = shlex.split(line)
            self.assertEqual(argv[0], "python3")
            completed = subprocess.run(
                [sys.executable, *argv[1:]], capture_output=True, text=True
            )
            self.assertEqual(
                completed.returncode, 0, completed.stdout + completed.stderr
            )
            self.assertEqual(
                json.loads(completed.stdout),
                {"path": str(context_dir / f"{context_id}.json")},
            )

    # --- 結果の意味が契約と一致する ---

    def test_result_field_descriptions_match_the_contract(self):
        """出力の表が挙げるフィールドが、結果の契約のフィールド集合と一致する。"""
        section = self.text.split("## Output [MANDATORY]")[1].split("\n---", 1)[0]
        top = set()
        verification = set()
        for match in re.finditer(r"(?m)^\| `([a-z_.]+)`", section):
            name = match.group(1)
            if name.startswith("verification."):
                verification.add(name.split(".", 1)[1])
            else:
                top.add(name)
        self.assertEqual(top, set(executor_result_contract.TASK_RESULT_FIELDS))
        self.assertEqual(
            verification, set(executor_result_contract.VERIFICATION_RESULT_FIELDS)
        )

    def test_describes_enumerations_of_the_contract(self):
        for value in (
            *executor_result_contract.STATUSES,
            *executor_result_contract.VERIFICATION_STATES,
        ):
            self.assertIn(f"`{value}`", self.text)

    def test_describes_every_task_context_field_it_relies_on(self):
        for field in (
            "task_id",
            "acceptance_criteria",
            "scope_in",
            "scope_out",
            "required_reading",
            "implementation_instructions",
            "verification",
            "spec_authority",
        ):
            self.assertIn(f"`{field}`", self.text)

    # --- 配布物の規約 ---

    def test_does_not_reference_internal_documents(self):
        self.assertNotRegex(self.text, r"\b(?:REQ|DES|ADR|TASK)-\d")
        self.assertNotIn("docs/specs", self.text)
        self.assertNotIn("docs/rules", self.text)

    def test_frontmatter_is_kept(self):
        head = self.text.split("---")[1]
        self.assertRegex(head, r"(?m)^name: executor$")
        self.assertRegex(head, r"(?m)^tools: \[Read, Write, Edit, Grep, Glob, Bash\]$")
        self.assertRegex(head, r"(?m)^model: inherit$")


if __name__ == "__main__":
    unittest.main()
