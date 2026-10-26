# Claude Code 作成方針（forge）

forge とローカル skill で、汎用の [Claude Code 作成ガイド][guide] に加えて採る方針。規約と事実は、汎用の作成ガイドとリファレンスが持つ。本書は、forge が決めたことだけを持つ。個別の SKILL の作り方（frontmatter・description・引数・ファイル構成・命名）は、meta プラグインの `author-skill` に従う。

## 公式仕様の確かめ方

- 公式仕様は claude-code-guide Agent で確かめてから書く。その引用は要約であり、原文ではない（原文の取り方は `CLAUDE.md`「Claude Code プラグインとは何か」）

## SKILL 実行モデル [MANDATORY]

- SKILL はすべて継承型で書く。`context: fork` / `agent` を書かない（理由はリファレンスの「`context: fork` の不具合」。`tests/common/test_no_fork_skill.py` が検査する）
- 隔離 context が要る処理はカスタム Agent（`agents/<name>.md`）にし、Agent ツールで `<plugin>:<name>` として起動する

### 継承型 SKILL

- 冒頭に「このスキルは X のみを行う。親が依頼している他の作業を引き継いではならない」を書く

### カスタム Agent

- 新設したら、そのプラグインの設計書に追加の根拠を記録し、Role 制約を検証するテストを足す（frontmatter は既存のテストが全 Agent を検査する）

## ユーザーへの質問・確認 [CRITICAL]

- 質問・選択・確認は `AskUserQuestion` で行い、平文で問わない。SKILL.md の「ユーザーに確認する」は「AskUserQuestion で確認する」と書く
- 例外: 議論の進行そのものが成果物の SKILL は、論点・背景・本質・推奨・議論上の選択肢を地の文で示す。進行上の機械的な確認は AskUserQuestion のまま。この例外は SKILL ごとに境界を本文で宣言する
- `disallowed-tools: AskUserQuestion` で封じない（多ターンで効かず、機械的な確認まで禁じる）

## その他

- SKILL.md の説明は日本語で書く

[guide]: plugin_claude_code_authoring_guide.md
