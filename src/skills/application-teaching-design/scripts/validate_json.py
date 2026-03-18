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
DEFAULT_TARGET_PATH = SKILL_DIR / "references" / "demo.json"


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
        nargs="?",
        default=str(DEFAULT_TARGET_PATH),
        help="Path to the JSON file to validate. Defaults to references/demo.json.",
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

    root_activity_sequence = instance.get("活动序列")
    if not isinstance(root_activity_sequence, dict):
        return errors

    course_design = instance.get("课程设计")
    if not isinstance(course_design, list):
        return errors

    course_activity_section = None
    for item in course_design:
        if isinstance(item, dict) and item.get("key") == "活动序列":
            course_activity_section = item
            break

    if not isinstance(course_activity_section, dict):
        return errors

    course_activity_value = course_activity_section.get("value")
    sorted_names = course_activity_section.get("sorted_names")

    if isinstance(course_activity_value, dict):
        root_names = list(root_activity_sequence.keys())
        course_names = list(course_activity_value.keys())
        if root_names != course_names:
            errors.append(
                "根层 `活动序列` 与 `课程设计[].活动序列.value` 的活动名称顺序或内容不一致"
            )

        if isinstance(sorted_names, list) and sorted_names != course_names:
            errors.append(
                "`课程设计[].活动序列.sorted_names` 与 `课程设计[].活动序列.value` 的活动名称不一致"
            )

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
    except Exception as exc:  # pragma: no cover - direct CLI reporting
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
