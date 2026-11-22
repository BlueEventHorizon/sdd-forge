"""TypeSafe の Jev（System One）による判定 backend。

1 文書を state に 1 回だけ載せ、その文書への問いを Noul（条件が成り立つ確率）としてまとめて送る。
入力トークン課金のため、問いごとにリクエストを分けない。

API キーは環境変数から読み、出力・例外の文面に含めない。応答の本文も文面に含めない
（送った文書が含まれうるため）。通信の失敗と契約外の応答は `BackendError` として送出し、
成功や空の結果へ変換しない。
"""

from __future__ import annotations

import http.client
import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

from ai_lint.backend import BackendError, Judgement

API_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
#: 判定を再現できるよう、版を固定する。上げるときは、既存の検査の結果が変わらないことを確かめる。
MODEL = "jev-1.14.0"
API_KEY_ENV = "TYPESAFE_API_KEY"
TIMEOUT_SECONDS = 60.0

Transport = Callable[[urllib.request.Request, float], bytes]


def build_payload(document: str, questions: dict[str, str]) -> dict[str, Any]:
    return {
        "model": MODEL,
        "state": {"document": document},
        "questions": {
            question_id: {"type": "noul", "instructions": text}
            for question_id, text in questions.items()
        },
    }


def parse_response(response: Any, question_ids: list[str]) -> Judgement:
    """送った問いのすべてに、過不足なく契約どおりの答えがあることを検証する。"""
    if not isinstance(response, dict):
        raise BackendError("Jev の応答のルートが object ではありません")
    model = response.get("model")
    answers = response.get("answers")
    usage = response.get("usage")
    if not isinstance(model, str) or not model:
        raise BackendError("Jev の応答に model がありません")
    if not isinstance(answers, dict):
        raise BackendError("Jev の応答の answers が object ではありません")
    missing = sorted(set(question_ids) - set(answers))
    extra = sorted(set(answers) - set(question_ids))
    if missing or extra:
        raise BackendError(
            f"Jev の応答の問いが送信と一致しません（欠落 {missing} / 余剰 {extra}）"
        )
    input_tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
    if (
        isinstance(input_tokens, bool)
        or not isinstance(input_tokens, int)
        or input_tokens < 0
    ):
        raise BackendError("Jev の応答の usage.input_tokens が非負整数ではありません")
    probabilities: dict[str, float] = {}
    for question_id in question_ids:
        answer = answers[question_id]
        value = answer.get("noul") if isinstance(answer, dict) else None
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0.0 <= float(value) <= 1.0
        ):
            raise BackendError(
                f"Jev の応答の answers.{question_id}.noul が 0〜1 の数値ではありません"
            )
        probabilities[question_id] = float(value)
    return Judgement(
        probabilities=probabilities, input_tokens=input_tokens, model=model
    )


def _send(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class JevBackend:
    name = "jev"

    def __init__(
        self,
        api_key: str,
        transport: Transport = _send,
        timeout: float = TIMEOUT_SECONDS,
    ):
        self._api_key = api_key
        self._transport = transport
        self._timeout = timeout

    @classmethod
    def from_environment(cls) -> "JevBackend":
        api_key = os.environ.get(API_KEY_ENV)
        if not api_key:
            raise BackendError(
                f"環境変数 {API_KEY_ENV} が設定されていないため、Jev を呼べません"
            )
        return cls(api_key)

    def judge(self, document: str, questions: dict[str, str]) -> Judgement:
        payload = build_payload(document, questions)
        request = urllib.request.Request(
            API_ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            body = self._transport(request, self._timeout)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read() or b""
            except OSError:
                detail = b""
            finally:
                exc.close()
            # 本文は転記しない。コンテキスト長の超過を示す識別子だけを拾う
            suffix = (
                "（max_tokens_exceeded: 文書と問いがコンテキスト長を超えています）"
                if b"max_tokens_exceeded" in detail
                else ""
            )
            raise BackendError(
                f"Jev の API が HTTP {exc.code} を返しました{suffix}"
            ) from exc
        except urllib.error.URLError as exc:
            raise BackendError("Jev の API へ接続できません") from exc
        except TimeoutError as exc:
            raise BackendError("Jev の API がタイムアウトしました") from exc
        except (OSError, http.client.HTTPException) as exc:
            raise BackendError(
                f"Jev の API との通信が途中で失敗しました: {type(exc).__name__}"
            ) from exc
        try:
            decoded = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackendError("Jev の応答が JSON ではありません") from exc
        return parse_response(decoded, list(questions))
