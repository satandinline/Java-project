# AIGC功能使用说明

## 概述

AIGC（AI-Generated Content）模块提供文字和图片生成功能，基于RAG（检索增强生成）技术，结合数据库中的文化资源进行智能问答和内容生成。

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

服务器将在 `http://localhost:8000` 启动（通过前端5173代理访问）。

### API端点

#### 1. POST /api/aigc/chat - AIGC聊天接口

**功能：** 文字或图片AIGC生成

**参数：**
- `mode`: 'text' 或 'image'（必需）
- `query`: 用户输入的问题或提示词（可选，如果有图片可以留空）
- `images`: 图片文件（可选，文字和图片AIGC模式都支持）
- `session_id`: 会话ID（可选，用于多轮对话）
- `stream`: true/false（可选，是否启用流式输出，默认false）

**请求头：**
- `X-User-Id`: 用户ID（必需）

**响应：**
- 流式输出：Server-Sent Events (SSE) 格式
- 非流式输出：JSON格式

#### 2. POST /api/aigc/sessions - 创建新会话

**功能：** 创建新的AIGC对话会话

**参数：**
- `summary`: 会话摘要（可选，会自动提取）

**请求头：**
- `X-User-Id`: 用户ID（必需）

#### 3. GET /api/aigc/sessions - 获取会话列表

**功能：** 获取当前用户的所有会话列表

**查询参数：**
- `user_id`: 用户ID（必需）

**请求头：**
- `X-User-Id`: 用户ID（必需）

#### 4. GET /api/aigc/sessions/{session_id}/messages - 获取会话消息

**功能：** 获取指定会话的所有消息

**请求头：**
- `X-User-Id`: 用户ID（必需）

#### 5. DELETE /api/aigc/sessions/{session_id} - 删除单个会话

**功能：** 删除指定的会话及其所有消息

**请求头：**
- `X-User-Id`: 用户ID（必需）

#### 6. DELETE /api/aigc/sessions/batch - 批量删除会话

**功能：** 批量删除多个会话

**参数：**
- `session_ids`: 会话ID数组（必需）

**请求头：**
- `X-User-Id`: 用户ID（必需）

#### 7. DELETE /api/aigc/sessions/all - 删除所有会话

**功能：** 删除当前用户的所有会话

**请求头：**
- `X-User-Id`: 用户ID（必需）

#### 8. POST /api/aigc/extract-title - 提取对话主题

**功能：** 从对话内容中提取主题（不超过20字）

**参数：**
- `conversation`: 对话内容文本（必需）

#### 9. GET /api/health - 健康检查

**功能：** 检查服务器运行状态

## 前端配置

前端已配置Vite代理，会自动将 `/api/*` 请求转发到 `http://localhost:8000`。

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

### 文字AIGC（使用Tongyi模型）

- **RAG检索增强生成**：基于数据库中的文化资源进行智能问答
- **多轮对话**：支持上下文理解和多轮对话
- **图片输入**：支持上传图片并分析图片内容（使用图文互搜的图片理解逻辑）
- **图片理解**：自动理解上传图片的内容，并用于生成回答
- **默认故事生成**：如果没有文字提示，会根据图片内容自动生成像夸父逐日、嫦娥奔月这样具有辨识度的传统文化故事
- **资源检索**：自动检索相关文化资源并显示
- **实体提取**：自动提取关键实体信息
- **高质量生成**：使用通义千问（Tongyi）模型，生成内容具有高辨识度

### 图片AIGC（使用Huoshan模型）

- **文字提示词生成**：根据文字描述生成图片
- **图片输入**：支持上传图片并分析图片内容（使用图文互搜的图片理解逻辑）
- **图片理解**：自动理解上传图片的内容，并用于生成图片
- **默认连环画生成**：如果没有文字提示，会先生成故事，再根据故事生成连环画
- **高质量生成**：使用火山引擎Seedream（Huoshan）模型，生成的图片以假乱真
- **参考图片输入**：支持上传参考图片进行风格迁移
- **风格选择**：支持多种艺术风格（如：水墨画、油画等）
- **历史记录**：生成的图片自动保存到数据库

### 历史会话管理

- **自动保存**：对话历史自动保存到数据库（`qa_sessions` 和 `qa_messages` 表）
- **用户隔离**：每个用户只能看到自己的会话历史
- **自动提取主题**：自动提取对话主题（不超过20字）作为会话标题
- **会话操作**：
  - 开启新对话
  - 加载历史会话
  - 删除单个会话
  - 批量删除会话
  - 删除所有会话
- **界面优化**：
  - 支持隐藏/显示历史记录面板
  - 状态持久化（保存在localStorage）

### 数据持久化

- **会话数据**：存储在 `qa_sessions` 表，不依赖浏览器localStorage
- **消息数据**：存储在 `qa_messages` 表，包含用户消息和AI回复
- **图片数据**：生成的图片存储在 `AIGC_graph` 表和文件夹

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

### AIGC生成的数据

- **文字数据**：
  - `AIGC_cultural_resources` 表：存储生成的文本资源（title字段存储节日名称）
  - `AIGC_cultural_entities` 表：存储提取的实体信息（entity_name存储资源名称，entity_type为ENUM类型）
- **图片数据**：
  - `AIGC_graph` 表：存储生成的图片元数据
  - `AIGC_graph` 文件夹：存储图片文件

### 对话历史数据

- **会话信息**：`qa_sessions` 表
  - 存储每个用户的会话列表
  - 包含会话摘要（自动提取的标题）
  - 关联用户ID
- **消息内容**：`qa_messages` 表
  - 存储每条用户消息和AI回复
  - 关联用户ID和会话ID
  - 包含 `user_message`（用户输入）和 `ai_message`（AI回答）字段
  - 包含 `model` 字段（'text' 或 'image'）标识使用的模型类型
  - 包含 `image_url` 字段（图片AIGC时存储生成的图片地址）
  - 包含时间戳和用户反馈字段

### 用户上传的数据

- **待审核数据**：`cultural_resources_from_user` 表
- **审核通过后**：迁移到 `cultural_resources` 表
- **标注任务**：自动创建标注任务，存储在 `annotation_tasks` 表（通过 `resource_source` 字段关联不同的资源表）

## 技术架构

### RAG系统

- **向量数据库**：Chroma
- **文本分割**：LangChain TextSplitter
- **嵌入模型**：支持多种嵌入模型
- **检索策略**：相似度检索 + 关键词检索

### 图片生成

- **模型支持**：火山引擎、通义千问等
- **风格迁移**：支持参考图片风格提取
- **图片存储**：本地文件系统 + 数据库元数据

## 常见问题

### 1. API请求失败
- 检查后端服务器是否运行
- 验证API密钥配置是否正确
- 查看后端日志错误信息

### 2. 图片生成失败
- 检查图片生成API密钥
- 验证提示词格式
- 确认图片存储路径权限

### 3. 会话加载失败
- 检查数据库连接
- 验证用户ID是否正确
- 查看数据库表结构

## 许可证

本项目遵循项目主许可证。
