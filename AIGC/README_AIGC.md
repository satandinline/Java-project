# AIGC功能使用说明

## 后端API服务器

### 安装依赖

**方式一：使用自动安装脚本（推荐）**
```bash
# 在项目根目录运行
python install_dependencies.py
```

**方式二：手动安装**
```bash
# 安装所有Python依赖
pip install -r requirements.txt

# 或只安装AIGC相关依赖
pip install flask flask-cors langchain langchain-openai langchain-community pymysql python-dotenv openai pydantic chromadb
```

### 启动服务器
```bash
# 在项目根目录运行
python AIGC/aigc_api_server.py
```

服务器将在 `http://localhost:5000` 启动。

### API端点

1. **POST /api/aigc/chat** - AIGC聊天接口
   - 参数：
     - `mode`: 'text' 或 'image'
     - `query`: 用户输入的问题或提示词
     - `images`: 图片文件（可选，仅图片AIGC模式）

2. **POST /api/aigc/extract-title** - 提取对话主题
   - 参数：
     - `conversation`: 对话内容文本

3. **GET /api/health** - 健康检查

## 前端配置

前端已配置Vite代理，会自动将 `/api/*` 请求转发到 `http://localhost:5000`。

### 一键启动（推荐）

**Windows系统：**
```bash
# 在项目根目录运行
start_dev.bat
```

**Linux/Mac系统：**
```bash
# 在项目根目录运行
chmod +x start_dev.sh
./start_dev.sh
```

或者使用npm命令：
```bash
cd FrontEnd
npm run dev:full
```

这会自动同时启动前端和后端服务器。

## 功能说明

### 文字AIGC
- 使用RAG系统进行问答
- 支持多轮对话
- 支持图片输入（分析图片内容）

### 图片AIGC
- 使用ImageAIGC系统生成图片
- 支持文字提示词
- 支持参考图片输入

### 历史会话
- 自动保存对话历史到数据库（`qa_sessions` 和 `qa_messages` 表）
- 每个用户只能看到自己的会话历史
- 自动提取对话主题（不超过20字）
- 支持开启新对话
- 支持加载历史会话
- 会话数据持久化存储，不依赖浏览器localStorage

## 环境变量配置

确保 `.env` 文件中包含以下配置：

```env
# 文本生成API密钥（至少配置一个）
DASHSCOPE_API_KEY=your_aliyun_api_key
# 或
OPENAI_API_KEY=your_openai_api_key

# 图片生成API密钥
VOLC_SEEDREAM_API_KEY=your_volc_api_key
# 或
DASHSCOPE_API_KEY=your_aliyun_api_key

# 数据库配置
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DB=java_project
```

## 数据库连接说明

系统使用统一的数据库连接管理（`db_connection.py`）：
- **爬虫模块**：使用root账户连接数据库
- **其他模块**：使用登录用户的账户连接数据库，确保数据隔离和权限控制

## 用户管理

- 所有注册用户默认角色为"普通用户"
- 普通用户和管理员都拥有所有权限，但普通用户的权限不可转移
- 用户信息存储在 `users` 表中
- 用户行为日志存储在 `user_behavior_logs` 表中

## 数据存储

### 数据存储

#### AIGC生成的数据

- **文字数据**：
  - `AIGC_cultural_resources` 表：存储生成的文本资源（title字段存储英文节日名称）
  - `AIGC_cultural_entities` 表：存储提取的实体信息（entity_name存储资源名称，entity_type为ENUM类型）
- **图片数据**：
  - `AIGC_graph` 表：存储生成的图片元数据
  - `AIGC_graph` 文件夹：存储图片文件

#### 对话历史数据

- **会话信息**：`qa_sessions` 表
  - 存储每个用户的会话列表
  - 包含会话摘要（自动提取的标题）
  - 关联用户ID
- **消息内容**：`qa_messages` 表
  - 存储每条用户消息和AI回复
  - 关联会话ID
  - 包含发送者类型（user/ai）和时间戳

#### 用户上传的数据

- **待审核数据**：`cultural_resources_from_user` 表
- **审核通过后**：迁移到 `cultural_resources` 表
- **标注任务**：自动创建标注任务，存储在 `annotation_tasks` 表（通过 `resource_source` 字段关联不同的资源表）

