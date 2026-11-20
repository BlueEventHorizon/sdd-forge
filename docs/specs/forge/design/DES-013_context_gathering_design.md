---
doc_link_id: DLID-1vfqj6r96sr4
---

# DES-013 コンテキスト収集タスク仕様 DLID-mq8v1rvrpd30

## 1. 概要 DLID-d17p2rv2vwvs

forge の create-\* スキルが使用するコンテキスト収集タスクの仕様を定義する。

コンテキスト収集は 2 種類ある。文書検索は、オーケストレータが `/forge:query-db-specs` / `/forge:query-db-rules` を Skill ツールで直接呼ぶ。既存コードの探索は、各 SKILL.md（またはモード別ワークフロー文書）にインラインで定義した prompt で汎用 agent を Agent ツールで起動し、agent の **return value**（markdown bullet list）を main AI コンテキストに直接保持する（DES-022 並列 agent 出力契約）。

- 文書検索に Agent を挟まない（理由は [DES-010](DES-010_create_skills_orchestrator_design.md) §3.1）
- セッションディレクトリ・中間ファイルは使わない
- 文書検索が失敗したとき、または agent がエラー終了したときは、後続工程へ進まず、利用者に報告して指示を待つ（[DES-010](DES-010_create_skills_orchestrator_design.md) §3.5）

---

## 2. タスク一覧 DLID-jh3wrycz00ap

コンテキスト収集のタスクは以下の 3 種類:

| タスク名       | 実行主体         | 出力                               | 検索手段                 | 説明                                     |
| -------------- | ---------------- | ---------------------------------- | ------------------------ | ---------------------------------------- |
| 仕様書調査     | オーケストレータ | 検索スキルが返す文書のパスの一覧   | `/forge:query-db-specs`  | 要件定義書・設計書・計画書を特定         |
| 実装ルール調査 | オーケストレータ | 検索スキルが返す文書のパスの一覧   | `/forge:query-db-rules`  | プロジェクト固有の開発ルール・規約を特定 |
| 既存コード調査 | 汎用 agent       | `## 既存実装 (N 件)` + bullet list | `Grep` / `Glob` 直接探索 | 関連ソースコード・テスト・類似実装を特定 |

agent の bullet list の各行は `` `path` — 関連理由を 1 行 `` の形式とする。見出しの文言・件数上限は各 SKILL.md の prompt テンプレートが確定する。

---

## 3. スキル別タスク適用マトリクス DLID-r3707pgmaj3v

start-design / start-plan / start-requirements の適用マトリクス・agent 構成は [DES-010](DES-010_create_skills_orchestrator_design.md) §3〜§4 を正本とする。`start-implement` はコンテキスト収集 agent を起動せず、本文書の対象外である（[DES-088](../../start-implement/design/DES-088_start_implement_design.md)）。

---

## 4. agent への指示 DLID-rq3pqqvfszw5

既存コード収集 agent への指示は「検索目的・検索手段・出力契約」の3要素で構成する prompt テンプレートで渡す。テンプレートの形式は [DES-010](DES-010_create_skills_orchestrator_design.md) §3.3 を正本とする。

セッションディレクトリや外部仕様書パスは渡さない。agent は prompt だけで自己完結して動作する（REQ-001 FNC-003）。
