# 数据库ER图

本文档使用Mermaid格式描述数据库的实体关系图。

## ER图（Mermaid格式）

```mermaid
erDiagram
    %% 用户相关表
    users {
        BIGINT id PK
        VARCHAR account UK "用户账号（8-10位数字，系统自动生成）"
        VARCHAR password_hash
        ENUM role
        VARCHAR nickname "用户昵称（可修改）"
        VARCHAR avatar_path
        VARCHAR security_question
        VARCHAR security_answer_hash
        TIMESTAMP created_at
    }
    
    %% 文化资源相关表
    cultural_resources {
        BIGINT id PK
        VARCHAR title "节日（文化资源涉及到的传统节日的名称）"
        VARCHAR resource_type
        VARCHAR file_format
        VARCHAR source_from
        TEXT source_url
        LONGTEXT content_feature_data
        INT version
        TIMESTAMP created_at
        TIMESTAMP updated_at
        BIGINT upload_user_id FK
        VARCHAR ai_review_status
        TEXT ai_review_remark
        VARCHAR manual_review_status
        TEXT manual_review_remark
        DATETIME upload_time
    }
    
    cultural_entities {
        BIGINT id PK
        VARCHAR entity_name "实体名称（文化资源的名称）"
        VARCHAR entity_type
        TEXT description
        TEXT source
        VARCHAR period_era
        VARCHAR geo_coordinates
        VARCHAR cultural_region
        TEXT style_features
        TEXT cultural_value
        TEXT related_images_url
        TEXT digital_resource_link
    }
    
    entity_relationships {
        BIGINT id PK
        BIGINT source_entity_id FK
        BIGINT target_entity_id FK
        VARCHAR relationship_type
        FLOAT relationship_strength
        TEXT relationship_evidence
        VARCHAR spatiotemporal_constraint
        FLOAT confidence_score
    }
    
    %% 用户行为相关表
    user_behavior_logs {
        BIGINT id PK
        BIGINT user_id FK
        ENUM behavior_type
        TEXT content
        TIMESTAMP timestamp
    }
    
    qa_sessions {
        BIGINT id PK
        BIGINT user_id FK
        TIMESTAMP created_at
        TEXT summary
    }
    
    qa_messages {
        BIGINT id PK
        BIGINT user_id FK
        BIGINT session_id FK
        DATETIME create_time
        TEXT user_message
        TEXT ai_message
        TEXT user_feedback
        TIMESTAMP timestamp
        ENUM model
        VARCHAR image_url
    }
    
    %% 标注相关表
    annotation_tasks {
        BIGINT id PK
        BIGINT resource_id FK
        ENUM task_type
        ENUM annotation_method
        VARCHAR status
        INT required_annotators
    }
    
    annotation_records {
        BIGINT id PK
        BIGINT task_id FK
        BIGINT annotator_id FK
        JSON annotation_data
        ENUM annotation_source
        BOOLEAN is_expert_reviewed
        BIGINT reviewer_id FK
        TIMESTAMP created_at
        TINYINT is_latest
        DATETIME create_time
        VARCHAR entity_name
        ENUM entity_type
        TEXT description
        TEXT source
        VARCHAR period_era
        VARCHAR geo_coordinates
        VARCHAR cultural_region
        TEXT style_features
        TEXT cultural_value
        TEXT related_images_url
        TEXT digital_resource_link
    }
    
    %% 用户上传资源表
    cultural_resources_from_user {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR title
        VARCHAR resource_type
        VARCHAR file_format
        LONGTEXT content_feature_data
        VARCHAR content_hash UK
        ENUM ai_review_status
        ENUM manual_review_status
        TIMESTAMP upload_time
        TEXT review_notes
    }
    
    %% AIGC相关表
    AIGC_cultural_resources {
        BIGINT id PK
        VARCHAR title "节日（文化资源涉及到的传统节日的名称）"
        VARCHAR resource_type
        VARCHAR file_format
        VARCHAR source_from
        TEXT source_url
        LONGTEXT content_feature_data
        INT version
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }
    
    AIGC_cultural_entities {
        BIGINT id PK
        VARCHAR entity_name "实体名称（文化资源的名称）"
        VARCHAR entity_type
        TEXT description
        TEXT source
        VARCHAR period_era
        VARCHAR geo_coordinates
        VARCHAR cultural_region
        TEXT style_features
        TEXT cultural_value
        TEXT related_images_url
        TEXT digital_resource_link
    }
    
    AIGC_graph {
        BIGINT id PK
        VARCHAR file_name
        VARCHAR storage_path UK
        VARCHAR dimensions
        TIMESTAMP upload_time
        JSON tags
    }
    
    %% 爬虫相关表
    crawled_images {
        BIGINT id PK
        VARCHAR file_name
        VARCHAR storage_path UK
        VARCHAR dimensions
        TIMESTAMP crawl_time
        JSON tags
    }
    
    %% 用户评分和评论相关表
    user_ratings {
        BIGINT id PK
        BIGINT resource_id FK
        BIGINT user_id FK
        TINYINT rating
        VARCHAR rating_dimension
        TIMESTAMP rated_at
    }
    
    user_comments {
        BIGINT id PK
        BIGINT resource_id FK
        BIGINT user_id FK
        TEXT comment_content
        VARCHAR comment_status
        TINYINT is_academic_discussion
        BIGINT reviewer_id FK
        TIMESTAMP reviewed_at
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }
    
    comment_replies {
        BIGINT id PK
        BIGINT comment_id FK
        BIGINT reply_user_id FK
        TEXT reply_content
        TIMESTAMP created_at
    }
    
    %% 关系定义
    users ||--o{ cultural_resources : "上传"
    users ||--o{ user_behavior_logs : "产生"
    users ||--o{ qa_sessions : "创建"
    users ||--o{ cultural_resources_from_user : "上传"
    users ||--o{ annotation_records : "标注"
    users ||--o{ annotation_records : "审核"
    users ||--o{ user_ratings : "评分"
    users ||--o{ user_comments : "评论"
    users ||--o{ user_comments : "审核"
    users ||--o{ comment_replies : "回复"
    
    cultural_resources ||--o{ annotation_tasks : "关联"
    cultural_resources ||--o{ cultural_entities : "提取"
    cultural_resources ||--o{ user_ratings : "被评分"
    cultural_resources ||--o{ user_comments : "被评论"
    
    user_comments ||--o{ comment_replies : "被回复"
    
    cultural_entities ||--o{ entity_relationships : "构建关系"
    entity_relationships }o--|| cultural_entities : "源实体"
    entity_relationships }o--|| cultural_entities : "目标实体"
    
    qa_sessions ||--o{ qa_messages : "包含"
    
    annotation_tasks ||--o{ annotation_records : "包含"
    
    %% AIGC表的关系（逻辑关系，无外键）
    AIGC_cultural_resources ||--o{ AIGC_cultural_entities : "提取"
```

## 表说明

### 核心表

1. **users** - 用户表
   - 存储系统用户信息（管理员和普通用户）

2. **cultural_resources** - 文化资源表
   - 存储爬虫抓取或用户上传的原始文化素材
   - `title`字段：节日名称（文化资源涉及到的传统节日的名称）

3. **cultural_entities** - 文化实体表
   - 存储从资源中提取出的结构化实体信息
   - `entity_name`字段：实体名称（文化资源的名称）

4. **entity_relationships** - 实体关系表
   - 存储实体与实体之间的关系，用于构建知识图谱

### 用户行为表

5. **user_behavior_logs** - 用户行为日志表
   - 追踪用户的各类行为（检索、交互、生成、标注）

6. **qa_sessions** - 问答会话表
   - 存储AIGC过程中多轮对话的会话信息

7. **qa_messages** - 问答消息表
   - 追踪多轮对话的具体内容并收集反馈
   - 新表结构包含：user_id, user_message, ai_message, model, image_url 等字段
   - model字段标识使用的模型类型（'text' 或 'image'）
   - image_url字段仅在图片AIGC时存储生成的图片地址

### 标注相关表

8. **annotation_tasks** - 标注任务表
   - 管理标注任务

9. **annotation_records** - 标注记录表
   - 存储每条具体的标注结果，支持多人标注和专家审核

### 用户上传表

10. **cultural_resources_from_user** - 用户上传资源表
    - 用于存储用户上传、等待审核的内容

### AIGC相关表

11. **AIGC_cultural_resources** - AIGC文化资源表
    - 专门存储由AIGC生成的文化资源
    - `title`字段：节日名称（文化资源涉及到的传统节日的名称）

12. **AIGC_cultural_entities** - AIGC文化实体表
    - 存储AIGC生成的文化实体信息
    - `entity_name`字段：实体名称（文化资源的名称）

13. **AIGC_graph** - AIGC生成图像表
    - 存储AIGC生成的图像的元数据

### 爬虫相关表

14. **crawled_images** - 爬虫抓取图像表
    - 存储爬虫抓取的图像元数据

### 用户评分和评论相关表

15. **user_ratings** - 用户评分表
    - 存储用户对文化资源的评分数据
    - 支持多维度评分（综合、准确性、实用性、完整性）

16. **user_comments** - 用户评论表
    - 存储用户对文化资源的评论数据
    - 支持评论审核和学术讨论标记

17. **comment_replies** - 评论回复表
    - 存储用户对评论的回复数据

## 重要说明

1. **字段含义**：
   - `cultural_resources.title` 和 `AIGC_cultural_resources.title`：存储**节日名称**（文化资源涉及到的传统节日的名称）
   - `cultural_entities.entity_name` 和 `AIGC_cultural_entities.entity_name`：存储**文化资源名称**

2. **数据流向**：
   - 爬虫数据 → `cultural_resources` + `cultural_entities` + `crawled_images`
   - AIGC生成数据 → `AIGC_cultural_resources` + `AIGC_cultural_entities` + `AIGC_graph`
   - 用户上传数据 → `cultural_resources_from_user` → 审核通过后 → `cultural_resources`

3. **AIGC对话记录**：
   - `qa_sessions` 和 `qa_messages` 用于存储AIGC过程中的多轮对话记录

## 视图

所有表都创建了对应的只读视图（v_表名），便于统一查询与权限控制。

## 使用方法

1. **在线查看**：将Mermaid代码复制到 [Mermaid Live Editor](https://mermaid.live/) 查看
2. **Markdown渲染**：在支持Mermaid的Markdown查看器中查看（如GitHub、GitLab等）
3. **导出图片**：使用Mermaid工具导出为PNG/SVG格式

