# 文件名：web_search_tool.py
from src.do_tool.tool_can_use.base_tool import BaseTool, register_tool
from src.plugins.models.utils_model import LLM_request
from src.plugins.config.config import global_config
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
        self.llm_summary = LLM_request(
            model=global_config.llm_summary_by_topic,
            temperature=0.7,
            max_tokens=4096,
            request_type="relation")

        self.HEADERS = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "*/*",
            "Connection": "keep-alive",
            "Accept-Language": "en-GB,en;q=0.5",

        }

    async def _tidy_text(self, text: str) -> str:
        """清理文本，去除空格、换行符等"""
        return text.strip().replace("\n", " ").replace("\r", " ").replace("  ", " ")

    async def _get_from_url(self, url: str, query: str, message_txt="") -> str:
        """获取网页内容"""
        headers = self.HEADERS.copy()
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(url, headers=headers, timeout=6) as response:
                html = await response.text(encoding="utf-8")
                doc = Document(html)
                ret = doc.summary(html_partial=True)
                soup = BeautifulSoup(ret, "html.parser")
                ret = await self._tidy_text(soup.get_text())
                prompt = f"请根据这一关键词：{query}和用户的这一请求：{message_txt}使用平实的叙述性语言总结以下内容：\n{ret}\n,提取以上内容与这一关键词有关的部分，并适当概括其主要信息以完成用户请求，不要分点，输出内容小于等于200字。"
                try:
                    summary, _ = await self.llm_summary.generate_response_summary(prompt)
                except Exception as e:
                    print(f"总结主题失败: {e}")
                    summary = "无法总结主题"
                # 清理文本
                return summary

    async def search(self, query: str, num_results: int = 3) -> List[str]:
        """多引擎搜索实现"""
        results = []
        try:
            results = await self.sogo.search(query, num_results)
        except:
            results = await self.bing.search(query, num_results)
        return results


class WebSearchTool(BaseTool):
    name = "search_web"
    description = "当用户需要你进行网页搜索获取信息或你不知道某概念需要搜索验证概念时，使用此工具进行网页搜索。"

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
            query = function_args.get("query", message_txt)
            raw_results = await self.searcher.search(query, self.max_results)

            formatted_results = []
            for idx, result in enumerate(raw_results[:self.max_results]):
                # 获取网页内容摘要
                try:
                    content = await self.searcher._get_from_url(result.url, query, message_txt)
                    content = content[:1000] + "..." if len(content) > 1000 else content
                except:
                    content = "在网上没找到啥有用的东西"

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