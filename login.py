import random
from typing import Dict, Optional


class AuthSystem:
    def __init__(self):
        # 模拟数据库：存储账号密码（实际替换为数据库操作）
        self.user_db: Dict[str, str] = {}
        # 模拟记住密码存储（实际可用加密本地存储）
        self.remembered_pwd: Dict[str, str] = {}

    def generate_verification_code(self) -> str:
        """生成4位数字验证码"""
        return str(random.randint(1000, 9999))

    def register(self, username: str, password: str) -> str:
        """
        注册入口：用户主动选择注册时调用
        :param username: 账号名
        :param password: 密码
        :return: 注册结果提示
        """
        if username in self.user_db:
            # 账号已存在，提示是否找回密码
            choice = input("该账号已注册，是否找回密码？(y/n): ").strip().lower()
            if choice == 'y':
                return self.forgot_password()
            else:
                return "注册取消"
        # 账号不存在，完成注册
        self.user_db[username] = password
        return f"注册成功！账号：{username}，可直接登录"

    def login(self, username: str, password: Optional[str] = None) -> str:
        """
        登录入口：用户主动选择登录时调用
        :param username: 输入的账号
        :param password: 输入的密码（可为空，用于记住密码场景）
        :return: 登录结果提示
        """
        # 检查是否有记住的密码
        if username in self.remembered_pwd:
            use_remembered = input(f"检测到记住的密码，是否使用？(y/n): ").strip().lower()
            if use_remembered == 'y':
                password = self.remembered_pwd[username]
                print("已自动填充密码")

        # 若未输入密码，提示用户输入
        if not password:
            password = input("请输入密码：").strip()

        # 检查账号是否存在
        if username not in self.user_db:
            return "账号不存在，请先注册"

        # 验证密码
        if self.user_db[username] == password:
            # 询问是否记住密码
            remember = input("是否记住密码？(y/n): ").strip().lower()
            if remember == 'y':
                self.remembered_pwd[username] = password
                print("已记住密码")
            return f"登录成功！欢迎回来，{username}"
        else:
            return "密码错误，请重新尝试"

    def forgot_password(self) -> str:
        """忘记密码功能：重置密码流程"""
        username = input("请输入需要重置密码的账号：").strip()
        if username not in self.user_db:
            return "该账号未注册，无法重置密码"

        # 验证码验证
        code = self.generate_verification_code()
        print(f"验证码已发送（模拟）：{code}")
        user_code = input("请输入验证码：").strip()
        if user_code != code:
            return "验证码错误，重置失败"

        # 输入新密码
        new_pwd = input("请输入新密码：").strip()
        confirm_pwd = input("请再次输入新密码：").strip()
        if new_pwd != confirm_pwd:
            return "两次密码不一致，重置失败"

        # 更新密码并清除记住的密码
        self.user_db[username] = new_pwd
        if username in self.remembered_pwd:
            del self.remembered_pwd[username]
        return "密码重置成功，请重新登录"


# 测试示例：模拟用户主动选择登录/注册
if __name__ == "__main__":
    auth = AuthSystem()

    print("===== 测试注册流程 =====")
    # 用户主动选择注册
    print(auth.register("user1", "pwd123"))  # 新账号注册成功
    print(auth.register("user1", "pwd456"))  # 重复注册，提示是否找回密码

    print("\n===== 测试登录流程 =====")
    # 用户主动选择登录
    print(auth.login("user1"))  # 输入密码后登录成功
    print(auth.login("user2"))  # 账号不存在，提示先注册

    print("\n===== 测试记住密码 =====")
    # 登录时选择记住密码，下次登录自动提示
    print(auth.login("user1"))  # 此时会提示使用记住的密码

    print("\n===== 测试忘记密码 =====")
    print(auth.forgot_password())  # 重置user1的密码