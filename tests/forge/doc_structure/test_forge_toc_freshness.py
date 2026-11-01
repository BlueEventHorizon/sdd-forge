#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""forge 同梱 ToC の鮮度契約テスト。

`plugins/forge/toc/rules/rules_toc.yaml` と `.toc_checksums.yaml` は、doc-advisor が
管理する store（`.claude/.doc-advisor/toc/forge-rules-*/`）のコピー配布物であり、
`update-forge-toc` skill（`.claude/skills/update-forge-toc/`）の実行を忘れると
ソース文書（`plugins/forge/docs/`, `plugins/forge/skills/*/docs/`）を更新しても
黙って stale になる。以下を検証し、更新忘れを CI / ローカルテストで検出する:

1. `.bak` ファイルが残存していないこと
2. 同梱の `.toc_checksums.yaml`（doc-advisor が toc.yaml と同時に書いたもの）が、
   現在のソース文書の内容 hash（sha256）と一致すること
3. 同梱の `rules_toc.yaml` の索引パス集合が、解決された全ソース文書パス集合と
   完全一致すること（不足だけでなく、doc_structure から外れた余剰エントリも検出する）
4. 索引パスがすべて実在すること
5. 同梱の `rules_toc.yaml` と `.toc_checksums.yaml` が、store のものと同一であること
   （コピー漏れ・片方だけのコピーを検出する）

checksums は doc-advisor が toc.yaml と同じ merge で書くため、2 が通れば
ToC 本体も同じソース文書から作られている（forge が checksums を別計算しないので、
「checksums だけが新しく ToC 本体が古い」状態は作れない）。

実行:
    python3 -m unittest tests.forge.doc_structure.test_forge_toc_freshness -v
"""

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_STRUCTURE_SCRIPTS = REPO_ROOT / "plugins" / "forge" / "scripts" / "doc_structure"
DOC_STRUCTURE_PATH = ".claude/skills/update-forge-toc/forge_doc_structure.yaml"
TOC_DIR = REPO_ROOT / "plugins" / "forge" / "toc"
RULES_TOC_PATH = TOC_DIR / "rules" / "rules_toc.yaml"
CHECKSUMS_PATH = TOC_DIR / "rules" / ".toc_checksums.yaml"
STORE_ROOT = REPO_ROOT / ".claude" / ".doc-advisor" / "toc"

DOC_KEY_PATTERN = re.compile(r"^  (\S.*\.md):$", re.MULTILINE)
CHECKSUM_PATTERN = re.compile(r"^  (\S.*\.md): ([0-9a-f]{64})$", re.MULTILINE)


def resolve_rules_paths():
    result = subprocess.run(
        [
            sys.executable,
            str(DOC_STRUCTURE_SCRIPTS / "resolve_doc_structure.py"),
            "--type",
            "rules",
            "--doc-structure",
            DOC_STRUCTURE_PATH,
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["status"] == "ok", data
    return sorted(data["rules"])


class TestForgeTocFreshness(unittest.TestCase):
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

    def test_toc_checksums_match_current_docs(self):
        committed = dict(
            CHECKSUM_PATTERN.findall(CHECKSUMS_PATH.read_text(encoding="utf-8"))
        )
        current = {
            path: hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest()
            for path in resolve_rules_paths()
        }

        self.assertEqual(
            committed,
            current,
            "plugins/forge/toc/rules/.toc_checksums.yaml が現在のソース文書と一致しません"
            "（stale）。plugins/forge/docs/ または plugins/forge/skills/*/docs/ の更新後は"
            "update-forge-toc skill を実行して ToC と checksums を再生成してください。",
        )

    def test_rules_toc_indexed_paths_match_resolved_paths_exactly(self):
        resolved = set(resolve_rules_paths())
        toc_text = RULES_TOC_PATH.read_text(encoding="utf-8")
        indexed = set(DOC_KEY_PATTERN.findall(toc_text))

        missing = sorted(resolved - indexed)
        surplus = sorted(indexed - resolved)

        self.assertEqual(
            (missing, surplus),
            ([], []),
            f"rules_toc.yaml の索引パス集合が解決済みソース文書パス集合と一致しません。\n"
            f"不足（索引に無い文書）: {missing}\n"
            f"余剰（doc_structure から外れた stale な索引エントリ）: {surplus}\n"
            "update-forge-toc skill を実行して再生成してください。",
        )

    def test_rules_toc_paths_all_exist_on_disk(self):
        toc_text = RULES_TOC_PATH.read_text(encoding="utf-8")
        indexed_paths = DOC_KEY_PATTERN.findall(toc_text)
        self.assertGreater(
            len(indexed_paths), 0, "rules_toc.yaml から索引パスを抽出できませんでした"
        )

        missing = [p for p in indexed_paths if not (REPO_ROOT / p).is_file()]
        self.assertEqual(
            missing,
            [],
            f"rules_toc.yaml に索引があるが実在しないファイルがあります: {missing}",
        )

    def test_shipped_files_are_identical_to_doc_advisor_store(self):
        stores = sorted(STORE_ROOT.glob("forge-rules-*"))
        self.assertEqual(
            len(stores),
            1,
            f"forge-rules の store がちょうど 1 つ必要です: {[str(s) for s in stores]}",
        )
        store = stores[0]

        for shipped, source in (
            (RULES_TOC_PATH, store / "toc.yaml"),
            (CHECKSUMS_PATH, store / ".toc_checksums.yaml"),
        ):
            self.assertEqual(
                shipped.read_bytes(),
                source.read_bytes(),
                f"{shipped.relative_to(REPO_ROOT)} が store の "
                f"{source.relative_to(REPO_ROOT)} と一致しません。"
                "update-forge-toc skill の Step 3 で、2 つとも store からコピーしてください。",
            )


if __name__ == "__main__":
    unittest.main()
