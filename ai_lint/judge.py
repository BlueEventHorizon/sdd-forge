"""検査の宣言の読み込みと、判定の規則。

宣言（`ai_lint/checks/*.json`）は、対象の文書・問い・期待・根拠を持つ。問いの文は、文書を
`document` という名前で指し、1 問に 1 つの条件だけを問う。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ai_lint.backend import Backend, BackendError

#: 確率がこの値以上なら「成り立つ」、`NO_THRESHOLD` 以下なら「成り立たない」、その間は保留。
YES_THRESHOLD = 0.7
NO_THRESHOLD = 0.3

PASS = "pass"
VIOLATION = "violation"
UNCERTAIN = "uncertain"


class CheckError(Exception):
    """検査の宣言に不備がある、または対象の文書が見つからない。"""


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    expect: bool
    basis: str


@dataclass(frozen=True)
class Check:
    id: str
    targets: tuple[str, ...]
    questions: tuple[Question, ...]


@dataclass(frozen=True)
class Result:
    check_id: str
    path: str
    question: Question
    probability: float
    outcome: str


@dataclass(frozen=True)
class Usage:
    requests: int
    input_tokens: int
    models: tuple[str, ...]


def _require_text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CheckError(f"{where} が空でない文字列ではありません")
    return value


def parse_check(data: object, source: str) -> Check:
    if not isinstance(data, dict):
        raise CheckError(f"{source}: ルートが object ではありません")
    check_id = _require_text(data.get("id"), f"{source}: id")
    targets = data.get("targets")
    if not isinstance(targets, list) or not targets:
        raise CheckError(f"{source}: targets が空でない配列ではありません")
    for index, target in enumerate(targets):
        _require_text(target, f"{source}: targets[{index}]")
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise CheckError(f"{source}: questions が空でない配列ではありません")
    questions: list[Question] = []
    for index, raw in enumerate(raw_questions):
        where = f"{source}: questions[{index}]"
        if not isinstance(raw, dict):
            raise CheckError(f"{where} が object ではありません")
        expect = raw.get("expect")
        if expect not in ("yes", "no"):
            raise CheckError(f"{where}.expect が yes / no ではありません")
        text = _require_text(raw.get("question"), f"{where}.question")
        if "`document`" not in text:
            raise CheckError(f"{where}.question が文書を `document` で指していません")
        questions.append(
            Question(
                id=_require_text(raw.get("id"), f"{where}.id"),
                text=text,
                expect=expect == "yes",
                basis=_require_text(raw.get("basis"), f"{where}.basis"),
            )
        )
    ids = [question.id for question in questions]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    if duplicated:
        raise CheckError(f"{source}: 問いの id が重複しています: {duplicated}")
    return Check(id=check_id, targets=tuple(targets), questions=tuple(questions))


def load_checks(checks_dir: Path) -> list[Check]:
    files = sorted(checks_dir.glob("*.json"))
    if not files:
        raise CheckError(f"検査の宣言が 1 件もありません: {checks_dir}")
    checks: list[Check] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CheckError(f"{path.name}: JSON として読めません（{exc}）") from exc
        checks.append(parse_check(data, path.name))
    ids = [check.id for check in checks]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    if duplicated:
        raise CheckError(f"検査の id が重複しています: {duplicated}")
    return checks


def resolve_targets(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    """glob を文書のパスへ解決する。1 件も合わない glob は、不備として報告する。"""
    resolved: list[Path] = []
    for pattern in patterns:
        matches = sorted(path for path in root.glob(pattern) if path.is_file())
        if not matches:
            raise CheckError(f"対象が 1 件も見つかりません: {pattern}")
        resolved.extend(path for path in matches if path not in resolved)
    return resolved


def strip_frontmatter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)


def grade(expect: bool, probability: float) -> str:
    if NO_THRESHOLD < probability < YES_THRESHOLD:
        return UNCERTAIN
    return PASS if (probability >= YES_THRESHOLD) == expect else VIOLATION


def run_checks(
    checks: list[Check], backend: Backend, root: Path
) -> tuple[list[Result], Usage]:
    """対象の文書ごとに 1 回 backend を呼び、問いごとの結果を返す。"""
    results: list[Result] = []
    requests = 0
    input_tokens = 0
    models: list[str] = []
    for check in checks:
        questions = {question.id: question.text for question in check.questions}
        for path in resolve_targets(root, check.targets):
            document = strip_frontmatter(path.read_text(encoding="utf-8"))
            judgement = backend.judge(document, questions)
            missing = sorted(set(questions) - set(judgement.probabilities))
            if missing:
                raise BackendError(
                    f"backend が答えを返さなかった問いがあります: {missing}"
                )
            requests += 1
            input_tokens += judgement.input_tokens
            if judgement.model not in models:
                models.append(judgement.model)
            for question in check.questions:
                probability = judgement.probabilities[question.id]
                results.append(
                    Result(
                        check_id=check.id,
                        path=path.relative_to(root).as_posix(),
                        question=question,
                        probability=probability,
                        outcome=grade(question.expect, probability),
                    )
                )
    return results, Usage(requests, input_tokens, tuple(models))
