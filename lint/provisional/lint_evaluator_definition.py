"""lint（暫定）: evaluator.md の文面。

他の主体のラッパーが現れないこと、評価に要る項目・5 つのメタ観点・disposition の 5 値・
reason の書き方を持つこと、frontmatter が保たれていることを、文字列の有無で確かめる。

定義に書かれた script の呼び方を実際に実行する検査は、
`tests/forge/agent-review/test_evaluator_definition_contract.py`（契約テスト）にある。

実行:
  python3 -m unittest lint.provisional.lint_evaluator_definition -v
"""

import unittest

from lint import REPO_ROOT

PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
EVALUATOR_PATH = PLUGIN_ROOT / "agents" / "evaluator.md"


class EvaluatorDefinitionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = EVALUATOR_PATH.read_text(encoding="utf-8")

    def test_does_not_mention_other_actors_wrappers(self):
        """他の主体のラッパー（reviewer_* と body_*）が現れない。"""
        self.assertNotRegex(self.text, r"reviewer_|body_")

    # --- 読む文書 ---

    def test_is_told_to_read_review_target_types(self):
        path = "${CLAUDE_PLUGIN_ROOT}/docs/criteria/review_target_types.md"
        self.assertTrue(
            any(path in line and "Read" in line for line in self.text.splitlines()),
            "review_target_types.md を Read する指示が無い",
        )

    # --- REQ-026 FNC-208 の項目 ---

    def test_has_every_item_of_fnc_208(self):
        for heading in (
            "## script の呼び方",
            "## 入力の各項目の扱い",
            "## 所見を起点に読む",
            "## target 種別ごとに読む文書",
            "## メタ観点",
            "## 評価として何を述べるか",
        ):
            self.assertIn(heading, self.text)
        self.assertRegex(self.text, r"`disposition` を判定する")
        self.assertIn("severity と確信度", self.text)

    def test_has_the_five_meta_perspectives(self):
        for phrase in (
            "本質を疑う",
            "対象の情報を疑う",
            "既存の決定の当否を外から判定しない",
            "まず最も強い解釈を試す",
            "逆から検証する",
        ):
            self.assertIn(phrase, self.text)
        self.assertIn("作り出さない", self.text)

    def test_has_the_five_dispositions(self):
        for value in (
            "invalid",
            "misunderstanding",
            "out_of_scope",
            "flawed_premise",
            "valid",
        ):
            self.assertIn(f"`{value}`", self.text)

    def test_unreadable_location_and_unknown_location_are_distinguished(self):
        # 指す箇所が読めない所見だけを退ける材料にし、位置未確定の所見はそれを理由に退けない
        self.assertIn("`ファイルパス:行` で指された箇所が読めないとき", self.text)
        self.assertIn(
            "`位置未確定` の所見は、指す箇所が元から無いだけで、箇所が読めないのではない",
            self.text,
        )

    def test_explains_every_key_of_targets_and_that_diff_is_not_an_empty_diff(self):
        for key in ("`paths`", "`base_branch`", "`diff`"):
            self.assertIn(key, self.text)
        self.assertIn("差分が空であることを意味しない", self.text)

    def test_has_how_to_write_reason_for_each_scene(self):
        for scene in (
            "所見のとおり成立する",
            "所見を書き直す",
            "複数の所見を束ねる",
            "1 つの所見を複数の評価に分ける",
            "退ける",
        ):
            self.assertIn(scene, self.text)
        self.assertIn("確定させた問題を先に書き", self.text)

    def test_has_confidence_new_finding_and_finishing(self):
        for phrase in (
            "`confirmed`",
            "`inferred`",
            "`unverified`",
            "`fix_confident`",
            "`--new`",
            "`--location`",
            "すべての判断を確定させてから書き出す",
            "引かれていない",
            "書けない異常終了",
        ):
            self.assertIn(phrase, self.text)

    def test_carries_the_items_the_templates_used_to_carry(self):
        """戦略書「移し替え」のうち evaluator 側へ寄る項目。"""
        for phrase in (
            "重大度カタログの特定手順",  # severity の特定手順
            "失効した棄却理由",  # ADR の棄却理由の確認
            "ADR-NNN §N",
            "比例性チェックの適用条件",
            "`advisor` ツールを呼ばない",
            "最終形である",  # scope の読み方
            "`focus`",
        ):
            self.assertIn(phrase, self.text)

    def test_frontmatter_is_kept(self):
        head = self.text.split("---")[1]
        self.assertRegex(head, r"(?m)^tools: \[Read, Grep, Glob, Bash\]$")
        self.assertRegex(head, r"(?m)^model: inherit$")
        self.assertRegex(head, r"(?m)^permissionMode: plan$")


if __name__ == "__main__":
    unittest.main()
