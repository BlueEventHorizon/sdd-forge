"""consult/SKILL.md の契約テスト（暫定措置 DES-083 §4.3、consult brief の記録 DES-078）。

実装期間中の consult は、記録・表示機構（agenda）へ記録せず、提示に必要な状態を会話コンテキストに持つ。
agenda を呼ぶ記述が戻ると、書き換えの途上にある agenda に依存して提示が成立しなくなる。
あわせて、SKILL と手順文書・記録 script の構造（案内先の実在、許可するツール）を検査する。
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
SKILL_PATH = PLUGIN_ROOT / "skills" / "consult" / "SKILL.md"
REVIEW_SKILL_PATH = PLUGIN_ROOT / "skills" / "review" / "SKILL.md"
HANDLING_PATH = PLUGIN_ROOT / "skills" / "consult" / "docs" / "review_handling.md"
DIALOGUE_REVISION_HANDLING_PATH = (
    PLUGIN_ROOT / "skills" / "consult" / "docs" / "dialogue_revision_handling.md"
)
CREATION_HANDLING_PATH = (
    PLUGIN_ROOT / "skills" / "consult" / "docs" / "creation_handling.md"
)
RECORD_SCRIPT_PATH = (
    PLUGIN_ROOT / "skills" / "consult" / "scripts" / "record_review_brief.py"
)


def allowed_tools(text):
    frontmatter = re.match(r"---\n(.*?)\n---", text, re.DOTALL).group(1)
    tools = re.search(r"^allowed-tools:\s*(.+)$", frontmatter, re.MULTILINE).group(1)
    return {t.strip() for t in tools.split(",")}


class ConsultInterimContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_PATH.read_text(encoding="utf-8")
        cls.review = REVIEW_SKILL_PATH.read_text(encoding="utf-8")

    def test_does_not_call_agenda(self):
        for forbidden in (
            "agenda_wrapper",
            "scripts/agenda",
            "--origin",
            "agenda.json",
            "agenda.html",
        ):
            self.assertNotIn(forbidden, self.text)
        # コマンドの呼び出し（コードブロック）を 1 つも持たない
        self.assertNotIn("```", self.text)
        self.assertNotIn("python3", self.text)

    def test_keeps_state_in_the_conversation(self):
        """review から委譲されたときの提示状態は会話にだけ持つ（置き場は用途の手順文書が定める）。"""
        handling = HANDLING_PATH.read_text(encoding="utf-8")
        self.assertIn("置き場は用途ごとに 1 つ", self.text)
        self.assertIn("会話コンテキストにだけ持つ", handling)
        self.assertIn("永続化されない", handling)

    def test_cannot_invoke_itself(self):
        """Skill ツールを許可しない。自己呼び出しは、多くの議論の起点に置かれる本スキルで暴走ループになりうる。"""
        frontmatter = re.match(r"---\n(.*?)\n---", self.text, re.DOTALL).group(1)
        tools = re.search(r"^allowed-tools:\s*(.+)$", frontmatter, re.MULTILINE).group(
            1
        )
        self.assertNotIn("Skill", {t.strip() for t in tools.split(",")})

    def test_can_write_the_handoff_files(self):
        """受け渡し本文を Write ツールで書くため、Write を許可する。"""
        self.assertIn("Write", allowed_tools(self.text))
        self.assertNotIn("Skill", allowed_tools(self.text))

    def test_guided_files_exist(self):
        """SKILL が案内する手順文書と記録 script が実在する。"""
        self.assertTrue(HANDLING_PATH.is_file())
        self.assertTrue(RECORD_SCRIPT_PATH.is_file())
        self.assertIn("${CLAUDE_SKILL_DIR}/docs/review_handling.md", self.text)
        self.assertIn("${CLAUDE_SKILL_DIR}/scripts/record_review_brief.py", self.text)

    def test_guides_the_two_handoff_paths(self):
        for name in ("summary", "recommendation"):
            self.assertIn(
                "${CLAUDE_PROJECT_DIR}/.temp/forge/consult/consult-brief-${CLAUDE_SESSION_ID}-"
                + name
                + ".md",
                self.text,
            )

    def test_has_no_command_invocation(self):
        """SKILL はコマンドの呼び出しを持たない（記録の手順は手順文書が持つ）。"""
        self.assertNotRegex(self.text, r"(?m)^\s*(python3?|bash|sh)\s")
        self.assertIn("python3", HANDLING_PATH.read_text(encoding="utf-8"))

    def test_does_not_resume_an_interrupted_presentation(self):
        self.assertIn(
            "続きから再開する経路は持たない", HANDLING_PATH.read_text(encoding="utf-8")
        )

    def test_guides_the_dialogue_handlings(self):
        """対話による修正と新規作成の手順文書を案内し、それらが実在する。"""
        self.assertIn(
            "${CLAUDE_SKILL_DIR}/docs/dialogue_revision_handling.md", self.text
        )
        self.assertIn("${CLAUDE_SKILL_DIR}/docs/creation_handling.md", self.text)
        self.assertTrue(DIALOGUE_REVISION_HANDLING_PATH.is_file())
        self.assertTrue(CREATION_HANDLING_PATH.is_file())

    def test_review_body_does_not_assume_a_consult_record(self):
        """review 本体の手順が、consult の記録（永続化された提示）を前提にしていない。"""
        self.assertNotIn("consult の記録", self.review)
        self.assertNotIn("記録から生成された", self.review)
        self.assertNotIn("固定の主題名", self.review)
        self.assertNotRegex(self.review, r"アジェンダの構造|記録の保存と表示")
        self.assertRegex(self.review, r"提示の状態は永続化されない")


if __name__ == "__main__":
    unittest.main()
