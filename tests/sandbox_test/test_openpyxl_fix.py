#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 openpyxl 在移除 SafePathProxy 后是否能正常工作

目的：验证修复提交 1d2929c 导致的 openpyxl 卡死问题
"""
import sys
from pathlib import Path
import shutil

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sandbox.sandbox_filesystem import SandboxFilesystemBackend

# 测试工作目录
WORKSPACE_DIR = Path(__file__).parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)


def test_openpyxl_basic():
    """测试 openpyxl 基本功能"""
    print("\n" + "=" * 70)
    print("测试 openpyxl 在移除 SafePathProxy 后是否能正常工作")
    print("=" * 70)
    
    # 创建后端实例，设置超时时间为 60 秒
    backend = SandboxFilesystemBackend(
        root_dir=str(WORKSPACE_DIR),
        timeout_seconds=60,
        max_memory_mb=512,
        max_output_length=100000,
    )
    
    # 测试代码
    test_code = r"""
python -c "
import openpyxl
from openpyxl.chart import BarChart, Reference, LineChart
from openpyxl.styles import Font, PatternFill, Alignment
from datetime import datetime

# 创建工作簿
wb = openpyxl.Workbook()
ws = wb.active
ws.title = '销售数据'

# 设置标题
ws['A1'] = '2024年销售数据汇总'
ws['A1'].font = Font(size=16, bold=True)
ws.merge_cells('A1:E1')

# 添加表头
headers = ['产品类别', '第一季度', '第二季度', '第三季度', '第四季度', '年度总计']
for col, header in enumerate(headers, start=1):
    cell = ws.cell(row=3, column=col)
    cell.value = header
    cell.font = Font(bold=True)
    cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    cell.alignment = Alignment(horizontal='center')

# 添加数据
data = [
    ['电子产品', 150000, 180000, 200000, 250000],
    ['家居用品', 80000, 95000, 110000, 130000],
    ['服装鞋帽', 120000, 140000, 160000, 190000],
    ['食品饮料', 200000, 220000, 240000, 280000],
    ['图书文具', 50000, 60000, 70000, 85000],
]

# 填充数据并计算总计
for row_idx, row_data in enumerate(data, start=4):
    for col_idx, value in enumerate(row_data, start=1):
        ws.cell(row=row_idx, column=col_idx).value = value
    # 计算年度总计
    ws.cell(row=row_idx, column=6).value = f'=SUM(B{row_idx}:E{row_idx})'

# 添加总计行
total_row = len(data) + 4
ws.cell(row=total_row, column=1, value='总计')
ws.cell(row=total_row, column=1).font = Font(bold=True)
for col in range(2, 7):
    ws.cell(row=total_row, column=col).value = f'=SUM({chr(64+col)}4:{chr(64+col)}{total_row-1})'
    ws.cell(row=total_row, column=col).font = Font(bold=True)

# 调整列宽
ws.column_dimensions['A'].width = 15
for col in ['B', 'C', 'D', 'E', 'F']:
    ws.column_dimensions[col].width = 14

# 创建柱状图
chart1 = BarChart()
chart1.type = 'col'
chart1.style = 10
chart1.title = '各产品类别季度销售对比'
chart1.y_axis.title = '销售额（元）'
chart1.x_axis.title = '产品类别'

# 设置数据范围
data_ref = Reference(ws, min_col=2, min_row=3, max_row=total_row, max_col=5)
cats_ref = Reference(ws, min_col=1, min_row=4, max_row=total_row-1)
chart1.add_data(data_ref, titles_from_data=True)
chart1.set_categories(cats_ref)

# 设置图表位置
ws.add_chart(chart1, 'H2')

# 创建折线图
chart2 = LineChart()
chart2.title = '各产品类别年度销售趋势'
chart2.style = 12
chart2.y_axis.title = '销售额（元）'
chart2.x_axis.title = '季度'

# 设置折线图数据
line_data_ref = Reference(ws, min_col=2, min_row=3, max_row=total_row-1, max_col=5)
line_cats_ref = Reference(ws, min_col=1, min_row=4, max_row=total_row-1)
chart2.add_data(line_data_ref, titles_from_data=True)
chart2.set_categories(line_cats_ref)

ws.add_chart(chart2, 'H18')

# 保存文件
output_path = '/outputs/销售数据汇总.xlsx'
wb.save(output_path)
print(f'Excel文件已生成：{output_path}')
print('包含内容：')
print('- 5个产品类别的季度销售数据')
print('- 自动计算的年度总计')
print('- 柱状图：各产品类别季度销售对比')
print('- 折线图：各产品类别年度销售趋势')
"
"""
    
    print(f"\n正在执行测试...")
    print(f"超时设置: 60 秒")
    print(f"工作目录: {WORKSPACE_DIR}")
    print()
    
    try:
        # 执行代码
        response = backend.execute(test_code)
        
        # 检查结果
        if response.exit_code == 0:
            print("\n✅ 测试成功！")
            print("\n执行输出：")
            print(response.output)
            
            # 检查文件是否生成
            output_file = WORKSPACE_DIR / "outputs" / "销售数据汇总.xlsx"
            if output_file.exists():
                file_size = output_file.stat().st_size
                print(f"\n✅ 文件已成功生成：{output_file}")
                print(f"   文件大小：{file_size:,} 字节")
                return True
            else:
                print(f"\n⚠️  文件未生成：{output_file}")
                return False
        else:
            print(f"\n❌ 测试失败！")
            print(f"退出码: {response.exit_code}")
            print(f"\n错误输出：")
            print(response.output)
            
            if hasattr(response, 'error') and response.error:
                print(f"\n错误信息：")
                print(response.error)
            
            return False
            
    except Exception as e:
        print(f"\n❌ 执行过程中发生异常！")
        print(f"异常信息：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理测试环境
        print("\n清理测试环境...")
        cleanup_workspace()
        print(f"✓ 工作目录已清理")


def cleanup_workspace():
    """清理工作目录"""
    if WORKSPACE_DIR.exists():
        for item in WORKSPACE_DIR.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)


def main():
    """主函数"""
    success = test_openpyxl_basic()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ openpyxl 测试通过 - SafePathProxy 问题已修复")
    else:
        print("❌ openpyxl 测试失败 - 可能仍存在问题")
    print("=" * 70)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)