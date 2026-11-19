#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc-link の検索結果のパスを、query wrapper の出力形式へ整える CLI。

doc-link の検索は、文書ごとに記録されたパスを返す。query wrapper の出力契約は
`Required documents:` を先頭とするパスの一覧であり、現在の作業ツリーに実在しない
パスを含めない（REQ-014 BL-005）。本 CLI は、受け取ったパスから実在しないものを
除き、出力形式を決定論的に構築する。SKILL はパスを引数で渡すだけで、形式を
組み立てない。

## 入力

位置引数にパスを 0 個以上渡す（プロジェクトルートからの相対パス。検索結果の順）。
0 個は検索結果が 0 件だった場合であり、空の `Required documents:` を返す。

## 出力（標準出力の JSON）

| field            | 内容                                                 |
| ---------------- | ---------------------------------------------------- |
| `result`         | `Required documents:` 形式の文字列                   |
| `excluded_count` | 実在しないために除いたパスの件数                     |
| `notices`        | 利用者へ伝える通知（除いたパスがあるときの件数など） |

## 終了コード

`0`（完了した）と `2`（引数を受理できない。`argparse`）だけを返す。

## 依存

Python 標準ライブラリのみ。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
import required_documents  # noqa: E402


def run(paths, project_root) -> dict:
    """実在しないパスを除き、出力形式と通知を組み立てる。"""
    existing, excluded_count = required_documents.filter_existing(paths, project_root)
    notices = []
    if excluded_count:
        notices.append(f"実在しないパス {excluded_count} 件を検索結果から除外しました")
    return {
        "result": required_documents.build_required_documents(existing),
        "excluded_count": excluded_count,
        "notices": notices,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="doc-link の検索結果のパスを Required documents 形式へ整える"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="検索結果のパス（プロジェクトルートからの相対パス。検索結果の順）",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="プロジェクトルートのパス（省略時: カレントディレクトリ）",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root) if args.project_root else Path.cwd()
    print(json.dumps(run(args.paths, project_root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
