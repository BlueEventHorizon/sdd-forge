#!/usr/bin/env python3
"""AI-Linter の入口（`ai_lint/run.py`）の単体テスト。偽の backend を使う。

実行:
  python3 -m unittest tests.ai_lint_unit.test_run -v
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from ai_lint.backend import BackendError, Judgement
from ai_lint.run import EXIT_FINDINGS, EXIT_NOT_RUN, EXIT_OK, main

BODY = "秘密にすべき本文"


class FakeBackend:
    name = "fake"

    def __init__(self, probabilities):
        self.probabilities = probabilities

    def judge(self, document, questions):
        return Judgement(dict(self.probabilities), input_tokens=7, model="fake-1")


class RunTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "checks").mkdir()
        (self.root / "docs" / "a.md").write_text(BODY, encoding="utf-8")
        (self.root / "checks" / "sample.json").write_text(
            json.dumps(
                {
                    "id": "sample",
                    "targets": ["docs/*.md"],
                    "questions": [
                        {
                            "id": "q1",
                            "question": "`document` は書き込みを禁じているか。",
                            "expect": "yes",
                            "basis": "規則 A",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, argv, backend=None, factory=None):
        out = io.StringIO()
        code = main(
            argv,
            backend_factory=factory or (lambda name: backend),
            root=self.root,
            checks_dir=self.root / "checks",
            out=out,
        )
        return code, out.getvalue()

    def test_all_pass(self):
        code, text = self._run([], FakeBackend({"q1": 0.95}))
        self.assertEqual(EXIT_OK, code)
        self.assertIn("合格 docs/a.md sample/q1 期待=yes 確率=0.950", text)
        self.assertIn("合格 1 / 違反 0 / 保留 0", text)
        self.assertIn("入力 7 トークン", text)

    def test_violation_reports_question_and_basis(self):
        code, text = self._run([], FakeBackend({"q1": 0.05}))
        self.assertEqual(EXIT_FINDINGS, code)
        self.assertIn("違反 docs/a.md sample/q1", text)
        self.assertIn("根拠: 規則 A", text)

    def test_uncertain_is_not_a_pass(self):
        code, text = self._run([], FakeBackend({"q1": 0.5}))
        self.assertEqual(EXIT_FINDINGS, code)
        self.assertIn("保留 docs/a.md sample/q1", text)

    def test_document_body_is_never_printed(self):
        for probability in (0.95, 0.5, 0.05):
            _code, text = self._run([], FakeBackend({"q1": probability}))
            self.assertNotIn(BODY, text)

    def test_backend_unavailable_is_not_run(self):
        def factory(name):
            raise BackendError("キーがありません")

        code, text = self._run([], factory=factory)
        self.assertEqual(EXIT_NOT_RUN, code)
        self.assertIn("実行できませんでした: キーがありません", text)

    def test_unknown_check_is_not_run(self):
        code, _text = self._run(["--check", "nothing"], FakeBackend({"q1": 0.95}))
        self.assertEqual(EXIT_NOT_RUN, code)

    def test_target_without_match_is_not_run(self):
        (self.root / "docs" / "a.md").unlink()
        code, _text = self._run([], FakeBackend({"q1": 0.95}))
        self.assertEqual(EXIT_NOT_RUN, code)

    def test_dry_run_does_not_create_a_backend(self):
        def factory(name):
            raise AssertionError("dry-run で backend を作ってはならない")

        code, text = self._run(["--dry-run"], factory=factory)
        self.assertEqual(EXIT_OK, code)
        self.assertIn("対象 docs/a.md", text)
        self.assertIn("問い q1 期待=yes 根拠=規則 A", text)


if __name__ == "__main__":
    unittest.main()
