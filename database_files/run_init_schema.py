# -*- coding: utf-8 -*-
"""
自动执行 init_schema.sql 脚本
用于初始化数据库结构

使用方法：
    python database_files/run_init_schema.py

功能：
    - 自动连接MySQL数据库
    - 执行 init_schema.sql 中的所有SQL语句
    - 创建所有表、视图、索引和角色
    - 创建默认管理员账户（admin/123456）
    
注意：
    - 此脚本会创建全新的数据库结构
    - 如果数据库已存在，会保留现有数据（使用 CREATE TABLE IF NOT EXISTS）
    - qa_messages 表使用新结构（包含 user_id, user_message, ai_message, model, image_url 等字段）
"""

import os
import sys
import pymysql
import re
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

# 尝试从环境变量获取配置，如果没有则使用默认值
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', '3306')),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'M17382930994c@'),
    'charset': 'utf8mb4'
}

# SQL文件路径
SQL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'init_schema.sql')


def split_sql_statements(sql_content):
    """
    将SQL文件内容分割成独立的SQL语句
    处理多行语句、注释、字符串中的分号等
    """
    # 移除单行注释 (-- 开头的注释)
    lines = []
    for line in sql_content.split('\n'):
        # 保留包含字符串的行的注释（因为可能是SQL的一部分）
        if '--' in line and not any(quote in line for quote in ["'", '"', '`']):
            # 移除注释部分
            comment_pos = line.find('--')
            line = line[:comment_pos].rstrip()
        lines.append(line)
    
    sql_content = '\n'.join(lines)
    
    # 移除多行注释 (/* ... */)
    sql_content = re.sub(r'/\*.*?\*/', '', sql_content, flags=re.DOTALL)
    
    # 按分号分割，但需要处理字符串中的分号
    statements = []
    current_statement = []
    in_string = False
    string_char = None
    i = 0
    
    while i < len(sql_content):
        char = sql_content[i]
        
        # 检测字符串开始/结束
        if char in ("'", '"', '`') and (i == 0 or sql_content[i-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
        
        current_statement.append(char)
        
        # 如果遇到分号且不在字符串中，则结束当前语句
        if char == ';' and not in_string:
            statement = ''.join(current_statement).strip()
            if statement and statement != ';':
                statements.append(statement)
            current_statement = []
        
        i += 1
    
    # 添加最后一个语句（如果没有以分号结尾）
    if current_statement:
        statement = ''.join(current_statement).strip()
        if statement:
            statements.append(statement)
    
    # 过滤空语句
    statements = [s for s in statements if s.strip() and not s.strip().startswith('--')]
    
    return statements


def execute_sql_file(conn, sql_file_path):
    """
    执行SQL文件中的所有语句
    """
    print(f"正在读取SQL文件: {sql_file_path}")
    
    if not os.path.exists(sql_file_path):
        print(f"错误: SQL文件不存在: {sql_file_path}")
        return False
    
    with open(sql_file_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    print(f"SQL文件大小: {len(sql_content)} 字符")
    
    # 分割SQL语句
    statements = split_sql_statements(sql_content)
    print(f"共找到 {len(statements)} 条SQL语句")
    print("-" * 60)
    
    success_count = 0
    error_count = 0
    
    try:
        cursor = conn.cursor()
        
        for i, statement in enumerate(statements, 1):
            # 跳过空语句和纯注释
            statement = statement.strip()
            if not statement or statement.startswith('--'):
                continue
            
            # 显示当前执行的语句（截取前100字符）
            preview = statement[:100].replace('\n', ' ').strip()
            if len(statement) > 100:
                preview += '...'
            print(f"[{i}/{len(statements)}] 执行: {preview}")
            
            try:
                # 执行SQL语句
                cursor.execute(statement)
                conn.commit()
                success_count += 1
                print(f"  ✓ 成功")
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                # 检查是否是"已存在"类型的错误（这些通常可以忽略）
                if any(keyword in error_msg.lower() for keyword in ['already exists', 'duplicate', '已存在', '跳过']):
                    print(f"  ⚠ 跳过（已存在或可忽略）: {error_msg[:100]}")
                    success_count += 1  # 视为成功
                else:
                    print(f"  ✗ 错误: {error_msg}")
                    # 对于严重错误，可以选择继续或停止
                    # 这里选择继续执行，但记录错误
                    conn.rollback()
        
        cursor.close()
        
        print("-" * 60)
        print(f"执行完成！")
        print(f"成功: {success_count} 条")
        print(f"失败: {error_count} 条")
        
        return error_count == 0
        
    except Exception as e:
        print(f"执行过程中发生错误: {e}")
        conn.rollback()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("MySQL 数据库初始化脚本")
    print("=" * 60)
    print(f"MySQL 主机: {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}")
    print(f"用户名: {MYSQL_CONFIG['user']}")
    print(f"数据库: java_project")
    print(f"SQL文件: {SQL_FILE}")
    print("=" * 60)
    print()
    
    # 连接数据库（不指定数据库，因为可能还不存在）
    try:
        print("正在连接MySQL服务器...")
        # 先连接到MySQL服务器（不指定数据库）
        conn_config = MYSQL_CONFIG.copy()
        if 'database' in conn_config:
            del conn_config['database']
        conn = pymysql.connect(**conn_config)
        print("✓ MySQL服务器连接成功")
        print()
    except Exception as e:
        print(f"✗ MySQL服务器连接失败: {e}")
        print("\n请检查:")
        print("  1. MySQL服务是否正在运行")
        print("  2. 用户名和密码是否正确（可在.env文件中配置）")
        print("  3. 主机地址和端口是否正确")
        print(f"  4. 当前配置: host={MYSQL_CONFIG['host']}, port={MYSQL_CONFIG['port']}, user={MYSQL_CONFIG['user']}")
        return 1
    
    try:
        # 执行SQL文件（SQL文件中会创建数据库）
        success = execute_sql_file(conn, SQL_FILE)
        
        if success:
            print("\n" + "=" * 60)
            print("✓ 数据库初始化成功完成！")
            print("=" * 60)
            print("\n默认管理员账户:")
            print("  用户名: admin")
            print("  密码: 123456")
            print("\n请及时修改默认管理员密码！")
            return 0
        else:
            print("\n⚠ 数据库初始化完成，但存在一些错误")
            print("请检查上面的错误信息")
            return 1
            
    except Exception as e:
        print(f"\n✗ 发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()
        print("\n数据库连接已关闭")


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

