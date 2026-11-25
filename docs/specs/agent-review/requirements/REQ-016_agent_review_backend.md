---
doc_link_id: DLID-3bmft1apetsm
---

# REQ-016 agent-review バックエンド DLID-5jcxtvv9k65q

## 1. 背景と目的 DLID-qcs4gh1gyp7n

既定のレビューを開始するために、外部ツール、メッセージ DB、常駐セッションを準備する必要があると、プラグイン単体での利用が成立しない。

`agent-review` は、プラグインに同梱した read-only カスタム Agent `reviewer` をレビュー実行主体とし、外部依存なしでバックエンドの契約（可用性検査と `retains_context` の宣言。[REQ-013][req-013] FNC-1318）を満たす。ラウンドを越える状態を持たず、レビュー対象の変更、履歴の保存、常駐資源の管理を行わない。

reviewer の起動と所見の受け渡しは、レビュー本体が直接行う（[REQ-029][req-029]）。

## 2. スコープ DLID-24t8hs6x4ez5

### 対象 DLID-9b8a30w44dmn

- 可用性検査
- `reviewer` Agent が read-only であること（役割定義とツール制約）
- `retains_context` が `false` であることの申告

### 対象外 DLID-31vdqj9fys9h

- reviewer の起動、所見の書き出しと受け渡し（レビュー本体と REQ-029 の仕事）
- 所見を受けた対象ファイルの修正
- ラウンド間のセッション継続
- レビュー履歴の保存と復元
- 人間が常駐レビュアへ途中介入するための通信経路
- バックエンド間の自動フォールバック

## 3. 機能要件 DLID-ty0msghbet5x

### FNC-1601 read-only レビュア [MANDATORY] DLID-mgtyz9cxn57a

実行主体は、レビュー判断だけを役割とするカスタム Agent `reviewer` である。`reviewer` は次の操作を行ってはならない。

- ファイルの作成、変更、削除
- git の index、commit、branch、remote の変更
- レビュー対象プロジェクトまたは外部サービスへの書き込み
- 修正コマンド、formatter、generator など、成果物を変更し得るコマンドの実行

対象と規範を読むためのファイル参照、検索、read-only な git 照会は許可する。所見は、`reviewer` 専用の script を介してだけ書き出す。

### FNC-1602 1 ラウンド 1 Agent [CRITICAL] DLID-mh9ffqf4s4fx

`reviewer` は、ラウンドごとに新しい Agent として起動される（起動するのはレビュー本体。REQ-029 FNC-302）。Agent は 1 ラウンドの結果を書き出した時点で役割を終え、次ラウンドへ再利用しない。

各ラウンドの `reviewer` は、そのラウンドで読む依頼と、そこから明示的に参照される対象・規範だけを根拠に判定する。前ラウンドの Agent コンテキストを暗黙に継承しない。

### FNC-1604 可用性検査 [MANDATORY] DLID-mq7ej90kpf23

バックエンドは依頼を公開する前に、次の条件を副作用なく検査する。

- カスタム Agent `reviewer` の定義を解決できる
- `reviewer` が read-only のツール制約と役割指示を持つ
- `reviewer` が呼ぶ script と読む文書が、プラグイン内に存在する

全条件を満たす場合だけ利用可能と返し、あわせて `retains_context` が `false` であることを申告する。不足がある場合は、条件ごとに利用者が読める説明を返し、Agent を起動しない。

### FNC-1606 履歴非対応 [CRITICAL] DLID-dqwr8a58ab1k

バックエンドはレビュー履歴を永続化しない。中断したレビューを同一 `review_id` で再開する経路を持たない。利用者がレビューの継続を求める場合、本体は新しい `review_id` で新規レビューを開始する。

## 4. 非機能要件 DLID-98tgf3rv1bwy

### NFR-1601 非永続性 [CRITICAL] DLID-8drr6mxazr7n

`agent-review` は、DB、ファイル上の履歴、常駐プロセス、再利用セッションを作成しない。可用性検査の後に、バックエンドが所有する資源を残さない。

### NFR-1602 外部依存の排除 [CRITICAL] DLID-79xpgntmyf5k

`agent-review` の成立条件は、forge プラグインとホストが提供するカスタム Agent 実行機能だけとする。端末多重化ツール、メッセージング基盤、常駐セッション、外部デーモンを前提にしない。

### NFR-1603 fail closed [MANDATORY] DLID-0drhsb4j2nsj

可用性、read-only 制約のいずれかを確認できない場合、利用可能として扱わない。理由を伴う利用不可として返す。

## 5. 受け入れ基準 DLID-7h61zq90ga5t

1. 連続する 2 ラウンドで異なる `reviewer` Agent が起動され、Agent セッションが再利用されない
2. `reviewer` の役割定義が、成果物の変更・他の実行主体の起動・外部への書き込みを禁じており、`reviewer` が利用できるツールに編集専用の手段と他の実行主体を起動する手段が含まれていない
3. 可用性検査が `reviewer` の定義、read-only の役割指示、`reviewer` が呼ぶ script と読む文書が**意図どおり書かれ、揃っていること**を副作用なく確認し、不足を条件ごとに返す
4. `retains_context` が `false` と申告される
5. 可用性検査の後に DB、履歴ファイル、常駐セッションが作成されていない

## 6. 未確定事項 DLID-60fwetem8kfn

なし。

[req-013]: ../../forge/requirements/REQ-013_review_policy.md "8447df198f9e DLID-yg0c67zs3zky"
[req-029]: ../../review/requirements/REQ-029_review_exchange.md "d635cdb8307b DLID-5vrs9fnet7de"
