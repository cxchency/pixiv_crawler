import re
import os
import logging
from colorama import init, Fore, Style
from datetime import time

from concurrent_log_handler import ConcurrentTimedRotatingFileHandler

# 定义日志格式
LOG_FORMAT = '[%(asctime)s]%(levelname)s[%(module)s]: %(message)s'

# 初始化 colorama
init(autoreset=True)

def strip_ansi(text: str) -> str:
    """去除 ANSI 颜色代码"""
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

class NoColorFormatter(logging.Formatter):
    """去除 ANSI 颜色代码的格式化器"""
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        return strip_ansi(message)

class CustomColorFormatter(logging.Formatter):
    """自定义控制台输出格式化器"""
    def format(self, record: logging.LogRecord) -> str:
        # 获取完整的模块路径
        try:
            pathname = record.pathname
            # 获取相对路径，去掉项目根目录的路径部分
            module_path = os.path.relpath(pathname, start=os.getcwd())  # 获取相对路径
            module_path = module_path.replace(os.sep, '.')  # 将路径分隔符替换为点（.）
            module_path = '.'.join(module_path.split('.')[0:-1])  # 保留路径部分
        except Exception as e:
            # 如果获取模块路径失败，使用默认的模块名
            module_path = record.module

        log_colors = {
            'DEBUG': Fore.BLUE,
            'INFO': Fore.GREEN,
            'WARNING': Fore.YELLOW,
            'ERROR': Fore.RED,
            'CRITICAL': Fore.RED + Style.BRIGHT,
        }
        levelname_color = log_colors.get(record.levelname, Fore.WHITE)
        module_color = Fore.CYAN
        message_color = Fore.WHITE

        message = record.msg
        parts = re.split(r'(\[.*?\])', message)
        colored_message_parts = [f'{Fore.YELLOW}{part}{Style.RESET_ALL}' if part.startswith('[') and part.endswith(']') else part for part in parts]
        message = ''.join(colored_message_parts)

        record.levelname = f"{levelname_color}{record.levelname}{Style.RESET_ALL}"
        record.module = f"{module_color}{module_path}{Style.RESET_ALL}"  # 显示完整模块路径
        record.msg = f"{message_color}{message}{Style.RESET_ALL}"

        return super().format(record)

# 主函数
def get_logger(name: str = 'logger', is_debug: bool = False) -> logging.Logger:
    """获取日志记录器"""
    logger = logging.getLogger(name)

    # 如果已经设置过 Handler，就直接返回（防止重复添加 handler）
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if is_debug else logging.INFO)

    # 日志目录
    log_dir = 'logs/'
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'{name}.log')
    
    file_handler = ConcurrentTimedRotatingFileHandler(filename=log_file, when='midnight', backupCount=999999,
                                                             encoding='utf-8', atTime=time(), delay=True)
    file_handler.setFormatter(NoColorFormatter(LOG_FORMAT))
    file_handler.setLevel(logging.DEBUG if is_debug else logging.INFO)
    logger.addHandler(file_handler)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomColorFormatter(LOG_FORMAT))
    console_handler.setLevel(logging.DEBUG if is_debug else logging.INFO)
    logger.addHandler(console_handler)

    return logger
