#!/usr/bin/env python3
"""Validate relation graph JSON files against references/schema.json."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_SCHEMA_PATH = SKILL_DIR / "references" / "schema.json"
ALLOWED_LINE_COLOR = "#000000"
MIN_NODE_GAP = 18


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def format_path(error: ValidationError) -> str:
    if not error.absolute_path:
        return "$"
    return "$." + ".".join(str(part) for part in error.absolute_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a relation graph JSON file against schema.json."
    )
    parser.add_argument("target", help="Path to the JSON file to validate.")
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help="Path to the JSON Schema file. Defaults to references/schema.json.",
    )
    return parser


def values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)
    return left == right


def boxes_too_close(a: dict[str, Any], b: dict[str, Any], gap: float) -> bool:
    ax1 = float(a["x"])
    ay1 = float(a["y"])
    ax2 = ax1 + float(a["width"])
    ay2 = ay1 + float(a["height"])
    bx1 = float(b["x"])
    by1 = float(b["y"])
    bx2 = bx1 + float(b["width"])
    by2 = by1 + float(b["height"])

    return not (
        ax2 + gap <= bx1
        or bx2 + gap <= ax1
        or ay2 + gap <= by1
        or by2 + gap <= ay1
    )


def iter_semantic_errors(instance: Any) -> list[str]:
    if not isinstance(instance, dict):
        return []

    errors: list[str] = []
    nodes = instance.get("nodes")
    lines = instance.get("lines")
    root_id = instance.get("rootId")

    if not isinstance(nodes, list) or not isinstance(lines, list):
        return errors

    node_ids: list[str] = []
    line_ids: list[str] = []
    node_by_id: dict[str, dict[str, Any]] = {}

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue

        node_id = node.get("id")
        if isinstance(node_id, str):
            node_ids.append(node_id)
            node_by_id[node_id] = node

        data = node.get("data")
        if isinstance(data, dict):
            start_position = data.get("startPostion")
            if isinstance(start_position, dict):
                if not values_equal(start_position.get("x"), node.get("x")):
                    errors.append(f"节点 `{node_id or index}` 的 data.startPostion.x 必须与 x 一致")
                if not values_equal(start_position.get("y"), node.get("y")):
                    errors.append(f"节点 `{node_id or index}` 的 data.startPostion.y 必须与 y 一致")

        node_shape = node.get("nodeShape")
        if node_shape is not None and node_shape != 1:
            errors.append(f"节点 `{node_id or index}` 的 nodeShape 必须固定为 1；真实形状由 data.type 决定")

    if len(node_ids) != len(set(node_ids)):
        errors.append("nodes 中存在重复 id")

    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            continue

        line_id = line.get("id")
        if isinstance(line_id, str):
            line_ids.append(line_id)

        from_id = line.get("from")
        to_id = line.get("to")

        if isinstance(from_id, str):
            if from_id not in node_by_id:
                errors.append(f"连线 `{line_id or index}` 的 from 未引用有效节点")
        if isinstance(to_id, str):
            if to_id not in node_by_id:
                errors.append(f"连线 `{line_id or index}` 的 to 未引用有效节点")

        if "fromJunctionPoint" not in line:
            errors.append(f"连线 `{line_id or index}` 缺少 fromJunctionPoint")
        if "toJunctionPoint" not in line:
            errors.append(f"连线 `{line_id or index}` 缺少 toJunctionPoint")
        if "showStartArrow" not in line:
            errors.append(f"连线 `{line_id or index}` 缺少 showStartArrow")
        if "showEndArrow" not in line:
            errors.append(f"连线 `{line_id or index}` 缺少 showEndArrow")

        line_color = line.get("color")
        if isinstance(line_color, str) and line_color != ALLOWED_LINE_COLOR:
            errors.append(f"连线 `{line_id or index}` 的 color 必须为 {ALLOWED_LINE_COLOR}")

    if len(line_ids) != len(set(line_ids)):
        errors.append("lines 中存在重复 id")

    for i, left in enumerate(nodes):
        if not isinstance(left, dict):
            continue
        required = ("x", "y", "width", "height")
        if not all(isinstance(left.get(key), (int, float)) for key in required):
            continue
        for j in range(i + 1, len(nodes)):
            right = nodes[j]
            if not isinstance(right, dict):
                continue
            if not all(isinstance(right.get(key), (int, float)) for key in required):
                continue
            if boxes_too_close(left, right, MIN_NODE_GAP):
                left_id = left.get("id", i)
                right_id = right.get("id", j)
                errors.append(
                    f"节点 `{left_id}` 与 `{right_id}` 未满足至少 {MIN_NODE_GAP}px 的间距要求"
                )

    if node_ids:
        referenced = {root_id} if isinstance(root_id, str) else set()
        for line in lines:
            if isinstance(line, dict):
                if isinstance(line.get("from"), str):
                    referenced.add(line["from"])
                if isinstance(line.get("to"), str):
                    referenced.add(line["to"])
        isolated = [node_id for node_id in node_ids if node_id not in referenced]
        if isolated:
            errors.append("存在孤立节点: " + ", ".join(sorted(isolated)))

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
