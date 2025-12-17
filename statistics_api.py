# -*- coding: utf-8 -*-
"""
统计数据API接口
用于DataEase等数据可视化工具集成
提供访问人次、上传数量、AIGC使用量等统计数据
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, date
from db_connection import get_user_db_connection
from typing import Dict, Optional

statistics_bp = Blueprint('statistics', __name__)


def get_today_date() -> date:
    """获取当前日期（用于今日统计）"""
    return date.today()


def get_statistics() -> Dict:
    """
    获取所有统计数据
    
    Returns:
        Dict: 包含所有统计数据的字典
    """
    try:
        conn = get_user_db_connection()
        if not conn:
            return {"error": "数据库连接失败"}
        
        today = get_today_date()
        
        try:
            with conn.cursor() as cursor:
                # 1. 历史访问人次（去重的用户登录次数）
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as total_visits
                    FROM user_behavior_logs
                    WHERE behavior_type = '交互' 
                    AND content LIKE '用户登录%'
                """)
                total_visits = cursor.fetchone()[0] or 0
                
                # 2. 今日访问人次（今日登录的独立用户数）
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as today_visits
                    FROM user_behavior_logs
                    WHERE behavior_type = '交互' 
                    AND content LIKE '用户登录%'
                    AND DATE(timestamp) = %s
                """, (today,))
                today_visits = cursor.fetchone()[0] or 0
                
                # 3. 历史用户上传内容数量
                cursor.execute("""
                    SELECT COUNT(*) as total_uploads
                    FROM cultural_resources_from_user
                """)
                total_uploads = cursor.fetchone()[0] or 0
                
                # 4. 今日用户上传数量
                cursor.execute("""
                    SELECT COUNT(*) as today_uploads
                    FROM cultural_resources_from_user
                    WHERE DATE(upload_time) = %s
                """, (today,))
                today_uploads = cursor.fetchone()[0] or 0
                
                # 5. 历史AIGC使用总量（文字+图片）
                cursor.execute("""
                    SELECT COUNT(*) as total_aigc
                    FROM qa_messages
                    WHERE model IN ('text', 'image')
                """)
                total_aigc = cursor.fetchone()[0] or 0
                
                # 6. 今日AIGC使用总量
                cursor.execute("""
                    SELECT COUNT(*) as today_aigc
                    FROM qa_messages
                    WHERE model IN ('text', 'image')
                    AND DATE(create_time) = %s
                """, (today,))
                today_aigc = cursor.fetchone()[0] or 0
                
                # 7. 历史文字AIGC使用量
                cursor.execute("""
                    SELECT COUNT(*) as total_text_aigc
                    FROM qa_messages
                    WHERE model = 'text'
                """)
                total_text_aigc = cursor.fetchone()[0] or 0
                
                # 8. 今日文字AIGC使用量
                cursor.execute("""
                    SELECT COUNT(*) as today_text_aigc
                    FROM qa_messages
                    WHERE model = 'text'
                    AND DATE(create_time) = %s
                """, (today,))
                today_text_aigc = cursor.fetchone()[0] or 0
                
                # 9. 历史图片AIGC使用量
                cursor.execute("""
                    SELECT COUNT(*) as total_image_aigc
                    FROM qa_messages
                    WHERE model = 'image'
                """)
                total_image_aigc = cursor.fetchone()[0] or 0
                
                # 10. 今日图片AIGC使用量
                cursor.execute("""
                    SELECT COUNT(*) as today_image_aigc
                    FROM qa_messages
                    WHERE model = 'image'
                    AND DATE(create_time) = %s
                """, (today,))
                today_image_aigc = cursor.fetchone()[0] or 0
                
                return {
                    "success": True,
                    "data": {
                        "total_visits": total_visits,
                        "today_visits": today_visits,
                        "total_uploads": total_uploads,
                        "today_uploads": today_uploads,
                        "total_aigc": total_aigc,
                        "today_aigc": today_aigc,
                        "total_text_aigc": total_text_aigc,
                        "today_text_aigc": today_text_aigc,
                        "total_image_aigc": total_image_aigc,
                        "today_image_aigc": today_image_aigc,
                        "current_date": today.strftime("%Y-%m-%d")
                    }
                }
        finally:
            conn.close()
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@statistics_bp.route('/api/statistics', methods=['GET'])
def get_statistics_endpoint():
    """
    获取统计数据接口
    
    返回格式：
    {
        "success": true,
        "data": {
            "total_visits": 历史访问人次,
            "today_visits": 今日访问人次,
            "total_uploads": 历史用户上传内容数量,
            "today_uploads": 今日用户上传数量,
            "total_aigc": 历史AIGC使用总量,
            "today_aigc": 今日AIGC使用总量,
            "total_text_aigc": 历史文字AIGC使用量,
            "today_text_aigc": 今日文字AIGC使用量,
            "total_image_aigc": 历史图片AIGC使用量,
            "today_image_aigc": 今日图片AIGC使用量,
            "current_date": "当前日期"
        }
    }
    """
    result = get_statistics()
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@statistics_bp.route('/api/statistics/detailed', methods=['GET'])
def get_detailed_statistics():
    """
    获取详细统计数据（包含时间序列数据）
    
    查询参数：
    - days: 返回最近N天的数据（默认7天）
    """
    try:
        days = int(request.args.get('days', 7))
        conn = get_user_db_connection()
        if not conn:
            return jsonify({"success": False, "error": "数据库连接失败"}), 500
        
        try:
            with conn.cursor() as cursor:
                # 获取每日访问人次（最近N天）
                cursor.execute("""
                    SELECT DATE(timestamp) as date, COUNT(DISTINCT user_id) as visits
                    FROM user_behavior_logs
                    WHERE behavior_type = '交互' 
                    AND content LIKE '用户登录%'
                    AND DATE(timestamp) >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                """, (days,))
                daily_visits = {row[0].strftime("%Y-%m-%d"): row[1] for row in cursor.fetchall()}
                
                # 获取每日上传数量（最近N天）
                cursor.execute("""
                    SELECT DATE(upload_time) as date, COUNT(*) as uploads
                    FROM cultural_resources_from_user
                    WHERE DATE(upload_time) >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                    GROUP BY DATE(upload_time)
                    ORDER BY date DESC
                """, (days,))
                daily_uploads = {row[0].strftime("%Y-%m-%d"): row[1] for row in cursor.fetchall()}
                
                # 获取每日AIGC使用量（最近N天）
                cursor.execute("""
                    SELECT DATE(create_time) as date, 
                           COUNT(*) as total,
                           SUM(CASE WHEN model = 'text' THEN 1 ELSE 0 END) as text_count,
                           SUM(CASE WHEN model = 'image' THEN 1 ELSE 0 END) as image_count
                    FROM qa_messages
                    WHERE model IN ('text', 'image')
                    AND DATE(create_time) >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                    GROUP BY DATE(create_time)
                    ORDER BY date DESC
                """, (days,))
                daily_aigc = {}
                for row in cursor.fetchall():
                    daily_aigc[row[0].strftime("%Y-%m-%d")] = {
                        "total": row[1],
                        "text": row[2],
                        "image": row[3]
                    }
                
                return jsonify({
                    "success": True,
                    "data": {
                        "daily_visits": daily_visits,
                        "daily_uploads": daily_uploads,
                        "daily_aigc": daily_aigc,
                        "days": days
                    }
                })
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

