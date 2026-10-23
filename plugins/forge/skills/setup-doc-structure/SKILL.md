---
name: setup-doc-structure
description: |
  プロジェクトのディレクトリをスキャン・分類し .doc_structure.yaml を対話的に生成する。
  forge が文書を参照するための必須初期設定。
  トリガー: "forge の初期設定", "doc structure を作成", "ドキュメント構成", "setup"
user-invocable: true
argument-hint: ""
---

# /forge:setup-doc-structure

このスキルは、`.doc_structure.yaml` の作成・更新のみを行う。親が依頼している他の作業を引き継いではならない。

## 概要

対話的に `.doc_structure.yaml` をプロジェクトルートに作成・更新する。
このファイルはドキュメントの所在を宣言し、他のツール（Doc Advisor, forge 等）がドキュメントを参照できるようにする。

## 実行規則

- プランモードが有効な場合は解除すること。プランモードの解除についてユーザーへの確認は不要。
- `.doc_structure.yaml` がすでに存在する場合は**レビューモード**に切り替えること（現在の内容を表示し、「生成内容の不変条件」に反する箇所と変更を提案する）。
- `.doc_structure.yaml` を書き込む前に、必ず Step 5 で書き込む内容の全文を提示して承認を得る。承認なしに書き込まない。

## 生成内容の不変条件 [CRITICAL]

`.doc_structure.yaml` を生成・更新するときに必ず満たす条件。Step 1 のレビューと Step 5 の提示の両方で照合する。

1. **forge が置き場を解決する doc_type を宣言する**: specs の `root_dirs` と `doc_types_map` に、doc_type `requirement` / `design` / `plan` / `adr` のエントリをそれぞれ**ちょうど 1 つ**置く。forge は要件定義書・設計書・計画書・ADR の作成先・読込先を `doc_types_map` の該当エントリから解決するため、宣言が無いと要件定義・設計・計画・実装・ADR 記録のスキルが止まる。エントリが複数あると置き場を一意に決められず、同じく止まる。キーの形は specs の構成に揃える（Feature ごとの構成なら `docs/specs/**/plan/` のような glob、フラットな構成なら `docs/specs/plan/`）。スキャンで検出されなかったものも宣言するが、ディレクトリは作らない（各スキルが文書の作成時に作る）
2. **plan を索引から除外する**: specs の `patterns.exclude` に、plan エントリの末尾のディレクトリ名（通常は `plan`）を入れる。計画書・実装戦略書・タスクコンテキストは実装の完了後に破棄しうる一時文書であり、検索索引に載せると、破棄後に実在しない文書を指す索引が残る。除外は索引の範囲だけを決め、置き場の解決には影響しない（1 の宣言と両立する）
3. **作成したディレクトリを宣言する**: Step 4 で作成したディレクトリは、すべて `root_dirs` と `doc_types_map` に含める

## Procedure

### Step 1: 既存ファイルの確認

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doc_structure/check_doc_structure.py
```

JSON 出力に応じて分岐する:

- **`exists: false`** → Step 2 へ。
- **`error` あり** → エラー内容をユーザーに報告して終了。
- **`exists: true`** →
  1. `needs_migration: true` の場合 → AskUserQuestion を使用して「.doc_structure.yaml を v{detected_version} → v{current_version} にマイグレーションしますか？」と確認
     - Yes → `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doc_structure/migrate_doc_structure.py <path>` で変換結果を取得し、Write で書き出す
     - No → 手順 2 へ
  2. `content` を表示し、上記「生成内容の不変条件」に照らして反する箇所を列挙する（反する箇所が無ければその旨を示す）。反する箇所ごとに、どう直すかの案を添える
  3. AskUserQuestion を使用して方針を確認する
     - **更新する** → Step 2 へ（既存の分類結果をベースにスキャン・再分類。手順 2 で列挙した箇所は修正案を反映した状態で候補リストに載せる）
     - **再生成する** → 既存の分類結果を使わず Step 2 へ（ゼロから生成）。既存ファイルは削除せず、Step 6 で承認された内容に置き換える（Step 5 で中止すれば元のまま残る）
     - **このまま使う** → 完了（変更なし）

### Step 2: ディレクトリスキャン + 候補リスト作成

#### 2-1: 自動スキャン

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doc_structure/classify_dirs.py
```

スキャン結果（JSON）を取得する。`readme_only: true` のディレクトリは分類対象外としてスキップする。

> **注意**: classify_dirs.py は浅いスキャン（親ディレクトリに .md ファイルがある場合、サブディレクトリは検出されない）のため、後続の「空ディレクトリの補完」Glob 探索は必須。

空ディレクトリの補完: ドキュメント系の親ディレクトリ（`docs/`, `rules/`, `specs/` 等）配下のサブディレクトリを Glob で探索し、スキャン結果にないものも候補に追加する。

#### 2-2: AI 分類判定

同ディレクトリの `classification_rules.md` を Read し、そのルールに従ってスキャン結果の各ディレクトリに category と doc_type を割り当てる。

**進捗表示**: 各ディレクトリの判定ごとに結果をユーザーに表示すること。

#### 2-3: 推奨ディレクトリの補完

スキャン結果に含まれない推奨ディレクトリを「未検出（推奨）」として候補リストに追加する。

推奨ディレクトリ（スキャンで検出されなかった場合のみ追加）:

| パス              | doc_type  | 説明                                                      |
| ----------------- | --------- | --------------------------------------------------------- |
| `docs/specs/`     | —         | 仕様書ベースディレクトリ（requirements/design/plan の親） |
| `docs/rules/`     | rule      | 開発ルール・規約                                          |
| `docs/reference/` | reference | 参考文献・技術調査メモ（今後利用予定）                    |

`requirement` / `design` / `plan` / `adr` は推奨ディレクトリとして作成せず、検出されなかった場合も「常に宣言」として候補リストに載せる（「生成内容の不変条件」1）。

> スキャンで類似ディレクトリが検出済みの場合（例: `rules/` が既にある場合に `docs/rules/` は推奨しない）、重複する推奨は追加しない。

> **Feature ディレクトリについて**: 既存の Feature ディレクトリ（`docs/specs/{feature}/requirements/` 等）は Step 2 のスキャンで自動検出し、glob パターン（例: `docs/specs/*/requirements/`）として `.doc_structure.yaml` に設定する。ただし、まだ存在しない Feature の空ディレクトリをここで作成はしない。新規 Feature のディレクトリは `start-requirements` / `start-design` / `start-plan` が作業開始時に作成する。

### Step 3: 候補の対話的確認

スキャン結果と推奨ディレクトリを統合した**候補リスト**をユーザーに提示する。

> **重要**: スキャン結果はあくまで候補である。ユーザーが見ていない場所にディレクトリがある可能性もある。全ての候補について確認を取り、ユーザーの指示に従う。

#### 3-1: パターン A — ディレクトリが検出された場合

テキスト出力:

```
## ドキュメントディレクトリ候補

検出済み:
  1. ✅ docs/rules/                       — rule        （根拠: 親ディレクトリ名 rules）
  2. ✅ docs/specs/<feature>/design/       — design      （根拠: ディレクトリ名 design）
  3. ✅ docs/specs/<feature>/requirements/ — requirement （根拠: ディレクトリ名 requirements）
     → glob パターン: docs/specs/**/design/, docs/specs/**/requirements/

未検出（推奨）:
  4. ☐ docs/reference/                   — 参考文献（今後利用予定）

常に宣言（未検出でも宣言する。ディレクトリは作らない）:
  - docs/specs/**/plan/                  — plan（計画書の置き場。検索索引から除外。「生成内容の不変条件」1・2）
  - docs/specs/**/adr/                   — adr（ADR の置き場。「生成内容の不変条件」1）
```

各候補には、分類の根拠（どのパスコンポーネント・frontmatter・本文から判定したか）を必ず添える。根拠が無いと、利用者は分類を変えるべきかを判断できない。

AskUserQuestion を使用して方針を確認する:

| 選択肢                         | 説明                                                              |
| ------------------------------ | ----------------------------------------------------------------- |
| この候補で確定                 | 検出済みディレクトリと「常に宣言」で内容を組み立て、Step 5 で確認 |
| 不足ディレクトリを作成して追加 | 未検出（推奨）から選択し、.gitkeep 付きで作成                     |
| 候補を修正                     | 分類の変更、パスの追加・除外など                                  |
| （Other）                      | 別のパスを指定したい等 — 自動提供                                 |

#### 3-2: パターン B — ディレクトリが検出されなかった場合

テキスト出力:

```
## ドキュメントディレクトリ候補

ドキュメントディレクトリが検出されませんでした。
推奨構成を提案します:

  ☐ docs/specs/      — 仕様書ベースディレクトリ（requirements/design/plan の親）
  ☐ docs/rules/      — 開発ルール・規約
  ☐ docs/reference/  — 参考文献（今後利用予定）

常に宣言（未検出でも宣言する。ディレクトリは作らない）:
  - docs/specs/**/requirements/ — requirement（要件定義書の置き場。「生成内容の不変条件」1）
  - docs/specs/**/design/       — design（設計書の置き場。「生成内容の不変条件」1）
  - docs/specs/**/plan/         — plan（計画書の置き場。検索索引から除外。「生成内容の不変条件」1・2）
  - docs/specs/**/adr/          — adr（ADR の置き場。feature ごとに 1 ファイル。「生成内容の不変条件」1）
```

AskUserQuestion を使用して方針を確認する:

| 選択肢             | 説明                                                           |
| ------------------ | -------------------------------------------------------------- |
| 推奨構成を全て作成 | specs/ + rules/ + reference/ を .gitkeep 付きで作成            |
| 選択して作成       | 作成するディレクトリを個別に選択                               |
| 作成しない         | ディレクトリ作成をスキップ（.doc_structure.yaml も生成しない） |
| （Other）          | 自分でパスを指定したい等 — 自動提供                            |

#### 3-3: 詳細選択（条件分岐）

**「不足ディレクトリを作成して追加」または「選択して作成」の場合:**

AskUserQuestion（multiSelect）で作成するディレクトリを選択させる。
選択肢は未検出項目または推奨項目から動的に生成する（最大4件。超過時は複数回に分割）。
選択されたディレクトリを Step 4 で作成する。

**「候補を修正」の場合:**

AskUserQuestion を使用して修正内容を確認する:

| 選択肢             | 説明                                                                      |
| ------------------ | ------------------------------------------------------------------------- |
| 分類を変更         | 既存ディレクトリの category/doc_type を修正（例: 2番を reference に変更） |
| ディレクトリを除外 | 候補から除外するディレクトリを指定                                        |
| ディレクトリを追加 | 候補にないパスを追加                                                      |

「分類を変更」では、対象の候補を選ばせたうえで、その候補が取りうる値を選択肢として示す。操作の種類だけを示して値を利用者に考えさせない。

- category: rules / specs
- doc_type: category に応じた doc_type 定義（下記「doc_type 定義」の表）から、根拠に照らして候補になるもの
- glob の形: 同じ doc_type を Feature ごとに持つ構成では `*`（1 階層）と `**`（任意の深さ）

修正を適用後、再度候補リストを表示して方針選択に戻る（確認ループ）。
ユーザーが追加したパスが存在しない場合 → 作成するか AskUserQuestion を使用して確認する。

#### Feature の扱い

- 既存 Feature（`docs/specs/<feature>/` 配下）はスキャンで自動検出する
- AI が glob パターン（`docs/specs/**/design/` 等）を推定し、.doc_structure.yaml に設定する
- ユーザーが「Other」で新しい Feature パスを指定した場合 → 存在しなければ作成を提案
- Feature 名を引数として受け取らない（Feature はテンポラリーであり、スキャンで検出するもの）

### Step 4: ディレクトリ作成

Step 3 で作成を選択されたディレクトリについて:

1. `mkdir -p` でディレクトリを作成
2. 空ディレクトリに `.gitkeep` を配置
3. 作成結果を一覧表示

```
ディレクトリを作成しました:
  ✅ docs/specs/.gitkeep
  ✅ docs/rules/.gitkeep
  ✅ docs/reference/.gitkeep
```

作成したディレクトリを候補リストの「検出済み」に追加し、Step 5 へ進む。

> Step 3 でディレクトリ作成が不要だった場合（「この候補で確定」「作成しない」選択時）、この Step はスキップする。

### Step 5: 書き込む内容の提示と確認

確定した分類結果から `.doc_structure.yaml` の内容を組み立てる。forge が使用するフィールド（`root_dirs` / `doc_types_map` / `patterns`）のみを生成する（Quick reference のテンプレートを参照）。**この時点ではまだ書き込まない。**

組み立てた内容を「生成内容の不変条件」と照合し、反する箇所があれば直してから、次の 2 つを利用者に提示する:

1. 書き込む YAML の全文
2. エントリごとの対応表: パス、category、doc_type、根拠、索引の対象か（`exclude` で外れるか）

Step 3 の候補リストに現れない値（glob の形、`patterns.exclude`、「常に宣言」のエントリ等）も、この提示で初めて利用者の目に触れる。提示を省略してはならない。

AskUserQuestion を使用して確認する:

| 選択肢             | 説明                                                         |
| ------------------ | ------------------------------------------------------------ |
| この内容で書き込む | Step 6 へ                                                    |
| 項目を変更する     | Step 3-3「候補を修正」と同じく、対象と取りうる値を示して修正 |
| 中止する           | 書き込まずに終了する（Step 4 で作成したディレクトリは残る）  |

「項目を変更する」の場合は、修正を適用して本 Step の提示からやり直す（確認ループ）。

### Step 6: .doc_structure.yaml の書き出し

Step 5 で承認された内容を、そのままプロジェクトルートの `.doc_structure.yaml` へ書き出す。承認後に内容を変えない。

### Step 7: 結果表示

生成したファイルの内容を表示し、次のステップを案内する:

```
.doc_structure.yaml を作成しました。

作成したディレクトリ:（Step 4 で作成した場合のみ表示）
  - docs/rules/
  - docs/reference/

次のステップ:
- forge が .doc_structure.yaml を直接参照してレビュー・修正時の参考文書を収集します
- .doc_structure.yaml をバージョン管理にコミットしてください
- 設定を変えたいときは、このスキル（forge の setup-doc-structure）を再実行してください（既存ファイルのレビューモードで変更できます）
```

---

## Schema Reference

See: `${CLAUDE_PLUGIN_ROOT}/docs/doc_structure_format.md`

### Quick reference

```yaml
# doc_structure_version: 3.0

# === rules configuration ===
rules:
  root_dirs:
    - <dir_path>
  doc_types_map:
    <dir_path>: <doc_type>
  patterns:
    target_glob: "**/*.md"
    exclude: []

# === specs configuration ===
specs:
  root_dirs:
    - <requirement_dir_path>
    - <design_dir_path>
    - <plan_dir_path>
    - <adr_dir_path>
    - <dir_path>
  doc_types_map:
    <requirement_dir_path>: requirement
    <design_dir_path>: design
    <plan_dir_path>: plan
    <adr_dir_path>: adr
    <dir_path>: <doc_type>
  patterns:
    target_glob: "**/*.md"
    # plan の置き場の末尾ディレクトリ名（生成内容の不変条件 2）
    exclude:
      - plan
```

requirement / design / plan / adr の 4 エントリは常に置く（生成内容の不変条件 1）。`<dir_path>: <doc_type>` はそれ以外に検出・作成したディレクトリである。

### 生成例（Feature-Based）

```yaml
# doc_structure_version: 3.0

rules:
  root_dirs:
    - docs/rules/
  doc_types_map:
    docs/rules/: rule
  patterns:
    target_glob: "**/*.md"
    exclude: []

specs:
  root_dirs:
    - "docs/specs/**/adr/"
    - "docs/specs/**/design/"
    - "docs/specs/**/plan/"
    - "docs/specs/**/requirement/"
  doc_types_map:
    "docs/specs/**/adr/": adr
    "docs/specs/**/design/": design
    "docs/specs/**/plan/": plan
    "docs/specs/**/requirement/": requirement
  patterns:
    target_glob: "**/*.md"
    exclude: [plan]
```

glob パターン（`*` または `**`）を使う場合、root_dirs と doc_types_map の両方に同じパターンを記述する。`*` は1階層のみ、`**` は任意の深さにマッチする。サブ Feature がある場合は `**` を推奨。

### doc_type 定義（固定。全プロジェクト・全プラグインで共通）

| category | doc_type    | 意味                                   | 含まれる文書の例                                                                      |
| -------- | ----------- | -------------------------------------- | ------------------------------------------------------------------------------------- |
| rules    | rule        | 開発プロセスのルール・規約・手順       | コーディング規約、命名規則、Git ワークフロー、レビュー手順、CI/CD ルール              |
| specs    | requirement | 「何を実現するか」のゴール定義         | ユーザーストーリー、機能要件、非機能要件、ビジネスルール、受入条件                    |
| specs    | design      | 「どう構成するか」の技術的構造         | アーキテクチャ設計、DB スキーマ設計、画面設計、シーケンス図、状態遷移図               |
| specs    | plan        | 「どの順で作るか」の作業計画           | タスク分割、実装順序、マイルストーン、スプリント計画、移行計画                        |
| specs    | adr         | 採らなかった案とその理由の決定記録     | 優れた方式がありそうなのに採らなかった決定（feature ごとに 1 ファイル）               |
| specs    | api         | 外部インターフェースの契約             | REST エンドポイント定義、リクエスト/レスポンス仕様、OpenAPI/Swagger、GraphQL スキーマ |
| specs    | reference   | 判断の根拠となる補助文書               | 技術調査メモ、比較検討資料、外部仕様の要約、議事録、用語集                            |
| specs    | spec        | 上記に該当しない仕様文書（デフォルト） | 分類不明な仕様文書の一時的な受け皿                                                    |
