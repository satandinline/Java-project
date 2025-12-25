# -*- coding: utf-8 -*-
"""
AIGC API服务器工具函数
提供数据库连接管理、错误处理等公共功能
"""

import functools
from contextlib import contextmanager
from typing import Optional, Dict, Any, Callable
from flask import jsonify
from pymysql.cursors import DictCursor
from db_connection import get_user_db_connection


@contextmanager
def get_db_connection(user_id: Optional[int] = None):
    """
    数据库连接上下文管理器
    自动处理连接的获取和关闭
    
    Usage:
        with get_db_connection(user_id) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users")
                result = cursor.fetchall()
    """
    conn = None
    try:
        conn = get_user_db_connection(user_id)
        if not conn:
            raise Exception("数据库连接失败")
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def db_operation(user_id_param: str = 'user_id', require_auth: bool = True):
    """
    数据库操作装饰器
    自动处理数据库连接、错误处理和响应格式化
    
    Args:
        user_id_param: 请求中用户ID参数名（'user_id'或从header获取）
        require_auth: 是否需要用户认证
    
    Usage:
        @app.route('/api/test', methods=['GET'])
        @db_operation(user_id_param='user_id')
        def test_endpoint(conn, cursor, user_id):
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return {'users': cursor.fetchall()}
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # 获取用户ID
                from flask import request
                user_id = None
                
                if require_auth:
                    if user_id_param == 'user_id':
                        # 从请求参数或header获取
                        user_id = request.args.get('user_id', type=int) or \
                                 request.headers.get('X-User-Id', type=int)
                    else:
                        user_id = kwargs.get(user_id_param)
                    
                    if not user_id:
                        return jsonify({
                            'success': False,
                            'message': '缺少用户ID'
                        }), 400
                
                # 使用数据库连接上下文管理器
                with get_db_connection(user_id) as conn:
                    with conn.cursor(DictCursor) as cursor:
                        # 调用原函数
                        result = func(conn=conn, cursor=cursor, user_id=user_id, *args, **kwargs)
                        
                        # 如果函数返回字典，自动格式化为JSON响应
                        if isinstance(result, dict):
                            if 'success' not in result:
                                result['success'] = True
                            return jsonify(result)
                        
                        # 如果函数返回元组，假设是(数据, 状态码)
                        if isinstance(result, tuple):
                            data, status_code = result
                            if isinstance(data, dict) and 'success' not in data:
                                data['success'] = True
                            return jsonify(data), status_code
                        
                        # 其他情况直接返回
                        return result
                        
            except Exception as e:
                import traceback
                error_msg = str(e)
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'message': f'操作失败：{error_msg}'
                }), 500
                
        return wrapper
    return decorator


def success_response(data: Any = None, message: str = '操作成功') -> Dict[str, Any]:
    """
    创建成功响应
    
    Args:
        data: 响应数据
        message: 响应消息
    
    Returns:
        响应字典
    """
    response = {
        'success': True,
        'message': message
    }
    if data is not None:
        if isinstance(data, dict):
            response.update(data)
        else:
            response['data'] = data
    return response


def error_response(message: str, status_code: int = 400) -> tuple:
    """
    创建错误响应
    
    Args:
        message: 错误消息
        status_code: HTTP状态码
    
    Returns:
        (响应字典, 状态码)元组
    """
    return {
        'success': False,
        'message': message
    }, status_code


def optimize_comment_query(cursor, resource_id: int) -> list:
    """
    优化的评论查询（使用JOIN减少查询次数）
    
    Args:
        cursor: 数据库游标
        resource_id: 资源ID
    
    Returns:
        评论列表（包含回复）
    """
    # 一次性获取所有评论和回复
    cursor.execute("""
        SELECT 
            c.id as comment_id,
            c.resource_id,
            c.user_id as comment_user_id,
            c.comment_content,
            c.created_at as comment_created_at,
            cu.account as comment_account,
            cu.nickname as comment_nickname,
            cu.avatar_path as comment_avatar_path,
            (SELECT COUNT(*) FROM comment_likes WHERE comment_id = c.id) as like_count,
            r.id as reply_id,
            r.reply_user_id,
            r.reply_content,
            r.created_at as reply_created_at,
            ru.account as reply_account,
            ru.nickname as reply_nickname,
            ru.avatar_path as reply_avatar_path
        FROM user_comments c
        LEFT JOIN users cu ON c.user_id = cu.id
        LEFT JOIN comment_replies r ON c.id = r.comment_id
        LEFT JOIN users ru ON r.reply_user_id = ru.id
        WHERE c.resource_id = %s AND c.comment_status = 'approved'
        ORDER BY c.created_at DESC, r.created_at ASC
    """, (resource_id,))
    
    rows = cursor.fetchall()
    
    # 组织数据
    comments_dict = {}
    for row in rows:
        comment_id = row['comment_id']
        
        if comment_id not in comments_dict:
            comments_dict[comment_id] = {
                'id': comment_id,
                'resource_id': row['resource_id'],
                'user_id': row['comment_user_id'],
                'comment_content': row['comment_content'],
                'created_at': row['comment_created_at'],
                'account': row['comment_account'],
                'nickname': row['comment_nickname'],
                'avatar_path': row['comment_avatar_path'],
                'like_count': row['like_count'] or 0,
                'replies': []
            }
        
        # 添加回复
        if row['reply_id']:
            comments_dict[comment_id]['replies'].append({
                'id': row['reply_id'],
                'comment_id': comment_id,
                'reply_user_id': row['reply_user_id'],
                'reply_content': row['reply_content'],
                'created_at': row['reply_created_at'],
                'account': row['reply_account'],
                'nickname': row['reply_nickname'],
                'avatar_path': row['reply_avatar_path']
            })
    
    return list(comments_dict.values())


def get_user_info(cursor, user_id: int) -> Optional[Dict]:
    """
    获取用户信息（带缓存）
    
    Args:
        cursor: 数据库游标
        user_id: 用户ID
    
    Returns:
        用户信息字典或None
    """
    cursor.execute("""
        SELECT id, account, nickname, avatar_path, role, signature, security_question
        FROM users
        WHERE id = %s
    """, (user_id,))
    return cursor.fetchone()

