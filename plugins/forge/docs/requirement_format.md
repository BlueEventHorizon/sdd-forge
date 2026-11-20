---
doc_link_id: DLID-c13gr4qbk4vm
---

# 要件定義書 デフォルトフォーマット DLID-xce107ay8m4n

プロジェクト固有の「要件定義書 フォーマット」が見つからない場合に使用する汎用フォーマット。

作成原則: [spec_priorities_spec.md][spec-priorities-spec]
要件との境界: [spec_design_boundary_spec.md][spec-design-boundary-spec]

---

## 追加 feature 用 frontmatter DLID-zxhcbgbna01e

**[additive_development_spec.md][additive-development-spec] §1 の判定で追加 feature に該当する要件定義書を作成するときに限り**、文書先頭に以下の YAML frontmatter を含めること。判定は変更の実質（分離管理価値・旧仕様との衝突リスク）で行い、文書操作の形式（新規作成か追記か）では判定しない。分離して管理する価値のない軽微な追記・修正、および既存仕様が存在しない初回立ち上げ時は含めない。

この要件定義書は、その対象範囲において旧仕様を置き換えている。旧仕様の記述はまだ更新されていないだけである。文書全体がこの性質を持つため、本文ブロックではなく frontmatter にメタ情報として宣言する。

`feature_type: temporary-feature` を付与し、feature_note に①この文書が対象範囲における現在の仕様であり旧仕様の記述は置き換わっていること②旧仕様ファイルは書き換えず新規ファイル・新規ディレクトリへ切り出すこと③実装完了後に旧仕様との齟齬を解消する（merge）こと④同一スコープの内容は旧仕様側へ移しスコープが異なる内容は分離維持すること、の4点を記載する。frontmatter の正式な文言は [frontmatter_format.md][frontmatter-format] §1.1 を参照。

全文書種別（要件・設計・計画）の frontmatter 集約 SoT: [frontmatter_format.md][frontmatter-format]
判定基準・旧仕様の置き換え・merge 手順: [additive_development_spec.md][additive-development-spec] §1

---

## 要件ID カタログ DLID-j4h05z7z0r5x

プロジェクトの性質に合わせて必要なものを選んで使用する。使わない ID は定義しない。

| ID prefix   | 対象               | 主な用途                                                      |
| ----------- | ------------------ | ------------------------------------------------------------- |
| `APP-xxx`   | アプリ概要         | アプリの目的・価値・主要機能の概要定義                        |
| `SCR-xxx`   | 画面               | 画面ごとの表示要件・操作要件（UI を持つプロジェクト）         |
| `CMP-xxx`   | UI コンポーネント  | 再利用可能な UI コンポーネントの要件                          |
| `THEME-xxx` | デザイントークン   | カラー・タイポグラフィ・スペーシング等のデザイン定義          |
| `NAV-xxx`   | ナビゲーション     | 画面遷移・ルーティング構造                                    |
| `FNC-xxx`   | 機能要件           | ユーザーが実行できる操作・システムの振る舞い                  |
| `BL-xxx`    | ビジネスロジック   | 計算ルール・バリデーション・業務ルール                        |
| `DM-xxx`    | データモデル       | エンティティ定義・保存データの構造                            |
| `API-xxx`   | API エンドポイント | REST/GraphQL 等のエンドポイント仕様（バックエンド・外部連携） |
| `EXT-xxx`   | 外部連携           | 外部サービス・SDK・ライブラリとの連携要件                     |
| `NFR-xxx`   | 非機能要件         | 性能・可用性・スケーラビリティ等                              |
| `SEC-xxx`   | セキュリティ       | 認証・認可・データ保護要件                                    |
| `ERR-xxx`   | エラー定義         | エラーコード・エラーハンドリング方針                          |
| `INT-xxx`   | インテグレーション | サービス間連携・イベント・メッセージング                      |
| `BUG-xxx`   | バグ報告           | 不具合修正・既知バグのトラッキング                            |
| `GLS-xxx`   | 用語集             | 特有の意味を持つ語の定義（要件側。書式は文書スタイル指針 §9） |

---

## 本体フォーマット DLID-6qbgqbk1xcw9

```markdown
<!-- 追加 feature の場合、ここに上記 frontmatter を挿入する -->

# {要件ID} {機能名} 要件定義書

用語集: {用語集の ID。用語集がある場合のみ。複数あるときは `、` で区切る}

## 概要

{この要件の目的・対象ユーザー・その機能がユーザーにもたらす価値を1〜3文で記述}

## 前提条件

- {この機能が利用可能になる条件}

## 要件一覧

### 表示要件

- {画面に表示される要素}

### 操作要件

- {ユーザーが実行できるアクション}
- 入力: {入力値の制約}
- 出力/遷移先: {結果や画面遷移}

### エラーケース

| 条件 | 分類（回復可能 / 回復不能） | 回復の手段 / 利用者への報告 |
| ---- | --------------------------- | --------------------------- |

## 未確定事項

| ID      | 内容 | 期限 |
| ------- | ---- | ---- |
| TBD-001 |      |      |
```

### エラーケースの書き方 DLID-pzsvndgxcyfb

エラーケース節の分類は [error_classification_spec.md][error-classification-spec] §3 に従う。回復可能なエラーには回復の手段を、回復不能なエラーには利用者へ報告する内容を書く。判定できる事象（同 §2.1）はエラーではないので、この節に書かない。

---

## 重大度カタログ DLID-6ygh93jm4py6

本フォーマットの各規範を、違反時の重大度に対応付ける。レビュー時の severity 判定はこの表を SoT とする。criteria 側で重大度を判定してはならない。

### 追加 feature 用 frontmatter DLID-29nvbbd9e3rm

判定（追加 feature か否か）は [additive_development_spec.md][additive-development-spec] §1（適用条件 / 対象外）に従う。判定は変更の実質（分離管理価値・旧仕様との衝突リスク）で行い、既存仕様が存在しない初回立ち上げ、および分離して管理する価値のない軽微な追記・修正は対象外（false positive 防止）。

| 違反パターン                                                                 | 違反時の重大度 | 理由                                                                                    |
| ---------------------------------------------------------------------------- | -------------- | --------------------------------------------------------------------------------------- |
| 追加 feature 要件定義書に `feature_type: temporary-feature` frontmatter 欠如 | 🟡 major       | 当該範囲の現在の仕様であることと merge 予定が宣言されず、生成経路を問わず取りこぼされる |

[spec-priorities-spec]: spec_priorities_spec.md "f8233c87c564 DLID-f9ny9e932trv"
[spec-design-boundary-spec]: spec_design_boundary_spec.md "4e2a4cd68a8a DLID-h9h90g9wcy8f"
[additive-development-spec]: additive_development_spec.md "307dc53425f0 DLID-cyrk9xr8vcap"
[frontmatter-format]: frontmatter_format.md "19cf661699b0 DLID-jtc4qnjwbdxf"
[error-classification-spec]: error_classification_spec.md "04397ae80f5c DLID-5ykqs19cdbks"
