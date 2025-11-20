
# 文化资源爬虫（Scrapy + MySQL）
先在 MySQL 中创建库 `java_project` 并执行 `sql/init_schema.sql`，再运行爬虫即可把抓到的数据写入数据库。

## 使用
python -m venv venv
.\venv\Scripts\Activate.ps1   # 或 venv\Scripts\activate.bat
pip install -r requirements.txt

# 可通过环境变量覆盖连接：MYSQL_HOST/MYSQL_PORT/MYSQL_DB/MYSQL_USER/MYSQL_PASSWORD
scrapy crawl minzu_festivals  # 同时导出 out.ndjson
