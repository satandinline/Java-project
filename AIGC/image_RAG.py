import os
import requests
import time
import json
import warnings
import textwrap
import re
from typing import Dict, Optional, List, Callable, Any, Tuple
from datetime import datetime
import urllib3
from dotenv import load_dotenv
from urllib.parse import urlparse
from io import BytesIO
import urllib.parse

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("警告：未安装PIL/Pillow库，无法在图片上添加文字。请运行: pip install Pillow")

from langchain_core.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from pydantic import SecretStr
from bs4 import BeautifulSoup

warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)

load_dotenv(override=True)

VOLC_SEEDREAM_API_KEY = os.getenv("VOLC_SEEDREAM_API_KEY")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")

# 导入统一的数据库连接模块（从父目录）
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_connection import get_user_db_config, get_user_db_connection




class ImageAIGC:
    """
    图像生成AIGC功能
    支持火山引擎和阿里云图像生成模型
    支持连环画/漫画生成：自动生成故事并生成系列图片
    """
    
    def __init__(self, text_model: Optional[Any] = None, model_configs: Optional[Dict] = None,
                 default_model: str = "volc_seedream", 
                 log_dir: str = "aigc_logs", 
                 local_save_dir: str = "images",
                 save_local: bool = True,
                 enable_retrieval: bool = True,
                 persist_directory: str = "./chroma_db_image",
                 database_name: str = "java-project",
                 retrieval_tables: Optional[List[str]] = None,
                 db_config: Optional[Dict] = None):
        """
        初始化图像生成AIGC系统
        :param text_model: 文本生成模型（用于生成故事），可选；未提供则根据环境变量自动初始化
        :param model_configs: 图像生成模型配置字典；未提供则使用环境变量构建默认配置
        :param default_model: 默认图像生成模型键名
        :param log_dir: 日志目录
        :param local_save_dir: 本地保存目录
        :param save_local: 是否保存到本地
        :param enable_retrieval: 是否启用RAG检索功能
        :param persist_directory: 向量库持久化目录
        :param database_name: 数据库名称
        :param retrieval_tables: 要检索的数据库表列表
        :param db_config: 数据库配置字典
        """
        if text_model is None:
            try:
                from langchain_community.chat_models import ChatTongyi
                if ALIYUN_API_KEY:
                    text_model = ChatTongyi(api_key=SecretStr(ALIYUN_API_KEY or ""), model="qwen-turbo")
            except Exception:
                if OPENAI_API_KEY:
                    text_model = ChatOpenAI(model="gpt-3.5-turbo")
        self.text_model = text_model
        
        # 若调用方未传入模型配置，则使用环境变量构建默认配置
        if model_configs is None:
            model_configs = {
        "volc_seedream": {
            "name": "火山引擎Seedream 4.0",
            "api_url": "https://ark.cn-beijing.volces.com/api/v3/images/generations",
                    "api_key": VOLC_SEEDREAM_API_KEY,
            "model_id": "doubao-seedream-4-0-250828",
                    "image_size": "1024x1024",
                    "supported_sizes": ["1024x1024", "2048x2048"],
            "timeout": 90,
            "max_retries": 2,
            "request_format": "volc"
        },
        "ali_sd_xl": {
            "name": "阿里云Stable Diffusion XL",
            "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
                    "api_key": DASHSCOPE_API_KEY,
            "model_id": "stable-diffusion-xl",
            "image_size": "1024x1024",
            "supported_sizes": ["512x512", "1024x1024", "2048x2048"],
            "timeout": 120,
            "max_retries": 2,
            "request_format": "aliyun"
        }
            }
        self.model_configs = model_configs
        self.default_model = default_model
        self.log_dir = log_dir
        self.local_save_dir = local_save_dir
        self.save_local = save_local
        self.enable_retrieval = enable_retrieval
        self.retrieval_func: Optional[Callable[[str, str], str]] = None
        
        if enable_retrieval:
            self._init_rag_components(persist_directory, database_name, retrieval_tables, db_config)
        
        self._init_story_prompts()
        
        self.prompt_template = """
主题：{prompt}，风格：{style}
补充参考信息：{retrieval_info}
要求：高清分辨率，细节丰富，色彩鲜明，必须体现传统节日的文化内涵和公共文化资源特色，
      包含传统元素（如传统服饰、建筑、器物、习俗等），构图合理，无多余元素，
      视觉冲击力强，具有文化传承价值，不能看起来毫无文化特色。
      图片要看起来非常真实，像真实拍摄的照片一样，具有自然的光影效果、真实的纹理细节、
      自然的色彩过渡、真实的景深效果，避免AI生成的痕迹，避免过度完美或过于规整
"""
        
        if self.default_model not in self.model_configs:
            raise ValueError(f"默认模型 '{self.default_model}' 不在 model_configs 中")
        
        self.model = self.model_configs[self.default_model]
        
        if not self.model.get("api_key"):
            raise ValueError(
                f"模型[{self.model.get('name', self.default_model)}]的API密钥未配置！"
            )
        
        self._init_dirs()
        print(f"ImageAIGC初始化完成，默认模型：{self.model['name']}")
        print(f"默认生图尺寸：{self.model['image_size']}，支持尺寸：{self.model['supported_sizes']}")
        if enable_retrieval:
            print(f"RAG检索功能已启用")
    
    def _init_rag_components(self, persist_directory: str, database_name: str,
                             retrieval_tables: Optional[List[str]], db_config: Optional[Dict]):
        """初始化RAG检索组件"""
        try:
            from langchain_community.embeddings import DashScopeEmbeddings
            self.embedding_model = DashScopeEmbeddings(
                dashscope_api_key=ALIYUN_API_KEY,
                model="text-embedding-v2"
            )
        except Exception as e:
            print(f"DashScopeEmbeddings 初始化失败: {e}，使用 OpenAIEmbeddings 作为备选。")
            self.embedding_model = OpenAIEmbeddings()
        
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        
        self.vector_store = Chroma(persist_directory=persist_directory, embedding_function=self.embedding_model)
        self._persist_directory = persist_directory
        
        try:
            self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
            print("向量检索器初始化成功")
        except Exception as e:
            print(f"创建 retriever 出错: {e}")
            self.retriever = None
        
        self.database_name = database_name
        self.retrieval_tables = retrieval_tables or ["cultural_resources", "cultural_entities", 
                                                      "entity_relationships", "AIGC_cultural_resources",
                                                      "AIGC_graph", "crawled_images"]
        
        # 多轮对话支持：存储对话历史
        self.conversation_history: List[Dict] = []
        
        if db_config:
            self.db_config = db_config
        else:
            # 使用统一的数据库配置（从login.py获取用户配置）
            self.db_config = get_user_db_config()
        
        self.db_connection = None
    
    def _init_story_prompts(self):
        """初始化故事生成相关的prompt模板"""
        story_schemas = [
            ResponseSchema(name="title", description="故事标题，要体现传统节日文化特色"),
            ResponseSchema(name="story", description="完整的故事内容，适合制作连环画，要深入体现传统节日的文化内涵"),
            ResponseSchema(name="scenes", description="故事场景列表，每个场景必须包含：场景描述、画面描述、文字说明（简短精炼，体现文化内涵，不超过20字），至少6个场景")
        ]
        self.story_parser = StructuredOutputParser.from_response_schemas(story_schemas)
        self.story_format_instructions = self.story_parser.get_format_instructions()
        
        story_template = textwrap.dedent("""
        你是一位擅长创作传统节日故事的作家。请根据用户的要求创作一个适合制作连环画/漫画的故事。

        用户要求：{user_request}

        要求：
        1. 故事必须围绕传统节日主题，深入挖掘节日的文化内涵、历史渊源、民俗传统和象征意义
        2. 故事要体现公共文化资源的特性，具有教育意义和文化传承价值
        3. 每个场景要包含：场景描述（用于理解情节）、画面描述（用于绘制）、文字说明（简短精炼，体现文化内涵，不超过20字）
        4. 文字说明要典雅、富有文化韵味，可以引用古诗词、谚语或传统表达方式
        5. 故事要有清晰的起承转合，适合用6-12幅画面来表现
        6. 语言生动有趣，适合儿童和青少年阅读，同时保持文化深度
        7. **重要：场景之间必须紧密连贯，每个场景的文字说明要承上启下，形成完整的故事链条**
        8. **重要：人物、环境、时间等要素在相邻场景中要保持一致性，确保故事逻辑流畅**
        9. **重要：文字说明要体现故事的发展脉络，前一个场景的文字要为下一个场景做铺垫，形成连贯的叙事**

        请按照以下JSON格式输出：
        {format_instructions}
        """)
        self.story_prompt_template = PromptTemplate(
            template=story_template,
            input_variables=["user_request"],
            partial_variables={"format_instructions": self.story_format_instructions}
        )  # type: ignore[arg-type]
        
        scene_template = textwrap.dedent("""
        请将以下故事场景转换为适合图像生成的提示词。

        场景描述：{scene_description}
        故事上下文：{story_context}
        前一个场景：{previous_scene}
        后一个场景：{next_scene}

        要求：
        1. 提示词要详细描述画面内容，包括人物、动作、环境、氛围
        2. 必须体现传统节日的文化特色，如传统服饰、传统建筑、传统器物、传统习俗等
        3. 画面要有故事性和连贯性，体现公共文化资源的特性
        4. 风格要统一，适合连环画/漫画风格，具有文化传承价值
        5. 画面要富有文化内涵，不能看起来毫无文化特色
        6. **重要：必须与前一个场景在人物形象、环境设置、时间氛围上保持视觉连贯性**
        7. **重要：画面要体现故事的发展，与前一个场景形成自然的过渡，为后一个场景做铺垫**
        8. **重要：人物表情、动作、位置要与故事发展逻辑一致，体现情节的连贯性**

        只返回图像生成的提示词，不要其他解释：
        """)
        self.scene_prompt_template = PromptTemplate(
            template=scene_template,
            input_variables=["scene_description", "story_context", "previous_scene", "next_scene"]
        )  # type: ignore[arg-type]
    
    def _init_dirs(self):
        """初始化必要的目录"""
        os.makedirs(self.log_dir, exist_ok=True)
        if self.save_local:
            os.makedirs(self.local_save_dir, exist_ok=True)
    
    def _log_info(self, message: str):
        """记录信息日志"""
        log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_content = f"[{log_time}] [INFO] {message}\n"
        print(log_content, end="")
        with open(os.path.join(self.log_dir, "aigc.log"), "a", encoding="utf-8") as f:
            f.write(log_content)

    def _log_error(self, message: str):
        """记录错误日志"""
        log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_content = f"[{log_time}] [ERROR] {message}\n"
        print(log_content, end="")
        with open(os.path.join(self.log_dir, "aigc_error.log"), "a", encoding="utf-8") as f:
            f.write(log_content)

    def set_retrieval_func(self, retrieval_func: Callable[[str, str], str]):
        """设置检索函数"""
        self.retrieval_func = retrieval_func
        self.enable_retrieval = True
        self._log_info("检索功能模块已注册")
    
    def _add_text_to_image(self, image_path: str, text: str) -> str:
        """在图片上添加文字说明"""
        if not HAS_PIL:
            self._log_error("PIL库未安装，无法在图片上添加文字")
            return image_path
        
        if not text or not text.strip():
            return image_path
        
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)
            
            width, height = img.size
            font_size = max(24, min(width, height) // 30)
            
            try:
                font = ImageFont.truetype("simhei.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
            
            text_lines = textwrap.wrap(text, width=15)
            line_height = font_size + 10
            
            y_offset = height - (len(text_lines) * line_height) - 20
            
            for line in text_lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                
                shadow_offset = 2
                draw.text((x + shadow_offset, y_offset + shadow_offset), line, 
                         font=font, fill=(0, 0, 0, 180))
                draw.text((x, y_offset), line, font=font, fill=(255, 255, 255, 255))
                
                y_offset += line_height
            
            img.save(image_path, quality=95)
            return image_path
        except Exception as e:
            self._log_error(f"添加文字到图片失败：{str(e)}")
            return image_path
    
    def _save_image_local(self, image_url: str, prompt: str, model_name: str, 
                          text_overlay: Optional[str] = None) -> str:
        """保存图片到本地，可选择添加文字"""
        if not self.save_local:
            return ""
        try:
            response = requests.get(image_url, timeout=30, verify=False)
            response.raise_for_status()
            
            existing_files = []
            for filename in os.listdir(self.local_save_dir):
                if os.path.isfile(os.path.join(self.local_save_dir, filename)):
                    name_part = filename.split('.')[0]
                    if name_part.isdigit():
                        existing_files.append(int(name_part))
            
            next_number = max(existing_files) + 1 if existing_files else 1
            
            file_extension = ".jpg"
            parsed_url = urlparse(image_url)
            original_filename = os.path.basename(parsed_url.path)
            if '.' in original_filename:
                ext = '.' + original_filename.split('.')[-1]
                if ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    file_extension = ext
            
            file_name = f"{next_number:04d}{file_extension}"
            file_path = os.path.join(self.local_save_dir, file_name)
            
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            if text_overlay:
                file_path = self._add_text_to_image(file_path, text_overlay)
            
            self._log_info(f"图片已保存到本地：{file_path}")
            return file_path
        except Exception as e:
            self._log_error(f"本地保存图片失败：{str(e)}")
            return ""

    def _is_comic_request(self, user_input: str) -> bool:
        """检测用户输入是否为连环画/漫画生成请求"""
        comic_keywords = ["连环画", "漫画", "绘本", "故事画", "系列图", "多张图", "一套图"]
        user_input_lower = user_input.lower()
        return any(keyword in user_input_lower for keyword in comic_keywords)
    
    def _generate_story(self, user_request: str) -> Optional[Dict]:
        """使用langchain生成故事"""
        if self.text_model is None:
            self._log_error("文本生成模型未配置，无法生成故事")
            return None
        
        try:
            prompt_text = self.story_prompt_template.format(user_request=user_request)
            response = self.text_model.invoke(prompt_text)
            
            if hasattr(response, "content"):
                raw_text = response.content
            elif isinstance(response, str):
                raw_text = response
            else:
                raw_text = str(response)
            
            try:
                if isinstance(raw_text, str):
                    parsed = self.story_parser.parse(raw_text)
                else:
                    parsed = json.loads(str(raw_text))
                self._log_info(f"故事生成成功：{parsed.get('title', '未命名')}")
                return parsed
            except Exception as e:
                self._log_error(f"解析故事失败：{e}，原始文本：{raw_text[:200]}")
                return None
        except Exception as e:
            self._log_error(f"生成故事失败：{e}")
            return None
    
    def _convert_scene_to_image_prompt(self, scene_description: str, story_context: str, 
                                      previous_scene: str = "", next_scene: str = "") -> str:
        """将场景描述转换为图像生成提示词，考虑前后场景的连贯性"""
        if not self.text_model:
            return scene_description
        
        try:
            prompt_text = self.scene_prompt_template.format(
                scene_description=scene_description,
                story_context=story_context,
                previous_scene=previous_scene if previous_scene else "这是第一个场景",
                next_scene=next_scene if next_scene else "这是最后一个场景"
            )
            response = self.text_model.invoke(prompt_text)
            
            if hasattr(response, "content"):
                result = response.content
            elif isinstance(response, str):
                result = response
            else:
                result = str(response)
            
            if isinstance(result, str):
                return result.strip()
            else:
                return str(result).strip()
        except Exception as e:
            self._log_error(f"转换场景提示词失败：{e}")
            return scene_description
    
    def generate_comic(self, user_request: str, style: str = "连环画风格",
                      model_key: Optional[str] = None,
                      image_size: Optional[str] = None,
                      num_scenes: Optional[int] = None) -> List[str]:
        """
        生成连环画/漫画
        :param user_request: 用户请求
        :param style: 图像风格
        :param model_key: 模型键名
        :param image_size: 图像尺寸
        :param num_scenes: 场景数量（如果不指定，使用故事中的场景数）
        :return: 图片路径列表
        """
        self._log_info(f"检测到连环画/漫画生成请求：{user_request}")
        
        story_data = self._generate_story(user_request)
        if not story_data:
            self._log_error("故事生成失败，无法继续生成连环画")
            return []
        
        scenes = story_data.get("scenes", [])
        if not scenes:
            self._log_error("故事中没有场景信息")
            return []
        
        if num_scenes:
            scenes = scenes[:num_scenes]
        
        story_context = story_data.get("story", "")
        story_title = story_data.get("title", "未命名故事")
        
        self._log_info(f"开始生成连环画《{story_title}》，共{len(scenes)}个场景")
        
        image_paths = []
        for idx, scene in enumerate(scenes, 1):
            if isinstance(scene, dict):
                scene_desc = scene.get("场景描述", scene.get("scene_description", scene.get("description", "")))
                image_desc = scene.get("画面描述", scene.get("image_description", scene_desc))
                text_overlay = scene.get("文字说明", scene.get("text", scene.get("caption", "")))
            else:
                scene_desc = str(scene)
                image_desc = scene_desc
                text_overlay = ""
            
            if not image_desc:
                image_desc = scene_desc
            
            if not text_overlay:
                text_overlay = scene_desc[:20] if scene_desc else ""
            
            # 获取前后场景信息以确保连贯性
            previous_scene = ""
            next_scene = ""
            if idx > 1:
                prev_scene = scenes[idx - 2]
                if isinstance(prev_scene, dict):
                    previous_scene = prev_scene.get("场景描述", prev_scene.get("scene_description", prev_scene.get("description", "")))
                else:
                    previous_scene = str(prev_scene)
            if idx < len(scenes):
                next_scene_obj = scenes[idx]
                if isinstance(next_scene_obj, dict):
                    next_scene = next_scene_obj.get("场景描述", next_scene_obj.get("scene_description", next_scene_obj.get("description", "")))
                else:
                    next_scene = str(next_scene_obj)
            
            image_prompt = self._convert_scene_to_image_prompt(
                image_desc, 
                story_context, 
                previous_scene, 
                next_scene
            )
            
            # 添加连贯性要求到提示词中
            continuity_note = ""
            if idx > 1:
                continuity_note = "，与前一幅画面保持人物形象、环境、风格的一致性，体现故事发展的连贯性"
            if idx < len(scenes):
                continuity_note += "，为下一幅画面做铺垫，形成自然的叙事过渡"
            
            full_prompt = f"{image_prompt}，{style}，连环画风格，画面连贯，体现传统节日文化特色{continuity_note}"
            
            self._log_info(f"生成第{idx}/{len(scenes)}幅画面：{image_prompt[:50]}...")
            self._log_info(f"文字说明：{text_overlay}")
            
            image_path = self.generate_image(
                prompt=full_prompt,
                style=style,
                model_key=model_key,
                image_size=image_size,
                auto_detect_comic=False,
                text_overlay=text_overlay
            )
            
            if image_path:
                image_paths.append(image_path)
                time.sleep(1)
            else:
                self._log_error(f"第{idx}幅画面生成失败")
        
        self._log_info(f"连环画生成完成，共生成{len(image_paths)}幅画面")
        return image_paths
    
    def _call_retriever(self, query: str) -> List[Document]:
        """从向量库检索相关文档"""
        if not hasattr(self, 'retriever') or not self.retriever:
            return []
        try:
            if hasattr(self.retriever, "invoke"):
                docs = self.retriever.invoke(query)
                if isinstance(docs, list):
                    return docs
                return list(docs)
            if hasattr(self.retriever, "get_relevant_documents") and callable(self.retriever.get_relevant_documents):
                return self.retriever.get_relevant_documents(query)
            if callable(self.retriever):
                return self.retriever(query)
        except Exception as e:
            self._log_error(f"检索器调用错误: {e}")
        return []
    
    def _get_db_connection(self, user_id: Optional[int] = None):
        """获取数据库连接（使用用户账户）"""
        if not hasattr(self, 'db_config'):
            return None
        try:
            # 如果提供了user_id，使用该用户的数据库配置
            if user_id is not None:
                conn = get_user_db_connection(user_id)
            else:
                # 使用当前db_config中的配置
                conn = get_user_db_connection()
            
            if conn is None:
                # 如果获取失败，尝试使用self.db_config通过db_connection创建连接
                # 确保db_config已更新到db_connection
                if hasattr(self, 'db_config') and self.db_config:
                    # 使用db_connection的统一函数，它会自动使用环境变量或默认配置
                    conn = get_user_db_connection()
                    if conn is None:
                        raise Exception(f"无法连接到数据库，请检查数据库配置。配置信息: host={self.db_config.get('host')}, database={self.db_config.get('database')}")
                else:
                    raise Exception("数据库配置未初始化")
            
            self.db_connection = conn
            return self.db_connection
        except Exception as e:
            self._log_error(f"数据库连接失败: {e}")
            return None
    
    def query_database(self, query: str, table_names: Optional[List[str]] = None) -> List[Dict]:
        """从指定数据库表中检索相关内容"""
        if not hasattr(self, 'retrieval_tables'):
            return []
        if table_names is None:
            table_names = self.retrieval_tables
        
        conn = self._get_db_connection()
        if not conn:
            return []
        
        results = []
        
        try:
            with conn.cursor() as cursor:
                for table in table_names:
                    if table == "cultural_resources":
                        sql = """
                            SELECT id, title, resource_type, content_feature_data, source_from, source_url
                            FROM cultural_resources
                            WHERE title LIKE %s OR content_feature_data LIKE %s
                            LIMIT 10
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            results.append({
                                "table": "cultural_resources",
                                "id": row.get("id"),
                                "title": row.get("title", ""),
                                "content": str(row.get("content_feature_data", ""))[:2000],
                                "source": row.get("source_from", ""),
                                "url": row.get("source_url", "")
                            })
                    
                    elif table == "cultural_entities":
                        sql = """
                            SELECT id, entity_name, entity_type, description, source, 
                                   period_era, cultural_region, cultural_value
                            FROM cultural_entities
                            WHERE entity_name LIKE %s OR description LIKE %s 
                                  OR entity_type LIKE %s
                            LIMIT 10
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            content_parts = []
                            if row.get("description"):
                                content_parts.append(f"描述：{row.get('description')}")
                            if row.get("cultural_value"):
                                content_parts.append(f"文化价值：{row.get('cultural_value')}")
                            if row.get("period_era"):
                                content_parts.append(f"时期：{row.get('period_era')}")
                            if row.get("cultural_region"):
                                content_parts.append(f"文化区域：{row.get('cultural_region')}")
                            
                            results.append({
                                "table": "cultural_entities",
                                "id": row.get("id"),
                                "title": row.get("entity_name", ""),
                                "content": "；".join(content_parts) if content_parts else "",
                                "source": row.get("source", ""),
                                "entity_type": row.get("entity_type", "")
                            })
                    
                    elif table == "entity_relationships":
                        sql = """
                            SELECT er.id, er.relationship_type, er.relationship_evidence,
                                   ce1.entity_name as source_entity, ce2.entity_name as target_entity
                            FROM entity_relationships er
                            JOIN cultural_entities ce1 ON er.source_entity_id = ce1.id
                            JOIN cultural_entities ce2 ON er.target_entity_id = ce2.id
                            WHERE ce1.entity_name LIKE %s OR ce2.entity_name LIKE %s 
                                  OR er.relationship_type LIKE %s
                            LIMIT 10
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            results.append({
                                "table": "entity_relationships",
                                "id": row.get("id"),
                                "title": f"{row.get('source_entity')} - {row.get('relationship_type')} - {row.get('target_entity')}",
                                "content": row.get("relationship_evidence", ""),
                                "source": "",
                                "relationship_type": row.get("relationship_type", "")
                            })
                    
                    elif table == "AIGC_cultural_resources":
                        sql = """
                            SELECT id, title, resource_type, content_feature_data, source_from
                            FROM AIGC_cultural_resources
                            WHERE title LIKE %s OR content_feature_data LIKE %s
                            LIMIT 10
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            results.append({
                                "table": "AIGC_cultural_resources",
                                "id": row.get("id"),
                                "title": row.get("title", ""),
                                "content": str(row.get("content_feature_data", ""))[:2000],
                                "source": row.get("source_from", ""),
                                "url": ""
                            })
                    
                    elif table == "AIGC_graph":
                        sql = """
                            SELECT id, file_name, storage_path, dimensions, tags
                            FROM AIGC_graph
                            WHERE file_name LIKE %s OR JSON_SEARCH(tags, 'one', %s) IS NOT NULL
                            LIMIT 10
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            storage_path = row.get("storage_path", "")
                            # 构建完整路径：项目根目录的AIGC_graph文件夹 + storage_path
                            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            full_path = os.path.join(base_dir, "AIGC_graph", storage_path) if storage_path else ""
                            results.append({
                                "table": "AIGC_graph",
                                "id": row.get("id"),
                                "title": row.get("file_name", ""),
                                "content": f"图片路径：{full_path}，尺寸：{row.get('dimensions', '未知')}",
                                "source": "AIGC生成",
                                "url": full_path,
                                "image_path": full_path
                            })
                    
                    elif table == "crawled_images":
                        sql = """
                            SELECT id, file_name, storage_path, dimensions, tags
                            FROM crawled_images
                            WHERE file_name LIKE %s OR JSON_SEARCH(tags, 'one', %s) IS NOT NULL
                            LIMIT 10
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            storage_path = row.get("storage_path", "")
                            # 构建完整路径：项目根目录的crawled_images文件夹 + storage_path
                            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            full_path = os.path.join(base_dir, "crawled_images", storage_path) if storage_path else ""
                            results.append({
                                "table": "crawled_images",
                                "id": row.get("id"),
                                "title": row.get("file_name", ""),
                                "content": f"图片路径：{full_path}，尺寸：{row.get('dimensions', '未知')}",
                                "source": "爬虫抓取",
                                "url": full_path,
                                "image_path": full_path
                            })
                    
                    elif table == "AIGC_graph":
                        sql = """
                            SELECT id, file_name, storage_path, dimensions, tags
                            FROM AIGC_graph
                            WHERE file_name LIKE %s OR JSON_SEARCH(tags, 'one', %s) IS NOT NULL
                            LIMIT 10
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            storage_path = row.get("storage_path", "")
                            # 构建完整路径：项目根目录的AIGC_graph文件夹 + storage_path
                            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            full_path = os.path.join(base_dir, "AIGC_graph", storage_path) if storage_path else ""
                            results.append({
                                "table": "AIGC_graph",
                                "id": row.get("id"),
                                "title": row.get("file_name", ""),
                                "content": str(row.get("content_feature_data", ""))[:2000] if row.get("content_feature_data") else f"图片路径：{full_path}，尺寸：{row.get('dimensions', '未知')}",
                                "source": row.get("source_from", "AIGC生成"),
                                "url": full_path,
                                "image_path": full_path
                            })
                    
                    elif table == "crawled_images":
                        sql = """
                            SELECT id, file_name, storage_path, dimensions, tags
                            FROM crawled_images
                            WHERE file_name LIKE %s OR JSON_SEARCH(tags, 'one', %s) IS NOT NULL
                            LIMIT 10
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            storage_path = row.get("storage_path", "")
                            # 构建完整路径：项目根目录的crawled_images文件夹 + storage_path
                            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            full_path = os.path.join(base_dir, "crawled_images", storage_path) if storage_path else ""
                            results.append({
                                "table": "crawled_images",
                                "id": row.get("id"),
                                "title": row.get("file_name", ""),
                                "content": f"图片路径：{full_path}，尺寸：{row.get('dimensions', '未知')}",
                                "source": row.get("source_from", "爬虫抓取"),
                                "url": full_path,
                                "image_path": full_path
                            })
        
        except Exception as e:
            self._log_error(f"数据库查询错误: {e}")
        
        return results
    
    def _crawl_web_content(self, query: str, max_results: int = 3) -> List[Document]:
        """当数据库中没有相关信息时，从网页获取传统节日相关内容"""
        documents = []
        search_query = f"{query} 传统节日"
        
        search_urls = [
            f"https://www.baidu.com/s?wd={urllib.parse.quote(search_query)}",
            f"https://www.sogou.com/web?query={urllib.parse.quote(search_query)}"
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        for url in search_urls[:1]:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    links = []
                    for a_tag in soup.find_all("a", href=True)[:max_results * 2]:
                        href = a_tag.get("href", "")
                        if href and isinstance(href, str) and href.startswith("http"):
                            if any(domain in href for domain in 
                                ["baike.baidu.com", "zh.wikipedia.org", "baike.com", "sohu.com", "sina.com.cn"]):
                                links.append(href)
                    
                    for link in links[:max_results]:
                        try:
                            time.sleep(1)
                            page_response = requests.get(link, headers=headers, timeout=10)
                            if page_response.status_code == 200:
                                page_soup = BeautifulSoup(page_response.text, "html.parser")
                                
                                for script in page_soup(["script", "style"]):
                                    script.decompose()
                                
                                text_content = page_soup.get_text()
                                text_content = re.sub(r'\s+', ' ', text_content).strip()
                                
                                if len(text_content) > 200:
                                    doc = Document(
                                        page_content=text_content[:5000],
                                        metadata={"source": link, "title": page_soup.title.string if page_soup.title else ""}
                                    )
                                    documents.append(doc)
                        except Exception as e:
                            continue
            except Exception as e:
                continue
        
        return documents

    def _read_image_info(self, image_path: str) -> Optional[str]:
        """
        读取图片信息（使用视觉模型分析图片内容）
        :param image_path: 图片路径
        :return: 图片描述文本
        """
        if not image_path or not os.path.exists(image_path):
            return None
        
        try:
            # 尝试使用支持视觉的模型读取图片
            if OPENAI_API_KEY:
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=OPENAI_API_KEY)
                    with open(image_path, "rb") as image_file:
                        response = client.chat.completions.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": "请详细描述这张图片的内容，特别是与传统节日、文化相关的元素。"},
                                        {"type": "image_url", "image_url": {"url": f"file://{os.path.abspath(image_path)}"}}
                                    ]
                                }
                            ],
                            max_tokens=300
                        )
                        return response.choices[0].message.content
                except Exception as e:
                    self._log_error(f"图片读取失败: {e}")
                    return f"图片路径：{image_path}（无法读取图片内容）"
            return f"图片路径：{image_path}"
        except Exception as e:
            self._log_error(f"读取图片信息出错: {e}")
            return None
    
    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history = []
    
    def _get_retrieval_info(self, prompt: str, style: str, image_paths: Optional[List[str]] = None) -> str:
        """获取检索参考信息（使用RAG检索），支持图片输入"""
        if not self.enable_retrieval:
            return ""
        
        context_parts = []
        
        # 读取图片信息
        if image_paths:
            image_descriptions = []
            for img_path in image_paths:
                img_info = self._read_image_info(img_path)
                if img_info:
                    image_descriptions.append(img_info)
            if image_descriptions:
                context_parts.append(f"用户上传的图片信息：\n" + "\n".join(image_descriptions))
        
        try:
            docs = self._call_retriever(prompt)
            vector_context = "\n".join([getattr(d, "page_content", str(d)) for d in docs]) if docs else ""
            if vector_context:
                context_parts.append(f"向量库检索：{vector_context[:500]}")
        except Exception as e:
            self._log_error(f"向量数据库检索错误: {e}")
        
        if hasattr(self, 'retrieval_tables') and self.retrieval_tables:
            try:
                db_results = self.query_database(prompt, self.retrieval_tables)
                if db_results:
                    db_context_parts = []
                    for result in db_results[:3]:
                        db_text = ""
                        if result.get('title'):
                            db_text += f"标题：{result.get('title')}\n"
                        content = result.get('content')
                        if content:
                            db_text += f"内容：{str(content)[:300]}\n"
                        if db_text:
                            db_context_parts.append(db_text)
                    if db_context_parts:
                        context_parts.append(f"数据库检索：\n" + "\n---\n".join(db_context_parts))
            except Exception as e:
                self._log_error(f"数据库查询错误: {e}")
        
        context = "\n\n".join(context_parts) if context_parts else ""
        
        if not context or len(context.strip()) < 50:
            try:
                web_docs = self._crawl_web_content(prompt, max_results=2)
                if web_docs:
                    web_context = "\n\n".join([getattr(d, "page_content", str(d))[:500] for d in web_docs])
                    if web_context:
                        context_parts.append(f"网页检索：{web_context}")
                        context = "\n\n".join(context_parts)
            except Exception as e:
                self._log_error(f"网页爬取失败: {e}")
        
        if context:
            self._log_info(f"检索成功，获取参考信息：{context[:100]}...")
        else:
            self._log_info("检索未返回有效信息")
        
        return context

    def _validate_image_size(self, image_size: Optional[str]) -> Tuple[bool, str]:
        """校验尺寸是否被当前模型支持"""
        if not image_size:
            return True, self.model["image_size"]
        if image_size in self.model["supported_sizes"]:
            return True, image_size
        else:
            warning_msg = f"尺寸{image_size}不被{self.model['name']}支持，自动使用默认尺寸{self.model['image_size']}"
            self._log_info(warning_msg)
            return False, self.model["image_size"]

    def generate_image(
            self,
            prompt: str,
            style: str,
            model_key: Optional[str] = None,
            image_size: Optional[str] = None,
            auto_detect_comic: bool = True,
            text_overlay: Optional[str] = None,
            image_paths: Optional[List[str]] = None,
            use_history: bool = True
    ) -> str:
        """
        生成图像
        :param prompt: 主题
        :param style: 风格
        :param model_key: 模型键名
        :param image_size: 图像尺寸
        :param auto_detect_comic: 是否自动检测连环画请求
        :param text_overlay: 可选，要在图片上叠加的文字说明
        :return: 本地保存路径（如果是连环画请求，返回JSON字符串包含所有路径）
        """
        if auto_detect_comic and self._is_comic_request(prompt):
            comic_paths = self.generate_comic(prompt, style, model_key, image_size)
            if comic_paths:
                result = {
                    "type": "comic",
                    "paths": comic_paths,
                    "count": len(comic_paths)
                }
                return json.dumps(result, ensure_ascii=False)
            else:
                self._log_error("连环画生成失败，回退到单图生成")
                return ""
        
        prompt = prompt.strip() if prompt else "未指定主题"
        style = style.strip() if style else "未指定风格"
        if prompt == "未指定主题" or style == "未指定风格":
            self._log_error(f"生图失败：主题或风格不能为空")
            return ""

        if model_key and model_key in self.model_configs:
            self.model = self.model_configs[model_key]
            if not self.model["api_key"]:
                self._log_error(f"模型[{self.model['name']}]的API密钥未配置")
                return ""
        else:
            self.model = self.model_configs[self.default_model]

        is_size_valid, final_image_size = self._validate_image_size(image_size)
        self._log_info(f"生图尺寸：{final_image_size}")

        retrieval_info = self._get_retrieval_info(prompt, style, image_paths)
        
        # 添加对话历史信息
        if use_history and self.conversation_history:
            history_parts = []
            for hist in self.conversation_history[-3:]:  # 只保留最近3轮对话
                if hist.get("role") == "user":
                    history_parts.append(f"用户：{hist.get('content', '')}")
                elif hist.get("role") == "assistant":
                    history_parts.append(f"助手：{hist.get('content', '')}")
            if history_parts:
                retrieval_info += f"\n\n对话历史：\n" + "\n".join(history_parts)

        full_prompt = self.prompt_template.format(
            prompt=prompt,
            style=style,
            retrieval_info=retrieval_info
        ).strip()
        self._log_info(f"生图请求：模型={self.model['name']}，主题={prompt}，风格={style}")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.model['api_key']}"
        }
        request_data = {}

        if self.model["request_format"] == "volc":
            request_data = {
                "model": self.model["model_id"],
                "prompt": full_prompt,
                "sequential_image_generation": "disabled",
                "response_format": "url",
                "size": final_image_size,
                "stream": False,
                "watermark": True
            }
        elif self.model["request_format"] == "aliyun":
            request_data = {
                "model": self.model["model_id"],
                "input": {"prompt": full_prompt},
                "parameters": {
                    "size": final_image_size,
                    "response_format": "url",
                    "quality": "high"
                }
            }

        start_time = time.time()
        for retry in range(self.model["max_retries"] + 1):
            try:
                response = requests.post(
                    url=self.model["api_url"],
                    headers=headers,
                    json=request_data,
                    timeout=self.model["timeout"]
                )
                response.raise_for_status()
                response_data = response.json()
                generate_time = round(time.time() - start_time, 2)

                if self.model["request_format"] == "volc":
                    image_url = response_data["data"][0]["url"]
                elif self.model["request_format"] == "aliyun":
                    image_url = response_data["output"]["url"]
                else:
                    image_url = ""

                self._log_info(f"生图成功：耗时={generate_time}秒")

                local_path = self._save_image_local(image_url, prompt, self.model["name"], text_overlay=text_overlay)
                
                # 更新对话历史
                if use_history:
                    self.conversation_history.append({
                        "role": "user",
                        "content": prompt,
                        "image_paths": image_paths or [],
                        "style": style,
                        "timestamp": datetime.now()
                    })
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": f"已生成图片：{local_path}",
                        "image_path": local_path,
                        "timestamp": datetime.now()
                    })
                    # 限制历史记录长度
                    if len(self.conversation_history) > 20:
                        self.conversation_history = self.conversation_history[-20:]
                
                return local_path if local_path else ""

            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if hasattr(e, "response") and e.response is not None:
                    error_detail += f" | 状态码：{e.response.status_code}"
                if retry < self.model["max_retries"]:
                    self._log_error(f"生图失败（重试{retry + 1}/{self.model['max_retries']}）：{error_detail[:80]}")
                    time.sleep(3)
                else:
                    self._log_error(f"生图失败（已重试{self.model['max_retries']}次）：{error_detail[:100]}")
                    return ""
            except Exception as e:
                self._log_error(f"生图系统错误：{str(e)[:100]}")
                return ""
        
        return ""

    def batch_generate(self, tasks: List[Dict]) -> List[str]:
        """
        批量生成图像
        :param tasks: 任务列表，每个任务包含prompt、style等字段
        :return: 保存路径列表
        """
        tasks = [task for task in tasks if task.get("prompt") and task.get("style")]
        if not tasks:
            self._log_info("批量生图：无有效任务")
            return []

        self._log_info(f"开始批量生图，共{len(tasks)}个有效任务")
        batch_results = []
        for idx, task in enumerate(tasks, 1):
            prompt = task.get("prompt", "").strip()
            style = task.get("style", "").strip()
            model_key = task.get("model_key", None)
            image_size = task.get("image_size", None)
            self._log_info(f"批量任务{idx}/{len(tasks)}：主题={prompt}，风格={style}")
            result = self.generate_image(prompt, style, model_key, image_size)
            batch_results.append(result)

        self._log_info(f"批量生图完成，共{len(batch_results)}个结果")
        return batch_results


def mock_rag_retrieval(prompt: str, style: str) -> str:
    """模拟检索功能"""
    mock_data = {
        "元宵节花灯": "元宵节花灯文化：传统花灯多以红灯笼为基础，搭配龙、凤、牡丹等吉祥图案，色彩以红、金为主，象征团圆喜庆，常见造型有宫灯、走马灯等。",
        "端午节龙舟": "龙舟文化特点：传统龙舟船体修长，头部雕刻龙形，色彩鲜艳（红、黄、蓝为主），龙舟上插彩旗，体现端午节驱邪避灾、祈福安康的文化内涵。",
        "中秋节玉兔": "中秋玉兔元素：玉兔是中秋节核心象征之一，传统形象为白色玉兔持捣药杵，背景常搭配月亮、桂树，风格多温婉、静谧，色彩以白、黄、银为主。"
    }
    return mock_data.get(prompt, f"未检索到{prompt}的相关参考信息")


if __name__ == "__main__":
    try:
        try:
            from langchain_community.chat_models import ChatTongyi
            text_model = ChatTongyi(api_key=SecretStr(ALIYUN_API_KEY or ""), model="qwen-turbo")
        except Exception:
            if OPENAI_API_KEY:
                text_model = ChatOpenAI(model="gpt-3.5-turbo")
            else:
                print("错误：未配置文本生成模型API密钥")
                exit(1)
        
        model_configs = {
            "volc_seedream": {
                "name": "火山引擎Seedream 4.0",
                "api_url": "https://ark.cn-beijing.volces.com/api/v3/images/generations",
                "api_key": VOLC_SEEDREAM_API_KEY,
                "model_id": "doubao-seedream-4-0-250828",
                "image_size": "1024x1024",
                "supported_sizes": ["1024x1024", "2048x2048"],
                "timeout": 90,
                "max_retries": 2,
                "request_format": "volc"
            },
            "ali_sd_xl": {
                "name": "阿里云Stable Diffusion XL",
                "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
                "api_key": DASHSCOPE_API_KEY,
                "model_id": "stable-diffusion-xl",
                "image_size": "1024x1024",
                "supported_sizes": ["512x512", "1024x1024", "2048x2048"],
                "timeout": 120,
                "max_retries": 2,
                "request_format": "aliyun"
            }
        }
        
        aigc = ImageAIGC(text_model=text_model, model_configs=model_configs)

        print("\n=== 测试1：单图生成 ===")
        local_path = aigc.generate_image(
            prompt="中秋节玉兔",
            style="现代简约风"
        )
        if local_path:
            print(f"图片已保存到本地：{local_path}")
        else:
            print("图片生成失败")

        print("\n=== 测试2：连环画生成 ===")
        comic_result = aigc.generate_image(
            prompt="生成一个关于中秋节的连环画故事",
            style="传统连环画风格"
        )
        if comic_result:
            try:
                comic_data = json.loads(comic_result)
                if comic_data.get("type") == "comic":
                    print(f"连环画生成成功，共{comic_data['count']}幅画面：")
                    for idx, path in enumerate(comic_data["paths"], 1):
                        print(f"  第{idx}幅：{path}")
            except:
                print(f"结果：{comic_result}")

        print("\n=== 测试3：批量生图 ===")
        batch_tasks = [
            {"prompt": "中秋节玉兔", "style": "现代简约风"},
            {"prompt": "重阳节菊花", "style": "古典工笔风", "image_size": "512x512"},
            {"prompt": "春节春联", "style": "喜庆红黑风"},
            {"prompt": "元宵节花灯", "style": "传统红金风", "image_size": "2048x2048"}
        ]
        batch_results = aigc.batch_generate(batch_tasks)
        print("批量生图结果汇总：")
        for idx, local_path in enumerate(batch_results):
            task = batch_tasks[idx]
            print(
                f"任务{idx+1} - 主题：{task['prompt']} → 风格：{task['style']} → "
                f"保存路径：{local_path if local_path else '失败'}"
            )
    except ValueError as e:
        print(f"初始化失败：{str(e)}")
    except Exception as e:
        print(f"运行出错：{str(e)}")