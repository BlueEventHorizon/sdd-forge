#!/usr/bin/env python3
"""lint: sync_files のバージョンドリフト。

`.version-config.yaml` の sync_files に列挙された各ファイルが、
version_file の現行バージョンと同期しているかを検査する。

- filter パターン自体がファイルに存在しない場合、`optional: true` エントリのみ
  対象外として許容する。`optional` でないエントリの filter 消失（設定の filter が
  ファイル内容の変化で一致しなくなった等）は、それ自体が見逃してはいけない不整合
  として fail する（optional の有無を問わず一律 continue すると、
  必須エントリの filter 消失を見逃す）
- filter パターンは存在するのに現行バージョンが見当たらない場合（ドリフト）は fail する
- filter 無し（version_path 使用）の sync_file でも同様にドリフトを検出する
  （本リポジトリの現行 config には filter 無し sync_file が存在しない。この経路は
  `update_version_in_text` の単体テストが合成データで担保する）

これにより README_en.md のようなファイルが optional スキップで
サイレントに古いバージョン表記のまま放置される事態を CI で検出する。

実行:
    python3 -m unittest lint.lint_version_sync_drift -v
"""

import sys
import unittest

from lint import REPO_ROOT
from lint.version_sync import is_optional_flag

UPDATE_VERSION_SCRIPTS = (
    REPO_ROOT / "plugins" / "forge" / "skills" / "update-version" / "scripts"
)
FORGE_SCRIPTS = REPO_ROOT / "plugins" / "forge" / "scripts"
sys.path.insert(0, str(UPDATE_VERSION_SCRIPTS))
sys.path.insert(0, str(FORGE_SCRIPTS))

from update_version_files import (  # noqa: E402
    FilterNotFoundError,
    VersionDriftError,
    update_version_in_text,
)
from get_version_status import (  # noqa: E402
    extract_version_from_content,
    load_version_config,
)


class TestSyncFilesNoDrift(unittest.TestCase):
    """sync_files の各ファイルにバージョンドリフトがないことを検証する。"""

    @classmethod
    def setUpClass(cls):
        cls.config = load_version_config(REPO_ROOT)

    def test_no_drift_in_sync_files(self):
        drifted = []

        for target in self.config.get("targets", []):
            version_file = target.get("version_file", "")
            version_path = (
                (target.get("version_path", "version") or "version")
                .strip()
                .strip("'\"")
            )
            local_path = REPO_ROOT / version_file
            if not local_path.exists():
                continue

            current_ver = extract_version_from_content(
                local_path.read_text(encoding="utf-8"), version_path
            )
            if current_ver is None:
                continue

            for sync in target.get("sync_files", []):
                sync_path = REPO_ROOT / sync["path"]
                if not sync_path.exists():
                    continue

                content = sync_path.read_text(encoding="utf-8")
                filter_pattern = sync.get("filter")
                is_optional = is_optional_flag(sync)
                try:
                    # 現行バージョンで noop 置換を試み、filter ブロック内に
                    # 現行バージョンが実在するかを確認する
                    update_version_in_text(
                        content,
                        current_ver,
                        current_ver,
                        filter_pattern=filter_pattern,
                    )
                except VersionDriftError as e:
                    drifted.append(
                        f"{sync['path']} (target={target['name']}, "
                        f"expected={current_ver}): {e}"
                    )
                except FilterNotFoundError as e:
                    if is_optional:
                        # optional かつ filter パターン自体が無い（対象外）は許容
                        continue
                    # optional でないエントリの filter 消失は、
                    # そのエントリが今後一切更新されなくなる不整合であり見逃せない
                    drifted.append(
                        f"{sync['path']} (target={target['name']}): "
                        f"必須エントリの filter が見つかりません（設定 or ファイル内容の不整合）: {e}"
                    )

        self.assertEqual(
            drifted,
            [],
            "以下の sync_files でバージョンドリフトを検出しました:\n"
            + "\n".join(drifted),
        )


if __name__ == "__main__":
    unittest.main()
