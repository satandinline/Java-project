# 公共文化资源管理系统

一个基于AI的公共文化资源管理系统，支持文化资源的爬取、存储、检索、生成和管理。

## 项目结构

```
Java-project/
├── AIGC/                    # AIGC相关功能模块
│   ├── RAG.py              # RAG检索增强生成系统
│   ├── image_RAG.py        # 图像生成系统
│   ├── aigc_api_server.py  # AIGC API服务器
│   └── README_AIGC.md      # AIGC功能说明
├── FrontEnd/               # 前端Vue.js应用
│   ├── src/               # 源代码
│   ├── public/            # 静态资源（包含default.jpg默认头像）
│   ├── package.json       # 依赖配置
│   └── README.md          # 前端说明
├── spider/                # 爬虫模块
│   ├── minzu_festivals_spider.py  # 民族文化资源库爬虫
│   ├── wikipedia_spider.py        # 维基百科爬虫
│   ├── run_spiders.py             # 爬虫运行脚本
│   └── README.md                  # 爬虫说明
├── database_files/        # 数据库相关文件
│   ├── init_schema.sql    # 数据库初始化脚本（包含所有表结构）
│   ├── run_init_schema.py # 自动执行SQL脚本的Python工具
│   ├── erdiagram.md       # ER图（Mermaid格式）
│   └── readme.md          # 数据库说明
├── avatars/               # 用户上传的头像存储目录
├── db_connection.py       # 数据库连接管理（统一配置）
├── login.py              # 用户登录认证系统
├── upload_handler.py     # 用户上传处理
├── festival_name_utils.py # 节日名称转换工具
├── entity_type_utils.py  # 实体类型工具
├── requirements.txt       # Python依赖列表
├── install_dependencies.py # 自动安装依赖脚本
├── start_dev.bat          # Windows启动脚本
├── start_dev.sh           # Linux/Mac启动脚本
└── README.md              # 本文件
```

## 主要功能

### 1. 用户管理
- **用户注册**：支持昵称、头像上传、自定义安全问题设置
- **用户登录**：支持用户名密码登录
- **密码管理**：
  - 修改密码（需验证旧密码）
  - 忘记密码（通过自定义安全问题找回）
- **用户资料**：昵称、头像显示，支持默认头像
- **角色管理**：管理员/普通用户（默认管理员账号：admin/123456）

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
- 创建所有14个表
- 创建视图和索引
- 创建默认管理员账户（admin/123456）

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
- 前端：http://localhost:5173（用户访问地址）
- 后端API：http://localhost:8000（内部服务，通过前端代理访问）

## 默认账户

- **管理员账户**：
  - 用户名：`admin`
  - 密码：`123456`
  - 角色：管理员

**⚠️ 重要提示**：首次登录后请立即修改默认管理员密码！

## 详细文档

- [AIGC功能说明](AIGC/README_AIGC.md)
- [前端使用说明](FrontEnd/README.md)
- [爬虫使用说明](spider/README.md)
- [数据库结构说明](database_files/readme.md)
- [数据库ER图](database_files/erdiagram.md)

## 技术栈

- **后端**：Python, Flask, LangChain, PyMySQL
- **前端**：Vue.js 3, Vite, Vue Router 4
- **数据库**：MySQL
- **AI模型**：
  - 文字AIGC：通义千问（Tongyi）
  - 图片AIGC：火山引擎Seedream（Huoshan）
  - 备选：OpenAI GPT
- **向量数据库**：Chroma

## 密码加密

系统使用 **SHA-256** 单向哈希算法加密用户密码：
- 密码在存储前进行SHA-256哈希处理
- 登录时对输入的密码进行哈希后与数据库中的哈希值比较
- 安全问题答案同样使用SHA-256加密

## 文件说明

### 默认头像
- 位置：`FrontEnd/public/default.jpg`
- 用途：用户未上传头像时显示的默认头像
- 格式：JPG格式，建议尺寸200x200像素

### 用户头像
- 存储位置：`FrontEnd/public/` 目录
- 命名格式：`{username}.jpg`（如：admin.jpg）
- 访问路径：`/{username}.jpg`
- 处理方式：自动压缩到200x200像素，统一保存为JPG格式

### 图片存储文件夹说明
- **`AIGC_graph/`**：存储AIGC生成的图片（图片AIGC功能）
- **`crawled_images/`**：存储爬虫抓取的图片（文化资源图片）
- **`FrontEnd/public/`**：存储前端静态资源和用户头像
- **`avatars/`**：当前未使用（空文件夹）
- **`images/`**：当前未使用（空文件夹）

详细说明请参考 [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md)

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
- 确认 `FrontEnd/public/default.jpg` 文件存在
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
