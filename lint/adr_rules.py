"""ADR の参照と書式の検査ロジック。

ADR ファイルを受け取り、違反の一覧を返す関数だけを持つ。どの ADR を検査するかは
呼び出し側（`lint_adr.py`）が決める。合成した ADR での単体テストは
`tests/lint_rules/test_adr_rules.py` にある。
"""

from __future__ import annotations

import re
from pathlib import Path

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+\.md)(?:#[^)]*)?\)")
#: リファレンスリンク（`[表示名][ラベル]`）と、その定義（`[ラベル]: パス "title"`）。
REF_LINK_RE = re.compile(r"\[[^\]]*\]\[([^\]]+)\]")
REF_DEF_RE = re.compile(
    r'^\[([^\]]+)\]:\s*<?([^\s#>]+\.md)(?:#[^\s>]*)?>?(?:\s+"[^"]*")?\s*$'
)
#: リンク直後に続く `§X.Y`（`§5.2 / §5.6` のように複数続くことがある）。
TRAILING_SECTION_RE = re.compile(r"\A(?:\s*§\d+(?:\.\d+)*(?:\s*/)?)+")
SECTION_RE = re.compile(r"§(\d+(?:\.\d+)*)")
ADR_SECTION_REF_RE = re.compile(r"ADR-(\d{3})\s*§(\d+(?:\.\d+)*)")
HEADING_NUM_RE = re.compile(r"^#{2,6}\s+(\d+(?:\.\d+)*)\.?\s")
INVALIDATION_RE = re.compile(r"⚠️失効")
# 見出しの行末に機械的に付与される文書検索用の識別子。見出しの名前には含めない
# （document_style_guide.md §1.1）。
HEADING_ID_RE = re.compile(r"\s+DLID-[0-9a-z]+\s*$")

#: 決定の節が持つ 4 つの小節（番号の下 1 桁と名前）。
DECISION_SUBSECTIONS = (
    (1, "コンテキスト"),
    (2, "決定"),
    (3, "検討した代替案"),
    (4, "影響"),
)


def strip_code(text: str) -> str:
    """フェンス済みコードブロックとインラインコードを空行・空文字へ潰す。

    記法の説明でリンク構文そのものを例示することがあり（`[foo_format.md](foo_format.md)`
    のような例）、これを実リンクとして扱うと存在しないファイルを指しているように
    見える。行番号を保つため、フェンス内は行ごと空行に置き換える。
    """
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)


def markdown_links(path: Path) -> list[tuple[int, str, int, str]]:
    """文書が Markdown 文書へ張るリンクを `(行番号, 行, リンクの終わりの位置, リンク先)` で返す。

    インラインリンクと、リファレンスリンク（本文の `[表示名][ラベル]` を定義で解決したもの）の
    両方を返す。定義だけがあって本文から使われていないものは返さない。
    """
    lines = strip_code(path.read_text(encoding="utf-8")).splitlines()
    definitions: dict[str, str] = {}
    for line in lines:
        d = REF_DEF_RE.match(line)
        if d:
            definitions[d.group(1).lower()] = d.group(2)
    found: list[tuple[int, str, int, str]] = []
    for lineno, line in enumerate(lines, 1):
        for m in MD_LINK_RE.finditer(line):
            found.append((lineno, line, m.end(), m.group(1)))
        for m in REF_LINK_RE.finditer(line):
            target = definitions.get(m.group(1).lower())
            if target is not None:
                found.append((lineno, line, m.end(), target))
    return found


#: 定義行のラベル（リンク先の種類を問わない。外部 URL の定義も含む）。
ANY_DEF_RE = re.compile(r"^\[([^\]]+)\]:\s*\S")


def undefined_reference_labels(path: Path) -> list[tuple[int, str]]:
    """本文のリファレンスリンク `[表示名][ラベル]` のうち、定義の無いものを `(行番号, ラベル)` で返す。

    定義の無い参照は、リンクにならずそのままの文字で表示される。`markdown_links` は定義で
    解決できた参照だけを返すので、ここで拾わないと、宛先を失った参照ほど検査を通ってしまう。
    """
    lines = strip_code(path.read_text(encoding="utf-8")).splitlines()
    defined = {
        m.group(1).lower() for m in (ANY_DEF_RE.match(line) for line in lines) if m
    }
    return [
        (lineno, m.group(1))
        for lineno, line in enumerate(lines, 1)
        if not ANY_DEF_RE.match(line)
        for m in REF_LINK_RE.finditer(line)
        if m.group(1).lower() not in defined
    ]


def heading_numbers(path: Path) -> set[str]:
    """文書内の見出しが持つ節番号の集合（`## 1. 概要` → `1`、`### 2.4 …` → `2.4`）。"""
    numbers: set[str] = set()
    for line in strip_code(path.read_text(encoding="utf-8")).splitlines():
        m = HEADING_NUM_RE.match(line)
        if m:
            numbers.add(m.group(1))
    return numbers


def structure_violations(path: Path) -> list[str]:
    """ADR ファイルの構成が adr_format.md「ファイルの構成」に反する箇所を返す。

    - `#` 見出しはファイルのタイトル 1 つだけ
    - `##` は `## N. ` の形で、N は昇順（決定を足すときは末尾に追加する）
    - `###` は、直近の `## N.` の下の `### N.1`〜`### N.4` の形
    - 各決定の節は、4 つの小節を番号順に過不足なく持つ
    - 旧書式の節（メタデータ・ステータス履歴）を持たない
    """
    violations: list[str] = []
    current: int | None = None
    previous: int = 0
    seen: list[tuple[int, str]] = []
    titles = 0

    def close_section(lineno: int) -> None:
        if current is not None and seen != [
            (num, name) for num, name in DECISION_SUBSECTIONS
        ]:
            violations.append(
                f"{path.name}: `## {current}.` の小節が 4 つの定義と一致しない: {seen}"
            )

    for lineno, line in enumerate(
        strip_code(path.read_text(encoding="utf-8")).splitlines(), 1
    ):
        rel = f"{path.name}:{lineno}"
        if line.startswith("# "):
            titles += 1
            continue
        if line.startswith("## メタデータ") or line.startswith("## ステータス履歴"):
            violations.append(f"{rel} 旧書式の節: {line}")
            continue
        if line.startswith("## "):
            close_section(lineno)
            m = re.match(r"^## (\d+)\. ", line)
            if not m:
                violations.append(
                    f"{rel} 決定の節の見出しが `## N. ` の形ではない: {line}"
                )
                current = None
                seen = []
                continue
            number = int(m.group(1))
            if number <= previous:
                violations.append(f"{rel} 節番号が昇順ではない: {line}")
            previous = number
            current = number
            seen = []
            continue
        if line.startswith("### "):
            m = re.match(r"^### (\d+)\.(\d+) (.+)$", line)
            if current is None or not m or int(m.group(1)) != current:
                violations.append(
                    f"{rel} 小節が直近の `## N.` の `### N.M ` の形ではない: {line}"
                )
                continue
            seen.append((int(m.group(2)), HEADING_ID_RE.sub("", m.group(3)).strip()))
    close_section(0)

    if titles != 1:
        violations.append(
            f"{path.name}: `#` 見出し（ファイルのタイトル）が 1 つではない: {titles}"
        )
    return violations


def invalidation_marker_violations(path: Path) -> list[str]:
    """ADR は失効マーカーを持たない。ADR に `⚠️失効` が現れたら違反とする。"""
    return [
        f"{path.name}:{lineno} {line}"
        for lineno, line in enumerate(
            strip_code(path.read_text(encoding="utf-8")).splitlines(), 1
        )
        if INVALIDATION_RE.search(line)
    ]


def adr_dirs_with_multiple_files(specs_dir: Path) -> list[str]:
    """同じ feature の ADR は 1 つのファイルに書く。`adr/` に ADR ファイルが複数あれば返す。"""
    found: list[str] = []
    for adr_dir in sorted(p for p in specs_dir.rglob("adr") if p.is_dir()):
        files = sorted(adr_dir.glob("ADR-*.md"))
        if len(files) > 1:
            found.append(f"{adr_dir}: {', '.join(f.name for f in files)}")
    return found
