import os
import uuid
import json
import random
from datetime import datetime
from typing import Optional, Dict, Any
import pymysql
from pymysql.cursors import DictCursor
import hashlib
import sys
import threading

# 添加项目根目录到路径，以便导入db_connection
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_connection import get_user_db_connection, get_user_db_config
from festival_name_utils import extract_and_convert_festival_name


class ResourceUploader:
    def __init__(self, user_id: Optional[int] = None, db_config: Optional[Dict[str, Any]] = None):
        """
        初始化资源上传器
        :param user_id: 用户ID，如果提供则使用该用户的数据库配置
        :param db_config: 数据库配置字典，如果提供则直接使用
        """
        self.user_id = user_id
        if db_config:
            self.db_config = db_config
        else:
            # 获取用户数据库配置
            config = get_user_db_config(user_id) if user_id else get_user_db_config()
            # 如果config包含db_config键（从login.py返回的格式），提取db_config
            if isinstance(config, dict) and 'db_config' in config:
                self.db_config = config['db_config']
            elif isinstance(config, dict):
                # 如果直接是配置字典，直接使用
                self.db_config = config
            else:
                # 如果返回的不是字典，尝试获取默认配置
                default_config = get_user_db_config()
                if isinstance(default_config, dict) and 'db_config' in default_config:
                    self.db_config = default_config['db_config']
                else:
                    self.db_config = default_config
        self.upload_dir = "uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
        
    def _get_db_connection(self):
        """获取数据库连接"""
        if self.user_id is None:
            # 如果没有user_id，尝试使用默认连接
            return get_user_db_connection()
        return get_user_db_connection(self.user_id)
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件的SHA-256哈希值用于查重"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # 分块读取大文件，避免内存占用过高
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def upload_resource(self, user_id: int, file_data, file_name: str, resource_type: str) -> Dict[str, Any]:
        """
        处理用户上传资源
        :param user_id: 上传用户ID
        :param file_data: 文件二进制数据
        :param file_name: 文件名
        :param resource_type: 资源类型
        :return: 上传结果
        """
        # 更新实例的user_id，确保使用正确的用户ID
        self.user_id = user_id
        
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4()}_{file_name}"
        file_path = os.path.join(self.upload_dir, unique_filename)
        
        # 保存文件
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # 计算文件哈希值
        content_hash = self._calculate_file_hash(file_path)
        
        # 保存到数据库
        conn = None
        try:
            conn = self._get_db_connection()
            if conn is None:
                # 如果连接失败，删除已保存的文件并返回错误
                if os.path.exists(file_path):
                    os.remove(file_path)
                return {
                    "success": False,
                    "message": "数据库连接失败，请检查数据库配置"
                }
            with conn.cursor() as cursor:
                # 查重校验：检查是否存在相同哈希的资源
                cursor.execute("""
                    SELECT id FROM cultural_resources_from_user 
                    WHERE content_hash = %s
                """, (content_hash,))
                if cursor.fetchone():
                    # 存在重复资源，删除文件并返回错误
                    os.remove(file_path)
                    return {
                        "success": False,
                        "message": "上传失败：该资源已存在（重复内容）"
                    }
                
                # 提取节日名称（从文件名或文件内容中）
                # 对于文本文件，尝试读取内容提取节日名称
                festival_title_en = "Traditional Festival"  # 默认值
                content_text = ""
                
                if resource_type == "文本":
                    try:
                        # 尝试读取文本文件内容
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content_text = f.read(1000)  # 读取前1000字符用于提取节日名称
                        if content_text:
                            festival_title_en = extract_and_convert_festival_name(content_text)
                    except:
                        # 如果读取失败，尝试从文件名提取
                        festival_title_en = extract_and_convert_festival_name(file_name)
                else:
                    # 对于图片文件，从文件名提取
                    festival_title_en = extract_and_convert_festival_name(file_name)
                
                # 插入用户上传资源表（title字段存储英文节日名称）
                cursor.execute("""
                    INSERT INTO cultural_resources_from_user 
                    (user_id, title, resource_type, file_format, content_feature_data,
                     content_hash, upload_time, ai_review_status, manual_review_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,  # 关联上传用户ID
                    festival_title_en,  # title字段存储英文节日名称
                    resource_type,
                    file_name.split('.')[-1] if '.' in file_name else '',
                    json.dumps({"file_name": file_name, "content_preview": content_text[:500]}, ensure_ascii=False) if content_text else '{}',
                    content_hash,  # 存储哈希值用于后续查重
                    datetime.now(),  # 上传时间
                    'pending',  # 初始AI审核状态
                    'pending'   # 初始人工审核状态
                ))
                
                resource_id = cursor.lastrowid  # 获取用户上传资源的ID
                
                # 创建标注任务（关联用户上传的资源ID，指定资源来源为cultural_resources_from_user）
                cursor.execute("""
                    INSERT INTO annotation_tasks 
                    (resource_id, resource_source, task_type, annotation_method, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, (resource_id, 'cultural_resources_from_user', '实体', 'ai', '待标注'))
                
                conn.commit()
                
                # 记录用户行为日志（上传行为属于"交互"类型）
                try:
                    cursor.execute("""
                        INSERT INTO user_behavior_logs 
                        (user_id, behavior_type, content, timestamp)
                        VALUES (%s, %s, %s, NOW())
                    """, (
                        user_id,
                        '交互',
                        f"上传资源：{file_name}（类型：{resource_type}）"
                    ))
                    conn.commit()
                except Exception as e:
                    print(f"记录用户行为日志失败: {e}")
                    # 不影响主流程，继续执行
                
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
            # 发生异常时删除已保存的文件
            if os.path.exists(file_path):
                os.remove(file_path)
            return {
                "success": False,
                "message": f"上传失败: {str(e)}"
            }
        finally:
            if conn:
                conn.close()
    
    
    def trigger_ai_annotation(self, task_id: int) -> None:
        """
        触发真实的AI标注（使用RAG系统）
        :param task_id: 标注任务ID
        """
        
        def real_ai_annotation():
            """真实的AI标注流程"""
            conn = None
            rag_system = None
            try:
                conn = self._get_db_connection()
                if not conn:
                    error_msg = "数据库连接失败"
                    print(f"[AI标注] 任务{task_id}: {error_msg}")
                    self._update_task_status_on_error(conn, task_id, error_msg)
                    return
                
                with conn.cursor() as cursor:
                    # 1. 获取标注任务和资源信息
                    cursor.execute("""
                        SELECT t.resource_id, t.resource_source,
                            cru.content_feature_data, cru.resource_type, cru.title
                        FROM annotation_tasks t
                        LEFT JOIN cultural_resources_from_user cru 
                            ON t.resource_id = cru.id 
                            AND t.resource_source = 'cultural_resources_from_user'
                        WHERE t.id = %s
                    """, (task_id,))
                    
                    task_info = cursor.fetchone()
                    if not task_info:
                        error_msg = "任务不存在"
                        print(f"[AI标注] 任务{task_id}: {error_msg}")
                        self._update_task_status_on_error(conn, task_id, error_msg)
                        return
                    
                    # 2. 解析资源内容
                    content_data = json.loads(task_info['content_feature_data'] or '{}')
                    content_text = content_data.get('content_preview', '')
                    
                    if not content_text:
                        error_msg = "无可标注内容"
                        print(f"[AI标注] 任务{task_id}: {error_msg}")
                        self._update_task_status_on_error(conn, task_id, error_msg)
                        return
                    
                    # 3. 调用RAG系统进行实体识别
                    from AIGC.RAG import CulturalResourceRAG
                    from langchain_community.chat_models import ChatTongyi
                    from pydantic import SecretStr
                    import os
                    
                    # 初始化模型
                    ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")
                    if not ALIYUN_API_KEY:
                        error_msg = "未配置API密钥"
                        print(f"[AI标注] 任务{task_id}: {error_msg}")
                        self._update_task_status_on_error(conn, task_id, error_msg)
                        return
                    
                    model = ChatTongyi(api_key=SecretStr(ALIYUN_API_KEY), model="qwen-turbo")
                    
                    # 创建RAG系统实例（在数据库操作之外创建，避免长时间占用连接）
                    rag_system = CulturalResourceRAG(
                        model=model,
                        persist_directory="./chroma_db_annotation",
                        database_name="java_project"
                    )
                    
                    # 先关闭数据库连接，RAG调用可能耗时较长
                    conn.close()
                    conn = None
                    
                    # 4. 构建标注提示词
                    annotation_prompt = f"""
    请从以下文化资源内容中识别并提取所有文化实体。

    资源标题: {task_info['title']}
    资源类型: {task_info['resource_type']}

    内容:
    {content_text}

    要求:
    1. 识别所有文化实体（人物、作品、事件、地点、其他）
    2. 为每个实体标注类型（人物/作品/事件/地点/其他）
    3. 评估识别的置信度（0-1之间）

    请以JSON格式返回，例如:
    {{
    "entities": [
        {{"name": "春节", "type": "事件", "confidence": 0.95}},
        {{"name": "王安石", "type": "人物", "confidence": 0.88}}
    ]
    }}
    """
                    
                    # 5. 调用RAG系统
                    print(f"[AI标注] 任务{task_id}: 开始AI标注...")
                    result = rag_system.ask(annotation_prompt)
                    
                    # 6. 解析标注结果
                    answer = result.get('answer', '')
                    entities = []
                    
                    try:
                        # 尝试从回答中提取JSON
                        import re
                        json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                        if json_match:
                            annotation_data = json.loads(json_match.group())
                            entities = annotation_data.get('entities', [])
                        else:
                            # 如果没有JSON，从key_entities中提取
                            key_entities = result.get('key_entities', [])
                            entities = [
                                {"name": e, "type": "其他", "confidence": 0.75}
                                for e in key_entities
                            ]
                    except Exception as e:
                        print(f"[AI标注] 任务{task_id}: 解析结果失败: {e}")
                        # 降级方案: 从key_entities提取
                        key_entities = result.get('key_entities', [])
                        entities = [
                            {"name": e, "type": "其他", "confidence": 0.75}
                            for e in key_entities
                        ]
                    
                    if not entities:
                        print(f"[AI标注] 任务{task_id}: 未识别到实体")
                        entities = [{"name": "未识别到实体", "type": "其他", "confidence": 0.0}]
                    
                    # 7. RAG调用完成后，重新获取数据库连接保存结果
                    conn = self._get_db_connection()
                    if not conn:
                        print(f"[AI标注] 任务{task_id}: 保存结果时数据库连接失败")
                        return
                    
                    try:
                        with conn.cursor() as cursor:
                            # 保存标注结果
                            annotation_result = {
                                "entities": entities,
                                "description": f"AI自动标注 (模型: qwen-turbo)",
                                "timestamp": str(datetime.now())
                            }
                            
                            cursor.execute("""
                                UPDATE annotation_tasks 
                                SET status = %s 
                                WHERE id = %s
                            """, ('已标注', task_id))
                            
                            cursor.execute("""
                                INSERT INTO annotation_records 
                                (task_id, annotator_id, annotation_data, annotation_source, is_expert_reviewed)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (
                                task_id,
                                -1,  # -1表示AI标注
                                json.dumps(annotation_result, ensure_ascii=False),
                                'ai',
                                False
                            ))
                            
                            conn.commit()
                            print(f"[AI标注] 任务{task_id}: 标注完成，识别{len(entities)}个实体")
                    finally:
                        if conn:
                            conn.close()
                    
            except Exception as e:
                error_msg = f"AI标注失败: {str(e)}"
                print(f"[AI标注] 任务{task_id}: {error_msg}")
                import traceback
                traceback.print_exc()
                # 更新任务状态为失败
                self._update_task_status_on_error(conn, task_id, error_msg)
            finally:
                # 清理RAG系统资源
                if rag_system and hasattr(rag_system, 'vector_store'):
                    try:
                        # Chroma向量数据库会自动管理资源，但可以显式清理
                        pass
                    except:
                        pass
                if conn:
                    conn.close()
        
        # 启动后台线程执行AI标注
        threading.Thread(target=real_ai_annotation, daemon=True).start()
    
    def _update_task_status_on_error(self, conn, task_id: int, error_msg: str):
        """
        更新任务状态为失败，并记录错误信息
        :param conn: 数据库连接（可能为None）
        :param task_id: 任务ID
        :param error_msg: 错误信息
        """
        if not conn:
            # 如果连接不存在，尝试获取新连接
            try:
                conn = self._get_db_connection()
            except:
                print(f"[AI标注] 任务{task_id}: 无法更新失败状态，数据库连接失败")
                return
        
        if not conn:
            return
            
        try:
            with conn.cursor() as cursor:
                # 更新任务状态为失败（可以添加一个'标注失败'状态，或保持'待标注'但记录错误）
                # 这里选择更新状态为'待标注'，但记录错误信息到annotation_records
                cursor.execute("""
                    INSERT INTO annotation_records 
                    (task_id, annotator_id, annotation_data, annotation_source, is_expert_reviewed)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    task_id,
                    -1,  # -1表示AI标注
                    json.dumps({
                        "error": error_msg,
                        "timestamp": str(datetime.now())
                    }, ensure_ascii=False),
                    'ai_error',
                    False
                ))
                conn.commit()
        except Exception as e:
            print(f"[AI标注] 任务{task_id}: 更新失败状态时出错: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    
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
                    json.dumps(annotation_data, ensure_ascii=False),
                    'manual',
                    False  # 默认为非专家审核
                ))
                
                conn.commit()
                
                # 记录用户行为日志（标注行为属于"标注"类型）
                try:
                    cursor.execute("""
                        INSERT INTO user_behavior_logs 
                        (user_id, behavior_type, content, timestamp)
                        VALUES (%s, %s, %s, NOW())
                    """, (
                        user_id,
                        '标注',
                        f"保存人工标注：任务ID {task_id}"
                    ))
                    conn.commit()
                except Exception as e:
                    print(f"记录用户行为日志失败: {e}")
                    # 不影响主流程，继续执行
                
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
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor() as cursor:
                # 管理员可以看到所有任务，普通用户只能看到自己上传的
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_result = cursor.fetchone()
                if not user_result:
                    return {"success": False, "message": "用户不存在"}
                user_role = user_result['role']
                
                # 根据resource_source字段关联不同的资源表
                # 使用LEFT JOIN来同时支持两种资源来源
                query = """
                    SELECT t.id, t.resource_id, t.resource_source, t.task_type, t.status, t.annotation_method,
                           COALESCE(cru.title, cr.title) as title,
                           COALESCE(cru.resource_type, cr.resource_type) as resource_type
                    FROM annotation_tasks t
                    LEFT JOIN cultural_resources_from_user cru 
                        ON t.resource_id = cru.id AND t.resource_source = 'cultural_resources_from_user'
                    LEFT JOIN cultural_resources cr 
                        ON t.resource_id = cr.id AND t.resource_source = 'cultural_resources'
                """
                params = []
                where_clauses = []
                
                # 普通用户只能看到自己上传的资源对应的任务
                if user_role != '管理员':
                    where_clauses.append("(cru.user_id = %s OR (t.resource_source = 'cultural_resources'))")
                    params.append(user_id)
                
                # 状态过滤
                if status:
                    where_clauses.append("t.status = %s")
                    params.append(status)
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                cursor.execute(query, params)
                tasks = cursor.fetchall()
                
                return {"success": True, "tasks": tasks}
        except Exception as e:
            return {"success": False, "message": f"获取任务失败: {str(e)}"}
        finally:
            if conn:
                conn.close()



