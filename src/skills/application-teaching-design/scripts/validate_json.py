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

    print(f"VALID: {target_path}")
    print(f"Schema: {schema_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
