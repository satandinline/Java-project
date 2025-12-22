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
    
    注意：
    - 所有统计都不进行去重，统计的是总记录数
    - 访问人次统计所有登录记录的总数
    - AIGC使用人次等于使用总次数（每次使用都算一次）
    
    Returns:
        Dict: 包含所有统计数据的字典
    """
    try:
        conn = get_user_db_connection()
        if not conn:
            return {"success": False, "error": "数据库连接失败"}
        
        today = get_today_date()
        
        try:
            with conn.cursor() as cursor:
                # 1. 历史访问人次（所有登录记录总数，不去重）
                try:
                    cursor.execute("""
                        SELECT COUNT(*) as total_users
                        FROM user_behavior_logs
                        WHERE behavior_type = '交互' 
                        AND content LIKE '用户登录%'
                    """)
                    result = cursor.fetchone()
                    total_users = result.get('total_users', 0) if isinstance(result, dict) else (result[0] if result else 0) or 0
                except Exception as e:
                    print(f"查询历史访问人次失败: {e}")
                    import traceback
                    traceback.print_exc()
                    total_users = 0
                
                # 2. 今日访问人次（今日所有登录记录总数，不去重）
                # 使用数据库的CURDATE()函数，确保时区一致
                try:
                    cursor.execute("""
                        SELECT COUNT(*) as today_users
                        FROM user_behavior_logs
                        WHERE behavior_type = '交互' 
                        AND content LIKE '用户登录%'
                        AND DATE(timestamp) = CURDATE()
                    """)
                    result = cursor.fetchone()
                    today_users = result.get('today_users', 0) if isinstance(result, dict) else (result[0] if result else 0) or 0
                except Exception as e:
                    print(f"查询今日访问人次失败: {e}")
                    import traceback
                    traceback.print_exc()
                    today_users = 0
                
                # 3. 历史文字AIGC使用人次（所有用户发送消息总数，不去重，等于总次数）
                try:
                    # 直接统计所有text类型的消息，不检查user_message（因为每条记录都代表一次使用）
                    cursor.execute("""
                        SELECT COUNT(*) as total_text_count
                        FROM qa_messages
                        WHERE model = 'text'
                    """)
                    result = cursor.fetchone()
                    total_text_count = result.get('total_text_count', 0) if isinstance(result, dict) else (result[0] if result else 0) or 0
                    # 使用人次等于总次数（每次使用都算一次）
                    total_text_users = total_text_count
                except Exception as e:
                    print(f"查询历史文字AIGC使用人次失败: {e}")
                    import traceback
                    traceback.print_exc()
                    total_text_users = 0
                    total_text_count = 0
                
                # 4. 今日文字AIGC使用人次（今日所有用户发送消息总数，不去重，等于总次数）
                # 使用数据库的CURDATE()函数，确保时区一致
                try:
                    # 直接统计所有text类型的消息，不检查user_message（因为每条记录都代表一次使用）
                    cursor.execute("""
                        SELECT COUNT(*) as today_text_count
                        FROM qa_messages
                        WHERE model = 'text'
                        AND DATE(create_time) = CURDATE()
                    """)
                    result = cursor.fetchone()
                    today_text_count = result.get('today_text_count', 0) if isinstance(result, dict) else (result[0] if result else 0) or 0
                    # 使用人次等于总次数（每次使用都算一次）
                    today_text_users = today_text_count
                except Exception as e:
                    print(f"查询今日文字AIGC使用人次失败: {e}")
                    import traceback
                    traceback.print_exc()
                    today_text_users = 0
                    today_text_count = 0
                
                # 5. 历史图片AIGC使用人次（所有用户发送消息总数，不去重，等于总次数）
                try:
                    # 直接统计所有image类型的消息，不检查user_message（因为每条记录都代表一次使用）
                    cursor.execute("""
                        SELECT COUNT(*) as total_image_count
                        FROM qa_messages
                        WHERE model = 'image'
                    """)
                    result = cursor.fetchone()
                    total_image_count = result.get('total_image_count', 0) if isinstance(result, dict) else (result[0] if result else 0) or 0
                    # 使用人次等于总次数（每次使用都算一次）
                    total_image_users = total_image_count
                except Exception as e:
                    print(f"查询历史图片AIGC使用人次失败: {e}")
                    import traceback
                    traceback.print_exc()
                    total_image_users = 0
                    total_image_count = 0
                
                # 6. 今日图片AIGC使用人次（今日所有用户发送消息总数，不去重，等于总次数）
                # 使用数据库的CURDATE()函数，确保时区一致
                try:
                    # 直接统计所有image类型的消息，不检查user_message（因为每条记录都代表一次使用）
                    cursor.execute("""
                        SELECT COUNT(*) as today_image_count
                        FROM qa_messages
                        WHERE model = 'image'
                        AND DATE(create_time) = CURDATE()
                    """)
                    result = cursor.fetchone()
                    today_image_count = result.get('today_image_count', 0) if isinstance(result, dict) else (result[0] if result else 0) or 0
                    # 使用人次等于总次数（每次使用都算一次）
                    today_image_users = today_image_count
                except Exception as e:
                    print(f"查询今日图片AIGC使用人次失败: {e}")
                    import traceback
                    traceback.print_exc()
                    today_image_users = 0
                    today_image_count = 0
                
                # 7. 获取最近7天的趋势数据（以当前日期为基准，获取最近7天）
                trend_data = []
                try:
                    from datetime import timedelta
                    # 从6天前到今天（共7天），使用数据库的CURDATE()确保时区一致
                    # 先获取数据库的当前日期，用于验证
                    cursor.execute("SELECT CURDATE() as today")
                    db_today_result = cursor.fetchone()
                    db_today = db_today_result.get('today') if isinstance(db_today_result, dict) else db_today_result[0] if db_today_result else None
                    if isinstance(db_today, str):
                        db_today = datetime.strptime(db_today, '%Y-%m-%d').date()
                    elif isinstance(db_today, datetime):
                        db_today = db_today.date()
                    print(f"数据库当前日期: {db_today}, Python当前日期: {today}")
                    
                    for i in range(6, -1, -1):
                        # 使用数据库的日期函数计算目标日期，确保时区一致
                        cursor.execute("""
                            SELECT DATE_SUB(CURDATE(), INTERVAL %s DAY) as target_date
                        """, (i,))
                        result = cursor.fetchone()
                        if isinstance(result, dict):
                            target_date = result.get('target_date')
                        else:
                            target_date = result[0] if result else None
                        
                        if not target_date:
                            # 如果数据库查询失败，使用Python计算
                            target_date = today - timedelta(days=i)
                            print(f"  警告：使用Python计算日期 i={i}, date={target_date}")
                        else:
                            # 确保target_date是date对象
                            if isinstance(target_date, str):
                                try:
                                    from datetime import datetime
                                    target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
                                except:
                                    # 如果解析失败，尝试其他格式
                                    try:
                                        target_date = datetime.strptime(target_date, '%Y-%m-%d %H:%M:%S').date()
                                    except:
                                        # 如果还是失败，使用Python计算
                                        target_date = today - timedelta(days=i)
                                        print(f"  警告：日期解析失败，使用Python计算 i={i}, date={target_date}")
                            elif isinstance(target_date, datetime):
                                target_date = target_date.date()
                        
                        # 每日访问人次（所有登录记录总数，不去重）
                        # 对于今天（i=0），直接使用CURDATE()，与今日访问人次查询保持一致
                        # 对于其他日期，使用DATE_SUB
                        if i == 0:
                            # 今天：使用与"今日访问人次"相同的查询逻辑
                            cursor.execute("""
                                SELECT COUNT(*) as daily_users
                                FROM user_behavior_logs
                                WHERE behavior_type = '交互' 
                                AND content LIKE '用户登录%'
                                AND DATE(timestamp) = CURDATE()
                            """)
                        else:
                            # 其他日期：使用DATE_SUB
                            cursor.execute("""
                                SELECT COUNT(*) as daily_users
                                FROM user_behavior_logs
                                WHERE behavior_type = '交互' 
                                AND content LIKE '用户登录%'
                                AND DATE(timestamp) = DATE_SUB(CURDATE(), INTERVAL %s DAY)
                            """, (i,))
                        result = cursor.fetchone()
                        daily_users = result.get('daily_users', 0) if isinstance(result, dict) else (result[0] if result else 0) or 0
                        
                        # 调试输出
                        if i == 0:
                            print(f"  今天访问人次查询结果: {daily_users} (日期: {date_str})")
                        
                        # 每日文字AIGC使用人次（等于使用次数）
                        # 直接统计所有text类型的消息（每条记录代表一次用户使用）
                        # 对于今天（i=0），使用与"今日文字AIGC使用人次"相同的查询逻辑
                        if i == 0:
                            # 今天：使用与"今日文字AIGC使用人次"相同的查询逻辑
                            cursor.execute("""
                                SELECT COUNT(*) as text_count
                                FROM qa_messages
                                WHERE model = 'text'
                                AND DATE(create_time) = CURDATE()
                            """)
                        else:
                            # 其他日期：使用DATE_SUB
                            cursor.execute("""
                                SELECT COUNT(*) as text_count
                                FROM qa_messages
                                WHERE model = 'text'
                                AND DATE(create_time) = DATE_SUB(CURDATE(), INTERVAL %s DAY)
                            """, (i,))
                        result = cursor.fetchone()
                        text_count = result.get('text_count', 0) if isinstance(result, dict) else (result[0] if result else 0) or 0
                        
                        # 调试输出
                        if i == 0:
                            print(f"  今天文字AIGC查询结果: {text_count} (日期: {date_str})")
                        
                        # 每日图片AIGC使用人次（等于使用次数）
                        # 直接统计所有image类型的消息（每条记录代表一次用户使用）
                        # 对于今天（i=0），使用与"今日图片AIGC使用人次"相同的查询逻辑
                        if i == 0:
                            # 今天：使用与"今日图片AIGC使用人次"相同的查询逻辑
                            cursor.execute("""
                                SELECT COUNT(*) as image_count
                                FROM qa_messages
                                WHERE model = 'image'
                                AND DATE(create_time) = CURDATE()
                            """)
                        else:
                            # 其他日期：使用DATE_SUB
                            cursor.execute("""
                                SELECT COUNT(*) as image_count
                                FROM qa_messages
                                WHERE model = 'image'
                                AND DATE(create_time) = DATE_SUB(CURDATE(), INTERVAL %s DAY)
                            """, (i,))
                        result = cursor.fetchone()
                        image_count = result.get('image_count', 0) if isinstance(result, dict) else (result[0] if result else 0) or 0
                        
                        # 调试输出
                        if i == 0:
                            print(f"  今天图片AIGC查询结果: {image_count} (日期: {date_str})")
                        
                        # 每日文字+图片AIGC使用人次（等于总使用次数）
                        total_aigc_count = text_count + image_count
                        
                        # 确保target_date是date对象，用于格式化
                        if isinstance(target_date, date):
                            date_str = target_date.strftime("%Y-%m-%d")
                        elif isinstance(target_date, datetime):
                            date_str = target_date.date().strftime("%Y-%m-%d")
                        else:
                            date_str = str(target_date)
                            # 尝试解析字符串日期
                            try:
                                from datetime import datetime
                                parsed = datetime.strptime(date_str, '%Y-%m-%d')
                                date_str = parsed.strftime("%Y-%m-%d")
                            except:
                                pass
                        
                        # 调试输出（可以后续移除）
                        print(f"趋势数据 - i={i}, date={date_str}, daily_users={daily_users}, text_count={text_count}, image_count={image_count}")
                        
                        trend_data.append({
                            "date": date_str,
                            "daily_users": daily_users,
                            "text_count": text_count,
                            "image_count": image_count,
                            "total_aigc_count": total_aigc_count
                        })
                except Exception as e:
                    print(f"查询趋势数据失败: {e}")
                    import traceback
                    traceback.print_exc()
                    # 如果查询失败，至少返回7天的空数据
                    from datetime import timedelta
                    trend_data = []
                    for i in range(6, -1, -1):
                        target_date = today - timedelta(days=i)
                        trend_data.append({
                            "date": target_date.strftime("%Y-%m-%d"),
                            "daily_users": 0,
                            "text_count": 0,
                            "image_count": 0,
                            "total_aigc_count": 0
                        })
                
                # 调试输出：打印趋势数据
                print(f"返回的趋势数据条数: {len(trend_data)}")
                if trend_data:
                    print(f"第一条数据: {trend_data[0]}")
                    print(f"最后一条数据: {trend_data[-1]}")
                
                return {
                    "success": True,
                    "data": {
                        "total_users": total_users,
                        "today_users": today_users,
                        "total_text_users": total_text_users,
                        "total_text_count": total_text_count,
                        "today_text_users": today_text_users,
                        "today_text_count": today_text_count,
                        "total_image_users": total_image_users,
                        "total_image_count": total_image_count,
                        "today_image_users": today_image_users,
                        "today_image_count": today_image_count,
                        "trend_data": trend_data,
                        "current_date": today.strftime("%Y-%m-%d")
                    }
                }
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@statistics_bp.route('/api/statistics', methods=['GET'])
def get_statistics_endpoint():
    """
    获取统计数据接口（需要管理员或超级管理员权限）
    
    查询参数：
    - userId: 用户ID（用于权限检查）
    
    返回格式：
    {
        "success": true,
        "data": {
            "total_users": 历史访问人次（所有登录记录总数，不去重）,
            "today_users": 今日访问人次（今日所有登录记录总数，不去重）,
            "total_text_users": 历史文字AIGC使用人次（等于总次数，每次使用都算一次）,
            "total_text_count": 历史文字AIGC总次数,
            "today_text_users": 今日文字AIGC使用人次（等于总次数，每次使用都算一次）,
            "today_text_count": 今日文字AIGC总次数,
            "total_image_users": 历史图片AIGC使用人次（等于总次数，每次使用都算一次）,
            "total_image_count": 历史图片AIGC总次数,
            "today_image_users": 今日图片AIGC使用人次（等于总次数，每次使用都算一次）,
            "today_image_count": 今日图片AIGC总次数,
            "trend_data": [
                {
                    "date": "YYYY-MM-DD",
                    "daily_users": 每日访问人次（所有登录记录总数，不去重）,
                    "text_count": 每日文字AIGC使用人次（等于使用次数）,
                    "image_count": 每日图片AIGC使用人次（等于使用次数）,
                    "total_aigc_count": 每日文字+图片AIGC使用人次（等于总使用次数）
                },
                ...
            ],
            "current_date": "当前日期"
        }
    }
    """
    try:
        # 获取用户ID参数
        user_id = request.args.get('userId')
        if not user_id:
            return jsonify({'success': False, 'message': '未授权访问，请先登录'}), 401
        
        user_id = int(user_id)
        
        # 检查用户权限（管理员或超级管理员）
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_info = cursor.fetchone()
                if not user_info:
                    return jsonify({'success': False, 'message': '用户不存在'}), 404
                
                # 检查role字段是否为'管理员'或'超级管理员'
                # 兼容DictCursor和普通游标
                if isinstance(user_info, dict):
                    role = user_info.get('role')
                elif isinstance(user_info, tuple):
                    role = user_info[0]
                else:
                    role = None
                    
                if role != '管理员' and role != '超级管理员':
                    return jsonify({'success': False, 'message': '权限不足，仅管理员可访问'}), 403
        except Exception as e:
            print(f"权限检查失败: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'权限检查失败: {str(e)}'}), 500
        finally:
            # 关闭权限检查的连接
            if conn:
                conn.close()
        
        # 获取统计数据（get_statistics内部会创建新的数据库连接）
        try:
            result = get_statistics()
            if not result.get("success", False):
                error_msg = result.get('error', '获取统计数据失败')
                print(f"获取统计数据失败: {error_msg}")
                return jsonify({'success': False, 'message': error_msg}), 500
            
            # 返回统计数据
            return jsonify(result)
        except Exception as e:
            print(f"获取统计数据异常: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'获取统计数据失败: {str(e)}'}), 500
    except ValueError:
        return jsonify({'success': False, 'message': '无效的用户ID'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500


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

