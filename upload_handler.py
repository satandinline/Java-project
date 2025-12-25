import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
import pymysql
from pymysql.cursors import DictCursor
import hashlib
import sys
import threading
import io

# 添加项目根目录到路径，以便导入db_connection
# 使用相对路径添加项目根目录到sys.path
current_file_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, current_file_dir)
from db_connection import get_user_db_connection, get_user_db_config
from festival_name_utils import extract_and_convert_festival_name

# 尝试导入文件解析库
try:
    from docx import Document as DocxDocument
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    print("警告：未安装python-docx库，无法解析Word文档。请运行: pip install python-docx")

try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False
    print("警告：未安装PyPDF2库，无法解析PDF文档。请运行: pip install PyPDF2")


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
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """从Word文档中提取文本内容"""
        if not HAS_DOCX:
            return ""
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(file_path)
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            return "\n".join(text_parts)
        except Exception as e:
            print(f"解析Word文档失败: {e}")
            return ""
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """从PDF文档中提取文本内容"""
        if not HAS_PDF:
            return ""
        try:
            import PyPDF2
            text_parts = []
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        text_parts.append(text)
            return "\n".join(text_parts)
        except Exception as e:
            print(f"解析PDF文档失败: {e}")
            return ""
    
    def _extract_text_from_file(self, file_path: str, file_ext: str) -> str:
        """根据文件类型提取文本内容"""
        file_ext_lower = file_ext.lower()
        
        if file_ext_lower in ['.docx']:
            return self._extract_text_from_docx(file_path)
        elif file_ext_lower in ['.pdf']:
            return self._extract_text_from_pdf(file_path)
        elif file_ext_lower in ['.doc']:
            # .doc格式需要特殊处理，这里先返回空，提示用户使用.docx
            print("警告：不支持旧版.doc格式，请转换为.docx或PDF格式")
            return ""
        else:
            # 尝试作为纯文本读取
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except:
                return ""
    
    def upload_resource(self, user_id: int, file_data: Optional[bytes] = None, file_name: Optional[str] = None, 
                       resource_type: str = "文本", text_content: Optional[str] = None, 
                       user_annotation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理用户上传资源（支持文件上传或直接文本输入）
        :param user_id: 上传用户ID
        :param file_data: 文件二进制数据（可选，如果提供text_content则不需要）
        :param file_name: 文件名（可选，如果提供text_content则不需要）
        :param resource_type: 资源类型（"文本"或"图像"）
        :param text_content: 直接输入的文本内容（可选，如果提供file_data则不需要）
        :param user_annotation: 用户标注数据（可选）
        :return: 上传结果
        """
        # 更新实例的user_id，确保使用正确的用户ID
        self.user_id = user_id
        
        # 获取上传时间
        upload_datetime = datetime.now()
        date_str = upload_datetime.strftime("%Y-%m-%d")
        time_str = upload_datetime.strftime("%H-%M-%S")
        
        # 获取用户账号
        conn_temp = None
        user_account = "unknown"
        try:
            conn_temp = self._get_db_connection()
            if conn_temp:
                with conn_temp.cursor() as cursor:
                    cursor.execute("SELECT account FROM users WHERE id = %s", (user_id,))
                    user_result = cursor.fetchone()
                    if user_result:
                        user_account = user_result['account']
        except Exception as e:
            print(f"获取用户账号失败: {e}")
        finally:
            if conn_temp:
                conn_temp.close()
        
        # 清理用户账号中的特殊字符，只保留字母、数字、下划线和连字符
        import re
        safe_account = re.sub(r'[^\w\-]', '_', user_account)
        
        # 处理两种上传方式：文件上传或直接文本输入
        file_path = None
        content_hash = None
        content_text = ""
        file_ext = ""
        unique_filename = ""
        
        if text_content:
            # 直接文本输入模式
            content_text = text_content.strip()
            if not content_text:
                return {
                    "success": False,
                    "message": "文本内容不能为空"
                }
            
            # 为文本内容生成文件名（保存为.txt文件）
            file_ext = '.txt'
            base_filename = f"{safe_account}-{date_str}-{time_str}"
            unique_filename = f"{base_filename}{file_ext}"
            file_path = os.path.join(self.upload_dir, unique_filename)
            
            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(file_path):
                unique_filename = f"{base_filename}-{counter}{file_ext}"
                file_path = os.path.join(self.upload_dir, unique_filename)
                counter += 1
            
            # 保存文本内容到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_text)
            
            # 计算文本内容的哈希值
            content_hash = hashlib.sha256(content_text.encode('utf-8')).hexdigest()
            file_name = f"文本输入_{date_str}_{time_str}.txt"
            
        elif file_data and file_name:
            # 文件上传模式
            # 验证文件类型
            file_ext = os.path.splitext(file_name)[1].lower() if '.' in file_name else ''
            
            if resource_type == "文本":
                # 文本类型只允许.doc, .docx, .pdf
                allowed_text_exts = ['.doc', '.docx', '.pdf']
                if file_ext not in allowed_text_exts:
                    return {
                        "success": False,
                        "message": f"文本类型只支持Word文档（.doc, .docx）或PDF（.pdf），当前文件类型：{file_ext}"
                    }
            elif resource_type == "图像":
                # 图像类型只允许.jpg, .png
                allowed_image_exts = ['.jpg', '.jpeg', '.png']
                if file_ext not in allowed_image_exts:
                    return {
                        "success": False,
                        "message": f"图像类型只支持JPG（.jpg）或PNG（.png），当前文件类型：{file_ext}"
                    }
            
            # 生成文件名：用户账号-日期-时间.扩展名
            base_filename = f"{safe_account}-{date_str}-{time_str}"
            unique_filename = f"{base_filename}{file_ext}"
            file_path = os.path.join(self.upload_dir, unique_filename)
            
            # 如果文件已存在，添加序号
            counter = 1
            while os.path.exists(file_path):
                unique_filename = f"{base_filename}-{counter}{file_ext}"
                file_path = os.path.join(self.upload_dir, unique_filename)
                counter += 1
            
            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            # 计算文件哈希值
            content_hash = self._calculate_file_hash(file_path)
            
            # 如果是文本类型文件，提取文本内容
            if resource_type == "文本":
                content_text = self._extract_text_from_file(file_path, file_ext)
                if not content_text:
                    print(f"警告：无法从文件 {file_name} 中提取文本内容")
        else:
            return {
                "success": False,
                "message": "请提供文件或文本内容"
            }
        
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
                festival_title_en = "Traditional Festival"  # 默认值
                
                if resource_type == "文本" and content_text:
                    # 从文本内容中提取节日名称（使用前2000字符）
                    preview_text = content_text[:2000] if len(content_text) > 2000 else content_text
                    festival_title_en = extract_and_convert_festival_name(preview_text)
                else:
                    # 对于图片文件或无法提取文本的情况，从文件名提取
                    festival_title_en = extract_and_convert_festival_name(file_name)
                
                # 插入用户上传资源表（title字段存储英文节日名称）
                # content_feature_data中保存原始文件名和新文件名，便于展示和排序
                # 对于文本资源，保存完整文本内容（用于AI标注）
                # 计算存储路径（相对于项目根目录）
                storage_path = f"uploads/{unique_filename}" if file_path else None
                
                content_feature_data = {
                    "original_file_name": file_name,  # 原始文件名
                    "stored_file_name": unique_filename,  # 存储的文件名（新格式）
                    "user_account": user_account,  # 用户账号
                    "upload_date": date_str,  # 上传日期
                    "upload_time": time_str,  # 上传时间
                    "content_preview": content_text[:500] if content_text else "",  # 预览文本（前500字符）
                    "content_full": content_text if resource_type == "文本" else ""  # 完整文本内容（仅文本类型）
                }
                
                cursor.execute("""
                    INSERT INTO cultural_resources_from_user 
                    (user_id, title, resource_type, file_format, content_feature_data,
                     content_hash, storage_path, upload_time, ai_review_status, manual_review_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,  # 关联上传用户ID
                    festival_title_en,  # title字段存储英文节日名称
                    resource_type,
                    file_name.split('.')[-1] if '.' in file_name else '',
                    json.dumps(content_feature_data, ensure_ascii=False),
                    content_hash,  # 存储哈希值用于后续查重
                    storage_path,  # 文件存储路径
                    upload_datetime,  # 上传时间
                    'pending',  # 初始AI审核状态
                    'pending'   # 初始人工审核状态
                ))
                
                resource_id = cursor.lastrowid  # 获取用户上传资源的ID
                
                # 创建标注任务（关联用户上传的资源ID，指定资源来源为cultural_resources_from_user）
                task_id = None
                # 无论用户是否提供标注，都创建统一的标注任务：
                # - 初始状态：待标注
                # - 标注方式：ai（后续人工保存时会更新为manual）
                cursor.execute("""
                    INSERT INTO annotation_tasks 
                    (resource_id, resource_source, task_type, annotation_method, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, (resource_id, 'cultural_resources_from_user', '实体', 'ai', '待标注'))
                task_id = cursor.lastrowid
                
                # 如果用户在上传时提供了标注，先保存一份人工标注记录
                if user_annotation:
                    self._save_user_annotation(cursor, task_id, user_id, user_annotation)
                
                conn.commit()
                
                # 记录用户行为日志（上传行为属于"交互"类型）
                try:
                    from user_logging import UserLogging
                    UserLogging.log_upload(user_id, file_name, resource_type)
                except Exception as e:
                    print(f"记录用户行为日志失败: {e}")
                    # 不影响主流程，继续执行
                
                # 只要检测到有用户上传资源，就自动触发AI标注
                self.trigger_ai_annotation(task_id)
                
                message = "资源上传成功"
                if user_annotation:
                    message += "，用户标注已保存"
                else:
                    message += "，已提交AI标注任务"
                
                return {
                    "success": True,
                    "resource_id": resource_id,
                    "message": message
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
                    # 更新任务状态为 AI 标注中
                    try:
                        cursor.execute(
                            "UPDATE annotation_tasks SET status = %s WHERE id = %s",
                            ('AI标注中', task_id)
                        )
                        conn.commit()
                    except Exception as e:
                        print(f"[AI标注] 任务{task_id}: 无法更新为AI标注中: {e}")
                    
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
                    # 优先使用完整文本内容（content_full），如果没有则使用预览文本
                    content_text = content_data.get('content_full', '') or content_data.get('content_preview', '')
                    resource_type = task_info.get('resource_type', '')
                    
                    # 对于图片资源，需要获取图片文件路径
                    image_path = None
                    if resource_type == '图像':
                        stored_file_name = content_data.get('stored_file_name') or content_data.get('file_name', '')
                        if stored_file_name:
                            image_path = os.path.join(self.upload_dir, stored_file_name)
                            if not os.path.exists(image_path):
                                error_msg = f"图片文件不存在: {image_path}"
                                print(f"[AI标注] 任务{task_id}: {error_msg}")
                                self._update_task_status_on_error(conn, task_id, error_msg)
                                return
                        else:
                            error_msg = "无法获取图片文件路径"
                            print(f"[AI标注] 任务{task_id}: {error_msg}")
                            self._update_task_status_on_error(conn, task_id, error_msg)
                            return
                    
                    # 对于文本资源，检查是否有内容
                    if resource_type == '文本' and not content_text:
                        error_msg = "无可标注内容"
                        print(f"[AI标注] 任务{task_id}: {error_msg}")
                        self._update_task_status_on_error(conn, task_id, error_msg)
                        return
                    
                    # 3. 调用RAG系统进行实体识别
                    from AIGC.RAG import CulturalResourceRAG
                    from langchain_community.chat_models import ChatTongyi
                    from pydantic import SecretStr
                    
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
                    if resource_type == '图像':
                        # 图片资源的标注提示词
                        annotation_prompt = """
请分析这张图片，识别并提取所有与文化相关的实体。

要求:
1. 识别图片中出现的所有文化实体（人物、作品、事件、地点、其他）
2. 为每个实体标注类型（人物/作品/事件/地点/其他）
3. 评估识别的置信度（0-1之间）
4. 描述图片中的文化元素和传统节日相关内容

请以JSON格式返回，例如:
{
"entities": [
    {"name": "春节", "type": "事件", "confidence": 0.95},
    {"name": "王安石", "type": "人物", "confidence": 0.88}
]
}
"""
                    else:
                        # 文本资源的标注提示词
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
                    print(f"[AI标注] 任务{task_id}: 开始AI标注（资源类型: {resource_type}）...")
                    if resource_type == '图像' and image_path:
                        # 对于图片，使用image_paths参数
                        result = rag_system.ask(annotation_prompt, image_paths=[image_path])
                    else:
                        # 对于文本，只使用文本提示词
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
                            # 保存标注结果 - 使用扁平化字段
                            # 从entities列表中提取第一个实体作为主要实体（如果有多个实体，可以创建多条记录）
                            if entities:
                                # 取第一个实体作为主要标注结果
                                main_entity = entities[0]
                                entity_name = main_entity.get('name', '')
                                entity_type = main_entity.get('type', '其他')
                                
                                # 构建描述信息（包含所有识别的实体）
                                all_entities_text = ', '.join([e.get('name', '') for e in entities])
                                description = f"AI自动标注 (模型: qwen-turbo)。识别到实体: {all_entities_text}"
                                
                                # 更新任务状态
                                cursor.execute("""
                                    UPDATE annotation_tasks 
                                    SET status = %s 
                                    WHERE id = %s AND status != '已完成'
                                """, ('AI标注完成', task_id))
                                
                                # 保存标注记录 - 使用新字段结构
                                cursor.execute("""
                                    INSERT INTO annotation_records 
                                    (task_id, annotator_id, annotation_source, is_expert_reviewed,
                                     entity_name, entity_type, description)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    task_id,
                                    -1,  # -1表示AI标注
                                    'ai',
                                    False,
                                    entity_name,
                                    entity_type,
                                    description
                                ))
                                
                                # 如果有多个实体，为每个实体创建一条记录
                                for entity in entities[1:]:
                                    entity_name = entity.get('name', '')
                                    entity_type = entity.get('type', '其他')
                                    cursor.execute("""
                                        INSERT INTO annotation_records 
                                        (task_id, annotator_id, annotation_source, is_expert_reviewed,
                                         entity_name, entity_type, description)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        task_id,
                                        -1,
                                        'ai',
                                        False,
                                        entity_name,
                                        entity_type,
                                        f"AI自动标注 (模型: qwen-turbo)"
                                    ))
                            else:
                                # 如果没有识别到实体，创建一条默认记录
                                cursor.execute("""
                                    UPDATE annotation_tasks 
                                    SET status = %s 
                                    WHERE id = %s AND status != '已完成'
                                """, ('AI标注完成', task_id))
                                
                                cursor.execute("""
                                    INSERT INTO annotation_records 
                                    (task_id, annotator_id, annotation_source, is_expert_reviewed,
                                     entity_name, entity_type, description)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    task_id,
                                    -1,
                                    'ai',
                                    False,
                                    '未识别到实体',
                                    '其他',
                                    'AI自动标注 (模型: qwen-turbo)：未识别到实体'
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
    
    def _save_user_annotation(self, cursor, task_id: int, user_id: int, annotation_data: Dict[str, Any]):
        """
        保存用户上传时提供的标注（内部方法，在事务中调用）
        :param cursor: 数据库游标（已在事务中）
        :param task_id: 标注任务ID
        :param user_id: 标注用户ID
        :param annotation_data: 标注数据
        """
        # 保存用户标注记录 - 使用扁平化字段
        if 'entity_name' in annotation_data:
            # 新格式：直接使用扁平化字段
            cursor.execute("""
                INSERT INTO annotation_records 
                (task_id, annotator_id, annotation_source, is_expert_reviewed,
                 entity_name, entity_type, description, source,
                 period_era, geo_coordinates, cultural_region,
                 style_features, cultural_value, related_images_url, digital_resource_link)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                task_id,
                user_id,
                'manual',
                False,
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
        else:
            # 如果没有实体名称，创建一条默认记录
            cursor.execute("""
                INSERT INTO annotation_records 
                (task_id, annotator_id, annotation_source, is_expert_reviewed,
                 entity_name, entity_type, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                task_id,
                user_id,
                'manual',
                False,
                '未指定实体',
                '其他',
                annotation_data.get('description', '用户上传时提供的标注')
            ))
    
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
            if not conn:
                return {"success": False, "message": "数据库连接失败"}
            with conn.cursor() as cursor:
                # 更新任务状态
                cursor.execute("""
                    UPDATE annotation_tasks 
                    SET status = %s, annotation_method = %s
                    WHERE id = %s
                """, ('已完成', 'manual', task_id))
                
                # 保存人工标注记录 - 使用扁平化字段
                # 从annotation_data中提取字段
                entities = annotation_data.get('entities', [])
                description = annotation_data.get('description', '')

                # 如果annotation_data包含新字段结构，直接使用
                if 'entity_name' in annotation_data:
                    # 新格式：直接使用扁平化字段
                    cursor.execute("""
                        INSERT INTO annotation_records 
                        (task_id, annotator_id, annotation_source, is_expert_reviewed,
                         entity_name, entity_type, description, source,
                         period_era, geo_coordinates, cultural_region,
                         style_features, cultural_value, related_images_url, digital_resource_link)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_id,
                        user_id,
                        'manual',
                        False,
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
                elif entities:
                    # 旧格式：从entities数组中提取（兼容旧代码）
                    # 为每个实体创建一条记录
                    for entity in entities:
                        cursor.execute("""
                            INSERT INTO annotation_records 
                            (task_id, annotator_id, annotation_source, is_expert_reviewed,
                             entity_name, entity_type, description)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            task_id,
                            user_id,
                            'manual',
                            False,
                            entity.get('name', ''),
                            entity.get('type', '其他'),
                            description or f"人工标注：{entity.get('name', '')}"
                        ))
                else:
                    # 如果没有实体信息，创建一条默认记录
                    cursor.execute("""
                        INSERT INTO annotation_records 
                        (task_id, annotator_id, annotation_source, is_expert_reviewed,
                         entity_name, entity_type, description)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_id,
                        user_id,
                        'manual',
                        False,
                        '未指定实体',
                        '其他',
                        description or '人工标注'
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
    
    def get_annotation_tasks(self, user_id: int, status: Optional[str] = None, page: int = 1, page_size: int = 12) -> Dict[str, Any]:
        """
        获取标注任务列表（支持分页）
        :param user_id: 用户ID
        :param status: 任务状态过滤，可选
        :param page: 页码（从1开始）
        :param page_size: 每页数量
        :return: 任务列表（包含分页信息）
        """
        conn = None
        try:
            conn = self._get_db_connection()
            if not conn:
                return {"success": False, "message": "数据库连接失败"}
            with conn.cursor() as cursor:
                # 管理员可以看到所有任务，普通用户只能看到自己上传的资源对应的任务
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_result = cursor.fetchone()
                if not user_result:
                    return {"success": False, "message": "用户不存在"}
                user_role = user_result['role']
                
                # 构建基础查询（用于计数和获取数据）
                base_query = """
                    FROM annotation_tasks t
                    LEFT JOIN cultural_resources_from_user cru 
                        ON t.resource_id = cru.id AND t.resource_source = 'cultural_resources_from_user'
                    LEFT JOIN cultural_resources cr 
                        ON t.resource_id = cr.id AND t.resource_source = 'cultural_resources'
                    LEFT JOIN AIGC_cultural_resources aigc
                        ON t.resource_id = aigc.id AND t.resource_source = 'AIGC_cultural_resources'
                """
                params = []
                where_clauses = []
                
                # 普通用户只能看到自己上传的资源对应的任务（只针对cultural_resources_from_user表）
                # 管理员和超级管理员可以看到所有任务（包括cultural_resources_from_user和其他来源的资源）
                if user_role != '管理员' and user_role != '超级管理员':
                    where_clauses.append("(t.resource_source = 'cultural_resources_from_user' AND cru.user_id = %s)")
                    params.append(user_id)
                # 注意：管理员可以看到所有来源的资源，包括cultural_resources、cultural_resources_from_user和AIGC_cultural_resources
                # 但根据需求，AI标注功能应该只针对用户上传的资源（cultural_resources_from_user表）
                
                # 状态过滤
                if status:
                    where_clauses.append("t.status = %s")
                    params.append(status)
                
                where_clause = ""
                if where_clauses:
                    where_clause = " WHERE " + " AND ".join(where_clauses)
                
                # 先获取总数
                count_query = f"SELECT COUNT(*) as total {base_query} {where_clause}"
                cursor.execute(count_query, params)
                total_result = cursor.fetchone()
                total = total_result['total'] if total_result else 0
                total_pages = (total + page_size - 1) // page_size if total > 0 else 0
                
                # 获取分页数据
                data_query = f"""
                    SELECT t.id, t.resource_id, t.resource_source, t.task_type, t.status, t.annotation_method,
                           COALESCE(cru.title, cr.title, aigc.title) as title,
                           COALESCE(cru.resource_type, cr.resource_type, aigc.resource_type) as resource_type,
                           COALESCE(cru.content_feature_data, cr.content_feature_data, aigc.content_feature_data) as content_feature_data,
                           COALESCE(cru.storage_path, NULL) as storage_path,
                           t.created_at, t.updated_at
                    {base_query}
                    {where_clause}
                    ORDER BY t.created_at DESC
                    LIMIT %s OFFSET %s
                """
                offset = (page - 1) * page_size
                cursor.execute(data_query, params + [page_size, offset])
                tasks = cursor.fetchall()
                
                # 处理任务数据，添加文件名和资源内容信息
                processed_tasks = []
                for task in tasks:
                    task_dict = dict(task)
                    
                    # 解析content_feature_data，提取资源内容
                    content_feature_data = task_dict.get('content_feature_data')
                    if content_feature_data:
                        try:
                            if isinstance(content_feature_data, str):
                                content_data = json.loads(content_feature_data)
                            else:
                                content_data = content_feature_data
                            
                            # 提取文本预览（用于文本资源）
                            task_dict['content_preview'] = content_data.get('content_preview', '') or content_data.get('text', '')[:200]  # 最多200字符
                            
                            # 提取完整文本内容（用于文本资源）
                            task_dict['content_full'] = content_data.get('content_full', '') or content_data.get('text', '')
                            
                            # 提取图片文件信息（用于图像资源）
                            stored_file_name = content_data.get('stored_file_name') or content_data.get('file_name', '')
                            if stored_file_name:
                                task_dict['image_url'] = f"/api/uploads/{stored_file_name}"
                                task_dict['original_file_name'] = content_data.get('original_file_name', stored_file_name)
                            
                            # 其他元数据
                            task_dict['file_name'] = stored_file_name
                            task_dict['upload_date'] = content_data.get('upload_date', '')
                            task_dict['upload_time'] = content_data.get('upload_time', '')
                        except Exception as e:
                            print(f"解析content_feature_data失败: {e}")
                            task_dict['content_preview'] = ''
                            task_dict['image_url'] = None
                    
                    # 如果资源类型是图像，确保有图片URL
                    if task_dict.get('resource_type') == '图像' and not task_dict.get('image_url'):
                        storage_path = task_dict.get('storage_path')
                        if storage_path:
                            # 从storage_path构建URL
                            if 'uploads' in storage_path:
                                file_name = storage_path.split('uploads/')[-1] if 'uploads/' in storage_path else storage_path.split('/')[-1]
                                task_dict['image_url'] = f"/api/uploads/{file_name}"
                    
                    processed_tasks.append(task_dict)
                
                return {
                    "success": True, 
                    "tasks": processed_tasks,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages
                }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "message": f"获取任务失败: {str(e)}"}
        finally:
            if conn:
                conn.close()

    def approve_and_migrate_annotation(self, task_id: int, reviewer_id: int) -> Dict[str, Any]:
        """
        审核通过标注并迁移数据到正式表
        :param task_id: 标注任务ID
        :param reviewer_id: 审核者ID
        :return: 迁移结果
        """
        conn = None
        try:
            conn = self._get_db_connection()
            if not conn:
                return {
                    "success": False,
                    "message": "数据库连接失败"
                }
            
            with conn.cursor() as cursor:
                # 1. 获取任务信息（支持三种资源来源）
                cursor.execute("""
                    SELECT t.resource_id, t.resource_source, t.task_type,
                           COALESCE(cru.resource_type, cr.resource_type, aigc.resource_type) as resource_type,
                           COALESCE(cru.title, cr.title, aigc.title) as title,
                           COALESCE(cru.content_feature_data, cr.content_feature_data, aigc.content_feature_data) as content_feature_data,
                           COALESCE(cru.file_format, cr.file_format, aigc.file_format) as file_format,
                           COALESCE(cru.storage_path, NULL) as storage_path
                    FROM annotation_tasks t
                    LEFT JOIN cultural_resources_from_user cru 
                        ON t.resource_id = cru.id 
                        AND t.resource_source = 'cultural_resources_from_user'
                    LEFT JOIN cultural_resources cr 
                        ON t.resource_id = cr.id 
                        AND t.resource_source = 'cultural_resources'
                    LEFT JOIN AIGC_cultural_resources aigc
                        ON t.resource_id = aigc.id
                        AND t.resource_source = 'AIGC_cultural_resources'
                    WHERE t.id = %s
                """, (task_id,))
                
                task_info = cursor.fetchone()
                if not task_info:
                    return {
                        "success": False,
                        "message": "任务不存在"
                    }
                
                # 2. 获取最新的标注记录（已审核通过的）
                cursor.execute("""
                    SELECT entity_name, entity_type, description, source,
                           period_era, geo_coordinates, cultural_region,
                           style_features, cultural_value, related_images_url, digital_resource_link
                    FROM annotation_records
                    WHERE task_id = %s AND is_expert_reviewed = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (task_id,))
                
                annotation = cursor.fetchone()
                if not annotation:
                    return {
                        "success": False,
                        "message": "未找到已审核的标注记录"
                    }
                
                # 3. 根据任务类型迁移到不同表
                task_type = task_info['task_type']
                migrated_ids = []
                entity_id = None
                
                if task_type == '实体':
                    # 迁移到 cultural_entities 表
                    cursor.execute("""
                        INSERT INTO cultural_entities 
                        (entity_name, entity_type, description, source,
                         period_era, geo_coordinates, cultural_region,
                         style_features, cultural_value, related_images_url, digital_resource_link)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        annotation['entity_name'],
                        annotation['entity_type'],
                        annotation['description'],
                        annotation['source'],
                        annotation['period_era'],
                        annotation['geo_coordinates'],
                        annotation['cultural_region'],
                        annotation['style_features'],
                        annotation['cultural_value'],
                        annotation['related_images_url'],
                        annotation['digital_resource_link']
                    ))
                    entity_id = cursor.lastrowid
                    migrated_ids.append(('cultural_entities', entity_id))
                
                # 4. 如果资源来源是 cultural_resources_from_user 或 AIGC_cultural_resources，迁移资源到 cultural_resources
                resource_id = None
                if task_info['resource_source'] in ['cultural_resources_from_user', 'AIGC_cultural_resources']:
                    # 确定source_from
                    if task_info['resource_source'] == 'cultural_resources_from_user':
                        source_from = '用户上传'
                    else:
                        source_from = 'AIGC生成'
                    
                    cursor.execute("""
                        INSERT INTO cultural_resources 
                        (title, resource_type, file_format, source_from,
                         content_feature_data, upload_user_id, ai_review_status, manual_review_status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_info['title'],
                        task_info['resource_type'],
                        task_info['file_format'],
                        source_from,
                        task_info['content_feature_data'],
                        self.user_id if task_info['resource_source'] == 'cultural_resources_from_user' else None,
                        'passed',
                        'passed'
                    ))
                    resource_id = cursor.lastrowid
                    migrated_ids.append(('cultural_resources', resource_id))
                    
                    # 更新原资源表的审核状态
                    if task_info['resource_source'] == 'cultural_resources_from_user':
                        cursor.execute("""
                            UPDATE cultural_resources_from_user 
                            SET ai_review_status = 'passed', manual_review_status = 'passed'
                            WHERE id = %s
                        """, (task_info['resource_id'],))
                
                # 5. 迁移到图片表（crawled_images）
                # 要求：用户上传资源人工标注通过后，始终在图片表中有一条记录：
                # - 如果是图像资源：使用真实图片路径
                # - 如果没有图片：使用 uploads/default.jpg 作为默认图片
                if resource_id:
                    storage_path = None
                    file_name = None
                    
                    if task_info['resource_type'] == '图像':
                        # 图像资源：优先使用storage_path字段，如果没有则从content_feature_data中获取
                        storage_path = task_info.get('storage_path')
                        if not storage_path:
                            content_data = json.loads(task_info['content_feature_data'] or '{}')
                            file_name = content_data.get('stored_file_name') or content_data.get('file_name', '')
                            if file_name:
                                # 根据资源来源确定存储路径
                                if task_info['resource_source'] == 'cultural_resources_from_user':
                                    storage_path = f"uploads/{file_name}"
                                elif task_info['resource_source'] == 'AIGC_cultural_resources':
                                    storage_path = f"AIGC_graph/{file_name}"
                                else:
                                    storage_path = f"crawled_images/{file_name}"
                    else:
                        # 非图像资源：使用默认图片
                        file_name = "default.jpg"
                        storage_path = "uploads/default.jpg"
                    
                    if storage_path:
                        # 从storage_path中提取文件名（非图像资源会覆盖为default.jpg）
                        file_name = os.path.basename(storage_path) if storage_path else (file_name or "default.jpg")
                        
                        cursor.execute("""
                            INSERT INTO crawled_images 
                            (file_name, storage_path, tags, resource_id, entity_id)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            file_name,
                            storage_path,
                            json.dumps([annotation['entity_name']], ensure_ascii=False),
                            resource_id,  # 关联到迁移后的cultural_resources表
                            entity_id
                        ))
                        image_id = cursor.lastrowid
                        migrated_ids.append(('crawled_images', image_id))
                
                # 6. 更新任务状态为已完成
                cursor.execute("""
                    UPDATE annotation_tasks 
                    SET status = '已完成'
                    WHERE id = %s
                """, (task_id,))
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "标注审核通过，数据已迁移",
                    "migrated": migrated_ids
                }
                
        except Exception as e:
            if conn:
                conn.rollback()
            return {
                "success": False,
                "message": f"迁移失败: {str(e)}"
            }
        finally:
            if conn:
                conn.close()



