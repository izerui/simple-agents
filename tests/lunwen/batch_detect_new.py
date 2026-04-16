#!/usr/bin/env python3
"""
新论文批量查重与AI检测脚本
按学生文件夹逐个检测，报告保存到学生同级目录下，汇总xlsx保存到新论文文件夹下
"""
import asyncio
import base64
import json
import os
import re
import uuid
from pathlib import Path
from urllib.parse import quote

import aiofiles
import requests
from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


HOST = 'http://localhost:2024'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEW_PAPERS_DIR = os.path.join(BASE_DIR, '新论文')


async def get_file_base64(file_path):
    async with aiofiles.open(file_path, 'rb') as f:
        return base64.b64encode(await f.read()).decode('utf-8')


async def stream_detect(docx_path):
    """对单篇论文执行 paper-detector 检测"""
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
                        if msg_type == "tool":
                            tool_name = msg.get('name', '')
                            print(f"    🔧 {tool_name}", end='', flush=True)
                        elif msg_type == "AIMessageChunk":
                            content = msg.get('content', '')
                            if content and len(content) > 2:
                                print('.', end='', flush=True)
        except Exception as e:
            print(f"\n    ❌ 流处理错误: {e}")

    return thread_id, generated_files


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
    m = re.search(r'(\d+\.?\d*)%', text)
    return m.group(1) + '%' if m else ''


def parse_report(md_content):
    """从检测报告md中解析关键指标（兼容多种格式）"""
    result = {}

    # 知网 总文字复制比
    m = re.search(r'总文字复制比.*?(\d+\.?\d*)%', md_content)
    if m:
        result['知网_总文字复制比'] = m.group(1) + '%'

    # 去除引用复制比
    m = re.search(r'去除引用.*?复制比.*?(\d+\.?\d*)%', md_content)
    if m:
        result['知网_去除引用复制比'] = m.group(1) + '%'

    # 去除本人复制比
    m = re.search(r'去除本人.*?复制比.*?(\d+\.?\d*)%', md_content)
    if m:
        result['知网_去除本人复制比'] = m.group(1) + '%'

    # 单篇最大
    m = re.search(r'单篇最大.*?(\d+\.?\d*)%', md_content)
    if m:
        result['知网_单篇最大复制比'] = m.group(1) + '%'

    # 重复字符数
    m = re.search(r'重复字符数.*?([\d,]+)\s*字', md_content)
    if m:
        result['知网_重复字符数'] = m.group(1).replace(',', '')

    # 维普指标
    for cn_name, field in [('引用率', '维普_引用率'), ('原创率', '维普_原创率'),
                            ('复写率', '维普_复写率'), ('自引率', '维普_自引率'),
                            ('他引率', '维普_他引率'), ('自写率', '维普_自写率')]:
        m = re.search(rf'{cn_name}.*?(\d+\.?\d*)%', md_content)
        if m:
            result[field] = m.group(1) + '%'

    # 维普复制率（避免匹配"去除xx复制比"）
    m = re.search(r'(?<!去除)复制率.*?(\d+\.?\d*)%', md_content)
    if m:
        result['维普_复制率'] = m.group(1) + '%'

    # AIGC 生成率
    m = re.search(r'(?:综合|全文疑似)\s*AIGC\s*生成率.*?(\d+\.?\d*)%', md_content)
    if m:
        result['AIGC_生成率'] = m.group(1) + '%'

    # 人写概率
    m = re.search(r'(?:全文)?人写概率.*?(\d+\.?\d*)%', md_content)
    if m:
        result['AIGC_人写概率'] = m.group(1) + '%'
    elif 'AIGC_生成率' in result:
        try:
            aigc = float(result['AIGC_生成率'].replace('%', ''))
            result['AIGC_人写概率'] = f"{100 - aigc:.1f}%"
        except:
            pass

    # 各章节 AIGC
    aigc_chapter_patterns = [
        r'\|\s*([^|]+?)\s*\|\s*(\d+\.?\d*)%\s*\|\s*\d+\.?\d*%\s*\|\s*[\d,]+\s*字',
        r'\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*(\d+\.?\d*)%\s*\|\s*[^|]*\|',
    ]
    aigc_section = ''
    for pat in [r'(?:各章节\s*AIGC|AIGC\s*检测详细|AIGC\s*分布)', r'AIGC']:
        m = re.search(pat, md_content)
        if m:
            start = max(0, m.start() - 50)
            next_sec = re.search(r'\n##\s', md_content[m.end():])
            end = m.end() + next_sec.start() if next_sec else len(md_content)
            aigc_section = md_content[start:end]
            if '|' in aigc_section and '%' in aigc_section:
                break

    if aigc_section:
        for pattern in aigc_chapter_patterns:
            matches = re.findall(pattern, aigc_section)
            if matches:
                for chapter_name, pct in matches:
                    chapter_name = chapter_name.strip()
                    if any(kw in chapter_name for kw in ['指标', '章节', '编号', '---', '名称', '相似', '复制']):
                        continue
                    result[f'章节AIGC_{chapter_name}'] = pct + '%'
                break

    # 风险等级
    for pattern, field in [
        (r'\*\*查重风险\*\*[：:]\s*[^\n]*?\*\*(.+?)\*\*', '查重风险'),
        (r'\*\*AIGC\s*风险\*\*[：:]\s*[^\n]*?\*\*(.+?)\*\*', 'AIGC风险'),
        (r'\*\*剽窃风险\*\*[：:]\s*[^\n]*?\*\*(.+?)\*\*', '剽窃风险'),
    ]:
        m = re.search(pattern, md_content)
        if m:
            val = m.group(1).strip()
            if '|' not in val:
                result[field] = val

    if '查重风险' not in result:
        m = re.search(r'学术风险等级[^|]*?\*\*(.+?)\*\*', md_content)
        if m and '|' not in m.group(1):
            result['查重风险'] = m.group(1).strip()

    if '查重风险' not in result and '知网_总文字复制比' in result:
        try:
            v = float(result['知网_总文字复制比'].replace('%', ''))
            if v >= 50: result['查重风险'] = '高风险'
            elif v >= 30: result['查重风险'] = '中风险'
            elif v >= 15: result['查重风险'] = '低风险'
            else: result['查重风险'] = '正常'
        except:
            pass

    if 'AIGC风险' not in result and 'AIGC_生成率' in result:
        try:
            aigc_val = float(result['AIGC_生成率'].replace('%', ''))
            if aigc_val >= 60: result['AIGC风险'] = '极高风险'
            elif aigc_val >= 40: result['AIGC风险'] = '高风险'
            elif aigc_val >= 25: result['AIGC风险'] = '中等风险'
            elif aigc_val >= 10: result['AIGC风险'] = '低风险'
            else: result['AIGC风险'] = '正常'
        except:
            pass

    if '剽窃风险' not in result:
        m = re.search(r'剽窃风险.*?(?:较低|低|无|正常)', md_content)
        if m:
            result['剽窃风险'] = '低风险'

    return result


def generate_xlsx(all_results, output_path):
    """生成汇总xlsx"""
    wb = Workbook()
    ws = wb.active
    ws.title = "论文检测汇总"

    base_headers = ['序号', '学生姓名', '论文文件']
    cnki_headers = ['知网_总文字复制比', '知网_去除引用复制比', '知网_去除本人复制比', '知网_单篇最大复制比', '知网_重复字符数']
    vip_headers = ['维普_引用率', '维普_复制率', '维普_原创率', '维普_复写率', '维普_自引率', '维普_他引率', '维普_自写率']
    aigc_headers = ['AIGC_生成率', 'AIGC_人写概率']
    risk_headers = ['查重风险', 'AIGC风险', '剽窃风险']

    # 动态章节列
    chapter_aigc_keys = set()
    for r in all_results:
        for k in r.get('parsed', {}):
            if k.startswith('章节AIGC_'):
                chapter_aigc_keys.add(k)
    chapter_aigc_keys = sorted(chapter_aigc_keys)

    status_headers = ['检测状态', '报告文件']
    all_headers = base_headers + cnki_headers + vip_headers + aigc_headers + chapter_aigc_keys + risk_headers + status_headers

    # 样式
    header_font_white = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    sub_header_fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    risk_high = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
    risk_mid = PatternFill(start_color="FFD93D", end_color="FFD93D", fill_type="solid")
    risk_low = PatternFill(start_color="6BCB77", end_color="6BCB77", fill_type="solid")

    # 分组表头（第1行）
    groups = [
        ('基本信息', len(base_headers)),
        ('知网指标', len(cnki_headers)),
        ('维普指标', len(vip_headers)),
        ('AIGC检测', len(aigc_headers)),
        ('各章节AIGC占比', len(chapter_aigc_keys)),
        ('风险等级', len(risk_headers)),
        ('状态', len(status_headers)),
    ]
    col = 1
    for group_name, group_len in groups:
        if group_len == 0:
            continue
        cell = ws.cell(row=1, column=col, value=group_name)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
        if group_len > 1:
            ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + group_len - 1)
        col += group_len

    # 字段表头（第2行）
    for i, h in enumerate(all_headers, 1):
        display = h.replace('知网_', '').replace('维普_', '').replace('AIGC_', '').replace('章节AIGC_', '')
        cell = ws.cell(row=2, column=i, value=display)
        cell.font = Font(bold=True, size=11)
        cell.fill = sub_header_fill
        cell.alignment = center_align
        cell.border = thin_border

    # 数据行
    for idx, res in enumerate(all_results):
        row_num = idx + 3
        parsed = res.get('parsed', {})

        row_data = [idx + 1, res.get('student_name', ''), res.get('docx_name', '')]
        for h in cnki_headers:
            row_data.append(parsed.get(h, ''))
        for h in vip_headers:
            row_data.append(parsed.get(h, ''))
        for h in aigc_headers:
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
            header_name = all_headers[col_idx - 1] if col_idx <= len(all_headers) else ''
            if header_name in risk_headers and isinstance(val, str):
                if '高' in val and '低' not in val:
                    cell.fill = risk_high
                elif '中' in val:
                    cell.fill = risk_mid
                elif '低' in val or '正常' in val:
                    cell.fill = risk_low

    # 列宽
    for col_idx in range(1, len(all_headers) + 1):
        max_len = 0
        for row_idx in range(1, len(all_results) + 3):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value:
                try:
                    max_len = max(max_len, len(str(cell.value)))
                except:
                    pass
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 8), 30)

    ws.freeze_panes = 'D3'
    wb.save(output_path)
    print(f"\n✅ 汇总报告已生成: {output_path}")


async def process_one(idx, total, student_name, docx_path, report_dir):
    """处理单篇论文"""
    docx_name = os.path.basename(docx_path)
    report_filename = os.path.splitext(docx_name)[0] + '_检测报告.md'
    local_report_path = os.path.join(report_dir, report_filename)

    print(f"\n{'='*70}")
    print(f"[{idx}/{total}] 📄 {student_name} - {docx_name}")
    print(f"{'='*70}")

    # 断点续跑
    if os.path.exists(local_report_path):
        with open(local_report_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        if len(md_content) > 100:
            print(f"    ⏭️  已有报告，跳过检测")
            parsed = parse_report(md_content)
            return {'status': '成功（缓存）', 'report_file': report_filename, 'parsed': parsed,
                    'student_name': student_name, 'docx_name': docx_name}

    if not os.path.exists(docx_path):
        print(f"    ❌ 文件不存在: {docx_path}")
        return {'status': '失败-文件不存在', 'report_file': '', 'parsed': {},
                'student_name': student_name, 'docx_name': docx_name}

    try:
        thread_id, generated_files = await stream_detect(docx_path)
        print(f"\n    Thread: {thread_id}")

        md_content = None
        if generated_files:
            for remote_path in generated_files:
                md_content = download_report(thread_id, remote_path, local_report_path)
                if md_content:
                    break

        if not md_content:
            for try_path in ['deepthink/final_report.md', 'final_report.md']:
                md_content = download_report(thread_id, try_path, local_report_path)
                if md_content:
                    break

        if md_content and len(md_content) > 100:
            parsed = parse_report(md_content)
            print(f"    ✅ 报告已保存: {local_report_path}")
            print(f"    📊 知网复制比: {parsed.get('知网_总文字复制比', 'N/A')}, AIGC率: {parsed.get('AIGC_生成率', 'N/A')}")
            return {'status': '成功', 'report_file': report_filename, 'parsed': parsed,
                    'student_name': student_name, 'docx_name': docx_name}
        else:
            print(f"    ⚠️ 报告内容为空")
            return {'status': '失败-报告为空', 'report_file': '', 'parsed': {},
                    'student_name': student_name, 'docx_name': docx_name}

    except Exception as e:
        print(f"    ❌ 检测出错: {e}")
        import traceback
        traceback.print_exc()
        return {'status': f'失败-{str(e)[:50]}', 'report_file': '', 'parsed': {},
                'student_name': student_name, 'docx_name': docx_name}


async def main():
    # 扫描新论文目录：每个子文件夹是一个学生
    students = []
    for student_dir in sorted(Path(NEW_PAPERS_DIR).iterdir()):
        if not student_dir.is_dir():
            continue
        student_name = student_dir.name
        docx_files = list(student_dir.glob('*.docx'))
        if docx_files:
            students.append({
                'name': student_name,
                'docx_path': str(docx_files[0]),
                'dir': str(student_dir),
            })

    total = len(students)
    print(f"📋 共发现 {total} 位学生的论文")
    for s in students:
        print(f"   - {s['name']}: {os.path.basename(s['docx_path'])}")
    print(f"\n🚀 开始逐个检测...\n")

    all_results = []
    success_count = 0

    for i, student in enumerate(students, 1):
        result = await process_one(i, total, student['name'], student['docx_path'], student['dir'])
        all_results.append(result)
        if '成功' in result.get('status', ''):
            success_count += 1

    # 生成汇总xlsx
    xlsx_path = os.path.join(NEW_PAPERS_DIR, '汇总报告.xlsx')
    generate_xlsx(all_results, xlsx_path)

    fail_count = total - success_count
    print(f"\n{'='*70}")
    print(f"🎉 全部完成！")
    print(f"   总计: {total} 篇")
    print(f"   成功: {success_count} 篇")
    print(f"   失败: {fail_count} 篇")
    print(f"   汇总报告: {xlsx_path}")
    print(f"{'='*70}")


if __name__ == '__main__':
    asyncio.run(main())
