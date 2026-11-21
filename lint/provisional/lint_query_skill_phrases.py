#!/usr/bin/env python3
"""lint（暫定）: 検索系 SKILL・worker Agent の制約の文言。

`lint/provisional/` の検査は、文字列の有無を見るだけで、制約の意味を検査しない。
文意の検査（Issue #14）へ置き換えた時点で削除する。

対象の本文に、次の文字列があることを検査する:

- read-only 制約（書き込み系ツールの名前、`git commit`、git 管理ファイルの書き換え禁止）
- 引数解釈ガード（`引数解釈` の見出しと、実装指示として解釈しない旨）
- 出力契約（`Required documents:`）

対象:
- plugins/forge/skills/query-forge-rules/SKILL.md
- plugins/forge/agents/rules-query-worker.md

実行:
  python3 -m unittest lint.provisional.lint_query_skill_phrases -v
"""

import unittest

from lint import REPO_ROOT
from lint.lint_query_skill_wiring import split_frontmatter_body

CONSTRAINT_TARGET_SKILLS = [
    REPO_ROOT / "plugins" / "forge" / "skills" / "query-forge-rules" / "SKILL.md",
    REPO_ROOT / "plugins" / "forge" / "agents" / "rules-query-worker.md",
]


class TestQuerySkillRoleReadonlyConstraint(unittest.TestCase):
    """Role 章に read-only 制約が明記されていることを検証 (多重防御 B 層)"""

    REQUIRED_PHRASES = [
        # read-only であることの明記
        "read-only",
        # 禁止される書き込み系ツール (列挙)
        "Edit",
        "Write",
        "MultiEdit",
        "NotebookEdit",
        # git 副作用を伴うコマンド禁止
        "git commit",
        # git 管理ファイル書き換え禁止
        "git 管理ファイル",
        # MANDATORY タグ (制約セクションの強制力を担保)
        "[MANDATORY]",
    ]

    def test_role_section_has_constraints(self):
        for skill_path in CONSTRAINT_TARGET_SKILLS:
            with self.subTest(skill=str(skill_path.relative_to(REPO_ROOT))):
                _, body = split_frontmatter_body(skill_path)
                for phrase in self.REQUIRED_PHRASES:
                    self.assertIn(
                        phrase,
                        body,
                        f"{skill_path.relative_to(REPO_ROOT)} に制約文言 "
                        f"'{phrase}' がない (多重防御 B 層違反)",
                    )


class TestQuerySkillArgumentGuard(unittest.TestCase):
    """引数解釈ガードが含まれていることを検証 (多重防御 C 層)"""

    def test_argument_interpretation_section(self):
        for skill_path in CONSTRAINT_TARGET_SKILLS:
            with self.subTest(skill=str(skill_path.relative_to(REPO_ROOT))):
                _, body = split_frontmatter_body(skill_path)
                # `### 引数解釈` または `## 引数解釈` 見出しが存在する
                self.assertRegex(
                    body,
                    r"(?m)^#{2,3}\s*引数解釈",
                    f"{skill_path.relative_to(REPO_ROOT)} に "
                    f"`引数解釈` セクションがない (引数解釈ガードの欠落)",
                )
                # 命令文を実装指示として解釈しない旨の明記
                self.assertIn(
                    "実装指示として解釈してはならない",
                    body,
                    f"{skill_path.relative_to(REPO_ROOT)} の引数解釈に "
                    f"命令文の解釈ガードがない (引数解釈ガードの欠落)",
                )


class TestQuerySkillReturnContract(unittest.TestCase):
    """最終 return が `Required documents:` 形式に限定されていることを検証"""

    def test_return_contract_documented(self):
        for skill_path in CONSTRAINT_TARGET_SKILLS:
            with self.subTest(skill=str(skill_path.relative_to(REPO_ROOT))):
                _, body = split_frontmatter_body(skill_path)
                self.assertIn(
                    "Required documents:",
                    body,
                    f"{skill_path.relative_to(REPO_ROOT)} に "
                    f"`Required documents:` 出力契約の記載がない",
                )


if __name__ == "__main__":
    unittest.main()
