---
doc_link_id: DLID-4wshmhbcgynm
---

# レビュー対象の種別と読む文書 DLID-a3nc5ac2jq91

reviewer が、レビュー対象 1 件ごとに target 種別を判定し、種別に応じて読む文書を選ぶための文書である。持つのは判定の手順と、種別ごとの文書の対応だけである。規範の本文・レビュー観点の中身は各文書が持つので、ここへ写さない。観点文書から規範への委譲は観点文書の側が持つ。

target 種別は **code / requirement / design / plan / uxui** の 5 つである。ADR は design として扱う。

## 1. 種別の判定 DLID-btd757hrjq12

先に設定を引いて種別を決め、決まらないものと細分が要るものだけファイルを読む。設定ファイル `.doc_structure.yaml` を自分で読まない。設定の解釈は script が行う。

### 1.1 設定を引く DLID-fd8jqdv4tr8y

対象 1 件につき、`resolve_doc_structure.py` にパスを 1 つ渡す（絶対パス、またはプロジェクトルートからの相対パス。呼び方は reviewer の定義が持つ）。

標準出力は JSON であり、`doc_type` に、宣言された doc_type（`plan` / `requirement` / `design` / `adr` のほか、`glossary` / `reference` / `api` 等）、または `null`（宣言に合わないパス）が入る。`status` が `ok` でないときは設定を引けていないので、種別を決めずに、レビューを続けず止まる（値で区別しないエラーとして終える）。

### 1.2 返った値から種別を決める DLID-ntdb48nbbkf3

| `doc_type`                       | 次の動作                                          | 種別                                                   |
| -------------------------------- | ------------------------------------------------- | ------------------------------------------------------ |
| `plan`                           | 細分は無い                                        | plan                                                   |
| 上記以外の doc_type              | 細分は無い                                        | 種別なし（1.3 のとおり、共通の文書だけで見る）         |
| `requirement` / `design` / `adr` | ファイルを読み、UI を扱う文書か（下記）を見分ける | UI を扱う文書なら uxui。そうでなければ返った種別       |
| `null`                           | ファイルを読み、ソースコードか否かを見分ける      | ソースコードなら code。そうでなければ決まらない（1.3） |

- `adr` は design として扱う。この読み替えは reviewer が行う。script は返さない
- UI を扱う文書とは、デザイントークン・UI コンポーネント・画面・UX 評価を扱う文書、および設計書の UI 設計である。UI を扱う requirement / design も、設定の上では requirement / design の置き場にある
- 名前（ファイル名・ディレクトリ名）だけで種別を当てない。設定が宣言している対応を使うことは、これに当たらない

### 1.3 決まらない対象 DLID-633angt31hds

設定にもファイルの実体にも当たらず、種別が決まらない対象は、次節の「全 target 種別に共通」の文書だけで見る。推測で 1 つに寄せない。種別が決まらないことは、所見にもエラーにもしない。

## 2. 全 target 種別に共通の文書 DLID-66jzrce09d5t

すべての対象に適用する。種別が決まった対象には、次節の文書を上乗せする。

| 文書                                                        | 役割                                         |
| ----------------------------------------------------------- | -------------------------------------------- |
| [review_criteria_generic.md][review-criteria-generic]       | すべての対象に適用するレビュー観点           |
| [review_priorities_spec.md][review-priorities-spec]         | 重大度の判断基準                             |
| [scope_proportionality_spec.md][scope-proportionality-spec] | 比例性の原則（過剰設計の抑止）               |
| [error_classification_spec.md][error-classification-spec]   | エラーの定義・分類（回復可能性）・原因の扱い |

## 3. 種別ごとに上乗せする文書 DLID-y7ny461sst3j

「プロジェクト固有」の欄は、依頼の `references` が運ぶ文書のうち、その種別で用いるものを示す。内蔵の文書はここに挙げたものを直接読む。

### 3.1 code（ソースコード） DLID-8vpdyxy3p22b

| 区分             | 内容                                                                                                              |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| レビュー観点     | [review_criteria_code.md][review-criteria-code]                                                                   |
| 内蔵規範         | [deterministic_generation_spec.md][deterministic-generation-spec] / [forge_anti_patterns.md][forge-anti-patterns] |
| プロジェクト固有 | 実装・コーディング・出力フォーマット規約                                                                          |
| 突き合わせ対象   | 対象に対応する関連設計書                                                                                          |

### 3.2 requirement（要件定義書） DLID-j1pxx7pwvpa0

| 区分             | 内容                                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| レビュー観点     | [review_criteria_requirement.md][review-criteria-requirement]                                                                                                                                                                                                                                                                                                                         |
| 内蔵規範         | [requirement_principles_spec.md][requirement-principles-spec] / [requirement_format.md][requirement-format] / [spec_design_boundary_spec.md][spec-design-boundary-spec] / [spec_priorities_spec.md][spec-priorities-spec] / [additive_development_spec.md][additive-development-spec] / [frontmatter_format.md][frontmatter-format] / [document_style_guide.md][document-style-guide] |
| プロジェクト固有 | 文書記述・仕様記述規約                                                                                                                                                                                                                                                                                                                                                                |
| 突き合わせ対象   | 対象ファイル内部 / 関連設計書                                                                                                                                                                                                                                                                                                                                                         |

### 3.3 design（設計書・ADR） DLID-7c120qp5qtwx

| 区分             | 内容                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| レビュー観点     | [review_criteria_design.md][review-criteria-design]                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 内蔵規範         | [spec_design_boundary_spec.md][spec-design-boundary-spec] / [design_principles_spec.md][design-principles-spec] / [design_method.md][design-method] / [additive_development_spec.md][additive-development-spec] / [frontmatter_format.md][frontmatter-format] / [adr_format.md][adr-format] / [adr_principles_spec.md][adr-principles-spec] / [document_style_guide.md][document-style-guide] / [deterministic_generation_spec.md][deterministic-generation-spec] / [spec_priorities_spec.md][spec-priorities-spec] |
| プロジェクト固有 | アーキテクチャ・設計規約                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| 突き合わせ対象   | 対象ファイル内部 / 関連要件定義書                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |

### 3.4 plan（計画書） DLID-0vayzdt2agj4

| 区分             | 内容                                                                                                                                                                                                        |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| レビュー観点     | [review_criteria_plan.md][review-criteria-plan]                                                                                                                                                             |
| 内蔵規範         | [plan_principles_spec.md][plan-principles-spec] / [additive_development_spec.md][additive-development-spec] / [frontmatter_format.md][frontmatter-format] / [spec_priorities_spec.md][spec-priorities-spec] |
| プロジェクト固有 | 依存関係・ワークフロー規約                                                                                                                                                                                  |
| 突き合わせ対象   | 対象の計画書内部 / 関連設計書・要件定義書                                                                                                                                                                   |

### 3.5 uxui（UI / UX に関わる文書） DLID-enyjmb2hb2rm

| 区分             | 内容                                                                                              |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| レビュー観点     | [review_criteria_uxui.md][review-criteria-uxui]                                                   |
| 内蔵規範         | [document_style_guide.md][document-style-guide] / [spec_priorities_spec.md][spec-priorities-spec] |
| プロジェクト固有 | デザインシステム・HIG 準拠規約                                                                    |
| 突き合わせ対象   | 対象ファイル内部 / 関連要件定義書・設計書                                                         |

[review-criteria-generic]: review_criteria_generic.md "0aaf2e1f0413 DLID-wm7t1emetwbx"
[review-priorities-spec]: ../review_priorities_spec.md "458b42b8deb4 DLID-dcec6pr177c9"
[scope-proportionality-spec]: ../scope_proportionality_spec.md "be634f5152a6 DLID-s1dhhaprgf1r"
[error-classification-spec]: ../error_classification_spec.md "94496cc6d044 DLID-5ykqs19cdbks"
[review-criteria-code]: review_criteria_code.md "a7ceb082eeaf DLID-spgw9f5y6thy"
[deterministic-generation-spec]: ../deterministic_generation_spec.md "75383cc8c6d8 DLID-tm2m7nv23dqd"
[forge-anti-patterns]: ../forge_anti_patterns.md "0e4a099e332f DLID-wkh7nt1wrds7"
[review-criteria-requirement]: review_criteria_requirement.md "90aabf3f4899 DLID-4zxqtf2m3x6t"
[requirement-principles-spec]: ../requirement_principles_spec.md "8c5971b68aaf DLID-8y2jh2y06761"
[requirement-format]: ../requirement_format.md "c05edc5d1de7 DLID-c13gr4qbk4vm"
[spec-design-boundary-spec]: ../spec_design_boundary_spec.md "e0d1a83f7e47 DLID-h9h90g9wcy8f"
[spec-priorities-spec]: ../spec_priorities_spec.md "b68b930cec1d DLID-f9ny9e932trv"
[additive-development-spec]: ../additive_development_spec.md "3be39e634c1c DLID-cyrk9xr8vcap"
[frontmatter-format]: ../frontmatter_format.md "867507803b4a DLID-jtc4qnjwbdxf"
[document-style-guide]: ../document_style_guide.md "335c3c0eb320 DLID-c59znr7b8f56"
[review-criteria-design]: review_criteria_design.md "0b7187e6bfc6 DLID-0zyw4hj937y9"
[design-principles-spec]: ../design_principles_spec.md "e590554be385 DLID-061pwjejh6yc"
[design-method]: ../design_method.md "157820b1afb7 DLID-pdvdjb49qpr4"
[adr-format]: ../adr_format.md "3a31a2d6bfe3 DLID-ns59za8fens1"
[adr-principles-spec]: ../adr_principles_spec.md "1fb15e199859 DLID-45wzpggz1set"
[review-criteria-plan]: review_criteria_plan.md "fa4854482b2e DLID-31c3mp46a5p2"
[plan-principles-spec]: ../plan_principles_spec.md "33e1e8046cdc DLID-t8jcg5jkb5mj"
[review-criteria-uxui]: review_criteria_uxui.md "f2e598645f12 DLID-e9tn4760zpw5"
