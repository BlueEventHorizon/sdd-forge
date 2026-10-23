#!/usr/bin/env python3
"""計画書（`{feature}_plan.json`）の読み書き・スキーマ検証を担う共有コアモジュール。

`start-plan`（生成）・`start-implement`（タスク選択・依存判定・ステータス更新）の
複数 SKILL から再利用される（REQ-003 FNC-006: 複数 SKILL が再利用する実体ロジックは
プラグイン共通の低レベル script に置く）。SKILL ローカルの操作入口はこのモジュールを
import し、当該 SKILL が必要とする操作だけを公開する。
"""

import json
import os
import re
import stat
import tempfile
from pathlib import Path


TOP_LEVEL_KEYS = {
    "requirements_traceability",
    "design_traceability",
    "tasks",
}

#: `design_traceability[]` の必須フィールド。`requirement_ids` は
#: `update_plan_status.py` が要件のステータスを判定する唯一の経路であり、
#: 欠けると全タスクを completed にしても要件が pending のまま静かに残る。
DESIGN_TRACEABILITY_REQUIRED_FIELDS = {
    "design_id",
    "requirement_ids",
    "task_ids",
}

TASK_REQUIRED_FIELDS = {
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
}

TASK_STATUS_VALUES = {"pending", "in_progress", "implemented", "completed", "failed"}
BUILD_CHECK_VALUES = {"per_task", "skip", "on_group_complete"}
REQUIREMENT_STATUS_VALUES = {"pending", "completed"}

_GROUP_KEY_RE = re.compile(r"^(.*?)\s*\(")


class PlanContractError(Exception):
    """計画書の読み込み・検証に失敗した場合に送出する。"""


def load_plan(plan_path):
    """計画書 JSON を読み込んで dict を返す。読み込めない場合は PlanContractError。"""
    path = Path(plan_path)
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanContractError(f"計画書を読み込めません: {exc}") from exc


def _plan_file_mode(path):
    """置き換え後の計画書に与えるモード。既存の計画書はそのモード、新規は umask に従う通常のモード。"""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask


def save_plan(plan_path, data):
    """計画書 JSON を書き込む。親ディレクトリが無ければ作成する。

    同じディレクトリの一時ファイルへ書いてから `os.replace` で置き換える。途中で
    失敗しても、既存の計画書は元の内容のまま残り、一時ファイルも残さない。
    置き換え後のモードは、既存の計画書があればそのモード、無ければ umask に従う。
    排他の制御（ロック）は持たない。
    """
    path = Path(plan_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = _plan_file_mode(path)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def validate_plan_schema(data):
    """計画書の構造とタスク ID の一意性を検証し、errors を返す（空なら妥当）。"""
    errors = []
    if not isinstance(data, dict):
        return ["計画書は object である必要があります"]

    actual_keys = set(data)
    missing = sorted(TOP_LEVEL_KEYS - actual_keys)
    unknown = sorted(actual_keys - TOP_LEVEL_KEYS)
    if missing:
        errors.append(f"必須の top-level キーがありません: {missing}")
    if unknown:
        errors.append(f"未知の top-level キーがあります: {unknown}")

    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        errors.append("tasks は配列である必要があります")
    else:
        seen_task_ids = set()
        for index, task in enumerate(tasks):
            errors.extend(validate_task(index, task))
            task_id = task.get("task_id") if isinstance(task, dict) else None
            if isinstance(task_id, str):
                if task_id in seen_task_ids:
                    errors.append(f"tasks[{index}].task_id が重複しています: {task_id}")
                seen_task_ids.add(task_id)

    designs = data.get("design_traceability")
    if designs is not None and not isinstance(designs, list):
        errors.append("design_traceability は配列である必要があります")
    elif isinstance(designs, list):
        for index, entry in enumerate(designs):
            if not isinstance(entry, dict):
                errors.append(
                    f"design_traceability[{index}] は object である必要があります"
                )
                continue
            missing_fields = sorted(DESIGN_TRACEABILITY_REQUIRED_FIELDS - set(entry))
            if missing_fields:
                errors.append(
                    f"design_traceability[{index}] に必須フィールドがありません: {missing_fields}"
                )

    requirements = data.get("requirements_traceability")
    if requirements is not None and not isinstance(requirements, list):
        errors.append("requirements_traceability は配列である必要があります")
    elif isinstance(requirements, list):
        for index, entry in enumerate(requirements):
            if not isinstance(entry, dict):
                errors.append(
                    f"requirements_traceability[{index}] は object である必要があります"
                )
                continue
            status = entry.get("status")
            if status not in REQUIREMENT_STATUS_VALUES:
                errors.append(
                    f"requirements_traceability[{index}].status は "
                    f"{sorted(REQUIREMENT_STATUS_VALUES)} のいずれかです（実際: {status!r}）"
                )

    return errors


def _is_member(value, allowed):
    """`value` が文字列で、`allowed`（文字列の集合）に含まれるか。list・dict でも落ちない。"""
    return isinstance(value, str) and value in allowed


def validate_task(index, task):
    """計画書のタスク 1 件の構造的妥当性を検証し、errors のリストを返す（空なら妥当）。

    `index` は計画書の `tasks` 内の位置（メッセージの識別に使う）。
    """
    label = f"tasks[{index}]"
    if not isinstance(task, dict):
        return [f"{label} は object である必要があります"]

    errors = []
    actual = set(task)
    missing = sorted(TASK_REQUIRED_FIELDS - actual)
    unknown = sorted(actual - TASK_REQUIRED_FIELDS)
    if missing:
        errors.append(f"{label} に必須フィールドがありません: {missing}")
    if unknown:
        errors.append(f"{label} に未知フィールドがあります: {unknown}")

    task_id = task.get("task_id")
    if "task_id" in task and (not isinstance(task_id, str) or not task_id.strip()):
        errors.append(f"{label}.task_id は空でない文字列である必要があります")

    if not _is_member(task.get("status"), TASK_STATUS_VALUES):
        errors.append(
            f"{label}.status は {sorted(TASK_STATUS_VALUES)} のいずれかです"
            f"（実際: {task.get('status')!r}）"
        )
    if not _is_member(task.get("build_check"), BUILD_CHECK_VALUES):
        errors.append(
            f"{label}.build_check は {sorted(BUILD_CHECK_VALUES)} のいずれかです"
            f"（実際: {task.get('build_check')!r}）"
        )
    if not isinstance(task.get("depends_on"), list):
        errors.append(f"{label}.depends_on は配列である必要があります")
    if not isinstance(task.get("required_reading"), list):
        errors.append(f"{label}.required_reading は配列である必要があります")
    if task.get("design_id") is not None and not isinstance(task.get("design_id"), str):
        errors.append(f"{label}.design_id は文字列か null である必要があります")

    return errors


def read_and_consume_candidate_input(input_file):
    """候補 JSON を `.temp/forge/` 配下から読み込み、成否に関わらず入力ファイルを削除する。

    `write_plan.py`（start-plan）と `build_task_context.py`（start-implement）の双方が
    「AI が組み立てた候補 JSON を一時ファイル経由で受け取り、消費後に削除する」という
    同一の入出力契約を必要とするため、本モジュールへ集約する。
    """
    path = Path(input_file)
    if path.is_absolute() or ".." in path.parts or path.parts[:2] != (".temp", "forge"):
        return None, [
            "input-file は .temp/forge/ 配下のプロジェクトルート相対パスである必要があります"
        ]
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle), []
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"入力を JSON object として解析できません: {exc}"]
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def normalize_group_key(group_id):
    """通し番号付き group_id ("GROUP-001 (1/7)") からグループキー ("GROUP-001") を抽出する。

    括弧を含まない場合はそのまま返す（フォーマットの揺れに対する保守的なフォールバック）。
    タスク選択（`select_tasks.py`）と範囲導出の script の双方が同一のグループ正規化を
    要求するため、本モジュールへ集約する。
    """
    if group_id is None:
        return None
    match = _GROUP_KEY_RE.match(group_id)
    if match:
        key = match.group(1).strip()
        return key if key else group_id
    return group_id
