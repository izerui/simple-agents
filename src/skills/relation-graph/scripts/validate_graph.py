#!/usr/bin/env python3
"""Validate and auto-fix graph.md before generating the final relation graph JSON.

执行顺序：
1. 结构硬校验（表头、字段合法性、父子引用）— 失败立即报错退出
2. 自动修复布局（消除子树级别重叠，保证最小间距）— 直接写回 graph.md
3. 输出修复摘要
"""

from __future__ import annotations

import argparse
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

# 布局间距常量
MIN_H_GAP = 30   # 同行节点/子树之间最小水平间距
MIN_V_GAP = 20   # 同列节点/子树之间最小垂直间距
CLUSTER_GAP = 80 # 顶层独立根区块之间最小间距


class GraphError(ValueError):
    """Raised when graph.md structure is invalid."""


# ---------------------------------------------------------------------------
# 解析工具
# ---------------------------------------------------------------------------

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
        raise GraphError(f"`NodeType` 仅支持 {sorted(NODE_TYPE_TO_INT)}；请回去修改 graph.md")
    return NODE_TYPE_TO_INT[text]


def normalize_node_semantic(value: str, field_name: str) -> str:
    canonical = require_text(value, field_name)
    if canonical not in ALLOWED_NODE_SEMANTICS:
        raise GraphError(f"`{field_name}` 仅支持 {sorted(ALLOWED_NODE_SEMANTICS)}；请回去修改 graph.md")
    return canonical


def normalize_relation_text(value: str, field_name: str) -> str:
    text = require_text(value, field_name)
    if text not in ALLOWED_RELATION_TEXTS:
        raise GraphError(f"`{field_name}` 只能使用 {sorted(ALLOWED_RELATION_TEXTS)}；请回去修改 graph.md")
    return text


# ---------------------------------------------------------------------------
# 读取 / 写入 graph.md
# ---------------------------------------------------------------------------

def parse_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """返回 (原始行列表, 数据行字典列表)，原始行用于后续回写。"""
    if not path.is_file():
        raise GraphError(f"Markdown 表格不存在: {path}；请回去修改 graph.md")

    raw_lines = path.read_text(encoding="utf-8").splitlines()
    lines = [line.rstrip("\n") for line in raw_lines if line.strip()]
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
    return lines, rows


def write_table(path: Path, header_line: str, sep_line: str, rows: list[dict[str, str]]) -> None:
    """将修正后的行写回 graph.md。"""
    data_lines = []
    for row in rows:
        cells = [row[h] for h in REQUIRED_HEADERS]
        data_lines.append("| " + " | ".join(cells) + " |")
    content = "\n".join([header_line, sep_line] + data_lines) + "\n"
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# 硬校验
# ---------------------------------------------------------------------------

def validate_rows(rows: list[dict[str, str]]) -> dict[str, int]:
    node_defs: dict[str, tuple] = {}
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
        if node_width <= 0 or node_height <= 0:
            raise GraphError("`NodeWidth` 和 `NodeHeight` 必须大于 0；请回去修改 graph.md")
        node_signature = (node_text, node_type, node_x, node_y, node_width, node_height, node_semantic)
        if node_id in node_defs and node_defs[node_id] != node_signature:
            raise GraphError(f"`NodeID` `{node_id}` 重复出现时，节点定义字段必须完全一致；请回去修改 graph.md")
        node_defs[node_id] = node_signature
        parent_id = row["ParentID"].strip()
        relation = row["RelationText"].strip()
        if bool(parent_id) != bool(relation):
            raise GraphError("`ParentID` 和 `RelationText` 必须同时为空，或同时非空；请回去修改 graph.md")
        if relation:
            normalize_relation_text(relation, "RelationText")
            line_count += 1

    for row in rows:
        parent_id = row["ParentID"].strip()
        if parent_id and parent_id not in node_defs:
            raise GraphError(f"父节点 `{parent_id}` 未定义；请回去修改 graph.md")

    return {"nodeCount": len(node_defs), "lineCount": line_count}


# ---------------------------------------------------------------------------
# 布局自动修复
# ---------------------------------------------------------------------------

def build_graph(rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    """构建节点字典和父子关系映射。节点坐标用 float 存储，方便计算。"""
    nodes: dict[str, dict[str, Any]] = {}
    children: dict[str, list[str]] = {}  # parent_id -> [child_id, ...]（有序，去重）

    for row in rows:
        nid = row["NodeID"].strip()
        if nid not in nodes:
            nodes[nid] = {
                "id": nid,
                "x": float(row["NodeX"].strip()),
                "y": float(row["NodeY"].strip()),
                "w": float(row["NodeWidth"].strip()),
                "h": float(row["NodeHeight"].strip()),
            }
        pid = row["ParentID"].strip()
        if pid:
            lst = children.setdefault(pid, [])
            if nid not in lst:
                lst.append(nid)

    return nodes, children


def subtree_ids(nid: str, children: dict[str, list[str]], visited: set[str] | None = None) -> set[str]:
    """返回以 nid 为根的子树中所有节点 ID（含 nid 自身）。"""
    if visited is None:
        visited = set()
    if nid in visited:
        return set()
    visited.add(nid)
    result = {nid}
    for cid in children.get(nid, []):
        result |= subtree_ids(cid, children, visited)
    return result


def bounding_box(ids: set[str], nodes: dict[str, dict[str, Any]]) -> tuple[float, float, float, float]:
    """返回 (min_x, min_y, max_x, max_y)。"""
    xs = [nodes[i]["x"] for i in ids]
    ys = [nodes[i]["y"] for i in ids]
    rxs = [nodes[i]["x"] + nodes[i]["w"] for i in ids]
    bys = [nodes[i]["y"] + nodes[i]["h"] for i in ids]
    return min(xs), min(ys), max(rxs), max(bys)


def translate_subtree(nid: str, children: dict[str, list[str]], nodes: dict[str, dict[str, Any]], dx: float, dy: float) -> None:
    """将以 nid 为根的整棵子树平移 (dx, dy)。"""
    for i in subtree_ids(nid, children):
        nodes[i]["x"] += dx
        nodes[i]["y"] += dy


def dominant_axis(parent: dict[str, Any], child_bb: tuple[float, float, float, float]) -> str:
    """判断子树相对父节点的主方向：'h'（水平）或 'v'（垂直）。"""
    px = parent["x"] + parent["w"] / 2
    py = parent["y"] + parent["h"] / 2
    cx = (child_bb[0] + child_bb[2]) / 2
    cy = (child_bb[1] + child_bb[3]) / 2
    return "h" if abs(cx - px) >= abs(cy - py) else "v"


def fix_siblings(parent_id: str, children: dict[str, list[str]], nodes: dict[str, dict[str, Any]]) -> int:
    """
    修复同一父节点下各子树之间的重叠与间距不足。
    返回修复的冲突数量。
    """
    child_ids = children.get(parent_id, [])
    if len(child_ids) < 2:
        return 0

    parent = nodes[parent_id]
    # 计算每个子树的 bounding box
    bbs: list[tuple[str, tuple[float, float, float, float]]] = [
        (cid, bounding_box(subtree_ids(cid, children), nodes))
        for cid in child_ids
    ]

    # 判断主方向：取第一个子树做参考
    axis = dominant_axis(parent, bbs[0][1])

    fixes = 0

    if axis == "h":
        # 水平方向：按 bb 左边 x 排序，从左到右依次保证间距
        bbs.sort(key=lambda t: t[1][0])
        for i in range(1, len(bbs)):
            prev_cid, prev_bb = bbs[i - 1]
            cur_cid, cur_bb = bbs[i]
            required_left = prev_bb[2] + MIN_H_GAP  # prev_right + gap
            delta = required_left - cur_bb[0]
            if delta > 0:
                translate_subtree(cur_cid, children, nodes, delta, 0)
                # 更新当前及后续 bb
                cur_bb = bounding_box(subtree_ids(cur_cid, children), nodes)
                bbs[i] = (cur_cid, cur_bb)
                fixes += 1
    else:
        # 垂直方向：按 bb 顶边 y 排序，从上到下依次保证间距
        bbs.sort(key=lambda t: t[1][1])
        for i in range(1, len(bbs)):
            prev_cid, prev_bb = bbs[i - 1]
            cur_cid, cur_bb = bbs[i]
            required_top = prev_bb[3] + MIN_V_GAP  # prev_bottom + gap
            delta = required_top - cur_bb[1]
            if delta > 0:
                translate_subtree(cur_cid, children, nodes, 0, delta)
                cur_bb = bounding_box(subtree_ids(cur_cid, children), nodes)
                bbs[i] = (cur_cid, cur_bb)
                fixes += 1

    return fixes


def fix_root_blocks(root_ids: list[str], children: dict[str, list[str]], nodes: dict[str, dict[str, Any]]) -> int:
    """
    修复多个独立根区块之间的重叠。
    策略：按中心 x 排序，从左到右保证水平间距；若垂直方向也有重叠则同时处理。
    返回修复的冲突数量。
    """
    if len(root_ids) < 2:
        return 0

    bbs = [(rid, bounding_box(subtree_ids(rid, children), nodes)) for rid in root_ids]
    bbs.sort(key=lambda t: (t[1][0] + t[1][2]) / 2)  # 按中心 x 排序

    fixes = 0
    for i in range(1, len(bbs)):
        prev_rid, prev_bb = bbs[i - 1]
        cur_rid, cur_bb = bbs[i]
        overlap_w = prev_bb[2] - cur_bb[0]
        if overlap_w > -CLUSTER_GAP:
            delta = overlap_w + CLUSTER_GAP
            translate_subtree(cur_rid, children, nodes, delta, 0)
            cur_bb = bounding_box(subtree_ids(cur_rid, children), nodes)
            bbs[i] = (cur_rid, cur_bb)
            fixes += 1

    return fixes


def fix_residual_overlaps(nodes: dict[str, dict[str, Any]]) -> int:
    """
    兜底：处理上述步骤后仍残余的任意两节点重叠。
    将较右/较下的节点平移出去，不移动整棵子树（此时子树已经由上层修复过）。
    返回修复的冲突数量。
    """
    node_list = list(nodes.values())
    fixes = 0
    for i in range(len(node_list)):
        for j in range(i + 1, len(node_list)):
            a = node_list[i]
            b = node_list[j]
            ow = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oh = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            if ow <= 0 or oh <= 0:
                continue
            # 移动中心偏右/偏下的那个
            if (a["x"] + a["w"] / 2) <= (b["x"] + b["w"] / 2):
                move, stay = b, a
            else:
                move, stay = a, b
            if ow <= oh:
                move["x"] += ow + MIN_H_GAP
            else:
                move["y"] += oh + MIN_V_GAP
            fixes += 1
    return fixes


def center_graph(nodes: dict[str, dict[str, Any]]) -> None:
    """将整张图整体居中到原点附近。"""
    all_ids = set(nodes.keys())
    if not all_ids:
        return
    mn_x, mn_y, mx_x, mx_y = bounding_box(all_ids, nodes)
    cx = (mn_x + mx_x) / 2
    cy = (mn_y + mx_y) / 2
    for node in nodes.values():
        node["x"] -= cx
        node["y"] -= cy


def run_layout_fix(rows: list[dict[str, str]]) -> int:
    """
    执行布局自动修复，直接修改 rows 中的坐标字段。
    返回总修复次数。
    """
    nodes, children = build_graph(rows)

    # 找出所有根节点（无父节点的节点）
    all_ids = set(nodes.keys())
    has_parent: set[str] = set()
    for row in rows:
        pid = row["ParentID"].strip()
        nid = row["NodeID"].strip()
        if pid:
            has_parent.add(nid)
    root_ids = [nid for nid in all_ids if nid not in has_parent]

    total_fixes = 0

    # 1. 修复每个父节点下的兄弟子树重叠（从叶向根，确保内层先修复）
    # 用 BFS 收集所有有子节点的父节点，按深度从深到浅处理
    depth: dict[str, int] = {}

    def compute_depth(nid: str, d: int) -> None:
        if nid in depth and depth[nid] <= d:
            return
        depth[nid] = d
        for cid in children.get(nid, []):
            compute_depth(cid, d + 1)

    for rid in root_ids:
        compute_depth(rid, 0)

    parents_by_depth = sorted(
        [pid for pid in children if pid in nodes],
        key=lambda pid: -depth.get(pid, 0),
    )
    for pid in parents_by_depth:
        total_fixes += fix_siblings(pid, children, nodes)

    # 2. 修复多个独立根区块之间的重叠
    total_fixes += fix_root_blocks(root_ids, children, nodes)

    # 3. 兜底：处理残余的任意节点重叠
    total_fixes += fix_residual_overlaps(nodes)

    # 4. 整体居中
    center_graph(nodes)

    # 5. 将修正后的坐标写回 rows（整数化）
    for row in rows:
        nid = row["NodeID"].strip()
        node = nodes[nid]
        row["NodeX"] = str(int(round(node["x"])))
        row["NodeY"] = str(int(round(node["y"])))
        row["NodeWidth"] = str(int(round(node["w"])))
        row["NodeHeight"] = str(int(round(node["h"])))

    return total_fixes


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate graph.md and auto-fix layout before generating result JSON."
    )
    parser.add_argument("graph", help="Path to the markdown graph table file.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    graph_path = Path(args.graph).resolve()

    try:
        raw_lines, rows = parse_table(graph_path)
    except GraphError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"读取 graph.md 失败: {exc}", file=sys.stderr)
        return 2

    # 步骤 1：硬校验
    try:
        summary = validate_rows(rows)
    except GraphError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # 步骤 2：布局自动修复
    try:
        fixes = run_layout_fix(rows)
    except Exception as exc:  # pragma: no cover
        print(f"布局修复失败: {exc}", file=sys.stderr)
        return 2

    # 步骤 3：写回 graph.md
    header_line = raw_lines[0]
    sep_line = raw_lines[1]
    write_table(graph_path, header_line, sep_line, rows)

    print("校验通过，布局修复完成")
    print(f"输入文件: {graph_path}")
    print(f"节点数量: {summary['nodeCount']}")
    print(f"连线数量: {summary['lineCount']}")
    print(f"布局修复次数: {fixes}")
    print("后续指引: 直接执行 build_graph.py 生成最终 result json 文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
