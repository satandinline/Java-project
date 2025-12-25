# -*- coding: utf-8 -*-
"""
维基百科爬虫
爬取汉族传统节日相关页面，提取图片并存储到crawled_images文件夹
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
import html
import sys

# 添加项目根目录到路径，以便导入db_connection
# 使用相对路径添加项目根目录到sys.path
current_file_dir = os.path.dirname(os.path.realpath(__file__))
project_root = os.path.dirname(current_file_dir)
sys.path.insert(0, project_root)
from db_connection import get_spider_db_connection, get_spider_db_config
from festival_name_utils import chinese_to_english_festival, extract_and_convert_festival_name

# 爬虫配置
# 使用相对路径获取项目根目录
current_file_dir = os.path.dirname(os.path.realpath(__file__))
BASE_DIR = os.path.dirname(current_file_dir)
CRAWLED_IMAGES_DIR = os.path.join(BASE_DIR, "crawled_images")
BASE_URL = "https://zh.wikipedia.org"
START_URL = "https://zh.wikipedia.org/wiki/%E6%BC%A2%E6%97%8F%E5%82%B3%E7%B5%B1%E7%AF%80%E6%97%A5"

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9"
}


class WikipediaSpider:
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
        
        # 时间限制（30分钟）
        self.max_duration = 30 * 60  # 最大爬取时间（秒）：30分钟
        self.start_time = None  # 爬取开始时间
        self.resources_count = 0  # 已爬取的资源数量（用于统计）
        
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
            # 检查是否存在系统用户（account='99999999'或id=1）
            self.db_cursor.execute("SELECT id FROM users WHERE account = '99999999' OR id = 1 LIMIT 1")
            user = self.db_cursor.fetchone()
            
            if user:
                self.system_user_id = user[0]
                print(f"使用系统用户ID: {self.system_user_id}")
            else:
                # 创建系统用户
                import hashlib
                # 使用一个固定的密码哈希（实际不会用于登录）
                password_hash = hashlib.sha256("system_user_password".encode()).hexdigest()
                # 生成系统用户账号（固定为'99999999'，8位数字）
                system_account = '99999999'
                
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
        采用保守策略：只过滤明显无意义的图片（几乎全白、全黑、极小尺寸）
        其他情况默认保留，避免误删正常图片
        返回True表示图片有意义，False表示应该过滤掉
        """
        try:
            with Image.open(image_path) as img:
                # 转换为RGB模式（如果是RGBA或其他模式）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 获取图片尺寸
                width, height = img.size
                
                # 1. 过滤掉太小的图片（小于50x50，这是明显无意义的尺寸）
                if width < 50 or height < 50:
                    print(f"  过滤极小图片（尺寸: {width}x{height}）")
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
                
                # 2. 只过滤极端情况：几乎全白（亮度>250且标准差极小，说明几乎没有任何变化）
                # 这个判断非常严格，只有真正是纯白或接近纯白的图片才会被过滤
                if mean_brightness > 250 and std_brightness < 1.5:
                    print(f"  过滤极端空白图片（亮度: {mean_brightness:.1f}, 标准差: {std_brightness:.1f}）")
                    return False
                
                # 3. 只过滤极端情况：几乎全黑（亮度<3且标准差极小）
                if mean_brightness < 3 and std_brightness < 1.5:
                    print(f"  过滤极端纯黑图片（亮度: {mean_brightness:.1f}, 标准差: {std_brightness:.1f}）")
                    return False
                
                # 4. 过滤单色图片：如果标准差极小（<0.5），说明图片几乎没有变化，可能是单色图
                # 但需要结合亮度判断，避免误判深色或浅色的正常图片
                if std_brightness < 0.5:
                    # 如果标准差极小，且亮度在中间范围（不是极白或极黑），可能是单色背景图
                    # 但为了保守起见，我们只过滤标准差接近0的情况
                    if std_brightness < 0.1:
                        print(f"  过滤单色图片（标准差: {std_brightness:.3f}）")
                        return False
                
                # 其他所有情况都认为是有意义的图片，包括：
                # - 颜色比较统一的图片（传统节日图片可能主色调统一，但仍有内容）
                # - 低对比度的图片（可能是艺术风格）
                # - 边缘不明显的图片（可能是柔和的图片）
                # - 熵值较低的图片（可能是简洁的设计，但仍有意义）
                return True
                
        except ImportError:
            # 如果没有numpy，使用最基本的判断
            try:
                # 重新打开图片获取尺寸（因为img可能在with块外不可用）
                with Image.open(image_path) as img:
                    width, height = img.size
                    if width < 50 or height < 50:
                        return False
                    # 没有numpy时，默认保留所有图片
                    return True
            except:
                # 如果连打开图片都失败，默认保留（避免误删）
                return True
        except Exception as e:
            print(f"  图片质量检测失败: {e}")
            # 如果检测失败，默认保留图片（避免误删）
            return True
    
    def _download_image(self, image_url, file_name):
        """下载图片并保存"""
        try:
            # 过滤掉维基百科的特殊URL（如CentralAutoLogin等）
            if 'special:' in image_url.lower() or 'centralautologin' in image_url.lower():
                print(f"  跳过维基百科特殊URL: {image_url[:80]}...")
                return None, None
            
            # 处理维基百科的图片URL（可能需要转换为直接访问URL）
            if 'upload.wikimedia.org' in image_url or image_url.startswith('//'):
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                # 对于缩略图，尝试获取原图
                if '/thumb/' in image_url:
                    # 提取原图URL：/thumb/文件名/尺寸-文件名 -> /文件名
                    parts = image_url.split('/thumb/')
                    if len(parts) == 2:
                        thumb_path = parts[1]
                        # 移除尺寸前缀（如 220px-）
                        thumb_path = re.sub(r'^\d+px-', '', thumb_path)
                        # 提取文件名（最后一个/之后的部分）
                        filename = thumb_path.split('/')[-1]
                        # 构建原图URL
                        image_url = parts[0] + '/' + filename
                    else:
                        # 如果解析失败，使用原始逻辑
                        image_url = image_url.split('/thumb/')[0] + '/' + '/'.join(image_url.split('/thumb/')[1].split('/')[1:])
            
            # 增加超时时间和重试机制
            max_retries = 3
            base_retry_delay = 2
            response = None
            
            for attempt in range(max_retries):
                try:
                    # 增加超时时间到40秒，并添加连接超时
                    response = self.session.get(
                        image_url, 
                        timeout=(10, 40),  # (连接超时, 读取超时)
                        stream=True,
                        allow_redirects=True
                    )
                    response.raise_for_status()
                    break
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        retry_delay = base_retry_delay * (attempt + 1)  # 递增延迟：2秒、4秒、6秒
                        print(f"  图片下载超时（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                    else:
                        print(f"  图片下载超时，已重试{max_retries}次，放弃下载")
                        return None, None
                except requests.exceptions.HTTPError as e:
                    # 针对服务器错误（502, 503, 504等）使用更长的延迟
                    status_code = e.response.status_code if e.response else None
                    if status_code in [502, 503, 504, 429]:
                        if attempt < max_retries - 1:
                            # 服务器错误使用更长的延迟：5秒、10秒、15秒
                            retry_delay = 5 * (attempt + 1)
                            print(f"  服务器错误 {status_code}（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                        else:
                            print(f"  服务器错误 {status_code}，已重试{max_retries}次，放弃下载")
                            return None, None
                    else:
                        # 其他HTTP错误（如404）直接放弃
                        print(f"  HTTP错误 {status_code}，放弃下载")
                        return None, None
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        retry_delay = base_retry_delay * (attempt + 1)
                        print(f"  图片下载失败（尝试 {attempt + 1}/{max_retries}）: {str(e)[:100]}，{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                    else:
                        print(f"  图片下载失败，已重试{max_retries}次: {str(e)[:100]}")
                        return None, None
                except Exception as e:
                    if attempt < max_retries - 1:
                        retry_delay = base_retry_delay * (attempt + 1)
                        print(f"  未知错误（尝试 {attempt + 1}/{max_retries}）: {str(e)[:100]}，{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                    else:
                        raise
            
            if not response:
                return None, None
            
            file_path = os.path.join(CRAWLED_IMAGES_DIR, file_name)
            
            # 保存图片
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 检测图片是否有意义
            if not self._is_meaningful_image(file_path):
                # 如果图片无意义，删除文件并返回None
                try:
                    os.remove(file_path)
                    print(f"  已删除无意义图片: {file_name}")
                except:
                    pass
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
            # 跳过纯数字（通常是URL路径中的ID）
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
        """
        if not entity_name:
            return entity_name
        
        # 移除引用标记
        entity_name = re.sub(r'\[\d+\]', '', entity_name)
        
        # 移除多余空白
        entity_name = re.sub(r'\s+', ' ', entity_name)
        
        return entity_name.strip()
    
    def _clean_text_content(self, text):
        """
        清洗文本内容，移除无关信息
        - 移除维基百科特有的导航和分类信息
        - 移除引用标记（如[1]、[2]等）
        - 移除编辑链接标记
        - 保留核心文化内容
        """
        if not text:
            return text
        
        # 移除引用标记（如[1]、[2]等，包括[注 1]这种格式）
        text = re.sub(r'\[.*?\]', '', text)
        
        # 移除编辑链接标记（如[编辑]等）
        text = re.sub(r'\[编辑\]', '', text)
        
        # 移除维基百科分类信息（通常在文末）
        text = re.sub(r'分类：.*$', '', text, flags=re.MULTILINE)
        
        # 移除多余空白和换行
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        
        return text.strip()
    
    def _save_text_to_database(self, resource_title, content_text, source_url, tags=None):
        """
        保存文字数据到cultural_resources和cultural_entities表
        resource_title: 文化资源名称（页面标题）
        content_text: 文本内容
        返回: (resource_id, entity_id, festival_name) 或 None
        """
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
            
            # 清洗tags
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
                "维基百科",
                source_url,
                content_feature_data,
                self.system_user_id  # 使用系统用户ID
            ))
            
            resource_id = self.db_cursor.lastrowid
            
            # 2. 保存到cultural_entities表（entity_name字段存储文化资源名称，description存储详细文化信息）
            # 实体类型默认为"其他"（因为文化资源本身不属于人物、作品、事件、地点）
            # 清洗entity_name
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
            
            # 返回resource_id, entity_id, festival_name用于关联图片
            return (resource_id, entity_id, chinese_festival_name)
        except Exception as e:
            print(f"保存文字数据到数据库失败: {e}")
            self.db_conn.rollback()
            return None
    
    def _extract_festival_links(self, html_content):
        """从列表页面提取节日链接"""
        festival_links = []
        
        try:
            # 查找"一般民俗节日"部分的表格
            if '<h2 id="一般民俗節日">' in html_content or '<h2 id="一般民俗节日">' in html_content:
                # 提取表格中的链接
                pattern = r'<td>.*?</td>\s*<td><a href="(/wiki/[^"]+)"'
                matches = re.findall(pattern, html_content, re.S)
                for match in matches:
                    full_url = urljoin(BASE_URL, match)
                    if full_url not in festival_links:
                        festival_links.append(full_url)
        except Exception as e:
            print(f"提取节日链接失败: {e}")
        
        return festival_links
    
    def _is_cultural_image(self, img_tag, img_url):
        """
        判断图片是否与文化资源相关
        过滤掉logo、icon、banner、cover、二维码等无关图片
        特别注意：过滤掉维基百科的特殊URL（如CentralAutoLogin等）
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
        
        # 1. 过滤掉维基百科的特殊URL（如CentralAutoLogin、Special等）
        if 'special:' in img_url_lower or 'centralautologin' in img_url_lower:
            return False
        
        # 2. 过滤掉明显无意义的URL路径
        if '/thumb/' in img_url_lower and ('1px' in img_url_lower or '2px' in img_url_lower or '3px' in img_url_lower):
            return False
        
        # 3. 需要过滤的关键词
        filter_keywords = [
            'logo', 'icon', 'banner', 'cover', 'header', 'footer', 'nav',
            'qrcode', 'qr-code', '二维码', 'qr', 'code',
            'ad', 'advertisement', '广告', 'promotion', '推广',
            'button', 'btn', 'arrow', 'back', 'next', 'prev',
            'avatar', '头像', 'user', 'member',
            'loading', 'spinner', 'placeholder', 'empty',
            'stub', 'disambig',  # 维基百科的占位图和消歧义图
            'wikimedia-button', 'wikimedia-logo', 'wikimedia-commons'
        ]
        
        # 检查是否包含过滤关键词
        check_text = f"{alt} {title} {img_class} {img_url_lower}"
        for keyword in filter_keywords:
            if keyword in check_text:
                return False
        
        # 4. 检查图片尺寸（通过URL中的尺寸参数）
        # 维基百科的缩略图通常包含尺寸信息，如 /thumb/.../220px-...
        size_match = re.search(r'(\d+)px', img_url_lower)
        if size_match:
            size = int(size_match.group(1))
            # 如果图片尺寸小于200px，可能是图标，过滤掉（提高阈值）
            if size < 200:
                return False
        
        # 5. 检查图片的width和height属性（如果存在）
        width = img_tag.get('width')
        height = img_tag.get('height')
        if width and height:
            try:
                width_val = int(str(width).replace('px', ''))
                height_val = int(str(height).replace('px', ''))
                # 如果图片尺寸小于200x200，过滤掉
                if width_val < 200 or height_val < 200:
                    return False
            except:
                pass
        
        return True
    
    def _extract_image_from_festival_page(self, html_content, page_url):
        """从节日页面提取图片（只提取与文化资源相关的图片）"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 收集所有候选图片
        candidate_images = []
        
        # 1. 优先从信息框（infobox）中提取图片
        infobox = soup.find('table', class_=re.compile('infobox'))
        if infobox:
            img_tag = infobox.find('img')
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(BASE_URL, src)
                    
                    # 检查是否是文化资源相关的图片
                    if self._is_cultural_image(img_tag, src):
                        # 获取图片尺寸信息（用于排序）
                        width = img_tag.get('width')
                        height = img_tag.get('height')
                        size_score = 0
                        if width and height:
                            try:
                                width_val = int(str(width).replace('px', ''))
                                height_val = int(str(height).replace('px', ''))
                                size_score = width_val * height_val
                            except:
                                pass
                        
                        candidate_images.append({
                            'url': src,
                            'alt': img_tag.get('alt', ''),
                            'title': img_tag.get('title', ''),
                            'size_score': size_score,
                            'source': 'infobox'
                        })
        
        # 2. 从内容区域提取图片
        content_area = soup.find('div', id='mw-content-text')
        if content_area:
            for img_tag in content_area.find_all('img'):
                src = img_tag.get('src') or img_tag.get('data-src')
                if not src:
                    continue
                
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(BASE_URL, src)
                
                # 检查是否是文化资源相关的图片
                if self._is_cultural_image(img_tag, src):
                    # 获取图片尺寸信息（用于排序）
                    width = img_tag.get('width')
                    height = img_tag.get('height')
                    size_score = 0
                    if width and height:
                        try:
                            width_val = int(str(width).replace('px', ''))
                            height_val = int(str(height).replace('px', ''))
                            size_score = width_val * height_val
                        except:
                            pass
                    
                    candidate_images.append({
                        'url': src,
                        'alt': img_tag.get('alt', ''),
                        'title': img_tag.get('title', ''),
                        'size_score': size_score,
                        'source': 'content'
                    })
        
        # 3. 选择最佳图片（优先选择infobox中的，其次选择尺寸最大的）
        if candidate_images:
            # 优先选择infobox中的图片
            infobox_images = [img for img in candidate_images if img['source'] == 'infobox']
            if infobox_images:
                # 选择尺寸最大的
                best_image = max(infobox_images, key=lambda x: x['size_score'])
                return {
                    'url': best_image['url'],
                    'alt': best_image['alt'],
                    'title': best_image['title']
                }
            else:
                # 如果没有infobox图片，选择尺寸最大的内容图片
                best_image = max(candidate_images, key=lambda x: x['size_score'])
                return {
                    'url': best_image['url'],
                    'alt': best_image['alt'],
                    'title': best_image['title']
                }
        
        return None
    
    def _extract_title(self, html_content):
        """提取页面标题"""
        soup = BeautifulSoup(html_content, 'html.parser')
        title_tag = soup.find('h1', id='firstHeading')
        if title_tag:
            return title_tag.get_text().strip()
        return None
    
    def _extract_description(self, html_content):
        """提取页面主要内容（过滤导航、引用框等无关内容）"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 移除不需要的元素
        for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
            element.decompose()
        
        # 移除维基百科的导航框、信息框、引用等
        unwanted_classes = ['navbox', 'infobox', 'reference', 'mw-references-wrap', 
                           'mw-jump-link', 'noprint', 'hatnote', 'dablink',
                           'vertical-navbox', 'navbox-group', 'mw-editsection']
        for class_name in unwanted_classes:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                element.decompose()
        
        # 查找主要内容区域
        content_area = soup.find('div', id='mw-content-text')
        if not content_area:
            return None
        
        # 移除内容区域内的导航框、信息框等
        for unwanted in content_area.find_all(['div', 'table', 'nav'], 
                                             class_=re.compile(r'navbox|infobox|reference|hatnote|dablink', re.I)):
            unwanted.decompose()
        
        # 提取所有段落（不只是第一段）
        paragraphs = content_area.find_all('p')
        text_parts = []
        
        for p in paragraphs:
            # 跳过空段落和导航段落
            p_text = p.get_text().strip()
            if not p_text or len(p_text) < 20:
                continue
            
            # 跳过明显是导航或提示的段落
            if any(keyword in p_text for keyword in ['跳转到', '重定向', '参见', '相关条目', '外部链接']):
                continue
            
            # 移除引用标记 [1], [注 1] 等
            p_text = re.sub(r'\[.*?\]', '', p_text).strip()
            # 解码HTML实体
            p_text = html.unescape(p_text)
            
            if len(p_text) > 30:
                text_parts.append(p_text)
        
        # 如果提取到多个段落，合并它们（最多前5段，避免太长）
        if text_parts:
            # 限制段落数量，避免包含太多无关内容
            max_paragraphs = 5
            combined_text = ' '.join(text_parts[:max_paragraphs])
            # 限制总长度（最多5000字符）
            if len(combined_text) > 5000:
                combined_text = combined_text[:5000] + '...'
            
            # 应用数据清洗
            combined_text = self._clean_text_content(combined_text)
            
            return combined_text
        
        return None
    
    def _extract_tags(self, html_content, page_url, title):
        """提取标签"""
        tags = []
        
        # 添加标题作为标签
        if title:
            # 提取关键词
            keywords = re.findall(r'[\u4e00-\u9fa5]+', title)
            tags.extend(keywords[:3])
        
        # 添加固定标签
        tags.append('传统节日')
        tags.append('汉族')
        tags.append('维基百科')
        
        return list(set(tags))[:5]  # 去重并限制最多5个标签
    
    def crawl_festival_page(self, url):
        """爬取单个节日页面"""
        if url in self.visited_urls:
            return False
        
        # 检查是否超过时间限制
        if self.start_time and (time.time() - self.start_time) >= self.max_duration:
            print(f"已达到时间限制（30分钟），停止爬取")
            return False
        
        self.visited_urls.add(url)
        print(f"正在爬取节日页面: {url}")
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            html_content = response.text
            
            # 提取标题和描述
            resource_title = self._extract_title(html_content)
            
            # 先检查页面标题是否与传统节日相关
            if not self._is_festival_related(resource_title, url):
                print(f"  跳过无关页面（非传统节日相关）: {resource_title}")
                return False
            
            description = self._extract_description(html_content)
            
            # 检查是否超过时间限制
            if self.start_time and (time.time() - self.start_time) >= self.max_duration:
                print(f"已达到时间限制（30分钟），停止爬取")
                return False
            
            # 先保存文字数据（即使没有图片也要保存，只要文本内容足够）
            # description已经在_extract_description中经过清洗
            resource_id = None
            entity_id = None
            festival_name = None
            
            if resource_title and description and len(description) > 50:
                tags = self._extract_tags(html_content, url, resource_title)
                result = self._save_text_to_database(resource_title, description, url, tags)
                if result:
                    resource_id, entity_id, festival_name = result
                    print(f"已保存文字数据: {resource_title[:50]}... (resource_id: {resource_id}, entity_id: {entity_id})")
            
            # 提取图片（如果有文字资源，图片应该关联到该资源）
            image_saved = False  # 记录是否保存了图片
            # 确定当前节日的名称（用于关联图片）
            # 优先使用从文字数据中提取的节日名称
            current_festival = festival_name
            if not current_festival and resource_title:
                # 如果没有文字资源，从标题中提取节日名称
                from festival_name_utils import extract_and_convert_festival_name
                festival_names = extract_and_convert_festival_name(resource_title)
                if festival_names:
                    current_festival = festival_names[0]
            
            # 如果是新节日，重置计数器
            if current_festival != self.current_festival_name:
                self.current_festival_name = current_festival
                self.current_festival_base_index = 0  # 将在_get_next_image_name中设置
                self.current_festival_image_count = 0
            
            # 注意：wikipedia_spider每次只提取一张图片，所以不需要分组命名
            # 但如果将来改为提取多张，可以在这里添加计数逻辑
            img_info = self._extract_image_from_festival_page(html_content, url)
            
            if img_info and img_info['url']:
                print(f"  找到图片: {img_info['url'][:80]}...")
                # wikipedia_spider通常每次只提取一张图片，所以使用普通命名
                # 如果将来支持多张图片，可以在这里判断
                is_same_festival = False  # 单张图片，不使用分组命名
                
                # 下载图片
                file_name = self._get_next_image_name(img_info['url'], is_same_festival=is_same_festival)
                print(f"  开始下载图片: {file_name}")
                file_path, dimensions = self._download_image(img_info['url'], file_name)
                
                if file_path:
                    print(f"  图片下载成功: {file_name}, 尺寸: {dimensions}")
                    # 提取标签
                    tags = self._extract_tags(html_content, url, resource_title)
                    if img_info.get('alt'):
                        tags.append(img_info['alt'])
                    if resource_title:
                        tags.append(resource_title)
                    
                    # 添加节日名称到tags中（如果存在）
                    if current_festival:
                        if current_festival not in tags:
                            tags.insert(0, current_festival)  # 将节日名称放在最前面
                    
                    # 保存到数据库，关联resource_id和entity_id
                    storage_path = f"crawled_images/{file_name}"
                    if self._save_to_database(file_name, storage_path, dimensions, tags, resource_id, entity_id, current_festival):
                        image_saved = True
                        print(f"已保存图片: {file_name} (节日: {current_festival or '未知'}, resource_id: {resource_id}, entity_id: {entity_id})")
                else:
                    print(f"  图片下载失败或被过滤: {file_name}")
            else:
                print(f"  未找到图片")
            
            # 如果保存了文字数据但没有保存任何图片，插入一条default.jpg记录
            if resource_id and entity_id and not image_saved:
                if self._save_default_image(resource_id, entity_id, festival_name):
                    image_saved = True  # 标记为已保存（default.jpg也算保存了）
            
            # 如果成功保存了一个完整资源（文字+图片或default.jpg），增加资源计数
            if resource_id and entity_id and image_saved:
                self.resources_count += 1
                elapsed_time = int(time.time() - self.start_time) if self.start_time else 0
                title_display = resource_title[:50] if resource_title else "未知标题"
                print(f"已保存完整资源 #{self.resources_count} (已用时: {elapsed_time//60}分{elapsed_time%60}秒): {title_display}...")
                return True
            
            return False
            
        except Exception as e:
            print(f"爬取页面失败 {url}: {e}")
            return False
    
    def _is_festival_related(self, title, url=None):
        """
        判断页面是否与传统节日相关
        包括汉族传统节日和中国各少数民族的传统节日
        """
        if not title:
            return False
        
        title_lower = title.lower()
        
        # 节日相关关键词（包括汉族和少数民族节日）
        festival_keywords = [
            '节', '日', '祭', '典', '礼', '俗', '传统节日', '民俗节日',
            '春节', '元宵', '清明', '端午', '中秋', '重阳', '除夕',
            '那达慕', '泼水节', '火把节', '开斋节', '古尔邦节', '藏历',
            '雪顿节', '望果节', '赛马节', '花山节', '三月三', '六月六',
            '赶秋', '苗年', '侗年', '水族端节', '瑶族盘王节', '彝族年',
            '白族三月街', '哈尼族十月年', '傣族泼水节', '纳西族三朵节',
            '布依族六月六', '土家族赶年', '壮族三月三', '回族开斋节',
            '维吾尔族古尔邦节', '藏族雪顿节', '蒙古族那达慕'
        ]
        
        # 排除无关关键词（生物、地理、历史人物等）
        exclude_keywords = [
            '生物', '植物', '动物', '昆虫', '鸟类', '鱼类', '哺乳动物',
            '地理', '山脉', '河流', '湖泊', '城市', '国家', '地区',
            '历史人物', '皇帝', '皇帝', '朝代', '战争', '战役',
            '化学', '物理', '数学', '科学', '技术', '工程',
            '电影', '电视剧', '音乐', '歌曲', '专辑',
            '公司', '企业', '品牌', '产品', '商品'
        ]
        
        # 检查是否包含排除关键词
        for exclude_keyword in exclude_keywords:
            if exclude_keyword in title:
                return False
        
        # 检查是否包含节日关键词
        for keyword in festival_keywords:
            if keyword in title:
                return True
        
        # 如果URL中包含节日相关关键词，也认为是相关的
        if url:
            url_lower = url.lower()
            for keyword in festival_keywords:
                if keyword in url_lower:
                    return True
        
        return False
    
    def _extract_related_links(self, html_content, current_url):
        """从节日页面提取相关链接（继续发现新的节日页面）"""
        related_links = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # 查找信息框（infobox）中的链接
            infobox = soup.find('table', class_='infobox') or soup.find('table', {'class': re.compile('infobox', re.I)})
            if infobox:
                for a in infobox.find_all('a', href=True):
                    href = a['href']
                    if href.startswith('/wiki/') and not href.startswith('/wiki/File:') and not href.startswith('/wiki/Category:'):
                        # 从href中提取页面标题
                        page_title = href.replace('/wiki/', '').replace('_', ' ')
                        # URL解码
                        try:
                            from urllib.parse import unquote
                            page_title = unquote(page_title)
                        except:
                            pass
                        # 检查链接文本和页面标题是否与传统节日相关
                        link_text = a.get_text().strip()
                        if self._is_festival_related(link_text) or self._is_festival_related(page_title):
                            full_url = urljoin(BASE_URL, href)
                            if full_url not in self.visited_urls and full_url not in related_links:
                                related_links.append(full_url)
            
            # 查找"参见"或"相关"部分的链接
            for heading in soup.find_all(['h2', 'h3']):
                heading_text = heading.get_text().strip().lower()
                if any(keyword in heading_text for keyword in ['参见', '相关', '另见', '参考']):
                    next_sibling = heading.find_next_sibling(['ul', 'div', 'p'])
                    if next_sibling:
                        for a in next_sibling.find_all('a', href=True):
                            href = a['href']
                            if href.startswith('/wiki/') and not href.startswith('/wiki/File:') and not href.startswith('/wiki/Category:'):
                                # 从href中提取页面标题
                                page_title = href.replace('/wiki/', '').replace('_', ' ')
                                # URL解码
                                try:
                                    from urllib.parse import unquote
                                    page_title = unquote(page_title)
                                except:
                                    pass
                                # 检查链接文本和页面标题是否与传统节日相关
                                link_text = a.get_text().strip()
                                if self._is_festival_related(link_text) or self._is_festival_related(page_title):
                                    full_url = urljoin(BASE_URL, href)
                                    if full_url not in self.visited_urls and full_url not in related_links:
                                        related_links.append(full_url)
        except Exception as e:
            print(f"提取相关链接失败: {e}")
        return related_links
    
    def run(self):
        """运行爬虫"""
        print("开始爬取维基百科汉族传统节日...")
        print(f"时间限制：30分钟")
        
        # 记录开始时间
        self.start_time = time.time()
        
        # 爬取列表页面
        try:
            response = self.session.get(START_URL, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            html_content = response.text
            
            # 提取初始节日链接
            initial_links = self._extract_festival_links(html_content)
            print(f"从列表页面找到 {len(initial_links)} 个初始节日链接")
            
            # 使用队列机制，继续发现新链接
            queue = list(initial_links)
            crawled_count = 0
            
            while queue:
                # 检查是否超过时间限制
                if self.start_time and (time.time() - self.start_time) >= self.max_duration:
                    print(f"已达到时间限制（30分钟），停止爬取")
                    break
                
                url = queue.pop(0)
                
                # 爬取页面
                if self.crawl_festival_page(url):
                    crawled_count += 1
                    
                    # 从当前页面提取相关链接，继续发现新页面
                    try:
                        response = self.session.get(url, timeout=10)
                        response.raise_for_status()
                        response.encoding = 'utf-8'
                        related_links = self._extract_related_links(response.text, url)
                        for link in related_links:
                            if link not in self.visited_urls and link not in queue:
                                queue.append(link)
                        if related_links:
                            print(f"  从当前页面发现 {len(related_links)} 个相关链接，队列中还有 {len(queue)} 个链接待爬取")
                    except Exception as e:
                        print(f"  提取相关链接失败: {e}")
                
                time.sleep(2)  # 延迟2秒，避免请求过快
            
            elapsed_time = int(time.time() - self.start_time)
            print(f"爬取完成，共爬取 {crawled_count} 个节日页面")
            print(f"资源数据: {self.resources_count} 个资源，用时: {elapsed_time//60}分{elapsed_time%60}秒")
            
        except Exception as e:
            print(f"爬取失败: {e}")
    
    def close(self):
        """关闭数据库连接"""
        if self.db_cursor:
            self.db_cursor.close()
        if self.db_conn:
            self.db_conn.close()
        print("数据库连接已关闭")


if __name__ == "__main__":
    spider = WikipediaSpider()
    try:
        spider.run()
    finally:
        spider.close()

