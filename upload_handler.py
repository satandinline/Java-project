import os
import uuid
import json
import random
from datetime import datetime
from typing import Optional, Dict, Any
import pymysql
from pymysql.cursors import DictCursor
import hashlib

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
        处理用户上传资源（核心流程：保存文件→创建记录→触发AI审核+标注）
        :param user_id: 上传用户ID
        :param file_data: 文件二进制数据
        :param file_name: 文件名
        :param resource_type: 资源类型（文本/图像/音频/视频）
        :return: 上传结果
        """
        # 生成唯一文件名+存储路径
        unique_filename = f"{uuid.uuid4()}_{file_name}"
        file_path = os.path.join(self.upload_dir, unique_filename)
        file_format = file_name.split('.')[-1].lower() if '.' in file_name else ''  # 提取文件格式（小写统一）
        
        # 保存文件到本地
        with open(file_path, 'wb') as f:
            f.write(file_data)
      
   计算哈希并查重
    content_hash = self._calculate_file_hash(file_path)  # 调用哈希函数
    conn = None
    try:
        conn = self._get_db_connection()
        with conn.cursor() as cursor:
            # 检查cultural_resources_from_user表中是否存在相同哈希
            cursor.execute("""
                SELECT id FROM cultural_resources_from_user 
                WHERE content_hash = %s
            """, (content_hash,))
            if cursor.fetchone():  # 存在重复资源
                os.remove(file_path)  # 删除已保存的文件
                return {"success": False, "message": "上传失败：该资源已存在（重复内容）"}
            
            # 后续数据库操作...
    except Exception as e:
        # 异常处理：若数据库操作失败，删除已保存的文件
        if os.path.exists(file_path):
            os.remove(file_path)
        return {"success": False, "message": f"上传失败: {str(e)}"}
    finally:
        if conn:
            conn.close()
        # 写入数据库+触发AI流程
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                # 1. 插入资源记录（含上传用户、初始审核状态）
                cursor.execute("""
                    INSERT INTO cultural_resources 
                    (title, resource_type, file_format, source_from, source_url, content_feature_data,
                     upload_user_id, ai_review_status, manual_review_status, upload_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    file_name,
                    resource_type,
                    file_format,
                    'user_upload',
                    file_path,
                    '{}',  # 预留特征字段
                    user_id,  # 关联上传用户
                    'pending',  # AI审核初始状态：待审核
                    'pending',  # 人工审核初始状态：待审核
                    datetime.now()  # 上传时间
                ))
                resource_id = cursor.lastrowid
                
                # 2. 创建标注任务（默认AI标注）
                cursor.execute("""
                    INSERT INTO annotation_tasks 
                    (resource_id, task_type, annotation_method, status)
                    VALUES (%s, %s, %s, %s)
                """, (resource_id, '实体', 'ai', '待标注'))
                task_id = cursor.lastrowid
                
                conn.commit()
                # 3. 异步触发AI审核+标注（不阻塞上传响应）
                self.trigger_ai_review_and_annotation(task_id, resource_id)
                
                return {
                    "success": True,
                    "resource_id": resource_id,
                    "task_id": task_id,
                    "message": "资源上传成功，已自动触发AI审核和标注"
                }
        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"上传失败: {str(e)}"}
        finally:
            if conn:
                conn.close()
    
    def trigger_ai_review_and_annotation(self, task_id: int, resource_id: int) -> None:
        """
        异步触发AI审核+标注（合并流程，避免重复线程）
        :param task_id: 标注任务ID
        :param resource_id: 资源ID
        """
        from time import sleep
        import threading
        
        def mock_ai_process():
            """模拟AI审核+标注流程（实际项目替换为真实API调用）"""
            # 模拟API调用延迟（1-3秒）
            sleep(random.uniform(1, 3))
            
            # -------------------------- 1. 模拟AI审核 --------------------------
            # 实际逻辑：调用内容安全API（如阿里云/腾讯云）检测违规、合规性
            # 示例规则：90%概率通过，10%概率驳回（可自定义）
            ai_review_status = 'approved' if random.random() > 0.1 else 'rejected'
            ai_review_remark = {
                'approved': 'AI检测内容合规，无违规信息',
                'rejected': 'AI检测到疑似违规内容（如敏感词、违规图像）'
            }[ai_review_status]
            
            # -------------------------- 2. 模拟AI标注 --------------------------
            # 实际逻辑：调用NLP/图像识别API（如实体识别、标签提取）
            mock_annotation = {
                "entities": [
                    {"name": "示例实体1", "type": "人物", "confidence": round(random.uniform(0.7, 0.95), 2)},
                    {"name": "示例实体2", "type": "地点", "confidence": round(random.uniform(0.7, 0.95), 2)},
                    {"name": "示例实体3", "type": "事件", "confidence": round(random.uniform(0.7, 0.95), 2)}
                ],
                "description": "AI自动标注结果（基于实体识别模型）",
                "confidence_score": round(random.uniform(0.8, 0.98), 2)
            }
            
            # -------------------------- 3. 保存AI结果到数据库 --------------------------
            conn = self._get_db_connection()
            try:
                with conn.cursor() as cursor:
                    # 事务：同时更新审核状态和标注结果
                    # 3.1 更新AI审核状态
                    cursor.execute("""
                        UPDATE cultural_resources 
                        SET ai_review_status = %s, ai_review_remark = %s
                        WHERE id = %s
                    """, (ai_review_status, ai_review_remark, resource_id))
                    
                    # 3.2 更新标注任务状态为「已标注」
                    cursor.execute("""
                        UPDATE annotation_tasks 
                        SET status = %s 
                        WHERE id = %s
                    """, ('已标注', task_id))
                    
                    # 3.3 标记该任务旧标注为「非最新」（支持后续修改）
                    cursor.execute("""
                        UPDATE annotation_records 
                        SET is_latest = 0 
                        WHERE task_id = %s
                    """, (task_id,))
                    
                    # 3.4 插入AI标注记录（设为最新）
                    cursor.execute("""
                        INSERT INTO annotation_records 
                        (task_id, annotator_id, annotation_data, annotation_source, 
                         is_expert_reviewed, is_latest, create_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_id,
                        -1,  # 特殊标识：AI标注（非用户）
                        json.dumps(mock_annotation, ensure_ascii=False),  # JSON格式存储（安全+易解析）
                        'ai',
                        False,  # AI标注默认无需专家审核
                        1,  # 标记为最新标注结果
                        datetime.now()
                    ))
                    conn.commit()
                    print(f"AI流程完成：资源{resource_id} 审核状态：{ai_review_status}，标注任务{task_id}已更新")
            except Exception as e:
                print(f"AI审核/标注失败：{str(e)}")
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()
        
        # 启动异步线程（daemon=True：主线程退出时自动销毁）
        threading.Thread(target=mock_ai_process, daemon=True).start()
    
    def save_manual_review(self, admin_id: int, resource_id: int, review_status: str, review_remark: Optional[str] = None) -> Dict[str, Any]:
        """
        管理员提交人工审核结果（可覆盖AI审核结果）
        :param admin_id: 管理员ID（验证权限）
        :param resource_id: 待审核资源ID
        :param review_status: 审核状态（approved/rejected）
        :param review_remark: 审核备注（可选）
        :return: 保存结果
        """
        # 参数校验
        if review_status not in ['approved', 'rejected']:
            return {"success": False, "message": "审核状态仅支持：approved（通过）/ rejected（驳回）"}
        
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                # 1. 验证是否为管理员
                cursor.execute("SELECT role FROM users WHERE id = %s", (admin_id,))
                user_info = cursor.fetchone()
                if not user_info or user_info['role'] != '管理员':
                    return {"success": False, "message": "无权限执行审核：仅管理员可操作"}
                
                # 2. 验证资源是否存在
                cursor.execute("SELECT id FROM cultural_resources WHERE id = %s", (resource_id,))
                if not cursor.fetchone():
                    return {"success": False, "message": "资源不存在"}
                
                # 3. 更新人工审核状态（覆盖AI结果）
                cursor.execute("""
                    UPDATE cultural_resources 
                    SET manual_review_status = %s, manual_review_remark = %s
                    WHERE id = %s
                """, (review_status, review_remark or '无备注', resource_id))
                
                conn.commit()
                return {"success": True, "message": f"人工审核成功：资源{resource_id}已标记为{review_status}"}
        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"审核失败：{str(e)}"}
        finally:
            if conn:
                conn.close()
    
    def save_manual_annotation(self, task_id: int, user_id: int, annotation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        管理员/资源上传者提交人工标注（可修改AI标注结果）
        :param task_id: 标注任务ID
        :param user_id: 标注者ID（管理员/上传者）
        :param annotation_data: 人工标注数据（格式同AI标注）
        :return: 保存结果
        """
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                # 1. 验证任务存在性+获取资源信息
                cursor.execute("""
                    SELECT t.resource_id, cr.upload_user_id 
                    FROM annotation_tasks t
                    JOIN cultural_resources cr ON t.resource_id = cr.id
                    WHERE t.id = %s
                """, (task_id,))
                task_info = cursor.fetchone()
                if not task_info:
                    return {"success": False, "message": "标注任务不存在"}
                
                # 2. 权限校验：管理员 或 资源上传者
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_role = cursor.fetchone()['role']
                if user_role != '管理员' and task_info['upload_user_id'] != user_id:
                    return {"success": False, "message": "无权限标注：仅管理员或资源上传者可操作"}
                
                # 3. 更新标注任务状态为「已标注」（人工）
                cursor.execute("""
                    UPDATE annotation_tasks 
                    SET status = %s, annotation_method = %s
                    WHERE id = %s
                """, ('已标注', 'manual', task_id))
                
                # 4. 标记旧标注为「非最新」（实现修改AI结果的核心）
                cursor.execute("""
                    UPDATE annotation_records 
                    SET is_latest = 0 
                    WHERE task_id = %s
                """, (task_id,))
                
                # 5. 插入人工标注记录（设为最新）
                cursor.execute("""
                    INSERT INTO annotation_records 
                    (task_id, annotator_id, annotation_data, annotation_source, 
                     is_expert_reviewed, is_latest, create_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    task_id,
                    user_id,
                    json.dumps(annotation_data, ensure_ascii=False),  # JSON格式存储
                    'manual',
                    user_role == '管理员',  # 管理员标注视为专家审核
                    1,  # 标记为最新结果
                    datetime.now()
                ))
                
                conn.commit()
                return {"success": True, "message": "人工标注已保存（已覆盖AI标注结果）"}
        except Exception as e:
            if conn:
                conn.rollback()
            return {"success": False, "message": f"标注失败：{str(e)}"}
        finally:
            if conn:
                conn.close()
    
    def get_all_uploaded_resources(self, admin_id: int, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        管理员获取所有用户上传的资源（支持筛选：审核状态、资源类型等）
        :param admin_id: 管理员ID（验证权限）
        :param filters: 筛选条件（可选）：ai_review_status、manual_review_status、resource_type等
        :return: 资源列表（含审核/标注状态）
        """
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                # 1. 验证管理员权限
                cursor.execute("SELECT role FROM users WHERE id = %s", (admin_id,))
                user_info = cursor.fetchone()
                if not user_info or user_info['role'] != '管理员':
                    return {"success": False, "message": "无权限访问：仅管理员可查看所有资源"}
                
                # 2. 构建查询SQL（关联资源、任务、最新标注结果）
                query = """
                    SELECT 
                        cr.id AS resource_id,
                        cr.title, cr.resource_type, cr.file_format, cr.source_url AS file_path,
                        cr.upload_user_id, u.username AS upload_username,
                        cr.ai_review_status, cr.ai_review_remark,
                        cr.manual_review_status, cr.manual_review_remark,
                        cr.upload_time,
                        at.id AS task_id, at.status AS annotation_status, at.annotation_method,
                        ar.annotation_data AS latest_annotation, ar.annotation_source AS annotation_source
                    FROM cultural_resources cr
                    LEFT JOIN users u ON cr.upload_user_id = u.id
                    LEFT JOIN annotation_tasks at ON cr.id = at.resource_id
                    LEFT JOIN annotation_records ar ON at.id = ar.task_id AND ar.is_latest = 1
                """
                
                # 3. 处理筛选条件
                params = []
                if filters:
                    where_clauses = []
                    if 'ai_review_status' in filters:
                        where_clauses.append("cr.ai_review_status = %s")
                        params.append(filters['ai_review_status'])
                    if 'manual_review_status' in filters:
                        where_clauses.append("cr.manual_review_status = %s")
                        params.append(filters['manual_review_status'])
                    if 'resource_type' in filters:
                        where_clauses.append("cr.resource_type = %s")
                        params.append(filters['resource_type'])
                    if 'upload_user_id' in filters:
                        where_clauses.append("cr.upload_user_id = %s")
                        params.append(filters['upload_user_id'])
                    if where_clauses:
                        query += " WHERE " + " AND ".join(where_clauses)
                
                # 4. 按上传时间倒序（最新上传在前）
                query += " ORDER BY cr.upload_time DESC"
                
                cursor.execute(query, params)
                resources = cursor.fetchall()
                
                # 5. 格式化标注数据（JSON字符串转字典）
                for res in resources:
                    if res['latest_annotation']:
                        try:
                            res['latest_annotation'] = json.loads(res['latest_annotation'])
                        except:
                            res['latest_annotation'] = None
                
                return {
                    "success": True,
                    "resources": resources,
                    "total": len(resources),
                    "message": f"共查询到{len(resources)}条资源"
                }
        except Exception as e:
            return {"success": False, "message": f"查询失败：{str(e)}"}
        finally:
            if conn:
                conn.close()
    
    def get_annotation_tasks(self, user_id: int, status: Optional[str] = None) -> Dict[str, Any]:
        """
        获取标注任务列表（管理员可见所有，普通用户仅见自己上传的）
        :param user_id: 用户ID
        :param status: 任务状态筛选（可选：待标注/已标注）
        :return: 任务列表
        """
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                query = """
                    SELECT 
                        t.id, t.resource_id, t.task_type, t.status, t.annotation_method,
                        r.title, r.resource_type, r.ai_review_status, r.manual_review_status,
                        r.upload_user_id, u.username AS upload_username,
                        ar.annotation_data AS latest_annotation, ar.annotation_source AS annotation_source
                    FROM annotation_tasks t
                    JOIN cultural_resources r ON t.resource_id = r.id
                    LEFT JOIN users u ON r.upload_user_id = u.id
                    LEFT JOIN annotation_records ar ON t.id = ar.task_id AND ar.is_latest = 1
                """
                params = []
                where_clauses = []
                
                # 权限控制：管理员看所有，普通用户看自己上传的
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_role = cursor.fetchone()['role']
                if user_role != '管理员':
                    where_clauses.append("r.upload_user_id = %s")
                    params.append(user_id)
                
                # 状态筛选
                if status:
                    where_clauses.append("t.status = %s")
                    params.append(status)
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                cursor.execute(query, params)
                tasks = cursor.fetchall()
                
                # 格式化标注数据
                for task in tasks:
                    if task['latest_annotation']:
                        try:
                            task['latest_annotation'] = json.loads(task['latest_annotation'])
                        except:
                            task['latest_annotation'] = None
                
                return {"success": True, "tasks": tasks}
        except Exception as e:
            return {"success": False, "message": f"获取任务失败：{str(e)}"}
        finally:
            if conn:
                conn.close()
      import hashlib  # 需在文件顶部导入

def _calculate_file_hash(self, file_path: str) -> str:
    """计算文件的SHA-256哈希值"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):  # 分块读取大文件
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


