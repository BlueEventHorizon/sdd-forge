#!/usr/bin/env python3
"""lint: onboarding の転記元（`copy_block.md`）が、転記可能な状態であること。

配布物の実体を検査する。転記範囲の読み出しには、onboarding の script の関数を使う
（範囲の決め方を 2 か所に持たないため）。script の振る舞いの検査は
`tests/forge/onboarding/test_onboarding_block.py` にある。

実行:
  python3 -m unittest lint.lint_onboarding_copy_block -v
"""

import importlib.util
import unittest

from lint import REPO_ROOT

_SKILL_DIR = REPO_ROOT / "plugins" / "forge" / "skills" / "onboarding"
_SCRIPT_PATH = _SKILL_DIR / "scripts" / "onboarding_block.py"

_spec = importlib.util.spec_from_file_location("onboarding_block", _SCRIPT_PATH)
ob = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ob)


class TestRealCopyBlock(unittest.TestCase):
    """配布物の実体が転記可能な状態であることを検証する。"""

    def setUp(self):
        self.region = ob.read_region(ob.SOURCE.read_text(encoding="utf-8"))

    def test_source_file_is_the_dedicated_copy_block(self):
        self.assertEqual(ob.SOURCE.name, "copy_block.md")
        self.assertTrue(ob.SOURCE.is_file())

    def test_real_copy_region_is_not_empty(self):
        self.assertTrue(self.region.strip())

    def test_real_copy_region_headings_are_forge_prefixed(self):
        """転記先での見出し重複を防ぐ規約。script は接頭辞を付けないので、ここで強制する。"""
        h2 = [ln for ln in self.region.splitlines() if ln.startswith("## ")]
        self.assertTrue(h2, "転記範囲に ## 見出しが無い")
        for line in h2:
            self.assertTrue(
                line.startswith("## forge "),
                f"転記範囲の ## 見出しは 'forge ' で始めること: {line!r}",
            )

    def test_real_copy_region_has_no_destination_markers(self):
        """転記先マーカーが混入するとブロック検出が壊れる。"""
        self.assertNotIn("FORGE_ONBOARDING_START", self.region)
        self.assertNotIn(ob.MARKER_END, self.region)

    def test_skill_md_does_not_duplicate_the_copy_block(self):
        """SKILL.md は起動時に全文注入される。転記範囲を持たせると必ず二重読みになる。"""
        skill = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for line in self.region.splitlines():
            body = line.strip()
            if len(body) < 20:
                continue
            self.assertNotIn(
                body,
                skill,
                f"転記範囲の記述が SKILL.md に複製されている: {body[:40]!r}",
            )


if __name__ == "__main__":
    unittest.main()
