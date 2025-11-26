class AuthSystem:
    def __init__(self):
        # 模拟数据库：存储账号密码和用户ID（实际替换为数据库操作）
        self.user_db: Dict[str, Dict] = {}  # 改为存储字典，包含password和id
        self.next_user_id = 1  # 用于生成用户ID
        # 模拟记住密码存储（实际可用加密本地存储）
        self.remembered_pwd: Dict[str, str] = {}

    def generate_verification_code(self) -> str:
        """生成4位数字验证码"""
        import random
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
        user_id = self.next_user_id
        self.next_user_id += 1
        self.user_db[username] = {
            "password": password,
            "id": user_id,
            "role": "普通用户"  # 默认普通用户
        }
        return f"注册成功！账号：{username}，用户ID：{user_id}，可直接登录"

    def login(self, username: str, password: Optional[str] = None) -> Dict:
        """
        登录入口：用户主动选择登录时调用
        :param username: 输入的账号
        :param password: 输入的密码（可为空，用于记住密码场景）
        :return: 登录结果字典，包含成功状态、消息和用户信息
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
            return {"success": False, "message": "账号不存在，请先注册"}

        # 验证密码
        if self.user_db[username]["password"] == password:
            # 询问是否记住密码
            remember = input("是否记住密码？(y/n): ").strip().lower()
            if remember == 'y':
                self.remembered_pwd[username] = password
                print("已记住密码")
            
            # 返回用户信息，包括ID和角色
            user_info = {
                "id": self.user_db[username]["id"],
                "username": username,
                "role": self.user_db[username]["role"]
            }
            return {
                "success": True, 
                "message": f"登录成功！欢迎回来，{username}",
                "user_info": user_info
            }
        else:
            return {"success": False, "message": "密码错误，请重新尝试"}

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
        self.user_db[username]["password"] = new_pwd
        if username in self.remembered_pwd:
            del self.remembered_pwd[username]
        return "密码重置成功，请重新登录"
