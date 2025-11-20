-- --------------------------------------------------
-- init_schema.sql
-- java_project的数据库初始化脚本
-- 一共七个表
-- 数据库类型: MySQL
-- --------------------------------------------------

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `username` VARCHAR(100) UNIQUE NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` ENUM('普通用户', '管理员') NOT NULL DEFAULT '普通用户',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `cultural_resources` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `title` VARCHAR(255),
  `resource_type` VARCHAR(50),
  `file_format` VARCHAR(20),
  `source_from` VARCHAR(255),
  `source_url` TEXT,
  `content_feature_data` LONGTEXT,
  `version` INT DEFAULT 1,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_source_url` (`source_url`(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `cultural_entities` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `entity_name` VARCHAR(255) NOT NULL,
  `entity_type` VARCHAR(50),
  `description` TEXT,
  `source` TEXT,
  `period_era` VARCHAR(100),
  `geo_coordinates` VARCHAR(100),
  `cultural_region` VARCHAR(100),
  `style_features` TEXT,
  `cultural_value` TEXT,
  `related_images_url` TEXT,
  `digital_resource_link` TEXT,
  INDEX `idx_entity_name` (`entity_name`),
  INDEX `idx_entity_type` (`entity_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `entity_relationships` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `source_entity_id` BIGINT NOT NULL,
  `target_entity_id` BIGINT NOT NULL,
  `relationship_type` VARCHAR(50) NOT NULL,
  `relationship_strength` FLOAT,
  `relationship_evidence` TEXT,
  `spatiotemporal_constraint` VARCHAR(255),
  `confidence_score` FLOAT,
  FOREIGN KEY (`source_entity_id`) REFERENCES `cultural_entities`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`target_entity_id`) REFERENCES `cultural_entities`(`id`) ON DELETE CASCADE,
  INDEX `idx_source_entity` (`source_entity_id`),
  INDEX `idx_target_entity` (`target_entity_id`),
  INDEX `idx_relationship_type` (`relationship_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user_behavior_logs` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `behavior_type` ENUM('检索', '交互', '生成', '标注'),
  `content` TEXT,
  `timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  INDEX `idx_user` (`user_id`),
  INDEX `idx_behavior_type` (`behavior_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `qa_sessions` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `summary` TEXT,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `qa_messages` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `session_id` BIGINT NOT NULL,
  `sender` ENUM('user', 'ai') NOT NULL,
  `message_content` TEXT,
  `user_feedback` TEXT,
  `timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`session_id`) REFERENCES `qa_sessions`(`id`) ON DELETE CASCADE,
  INDEX `idx_session` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `annotation_tasks` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `resource_id` BIGINT,
  `task_type` ENUM('实体', '质量', '语义'),
  `status` VARCHAR(20) DEFAULT '待标注',
  `required_annotators` INT DEFAULT 1,
  FOREIGN KEY (`resource_id`) REFERENCES `cultural_resources`(`id`) ON DELETE SET NULL,
  INDEX `idx_resource` (`resource_id`),
  INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `annotation_records` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `task_id` BIGINT NOT NULL,
  `annotator_id` BIGINT NOT NULL,
  `annotation_data` JSON,
  `is_expert_reviewed` BOOLEAN DEFAULT FALSE,
  `reviewer_id` BIGINT,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`task_id`) REFERENCES `annotation_tasks`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`annotator_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`reviewer_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
  INDEX `idx_task` (`task_id`),
  INDEX `idx_annotator` (`annotator_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
