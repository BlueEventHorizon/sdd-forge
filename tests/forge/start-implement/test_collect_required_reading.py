#!/usr/bin/env python3
"""collect_required_reading.py（必読収集の土台 RD-01）の契約テスト。"""

import importlib.util
import json
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
    / "collect_required_reading.py"
)

_SPEC = importlib.util.spec_from_file_location("collect_required_reading", SCRIPT)
collect_module = importlib.util.module_from_spec(_SPEC)
sys.modules["collect_required_reading"] = collect_module
_SPEC.loader.exec_module(collect_module)

DOC_STRUCTURE = """\
rules:
  root_dirs:
    - docs/rules/
  doc_types_map:
    docs/rules/: rule
  patterns:
    target_glob: "**/*.md"
    exclude: []

specs:
  root_dirs:
    - "docs/specs/**/design/"
    - "docs/specs/**/requirements/"
  doc_types_map:
    "docs/specs/**/design/": design
    "docs/specs/**/requirements/": requirement
  patterns:
    target_glob: "**/*.md"
    exclude: []
"""


def _task(task_id="TASK-001", design_id=None, required_reading=None):
    return {
        "task_id": task_id,
        "title": task_id,
        "priority": 50,
        "status": "pending",
        "design_id": design_id,
        "depends_on": [],
        "group_id": None,
        "build_check": "per_task",
        "description": ["x"],
        "acceptance_criteria": None,
        "required_reading": required_reading if required_reading is not None else [],
    }


class _ProjectCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".doc_structure.yaml").write_text(DOC_STRUCTURE, encoding="utf-8")

    def write(self, rel, text="x\n"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return rel

    def collect(self, task, design_traceability=None):
        plan = {"tasks": [task]}
        if design_traceability is not None:
            plan["design_traceability"] = design_traceability
        return collect_module.collect_required_reading(
            plan, task["task_id"], str(self.root)
        )


def _trace(design_id, requirement_ids):
    return {
        "design_id": design_id,
        "title": design_id,
        "requirement_ids": requirement_ids,
        "task_ids": ["TASK-001"],
    }


class CollectFunctionTest(_ProjectCase):
    def test_required_reading_is_added_as_is(self):
        a = self.write("docs/rules/a.md")
        b = self.write("src/b.py")
        result, errors = self.collect(_task(required_reading=[a, b]))
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [a, b])
        self.assertEqual(result["missing_paths"], [])
        self.assertEqual(result["problems"], [])

    def test_null_design_id_does_not_add_design_doc(self):
        a = self.write("docs/rules/a.md")
        self.write("docs/specs/f/design/DES-001_x.md")
        result, errors = self.collect(_task(design_id=None, required_reading=[a]))
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [a])
        self.assertEqual(result["design_lookup"]["status"], "not_applicable")

    def test_design_doc_is_added_when_design_id_given(self):
        a = self.write("docs/rules/a.md")
        design = self.write("docs/specs/f/design/DES-001_x.md")
        result, errors = self.collect(_task(design_id="DES-001", required_reading=[a]))
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [a, design])
        self.assertEqual(result["design_lookup"]["status"], "found")
        self.assertEqual(result["problems"], [])

    def test_duplicates_are_removed(self):
        a = self.write("docs/rules/a.md")
        design = self.write("docs/specs/f/design/DES-001_x.md")
        result, errors = self.collect(
            _task(design_id="DES-001", required_reading=[a, design, a])
        )
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [a, design])

    def test_design_doc_not_found_is_reported(self):
        a = self.write("docs/rules/a.md")
        result, errors = self.collect(_task(design_id="DES-009", required_reading=[a]))
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [a])
        self.assertEqual(result["design_lookup"]["status"], "not_found")
        self.assertEqual(len(result["problems"]), 1)
        self.assertIn("DES-009", result["problems"][0])

    def test_multiple_design_docs_are_reported(self):
        first = self.write("docs/specs/f/design/DES-002_a.md")
        second = self.write("docs/specs/g/design/DES-002_b.md")
        result, errors = self.collect(_task(design_id="DES-002"))
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [])
        self.assertEqual(result["design_lookup"]["status"], "ambiguous")
        self.assertEqual(
            sorted(result["design_lookup"]["matches"]), sorted([first, second])
        )
        self.assertIn("複数", result["problems"][0])

    def test_requirement_docs_of_the_design_are_added(self):
        a = self.write("docs/rules/a.md")
        design = self.write("docs/specs/f/design/DES-001_x.md")
        req1 = self.write("docs/specs/f/requirements/REQ-001_x.md")
        req2 = self.write("docs/specs/f/requirements/REQ-002_y.md")
        result, errors = self.collect(
            _task(design_id="DES-001", required_reading=[a]),
            design_traceability=[_trace("DES-001", ["REQ-001", "REQ-002"])],
        )
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [a, design, req1, req2])
        self.assertEqual(
            [(r["requirement_id"], r["status"]) for r in result["requirement_lookup"]],
            [("REQ-001", "found"), ("REQ-002", "found")],
        )
        self.assertEqual(result["problems"], [])

    def test_only_the_requirements_of_this_design_are_added(self):
        design = self.write("docs/specs/f/design/DES-001_x.md")
        req1 = self.write("docs/specs/f/requirements/REQ-001_x.md")
        self.write("docs/specs/f/requirements/REQ-002_y.md")
        result, errors = self.collect(
            _task(design_id="DES-001"),
            design_traceability=[
                _trace("DES-001", ["REQ-001"]),
                _trace("DES-002", ["REQ-002"]),
            ],
        )
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [design, req1])

    def test_requirement_doc_already_in_required_reading_is_not_duplicated(self):
        design = self.write("docs/specs/f/design/DES-001_x.md")
        req = self.write("docs/specs/f/requirements/REQ-001_x.md")
        result, errors = self.collect(
            _task(design_id="DES-001", required_reading=[req]),
            design_traceability=[_trace("DES-001", ["REQ-001"])],
        )
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [req, design])

    def test_requirement_doc_not_found_is_reported(self):
        design = self.write("docs/specs/f/design/DES-001_x.md")
        result, errors = self.collect(
            _task(design_id="DES-001"),
            design_traceability=[_trace("DES-001", ["REQ-009"])],
        )
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [design])
        self.assertEqual(result["requirement_lookup"][0]["status"], "not_found")
        self.assertEqual(len(result["problems"]), 1)
        self.assertIn("REQ-009", result["problems"][0])

    def test_multiple_requirement_docs_are_reported(self):
        design = self.write("docs/specs/f/design/DES-001_x.md")
        first = self.write("docs/specs/f/requirements/REQ-001_a.md")
        second = self.write("docs/specs/g/requirements/REQ-001_b.md")
        result, errors = self.collect(
            _task(design_id="DES-001"),
            design_traceability=[_trace("DES-001", ["REQ-001"])],
        )
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [design])
        lookup = result["requirement_lookup"][0]
        self.assertEqual(lookup["status"], "ambiguous")
        self.assertEqual(sorted(lookup["matches"]), sorted([first, second]))
        self.assertIn("複数", result["problems"][0])

    def test_design_without_trace_entry_adds_no_requirement_docs(self):
        design = self.write("docs/specs/f/design/DES-001_x.md")
        self.write("docs/specs/f/requirements/REQ-001_x.md")
        result, errors = self.collect(
            _task(design_id="DES-001"),
            design_traceability=[_trace("DES-002", ["REQ-001"])],
        )
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [design])
        self.assertEqual(result["requirement_lookup"], [])

    def test_null_design_id_adds_no_requirement_docs(self):
        self.write("docs/specs/f/requirements/REQ-001_x.md")
        result, errors = self.collect(
            _task(design_id=None),
            design_traceability=[_trace("DES-001", ["REQ-001"])],
        )
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [])
        self.assertEqual(result["requirement_lookup"], [])

    def test_missing_paths_are_listed(self):
        a = self.write("docs/rules/a.md")
        result, errors = self.collect(
            _task(required_reading=[a, "docs/rules/none.md", "src/none.py"])
        )
        self.assertEqual(errors, [])
        self.assertEqual(result["missing_paths"], ["docs/rules/none.md", "src/none.py"])
        self.assertEqual(len(result["problems"]), 1)

    def test_unknown_task_id_is_error(self):
        result, errors = collect_module.collect_required_reading(
            {"tasks": [_task("TASK-001")]}, "TASK-999", str(self.root)
        )
        self.assertIsNone(result)
        self.assertTrue(errors)

    def test_malformed_required_reading_is_error(self):
        task = _task()
        task["required_reading"] = "docs/a.md"
        result, errors = self.collect(task)
        self.assertIsNone(result)
        self.assertTrue(errors)

    def test_missing_doc_structure_is_error_when_design_id_given(self):
        (self.root / ".doc_structure.yaml").unlink()
        result, errors = self.collect(_task(design_id="DES-001"))
        self.assertIsNone(result)
        self.assertTrue(errors)

    def test_missing_doc_structure_is_ok_when_design_id_null(self):
        (self.root / ".doc_structure.yaml").unlink()
        a = self.write("docs/rules/a.md")
        result, errors = self.collect(_task(required_reading=[a]))
        self.assertEqual(errors, [])
        self.assertEqual(result["paths"], [a])


class CollectCliTest(_ProjectCase):
    def run_cli(self, plan, task_id):
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--plan-path",
                str(plan_path),
                "--task-id",
                task_id,
                "--project-root",
                str(self.root),
            ],
            capture_output=True,
            text=True,
        )

    def test_success_exit_0_with_result_json(self):
        a = self.write("docs/rules/a.md")
        design = self.write("docs/specs/f/design/DES-001_x.md")
        proc = self.run_cli(
            {"tasks": [_task(design_id="DES-001", required_reading=[a])]}, "TASK-001"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["paths"], [a, design])

    def test_requirement_doc_is_in_cli_output(self):
        design = self.write("docs/specs/f/design/DES-001_x.md")
        req = self.write("docs/specs/f/requirements/REQ-001_x.md")
        proc = self.run_cli(
            {
                "tasks": [_task(design_id="DES-001")],
                "design_traceability": [_trace("DES-001", ["REQ-001"])],
            },
            "TASK-001",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["paths"], [design, req])
        self.assertEqual(out["requirement_lookup"][0]["status"], "found")

    def test_findings_still_exit_0(self):
        proc = self.run_cli(
            {"tasks": [_task(design_id="DES-009", required_reading=["nope.md"])]},
            "TASK-001",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["missing_paths"], ["nope.md"])
        self.assertEqual(out["design_lookup"]["status"], "not_found")

    def test_error_exit_1_with_errors_array(self):
        proc = self.run_cli({"tasks": [_task()]}, "TASK-999")
        self.assertEqual(proc.returncode, 1)
        out = json.loads(proc.stdout)
        self.assertEqual(out["status"], "error")
        self.assertIsInstance(out["errors"], list)
        self.assertTrue(out["errors"])

    def test_unreadable_plan_exit_1(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--plan-path",
                str(self.root / "absent.json"),
                "--task-id",
                "TASK-001",
                "--project-root",
                str(self.root),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(json.loads(proc.stdout)["errors"])

    def test_missing_argument_exit_2(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
