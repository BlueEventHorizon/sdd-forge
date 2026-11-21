#!/usr/bin/env python3
"""ADR の検査ロジック（`lint/adr_rules.py`）の単体テスト。

合成した ADR ファイルで、書式の検査そのものが働くことを確かめる
（実ファイルが 0 件でも空振りしないことの担保）。

実行:
  python3 -m unittest tests.lint_rules.test_adr_rules -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lint.adr_rules import (
    adr_dirs_with_multiple_files,
    invalidation_marker_violations,
    markdown_links,
    structure_violations,
    undefined_reference_labels,
)

GOOD_ADR = """\
# ADR-001 foo の決定記録

## 1. 最初の決定

### 1.1 コンテキスト

背景。

### 1.2 決定

決定の内容。

### 1.3 検討した代替案

| 代替案 | 棄却理由 |
| ------ | -------- |
| 案 A   | 理由     |

### 1.4 影響

帰結。

## 2. 次の決定

### 2.1 コンテキスト

背景。

### 2.2 決定

決定の内容。

### 2.3 検討した代替案

| 代替案 | 棄却理由 |
| ------ | -------- |

### 2.4 影響

帰結。
"""


class TestFormatChecksDetectViolations(unittest.TestCase):
    """書式の検査そのものが働くこと（実ファイルが 0 件でも空振りしないことの担保）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _adr(self, text, name="ADR-001_foo.md"):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_good_file_passes(self):
        self.assertEqual([], structure_violations(self._adr(GOOD_ADR)))

    def test_reference_links_are_resolved_through_their_definitions(self):
        """リファレンスリンクは、定義で解決したリンク先として拾う（title つきの定義を含む）。"""
        path = self._adr(
            "判定は [DES-001][des-001] §3.2 に従う。書式は [foo][foo-format] を見る。\n"
            "\n"
            '[des-001]: ../design/DES-001_foo_design.md "abc DLID-xxxxxxxxxxxx"\n'
            "[foo-format]: foo_format.md#section\n"
        )
        links = markdown_links(path)
        self.assertEqual(
            ["../design/DES-001_foo_design.md", "foo_format.md"],
            [link for _lineno, _line, _end, link in links],
        )
        _lineno, line, end, _link = links[0]
        self.assertTrue(line[end:].startswith(" §3.2"))

    def test_inline_links_are_still_found(self):
        path = self._adr("書式は [foo](foo_format.md) を見る。\n")
        self.assertEqual(
            ["foo_format.md"], [link for *_rest, link in markdown_links(path)]
        )

    def test_reference_without_definition_is_detected(self):
        """ラベルの書き誤り・定義の書き忘れは、黙って通さずに拾う。"""
        path = self._adr(
            "書式は [foo][foo-fromat] を見る。外部は [RFC][rfc] を見る。\n"
            "\n"
            "[foo-format]: foo_format.md\n"
            "[rfc]: https://example.com/rfc\n"
        )
        self.assertEqual([(1, "foo-fromat")], undefined_reference_labels(path))

    def test_links_in_code_are_not_links(self):
        path = self._adr("例: `[foo][foo-format]`\n\n[foo-format]: foo_format.md\n")
        self.assertEqual([], markdown_links(path))

    def test_heading_identifiers_are_not_part_of_the_names(self):
        """見出しの行末に付与された識別子は、小節の名前に含めない。"""
        text = "\n".join(
            f"{line} DLID-abc123def456" if line.startswith("#") else line
            for line in GOOD_ADR.splitlines()
        )
        self.assertEqual([], structure_violations(self._adr(text)))

    def test_multiple_decisions_in_one_file_are_allowed(self):
        """1 つのファイルに、決定の節が複数並ぶ。"""
        self.assertEqual(2, GOOD_ADR.count("\n## "))
        self.assertEqual([], structure_violations(self._adr(GOOD_ADR)))

    def test_legacy_metadata_section_is_detected(self):
        text = GOOD_ADR.replace(
            "## 1. 最初の決定", "## メタデータ\n\n| ID | x |\n\n## 1. 最初の決定", 1
        )
        self.assertTrue(structure_violations(self._adr(text)))

    def test_section_without_number_is_detected(self):
        text = GOOD_ADR.replace("## 2. 次の決定", "## 次の決定")
        self.assertTrue(structure_violations(self._adr(text)))

    def test_non_ascending_section_number_is_detected(self):
        text = GOOD_ADR.replace("## 2. 次の決定", "## 1. 次の決定").replace(
            "### 2.", "### 1."
        )
        self.assertTrue(structure_violations(self._adr(text)))

    def test_missing_subsection_is_detected(self):
        text = GOOD_ADR.replace("### 2.4 影響\n\n帰結。\n", "")
        self.assertTrue(structure_violations(self._adr(text)))

    def test_subsection_without_number_is_detected(self):
        text = GOOD_ADR.replace("### 1.4 影響", "### 影響")
        self.assertTrue(structure_violations(self._adr(text)))

    def test_subsection_of_another_section_is_detected(self):
        text = GOOD_ADR.replace("### 2.1 コンテキスト", "### 1.5 コンテキスト")
        self.assertTrue(structure_violations(self._adr(text)))

    def test_second_title_is_detected(self):
        self.assertTrue(
            structure_violations(self._adr(GOOD_ADR + "\n# 別のタイトル\n"))
        )

    def test_invalidation_marker_is_detected(self):
        text = GOOD_ADR.replace(
            "## 1. 最初の決定", "## 1. 最初の決定 ⚠️失効（別の決定が置き換えた）"
        )
        self.assertTrue(invalidation_marker_violations(self._adr(text)))

    def test_invalidation_marker_in_code_is_not_a_violation(self):
        """記法の説明として、コードの中で言及することは違反ではない。"""
        text = GOOD_ADR + "\n廃止した記法は `⚠️失効` である。\n"
        self.assertEqual([], invalidation_marker_violations(self._adr(text)))

    def test_multiple_adr_files_in_one_adr_dir_are_detected(self):
        adr_dir = self.root / "docs" / "specs" / "foo" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "ADR-001_foo.md").write_text(GOOD_ADR, encoding="utf-8")
        self.assertEqual([], adr_dirs_with_multiple_files(self.root))
        (adr_dir / "ADR-002_foo.md").write_text(GOOD_ADR, encoding="utf-8")
        self.assertEqual(1, len(adr_dirs_with_multiple_files(self.root)))


if __name__ == "__main__":
    unittest.main()
