---
doc_link_id: DLID-vfdedgq63evv
---

# DES-016 .doc_structure.yaml バージョン管理設計 DLID-k4yt74q513zs

## 概要 DLID-jsh7ymjq4ctb

`.doc_structure.yaml` のバージョン管理・マイグレーション方式を定義する。
[COMMON-REQ-001][common-req-001-versioned-migration] に準拠し、Python スクリプトによる機械的なマイグレーションを実現する。
ファイルの形式そのものは、[.doc_structure.yaml フォーマット仕様][doc-structure-format]が定める。

## バージョン識別子 DLID-073rb28bwvev

YAML コメント行でバージョンを記録する:

```yaml
# doc_structure_version: 3.0
```

- **フォーマット**: `X.Y`（X = メジャー、Y = マイナー）
- **マーカー**: `doc_structure_version:` — `.doc_structure.yaml` 独自のバージョン識別子
- **配置**: ファイル先頭のコメントブロック内

### バージョン番号の意味 DLID-ywvqdyc08sjr

| 変更種別                                   | バージョン          | 例        |
| ------------------------------------------ | ------------------- | --------- |
| 破壊的変更（フィールド削除、構造変更）     | メジャー X を上げる | 2.0 → 3.0 |
| 後方互換の追加（新オプショナルフィールド） | マイナー Y を上げる | 2.0 → 2.1 |

## マイグレーション方式 DLID-7rqkv2xxzyk8

COMMON-REQ-001（段階的バージョンマイグレーション要件）に準拠する。

### マイグレーションフロー DLID-8hgbevz33jfr

```text
1. .doc_structure.yaml を読み込み
2. バージョン検出（get_major_version）
3. detected_version < CURRENT_VERSION なら段階的マイグレーション適用
4. マイグレーション後のデータを返す（元データは書き換えない: NFR-01）
```

### CURRENT_VERSION 定数 DLID-yd1kh5vgjdpp

```python
CURRENT_VERSION = 3  # FR-02-5
```

### MIGRATIONS レジストリ DLID-7hfd7apr9759

メジャーバージョン変更時に、構造変換関数を登録する:

```python
MIGRATIONS = {
    2: migrate_v1_to_v2,  # v1 → v2: config.yaml 互換フォーマット採用
    3: migrate_v2_to_v3,  # v2 → v3: 文書検索 backend の内部フィールド除去
}
```

- キー: ターゲットバージョン番号（FR-02-2）
- 値: 変換関数 `fn(content: str) -> str`（FR-03-1: 1入力1出力。本適用では str テキスト操作）
- 段階的適用: `detected_version < v <= CURRENT_VERSION` の範囲を昇順に実行（FR-02-1, FR-02-3）
- 各関数は前段の出力を入力として受け取る（FR-02-4: チェーン実行）
- 冪等であること（FR-03-2）、副作用を持たないこと（FR-03-3）

### エラーハンドリング DLID-n3q514qr4yqb

- マイグレーション関数は純粋関数（FR-03-3）であり、例外はコードバグとして伝播させる（FR-04-1）。サイレントフォールバックで不具合を隠蔽しない
- 検出バージョンが CURRENT_VERSION より大きい場合、マイグレーションをスキップしそのまま使用する（FR-04-2）
- バージョン検出に失敗した場合は v1 として扱う（FR-04-3, FR-01-2）

### マイグレーション追加手順 DLID-0xpfh4dyky1p

1. `migrate_vN_to_vN1(content: str) -> str` を実装する（FR-05-2: 既存関数は変更しない）
2. `MIGRATIONS[N+1] = migrate_vN_to_vN1` を登録する（FR-02-2）
3. `CURRENT_VERSION` を `N+1` に更新する（FR-02-5）

## 実装上の設計判断 DLID-y0787g0dwmfh

### data の型: str（テキスト操作） DLID-vyb83697bdvv

標準ライブラリに YAML パーサーがない（NFR-02）ため、マイグレーション関数はテキスト操作で実装する。

- 入力: `str`（`.doc_structure.yaml` の生テキスト）
- 出力: `str`（マイグレーション後のテキスト）
- バージョンマーカー（`# doc_structure_version: X.0`）はコメント行なので dict 変換すると消える。テキスト操作ならコメント行を自然に保持できる

COMMON-REQ-001 の設計パターンは `data` を dict として描いているが、本適用では `str` とする。要件 FR-03-1「1つ前のバージョンの出力形式を入力として受け取り、ターゲットバージョンの形式を返す」は str でも満たせる。

```python
MIGRATIONS = {
    2: migrate_v1_to_v2,  # fn(str) -> str
    3: migrate_v2_to_v3,  # fn(str) -> str
}
```

### バージョン検出の再利用方法 DLID-w2s47vk06a3m

`resolve_doc_structure.py` の `get_version()` / `get_major_version()` はテキストベースの正規表現マッチであり、`migrate_doc_structure.py` から再利用可能。

方法: `sys.path` にスクリプトのディレクトリを追加して import する。`resolve_doc_structure.py` は `plugins/forge/scripts/doc_structure/`（`migrate_doc_structure.py` と同一ディレクトリ）に配置されているため:

```python
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent  # plugins/forge/scripts/doc_structure/
sys.path.insert(0, str(SCRIPT_DIR))
from resolve_doc_structure import get_version, get_major_version
```

### v1 形式の構造 DLID-85y47efzs6d5

git 履歴から確認した v1 形式:

```yaml
version: "1.0"

specs:
  design:
    paths: [docs/specs/design/]
    description: "Design specifications..."
  plan:
    paths: [docs/specs/plan/]
    description: "Development plans..."
  requirement:
    paths: [docs/specs/requirement/]
    description: "Functional and non-functional requirements"

rules:
  rule:
    paths: [docs/rules/]
    description: "Development rules..."
```

特徴:

- `version: "1.0"` — YAML フィールドとしてバージョンを記録（v2+ はコメント行）
- `{category}.{doc_type}.paths` — doc_type がキー、paths が配列
- `description` フィールドあり（v2+ では廃止）

### migrate_v1_to_v2 の変換仕様 DLID-5v5s8q90j07f

v1 → v2 変換:

1. `version: "1.0"` 行を削除
2. `# doc_structure_version: 2.0` コメント行を先頭に追加
3. `{category}.{doc_type}.paths` → `{category}.root_dirs` + `{category}.doc_types_map` に変換
4. `description` フィールドを削除
5. `patterns`, `toc_file`, `checksums_file`, `work_dir`, `output`, `common` を追加（v2 形式のデフォルト値）

### migrate_v2_to_v3 の変換仕様 DLID-3rr35vwh9r0j

v2 → v3 変換:

1. `# doc_structure_version: 2.0` → `# doc_structure_version: 3.0` に置換
2. `toc_file`, `checksums_file`, `work_dir` 行を削除
3. `output:` セクション（`header_comment`, `metadata_name`）を削除
4. `common:` セクション全体を削除
5. `root_dirs`, `doc_types_map`, `patterns` は保持

---

## マイグレーションスクリプト DLID-wa9dw98yxv8z

### 配置 DLID-jykgp085c2xq

```text
plugins/forge/scripts/doc_structure/migrate_doc_structure.py
```

forge プラグインのスクリプトとして配置する。

### CLI インターフェース DLID-n7p83kcr1743

```bash
# マイグレーション実行（結果を stdout に出力。元ファイルは書き換えない: NFR-01）
python3 migrate_doc_structure.py <file_path>

# ドライラン（マイグレーション内容を表示するが適用しない）
python3 migrate_doc_structure.py <file_path> --dry-run

# バージョン情報のみ表示
python3 migrate_doc_structure.py <file_path> --check
```

### 出力仕様 DLID-r2mckrv3eqz3

| モード      | stdout                                 | 終了コード               |
| ----------- | -------------------------------------- | ------------------------ |
| 通常        | マイグレーション後の YAML テキスト     | 0: 成功, 1: エラー       |
| `--dry-run` | 適用されるマイグレーション一覧（JSON） | 0: 変更あり, 2: 変更なし |
| `--check`   | バージョン情報（JSON）                 | 0                        |

```bash
# --check の出力例
python3 migrate_doc_structure.py .doc_structure.yaml --check
# → {"detected_version": 2, "current_version": 3, "needs_migration": true}

# バージョン検出失敗時（FR-04-3: v1 として扱う）
# → {"detected_version": 1, "current_version": 3, "needs_migration": true}

# --dry-run の出力例
python3 migrate_doc_structure.py .doc_structure.yaml --dry-run
# → {"migrations": [{"from": 2, "to": 3, "description": "Remove document-search backend internal fields"}]}

# 通常実行の出力例（stdout にマイグレーション後の YAML）
python3 migrate_doc_structure.py .doc_structure.yaml > .doc_structure.yaml.new
mv .doc_structure.yaml.new .doc_structure.yaml
```

### 書き出しの責務分担 DLID-3pte09120gy1

NFR-01「元データを書き換えない」に従い、スクリプトは stdout に出力するのみ。ファイルへの書き出しは呼び出し元（`setup-doc-structure` SKILL.md または手動）が行う。

### setup-doc-structure からの呼び出しフロー DLID-qybg2ntza657

`setup-doc-structure` は、Step 1（既存ファイルの確認）で `check_doc_structure.py` を呼ぶ。この script は `migrate_doc_structure.py` と同じディレクトリにあり、存在確認・バージョン検出・マイグレーション要否を、1 回の呼び出しで JSON として返す。バージョンの検出には、`migrate_doc_structure.py` の `detect_version` と `CURRENT_VERSION` を使う。

| 出力の項目                             | 意味                                                        |
| -------------------------------------- | ----------------------------------------------------------- |
| `exists`                               | `.doc_structure.yaml` があるか                              |
| `error`                                | 読み込みに失敗したときの理由（`exists` が真のときだけ持つ） |
| `needs_migration`                      | 検出したバージョンが `CURRENT_VERSION` より小さいか         |
| `detected_version` / `current_version` | 検出したバージョンと、現行のバージョン                      |
| `content`                              | ファイルの内容                                              |

SKILL は、出力で 3 つに分岐する。

```text
1. exists: false → Step 2（ディレクトリスキャン）へ
2. error あり → エラーの内容を利用者に報告して終了
3. exists: true →
   a. needs_migration: true の場合:
      - AskUserQuestion:「.doc_structure.yaml を v{detected_version} → v{current_version} にマイグレーションしますか？」
      - Yes → python3 migrate_doc_structure.py <path> で変換結果を取得 → Write で書き出し
      - No → b へ
   b. content を表示し、既存の内容を確認する
   c. 更新する / 再生成する / このまま使う、を利用者に確認する
```

---

## ユーザー設定の保持ルール DLID-ttpg4fg62d28

マイグレーション時に以下のユーザー設定を保持する:

| 設定                   | 保持条件   |
| ---------------------- | ---------- |
| `root_dirs`            | 非空の場合 |
| `doc_types_map`        | 非空の場合 |
| `patterns.target_glob` | 非空の場合 |
| `patterns.exclude`     | 非空の場合 |

> **Note**: `output.*`, `common.*`, `toc_file`, `checksums_file`, `work_dir` は、文書検索 backend の内部フィールドであり、v3 で `.doc_structure.yaml` から除去された。これらは backend が自分で管理する。v2 のファイルにこれらが残っていれば、`migrate_v2_to_v3` が削除する。保持の対象にはならない。

## バージョン検出 API DLID-6x6g57m5xw8y

`resolve_doc_structure.py` が提供する:

```bash
python3 resolve_doc_structure.py --version
# → {"status": "ok", "version": "3.0", "major_version": 3}
```

```python
from resolve_doc_structure import get_version, get_major_version

content = open(".doc_structure.yaml").read()
version = get_version(content)  # "3.0"
major = get_major_version(content)  # 3
```

[common-req-001-versioned-migration]: ../../common/requirements/COMMON-REQ-001_versioned_migration.md "857319588069 DLID-dqkf6wa1z2cp"
[doc-structure-format]: ../../../../plugins/forge/docs/doc_structure_format.md "50a324934bb2 DLID-cbr02jpbxfcs"
