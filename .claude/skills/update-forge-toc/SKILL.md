---
name: update-forge-toc
description: |
  forge 内蔵ドキュメントの検索インデックスを更新する。
  /forge:query-forge-rules の検索結果を最新化したいときに使う。
  トリガー: "forge ToC 更新", "update forge toc", "forge インデックス更新", "forge 内蔵ドキュメントの ToC を再生成"
user-invocable: true
allowed-tools: Bash, Skill
argument-hint: ""
---

# update-forge-toc

forge 内蔵ドキュメント（`plugins/forge/docs/`, `plugins/forge/skills/*/docs/`）の索引を doc-link で構築し、
その内容から forge 同梱の検索インデックス `plugins/forge/toc/rules/rules_toc.yaml` を生成する。

同梱ファイルの形式は forge のものである。配布物（`/forge:query-forge-rules` とその worker）は
同梱ファイルだけを読み、doc-link を知らない。

## 前提条件

- `doc-link` プラグインがインストールされ、`doc-link:index-docs` が available-skills に存在すること
- 未インストールの場合はその旨を報告して終了する

## 実行フロー

### Step 1: 索引を構築する

`Skill` ツールで `doc-link:index-docs` を呼ぶ。キーは `forge-rules`、対象指定は次のとおりで、変えない。

```
/doc-link:index-docs --key forge-rules --dirs-json '["plugins/forge/docs/", "plugins/forge/skills/*/docs/"]' --exclude-json '[]'
```

構築が失敗した場合、または索引に入らなかった文書が残る場合は、Step 2 へ進まず、返された内容を報告して終了する。

### Step 2: 同梱ファイルを生成する

```bash
python3 .claude/skills/update-forge-toc/scripts/build_forge_toc.py
```

- 終了コード 0: 標準出力の JSON の `output` と `file_count` を控えて Step 3 へ進む
- それ以外: 標準出力の JSON の `errors` を報告して終了する。索引の文書の集合が内蔵文書と一致しないときは、ここでエラーになる

### Step 3: 完了報告

```
forge 内蔵 docs の検索インデックスを更新しました

- 生成元: plugins/forge/docs/, plugins/forge/skills/*/docs/
- key: forge-rules
- 出力: plugins/forge/toc/rules/rules_toc.yaml（<file_count> 件）
```

## Notes

- 同梱ファイル、`.doc-link/` の変更、DLID の入った内蔵文書は、同じコミットに入れる。
  `lint/lint_forge_toc_freshness.py`（lint）が、索引と内蔵文書の集合の一致と、同梱ファイルと生成結果の一致を検査する。
  索引の内容が現物の文書より古いかは、doc-link の検査（`doc-link:check-toc`。`doc-link:index-docs` も構築の前に確かめる）が担う。内蔵文書を変えたら、本 skill を実行する。
- ランタイムの `/forge:query-forge-rules` は同梱ファイルを直接 Read するため、利用者の環境に doc-link は要らない。
- `.bak` ファイル（`rules_toc.yaml.bak` 等）はコミットしない。同じテストが残存を検出する。
