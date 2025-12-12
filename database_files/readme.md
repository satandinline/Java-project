# 数据库说明文档

## 数据库初始化

### 方式一：使用Python脚本自动初始化（推荐）

```bash
# 在项目根目录运行
python database_files/run_init_schema.py
```

此脚本会自动：
- 连接到MySQL数据库（使用root账户）
- 执行 `init_schema.sql` 中的所有SQL语句
- 创建所有表、视图、索引和角色
- 创建默认管理员账户（admin/123456）

**配置说明：**
- 脚本会从环境变量或 `.env` 文件读取数据库配置
- 如果没有配置，使用默认值（127.0.0.1:3306, root, M17382930994c@）

### 方式二：手动执行SQL脚本

```bash
# 在MySQL客户端中执行
mysql -u root -p < database_files/init_schema.sql
```

## 数据库结构

### 表列表（共14个表）

1. **users** - 用户表
2. **cultural_resources** - 文化资源表
3. **cultural_entities** - 文化实体表
4. **entity_relationships** - 实体关系表
5. **user_behavior_logs** - 用户行为日志表
6. **qa_sessions** - 问答会话表
7. **qa_messages** - 问答消息表
8. **annotation_tasks** - 标注任务表
9. **annotation_records** - 标注记录表
10. **cultural_resources_from_user** - 用户上传资源表
11. **AIGC_cultural_resources** - AIGC文化资源表
12. **AIGC_graph** - AIGC生成图像表
13. **crawled_images** - 爬虫抓取图像表
14. **AIGC_cultural_entities** - AIGC文化实体表

### ER图

- `erdiagram.md` 文件包含了完整的ER图（Mermaid格式）
- 可以使用Mermaid工具查看或导出为PNG/SVG格式
- 所有表都包含在ER图中，包括新增的AIGC相关表和爬虫相关表

## 重要表结构说明

### 1. 用户表 (users)

**新增字段（已整合到init_schema.sql）：**
- `nickname` - 用户昵称（可选，未设置则随机生成）
- `avatar_path` - 头像路径（默认：`./default.jpg`）
- `security_question` - 自定义安全问题（用于找回密码）
- `security_answer_hash` - 安全问题答案的哈希值（SHA-256）

**默认管理员账户：**
- 用户名：`admin`
- 密码：`123456`（SHA-256哈希值：`8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92`）
- 角色：管理员
- 昵称：管理员

### 2. 文化资源表 (cultural_resources)

**用途：** 存储爬虫抓取或用户上传的原始文化素材。

**重要字段：**
- `title` - 节日名称（文化资源涉及到的传统节日的名称）
- `upload_user_id` - 上传用户ID（关联users表，用户删除后设为NULL）
- `ai_review_status` - AI审核状态：pending/approved/rejected
- `manual_review_status` - 人工审核状态：pending/approved/rejected

### 3. 文化实体表 (cultural_entities)

**用途：** 存储从资源中提取出的结构化实体信息。

**重要字段：**
- `entity_name` - 实体名称（文化资源的名称）
- `entity_type` - 实体类型（ENUM类型：'人物', '作品', '事件', '地点', '其他'）

### 4. 问答会话表 (qa_sessions)

**用途：** 存储AIGC对话的会话信息。

**重要字段：**
- `user_id` - 用户ID（关联users表）
- `summary` - 会话摘要（自动提取的标题，不超过20字）

### 5. 问答消息表 (qa_messages)

**用途：** 存储AIGC对话的具体消息内容。

**重要字段：**
- `user_id` - 用户ID（关联users表）
- `session_id` - 会话ID（关联qa_sessions表）
- `create_time` - 创建时间
- `user_message` - 用户输入的信息
- `ai_message` - AI的回答
- `model` - 模型类型（'text' 或 'image'，参考qa_sessions表的mode字段）
- `image_url` - 图片URL（文字类型AIGC为null，图片类型AIGC存储生成的图片地址）
- `user_feedback` - 用户反馈（如：评分或评论）
- `timestamp` - 消息发送时间

**表结构说明：**
- 新表结构将用户消息和AI消息分别存储在 `user_message` 和 `ai_message` 字段中
- `model` 字段标识使用的模型类型（文字AIGC使用Tongyi，图片AIGC使用Huoshan）
- `image_url` 字段仅在图片AIGC时存储生成的图片地址

### 6. 标注任务表 (annotation_tasks)

**重要字段：**
- `resource_id` - 关联的资源ID
- `resource_source` - 资源来源表（'cultural_resources' 或 'cultural_resources_from_user'）
- `task_type` - 任务体系（'实体', '质量', '语义'）
- `status` - 任务状态（如：待标注, 待审核, 已完成）

**注意：** 
- `resource_id` 不再有外键约束，而是通过 `resource_source` 字段来标识资源来源
- 如果 `resource_source` 为 `'cultural_resources'`，则 `resource_id` 关联 `cultural_resources.id`
- 如果 `resource_source` 为 `'cultural_resources_from_user'`，则 `resource_id` 关联 `cultural_resources_from_user.id`

## 数据流向

1. **爬虫数据**：
   - 文字数据 → `cultural_resources`（title=节日名称）+ `cultural_entities`（entity_name=资源名称）
   - 图片数据 → `crawled_images`

2. **AIGC生成数据**：
   - 文字数据 → `AIGC_cultural_resources`（title=节日名称）+ `AIGC_cultural_entities`（entity_name=资源名称）
   - 图片数据 → `AIGC_graph`

3. **用户上传数据**：
   - 待审核数据 → `cultural_resources_from_user`
   - 审核通过后 → `cultural_resources`

4. **AIGC对话记录**：
   - 会话信息 → `qa_sessions`
   - 对话消息 → `qa_messages`

5. **标注任务**：
   - 标注任务 → `annotation_tasks`（通过 `resource_source` 字段关联不同的资源表）
   - 标注记录 → `annotation_records`

## 密码加密

系统使用 **SHA-256** 单向哈希算法加密用户密码：
- 密码在存储前进行SHA-256哈希处理
- 登录时对输入的密码进行哈希后与数据库中的哈希值比较
- 安全问题答案同样使用SHA-256加密

**示例：**
- 密码 `123456` 的SHA-256哈希值：`8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92`

## 视图

系统为每个表创建了只读视图，便于统一查询与权限控制：
- `v_users`
- `v_cultural_resources`
- `v_cultural_entities`
- `v_entity_relationships`
- `v_user_behavior_logs`
- `v_qa_sessions`
- `v_qa_messages`
- `v_annotation_tasks`
- `v_annotation_records`
- `v_cultural_resources_from_user`
- `v_AIGC_cultural_resources`
- `v_AIGC_graph`
- `v_crawled_images`
- `v_AIGC_cultural_entities`

## 索引

主要索引包括：
- 主键自动创建聚簇索引
- 外键自动创建索引
- `entity_name`、`entity_type` 等常用查询字段创建了索引
- `source_url` 创建了唯一索引

## 注意事项

1. **数据库字符集**：使用 `utf8mb4` 字符集，支持emoji等特殊字符
2. **时区**：使用服务器本地时区
3. **外键约束**：
   - 大部分外键使用 `ON DELETE CASCADE`（级联删除）
   - `cultural_resources.upload_user_id` 使用 `ON DELETE SET NULL`（用户删除后设为NULL）
4. **数据备份**：建议定期备份数据库
5. **默认管理员密码**：首次登录后请立即修改

## 故障排除

### 数据库连接失败
- 检查MySQL服务是否运行
- 检查环境变量配置是否正确
- 检查数据库用户权限

### 表不存在
- 运行 `database_files/run_init_schema.py` 初始化数据库
- 或手动执行 `database_files/init_schema.sql`

### 外键约束错误
- 检查关联表的数据是否存在
- 确认外键约束配置正确

## 许可证

本项目遵循项目主许可证。
