#!/usr/bin/env python3
"""forge 実装計画書 `{feature}_plan.json` の JSON 正本契約を静的検査する回帰テスト。

実行:
  python3 -m unittest tests.forge.plan_json_contract.test_plan_json_contract -v

検査対象:
  1. ユーザー向けガイド・SKILL の JSON 例が DES-074（計画書フォーマット設計書）の必須フィールドを欠かない
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


PLAN_FORMAT = (
    REPO_ROOT / "docs" / "specs" / "forge" / "design" / "DES-074_plan_format_design.md"
)

GUIDE_JSON_EXAMPLE_FILES = [
    REPO_ROOT / "docs" / "readme" / "forge" / "guide_create_docs_ja.md",
    REPO_ROOT / "docs" / "readme" / "forge" / "guide_create_docs.md",
]

REQUIRED_TASK_FIELDS = [
    "task_id",
    "title",
    "priority",
    "status",
    "design_id",
    "depends_on",
    "group_id",
    "build_check",
    "description",
    "acceptance_criteria",
    "required_reading",
]

REQUIRED_TOP_LEVEL_KEYS = [
    "requirements_traceability",
    "design_traceability",
    "tasks",
]


def _extract_json_blocks(text: str) -> list[str]:
    return re.findall(r"```json\n(.*?)```", text, flags=re.DOTALL)


class TestGuideJsonExamplesHaveRequiredFields(unittest.TestCase):
    """ユーザー向けガイドの計画書 JSON 例が必須フィールドを欠かないことを検査"""

    def test_guides_have_complete_plan_json_example(self):
        for path in GUIDE_JSON_EXAMPLE_FILES:
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                self.assertTrue(path.exists(), f"missing: {path}")
                text = path.read_text(encoding="utf-8")
                blocks = _extract_json_blocks(text)
                self.assertTrue(
                    blocks,
                    "ガイドに JSON コードブロックが 1 つも無い: " + str(path),
                )

                plan_block = self._find_plan_block(blocks)
                self.assertIsNotNone(
                    plan_block,
                    "計画書 JSON 例 (tasks/requirements_traceability を含むブロック) が見当たらない: "
                    + str(path),
                )

                for key in REQUIRED_TOP_LEVEL_KEYS:
                    with self.subTest(top_level=key):
                        self.assertIn(
                            key,
                            plan_block,
                            f"ガイドの計画書 JSON 例に top-level キー '{key}' が含まれていない: {path}",
                        )

                for field in REQUIRED_TASK_FIELDS:
                    with self.subTest(field=field):
                        self.assertIn(
                            field,
                            plan_block,
                            f"ガイドの計画書 JSON 例に tasks[] 必須フィールド '{field}' が含まれていない: {path}",
                        )

    @staticmethod
    def _find_plan_block(blocks: list[str]) -> str | None:
        for block in blocks:
            if '"tasks"' in block and '"requirements_traceability"' in block:
                return block
        return None


class TestPlanFormatIsCanonical(unittest.TestCase):
    """DES-074（計画書フォーマット設計書）が必須フィールドを全て定義していること（正本性の自己検査）"""

    def test_plan_format_lists_all_required_fields(self):
        text = PLAN_FORMAT.read_text(encoding="utf-8")
        for key in REQUIRED_TOP_LEVEL_KEYS:
            self.assertIn(key, text, f"DES-074 に top-level キー '{key}' が無い")
        for field in REQUIRED_TASK_FIELDS:
            self.assertIn(
                field, text, f"DES-074 に tasks[] フィールド '{field}' が無い"
            )


if __name__ == "__main__":
    unittest.main()
