import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import pymysql
from pymysql.cursors import DictCursor

class ResourceUploader:
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.upload_dir = "uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
        
    def _get_db_connection(self):
        """获取数据库连接"""
        return pymysql.connect(
            host=self.db_config.get("host"),
            user=self.db_config.get("user"),
            password=self.db_config.get("password"),
            database=self.db_config.get("database"),
            cursorclass=DictCursor
        )
    
    def upload_resource(self, user_id: int, file_data, file_name: str, resource_type: str) -> Dict[str, Any]:
        """
        处理用户上传资源
        :param user_id: 上传用户ID
        :param file_data: 文件二进制数据
        :param file_name: 文件名
        :param resource_type: 资源类型
        :return: 上传结果
        """
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4()}_{file_name}"
        file_path = os.path.join(self.upload_dir, unique_filename)
        
        # 保存文件
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # 保存到数据库
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                # 插入资源记录
                cursor.execute("""
                    INSERT INTO cultural_resources 
                    (title, resource_type, file_format, source_from, source_url, content_feature_data)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    file_name,
                    resource_type,
                    file_name.split('.')[-1] if '.' in file_name else '',
                    'user_upload',
                    file_path,
                    '{}'  # 空JSON
                ))
                
                resource_id = cursor.lastrowid
                
                # 创建标注任务
                cursor.execute("""
                    INSERT INTO annotation_tasks 
                    (resource_id, task_type, annotation_method, status)
                    VALUES (%s, %s, %s, %s)
                """, (resource_id, '实体', 'ai', '待标注'))
                
                conn.commit()
                
                # 触发AI标注
                self.trigger_ai_annotation(cursor.lastrowid)
                
                return {
                    "success": True,
                    "resource_id": resource_id,
                    "message": "资源上传成功，已提交AI标注任务"
                }
        except Exception as e:
            if conn:
                conn.rollback()
            return {
                "success": False,
                "message": f"上传失败: {str(e)}"
            }
        finally:
            if conn:
                conn.close()
    
    def trigger_ai_annotation(self, task_id: int) -> None:
        """
        触发AI标注（预留API接口位置）
        :param task_id: 标注任务ID
        """
        # TODO: 未来将接入实际的AI标注API
        # 目前使用模拟函数
        from time import sleep
        import threading
        
        def mock_ai_annotation():
            """模拟AI标注过程"""
            # 模拟API调用延迟
            sleep(3)
            
            # 模拟AI标注结果
            mock_annotation = {
                "entities": [
                    {"name": "示例实体1", "type": "人物", "confidence": 0.85},
                    {"name": "示例实体2", "type": "地点", "confidence": 0.92}
                ],
                "description": "AI自动标注结果"
            }
            
            # 保存AI标注结果
            conn = self._get_db_connection()
            try:
                with conn.cursor() as cursor:
                    # 更新任务状态
                    cursor.execute("""
                        UPDATE annotation_tasks 
                        SET status = %s 
                        WHERE id = %s
                    """, ('已标注', task_id))
                    
                    # 获取资源ID
                    cursor.execute("""
                        SELECT resource_id FROM annotation_tasks WHERE id = %s
                    """, (task_id,))
                    result = cursor.fetchone()
                    if not result:
                        return
                    
                    resource_id = result['resource_id']
                    
                    # 保存标注记录
                    cursor.execute("""
                        INSERT INTO annotation_records 
                        (task_id, annotator_id, annotation_data, annotation_source, is_expert_reviewed)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        task_id,
                        -1,  # 用-1表示AI标注，非用户
                        str(mock_annotation),
                        'ai',
                        False
                    ))
                    conn.commit()
            except Exception as e:
                print(f"AI标注模拟失败: {str(e)}")
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()
        
        # 启动线程执行模拟标注，避免阻塞
        threading.Thread(target=mock_ai_annotation, daemon=True).start()
    
    def save_manual_annotation(self, task_id: int, user_id: int, annotation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存人工标注结果
        :param task_id: 标注任务ID
        :param user_id: 标注用户ID
        :param annotation_data: 标注数据
        :return: 保存结果
        """
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                # 更新任务状态
                cursor.execute("""
                    UPDATE annotation_tasks 
                    SET status = %s, annotation_method = %s
                    WHERE id = %s
                """, ('已标注', 'manual', task_id))
                
                # 保存人工标注记录
                cursor.execute("""
                    INSERT INTO annotation_records 
                    (task_id, annotator_id, annotation_data, annotation_source, is_expert_reviewed)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    task_id,
                    user_id,
                    str(annotation_data),
                    'manual',
                    False  # 默认为非专家审核
                ))
                
                conn.commit()
                return {"success": True, "message": "人工标注已保存"}
        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"保存失败: {str(e)}"}
        finally:
            if conn:
                conn.close()
    
    def get_annotation_tasks(self, user_id: int, status: Optional[str] = None) -> Dict[str, Any]:
        """
        获取标注任务列表
        :param user_id: 用户ID
        :param status: 任务状态过滤，可选
        :return: 任务列表
        """
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                query = """
                    SELECT t.id, t.resource_id, t.task_type, t.status, t.annotation_method,
                           r.title, r.resource_type
                    FROM annotation_tasks t
                    JOIN cultural_resources r ON t.resource_id = r.id
                """
                params = []
                
                # 管理员可以看到所有任务，普通用户只能看到自己上传的
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_role = cursor.fetchone()['role']
                
                if user_role != '管理员':
                    query += " JOIN cultural_resources cr ON t.resource_id = cr.id "
                    query += " WHERE cr.upload_user_id = %s"
                    params.append(user_id)
                
                if status:
                    query += " AND t.status = %s"
                    params.append(status)
                
                cursor.execute(query, params)
                tasks = cursor.fetchall()
                
                return {"success": True, "tasks": tasks}
        except Exception as e:
            return {"success": False, "message": f"获取任务失败: {str(e)}"}
        finally:
            if conn:
                conn.close()