#!/usr/bin/env python3
"""build_task_context.py（文脈作成 CX-01・CX-03）の契約テスト。

- 作る: TaskContext の形で、計画書と同じディレクトリの `tasks/{context_id}.json` へ公開する
- 拒否: 単一行でない値・理由の欠落・RequiredReading の形・RD-01 のパスの漏れや重複・
  実在しないパス・判定できない文書は、書かずに拒否する
- 公開は 1 回で上書きせず、識別値を再利用しない
- 削除: 残さず、既に無くても成功する
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "forge" / "skills" / "start-implement" / "scripts"
SCRIPT = SCRIPTS_DIR / "build_task_context.py"

sys.path.insert(0, str(SCRIPTS_DIR))
import build_task_context as btc  # noqa: E402
from build_task_context import (  # noqa: E402
    CANDIDATE_TEMPLATE,
    build_task_context,
    validate_candidate,
)


PARALLEL_FRONTMATTER = ["feature_type: temporary-feature"]
REQ = "docs/requirements/REQ-001.md"
DES = "docs/design/DES-001.md"
STRATEGY = "docs/plan/foo_strategy.md"
RULE = "docs/rules/implementation_guidelines.md"
CODE = "src/foo.py"


def valid_candidate(**overrides):
    candidate = {
        "task_id": "TASK-001",
        "scope_in": "fm_to_pending.py の新規作成とテストまで",
        "scope_out": [
            {
                "item": "_meta.extracted_by の追加",
                "owner_task_id": "TASK-011",
                "reason": "転記側だけ先に書くと読む側が存在しない死にフィールドになるため分離",
            }
        ],
        "required_reading": {
            "design_docs": [DES],
            "requirement_docs": [REQ],
            "strategy_doc": STRATEGY,
            "rule_docs": [RULE],
            "reference_code": [CODE],
            "additional": [],
        },
        "collected_paths": [DES, REQ, STRATEGY, RULE, CODE],
        "implementation_instructions": "fm_to_pending.py を新規作成し、\n既存パターンに倣う",
        "verification": {"tests": "required", "tests_reason": None},
    }
    candidate.update(overrides)
    return candidate


def valid_plan_task(task_id="TASK-001", **overrides):
    task = {
        "task_id": task_id,
        "title": "fm_to_pending の実装",
        "priority": 70,
        "status": "in_progress",
        "design_id": "DES-001",
        "depends_on": [],
        "group_id": None,
        "build_check": "per_task",
        "description": ["fm_to_pending.py を新規作成"],
        "acceptance_criteria": None,
        "required_reading": [],
    }
    task.update(overrides)
    return task


def write_file(root, rel, frontmatter=None, closed=True):
    """frontmatter（`---` 行を含まない行の配列）を持つ Markdown 文書を作る。"""
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "# 文書\n\n本文\n"
    if frontmatter is None:
        path.write_text(body, encoding="utf-8")
        return rel
    block = "---\n" + "".join(f"{line}\n" for line in frontmatter)
    if closed:
        block += "---\n"
    path.write_text(block + "\n" + body, encoding="utf-8")
    return rel


class ProjectCase(unittest.TestCase):
    """一時ディレクトリをプロジェクトルートにし、必読文書と計画書を実体として作る。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)
        self.plan_path = self.root / "docs" / "plan" / "foo_plan.json"
        self.write_plan([valid_plan_task()])
        self.make_docs()

    def write_plan(self, tasks):
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(
            json.dumps({"tasks": tasks}, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def make_docs(self, requirement=None, design=None):
        write_file(self.root, REQ, requirement)
        write_file(self.root, DES, design)
        for rel in (STRATEGY, RULE, CODE):
            write_file(self.root, rel)

    def build(self, candidate=None, task_id="TASK-001"):
        return build_task_context(
            self.root,
            str(self.plan_path),
            task_id,
            valid_candidate() if candidate is None else candidate,
        )

    def contexts(self, plan_path=None):
        directory = Path(plan_path or self.plan_path).parent / "tasks"
        return sorted(directory.glob("*")) if directory.is_dir() else []


class TemplateTest(unittest.TestCase):
    def test_template_matches_candidate_fields(self):
        self.assertEqual(set(CANDIDATE_TEMPLATE), set(valid_candidate()))
        self.assertEqual(
            set(CANDIDATE_TEMPLATE["required_reading"]),
            set(valid_candidate()["required_reading"]),
        )

    def test_template_verification_has_only_tests_and_reason(self):
        """build は計画書の build_check から script が決める。候補は持たない。"""
        self.assertEqual(
            set(CANDIDATE_TEMPLATE["verification"]), {"tests", "tests_reason"}
        )


class ValidateCandidateTest(unittest.TestCase):
    def assert_rejected(self, raw, fragment):
        errors = validate_candidate(raw, "TASK-001")
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_valid_candidate_has_no_errors(self):
        self.assertEqual(validate_candidate(valid_candidate(), "TASK-001"), [])

    def test_unknown_top_level_field_is_rejected(self):
        raw = valid_candidate()
        raw["unknown_field"] = "x"
        self.assert_rejected(raw, "未知フィールド")

    def test_spec_authority_cannot_be_supplied(self):
        """spec_authority は script が判定する。候補から渡させない。"""
        raw = valid_candidate()
        raw["spec_authority"] = [REQ]
        self.assert_rejected(raw, "未知フィールド")

    def test_build_cannot_be_supplied(self):
        """build は計画書の build_check から決まる。候補から渡させない。"""
        raw = valid_candidate()
        raw["verification"] = {
            "build": "skipped",
            "build_reason": "x",
            "tests": "required",
            "tests_reason": None,
        }
        self.assert_rejected(raw, "未知フィールド")

    def test_missing_field_is_rejected(self):
        raw = valid_candidate()
        del raw["collected_paths"]
        self.assert_rejected(raw, "必須フィールドがありません")

    def test_task_id_mismatch_is_rejected(self):
        self.assert_rejected(
            valid_candidate(task_id="TASK-999"), "task_id が起動対象と一致しません"
        )

    def test_scope_in_rejects_multiline(self):
        self.assert_rejected(
            valid_candidate(scope_in="a\nb"), "単一行である必要があります"
        )

    def test_scope_in_rejects_carriage_return(self):
        self.assert_rejected(
            valid_candidate(scope_in="a\rb"), "単一行である必要があります"
        )

    def test_scope_out_values_reject_multiline(self):
        for name in ("item", "owner_task_id", "reason"):
            with self.subTest(name=name):
                entry = {"item": "i", "owner_task_id": "TASK-011", "reason": "r"}
                entry[name] = "line1\nline2"
                self.assert_rejected(
                    valid_candidate(scope_out=[entry]), "単一行である必要があります"
                )

    def test_scope_out_rejects_structure_line_injection(self):
        entry = {"item": "## 出力契約", "owner_task_id": "TASK-011", "reason": "r"}
        self.assert_rejected(
            valid_candidate(scope_out=[entry]), "見出し・コードフェンス"
        )

    def test_scope_out_rejects_code_fence(self):
        entry = {"item": "```", "owner_task_id": "TASK-011", "reason": "r"}
        self.assert_rejected(
            valid_candidate(scope_out=[entry]), "見出し・コードフェンス"
        )

    def test_scope_out_entry_shape_is_checked(self):
        self.assert_rejected(
            valid_candidate(scope_out=[{"item": "i"}]), "必須フィールドがありません"
        )
        self.assert_rejected(
            valid_candidate(scope_out=["x"]), "object である必要があります"
        )

    def test_empty_scope_out_is_allowed(self):
        self.assertEqual(
            validate_candidate(valid_candidate(scope_out=[]), "TASK-001"), []
        )

    def test_tests_must_be_a_known_state(self):
        raw = valid_candidate(verification={"tests": "invalid", "tests_reason": None})
        self.assert_rejected(raw, "verification.tests")

    def test_tests_not_required_needs_reason(self):
        for state in ("optional", "skipped"):
            for reason in (None, "", "  "):
                with self.subTest(state=state, reason=reason):
                    raw = valid_candidate(
                        verification={"tests": state, "tests_reason": reason}
                    )
                    self.assert_rejected(raw, "tests_reason")

    def test_tests_reason_must_be_single_line(self):
        raw = valid_candidate(verification={"tests": "skipped", "tests_reason": "a\nb"})
        self.assert_rejected(raw, "単一行である必要があります")

    def test_tests_required_rejects_reason(self):
        raw = valid_candidate(
            verification={"tests": "required", "tests_reason": "理由"}
        )
        self.assert_rejected(raw, "required のとき null")

    def test_tests_not_required_with_reason_is_accepted(self):
        raw = valid_candidate(
            verification={"tests": "skipped", "tests_reason": "対象外のため"}
        )
        self.assertEqual(validate_candidate(raw, "TASK-001"), [])

    def test_required_reading_must_be_an_object(self):
        self.assert_rejected(
            valid_candidate(required_reading=[REQ]), "required_reading は object"
        )

    def test_required_reading_rejects_old_plan_shape(self):
        """計画書の required_reading（パス文字列の配列）は RequiredReading の形ではない。"""
        self.assert_rejected(
            valid_candidate(required_reading=[DES, REQ]), "object である必要があります"
        )

    def test_required_reading_field_set_is_checked(self):
        reading = valid_candidate()["required_reading"]
        del reading["additional"]
        reading["extra"] = []
        raw = valid_candidate(required_reading=reading)
        self.assert_rejected(raw, "必須フィールドがありません")
        self.assert_rejected(raw, "未知フィールド")

    def test_required_reading_kinds_must_be_string_arrays(self):
        reading = valid_candidate()["required_reading"]
        reading["design_docs"] = DES
        self.assert_rejected(
            valid_candidate(required_reading=reading), "配列である必要があります"
        )
        reading = valid_candidate()["required_reading"]
        reading["rule_docs"] = [RULE, ""]
        self.assert_rejected(
            valid_candidate(required_reading=reading), "空でない文字列"
        )

    def test_strategy_doc_must_be_string_or_null(self):
        reading = valid_candidate()["required_reading"]
        reading["strategy_doc"] = [STRATEGY]
        self.assert_rejected(valid_candidate(required_reading=reading), "strategy_doc")
        reading["strategy_doc"] = None
        raw = valid_candidate(
            required_reading=reading, collected_paths=[DES, REQ, RULE, CODE]
        )
        self.assertEqual(validate_candidate(raw, "TASK-001"), [])

    def test_implementation_instructions_must_not_be_empty(self):
        self.assert_rejected(
            valid_candidate(implementation_instructions=" "),
            "implementation_instructions",
        )


class CreateContextTest(ProjectCase):
    def test_builds_task_context_shape(self):
        self.write_plan(
            [
                valid_plan_task(
                    acceptance_criteria="基準", required_reading=["docs/x.md"]
                )
            ]
        )
        context, errors = self.build()
        self.assertEqual(errors, [])
        # Task の全フィールド + 加えた 6 つ（required_reading は型が置き換わる）
        self.assertEqual(
            list(context),
            [
                "task_id",
                "title",
                "priority",
                "status",
                "design_id",
                "depends_on",
                "group_id",
                "build_check",
                "description",
                "acceptance_criteria",
                "required_reading",
                "scope_in",
                "scope_out",
                "implementation_instructions",
                "verification",
                "spec_authority",
            ],
        )
        self.assertEqual(context["title"], "fm_to_pending の実装")
        self.assertEqual(context["acceptance_criteria"], "基準")
        self.assertEqual(
            context["required_reading"],
            {
                "design_docs": [DES],
                "requirement_docs": [REQ],
                "strategy_doc": STRATEGY,
                "rule_docs": [RULE],
                "reference_code": [CODE],
                "additional": [],
            },
        )
        self.assertNotIn("collected_paths", context)

    def test_values_are_not_transformed(self):
        """渡された値は、空白・改行を含めて、そのまま置く。"""
        candidate = valid_candidate(
            scope_in="  前後に空白がある  ",
            implementation_instructions="1 行目\n\n  2 行目 `code`\n",
        )
        context, errors = self.build(candidate)
        self.assertEqual(errors, [])
        self.assertEqual(context["scope_in"], "  前後に空白がある  ")
        self.assertEqual(
            context["implementation_instructions"], "1 行目\n\n  2 行目 `code`\n"
        )
        self.assertEqual(context["scope_out"], candidate["scope_out"])

    def test_does_not_contain_other_tasks(self):
        self.write_plan(
            [
                valid_plan_task("TASK-001"),
                valid_plan_task("TASK-002", title="別のタスク"),
            ]
        )
        context, errors = self.build()
        self.assertEqual(errors, [])
        self.assertNotIn("別のタスク", json.dumps(context, ensure_ascii=False))

    def test_task_id_not_in_plan_is_rejected(self):
        self.write_plan([valid_plan_task("TASK-002")])
        context, errors = self.build()
        self.assertIsNone(context)
        self.assertTrue(any("見つかりません" in e for e in errors))

    def test_unreadable_plan_is_rejected(self):
        self.plan_path.write_text("{", encoding="utf-8")
        context, errors = self.build()
        self.assertIsNone(context)
        self.assertTrue(any("計画書を読み込めません" in e for e in errors))

    def test_tests_and_reason_are_taken_as_is(self):
        candidate = valid_candidate(
            verification={"tests": "optional", "tests_reason": "任意の理由"}
        )
        context, errors = self.build(candidate)
        self.assertEqual(errors, [])
        self.assertEqual(context["verification"]["tests"], "optional")
        self.assertEqual(context["verification"]["tests_reason"], "任意の理由")


class BuildDecisionTest(ProjectCase):
    """verification.build は、計画書の build_check から script が決める（DES-088 6.2）。"""

    def verification(self, build_check):
        self.write_plan([valid_plan_task(build_check=build_check)])
        context, errors = self.build()
        return context, errors

    def test_per_task_is_required(self):
        context, errors = self.verification("per_task")
        self.assertEqual(errors, [])
        self.assertEqual(context["verification"]["build"], "required")
        self.assertIsNone(context["verification"]["build_reason"])

    def test_on_group_complete_is_required(self):
        context, errors = self.verification("on_group_complete")
        self.assertEqual(errors, [])
        self.assertEqual(context["verification"]["build"], "required")
        self.assertIsNone(context["verification"]["build_reason"])

    def test_skip_is_skipped_with_reason(self):
        context, errors = self.verification("skip")
        self.assertEqual(errors, [])
        self.assertEqual(context["verification"]["build"], "skipped")
        self.assertEqual(
            context["verification"]["build_reason"],
            "計画書の build_check が skip である",
        )

    def test_unknown_build_check_is_rejected(self):
        context, errors = self.verification("sometimes")
        self.assertIsNone(context)
        self.assertTrue(any("build_check は" in e for e in errors))

    def test_missing_build_check_is_rejected(self):
        task = valid_plan_task()
        del task["build_check"]
        self.write_plan([task])
        context, errors = self.build()
        self.assertIsNone(context)
        self.assertTrue(any("build_check は" in e for e in errors))

    def test_unhashable_build_check_is_rejected_with_errors(self):
        for value in (["per_task"], {"k": "v"}):
            with self.subTest(value=value):
                context, errors = self.verification(value)
                self.assertIsNone(context)
                self.assertTrue(any("build_check は" in e for e in errors))

    def test_task_missing_required_field_is_rejected(self):
        task = valid_plan_task()
        del task["title"]
        self.write_plan([task])
        context, errors = self.build()
        self.assertIsNone(context)
        self.assertTrue(any("必須フィールドがありません" in e for e in errors))

    def test_task_with_unknown_field_is_rejected(self):
        self.write_plan([valid_plan_task(extra="x")])
        context, errors = self.build()
        self.assertIsNone(context)
        self.assertTrue(any("未知フィールドがあります" in e for e in errors))

    def test_verification_key_order(self):
        context, _ = self.verification("per_task")
        self.assertEqual(
            list(context["verification"]),
            ["build", "build_reason", "tests", "tests_reason"],
        )


class ClassificationTest(ProjectCase):
    """RD-01 のパスが、漏れなく、ちょうど 1 つの種別に入っていること。"""

    def reject(self, candidate, fragment):
        context, errors = self.build(candidate)
        self.assertIsNone(context)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_path_in_no_kind_is_rejected(self):
        extra = write_file(self.root, "docs/extra.md")
        candidate = valid_candidate()
        candidate["collected_paths"] = candidate["collected_paths"] + [extra]
        self.reject(candidate, "どの種別にもありません")

    def test_path_in_two_kinds_is_rejected(self):
        candidate = valid_candidate()
        candidate["required_reading"]["additional"] = [RULE]
        self.reject(candidate, "複数の種別にあります")

    def test_strategy_doc_counts_as_a_kind(self):
        candidate = valid_candidate()
        candidate["required_reading"]["rule_docs"] = [STRATEGY, RULE]
        self.reject(candidate, "複数の種別にあります")

    def test_strategy_doc_alone_is_accepted(self):
        context, errors = self.build()
        self.assertEqual(errors, [])
        self.assertEqual(context["required_reading"]["strategy_doc"], STRATEGY)

    def test_same_path_twice_in_one_kind_is_one_kind(self):
        candidate = valid_candidate()
        candidate["required_reading"]["rule_docs"] = [RULE, RULE]
        context, errors = self.build(candidate)
        self.assertEqual(errors, [])
        self.assertEqual(context["required_reading"]["rule_docs"], [RULE, RULE])

    def test_collected_paths_duplicates_are_accepted(self):
        candidate = valid_candidate()
        candidate["collected_paths"] = candidate["collected_paths"] + [RULE]
        context, errors = self.build(candidate)
        self.assertEqual(errors, [])

    def test_paths_are_compared_as_given(self):
        """正規化しない。`./` 付きは別のパスとして、どの種別にもないと拒否する。"""
        candidate = valid_candidate()
        candidate["collected_paths"] = candidate["collected_paths"] + ["./" + RULE]
        self.reject(candidate, "どの種別にもありません")

    def test_empty_collected_paths_is_accepted(self):
        context, errors = self.build(valid_candidate(collected_paths=[]))
        self.assertEqual(errors, [])


class PathExistenceTest(ProjectCase):
    def test_nonexistent_path_is_rejected(self):
        candidate = valid_candidate()
        candidate["required_reading"]["reference_code"] = ["src/missing.py"]
        candidate["collected_paths"] = [DES, REQ, STRATEGY, RULE, "src/missing.py"]
        context, errors = self.build(candidate)
        self.assertIsNone(context)
        self.assertTrue(
            any(
                "実在しないパスがあります" in e and "src/missing.py" in e
                for e in errors
            ),
            errors,
        )

    def test_nonexistent_strategy_doc_is_rejected(self):
        candidate = valid_candidate()
        candidate["required_reading"]["strategy_doc"] = "docs/plan/missing_strategy.md"
        candidate["collected_paths"] = [
            DES,
            REQ,
            "docs/plan/missing_strategy.md",
            RULE,
            CODE,
        ]
        context, errors = self.build(candidate)
        self.assertIsNone(context)
        self.assertTrue(any("missing_strategy.md" in e for e in errors), errors)

    def test_paths_resolve_from_project_root_not_cwd(self):
        """プロジェクトルートからの相対パスで実在を確かめる（cwd に依らない）。"""
        context, errors = self.build()
        self.assertEqual(errors, [])


class SpecAuthorityTest(ProjectCase):
    """spec_authority は、並行文書判定の結果をそのまま置く。判定できない文書があれば拒否する。"""

    def authority(self, requirement=None, design=None, candidate=None):
        self.make_docs(requirement, design)
        return self.build(candidate)

    def test_empty_when_no_document_is_in_parallel_state(self):
        context, errors = self.authority()
        self.assertEqual(errors, [])
        self.assertEqual(context["spec_authority"], [])

    def test_frontmatter_without_feature_type_is_not_parallel(self):
        context, errors = self.authority(
            ["doc_status: draft"], ["doc_status: not_implemented"]
        )
        self.assertEqual(errors, [])
        self.assertEqual(context["spec_authority"], [])

    def test_requirement_in_parallel_state(self):
        context, errors = self.authority(requirement=PARALLEL_FRONTMATTER)
        self.assertEqual(errors, [])
        self.assertEqual(context["spec_authority"], [REQ])

    def test_design_in_parallel_state(self):
        context, errors = self.authority(design=PARALLEL_FRONTMATTER)
        self.assertEqual(errors, [])
        self.assertEqual(context["spec_authority"], [DES])

    def test_both_keep_requirement_first(self):
        context, errors = self.authority(PARALLEL_FRONTMATTER, PARALLEL_FRONTMATTER)
        self.assertEqual(errors, [])
        self.assertEqual(context["spec_authority"], [REQ, DES])

    def test_key_order_does_not_change_the_result(self):
        feature_note = ["feature_note:", "  - この文書が、現在の仕様である。"]
        for frontmatter in (
            ["feature_type: temporary-feature"] + feature_note,
            ["doc_status: draft", "feature_type: temporary-feature"] + feature_note,
            feature_note + ["feature_type: temporary-feature"],
        ):
            with self.subTest(frontmatter=frontmatter):
                context, errors = self.authority(requirement=frontmatter)
                self.assertEqual(errors, [])
                self.assertEqual(context["spec_authority"], [REQ])

    def test_indented_feature_type_is_not_a_top_level_key(self):
        context, errors = self.authority(
            requirement=[
                "feature_note:",
                "  - feature_type: temporary-feature を付与すること。",
            ]
        )
        self.assertEqual(errors, [])
        self.assertEqual(context["spec_authority"], [])

    def test_fixed_kinds_are_not_classified(self):
        """戦略書・ルール・コードは種別が固定で識別子を持たないため、判定の対象にしない。"""
        for rel in (STRATEGY, RULE, CODE):
            write_file(self.root, rel, PARALLEL_FRONTMATTER)
        context, errors = self.build()
        self.assertEqual(errors, [])
        self.assertEqual(context["spec_authority"], [])

    def test_fixed_kind_with_broken_frontmatter_is_not_classified(self):
        write_file(self.root, RULE, PARALLEL_FRONTMATTER, closed=False)
        context, errors = self.build()
        self.assertEqual(errors, [])

    def test_additional_is_classified_because_it_is_a_catch_all(self):
        extra = write_file(self.root, "docs/specs/extra_req.md", PARALLEL_FRONTMATTER)
        candidate = valid_candidate()
        candidate["required_reading"]["additional"] = [extra]
        candidate["collected_paths"] = candidate["collected_paths"] + [extra]
        context, errors = self.build(candidate)
        self.assertEqual(errors, [])
        self.assertEqual(context["spec_authority"], [extra])

    def test_same_path_in_two_sources_appears_once(self):
        candidate = valid_candidate()
        candidate["required_reading"]["additional"] = [REQ]
        context, errors = self.authority(
            requirement=PARALLEL_FRONTMATTER, candidate=candidate
        )
        # 2 つの種別に入るため分類で拒否される。判定の重複は、分類の拒否と別に確かめる
        self.assertIsNone(context)
        authority, authority_errors = btc._resolve_spec_authority(
            self.root, candidate["required_reading"], set()
        )
        self.assertEqual(authority_errors, [])
        self.assertEqual(authority, [REQ])

    def test_unterminated_frontmatter_is_rejected(self):
        write_file(self.root, REQ, PARALLEL_FRONTMATTER, closed=False)
        context, errors = self.build()
        self.assertIsNone(context)
        self.assertTrue(any("終端 '---' がありません" in e for e in errors), errors)

    def test_duplicate_feature_type_is_rejected(self):
        context, errors = self.authority(
            requirement=[
                "feature_type: temporary-feature",
                "feature_type: temporary-feature",
            ]
        )
        self.assertIsNone(context)
        self.assertTrue(any("一意に決められません" in e for e in errors), errors)

    def test_undefined_feature_type_value_is_rejected(self):
        context, errors = self.authority(requirement=["feature_type: permanent"])
        self.assertIsNone(context)
        self.assertTrue(any("未定義です" in e for e in errors), errors)

    def test_empty_feature_type_value_is_rejected(self):
        context, errors = self.authority(requirement=["feature_type:"])
        self.assertIsNone(context)
        self.assertTrue(any("未定義です" in e for e in errors), errors)

    def test_non_utf8_document_is_rejected_instead_of_raising(self):
        binary = self.root / "docs" / "specs" / "extra.md"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"\xff\xfe\x00---\n")
        candidate = valid_candidate()
        candidate["required_reading"]["additional"] = ["docs/specs/extra.md"]
        candidate["collected_paths"] = candidate["collected_paths"] + [
            "docs/specs/extra.md"
        ]
        context, errors = self.build(candidate)
        self.assertIsNone(context)
        self.assertTrue(any("UTF-8 として読めません" in e for e in errors), errors)

    def test_nonexistent_document_is_reported_as_missing_not_as_not_parallel(self):
        (self.root / REQ).unlink()
        context, errors = self.build()
        self.assertIsNone(context)
        self.assertTrue(any("実在しないパスがあります" in e for e in errors), errors)


class PublishContextTest(ProjectCase):
    def test_publishes_at_context_dir_with_context_id(self):
        context, _ = self.build()
        context_id = btc.publish_context(
            self.root, str(self.plan_path), "TASK-001", context
        )
        self.assertRegex(context_id, r"^TASK-001-[0-9a-f]{8}$")
        path = self.plan_path.parent / "tasks" / f"{context_id}.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), context)

    def test_leaves_only_the_published_file(self):
        """下書き（一時ファイル）を残さない。"""
        context, _ = self.build()
        context_id = btc.publish_context(
            self.root, str(self.plan_path), "TASK-001", context
        )
        self.assertEqual([p.name for p in self.contexts()], [f"{context_id}.json"])

    def test_does_not_overwrite_and_does_not_reuse_an_existing_id(self):
        directory = self.plan_path.parent / "tasks"
        directory.mkdir(parents=True)
        existing = directory / "TASK-001-aaaaaaaa.json"
        existing.write_text('{"keep": true}\n', encoding="utf-8")
        context, _ = self.build()
        with mock.patch.object(
            btc,
            "_new_context_id",
            side_effect=["TASK-001-aaaaaaaa", "TASK-001-bbbbbbbb"],
        ):
            context_id = btc.publish_context(
                self.root, str(self.plan_path), "TASK-001", context
            )
        self.assertEqual(context_id, "TASK-001-bbbbbbbb")
        self.assertEqual(existing.read_text(encoding="utf-8"), '{"keep": true}\n')
        self.assertTrue((directory / "TASK-001-bbbbbbbb.json").is_file())

    def test_ids_differ_between_publishes(self):
        context, _ = self.build()
        ids = {
            btc.publish_context(self.root, str(self.plan_path), "TASK-001", context)
            for _ in range(20)
        }
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(self.contexts()), 20)

    def test_publish_is_a_single_replace(self):
        """完成前の内容を公開しない: 公開は一時ファイルからの 1 回の置き換えである。"""
        context, _ = self.build()
        calls = []
        real_publish = btc.review_common.publish_json

        def spy(path, payload):
            calls.append(path)
            self.assertFalse(path.exists())
            real_publish(path, payload)
            self.assertTrue(path.exists())

        with mock.patch.object(btc.review_common, "publish_json", side_effect=spy):
            btc.publish_context(self.root, str(self.plan_path), "TASK-001", context)
        self.assertEqual(len(calls), 1)


def run_cli(*args, cwd=REPO_ROOT):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout) if completed.stdout.strip() else None
    return completed.returncode, payload, completed


class CliTest(ProjectCase):
    def setUp(self):
        super().setUp()
        self.temp_dir = REPO_ROOT / ".temp" / "forge" / "start-implement"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.input_path = self.temp_dir / "test_build_task_context_input.json"
        self.addCleanup(lambda: self.input_path.unlink(missing_ok=True))

    def write_input(self, candidate):
        self.input_path.write_text(
            json.dumps(candidate, ensure_ascii=False), encoding="utf-8"
        )
        return str(self.input_path.relative_to(REPO_ROOT))

    def create(self, candidate, plan_path=None, task_id="TASK-001", input_rel=None):
        return run_cli(
            "--create",
            "--project-root",
            str(self.root),
            "--plan-path",
            str(self.plan_path if plan_path is None else plan_path),
            "--task-id",
            task_id,
            "--input-file",
            input_rel or self.write_input(candidate),
        )

    def delete(self, context_id, plan_path=None):
        return run_cli(
            "--delete",
            "--project-root",
            str(self.root),
            "--plan-path",
            str(self.plan_path if plan_path is None else plan_path),
            "--context-id",
            context_id,
        )

    def test_create_writes_context_and_returns_only_the_id(self):
        code, payload, _ = self.create(valid_candidate())
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"context_id"})
        context_id = payload["context_id"]
        self.assertRegex(context_id, r"^TASK-001-[0-9a-f]{8}$")
        path = self.plan_path.parent / "tasks" / f"{context_id}.json"
        written = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(written["task_id"], "TASK-001")
        self.assertEqual(written["verification"]["build"], "required")
        self.assertEqual(written["spec_authority"], [])
        self.assertFalse(self.input_path.exists())

    def test_create_uses_tasks_directory_next_to_the_plan(self):
        """置き場は計画書と同じディレクトリの tasks/（計画書・実装戦略書と同じライフサイクル）。"""
        self.create(valid_candidate())
        self.assertTrue((self.plan_path.parent / "tasks").is_dir())
        self.assertFalse((self.root / ".temp").exists())

    def test_relative_plan_path_is_resolved_against_the_project_root(self):
        code, payload, _ = self.create(
            valid_candidate(), plan_path=self.plan_path.relative_to(self.root)
        )
        self.assertEqual(code, 0, payload)
        self.assertEqual(len(self.contexts()), 1)

    def test_two_creates_get_different_ids_and_files(self):
        _, first, _ = self.create(valid_candidate())
        _, second, _ = self.create(valid_candidate())
        self.assertNotEqual(first["context_id"], second["context_id"])
        self.assertEqual(len(self.contexts()), 2)

    def test_same_task_in_another_plan_goes_to_another_directory(self):
        other = self.root / "docs" / "other" / "bar_plan.json"
        other.parent.mkdir(parents=True)
        other.write_text(self.plan_path.read_text(encoding="utf-8"), encoding="utf-8")
        _, payload, _ = self.create(valid_candidate(), plan_path=other)
        self.assertEqual(len(self.contexts(other)), 1)
        self.assertEqual(self.contexts(), [])

    def test_rejection_writes_nothing_and_deletes_input(self):
        broken = valid_candidate(scope_in="a\nb")
        code, payload, _ = self.create(broken)
        self.assertEqual(code, 1)
        self.assertTrue(any("単一行" in e for e in payload["errors"]))
        self.assertEqual(self.contexts(), [])
        self.assertFalse((self.plan_path.parent / "tasks").exists())
        self.assertFalse(self.input_path.exists())

    def test_errors_are_a_natural_language_array(self):
        code, payload, _ = self.create(
            valid_candidate(scope_in="a\nb", collected_paths="x")
        )
        self.assertEqual(code, 1)
        self.assertIsInstance(payload["errors"], list)
        self.assertGreaterEqual(len(payload["errors"]), 2)
        self.assertEqual(set(payload), {"errors"})

    def test_exit_20_is_not_used(self):
        code, _, _ = self.create(valid_candidate(task_id="TASK-999"))
        self.assertEqual(code, 1)

    def test_input_file_outside_temp_dir_is_rejected_and_kept(self):
        outside = self.root / "outside.json"
        outside.write_text(
            json.dumps(valid_candidate(), ensure_ascii=False), encoding="utf-8"
        )
        code, payload, _ = self.create(None, input_rel=str(outside))
        self.assertEqual(code, 1)
        self.assertTrue(any(".temp/forge/" in e for e in payload["errors"]))
        self.assertTrue(outside.exists())
        self.assertEqual(self.contexts(), [])

    def test_plan_path_outside_project_root_is_rejected_and_input_is_consumed(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        for bad in (
            "",
            "../outside_plan.json",
            str(Path(outside.name) / "x_plan.json"),
        ):
            with self.subTest(plan_path=bad):
                code, payload, _ = self.create(valid_candidate(), plan_path=bad)
                self.assertEqual(code, 1)
                self.assertTrue(
                    any("plan-path" in e for e in payload["errors"]), payload
                )
                self.assertFalse(self.input_path.exists())
        self.assertEqual(list(self.root.rglob("tasks")), [])
        self.assertEqual(list(Path(outside.name).rglob("*")), [])

    def test_invalid_task_id_is_rejected(self):
        code, payload, _ = self.create(valid_candidate(task_id="../x"), task_id="../x")
        self.assertEqual(code, 1)
        self.assertTrue(any("不正" in e for e in payload["errors"]))

    def test_missing_arguments_exit_2(self):
        base = ("--project-root", str(self.root), "--plan-path", str(self.plan_path))
        code, _, _ = run_cli("--create", *base)
        self.assertEqual(code, 2)
        code, _, _ = run_cli("--delete", *base)
        self.assertEqual(code, 2)
        code, _, _ = run_cli(*base)
        self.assertEqual(code, 2)
        code, _, _ = run_cli(
            "--create",
            "--project-root",
            str(self.root),
            "--task-id",
            "TASK-001",
            "--input-file",
            ".temp/forge/x.json",
        )
        self.assertEqual(code, 2)  # --plan-path が無い
        code, _, _ = run_cli(
            "--delete", "--project-root", str(self.root), "--context-id", "x"
        )
        self.assertEqual(code, 2)  # --plan-path が無い

    def test_delete_removes_the_context(self):
        _, payload, _ = self.create(valid_candidate())
        code, out, _ = self.delete(payload["context_id"])
        self.assertEqual((code, out), (0, {}))
        self.assertEqual(self.contexts(), [])

    def test_delete_keeps_other_contexts(self):
        _, first, _ = self.create(valid_candidate())
        _, second, _ = self.create(valid_candidate())
        self.delete(first["context_id"])
        self.assertEqual(
            [p.name for p in self.contexts()], [f"{second['context_id']}.json"]
        )

    def test_delete_succeeds_when_already_absent(self):
        _, payload, _ = self.create(valid_candidate())
        self.delete(payload["context_id"])
        self.assertEqual(self.delete(payload["context_id"])[:2], (0, {}))
        never = self.root / "docs" / "never" / "never_plan.json"
        self.assertEqual(self.delete("TASK-001-00000000", plan_path=never)[:2], (0, {}))

    def test_delete_rejects_ids_outside_the_directory(self):
        victim = self.plan_path.parent / "victim.json"
        victim.write_text("{}", encoding="utf-8")
        for bad in ("..", ".", "../victim", "../../victim", "a/b", "a\\b"):
            with self.subTest(context_id=bad):
                code, payload, _ = self.delete(bad)
                self.assertEqual(code, 1)
                self.assertTrue(any("不正" in e for e in payload["errors"]))
        for bad_plan in ("", "../outside_plan.json"):
            code, payload, _ = self.delete("x", plan_path=bad_plan)
            self.assertEqual(code, 1)
            self.assertTrue(any("plan-path" in e for e in payload["errors"]), payload)
        self.assertTrue(victim.is_file())

    def test_delete_does_not_follow_a_symlink(self):
        target = self.root / "victim.json"
        target.write_text("{}", encoding="utf-8")
        directory = self.plan_path.parent / "tasks"
        directory.mkdir(parents=True)
        (directory / "TASK-001-deadbeef.json").symlink_to(target)
        code, out, _ = self.delete("TASK-001-deadbeef")
        self.assertEqual((code, out), (0, {}))
        self.assertTrue(target.is_file())
        self.assertFalse((directory / "TASK-001-deadbeef.json").exists())


class ContextIdFormatTest(unittest.TestCase):
    def test_context_id_is_task_id_and_eight_hex_digits(self):
        for _ in range(50):
            self.assertRegex(btc._new_context_id("TASK-048"), r"^TASK-048-[0-9a-f]{8}$")

    def test_context_id_matches_documented_pattern(self):
        self.assertTrue(
            re.fullmatch(r"TASK-\d+-[0-9a-f]{8}", btc._new_context_id("TASK-001"))
        )


if __name__ == "__main__":
    unittest.main()
