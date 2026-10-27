# ローカル開発・デバッグガイド

**目的**: プラグイン開発時のローカルデバッグ手順をまとめる
**適用範囲**: このリポジトリのコントリビューター

---

## 1. プラグインのローカルロード

### 1.1 forge をロードする [MANDATORY]

```bash
claude --plugin-dir ./plugins/forge
```

セッション起動後、すべての forge スキルが `/forge:<skill>` として使用可能になる。

`.claude/skills/` 配下のローカル skill（Issue 駆動・Figma 系など）は、`--plugin-dir` を指定しなくてもプロジェクトの skill として読み込まれ、`/<skill>` で起動できる。commit / PR / Issue 作成は外部の anvil plugin が提供する。

### 1.2 マーケットプレイス経由（配布後の動作確認）

```bash
/plugin marketplace add BlueEventHorizon/sdd-forge
/plugin install forge@sdd-forge
```

> ローカル変更を反映するには `--plugin-dir` を使う。マーケットプレイス経由はリモートの公開版を取得する。

### 1.3 manifest と配布経路の検証

`marketplace.json` と `plugin.json` を変えたときは、次を実行し、どちらも `Validation passed` になることを確かめる。

```bash
claude plugin validate . --strict                  # marketplace.json
claude plugin validate ./plugins/forge --strict    # plugin.json
```

`--plugin-dir` は `marketplace.json` を読まない。カタログ自体（`source` のパスなど）の確認は、ローカルのリポジトリを marketplace として登録して行う。

```
/plugin marketplace add ./
/plugin install forge@sdd-forge
/reload-plugins
```

> `.DS_Store` と、アイコンが無いことの警告は、無視してよい。前者はコミットされておらず、後者は公式ディレクトリへ申請するときの項目である。

---

## 2. スキル動作の確認手順

### 2.1 起動後の確認

```
/forge:help        # forge スキル一覧
```

### 2.2 SKILL.md を編集した場合

セッションを再起動する（`--plugin-dir` オプション付きで再実行）。編集内容はセッション内では即時反映されない。

```bash
# セッションを終了して再起動
claude --plugin-dir ./plugins/forge
```

---

## 3. Python スクリプトの単体確認

SKILL.md から呼び出されるスクリプトは、Claude セッションを介さずに直接実行して動作確認できる。

```bash
# レビュー対象の自動検出
python3 plugins/forge/skills/review/scripts/resolve_targets.py --mode diff

# ディレクトリスキャン（メタデータ JSON 出力）
python3 plugins/forge/scripts/doc_structure/classify_dirs.py [プロジェクトルート]
```

`python3` が見つからない環境では `/opt/homebrew/bin/python3` を使う。

---

## 4. テスト

テストは 2 種類ある。テストの実行・追加・配置の判断では、本節を読む。

| 種類                  | 置き場      | 対象                                | 実行                                |
| --------------------- | ----------- | ----------------------------------- | ----------------------------------- |
| 単体テスト            | `tests/`    | `plugins/` 配下の Python スクリプト | 下記コマンド。CI のゲートに含まれる |
| AI の判断を試すテスト | `ai_tests/` | Agent・SKILL の判断（AI の出力）    | 手動。CI のゲートに含めない         |

### 4.1 単体テスト

```bash
# 全テスト一括実行
python3 -m unittest discover -s tests -p 'test_*.py' -v

# 特定モジュールのみ
python3 -m unittest tests.forge.review.test_xxx -v
```

- `plugins/` 配下の Python スクリプトにはテストが必須。SKILL.md は自動テストが難しいため例外
- `.claude/` 配下のローカルスキル・スクリプトはテスト対象外
- `tests/` にプラグイン名・スキル名で分類して置く（例: `tests/forge/review/`、プラグイン横断は `tests/common/`）
- ファイル名は `test_{module}.py`
- テストのディレクトリ名は、対象のスキル名と一致させる。スキルを改名したら、テストのディレクトリも同じ変更で改名する

### 4.2 AI の判断を試すテスト

判定が揺れ、実行に費用がかかるため、CI のゲートに含めず、手動で実行する。

- Markdown だけで書く。置き場は `ai_tests/<プラグイン名>/<対象名>/`（例: `ai_tests/forge/adr-writer/`）
- 各ディレクトリの `README.md` に、目的・手順・結果の読み方を書く。実行はその手順に従う
- 実行を補助するスクリプトは置かない（道具がテストの対象になるため）

---

## 5. フォーマット

```bash
dprint fmt      # Python / TOML / Markdown / YAML に適用
dprint check    # 差分チェックのみ（CI 向け）
```

設定ファイル: `dprint.json`

---

## 6. デバッグのポイント

### 6.1 スキルが認識されない

- `--plugin-dir` のパスが正しいか確認（`./plugins/forge` のように相対パスで指定）
- `plugins/{plugin}/.claude-plugin/plugin.json` が壊れていないか確認
- `plugins/{plugin}/skills/{skill}/SKILL.md` の frontmatter `user-invocable: true` を確認

### 6.2 スクリプトが期待した動作をしない

コード読解による推論で 2〜3 回修正しても解決しない場合は `print()` / 変数ダンプで実際の状態を観測する。観測後にログを除去すること（`CLAUDE.md` Debugging セクションも参照）。

### 6.3 スキル間の連携を確認したい

`--plugin-dir` で forge をロードした状態で（ローカル skill は自動で読み込まれる）、実際のユーザー操作をトレースする。スキルが別スキルを `Skill` ツール経由で呼び出す場合も同一セッション内で解決される。

---

## 7. 参考

- `CLAUDE.md` — リポジトリ全体の規約・構成説明
- [docs/rules/plugin_claude_code_authoring_guide.md](docs/rules/plugin_claude_code_authoring_guide.md) — SKILL.md / カスタム Agent の書き方の規約（汎用）
- [docs/rules/plugin_claude_code_reference.md](docs/rules/plugin_claude_code_reference.md) — Claude Code の SKILL・プラグイン・Agent の仕組みの事実（汎用）
- [docs/rules/forge_claude_code_authoring_policy.md](docs/rules/forge_claude_code_authoring_policy.md) — forge が決めた作成方針
- [docs/rules/plugin_implementation_guidelines.md](docs/rules/plugin_implementation_guidelines.md) — 実装ガイドライン（汎用）
