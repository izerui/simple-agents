#!/usr/bin/env python3
"""Build a relation graph result JSON from graph.md."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from validate_graph import GraphError, build_payload, parse_table


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a relation graph result JSON from graph.md after validation."
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    graph_path = Path(args.graph).resolve()

    try:
        output_path = resolve_output_path(args.output)
        rows = parse_table(graph_path)
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
