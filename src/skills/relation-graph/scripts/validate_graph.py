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
    "NodeID",
    "NodeText",
    "NodeType",
    "ParentID",
    "RelationText",
    "NodeX",
    "NodeY",
    "NodeWidth",
    "NodeHeight",
    "NodeSemantic",
]
NODE_TYPE_TO_INT = {
    "DK": 2,
    "PK": 3,
    "CS": 5,
    "FC": 6,
}
ALLOWED_NODE_SEMANTICS = {
    "核心知识点",
    "核心结构化知识框架",
    "先决知识点",
    "普通知识点",
}
ALLOWED_JUNCTION_POINTS = {"border", "left", "right", "top", "bottom"}
ALLOWED_RELATION_TEXTS = {
    "包含",
    "组成",
    "构成",
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
    text = value.strip().upper()
    if text not in NODE_TYPE_TO_INT:
        raise GraphError(
            f"`NodeType` 仅支持 {sorted(NODE_TYPE_TO_INT)}；请回去修改 graph.md"
        )
    return NODE_TYPE_TO_INT[text]


def normalize_node_semantic(value: str, field_name: str) -> str:
    canonical = require_text(value, field_name)
    if canonical not in ALLOWED_NODE_SEMANTICS:
        raise GraphError(
            f"`{field_name}` 仅支持 {sorted(ALLOWED_NODE_SEMANTICS)}；请回去修改 graph.md"
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


def validate_rows(rows: list[dict[str, str]]) -> dict[str, int]:
    node_defs: dict[str, tuple[str, int, int | float, int | float, int | float, int | float, str]] = {}
    line_count = 0
    for row in rows:
        node_id = require_text(row["NodeID"], "NodeID")
        node_text = require_text(row["NodeText"], "NodeText")
        node_type = parse_node_type(row["NodeType"])
        node_x = parse_number(row["NodeX"], "NodeX")
        node_y = parse_number(row["NodeY"], "NodeY")
        node_width = parse_number(row["NodeWidth"], "NodeWidth")
        node_height = parse_number(row["NodeHeight"], "NodeHeight")
        node_semantic = normalize_node_semantic(row["NodeSemantic"], "NodeSemantic")
        node_signature = (
            node_text,
            node_type,
            node_x,
            node_y,
            node_width,
            node_height,
            node_semantic,
        )
        if node_id in node_defs and node_defs[node_id] != node_signature:
            raise GraphError(
                f"`NodeID` `{node_id}` 重复出现时，节点定义字段必须完全一致；请回去修改 graph.md"
            )
        node_defs[node_id] = node_signature
        parent_id = row["ParentID"].strip()
        relation = row["RelationText"].strip()
        if bool(parent_id) != bool(relation):
            raise GraphError(
                "`ParentID` 和 `RelationText` 必须同时为空，或同时非空；请回去修改 graph.md"
            )
        if relation:
            normalize_relation_text(relation, "RelationText")
            line_count += 1

    for row in rows:
        parent_id = row["ParentID"].strip()
        if parent_id and parent_id not in node_defs:
            raise GraphError(f"父节点 `{parent_id}` 未定义；请回去修改 graph.md")

    return {"nodeCount": len(node_defs), "lineCount": line_count}


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
        summary = validate_rows(rows)

        print("校验通过")
        print(f"输入文件: {graph_path}")
        print(f"节点数量: {summary['nodeCount']}")
        print(f"连线数量: {summary['lineCount']}")
        return 0
    except GraphError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"校验 graph.md 失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
