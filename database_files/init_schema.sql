-- --------------------------------------------------
-- init_schema.sql
-- java_project的数据库初始化脚本
-- 包含所有表结构定义和初始化数据
-- 数据库类型: MySQL
-- 
-- 使用说明：
-- 1. 直接执行此脚本创建全新数据库
-- 2. 或使用 Python 脚本：python database_files/run_init_schema.py
-- 
-- 注意：此脚本会创建全新数据库，如果数据库已存在，会保留现有数据
-- --------------------------------------------------

-- 创建数据库java_project（如果不存在）
CREATE DATABASE IF NOT EXISTS java_project CHARACTER SET utf8mb4;

-- 切换到该数据库
USE java_project;



-- 设置字符集
SET NAMES utf8mb4;



   
-- --------------------------------------------------
-- 1. 用户表 (users)
-- 存储用户信息和权限 
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `account` VARCHAR(20) UNIQUE NOT NULL COMMENT '用户账号（8-10位数字，系统自动生成，永久不可修改）',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '加密后的密码',
  `role` ENUM('普通用户', '管理员', '超级管理员') NOT NULL DEFAULT '普通用户' COMMENT '角色（普通用户、系统管理员或超级管理员）',
  `nickname` VARCHAR(100) COMMENT '用户昵称（可修改）',
  `signature` VARCHAR(500) COMMENT '个人签名（可修改）',
  `avatar_path` VARCHAR(255) DEFAULT '/default.jpg' COMMENT '头像路径（存储在public文件夹，格式：/账号.jpg 或 /default.jpg）',
  `security_question` VARCHAR(255) COMMENT '自定义安全问题（用于找回密码）',
  `security_answer_hash` VARCHAR(255) COMMENT '安全问题的答案（哈希值）',
  `is_online` TINYINT(1) DEFAULT 0 COMMENT '是否在线（0：离线，1：在线）',
  `last_active_time` TIMESTAMP NULL DEFAULT NULL COMMENT '最后活跃时间',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  INDEX `idx_account` (`account`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';





-- --------------------------------------------------
-- 2. 文化资源表 (cultural_resources)
-- 存储爬虫抓取或用户上传的原始文化素材。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `cultural_resources` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `title` VARCHAR(255) COMMENT '节日（文化资源涉及到的传统节日的名称）',
  `resource_type` VARCHAR(50) COMMENT '资源类型（文本、图像、视频、数据态资源、虚拟展示资源等。数据态资源：用于AI分析的原始数据集；虚拟展示资源：全景图像、3D模型文件等）',
  `file_format` VARCHAR(20) COMMENT '文件格式（如：TXT, JPG, MP4, OBJ, GLB等）',
  `source_from` VARCHAR(255) COMMENT '数据来源（如：网站名称）',
  `source_url` TEXT COMMENT '原始URL链接',
  `content_feature_data` LONGTEXT COMMENT '存储用于知识图谱构建的实体向量或AI提取的语义特征（数据赋能）',
  `version` INT DEFAULT 1 COMMENT '版本号',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  `upload_user_id` BIGINT COMMENT '上传用户ID（关联users表，用户删除后设为NULL）',
  `ai_review_status` VARCHAR(20) DEFAULT 'pending' COMMENT 'AI审核状态：pending-待审核/approved-通过/rejected-驳回',
  `ai_review_remark` TEXT COMMENT 'AI审核备注',
  `manual_review_status` VARCHAR(20) DEFAULT 'pending' COMMENT '人工审核状态：pending-待审核/approved-通过/rejected-驳回',
  `manual_review_remark` TEXT COMMENT '人工审核备注',
  `upload_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  UNIQUE KEY `uk_source_url` (`source_url`(255)) COMMENT 'URL唯一索引',
  CONSTRAINT `fk_cr_upload_user` FOREIGN KEY (`upload_user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文化资源表';





-- --------------------------------------------------
-- 3. 文化实体表 (cultural_entities)
-- 存储从资源中提取出的结构化实体信息。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `cultural_entities` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `entity_name` VARCHAR(255) NOT NULL COMMENT '实体名称（文化资源的名称）',
  `entity_type` ENUM('人物', '作品', '事件', '地点', '其他') DEFAULT '其他' COMMENT '实体类型（人物、作品、事件、地点、其他）',
  `description` TEXT COMMENT '描述',
  `source` TEXT COMMENT '来源',
  `period_era` VARCHAR(100) COMMENT '时期年代',
  `geo_coordinates` VARCHAR(100) COMMENT '地理坐标',
  `cultural_region` VARCHAR(100) COMMENT '文化区域',
  `style_features` TEXT COMMENT '风格特征',
  `cultural_value` TEXT COMMENT '文化价值',
  `related_images_url` TEXT COMMENT '相关图像链接',
  `digital_resource_link` TEXT COMMENT '数字资源链接',
  INDEX `idx_entity_name` (`entity_name`),
  INDEX `idx_entity_type` (`entity_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文化实体表';

-- 为cultural_entities表添加全文索引（如果不存在）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'cultural_entities' 
    AND INDEX_NAME = 'idx_ce_search'
);
SET @sql = IF(@index_exists = 0,
    'ALTER TABLE `cultural_entities` ADD FULLTEXT INDEX `idx_ce_search` (`entity_name`, `description`) WITH PARSER ngram',
    'SELECT "idx_ce_search索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;



-- --------------------------------------------------
-- 4. 关系表 (entity_relationships)
-- 存储实体与实体之间的关系，用于构建知识图谱。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `entity_relationships` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `source_entity_id` BIGINT NOT NULL COMMENT '源实体ID',
  `target_entity_id` BIGINT NOT NULL COMMENT '目标实体ID',
  `relationship_type` VARCHAR(50) NOT NULL COMMENT '关系类型（创作、影响、位于、包含、参与、相似、继承、引用、公布）',
  `cidoc_property_id` VARCHAR(10) COMMENT 'CIDOC-CRM标准属性代码（如P14, P15, P53, P46, P11, P130, P127, P67, P70等），用于标准化关系类型',
  `relationship_strength` FLOAT COMMENT '关系强度',
  `relationship_evidence` TEXT COMMENT '关系证据（支撑关系的图像或来源）',
  `spatiotemporal_constraint` VARCHAR(255) COMMENT '时空约束',
  `confidence_score` FLOAT COMMENT '置信度评分',
  FOREIGN KEY (`source_entity_id`) REFERENCES `cultural_entities`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`target_entity_id`) REFERENCES `cultural_entities`(`id`) ON DELETE CASCADE,
  INDEX `idx_source_entity` (`source_entity_id`),
  INDEX `idx_target_entity` (`target_entity_id`),
  INDEX `idx_relationship_type` (`relationship_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实体关系表';





-- --------------------------------------------------
-- 5. 用户行为日志表 (user_behavior_logs)
-- 追踪用户的各类行为。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_behavior_logs` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `user_id` BIGINT NOT NULL COMMENT '用户ID',
  `behavior_type` ENUM('检索', '交互', '生成', '标注') COMMENT '行为类型（检索、交互、生成、标注）',
  `content` TEXT COMMENT '行为内容（如：搜索词、生成提示词）',
  `timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '行为发生时间',
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  INDEX `idx_user` (`user_id`),
  INDEX `idx_behavior_type` (`behavior_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户行为日志表';





-- --------------------------------------------------
-- 6. 问答会话表 (qa_sessions)
-- 存储会话信息，用于上下文管理。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `qa_sessions` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `user_id` BIGINT NOT NULL COMMENT '用户ID',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '会话开始时间',
  `summary` TEXT COMMENT '会话摘要（用于上下文管理）',
  `mode` ENUM('text', 'image') DEFAULT 'text' COMMENT '会话模式（text或image）',
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_mode` (`mode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='问答会话表';





-- --------------------------------------------------
-- 7. 问答消息表 (qa_messages)
-- 追踪多轮对话的具体内容并收集反馈。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `qa_messages` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `user_id` BIGINT NOT NULL COMMENT '用户ID',
  `session_id` BIGINT NOT NULL COMMENT '会话ID',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `user_message` TEXT COMMENT '用户输入的信息',
  `ai_message` TEXT COMMENT 'AI的回答',
  `user_feedback` TEXT COMMENT '用户反馈（如：评分或评论）',
  `timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '消息发送时间',
  `model` ENUM('text', 'image') DEFAULT 'text' COMMENT '模型类型（text或image，参考qa_sessions表的mode字段）',
  `image_url` VARCHAR(500) COMMENT '图片URL（文字类型AIGC为null，图片类型AIGC存储生成的图片地址）',
  `image_from_users_url` VARCHAR(500) COMMENT '用户上传的图片URL（存储在image_from_users文件夹中）',
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`session_id`) REFERENCES `qa_sessions`(`id`) ON DELETE CASCADE,
  INDEX `idx_session` (`session_id`),
  INDEX `idx_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='问答消息表';





-- --------------------------------------------------
-- 8. 标注任务表 (annotation_tasks)
-- 管理标注任务。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `annotation_tasks` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `resource_id` BIGINT COMMENT '关联的资源ID',
  `resource_source` ENUM('cultural_resources', 'cultural_resources_from_user', 'AIGC_cultural_resources') DEFAULT 'cultural_resources' COMMENT '资源来源表（cultural_resources、cultural_resources_from_user或AIGC_cultural_resources）',
  `task_type` ENUM('实体', '质量', '语义') COMMENT '任务体系（实体、质量、语义）',
  `annotation_method` ENUM('ai', 'manual') DEFAULT 'ai' COMMENT '标注方式',
  `status` VARCHAR(20) DEFAULT '待标注' COMMENT '任务状态（待标注、AI标注中、AI标注完成、已完成）',
  `required_annotators` INT DEFAULT 1 COMMENT '需要的标注人数',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '任务创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '任务更新时间',
  INDEX `idx_resource` (`resource_id`),
  INDEX `idx_status` (`status`),
  INDEX `idx_resource_source` (`resource_source`),
  INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标注任务表';





-- --------------------------------------------------
-- 9. 标注记录表 (annotation_records)
-- 存储每条具体的标注结果，支持多人标注和专家审核。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `annotation_records` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `task_id` BIGINT NOT NULL COMMENT '任务ID',
  `annotator_id` BIGINT NOT NULL COMMENT '标注者ID',
  `annotation_data` JSON COMMENT '标注的具体内容',
  `annotation_source` ENUM('ai', 'manual') DEFAULT 'manual' COMMENT '标注来源',
  `is_expert_reviewed` BOOLEAN DEFAULT FALSE COMMENT '是否经过专家审核',
  `reviewer_id` BIGINT COMMENT '审核专家ID',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '标注提交时间',
  `is_latest` TINYINT(1) DEFAULT 1 COMMENT '是否为最新标注结果：1-是/0-否',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '标注时间',
  -- 扁平化字段（对应 cultural_entities 的结构标准）
  `entity_name` VARCHAR(255) COMMENT '实体名称（标注结果，对应 cultural_entities.entity_name）',
  `entity_type` ENUM('人物', '作品', '事件', '地点', '其他') DEFAULT '其他' COMMENT '实体类型（标注结果）',
  `description` TEXT COMMENT '描述（标注结果）',
  `source` TEXT COMMENT '来源（标注结果）',
  `period_era` VARCHAR(100) COMMENT '时期年代（标注结果）',
  `geo_coordinates` VARCHAR(100) COMMENT '地理坐标（标注结果）',
  `cultural_region` VARCHAR(100) COMMENT '文化区域（标注结果）',
  `style_features` TEXT COMMENT '风格特征（标注结果）',
  `cultural_value` TEXT COMMENT '文化价值（标注结果）',
  `related_images_url` TEXT COMMENT '相关图像链接（标注结果）',
  `digital_resource_link` TEXT COMMENT '数字资源链接（标注结果）',
  FOREIGN KEY (`task_id`) REFERENCES `annotation_tasks`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`annotator_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`reviewer_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
  INDEX `idx_task` (`task_id`),
  INDEX `idx_annotator` (`annotator_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标注记录表';





-- --------------------------------------------------
-- 10. 用户上传资源表 (cultural_resources_from_user)
-- 用于存储用户上传、等待审核的内容
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `cultural_resources_from_user` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `user_id` BIGINT NOT NULL COMMENT '上传用户ID',
  `title` VARCHAR(255) COMMENT '节日（文化资源涉及到的传统节日的名称）',
  `resource_type` VARCHAR(50) COMMENT '资源类型（文本、图像、视频、数据态资源、虚拟展示资源等。数据态资源：用于AI分析的原始数据集；虚拟展示资源：全景图像、3D模型文件等）',
  `file_format` VARCHAR(20) COMMENT '文件格式（如：TXT, JPG, MP4, OBJ, GLB等）',
  `content_feature_data` LONGTEXT COMMENT '存储用于知识图谱构建的实体向量或AI提取的语义特征（数据赋能），包含文件路径、文本内容等信息',
  `content_hash` VARCHAR(64) COMMENT '内容的SHA-256哈希，用于快速查重',
  `storage_path` VARCHAR(767) COMMENT '文件存储路径（相对于项目根目录，如uploads/xxx.jpg）',
  `ai_review_status` ENUM('pending', 'passed', 'failed') NOT NULL DEFAULT 'pending' COMMENT 'AI审核状态',
  `manual_review_status` ENUM('pending', 'passed', 'failed') NOT NULL DEFAULT 'pending' COMMENT '人工审核状态',
  `upload_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  `review_notes` TEXT COMMENT '审核备注（例如：未通过原因）',
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_content_hash` (`content_hash`) COMMENT '哈希唯一索引，防止重复上传',
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_upload_time` (`upload_time`),
  INDEX `idx_storage_path` (`storage_path`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户上传资源待审表';





-- --------------------------------------------------
-- 11. AIGC文化资源表 (AIGC_cultural_resources)
-- 专门存储由AIGC生成的文化资源，结构与主资源表一致
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `AIGC_cultural_resources` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `title` VARCHAR(255) COMMENT '节日（文化资源涉及到的传统节日的名称）',
  `resource_type` VARCHAR(50) COMMENT '资源类型（文本、图像、视频、数据态资源、虚拟展示资源等。数据态资源：用于AI分析的原始数据集；虚拟展示资源：全景图像、3D模型文件等）',
  `file_format` VARCHAR(20) COMMENT '文件格式（如：TXT, JPG, MP4, OBJ, GLB等）',
  `source_from` VARCHAR(255) COMMENT '数据来源（例如：AIGC模型名称）',
  `source_url` TEXT COMMENT '原始URL链接 (如果适用)',
  `content_feature_data` LONGTEXT COMMENT '存储用于知识图谱构建的实体向量或AI提取的语义特征（数据赋能），包含文件路径、文本内容等信息',
  `storage_path` VARCHAR(767) COMMENT '文件存储路径（相对于项目根目录，如AIGC_graph/xxx.jpg）',
  `retrieved_resource_ids` TEXT COMMENT '检索到的资源ID列表（英文逗号分隔，用于持久化显示检索结果）',
  `version` INT DEFAULT 1 COMMENT '版本号',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  INDEX `idx_storage_path` (`storage_path`),
  INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AIGC生成的文化资源表';





-- --------------------------------------------------
-- 12. AIGC生成图像表 (AIGC_graph)
-- 存储AIGC生成的图像的元数据
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `AIGC_graph` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `file_name` VARCHAR(255) NOT NULL COMMENT '文件名',
  `storage_path` VARCHAR(767) NOT NULL UNIQUE COMMENT '存储路径',
  `dimensions` VARCHAR(50) COMMENT '尺寸 (例如: 1024x1024)',
  `upload_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  `tags` JSON COMMENT '标签 (JSON数组格式, e.g., ["风景", "水墨画"])'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AIGC生成图像元数据表';





-- --------------------------------------------------
-- 13. 爬虫抓取图像表 (crawled_images)
-- 存储爬虫抓取的图像元数据
-- 注意：storage_path不设置UNIQUE约束，因为多个资源可能共享default.jpg
-- 实际爬取的图片通过递增序号保证路径唯一性（如crawled_images/1.jpg, crawled_images/2.jpg等）
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `crawled_images` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `file_name` VARCHAR(255) NOT NULL COMMENT '文件名',
  `storage_path` VARCHAR(767) NOT NULL COMMENT '存储路径（实际图片如crawled_images/1.jpg，默认图片为FrontEnd/public/default.jpg）',
  `dimensions` VARCHAR(50) COMMENT '尺寸 (例如: 1024x1024)',
  `crawl_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '抓取时间',
  `tags` JSON COMMENT '标签 (使用JSON数组格式, e.g., ["京剧", "脸谱"])',
  `resource_id` BIGINT COMMENT '关联的文化资源ID（对应cultural_resources表id，如果该图片属于某个文字资源）',
  `entity_id` BIGINT COMMENT '关联的文化实体ID（对应cultural_entities表id，如果该图片属于某个文化实体）',
  `festival_name` VARCHAR(255) COMMENT '关联的节日名称（中文，用于快速查询和关联）',
  INDEX `idx_resource_id` (`resource_id`),
  INDEX `idx_entity_id` (`entity_id`),
  INDEX `idx_festival_name` (`festival_name`),
  INDEX `idx_storage_path` (`storage_path`),
  CONSTRAINT `fk_ci_resource` FOREIGN KEY (`resource_id`) REFERENCES `cultural_resources`(`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_ci_entity` FOREIGN KEY (`entity_id`) REFERENCES `cultural_entities`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='爬虫抓取图像元数据表';





-- --------------------------------------------------
-- 14. AIGC文化实体表 (AIGC_cultural_entities)
-- 存储AIGC生成的文化实体信息，结构与cultural_entities表一致
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `AIGC_cultural_entities` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `entity_name` VARCHAR(255) NOT NULL COMMENT '实体名称（文化资源的名称）',
  `entity_type` ENUM('人物', '作品', '事件', '地点', '其他') DEFAULT '其他' COMMENT '实体类型（人物、作品、事件、地点、其他）',
  `description` TEXT COMMENT '描述',
  `source` TEXT COMMENT '来源',
  `period_era` VARCHAR(100) COMMENT '时期年代',
  `geo_coordinates` VARCHAR(100) COMMENT '地理坐标',
  `cultural_region` VARCHAR(100) COMMENT '文化区域',
  `style_features` TEXT COMMENT '风格特征',
  `cultural_value` TEXT COMMENT '文化价值',
  `related_images_url` TEXT COMMENT '相关图像链接',
  `digital_resource_link` TEXT COMMENT '数字资源链接',
  INDEX `idx_entity_name` (`entity_name`),
  INDEX `idx_entity_type` (`entity_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AIGC生成的文化实体表';


-- 为AIGC_cultural_entities表添加全文索引（如果不存在）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'AIGC_cultural_entities' 
    AND INDEX_NAME = 'idx_ace_search'
);
SET @sql = IF(@index_exists = 0,
    'ALTER TABLE `AIGC_cultural_entities` ADD FULLTEXT INDEX `idx_ace_search` (`entity_name`, `description`) WITH PARSER ngram',
    'SELECT "idx_ace_search索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;


-- --------------------------------------------------
-- 15. 用户评分表 (user_ratings)
-- 存储用户对文化资源的评分数据
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_ratings` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `resource_id` BIGINT NOT NULL COMMENT '关联文化资源ID（对应cultural_resources表id）',
  `user_id` BIGINT NOT NULL COMMENT '关联用户ID（对应users表id）',
  `rating` TINYINT NOT NULL COMMENT '评分（1-5分，5分为最佳）',
  `rating_dimension` VARCHAR(50) DEFAULT 'overall' COMMENT '评分维度（overall：综合评分，accuracy：内容准确性，usefulness：实用性，completeness：完整性）',
  `rated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '评分时间',
  -- 唯一约束：同一用户对同一资源的同一维度只能评一次
  UNIQUE KEY `uk_user_resource_dimension` (`user_id`, `resource_id`, `rating_dimension`),
  -- 外键关联，删除资源/用户时级联删除评分
  FOREIGN KEY (`resource_id`) REFERENCES `cultural_resources`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  -- 索引优化查询
  INDEX `idx_resource_id` (`resource_id`),
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_rating` (`rating`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户评分表';

-- --------------------------------------------------
-- 16. 用户评论表 (user_comments)
-- 存储用户对文化资源的评论数据
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_comments` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `resource_id` BIGINT NOT NULL COMMENT '关联文化资源ID（对应cultural_resources表id）',
  `user_id` BIGINT NOT NULL COMMENT '关联用户ID（对应users表id）',
  `comment_content` TEXT NOT NULL COMMENT '评论内容',
  `comment_status` VARCHAR(20) DEFAULT 'approved' COMMENT '评论状态（pending：待审核，approved：已通过，rejected：已驳回）',
  `is_academic_discussion` TINYINT DEFAULT 0 COMMENT '是否学术讨论（0：否，1：是）',
  `reviewer_id` BIGINT NULL COMMENT '审核人ID（关联users表id，管理员）',
  `reviewed_at` TIMESTAMP NULL COMMENT '审核时间',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '评论创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '评论更新时间',
  -- 外键关联，删除资源/用户时级联删除评论
  FOREIGN KEY (`resource_id`) REFERENCES `cultural_resources`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`reviewer_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
  -- 索引优化查询
  INDEX `idx_resource_id` (`resource_id`),
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_comment_status` (`comment_status`),
  INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户评论表';

-- --------------------------------------------------
-- 17. 评论回复表 (comment_replies)
-- 存储用户对评论的回复数据
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `comment_replies` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `comment_id` BIGINT NOT NULL COMMENT '关联评论ID（对应user_comments表id）',
  `reply_user_id` BIGINT NOT NULL COMMENT '回复用户ID（对应users表id）',
  `reply_content` TEXT NOT NULL COMMENT '回复内容',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '回复创建时间',
  -- 外键关联，删除评论/用户时级联删除回复
  FOREIGN KEY (`comment_id`) REFERENCES `user_comments`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`reply_user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  -- 索引优化查询
  INDEX `idx_comment_id` (`comment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评论回复表';

-- --------------------------------------------------
-- 18. 评论点赞表 (comment_likes)
-- 存储用户对评论的点赞数据
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `comment_likes` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `comment_id` BIGINT NOT NULL COMMENT '关联评论ID（对应user_comments表id）',
  `user_id` BIGINT NOT NULL COMMENT '点赞用户ID（对应users表id）',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '点赞时间',
  -- 外键关联，删除评论/用户时级联删除点赞
  FOREIGN KEY (`comment_id`) REFERENCES `user_comments`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  -- 唯一索引，防止重复点赞
  UNIQUE KEY `uk_comment_user` (`comment_id`, `user_id`),
  -- 索引优化查询
  INDEX `idx_comment_id` (`comment_id`),
  INDEX `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评论点赞表';

-- --------------------------------------------------
-- 19. 消息通知表 (notifications)
-- 存储用户收到的消息通知（点赞、回复等）
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `notifications` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `user_id` BIGINT NOT NULL COMMENT '接收通知的用户ID（对应users表id）',
  `notification_type` VARCHAR(50) NOT NULL COMMENT '通知类型（like：点赞，reply：回复）',
  `content` TEXT COMMENT '通知内容',
  `related_id` BIGINT COMMENT '关联ID（如评论ID）',
  `is_read` TINYINT(1) DEFAULT 0 COMMENT '是否已读（0：未读，1：已读）',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '通知创建时间',
  -- 外键关联，删除用户时级联删除通知
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  -- 索引优化查询
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_is_read` (`is_read`),
  INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息通知表';

-- --------------------------------------------------
-- 20. 用户访问日志表 (user_access_logs)
-- 记录所有用户的访问行为（包括管理员），用于数据大屏统计
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_access_logs` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `user_id` BIGINT NOT NULL COMMENT '用户ID（包括管理员）',
  `access_type` VARCHAR(50) NOT NULL COMMENT '访问类型（page_view：页面访问，aigc_text：文字AIGC，aigc_image：图片AIGC，search：搜索，upload：上传等）',
  `resource_id` BIGINT COMMENT '关联资源ID（可选）',
  `resource_type` VARCHAR(50) COMMENT '资源类型（可选）',
  `access_path` VARCHAR(500) COMMENT '访问路径（如：/aigc, /search等）',
  `access_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '访问时间',
  -- 外键关联，删除用户时级联删除日志
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  -- 索引优化查询
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_access_type` (`access_type`),
  INDEX `idx_access_time` (`access_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户访问日志表';

-- --------------------------------------------------
-- 创建角色和权限
-- --------------------------------------------------




-- 创建管理员角色并赋予所有权限（可转移权限）
-- create role 'manager'@'%';



grant all privileges on java_project.* to 'manager'@'%' with grant option;





-- 创建普通用户角色并赋予所有权限（但不可转移权限）
-- 普通用户和管理员都拥有所有权限，但普通用户的权限不可转移
-- create role 'users'@'%';



grant all privileges on java_project.* to 'users'@'%';

-- 注意：没有 with grant option，所以普通用户不能转移权限给其他用户





-- --------------------------------------------------
-- 创建视图
-- --------------------------------------------------




-- 为每个表创建只读视图，便于统一查询与权限控制
CREATE OR REPLACE VIEW v_users AS SELECT * FROM users;



CREATE OR REPLACE VIEW v_cultural_resources AS SELECT * FROM cultural_resources;



CREATE OR REPLACE VIEW v_cultural_entities AS SELECT * FROM cultural_entities;



CREATE OR REPLACE VIEW v_entity_relationships AS SELECT * FROM entity_relationships;



CREATE OR REPLACE VIEW v_user_behavior_logs AS SELECT * FROM user_behavior_logs;

CREATE OR REPLACE VIEW v_user_access_logs AS SELECT * FROM user_access_logs;

CREATE OR REPLACE VIEW v_qa_sessions AS SELECT * FROM qa_sessions;



CREATE OR REPLACE VIEW v_qa_messages AS SELECT * FROM qa_messages;



CREATE OR REPLACE VIEW v_annotation_tasks AS SELECT * FROM annotation_tasks;



CREATE OR REPLACE VIEW v_annotation_records AS SELECT * FROM annotation_records;



CREATE OR REPLACE VIEW v_cultural_resources_from_user AS SELECT * FROM cultural_resources_from_user;



CREATE OR REPLACE VIEW v_AIGC_cultural_resources AS SELECT * FROM AIGC_cultural_resources;



CREATE OR REPLACE VIEW v_AIGC_graph AS SELECT * FROM AIGC_graph;



CREATE OR REPLACE VIEW v_crawled_images AS SELECT * FROM crawled_images;



CREATE OR REPLACE VIEW v_AIGC_cultural_entities AS SELECT * FROM AIGC_cultural_entities;
-- 新增评论/评分相关视图
CREATE OR REPLACE VIEW v_user_ratings AS SELECT * FROM user_ratings;
CREATE OR REPLACE VIEW v_user_comments AS SELECT * FROM user_comments;
CREATE OR REPLACE VIEW v_comment_replies AS SELECT * FROM comment_replies;




-- --------------------------------------------------
-- 补充索引（优化查询性能）
-- --------------------------------------------------

-- qa_sessions表：为user_id添加索引（用于查询用户的会话列表）
-- 注意：虽然外键会自动创建索引，但显式声明更清晰
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'qa_sessions' 
    AND INDEX_NAME = 'idx_qa_sessions_user_id'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_qa_sessions_user_id` ON `qa_sessions`(`user_id`)',
    'SELECT "idx_qa_sessions_user_id索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- qa_sessions表：为created_at添加索引（用于按时间排序）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'qa_sessions' 
    AND INDEX_NAME = 'idx_qa_sessions_created_at'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_qa_sessions_created_at` ON `qa_sessions`(`created_at`)',
    'SELECT "idx_qa_sessions_created_at索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- cultural_resources_from_user表：为user_id添加索引（用于查询用户上传的资源）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'cultural_resources_from_user' 
    AND INDEX_NAME = 'idx_crfu_user_id'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_crfu_user_id` ON `cultural_resources_from_user`(`user_id`)',
    'SELECT "idx_crfu_user_id索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- cultural_resources_from_user表：为upload_time添加索引（用于按时间排序）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'cultural_resources_from_user' 
    AND INDEX_NAME = 'idx_crfu_upload_time'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_crfu_upload_time` ON `cultural_resources_from_user`(`upload_time`)',
    'SELECT "idx_crfu_upload_time索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- cultural_resources_from_user表：为审核状态添加索引（用于筛选待审核资源）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'cultural_resources_from_user' 
    AND INDEX_NAME = 'idx_crfu_ai_review_status'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_crfu_ai_review_status` ON `cultural_resources_from_user`(`ai_review_status`)',
    'SELECT "idx_crfu_ai_review_status索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'cultural_resources_from_user' 
    AND INDEX_NAME = 'idx_crfu_manual_review_status'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_crfu_manual_review_status` ON `cultural_resources_from_user`(`manual_review_status`)',
    'SELECT "idx_crfu_manual_review_status索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- annotation_records表：为reviewer_id添加索引（用于查询审核记录）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'annotation_records' 
    AND INDEX_NAME = 'idx_ar_reviewer_id'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_ar_reviewer_id` ON `annotation_records`(`reviewer_id`)',
    'SELECT "idx_ar_reviewer_id索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- annotation_records表：为is_latest添加索引（用于查询最新标注）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'annotation_records' 
    AND INDEX_NAME = 'idx_ar_is_latest'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_ar_is_latest` ON `annotation_records`(`is_latest`)',
    'SELECT "idx_ar_is_latest索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- cultural_resources表：为upload_user_id添加索引（虽然外键会自动创建，但显式声明更清晰）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'cultural_resources' 
    AND INDEX_NAME = 'idx_cr_upload_user_id'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_cr_upload_user_id` ON `cultural_resources`(`upload_user_id`)',
    'SELECT "idx_cr_upload_user_id索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- cultural_resources表：为审核状态添加索引（用于筛选待审核资源）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'cultural_resources' 
    AND INDEX_NAME = 'idx_cr_ai_review_status'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_cr_ai_review_status` ON `cultural_resources`(`ai_review_status`)',
    'SELECT "idx_cr_ai_review_status索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'cultural_resources' 
    AND INDEX_NAME = 'idx_cr_manual_review_status'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_cr_manual_review_status` ON `cultural_resources`(`manual_review_status`)',
    'SELECT "idx_cr_manual_review_status索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- comment_replies表：为reply_user_id添加索引（用于查询用户的回复）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'comment_replies' 
    AND INDEX_NAME = 'idx_cr_reply_user_id'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_cr_reply_user_id` ON `comment_replies`(`reply_user_id`)',
    'SELECT "idx_cr_reply_user_id索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- qa_messages表：为create_time添加索引（用于按时间排序）
SET @index_exists = (
    SELECT COUNT(*) 
    FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'qa_messages' 
    AND INDEX_NAME = 'idx_qm_create_time'
);
SET @sql = IF(@index_exists = 0,
    'CREATE INDEX `idx_qm_create_time` ON `qa_messages`(`create_time`)',
    'SELECT "idx_qm_create_time索引已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- --------------------------------------------------
-- 添加entity_relationships表的CIDOC字段
-- --------------------------------------------------

-- 为entity_relationships表添加cidoc_property_id字段（如果不存在）
SET @column_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'entity_relationships' 
    AND COLUMN_NAME = 'cidoc_property_id'
);
SET @sql = IF(@column_exists = 0,
    'ALTER TABLE `entity_relationships` ADD COLUMN `cidoc_property_id` VARCHAR(10) COMMENT \'CIDOC-CRM标准属性代码（如P14, P62等），用于标准化关系类型\' AFTER `relationship_type`',
    'SELECT "cidoc_property_id字段已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 更新现有关系类型的CIDOC代码映射（示例）
-- 创作 -> P14 (carried out by)
-- 影响 -> P15 (was influenced by)
-- 位于 -> P53 (has former or current location)
-- 包含 -> P46 (is composed of)
-- 参与 -> P11 (had participant)
-- 相似 -> P130 (shows features of)
-- 继承 -> P127 (has broader term)
-- 引用 -> P67 (refers to)
-- 公布 -> P70 (documents)

UPDATE `entity_relationships` 
SET `cidoc_property_id` = 'P14' 
WHERE `relationship_type` = '创作' AND (`cidoc_property_id` IS NULL OR `cidoc_property_id` = '');

UPDATE `entity_relationships` 
SET `cidoc_property_id` = 'P15' 
WHERE `relationship_type` = '影响' AND (`cidoc_property_id` IS NULL OR `cidoc_property_id` = '');

UPDATE `entity_relationships` 
SET `cidoc_property_id` = 'P53' 
WHERE `relationship_type` = '位于' AND (`cidoc_property_id` IS NULL OR `cidoc_property_id` = '');

UPDATE `entity_relationships` 
SET `cidoc_property_id` = 'P46' 
WHERE `relationship_type` = '包含' AND (`cidoc_property_id` IS NULL OR `cidoc_property_id` = '');

UPDATE `entity_relationships` 
SET `cidoc_property_id` = 'P11' 
WHERE `relationship_type` = '参与' AND (`cidoc_property_id` IS NULL OR `cidoc_property_id` = '');

UPDATE `entity_relationships` 
SET `cidoc_property_id` = 'P130' 
WHERE `relationship_type` = '相似' AND (`cidoc_property_id` IS NULL OR `cidoc_property_id` = '');

UPDATE `entity_relationships` 
SET `cidoc_property_id` = 'P127' 
WHERE `relationship_type` = '继承' AND (`cidoc_property_id` IS NULL OR `cidoc_property_id` = '');

UPDATE `entity_relationships` 
SET `cidoc_property_id` = 'P67' 
WHERE `relationship_type` = '引用' AND (`cidoc_property_id` IS NULL OR `cidoc_property_id` = '');

UPDATE `entity_relationships` 
SET `cidoc_property_id` = 'P70' 
WHERE `relationship_type` = '公布' AND (`cidoc_property_id` IS NULL OR `cidoc_property_id` = '');

-- --------------------------------------------------
-- 索引说明
-- --------------------------------------------------




-- 索引：主键已自动创建聚簇索引；如需额外索引可在此追加（示例）
-- CREATE INDEX idx_cr_title ON cultural_resources(title);







-- 1. 更新cultural_entities表的entity_type字段为ENUM类型
-- 首先将现有数据中不符合枚举值的类型改为"其他"
UPDATE `cultural_entities` 
SET `entity_type` = '其他' 
WHERE `entity_type` NOT IN ('人物', '作品', '事件', '地点', '其他') 
   OR `entity_type` IS NULL;

-- 修改字段类型为ENUM（如果字段已存在且类型不同）
SET @column_type = (
    SELECT DATA_TYPE 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'cultural_entities' 
    AND COLUMN_NAME = 'entity_type'
);

SET @sql = IF(@column_type IS NOT NULL AND @column_type != 'enum',
    'ALTER TABLE `cultural_entities` MODIFY COLUMN `entity_type` ENUM(\'人物\', \'作品\', \'事件\', \'地点\', \'其他\') DEFAULT \'其他\' COMMENT \'实体类型（人物、作品、事件、地点、其他）\'',
    'SELECT "cultural_entities.entity_type字段类型已正确，跳过修改"'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. 更新AIGC_cultural_entities表的entity_type字段为ENUM类型
-- 首先将现有数据中不符合枚举值的类型改为"其他"
UPDATE `AIGC_cultural_entities` 
SET `entity_type` = '其他' 
WHERE `entity_type` NOT IN ('人物', '作品', '事件', '地点', '其他') 
   OR `entity_type` IS NULL;

-- 修改字段类型为ENUM（如果字段已存在且类型不同）
SET @column_type = (
    SELECT DATA_TYPE 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'AIGC_cultural_entities' 
    AND COLUMN_NAME = 'entity_type'
);

SET @sql = IF(@column_type IS NOT NULL AND @column_type != 'enum',
    'ALTER TABLE `AIGC_cultural_entities` MODIFY COLUMN `entity_type` ENUM(\'人物\', \'作品\', \'事件\', \'地点\', \'其他\') DEFAULT \'其他\' COMMENT \'实体类型（人物、作品、事件、地点、其他）\'',
    'SELECT "AIGC_cultural_entities.entity_type字段类型已正确，跳过修改"'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. 更新现有记录的resource_source（默认为cultural_resources）
-- 注意：annotation_tasks表的resource_source字段已在CREATE TABLE中定义，无需ALTER TABLE
UPDATE `annotation_tasks` 
SET `resource_source` = 'cultural_resources' 
WHERE `resource_source` IS NULL OR `resource_source` = '';

-- --------------------------------------------------
-- 更新现有数据库结构（兼容已有数据）
-- --------------------------------------------------

-- 更新users表的role ENUM，添加'超级管理员'选项（如果不存在）
SET @enum_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'users' 
    AND COLUMN_NAME = 'role'
    AND COLUMN_TYPE LIKE "%'超级管理员'%"
);
SET @sql = IF(@enum_exists = 0,
    'ALTER TABLE `users` MODIFY COLUMN `role` ENUM(\'普通用户\', \'管理员\', \'超级管理员\') NOT NULL DEFAULT \'普通用户\' COMMENT \'角色（普通用户、系统管理员或超级管理员）\'',
    'SELECT "role ENUM已包含超级管理员，跳过更新"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加is_online字段（如果不存在）
SET @column_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'users' 
    AND COLUMN_NAME = 'is_online'
);
SET @sql = IF(@column_exists = 0,
    'ALTER TABLE `users` ADD COLUMN `is_online` TINYINT(1) DEFAULT 0 COMMENT \'是否在线（0：离线，1：在线）\' AFTER `security_answer_hash`',
    'SELECT "is_online字段已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加last_active_time字段（如果不存在）
SET @column_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'java_project' 
    AND TABLE_NAME = 'users' 
    AND COLUMN_NAME = 'last_active_time'
);
SET @sql = IF(@column_exists = 0,
    'ALTER TABLE `users` ADD COLUMN `last_active_time` TIMESTAMP NULL DEFAULT NULL COMMENT \'最后活跃时间\' AFTER `is_online`',
    'SELECT "last_active_time字段已存在，跳过添加"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- --------------------------------------------------
-- 注意：
-- 1. users表的signature字段已在CREATE TABLE中定义，无需ALTER TABLE
-- 2. cultural_resources表的外键约束已在CREATE TABLE中定义，无需ALTER TABLE
-- 3. annotation_records表的扁平化字段已在CREATE TABLE中定义，无需ALTER TABLE
-- 4. annotation_tasks表的resource_source字段已在CREATE TABLE中定义，无需ALTER TABLE
-- 5. users表的role ENUM、is_online和last_active_time字段已通过上面的ALTER TABLE更新
-- --------------------------------------------------
