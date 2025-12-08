# 公共文化资源管理系统

一个基于AI的公共文化资源管理系统，支持文化资源的爬取、存储、检索、生成和管理。

## 项目结构

```
Java-project/
├── AIGC/                    # AIGC相关功能模块
│   ├── RAG.py              # RAG检索增强生成系统
│   ├── image_RAG.py        # 图像生成系统
│   ├── aigc_api_server.py  # AIGC API服务器
│   ├── aigc_db_helper.py   # AIGC数据库辅助函数
│   └── README_AIGC.md      # AIGC功能说明
├── FrontEnd/               # 前端Vue.js应用
│   ├── src/               # 源代码
│   ├── package.json       # 依赖配置
│   └── README.md          # 前端说明
├── spider/                # 爬虫模块
│   ├── minzu_festivals_spider.py  # 民族文化资源库爬虫
│   ├── wikipedia_spider.py        # 维基百科爬虫
│   ├── run_spiders.py             # 爬虫运行脚本
│   └── README.md                  # 爬虫说明
├── database_files/        # 数据库相关文件
│   ├── init_schema.sql    # 数据库初始化脚本
│   ├── migrate_annotation_tasks.sql  # 数据库迁移脚本
│   ├── erdiagram.md       # ER图（Mermaid格式）
│   └── readme.md          # 数据库说明
├── db_connection.py       # 数据库连接管理
├── login.py               # 用户登录认证
├── upload_handler.py      # 用户上传处理
├── festival_name_utils.py # 节日名称转换工具
├── entity_type_utils.py  # 实体类型工具
├── requirements.txt       # Python依赖列表
├── install_dependencies.py # 自动安装依赖脚本
├── start_dev.bat          # Windows启动脚本
├── start_dev.sh           # Linux/Mac启动脚本
└── README.md              # 本文件
```

## 主要功能

### 1. 文化资源爬取
- 自动爬取民族文化资源库和维基百科的文化资源
- 支持文字和图片数据的爬取
- 自动过滤非文化相关图片
- 数据存储到数据库和本地文件夹

### 2. AIGC生成
- **文字AIGC**：基于RAG的智能问答和文化资源生成
- **图片AIGC**：图像生成和漫画/连环画创作
- 支持多轮对话和历史会话管理（会话和消息存储在 `qa_sessions` 和 `qa_messages` 表）
- 支持图片输入和分析
- 自动保存AIGC生成的内容到数据库

### 3. 用户管理
- 用户注册和登录
- 角色管理（管理员/普通用户）
- 用户行为日志记录

### 4. 资源上传
- 用户上传文本或图片资源
- 自动查重和审核流程
- 标注任务自动创建

### 5. 数据管理
- 14个数据表的完整管理
- 支持视图和索引
- 数据关联和查询优化

## 快速开始

### 环境要求

- Python 3.7+
- Node.js 16+
- MySQL 5.7+

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd Java-project
```

2. **一键安装所有依赖（推荐）**
```bash
# Windows
python install_dependencies.py

# Linux/Mac
python3 install_dependencies.py
# 或
chmod +x install_dependencies.py
./install_dependencies.py
```

此脚本会自动：
- 检查Python和Node.js环境
- 安装所有Python依赖包
- 安装所有前端依赖包

**或者手动安装：**

2a. **安装Python依赖**
```bash
pip install -r requirements.txt
```

2b. **安装前端依赖**
```bash
cd FrontEnd
npm install
cd ..
```

4. **配置数据库**
   - 创建MySQL数据库 `java_project`
   - 运行 `database_files/run_init_schema.py` 自动初始化数据库
   - 或手动执行 `database_files/init_schema.sql` 初始化数据库

5. **配置环境变量**
   创建 `.env` 文件，配置以下内容：
```env
# 数据库配置
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DB=java_project

# API密钥（至少配置一个）
DASHSCOPE_API_KEY=your_aliyun_api_key
OPENAI_API_KEY=your_openai_api_key
VOLC_SEEDREAM_API_KEY=your_volc_api_key
```

### 启动项目

**方式一：一键启动（推荐）**

Windows:
```bash
start_dev.bat
```

Linux/Mac:
```bash
chmod +x start_dev.sh
./start_dev.sh
```

**方式二：分别启动**

启动前端：
```bash
cd FrontEnd
npm run dev
```

启动后端：
```bash
python AIGC/aigc_api_server.py
```

访问地址：
- 前端：http://localhost:5173
- 后端API：http://localhost:5000

## 详细文档

- [AIGC功能说明](AIGC/README_AIGC.md)
- [前端使用说明](FrontEnd/README.md)
- [爬虫使用说明](spider/README.md)
- [数据库结构说明](database_files/readme.md)
- [数据库ER图](database_files/erdiagram.md)

## 技术栈

- **后端**：Python, Flask, LangChain, PyMySQL
- **前端**：Vue.js 3, Vite
- **数据库**：MySQL
- **AI模型**：通义千问, OpenAI GPT, 火山引擎
- **向量数据库**：Chroma

## 许可证

本项目遵循项目主许可证。
