#!/usr/bin/env python3
"""索引整備の入口が `update-db-*` に一本化されていることの静的検査。

REQ-014 FNC-002 は query wrapper が索引の整備の手順を持たないことを定め、DES-057 §5.3 は
未整備時の整備を `update-db-*` への委譲で行うと定める。query 側に同期・索引入力準備の wrapper が
あると、索引を整備する経路が 2 つになり、query が確定させた backend とは別の索引を整備しうる
（DES-057 §5.3 の乖離）。エラーにならないため、ファイルの有無で構造的に検査する。

**本ファイルの主題は「ファイル構成」である [MANDATORY]**。SKILL.md 本文が何を書いている / 書いて
いないかという記述内容の契約は `provisional/lint_link_contract.py` が持つ。

実行:
    python3 -m unittest lint.lint_index_maintenance_boundary -v
"""

import unittest
from lint import REPO_ROOT

SKILLS_ROOT = REPO_ROOT / "plugins" / "forge" / "skills"

QUERY_SKILLS = ("query-db-rules", "query-db-specs")
UPDATE_SKILLS = ("update-db-rules", "update-db-specs")

#: 索引整備を担う wrapper。query 側に存在してはならない。
MAINTENANCE_WRAPPERS = ("sync_documents.py", "prepare_index_input.py")


class TestQuerySkillsHaveNoMaintenanceWrappers(unittest.TestCase):
    def test_query_skills_do_not_own_maintenance_wrappers(self):
        for skill in QUERY_SKILLS:
            for wrapper in MAINTENANCE_WRAPPERS:
                path = SKILLS_ROOT / skill / "scripts" / wrapper
                self.assertFalse(
                    path.is_file(),
                    f"{skill} に索引整備の wrapper が存在する: {wrapper}。"
                    "整備は update-db-* へ委譲する（DES-057 §5.3）",
                )

    def test_query_skills_keep_the_query_wrapper(self):
        """委譲の副作用で検索そのものの入口まで失われていないことを確かめる。"""
        for skill in QUERY_SKILLS:
            path = SKILLS_ROOT / skill / "scripts" / "query_documents.py"
            self.assertTrue(path.is_file(), f"{skill} に query wrapper が無い")

    def test_update_skills_own_maintenance_wrappers(self):
        for skill in UPDATE_SKILLS:
            for wrapper in MAINTENANCE_WRAPPERS:
                path = SKILLS_ROOT / skill / "scripts" / wrapper
                self.assertTrue(
                    path.is_file(),
                    f"{skill} に索引整備の wrapper が無い: {wrapper}",
                )


if __name__ == "__main__":
    unittest.main()
