# -*- coding: utf-8 -*-
"""
中国民族文化资源库爬虫
爬取民族节日相关页面，提取图片并存储到crawled_images文件夹
"""

import os
import re
import json
import requests
from urllib.parse import urljoin, urlparse
from PIL import Image
import pymysql
from pymysql.cursors import DictCursor
from bs4 import BeautifulSoup
import time
import sys

# 添加项目根目录到路径，以便导入db_connection
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_connection import get_spider_db_connection, get_spider_db_config
from festival_name_utils import chinese_to_english_festival, extract_and_convert_festival_name

# 爬虫配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRAWLED_IMAGES_DIR = os.path.join(BASE_DIR, "crawled_images")
ALLOWED_DOMAINS = ["www.minwang.com.cn", "minwang.com.cn", "w.minwang.com.cn", 
                   "www.mzzyk.com", "mzzyk.com", "m.mzzyk.com"]
START_URLS = [
    "http://www.minwang.com.cn/mzwhzyk/674771/682393/index.html",
    "https://w.minwang.com.cn/mzwhzyk/674771/682393/index.html",
    "https://www.mzzyk.com/mzwhzyk/674771/682393/index.html",
]

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9"
}


class MinzuFestivalsSpider:
    def __init__(self):
        """初始化爬虫"""
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.visited_urls = set()
        self.db_conn = None
        self.db_cursor = None
        self.current_image_index = 0
        self.current_festival_base_index = 0  # 当前节日的基准序号
        self.current_festival_image_count = 0  # 当前节日已保存的图片数量
        self.current_festival_name = None  # 当前节日的名称
        
        # 数量限制
        self.max_text_items = 20  # 最大文字数据条数
        self.max_image_items = 20  # 最大图片数据条数
        self.text_items_count = 0  # 已爬取的文字数据条数
        self.image_items_count = 0  # 已爬取的图片数据条数
        
        # 确保crawled_images文件夹存在
        os.makedirs(CRAWLED_IMAGES_DIR, exist_ok=True)
        
        # 连接数据库
        self._connect_db()
        
        # 确保系统用户存在（用于爬虫数据）
        self._ensure_system_user()
        
        # 获取当前最大图片序号
        self._get_current_max_index()
    
    def _connect_db(self):
        """连接数据库（使用爬虫专用连接）"""
        try:
            self.db_conn = get_spider_db_connection()
            if self.db_conn is None:
                raise Exception("无法获取数据库连接")
            self.db_cursor = self.db_conn.cursor()
            print("数据库连接成功（使用爬虫专用账户）")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            raise
    
    def _ensure_system_user(self):
        """确保系统用户存在（用于爬虫数据）"""
        try:
            # 检查是否存在系统用户（account='system'或id=1）
            self.db_cursor.execute("SELECT id FROM users WHERE account = 'system' OR id = 1 LIMIT 1")
            user = self.db_cursor.fetchone()
            
            if user:
                self.system_user_id = user[0]
                print(f"使用系统用户ID: {self.system_user_id}")
            else:
                # 创建系统用户
                import hashlib
                # 使用一个固定的密码哈希（实际不会用于登录）
                password_hash = hashlib.sha256("system_user_password".encode()).hexdigest()
                # 生成系统用户账号（固定为'system'，但需要符合account字段要求）
                # 由于account是8-10位数字，我们使用一个特殊的数字账号
                system_account = '99999999'  # 8位数字，作为系统账号
                
                # 检查账号是否已存在
                self.db_cursor.execute("SELECT id FROM users WHERE account = %s", (system_account,))
                existing_user = self.db_cursor.fetchone()
                
                if existing_user:
                    self.system_user_id = existing_user[0]
                    print(f"使用已存在的系统用户ID: {self.system_user_id}")
                else:
                    self.db_cursor.execute("""
                        INSERT INTO users (account, password_hash, role, nickname, created_at)
                        VALUES (%s, %s, '管理员', '系统用户', NOW())
                    """, (system_account, password_hash))
                    self.db_conn.commit()
                    self.system_user_id = self.db_cursor.lastrowid
                    print(f"创建系统用户，ID: {self.system_user_id}, 账号: {system_account}")
        except Exception as e:
            print(f"确保系统用户失败: {e}")
            # 如果失败，尝试查找ID=1的用户
            try:
                self.db_cursor.execute("SELECT id FROM users WHERE id = 1")
                user = self.db_cursor.fetchone()
                if user:
                    self.system_user_id = 1
                    print(f"使用默认用户ID: {self.system_user_id}")
                else:
                    # 如果ID=1的用户不存在，使用NULL（外键允许NULL）
                    self.system_user_id = None
                    print("警告：未找到系统用户，将使用NULL作为upload_user_id")
            except Exception as e2:
                print(f"查找默认用户也失败: {e2}")
                self.system_user_id = None
                print("警告：将使用NULL作为upload_user_id")
    
    def _get_current_max_index(self):
        """获取当前crawled_images文件夹和数据库中的最大序号"""
        max_index = 0
        
        # 从文件夹中查找最大序号（支持 8.jpg 和 8-1.jpg 格式）
        if os.path.exists(CRAWLED_IMAGES_DIR):
            for filename in os.listdir(CRAWLED_IMAGES_DIR):
                if filename.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    try:
                        # 提取文件名中的数字（支持格式：8.jpg -> 8, 8-1.jpg -> 8）
                        base_name = os.path.splitext(filename)[0]
                        # 如果是 8-1 格式，提取第一个数字
                        if '-' in base_name:
                            base_name = base_name.split('-')[0]
                        if base_name.isdigit():
                            max_index = max(max_index, int(base_name))
                    except:
                        pass
        
        # 从数据库中查找最大序号（支持新旧格式）
        try:
            # 查找所有格式的文件名：8.jpg 或 8-1.jpg
            self.db_cursor.execute("""
                SELECT file_name FROM crawled_images 
                WHERE file_name REGEXP '^[0-9]+(-[0-9]+)?\\.[a-zA-Z]+$'
                ORDER BY CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(file_name, '-', 1), '.', 1) AS UNSIGNED) DESC
                LIMIT 1
            """)
            result = self.db_cursor.fetchone()
            if result:
                base_name = os.path.splitext(result['file_name'])[0]
                # 如果是 8-1 格式，提取第一个数字
                if '-' in base_name:
                    base_name = base_name.split('-')[0]
                if base_name.isdigit():
                    max_index = max(max_index, int(base_name))
        except Exception as e:
            print(f"从数据库获取最大序号失败（将仅使用文件夹中的序号）: {e}")
        
        self.current_image_index = max_index
        print(f"当前最大图片序号: {self.current_image_index}")
    
    def _get_next_image_name(self, image_url, is_same_festival=False):
        """
        获取下一个图片文件名
        :param image_url: 图片URL
        :param is_same_festival: 是否使用分组命名（同一资源的多张图片）
        :return: 文件名，如 "8.jpg" 或 "8-1.jpg", "8-2.jpg"
        """
        # 根据URL确定文件扩展名
        parsed_url = urlparse(image_url)
        ext = os.path.splitext(parsed_url.path)[1].lower()
        if not ext or ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            ext = '.jpg'  # 默认使用jpg
        
        if is_same_festival:
            # 使用分组命名：所有图片都使用 基准序号-序号 格式
            if self.current_festival_base_index == 0:
                # 如果是第一次使用分组命名，先获取基准序号
                self.current_image_index += 1
                self.current_festival_base_index = self.current_image_index
                self.current_festival_image_count = 0
            
            # 递增子序号（从1开始）
            self.current_festival_image_count += 1
            return f"{self.current_festival_base_index}-{self.current_festival_image_count}{ext}"
        else:
            # 单张图片，使用普通序号格式
            self.current_image_index += 1
            self.current_festival_base_index = 0  # 重置基准序号
            self.current_festival_image_count = 0
        return f"{self.current_image_index}{ext}"
    
    def _is_meaningful_image(self, image_path):
        """
        检测图片是否有意义（不是空白或纯色图片）
        使用更合理的判断方式，避免误判正常图片
        返回True表示图片有意义，False表示应该过滤掉
        """
        try:
            with Image.open(image_path) as img:
                # 转换为RGB模式（如果是RGBA或其他模式）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 获取图片尺寸
                width, height = img.size
                
                # 过滤掉太小的图片（小于80x80，放宽限制）
                if width < 80 or height < 80:
                    return False
                
                # 将图片转换为numpy数组进行分析
                import numpy as np
                img_array = np.array(img)
                
                # 计算图片的亮度（灰度值）
                # 使用标准公式：0.299*R + 0.587*G + 0.114*B
                gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
                
                # 计算亮度的均值和标准差
                mean_brightness = np.mean(gray)
                std_brightness = np.std(gray)
                
                # 计算图片的方差
                variance = np.var(gray)
                
                # 计算RGB三个通道的标准差
                r_std = np.std(img_array[:, :, 0])
                g_std = np.std(img_array[:, :, 1])
                b_std = np.std(img_array[:, :, 2])
                
                # 计算图片的熵值（信息量）- 更准确的判断方式
                # 使用灰度直方图计算熵
                hist, _ = np.histogram(gray.flatten(), bins=256, range=(0, 256))
                hist = hist[hist > 0]  # 移除0值
                if len(hist) > 0:
                    prob = hist / hist.sum()
                    entropy = -np.sum(prob * np.log2(prob + 1e-10))
                else:
                    entropy = 0
                
                # 使用边缘检测来判断图片是否有内容
                # 使用Sobel算子计算边缘强度
                from scipy import ndimage
                sobel_x = ndimage.sobel(gray, axis=1)
                sobel_y = ndimage.sobel(gray, axis=0)
                edge_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
                edge_mean = np.mean(edge_magnitude)
                
                # 综合判断：使用多个指标，只有同时满足多个条件才过滤
                # 1. 极端情况：几乎全白或全黑（非常严格的判断）
                if mean_brightness > 248 and std_brightness < 3:
                    print(f"  过滤极端空白图片（亮度: {mean_brightness:.1f}, 标准差: {std_brightness:.1f}）")
                    return False
                
                if mean_brightness < 5 and std_brightness < 3:
                    print(f"  过滤极端纯黑图片（亮度: {mean_brightness:.1f}, 标准差: {std_brightness:.1f}）")
                    return False
                
                # 2. 信息量极低：熵值小于2（说明图片几乎没有信息）
                if entropy < 2:
                    print(f"  过滤低熵图片（熵值: {entropy:.2f}）")
                    return False
                
                # 3. 边缘检测：如果边缘强度极低，说明图片几乎没有内容
                if edge_mean < 2:
                    print(f"  过滤无边缘图片（边缘强度: {edge_mean:.2f}）")
                    return False
                
                # 4. 综合判断：如果标准差、方差、RGB标准差都很低，且熵值也低，才过滤
                # 放宽阈值，避免误判
                if (std_brightness < 2 and variance < 20 and 
                    r_std < 2 and g_std < 2 and b_std < 2 and entropy < 3):
                    print(f"  过滤综合低质量图片（标准差: {std_brightness:.1f}, 方差: {variance:.1f}, 熵: {entropy:.2f}）")
                    return False
                
                # 其他情况都认为是有意义的图片
                return True
        except ImportError:
            # 如果没有scipy，使用简化判断
            try:
                import numpy as np
                img_array = np.array(img)
                gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
                mean_brightness = np.mean(gray)
                std_brightness = np.std(gray)
                variance = np.var(gray)
                
                # 只过滤极端情况
                if mean_brightness > 248 and std_brightness < 3:
                    return False
                if mean_brightness < 5 and std_brightness < 3:
                    return False
                if std_brightness < 2 and variance < 20:
                    return False
                return True
            except:
                return True
        except Exception as e:
            print(f"  图片质量检测失败: {e}")
            # 如果检测失败，默认保留图片（避免误删）
            return True
    
    def _download_image(self, image_url, file_name):
        """下载图片并保存"""
        try:
            response = self.session.get(image_url, timeout=10, stream=True)
            response.raise_for_status()
            
            file_path = os.path.join(CRAWLED_IMAGES_DIR, file_name)
            
            # 保存图片
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 检测图片是否有意义
            if not self._is_meaningful_image(file_path):
                # 如果图片无意义，删除文件
                try:
                    os.remove(file_path)
                    print(f"  已删除无意义图片: {file_name}")
                except:
                    pass
                # 检查该资源是否还有其他图片，如果没有，使用default图片
                # 这里需要检查当前资源（通过current_festival_name）是否还有其他图片
                # 由于我们在保存图片时才检查，这里先返回None，在保存时再处理
                return None, None
            
            # 获取图片尺寸
            try:
                with Image.open(file_path) as img:
                    dimensions = f"{img.width}x{img.height}"
            except:
                dimensions = None
            
            return file_path, dimensions
        except Exception as e:
            print(f"下载图片失败 {image_url}: {e}")
            return None, None
    
    def _clean_tags(self, tags):
        """
        清洗标签，移除无关信息
        - 移除纯数字标签（如URL路径中的ID）
        - 移除空字符串
        - 保留有意义的标签
        """
        if not tags:
            return []
        
        cleaned_tags = []
        for tag in tags:
            if not tag or not isinstance(tag, str):
                continue
            tag = tag.strip()
            # 跳过空字符串
            if not tag:
                continue
            # 跳过纯数字（通常是URL路径中的ID，如"674771"、"682393"等）
            if tag.isdigit():
                continue
            # 跳过太短的标签（少于2个字符）
            if len(tag) < 2:
                continue
            cleaned_tags.append(tag)
        
        return cleaned_tags
    
    def _get_default_image_info(self):
        """获取default.jpg的信息（尺寸等）"""
        default_image_path = os.path.join(BASE_DIR, "FrontEnd", "public", "default.jpg")
        dimensions = "200x200"  # 默认尺寸
        
        if os.path.exists(default_image_path):
            try:
                with Image.open(default_image_path) as img:
                    dimensions = f"{img.width}x{img.height}"
            except:
                pass
        
        return dimensions
    
    def _save_default_image(self, resource_id, entity_id, festival_name):
        """为只有文字没有图片的资源保存default.jpg记录"""
        if self.image_items_count >= self.max_image_items:
            return False
        
        try:
            # 获取default.jpg的尺寸信息
            dimensions = self._get_default_image_info()
            
            # 使用default.jpg作为文件名和存储路径
            file_name = "default.jpg"
            storage_path = "FrontEnd/public/default.jpg"
            
            # 使用空标签或从resource中提取的标签
            tags_json = None
            if festival_name:
                tags_json = json.dumps([festival_name], ensure_ascii=False)
            
            self.db_cursor.execute("""
                INSERT INTO crawled_images 
                (file_name, storage_path, dimensions, tags, crawl_time, resource_id, entity_id, festival_name)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s)
            """, (file_name, storage_path, dimensions, tags_json, resource_id, entity_id, festival_name))
            
            self.db_conn.commit()
            self.image_items_count += 1
            print(f"已保存默认图片记录: default.jpg (resource_id: {resource_id}, entity_id: {entity_id}, festival_name: {festival_name or '未知'})")
            return True
        except Exception as e:
            print(f"保存默认图片记录失败: {e}")
            self.db_conn.rollback()
            return False
    
    def _save_to_database(self, file_name, storage_path, dimensions, tags=None, resource_id=None, entity_id=None, festival_name=None):
        """
        保存图片信息到数据库，并关联到对应的文字资源
        """
        # 检查是否达到图片数量限制
        if self.image_items_count >= self.max_image_items:
            return False
        
        try:
            # 清洗tags
            cleaned_tags = self._clean_tags(tags) if tags else []
            tags_json = json.dumps(cleaned_tags, ensure_ascii=False) if cleaned_tags else None
            
            self.db_cursor.execute("""
                INSERT INTO crawled_images 
                (file_name, storage_path, dimensions, tags, crawl_time, resource_id, entity_id, festival_name)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s)
            """, (file_name, storage_path, dimensions, tags_json, resource_id, entity_id, festival_name))
            
            self.db_conn.commit()
            self.image_items_count += 1
            return True
        except Exception as e:
            print(f"保存到数据库失败: {e}")
            self.db_conn.rollback()
            return False
    
    def _extract_festival_names(self, text):
        """从文本中提取节日名称"""
        # 常见的节日关键词模式
        festival_patterns = [
            r'([\u4e00-\u9fa5]{2,10}节)',  # 如：春节、中秋节
            r'([\u4e00-\u9fa5]{2,10}日)',  # 如：端午节、重阳日
            r'([\u4e00-\u9fa5]{2,10}节庆)',  # 如：春节庆
            r'([\u4e00-\u9fa5]{2,10}习俗)',  # 如：春节习俗
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
    
    def _clean_entity_name(self, entity_name):
        """
        清洗实体名称，移除无关信息
        处理如"民族节日资讯"这样的标题，移除可能包含的分页信息
        """
        if not entity_name:
            return entity_name
        
        # 移除分页信息（包括逗号分隔的格式）
        entity_name = re.sub(r'上一页\s*下一页', '', entity_name)
        entity_name = re.sub(r'总记录数:\d+', '', entity_name)
        entity_name = re.sub(r'每页显示\d+条记录', '', entity_name)
        entity_name = re.sub(r'当前页:\s*\d+\s*/\s*\d+', '', entity_name)
        entity_name = re.sub(r'跳转至', '', entity_name)
        entity_name = re.sub(r'首页', '', entity_name)
        
        # 移除日期格式（如"中元节2019-08-14"、"2024-04-25"等）
        entity_name = re.sub(r'\d{4}-\d{2}-\d{2}', '', entity_name)
        
        # 移除节日名称列表项（如"欢歌"春社节"2024-04-25"、"毛南族分龙节2023-02-07"等）
        # 这些通常是列表项，不是实体名称的一部分
        lines = entity_name.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 跳过纯节日名称+日期的行（这些是列表项）
            if re.match(r'^([\u4e00-\u9fa5""]+节?)(?:\d{4}-\d{2}-\d{2})?$', line):
                continue
            cleaned_lines.append(line)
        entity_name = '\n'.join(cleaned_lines)
        
        # 移除多余空白
        entity_name = re.sub(r'\s+', ' ', entity_name)
        
        return entity_name.strip()
    
    def _clean_text_content(self, text):
        """
        清洗文本内容，移除无关信息
        - 移除分页信息（如"上一页 下一页 总记录数"等）
        - 移除重复内容
        - 移除导航链接文本
        - 保留核心文化内容
        """
        if not text:
            return text
        
        # 移除分页信息
        text = re.sub(r'上一页\s*下一页', '', text)
        text = re.sub(r'总记录数:\d+', '', text)
        text = re.sub(r'每页显示\d+条记录', '', text)
        text = re.sub(r'当前页:\s*\d+\s*/\s*\d+', '', text)
        text = re.sub(r'跳转至', '', text)
        text = re.sub(r'首页', '', text)
        
        # 移除日期格式的重复内容（如"中元节2019-08-14"、"欢歌"春社节"2024-04-25"这种格式）
        text = re.sub(r'([\u4e00-\u9fa5""]+)\d{4}-\d{2}-\d{2}', r'\1', text)
        
        # 移除重复的节日名称行（如果连续出现多次相同的节日名称+日期）
        lines = text.split('\n')
        seen_festivals = set()
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是重复的节日名称行（格式：节日名称+日期 或 纯节日名称）
            # 匹配模式：如"中元节2019-08-14"、"毛南族分龙节2023-02-07"、"欢歌"春社节"2024-04-25"
            festival_match = re.match(r'^([\u4e00-\u9fa5""]+节?)(?:\d{4}-\d{2}-\d{2})?$', line)
            if festival_match:
                festival_name = festival_match.group(1).strip('"').strip("'")
                if festival_name in seen_festivals:
                    continue  # 跳过重复的节日名称
                seen_festivals.add(festival_name)
                continue  # 跳过纯节日名称行（这些是列表项，不是描述内容）
            
            # 保留有实际内容的行
            if len(line) > 10:  # 至少10个字符才保留
                cleaned_lines.append(line)
        
        text = '\n'.join(cleaned_lines)
        
        # 移除HTML标签残留
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除多余空白和换行
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        
        # 移除开头和结尾的空白
        text = text.strip()
        
        return text
    
    def _save_text_to_database(self, resource_title, content_text, source_url, tags=None):
        """
        保存文字数据到cultural_resources和cultural_entities表
        resource_title: 文化资源名称（页面标题）
        content_text: 文本内容
        返回: (resource_id, entity_id, festival_name) 或 None
        """
        # 检查是否达到文字数量限制
        if self.text_items_count >= self.max_text_items:
            return None
        
        if not resource_title or not content_text:
            return None
        
        try:
            # 清洗文本内容
            cleaned_text = self._clean_text_content(content_text)
            
            # 如果清洗后内容太短，跳过
            if len(cleaned_text) < 100:
                print(f"  文本内容太短（清洗后: {len(cleaned_text)}字符），跳过保存")
                return None
            
            # 从文本中提取节日名称（中文）
            festival_names = self._extract_festival_names(cleaned_text)
            # 如果没有提取到节日名称，尝试从标题中提取
            if not festival_names:
                festival_names = self._extract_festival_names(resource_title)
            # 转换为英文节日名称
            chinese_festival_name = festival_names[0] if festival_names else "传统节日"
            festival_title_en = chinese_to_english_festival(chinese_festival_name)
            
            # 清洗tags（移除URL路径中的数字ID等无关信息）
            cleaned_tags = self._clean_tags(tags) if tags else []
            
            # 构建content_feature_data（使用清洗后的文本）
            meta = {
                "tags": cleaned_tags,
                "source_url": source_url,
                "festival_names": festival_names,
                "festival_name_en": festival_title_en
            }
            content_feature_data = json.dumps({
                "title": resource_title,
                "text": cleaned_text,  # 使用清洗后的文本
                "meta": meta
            }, ensure_ascii=False)
            
            # 1. 保存到cultural_resources表（title字段存储英文节日名称）
            self.db_cursor.execute("""
                INSERT INTO cultural_resources 
                (title, resource_type, file_format, source_from, source_url, 
                 content_feature_data, version, created_at, updated_at, upload_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, 1, NOW(), NOW(), %s)
            """, (
                festival_title_en,  # title字段存储英文节日名称
                "文本",
                "HTML",
                "中国民族文化资源库",
                source_url,
                content_feature_data,
                self.system_user_id  # 使用系统用户ID
            ))
            
            resource_id = self.db_cursor.lastrowid
            
            # 2. 保存到cultural_entities表（entity_name字段存储文化资源名称，description存储详细文化信息）
            # 实体类型默认为"其他"（因为文化资源本身不属于人物、作品、事件、地点）
            # 清洗entity_name（移除分页信息等）
            cleaned_entity_name = self._clean_entity_name(resource_title)
            
            self.db_cursor.execute("""
                INSERT INTO cultural_entities
                (entity_name, entity_type, description, source, cultural_region)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                cleaned_entity_name,  # entity_name字段存储清洗后的文化资源名称
                "其他",  # entity_type使用枚举值：人物、作品、事件、地点、其他
                cleaned_text,  # description存储清洗后的文本内容（详细文化信息）
                source_url,
                None  # 文化区域暂时为空
            ))
            
            entity_id = self.db_cursor.lastrowid
            
            self.db_conn.commit()
            self.text_items_count += 1
            
            # 返回resource_id, entity_id, festival_name用于关联图片
            return (resource_id, entity_id, chinese_festival_name)
        except Exception as e:
            print(f"保存文字数据到数据库失败: {e}")
            self.db_conn.rollback()
            return None
    
    def _is_cultural_image(self, img_tag, img_url):
        """
        判断图片是否与文化资源相关
        过滤掉logo、icon、banner、cover、二维码等无关图片
        """
        # 获取图片的alt、title、class等属性
        alt = (img_tag.get('alt', '') or '').lower()
        title = (img_tag.get('title', '') or '').lower()
        img_class = (img_tag.get('class', []) or [])
        if isinstance(img_class, list):
            img_class = ' '.join(img_class).lower()
        else:
            img_class = str(img_class).lower()
        
        # 获取图片URL的小写形式用于检查
        img_url_lower = img_url.lower()
        
        # 需要过滤的关键词
        filter_keywords = [
            'logo', 'icon', 'banner', 'cover', 'header', 'footer', 'nav',
            'qrcode', 'qr-code', '二维码', 'qr', 'code',
            'ad', 'advertisement', '广告', 'promotion', '推广',
            'button', 'btn', 'arrow', 'arrow', 'back', 'next', 'prev',
            'avatar', '头像', 'user', 'member',
            'thumb', 'thumbnail', 'small', 'tiny',
            'loading', 'spinner', 'placeholder', 'empty'
        ]
        
        # 检查是否包含过滤关键词
        check_text = f"{alt} {title} {img_class} {img_url_lower}"
        for keyword in filter_keywords:
            if keyword in check_text:
                return False
        
        # 检查图片尺寸（通过URL中的尺寸参数或文件名）
        # 过滤掉明显是图标的小图片（通常小于100x100）
        size_patterns = [
            r'(\d+)x(\d+)',  # 如 50x50
            r'[_-](\d+)[xX](\d+)',  # 如 _50x50
        ]
        for pattern in size_patterns:
            match = re.search(pattern, img_url_lower)
            if match:
                width, height = int(match.group(1)), int(match.group(2))
                # 如果图片尺寸小于100x100，可能是图标，过滤掉
                if width < 100 or height < 100:
                    return False
        
        # 检查图片是否在内容区域（优先选择内容区域的图片）
        # 查找父元素，看是否在header、footer、nav、sidebar等区域
        parent = img_tag.parent
        depth = 0
        while parent and depth < 5:  # 最多向上查找5层
            parent_class = (parent.get('class', []) or [])
            if isinstance(parent_class, list):
                parent_class = ' '.join(parent_class).lower()
            else:
                parent_class = str(parent_class).lower()
            parent_id = (parent.get('id', '') or '').lower()
            
            # 如果在header、footer、nav、sidebar等区域，过滤掉
            if any(keyword in f"{parent_class} {parent_id}" for keyword in ['header', 'footer', 'nav', 'sidebar', 'menu', 'toolbar']):
                return False
            
            parent = parent.parent
            depth += 1
        
        return True
    
    def _extract_images_from_page(self, html_content, page_url):
        """从页面中提取图片URL（只提取与文化资源相关的图片）"""
        soup = BeautifulSoup(html_content, 'html.parser')
        images = []
        
        # 优先查找内容区域的图片
        content_areas = soup.find_all(['article', 'div'], class_=re.compile(r'content|article|main|detail|text', re.I))
        if not content_areas:
            # 如果没有找到内容区域，查找所有img标签
            content_areas = [soup]
        
        for area in content_areas:
            # 查找所有img标签
            for img in area.find_all('img'):
                src = img.get('src') or img.get('data-src') or img.get('data-original')
                if not src:
                    continue
                
                # 转换为绝对URL
                absolute_url = urljoin(page_url, src)
                
                # 过滤掉无效的图片URL
                if not any(domain in absolute_url for domain in ALLOWED_DOMAINS):
                    continue
                
                # 过滤掉非文化资源相关的图片
                if not self._is_cultural_image(img, absolute_url):
                    continue
                
                images.append({
                    'url': absolute_url,
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
                
                # 如果已经达到图片数量限制，停止提取
                if len(images) >= 10:  # 每个页面最多提取10张图片
                    break
            
            if len(images) >= 10:
                break
        
        return images
    
    def _extract_text_content(self, html_content):
        """提取页面文本内容（只提取主要内容，过滤导航、页脚等）"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 移除不需要的元素
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "sidebar"]):
            element.decompose()
        
        # 移除常见的导航和无关内容
        unwanted_classes = ['nav', 'navigation', 'menu', 'header', 'footer', 'sidebar', 
                           'breadcrumb', 'breadcrumbs', 'notice', 'warning', 'ad', 'advertisement',
                           'comment', 'comments', 'related', 'recommend', 'hot', 'top']
        for class_name in unwanted_classes:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                element.decompose()
        
        # 移除id包含导航、页脚等关键词的元素
        unwanted_ids = ['nav', 'navigation', 'header', 'footer', 'sidebar', 'menu', 'top']
        for id_name in unwanted_ids:
            for element in soup.find_all(id=re.compile(id_name, re.I)):
                element.decompose()
        
        # 优先查找主要内容区域
        content_areas = []
        
        # 尝试查找常见的内容区域
        content_selectors = [
            ('article', {}),
            ('div', {'class': re.compile(r'content|article|main|detail|text|body', re.I)}),
            ('div', {'id': re.compile(r'content|article|main|detail|text|body', re.I)}),
            ('main', {}),
            ('section', {'class': re.compile(r'content|article|main', re.I)}),
        ]
        
        for tag, attrs in content_selectors:
            elements = soup.find_all(tag, attrs)
            if elements:
                content_areas.extend(elements)
                break
        
        # 如果找到内容区域，只提取这些区域的文本
        if content_areas:
            text_parts = []
            for area in content_areas:
                # 移除内容区域内的导航、引用等
                for unwanted in area.find_all(['nav', 'aside', 'div'], class_=re.compile(r'nav|menu|related|recommend|hot', re.I)):
                    unwanted.decompose()
                text = area.get_text()
                if text and len(text.strip()) > 50:  # 只保留有意义的文本
                    text_parts.append(text.strip())
            
            if text_parts:
                # 合并文本并清理
                text = ' '.join(text_parts)
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk and len(chunk) > 2)
                return text
        
        # 如果没有找到明确的内容区域，尝试从body中提取，但排除导航等
        body = soup.find('body')
        if body:
            # 移除body中的导航、页脚等
            for unwanted in body.find_all(['nav', 'header', 'footer', 'aside', 'div'], 
                                         class_=re.compile(r'nav|menu|header|footer|sidebar|breadcrumb', re.I)):
                unwanted.decompose()
            text = body.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk and len(chunk) > 2)
            return text
        
        # 最后降级方案：提取所有文本但过滤短行
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # 过滤掉太短的内容（可能是导航项、按钮文字等）
        text = ' '.join(chunk for chunk in chunks if chunk and len(chunk) > 5)
        return text
    
    def _extract_tags(self, html_content, page_url):
        """从页面内容中提取标签"""
        soup = BeautifulSoup(html_content, 'html.parser')
        tags = []
        
        # 提取标题作为标签
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text().strip()
            # 提取关键词
            keywords = re.findall(r'[\u4e00-\u9fa5]+', title_text)
            tags.extend(keywords[:3])  # 最多3个关键词
        
        # 从URL路径中提取标签
        path_parts = urlparse(page_url).path.split('/')
        for part in path_parts:
            if part and part not in ['index.html', '']:
                tags.append(part)
        
        return list(set(tags))[:5]  # 去重并限制最多5个标签
    
    def crawl_page(self, url):
        """爬取单个页面"""
        if url in self.visited_urls:
            return []
        
        # 检查是否达到数量限制
        if self.text_items_count >= self.max_text_items and self.image_items_count >= self.max_image_items:
            print(f"已达到数量限制（文字: {self.text_items_count}/{self.max_text_items}, 图片: {self.image_items_count}/{self.max_image_items}），停止爬取")
            return []
        
        self.visited_urls.add(url)
        print(f"正在爬取: {url}")
        
        # 添加重试机制
        max_retries = 3
        retry_delay = 2  # 秒
        html_content = None
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=15, allow_redirects=True)
                response.raise_for_status()
                response.encoding = 'utf-8'
                html_content = response.text
                break  # 成功获取，退出重试循环
            except requests.exceptions.SSLError as e:
                print(f"  SSL错误（尝试 {attempt + 1}/{max_retries}）: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    # 尝试禁用SSL验证（仅作为最后手段）
                    if attempt == max_retries - 2:
                        import urllib3
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                        self.session.verify = False
                else:
                    print(f"爬取页面失败 {url}: SSL连接失败，已重试{max_retries}次")
                    return []
            except requests.exceptions.RequestException as e:
                print(f"  请求错误（尝试 {attempt + 1}/{max_retries}）: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print(f"爬取页面失败 {url}: {e}")
                    return []
        
        if not html_content:
            print(f"爬取页面失败 {url}: 无法获取页面内容")
            return []
        
        try:
            # 提取标题和文本内容
            soup = BeautifulSoup(html_content, 'html.parser')
            title_tag = soup.find('title')
            resource_title = title_tag.get_text().strip() if title_tag else ''
            # 如果没有title标签，尝试从h1获取
            if not resource_title:
                h1_tag = soup.find('h1')
                resource_title = h1_tag.get_text().strip() if h1_tag else ''
            content_text = self._extract_text_content(html_content)
            
            # 先保存文字数据（即使没有图片也要保存，只要文本内容足够）
            # 先清洗文本内容
            cleaned_content = self._clean_text_content(content_text)
            resource_id = None
            entity_id = None
            festival_name = None
            
            if self.text_items_count < self.max_text_items and resource_title and cleaned_content and len(cleaned_content) > 50:
                tags = self._extract_tags(html_content, url)
                result = self._save_text_to_database(resource_title, cleaned_content, url, tags)
                if result:
                    resource_id, entity_id, festival_name = result
                    print(f"已保存文字数据: {resource_title[:50]}... (文字数据: {self.text_items_count}/{self.max_text_items}, resource_id: {resource_id}, entity_id: {entity_id})")
            
            # 提取图片（如果未达到限制）
            images_saved = 0  # 记录实际保存的图片数量
            if self.image_items_count < self.max_image_items:
                images = self._extract_images_from_page(html_content, url)
                
                # 确定当前节日的名称（用于关联图片）
                # 优先使用从文字数据中提取的节日名称，如果没有则从标题中提取
                current_festival = festival_name
                if not current_festival and resource_title:
                    # 从标题中提取节日名称
                    festival_names = self._extract_festival_names(resource_title)
                    if festival_names:
                        current_festival = festival_names[0]
                
                # 如果是新节日，重置计数器
                if current_festival != self.current_festival_name:
                    self.current_festival_name = current_festival
                    self.current_festival_base_index = 0  # 将在_get_next_image_name中设置
                    self.current_festival_image_count = 0
                
                # 先检查这个资源有多少张图片
                valid_images_count = 0
                for img_info in images:
                    if self.image_items_count + valid_images_count >= self.max_image_items:
                        break
                    # 简单检查URL是否有效（不下载，只计数）
                    if img_info.get('url'):
                        valid_images_count += 1
                
                # 如果有多张图片（>=2），所有图片都使用 基准序号-序号 格式
                # 如果只有一张图片，使用普通序号格式
                use_grouped_naming = valid_images_count >= 2
                
                # 下载并保存图片
                for img_info in images:
                    if self.image_items_count >= self.max_image_items:
                        break
                    
                    image_url = img_info['url']
                    # 如果有多张图片，所有图片都使用分组命名（包括第一张）
                    is_same_festival = use_grouped_naming and current_festival == self.current_festival_name
                    file_name = self._get_next_image_name(image_url, is_same_festival=is_same_festival)
                    file_path, dimensions = self._download_image(image_url, file_name)
                    
                    if file_path:
                        # 提取标签
                        tags = self._extract_tags(html_content, url)
                        if img_info.get('alt'):
                            tags.append(img_info['alt'])
                        
                        # 添加节日名称到tags中（如果存在）
                        if current_festival:
                            if current_festival not in tags:
                                tags.insert(0, current_festival)  # 将节日名称放在最前面
                        
                        # 保存到数据库，关联resource_id和entity_id
                        storage_path = f"crawled_images/{file_name}"
                        if self._save_to_database(file_name, storage_path, dimensions, tags, resource_id, entity_id, current_festival):
                            images_saved += 1
                            print(f"已保存图片: {file_name} (节日: {current_festival or '未知'}, 图片数据: {self.image_items_count}/{self.max_image_items}, resource_id: {resource_id}, entity_id: {entity_id})")
            
            # 如果保存了文字数据但没有保存任何图片，插入一条default.jpg记录
            if resource_id and entity_id and images_saved == 0:
                self._save_default_image(resource_id, entity_id, festival_name)
            
            # 提取链接，继续爬取（如果未达到限制）
            links = []
            if self.text_items_count < self.max_text_items or self.image_items_count < self.max_image_items:
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    absolute_url = urljoin(url, href)
                    
                    # 只爬取相关域名的链接
                    if any(domain in absolute_url for domain in ALLOWED_DOMAINS):
                        if '/mzwhzyk/674771/682393/' in absolute_url:
                            links.append(absolute_url)
            
            return links
            
        except Exception as e:
            print(f"爬取页面失败 {url}: {e}")
            return []
    
    def run(self, max_pages=500):
        """运行爬虫"""
        print("开始爬取中国民族文化资源库...")
        print(f"数量限制：文字数据 {self.max_text_items} 条，图片数据 {self.max_image_items} 条")
        
        queue = list(START_URLS)
        pages_crawled = 0
        
        while queue and pages_crawled < max_pages:
            # 检查是否达到数量限制
            if self.text_items_count >= self.max_text_items and self.image_items_count >= self.max_image_items:
                print(f"已达到数量限制，停止爬取")
                break
            
            url = queue.pop(0)
            links = self.crawl_page(url)
            
            if links:
                for link in links:
                    if link not in self.visited_urls and link not in queue:
                        queue.append(link)
            
            pages_crawled += 1
            time.sleep(1)  # 延迟1秒，避免请求过快
        
        print(f"爬取完成，共爬取 {pages_crawled} 个页面")
        print(f"文字数据: {self.text_items_count}/{self.max_text_items} 条")
        print(f"图片数据: {self.image_items_count}/{self.max_image_items} 条")
    
    def close(self):
        """关闭数据库连接"""
        if self.db_cursor:
            self.db_cursor.close()
        if self.db_conn:
            self.db_conn.close()
        print("数据库连接已关闭")


if __name__ == "__main__":
    spider = MinzuFestivalsSpider()
    try:
        spider.run(max_pages=50)
    finally:
        spider.close()

