---
doc_link_id: DLID-wm7t1emetwbx
---

# generic レビュー基準 DLID-1d22mabn3k7z

> SoT: [review_priorities_spec.md][review-priorities-spec]
> 重大度判定 / グレーゾーン許容範囲は委譲先 principles 側を参照すること。本ファイルは判断を持たない。
> severity は委譲先 principles の重大度カタログから取得する ([review_priorities_spec.md][review-priorities-spec] §2.2)。

## 1. SSOT参照 DLID-63wpw8s262ay

P1 で照合すべき委譲先文書一覧。各文書は「規範本体 + 重大度カタログ (拡充済み)」を保持する SoT である。複数文書間の優先順位は「プロジェクト固有 > 内蔵」とする (review_priorities_spec.md)。

| priority | path                                                                         | doc_type   | 役割                                                                                                                                                                                                             |
| -------- | ---------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1       | [document_style_guide.md][document-style-guide]                              | format     | 文書スタイル規約 (タグ用法 / 見出し / 表記揺れ / §5 文書参照記法 / §9 用語等の内蔵 format。規範本体。文書参照の severity は [review_priorities_spec.md][review-priorities-spec] §2.3、用語の severity は同 §2.4) |
| P1       | `(query-db-rules: "文書レビュー全般に関するプロジェクト固有の文書記述規約")` | rules      | プロジェクト固有 文書記述ルール (規範本体 + 重大度カタログ)                                                                                                                                                      |
| P1       | [error_classification_spec.md][error-classification-spec]                    | principles | エラーの定義・分類（回復可能・回復不能）・原因の扱い (規範本体 + 重大度カタログ)                                                                                                                                 |
| P2       | target ファイル内部 + 関連文書間の整合性チェック対象                         | specs      | 矛盾検出 (用語不一致 / 重複記述等の相反のみ。漏れ・欠落は P2 対象外)                                                                                                                                             |
| P3       | [spec_priorities_spec.md][spec-priorities-spec]                              | principles | 不要な複雑化判定 (§3.4 / §4 倒錯パターン、Yes/No 判定原則)                                                                                                                                                       |

委譲先ルールが未整備の場合は forge 内蔵ルールへフォールバックする。`(query-db-rules: "文書レビュー全般に関するプロジェクト固有の文書記述規約")` の解決結果が 0 件の場合も、内蔵 `document_style_guide.md` のみで review_packet が構築できる。

## 2. チェック順 DLID-wn2atcngzmcv

種別ごとに「どの委譲先文書から先に読むか」の順序。規範本体は再掲しない:

1. **P1 文書スタイル合致**: [document_style_guide.md][document-style-guide] を Read し、対象文書のタグ用法 / 見出し階層 / 表記揺れ等を照合する
2. **P1 プロジェクト固有 rules 合致**: `(query-db-rules: "文書レビュー全般に関するプロジェクト固有の文書記述規約")` の解決結果 (存在する場合) を Read し、プロジェクト固有の文書記述ルールと対象を照合する
3. **P1 エラーの扱い**: 対象がエラーの扱いを定めている場合、[error_classification_spec.md][error-classification-spec] を Read し、規範と照合する (握りつぶし / 判定できる事象のエラー化 / 原因ごとの値)
4. **P2 矛盾・齟齬**: target ファイル内部、および P1 で参照した関連文書間で、同一概念への相反記述 (用語不一致 / 重複記述等) を突き合わせる (不足・欠落は P2 対象外)
5. **P3 不要な複雑化**: [spec_priorities_spec.md][spec-priorities-spec] §3.4 / §4 (倒錯パターン) を参照し、より少ない要素で同じ目的を達成できる代替案の有無を Yes/No で判定する

## 3. 判定ルール DLID-ygkp2zrfehc0

| recommendation | 採用条件                                                                                                    |
| -------------- | ----------------------------------------------------------------------------------------------------------- |
| `fix`          | 規範違反であり、修正による副作用が限定的な場合                                                              |
| `create_issue` | ルール未整備で発見した場合 ([review_priorities_spec.md][review-priorities-spec] §4 の 3 条件をすべて満たす) |
| `skip`         | false positive / グレーゾーン許容範囲内 (principles の許容範囲に該当)                                       |

### `recommendation: create_issue` の 3 条件 DLID-f92ap1mvdegp

| # | 条件               | 内容                                                                                                                    |
| - | ------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| 1 | 該当規定なし       | P1 で参照する SSOT (プロジェクト固有 rules / forge 内蔵 principles / format) のいずれにも該当規定が存在しない           |
| 2 | 再発性または客観性 | 同種の指摘が今回・過去のレビューで複数箇所に観察される (再発性)、または客観的事実で説明可能 (AI 主観の単発判断ではない) |
| 3 | 明文化可能粒度     | ルールとして明文化可能な具体粒度を持ち、Issue として書き起こせる (「主観的にシンプルでない」等の評価語のみは不可)       |

3 条件のいずれかが不成立の場合は `recommendation: skip` (skip_reason に該当条件不成立の理由を記載) とする。

[review-priorities-spec]: ../review_priorities_spec.md "458b42b8deb4 DLID-dcec6pr177c9"
[document-style-guide]: ../document_style_guide.md "335c3c0eb320 DLID-c59znr7b8f56"
[error-classification-spec]: ../error_classification_spec.md "94496cc6d044 DLID-5ykqs19cdbks"
[spec-priorities-spec]: ../spec_priorities_spec.md "b68b930cec1d DLID-f9ny9e932trv"
