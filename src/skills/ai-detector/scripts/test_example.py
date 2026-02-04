#!/usr/bin/env python3
"""
检测脚本示例和测试
Test examples for AI detection scripts

演示如何使用各个检测脚本
"""

# 示例文本
EXAMPLE_TEXTS = {
    "高风险_AI生成": """
本文采用问卷调查法对大学生网络使用行为进行了深入研究。
研究结果表明，网络使用时间与学习成绩呈显著负相关。
此外，网络使用还对学生的社交能力产生了重要影响。
同时，网络使用也会影响学生的身体健康状况。
综上所述，本研究具有重要的理论和实践意义，
能够为高校教育管理提供重要参考。
    """,

    "中风险_部分AI": """
以大学生网络使用为例，我们调查了5所学校的1200名学生。
数据显示：每天用网超过5小时的同学，期末成绩平均低8.3分。
这个影响在理工科更明显——达到12.1分。
但我们也发现，用网查资料的同学，如果合理控制时间，
成绩反而会提高。
这可能是网络使用的双刃剑效应。
    """,

    "低风险_人工写作": """
大四那年，我发现了这事儿挺有意思。
就说我自己吧，每天刷短视频要花3个小时，
结果期末考砸了——整整掉了10分！
但有意思的是，我室友天天用网查资料，
他的成绩反而提高了5分。
我觉得吧，关键不在用不用网，而在怎么用。
当然，这只是我的一己之见，样本也就我们宿舍几个人。
    """,

    "改写攻击示例": """
我们使用问卷方式调查了学生上网情况。
分析发现，上网时间长的学生，成绩通常较低。
这个结果对学校教育工作有参考价值。
通过标准方法，我们对数据进行了收集和分析。
研究显示，网络对学习有关键影响。
这项研究对教育管理有核心意义。
    """
}


def run_tests():
    """运行所有测试示例"""
    print("="*70)
    print("AI检测脚本测试示例".center(70))
    print("="*70)
    print()

    # 测试1: 基础词汇检测
    print("\n【测试1: AI词汇密度检测】")
    print("-"*70)

    from count_ai_words import count_ai_words

    for name, text in EXAMPLE_TEXTS.items():
        print(f"\n{name}:")
        result = count_ai_words(text)
        print(f"  AI词汇密度: {result['density']:.1f}个/1000字")
        print(f"  风险等级: {result['risk_level']}")

    # 测试2: 综合检测
    print("\n\n【测试2: 综合检测】")
    print("-"*70)

    try:
        from comprehensive_detector import ComprehensiveAIDetector

        detector = ComprehensiveAIDetector()

        for name, text in EXAMPLE_TEXTS.items():
            print(f"\n{name}:")
            result = detector.detect(text)
            print(f"  综合评分: {result['overall_score']:.1%}")
            print(f"  风险等级: {result['risk_level']}")
    except ImportError:
        print("综合检测器需要安装依赖: pip install jieba numpy")

    # 测试3: 改写攻击检测
    print("\n\n【测试3: 改写攻击检测】")
    print("-"*70)

    try:
        from detect_paraphrasing import ParaphrasingDetector

        pd = ParaphrasingDetector()

        test_paraphrase = EXAMPLE_TEXTS["改写攻击示例"]
        result = pd.detect(test_paraphrase)

        print(f"\n改写攻击示例:")
        print(f"  改写概率: {result['paraphrasing_probability']:.1%}")
        print(f"  风险等级: {result['risk_level']}")
        if result['indicators']:
            print(f"  检测到的问题:")
            for indicator in result['indicators']:
                print(f"    - {indicator}")
    except ImportError:
        print("改写攻击检测器需要安装依赖: pip install jieba numpy")

    print("\n" + "="*70)
    print("测试完成！".center(70))
    print("="*70)
    print("\n提示:")
    print("- 高风险文本应该被检测出AI特征")
    print("- 低风险文本应该通过检测")
    print("- 改写攻击应该被识别")
    print("\n如需运行完整检测，请使用:")
    print("  python comprehensive_detector.py your_file.txt")
    print("="*70 + "\n")


def interactive_demo():
    """交互式演示"""
    print("\n" + "="*70)
    print("交互式AI检测演示".center(70))
    print("="*70)
    print("\n请输入一段文本进行检测（输入 'quit' 退出）:")
    print("-"*70)

    try:
        from comprehensive_detector import ComprehensiveAIDetector
        detector = ComprehensiveAIDetector()

        while True:
            print("\n您的文本:")
            text = input("> ")

            if text.lower() in ['quit', 'exit', 'q', '退出']:
                print("退出演示。")
                break

            if len(text.strip()) < 50:
                print("文本太短，请输入至少50个字符。")
                continue

            print("\n检测中...")
            result = detector.detect(text)

            print(f"\n检测结果:")
            print(f"  综合评分: {result['overall_score']:.1%}")
            print(f"  风险等级: {result['risk_level']}")

            if result['overall_score'] > 0.5:
                print(f"\n建议: 文本表现出AI特征，建议修改")
            else:
                print(f"\n良好: 未检测到明显AI特征")

    except ImportError:
        print("错误: 需要先安装依赖")
        print("pip install jieba numpy")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_demo()
    else:
        run_tests()
