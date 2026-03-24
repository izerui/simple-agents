#!/usr/bin/env python3
"""Auto-layout a relation-graph result.json file.

This script rewrites node positions in an existing result.json and updates
line junction points to match the new layout.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path
from typing import Any


class LayoutError(ValueError):
    """Raised when the input file cannot be auto-laid out."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Auto-layout an existing relation-graph result.json file."
    )
    parser.add_argument("json_file", help="Path to the input result.json file.")
    parser.add_argument(
        "--output",
        help="Path to the output JSON file. Defaults to overwriting the input file.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print output JSON.",
    )
    parser.add_argument(
        "--level-gap",
        type=float,
        default=150.0,
        help="Vertical gap between parent and child levels in tree layout.",
    )
    parser.add_argument(
        "--sibling-gap",
        type=float,
        default=48.0,
        help="Horizontal gap between sibling subtrees.",
    )
    parser.add_argument(
        "--component-gap-x",
        type=float,
        default=240.0,
        help="Horizontal gap between weakly connected components.",
    )
    parser.add_argument(
        "--component-gap-y",
        type=float,
        default=180.0,
        help="Vertical gap between weakly connected components.",
    )
    return parser


def read_payload(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise LayoutError(f"JSON 文件不存在: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LayoutError(f"JSON 解析失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise LayoutError("顶层 JSON 必须是对象")
    if not isinstance(payload.get("nodes"), list):
        raise LayoutError("JSON 中缺少 nodes 数组")
    if not isinstance(payload.get("lines"), list):
        raise LayoutError("JSON 中缺少 lines 数组")
    return payload


def dump_json(path: Path, payload: dict[str, Any], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        if pretty:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        else:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def center_x(node: dict[str, Any]) -> float:
    return float(node["x"]) + float(node["width"]) / 2.0


def center_y(node: dict[str, Any]) -> float:
    return float(node["y"]) + float(node["height"]) / 2.0


def choose_single_junction(source: dict[str, Any], target: dict[str, Any]) -> str:
    dx = center_x(target) - center_x(source)
    dy = center_y(target) - center_y(source)
    if dx == 0 and dy == 0:
        return "right"

    half_width = float(source["width"]) / 2.0
    half_height = float(source["height"]) / 2.0
    tx = float("inf") if dx == 0 else half_width / abs(dx)
    ty = float("inf") if dy == 0 else half_height / abs(dy)

    if tx < ty:
        return "right" if dx > 0 else "left"
    return "bottom" if dy > 0 else "top"


def choose_junction_points(
    source: dict[str, Any], target: dict[str, Any]
) -> tuple[str, str]:
    return choose_single_junction(source, target), choose_single_junction(target, source)


def round_int(value: float) -> int:
    return int(round(value))


class AutoLayoutEngine:
    """Layout engine for relation-graph result.json payloads."""

    def __init__(
        self,
        payload: dict[str, Any],
        *,
        level_gap: float,
        sibling_gap: float,
        component_gap_x: float,
        component_gap_y: float,
    ) -> None:
        self.payload = deepcopy(payload)
        self.nodes = self.payload["nodes"]
        self.lines = self.payload["lines"]

        self.node_map: dict[str, dict[str, Any]] = {}
        self.children: dict[str, list[str]] = defaultdict(list)
        self.parents: dict[str, list[str]] = defaultdict(list)
        self.undirected: dict[str, set[str]] = defaultdict(set)
        self.in_degree: dict[str, int] = defaultdict(int)
        self.out_degree: dict[str, int] = defaultdict(int)

        self.level_gap = level_gap
        self.sibling_gap = sibling_gap
        self.component_gap_x = component_gap_x
        self.component_gap_y = component_gap_y

        self._build_graph()

    def _build_graph(self) -> None:
        for node in self.nodes:
            node_id = str(node.get("id", "")).strip()
            if not node_id:
                raise LayoutError("存在缺少 id 的节点")
            if node_id in self.node_map:
                raise LayoutError(f"节点 id 重复: {node_id}")
            self.node_map[node_id] = node
            self.in_degree[node_id] = 0
            self.out_degree[node_id] = 0
            self.undirected[node_id]

        for line in self.lines:
            source = str(line.get("from", "")).strip()
            target = str(line.get("to", "")).strip()
            if source not in self.node_map or target not in self.node_map:
                continue
            self.children[source].append(target)
            self.parents[target].append(source)
            self.undirected[source].add(target)
            self.undirected[target].add(source)
            self.in_degree[target] += 1
            self.out_degree[source] += 1

    def calculate(self) -> dict[str, Any]:
        components = self._weakly_connected_components()
        layouts = [self._layout_component(component) for component in components]
        global_positions = self._pack_components(layouts)
        self._apply_positions(global_positions)
        self._update_line_junctions()
        return self.payload

    def _weakly_connected_components(self) -> list[list[str]]:
        visited: set[str] = set()
        components: list[list[str]] = []

        for node_id in self.node_map:
            if node_id in visited:
                continue
            queue = deque([node_id])
            visited.add(node_id)
            component: list[str] = []

            while queue:
                current = queue.popleft()
                component.append(current)
                for neighbor in self.undirected[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            components.append(component)

        components.sort(key=len, reverse=True)
        return components

    def _layout_component(self, component: list[str]) -> dict[str, Any]:
        if len(component) == 1:
            node_id = component[0]
            return {
                "positions": {node_id: (0.0, 0.0)},
                "bbox": self._bbox_for_positions({node_id: (0.0, 0.0)}),
            }

        roots = self._find_roots(component)
        if roots:
            positions = self._layout_tree_component(component, roots)
        else:
            positions = self._layout_cyclic_component(component)

        return {
            "positions": positions,
            "bbox": self._bbox_for_positions(positions),
        }

    def _find_roots(self, component: list[str]) -> list[str]:
        component_set = set(component)
        roots = [
            node_id
            for node_id in component
            if sum(1 for parent in self.parents[node_id] if parent in component_set) == 0
        ]
        roots.sort(
            key=lambda node_id: (
                -self.out_degree[node_id],
                self.in_degree[node_id] + self.out_degree[node_id],
                node_id,
            )
        )
        return roots

    def _layout_tree_component(
        self, component: list[str], roots: list[str]
    ) -> dict[str, tuple[float, float]]:
        component_set = set(component)
        levels = self._assign_levels(component, roots)
        primary_parent = self._assign_primary_parent(component, roots, levels)
        primary_children: dict[str, list[str]] = defaultdict(list)
        for node_id, parent_id in primary_parent.items():
            if parent_id is not None:
                primary_children[parent_id].append(node_id)

        virtual_root = "__virtual_root__"
        primary_children[virtual_root] = list(roots)

        def sort_key(node_id: str) -> tuple[float, float, str]:
            node = self.node_map[node_id]
            return (
                levels.get(node_id, 10**9),
                center_y(node),
                node_id,
            )

        for parent_id, child_ids in primary_children.items():
            child_ids.sort(key=sort_key)

        subtree_size_cache: dict[str, int] = {}

        def subtree_size(node_id: str) -> int:
            if node_id in subtree_size_cache:
                return subtree_size_cache[node_id]
            total = 1
            for child_id in primary_children.get(node_id, []):
                total += subtree_size(child_id)
            subtree_size_cache[node_id] = total
            return total

        for parent_id, child_ids in primary_children.items():
            child_ids.sort(key=lambda node_id: (-subtree_size(node_id), sort_key(node_id)))
        positions: dict[str, tuple[float, float]] = {}
        self._place_roots_as_skeleton(roots, primary_children, positions)

        unplaced = component_set - set(positions)
        if unplaced:
            fallback = self._layout_cyclic_component(sorted(unplaced))
            fallback = self._shift_positions_below(fallback, positions)
            positions.update(fallback)

        return positions

    def _assign_levels(self, component: list[str], roots: list[str]) -> dict[str, int]:
        component_set = set(component)
        levels: dict[str, int] = {}
        queue = deque()

        for root_id in roots:
            levels[root_id] = 0
            queue.append(root_id)

        while queue:
            current = queue.popleft()
            current_level = levels[current]
            for child_id in self.children[current]:
                if child_id not in component_set:
                    continue
                next_level = current_level + 1
                if child_id not in levels or next_level < levels[child_id]:
                    levels[child_id] = next_level
                    queue.append(child_id)

        if len(levels) == len(component_set):
            return levels

        undirected_queue = deque(levels)
        while undirected_queue:
            current = undirected_queue.popleft()
            current_level = levels[current]
            for neighbor in self.undirected[current]:
                if neighbor not in component_set:
                    continue
                next_level = current_level + 1
                if neighbor not in levels:
                    levels[neighbor] = next_level
                    undirected_queue.append(neighbor)

        for node_id in component:
            levels.setdefault(node_id, 0)
        return levels

    def _assign_primary_parent(
        self,
        component: list[str],
        roots: list[str],
        levels: dict[str, int],
    ) -> dict[str, str | None]:
        component_set = set(component)
        primary_parent: dict[str, str | None] = {root_id: None for root_id in roots}

        for node_id in component:
            if node_id in primary_parent:
                continue
            candidates = [parent for parent in self.parents[node_id] if parent in component_set]
            if not candidates:
                primary_parent[node_id] = None
                continue

            def parent_key(parent_id: str) -> tuple[int, int, str]:
                return (
                    levels.get(parent_id, 10**9),
                    -self.out_degree[parent_id],
                    parent_id,
                )

            primary_parent[node_id] = min(candidates, key=parent_key)

        return primary_parent

    def _place_roots_as_skeleton(
        self,
        roots: list[str],
        primary_children: dict[str, list[str]],
        positions: dict[str, tuple[float, float]],
    ) -> None:
        if len(roots) == 1:
            root_id = roots[0]
            root_node = self.node_map[root_id]
            root_cx = 0.0
            root_cy = 0.0
            positions[root_id] = (
                root_cx - float(root_node["width"]) / 2.0,
                root_cy - float(root_node["height"]) / 2.0,
            )
            children = primary_children.get(root_id, [])
            slots = self._skeleton_slots(len(children))
            for child_id, slot in zip(children, slots):
                child_node = self.node_map[child_id]
                child_cx = slot["cx"]
                child_cy = slot["cy"]
                positions[child_id] = (
                    child_cx - float(child_node["width"]) / 2.0,
                    child_cy - float(child_node["height"]) / 2.0,
                )
                self._place_sector_descendants(
                    child_id,
                    child_cx,
                    child_cy,
                    slot["angle"],
                    slot["spread"],
                    primary_children,
                    positions,
                    depth=2,
                )
            return

        slots = self._skeleton_slots(len(roots), root_radius=self.level_gap * 1.4)
        for root_id, slot in zip(roots, slots):
            root_node = self.node_map[root_id]
            root_cx = slot["cx"]
            root_cy = slot["cy"]
            positions[root_id] = (
                root_cx - float(root_node["width"]) / 2.0,
                root_cy - float(root_node["height"]) / 2.0,
            )
            self._place_sector_descendants(
                root_id,
                root_cx,
                root_cy,
                slot["angle"],
                slot["spread"],
                primary_children,
                positions,
                depth=1,
            )

    def _skeleton_slots(self, count: int, root_radius: float | None = None) -> list[dict[str, float]]:
        if count <= 0:
            return []

        radius = root_radius if root_radius is not None else max(self.level_gap * 1.55, 220.0)
        presets = [
            {"angle": -90.0, "spread": 42.0},
            {"angle": 180.0, "spread": 46.0},
            {"angle": 0.0, "spread": 46.0},
            {"angle": 90.0, "spread": 42.0},
            {"angle": -140.0, "spread": 32.0},
            {"angle": -40.0, "spread": 32.0},
            {"angle": 140.0, "spread": 32.0},
            {"angle": 40.0, "spread": 32.0},
        ]
        if count <= len(presets):
            selected = presets[:count]
        else:
            selected = []
            for index in range(count):
                angle = -90.0 + index * (360.0 / count)
                selected.append({"angle": angle, "spread": max(18.0, 300.0 / count)})

        slots = []
        for preset in selected:
            rad = math.radians(preset["angle"])
            slots.append(
                {
                    "cx": radius * math.cos(rad),
                    "cy": radius * math.sin(rad),
                    "angle": preset["angle"],
                    "spread": preset["spread"],
                }
            )
        return slots

    def _place_sector_descendants(
        self,
        node_id: str,
        center_x_value: float,
        center_y_value: float,
        angle_deg: float,
        spread_deg: float,
        primary_children: dict[str, list[str]],
        positions: dict[str, tuple[float, float]],
        depth: int,
    ) -> None:
        children = primary_children.get(node_id, [])
        if not children:
            return

        if len(children) == 1:
            child_angles = [angle_deg]
        else:
            start = angle_deg - spread_deg / 2.0
            step = spread_deg / max(1, len(children) - 1)
            child_angles = [start + index * step for index in range(len(children))]

        for child_id, child_angle in zip(children, child_angles):
            child_node = self.node_map[child_id]
            distance = self._sector_distance(depth, child_angle)
            rad = math.radians(child_angle)
            child_cx = center_x_value + distance * math.cos(rad)
            child_cy = center_y_value + distance * math.sin(rad)
            positions[child_id] = (
                child_cx - float(child_node["width"]) / 2.0,
                child_cy - float(child_node["height"]) / 2.0,
            )

            next_spread = max(16.0, spread_deg * 0.72)
            self._place_sector_descendants(
                child_id,
                child_cx,
                child_cy,
                child_angle,
                next_spread,
                primary_children,
                positions,
                depth + 1,
            )

    def _sector_distance(self, depth: int, angle_deg: float) -> float:
        vertical_bias = abs(math.sin(math.radians(angle_deg)))
        base = self.level_gap + depth * 18.0
        if vertical_bias > 0.75:
            return base
        if vertical_bias < 0.3:
            return base + 30.0
        return base + 12.0

    def _layout_cyclic_component(
        self, component: list[str]
    ) -> dict[str, tuple[float, float]]:
        center_node = max(
            component,
            key=lambda node_id: (
                self.in_degree[node_id] + self.out_degree[node_id],
                self.out_degree[node_id],
                node_id,
            ),
        )

        levels = self._assign_radial_levels(component, center_node)
        layered_nodes: dict[int, list[str]] = defaultdict(list)
        for node_id, level in levels.items():
            layered_nodes[level].append(node_id)

        positions: dict[str, tuple[float, float]] = {}
        root_node = self.node_map[center_node]
        positions[center_node] = (
            -float(root_node["width"]) / 2.0,
            -float(root_node["height"]) / 2.0,
        )

        max_width = max(float(self.node_map[node_id]["width"]) for node_id in component)
        max_height = max(float(self.node_map[node_id]["height"]) for node_id in component)
        base_radius = max(max_width * 1.2, max_height * 1.8, self.level_gap * 0.8)
        radius_step = max(max_width + self.sibling_gap, max_height + self.level_gap * 0.5)

        for level in sorted(layered_nodes):
            if level == 0:
                continue
            nodes_at_level = sorted(layered_nodes[level])
            radius = base_radius + (level - 1) * radius_step
            count = len(nodes_at_level)
            for index, node_id in enumerate(nodes_at_level):
                angle = -math.pi / 2.0
                if count > 1:
                    angle += (2.0 * math.pi * index) / count
                node = self.node_map[node_id]
                cx = radius * math.cos(angle)
                cy = radius * math.sin(angle)
                positions[node_id] = (
                    cx - float(node["width"]) / 2.0,
                    cy - float(node["height"]) / 2.0,
                )

        return positions

    def _assign_radial_levels(self, component: list[str], root_id: str) -> dict[str, int]:
        component_set = set(component)
        levels = {root_id: 0}
        queue = deque([root_id])

        while queue:
            current = queue.popleft()
            current_level = levels[current]
            for neighbor in self.undirected[current]:
                if neighbor not in component_set or neighbor in levels:
                    continue
                levels[neighbor] = current_level + 1
                queue.append(neighbor)

        for node_id in component:
            levels.setdefault(node_id, max(levels.values(), default=0) + 1)
        return levels

    def _shift_positions_below(
        self,
        fallback: dict[str, tuple[float, float]],
        positions: dict[str, tuple[float, float]],
    ) -> dict[str, tuple[float, float]]:
        if not positions:
            return fallback
        bbox_main = self._bbox_for_positions(positions)
        bbox_extra = self._bbox_for_positions(fallback)
        shift_x = 0.0
        shift_y = bbox_main["bottom"] - bbox_extra["top"] + self.level_gap
        return {
            node_id: (left + shift_x, top + shift_y)
            for node_id, (left, top) in fallback.items()
        }

    def _bbox_for_positions(
        self, positions: dict[str, tuple[float, float]]
    ) -> dict[str, float]:
        lefts: list[float] = []
        rights: list[float] = []
        tops: list[float] = []
        bottoms: list[float] = []

        for node_id, (left, top) in positions.items():
            node = self.node_map[node_id]
            width = float(node["width"])
            height = float(node["height"])
            lefts.append(left)
            rights.append(left + width)
            tops.append(top)
            bottoms.append(top + height)

        return {
            "left": min(lefts),
            "right": max(rights),
            "top": min(tops),
            "bottom": max(bottoms),
            "width": max(rights) - min(lefts),
            "height": max(bottoms) - min(tops),
        }

    def _pack_components(
        self, layouts: list[dict[str, Any]]
    ) -> dict[str, tuple[float, float]]:
        if len(layouts) == 1:
            positions = dict(layouts[0]["positions"])
            return self._recenter_positions(positions)

        count = len(layouts)
        columns = math.ceil(math.sqrt(count))
        rows = math.ceil(count / columns)

        column_widths = [0.0] * columns
        row_heights = [0.0] * rows
        for index, layout in enumerate(layouts):
            row = index // columns
            col = index % columns
            bbox = layout["bbox"]
            column_widths[col] = max(column_widths[col], bbox["width"])
            row_heights[row] = max(row_heights[row], bbox["height"])

        x_offsets = []
        running_x = 0.0
        for col_width in column_widths:
            x_offsets.append(running_x)
            running_x += col_width + self.component_gap_x

        y_offsets = []
        running_y = 0.0
        for row_height in row_heights:
            y_offsets.append(running_y)
            running_y += row_height + self.component_gap_y

        packed: dict[str, tuple[float, float]] = {}
        for index, layout in enumerate(layouts):
            row = index // columns
            col = index % columns
            bbox = layout["bbox"]
            cell_left = x_offsets[col]
            cell_top = y_offsets[row]
            dx = cell_left - bbox["left"] + (column_widths[col] - bbox["width"]) / 2.0
            dy = cell_top - bbox["top"] + (row_heights[row] - bbox["height"]) / 2.0
            for node_id, (left, top) in layout["positions"].items():
                packed[node_id] = (left + dx, top + dy)

        return self._recenter_positions(packed)

    def _recenter_positions(
        self, positions: dict[str, tuple[float, float]]
    ) -> dict[str, tuple[float, float]]:
        bbox = self._bbox_for_positions(positions)
        center_x_value = (bbox["left"] + bbox["right"]) / 2.0
        center_y_value = (bbox["top"] + bbox["bottom"]) / 2.0
        return {
            node_id: (left - center_x_value, top - center_y_value)
            for node_id, (left, top) in positions.items()
        }

    def _apply_positions(self, positions: dict[str, tuple[float, float]]) -> None:
        for node_id, (left, top) in positions.items():
            node = self.node_map[node_id]
            node["x"] = round_int(left)
            node["y"] = round_int(top)
            start_position = node.get("data", {}).get("startPostion")
            if isinstance(start_position, dict):
                start_position["x"] = node["x"]
                start_position["y"] = node["y"]

    def _update_line_junctions(self) -> None:
        for line in self.lines:
            source_id = str(line.get("from", "")).strip()
            target_id = str(line.get("to", "")).strip()
            source = self.node_map.get(source_id)
            target = self.node_map.get(target_id)
            if not source or not target:
                continue
            from_junction, to_junction = choose_junction_points(source, target)
            line["fromJunctionPoint"] = from_junction
            line["toJunctionPoint"] = to_junction


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.json_file).resolve()
    output_path = Path(args.output).resolve() if args.output else input_path

    try:
        payload = read_payload(input_path)
        engine = AutoLayoutEngine(
            payload,
            level_gap=args.level_gap,
            sibling_gap=args.sibling_gap,
            component_gap_x=args.component_gap_x,
            component_gap_y=args.component_gap_y,
        )
        result = engine.calculate()
        dump_json(output_path, result, pretty=args.pretty)
        print("自动布局完成")
        print(f"输入文件: {input_path}")
        print(f"输出文件: {output_path}")
        print(f"节点数量: {len(result['nodes'])}")
        print(f"连线数量: {len(result['lines'])}")
        return 0
    except LayoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"自动布局失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
