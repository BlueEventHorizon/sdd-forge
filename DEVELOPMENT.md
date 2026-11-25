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

## 4. テストと lint

検査は 4 種類ある。検査の実行・追加・配置の判断では、本節を読む。

| 種類                  | 置き場      | 対象                                                         | 実行                                |
| --------------------- | ----------- | ------------------------------------------------------------ | ----------------------------------- |
| 単体テスト            | `tests/`    | `plugins/` 配下・`lint/`・`ai_lint/` の Python スクリプト    | 下記コマンド。CI のゲートに含まれる |
| lint                  | `lint/`     | リポジトリの成果物（文書・設定・配布物の定義・ソースの文面） | 下記コマンド。CI のゲートに含まれる |
| AI-Linter             | `ai_lint/`  | 成果物の文章の意味（SKILL・agent 定義が述べている内容）      | 下記コマンド。ローカルで実行する    |
| AI の判断を試すテスト | `ai_tests/` | Agent・SKILL の判断（AI の出力）                             | 手動。CI のゲートに含めない         |

単体テストと lint は別の検査である。どちらに置くかは、失敗が何を意味するかで決める。

- **単体テスト**: コードを実行して、振る舞いを確かめる。失敗は、コードが意図どおりに動かないことを意味する
- **lint**: 成果物を実行せずに、規則と照合する。失敗は、成果物が規則に反していることを意味する

lint と AI-Linter は、判定の手段で分ける。

- **lint**: script だけで判定できる事実を見る（frontmatter の値、ファイルの実在、JSON の値の一致など、両側が構造化されているもの）
- **AI-Linter**: 文章を読まないと判定できないことを、判定モデルに問う。自然文を、文字列の一致や正規表現で読んで代用しない

### 4.1 単体テスト

```bash
# 全テスト一括実行
python3 -m unittest discover -s tests -p 'test_*.py' -v

# 特定モジュールのみ
python3 -m unittest tests.forge.review.test_xxx -v
```

- `plugins/` 配下の Python スクリプトにはテストが必須。SKILL.md は自動テストが難しいため例外
- `.claude/` 配下のローカルスキル・スクリプトはテスト対象外
- `tests/` にプラグイン名・スキル名で分類して置く（例: `tests/forge/review/`）。`lint/` の検査ロジックの単体テストは `tests/lint_rules/` に、`ai_lint/` の単体テストは `tests/ai_lint_unit/` に置く（`tests/lint/`・`tests/ai_lint/` は、直下の同名のパッケージと衝突するので使わない）
- ファイル名は `test_{module}.py`
- テストのディレクトリ名は、対象のスキル名と一致させる。スキルを改名したら、テストのディレクトリも同じ変更で改名する
- テストがリポジトリのルートを必要とするときは、`from tests import REPO_ROOT` で得る。`Path(__file__).resolve().parents[N]` で自力では求めない（ディレクトリを動かすと `N` がずれる）。このため、テストはリポジトリのルートから実行する
- 文書（SKILL.md・agent 定義）に書かれた script の呼び方を実際に実行して引数が合うかを確かめる検査と、文書の記述を製品コードの定数と突き合わせる検査（契約テスト）は、コードを実行するので `tests/` に置く
- 文書・設定・配布物の定義を、コードを実行せずに規則と照合する検査は、単体テストではない。`lint/` に置く

### 4.2 lint

```bash
# 全 lint 一括実行
python3 -m unittest discover -s lint -p 'lint_*.py' -v

# 特定の lint のみ
python3 -m unittest lint.lint_xxx -v
```

- ファイル名は `lint_{対象}.py`。実行器には `unittest` を使う（標準ライブラリだけで、違反の箇所を報告できる）
- 対象は種別（glob・文書の種別）で決める。新しく足す検査で、特定のファイルを名指ししない
- 違反を返す検査ロジックに分岐や解析があるときは、`lint_*.py` から分けて `lint/` のモジュールに置き、合成した入力での単体テストを `tests/lint_rules/` に置く
- リポジトリのルートは `from lint import REPO_ROOT` で得る。lint はリポジトリのルートから実行する
- 製品コードを実行して振る舞いを確かめる検査は、lint に置かない
- `lint/provisional/` は、名指しした文書に文字列があるか・無いかだけを見る暫定の検査である。記述の意味は検査しない。AI-Linter（4.3）か、種別を対象にした検査へ置き換えたら削除する。ここへ新しい検査を足さない

### 4.3 AI-Linter

```bash
# 全検査（対象の文書の本文を、判定 backend へ送る）
python3 -m ai_lint.run

# 指定した検査だけ
python3 -m ai_lint.run --check <id>

# 対象と問いを表示するだけで、送信しない
python3 -m ai_lint.run --dry-run
```

- ローカルで実行する。CI のゲートには含めない。対象の SKILL・agent 定義か、検査の宣言を変えたら実行する
- 判定 backend は差し替えられる（`ai_lint/backend.py` の窓口を実装する）。現在の実装は Jev（`ai_lint/backends/jev.py`）で、環境変数 `TYPESAFE_API_KEY` が要る。キーは script が読む。値を表示・記録しない
- 終了コードは、0 が全件合格、1 が違反または保留あり、2 が実行できなかった（キーが無い・通信の失敗・宣言の不備・対象が無い）。2 を合格として扱わない
- 検査は `ai_lint/checks/*.json` に宣言する。対象（glob）、問い、期待（`yes` / `no`）、根拠（どの要件・設計・ルールの記述か）を書く。検査のコードに問いを書かない
- 根拠には、要件定義書・設計書・ルール文書にある記述を書く。その対象に当たる記述が見つからないことは、検査しない（検査を足す前に、要件として書く）
- 問いは、文書を `` `document` `` で指し、1 問に 1 つの条件だけを問う。2 つの条件を 1 問に入れると、判定が保留になりやすい
- 確率が 0.7 以上を「成り立つ」、0.3 以下を「成り立たない」、その間を保留とする。保留は合格にしない
- 判定するのは文書全体の意味である。同じ禁止を複数の箇所で述べている文書から 1 箇所を消しても、意味が残っていれば合格する。特定の記述（ツール名の列挙など）が在ることを求めるなら、その事実を構造化して lint で見る
- 検査を足したら、対象の文書を一時的に書き換えて、意味を逆にすると違反になること・言い換えでは合格のままであることを確かめ、元に戻す
- AI の判断を試すテスト（4.4）との違い: AI-Linter は成果物（定義の文章）を規則と照合する。`ai_tests/` は、その定義で動いた AI の出力を確かめる

### 4.4 AI の判断を試すテスト

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

設定ファイル: `dprint.jsonc`

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
- [docs/rules/plugin_claude_code_authoring_guide.md][plugin-claude-code-authoring-guide] — SKILL.md / カスタム Agent の書き方の規約（汎用）
- [docs/rules/plugin_claude_code_reference.md][plugin-claude-code-reference] — Claude Code の SKILL・プラグイン・Agent の仕組みの事実（汎用）
- [docs/rules/forge_claude_code_authoring_policy.md][forge-claude-code-authoring-policy] — forge が決めた作成方針
- [docs/rules/plugin_implementation_guidelines.md][plugin-implementation-guidelines] — 実装ガイドライン（汎用）

[plugin-claude-code-authoring-guide]: docs/rules/plugin_claude_code_authoring_guide.md
[plugin-claude-code-reference]: docs/rules/plugin_claude_code_reference.md
[forge-claude-code-authoring-policy]: docs/rules/forge_claude_code_authoring_policy.md
[plugin-implementation-guidelines]: docs/rules/plugin_implementation_guidelines.md
