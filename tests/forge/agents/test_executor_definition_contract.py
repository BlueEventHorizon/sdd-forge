"""executor.md の契約テスト（定義の呼び方と結果の説明が、実際の script と一致すること）。

定義が持つ script の呼び方が `resolve_task_context.py` の実際の引数と一致すること、
結果の各フィールドの説明が結果の契約（`executor_result_contract.py`）のフィールド集合と
一致することを確かめる。Claude Code の実 Agent 起動は unittest の検証対象にしない。

文面だけを見る検査（Role 制約・配布物の規約）は `lint/provisional/lint_executor_definition.py` にある。
"""

import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import REPO_ROOT

PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
SCRIPT_DIR = PLUGIN_ROOT / "skills" / "start-implement" / "scripts"
EXECUTOR_PATH = PLUGIN_ROOT / "agents" / "executor.md"

sys.path.insert(0, str(SCRIPT_DIR))
import executor_result_contract  # noqa: E402


class ExecutorDefinitionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = EXECUTOR_PATH.read_text(encoding="utf-8")

    def _documented_commands(self):
        return [
            line
            for line in self.text.splitlines()
            if line.startswith('python3 "${CLAUDE_PLUGIN_ROOT}/')
        ]

    # --- script の呼び方 ---

    def test_documented_script_call_matches_the_actual_arguments(self):
        """定義に書かれた呼び方を実際に実行して、引数が実際の script と一致することを確かめる。"""
        line = self._documented_commands()[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            context_id = "TASK-001-0123abcd"
            context_dir = (
                root / "docs" / "tasks"
            )  # 計画書 docs/x_plan.json と同じディレクトリ
            context_dir.mkdir(parents=True)
            (context_dir / f"{context_id}.json").write_text("{}", encoding="utf-8")
            line = line.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT))
            line = line.replace("${CLAUDE_PROJECT_DIR}", str(root))
            line = line.replace("{plan_path}", "docs/x_plan.json").replace(
                "{context_id}", context_id
            )
            argv = shlex.split(line)
            self.assertEqual(argv[0], "python3")
            completed = subprocess.run(
                [sys.executable, *argv[1:]], capture_output=True, text=True
            )
            self.assertEqual(
                completed.returncode, 0, completed.stdout + completed.stderr
            )
            self.assertEqual(
                json.loads(completed.stdout),
                {"path": str(context_dir / f"{context_id}.json")},
            )

    # --- 結果の意味が契約と一致する ---

    def test_result_field_descriptions_match_the_contract(self):
        """出力の表が挙げるフィールドが、結果の契約のフィールド集合と一致する。"""
        section = self.text.split("## Output [MANDATORY]")[1].split("\n---", 1)[0]
        top = set()
        verification = set()
        for match in re.finditer(r"(?m)^\| `([a-z_.]+)`", section):
            name = match.group(1)
            if name.startswith("verification."):
                verification.add(name.split(".", 1)[1])
            else:
                top.add(name)
        self.assertEqual(top, set(executor_result_contract.TASK_RESULT_FIELDS))
        self.assertEqual(
            verification, set(executor_result_contract.VERIFICATION_RESULT_FIELDS)
        )

    def test_describes_enumerations_of_the_contract(self):
        for value in (
            *executor_result_contract.STATUSES,
            *executor_result_contract.VERIFICATION_STATES,
        ):
            self.assertIn(f"`{value}`", self.text)


if __name__ == "__main__":
    unittest.main()
