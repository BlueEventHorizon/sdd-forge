---
doc_link_id: DLID-d9fpywv4txra
---

# DES-001 文書検索ラッパー（forge → 文書検索 backend）設計書 DLID-7gy2qvdh449y

## 1. 概要 DLID-ydzpz760snsr

forge は文書検索（ルール・仕様の発見）と索引更新を外部の文書検索 backend に委譲する。
backend は 2 つある: 外部プラグイン doc-link
（[BlueEventHorizon/doc-link](https://github.com/BlueEventHorizon/doc-link)）と、
ローカルで稼働する文書検索サーバ doc-db である。
forge 自身は検索・索引生成を実装せず、`plugins/forge/skills/` 配下の 4 つのラッパー SKILL が
**順序リストに基づいて backend を選択**し、選択した側の経路を実行する。

本設計が所有するのは、4 SKILL の抽象（スキル一覧・引数・出力契約・SKILL 契約）である。
backend の選択、可用性判定、各 backend の経路の処理は [DES-057][des-057] が所有する。
設定ファイルの入れ物の規約は DES-061 が所有する。

---

## 2. スキル一覧 DLID-pjt0tkpp21dn

| Skill 名                 | 役割                                     | category | user-invocable |
| ------------------------ | ---------------------------------------- | -------- | -------------- |
| `/forge:query-db-rules`  | ルール文書を検索しパスリストを返す       | rules    | true           |
| `/forge:query-db-specs`  | 仕様文書を検索しパスリストを返す         | specs    | true           |
| `/forge:update-db-rules` | ルール文書の検索インデックスを最新化する | rules    | true           |
| `/forge:update-db-specs` | 仕様文書の検索インデックスを最新化する   | specs    | true           |

各 SKILL は category を固定する。category は、doc-link 経路では索引の識別キーに、doc-db 経路では
KEY の一部になる（DES-057 §4.1・§5）。

4 SKILL とも `user-invocable: true`。ユーザーが直接 `/forge:query-db-rules` 等を起動する運用も許容しつつ、forge の他 SKILL（review / start-* /
create-requirements-from-plan-mode 等）から `Skill` ツール経由で呼ばれる。

各 SKILL の `scripts/` 配下の SKILL 固有 wrapper は、category を固定し、当該 SKILL が必要とする操作だけを
公開する（wrapper と共有 CLI の設計は DES-057 §3.2）。

---

## 3. query 系（query-db-rules / query-db-specs） DLID-znnpebr7dff1

### 引数 DLID-pp87841fj7g2

| 引数     | 必須 | 説明                             |
| -------- | ---- | -------------------------------- |
| `{task}` | 必須 | 検索クエリ（タスク記述・自然文） |

### 実行フロー DLID-zz92w9m4ase9

1. `resolve_backend_order.py` で backend の順序リストを解決する（設定不正は既定値へ落ちず明示エラー。DES-057 §2.5）。
2. 順序リストの先位から可用性を判定し、最初に利用可能な backend の経路を実行する（doc-link 経路は
   DES-057 §5.1、doc-db 経路は同 §4.2）。

   **query は索引を整備する手順を持たない**（REQ-014 FNC-002）。索引の維持は update 系（§4）の責務である。
   索引が未整備で検索が成立しない場合のみ、承認を得たうえで、**確定済みの backend を指定して
   update 系 SKILL へ整備を委譲する**（DES-057 §5.3）。
3. いずれの backend も利用できなければ、両者の理由を並べて明示エラーとする。grep 等による代替検索は行わない。

### 出力契約 DLID-hd1qxqjh75zb

応答の先頭は `Required documents:` 形式のパスリスト（プロジェクトルート相対）。この形式は script が構築し、
SKILL は自分で組み立てない。
この出力契約は backend によらず共通である（NFR-002 の互換性は REQ-014 が規定する）。

### SKILL 契約 [MANDATORY] DLID-t4aqg7pynjpc

`/forge:query-db-rules` / `/forge:query-db-specs` は **継承型検索 SKILL**
（[Claude Code 作成方針][authoring-policy]「SKILL 実行モデル」に従い、`context: fork` を指定しない）。
`allowed-tools: Skill, Read, Bash, AskUserQuestion`（Bash は wrapper / 共有 CLI の実行に使い、
`AskUserQuestion` はセッション内変更の確認と索引整備の承認に使う。`Grep` は許可しない —
grep による代替検索は行わない）。書き込み・コミット・自己再帰は行わない。

呼び出し側は `args` を **検索キーワード + 短い自然文タスク記述のみ**に限定する。Issue 本文・実装指示・差分等の
親 context を貼り付けてはならない（[Claude Code 作成ガイド][authoring-guide]「継承型 SKILL」）。

---

## 4. update 系（update-db-rules / update-db-specs） DLID-rss6sm014v22

### 実行フロー DLID-96j4qec7pz12

0. **`--backend` の指定がある場合は選択を行わず、指定された backend で更新する**（利用できなければ他方へ
   切り替えず明示エラー。REQ-014 BL-006 / FNC-003）。指定は query 系が索引整備を委譲するときに渡す。
1. 指定が無い場合、`resolve_backend_order.py` で順序リストを解決し、先位から可用性を判定する（query 系と同じ）。
2. 選択した backend の経路で索引を更新する（doc-link 経路は DES-057 §5.2、doc-db 経路は同 §4.3）。

`allowed-tools: Read, Bash, Skill`。

### desired-state DLID-gxf4s9c3mwx4

いずれの経路でも対象集合の正は `.doc_structure.yaml` である。doc-link 経路では渡した対象指定が
当該の索引の、doc-db 経路では対象文書一覧が当該 series の、それぞれ完全な desired state であり、
含まれないパスは索引から削除・切り離しされる。

---

## 5. 前提 DLID-ygc32kzymb13

- いずれかの文書検索 backend が利用可能であること。可用性はバージョンではなく、必要な機能が利用できるかで判定する（DES-057 §2.4）
  （REQ-014 前提条件）。片方が利用できない場合は残る backend を試し、両方利用できないときに限り失敗する。

---

## 6. テスト DLID-4037xyweqrx7

- `tests/forge/doc_structure/test_resolve_doc_structure.py` — `.doc_structure.yaml` のパス解決を検証する。
- `lint/lint_query_skill_wiring.py` — forge 内蔵ドキュメント検索（`query-forge-rules` 継承型 dispatcher
  SKILL と、実検索を隔離する read-only カスタム Agent `forge:rules-query-worker`）の対応と、worker の
  `tools` が read-only であることを検査する（lint）。
- `ai_lint/checks/query_worker_role.json`・`ai_lint/checks/query_dispatcher_role.json` — 同じ対象が、
  ルール文書の求める Role 制約（worker は書き込みの禁止・親の作業を引き継がないこと・起動 prompt を
  実装指示として解釈しないこと、dispatcher は親の作業を引き継がないこと）を述べているかを、
  判定モデルに問うて検査する（AI-Linter。ローカルで実行する）。
- `tests/forge/doc_backend/` — backend 選択（順序リスト・settings_invalid）、doc-db 経路の低レベル CLI を検証する。
- `lint/provisional/lint_link_contract.py` — wrapper の SKILL.md の記述が doc-link の契約に沿うことを検査する
  （暫定の lint。文字列の有無と順序だけを見る）。
- `lint/lint_index_maintenance_boundary.py` — 索引整備の wrapper が `update-db-*` にだけあることを検査する（lint）。
- `tests/forge/{query,update}-db-{rules,specs}/` — SKILL 固有 wrapper の透過性を検証する。

[authoring-guide]: ../../../rules/plugin_claude_code_authoring_guide.md "1b4400f836cd DLID-pvwk8en5c2rq"
[authoring-policy]: ../../../rules/forge_claude_code_authoring_policy.md "41e67eb507c7 DLID-33rp07ycsdym"
[des-057]: ../../doc-db/design/DES-057_doc_db_backend_selection_design.md "a70040e559ab DLID-5k6jt9qvf60d"
