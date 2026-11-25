---
doc_link_id: DLID-9byg0qbksas5
---

# ADR-091 forge の決定記録 DLID-nw62e7j4zbar

## 1. 内蔵ドキュメント検索の関連選定係を、Bash を持ち script 経由で結果を渡す構成にする DLID-wjpj3mxgggen

### 1.1 コンテキスト DLID-4d5ynpb3kd0m

従来の関連選定係（`rules-query-worker`）と、DES-001 の内蔵検索に関する記述は、関連選定係に `Bash` を持たせない read-only の設計であり、lint がそれを検査していた。一方、[agent データ受け渡し規範][agent-data-exchange]は、識別値だけを運び、依頼と結果は script が JSON として書き、成否は結果に置かれた終了の値で表すことを求める。この型を使うには、関連選定係が script を呼ぶ手段（`Bash`）を持つ必要がある。

収集系の agent が成果物を書かず、結果を return value で返す設計が既存の設計書（[DES-022][des-022]）にある。そのため、将来の設計者・AI・reviewer が「read-only に戻し、結果は return value で返せばよい」と提案する見込みが高い。この提案が誤りであることは、コード・ルール・仕様を読むだけでは分からない。

要件へ戻さず設計書に書く理由は次のとおりである。[REQ-035][req-035] は、結果の形（`Required documents:` とパスの一覧）と、検索以外の書き込みをしないことを定める。関連選定係のツール構成と受け渡しの方式は How であり、設計の責務である。この設計は要件定義書に無いため、利用者の承認のもとで採った。承認の引用は次のとおりである。

> doc-link の workerがJSONを返しているなら、forgeも返せるので、それで終わりでは？といっている。そもそも問題はそこでは？
>
> 全て承認する

### 1.2 決定 DLID-xpjcrcmwf6aj

関連選定係を、read-only（`tools` に `Bash` を含めず、結果は return value で返す）から、`tools` に `Bash` を持ち、結果を script 経由の JSON で受け渡す設計へ転換する。

- 受け渡しは、検索 ID だけを運び、依頼と結果は script が JSON として書き、成否は結果に置かれた終了の値で表す（agent データ受け渡し規範に従う）
- 書き込みの禁止は、物理的な許可ではなく、Role 制約と、受け渡し係の照合（渡せる文書を内蔵索引のパスに限る）が支える
- 構成は、[DES-072][des-072] の reviewer（`Bash` を持つ read-only のカスタム Agent）と同じである

設計は [DES-090][des-090] の §6・§8.3・§8.9 にある。

### 1.3 検討した代替案 DLID-kt22z81n4t27

| 代替案                                                                                                                   | 棄却理由                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 関連選定係を read-only のまま（`tools` は `Read, Grep, Glob`）にし、結果を return value で返す。受け渡し規範の例外とする | 規範の例外になり、他の agent（実装戦略・ADR・レビュー）との受け渡しの型が 2 種類になる。同じ役割のものを並べないため、規範に合わせる。得られる利点は read-only の物理的な担保を保てることだが、`Bash` を持つことの代償は、DES-072 の reviewer と同じ層（Role 制約と受け渡し係の照合）で支える |

### 1.4 影響 DLID-4rm0pqtv0j81

- 関連選定係は `Bash` を持つため、書き込みの禁止は、物理的な許可ではなく、Role 制約と、受け渡し係の照合（渡せる文書を内蔵索引のパスに限る）が支える
- 関連選定係の受け渡しの型は、他の agent（実装戦略・ADR・レビュー）と同じになる
- 上記以外に、渡された内容から導ける影響は示されていない

[agent-data-exchange]: ../../../rules/forge_agent_data_exchange_rules.md "d359747d755f DLID-7zh3q09p2acs"
[des-022]: ../design/DES-022_parallel_agent_output_contract_design.md "02eb53006efc DLID-5h7wqxcknyha"
[des-072]: ../../agent-review/design/DES-072_agent_review_backend_design.md "ef29f0fe6897 DLID-rzp2zxe38068"
[des-090]: ../design/DES-090_builtin_docs_search_design.md "ecbe6c8ae7b1 DLID-m0zzg6nfe1sf"
[req-035]: ../requirements/REQ-035_builtin_docs_search_spec.md "25b40d946c4c DLID-vr7dyvw3y5qz"
