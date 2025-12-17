# -*- coding: utf-8 -*-
"""测试数据库连接"""
import pymysql

try:
    conn = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='M17382930994c@',
        charset='utf8mb4'
    )
    print("数据库连接成功！")
    conn.close()
except Exception as e:
    print(f"数据库连接失败: {e}")

