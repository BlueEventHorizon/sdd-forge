#!/usr/bin/env python3
"""docs/rules/ の接頭辞による分類と、汎用規範（`plugin_`）の独立性を検査する。

`plugin_` を付けた文書は、他のプラグイン開発プロジェクトへそのままコピーして使う。
`forge_` を付けた文書は、forge 固有の規範で、コピーの対象にしない。

- docs/rules/ の文書は、`plugin_` か `forge_` で始まる（接頭辞で汎用と forge 固有を分ける）
- `plugin_` の文書は、forge の名前を含まない
- `plugin_` の文書の Markdown リンク（`[表示名](パス)` と `[ラベル]: パス`）の宛先は、
  実在する `plugin_` の文書だけである（コピー先で壊れないための条件）

実行:
    python3 -m unittest tests.common.test_plugin_docs_independence -v
"""

import re
import unittest
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parents[2] / "docs" / "rules"
PREFIXES = ("plugin_", "forge_")

INLINE_LINK = re.compile(r"\]\(([^)\s]+)\)")
REFERENCE_LINK = re.compile(r"^\[[^\]]+\]:\s*(\S+)", re.MULTILINE)
FORGE_NAME = re.compile(r"forge", re.IGNORECASE)


def plugin_docs():
    return sorted(RULES_DIR.glob("plugin_*.md"))


def link_targets(text):
    targets = INLINE_LINK.findall(text) + REFERENCE_LINK.findall(text)
    for target in targets:
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        yield target.split("#", 1)[0]


class TestRulesPrefix(unittest.TestCase):
    def test_every_rule_doc_has_a_prefix(self):
        unprefixed = [
            path.name
            for path in sorted(RULES_DIR.glob("*.md"))
            if not path.name.startswith(PREFIXES)
        ]
        self.assertEqual(
            unprefixed,
            [],
            "docs/rules/ の文書は plugin_（汎用）か forge_（forge 固有）で始める: "
            + ", ".join(unprefixed),
        )

    def test_plugin_docs_exist(self):
        self.assertTrue(
            plugin_docs(), "plugin_ の文書が 1 件も無い（改名の誤りの疑い）"
        )


class TestPluginDocsIndependence(unittest.TestCase):
    def test_no_forge_name(self):
        found = []
        for path in plugin_docs():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if FORGE_NAME.search(line):
                    found.append(f"{path.name}:{number}: {line.strip()}")
        self.assertEqual(
            found, [], "plugin_ の文書に forge の名前がある:\n" + "\n".join(found)
        )

    def test_links_point_only_to_existing_plugin_docs(self):
        broken = []
        for path in plugin_docs():
            for target in link_targets(path.read_text(encoding="utf-8")):
                resolved = (path.parent / target).resolve()
                if not resolved.name.startswith("plugin_") or not resolved.is_file():
                    broken.append(f"{path.name}: {target}")
        self.assertEqual(
            broken,
            [],
            "plugin_ の文書のリンクの宛先は、実在する plugin_ の文書だけにする:\n"
            + "\n".join(broken),
        )


if __name__ == "__main__":
    unittest.main()
