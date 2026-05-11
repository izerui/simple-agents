#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a relation graph result JSON from graph.md."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GraphError(ValueError):
    """Raised when graph.md cannot be converted into result.json."""


RESULT_FILE_PATTERN = re.compile(r"^result(?:-(\d+))?\.json$")
LAYOUT_STATE_FILENAME = "graph.layout.json"
REQUIRED_HEADERS = [
    "NodeID",
    "NodeText",
    "NodeType",
    "ParentID",
    "RelationText",
    "NodeSemantic",
]
NODE_TYPE_TO_INT = {
    "DK": 2,
    "PK": 3,
    "CS": 5,
    "FC": 6,
}
SEMANTIC_TO_COLOR = {
    "核心知识点": "#FF0000",
    "核心结构化知识框架": "#00B0F0",
    "先决知识点": "#00B050",
    "普通知识点": "#000000",
}
# 关系到连线类型的映射（移除"包含”，只保留细分类型）
RELATION_TO_LINE_TYPE = {
    "支持": 0,
    "组成": 1,
    "构成": 1,
    "是一种": 3,
    "具有属性": 4,
    "具有特征": 5,
    "定义": 6,
    "并列": 8,
    "是前提": 9,
    # 包含关系细分类型
    "条件包含": 1,
    "步骤包含": 1,
    "内容包含": 1,
    "常见问题包含": 1,
    "原因包含": 1,
    "关键点包含": 1,
    "科目包含": 1,
    "形式包含": 1,
    "要求包含": 1,
}
REVERSED_RELATIONS = {"支持", "定义", "组成"}

CHAR_WIDTH_CN = 19
CHAR_WIDTH_EN = 10
MAX_CN_CHARS_PER_LINE = 10
MAX_WIDTH = MAX_CN_CHARS_PER_LINE * CHAR_WIDTH_CN + 24
MIN_WIDTH = 90
LINE_HEIGHT = 36
PADDING = 24

DEFAULT_LEVEL_SPACING = 200
DEFAULT_SIBLING_SPACING = 30
DEFAULT_SUBTREE_SPACING = 80
DEFAULT_NODE_MARGIN = 10
CANVAS_PADDING = 600
VALID_LAYOUTS = ("auto", "compact", "balanced", "sector", "hierarchical", "dispersed")
VALID_DIRECTIONS = ("vertical", "horizontal")
ARROW_MARGIN = 40
TEXT_PADDING = 20
LAYOUT_ROOT_ID = "__layout_root__"


def split_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise GraphError("Markdown 表格行必须以 `|` 开始并以 `|` 结束")
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a relation graph result JSON from graph.md."
    )
    parser.add_argument("graph", help="Path to the markdown graph table file.")
    parser.add_argument(
        "--output",
        help=(
            "Path to the final result JSON. If omitted, defaults to /output/result.json "
            "or the next available /output/result-N.json when the base file already exists."
        ),
    )
    parser.add_argument(
        "--layout-state",
        help="Path to graph.layout.json. Defaults to graph.layout.json next to the input graph.md.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON.")
    parser.add_argument("--layout", choices=VALID_LAYOUTS, default="auto")
    parser.add_argument("--direction", choices=VALID_DIRECTIONS, default="vertical")
    parser.add_argument("--level-spacing", type=int, default=DEFAULT_LEVEL_SPACING)
    parser.add_argument("--sibling-spacing", type=int, default=DEFAULT_SIBLING_SPACING)
    parser.add_argument("--subtree-spacing", type=int, default=DEFAULT_SUBTREE_SPACING)
    parser.add_argument("--node-margin", type=int, default=DEFAULT_NODE_MARGIN)
    parser.add_argument("--max-chars", type=int, default=10)
    return parser


def next_available_result_path(output_dir: Path) -> Path:
    base_path = output_dir / "result.json"
    if not base_path.exists():
        return base_path

    used_indices = {1}
    for child in output_dir.iterdir():
        if not child.is_file():
            continue
        match = RESULT_FILE_PATTERN.match(child.name)
        if not match:
            continue
        suffix = match.group(1)
        used_indices.add(1 if suffix is None else int(suffix))

    candidate = 2
    while candidate in used_indices:
        candidate += 1
    return output_dir / f"result-{candidate}.json"


def resolve_output_path(raw_output: str | None) -> Path:
    if raw_output is None:
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        return next_available_result_path(output_dir)
    return Path(raw_output).resolve()


def dump_json_atomic(path: Path, payload: Any, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        if pretty:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        else:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def dump_layout_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def resolve_layout_state_path(graph_path: Path, raw_layout_state: str | None) -> Path:
    if raw_layout_state is not None:
        return Path(raw_layout_state).resolve()
    return graph_path.with_name(LAYOUT_STATE_FILENAME)


def read_layout_state(path: Path) -> dict[str, dict[str, int]]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GraphError(f"布局状态文件解析失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise GraphError("布局状态文件必须是对象")
    raw_nodes = payload.get("nodes", {})
    if not isinstance(raw_nodes, dict):
        raise GraphError("布局状态文件中的 nodes 必须是对象")

    state: dict[str, dict[str, int]] = {}
    for node_id, raw_layout in raw_nodes.items():
        if not isinstance(raw_layout, dict):
            continue
        try:
            state[str(node_id)] = {
                "x": int(round(float(raw_layout["x"]))),
                "y": int(round(float(raw_layout["y"]))),
                "width": int(round(float(raw_layout["width"]))),
                "height": int(round(float(raw_layout["height"]))),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise GraphError(f"布局状态节点 `{node_id}` 缺少有效的 x/y/width/height") from exc
    return state


def parse_node_semantic(value: str) -> str:
    text = value.strip()
    if text not in SEMANTIC_TO_COLOR:
        raise GraphError(f"`NodeSemantic` 仅支持 {sorted(SEMANTIC_TO_COLOR)}")
    return text


def parse_node_type(value: str) -> int:
    text = value.strip().upper()
    if text not in NODE_TYPE_TO_INT:
        raise GraphError(f"`NodeType` 仅支持 {sorted(NODE_TYPE_TO_INT)}")
    return NODE_TYPE_TO_INT[text]


def parse_table_for_build(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise GraphError(f"Markdown 表格不存在: {path}")
    lines = [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 3:
        raise GraphError("Markdown 表格内容不足，无法生成 result.json")
    headers = split_row(lines[0])
    if headers != REQUIRED_HEADERS:
        raise GraphError("Markdown 表头不符合预期，无法生成 result.json")

    rows: list[dict[str, str]] = []
    for raw_line in lines[2:]:
        if not raw_line.lstrip().startswith("|"):
            continue
        cells = split_row(raw_line)
        if len(cells) != len(headers):
            raise GraphError("Markdown 数据行列数与表头不一致，无法生成 result.json")
        rows.append(dict(zip(headers, cells)))
    return rows


def estimate_text_width(text: str) -> int:
    width = 0
    for char in text:
        if "一" <= char <= "鿿":
            width += CHAR_WIDTH_CN
        elif "＀" <= char <= "￯":
            width += CHAR_WIDTH_CN
        elif char in "0123456789":
            width += CHAR_WIDTH_EN
        elif char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            width += CHAR_WIDTH_EN * 0.8
        elif char in "abcdefghijklmnopqrstuvwxyz":
            width += CHAR_WIDTH_EN * 0.6
        else:
            width += CHAR_WIDTH_EN * 0.5
    return int(width)


def derive_dimensions(node: dict[str, Any]) -> tuple[int, int]:
    text = node.get("text", "")
    if not text:
        return MIN_WIDTH, LINE_HEIGHT

    text_width = estimate_text_width(text)
    content_width = MAX_WIDTH - PADDING

    if text_width <= content_width:
        width = max(MIN_WIDTH, text_width + PADDING)
        height = LINE_HEIGHT
    else:
        lines = math.ceil(text_width / content_width)
        width = MAX_WIDTH
        height = lines * LINE_HEIGHT

    width = int(width)
    if width % 2 == 1:
        width += 1
    height = int(height)
    if height % 2 == 1:
        height += 1
    return width, height


def get_node_dimensions(node: dict[str, Any]) -> tuple[int, int]:
    locked_width = node.get("locked_width")
    locked_height = node.get("locked_height")
    if locked_width is not None and locked_height is not None:
        return int(locked_width), int(locked_height)
    return derive_dimensions(node)


@dataclass
class LayoutParams:
    layout: str = "auto"
    direction: str = "vertical"
    max_chars: int = 10
    level_spacing: int = DEFAULT_LEVEL_SPACING
    sibling_spacing: int = DEFAULT_SIBLING_SPACING
    subtree_spacing: int = DEFAULT_SUBTREE_SPACING
    node_margin: int = DEFAULT_NODE_MARGIN


class LayoutContext:
    def __init__(self, nodes: list[dict[str, Any]], root_id: str, params: LayoutParams):
        self.nodes = nodes
        self.root_id = root_id
        self.params = params
        self.positions: dict[str, tuple[float, float]] = {}
        self.children_map: dict[str, list[dict[str, Any]]] = {}
        self.parent_map: dict[str, str] = {}
        self.node_map: dict[str, dict[str, Any]] = {}
        self.node_levels: dict[str, int] = {}
        self.node_dims: dict[str, tuple[int, int]] = {}
        self.subtree_sizes: dict[str, int] = {}
        self.bbox_cache: dict[str, tuple[float, float]] = {}

    @staticmethod
    def build(nodes: list[dict[str, Any]], root_id: str, params: LayoutParams) -> "LayoutContext":
        ctx = LayoutContext(nodes, root_id, params)

        for node in nodes:
            nid = node["id"]
            ctx.node_map[nid] = node
            ctx.node_dims[nid] = get_node_dimensions(node)
            pid = node.get("parent")
            if pid:
                ctx.parent_map[nid] = pid
                ctx.children_map.setdefault(pid, []).append(node)

        ctx.node_levels[root_id] = 0
        queue = deque([root_id])
        while queue:
            nid = queue.popleft()
            for child in ctx.children_map.get(nid, []):
                cid = child["id"]
                if cid not in ctx.node_levels:
                    ctx.node_levels[cid] = ctx.node_levels[nid] + 1
                    queue.append(cid)

        def calc_size(nid: str) -> int:
            children = ctx.children_map.get(nid, [])
            size = 1 + sum(calc_size(child["id"]) for child in children)
            ctx.subtree_sizes[nid] = size
            return size

        calc_size(root_id)
        return ctx

    @property
    def max_depth(self) -> int:
        return max(self.node_levels.values()) if self.node_levels else 0

    @property
    def total_nodes(self) -> int:
        return len(self.nodes)

    @property
    def l1_count(self) -> int:
        return len(self.children_map.get(self.root_id, []))

    @property
    def max_fanout(self) -> int:
        if not self.children_map:
            return 0
        return max(len(children) for children in self.children_map.values())


def adjust_spacing_for_text(nodes: list[dict[str, Any]], params: LayoutParams) -> None:
    max_text_w = 0
    for node in nodes:
        relation = node.get("relation", "")
        if relation:
            max_text_w = max(max_text_w, estimate_text_width(relation))

    if max_text_w == 0:
        return

    max_half_h = 0.0
    max_half_w = 0.0
    for node in nodes:
        width, height = get_node_dimensions(node)
        max_half_h = max(max_half_h, height / 2)
        max_half_w = max(max_half_w, width / 2)

    min_line = max_text_w + TEXT_PADDING * 2
    if params.direction == "horizontal":
        needed = min_line + max_half_w * 2 + ARROW_MARGIN * 2
    else:
        needed = min_line + max_half_h * 2 + ARROW_MARGIN * 2
    if params.level_spacing < needed:
        params.level_spacing = int(needed)


def select_strategy(ctx: LayoutContext, params: LayoutParams) -> str:
    if params.layout != "auto":
        return params.layout
    if ctx.total_nodes < 15 and ctx.l1_count <= 3:
        return "compact"
    if ctx.l1_count > 15:
        return "sector"
    if ctx.max_depth >= 6 and ctx.total_nodes > 300:
        return "hierarchical"
    return "dispersed"


def compute_subtree_bboxes(ctx: LayoutContext) -> None:
    cache = ctx.bbox_cache
    margin = ctx.params.node_margin
    horizontal = ctx.params.direction == "horizontal"

    def compute(nid: str) -> tuple[float, float]:
        if nid in cache:
            return cache[nid]

        children = ctx.children_map.get(nid, [])
        width, height = ctx.node_dims[nid]
        inflated_w = width + 2 * margin
        inflated_h = height + 2 * margin

        if not children:
            cache[nid] = (inflated_w, inflated_h)
            return inflated_w, inflated_h

        child_boxes = [compute(child["id"]) for child in children]
        gap = ctx.params.sibling_spacing

        if horizontal:
            children_total_h = sum(box_h for _, box_h in child_boxes) + gap * (len(children) - 1)
            max_child_w = max(box_w for box_w, _ in child_boxes)
            total_w = inflated_w + ctx.params.level_spacing + max_child_w
            total_h = max(inflated_h, children_total_h)
        else:
            children_total_w = sum(box_w for box_w, _ in child_boxes) + gap * (len(children) - 1)
            max_child_h = max(box_h for _, box_h in child_boxes)
            total_w = max(inflated_w, children_total_w)
            total_h = inflated_h + ctx.params.level_spacing + max_child_h

        cache[nid] = (total_w, total_h)
        return total_w, total_h

    for node in ctx.nodes:
        compute(node["id"])


def layout_subtree(node_id: str, x: float, y: float, ctx: LayoutContext) -> None:
    ctx.positions[node_id] = (x, y)
    children = ctx.children_map.get(node_id, [])
    if not children:
        return

    horizontal = ctx.params.direction == "horizontal"
    gap = ctx.params.sibling_spacing
    node_w, node_h = ctx.node_dims[node_id]

    if horizontal:
        child_heights = [ctx.bbox_cache[child["id"]][1] for child in children]
        total_h = sum(child_heights) + gap * (len(children) - 1)
        start_y = y + node_h / 2 - total_h / 2
        child_x = x + node_w + ctx.params.level_spacing
        for index, child in enumerate(children):
            child_h = ctx.node_dims[child["id"]][1]
            child_y = start_y + child_heights[index] / 2 - child_h / 2
            layout_subtree(child["id"], child_x, child_y, ctx)
            start_y += child_heights[index] + gap
        return

    child_widths = [ctx.bbox_cache[child["id"]][0] for child in children]
    total_w = sum(child_widths) + gap * (len(children) - 1)
    start_x = x + node_w / 2 - total_w / 2
    child_y = y + node_h + ctx.params.level_spacing
    for index, child in enumerate(children):
        child_w = ctx.node_dims[child["id"]][0]
        child_x = start_x + child_widths[index] / 2 - child_w / 2
        layout_subtree(child["id"], child_x, child_y, ctx)
        start_x += child_widths[index] + gap


def layout_subtree_into(
    node_id: str,
    x: float,
    y: float,
    ctx: LayoutContext,
    positions: dict[str, tuple[float, float]],
) -> None:
    positions[node_id] = (x, y)
    children = ctx.children_map.get(node_id, [])
    if not children:
        return

    horizontal = ctx.params.direction == "horizontal"
    gap = ctx.params.sibling_spacing
    node_w, node_h = ctx.node_dims[node_id]

    if horizontal:
        child_heights = [ctx.bbox_cache[child["id"]][1] for child in children]
        total_h = sum(child_heights) + gap * (len(children) - 1)
        start_y = y + node_h / 2 - total_h / 2
        child_x = x + node_w + ctx.params.level_spacing
        for index, child in enumerate(children):
            child_h = ctx.node_dims[child["id"]][1]
            child_y = start_y + child_heights[index] / 2 - child_h / 2
            layout_subtree_into(child["id"], child_x, child_y, ctx, positions)
            start_y += child_heights[index] + gap
        return

    child_widths = [ctx.bbox_cache[child["id"]][0] for child in children]
    total_w = sum(child_widths) + gap * (len(children) - 1)
    start_x = x + node_w / 2 - total_w / 2
    child_y = y + node_h + ctx.params.level_spacing
    for index, child in enumerate(children):
        child_w = ctx.node_dims[child["id"]][0]
        child_x = start_x + child_widths[index] / 2 - child_w / 2
        layout_subtree_into(child["id"], child_x, child_y, ctx, positions)
        start_x += child_widths[index] + gap


def compute_positions_bbox(
    positions: dict[str, tuple[float, float]],
    ctx: LayoutContext,
    include_margin: bool = True,
) -> tuple[float, float, float, float]:
    margin = ctx.params.node_margin if include_margin else 0
    left = math.inf
    top = math.inf
    right = -math.inf
    bottom = -math.inf

    for node_id, (x, y) in positions.items():
        width, height = ctx.node_dims[node_id]
        left = min(left, x - margin)
        top = min(top, y - margin)
        right = max(right, x + width + margin)
        bottom = max(bottom, y + height + margin)

    if left == math.inf:
        return 0.0, 0.0, 0.0, 0.0
    return left, top, right, bottom


def convert_positions_to_top_left(ctx: LayoutContext) -> None:
    for node_id, (x, y) in list(ctx.positions.items()):
        width, height = ctx.node_dims[node_id]
        ctx.positions[node_id] = (x - width / 2, y - height / 2)


def detect_collisions(ctx: LayoutContext) -> list[tuple[str, str]]:
    margin = ctx.params.node_margin
    ids = list(ctx.positions.keys())
    collisions: list[tuple[str, str]] = []

    for index in range(len(ids)):
        x1, y1 = ctx.positions[ids[index]]
        w1, h1 = ctx.node_dims[ids[index]]
        l1, r1 = x1 - margin, x1 + w1 + margin
        t1, b1 = y1 - margin, y1 + h1 + margin
        for inner in range(index + 1, len(ids)):
            x2, y2 = ctx.positions[ids[inner]]
            w2, h2 = ctx.node_dims[ids[inner]]
            l2, r2 = x2 - margin, x2 + w2 + margin
            t2, b2 = y2 - margin, y2 + h2 + margin
            if not (r1 < l2 or l1 > r2 or b1 < t2 or t1 > b2):
                collisions.append((ids[index], ids[inner]))
    return collisions


def resolve_collisions(
    ctx: LayoutContext,
    fixed_ids: set[str] | None = None,
    max_rounds: int = 50,
) -> None:
    fixed_ids = fixed_ids or set()
    for _ in range(max_rounds):
        collisions = detect_collisions(ctx)
        if not collisions:
            return
        for nid1, nid2 in collisions:
            x1, y1 = ctx.positions[nid1]
            x2, y2 = ctx.positions[nid2]
            w1, h1 = ctx.node_dims[nid1]
            w2, h2 = ctx.node_dims[nid2]
            margin = ctx.params.node_margin

            overlap_x = min(x1 + w1 + margin, x2 + w2 + margin) - max(x1 - margin, x2 - margin)
            overlap_y = min(y1 + h1 + margin, y2 + h2 + margin) - max(y1 - margin, y2 - margin)
            dx = x2 - x1
            dy = y2 - y1
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.1:
                dx, dy = 1.0, 0.0

            nid1_fixed = nid1 in fixed_ids
            nid2_fixed = nid2 in fixed_ids
            if nid1_fixed and nid2_fixed:
                continue
            if overlap_x <= overlap_y:
                push = overlap_x + 5 if nid1_fixed or nid2_fixed else (overlap_x / 2 + 5)
                direction = 1 if dx >= 0 else -1
                if nid1_fixed:
                    ctx.positions[nid2] = (x2 + push * direction, y2)
                elif nid2_fixed:
                    ctx.positions[nid1] = (x1 - push * direction, y1)
                else:
                    ctx.positions[nid1] = (x1 - push * direction, y1)
                    ctx.positions[nid2] = (x2 + push * direction, y2)
            else:
                push = overlap_y + 5 if nid1_fixed or nid2_fixed else (overlap_y / 2 + 5)
                direction = 1 if dy >= 0 else -1
                if nid1_fixed:
                    ctx.positions[nid2] = (x2, y2 + push * direction)
                elif nid2_fixed:
                    ctx.positions[nid1] = (x1, y1 - push * direction)
                else:
                    ctx.positions[nid1] = (x1, y1 - push * direction)
                    ctx.positions[nid2] = (x2, y2 + push * direction)


def normalize_coordinates(ctx: LayoutContext) -> None:
    if not ctx.positions:
        return
    min_x = min(x for x, _ in ctx.positions.values())
    min_y = min(y for _, y in ctx.positions.values())
    offset_x = -min_x + CANVAS_PADDING if min_x < CANVAS_PADDING else 0
    offset_y = -min_y + CANVAS_PADDING if min_y < CANVAS_PADDING else 0
    if offset_x or offset_y:
        for node_id in list(ctx.positions):
            x, y = ctx.positions[node_id]
            ctx.positions[node_id] = (x + offset_x, y + offset_y)


def apply_locked_layout(
    positions: dict[str, tuple[int, int]],
    nodes: list[dict[str, Any]],
    fixed_ids: set[str],
) -> tuple[dict[str, tuple[int, int]], tuple[float, float] | None]:
    anchor_delta: tuple[float, float] | None = None
    for node in nodes:
        node_id = node["id"]
        if node_id not in fixed_ids or "locked_position" not in node or node_id not in positions:
            continue
        locked_position = node["locked_position"]
        current_position = positions[node_id]
        anchor_delta = (
            locked_position[0] - current_position[0],
            locked_position[1] - current_position[1],
        )
        break

    shifted_positions = dict(positions)
    if anchor_delta is not None:
        dx, dy = anchor_delta
        shifted_positions = {
            node_id: (int(round(x + dx)), int(round(y + dy)))
            for node_id, (x, y) in shifted_positions.items()
        }

    for node in nodes:
        node_id = node["id"]
        if node_id in fixed_ids and "locked_position" in node:
            shifted_positions[node_id] = node["locked_position"]
    return shifted_positions, anchor_delta


def layout_compact(ctx: LayoutContext) -> None:
    compute_subtree_bboxes(ctx)
    layout_subtree(ctx.root_id, 0, 0, ctx)


def layout_balanced(ctx: LayoutContext) -> None:
    compute_subtree_bboxes(ctx)
    ctx.positions[ctx.root_id] = (0, 0)
    l1_children = ctx.children_map.get(ctx.root_id, [])
    if not l1_children:
        return

    subtree_local: dict[str, dict[str, tuple[float, float]]] = {}
    subtree_bboxes: dict[str, tuple[float, float, float, float]] = {}
    for child in l1_children:
        cid = child["id"]
        local: dict[str, tuple[float, float]] = {}
        layout_subtree_into(cid, 0, 0, ctx, local)
        subtree_local[cid] = local
        subtree_bboxes[cid] = compute_positions_bbox(local, ctx)

    if len(l1_children) == 1:
        cid = l1_children[0]["id"]
        bbox = subtree_bboxes[cid]
        root_w = ctx.node_dims[ctx.root_id][0]
        offset_x = root_w + ctx.params.subtree_spacing - bbox[0]
        ctx.positions[cid] = (offset_x, 0)
        for nid, (lx, ly) in subtree_local[cid].items():
            if nid != cid:
                ctx.positions[nid] = (offset_x + lx, ly)
        return

    total_weight = sum(ctx.subtree_sizes[child["id"]] for child in l1_children)
    sectors = []
    angle = -math.pi / 2
    for child in l1_children:
        weight = ctx.subtree_sizes[child["id"]]
        sector = 2 * math.pi * weight / total_weight
        sectors.append((child, angle, angle + sector))
        angle += sector

    root_w, root_h = ctx.node_dims[ctx.root_id]
    min_radius = max(root_w, root_h) / 2 + ctx.params.subtree_spacing
    for index in range(len(sectors)):
        next_index = (index + 1) % len(sectors)
        _, _, end_i = sectors[index]
        next_child, start_j, _ = sectors[next_index]
        delta_angle = start_j - end_i if next_index != 0 else (start_j - end_i) % (2 * math.pi)
        if delta_angle < 0.01:
            delta_angle = 0.01
        bbox_i = subtree_bboxes[sectors[index][0]["id"]]
        bbox_j = subtree_bboxes[next_child["id"]]
        bw_i = max(bbox_i[2] - bbox_i[0], bbox_i[3] - bbox_i[1])
        bw_j = max(bbox_j[2] - bbox_j[0], bbox_j[3] - bbox_j[1])
        needed_r = (bw_i + bw_j + 2 * ctx.params.node_margin) / (4 * math.sin(delta_angle / 2))
        min_radius = max(min_radius, needed_r)

    radius = min_radius
    for child, start_a, end_a in sectors:
        cid = child["id"]
        mid_angle = start_a + (end_a - start_a) / 2
        offset_x = radius * math.cos(mid_angle)
        offset_y = radius * math.sin(mid_angle)
        ctx.positions[cid] = (offset_x, offset_y)
        for nid, (lx, ly) in subtree_local[cid].items():
            if nid != cid:
                ctx.positions[nid] = (offset_x + lx, offset_y + ly)


def layout_sector(ctx: LayoutContext) -> None:
    compute_subtree_bboxes(ctx)
    ctx.positions[ctx.root_id] = (0, 0)
    l1_children = ctx.children_map.get(ctx.root_id, [])
    if not l1_children:
        return

    subtree_info = []
    for index, child in enumerate(l1_children):
        cid = child["id"]
        bbox_w, bbox_h = ctx.bbox_cache[cid]
        subtree_info.append({"id": cid, "idx": index, "bbox_w": bbox_w, "bbox_h": bbox_h})

    max_subtree_w = max(info["bbox_w"] for info in subtree_info)
    target_row_w = max(2000, max_subtree_w * 4)
    rows: list[list[dict[str, Any]]] = []
    current_row: list[dict[str, Any]] = []
    current_w = 0.0
    for info in subtree_info:
        if current_row and current_w + info["bbox_w"] + ctx.params.subtree_spacing > target_row_w:
            rows.append(current_row)
            current_row = [info]
            current_w = info["bbox_w"]
        else:
            current_row.append(info)
            current_w += info["bbox_w"] + ctx.params.subtree_spacing
    if current_row:
        rows.append(current_row)

    root_h = ctx.node_dims[ctx.root_id][1]
    current_y = root_h + ctx.params.level_spacing
    for row in rows:
        row_w = sum(info["bbox_w"] for info in row) + ctx.params.subtree_spacing * (len(row) - 1)
        start_x = -row_w / 2
        max_h = max(info["bbox_h"] for info in row)
        col_x = start_x
        for info in row:
            child_w = ctx.node_dims[info["id"]][0]
            child_x = col_x + info["bbox_w"] / 2 - child_w / 2
            layout_subtree(info["id"], child_x, current_y, ctx)
            col_x += info["bbox_w"] + ctx.params.subtree_spacing
        current_y += max_h + ctx.params.subtree_spacing


def layout_hierarchical(ctx: LayoutContext) -> None:
    compute_subtree_bboxes(ctx)
    ctx.positions[ctx.root_id] = (0, 0)
    l1_children = ctx.children_map.get(ctx.root_id, [])
    if not l1_children:
        return

    subtree_info = []
    for child in l1_children:
        cid = child["id"]
        bbox_w, bbox_h = ctx.bbox_cache[cid]
        subtree_info.append({"id": cid, "bbox_w": bbox_w, "bbox_h": bbox_h})

    gap = ctx.params.subtree_spacing
    total_w = sum(info["bbox_w"] for info in subtree_info) + gap * (len(subtree_info) - 1)
    start_x = -total_w / 2
    root_h = ctx.node_dims[ctx.root_id][1]
    y = root_h + ctx.params.level_spacing
    col_x = start_x
    for info in subtree_info:
        child_w = ctx.node_dims[info["id"]][0]
        child_x = col_x + info["bbox_w"] / 2 - child_w / 2
        layout_subtree(info["id"], child_x, y, ctx)
        col_x += info["bbox_w"] + gap


def layout_subtree_horizontal(node_id: str, x: float, y: float, ctx: LayoutContext) -> None:
    ctx.positions[node_id] = (x, y)
    children = ctx.children_map.get(node_id, [])
    if not children:
        return

    gap = ctx.params.sibling_spacing
    node_w, node_h = ctx.node_dims[node_id]
    child_heights = [ctx.bbox_cache[child["id"]][1] for child in children]
    total_h = sum(child_heights) + gap * (len(children) - 1)
    start_y = y + node_h / 2 - total_h / 2
    child_x = x + node_w + ctx.params.level_spacing
    for index, child in enumerate(children):
        child_h = ctx.node_dims[child["id"]][1]
        child_y = start_y + child_heights[index] / 2 - child_h / 2
        layout_subtree_horizontal(child["id"], child_x, child_y, ctx)
        start_y += child_heights[index] + gap


def layout_subtree_horizontal_into(
    node_id: str,
    x: float,
    y: float,
    ctx: LayoutContext,
    positions: dict[str, tuple[float, float]],
) -> None:
    positions[node_id] = (x, y)
    children = ctx.children_map.get(node_id, [])
    if not children:
        return

    gap = ctx.params.sibling_spacing
    node_w, node_h = ctx.node_dims[node_id]
    child_heights = [ctx.bbox_cache[child["id"]][1] for child in children]
    total_h = sum(child_heights) + gap * (len(children) - 1)
    start_y = y + node_h / 2 - total_h / 2
    child_x = x + node_w + ctx.params.level_spacing
    for index, child in enumerate(children):
        child_h = ctx.node_dims[child["id"]][1]
        child_y = start_y + child_heights[index] / 2 - child_h / 2
        layout_subtree_horizontal_into(child["id"], child_x, child_y, ctx, positions)
        start_y += child_heights[index] + gap


def layout_dispersed(ctx: LayoutContext) -> None:
    saved_dir = ctx.params.direction
    ctx.params.direction = "horizontal"
    compute_subtree_bboxes(ctx)
    ctx.params.direction = saved_dir
    ctx.positions[ctx.root_id] = (0, 0)

    l1_children = ctx.children_map.get(ctx.root_id, [])
    if not l1_children:
        return

    root_w, _ = ctx.node_dims[ctx.root_id]
    gap = ctx.params.subtree_spacing
    right_count = math.ceil(len(l1_children) / 2)
    right_group = l1_children[:right_count]
    left_group = l1_children[right_count:]

    right_infos = []
    for child in right_group:
        cid = child["id"]
        bbox_w, bbox_h = ctx.bbox_cache[cid]
        right_infos.append({"id": cid, "bbox_w": bbox_w, "bbox_h": bbox_h})

    right_total_h = sum(info["bbox_h"] for info in right_infos) + gap * (len(right_infos) - 1)
    right_start_y = -right_total_h / 2
    right_x = root_w + ctx.params.level_spacing
    current_y = right_start_y
    for info in right_infos:
        child_h = ctx.node_dims[info["id"]][1]
        child_y = current_y + info["bbox_h"] / 2 - child_h / 2
        layout_subtree_horizontal(info["id"], right_x, child_y, ctx)
        current_y += info["bbox_h"] + gap

    if not left_group:
        return

    left_infos = []
    for child in left_group:
        cid = child["id"]
        bbox_w, bbox_h = ctx.bbox_cache[cid]
        left_infos.append({"id": cid, "bbox_w": bbox_w, "bbox_h": bbox_h})

    left_total_h = sum(info["bbox_h"] for info in left_infos) + gap * (len(left_infos) - 1)
    left_start_y = -left_total_h / 2
    temp_positions: dict[str, tuple[float, float]] = {}
    current_y = left_start_y
    for info in left_infos:
        child_h = ctx.node_dims[info["id"]][1]
        child_y = current_y + info["bbox_h"] / 2 - child_h / 2
        layout_subtree_horizontal_into(info["id"], 0, child_y, ctx, temp_positions)
        current_y += info["bbox_h"] + gap

    min_x_old = min(position[0] for position in temp_positions.values())
    offset_x = -(root_w / 2 + ctx.params.level_spacing) + min_x_old
    for nid, (px, py) in temp_positions.items():
        ctx.positions[nid] = (-px + offset_x, py)


def auto_layout(
    nodes: list[dict[str, Any]],
    root_id: str,
    params: LayoutParams | None = None,
    fixed_ids: set[str] | None = None,
) -> tuple[dict[str, tuple[int, int]], str]:
    params = params or LayoutParams()
    ctx = LayoutContext.build(nodes, root_id, params)

    strategy = select_strategy(ctx, params)
    if strategy == "dispersed":
        saved_dir = params.direction
        params.direction = "horizontal"
        adjust_spacing_for_text(nodes, params)
        params.direction = saved_dir
    else:
        adjust_spacing_for_text(nodes, params)

    if strategy == "compact":
        layout_compact(ctx)
    elif strategy == "balanced":
        layout_balanced(ctx)
    elif strategy == "sector":
        layout_sector(ctx)
    elif strategy == "hierarchical":
        layout_hierarchical(ctx)
    else:
        layout_dispersed(ctx)

    fixed_ids = fixed_ids or set()
    if fixed_ids:
        locked_positions, _ = apply_locked_layout(
            {nid: (int(round(x)), int(round(y))) for nid, (x, y) in ctx.positions.items()},
            nodes,
            fixed_ids,
        )
        ctx.positions = {nid: (float(x), float(y)) for nid, (x, y) in locked_positions.items()}
        resolve_collisions(ctx, fixed_ids=fixed_ids)
    else:
        resolve_collisions(ctx)
        normalize_coordinates(ctx)
    return {nid: (int(round(x)), int(round(y))) for nid, (x, y) in ctx.positions.items()}, strategy


def center_x(node: dict[str, Any]) -> float:
    return float(node["x"]) + float(node["width"]) / 2


def center_y(node: dict[str, Any]) -> float:
    return float(node["y"]) + float(node["height"]) / 2


def choose_single_junction(source: dict[str, Any], target: dict[str, Any]) -> str:
    dx = center_x(target) - center_x(source)
    dy = center_y(target) - center_y(source)
    if dx == 0 and dy == 0:
        return "right"

    half_width = float(source["width"]) / 2
    half_height = float(source["height"]) / 2
    tx = float("inf") if dx == 0 else half_width / abs(dx)
    ty = float("inf") if dy == 0 else half_height / abs(dy)
    if tx < ty:
        return "right" if dx > 0 else "left"
    return "bottom" if dy > 0 else "top"


def choose_junction_points(source: dict[str, Any], target: dict[str, Any]) -> tuple[str, str]:
    return choose_single_junction(source, target), choose_single_junction(target, source)


def compose_node(
    node_id: str,
    text: str,
    data_type: int,
    x: int,
    y: int,
    width: int,
    height: int,
    border_color: str,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "text": text,
        "type": "node",
        "isShow": True,
        "isHide": False,
        "expanded": True,
        "selected": False,
        "dragging": False,
        "styleClass": "",
        "className": "",
        "nodeShape": 1,
        "borderWidth": 1,
        "borderColor": border_color,
        "fontColor": border_color,
        "fontFamily": "宋体",
        "fontSize": 12,
        "fontBold": False,
        "fontItalic": False,
        "fontUnderline": False,
        "textHorizontalAlign": "center",
        "textVerticalAlign": "middle",
        "color": "#ffffff",
        "opacity": 1,
        "fixed": True,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "Fx": 0,
        "Fy": 0,
        "offset_x": 0,
        "offset_y": 0,
        "disableDrag": False,
        "singleNode": False,
        "invisiable": False,
        "zIndex": 300,
        "data": {
            "type": data_type,
            "backgroundImage": "",
            "imageFit": "cover",
            "startPostion": {"x": x, "y": y},
        },
    }


def compose_line(parent_id: str, node_id: str, relation: str, node_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    relation_text = relation.strip()
    from_id = parent_id
    to_id = node_id
    if relation_text in REVERSED_RELATIONS:
        from_id, to_id = to_id, from_id

    source = node_map[from_id]
    target = node_map[to_id]
    from_junction, to_junction = choose_junction_points(source, target)
    return {
        "id": f"line-{uuid.uuid4().hex[:12]}",
        "type": "line",
        "text": relation_text,
        "from": from_id,
        "to": to_id,
        "lineWidth": 1,
        "color": "#000000",
        "isHide": False,
        "lineShape": 1,
        "fontSize": 10,
        "fontBold": False,
        "fontItalic": False,
        "fontUnderline": False,
        "opacity": 1,
        "arrow": "RGIns-12-arrow-000000-w5",
        "animation": 0,
        "dashType": 0,
        "disableDefaultClickEffect": False,
        "showStartArrow": False,
        "showEndArrow": True,
        "startMarkerId": "",
        "endMarkerId": "",
        "forDisplayOnly": False,
        "fromJunctionPoint": from_junction,
        "toJunctionPoint": to_junction,
        "fromJuctionPointOffsetX": 0,
        "fromJuctionPointOffsetY": 0,
        "toJuctionPointOffsetX": 0,
        "toJuctionPointOffsetY": 0,
        "polyLineRadius": 0,
        "hidden": False,
        "data": {"type": RELATION_TO_LINE_TYPE.get(relation_text, 1)},
    }


def select_primary_parent(rows: list[dict[str, str]]) -> dict[str, str]:
    primary_parent: dict[str, str] = {}
    for row in rows:
        node_id = row["NodeID"].strip()
        parent_id = row["ParentID"].strip()
        if parent_id and node_id not in primary_parent:
            primary_parent[node_id] = parent_id
    return primary_parent


def choose_component_anchors(
    order: list[str],
    primary_parent: dict[str, str],
) -> tuple[list[str], set[str]]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in order}
    child_counts: dict[str, int] = {node_id: 0 for node_id in order}
    for node_id, parent_id in primary_parent.items():
        if parent_id not in adjacency:
            continue
        adjacency[node_id].add(parent_id)
        adjacency[parent_id].add(node_id)
        child_counts[parent_id] += 1

    anchors: list[str] = []
    detached_for_layout: set[str] = set()
    visited: set[str] = set()

    for start_id in order:
        if start_id in visited:
            continue
        stack = [start_id]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(neighbor for neighbor in adjacency[current] if neighbor not in visited)

        natural_roots = [node_id for node_id in component if node_id not in primary_parent]
        if natural_roots:
            anchor = min(natural_roots, key=order.index)
        else:
            anchor = min(
                component,
                key=lambda node_id: (-child_counts.get(node_id, 0), order.index(node_id)),
            )
            detached_for_layout.add(anchor)
        anchors.append(anchor)

    return anchors, detached_for_layout


def build_layout_nodes(
    rows: list[dict[str, str]],
    layout_state: dict[str, dict[str, int]],
) -> tuple[list[dict[str, Any]], list[str], set[str]]:
    primary_parent = select_primary_parent(rows)
    node_map: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    relation_map: dict[tuple[str, str], str] = {}

    for row in rows:
        node_id = row["NodeID"].strip()
        parent_id = row["ParentID"].strip()
        relation_text = row["RelationText"].strip()
        if parent_id and relation_text:
            relation_map[(node_id, parent_id)] = relation_text
        if node_id in node_map:
            continue
        order.append(node_id)
        node: dict[str, Any] = {
            "id": node_id,
            "text": row["NodeText"].strip(),
            "type": row["NodeType"].strip().upper(),
            "semantic": parse_node_semantic(row["NodeSemantic"]),
        }
        if node_id in layout_state:
            saved = layout_state[node_id]
            node["locked_x"] = saved["x"]
            node["locked_y"] = saved["y"]
            node["locked_width"] = saved["width"]
            node["locked_height"] = saved["height"]
            node["locked_position"] = (saved["x"], saved["y"])
        node_map[node_id] = node

    anchors, detached_for_layout = choose_component_anchors(order, primary_parent)
    for node_id in order:
        parent_id = primary_parent.get(node_id)
        if not parent_id or node_id in detached_for_layout:
            continue
        node_map[node_id]["parent"] = parent_id
        node_map[node_id]["relation"] = relation_map[(node_id, parent_id)]

    roots = anchors
    nodes = [node_map[node_id] for node_id in order]
    fixed_ids = {node["id"] for node in nodes if "locked_position" in node}
    return nodes, roots, fixed_ids


def build_payload(
    rows: list[dict[str, str]],
    params: LayoutParams,
    layout_state: dict[str, dict[str, int]],
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    layout_nodes, roots, fixed_ids = build_layout_nodes(rows, layout_state)
    if not layout_nodes:
        raise GraphError("graph.md 中没有可用于生成的节点")

    root_id = roots[0] if len(roots) == 1 else LAYOUT_ROOT_ID
    layout_input = layout_nodes
    if len(roots) > 1:
        synthetic_root = {
            "id": LAYOUT_ROOT_ID,
            "text": "ROOT",
            "type": "DK",
            "semantic": "核心结构化知识框架",
        }
        layout_input = [synthetic_root] + layout_nodes
        for node in layout_nodes:
            if node["id"] in roots:
                node.setdefault("parent", LAYOUT_ROOT_ID)
                node.setdefault("relation", "并列")

    effective_fixed_ids = set(fixed_ids)
    if root_id == LAYOUT_ROOT_ID:
        effective_fixed_ids.discard(LAYOUT_ROOT_ID)
    if effective_fixed_ids == {node["id"] for node in layout_nodes}:
        effective_fixed_ids.clear()
    positions, strategy = auto_layout(layout_input, root_id, params, fixed_ids=effective_fixed_ids)
    if root_id == LAYOUT_ROOT_ID:
        positions.pop(LAYOUT_ROOT_ID, None)

    nodes = []
    new_layout_state_nodes: dict[str, dict[str, int]] = {}
    for node in layout_nodes:
        if node["id"] == LAYOUT_ROOT_ID:
            continue
        width, height = get_node_dimensions(node)
        x, y = positions.get(node["id"], (0, 0))
        x = int(round(x))
        y = int(round(y))
        new_layout_state_nodes[node["id"]] = {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
        nodes.append(
            compose_node(
                node["id"],
                node["text"],
                NODE_TYPE_TO_INT[node["type"]],
                x,
                y,
                width,
                height,
                SEMANTIC_TO_COLOR[node["semantic"]],
            )
        )

    node_map = {node["id"]: node for node in nodes}
    lines = [
        compose_line(
            row["ParentID"].strip(),
            row["NodeID"].strip(),
            row["RelationText"].strip(),
            node_map,
        )
        for row in rows
        if row["ParentID"].strip() and row["RelationText"].strip()
    ]
    payload = {
        "rootId": f"root-{uuid.uuid4().hex}",
        "datetime": int(time.time() * 1000),
        "nodes": nodes,
        "lines": lines,
    }
    return payload, strategy, {"nodes": new_layout_state_nodes}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    graph_path = Path(args.graph).resolve()
    layout_state_path = resolve_layout_state_path(graph_path, args.layout_state)
    params = LayoutParams(
        layout=args.layout,
        direction=args.direction,
        max_chars=args.max_chars,
        level_spacing=args.level_spacing,
        sibling_spacing=args.sibling_spacing,
        subtree_spacing=args.subtree_spacing,
        node_margin=args.node_margin,
    )

    try:
        output_path = resolve_output_path(args.output)
        layout_state = read_layout_state(layout_state_path)
        rows = parse_table_for_build(graph_path)
        payload, strategy, next_layout_state = build_payload(rows, params, layout_state)
        dump_json_atomic(output_path, payload, pretty=args.pretty)
        dump_layout_state(layout_state_path, next_layout_state)
        print("生成完成")
        print(f"输入文件: {graph_path}")
        print(f"输出文件: {output_path}")
        print(f"布局文件: {layout_state_path}")
        print(f"rootId: {payload['rootId']}")
        print(f"节点数量: {len(payload['nodes'])}")
        print(f"连线数量: {len(payload['lines'])}")
        print(f"布局方式: build_graph.py 自动布局 ({strategy})")
        return 0
    except GraphError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"生成 result.json 失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
