---
name: feature-marker
user-invocable: false
description: |
  文書が差分 feature の一時マーカー（frontmatter の `feature_type: temporary-feature`）を持つかを判定する。
  設計・計画・実装・仕様マージで、入力の文書が並行状態（差分開発の途中）にあるかを知りたいときに呼び出される。
argument-hint: "paths <文書のパス>... | dirs <ディレクトリ>..."
allowed-tools: Bash
---

# feature-marker スキル

このスキルは、文書の一時マーカーの有無の判定のみを行う。親が依頼している他の作業を引き継いではならない。

文書先頭の YAML frontmatter から `feature_type` の値を取り出し、`temporary-feature` を持つ文書を「並行状態にある」と判定する。`.doc_structure.yaml` には依存しない。

forge 内の他スキル・agent からの呼び出し専用（`user-invocable: false`）。呼び出し側は、本スキルを `Skill` ツールで呼ぶ。本スキルのスクリプトを直接呼ばない。

## 呼び出しの契約

### 入力（`Skill` ツールの `args`）

第 1 引数で判定の対象の種類を指定し、続けて対象を空白区切りで渡す（空白を含むパスは引用符で囲む）。

| 第 1 引数 | 続く引数                 | 判定の対象                                           |
| --------- | ------------------------ | ---------------------------------------------------- |
| `paths`   | 文書のパス（1 つ以上）   | 指定した文書。文書ごとの結果（`results`）も返る      |
| `dirs`    | ディレクトリ（1 つ以上） | 配下の `*.md` すべて。マーカーを持つ文書のパスが返る |

### 出力

| 項目            | 内容                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------ |
| `status`        | `ok` または `error`                                                                              |
| `any_marker`    | マーカーを持つ文書が 1 件でもあれば `true`                                                       |
| `marker_paths`  | マーカーを持つ文書のパス                                                                         |
| `checked_count` | 判定できた文書の件数                                                                             |
| `results`       | `paths` のときだけ。文書ごとの `{path, has_marker}`                                              |
| `errors`        | 判定できなかった文書とその理由。`status` が `error` のときだけ。理由を推測で補わず、そのまま返す |

## 手順

1. 入力の第 1 引数（`paths` / `dirs`）と対象を読み取る。どちらかが欠けていれば、不足として返し、判定しない
2. 次を実行する

   ```bash
   SCRIPT="${CLAUDE_SKILL_DIR}/scripts/feature_marker.py"

   python3 "$SCRIPT" --paths <文書のパス>...
   python3 "$SCRIPT" --dirs <ディレクトリ>...
   ```

3. stdout の JSON を、そのまま呼び出し側へ返す。終了コードが 1 のときは、`errors` を添えて返す（判定できなかった文書を「マーカー無し」として扱わない）

## 動作概要

- frontmatter が無い文書は、マーカー無し
- `feature_type` が `temporary-feature` 以外の値、複数回の出現、frontmatter の終端の欠落は、判定不能（`errors`）
- 標準ライブラリのみで実装する
