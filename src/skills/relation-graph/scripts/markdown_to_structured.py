#!/usr/bin/env python3
"""Convert a single markdown node table into structured relation graph JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_HEADERS = [
    "是否根节点",
    "当前节点ID",
    "当前节点文本",
    "当前节点类型",
    "父节点ID",
    "关系名称",
    "当前节点X",
    "当前节点Y",
    "当前节点宽度",
    "当前节点高度",
    "当前节点颜色",
]


class ConvertError(ValueError):
    """Raised when the markdown table cannot be converted."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a markdown node table into structured relation graph JSON."
    )
    parser.add_argument("source", help="Path to the markdown table file.")
    parser.add_argument("--output", required=True, help="Path to write structured JSON.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON.")
    return parser


def split_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise ConvertError("Markdown 表格行必须以 `|` 开始并以 `|` 结束")
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def parse_table(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ConvertError(f"Markdown 表格不存在: {path}")

    lines = [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 3:
        raise ConvertError("Markdown 表格至少需要表头、分隔行和一行数据")

    headers = split_row(lines[0])
    if headers != REQUIRED_HEADERS:
        raise ConvertError("Markdown 表头不符合预期的单表格式")

    separator = split_row(lines[1])
    if len(separator) != len(headers) or not all(set(cell) <= {"-", ":"} and cell for cell in separator):
        raise ConvertError("Markdown 表格第二行必须是分隔行")

    rows: list[dict[str, str]] = []
    for raw_line in lines[2:]:
        if not raw_line.lstrip().startswith("|"):
            continue
        cells = split_row(raw_line)
        if len(cells) != len(headers):
            raise ConvertError("Markdown 数据行列数与表头不一致")
        rows.append(dict(zip(headers, cells)))

    if not rows:
        raise ConvertError("Markdown 表格没有数据行")
    return rows


def parse_bool(value: str, field_name: str) -> bool:
    normalized = value.strip()
    if normalized == "是":
        return True
    if normalized == "否":
        return False
    raise ConvertError(f"`{field_name}` 只允许填写 `是` 或 `否`")


def parse_number(value: str, field_name: str) -> int | float:
    text = value.strip()
    if not text:
        raise ConvertError(f"`{field_name}` 不能为空")
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    raise ConvertError(f"`{field_name}` 必须是数字")


def parse_node_type(value: str) -> int:
    text = value.strip()
    if not re.fullmatch(r"\d+", text):
        raise ConvertError("`当前节点类型` 必须是整数")
    return int(text)


def require_text(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ConvertError(f"`{field_name}` 不能为空")
    if "\n" in text or "\r" in text:
        raise ConvertError(f"`{field_name}` 不允许换行")
    return text


def convert_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    root_id: str | None = None

    for row in rows:
        is_root = parse_bool(row["是否根节点"], "是否根节点")
        node_id = require_text(row["当前节点ID"], "当前节点ID")
        if node_id in node_ids:
            raise ConvertError(f"当前节点重复出现: {node_id}")
        node_ids.add(node_id)

        parent_id = row["父节点ID"].strip()
        relation = row["关系名称"].strip()

        if is_root:
            if root_id is not None:
                raise ConvertError("只能有一个根节点")
            root_id = node_id
            if parent_id or relation:
                raise ConvertError("根节点行的 `父节点ID` 和 `关系名称` 必须为空")
        else:
            if not parent_id:
                raise ConvertError(f"非根节点 `{node_id}` 必须填写 `父节点ID`")
            if not relation:
                raise ConvertError(f"非根节点 `{node_id}` 必须填写 `关系名称`")

        nodes.append(
            {
                "id": node_id,
                "text": require_text(row["当前节点文本"], "当前节点文本"),
                "x": parse_number(row["当前节点X"], "当前节点X"),
                "y": parse_number(row["当前节点Y"], "当前节点Y"),
                "width": parse_number(row["当前节点宽度"], "当前节点宽度"),
                "height": parse_number(row["当前节点高度"], "当前节点高度"),
                "borderColor": require_text(row["当前节点颜色"], "当前节点颜色"),
                "data": {"type": parse_node_type(row["当前节点类型"])},
            }
        )

        if not is_root:
            lines.append(
                {
                    "id": f"{parent_id}->{node_id}",
                    "from": parent_id,
                    "to": node_id,
                    "text": relation,
                }
            )

    if root_id is None:
        raise ConvertError("必须有且仅有一个根节点")

    return {"rootId": root_id, "nodes": nodes, "lines": lines}


def dump_json(path: Path, payload: Any, pretty: bool) -> None:
    if path.exists():
        raise ConvertError(
            f"Cannot write to {path} because it already exists. Read and then make an edit, or write to a new path."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        if pretty:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        else:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    output_path = Path(args.output).resolve()

    try:
        rows = parse_table(source_path)
        payload = convert_rows(rows)
        dump_json(output_path, payload, pretty=args.pretty)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "source": str(source_path),
                    "output": str(output_path),
                    "rootId": payload["rootId"],
                    "nodeCount": len(payload["nodes"]),
                    "lineCount": len(payload["lines"]),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except ConvertError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Markdown 转结构化 JSON 失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
