curl -X POST http://localhost:2024/runs/stream \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "research",
    "input": {
      "messages": [
        {"role": "system", "content": "你是专业助手"},
        {"role": "user", "content": "你好"}
      ]
    },
    "stream_mode": "messages-tuple"
  }'