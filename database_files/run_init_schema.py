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
    - 创建默认管理员账户和测试用户账户（在Python代码中创建）
    
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

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

# 加载环境变量
load_dotenv(override=True)

# 从环境变量获取配置，不提供硬编码的默认值
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_PORT = os.getenv('MYSQL_PORT')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DB = os.getenv('MYSQL_DB', 'java_project')  # 数据库名可以使用默认值

# 验证必需的配置项
if not all([MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD]):
    missing = []
    if not MYSQL_HOST:
        missing.append('MYSQL_HOST')
    if not MYSQL_PORT:
        missing.append('MYSQL_PORT')
    if not MYSQL_USER:
        missing.append('MYSQL_USER')
    if not MYSQL_PASSWORD:
        missing.append('MYSQL_PASSWORD')
    raise ValueError(
        f"缺少必需的数据库配置环境变量: {', '.join(missing)}\n"
        f"请在.env文件中配置以下变量:\n"
        f"MYSQL_HOST=127.0.0.1\n"
        f"MYSQL_PORT=3306\n"
        f"MYSQL_USER=root\n"
        f"MYSQL_PASSWORD=your_password\n"
        f"MYSQL_DB=java_project"
    )

MYSQL_CONFIG = {
    'host': MYSQL_HOST,
    'port': int(MYSQL_PORT),
    'user': MYSQL_USER,
    'password': MYSQL_PASSWORD,
    'charset': 'utf8mb4'
}

# SQL文件路径
# 使用相对路径
SQL_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'init_schema.sql')


def get_statement_priority(stmt):
    """获取SQL语句的优先级"""
    stmt_upper = stmt.upper().strip()
    if stmt_upper.startswith('CREATE DATABASE') or stmt_upper.startswith('USE ') or stmt_upper.startswith('SET '):
        return 1
    elif stmt_upper.startswith('CREATE TABLE'):
        return 2
    elif stmt_upper.startswith('INSERT'):
        return 3
    elif stmt_upper.startswith('ALTER TABLE'):
        return 4
    elif stmt_upper.startswith('GRANT'):
        return 5
    elif stmt_upper.startswith('CREATE') and 'VIEW' in stmt_upper:
        return 6
    else:
        return 7


def split_sql_statements(sql_content):
    """
    将SQL文件内容分割成独立的SQL语句
    处理多行语句、注释、字符串中的分号等
    特别处理PREPARE/EXECUTE语句块
    """
    # 移除BOM字符（必须在最开始处理）
    if sql_content.startswith('\ufeff'):
        sql_content = sql_content[1:]
    
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
        
        # 检测字符串开始/结束（处理转义字符）
        if char in ("'", '"', '`'):
            # 检查是否是转义字符（MySQL中反斜杠转义）
            # 注意：需要检查前一个字符是否是反斜杠，且反斜杠本身没有被转义
            is_escaped = False
            if i > 0 and sql_content[i-1] == '\\':
                # 检查反斜杠是否被转义（连续两个反斜杠）
                backslash_count = 0
                j = i - 1
                while j >= 0 and sql_content[j] == '\\':
                    backslash_count += 1
                    j -= 1
                # 如果反斜杠数量是奇数，则当前引号被转义
                is_escaped = (backslash_count % 2 == 1)
            
            if is_escaped:
                # 转义字符，继续（引号是字符串内容的一部分）
                pass
            elif not in_string:
                # 开始字符串
                in_string = True
                string_char = char
            elif char == string_char:
                # 结束字符串（匹配的引号类型）
                in_string = False
                string_char = None
        
        current_statement.append(char)
        
        # 如果遇到分号且不在字符串中，则结束当前语句
        if char == ';' and not in_string:
            statement = ''.join(current_statement).strip()
            if statement and statement != ';':
                # 移除单行注释（在语句末尾）
                if '--' in statement:
                    # 检查注释是否在字符串外
                    comment_pos = statement.find('--')
                    # 简单检查：如果--前面有引号，可能是字符串内的
                    before_comment = statement[:comment_pos]
                    quote_count = before_comment.count("'") + before_comment.count('"') + before_comment.count('`')
                    if quote_count % 2 == 0:  # 引号成对，说明注释在字符串外
                        statement = statement[:comment_pos].rstrip()
                
                if statement and not statement.startswith('--'):
                    statements.append(statement)
            current_statement = []
        
        i += 1
    
    # 添加最后一个语句（如果没有以分号结尾）
    if current_statement:
        statement = ''.join(current_statement).strip()
        if statement and not statement.startswith('--'):
            statements.append(statement)
    
    # 过滤空语句和纯注释
    filtered_statements = []
    for s in statements:
        s = s.strip()
        # 移除BOM字符（如果存在）
        if s.startswith('\ufeff'):
            s = s[1:].strip()
        # 过滤空语句、纯注释、只有分号的语句
        if s and not s.startswith('--') and s != ';' and len(s) > 1:
            # 移除语句前后的空白行
            s = '\n'.join([line.strip() for line in s.split('\n') if line.strip()])
            if s:
                filtered_statements.append(s)
    
    # 如果CREATE TABLE语句没有被识别，尝试使用正则表达式补充
    create_table_pattern = r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS[^;]*;'
    create_table_matches = re.findall(create_table_pattern, sql_content, re.IGNORECASE | re.DOTALL)
    if create_table_matches:
        # 检查哪些CREATE TABLE语句已经在filtered_statements中
        existing_create_tables = [s for s in filtered_statements if s.upper().strip().startswith('CREATE TABLE')]
        if len(existing_create_tables) < len(create_table_matches):
            # 添加缺失的CREATE TABLE语句
            for match in create_table_matches:
                match_clean = match.strip()
                if match_clean and not any(match_clean.upper() == s.upper() for s in filtered_statements):
                    filtered_statements.append(match_clean)
    
    # 按优先级排序（使用外部定义的函数）
    filtered_statements.sort(key=get_statement_priority)
    
    # 调试：检查前10个语句的类型
    if len(filtered_statements) > 0:
        print(f"\n[DEBUG] 排序后的前10个语句类型:")
        for i, stmt in enumerate(filtered_statements[:10], 1):
            stmt_type = get_statement_priority(stmt)
            preview = stmt[:80].replace('\n', ' ').strip()
            print(f"  {i}. 优先级{stmt_type}: {preview}...")
        print()
        # 检查CREATE TABLE语句
        create_tables = [s for s in filtered_statements if s.upper().strip().startswith('CREATE TABLE')]
        print(f"[DEBUG] 找到 {len(create_tables)} 个CREATE TABLE语句")
        if len(create_tables) > 0:
            for i, stmt in enumerate(create_tables[:5], 1):
                preview = stmt[:80].replace('\n', ' ').strip()
                print(f"  CREATE TABLE {i}: {preview}...")
        print()
    
    return filtered_statements


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
    
    # 调试：检查CREATE TABLE语句
    create_tables = [s for s in statements if s.upper().strip().startswith('CREATE TABLE')]
    print(f"[DEBUG] 分割后找到 {len(create_tables)} 个CREATE TABLE语句")
    if len(create_tables) == 0:
        # 检查原始内容中是否有CREATE TABLE
        if 'CREATE TABLE' in sql_content.upper():
            print("[DEBUG] 警告：SQL文件中包含CREATE TABLE，但分割后未找到！")
            # 尝试手动查找
            import re
            manual_find = re.findall(r'CREATE TABLE[^;]*;', sql_content, re.IGNORECASE | re.DOTALL)
            print(f"[DEBUG] 手动查找找到 {len(manual_find)} 个CREATE TABLE语句")
    
    print("-" * 60)
    
    success_count = 0
    error_count = 0
    
    try:
        cursor = conn.cursor()
        
        for i, statement in enumerate(statements, 1):
            # 跳过空语句和纯注释
            statement = statement.strip()
            if not statement or statement.startswith('--') or statement == ';' or len(statement) <= 1:
                continue
            
            # 移除BOM字符（如果存在）
            if statement.startswith('\ufeff'):
                statement = statement[1:]
            
            # 再次检查是否为空
            if not statement.strip():
                continue
            
            # 跳过空语句
            if not statement.strip() or statement.strip() == ';':
                continue
            
            # 显示当前执行的语句（截取前100字符）
            preview = statement[:100].replace('\n', ' ').strip()
            if len(statement) > 100:
                preview += '...'
            # 显示语句类型和优先级
            stmt_type = get_statement_priority(statement)
            stmt_keyword = statement.upper().strip().split()[0] if statement.strip() else "UNKNOWN"
            print(f"[{i}/{len(statements)}] 优先级{stmt_type} ({stmt_keyword}): {preview}")
            
            try:
                # 执行SQL语句
                cursor.execute(statement)
                conn.commit()
                success_count += 1
                print(f"  [OK] 成功")
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                # 检查是否是"已存在"类型的错误（这些通常可以忽略）
                ignore_keywords = [
                    'already exists', 'duplicate', '已存在', '跳过',
                    'unknown database', 'table doesn\'t exist', '表不存在',
                    'unknown column', '列不存在', 'column doesn\'t exist'
                ]
                if any(keyword in error_msg.lower() for keyword in ignore_keywords):
                    print(f"  [SKIP] 跳过（已存在或可忽略）: {error_msg[:100]}")
                    success_count += 1  # 视为成功
                else:
                    print(f"  [ERROR] 错误: {error_msg}")
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


def create_default_accounts(conn):
    """
    创建默认管理员和测试用户账号
    密码123456的SHA256哈希值：8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92
    """
    import hashlib
    
    password_hash = hashlib.sha256('123456'.encode()).hexdigest()
    
    # 生成安全问题答案的哈希值
    admin_answer_hash = hashlib.sha256('管理员'.encode()).hexdigest()
    test_user_answer_hash = hashlib.sha256('测试用户'.encode()).hexdigest()
    
    # 生成超级管理员安全问题答案的哈希值
    super_admin_answer_hash = hashlib.sha256('超级管理员'.encode()).hexdigest()
    
    default_accounts = [
        {
            'account': '111111111',
            'password_hash': password_hash,
            'role': '超级管理员',
            'nickname': '超级管理员',
            'avatar_path': '/default.jpg',
            'security_question': '我的身份是？',
            'security_answer_hash': super_admin_answer_hash
        },
        {
            'account': '123456789',
            'password_hash': password_hash,
            'role': '管理员',
            'nickname': '管理员',
            'avatar_path': '/default.jpg',
            'security_question': '我的身份是？',
            'security_answer_hash': admin_answer_hash
        },
        {
            'account': '987654321',
            'password_hash': password_hash,
            'role': '普通用户',
            'nickname': '测试用户',
            'avatar_path': '/default.jpg',
            'security_question': '我的身份是？',
            'security_answer_hash': test_user_answer_hash
        }
    ]
    
    try:
        with conn.cursor() as cursor:
            for account_info in default_accounts:
                # 检查账号是否已存在
                cursor.execute(
                    "SELECT id FROM users WHERE account = %s",
                    (account_info['account'],)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # 如果账号已存在，跳过创建
                    print(f"  账号 {account_info['account']} 已存在，跳过创建")
                else:
                    # 尝试使用新字段结构插入（包含is_online和last_active_time）
                    try:
                        cursor.execute("""
                            INSERT INTO `users` (`account`, `password_hash`, `role`, `nickname`, `signature`, `avatar_path`, `security_question`, `security_answer_hash`, `is_online`, `last_active_time`) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            account_info['account'],
                            account_info['password_hash'],
                            account_info['role'],
                            account_info['nickname'],
                            None,  # signature 默认为 NULL
                            account_info['avatar_path'],
                            account_info.get('security_question'),
                            account_info.get('security_answer_hash'),
                            0,  # is_online默认为0（离线）
                            None  # last_active_time默认为NULL
                        ))
                        print(f"  [OK] 已创建账号: {account_info['account']} ({account_info['nickname']}, 角色: {account_info['role']})")
                    except Exception as e:
                        # 如果新字段不存在，使用旧表结构（兼容旧数据库）
                        error_msg = str(e).lower()
                        if 'unknown column' in error_msg or 'is_online' in error_msg or 'last_active_time' in error_msg:
                            print(f"  [WARN] 表结构较旧，使用兼容模式创建账号")
                            cursor.execute("""
                                INSERT INTO `users` (`account`, `password_hash`, `role`, `nickname`, `signature`, `avatar_path`, `security_question`, `security_answer_hash`) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                account_info['account'],
                                account_info['password_hash'],
                                account_info['role'],
                                account_info['nickname'],
                                None,  # signature 默认为 NULL
                                account_info['avatar_path'],
                                account_info.get('security_question'),
                                account_info.get('security_answer_hash')
                            ))
                            print(f"  [OK] 已创建账号: {account_info['account']} ({account_info['nickname']}, 角色: {account_info['role']})")
                        else:
                            # 其他错误，抛出异常
                            raise
        
        conn.commit()
        print("[OK] 默认账号创建完成")
    except Exception as e:
        print(f"[ERROR] 创建默认账号失败: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()


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
        print("[OK] MySQL服务器连接成功")
        
        # 确保数据库存在并切换到该数据库
        with conn.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS java_project CHARACTER SET utf8mb4")
            cursor.execute("USE java_project")
            conn.commit()
        print("[OK] 数据库java_project已准备就绪")
        print()
    except Exception as e:
        print(f"[ERROR] MySQL服务器连接失败: {e}")
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
            # 创建默认账号
            print("\n正在创建默认账号...")
            create_default_accounts(conn)
            
            print("\n" + "=" * 60)
            print("[OK] 数据库初始化成功完成！")
            print("=" * 60)
            print("\n默认账户:")
            print("  超级管理员账号: 111111111")
            print("  超级管理员密码: 123456")
            print("  管理员账号: 123456789")
            print("  管理员密码: 123456")
            print("  测试用户账号: 987654321")
            print("  测试用户密码: 123456")
            print("\n请及时修改默认密码！")
            return 0
        else:
            print("\n[WARNING] 数据库初始化完成，但存在一些错误")
            print("请检查上面的错误信息")
            return 1
            
    except Exception as e:
        print(f"\n[ERROR] 发生未预期的错误: {e}")
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

