"""Pytest configuration file for tests.

This module sets up environment variables before any tests run.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 获取项目根目录（tests 目录的父目录）
project_root = Path(__file__).parent.parent
env_file = project_root / '.env'

# 在导入任何其他模块之前加载环境变量
load_dotenv(dotenv_path=env_file, verbose=True)