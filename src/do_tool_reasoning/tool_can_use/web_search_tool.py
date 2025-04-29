# 文件名：web_search_tool.py
from src.do_tool_reasoning.tool_can_use.base_tool import BaseTool, register_tool
from .engines.bing import Bing
from .engines.sogo import Sogo
from readability import Document
from .engines import HEADERS, USER_AGENTS
from bs4 import BeautifulSoup
import aiohttp
import random
from typing import List


# 继承main.py的网页内容抓取逻辑
class WebSearcher:
    def __init__(self):
        self.bing = Bing()
        self.sogo = Sogo()

        self.HEADERS = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "*/*",
            "Connection": "keep-alive",
            "Accept-Language": "en-GB,en;q=0.5",
        }

    async def _tidy_text(self, text: str) -> str:
        """清理文本，去除空格、换行符等"""
        return text.strip().replace("\n", " ").replace("\r", " ").replace("  ", " ")

    async def _get_from_url(self, url: str) -> str:
        """获取网页内容"""
        headers = self.HEADERS.copy()
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(url, headers=headers, timeout=6) as response:
                html = await response.text(encoding="utf-8")
                doc = Document(html)
                ret = doc.summary(html_partial=True)
                soup = BeautifulSoup(ret, "html.parser")
                ret = await self._tidy_text(soup.get_text())  # 清理文本
                return ret

    async def search(self, query: str, num_results: int = 3) -> List[str]:
        """多引擎搜索实现"""
        results = []
        try:
            results = await self.bing.search(query, num_results)
        except:
            results = await self.sogo.search(query, num_results)
        return results


class WebSearchTool(BaseTool):
    name = "web_search_tool"
    description = "当需要获取实时信息或验证概念时，使用此工具进行多引擎网页搜索。支持返回标题、摘要和网页内容摘要。"

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "需要搜索的关键词或问题，例如：'量子计算的基本原理是什么？'"
            }
        },
        "required": ["query"]
    }

    def __init__(self):
        super().__init__()
        self.searcher = WebSearcher()
        self.max_results = 3  # 默认返回3条结果
        self.show_link = True  # 是否显示链接

    async def execute(self, function_args, message_txt=""):
        try:
            query = function_args.get("query")
            raw_results = await self.searcher.search(query, self.max_results)

            formatted_results = []
            for idx, result in enumerate(raw_results[:self.max_results]):
                # 获取网页内容摘要
                try:
                    content = await self.searcher._get_from_url(result.url)
                    content = content[:1000] + "..." if len(content) > 1000 else content
                except:
                    content = "无法获取网页内容"

                # 结构化结果
                entry = f"{idx + 1}. 【{result.title}】\n"
                if self.show_link:
                    entry += f"链接：{result.url}\n"
                entry += f"摘要：{result.snippet}\n内容摘要：{content}\n"
                formatted_results.append(entry)

            return {
                "name": self.name,
                "content": "\n\n".join(formatted_results)
            }

        except Exception as e:
            return {
                "name": self.name,
                "content": f"搜索失败：{str(e)}"
            }


# 注册工具
#register_tool(WebSearchTool)