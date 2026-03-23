#!/usr/bin/env python3
"""Validate graph.md before generating the final relation graph JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_HEADERS = [
    "IsRoot",
    "NodeID",
    "NodeText",
    "NodeType",
    "ParentID",
    "RelationText",
    "NodeX",
    "NodeY",
    "NodeWidth",
    "NodeHeight",
    "NodeColor",
]
ALLOWED_NODE_TYPES = {2, 3, 5, 6}
CANONICAL_COLORS = {"#FF0000", "#00B0F0", "#00B050", "#000000"}
COLOR_ALIASES = {
    "#ff0000": "#FF0000",
    "#00b0f0": "#00B0F0",
    "#00b050": "#00B050",
    "#000000": "#000000",
    "#548bd4": "#00B0F0",
    "#0070c0": "#00B0F0",
}
ALLOWED_JUNCTION_POINTS = {"border", "left", "right", "top", "bottom"}
ALLOWED_RELATION_TEXTS = {
    "各类包含",
    "组成/构成",
    "是一种",
    "具有属性",
    "具有特征",
    "定义",
    "并列",
    "是前提",
    "支持",
}


class GraphError(ValueError):
    """Raised when graph.md or derived payload is invalid."""


def split_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise GraphError("Markdown 表格行必须以 `|` 开始并以 `|` 结束；请回去修改 graph.md")
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def require_text(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise GraphError(f"`{field_name}` 不能为空；请回去修改 graph.md")
    if any(char in text for char in ("\r", "\n")):
        raise GraphError(f"`{field_name}` 不允许换行；请回去修改 graph.md")
    return text


def parse_bool(value: str, field_name: str) -> bool:
    normalized = value.strip()
    if normalized == "是":
        return True
    if normalized == "否":
        return False
    raise GraphError(f"`{field_name}` 只允许填写 `是` 或 `否`；请回去修改 graph.md")


def parse_number(value: str, field_name: str) -> int | float:
    text = value.strip()
    if not text:
        raise GraphError(f"`{field_name}` 不能为空；请回去修改 graph.md")
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    raise GraphError(f"`{field_name}` 必须是数字；请回去修改 graph.md")


def parse_node_type(value: str) -> int:
    text = value.strip()
    if not re.fullmatch(r"\d+", text):
        raise GraphError("`NodeType` 必须是整数；请回去修改 graph.md")
    node_type = int(text)
    if node_type not in ALLOWED_NODE_TYPES:
        raise GraphError(
            f"`NodeType` 仅支持 {sorted(ALLOWED_NODE_TYPES)}；请回去修改 graph.md"
        )
    return node_type


def normalize_color(value: str, field_name: str) -> str:
    canonical = COLOR_ALIASES.get(value.strip(), COLOR_ALIASES.get(value.strip().lower()))
    if canonical not in CANONICAL_COLORS:
        raise GraphError(
            f"`{field_name}` 仅支持 {sorted(CANONICAL_COLORS)}；请回去修改 graph.md"
        )
    return canonical


def normalize_relation_text(value: str, field_name: str) -> str:
    text = require_text(value, field_name)
    if text not in ALLOWED_RELATION_TEXTS:
        raise GraphError(
            f"`{field_name}` 只能使用 {sorted(ALLOWED_RELATION_TEXTS)}；请回去修改 graph.md"
        )
    return text


def parse_table(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise GraphError(f"Markdown 表格不存在: {path}；请回去修改 graph.md")

    lines = [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 3:
        raise GraphError("Markdown 表格至少需要表头、分隔行和一行数据；请回去修改 graph.md")

    headers = split_row(lines[0])
    if headers != REQUIRED_HEADERS:
        raise GraphError("Markdown 表头不符合预期的单表格式；请回去修改 graph.md")

    separator = split_row(lines[1])
    if len(separator) != len(headers) or not all(set(cell) <= {"-", ":"} and cell for cell in separator):
        raise GraphError("Markdown 表格第二行必须是分隔行；请回去修改 graph.md")

    rows: list[dict[str, str]] = []
    for raw_line in lines[2:]:
        if not raw_line.lstrip().startswith("|"):
            continue
        cells = split_row(raw_line)
        if len(cells) != len(headers):
            raise GraphError("Markdown 数据行列数与表头不一致；请回去修改 graph.md")
        rows.append(dict(zip(headers, cells)))

    if not rows:
        raise GraphError("Markdown 表格没有数据行；请回去修改 graph.md")
    return rows


def center_x(node: dict[str, Any]) -> float:
    return float(node["x"]) + float(node["width"]) / 2


def center_y(node: dict[str, Any]) -> float:
    return float(node["y"]) + float(node["height"]) / 2


def center(node: dict[str, Any]) -> tuple[float, float]:
    return (center_x(node), center_y(node))


def choose_junction_points(source: dict[str, Any], target: dict[str, Any]) -> tuple[str, str]:
    dx = center_x(target) - center_x(source)
    dy = center_y(target) - center_y(source)
    if abs(dy) < abs(dx):
        return ("right", "left") if dx >= 0 else ("left", "right")
    return ("bottom", "top") if dy >= 0 else ("top", "bottom")


def compose_node(
    node_id: str,
    text: str,
    x: int | float,
    y: int | float,
    width: int | float,
    height: int | float,
    border_color: str,
    data_type: int,
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
        "fontSize": 14,
        "fontBold": False,
        "fontItalic": False,
        "fontUnderline": False,
        "textHorizontalAlign": "center",
        "textVerticalAlign": "middle",
        "color": "#ffffff",
        "opacity": 1,
        "fixed": False,
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


def compose_line(
    parent_id: str,
    node_id: str,
    relation: str,
    node_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    from_junction, to_junction = choose_junction_points(node_map[parent_id], node_map[node_id])
    return {
        "id": f"{parent_id}->{node_id}",
        "from": parent_id,
        "to": node_id,
        "text": relation,
        "lineWidth": 1,
        "color": "#000000",
        "isHide": False,
        "lineShape": 1,
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
    }


def build_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    pending_lines: list[tuple[str, str, str]] = []
    node_ids: set[str] = set()
    root_node_id: str | None = None

    for row in rows:
        is_root = parse_bool(row["IsRoot"], "IsRoot")
        node_id = require_text(row["NodeID"], "NodeID")
        if node_id in node_ids:
            raise GraphError(f"当前节点重复出现: {node_id}；请回去修改 graph.md")
        node_ids.add(node_id)

        parent_id = row["ParentID"].strip()
        relation = row["RelationText"].strip()

        if is_root:
            if root_node_id is not None:
                raise GraphError("只能有一个根节点；请回去修改 graph.md")
            root_node_id = node_id
            if parent_id or relation:
                raise GraphError("根节点行的 `ParentID` 和 `RelationText` 必须为空；请回去修改 graph.md")
        else:
            if not parent_id:
                raise GraphError(f"非根节点 `{node_id}` 必须填写 `ParentID`；请回去修改 graph.md")
            if not relation:
                raise GraphError(f"非根节点 `{node_id}` 必须填写 `RelationText`；请回去修改 graph.md")
            pending_lines.append((parent_id, node_id, normalize_relation_text(relation, "RelationText")))

        node = compose_node(
            node_id=node_id,
            text=require_text(row["NodeText"], "NodeText"),
            x=parse_number(row["NodeX"], "NodeX"),
            y=parse_number(row["NodeY"], "NodeY"),
            width=parse_number(row["NodeWidth"], "NodeWidth"),
            height=parse_number(row["NodeHeight"], "NodeHeight"),
            border_color=normalize_color(require_text(row["NodeColor"], "NodeColor"), "NodeColor"),
            data_type=parse_node_type(row["NodeType"]),
        )
        nodes.append(node)

    if root_node_id is None:
        raise GraphError("必须有且仅有一个根节点；请回去修改 graph.md")

    node_map = {node["id"]: node for node in nodes}
    lines: list[dict[str, Any]] = []
    for parent_id, node_id, relation in pending_lines:
        if parent_id not in node_map:
            raise GraphError(f"父节点 `{parent_id}` 未定义；请回去修改 graph.md")
        lines.append(compose_line(parent_id, node_id, relation, node_map))

    return {"rootId": f"root-{root_node_id}", "nodes": nodes, "lines": lines}


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root_id = payload.get("rootId")
    nodes = payload.get("nodes")
    lines = payload.get("lines")

    if not isinstance(root_id, str) or not root_id.strip():
        errors.append("`rootId` 必须是非空字符串")

    if not isinstance(nodes, list) or not nodes:
        errors.append("`nodes` 必须是非空数组")
        return errors
    if not isinstance(lines, list):
        errors.append("`lines` 必须是数组")
        return errors

    node_ids: list[str] = []
    node_by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = node["id"]
        node_ids.append(node_id)
        node_by_id[node_id] = node
        if node["fontColor"] != node["borderColor"]:
            errors.append(f"节点 `{node_id}` 的 fontColor 必须与 borderColor 一致")
        if node["data"]["startPostion"]["x"] != node["x"] or node["data"]["startPostion"]["y"] != node["y"]:
            errors.append(f"节点 `{node_id}` 的 data.startPostion 必须与 x/y 一致")
        if node["data"]["type"] not in ALLOWED_NODE_TYPES:
            errors.append(f"节点 `{node_id}` 的 data.type 仅支持 {sorted(ALLOWED_NODE_TYPES)}")
        if node["borderColor"] not in CANONICAL_COLORS:
            errors.append(f"节点 `{node_id}` 的 borderColor 仅支持 {sorted(CANONICAL_COLORS)}")
        if any(char in node["text"] for char in ("\r", "\n")):
            errors.append(f"节点 `{node_id}` 的 text 不允许换行")

    if len(node_ids) != len(set(node_ids)):
        errors.append("nodes 中存在重复 id")

    line_ids: list[str] = []
    for line in lines:
        line_id = line["id"]
        line_ids.append(line_id)
        from_id = line["from"]
        to_id = line["to"]

        if from_id not in node_by_id:
            errors.append(f"连线 `{line_id}` 的 from 未引用有效节点")
            continue
        if to_id not in node_by_id:
            errors.append(f"连线 `{line_id}` 的 to 未引用有效节点")
            continue
        if any(char in line["text"] for char in ("\r", "\n")):
            errors.append(f"连线 `{line_id}` 的 text 不允许换行")
        if line["fromJunctionPoint"] not in ALLOWED_JUNCTION_POINTS:
            errors.append(
                f"连线 `{line_id}` 的 fromJunctionPoint 仅支持 {sorted(ALLOWED_JUNCTION_POINTS)}"
            )
        if line["toJunctionPoint"] not in ALLOWED_JUNCTION_POINTS:
            errors.append(
                f"连线 `{line_id}` 的 toJunctionPoint 仅支持 {sorted(ALLOWED_JUNCTION_POINTS)}"
            )

    if len(line_ids) != len(set(line_ids)):
        errors.append("lines 中存在重复 id")

    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate graph.md for relation graph generation."
    )
    parser.add_argument("graph", help="Path to the markdown graph table file.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    graph_path = Path(args.graph).resolve()

    try:
        rows = parse_table(graph_path)
        payload = build_payload(rows)
        errors = validate_payload(payload)
        if errors:
            print(f"INVALID: {graph_path}")
            for index, error in enumerate(errors, start=1):
                print(f"{index}. {error}")
            return 1

        print(
            json.dumps(
                {
                    "status": "ok",
                    "graph": str(graph_path),
                    "rootId": payload["rootId"],
                    "nodeCount": len(payload["nodes"]),
                    "lineCount": len(payload["lines"]),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except GraphError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"校验 graph.md 失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
