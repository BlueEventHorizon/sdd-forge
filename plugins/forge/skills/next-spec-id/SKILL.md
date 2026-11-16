---
name: next-spec-id
user-invocable: false
description: |
  ブランチ間で衝突しない、次の Spec ID（SCR / DES / ADR 等任意プレフィックス）を発行する。
  要件定義書・設計書・ADR（アーキテクチャ決定記録）の作成時に ID の重複を防ぐために呼び出される。
  TASK ID（計画書内の連番）は対象外（計画書 1 件の中だけで閉じるため、`start-plan` が自ら採番する）。
argument-hint: "<プレフィックス> [共有するプレフィックスのカンマ区切り]"
---

# next-spec-id スキル

このスキルは、次の Spec ID の発行のみを行う。親が依頼している他の作業を引き継いではならない。

仕様書（要件定義書・設計書・ADR）の次の連番 ID を、全ブランチと現在の作業ツリーのスキャンで求める。ブランチ間および未コミット文書との ID 重複を防ぐ。

forge 内の他スキルからの呼び出し専用（`user-invocable: false`）。他スキルは、本スキルを `Skill` ツールで呼ぶ。本スキルのスクリプトを直接呼ばない。

## 呼び出しの契約

### 入力（`Skill` ツールの `args`）

| 引数              | 内容                                                                                                |
| ----------------- | --------------------------------------------------------------------------------------------------- |
| 第 1 引数（必須） | 発行する ID のプレフィックス（例: `SCR` / `DES` / `ADR` / `GLS`）                                   |
| 第 2 引数（任意） | 通し番号を共有するプレフィックスのカンマ区切り（例: `ADR,DES`）。指定した全プレフィックスを横断する |

どのプレフィックスを使うかは**呼び出し側が決める**。本スキルは ID 体系の知識を持たない。

1. プロジェクト固有のルールがあればそれに従う
2. なければ forge の各文書型の format / principles を参照する（要件 → `requirement_format.md`、設計 → `DES`、ADR → `adr_format.md`）

ADR と DES は同一ディレクトリで通し番号を共有するため、ADR を発行する呼び出しは第 2 引数に `ADR,DES` を渡す。

### 出力

発行した ID（`next_id`）と、重複の有無（`duplicates`）を返す。呼び出し側は、`next_id` をファイル名の先頭に使う。`duplicates` が空でなければ、利用者に提示する。

| 項目         | 内容                                                                                   |
| ------------ | -------------------------------------------------------------------------------------- |
| `next_id`    | 次の ID（例: `ADR-005`）                                                               |
| `duplicates` | 異なるファイルが同じ ID（共有採番では同じ番号）を主張している衝突。空なら衝突なし      |
| 失敗         | 発行できなかった理由（`message`）。ID を自分で推測して補わず、そのまま呼び出し側へ返す |

## 手順

1. 入力の第 1 引数・第 2 引数を読み取る。第 1 引数が無ければ、不足として返し、ID を発行しない
2. 次を実行する（第 2 引数があるときだけ `--share-prefixes` を付ける）

   ```bash
   SCRIPT="${CLAUDE_SKILL_DIR}/scripts/scan_spec_ids.py"

   python3 "$SCRIPT" <プレフィックス>
   python3 "$SCRIPT" <プレフィックス> --share-prefixes <共有するプレフィックス>
   ```

3. stdout の JSON の `status` を確認する
   - `ok` → `next_id` と `duplicates` を呼び出し側へ返す
   - `error` → `message` をそのまま返す

### 出力 JSON（スクリプトの出力）

```json
{
  "status": "ok",
  "next_id": "SCR-016",
  "prefix": "SCR",
  "max_number": 15,
  "base_branch": "develop",
  "branches_scanned": 7,
  "ids_found": 15,
  "duplicates": []
}
```

共有採番（`--share-prefixes`）では、`shared_with` に共有先のプレフィックスが入る。

`duplicates` の要素は、衝突に関与する全 ID（`ids`。共有採番では `["ADR-007", "DES-007"]` のように複数になりうる）、同じ番号を主張している異なるファイルパス（`paths`）、該当ファイルが存在するブランチ（`branches`）を持つ。同一パスのファイルが複数ブランチに存在するだけの同一履歴由来のケースは、報告されない。

エラー時は `{"status": "error", "message": "..."}` を返す。

## 動作概要

1. 文書の置き場（specs の `root_dirs`）を取得する
2. `git fetch --quiet` でリモートを最新化する
3. ベースブランチ（develop or main）を特定する
4. ベースブランチから派生した全ブランチをスキャンする（ローカル + リモート）
5. `git ls-tree` で各ブランチの specs ディレクトリを走査する
6. `git ls-files --cached --others --exclude-standard` で現在の tracked／untracked 文書を走査する
7. 指定プレフィックスの最大番号を検出する
8. 異なるファイルが同じ ID / 共有番号を主張する衝突があれば `duplicates` に記録する
9. 最大番号 + 1 を返す
