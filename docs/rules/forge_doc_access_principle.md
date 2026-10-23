# forge ドキュメントアクセス原則

forge プラグインの**開発ルール**。forge 内部 (SKILL / agent / scripts) からドキュメントに**どう到達するか**を定める。配布物ではなく、この repo の開発者が遵守する設計原則。

## 2 つの経路のみ

| 経路            | 対象                                                                                                         | 方式                                                        |
| --------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| **A. 直接参照** | forge 内蔵 docs (`plugins/forge/docs/*`、または参照元スキル自身の `plugins/forge/skills/{同一skill}/docs/*`) | パスを直接書く: `${CLAUDE_PLUGIN_ROOT}/docs/xxx.md` を Read |
| **B. クエリ**   | プロジェクト固有 spec / rules (`docs/specs/`, `docs/rules/`)                                                 | `/forge:query-db-specs` / `/forge:query-db-rules` を呼ぶ    |

**Route A の範囲に注意**: `plugins/forge/skills/{skill}/docs/*` を直接参照してよいのは、**その skill 自身** から `${CLAUDE_SKILL_DIR}/docs/xxx.md` で参照する場合のみ。**別の skill から他 skill の `docs/*` を直接参照してはならない**（`docs/rules/implementation_guidelines.md`「スクリプトと文書の配置」参照）。複数 skill が必要とする文書は `plugins/forge/docs/*`（プラグイン共有）へ昇格する。

それ以外の経路 (例: session_dir / refs/*.yaml を介したファイル受け渡し) は採用しない。

## なぜこの 2 経路だけか

- **forge 内蔵 docs**: forge プラグイン自身のリリースで参照箇所と一緒に更新できる → 固定パスが腐らない → 直接参照が最短
- **プロジェクト spec/rules**: プロジェクト側で増減・改廃が頻繁 → 固定パスは腐る → クエリ動的発見が必要

## やってはいけない (アンチパターン)

- **forge 内蔵 docs をクエリで探す**: 固定パスで済むのに動的解決を挟む冗長
- **プロジェクト spec/rules を配布物から参照する**: パス直書きも spec ID 参照（`DES-028 §3.4.1 に従う` 等）も禁止（`docs/rules/implementation_guidelines.md`「配布物は開発用の文書を参照しない」）
- **forge 内部ロジックを「内蔵 doc」として書く**: doc は宣言的に読み取るもの。手続きは SKILL.md / scripts に閉じる
- **agent への引数として `session_dir` を渡し、ファイル経由で結果を受ける**: Agent return value で代替可能で、第三の経路を作るだけ
- **他 skill の `docs/*` を直接参照する**: 参照元 skill の視点では無断参照であり、参照先 skill のディレクトリ構成が変わると静かに壊れる。詳細は [implementation_guidelines.md](implementation_guidelines.md)「スクリプトと文書の配置」を参照。複数 skill が必要とする文書はプラグイン共有 `plugins/forge/docs/*` へ昇格する

## 外部利用 (参考)

プロジェクト側ユーザーが forge 内蔵 docs を読みたい場合は `/forge:query-forge-rules` を使う。これは forge 内部の使い方ではなく、forge を外から利用するための入口で本原則の対象外。
