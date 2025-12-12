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

-- 创建数据库java_project，并切换到该数据库 
CREATE DATABASE IF NOT EXISTS java_project CHARACTER SET utf8mb4;



USE java_project;



-- 设置字符集
SET NAMES utf8mb4;



   
-- --------------------------------------------------
-- 1. 用户表 (users)
-- 存储用户信息和权限 
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `username` VARCHAR(100) UNIQUE NOT NULL COMMENT '用户名',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '加密后的密码',
  `role` ENUM('普通用户', '管理员') NOT NULL DEFAULT '普通用户' COMMENT '角色（普通用户或系统管理员）',
  `nickname` VARCHAR(100) COMMENT '用户昵称',
  `avatar_path` VARCHAR(255) DEFAULT '/default.jpg' COMMENT '头像路径（存储在public文件夹，格式：/用户名.jpg 或 /default.jpg）',
  `security_question` VARCHAR(255) COMMENT '自定义安全问题（用于找回密码）',
  `security_answer_hash` VARCHAR(255) COMMENT '安全问题的答案（哈希值）',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';





-- --------------------------------------------------
-- 2. 文化资源表 (cultural_resources)
-- 存储爬虫抓取或用户上传的原始文化素材。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `cultural_resources` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `title` VARCHAR(255) COMMENT '节日（文化资源涉及到的传统节日的名称）',
  `resource_type` VARCHAR(50) COMMENT '资源类型（如：文本、图像）',
  `file_format` VARCHAR(20) COMMENT '文件格式（如：TXT, JPG）',
  `source_from` VARCHAR(255) COMMENT '数据来源（如：网站名称）',
  `source_url` TEXT COMMENT '原始URL链接',
  `content_feature_data` LONGTEXT COMMENT '存储文本内容或特征向量的引用',
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





-- --------------------------------------------------
-- 4. 关系表 (entity_relationships)
-- 存储实体与实体之间的关系，用于构建知识图谱。
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `entity_relationships` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `source_entity_id` BIGINT NOT NULL COMMENT '源实体ID',
  `target_entity_id` BIGINT NOT NULL COMMENT '目标实体ID',
  `relationship_type` VARCHAR(50) NOT NULL COMMENT '关系类型（如：创作、影响、时空、相似、组成）',
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
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
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
  `resource_source` ENUM('cultural_resources', 'cultural_resources_from_user') DEFAULT 'cultural_resources' COMMENT '资源来源表（cultural_resources或cultural_resources_from_user）',
  `task_type` ENUM('实体', '质量', '语义') COMMENT '任务体系（实体、质量、语义）',
  `annotation_method` ENUM('ai', 'manual') DEFAULT 'ai' COMMENT '标注方式',
  `status` VARCHAR(20) DEFAULT '待标注' COMMENT '任务状态（如：待标注, 待审核, 已完成）',
  `required_annotators` INT DEFAULT 1 COMMENT '需要的标注人数',
  INDEX `idx_resource` (`resource_id`),
  INDEX `idx_status` (`status`),
  INDEX `idx_resource_source` (`resource_source`)
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
  `title` VARCHAR(255) COMMENT '节日',
  `resource_type` VARCHAR(50) COMMENT '资源类型（如：文本、图像）',
  `file_format` VARCHAR(20) COMMENT '文件格式（如：TXT, JPG）',
  `content_feature_data` LONGTEXT COMMENT '存储文本内容或特征向量的引用',
  `content_hash` VARCHAR(64) COMMENT '内容的SHA-256哈希，用于快速查重',
  `ai_review_status` ENUM('pending', 'passed', 'failed') NOT NULL DEFAULT 'pending' COMMENT 'AI审核状态',
  `manual_review_status` ENUM('pending', 'passed', 'failed') NOT NULL DEFAULT 'pending' COMMENT '人工审核状态',
  `upload_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  `review_notes` TEXT COMMENT '审核备注（例如：未通过原因）',
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_content_hash` (`content_hash`) COMMENT '哈希唯一索引，防止重复上传'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户上传资源待审表';





-- --------------------------------------------------
-- 11. AIGC文化资源表 (AIGC_cultural_resources)
-- 专门存储由AIGC生成的文化资源，结构与主资源表一致
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `AIGC_cultural_resources` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `title` VARCHAR(255) COMMENT '节日（文化资源涉及到的传统节日的名称）',
  `resource_type` VARCHAR(50) COMMENT '资源类型（如：文本、图像）',
  `file_format` VARCHAR(20) COMMENT '文件格式（如：TXT, JPG）',
  `source_from` VARCHAR(255) COMMENT '数据来源（例如：AIGC模型名称）',
  `source_url` TEXT COMMENT '原始URL链接 (如果适用)',
  `content_feature_data` LONGTEXT COMMENT '存储文本内容或特征向量的引用',
  `version` INT DEFAULT 1 COMMENT '版本号',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间'
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
-- --------------------------------------------------
CREATE TABLE IF NOT EXISTS `crawled_images` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '唯一主键',
  `file_name` VARCHAR(255) NOT NULL COMMENT '文件名',
  `storage_path` VARCHAR(767) NOT NULL UNIQUE COMMENT '存储路径',
  `dimensions` VARCHAR(50) COMMENT '尺寸 (例如: 1024x1024)',
  `crawl_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '抓取时间',
  `tags` JSON COMMENT '标签 (使用JSON数组格式, e.g., ["京剧", "脸谱"])'
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



CREATE OR REPLACE VIEW v_qa_sessions AS SELECT * FROM qa_sessions;



CREATE OR REPLACE VIEW v_qa_messages AS SELECT * FROM qa_messages;



CREATE OR REPLACE VIEW v_annotation_tasks AS SELECT * FROM annotation_tasks;



CREATE OR REPLACE VIEW v_annotation_records AS SELECT * FROM annotation_records;



CREATE OR REPLACE VIEW v_cultural_resources_from_user AS SELECT * FROM cultural_resources_from_user;



CREATE OR REPLACE VIEW v_AIGC_cultural_resources AS SELECT * FROM AIGC_cultural_resources;



CREATE OR REPLACE VIEW v_AIGC_graph AS SELECT * FROM AIGC_graph;



CREATE OR REPLACE VIEW v_crawled_images AS SELECT * FROM crawled_images;



CREATE OR REPLACE VIEW v_AIGC_cultural_entities AS SELECT * FROM AIGC_cultural_entities;





-- --------------------------------------------------
-- 索引说明
-- --------------------------------------------------




-- 索引：主键已自动创建聚簇索引；如需额外索引可在此追加（示例）
-- CREATE INDEX idx_cr_title ON cultural_resources(title);




-- --------------------------------------------------
-- 创建默认管理员账户
-- --------------------------------------------------

-- 创建默认管理员账户（admin/123456）
-- 密码123456的SHA256哈希值
INSERT INTO `users` (`username`, `password_hash`, `role`, `nickname`, `avatar_path`) 
VALUES (
    'admin', 
    '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 
    '管理员',
    '管理员',
    './default.jpg'
) ON DUPLICATE KEY UPDATE `username` = `username`;
