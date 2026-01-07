# -*- coding: utf-8 -*-
"""
统一的数据库连接配置文件
提供两种连接方式：
1. 爬虫专用连接（使用root账户）
2. 用户连接（使用登录用户的账户信息）
"""

import os
import pymysql
from pymysql.cursors import DictCursor
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv(override=True)

# ==================== 数据库配置（从环境变量获取） ====================
# 所有数据库配置都从.env文件读取，不提供硬编码的默认值
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = os.getenv("MYSQL_PORT")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")

# 验证必需的配置项
def validate_db_config():
    """验证数据库配置是否完整"""
    missing = []
    if not MYSQL_HOST:
        missing.append("MYSQL_HOST")
    if not MYSQL_PORT:
        missing.append("MYSQL_PORT")
    if not MYSQL_USER:
        missing.append("MYSQL_USER")
    if not MYSQL_PASSWORD:
        missing.append("MYSQL_PASSWORD")
    if not MYSQL_DB:
        missing.append("MYSQL_DB")
    
    if missing:
        raise ValueError(
            f"缺少必需的数据库配置环境变量: {', '.join(missing)}\n"
            f"请在.env文件中配置以下变量:\n"
            f"MYSQL_HOST=127.0.0.1\n"
            f"MYSQL_PORT=3306\n"
            f"MYSQL_USER=root\n"
            f"MYSQL_PASSWORD=your_password\n"
            f"MYSQL_DB=java_project"
        )
    return True

# 获取爬虫专用数据库配置（使用root账户，从环境变量读取）
def get_spider_db_config():
    """
    获取爬虫专用的数据库配置字典（从环境变量读取）
    
    Returns:
        dict: 数据库配置字典
    """
    validate_db_config()
    return {
        "host": MYSQL_HOST,
        "port": int(MYSQL_PORT),
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "database": MYSQL_DB.replace("-", "_") if "-" in MYSQL_DB else MYSQL_DB,
        "charset": "utf8mb4"
    }


def get_spider_db_connection():
    """
    获取爬虫专用的数据库连接（使用root账户）
    用于爬虫程序连接数据库
    
    Returns:
        pymysql.Connection: 数据库连接对象，失败返回None
    """
    try:
        config = get_spider_db_config()
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            charset=config["charset"],
            cursorclass=DictCursor
        )
        return conn
    except ValueError as e:
        print(f"数据库配置错误: {e}")
        return None
    except Exception as e:
        print(f"爬虫数据库连接失败: {e}")
        return None


def get_user_db_config(user_id: Optional[int] = None):
    """
    获取用户数据库配置
    如果提供了user_id，从login.py的AuthSystem获取用户特定的数据库配置
    否则使用环境变量中的配置
    
    Args:
        user_id: 用户ID，如果提供则从login.py获取该用户的数据库配置
    
    Returns:
        dict: 数据库配置字典
    """
    if user_id is not None:
        try:
            from login import AuthSystem
            auth_system = AuthSystem()
            user_config = auth_system.get_user_db_config(user_id)
            if user_config:
                return user_config
        except Exception as e:
            print(f"从login.py获取用户数据库配置失败: {e}，使用环境变量配置")
    
    # 使用环境变量配置
    validate_db_config()
    return {
        "host": MYSQL_HOST,
        "port": int(MYSQL_PORT),
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "database": MYSQL_DB.replace("-", "_") if "-" in MYSQL_DB else MYSQL_DB,
        "charset": "utf8mb4"
    }


def get_user_db_connection(user_id: Optional[int] = None):
    """
    获取用户数据库连接（使用登录用户的账户）
    用于RAG.py、image_RAG.py等需要用户权限的文件
    
    Args:
        user_id: 用户ID，如果提供则使用该用户的数据库配置
    
    Returns:
        pymysql.Connection: 数据库连接对象，失败返回None
    """
    config = get_user_db_config(user_id)
    # 如果config包含db_config键（从login.py返回的格式），提取db_config
    if isinstance(config, dict) and 'db_config' in config:
        db_config = config['db_config']
    elif isinstance(config, dict):
        # 如果直接是配置字典，直接使用
        db_config = config
    else:
        print(f"无效的数据库配置格式: {type(config)}")
        return None
    
    try:
        conn = pymysql.connect(
            host=db_config["host"],
            port=db_config["port"],
            user=db_config["user"],
            password=db_config["password"],
            database=db_config["database"],
            charset=db_config.get("charset", "utf8mb4"),
            cursorclass=DictCursor
        )
        return conn
    except Exception as e:
        print(f"用户数据库连接失败: {e}")
        return None


# ==================== 向后兼容的默认配置 ====================
# 为了保持向后兼容，提供默认的数据库配置
def get_default_db_config():
    """
    获取默认数据库配置（用于向后兼容）
    从环境变量读取配置
    
    Returns:
        dict: 数据库配置字典
    """
    validate_db_config()
    return {
        "host": MYSQL_HOST,
        "port": int(MYSQL_PORT),
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "database": MYSQL_DB.replace("-", "_") if "-" in MYSQL_DB else MYSQL_DB,
        "charset": "utf8mb4"
    }


def get_default_db_connection():
    """
    获取默认数据库连接（用于向后兼容）
    
    Returns:
        pymysql.Connection: 数据库连接对象，失败返回None
    """
    db_config = get_default_db_config()
    try:
        conn = pymysql.connect(
            host=db_config["host"],
            port=db_config["port"],
            user=db_config["user"],
            password=db_config["password"],
            database=db_config["database"],
            charset=db_config.get("charset", "utf8mb4"),
            cursorclass=DictCursor
        )
        return conn
    except Exception as e:
        print(f"默认数据库连接失败: {e}")
        return None


if __name__ == "__main__":
    # 测试连接
    print("测试爬虫数据库连接...")
    spider_conn = get_spider_db_connection()
    if spider_conn:
        print("✓ 爬虫数据库连接成功")
        spider_conn.close()
    else:
        print("✗ 爬虫数据库连接失败")
    
    print("\n测试用户数据库连接...")
    user_conn = get_user_db_connection()
    if user_conn:
        print("✓ 用户数据库连接成功")
        user_conn.close()
    else:
        print("✗ 用户数据库连接失败")

