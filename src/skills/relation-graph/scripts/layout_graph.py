#!/usr/bin/env python3
"""Apply layout rules to a relation graph request JSON file."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

ALLOWED_DATA_TYPES = {2, 3, 5, 6}
DEFAULT_MIN_NODE_GAP = 20
DEFAULT_SEARCH_STEP = 20
DEFAULT_SEARCH_RADIUS = 1600
DEFAULT_STEP_VERTICAL_GAP = 60
DEFAULT_ENUM_HORIZONTAL_GAP = 120
DEFAULT_ENUM_VERTICAL_GAP = 80
DEFAULT_CASE_OUTER_GAP = 120

SUPPORTED_MODES = {"create", "incremental"}
MIN_NODE_GAP = 20
CANONICAL_COLORS = {"#FF0000", "#00B0F0", "#00B050", "#000000"}
CONTROL_REQUEST_FIELDS = {
    "mode",
    "layout",
    "layoutOptions",
    "preserveNodeIds",
    "targetNodeIds",
}
REQUIRED_NODE_FIXED_FIELDS = (
    "type",
    "isShow",
    "isHide",
    "expanded",
    "selected",
    "dragging",
    "styleClass",
    "className",
    "nodeShape",
    "borderWidth",
    "borderColor",
    "fontColor",
    "fontFamily",
    "fontSize",
    "fontBold",
    "fontItalic",
    "fontUnderline",
    "textHorizontalAlign",
    "textVerticalAlign",
    "color",
    "opacity",
    "fixed",
    "Fx",
    "Fy",
    "offset_x",
    "offset_y",
    "disableDrag",
    "singleNode",
    "invisiable",
    "zIndex",
)
REQUIRED_LINE_FIXED_FIELDS = (
    "lineWidth",
    "color",
    "isHide",
    "lineShape",
    "fontBold",
    "fontItalic",
    "fontUnderline",
    "opacity",
    "arrow",
    "animation",
    "dashType",
    "disableDefaultClickEffect",
    "showStartArrow",
    "showEndArrow",
    "startMarkerId",
    "endMarkerId",
    "forDisplayOnly",
    "fromJuctionPointOffsetX",
    "fromJuctionPointOffsetY",
    "toJuctionPointOffsetX",
    "toJuctionPointOffsetY",
    "polyLineRadius",
    "hidden",
    "fromJunctionPoint",
    "toJunctionPoint",
)
COLOR_ALIASES = {
    "#ff0000": "#FF0000",
    "#00b0f0": "#00B0F0",
    "#00b050": "#00B050",
    "#000000": "#000000",
    "#548bd4": "#00B0F0",
    "#0070c0": "#00B0F0",
}


@dataclass
class NodeSize:
    """节点尺寸。"""

    width: int
    height: int

    @classmethod
    def estimate_from_text(cls, text: str, max_width: int = 200) -> "NodeSize":
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        estimated_width = chinese_chars * 14 + other_chars * 8 + 20
        width = min(max(estimated_width, 100), max_width)
        lines = max(1, math.ceil(estimated_width / max_width))
        height = 40 + (lines - 1) * 20
        return cls(width=int(width), height=int(height))


@dataclass
class Node:
    """节点对象。"""

    id: str
    text: str
    x: float = 0.0
    y: float = 0.0
    width: int = 100
    height: int = 50
    data_type: int = 2
    color: str = "#000000"
    level: int = 0
    parent_id: str | None = None
    children: list[str] = field(default_factory=list)
    frozen: bool = False


@dataclass
class Line:
    """连线对象。"""

    id: str
    from_node: str
    to_node: str
    text: str = "包含"
    line_shape: int = 1
    from_junction_point: str = "border"
    to_junction_point: str = "border"


def build_node_map(nodes: list[Node]) -> dict[str, Node]:
    return {node.id: node for node in nodes}


def attach_hierarchy(nodes: list[Node], lines: list[Line]) -> None:
    node_map = build_node_map(nodes)
    for node in nodes:
        node.children = []
        node.parent_id = None
    for line in lines:
        parent = node_map.get(line.from_node)
        child = node_map.get(line.to_node)
        if not parent or not child:
            continue
        if child.id not in parent.children:
            parent.children.append(child.id)
        if child.parent_id is None:
            child.parent_id = parent.id


def build_line_maps(lines: list[Line]) -> tuple[dict[str, list[Line]], dict[str, list[Line]]]:
    outgoing: dict[str, list[Line]] = {}
    incoming: dict[str, list[Line]] = {}
    for line in lines:
        outgoing.setdefault(line.from_node, []).append(line)
        incoming.setdefault(line.to_node, []).append(line)
    return outgoing, incoming


def find_root(nodes: list[Node], lines: list[Line], root_id: str | None = None) -> Node | None:
    if not nodes:
        return None
    node_map = build_node_map(nodes)
    attach_hierarchy(nodes, lines)
    if root_id and root_id in node_map:
        return node_map[root_id]
    for node in nodes:
        if node.parent_id is None:
            return node
    return nodes[0]


def center_x(node: Node) -> float:
    return node.x + node.width / 2


def center_y(node: Node) -> float:
    return node.y + node.height / 2


def is_step_relation(line: Line, from_node: Node, to_node: Node) -> bool:
    text = (line.text or "").strip()
    if any(keyword in text for keyword in ("后续", "下一步", "顺序", "流程链")):
        return True
    if from_node.data_type == 3 and to_node.data_type == 3:
        return abs(center_x(from_node) - center_x(to_node)) <= max(from_node.width, to_node.width) * 0.6
    return False


def _side_towards(source: Node, target: Node) -> str:
    dx = center_x(target) - center_x(source)
    dy = center_y(target) - center_y(source)
    if abs(dx) > abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def _opposite_side(side: str) -> str:
    return {
        "left": "right",
        "right": "left",
        "top": "bottom",
        "bottom": "top",
    }.get(side, "border")


def calculate_junction_points(nodes: list[Node], lines: list[Line]) -> None:
    node_map = build_node_map(nodes)
    for line in lines:
        from_node = node_map.get(line.from_node)
        to_node = node_map.get(line.to_node)
        if not from_node or not to_node:
            continue

        if is_step_relation(line, from_node, to_node):
            line.from_junction_point = "bottom"
            line.to_junction_point = "top"
            continue

        if from_node.data_type == 3 or to_node.data_type == 3:
            if center_x(from_node) <= center_x(to_node):
                line.from_junction_point = "right"
                line.to_junction_point = "left"
            else:
                line.from_junction_point = "left"
                line.to_junction_point = "right"
            continue

        if from_node.data_type == 6 or to_node.data_type == 6:
            line.from_junction_point = _side_towards(from_node, to_node)
            line.to_junction_point = _side_towards(to_node, from_node)
            continue

        side = _side_towards(from_node, to_node)
        line.from_junction_point = side
        line.to_junction_point = _opposite_side(side)


def boxes_too_close(left: Node, right: Node, gap: float = DEFAULT_MIN_NODE_GAP) -> bool:
    left_x2 = left.x + left.width
    left_y2 = left.y + left.height
    right_x2 = right.x + right.width
    right_y2 = right.y + right.height
    return not (
        left_x2 + gap <= right.x
        or right_x2 + gap <= left.x
        or left_y2 + gap <= right.y
        or right_y2 + gap <= left.y
    )


def _candidate_offsets(step: int, max_radius: int) -> list[tuple[int, int]]:
    offsets: list[tuple[int, int]] = [(0, 0)]
    for radius in range(step, max_radius + step, step):
        offsets.extend([
            (radius, 0), (0, radius), (-radius, 0), (0, -radius),
            (radius, radius), (radius, -radius), (-radius, radius), (-radius, -radius),
        ])
        for delta in range(step, radius, step):
            offsets.extend([
                (radius, delta), (radius, -delta), (-radius, delta), (-radius, -delta),
                (delta, radius), (-delta, radius), (delta, -radius), (-delta, -radius),
            ])
    return offsets


def _ordered_unique_positions(positions: list[tuple[float, float]]) -> list[tuple[float, float]]:
    ordered: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for x, y in positions:
        key = (round(x, 4), round(y, 4))
        if key in seen:
            continue
        seen.add(key)
        ordered.append((x, y))
    return ordered


def _sorted_nodes_by_y(nodes: list[Node]) -> list[Node]:
    return sorted(nodes, key=lambda item: (item.y, item.x, item.id))


def _sorted_nodes_by_x(nodes: list[Node]) -> list[Node]:
    return sorted(nodes, key=lambda item: (item.x, item.y, item.id))


def _median_gap(values: list[float], default: float) -> float:
    positive_values = [value for value in values if value > 0]
    if not positive_values:
        return default
    return float(median(positive_values))


def _step_column_candidates(node: Node, node_map: dict[str, Node], outgoing: dict[str, list[Line]], incoming: dict[str, list[Line]]) -> list[tuple[float, float]]:
    if node.data_type != 3:
        return []

    siblings: list[Node] = []
    if node.parent_id:
        parent = node_map.get(node.parent_id)
        if parent:
            siblings = [node_map[child_id] for child_id in parent.children if child_id != node.id and child_id in node_map]
    step_siblings = [item for item in siblings if item.data_type == 3]
    related_steps = list(step_siblings)

    incoming_steps = [node_map[line.from_node] for line in incoming.get(node.id, []) if line.from_node in node_map and node_map[line.from_node].data_type == 3]
    outgoing_steps = [node_map[line.to_node] for line in outgoing.get(node.id, []) if line.to_node in node_map and node_map[line.to_node].data_type == 3]

    for candidate in incoming_steps + outgoing_steps:
        if candidate.id != node.id and all(existing.id != candidate.id for existing in related_steps):
            related_steps.append(candidate)

    if not related_steps:
        return []

    axis_x = round(sum(item.x for item in related_steps) / len(related_steps))
    sorted_steps = _sorted_nodes_by_y(related_steps)
    step_gap = _median_gap(
        [sorted_steps[index + 1].y - sorted_steps[index].y for index in range(len(sorted_steps) - 1)],
        DEFAULT_STEP_VERTICAL_GAP,
    )

    candidates: list[tuple[float, float]] = []
    if incoming_steps:
        base_y = max(item.y for item in incoming_steps)
        candidates.append((axis_x, base_y + step_gap))
    if outgoing_steps:
        base_y = min(item.y for item in outgoing_steps)
        candidates.append((axis_x, base_y - step_gap))
    if step_siblings:
        base_y = max(item.y for item in step_siblings)
        candidates.append((axis_x, base_y + step_gap))
    candidates.append((axis_x, node.y))
    return _ordered_unique_positions(candidates)


def _enum_group_candidates(node: Node, node_map: dict[str, Node]) -> list[tuple[float, float]]:
    if node.data_type in {3, 5, 6} or not node.parent_id:
        return []
    parent = node_map.get(node.parent_id)
    if not parent:
        return []

    siblings = [
        node_map[child_id]
        for child_id in parent.children
        if child_id != node.id and child_id in node_map and node_map[child_id].data_type not in {3, 5, 6}
    ]
    if not siblings:
        return []

    horizontal_span = max(item.x for item in siblings) - min(item.x for item in siblings)
    vertical_span = max(item.y for item in siblings) - min(item.y for item in siblings)
    horizontal = horizontal_span >= vertical_span
    candidates: list[tuple[float, float]] = []

    if horizontal:
        ordered = _sorted_nodes_by_x(siblings)
        gaps = [ordered[index + 1].x - ordered[index].x for index in range(len(ordered) - 1)]
        spacing = _median_gap(gaps, DEFAULT_ENUM_HORIZONTAL_GAP)
        direction = 1.0
        if len(ordered) == 1:
            direction = 1.0 if ordered[0].x >= parent.x else -1.0
        elif (ordered[-1].x - parent.x) < (parent.x - ordered[0].x):
            direction = -1.0
        anchor = ordered[-1] if direction > 0 else ordered[0]
        candidates.append((anchor.x + direction * spacing, anchor.y))
        candidates.append((anchor.x + direction * spacing, node.y))
    else:
        ordered = _sorted_nodes_by_y(siblings)
        gaps = [ordered[index + 1].y - ordered[index].y for index in range(len(ordered) - 1)]
        spacing = _median_gap(gaps, DEFAULT_ENUM_VERTICAL_GAP)
        direction = 1.0
        if len(ordered) == 1:
            direction = 1.0 if ordered[0].y >= parent.y else -1.0
        elif (ordered[-1].y - parent.y) < (parent.y - ordered[0].y):
            direction = -1.0
        anchor = ordered[-1] if direction > 0 else ordered[0]
        candidates.append((anchor.x, anchor.y + direction * spacing))
        candidates.append((node.x, anchor.y + direction * spacing))

    return _ordered_unique_positions(candidates)


def _case_outer_candidates(node: Node, node_map: dict[str, Node], outgoing: dict[str, list[Line]], incoming: dict[str, list[Line]]) -> list[tuple[float, float]]:
    if node.data_type != 6:
        return []

    related_nodes: list[Node] = []
    for line in incoming.get(node.id, []):
        if line.from_node in node_map:
            related_nodes.append(node_map[line.from_node])
    for line in outgoing.get(node.id, []):
        if line.to_node in node_map:
            related_nodes.append(node_map[line.to_node])
    if not related_nodes:
        return []

    anchor = related_nodes[0]
    sibling_cases: list[Node] = []
    for child_id in anchor.children:
        sibling = node_map.get(child_id)
        if sibling and sibling.id != node.id and sibling.data_type == 6:
            sibling_cases.append(sibling)

    candidates: list[tuple[float, float]] = []
    if sibling_cases:
        dx = sum(center_x(item) - center_x(anchor) for item in sibling_cases) / len(sibling_cases)
        dy = sum(center_y(item) - center_y(anchor) for item in sibling_cases) / len(sibling_cases)
    else:
        dx = center_x(node) - center_x(anchor)
        dy = center_y(node) - center_y(anchor)

    if dx == 0 and dy == 0:
        dx = 1.0
        dy = 1.0

    if abs(dx) >= abs(dy):
        direction_x = 1.0 if dx >= 0 else -1.0
        base_x = max((item.x for item in sibling_cases), default=node.x) if direction_x > 0 else min((item.x for item in sibling_cases), default=node.x)
        anchor_x = max(base_x, anchor.x) if direction_x > 0 else min(base_x, anchor.x)
        candidates.append((anchor_x + direction_x * DEFAULT_CASE_OUTER_GAP, node.y))
        candidates.append((anchor_x + direction_x * DEFAULT_CASE_OUTER_GAP, anchor.y + dy))
    else:
        direction_y = 1.0 if dy >= 0 else -1.0
        base_y = max((item.y for item in sibling_cases), default=node.y) if direction_y > 0 else min((item.y for item in sibling_cases), default=node.y)
        anchor_y = max(base_y, anchor.y) if direction_y > 0 else min(base_y, anchor.y)
        candidates.append((node.x, anchor_y + direction_y * DEFAULT_CASE_OUTER_GAP))
        candidates.append((anchor.x + dx, anchor_y + direction_y * DEFAULT_CASE_OUTER_GAP))

    candidates.append((node.x, node.y))
    return _ordered_unique_positions(candidates)


def _strategy_edge_candidates(node: Node, node_map: dict[str, Node], outgoing: dict[str, list[Line]], incoming: dict[str, list[Line]]) -> list[tuple[float, float]]:
    if node.data_type != 5:
        return []
    related_nodes: list[Node] = []
    for line in incoming.get(node.id, []):
        if line.from_node in node_map:
            related_nodes.append(node_map[line.from_node])
    for line in outgoing.get(node.id, []):
        if line.to_node in node_map:
            related_nodes.append(node_map[line.to_node])
    if not related_nodes:
        return []

    anchor = related_nodes[0]
    dx = center_x(node) - center_x(anchor)
    dy = center_y(node) - center_y(anchor)
    if dx == 0 and dy == 0:
        dx = -1.0
    if abs(dx) >= abs(dy):
        direction_x = 1.0 if dx >= 0 else -1.0
        return _ordered_unique_positions([
            (anchor.x + direction_x * DEFAULT_CASE_OUTER_GAP, node.y),
            (node.x, node.y),
        ])
    direction_y = 1.0 if dy >= 0 else -1.0
    return _ordered_unique_positions([
        (node.x, anchor.y + direction_y * DEFAULT_CASE_OUTER_GAP),
        (node.x, node.y),
    ])


def suggest_semantic_positions(nodes: list[Node], lines: list[Line], movable_node_ids: list[str]) -> dict[str, list[tuple[float, float]]]:
    node_map = build_node_map(nodes)
    outgoing, incoming = build_line_maps(lines)
    suggestions: dict[str, list[tuple[float, float]]] = {}
    movable_set = set(movable_node_ids)

    for node in nodes:
        if node.id not in movable_set:
            continue
        candidates = (
            _step_column_candidates(node, node_map, outgoing, incoming)
            or _enum_group_candidates(node, node_map)
            or _case_outer_candidates(node, node_map, outgoing, incoming)
            or _strategy_edge_candidates(node, node_map, outgoing, incoming)
            or [(node.x, node.y)]
        )
        suggestions[node.id] = _ordered_unique_positions(candidates)
    return suggestions


def find_non_overlapping_position(
    node: Node,
    occupied_nodes: list[Node],
    *,
    preferred_positions: list[tuple[float, float]] | None = None,
    gap: int = DEFAULT_MIN_NODE_GAP,
    step: int = DEFAULT_SEARCH_STEP,
    max_radius: int = DEFAULT_SEARCH_RADIUS,
) -> tuple[float, float, bool]:
    preferred_origins = list(preferred_positions or [(node.x, node.y)])
    for preferred_x, preferred_y in preferred_origins:
        for dx, dy in _candidate_offsets(step, max_radius):
            candidate_x = preferred_x + dx
            candidate_y = preferred_y + dy
            candidate = Node(
                id=node.id,
                text=node.text,
                x=candidate_x,
                y=candidate_y,
                width=node.width,
                height=node.height,
                data_type=node.data_type,
                color=node.color,
            )
            if any(boxes_too_close(candidate, other, gap) for other in occupied_nodes if other.id != node.id):
                continue
            adjusted = not (math.isclose(candidate_x, node.x) and math.isclose(candidate_y, node.y))
            return candidate_x, candidate_y, adjusted
    return node.x, node.y, False


def resolve_node_positions(
    nodes: list[Node],
    lines: list[Line],
    *,
    movable_node_ids: list[str],
    gap: int = DEFAULT_MIN_NODE_GAP,
    step: int = DEFAULT_SEARCH_STEP,
    max_radius: int = DEFAULT_SEARCH_RADIUS,
) -> list[str]:
    movable_set = set(movable_node_ids)
    occupied: list[Node] = []
    adjusted_ids: list[str] = []
    semantic_positions = suggest_semantic_positions(nodes, lines, movable_node_ids)

    for node in nodes:
        if node.id not in movable_set:
            occupied.append(node)

    for node in nodes:
        if node.id not in movable_set:
            continue
        preferred_positions = semantic_positions.get(node.id, [(node.x, node.y)])
        new_x, new_y, adjusted = find_non_overlapping_position(
            node,
            occupied,
            preferred_positions=preferred_positions,
            gap=gap,
            step=step,
            max_radius=max_radius,
        )
        node.x = new_x
        node.y = new_y
        occupied.append(node)
        if adjusted:
            adjusted_ids.append(node.id)

    return adjusted_ids


def apply_semantic_fixed_layout(
    nodes: list[Node],
    lines: list[Line],
    *,
    movable_node_ids: list[str],
    root_id: str | None = None,
    min_node_gap: int = DEFAULT_MIN_NODE_GAP,
) -> dict[str, Any]:
    attach_hierarchy(nodes, lines)
    root = find_root(nodes, lines, root_id)
    adjusted_ids = resolve_node_positions(nodes, lines, movable_node_ids=movable_node_ids, gap=min_node_gap)
    calculate_junction_points(nodes, lines)
    return {
        "rootId": root.id if root else None,
        "adjustedNodeIds": adjusted_ids,
        "nodeCount": len(nodes),
        "lineCount": len(lines),
    }


class RequestError(ValueError):
    """Raised when the layout request is invalid."""


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: Any, pretty: bool) -> None:
    with path.open("w", encoding="utf-8") as handle:
        if pretty:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        else:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply layout rules to relation graph request JSON.")
    parser.add_argument("request", help="Path to layout request JSON.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write layout result JSON. Must be inside an `output` directory.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON.")
    return parser


def ensure_object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RequestError(f"`{field_name}` 必须是对象")
    return value


def ensure_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise RequestError(f"`{field_name}` 必须是数组")
    return value


def require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequestError(f"`{field_name}` 必须是非空字符串")
    return value


def optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return require_string(value, field_name)


def normalize_number(value: Any, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        raise RequestError(f"`{field_name}` 必须是数字")
    return float(value)


def ensure_output_dir(path: Path) -> Path:
    normalized = path.resolve()
    if "output" not in normalized.parts:
        raise RequestError("输出 JSON 必须写入 `output` 目录下")
    return normalized


def validate_unique_ids(items: list[dict[str, Any]], field_name: str) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items):
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise RequestError(f"`{field_name}[{index}].id` 必须是非空字符串")
        if item_id in seen:
            raise RequestError(f"`{field_name}` 中存在重复 id: {item_id}")
        seen.add(item_id)


def normalize_color(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "#000000"
    normalized = COLOR_ALIASES.get(value.strip(), COLOR_ALIASES.get(value.strip().lower()))
    if normalized in CANONICAL_COLORS:
        return normalized
    return "#000000"


def parse_node(node_data: dict[str, Any]) -> Node:
    node_id = require_string(node_data.get("id"), "nodes[].id")
    text = require_string(node_data.get("text"), f"nodes[{node_id}].text")

    if "x" not in node_data or "y" not in node_data:
        raise RequestError(f"节点 `{node_id}` 必须提供布局坐标 `x/y`")

    width = node_data.get("width")
    height = node_data.get("height")
    if width is None or height is None:
        estimated = NodeSize.estimate_from_text(text)
        width = estimated.width if width is None else width
        height = estimated.height if height is None else height

    data = node_data.get("data") if isinstance(node_data.get("data"), dict) else {}
    data_type = data.get("type", node_data.get("data_type", 2))
    if not isinstance(data_type, int) or data_type not in ALLOWED_DATA_TYPES:
        raise RequestError(f"节点 `{node_id}` 的 data.type 仅支持 {sorted(ALLOWED_DATA_TYPES)}")

    color = normalize_color(node_data.get("borderColor") or node_data.get("fontColor") or "#000000")

    return Node(
        id=node_id,
        text=text,
        x=normalize_number(node_data.get("x"), f"nodes[{node_id}].x"),
        y=normalize_number(node_data.get("y"), f"nodes[{node_id}].y"),
        width=int(normalize_number(width, f"nodes[{node_id}].width")),
        height=int(normalize_number(height, f"nodes[{node_id}].height")),
        data_type=data_type,
        color=color,
    )


def parse_line(line_data: dict[str, Any]) -> Line:
    line_id = require_string(line_data.get("id"), "lines[].id")
    from_node = require_string(line_data.get("from"), f"lines[{line_id}].from")
    to_node = require_string(line_data.get("to"), f"lines[{line_id}].to")
    text = require_string(line_data.get("text", "包含"), f"lines[{line_id}].text")
    line_shape = line_data.get("lineShape", 1)
    if not isinstance(line_shape, int):
        raise RequestError(f"连线 `{line_id}` 的 lineShape 必须是整数")
    return Line(
        id=line_id,
        from_node=from_node,
        to_node=to_node,
        text=text,
        line_shape=line_shape,
        from_junction_point=line_data.get("fromJunctionPoint", "border"),
        to_junction_point=line_data.get("toJunctionPoint", "border"),
    )


def merge_node_payload(source: dict[str, Any], node: Node) -> dict[str, Any]:
    payload = dict(source)
    payload["id"] = node.id
    payload["text"] = node.text
    payload["x"] = node.x
    payload["y"] = node.y
    payload["width"] = node.width
    payload["height"] = node.height
    payload["type"] = source["type"]
    payload["data"] = dict(source["data"])
    payload["data"].setdefault("type", node.data_type)
    payload["data"]["startPostion"] = {"x": node.x, "y": node.y}
    return payload


def merge_line_payload(source: dict[str, Any], line: Line) -> dict[str, Any]:
    payload = dict(source)
    payload["id"] = line.id
    payload["from"] = line.from_node
    payload["to"] = line.to_node
    payload["text"] = line.text
    payload["fromJunctionPoint"] = line.from_junction_point
    payload["toJunctionPoint"] = line.to_junction_point
    return payload


def ensure_required_fixed_fields(items: list[dict[str, Any]], field_name: str, required_fields: tuple[str, ...]) -> None:
    for index, item in enumerate(items):
        item_id = item.get("id", index)
        missing = [field for field in required_fields if field not in item]
        if missing:
            raise RequestError(
                f"`{field_name}[{item_id}]` 缺少固定字段: {', '.join(missing)}"
            )


def ensure_required_data_fields(node_dicts: list[dict[str, Any]]) -> None:
    for index, item in enumerate(node_dicts):
        node_id = item.get("id", index)
        data = item.get("data")
        if not isinstance(data, dict):
            raise RequestError(f"`nodes[{node_id}].data` 必须是对象")
        missing = [field for field in ("type", "backgroundImage", "imageFit", "startPostion") if field not in data]
        if missing:
            raise RequestError(
                f"`nodes[{node_id}].data` 缺少固定字段: {', '.join(missing)}"
            )

        start_position = data.get("startPostion")
        if not isinstance(start_position, dict):
            raise RequestError(f"`nodes[{node_id}].data.startPostion` 必须是对象")
        start_missing = [field for field in ("x", "y") if field not in start_position]
        if start_missing:
            raise RequestError(
                f"`nodes[{node_id}].data.startPostion` 缺少固定字段: {', '.join(start_missing)}"
            )


def build_request_context(request_data: dict[str, Any]) -> dict[str, Any]:
    mode = require_string(request_data.get("mode"), "mode")
    if mode not in SUPPORTED_MODES:
        raise RequestError(f"`mode` 仅支持 {sorted(SUPPORTED_MODES)}")

    requested_layout = request_data.get("layout")
    if requested_layout is not None:
        requested_layout = require_string(requested_layout, "layout")

    layout_options = request_data.get("layoutOptions")
    if layout_options is not None:
        layout_options = ensure_object(layout_options, "layoutOptions")
        if layout_options:
            raise RequestError("`layoutOptions` 已废弃，布局坐标应由 AI 直接给出")

    raw_nodes = ensure_list(request_data.get("nodes"), "nodes")
    raw_lines = ensure_list(request_data.get("lines"), "lines")
    if not raw_nodes:
        raise RequestError("`nodes` 不能为空")

    node_dicts = [ensure_object(item, f"nodes[{index}]") for index, item in enumerate(raw_nodes)]
    line_dicts = [ensure_object(item, f"lines[{index}]") for index, item in enumerate(raw_lines)]

    validate_unique_ids(node_dicts, "nodes")
    validate_unique_ids(line_dicts, "lines")
    ensure_required_fixed_fields(node_dicts, "nodes", REQUIRED_NODE_FIXED_FIELDS)
    ensure_required_data_fields(node_dicts)
    ensure_required_fixed_fields(line_dicts, "lines", REQUIRED_LINE_FIXED_FIELDS)

    nodes = [parse_node(item) for item in node_dicts]
    lines = [parse_line(item) for item in line_dicts]
    node_map = {node.id: node for node in nodes}

    for line in lines:
        if line.from_node not in node_map:
            raise RequestError(f"连线 `{line.id}` 的 from 未引用有效节点: {line.from_node}")
        if line.to_node not in node_map:
            raise RequestError(f"连线 `{line.id}` 的 to 未引用有效节点: {line.to_node}")

    root_id = optional_string(request_data.get("rootId"), "rootId")
    if root_id and root_id not in node_map:
        raise RequestError(f"`rootId` 未引用有效节点: {root_id}")

    preserve_node_ids = ensure_list(request_data.get("preserveNodeIds", []), "preserveNodeIds")
    target_node_ids = ensure_list(request_data.get("targetNodeIds", []), "targetNodeIds")
    preserve_node_ids = [require_string(item, "preserveNodeIds[]") for item in preserve_node_ids]
    target_node_ids = [require_string(item, "targetNodeIds[]") for item in target_node_ids]

    missing_preserve = [node_id for node_id in preserve_node_ids if node_id not in node_map]
    missing_target = [node_id for node_id in target_node_ids if node_id not in node_map]
    if missing_preserve:
        raise RequestError(f"`preserveNodeIds` 包含不存在的节点: {missing_preserve}")
    if missing_target:
        raise RequestError(f"`targetNodeIds` 包含不存在的节点: {missing_target}")

    overlap = sorted(set(preserve_node_ids) & set(target_node_ids))
    if overlap:
        raise RequestError(f"`preserveNodeIds` 与 `targetNodeIds` 不能重叠: {overlap}")

    if mode == "incremental":
        if not preserve_node_ids:
            raise RequestError("`mode=incremental` 时必须提供 `preserveNodeIds`")
        if not target_node_ids:
            raise RequestError("`mode=incremental` 时必须提供 `targetNodeIds`")
        for node_id in preserve_node_ids:
            node_map[node_id].frozen = True
        movable_node_ids = target_node_ids
    else:
        movable_node_ids = [node.id for node in nodes]

    return {
        "mode": mode,
        "nodes": nodes,
        "lines": lines,
        "node_map": node_map,
        "node_payload_map": {item["id"]: item for item in node_dicts},
        "line_payload_map": {item["id"]: item for item in line_dicts},
        "request_payload": dict(request_data),
        "preserve_node_ids": preserve_node_ids,
        "target_node_ids": target_node_ids,
        "movable_node_ids": movable_node_ids,
        "root_id": root_id,
    }


def run_layout(context: dict[str, Any]) -> dict[str, Any]:
    stats = apply_semantic_fixed_layout(
        context["nodes"],
        context["lines"],
        movable_node_ids=context["movable_node_ids"],
        root_id=context["root_id"],
        min_node_gap=MIN_NODE_GAP,
    )
    return {
        "nodes": context["nodes"],
        "lines": context["lines"],
        "layout_stats": stats,
    }


def build_result(context: dict[str, Any], layout_result: dict[str, Any]) -> dict[str, Any]:
    result_nodes = [merge_node_payload(context["node_payload_map"][node.id], node) for node in layout_result["nodes"]]
    result_lines = [merge_line_payload(context["line_payload_map"][line.id], line) for line in layout_result["lines"]]
    result = {
        key: value
        for key, value in context["request_payload"].items()
        if key not in CONTROL_REQUEST_FIELDS
    }
    result["rootId"] = layout_result["layout_stats"]["rootId"] or context["root_id"]
    result["nodes"] = result_nodes
    result["lines"] = result_lines
    return result


def print_success_summary(result_path: Path, result: dict[str, Any]) -> None:
    summary = {
        "status": "ok",
        "output": str(result_path),
        "rootId": result["rootId"],
        "nodeCount": len(result["nodes"]),
        "lineCount": len(result["lines"]),
    }
    print(json.dumps(summary, ensure_ascii=False))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    request_path = Path(args.request).resolve()
    output_path = ensure_output_dir(Path(args.output))

    try:
        if not request_path.is_file():
            raise RequestError(f"布局请求文件不存在: {request_path}")
        request_data = ensure_object(load_json(request_path), "request")
        context = build_request_context(request_data)
        layout_result = run_layout(context)
        result = build_result(context, layout_result)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dump_json(output_path, result, pretty=args.pretty)
        print_success_summary(output_path, result)
        return 0
    except RequestError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"布局脚本运行异常: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
