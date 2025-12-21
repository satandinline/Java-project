# 公共文化资源管理系统

一个基于AI的公共文化资源管理系统，支持文化资源的爬取、存储、检索、生成和管理。

## 项目结构

```
Java-project/
├── backend/                # Java后端（Spring Boot）
│   ├── src/main/java/com/cultural/  # Java源代码
│   │   ├── config/        # 配置类（数据源、Web配置）
│   │   ├── controller/    # REST API控制器
│   │   ├── service/       # 业务逻辑服务层
│   │   ├── dao/           # 数据访问层（JDBC）
│   │   ├── entity/        # 实体类
│   │   └── util/          # 工具类
│   ├── src/main/resources/  # 配置文件
│   │   └── application.yml  # Spring Boot配置
│   ├── pom.xml            # Maven配置文件
│   └── README.md          # 后端说明文档
├── AIGC/                  # AIGC相关功能模块（Python，用于AI功能）
│   ├── RAG.py             # RAG检索增强生成系统
│   ├── image_RAG.py       # 图像生成系统
│   ├── aigc_api_server.py # AIGC API服务器（保留用于AI功能）
│   └── README_AIGC.md     # AIGC功能说明
├── FrontEnd/              # 前端Vue.js应用
│   ├── src/               # 源代码
│   ├── public/            # 静态资源
│   ├── package.json       # 依赖配置
│   └── README.md          # 前端说明
├── spider/                # 爬虫模块（Python）
│   ├── minzu_festivals_spider.py  # 民族文化资源库爬虫
│   ├── wikipedia_spider.py        # 维基百科爬虫
│   ├── run_spiders.py             # 爬虫运行脚本
│   └── README.md                  # 爬虫说明
├── database_files/        # 数据库相关文件
│   ├── init_schema.sql    # 数据库初始化脚本（包含所有表结构）
│   ├── run_init_schema.py # 自动执行SQL脚本的Python工具
│   ├── erdiagram.md       # ER图（Mermaid格式）
│   └── readme.md          # 数据库说明
├── uploads/               # 用户上传的资源文件存储目录
├── public/                # 用户头像存储目录
├── crawled_images/        # 爬虫抓取的图片存储目录
├── db_connection.py       # 数据库连接管理（Python模块，爬虫和AIGC使用）
├── login.py               # 用户登录认证系统（Python，AIGC模块使用，已迁移到Java但AIGC仍依赖）
├── upload_handler.py      # 用户上传处理（Python，AIGC模块使用）
├── festival_name_utils.py # 节日名称转换工具
├── entity_type_utils.py   # 实体类型工具
├── requirements.txt       # Python依赖列表
├── install_dependencies.py # 自动安装依赖脚本
├── start_dev.bat          # Windows启动脚本
├── start_dev.sh           # Linux/Mac启动脚本
└── README.md              # 本文件
```

## 主要功能

### 1. 用户管理
- **用户注册**：系统自动生成8-10位数字账号，支持昵称、头像上传、自定义安全问题设置
- **用户登录**：使用账号（8-10位数字）和密码登录
- **账号特性**：账号一旦生成永久不可修改，请妥善保管
- **密码管理**：
  - 修改密码（需验证旧密码或二级密码）
  - 忘记密码（通过自定义安全问题找回）
- **用户资料**：
  - 昵称显示和修改（可在设置中修改）
  - 个人签名设置和修改（最多500字符，可在设置中修改）
  - 头像显示和更换，支持默认头像
- **角色管理**：管理员/普通用户
- **默认账号**：
  - 管理员：账号 `123456789`，密码 `123456`
  - 测试用户：账号 `987654321`，密码 `123456`
  - （首次登录后请立即修改密码）

### 2. 文化资源爬取
- 自动爬取民族文化资源库和维基百科的文化资源
- 支持文字和图片数据的爬取
- 自动过滤非文化相关图片
- 数据存储到数据库和本地文件夹

### 3. AIGC生成
- **文字AIGC（Tongyi模型）**：基于RAG的智能问答和文化资源生成
  - 支持上传图片并理解图片内容
  - 无文字提示时自动生成传统文化故事
  - 生成内容具有高辨识度（如夸父逐日、嫦娥奔月）
- **图片AIGC（Huoshan模型）**：图像生成和漫画/连环画创作
  - 支持上传图片并理解图片内容
  - 无文字提示时自动生成故事并生成连环画
  - 生成的图片以假乱真
- 支持多轮对话和历史会话管理（会话和消息存储在 `qa_sessions` 和 `qa_messages` 表）
- 文字和图片AIGC都支持图片上传
- 自动保存AIGC生成的内容到数据库
- 支持会话删除（单个、批量、全部）

### 4. 资源上传
- 用户上传文本或图片资源
- 自动查重和审核流程
- 标注任务自动创建

### 5. 数据管理
- 17个数据表的完整管理
- 支持视图和索引
- 数据关联和查询优化

## 快速开始

### 环境要求

**后端（Java）**：
- Java：最新LTS版本（推荐Java 17或21）
- Maven 3.6 或更高版本

**数据库**：
- MySQL 5.7+ 或 MySQL 8.0+

**前端**：
- Node.js 16+

**Python（用于爬虫和AIGC功能）**：
- Python 3.7+

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

3. **配置数据库**

**方式一：使用Python脚本自动初始化（推荐）**
```bash
python database_files/run_init_schema.py
```

**方式二：手动执行SQL脚本**
```bash
mysql -u root -p < database_files/init_schema.sql
```

脚本会自动：
- 创建数据库 `java_project`
- 创建所有17个表
- 创建视图和索引
- 创建默认管理员账户（账号：123456789，密码：123456）
- 创建默认测试用户账户（账号：987654321，密码：123456）

4. **配置环境变量**

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

启动Java后端：
```bash
cd backend
mvn spring-boot:run
```

或使用启动脚本：
```bash
# Windows
cd backend
start_backend.bat

# Linux/Mac
cd backend
chmod +x start_backend.sh
./start_backend.sh
```

启动前端：
```bash
cd FrontEnd
npm run dev
```

**注意**：如果需要使用AIGC功能（AI生成），还需要启动Python AIGC服务：
```bash
python AIGC/aigc_api_server.py
```

访问地址：
- 前端：http://localhost:5173（用户访问地址）
- Java后端API：http://localhost:8000（内部服务，通过前端代理访问）
- Python AIGC服务：http://localhost:8001（如需要AI功能）

## 默认账户

- **管理员账户**：
  - 账号：`123456789`（9位数字）
  - 密码：`123456`
  - 角色：管理员
  - 昵称：管理员
  - 头像：`/default.jpg`（使用默认头像）
- **测试用户账户**：
  - 账号：`987654321`（9位数字）
  - 密码：`123456`
  - 角色：普通用户
  - 昵称：测试用户
  - 头像：`/default.jpg`（使用默认头像）

**⚠️ 重要提示**：
- 首次登录后请立即修改默认密码！
- 账号一旦生成永久不可修改，请妥善保管！

## 详细文档

- [技术实现手册](技术实现手册.txt) - 系统架构、技术栈、API文档、代码规范
- [用户使用手册](用户使用手册.txt) - 用户操作指南、功能说明、常见问题
- [Java后端说明](backend/README.md) - Java后端项目文档
- [AIGC功能说明](AIGC/README_AIGC.md) - AIGC模块详细说明（Python）
- [前端使用说明](FrontEnd/README.md) - 前端开发指南
- [爬虫使用说明](spider/README.md) - 爬虫模块使用说明
- [数据库结构说明](database_files/readme.md) - 数据库设计文档
- [数据库ER图](database_files/erdiagram.md) - 数据库关系图

## 技术栈

- **后端（Java）**：Spring Boot 3.2.0, JDBC
  - 使用JDBC连接MySQL数据库
  - RESTful API服务
  - MVC架构（Controller-Service-DAO）
  - 推荐使用最新LTS版本的Java（如Java 17或21）
  
- **后端（Python - 可选）**：Flask, LangChain, PyMySQL
  - AIGC功能（AI生成）
  - 爬虫功能

- **前端**：Vue.js 3, Vite, Vue Router 4

- **数据库**：MySQL 8.0+（推荐使用最新版本）
  - 使用JDBC连接（Java后端）
  - 支持utf8mb4字符集

- **AI模型**（需要Python服务）：
  - 文字AIGC：通义千问（Tongyi）
  - 图片AIGC：火山引擎Seedream（Huoshan）
  - 备选：OpenAI GPT

- **向量数据库**（AIGC功能使用）：Chroma

## 密码加密

系统使用 **SHA-256** 单向哈希算法加密用户密码：
- 密码在存储前进行SHA-256哈希处理
- 登录时对输入的密码进行哈希后与数据库中的哈希值比较
- 安全问题答案同样使用SHA-256加密

## 文件说明

### 默认头像
- 位置：项目根目录的 `public/default.jpg`（与 `start_dev.bat` 同目录）
- 用途：用户未上传头像时显示的默认头像
- 格式：JPG格式，建议尺寸200x200像素

### 用户头像
- 存储位置：项目根目录的 `public/` 目录（与 `start_dev.bat` 同目录）
- 命名格式：`{account}.jpg`（如：123456789.jpg，使用账号而非用户名）
- 访问路径：`/{account}.jpg`
- 处理方式：自动压缩到200x200像素，统一保存为JPG格式

### 图片存储文件夹说明
- **`AIGC_graph/`**：存储AIGC生成的图片（图片AIGC功能）
- **`crawled_images/`**：存储爬虫抓取的图片（文化资源图片）
- **`public/`**（项目根目录）：存储用户头像和默认头像
- **`FrontEnd/public/`**：存储前端静态资源（favicon、视频等）
- **`uploads/`**：存储用户上传的待审核资源文件


## 常见问题

### 1. 前端页面空白
- 检查浏览器控制台是否有错误
- 确认后端API服务器是否正常运行
- 检查路由配置是否正确

### 2. 数据库连接失败
- 检查MySQL服务是否运行
- 验证 `.env` 文件中的数据库配置
- 确认数据库用户权限

### 3. 图片无法显示
- 确认项目根目录的 `public/default.jpg` 文件存在
- 检查头像文件路径是否正确
- 验证后端静态文件服务配置

### 4. 显示已删除的用户信息
- **问题**：即使数据库已删除用户，浏览器仍可能显示旧的用户信息（如昵称"立线"）
- **原因**：用户信息存储在浏览器的localStorage中
- **解决方法**：
  1. 打开浏览器开发者工具（F12）
  2. 进入"应用程序"（Application）或"存储"（Storage）标签
  3. 找到"本地存储"（Local Storage）中的 `userInfo` 项
  4. 删除该项或清除所有本地存储
  5. 刷新页面，系统会自动清除无效的用户信息
- **注意**：系统已添加自动验证机制，如果localStorage中的用户信息无效，会自动清除

## 许可证

本项目遵循项目主许可证。
