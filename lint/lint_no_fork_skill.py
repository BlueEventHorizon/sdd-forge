#!/usr/bin/env python3
"""
lint: fork 型 SKILL を採用していないこと

「fork 型 SKILL 不採用 + カスタム Agent 起動」方針（docs/rules/forge_claude_code_authoring_policy.md
「SKILL 実行モデル」）の継続的な再発防止用静的検証。
フィーチャー完了後は ALL_SKILLS_FORK_FREE=True で全 SKILL.md を対象に検査する。

検証ロジック:
- ALL_SKILLS_FORK_FREE=True のとき plugins/*/skills/*/SKILL.md 全件の frontmatter に
  `context: fork` が **含まれていない** ことを assert する

外部依存 (PyYAML 等) は使用しない。frontmatter は regex で抽出する。

実行:
  python3 -m unittest lint.lint_no_fork_skill -v
"""

import re
import unittest
from pathlib import Path

from lint import REPO_ROOT


# ALL_SKILLS_FORK_FREE: True のとき plugins/*/skills/*/SKILL.md を全件対象に検査する。
# True のとき、新規に context: fork を持つ SKILL.md を追加すると本検査が fail する
# (docs/rules/forge_claude_code_authoring_policy.md の fork 不採用方針の継続的な再発防止)。
ALL_SKILLS_FORK_FREE: bool = True

# frontmatter 内の `context: fork` を検出する正規表現。
# 行頭から始まり、値が `fork` (前後の空白許容) であることを要求する。
_CONTEXT_FORK_RE = re.compile(r"(?m)^context:\s*fork\s*$")


def _extract_frontmatter(skill_path: Path) -> str:
    """SKILL.md の YAML frontmatter 部分の文字列を返す。frontmatter が無い場合は空文字列。"""
    text = skill_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        raise AssertionError(f"{skill_path} の frontmatter が閉じていない")
    return text[3:end]


def _has_context_fork(skill_path: Path) -> bool:
    """SKILL.md の frontmatter に `context: fork` が含まれているか。"""
    fm = _extract_frontmatter(skill_path)
    return bool(_CONTEXT_FORK_RE.search(fm))


def _iter_all_skills() -> list[Path]:
    """plugins/*/skills/*/SKILL.md を全件返す。"""
    return sorted((REPO_ROOT / "plugins").glob("*/skills/*/SKILL.md"))


class TestAllSkillsForkFree(unittest.TestCase):
    """ALL_SKILLS_FORK_FREE=True で全 SKILL.md に `context: fork` が無いこと。"""

    def test_no_context_fork_anywhere(self):
        if not ALL_SKILLS_FORK_FREE:
            self.skipTest(
                "ALL_SKILLS_FORK_FREE=False。全件検査を行うには True に切り替える"
            )
        skills = _iter_all_skills()
        self.assertGreater(
            len(skills),
            0,
            "plugins/*/skills/*/SKILL.md が 1 件も見つからない",
        )
        for skill_path in skills:
            with self.subTest(skill=str(skill_path.relative_to(REPO_ROOT))):
                self.assertFalse(
                    _has_context_fork(skill_path),
                    f"{skill_path.relative_to(REPO_ROOT)} の frontmatter に "
                    f"`context: fork` が残っている。docs/rules/forge_claude_code_authoring_policy.md "
                    f"「SKILL 実行モデル」の "
                    f"fork 不採用方針に違反するため、カスタム Agent (plugins/forge/agents/<name>.md) "
                    f"に置き換えるか、継承型 SKILL に戻すこと",
                )


if __name__ == "__main__":
    unittest.main()
