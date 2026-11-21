#!/usr/bin/env python3
"""lint: 配布する script のソースが、責務の境界を守っていること。

script を実行せず、ソースの文面と構文木を見る。対象の script ごとに、持ち込んではならない
import・呼び出し・語を検査する。振る舞いの検査は、各 script の単体テスト（`tests/forge/`）にある。

実行:
  python3 -m unittest lint.lint_script_source -v
"""

import ast
import re
import sys
import unittest
from pathlib import Path

from lint import REPO_ROOT

PLUGIN_ROOT = REPO_ROOT / "plugins" / "forge"
DOC_BACKEND = PLUGIN_ROOT / "scripts" / "doc_backend"

ADR_EXCHANGE = PLUGIN_ROOT / "scripts" / "adr" / "adr_exchange.py"
RECORD_REVIEW_BRIEF = (
    PLUGIN_ROOT / "skills" / "consult" / "scripts" / "record_review_brief.py"
)

#: 認証情報の取り扱いを示す語
CREDENTIAL_WORDS = ("api_key", "apikey", "token", "password", "secret", "authorization")

#: `.doc_structure.yaml` の解釈（resolver の責務）を示す import と関数名
RESOLVER_IMPORTS = ("glob", "fnmatch", "yaml", "os")
RESOLVER_FUNCTIONS = ("parse_config", "expand_globs", "collect_md_files", "is_excluded")


def syntax_tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def imported_modules(path: Path) -> set[str]:
    """script が import するモジュールの、最上位の名前の集合。"""
    imported: set[str] = set()
    for node in ast.walk(syntax_tree(path)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def defined_functions(path: Path) -> set[str]:
    return {
        node.name
        for node in ast.walk(syntax_tree(path))
        if isinstance(node, ast.FunctionDef)
    }


def code_without_comment_lines(path: Path) -> str:
    """`#` で始まる行を除いたソース。"""
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


class NoCredentialHandlingTest(unittest.TestCase):
    """doc-db と通信する script が、認証情報・環境変数を読む処理を持たないこと。"""

    def test_module_source_has_no_credential_reads(self):
        for name in ("docdb_client.py", "docdb_runtime.py"):
            with self.subTest(script=name):
                code = code_without_comment_lines(DOC_BACKEND / name).lower()
                for forbidden in CREDENTIAL_WORDS:
                    self.assertNotIn(
                        forbidden,
                        code,
                        f"認証情報の取り扱いが混入している: {forbidden}",
                    )

    def test_runtime_does_not_read_environment(self):
        code = code_without_comment_lines(DOC_BACKEND / "docdb_runtime.py")
        for forbidden in ("os.environ", "getenv", "environb"):
            self.assertNotIn(
                forbidden, code, f"環境変数の読み取りが混入している: {forbidden}"
            )


class NoLogFileTest(unittest.TestCase):
    """forge 側でログファイルを作らない（出力先は doc-db 自身の設定に委ねる）。"""

    def test_runtime_opens_no_file(self):
        code = code_without_comment_lines(DOC_BACKEND / "docdb_runtime.py")
        # `Popen(` は許容し、単独の `open(` だけを検出する
        self.assertIsNone(
            re.search(r"\bopen\s*\(", code), "ファイルを開く処理が混入している"
        )
        for forbidden in ("NamedTemporaryFile", "write_text", ".log"):
            self.assertNotIn(forbidden, code, f"ログ・ファイル生成の疑い: {forbidden}")


class NoSettingsDependencyTest(unittest.TestCase):
    """doc-db 経路の CLI は、設定・優先指定・選択順序を知らない（責務分離）。

    順序リストの解決（`.claude/.forge.yaml` の読み取り）は `resolve_backend_order.py` が担う。
    """

    def test_does_not_import_forge_settings(self):
        for name in ("query_docdb.py", "sync_docdb.py"):
            with self.subTest(script=name):
                self.assertNotIn(
                    "forge_settings",
                    imported_modules(DOC_BACKEND / name),
                    "設定を読んではならない",
                )


class NoPollingLoopTest(unittest.TestCase):
    """完了待ちを SKILL 側へ固定するため、sync の script 内に時間待ち・反復問い合わせを持たない。"""

    SCRIPT = DOC_BACKEND / "sync_docdb.py"

    def test_no_time_import_and_no_sleep_calls(self):
        self.assertNotIn(
            "time",
            imported_modules(self.SCRIPT),
            "ポーリングのための時間待ちを持ち込まない",
        )
        sleep_calls = [
            node
            for node in ast.walk(syntax_tree(self.SCRIPT))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sleep"
        ]
        self.assertEqual(sleep_calls, [])

    def test_no_loop_around_status_retrieval(self):
        """`get_sync_status` の呼び出しがループ（while / for）の中にないこと。"""
        tree = syntax_tree(self.SCRIPT)
        for loop in [n for n in ast.walk(tree) if isinstance(n, (ast.While, ast.For))]:
            for node in ast.walk(loop):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotEqual(
                        node.func.attr,
                        "get_sync_status",
                        "状態取得をプロセス内ループで反復してはならない",
                    )


class NoYamlReimplementationTest(unittest.TestCase):
    """`.doc_structure.yaml` の解釈を自前で持っていないこと（resolver へ委譲）。"""

    def test_no_yaml_parsing_is_reimplemented(self):
        for name in ("prepare_index_input.py", "project_documents.py"):
            with self.subTest(script=name):
                script = DOC_BACKEND / name
                imported = imported_modules(script)
                for forbidden in RESOLVER_IMPORTS:
                    self.assertNotIn(
                        forbidden,
                        imported,
                        f"resolver の責務を再実装している: {forbidden}",
                    )
                defined = defined_functions(script)
                for forbidden in RESOLVER_FUNCTIONS:
                    self.assertNotIn(
                        forbidden,
                        defined,
                        f"resolver の責務を再実装している: {forbidden}",
                    )


class AdrExchangeSourceTest(unittest.TestCase):
    def test_module_docstring_declares_exit_codes_only_0_1_2(self):
        """3 以上を返さない script は、0 / 1 / 2 だけを宣言する。"""
        text = ADR_EXCHANGE.read_text(encoding="utf-8")
        self.assertIn("## 終了コード", text)
        for code in ("| 0 ", "| 1 ", "| 2 "):
            self.assertIn(code, text)

    def test_no_blanket_exception_catch(self):
        """内部バグを握りつぶさない（COMMON-REQ-002）。"""
        text = ADR_EXCHANGE.read_text(encoding="utf-8")
        self.assertNotIn("except Exception", text)
        self.assertNotIn("except:", text)


class RecordReviewBriefImportsTest(unittest.TestCase):
    def test_script_imports_only_the_standard_library(self):
        modules = set()
        for node in ast.walk(syntax_tree(RECORD_REVIEW_BRIEF)):
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
        self.assertNotIn("sys.path", RECORD_REVIEW_BRIEF.read_text(encoding="utf-8"))


class RemovedFilesTest(unittest.TestCase):
    """取り除いた 2 本目の検証経路とテンプレートが、戻っていないこと。"""

    def test_second_path_and_template_are_gone(self):
        base = PLUGIN_ROOT / "skills" / "start-implement"
        self.assertFalse((base / "scripts" / "validate_executor_result.py").exists())
        self.assertFalse((base / "templates" / "executor_result.json").exists())
        self.assertFalse(
            (
                REPO_ROOT
                / "tests"
                / "forge"
                / "start-implement"
                / "test_validate_executor_result.py"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
