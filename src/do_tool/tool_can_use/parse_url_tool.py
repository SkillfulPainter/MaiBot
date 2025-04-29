# [file name]: parse_url_tool.py
from src.do_tool.tool_can_use.base_tool import BaseTool, register_tool
from src.plugins.models.utils_model import LLM_request
from src.plugins.config.config import global_config
import re
from urllib.parse import urlparse
from typing import Dict
import aiohttp
from bs4 import BeautifulSoup
from .engines import HEADERS, USER_AGENTS
import random


class ParseUrlTool(BaseTool):
    """解析群消息中的链接内容工具"""

    def __init__(self):
        self.llm_summary = LLM_request(
            model=global_config.llm_summary_by_topic,
            temperature=0.7,
            max_tokens=4096,
            request_type="relation")

    # 工具名称（必须唯一）
    name = "parse_group_urls"

    # 工具描述（告诉LLM这个工具的用途）
    description = "当用户的消息中含有网页链接并且用户传达出需要你查看网页链接中的内容时，你可以用这个工具解析群消息中的链接内容，自动提取消息中的URL并获取网页主要内容"

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

    async def _get_from_url(self, url: str, message_txt="") -> str:
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
                    if main_content:
                        ret = await self._tidy_text(main_content.get_text()[:1000])
                        prompt = f"请根据用户的这一请求：{message_txt}使用平实的叙述性语言总结以下内容：\n{ret}\n,提取以上内容与用户请求有关的部分，并适当概括其主要信息以完成用户请求，不要分点，输出内容小于等于200字。"
                        try:
                            summary, _ = await self.llm_summary.generate_response_summary(prompt)
                        except Exception as e:
                            print(f"总结主题失败: {e}")
                            summary = "无法总结主题"
                    else:
                        summary = "无法总结主题"
                    return summary
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
            content = await self._get_from_url(url, message_txt)
            if content:
                contents.append(f"【链接内容】{url}\n{content}\n")

        return {
            "name": self.name,
            "content": "\n".join(contents) if contents else "未发现有效链接或内容获取失败"
        }


# 注册工具
#register_tool(ParseUrlTool)