import win32com.client
import win32con
import win32gui
import datetime
import pythoncom
import time

def create_scheduled_task(task_name, bat_path, delay_seconds):
    """
    创建一次性定时任务来运行批处理文件
    
    :param task_name: 任务名称（需唯一）
    :param bat_path: 批处理文件的绝对路径
    :param delay_minutes: 延迟执行的分钟数
    """
    try:
        # 初始化COM对象
        pythoncom.CoInitialize()
        
        # 连接到任务计划程序服务
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        
        # 获取根任务文件夹
        root_folder = scheduler.GetFolder('\\')
        
        # 创建新任务定义
        task_def = scheduler.NewTask(0)
        
        # 配置任务设置
        task_def.Settings.Enabled = True
        task_def.Settings.StartWhenAvailable = True  # 如果错过时间仍启动
        task_def.Settings.DisallowStartIfOnBatteries = False
        task_def.Settings.StopIfGoingOnBatteries = False
        
        # 设置触发器（一次性触发）
        start_time = datetime.datetime.now() + datetime.timedelta(seconds=delay_seconds)
        trigger = task_def.Triggers.Create(1)  # 1代表TASK_TRIGGER_TIME
        trigger.StartBoundary = start_time.isoformat()  # ISO 8601格式时间
        trigger.Enabled = True
        
        # 设置操作（运行批处理文件）
        action = task_def.Actions.Create(0)  # 0代表TASK_ACTION_EXEC
        action.Path = bat_path
        
        # 配置用户上下文（此处使用当前用户，无需密码）
        task_def.Principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN（交互式登录）
        task_def.Principal.RunLevel = 0   # TASK_RUNLEVEL_LUA（默认权限）
        
        # 注册任务（如果存在则更新）
        TASK_CREATE_OR_UPDATE = 6
        TASK_LOGON_NONE = 0
        root_folder.RegisterTaskDefinition(
            task_name,
            task_def,
            TASK_CREATE_OR_UPDATE,
            '',  # 空用户表示当前用户
            '',  # 无密码
            TASK_LOGON_NONE
        )
        
        #print(f"任务 '{task_name}' 创建成功，将在 {seconds} 分钟后运行")
    except Exception as e:
        print(f"创建任务失败: {str(e)}")
    finally:
        # 清理COM资源
        pythoncom.CoUninitialize()

def close_window(window_name):
    # 获取窗口句柄
    hwnd = win32gui.FindWindow(None, window_name)
    if hwnd:
        # 发送关闭消息
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    else:
        print("窗口未找到")

# 使用示例
"""
if __name__ == "__main__":
    bat_path = r'D:\Good_Stuff\MaiBot\MaiMai\start.bat'  # 替换为你的批处理文件路径
    task_name = 'LaunchMaiBot'               # 自定义任务名称
    delay_seconds = 20                       # 延迟10分钟执行
    create_scheduled_task(task_name, bat_path, delay_seconds)
    time.sleep(30)
    close_window("MaiBot")
"""