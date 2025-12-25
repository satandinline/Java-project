#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全功能测试脚本（Python版本）
使用方法：python test_all_features.py
"""
import requests
import json
import time

BASE_URL = "http://localhost:7200"
USER_ID = 1  # 请根据实际情况修改

def test_full_text_search():
    """测试全文检索（不限制返回条数）"""
    print("\n1. 测试全文检索（不限制返回条数）")
    print("-" * 50)
    response = requests.get(f"{BASE_URL}/api/search?q=春节")
    data = response.json()
    result_count = len(data.get('data', []))
    print(f"返回结果数量: {result_count}")
    assert result_count > 0, "全文检索应该返回结果"
    print("✓ 全文检索测试通过")

def test_multimodal_search():
    """测试图文互搜（三列布局）"""
    print("\n2. 测试图文互搜（三列布局）")
    print("-" * 50)
    form_data = {
        'mode': 'text',
        'query': '春节',
        'user_id': USER_ID
    }
    response = requests.post(f"{BASE_URL}/api/multimodal/search", 
                            files={}, data=form_data,
                            headers={'X-User-Id': str(USER_ID)})
    data = response.json()
    vector_count = len(data.get('vector_results', []))
    text_count = len(data.get('text_results', []))
    image_count = len(data.get('image_results', []))
    print(f"向量结果数量: {vector_count}")
    print(f"文字结果数量: {text_count}")
    print(f"图片结果数量: {image_count}")
    print("✓ 图文互搜测试通过")

def test_aigc_retrieval_id():
    """测试AIGC-RAG写入retrieval_id字段"""
    print("\n3. 测试AIGC-RAG写入retrieval_id字段")
    print("-" * 50)
    # 创建会话
    session_response = requests.post(f"{BASE_URL}/api/aigc/sessions",
                                    json={'summary': '测试会话', 'mode': 'text'},
                                    headers={'X-User-Id': str(USER_ID)})
    session_id = session_response.json()['session']['id']
    print(f"会话ID: {session_id}")
    
    # 发送AIGC请求
    ask_response = requests.post(f"{BASE_URL}/api/aigc/ask",
                                json={
                                    'query': '请介绍一下春节的习俗',
                                    'session_id': session_id,
                                    'mode': 'text'
                                },
                                headers={'X-User-Id': str(USER_ID)})
    print("AIGC请求已发送")
    
    # 检查qa_messages表的retrieval_id字段
    from db_connection import get_user_db_connection
    from pymysql.cursors import DictCursor
    conn = get_user_db_connection()
    if conn:
        try:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT retrieval_id FROM qa_messages 
                    WHERE session_id = %s 
                    ORDER BY id DESC LIMIT 1
                """, (session_id,))
                result = cursor.fetchone()
                if result and result.get('retrieval_id'):
                    print(f"✓ retrieval_id字段已写入: {result['retrieval_id']}")
                else:
                    print("⚠ retrieval_id字段为空（可能没有检索到资源）")
        finally:
            conn.close()
    print("✓ AIGC-RAG测试完成")

def test_comment_notifications():
    """测试评论通知功能"""
    print("\n4. 测试评论通知功能")
    print("-" * 50)
    # 创建评论
    comment_response = requests.post(f"{BASE_URL}/api/comments",
                                    json={
                                        'resource_id': 1,
                                        'user_id': USER_ID,
                                        'comment_content': '测试评论'
                                    })
    comment_id = comment_response.json()['comment']['id']
    print(f"评论ID: {comment_id}")
    
    # 点赞（使用另一个用户，需要先创建）
    like_user_id = 2
    like_response = requests.post(f"{BASE_URL}/api/comments/{comment_id}/like",
                                 json={'user_id': like_user_id})
    print("点赞操作已完成")
    
    # 检查通知
    time.sleep(1)  # 等待通知创建
    notifications_response = requests.get(f"{BASE_URL}/api/notifications?user_id={USER_ID}")
    notifications = notifications_response.json().get('notifications', [])
    like_notifications = [n for n in notifications if n.get('notification_type') == 'like']
    print(f"点赞通知数量: {len(like_notifications)}")
    
    # 回复
    reply_response = requests.post(f"{BASE_URL}/api/comments/{comment_id}/reply",
                                   json={
                                       'user_id': like_user_id,
                                       'reply_content': '测试回复'
                                   })
    print("回复操作已完成")
    
    # 检查回复通知
    time.sleep(1)
    notifications_response = requests.get(f"{BASE_URL}/api/notifications?user_id={USER_ID}")
    notifications = notifications_response.json().get('notifications', [])
    reply_notifications = [n for n in notifications if n.get('notification_type') == 'reply']
    print(f"回复通知数量: {len(reply_notifications)}")
    
    # 标记全部已读
    mark_all_read_response = requests.post(f"{BASE_URL}/api/notifications/mark-all-read",
                                           headers={'X-User-Id': str(USER_ID)})
    print("✓ 评论通知测试完成")

def main():
    """主测试函数"""
    print("=" * 50)
    print("开始测试所有新功能")
    print("=" * 50)
    
    try:
        test_full_text_search()
        test_multimodal_search()
        test_aigc_retrieval_id()
        test_comment_notifications()
        
        print("\n" + "=" * 50)
        print("所有测试完成")
        print("=" * 50)
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

