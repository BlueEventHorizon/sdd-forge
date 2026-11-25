---
name: query-db-rules
description: |
  プロジェクトの様々なルールを、キーワード・機能名・自然文で、高速・高品位に、優先度をつけて検索する。
  設計・実装・コーディング・レビュー等、開発作業のあらゆる場面でルールを参照したいときに使う。
user-invocable: true
argument-hint: "task description"
allowed-tools: Skill, Read, Bash, AskUserQuestion
---

ルール文書（category `rules`）を、利用可能な文書検索 backend（doc-link / doc-db）で検索して結果を返す。

この SKILL はルール文書の検索のみを行う。**索引の作成・更新は行わない**（`/forge:update-db-rules` の責務）。
親が依頼している他の作業を引き継いではならない。

**grep を backend の代替として使用しない。** backend の索引に基づかない結果を返すと、利用者は検索の
網羅性を誤認する。

索引の整備が必要な場面では `/forge:update-db-rules` を Skill ツールで起動する。整備の手順を本 SKILL に
複製せず委譲するのは、索引を整備する入口を 1 つに保つためである。渡す引数は backend 名だけであり、
親タスクの指示文を渡さない。

> ❌ 自己再帰禁止: `Skill` ツールで自分自身（`query-db-rules`）および他の `query-db-*` を呼ばないこと（無限再帰）。
> Skill ツールによる `/forge:update-db-rules` の起動は上記のとおり許可される（検索側から更新側への一方向であり循環しない）。

## この検索の性質

単語一致の検索ではない。各文書の要約・キーワード・適用タスクを収めた索引を AI が全件読み、タスクとの関連を意味で判断して選ぶ。

- 渡すのは単語ではなく、**タスクの記述と関連する概念**である。言い換え・上位概念・周辺語を並べて渡すほど当たる
- 索引の要約に載っていない事柄は、本文にあっても引けないことがある

## Procedure

### Step 1: backend の順序を解決する

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_backend/resolve_backend_order.py"
```

exit 0 なら JSON の `order` を先頭から試す。exit 20 なら JSON の `message` を添えて明示エラーとして終了する。

後位へ進む事由は、その backend が利用不能だったときだけである。全て利用不能なら、それぞれの理由を並べて
明示エラーとして終了する。

- `doc-link` の番 → Step 2
- `doc-db` の番 → Step 3

### Step 2: doc-link で検索する

#### Step 2.1: 可用性を判定する

次の 2 つをどちらも満たすとき、doc-link を利用可能とする。満たさなければ利用不能として理由を控え、
Step 1 の次の backend へ進む。理由には、揃っていない SKILL の名前、または `uv` を実行できないことを書き、doc-link の導入状態の確認を促す。

- available-skills に `doc-link:query-docs`・`doc-link:index-docs`・`doc-link:embed-dlid` が揃っている
- `uv` を実行できる（doc-link の script は `uv` で動く）

```bash
command -v uv
```

#### Step 2.2: 検索する

`Skill` ツールで `doc-link:query-docs` を **1 回だけ** 呼ぶ:

```
/doc-link:query-docs --key rules <$ARGUMENTS>
```

索引が現物の文書と合っているかは、doc-link が検索の前に自分で検査する。古いときに再構築するかの
確認と、再構築そのものも doc-link が行う。本 SKILL はそこへ手を加えず、応答を受け取る。

応答で次の 3 つに分ける。

| 応答                                             | 動作                                                                          |
| ------------------------------------------------ | ----------------------------------------------------------------------------- |
| 検索結果（文書の一覧。0 件を含む）が返った       | Step 2.3 へ                                                                   |
| 索引が未構築で、初回の構築が必要だと返った       | Step 4 へ（`--backend doc-link` を指定して整備する）                          |
| 上のどちらでもない（検索できなかった・失敗した） | doc-link が返した内容を添えて明示エラーとして終了する。backend を切り替えない |

**0 件は正しい結果である。** 0 件を受けて、検索対象の拡大・grep での代替を行わない。

#### Step 2.3: 出力形式へ整える

検索結果の各文書の記録されたパスを、返された順のまま、位置引数として渡す。0 件のときは引数なしで呼ぶ。

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_backend/format_link_result.py" "<パス 1>" "<パス 2>"
```

JSON の `result` を検索結果として Step 5 へ進む。パスの一覧を自分で組み立てない。

### Step 3: doc-db で検索する

#### Step 3.1: セッション内でルール文書を変更したか判断する

doc-db は、索引が現物の文書と合っているかを検査しない。このセッションで自分がルール文書を変更している
場合、索引はその変更を含まない。`AskUserQuestion` で索引を更新するか確認し、更新する場合は Skill ツールで
`/forge:update-db-rules` を起動してから Step 3.2 へ進む。

変更していない場合は確認せず Step 3.2 へ進む。**拾えるのは自分がこのセッションで行った変更だけである**
（他セッション・利用者による直接編集・ブランチ切替は判断材料に無い）。

#### Step 3.2: 検索する

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/query_documents.py" "<検索タスク記述>"
```

`$ARGUMENTS`（検索タスク記述）を 1 つの位置引数として渡す。引数を Bash ブロックへ素の形で埋め込まない
（`"` や `` ` `` を含む記述で引用が崩れる）。

| exit code | 動作                                                             |
| --------- | ---------------------------------------------------------------- |
| 0         | JSON の `result` を返して Step 5 へ                              |
| 10        | doc-db 利用不能。理由を控えて Step 1 の次の backend へ           |
| 20        | JSON の `message` を添えて明示エラーとして終了する               |
| 30        | 索引が未整備。Step 4 へ（`--backend doc-db` を指定して整備する） |

**0 件は正しい結果である。** 当該 series はその branch の完全な現在状態なので、0 件を受けて series を
外した再検索・検索対象の拡大・grep での代替を行わない。0 件のまま成功として返す。

### Step 4: 未整備の索引を整備する

`AskUserQuestion` で整備の承認を得る。

**件数を自前に数えて提示しない。** doc-link 経路で索引される件数を決めるのは doc-link 側であり、
forge が数えた値はその件数と一致する保証を持たない。

- 承認された → Skill ツールで `/forge:update-db-rules --backend <確定済みの backend>` を起動する。
  完了後に Step 2.2 または Step 3.2 の検索を **1 回だけ** 再実行し、Step 5 へ進む。整備が失敗した場合は
  検索せず明示エラーとして終了する
- 見送られた → 検索を行わず、索引が未整備である事実を報告して終了する。失敗として扱わない

`--backend` を渡すのは、既に確定させた backend と別の索引が整備されるのを防ぐためである。

### Step 5: 結果を返す

`Required documents:` 形式のパスリストを先頭に置き、その後に次を添える。

- 利用した backend
- 先位を利用できず後位を利用した場合: その理由
- 設定で優先 backend を指定していて満たされなかった場合: 指定が満たされなかったこととその理由
- doc-link で検索した場合: doc-link が返した索引の鮮度の通知（最新か、古い可能性があるか）。
  doc-link が検索の前に索引を再構築した場合は、その事実
- doc-db の起動を試行した場合（JSON の `startup` が未試行以外）: その結果
- Step 3.1 の確認を行った場合: 索引を更新したか否か
- Step 4 で索引を整備した場合: その事実
- 実在しないパスを結果から除外した場合（JSON の `notices`）: その件数

## Output Format

```
Required documents:

- docs/rules/xxx.md
- docs/rules/yyy.md
```

## Notes

- doc-link の ToC 識別キーは `rules` である。`/forge:update-db-rules` が同じ ToC 識別キーで索引を構築する。
- doc-db の key は `{project_name}-rules`、series は現在の git branch。`/forge:update-db-rules` と同一の series を検索する。
