#!/usr/bin/env python3
"""
批量论文查重与AI检测脚本
逐个串行处理50篇论文，使用 paper-detector 技能检测，下载报告并生成汇总xlsx
"""
import asyncio
import base64
import csv
import json
import os
import re
import uuid
from urllib.parse import quote

import aiofiles
import requests
from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


HOST = 'http://localhost:2024'
OUTPUT_DIR = '结果'
CSV_FILE = '论文信息表.csv'


async def get_file_base64(file_path):
    async with aiofiles.open(file_path, 'rb') as f:
        return base64.b64encode(await f.read()).decode('utf-8')


async def stream_detect(docx_path):
    """对单篇论文执行 paper-detector 检测，返回 (generated_files, stream_output)"""
    docx_content = await get_file_base64(docx_path)

    message = HumanMessage(content=[
        {"type": "text", "text": "/skills/paper-detector\n\n请对这篇论文进行查重检测和AI生成内容检测，生成完整的检测报告。"},
        {"type": "file", "data": docx_content, "metadata": {"filename": os.path.basename(docx_path)}},
    ])

    thread_id = str(uuid.uuid4())
    client = get_client(url=HOST, api_key='')

    chunks = client.runs.stream(
        thread_id=thread_id,
        assistant_id='research',
        input={"messages": [message]},
        multitask_strategy='reject',
        stream_mode=["messages-tuple", "custom"],
        if_not_exists='create',
        stream_subgraphs=True,
        on_disconnect='cancel',
        on_completion='keep',
    )

    generated_files = []
    output_text = ''

    async for chunk in chunks:
        try:
            event_name = chunk.event if hasattr(chunk, 'event') else None
            data = chunk.data if hasattr(chunk, 'data') else None
            if event_name is None:
                continue

            if event_name == "custom":
                if isinstance(data, dict):
                    if data.get('type') == 'generated_files':
                        generated_files.extend(data.get('content', []))
                        print(f"    📁 生成文件: {data.get('content', [])}")
                continue

            if event_name == "messages":
                if not isinstance(data, list) or len(data) < 2:
                    continue
                msg_list = data[0]
                if not isinstance(msg_list, list):
                    msg_list = [msg_list]
                for msg in msg_list:
                    if isinstance(msg, dict):
                        msg_type = msg.get('type')
                        if msg_type == "AIMessageChunk":
                            content = msg.get('content', '')
                            if content:
                                output_text += content
                                print(content[:80].replace('\n', ' '), end='', flush=True) if len(output_text) < 500 else None
                        elif msg_type == "tool":
                            tool_name = msg.get('name', '')
                            print(f"\n    🔧 {tool_name}", end='', flush=True)
        except Exception as e:
            print(f"\n    ❌ 流处理错误: {e}")

    return thread_id, generated_files, output_text


def download_report(thread_id, remote_path, local_path):
    """下载报告到本地"""
    download_url = f"{HOST}/webapp/download/{thread_id}?path={quote(remote_path.lstrip('/'))}"
    try:
        response = requests.get(download_url, timeout=30)
        if response.ok:
            content = response.content.decode('utf-8')
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return content
        else:
            print(f"    ❌ 下载失败 ({response.status_code})")
            return None
    except Exception as e:
        print(f"    ❌ 下载出错: {e}")
        return None


def extract_percent(text):
    """从文本中提取百分比数值，如 '**11.8%**' -> '11.8%'"""
    m = re.search(r'(\d+\.?\d*)%', text)
    return m.group(1) + '%' if m else ''


def extract_value(text):
    """从文本中提取数值，如 '5,850 字' -> '5850'"""
    m = re.search(r'([\d,]+)', text.replace(',', ''))
    if m:
        return m.group(1)
    m = re.search(r'([\d,]+)', text)
    return m.group(1).replace(',', '') if m else ''


def parse_report(md_content):
    """从检测报告md中解析所有关键指标（兼容多种报告格式）"""
    result = {}

    # 辅助：在整个md中按"指标名 ... 数值%"模式搜索
    def find_metric(pattern, field):
        m = re.search(pattern, md_content)
        if m:
            result[field] = extract_percent(m.group(0))

    # === 知网指标（通用正则，兼容两种格式）===
    # 总文字复制比
    for m in re.finditer(r'总文字复制比[^|]*\|[^|]*?(\*?\*?[\d.]+%\*?\*?)', md_content):
        result['知网_总文字复制比'] = extract_percent(m.group(1))
    # 如果上面没匹配到，尝试另一种格式：| 总文字复制比 | **8.3%** |
    if '知网_总文字复制比' not in result:
        m = re.search(r'总文字复制比.*?(\d+\.?\d*)%', md_content)
        if m:
            result['知网_总文字复制比'] = m.group(1) + '%'

    # 去除引用文献复制比
    m = re.search(r'去除引用.*?复制比.*?(\d+\.?\d*)%', md_content)
    if m:
        result['知网_去除引用复制比'] = m.group(1) + '%'

    # 去除本人文献复制比
    m = re.search(r'去除本人.*?复制比.*?(\d+\.?\d*)%', md_content)
    if m:
        result['知网_去除本人复制比'] = m.group(1) + '%'

    # 单篇最大复制比/相似度
    m = re.search(r'单篇最大.*?(\d+\.?\d*)%', md_content)
    if m:
        result['知网_单篇最大复制比'] = m.group(1) + '%'

    # 重复字符数
    m = re.search(r'重复字符数.*?([\d,]+)\s*字', md_content)
    if m:
        result['知网_重复字符数'] = m.group(1).replace(',', '')

    # === 维普指标 ===
    vip_patterns = {
        '维普_引用率': r'引用率.*?(\d+\.?\d*)%',
        '维普_复制率': r'(?<!\u53bb\u9664)复制率.*?(\d+\.?\d*)%',
        '维普_原创率': r'原创率.*?(\d+\.?\d*)%',
        '维普_复写率': r'复写率.*?(\d+\.?\d*)%',
        '维普_自引率': r'自引率.*?(\d+\.?\d*)%',
        '维普_他引率': r'他引率.*?(\d+\.?\d*)%',
        '维普_自写率': r'自写率.*?(\d+\.?\d*)%',
    }
    for field, pattern in vip_patterns.items():
        m = re.search(pattern, md_content)
        if m:
            result[field] = m.group(1) + '%'

    # === AIGC 检测指标 ===
    # 综合 AIGC 生成率 / 全文疑似 AIGC 生成率
    m = re.search(r'(?:综合|全文疑似)\s*AIGC\s*生成率.*?(\d+\.?\d*)%', md_content)
    if m:
        result['AIGC_生成率'] = m.group(1) + '%'

    # 人写概率
    m = re.search(r'(?:全文)?人写概率.*?(\d+\.?\d*)%', md_content)
    if m:
        result['AIGC_人写概率'] = m.group(1) + '%'
    elif 'AIGC_生成率' in result:
        # 计算人写概率
        try:
            aigc = float(result['AIGC_生成率'].replace('%', ''))
            result['AIGC_人写概率'] = f"{100 - aigc:.1f}%"
        except:
            pass

    # === 各章节 AIGC 占比（从表格行提取）===
    # 格式1: | 章节名 | AIGC 占比 | 人工占比 | 字数 | 风险 |
    # 格式2: | 编号 | 章节名 | AIGC 概率 | 风险 |
    aigc_chapter_patterns = [
        # 格式1: | 摘要 | 31.8% | 68.2% | 480 字 | ⚠️ 中 |
        r'\|\s*([^|]+?)\s*\|\s*(\d+\.?\d*)%\s*\|\s*\d+\.?\d*%\s*\|\s*[\d,]+\s*字',
        # 格式2: | 28 | 摘要 | 22.3% | 中低 |
        r'\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*(\d+\.?\d*)%\s*\|\s*[^|]*\|',
    ]

    # 只在 AIGC 相关 section 中搜索
    aigc_section = ''
    for pattern in [r'(?:各章节\s*AIGC|AIGC\s*检测详细|AIGC\s*分布)', r'AIGC']:
        m = re.search(pattern, md_content)
        if m:
            start = max(0, m.start() - 50)
            # 找到下一个 ## 标题
            next_section = re.search(r'\n##\s', md_content[m.end():])
            end = m.end() + next_section.start() if next_section else len(md_content)
            aigc_section = md_content[start:end]
            if '|' in aigc_section and '%' in aigc_section:
                break

    if aigc_section:
        for pattern in aigc_chapter_patterns:
            matches = re.findall(pattern, aigc_section)
            if matches:
                for chapter_name, pct in matches:
                    chapter_name = chapter_name.strip()
                    # 跳过表头和非章节行
                    if any(kw in chapter_name for kw in ['指标', '章节', '编号', '---', '名称', '相似', '复制']):
                        continue
                    result[f'章节AIGC_{chapter_name}'] = pct + '%'
                break

    # === 各章节复制比 ===
    # 格式: | 章节名 | 字数 | 复制比 | ... |
    copy_section = ''
    for pattern in [r'各章节复制比', r'章节.*?指标统计', r'章节详细分析']:
        m = re.search(pattern, md_content)
        if m:
            start = m.start()
            next_section = re.search(r'\n##\s', md_content[m.end():])
            end = m.end() + next_section.start() if next_section else min(m.end() + 3000, len(md_content))
            copy_section = md_content[start:end]
            break

    if copy_section:
        # | 摘要 | 480 字 | 39.1% | ...
        matches = re.findall(r'\|\s*([^|]+?)\s*\|\s*[\d,]+\s*字\s*\|\s*(\d+\.?\d*)%', copy_section)
        for chapter_name, pct in matches:
            chapter_name = chapter_name.strip()
            if any(kw in chapter_name for kw in ['章节', '指标', '---']):
                continue
            result[f'章节复制比_{chapter_name}'] = pct + '%'

    # 格式2: 从章节详细分析中提取 **复制比**：6.8%
    if not any(k.startswith('章节复制比_') for k in result):
        sections = re.findall(r'###\s*(.+?)(?:\n|$).*?\*\*复制比\*\*[：:]\s*(\d+\.?\d*)%', md_content, re.DOTALL)
        for chapter_name, pct in sections:
            chapter_name = chapter_name.strip().lstrip('#').strip()
            result[f'章节复制比_{chapter_name}'] = pct + '%'

    # === 风险等级 ===
    # 格式1: **查重风险**：✅ **低风险**
    risk_patterns = [
        (r'\*\*查重风险\*\*[：:]\s*[^\n]*?\*\*(.+?)\*\*', '查重风险'),
        (r'\*\*AIGC\s*风险\*\*[：:]\s*[^\n]*?\*\*(.+?)\*\*', 'AIGC风险'),
        (r'\*\*剽窃风险\*\*[：:]\s*[^\n]*?\*\*(.+?)\*\*', '剽窃风险'),
    ]
    for pattern, field in risk_patterns:
        m = re.search(pattern, md_content)
        if m:
            result[field] = m.group(1).strip()

    # 格式2: 学术风险等级：**低风险** 或 表格中
    if '查重风险' not in result:
        m = re.search(r'学术风险等级[^|]*?\*\*(.+?)\*\*', md_content)
        if m:
            val = m.group(1).strip()
            if '|' not in val:
                result['查重风险'] = val
    # 格式3: 从知网复制比推断
    if '查重风险' not in result and '知网_总文字复制比' in result:
        try:
            v = float(result['知网_总文字复制比'].replace('%', ''))
            if v >= 50:
                result['查重风险'] = '高风险'
            elif v >= 30:
                result['查重风险'] = '中风险'
            elif v >= 15:
                result['查重风险'] = '低风险'
            else:
                result['查重风险'] = '正常'
        except:
            pass

    # 从综合评估表格提取
    if 'AIGC风险' not in result:
        m = re.search(r'AIGC.*?生成率.*?(\d+\.?\d*)%', md_content)
        if m:
            aigc_val = float(m.group(1))
            if aigc_val >= 60:
                result['AIGC风险'] = '极高风险'
            elif aigc_val >= 40:
                result['AIGC风险'] = '高风险'
            elif aigc_val >= 25:
                result['AIGC风险'] = '中等风险'
            elif aigc_val >= 10:
                result['AIGC风险'] = '低风险'
            else:
                result['AIGC风险'] = '正常'

    if '剽窃风险' not in result:
        m = re.search(r'剽窃风险.*?(?:较低|低|无|正常)', md_content)
        if m:
            result['剽窃风险'] = '低风险'

    return result


def generate_xlsx(all_results, csv_rows):
    """生成汇总xlsx报告"""
    wb = Workbook()
    ws = wb.active
    ws.title = "论文检测汇总"

    # 定义表头
    base_headers = ['序号', '院系', '专业', '学生姓名', '学号', '指导老师']
    cnki_headers = ['知网_总文字复制比', '知网_去除引用复制比', '知网_去除本人复制比', '知网_单篇最大复制比', '知网_重复字符数']
    vip_headers = ['维普_引用率', '维普_复制率', '维普_原创率', '维普_复写率', '维普_自引率', '维普_他引率', '维普_自写率']
    aigc_headers = ['AIGC_生成率', 'AIGC_人写概率']
    risk_headers = ['查重风险', 'AIGC风险', '剽窃风险']

    # 收集所有章节名称（动态）
    chapter_aigc_keys = set()
    chapter_copy_keys = set()
    for r in all_results:
        for k in r.get('parsed', {}):
            if k.startswith('章节AIGC_'):
                chapter_aigc_keys.add(k)
            elif k.startswith('章节复制比_'):
                chapter_copy_keys.add(k)
    chapter_aigc_keys = sorted(chapter_aigc_keys)
    chapter_copy_keys = sorted(chapter_copy_keys)

    status_headers = ['检测状态', '报告文件']
    all_headers = base_headers + cnki_headers + vip_headers + aigc_headers + chapter_copy_keys + chapter_aigc_keys + risk_headers + status_headers

    # 样式定义
    header_font = Font(bold=True, size=11)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font_white = Font(bold=True, size=11, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    risk_high_fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
    risk_mid_fill = PatternFill(start_color="FFD93D", end_color="FFD93D", fill_type="solid")
    risk_low_fill = PatternFill(start_color="6BCB77", end_color="6BCB77", fill_type="solid")

    # 写分组表头（第1行）
    group_row = 1
    groups = [
        ('基本信息', len(base_headers)),
        ('知网指标', len(cnki_headers)),
        ('维普指标', len(vip_headers)),
        ('AIGC检测', len(aigc_headers)),
        ('各章节复制比', len(chapter_copy_keys)),
        ('各章节AIGC占比', len(chapter_aigc_keys)),
        ('风险等级', len(risk_headers)),
        ('状态', len(status_headers)),
    ]
    col = 1
    for group_name, group_len in groups:
        if group_len == 0:
            continue
        cell = ws.cell(row=group_row, column=col, value=group_name)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
        if group_len > 1:
            ws.merge_cells(start_row=group_row, start_column=col, end_row=group_row, end_column=col + group_len - 1)
        col += group_len

    # 写字段表头（第2行）
    header_row = 2
    display_headers = []
    for h in all_headers:
        # 美化显示名
        display = h.replace('知网_', '').replace('维普_', '').replace('AIGC_', '').replace('章节AIGC_', '').replace('章节复制比_', '')
        display_headers.append(display)

    for i, h in enumerate(display_headers, 1):
        cell = ws.cell(row=header_row, column=i, value=h)
        cell.font = header_font
        cell.fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
        cell.alignment = center_align
        cell.border = thin_border

    # 写数据
    for idx, res in enumerate(all_results):
        row_num = idx + 3
        csv_row = csv_rows[idx] if idx < len(csv_rows) else {}
        parsed = res.get('parsed', {})

        row_data = [
            csv_row.get('序号', ''),
            csv_row.get('院系', ''),
            csv_row.get('专业', ''),
            csv_row.get('学生姓名', ''),
            csv_row.get('学号', ''),
            csv_row.get('指导老师', ''),
        ]
        for h in cnki_headers:
            row_data.append(parsed.get(h, ''))
        for h in vip_headers:
            row_data.append(parsed.get(h, ''))
        for h in aigc_headers:
            row_data.append(parsed.get(h, ''))
        for h in chapter_copy_keys:
            row_data.append(parsed.get(h, ''))
        for h in chapter_aigc_keys:
            row_data.append(parsed.get(h, ''))
        for h in risk_headers:
            row_data.append(parsed.get(h, ''))
        row_data.append(res.get('status', ''))
        row_data.append(res.get('report_file', ''))

        for col_idx, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_idx, value=val)
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border

            # 风险等级条件格式
            header_name = all_headers[col_idx - 1] if col_idx <= len(all_headers) else ''
            if header_name in risk_headers and isinstance(val, str):
                if '高' in val and '低' not in val:
                    cell.fill = risk_high_fill
                elif '中' in val:
                    cell.fill = risk_mid_fill
                elif '低' in val or '正常' in val:
                    cell.fill = risk_low_fill

    # 自动调整列宽
    from openpyxl.utils import get_column_letter
    for col_idx in range(1, len(all_headers) + 1):
        max_len = 0
        for row_idx in range(1, len(all_results) + 3):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value and not isinstance(cell, type(ws.merged_cells)):
                try:
                    max_len = max(max_len, len(str(cell.value)))
                except:
                    pass
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 8), 25)

    # 冻结窗格
    ws.freeze_panes = 'G3'

    output_path = os.path.join(OUTPUT_DIR, '汇总报告.xlsx')
    wb.save(output_path)
    print(f"\n✅ 汇总报告已生成: {output_path}")
    return output_path


async def process_one(idx, total, csv_row, docx_path):
    """处理单篇论文"""
    name = csv_row.get('学生姓名', '')
    filename = csv_row.get('新文件名', '')
    report_filename = os.path.splitext(filename)[0] + '.md'
    local_report_path = os.path.join(OUTPUT_DIR, report_filename)

    print(f"\n{'='*70}")
    print(f"[{idx}/{total}] 📄 {filename} ({name})")
    print(f"{'='*70}")

    # 检查是否已有报告（支持断点续跑）
    if os.path.exists(local_report_path):
        print(f"    ⏭️  已有报告，跳过检测，直接解析")
        with open(local_report_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        if len(md_content) > 100:
            parsed = parse_report(md_content)
            return {
                'status': '成功（缓存）',
                'report_file': report_filename,
                'parsed': parsed,
            }

    if not os.path.exists(docx_path):
        print(f"    ❌ 文件不存在: {docx_path}")
        return {'status': '失败-文件不存在', 'report_file': '', 'parsed': {}}

    try:
        thread_id, generated_files, output_text = await stream_detect(docx_path)
        print(f"\n    Thread: {thread_id}")
        print(f"    生成文件: {generated_files}")

        # 下载报告
        md_content = None
        if generated_files:
            for remote_path in generated_files:
                md_content = download_report(thread_id, remote_path, local_report_path)
                if md_content:
                    break

        if not md_content:
            # 尝试默认路径
            for try_path in ['deepthink/final_report.md', 'final_report.md']:
                md_content = download_report(thread_id, try_path, local_report_path)
                if md_content:
                    break

        if md_content and len(md_content) > 100:
            parsed = parse_report(md_content)
            print(f"    ✅ 报告已保存: {local_report_path}")
            print(f"    📊 知网复制比: {parsed.get('知网_总文字复制比', 'N/A')}, AIGC率: {parsed.get('AIGC_生成率', 'N/A')}")
            return {
                'status': '成功',
                'report_file': report_filename,
                'parsed': parsed,
            }
        else:
            print(f"    ⚠️ 报告内容为空或过短")
            return {'status': '失败-报告为空', 'report_file': '', 'parsed': {}}

    except Exception as e:
        print(f"    ❌ 检测出错: {e}")
        import traceback
        traceback.print_exc()
        return {'status': f'失败-{str(e)[:50]}', 'report_file': '', 'parsed': {}}


async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 读取CSV
    csv_rows = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_rows.append(row)

    total = len(csv_rows)
    print(f"📋 共读取 {total} 篇论文信息")
    print(f"📁 报告输出目录: {OUTPUT_DIR}/")
    print(f"🚀 开始逐个检测...\n")

    all_results = []
    success_count = 0
    fail_count = 0

    for i, csv_row in enumerate(csv_rows, 1):
        filename = csv_row.get('新文件名', '')
        docx_path = filename  # 当前目录下

        result = await process_one(i, total, csv_row, docx_path)
        all_results.append(result)

        if '成功' in result.get('status', ''):
            success_count += 1
        else:
            fail_count += 1

        # 每5篇生成一次临时汇总（防止中途崩溃丢失）
        if i % 5 == 0 or i == total:
            generate_xlsx(all_results, csv_rows[:len(all_results)])
            print(f"\n📊 进度: {i}/{total} (成功: {success_count}, 失败: {fail_count})")

    print(f"\n{'='*70}")
    print(f"🎉 全部完成！")
    print(f"   总计: {total} 篇")
    print(f"   成功: {success_count} 篇")
    print(f"   失败: {fail_count} 篇")
    print(f"   报告目录: {OUTPUT_DIR}/")
    print(f"   汇总报告: {OUTPUT_DIR}/汇总报告.xlsx")
    print(f"{'='*70}")


if __name__ == '__main__':
    asyncio.run(main())
