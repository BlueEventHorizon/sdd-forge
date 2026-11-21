"""lint（暫定）: review 本体（SKILL.md）の文面。

本体の定義が、`disposition` などの値にそのまま従わず内容を吟味してから修正・ドロップ・終端を決める
指示を持つこと、Agent の起動と許可するツール、終端のすべての経路が 1 つの出口を通ることを、
文字列の有無と出現回数で確かめる。

定義に書かれた script の呼び方を実際に実行する検査は、
`tests/forge/review/test_review_skill_contract.py`（契約テスト）にある。

実行:
  python3 -m unittest lint.provisional.lint_review_skill -v
"""

import re
import unittest

from lint import REPO_ROOT

PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
SKILL_PATH = PLUGIN_ROOT / "skills" / "review" / "SKILL.md"


def _between(text, start, end=None):
    """``start`` を含む行から、``end`` を含む行の手前までを返す。"""
    begin = text.index(start)
    if end is None:
        return text[begin:]
    return text[begin : text.index(end, begin)]


class ReviewSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_PATH.read_text(encoding="utf-8")
        cls.step7 = _between(cls.text, "### Step 7: ", "### Step 7.5:")
        cls.step8 = _between(cls.text, "### Step 8: ", "## エラーフロー一覧")

    # --- 吟味（DES-083 §7 の契約テスト） ---

    def test_does_not_follow_values_as_is_but_examines_the_content(self):
        for phrase in (
            "`disposition`・`confidence`・`fix_confident` などの値にそのまま従って、修正・ドロップ・終端を決めない",
            "自分で理解し、調査し、考える",
            "吟味",
            "script は行き先を決めない",
        ):
            self.assertIn(phrase, self.step7)

    def test_flawed_premise_is_always_presented(self):
        self.assertRegex(
            self.step7,
            r"`flawed_premise` は、`confidence` / `fix_confident` の値に関わらず自動修正の対象にしない。常に提示する",
        )

    def test_terminal_judgement_uses_count_as_material_not_as_the_decision(self):
        self.assertIn("材料であって、判断そのものではない", self.step7)
        self.assertIn("本体が単独で打ち切らない", self.step7)

    def test_unfixable_open_findings_are_confirmed_with_the_user_before_ending(self):
        """対応できるものが無い（ドロップ・位置未確定のみ）ときも、本体が単独で終えない（REQ-029 FNC-318）。"""
        start = self.step7.index("**対応できるものが無い**")
        bullet = self.step7[start : self.step7.index("- **残りが軽微**", start)]
        self.assertIn("AskUserQuestion", bullet)
        self.assertIn("本体が単独で打ち切らない", bullet)
        self.assertIn("終えると決まれば Step 8", bullet)

    # --- Agent の起動 ---

    def test_launches_reviewer_and_evaluator_with_the_two_values_only(self):
        self.assertIn("`forge:reviewer`", self.text)
        self.assertIn("`forge:evaluator`", self.text)
        self.assertEqual(
            self.text.count("**prompt に渡すのは `review_id` と `round_number` だけ**"),
            2,
        )

    def test_allowed_tools_keep_agent_and_skill(self):
        head = self.text.split("---", 2)[1]
        tools = re.search(r"(?m)^allowed-tools: (.*)$", head).group(1)
        names = {t.strip() for t in tools.split(",")}
        self.assertLessEqual(
            {"Agent", "Skill", "Read", "Write", "Bash", "AskUserQuestion"}, names
        )

    def test_retains_context_comes_from_the_backend_resolution_script(self):
        step15 = _between(self.text, "### Step 1.5:", "### Step 2:")
        self.assertIn("`retains_context`（候補名から真偽値への対応）", step15)
        self.assertIn("`true` が得られたら、依頼を公開せず", step15)

    # --- 終端 ---

    def test_all_terminal_routes_go_through_one_exit_that_deletes(self):
        for route in (
            "approved",
            "halted_with_open_findings",
            "failure",
            "interrupted",
        ):
            self.assertIn(f"`{route}`", self.step8)
        self.assertIn("レビューを終える経路はすべてこの Step を通す", self.step8)
        self.assertEqual(self.text.count("scripts/review/delete_review.py"), 1)
        self.assertIn("scripts/review/delete_review.py", self.step8)
        self.assertIn("報告を出力してから、保持物を削除する", self.step8)

    def test_next_round_is_only_reached_from_step_7_and_does_not_rebuild_the_request(
        self,
    ):
        self.assertEqual(self.text.count("scripts/review/advance_round.py"), 1)
        self.assertIn("scripts/review/advance_round.py", self.step7)
        self.assertIn("**依頼は変えない**", self.step7)
        self.assertIn("次のラウンド番号が 5 以上になる場合", self.step7)


if __name__ == "__main__":
    unittest.main()
