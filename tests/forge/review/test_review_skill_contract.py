"""review 本体（SKILL.md）の契約テスト（DES-084 §7 の契約テスト対象）。

本体の定義に書かれた script の呼び方が、実際の引数と一致することを確かめる。定義の呼び方を
一時ディレクトリで実際に実行する。Claude Code の実 Agent 起動は unittest の検証対象にしない。

文面だけを見る検査（吟味の指示・Agent の起動・終端の経路）は `lint/provisional/lint_review_skill.py` にある。

置き場: `plugins/forge/skills/review/` のテストは `tests/forge/review/` に置く規約（テストディレクトリ名は
スキルディレクトリ名と一致させる）に従う。reviewer.md / evaluator.md の契約テスト（`tests/forge/agent-review/`）は
Agent の定義を対象にしており、本テストは review スキルの定義を対象にする。
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
SKILL_PATH = PLUGIN_ROOT / "skills" / "review" / "SKILL.md"
SCRIPT_DIR = PLUGIN_ROOT / "scripts" / "review"

# 本体が本書の仕組みで呼ぶ script（`${CLAUDE_PLUGIN_ROOT}` 起点のもの）
EXPECTED_PLUGIN_ROOT_SCRIPTS = {
    "resolve_review_backend",
    "publish_request",
    "body_resolve_findings",
    "body_resolve_evaluations",
    "count_actionable",
    "advance_round",
    "delete_review",
}


def _between(text, start, end=None):
    """``start`` を含む行から、``end`` を含む行の手前までを返す。"""
    begin = text.index(start)
    if end is None:
        return text[begin:]
    return text[begin : text.index(end, begin)]


class ReviewSkillContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_PATH.read_text(encoding="utf-8")
        cls.step7 = _between(cls.text, "### Step 7: ", "### Step 7.5:")

    # --- script の呼び方 ---

    def _documented_commands(self):
        """``${CLAUDE_PLUGIN_ROOT}`` 起点の ``python3`` の呼び方を、script 名 → 1 行 の対応で返す。"""
        commands = {}
        lines = self.text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('python3 "${CLAUDE_PLUGIN_ROOT}/'):
                joined = line
                while joined.endswith("\\"):
                    i += 1
                    joined = joined[:-1].rstrip() + " " + lines[i].strip()
                name = re.search(r"/([A-Za-z0-9_]+)\.py\"", joined).group(1)
                self.assertNotIn(name, commands, f"{name} の呼び方が複数ある")
                commands[name] = joined
            i += 1
        return commands

    def _materialize(self, line, project_root, review_id, round_number, extra):
        line = re.sub(r"\[--backend <name>\]\s*", "", line)
        line = line.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT))
        line = line.replace("${CLAUDE_PROJECT_DIR}", str(project_root))
        line = line.replace("{review_id}", review_id).replace(
            "{round_number}", str(round_number)
        )
        for placeholder, value in extra.items():
            line = line.replace(placeholder, value)
        argv = shlex.split(line)
        self.assertEqual(argv[0], "python3")
        return [sys.executable, *argv[1:]]

    def test_documented_plugin_root_scripts_are_exactly_the_expected_ones(self):
        self.assertEqual(set(self._documented_commands()), EXPECTED_PLUGIN_ROOT_SCRIPTS)

    def test_documented_script_calls_match_the_actual_arguments(self):
        """定義に書かれた呼び方を実際に実行して、引数が実際の script と一致することを確かめる。"""
        commands = self._documented_commands()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = root / "a.md"
            target.write_text("# a\n", encoding="utf-8")
            reference = root / "rule.md"
            reference.write_text("# rule\n", encoding="utf-8")
            focus = root / "focus.txt"
            focus.write_text("重点観点\n複数行\n", encoding="utf-8")
            scope = root / "scope.txt"
            scope.write_text("到達目標\n", encoding="utf-8")

            def run(name, review_id="unused", round_number=1, extra=None, expect=0):
                argv = self._materialize(
                    commands[name], root, review_id, round_number, extra or {}
                )
                completed = subprocess.run(argv, capture_output=True, text=True)
                self.assertEqual(
                    completed.returncode,
                    expect,
                    f"{name}: {completed.stdout}{completed.stderr}",
                )
                return json.loads(completed.stdout)

            backend = run("resolve_review_backend")
            self.assertEqual(backend["status"], "success")
            self.assertEqual(set(backend["retains_context"]), set(backend["order"]))

            published = run(
                "publish_request",
                extra={
                    "{target_path}": str(target),
                    "{base_branch}": "main",
                    "{reference_path}": str(reference),
                    "{focus_file}": str(focus),
                    "{scope_file}": str(scope),
                },
            )
            review_id = published["review_id"]
            self.assertEqual(published["round_number"], 1)
            # 受け渡しファイルは成功時に script が削除する
            self.assertFalse(focus.exists())
            self.assertFalse(scope.exists())

            # 所見・評価が正常に書き終えられていない間は、読み出しが失敗して errors を返す
            for name in ("body_resolve_findings", "body_resolve_evaluations"):
                self.assertIn("errors", run(name, review_id, expect=1))

            def call(script, *args, stdin=""):
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT_DIR / script),
                        str(root),
                        review_id,
                        "1",
                        *args,
                    ],
                    input=stdin,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return json.loads(completed.stdout)

            call("reviewer_add_finding.py", "--location", f"{target}:1", stdin="所見\n")
            call("reviewer_finish.py")
            call(
                "evaluator_add_evaluation.py",
                "--disposition",
                "valid",
                "--severity",
                "major",
                "--findings",
                "1",
                "--confidence",
                "confirmed",
                "--fix-confident",
                "true",
                stdin="根拠\n",
            )
            call("evaluator_finish.py")

            for name in ("body_resolve_findings", "body_resolve_evaluations"):
                self.assertTrue(Path(run(name, review_id)["path"]).is_file())
            self.assertEqual(run("count_actionable", review_id), {"actionable": 1})
            self.assertEqual(run("advance_round", review_id), {"round_number": 2})
            self.assertTrue(
                (root / ".temp" / "forge" / "review" / review_id / "2").is_dir()
            )
            self.assertEqual(run("delete_review", review_id), {})
            self.assertFalse((root / ".temp" / "forge" / "review" / review_id).exists())

    def test_publish_request_documents_every_option_it_has(self):
        """本文が挙げる ``--xxx`` が publish_request.py の実際の引数に存在し、逆も欠けていない。"""
        helps = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "publish_request.py"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        step4 = _between(self.text, "### Step 4:", "### Step 5:")
        for option in (
            "--paths",
            "--base-branch",
            "--diff",
            "--references",
            "--focus-file",
            "--scope-file",
        ):
            self.assertIn(option, helps)
            self.assertIn(f"`{option}", step4)

    def test_split_by_location_call_matches_the_actual_arguments(self):
        """位置の振り分けは script に任せ、所見の結果のパスを渡す（JSON を引数へ埋め込まない）。"""
        step7 = self.step7
        match = re.search(
            r'(?m)^\s*(python3 "\$\{CLAUDE_SKILL_DIR\}/scripts/split_by_location\.py" .*)$',
            step7,
        )
        self.assertIsNotNone(match, "split_by_location.py の呼び方が Step 7 に無い")
        self.assertNotIn("--findings-json", self.text)
        with tempfile.TemporaryDirectory() as tmp:
            findings = Path(tmp) / "review_result.json"
            findings.write_text(
                json.dumps(
                    {
                        "findings": [
                            {"finding_id": 1, "location": ["/abs/a.md:1"], "body": "x"},
                            {"finding_id": 2, "location": ["位置未確定"], "body": "y"},
                        ],
                        "exit": "0",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            line = (
                match.group(1)
                .replace("${CLAUDE_SKILL_DIR}", str(PLUGIN_ROOT / "skills" / "review"))
                .replace("{findings_path}", str(findings))
            )
            argv = shlex.split(line)
            completed = subprocess.run(
                [sys.executable, *argv[1:]], capture_output=True, text=True
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual([f["finding_id"] for f in payload["located"]], [1])
        self.assertEqual([f["finding_id"] for f in payload["unlocated"]], [2])


if __name__ == "__main__":
    unittest.main()
