#!/bin/bash

# 读取 langgraph.json 并设置 LANGSERVE_GRAPHS 环境变量
set -e

# 使用 Python 解析 langgraph.json 并构建 LANGSERVE_GRAPHS
export LANGSERVE_GRAPHS=$(python3 << 'EOF'
import json
import os

# 读取 langgraph.json
with open('/deps/simple-agents/langgraph.json', 'r') as f:
    config = json.load(f)

graphs = config.get('graphs', {})

# 构建新的 graphs 字典，将路径转换为绝对路径
new_graphs = {}
for name, path in graphs.items():
    # 移除 ./ 前缀
    if path.startswith('./'):
        path = path[2:]
    new_graphs[name] = f'/deps/simple-agents/{path}'

# 输出 JSON 字符串
print(json.dumps(new_graphs))
EOF
)

echo "LANGSERVE_GRAPHS set to: $LANGSERVE_GRAPHS"

# 执行传入的命令
exec "$@"