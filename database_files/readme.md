## 说明

### 数据库初始化

**方式一：使用Python脚本自动初始化（推荐）**
```bash
# 在项目根目录运行
python database_files/run_init_schema.py
```

此脚本会自动：
- 连接到MySQL数据库（使用root账户）
- 执行 `init_schema.sql` 中的所有SQL语句
- 创建所有表、视图、索引和角色
- 创建默认管理员账户（admin/123456）

**方式二：手动执行SQL脚本**
```bash
# 在MySQL客户端中执行
mysql -u root -p < database_files/init_schema.sql
```

### ER图

- `erdiagram.md` 文件包含了完整的、更新的ER图（Mermaid格式），包含所有14个表及其关系
- 可以使用Mermaid工具查看或导出为PNG/SVG格式
- 所有表都包含在ER图中，包括新增的AIGC相关表和爬虫相关表

**更新说明：**
- `erdiagram.md` 文件包含了完整的、更新的ER图（Mermaid格式），包含所有14个表及其关系
- 可以使用Mermaid工具查看或导出为PNG/SVG格式
- 所有表都包含在ER图中，包括新增的AIGC相关表和爬虫相关表

**数据库迁移：**
- 如果已有数据库，需要执行 `migrate_annotation_tasks.sql` 来更新 `annotation_tasks` 表结构
- 该迁移脚本会添加 `resource_source` 字段并移除外键约束，以支持用户上传资源的标注任务

## 表的字段解释

### 1. 文化资源表 (cultural_resources)

**用途：** 存储爬虫抓取或用户上传的原始文化素材。

| 字段名 (Field Name) | 推荐类型 | 描述 | 作用 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 | |
| `title` | `VARCHAR(255)` | 节日（文化资源涉及到的传统节日的名称） |"基础标识字段" |
| `resource_type` | `VARCHAR(50)` | 资源类型（如：文本、图像） |"内容类型字段" |
| `file_format` | `VARCHAR(20)` | 文件格式（如：TXT, JPG） |"内容类型字段" |
| `source_from` | `VARCHAR(255)` | 数据来源（如：网站名称） |"来源信息字段" |
| `source_url` | `TEXT` (Unique) | 原始URL链接 |"来源信息字段" |
| `content_feature_data` | `LONGTEXT` / `JSON` | 存储文本内容或特征向量的引用 |"内容特征字段" |
| `version` | `INT` | 版本号 |"版本管理字段" |
| `created_at` | `TIMESTAMP` | 创建时间 |"基础标识字段" |
| `updated_at` | `TIMESTAMP` | 最后更新时间 |"版本管理字段" |

---

### 2. 文化实体表 (cultural_entities)

**用途：** 存储从资源中提取出的结构化实体信息。

| 字段名 (Field Name) | 推荐类型 | 描述 | 作用 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 | |
| `entity_name` | `VARCHAR(255)` |实体名称（文化资源的名称） |"核心属性" |
| `entity_type` | `VARCHAR(50)` |实体类型（如：人物、作品、事件、地点） |"核心属性" |
| `description` | `TEXT` |描述 |"核心属性" |
| `source` | `TEXT` |来源 |"核心属性" |
| `period_era` | `VARCHAR(100)` |时期年代 |"时空属性" |
| `geo_coordinates` | `POINT` / `VARCHAR(100)`|地理坐标 |"时空属性" |
| `cultural_region` | `VARCHAR(100)` |文化区域 |"时空属性" |
| `style_features` | `TEXT` |风格特征 |"特征属性" |
| `cultural_value` | `TEXT` |文化价值 |"特征属性" |
| `related_images_url` | `TEXT` |相关图像链接 |"扩展属性" |
| `digital_resource_link` | `TEXT` |数字资源链接 |"扩展属性" |

---

### 3. 关系表 (entity_relationships)

**用途：** 存储实体与实体之间的关系，用于构建知识图谱。

| 字段名 (Field Name) | 推荐类型 | 描述 | 作用 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 | |
| `source_entity_id` | `BIGINT` (FK) | 源实体ID (关联 `cultural_entities.id`) | |
| `target_entity_id` | `BIGINT` (FK) | 目标实体ID (关联 `cultural_entities.id`) | |
| `relationship_type` | `VARCHAR(50)` |关系类型（如：创作、影响、时空、相似、组成） |"关系类型体系" |
| `relationship_strength` | `FLOAT` |关系强度 |"关系属性设计" |
| `relationship_evidence` | `TEXT` |关系证据（支撑关系的图像或来源） |"关系属性设计" |
| `spatiotemporal_constraint` | `VARCHAR(255)` |时空约束 |"关系属性设计" |
| `confidence_score` | `FLOAT` |置信度评分 |"关系属性设计" |

---

### 4. 用户表 (users)

**用途：** 存储用户信息和权限。

| 字段名 (Field Name) | 推荐类型 | 描述 | 作用 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 | |
| `username` | `VARCHAR(100)` (Unique) | 用户名 | |
| `password_hash` | `VARCHAR(255)` | 加密后的密码 | |
| `role` | `ENUM('普通用户', '管理员')` |角色（普通用户或系统管理员） |"用户主要分为两类" |
| `created_at` | `TIMESTAMP` | 注册时间 | |

---

### 5. 用户行为日志表 (user_behavior_logs)

**用途：** 追踪用户的各类行为。 

| 字段名 (Field Name) | 推荐类型 | 描述 | 作用 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 | |
| `user_id` | `BIGINT` (FK) | 用户ID (关联 `users.id`) |"对用户的行为进行追踪" |
| `behavior_type` | `ENUM('检索', '交互', '生成', '标注')` |行为类型（检索、交互、生成、标注） |"检索行为、交互行为、生成行为、标注行为" |
| `content` | `TEXT` | 行为内容（如：搜索词、生成提示词） | |
| `timestamp` | `TIMESTAMP` | 行为发生时间 | |

---

### 6. 问答会话表 (qa_sessions)

**用途：** 存储会话信息，用于上下文管理。 

| 字段名 (Field Name) | 推荐类型 | 描述 | 作用 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 | |
| `user_id` | `BIGINT` (FK) | 用户ID (关联 `users.id`) | |
| `created_at` | `TIMESTAMP` | 会话开始时间 | |
| `summary` | `TEXT` | 会话摘要（用于上下文管理） |"对会话进行上下文管理" |

---

### 7. 问答消息表 (qa_messages)

**用途：** 追踪多轮对话的具体内容并收集反馈。 

| 字段名 (Field Name) | 推荐类型 | 描述 | 作用 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 | |
| `session_id` | `BIGINT` (FK) | 会话ID (关联 `qa_sessions.id`) |"对多轮对话进行追踪" |
| `sender` | `ENUM('user', 'ai')` | 发送方（用户或AI） | |
| `message_content` | `TEXT` | 消息内容 | |
| `user_feedback` | `TEXT` / `INT` |用户反馈（如：评分或评论） |"收集用户反馈" |
| `timestamp` | `TIMESTAMP` | 消息发送时间 | |

---

### 8. 标注任务表 (annotation_tasks)

**用途：** 管理标注任务。

| 字段名 (Field Name) | 推荐类型 | 描述 | 作用 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 | |
| `resource_id` | `BIGINT` | 关联的资源ID | |
| `resource_source` | `ENUM('cultural_resources', 'cultural_resources_from_user')` | 资源来源表（cultural_resources或cultural_resources_from_user） | 标识资源来自哪个表 |
| `task_type` | `ENUM('实体', '质量', '语义')` |任务体系（实体、质量、语义） |"标注任务分为几个体系" |
| `annotation_method` | `ENUM('ai', 'manual')` | 标注方式（AI或人工） | |
| `status` | `VARCHAR(20)` | 任务状态（如：待标注, 待审核, 已完成） | |
| `required_annotators` | `INT` | 需要的标注人数 |"多人标注机制"  |

**注意：** 
- `resource_id` 不再有外键约束，而是通过 `resource_source` 字段来标识资源来源
- 如果 `resource_source` 为 `'cultural_resources'`，则 `resource_id` 关联 `cultural_resources.id`
- 如果 `resource_source` 为 `'cultural_resources_from_user'`，则 `resource_id` 关联 `cultural_resources_from_user.id`

---

### 9. 标注记录表 (annotation_records)

**用途：** 存储每条具体的标注结果，支持多人标注和专家审核。 

| 字段名 (Field Name) | 推荐类型 | 描述 | 作用 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 | |
| `task_id` | `BIGINT` (FK) | 任务ID (关联 `annotation_tasks.id`) | |
| `annotator_id` | `BIGINT` (FK) | 标注者ID (关联 `users.id`) |"多人标注机制" |
| `annotation_data` | `JSON` / `TEXT` | 标注的具体内容 | |
| `is_expert_reviewed` | `BOOLEAN` | 是否经过专家审核 |"引入专家审核流程" |
| `reviewer_id` | `BIGINT` (FK) | 审核专家ID (关联 `users.id`) |"引入专家审核流程" |
| `created_at` | `TIMESTAMP` | 标注提交时间 | |


### 10. 用户上传资源表 (cultural_resources_from_user)

**用途：** 存储用户上传、等待审核的内容。

| 字段名 (Field Name) | 推荐类型 | 描述 |
| :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 |
| `user_id` | `BIGINT` (FK) | 上传用户ID (关联 `users.id`) |
| `title` | `VARCHAR(255)` | 节日（文化资源涉及到的传统节日的名称） |
| `resource_type` | `VARCHAR(50)` | 资源类型（如：文本、图像） |
| `file_format` | `VARCHAR(20)` | 文件格式（如：TXT, JPG） |
| `content_feature_data` | `LONGTEXT` | 存储文本内容或特征向量的引用 |
| `content_hash` | `VARCHAR(64)` | 内容的SHA-256哈希，用于快速查重 |
| `ai_review_status` | `ENUM('pending', 'passed', 'failed')` | AI审核状态 |
| `manual_review_status` | `ENUM('pending', 'passed', 'failed')` | 人工审核状态 |
| `upload_time` | `TIMESTAMP` | 上传时间 |
| `review_notes` | `TEXT` | 审核备注（例如：未通过原因） |

---

### 11. AIGC文化资源表 (AIGC_cultural_resources)

**用途：** 专门存储由AIGC生成的文化资源，结构与主资源表一致。

| 字段名 (Field Name) | 推荐类型 | 描述 |
| :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 |
| `title` | `VARCHAR(255)` | 节日（文化资源涉及到的传统节日的名称） |
| `resource_type` | `VARCHAR(50)` | 资源类型（如：文本、图像） |
| `file_format` | `VARCHAR(20)` | 文件格式（如：TXT, JPG） |
| `source_from` | `VARCHAR(255)` | 数据来源（例如：AIGC模型名称） |
| `source_url` | `TEXT` | 原始URL链接 (如果适用) |
| `content_feature_data` | `LONGTEXT` | 存储文本内容或特征向量的引用 |
| `version` | `INT` | 版本号 |
| `created_at` | `TIMESTAMP` | 创建时间 |
| `updated_at` | `TIMESTAMP` | 最后更新时间 |

---

### 12. AIGC生成图像表 (AIGC_graph)

**用途：** 存储AIGC生成的图像的元数据。

| 字段名 (Field Name) | 推荐类型 | 描述 |
| :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 |
| `file_name` | `VARCHAR(255)` | 文件名 |
| `storage_path` | `VARCHAR(767)` (Unique) | 存储路径 (已调整长度以兼容索引) |
| `dimensions` | `VARCHAR(50)` | 尺寸 (例如: 1024x1024) |
| `upload_time` | `TIMESTAMP` | 上传时间 |
| `tags` | `JSON` | 标签 (JSON数组格式) |

---

### 13. 爬虫抓取图像表 (crawled_images)

**用途：** 存储爬虫抓取的图像元数据。

| 字段名 (Field Name) | 推荐类型 | 描述 |
| :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 |
| `file_name` | `VARCHAR(255)` | 文件名 |
| `storage_path` | `VARCHAR(767)` (Unique) | 存储路径 (已调整长度以兼容索引) |
| `dimensions` | `VARCHAR(50)` | 尺寸 (例如: 1024x1024) |
| `crawl_time` | `TIMESTAMP` | 抓取时间 |
| `tags` | `JSON` | 标签 (JSON数组格式) |

---

### 14. AIGC文化实体表 (AIGC_cultural_entities)

**用途：** 存储AIGC生成的文化实体信息，结构与cultural_entities表一致。

| 字段名 (Field Name) | 推荐类型 | 描述 |
| :--- | :--- | :--- |
| `id` | `BIGINT` (PK) | 唯一主键 |
| `entity_name` | `VARCHAR(255)` | 实体名称（文化资源的名称） |
| `entity_type` | `VARCHAR(50)` | 实体类型（如：人物、作品、事件、地点） |
| `description` | `TEXT` | 描述 |
| `source` | `TEXT` | 来源 |
| `period_era` | `VARCHAR(100)` | 时期年代 |
| `geo_coordinates` | `VARCHAR(100)` | 地理坐标 |
| `cultural_region` | `VARCHAR(100)` | 文化区域 |
| `style_features` | `TEXT` | 风格特征 |
| `cultural_value` | `TEXT` | 文化价值 |
| `related_images_url` | `TEXT` | 相关图像链接 |
| `digital_resource_link` | `TEXT` | 数字资源链接 |

---

## 重要字段说明

### cultural_resources 和 AIGC_cultural_resources 表
- **`title`字段**：存储**节日名称**（文化资源涉及到的传统节日的名称）
- 例如：如果资源是关于"春节"的，title字段存储"春节"

### cultural_entities 和 AIGC_cultural_entities 表
- **`entity_name`字段**：存储**文化资源名称**（即资源本身的名称）
- 例如：如果资源标题是"春节习俗介绍"，entity_name字段存储"春节习俗介绍"

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