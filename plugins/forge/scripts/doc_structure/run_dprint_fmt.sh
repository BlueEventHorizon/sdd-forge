#!/usr/bin/env bash
# ToC 生成前に dprint fmt を実行する共有スクリプト。
# dprint.jsonc/dprint.json が存在し dprint コマンドが利用可能な場合のみ実行する
# (外部の anvil プラグインの anvil:commit Phase 0 と同一条件・同一コマンド)。
#
# ${CLAUDE_PLUGIN_ROOT} はプラグインごとに解決されるためプラグイン間でスクリプトを
# 共有できず、forge は自身の複製を保持する。

set -euo pipefail

if [ -f dprint.jsonc ] || [ -f dprint.json ]; then
  if command -v dprint >/dev/null 2>&1; then
    dprint fmt
  else
    echo "warning: dprint 設定ファイルがあるが dprint コマンドが見つかりません。format スキップ" >&2
  fi
fi
