from core.utils import zip_to_webp, compress_to_webp, ExifToolWorker
import json
from core.models import Artwork, Tag, ArtworkType, ArtworkRestrict, Image
from datetime import datetime
import core.database as db
import core.api as api
from tqdm import tqdm
from config.settings import *
import concurrent.futures
import os

# 0. 初始化
new_artworks: dict[str, Artwork] = {}
new_images: list[Image] = []
logger.info("开始获取数据库中的收藏夹信息...")
local_bookmarks_id_set = {str(id) for id in db.get_bookmark_ids()}
logger.info(f"本地收藏夹数量: {len(local_bookmarks_id_set)}")

# 1. 获取远程用户的收藏夹
all_new_bookmarks = []
offset = 0
limit = 100
while True:
    page_data: dict = api.get_bookmarks(TARGET_USER_ID, offset=offset, limit=limit, lang="zh")
    bookmarks: list = page_data.get("works", [])
    if not bookmarks:
        break
    bookmarks_id_set = {artwork["id"] for artwork in bookmarks}
    new_bookmarks = bookmarks_id_set - local_bookmarks_id_set
    if not new_bookmarks:
        break
    else:
        all_new_bookmarks.extend([b for b in bookmarks if b["id"] in new_bookmarks])
    logger.info(f"新增收藏数量: {len(new_bookmarks)}，当前总收藏数量: {len(all_new_bookmarks)}")
    offset += limit
    
# with open("new_bookmarks.json", "w", encoding="utf-8") as f:
#     json.dump(all_new_bookmarks, f, ensure_ascii=False, indent=4)
logger.info(f"获取到 {len(all_new_bookmarks)} 个新收藏。")

# with open("new_bookmarks.json", "r", encoding="utf-8") as f:
#     all_new_bookmarks = json.load(f)

if not all_new_bookmarks:
    logger.info("收藏夹中没有新的作品，程序结束。")
    exit(0)
    
# 2.获取详细信息
new_bookmarks_details = {}

def fetch_artwork_details(artwork):
    """获取插画详情函数"""
    try:
        if not artwork['userId']:
            local_artwork = db.get_bookmark_by_id(artwork["id"])
            if local_artwork:
                local_artwork.is_deleted = True
            else:
                local_artwork = Artwork(
                    id=artwork["id"],
                    is_deleted=True
                )
            db.upsert_bookmark(local_artwork)
            logger.info(f"作品 {artwork['id']} 已被删除，跳过处理。")
            return None
            
        details = api.get_illust_details(artwork["id"], lang="zh")
        if details:
            new_bookmarks_details[artwork["id"]] = details
        # time.sleep(1.6)  # 避免请求过快
        return details
    except Exception as e:
        logger.error(f"获取插画 {artwork['id']} 详情失败: {e}", exc_info=True)
        return None

# 使用多线程处理
max_workers = 16  # 可以根据需要调整线程数
with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    # 提交所有任务
    future_to_artwork = {executor.submit(fetch_artwork_details, artwork): artwork for artwork in all_new_bookmarks}
    
    # 使用tqdm显示进度
    with tqdm(total=len(all_new_bookmarks), desc="获取插画详情", unit="张") as pbar:
        for future in concurrent.futures.as_completed(future_to_artwork):
            pbar.update(1)
            
# with open("new_bookmarks_details.json", "w", encoding="utf-8") as f:
#     json.dump(new_bookmarks_details, f, ensure_ascii=False, indent=4)
logger.info(f"获取到 {len(new_bookmarks_details)} 个新的插画详情。")

# with open("new_bookmarks_details.json", "r", encoding="utf-8") as f:
#     new_bookmarks_details: dict = json.load(f)

if not new_bookmarks_details:
    logger.info("没有新的插画详情，程序结束。")
    exit(0)

# 3. 处理并下载

def download_and_process_image(image: Image, artwork: Artwork, save_name: str, use_cookies: bool, pbar: tqdm) -> Image:
    """下载并处理单个图片的函数"""
    
    if artwork.type == ArtworkType.ILLUST:
        type_dir = "Illustration"
    elif artwork.type == ArtworkType.MANGA:
        type_dir = "Manga"
    elif artwork.type == ArtworkType.UGOIRA:
        type_dir = "Ugoira"
    else:
        raise ValueError(f"未知的插画类型: {artwork.type}")
    try:
        # 下载图片
        save_path = rf"{REMOTE_DIR}\{type_dir}\{save_name}"
        api.download_image(image.url, save_path, use_cookies)
        image.original_path = save_path
        
        # 压缩图片
        if artwork.type == ArtworkType.UGOIRA:
            zip_path = image.original_path
            zip_name = os.path.basename(zip_path)
            webp_path = os.path.join(LOCAL_DIR, type_dir, zip_name.replace(".zip", ".webp"))
            metadata = artwork.ugoiraInfo
            if not zip_to_webp(zip_path, webp_path, metadata):
                raise ValueError(f"压缩 Ugoira 失败: {zip_path}")
            image.compressed_path = webp_path
        else:
            input_image_path = image.original_path
            image_name = os.path.basename(input_image_path)
            output_image_path = os.path.join(LOCAL_DIR, type_dir, image_name.replace(f".{image.ext}", ".webp"))
            if not compress_to_webp(input_image_path, output_image_path, quality=85):
                raise ValueError(f"压缩图片失败: {input_image_path}")
            image.compressed_path = output_image_path
        
        # 更新进度条
        pbar.update(1)
        return image
    except Exception as e:
        logger.error(f"下载图片 {image.id} 时出错: {e}", exc_info=True)
        pbar.update(1)  # 即使失败也要更新进度条
        return artwork.id

def process_artwork(artwork_data, pbar):
    """处理单个作品的函数"""
    artwork_id, details = artwork_data
    artwork_id = int(artwork_id)
    try:
        images: list[Image] = []
        illust_details: dict = details.get("illust_details", {})
        author_details: dict = details.get("author_details", {})
        manga_a: list = illust_details.get("manga_a", [])
        illust_images: list = illust_details.get("illust_images", [])
        display_tags = illust_details.get("display_tags", [])
        tags: list[Tag] = []
        use_cookies = True if illust_details.get("mask_reason") else False
        
        for tag in display_tags:
            tags.append(Tag(
                tag=tag.get("tag", ""),
                translation=tag.get("translation", tag.get("tag", "")),
            ))
        
        artwork = Artwork(
            id=artwork_id,
            title=illust_details.get("title", ""),
            comment=illust_details.get("comment_html", ""),
            pageCount=int(illust_details.get("page_count", 0)),
            user_id=int(author_details.get("user_id", 0)),
            user_name=author_details.get("user_name", ""),
            type=ArtworkType(int(illust_details.get("type", ArtworkType.ILLUST))),
            restrict=ArtworkRestrict(int(illust_details.get("x_restrict", ArtworkRestrict.NORMAL))),
            aiType=int(illust_details.get("ai_type")),
            timestamp=datetime.fromtimestamp(illust_details.get("upload_timestamp")),
            width=int(illust_details.get("width")),
            height=int(illust_details.get("height")),
            tags=tags,
            ugoiraInfo=illust_details.get("ugoira_meta", {}),
            data=details,
        )
        
        # 准备图片信息
        if artwork.type in [ArtworkType.ILLUST, ArtworkType.MANGA]:
            if artwork.pageCount == 1:
                image_url = illust_details.get("url_big", "")
                images.append(Image(
                    id=f"{artwork.id}_p0",
                    idNum=artwork.id,
                    index=0,
                    url=image_url,
                    height=artwork.height,
                    width=artwork.width,
                    ext=image_url.split(".")[-1].lower(),
                ))
            else:
                for manga, illust_image in zip(manga_a, illust_images):
                    image_url = manga.get("url_big", "")
                    images.append(Image(
                        id=f"{artwork.id}_p{manga['page']}",
                        idNum=artwork.id,
                        index=manga["page"],
                        url=image_url,
                        height=illust_image.get("illust_image_width", 0),
                        width=illust_image.get("illust_image_height", 0),
                        ext=image_url.split(".")[-1].lower()
                    ))
        elif artwork.type == ArtworkType.UGOIRA:
            ugoira_info = artwork.ugoiraInfo
            if ugoira_info:
                images.append(Image(
                    id=artwork.id,
                    idNum=artwork.id,
                    index=0,
                    url=ugoira_info.get("src", ""),
                    height=artwork.height,
                    width=artwork.width,
                    ext="zip"
                ))
        
        # 多线程下载和处理图片
        processed_images = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as img_executor:
            image_futures = []
            for image in images:
                save_name = f"{image.idNum}_p{str(image.index).zfill(3)} - {artwork.title} - {artwork.user_name}.{image.ext}".replace("<", "").replace(">", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("|", "").replace("?", "").replace("*", "").replace("\b", "")
                future = img_executor.submit(download_and_process_image, image, artwork, save_name, use_cookies, pbar)
                image_futures.append(future)
            
            for future in concurrent.futures.as_completed(image_futures):
                result = future.result()
                if result:
                    processed_images.append(result)
        
        # 数据库操作
        for image in processed_images:
            if isinstance(image, int):
                continue
            db.upsert_image(image)
            new_images.append(image)
        if any(isinstance(image, int) for image in processed_images):
            new_artworks[artwork_id] = None
            logger.warning(f"作品 {artwork_id} 下载失败，部分图片未能成功处理。")
            return 0
        else:
            db.upsert_bookmark(artwork)
            new_artworks[artwork_id] = artwork
            return len(processed_images)
        
    except Exception as e:
        logger.error(f"下载作品 {artwork_id} 时出错: {e}", exc_info=True)
        return 0

# 3. 多线程处理并下载
artwork_items = list(new_bookmarks_details.items())

# 计算总图片数量
total_images_count = 0
for artwork_id, details in artwork_items:
    illust_details = details.get("illust_details", {})
    page_count = int(illust_details.get("page_count", 1))
    total_images_count += page_count

logger.info(f"总共需要下载 {total_images_count} 张图片")

max_workers = 16  # 可以根据需要调整线程数
total_downloaded_images = 0

with tqdm(total=total_images_count, desc="下载图片", unit="张") as pbar:
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_artwork = {executor.submit(process_artwork, item, pbar): item for item in artwork_items}
        
        for future in concurrent.futures.as_completed(future_to_artwork):
            result = future.result()
            total_downloaded_images += result

logger.info(f"成功下载 {total_downloaded_images} 张图片")

# 4. 更新标签
NUM_WORKERS = 16  # 可根据你的 CPU 核心数调整
workers = [ExifToolWorker() for _ in range(NUM_WORKERS)]

def worker_task(worker: ExifToolWorker, image: Image):
    try:
        artwork = new_artworks.get(image.idNum)
        if artwork:
            worker.process_image(image, artwork)
    except Exception as e:
        logger.error(f"工作线程处理图片 {image.id} 时出错: {e}", exc_info=True)

try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = []
        for i, image in enumerate(new_images):
            worker = workers[i % NUM_WORKERS]
            futures.append(executor.submit(worker_task, worker, image))

        # 使用 tqdm 展示进度条
        for _ in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="标记图片", unit="张"):
            pass

finally:
    # 关闭所有 ExifTool 实例
    for worker in workers:
        worker.close()