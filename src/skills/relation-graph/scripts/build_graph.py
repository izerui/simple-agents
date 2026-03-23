#!/usr/bin/env python3
"""Build a relation graph result JSON from graph.md."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


class GraphError(ValueError):
    """Raised when graph.md cannot be converted into result.json."""


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
        help="Path to the final result JSON. Defaults to <cwd>/output/result.json.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON.")
    return parser


def resolve_output_path(raw_output: str | None) -> Path:
    output_root = (Path.cwd() / "output").resolve()
    if raw_output is None:
        return output_root / "result.json"

    output_path = Path(raw_output).resolve()
    if output_path.parent != output_root:
        raise GraphError(
            f"输出文件必须写到当前任务工作目录下的 /output 目录: {output_root}"
        )
    return output_path


def dump_json_atomic(path: Path, payload: Any, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".result.", suffix=".json", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if pretty:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            else:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


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
    "NodeColor",
]
COLOR_ALIASES = {
    "#ff0000": "#FF0000",
    "#00b0f0": "#00B0F0",
    "#00b050": "#00B050",
    "#000000": "#000000",
    "#548bd4": "#00B0F0",
    "#0070c0": "#00B0F0",
}


def parse_number(value: str) -> int | float:
    text = value.strip()
    return float(text) if "." in text else int(text)


def normalize_color(value: str) -> str:
    return COLOR_ALIASES.get(value.strip(), COLOR_ALIASES.get(value.strip().lower(), value.strip()))


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


def compose_node(
    node_id: str,
    text: str,
    data_type: int,
    x: int | float,
    y: int | float,
    width: int | float,
    height: int | float,
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


def compose_line(parent_id: str, node_id: str, relation: str, node_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source = node_map[parent_id]
    target = node_map[node_id]
    from_junction, to_junction = choose_junction_points(source, target)
    return {
        "id": f"line-{uuid.uuid4().hex[:12]}",
        "type": "line",
        "text": relation.strip(),
        "from": parent_id,
        "to": node_id,
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
    node_defs: dict[str, tuple[str, int, int | float, int | float, int | float, int | float, str]] = {}
    for row in rows:
        node_id = row["NodeID"].strip()
        node_signature = (
            row["NodeText"].strip(),
            int(row["NodeType"].strip()),
            parse_number(row["NodeX"]),
            parse_number(row["NodeY"]),
            parse_number(row["NodeWidth"]),
            parse_number(row["NodeHeight"]),
            normalize_color(row["NodeColor"]),
        )
        node_defs.setdefault(node_id, node_signature)

    nodes = [
        compose_node(node_id, text, data_type, x, y, width, height, border_color)
        for node_id, (text, data_type, x, y, width, height, border_color) in node_defs.items()
    ]
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
    return {
        "rootId": f"root-{uuid.uuid4().hex}",
        "datetime": int(time.time() * 1000),
        "nodes": nodes,
        "lines": lines,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    graph_path = Path(args.graph).resolve()

    try:
        output_path = resolve_output_path(args.output)
        rows = parse_table_for_build(graph_path)
        payload = build_payload(rows)
        dump_json_atomic(output_path, payload, pretty=args.pretty)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "graph": str(graph_path),
                    "output": str(output_path),
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
        print(f"生成 result.json 失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
