curl -X POST https://agent.schoopia.com/runs/stream \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "research",
    "input": {
      "messages": [
        {"role": "system", "content": "你是一个专业的技术顾问，擅长回答编程问题。"},
        {"role": "user", "content": "测试10个工具调用"}
      ]
    },
    "config": {
    },
    "metadata": {
      "user_id": "user001",
      "name": "你好，请介绍一下自己"
    },
    "stream_mode": ["messages-tuple", "custom"]
  }'
