# weibo/spiders/search.py

import scrapy
import re
import html # 导入HTML转义库
from urllib.parse import unquote
from ..items import FestivalItem
from scrapy.exceptions import CloseSpider

class FestivalSpider(scrapy.Spider):
    name = 'festival'
    allowed_domains = ['zh.wikipedia.org']
    start_urls = ['https://zh.wikipedia.org/wiki/%E6%BC%A2%E6%97%8F%E5%82%B3%E7%B5%B1%E7%AF%80%E6%97%A5']

    def __init__(self, *args, **kwargs):
        super(FestivalSpider, self).__init__(*args, **kwargs)
        self.item_count = 0
        self.item_limit = 5 # 统一的数量限制

    def parse(self, response):

        self.logger.info(f"成功获取列表页面: {response.url}")
        html_text = response.text
        try:
            html_after_heading = html_text.split('<h2 id="一般民俗節日">', 1)[1]
            table_html_match = re.search(r'<table class="wikitable">(.*?)</table>', html_after_heading, re.S)
            table_html = table_html_match.group(1)
            rows = re.findall(r'<tr align="center">(.*?)</tr>', table_html, re.S)
        except (IndexError, AttributeError):
            self.logger.error("无法定位'一般民俗节日'表格，爬虫终止。")
            return
        festival_links = []
        for row in rows:
            link_match = re.search(r'<td>.*?</td>\s*<td><a href="(/wiki/[^"]+)"', row, re.S)
            if link_match:
                festival_links.append(link_match.group(1))
        unique_links = sorted(list(set(festival_links)))
        self.logger.info(f"通过表格解析，精准定位到 {len(unique_links)} 个不重复的节日链接")
        for link in unique_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_festival)

    def parse_festival(self, response):
        if self.item_count >= self.item_limit:
            return

        self.logger.info(f"正在解析节日页面: {response.url}")
        html_text = response.text
        item = FestivalItem()

        # --- 标题提取 ---
        title_match = re.search(r'<h1 id="firstHeading".*?>(.*?)</h1>', html_text, re.S)
        title = re.sub(r'<.*?>', '', title_match.group(1)).strip() if title_match else ''
        
        # --- 终极文本清洗逻辑 ---
        description = ''
        content_area_match = re.search(r'<div id="mw-content-text".*?>(.*?)<div id="catlinks"', html_text, re.S)
        if content_area_match:
            content_area = content_area_match.group(1)
            paragraphs = re.findall(r'<p>(.*?)</p>', content_area, re.S)
            for p_html in paragraphs:
                # 第一步：解码HTML实体，把 &#91; 这种代码转回 [ 符号
                decoded_text = html.unescape(p_html)
                # 第二步：移除所有HTML标签，比如 <b>, <i> 等
                text_no_tags = re.sub(r'<.*?>', '', decoded_text)
                # 第三步：移除所有方括号引用，比如 [1], [注 1] 等
                p_text = re.sub(r'\[.*?\]', '', text_no_tags).strip()
                
                # 选择第一个足够长的、清洗干净的段落作为最终描述
                if len(p_text) > 30:
                    description = p_text
                    break
        
        # --- 智能图片提取---
        image_url = ''
        infobox_match = re.search(r'<table class="[^"]*infobox[^"]*".*?</table>', html_text, re.S)
        if infobox_match:
            img_match = re.search(r'<img.*?src="([^"]+\.(?:jpg|jpeg|png|gif))"', infobox_match.group(0), re.I)
            if img_match:
                image_url = img_match.group(1)
        if not image_url and content_area_match:
            all_imgs = re.findall(r'<img[^>]+>', content_area_match.group(1))

        if image_url and image_url.startswith('//'):
            image_url = 'https:' + image_url
        
        # --- 填充 Item ---
        if title and description and image_url:
            item['title'] = title
            item['source_from'] = '维基百科'
            item['source_url'] = response.url
            item['content_feature_data'] = description
            item['entity_name'] = title
            item['entity_type'] = '传统节日'
            item['description'] = description
            item['image_urls'] = [image_url]

            self.logger.info(f"成功解析页面: {title} (已锁定图片)")
            
            self.item_count += 1
            if self.item_count >= self.item_limit:
                yield item
                self.logger.info(f"已达到 {self.item_limit} 个项目的限制，正在关闭爬虫...")
                raise CloseSpider(f'达到 {self.item_limit} 个项目的限制')
            
            yield item
        else:
            self.logger.warning(f"页面信息不完整或未找到合适图片，已跳过: {response.url}")