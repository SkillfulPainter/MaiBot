from src.do_tool.tool_can_use.base_tool import BaseTool, register_tool
from typing import Dict, Any
from src.plugins.reboot.reboot import close_window
import time


class ProcessCloseTool(BaseTool):
    """进程关键词触发关闭重启工具"""

    name = "close_tool"
    description = "只在用户明确说出以下语句：“麦麦,关机”的时候才可以使用此工具。在其他任何情况下都不要使用此工具。此工具的作用是将主程序关闭。"

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
                time.sleep(function_args['delay_seconds'])
            finally:
                close_window("MNA")
                close_window("麦麦Bot控制台 v1.0")
        else:
            return {
                "name": self.name,
                "content": "就不关就不关，略略略~~~"
            }

# 注册工具
#register_tool(ProcessRestartTool)