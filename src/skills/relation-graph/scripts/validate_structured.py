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
MIN_SIBLING_Y_GAP = 36
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


def center(node: dict[str, Any]) -> tuple[float, float]:
    return (
        float(node["x"]) + float(node["width"]) / 2,
        float(node["y"]) + float(node["height"]) / 2,
    )


def orientation(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> int:
    value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    if math.isclose(value, 0.0, abs_tol=1e-9):
        return 0
    return 1 if value > 0 else 2


def on_segment(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> bool:
    return (
        min(a[0], c[0]) - 1e-9 <= b[0] <= max(a[0], c[0]) + 1e-9
        and min(a[1], c[1]) - 1e-9 <= b[1] <= max(a[1], c[1]) + 1e-9
    )


def segments_intersect(
    p1: tuple[float, float],
    q1: tuple[float, float],
    p2: tuple[float, float],
    q2: tuple[float, float],
) -> bool:
    o1 = orientation(p1, q1, p2)
    o2 = orientation(p1, q1, q2)
    o3 = orientation(p2, q2, p1)
    o4 = orientation(p2, q2, q1)

    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_segment(p1, p2, q1):
        return True
    if o2 == 0 and on_segment(p1, q2, q1):
        return True
    if o3 == 0 and on_segment(p2, p1, q2):
        return True
    if o4 == 0 and on_segment(p2, q1, q2):
        return True
    return False


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

    for index, left_id in enumerate(node_ids):
        left = node_by_id[left_id]
        for right_id in node_ids[index + 1:]:
            right = node_by_id[right_id]
            if boxes_too_close(left, right, MIN_NODE_GAP):
                errors.append(f"节点 `{left_id}` 与 `{right_id}` 过近或重叠")

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
                if isinstance(from_id, str) and from_id in adjacency:
                    adjacency[from_id].append(to_id)

    isolated = [node_id for node_id in node_ids if node_id not in referenced]
    if isolated:
        errors.append("存在孤立节点: " + ", ".join(sorted(isolated)))

    parent_to_children: dict[str, list[dict[str, Any]]] = {}
    for line in lines:
        if isinstance(line, dict):
            from_id = line.get("from")
            to_id = line.get("to")
            if isinstance(from_id, str) and isinstance(to_id, str) and from_id in node_by_id and to_id in node_by_id:
                parent_to_children.setdefault(from_id, []).append(node_by_id[to_id])

    for parent_id, children in parent_to_children.items():
        if len(children) < 4:
            continue
        children_sorted = sorted(children, key=lambda node: (float(node["x"]), float(node["y"])))
        x_values = [float(node["x"]) for node in children_sorted]
        y_values = [float(node["y"]) for node in children_sorted]
        if max(x_values) - min(x_values) <= 100:
            gaps = [
                y_values[i + 1] - y_values[i]
                for i in range(len(y_values) - 1)
            ]
            if gaps and min(gaps) < MIN_SIBLING_Y_GAP:
                errors.append(
                    f"父节点 `{parent_id}` 的子节点过度挤在同一竖列，需拆分分区或增加中间分组节点"
                )

    line_segments: list[tuple[str, str, str, tuple[float, float], tuple[float, float]]] = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        line_id = line.get("id")
        from_id = line.get("from")
        to_id = line.get("to")
        if (
            isinstance(line_id, str)
            and isinstance(from_id, str)
            and isinstance(to_id, str)
            and from_id in node_by_id
            and to_id in node_by_id
        ):
            line_segments.append(
                (line_id, from_id, to_id, center(node_by_id[from_id]), center(node_by_id[to_id]))
            )

    for index, (left_line_id, left_from, left_to, left_start, left_end) in enumerate(line_segments):
        left_nodes = {left_from, left_to}
        for right_line_id, right_from, right_to, right_start, right_end in line_segments[index + 1:]:
            if left_nodes & {right_from, right_to}:
                continue
            if segments_intersect(left_start, left_end, right_start, right_end):
                errors.append(f"连线 `{left_line_id}` 与 `{right_line_id}` 存在明显交叉")

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
