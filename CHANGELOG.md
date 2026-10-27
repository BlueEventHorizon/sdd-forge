# Changelog

All notable changes to this project will be documented in this file.

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
