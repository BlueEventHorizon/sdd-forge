import os
import tempfile
from pathlib import Path

# sandbox 環境は TMPDIR をプロジェクトルート内に書き換えることも、
# /tmp 直下への書き込みを禁止することもある。
# プロジェクト外かつ実際に書き込めるディレクトリを選んで固定する。
#
# REPO_ROOT は、各テストがリポジトリのルートを得る唯一の定義である。
# テストは `from tests import REPO_ROOT` で参照し、`parents[N]` で自力では求めない。
REPO_ROOT = Path(__file__).resolve().parent.parent


def _writable_tmpdir():
    for cand in (os.environ.get("TMPDIR"), "/tmp"):
        if not cand:
            continue
        path = Path(cand).resolve()
        if path == REPO_ROOT or REPO_ROOT in path.parents:
            continue  # プロジェクト内に一時ファイルを作らない
        try:
            probe = tempfile.mkdtemp(dir=str(path))
        except OSError:
            continue
        os.rmdir(probe)
        return str(path)
    return None


_tmpdir = _writable_tmpdir()
if _tmpdir is not None:
    tempfile.tempdir = _tmpdir
