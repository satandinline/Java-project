# culture_spider/items.py
import scrapy

class FestivalItem(scrapy.Item):
    url = scrapy.Field()
    canonical_url = scrapy.Field()
    site_name = scrapy.Field()
    title = scrapy.Field()
    lang = scrapy.Field()
    category_path = scrapy.Field()
    publish_date = scrapy.Field()
    author = scrapy.Field()
    content_text = scrapy.Field()
    festival_names = scrapy.Field()
    ethnic_groups = scrapy.Field()
    regions = scrapy.Field()
    calendar_type = scrapy.Field()
    date_rule = scrapy.Field()
    media = scrapy.Field()
    content_hash = scrapy.Field()
    crawl_time = scrapy.Field()

class WikiItem(scrapy.Item):   # 仅供维基爬虫用
    url = scrapy.Field()
    title = scrapy.Field()
    lang = scrapy.Field()
    abstract = scrapy.Field()
    infobox = scrapy.Field()   # dict
    categories = scrapy.Field()
    images = scrapy.Field()
    content_text = scrapy.Field()
    content_hash = scrapy.Field()
