# -*- coding: utf-8 -*-
"""
RAG基础类
提供RAG系统的公共方法，避免代码重复
"""
import os
import sys
import time
import re
import urllib.parse
from typing import List, Dict, Optional
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_openai import OpenAIEmbeddings
import requests
from bs4 import BeautifulSoup

# 添加项目根目录到路径
current_file_dir = os.path.dirname(os.path.realpath(__file__))
project_root = os.path.dirname(current_file_dir)
sys.path.insert(0, project_root)

from db_connection import get_user_db_connection
from dotenv import load_dotenv
import json

load_dotenv(override=True)

ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")

# 导入节日名称转换工具（延迟导入，避免循环依赖）
def _get_festival_name_utils():
    """延迟导入节日名称转换工具"""
    try:
        from festival_name_utils import chinese_to_english_festival
        return chinese_to_english_festival
    except ImportError:
        return lambda x: ""


class RAGBase:
    """RAG系统基础类，提供公共方法"""
    
    def __init__(self, persist_directory: str, database_name: str,
                 retrieval_tables: Optional[List[str]] = None, db_config: Optional[Dict] = None):
        """初始化RAG基础组件"""
        # 初始化嵌入模型
        try:
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
        self.retrieval_tables = retrieval_tables or [
            "cultural_resources", "cultural_entities", "entity_relationships",
            "AIGC_cultural_resources", "AIGC_graph", "crawled_images", "cultural_resources_from_user"
        ]
        
        self.conversation_history: List[Dict] = []
        self.db_config = db_config
        self.db_connection = None
    
    def _call_retriever(self, query: str) -> List[Document]:
        """从向量库检索相关文档"""
        if not self.retriever:
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
            print(f"检索器调用错误: {e}")
        return []
    
    def _get_db_connection(self, user_id: Optional[int] = None):
        """获取数据库连接（使用用户账户）"""
        try:
            if user_id is not None:
                conn = get_user_db_connection(user_id)
            else:
                conn = get_user_db_connection()
            
            if conn is None:
                if hasattr(self, 'db_config') and self.db_config:
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
    
    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history = []
    
    def query_database(self, query: str, table_names: Optional[List[str]] = None) -> List[Dict]:
        """
        从指定数据库表中检索相关内容（统一实现）
        此方法已从RAG.py迁移至此，供所有RAG类继承使用
        
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
        chinese_to_english_festival = _get_festival_name_utils()
        query_en = chinese_to_english_festival(query) if chinese_to_english_festival else ""
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
                        """
                        pattern_cn = f"%{query}%"
                        pattern_en = f"%{query_en}%" if query_en else pattern_cn
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
                                   period_era, geo_coordinates, cultural_region, 
                                   style_features, cultural_value, related_images_url, digital_resource_link
                            FROM cultural_entities
                            WHERE entity_name LIKE %s 
                               OR description LIKE %s 
                               OR entity_type LIKE %s
                               OR source LIKE %s
                               OR period_era LIKE %s
                               OR cultural_region LIKE %s
                               OR style_features LIKE %s
                               OR cultural_value LIKE %s
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern))
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
                            if row.get("style_features"):
                                content_parts.append(f"风格特征：{row.get('style_features')}")
                            if row.get("geo_coordinates"):
                                content_parts.append(f"地理坐标：{row.get('geo_coordinates')}")
                            
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
                        """
                        pattern_cn = f"%{query}%"
                        pattern_en = f"%{query_en}%" if query_en else pattern_cn
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
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            storage_path = row.get("storage_path", "")
                            # 构建完整路径：项目根目录的AIGC_graph文件夹 + storage_path（使用相对路径）
                            current_file_dir = os.path.dirname(os.path.realpath(__file__))
                            base_dir = os.path.dirname(current_file_dir)
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
                            SELECT ci.id, ci.file_name, ci.storage_path, ci.dimensions, ci.tags,
                                   ci.resource_id, ci.entity_id, ci.festival_name,
                                   cr.title as resource_title, ce.entity_name
                            FROM crawled_images ci
                            LEFT JOIN cultural_resources cr ON ci.resource_id = cr.id
                            LEFT JOIN cultural_entities ce ON ci.entity_id = ce.id
                            WHERE ci.file_name LIKE %s 
                               OR JSON_SEARCH(ci.tags, 'one', %s) IS NOT NULL
                               OR ci.festival_name LIKE %s
                               OR cr.title LIKE %s
                               OR ce.entity_name LIKE %s
                        """
                        pattern = f"%{query}%"
                        cursor.execute(sql, (pattern, pattern, pattern, pattern, pattern))
                        rows = cursor.fetchall()
                        for row in rows:
                            storage_path = row.get("storage_path", "")
                            # 构建完整路径：项目根目录的crawled_images文件夹 + storage_path（使用相对路径）
                            current_file_dir = os.path.dirname(os.path.realpath(__file__))
                            base_dir = os.path.dirname(current_file_dir)
                            full_path = os.path.join(base_dir, "crawled_images", storage_path) if storage_path else ""
                            # 如果storage_path已经是完整路径，直接使用
                            if not os.path.exists(full_path) and storage_path:
                                # 尝试直接使用storage_path
                                if os.path.exists(storage_path):
                                    full_path = storage_path
                                else:
                                    # 尝试从项目根目录查找
                                    full_path = os.path.join(base_dir, storage_path)
                            
                            results.append({
                                "table": "crawled_images",
                                "id": row.get("id"),
                                "title": row.get("file_name", ""),
                                "content": f"图片路径：{full_path}，尺寸：{row.get('dimensions', '未知')}，关联资源：{row.get('resource_title', '')}，关联实体：{row.get('entity_name', '')}",
                                "source": "爬虫抓取",
                                "url": full_path,
                                "image_path": full_path,
                                "resource_id": row.get("resource_id"),
                                "entity_id": row.get("entity_id")
                            })
                    
                    elif table == "cultural_resources_from_user":
                        # 用户上传资源表查询：同时搜索中英文，并解析JSON字段
                        sql = """
                            SELECT id, title, resource_type, content_feature_data, source_from, storage_path
                            FROM cultural_resources_from_user
                            WHERE title LIKE %s 
                               OR title LIKE %s
                               OR content_feature_data LIKE %s
                               OR JSON_EXTRACT(content_feature_data, '$.title') LIKE %s
                               OR JSON_EXTRACT(content_feature_data, '$.text') LIKE %s
                               OR JSON_EXTRACT(content_feature_data, '$.meta.festival_names') LIKE %s
                        """
                        pattern_cn = f"%{query}%"
                        pattern_en = f"%{query_en}%" if query_en else pattern_cn
                        cursor.execute(sql, (pattern_cn, pattern_en, pattern_cn, pattern_cn, pattern_cn, pattern_cn))
                        rows = cursor.fetchall()
                        for row in rows:
                            # 解析content_feature_data JSON字段
                            content_text = ""
                            try:
                                content_data = json.loads(row.get("content_feature_data", "{}"))
                                if isinstance(content_data, dict):
                                    content_text = content_data.get("text", "") or content_data.get("title", "") or content_data.get("content_full", "")
                                else:
                                    content_text = str(content_data)
                            except:
                                content_text = str(row.get("content_feature_data", ""))
                            
                            results.append({
                                "table": "cultural_resources_from_user",
                                "id": row.get("id"),
                                "title": row.get("title", ""),
                                "content": content_text[:2000] if content_text else "",
                                "source": row.get("source_from", "用户上传"),
                                "url": "",
                                "storage_path": row.get("storage_path", "")
                            })
        
        except Exception as e:
            import traceback
            print(f"[RAG] 数据库查询错误: {e}")
            print(f"[RAG] 查询错误堆栈: {traceback.format_exc()}")
        
        print(f"[RAG] query_database返回 {len(results)} 条结果")
        return results

