#!/bin/bash
# 取消所有 LangGraph 运行

API_URL="${LANGGRAPH_API_URL:-http://localhost:2024}"

echo "获取所有运行..."

# 获取所有线程和运行
RUN_IDS=$(curl -s "$API_URL/threads" | python3 -c "
import sys, json
import urllib.request

threads = json.load(sys.stdin)
all_run_ids = []

for t in threads:
    thread_id = t.get('thread_id')
    if not thread_id:
        continue
    try:
        req = urllib.request.Request(f'{API_URL}/threads/{thread_id}/runs')
        with urllib.request.urlopen(req) as resp:
            runs = json.loads(resp.read())
            for r in runs:
                run_id = r.get('run_id')
                if run_id:
                    all_run_ids.append(run_id)
    except:
        pass

for rid in all_run_ids:
    print(rid)
" 2>/dev/null)

if [ -z "$RUN_IDS" ]; then
    echo "没有找到需要取消的运行"
    exit 0
fi

RUN_IDS_ARR=($RUN_IDS)
echo "找到 ${#RUN_IDS_ARR[@]} 个运行需要取消"

# 批量取消
curl -s -X POST "$API_URL/runs/cancel" \
    -H "Content-Type: application/json" \
    -d "{\"run_ids\": $RUN_IDS}"

echo ""
echo "完成!"
