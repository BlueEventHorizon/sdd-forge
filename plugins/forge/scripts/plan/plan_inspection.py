#!/usr/bin/env python3
"""計画書の検査（DES-088 CH-01）。計画書を作る側（`/forge:start-plan`）が呼ぶための検査関数。

検査は入力を変更せず、違反を自然文の一覧で返す。違反が無ければ空の一覧を返す。

- ``find_dependency_violations`` — 依存の構造（自己依存・存在しないタスクへの依存・依存の循環）。
  計画書を知らない純関数であり、タスク ID から先行タスク ID の配列への対応だけを受け取る
- ``inspect_plan`` — 計画書全体。上記に加え、設計の識別子の対応・``required_reading`` の型・
  タスクに辿れない要件（設計が無い、または設計にタスクが 1 件も無い要件）を見る

呼び出し元は未配線である（start-plan への組み込みは本モジュールの範囲外）。
``plan_contract.validate_plan_schema`` の挙動は変えない。

終了コードを持つ操作入口は無い（import して使う関数だけを提供する）。
"""


def find_dependency_violations(dependencies):
    """依存の構造の違反を自然文の一覧で返す。

    ``dependencies`` はタスク ID から先行タスク ID の配列への対応（dict）。入力は変更しない。
    """
    violations = []
    known = set(dependencies)

    # 自己依存と存在しない先行は、タスクの定義順に報告する
    graph = {}
    for task_id, predecessors in dependencies.items():
        edges = []
        for predecessor in predecessors:
            if predecessor == task_id:
                violations.append(f"{task_id} が自分自身に依存しています")
            elif predecessor not in known:
                violations.append(
                    f"{task_id} が存在しないタスク {predecessor} に依存しています"
                )
            elif predecessor not in edges:
                edges.append(predecessor)
        graph[task_id] = edges

    violations.extend(_find_cycles(graph))
    return violations


def _find_cycles(graph):
    """有向グラフ（自己辺と未知の頂点を含まない）から、循環を 1 つずつ自然文で返す。

    深さ優先で辿り、辿っている最中の頂点（経路上）へ戻る辺を見つけたとき 1 件と数える。
    反復で実装し、深い依存でも再帰の上限に当たらない。
    """
    unvisited, on_path, done = 0, 1, 2
    state = {node: unvisited for node in graph}
    cycles = []
    for root in graph:
        if state[root] != unvisited:
            continue
        path = [root]
        state[root] = on_path
        stack = [iter(graph[root])]
        while stack:
            advanced = False
            for nxt in stack[-1]:
                if state[nxt] == on_path:
                    start = path.index(nxt)
                    cycle = path[start:] + [nxt]
                    cycles.append("依存が循環しています: " + " -> ".join(cycle))
                elif state[nxt] == unvisited:
                    state[nxt] = on_path
                    path.append(nxt)
                    stack.append(iter(graph[nxt]))
                    advanced = True
                    break
            if not advanced:
                state[path.pop()] = done
                stack.pop()
    return cycles


def inspect_plan(plan):
    """計画書（dict）を検査し、違反を自然文の一覧で返す。入力は変更しない。"""
    if not isinstance(plan, dict):
        return ["計画書は object である必要があります"]
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        return ["tasks は配列である必要があります"]

    violations = []
    design_ids = _design_ids(plan.get("design_traceability"))

    dependencies = {}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            violations.append(f"tasks[{index}] は object である必要があります")
            continue
        task_id = task.get("task_id")
        label = task_id if isinstance(task_id, str) else f"tasks[{index}]"
        if not isinstance(task_id, str):
            violations.append(f"{label} の task_id は文字列である必要があります")

        # 実在するタスクの集合は depends_on の型に関わらず作る（他のタスクの依存先の判定に使うため）
        depends_on = task.get("depends_on")
        depends_on_valid = _is_list_of_str(depends_on)
        if "depends_on" in task and not depends_on_valid:
            violations.append(
                f"{label} の depends_on はタスク ID 文字列の配列である必要があります"
            )
        if isinstance(task_id, str):
            dependencies[task_id] = list(depends_on) if depends_on_valid else []

        design_id = task.get("design_id")
        if isinstance(design_id, str) and design_id not in design_ids:
            violations.append(
                f"{label} の設計 ID {design_id} が design_traceability に存在しません"
            )

        if "required_reading" in task and not _is_list_of_str(task["required_reading"]):
            violations.append(
                f"{label} の required_reading はパス文字列の配列である必要があります"
            )

    violations.extend(find_dependency_violations(dependencies))
    violations.extend(_find_untraceable_requirements(plan))
    return violations


def _find_untraceable_requirements(plan):
    """要件から設計を経由してタスクに辿れないものを違反として返す。

    設計が無い（``design_id`` が欠ける、または ``design_traceability`` に存在しない）要件と、
    設計にタスクが 1 件も無い要件が対象。実装しない要件を外す概念は無い。
    """
    requirements = plan.get("requirements_traceability")
    if not isinstance(requirements, list):
        return []
    task_ids_by_design = {}
    design_traceability = plan.get("design_traceability")
    if isinstance(design_traceability, list):
        for entry in design_traceability:
            if isinstance(entry, dict) and isinstance(entry.get("design_id"), str):
                task_ids = entry.get("task_ids")
                task_ids_by_design[entry["design_id"]] = (
                    task_ids if isinstance(task_ids, list) else []
                )

    violations = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        requirement_id = requirement.get("requirement_id")
        label = (
            requirement_id
            if isinstance(requirement_id, str)
            else f"requirements_traceability[{index}]"
        )
        design_id = requirement.get("design_id")
        if not isinstance(design_id, str) or design_id not in task_ids_by_design:
            violations.append(
                f"要件 {label} に対応する設計が design_traceability に存在せず、タスクに辿れません"
            )
        elif not task_ids_by_design[design_id]:
            violations.append(
                f"要件 {label} の設計 {design_id} にタスクが 1 件も無く、タスクに辿れません"
            )
    return violations


def _design_ids(design_traceability):
    if not isinstance(design_traceability, list):
        return set()
    return {
        entry["design_id"]
        for entry in design_traceability
        if isinstance(entry, dict) and isinstance(entry.get("design_id"), str)
    }


def _is_list_of_str(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)
