"""判定 backend の窓口。

AI-Linter の本体は、この窓口だけに依存する。backend を差し替えても、検査の宣言と判定の規則は
変わらない。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class BackendError(Exception):
    """backend を使えない、通信に失敗した、または応答が契約を満たさない。"""


@dataclass(frozen=True)
class Judgement:
    """1 文書に対する問いの結果。

    `probabilities` は、問いの識別子ごとの「成り立つ」確率（0〜1）である。
    """

    probabilities: dict[str, float]
    input_tokens: int
    model: str


class Backend(Protocol):
    name: str

    def judge(self, document: str, questions: dict[str, str]) -> Judgement:
        """`document` について、`questions`（識別子 → 問いの文）のそれぞれが成り立つ確率を返す。

        問いの文は、文書を `document` という名前で指す。送った識別子のすべてに答えを返せないときは
        `BackendError` を送出する（一部だけの結果を返さない）。
        """
        ...
