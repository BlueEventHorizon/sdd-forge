#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_forge_toc.py の、索引（.doc-link/tocs/<キー>.json）の読み取りのテスト。

doc-link は、索引の `documents` の書き方を変えた。旧は `{"doc_link_id": …, "applied_hash": …}` の
オブジェクト、新（0.1.6 以降）は文書 ID の文字列である。旧は、次に索引を再構築するまで残る。
どちらの索引からも、同じ文書情報を読めることを確かめる。

実行:
    python3 -m unittest tests.update_forge_toc.test_build_forge_toc -v
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from lint import REPO_ROOT

BUILD_SCRIPT = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "update-forge-toc"
    / "scripts"
    / "build_forge_toc.py"
)

DOC_ID = "DLID-aaaaaaaaaaaa"
DOC_PATH = "plugins/forge/docs/sample.md"


def load_build_module():
    spec = importlib.util.spec_from_file_location("build_forge_toc", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestLoadEntries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = load_build_module()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        source = self.root / DOC_PATH
        source.parent.mkdir(parents=True)
        source.write_text("# sample\n", encoding="utf-8")
        store = self.root / ".doc-link"
        (store / "documents").mkdir(parents=True)
        (store / "tocs").mkdir(parents=True)
        self.doc = {
            "doc_link_id": DOC_ID,
            "path": DOC_PATH,
            "title": "sample",
            "purpose": "purpose",
            "summary": ["a"],
            "tasks": ["b"],
            "keywords": ["c"],
        }
        (store / "documents" / f"{DOC_ID}.json").write_text(
            json.dumps(self.doc), encoding="utf-8"
        )

    def _write_toc(self, documents):
        toc = {"toc_key": "forge-rules", "documents": documents}
        path = self.root / ".doc-link" / "tocs" / "forge-rules.json"
        path.write_text(json.dumps(toc), encoding="utf-8")

    def test_old_format_documents_are_objects(self):
        self._write_toc([{"doc_link_id": DOC_ID, "applied_hash": "x"}])
        self.assertEqual(self.build.load_entries(self.root), [self.doc])

    def test_new_format_documents_are_id_strings(self):
        self._write_toc([DOC_ID])
        self.assertEqual(self.build.load_entries(self.root), [self.doc])

    def test_unknown_item_type_is_a_build_error(self):
        self._write_toc([123])
        with self.assertRaises(self.build.BuildError):
            self.build.load_entries(self.root)

    def test_object_without_document_id_is_a_build_error(self):
        self._write_toc([{"applied_hash": "x"}])
        with self.assertRaises(self.build.BuildError):
            self.build.load_entries(self.root)

    def test_document_set_mismatch_is_a_build_error(self):
        self._write_toc([])
        with self.assertRaises(self.build.BuildError):
            self.build.load_entries(self.root)


if __name__ == "__main__":
    unittest.main()
