#!/usr/bin/env python3
"""Claude Code の plan mode が保存する plan ファイルを mtime 降順で列挙する。

探索先は次の優先順位で決める。結果の JSON の `plans_dir_source` が、どれで決まったかを示す。

1. `--plans-dir`（`flag`）
2. 環境変数 `PLANS_DIR`（`env`）
3. 設定 `plansDirectory`（`settings:<設定ファイルのパス>`）。プロジェクトルートからの相対パスで、
   プロジェクトルートの外は不可（Claude Code 本体と同じ）。設定ファイルは
   `<プロジェクトルート>/.claude/settings.local.json`、`<プロジェクトルート>/.claude/settings.json`、
   `~/.claude/settings.json` の順に探し、最初に定義のあったものを使う
4. 既定の `~/.claude/plans/`（`default`）

設定が読めない・値が不正なときは、既定へ戻さず、終了コード 1 と標準出力の `errors` で返す。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


class PlansDirError(Exception):
    """plan の置き場を決められない（設定が読めない、値が不正）。"""


def _read_plans_directory(settings_path: Path) -> str | None:
    """設定ファイルの `plansDirectory` を返す。ファイルが無い、または定義が無ければ None。"""
    if not settings_path.is_file():
        return None
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PlansDirError(f"{settings_path} を読めません: {error}") from error
    if not isinstance(data, dict) or "plansDirectory" not in data:
        return None
    value = data["plansDirectory"]
    if not isinstance(value, str) or not value.strip():
        raise PlansDirError(
            f"{settings_path} の plansDirectory は空でない文字列で指定してください: {value!r}"
        )
    return value


def resolve_plans_dir(
    project_root: Path, home: Path, explicit: str | None, env: str | None
) -> tuple[Path, str]:
    """探索先とその決定元を返す。優先順位はモジュールの docstring のとおり。"""
    if explicit:
        return Path(explicit).expanduser(), "flag"
    if env:
        return Path(env).expanduser(), "env"
    root = project_root.resolve()
    for settings_path in (
        project_root / ".claude" / "settings.local.json",
        project_root / ".claude" / "settings.json",
        home / ".claude" / "settings.json",
    ):
        value = _read_plans_directory(settings_path)
        if value is None:
            continue
        resolved = (root / value).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            raise PlansDirError(
                f"{settings_path} の plansDirectory がプロジェクトルートの外を指しています: {value}"
            ) from None
        return resolved, f"settings:{settings_path}"
    return home / ".claude" / "plans", "default"


def _extract_title(path: Path, max_bytes: int = 4096) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            head = f.read(max_bytes)
    except OSError:
        return path.stem
    for line in head.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or path.stem
    return path.stem


def list_plans(plans_dir: Path, limit: int) -> dict:
    if not plans_dir.exists() or not plans_dir.is_dir():
        return {
            "status": "missing",
            "plans_dir": str(plans_dir),
            "count": 0,
            "plans": [],
            "latest": None,
        }

    files = [p for p in plans_dir.glob("*.md") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    plans = []
    for p in files[:limit]:
        st = p.stat()
        plans.append(
            {
                "path": str(p),
                "mtime": st.st_mtime,
                "mtime_iso": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                .astimezone()
                .isoformat(timespec="seconds"),
                "size": st.st_size,
                "title": _extract_title(p),
            }
        )

    return {
        "status": "found" if plans else "empty",
        "plans_dir": str(plans_dir),
        "count": len(plans),
        "plans": plans,
        "latest": plans[0]["path"] if plans else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plans-dir",
        default=None,
        help="plan ファイルの探索ディレクトリ。指定すれば設定より優先する（主にテスト用途）",
    )
    parser.add_argument(
        "--project-root",
        default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd(),
        help="設定 plansDirectory の基準となるプロジェクトルート (default: CLAUDE_PROJECT_DIR、無ければ cwd)",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="列挙する最大件数 (default: 10)"
    )
    args = parser.parse_args(argv)

    try:
        plans_dir, source = resolve_plans_dir(
            Path(args.project_root),
            Path.home(),
            args.plans_dir,
            os.environ.get("PLANS_DIR"),
        )
    except PlansDirError as error:
        json.dump({"errors": [str(error)]}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1

    result = list_plans(plans_dir, max(args.limit, 1))
    result["plans_dir_source"] = source
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
