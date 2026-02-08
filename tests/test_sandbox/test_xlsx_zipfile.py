#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 xlsx 和 zipfile 功能
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.sandbox.pycode_executor import CodeExecutor
from pathlib import Path
import tempfile


def test_xlsx_creation():
    """测试使用 openpyxl 创建 xlsx 文件"""
    print("\n" + "=" * 80)
    print("测试 openpyxl 创建 xlsx 文件")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        sandbox_dir = tmpdir / "sandbox"
        sandbox_dir.mkdir()
        
        executor = CodeExecutor(root_dir=str(sandbox_dir), timeout=30)
        
        # 创建测试脚本文件
        test_script = sandbox_dir / "test_xlsx.py"
        test_script.write_text("""
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "测试表"
ws.append(["姓名", "年龄", "部门"])
ws.append(["张三", 25, "技术部"])
ws.append(["李四", 30, "市场部"])
output_path = "/outputs/test.xlsx"
wb.save(output_path)
print("xlsx created at:", output_path)
import os
if os.path.exists(output_path):
    print("file size:", os.path.getsize(output_path))
""")
        
        result = executor.execute('python test_xlsx.py')
        
        if result.exit_code == 0:
            print("✅ openpyxl 测试通过")
            print(result.output)
            
            expected_file = sandbox_dir / "outputs" / "test.xlsx"
            if expected_file.exists():
                print(f"✅ 文件验证成功: {expected_file}")
                print(f"   实际大小: {expected_file.stat().st_size} 字节")
                return True
            else:
                print(f"❌ 文件不存在: {expected_file}")
                return False
        else:
            print("❌ openpyxl 测试失败")
            print(result.output)
            return False


def test_zipfile_operations():
    """测试 zipfile 基本操作"""
    print("\n" + "=" * 80)
    print("测试 zipfile 基本操作")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        sandbox_dir = tmpdir / "sandbox"
        sandbox_dir.mkdir()
        
        executor = CodeExecutor(root_dir=str(sandbox_dir), timeout=30)
        
        test_script = sandbox_dir / "test_zipfile.py"
        test_script.write_text("""
import zipfile
import os
os.makedirs("/data", exist_ok=True)
with open("/data/file1.txt", "w") as f:
    f.write("File 1 content")
with open("/data/file2.txt", "w") as f:
    f.write("File 2 content")
with zipfile.ZipFile("/archive.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write("/data/file1.txt", "file1.txt")
    zf.write("/data/file2.txt", "file2.txt")
print("zip file created")
with zipfile.ZipFile("/archive.zip", "r") as zf:
    names = zf.namelist()
    print("files in zip:", names)
    content = zf.read("file1.txt").decode()
    print("file1.txt content:", content)
""")
        
        result = executor.execute('python test_zipfile.py')
        
        if result.exit_code == 0:
            print("✅ zipfile 测试通过")
            print(result.output)
            
            expected_file = sandbox_dir / "archive.zip"
            if expected_file.exists():
                print(f"✅ zip 文件验证成功: {expected_file}")
                return True
            else:
                print(f"❌ 文件不存在: {expected_file}")
                return False
        else:
            print("❌ zipfile 测试失败")
            print(result.output)
            return False


def test_pandas_xlsx():
    """测试使用 pandas 保存 xlsx 文件"""
    print("\n" + "=" * 80)
    print("测试 pandas 保存 xlsx 文件")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        sandbox_dir = tmpdir / "sandbox"
        sandbox_dir.mkdir()
        
        executor = CodeExecutor(root_dir=str(sandbox_dir), timeout=30)
        
        test_script = sandbox_dir / "test_pandas.py"
        test_script.write_text("""
import pandas as pd
import numpy as np
np.random.seed(42)
data = {'ID': range(1, 11), '姓名': [f'员工{i}' for i in range(1, 11)], '部门': np.random.choice(['技术部', '市场部', '财务部'], 10), '薪资': np.random.randint(5000, 15000, 10)}
df = pd.DataFrame(data)
output_path = "/outputs/pandas_test.xlsx"
df.to_excel(output_path, index=False)
print("pandas xlsx created at:", output_path)
print("rows:", len(df))
print("columns:", len(df.columns))
""")
        
        result = executor.execute('python test_pandas.py')
        
        if result.exit_code == 0:
            print("✅ pandas xlsx 测试通过")
            print(result.output)
            
            expected_file = sandbox_dir / "outputs" / "pandas_test.xlsx"
            if expected_file.exists():
                print(f"✅ 文件验证成功: {expected_file}")
                print(f"   实际大小: {expected_file.stat().st_size} 字节")
                return True
            else:
                print(f"❌ 文件不存在: {expected_file}")
                return False
        else:
            print("❌ pandas xlsx 测试失败")
            print(result.output)
            return False


def test_path_redirection():
    """测试路径重定向功能"""
    print("\n" + "=" * 80)
    print("测试路径重定向功能")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        sandbox_dir = tmpdir / "sandbox"
        sandbox_dir.mkdir()
        
        executor = CodeExecutor(root_dir=str(sandbox_dir), timeout=30)
        
        test_script = sandbox_dir / "test_redirect.py"
        test_script.write_text("""
import zipfile
import os
with open("/data/test.txt", "w") as f:
    f.write("test content")
with zipfile.ZipFile("/absolute/path/archive.zip", "w") as zf:
    zf.write("/data/test.txt", "test.txt")
print("absolute path redirection successful")
print("current dir:", os.getcwd())
print("data/test.txt exists:", os.path.exists("data/test.txt"))
print("absolute/path/archive.zip exists:", os.path.exists("absolute/path/archive.zip"))
""")
        
        result = executor.execute('python test_redirect.py')
        
        if result.exit_code == 0:
            print("✅ 路径重定向测试通过")
            print(result.output)
            
            data_file = sandbox_dir / "data" / "test.txt"
            archive_file = sandbox_dir / "absolute" / "path" / "archive.zip"
            
            if data_file.exists() and archive_file.exists():
                print(f"✅ 文件重定向验证成功")
                print(f"   /data/test.txt -> {data_file}")
                print(f"   /absolute/path/archive.zip -> {archive_file}")
                return True
            else:
                print(f"❌ 文件重定向失败")
                print(f"   data_file: {data_file} (exists: {data_file.exists()})")
                print(f"   archive_file: {archive_file} (exists: {archive_file.exists()})")
                return False
        else:
            print("❌ 路径重定向测试失败")
            print(result.output)
            return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("xlsx 和 zipfile 功能测试")
    print("=" * 80)
    
    results = []
    
    results.append(("openpyxl 创建 xlsx", test_xlsx_creation()))
    results.append(("zipfile 基本操作", test_zipfile_operations()))
    results.append(("pandas 保存 xlsx", test_pandas_xlsx()))
    results.append(("路径重定向功能", test_path_redirection()))
    
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print()
    print(f"总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        exit(0)
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        exit(1)
