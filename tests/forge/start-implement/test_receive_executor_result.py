#!/usr/bin/env python3
"""結果検査（receive_executor_result.py / executor_result_contract.py）の契約テスト。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "forge" / "skills" / "start-implement" / "scripts"
SCRIPT = SCRIPTS_DIR / "receive_executor_result.py"

sys.path.insert(0, str(SCRIPTS_DIR))
from executor_result_contract import (  # noqa: E402
    ContextError,
    TASK_RESULT_FIELDS,
    VERIFICATION_RESULT_FIELDS,
    check_result,
    inspect_result,
    load_expectation,
)


def make_context(build="required", tests="required", **overrides):
    context = {
        "task_id": "TASK-001",
        "verification": {
            "build": build,
            "build_reason": None if build == "required" else "build_check が skip",
            "tests": tests,
            "tests_reason": None if tests == "required" else "理由",
        },
    }
    context.update(overrides)
    return context


def valid_result(**overrides):
    result = {
        "task_id": "TASK-001",
        "status": "SUCCESS",
        "files_modified": ["src/foo.py"],
        "summary": "foo を実装",
        "verification": {
            "build": "success",
            "build_reason": None,
            "tests": "success",
            "tests_reason": None,
        },
        "notes": [],
        "error": None,
    }
    result.update(overrides)
    return result


class FieldSetTest(unittest.TestCase):
    def test_contract_owns_field_sets(self):
        self.assertEqual(set(valid_result()), set(TASK_RESULT_FIELDS))
        self.assertEqual(
            set(valid_result()["verification"]), set(VERIFICATION_RESULT_FIELDS)
        )

    def test_pre_mortem_is_contract_violation(self):
        raw = valid_result(
            pre_mortem={"actualized_risks": [], "implementation_adjustments": []}
        )
        result = check_result(raw, make_context())
        self.assertEqual(result["status"], "FAILURE")
        self.assertIn("未知フィールド", result["error"])
        self.assertIn("pre_mortem", result["error"])

    def test_missing_field_is_violation(self):
        raw = valid_result()
        del raw["notes"]
        result = check_result(raw, make_context())
        self.assertEqual(result["status"], "FAILURE")
        self.assertIn("必須フィールド", result["error"])

    def test_non_object_is_violation(self):
        for raw in (None, [], "text", 3):
            result = check_result(raw, make_context())
            self.assertEqual(result["status"], "FAILURE", raw)
            self.assertIn("object である必要", result["error"])


class InspectTest(unittest.TestCase):
    def inspect(self, raw, build="required", tests="required"):
        return inspect_result(raw, "TASK-001", build, tests)

    def test_valid_result_passes(self):
        normalized, errors = self.inspect(valid_result())
        self.assertEqual(errors, [])
        self.assertEqual(normalized, valid_result())

    def test_normalizes_whitespace(self):
        raw = valid_result(files_modified=[" src/foo.py "], summary=" foo を実装 ")
        normalized, errors = self.inspect(raw)
        self.assertEqual(errors, [])
        self.assertEqual(normalized["files_modified"], ["src/foo.py"])
        self.assertEqual(normalized["summary"], "foo を実装")

    def test_task_id_must_match(self):
        _, errors = self.inspect(valid_result(task_id="TASK-999"))
        self.assertTrue(any("一致しません" in e for e in errors))

    def test_status_must_be_enum(self):
        _, errors = self.inspect(valid_result(status="DONE"))
        self.assertIn("status は SUCCESS / FAILURE のいずれかです", errors)
        _, errors = self.inspect(valid_result(status=[]))
        self.assertIn("status は SUCCESS / FAILURE のいずれかです", errors)

    def test_success_requires_null_error(self):
        _, errors = self.inspect(valid_result(error="x"))
        self.assertIn("error は SUCCESS 時は null です", errors)

    def test_failure_requires_error_text(self):
        _, errors = self.inspect(valid_result(status="FAILURE", error=None))
        self.assertTrue(any("error は空でない文字列" in e for e in errors))

    def test_summary_limited_to_two_lines(self):
        _, errors = self.inspect(valid_result(summary="a\nb\nc"))
        self.assertIn("summary は 1〜2 行である必要があります", errors)

    def test_paths_must_be_relative_unique(self):
        raw = valid_result(files_modified=["/abs.py", "../up.py", "a.py", "a.py"])
        _, errors = self.inspect(raw)
        self.assertEqual(sum("プロジェクトルート相対パス" in e for e in errors), 2)
        self.assertTrue(any("重複" in e for e in errors))

    def test_nul_in_path(self):
        _, errors = self.inspect(valid_result(files_modified=["a\0b"]))
        self.assertTrue(any("NUL" in e for e in errors))

    def test_verification_value_domain_excludes_optional(self):
        raw = valid_result()
        raw["verification"]["tests"] = "optional"
        raw["verification"]["tests_reason"] = "任意"
        _, errors = self.inspect(raw)
        self.assertTrue(any("verification.tests は" in e for e in errors))

    def test_unhashable_verification_values(self):
        raw = valid_result()
        raw["verification"]["build"] = []
        raw["verification"]["tests"] = {}
        _, errors = self.inspect(raw)
        self.assertTrue(any("verification.build は" in e for e in errors))
        self.assertTrue(any("verification.tests は" in e for e in errors))

    def test_reason_must_match_state(self):
        raw = valid_result()
        raw["verification"]["tests"] = "skipped"
        raw["verification"]["tests_reason"] = None
        _, errors = self.inspect(raw, tests="skipped")
        self.assertTrue(any("tests_reason は空でない文字列" in e for e in errors))
        raw = valid_result()
        raw["verification"]["build_reason"] = "余計"
        _, errors = self.inspect(raw)
        self.assertIn("verification.build_reason は success 時は null です", errors)

    def test_success_rejects_failed_verification(self):
        raw = valid_result()
        raw["verification"]["tests"] = "failed"
        raw["verification"]["tests_reason"] = "落ちた"
        _, errors = self.inspect(raw, tests="optional")
        self.assertIn(
            "status が SUCCESS の場合、verification に failed を含められません", errors
        )

    def test_required_must_be_success(self):
        raw = valid_result()
        raw["verification"]["build"] = "skipped"
        raw["verification"]["build_reason"] = "未実行"
        _, errors = self.inspect(raw)
        self.assertIn(
            "必須の build 検証は SUCCESS 時に success である必要があります", errors
        )
        raw = valid_result()
        raw["verification"]["tests"] = "skipped"
        raw["verification"]["tests_reason"] = "未実行"
        _, errors = self.inspect(raw)
        self.assertIn(
            "必須の tests 検証は SUCCESS 時に success である必要があります", errors
        )

    def test_skipped_plan_must_be_skipped(self):
        _, errors = self.inspect(valid_result(), build="skipped", tests="skipped")
        self.assertIn(
            "スキップ指定の build 検証は skipped である必要があります", errors
        )
        self.assertIn(
            "スキップ指定の tests 検証は skipped である必要があります", errors
        )

    def test_skipped_plan_passes_when_skipped(self):
        raw = valid_result()
        raw["verification"] = {
            "build": "skipped",
            "build_reason": "skip",
            "tests": "skipped",
            "tests_reason": "skip",
        }
        _, errors = self.inspect(raw, build="skipped", tests="skipped")
        self.assertEqual(errors, [])

    def test_failure_status_does_not_require_plan_conformance(self):
        raw = valid_result(status="FAILURE", error="実装失敗")
        raw["verification"] = {
            "build": "failed",
            "build_reason": "エラー",
            "tests": "skipped",
            "tests_reason": "ビルド失敗のため未実行",
        }
        _, errors = self.inspect(raw)
        self.assertEqual(errors, [])


class FailureReplacementTest(unittest.TestCase):
    def test_replacement_has_same_shape_as_success(self):
        ok = check_result(valid_result(), make_context())
        ng = check_result(valid_result(summary=""), make_context())
        self.assertEqual(set(ok), set(ng))
        self.assertEqual(set(ok["verification"]), set(ng["verification"]))
        self.assertEqual(set(ng), set(TASK_RESULT_FIELDS))

    def test_replacement_is_failure_with_reason(self):
        ng = check_result(valid_result(status="DONE"), make_context())
        self.assertEqual(ng["status"], "FAILURE")
        self.assertEqual(ng["task_id"], "TASK-001")
        self.assertEqual(ng["files_modified"], [])
        self.assertIn("status は SUCCESS / FAILURE", ng["error"])
        self.assertTrue(ng["notes"])

    def test_replacement_passes_inspection_itself(self):
        context = make_context(build="skipped", tests="optional")
        ng = check_result(None, context)
        normalized, errors = inspect_result(ng, "TASK-001", "skipped", "optional")
        self.assertEqual(errors, [])
        self.assertEqual(normalized, ng)

    def test_replacement_verification_follows_plan(self):
        ng = check_result(None, make_context(build="skipped", tests="required"))
        self.assertEqual(ng["verification"]["build"], "skipped")
        self.assertEqual(ng["verification"]["build_reason"], "build_check が skip")
        self.assertEqual(ng["verification"]["tests"], "failed")
        self.assertTrue(ng["verification"]["tests_reason"])

    def test_success_is_never_returned_for_violation(self):
        violations = [
            valid_result(task_id="OTHER"),
            valid_result(error="x"),
            valid_result(files_modified=["/abs"]),
            valid_result(extra=1),
        ]
        for raw in violations:
            self.assertEqual(check_result(raw, make_context())["status"], "FAILURE")


class ExpectationTest(unittest.TestCase):
    def test_reads_expectation_from_context(self):
        self.assertEqual(
            load_expectation(make_context(build="skipped", tests="optional")),
            ("TASK-001", "skipped", "optional", "build_check が skip", "理由"),
        )

    def test_invalid_context_raises(self):
        bad_contexts = [
            [],
            make_context(task_id=""),
            make_context(verification=None),
            make_context(build="optional"),
            make_context(tests="success"),
        ]
        for context in bad_contexts:
            with self.assertRaises(ContextError):
                load_expectation(context)


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".temp" / "forge" / "start-implement").mkdir(parents=True)
        self.context_dir = (
            self.root / "docs" / "tasks"
        )  # 計画書 docs/x_plan.json と同じディレクトリ
        self.context_dir.mkdir(parents=True)

    def write_context(self, context, context_id="TASK-001-abcd1234"):
        (self.context_dir / f"{context_id}.json").write_text(
            json.dumps(context), encoding="utf-8"
        )
        return context_id

    def run_cli(
        self,
        payload,
        context_id="TASK-001-abcd1234",
        input_file=".temp/forge/start-implement/r.json",
    ):
        if payload is not None:
            (self.root / input_file).write_text(payload, encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--project-root",
                str(self.root),
                "--plan-path",
                "docs/x_plan.json",
                "--context-id",
                context_id,
                "--input-file",
                input_file,
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=self.root,
        )
        return completed

    def test_valid_result_exit_0_and_input_consumed(self):
        self.write_context(make_context())
        completed = self.run_cli(json.dumps(valid_result()))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), valid_result())
        self.assertFalse((self.root / ".temp/forge/start-implement/r.json").exists())

    def test_expectations_come_from_context_not_arguments(self):
        self.write_context(make_context(build="skipped", tests="skipped"))
        completed = self.run_cli(json.dumps(valid_result()))
        self.assertEqual(completed.returncode, 0)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "FAILURE")
        self.assertIn("スキップ指定", result["error"])

    def test_pre_mortem_result_becomes_failure(self):
        self.write_context(make_context())
        raw = valid_result(
            pre_mortem={"actualized_risks": [], "implementation_adjustments": []}
        )
        completed = self.run_cli(json.dumps(raw))
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout)["status"], "FAILURE")

    def test_not_json_becomes_failure_and_consumed(self):
        self.write_context(make_context())
        completed = self.run_cli("not-json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "FAILURE")
        self.assertEqual(result["task_id"], "TASK-001")
        self.assertIn("JSON", result["error"])
        self.assertFalse((self.root / ".temp/forge/start-implement/r.json").exists())

    def test_empty_result_becomes_failure(self):
        self.write_context(make_context())
        completed = self.run_cli("")
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout)["status"], "FAILURE")

    def test_missing_result_file_is_entry_error_not_task_failure(self):
        """入力ファイルの不在は呼び出し側の手違いであり、タスクの FAILURE に置き換えない。"""
        self.write_context(make_context())
        completed = self.run_cli(None)
        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertNotIn("status", payload)
        self.assertTrue(any("存在しません" in e for e in payload["errors"]), payload)

    def test_missing_context_exit_1_with_errors(self):
        completed = self.run_cli(
            json.dumps(valid_result()), context_id="TASK-001-00000000"
        )
        self.assertEqual(completed.returncode, 1)
        self.assertTrue(json.loads(completed.stdout)["errors"])
        self.assertFalse((self.root / ".temp/forge/start-implement/r.json").exists())

    def test_invalid_context_exit_1(self):
        self.write_context(make_context(build="optional"))
        completed = self.run_cli(json.dumps(valid_result()))
        self.assertEqual(completed.returncode, 1)
        self.assertTrue(json.loads(completed.stdout)["errors"])

    def test_invalid_input_path_exit_1(self):
        self.write_context(make_context())
        completed = self.run_cli(None, input_file="elsewhere/r.json")
        self.assertEqual(completed.returncode, 1)
        self.assertTrue(json.loads(completed.stdout)["errors"])

    def test_context_is_not_deleted(self):
        context_id = self.write_context(make_context())
        self.run_cli(json.dumps(valid_result()))
        self.assertTrue((self.context_dir / f"{context_id}.json").exists())

    def test_bad_arguments_exit_2(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)

    def test_old_arguments_are_not_accepted(self):
        self.write_context(make_context())
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--project-root",
                str(self.root),
                "--plan-path",
                "docs/x_plan.json",
                "--context-id",
                "TASK-001-abcd1234",
                "--input-file",
                ".temp/forge/start-implement/r.json",
                "--expected-build",
                "required",
            ],
            text=True,
            capture_output=True,
            check=False,
            cwd=self.root,
        )
        self.assertEqual(completed.returncode, 2)


class RemovedFilesTest(unittest.TestCase):
    def test_second_path_and_template_are_gone(self):
        base = REPO_ROOT / "plugins" / "forge" / "skills" / "start-implement"
        self.assertFalse((base / "scripts" / "validate_executor_result.py").exists())
        self.assertFalse((base / "templates" / "executor_result.json").exists())
        self.assertFalse(
            Path(__file__).with_name("test_validate_executor_result.py").exists()
        )


if __name__ == "__main__":
    unittest.main()
