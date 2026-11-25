"""lint: 単体テストと lint が CI の discover に確実に拾われること。

CI は `python3 -m unittest discover -s tests -p 'test_*.py'` と
`python3 -m unittest discover -s lint -p 'lint_*.py'` を実行する。discover は
パッケージを辿って走査するため、`__init__.py` を欠くディレクトリは**エラーにならず黙って
飛ばされる**。ファイルは存在し、直接指定すれば通り、`git status` にも異常が出ないため、
「検査済み」に見えたまま 1 行も実行されない状態が成立する。

件数の増減では気づけない（元から数えられていない）ため、構造として検査する。

実行:
  python3 -m unittest lint.lint_test_discovery -v
"""

import unittest
from pathlib import Path

from lint import REPO_ROOT

#: discover の起点と、そこで拾うファイル名のパターン（CI のコマンドと対応する）。
DISCOVER_ROOTS = (
    (REPO_ROOT / "tests", "test_*.py"),
    (REPO_ROOT / "lint", "lint_*.py"),
)


def _dirs_containing(root: Path, pattern: str) -> set[Path]:
    """パターンに合うファイルを含むディレクトリと、起点までのその全祖先を返す。"""
    dirs: set[Path] = set()
    for found in root.rglob(pattern):
        current = found.parent
        while True:
            dirs.add(current)
            if current == root:
                break
            current = current.parent
    return dirs


class TestDiscoveryTest(unittest.TestCase):
    def test_every_directory_is_a_package(self):
        """対象のファイルを含むディレクトリとその祖先すべてに `__init__.py` があること。

        祖先まで検査するのは、末端にだけ置いても親が欠けていれば discover が
        そこで止まるためである。
        """
        for root, pattern in DISCOVER_ROOTS:
            with self.subTest(root=root.name):
                missing = sorted(
                    str(d.relative_to(REPO_ROOT))
                    for d in _dirs_containing(root, pattern)
                    if not (d / "__init__.py").is_file()
                )
                self.assertEqual(
                    missing,
                    [],
                    f"__init__.py が無いため discover に拾われないディレクトリ: {missing}",
                )


if __name__ == "__main__":
    unittest.main()
