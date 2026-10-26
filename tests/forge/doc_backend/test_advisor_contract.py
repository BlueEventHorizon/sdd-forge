#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc-advisor 契約テスト（DES-057 §9.4 doc-advisor 契約テスト・SKILL.md の静的検証）。

doc-advisor は外部 SKILL であり、`Skill` ツール起動を伴う経路はユニットテストで
実行できないため、SKILL.md の記述を静的に検証して doc-advisor I/F への依拠を機械検証する。

検証項目:

- query が `query-docs` だけを呼び、索引を書き換えないこと（REQ-014 FNC-002）
- 未整備時は承認 → `update-db-*` への委譲 → 再検索の順であること（DES-057 §5.3）
- doc-advisor 経路の query で検索母集団の相違を通知すること
- 可用性判定に必要な SKILL が `index-docs` / `query-docs` の 2 つであること

**復活を防ぐ検証** — 次はいずれも「索引の正しさを別の指標で代用する」または
「読み取り操作の内側で索引を書き換える」誤りであり、再導入されていないことを機械検査する
（REQ-014 BL-002 / DES-057 §2.4・§5.1）:

- 経過時間による鮮度判定（閾値・`--max-age` 相当の引数）を持たないこと
- 検索のたびに索引を更新する経路（「検索前に必ず」「更新の要否を判定しない」）を持たないこと
- バージョン番号による判定を持たないこと

実行:
  python3 -m unittest tests.forge.doc_backend.test_advisor_contract -v
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILLS_DIR = REPO_ROOT / "plugins" / "forge" / "skills"

# query 系 SKILL: category → SKILL.md（category は index-docs / query-docs の --key 値）
QUERY_SKILLS = {
    "rules": _SKILLS_DIR / "query-db-rules" / "SKILL.md",
    "specs": _SKILLS_DIR / "query-db-specs" / "SKILL.md",
}

UPDATE_SKILLS = {
    "rules": _SKILLS_DIR / "update-db-rules" / "SKILL.md",
    "specs": _SKILLS_DIR / "update-db-specs" / "SKILL.md",
}

ALL_SKILLS = {
    **{f"query-{k}": v for k, v in QUERY_SKILLS.items()},
    **{f"update-{k}": v for k, v in UPDATE_SKILLS.items()},
}


def _read_body(skill_path):
    """SKILL.md の frontmatter を除いた本文を返す。"""
    text = skill_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise AssertionError(f"{skill_path} に YAML frontmatter がない")
    end = text.find("\n---", 3)
    if end == -1:
        raise AssertionError(f"{skill_path} の frontmatter が閉じていない")
    return text[end + 4 :]


class _ContractBase(unittest.TestCase):
    """query 系 SKILL.md 本文を category ごとに検証する基盤。"""

    def each_query_skill(self):
        for category, path in QUERY_SKILLS.items():
            with self.subTest(skill=path.parent.name):
                yield category, path, _read_body(path)

    def each_skill(self):
        for name, path in ALL_SKILLS.items():
            with self.subTest(skill=name):
                yield name, path, _read_body(path)


class TestQueryDoesNotWriteTheIndex(_ContractBase):
    """query は索引を書き換えない（REQ-014 FNC-002）。

    検索が読み取り操作の内側で索引を書き換えると、古かった事実が消え、利用者は索引の
    更新漏れに気づけない。整備の入口も `update-db-*` と二重化する。
    """

    def test_query_docs_is_the_only_advisor_invocation(self):
        for _category, path, body in self.each_query_skill():
            idx = body.find("/doc-advisor:query-docs")
            self.assertNotEqual(
                idx, -1, f"{path.parent.name}: query-docs の起動記述がない"
            )
            self.assertNotIn(
                "/doc-advisor:index-docs",
                body,
                f"{path.parent.name}: index-docs を直接起動している（DES-057 §5.1）",
            )

    def test_no_maintenance_wrapper_invocation(self):
        for _category, path, body in self.each_query_skill():
            for wrapper in ("prepare_advisor_index.py", "sync_documents.py"):
                self.assertNotIn(
                    wrapper,
                    body,
                    f"{path.parent.name}: 索引整備 wrapper を呼んでいる: {wrapper}",
                )


class TestUnpreparedIndexDelegation(_ContractBase):
    """未整備時は承認 → `update-db-*` への委譲 → 再検索の順であること（DES-057 §5.3）。"""

    def test_order_is_approval_then_delegation(self):
        """整備の承認が委譲より先にあること。

        探索は整備を扱う Step の見出し以降に限る。SKILL.md 冒頭側にはセッション内変更を確認する
        `AskUserQuestion` が先に現れるため、本文全体を対象にすると整備の承認が消えても
        そちらにマッチして通ってしまう。
        """
        for category, path, body in self.each_query_skill():
            section = body.find("### Step 5")
            self.assertNotEqual(
                section,
                -1,
                f"{path.parent.name}: 整備を扱う Step の見出しが見つからない",
            )
            scope = body[section:]
            approval = scope.find("AskUserQuestion")
            delegation = scope.find(f"/forge:update-db-{category} --backend")
            self.assertNotEqual(
                approval,
                -1,
                f"{path.parent.name}: 整備の Step に承認取得の記述がない",
            )
            self.assertNotEqual(
                delegation,
                -1,
                f"{path.parent.name}: backend を指定した委譲の記述がない",
            )
            self.assertLess(
                approval,
                delegation,
                f"{path.parent.name}: 承認が委譲より先であること",
            )

    def test_declines_do_not_fail_the_operation(self):
        for _category, path, body in self.each_query_skill():
            self.assertIn(
                "失敗として扱わない",
                body,
                f"{path.parent.name}: 見送りを失敗としない旨の記述がない（REQ-014 BL-004）",
            )

    def test_query_does_not_continue_after_failed_maintenance(self):
        """整備が失敗したら検索を続行せず明示エラーで終了すること（REQ-014 BL-003）。

        整備に失敗した backend で検索を続けると、失敗前と同じ状態の索引（または不完全な索引）に
        対する結果が「検索の成功」として返り、整備の失敗が利用者から見えなくなる。
        改行と字下げをまたぐ文のため、空白を正規化してから照合する。
        """
        for _category, path, body in self.each_query_skill():
            section = body.find("### Step 5")
            self.assertNotEqual(
                section,
                -1,
                f"{path.parent.name}: 整備を扱う Step の見出しが見つからない",
            )
            normalized = " ".join(body[section:].split())
            self.assertIn(
                "整備が失敗した場合は 検索せず明示エラーとして終了する".replace(
                    " ", ""
                ),
                normalized.replace(" ", ""),
                f"{path.parent.name}: 整備失敗時に検索を続行しない旨の記述がない（REQ-014 BL-003）",
            )


class TestIndexMaintenanceOutOfScope(_ContractBase):
    """query 系が索引の整備を行わないこと（REQ-014 FNC-002 / BL-002）。"""

    def test_declares_index_maintenance_is_out_of_scope(self):
        for _category, path, body in self.each_query_skill():
            self.assertIn(
                "索引の作成・更新は行わない",
                body,
                f"{path.parent.name}: 責務境界の宣言がない（REQ-014 FNC-002）",
            )


class TestAvailabilityRequiresTwoSkills(_ContractBase):
    """可用性判定に必要な doc-advisor SKILL は index-docs / query-docs の 2 つ。

    query 自身が呼ぶのは `query-docs` だけだが、未整備時に委譲する `update-db-*` が
    `index-docs` を要するため、query 経路の可用性は両者が揃うことを条件とする。
    """

    def test_query_path_requires_index_and_query(self):
        for _category, path, body in self.each_query_skill():
            self.assertIn(
                "`doc-advisor:index-docs`",
                body,
                f"{path.parent.name}: index-docs の可用性条件の記述がない",
            )
            self.assertIn(
                "`doc-advisor:query-docs`",
                body,
                f"{path.parent.name}: query-docs の可用性条件の記述がない",
            )


class TestPinnedBackendContract(unittest.TestCase):
    """`update-db-*` は backend の指定を受理し、指定時は切り替えないこと（REQ-014 BL-006）。"""

    def test_update_skills_accept_pin(self):
        for name, path in UPDATE_SKILLS.items():
            body = _read_body(path)
            with self.subTest(skill=name):
                self.assertIn("--backend", body, f"update-{name}: 指定の受理がない")
                self.assertIn(
                    "他方へ切り替えず明示エラー",
                    body,
                    f"update-{name}: 指定時に切り替えない旨の記述がない",
                )


class TestNoVersionInference(unittest.TestCase):
    """バージョンを条件にせず、成果物の有無からバージョンを推測しないこと。

    「どの版で何が入ったか」は提供側のリリース履歴であり、forge が抱える情報ではない。
    成果物の有無はバージョンではなく、fork・部分インストール・提供側の改名で推測が誤る。
    """

    def test_version_inference_is_forbidden_in_the_design(self):
        """推測しない旨が規範として残っていること（黙って消えていないこと）。

        明文の置き場は設計書である。バージョン判定という個別事項の禁止を SKILL.md へ警告として
        書くことは REQ-003 FNC-004 が禁じており（警告文は AI に禁止対象の存在を認識させ逆効果に
        なりうる）、SKILL.md 側にこの文言を要求すると 2 つの規約が衝突する。

        SKILL.md の禁止警告が一律に禁じられているわけではない（docs/rules/forge_claude_code_authoring_policy.md は
        責務境界の、docs/rules/plugin_claude_code_authoring_guide.md は自己再帰禁止の明記を求めている）。ここで設計書側へ寄せているのは
        バージョン判定に限る。
        """
        design = (
            REPO_ROOT
            / "docs"
            / "specs"
            / "doc-db"
            / "design"
            / "DES-057_doc_db_backend_selection_design.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "バージョンを推測しない",
            design,
            "DES-057 からバージョン推測禁止の規範が消えている",
        )


class TestPopulationDifferenceNotice(_ContractBase):
    """doc-advisor 経路の query では検索母集団の相違を通知し、doc-db 経路では通知しないこと。"""

    def test_notice_present_for_advisor_path_and_absent_for_docdb_path(self):
        for _category, path, body in self.each_query_skill():
            self.assertIn(
                "検索母集団",
                body,
                f"{path.parent.name}: 検索母集団の相違に関する通知の記述がない",
            )
            self.assertIn(
                "doc-db 経路で完了した検索では出さない",
                body,
                f"{path.parent.name}: doc-db 経路では通知しない旨の記述がない",
            )


if __name__ == "__main__":
    unittest.main()
