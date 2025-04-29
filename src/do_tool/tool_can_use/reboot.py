from src.do_tool.tool_can_use.base_tool import BaseTool, register_tool
from typing import Dict, Any
from src.plugins.reboot.reboot import create_scheduled_task, close_window
import time


class ProcessRestartTool(BaseTool):
    """进程关键词触发关闭重启工具"""

    name = "reboot_tool"
    description = "只在用户明确说出以下语句：“麦麦，重启”的时候才可以使用此工具。在其他任何情况下都不要使用此工具。此工具的作用是将主程序关闭重启。"

    parameters = {
        "type": "object",
        "properties": {
            "delay_seconds": {
                "type": "integer",
                "description": "延迟关闭时间（秒），若用户所述时间为分钟，则转换为秒钟，若用户未声明时间，则设为3"
            },
            "user_id": {
                "type": "string",
                "description": "发送该消息的人的昵称"
            },
        },
        "required": ["delay_seconds"]
    }

    async def execute(self, function_args: Dict[str, Any], message_txt: str = "") -> Dict[str, Any]:
        """执行关闭重启逻辑"""
        #from src.main import MainSystem
        #main_system = MainSystem()
        if function_args['user_id'] == "火火火木":
            try:

                # 推送任务指令到队列
                bat_path_1 = r'D:\Good_Stuff\MaiBot\MaiMai\start.bat'  # 替换为你的批处理文件路径
                task_name_1 = 'LaunchMaiBot'
                bat_path_2 = r'D:\Good_Stuff\MaiBot\MaiBot-Napcat-Adapter\start.bat'  # 替换为你的批处理文件路径
                task_name_2 = 'LaunchMNA'
                """
                await main_system.task_command_queue.put({
                    "function": "reboot",  # 监控函数
                    "args": {
                        "delay_seconds": function_args['delay_seconds']
                    }
                })

                return {
                    "name": self.name,
                    "content": f"林晓麦的主程序将在{function_args['delay_seconds']}秒后关闭！！！不过{function_args['delay_seconds']+5}秒后就会重启了~~"
                }
                """
                create_scheduled_task(
                    task_name=task_name_1,
                    bat_path=bat_path_1,
                    delay_seconds=function_args['delay_seconds'] + 3,
                )
                create_scheduled_task(
                    task_name=task_name_2,
                    bat_path=bat_path_2,
                    delay_seconds=function_args['delay_seconds'] + 4,
                )
                # 添加后置处理（如状态记录）
                # logger.success(f"动态任务完成: {func.__name__}")

            finally:
                time.sleep(function_args['delay_seconds'])
                close_window("MNA")
                close_window("麦麦Bot控制台 v1.0")
        else:
            return {
                "name": self.name,
                "content": "就不关就不关，略略略~~~"
            }

# 注册工具
#register_tool(ProcessRestartTool)