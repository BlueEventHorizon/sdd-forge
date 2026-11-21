"""バージョン同期の lint が使う検査ロジック。

単体テストは `tests/lint_rules/test_version_sync.py` にある。
"""


def is_optional_flag(sync):
    """sync_files エントリの `optional` フラグを真偽値として解釈する。

    `get_version_status.py` の手製 YAML パーサーはスカラー値を文字列のまま返す
    （bool にキャストしない）ため、`optional: false` も文字列 `"false"` になる。
    `bool("false")` は Python では `True` になるため、単純な `bool()` 変換では
    `optional: false` を明示したエントリまで optional 扱いになってしまう。
    """
    value = sync.get("optional")
    if value is None:
        return False
    return str(value).strip().lower() == "true"
