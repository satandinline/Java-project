# -*- coding: utf-8 -*-
"""
用户行为日志记录工具
提供统一的日志记录接口，实时将用户行为存入数据库
"""

import pymysql
from datetime import datetime
from typing import Optional, Dict
from db_connection import get_user_db_connection


class UserLogging:
    """用户行为日志记录类"""
    
    @staticmethod
    def log_behavior(user_id: int, behavior_type: str, content: str, 
                    db_config: Optional[Dict] = None) -> bool:
        """
        记录用户行为日志到数据库
        
        Args:
            user_id: 用户ID
            behavior_type: 行为类型（'检索', '交互', '生成', '标注'）
            content: 行为内容描述
            db_config: 数据库配置（可选，默认使用默认配置）
            
        Returns:
            bool: 是否记录成功
        """
        try:
            conn = get_user_db_connection()
            if not conn:
                print(f"[日志] 记录失败：数据库连接失败")
                return False
            
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO user_behavior_logs 
                        (user_id, behavior_type, content, timestamp)
                        VALUES (%s, %s, %s, NOW())
                    """, (user_id, behavior_type, content))
                    conn.commit()
                    return True
            except Exception as e:
                print(f"[日志] 记录用户行为失败: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
        except Exception as e:
            print(f"[日志] 记录用户行为异常: {e}")
            return False
    
    @staticmethod
    def log_login(user_id: int, account: str) -> bool:
        """记录用户登录行为"""
        return UserLogging.log_behavior(
            user_id, 
            '交互', 
            f"用户登录：{account}"
        )
    
    @staticmethod
    def log_register(user_id: int, account: str) -> bool:
        """记录用户注册行为"""
        return UserLogging.log_behavior(
            user_id, 
            '交互', 
            f"用户注册：{account}"
        )
    
    @staticmethod
    def log_aigc_text(user_id: int, query: str = "") -> bool:
        """记录文字AIGC使用"""
        content = f"使用文字AIGC生成内容"
        if query:
            content += f"（提示词：{query[:50]}...）" if len(query) > 50 else f"（提示词：{query}）"
        return UserLogging.log_behavior(user_id, '生成', content)
    
    @staticmethod
    def log_aigc_image(user_id: int, prompt: str = "") -> bool:
        """记录图片AIGC使用"""
        content = f"使用图片AIGC生成图像"
        if prompt:
            content += f"（提示词：{prompt[:50]}...）" if len(prompt) > 50 else f"（提示词：{prompt}）"
        return UserLogging.log_behavior(user_id, '生成', content)
    
    @staticmethod
    def log_upload(user_id: int, file_name: str, resource_type: str) -> bool:
        """记录资源上传行为"""
        return UserLogging.log_behavior(
            user_id, 
            '交互', 
            f"上传资源：{file_name}（类型：{resource_type}）"
        )
    
    @staticmethod
    def log_search(user_id: int, search_type: str, query: str = "") -> bool:
        """记录搜索行为"""
        content = f"执行{search_type}搜索"
        if query:
            content += f"（关键词：{query[:50]}...）" if len(query) > 50 else f"（关键词：{query}）"
        return UserLogging.log_behavior(user_id, '检索', content)
    
    @staticmethod
    def log_annotation(user_id: int, task_id: int, action: str = "标注") -> bool:
        """记录标注行为"""
        return UserLogging.log_behavior(
            user_id, 
            '标注', 
            f"{action}任务（任务ID：{task_id}）"
        )

