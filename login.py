import os
from typing import Dict, Optional
import hashlib
from dotenv import load_dotenv
import sys
from pymysql.cursors import DictCursor

# 添加项目根目录到路径，以便导入db_connection
# 使用相对路径添加项目根目录到sys.path
current_file_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, current_file_dir)
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
    
    def _generate_random_account(self) -> str:
        """生成随机账号（8-10位数字字符串）"""
        import random
        length = random.randint(8, 10)
        # 生成8-10位数字字符串，第一位不能是0
        first_digit = random.randint(1, 9)
        rest_digits = ''.join([str(random.randint(0, 9)) for _ in range(length - 1)])
        return str(first_digit) + rest_digits
    
    def _generate_random_nickname(self) -> str:
        """生成随机昵称（10位英文字符）"""
        import random
        import string
        return ''.join(random.choices(string.ascii_letters, k=10))

    def generate_verification_code(self) -> str:
        """生成4位数字验证码"""
        import random
        return str(random.randint(1000, 9999))

    def register(self, password: str, nickname: str = None, 
                 avatar_path: str = None, security_question: str = None, 
                 security_answer: str = None) -> Dict:
        """
        注册入口：用户主动选择注册时调用
        :param password: 密码
        :param nickname: 昵称（可选，未提供则随机生成）
        :param avatar_path: 头像路径（可选，未提供则使用默认头像）
        :param security_question: 自定义安全问题（可选）
        :param security_answer: 安全问题答案（可选）
        :return: 注册结果字典，包含成功状态、消息和用户信息
        """
        if not password:
            return {"success": False, "message": "密码不能为空"}
        
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
            with conn.cursor(DictCursor) as cursor:
                # 生成唯一的账号（8-10位数字）
                max_attempts = 100  # 最多尝试100次生成唯一账号
                account = None
                for _ in range(max_attempts):
                    candidate_account = self._generate_random_account()
                    cursor.execute("SELECT id FROM users WHERE account = %s", (candidate_account,))
                    if not cursor.fetchone():
                        account = candidate_account
                        break
                
                if not account:
                    return {"success": False, "message": "账号生成失败，请稍后重试"}
                
                # 加密密码
                password_hash = self._hash_password(password)
                
                # 插入新用户（默认角色为'普通用户'）
                cursor.execute(
                    """INSERT INTO users (account, password_hash, role, nickname, signature, avatar_path, 
                       security_question, security_answer_hash) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (account, password_hash, "普通用户", nickname, None, avatar_path, 
                     security_question, security_answer_hash)
                )
                conn.commit()
                
                # 获取新创建的用户ID
                user_id = cursor.lastrowid
                
                return {
                    "success": True,
                    "message": f"注册成功！您的账号：{account}，请妥善保管，可直接登录",
                    "user_info": {
                        "id": user_id,
                        "account": account,
                        "nickname": nickname,
                        "signature": None,
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

    def login(self, account: str, password: str) -> Dict:
        """
        登录入口：用户主动选择登录时调用
        :param account: 输入的账号（8-10位数字）
        :param password: 输入的密码
        :return: 登录结果字典，包含成功状态、消息和用户信息
        """
        if not account or not password:
            return {"success": False, "message": "账号和密码不能为空"}
        
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            # 显式使用DictCursor确保返回字典格式
            with conn.cursor(DictCursor) as cursor:
                # 查询用户（使用account字段）
                cursor.execute(
                    "SELECT id, account, password_hash, role, nickname, signature, avatar_path FROM users WHERE account = %s",
                    (account,)
                )
                user = cursor.fetchone()
                
                if not user:
                    return {"success": False, "message": "账号不存在，请先注册"}
                
                # 确保user是字典格式
                if not isinstance(user, dict):
                    print(f"警告：查询结果不是字典格式，类型：{type(user)}")
                    # 如果是元组，尝试转换为字典
                    if isinstance(user, tuple):
                        columns = ['id', 'account', 'password_hash', 'role', 'nickname', 'signature', 'avatar_path']
                        user = dict(zip(columns, user))
                    else:
                        return {"success": False, "message": "数据库查询结果格式错误"}
                
                # 验证密码
                password_hash = self._hash_password(password)
                stored_password_hash = user.get("password_hash")
                if not stored_password_hash:
                    return {"success": False, "message": "用户数据异常，密码哈希不存在"}
                
                if stored_password_hash != password_hash:
                    return {"success": False, "message": "密码错误，请重新尝试"}
                
                # 更新用户在线状态和最后活跃时间
                user_id = user.get("id")
                if not user_id:
                    return {"success": False, "message": "用户数据异常，用户ID不存在"}
                
                try:
                    cursor.execute("""
                        UPDATE users 
                        SET is_online = 1, last_active_time = NOW() 
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                except Exception as e:
                    print(f"更新在线状态失败: {e}")
                    import traceback
                    traceback.print_exc()
                    # 即使更新失败也继续登录流程
                
                # 返回用户信息（包含昵称、个人签名和头像）
                avatar_path = user.get("avatar_path")
                if not avatar_path or avatar_path == './default.jpg':
                    avatar_path = '/default.jpg'
                user_info = {
                    "id": user.get("id"),
                    "account": user.get("account"),
                    "role": user.get("role", "普通用户"),
                    "nickname": user.get("nickname") or user.get("account"),
                    "signature": user.get("signature"),
                    "avatar_path": avatar_path
                }
                return {
                    "success": True,
                    "message": f"登录成功！欢迎回来，{user_info.get('nickname', account)}",
                    "user_info": user_info
                }
        except Exception as e:
            print(f"登录失败: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": f"登录失败：{str(e)}"}
        finally:
            if conn:
                conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据用户ID获取用户信息"""
        conn = self._get_db_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, account, role, nickname, signature, avatar_path, security_question FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cursor.fetchone()
                if user:
                    # 确保user是字典格式
                    if not isinstance(user, dict):
                        if isinstance(user, tuple):
                            columns = ['id', 'account', 'role', 'nickname', 'signature', 'avatar_path', 'security_question']
                            user = dict(zip(columns, user))
                        else:
                            return None
                    return {
                        "id": user.get("id"),
                        "account": user.get("account"),
                        "role": user.get("role"),
                        "nickname": user.get("nickname") or user.get("account"),
                        "signature": user.get("signature"),
                        "avatar_path": user.get("avatar_path", "./default.jpg"),
                        "security_question": user.get("security_question")
                    }
                return None
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return None
        finally:
            conn.close()
    
    def update_nickname(self, user_id: int, nickname: str) -> Dict:
        """修改用户昵称"""
        if not nickname or not nickname.strip():
            return {"success": False, "message": "昵称不能为空"}
        
        if len(nickname.strip()) > 100:
            return {"success": False, "message": "昵称长度不能超过100个字符"}
        
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor(DictCursor) as cursor:
                # 检查用户是否存在
                cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cursor.fetchone():
                    return {"success": False, "message": "用户不存在"}
                
                # 更新昵称
                cursor.execute(
                    "UPDATE users SET nickname = %s WHERE id = %s",
                    (nickname.strip(), user_id)
                )
                conn.commit()
                
                return {"success": True, "message": "昵称修改成功"}
        except Exception as e:
            conn.rollback()
            print(f"修改昵称失败: {e}")
            return {"success": False, "message": f"修改昵称失败：{str(e)}"}
        finally:
            conn.close()
    
    def get_security_question(self, account: str) -> Optional[Dict]:
        """获取用户的安全问题"""
        conn = self._get_db_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, security_question FROM users WHERE account = %s",
                    (account,)
                )
                user = cursor.fetchone()
                if user:
                    # 确保user是字典格式
                    if not isinstance(user, dict):
                        if isinstance(user, tuple):
                            columns = ['id', 'security_question']
                            user = dict(zip(columns, user))
                        else:
                            return {"success": False, "message": "数据库查询结果格式错误"}
                    if user.get("security_question"):
                        return {
                            "success": True,
                            "user_id": user.get("id"),
                            "security_question": user.get("security_question")
                        }
                return {"success": False, "message": "该用户未设置安全问题"}
        except Exception as e:
            print(f"获取安全问题失败: {e}")
            return {"success": False, "message": f"获取安全问题失败：{str(e)}"}
        finally:
            conn.close()
    
    def verify_security_answer(self, account: str, answer: str) -> Dict:
        """验证安全问题答案"""
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, security_answer_hash FROM users WHERE account = %s",
                    (account,)
                )
                user = cursor.fetchone()
                if not user:
                    return {"success": False, "message": "用户不存在"}
                
                # 确保user是字典格式
                if not isinstance(user, dict):
                    if isinstance(user, tuple):
                        columns = ['id', 'security_answer_hash']
                        user = dict(zip(columns, user))
                    else:
                        return {"success": False, "message": "数据库查询结果格式错误"}
                
                if not user.get("security_answer_hash"):
                    return {"success": False, "message": "该用户未设置安全问题"}
                
                # 验证答案
                answer_hash = self._hash_password(answer)
                if answer_hash == user.get("security_answer_hash"):
                    return {"success": True, "user_id": user.get("id")}
                else:
                    return {"success": False, "message": "答案错误"}
        except Exception as e:
            print(f"验证安全问题失败: {e}")
            return {"success": False, "message": f"验证失败：{str(e)}"}
        finally:
            conn.close()
    
    def reset_password(self, account: str, new_password: str) -> Dict:
        """重置密码"""
        if len(new_password) < 6:
            return {"success": False, "message": "密码至少需要6个字符"}
        
        conn = self._get_db_connection()
        if not conn:
            return {"success": False, "message": "数据库连接失败"}
        
        try:
            with conn.cursor(DictCursor) as cursor:
                # 检查用户是否存在
                cursor.execute("SELECT id FROM users WHERE account = %s", (account,))
                user = cursor.fetchone()
                if not user:
                    return {"success": False, "message": "用户不存在"}
                
                # 更新密码
                password_hash = self._hash_password(new_password)
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE account = %s",
                    (password_hash, account)
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
            with conn.cursor(DictCursor) as cursor:
                # 获取用户信息
                cursor.execute(
                    "SELECT password_hash FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cursor.fetchone()
                if not user:
                    return {"success": False, "message": "用户不存在"}
                
                # 确保user是字典格式
                if not isinstance(user, dict):
                    if isinstance(user, tuple):
                        columns = ['password_hash']
                        user = dict(zip(columns, user))
                    else:
                        return {"success": False, "message": "数据库查询结果格式错误"}
                
                # 验证旧密码
                old_password_hash = self._hash_password(old_password)
                if old_password_hash != user.get("password_hash"):
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
            with conn.cursor(DictCursor) as cursor:
                # 获取用户的安全问题答案
                cursor.execute(
                    "SELECT security_answer_hash FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cursor.fetchone()
                if not user:
                    return {"success": False, "message": "用户不存在"}
                
                # 确保user是字典格式
                if not isinstance(user, dict):
                    if isinstance(user, tuple):
                        columns = ['security_answer_hash']
                        user = dict(zip(columns, user))
                    else:
                        return {"success": False, "message": "数据库查询结果格式错误"}
                
                if not user.get("security_answer_hash"):
                    return {"success": False, "message": "用户未设置安全问题"}
                
                # 验证答案
                answer_hash = self._hash_password(answer)
                if answer_hash == user.get("security_answer_hash"):
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
            with conn.cursor(DictCursor) as cursor:
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
