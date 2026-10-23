# Changelog

All notable changes to this project will be documented in this file.

## [marketplace 0.1.0] - 2026-10-23

### marketplace

- **chore**: マーケットプレイス名を `sdd-forge` に改め、版を 0.1.0 から数え直す（旧 `bw-cc-plugins` からの移管）。作者表記を `k2moons` に統一した
- **chore**: 全スキルの冒頭に責務宣言をそろえ、ADR-089 に決定を記録した
- **fix**: `update-version` を利用者の明示的な起動に限り、`help` はコマンドの表示にした
- **fix**: CI を `unittest` と `dprint check` の実体に直し、dprint に TOML プラグインを追加した
- **chore**: 一時ファイルの置き場を `.temp/<plugin>/<skill>/` に統一し、`mktemp` を廃止した
- **chore**: 文書の履歴記述と、旧物の不在を検査するだけのテストを整理し、変更行 gate 一式を削除した。実装ガイドラインと script のエラー出力の規範を新版にした
