#!/usr/bin/env python3
"""AI-Linter の宣言の読み込みと判定の規則（`ai_lint/judge.py`）の単体テスト。

実行:
  python3 -m unittest tests.ai_lint_unit.test_judge -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_lint.backend import BackendError, Judgement
from ai_lint.judge import (
    PASS,
    UNCERTAIN,
    VIOLATION,
    CheckError,
    grade,
    load_checks,
    parse_check,
    resolve_targets,
    run_checks,
    strip_frontmatter,
)


def check_data(**overrides):
    data = {
        "id": "sample",
        "targets": ["docs/*.md"],
        "questions": [
            {
                "id": "q1",
                "question": "`document` は書き込みを禁じているか。",
                "expect": "yes",
                "basis": "規則 A",
            },
            {
                "id": "q2",
                "question": "`document` は書き込みを許しているか。",
                "expect": "no",
                "basis": "規則 A",
            },
        ],
    }
    data.update(overrides)
    return data


class FakeBackend:
    name = "fake"

    def __init__(self, probabilities):
        self.probabilities = probabilities
        self.calls = []

    def judge(self, document, questions):
        self.calls.append((document, dict(questions)))
        return Judgement(dict(self.probabilities), input_tokens=10, model="fake-1")


class GradeTest(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(PASS, grade(True, 0.7))
        self.assertEqual(PASS, grade(False, 0.3))
        self.assertEqual(VIOLATION, grade(True, 0.3))
        self.assertEqual(VIOLATION, grade(False, 0.7))

    def test_between_thresholds_is_uncertain_for_either_expectation(self):
        """保留は、期待がどちらでも合格にしない。"""
        for expect in (True, False):
            for probability in (0.31, 0.5, 0.69):
                self.assertEqual(UNCERTAIN, grade(expect, probability))


class ParseCheckTest(unittest.TestCase):
    def test_valid(self):
        check = parse_check(check_data(), "sample.json")
        self.assertEqual("sample", check.id)
        self.assertEqual([True, False], [q.expect for q in check.questions])

    def test_defects_are_rejected(self):
        question = check_data()["questions"][0]
        cases = {
            "id が無い": check_data(id=""),
            "targets が空": check_data(targets=[]),
            "questions が空": check_data(questions=[]),
            "expect が不正": check_data(questions=[{**question, "expect": "maybe"}]),
            "根拠が無い": check_data(questions=[{**question, "basis": ""}]),
            "文書を指していない": check_data(
                questions=[{**question, "question": "書き込みを禁じているか。"}]
            ),
            "問いの id が重複": check_data(questions=[question, question]),
        }
        for name, data in cases.items():
            with self.subTest(name):
                with self.assertRaises(CheckError):
                    parse_check(data, "sample.json")


class FilesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "checks").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _write_check(self, name, data):
        (self.root / "checks" / name).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def test_no_check_files_is_an_error(self):
        with self.assertRaises(CheckError):
            load_checks(self.root / "checks")

    def test_broken_json_is_an_error(self):
        (self.root / "checks" / "a.json").write_text("{", encoding="utf-8")
        with self.assertRaises(CheckError):
            load_checks(self.root / "checks")

    def test_duplicate_check_ids_are_an_error(self):
        self._write_check("a.json", check_data())
        self._write_check("b.json", check_data())
        with self.assertRaises(CheckError):
            load_checks(self.root / "checks")

    def test_pattern_without_match_is_an_error(self):
        """対象が 0 件の検査を、合格として通さない。"""
        with self.assertRaises(CheckError):
            resolve_targets(self.root, ("docs/*.md",))

    def test_run_sends_body_without_frontmatter_once_per_document(self):
        (self.root / "docs" / "a.md").write_text(
            "---\nname: a\n---\n本文 A\n", encoding="utf-8"
        )
        (self.root / "docs" / "b.md").write_text("本文 B\n", encoding="utf-8")
        self._write_check("a.json", check_data())
        backend = FakeBackend({"q1": 0.9, "q2": 0.5})
        results, usage = run_checks(
            load_checks(self.root / "checks"), backend, self.root
        )
        self.assertEqual(["本文 A\n", "本文 B\n"], [call[0] for call in backend.calls])
        self.assertEqual({"q1", "q2"}, set(backend.calls[0][1]))
        self.assertEqual(
            [
                ("docs/a.md", "q1", PASS),
                ("docs/a.md", "q2", UNCERTAIN),
                ("docs/b.md", "q1", PASS),
                ("docs/b.md", "q2", UNCERTAIN),
            ],
            [(r.path, r.question.id, r.outcome) for r in results],
        )
        self.assertEqual(
            (2, 20, ("fake-1",)), (usage.requests, usage.input_tokens, usage.models)
        )

    def test_missing_answer_from_backend_is_an_error(self):
        (self.root / "docs" / "a.md").write_text("本文\n", encoding="utf-8")
        self._write_check("a.json", check_data())
        with self.assertRaises(BackendError):
            run_checks(
                load_checks(self.root / "checks"), FakeBackend({"q1": 0.9}), self.root
            )


class StripFrontmatterTest(unittest.TestCase):
    def test_only_leading_frontmatter_is_removed(self):
        self.assertEqual(
            "本文\n---\nx\n---\n",
            strip_frontmatter("---\na: 1\n---\n本文\n---\nx\n---\n"),
        )
        self.assertEqual("本文\n", strip_frontmatter("本文\n"))


if __name__ == "__main__":
    unittest.main()
