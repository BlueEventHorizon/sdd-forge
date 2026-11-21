from pathlib import Path

#: リポジトリのルート。lint は `from lint import REPO_ROOT` で参照する。
REPO_ROOT = Path(__file__).resolve().parent.parent
