#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汉斯出版社书目检索服务核心模块
遵循skill-creator最佳实践，提供简洁、可靠的检索功能
"""

import requests
import urllib.parse
from bs4 import BeautifulSoup
import time
import logging
from typing import List, Dict, Optional

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HansPubBibliographyRetriever:
    """汉斯出版社书目检索服务类 - 简洁高效实现"""
    
    def __init__(self):
        self.base_url = "https://www.hanspub.org"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 学科分类映射（精简版）
        self.subject_mapping = {
            "数学与物理": "1.shtml",
            "化学与材料": "9.shtml", 
            "生命科学": "5.shtml",
            "医药卫生": "7.shtml",
            "信息通讯": "3.shtml",
            "工程技术": "6.shtml",
            "地球与环境": "2.shtml",
            "经济与管理": "4.shtml",
            "人文社科": "8.shtml",
            "合作期刊": "10.shtml"
        }
        
        # 核心期刊映射（常用期刊）
        self.journal_mapping = {
            # 医药卫生
            "ACRVM": "亚洲心脑血管病例研究",
            "ACM": "临床医学进展", 
            "HJBM": "生物医学",
            "TCM": "中医学",
            "NS": "护理学",
            # 信息通讯  
            "CSA": "计算机科学与应用",
            "MOS": "建模与仿真",
            "HJDM": "数据挖掘",
            "AIRR": "人工智能与机器人研究",
            # 工程技术
            "SG": "智能电网",
            "MET": "机械工程与技术",
            "HJCE": "土木工程",
            # 其他常用
            "JC": "新闻传播科学",
            "ASS": "社会科学前沿",
            "WJCR": "世界肿瘤研究"
        }
    
    def _safe_request(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """安全的HTTP请求，包含重试机制"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                else:
                    logger.error(f"请求最终失败: {url}")
                    return None
        return None
    
    def build_search_url(self, query: str, search_field: str = "title", 
                        subject: Optional[str] = None, journal: Optional[str] = None, 
                        page: int = 1) -> str:
        """
        构建汉斯出版社检索URL
        
        Args:
            query: 检索关键词
            search_field: 检索字段 ("title", "authors", "all")
            subject: 学科分类名称
            journal: 期刊代码
            page: 页码
            
        Returns:
            完整的检索URL
        """
        # URL编码关键词
        encoded_query = urllib.parse.quote(query, encoding='utf-8')
        
        # 基础文章检索URL
        base_url = f"{self.base_url}/journal/articles"
        
        # 构建参数
        params = {
            "searchcode": encoded_query,
            "searchfield": search_field,
            "page": str(page)
        }
        
        # 如果指定了学科，优先使用学科页面
        if subject and subject in self.subject_mapping:
            subject_url = f"{self.base_url}/{self.subject_mapping[subject]}"
            # TODO: 学科页面的检索需要特殊处理
            return base_url + f"?searchcode={encoded_query}&searchfield={search_field}&page={page}"
        
        # 如果指定了期刊，构建期刊特定期刊URL
        if journal and journal in self.journal_mapping:
            journal_url = f"{self.base_url}/journal/{journal}"
            return journal_url + f"?searchcode={encoded_query}&searchfield={search_field}&page={page}"
        
        # 返回通用检索URL
        return base_url + f"?searchcode={encoded_query}&searchfield={search_field}&page={page}"
    
    def hanspub_search(self, query: str, search_field: str = "title", 
                      subject: Optional[str] = None, journal: Optional[str] = None, 
                      page: int = 1, max_results: int = 20) -> List[Dict]:
        """
        执行汉斯出版社书目检索
        
        Args:
            query: 检索关键词
            search_field: 检索字段
            subject: 学科分类
            journal: 期刊代码  
            page: 页码
            max_results: 最大结果数
            
        Returns:
            书目信息列表
        """
        # 构建检索URL
        search_url = self.build_search_url(query, search_field, subject, journal, page)
        logger.info(f"执行检索: {search_url}")
        
        # 发送请求
        response = self._safe_request(search_url)
        if not response:
            return []
        
        # 解析结果
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = self._parse_article_list(soup, max_results)
            return articles
        except Exception as e:
            logger.error(f"解析失败: {e}")
            return []
    
    def _parse_article_list(self, soup: BeautifulSoup, max_results: int) -> List[Dict]:
        """解析文章列表"""
        articles = []
        
        # 查找文章链接（基于汉斯出版社的实际HTML结构）
        article_links = soup.find_all('a', href=lambda x: x and 'paperinformation' in x)
        
        for link in article_links[:max_results]:
            try:
                article_info = {
                    'title': link.get_text(strip=True),
                    'url': self.base_url + link.get('href', ''),
                    'authors': [],
                    'journal': '',
                    'publication_date': '',
                    'doi': '',
                    'pdf_url': ''
                }
                
                # 尝试提取作者信息
                author_links = link.find_next_siblings('a', href=lambda x: x and 'authors' in x)
                if author_links:
                    article_info['authors'] = [author.get_text(strip=True) for author in author_links]
                
                # 尝试提取期刊信息
                journal_link = link.find_next('a', href=lambda x: x and 'journal' in x and 'home' not in x)
                if journal_link:
                    article_info['journal'] = journal_link.get_text(strip=True)
                
                articles.append(article_info)
                
            except Exception as e:
                logger.warning(f"解析单篇文章失败: {e}")
                continue
        
        return articles
    
    def get_subject_journals(self, subject_name: str) -> List[Dict]:
        """获取指定学科下的期刊列表"""
        if subject_name not in self.subject_mapping:
            return []
        
        # 这里返回预定义的期刊映射（实际应用中可以从网站抓取）
        subject_journals = []
        for code, name in self.journal_mapping.items():
            # 简单的学科匹配（实际需要更精确的映射）
            if subject_name == "医药卫生" and code in ["ACRVM", "ACM", "HJBM", "TCM", "NS", "WJCR"]:
                subject_journals.append({"code": code, "name": name})
            elif subject_name == "信息通讯" and code in ["CSA", "MOS", "HJDM", "AIRR", "JC"]:
                subject_journals.append({"code": code, "name": name})
            elif subject_name == "工程技术" and code in ["SG", "MET", "HJCE", "OE", "SEA"]:
                subject_journals.append({"code": code, "name": name})
        
        return subject_journals

# 全局函数接口（便于直接调用）
def hanspub_search(query: str, search_field: str = "title", 
                  subject: Optional[str] = None, journal: Optional[str] = None, 
                  page: int = 1, max_results: int = 20) -> List[Dict]:
    """全局检索函数"""
    retriever = HansPubBibliographyRetriever()
    return retriever.hanspub_search(query, search_field, subject, journal, page, max_results)

def get_subject_journals(subject_name: str) -> List[Dict]:
    """获取学科期刊列表"""
    retriever = HansPubBibliographyRetriever()
    return retriever.get_subject_journals(subject_name)