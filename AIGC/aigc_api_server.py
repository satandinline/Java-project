"""
AIGC API服务器
提供文字AIGC和图片AIGC的后端接口

使用方法：
1. 安装依赖：pip install flask flask-cors
2. 运行：python aigc_api_server.py
3. 服务器将在 http://localhost:8000 启动（通过前端5173代理访问）
"""
import os
import sys
import json
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
from pydantic import SecretStr
from typing import Optional, Dict

# 添加项目根目录和当前目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

load_dotenv(override=True)

# 延迟导入RAG和ImageAIGC模块（避免启动时加载，提升启动速度）
# from RAG import CulturalResourceRAG
# from image_RAG import ImageAIGC
from aigc_db_helper import save_aigc_text_resource, save_aigc_image, extract_festival_names
# 导入父目录的模块
from login import AuthSystem
from upload_handler import ResourceUploader
from user_logging import UserLogging

# 导入统计API（延迟导入，避免循环依赖）
def register_statistics_api():
    """注册统计API蓝图"""
    from statistics_api import statistics_bp
    app.register_blueprint(statistics_bp)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 注册统计API蓝图
register_statistics_api()

# 配置静态文件服务
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 头像存储在项目根目录的 public 文件夹
public_dir = os.path.join(project_root, 'public')
os.makedirs(public_dir, exist_ok=True)

# 初始化认证系统
auth_system = AuthSystem()

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
            print("[搜索] 警告：未找到通义千问API密钥，搜索功能可能受限")
            return None
        
        print("[搜索] 正在初始化AI辅助检索系统...")
        tongyi_model = ChatTongyi(api_key=SecretStr(ALIYUN_API_KEY), model="qwen-turbo")
        search_rag_system = CulturalResourceRAG(model=tongyi_model, persist_directory="./chroma_db")
        print("[搜索] AI辅助检索系统初始化成功")
        return search_rag_system
    except Exception as e:
        print(f"[搜索] 初始化AI辅助检索系统失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_aigc_message_to_db(user_id: int, session_id: int, user_message: str, ai_message: str, 
                            model: str, image_url: Optional[str], image_from_users_url: Optional[str] = None, db_config: Dict = None):
    """保存AIGC消息到数据库，并记录访问日志（包括管理员）"""
    """保存AIGC消息到数据库（使用新表结构）"""
    try:
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            print(f"[API] 保存消息失败：数据库连接失败")
            return False
        
        try:
            with conn.cursor() as cursor:
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
                except:
                    has_new_structure = False
                    has_image_from_users_field = False
                
                if has_new_structure:
                    # 使用新表结构保存消息
                    if has_image_from_users_field:
                        cursor.execute("""
                            INSERT INTO qa_messages (user_id, session_id, user_message, ai_message, model, image_url, image_from_users_url)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (user_id, session_id, user_message, ai_message, model, image_url, image_from_users_url))
                    else:
                        cursor.execute("""
                            INSERT INTO qa_messages (user_id, session_id, user_message, ai_message, model, image_url)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (user_id, session_id, user_message, ai_message, model, image_url))
                    
                    # 记录访问日志（包括管理员）
                    access_type = 'aigc_text' if model == 'text' else 'aigc_image'
                    try:
                        cursor.execute("""
                            INSERT INTO user_access_logs 
                            (user_id, access_type, access_path, resource_id, resource_type)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (user_id, access_type, '/api/aigc/chat', session_id, 'aigc_session'))
                    except Exception as log_error:
                        print(f"[日志] 记录访问日志失败: {log_error}")
                        # 不影响主流程，继续执行
                    
                    conn.commit()
                    return True
                else:
                    # 兼容旧表结构
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
                    return True
        finally:
            conn.close()
    except Exception as e:
        print(f"[API] 保存消息到数据库失败: {e}")
        import traceback
        traceback.print_exc()
        return False

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
                print(f"[模型] ChatTongyi初始化失败: {e}")
                if OPENAI_API_KEY:
                    try:
                        return ChatOpenAI(model="gpt-3.5-turbo")
                    except Exception as e2:
                        print(f"[模型] ChatOpenAI初始化失败: {e2}")
        elif OPENAI_API_KEY:
            try:
                return ChatOpenAI(model="gpt-3.5-turbo")
            except Exception as e:
                print(f"[模型] ChatOpenAI初始化失败: {e}")
        return None
    except Exception as e:
        print(f"[模型] 获取文本模型失败: {e}")
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
        print(f"[RAG] 为用户 {user_id} 创建RAG系统成功")
        return rag_system
    except Exception as e:
        print(f"[RAG] 为用户 {user_id} 创建RAG系统失败: {e}")
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
        
        # 设置图片保存目录为项目根目录的AIGC_graph文件夹
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        print(f"[ImageAIGC] 为用户 {user_id} 创建ImageAIGC系统成功")
        return image_aigc_system
    except Exception as e:
        print(f"[ImageAIGC] 为用户 {user_id} 创建ImageAIGC系统失败: {e}")
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
                print(f"[multimodal_search] 保存上传图片失败: {e}")

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

        user_db_config = auth_system.get_user_db_config(user_id)
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
                    print(f"[multimodal_search] 读取图片信息失败: {e}")

        query_parts = []
        if query:
            query_parts.append(query)
        if image_descriptions:
            query_parts.append(" ".join(image_descriptions))
        final_query = " ".join(query_parts).strip()
        if not final_query:
            return jsonify({'success': False, 'message': '缺少查询内容或图片描述失败'}), 400

        vector_results = []
        if getattr(rag_system, "retriever", None):
            try:
                docs = rag_system._search_vector(final_query)
                for doc in docs[:6]:
                    vector_results.append({
                        "content": getattr(doc, "page_content", str(doc))[:500],
                        "metadata": getattr(doc, "metadata", {})
                    })
            except Exception as e:
                print(f"[multimodal_search] 向量检索失败: {e}")

        db_results = []
        try:
            db_results = rag_system.query_database(final_query)
        except Exception as e:
            print(f"[multimodal_search] 数据库检索失败: {e}")

        response = {
            "success": True,
            "query_used": final_query,
            "image_descriptions": image_descriptions,
            "vector_results": vector_results,
            "database_results": db_results
        }
        return jsonify(response)
    except Exception as e:
        import traceback
        print(f"[multimodal_search] 未处理异常: {e}")
        print(traceback.format_exc())
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
                    import os
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
        result = auth_system.register(
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
                    import os
                    import shutil
                    if os.path.exists(avatar_path):
                        public_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'FrontEnd', 'public')
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
                    print(f"[API] 处理头像失败: {e}")
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
                    print(f"[API] 更新头像路径失败: {e}")
        
        return jsonify(result)
    except Exception as e:
        print(f"[API] 注册失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'注册失败：{str(e)}'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录接口"""
    try:
        data = request.json
        account = data.get('account', '').strip()
        password = data.get('password', '').strip()
        
        if not account or not password:
            return jsonify({'success': False, 'message': '账号和密码不能为空'}), 400
        
        result = auth_system.login(account, password)
        
        # 记录登录日志
        if result.get('success') and result.get('user_info'):
            user_id = result['user_info'].get('id')
            if user_id:
                UserLogging.log_login(user_id, account)
        
        return jsonify(result)
    except Exception as e:
        print(f"[API] 登录失败: {e}")
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
        
        result = auth_system.update_nickname(user_id, nickname)
        
        # 如果修改成功，返回更新后的用户信息
        if result.get('success'):
            user_info = auth_system.get_user_by_id(user_id)
            if user_info:
                result['user_info'] = user_info
        
        return jsonify(result)
    except Exception as e:
        print(f"[API] 修改昵称失败: {e}")
        return jsonify({'success': False, 'message': f'修改昵称失败：{str(e)}'}), 500

@app.route('/api/auth/user', methods=['GET'])
def get_user():
    """获取当前用户信息（通过user_id参数）"""
    try:
        user_id = request.args.get('user_id', type=int)
        if not user_id:
            return jsonify({'success': False, 'message': '缺少user_id参数'}), 400
        
        user_info = auth_system.get_user_by_id(user_id)
        if user_info:
            # 不返回敏感信息（密码哈希、安全问题答案哈希）
            safe_user_info = {
                'id': user_info.get('id'),
                'account': user_info.get('account'),
                'nickname': user_info.get('nickname'),
                'avatar_path': user_info.get('avatar_path'),
                'role': user_info.get('role'),
                'security_question': user_info.get('security_question')
            }
            return jsonify({'success': True, 'user_info': safe_user_info})
        else:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
    except Exception as e:
        print(f"[API] 获取用户信息失败: {e}")
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
        
        result = auth_system.update_password(user_id, old_password, new_password)
        return jsonify(result)
    except Exception as e:
        print(f"[API] 修改密码失败: {e}")
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
        verify_result = auth_system.verify_security_question(user_id, security_answer)
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
        print(f"[API] 通过二级密码修改密码失败: {e}")
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
        print(f"[API] 验证安全问题答案失败: {e}")
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
        
        result = auth_system.update_security_question(user_id, question, answer)
        return jsonify(result)
    except Exception as e:
        print(f"[API] 更换安全问题失败: {e}")
        return jsonify({'success': False, 'message': f'更换失败：{str(e)}'}), 500

@app.route('/api/auth/forgot-password/question', methods=['POST'])
def get_security_question_for_reset():
    """获取用户的安全问题（用于重置密码）"""
    try:
        data = request.json
        account = data.get('account', '').strip()
        
        if not account:
            return jsonify({'success': False, 'message': '请输入账号'}), 400
        
        result = auth_system.get_security_question(account)
        return jsonify(result)
    except Exception as e:
        print(f"[API] 获取安全问题失败: {e}")
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
        
        result = auth_system.verify_security_answer(account, answer)
        return jsonify(result)
    except Exception as e:
        print(f"[API] 验证答案失败: {e}")
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
        result = auth_system.reset_password(account, new_password)
        return jsonify(result)
    except Exception as e:
        print(f"[API] 重置密码失败: {e}")
        return jsonify({'success': False, 'message': f'重置密码失败：{str(e)}'}), 500

@app.route('/api/auth/change-avatar', methods=['POST'])
def change_avatar():
    """更换头像接口"""
    try:
        user_id = request.headers.get('X-User-Id', type=int)
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        
        # 获取用户信息
        user_info = auth_system.get_user_by_id(user_id)
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
                        import os
                        old_filename = old_avatar_path.lstrip('/')
                        old_file_path = os.path.join(public_dir, old_filename)
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                            print(f"[API] 已删除旧头像: {old_file_path}")
                    except Exception as e:
                        print(f"[API] 删除旧头像失败: {e}")
                
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
            
            import os
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
                        print(f"[API] 已删除旧头像: {old_file_path}")
                except Exception as e:
                    print(f"[API] 删除旧头像失败: {e}")
            
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
                print(f"[API] 处理头像失败: {e}")
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
        print(f"[API] 更换头像失败: {e}")
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
            print(f"[日志] 记录访问日志失败: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    except Exception as e:
        print(f"[日志] 记录访问日志异常: {e}")


@app.route('/api/aigc/chat', methods=['POST'])
def aigc_chat():
    """处理AIGC聊天请求（支持流式输出）"""
    image_paths = []  # 在函数开始处初始化，确保finally中可用
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
                print(f"[API] 警告：无效的session_id: {session_id}")
                session_id = None
        else:
            session_id = None
        
        print(f"[API] 收到请求 - mode: {mode}, query: {query[:50] if query else '(空)'}..., stream: {stream}, session_id: {session_id}")
        
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
                # 创建image_from_users文件夹（与AIGC_graph同目录）
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                image_from_users_dir = os.path.join(base_dir, "image_from_users")
                os.makedirs(image_from_users_dir, exist_ok=True)
                
                for idx, file in enumerate(files):
                    if file.filename:
                        # 临时保存用于处理
                        temp_file_path = os.path.join(temp_dir, f"upload_{idx}_{file.filename}")
                        file.save(temp_file_path)
                        image_paths.append(temp_file_path)
                        
                        # 注意：此时user_id还未定义，需要先获取user_id后再保存图片
                        # 这里先保存到临时目录，稍后在获取user_id后再保存到image_from_users文件夹
            except Exception as e:
                print(f"保存上传图片失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 如果没有查询内容且没有图片，返回错误
        if not query and not image_paths:
            print("[API] 错误：查询内容和图片都为空")
            return jsonify({'error': '查询内容或图片不能同时为空', 'answer': '请输入查询内容或上传图片'}), 400
        
        # 获取用户ID（从请求头、表单数据或JSON数据）
        user_id = (request.headers.get('X-User-Id') or 
                   request.headers.get('X-User-ID') or 
                   request.form.get('user_id') or
                   (request.json.get('user_id') if request.is_json else None))
        if not user_id:
            print("[API] 错误：缺少用户ID")
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
        user_db_config = auth_system.get_user_db_config(user_id)
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
            import uuid
            
            # 创建image_from_users文件夹（与AIGC_graph同目录）
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            image_from_users_dir = os.path.join(base_dir, "image_from_users")
            os.makedirs(image_from_users_dir, exist_ok=True)
            
            # 保存每个上传的图片
            for temp_file_path in image_paths:
                try:
                    # 生成唯一文件名：时间戳_用户ID_随机UUID_原文件名
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    user_id_str = str(user_id)
                    unique_id = str(uuid.uuid4())[:8]
                    # 从临时文件路径获取原始文件名
                    original_filename = os.path.basename(temp_file_path)
                    if original_filename.startswith('upload_'):
                        # 提取原始文件名（去掉upload_前缀和索引）
                        parts = original_filename.split('_', 2)
                        if len(parts) >= 3:
                            original_filename = parts[2]
                    safe_filename = secure_filename(original_filename)
                    file_ext = os.path.splitext(safe_filename)[1] or '.jpg'
                    saved_filename = f"{timestamp}_{user_id_str}_{unique_id}{file_ext}"
                    saved_path = os.path.join(image_from_users_dir, saved_filename)
                    
                    # 复制文件到image_from_users文件夹
                    shutil.copy2(temp_file_path, saved_path)
                    
                    # 构建URL（相对路径）
                    image_url = f'/image_from_users/{saved_filename}'
                    user_uploaded_image_urls.append(image_url)
                    print(f"[API] 用户上传图片已保存: {saved_path} -> {image_url}")
                except Exception as e:
                    print(f"[API] 保存用户上传图片失败: {e}")
                    import traceback
                    traceback.print_exc()
        
        if mode == 'text':
            # 文字AIGC模式：使用RAG系统（Tongyi模型）
            rag_system = get_or_create_rag_system(user_id, db_config)
            if not rag_system:
                print("[API] 错误：RAG系统未初始化")
                return jsonify({
                    'error': 'RAG系统未初始化',
                    'answer': '抱歉，系统未正确配置，请检查API密钥设置。'
                }), 500
            
            try:
                # 处理图片理解：如果有图片，先理解图片内容
                image_descriptions = []
                if image_paths:
                    print(f"[API] 开始理解图片内容... (共{len(image_paths)}张)")
                    for img_path in image_paths:
                        try:
                            desc = rag_system._read_image_info(img_path)
                            if desc:
                                image_descriptions.append(desc)
                                print(f"[API] 图片描述: {desc[:100]}...")
                        except Exception as e:
                            print(f"[API] 读取图片信息失败: {e}")
                
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
                
                print(f"[API] 调用RAG系统（Tongyi）处理问题... (用户ID: {user_id})")
                print(f"[API] 最终查询: {final_query[:200]}...")
                
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
                    print(f"[API] 已保存AIGC生成的文字资源到数据库")
                except Exception as e:
                    print(f"[API] 保存AIGC文字资源失败: {e}")
                    # 不影响正常返回，继续执行
                
                # 保存消息到数据库（在返回前保存）
                if session_id:
                    try:
                        save_aigc_message_to_db(
                            user_id=user_id,
                            session_id=session_id,
                            user_message=final_query,
                            ai_message=answer,
                            model='text',
                            image_url=None,
                            db_config=db_config
                        )
                        # 记录文字AIGC使用日志
                        UserLogging.log_aigc_text(user_id, final_query)
                    except Exception as save_error:
                        print(f"[API] 保存消息失败: {save_error}")
                
                print(f"[API] RAG处理成功（Tongyi模型），返回答案长度: {len(answer)}")
                
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
                print(f"[API] RAG处理失败: {e}")
                print(f"[API] 错误堆栈: {error_trace}")
                
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
            image_aigc_system = get_or_create_image_aigc_system(user_id, db_config)
            if not image_aigc_system:
                error_msg = 'ImageAIGC系统未初始化，请检查API密钥设置'
                return jsonify({
                    'error': error_msg,
                    'answer': f'抱歉，{error_msg}。'
                }), 500
            
            try:
                # 处理图片理解：如果有图片，先理解图片内容
                image_descriptions = []
                if image_paths:
                    print(f"[API] 开始理解图片内容... (共{len(image_paths)}张)")
                    # 使用RAG系统来理解图片（如果有的话）
                    rag_system = get_or_create_rag_system(user_id, db_config)
                    if rag_system:
                        for img_path in image_paths:
                            try:
                                desc = rag_system._read_image_info(img_path)
                                if desc:
                                    image_descriptions.append(desc)
                                    print(f"[API] 图片描述: {desc[:100]}...")
                            except Exception as e:
                                print(f"[API] 读取图片信息失败: {e}")
                
                # 保存用户原始输入（用于保存到数据库）
                user_original_query = query if query else ""
                
                # 构建最终提示词
                final_prompt = query
                if image_descriptions:
                    image_context = "\n".join(image_descriptions)
                    if not final_prompt:
                        # 如果没有文字提示，先生成故事，再生成连环画
                        # 第一步：生成故事
                        story_prompt = f"请根据以下图片内容，创作一个像夸父逐日、嫦娥奔月这样具有辨识度的传统文化故事。图片内容：{image_context}"
                        print(f"[API] 第一步：生成故事...")
                        # 使用RAG系统生成故事
                        if rag_system:
                            story_result = rag_system.ask(
                                query=story_prompt,
                                image_paths=None,
                                use_history=False
                            )
                            story = story_result.get('answer', '')
                            if story:
                                # 第二步：根据故事生成连环画提示词
                                final_prompt = f"根据以下故事创作一组连环画，要求画面精美、以假乱真：{story}"
                                print(f"[API] 故事生成完成，长度: {len(story)}")
                    else:
                        # 如果有文字提示，将图片信息作为上下文
                        final_prompt = f"{query}\n\n图片信息：{image_context}"
                
                # 如果没有提示词且没有图片描述，使用默认提示
                if not final_prompt:
                    final_prompt = "请创作一组像夸父逐日、嫦娥奔月这样具有辨识度的传统文化连环画，要求画面精美、以假乱真"
                    # 如果用户没有输入，使用默认提示作为用户消息
                    if not user_original_query:
                        user_original_query = "（根据上传的图片自动生成）"
                
                # 从查询中提取风格（如果有）
                style = "传统节日风格"
                if "风格" in final_prompt or "style" in final_prompt.lower():
                    # 尝试提取风格信息
                    pass
                
                print(f"[API] 调用ImageAIGC系统（Huoshan）生成图片... (用户ID: {user_id})")
                print(f"[API] 最终提示词: {final_prompt[:200]}...")
                
                # 生成图片
                image_path = image_aigc_system.generate_image(
                    prompt=final_prompt,
                    style=style,
                    image_paths=image_paths if image_paths else None,
                    use_history=True
                )
                
                if image_path:
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
                        print(f"[API] 已保存AIGC生成的图片到数据库")
                    except Exception as e:
                        print(f"[API] 保存AIGC图片失败: {e}")
                        # 不影响正常返回，继续执行
                    
                    # 构建图片URL（相对路径）
                    # image_path可能是绝对路径（如：D:\git\mygit\Java-project\AIGC_graph\0001.jpeg）
                    # 需要转换为相对路径（如：/AIGC_graph/0001.jpeg）
                    import os
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    aigc_graph_dir = os.path.join(base_dir, "AIGC_graph")
                    
                    # 如果image_path是绝对路径且包含AIGC_graph目录
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
                    
                    print(f"[API] 图片路径转换: {image_path} -> {image_url}")
                    
                    # 保存消息到数据库（在返回前保存）
                    # 使用用户原始输入作为user_message，而不是处理后的final_prompt
                    # 将用户上传的图片URL列表转换为JSON字符串存储
                    image_from_users_url_json = json.dumps(user_uploaded_image_urls, ensure_ascii=False) if user_uploaded_image_urls else None
                    if session_id:
                        try:
                            save_aigc_message_to_db(
                                user_id=user_id,
                                session_id=session_id,
                                user_message=user_original_query if user_original_query else "（根据上传的图片自动生成）",
                                ai_message=f'图片生成成功！\n提示词：{final_prompt}',
                                model='image',
                                image_url=image_url,
                                image_from_users_url=image_from_users_url_json,
                                db_config=db_config
                            )
                            # 记录图片AIGC使用日志
                            UserLogging.log_aigc_image(user_id, final_prompt)
                        except Exception as save_error:
                            print(f"[API] 保存消息失败: {save_error}")
                    
                    print(f"[API] 图片生成成功（Huoshan模型），图片路径: {image_url}")
                    
                    # 非流式输出（普通模式）
                    return jsonify({
                        'answer': f'图片生成成功！\n提示词：{final_prompt}',
                        'image_path': image_url,
                        'model': 'image'  # 明确返回model类型，用于前端显示AI昵称
                    })
                else:
                    error_msg = '图片生成失败，请稍后重试'
                    return jsonify({
                        'error': '图片生成失败',
                        'answer': f'抱歉，{error_msg}。'
                    }), 500
                    
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"图片生成失败: {e}")
                print(f"错误堆栈: {error_trace}")
                error_msg = str(e)
                
                return jsonify({
                    'error': error_msg,
                    'answer': f'图片生成失败：{error_msg}'
                }), 500
        else:
            return jsonify({'error': f'不支持的模式：{mode}'}), 400
            
    except Exception as e:
        import traceback
        print(f"[API] 处理错误: {e}")
        print(f"[API] 错误堆栈: {traceback.format_exc()}")
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
        
        print(f"[API] 提取主题请求，对话长度: {len(conversation)}")
        
        if not conversation:
            return jsonify({'title': '新对话'}), 200
        
        # 获取用户的RAG系统（如果没有user_id，使用第一个可用的系统）
        rag_system = None
        if user_id:
            try:
                user_id = int(user_id)
                user_db_config = auth_system.get_user_db_config(user_id)
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
                
                print(f"[API] 调用模型提取主题...")
                # 直接使用RAG系统的模型调用方法
                response = rag_system._call_model(prompt)
                print(f"[API] 模型返回: {response[:50]}...")
                
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
                        import json
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
                
                print(f"[API] 提取的主题: {title}")
                return jsonify({'title': title})
                
            except Exception as e:
                import traceback
                print(f"[API] AI提取主题失败: {e}")
                print(f"[API] 错误堆栈: {traceback.format_exc()}")
                # 继续执行降级方案
        
        # 降级方案：从对话中提取关键词
        print(f"[API] 使用降级方案提取主题")
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
        print(f"[API] 提取主题失败: {e}")
        print(f"[API] 错误堆栈: {traceback.format_exc()}")
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
        
        # 验证文件类型
        file_name = file.filename
        file_extension = file_name.split('.')[-1].lower() if '.' in file_name else ''
        
        # 图片文件扩展名
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg']
        # 文本文件扩展名
        text_extensions = ['txt', 'md', 'doc', 'docx', 'pdf']
        
        is_image = file_extension in image_extensions
        is_text = file_extension in text_extensions
        
        if not is_image and not is_text:
            return jsonify({
                'success': False,
                'message': f'不支持的文件类型：{file_extension}。仅支持图片（{", ".join(image_extensions)}）或文本（{", ".join(text_extensions)}）文件'
            }), 400
        
        # 验证资源类型与文件类型是否匹配
        if resource_type == '图像' and not is_image:
            return jsonify({
                'success': False,
                'message': f'资源类型为"图像"，但文件类型（{file_extension}）不是图片格式'
            }), 400
        
        if resource_type == '文本' and not is_text:
            return jsonify({
                'success': False,
                'message': f'资源类型为"文本"，但文件类型（{file_extension}）不是文本格式'
            }), 400
        
        # 获取用户的数据库配置
        user_db_config = auth_system.get_user_db_config(user_id)
        if not user_db_config:
            return jsonify({
                'success': False,
                'message': '用户不存在'
            }), 401
        
        db_config = user_db_config['db_config']
        
        # 创建上传器并处理上传
        uploader = ResourceUploader(user_id=user_id, db_config=db_config)
        
        # 读取文件数据
        file_data = file.read()
        file_name = file.filename
        
        # 调用上传方法
        result = uploader.upload_resource(
            user_id=user_id,
            file_data=file_data,
            file_name=file_name,
            resource_type=resource_type
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        import traceback
        print(f"[API] 上传资源失败: {e}")
        print(f"[API] 错误堆栈: {traceback.format_exc()}")
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
    print(f"[API] 收到获取首页资源请求: page={request.args.get('page', 1)}, page_size={request.args.get('page_size', 8)}")
    try:
        import re
        import json
        import os
        
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 8))
        
        # 获取数据库连接（使用默认配置）
        from db_connection import get_user_db_connection
        conn = None
        try:
            print("[API] 正在连接数据库...")
            conn = get_user_db_connection()
            if not conn:
                print("[API] 获取首页资源失败：数据库连接返回None")
                return jsonify({'success': False, 'message': '数据库连接失败，请检查数据库配置和连接状态'}), 500
            print("[API] 数据库连接成功")
        except Exception as db_error:
            print(f"[API] 获取首页资源失败：数据库连接异常: {db_error}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'数据库连接异常：{str(db_error)}'}), 500
        
        try:
            with conn.cursor() as cursor:
                resources = []
                
                # 1. 从crawled_images表获取图片资源，按节日分组，每个节日只取第一张图片
                # 首先获取所有图片，按节日名称分组
                cursor.execute("""
                    SELECT id, file_name, storage_path, tags, dimensions, crawl_time, 
                           resource_id, entity_id, festival_name
                    FROM crawled_images
                    ORDER BY crawl_time DESC
                """)
                
                all_images = cursor.fetchall()
                
                # 按节日名称分组，每个节日只保留第一张图片（基准图片，文件名格式为 数字.扩展名）
                festival_images = {}  # {festival_name: first_image}
                seen_festivals = set()
                
                for img in all_images:
                    # 从tags字段提取节日名称
                    festival_name = None
                    entity_name = ""
                    description = ""
                    
                    if img.get('tags'):
                        try:
                            tags_data = json.loads(img['tags']) if isinstance(img['tags'], str) else img['tags']
                            if isinstance(tags_data, list) and tags_data:
                                # tags的第一个元素通常是节日名称
                                for tag in tags_data:
                                    if isinstance(tag, str):
                                        # 匹配第一个汉字到下一个非汉字之前的内容作为节日名称
                                        match = re.search(r'([\u4e00-\u9fa5]+)', tag)
                                        if match:
                                            festival_name = match.group(1)
                                            entity_name = festival_name
                                            # 提取描述
                                            desc_match = re.search(r'([\u4e00-\u9fa5]+[^\u4e00-\u9fa5]*)', tag)
                                            if desc_match:
                                                description = desc_match.group(1).strip()[:100]
                                            else:
                                                description = tag[:100] if len(tag) > 100 else tag
                                            break
                        except Exception as e:
                            print(f"解析tags失败: {e}")
                            pass
                    
                    # 如果tags中没有找到节日名称，尝试从文件名推断
                    if not festival_name and img.get('file_name'):
                        file_name = img['file_name']
                        # 检查文件名格式：如果是 "8.jpg" 格式，说明是基准图片
                        # 如果是 "8-1.jpg" 格式，提取基准序号 "8"
                        base_match = re.match(r'^(\d+)(?:-\d+)?\.', file_name)
                        if base_match:
                            base_index = base_match.group(1)
                            # 如果文件名是 "8.jpg" 格式（没有 -1），说明是基准图片
                            if not re.match(r'^\d+-\d+\.', file_name):
                                # 这是基准图片，但如果没有节日名称，使用文件名作为标识
                                if not festival_name:
                                    festival_name = f"资源_{base_index}"
                                    entity_name = festival_name
                    
                    # 如果还是没有节日名称，跳过
                    if not festival_name:
                        continue
                    
                    # 检查文件名格式：只选择基准图片（格式为 数字.扩展名，不是 数字-数字.扩展名）
                    file_name = img.get('file_name', '')
                    is_base_image = bool(re.match(r'^\d+\.', file_name))
                    
                    # 每个节日只保留第一张基准图片
                    if is_base_image and festival_name not in seen_festivals:
                        seen_festivals.add(festival_name)
                        festival_images[festival_name] = img
                
                # 转换为列表并按时间排序
                festival_list = list(festival_images.values())
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
                    festival_name = img.get('festival_name')
                    
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
                            print(f"解析tags失败: {e}")
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
                
                # 如果节日资源不足，补充统计cultural_entities
                if total < page_size:
                    cursor.execute("SELECT COUNT(*) as total FROM cultural_entities")
                    total_entities_result = cursor.fetchone()
                    total_entities = total_entities_result['total'] if total_entities_result else 0
                    total = max(total, total_entities)
                
                print(f"[API] 成功获取资源: {len(resources)} 条记录")
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
        print(f"[API] 获取首页资源失败: {e}")
        import traceback
        error_trace = traceback.format_exc()
        print(f"[API] 错误堆栈:\n{error_trace}")
        return jsonify({
            'success': False,
            'message': f'获取资源失败：{str(e)}',
            'error_type': type(e).__name__
        }), 500


@app.route('/api/resource/detail', methods=['GET'])
def get_resource_detail():
    """获取资源详情（某个节日的所有图片）"""
    festival_name = request.args.get('festival_name')
    if not festival_name:
        return jsonify({'success': False, 'message': '缺少festival_name参数'}), 400
    
    print(f"[API] 收到获取资源详情请求: festival_name={festival_name}")
    try:
        import json
        import os
        import re
        
        # 获取数据库连接
        from db_connection import get_user_db_connection
        conn = None
        try:
            conn = get_user_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        except Exception as db_error:
            print(f"[API] 数据库连接异常: {db_error}")
            return jsonify({'success': False, 'message': f'数据库连接异常：{str(db_error)}'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 查找该节日的所有图片（通过tags字段匹配节日名称）
                cursor.execute("""
                    SELECT id, file_name, storage_path, tags, dimensions, crawl_time
                    FROM crawled_images
                    WHERE tags LIKE %s
                    ORDER BY 
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
                """, (f'%{festival_name}%',))
                
                images = cursor.fetchall()
                
                # 即使没有图片，也尝试从cultural_entities表获取资源信息
                if not images:
                    # 尝试从cultural_entities表获取资源信息
                    cursor.execute("""
                        SELECT entity_name, description, entity_type, cultural_value
                        FROM cultural_entities
                        WHERE entity_name LIKE %s
                        LIMIT 1
                    """, (f'%{festival_name}%',))
                    entity_info = cursor.fetchone()
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
                            'entity_name': entity_info.get('entity_name', festival_name),
                            'description': entity_info.get('description', '') or '暂无简介',
                            'images': [default_image],
                            'total_images': 1
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'message': f'未找到节日"{festival_name}"的资源'
                        }), 404
                
                # 先尝试从cultural_entities表获取资源信息和描述（优先获取）
                entity_name = festival_name
                description = ""
                cursor.execute("""
                    SELECT entity_name, description, entity_type, cultural_value
                    FROM cultural_entities
                    WHERE entity_name LIKE %s
                    LIMIT 1
                """, (f'%{festival_name}%',))
                entity_info = cursor.fetchone()
                if entity_info:
                    entity_name = entity_info.get('entity_name', festival_name)
                    description = entity_info.get('description', '') or ''
                    if description:
                        description = description[:500]  # 限制长度但保留更多内容
                
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
                            print(f"解析tags失败: {e}")
                            pass
                    
                    image_list.append({
                        'id': img['id'],
                        'file_name': file_name,
                        'image_url': image_url,
                        'dimensions': img.get('dimensions'),
                        'crawl_time': str(img.get('crawl_time', '')) if img.get('crawl_time') else None
                    })
                
                print(f"[API] 成功获取资源详情: {festival_name}, 共 {len(image_list)} 张图片")
                print(f"[API] 资源描述长度: {len(description) if description else 0} 字符")
                return jsonify({
                    'success': True,
                    'festival_name': festival_name,
                    'entity_name': entity_name,
                    'description': description or '暂无简介',
                    'images': image_list,
                    'total_images': len(image_list)
                })
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    except Exception as e:
        print(f"[API] 获取资源详情失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取资源详情失败：{str(e)}'}), 500

@app.route('/api/search', methods=['GET'])
def search_resources():
    """全文检索接口（集成自search_service.py）"""
    keyword = request.args.get('q', '').strip()
    user_id = request.args.get('user_id', None)
    
    if not keyword:
        return jsonify({"code": 400, "msg": "请输入搜索关键词", "data": []})
    
    # 初始化搜索RAG系统
    rag_system = init_search_rag_system()
    if not rag_system:
        return jsonify({"code": 500, "msg": "搜索系统初始化失败，请检查API密钥配置", "data": []})
    
    # 获取数据库连接
    from db_connection import get_default_db_connection
    conn = get_default_db_connection()
    if not conn:
        return jsonify({"code": 500, "msg": "数据库连接失败", "data": []})
    
    # AI语义提取提示模板
    semantic_extraction_prompt = """
你是一位专业的文化资源检索专家，请将用户的自然语言查询转换为精确的检索关键词和实体类型。

用户查询: {query}

请按照以下JSON格式返回结果：
{{
  "keywords": ["关键词1", "关键词2", ...],  # 提取的核心关键词
  "entities": [{{"name": "实体名称", "type": "实体类型"}}],  # 提取的实体及其类型
  "advanced_query": "优化后的检索式"  # 适合数据库检索的高级检索式
}}

实体类型包括：节日、习俗、人物、作品、事件、地点等。
"""
    
    try:
        # ------------------------
        # 1. AI语义提取构建高级检索式
        # ------------------------
        print(f"[搜索] 正在进行AI语义分析: {keyword}")
        extraction_result = rag_system.model.invoke(
            semantic_extraction_prompt.format(query=keyword)
        ).content
        
        # 解析AI返回的结果
        try:
            ai_analysis = json.loads(extraction_result)
            advanced_query = ai_analysis.get("advanced_query", keyword)
            keywords = ai_analysis.get("keywords", [keyword])
            print(f"[搜索] AI分析结果 - 关键词: {keywords}, 高级检索式: {advanced_query}")
        except:
            # 如果解析失败，使用原始关键词
            advanced_query = keyword
            keywords = [keyword]
            ai_analysis = {"keywords": keywords, "advanced_query": advanced_query}
            print(f"[搜索] AI分析失败，使用原始关键词: {keyword}")
        
        with conn.cursor() as cursor:
            # ------------------------
            # 2. 增强的检索查询
            # ------------------------
            sql = """
                (SELECT 
                    id, 
                    entity_name as title, 
                    description, 
                    related_images_url as image_url,
                    source,
                    '传统实体' as type_tag,
                    MATCH(entity_name, description) AGAINST(%s IN NATURAL LANGUAGE MODE) as relevance_score,
                    1 as type_weight  -- 传统实体权重更高
                FROM cultural_entities 
                WHERE MATCH(entity_name, description) 
                AGAINST(%s IN NATURAL LANGUAGE MODE)
                LIMIT 25)
                
                UNION ALL
                
                (SELECT 
                    id, 
                    entity_name as title, 
                    description, 
                    related_images_url as image_url,
                    'AIGC生成' as source,
                    'AI实体' as type_tag,
                    MATCH(entity_name, description) AGAINST(%s IN NATURAL LANGUAGE MODE) as relevance_score,
                    0.5 as type_weight  -- AI生成实体权重较低
                FROM AIGC_cultural_entities 
                WHERE MATCH(entity_name, description) 
                AGAINST(%s IN NATURAL LANGUAGE MODE)
                LIMIT 25);
            """
            
            print(f"[搜索] 正在双表检索，查询词: {advanced_query}")
            try:
                cursor.execute(sql, (advanced_query, advanced_query, advanced_query, advanced_query))
                results = cursor.fetchall()
            except Exception as e:
                # FULLTEXT 索引缺失时的回退：使用 LIKE
                err_code = getattr(e, "args", [None])[0]
                if err_code == 1191:  # Can't find FULLTEXT index matching the column list
                    print("[搜索] 未找到 FULLTEXT 索引，使用 LIKE 回退查询")
                    like_q = f"%{advanced_query}%"
                    fallback_sql = """
                        (SELECT 
                            id, 
                            entity_name as title, 
                            description, 
                            related_images_url as image_url,
                            source,
                            '传统实体' as type_tag,
                            0.6 as relevance_score,
                            1 as type_weight
                        FROM cultural_entities 
                        WHERE entity_name LIKE %s OR description LIKE %s
                        LIMIT 25)
                        
                        UNION ALL
                        
                        (SELECT 
                            id, 
                            entity_name as title, 
                            description, 
                            related_images_url as image_url,
                            'AIGC生成' as source,
                            'AI实体' as type_tag,
                            0.4 as relevance_score,
                            0.5 as type_weight
                        FROM AIGC_cultural_entities 
                        WHERE entity_name LIKE %s OR description LIKE %s
                        LIMIT 25);
                    """
                    cursor.execute(fallback_sql, (like_q, like_q, like_q, like_q))
                    results = cursor.fetchall()
                else:
                    raise
            
            # ------------------------
            # 3. 检索结果排序
            # ------------------------
            def sort_key(result):
                # 综合排序：相关性得分 * 类型权重
                relevance = result.get('relevance_score', 0)
                type_weight = result.get('type_weight', 0.5)
                return -(relevance * type_weight)
            
            # 按综合得分排序
            sorted_results = sorted(results, key=sort_key)
            
            formatted_list = []
            
            for row in sorted_results:
                # 提取描述摘要
                desc = row.get('description', '')
                if desc:
                    snippet = desc[:100] + '...'
                else:
                    snippet = '暂无详细描述'
                
                # 提取图片
                img = row.get('image_url')
                if not img or img == 'null':
                    img = None
                
                # 组装数据
                formatted_list.append({
                    "id": row['id'],
                    "title": row['title'],
                    "snippet": snippet,
                    "tags": [row['type_tag']], 
                    "source_url": row.get('source', '#'),
                    "image_url": img,
                    "relevance_score": row.get('relevance_score', 0)  # 返回相关性得分
                })
            
            return jsonify({
                "code": 200,
                "msg": "success",
                "data": formatted_list,
                "ai_analysis": ai_analysis  # 返回AI分析结果，供前端展示
            })
    
    except Exception as e:
        print(f"[搜索] 搜索错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "msg": str(e), "data": []})
        
    finally:
        if conn:
            conn.close()


@app.route('/api/ai_search', methods=['GET'])
def ai_search():
    """
    AI 检索接口：使用阿里云通义模型对用户问题进行语义分析，并结合向量检索的参考资料给出答案。
    - 依赖环境变量 DASHSCOPE_API_KEY 或 ALIYUN_API_KEY
    - 返回结构：data 为参考列表，ai_analysis 为 LLM 生成的回答和建议
    """
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return jsonify({"code": 400, "msg": "请输入搜索关键词", "data": []})

    rag_system = init_search_rag_system()
    if not rag_system:
        return jsonify({"code": 500, "msg": "AI 检索初始化失败，请检查阿里云 API Key 配置", "data": []})

    # 1) 向量检索参考资料
    docs = []
    try:
        docs = rag_system._call_retriever(keyword) or []
    except Exception as e:
        print(f"[AI检索] 向量检索失败: {e}")
        docs = []

    def safe_content(text: str, limit: int = 600):
        text = text or ""
        return text[:limit] + ("..." if len(text) > limit else "")

    # 2) 组织上下文
    context_blocks = []
    for idx, doc in enumerate(docs[:5]):
        meta = getattr(doc, "metadata", {}) or {}
        title = meta.get("title") or meta.get("entity_name") or f"资料{idx+1}"
        content = getattr(doc, "page_content", "") or ""
        context_blocks.append(f"[{idx+1}] 标题：{title}\n内容：{safe_content(content)}")
    context_text = "\n\n".join(context_blocks) if context_blocks else "（无可用参考资料）"

    # 3) 调用阿里云通义模型生成回答
    prompt = f"""
你是一个文化资源 AI 检索助手。请结合【用户问题】和【参考资料】给出简明回答，并返回 JSON：
{{
  "answer": "面向用户的简洁回答",
  "suggestions": ["可执行建议1", "可执行建议2"],
  "used_sources": ["参考1", "参考2"]
}}

【用户问题】：
{keyword}

【参考资料】：
{context_text}
    """
    ai_analysis = {}
    try:
        resp_text = rag_system._call_model(prompt)
        ai_analysis = json.loads(resp_text) if resp_text else {}
    except Exception as e:
        print(f"[AI检索] 调用阿里云模型失败: {e}")
        ai_analysis = {"answer": "AI 检索暂时不可用，请稍后重试。", "suggestions": [], "used_sources": []}

    # 4) 构造返回的参考列表（用于前端列表展示）
    results = []
    for idx, doc in enumerate(docs):
        meta = getattr(doc, "metadata", {}) or {}
        title = meta.get("title") or meta.get("entity_name") or f"AI参考{idx+1}"
        content = getattr(doc, "page_content", "") or ""
        results.append({
            "id": idx + 1,
            "title": title,
            "entity_name": title,
            "description": safe_content(content, 200),
            "snippet": safe_content(content, 200),
            "image_url": meta.get("image_url"),
            "source_url": meta.get("source") or meta.get("url") or "#",
            "tags": ["AI检索"]
        })

    return jsonify({
        "code": 200,
        "msg": "success",
        "data": results,
        "ai_analysis": ai_analysis
    })

@app.route('/api/images/crawled/<path:filename>')
def serve_crawled_image(filename):
    """提供crawled_images文件夹中的图片"""
    try:
        from flask import send_from_directory
        import os
        import urllib.parse
        
        # URL解码文件名（处理中文文件名）
        filename = urllib.parse.unquote(filename)
        
        # 获取项目根目录
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
            print(f"[API] 图片文件不存在: {safe_path}，返回default图片")
            default_image_path = os.path.join(base_dir, "public", "default.jpg")
            if os.path.exists(default_image_path):
                return send_from_directory(os.path.join(base_dir, "public"), "default.jpg")
            else:
                # 如果default.jpg也不存在，返回404
                return jsonify({'error': 'Image not found'}), 404
        
        # 文件存在，返回图片
        return send_from_directory(image_dir, os.path.basename(safe_path))
    except Exception as e:
        print(f"[API] 提供图片失败: {e}")
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
            with conn.cursor() as cursor:
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
                    cursor.execute("""
                        SELECT COUNT(*) as message_count
                        FROM qa_messages
                        WHERE session_id = %s
                    """, (session['id'],))
                    msg_count = cursor.fetchone()
                    sessions_with_messages.append({
                        'id': session['id'],
                        'user_id': session['user_id'],
                        'created_at': session['created_at'].isoformat() if session['created_at'] else None,
                        'summary': session['summary'],
                        'mode': session.get('mode', 'text'),  # 确保mode字段正确返回
                        'message_count': msg_count['message_count'] if msg_count else 0
                    })
                
                return jsonify({
                    'success': True,
                    'sessions': sessions_with_messages
                })
        finally:
            conn.close()
    except Exception as e:
        print(f"[API] 获取会话列表失败: {e}")
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
                    print(f"[API] 检查/添加mode字段失败: {e}")
                
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
        print(f"[API] 创建会话失败: {e}")
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
                    
                    # 使用新表结构
                    if has_image_from_users_field:
                        cursor.execute("""
                            SELECT id, user_id, session_id, create_time, user_message, ai_message, 
                                   user_feedback, timestamp, model, image_url, image_from_users_url
                            FROM qa_messages
                            WHERE session_id = %s
                            ORDER BY create_time ASC
                        """, (session_id,))
                    else:
                        cursor.execute("""
                            SELECT id, user_id, session_id, create_time, user_message, ai_message, 
                                   user_feedback, timestamp, model, image_url
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
                            formatted_messages.append({
                                'id': msg['id'],
                                'role': 'assistant',
                                'content': msg['ai_message'],
                                'timestamp': msg['create_time'].isoformat() if msg['create_time'] else (msg['timestamp'].isoformat() if msg['timestamp'] else None),
                                'image_path': msg['image_url'] if msg['image_url'] else None,  # 确保image_url正确传递
                                'model': model_type,  # 确保model字段正确传递
                                'retrieved_resources': None,
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
        print(f"[API] 获取消息列表失败: {e}")
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
                            import json
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
        print(f"[API] 保存消息失败: {e}")
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
        print(f"[API] 删除会话失败: {e}")
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
                valid_ids = [s['id'] for s in valid_sessions]
                
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
        print(f"[API] 批量删除会话失败: {e}")
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
        print(f"[API] 删除所有会话失败: {e}")
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
        print(f"[API] 更新会话摘要失败: {e}")
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
        
        # 获取状态过滤参数
        status = request.args.get('status', '')
        
        # 创建ResourceUploader实例来获取任务
        user_db_config = auth_system.get_user_db_config(user_id)
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
        print(f"[API] 获取标注任务失败: {e}")
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
                # 获取任务信息
                cursor.execute("""
                    SELECT t.id, t.resource_id, t.resource_source, t.status,
                           cru.content_feature_data, cru.title
                    FROM annotation_tasks t
                    LEFT JOIN cultural_resources_from_user cru 
                        ON t.resource_id = cru.id 
                        AND t.resource_source = 'cultural_resources_from_user'
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
                
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'resource_id': task['resource_id'],
                    'title': task['title'],
                    'status': task['status'],
                    'resource_content': content_data.get('content_preview', ''),
                    'annotations': annotations
                })
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[API] 获取标注详情失败: {e}")
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
        from login import AuthSystem
        
        auth_system = AuthSystem()
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
        print(f"[API] 更新标注失败: {e}")
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


# 提供image_from_users文件夹中的图片
@app.route('/image_from_users/<path:filename>', methods=['GET'])
def serve_user_uploaded_image(filename):
    """提供image_from_users文件夹中的用户上传图片"""
    from flask import send_from_directory
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        image_dir = os.path.join(base_dir, "image_from_users")
        
        print(f"[API] 请求用户上传图片: {filename}")
        print(f"[API] image_from_users目录: {image_dir}")
        print(f"[API] 目录是否存在: {os.path.exists(image_dir)}")
        
        # 确保文件路径安全（防止路径遍历攻击）
        safe_path = os.path.normpath(os.path.join(image_dir, filename))
        if not safe_path.startswith(os.path.normpath(image_dir)):
            print(f"[API] 路径不安全: {safe_path}")
            return jsonify({'error': 'Invalid path'}), 403
        
        print(f"[API] 完整文件路径: {safe_path}")
        print(f"[API] 文件是否存在: {os.path.exists(safe_path)}")
        
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            print(f"[API] 成功提供用户上传图片: {filename}")
            return send_from_directory(image_dir, os.path.basename(safe_path))
        else:
            # 列出目录中的文件，用于调试
            if os.path.exists(image_dir):
                files = os.listdir(image_dir)
                print(f"[API] image_from_users目录中的文件: {files[:10]}")  # 只显示前10个
            print(f"[API] 文件不存在: {safe_path}")
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        import traceback
        print(f"[API] 提供用户上传图片失败: {e}")
        print(f"[API] 错误堆栈: {traceback.format_exc()}")
        return jsonify({'error': 'File not found'}), 404

# 提供AIGC_graph文件夹中的图片
@app.route('/AIGC_graph/<path:filename>', methods=['GET'])
def serve_aigc_image(filename):
    """提供AIGC_graph文件夹中的图片"""
    from flask import send_from_directory
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        image_dir = os.path.join(base_dir, "AIGC_graph")
        
        print(f"[API] 请求AIGC图片: {filename}")
        print(f"[API] AIGC_graph目录: {image_dir}")
        print(f"[API] 目录是否存在: {os.path.exists(image_dir)}")
        
        # 确保文件路径安全（防止路径遍历攻击）
        safe_path = os.path.normpath(os.path.join(image_dir, filename))
        if not safe_path.startswith(os.path.normpath(image_dir)):
            print(f"[API] 路径不安全: {safe_path}")
            return jsonify({'error': 'Invalid path'}), 403
        
        print(f"[API] 完整文件路径: {safe_path}")
        print(f"[API] 文件是否存在: {os.path.exists(safe_path)}")
        
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            print(f"[API] 成功提供图片: {filename}")
            return send_from_directory(image_dir, os.path.basename(safe_path))
        else:
            # 列出目录中的文件，用于调试
            if os.path.exists(image_dir):
                files = os.listdir(image_dir)
                print(f"[API] AIGC_graph目录中的文件: {files[:10]}")  # 只显示前10个
            print(f"[API] 文件不存在: {safe_path}")
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        import traceback
        print(f"[API] 提供AIGC图片失败: {e}")
        print(f"[API] 错误堆栈: {traceback.format_exc()}")
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
        from login import AuthSystem
        from db_connection import get_user_db_connection
        
        auth_system = AuthSystem()
        user_config = auth_system.get_user_db_config(user_id)
        if not user_config:
            return jsonify({'success': False, 'message': '用户不存在'}), 401
        
        # 检查用户权限（只有管理员可以审核）
        user_info = auth_system.get_user_by_id(user_id)
        if not user_info or user_info.get('role') != '管理员':
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
        print(f"[API] 审核标注失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'审核失败: {str(e)}'}), 500


@app.route('/api/annotation/tasks/<int:task_id>/reject', methods=['POST'])
def reject_annotation(task_id):
    """驳回标注"""
    try:
        user_id = int(request.headers.get('X-User-Id', 0))
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户信息'}), 400
        
        data = request.json
        reject_reason = data.get('reason', '')
        
        from login import AuthSystem
        from db_connection import get_user_db_connection
        
        auth_system = AuthSystem()
        user_config = auth_system.get_user_db_config(user_id)
        if not user_config:
            return jsonify({'success': False, 'message': '用户不存在'}), 401
        
        # 检查用户权限
        user_info = auth_system.get_user_by_id(user_id)
        if not user_info or user_info.get('role') != '管理员':
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
        print(f"[API] 驳回标注失败: {e}")
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
        print(f"[API] 获取评论失败: {e}")
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
        print(f"[API] 创建评论失败: {e}")
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
                                cursor.execute("""
                                    INSERT INTO notifications (user_id, notification_type, content, related_id)
                                    VALUES (%s, 'like', %s, %s)
                                """, (comment_author['user_id'], f'用户点赞了您的评论', comment_id))
                            except:
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
        print(f"[API] 点赞失败: {e}")
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
                        cursor.execute("""
                            INSERT INTO notifications (user_id, notification_type, content, related_id)
                            VALUES (%s, 'reply', %s, %s)
                        """, (comment_author['user_id'], f'用户回复了您的评论', comment_id))
                        conn.commit()
                    except:
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
        print(f"[API] 回复失败: {e}")
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
            with conn.cursor() as cursor:
                # 构建查询条件
                query = "SELECT * FROM notifications WHERE user_id = %s"
                params = [user_id]
                
                if is_read is not None:
                    query += " AND is_read = %s"
                    params.append(is_read)
                
                query += " ORDER BY created_at DESC LIMIT 50"
                
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
        print(f"[API] 获取通知失败: {e}")
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
        print(f"[API] 记录访问日志失败: {e}")
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
        print(f"[API] 标记通知已读失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'标记通知已读失败：{str(e)}'}), 500


@app.route('/api/admin/dashboard/statistics', methods=['GET'])
def get_dashboard_statistics():
    """获取数据大屏统计信息（仅管理员可访问）"""
    try:
        # 从请求参数或请求头获取用户ID
        user_id = request.args.get('user_id') or request.headers.get('X-User-ID')
        
        if not user_id:
            return jsonify({'success': False, 'message': '未授权访问，请先登录'}), 401
        
        user_id = int(user_id)
        
        # 检查是否为管理员
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                # 从数据库users表读取role字段，检查是否为管理员
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user_info = cursor.fetchone()
                if not user_info:
                    return jsonify({'success': False, 'message': '用户不存在'}), 404
                
                # 检查role字段是否为'管理员'
                if user_info.get('role') != '管理员':
                    return jsonify({'success': False, 'message': '权限不足，仅管理员可访问'}), 403
                
                from datetime import datetime, timedelta
                import pytz
                
                # 获取当前时间（中国时区）
                tz = pytz.timezone('Asia/Shanghai')
                now = datetime.now(tz)
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # 1. 历史总访问人次（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as total_users
                    FROM user_access_logs
                    WHERE access_type = 'page_view'
                """)
                result = cursor.fetchone()
                total_users = result.get('total_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_sessions表统计
                if total_users == 0:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT user_id) as total_users
                        FROM qa_sessions
                    """)
                    result = cursor.fetchone()
                    total_users = result.get('total_users', 0) if result else 0
                
                # 2. 今日访问人次（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as today_users
                    FROM user_access_logs
                    WHERE access_type = 'page_view' AND access_time >= %s
                """, (today_start,))
                result = cursor.fetchone()
                today_users = result.get('today_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_sessions表统计
                if today_users == 0:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT user_id) as today_users
                        FROM qa_sessions
                        WHERE created_at >= %s
                    """, (today_start,))
                    result = cursor.fetchone()
                    today_users = result.get('today_users', 0) if result else 0
                
                # 3. 历史文字AIGC使用人次（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as total_text_users
                    FROM user_access_logs
                    WHERE access_type = 'aigc_text'
                """)
                result = cursor.fetchone()
                total_text_users = result.get('total_text_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计
                if total_text_users == 0:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT user_id) as total_text_users
                        FROM qa_messages
                        WHERE model = 'text'
                    """)
                    result = cursor.fetchone()
                    total_text_users = result.get('total_text_users', 0) if result else 0
                
                # 4. 今日文字AIGC使用人次（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as today_text_users
                    FROM user_access_logs
                    WHERE access_type = 'aigc_text' AND access_time >= %s
                """, (today_start,))
                result = cursor.fetchone()
                today_text_users = result.get('today_text_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计
                if today_text_users == 0:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT user_id) as today_text_users
                        FROM qa_messages
                        WHERE model = 'text' AND create_time >= %s
                    """, (today_start,))
                    result = cursor.fetchone()
                    today_text_users = result.get('today_text_users', 0) if result else 0
                
                # 5. 历史图片AIGC使用人次（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as total_image_users
                    FROM user_access_logs
                    WHERE access_type = 'aigc_image'
                """)
                result = cursor.fetchone()
                total_image_users = result.get('total_image_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计
                if total_image_users == 0:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT user_id) as total_image_users
                        FROM qa_messages
                        WHERE model = 'image'
                    """)
                    result = cursor.fetchone()
                    total_image_users = result.get('total_image_users', 0) if result else 0
                
                # 6. 今日图片AIGC使用人次（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as today_image_users
                    FROM user_access_logs
                    WHERE access_type = 'aigc_image' AND access_time >= %s
                """, (today_start,))
                result = cursor.fetchone()
                today_image_users = result.get('today_image_users', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计
                if today_image_users == 0:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT user_id) as today_image_users
                        FROM qa_messages
                        WHERE model = 'image' AND create_time >= %s
                    """, (today_start,))
                    result = cursor.fetchone()
                    today_image_users = result.get('today_image_users', 0) if result else 0
                
                # 7. 历史文字AIGC使用次数（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(*) as total_text_count
                    FROM user_access_logs
                    WHERE access_type = 'aigc_text'
                """)
                result = cursor.fetchone()
                total_text_count = result.get('total_text_count', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计
                if total_text_count == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as total_text_count
                        FROM qa_messages
                        WHERE model = 'text'
                    """)
                    result = cursor.fetchone()
                    total_text_count = result.get('total_text_count', 0) if result else 0
                
                # 8. 今日文字AIGC使用次数（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(*) as today_text_count
                    FROM user_access_logs
                    WHERE access_type = 'aigc_text' AND access_time >= %s
                """, (today_start,))
                result = cursor.fetchone()
                today_text_count = result.get('today_text_count', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计
                if today_text_count == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as today_text_count
                        FROM qa_messages
                        WHERE model = 'text' AND create_time >= %s
                    """, (today_start,))
                    result = cursor.fetchone()
                    today_text_count = result.get('today_text_count', 0) if result else 0
                
                # 9. 历史图片AIGC使用次数（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(*) as total_image_count
                    FROM user_access_logs
                    WHERE access_type = 'aigc_image'
                """)
                result = cursor.fetchone()
                total_image_count = result.get('total_image_count', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计
                if total_image_count == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as total_image_count
                        FROM qa_messages
                        WHERE model = 'image'
                    """)
                    result = cursor.fetchone()
                    total_image_count = result.get('total_image_count', 0) if result else 0
                
                # 10. 今日图片AIGC使用次数（从user_access_logs表统计，包括管理员）
                cursor.execute("""
                    SELECT COUNT(*) as today_image_count
                    FROM user_access_logs
                    WHERE access_type = 'aigc_image' AND access_time >= %s
                """, (today_start,))
                result = cursor.fetchone()
                today_image_count = result.get('today_image_count', 0) if result else 0
                
                # 如果user_access_logs表为空，回退到qa_messages表统计
                if today_image_count == 0:
                    cursor.execute("""
                        SELECT COUNT(*) as today_image_count
                        FROM qa_messages
                        WHERE model = 'image' AND create_time >= %s
                    """, (today_start,))
                    result = cursor.fetchone()
                    today_image_count = result.get('today_image_count', 0) if result else 0
                
                # 11. 最近7天的使用趋势（按天统计，优先使用user_access_logs表）
                seven_days_ago = today_start - timedelta(days=6)
                cursor.execute("""
                    SELECT 
                        DATE(access_time) as date,
                        COUNT(DISTINCT user_id) as daily_users,
                        SUM(CASE WHEN access_type = 'aigc_text' THEN 1 ELSE 0 END) as text_count,
                        SUM(CASE WHEN access_type = 'aigc_image' THEN 1 ELSE 0 END) as image_count
                    FROM user_access_logs
                    WHERE access_time >= %s
                    GROUP BY DATE(access_time)
                    ORDER BY date ASC
                """, (seven_days_ago,))
                trend_data = cursor.fetchall()
                
                # 如果user_access_logs表为空，回退到qa_messages表统计
                if not trend_data:
                    cursor.execute("""
                        SELECT 
                            DATE(create_time) as date,
                            COUNT(DISTINCT user_id) as daily_users,
                            SUM(CASE WHEN model = 'text' THEN 1 ELSE 0 END) as text_count,
                            SUM(CASE WHEN model = 'image' THEN 1 ELSE 0 END) as image_count
                        FROM qa_messages
                        WHERE create_time >= %s
                        GROUP BY DATE(create_time)
                        ORDER BY date ASC
                    """, (seven_days_ago,))
                    trend_data = cursor.fetchall()
                
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
                        'trend_data': trend_data
                    }
                })
        finally:
            if conn:
                conn.close()
    except Exception as e:
        print(f"[API] 获取数据大屏统计失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取统计信息失败：{str(e)}'}), 500


if __name__ == '__main__':
    print("=" * 60)
    # 使用8000端口作为后端服务端口（通过前端5173代理访问）
    backend_port = 8000
    
    print("启动AIGC API服务器...")
    print("=" * 60)
    print("注意：RAG和ImageAIGC系统将按用户动态创建")
    print("搜索RAG系统将在首次搜索请求时初始化")
    print("=" * 60)
    try:
        app.run(host='0.0.0.0', port=backend_port, debug=True)
    except Exception as e:
        print(f"服务器启动失败: {e}")
        import traceback
        traceback.print_exc()

