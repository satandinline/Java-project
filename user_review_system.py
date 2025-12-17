#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户评论与评价系统核心模块

本模块提供了完整的用户评论、评分和回复管理功能，支持多维度评分、评论状态管理、
学术讨论标记以及用户权限控制。
"""

import pymysql
import pymysql.cursors
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Union, Tuple, Any


class DatabaseError(Exception):
    """数据库操作异常类"""
    pass


class PermissionError(Exception):
    """权限不足异常类"""
    pass


class ValidationError(Exception):
    """数据验证异常类"""
    pass


class UserReviewSystem:
    """
    用户评论与评价系统类
    提供评分、评论和回复的增删改查功能
    """
    
    def __init__(self, host: str = 'localhost', user: str = 'root', password: str = '', 
                 database: str = 'java_project', charset: str = 'utf8mb4', 
                 cursorclass: Any = pymysql.cursors.DictCursor):
        """
        初始化数据库连接
        
        Args:
            host: 数据库主机地址
            user: 数据库用户名
            password: 数据库密码
            database: 数据库名称
            charset: 字符集
            cursorclass: 游标类型
        """
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.charset = charset
        self.cursorclass = cursorclass
        self.connection = None
        
    def connect(self) -> bool:
        """
        建立数据库连接
        
        Returns:
            bool: 连接是否成功
            
        Raises:
            DatabaseError: 数据库连接失败
        """
        try:
            if self.connection and self.connection.open:
                return True
                
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                cursorclass=self.cursorclass
            )
            return True
        except pymysql.MySQLError as e:
            raise DatabaseError(f"数据库连接失败: {str(e)}")
    
    def disconnect(self) -> None:
        """
        关闭数据库连接
        """
        if self.connection and self.connection.open:
            self.connection.close()
    
    def _execute_query(self, query: str, params: Optional[Tuple] = None, 
                      commit: bool = False) -> Any:
        """
        执行SQL查询
        
        Args:
            query: SQL查询语句
            params: 查询参数
            commit: 是否提交事务
            
        Returns:
            Any: 查询结果
            
        Raises:
            DatabaseError: 数据库操作失败
        """
        try:
            if not self.connect():
                raise DatabaseError("数据库连接失败")
                
            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                
                if commit:
                    self.connection.commit()
                else:
                    return cursor.fetchall()
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            raise DatabaseError(f"数据库操作失败: {str(e)}")
    
    def check_user_exists(self, user_id: int) -> bool:
        """
        检查用户是否存在
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 用户是否存在
        """
        query = "SELECT id FROM users WHERE id = %s"
        result = self._execute_query(query, (user_id,))
        return len(result) > 0
    
    def check_resource_exists(self, resource_id: int) -> bool:
        """
        检查资源是否存在
        
        Args:
            resource_id: 资源ID
            
        Returns:
            bool: 资源是否存在
        """
        query = "SELECT id FROM cultural_resources WHERE id = %s"
        result = self._execute_query(query, (resource_id,))
        return len(result) > 0
    
    # 评分相关功能
    def add_or_update_rating(self, user_id: int, resource_id: int, rating: int, 
                           rating_dimension: str = 'general') -> Dict[str, Any]:
        """
        添加或更新评分
        
        Args:
            user_id: 用户ID
            resource_id: 资源ID
            rating: 评分值(1-5)
            rating_dimension: 评分维度
            
        Returns:
            Dict: 操作结果
            
        Raises:
            ValidationError: 数据验证失败
            DatabaseError: 数据库操作失败
        """
        # 验证输入
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            raise ValidationError("评分必须为1-5之间的整数")
        
        if not self.check_user_exists(user_id):
            raise ValidationError(f"用户ID {user_id} 不存在")
        
        if not self.check_resource_exists(resource_id):
            raise ValidationError(f"资源ID {resource_id} 不存在")
        
        # 检查是否已存在评分
        query = """
        SELECT id FROM user_ratings 
        WHERE user_id = %s AND resource_id = %s AND rating_dimension = %s
        """
        existing = self._execute_query(query, (user_id, resource_id, rating_dimension))
        
        current_time = datetime.now()
        
        if existing:
            # 更新评分
            query = """
            UPDATE user_ratings 
            SET rating = %s, rated_at = %s 
            WHERE id = %s
            """
            self._execute_query(query, (rating, current_time, existing[0]['id']), commit=True)
            
            return {
                "success": True,
                "message": "评分更新成功",
                "operation": "update",
                "rating_id": existing[0]['id']
            }
        else:
            # 添加新评分
            query = """
            INSERT INTO user_ratings 
            (user_id, resource_id, rating, rating_dimension, rated_at)
            VALUES (%s, %s, %s, %s, %s)
            """
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (user_id, resource_id, rating, rating_dimension, 
                                          current_time))
                    self.connection.commit()
                    
                    return {
                        "success": True,
                        "message": "评分添加成功",
                        "operation": "insert",
                        "rating_id": cursor.lastrowid
                    }
            except Exception as e:
                self.connection.rollback()
                raise DatabaseError(f"添加评分失败: {str(e)}")
    
    def get_user_rating(self, user_id: int, resource_id: int, 
                       rating_dimension: str = 'general') -> Optional[Dict[str, Any]]:
        """
        获取用户对特定资源的评分
        
        Args:
            user_id: 用户ID
            resource_id: 资源ID
            rating_dimension: 评分维度
            
        Returns:
            Dict or None: 评分信息或None(不存在)
        """
        query = """
        SELECT * FROM user_ratings 
        WHERE user_id = %s AND resource_id = %s AND rating_dimension = %s
        """
        result = self._execute_query(query, (user_id, resource_id, rating_dimension))
        
        if result:
            return dict(result[0])
        return None
    
    def get_resource_ratings(self, resource_id: int, 
                           rating_dimension: str = None) -> List[Dict[str, Any]]:
        """
        获取资源的所有评分
        
        Args:
            resource_id: 资源ID
            rating_dimension: 评分维度(None表示所有维度)
            
        Returns:
            List: 评分列表
        """
        if rating_dimension:
            query = """
            SELECT * FROM user_ratings 
            WHERE resource_id = %s AND rating_dimension = %s
            ORDER BY rated_at DESC
            """
            params = (resource_id, rating_dimension)
        else:
            query = """
            SELECT * FROM user_ratings 
            WHERE resource_id = %s
            ORDER BY rating_dimension, rated_at DESC
            """
            params = (resource_id,)
            
        return self._execute_query(query, params)
    
    def get_resource_average_rating(self, resource_id: int, 
                                  rating_dimension: str = 'general') -> float:
        """
        获取资源的平均评分
        
        Args:
            resource_id: 资源ID
            rating_dimension: 评分维度
            
        Returns:
            float: 平均评分
        """
        query = """
        SELECT AVG(rating) as avg_rating FROM user_ratings 
        WHERE resource_id = %s AND rating_dimension = %s
        """
        result = self._execute_query(query, (resource_id, rating_dimension))
        
        return float(result[0]['avg_rating']) if result[0]['avg_rating'] else 0.0
    
    def delete_rating(self, rating_id: int, user_id: int) -> Dict[str, Any]:
        """
        删除评分(仅限评分所有者)
        
        Args:
            rating_id: 评分ID
            user_id: 请求删除的用户ID
            
        Returns:
            Dict: 操作结果
            
        Raises:
            PermissionError: 权限不足
            DatabaseError: 数据库操作失败
        """
        # 检查评分归属
        query = "SELECT user_id FROM user_ratings WHERE id = %s"
        result = self._execute_query(query, (rating_id,))
        
        if not result:
            return {"success": False, "message": "评分不存在"}
        
        if result[0]['user_id'] != user_id:
            raise PermissionError("无权删除此评分")
        
        # 删除评分
        query = "DELETE FROM user_ratings WHERE id = %s"
        try:
            self._execute_query(query, (rating_id,), commit=True)
            return {"success": True, "message": "评分删除成功"}
        except Exception as e:
            raise DatabaseError(f"删除评分失败: {str(e)}")
    
    # 评论相关功能
    def add_comment(self, user_id: int, resource_id: int, comment_content: str, 
                   is_academic_discussion: bool = False) -> Dict[str, Any]:
        """
        添加评论
        
        Args:
            user_id: 用户ID
            resource_id: 资源ID
            comment_content: 评论内容
            is_academic_discussion: 是否为学术讨论
            
        Returns:
            Dict: 操作结果
            
        Raises:
            ValidationError: 数据验证失败
            DatabaseError: 数据库操作失败
        """
        # 验证输入
        if not comment_content or len(comment_content.strip()) == 0:
            raise ValidationError("评论内容不能为空")
        
        if not self.check_user_exists(user_id):
            raise ValidationError(f"用户ID {user_id} 不存在")
        
        if not self.check_resource_exists(resource_id):
            raise ValidationError(f"资源ID {resource_id} 不存在")
        
        current_time = datetime.now()
        
        try:
            query = """
            INSERT INTO user_comments 
            (user_id, resource_id, comment_content, comment_status, 
            is_academic_discussion, created_at, updated_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            with self.connection.cursor() as cursor:
                cursor.execute(query, (user_id, resource_id, comment_content, 'approved', 
                                      is_academic_discussion, current_time, current_time))
                self.connection.commit()
                
                return {
                    "success": True,
                    "message": "评论添加成功",
                    "comment_id": cursor.lastrowid
                }
        except Exception as e:
            self.connection.rollback()
            raise DatabaseError(f"添加评论失败: {str(e)}")
    
    def update_comment(self, comment_id: int, user_id: int, comment_content: str) -> Dict[str, Any]:
        """
        更新评论(仅限评论所有者)
        
        Args:
            comment_id: 评论ID
            user_id: 用户ID
            comment_content: 新的评论内容
            
        Returns:
            Dict: 操作结果
            
        Raises:
            ValidationError: 数据验证失败
            PermissionError: 权限不足
            DatabaseError: 数据库操作失败
        """
        # 验证输入
        if not comment_content or len(comment_content.strip()) == 0:
            raise ValidationError("评论内容不能为空")
        
        # 检查评论归属
        query = "SELECT user_id FROM user_comments WHERE id = %s"
        result = self._execute_query(query, (comment_id,))
        
        if not result:
            return {"success": False, "message": "评论不存在"}
        
        if result[0]['user_id'] != user_id:
            raise PermissionError("无权修改此评论")
        
        current_time = datetime.now()
        
        # 更新评论
        query = """
        UPDATE user_comments 
        SET comment_content = %s, updated_at = %s 
        WHERE id = %s
        """
        try:
            self._execute_query(query, (comment_content, current_time, comment_id), commit=True)
            return {"success": True, "message": "评论更新成功"}
        except Exception as e:
            raise DatabaseError(f"更新评论失败: {str(e)}")
    
    def delete_comment(self, comment_id: int, user_id: int, is_admin: bool = False) -> Dict[str, Any]:
        """
        删除评论(评论所有者或管理员)
        
        Args:
            comment_id: 评论ID
            user_id: 请求删除的用户ID
            is_admin: 是否为管理员
            
        Returns:
            Dict: 操作结果
            
        Raises:
            PermissionError: 权限不足
            DatabaseError: 数据库操作失败
        """
        # 检查评论归属
        query = "SELECT user_id FROM user_comments WHERE id = %s"
        result = self._execute_query(query, (comment_id,))
        
        if not result:
            return {"success": False, "message": "评论不存在"}
        
        if not is_admin and result[0]['user_id'] != user_id:
            raise PermissionError("无权删除此评论")
        
        try:
            # 开始事务
            with self.connection.cursor() as cursor:
                # 先删除关联的回复
                cursor.execute("DELETE FROM comment_replies WHERE comment_id = %s", (comment_id,))
                
                # 再删除评论
                cursor.execute("DELETE FROM user_comments WHERE id = %s", (comment_id,))
                
                self.connection.commit()
                
                return {"success": True, "message": "评论及其回复删除成功"}
        except Exception as e:
            self.connection.rollback()
            raise DatabaseError(f"删除评论失败: {str(e)}")
    
    def get_comment(self, comment_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单个评论详情
        
        Args:
            comment_id: 评论ID
            
        Returns:
            Dict or None: 评论信息或None(不存在)
        """
        query = """
        SELECT c.*, u.username 
        FROM user_comments c 
        JOIN users u ON c.user_id = u.id 
        WHERE c.id = %s
        """
        result = self._execute_query(query, (comment_id,))
        
        if result:
            return dict(result[0])
        return None
    
    def get_resource_comments(self, resource_id: int, status: str = 'approved', 
                            limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取资源的评论列表
        
        Args:
            resource_id: 资源ID
            status: 评论状态('approved', 'pending', 'rejected', None表示所有状态)
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            List: 评论列表
        """
        if status:
            query = """
            SELECT c.*, u.username 
            FROM user_comments c 
            JOIN users u ON c.user_id = u.id 
            WHERE c.resource_id = %s AND c.comment_status = %s
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
            """
            params = (resource_id, status, limit, offset)
        else:
            query = """
            SELECT c.*, u.username 
            FROM user_comments c 
            JOIN users u ON c.user_id = u.id 
            WHERE c.resource_id = %s
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
            """
            params = (resource_id, limit, offset)
            
        return self._execute_query(query, params)
    
    def get_user_comments(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取用户发表的所有评论
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            List: 评论列表
        """
        query = """
        SELECT c.*, cr.title as resource_title 
        FROM user_comments c 
        JOIN cultural_resources cr ON c.resource_id = cr.id 
        WHERE c.user_id = %s
        ORDER BY c.created_at DESC
        LIMIT %s OFFSET %s
        """
        return self._execute_query(query, (user_id, limit, offset))
    
    # 回复相关功能
    def add_reply(self, comment_id: int, user_id: int, reply_content: str) -> Dict[str, Any]:
        """
        添加回复
        
        Args:
            comment_id: 评论ID
            user_id: 用户ID
            reply_content: 回复内容
            
        Returns:
            Dict: 操作结果
            
        Raises:
            ValidationError: 数据验证失败
            DatabaseError: 数据库操作失败
        """
        # 验证输入
        if not reply_content or len(reply_content.strip()) == 0:
            raise ValidationError("回复内容不能为空")
        
        if not self.check_user_exists(user_id):
            raise ValidationError(f"用户ID {user_id} 不存在")
        
        # 检查评论是否存在
        query = "SELECT id FROM user_comments WHERE id = %s"
        result = self._execute_query(query, (comment_id,))
        
        if not result:
            raise ValidationError(f"评论ID {comment_id} 不存在")
        
        current_time = datetime.now()
        
        try:
            query = """
            INSERT INTO comment_replies 
            (comment_id, reply_user_id, reply_content, created_at) 
            VALUES (%s, %s, %s, %s)
            """
            with self.connection.cursor() as cursor:
                cursor.execute(query, (comment_id, user_id, reply_content, current_time))
                self.connection.commit()
                
                return {
                    "success": True,
                    "message": "回复添加成功",
                    "reply_id": cursor.lastrowid
                }
        except Exception as e:
            self.connection.rollback()
            raise DatabaseError(f"添加回复失败: {str(e)}")
    
    def delete_reply(self, reply_id: int, user_id: int, is_admin: bool = False) -> Dict[str, Any]:
        """
        删除回复(回复所有者或管理员)
        
        Args:
            reply_id: 回复ID
            user_id: 请求删除的用户ID
            is_admin: 是否为管理员
            
        Returns:
            Dict: 操作结果
            
        Raises:
            PermissionError: 权限不足
            DatabaseError: 数据库操作失败
        """
        # 检查回复归属
        query = "SELECT reply_user_id FROM comment_replies WHERE id = %s"
        result = self._execute_query(query, (reply_id,))
        
        if not result:
            return {"success": False, "message": "回复不存在"}
        
        if not is_admin and result[0]['reply_user_id'] != user_id:
            raise PermissionError("无权删除此回复")
        
        # 删除回复
        query = "DELETE FROM comment_replies WHERE id = %s"
        try:
            self._execute_query(query, (reply_id,), commit=True)
            return {"success": True, "message": "回复删除成功"}
        except Exception as e:
            raise DatabaseError(f"删除回复失败: {str(e)}")
    
    def get_comment_replies(self, comment_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取评论的所有回复
        
        Args:
            comment_id: 评论ID
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            List: 回复列表
        """
        query = """
        SELECT r.*, u.username 
        FROM comment_replies r 
        JOIN users u ON r.reply_user_id = u.id 
        WHERE r.comment_id = %s
        ORDER BY r.created_at ASC
        LIMIT %s OFFSET %s
        """
        return self._execute_query(query, (comment_id, limit, offset))


# 模块测试代码(当直接运行此文件时执行)
if __name__ == "__main__":
    print("用户评论与评价系统核心模块已加载")
    print("请导入 UserReviewSystem 类并创建实例使用")