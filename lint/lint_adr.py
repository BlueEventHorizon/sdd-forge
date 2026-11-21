#!/usr/bin/env python3
"""lint: ADR の参照と書式の整合。

ADR は仕様を書かず参照で示すため、参照が沈黙して腐ると ADR 自体が誤った根拠になる。
ADR は「その提案は検討済みで、こういう理由で採らなかった」と答えるために読まれるので、
宛先を失った参照は誤った見送り判断を生む。

検査するもの:

- 参照の実在: マークダウンリンクのリンク先ファイル、リンクに添えた `§X.Y`、
  および `ADR-NNN §X.Y` 形式の参照の宛先
- 書式の維持: feature ごとに 1 つの ADR ファイル、決定ごとの節（`## N.`）と
  4 つの小節（`### N.1`〜`### N.4`）、旧書式（メタデータ表・ステータス履歴節）と
  失効マーカーへの逆戻り

`ADR-NNN §X.Y` は ADR の外（コード・テスト・他の文書）からも書かれうるため、
リポジトリ全体を走査する。節番号が動けば、そうした参照は宛先を失う。

ADR が 1 件も無い状態では走査対象が空になり、検査はすべて通る。検査ロジックは
`adr_rules.py` にある。

実行:
  python3 -m unittest lint.lint_adr -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from lint import REPO_ROOT
from lint.adr_rules import (
    ADR_SECTION_REF_RE,
    SECTION_RE,
    TRAILING_SECTION_RE,
    adr_dirs_with_multiple_files,
    heading_numbers,
    invalidation_marker_violations,
    markdown_links,
    structure_violations,
    undefined_reference_labels,
)

SPECS_DIR = REPO_ROOT / "docs" / "specs"

#: `ADR-NNN §X.Y` 形式の参照を走査する対象。`.claude/` は生成物なので除く。
CROSS_REF_ROOTS = ("docs", "plugins", "tests", "lint")
CROSS_REF_SUFFIXES = (".md", ".py", ".sh")


def adr_files() -> list[Path]:
    return sorted(SPECS_DIR.rglob("ADR-*.md"))


class TestADRReferenceIntegrity(unittest.TestCase):
    """ADR が張る参照の宛先が実在すること。"""

    def test_markdown_link_targets_exist(self):
        """マークダウンリンクのリンク先ファイルが実在すること。"""
        broken: list[str] = []
        for path in adr_files():
            for lineno, _line, _end, link in markdown_links(path):
                if not (path.parent / link).resolve().is_file():
                    rel = path.relative_to(REPO_ROOT)
                    broken.append(f"{rel}:{lineno} -> {link}")
        self.assertEqual(
            [],
            broken,
            "ADR のマークダウンリンクが実在しないファイルを指している:\n"
            + "\n".join(broken),
        )

    def test_reference_links_have_definitions(self):
        """本文のリファレンスリンクのラベルに、定義があること。"""
        broken: list[str] = []
        for path in adr_files():
            rel = path.relative_to(REPO_ROOT)
            for lineno, label in undefined_reference_labels(path):
                broken.append(f"{rel}:{lineno} -> [{label}]")
        self.assertEqual(
            [],
            broken,
            "ADR のリファレンスリンクに定義が無い:\n" + "\n".join(broken),
        )

    def test_section_suffix_of_links_exists_in_target(self):
        """リンクに添えた `§X.Y` が参照先文書に実在する見出しであること。"""
        broken: list[str] = []
        for path in adr_files():
            for lineno, line, end, link in markdown_links(path):
                target = (path.parent / link).resolve()
                if not target.is_file():
                    continue  # 上のテストが報告する
                tail = TRAILING_SECTION_RE.match(line[end:])
                if not tail:
                    continue
                available = heading_numbers(target)
                for number in SECTION_RE.findall(tail.group(0)):
                    if number not in available:
                        rel = path.relative_to(REPO_ROOT)
                        broken.append(f"{rel}:{lineno} -> {link} §{number}")
        self.assertEqual(
            [],
            broken,
            "リンクに添えた節番号が参照先に存在しない:\n" + "\n".join(broken),
        )

    def test_adr_section_references_resolve(self):
        """`ADR-NNN §X.Y` 形式の参照の宛先が実在すること（リポジトリ全体）。"""
        by_number: dict[str, Path] = {}
        for path in adr_files():
            m = re.match(r"ADR-(\d{3})_", path.name)
            if m:
                by_number[m.group(1)] = path

        headings_cache: dict[str, set[str]] = {}
        self_path = Path(__file__).resolve()
        broken: list[str] = []

        for root in CROSS_REF_ROOTS:
            for path in sorted((REPO_ROOT / root).rglob("*")):
                if not path.is_file() or path.suffix not in CROSS_REF_SUFFIXES:
                    continue
                if path.resolve() == self_path:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for lineno, line in enumerate(text.splitlines(), 1):
                    for number, section in ADR_SECTION_REF_RE.findall(line):
                        target = by_number.get(number)
                        rel = path.relative_to(REPO_ROOT)
                        if target is None:
                            broken.append(f"{rel}:{lineno} -> ADR-{number}（不在）")
                            continue
                        if number not in headings_cache:
                            headings_cache[number] = heading_numbers(target)
                        if section not in headings_cache[number]:
                            broken.append(f"{rel}:{lineno} -> ADR-{number} §{section}")
        self.assertEqual(
            [],
            broken,
            "`ADR-NNN §X.Y` 形式の参照が宛先を失っている:\n" + "\n".join(broken),
        )


class TestADRFormat(unittest.TestCase):
    """ADR が現行書式を保っていること（旧書式への逆戻りの検出）。"""

    def test_real_adr_files_follow_the_structure(self):
        violations = [v for path in adr_files() for v in structure_violations(path)]
        self.assertEqual(
            [],
            violations,
            "ファイルの構成が adr_format.md「ファイルの構成」に反する:\n"
            + "\n".join(violations),
        )

    def test_real_adr_files_have_no_invalidation_marker(self):
        violations = [
            v for path in adr_files() for v in invalidation_marker_violations(path)
        ]
        self.assertEqual(
            [],
            violations,
            "ADR は失効マーカーを持たない（adr_principles_spec.md「決定の否決」）:\n"
            + "\n".join(violations),
        )

    def test_one_adr_file_per_feature(self):
        self.assertEqual(
            [],
            adr_dirs_with_multiple_files(SPECS_DIR),
            "同じ feature の ADR は 1 つのファイルに書く（adr_principles_spec.md「配置と ID 採番」）",
        )


if __name__ == "__main__":
    unittest.main()
