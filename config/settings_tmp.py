
# 日志记录器
from core.logger import get_logger
from core.utils import load_cookies_from_file
logger = get_logger('pixiv')

# 从文件加载 cookies（请确保 config/cookies.txt 只有一行完整 cookie 字符串）
COOKIES = load_cookies_from_file("config/cookies.txt")

# 目标用户 ID（需填写你要爬取的 Pixiv 用户的数字 ID，例如 '12345678'）
TARGET_USER_ID = ""

# MySQL 数据库配置
DATABASE_CONFIG = {
    'host': "",      # 数据库主机地址，如 'localhost' 或远程 IP
    'user': "",      # 数据库用户名
    'password': "",  # 数据库密码
    'database': "",  # 数据库名称
}

# 请求头（一般保持默认即可，如需自定义 UA 可修改）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1", # 可自定义
    'Referer': 'https://www.pixiv.net/'
}

# 本地和远程目录配置
# LOCAL_DIR：图片压缩后保存的本地目录（如 r"D:\pixiv_images"）
# REMOTE_DIR：原始图片下载保存目录（如 r"D:\pixiv_downloads"）
LOCAL_DIR = r""
REMOTE_DIR = r""

# 代理配置（如需使用代理访问 Pixiv，填写代理地址，否则留空）
PROXIES = {}
# PROXIES = {
#     "http": "",   # 例如 "http://127.0.0.1:7890"
#     "https": "",  # 例如 "http://127.0.0.1:7890"
# }