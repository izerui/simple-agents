#!/usr/bin/env python3
"""Materialize append-only JSONL records into a structured relation graph JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class MaterializeError(ValueError):
    """Raised when the JSONL payload cannot be materialized."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize relation graph JSONL records into structured JSON."
    )
    parser.add_argument("source", help="Path to the append-only structured JSONL file.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the materialized structured JSON file.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON.")
    return parser


def load_jsonl(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MaterializeError(f"结构化产物 JSONL 不存在: {path}")

    root_id: str | None = None
    datetime_value: int | float | None = None
    nodes: dict[str, dict[str, Any]] = {}
    lines: dict[str, dict[str, Any]] = {}

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MaterializeError(
                    f"第 {line_number} 行不是合法 JSON: {exc.msg}"
                ) from exc

            if not isinstance(record, dict):
                raise MaterializeError(f"第 {line_number} 行必须是 JSON 对象")

            kind = record.get("kind")
            if kind == "meta":
                value = record.get("rootId")
                if value is not None:
                    if not isinstance(value, str) or not value.strip():
                        raise MaterializeError(f"第 {line_number} 行的 rootId 必须是非空字符串")
                    root_id = value.strip()
                if "datetime" in record:
                    if not isinstance(record["datetime"], (int, float)):
                        raise MaterializeError(f"第 {line_number} 行的 datetime 必须是数字")
                    datetime_value = record["datetime"]
                continue

            if kind == "node":
                node_id = record.get("id")
                if not isinstance(node_id, str) or not node_id.strip():
                    raise MaterializeError(f"第 {line_number} 行的节点 id 必须是非空字符串")
                payload = dict(record)
                payload.pop("kind", None)
                nodes[node_id] = payload
                continue

            if kind == "line":
                line_id = record.get("id")
                if not isinstance(line_id, str) or not line_id.strip():
                    raise MaterializeError(f"第 {line_number} 行的连线 id 必须是非空字符串")
                payload = dict(record)
                payload.pop("kind", None)
                lines[line_id] = payload
                continue

            raise MaterializeError(
                f"第 {line_number} 行的 kind 仅支持 meta、node、line"
            )

    if root_id is None:
        raise MaterializeError("JSONL 中缺少 meta 记录或 rootId")
    if not nodes:
        raise MaterializeError("JSONL 中至少要有一个 node 记录")

    result: dict[str, Any] = {
        "rootId": root_id,
        "nodes": list(nodes.values()),
        "lines": list(lines.values()),
    }
    if datetime_value is not None:
        result["datetime"] = datetime_value
    return result


def dump_json(path: Path, payload: Any, pretty: bool) -> None:
    if path.exists():
        raise MaterializeError(f"Cannot write to {path} because it already exists.")

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
        payload = load_jsonl(source_path)
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
    except MaterializeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"结构化产物物化失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
