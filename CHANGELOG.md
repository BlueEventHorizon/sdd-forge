# Changelog

All notable changes to this project will be documented in this file.

## [forge 0.1.3] - 2026-11-20

### forge

- **feat**: エラー分類の規範を、文書を作る工程・レビュー観点・CLAUDE.md へ行き渡らせた
- **fix**: 文書検索 backend を doc-link へ差し替え、backend の参照を wrapper に集約した。forge 内蔵文書の検索索引も doc-link へ移した
- **fix**: 文書検索 wrapper の仕様をレビューし、要件・設計・SKILL の食い違いを直した
- **fix**: コンテキスト収集の文書検索を Agent に委ねず直接実行し、失敗したら後続へ進まないようにした (#11)
- **fix**: 見出しの行末の DLID で壊れた ADR の構成検査と DES-085 のアンカーを直した
- **fix**: 文書への参照をリファレンスリンクで書く規範に改め、既存のリンクを書き換えた

## [marketplace 0.1.3] - 2026-11-20

### marketplace

- **chore**: forge 0.1.3 のリリースに伴い marketplace バージョンをバンプ

## [forge 0.1.2] - 2026-11-17

### forge

- **feat**: 用語の命名原則・`[用語]` 表記・用語集（glossary）を加えた
- **fix**: `find_doc` が空の名前で全件に当たる退行を直し、ID の後ろの区切りに依存せず、番号の終端まで照合して文書を探すようにした
- **fix**: `next-spec-id` が specs の置き場を `doc-structure` スキルで求めるようにした。置き場の宣言が無い・不正なときは、`specs/` を推測せずエラーで報告する
- **fix**: forge 同梱 ToC の checksums を、doc-advisor の出力のコピーにした
- **refactor**: 他のスキルへの窓口を SKILL だけにした（`doc-structure`・`next-spec-id`・`uxui_analysis_workflow` の置き場の解決）。テストがリポジトリのルートを `tests` の `REPO_ROOT` から得るようにし、文言を固定するテストを削除した
- **docs**: 共通 script は直接使ってよく、禁止されるのは他のスキルの script の直接呼び出しだけであると規約に明記した。agent は自分を起動したスキルの script を直接呼んでよい旨も加えた
- **docs**: 設計文書の置き場の解決手段を `/forge:doc-structure` とし、`doc_structure` の宣言を必須とする記述を取り除いた。glossary を `setup-doc-structure` の既定に含め、`doc_structure_format` の引数の記述を実装に合わせた
- **docs**: dprint 設定ファイル名の記述を `dprint.jsonc` に揃え、CI の dprint を 0.64.3 へ上げた。文書スタイル指針や実装ガイドラインの語・タグを整えた
- **chore**: dprint 設定を `dprint.jsonc` へ移行し、CLAUDE.md を更新し、検索インデックスを再生成した

## [marketplace 0.1.2] - 2026-11-17

### marketplace

- **chore**: forge 0.1.2 のリリースに伴い marketplace バージョンをバンプ

## [forge 0.1.1] - 2026-10-27

### forge

- **feat**: `create-requirements-from-plan-mode` が `plansDirectory` 設定を読むようにした
- **fix**: SKILL と agent の記述の誤りを直し、`.env` を `.gitignore` に加えた
- **docs**: ルール文書を、配布先へ写す汎用のもの（`plugin_`）と forge 固有のもの（`forge_`）に分け、参照を更新した。uv 利用ルールを加え、公開直後の版を取り込まない設定の宣言先を ADR-089 に記録した
- **docs**: 比例性の原則に、極めてまれで起きても収まる障害への対策は害になる旨を加え、reviewer / evaluator の判定にも反映した。外部依存と公式仕様の確かめ方の記述を、規範の正本どおりに直した
- **chore**: CLAUDE.md と DEVELOPMENT.md を整理し、検索インデックスを再生成した

## [marketplace 0.1.1] - 2026-10-27

### marketplace

- **chore**: forge 0.1.1 のリリースに伴い marketplace バージョンをバンプ

## [marketplace 0.1.0] - 2026-10-23

### marketplace

- **chore**: マーケットプレイス名を `sdd-forge` に改め、版を 0.1.0 から数え直す（旧 `bw-cc-plugins` からの移管）。作者表記を `k2moons` に統一した
- **chore**: 全スキルの冒頭に責務宣言をそろえ、ADR-089 に決定を記録した
- **fix**: `update-version` を利用者の明示的な起動に限り、`help` はコマンドの表示にした
- **fix**: CI を `unittest` と `dprint check` の実体に直し、dprint に TOML プラグインを追加した
- **chore**: 一時ファイルの置き場を `.temp/<plugin>/<skill>/` に統一し、`mktemp` を廃止した
- **chore**: 文書の履歴記述と、旧物の不在を検査するだけのテストを整理し、変更行 gate 一式を削除した。実装ガイドラインと script のエラー出力の規範を新版にした
