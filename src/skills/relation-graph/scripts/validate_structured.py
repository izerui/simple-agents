#!/usr/bin/env python3
"""Validate structured relation graph JSON files before composing final output."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


MIN_NODE_GAP = 20
ALLOWED_NODE_TYPES = {2, 3, 5, 6}
ALLOWED_COLORS = {"#FF0000", "#00B0F0", "#00B050", "#000000"}
COLOR_ALIASES = {
    "#ff0000": "#FF0000",
    "#00b0f0": "#00B0F0",
    "#00b050": "#00B050",
    "#000000": "#000000",
    "#548bd4": "#00B0F0",
    "#0070c0": "#00B0F0",
}
ALLOWED_JUNCTION_POINTS = {"border", "left", "right", "top", "bottom"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a structured relation graph JSON file."
    )
    parser.add_argument("target", help="Path to the structured JSON file to validate.")
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


def normalize_color(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return COLOR_ALIASES.get(value.strip(), COLOR_ALIASES.get(value.strip().lower()))


def iter_errors(instance: Any) -> list[str]:
    if not isinstance(instance, dict):
        return ["根对象必须是 JSON 对象"]

    errors: list[str] = []
    root_id = instance.get("rootId")
    nodes = instance.get("nodes")
    lines = instance.get("lines")

    if not isinstance(root_id, str) or not root_id.strip():
        errors.append("`rootId` 必须是非空字符串")

    if "datetime" in instance and not isinstance(instance["datetime"], (int, float)):
        errors.append("`datetime` 必须是数字")

    if not isinstance(nodes, list) or not nodes:
        errors.append("`nodes` 必须是非空数组")
        return errors

    if not isinstance(lines, list):
        errors.append("`lines` 必须是数组")
        return errors

    node_ids: list[str] = []
    line_ids: list[str] = []
    node_by_id: dict[str, dict[str, Any]] = {}

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"`nodes[{index}]` 必须是对象")
            continue

        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            errors.append(f"`nodes[{index}].id` 必须是非空字符串")
            continue
        node_ids.append(node_id)
        node_by_id[node_id] = node

        text = node.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"节点 `{node_id}` 的 text 必须是非空字符串")
        elif any(char in text for char in ("\r", "\n")):
            errors.append(f"节点 `{node_id}` 的 text 不允许换行")

        for field in ("x", "y", "width", "height"):
            if not isinstance(node.get(field), (int, float)):
                errors.append(f"节点 `{node_id}` 必须提供数字类型的 `{field}`")

        border_color = normalize_color(node.get("borderColor"))
        if border_color not in ALLOWED_COLORS:
            errors.append(f"节点 `{node_id}` 的 borderColor 仅支持 {sorted(ALLOWED_COLORS)}")

        data = node.get("data")
        if not isinstance(data, dict):
            errors.append(f"节点 `{node_id}` 的 data 必须是对象")
        else:
            node_type = data.get("type")
            if not isinstance(node_type, int) or node_type not in ALLOWED_NODE_TYPES:
                errors.append(
                    f"节点 `{node_id}` 的 data.type 仅支持 {sorted(ALLOWED_NODE_TYPES)}"
                )

    if len(node_ids) != len(set(node_ids)):
        errors.append("nodes 中存在重复 id")

    if isinstance(root_id, str) and root_id and root_id not in node_by_id:
        errors.append(f"`rootId` 未引用有效节点: {root_id}")

    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            errors.append(f"`lines[{index}]` 必须是对象")
            continue

        line_id = line.get("id")
        if not isinstance(line_id, str) or not line_id.strip():
            errors.append(f"`lines[{index}].id` 必须是非空字符串")
            continue
        line_ids.append(line_id)

        text = line.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"连线 `{line_id}` 的 text 必须是非空字符串")
        elif any(char in text for char in ("\r", "\n")):
            errors.append(f"连线 `{line_id}` 的 text 不允许换行")

        from_id = line.get("from")
        to_id = line.get("to")
        if not isinstance(from_id, str) or not from_id.strip():
            errors.append(f"连线 `{line_id}` 的 from 必须是非空字符串")
        elif from_id not in node_by_id:
            errors.append(f"连线 `{line_id}` 的 from 未引用有效节点")
        if not isinstance(to_id, str) or not to_id.strip():
            errors.append(f"连线 `{line_id}` 的 to 必须是非空字符串")
        elif to_id not in node_by_id:
            errors.append(f"连线 `{line_id}` 的 to 未引用有效节点")

        for field in ("fromJunctionPoint", "toJunctionPoint"):
            if field in line:
                value = line.get(field)
                if value not in ALLOWED_JUNCTION_POINTS:
                    errors.append(
                        f"连线 `{line_id}` 的 {field} 仅支持 {sorted(ALLOWED_JUNCTION_POINTS)}"
                    )

        if "lineShape" in line and not isinstance(line["lineShape"], int):
            errors.append(f"连线 `{line_id}` 的 lineShape 必须是整数")

    if len(line_ids) != len(set(line_ids)):
        errors.append("lines 中存在重复 id")

    valid_nodes = [
        node for node in nodes
        if isinstance(node, dict)
        and isinstance(node.get("x"), (int, float))
        and isinstance(node.get("y"), (int, float))
        and isinstance(node.get("width"), (int, float))
        and isinstance(node.get("height"), (int, float))
        and isinstance(node.get("id"), str)
    ]
    for i, left in enumerate(valid_nodes):
        for right in valid_nodes[i + 1:]:
            if boxes_too_close(left, right, MIN_NODE_GAP):
                errors.append(
                    f"节点 `{left['id']}` 与 `{right['id']}` 间距过近，未满足最小间距要求"
                )

    incoming_count: dict[str, int] = {node_id: 0 for node_id in node_ids}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    referenced = {root_id} if isinstance(root_id, str) else set()
    for line in lines:
        if isinstance(line, dict):
            from_id = line.get("from")
            to_id = line.get("to")
            if isinstance(from_id, str):
                referenced.add(from_id)
            if isinstance(to_id, str):
                referenced.add(to_id)
                if to_id in incoming_count:
                    incoming_count[to_id] += 1
                if isinstance(from_id, str) and from_id in adjacency:
                    adjacency[from_id].append(to_id)

    for node_id, count in incoming_count.items():
        if count > 1:
            errors.append(f"节点 `{node_id}` 存在多个父节点")

    visited: set[str] = set()
    visiting: set[str] = set()

    def has_cycle(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        for next_id in adjacency.get(node_id, []):
            if next_id in adjacency and has_cycle(next_id):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    for node_id in adjacency:
        if has_cycle(node_id):
            errors.append("连接关系不允许形成循环")
            break

    isolated = [node_id for node_id in node_ids if node_id not in referenced]
    if isolated:
        errors.append("存在孤立节点: " + ", ".join(sorted(isolated)))

    return errors


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.is_file():
        print(f"Structured JSON not found: {target_path}", file=sys.stderr)
        return 2

    try:
        instance = load_json(target_path)
    except Exception as exc:
        print(f"Failed to read JSON: {exc}", file=sys.stderr)
        return 2

    errors = iter_errors(instance)
    if errors:
        print(f"INVALID: {target_path}")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. $: {error}")
        return 1

    print(f"VALID: {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
