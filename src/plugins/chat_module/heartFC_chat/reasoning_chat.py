import time
import threading  # 导入 threading
from random import random
import traceback
import asyncio
from typing import List, Dict
from ...moods.moods import MoodManager
from src.plugins.config.configimport global_config
from ...chat.emoji_manager import emoji_manager
from .reasoning_generator import ResponseGenerator
from ...chat.message import MessageSending, MessageRecv, MessageThinking, MessageSet
from ...chat.messagesender import message_manager
from ...storage.storage import MessageStorage
from ...chat.utils import is_mentioned_bot_in_message
from ...chat.utils_image import image_path_to_base64
from ...willing.willing_manager import willing_manager
from ...message import UserInfo, Seg
from src.common.logger import get_module_logger, CHAT_STYLE_CONFIG, LogConfig
from src.plugins.chat.chat_stream import ChatStream
from src.plugins.person_info.relationship_manager import relationship_manager
from src.plugins.respon_info_catcher.info_catcher import info_catcher_manager
from src.plugins.utils.timer_calculater import Timer
from .interest import InterestManager
from .heartFC_controler import HeartFCController  # 导入 HeartFCController

# 定义日志配置
chat_config = LogConfig(
    console_format=CHAT_STYLE_CONFIG["console_format"],
    file_format=CHAT_STYLE_CONFIG["file_format"],
)

logger = get_module_logger("reasoning_chat", config=chat_config)


class ReasoningChat:
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 防止重复初始化
        if self._initialized:
            return
        with self.__class__._lock:  # 使用类锁确保线程安全
            if self._initialized:
                return
            logger.info("正在初始化 ReasoningChat 单例...")  # 添加日志
            self.storage = MessageStorage()
            self.gpt = ResponseGenerator()
            self.mood_manager = MoodManager.get_instance()
            self.mood_manager.start_mood_update()
            # 用于存储每个 chat stream 的兴趣监控任务
            self._interest_monitoring_tasks: Dict[str, asyncio.Task] = {}
            self._initialized = True
            self.interest_manager = InterestManager()
            logger.info("ReasoningChat 单例初始化完成。")  # 添加日志

    @classmethod
    def get_instance(cls):
        """获取 ReasoningChat 的单例实例。"""
        if cls._instance is None:
            # 如果实例还未创建（理论上应该在 main 中初始化，但作为备用）
            logger.warning("ReasoningChat 实例在首次 get_instance 时创建。")
            cls()  # 调用构造函数来创建实例
        return cls._instance

    @staticmethod
    async def _create_thinking_message(message, chat, userinfo, messageinfo):
        """创建思考消息"""
        bot_user_info = UserInfo(
            user_id=global_config.BOT_QQ,
            user_nickname=global_config.BOT_NICKNAME,
            platform=messageinfo.platform,
        )

        thinking_time_point = round(time.time(), 2)
        thinking_id = "mt" + str(thinking_time_point)
        thinking_message = MessageThinking(
            message_id=thinking_id,
            chat_stream=chat,
            bot_user_info=bot_user_info,
            reply=message,
            thinking_start_time=thinking_time_point,
        )

        message_manager.add_message(thinking_message)

        return thinking_id

    @staticmethod
    async def _send_response_messages(message, chat, response_set: List[str], thinking_id) -> MessageSending:
        """发送回复消息"""
        container = message_manager.get_container(chat.stream_id)
        thinking_message = None

        for msg in container.messages:
            if isinstance(msg, MessageThinking) and msg.message_info.message_id == thinking_id:
                thinking_message = msg
                container.messages.remove(msg)
                break

        if not thinking_message:
            logger.warning("未找到对应的思考消息，可能已超时被移除")
            return

        thinking_start_time = thinking_message.thinking_start_time
        message_set = MessageSet(chat, thinking_id)

        mark_head = False
        first_bot_msg = None
        for msg in response_set:
            message_segment = Seg(type="text", data=msg)
            bot_message = MessageSending(
                message_id=thinking_id,
                chat_stream=chat,
                bot_user_info=UserInfo(
                    user_id=global_config.BOT_QQ,
                    user_nickname=global_config.BOT_NICKNAME,
                    platform=message.message_info.platform,
                ),
                sender_info=message.message_info.user_info,
                message_segment=message_segment,
                reply=message,
                is_head=not mark_head,
                is_emoji=False,
                thinking_start_time=thinking_start_time,
            )
            if not mark_head:
                mark_head = True
                first_bot_msg = bot_message
            message_set.add_message(bot_message)
        message_manager.add_message(message_set)

        return first_bot_msg

    @staticmethod
    async def _handle_emoji(message, chat, response):
        """处理表情包"""
        if random() < global_config.emoji_chance:
            emoji_raw = await emoji_manager.get_emoji_for_text(response)
            if emoji_raw:
                emoji_path, description = emoji_raw
                emoji_cq = image_path_to_base64(emoji_path)

                thinking_time_point = round(message.message_info.time, 2)

                message_segment = Seg(type="emoji", data=emoji_cq)
                bot_message = MessageSending(
                    message_id="mt" + str(thinking_time_point),
                    chat_stream=chat,
                    bot_user_info=UserInfo(
                        user_id=global_config.BOT_QQ,
                        user_nickname=global_config.BOT_NICKNAME,
                        platform=message.message_info.platform,
                    ),
                    sender_info=message.message_info.user_info,
                    message_segment=message_segment,
                    reply=message,
                    is_head=False,
                    is_emoji=True,
                )
                message_manager.add_message(bot_message)

    async def _update_relationship(self, message: MessageRecv, response_set):
        """更新关系情绪"""
        ori_response = ",".join(response_set)
        stance, emotion = await self.gpt._get_emotion_tags(ori_response, message.processed_plain_text)
        await relationship_manager.calculate_update_relationship_value(
            chat_stream=message.chat_stream, label=emotion, stance=stance
        )
        self.mood_manager.update_mood_from_emotion(emotion, global_config.mood_intensity_factor)

    async def _find_interested_message(self, chat: ChatStream) -> None:
        # 此函数设计为后台任务，轮询指定 chat 的兴趣消息。
        # 它通常由外部代码在 chat 流活跃时启动。
        controller = HeartFCController.get_instance()  # 获取控制器实例
        if not controller:
            logger.error(f"无法获取 HeartFCController 实例，无法检查 PFChatting 状态。stream: {chat.stream_id}")
            # 在没有控制器的情况下可能需要决定是继续处理还是完全停止？这里暂时假设继续
            pass  # 或者 return?

        while True:
            await asyncio.sleep(1)  # 每秒检查一次
            interest_chatting = self.interest_manager.get_interest_chatting(chat.stream_id)

            if not interest_chatting:
                continue

            interest_dict = interest_chatting.interest_dict if interest_chatting.interest_dict else {}
            items_to_process = list(interest_dict.items())

            if not items_to_process:
                continue

            for msg_id, (message, interest_value, is_mentioned) in items_to_process:
                # --- 检查 PFChatting 是否活跃 --- #
                pf_active = False
                if controller:
                    pf_active = controller.is_pf_chatting_active(chat.stream_id)

                if pf_active:
                    # 如果 PFChatting 活跃，则跳过处理，直接移除消息
                    removed_item = interest_dict.pop(msg_id, None)
                    if removed_item:
                        logger.debug(f"PFChatting 活跃，已跳过并移除兴趣消息 {msg_id} for stream: {chat.stream_id}")
                    continue  # 处理下一条消息
                # --- 结束检查 --- #

                # 只有当 PFChatting 不活跃时才执行以下处理逻辑
                try:
                    # logger.debug(f"正在处理消息 {msg_id} for stream: {chat.stream_id}") # 可选调试信息
                    await self.normal_reasoning_chat(
                        message=message,
                        chat=chat,
                        is_mentioned=is_mentioned,
                        interested_rate=interest_value,
                    )
                    # logger.debug(f"处理完成消息 {msg_id}") # 可选调试信息
                except Exception as e:
                    logger.error(f"处理兴趣消息 {msg_id} 时出错: {e}\n{traceback.format_exc()}")
                finally:
                    # 无论处理成功与否（且PFChatting不活跃），都尝试从原始字典中移除该消息
                    removed_item = interest_dict.pop(msg_id, None)
                    if removed_item:
                        logger.debug(f"已从兴趣字典中移除消息 {msg_id}")

    async def normal_reasoning_chat(
        self, message: MessageRecv, chat: ChatStream, is_mentioned: bool, interested_rate: float
    ) -> None:
        timing_results = {}
        userinfo = message.message_info.user_info
        messageinfo = message.message_info

        is_mentioned, reply_probability = is_mentioned_bot_in_message(message)
        # 意愿管理器：设置当前message信息
        willing_manager.setup(message, chat, is_mentioned, interested_rate)

        # 获取回复概率
        is_willing = False
        if reply_probability != 1:
            is_willing = True
            reply_probability = await willing_manager.get_reply_probability(message.message_info.message_id)

            if message.message_info.additional_config:
                if "maimcore_reply_probability_gain" in message.message_info.additional_config.keys():
                    reply_probability += message.message_info.additional_config["maimcore_reply_probability_gain"]

        # 打印消息信息
        mes_name = chat.group_info.group_name if chat.group_info else "私聊"
        current_time = time.strftime("%H:%M:%S", time.localtime(message.message_info.time))
        willing_log = f"[回复意愿:{await willing_manager.get_willing(chat.stream_id):.2f}]" if is_willing else ""
        logger.info(
            f"[{current_time}][{mes_name}]"
            f"{chat.user_info.user_nickname}:"
            f"{message.processed_plain_text}{willing_log}[概率:{reply_probability * 100:.1f}%]"
        )
        do_reply = False
        if random() < reply_probability:
            do_reply = True

            # 回复前处理
            await willing_manager.before_generate_reply_handle(message.message_info.message_id)

            # 创建思考消息
            with Timer("创建思考消息", timing_results):
                thinking_id = await self._create_thinking_message(message, chat, userinfo, messageinfo)

            logger.debug(f"创建捕捉器，thinking_id:{thinking_id}")

            info_catcher = info_catcher_manager.get_info_catcher(thinking_id)
            info_catcher.catch_decide_to_response(message)

            # 生成回复
            try:
                with Timer("生成回复", timing_results):
                    response_set = await self.gpt.generate_response(message, thinking_id)

                info_catcher.catch_after_generate_response(timing_results["生成回复"])
            except Exception as e:
                logger.error(f"回复生成出现错误：{str(e)} {traceback.format_exc()}")
                response_set = None

            if not response_set:
                logger.info("为什么生成回复失败？")
                return

            # 发送消息
            with Timer("发送消息", timing_results):
                first_bot_msg = await self._send_response_messages(message, chat, response_set, thinking_id)

            info_catcher.catch_after_response(timing_results["发送消息"], response_set, first_bot_msg)

            info_catcher.done_catch()

            # 处理表情包
            with Timer("处理表情包", timing_results):
                await self._handle_emoji(message, chat, response_set)

            # 更新关系情绪
            with Timer("更新关系情绪", timing_results):
                await self._update_relationship(message, response_set)

            # 回复后处理
            await willing_manager.after_generate_reply_handle(message.message_info.message_id)

        # 输出性能计时结果
        if do_reply:
            timing_str = " | ".join([f"{step}: {duration:.2f}秒" for step, duration in timing_results.items()])
            trigger_msg = message.processed_plain_text
            response_msg = " ".join(response_set) if response_set else "无回复"
            logger.info(f"触发消息: {trigger_msg[:20]}... | 推理消息: {response_msg[:20]}... | 性能计时: {timing_str}")
        else:
            # 不回复处理
            await willing_manager.not_reply_handle(message.message_info.message_id)

        # 意愿管理器：注销当前message信息
        willing_manager.delete(message.message_info.message_id)

    @staticmethod
    def _check_ban_words(text: str, chat, userinfo) -> bool:
        """检查消息中是否包含过滤词"""
        for word in global_config.ban_words:
            if word in text:
                logger.info(
                    f"[{chat.group_info.group_name if chat.group_info else '私聊'}]{userinfo.user_nickname}:{text}"
                )
                logger.info(f"[过滤词识别]消息中含有{word}，filtered")
                return True
        return False

    @staticmethod
    def _check_ban_regex(text: str, chat, userinfo) -> bool:
        """检查消息是否匹配过滤正则表达式"""
        for pattern in global_config.ban_msgs_regex:
            if pattern.search(text):
                logger.info(
                    f"[{chat.group_info.group_name if chat.group_info else '私聊'}]{userinfo.user_nickname}:{text}"
                )
                logger.info(f"[正则表达式过滤]消息匹配到{pattern}，filtered")
                return True
        return False

    async def start_monitoring_interest(self, chat: ChatStream):
        """为指定的 ChatStream 启动后台兴趣消息监控任务。"""
        stream_id = chat.stream_id
        # 检查任务是否已在运行
        if stream_id in self._interest_monitoring_tasks and not self._interest_monitoring_tasks[stream_id].done():
            task = self._interest_monitoring_tasks[stream_id]
            if not task.cancelled():  # 确保任务未被取消
                logger.info(f"兴趣监控任务已在运行 stream: {stream_id}")
                return
            else:
                logger.info(f"发现已取消的任务，重新创建 stream: {stream_id}")
                # 如果任务被取消了，允许重新创建

        logger.info(f"启动兴趣监控任务 stream: {stream_id}...")
        # 创建新的后台任务来运行 _find_interested_message
        task = asyncio.create_task(self._find_interested_message(chat))
        self._interest_monitoring_tasks[stream_id] = task

        # 添加回调，当任务完成（或被取消）时，自动从字典中移除
        task.add_done_callback(lambda t: self._handle_task_completion(stream_id, t))

    def _handle_task_completion(self, stream_id: str, task: asyncio.Task):
        """处理监控任务完成的回调。"""
        try:
            # 检查任务是否因异常而结束
            exception = task.exception()
            if exception:
                logger.error(f"兴趣监控任务 stream {stream_id} 异常结束: {exception}", exc_info=exception)
            elif task.cancelled():
                logger.info(f"兴趣监控任务 stream {stream_id} 已被取消。")
            else:
                logger.info(f"兴趣监控任务 stream {stream_id} 正常结束。")  # 理论上 while True 不会正常结束
        except asyncio.CancelledError:
            logger.info(f"兴趣监控任务 stream {stream_id} 在完成处理期间被取消。")
        finally:
            # 无论如何都从字典中移除
            removed_task = self._interest_monitoring_tasks.pop(stream_id, None)
            if removed_task:
                logger.debug(f"已从监控任务字典移除 stream: {stream_id}")

    async def stop_monitoring_interest(self, stream_id: str):
        """停止指定 stream_id 的兴趣消息监控任务。"""
        if stream_id in self._interest_monitoring_tasks:
            task = self._interest_monitoring_tasks[stream_id]
            if not task.done():
                logger.info(f"正在停止兴趣监控任务 stream: {stream_id}...")
                task.cancel()  # 请求取消任务
                try:
                    # 等待任务实际被取消（可选，提供更明确的停止）
                    # 设置超时以防万一
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.CancelledError:
                    logger.info(f"兴趣监控任务 stream {stream_id} 已确认取消。")
                except asyncio.TimeoutError:
                    logger.warning(f"停止兴趣监控任务 stream {stream_id} 超时。任务可能仍在运行。")
                except Exception as e:
                    # 捕获 task.exception() 可能在取消期间重新引发的错误
                    logger.error(f"停止兴趣监控任务 stream {stream_id} 时发生错误: {e}")
            # 任务最终会由 done_callback 移除，或在这里再次确认移除
            self._interest_monitoring_tasks.pop(stream_id, None)
        else:
            logger.warning(f"尝试停止不存在或已停止的监控任务 stream: {stream_id}")
