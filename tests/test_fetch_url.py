"""
测试 fetch_url 工具方法的完整测试脚本
"""

import json
import sys
from src.tools.fetch import fetch_url, WEB_READER_AVAILABLE


def print_separator(title: str = ""):
    """打印分隔线"""
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)


def print_result(result: dict, show_content: bool = False):
    """打印测试结果"""
    print(f"✅ Success: {result.get('success')}")
    print(f"📝 Title: {result.get('title', 'N/A')}")
    print(f"🔗 URL: {result.get('url', 'N/A')}")
    print(f"🔧 Method: {result.get('method', 'N/A')}")
    print(f"📊 Status Code: {result.get('status_code', 'N/A')}")
    print(f"📏 Content Length: {result.get('content_length', 'N/A')} chars")
    print(f"⏰ Fetched At: {result.get('fetched_at', 'N/A')}")
    print(f"💬 Message: {result.get('message', 'N/A')}")

    if not result.get('success'):
        print(f"❌ Error: {result.get('error', 'Unknown error')}")

    if show_content and result.get('markdown_content'):
        content = result['markdown_content']
        print(f"\n📄 Content Preview (first 300 chars):")
        print("-" * 40)
        print(content[:300] + "..." if len(content) > 300 else content)
        print("-" * 40)


def test_dependencies():
    """测试 1: 检查依赖是否安装"""
    print_separator("测试 1: 检查依赖")
    print(f"Web Reader 依赖可用: {WEB_READER_AVAILABLE}")

    if WEB_READER_AVAILABLE:
        print("✅ 所有依赖已安装")
        try:
            import requests
            print(f"   - requests: {requests.__version__}")
        except ImportError:
            print("   - requests: 未安装")

        try:
            from bs4 import BeautifulSoup
            print(f"   - beautifulsoup4: 已安装")
        except ImportError:
            print("   - beautifulsoup4: 未安装")

        try:
            from playwright.sync_api import sync_playwright
            print(f"   - playwright: 已安装")
        except ImportError:
            print("   - playwright: 未安装")
    else:
        print("❌ Web Reader 依赖未安装")
        print("   请运行: pip install requests beautifulsoup4 playwright")
        print("   然后运行: playwright install chromium")
        return False
    return True


def test_invalid_url():
    """测试 2: 无效 URL"""
    print_separator("测试 2: 无效 URL")

    test_urls = [
        "not-a-url",
        "ftp://example.com",
        "",
        "javascript:void(0)"
    ]

    for url in test_urls:
        print(f"\n测试 URL: {url}")
        result = fetch_url.invoke({"url": url})
        print(f"   Success: {result.get('success')}")
        print(f"   Error: {result.get('error', 'N/A')}")


def test_simple_website():
    """测试 3: 简单网站（使用智能降级）"""
    print_separator("测试 3: 简单网站 - Example.com")

    result = fetch_url.invoke({"url": "https://example.com"})
    print_result(result, show_content=True)
    return result.get('success', False)


def test_jina_reader():
    """测试 4: 强制使用 Jina Reader"""
    print_separator("测试 4: 强制使用 Jina Reader")

    result = fetch_url.invoke({
        "url": "https://example.com",
        "force_method": "jina"
    })
    print_result(result, show_content=True)
    return result.get('success', False)


def test_local_parser():
    """测试 5: 强制使用本地解析器"""
    print_separator("测试 5: 强制使用本地解析器")

    result = fetch_url.invoke({
        "url": "https://example.com",
        "force_method": "local"
    })
    print_result(result, show_content=True)
    return result.get('success', False)


def test_force_browser():
    """测试 6: 强制使用浏览器模式"""
    print_separator("测试 6: 强制使用浏览器模式 (Playwright)")

    result = fetch_url.invoke({
        "url": "https://example.com",
        "force_method": "browser"
    })
    print_result(result, show_content=True)
    return result.get('success', False)


def test_chinese_website():
    """测试 7: 中文网站"""
    print_separator("测试 7: 中文网站 - 百度首页")

    result = fetch_url.invoke({
        "url": "https://www.baidu.com",
        "prefer_jina": True
    })
    print_result(result)
    return result.get('success', False)


def test_real_world_site():
    """测试 8: 真实新闻网站"""
    print_separator("测试 8: 新闻网站测试")

    test_sites = [
        "https://news.ycombinator.com/",  # Hacker News
    ]

    for site in test_sites:
        print(f"\n测试站点: {site}")
        result = fetch_url.invoke({
            "url": site,
            "prefer_jina": True
        })
        print_result(result)
        if result.get('success'):
            print(f"   ✅ 成功使用 {result.get('method')} 获取内容")
        else:
            print(f"   ❌ 获取失败: {result.get('error')}")


def test_invalid_force_method():
    """测试 9: 无效的强制方法"""
    print_separator("测试 9: 无效的强制方法参数")

    result = fetch_url.invoke({
        "url": "https://example.com",
        "force_method": "invalid_method"
    })
    print_result(result)
    assert not result.get('success'), "应该返回失败"
    assert "无效的强制方法" in result.get('error', ''), "错误信息应包含提示"
    print("✅ 正确处理无效的强制方法参数")


def test_without_jina_preference():
    """测试 10: 不优先使用 Jina"""
    print_separator("测试 10: 不优先使用 Jina Reader")

    result = fetch_url.invoke({
        "url": "https://example.com",
        "prefer_jina": False
    })
    print_result(result, show_content=True)
    print(f"使用的方法: {result.get('method')}")
    return result.get('success', False)


def test_hanspub_search_with_verification():
    """测试 11: 汉斯出版社搜索页面（带验证码，使用浏览器模式）"""
    print_separator("测试 11: 汉斯出版社搜索 - 反爬虫测试")

    # 汉斯出版社搜索URL - 神经网络分支动力学分析
    url = "https://www.hanspub.org/journal/articles?searchcode=%e7%a5%9e%e7%bb%8f%e7%bd%91%e7%bb%9c%e5%88%86%e5%b2%94%e5%8a%a8%e5%8a%9b%e5%ad%a6%e5%88%86%e6%9e%90&searchfield=all&page=1"

    print(f"测试 URL: {url}")
    print(f"搜索关键词: 神经网络分支动力学分析")
    print()

    # 使用浏览器模式（唯一能绕过验证码的方法）
    result = fetch_url.invoke({
        "url": url,
        "force_method": "browser"
    })

    print_result(result)

    if result.get('success'):
        content = result.get('markdown_content', '')

        # 检查是否成功绕过验证码
        if '验证' in content or 'captcha' in content.lower() or 'verify' in content.lower():
            print("⚠️  内容仍包含验证码页面")
            return False

        # 提取文章数量
        import re
        article_links = re.findall(r'//www\.hanspub\.org/journal/paperinformation\?paperid=\d+', content)
        article_count = len(article_links)

        print(f"\n📊 解析结果:")
        print(f"   找到文章数: {article_count}")

        # 检查是否包含相关关键词
        has_keywords = any(keyword in content for keyword in ['神经网络', '动力学', '神经'])
        print(f"   包含相关关键词: {'是' if has_keywords else '否'}")

        if article_count >= 5 and has_keywords:
            print("\n✅ 成功绕过验证码，获取到搜索结果！")
            return True
        else:
            print(f"\n⚠️  获取的内容可能不完整（文章数: {article_count}, 关键词: {has_keywords}）")
            return False
    else:
        print(f"\n❌ 获取失败: {result.get('error')}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "fetch_url 工具方法完整测试套件" + " " * 26 + "║")
    print("╚" + "=" * 78 + "╝")

    results = {
        "dependency_check": None,
        "simple_website": None,
        "jina_reader": None,
        "local_parser": None,
        "force_browser": None,
        "chinese_website": None,
        "without_jina": None,
        "hanspub_search": None,
    }

    # 测试 1: 依赖检查
    if not test_dependencies():
        print("\n❌ 依赖检查失败，请先安装必要的依赖包")
        print("pip install requests beautifulsoup4 playwright playwright-stealth")
        print("playwright install chromium")
        return

    results["dependency_check"] = True

    # 测试 2: 无效 URL
    test_invalid_url()

    # 测试 3: 简单网站
    results["simple_website"] = test_simple_website()

    # 测试 4: 强制使用 Jina Reader
    results["jina_reader"] = test_jina_reader()

    # 测试 5: 强制使用本地解析器
    results["local_parser"] = test_local_parser()

    # 测试 6: 强制使用浏览器
    results["force_browser"] = test_force_browser()

    # 测试 7: 中文网站
    results["chinese_website"] = test_chinese_website()

    # 测试 8: 真实网站
    test_real_world_site()

    # 测试 9: 无效参数
    test_invalid_force_method()

    # 测试 10: 不优先使用 Jina
    results["without_jina"] = test_without_jina_preference()

    # 测试 11: 汉斯出版社搜索（反爬虫测试）
    results["hanspub_search"] = test_hanspub_search_with_verification()

    # 打印测试总结
    print_separator("测试总结")

    total_tests = len([k for k in results.keys() if results[k] is not None])
    passed_tests = len([k for k, v in results.items() if v is True])

    print(f"\n📊 测试结果统计:")
    print(f"   总测试数: {total_tests}")
    print(f"   通过: {passed_tests}")
    print(f"   失败: {total_tests - passed_tests}")

    print(f"\n📋 详细结果:")
    for test_name, result in results.items():
        if result is not None:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"   {test_name}: {status}")

    if passed_tests == total_tests:
        print(f"\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
