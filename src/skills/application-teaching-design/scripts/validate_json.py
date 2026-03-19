#!/usr/bin/env python3
"""Validate teaching design JSON files against references/schema.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_SCHEMA_PATH = SKILL_DIR / "references" / "schema.json"


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def format_path(error: ValidationError) -> str:
    if not error.absolute_path:
        return "$"
    return "$." + ".".join(str(part) for part in error.absolute_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a teaching design JSON file against schema.json."
    )
    parser.add_argument(
        "target",
        help="Path to the JSON file to validate.",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help="Path to the JSON Schema file. Defaults to references/schema.json.",
    )
    return parser


def iter_semantic_errors(instance: object) -> list[str]:
    if not isinstance(instance, dict):
        return []

    errors: list[str] = []

    course_info = instance.get("课程信息")
    activities = instance.get("活动序列")

    if not isinstance(course_info, dict) or not isinstance(activities, list):
        return errors

    time_allocation = course_info.get("学时安排")
    if not isinstance(time_allocation, dict):
        return errors

    total_in_class = 0
    total_after_class = 0

    seen_activity_ids: set[str] = set()
    seen_task_ids: set[str] = set()

    learning_goals = instance.get("学习目标")
    if isinstance(learning_goals, dict):
        ability_goals = learning_goals.get("能力目标")
        course_type = str(course_info.get("课程类型", ""))
        if "项目化" in course_type and (not isinstance(ability_goals, list) or len(ability_goals) == 0):
            errors.append("课程类型包含“项目化”时，学习目标.能力目标 不能为空")

    for index, activity in enumerate(activities, start=1):
        if not isinstance(activity, dict):
            continue

        activity_id = activity.get("活动id")
        if isinstance(activity_id, str):
            if activity_id in seen_activity_ids:
                errors.append(f"活动id 重复: {activity_id}")
            seen_activity_ids.add(activity_id)

        if activity.get("排序") != index:
            activity_name = activity.get("活动名称", activity_id or "未知活动")
            errors.append(f"活动 `{activity_name}` 的排序应为 {index}")

        activity_time = activity.get("时间分配")
        tasks = activity.get("任务序列")
        if not isinstance(activity_time, dict) or not isinstance(tasks, list):
            continue

        activity_in_class = activity_time.get("课上分钟", 0)
        activity_after_class = activity_time.get("课下分钟", 0)
        if isinstance(activity_in_class, int):
            total_in_class += activity_in_class
        if isinstance(activity_after_class, int):
            total_after_class += activity_after_class

        task_in_class = 0
        task_after_class = 0

        for task_index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                continue

            task_id = task.get("任务id")
            if isinstance(task_id, str):
                if task_id in seen_task_ids:
                    errors.append(f"任务id 重复: {task_id}")
                seen_task_ids.add(task_id)

            if task.get("排序") != task_index:
                task_name = task.get("任务名称", task_id or "未知任务")
                errors.append(f"任务 `{task_name}` 的排序应为 {task_index}")

            duration = task.get("任务时长分钟")
            location = task.get("学习地点")
            if not isinstance(duration, int) or not isinstance(location, str):
                continue

            method = task.get("教学方式")
            method_values = method.get("方式") if isinstance(method, dict) else []
            if location == "课上" and isinstance(method_values, list) and "自主学习" in method_values:
                task_name = task.get("任务名称", task_id or "未知任务")
                errors.append(f"任务 `{task_name}` 学习地点为课上时，教学方式不能包含“自主学习”")
            if location == "课下" and isinstance(method_values, list) and "讲授" in method_values:
                task_name = task.get("任务名称", task_id or "未知任务")
                errors.append(f"任务 `{task_name}` 学习地点为课下时，教学方式不能包含“讲授”")

            if location == "课上":
                task_in_class += duration
            elif location == "课下":
                task_after_class += duration

        if task_in_class != activity_in_class or task_after_class != activity_after_class:
            activity_name = activity.get("活动名称", activity_id or "未知活动")
            errors.append(
                f"活动 `{activity_name}` 的时间分配与任务时长汇总不一致"
            )

    if time_allocation.get("课上分钟") != total_in_class:
        errors.append("课程信息.学时安排.课上分钟 与活动课上分钟汇总不一致")
    if time_allocation.get("课下分钟") != total_after_class:
        errors.append("课程信息.学时安排.课下分钟 与活动课下分钟汇总不一致")

    return errors


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    schema_path = Path(args.schema).resolve()

    if not target_path.is_file():
        print(f"Target JSON not found: {target_path}", file=sys.stderr)
        return 2
    if not schema_path.is_file():
        print(f"Schema JSON not found: {schema_path}", file=sys.stderr)
        return 2

    schema = load_json(schema_path)
    instance = load_json(target_path)

    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
    except Exception as exc:
        print(f"Validation setup failed: {exc}", file=sys.stderr)
        return 2

    if errors:
        print(f"INVALID: {target_path}")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {format_path(error)}: {error.message}")
        return 1

    semantic_errors = iter_semantic_errors(instance)
    if semantic_errors:
        print(f"INVALID: {target_path}")
        for index, error in enumerate(semantic_errors, start=1):
            print(f"{index}. $: {error}")
        return 1

    print(f"VALID: {target_path}")
    print(f"Schema: {schema_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
