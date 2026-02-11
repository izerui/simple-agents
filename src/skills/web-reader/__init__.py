"""
Web Reader 技能 - 网页内容获取和解析工具
"""

from .web_reader import (
    fetch_url,
    fetch_multiple_urls,
    fetch_url_with_jina,
    fetch_url_local,
    fetch_url_with_browser,
    WebContent,
    WebReaderError
)

__version__ = "1.0.0"
__author__ = "Skill Creator"