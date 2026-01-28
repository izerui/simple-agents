# -*- coding: utf-8 -*-
"""交互式测试程序 - 支持多轮对话和自定义问题"""
import asyncio
from pathlib import Path
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

# 加载环境变量并添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(dotenv_path=project_root / '.env')

from src.graph import agent
from tests.agents.output_handler import output_handler, print_header, print_user_message, print_footer


class InteractiveAgent:
    """交互式Agent会话管理器"""
    
    def __init__(self):
        self.thread_id = "interactive_session_" + str(asyncio.get_event_loop().time())
        self.running = True
        self.config = RunnableConfig(
            configurable={
                "thread_id": self.thread_id,
                "tool_timeout": 60.0  # 交互模式给更长的超时时间
            },
            recursion_limit=500,
        )
        print(f"\n📋 会话ID: {self.thread_id}")
        print("💡 提示: 输入 'quit', 'exit', 'q' 或 Ctrl+C 退出程序")
    
    async def process_message(self, user_message: str):
        """处理用户消息"""
        if not user_message.strip():
            return
        
        # 显示用户问题
        print_user_message(user_message)
        
        # 创建输入
        inputs = {"messages": [HumanMessage(content=user_message)]}
        
        # 执行 agent（流式输出）
        try:
            async for event in agent.astream_events(inputs, version="v2", config=self.config):
                output_handler(event)
        except KeyboardInterrupt:
            print("\n\n⚠️  中断当前请求...")
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
    
    def should_exit(self, user_input: str) -> bool:
        """检查是否应该退出"""
        exit_commands = ['quit', 'exit', 'q']
        return user_input.strip().lower() in exit_commands
    
    async def run(self):
        """运行交互式会话"""
        print_header("交互式 Agent 测试")
        
        print("🎉 欢迎使用交互式 Agent 测试程序！")
        print("📝 你可以随时输入问题与 Agent 进行对话")
        print("🔄 对话上下文会被保留，支持多轮对话")
        print("🛠️  Agent 可以使用工具操作文件系统、分析 PDF 等")
        print()
        
        while self.running:
            try:
                # 获取用户输入
                user_input = input("👤 你: ")
                
                # 检查退出命令
                if self.should_exit(user_input):
                    print("\n👋 再见！")
                    break
                
                # 处理消息
                await self.process_message(user_input)
                
                # 添加空行分隔
                print()
                
            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
            except EOFError:
                print("\n\n👋 再见！")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                print("继续对话...")
                print()


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("   🤖 交互式 Agent 测试程序")
    print("=" * 60 + "\n")
    
    interactive_agent = InteractiveAgent()
    await interactive_agent.run()
    
    print_footer("交互式测试结束")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 程序已退出")