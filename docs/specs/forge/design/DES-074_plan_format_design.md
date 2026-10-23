# 計画書 デフォルトフォーマット

プロジェクト固有の `plan_format.md` が見つからない場合に使用する汎用フォーマット。

作成原則: [plan_principles_spec.md](../../../../plugins/forge/docs/plan_principles_spec.md)

本文書は、計画書の形式と、複数のスキルが共有する `feature_marker.py` の並行状態判定の契約を定義する開発文書である（配布物ではない）。AI はランタイムでこの文書を読まない。計画書を消費する `start-implement` の script の契約は、[DES-088](../../start-implement/design/DES-088_start_implement_design.md) が定める。

要件: [REQ-024 実装計画書 要件定義書](../requirements/REQ-024_implementation_plan_spec.md)

## フォーマット選定理由

計画書は JSON を使用する。理由:

- タスクID・優先度・依存関係・ステータス等、全てが構造化データ
- `start-implement` が機械的にパース・更新する必要がある（タスク選択・依存チェック・完了更新）
- Markdown テーブルは AI によるパースが不確実（列幅崩れ・`<br>` 改行等）
- 生成・読取・検証を script（標準ライブラリ `json`）に一元化することで、AI がファイル形式を意識する必要をなくす

要件定義書・設計書は mermaid や自由記述を含むため Markdown を維持する。

---

## 追加 feature の計画書（frontmatter を付与しない）

計画書には frontmatter を付与しない。追加 feature に属する計画書かどうかは、`requirements_traceability` が参照する要件定義書の `feature_type: temporary-feature` frontmatter で辿って判定する。計画書自体に重複してマーカーを持たせる必要はない。

トップレベルキーは `requirements_traceability` / `design_traceability` / `tasks` のみ許容する（それ以外の追加は 🟡 major 違反）。

frontmatter 定義: [frontmatter_format.md](../../../../plugins/forge/docs/frontmatter_format.md) §1.3
判定基準・旧仕様の置き換え・merge 手順: [additive_development_spec.md](../../../../plugins/forge/docs/additive_development_spec.md) §1 適用条件

---

## JSON スキーマ

ファイル名: `{feature}_plan.json`

```json
{
  "requirements_traceability": [
    {
      "requirement_id": "REQ-001",
      "title": "要件のタイトル",
      "design_id": "DES-001",
      "status": "pending"
    }
  ],
  "design_traceability": [
    {
      "design_id": "DES-001",
      "title": "設計書のタイトル",
      "requirement_ids": ["REQ-001"],
      "task_ids": ["TASK-001", "TASK-002"]
    }
  ],
  "tasks": [
    {
      "task_id": "TASK-001",
      "title": "タスクのタイトル",
      "priority": 90,
      "status": "pending",
      "design_id": "DES-001",
      "depends_on": [],
      "group_id": null,
      "build_check": "per_task",
      "description": ["やるべきこと 1", "やるべきこと 2", "やるべきこと 3"],
      "acceptance_criteria": "受け入れ基準の記述",
      "required_reading": ["path/to/design.md", "path/to/rule.md"]
    }
  ]
}
```

---

## フィールド定義

### requirements_traceability

| フィールド     | 型     | 必須 | 説明                    |
| -------------- | ------ | ---- | ----------------------- |
| requirement_id | string | Yes  | 要件ID                  |
| title          | string | Yes  | 要件のタイトル          |
| design_id      | string | Yes  | 対応する設計ID          |
| status         | enum   | Yes  | `pending` / `completed` |

### design_traceability

| フィールド      | 型       | 必須 | 説明                    |
| --------------- | -------- | ---- | ----------------------- |
| design_id       | string   | Yes  | 設計ID                  |
| title           | string   | Yes  | 設計書のタイトル        |
| requirement_ids | string[] | Yes  | 対応する要件ID の配列   |
| task_ids        | string[] | Yes  | 対応するタスクID の配列 |

### tasks

| フィールド          | 型          | 必須 | 説明                                                                                                                |
| ------------------- | ----------- | ---- | ------------------------------------------------------------------------------------------------------------------- |
| task_id             | string      | Yes  | タスクID（`TASK-001` 形式）。計画書内で一意。空文字列・空白のみは不可                                               |
| title               | string      | Yes  | タスクのタイトル                                                                                                    |
| priority            | integer     | Yes  | 優先度 1-99                                                                                                         |
| status              | enum        | Yes  | `pending` / `in_progress` / `implemented` / `completed` / `failed`                                                  |
| design_id           | string/null | Yes  | 対応する設計ID。なければ `null`                                                                                     |
| depends_on          | string[]    | Yes  | 依存するタスクID の配列。なければ `[]`                                                                              |
| group_id            | string/null | Yes  | タスクグループの ID と通し番号（`GROUP-001 (1/3)`）。独立したタスクは `null`                                        |
| build_check         | enum        | Yes  | `per_task`（完了時にビルドを確認）/ `skip`（確認しない）/ `on_group_complete`（タスクグループの最後のタスクで確認） |
| description         | string[]    | Yes  | やるべき内容の配列（1項目 = 1行）                                                                                   |
| acceptance_criteria | string/null | Yes  | 受け入れ基準。なければ `null`                                                                                       |
| required_reading    | string[]    | Yes  | 必読文書パスの配列。なければ `[]`                                                                                   |

---

## status の遷移

`status` の値は、上の表のとおりである。各値の意味は [REQ-024](../requirements/REQ-024_implementation_plan_spec.md) FNC-002 が、許される遷移と失敗の波及は [DES-088](../../start-implement/design/DES-088_start_implement_design.md) 6.3 が定める。

---

## 優先度の目安

| 範囲  | 意味                                               |
| ----- | -------------------------------------------------- |
| 70-99 | 高: コアビジネスロジック・共通基盤・ブロッカー解消 |
| 40-69 | 中: 主要機能                                       |
| 1-39  | 低: UI・補助機能                                   |

---

## `feature_marker.py` の並行状態判定の契約

要件: [REQ-025 差分開発の仕組み 要件定義書](../requirements/REQ-025_additive_development_spec.md) FNC-003（仕様の適用者への伝達）・FNC-005（識別できない場合の扱い）

### frontmatter の解析

文書先頭の YAML frontmatter（`---` で囲まれたブロック）から `feature_type` の値を取り出す。標準ライブラリのみで実装する（PyYAML 禁止）。この解析は複数の SKILL が再利用する汎用処理のため、共有低レベル script（`plugins/forge/scripts/doc_structure/feature_marker.py`）に置く。`/forge:start-implement` は、必読文書とレビューの規範のうち並行状態にある文書を求めるために、`/forge:start-design` は、入力の要件定義書の一時マーカーの有無を判定するために、同じ script を使う。

判定は次の 3 値のいずれかになる。

| 判定           | 条件                                                                           |
| -------------- | ------------------------------------------------------------------------------ |
| 並行状態にある | frontmatter に `feature_type` が 1 回だけ現れ、値が `temporary-feature` である |
| 並行状態にない | frontmatter を持たない、または frontmatter に `feature_type` が現れない        |
| 解析失敗       | 上記のいずれにも当てはまらない（下記の列挙）                                   |

解析失敗として扱うもの:

- 対象文書を読めない
- 先頭の `---` に対応する終端の `---` が無い
- `feature_type` が複数回現れ、値を一意に決められない
- `feature_type` の値が `temporary-feature` 以外である（[frontmatter_format.md](../../../../plugins/forge/docs/frontmatter_format.md) §1 は他の値を定義していない）

**キーの順序で判定結果が変わってはならない。** `frontmatter_format.md` §2.3 は `feature_type` と `doc_status` の併記を許可し、キーの順序を制約していない。`feature_note` はリスト値を持つため後続行がインデントされるが、これも `feature_type` の抽出に影響してはならない。規約が許可している書式のいずれかで解析が失敗する実装は、この契約に違反する。

解析失敗は「並行状態にない」と区別する（REQ-025 FNC-005）。並行状態にあるかを判定できないまま実装へ進むと、実装者は旧仕様に従って実装しうる。呼び出し側は、判定できないとき、先へ進まずに、対象のパスと理由を伝える。
