#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接运行后端服务器，用于调试
"""

import sys
import os

# 添加项目根目录到路径
# 使用相对路径
project_root = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'AIGC'))

# 设置环境变量，确保使用UTF-8编码
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

print("=" * 60)
print("启动后端服务器...")
print("=" * 60)

try:
    # 直接执行后端服务器
    server_file = os.path.join(project_root, 'AIGC', 'aigc_api_server.py')
    with open(server_file, 'r', encoding='utf-8') as f:
        code = f.read()
        exec(compile(code, server_file, 'exec'), {'__name__': '__main__'})
except KeyboardInterrupt:
    print("\n服务器已停止（用户中断）")
except Exception as e:
    print(f"\n服务器启动失败: {e}")
    import traceback
    traceback.print_exc()
    input("\n按Enter键退出...")
    sys.exit(1)

