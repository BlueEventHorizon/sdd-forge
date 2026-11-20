#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""検索結果の出力形式（`Required documents:`）と、パスの実在確認を持つ helper。

query wrapper の出力契約は backend によらず共通である。形式の構築と、現在の
作業ツリーに実在しないパスの除外を、backend ごとに持たずここへ集める。

## 依存

Python 標準ライブラリのみ。
"""

from __future__ import annotations

from pathlib import Path

#: 検索結果ヘッダ（query wrapper の出力契約）
REQUIRED_DOCUMENTS_HEADER = "Required documents:"


def build_required_documents(paths) -> str:
    """`Required documents:` 文字列を決定論的に構築する。

    各項目には path だけを出力する。0 件（全件除外を含む）は空のヘッダのみ。
    """
    paths = list(paths)
    if not paths:
        return REQUIRED_DOCUMENTS_HEADER + "\n"
    lines = "\n".join(f"- {path}" for path in paths)
    return f"{REQUIRED_DOCUMENTS_HEADER}\n\n{lines}\n"


def exists_within_root(path_text, project_root) -> bool:
    """path が現在の worktree 内に実在するか判定する（REQ-014 BL-005）。

    索引はバックエンド側の状態であり、応答の path は信頼境界の外にある。
    絶対パス・`../` を経由するパス・symlink 解決で root の外へ出るパスは、
    実在していても「現在の worktree に存在する文書」ではないため除外する。
    """
    candidate = Path(str(path_text))
    if candidate.is_absolute():
        return False
    root = Path(project_root).resolve()
    try:
        resolved = (root / candidate).resolve()
    except OSError:
        return False
    if root not in resolved.parents:
        # root 自身（`.`）も文書ではないため除外する
        return False
    return resolved.exists()


def filter_existing(paths, project_root) -> tuple:
    """実在する path だけを元の順序で残し、`(残った path, 除外件数)` を返す。"""
    paths = list(paths)
    existing = [path for path in paths if exists_within_root(path, project_root)]
    return existing, len(paths) - len(existing)
