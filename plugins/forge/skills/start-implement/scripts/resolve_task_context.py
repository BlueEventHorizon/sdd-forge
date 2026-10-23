#!/usr/bin/env python3
"""識別値から、タスクコンテキストの絶対パスを返す（文脈作成 CX-02）。

`/forge:start-implement` の文脈作成のローカル操作入口のうち、executor agent が呼ぶ
「解決する」入口。作る・削除する入口（CX-01・CX-03）は `build_task_context.py` である。

返すのは絶対パスだけで、ファイルの本文は標準出力に載せない。executor agent は、返された
パスのファイルを直接読む。置き場の決め方・名前の検査は `build_task_context.py` を再利用する。

## 引数

`--project-root` / `--plan-path` / `--context-id`（すべて必須）。置き場は計画書と同じ
ディレクトリの `tasks/` であり、`--plan-path` から決まる。

## 標準出力

0 のとき、`{"path": "絶対パス"}`。
1 のとき、`{"errors": ["自然文", ...]}`。パスは返さない。

## 拒否（パスを返さず、標準出力の `errors` に自然文で返す）

- 識別値が名前 1 つでない（置き場の外を指す値を含む）
- 計画書パスが空、またはプロジェクトルートの外を指す
- プロジェクトルートがディレクトリでない
- 識別値に対応するファイルが無い
- 対応するものがシンボリックリンクである、または通常ファイルでない

## 終了コード

| code | 意味                                                               |
| ---- | ------------------------------------------------------------------ |
| 0    | 解決できた（標準出力に `path`）                                    |
| 1    | 区別のないエラー（標準出力の `errors` に理由）                     |
| 2    | 引数を受理できない（`argparse`）                                   |

Usage:
    python3 resolve_task_context.py --project-root ROOT --plan-path PLAN --context-id ID
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_task_context  # noqa: E402

review_common = build_task_context.review_common


def resolve(project_root, plan_path, context_id):
    """`(絶対パス | None, 理由 | None)` を返す。パスは公開済みの通常ファイルだけである。"""
    reason = build_task_context.invalid_name("context-id", context_id)
    if reason:
        return None, reason
    root = Path(project_root).resolve()
    if not root.is_dir():
        return None, f"プロジェクトルートがディレクトリではありません: {root}"
    reason = build_task_context.plan_path_error(root, plan_path)
    if reason:
        return None, reason
    path = build_task_context.context_path(root, plan_path, context_id)
    if path.is_symlink():
        return (
            None,
            f"タスクコンテキストがシンボリックリンクです: context_id={context_id}",
        )
    if not path.exists():
        return (
            None,
            f"識別値に対応するタスクコンテキストがありません: context_id={context_id}",
        )
    if not path.is_file():
        return (
            None,
            f"タスクコンテキストが通常ファイルではありません: context_id={context_id}",
        )
    return path, None


def build_parser():
    parser = argparse.ArgumentParser(description="タスクコンテキストの絶対パスを返す")
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--plan-path",
        required=True,
        help="計画書のパス（置き場は同じディレクトリの tasks/）",
    )
    parser.add_argument("--context-id", required=True)
    return parser


def run_cli(argv=None):
    args = build_parser().parse_args(argv)
    path, reason = resolve(args.project_root, args.plan_path, args.context_id)
    if reason:
        return review_common.error(reason)
    review_common.emit({"path": str(path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
