import uuid

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# 在所有其他导入之前加载环境变量
load_dotenv(dotenv_path='.env', verbose=True)

from analysis import agent


async def run_agent_node_stream():
    inputs = {"messages": [HumanMessage(content="读取文件内容帮我汇总后，生成一个新的汇总文件。")]}

    print("--- 开始执行 (使用 astream_events 监控节点) ---")

    # 在调用时传入 recursion_limit
    # 每次运行都生成一个独一无二的 ID
    config = {
        "thread_id": str(uuid.uuid4()),
        "recursion_limit": 100  # 默认是 25 改成 100
    }

    # astream_events 迭代的是一个个事件
    async for event in agent.astream_events(inputs, version="v1", config=config):
        kind = event["event"]

        # 我们只关心节点结束的事件 (on_chain_end)
        # 这里的 event["name"] 就是节点名
        if kind == "on_chain_end":
            node_name = event["name"]

            # 获取该节点的输出数据
            # 注意：event["data"]["output"] 的结构取决于你的 State 定义
            node_output = event["data"].get("output")

            print(f"✅ 节点 [{node_name}] 执行完毕")
            print(f"   输出内容: {node_output}\n")

        # 2. 监控 Token 级别 (打字机)
        elif kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                print(content, end="", flush=True)  # 实时打印字

    print("--- 执行结束 ---")


# 运行
if __name__ == "__main__":
    import asyncio
    asyncio.run(run_agent_node_stream())