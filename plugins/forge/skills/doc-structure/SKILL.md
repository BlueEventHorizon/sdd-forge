---
name: doc-structure
user-invocable: false
description: |
  プロジェクトが宣言した文書の置き場を解決する。文書の出力先ディレクトリ・feature・既存文書の所在・検索対象ディレクトリ・
  パスの種別を、他のスキル・agent に代わって求める。文書の置き場を知りたいときは、このスキルを呼ぶ。
argument-hint: "<操作> [名前=値 ...]"
allowed-tools: Bash, Skill, AskUserQuestion
---

# doc-structure スキル

このスキルは、文書の置き場の解決のみを行う。親が依頼している他の作業を引き継いではならない。

プロジェクトが `.doc_structure.yaml` で宣言した置き場（出力先・feature・種別・検索対象）を、呼び出し側に代わって解決する。宣言は置き場の案内であり、宣言したディレクトリやファイルが実在することを保証しない。

forge 内の他スキル・agent からの呼び出し専用（`user-invocable: false`）。呼び出し側は、本スキルを `Skill` ツールで呼び、結果だけを使う。本スキルのスクリプト・本スキルの文書・`.doc_structure.yaml` を、呼び出し側が直接読んだり実行したりしない。

## 呼び出しの契約

### 入力（`Skill` ツールの `args`）

`<操作> 名前=値 ...` の形で渡す。値に空白を含むときは引用符で囲む。省略できる項目は「任意」と示す。`category` は `specs`（既定）または `rules`。

| 操作             | 入力                                                                        | 用途                                               |
| ---------------- | --------------------------------------------------------------------------- | -------------------------------------------------- |
| `dir-of`         | `doc_type`、`feature`（任意）、`category`（任意）                           | 文書の出力先ディレクトリを求める                   |
| `decide-feature` | `doc_type`、`feature`（任意）、`source-path`（任意）、`category`（任意）    | 作る文書の feature と出力先を決める                |
| `find-in`        | `doc_type`、`name`、`category`（任意）                                      | パス・ファイル名・ID から文書の実体を探す          |
| `feature-of`     | `path`、`category`（任意）                                                  | 文書のパスから、その種別と feature を求める        |
| `match-path`     | `path`、`category`（任意）                                                  | パスが宣言のどの種別に当たるかを求める             |
| `files`          | `category`（`rules` / `specs` / `all`）、または `doc_type`（と `category`） | 文書（`.md`）の一覧を求める                        |
| `search-dirs`    | `category`                                                                  | 文書検索の対象ディレクトリを求める                 |
| `spec-root`      | `alias`（短縮名・相対パス・絶対パスのいずれか）                             | 短縮名などを、実在する spec ディレクトリへ解決する |

`doc_type` は抽象的な種別名（`requirement` / `design` / `plan` / `adr` / `glossary` / `rule` 等）である。どの種別を使うかは呼び出し側が決める。

### 出力

操作ごとの出力は、下記の各節に示す。いずれも、成功では `status` が `ok`、失敗では `error`（理由は `message`）である。失敗のうち、宣言が無い・種別のエントリが無い場合は、本スキルが次の共通ハンドオフを担う。

## 共通ハンドオフ

呼び出し側は、宣言の有無を確認しない。以下は本スキルが担う。

### `.doc_structure.yaml` が無い場合

1. AskUserQuestion で確認する:
   ```
   .doc_structure.yaml が見つかりません。
   /forge:setup-doc-structure を実行してプロジェクト構造を定義する必要があります。
   今すぐ /forge:setup-doc-structure を実行しますか？
   ```
2. **はい** → Skill ツールで `/forge:setup-doc-structure` を呼ぶ。完了後、要求された操作を最初からやり直す
3. **いいえ** → 呼び出し側へ「`.doc_structure.yaml` が無いため解決できません」と返して終える

### `doc_type` に対応するエントリが無い場合

配置はプロジェクトが宣言するものであり、forge が決めるものではない。宣言が無いときに既定値を当てはめることも、他の `doc_type` のキーから導出することも、**宣言されていない配置を forge が発明する行為**である。当たっている保証が無く、外れたときは文書が想定外の場所に作られ、後続の処理はそれを見つけられない。呼び出し側は、既定のパスを持たず、出力先を利用者に尋ねもしない。

1. AskUserQuestion で確認する:
   ```
   .doc_structure.yaml に doc_type `{doc_type}` に対応するエントリがありません。
   /forge:setup-doc-structure を実行して定義する必要があります。
   今すぐ /forge:setup-doc-structure を実行しますか？
   ```
2. **はい** → Skill ツールで `/forge:setup-doc-structure` を呼ぶ。完了後、要求された操作を最初からやり直す
3. **いいえ** → 呼び出し側へ「`{doc_type}` に対応するエントリが無いため解決できません」と返して終える

### それ以外のエラー

置き場を一意に決められない（キーの書き方が未対応、複数のエントリ 等）など、上の 2 つに当たらないエラーは、次に従う。

- `message` を、そのまま呼び出し側へ返す（読むだけで終わらせない。呼び出し側が利用者へ伝える）
- 原因がキーの書き方のとき、利用者に回答させても解決しない。キーの修正（プロジェクトの管理者が行う）か、置き場の直接指定を促す
- 推測で置き場・feature を決めない

## 実行

各操作は、次のスクリプトを呼ぶ。

```bash
SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/doc_structure/resolve_doc_structure.py"
```

実行の結果（stdout の JSON）が `status: error`（終了コード 1）のときは、上の共通ハンドオフとエラーの扱いに従う。

## 操作

### dir-of

文書の出力先ディレクトリを求める。

```bash
python3 "$SCRIPT" --dir-of {doc_type} [--feature {feature}] [--category {category}]
```

| 出力              | 内容                                                                                                      |
| ----------------- | --------------------------------------------------------------------------------------------------------- |
| `dir`             | 解決済みの置き場。`feature` を渡さなければ、feature なしの置き場                                          |
| `feature_applied` | `false` のときは、キーに feature を置く場所が無く、feature は使われていない。呼び出し側へそのことを伝える |
| `has_existing`    | `feature` を渡さなかったときだけ。既存ファイルが 1 件でもあれば `true`。`false` なら、その種別は完全新規  |

### decide-feature

作る文書の feature と出力先を決める。分岐とキーの解釈は script が行う。

```bash
python3 "$SCRIPT" --decide-feature-for {doc_type} [--feature {feature}] [--source-path {source-path}] [--category {category}]
```

`feature` は、引数で渡された feature 名で、**渡されたものを置き換えない**。`source-path` は、入力の文書のパス（設計書を作るときの要件定義書など）で、分かっていれば渡す。

| `decision`    | 意味                                                                                                                | 呼び出し側の動作                                                                                                                                             |
| ------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `argument`    | 引数の feature（`source-path` も渡されたときは、パスから求めた feature と食い違わない場合に限る。食い違えば `ask`） | `feature` と `dir`（出力先）を使う                                                                                                                           |
| `path`        | `source-path` から求めた（`feature` が `null` なら feature なし）                                                   | `feature` と `dir` を使う                                                                                                                                    |
| `no-existing` | その種別の既存ファイルが無い（完全新規）。feature なし                                                              | `dir` を使う                                                                                                                                                 |
| `ask`         | 決められない                                                                                                        | 呼び出し側が、`reason` を添えて利用者に feature を確認する。`features` に既知の feature、`existing_count` に既存の件数がある。件数が多いときは全件を並べない |

`feature_applied` の扱いは、`dir-of` と同じ。

### find-in

パス・ファイル名・ID（`REQ-032` など）で示された文書の実体を求める。文書を列挙して選ばせない（件数が多いと成り立たない）。

```bash
python3 "$SCRIPT" --find-in {doc_type} --name {name} [--category {category}]
```

| 出力      | 内容                                                                                                                                          |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `count`   | 見つかった件数。1 ならその文書、0 なら見つからない、2 以上なら、呼び出し側がどれかを利用者に尋ねる（同じ ID が複数の feature にある場合など） |
| `matches` | 見つかった文書のパス                                                                                                                          |

### feature-of

文書のパスから、その文書が属する feature を求める。

```bash
python3 "$SCRIPT" --feature-of {path} [--category {category}]
```

| 出力       | 内容                                                                                                                                                  |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `doc_type` | 文書の種別                                                                                                                                            |
| `feature`  | 属する feature。`null` のときは、feature なし（その種別のトップのディレクトリに置かれている）。feature の下にさらに階層があるときは、最上位の feature |

どの宣言にも一致しないパスは、`status: error` で返る。

### match-path

パスが、宣言のどの種別に当たるかを求める。

```bash
python3 "$SCRIPT" --match-path {path} [--category {category}]
```

| 出力       | 内容                                                                                                                              |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `doc_type` | 宣言の値（`design` / `plan` / `requirement` / `adr` 等）をそのまま返す。宣言に合わないパスと、プロジェクトルート外のパスは `null` |

ファイルシステムを見ず、宣言のパターンだけで照合する（ディスクに無いパスにも答える）。`feature-of` と違い、feature を求められないキーに当たったパスにも、種別だけは答える。

### files

文書（`.md`）の一覧を求める。

`category`（`rules` / `specs` / `all`）を渡したときは、カテゴリ全体の一覧を求める。`doc_type` を渡したときは、その種別の一覧を求める。

```bash
python3 "$SCRIPT" --type {rules|specs|all}
python3 "$SCRIPT" --doc-type {doc_type} [--category {category}]
```

| 入力       | 出力                                                                    |
| ---------- | ----------------------------------------------------------------------- |
| `category` | `rules` / `specs`（`all` を渡したときは両方）に、文書のパスの配列が入る |
| `doc_type` | `files`（その種別の文書のパス）                                         |

### search-dirs

文書検索（Grep 等）や外部インデックス転送のために、対象のディレクトリ一覧を求める。

```bash
python3 "$SCRIPT" --search-dirs --category {category}
```

| 出力            | 内容                                                                                                                                           |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `dirs`          | 宣言された検索対象のディレクトリ（展開しない。そのまま）                                                                                       |
| `exclude`       | 宣言された除外パターン                                                                                                                         |
| `filtered_dirs` | `dirs` のうち、末尾のディレクトリ名が `exclude` のいずれかに一致するエントリを除いたもの（参考値。ネストした除外ディレクトリの混入は許容する） |

`dirs` と `exclude` をそのまま下流のツール（doc-advisor の `--dirs-json` / `--exclude-json` 等）へ転送する呼び出し側は、`filtered_dirs` を使わず `dirs` / `exclude` を使う。自前で Grep 等に渡す呼び出し側は、`filtered_dirs` を使う。

### spec-root

短縮名（例: `main`）・相対パス・絶対パスのいずれかを、実在する spec ディレクトリへ解決する。

```bash
python3 "$SCRIPT" --spec-root {alias}
```

| 出力       | 内容                                                                                                                             |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `resolved` | 解決済みのディレクトリ。解決できないときは `null`（エラーではない。呼び出し側が利用者に尋ねる等で対応する）                      |
| `source`   | `as-is`（`alias` がそのまま実在するディレクトリだった）、`spec-root`（spec ルートの下の短縮名だった）、解決できないときは `null` |

## 宣言の解釈（本スキルの内部）

呼び出し側は、この節を読まない。`.doc_structure.yaml` は、`root_dirs`（文書ディレクトリ）・`doc_types_map`（パスから種別への対応）・`patterns.exclude`（除外）だけを使う。他のフィールドは無視する。

```yaml
# doc_structure_version: 3.0

specs:
  root_dirs:
    - "docs/specs/**/design/"
    - "docs/specs/**/plan/"
  doc_types_map:
    "docs/specs/**/design/": design
    "docs/specs/**/plan/": plan
  patterns:
    exclude: []
```

`*` は 1 階層、`**` は任意の深さにマッチする。サブ feature（`forge/review-PR/design/` 等）があるときは `**` を使う。`# doc_structure_version: X.Y` でバージョンを管理し、メジャーバージョンの変更はフォーマットの破壊的変更を意味する。
