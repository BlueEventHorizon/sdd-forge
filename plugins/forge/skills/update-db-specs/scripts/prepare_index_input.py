#!/usr/bin/env python3
"""update-db-specs の doc-link 索引入力準備を行う薄いラッパー。

低レベル CLI prepare_index_input.py を category=specs 固定で subprocess
呼び出しし、stdout・stderr・exit code をそのまま透過する。

引数: なし（category はラッパー内にハードコード）
"""

import subprocess
import sys
from pathlib import Path

LOW_LEVEL = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "doc_backend"
    / "prepare_index_input.py"
)
CATEGORY = "specs"


def main() -> int:
    if len(sys.argv) != 1:
        print("usage: prepare_index_input.py", file=sys.stderr)
        return 20
    result = subprocess.run(
        [sys.executable, str(LOW_LEVEL), CATEGORY],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
