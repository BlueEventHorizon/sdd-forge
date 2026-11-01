#!/usr/bin/env python3
"""next-spec-id の窓口が SKILL だけであることの契約テスト。

他コンポーネントは、採番を `Skill` ツールで `next-spec-id` を呼んで行う。採番スクリプト
`scan_spec_ids.py` は next-spec-id の内部であり、他スキル・内蔵文書・agent 定義が
直接呼んだり、CLI の形を書いたりしてはならない。

実行:
  python3 -m unittest tests.forge.scripts.test_next_spec_id_window -v
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN = REPO_ROOT / "plugins" / "forge"
OWNER = PLUGIN / "skills" / "next-spec-id"


class NextSpecIdWindowTest(unittest.TestCase):
    def test_no_other_markdown_names_the_script(self):
        offenders = []
        for path in sorted(PLUGIN.rglob("*.md")):
            if OWNER in path.parents:
                continue
            if "scan_spec_ids" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(
            offenders,
            [],
            "next-spec-id の採番スクリプトを直接指している文書がある。"
            "Skill ツールで next-spec-id を呼ぶ形に直すこと",
        )

    def test_owner_skill_states_the_invocation_contract(self):
        text = (OWNER / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`Skill` ツールで呼ぶ", text)
        self.assertIn("argument-hint:", text)


if __name__ == "__main__":
    unittest.main()
