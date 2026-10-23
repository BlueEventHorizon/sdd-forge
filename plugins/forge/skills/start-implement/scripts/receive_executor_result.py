#!/usr/bin/env python3
"""executor agent の結果を検査する（結果検査 RS-01）。

`/forge:start-implement` が executor agent の return value を受け取るときの、唯一の検査の入口。
結果を、タスクコンテキストを読んで 1 か所で検査し、契約に反する結果は理由を `error` に持つ
`FAILURE` の結果へ置き換えて、成功の結果と同じ形（`TaskResult`）で返す。期待値（build・tests）は
タスクコンテキストの `verification` から得る。引数では渡さない。検査の内容は
`executor_result_contract.py` の docstring を参照。

## 使い方

    receive_executor_result.py --project-root <ルート> --plan-path <計画書> \\
        --context-id <識別値> --input-file <結果の JSON>

`--input-file` は `.temp/forge/` 配下のプロジェクトルート相対パス。オーケストレータが受け取った
return value を、そのまま書いたファイルである。読んだ後、成否に関わらず削除される。
タスクコンテキストは、計画書と同じディレクトリの `tasks/{context_id}.json` を読む（置き場の
決め方は `build_task_context.py` を再利用する）。削除しない（削除は `build_task_context.py
--delete` が行う）。

## 標準出力

0 のとき、検査済みの `TaskResult`（JSON object 1 つ）。契約違反は `FAILURE` の結果として 0 で返る。
結果が空・JSON でないときも契約違反として返す（推測で補完しない）。
1 のとき、`{"errors": ["自然文", ...]}`。

## 終了コード

| code | 意味                                                                                  |
| ---- | ------------------------------------------------------------------------------------- |
| 0    | 検査した（成功の結果、または契約違反を置き換えた `FAILURE` の結果を標準出力に返した） |
| 1    | 区別のないエラー（タスクコンテキストを読めない・不正、入力パスが不正、入力ファイルが無い。`errors` に理由） |
| 2    | 引数を受理できない（`argparse`）                                                      |
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from executor_result_contract import (  # noqa: E402
    ContextError,
    check_result,
    failure_result,
    load_expectation,
)
import build_task_context  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "plan"))
from plan_contract import read_and_consume_candidate_input  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "review"))
import review_common  # noqa: E402


def _input_path_error(input_file):
    path = Path(input_file)
    if path.is_absolute() or ".." in path.parts or path.parts[:2] != (".temp", "forge"):
        return "input-file は .temp/forge/ 配下のプロジェクトルート相対パスである必要があります"
    return None


def _load_context(project_root, plan_path, context_id):
    path = build_task_context.context_path(project_root, plan_path, context_id)
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContextError(f"タスクコンテキストを読めません: {path}: {exc}") from exc


def run_cli(argv=None):
    parser = argparse.ArgumentParser(description="executor agent の結果を検査する")
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--plan-path",
        required=True,
        help="計画書のパス（置き場は同じディレクトリの tasks/）",
    )
    parser.add_argument(
        "--context-id", required=True, help="タスクコンテキストの識別値"
    )
    parser.add_argument(
        "--input-file", required=True, help=".temp/forge/ 配下の結果 JSON"
    )
    args = parser.parse_args(argv)

    path_error = _input_path_error(args.input_file)
    if path_error:
        return review_common.error(path_error)
    if not Path(args.input_file).exists():
        # ファイルが無いのは executor agent の結果の不備ではなく、呼び出し側の手違いである。
        # 契約違反（タスクの FAILURE）にせず、検査の入口の失敗として返す
        return review_common.error(
            f"結果の入力ファイルが存在しません: {args.input_file}"
        )

    # 結果は、成否に関わらず消費する（削除する）。以降の早期 return でも残さない
    raw, read_errors = read_and_consume_candidate_input(args.input_file)

    reason = build_task_context.invalid_name("context-id", args.context_id) or (
        build_task_context.plan_path_error(args.project_root, args.plan_path)
    )
    if reason:
        return review_common.error(reason)
    try:
        context = _load_context(args.project_root, args.plan_path, args.context_id)
        expectation = load_expectation(context)
    except ContextError as exc:
        return review_common.error(str(exc))

    if read_errors:
        # 空・JSON でない結果。推測で補完せず、契約違反として FAILURE に置き換える
        task_id, build, tests, build_reason, tests_reason = expectation
        result = failure_result(
            task_id,
            ["結果を JSON として読めません: " + e for e in read_errors],
            build,
            tests,
            build_reason,
            tests_reason,
        )
    else:
        result = check_result(raw, context)
    review_common.emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
