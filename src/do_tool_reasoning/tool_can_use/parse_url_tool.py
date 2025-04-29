# [file name]: parse_url_tool.py
from src.do_tool_reasoning.tool_can_use.base_tool import BaseTool, register_tool
import re
from urllib.parse import urlparse
from typing import Dict
import aiohttp
from bs4 import BeautifulSoup
from .engines import HEADERS, USER_AGENTS
import random


class ParseUrlTool(BaseTool):
    """解析群消息中的链接内容工具"""

    # 工具名称（必须唯一）
    name = "parse_group_urls"

    # 工具描述（告诉LLM这个工具的用途）
    description = "当用户需要你查看某个网页链接中的内容时，你可以用这个工具解析群消息中的链接内容，自动提取消息中的URL并获取网页主要内容"

    # 工具参数定义（JSONSchema格式）
    parameters = {
        "type": "object",
        "properties": {
            "message_text": {
                "type": "string",
                "description": "需要解析的群消息文本内容"
            }
        },
        "required": ["message_text"]
    }

    async def _tidy_text(self, text: str) -> str:
        """清理网页文本"""
        return text.strip().replace("\n", " ").replace("\r", " ").replace("  ", " ")

    async def _get_from_url(self, url: str) -> str:
        """复用现有获取网页内容逻辑"""
        header = HEADERS.copy()
        header["User-Agent"] = random.choice(USER_AGENTS)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=header, timeout=6) as response:
                    html = await response.text(encoding="utf-8")
                    doc = BeautifulSoup(html, "html.parser")
                    # 提取主要内容
                    main_content = doc.find("article") or doc.find("main") or doc.body
                    return await self._tidy_text(main_content.get_text()[:1000]) if main_content else ""
        except Exception:
            return ""

    async def execute(self, function_args: Dict, message_txt: str = "") -> Dict:
        # 使用正则匹配消息中的URL
        urls = re.findall(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            function_args.get("message_text", "")
        )

        # 验证并去重URL
        valid_urls = []
        for url in set(urls):
            try:
                result = urlparse(url)
                if all([result.scheme, result.netloc]):
                    valid_urls.append(url)
            except:
                continue

        # 获取所有链接内容
        contents = []
        for url in valid_urls:
            content = await self._get_from_url(url)
            if content:
                contents.append(f"【链接内容】{url}\n{content}\n")

        return {
            "name": self.name,
            "content": "\n".join(contents) if contents else "未发现有效链接或内容获取失败"
        }


# 注册工具
#register_tool(ParseUrlTool)