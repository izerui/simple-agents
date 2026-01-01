# -*- coding: utf-8 -*-
"""批量运行所有独立的 agent 测试

这个脚本会依次运行 tests/agents 目录下的所有独立测试文件。
"""
import asyncio
import sys
from pathlib import Path


def get_test_runners():
    """获取所有测试运行器文件"""
    agents_dir = Path(__file__).parent
    runners = sorted(agents_dir.glob("run_*.py"))
    
    # 过滤掉 __pycache__ 和非测试文件
    runners = [r for r in runners if r.name != "run_all.py" and not r.name.startswith("__")]
    
    return runners


async def run_single_test(test_file):
    """运行单个测试"""
    print(f"\n{'=' * 80}")
    print(f"🚀 运行测试: {test_file.name}")
    print(f"{'=' * 80}\n")
    
    try:
        # 动态导入并运行测试
        import importlib.util
        spec = importlib.util.spec_from_file_location("test_module", test_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_module"] = module
        spec.loader.exec_module(module)
        
        # 运行测试
        await module.run_test()
        
        print(f"\n✅ {test_file.name} 执行成功\n")
        return True, None
        
    except Exception as e:
        print(f"\n❌ {test_file.name} 执行失败: {str(e)}\n")
        return False, str(e)


async def main():
    """主函数：运行所有测试"""
    print("\n" + "=" * 80)
    print("📦 批量运行所有 Agent 独立测试")
    print("=" * 80)
    
    runners = get_test_runners()
    
    if not runners:
        print("❌ 未找到任何测试运行器文件")
        return
    
    print(f"\n找到 {len(runners)} 个测试运行器:")
    for runner in runners:
        print(f"  - {runner.name}")
    
    print(f"\n{'=' * 80}")
    print("开始执行测试...")
    print(f"{'=' * 80}\n")
    
    results = []
    success_count = 0
    failure_count = 0
    
    for runner in runners:
        success, error = await run_single_test(runner)
        results.append((runner.name, success, error))
        
        if success:
            success_count += 1
        else:
            failure_count += 1
    
    # 打印总结
    print("\n\n" + "=" * 80)
    print("📊 测试执行总结")
    print("=" * 80)
    
    print(f"\n总计: {len(runners)} 个测试")
    print(f"✅ 成功: {success_count} 个")
    print(f"❌ 失败: {failure_count} 个")
    
    if failure_count > 0:
        print(f"\n失败的测试:")
        for name, success, error in results:
            if not success:
                print(f"  - {name}: {error}")
    
    print(f"\n{'=' * 80}")
    print("所有测试执行完成！")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)