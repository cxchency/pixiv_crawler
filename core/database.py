from dbutils.pooled_db import PooledDB
import mysql.connector
from dataclasses import asdict
import json
from typing import List, Dict, Any, TypeVar, Type
from contextlib import contextmanager
from enum import Enum

from config.settings import DATABASE_CONFIG
from core.models import Artwork, Image

DB_POOL = PooledDB(
    creator=mysql.connector,
    maxconnections=16,
    mincached=2,
    maxcached=16,
    blocking=True,
    ping=1,
    **DATABASE_CONFIG
)

@contextmanager
def get_db_cursor(dictionary=False):
    """数据库连接和游标的上下文管理器"""
    conn: mysql.connector.MySQLConnection = DB_POOL.connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield conn, cursor
    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def serialize_complex_fields(data_dict: Dict[str, Any]) -> Dict[str, Any]:
    """将复杂数据类型序列化为JSON字符串"""
    result = data_dict.copy()
    for key, value in result.items():
        # 处理枚举类型
        if isinstance(value, Enum):
            result[key] = value.value
        elif isinstance(value, (list, dict)):
            # 对于包含 dataclass 的复杂类型，先转换为可序列化的格式
            if isinstance(value, list) and value and hasattr(value[0], '__dataclass_fields__'):
                serializable_value = [asdict(item) for item in value]
            else:
                serializable_value = value
            result[key] = json.dumps(serializable_value, ensure_ascii=False)
    return result

def deserialize_complex_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """将JSON字符串反序列化为复杂数据类型"""
    result = row.copy()
    for key, value in result.items():
        if isinstance(value, str) and (value.startswith('[') or value.startswith('{')):
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return result

def upsert_entity(entity: Any, table_name: str) -> None:
    """通用的插入或更新实体到数据库"""
    with get_db_cursor() as (conn, cursor):
        entity_dict = serialize_complex_fields(asdict(entity))
        
        columns = ', '.join([f"`{col}`" for col in entity_dict.keys()])
        placeholders = ', '.join(['%s'] * len(entity_dict))
        values = tuple(entity_dict.values())
        
        # 构建UPDATE子句，排除主键id，为列名添加反引号
        update_assignments = ', '.join([f"`{col}` = VALUES(`{col}`)" for col in entity_dict.keys() if col != 'id'])
        
        cursor.execute(
            f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {update_assignments}",
            values
        )
        conn.commit()

def upsert_bookmark(artwork: Artwork) -> None:
    """插入或更新插画信息到数据库"""
    try:
        upsert_entity(artwork, 'bookmarks')
    except Exception as e:
        print(f"Error upserting bookmark: {e}")
        
def delete_bookmark(artwork_id: int) -> None:
    """根据ID删除书签"""
    try:
        with get_db_cursor() as (conn, cursor):
            cursor.execute("DELETE FROM bookmarks WHERE id = %s", (artwork_id,))
            conn.commit()
    except Exception as e:
        print(f"Error deleting bookmark: {e}")

def delete_image(image_id: str) -> None:
    """根据ID删除图片信息"""
    try:
        with get_db_cursor() as (conn, cursor):
            cursor.execute("DELETE FROM images WHERE id = %s", (image_id,))
            conn.commit()
    except Exception as e:
        print(f"Error deleting image: {e}")
        
def get_bookmarks() -> dict[int, Artwork]:
    """获取所有书签"""
    try:
        with get_db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT * FROM bookmarks")
            rows = cursor.fetchall()
            bookmarks = {}
            for row in rows:
                deserialized_row = deserialize_complex_fields(row)
                artwork = Artwork(**deserialized_row)
                bookmarks[artwork.id] = artwork
            return bookmarks
    except Exception as e:
        print(f"Error fetching bookmarks: {e}")
        return {}
    
def get_bookmark_ids() -> List[int]:
    """获取所有书签的ID列表"""
    try:
        with get_db_cursor() as (conn, cursor):
            cursor.execute("SELECT id FROM bookmarks")
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"Error fetching bookmark IDs: {e}")
        return []
    
def get_images() -> dict[str, Image]:
    """获取所有图片信息"""
    try:
        with get_db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT * FROM images")
            rows = cursor.fetchall()
            images = {}
            for row in rows:
                deserialized_row = deserialize_complex_fields(row)
                image = Image(**deserialized_row)
                images[image.id] = image
            return images
    except Exception as e:
        print(f"Error fetching images: {e}")
        return {}
    
def get_images_by_artwork_id(artwork_id: int) -> List[Image]:
    """根据插画ID获取所有相关图片信息"""
    try:
        with get_db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT * FROM images WHERE idNum = %s", (artwork_id,))
            rows = cursor.fetchall()
            images = []
            for row in rows:
                deserialized_row = deserialize_complex_fields(row)
                image = Image(**deserialized_row)
                images.append(image)
            return images
    except Exception as e:
        print(f"Error fetching images by artwork id: {e}")
        return []
        
def get_bookmark_by_id(artwork_id: int) -> Artwork:
    """根据ID获取单个书签"""
    try:
        with get_db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT * FROM bookmarks WHERE id = %s", (artwork_id,))
            row = cursor.fetchone()
            if row:
                deserialized_row = deserialize_complex_fields(row)
                return Artwork(**deserialized_row)
            return None
    except Exception as e:
        print(f"Error fetching bookmark by id: {e}")
        return None
    
def get_image_by_id(image_id: str) -> Image:
    """根据ID获取单个图片信息"""
    try:
        with get_db_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT * FROM images WHERE id = %s", (image_id,))
            row = cursor.fetchone()
            if row:
                deserialized_row = deserialize_complex_fields(row)
                return Image(**deserialized_row)
            return None
    except Exception as e:
        print(f"Error fetching image by id: {e}")
        return None
        
def upsert_image(image: Image) -> None:
    """插入或更新图片信息到数据库"""
    try:
        upsert_entity(image, 'images')
    except Exception as e:
        print(f"Error upserting image: {e}")