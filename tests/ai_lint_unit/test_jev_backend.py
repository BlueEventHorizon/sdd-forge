#!/usr/bin/env python3
"""Jev backend（`ai_lint/backends/jev.py`）の単体テスト。ネットワークへは出ない。

実行:
  python3 -m unittest tests.ai_lint_unit.test_jev_backend -v
"""

from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from unittest import mock

from ai_lint.backend import BackendError
from ai_lint.backends.jev import (
    API_ENDPOINT,
    API_KEY_ENV,
    MODEL,
    JevBackend,
    build_payload,
    parse_response,
)

QUESTIONS = {"q1": "`document` は A か。", "q2": "`document` は B か。"}
SECRET = "secret-key-for-test"


def response(**overrides):
    data = {
        "model": MODEL,
        "usage": {"input_tokens": 123, "output_tokens": 0},
        "answers": {
            "q1": {"type": "noul", "noul": 0.91},
            "q2": {"type": "noul", "noul": 0.02},
        },
    }
    data.update(overrides)
    return data


class PayloadTest(unittest.TestCase):
    def test_document_is_sent_once_with_all_questions(self):
        payload = build_payload("本文", QUESTIONS)
        self.assertEqual(MODEL, payload["model"])
        self.assertEqual({"document": "本文"}, payload["state"])
        self.assertEqual(
            {
                "q1": {"type": "noul", "instructions": QUESTIONS["q1"]},
                "q2": {"type": "noul", "instructions": QUESTIONS["q2"]},
            },
            payload["questions"],
        )


class ParseResponseTest(unittest.TestCase):
    def test_valid(self):
        judgement = parse_response(response(), list(QUESTIONS))
        self.assertEqual({"q1": 0.91, "q2": 0.02}, judgement.probabilities)
        self.assertEqual(123, judgement.input_tokens)
        self.assertEqual(MODEL, judgement.model)

    def test_responses_outside_the_contract_are_rejected(self):
        cases = {
            "ルートが配列": [],
            "model が無い": response(model=""),
            "answers が無い": response(answers=None),
            "問いが欠ける": response(answers={"q1": {"noul": 0.9}}),
            "余分な問い": response(
                answers={"q1": {"noul": 0.9}, "q2": {"noul": 0.1}, "q3": {"noul": 0.1}}
            ),
            "確率が範囲外": response(
                answers={"q1": {"noul": 1.5}, "q2": {"noul": 0.1}}
            ),
            "確率が真偽値": response(
                answers={"q1": {"noul": True}, "q2": {"noul": 0.1}}
            ),
            "usage が無い": response(usage=None),
        }
        for name, data in cases.items():
            with self.subTest(name):
                with self.assertRaises(BackendError):
                    parse_response(data, list(QUESTIONS))


class JevBackendTest(unittest.TestCase):
    def test_missing_api_key_is_an_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BackendError) as caught:
                JevBackend.from_environment()
        self.assertIn(API_KEY_ENV, str(caught.exception))

    def test_request_carries_the_key_only_in_the_header(self):
        seen = {}

        def transport(request, timeout):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            seen["body"] = request.data.decode("utf-8")
            return json.dumps(response()).encode("utf-8")

        judgement = JevBackend(SECRET, transport=transport).judge("本文", QUESTIONS)
        self.assertEqual(API_ENDPOINT, seen["url"])
        self.assertEqual(f"Bearer {SECRET}", seen["auth"])
        self.assertNotIn(SECRET, seen["body"])
        self.assertEqual(0.91, judgement.probabilities["q1"])

    def test_failures_become_backend_errors_without_key_or_body(self):
        def http_error(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO("max_tokens_exceeded 本文の写し".encode("utf-8")),
            )

        def url_error(request, timeout):
            raise urllib.error.URLError("no route")

        def timeout_error(request, timeout):
            raise TimeoutError()

        def not_json(request, timeout):
            return b"<html>"

        for name, transport in {
            "HTTP エラー": http_error,
            "接続できない": url_error,
            "タイムアウト": timeout_error,
            "JSON でない": not_json,
        }.items():
            with self.subTest(name):
                with self.assertRaises(BackendError) as caught:
                    JevBackend(SECRET, transport=transport).judge("本文", QUESTIONS)
                message = str(caught.exception)
                self.assertNotIn(SECRET, message)
                self.assertNotIn("本文の写し", message)

    def test_context_overflow_is_named(self):
        def transport(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(b"max_tokens_exceeded"),
            )

        with self.assertRaises(BackendError) as caught:
            JevBackend(SECRET, transport=transport).judge("本文", QUESTIONS)
        self.assertIn("max_tokens_exceeded", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
