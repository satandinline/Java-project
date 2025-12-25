#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
后端服务器启动测试脚本
用于诊断后端服务器启动问题
"""

import sys
import os

# 添加项目根目录到路径
# 使用相对路径
project_root = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'AIGC'))

print("=" * 60)
print("后端服务器启动诊断工具")
print("=" * 60)

# 1. 检查Python版本
print("\n[1] 检查Python版本...")
print(f"    Python版本: {sys.version}")

# 2. 检查必要的依赖
print("\n[2] 检查Python依赖...")
required_modules = [
    'flask',
    'flask_cors',
    'pymysql',
    'dotenv',
    'pydantic'
]

missing_modules = []
for module in required_modules:
    try:
        if module == 'flask_cors':
            __import__('flask_cors')
        else:
            __import__(module)
        print(f"    ✓ {module}")
    except ImportError:
        print(f"    ✗ {module} (缺失)")
        missing_modules.append(module)

if missing_modules:
    print(f"\n[错误] 缺少以下依赖: {', '.join(missing_modules)}")
    print("请运行: pip install -r requirements.txt")
    sys.exit(1)

# 3. 检查数据库连接
print("\n[3] 检查数据库连接...")
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
        print("    ✓ 数据库连接成功")
        conn.close()
    else:
        print("    ✗ 数据库连接失败")
        print("    提示: 请确保MySQL服务已启动，数据库配置正确")
except Exception as e:
    print(f"    ✗ 数据库连接失败: {e}")

# 4. 检查端口占用
print("\n[4] 检查端口7200...")
try:
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 7200))
    sock.close()
    if result == 0:
        print("    ⚠ 端口7200已被占用")
        print("    提示: 请关闭占用该端口的程序，或修改后端服务器端口")
    else:
        print("    ✓ 端口7200可用")
except Exception as e:
    print(f"    ⚠ 无法检查端口: {e}")

# 5. 测试导入后端服务器模块
print("\n[5] 测试导入后端服务器模块...")
try:
    sys.path.insert(0, os.path.join(project_root, 'AIGC'))
    import aigc_api_server
    print("    ✓ 后端服务器模块导入成功")
except Exception as e:
    print(f"    ✗ 后端服务器模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("诊断完成！")
print("=" * 60)
print("\n如果所有检查都通过，可以尝试启动后端服务器：")
print("  python AIGC/aigc_api_server.py")
print("\n或者使用启动脚本：")
print("  start_dev.bat (Windows)")
print("  ./start_dev.sh (Linux/Mac)")

