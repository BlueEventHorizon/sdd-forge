#!/usr/bin/env python3
"""文書検索 backend を参照するのが wrapper だけであることの静的検査。

backend の名前が wrapper 以外の SKILL・agent の文面にあると、それを読んだ AI が wrapper
（`query-db-*` / `update-db-*`）を通らずに backend を直接呼ぶ。エラーにならず、検索の経路が
静かに 2 つになるため、名前の不在で構造的に検査する。規約の本文は
`docs/rules/forge_doc_access_principle.md`「文書検索 backend を参照してよいのは wrapper だけ」が持つ。

検査するのは「AI の文脈へ入る文面」である。

- wrapper 以外のスキルのディレクトリにある Markdown（SKILL.md と、SKILL が読む手順文書・転記ブロック）
- `agents/*.md`

backend の名前は `resolve_backend_order.py` の `DEFAULT_ORDER` から得る。backend を入れ替えても、
本ファイルに名前を書き足す必要が無い。

実行:
    python3 -m unittest tests.forge.doc_backend.test_backend_reference_boundary -v
"""

import importlib.util
import unittest

from tests import REPO_ROOT

PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
AGENTS_ROOT = PLUGIN_ROOT / "agents"

#: backend を参照してよいスキル。
WRAPPER_SKILLS = frozenset(
    ("query-db-rules", "query-db-specs", "update-db-rules", "update-db-specs")
)

_spec = importlib.util.spec_from_file_location(
    "resolve_backend_order",
    PLUGIN_ROOT / "scripts" / "doc_backend" / "resolve_backend_order.py",
)
_resolve_backend_order = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_resolve_backend_order)

BACKEND_NAMES = tuple(_resolve_backend_order.DEFAULT_ORDER)


def _targets():
    """検査対象の Markdown を列挙する。"""
    for skill_dir in sorted(p for p in SKILLS_ROOT.iterdir() if p.is_dir()):
        if skill_dir.name in WRAPPER_SKILLS:
            continue
        yield from sorted(skill_dir.rglob("*.md"))
    yield from sorted(AGENTS_ROOT.glob("*.md"))


class TestBackendIsReferencedOnlyByWrappers(unittest.TestCase):
    def test_wrapper_skills_exist(self):
        """wrapper の名前が実在すること（改名で除外が空振りし、検査が素通りするのを防ぐ）。"""
        for skill in WRAPPER_SKILLS:
            self.assertTrue(
                (SKILLS_ROOT / skill / "SKILL.md").is_file(),
                f"wrapper が見つからない: {skill}",
            )

    def test_targets_are_found(self):
        """検査対象が 0 件でないこと（配置が変わって検査が素通りするのを防ぐ）。"""
        self.assertTrue(BACKEND_NAMES, "backend の名前を取得できない")
        self.assertTrue(list(_targets()), "検査対象の Markdown が見つからない")

    def test_non_wrapper_markdown_does_not_name_a_backend(self):
        found = []
        for path in _targets():
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for name in BACKEND_NAMES:
                    if name in line:
                        found.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {name}")
        self.assertEqual(
            found,
            [],
            "wrapper 以外の SKILL・agent が backend を名指ししている。"
            "backend を参照してよいのは wrapper だけである:\n" + "\n".join(found),
        )


if __name__ == "__main__":
    unittest.main()
