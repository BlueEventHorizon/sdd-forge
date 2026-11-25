#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""forge 内蔵文書の検索索引（同梱ファイル）を、文書検索の管理状態から生成する。

入力は、キー `forge-rules` で構築した索引（`.doc-link/tocs/forge-rules.json`）と、
その各文書の文書情報（`.doc-link/documents/<文書 ID>.json`）である。出力は
`plugins/forge/toc/rules/rules_toc.yaml` で、`/forge:query-forge-rules` の worker が読む。

同梱ファイルの形式は forge のものであり、文書検索 backend の形式ではない。配布物は
backend を知らないまま、このファイルだけを読む。

索引の文書の集合が内蔵文書の集合と一致しないとき（索引に無い文書がある・索引にだけある
文書がある）は、何も書かずにエラーで終える。索引の内容が現物の文書より古いかは、ここでは
確かめない。それは索引を構築する側（文書検索）の検査が担う。

使い方:
    build_forge_toc.py            同梱ファイルを書く
    build_forge_toc.py --check    書かずに、同梱ファイルが生成結果と一致するかを返す

終了コードは 0（完了）/ 1（区別のないエラー）/ 2（引数を受理できない）だけを返す。
`--check` で不一致のときは 0 で終え、標準出力の JSON の `up_to_date` を false にする。
"""

import argparse
import glob
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
TOC_KEY = "forge-rules"
OUTPUT = REPO_ROOT / "plugins" / "forge" / "toc" / "rules" / "rules_toc.yaml"

# 索引の対象。索引の構築に渡す指定と同じ範囲である。
SOURCE_GLOBS = (
    "plugins/forge/docs/**/*.md",
    "plugins/forge/skills/*/docs/**/*.md",
)

# 文書情報のフィールド → 同梱ファイルのフィールド（リスト）
LIST_FIELDS = (
    ("summary", "content_details"),
    ("tasks", "applicable_tasks"),
    ("keywords", "keywords"),
)


class BuildError(Exception):
    """同梱ファイルを生成できない。"""


def source_paths(repo_root=REPO_ROOT):
    """索引の対象である内蔵文書のパス（リポジトリルートからの相対）を返す。"""
    found = set()
    for pattern in SOURCE_GLOBS:
        for path in glob.glob(str(repo_root / pattern), recursive=True):
            found.add(Path(path).relative_to(repo_root).as_posix())
    return sorted(found)


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BuildError(f"索引のファイルが無い: {path}") from None
    except (OSError, ValueError) as exc:
        raise BuildError(f"索引のファイルを読めない: {path}: {exc}") from None


def _document_id(item):
    """索引の `documents` の 1 要素から、文書 ID を返す。

    doc-link は、この要素の書き方を変えた。旧は `{"doc_link_id": …, …}` のオブジェクト、
    新（0.1.6 以降）は文書 ID の文字列である。旧は、次に索引を再構築するまで残るので、両方を読む。
    """
    if isinstance(item, str):
        return item
    if isinstance(item, dict) and isinstance(item.get("doc_link_id"), str):
        return item["doc_link_id"]
    raise BuildError(f"索引の documents の要素から文書 ID を読めない: {item!r}")


def load_entries(repo_root=REPO_ROOT):
    """索引の各文書の文書情報を、パスの順で返す。文書の集合が一致しなければ BuildError。"""
    store = repo_root / ".doc-link"
    toc = _read_json(store / "tocs" / f"{TOC_KEY}.json")
    entries = {}
    for item in toc.get("documents", []):
        doc = _read_json(store / "documents" / f"{_document_id(item)}.json")
        entries[doc["path"]] = doc

    sources = set(source_paths(repo_root))
    missing = sorted(sources - set(entries))
    surplus = sorted(set(entries) - sources)
    if missing or surplus:
        raise BuildError(
            "索引の文書の集合が内蔵文書と一致しない。索引を再構築してから実行する。"
            f" 索引に無い文書: {missing}"
            f" 索引にだけある文書: {surplus}"
        )
    return [entries[path] for path in sorted(entries)]


def _scalar(value):
    # JSON の文字列は YAML の二重引用符の文字列としてそのまま読める。
    return json.dumps(str(value), ensure_ascii=False)


def render(entries):
    """同梱ファイルの本文を返す。同じ入力からは常に同じ本文になる。"""
    lines = [
        "# forge 内蔵文書の検索索引",
        "# update-forge-toc が生成する。直接編集しない",
        "",
        "metadata:",
        f"  key: {TOC_KEY}",
        f"  file_count: {len(entries)}",
        "",
        "docs:",
    ]
    for doc in entries:
        lines.append(f"  {doc['path']}:")
        lines.append(f"    title: {_scalar(doc['title'])}")
        lines.append(f"    purpose: {_scalar(doc['purpose'])}")
        for source, target in LIST_FIELDS:
            lines.append(f"    {target}:")
            for value in doc.get(source) or []:
                lines.append(f"      - {_scalar(value)}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="書かずに、同梱ファイルが生成結果と一致するかを返す",
    )
    args = parser.parse_args(argv)

    try:
        entries = load_entries()
        text = render(entries)
        output = OUTPUT.relative_to(REPO_ROOT).as_posix()
        if args.check:
            current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else None
            result = {"output": output, "up_to_date": current == text}
        else:
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT.write_text(text, encoding="utf-8")
            result = {"output": output, "file_count": len(entries)}
    except (BuildError, OSError, KeyError) as exc:
        print(json.dumps({"errors": [str(exc)]}, ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
