#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试后端服务器启动
"""

import sys
import os
import traceback

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'AIGC'))

print("=" * 60)
print("测试后端服务器启动")
print("=" * 60)

# 1. 测试导入基础模块
print("\n[1] 测试导入基础模块...")
try:
    from flask import Flask
    print("    [OK] Flask")
except Exception as e:
    print(f"    [ERROR] Flask: {e}")
    sys.exit(1)

try:
    from flask_cors import CORS
    print("    [OK] Flask-CORS")
except Exception as e:
    print(f"    [ERROR] Flask-CORS: {e}")
    sys.exit(1)

# 2. 测试导入项目模块
print("\n[2] 测试导入项目模块...")
try:
    from login import AuthSystem
    print("    [OK] login")
except Exception as e:
    print(f"    [ERROR] login: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from upload_handler import ResourceUploader
    print("    [OK] upload_handler")
except Exception as e:
    print(f"    [ERROR] upload_handler: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from user_logging import UserLogging
    print("    [OK] user_logging")
except Exception as e:
    print(f"    [ERROR] user_logging: {e}")
    traceback.print_exc()
    sys.exit(1)

# 3. 测试导入统计API
print("\n[3] 测试导入统计API...")
try:
    from statistics_api import statistics_bp
    print("    [OK] statistics_api")
except Exception as e:
    print(f"    [ERROR] statistics_api: {e}")
    traceback.print_exc()
    sys.exit(1)

# 4. 测试导入AIGC模块
print("\n[4] 测试导入AIGC模块...")
try:
    from aigc_db_helper import save_aigc_text_resource, save_aigc_image, extract_festival_names
    print("    [OK] aigc_db_helper")
except Exception as e:
    print(f"    [ERROR] aigc_db_helper: {e}")
    traceback.print_exc()
    sys.exit(1)

# 5. 尝试导入主服务器模块
print("\n[5] 测试导入主服务器模块...")
try:
    # 只导入，不执行
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "aigc_api_server",
        os.path.join(project_root, "AIGC", "aigc_api_server.py")
    )
    if spec is None:
        print("    [ERROR] 无法加载模块规范")
        sys.exit(1)
    
    # 检查语法
    with open(os.path.join(project_root, "AIGC", "aigc_api_server.py"), 'r', encoding='utf-8') as f:
        code = f.read()
        compile(code, os.path.join(project_root, "AIGC", "aigc_api_server.py"), 'exec')
    print("    [OK] 语法检查通过")
    
    # 尝试导入（但不执行if __name__ == '__main__'部分）
    module = importlib.util.module_from_spec(spec)
    print("    [OK] 模块对象创建成功")
    
except SyntaxError as e:
    print(f"    [ERROR] 语法错误: {e}")
    print(f"    行号: {e.lineno}, 位置: {e.offset}")
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"    [ERROR] 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 6. 检查数据库连接
print("\n[6] 检查数据库连接...")
try:
    from db_connection import get_user_db_connection, get_user_db_config
    
    db_config = get_user_db_config()
    print(f"    数据库配置:")
    print(f"      Host: {db_config.get('host')}")
    print(f"      Port: {db_config.get('port')}")
    print(f"      User: {db_config.get('user')}")
    print(f"      Database: {db_config.get('database')}")
    
    conn = get_user_db_connection()
    if conn:
        print("    [OK] 数据库连接成功")
        conn.close()
    else:
        print("    [ERROR] 数据库连接失败")
        print("    提示: 请确保MySQL服务已启动，数据库配置正确")
        sys.exit(1)
except Exception as e:
    print(f"    [ERROR] 数据库连接失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 7. 检查端口占用
print("\n[7] 检查端口7200...")
try:
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', 7200))
    sock.close()
    if result == 0:
        print("    [WARN] 端口7200已被占用")
        print("    提示: 请关闭占用该端口的程序，或修改后端服务器端口")
    else:
        print("    [OK] 端口7200可用")
except Exception as e:
    print(f"    [WARN] 无法检查端口: {e}")

# 8. 检查环境变量
print("\n[8] 检查环境变量配置...")
import os
from dotenv import load_dotenv
load_dotenv(override=True)

env_vars = {
    'MYSQL_HOST': os.getenv('MYSQL_HOST'),
    'MYSQL_PORT': os.getenv('MYSQL_PORT'),
    'MYSQL_USER': os.getenv('MYSQL_USER'),
    'MYSQL_PASSWORD': os.getenv('MYSQL_PASSWORD'),
    'MYSQL_DB': os.getenv('MYSQL_DB'),
    'DASHSCOPE_API_KEY': os.getenv('DASHSCOPE_API_KEY') or os.getenv('ALIYUN_API_KEY'),
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY')
}

has_env_file = os.path.exists('.env')
if has_env_file:
    print("    [OK] 找到.env文件")
else:
    print("    [INFO] 未找到.env文件，将使用默认配置")

for key, value in env_vars.items():
    if value:
        if 'PASSWORD' in key or 'API_KEY' in key:
            print(f"    [OK] {key}: {'*' * min(len(value), 10)}")
        else:
            print(f"    [OK] {key}: {value}")
    else:
        if key in ['MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 'MYSQL_DB']:
            print(f"    [INFO] {key}: 未设置，将使用默认值")
        else:
            print(f"    [WARN] {key}: 未设置（某些功能可能不可用）")

print("\n" + "=" * 60)
print("所有检查完成！")
print("=" * 60)
