import os
from typing import Dict, Optional
import hashlib
from dotenv import load_dotenv
import sys

# 添加项目根目录到路径，以便导入db_connection
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_connection import get_user_db_config, get_user_db_connection

load_dotenv(override=True)

class AuthSystem:
    def __init__(self):
        # 使用db_connection.py的统一配置
        # 如果没有环境变量，会使用db_connection.py中的默认配置
        self.db_config = get_user_db_config()
    
    def _get_db_connection(self):
        """获取数据库连接"""
        try:
            # 使用db_connection.py的统一连接函数
            conn = get_user_db_connection()
            if conn:
                return conn
            else:
                # 如果get_user_db_connection失败，抛出异常而不是尝试直接连接
                raise Exception(f"无法连接到数据库，请检查数据库配置。配置信息: host={self.db_config.get('host')}, user={self.db_config.get('user')}, database={self.db_config.get('database')}")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            print(f"数据库配置: host={self.db_config.get('host')}, user={self.db_config.get('user')}, database={self.db_config.get('database')}")
            return None
    
    def _hash_password(self, password: str) -> str:
        """对密码进行哈希加密"""
        return hashlib.sha256(password.encode()).hexdigest()

    def generate_verification_code(self) -> str:
        """生成4位数字验证码"""
        import random
        return str(random.randint(1000, 9999))

    def register(self, username: str, password: str) -> Dict:
        """
        注册入口：用户主动选择注册时调用
        :param username: 账号名
        :param password: 密码
        :return: 注册结果字典，包含成功状态、消息和用户信息
        """
        if not username or not password:
            return {"success": False, "message": "用户名和密码不能为空"}
        
        if len(username) < 3:
            return {"success": False, "message": "用户名至少需要3个字符"}
        
        if len(password) < 6:
            return {"success": False, "message": "密码至少需要6个字符"}
        
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor() as cursor:
                # 检查用户名是否已存在
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    return {"success": False, "message": "该用户名已存在，请使用其他用户名"}
                
                # 加密密码
                password_hash = self._hash_password(password)
                
                # 插入新用户（默认角色为'普通用户'）
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                    (username, password_hash, "普通用户")
                )
                conn.commit()
                
                # 获取新创建的用户ID
                user_id = cursor.lastrowid
                
                return {
                    "success": True,
                    "message": f"注册成功！账号：{username}，可直接登录",
                    "user_info": {
                        "id": user_id,
                        "username": username,
                        "role": "普通用户"
                    }
                }
        except Exception as e:
            conn.rollback()
            print(f"注册失败: {e}")
            return {"success": False, "message": f"注册失败：{str(e)}"}
        finally:
            conn.close()

    def login(self, username: str, password: str) -> Dict:
        """
        登录入口：用户主动选择登录时调用
        :param username: 输入的账号
        :param password: 输入的密码
        :return: 登录结果字典，包含成功状态、消息和用户信息
        """
        if not username or not password:
            return {"success": False, "message": "用户名和密码不能为空"}
        
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor() as cursor:
                # 查询用户
                cursor.execute(
                    "SELECT id, username, password_hash, role FROM users WHERE username = %s",
                    (username,)
                )
                user = cursor.fetchone()
                
                if not user:
                    return {"success": False, "message": "账号不存在，请先注册"}
                
                # 验证密码
                password_hash = self._hash_password(password)
                if user["password_hash"] != password_hash:
                    return {"success": False, "message": "密码错误，请重新尝试"}
                
                # 返回用户信息
                user_info = {
                    "id": user["id"],
                    "username": user["username"],
                    "role": user["role"]
                }
                return {
                    "success": True,
                    "message": f"登录成功！欢迎回来，{username}",
                    "user_info": user_info
                }
        except Exception as e:
            print(f"登录失败: {e}")
            return {"success": False, "message": f"登录失败：{str(e)}"}
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据用户ID获取用户信息"""
        conn = self._get_db_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, role FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cursor.fetchone()
                if user:
                    return {
                        "id": user["id"],
                        "username": user["username"],
                        "role": user["role"]
                    }
                return None
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_db_config(self, user_id: int) -> Optional[Dict]:
        """
        获取用户的数据库配置信息（用于RAG系统连接数据库）
        现阶段所有用户都使用相同的数据库配置，但返回用户信息用于日志记录
        """
        user_info = self.get_user_by_id(user_id)
        if not user_info:
            return None
        
        # 返回数据库配置和用户信息
        return {
            "db_config": {
                "host": self.db_config["host"],
                "port": self.db_config["port"],
                "user": self.db_config["user"],
                "password": self.db_config["password"],
                "database": self.db_config["database"]
            },
            "user_info": user_info
        }
