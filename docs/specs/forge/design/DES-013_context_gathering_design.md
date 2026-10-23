# DES-013 コンテキスト収集タスク仕様

## 1. 概要

forge の create-\* スキルが使用するコンテキスト収集タスクの仕様を定義する。

コンテキスト収集は、各 SKILL.md（またはモード別ワークフロー文書）にインラインで定義した prompt で汎用 agent を **Agent ツールで並列起動**し、各 agent の **return value**（markdown bullet list）を main AI コンテキストに直接保持する方式で行う（DES-022 並列 agent 出力契約）。

- 文書検索は agent 内から `/forge:query-db-specs` / `/forge:query-db-rules` スキルに委譲する（検索ロジックを収集 agent に持たせない）
- セッションディレクトリ・中間ファイルは使わない
- agent がエラー終了した場合は該当カテゴリなしで後続工程に進む（fail-open）

---

## 2. タスク一覧

コンテキスト収集 agent が実行するタスクは以下の 3 種類:

| タスク名       | 出力（return value）               | 検索手段                 | 説明                                     |
| -------------- | ---------------------------------- | ------------------------ | ---------------------------------------- |
| 仕様書調査     | `## 仕様書 (N 件)` + bullet list   | `/forge:query-db-specs`  | 要件定義書・設計書・計画書を特定         |
| 実装ルール調査 | `## ルール (N 件)` + bullet list   | `/forge:query-db-rules`  | プロジェクト固有の開発ルール・規約を特定 |
| 既存コード調査 | `## 既存実装 (N 件)` + bullet list | `Grep` / `Glob` 直接探索 | 関連ソースコード・テスト・類似実装を特定 |

bullet list の各行は `` `path` — 関連理由を 1 行 `` の形式とする。見出しの文言・件数上限は各 SKILL.md の prompt テンプレートが確定する。

---

## 3. スキル別タスク適用マトリクス

start-design / start-plan / start-requirements の適用マトリクス・agent 構成は [DES-010](DES-010_create_skills_orchestrator_design.md) §3〜§4 を正本とする。`start-implement` はコンテキスト収集 agent を起動せず、本文書の対象外である（[DES-088](../../start-implement/design/DES-088_start_implement_design.md)）。

---

## 4. agent への指示

各 agent への指示は「検索目的・検索手段・出力契約」の3要素で構成する prompt テンプレートで渡す。テンプレートの形式は [DES-010](DES-010_create_skills_orchestrator_design.md) §3.3 を正本とする。

セッションディレクトリや外部仕様書パスは渡さない。agent は prompt だけで自己完結して動作する（REQ-001 FNC-003）。
