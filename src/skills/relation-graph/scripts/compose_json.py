#!/usr/bin/env python3
"""Compose a full relation graph JSON from a structured intermediate JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


CANONICAL_COLORS = {"#FF0000", "#00B0F0", "#00B050", "#000000"}
COLOR_ALIASES = {
    "#ff0000": "#FF0000",
    "#00b0f0": "#00B0F0",
    "#00b050": "#00B050",
    "#000000": "#000000",
    "#548bd4": "#00B0F0",
    "#0070c0": "#00B0F0",
}
ALLOWED_NODE_TYPES = {2, 3, 5, 6}
OUTPUT_DIRNAME = "relation-graph"


class ComposeError(ValueError):
    """Raised when the structured payload is invalid."""


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
    parser = argparse.ArgumentParser(
        description="Compose a full relation graph JSON from a structured intermediate JSON."
    )
    parser.add_argument("structured", help="Path to the structured intermediate JSON.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the final full JSON. Must be inside an `output` directory.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON.")
    return parser


def ensure_output_dir(path: Path) -> Path:
    normalized = path.resolve()
    if OUTPUT_DIRNAME not in normalized.parts:
        raise ComposeError("输出 JSON 必须写入 `output` 目录下")
    return normalized


def ensure_object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ComposeError(f"`{field_name}` 必须是对象")
    return value


def ensure_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ComposeError(f"`{field_name}` 必须是数组")
    return value


def require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ComposeError(f"`{field_name}` 必须是非空字符串")
    if any(char in value for char in ("\r", "\n")):
        raise ComposeError(f"`{field_name}` 不允许换行")
    return value.strip()


def require_number(value: Any, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        raise ComposeError(f"`{field_name}` 必须是数字")
    return float(value)


def normalize_color(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ComposeError(f"`{field_name}` 必须是颜色字符串")
    canonical = COLOR_ALIASES.get(value.strip(), COLOR_ALIASES.get(value.strip().lower()))
    if canonical not in CANONICAL_COLORS:
        raise ComposeError(
            f"`{field_name}` 仅支持 {sorted(CANONICAL_COLORS)}"
        )
    return canonical


def validate_unique_ids(items: list[dict[str, Any]], field_name: str) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items):
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ComposeError(f"`{field_name}[{index}].id` 必须是非空字符串")
        if item_id in seen:
            raise ComposeError(f"`{field_name}` 中存在重复 id: {item_id}")
        seen.add(item_id)


def center_x(node: dict[str, Any]) -> float:
    return float(node["x"]) + float(node["width"]) / 2


def center_y(node: dict[str, Any]) -> float:
    return float(node["y"]) + float(node["height"]) / 2


def choose_junction_points(source: dict[str, Any], target: dict[str, Any]) -> tuple[str, str]:
    dx = center_x(target) - center_x(source)
    dy = center_y(target) - center_y(source)
    if abs(dy) < abs(dx):
        return ("right", "left") if dx >= 0 else ("left", "right")
    return ("bottom", "top") if dy >= 0 else ("top", "bottom")


def compose_node(node: dict[str, Any]) -> dict[str, Any]:
    node_id = require_string(node.get("id"), "nodes[].id")
    text = require_string(node.get("text"), f"nodes[{node_id}].text")
    x = require_number(node.get("x"), f"nodes[{node_id}].x")
    y = require_number(node.get("y"), f"nodes[{node_id}].y")
    width = require_number(node.get("width"), f"nodes[{node_id}].width")
    height = require_number(node.get("height"), f"nodes[{node_id}].height")
    data = ensure_object(node.get("data"), f"nodes[{node_id}].data")
    data_type = data.get("type")
    if not isinstance(data_type, int) or data_type not in ALLOWED_NODE_TYPES:
        raise ComposeError(
            f"`nodes[{node_id}].data.type` 仅支持 {sorted(ALLOWED_NODE_TYPES)}"
        )
    border_color = normalize_color(node.get("borderColor"), f"nodes[{node_id}].borderColor")

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
            "startPostion": {
                "x": x,
                "y": y,
            },
        },
    }


def compose_line(line: dict[str, Any], node_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    line_id = require_string(line.get("id"), "lines[].id")
    from_id = require_string(line.get("from"), f"lines[{line_id}].from")
    to_id = require_string(line.get("to"), f"lines[{line_id}].to")
    text = require_string(line.get("text"), f"lines[{line_id}].text")

    if from_id not in node_map:
        raise ComposeError(f"`lines[{line_id}].from` 未引用有效节点: {from_id}")
    if to_id not in node_map:
        raise ComposeError(f"`lines[{line_id}].to` 未引用有效节点: {to_id}")

    from_junction = line.get("fromJunctionPoint")
    to_junction = line.get("toJunctionPoint")
    if from_junction is None or to_junction is None:
        from_junction, to_junction = choose_junction_points(node_map[from_id], node_map[to_id])

    return {
        "id": line_id,
        "from": from_id,
        "to": to_id,
        "text": text,
        "lineWidth": 1,
        "color": "#000000",
        "isHide": False,
        "lineShape": int(line.get("lineShape", 1)),
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
        "fromJunctionPoint": require_string(from_junction, f"lines[{line_id}].fromJunctionPoint"),
        "toJunctionPoint": require_string(to_junction, f"lines[{line_id}].toJunctionPoint"),
        "fromJuctionPointOffsetX": 0,
        "fromJuctionPointOffsetY": 0,
        "toJuctionPointOffsetX": 0,
        "toJuctionPointOffsetY": 0,
        "polyLineRadius": 0,
        "hidden": False,
    }


def compose(payload: dict[str, Any]) -> dict[str, Any]:
    root_id = require_string(payload.get("rootId"), "rootId")
    raw_nodes = [ensure_object(item, f"nodes[{index}]") for index, item in enumerate(ensure_list(payload.get("nodes"), "nodes"))]
    raw_lines = [ensure_object(item, f"lines[{index}]") for index, item in enumerate(ensure_list(payload.get("lines"), "lines"))]

    if not raw_nodes:
        raise ComposeError("`nodes` 不能为空")

    validate_unique_ids(raw_nodes, "nodes")
    validate_unique_ids(raw_lines, "lines")

    nodes = [compose_node(item) for item in raw_nodes]
    node_map = {node["id"]: node for node in nodes}
    if root_id not in node_map:
        raise ComposeError(f"`rootId` 未引用有效节点: {root_id}")

    lines = [compose_line(item, node_map) for item in raw_lines]
    result: dict[str, Any] = {
        "rootId": root_id,
        "nodes": nodes,
        "lines": lines,
    }
    if "datetime" in payload:
        if not isinstance(payload["datetime"], (int, float)):
            raise ComposeError("`datetime` 必须是数字")
        result["datetime"] = payload["datetime"]
    return result


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    structured_path = Path(args.structured).resolve()
    output_path = ensure_output_dir(Path(args.output))

    try:
        if not structured_path.is_file():
            raise ComposeError(f"结构化产物 JSON 不存在: {structured_path}")
        payload = ensure_object(load_json(structured_path), "structured")
        result = compose(payload)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dump_json(output_path, result, pretty=args.pretty)
        print(json.dumps({
            "status": "ok",
            "output": str(output_path),
            "rootId": result["rootId"],
            "nodeCount": len(result["nodes"]),
            "lineCount": len(result["lines"]),
        }, ensure_ascii=False))
        return 0
    except ComposeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"编译脚本运行异常: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
