#!/usr/bin/env python3
"""derive_scope.py（範囲導出 SP-01）の単体テスト。"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "forge"
    / "skills"
    / "start-implement"
    / "scripts"
    / "derive_scope.py"
)

_SPEC = importlib.util.spec_from_file_location("derive_scope", SCRIPT)
derive_scope = importlib.util.module_from_spec(_SPEC)
sys.modules["derive_scope"] = derive_scope
_SPEC.loader.exec_module(derive_scope)

InvalidInputError = derive_scope.InvalidInputError


def _task(task_id, status="pending", design_id=None, depends_on=None):
    return {
        "task_id": task_id,
        "title": f"title-{task_id}",
        "status": status,
        "design_id": design_id,
        "depends_on": depends_on or [],
        "description": [f"desc-{task_id}"],
    }


def _member(task_id, scope_in="到達点", scope_out=None):
    return {"task_id": task_id, "scope_in": scope_in, "scope_out": scope_out or []}


def _out(item, owner=None, reason=None):
    return {"item": item, "owner_task_id": owner, "reason": reason}


class ListCandidatesTest(unittest.TestCase):
    def _ids(self, plan, unit):
        return [
            c["task_id"] for c in derive_scope.list_candidates({"tasks": plan}, unit)
        ]

    def test_same_design_id_is_candidate(self):
        plan = [
            _task("A", design_id="D1"),
            _task("B", design_id="D1"),
            _task("C", design_id="D2"),
        ]
        self.assertEqual(self._ids(plan, ["A"]), ["B"])

    def test_dependency_and_dependent_are_candidates(self):
        plan = [
            _task("A", design_id="D1"),
            _task("PRE", design_id="D9"),
            _task("POST", design_id="D8", depends_on=["A"]),
            _task("FAR", design_id="D7"),
        ]
        plan[0]["depends_on"] = ["PRE"]
        self.assertEqual(self._ids(plan, ["A"]), ["PRE", "POST"])

    def test_null_design_id_does_not_match(self):
        plan = [_task("A"), _task("B")]
        self.assertEqual(self._ids(plan, ["A"]), [])

    def test_completed_and_unit_members_are_excluded(self):
        plan = [
            _task("A", design_id="D1"),
            _task("M", design_id="D1"),
            _task("DONE", status="completed", design_id="D1"),
            _task("IMPL", status="implemented", design_id="D1"),
        ]
        self.assertEqual(self._ids(plan, ["A", "M"]), ["IMPL"])

    def test_candidate_fields(self):
        plan = [_task("A", design_id="D1"), _task("B", design_id="D1")]
        result = derive_scope.list_candidates({"tasks": plan}, ["A"])
        self.assertEqual(
            result, [{"task_id": "B", "title": "title-B", "description": ["desc-B"]}]
        )

    def test_unknown_unit_task_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            derive_scope.list_candidates({"tasks": [_task("A")]}, ["X"])

    def test_empty_unit_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            derive_scope.list_candidates({"tasks": [_task("A")]}, [])

    def test_missing_tasks_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            derive_scope.list_candidates({}, ["A"])

    def test_non_object_plan_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            derive_scope.list_candidates([], ["A"])

    def test_non_object_task_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            derive_scope.list_candidates({"tasks": [_task("A"), "B"]}, ["A"])


class ComposeReviewTextTest(unittest.TestCase):
    def test_single_member_with_scope_out(self):
        text = derive_scope.compose_review_text(
            {
                "members": [
                    _member("T1", "到達 A", [_out("後続の項目", "T9", "計画上分離")])
                ]
            }
        )
        self.assertEqual(
            text,
            "到達 A\n\n以下は今回の範囲外である。担当タスクで実装される。\n\n"
            "- 後続の項目 — T9（計画上分離）",
        )

    def test_no_scope_out_returns_single_sentence(self):
        text = derive_scope.compose_review_text({"members": [_member("T1", "到達 A")]})
        self.assertEqual(text, "到達 A\n\n" + derive_scope._NO_OUT_OF_SCOPE)

    def test_items_owned_by_unit_members_are_subtracted(self):
        text = derive_scope.compose_review_text(
            {
                "members": [
                    _member(
                        "T1",
                        "a",
                        [_out("B の担当", "T2", "分離"), _out("外部", "T9", "分離")],
                    ),
                    _member("T2", "b", [_out("A の担当", "T1", "分離")]),
                ]
            }
        )
        self.assertNotIn("B の担当", text)
        self.assertNotIn("A の担当", text)
        self.assertIn("- 外部 — T9（分離）", text)
        self.assertIn("- T1: a", text)
        self.assertIn("- T2: b", text)

    def test_all_subtracted_yields_no_scope_out_sentence(self):
        text = derive_scope.compose_review_text(
            {
                "members": [
                    _member("T1", "a", [_out("x", "T2", "分離")]),
                    _member("T2", "b"),
                ]
            }
        )
        self.assertTrue(text.endswith(derive_scope._NO_OUT_OF_SCOPE))

    def test_duplicates_removed_by_item_and_owner(self):
        text = derive_scope.compose_review_text(
            {
                "members": [
                    _member("T1", "a", [_out("同じ", "T9", "r")]),
                    _member(
                        "T2", "b", [_out("同じ", "T9", "r"), _out("同じ", "T8", "r")]
                    ),
                ]
            }
        )
        self.assertEqual(text.count("- 同じ — T9"), 1)
        self.assertEqual(text.count("- 同じ — T8"), 1)

    def test_owner_none_is_kept(self):
        text = derive_scope.compose_review_text(
            {"members": [_member("T1", "a", [_out("孤児")])]}
        )
        self.assertIn("- 孤児", text)


class InputValidationTest(unittest.TestCase):
    def _compose(self, **member_kwargs):
        return derive_scope.compose_review_text(
            {"members": [_member("T1", **member_kwargs)]}
        )

    def test_multiline_scope_in_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            self._compose(scope_in="一行目\n二行目")

    def test_carriage_return_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            self._compose(scope_in="一行目\r二行目")

    def test_heading_line_is_rejected(self):
        for value in ("# 見出し", "### 見出し", "```python", "~~~", "  ## 見出し"):
            with self.subTest(value=value), self.assertRaises(InvalidInputError):
                self._compose(scope_in=value)

    def test_hash_without_space_is_accepted(self):
        self.assertIn("#1 を直す", self._compose(scope_in="#1 を直す"))

    def test_protocol_prefix_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            self._compose(scope_in="REVIEW_RESULT: ok")

    def test_scope_out_fields_are_validated(self):
        for field in ("item", "owner_task_id", "reason"):
            entry = _out("項目", "T9", "理由")
            entry[field] = "a\nb"
            with self.subTest(field=field), self.assertRaises(InvalidInputError):
                self._compose(scope_out=[entry])
            entry[field] = "# h"
            with (
                self.subTest(field=field, kind="heading"),
                self.assertRaises(InvalidInputError),
            ):
                self._compose(scope_out=[entry])

    def test_scope_out_item_is_required(self):
        with self.assertRaises(InvalidInputError):
            self._compose(scope_out=[_out("  ", "T9")])

    def test_non_string_value_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            self._compose(scope_in=123)

    def test_scope_out_shape_is_validated(self):
        with self.assertRaises(InvalidInputError):
            self._compose(scope_out="x")
        with self.assertRaises(InvalidInputError):
            self._compose(scope_out=["x"])

    def test_scope_in_is_required(self):
        with self.assertRaises(InvalidInputError):
            self._compose(scope_in=None)

    def test_members_shape_is_validated(self):
        for payload in ({}, {"members": []}, {"members": ["x"]}, []):
            with self.subTest(payload=payload), self.assertRaises(InvalidInputError):
                derive_scope.compose_review_text(payload)

    def test_duplicate_member_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            derive_scope.compose_review_text(
                {"members": [_member("T1"), _member("T1")]}
            )


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".temp" / "forge" / "start-implement").mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_candidates_cli(self):
        plan = self.root / "plan.json"
        plan.write_text(
            json.dumps(
                {"tasks": [_task("A", design_id="D"), _task("B", design_id="D")]}
            ),
            encoding="utf-8",
        )
        proc = self._run("--candidates", "--plan-path", str(plan), "--unit", "A")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            [c["task_id"] for c in json.loads(proc.stdout)["candidates"]], ["B"]
        )

    def test_candidates_cli_unknown_task_exits_1_with_errors(self):
        plan = self.root / "plan.json"
        plan.write_text(json.dumps({"tasks": [_task("A")]}), encoding="utf-8")
        proc = self._run("--candidates", "--plan-path", str(plan), "--unit", "X")
        self.assertEqual(proc.returncode, 1)
        self.assertIsInstance(json.loads(proc.stdout)["errors"], list)

    def test_candidates_cli_malformed_plan_exits_1_with_errors(self):
        for body in ([], {"tasks": [_task("A"), "B"]}):
            with self.subTest(body=body):
                plan = self.root / "plan.json"
                plan.write_text(json.dumps(body), encoding="utf-8")
                proc = self._run(
                    "--candidates", "--plan-path", str(plan), "--unit", "A"
                )
                self.assertEqual(proc.returncode, 1)
                self.assertTrue(json.loads(proc.stdout)["errors"])

    def test_unreadable_plan_exits_1(self):
        proc = self._run("--candidates", "--plan-path", "missing.json", "--unit", "A")
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(json.loads(proc.stdout)["errors"])

    def test_review_text_cli_consumes_input(self):
        rel = ".temp/forge/start-implement/scope-input.json"
        (self.root / rel).write_text(
            json.dumps({"members": [_member("T1", "到達")]}), encoding="utf-8"
        )
        proc = self._run("--review-text", "--input-file", rel)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["review_text"].startswith("到達"))
        self.assertFalse((self.root / rel).exists())

    def test_review_text_cli_rejects_invalid_value(self):
        rel = ".temp/forge/start-implement/scope-input.json"
        (self.root / rel).write_text(
            json.dumps({"members": [_member("T1", "# 見出し")]}), encoding="utf-8"
        )
        proc = self._run("--review-text", "--input-file", rel)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(json.loads(proc.stdout)["errors"])

    def test_review_text_cli_rejects_path_outside_temp(self):
        proc = self._run("--review-text", "--input-file", "input.json")
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(json.loads(proc.stdout)["errors"])

    def test_missing_mode_exits_2(self):
        self.assertEqual(self._run().returncode, 2)

    def test_missing_mode_arguments_exit_2(self):
        self.assertEqual(self._run("--candidates").returncode, 2)
        self.assertEqual(self._run("--review-text").returncode, 2)


if __name__ == "__main__":
    unittest.main()
