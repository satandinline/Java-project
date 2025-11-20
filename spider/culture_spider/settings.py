
import os

BOT_NAME = "culture_spider"
SPIDER_MODULES = ["culture_spider.spiders"]
NEWSPIDER_MODULE = "culture_spider.spiders"

ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 0.6
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 5
RETRY_TIMES = 3
HTTPCACHE_ENABLED = True
FEED_EXPORT_ENCODING = "utf-8"
DEFAULT_REQUEST_HEADERS = {
  "User-Agent": "FestivalCrawler/1.1 (+contact@example.com)",
  "Accept-Language": "zh-CN,zh;q=0.9"
}

ITEM_PIPELINES = {
    "culture_spider.pipelines.DedupInlinePipeline": 300,
    "culture_spider.pipelines.MySQLStorePipeline": 800,
}

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DB = os.getenv("MYSQL_DB", "java_project")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_CHARSET = "utf8mb4"

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
FEEDS = {
  "out.ndjson": {"format": "jsonlines", "encoding": "utf-8", "overwrite": True}
}
