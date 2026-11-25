"""lint（暫定）: executor.md の Role 制約と配布物の規約の文面。

禁止事項が否定形で書かれていること、定義が持つ script の呼び出しが 1 つであること、
依拠するタスクコンテキストのフィールドを説明していること、配布物の規約（内部文書の ID・
プロジェクト文書のパスを書かない）を守っていることを、文字列の有無で確かめる。

定義に書かれた呼び方を実際に実行する検査と、結果の契約との一致は、
`tests/forge/agents/test_executor_definition_contract.py`（契約テスト）にある。

実行:
  python3 -m unittest lint.provisional.lint_executor_definition -v
"""

import unittest

from lint import REPO_ROOT

PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
EXECUTOR_PATH = PLUGIN_ROOT / "agents" / "executor.md"


class ExecutorDefinitionTest(unittest.TestCase):
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

    # --- タスクコンテキストのフィールド ---

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
