#!/usr/bin/env python3
"""Convert a relation-graph result.json into graph.md."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


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


class ReverseError(ValueError):
    """Raised when result.json cannot be converted into graph.md."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a relation graph result JSON into graph.md."
    )
    parser.add_argument("json_file", help="Path to the result JSON file.")
    parser.add_argument(
        "--output",
        help="Path to the output markdown file. Defaults to /output/graph.md.",
    )
    return parser


def resolve_output_path(raw_output: str | None) -> Path:
    if raw_output is None:
        return Path("/output/graph.md")
    return Path(raw_output).resolve()


def dump_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".graph.", suffix=".md", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def normalize_color(value: str) -> str:
    return COLOR_ALIASES.get(value.strip(), COLOR_ALIASES.get(value.strip().lower(), value.strip()))


def read_payload(path: Path) -> dict:
    if not path.is_file():
        raise ReverseError(f"JSON 文件不存在: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReverseError(f"JSON 解析失败: {exc}") from exc

    if not isinstance(payload, dict):
        raise ReverseError("顶层 JSON 必须是对象")
    if not isinstance(payload.get("nodes"), list):
        raise ReverseError("JSON 中缺少 nodes 数组")
    if not isinstance(payload.get("lines"), list):
        raise ReverseError("JSON 中缺少 lines 数组")
    return payload


def sanitize_cell(value: object) -> str:
    return str(value).strip().replace("|", "/")


def build_markdown(payload: dict) -> tuple[str, int, int]:
    nodes = payload["nodes"]
    lines = payload["lines"]

    node_order = [str(node["id"]) for node in nodes]
    node_map = {str(node["id"]): node for node in nodes}
    incoming: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for line in lines:
        parent_id = sanitize_cell(line.get("from", ""))
        child_id = sanitize_cell(line.get("to", ""))
        relation = sanitize_cell(line.get("text", ""))
        if not child_id:
            continue
        incoming[child_id].append((parent_id, relation))

    header = "| " + " | ".join(REQUIRED_HEADERS) + " |"
    separator = "| " + " | ".join(["---"] * len(REQUIRED_HEADERS)) + " |"
    rows = [header, separator]

    row_count = 0
    for node_id in node_order:
        node = node_map[node_id]
        node_text = sanitize_cell(node.get("text", ""))
        node_type = sanitize_cell(node.get("data", {}).get("type", ""))
        node_x = sanitize_cell(node.get("x", ""))
        node_y = sanitize_cell(node.get("y", ""))
        node_width = sanitize_cell(node.get("width", ""))
        node_height = sanitize_cell(node.get("height", ""))
        node_color = normalize_color(sanitize_cell(node.get("borderColor", "")))

        parent_rows = incoming.get(node_id)
        if not parent_rows:
            rows.append(
                "| "
                + " | ".join(
                    [
                        node_id,
                        node_text,
                        node_type,
                        "",
                        "",
                        node_x,
                        node_y,
                        node_width,
                        node_height,
                        node_color,
                    ]
                )
                + " |"
            )
            row_count += 1
            continue

        for parent_id, relation_text in parent_rows:
            rows.append(
                "| "
                + " | ".join(
                    [
                        node_id,
                        node_text,
                        node_type,
                        parent_id,
                        relation_text,
                        node_x,
                        node_y,
                        node_width,
                        node_height,
                        node_color,
                    ]
                )
                + " |"
            )
            row_count += 1

    return ("\n".join(rows) + "\n", len(node_order), row_count)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    json_path = Path(args.json_file).resolve()
    try:
        output_path = resolve_output_path(args.output)
        payload = read_payload(json_path)
        markdown, node_count, row_count = build_markdown(payload)
        dump_text_atomic(output_path, markdown)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "json": str(json_path),
                    "output": str(output_path),
                    "nodeCount": node_count,
                    "rowCount": row_count,
                },
                ensure_ascii=False,
            )
        )
        return 0
    except ReverseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"反向生成 graph.md 失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
