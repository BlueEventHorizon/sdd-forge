#!/usr/bin/env python3
"""executor agent の結果（`TaskResult`）の契約と検査（結果検査 RS-01 の実体）。

内部モジュール。入口は `receive_executor_result.py` の 1 本だけである。
`TaskResult` の項目の集合（REQ-034 5.3）は本モジュールが持つ。外部の雛形ファイルは持たない。

## 検査（DES-088 6.3 結果検査）

1. 結果が JSON object で、項目の集合が `TaskResult` と一致する（過不足を許さない）
2. `task_id` がタスクコンテキストのタスクと一致する。`status` は `SUCCESS` / `FAILURE`。
   `files_modified` はプロジェクトルート相対パスで重複が無い。`summary` は 1〜2 行
3. `verification` の各値が `success` / `skipped` / `failed` で、`success` のとき理由は `null`、
   それ以外は理由がある
4. `status` が `SUCCESS` のとき、`error` は `null`、`verification` に `failed` が無く、
   タスクコンテキストが `required` の検証は `success`、`skipped` の検証は `skipped` である
   （`tests` が `optional` のときは、`success` / `skipped` のどちらでもよい）
5. 違反があれば、理由を `error` に持つ `FAILURE` の結果を、成功の結果と同じ形で返す

期待値（build・tests）は、タスクコンテキストの `verification` から得る。呼び出し側から
引数で渡さない。結果が空・JSON でないときも契約違反であり、推測で補完しない。
"""

from pathlib import PurePosixPath


TASK_RESULT_FIELDS = frozenset(
    {"task_id", "status", "files_modified", "summary", "verification", "notes", "error"}
)
VERIFICATION_RESULT_FIELDS = frozenset(
    {"build", "build_reason", "tests", "tests_reason"}
)
VERIFICATION_STATES = ("success", "skipped", "failed")
STATUSES = ("SUCCESS", "FAILURE")

# タスクコンテキスト（`VerificationPlan`）の値域
PLAN_BUILD_VALUES = ("required", "skipped")
PLAN_TESTS_VALUES = ("required", "optional", "skipped")

_FAILURE_SUMMARY = "executor agent の結果が契約に反する"


class ContextError(Exception):
    """タスクコンテキストから検査の期待値を得られないときに送出する。"""


def load_expectation(context):
    """タスクコンテキスト（dict）から `(task_id, build, tests, build_reason, tests_reason)` を返す。

    得られないときは `ContextError`。期待値を推測で補わない。
    """
    if not isinstance(context, dict):
        raise ContextError("タスクコンテキストは JSON object である必要があります")
    task_id = context.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ContextError(
            "タスクコンテキストの task_id が空でない文字列ではありません"
        )
    verification = context.get("verification")
    if not isinstance(verification, dict):
        raise ContextError("タスクコンテキストの verification が object ではありません")
    build = verification.get("build")
    tests = verification.get("tests")
    if build not in PLAN_BUILD_VALUES:
        raise ContextError(
            f"タスクコンテキストの verification.build は {list(PLAN_BUILD_VALUES)} のいずれかである必要があります"
        )
    if tests not in PLAN_TESTS_VALUES:
        raise ContextError(
            f"タスクコンテキストの verification.tests は {list(PLAN_TESTS_VALUES)} のいずれかである必要があります"
        )
    return (
        task_id.strip(),
        build,
        tests,
        verification.get("build_reason"),
        verification.get("tests_reason"),
    )


def _field_set_errors(label, value, expected):
    if not isinstance(value, dict):
        return [f"{label} は object である必要があります"]
    actual = set(value)
    errors = []
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        errors.append(f"{label} に必須フィールドがありません: {missing}")
    if unknown:
        errors.append(f"{label} に未知フィールドがあります: {unknown}")
    return errors


def _nonempty_string(label, value, errors):
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} は空でない文字列である必要があります")
        return ""
    return value.strip()


def _string_list(label, value, errors):
    if not isinstance(value, list):
        errors.append(f"{label} は配列である必要があります")
        return []
    normalized = []
    for index, item in enumerate(value):
        text = _nonempty_string(f"{label}[{index}]", item, errors)
        if text:
            normalized.append(text)
    return normalized


def _paths(value, errors):
    normalized = []
    seen = set()
    for path in _string_list("files_modified", value, errors):
        posix = PurePosixPath(path)
        if posix.is_absolute() or ".." in posix.parts or path in {".", ".."}:
            errors.append(
                f"files_modified はプロジェクトルート相対パスである必要があります: {path!r}"
            )
            continue
        if "\n" in path or "\r" in path or "\0" in path:
            errors.append(f"files_modified に改行・NUL 文字を含められません: {path!r}")
            continue
        normalized_path = posix.as_posix()
        if normalized_path in seen:
            errors.append(f"files_modified に重複があります: {normalized_path!r}")
            continue
        seen.add(normalized_path)
        normalized.append(normalized_path)
    return normalized


def _verification(raw, errors):
    errors.extend(_field_set_errors("verification", raw, VERIFICATION_RESULT_FIELDS))
    if not isinstance(raw, dict):
        return None
    normalized = {}
    for name in ("build", "tests"):
        state = raw.get(name)
        reason_name = f"{name}_reason"
        reason = raw.get(reason_name)
        if not isinstance(state, str) or state not in VERIFICATION_STATES:
            errors.append(
                f"verification.{name} は success / skipped / failed のいずれかです"
            )
            normalized[name] = None
        else:
            normalized[name] = state
        if state == "success":
            if reason is not None:
                errors.append(f"verification.{reason_name} は success 時は null です")
            normalized[reason_name] = None
        else:
            normalized[reason_name] = _nonempty_string(
                f"verification.{reason_name}", reason, errors
            )
    return normalized


def inspect_result(raw, task_id, build, tests):
    """結果を検査し、`(正規化した TaskResult | None, errors)` を返す。違反が無ければ errors は空。"""
    errors = _field_set_errors("result", raw, TASK_RESULT_FIELDS)
    if not isinstance(raw, dict):
        return None, errors

    actual_task_id = _nonempty_string("task_id", raw.get("task_id"), errors)
    if actual_task_id and actual_task_id != task_id:
        errors.append(
            f"task_id が起動したタスクと一致しません: expected={task_id!r}, actual={actual_task_id!r}"
        )

    status = raw.get("status")
    if not isinstance(status, str) or status not in STATUSES:
        errors.append("status は SUCCESS / FAILURE のいずれかです")
        status = None

    error = raw.get("error")
    if status == "SUCCESS":
        if error is not None:
            errors.append("error は SUCCESS 時は null です")
        normalized_error = None
    else:
        normalized_error = _nonempty_string("error", error, errors)

    summary = _nonempty_string("summary", raw.get("summary"), errors)
    if summary and len(summary.splitlines()) > 2:
        errors.append("summary は 1〜2 行である必要があります")

    verification = _verification(raw.get("verification"), errors)
    if status == "SUCCESS" and verification is not None:
        states = (verification["build"], verification["tests"])
        if "failed" in states:
            errors.append(
                "status が SUCCESS の場合、verification に failed を含められません"
            )
        if build == "required" and verification["build"] != "success":
            errors.append(
                "必須の build 検証は SUCCESS 時に success である必要があります"
            )
        if build == "skipped" and verification["build"] != "skipped":
            errors.append("スキップ指定の build 検証は skipped である必要があります")
        if tests == "required" and verification["tests"] != "success":
            errors.append(
                "必須の tests 検証は SUCCESS 時に success である必要があります"
            )
        if tests == "skipped" and verification["tests"] != "skipped":
            errors.append("スキップ指定の tests 検証は skipped である必要があります")

    normalized = {
        "task_id": task_id,
        "status": status,
        "files_modified": _paths(raw.get("files_modified"), errors),
        "summary": summary,
        "verification": verification,
        "notes": _string_list("notes", raw.get("notes"), errors),
        "error": normalized_error,
    }
    return (None if errors else normalized), errors


def failure_result(task_id, errors, build, tests, build_reason=None, tests_reason=None):
    """契約違反を、理由を `error` に持つ `FAILURE` の結果（成功の結果と同じ形）へ置き換える。

    検証の値は、タスクコンテキストが `skipped` の検証を `skipped`、それ以外を `failed` とする
    （実行の結果を検査できていないため、成功とは言えない）。
    """

    def _entry(plan_value, reason, plan_reason):
        if plan_value == "skipped":
            return "skipped", plan_reason or reason
        return "failed", reason

    build_state, build_why = _entry(build, _FAILURE_SUMMARY, build_reason)
    tests_state, tests_why = _entry(tests, _FAILURE_SUMMARY, tests_reason)
    return {
        "task_id": task_id,
        "status": "FAILURE",
        "files_modified": [],
        "summary": _FAILURE_SUMMARY,
        "verification": {
            "build": build_state,
            "build_reason": build_why,
            "tests": tests_state,
            "tests_reason": tests_why,
        },
        "notes": list(errors),
        "error": "; ".join(errors),
    }


def check_result(raw, context):
    """タスクコンテキスト（dict）に照らして結果を検査し、`TaskResult` を必ず返す。

    契約違反は `FAILURE` の結果に置き換える。タスクコンテキストから期待値を得られないときは
    `ContextError` を送出する（結果を推測で検査しない）。
    """
    task_id, build, tests, build_reason, tests_reason = load_expectation(context)
    normalized, errors = inspect_result(raw, task_id, build, tests)
    if errors:
        return failure_result(task_id, errors, build, tests, build_reason, tests_reason)
    return normalized
