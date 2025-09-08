from typing import Optional
import subprocess
import os

import requests
import time

from config.settings import *
from core.utils import load_cookies_from_file

COOKIES = load_cookies_from_file("config/cookies.txt")

def download_image(url: str, save_path: str, use_cookies: bool = False, retry: int = 5) -> None:
    """使用aria2下载图片，带重试和完整性检查"""
    for attempt in range(retry):
        try:
            # 构建aria2c命令
            # if os.path.exists(save_path):
            #     logger.info(f"文件已存在，跳过下载: {save_path}")
            #     raise FileExistsError(f"文件已存在: {save_path}")
            cmd = [
                'aria2c',
                '--user-agent=' + HEADERS.get('User-Agent', ''),
                '--referer=' + HEADERS.get('Referer', ''),
                '--dir=' + os.path.dirname(save_path),
                '--out=' + os.path.basename(save_path),
                '--max-tries=10',
                '--retry-wait=1',
                '--timeout=30',
                '--continue=true',
                '--check-integrity=true',
                '--allow-overwrite=true',
                url
            ]

            # 如果配置了代理，添加代理选项
            if PROXIES and 'http' in PROXIES:
                cmd.extend(['--all-proxy=' + PROXIES['http']])

            # 如果使用cookies，添加cookie选项
            if use_cookies and COOKIES:
                cookie_str = '; '.join([f"{k}={v}" for k, v in COOKIES.items()])
                cmd.extend(['--header=Cookie: ' + cookie_str])

            # 执行下载
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=600)
            
            if result.returncode == 0:
                # 检查文件是否存在且大小大于0
                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    return
                else:
                    raise Exception("Downloaded file is empty or missing")
            else:
                # 收集所有可用的错误信息
                error_details = []
                error_details.append(f"退出码: {result.returncode}")
                if result.stderr.strip():
                    error_details.append(f"stderr: {result.stderr.strip()}")
                if result.stdout.strip():
                    error_details.append(f"stdout: {result.stdout.strip()}")
                error_details.append(f"命令: {' '.join(cmd)}")
                
                raise Exception(f"aria2c failed: {'; '.join(error_details)}")

        except Exception as e:
            logger.warning(f"[{url}][尝试 {attempt + 1}/{retry}] 下载失败：{e}")
            # 清理可能的不完整文件
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except:
                    pass
            time.sleep(1)

    raise Exception(f"多次尝试后仍无法下载：{url}")

def get_bookmarks(user_id: str, offset: int = 0, limit: int = 100, lang: str = "zh") -> Optional[dict]:
    """获取用户的收藏夹信息"""
    url = f"https://www.pixiv.net/ajax/user/{user_id}/illusts/bookmarks?tag=&rest=show&offset={offset}&limit={limit}&lang={lang}"
    # print(url)
    response = requests.get(url, headers=HEADERS, cookies=COOKIES, proxies=PROXIES)
    if response.status_code == 200:
        data: dict = response.json()
        if not data.get("error"):
            body: dict = data.get("body", {})
            body.pop("ads", None)
            return body
        else:
            raise Exception(f"Error fetching bookmarks: {data.get('message', 'Unknown error')}")
    else:
        raise Exception(f"Failed to fetch bookmarks, status code: {response.status_code}")

def get_illust_details(illust_id: int, lang: str = "zh", use_cookies = False, retry: int = 16) -> Optional[dict]:
    """获取插画的详细信息"""
    for attempt in range(retry):
        try:
            url = f"https://www.pixiv.net/touch/ajax/illust/details?illust_id={illust_id}&lang={lang}"
            if use_cookies:
                response = requests.get(url, headers=HEADERS, cookies=COOKIES, proxies=PROXIES)
            else:
                response = requests.get(url, headers=HEADERS, proxies=PROXIES)
            if response.status_code == 200:
                data: dict = response.json()
                if not data.get("error"):
                    body: dict = data.get("body", {})
                    body.pop("ads", None)
                    illust_details = body.get("illust_details", {})
                    if illust_details.get("mask_reason"):
                        logger.warning(f"插画 {illust_id} 被屏蔽，尝试使用 cookies 重新获取")
                        return get_illust_details(illust_id, lang, use_cookies=True, retry=retry)
                    return body
                else:
                    raise Exception(f"Error fetching illust details: {data.get('message', 'Unknown error')}")
            else:
                raise Exception(f"Failed to fetch illust details, status code: {response.status_code}")
        except Exception as e:
            if attempt < retry - 1:
                logger.warning(f"[插画 {illust_id}][尝试 {attempt + 1}/{retry}] 获取详情失败：{e}")
                time.sleep(1)
            else:
                raise Exception(f"多次尝试后仍无法获取插画详情 {illust_id}: {e}")