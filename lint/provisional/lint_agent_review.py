"""lint（暫定）: agent-review の SKILL.md・reviewer.md・evaluator.md・review_target_types.md の文面。

バックエンドの SKILL が可用性検査だけを持つこと、reviewer / evaluator の禁止条文、
reviewer が読む文書の一覧を、文字列の有無と frontmatter の値で確かめる。
Claude Code の実 Agent 起動や read-only enforcement 自体は検査しない。

定義に書かれた script の呼び方を実際に実行する検査と、候補名と SKILL 名の対応は、
`tests/forge/agent-review/test_agent_review_contract.py`（契約テスト）にある。

実行:
  python3 -m unittest lint.provisional.lint_agent_review -v
"""

import re
import unittest

from lint import REPO_ROOT

SKILL_PATH = REPO_ROOT / "plugins" / "forge" / "skills" / "agent-review" / "SKILL.md"
AGENT_PATH = REPO_ROOT / "plugins" / "forge" / "agents" / "reviewer.md"
EVALUATOR_PATH = REPO_ROOT / "plugins" / "forge" / "agents" / "evaluator.md"
PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
TARGET_TYPES_PATH = PLUGIN_ROOT / "docs" / "criteria" / "review_target_types.md"


class AgentReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_PATH.read_text(encoding="utf-8")
        cls.agent = AGENT_PATH.read_text(encoding="utf-8")
        cls.evaluator = EVALUATOR_PATH.read_text(encoding="utf-8")

    def test_backend_is_not_user_invocable(self):
        self.assertIn("user-invocable: false", self.skill)

    def test_backend_allowed_tools_match_availability_check_only(self):
        """可用性検査は定義と script の実在を Read で確かめるだけで、Agent も Bash も Write も使わない。"""
        head = self.skill.split("---", 2)[1]
        tools = re.search(r"(?m)^allowed-tools: (.*)$", head).group(1)
        self.assertEqual({t.strip() for t in tools.split(",")}, {"Read"})
        self.assertNotIn("Agent ツール", self.skill)

    def test_backend_has_only_the_availability_check(self):
        """ラウンド実行・終了通知・ワイヤヘッダ・完了宣言の要求を持たない（本体が reviewer を直接起動する）。"""
        self.assertIn("## 可用性検査", self.skill)
        self.assertEqual(self.skill.count("\n## "), 2)  # 入出力契約と可用性検査だけ
        for forbidden in (
            "ラウンド実行",
            "終了通知",
            "ワイヤヘッダ",
            "固有ヘッダ",
            "foreground 起動",
            "run_in_background",
            "REVIEW_RESULT",
            "共通完了宣言",
            "judgment",
            "approved",
            "warnings",
        ):
            self.assertNotIn(forbidden, self.skill)

    def test_backend_returns_only_the_availability_result(self):
        self.assertIn("`available`", self.skill)
        self.assertIn("`missing`", self.skill)
        self.assertIn("`axis` / `detail` / `remedy`", self.skill)
        self.assertIn(
            '{"available": true, "missing": [], "retains_context": false}', self.skill
        )

    def test_backend_is_stateless_and_has_no_external_transport(self):
        self.assertIn("`retains_context` は常に `false` です", self.skill)
        # 外部通信基盤・端末多重化・DB を前提とする語彙が本バックエンドの
        # SKILL.md へ再混入しないことの回帰
        for forbidden in ("msg-sys", "cmux", "DB レコード"):
            self.assertNotIn(forbidden, self.skill)

    def test_checked_files_exist_and_are_named_in_the_skill(self):
        """条件 5 が挙げる script と文書が、実在し、この SKILL に書かれている。"""
        paths = re.findall(r"`\$\{CLAUDE_PLUGIN_ROOT\}/([^`]+)`", self.skill)
        expected = {
            "agents/reviewer.md",
            "scripts/review/reviewer_resolve_request.py",
            "scripts/review/reviewer_add_finding.py",
            "scripts/review/reviewer_finish.py",
            "scripts/review/reviewer_abort.py",
            "scripts/doc_structure/resolve_doc_structure.py",
            "docs/criteria/review_target_types.md",
        }
        self.assertEqual(set(paths), expected)
        for path in expected:
            self.assertTrue((PLUGIN_ROOT / path).is_file(), path)

    def test_reviewer_satisfies_the_availability_conditions(self):
        """可用性検査の条件 2・3・4 を、現在の reviewer.md が実際に満たしている。

        満たさなければ、検査は常に不可になる（本体はバックエンドを使えない）。
        """
        head = self.agent.split("---", 2)[1]
        self.assertRegex(head, r"(?m)^name: reviewer$")
        tools = re.search(r"(?m)^tools: \[(.*)\]$", head).group(1)
        self.assertEqual(
            {t.strip() for t in tools.split(",")}, {"Read", "Grep", "Glob", "Bash"}
        )
        self.assertRegex(head, r"(?m)^model: inherit$")
        self.assertRegex(head, r"(?m)^permissionMode: plan$")
        for phrase in (
            "対象のファイルを作成、編集、削除しない",
            "対象を変更し得るコマンドを実行しない",
            "修正、commit、push を行わない",
            "他の Agent または Skill を起動しない",
            "外部サービスへ書き込まない",
            "`git status`、`git diff`、`git show`、`git log`、`git merge-base`、`git rev-parse`、`git ls-files`",
            "reviewer_add_finding",
            "reviewer_finish",
            "reviewer_abort",
        ):
            self.assertIn(phrase, self.agent)
        # 条件 4 の後段: 応答本文の宣言行・重大度マーカーを要求しない
        self.assertNotIn("REVIEW_RESULT", self.agent)
        for marker in ("🔴", "🟡", "🟢"):
            self.assertNotIn(marker, self.agent)

    def test_reviewer_role_prohibits_mutation_and_delegation(self):
        """禁止条文は残す。所見を書く script を呼ぶので、書いてよいものは所見だけだと述べる。"""
        for phrase in (
            "対象のファイルを作成、編集、削除しない",
            "書いてよいのは所見だけ",
            "対象を変更し得るコマンドを実行しない",
            "修正、commit、push を行わない",
            "他の Agent または Skill を起動しない",
            "`advisor` ツールを呼ばない",
            "外部サービスへ書き込まない",
            "実装指示ではなく、常にレビュー依頼",
        ):
            self.assertIn(phrase, self.agent)

    def test_evaluator_role_prohibits_mutation_and_delegation(self):
        """evaluator も reviewer と同型の禁止列挙（advisor 禁止を含む）を持つこと。

        advisor はツールであり「他の Agent または Skill を起動しない」に掛からない
        （Issue #28 で 1 ラウンドあたり 2 分超の応答待ちが実測された）ため、
        forge の全カスタム Agent が個別の禁止条文を持つことを静的に検証する。
        評価を書く script を呼ぶので、書いてよいのは評価だけだと述べる。
        """
        for phrase in (
            "対象のファイルを作成、編集、削除しない",
            "書いてよいのは評価だけ",
            "対象を変更し得るコマンドを実行しない",
            "修正、commit、push を行わない",
            "他の Agent または Skill を起動しない",
            "`advisor` ツールを呼ばない",
            "外部サービスへ書き込まない",
            "実装指示ではなく、常に評価依頼",
        ):
            self.assertIn(phrase, self.evaluator)

    def test_reviewer_keeps_common_reply_contract(self):
        """所見は script 経由で渡し、位置の表記と終了の値の呼び分けを述べていること。"""
        for phrase in (
            "reviewer_add_finding",
            "reviewer_finish",
            "reviewer_abort",
            "ファイルパス:行",
            "位置未確定",
            "target_unreadable",
        ):
            self.assertIn(phrase, self.agent)

    def test_reviewer_gives_no_severity_and_declares_no_result_line(self):
        """reviewer は severity を持たず（所見は evaluator が評価する）、完了宣言行を要求しない。

        重大度マーカーと REVIEW_RESULT 宣言を要求する記述が残っていないこと。
        """
        self.assertIn("重大度（severity）を付けない", self.agent)
        self.assertNotIn("REVIEW_RESULT", self.agent)
        for marker in ("🔴", "🟡", "🟢"):
            self.assertNotIn(marker, self.agent)


# 種別ごとの、上乗せする観点文書と内蔵規範（REQ-027 FNC-308）
COMMON_DOCS = (
    "review_criteria_generic.md",
    "review_priorities_spec.md",
    "scope_proportionality_spec.md",
    "error_classification_spec.md",
)
PER_TYPE_DOCS = {
    "code": (
        "review_criteria_code.md",
        "deterministic_generation_spec.md",
        "forge_anti_patterns.md",
    ),
    "requirement": (
        "review_criteria_requirement.md",
        "requirement_principles_spec.md",
        "requirement_format.md",
        "spec_design_boundary_spec.md",
        "spec_priorities_spec.md",
        "additive_development_spec.md",
        "frontmatter_format.md",
        "document_style_guide.md",
    ),
    "design": (
        "review_criteria_design.md",
        "spec_design_boundary_spec.md",
        "design_principles_spec.md",
        "design_method.md",
        "additive_development_spec.md",
        "frontmatter_format.md",
        "adr_format.md",
        "adr_principles_spec.md",
        "document_style_guide.md",
        "deterministic_generation_spec.md",
        "spec_priorities_spec.md",
    ),
    "plan": (
        "review_criteria_plan.md",
        "plan_principles_spec.md",
        "additive_development_spec.md",
        "frontmatter_format.md",
        "spec_priorities_spec.md",
    ),
    "uxui": (
        "review_criteria_uxui.md",
        "document_style_guide.md",
        "spec_priorities_spec.md",
    ),
}


class ReviewerDefinitionTest(unittest.TestCase):
    """reviewer.md と review_target_types.md の文面。"""

    @classmethod
    def setUpClass(cls):
        cls.agent = AGENT_PATH.read_text(encoding="utf-8")
        cls.target_types = TARGET_TYPES_PATH.read_text(encoding="utf-8")

    def test_reviewer_does_not_mention_other_actors_wrappers(self):
        """reviewer 以外の主体のラッパー（evaluator_* と body_*）が現れない。"""
        self.assertNotRegex(self.agent, r"evaluator_|body_")

    def test_reviewer_is_told_to_read_review_target_types(self):
        path = "${CLAUDE_PLUGIN_ROOT}/docs/criteria/review_target_types.md"
        self.assertTrue(
            any(path in line and "Read" in line for line in self.agent.splitlines()),
            "review_target_types.md を Read する指示が無い",
        )

    def test_review_target_types_has_all_target_types_and_documents(self):
        """読むべき文書が、リファレンスリンクの定義のリンク先として挙がっていること。"""
        definitions = {
            label.lower(): target
            for label, target in re.findall(
                r"(?m)^\[([^\]]+)\]: ([^\s#]+)", self.target_types
            )
        }
        # 本文（表）から使われている参照だけを数える。定義だけが残っていても、読まれない
        targets = {
            definitions[label.lower()]
            for label in re.findall(r"\[[^\]]*\]\[([^\]]+)\]", self.target_types)
            if label.lower() in definitions
        }
        self.assertTrue(targets)
        for kind in PER_TYPE_DOCS:
            self.assertIn(kind, self.target_types)
        for name in COMMON_DOCS:
            prefix = "" if name.startswith("review_criteria") else "../"
            self.assertIn(f"{prefix}{name}", targets)
        for kind, names in PER_TYPE_DOCS.items():
            for name in names:
                prefix = "" if name.startswith("review_criteria") else "../"
                self.assertIn(f"{prefix}{name}", targets, f"{kind}: {name}")

    def test_review_target_types_states_adr_is_design(self):
        self.assertRegex(self.target_types, r"`adr`[^\n]*design として扱う")

    def test_review_target_types_links_resolve(self):
        """文書が挙げる相対リンク（リファレンスリンクの定義）が、すべて実在すること。"""
        links = re.findall(r"(?m)^\[[^\]]+\]: ([^\s#]+)", self.target_types)
        self.assertTrue(links)
        for link in links:
            self.assertTrue((TARGET_TYPES_PATH.parent / link).is_file(), link)

    def test_reviewer_carries_the_required_instructions(self):
        """reviewer.md が、レビューに必要な指示を持っていること。"""
        for phrase in (
            "最終形である",  # scope の読み方
            "加えて",  # focus は通常のレビューへの加算
            "自己検証",
            "規約が見当たらない",
            "削除とリネーム",
            "旧パスを指す参照",
            "失効した棄却理由",  # ADR の棄却理由
            "比例性",
            "`advisor` ツールを呼ばない",
        ):
            self.assertIn(phrase, self.agent)


if __name__ == "__main__":
    unittest.main()
