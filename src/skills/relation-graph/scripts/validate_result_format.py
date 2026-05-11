#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终结果 JSON 格式校验脚本

功能：基于 schema.json 对最终结果 JSON 进行格式校验，确保符合系统对接要求。

用法：
    python3 validate_result_format.py <result_json_path>

示例：
    python3 validate_result_format.py /output/result.json
    python3 validate_result_format.py /output/result-2.json
"""

import json
import sys
import os
from pathlib import Path

def load_json(file_path: str) -> dict:
    """加载 JSON 文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析错误: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"❌ 文件不存在: {file_path}")
        sys.exit(1)

def get_schema_path() -> str:
    """获取 schema.json 路径"""
    # 脚本所在目录
    script_dir = Path(__file__).parent
    # schema.json 相对于脚本的路径
    schema_path = script_dir.parent / "references" / "schema.json"

    if not schema_path.exists():
        print(f"❌ schema.json 不存在: {schema_path}")
        sys.exit(1)

    return str(schema_path)

def validate_with_schema(data: dict, schema: dict) -> list:
    """使用 JSON Schema 校验数据"""
    errors = []

    try:
        import jsonschema
        from jsonschema import validate, ValidationError

        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            # 格式化错误信息
            path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "根节点"
            errors.append(f"路径 [{path}]: {e.message}")

    except ImportError:
        # 如果没有安装 jsonschema，使用内置校验
        errors = validate_builtin(data, schema)

    return errors

def validate_builtin(data: dict, schema: dict) -> list:
    """内置校验逻辑（当 jsonschema 库不可用时）"""
    errors = []

    # 1. 校验必需字段
    required_fields = schema.get('required', [])
    for field in required_fields:
        if field not in data:
            errors.append(f"缺少必需字段: {field}")

    # 2. 校验 rootId
    if 'rootId' in data:
        root_id_schema = schema.get('properties', {}).get('rootId', {})
        if root_id_schema.get('type') == 'string':
            if not isinstance(data['rootId'], str):
                errors.append("rootId 必须是字符串")
            elif root_id_schema.get('minLength', 0) > 0 and len(data['rootId']) == 0:
                errors.append("rootId 不能为空")

    # 3. 校验 nodes
    if 'nodes' in data:
        nodes = data['nodes']
        nodes_schema = schema.get('properties', {}).get('nodes', {})

        if nodes_schema.get('type') == 'array':
            if not isinstance(nodes, list):
                errors.append("nodes 必须是数组")
            elif nodes_schema.get('minItems', 0) > 0 and len(nodes) < nodes_schema['minItems']:
                errors.append(f"nodes 至少需要 {nodes_schema['minItems']} 个元素")
            else:
                # 校验每个节点
                node_schema = schema.get('$defs', {}).get('node', {})
                node_ids = set()
                for i, node in enumerate(nodes):
                    node_errors = validate_node_builtin(node, node_schema, i, node_ids)
                    errors.extend(node_errors)

    # 4. 校验 lines
    if 'lines' in data:
        lines = data['lines']
        lines_schema = schema.get('properties', {}).get('lines', {})

        if lines_schema.get('type') == 'array':
            if not isinstance(lines, list):
                errors.append("lines 必须是数组")
            else:
                # 获取所有节点 ID
                node_ids = {n['id'] for n in data.get('nodes', []) if 'id' in n}
                # 校验每条连线
                line_schema = schema.get('$defs', {}).get('line', {})
                line_ids = set()
                for i, line in enumerate(lines):
                    line_errors = validate_line_builtin(line, line_schema, i, line_ids, node_ids)
                    errors.extend(line_errors)

    return errors

def validate_node_builtin(node: dict, schema: dict, index: int, node_ids: set) -> list:
    """校验单个节点"""
    errors = []
    prefix = f"nodes[{index}]"

    # 必需字段
    required = schema.get('required', [])
    for field in required:
        if field not in node:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")

    # id 校验
    if 'id' in node:
        if not isinstance(node['id'], str) or len(node['id']) == 0:
            errors.append(f"{prefix}: id 必须是非空字符串")
        elif node['id'] in node_ids:
            errors.append(f"{prefix}: id 重复 '{node['id']}'")
        else:
            node_ids.add(node['id'])

    # text 校验
    if 'text' in node:
        if not isinstance(node['text'], str):
            errors.append(f"{prefix}: text 必须是字符串")
        elif '\n' in node['text'] or '\r' in node['text']:
            errors.append(f"{prefix}: text 不允许换行")

    # type 校验
    if 'type' in node:
        type_schema = schema.get('properties', {}).get('type', {})
        allowed_values = type_schema.get('enum', [])
        if allowed_values and node['type'] not in allowed_values:
            errors.append(f"{prefix}: type 必须是 {allowed_values} 之一")

    # 坐标和尺寸校验
    for field in ['x', 'y', 'width', 'height']:
        if field in node:
            if not isinstance(node[field], (int, float)):
                errors.append(f"{prefix}: {field} 必须是数值")

    # data.type 校验（知识类型）
    if 'data' in node and isinstance(node['data'], dict):
        if 'type' in node['data']:
            data_schema = schema.get('$defs', {}).get('nodeData', {})
            type_schema = data_schema.get('properties', {}).get('type', {})
            allowed_types = type_schema.get('enum', [])
            if allowed_types and node['data']['type'] not in allowed_types:
                errors.append(f"{prefix}: data.type 必须是 {allowed_types} 之一")

    return errors

def validate_line_builtin(line: dict, schema: dict, index: int, line_ids: set, node_ids: set) -> list:
    """校验单条连线"""
    errors = []
    prefix = f"lines[{index}]"

    # 必需字段
    required = schema.get('required', [])
    for field in required:
        if field not in line:
            errors.append(f"{prefix}: 缺少必需字段 '{field}'")

    # id 校验
    if 'id' in line:
        if not isinstance(line['id'], str) or len(line['id']) == 0:
            errors.append(f"{prefix}: id 必须是非空字符串")
        elif line['id'] in line_ids:
            errors.append(f"{prefix}: id 重复 '{line['id']}'")
        else:
            line_ids.add(line['id'])

    # from/to 校验
    for field in ['from', 'to']:
        if field in line:
            if not isinstance(line[field], str) or len(line[field]) == 0:
                errors.append(f"{prefix}: {field} 必须是非空字符串")
            elif line[field] not in node_ids:
                errors.append(f"{prefix}: {field} 引用的节点不存在 '{line[field]}'")

    # text 校验
    if 'text' in line:
        if not isinstance(line['text'], str):
            errors.append(f"{prefix}: text 必须是字符串")
        elif '\n' in line['text'] or '\r' in line['text']:
            errors.append(f"{prefix}: text 不允许换行")

    return errors

def main():
    if len(sys.argv) < 2:
        print("用法: python3 validate_result_format.py <result_json_path>")
        print("示例: python3 validate_result_format.py /output/result.json")
        sys.exit(1)

    result_path = sys.argv[1]
    schema_path = get_schema_path()

    print(f"📋 正在校验: {result_path}")
    print(f"📄 使用 Schema: {schema_path}")

    # 加载 JSON
    data = load_json(result_path)

    # 加载 Schema
    schema = load_json(schema_path)

    # 执行校验
    errors = validate_with_schema(data, schema)

    if errors:
        print(f"\n❌ 格式校验失败，发现 {len(errors)} 个错误:\n")
        for error in errors:
            print(f"  - {error}")
        print("\n⚠️  生成的 JSON 格式不符合系统对接要求，请检查 graph.md 后重新生成。")
        sys.exit(1)
    else:
        print("✅ 格式校验通过，JSON 结构符合系统对接要求。")
        sys.exit(0)

if __name__ == '__main__':
    main()
