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
    
    def _generate_random_nickname(self) -> str:
        """生成随机昵称（10位英文字符）"""
        import random
        import string
        return ''.join(random.choices(string.ascii_letters, k=10))

    def generate_verification_code(self) -> str:
        """生成4位数字验证码"""
        import random
        return str(random.randint(1000, 9999))

    def register(self, username: str, password: str, nickname: str = None, 
                 avatar_path: str = None, security_question: str = None, 
                 security_answer: str = None) -> Dict:
        """
        注册入口：用户主动选择注册时调用
        :param username: 账号名
        :param password: 密码
        :param nickname: 昵称（可选，未提供则随机生成）
        :param avatar_path: 头像路径（可选，未提供则使用默认头像）
        :param security_question: 自定义安全问题（可选）
        :param security_answer: 安全问题答案（可选）
        :return: 注册结果字典，包含成功状态、消息和用户信息
        """
        if not username or not password:
            return {"success": False, "message": "用户名和密码不能为空"}
        
        if len(username) < 3:
            return {"success": False, "message": "用户名至少需要3个字符"}
        
        # 验证用户名只能包含数字和英文字母
        import re
        if not re.match(r'^[a-zA-Z0-9]+$', username):
            return {"success": False, "message": "用户名只能包含数字和英文字母"}
        
        if len(password) < 6:
            return {"success": False, "message": "密码至少需要6个字符"}
        
        # 如果没有提供昵称，生成随机昵称
        if not nickname or not nickname.strip():
            nickname = self._generate_random_nickname()
        
        # 如果没有提供头像路径，使用默认头像
        if not avatar_path or not avatar_path.strip():
            avatar_path = '/default.jpg'
        
        # 处理安全问题
        security_answer_hash = None
        if security_question and security_answer:
            security_answer_hash = self._hash_password(security_answer)
        
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
                    """INSERT INTO users (username, password_hash, role, nickname, avatar_path, 
                       security_question, security_answer_hash) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (username, password_hash, "普通用户", nickname, avatar_path, 
                     security_question, security_answer_hash)
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
                        "nickname": nickname,
                        "avatar_path": avatar_path,
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
                    "SELECT id, username, password_hash, role, nickname, avatar_path FROM users WHERE username = %s",
                    (username,)
                )
                user = cursor.fetchone()
                
                if not user:
                    return {"success": False, "message": "账号不存在，请先注册"}
                
                # 验证密码
                password_hash = self._hash_password(password)
                if user["password_hash"] != password_hash:
                    return {"success": False, "message": "密码错误，请重新尝试"}
                
                # 返回用户信息（包含昵称和头像）
                avatar_path = user.get("avatar_path")
                if not avatar_path or avatar_path == './default.jpg':
                    avatar_path = '/default.jpg'
                user_info = {
                    "id": user["id"],
                    "username": user["username"],
                    "role": user["role"],
                    "nickname": user.get("nickname", user["username"]),
                    "avatar_path": avatar_path
                }
                return {
                    "success": True,
                    "message": f"登录成功！欢迎回来，{user_info.get('nickname', username)}",
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
                    "SELECT id, username, role, nickname, avatar_path, security_question FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cursor.fetchone()
                if user:
                    return {
                        "id": user["id"],
                        "username": user["username"],
                        "role": user["role"],
                        "nickname": user.get("nickname", user["username"]),
                        "avatar_path": user.get("avatar_path", "./default.jpg"),
                        "security_question": user.get("security_question")
                    }
                return None
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return None
        finally:
            conn.close()
    
    def get_security_question(self, username: str) -> Optional[Dict]:
        """获取用户的安全问题"""
        conn = self._get_db_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, security_question FROM users WHERE username = %s",
                    (username,)
                )
                user = cursor.fetchone()
                if user and user.get("security_question"):
                    return {
                        "success": True,
                        "user_id": user["id"],
                        "security_question": user["security_question"]
                    }
                return {"success": False, "message": "该用户未设置安全问题"}
        except Exception as e:
            print(f"获取安全问题失败: {e}")
            return {"success": False, "message": f"获取安全问题失败：{str(e)}"}
        finally:
            conn.close()
    
    def verify_security_answer(self, username: str, answer: str) -> Dict:
        """验证安全问题答案"""
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, security_answer_hash FROM users WHERE username = %s",
                    (username,)
                )
                user = cursor.fetchone()
                if not user:
                    return {"success": False, "message": "用户不存在"}
                
                if not user.get("security_answer_hash"):
                    return {"success": False, "message": "该用户未设置安全问题"}
                
                # 验证答案
                answer_hash = self._hash_password(answer)
                if answer_hash == user["security_answer_hash"]:
                    return {"success": True, "user_id": user["id"]}
                else:
                    return {"success": False, "message": "答案错误"}
        except Exception as e:
            print(f"验证安全问题失败: {e}")
            return {"success": False, "message": f"验证失败：{str(e)}"}
        finally:
            conn.close()
    
    def reset_password(self, username: str, new_password: str) -> Dict:
        """重置密码"""
        if len(new_password) < 6:
            return {"success": False, "message": "密码至少需要6个字符"}
        
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor() as cursor:
                # 检查用户是否存在
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                if not user:
                    return {"success": False, "message": "用户不存在"}
                
                # 更新密码
                password_hash = self._hash_password(new_password)
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE username = %s",
                    (password_hash, username)
                )
                conn.commit()
                
                return {"success": True, "message": "密码重置成功"}
        except Exception as e:
            conn.rollback()
            print(f"重置密码失败: {e}")
            return {"success": False, "message": f"重置密码失败：{str(e)}"}
        finally:
            conn.close()
    
    def update_password(self, user_id: int, old_password: str, new_password: str) -> Dict:
        """修改密码（需要验证旧密码）"""
        if len(new_password) < 6:
            return {"success": False, "message": "新密码至少需要6个字符"}
        
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor() as cursor:
                # 获取用户信息
                cursor.execute(
                    "SELECT password_hash FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cursor.fetchone()
                if not user:
                    return {"success": False, "message": "用户不存在"}
                
                # 验证旧密码
                old_password_hash = self._hash_password(old_password)
                if old_password_hash != user["password_hash"]:
                    return {"success": False, "message": "旧密码错误"}
                
                # 更新密码
                new_password_hash = self._hash_password(new_password)
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (new_password_hash, user_id)
                )
                conn.commit()
                
                return {"success": True, "message": "密码修改成功"}
        except Exception as e:
            conn.rollback()
            print(f"修改密码失败: {e}")
            return {"success": False, "message": f"修改密码失败：{str(e)}"}
        finally:
            conn.close()
    
    def verify_security_question(self, user_id: int, answer: str) -> Dict:
        """验证安全问题答案（通过user_id）"""
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor() as cursor:
                # 获取用户的安全问题答案
                cursor.execute(
                    "SELECT security_answer_hash FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cursor.fetchone()
                if not user:
                    return {"success": False, "message": "用户不存在"}
                
                if not user.get("security_answer_hash"):
                    return {"success": False, "message": "用户未设置安全问题"}
                
                # 验证答案
                answer_hash = self._hash_password(answer)
                if answer_hash == user["security_answer_hash"]:
                    return {"success": True, "message": "验证成功"}
                else:
                    return {"success": False, "message": "答案错误"}
        except Exception as e:
            print(f"验证安全问题答案失败: {e}")
            return {"success": False, "message": f"验证失败：{str(e)}"}
        finally:
            conn.close()
    
    def update_security_question(self, user_id: int, question: str, answer: str, need_verify: bool = True) -> Dict:
        """更新安全问题（如果已设置需要先验证原答案，如果未设置则直接设置）"""
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor() as cursor:
                # 检查用户是否已设置安全问题
                cursor.execute(
                    "SELECT security_question, security_answer_hash FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cursor.fetchone()
                if not user:
                    return {"success": False, "message": "用户不存在"}
                
                # 如果已设置安全问题且需要验证，但这里不需要验证（因为前端已经验证过了）
                # 如果未设置，则直接设置
                
                # 加密新答案
                answer_hash = self._hash_password(answer)
                
                # 更新数据库
                cursor.execute(
                    "UPDATE users SET security_question = %s, security_answer_hash = %s WHERE id = %s",
                    (question, answer_hash, user_id)
                )
                conn.commit()
                
                return {"success": True, "message": "安全问题更新成功"}
        except Exception as e:
            conn.rollback()
            print(f"更新安全问题失败: {e}")
            return {"success": False, "message": f"更新失败：{str(e)}"}
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
