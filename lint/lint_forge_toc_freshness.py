#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""forge 同梱 ToC の鮮度契約テスト。

`plugins/forge/toc/rules/rules_toc.yaml` は、内蔵文書（`plugins/forge/docs/`,
`plugins/forge/skills/*/docs/`）の索引から `update-forge-toc` skill
（`.claude/skills/update-forge-toc/`）が生成する配布物である。以下を検証し、索引を更新したのに
同梱ファイルを生成し直していないこと、内蔵文書の追加・削除が索引に入っていないことを、
CI / ローカルテストで検出する:

1. `.bak` ファイルが残存していないこと
2. 索引の文書の集合が、現在の内蔵文書の集合と一致すること（過不足）。一致しなければ
   生成 script がエラーを返す。索引の内容が現物の文書より古いかは、ここでは確かめない
   （文書検索の側の検査が担う）
3. 同梱の `rules_toc.yaml` が、索引からの生成結果と同一であること（生成漏れを検出する）
4. 同梱の `rules_toc.yaml` の索引パス集合が、内蔵文書のパス集合と完全一致し、すべて実在すること

実行:
    python3 -m unittest lint.lint_forge_toc_freshness -v
"""

import importlib.util
import re
import unittest

from lint import REPO_ROOT

BUILD_SCRIPT = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "update-forge-toc"
    / "scripts"
    / "build_forge_toc.py"
)
TOC_DIR = REPO_ROOT / "plugins" / "forge" / "toc"
RULES_TOC_PATH = TOC_DIR / "rules" / "rules_toc.yaml"

DOC_KEY_PATTERN = re.compile(r"^  (\S.*\.md):$", re.MULTILINE)

REBUILD_HINT = (
    "update-forge-toc skill を実行して、索引と同梱ファイルを再生成してください。"
)


def load_build_module():
    spec = importlib.util.spec_from_file_location("build_forge_toc", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestForgeTocFreshness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = load_build_module()

    def test_no_bak_files_in_forge_toc(self):
        bak_files = sorted(
            str(p.relative_to(REPO_ROOT)) for p in TOC_DIR.rglob("*.bak")
        )
        self.assertEqual(
            bak_files,
            [],
            f"forge 同梱 ToC ディレクトリに .bak ファイルが残存しています: {bak_files}\n"
            "git 履歴から復元可能なため削除してください。",
        )

    def test_index_matches_current_docs(self):
        try:
            self.build.load_entries()
        except self.build.BuildError as exc:
            self.fail(f"{exc}\n{REBUILD_HINT}")

    def test_shipped_toc_is_identical_to_generated(self):
        try:
            generated = self.build.render(self.build.load_entries())
        except self.build.BuildError as exc:
            self.fail(f"{exc}\n{REBUILD_HINT}")
        self.assertEqual(
            RULES_TOC_PATH.read_text(encoding="utf-8"),
            generated,
            "plugins/forge/toc/rules/rules_toc.yaml が索引からの生成結果と一致しません。\n"
            + REBUILD_HINT,
        )

    def test_rules_toc_indexed_paths_match_source_paths_exactly(self):
        sources = set(self.build.source_paths())
        indexed = set(
            DOC_KEY_PATTERN.findall(RULES_TOC_PATH.read_text(encoding="utf-8"))
        )
        self.assertGreater(
            len(indexed), 0, "rules_toc.yaml から索引パスを抽出できませんでした"
        )

        missing = sorted(sources - indexed)
        surplus = sorted(indexed - sources)
        self.assertEqual(
            (missing, surplus),
            ([], []),
            f"rules_toc.yaml の索引パス集合が内蔵文書のパス集合と一致しません。\n"
            f"不足（索引に無い文書）: {missing}\n"
            f"余剰（実在しない、または対象外の索引エントリ）: {surplus}\n"
            + REBUILD_HINT,
        )


if __name__ == "__main__":
    unittest.main()
