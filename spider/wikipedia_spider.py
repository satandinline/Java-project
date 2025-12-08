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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_connection import get_spider_db_connection, get_spider_db_config
from festival_name_utils import chinese_to_english_festival, extract_and_convert_festival_name

# 爬虫配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        
        # 数量限制
        self.max_text_items = 200  # 最大文字数据条数
        self.max_image_items = 200  # 最大图片数据条数
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
            # 检查是否存在系统用户（username='system'或id=1）
            self.db_cursor.execute("SELECT id FROM users WHERE username = 'system' OR id = 1 LIMIT 1")
            user = self.db_cursor.fetchone()
            
            if user:
                self.system_user_id = user[0]
                print(f"使用系统用户ID: {self.system_user_id}")
            else:
                # 创建系统用户
                import hashlib
                # 使用一个固定的密码哈希（实际不会用于登录）
                password_hash = hashlib.sha256("system_user_password".encode()).hexdigest()
                self.db_cursor.execute("""
                    INSERT INTO users (username, password_hash, role, created_at)
                    VALUES ('system', %s, '管理员', NOW())
                """, (password_hash,))
                self.db_conn.commit()
                self.system_user_id = self.db_cursor.lastrowid
                print(f"创建系统用户，ID: {self.system_user_id}")
        except Exception as e:
            print(f"确保系统用户失败: {e}")
            # 如果失败，尝试使用ID=1（假设存在）
            self.system_user_id = 1
            print(f"使用默认用户ID: {self.system_user_id}")
    
    def _get_current_max_index(self):
        """获取当前crawled_images文件夹和数据库中的最大序号"""
        max_index = 0
        
        # 从文件夹中查找最大序号
        if os.path.exists(CRAWLED_IMAGES_DIR):
            for filename in os.listdir(CRAWLED_IMAGES_DIR):
                if filename.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    try:
                        # 提取文件名中的数字（如 "1.jpg" -> 1）
                        base_name = os.path.splitext(filename)[0]
                        if base_name.isdigit():
                            max_index = max(max_index, int(base_name))
                    except:
                        pass
        
        # 从数据库中查找最大序号
        try:
            self.db_cursor.execute("""
                SELECT file_name FROM crawled_images 
                WHERE file_name REGEXP '^[0-9]+\\.[a-zA-Z]+$'
                ORDER BY CAST(SUBSTRING_INDEX(file_name, '.', 1) AS UNSIGNED) DESC
                LIMIT 1
            """)
            result = self.db_cursor.fetchone()
            if result:
                base_name = os.path.splitext(result['file_name'])[0]
                if base_name.isdigit():
                    max_index = max(max_index, int(base_name))
        except Exception as e:
            print(f"从数据库获取最大序号失败（将仅使用文件夹中的序号）: {e}")
        
        self.current_image_index = max_index
        print(f"当前最大图片序号: {self.current_image_index}")
    
    def _get_next_image_name(self, image_url):
        """获取下一个图片文件名"""
        self.current_image_index += 1
        
        # 根据URL确定文件扩展名
        parsed_url = urlparse(image_url)
        ext = os.path.splitext(parsed_url.path)[1].lower()
        if not ext or ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            ext = '.jpg'  # 默认使用jpg
        
        return f"{self.current_image_index}{ext}"
    
    def _download_image(self, image_url, file_name):
        """下载图片并保存"""
        try:
            # 处理维基百科的图片URL（可能需要转换为直接访问URL）
            if 'upload.wikimedia.org' in image_url or image_url.startswith('//'):
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                # 对于缩略图，尝试获取原图
                if '/thumb/' in image_url:
                    image_url = image_url.split('/thumb/')[0] + '/' + '/'.join(image_url.split('/thumb/')[1].split('/')[1:])
            
            response = self.session.get(image_url, timeout=10, stream=True)
            response.raise_for_status()
            
            file_path = os.path.join(CRAWLED_IMAGES_DIR, file_name)
            
            # 保存图片
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
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
    
    def _save_to_database(self, file_name, storage_path, dimensions, tags=None):
        """保存图片信息到数据库"""
        # 检查是否达到图片数量限制
        if self.image_items_count >= self.max_image_items:
            return False
        
        try:
            tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
            
            self.db_cursor.execute("""
                INSERT INTO crawled_images 
                (file_name, storage_path, dimensions, tags, crawl_time)
                VALUES (%s, %s, %s, %s, NOW())
            """, (file_name, storage_path, dimensions, tags_json))
            
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
    
    def _save_text_to_database(self, resource_title, content_text, source_url, tags=None):
        """
        保存文字数据到cultural_resources和cultural_entities表
        resource_title: 文化资源名称（页面标题）
        content_text: 文本内容
        """
        # 检查是否达到文字数量限制
        if self.text_items_count >= self.max_text_items:
            return False
        
        if not resource_title or not content_text:
            return False
        
        try:
            # 从文本中提取节日名称（中文）
            festival_names = self._extract_festival_names(content_text)
            # 如果没有提取到节日名称，尝试从标题中提取
            if not festival_names:
                festival_names = self._extract_festival_names(resource_title)
            # 转换为英文节日名称
            chinese_festival_name = festival_names[0] if festival_names else "传统节日"
            festival_title_en = chinese_to_english_festival(chinese_festival_name)
            
            # 构建content_feature_data
            meta = {
                "tags": tags or [],
                "source_url": source_url,
                "festival_names": festival_names,
                "festival_name_en": festival_title_en
            }
            content_feature_data = json.dumps({
                "title": resource_title,
                "text": content_text,
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
            self.db_cursor.execute("""
                INSERT INTO cultural_entities
                (entity_name, entity_type, description, source, cultural_region)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                resource_title,  # entity_name字段存储文化资源名称
                "其他",  # entity_type使用枚举值：人物、作品、事件、地点、其他
                content_text,  # description存储完整的文本内容（详细文化信息）
                source_url,
                None  # 文化区域暂时为空
            ))
            
            self.db_conn.commit()
            self.text_items_count += 1
            return True
        except Exception as e:
            print(f"保存文字数据到数据库失败: {e}")
            self.db_conn.rollback()
            return False
    
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
            'button', 'btn', 'arrow', 'back', 'next', 'prev',
            'avatar', '头像', 'user', 'member',
            'thumb', 'thumbnail', 'small', 'tiny',
            'loading', 'spinner', 'placeholder', 'empty',
            'stub', 'disambig'  # 维基百科的占位图和消歧义图
        ]
        
        # 检查是否包含过滤关键词
        check_text = f"{alt} {title} {img_class} {img_url_lower}"
        for keyword in filter_keywords:
            if keyword in check_text:
                return False
        
        # 检查图片尺寸（通过URL中的尺寸参数）
        # 维基百科的缩略图通常包含尺寸信息，如 /thumb/.../220px-...
        size_match = re.search(r'(\d+)px', img_url_lower)
        if size_match:
            size = int(size_match.group(1))
            # 如果图片尺寸小于150px，可能是图标，过滤掉
            if size < 150:
                return False
        
        return True
    
    def _extract_image_from_festival_page(self, html_content, page_url):
        """从节日页面提取图片（只提取与文化资源相关的图片）"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 优先从信息框（infobox）中提取图片
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
                        return {
                            'url': src,
                            'alt': img_tag.get('alt', ''),
                            'title': img_tag.get('title', '')
                        }
        
        # 如果信息框没有图片，从内容区域提取第一张符合条件的图片
        content_area = soup.find('div', id='mw-content-text')
        if content_area:
            for img_tag in content_area.find_all('img'):
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(BASE_URL, src)
                    
                    # 检查是否是文化资源相关的图片
                    if self._is_cultural_image(img_tag, src):
                        return {
                            'url': src,
                            'alt': img_tag.get('alt', ''),
                            'title': img_tag.get('title', '')
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
        
        # 检查是否达到数量限制
        if self.text_items_count >= self.max_text_items and self.image_items_count >= self.max_image_items:
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
            description = self._extract_description(html_content)
            
            # 保存文字数据（即使没有图片也要保存，只要文本内容足够）
            if self.text_items_count < self.max_text_items and resource_title and description and len(description) > 50:
                tags = self._extract_tags(html_content, url, resource_title)
                if self._save_text_to_database(resource_title, description, url, tags):
                    print(f"已保存文字数据: {resource_title[:50]}... (文字数据: {self.text_items_count}/{self.max_text_items})")
            
            # 提取图片（如果未达到限制）
            if self.image_items_count < self.max_image_items:
                img_info = self._extract_image_from_festival_page(html_content, url)
                
                if img_info and img_info['url']:
                    # 下载图片
                    file_name = self._get_next_image_name(img_info['url'])
                    file_path, dimensions = self._download_image(img_info['url'], file_name)
                    
                    if file_path:
                        # 提取标签
                        tags = self._extract_tags(html_content, url, title)
                        if img_info.get('alt'):
                            tags.append(img_info['alt'])
                        if title:
                            tags.append(title)
                        
                        # 保存到数据库
                        storage_path = f"crawled_images/{file_name}"
                        if self._save_to_database(file_name, storage_path, dimensions, tags):
                            print(f"已保存图片: {file_name} (序号: {self.current_image_index}, 标题: {title}, 图片数据: {self.image_items_count}/{self.max_image_items})")
                            return True
            
            return False
            
        except Exception as e:
            print(f"爬取页面失败 {url}: {e}")
            return False
    
    def run(self):
        """运行爬虫"""
        print("开始爬取维基百科汉族传统节日...")
        print(f"数量限制：文字数据 {self.max_text_items} 条，图片数据 {self.max_image_items} 条")
        
        # 爬取列表页面
        try:
            response = self.session.get(START_URL, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            html_content = response.text
            
            # 提取节日链接
            festival_links = self._extract_festival_links(html_content)
            print(f"找到 {len(festival_links)} 个节日链接")
            
            # 爬取每个节日页面
            crawled_count = 0
            for link in festival_links:
                # 检查是否达到数量限制
                if self.text_items_count >= self.max_text_items and self.image_items_count >= self.max_image_items:
                    print(f"已达到数量限制，停止爬取")
                    break
                
                if self.crawl_festival_page(link):
                    crawled_count += 1
                
                time.sleep(2)  # 延迟2秒，避免请求过快
            
            print(f"爬取完成，共爬取 {crawled_count} 个节日页面")
            print(f"文字数据: {self.text_items_count}/{self.max_text_items} 条")
            print(f"图片数据: {self.image_items_count}/{self.max_image_items} 条")
            
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

