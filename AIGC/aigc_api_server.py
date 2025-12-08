"""
AIGC API服务器
提供文字AIGC和图片AIGC的后端接口

使用方法：
1. 安装依赖：pip install flask flask-cors
2. 运行：python aigc_api_server.py
3. 服务器将在 http://localhost:5000 启动
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

# 导入RAG和ImageAIGC模块（同文件夹内）
from RAG import CulturalResourceRAG
from image_RAG import ImageAIGC
from aigc_db_helper import save_aigc_text_resource, save_aigc_image, extract_festival_names
# 导入父目录的模块
from login import AuthSystem
from upload_handler import ResourceUploader

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 初始化认证系统
auth_system = AuthSystem()

# 初始化RAG和ImageAIGC系统（按用户动态创建）
rag_systems = {}  # {user_id: rag_system}
image_aigc_systems = {}  # {user_id: image_aigc_system}

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
    """获取或创建用户的RAG系统"""
    if user_id in rag_systems:
        return rag_systems[user_id]
    
    text_model = get_text_model()
    if not text_model:
        return None
    
    try:
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
    """获取或创建用户的ImageAIGC系统"""
    if user_id in image_aigc_systems:
        return image_aigc_systems[user_id]
    
    text_model = get_text_model()
    if not text_model:
        return None
    
    try:
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

@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册接口"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        
        result = auth_system.register(username, password)
        return jsonify(result)
    except Exception as e:
        print(f"[API] 注册失败: {e}")
        return jsonify({'success': False, 'message': f'注册失败：{str(e)}'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录接口"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        
        result = auth_system.login(username, password)
        return jsonify(result)
    except Exception as e:
        print(f"[API] 登录失败: {e}")
        return jsonify({'success': False, 'message': f'登录失败：{str(e)}'}), 500

@app.route('/api/auth/user', methods=['GET'])
def get_user():
    """获取当前用户信息（通过user_id参数）"""
    try:
        user_id = request.args.get('user_id', type=int)
        if not user_id:
            return jsonify({'success': False, 'message': '缺少user_id参数'}), 400
        
        user_info = auth_system.get_user_by_id(user_id)
        if user_info:
            return jsonify({'success': True, 'user_info': user_info})
        else:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
    except Exception as e:
        print(f"[API] 获取用户信息失败: {e}")
        return jsonify({'success': False, 'message': f'获取用户信息失败：{str(e)}'}), 500

@app.route('/api/aigc/chat', methods=['POST'])
def aigc_chat():
    """处理AIGC聊天请求（支持流式输出）"""
    image_paths = []  # 在函数开始处初始化，确保finally中可用
    try:
        mode = request.form.get('mode', 'text')
        query = request.form.get('query', '')
        stream = request.form.get('stream', 'false').lower() == 'true'
        
        print(f"[API] 收到请求 - mode: {mode}, query: {query[:50]}..., stream: {stream}")
        
        if not query:
            print("[API] 错误：查询内容为空")
            return jsonify({'error': '查询内容不能为空', 'answer': '查询内容不能为空'}), 400
        
        # 处理图片上传
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
                print(f"保存上传图片失败: {e}")
        
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
        
        if mode == 'text':
            # 文字AIGC模式：使用RAG系统
            rag_system = get_or_create_rag_system(user_id, db_config)
            if not rag_system:
                print("[API] 错误：RAG系统未初始化")
                return jsonify({
                    'error': 'RAG系统未初始化',
                    'answer': '抱歉，系统未正确配置，请检查API密钥设置。'
                }), 500
            
            try:
                print(f"[API] 调用RAG系统处理问题... (用户ID: {user_id})")
                # 确保image_paths参数正确传递
                result = rag_system.ask(
                    query=query,
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
                    resource_title = query[:50] if len(query) > 50 else query
                    if not resource_title:
                        resource_title = "AIGC生成的文化资源"
                    
                    # 提取节日名称
                    festival_names = extract_festival_names(answer + " " + query)
                    festival_title = festival_names[0] if festival_names else None
                    
                    # 保存到AIGC_cultural_resources和AIGC_cultural_entities表
                    save_aigc_text_resource(
                        db_config=db_config,
                        resource_title=resource_title,
                        content_text=answer,
                        source_from="AIGC文字生成",
                        festival_title=festival_title,
                        tags=result.get('key_entities', [])
                    )
                    print(f"[API] 已保存AIGC生成的文字资源到数据库")
                except Exception as e:
                    print(f"[API] 保存AIGC文字资源失败: {e}")
                    # 不影响正常返回，继续执行
                
                print(f"[API] RAG处理成功，返回答案长度: {len(answer)}")
                
                # 如果请求流式输出
                if stream:
                    def generate():
                        # 先发送检索到的资源信息
                        resources_data = {
                            'type': 'resources',
                            'data': retrieved_resources
                        }
                        yield f"data: {json.dumps(resources_data, ensure_ascii=False)}\n\n"
                        
                        # 然后流式发送答案（模拟流式，将答案分块发送）
                        chunk_size = 10  # 每次发送10个字符
                        for i in range(0, len(answer), chunk_size):
                            chunk = answer[i:i+chunk_size]
                            chunk_data = {
                                'type': 'chunk',
                                'data': chunk
                            }
                            yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                            import time
                            time.sleep(0.05)  # 模拟流式延迟
                        
                        # 最后发送完整结果
                        final_data = {
                            'type': 'done',
                            'data': {
                                'answer': answer,
                                'key_entities': result.get('key_entities', []),
                                'sources': result.get('sources', ''),
                                'confidence': result.get('confidence', 0),
                                'retrieved_resources': retrieved_resources
                            }
                        }
                        yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                    
                    return Response(
                        stream_with_context(generate()),
                        mimetype='text/event-stream',
                        headers={
                            'Cache-Control': 'no-cache',
                            'X-Accel-Buffering': 'no',
                            'Connection': 'keep-alive'
                        }
                    )
                else:
                    # 非流式输出
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
            # 图片AIGC模式：使用ImageAIGC系统
            image_aigc_system = get_or_create_image_aigc_system(user_id, db_config)
            if not image_aigc_system:
                return jsonify({
                    'error': 'ImageAIGC系统未初始化',
                    'answer': '抱歉，图片生成系统未正确配置，请检查API密钥设置。'
                }), 500
            
            try:
                # 从查询中提取风格（如果有）
                style = "传统节日风格"
                if "风格" in query or "style" in query.lower():
                    # 尝试提取风格信息
                    pass
                
                # 生成图片
                image_path = image_aigc_system.generate_image(
                    prompt=query,
                    style=style,
                    image_paths=image_paths if image_paths else None,
                    use_history=True
                )
                
                if image_path:
                    # 保存AIGC生成的图片到数据库
                    try:
                        # 从查询中提取标签
                        festival_names = extract_festival_names(query)
                        tags = festival_names + [style] if style else festival_names
                        
                        save_aigc_image(
                            db_config=db_config,
                            image_path=image_path,
                            source_from="AIGC图片生成",
                            tags=tags
                        )
                        print(f"[API] 已保存AIGC生成的图片到数据库")
                    except Exception as e:
                        print(f"[API] 保存AIGC图片失败: {e}")
                        # 不影响正常返回，继续执行
                    
                    return jsonify({
                        'answer': f'图片生成成功！\n提示词：{query}',
                        'image_path': image_path
                    })
                else:
                    return jsonify({
                        'error': '图片生成失败',
                        'answer': '抱歉，图片生成失败，请稍后重试。'
                    }), 500
                    
            except Exception as e:
                print(f"图片生成失败: {e}")
                return jsonify({
                    'error': str(e),
                    'answer': f'图片生成失败：{str(e)}'
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
    return jsonify({
        'status': 'ok',
        'rag_systems_count': len(rag_systems),
        'image_aigc_systems_count': len(image_aigc_systems)
    })

@app.route('/api/home/resources', methods=['GET'])
def get_home_resources():
    """获取首页资源列表（从crawled_images和cultural_entities表）"""
    try:
        import re
        import json
        import os
        
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 8))
        
        # 获取数据库连接（使用默认配置）
        from db_connection import get_user_db_connection
        conn = get_user_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '数据库连接失败'}), 500
        
        try:
            with conn.cursor() as cursor:
                resources = []
                
                # 1. 从crawled_images表获取图片资源
                cursor.execute("""
                    SELECT id, file_name, storage_path, tags, dimensions
                    FROM crawled_images
                    ORDER BY crawl_time DESC
                    LIMIT %s OFFSET %s
                """, (page_size, (page - 1) * page_size))
                
                crawled_images = cursor.fetchall()
                for img in crawled_images:
                    # 构建图片URL（优先使用storage_path，如果没有则使用file_name）
                    storage_path = img.get('storage_path')
                    file_name = img.get('file_name')
                    
                    # 确定实际的文件名（storage_path可能包含路径，需要提取文件名）
                    if storage_path:
                        # 如果storage_path是完整路径，提取文件名
                        actual_file = os.path.basename(storage_path) if os.path.sep in storage_path else storage_path
                    elif file_name:
                        actual_file = file_name
                    else:
                        actual_file = None
                    
                    # 构建图片URL
                    image_url = f"/api/images/crawled/{actual_file}" if actual_file else None
                    
                    # 从tags字段提取实体名称（正则匹配第一个汉字到下一个非汉字之前的内容）
                    entity_name = ""
                    description = ""
                    if img.get('tags'):
                        try:
                            tags_data = json.loads(img['tags']) if isinstance(img['tags'], str) else img['tags']
                            if isinstance(tags_data, list) and tags_data:
                                # 从tags列表中提取第一个包含汉字的字符串
                                for tag in tags_data:
                                    if isinstance(tag, str):
                                        # 匹配第一个汉字到下一个非汉字之前的内容
                                        # 例如："春节习俗" -> "春节"
                                        match = re.search(r'([\u4e00-\u9fa5]+)', tag)
                                        if match:
                                            entity_name = match.group(1)
                                            # 提取从第一个汉字开始到下一个非汉字之前的内容作为描述
                                            desc_match = re.search(r'([\u4e00-\u9fa5]+[^\u4e00-\u9fa5]*)', tag)
                                            if desc_match:
                                                description = desc_match.group(1).strip()[:100]
                                            else:
                                                description = tag[:100] if len(tag) > 100 else tag
                                            break
                        except Exception as e:
                            print(f"解析tags失败: {e}")
                            pass
                    
                    # 如果tags中没有找到，使用文件名（去掉扩展名）作为实体名称
                    if not entity_name and img.get('file_name'):
                        entity_name = os.path.splitext(img['file_name'])[0]
                    
                    resources.append({
                        'id': f"img_{img['id']}",
                        'type': 'image',
                        'image_url': image_url,
                        'entity_name': entity_name or '未命名资源',
                        'description': description or '暂无简介',
                        'source': 'crawled_images'
                    })
                
                # 2. 从cultural_entities表获取实体资源（如果图片资源不足）
                # 计算还需要多少条数据
                remaining = page_size - len(resources)
                if remaining > 0:
                    # 计算偏移量（考虑已经获取的图片数量）
                    offset = max(0, (page - 1) * page_size - len(crawled_images))
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
                        
                        resources.append({
                            'id': f"entity_{entity['id']}",
                            'type': 'entity',
                            'image_url': image_url,
                            'entity_name': entity.get('entity_name') or '未命名实体',
                            'description': (entity.get('description') or '')[:200] or '暂无简介',
                            'entity_type': entity.get('entity_type'),
                            'source': 'cultural_entities'
                        })
                
                # 获取总数（只统计crawled_images，因为这是主要资源）
                cursor.execute("SELECT COUNT(*) as total FROM crawled_images")
                total_result = cursor.fetchone()
                total = total_result['total'] if total_result else 0
                
                # 如果图片资源不足，补充统计cultural_entities
                if total < page_size:
                    cursor.execute("SELECT COUNT(*) as total FROM cultural_entities")
                    total_entities_result = cursor.fetchone()
                    total_entities = total_entities_result['total'] if total_entities_result else 0
                    total = max(total, total_entities)
                
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
            conn.close()
            
    except Exception as e:
        print(f"[API] 获取首页资源失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'获取资源失败：{str(e)}'
        }), 500

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
        
        if os.path.exists(safe_path):
            return send_from_directory(image_dir, os.path.basename(safe_path))
        else:
            return jsonify({'error': 'File not found'}), 404
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
                    SELECT id, user_id, created_at, summary
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
                cursor.execute("""
                    INSERT INTO qa_sessions (user_id, summary)
                    VALUES (%s, %s)
                """, (user_id, summary))
                conn.commit()
                session_id = cursor.lastrowid
                
                cursor.execute("""
                    SELECT id, user_id, created_at, summary
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
                        'summary': session['summary']
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
                
                # 获取消息列表
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
                        'role': msg['sender'],  # 'user' 或 'ai'
                        'content': msg['message_content'] or '',
                        'feedback': msg['user_feedback'],
                        'timestamp': msg['timestamp'].isoformat() if msg['timestamp'] else None,
                        'retrieved_resources': None,  # 可以从其他字段扩展
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
        sender = data.get('sender')  # 'user' 或 'ai'
        message_content = data.get('content', '')
        
        if sender not in ['user', 'ai']:
            return jsonify({'success': False, 'message': '无效的发送者类型'}), 400
        
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
                
                # 保存消息
                cursor.execute("""
                    INSERT INTO qa_messages (session_id, sender, message_content)
                    VALUES (%s, %s, %s)
                """, (session_id, sender, message_content))
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

if __name__ == '__main__':
    print("启动AIGC API服务器...")
    print("注意：RAG和ImageAIGC系统将按用户动态创建")
    app.run(host='0.0.0.0', port=5000, debug=True)

