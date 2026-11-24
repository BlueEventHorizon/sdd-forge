---
doc_link_id: DLID-e9tn4760zpw5
---

# uxui レビュー基準 DLID-j336y8qdsy3k

> SoT: [review_priorities_spec.md][review-priorities-spec]
> 重大度判定 / グレーゾーン許容範囲は委譲先 principles 側を参照すること。本ファイルは判断を持たない。
> severity は委譲先 principles の重大度カタログから取得する ([review_priorities_spec.md][review-priorities-spec] §2.2)。
> uxui 種別の主要 SoT (HIG / プロジェクト固有デザインシステム規約) は当面未整備のため、暫定的に [document_style_guide.md][document-style-guide] + プロジェクト固有 rules で代替する（内蔵ルールへのフォールバック）。

## 1. SSOT参照 DLID-h91yy7cte039

P1 で照合すべき委譲先文書一覧。各文書は「規範本体 + 重大度カタログ (拡充済み or 拡充予定)」を保持する SoT である。複数文書間の優先順位は「プロジェクト固有 > 内蔵」とする (review_priorities_spec.md)。

| priority | path                                                                                       | doc_type   | 役割                                                                                                                |
| -------- | ------------------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------- |
| P1       | Apple HIG (`https://developer.apple.com/design/human-interface-guidelines/`)               | rules      | プラットフォーム必須要件の規範本体 (URL 参照。uxui 専用 principles 整備までの暫定。重大度カタログは未整備)          |
| P1       | `(query-db-rules: "UI/UXレビューに関するプロジェクト固有のデザインシステム・HIG準拠規約")` | rules      | プロジェクト固有デザインシステム・HIG 準拠規約 (整備状況はプロジェクトごとに異なる。未整備時は内蔵フォールバックへ) |
| P1       | [document_style_guide.md][document-style-guide]                                            | format     | フォールバック先。uxui 専用 principles が整備されるまでの暫定的な文書スタイル規範                                   |
| P2       | target ファイル内部 + 関連要件・設計書                                                     | specs      | 矛盾検出 (target ファイル内および関連要件・設計書との相反記述を突合)                                                |
| P3       | [spec_priorities_spec.md][spec-priorities-spec]                                            | principles | 不要な複雑化判定 (§3.4 / §4 倒錯パターン参照。Yes/No 判定原則、拡充後はアンチパターン重大度カタログ)                |

委譲先ルールが未整備の場合は forge 内蔵ルールへフォールバックする。

## 2. チェック順 DLID-vymdmf5grfz6

種別ごとに「どの委譲先文書から先に読むか」の順序。規範本体は再掲しない:

1. **P1 ルール合致**: Apple HIG (URL) → `(query-db-rules: "UI/UXレビューに関するプロジェクト固有のデザインシステム・HIG準拠規約")` (未整備時はスキップ) → [document_style_guide.md][document-style-guide] (フォールバック) の順で対象 uxui 文書 (THEME / CMP / SCR / UXEVAL / 設計書内 UI 設計) と照合する
2. **P2 矛盾・齟齬**: target ファイル内部および関連要件・設計書との間で、同一対象への相反記述 (デザイントークン定義 / コンポーネント仕様 / 画面要件 / インタラクション規定等) を突き合わせる (不足・欠落は P2 対象外)
3. **P3 不要な複雑化**: [spec_priorities_spec.md][spec-priorities-spec] を参照し、より少ない要素 (トークン / コンポーネント / 階層 / バリエーション) で同じ目的を達成できる代替案の有無を Yes/No で判定する

## 3. 判定ルール DLID-9vhfq2kspkkw

| recommendation | 採用条件                                                                                                    |
| -------------- | ----------------------------------------------------------------------------------------------------------- |
| `fix`          | 規範違反であり、修正による副作用が限定的な場合                                                              |
| `create_issue` | ルール未整備で発見した場合 ([review_priorities_spec.md][review-priorities-spec] §4 の 3 条件をすべて満たす) |
| `skip`         | false positive / グレーゾーン許容範囲内 (principles の許容範囲に該当)                                       |

### `recommendation: create_issue` の 3 条件 DLID-g55zarnetzfj

| # | 条件               | 内容                                                                                                                    |
| - | ------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| 1 | 該当規定なし       | P1 で参照する SSOT (プロジェクト固有 rules / forge 内蔵 principles / format) のいずれにも該当規定が存在しない           |
| 2 | 再発性または客観性 | 同種の指摘が今回・過去のレビューで複数箇所に観察される (再発性)、または客観的事実で説明可能 (AI 主観の単発判断ではない) |
| 3 | 明文化可能粒度     | ルールとして明文化可能な具体粒度を持ち、Issue として書き起こせる (「主観的にシンプルでない」等の評価語のみは不可)       |

3 条件のいずれかが不成立の場合は `recommendation: skip` (skip_reason に該当条件不成立の理由を記載) とする。

[review-priorities-spec]: ../review_priorities_spec.md "458b42b8deb4 DLID-dcec6pr177c9"
[document-style-guide]: ../document_style_guide.md "335c3c0eb320 DLID-c59znr7b8f56"
[spec-priorities-spec]: ../spec_priorities_spec.md "b68b930cec1d DLID-f9ny9e932trv"
