# -*- coding: utf-8 -*-
"""
依赖安装执行器安全限制演示

演示 DependencyExecutor 如何通过严格的命令验证来保护环境安全，
防止任何可能破坏现有环境的操作。
"""
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sandbox.dependency_executor import DependencyExecutor
import tempfile


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def test_restriction(test_name, command, expected_rejection=True):
    """测试单个限制"""
    print("\n测试: {}".format(test_name))
    print("命令: {}".format(command))
    
    # 创建临时执行器
    temp_dir = tempfile.mkdtemp()
    executor = DependencyExecutor(root_dir=temp_dir)
    
    # 验证命令
    is_valid, error_msg = executor._parse_command(command)
    
    if expected_rejection:
        if not is_valid:
            print("✓ 成功拒绝")
            print("  原因: {}".format(error_msg.split('\n')[1]))
        else:
            print("✗ 失败 - 应该拒绝但被接受")
    else:
        if is_valid:
            print("✓ 成功接受")
        else:
            print("✗ 失败 - 应该接受但被拒绝")
            print("  错误: {}".format(error_msg))
    
    # 清理
    import shutil
    shutil.rmtree(temp_dir)
    
    return not is_valid if expected_rejection else is_valid


def main():
    """主函数"""
    print_header("依赖安装执行器安全限制演示")
    
    print("\n设计原则:")
    print("  - 只允许安装新的依赖包")
    print("  - 禁止任何可能改变现有环境的操作")
    print("  - 确保环境的稳定性和可预测性")
    
    total_tests = 0
    passed_tests = 0
    
    # ============================================
    # 第一部分：批量安装限制
    # ============================================
    print_header("限制 1: 禁止批量安装")
    print("\n原因: 批量安装可能导致不可控的环境变更")
    
    tests = [
        ("使用 -r 选项", "uv pip install -r requirements.txt"),
        ("使用 --requirement 选项", "uv pip install --requirement requirements.txt"),
        ("使用 -r 与其他选项组合", "uv pip install -r requirements.txt --verbose"),
    ]
    
    for test_name, command in tests:
        total_tests += 1
        if test_restriction(test_name, command, expected_rejection=True):
            passed_tests += 1
    
    # ============================================
    # 第二部分：卸载操作限制
    # ============================================
    print_header("限制 2: 禁止卸载操作")
    print("\n原因: 卸载操作会移除已存在的包，可能破坏环境")
    
    tests = [
        ("基本卸载命令", "uv pip uninstall requests"),
        ("卸载多个包", "uv pip uninstall requests numpy"),
        ("卸载带 -y 选项", "uv pip uninstall -y requests"),
    ]
    
    for test_name, command in tests:
        total_tests += 1
        if test_restriction(test_name, command, expected_rejection=True):
            passed_tests += 1
    
    # ============================================
    # 第三部分：升级操作限制
    # ============================================
    print_header("限制 3: 禁止升级已安装的包")
    print("\n原因: 升级操作会改变现有包的版本，可能导致兼容性问题")
    
    tests = [
        ("使用 --upgrade 选项", "uv pip install --upgrade requests"),
        ("使用 -U 选项", "uv pip install -U requests"),
        ("升级多个包", "uv pip install --upgrade requests numpy"),
        ("升级带其他选项", "uv pip install --upgrade --verbose requests"),
        ("在包名后指定升级", "uv pip install requests --upgrade"),
    ]
    
    for test_name, command in tests:
        total_tests += 1
        if test_restriction(test_name, command, expected_rejection=True):
            passed_tests += 1
    
    # ============================================
    # 第四部分：强制重装限制
    # ============================================
    print_header("限制 4: 禁止强制重新安装")
    print("\n原因: 强制重装会覆盖现有包，可能导致配置丢失")
    
    tests = [
        ("使用 --force-reinstall 选项", "uv pip install --force-reinstall requests"),
        ("使用 --reinstall 选项", "uv pip install --reinstall requests"),
        ("重装多个包", "uv pip install --force-reinstall requests numpy"),
        ("重装带其他选项", "uv pip install --reinstall --verbose requests"),
    ]
    
    for test_name, command in tests:
        total_tests += 1
        if test_restriction(test_name, command, expected_rejection=True):
            passed_tests += 1
    
    # ============================================
    # 第五部分：升级策略限制
    # ============================================
    print_header("限制 5: 禁止升级策略")
    print("\n原因: 升级策略会改变包依赖关系的处理方式")
    
    tests = [
        ("使用 eager 策略", "uv pip install --upgrade-strategy eager requests"),
        ("使用 only-if-needed 策略", "uv pip install --upgrade-strategy only-if-needed requests"),
        ("使用 to-satisfy-only 策略", "uv pip install --upgrade-strategy to-satisfy-only requests"),
    ]
    
    for test_name, command in tests:
        total_tests += 1
        if test_restriction(test_name, command, expected_rejection=True):
            passed_tests += 1
    
    # ============================================
    # 第六部分：忽略已安装版本限制
    # ============================================
    print_header("限制 6: 禁止忽略已安装版本")
    print("\n原因: 忽略已安装版本会导致版本冲突和不可预测的行为")
    
    tests = [
        ("使用 --ignore-installed 选项", "uv pip install --ignore-installed requests"),
        ("忽略已安装带其他选项", "uv pip install --ignore-installed --verbose requests"),
    ]
    
    for test_name, command in tests:
        total_tests += 1
        if test_restriction(test_name, command, expected_rejection=True):
            passed_tests += 1
    
    # ============================================
    # 第七部分：允许的安全操作
    # ============================================
    print_header("允许的安全操作")
    print("\n以下操作不会改变现有环境，因此被允许")
    
    tests = [
        ("基本安装", "uv pip install requests"),
        ("安装多个新包", "uv pip install requests numpy pandas"),
        ("带详细输出", "uv pip install --verbose requests"),
        ("带安静模式", "uv pip install --quiet requests"),
        ("使用 --dry-run", "uv pip install --dry-run requests"),
        ("使用 --no-deps", "uv pip install --no-deps requests"),
        ("指定索引 URL", "uv pip install --index-url https://pypi.org/simple/ requests"),
        ("列出已安装包", "uv pip list"),
        ("列出带格式", "uv pip list --format=json"),
        ("显示包信息", "uv pip show requests"),
        ("显示包文件", "uv pip show --files requests"),
        ("冻结依赖", "uv pip freeze"),
        ("冻结所有包", "uv pip freeze --all"),
        ("检查依赖冲突", "uv pip check"),
    ]
    
    for test_name, command in tests:
        total_tests += 1
        if test_restriction(test_name, command, expected_rejection=False):
            passed_tests += 1
    
    # ============================================
    # 第八部分：命令格式验证
    # ============================================
    print_header("命令格式验证")
    print("\n验证命令必须以 'uv pip' 开头")
    
    tests = [
        ("非 uv pip 命令", "pip install requests"),
        ("Python 代码执行", "python -c 'print(1)'"),
        ("Shell 命令", "ls -la"),
        ("npm 安装", "npm install"),
        ("不完整的命令", "uv pip"),
    ]
    
    for test_name, command in tests:
        total_tests += 1
        if test_restriction(test_name, command, expected_rejection=True):
            passed_tests += 1
    
    # ============================================
    # 第九部分：组合限制测试
    # ============================================
    print_header("组合限制测试")
    print("\n测试包含多个危险选项的命令")
    
    tests = [
        ("升级 + 重装", "uv pip install --upgrade --force-reinstall requests"),
        ("批量 + 升级", "uv pip install -r requirements.txt --upgrade"),
        ("重装 + 忽略已安装", "uv pip install --reinstall --ignore-installed requests"),
        ("升级策略 + 重装", "uv pip install --upgrade-strategy eager --force-reinstall requests"),
    ]
    
    for test_name, command in tests:
        total_tests += 1
        # 注意：由于命令验证会在第一个危险选项时返回，所以应该被拒绝
        if test_restriction(test_name, command, expected_rejection=True):
            passed_tests += 1
    
    # ============================================
    # 总结
    # ============================================
    print_header("测试总结")
    
    print("\n总测试数: {}".format(total_tests))
    print("通过测试: {}".format(passed_tests))
    print("失败测试: {}".format(total_tests - passed_tests))
    print("\n通过率: {:.1f}%".format(passed_tests / total_tests * 100 if total_tests > 0 else 0))
    
    if passed_tests == total_tests:
        print("\n✓ 所有安全限制测试通过！")
        print("\nDependencyExecutor 能够有效地防止破坏环境的操作。")
    else:
        print("\n✗ 部分测试失败，请检查安全限制的实现。")
    
    print("\n" + "=" * 70)
    print("安全限制演示完成")
    print("=" * 70 + "\n")
    
    return 0 if passed_tests == total_tests else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)