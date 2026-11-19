---
doc_link_id: DLID-1t0vpykg6nq6
---

# forge ドキュメントアクセス原則 DLID-8he86zf07kes

forge プラグインの**開発ルール**。forge 内部 (SKILL / agent / scripts) からドキュメントに**どう到達するか**を定める。配布物ではなく、この repo の開発者が遵守する設計原則。

## 2 つの経路のみ DLID-929mb459h5rq

| 経路            | 対象                                                                                                         | 方式                                                        |
| --------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| **A. 直接参照** | forge 内蔵 docs (`plugins/forge/docs/*`、または参照元スキル自身の `plugins/forge/skills/{同一skill}/docs/*`) | パスを直接書く: `${CLAUDE_PLUGIN_ROOT}/docs/xxx.md` を Read |
| **B. クエリ**   | プロジェクト固有 spec / rules (`docs/specs/`, `docs/rules/`)                                                 | `/forge:query-db-specs` / `/forge:query-db-rules` を呼ぶ    |

**Route A の範囲に注意**: `plugins/forge/skills/{skill}/docs/*` を直接参照してよいのは、**その skill 自身** から `${CLAUDE_SKILL_DIR}/docs/xxx.md` で参照する場合のみ。**別の skill から他 skill の `docs/*` を直接参照してはならない**（`docs/rules/plugin_implementation_guidelines.md`「スクリプトと文書の配置」参照）。複数 skill が必要とする文書は `plugins/forge/docs/*`（プラグイン共有）へ昇格する。

それ以外の経路 (例: session_dir / refs/*.yaml を介したファイル受け渡し) は採用しない。

## なぜこの 2 経路だけか DLID-pr0xgvwqs1d2

- **forge 内蔵 docs**: forge プラグイン自身のリリースで参照箇所と一緒に更新できる → 固定パスが腐らない → 直接参照が最短
- **プロジェクト spec/rules**: プロジェクト側で増減・改廃が頻繁 → 固定パスは腐る → クエリ動的発見が必要

## やってはいけない (アンチパターン) DLID-g38qcpvqmjmx

- **forge 内蔵 docs をクエリで探す**: 固定パスで済むのに動的解決を挟む冗長
- **プロジェクト spec/rules を配布物から参照する**: 禁止の範囲と例外は [plugin_implementation_guidelines.md](plugin_implementation_guidelines.md)「配布物は開発用の文書を参照しない」を参照
- **forge 内部ロジックを「内蔵 doc」として書く**: doc は宣言的に読み取るもの。手続きは SKILL.md / scripts に閉じる
- **agent への引数として `session_dir` を渡し、ファイル経由で結果を受ける**: Agent return value で代替可能で、第三の経路を作るだけ
- **他 skill の `docs/*` を直接参照する**: 参照元 skill の視点では無断参照であり、参照先 skill のディレクトリ構成が変わると静かに壊れる。詳細は [plugin_implementation_guidelines.md](plugin_implementation_guidelines.md)「スクリプトと文書の配置」を参照。複数 skill が必要とする文書はプラグイン共有 `plugins/forge/docs/*` へ昇格する

## 文書検索 backend を参照してよいのは wrapper だけ [MANDATORY] DLID-mxfwahv3vq7d

経路 B の wrapper は、`query-db-rules`・`query-db-specs`・`update-db-rules`・`update-db-specs` の 4 スキルと、それらが使う `plugins/forge/scripts/doc_backend/` である。backend は、wrapper が呼び出す外部の文書検索の実装を指す。

**backend を参照してよいのは wrapper だけである。** backend の名前が AI の文脈に入ると、AI は wrapper を通らずに backend を直接呼ぶ。

- wrapper 以外の SKILL.md・agent・SKILL が読む手順文書・`CLAUDE.md` へ転記するブロックに、backend の名前・SKILL 名・引数名・保存先のパスを書かない。説明や例としても書かない
- 文書が backend を説明する場所は、層ごとに次の 1 箇所とする。他の文書は backend の名前を書かず、必要ならその 1 箇所を指す

| 層               | backend を説明する場所                                      |
| ---------------- | ----------------------------------------------------------- |
| 配布物           | wrapper の SKILL.md                                         |
| 利用者向けの文書 | [backend の切り替えの案内][switch-backend]（と、その翻訳）  |
| 仕様             | wrapper の要件定義書と設計書（REQ-014 / DES-057 / DES-001） |
| `CLAUDE.md`      | Project Overview の説明                                     |

## 外部利用 (参考) DLID-e7nh82xy2fe0

プロジェクト側ユーザーが forge 内蔵 docs を読みたい場合は `/forge:query-forge-rules` を使う。これは forge 内部の使い方ではなく、forge を外から利用するための入口で本原則の対象外。

[switch-backend]: ../readme/switch-forge-backend.md
