# -*- coding: utf-8 -*-
"""
AI自动标注模块
监听数据库增量（INSERT/UPDATE），调用LLM生成JSON标注，写入annotation_records表
失败时写入死信队列
"""
import os
import sys
import json
import time
import threading
from typing import Dict, Optional, List
from datetime import datetime
from dotenv import load_dotenv
from pydantic import SecretStr

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.realpath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

from db_connection import get_user_db_connection, get_default_db_connection
from pymysql.cursors import DictCursor

load_dotenv(override=True)

ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")


class AutoAnnotationService:
    """AI自动标注服务"""
    
    def __init__(self):
        self.running = False
        self.check_interval = 10  # 每10秒检查一次
        self.processed_ids = set()  # 已处理的资源ID集合
        self.dead_letter_queue = []  # 死信队列
        
    def start(self):
        """启动自动标注服务"""
        if self.running:
            print("[自动标注] 服务已在运行")
            return
        
        self.running = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        print("[自动标注] 服务已启动")
    
    def stop(self):
        """停止自动标注服务"""
        self.running = False
        print("[自动标注] 服务已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                self._check_and_annotate()
            except Exception as e:
                print(f"[自动标注] 监控循环错误: {e}")
                import traceback
                traceback.print_exc()
            
            time.sleep(self.check_interval)
    
    def _check_and_annotate(self):
        """检查并标注新增/更新的资源"""
        try:
            conn = get_default_db_connection()
            if not conn:
                return
            
            try:
                with conn.cursor(DictCursor) as cursor:
                    # 检查cultural_resources表的新增/更新记录
                    cursor.execute("""
                        SELECT id, title, resource_type, content_feature_data, source_from
                        FROM cultural_resources
                        WHERE id NOT IN (
                            SELECT DISTINCT resource_id 
                            FROM annotation_tasks 
                            WHERE resource_source = 'cultural_resources' 
                            AND status IN ('已完成', 'AI标注完成')
                        )
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    resources = cursor.fetchall()
                    
                    for resource in resources:
                        if resource['id'] in self.processed_ids:
                            continue
                        
                        try:
                            self._annotate_resource(resource, 'cultural_resources')
                            self.processed_ids.add(resource['id'])
                        except Exception as e:
                            print(f"[自动标注] 标注资源 {resource['id']} 失败: {e}")
                            self._add_to_dead_letter_queue(resource, str(e))
                    
                    # 检查cultural_resources_from_user表的新增/更新记录
                    cursor.execute("""
                        SELECT id, title, resource_type, content_feature_data
                        FROM cultural_resources_from_user
                        WHERE id NOT IN (
                            SELECT DISTINCT resource_id 
                            FROM annotation_tasks 
                            WHERE resource_source = 'cultural_resources_from_user' 
                            AND status IN ('已完成', 'AI标注完成')
                        )
                        AND ai_review_status = 'passed'
                        ORDER BY upload_time DESC
                        LIMIT 10
                    """)
                    user_resources = cursor.fetchall()
                    
                    for resource in user_resources:
                        if resource['id'] in self.processed_ids:
                            continue
                        
                        try:
                            self._annotate_resource(resource, 'cultural_resources_from_user')
                            self.processed_ids.add(resource['id'])
                        except Exception as e:
                            print(f"[自动标注] 标注资源 {resource['id']} 失败: {e}")
                            self._add_to_dead_letter_queue(resource, str(e))
                    
                    # 检查AIGC_cultural_resources表的新增/更新记录
                    cursor.execute("""
                        SELECT id, title, resource_type, content_feature_data, source_from
                        FROM AIGC_cultural_resources
                        WHERE id NOT IN (
                            SELECT DISTINCT resource_id 
                            FROM annotation_tasks 
                            WHERE resource_source = 'AIGC_cultural_resources' 
                            AND status IN ('已完成', 'AI标注完成')
                        )
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    aigc_resources = cursor.fetchall()
                    
                    for resource in aigc_resources:
                        if resource['id'] in self.processed_ids:
                            continue
                        
                        try:
                            self._annotate_resource(resource, 'AIGC_cultural_resources')
                            self.processed_ids.add(resource['id'])
                        except Exception as e:
                            print(f"[自动标注] 标注资源 {resource['id']} 失败: {e}")
                            self._add_to_dead_letter_queue(resource, str(e))
                            
            finally:
                conn.close()
        except Exception as e:
            print(f"[自动标注] 检查失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_or_create_system_user(self, cursor) -> int:
        """获取或创建系统用户（用于自动标注）"""
        try:
            # 检查是否存在系统用户（account='99999999'）
            cursor.execute("SELECT id FROM users WHERE account = '99999999' LIMIT 1")
            user = cursor.fetchone()
            
            if user:
                return user['id']
            
            # 创建系统用户
            import hashlib
            password_hash = hashlib.sha256("system_user_password".encode()).hexdigest()
            system_account = '99999999'  # 8位数字，作为系统账号
            
            cursor.execute("""
                INSERT INTO users (account, password_hash, role, nickname, created_at)
                VALUES (%s, %s, '管理员', '系统用户', NOW())
            """, (system_account, password_hash))
            
            system_user_id = cursor.lastrowid
            print(f"[自动标注] 创建系统用户ID: {system_user_id}")
            return system_user_id
        except Exception as e:
            # 如果创建失败，尝试查找任何管理员用户
            cursor.execute("SELECT id FROM users WHERE role = '管理员' LIMIT 1")
            admin_user = cursor.fetchone()
            if admin_user:
                return admin_user['id']
            raise Exception(f"无法获取或创建系统用户: {e}")
    
    def _annotate_resource(self, resource: Dict, resource_source: str):
        """标注单个资源"""
        try:
            # 初始化LLM模型
            from langchain_community.chat_models import ChatTongyi
            if not ALIYUN_API_KEY:
                raise Exception("未配置阿里云API密钥")
            
            model = ChatTongyi(api_key=SecretStr(ALIYUN_API_KEY), model="qwen-turbo")
            
            # 构建提示词
            content_data = resource.get('content_feature_data', '')
            if isinstance(content_data, str):
                try:
                    content_data = json.loads(content_data)
                except:
                    pass
            
            text_content = ''
            if isinstance(content_data, dict):
                text_content = content_data.get('text', '') or content_data.get('title', '')
            else:
                text_content = str(content_data)
            
            title = resource.get('title', '')
            resource_type = resource.get('resource_type', '')
            
            prompt = f"""
你是一位专业的文化资源标注专家。请对以下文化资源进行自动标注，提取实体信息。

资源标题：{title}
资源类型：{resource_type}
资源内容：{text_content[:2000]}

请按照以下JSON格式输出标注结果：
{{
    "entity_name": "实体名称（文化资源的名称）",
    "entity_type": "实体类型（人物、作品、事件、地点、其他）",
    "description": "描述",
    "source": "来源",
    "period_era": "时期年代（如果有）",
    "geo_coordinates": "地理坐标（如果有）",
    "cultural_region": "文化区域（如果有）",
    "style_features": "风格特征（如果有）",
    "cultural_value": "文化价值（如果有）",
    "related_images_url": "相关图像链接（如果有）",
    "digital_resource_link": "数字资源链接（如果有）"
}}

要求：
1. 必须严格按照JSON格式输出，不要包含任何其他文字
2. 如果某个字段没有信息，使用空字符串""
3. entity_type必须是以下之一：人物、作品、事件、地点、其他
4. 描述要详细、准确，体现文化资源的特征
"""
            
            # 调用LLM生成标注
            response = model.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 解析JSON结果
            try:
                # 尝试提取JSON部分
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0].strip()
                
                annotation_data = json.loads(content)
            except json.JSONDecodeError as e:
                raise Exception(f"LLM返回的JSON格式错误: {e}, 内容: {content[:200]}")
            
            # 创建标注任务
            conn = get_default_db_connection()
            if not conn:
                raise Exception("数据库连接失败")
            
            try:
                with conn.cursor(DictCursor) as cursor:
                    # 获取或创建系统用户
                    system_user_id = self._get_or_create_system_user(cursor)
                    
                    # 创建标注任务
                    cursor.execute("""
                        INSERT INTO annotation_tasks (resource_id, resource_source, task_type, annotation_method, status)
                        VALUES (%s, %s, '实体', 'ai', 'AI标注中')
                    """, (resource['id'], resource_source))
                    task_id = cursor.lastrowid
                    
                    # 创建标注记录（使用系统用户ID）
                    cursor.execute("""
                        INSERT INTO annotation_records (
                            task_id, annotator_id, annotation_data, annotation_source,
                            entity_name, entity_type, description, source,
                            period_era, geo_coordinates, cultural_region,
                            style_features, cultural_value, related_images_url, digital_resource_link
                        )
                        VALUES (%s, %s, %s, 'ai', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_id, system_user_id, json.dumps(annotation_data, ensure_ascii=False),
                        annotation_data.get('entity_name', ''),
                        annotation_data.get('entity_type', '其他'),
                        annotation_data.get('description', ''),
                        annotation_data.get('source', ''),
                        annotation_data.get('period_era', ''),
                        annotation_data.get('geo_coordinates', ''),
                        annotation_data.get('cultural_region', ''),
                        annotation_data.get('style_features', ''),
                        annotation_data.get('cultural_value', ''),
                        annotation_data.get('related_images_url', ''),
                        annotation_data.get('digital_resource_link', '')
                    ))
                    
                    # 更新任务状态
                    cursor.execute("""
                        UPDATE annotation_tasks 
                        SET status = 'AI标注完成' 
                        WHERE id = %s
                    """, (task_id,))
                    
                    conn.commit()
                    print(f"[自动标注] 成功标注资源 {resource['id']} (任务ID: {task_id})")
                    
            finally:
                conn.close()
                
        except Exception as e:
            raise Exception(f"标注资源失败: {str(e)}")
    
    def _add_to_dead_letter_queue(self, resource: Dict, error: str):
        """添加到死信队列"""
        dead_letter = {
            'resource_id': resource.get('id'),
            'resource_source': resource.get('source', 'unknown'),
            'error': error,
            'timestamp': datetime.now().isoformat(),
            'resource_data': resource
        }
        self.dead_letter_queue.append(dead_letter)
        
        # 限制死信队列大小
        if len(self.dead_letter_queue) > 1000:
            self.dead_letter_queue.pop(0)
        
        print(f"[自动标注] 添加到死信队列: 资源ID {resource.get('id')}, 错误: {error}")
    
    def get_dead_letter_queue(self) -> List[Dict]:
        """获取死信队列"""
        return self.dead_letter_queue.copy()


# 全局服务实例
_auto_annotation_service = None

def get_auto_annotation_service() -> AutoAnnotationService:
    """获取自动标注服务实例"""
    global _auto_annotation_service
    if _auto_annotation_service is None:
        _auto_annotation_service = AutoAnnotationService()
    return _auto_annotation_service

