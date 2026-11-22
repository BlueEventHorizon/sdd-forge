#!/usr/bin/env python3
"""AI-Linter の入口。

実行（リポジトリのルートから）:
  python3 -m ai_lint.run                 # 全検査
  python3 -m ai_lint.run --check <id>    # 指定した検査だけ（繰り返し指定できる）
  python3 -m ai_lint.run --dry-run       # 対象と問いを表示するだけで、送信しない

終了コード:
  0  全件合格
  1  違反、または保留（判定できなかった問い）がある
  2  実行できなかった（backend を使えない・通信の失敗・宣言の不備・対象が無い）

対象の文書の本文は、判定 backend（外部のサービス）へ送られる。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, TextIO

from ai_lint import REPO_ROOT
from ai_lint.backend import Backend, BackendError
from ai_lint.backends import BACKEND_NAMES, create_backend
from ai_lint.judge import (
    PASS,
    UNCERTAIN,
    VIOLATION,
    Check,
    CheckError,
    load_checks,
    resolve_targets,
    run_checks,
)

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_NOT_RUN = 2

_LABELS = {PASS: "合格", VIOLATION: "違反", UNCERTAIN: "保留"}


def _select(checks: list[Check], wanted: list[str]) -> list[Check]:
    if not wanted:
        return checks
    known = {check.id for check in checks}
    unknown = sorted(set(wanted) - known)
    if unknown:
        raise CheckError(f"未知の検査: {unknown}（あるのは {sorted(known)}）")
    return [check for check in checks if check.id in wanted]


def _dry_run(checks: list[Check], root: Path, out: TextIO) -> None:
    for check in checks:
        print(f"検査 {check.id}", file=out)
        for path in resolve_targets(root, check.targets):
            print(f"  対象 {path.relative_to(root).as_posix()}", file=out)
        for question in check.questions:
            expect = "yes" if question.expect else "no"
            print(f"  問い {question.id} 期待={expect} 根拠={question.basis}", file=out)
    print("送信していません（--dry-run）", file=out)


def main(
    argv: list[str] | None = None,
    *,
    backend_factory: Callable[[str], Backend] = create_backend,
    root: Path = REPO_ROOT,
    checks_dir: Path | None = None,
    out: TextIO = sys.stdout,
) -> int:
    parser = argparse.ArgumentParser(description="文章の意味を判定モデルに問う lint")
    parser.add_argument("--check", action="append", default=[], metavar="ID")
    parser.add_argument("--backend", default="jev", choices=BACKEND_NAMES)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        checks = _select(
            load_checks(checks_dir or root / "ai_lint" / "checks"), args.check
        )
        if args.dry_run:
            _dry_run(checks, root, out)
            return EXIT_OK
        backend = backend_factory(args.backend)
        results, usage = run_checks(checks, backend, root)
    except (CheckError, BackendError) as exc:
        print(f"実行できませんでした: {exc}", file=out)
        return EXIT_NOT_RUN

    for result in results:
        expect = "yes" if result.question.expect else "no"
        print(
            f"{_LABELS[result.outcome]} {result.path} "
            f"{result.check_id}/{result.question.id} "
            f"期待={expect} 確率={result.probability:.3f}",
            file=out,
        )
        if result.outcome != PASS:
            print(f"    問い: {result.question.text}", file=out)
            print(f"    根拠: {result.question.basis}", file=out)
    counts = {
        outcome: sum(result.outcome == outcome for result in results)
        for outcome in (PASS, VIOLATION, UNCERTAIN)
    }
    print(
        f"合格 {counts[PASS]} / 違反 {counts[VIOLATION]} / 保留 {counts[UNCERTAIN]}"
        f"（backend {backend.name}、モデル {', '.join(usage.models)}、"
        f"{usage.requests} リクエスト、入力 {usage.input_tokens} トークン）",
        file=out,
    )
    return EXIT_OK if counts[PASS] == len(results) else EXIT_FINDINGS


if __name__ == "__main__":
    sys.exit(main())
