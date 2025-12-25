# -*- coding: utf-8 -*-
"""
AIGC数据库保存辅助模块
用于将AIGC生成的内容保存到相应的数据库表
"""

import os
import sys
import json
import re
from typing import Dict, Optional, List
from PIL import Image

# 添加项目根目录到路径，以便导入父目录的模块
# 使用相对路径添加项目根目录到sys.path
current_file_dir = os.path.dirname(os.path.realpath(__file__))
project_root = os.path.dirname(current_file_dir)
sys.path.insert(0, project_root)
from db_connection import get_user_db_connection, get_user_db_config
from festival_name_utils import chinese_to_english_festival, extract_and_convert_festival_name


def extract_festival_names(text: str) -> List[str]:
    """从文本中提取节日名称"""
    # 常见的节日关键词模式
    festival_patterns = [
        r'([\u4e00-\u9fa5]{2,10}节)',  # 如：春节、中秋节
        r'([\u4e00-\u9fa5]{2,10}日)',  # 如：端午节、重阳日
        r'([\u4e00-\u9fa5]{2,10}节庆)',  # 如：春节庆
    ]
    
    festival_names = []
    for pattern in festival_patterns:
        matches = re.findall(pattern, text)
        festival_names.extend(matches)
    
    # 去重并过滤
    festival_names = list(set(festival_names))
    # 过滤掉明显不是节日的词
    filter_words = ['节日', '节庆', '习俗', '传统', '文化', '活动', '仪式']
    festival_names = [name for name in festival_names if not any(word in name for word in filter_words)]
    
    return festival_names[:3]  # 最多返回3个节日名称


def save_aigc_text_resource(
    db_config: Dict,
    resource_title: str,
    content_text: str,
    source_from: str = "AIGC",
    festival_title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    retrieved_resource_ids: Optional[List[str]] = None
) -> Optional[int]:
    """
    保存AIGC生成的文字资源到AIGC_cultural_resources和AIGC_cultural_entities表
    
    Args:
        db_config: 数据库配置
        resource_title: 文化资源名称
        content_text: 文本内容
        source_from: 数据来源（AIGC模型名称）
        festival_title: 节日名称（如果为None，会从文本中提取）
        tags: 标签列表
    
    Returns:
        保存的资源ID，失败返回None
    """
    conn = None
    try:
        # 使用db_connection.py的统一连接函数
        conn = get_user_db_connection()
        if conn is None:
            raise Exception("无法连接到数据库，请检查数据库配置")
        
        cursor = conn.cursor()
        
        # 如果没有提供节日名称，从文本中提取（中文）
        if not festival_title:
            festival_names = extract_festival_names(content_text)
            if not festival_names:
                festival_names = extract_festival_names(resource_title)
            chinese_festival_name = festival_names[0] if festival_names else "传统节日"
        else:
            chinese_festival_name = festival_title
            festival_names = [festival_title]
        
        # 转换为英文节日名称
        festival_title_en = chinese_to_english_festival(chinese_festival_name)
        
        # 构建content_feature_data
        meta = {
            "tags": tags or [],
            "festival_names": festival_names,
            "festival_name_en": festival_title_en
        }
        content_feature_data = json.dumps({
            "title": resource_title,
            "text": content_text,
            "meta": meta
        }, ensure_ascii=False)
        
        # 处理检索资源ID（转换为逗号分隔的字符串）
        retrieved_ids_str = None
        if retrieved_resource_ids:
            retrieved_ids_str = ','.join(retrieved_resource_ids)
        
        # 1. 保存到AIGC_cultural_resources表（title字段存储英文节日名称）
        cursor.execute("""
            INSERT INTO AIGC_cultural_resources 
            (title, resource_type, file_format, source_from, content_feature_data, 
             retrieved_resource_ids, version, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, 1, NOW(), NOW())
        """, (
            festival_title_en,  # title字段存储英文节日名称
            "文本",
            "TXT",
            source_from,
            content_feature_data,
            retrieved_ids_str  # 检索资源ID列表
        ))
        
        resource_id = cursor.lastrowid
        
        # 2. 保存到AIGC_cultural_entities表（entity_name字段存储文化资源名称，description存储详细文化信息）
        # 实体类型默认为"其他"（因为文化资源本身不属于人物、作品、事件、地点）
        cursor.execute("""
            INSERT INTO AIGC_cultural_entities
            (entity_name, entity_type, description, source)
            VALUES (%s, %s, %s, %s)
        """, (
            resource_title,  # entity_name字段存储文化资源名称
            "其他",  # entity_type使用枚举值：人物、作品、事件、地点、其他
            content_text,  # description存储完整的文本内容（详细文化信息）
            source_from
        ))
        
        conn.commit()
        return resource_id
        
    except Exception as e:
        print(f"保存AIGC文字资源失败: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()


def save_aigc_image(
    db_config: Dict,
    image_path: str,
    source_from: str = "AIGC",
    tags: Optional[List[str]] = None
) -> Optional[int]:
    """
    保存AIGC生成的图片到AIGC_graph表
    
    Args:
        db_config: 数据库配置
        image_path: 图片文件路径
        source_from: 数据来源（AIGC模型名称）
        tags: 标签列表
    
    Returns:
        保存的图片ID，失败返回None
    """
    if not os.path.exists(image_path):
        print(f"图片文件不存在: {image_path}")
        return None
    
    conn = None
    try:
        # 使用db_connection.py的统一连接函数
        conn = get_user_db_connection()
        if conn is None:
            raise Exception("无法连接到数据库，请检查数据库配置")
        
        cursor = conn.cursor()
        
        # 获取文件名和存储路径
        file_name = os.path.basename(image_path)
        # 确保storage_path是相对于AIGC_graph文件夹的路径
        if "AIGC_graph" in image_path:
            storage_path = image_path.replace("\\", "/")
            # 提取AIGC_graph之后的部分
            if "/AIGC_graph/" in storage_path:
                storage_path = "AIGC_graph/" + storage_path.split("/AIGC_graph/")[-1]
            elif "AIGC_graph\\" in storage_path:
                storage_path = "AIGC_graph/" + storage_path.split("AIGC_graph\\")[-1].replace("\\", "/")
        else:
            storage_path = f"AIGC_graph/{file_name}"
        
        # 获取图片尺寸
        dimensions = None
        try:
            with Image.open(image_path) as img:
                dimensions = f"{img.width}x{img.height}"
        except:
            pass
        
        # 保存到AIGC_graph表
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        
        cursor.execute("""
            INSERT INTO AIGC_graph 
            (file_name, storage_path, dimensions, tags, upload_time)
            VALUES (%s, %s, %s, %s, NOW())
        """, (file_name, storage_path, dimensions, tags_json))
        
        image_id = cursor.lastrowid
        conn.commit()
        return image_id
        
    except Exception as e:
        print(f"保存AIGC图片失败: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            cursor.close()
            conn.close()

