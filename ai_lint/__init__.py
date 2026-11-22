"""AI-Linter: 文章の意味を、判定モデルに問うて規則と照合する検査。

script だけで判定できる検査は `lint/` にある。ここには、文章を読まないと判定できない検査を置く。
実行はローカルで行う（`python3 -m ai_lint.run`）。CI の discover には含めない。
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
