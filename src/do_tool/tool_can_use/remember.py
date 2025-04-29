# src/do_tool/tool_can_use/knowledge_build_tool.py
from dateutil import tz
import datetime
import random
from src.do_tool.tool_can_use.base_tool import BaseTool, register_tool
from src.common.logger import get_module_logger
from typing import Dict, Any
from src.plugins.zhishi.knowledge_library import knowledge_library  # 根据实际路径调整
from src.plugins.chat.utils import get_embedding, get_recent_group_detailed_plain_text
from src.plugins.config.config import global_config
from src.individuality.individuality import Individuality
from src.plugins.models.utils_model import LLM_request
from src.plugins.chat.chat_stream import chat_manager
from src.plugins.chat.message import MessageThinking

logger = get_module_logger("knowledge_build_tool")
TIME_ZONE = tz.gettz(global_config.TIME_ZONE)  # 设置时区

class KnowledgeBuildTool(BaseTool):
    """直接处理原始文本并构建知识库的工具"""
    
    name = "knowledge_builder"
    description = "当用户需要你记住什么东西的时候，比如说“你要记住”“记住...”的时候，或者你觉得某个话题很有意思，或者引起了你的注意，值得记住的时候，使用这个工具来将用户所说内容加入知识库。如果用户只是问你记不记得，知不知道，并没有明确要求你记住什么，不要使用此工具。"

    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "一句话总结想要记忆的内容"
            },
            "source": {
                "type": "string",
                "description": "内容来源标识格式为“群聊/私聊-发送者”",
                "default": "chat"
            }
        },
        "required": ["content"]
    }
    
    def __init__(self):
        self.llm_summary = LLM_request(
            model=global_config.llm_summary_by_topic,
            temperature=1.0,
            max_tokens=4096,
            request_type="relation")
    
    async def execute(self, function_args: Dict[str, Any], message_txt: str = "") -> Dict[str, Any]:
        """执行知识库构建"""
        target_date = datetime.datetime
        start_time = datetime.datetime.now(TIME_ZONE)
        date_str = target_date.strftime("%Y-%m-%d")
        weekday = target_date.strftime("%A")
        stream_id = MessageThinking.chat_stream.stream_id
        time_prompt = ''
        time_prompt += f'现在是{date_str}{weekday}的{start_time}'

        chat_talking_prompt = ""
        if stream_id:
            chat_talking_prompt = get_recent_group_detailed_plain_text(
                stream_id, limit=global_config.MAX_CONTEXT_SIZE - 4, combine=True
            )
            chat_stream = chat_manager.get_stream(stream_id)
            if chat_stream.group_info:
                chat_talking_prompt = chat_talking_prompt
            else:
                chat_talking_prompt = chat_talking_prompt

        content = function_args.get("content")
        source = function_args.get("source")

        prompt_personality = "你"
        # person
        individuality = Individuality.get_instance()

        personality_core = individuality.personality.personality_core
        prompt_personality += personality_core

        personality_sides = individuality.personality.personality_sides
        random.shuffle(personality_sides)
        prompt_personality += f",{personality_sides[0]}"

        identity_detail = individuality.identity.identity_detail
        random.shuffle(identity_detail)
        prompt_personality += f",{identity_detail[0]}"

        bot_name = global_config.BOT_NICKNAME,
        bot_other_names = "/".join(
            global_config.BOT_ALIAS_NAMES,
        ),

        prompt = f"""你的网名叫{bot_name}，有人也叫你{bot_other_names}，{prompt_personality}。
                 {time_prompt},{chat_talking_prompt}
                 现在有人想让你记住{content}，或者是你对{content}产生了兴趣，记忆深刻。
                 现在请你读读聊天记录，用两三句话总结出与{content}相关的内容作为你记住的东西。
                 如果你觉得聊天记录里的内容好像没啥好总结的，或者你对这些内容并不感兴趣，则不作任何回复，不输出任何内容。如果进行了输出不要分点，输出内容小于等于200字。"
                 """
        memory, _ = await self.llm_summary.generate_response_summary(prompt)

        if not content:
            return {
                "name": self.name,
                "content": "你还没告诉林晓麦要记啥呢。。。"
            }
        if not memory:
            return {
                "name": self.name,
                "content": "林晓麦觉得没啥好记的。。。"
            }

        try:
            # --- 直接处理文本内容 ---
            result = knowledge_library.process_text(
                text=memory,
                source_name=source
            )

            if result["status"] != "success":
                error_msg = result.get("error", "未知错误")
                return {
                    "name": self.name,
                    "content": f"林晓麦没记住。。。: {error_msg}"
                }

            return {
                "name": self.name,
                "content": f"林晓麦记住了{content}"
            }

        except Exception as e:
            logger.error(f"系统错误: {str(e)}")
            return {
                "name": self.name,
                "content": f"林晓麦没记住。。。 {str(e)}"
            }


# 注册工具
#register_tool(KnowledgeBuildTool)