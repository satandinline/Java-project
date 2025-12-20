# 文化资源爬虫

本目录包含两个独立的爬虫程序，用于爬取文化资源图片并存储到数据库。

## 文件说明

- `minzu_festivals_spider.py` - 中国民族文化资源库爬虫
- `wikipedia_spider.py` - 维基百科汉族传统节日爬虫
- `run_spiders.py` - 主运行文件，统一运行所有爬虫

## 功能特点

1. **统一资源管理**：每个资源包含文字（cultural_resources + cultural_entities）和图片（crawled_images），三个表通过resource_id和entity_id关联
2. **递增式图片命名**：图片从1开始递增命名（1.jpg, 2.jpg, ...），每次运行前自动检查当前最大序号
3. **自动存储到数据库**：爬取的图片信息自动存储到 `crawled_images` 表，并关联到对应的文字资源
4. **图片下载**：自动下载图片到 `crawled_images` 文件夹，支持超时重试机制（最多3次，超时30秒）
5. **标签提取**：自动从页面内容中提取标签并存储
6. **智能过滤**：自动过滤非文化相关的图片（如logo、图标、横幅、二维码、维基百科特殊URL等）
7. **默认图片处理**：如果文字资源没有图片，自动插入default.jpg记录
8. **资源数量限制**：统一限制资源数量（默认20个），每个资源包含文字和图片

## 数据库表结构

### 图片数据存储 (`crawled_images` 表)

图片信息存储到 `crawled_images` 表，包含以下字段：

- `file_name`: 文件名（如 "8.jpg" 或 "8-1.jpg"）
- `storage_path`: 存储路径（如 "crawled_images/8.jpg"）
- `dimensions`: 图片尺寸（如 "1024x768"）
- `crawl_time`: 抓取时间（自动）
- `tags`: JSON格式的标签数组（已清洗，移除纯数字等无关信息）
- `resource_id`: 关联的文化资源ID（如果图片属于某个文字资源）
- `entity_id`: 关联的文化实体ID（如果图片属于某个文化实体）
- `festival_name`: 节日名称（中文，用于快速查询）

### 文字数据存储

文字数据存储到两个表：

1. **`cultural_resources` 表**：
   - `title`: 节日名称（从文本内容中提取的传统节日名称）
   - `resource_type`: 资源类型（如："文本"）
   - `file_format`: 文件格式
   - `source_from`: 数据来源（网站名称）
   - `source_url`: 原始URL链接
   - `content_feature_data`: 文本内容

2. **`cultural_entities` 表**：
   - `entity_name`: 实体名称（文化资源的名称，通常是页面标题）
   - `entity_type`: 实体类型（ENUM类型：'人物', '作品', '事件', '地点', '其他'）
   - `description`: 描述（页面主要内容）
   - `source`: 来源

## 环境要求

### Python版本
Python 3.7+

### 依赖包

**方式一：使用自动安装脚本（推荐）**
```bash
# 在项目根目录运行
python install_dependencies.py
```

**方式二：手动安装**
```bash
# 安装所有Python依赖（包括爬虫依赖）
pip install -r requirements.txt

# 或只安装爬虫依赖
pip install requests beautifulsoup4 pymysql pillow python-dotenv
```

所有依赖已在项目根目录的 `requirements.txt` 中定义。

## 配置

### 数据库配置

爬虫使用统一的数据库连接配置文件 `db_connection.py`，该文件已配置好爬虫专用的root账户连接信息。

**注意**：爬虫使用root账户连接数据库，其他文件（如RAG.py、image_RAG.py）使用登录用户的账户连接数据库。

### 数据库初始化

确保已执行 `database_files/init_schema.sql` 创建数据库表结构。

**推荐方式：**
```bash
python database_files/run_init_schema.py
```

## 使用方法

### 方法1：运行所有爬虫（推荐）

```bash
# 在spider目录下运行
python run_spiders.py
```

这将依次运行：
1. 中国民族文化资源库爬虫
2. 维基百科爬虫

### 方法2：单独运行爬虫

#### 运行中国民族文化资源库爬虫
```bash
python minzu_festivals_spider.py
```

#### 运行维基百科爬虫
```bash
python wikipedia_spider.py
```

## 爬虫说明

### 1. 中国民族文化资源库爬虫 (`minzu_festivals_spider.py`)

- **目标网站**：中国民族文化资源库（minwang.com.cn, mzzyk.com）
- **爬取内容**：民族节日相关页面的文字和图片
- **爬取范围**：从起始URL开始，自动发现并爬取相关链接
- **限制**：
  - 文字数据：最多200条
  - 图片数据：最多20条
- **数据存储**：
  - 文字数据：存储到 `cultural_resources` 和 `cultural_entities` 表
  - 图片数据：存储到 `crawled_images` 表和 `crawled_images` 文件夹

### 2. 维基百科爬虫 (`wikipedia_spider.py`)

- **目标网站**：中文维基百科
- **爬取内容**：汉族传统节日页面的文字和图片
- **爬取范围**：从"汉族传统节日"列表页面提取节日链接，逐个爬取
- **限制**：
  - 文字数据：最多200条
  - 图片数据：最多20条
- **数据存储**：
  - 文字数据：存储到 `cultural_resources` 和 `cultural_entities` 表
  - 图片数据：存储到 `crawled_images` 表和 `crawled_images` 文件夹

## 数据存储

### 图片存储

- **存储位置**：项目根目录下的 `crawled_images` 文件夹
- **命名规则**：递增数字命名（1.jpg, 2.jpg, 3.jpg, ...）
- **序号管理**：每次运行前自动检查文件夹和数据库中的最大序号，新图片在此基础上递增
- **图片过滤**：自动过滤掉非文化相关的图片（如logo、图标、横幅、二维码等）

### 文字存储

- **存储位置**：数据库 `cultural_resources` 和 `cultural_entities` 表
- **内容提取**：自动提取页面标题、正文内容、节日名称等信息
- **去重机制**：通过URL和内容哈希进行去重

## 注意事项

1. **网络连接**：确保网络连接正常，能够访问目标网站
2. **数据库连接**：确保MySQL服务正在运行，数据库已创建
3. **请求频率**：爬虫已设置适当的延迟，避免请求过快被封禁
4. **图片格式**：支持 jpg, jpeg, png, gif, webp 格式
5. **错误处理**：爬虫会自动处理网络错误和数据库错误，继续运行
6. **爬取限制**：每个网站的文字数据限制为200条，图片数据限制为20条，避免数据量过大
7. **图片质量检测**：自动过滤空白、纯色、单调等无意义的图片，确保只保存有意义的图片
7. **图片过滤**：爬虫会自动过滤掉非文化相关的图片（如logo、图标、横幅、二维码等），只保留与文化资源相关的图片
8. **文字爬取**：爬虫会爬取所有相关页面，包括纯文字页面，确保获取完整的文化资源信息
9. **内容提取**：爬虫会智能提取页面主要内容，过滤导航、注意事项等无关内容

## 故障排除

### 数据库连接失败
- 检查MySQL服务是否运行
- 检查环境变量配置是否正确
- 检查数据库用户权限

### 图片下载失败
- 检查网络连接
- 检查目标网站是否可访问
- 某些图片URL可能需要特殊处理

### 序号冲突
- 爬虫会自动检查并处理序号冲突
- 如果出现冲突，可以手动清理 `crawled_images` 文件夹

### 内容提取不准确
- 检查目标网站HTML结构是否变化
- 可能需要更新选择器

## 开发说明

### 添加新爬虫

1. 创建新的爬虫文件（如 `new_spider.py`）
2. 实现类似的类结构，包含：
   - `_connect_db()` - 连接数据库
   - `_get_current_max_index()` - 获取当前最大序号
   - `_download_image()` - 下载图片
   - `_save_to_database()` - 保存到数据库
   - `run()` - 运行爬虫
   - `close()` - 关闭连接
3. 在 `run_spiders.py` 中添加新爬虫的调用

## 许可证

本项目遵循项目主许可证。
