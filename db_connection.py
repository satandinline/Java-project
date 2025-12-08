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

# ==================== 默认数据库配置 ====================
# 默认MySQL root密码（如果环境变量中没有设置，使用此默认值）
DEFAULT_MYSQL_PASSWORD = "M17382930994c@"

# ==================== 爬虫专用数据库配置（使用root账户） ====================
SPIDER_DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": DEFAULT_MYSQL_PASSWORD,
    "database": "java_project",
    "charset": "utf8mb4"
}

# ==================== 用户数据库配置（从环境变量获取，如果没有则使用默认配置） ====================
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
# 如果环境变量中没有密码，使用默认密码
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", DEFAULT_MYSQL_PASSWORD)
MYSQL_DB = os.getenv("MYSQL_DB", "java_project")


def get_spider_db_connection():
    """
    获取爬虫专用的数据库连接（使用root账户）
    用于爬虫程序连接数据库
    
    Returns:
        pymysql.Connection: 数据库连接对象，失败返回None
    """
    try:
        conn = pymysql.connect(
            host=SPIDER_DB_CONFIG["host"],
            port=SPIDER_DB_CONFIG["port"],
            user=SPIDER_DB_CONFIG["user"],
            password=SPIDER_DB_CONFIG["password"],
            database=SPIDER_DB_CONFIG["database"],
            charset=SPIDER_DB_CONFIG["charset"],
            cursorclass=DictCursor
        )
        return conn
    except Exception as e:
        print(f"爬虫数据库连接失败: {e}")
        return None


def get_spider_db_config():
    """
    获取爬虫专用的数据库配置字典
    
    Returns:
        dict: 数据库配置字典
    """
    return SPIDER_DB_CONFIG.copy()


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
            print(f"从login.py获取用户数据库配置失败: {e}，使用默认配置")
    
    # 使用环境变量配置
    return {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
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
    优先使用环境变量，如果没有则使用爬虫配置
    
    Returns:
        dict: 数据库配置字典
    """
    if MYSQL_PASSWORD:
        return {
            "host": MYSQL_HOST,
            "port": MYSQL_PORT,
            "user": MYSQL_USER,
            "password": MYSQL_PASSWORD,
            "database": MYSQL_DB.replace("-", "_") if "-" in MYSQL_DB else MYSQL_DB,
            "charset": "utf8mb4"
        }
    else:
        # 如果没有设置密码，使用爬虫配置
        return get_spider_db_config()


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

