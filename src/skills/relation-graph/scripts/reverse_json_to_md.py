#!/usr/bin/env python3
"""Convert a relation-graph result.json into graph.md."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


REQUIRED_HEADERS = [
    "NodeID",
    "NodeText",
    "NodeType",
    "ParentID",
    "RelationText",
    "NodeSemantic",
]
INT_TO_NODE_TYPE = {
    2: "DK",
    3: "PK",
    5: "CS",
    6: "FC",
}

COLOR_TO_SEMANTIC = {
    "#FF0000": "核心知识点",
    "#00B0F0": "核心结构化知识框架",
    "#00B050": "先决知识点",
    "#000000": "普通知识点",
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
    parser.add_argument(
        "--layout-output",
        help="Path to the output graph.layout.json file. Defaults to graph.layout.json next to graph.md.",
    )
    return parser


def resolve_output_path(raw_output: str | None) -> Path:
    if raw_output is None:
        return Path("/output/graph.md")
    return Path(raw_output).resolve()


def dump_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)


def dump_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def resolve_layout_output_path(markdown_path: Path, raw_layout_output: str | None) -> Path:
    if raw_layout_output is not None:
        return Path(raw_layout_output).resolve()
    return markdown_path.with_name("graph.layout.json")


def restore_node_semantic(value: object) -> str:
    text = str(value).strip().upper()
    return COLOR_TO_SEMANTIC.get(text, "普通知识点")


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


def restore_node_type(value: object) -> str:
    try:
        type_int = int(value)
    except (TypeError, ValueError) as exc:
        raise ReverseError(f"无法识别节点类型: {value}") from exc
    if type_int not in INT_TO_NODE_TYPE:
        raise ReverseError(f"不支持的节点类型: {value}")
    return INT_TO_NODE_TYPE[type_int]


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
        node_type = restore_node_type(node.get("data", {}).get("type", ""))
        node_semantic = restore_node_semantic(node.get("borderColor", ""))

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
                        node_semantic,
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
                        node_semantic,
                    ]
                )
                + " |"
            )
            row_count += 1

    return ("\n".join(rows) + "\n", len(node_order), row_count)


def build_layout_state(payload: dict) -> dict:
    state_nodes: dict[str, dict[str, int]] = {}
    for node in payload["nodes"]:
        node_id = str(node.get("id", "")).strip()
        if not node_id:
            continue
        state_nodes[node_id] = {
            "x": int(round(float(node.get("x", 0)))),
            "y": int(round(float(node.get("y", 0)))),
            "width": int(round(float(node.get("width", 0)))),
            "height": int(round(float(node.get("height", 0)))),
        }
    return {"nodes": state_nodes}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    json_path = Path(args.json_file).resolve()
    try:
        output_path = resolve_output_path(args.output)
        layout_output_path = resolve_layout_output_path(output_path, args.layout_output)
        payload = read_payload(json_path)
        markdown, node_count, row_count = build_markdown(payload)
        layout_state = build_layout_state(payload)
        dump_text_atomic(output_path, markdown)
        dump_json_atomic(layout_output_path, layout_state)
        print("反向生成完成")
        print(f"输入文件: {json_path}")
        print(f"输出文件: {output_path}")
        print(f"布局文件: {layout_output_path}")
        print(f"节点数量: {node_count}")
        print(f"表格行数: {row_count}")
        return 0
    except ReverseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"反向生成 graph.md 失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
