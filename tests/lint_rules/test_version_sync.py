#!/usr/bin/env python3
"""バージョン同期の検査ロジック（`lint/version_sync.py`）の単体テスト。

実行:
    python3 -m unittest tests.lint_rules.test_version_sync -v
"""

import unittest

from lint.version_sync import is_optional_flag


class TestIsOptionalFlag(unittest.TestCase):
    """`optional` フラグの文字列→真偽値解釈の回帰テスト。

    手製 YAML パーサーはスカラー値を文字列のまま返すため、
    `optional: false` を素朴に `bool()` で解釈すると常に `True` になってしまう。
    """

    def test_explicit_false_string_is_not_optional(self):
        """optional: false（パーサーが文字列 "false" を返すケース）は False と解釈する"""
        self.assertFalse(is_optional_flag({"optional": "false"}))

    def test_explicit_true_string_is_optional(self):
        """optional: true（パーサーが文字列 "true" を返すケース）は True と解釈する"""
        self.assertTrue(is_optional_flag({"optional": "true"}))

    def test_missing_key_is_not_optional(self):
        """optional キー自体が無い場合はデフォルト False（DES-023 §2.2 sync_files エントリ定義）"""
        self.assertFalse(is_optional_flag({}))


if __name__ == "__main__":
    unittest.main()
