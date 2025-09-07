from __future__ import annotations
import os
import exiftool
import threading
import time
import functools
from typing import Dict, TYPE_CHECKING
from PIL import Image as PILImage
import zipfile
import io

import imageio
from config.settings import *

if TYPE_CHECKING:
    from core.models import Image, Artwork

def retry_on_error(max_retries=5, delay=1):
    """重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"函数 {func.__name__} 在重试 {max_retries} 次后仍然失败: {e}", exc_info=True)
                        raise
                    else:
                        logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}，将在 {delay} 秒后重试")
                        time.sleep(delay)
            return None
        return wrapper
    return decorator

def load_cookies_from_file(file_path: str) -> Dict[str, str]:
    """从文件中加载cookies"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as fc:
            cookie_str = fc.read()
            cookie_str.strip()
            cookies = dict([l.split("=", 1) for l in cookie_str.split("; ")]) if cookie_str else {}
    else:
        logger.warning(f"cookies文件不存在: {file_path}")
        cookies = {}
    return cookies

@retry_on_error()    
def compress_to_webp(input_image_path, output_image_path, quality=85):
    """
    将图像压缩为 WebP 格式并保存
    """
    img = PILImage.open(input_image_path)
    img.save(output_image_path, format='WEBP', quality=quality, method=6)
    return input_image_path, output_image_path


@retry_on_error()    
def zip_to_webp(zip_path, webp_path, metadata, quality=85):
    # 获取文件名
    durations = [i['delay'] for i in metadata.get('frames', [])]
    
    # 打开 ZIP 文件
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # 获取 ZIP 文件中的所有文件列表
        file_list = zip_ref.namelist()
        
        # 过滤出图像文件（假设所有文件都是图像）
        image_files = [f for f in file_list if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        # logger.info(f"ZIP文件中找到 {len(image_files)} 个图像文件")
        
        # 读取第一帧作为背景
        first_frame_data = zip_ref.read(image_files[0])
        background = PILImage.open(io.BytesIO(first_frame_data)).convert("RGBA")
        
        # 读取所有帧并保存帧数据和持续时间
        frames = []
        
        for image_file in image_files:
            frame_data = zip_ref.read(image_file)
            pil_image = PILImage.open(io.BytesIO(frame_data)).convert("RGBA")
            
            # 使用第一帧作为背景合成
            frame_with_background = PILImage.alpha_composite(background, pil_image)
            frames.append(frame_with_background)
        return True

    
    # 保存为 WebP 格式，保持每帧的持续时间
    frames[0].save(
        webp_path,
        format="WebP",
        save_all=True,
        append_images=frames[1:],  # 追加后续帧
        loop=0,  # 循环播放
        lossless=False,  # 使用有损压缩
        quality=75,
        duration=durations,  # 每帧的持续时间
        method=6
    )
    

@retry_on_error()    
def gif_to_webp(gif_path, webp_path, quality=85):
    # 使用 imageio.get_reader 读取 GIF 文件
    reader = imageio.get_reader(gif_path, format='GIF')
    
    # 获取每一帧的持续时间
    durations = []
    frames_data = []
    
    for frame_idx in range(len(reader)):  # 遍历所有帧
        frame_meta = reader.get_meta_data(frame_idx)
        durations.append(frame_meta.get('duration', 100))  # 默认持续时间100ms
        frames_data.append(reader.get_data(frame_idx))  # 保存帧数据
    
    # 使用第一帧作为背景
    background = PILImage.fromarray(frames_data[0]).convert("RGBA")  # 将第一帧作为背景
    
    # 合成帧
    frames = []
    for i, frame in enumerate(frames_data):
        pil_image = PILImage.fromarray(frame).convert("RGBA")
        
        # 使用第一帧作为背景合成
        frame_with_background = PILImage.alpha_composite(background, pil_image)
        frames.append(frame_with_background)
    
    # 保存为 WebP 格式，保持每帧的持续时间
    frames[0].save(
        webp_path,
        format="WebP",
        save_all=True,
        append_images=frames[1:],  # 追加后续帧
        loop=0,  # 循环播放
        lossless=False,  # 使用有损压缩
        quality=75,  # 设置质量
        duration=durations,  # 每帧的持续时间
        method=6
    )
    
    
class ExifToolWorker:
    """
    每个线程独立持有一个 ExifTool 实例，重复使用。
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.et = exiftool.ExifTool(encoding='utf-8')
        self.et.__enter__()

    @retry_on_error()
    def process_image(self, image: Image, artwork: Artwork):
        try:
            tags = ["[pixiv]", f"id:{image.idNum}", f"user:{artwork.user_id}"]
            if image.is_deleted:
                tags.append("[已删除]")
            if artwork.aiType == 2:
                tags.append("AI生成")
            tags.extend([tag.display_tag for tag in artwork.tags])
            args = [
                f'-XMP-dc:title={str(image.index).zfill(3)} {artwork.title}'.encode('utf-8'),
                f'-XMP-dc:description={artwork.comment}'.encode('utf-8'),
                f'-XMP-dc:Creator={artwork.user_name}'.encode('utf-8'),
                f'-XMP-dc:source=https://www.pixiv.net/artworks/{image.idNum}'.encode('utf-8'),
            ]
            
            if artwork.timestamp:
                dt_original_str = artwork.timestamp.strftime('%Y:%m:%d %H:%M:%S')
                args.append(f'-DateTimeOriginal={dt_original_str}'.encode('utf-8'))
            else:
                args.append(f'-DateTimeOriginal=2007:09:10 00:00:00'.encode('utf-8'))
                
            
            args.extend([f'-XMP-dc:Subject={tag}'.encode('utf-8') for tag in tags])
            args.extend([
                f'-overwrite_original'.encode('utf-8'),
                image.compressed_path.encode('utf-8')
            ])

            with self.lock:
                self.et.execute(*args)
        except Exception as e:
            logger.error(f"处理 {image.compressed_path} 出错: {e}", exc_info=True)
            raise

    def close(self):
        self.et.__exit__(None, None, None)
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()