#!/usr/bin/env python3
"""
Thread 用户管理测试

测试流程：
1. 创建带有用户标记的 thread
2. 通过 user_id 查询该用户的 threads 列表

使用方法：
  python test_thread_user_management.py
"""

import asyncio
import os
import sys
import uuid
from typing import Optional

from langgraph_sdk import get_client


def get_api_url() -> str:
    return os.getenv("LANGGRAPH_API_URL", "https://agent.schoopia.com")


# ==================== 测试函数 ====================

async def test_threads():
    """测试: 创建多个 threads、搜索、对话"""
    print("\n" + "=" * 60)
    print("🧪 测试: threads 功能")
    print("=" * 60)

    from langchain_core.messages import HumanMessage

    client = get_client(url=get_api_url(), api_key="")
    test_user_id = 'user001'

    # 创建 3 个 threads
    for i in range(3):
        thread = await client.threads.create(
            metadata={"user_id": test_user_id, "index": i, "name": f"测试线程_{i}"}
        )
        print(f"✅ 创建 thread {i+1}: {thread['thread_id']}")

    # 搜索
    threads = await client.threads.search(metadata={"user_id": test_user_id}, limit=999)
    print(f"✅ 搜索成功: 找到 {len(threads)} 个 threads")

    if len(threads) < 3:
        print(f"❌ 验证失败: 只找到 {len(threads)} 个")
        return False

    # 搜索不存在的用户
    fake_user_id = f"non_existent_{uuid.uuid4().hex[:8]}"
    fake_threads = await client.threads.search(metadata={"user_id": fake_user_id}, limit=999)
    print(f"✅ 搜索不存在用户: 找到 {len(fake_threads)} 个 threads")

    if len(fake_threads) != 0:
        print("❌ 验证失败: 不存在的用户应返回空结果")
        return False

    # 对话
    for i, t in enumerate(threads[:3]):
        print(f"💬 Thread {i+1} 发送消息: '你好'")
        await client.runs.create(
            thread_id=t['thread_id'],
            assistant_id='research',
            input={"messages": [HumanMessage(content="你好")]},
            if_not_exists='create'
        )
        print(f"✅ Thread {i+1} 对话成功")

    # 全部对话完后搜索
    result = await client.threads.search(metadata={"user_id": test_user_id})
    print(f"✅ 全部对话后搜索: 找到 {len(result)} 个 threads")

    # 搜索验证
    result = await client.threads.search(metadata={"user_id": test_user_id})
    if len(result) > 0:
        print("✅ 验证通过")
        return True
    else:
        print("❌ 验证失败")
        return False


# ==================== 主函数 ====================

async def main():
    """运行所有测试"""
    print("🚀 Thread 用户管理测试")
    print(f"API URL: {get_api_url()}")
    print("=" * 60)

    results = [
        ("threads 功能", await test_threads()),
    ]

    # 汇总
    print("\n" + "=" * 60)
    print("📊 测试结果")
    print("=" * 60)

    passed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if result:
            passed += 1

    print(f"\n总计: {passed}/{len(results)} 通过")

    if passed == len(results):
        print("\n🎉 所有测试通过!")
        return True
    else:
        print(f"\n⚠️  {len(results) - passed} 个测试失败")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ 测试被中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
