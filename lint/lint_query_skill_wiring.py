#!/usr/bin/env python3
"""lint: 検索系 dispatcher SKILL と worker Agent の対応。

dispatcher が起動する `subagent_type` と worker の frontmatter が対応し、worker の `tools` に
書き込み系・Agent・Bash が無いこと（read-only worker）を検査する。

対象:
- 継承型 dispatcher の SKILL: plugins/forge/skills/query-forge-rules/SKILL.md
- その dispatcher が Agent ツールで起動する read-only worker: plugins/forge/agents/rules-query-worker.md

注: forge の query-db-rules / query-db-specs は文書検索 backend へ転送する薄いラッパー
（fork を持たない）であり、隔離契約は転送先の backend が担保するため対象外。

実行:
  python3 -m unittest lint.lint_query_skill_wiring -v
"""

import re
import unittest
from pathlib import Path

from lint import REPO_ROOT

# dispatcher SKILL と worker Agent の対応。dispatcher が起動する subagent_type と
# worker の frontmatter name が一致していることを検証する
DISPATCHER_WORKER_PAIRS = [
    (
        REPO_ROOT / "plugins" / "forge" / "skills" / "query-forge-rules" / "SKILL.md",
        REPO_ROOT / "plugins" / "forge" / "agents" / "rules-query-worker.md",
        "forge:rules-query-worker",
    ),
]


def split_frontmatter_body(skill_path: Path):
    """SKILL.md を frontmatter 文字列と本文に分割する。"""
    text = skill_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise AssertionError(f"{skill_path} に YAML frontmatter がない")
    end = text.find("\n---", 3)
    if end == -1:
        raise AssertionError(f"{skill_path} の frontmatter が閉じていない")
    fm = text[3:end]
    body = text[end + 4 :]
    return fm, body


class TestDispatcherWorkerWiring(unittest.TestCase):
    """dispatcher SKILL が起動する worker と、worker Agent の定義が対応していることを検証

    dispatcher 側は ToC を自分で読まず Agent へ委譲する構成なので、
    - dispatcher の frontmatter `allowed-tools` に `Agent` がある
    - dispatcher 本文が worker の subagent_type を名指ししている
    - worker の frontmatter `name` が subagent_type の `<plugin>:` 以降と一致する
    - worker の `tools` に書き込み系・Agent が含まれない（read-only worker）
    """

    def test_dispatcher_launches_declared_worker(self):
        for skill_path, agent_path, subagent_type in DISPATCHER_WORKER_PAIRS:
            with self.subTest(skill=str(skill_path.relative_to(REPO_ROOT))):
                fm, body = split_frontmatter_body(skill_path)
                self.assertRegex(
                    fm,
                    r"(?m)^allowed-tools:.*\bAgent\b",
                    f"{skill_path.relative_to(REPO_ROOT)} の allowed-tools に Agent がない",
                )
                self.assertIn(
                    subagent_type,
                    body,
                    f"{skill_path.relative_to(REPO_ROOT)} が worker `{subagent_type}` を名指ししていない",
                )
                self.assertTrue(
                    agent_path.is_file(),
                    f"worker 定義 {agent_path.relative_to(REPO_ROOT)} が存在しない",
                )
                agent_fm, _ = split_frontmatter_body(agent_path)
                name_match = re.search(r"(?m)^name:\s*(\S+)\s*$", agent_fm)
                self.assertIsNotNone(
                    name_match, f"{agent_path.relative_to(REPO_ROOT)} に name がない"
                )
                self.assertEqual(
                    name_match.group(1),
                    subagent_type.split(":", 1)[1],
                    f"{agent_path.relative_to(REPO_ROOT)} の name が subagent_type と一致しない",
                )
                tools_match = re.search(r"(?m)^tools:\s*(.+?)\s*$", agent_fm)
                self.assertIsNotNone(
                    tools_match, f"{agent_path.relative_to(REPO_ROOT)} に tools がない"
                )
                tools = {t.strip() for t in tools_match.group(1).strip("[]").split(",")}
                self.assertTrue(
                    {
                        "Edit",
                        "Write",
                        "MultiEdit",
                        "NotebookEdit",
                        "Agent",
                        "Bash",
                    }.isdisjoint(tools),
                    f"{agent_path.relative_to(REPO_ROOT)} の tools に read-only worker に不要なツールがある: {sorted(tools)}",
                )


if __name__ == "__main__":
    unittest.main()
