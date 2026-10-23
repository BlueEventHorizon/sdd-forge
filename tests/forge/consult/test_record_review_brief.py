#!/usr/bin/env python3
"""record_review_brief.py の契約テスト。

DES-078 §5.2 M-07 の事前条件・事後条件と §6.7 の観点を確かめる。

- 記録が §6.2 の構造で、本文がそのまま入り、成功したときに受け渡し本文が削除される
- ``finding_ids`` は昇順・重複なしになる
- 通し番号は既存の記録の最大の番号に 1 を足した値で、同じ名前が先に作られたときは進めて公開する
- 不正な引数・置き場の欠如・公開の失敗では、記録も一時ファイルも作られず、受け渡し本文が残る
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "forge"
    / "skills"
    / "consult"
    / "scripts"
    / "record_review_brief.py"
)

# 改行・引用符・バッククォート・非 ASCII・JSON/シェルの構文に見える文字を含む本文
TRICKY_SUMMARY = 'line1\nline2 "quoted" \'single\' `tick` $(echo x) \\n {"a": 1}\n日本語と絵文字 🎉\n'
TRICKY_RECOMMENDATION = '推奨: `rm -rf` ではなく "確認" する\r\n末尾の空白  \n\n'


def _run(*args):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True
    )
    stdout = completed.stdout.decode("utf-8")
    payload = json.loads(stdout) if stdout.strip() else None
    return completed.returncode, payload, completed.stderr.decode("utf-8")


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "record_review_brief_under_test", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name).resolve()
        self.round_dir = root / "round"
        self.round_dir.mkdir()
        self.evaluation = self.round_dir / "evaluate_result.json"
        self.evaluation.write_text('{"evaluations": []}\n', encoding="utf-8")
        handoff = root / "handoff"
        handoff.mkdir()
        self.summary = handoff / "summary.md"
        self.recommendation = handoff / "recommendation.md"
        self.write_bodies(TRICKY_SUMMARY, TRICKY_RECOMMENDATION)

    def write_bodies(self, summary, recommendation):
        # newline を変換せずそのまま書く（\r\n を含めて検証するため）
        self.summary.write_bytes(summary.encode("utf-8"))
        self.recommendation.write_bytes(recommendation.encode("utf-8"))

    def args(
        self, finding_ids=("1",), review_id="r-1", round_number="1", evaluation=None
    ):
        return [
            str(evaluation or self.evaluation),
            review_id,
            round_number,
            "--finding-ids",
            *finding_ids,
            "--summary-file",
            str(self.summary),
            "--recommendation-file",
            str(self.recommendation),
        ]

    def record(self, **kwargs):
        return _run(*self.args(**kwargs))

    def snapshot(self):
        """置き場の全ファイルの内容（名前 -> bytes）。一時ファイルの残存も含めて見る。"""
        return {p.name: p.read_bytes() for p in self.round_dir.iterdir()}

    def load(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def assert_failed_cleanly(self, code, payload, before):
        self.assertEqual(code, 1, payload)
        self.assertIsInstance(payload["errors"], list)
        self.assertTrue(payload["errors"])
        self.assertEqual(
            self.snapshot(),
            before,
            "置き場が変わっている（記録または一時ファイルが残った）",
        )
        self.assertTrue(self.summary.exists(), "受け渡し本文が消えた")
        self.assertTrue(self.recommendation.exists(), "受け渡し本文が消えた")


class SuccessTest(_Fixture):
    def test_record_structure_and_stdout(self):
        code, payload, _ = self.record(
            finding_ids=("3", "1"), review_id="abc", round_number="2"
        )
        self.assertEqual(code, 0, payload)
        self.assertEqual(set(payload), {"path"})
        path = Path(payload["path"])
        self.assertTrue(path.is_absolute())
        self.assertEqual(path, self.round_dir / "consult_brief_1.json")
        self.assertEqual(
            self.load(path),
            {
                "review_id": "abc",
                "round_number": 2,
                "sequence": 1,
                "finding_ids": [1, 3],
                "summary": TRICKY_SUMMARY,
                "recommendation": TRICKY_RECOMMENDATION,
            },
        )

    def test_bodies_are_kept_verbatim(self):
        code, payload, _ = self.record()
        self.assertEqual(code, 0, payload)
        record = self.load(payload["path"])
        # バイト列として同一であること（改行コード・末尾の空白を含む）
        self.assertEqual(
            record["summary"].encode("utf-8"), TRICKY_SUMMARY.encode("utf-8")
        )
        self.assertEqual(
            record["recommendation"].encode("utf-8"),
            TRICKY_RECOMMENDATION.encode("utf-8"),
        )
        self.assertIn("`tick`", record["summary"])
        self.assertIn("日本語と絵文字 🎉", record["summary"])
        self.assertIn("\r\n", record["recommendation"])

    def test_handoff_files_are_deleted_on_success(self):
        code, payload, _ = self.record()
        self.assertEqual(code, 0, payload)
        self.assertFalse(self.summary.exists())
        self.assertFalse(self.recommendation.exists())

    def test_only_the_record_is_added_to_the_directory(self):
        before = set(self.snapshot())
        code, payload, _ = self.record()
        self.assertEqual(code, 0, payload)
        self.assertEqual(set(self.snapshot()) - before, {"consult_brief_1.json"})

    def test_evaluation_json_is_not_modified_or_read(self):
        # 中身が JSON でなくても、置き場の基準としてパスだけを使う
        self.evaluation.write_bytes(b"\xff not json at all")
        before = self.evaluation.read_bytes()
        code, payload, _ = self.record()
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.evaluation.read_bytes(), before)

    def test_empty_bodies_are_not_rejected(self):
        # 値の内容を理由に受け渡しを拒まない
        self.write_bodies("", "")
        code, payload, _ = self.record()
        self.assertEqual(code, 0, payload)
        record = self.load(payload["path"])
        self.assertEqual((record["summary"], record["recommendation"]), ("", ""))


class FindingIdsTest(_Fixture):
    def test_sorted_and_deduplicated_regardless_of_input_order(self):
        for given in (("5", "2", "9"), ("9", "5", "2"), ("2", "2", "5", "9", "9", "5")):
            with self.subTest(given=given):
                self.write_bodies("s", "r")
                code, payload, _ = self.record(finding_ids=given)
                self.assertEqual(code, 0, payload)
                self.assertEqual(self.load(payload["path"])["finding_ids"], [2, 5, 9])

    def test_numeric_not_lexicographic_order(self):
        code, payload, _ = self.record(finding_ids=("10", "9", "100"))
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.load(payload["path"])["finding_ids"], [9, 10, 100])

    def test_leading_zero_is_normalized(self):
        code, payload, _ = self.record(finding_ids=("07", "7"))
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.load(payload["path"])["finding_ids"], [7])


class SequenceTest(_Fixture):
    def test_first_record_is_one(self):
        code, payload, _ = self.record()
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.load(payload["path"])["sequence"], 1)

    def test_sequence_is_max_existing_plus_one(self):
        for n in (1, 2, 7):
            (self.round_dir / f"consult_brief_{n}.json").write_text(
                "{}", encoding="utf-8"
            )
        code, payload, _ = self.record()
        self.assertEqual(code, 0, payload)
        self.assertEqual(Path(payload["path"]).name, "consult_brief_8.json")
        self.assertEqual(self.load(payload["path"])["sequence"], 8)

    def test_unrelated_files_do_not_affect_the_sequence(self):
        for name in (
            "consult_brief_99.json.bak",
            "consult_brief_x.json",
            "consult_brief_.json",
            "xconsult_brief_50.json",
            "consult_brief_50.txt",
            ".consult_brief.abc.tmp",
        ):
            (self.round_dir / name).write_text("{}", encoding="utf-8")
        code, payload, _ = self.record()
        self.assertEqual(code, 0, payload)
        self.assertEqual(Path(payload["path"]).name, "consult_brief_1.json")

    def test_same_finding_ids_twice_make_two_distinct_records(self):
        code1, first, _ = self.record(finding_ids=("1", "2"))
        self.assertEqual(code1, 0, first)
        first_bytes = Path(first["path"]).read_bytes()

        self.write_bodies("別の要旨", "別の推奨案")
        code2, second, _ = self.record(finding_ids=("1", "2"))
        self.assertEqual(code2, 0, second)

        self.assertNotEqual(first["path"], second["path"])
        self.assertEqual(self.load(first["path"])["sequence"], 1)
        self.assertEqual(self.load(second["path"])["sequence"], 2)
        self.assertEqual(
            Path(first["path"]).read_bytes(), first_bytes, "先の記録が変わった"
        )
        self.assertEqual(self.load(second["path"])["summary"], "別の要旨")


class RaceTest(_Fixture):
    """採番から公開までの間に同じ名前が先に作られた状況を、同一プロセス内で再現する。"""

    def run_in_process(self, module):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = module.run_cli(self.args())
        return code, json.loads(buffer.getvalue())

    def test_name_taken_between_numbering_and_publish_advances_the_sequence(self):
        module = _load_module()
        real = module.next_sequence
        competitor = b'{"competitor": true}\n'

        def numbering_then_competitor_publishes(directory):
            n = real(directory)
            # 採番した直後に、別の記録が同じ名前で公開される
            (directory / f"consult_brief_{n}.json").write_bytes(competitor)
            return n

        with mock.patch.object(
            module, "next_sequence", numbering_then_competitor_publishes
        ):
            code, payload = self.run_in_process(module)

        self.assertEqual(code, 0, payload)
        self.assertEqual(Path(payload["path"]).name, "consult_brief_2.json")
        self.assertEqual(self.load(payload["path"])["sequence"], 2)
        self.assertEqual(
            (self.round_dir / "consult_brief_1.json").read_bytes(),
            competitor,
            "先に作られた記録が上書きされた",
        )
        self.assertEqual(
            sorted(p.name for p in self.round_dir.iterdir()),
            ["consult_brief_1.json", "consult_brief_2.json", "evaluate_result.json"],
        )

    def test_several_names_taken_keeps_advancing(self):
        module = _load_module()
        for n in (1, 2, 3):
            (self.round_dir / f"consult_brief_{n}.json").write_text(
                f"old{n}", encoding="utf-8"
            )
        # 採番が古い値（1）を返し続ける状況。1, 2, 3 は塞がっているので 4 まで進む
        with mock.patch.object(module, "next_sequence", lambda directory: 1):
            code, payload = self.run_in_process(module)
        self.assertEqual(code, 0, payload)
        self.assertEqual(Path(payload["path"]).name, "consult_brief_4.json")
        self.assertEqual(self.load(payload["path"])["sequence"], 4)
        for n in (1, 2, 3):
            self.assertEqual(
                (self.round_dir / f"consult_brief_{n}.json").read_text(
                    encoding="utf-8"
                ),
                f"old{n}",
            )
        self.assertFalse(
            [p for p in self.round_dir.iterdir() if p.name.endswith(".tmp")]
        )


class InvalidArgumentsTest(_Fixture):
    def check_failure(self, args):
        before = self.snapshot()
        code, payload, _ = _run(*args)
        self.assert_failed_cleanly(code, payload, before)

    def test_relative_evaluation_path(self):
        args = self.args()
        args[0] = "evaluate_result.json"
        self.check_failure(args)

    def test_nonexistent_evaluation_path(self):
        args = self.args()
        args[0] = str(self.round_dir / "missing.json")
        self.check_failure(args)

    def test_relative_summary_file(self):
        args = self.args()
        args[args.index("--summary-file") + 1] = "summary.md"
        self.check_failure(args)

    def test_nonexistent_summary_file(self):
        args = self.args()
        args[args.index("--summary-file") + 1] = str(self.summary.parent / "nope.md")
        self.check_failure(args)

    def test_relative_recommendation_file(self):
        args = self.args()
        args[args.index("--recommendation-file") + 1] = "recommendation.md"
        self.check_failure(args)

    def test_nonexistent_recommendation_file(self):
        args = self.args()
        args[args.index("--recommendation-file") + 1] = str(
            self.summary.parent / "nope.md"
        )
        self.check_failure(args)

    def test_invalid_round_number(self):
        for bad in ("0", "-1", "abc", "1.5", ""):
            with self.subTest(round_number=bad):
                self.check_failure(self.args(round_number=bad))

    def test_invalid_finding_ids(self):
        for bad in (("0",), ("-3",), ("abc",), ("1", "0"), ("1", "x"), ("1.5",), ("",)):
            with self.subTest(finding_ids=bad):
                self.check_failure(self.args(finding_ids=bad))

    def test_collects_every_error(self):
        args = self.args(round_number="0", finding_ids=("0",))
        args[0] = "relative.json"
        before = self.snapshot()
        code, payload, _ = _run(*args)
        self.assert_failed_cleanly(code, payload, before)
        self.assertGreaterEqual(len(payload["errors"]), 3)

    def test_body_that_is_not_utf8_fails_without_writing(self):
        self.summary.write_bytes(b"\xff\xfe invalid")
        self.check_failure(self.args())

    def test_missing_required_option_is_an_argparse_error(self):
        code, payload, stderr = _run(str(self.evaluation), "r-1", "1")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)
        self.assertTrue(stderr)
        self.assertEqual(
            [p.name for p in self.round_dir.iterdir()], ["evaluate_result.json"]
        )

    def test_empty_finding_ids_is_an_argparse_error(self):
        args = self.args()
        index = args.index("--finding-ids")
        del args[index + 1]
        code, payload, _ = _run(*args)
        self.assertEqual(code, 2)
        self.assertIsNone(payload)
        self.assertEqual(
            [p.name for p in self.round_dir.iterdir()], ["evaluate_result.json"]
        )


class PublishFailureTest(_Fixture):
    def test_directory_not_writable_fails_and_keeps_handoff(self):
        if os.geteuid() == 0:
            self.skipTest("root は書き込み権限の検査を受けない")
        before = self.snapshot()
        self.round_dir.chmod(0o500)
        self.addCleanup(self.round_dir.chmod, 0o700)
        code, payload, _ = self.record()
        self.round_dir.chmod(0o700)
        self.assert_failed_cleanly(code, payload, before)

    def test_link_failure_other_than_name_taken_fails_cleanly(self):
        module = _load_module()
        before = self.snapshot()
        buffer = io.StringIO()
        with mock.patch.object(
            module.os, "link", side_effect=PermissionError("link 不可")
        ):
            with redirect_stdout(buffer):
                code = module.run_cli(self.args())
        self.assert_failed_cleanly(code, json.loads(buffer.getvalue()), before)

    def test_failure_leaves_no_temp_file_and_no_partial_record(self):
        module = _load_module()
        buffer = io.StringIO()
        with mock.patch.object(module.os, "link", side_effect=OSError("公開できない")):
            with redirect_stdout(buffer):
                code = module.run_cli(self.args())
        self.assertEqual(code, 1)
        self.assertEqual(
            [p.name for p in self.round_dir.iterdir()], ["evaluate_result.json"]
        )


class ImportsTest(unittest.TestCase):
    def test_script_imports_only_the_standard_library(self):
        import ast

        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "相対 import がある")
                modules.add((node.module or "").split(".")[0])
        self.assertTrue(modules)
        self.assertLessEqual(
            modules,
            set(sys.stdlib_module_names),
            sorted(modules - set(sys.stdlib_module_names)),
        )

    def test_does_not_touch_sys_path_for_sibling_components(self):
        self.assertNotIn("sys.path", SCRIPT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
