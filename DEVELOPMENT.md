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

## 4. テスト実行

```bash
# 全テスト一括実行
python3 -m unittest discover -s tests -p 'test_*.py' -v

# 特定モジュールのみ
python3 -m unittest tests.forge.review.test_xxx -v
```

テストの配置ルールは `CLAUDE.md` の「Testing」セクションを参照。

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
- [docs/rules/claude_code_authoring_guide.md](docs/rules/claude_code_authoring_guide.md) — SKILL.md / カスタム Agent の書き方の規約
- [docs/rules/claude_code_reference.md](docs/rules/claude_code_reference.md) — Claude Code の SKILL・プラグイン・Agent の仕組みの事実
- `docs/rules/implementation_guidelines.md` — 実装ガイドライン
