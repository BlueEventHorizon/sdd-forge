# forge backend の導入と切り替え

forge には差し替え可能な backend が 2 軸ある。

| 軸               | 候補                           | 使うスキル                                                                         |
| ---------------- | ------------------------------ | ---------------------------------------------------------------------------------- |
| 文書検索 backend | doc-link（既定先位）/ doc-db   | `/forge:query-db-rules` / `query-db-specs` / `update-db-rules` / `update-db-specs` |
| レビュー実行主体 | agent-review（現状唯一の候補） | `/forge:review`                                                                    |

どちらもプロジェクト設定ファイル `.claude/.forge.yaml`（プロジェクトルート相対）で切り替える。ファイルは任意であり、無ければ既定動作になる。

## 文書検索 backend の導入

文書検索 backend は forge に含まれない。使うものを別に導入する。どちらもバージョンを条件にせず、必要な機能が利用できるかで判定される。

| backend  | 何か                                                                                                                                                                                                                                 | 導入                                                                                     |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| doc-link | 外部プラグイン（[BlueEventHorizon/doc-link](https://github.com/BlueEventHorizon/doc-link)）。文書に変わらない ID（DLID）を付けて索引を作り、意味で検索する。[uv](https://docs.astral.sh/uv/) が要る（Python と依存は uv が用意する） | 下記のコマンド                                                                           |
| doc-db   | ローカルで稼働する文書検索サーバ                                                                                                                                                                                                     | `doc-db` コマンドを PATH に導入する。順序リストで選択されたときに forge が自動で起動する |

```
/plugin marketplace add BlueEventHorizon/doc-link
/plugin install doc-link@doc-link
```

### doc-link を使うときに文書へ起きること

- **索引の更新（`/forge:update-db-rules` / `update-db-specs`）は、対象の文書に DLID を書き込む。** 書き込む場所は、frontmatter の `doc_link_id` と、すべての見出しの行末である。DLID の無い文書は索引に入らないためである。書き込みの前に確認は出ない。最初の更新では、対象の全文書に書き込まれる
- 索引と管理状態は、プロジェクトルートの `.doc-link/` に置かれる。**`.doc-link/` と DLID の入った文書は git で追跡し、文書の変更と同じコミットに入れる**
- 検索（`/forge:query-db-rules` / `query-db-specs`）は、索引が現物の文書と合っているかを検索の前に検査する。古いときは、再構築してから検索するか、既存の索引のまま検索するかを尋ねる

## 設定ファイルの書き方

```yaml
# .claude/.forge.yaml
doc_backend:
  prefer: doc-db # doc-db | doc-link

review:
  backend: agent-review # 現状の候補は agent-review のみ
```

### `doc_backend.prefer`（文書検索 backend）

- 指定した backend が順序リストの先位になる（例: `doc-db` を指定すると `["doc-db", "doc-link"]`）。未指定の既定は doc-link 先位
- 先位の backend が利用不能な場合は、理由を通知して後位の backend を利用する
- 索引に入る文書を決める規則は backend ごとに異なる。同じ検索でも、backend が変わると結果が変わることがある
- 許容キーは `prefer` のみ。未知のキー・2 値以外の値は明示エラーになる（黙って既定動作へ落ちない — 設定したつもりで効いていない状態を防ぐため）

### `review.backend`（レビュー実行主体）

- 指定した backend **だけ**で実行する（明示指定扱い）。利用不能でも代替を選ばず、依頼を送らずにエラー終了する（fail closed）
- 未指定なら候補順で可用性を検査して採用する（**現状の候補は agent-review のみ**。候補が 1 つでも解決の機構は変わらない）
- 許容キーは `backend` のみ

## 引数による強制指定（設定より優先）

| スキル                                                                             | 引数                           | 挙動                                              |
| ---------------------------------------------------------------------------------- | ------------------------------ | ------------------------------------------------- |
| `/forge:review`                                                                    | `--backend <name>`             | 指定 backend のみを使う。利用不能なら fail closed |
| `/forge:query-db-rules` / `query-db-specs` / `update-db-rules` / `update-db-specs` | （利用者向けの引数を持たない） | 常に順序リストで決まる                            |

優先順位は **引数 > `.claude/.forge.yaml` > 既定の候補順**。

## 注意

- `.claude/.forge.yaml` は制約付き YAML サブセットとして読まれる。アンカー・エイリアス（`&` / `*`）、複数行文字列（`|` / `>`）、flow style（`[...]` / `{...}`）は使えず、含まれるとファイル全体が解析不能として明示エラーになる
- レビュー実行主体の候補順の設計根拠・各バックエンドの前提条件は [guide_review_ja.md](forge/guide_review_ja.md) を参照
