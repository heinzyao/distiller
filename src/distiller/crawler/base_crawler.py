"""
改進的爬蟲基礎類
"""

import logging
import time
import requests
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BaseCrawler:
    """爬蟲基礎類"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化爬蟲

        Args:
            config: 爬蟲配置字典
        """
        self.config = config
        self.logger = self._setup_logger()
        self.session = self._create_session()

    def _setup_logger(self) -> logging.Logger:
        """設置日誌記錄器"""
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(getattr(logging, self.config.get('logging', {}).get('level', 'INFO')))

        # 文件處理器
        log_file = self.config.get('logging', {}).get('file', 'logs/crawler.log')
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)

        # 控制台處理器
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # 格式化
        formatter = logging.Formatter(
            self.config.get('logging', {}).get('format',
                                               '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

        return logger

    def _create_session(self) -> requests.Session:
        """
        創建 HTTP Session（連接池復用）

        Returns:
            配置好的 Session 對象
        """
        session = requests.Session()

        # 設置 headers
        headers = self.config.get('headers', {})
        session.headers.update(headers)

        # 設置重試策略
        max_retries = self.config.get('request', {}).get('max_retries', 3)
        backoff_factor = self.config.get('request', {}).get('backoff_factor', 2)

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        發送 GET 請求

        Args:
            url: 請求 URL
            **kwargs: 其他請求參數

        Returns:
            Response 對象，失敗返回 None
        """
        timeout = self.config.get('request', {}).get('timeout', 30)
        delay = self.config.get('request', {}).get('delay', 3)

        try:
            # 請求延遲
            time.sleep(delay)

            # 發送請求
            response = self.session.get(url, timeout=timeout, **kwargs)
            response.raise_for_status()

            self.logger.debug(f"成功獲取: {url}")
            return response

        except requests.exceptions.Timeout:
            self.logger.error(f"請求超時: {url}")
            return None

        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP 錯誤 {e.response.status_code}: {url}")
            return None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"請求錯誤: {url}, {str(e)}")
            return None

    def parse_html(self, html: str, parser: str = 'lxml') -> Optional[BeautifulSoup]:
        """
        解析 HTML

        Args:
            html: HTML 字符串
            parser: 解析器類型

        Returns:
            BeautifulSoup 對象
        """
        try:
            return BeautifulSoup(html, parser)
        except Exception as e:
            self.logger.error(f"HTML 解析錯誤: {str(e)}")
            return None

    def safe_extract(self, extractor_func, default=None):
        """
        安全提取數據

        Args:
            extractor_func: 提取函數
            default: 默認值

        Returns:
            提取的數據或默認值
        """
        try:
            return extractor_func()
        except (AttributeError, IndexError, ValueError, TypeError) as e:
            self.logger.debug(f"提取失敗: {str(e)}")
            return default

    def close(self):
        """關閉 Session"""
        self.session.close()
        self.logger.info("Session 已關閉")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()


# 使用示例
if __name__ == '__main__':
    # 配置示例
    config = {
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        'request': {
            'timeout': 30,
            'delay': 1,
            'max_retries': 3,
            'backoff_factor': 2
        },
        'logging': {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'file': 'logs/crawler.log'
        }
    }

    # 使用上下文管理器
    with BaseCrawler(config) as crawler:
        response = crawler.get('https://example.com')
        if response:
            soup = crawler.parse_html(response.text)
            if soup:
                title = crawler.safe_extract(lambda: soup.find('h1').text.strip())
                print(f"頁面標題: {title}")
