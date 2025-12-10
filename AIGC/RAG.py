import concurrent.futures
import hashlib
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union
import json
import random
import textwrap
import re
import time
import urllib.parse

import pandas as pd
from dotenv import load_dotenv
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from sqlalchemy import create_engine, text, inspect
from tqdm import tqdm

from langchain_community.vectorstores import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import WebBaseLoader
from openai import OpenAI
import requests
from bs4 import BeautifulSoup

load_dotenv(override=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")
VOLC_SEEDREAM_API_KEY = os.getenv("VOLC_SEEDREAM_API_KEY")

# 导入统一的数据库连接模块（从父目录）
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_connection import get_user_db_config, get_user_db_connection
from festival_name_utils import chinese_to_english_festival, extract_and_convert_festival_name


class CulturalResourceRAG:
    """
    传统节日文化资源RAG系统
    支持从数据库和网页检索传统节日相关信息，生成高质量回答
    同时支持基于节日主题生成原创文化资源内容
    """

    def __init__(self, model, embedding_model_name='text-embedding-ada-002',
                 persist_directory="./chroma_db", database_name="java-project",
                 retrieval_tables=None, db_config=None):
        print("正在初始化 RAG 系统")
        self.model = model

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
            print("检索器初始化成功")
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

        # 自反思与性能记录存储
        self.reflection_history = []
        self.performance_log = []

        # 问答输出解析器（定义结构化输出字段）
        response_schemas = [
            ResponseSchema(name="answer", description="针对用户问题的详细回答，语言风格需典雅、准确。"),
            ResponseSchema(name="key_entities", description="回答中提到的关键文化实体（如节日名、习俗、文物等），以列表形式返回。"),
            ResponseSchema(name="sources", description="回答所依据的参考资料来源（如《xx志》、xx网页），若无明确来源则为空。"),
            ResponseSchema(name="confidence", description="对回答准确性的置信度评分（0-10）。")
        ]
        self.output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
        self.format_instructions = self.output_parser.get_format_instructions()

        template = textwrap.dedent("""
        你是一位专门研究中国传统节日的文化学者。请基于提供的【参考资料】和【对话历史】回答用户关于传统节日的【问题】。

        【参考资料】：
        {context}

        【对话历史】：
        {conversation_history}

        【用户问题】：
        {question}

        【回答要求】：
        1. 准确性：严格依据参考资料回答，涉及节日名称、起源、习俗、传说、时间、地域特色等要准确无误。如资料不足，明确说明。
        2. 结构化：必须按照指定的JSON格式输出，不要包含任何其他解释性文字。
        3. 风格：语言典雅、准确，符合公共文化服务场景，突出传统节日的文化内涵和民俗价值。
        4. 重点：关注节日的文化意义、传统习俗、历史演变、地域特色等公共文化资源相关内容。
        5. 连贯性：如果对话历史中有相关信息，请结合历史对话内容，使回答更加连贯和完整。

        {format_instructions}
        """)
        self.rag_prompt = PromptTemplate(template=template,
                                         input_variables=["context", "question", "conversation_history"],
                                         partial_variables={"format_instructions": self.format_instructions})

        self.reflection_prompt = PromptTemplate(
            template=textwrap.dedent("""
            你负责评估关于传统节日问题的回答质量。

            问题: {question}
            RAG系统回答: {answer}
            上下文: {context}

            请评估回答质量并提供以下信息：
            1. 回答准确性（0-10分），特别关注节日相关信息的准确性
            2. 是否需要更多信息（是/否）
            3. 改进建议
            4. 是否需要重新检索（是/否）

            请以JSON格式返回评估结果：
            {{
                "accuracy_score": <分数>,
                "needs_more_info": "<是/否>",
                "improvement_suggestions": "<建议>",
                "requires_retrieval": "<是/否>"
            }}
            """),
            input_variables=["question", "answer", "context"]
        )

        # 文化资源生成输出解析器（定义原创资源的结构化字段）
        gen_schemas = [
            ResponseSchema(name="title", description="新文化资源的标题，简洁"),
            ResponseSchema(name="type", description="资源类型，如：传说/仪式/符号/节庆活动等"),
            ResponseSchema(name="story", description="关于此资源的完整叙事（不超过400字）"),
            ResponseSchema(name="rituals", description="一到三项可执行的仪式或民俗描述"),
            ResponseSchema(name="symbols", description="新的象征或物件及其含义"),
            ResponseSchema(name="usage", description="如何在社区/活动中推广和使用（简短建议）"),
            ResponseSchema(name="novelty_explanation", description="为什么该资源具有原创性与文化价值（简短说明）")
        ]
        self.gen_output_parser = StructuredOutputParser.from_response_schemas(gen_schemas)
        self.gen_format_instructions = self.gen_output_parser.get_format_instructions()

        self.gen_prompt_template = PromptTemplate(
            template=textwrap.dedent("""
            你是一位富有创造力的传统节日文化研究者。
            输入：传统节日名称："{festival}"，以及可选提示："{hint}"。
            任务：基于该传统节日的文化主题与情感内涵，创造一个新的公共文化资源（可以是新的故事、仪式、象征或节庆活动），
            要求：
              1) 必须原创，不要复刻或明显模仿任何已知传说或真实节日活动。
              2) 必须深入体现传统节日的文化内涵、历史渊源、民俗传统和象征意义，具有公共文化资源的特性。
              3) 内容要富有文化特色，不能看起来毫无文化特色，要体现传统元素和文化传承价值。
              4) 风格自然、具有人情味，符合传统节日的文化氛围，避免模板化文本。
              5) 输出必须严格按照指定的JSON格式（不要包含多余文字）。
            输出格式说明（遵守 JSON）：
            {format_instructions}
            """),
            input_variables=["festival", "hint"],
            partial_variables={"format_instructions": self.gen_format_instructions}
        )

        print("RAG 初始化完成。")

    def _call_model(self, prompt_text: str) -> str:
        """
        统一模型调用接口，兼容不同SDK的返回格式
        :param prompt_text: 输入给模型的提示文本
        :return: 模型返回的纯文本内容
        """
        try:
            print(f"[RAG] 调用模型，提示词长度: {len(prompt_text)}")
            if hasattr(self.model, "invoke"):
                resp = self.model.invoke(prompt_text)
                if isinstance(resp, str):
                    print(f"[RAG] 模型返回字符串，长度: {len(resp)}")
                    return resp
                content = getattr(resp, "content", None)
                if content is not None:
                    print(f"[RAG] 从content属性获取，长度: {len(str(content))}")
                    return str(content)
                text = getattr(resp, "text", None)
                if text is not None:
                    print(f"[RAG] 从text属性获取，长度: {len(str(text))}")
                    return str(text)
                print(f"[RAG] 直接转换为字符串")
                return str(resp)
            elif callable(self.model):
                resp = self.model(prompt_text)
                if isinstance(resp, str):
                    return resp
                content = getattr(resp, "content", None)
                if content is not None:
                    return str(content)
                text = getattr(resp, "text", None)
                if text is not None:
                    return str(text)
                return str(resp)
            else:
                raise RuntimeError("未知模型接口：既没有 invoke 方法，也不可直接调用。")
        except Exception as e:
            import traceback
            print(f"[RAG] 模型调用错误: {e}")
            print(f"[RAG] 错误堆栈: {traceback.format_exc()}")
            raise

    def _call_retriever(self, query: str) -> List[Document]:
        """
        从向量库检索相关文档
        :param query: 查询关键词
        :return: 检索到的文档列表
        """
        if not self.retriever:
            return []
        try:
            if hasattr(self.retriever, "invoke"):
                # 直接传入字符串查询（Chroma检索器要求）
                docs = self.retriever.invoke(query)
                if isinstance(docs, list):
                    return docs
                return list(docs)
            if hasattr(self.retriever, "get_relevant_documents") and callable(self.retriever.get_relevant_documents):
                return self.retriever.get_relevant_documents(query)
            if callable(self.retriever):
                return self.retriever(query)
        except Exception as e:
            print(f"检索器调用错误: {e}")
        return []

    def _get_db_connection(self, user_id: Optional[int] = None):
        """获取数据库连接（使用用户账户）"""
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
            print(f"数据库连接失败: {e}")
            return None

    def query_database(self, query: str, table_names: Optional[List[str]] = None) -> List[Dict]:
        """
        从指定数据库表中检索相关内容
        :param query: 检索关键词
        :param table_names: 要查询的表名列表（默认使用初始化时的retrieval_tables）
        :return: 检索结果列表
        """
        if table_names is None:
            table_names = self.retrieval_tables
        
        conn = self._get_db_connection()
        if not conn:
            print("[RAG] 数据库连接失败，无法检索")
            return []
        
        results = []
        # 提取/截断关键词，避免整段描述导致 LIKE 失效
        raw_q = query.strip()
        # 简单按常见分隔符拆分，取前2~3段，最多取前30字
        parts = []
        for sep in ["。", "！", "？", "，", ",", ".", ";", "；", "\n"]:
            if sep in raw_q:
                parts = raw_q.split(sep)
                break
        if not parts:
            parts = [raw_q]
        keywords = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            keywords.append(p[:30])  # 每段最多30字
            if len(keywords) >= 3:
                break
        if not keywords:
            keywords = [raw_q[:30]]
        
        
        # 将查询词转换为英文节日名称（用于匹配title字段）
        query_en = chinese_to_english_festival(query)
        print(f"[RAG] 查询词：{query}，英文转换：{query_en}")
        
        try:
            with conn.cursor() as cursor:
                for table in table_names:
                    if table == "cultural_resources":
                        # 改进查询：同时搜索中英文，并解析JSON字段
                        sql = """
                            SELECT id, title, resource_type, content_feature_data, source_from, source_url
                            FROM cultural_resources
                            WHERE title LIKE %s 
                               OR title LIKE %s
                               OR content_feature_data LIKE %s
                               OR JSON_EXTRACT(content_feature_data, '$.title') LIKE %s
                               OR JSON_EXTRACT(content_feature_data, '$.text') LIKE %s
                               OR JSON_EXTRACT(content_feature_data, '$.meta.festival_names') LIKE %s
                            LIMIT 20
                        """
                        pattern_cn = f"%{query}%"
                        pattern_en = f"%{query_en}%"
                        cursor.execute(sql, (pattern_cn, pattern_en, pattern_cn, pattern_cn, pattern_cn, pattern_cn))
                        rows = cursor.fetchall()
                        for row in rows:
                            # 解析content_feature_data JSON字段
                            content_text = ""
                            try:
                                content_data = json.loads(row.get("content_feature_data", "{}"))
                                if isinstance(content_data, dict):
                                    content_text = content_data.get("text", "") or content_data.get("title", "")
                                else:
                                    content_text = str(content_data)
                            except:
                                content_text = str(row.get("content_feature_data", ""))
                            
                            results.append({
                                "table": "cultural_resources",
                                "id": row.get("id"),
                                "title": row.get("title", ""),
                                "content": content_text[:2000] if content_text else "",
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
                        # 改进查询：同时搜索中英文，并解析JSON字段
                        sql = """
                            SELECT id, title, resource_type, content_feature_data, source_from
                            FROM AIGC_cultural_resources
                            WHERE title LIKE %s 
                               OR title LIKE %s
                               OR content_feature_data LIKE %s
                               OR JSON_EXTRACT(content_feature_data, '$.title') LIKE %s
                               OR JSON_EXTRACT(content_feature_data, '$.text') LIKE %s
                               OR JSON_EXTRACT(content_feature_data, '$.meta.festival_names') LIKE %s
                            LIMIT 20
                        """
                        pattern_cn = f"%{query}%"
                        pattern_en = f"%{query_en}%"
                        cursor.execute(sql, (pattern_cn, pattern_en, pattern_cn, pattern_cn, pattern_cn, pattern_cn))
                        rows = cursor.fetchall()
                        for row in rows:
                            # 解析content_feature_data JSON字段
                            content_text = ""
                            try:
                                content_data = json.loads(row.get("content_feature_data", "{}"))
                                if isinstance(content_data, dict):
                                    content_text = content_data.get("text", "") or content_data.get("title", "")
                                else:
                                    content_text = str(content_data)
                            except:
                                content_text = str(row.get("content_feature_data", ""))
                            
                            results.append({
                                "table": "AIGC_cultural_resources",
                                "id": row.get("id"),
                                "title": row.get("title", ""),
                                "content": content_text[:2000] if content_text else "",
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
        
        except Exception as e:
            import traceback
            print(f"[RAG] 数据库查询错误: {e}")
            print(f"[RAG] 查询错误堆栈: {traceback.format_exc()}")
        
        print(f"[RAG] query_database返回 {len(results)} 条结果")
        return results

    def ingest_data(self, documents: List[Document]):
        """
        将文档分割后存入向量库
        :param documents: 待处理的文档列表
        """
        if not documents:
            print("没有需要加载的文档。")
            return
        print(f"开始加载 {len(documents)} 篇文档...")
        chunks = self.text_splitter.split_documents(documents)
        print(f"文档被分割为 {len(chunks)} 个块。")
        try:
            if hasattr(self.vector_store, "add_documents"):
                self.vector_store.add_documents(chunks)
            else:
                raise RuntimeError("当前 VectorStore 不支持 add_documents 方法")
            if hasattr(self.vector_store, "persist"):
                self.vector_store.persist()
            print(f"数据已成功加载并索引到 {self._persist_directory}")
        except Exception as e:
            print(f"向量库写入错误: {e}")

    def self_reflect(self, question: str, answer: str, context: str) -> Dict:
        """
        评估回答质量，提供改进建议
        :param question: 用户问题
        :param answer: 生成的回答
        :param context: 检索到的上下文
        :return: 评估结果字典
        """
        reflection_input = {"question": question, "answer": answer, "context": context}
        try:
            prompt_text = self.reflection_prompt.format(**reflection_input)
            reflection_text = self._call_model(prompt_text)
            try:
                reflection_data = json.loads(reflection_text)
                # 补全缺失字段，保证格式统一
                reflection_data = {
                    "accuracy_score": reflection_data.get("accuracy_score", 5),
                    "needs_more_info": reflection_data.get("needs_more_info", "否"),
                    "improvement_suggestions": reflection_data.get("improvement_suggestions", ""),
                    "requires_retrieval": reflection_data.get("requires_retrieval", "否")
                }
            except json.JSONDecodeError:
                reflection_data = {
                    "accuracy_score": 5,
                    "needs_more_info": "否",
                    "improvement_suggestions": "无法解析反思结果",
                    "requires_retrieval": "否"
                }
            self.reflection_history.append({
                "question": question,
                "answer": answer,
                "context": context,
                "reflection": reflection_data,
                "timestamp": datetime.now()
            })
            return reflection_data
        except Exception as e:
            print(f"自反思过程中出现错误: {e}")
            return {
                "accuracy_score": 5,
                "needs_more_info": "否",
                "improvement_suggestions": f"反思错误: {e}",
                "requires_retrieval": "否"
            }

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
            # 这里使用 OpenAI 的 vision API 或类似的视觉模型
            if hasattr(self.model, "invoke") and hasattr(self.model, "with_structured_output"):
                # 如果模型支持图片输入
                try:
                    from PIL import Image
                    img = Image.open(image_path)
                    # 这里需要根据实际使用的模型API来调用
                    # 示例：使用 OpenAI Vision API
                    if OPENAI_API_KEY:
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
                    print(f"图片读取失败: {e}")
                    return f"图片路径：{image_path}（无法读取图片内容）"
            return f"图片路径：{image_path}"
        except Exception as e:
            print(f"读取图片信息出错: {e}")
            return None
    
    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history = []
    
    def ask(self, query: str, image_paths: Optional[List[str]] = None, 
            session_id: Optional[int] = None, use_history: bool = True) -> Dict:
        """
        回答用户关于传统节日的问题（支持多轮对话和图片输入）
        :param query: 用户问题
        :param image_paths: 图片路径列表（可选）
        :param session_id: 会话ID（可选，用于持久化对话）
        :param use_history: 是否使用对话历史
        :return: 包含回答、关键实体、来源、置信度的字典
        """
        print(f"收到问题: {query}")
        if image_paths:
            print(f"附带图片: {image_paths}")
        
        # 读取图片信息
        image_context = ""
        if image_paths:
            image_descriptions = []
            for img_path in image_paths:
                img_info = self._read_image_info(img_path)
                if img_info:
                    image_descriptions.append(img_info)
            if image_descriptions:
                image_context = "\n".join(image_descriptions)
                print(f"图片信息: {image_context[:200]}...")
        
        context_parts = []
        
        # 添加图片信息到上下文
        if image_context:
            context_parts.append(f"用户上传的图片信息：\n{image_context}")
        
        # 保存检索结果用于后续返回
        vector_docs = []
        db_results = []
        web_docs = []
        
        try:
            vector_docs = self._call_retriever(query)
            vector_context = "\n".join([getattr(d, "page_content", str(d)) for d in vector_docs]) if vector_docs else ""
            if vector_context:
                context_parts.append(f"向量库检索结果：\n{vector_context}")
        except Exception as e:
            print(f"向量数据库检索错误: {e}")
            vector_context = ""

        if self.retrieval_tables:
            try:
                print(f"[RAG] 开始数据库检索，查询词：{query}")
                db_results = self.query_database(query, self.retrieval_tables)
                print(f"[RAG] 数据库检索完成，找到 {len(db_results)} 条结果")
                if db_results:
                    db_context_parts = []
                    for result in db_results:
                        db_text = f"来源表：{result.get('table', '')}\n"
                        if result.get('title'):
                            db_text += f"标题：{result.get('title')}\n"
                        if result.get('content'):
                            db_text += f"内容：{result.get('content')}\n"
                        if result.get('source'):
                            db_text += f"来源：{result.get('source')}\n"
                        db_context_parts.append(db_text)
                    context_parts.append(f"数据库检索结果：\n" + "\n---\n".join(db_context_parts))
                    print(f"[RAG] 数据库检索结果已添加到上下文")
                else:
                    print(f"[RAG] 警告：数据库检索未找到匹配结果，查询词：{query}")
            except Exception as e:
                import traceback
                print(f"[RAG] 数据库查询过程中出现错误: {e}")
                print(f"[RAG] 错误堆栈: {traceback.format_exc()}")
        
        context = "\n\n".join(context_parts) if context_parts else ""
        
        if not context or len(context.strip()) < 50:
            print("数据库和向量库中未找到相关信息，尝试从网页爬取...")
            try:
                web_docs = self._crawl_web_content(query, max_results=3)
                if web_docs:
                    web_context = "\n\n".join([getattr(d, "page_content", str(d)) for d in web_docs])
                    if web_context:
                        context_parts.append(f"网页检索结果：\n{web_context}")
                        context = "\n\n".join(context_parts)
                        
                        web_sources = [d.metadata.get("source", "") for d in web_docs if d.metadata.get("source")]
                        if web_sources:
                            print(f"已从以下网页获取信息: {', '.join(web_sources[:2])}")
            except Exception as e:
                print(f"网页爬取失败: {e}")

        # 构建对话历史文本
        conversation_history_text = ""
        if use_history and self.conversation_history:
            history_parts = []
            for hist in self.conversation_history[-5:]:  # 只保留最近5轮对话
                if hist.get("role") == "user":
                    history_parts.append(f"用户：{hist.get('content', '')}")
                elif hist.get("role") == "assistant":
                    history_parts.append(f"助手：{hist.get('content', '')}")
            conversation_history_text = "\n".join(history_parts)
        
        # 3. 生成回答（保证结构化输出）
        try:
            prompt_text = self.rag_prompt.format(
                context=context or "", 
                question=query or "",
                conversation_history=conversation_history_text or "无对话历史"
            )
            print(f"[RAG] 调用模型生成回答...")
            raw_text = self._call_model(prompt_text)
            print(f"[RAG] 模型返回文本长度: {len(raw_text) if raw_text else 0}")
            # 解析结构化输出，补全缺失字段
            try:
                parsed = self.output_parser.parse(raw_text)
                parsed = {
                    "answer": parsed.get("answer", ""),
                    "key_entities": parsed.get("key_entities", []),
                    "sources": parsed.get("sources", ""),
                    "confidence": parsed.get("confidence", 0)
                }
            except Exception as e:
                import traceback
                print(f"[RAG] 解析回答失败: {e}")
                print(f"[RAG] raw_text前200字符: {raw_text[:200] if raw_text else 'None'}")
                print(f"[RAG] 解析错误堆栈: {traceback.format_exc()}")
                # 解析失败时返回标准格式，使用原始文本作为答案
                parsed = {
                    "answer": raw_text if raw_text else "抱歉，无法解析模型返回的内容",
                    "key_entities": [],
                    "sources": "",
                    "confidence": 0
                }
        except Exception as e:
            import traceback
            print(f"[RAG] 生成回答时出现错误: {e}")
            print(f"[RAG] 错误堆栈: {traceback.format_exc()}")
            parsed = {
                "answer": f"回答生成失败：{str(e)}",
                "key_entities": [],
                "sources": "",
                "confidence": 0
            }

        # 4. 自反思评估，必要时重新检索生成
        reflection_result = None
        try:
            reflection_result = self.self_reflect(query, json.dumps(parsed, ensure_ascii=False), context)
            if reflection_result.get("requires_retrieval") == "是":
                print("根据自反思结果，重新检索并生成...")
                additional_context = self._get_additional_context(query, reflection_result)
                if additional_context:
                    enhanced_context = f"{context}\n\n补充信息:\n{additional_context}"
                    prompt_text2 = self.rag_prompt.format(context=enhanced_context, question=query)
                    raw_text2 = self._call_model(prompt_text2)
                    try:
                        parsed = self.output_parser.parse(raw_text2)
                        parsed = {
                            "answer": parsed.get("answer", ""),
                            "key_entities": parsed.get("key_entities", []),
                            "sources": parsed.get("sources", ""),
                            "confidence": parsed.get("confidence", 0)
                        }
                    except Exception:
                        parsed = {
                            "answer": raw_text2,
                            "key_entities": [],
                            "sources": "",
                            "confidence": 0
                        }
        except Exception as e:
            print(f"自反思阶段错误: {e}")
            reflection_result = {
                "accuracy_score": 5,
                "needs_more_info": "否",
                "improvement_suggestions": f"反思错误: {e}",
                "requires_retrieval": "否"
            }

        # 5. 更新对话历史
        if use_history:
            self.conversation_history.append({
                "role": "user",
                "content": query,
                "image_paths": image_paths or [],
                "timestamp": datetime.now()
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": parsed.get("answer", ""),
                "timestamp": datetime.now()
            })
            # 限制历史记录长度，只保留最近20轮对话
            if len(self.conversation_history) > 40:
                self.conversation_history = self.conversation_history[-40:]
        
        # 6. 记录性能日志
        try:
            self.performance_log.append({
                "question": query,
                "answer": parsed,
                "accuracy_score": reflection_result.get("accuracy_score", 5),
                "timestamp": datetime.now()
            })
        except Exception as e:
            print(f"记录性能日志失败: {e}")

        # 7. 整理检索到的资源信息
        retrieved_resources = {
            "vector_results": [],
            "database_results": db_results,
            "web_results": []
        }
        
        # 向量库结果
        if vector_docs:
            for doc in vector_docs:
                retrieved_resources["vector_results"].append({
                    "content": getattr(doc, "page_content", str(doc))[:500],  # 限制长度
                    "metadata": getattr(doc, "metadata", {})
                })
        
        # 网页爬取结果
        if web_docs:
            for doc in web_docs:
                retrieved_resources["web_results"].append({
                    "content": getattr(doc, "page_content", str(doc))[:500],  # 限制长度
                    "source": getattr(doc, "metadata", {}).get("source", ""),
                    "title": getattr(doc, "metadata", {}).get("title", "")
                })

        # 返回结果，包含检索到的资源
        result = {
            **parsed,
            "retrieved_resources": retrieved_resources
        }
        
        return result

    def _crawl_web_content(self, query: str, max_results: int = 3) -> List[Document]:
        """
        当数据库中没有相关信息时，从网页获取传统节日相关内容
        :param query: 查询关键词
        :param max_results: 最多获取的结果数
        :return: 文档列表
        """
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

    def _get_additional_context(self, query: str, reflection_result: Dict) -> str:
        """
        根据反思建议获取补充检索上下文
        :param query: 原始查询
        :param reflection_result: 反思结果
        :return: 补充的上下文文本
        """
        improvement_suggestions = reflection_result.get("improvement_suggestions", "")
        try:
            docs = self._call_retriever(f"{query} {improvement_suggestions}")
            return "\n".join([getattr(d, "page_content", str(d)) for d in docs]) if docs else ""
        except Exception as e:
            print(f"获取额外上下文时出错: {e}")
            return ""

    def generate_resource_from_festival(self, festival: str, user_hint: str = "") -> Dict:
        """
        基于传统节日主题生成原创文化资源
        :param festival: 节日名称
        :param user_hint: 可选的创作提示
        :return: 包含标题、类型、故事等字段的字典
        """
        # 检索节日相关上下文（仅作创作灵感，避免抄袭）
        try:
            docs = self._call_retriever(festival)
            context_snippet = "\n".join([getattr(d, "page_content", "") for d in docs])[:2000] if docs else ""
        except Exception as e:
            print(f"检索节日上下文失败: {e}")
            context_snippet = ""

        # 生成创作Prompt
        try:
            prompt_text = self.gen_prompt_template.format(festival=festival, hint=user_hint)
        except Exception as e:
            print(f"生成Prompt失败: {e}")
            prompt_text = self.gen_prompt_template.template.format(
                festival=festival, hint=user_hint, format_instructions=self.gen_format_instructions
            )
        
        # 追加灵感参考（强调原创要求）
        if context_snippet:
            prompt_text += f"\n\n注意：下面是供灵感使用的简短参考（禁止复刻或抄袭）：\n{context_snippet}\n\n请严格遵守原创要求。"

        # 调用模型生成资源
        try:
            raw_text = self._call_model(prompt_text)
        except Exception as e:
            print(f"生成文化资源时模型调用失败: {e}")
            # 生成失败返回标准格式
            return {
                "title": f"{festival} · 新文化资源",
                "type": "未知类型",
                "story": f"生成失败：{str(e)}",
                "rituals": "",
                "symbols": "",
                "usage": "",
                "novelty_explanation": ""
            }

        # 解析生成结果，保证字段完整性
        try:
            parsed = self.gen_output_parser.parse(raw_text)
            parsed = {
                "title": parsed.get("title", f"{festival} · 新文化资源"),
                "type": parsed.get("type", "传说/仪式混合"),
                "story": parsed.get("story", ""),
                "rituals": parsed.get("rituals", ""),
                "symbols": parsed.get("symbols", ""),
                "usage": parsed.get("usage", ""),
                "novelty_explanation": parsed.get("novelty_explanation", "")
            }
            return parsed
        except Exception as e:
            print(f"解析生成结果失败: {e}\nraw_text:\n{raw_text}")
            # 尝试抽取JSON片段解析
            try:
                start = raw_text.index("{")
                end = raw_text.rindex("}") + 1
                candidate = raw_text[start:end]
                parsed = json.loads(candidate)
                parsed = {
                    "title": parsed.get("title", f"{festival} · 新文化资源"),
                    "type": parsed.get("type", "传说/仪式混合"),
                    "story": parsed.get("story", ""),
                    "rituals": parsed.get("rituals", ""),
                    "symbols": parsed.get("symbols", ""),
                    "usage": parsed.get("usage", ""),
                    "novelty_explanation": parsed.get("novelty_explanation", "")
                }
                return parsed
            except Exception as ee:
                # 最终降级返回标准格式
                fallback = {
                    "title": f"{festival} · 新文化资源",
                    "type": "传说/仪式混合",
                    "story": raw_text[:800] if raw_text else "暂无内容",
                    "rituals": "暂无仪式描述",
                    "symbols": "暂无象征定义",
                    "usage": "暂无推广建议",
                    "novelty_explanation": f"解析失败：{str(ee)}，返回原始文本片段"
                }
                return fallback

    def format_generated_resource(self, resource_dict: Dict) -> str:
        """
        将生成的文化资源格式化为易读文本
        :param resource_dict: 文化资源字典
        :return: 格式化后的文本字符串
        """
        # 提取所有字段并处理空值
        title = resource_dict.get("title", "未命名文化资源")
        res_type = resource_dict.get("type", "未知类型")
        story = resource_dict.get("story", "暂无故事内容")
        rituals = resource_dict.get("rituals", "暂无仪式描述")
        symbols = resource_dict.get("symbols", "暂无象征定义")
        usage = resource_dict.get("usage", "暂无推广建议")
        novelty = resource_dict.get("novelty_explanation", "暂无原创性说明")

        # 整合为易读的文本格式
        formatted = textwrap.dedent(f"""
        ===================== 原创文化资源 =====================
        标题：{title}
        类型：{res_type}
        -----------------------------------------------------
        核心故事：
        {story}
        -----------------------------------------------------
        仪式/民俗：
        {rituals}
        -----------------------------------------------------
        象征含义：
        {symbols}
        -----------------------------------------------------
        推广建议：
        {usage}
        -----------------------------------------------------
        原创价值：
        {novelty}
        =====================================================
        """).strip()
        
        return formatted

    def extract_resource_fields(self, resource_dict: Dict) -> Tuple[str, str, str, str, str, str, str]:
        """
        提取文化资源的各个字段
        :param resource_dict: 文化资源字典
        :return: 包含标题、类型、故事等字段的元组
        """
        return (
            resource_dict.get("title", ""),
            resource_dict.get("type", ""),
            resource_dict.get("story", ""),
            resource_dict.get("rituals", ""),
            resource_dict.get("symbols", ""),
            resource_dict.get("usage", ""),
            resource_dict.get("novelty_explanation", "")
        )

    def get_performance_summary(self) -> Dict:
        """
        获取系统性能统计信息
        :return: 包含问题数、平均准确率等统计数据的字典
        """
        if not self.performance_log:
            return {"message": "暂无性能数据"}
        total_questions = len(self.performance_log)
        avg_accuracy = sum([log.get("accuracy_score", 5) for log in self.performance_log]) / total_questions
        high_quality_responses = len([log for log in self.performance_log if log.get("accuracy_score", 5) > 7])
        return {
            "total_questions": total_questions,
            "average_accuracy": round(avg_accuracy, 2),
            "high_quality_responses": high_quality_responses,
            "improvement_rate": round(high_quality_responses / total_questions * 100, 2)
        }

    def update_retrieval_tables(self, table_names: List[str]):
        """
        更新要检索的数据库表列表
        :param table_names: 表名列表
        """
        self.retrieval_tables = table_names
        print(f"已更新检索表列表: {table_names} (数据库功能已禁用)")


# 主函数（测试用）
if __name__ == '__main__':
    print(f"DASHSCOPE_API_KEY: {'已设置' if ALIYUN_API_KEY else '未设置'}")
    print(f"OPENAI_API_KEY: {'已设置' if OPENAI_API_KEY else '未设置'}")
    if not ALIYUN_API_KEY and not OPENAI_API_KEY:
        print("错误：未找到 API 密钥，请检查 .env 或环境变量")
        exit(1)

    try:
        from langchain_community.chat_models import ChatTongyi
        from pydantic import SecretStr
        model = ChatTongyi(api_key=SecretStr(ALIYUN_API_KEY or ""), model="qwen-turbo")
    except Exception as e:
        print(f"ChatTongyi 初始化失败: {e}，尝试使用 OpenAI ChatOpenAI 作为后备。")
        if OPENAI_API_KEY:
            model = ChatOpenAI(model="gpt-3.5-turbo")
        else:
            print("无法初始化任何模型，请检查 API 密钥")
            exit(1)

    web_db_path = "./chroma_db_web"
    retrieval_tables = ["cultural_resources", "cultural_entities", "entity_relationships", "AIGC_cultural_resources"]
    rag_system = CulturalResourceRAG(model=model, persist_directory=web_db_path, 
                                     database_name="java-project", retrieval_tables=retrieval_tables)

    # 测试：生成中秋节原创文化资源
    festival = "中秋节"
    hint = "团圆、回忆、流动的时间感"
    print("\n--- 生成原创文化资源（结构化JSON） ---")
    resource_dict = rag_system.generate_resource_from_festival(festival, hint)
    print(json.dumps(resource_dict, ensure_ascii=False, indent=2))

    # 测试：完整提取并格式化展示
    print("\n--- 完整提取整合后的文化资源（易读格式） ---")
    formatted_resource = rag_system.format_generated_resource(resource_dict)
    print(formatted_resource)

    # 测试：单独提取每个字段（按需使用）
    print("\n--- 单独提取每个字段示例 ---")
    title, res_type, story, rituals, symbols, usage, novelty = rag_system.extract_resource_fields(resource_dict)
    print(f"标题单独提取：{title}")
    print(f"核心故事单独提取：\n{story}")

    # 测试：传统文化问答
    print("\n--- 测试问答示例 ---")
    q = "中秋月圆之夜，全国人民阖家团聚。"
    ans = rag_system.ask(q)
    print(json.dumps(ans, ensure_ascii=False, indent=2))

    # 输出性能摘要
    print("\n--- 系统性能摘要 ---")
    print(json.dumps(rag_system.get_performance_summary(), ensure_ascii=False, indent=2))



