"""
AIGC API服务器
提供文字AIGC和图片AIGC的后端接口

使用方法：
1. 安装依赖：pip install flask flask-cors
2. 运行：python aigc_api_server.py
3. 服务器将在 http://localhost:7200 启动（通过前端5173代理访问）
"""
# -*- coding: utf-8 -*-
import os
import sys
import json

# 设置标准输出编码为UTF-8，解决Windows终端中文乱码问题
# 优先使用环境变量PYTHONIOENCODING（如果已设置）
if 'PYTHONIOENCODING' not in os.environ:
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 设置标准输出编码（适用于所有平台，包括Windows）
def setup_utf8_encoding():
    """设置UTF-8编码，解决Windows终端中文乱码问题"""
    try:
        # 检查stdout是否可用，避免在concurrently等环境下出错
        if hasattr(sys.stdout, 'buffer') and not getattr(sys.stdout, 'closed', True):
            import io
            try:
                # 测试stdout是否真的可用
                sys.stdout.write('')
                sys.stdout.flush()
                # 如果测试通过，尝试设置编码
                # 使用reconfigure方法（Python 3.7+）
                if hasattr(sys.stdout, 'reconfigure'):
                    try:
                        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
                        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
                    except (ValueError, OSError, AttributeError):
                        # 如果reconfigure失败，尝试使用TextIOWrapper
                        try:
                            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
                            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
                        except (AttributeError, ValueError, OSError, IOError):
                            pass
                else:
                    # Python 3.6及以下版本，使用TextIOWrapper
                    try:
                        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
                        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
                    except (AttributeError, ValueError, OSError, IOError):
                        pass
            except (AttributeError, ValueError, OSError, IOError):
                # 如果设置失败，保持原样
                pass
    except Exception:
        # 静默处理所有异常，确保不影响程序运行
        pass

# 在所有平台上都尝试设置编码（包括Windows和Linux/Mac）
# 这对于concurrently等工具重定向stdout时特别重要
try:
    setup_utf8_encoding()
except Exception:
    pass

import hashlib
import threading
import time
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
from pydantic import SecretStr
from typing import Optional, Dict

# 添加项目根目录和当前目录到路径（使用相对路径）
# 获取当前文件所在目录（AIGC目录）
current_dir = os.path.dirname(os.path.realpath(__file__))
# 获取项目根目录（AIGC的父目录）
project_root = os.path.dirname(current_dir)
# 将路径添加到sys.path（使用相对路径）
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

load_dotenv(override=True)

# 延迟导入RAG和ImageAIGC模块（避免启动时加载，提升启动速度）
from aigc_db_helper import save_aigc_text_resource, save_aigc_image, extract_festival_names
# 导入父目录的模块
from login import AuthSystem
from upload_handler import ResourceUploader
from user_logging import UserLogging
from db_connection import get_user_db_connection
from pymysql.cursors import DictCursor

# 导入统计API（延迟导入，避免循环依赖）
def register_statistics_api():
    """注册统计API蓝图"""
    try:
        from statistics_api import statistics_bp
        app.register_blueprint(statistics_bp)
    except Exception as e:
        import traceback
        traceback.print_exc()
        # 即使注册失败，也继续启动服务器

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 注册统计API蓝图
try:
    register_statistics_api()
except Exception as e:
    import traceback
    traceback.print_exc()
    # 继续启动，不中断

# 启动AI自动标注服务
try:
    from auto_annotation import get_auto_annotation_service
    auto_annotation_service = get_auto_annotation_service()
    auto_annotation_service.start()
except Exception as e:
    import traceback
    traceback.print_exc()
    # 继续启动，不中断

# 配置静态文件服务（使用相对路径）
# os已在文件开头导入，无需重复导入
# 获取项目根目录（相对于当前文件）
current_file_dir = os.path.dirname(os.path.realpath(__file__))
project_root = os.path.dirname(current_file_dir)
# 头像存储在项目根目录的 public 文件夹
public_dir = os.path.join(project_root, 'public')
os.makedirs(public_dir, exist_ok=True)

# 初始化认证系统（延迟初始化，避免启动时数据库连接失败导致服务器无法启动）
auth_system = None

def get_auth_system():
    """获取认证系统实例（延迟初始化）"""
    global auth_system
    if auth_system is None:
        try:
            auth_system = AuthSystem()
        except Exception as e:
            import traceback
            traceback.print_exc()
            # 即使初始化失败，也创建一个实例，在实际使用时再处理错误
            auth_system = AuthSystem()
    return auth_system

# 初始化RAG和ImageAIGC系统（按用户动态创建）
rag_systems = {}  # {user_id: rag_system}
image_aigc_systems = {}  # {user_id: image_aigc_system}

# 全局搜索RAG系统（用于全文检索功能，不按用户区分）
search_rag_system = None

def init_search_rag_system():
    """初始化全局搜索RAG系统（延迟加载）"""
    global search_rag_system
    if search_rag_system is not None:
        return search_rag_system
    
    try:
        # 延迟导入RAG模块，避免启动时加载
        from RAG import CulturalResourceRAG
        from langchain_community.chat_models import ChatTongyi
        from db_connection import get_default_db_connection
        
        ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")
        if not ALIYUN_API_KEY:
            return None
        
        tongyi_model = ChatTongyi(api_key=SecretStr(ALIYUN_API_KEY), model="qwen-turbo")
        search_rag_system = CulturalResourceRAG(model=tongyi_model, persist_directory="./chroma_db")
        return search_rag_system
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None

def save_aigc_message_to_db(user_id: int, session_id: int, user_message: str, ai_message: str, 
                            model: str, image_url: Optional[str], image_from_users_url: Optional[str] = None, 
                            retrieval_id: Optional[str] = None, message_id: Optional[int] = None, db_config: Dict = None):
    """保存AIGC消息到数据库，并记录访问日志（包括管理员）
    
    Args:
        user_id: 用户ID
        session_id: 会话ID
        user_message: 用户消息
        ai_message: AI回答
        model: 模型类型（'text'或'image'）
        image_url: 图片URL
        image_from_users_url: 用户上传的图片URL
        retrieval_id: 检索的资源ID列表（英文逗号分隔）
        message_id: 消息ID（如果提供，则更新现有消息而不是插入新消息）
        db_config: 数据库配置
    
    Returns:
        如果message_id为None，返回新插入的消息ID；否则返回True/False
    """
    try:
        from db_connection import get_user_db_connection
        from pymysql.cursors import DictCursor
        conn = get_user_db_connection()
        if not conn:
            return False if message_id else None
        
        try:
            with conn.cursor(DictCursor) as cursor:
                # 检查表是否有新字段
                try:
                    cursor.execute("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'qa_messages' 
                        AND COLUMN_NAME = 'user_message'
                    """)
                    has_new_structure = cursor.fetchone() is not None
                    
                    # 检查是否有image_from_users_url字段
                    cursor.execute("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'qa_messages' 
                        AND COLUMN_NAME = 'image_from_users_url'
                    """)
                    has_image_from_users_field = cursor.fetchone() is not None
                    
                    # 检查是否有retrieval_id字段
                    cursor.execute("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'qa_messages' 
                        AND COLUMN_NAME = 'retrieval_id'
                    """)
                    has_retrieval_id_field = cursor.fetchone() is not None
                except:
                    has_new_structure = False
                    has_image_from_users_field = False
                    has_retrieval_id_field = False
                
                if has_new_structure:
                    if message_id:
                        # 更新现有消息
                        update_fields = []
                        update_values = []
                        
                        if ai_message is not None:
                            update_fields.append("ai_message = %s")
                            update_values.append(ai_message)
                        if image_url is not None:
                            update_fields.append("image_url = %s")
                            update_values.append(image_url)
                        if retrieval_id is not None:
                            if has_retrieval_id_field:
                                update_fields.append("retrieval_id = %s")
                                update_values.append(retrieval_id)
                        
                        if update_fields:
                            update_values.append(message_id)
                            cursor.execute(f"""
                                UPDATE qa_messages 
                                SET {', '.join(update_fields)}
                                WHERE id = %s
                            """, tuple(update_values))
                            conn.commit()
                            return True
                        else:
                            return True
                    else:
                        # 插入新消息
                        fields = ["user_id", "session_id", "user_message", "ai_message", "model"]
                        values = [user_id, session_id, user_message, ai_message, model]
                        placeholders = ["%s"] * len(fields)
                        
                        if image_url is not None:
                            fields.append("image_url")
                            values.append(image_url)
                            placeholders.append("%s")
                        
                        if has_image_from_users_field and image_from_users_url is not None:
                            fields.append("image_from_users_url")
                            values.append(image_from_users_url)
                            placeholders.append("%s")
                        
                        if has_retrieval_id_field and retrieval_id is not None:
                            fields.append("retrieval_id")
                            values.append(retrieval_id)
                            placeholders.append("%s")
                        
                        cursor.execute(f"""
                            INSERT INTO qa_messages ({', '.join(fields)})
                            VALUES ({', '.join(placeholders)})
                        """, tuple(values))
                        
                        message_id_new = cursor.lastrowid
                        
                        # 记录访问日志（包括管理员）
                        access_type = 'aigc_text' if model == 'text' else 'aigc_image'
                        try:
                            cursor.execute("""
                                INSERT INTO user_access_logs 
                                (user_id, access_type, access_path, resource_id, resource_type)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (user_id, access_type, '/api/aigc/chat', session_id, 'aigc_session'))
                        except Exception as log_error:
                            # 不影响主流程，继续执行
                            pass
                        
                        conn.commit()
                        return message_id_new
                else:
                    # 兼容旧表结构
                    if user_message and not message_id:
                        cursor.execute("""
                            INSERT INTO qa_messages (session_id, sender, message_content)
                            VALUES (%s, 'user', %s)
                        """, (session_id, user_message))
                    if ai_message:
                        message_content = ai_message
                        if image_url:
                            message_content = json.dumps({
                                'content': ai_message,
                                'image_path': image_url
                            }, ensure_ascii=False)
                        if message_id:
                            cursor.execute("""
                                UPDATE qa_messages 
                                SET message_content = %s
                                WHERE id = %s
                            """, (message_content, message_id))
                        else:
                            cursor.execute("""
                                INSERT INTO qa_messages (session_id, sender, message_content)
                                VALUES (%s, 'ai', %s)
                            """, (session_id, message_content))
                    conn.commit()
                    return True if message_id else cursor.lastrowid
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False if message_id else None

def get_text_model():
    """获取文本模型（单例）"""
    try:
        from langchain_community.chat_models import ChatTongyi
        from langchain_openai import ChatOpenAI
        
        ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        if ALIYUN_API_KEY:
            try:
                return ChatTongyi(api_key=SecretStr(ALIYUN_API_KEY), model="qwen-turbo")
            except Exception as e:
                if OPENAI_API_KEY:
                    try:
                        return ChatOpenAI(model="gpt-3.5-turbo")
                    except Exception:
                        pass
        elif OPENAI_API_KEY:
            try:
                return ChatOpenAI(model="gpt-3.5-turbo")
            except Exception:
                pass
        return None
    except Exception:
        return None

def get_or_create_rag_system(user_id: int, db_config: Optional[Dict] = None):
    """获取或创建用户的RAG系统（延迟加载）"""
    if user_id in rag_systems:
        return rag_systems[user_id]
    
    text_model = get_text_model()
    if not text_model:
        return None
    
    try:
        # 延迟导入RAG模块，避免启动时加载
        from RAG import CulturalResourceRAG
        
        rag_system = CulturalResourceRAG(
            model=text_model,
            persist_directory="./chroma_db_web",
            database_name="java-project",
            db_config=db_config
        )
        rag_systems[user_id] = rag_system
        return rag_system
    except Exception as e:
        return None

def get_or_create_image_aigc_system(user_id: int, db_config: Optional[Dict] = None):
    """获取或创建用户的ImageAIGC系统（延迟加载）"""
    if user_id in image_aigc_systems:
        return image_aigc_systems[user_id]
    
    text_model = get_text_model()
    if not text_model:
        return None
    
    try:
        # 延迟导入ImageAIGC模块，避免启动时加载
        from image_RAG import ImageAIGC
        
        # 设置图片保存目录为项目根目录的AIGC_graph文件夹（使用相对路径）
        current_file_dir = os.path.dirname(os.path.realpath(__file__))
        base_dir = os.path.dirname(current_file_dir)
        aigc_graph_dir = os.path.join(base_dir, "AIGC_graph")
        os.makedirs(aigc_graph_dir, exist_ok=True)
        
        image_aigc_system = ImageAIGC(
            text_model=text_model,
            persist_directory="./chroma_db_image",
            database_name="java-project",
            local_save_dir=aigc_graph_dir,  # 指定保存到AIGC_graph文件夹
            db_config=db_config
        )
        image_aigc_systems[user_id] = image_aigc_system
        return image_aigc_system
    except Exception as e:
        return None
@app.route('/api/multimodal/search', methods=['POST'])
def multimodal_search():
    temp_dir = None
    image_paths = []
    try:
        mode = request.form.get('mode', 'text')
        query = request.form.get('query', '').strip()

        if 'images' in request.files:
            import tempfile
            import shutil
            temp_dir = tempfile.mkdtemp()
            try:
                files = request.files.getlist('images')
                for idx, file in enumerate(files):
                    if file.filename:
                        file_path = os.path.join(temp_dir, f"upload_{idx}_{file.filename}")
                        file.save(file_path)
                        image_paths.append(file_path)
            except Exception as e:
                pass

        user_id = (request.headers.get('X-User-Id') or 
                   request.headers.get('X-User-ID') or 
                   request.form.get('user_id') or
                   (request.json.get('user_id') if request.is_json else None))
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 401

        user_db_config = get_auth_system().get_user_db_config(user_id)
        if not user_db_config:
            return jsonify({'success': False, 'message': '用户不存在或未配置数据库'}), 401
        db_config = user_db_config['db_config']

        rag_system = get_or_create_rag_system(user_id, db_config)
        if not rag_system:
            return jsonify({'success': False, 'message': '文本模型未配置，无法检索'}), 500

        image_descriptions = []
        if image_paths:
            for p in image_paths:
                try:
                    desc = rag_system._read_image_info(p)
                    if desc:
                        image_descriptions.append(desc)
                except Exception as e:
                    pass

        query_parts = []
        if query:
            query_parts.append(query)
        if image_descriptions:
            query_parts.append(" ".join(image_descriptions))
        final_query = " ".join(query_parts).strip()
        if not final_query:
            return jsonify({'success': False, 'message': '缺少查询内容或图片描述失败'}), 400

        # 使用向量检索和数据库检索
        vector_results = []
        db_results = []
        try:
            # 向量检索
            vector_docs = rag_system._call_retriever(final_query)
            if vector_docs:
                for doc in vector_docs:
                    content = getattr(doc, "page_content", str(doc))
                    metadata = getattr(doc, "metadata", {})
                    vector_results.append({
                        "id": metadata.get('id', None),
                        "title": metadata.get('title', '向量检索结果'),
                        "content": content[:500],  # 限制长度
                        "source": metadata.get('source', '向量库'),
                        "table": "vector_store",
                        "resource_type": "向量"
                    })
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        try:
            # 数据库检索（不限制返回条数）
            db_results = rag_system.query_database(final_query)
        except Exception as e:
            import traceback
            traceback.print_exc()
            db_results = []  # 确保db_results是列表

        # 将结果分为图片和文字两类
        image_results = []
        text_results = []
        
        for result in db_results:
            # 判断是否为图片结果
            has_image = False
            image_url = None
            
            # 检查表名：crawled_images和AIGC_graph表的结果都是图片
            table_name = result.get('table', '')
            if table_name == 'crawled_images' or table_name == 'AIGC_graph':
                has_image = True
                # 获取图片URL
                if result.get('image_path'):
                    image_url = result['image_path']
                elif result.get('url'):
                    image_url = result['url']
            
            # 检查是否有图片路径字段
            elif result.get('image_path'):
                image_url = result['image_path']
                has_image = True
            elif result.get('url'):
                url = result['url']
                # 检查是否是图片文件扩展名
                if isinstance(url, str):
                    url_lower = url.lower()
                    if any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                        image_url = url
                        has_image = True
                    elif 'crawled_images' in url or 'AIGC_graph' in url or 'image_from_users' in url:
                        image_url = url
                        has_image = True
            
            # 检查resource_type字段
            resource_type = result.get('resource_type', '')
            if resource_type == '图像' or resource_type == '图片' or resource_type == 'image':
                has_image = True
                if not image_url:
                    # 尝试从其他字段获取图片URL
                    image_url = result.get('related_images_url') or result.get('url')
            
            # 处理图片URL，确保是完整的API路径
            if image_url and has_image:
                # 如果是从crawled_images关联的路径
                if 'crawled_images' in str(image_url) or str(image_url).startswith('crawled_images'):
                    actual_file = os.path.basename(str(image_url))
                    image_url = f"/api/images/crawled/{actual_file}"
                # 如果是AIGC_graph路径
                elif 'AIGC_graph' in str(image_url):
                    actual_file = os.path.basename(str(image_url))
                    image_url = f"/api/images/aigc/{actual_file}"
                # 如果是用户上传的图片
                elif 'image_from_users' in str(image_url) or 'AIGC_graph_from_users' in str(image_url):
                    actual_file = os.path.basename(str(image_url))
                    image_url = f"/AIGC_graph_from_users/{actual_file}"
                # 如果已经是完整URL，保持不变
                elif str(image_url).startswith('http://') or str(image_url).startswith('https://') or str(image_url).startswith('/'):
                    image_url = image_url
                # 其他情况，尝试作为文件名处理
                else:
                    image_url = f"/api/images/crawled/{os.path.basename(str(image_url))}"
            
            # 构建结果项
            result_item = {
                "id": result.get('id'),
                "title": result.get('title', ''),
                "content": result.get('content', ''),
                "source": result.get('source', ''),
                "table": table_name,
                "image_url": image_url if has_image else None,
                "resource_type": resource_type
            }
            
            if has_image:
                image_results.append(result_item)
            else:
                text_results.append(result_item)

        response = {
            "success": True,
            "query_used": final_query,
            "image_descriptions": image_descriptions,
            "vector_results": vector_results,  # 向量结果（新增）
            "text_results": text_results,      # 文字结果
            "image_results": image_results     # 图片结果
        }
        return jsonify(response)
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'message': f'服务器错误: {e}'}), 500
    finally:
        if image_paths:
            for p in image_paths:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except:
                    pass
        if temp_dir:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册接口"""
    try:
        # 处理表单数据（可能包含文件）
        password = None
        nickname = None
        security_question = None
        security_answer = None
        avatar_path = '/default.jpg'
        
        if request.is_json:
            data = request.json
            password = data.get('password', '').strip()
            nickname = data.get('nickname', '').strip()
            security_question = data.get('security_question', '').strip()
            security_answer = data.get('security_answer', '').strip()
            avatar_path = data.get('avatar_path', '/default.jpg')
        else:
            # 处理multipart/form-data
            password = request.form.get('password', '').strip()
            nickname = request.form.get('nickname', '').strip()
            security_question = request.form.get('security_question', '').strip()
            security_answer = request.form.get('security_answer', '').strip()
            
            # 处理头像上传（在注册成功后，使用生成的account作为文件名）
            if 'avatar' in request.files:
                avatar_file = request.files['avatar']
                if avatar_file.filename:
                    # 先保存为临时文件，注册成功后再重命名
                    import tempfile
                    # 获取文件扩展名
                    file_ext = os.path.splitext(avatar_file.filename)[1].lower()
                    if file_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        file_ext = '.jpg'  # 默认使用jpg
                    # 创建临时文件
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
                    avatar_file.save(temp_file.name)
                    avatar_path = temp_file.name  # 临时保存路径，注册成功后会重命名
        
        if not password:
            return jsonify({'success': False, 'message': '密码不能为空'}), 400
        
        # 调用注册接口（account会自动生成）
        result = get_auth_system().register(
            password=password,
            nickname=nickname if nickname else None,
            avatar_path=None,  # 先不传头像路径，注册成功后再处理
            security_question=security_question if security_question else None,
            security_answer=security_answer if security_answer else None
        )
        
        # 如果注册成功，处理头像上传和日志记录
        if result.get('success') and result.get('user_info'):
            user_id = result['user_info'].get('id')
            account = result['user_info'].get('account')
            
            # 记录注册日志
            if user_id and account:
                UserLogging.log_register(user_id, account)
            
            # 处理头像上传（如果有）
            if not request.is_json and 'avatar' in request.files and avatar_path and avatar_path != '/default.jpg':
                try:
                    import shutil
                    if os.path.exists(avatar_path):
                        # 使用项目根目录的public文件夹（与start_dev.bat同目录）
                        public_dir = os.path.join(project_root, 'public')
                        os.makedirs(public_dir, exist_ok=True)
                        
                        # 获取文件扩展名
                        file_ext = os.path.splitext(avatar_path)[1].lower()
                        if file_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                            file_ext = '.jpg'
                        
                        # 使用account作为文件名
                        avatar_filename = f'{account}{file_ext}'
                        final_avatar_path = os.path.join(public_dir, avatar_filename)
                        
                        # 移动临时文件到最终位置
                        shutil.move(avatar_path, final_avatar_path)
                        
                        # 转换为web路径格式
                        avatar_path = f'/{avatar_filename}'
                        
                        # 更新数据库
                        from db_connection import get_user_db_connection
                        conn = get_user_db_connection()
                        if conn:
                            try:
                                with conn.cursor() as cursor:
                                    cursor.execute(
                                        "UPDATE users SET avatar_path = %s WHERE id = %s",
                                        (avatar_path, user_id)
                                    )
                                    conn.commit()
                                    result['user_info']['avatar_path'] = avatar_path
                            finally:
                                conn.close()
                    else:
                        avatar_path = '/default.jpg'
                except Exception as e:
                    # 如果头像处理失败，使用默认头像
                    avatar_path = '/default.jpg'
            elif request.is_json and avatar_path and avatar_path != '/default.jpg':
                # JSON请求中直接使用提供的头像路径
                try:
                    from db_connection import get_user_db_connection
                    conn = get_user_db_connection()
                    if conn:
                        try:
                            with conn.cursor() as cursor:
                                cursor.execute(
                                    "UPDATE users SET avatar_path = %s WHERE id = %s",
                                    (avatar_path, user_id)
                                )
                                conn.commit()
                                result['user_info']['avatar_path'] = avatar_path
                        finally:
                            conn.close()
                except Exception as e:
                    pass
        
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'注册失败：{str(e)}'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录接口"""
    try:
        # 检查请求是否为JSON格式
        if not request.is_json:
            return jsonify({'success': False, 'message': '请求格式错误，需要JSON格式'}), 400
        
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': '请求数据为空'}), 400
        
        account = data.get('account', '').strip() if data.get('account') else ''
        password = data.get('password', '').strip() if data.get('password') else ''
        
        if not account or not password:
            return jsonify({'success': False, 'message': '账号和密码不能为空'}), 400
        
        result = get_auth_system().login(account, password)
        
        # 确保result不为None
        if not result:
            return jsonify({'success': False, 'message': '登录处理失败，请稍后重试'}), 500
        
        # 确保result是字典格式
        if not isinstance(result, dict):
            return jsonify({'success': False, 'message': '登录处理失败，服务器返回格式错误'}), 500
        
        # 记录登录日志
        if result.get('success') and result.get('user_info'):
            user_id = result['user_info'].get('id')
            if user_id:
                try:
                    UserLogging.log_login(user_id, account)
                except Exception as log_error:
                    import traceback
                    traceback.print_exc()
                    # 日志记录失败不影响登录流程
        
        # 如果登录失败，返回适当的HTTP状态码
        if not result.get('success'):
            # 根据错误类型返回不同的状态码
            error_message = result.get('message', '登录失败')
            if '不存在' in error_message or '账号' in error_message:
                return jsonify(result), 404
            elif '密码' in error_message:
                return jsonify(result), 401
            else:
                return jsonify(result), 400
        
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'登录失败：{str(e)}'}), 500

@app.route('/api/auth/update-nickname', methods=['POST'])
def update_nickname():
    """修改用户昵称"""
    try:
        user_id = request.headers.get('X-User-Id') or request.json.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        user_id = int(user_id)
        data = request.json
        nickname = data.get('nickname', '').strip()
        
        if not nickname:
            return jsonify({'success': False, 'message': '昵称不能为空'}), 400
        
        result = get_auth_system().update_nickname(user_id, nickname)
        
        # 如果修改成功，返回更新后的用户信息
        if result.get('success'):
            user_info = get_auth_system().get_user_by_id(user_id)
            if user_info:
                result['user_info'] = user_info
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'修改昵称失败：{str(e)}'}), 500

@app.route('/api/auth/update-signature', methods=['POST'])
def update_signature():
    """修改个人签名"""
    try:
        user_id = request.headers.get('X-User-Id') or request.json.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        user_id = int(user_id)
        data = request.json
        signature = data.get('signature', '').strip()
        
        if len(signature) > 500:
            return jsonify({'success': False, 'message': '个人签名长度不能超过500个字符'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET signature = %s WHERE id = %s",
                    (signature, user_id)
                )
                conn.commit()
            
            # 返回更新后的用户信息
            user_info = get_auth_system().get_user_by_id(user_id)
            if user_info:
                return jsonify({
                    'success': True,
                    'message': '个人签名修改成功',
                    'user_info': {
                        'id': user_info.get('id'),
                        'account': user_info.get('account'),
                        'nickname': user_info.get('nickname'),
                        'signature': user_info.get('signature'),
                        'avatar_path': user_info.get('avatar_path'),
                        'role': user_info.get('role')
                    }
                })
            else:
                return jsonify({'success': True, 'message': '个人签名修改成功'})
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'修改个人签名失败：{str(e)}'}), 500

@app.route('/api/auth/delete-account', methods=['POST'])
def delete_account():
    """注销账号（删除用户及其所有数据）"""
    try:
        user_id = request.headers.get('X-User-Id') or request.json.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        user_id = int(user_id)
        data = request.json
        password = data.get('password', '')
        
        if not password:
            return jsonify({'success': False, 'message': '请输入密码确认'}), 400
        
        # 验证密码
        user_info = get_auth_system().get_user_by_id(user_id)
        if not user_info:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if user_info.get('password_hash') != password_hash:
            return jsonify({'success': False, 'message': '密码错误'}), 400
        
        # 删除用户及其所有数据
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 删除用户的所有数据（根据外键约束，相关数据会被级联删除或设置为NULL）
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()
            
            return jsonify({'success': True, 'message': '账号已注销'})
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'注销账号失败：{str(e)}'}), 500

@app.route('/api/auth/user', methods=['GET'])
def get_user():
    """获取当前用户信息（通过user_id参数）"""
    try:
        user_id = request.args.get('user_id', type=int)
        if not user_id:
            return jsonify({'success': False, 'message': '缺少user_id参数'}), 400
        
        user_info = get_auth_system().get_user_by_id(user_id)
        if user_info:
            # 不返回敏感信息（密码哈希、安全问题答案哈希）
            safe_user_info = {
                'id': user_info.get('id'),
            'account': user_info.get('account'),
            'nickname': user_info.get('nickname'),
            'signature': user_info.get('signature'),
            'avatar_path': user_info.get('avatar_path'),
            'role': user_info.get('role'),
            'security_question': user_info.get('security_question')
            }
            return jsonify({'success': True, 'user_info': safe_user_info})
        else:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取用户信息失败：{str(e)}'}), 500

@app.route('/api/auth/change-password', methods=['POST'])
def change_password():
    """修改密码接口"""
    try:
        data = request.json
        user_id = request.headers.get('X-User-Id', type=int)
        old_password = data.get('old_password', '').strip()
        new_password = data.get('new_password', '').strip()
        
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        
        if not old_password or not new_password:
            return jsonify({'success': False, 'message': '旧密码和新密码不能为空'}), 400
        
        # 检查新密码是否与原密码相同
        if old_password == new_password:
            return jsonify({'success': False, 'message': '新密码不能与原密码相同'}), 400
        
        result = get_auth_system().update_password(user_id, old_password, new_password)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'修改密码失败：{str(e)}'}), 500

@app.route('/api/auth/change-password-by-security', methods=['POST'])
def change_password_by_security():
    """通过二级密码修改密码接口"""
    try:
        data = request.json
        user_id = request.headers.get('X-User-Id', type=int)
        security_answer = data.get('security_answer', '').strip()
        new_password = data.get('new_password', '').strip()
        
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        
        if not security_answer or not new_password:
            return jsonify({'success': False, 'message': '二级密码答案和新密码不能为空'}), 400
        
        # 先验证二级密码答案
        verify_result = get_auth_system().verify_security_question(user_id, security_answer)
        if not verify_result.get('success'):
            return jsonify(verify_result), 400
        
        # 获取用户当前密码（用于检查是否相同）
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user:
                    return jsonify({'success': False, 'message': '用户不存在'}), 404
                
                # 检查新密码是否与原密码相同
                import hashlib
                new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                if new_password_hash == user['password_hash']:
                    return jsonify({'success': False, 'message': '新密码不能与原密码相同'}), 400
                
                # 更新密码
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (new_password_hash, user_id)
                )
                conn.commit()
                return jsonify({'success': True, 'message': '密码修改成功'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'message': f'修改密码失败：{str(e)}'}), 500

@app.route('/api/auth/verify-security-answer', methods=['POST'])
def verify_security_answer():
    """验证安全问题答案接口"""
    try:
        data = request.json
        user_id = request.headers.get('X-User-Id', type=int)
        answer = data.get('answer', '').strip()
        
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        
        if not answer:
            return jsonify({'success': False, 'message': '请输入答案'}), 400
        
        result = auth_system.verify_security_question(user_id, answer)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'验证失败：{str(e)}'}), 500

@app.route('/api/auth/change-security-question', methods=['POST'])
def change_security_question():
    """更换安全问题接口"""
    try:
        data = request.json
        user_id = request.headers.get('X-User-Id', type=int)
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        
        if not question or not answer:
            return jsonify({'success': False, 'message': '问题和答案不能为空'}), 400
        
        result = get_auth_system().update_security_question(user_id, question, answer)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'更换失败：{str(e)}'}), 500

@app.route('/api/auth/forgot-password/question', methods=['POST'])
def get_security_question_for_reset():
    """获取用户的安全问题（用于重置密码）"""
    try:
        data = request.json
        account = data.get('account', '').strip()
        
        if not account:
            return jsonify({'success': False, 'message': '请输入账号'}), 400
        
        result = get_auth_system().get_security_question(account)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取安全问题失败：{str(e)}'}), 500

@app.route('/api/auth/forgot-password/verify', methods=['POST'])
def verify_security_answer_for_reset():
    """验证安全问题答案（用于重置密码）"""
    try:
        data = request.json
        account = data.get('account', '').strip()
        answer = data.get('answer', '').strip()
        
        if not account:
            return jsonify({'success': False, 'message': '请输入账号'}), 400
        
        if not answer:
            return jsonify({'success': False, 'message': '请输入安全问题答案'}), 400
        
        result = get_auth_system().verify_security_answer(account, answer)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'验证失败：{str(e)}'}), 500

@app.route('/api/auth/forgot-password/reset', methods=['POST'])
def reset_password_via_security():
    """通过安全问题重置密码"""
    try:
        data = request.json
        account = data.get('account', '').strip()
        answer = data.get('answer', '').strip()
        new_password = data.get('new_password', '').strip()
        
        if not account:
            return jsonify({'success': False, 'message': '请输入账号'}), 400
        
        if not answer:
            return jsonify({'success': False, 'message': '请输入安全问题答案'}), 400
        
        if not new_password:
            return jsonify({'success': False, 'message': '请输入新密码'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': '密码至少需要6个字符'}), 400
        
        # 先验证答案
        verify_result = auth_system.verify_security_answer(account, answer)
        if not verify_result.get('success'):
            return jsonify(verify_result), 400
        
        # 验证通过后重置密码
        result = get_auth_system().reset_password(account, new_password)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': f'重置密码失败：{str(e)}'}), 500

@app.route('/api/auth/change-avatar', methods=['POST'])
def change_avatar():
    """更换头像接口"""
    try:
        user_id = request.headers.get('X-User-Id', type=int)
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        
        # 获取用户信息
        user_info = get_auth_system().get_user_by_id(user_id)
        if not user_info:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        
        account = user_info.get('account')
        old_avatar_path = user_info.get('avatar_path', '/default.jpg')
        
        # 判断是上传新头像还是使用默认头像
        if request.is_json:
            # 使用默认头像
            data = request.json
            use_default = data.get('use_default', False)
            
            if use_default:
                # 如果当前头像不是默认头像，删除旧头像
                if old_avatar_path and old_avatar_path != '/default.jpg' and old_avatar_path != './default.jpg':
                    try:
                        old_filename = old_avatar_path.lstrip('/')
                        old_file_path = os.path.join(public_dir, old_filename)
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    except Exception as e:
                        pass
                
                # 更新数据库
                from db_connection import get_user_db_connection
                conn = get_user_db_connection()
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "UPDATE users SET avatar_path = %s WHERE id = %s",
                                ('/default.jpg', user_id)
                            )
                            conn.commit()
                        return jsonify({
                            'success': True,
                            'message': '已切换为默认头像',
                            'avatar_path': '/default.jpg'
                        })
                    finally:
                        conn.close()
                else:
                    return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        else:
            # 上传新头像
            if 'avatar' not in request.files:
                return jsonify({'success': False, 'message': '请选择头像文件'}), 400
            
            avatar_file = request.files['avatar']
            if not avatar_file.filename:
                return jsonify({'success': False, 'message': '请选择头像文件'}), 400
            
            from werkzeug.utils import secure_filename
            
            # 获取文件扩展名
            file_ext = os.path.splitext(avatar_file.filename)[1].lower()
            if file_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                file_ext = '.jpg'  # 默认使用jpg
            
            # 先保存为 账号1.扩展名
            temp_filename = f'{account}1{file_ext}'
            temp_path = os.path.join(public_dir, temp_filename)
            avatar_file.save(temp_path)
            
            # 删除旧头像（如果存在且不是默认头像）
            if old_avatar_path and old_avatar_path != '/default.jpg' and old_avatar_path != './default.jpg':
                try:
                    old_filename = old_avatar_path.lstrip('/')
                    old_file_path = os.path.join(public_dir, old_filename)
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                except Exception as e:
                    pass
            
            # 处理头像：压缩到200x200并重命名
            from PIL import Image
            try:
                # 打开图片
                img = Image.open(temp_path)
                # 转换为RGB（如果是RGBA）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                # 压缩到200x200（正方形）
                img = img.resize((200, 200), Image.Resampling.LANCZOS)
                # 重命名为 账号.jpg（统一使用jpg格式）
                final_filename = f'{account}.jpg'
                final_path = os.path.join(public_dir, final_filename)
                # 保存压缩后的图片
                img.save(final_path, 'JPEG', quality=90)
                # 删除临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                # 如果PIL处理失败，使用原文件
                final_filename = f'{account}{file_ext}'
                final_path = os.path.join(public_dir, final_filename)
                if os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(temp_path, final_path)
            
            # 更新数据库
            new_avatar_path = f'/{final_filename}'
            from db_connection import get_user_db_connection
            conn = get_user_db_connection()
            if conn:
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "UPDATE users SET avatar_path = %s WHERE id = %s",
                            (new_avatar_path, user_id)
                        )
                        conn.commit()
                    return jsonify({
                        'success': True,
                        'message': '头像更换成功',
                        'avatar_path': new_avatar_path
                    })
                finally:
                    conn.close()
            else:
                return jsonify({'success': False, 'message': '数据库连接失败'}), 500
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'更换头像失败：{str(e)}'}), 500

def log_user_access(user_id, access_type, access_path=None, resource_id=None, resource_type=None):
    """记录用户访问日志（包括管理员）"""
    try:
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO user_access_logs 
                    (user_id, access_type, access_path, resource_id, resource_type)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, access_type, access_path, resource_id, resource_type))
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    except Exception as e:
        pass


@app.route('/api/aigc/chat', methods=['POST'])
def aigc_chat():
    """处理AIGC聊天请求（支持流式输出）"""
    # 在函数开始处初始化所有可能用到的变量，确保它们始终被定义
    image_paths = []  # 在函数开始处初始化，确保finally中可用
    rag_system = None  # 初始化rag_system，避免UnboundLocalError
    try:
        mode = request.form.get('mode', 'text')
        query = request.form.get('query', '')
        stream = request.form.get('stream', 'false').lower() == 'true'
        session_id = request.form.get('session_id')  # 从请求中获取session_id
        
        # 将session_id转换为整数（如果存在）
        if session_id:
            try:
                session_id = int(session_id)
            except (ValueError, TypeError):
                session_id = None
        else:
            session_id = None
        
        
        # 处理图片上传（文字和图片AIGC都支持）
        temp_dir = None
        user_uploaded_image_urls = []  # 存储用户上传图片的URL（用于保存到数据库）
        if 'images' in request.files:
            import tempfile
            import shutil
            from werkzeug.utils import secure_filename
            from datetime import datetime
            import uuid
            
            temp_dir = tempfile.mkdtemp()
            try:
                files = request.files.getlist('images')
                # 创建AIGC_graph_from_users文件夹（与AIGC_graph同目录，使用相对路径）
                current_file_dir = os.path.dirname(os.path.realpath(__file__))
                base_dir = os.path.dirname(current_file_dir)
                aigc_graph_from_users_dir = os.path.join(base_dir, "AIGC_graph_from_users")
                os.makedirs(aigc_graph_from_users_dir, exist_ok=True)
                
                for idx, file in enumerate(files):
                    if file.filename:
                        # 临时保存用于处理
                        temp_file_path = os.path.join(temp_dir, f"upload_{idx}_{file.filename}")
                        file.save(temp_file_path)
                        image_paths.append(temp_file_path)
                        
                        # 注意：此时user_id还未定义，需要先获取user_id后再保存图片
                        # 这里先保存到临时目录，稍后在获取user_id后再保存到AIGC_graph_from_users文件夹
            except Exception as e:
                import traceback
                traceback.print_exc()
        
        # 如果没有查询内容且没有图片，返回错误
        if not query and not image_paths:
            return jsonify({'error': '查询内容或图片不能同时为空', 'answer': '请输入查询内容或上传图片'}), 400
        
        # 获取用户ID（从请求头、表单数据或JSON数据）
        user_id = (request.headers.get('X-User-Id') or 
                   request.headers.get('X-User-ID') or 
                   request.form.get('user_id') or
                   (request.json.get('user_id') if request.is_json else None))
        if not user_id:
            return jsonify({
                'error': '缺少用户信息',
                'answer': '请先登录后再使用AIGC功能'
            }), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({
                'error': '无效的用户ID',
                'answer': '用户信息无效，请重新登录'
            }), 401
        
        # 获取用户的数据库配置
        user_db_config = get_auth_system().get_user_db_config(user_id)
        if not user_db_config:
            return jsonify({
                'error': '用户不存在',
                'answer': '用户信息无效，请重新登录'
            }), 401
        
        db_config = user_db_config['db_config']
        
        # 现在user_id已获取，保存用户上传的图片到image_from_users文件夹
        if image_paths and (query or session_id):
            import shutil
            from werkzeug.utils import secure_filename
            from datetime import datetime
            
            # 获取用户账号
            user_info = get_auth_system().get_user_by_id(user_id)
            if not user_info:
                user_account = str(user_id)
            else:
                user_account = user_info.get('account', str(user_id))
            
            # 创建AIGC_graph_from_users文件夹（与AIGC_graph同目录）
            # 使用相对路径
            current_file_dir = os.path.dirname(os.path.realpath(__file__))
            base_dir = os.path.dirname(current_file_dir)
            aigc_graph_from_users_dir = os.path.join(base_dir, "AIGC_graph_from_users")
            os.makedirs(aigc_graph_from_users_dir, exist_ok=True)
            
            # 保存每个上传的图片
            base_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            for idx, temp_file_path in enumerate(image_paths):
                try:
                    # 生成文件名：用户账号-上传时间.扩展名
                    # 如果有多张图片，添加索引避免冲突
                    if len(image_paths) > 1:
                        timestamp = f"{base_timestamp}_{idx + 1}"
                    else:
                        timestamp = base_timestamp
                    # 从临时文件路径获取原始文件名以获取扩展名
                    original_filename = os.path.basename(temp_file_path)
                    if original_filename.startswith('upload_'):
                        # 提取原始文件名（去掉upload_前缀和索引）
                        parts = original_filename.split('_', 2)
                        if len(parts) >= 3:
                            original_filename = parts[2]
                    safe_filename = secure_filename(original_filename)
                    file_ext = os.path.splitext(safe_filename)[1] or '.jpg'
                    # 文件命名格式：用户账号-上传时间.扩展名
                    saved_filename = f"{user_account}-{timestamp}{file_ext}"
                    saved_path = os.path.join(aigc_graph_from_users_dir, saved_filename)
                    
                    # 复制文件到AIGC_graph_from_users文件夹
                    shutil.copy2(temp_file_path, saved_path)
                    
                    # 构建URL（相对路径）
                    image_url = f'/AIGC_graph_from_users/{saved_filename}'
                    user_uploaded_image_urls.append(image_url)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
        
        if mode == 'text':
            # 文字AIGC模式：使用RAG系统（Tongyi模型）
            rag_system = get_or_create_rag_system(user_id, db_config)
            if not rag_system:
                return jsonify({
                    'error': 'RAG系统未初始化',
                    'answer': '抱歉，系统未正确配置，请检查API密钥设置。'
                }), 500
            
            try:
                # 处理图片理解：如果有图片，先理解图片内容
                image_descriptions = []
                if image_paths:
                    for img_path in image_paths:
                        try:
                            desc = rag_system._read_image_info(img_path)
                            if desc:
                                image_descriptions.append(desc)
                        except Exception as e:
                            pass
                
                # 构建最终查询：如果有图片描述，合并到查询中
                final_query = query
                if image_descriptions:
                    image_context = "\n".join(image_descriptions)
                    if not final_query:
                        # 如果没有文字提示，默认生成故事
                        final_query = f"请根据以下图片内容，创作一个像夸父逐日、嫦娥奔月这样具有辨识度的传统文化故事。图片内容：{image_context}"
                    else:
                        # 如果有文字提示，将图片信息作为上下文
                        final_query = f"{query}\n\n图片信息：{image_context}"
                
                # 如果没有查询且没有图片描述，使用默认提示
                if not final_query:
                    final_query = "请创作一个像夸父逐日、嫦娥奔月这样具有辨识度的传统文化故事"
                
                # 立即保存用户消息到数据库（在调用RAG之前）
                message_id = None
                if session_id:
                    try:
                        # 先保存用户消息（AI消息暂时为空，稍后更新）
                        # 文字AIGC如果没有图片，使用AIGC_graph/default.jpg
                        default_image_url = '/AIGC_graph/default.jpg'
                        message_id = save_aigc_message_to_db(
                            user_id=user_id,
                            session_id=session_id,
                            user_message=final_query,
                            ai_message="",  # 先保存空消息，AI生成后再更新
                            model='text',
                            image_url=default_image_url if not user_uploaded_image_urls else None,
                            image_from_users_url=user_uploaded_image_urls[0] if user_uploaded_image_urls else None,
                            db_config=db_config
                        )
                    except Exception as save_error:
                        import traceback
                        traceback.print_exc()
                
                
                # 确保image_paths参数正确传递
                result = rag_system.ask(
                    query=final_query,
                    image_paths=image_paths if image_paths else None,
                    use_history=True
                )
                
                # 确保返回的answer字段不为空
                answer = result.get('answer', '')
                if not answer:
                    answer = '抱歉，未能生成有效回答。请检查输入内容或稍后重试。'
                
                # 获取检索到的资源
                retrieved_resources = result.get('retrieved_resources', {})
                
                # 从检索结果中提取资源ID列表
                retrieval_ids = []
                try:
                    database_results = retrieved_resources.get('database_results', [])
                    for db_result in database_results:
                        resource_id = db_result.get('resource_id')
                        if resource_id:
                            retrieval_ids.append(str(resource_id))
                    retrieval_id_str = ','.join(retrieval_ids) if retrieval_ids else None
                except Exception as e:
                    retrieval_id_str = None
                
                # 保存AIGC生成的文字资源到数据库
                try:
                    # 从查询中提取资源标题（使用查询的前50字作为标题）
                    resource_title = final_query[:50] if len(final_query) > 50 else final_query
                    if not resource_title:
                        resource_title = "AIGC生成的文化资源"
                    
                    # 提取节日名称
                    festival_names = extract_festival_names(answer + " " + final_query)
                    festival_title = festival_names[0] if festival_names else None
                    
                    # 保存到AIGC_cultural_resources和AIGC_cultural_entities表
                    save_aigc_text_resource(
                        db_config=db_config,
                        resource_title=resource_title,
                        content_text=answer,
                        source_from="Tongyi文字生成",
                        festival_title=festival_title,
                        tags=result.get('key_entities', [])
                    )
                except Exception as e:
                    # 不影响正常返回，继续执行
                    pass
                
                # 更新消息到数据库（使用message_id更新，而不是再次插入）
                if session_id and message_id:
                    try:
                        # 文字AIGC如果没有图片，使用AIGC_graph/default.jpg
                        default_image_url = '/AIGC_graph/default.jpg'
                        save_aigc_message_to_db(
                            user_id=user_id,
                            session_id=session_id,
                            user_message=final_query,
                            ai_message=answer,
                            model='text',
                            image_url=default_image_url if not user_uploaded_image_urls else None,
                            retrieval_id=retrieval_id_str,
                            message_id=message_id,  # 使用message_id更新现有消息
                            db_config=db_config
                        )
                        # 记录文字AIGC使用日志
                        UserLogging.log_aigc_text(user_id, final_query)
                    except Exception as save_error:
                        import traceback
                        traceback.print_exc()
                
                
                # 非流式输出（普通模式，不再支持流式输出）
                return jsonify({
                    'answer': answer,
                    'key_entities': result.get('key_entities', []),
                    'sources': result.get('sources', ''),
                    'confidence': result.get('confidence', 0),
                    'retrieved_resources': retrieved_resources
                })
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                
                # 返回更详细的错误信息
                error_msg = str(e)
                error_lower = error_msg.lower()
                if "model" in error_lower or "api" in error_lower or "key" in error_lower:
                    error_msg += "\n\n可能原因：\n1. API密钥未配置或无效\n2. 网络连接问题\n3. API服务暂时不可用"
                elif "database" in error_lower or "mysql" in error_lower:
                    error_msg += "\n\n可能原因：\n1. 数据库连接失败\n2. 数据库配置错误"
                
                return jsonify({
                    'error': error_msg,
                    'answer': f'处理失败：{error_msg}'
                }), 500
                
        elif mode == 'image':
            # 图片AIGC模式：使用ImageAIGC系统（Huoshan模型）
            # 注意：rag_system已在函数开始处初始化为None，这里不需要再次初始化
            message_id = None
            user_original_query = ""
            image_from_users_url_json = None
            
            image_aigc_system = get_or_create_image_aigc_system(user_id, db_config)
            if not image_aigc_system:
                error_msg = 'ImageAIGC系统未初始化，请检查API密钥设置'
                return jsonify({
                    'error': error_msg,
                    'answer': f'抱歉，{error_msg}。'
                }), 500
            
            # 初始化RAG系统（用于图片理解和故事生成）
            # rag_system已在函数开始处初始化为None，这里只需要赋值
            try:
                rag_system = get_or_create_rag_system(user_id, db_config)
            except Exception as rag_init_error:
                import traceback
                traceback.print_exc()
                rag_system = None
            
            # 在try块外初始化变量，确保在异常处理中可用
            story_prompt = query if query else "请创作一个像夸父逐日、嫦娥奔月这样具有辨识度的传统文化故事"
            user_original_query = query if query else ""
            
            try:
                
                # 处理图片理解：如果有图片，先理解图片内容
                image_descriptions = []
                if image_paths:
                    # 使用RAG系统来理解图片（如果有的话）
                    if rag_system:
                        for img_path in image_paths:
                            try:
                                desc = rag_system._read_image_info(img_path)
                                if desc:
                                    image_descriptions.append(desc)
                            except Exception as e:
                                pass
                
                # 更新story_prompt（如果有图片描述）
                if image_descriptions:
                    image_context = "\n".join(image_descriptions)
                    if query:
                        story_prompt = f"{query}\n\n图片信息：{image_context}"
                    else:
                        story_prompt = f"请根据以下图片内容，创作一个像夸父逐日、嫦娥奔月这样具有辨识度的传统文化故事。图片内容：{image_context}"
                
                # 确保story_prompt始终有值，用于后续降级处理
                if not story_prompt:
                    story_prompt = "请创作一个传统文化故事"
                if not user_original_query:
                    user_original_query = "（根据上传的图片自动生成）"
                
                # 立即保存用户消息到数据库（在生成图片之前）
                message_id = None
                if session_id:
                    try:
                        # 先保存用户消息（AI消息暂时为空，稍后更新）
                        # 图片AIGC如果没有上传图片，使用AIGC_graph/default.jpg
                        default_image_url = '/AIGC_graph/default.jpg'
                        message_id = save_aigc_message_to_db(
                            user_id=user_id,
                            session_id=session_id,
                            user_message=user_original_query if user_original_query else "（根据上传的图片自动生成）",
                            ai_message="",  # 先保存空消息，AI生成后再更新
                            model='image',
                            image_url=default_image_url if not user_uploaded_image_urls else None,
                            image_from_users_url=json.dumps(user_uploaded_image_urls, ensure_ascii=False) if user_uploaded_image_urls else None,
                            db_config=db_config
                        )
                    except Exception as save_error:
                        import traceback
                        traceback.print_exc()
                
                # 第一步：先生成完整故事
                story = ""
                if rag_system:
                    story_result = rag_system.ask(
                        query=story_prompt,
                        image_paths=None,
                        use_history=False
                    )
                    story = story_result.get('answer', '')
                    if not story:
                        story = story_prompt
                else:
                    story = story_prompt
                
                # 第二步：根据完整故事生成连环画
                final_prompt = f"根据以下完整故事创作一组连环画，要求画面精美、以假乱真，故事要连贯完整：\n\n{story}"
                
                # 从查询中提取风格（如果有）
                style = "传统节日风格"
                if "风格" in final_prompt or "style" in final_prompt.lower():
                    # 尝试提取风格信息
                    pass
                
                
                # 生成图片
                try:
                    image_path = image_aigc_system.generate_image(
                        prompt=final_prompt,
                        style=style,
                        image_paths=image_paths if image_paths else None,
                        use_history=True
                    )
                except Exception as gen_error:
                    import traceback
                    error_trace = traceback.format_exc()
                    image_path = None  # 确保image_path为None
                
                # 检查image_path是否有效（非空且非空字符串）
                if image_path and image_path.strip():
                    # 使用相对路径
                    current_file_dir = os.path.dirname(os.path.realpath(__file__))
                    base_dir = os.path.dirname(current_file_dir)
                    aigc_graph_dir = os.path.join(base_dir, "AIGC_graph")
                    
                    # 检查是否是连环画（JSON格式）
                    is_comic = False
                    comic_data = None
                    image_urls = []
                    
                    try:
                        # 尝试解析为JSON，判断是否是连环画
                        if isinstance(image_path, str) and image_path.strip().startswith('{'):
                            comic_data = json.loads(image_path)
                            if isinstance(comic_data, dict) and comic_data.get('type') == 'comic':
                                is_comic = True
                                comic_paths = comic_data.get('paths', [])
                    except (json.JSONDecodeError, AttributeError):
                        # 不是JSON格式，按单个图片处理
                        pass
                    
                    if is_comic and comic_data:
                        # 处理连环画：转换所有图片路径为URL
                        comic_paths = comic_data.get('paths', [])
                        for path in comic_paths:
                            if os.path.isabs(path) and aigc_graph_dir in path:
                                filename = os.path.basename(path)
                                image_urls.append(f'/AIGC_graph/{filename}')
                            elif path.startswith('/'):
                                image_urls.append(path)
                            elif path.startswith('AIGC_graph/'):
                                image_urls.append(f'/{path}')
                            else:
                                filename = os.path.basename(path)
                                image_urls.append(f'/AIGC_graph/{filename}')
                        
                        
                        # 保存连环画的所有图片到数据库
                        try:
                            prompt_for_tags = final_prompt if 'final_prompt' in locals() else query
                            festival_names = extract_festival_names(prompt_for_tags)
                            tags = festival_names + [style] if style else festival_names
                            
                            # 为每张图片保存到数据库
                            for path in comic_paths:
                                save_aigc_image(
                                    db_config=db_config,
                                    image_path=path,
                                    source_from="Huoshan连环画生成",
                                    tags=tags
                                )
                        except Exception as e:
                            # 不影响正常返回，继续执行
                            pass
                        
                        # 更新之前保存的用户消息，添加AI回答（如果之前已保存）
                        image_from_users_url_json = json.dumps(user_uploaded_image_urls, ensure_ascii=False) if user_uploaded_image_urls else None
                        if session_id and message_id:
                            try:
                                # 连环画：将所有图片路径保存为JSON字符串到image_url字段
                                # 格式：{"type": "comic", "paths": ["/AIGC_graph/0001.jpeg", ...], "count": 8}
                                comic_data_json = json.dumps({
                                    "type": "comic",
                                    "paths": image_urls,
                                    "count": len(image_urls)
                                }, ensure_ascii=False)
                                
                                # 使用save_aigc_message_to_db更新消息
                                save_aigc_message_to_db(
                                    user_id=user_id,
                                    session_id=session_id,
                                    user_message=user_original_query if user_original_query else "（根据上传的图片自动生成）",
                                    ai_message=f'连环画生成成功！共{len(image_urls)}张图片。\n提示词：{final_prompt}',
                                    model='image',
                                    image_url=comic_data_json,
                                    image_from_users_url=image_from_users_url_json,
                                    message_id=message_id,  # 使用message_id更新现有消息
                                    db_config=db_config
                                )
                                # 记录图片AIGC使用日志
                                UserLogging.log_aigc_image(user_id, final_prompt)
                            except Exception as save_error:
                                import traceback
                                traceback.print_exc()
                        
                        
                        # 返回连环画数据
                        return jsonify({
                            'answer': f'连环画生成成功！共{len(image_urls)}张图片。\n提示词：{final_prompt}',
                            'image_path': image_urls[0] if image_urls else None,  # 第一张图片作为主图
                            'image_paths': image_urls,  # 所有图片路径列表
                            'is_comic': True,  # 标识这是连环画
                            'comic_count': len(image_urls),  # 连环画数量
                            'model': 'image'
                        })
                    else:
                        # 处理单个图片
                        # 保存AIGC生成的图片到数据库
                        try:
                            # 从查询中提取标签
                            prompt_for_tags = final_prompt if 'final_prompt' in locals() else query
                            festival_names = extract_festival_names(prompt_for_tags)
                            tags = festival_names + [style] if style else festival_names
                            
                            save_aigc_image(
                                db_config=db_config,
                                image_path=image_path,
                                source_from="Huoshan图片生成",
                                tags=tags
                            )
                        except Exception as e:
                            # 不影响正常返回，继续执行
                            pass
                        
                        # 构建图片URL（相对路径）
                        # image_path可能是绝对路径（如：D:\git\mygit\Java-project\AIGC_graph\0001.jpeg）
                        # 需要转换为相对路径（如：/AIGC_graph/0001.jpeg）
                        if os.path.isabs(image_path) and aigc_graph_dir in image_path:
                            # 提取文件名
                            filename = os.path.basename(image_path)
                            image_url = f'/AIGC_graph/{filename}'
                        elif image_path.startswith('/'):
                            # 已经是相对路径，直接使用
                            image_url = image_path
                        elif image_path.startswith('AIGC_graph/'):
                            # 已经是相对路径格式，添加前导斜杠
                            image_url = f'/{image_path}'
                        else:
                            # 其他情况，假设是文件名，添加路径前缀
                            filename = os.path.basename(image_path)
                            image_url = f'/AIGC_graph/{filename}'
                        
                        
                        # 更新之前保存的用户消息，添加AI回答（如果之前已保存）
                        # 将用户上传的图片URL列表转换为JSON字符串存储
                        image_from_users_url_json = json.dumps(user_uploaded_image_urls, ensure_ascii=False) if user_uploaded_image_urls else None
                        if session_id and message_id:
                            try:
                                # 使用save_aigc_message_to_db更新消息
                                save_aigc_message_to_db(
                                    user_id=user_id,
                                    session_id=session_id,
                                    user_message=user_original_query if user_original_query else "（根据上传的图片自动生成）",
                                    ai_message=f'图片生成成功！\n提示词：{final_prompt}',
                                    model='image',
                                    image_url=image_url,
                                    image_from_users_url=image_from_users_url_json,
                                    message_id=message_id,  # 使用message_id更新现有消息
                                    db_config=db_config
                                )
                                # 记录图片AIGC使用日志
                                UserLogging.log_aigc_image(user_id, final_prompt)
                            except Exception as save_error:
                                import traceback
                                traceback.print_exc()
                        
                        
                        # 非流式输出（普通模式）
                        return jsonify({
                            'answer': f'图片生成成功！\n提示词：{final_prompt}',
                            'image_path': image_url,
                            'model': 'image'  # 明确返回model类型，用于前端显示AI昵称
                        })
                else:
                    # 图片生成失败，尝试使用RAG系统生成文字回答作为降级方案
                    text_answer = ""
                    try:
                        if rag_system:
                            # 使用RAG系统生成文字回答
                            # 优先使用story_prompt（已在try块外定义），其次使用user_original_query
                            fallback_query = story_prompt if story_prompt else (user_original_query if user_original_query else "请创作一个传统文化故事")
                            rag_result = rag_system.ask(
                                query=fallback_query,
                                image_paths=None,
                                use_history=False
                            )
                            text_answer = rag_result.get('answer', '')
                            if not text_answer:
                                text_answer = "抱歉，图片生成失败，文字回答生成也未能完成。可能的原因：1. 提示词包含敏感内容；2. API服务暂时不可用；3. 网络连接问题。"
                        else:
                            text_answer = "抱歉，图片生成失败，且RAG系统未初始化。可能的原因：1. 提示词包含敏感内容；2. API服务暂时不可用；3. 网络连接问题。"
                    except Exception as rag_error:
                        import traceback
                        traceback.print_exc()
                        text_answer = "抱歉，图片生成失败，文字回答生成也出现错误。可能的原因：1. 提示词包含敏感内容；2. API服务暂时不可用；3. 网络连接问题。"
                    
                    # 更新消息，使用文字回答和默认图片
                    default_image_url = '/AIGC_graph/default.jpg'
                    image_from_users_url_json = json.dumps(user_uploaded_image_urls, ensure_ascii=False) if user_uploaded_image_urls else None
                    if session_id and message_id:
                        try:
                            save_aigc_message_to_db(
                                user_id=user_id,
                                session_id=session_id,
                                user_message=user_original_query if user_original_query else "（根据上传的图片自动生成）",
                                ai_message=text_answer,
                                model='image',  # 保持为image模式，但内容是文字回答
                                image_url=default_image_url,
                                image_from_users_url=image_from_users_url_json,
                                message_id=message_id,  # 使用message_id更新现有消息
                                db_config=db_config
                            )
                        except Exception as save_error:
                            pass
                    
                    # 返回文字回答和默认图片
                    return jsonify({
                        'answer': text_answer,
                        'image_path': default_image_url,  # 提供默认图片
                        'model': 'image'  # 保持为image模式
                    }), 200
                    
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                error_msg = str(e)
                
                # 图片生成异常，尝试使用RAG系统生成文字回答作为降级方案
                text_answer = ""
                try:
                    if rag_system:
                        # 使用RAG系统生成文字回答
                        # 优先使用user_original_query，其次使用story_prompt（已在try块外定义），最后使用默认提示
                        fallback_query = user_original_query if user_original_query else (
                            story_prompt if story_prompt else "请创作一个传统文化故事"
                        )
                        rag_result = rag_system.ask(
                            query=fallback_query,
                            image_paths=None,
                            use_history=False
                        )
                        text_answer = rag_result.get('answer', '')
                        if not text_answer:
                            text_answer = f"抱歉，图片生成失败：{error_msg}。已尝试生成文字回答但未能完成。"
                    else:
                        text_answer = f"抱歉，图片生成失败：{error_msg}。RAG系统未初始化，无法生成文字回答。"
                except Exception as rag_error:
                    text_answer = f"抱歉，图片生成失败：{error_msg}。文字回答生成也出现错误。"
                
                # 如果发生异常，尝试更新消息（如果message_id存在）
                if session_id and message_id:
                    try:
                        default_image_url = '/AIGC_graph/default.jpg'
                        user_original_query_local = user_original_query if user_original_query else "（根据上传的图片自动生成）"
                        image_from_users_url_json = json.dumps(user_uploaded_image_urls, ensure_ascii=False) if user_uploaded_image_urls else None
                        save_aigc_message_to_db(
                            user_id=user_id,
                            session_id=session_id,
                            user_message=user_original_query_local,
                            ai_message=text_answer,
                            model='image',
                            image_url=default_image_url,
                            image_from_users_url=image_from_users_url_json,
                            message_id=message_id,
                            db_config=db_config
                        )
                    except Exception as save_error:
                        pass
                
                # 返回文字回答和默认图片
                return jsonify({
                    'answer': text_answer,
                    'image_path': '/AIGC_graph/default.jpg',  # 提供默认图片
                    'model': 'image'  # 保持为image模式
                }), 200
        else:
            return jsonify({'error': f'不支持的模式：{mode}'}), 400
            
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'answer': f'处理失败：{str(e)}\n\n请检查后端控制台的详细错误信息'
        }), 500
    finally:
        # 清理临时文件
        try:
            # 检查image_paths是否在作用域内
            if 'image_paths' in locals():
                import shutil
                for path in image_paths:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except:
                            pass
        except NameError:
            # image_paths未定义，跳过清理
            pass
        except Exception:
            # 其他错误，忽略
            pass

@app.route('/api/aigc/extract-title', methods=['POST'])
def extract_title():
    """提取对话主题 - 调用阿里云API生成"""
    try:
        data = request.json
        conversation = data.get('conversation', '')
        user_id = data.get('user_id')  # 从请求中获取用户ID
        
        
        if not conversation:
            return jsonify({'title': '新对话'}), 200
        
        # 获取用户的RAG系统（如果没有user_id，使用第一个可用的系统）
        rag_system = None
        if user_id:
            try:
                user_id = int(user_id)
                user_db_config = get_auth_system().get_user_db_config(user_id)
                if user_db_config:
                    rag_system = get_or_create_rag_system(user_id, user_db_config['db_config'])
            except:
                pass
        
        # 如果没有用户系统，尝试使用第一个可用的系统
        if not rag_system and rag_systems:
            rag_system = list(rag_systems.values())[0]
        
        # 使用AI提取主题（调用阿里云API）
        if rag_system and hasattr(rag_system, 'model') and rag_system.model:
            try:
                prompt = f"""请根据以下对话内容，提取一个不超过20字的主题标题。

对话内容：
{conversation}

要求：
1. 标题要简洁明了，准确概括对话的核心内容
2. 标题长度不超过20字
3. 只返回标题文本，不要包含"标题："、"标题:"等前缀，不要有其他解释

标题："""
                
                # 直接使用RAG系统的模型调用方法
                response = rag_system._call_model(prompt)
                
                title = response.strip()
                
                # 清理标题：移除可能的前缀和多余内容
                title = title.replace('标题：', '').replace('标题:', '').strip()
                # 移除可能的引号
                title = title.strip('"').strip("'").strip()
                # 如果包含换行，只取第一行
                if '\n' in title:
                    title = title.split('\n')[0].strip()
                # 移除可能的JSON格式标记
                if title.startswith('{') or title.startswith('['):
                    try:
                        parsed = json.loads(title)
                        if isinstance(parsed, dict):
                            title = parsed.get('title', title)
                        elif isinstance(parsed, str):
                            title = parsed
                    except:
                        pass
                
                # 确保不超过20字
                if len(title) > 20:
                    title = title[:20]
                
                # 如果标题为空或太短，使用降级方案
                if not title or len(title) < 2:
                    raise ValueError("标题太短或为空")
                
                return jsonify({'title': title})
                
            except Exception as e:
                import traceback
                # 继续执行降级方案
        
        # 降级方案：从对话中提取关键词
        import re
        lines = conversation.split('\n')
        for line in lines:
            if '用户：' in line or line.startswith('用户：'):
                text = line.replace('用户：', '').replace('用户:', '').strip()
                if text:
                    # 清理文本（移除标点符号和多余空格）
                    text = re.sub(r'[，。！？、；：\s]+', ' ', text).strip()
                    title = text[:20] if len(text) > 20 else text
                    if title:
                        return jsonify({'title': title})
        
        return jsonify({'title': '新对话'})
        
    except Exception as e:
        import traceback
        return jsonify({'title': '新对话'})

@app.route('/api/upload', methods=['POST'])
def upload_resource():
    """用户上传资源接口"""
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': '请选择要上传的文件'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': '请选择有效的文件'
            }), 400
        
        # 获取用户ID
        user_id = request.form.get('userId') or request.headers.get('X-User-Id')
        if not user_id:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({
                'success': False,
                'message': '无效的用户ID'
            }), 401
        
        # 获取资源类型
        resource_type = request.form.get('resourceType', '')
        if not resource_type:
            return jsonify({
                'success': False,
                'message': '请指定资源类型'
            }), 400
        
        # 验证资源类型：只允许"文本"或"图像"
        if resource_type not in ['文本', '图像']:
            return jsonify({
                'success': False,
                'message': f'不支持的资源类型：{resource_type}。仅支持"文本"或"图像"'
            }), 400
        
        # 如果是文件上传模式，验证文件类型
        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                file_name = file.filename
                file_extension = file_name.split('.')[-1].lower() if '.' in file_name else ''
                
                # 图片文件扩展名（只支持jpg和png）
                image_extensions = ['jpg', 'jpeg', 'png']
                # 文本文件扩展名（只支持doc, docx, pdf）
                text_extensions = ['doc', 'docx', 'pdf']
                
                is_image = file_extension in image_extensions
                is_text = file_extension in text_extensions
                
                if not is_image and not is_text:
                    return jsonify({
                        'success': False,
                        'message': f'不支持的文件类型：{file_extension}。文本类型只支持Word文档（.doc, .docx）或PDF（.pdf），图像类型只支持JPG（.jpg）或PNG（.png）'
                    }), 400
                
                # 验证资源类型与文件类型是否匹配
                if resource_type == '图像' and not is_image:
                    return jsonify({
                        'success': False,
                        'message': f'资源类型为"图像"，但文件类型（{file_extension}）不是支持的图片格式（只支持.jpg和.png）'
                    }), 400
                
                if resource_type == '文本' and not is_text:
                    return jsonify({
                        'success': False,
                        'message': f'资源类型为"文本"，但文件类型（{file_extension}）不是支持的文本格式（只支持.doc, .docx, .pdf）'
                    }), 400
        
        # 获取用户的数据库配置
        user_db_config = get_auth_system().get_user_db_config(user_id)
        if not user_db_config:
            return jsonify({
                'success': False,
                'message': '用户不存在'
            }), 401
        
        db_config = user_db_config['db_config']
        
        # 创建上传器并处理上传
        uploader = ResourceUploader(user_id=user_id, db_config=db_config)
        
        # 获取用户标注数据（如果提供）
        user_annotation = None
        annotation_json = request.form.get('annotation')
        if annotation_json:
            try:
                user_annotation = json.loads(annotation_json)
            except json.JSONDecodeError:
                return jsonify({
                    'success': False,
                    'message': '标注数据格式错误'
                }), 400
        
        # 检查是文件上传还是文本直接输入
        text_content = request.form.get('textContent', '').strip()
        
        if text_content:
            # 文本直接输入模式
            if resource_type != '文本':
                return jsonify({
                    'success': False,
                    'message': '文本直接输入只支持文本类型资源'
                }), 400
            
            result = uploader.upload_resource(
                user_id=user_id,
                text_content=text_content,
                resource_type=resource_type,
                user_annotation=user_annotation
            )
        else:
            # 文件上传模式
            if 'file' not in request.files:
                return jsonify({
                    'success': False,
                    'message': '请选择要上传的文件或输入文本内容'
                }), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({
                    'success': False,
                    'message': '请选择有效的文件'
                }), 400
            
            # 读取文件数据
            file_data = file.read()
            file_name = file.filename
            
            # 调用上传方法
            result = uploader.upload_resource(
                user_id=user_id,
                file_data=file_data,
                file_name=file_name,
                resource_type=resource_type,
                user_annotation=user_annotation
            )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': f'上传失败: {str(e)}'
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    # 测试数据库连接
    db_status = 'unknown'
    try:
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if conn:
            conn.close()
            db_status = 'connected'
        else:
            db_status = 'failed'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'ok',
        'rag_systems_count': len(rag_systems),
        'image_aigc_systems_count': len(image_aigc_systems),
        'database_status': db_status,
        'search_rag_initialized': search_rag_system is not None
    })

@app.route('/api/home/resources', methods=['GET'])
def get_home_resources():
    """获取首页资源列表（从crawled_images和cultural_entities表）"""
    try:
        import re
        
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 8))
        
        # 获取数据库连接（使用默认配置）
        from db_connection import get_user_db_connection
        conn = None
        try:
            conn = get_user_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': '数据库连接失败，请检查数据库配置和连接状态'}), 500
        except Exception as db_error:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'数据库连接异常：{str(db_error)}'}), 500
        
        try:
            with conn.cursor() as cursor:
                resources = []
                
                # 1. 从crawled_images表获取图片资源，按resource_id或entity_id分组
                # 优先选择有resource_id和entity_id的图片，每个资源只取第一张图片（优先非default图片）
                cursor.execute("""
                    SELECT id, file_name, storage_path, tags, dimensions, crawl_time, 
                           resource_id, entity_id, festival_name
                    FROM crawled_images
                    WHERE resource_id IS NOT NULL AND entity_id IS NOT NULL
                    ORDER BY 
                        CASE WHEN file_name != 'default.jpg' THEN 0 ELSE 1 END,
                        crawl_time DESC
                """)
                
                all_images = cursor.fetchall()
                
                # 按resource_id分组，每个资源只保留第一张图片（优先非default图片）
                resource_images = {}  # {resource_id: best_image}
                
                for img in all_images:
                    resource_id = img.get('resource_id')
                    if not resource_id:
                        continue
                    
                    # 如果这个资源还没有图片，或者当前图片不是default且已有的是default，则替换
                    if resource_id not in resource_images:
                        resource_images[resource_id] = img
                    else:
                        existing = resource_images[resource_id]
                        # 如果已有的是default，当前不是default，则替换
                        if existing.get('file_name') == 'default.jpg' and img.get('file_name') != 'default.jpg':
                            resource_images[resource_id] = img
                
                # 转换为列表并按时间排序
                festival_list = list(resource_images.values())
                festival_list.sort(key=lambda x: x.get('crawl_time', ''), reverse=True)
                
                # 分页处理
                total_count = len(festival_list)
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                paginated_images = festival_list[start_idx:end_idx]
                
                
                # 构建资源列表
                for img in paginated_images:
                    # 优先通过entity_id关联查询cultural_entities表（最准确的方式）
                    entity_id = img.get('entity_id')
                    resource_id = img.get('resource_id')
                    festival_name = img.get('festival_name')  # 从数据库字段直接获取
                    
                    entity_name = ""
                    description = ""
                    
                    # 1. 优先通过entity_id直接关联查询（最准确）
                    if entity_id:
                        cursor.execute("""
                            SELECT entity_name, description, entity_type, cultural_value
                            FROM cultural_entities
                            WHERE id = %s
                            LIMIT 1
                        """, (entity_id,))
                        entity_info = cursor.fetchone()
                        if entity_info:
                            entity_name = entity_info.get('entity_name', '') or ''
                            description = entity_info.get('description', '') or ''
                            if description:
                                description = description[:200]  # 首页显示较短描述
                    
                    # 2. 如果没有entity_id，尝试通过resource_id查询cultural_resources，再关联cultural_entities
                    if not entity_name and resource_id:
                        cursor.execute("""
                            SELECT cr.id, cr.title, cr.content_feature_data
                            FROM cultural_resources cr
                            WHERE cr.id = %s
                            LIMIT 1
                        """, (resource_id,))
                        resource_info = cursor.fetchone()
                        if resource_info:
                            # 从content_feature_data中提取信息
                            try:
                                content_data = json.loads(resource_info.get('content_feature_data', '{}') or '{}')
                                if isinstance(content_data, dict):
                                    title = content_data.get('title', '')
                                    if title:
                                        entity_name = title
                                    # 从meta中获取festival_name
                                    meta = content_data.get('meta', {})
                                    if meta and not festival_name:
                                        festival_name = meta.get('festival_names', [None])[0] if meta.get('festival_names') else None
                            except:
                                pass
                            
                            # 通过resource_id查找关联的entity_id
                            cursor.execute("""
                                SELECT ci.entity_id
                                FROM crawled_images ci
                                WHERE ci.resource_id = %s AND ci.entity_id IS NOT NULL
                                LIMIT 1
                            """, (resource_id,))
                            entity_id_result = cursor.fetchone()
                            if entity_id_result and entity_id_result.get('entity_id'):
                                cursor.execute("""
                                    SELECT entity_name, description
                                    FROM cultural_entities
                                    WHERE id = %s
                                    LIMIT 1
                                """, (entity_id_result['entity_id'],))
                                entity_info = cursor.fetchone()
                                if entity_info:
                                    entity_name = entity_info.get('entity_name', '') or entity_name or ''
                                    description = entity_info.get('description', '') or description or ''
                                    if description:
                                        description = description[:200]
                    
                    # 3. 如果还是没有，从tags提取节日名称和实体名称
                    if not entity_name and img.get('tags'):
                        try:
                            tags_data = json.loads(img['tags']) if isinstance(img['tags'], str) else img['tags']
                            if isinstance(tags_data, list) and tags_data:
                                for tag in tags_data:
                                    if isinstance(tag, str):
                                        match = re.search(r'([\u4e00-\u9fa5]+)', tag)
                                        if match:
                                            festival_name = festival_name or match.group(1)
                                            if not entity_name:
                                                entity_name = match.group(1)
                                            break
                        except Exception as e:
                            pass
                    
                    # 4. 如果还是没有，使用festival_name字段
                    if not entity_name:
                        entity_name = festival_name or ''
                    
                    # 构建图片URL
                    storage_path = img.get('storage_path', '')
                    file_name = img.get('file_name', '')
                    
                    # 处理default.jpg的特殊情况
                    if storage_path and 'default.jpg' in storage_path:
                        # 如果是default.jpg，直接使用/default.jpg路径
                        image_url = "/default.jpg"
                    elif storage_path:
                        # 如果是crawled_images路径，使用API路径
                        if 'crawled_images' in storage_path:
                            actual_file = os.path.basename(storage_path)
                            image_url = f"/api/images/crawled/{actual_file}"
                        else:
                            # 其他路径，直接使用
                            image_url = storage_path if storage_path.startswith('/') else f"/{storage_path}"
                    elif file_name and file_name != 'default.jpg':
                        # 如果有文件名且不是default.jpg，使用API路径
                        image_url = f"/api/images/crawled/{file_name}"
                    else:
                        # 默认使用default图片
                        image_url = "/default.jpg"
                    
                    # 如果还是没有实体名称，使用文件名（去掉扩展名）
                    if not entity_name and file_name and file_name != 'default.jpg':
                        entity_name = os.path.splitext(file_name)[0]
                    
                    resources.append({
                        'id': f"img_{img['id']}",
                        'type': 'image',
                        'image_url': image_url,
                        'entity_name': entity_name or '未命名资源',
                        'description': description or '暂无简介',
                        'festival_name': festival_name or entity_name,  # 添加节日名称字段
                        'source': 'crawled_images'
                    })
                
                # 2. 从cultural_entities表获取实体资源（如果图片资源不足）
                # 计算还需要多少条数据
                remaining = page_size - len(resources)
                if remaining > 0:
                    # 计算偏移量（考虑已经获取的节日图片数量）
                    offset = max(0, (page - 1) * page_size - len(paginated_images))
                    cursor.execute("""
                        SELECT ce.id, ce.entity_name, ce.description, ce.entity_type
                        FROM cultural_entities ce
                        ORDER BY ce.id DESC
                        LIMIT %s OFFSET %s
                    """, (remaining, offset))
                    
                    entities = cursor.fetchall()
                    for entity in entities:
                        # 尝试从关联的资源中查找图片
                        image_url = None
                        # 可以后续扩展：从related_images_url字段获取图片
                        if entity.get('related_images_url'):
                            try:
                                related_images = json.loads(entity['related_images_url']) if isinstance(entity['related_images_url'], str) else entity['related_images_url']
                                if isinstance(related_images, list) and related_images:
                                    image_url = related_images[0]
                            except:
                                pass
                        
                        # 如果没有图片，使用default图片
                        if not image_url:
                            image_url = "/default.jpg"
                        
                        resources.append({
                            'id': f"entity_{entity['id']}",
                            'type': 'entity',
                            'image_url': image_url,
                            'entity_name': entity.get('entity_name') or '未命名实体',
                            'description': (entity.get('description') or '')[:200] or '暂无简介',
                            'entity_type': entity.get('entity_type'),
                            'festival_name': entity.get('entity_name'),  # 添加节日名称字段
                            'source': 'cultural_entities'
                        })
                
                # 获取总数（按节日分组后的数量）
                total = total_count
                
                # 3. 从AIGC_cultural_resources表获取AIGC文字资源（如果资源不足）
                remaining_after_entities = page_size - len(resources)
                if remaining_after_entities > 0:
                    # 计算偏移量
                    offset_aigc = max(0, (page - 1) * page_size - len(paginated_images) - len(entities))
                    cursor.execute("""
                        SELECT id, title, resource_type, content_feature_data, source_from
                        FROM AIGC_cultural_resources
                        WHERE resource_type = '文本'
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (remaining_after_entities, offset_aigc))
                    
                    aigc_resources = cursor.fetchall()
                    for aigc in aigc_resources:
                        # 解析content_feature_data获取文本内容
                        entity_name = aigc.get('title', '')
                        description = ''
                        try:
                            content_data = json.loads(aigc.get('content_feature_data', '{}') or '{}')
                            if isinstance(content_data, dict):
                                description = content_data.get('text', '')[:200] or ''
                                if not entity_name:
                                    entity_name = content_data.get('title', '')
                        except:
                            pass
                        
                        # AIGC文字资源统一使用 AIGC_graph/default.jpg
                        image_url = "/AIGC_graph/default.jpg"
                        
                        resources.append({
                            'id': f"aigc_{aigc['id']}",
                            'type': 'aigc_text',
                            'image_url': image_url,
                            'entity_name': entity_name or 'AIGC生成资源',
                            'description': description or '暂无简介',
                            'festival_name': entity_name,
                            'source': aigc.get('source_from', 'AIGC生成')
                        })
                
                # 获取总数（按节日分组后的数量）
                total = total_count
                
                # 如果节日资源不足，补充统计cultural_entities和AIGC资源
                if total < page_size:
                    cursor.execute("SELECT COUNT(*) as total FROM cultural_entities")
                    total_entities_result = cursor.fetchone()
                    total_entities = total_entities_result['total'] if total_entities_result else 0
                    
                    cursor.execute("SELECT COUNT(*) as total FROM AIGC_cultural_resources WHERE resource_type = '文本'")
                    total_aigc_result = cursor.fetchone()
                    total_aigc = total_aigc_result['total'] if total_aigc_result else 0
                    
                    total = max(total, total_entities + total_aigc)
                
                return jsonify({
                    'success': True,
                    'resources': resources,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size
                    }
                })
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            'success': False,
            'message': f'获取资源失败：{str(e)}',
            'error_type': type(e).__name__
        }), 500


@app.route('/api/resource/detail', methods=['GET'])
def get_resource_detail():
    """获取资源详情（某个节日的所有图片）
    支持两种查询方式：
    1. festival_name参数：通过节日名称查询
    2. id + table参数：通过资源ID和表名查询
    """
    festival_name = request.args.get('festival_name')
    resource_id_param = request.args.get('id', type=int)
    table_param = request.args.get('table', '')
    
    # 如果使用id+table方式，需要转换为festival_name
    if resource_id_param and table_param:
        # 根据table类型查询festival_name
        from db_connection import get_user_db_connection
        from pymysql.cursors import DictCursor
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor(DictCursor) as cursor:
                if table_param == 'cultural_entities':
                    cursor.execute("""
                        SELECT entity_name FROM cultural_entities WHERE id = %s
                    """, (resource_id_param,))
                    result = cursor.fetchone()
                    if result:
                        festival_name = result.get('entity_name')
                elif table_param == 'cultural_resources':
                    cursor.execute("""
                        SELECT title FROM cultural_resources WHERE id = %s
                    """, (resource_id_param,))
                    result = cursor.fetchone()
                    if result:
                        festival_name = result.get('title')
                elif table_param == 'AIGC_cultural_entities':
                    cursor.execute("""
                        SELECT entity_name FROM AIGC_cultural_entities WHERE id = %s
                    """, (resource_id_param,))
                    result = cursor.fetchone()
                    if result:
                        festival_name = result.get('entity_name')
                elif table_param == 'AIGC_cultural_resources':
                    cursor.execute("""
                        SELECT title FROM AIGC_cultural_resources WHERE id = %s
                    """, (resource_id_param,))
                    result = cursor.fetchone()
                    if result:
                        festival_name = result.get('title')
        finally:
            conn.close()
    
    if not festival_name:
        return jsonify({'success': False, 'message': '缺少festival_name参数或无法通过id+table获取festival_name'}), 400
    
    try:
        import re
        
        # 获取数据库连接
        from db_connection import get_user_db_connection
        conn = None
        try:
            conn = get_user_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        except Exception as db_error:
            return jsonify({'success': False, 'message': f'数据库连接异常：{str(db_error)}'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 优先通过entity_id关联查询cultural_entities表获取完整信息
                entity_name = festival_name
                description = ""
                entity_id = None
                
                # 1. 先尝试通过entity_name精确匹配或模糊匹配查找实体
                cursor.execute("""
                    SELECT id, entity_name, description, entity_type, cultural_value
                    FROM cultural_entities
                    WHERE entity_name = %s OR entity_name LIKE %s
                    ORDER BY CASE WHEN entity_name = %s THEN 1 ELSE 2 END
                    LIMIT 1
                """, (festival_name, f'%{festival_name}%', festival_name))
                entity_info = cursor.fetchone()
                
                if entity_info:
                    entity_id = entity_info.get('id')
                    entity_name = entity_info.get('entity_name', festival_name)
                    description = entity_info.get('description', '') or ''
                    # 不限制描述长度，返回完整描述
                
                # 2. 查找该节日的所有图片（优先通过entity_id，如果没有则通过tags匹配）
                if entity_id:
                    # 通过entity_id关联查询（最准确）
                    cursor.execute("""
                        SELECT id, file_name, storage_path, tags, dimensions, crawl_time, resource_id, entity_id
                        FROM crawled_images
                        WHERE entity_id = %s
                        ORDER BY 
                            CASE 
                                WHEN file_name != 'default.jpg' THEN 0
                                ELSE 1
                            END,
                            CASE 
                                WHEN file_name REGEXP '^[0-9]+\\.[a-zA-Z]+$' THEN 1
                                WHEN file_name REGEXP '^[0-9]+-[0-9]+\\.[a-zA-Z]+$' THEN 2
                                ELSE 3
                            END,
                            CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(file_name, '-', 1), '.', 1) AS UNSIGNED),
                            CASE 
                                WHEN file_name REGEXP '^[0-9]+-[0-9]+\\.[a-zA-Z]+$' 
                                THEN CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(file_name, '-', -1), '.', 1) AS UNSIGNED)
                                ELSE 0
                            END
                    """, (entity_id,))
                else:
                    # 通过tags字段匹配节日名称（备用方案）
                    cursor.execute("""
                        SELECT id, file_name, storage_path, tags, dimensions, crawl_time, resource_id, entity_id
                        FROM crawled_images
                        WHERE tags LIKE %s OR festival_name = %s
                        ORDER BY 
                            CASE 
                                WHEN file_name != 'default.jpg' THEN 0
                                ELSE 1
                            END,
                            CASE 
                                WHEN file_name REGEXP '^[0-9]+\\.[a-zA-Z]+$' THEN 1
                                WHEN file_name REGEXP '^[0-9]+-[0-9]+\\.[a-zA-Z]+$' THEN 2
                                ELSE 3
                            END,
                            CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(file_name, '-', 1), '.', 1) AS UNSIGNED),
                            CASE 
                                WHEN file_name REGEXP '^[0-9]+-[0-9]+\\.[a-zA-Z]+$' 
                                THEN CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(file_name, '-', -1), '.', 1) AS UNSIGNED)
                                ELSE 0
                            END
                    """, (f'%{festival_name}%', festival_name))
                
                images = cursor.fetchall()
                
                # 3. 如果通过图片找到了entity_id，但没有描述，再次查询
                if not description and images:
                    for img in images:
                        img_entity_id = img.get('entity_id')
                        if img_entity_id:
                            cursor.execute("""
                                SELECT entity_name, description
                                FROM cultural_entities
                                WHERE id = %s
                                LIMIT 1
                            """, (img_entity_id,))
                            entity_info = cursor.fetchone()
                            if entity_info:
                                entity_name = entity_info.get('entity_name', entity_name)
                                description = entity_info.get('description', '') or description
                                break
                
                # 4. 如果还是没有描述，尝试从resource_id关联查询
                if not description and images:
                    for img in images:
                        resource_id = img.get('resource_id')
                        if resource_id:
                            cursor.execute("""
                                SELECT cr.content_feature_data
                                FROM cultural_resources cr
                                WHERE cr.id = %s
                                LIMIT 1
                            """, (resource_id,))
                            resource_info = cursor.fetchone()
                            if resource_info and resource_info.get('content_feature_data'):
                                try:
                                    content_data = json.loads(resource_info['content_feature_data'] or '{}')
                                    if isinstance(content_data, dict):
                                        description = content_data.get('text', '') or description
                                        if not entity_name or entity_name == festival_name:
                                            entity_name = content_data.get('title', entity_name)
                                except:
                                    pass
                            if description:
                                break
                
                # 5. 即使没有图片，也返回实体信息
                if not images:
                    if entity_info:
                        # 如果没有图片，使用default图片
                        default_image = {
                            'id': 0,
                            'file_name': 'default.jpg',
                            'image_url': '/default.jpg',
                            'dimensions': None,
                            'crawl_time': None
                        }
                        return jsonify({
                            'success': True,
                            'festival_name': festival_name,
                            'entity_name': entity_name,
                            'description': description or '暂无简介',
                            'images': [default_image],
                            'total_images': 1
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'message': f'未找到节日"{festival_name}"的资源'
                        }), 404
                
                # 构建图片列表
                image_list = []
                
                for img in images:
                    # 构建图片URL
                    storage_path = img.get('storage_path')
                    file_name = img.get('file_name')
                    
                    if storage_path:
                        # 如果storage_path包含路径，提取文件名
                        actual_file = os.path.basename(storage_path) if os.path.sep in storage_path else storage_path
                    elif file_name:
                        actual_file = file_name
                    else:
                        actual_file = None
                    
                    # 构建图片URL（直接使用API路径，不检查文件是否存在，让API路由处理）
                    if actual_file:
                        # 直接使用API路径，由serve_crawled_image函数处理文件不存在的情况
                        image_url = f"/api/images/crawled/{actual_file}"
                    else:
                        # 如果没有文件名，使用default图片
                        image_url = "/default.jpg"
                    
                    # 如果还没有描述，尝试从tags提取（只提取一次）
                    if not description and img.get('tags'):
                        try:
                            tags_data = json.loads(img['tags']) if isinstance(img['tags'], str) else img['tags']
                            if isinstance(tags_data, list) and tags_data:
                                for tag in tags_data:
                                    if isinstance(tag, str) and festival_name in tag:
                                        # 提取更完整的描述
                                        desc_match = re.search(r'([\u4e00-\u9fa5]+[^\u4e00-\u9fa5]*)', tag)
                                        if desc_match:
                                            description = desc_match.group(1).strip()[:500]
                                        else:
                                            description = tag[:500]
                                        break
                        except Exception as e:
                            pass
                    
                    image_list.append({
                        'id': img['id'],
                        'file_name': file_name,
                        'image_url': image_url,
                        'dimensions': img.get('dimensions'),
                        'crawl_time': str(img.get('crawl_time', '')) if img.get('crawl_time') else None
                    })
                
                # 获取resource_id（如果通过id和table参数查询）
                resource_id = None
                resource_id_param = request.args.get('id', type=int)
                table_param = request.args.get('table', '')
                
                if resource_id_param and table_param:
                    # 根据table参数确定resource_id
                    if table_param == 'cultural_resources':
                        resource_id = resource_id_param
                    elif table_param == 'cultural_entities':
                        # 从cultural_entities获取关联的resource_id
                        cursor.execute("""
                            SELECT resource_id FROM crawled_images 
                            WHERE entity_id = %s 
                            LIMIT 1
                        """, (resource_id_param,))
                        entity_result = cursor.fetchone()
                        if entity_result and entity_result.get('resource_id'):
                            resource_id = entity_result['resource_id']
                    # 其他表类型可以根据需要扩展
                
                return jsonify({
                    'success': True,
                    'festival_name': festival_name,
                    'entity_name': entity_name,
                    'description': description or '暂无简介',
                    'images': image_list,
                    'total_images': len(image_list),
                    'resource_id': resource_id  # 返回resource_id用于评论功能
                })
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取资源详情失败：{str(e)}'}), 500

@app.route('/api/search', methods=['GET'])
def search_resources():
    """全文检索接口：关键词直接与数据库匹配，不使用AI分析"""
    keyword = request.args.get('q', '').strip()
    user_id = request.args.get('user_id', None)

    if not keyword:
        return jsonify({"code": 400, "msg": "请输入搜索关键词", "data": []})

    # 获取数据库连接
    from db_connection import get_default_db_connection
    conn = get_default_db_connection()
    if not conn:
        return jsonify({"code": 500, "msg": "数据库连接失败", "data": []})

    try:
        from pymysql.cursors import DictCursor
        with conn.cursor(DictCursor) as cursor:
            # ------------------------
            # 直接关键词匹配查询（不使用AI分析）
            # ------------------------

            # 构建LIKE查询条件
            like_pattern = f'%{keyword}%'

            # 检查是否支持全文索引
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM information_schema.STATISTICS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'cultural_entities' 
                AND INDEX_NAME = 'idx_ce_search'
            """)
            has_fulltext = cursor.fetchone().get('cnt', 0) > 0
            
            # 构建查询：优先使用全文索引，否则使用LIKE
            if has_fulltext:
                # 使用全文索引查询（MATCH AGAINST）
                sql = """
                    (SELECT
                        ce.id,
                        ce.entity_name as title,
                        ce.description,
                        COALESCE(ci.storage_path, ce.related_images_url) as image_url,
                        ce.source,
                        '传统实体' as type_tag,
                        CASE
                            WHEN ce.entity_name LIKE %s THEN 2.0  -- 实体名完全匹配权重最高
                            WHEN MATCH(ce.entity_name, ce.description) AGAINST(%s IN NATURAL LANGUAGE MODE) THEN 1.8  -- 全文索引匹配权重高
                            WHEN ce.entity_name LIKE %s THEN 1.5  -- 实体名部分匹配权重较高
                            WHEN ce.description LIKE %s THEN 1.0  -- 描述匹配权重中等
                            ELSE 0.5
                        END as relevance_score,
                        1 as type_weight  -- 传统实体权重更高
                    FROM cultural_entities ce
                    LEFT JOIN crawled_images ci ON ce.id = ci.entity_id
                    WHERE MATCH(ce.entity_name, ce.description) AGAINST(%s IN NATURAL LANGUAGE MODE)
                       OR ce.entity_name LIKE %s 
                       OR ce.description LIKE %s
                    GROUP BY ce.id, ce.entity_name, ce.description, ce.source, ci.storage_path, ce.related_images_url)

                    UNION ALL

                    (SELECT
                        ace.id,
                        ace.entity_name as title,
                        ace.description,
                        ace.related_images_url as image_url,
                        'AIGC生成' as source,
                        'AI实体' as type_tag,
                        CASE
                            WHEN ace.entity_name LIKE %s THEN 1.6  -- AI实体名完全匹配权重较高
                            WHEN MATCH(ace.entity_name, ace.description) AGAINST(%s IN NATURAL LANGUAGE MODE) THEN 1.4  -- 全文索引匹配权重较高
                            WHEN ace.entity_name LIKE %s THEN 1.2  -- AI实体名部分匹配权重中等
                            WHEN ace.description LIKE %s THEN 0.8  -- AI描述匹配权重较低
                            ELSE 0.4
                        END as relevance_score,
                        0.7 as type_weight  -- AI生成实体权重较低
                    FROM AIGC_cultural_entities ace
                    WHERE MATCH(ace.entity_name, ace.description) AGAINST(%s IN NATURAL LANGUAGE MODE)
                       OR ace.entity_name LIKE %s 
                       OR ace.description LIKE %s)
                    
                    -- 不限制返回条数，移除所有LIMIT子句
                """
                # 准备查询参数（全文索引需要单独的关键词参数）
                exact_match = keyword
                partial_match = like_pattern
                cursor.execute(sql, (
                    exact_match, keyword, partial_match, partial_match, keyword, partial_match, partial_match,  # 传统实体
                    exact_match, keyword, partial_match, partial_match, keyword, partial_match, partial_match   # AI实体
                ))
            else:
                # 使用LIKE查询（不支持全文索引时）
                sql = """
                    (SELECT
                        ce.id,
                        ce.entity_name as title,
                        ce.description,
                        COALESCE(ci.storage_path, ce.related_images_url) as image_url,
                        ce.source,
                        '传统实体' as type_tag,
                        CASE
                            WHEN ce.entity_name LIKE %s THEN 2.0  -- 实体名完全匹配权重最高
                            WHEN ce.entity_name LIKE %s THEN 1.5  -- 实体名部分匹配权重较高
                            WHEN ce.description LIKE %s THEN 1.0  -- 描述匹配权重中等
                            ELSE 0.5
                        END as relevance_score,
                        1 as type_weight  -- 传统实体权重更高
                    FROM cultural_entities ce
                    LEFT JOIN crawled_images ci ON ce.id = ci.entity_id
                    WHERE ce.entity_name LIKE %s OR ce.description LIKE %s
                    GROUP BY ce.id, ce.entity_name, ce.description, ce.source, ci.storage_path, ce.related_images_url)

                    UNION ALL

                    (SELECT
                        ace.id,
                        ace.entity_name as title,
                        ace.description,
                        ace.related_images_url as image_url,
                        'AIGC生成' as source,
                        'AI实体' as type_tag,
                        CASE
                            WHEN ace.entity_name LIKE %s THEN 1.6  -- AI实体名完全匹配权重较高
                            WHEN ace.entity_name LIKE %s THEN 1.2  -- AI实体名部分匹配权重中等
                            WHEN ace.description LIKE %s THEN 0.8  -- AI描述匹配权重较低
                            ELSE 0.4
                        END as relevance_score,
                        0.7 as type_weight  -- AI生成实体权重较低
                    FROM AIGC_cultural_entities ace
                    WHERE ace.entity_name LIKE %s OR ace.description LIKE %s)
                    
                    -- 不限制返回条数，移除所有LIMIT子句
                """
                # 准备查询参数
                exact_match = keyword
                partial_match = like_pattern
                cursor.execute(sql, (
                    exact_match, partial_match, partial_match, partial_match, partial_match,  # 传统实体
                    exact_match, partial_match, partial_match, partial_match, partial_match   # AI实体
                ))

            results = cursor.fetchall()

            # ------------------------
            # 检索结果排序和格式化（不限制返回条数）
            # ------------------------
            def sort_key(result):
                # 综合排序：相关性得分 * 类型权重
                relevance = result.get('relevance_score', 0)
                type_weight = result.get('type_weight', 0.5)
                return -(relevance * type_weight)
            
            # 为结果添加权重并排序
            results_list = list(results)  # 转换为列表
            for result in results_list:
                result['combined_score'] = result.get('relevance_score', 0) * result.get('type_weight', 0.5)
            
            results_list.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
            results = results_list  # 不限制返回条数
            
            formatted_list = []
            
            for row in results:
                # 提取描述摘要
                desc = row.get('description', '')
                if desc:
                    snippet = desc[:100] + '...'
                else:
                    snippet = '暂无详细描述'
                
                # 提取并处理图片URL
                img = row.get('image_url')
                image_url = None
                if img and img != 'null' and img.strip():
                    # 如果是从crawled_images关联的路径
                    if 'crawled_images' in img or img.startswith('crawled_images'):
                        actual_file = os.path.basename(img)
                        image_url = f"/api/images/crawled/{actual_file}"
                    # 如果是related_images_url字段（可能是URL字符串）
                    elif img.startswith('http://') or img.startswith('https://'):
                        image_url = img
                    # 如果是以/开头的路径
                    elif img.startswith('/'):
                        image_url = img
                    # 其他情况，尝试作为文件名处理
                    else:
                        image_url = f"/api/images/crawled/{os.path.basename(img)}"
                
                # 如果没有图片，使用默认图片
                if not image_url:
                    image_url = "/public/default.jpg"

                # 组装数据
                formatted_list.append({
                    "id": row['id'],
                    "title": row['title'],
                    "entity_name": row['title'],
                    "description": desc,
                    "snippet": snippet,
                    "tags": [row['type_tag']], 
                    "source_url": row.get('source', '#'),
                    "image_url": image_url,
                    "relevance_score": row.get('relevance_score', 0)
                })

            return jsonify({
                "code": 200,
                "msg": "success",
                "data": formatted_list
            })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "msg": str(e), "data": []})
        
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


@app.route('/api/ai_search', methods=['GET'])
def ai_search():
    """
    AI 检索接口：调用大模型理解用户需求，将用户需求转化为检索词进行语义搜索
    - 首先使用AI模型分析用户需求，转化为检索关键词
    - 然后使用检索关键词在数据库中匹配
    - 依赖环境变量 DASHSCOPE_API_KEY 或 ALIYUN_API_KEY
    - 返回结构：data 为检索结果列表，ai_analysis 为 AI 分析结果
    """
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return jsonify({"code": 400, "msg": "请输入搜索关键词", "data": []})

    rag_system = init_search_rag_system()
    if not rag_system:
        return jsonify({"code": 500, "msg": "AI 检索初始化失败，请检查阿里云 API Key 配置", "data": []})

    # 获取数据库连接
    from db_connection import get_default_db_connection
    conn = get_default_db_connection()
    if not conn:
        return jsonify({"code": 500, "msg": "数据库连接失败", "data": []})

    try:
        # ------------------------
        # 1. AI语义分析：将用户需求转化为检索关键词
        # ------------------------
        semantic_extraction_prompt = """
你是一位专业的文化资源检索专家，请将用户的自然语言查询转换为精确的检索关键词。

用户查询: {query}

请按照以下JSON格式返回结果：
{{
  "keywords": ["关键词1", "关键词2", ...],  # 提取的核心关键词（用于数据库检索）
  "search_query": "优化后的检索式"  # 适合数据库检索的检索式
}}

要求：
1. 提取用户查询中的核心文化主题、节日名称、习俗、人物、地点等关键词
2. 如果涉及多个概念，用空格或逗号分隔
3. 保持原意，不要添加额外信息
4. search_query应该是适合在数据库中直接检索的字符串
"""
        
        try:
            extraction_response = rag_system.model.invoke(
                semantic_extraction_prompt.format(query=keyword)
            )
            extraction_result = extraction_response.content if hasattr(extraction_response, 'content') else str(extraction_response)
            
            # 解析AI返回的结果
            try:
                if isinstance(extraction_result, str):
                    ai_analysis = json.loads(extraction_result)
                elif isinstance(extraction_result, dict):
                    ai_analysis = extraction_result
                else:
                    raise ValueError("无法解析AI返回结果")
                
                # 获取检索关键词
                search_keywords = ai_analysis.get("keywords", [keyword])
                search_query = ai_analysis.get("search_query", keyword)
                
                # 如果关键词是列表，取第一个作为主要检索词
                if isinstance(search_keywords, list) and search_keywords:
                    primary_keyword = search_keywords[0]
                else:
                    primary_keyword = keyword
                
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                # 如果解析失败，使用原始关键词
                primary_keyword = keyword
                search_query = keyword
                ai_analysis = {"keywords": [keyword], "search_query": keyword}
        except Exception as e:
            # 如果AI调用失败，使用原始关键词
            primary_keyword = keyword
            search_query = keyword
            ai_analysis = {"keywords": [keyword], "search_query": keyword}

        # ------------------------
        # 2. 使用检索关键词在数据库中匹配
        # ------------------------
        from pymysql.cursors import DictCursor
        with conn.cursor(DictCursor) as cursor:
            like_pattern = f'%{search_query}%'
            
            sql = """
                (SELECT 
                    ce.id, 
                    ce.entity_name as title, 
                    ce.description, 
                    COALESCE(ci.storage_path, ce.related_images_url) as image_url,
                    ce.source,
                    '传统实体' as type_tag,
                    CASE
                        WHEN ce.entity_name LIKE %s THEN 2.0
                        WHEN ce.entity_name LIKE %s THEN 1.5
                        WHEN ce.description LIKE %s THEN 1.0
                        ELSE 0.5
                    END as relevance_score,
                    1 as type_weight
                FROM cultural_entities ce
                LEFT JOIN crawled_images ci ON ce.id = ci.entity_id
                WHERE ce.entity_name LIKE %s OR ce.description LIKE %s
                GROUP BY ce.id, ce.entity_name, ce.description, ce.source, ci.storage_path, ce.related_images_url)
                
                UNION ALL
                
                (SELECT 
                    ace.id, 
                    ace.entity_name as title, 
                    ace.description, 
                    ace.related_images_url as image_url,
                    'AIGC生成' as source,
                    'AI实体' as type_tag,
                    CASE
                        WHEN ace.entity_name LIKE %s THEN 1.6
                        WHEN ace.entity_name LIKE %s THEN 1.2
                        WHEN ace.description LIKE %s THEN 0.8
                        ELSE 0.4
                    END as relevance_score,
                    0.7 as type_weight
                FROM AIGC_cultural_entities ace
                WHERE ace.entity_name LIKE %s OR ace.description LIKE %s)
                
                -- 不限制返回条数，移除所有LIMIT子句
            """
            
            exact_match = search_query
            partial_match = like_pattern
            
            cursor.execute(sql, (
                exact_match, partial_match, partial_match, partial_match, partial_match,  # 传统实体
                exact_match, partial_match, partial_match, partial_match, partial_match   # AI实体
            ))
            results = cursor.fetchall()

        # ------------------------
        # 3. 检索结果排序和格式化
        # ------------------------
        results_list = list(results)  # 转换为列表
        for result in results_list:
            result['combined_score'] = result.get('relevance_score', 0) * result.get('type_weight', 0.5)
        
        results_list.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
        results = results_list  # 不限制返回条数
        
        formatted_list = []
        for row in results:
            desc = row.get('description', '')
            snippet = desc[:100] + '...' if desc else '暂无详细描述'
            
            # 处理图片URL
            img = row.get('image_url')
            image_url = None
            if img and img != 'null' and img.strip():
                if 'crawled_images' in img or img.startswith('crawled_images'):
                    actual_file = os.path.basename(img)
                    image_url = f"/api/images/crawled/{actual_file}"
                elif img.startswith('http://') or img.startswith('https://'):
                    image_url = img
                elif img.startswith('/'):
                    image_url = img
                else:
                    image_url = f"/api/images/crawled/{os.path.basename(img)}"
            
            if not image_url:
                image_url = "/public/default.jpg"
            
            formatted_list.append({
                "id": row['id'],
                "title": row['title'],
                "entity_name": row['title'],
                "description": desc,
                "snippet": snippet,
                "tags": [row['type_tag']], 
                "source_url": row.get('source', '#'),
                "image_url": image_url,
                "relevance_score": row.get('relevance_score', 0)
            })

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": formatted_list,
            "ai_analysis": ai_analysis  # 返回AI分析结果
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "msg": str(e), "data": []})
        
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

@app.route('/api/images/crawled/<path:filename>')
def serve_crawled_image(filename):
    """提供crawled_images文件夹中的图片"""
    try:
        from flask import send_from_directory
        import urllib.parse
        
        # URL解码文件名（处理中文文件名）
        filename = urllib.parse.unquote(filename)
        
        # 获取项目根目录
        # 使用相对路径
        current_file_dir = os.path.dirname(os.path.realpath(__file__))
        base_dir = os.path.dirname(current_file_dir)
        image_dir = os.path.join(base_dir, "crawled_images")
        
        # 确保文件路径安全（防止路径遍历攻击）
        safe_path = os.path.normpath(os.path.join(image_dir, filename))
        if not safe_path.startswith(os.path.normpath(image_dir)):
            return jsonify({'error': 'Invalid file path'}), 403
        
        # 如果文件不存在，尝试只使用文件名（忽略storage_path中的路径部分）
        if not os.path.exists(safe_path):
            # 只使用文件名部分
            actual_filename = os.path.basename(filename)
            safe_path = os.path.join(image_dir, actual_filename)
        
        # 如果文件仍然不存在，返回default图片
        if not os.path.exists(safe_path):
            default_image_path = os.path.join(base_dir, "public", "default.jpg")
            if os.path.exists(default_image_path):
                return send_from_directory(os.path.join(base_dir, "public"), "default.jpg")
            else:
                # 如果default.jpg也不存在，返回404
                return jsonify({'error': 'Image not found'}), 404
        
        # 文件存在，返回图片
        return send_from_directory(image_dir, os.path.basename(safe_path))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 404

@app.route('/api/aigc/sessions', methods=['GET'])
def get_aigc_sessions():
    """获取用户的AIGC会话列表"""
    try:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            # 显式使用DictCursor确保返回字典格式
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, user_id, created_at, summary, COALESCE(mode, 'text') as mode
                    FROM qa_sessions
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                """, (user_id,))
                sessions = cursor.fetchall()
                
                # 为每个会话获取消息数量
                sessions_with_messages = []
                for session in sessions:
                    # 确保session是字典格式
                    if not isinstance(session, dict):
                        if isinstance(session, tuple):
                            # 如果是元组，尝试转换为字典
                            columns = ['id', 'user_id', 'created_at', 'summary', 'mode']
                            session = dict(zip(columns, session))
                        else:
                            continue
                    
                    cursor.execute("""
                        SELECT COUNT(*) as message_count
                        FROM qa_messages
                        WHERE session_id = %s
                    """, (session.get('id'),))
                    msg_count = cursor.fetchone()
                    
                    # 确保msg_count是字典格式
                    if not isinstance(msg_count, dict):
                        if isinstance(msg_count, tuple):
                            msg_count = {'message_count': msg_count[0] if msg_count else 0}
                        else:
                            msg_count = {'message_count': 0}
                    
                    created_at = session.get('created_at')
                    sessions_with_messages.append({
                        'id': session.get('id'),
                        'user_id': session.get('user_id'),
                        'created_at': created_at.isoformat() if created_at else None,
                        'summary': session.get('summary'),
                        'mode': session.get('mode', 'text'),  # 确保mode字段正确返回
                        'message_count': msg_count.get('message_count', 0) if msg_count else 0
                    })
                
                return jsonify({
                    'success': True,
                    'sessions': sessions_with_messages
                })
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'获取会话列表失败：{str(e)}'
        }), 500

@app.route('/api/aigc/sessions', methods=['POST'])
def create_aigc_session():
    """创建新的AIGC会话"""
    try:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or (request.json.get('user_id') if request.is_json else None)
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        summary = None
        if request.is_json:
            summary = request.json.get('summary', '新对话')
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 获取模式（默认为text）
                mode = request.json.get('mode', 'text') if request.is_json else request.form.get('mode', 'text')
                
                # 检查表是否有mode字段，如果没有则添加
                try:
                    cursor.execute("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'qa_sessions' 
                        AND COLUMN_NAME = 'mode'
                    """)
                    if not cursor.fetchone():
                        # 添加mode字段
                        cursor.execute("""
                            ALTER TABLE qa_sessions 
                            ADD COLUMN mode ENUM('text', 'image') DEFAULT 'text' COMMENT '会话模式（text或image）'
                        """)
                        conn.commit()
                except Exception as e:
                    pass
                
                cursor.execute("""
                    INSERT INTO qa_sessions (user_id, summary, mode)
                    VALUES (%s, %s, %s)
                """, (user_id, summary, mode))
                conn.commit()
                session_id = cursor.lastrowid
                
                cursor.execute("""
                    SELECT id, user_id, created_at, summary, mode
                    FROM qa_sessions
                    WHERE id = %s
                """, (session_id,))
                session = cursor.fetchone()
                
                return jsonify({
                    'success': True,
                    'session': {
                        'id': session['id'],
                        'user_id': session['user_id'],
                        'created_at': session['created_at'].isoformat() if session['created_at'] else None,
                        'summary': session['summary'],
                        'mode': session.get('mode', 'text')
                    }
                })
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'创建会话失败：{str(e)}'
        }), 500

@app.route('/api/aigc/sessions/<int:session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    """获取指定会话的消息列表"""
    try:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 验证会话属于该用户
                cursor.execute("""
                    SELECT user_id FROM qa_sessions WHERE id = %s
                """, (session_id,))
                session = cursor.fetchone()
                if not session:
                    return jsonify({'success': False, 'message': '会话不存在'}), 404
                if session['user_id'] != user_id:
                    return jsonify({'success': False, 'message': '无权访问该会话'}), 403
                
                # 获取消息列表（使用新的表结构）
                # 检查表是否有新字段
                try:
                    cursor.execute("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'qa_messages' 
                        AND COLUMN_NAME = 'user_message'
                    """)
                    has_new_structure = cursor.fetchone() is not None
                except:
                    has_new_structure = False
                
                if has_new_structure:
                    # 检查是否有image_from_users_url字段
                    cursor.execute("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'qa_messages' 
                        AND COLUMN_NAME = 'image_from_users_url'
                    """)
                    has_image_from_users_field = cursor.fetchone() is not None
                    
                    # 检查是否有retrieval_id字段
                    cursor.execute("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'qa_messages' 
                        AND COLUMN_NAME = 'retrieval_id'
                    """)
                    has_retrieval_id_field = cursor.fetchone() is not None
                    
                    # 使用新表结构
                    fields = ['id', 'user_id', 'session_id', 'create_time', 'user_message', 'ai_message', 
                             'user_feedback', 'timestamp', 'model', 'image_url']
                    if has_image_from_users_field:
                        fields.append('image_from_users_url')
                    if has_retrieval_id_field:
                        fields.append('retrieval_id')
                    
                    cursor.execute(f"""
                        SELECT {', '.join(fields)}
                        FROM qa_messages
                        WHERE session_id = %s
                        ORDER BY create_time ASC
                    """, (session_id,))
                    messages = cursor.fetchall()
                    
                    formatted_messages = []
                    for msg in messages:
                        # 解析用户上传的图片URL（JSON格式）
                        user_images = []
                        if has_image_from_users_field and msg.get('image_from_users_url'):
                            try:
                                user_images = json.loads(msg['image_from_users_url']) if isinstance(msg['image_from_users_url'], str) else msg['image_from_users_url']
                                if not isinstance(user_images, list):
                                    user_images = []
                            except:
                                user_images = []
                        
                        # 添加用户消息
                        if msg['user_message']:
                            formatted_messages.append({
                                'id': msg['id'],
                                'role': 'user',
                                'content': msg['user_message'],
                                'timestamp': msg['create_time'].isoformat() if msg['create_time'] else (msg['timestamp'].isoformat() if msg['timestamp'] else None),
                                'images': user_images  # 用户上传的图片
                            })
                        # 添加AI回复
                        if msg['ai_message']:
                            # 确保model字段正确：如果数据库中是'image'，保持'image'；否则默认为'text'
                            model_type = msg['model'] if msg['model'] in ('text', 'image') else 'text'
                            
                            # 解析image_url：可能是单个图片路径，也可能是连环画JSON
                            image_path = None
                            image_paths = None
                            is_comic = False
                            comic_count = 0
                            
                            if msg.get('image_url'):
                                try:
                                    # 尝试解析为JSON（连环画格式）
                                    comic_data = json.loads(msg['image_url'])
                                    if isinstance(comic_data, dict) and comic_data.get('type') == 'comic':
                                        # 连环画数据
                                        is_comic = True
                                        image_paths = comic_data.get('paths', [])
                                        comic_count = comic_data.get('count', len(image_paths) if image_paths else 0)
                                        image_path = image_paths[0] if image_paths else None  # 第一张作为主图
                                    else:
                                        # 单个图片路径
                                        image_path = msg['image_url']
                                except (json.JSONDecodeError, TypeError):
                                    # 不是JSON，当作单个图片路径
                                    image_path = msg['image_url']
                            
                            # 从qa_messages表的retrieval_id字段获取检索资源ID（如果存在）
                            retrieved_resource_ids = []
                            retrieved_resources_data = None
                            try:
                                # 优先从qa_messages表的retrieval_id字段获取
                                if has_retrieval_id_field and msg.get('retrieval_id'):
                                    retrieved_ids_str = msg['retrieval_id']
                                    if retrieved_ids_str:
                                        retrieved_resource_ids = [rid.strip() for rid in retrieved_ids_str.split(',') if rid.strip()]
                                # 如果没有，尝试从AIGC资源表获取（兼容旧数据）
                                if not retrieved_resource_ids:
                                    cursor.execute("""
                                        SELECT retrieved_resource_ids 
                                        FROM AIGC_cultural_resources 
                                        WHERE content_feature_data LIKE %s
                                        ORDER BY created_at DESC
                                        LIMIT 1
                                    """, (f"%{msg['user_message'][:50]}%",))
                                    aigc_resource = cursor.fetchone()
                                    if aigc_resource and aigc_resource.get('retrieved_resource_ids'):
                                        retrieved_ids_str = aigc_resource['retrieved_resource_ids']
                                        if retrieved_ids_str:
                                            retrieved_resource_ids = [rid.strip() for rid in retrieved_ids_str.split(',') if rid.strip()]
                                
                                if retrieved_resource_ids:
                                        
                                        # 根据资源ID获取资源详细信息
                                        if retrieved_resource_ids:
                                            db_results = []
                                            for rid in retrieved_resource_ids:
                                                try:
                                                    resource_id = int(rid)
                                                    # 尝试从不同表查找资源
                                                    # 1. cultural_resources
                                                    cursor.execute("""
                                                        SELECT id, title, resource_type, content_feature_data, source_from
                                                        FROM cultural_resources WHERE id = %s
                                                    """, (resource_id,))
                                                    row = cursor.fetchone()
                                                    if row:
                                                        content_data = json.loads(row.get("content_feature_data", "{}") or "{}")
                                                        db_results.append({
                                                            "table": "cultural_resources",
                                                            "id": row.get("id"),
                                                            "title": row.get("title", ""),
                                                            "content": content_data.get("content_preview", "")[:200] if isinstance(content_data, dict) else "",
                                                            "source": row.get("source_from", ""),
                                                            "resource_type": row.get("resource_type", "")
                                                        })
                                                        continue
                                                    
                                                    # 2. cultural_entities
                                                    cursor.execute("""
                                                        SELECT id, entity_name, entity_type, description
                                                        FROM cultural_entities WHERE id = %s
                                                    """, (resource_id,))
                                                    row = cursor.fetchone()
                                                    if row:
                                                        db_results.append({
                                                            "table": "cultural_entities",
                                                            "id": row.get("id"),
                                                            "title": row.get("entity_name", ""),
                                                            "content": row.get("description", "")[:200],
                                                            "source": "",
                                                            "entity_type": row.get("entity_type", "")
                                                        })
                                                        continue
                                                    
                                                    # 3. cultural_resources_from_user
                                                    cursor.execute("""
                                                        SELECT id, title, resource_type, content_feature_data
                                                        FROM cultural_resources_from_user WHERE id = %s
                                                    """, (resource_id,))
                                                    row = cursor.fetchone()
                                                    if row:
                                                        content_data = json.loads(row.get("content_feature_data", "{}") or "{}")
                                                        db_results.append({
                                                            "table": "cultural_resources_from_user",
                                                            "id": row.get("id"),
                                                            "title": row.get("title", ""),
                                                            "content": content_data.get("content_preview", "")[:200] if isinstance(content_data, dict) else "",
                                                            "source": "用户上传",
                                                            "resource_type": row.get("resource_type", "")
                                                        })
                                                except (ValueError, Exception) as e:
                                                    continue
                                            
                                            if db_results:
                                                retrieved_resources_data = {
                                                    "vector_results": [],
                                                    "database_results": db_results,
                                                    "web_results": []
                                                }
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                            
                            formatted_messages.append({
                                'id': msg['id'],
                                'role': 'assistant',
                                'content': msg['ai_message'],
                                'timestamp': msg['create_time'].isoformat() if msg['create_time'] else (msg['timestamp'].isoformat() if msg['timestamp'] else None),
                                'image_path': image_path,  # 单个图片路径或连环画第一张
                                'image_paths': image_paths,  # 连环画所有图片路径
                                'is_comic': is_comic,  # 是否是连环画
                                'comic_count': comic_count,  # 连环画数量
                                'model': model_type,  # 确保model字段正确传递
                                'retrieved_resources': retrieved_resources_data,  # 检索资源数据
                                'retrieved_resource_ids': retrieved_resource_ids,  # 检索资源ID列表
                                'key_entities': [],
                                'sources': ''
                            })
                else:
                    # 兼容旧表结构
                    cursor.execute("""
                        SELECT id, session_id, sender, message_content, user_feedback, timestamp
                        FROM qa_messages
                        WHERE session_id = %s
                        ORDER BY timestamp ASC
                    """, (session_id,))
                    messages = cursor.fetchall()
                    
                    formatted_messages = []
                    for msg in messages:
                        formatted_messages.append({
                            'id': msg['id'],
                            'role': msg['sender'],
                            'content': msg['message_content'] or '',
                            'feedback': msg['user_feedback'],
                            'timestamp': msg['timestamp'].isoformat() if msg['timestamp'] else None,
                            'retrieved_resources': None,
                            'key_entities': [],
                            'sources': '',
                            'image_path': None
                        })
                
                return jsonify({
                    'success': True,
                    'messages': formatted_messages
                })
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'获取消息列表失败：{str(e)}'
        }), 500

@app.route('/api/aigc/sessions/<int:session_id>/messages', methods=['POST'])
def save_message(session_id):
    """保存消息到指定会话"""
    try:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or (request.json.get('user_id') if request.is_json else None)
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        if not request.is_json:
            return jsonify({'success': False, 'message': '请求格式错误'}), 400
        
        data = request.json
        user_message = data.get('user_message', '')  # 用户输入
        ai_message = data.get('ai_message', '')  # AI回答
        image_url = data.get('image_url')  # 图片URL（用于图片AIGC）
        model = data.get('model', 'text')  # 模型类型
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 验证会话属于该用户
                cursor.execute("""
                    SELECT user_id, mode FROM qa_sessions WHERE id = %s
                """, (session_id,))
                session = cursor.fetchone()
                if not session:
                    return jsonify({'success': False, 'message': '会话不存在'}), 404
                if session['user_id'] != user_id:
                    return jsonify({'success': False, 'message': '无权访问该会话'}), 403
                
                # 获取会话的mode，如果没有提供model，从会话中获取
                if not model or model not in ['text', 'image']:
                    if session.get('mode'):
                        model = session['mode']
                    else:
                        model = 'text'
                
                # 检查表是否有新字段
                try:
                    cursor.execute("""
                        SELECT COLUMN_NAME 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'qa_messages' 
                        AND COLUMN_NAME = 'user_message'
                    """)
                    has_new_structure = cursor.fetchone() is not None
                except:
                    has_new_structure = False
                
                if has_new_structure:
                    # 使用新表结构保存消息
                    cursor.execute("""
                        INSERT INTO qa_messages (user_id, session_id, user_message, ai_message, model, image_url)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (user_id, session_id, user_message, ai_message, model, image_url))
                else:
                    # 兼容旧表结构
                    # 分别保存用户消息和AI消息
                    if user_message:
                        cursor.execute("""
                            INSERT INTO qa_messages (session_id, sender, message_content)
                            VALUES (%s, 'user', %s)
                        """, (session_id, user_message))
                    if ai_message:
                        message_content = ai_message
                        if image_url:
                            message_content = json.dumps({
                                'content': ai_message,
                                'image_path': image_url
                            }, ensure_ascii=False)
                        cursor.execute("""
                            INSERT INTO qa_messages (session_id, sender, message_content)
                            VALUES (%s, 'ai', %s)
                        """, (session_id, message_content))
                conn.commit()
                message_id = cursor.lastrowid
                
                return jsonify({
                    'success': True,
                    'message_id': message_id
                })
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'保存消息失败：{str(e)}'
        }), 500

@app.route('/api/aigc/sessions/<int:session_id>', methods=['DELETE'])
def delete_aigc_session(session_id):
    """删除单个AIGC会话"""
    try:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 检查会话是否属于该用户
                cursor.execute("""
                    SELECT id FROM qa_sessions
                    WHERE id = %s AND user_id = %s
                """, (session_id, user_id))
                session = cursor.fetchone()
                
                if not session:
                    return jsonify({'success': False, 'message': '会话不存在或无权限'}), 404
                
                # 删除会话相关的消息（外键约束会自动处理）
                cursor.execute("""
                    DELETE FROM qa_messages WHERE session_id = %s
                """, (session_id,))
                
                # 删除会话
                cursor.execute("""
                    DELETE FROM qa_sessions WHERE id = %s
                """, (session_id,))
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': '会话删除成功'
                })
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'删除会话失败：{str(e)}'
        }), 500

@app.route('/api/aigc/sessions/batch', methods=['DELETE'])
def delete_aigc_sessions_batch():
    """批量删除AIGC会话"""
    try:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or (request.json.get('user_id') if request.is_json else None)
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        if not request.is_json:
            return jsonify({'success': False, 'message': '请求格式错误'}), 400
        
        session_ids = request.json.get('session_ids', [])
        if not session_ids or not isinstance(session_ids, list):
            return jsonify({'success': False, 'message': '缺少会话ID列表'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 验证所有会话都属于该用户
                placeholders = ','.join(['%s'] * len(session_ids))
                cursor.execute(f"""
                    SELECT id FROM qa_sessions
                    WHERE id IN ({placeholders}) AND user_id = %s
                """, session_ids + [user_id])
                valid_sessions = cursor.fetchall()
                # 兼容DictCursor和普通cursor
                if valid_sessions and isinstance(valid_sessions[0], dict):
                    valid_ids = [s['id'] for s in valid_sessions]
                else:
                    valid_ids = [s[0] for s in valid_sessions]
                
                if len(valid_ids) != len(session_ids):
                    return jsonify({'success': False, 'message': '部分会话不存在或无权限'}), 403
                
                # 删除会话相关的消息
                cursor.execute(f"""
                    DELETE FROM qa_messages WHERE session_id IN ({placeholders})
                """, session_ids)
                
                # 删除会话
                cursor.execute(f"""
                    DELETE FROM qa_sessions WHERE id IN ({placeholders})
                """, session_ids)
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': f'成功删除 {len(session_ids)} 个会话'
                })
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'批量删除会话失败：{str(e)}'
        }), 500

@app.route('/api/aigc/sessions/all', methods=['DELETE'])
def delete_all_aigc_sessions():
    """删除用户的所有AIGC会话"""
    try:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 获取用户的所有会话ID
                cursor.execute("""
                    SELECT id FROM qa_sessions WHERE user_id = %s
                """, (user_id,))
                sessions = cursor.fetchall()
                session_ids = [s['id'] for s in sessions]
                
                if not session_ids:
                    return jsonify({
                        'success': True,
                        'message': '没有可删除的会话'
                    })
                
                # 删除会话相关的消息
                placeholders = ','.join(['%s'] * len(session_ids))
                cursor.execute(f"""
                    DELETE FROM qa_messages WHERE session_id IN ({placeholders})
                """, session_ids)
                
                # 删除会话
                cursor.execute("""
                    DELETE FROM qa_sessions WHERE user_id = %s
                """, (user_id,))
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': f'成功删除 {len(session_ids)} 个会话'
                })
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'删除所有会话失败：{str(e)}'
        }), 500

@app.route('/api/aigc/sessions/<int:session_id>/summary', methods=['PUT'])
def update_session_summary(session_id):
    """更新会话摘要（标题）"""
    try:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or (request.json.get('user_id') if request.is_json else None)
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        if not request.is_json:
            return jsonify({'success': False, 'message': '请求格式错误'}), 400
        
        summary = request.json.get('summary', '')
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 验证会话属于该用户
                cursor.execute("""
                    SELECT user_id FROM qa_sessions WHERE id = %s
                """, (session_id,))
                session = cursor.fetchone()
                if not session:
                    return jsonify({'success': False, 'message': '会话不存在'}), 404
                if session['user_id'] != user_id:
                    return jsonify({'success': False, 'message': '无权访问该会话'}), 403
                
                # 更新摘要
                cursor.execute("""
                    UPDATE qa_sessions
                    SET summary = %s
                    WHERE id = %s
                """, (summary, session_id))
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': '摘要更新成功'
                })
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'更新会话摘要失败：{str(e)}'
        }), 500

@app.route('/api/annotation/tasks', methods=['GET'])
def get_annotation_tasks():
    """获取标注任务列表"""
    try:
        # 获取用户ID
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        # 获取状态过滤参数（支持：待标注、AI标注中、AI标注完成、已完成）
        status = request.args.get('status', '').strip()
        
        # 创建ResourceUploader实例来获取任务
        user_db_config = get_auth_system().get_user_db_config(user_id)
        if not user_db_config:
            return jsonify({'success': False, 'message': '用户不存在'}), 401
        
        db_config = user_db_config['db_config']
        uploader = ResourceUploader(user_id=user_id, db_config=db_config)
        
        # 获取任务列表
        result = uploader.get_annotation_tasks(user_id, status if status else None)
        
        if result['success']:
            return jsonify({
                'success': True,
                'tasks': result['tasks']
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'获取任务失败：{str(e)}'
        }), 500

@app.route('/api/annotation/tasks/<int:task_id>/details', methods=['GET'])
def get_annotation_details(task_id):
    """获取标注任务详情"""
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 获取任务信息（支持三种资源来源）
                cursor.execute("""
                    SELECT t.id, t.resource_id, t.resource_source, t.status,
                           COALESCE(cru.content_feature_data, cr.content_feature_data, aigc.content_feature_data) as content_feature_data,
                           COALESCE(cru.title, cr.title, aigc.title) as title,
                           COALESCE(cru.resource_type, cr.resource_type, aigc.resource_type) as resource_type,
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
                
                task = cursor.fetchone()
                if not task:
                    return jsonify({'success': False, 'message': '任务不存在'}), 404
                
                # 获取标注记录 - 使用新字段结构
                cursor.execute("""
                    SELECT entity_name, entity_type, description, source,
                           period_era, geo_coordinates, cultural_region,
                           style_features, cultural_value, related_images_url, digital_resource_link,
                           annotation_source, created_at, is_expert_reviewed
                    FROM annotation_records
                    WHERE task_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (task_id,))
                
                record = cursor.fetchone()
                annotations = None
                if record:
                    # 转换为前端需要的格式（兼容旧格式）
                    annotations = {
                        "entity_name": record.get('entity_name', ''),
                        "entity_type": record.get('entity_type', '其他'),
                        "description": record.get('description', ''),
                        "source": record.get('source', ''),
                        "period_era": record.get('period_era', ''),
                        "geo_coordinates": record.get('geo_coordinates', ''),
                        "cultural_region": record.get('cultural_region', ''),
                        "style_features": record.get('style_features', ''),
                        "cultural_value": record.get('cultural_value', ''),
                        "related_images_url": record.get('related_images_url', ''),
                        "digital_resource_link": record.get('digital_resource_link', ''),
                        # 兼容旧格式：转换为entities数组
                        "entities": [{
                            "name": record.get('entity_name', ''),
                            "type": record.get('entity_type', '其他')
                        }] if record.get('entity_name') else [],
                        "is_expert_reviewed": record.get('is_expert_reviewed', False)
                    }
                else:
                    annotations = {
                        "entity_name": "",
                        "entity_type": "其他",
                        "description": "",
                        "entities": [],
                        "is_expert_reviewed": False
                    }
                
                # 解析资源内容
                content_data = json.loads(task['content_feature_data'] or '{}')
                stored_file_name = content_data.get('stored_file_name') or content_data.get('file_name', '')
                resource_image_url = None
                if stored_file_name:
                    # 前端通过该URL即可预览用户上传的文件（目前主要是图片）
                    resource_image_url = f"/uploads/{stored_file_name}"
                
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'resource_id': task['resource_id'],
                    'title': task['title'],
                    'status': task['status'],
                    'resource_content': content_data.get('content_preview', ''),
                    'resource_image_url': resource_image_url,
                    'annotations': annotations
                })
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取失败: {str(e)}'}), 500


@app.route('/api/annotation/tasks/<int:task_id>', methods=['PUT'])
def update_annotation(task_id):
    """更新标注任务"""
    try:
        user_id = int(request.headers.get('X-User-Id', 0))
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        data = request.json
        
        from upload_handler import ResourceUploader
        
        auth_system = get_auth_system()
        user_config = auth_system.get_user_db_config(user_id)
        if not user_config:
            return jsonify({'success': False, 'message': '用户不存在'}), 401
        
        uploader = ResourceUploader(user_id=user_id, db_config=user_config['db_config'])
        
        # 支持新格式（扁平化字段）和旧格式（entities数组）两种输入
        if 'entity_name' in data:
            # 新格式：直接使用
            annotation_data = data
        else:
            # 旧格式：转换为新格式（兼容）
            entities = data.get('entities', [])
            description = data.get('description', '')
            
            if entities:
                # 取第一个实体作为主要标注
                main_entity = entities[0]
                annotation_data = {
                    "entity_name": main_entity.get('name', ''),
                    "entity_type": main_entity.get('type', '其他'),
                    "description": description,
                    "source": data.get('source', ''),
                    "period_era": data.get('period_era', ''),
                    "geo_coordinates": data.get('geo_coordinates', ''),
                    "cultural_region": data.get('cultural_region', ''),
                    "style_features": data.get('style_features', ''),
                    "cultural_value": data.get('cultural_value', ''),
                    "related_images_url": data.get('related_images_url', ''),
                    "digital_resource_link": data.get('digital_resource_link', '')
                }
            else:
                annotation_data = {
                    "entity_name": "",
                    "entity_type": "其他",
                    "description": description,
                    "source": data.get('source', ''),
                    "period_era": data.get('period_era', ''),
                    "geo_coordinates": data.get('geo_coordinates', ''),
                    "cultural_region": data.get('cultural_region', ''),
                    "style_features": data.get('style_features', ''),
                    "cultural_value": data.get('cultural_value', ''),
                    "related_images_url": data.get('related_images_url', ''),
                    "digital_resource_link": data.get('digital_resource_link', '')
                }
        
        result = uploader.save_manual_annotation(task_id, user_id, annotation_data)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


# 提供image_from_users文件夹中的图片
@app.route('/image_from_users/<path:filename>', methods=['GET'])
def serve_user_uploaded_image(filename):
    """提供image_from_users文件夹中的用户上传图片"""
    from flask import send_from_directory
    try:
        # 使用相对路径
        current_file_dir = os.path.dirname(os.path.realpath(__file__))
        base_dir = os.path.dirname(current_file_dir)
        image_dir = os.path.join(base_dir, "image_from_users")
        
        
        # 确保文件路径安全（防止路径遍历攻击）
        safe_path = os.path.normpath(os.path.join(image_dir, filename))
        if not safe_path.startswith(os.path.normpath(image_dir)):
            return jsonify({'error': 'Invalid path'}), 403
        
        
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            return send_from_directory(image_dir, os.path.basename(safe_path))
        else:
            # 列出目录中的文件，用于调试
            if os.path.exists(image_dir):
                files = os.listdir(image_dir)
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        import traceback
        return jsonify({'error': 'File not found'}), 404


@app.route('/uploads/<path:filename>', methods=['GET'])
def serve_uploaded_file(filename):
    """提供uploads文件夹中的上传资源（主要用于标注任务中预览）"""
    from flask import send_from_directory
    try:
        # 使用相对路径
        current_file_dir = os.path.dirname(os.path.realpath(__file__))
        base_dir = os.path.dirname(current_file_dir)
        upload_dir = os.path.join(base_dir, "uploads")
        safe_path = os.path.normpath(os.path.join(upload_dir, filename))
        if not safe_path.startswith(os.path.normpath(upload_dir)):
            return jsonify({'error': 'Invalid path'}), 403
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            return send_from_directory(upload_dir, os.path.basename(safe_path))
        return jsonify({'error': 'File not found'}), 404
    except Exception:
        return jsonify({'error': 'File not found'}), 404

# 提供AIGC_graph文件夹中的图片
@app.route('/AIGC_graph/<path:filename>', methods=['GET'])
def serve_aigc_image(filename):
    """提供AIGC_graph文件夹中的图片"""
    from flask import send_from_directory
    try:
        # 使用相对路径
        current_file_dir = os.path.dirname(os.path.realpath(__file__))
        base_dir = os.path.dirname(current_file_dir)
        image_dir = os.path.join(base_dir, "AIGC_graph")
        
        
        # 确保文件路径安全（防止路径遍历攻击）
        safe_path = os.path.normpath(os.path.join(image_dir, filename))
        if not safe_path.startswith(os.path.normpath(image_dir)):
            return jsonify({'error': 'Invalid path'}), 403
        
        
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            return send_from_directory(image_dir, os.path.basename(safe_path))
        else:
            # 列出目录中的文件，用于调试
            if os.path.exists(image_dir):
                files = os.listdir(image_dir)
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        import traceback
        return jsonify({'error': 'File not found'}), 404

@app.route('/AIGC_graph_from_users/<path:filename>', methods=['GET'])
def serve_aigc_graph_from_users_image(filename):
    """提供AIGC_graph_from_users文件夹中的用户上传图片"""
    from flask import send_from_directory
    try:
        # 使用相对路径
        current_file_dir = os.path.dirname(os.path.realpath(__file__))
        base_dir = os.path.dirname(current_file_dir)
        image_dir = os.path.join(base_dir, "AIGC_graph_from_users")
        
        
        # 确保文件路径安全（防止路径遍历攻击）
        safe_path = os.path.normpath(os.path.join(image_dir, filename))
        if not safe_path.startswith(os.path.normpath(image_dir)):
            return jsonify({'error': 'Invalid path'}), 403
        
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            return send_from_directory(image_dir, os.path.basename(safe_path))
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        import traceback
        return jsonify({'error': 'File not found'}), 404

# 提供头像文件服务（从public文件夹）
# 注意：这个路由必须放在最后，避免拦截其他API路由
@app.route('/<path:filename>', methods=['GET'])
def serve_public_file(filename):
    """提供public文件夹中的文件服务（包括头像和默认头像）"""
    from flask import send_from_directory
    # 如果请求的是AIGC_graph路径，不应该在这里处理（应该由上面的路由处理）
    if filename.startswith('AIGC_graph/'):
        return jsonify({'error': '请使用 /AIGC_graph/<filename> 路径'}), 404
    
    # 只允许访问特定文件类型
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico', '.svg'}
    file_ext = os.path.splitext(filename)[1].lower()
    # 如果文件扩展名不在允许列表中，返回404（避免拦截API路由）
    if file_ext not in allowed_extensions:
        return jsonify({'error': '文件类型不允许'}), 404
    # 检查文件是否存在
    file_path = os.path.join(public_dir, filename)
    if os.path.exists(file_path):
        return send_from_directory(public_dir, filename)
    else:
        return jsonify({'error': '文件不存在'}), 404


@app.route('/api/annotation/tasks/<int:task_id>/approve', methods=['POST'])
def approve_annotation(task_id):
    """审核通过标注并迁移数据"""
    try:
        user_id = int(request.headers.get('X-User-Id', 0))
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        from upload_handler import ResourceUploader
        from db_connection import get_user_db_connection
        
        auth_system = get_auth_system()
        user_config = auth_system.get_user_db_config(user_id)
        if not user_config:
            return jsonify({'success': False, 'message': '用户不存在'}), 401
        
        # 检查用户权限（只有管理员和超级管理员可以审核）
        user_info = get_auth_system().get_user_by_id(user_id)
        role = user_info.get('role') if user_info else None
        if not user_info or (role != '管理员' and role != '超级管理员'):
            return jsonify({'success': False, 'message': '无权限审核'}), 403
        
        uploader = ResourceUploader(user_id=user_id, db_config=user_config['db_config'])
        
        # 1. 先标记标注记录为已审核
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 更新最新标注记录为已审核
                cursor.execute("""
                    UPDATE annotation_records 
                    SET is_expert_reviewed = TRUE, reviewer_id = %s
                    WHERE task_id = %s AND is_latest = 1
                """, (user_id, task_id))
                
                if cursor.rowcount == 0:
                    return jsonify({'success': False, 'message': '未找到标注记录'}), 404
                
                conn.commit()
        finally:
            conn.close()
        
        # 2. 执行数据迁移
        result = uploader.approve_and_migrate_annotation(task_id, user_id)
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'审核失败: {str(e)}'}), 500


@app.route('/api/annotation/tasks/<int:task_id>/pause', methods=['POST'])
def pause_ai_annotation(task_id):
    """暂停AI标注（仅管理员和超级管理员）"""
    try:
        # 获取用户ID（支持多种header格式）
        user_id = (request.headers.get('X-User-Id') or 
                  request.headers.get('X-User-ID') or 
                  (request.json.get('user_id') if request.is_json else None))
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        # 检查用户权限
        from db_connection import get_user_db_connection
        from pymysql.cursors import DictCursor
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_info = cursor.fetchone()
                if not user_info:
                    return jsonify({'success': False, 'message': '用户不存在'}), 404
                
                # 兼容DictCursor和普通cursor
                role = user_info.get('role') if isinstance(user_info, dict) else (user_info[0] if user_info else None)
                if role != '管理员' and role != '超级管理员':
                    return jsonify({'success': False, 'message': '权限不足，仅管理员可操作'}), 403
                
                # 检查任务状态
                cursor.execute("SELECT status FROM annotation_tasks WHERE id = %s", (task_id,))
                task = cursor.fetchone()
                if not task:
                    return jsonify({'success': False, 'message': '任务不存在'}), 404
                
                # 兼容DictCursor和普通cursor
                current_status = task.get('status') if isinstance(task, dict) else (task[0] if task else None)
                if current_status != 'AI标注中':
                    return jsonify({'success': False, 'message': f'任务当前状态为{current_status}，无法暂停'}), 400
                
                # 更新任务状态为待标注
                cursor.execute(
                    "UPDATE annotation_tasks SET status = %s WHERE id = %s AND status = %s",
                    ('待标注', task_id, 'AI标注中')
                )
                
                if cursor.rowcount == 0:
                    # 检查任务是否还存在
                    cursor.execute("SELECT status FROM annotation_tasks WHERE id = %s", (task_id,))
                    task_check = cursor.fetchone()
                    if not task_check:
                        return jsonify({'success': False, 'message': '任务不存在'}), 404
                    current_status = task_check.get('status') if isinstance(task_check, dict) else (task_check[0] if task_check else None)
                    return jsonify({'success': False, 'message': f'更新失败，任务当前状态为{current_status}，无法暂停'}), 400
                
                conn.commit()
                
                return jsonify({'success': True, 'message': 'AI标注已暂停'})
        finally:
            conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'暂停失败: {str(e)}'}), 500

@app.route('/api/annotation/tasks/<int:task_id>/start-ai', methods=['POST'])
def start_ai_annotation(task_id):
    """启动AI标注（仅管理员和超级管理员）"""
    try:
        # 获取用户ID（支持多种header格式）
        user_id = (request.headers.get('X-User-Id') or 
                  request.headers.get('X-User-ID') or 
                  (request.json.get('user_id') if request.is_json else None))
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        # 检查用户权限
        from db_connection import get_user_db_connection
        from pymysql.cursors import DictCursor
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_info = cursor.fetchone()
                if not user_info:
                    return jsonify({'success': False, 'message': '用户不存在'}), 404
                
                # 兼容DictCursor和普通cursor
                role = user_info.get('role') if isinstance(user_info, dict) else (user_info[0] if user_info else None)
                if role != '管理员' and role != '超级管理员':
                    return jsonify({'success': False, 'message': '权限不足，仅管理员可操作'}), 403
                
                # 检查任务状态
                cursor.execute("SELECT status FROM annotation_tasks WHERE id = %s", (task_id,))
                task = cursor.fetchone()
                if not task:
                    return jsonify({'success': False, 'message': '任务不存在'}), 404
                
                # 兼容DictCursor和普通cursor
                current_status = task.get('status') if isinstance(task, dict) else (task[0] if task else None)
                if current_status != '待标注':
                    return jsonify({'success': False, 'message': f'任务当前状态为{current_status}，无法启动AI标注'}), 400
                
                # 先更新任务状态为AI标注中（防止重复触发）
                cursor.execute(
                    "UPDATE annotation_tasks SET status = %s WHERE id = %s AND status = %s",
                    ('AI标注中', task_id, '待标注')
                )
                
                if cursor.rowcount == 0:
                    # 检查任务状态是否已改变
                    cursor.execute("SELECT status FROM annotation_tasks WHERE id = %s", (task_id,))
                    task_check = cursor.fetchone()
                    if task_check:
                        current_status = task_check.get('status') if isinstance(task_check, dict) else (task_check[0] if task_check else None)
                        return jsonify({'success': False, 'message': f'任务状态已改变为{current_status}，无法启动AI标注'}), 400
                    else:
                        return jsonify({'success': False, 'message': '任务不存在'}), 404
                
                conn.commit()
                
                # 触发AI标注
                user_db_config = get_auth_system().get_user_db_config(user_id)
                if not user_db_config:
                    # 如果用户配置不存在，回滚状态
                    cursor.execute("UPDATE annotation_tasks SET status = %s WHERE id = %s", ('待标注', task_id))
                    conn.commit()
                    return jsonify({'success': False, 'message': '用户配置不存在'}), 500
                
                db_config = user_db_config['db_config']
                uploader = ResourceUploader(user_id=user_id, db_config=db_config)
                uploader.trigger_ai_annotation(task_id)
                
                return jsonify({'success': True, 'message': 'AI标注已启动'})
        finally:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'启动失败: {str(e)}'}), 500

@app.route('/api/annotation/tasks/<int:task_id>/reject', methods=['POST'])
def reject_annotation(task_id):
    """驳回标注"""
    try:
        user_id = int(request.headers.get('X-User-Id', 0))
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        data = request.json
        reject_reason = data.get('reason', '')
        
        from db_connection import get_user_db_connection
        
        auth_system = get_auth_system()
        user_config = auth_system.get_user_db_config(user_id)
        if not user_config:
            return jsonify({'success': False, 'message': '用户不存在'}), 401
        
        # 检查用户权限（只有管理员和超级管理员可以审核）
        user_info = get_auth_system().get_user_by_id(user_id)
        role = user_info.get('role') if user_info else None
        if not user_info or (role != '管理员' and role != '超级管理员'):
            return jsonify({'success': False, 'message': '无权限审核'}), 403
        
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 更新任务状态为已驳回
                cursor.execute("""
                    UPDATE annotation_tasks 
                    SET status = '已驳回'
                    WHERE id = %s
                """, (task_id,))
                
                # 更新标注记录
                cursor.execute("""
                    UPDATE annotation_records 
                    SET is_expert_reviewed = TRUE, reviewer_id = %s
                    WHERE task_id = %s AND is_latest = 1
                """, (user_id, task_id))
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': '标注已驳回'
                })
        finally:
                conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'驳回失败: {str(e)}'}), 500


# ==================== 评论相关API ====================

@app.route('/api/comments', methods=['GET'])
def get_comments():
    """获取资源的评论列表"""
    resource_id = request.args.get('resource_id', type=int)
    if not resource_id:
        return jsonify({'success': False, 'message': '缺少resource_id参数'}), 400
    
    try:
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 获取评论列表，包括用户信息和点赞数
                cursor.execute("""
                    SELECT 
                        c.id,
                        c.resource_id,
                        c.user_id,
                        c.comment_content,
                        c.created_at,
                        u.account,
                        u.nickname,
                        u.avatar_path,
                        (SELECT COUNT(*) FROM comment_likes WHERE comment_id = c.id) as like_count
                    FROM user_comments c
                    LEFT JOIN users u ON c.user_id = u.id
                    WHERE c.resource_id = %s AND c.comment_status = 'approved'
                    ORDER BY c.created_at DESC
                """, (resource_id,))
                
                comments = cursor.fetchall()
                
                # 获取每条评论的回复
                for comment in comments:
                    cursor.execute("""
                        SELECT 
                            r.id,
                            r.comment_id,
                            r.reply_user_id,
                            r.reply_content,
                            r.created_at,
                            u.account,
                            u.nickname,
                            u.avatar_path
                        FROM comment_replies r
                        LEFT JOIN users u ON r.reply_user_id = u.id
                        WHERE r.comment_id = %s
                        ORDER BY r.created_at ASC
                    """, (comment['id'],))
                    comment['replies'] = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'comments': comments
                })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取评论失败：{str(e)}'}), 500


@app.route('/api/comments', methods=['POST'])
def create_comment():
    """创建评论"""
    try:
        data = request.json
        resource_id = data.get('resource_id')
        user_id = data.get('user_id')
        comment_content = data.get('comment_content', '').strip()
        
        if not resource_id or not user_id or not comment_content:
            return jsonify({'success': False, 'message': '缺少必要参数'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO user_comments (resource_id, user_id, comment_content, comment_status)
                    VALUES (%s, %s, %s, 'approved')
                """, (resource_id, user_id, comment_content))
                conn.commit()
                
                comment_id = cursor.lastrowid
                
                # 获取创建的评论信息
                cursor.execute("""
                    SELECT 
                        c.id,
                        c.resource_id,
                        c.user_id,
                        c.comment_content,
                        c.created_at,
                        u.account,
                        u.nickname,
                        u.avatar_path,
                        0 as like_count
                    FROM user_comments c
                    LEFT JOIN users u ON c.user_id = u.id
                    WHERE c.id = %s
                """, (comment_id,))
                comment = cursor.fetchone()
                comment['replies'] = []
                
                return jsonify({
                    'success': True,
                    'comment': comment,
                    'message': '评论发布成功'
                })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'创建评论失败：{str(e)}'}), 500


@app.route('/api/comments/<int:comment_id>/like', methods=['POST'])
def like_comment(comment_id):
    """点赞评论"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'message': '缺少user_id参数'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 检查是否已经点赞（需要先检查comment_likes表是否存在）
                try:
                    cursor.execute("""
                        SELECT id FROM comment_likes 
                        WHERE comment_id = %s AND user_id = %s
                    """, (comment_id, user_id))
                    
                    existing_like = cursor.fetchone()
                    if existing_like:
                        # 已点赞，取消点赞
                        cursor.execute("""
                            DELETE FROM comment_likes 
                            WHERE comment_id = %s AND user_id = %s
                        """, (comment_id, user_id))
                        action = 'unliked'
                    else:
                        # 未点赞，添加点赞
                        cursor.execute("""
                            INSERT INTO comment_likes (comment_id, user_id)
                            VALUES (%s, %s)
                        """, (comment_id, user_id))
                        action = 'liked'
                        
                        # 发送通知给评论作者
                        cursor.execute("""
                            SELECT user_id FROM user_comments WHERE id = %s
                        """, (comment_id,))
                        comment_author = cursor.fetchone()
                        if comment_author and comment_author['user_id'] != user_id:
                            # 创建通知（需要先检查是否有notifications表）
                            try:
                                # 获取点赞用户的昵称
                                cursor.execute("""
                                    SELECT nickname, account FROM users WHERE id = %s
                                """, (user_id,))
                                liker_info = cursor.fetchone()
                                liker_name = liker_info.get('nickname') if liker_info and liker_info.get('nickname') else (liker_info.get('account') if liker_info else '用户')
                                
                                cursor.execute("""
                                    INSERT INTO notifications (user_id, notification_type, content, related_id)
                                    VALUES (%s, 'like', %s, %s)
                                """, (comment_author['user_id'], f'{liker_name}点赞了您的评论', comment_id))
                                conn.commit()
                            except Exception as notify_error:
                                pass  # 如果notifications表不存在，忽略
                except Exception as table_error:
                    # comment_likes表可能不存在，返回错误提示
                    return jsonify({
                        'success': False,
                        'message': '点赞功能需要comment_likes表，请先创建该表'
                    }), 500
                
                conn.commit()
                
                # 获取当前点赞数
                try:
                    cursor.execute("""
                        SELECT COUNT(*) as like_count 
                        FROM comment_likes 
                        WHERE comment_id = %s
                    """, (comment_id,))
                    result = cursor.fetchone()
                    like_count = result['like_count'] if result else 0
                except:
                    like_count = 0
                
                return jsonify({
                    'success': True,
                    'action': action,
                    'like_count': like_count
                })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'点赞失败：{str(e)}'}), 500


@app.route('/api/comments/<int:comment_id>/reply', methods=['POST'])
def reply_comment(comment_id):
    """回复评论"""
    try:
        data = request.json
        reply_user_id = data.get('user_id')
        reply_content = data.get('reply_content', '').strip()
        
        if not reply_user_id or not reply_content:
            return jsonify({'success': False, 'message': '缺少必要参数'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO comment_replies (comment_id, reply_user_id, reply_content)
                    VALUES (%s, %s, %s)
                """, (comment_id, reply_user_id, reply_content))
                conn.commit()
                
                reply_id = cursor.lastrowid
                
                # 获取创建的回复信息
                cursor.execute("""
                    SELECT 
                        r.id,
                        r.comment_id,
                        r.reply_user_id,
                        r.reply_content,
                        r.created_at,
                        u.account,
                        u.nickname,
                        u.avatar_path
                    FROM comment_replies r
                    LEFT JOIN users u ON r.reply_user_id = u.id
                    WHERE r.id = %s
                """, (reply_id,))
                reply = cursor.fetchone()
                
                # 发送通知给评论作者
                cursor.execute("""
                    SELECT user_id FROM user_comments WHERE id = %s
                """, (comment_id,))
                comment_author = cursor.fetchone()
                if comment_author and comment_author['user_id'] != reply_user_id:
                    try:
                        # 获取回复用户的昵称
                        cursor.execute("""
                            SELECT nickname, account FROM users WHERE id = %s
                        """, (reply_user_id,))
                        replier_info = cursor.fetchone()
                        replier_name = replier_info.get('nickname') if replier_info and replier_info.get('nickname') else (replier_info.get('account') if replier_info else '用户')
                        
                        cursor.execute("""
                            INSERT INTO notifications (user_id, notification_type, content, related_id)
                            VALUES (%s, 'reply', %s, %s)
                        """, (comment_author['user_id'], f'{replier_name}回复了您的评论', comment_id))
                        conn.commit()
                    except Exception as notify_error:
                        pass  # 如果notifications表不存在，忽略
                
                return jsonify({
                    'success': True,
                    'reply': reply,
                    'message': '回复成功'
                })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'回复失败：{str(e)}'}), 500


@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    """获取用户的通知列表"""
    user_id = request.args.get('user_id', type=int)
    is_read = request.args.get('is_read', type=int)
    
    if not user_id:
        return jsonify({'success': False, 'message': '缺少user_id参数'}), 400
    
    try:
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor(DictCursor) as cursor:
                # 构建查询条件
                query = "SELECT * FROM notifications WHERE user_id = %s"
                params = [user_id]
                
                if is_read is not None:
                    query += " AND is_read = %s"
                    params.append(is_read)
                
                query += " ORDER BY created_at DESC"
                # 不限制返回条数，移除LIMIT子句
                
                cursor.execute(query, params)
                notifications = cursor.fetchall()
                
                return jsonify({
                    'success': True,
                    'notifications': notifications
                })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取通知失败：{str(e)}'}), 500


@app.route('/api/admin/log-access', methods=['POST'])
def log_access():
    """记录用户访问日志（包括管理员）"""
    try:
        data = request.json
        user_id = data.get('user_id')
        access_type = data.get('access_type', 'page_view')
        access_path = data.get('access_path')
        resource_id = data.get('resource_id')
        resource_type = data.get('resource_type')
        
        if not user_id:
            return jsonify({'success': False, 'message': '缺少user_id参数'}), 400
        
        log_user_access(user_id, access_type, access_path, resource_id, resource_type)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    """标记通知为已读"""
    try:
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE notifications 
                    SET is_read = 1 
                    WHERE id = %s
                """, (notification_id,))
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': '通知已标记为已读'
                })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'标记通知已读失败：{str(e)}'}), 500


@app.route('/api/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    """标记所有通知为已读"""
    try:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-User-ID') or request.json.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少user_id参数'}), 400
        
        try:
            user_id = int(user_id)
        except:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE notifications 
                    SET is_read = 1 
                    WHERE user_id = %s AND is_read = 0
                """, (user_id,))
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': '所有通知已标记为已读'
                })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'标记所有通知已读失败：{str(e)}'}), 500


@app.route('/api/aigc/resources', methods=['GET'])
def get_aigc_resources():
    """根据资源ID列表获取资源详情（用于显示检索结果）"""
    try:
        ids_param = request.args.get('ids', '')
        if not ids_param:
            return jsonify({'success': False, 'message': '缺少ids参数'}), 400
        
        # 解析资源ID列表（逗号分隔）
        resource_ids = [int(id.strip()) for id in ids_param.split(',') if id.strip().isdigit()]
        if not resource_ids:
            return jsonify({'success': False, 'message': '无效的资源ID列表'}), 400
        
        from db_connection import get_user_db_connection
        from pymysql.cursors import DictCursor
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            resources = []
            with conn.cursor(DictCursor) as cursor:
                # 查询cultural_resources表
                placeholders = ','.join(['%s'] * len(resource_ids))
                cursor.execute(f"""
                    SELECT id, title, resource_type, content_feature_data, source_from, source_url
                    FROM cultural_resources
                    WHERE id IN ({placeholders})
                """, resource_ids)
                for row in cursor.fetchall():
                    content_data = {}
                    if row.get('content_feature_data'):
                        try:
                            content_data = json.loads(row['content_feature_data']) if isinstance(row['content_feature_data'], str) else row['content_feature_data']
                        except:
                            pass
                    
                    resources.append({
                        'id': row['id'],
                        'title': row.get('title', ''),
                        'entity_name': row.get('title', ''),
                        'description': content_data.get('text', '') if isinstance(content_data, dict) else '',
                        'content': content_data.get('text', '') if isinstance(content_data, dict) else '',
                        'table': 'cultural_resources',
                        'source': row.get('source_from', '')
                    })
                
                # 查询cultural_entities表
                cursor.execute(f"""
                    SELECT id, entity_name, description, source
                    FROM cultural_entities
                    WHERE id IN ({placeholders})
                """, resource_ids)
                for row in cursor.fetchall():
                    resources.append({
                        'id': row['id'],
                        'title': row.get('entity_name', ''),
                        'entity_name': row.get('entity_name', ''),
                        'description': row.get('description', ''),
                        'content': row.get('description', ''),
                        'table': 'cultural_entities',
                        'source': row.get('source', '')
                    })
                
                # 查询AIGC_cultural_entities表
                cursor.execute(f"""
                    SELECT id, entity_name, description
                    FROM AIGC_cultural_entities
                    WHERE id IN ({placeholders})
                """, resource_ids)
                for row in cursor.fetchall():
                    resources.append({
                        'id': row['id'],
                        'title': row.get('entity_name', ''),
                        'entity_name': row.get('entity_name', ''),
                        'description': row.get('description', ''),
                        'content': row.get('description', ''),
                        'table': 'AIGC_cultural_entities',
                        'source': 'AIGC生成'
                    })
            
            return jsonify({
                'success': True,
                'resources': resources
            })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取资源失败：{str(e)}'}), 500


@app.route('/api/comments/<int:comment_id>/resource-id', methods=['GET'])
def get_comment_resource_id(comment_id):
    """获取评论对应的资源ID"""
    try:
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT resource_id 
                    FROM user_comments 
                    WHERE id = %s
                """, (comment_id,))
                result = cursor.fetchone()
                
                if result:
                    return jsonify({
                        'success': True,
                        'resource_id': result['resource_id']
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': '评论不存在'
                    }), 404
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取评论资源ID失败：{str(e)}'}), 500


@app.route('/api/admin/dashboard/statistics', methods=['GET'])
def get_dashboard_statistics():
    """获取数据大屏统计信息（仅管理员和超级管理员可访问）"""
    try:
        # 从请求参数或请求头获取用户ID
        user_id = request.args.get('user_id') or request.headers.get('X-User-ID')
        
        if not user_id:
            return jsonify({'success': False, 'message': '未授权访问，请先登录'}), 401
        
        user_id = int(user_id)
        
        # 检查是否为管理员或超级管理员
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 从数据库users表读取role字段，检查是否为管理员或超级管理员
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_info = cursor.fetchone()
                if not user_info:
                    return jsonify({'success': False, 'message': '用户不存在'}), 404
                
                # 检查role字段是否为'管理员'或'超级管理员'
                role = user_info.get('role')
                if role != '管理员' and role != '超级管理员':
                    return jsonify({'success': False, 'message': '权限不足，仅管理员可访问'}), 403
                
                from datetime import datetime, timedelta, date
                import pytz
                
                # 获取当前时间（中国时区）
                tz = pytz.timezone('Asia/Shanghai')
                now = datetime.now(tz)
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # 1. 历史总访问人次（从user_access_logs表统计，每次进入网页就算一次访问）
                cursor.execute("""
                    SELECT COUNT(*) as total_users
                    FROM user_access_logs
                    WHERE access_type = 'page_view'
                """)
                result = cursor.fetchone()
                total_users = result.get('total_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_sessions表统计（统计会话数）
                if total_users == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as total_users
                        FROM qa_sessions
                    """)
                    result = cursor.fetchone()
                    total_users = result.get('total_users', 0) if result else 0
                
                # 2. 今日访问人次（从user_access_logs表统计，每次进入网页就算一次访问）
                cursor.execute("""
                    SELECT COUNT(*) as today_users
                    FROM user_access_logs
                    WHERE access_type = 'page_view' AND access_time >= %s
                """, (today_start,))
                result = cursor.fetchone()
                today_users = result.get('today_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_sessions表统计（统计今日会话数）
                if today_users == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as today_users
                        FROM qa_sessions
                        WHERE created_at >= %s
                    """, (today_start,))
                    result = cursor.fetchone()
                    today_users = result.get('today_users', 0) if result else 0
                
                # 3. 历史文字AIGC使用人次（每次和AI对话就算一次，从user_access_logs表统计）
                cursor.execute("""
                    SELECT COUNT(*) as total_text_users
                    FROM user_access_logs
                    WHERE access_type = 'aigc_text'
                """)
                result = cursor.fetchone()
                total_text_users = result.get('total_text_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计（统计用户消息数）
                if total_text_users == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as total_text_users
                        FROM qa_messages
                        WHERE model = 'text' AND user_message IS NOT NULL AND user_message != ''
                    """)
                    result = cursor.fetchone()
                    total_text_users = result.get('total_text_users', 0) if result else 0
                
                # 4. 今日文字AIGC使用人次（每次和AI对话就算一次，从user_access_logs表统计）
                cursor.execute("""
                    SELECT COUNT(*) as today_text_users
                    FROM user_access_logs
                    WHERE access_type = 'aigc_text' AND access_time >= %s
                """, (today_start,))
                result = cursor.fetchone()
                today_text_users = result.get('today_text_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计（统计今日用户消息数）
                if today_text_users == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as today_text_users
                        FROM qa_messages
                        WHERE model = 'text' AND create_time >= %s AND user_message IS NOT NULL AND user_message != ''
                    """, (today_start,))
                    result = cursor.fetchone()
                    today_text_users = result.get('today_text_users', 0) if result else 0
                
                # 5. 历史图片AIGC使用人次（每次和AI对话就算一次，从user_access_logs表统计）
                cursor.execute("""
                    SELECT COUNT(*) as total_image_users
                    FROM user_access_logs
                    WHERE access_type = 'aigc_image'
                """)
                result = cursor.fetchone()
                total_image_users = result.get('total_image_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计（统计用户消息数）
                if total_image_users == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as total_image_users
                        FROM qa_messages
                        WHERE model = 'image' AND user_message IS NOT NULL AND user_message != ''
                    """)
                    result = cursor.fetchone()
                    total_image_users = result.get('total_image_users', 0) if result else 0
                
                # 6. 今日图片AIGC使用人次（每次和AI对话就算一次，从user_access_logs表统计）
                cursor.execute("""
                    SELECT COUNT(*) as today_image_users
                    FROM user_access_logs
                    WHERE access_type = 'aigc_image' AND access_time >= %s
                """, (today_start,))
                result = cursor.fetchone()
                today_image_users = result.get('today_image_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计（统计今日用户消息数）
                if today_image_users == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as today_image_users
                        FROM qa_messages
                        WHERE model = 'image' AND create_time >= %s AND user_message IS NOT NULL AND user_message != ''
                    """, (today_start,))
                    result = cursor.fetchone()
                    today_image_users = result.get('today_image_users', 0) if result else 0
                
                # 7. 历史文字AIGC使用次数（一轮对话用户发了多少次需求就算多少次，统计qa_messages表中的用户消息数）
                cursor.execute("""
                    SELECT COUNT(*) as total_text_count
                    FROM qa_messages
                    WHERE model = 'text' AND user_message IS NOT NULL AND user_message != ''
                """)
                result = cursor.fetchone()
                total_text_count = result.get('total_text_count', 0) if result else 0
                
                # 8. 今日文字AIGC使用次数（一轮对话用户发了多少次需求就算多少次，统计qa_messages表中的用户消息数）
                cursor.execute("""
                    SELECT COUNT(*) as today_text_count
                    FROM qa_messages
                    WHERE model = 'text' AND create_time >= %s AND user_message IS NOT NULL AND user_message != ''
                """, (today_start,))
                result = cursor.fetchone()
                today_text_count = result.get('today_text_count', 0) if result else 0
                
                # 9. 历史图片AIGC使用次数（一轮对话用户发了多少次需求就算多少次，统计qa_messages表中的用户消息数）
                cursor.execute("""
                    SELECT COUNT(*) as total_image_count
                    FROM qa_messages
                    WHERE model = 'image' AND user_message IS NOT NULL AND user_message != ''
                """)
                result = cursor.fetchone()
                total_image_count = result.get('total_image_count', 0) if result else 0
                
                # 10. 今日图片AIGC使用次数（一轮对话用户发了多少次需求就算多少次，统计qa_messages表中的用户消息数）
                cursor.execute("""
                    SELECT COUNT(*) as today_image_count
                    FROM qa_messages
                    WHERE model = 'image' AND create_time >= %s AND user_message IS NOT NULL AND user_message != ''
                """, (today_start,))
                result = cursor.fetchone()
                today_image_count = result.get('today_image_count', 0) if result else 0
                
                # 11. 最近7天的使用趋势（按天统计）
                seven_days_ago = today_start - timedelta(days=6)
                
                # 统计每日访问次数（每次进入网页就算一次）
                cursor.execute("""
                    SELECT 
                        DATE(access_time) as date,
                        COUNT(*) as daily_users
                    FROM user_access_logs
                    WHERE access_type = 'page_view' AND access_time >= %s
                    GROUP BY DATE(access_time)
                    ORDER BY date ASC
                """, (seven_days_ago,))
                daily_visits_raw = cursor.fetchall()
                daily_visits = {}
                for row in daily_visits_raw:
                    date_val = row['date']
                    if isinstance(date_val, (datetime, date)):
                        date_str = date_val.strftime('%Y-%m-%d') if isinstance(date_val, datetime) else str(date_val)
                    else:
                        date_str = str(date_val)
                    daily_visits[date_str] = row['daily_users']
                
                # 统计每日文字AIGC使用次数（用户消息数，一轮对话用户发了多少次需求就算多少次）
                cursor.execute("""
                    SELECT 
                        DATE(create_time) as date,
                        COUNT(*) as text_count
                    FROM qa_messages
                    WHERE model = 'text' AND create_time >= %s 
                        AND user_message IS NOT NULL AND user_message != ''
                    GROUP BY DATE(create_time)
                    ORDER BY date ASC
                """, (seven_days_ago,))
                daily_text_raw = cursor.fetchall()
                daily_text = {}
                for row in daily_text_raw:
                    date_val = row['date']
                    if isinstance(date_val, (datetime, date)):
                        date_str = date_val.strftime('%Y-%m-%d') if isinstance(date_val, datetime) else str(date_val)
                    else:
                        date_str = str(date_val)
                    daily_text[date_str] = row['text_count']
                
                # 统计每日图片AIGC使用次数（用户消息数，一轮对话用户发了多少次需求就算多少次）
                cursor.execute("""
                    SELECT 
                        DATE(create_time) as date,
                        COUNT(*) as image_count
                    FROM qa_messages
                    WHERE model = 'image' AND create_time >= %s 
                        AND user_message IS NOT NULL AND user_message != ''
                    GROUP BY DATE(create_time)
                    ORDER BY date ASC
                """, (seven_days_ago,))
                daily_image_raw = cursor.fetchall()
                daily_image = {}
                for row in daily_image_raw:
                    date_val = row['date']
                    if isinstance(date_val, (datetime, date)):
                        date_str = date_val.strftime('%Y-%m-%d') if isinstance(date_val, datetime) else str(date_val)
                    else:
                        date_str = str(date_val)
                    daily_image[date_str] = row['image_count']
                
                # 生成完整的7天数据（从6天前到今天）
                complete_trend_data = []
                for i in range(7):
                    date_obj = (today_start - timedelta(days=6-i)).date()
                    date_str = date_obj.strftime('%Y-%m-%d')
                    
                    # 获取该日期的数据，如果没有则使用0
                    daily_users = daily_visits.get(date_str, 0)
                    text_count = daily_text.get(date_str, 0)
                    image_count = daily_image.get(date_str, 0)
                    
                    # 计算AIGC总使用次数（文字+图片）
                    total_aigc_count = text_count + image_count
                    
                    complete_trend_data.append({
                        'date': date_str,
                        'daily_users': daily_users,
                        'text_count': text_count,
                        'image_count': image_count,
                        'total_aigc_count': total_aigc_count
                    })
                
                return jsonify({
                    'success': True,
                    'data': {
                        'total_users': total_users,
                        'today_users': today_users,
                        'total_text_users': total_text_users,
                        'today_text_users': today_text_users,
                        'total_image_users': total_image_users,
                        'today_image_users': today_image_users,
                        'total_text_count': total_text_count,
                        'today_text_count': today_text_count,
                        'total_image_count': total_image_count,
                        'today_image_count': today_image_count,
                        'trend_data': complete_trend_data
                    }
                })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取统计信息失败：{str(e)}'}), 500


def auto_check_pending_annotations():
    """
    定时任务：每5分钟自动检测待标注任务并进行AI标注
    """
    uploader = ResourceUploader()
    
    while True:
        try:
            time.sleep(300)  # 等待5分钟（300秒）
            
            
            # 获取所有状态为"待标注"的任务
            from db_connection import get_user_db_connection
            conn = get_user_db_connection()
            if not conn:
                continue
            
            try:
                with conn.cursor() as cursor:
                    # 查询所有待标注的任务（仅限用户上传的资源）
                    cursor.execute("""
                        SELECT t.id, t.resource_id, t.resource_source
                        FROM annotation_tasks t
                        WHERE t.status = '待标注'
                        AND t.resource_source = 'cultural_resources_from_user'
                        ORDER BY t.created_at ASC
                    """)
                    
                    pending_tasks = cursor.fetchall()
                    
                    if pending_tasks:
                        
                        for task in pending_tasks:
                            task_id = task['id']
                            resource_id = task['resource_id']
                            resource_source = task['resource_source']
                            
                            try:
                                # 触发AI标注
                                uploader.trigger_ai_annotation(task_id)
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
            finally:
                if conn:
                    conn.close()
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            # 出错后继续运行，等待下次检查
            time.sleep(60)  # 出错后等待1分钟再继续

if __name__ == '__main__':
    # 使用7200端口作为后端服务端口（通过前端5173代理访问）
    backend_port = 7200
    
    
    # 启动定时任务线程（后台运行）
    timer_thread = threading.Thread(target=auto_check_pending_annotations, daemon=True)
    timer_thread.start()
    
    # 添加用户管理相关路由
    @app.route('/api/auth/users', methods=['GET'])
    def get_all_users():
        """获取所有用户列表（仅超级管理员可访问）"""
        try:
            user_id = request.args.get('userId')
            if not user_id:
                return jsonify({'success': False, 'message': '未授权访问，请先登录'}), 401
            
            user_id = int(user_id)
            
            # 检查用户权限（超级管理员）
            from db_connection import get_user_db_connection
            conn = get_user_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': '数据库连接失败'}), 500
            
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                    user_info = cursor.fetchone()
                    if not user_info:
                        return jsonify({'success': False, 'message': '用户不存在'}), 404
                    
                    # 检查role字段是否为'超级管理员'
                    role = user_info.get('role') if isinstance(user_info, dict) else user_info[0] if user_info else None
                    if role != '超级管理员':
                        return jsonify({'success': False, 'message': '权限不足，仅超级管理员可查看'}), 403
                    
                    # 获取所有用户，按在线状态、角色、账号排序
                    cursor.execute("""
                        SELECT id, account, nickname, signature, avatar_path, role,
                               COALESCE(is_online, 0) as is_online, last_active_time, created_at
                        FROM users
                        ORDER BY 
                            CASE WHEN COALESCE(is_online, 0) = 1 THEN 0 ELSE 1 END,
                            CASE WHEN role = '超级管理员' THEN 0
                                 WHEN role = '管理员' THEN 1
                                 ELSE 2 END,
                            account ASC
                    """)
                    users = cursor.fetchall()
                    
                    user_list = []
                    for user in users:
                        if isinstance(user, dict):
                            user_info_dict = {
                                'id': user.get('id'),
                                'account': user.get('account'),
                                'nickname': user.get('nickname'),
                                'signature': user.get('signature'),
                                'avatar_path': user.get('avatar_path'),
                                'role': user.get('role'),
                                'is_online': bool(user.get('is_online', 0)),
                                'last_active_time': user.get('last_active_time').isoformat() if user.get('last_active_time') else None,
                                'created_at': user.get('created_at').isoformat() if user.get('created_at') else None
                            }
                        else:
                            # 如果是元组格式，按顺序解析
                            user_info_dict = {
                                'id': user[0],
                                'account': user[1],
                                'nickname': user[2],
                                'signature': user[3],
                                'avatar_path': user[4],
                                'role': user[5],
                                'is_online': bool(user[6] if len(user) > 6 else 0),
                                'last_active_time': user[7].isoformat() if len(user) > 7 and user[7] else None,
                                'created_at': user[8].isoformat() if len(user) > 8 and user[8] else None
                            }
                        user_list.append(user_info_dict)
                    
                    return jsonify({'success': True, 'users': user_list})
            finally:
                conn.close()
        except ValueError:
            return jsonify({'success': False, 'message': '无效的用户ID'}), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500
    
    @app.route('/api/auth/switch-role', methods=['POST'])
    def switch_user_role():
        """切换用户角色（仅超级管理员可访问）"""
        try:
            data = request.json
            current_user_id = data.get('current_user_id')
            target_user_id = data.get('target_user_id')
            new_role = data.get('new_role')
            
            if not current_user_id or not target_user_id or not new_role:
                return jsonify({'success': False, 'message': '缺少必要参数'}), 400
            
            # 验证角色值
            if new_role not in ['普通用户', '管理员', '超级管理员']:
                return jsonify({'success': False, 'message': '无效的角色值'}), 400
            
            # 检查当前用户权限（超级管理员）
            from db_connection import get_user_db_connection
            conn = get_user_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': '数据库连接失败'}), 500
            
            try:
                with conn.cursor() as cursor:
                    # 检查当前用户是否为超级管理员
                    cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
                    current_user = cursor.fetchone()
                    if not current_user:
                        return jsonify({'success': False, 'message': '当前用户不存在'}), 404
                    
                    current_role = current_user.get('role') if isinstance(current_user, dict) else current_user[0] if current_user else None
                    if current_role != '超级管理员':
                        return jsonify({'success': False, 'message': '权限不足，仅超级管理员可操作'}), 403
                    
                    # 检查目标用户是否存在
                    cursor.execute("SELECT id, role FROM users WHERE id = %s", (target_user_id,))
                    target_user = cursor.fetchone()
                    if not target_user:
                        return jsonify({'success': False, 'message': '目标用户不存在'}), 404
                    
                    # 不能修改超级管理员的角色
                    target_role = target_user.get('role') if isinstance(target_user, dict) else target_user[1] if len(target_user) > 1 else None
                    if target_role == '超级管理员' and new_role != '超级管理员':
                        return jsonify({'success': False, 'message': '不能修改超级管理员的角色'}), 403
                    
                    # 更新用户角色
                    cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, target_user_id))
                    conn.commit()
                    
                    return jsonify({'success': True, 'message': '角色切换成功'})
            finally:
                conn.close()
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500
    
    @app.route('/api/aigc/edit-resource', methods=['POST'])
    def edit_resource():
        """编辑资源（二次创作）- 使用AI对话修改资源"""
        try:
            user_id = int(request.headers.get('X-User-Id', 0))
            if not user_id:
                return jsonify({'success': False, 'message': '缺少用户信息'}), 400
            
            data = request.json
            resource_id = data.get('resource_id')
            resource_type = data.get('resource_type')  # 'text' 或 'image'
            original_content = data.get('original_content')
            edit_request = data.get('edit_request')
            
            if not resource_id or not resource_type or not edit_request:
                return jsonify({'success': False, 'message': '缺少必要参数'}), 400
            
            # 获取用户的RAG系统
            rag_system = get_or_create_rag_system(user_id)
            if not rag_system:
                return jsonify({'success': False, 'message': 'RAG系统初始化失败'}), 500
            
            # 构建编辑提示词
            if resource_type == 'text':
                prompt = f"""
你是一位专业的文本编辑助手。请根据用户的要求修改以下文本内容。

原始文本：
{original_content}

用户要求：
{edit_request}

请直接返回修改后的文本内容，不要添加任何解释或说明。
"""
            else:  # image
                prompt = f"""
你是一位专业的图片描述编辑助手。请根据用户的要求修改以下图片描述。

原始描述：
{original_content}

用户要求：
{edit_request}

请直接返回修改后的描述内容，不要添加任何解释或说明。
"""
            
            # 调用AI模型进行编辑
            try:
                response = rag_system.model.invoke(prompt)
                edited_content = response.content if hasattr(response, 'content') else str(response)
                
                result = {
                    'success': True,
                    'message': '编辑成功',
                    'edited_content': edited_content
                }
                
                if resource_type == 'image':
                    result['edited_description'] = edited_content
                else:
                    result['edited_content'] = edited_content
                
                return jsonify(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'message': f'AI编辑失败: {str(e)}'}), 500
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'编辑失败: {str(e)}'}), 500
    
    @app.route('/api/aigc/save-edited-resource', methods=['POST'])
    def save_edited_resource():
        """保存编辑后的资源"""
        try:
            user_id = int(request.headers.get('X-User-Id', 0))
            if not user_id:
                return jsonify({'success': False, 'message': '缺少用户信息'}), 400
            
            data = request.json
            resource_id = data.get('resource_id')
            resource_type = data.get('resource_type')
            edited_content = data.get('edited_content')
            edited_image_url = data.get('edited_image_url')
            
            if not resource_id or not resource_type or not edited_content:
                return jsonify({'success': False, 'message': '缺少必要参数'}), 400
            
            # 这里应该保存到数据库，但由于是模拟数据，暂时只返回成功
            # 实际实现时，应该更新对应的资源表
            
            return jsonify({
                'success': True,
                'message': '保存成功'
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500
    
    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        """用户登出（更新在线状态）"""
        try:
            data = request.json
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'success': False, 'message': '缺少用户ID'}), 400
            
            from db_connection import get_user_db_connection
            conn = get_user_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': '数据库连接失败'}), 500
            
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE users 
                        SET is_online = 0, last_active_time = NOW() 
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    
                    return jsonify({'success': True, 'message': '登出成功'})
            finally:
                conn.close()
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500
    
    # 在启动前测试数据库连接
    print("\n[启动检查] 正在检查数据库连接...")
    try:
        test_conn = get_user_db_connection()
        if test_conn:
            print("[启动检查] [OK] 数据库连接成功")
            test_conn.close()
        else:
            print("[启动检查] [WARN] 数据库连接失败，但服务器将继续启动")
            print("[启动检查] 提示：请确保MySQL服务已启动，数据库配置正确")
    except Exception as e:
        print(f"[启动检查] [WARN] 数据库连接测试失败: {e}")
        print("[启动检查] 提示：服务器将继续启动，但某些功能可能无法使用")
    
    print(f"\n[启动] 正在启动服务器，监听端口: {backend_port}")
    print(f"[启动] 访问地址: http://localhost:{backend_port}")
    print(f"[启动] API文档: http://localhost:{backend_port}/api/")
    
    try:
        app.run(host='0.0.0.0', port=backend_port, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[停止] 服务器已停止（用户中断）")
    except Exception as e:
        print(f"\n[错误] 服务器启动失败: {e}")
        import traceback
        traceback.print_exc()
        print("\n[诊断] 可能的原因：")
        input("\n按Enter键退出...")

