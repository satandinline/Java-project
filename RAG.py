import concurrent.futures
import hashlib
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union
import json

import pandas as pd
from dotenv import load_dotenv
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from sqlalchemy import create_engine, text
from tqdm import tqdm
from langchain_community.vectorstores import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import WebBaseLoader
from openai import OpenAI


load_dotenv(override=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")


class CulturalResourceRAG:
    def __init__(self, model, embedding_model_name='text-embedding-ada-002', 
                 persist_directory="./chroma_db", database_name="culture", 
                 retrieval_tables=None):
        print(f"正在初始化 RAG 系统")
        
        self.model = model
        
        # 修正DashScopeEmbeddings的参数名称
        try:
            from langchain_community.embeddings import DashScopeEmbeddings
            self.embedding_model = DashScopeEmbeddings(
                dashscope_api_key=ALIYUN_API_KEY, 
                model="text-embedding-v2"
            )
        except Exception as e:
            print(f"DashScopeEmbeddings初始化失败: {e}")
            # 如果DashScopeEmbeddings不可用，使用OpenAIEmbeddings作为备选
            self.embedding_model = OpenAIEmbeddings(
                openai_api_key=OPENAI_API_KEY
            )

        # 2. 文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        
        # 3. 向量数据库
        self.vector_store = Chroma(persist_directory=persist_directory, embedding_function=self.embedding_model)
        
        # 4. 检索器
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
        
        # 5. 数据库配置
        self.database_name = database_name
        self.retrieval_tables = retrieval_tables or []
        
        # 6. 自反思机制相关
        self.reflection_history = []
        self.performance_log = []
        
        # 7. Prompt模板
        template = """
        你是一个专业的文化资源问答助手
        ---
        上下文:
        {context}
        ---
        问题: {question}
        ---
        你的回答:
        """
        self.rag_prompt = PromptTemplate(template=template, input_variables=["context", "question"])
        
        # 8. 自反思Prompt
        self.reflection_prompt = PromptTemplate(
            template="""
            你是一个AI助手，负责评估RAG系统的回答质量并提供改进建议。
            
            问题: {question}
            RAG系统回答: {answer}
            上下文: {context}
            
            请评估回答的质量并提供以下信息：
            1. 回答准确性（0-10分）
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
            """,
            input_variables=["question", "answer", "context"]
        )
        
        # 9. RAG链
        self.rag_chain = (
            {"context": self.retriever, "question": RunnablePassthrough()}
            | self.rag_prompt
            | self.model
            | StrOutputParser()
        )
        
        print("RAG初始化完成。")

    def query_database(self, query: str, table_names: List[str] = None) -> List[Dict]:
        """
        从数据库中检索相关信息
        """
        if not table_names:
            table_names = self.retrieval_tables
            
        if not table_names:
            return []
            
        # 这里需要根据实际数据库连接配置进行调整
        # 示例使用SQLite连接，需要根据实际情况修改
        try:
            # 示例数据库连接（需要根据实际情况修改）
            db_url = f"sqlite:///{self.database_name}.db"  # 或其他数据库连接字符串
            engine = create_engine(db_url)
            
            results = []
            for table_name in table_names:
                # 构建SQL查询，根据问题查询相关表
                sql_query = f"SELECT * FROM {table_name} WHERE content LIKE '%{query}%' LIMIT 10;"
                with engine.connect() as conn:
                    result = conn.execute(text(sql_query))
                    rows = result.fetchall()
                    for row in rows:
                        results.append(dict(row))
            return results
        except Exception as e:
            print(f"数据库查询错误: {e}")
            return []

    def ingest_data(self, documents: List[Document]):
        if not documents:
            print("没有需要加载的文档。")
            return
        print(f"开始加载 {len(documents)} 篇文档...")
        chunks = self.text_splitter.split_documents(documents)
        print(f"文档被分割为 {len(chunks)} 个块。")
        self.vector_store.add_documents(chunks)
        self.vector_store.persist()
        print(f"数据已成功加载并索引到 {self.vector_store._persist_directory}")

    def self_reflect(self, question: str, answer: str, context: str) -> Dict:
        """
        自反思机制，评估回答质量并提供改进建议
        """
        reflection_input = {
            "question": question,
            "answer": answer,
            "context": context
        }
        
        try:
            reflection_result = self.model.invoke(
                self.reflection_prompt.format(**reflection_input)
            ).content
            
            try:
                # 尝试解析JSON格式的反思结果
                reflection_data = json.loads(reflection_result)
            except json.JSONDecodeError:
                # 如果不是JSON格式，尝试提取关键信息
                reflection_data = {
                    "accuracy_score": 5,  # 默认分数
                    "needs_more_info": "否",
                    "improvement_suggestions": "无法解析反思结果",
                    "requires_retrieval": "否"
                }
            
            # 记录反思历史
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

    def ask(self, query: str) -> str:
        print(f"收到问题: {query}")
        
        # 1. 首先从向量数据库检索
        try:
            context_docs = self.retriever.invoke({"query": query})  # 使用新的调用方式
            context = "\n".join([doc.page_content for doc in context_docs])
        except Exception as e:
            print(f"向量数据库检索错误: {e}")
            context = ""
        
        # 2. 从数据库检索相关信息（仅在有表定义时进行）
        if self.retrieval_tables:
            try:
                db_results = self.query_database(query, self.retrieval_tables)
                if db_results:
                    db_context = "\n".join([str(result) for result in db_results])
                    context = f"{context}\n\n数据库信息:\n{db_context}"
            except Exception as e:
                print(f"数据库查询过程中出现错误: {e}")
        
        # 3. 生成回答
        try:
            answer = self.rag_chain.invoke({"context": context, "question": query})
        except Exception as e:
            print(f"生成回答时出现错误: {e}")
            answer = f"抱歉，生成回答时出现错误: {e}"
        
        # 4. 自我反思
        try:
            reflection_result = self.self_reflect(query, answer, context)
            
            # 5. 根据反思结果决定是否需要重新检索
            if reflection_result.get("requires_retrieval") == "是":
                print("根据自反思结果，重新检索相关信息...")
                # 可以根据改进建议调整检索策略
                additional_context = self._get_additional_context(query, reflection_result)
                if additional_context:
                    enhanced_context = f"{context}\n\n补充信息:\n{additional_context}"
                    try:
                        answer = self.rag_chain.invoke({"context": enhanced_context, "question": query})
                        # 再次反思
                        self.self_reflect(query, answer, enhanced_context)
                    except Exception as e:
                        print(f"重新生成回答时出现错误: {e}")
        except Exception as e:
            print(f"自反思过程中出现错误: {e}")
        
        # 6. 记录性能日志
        self.performance_log.append({
            "question": query,
            "answer": answer,
            "accuracy_score": reflection_result.get("accuracy_score", 5),
            "timestamp": datetime.now()
        })
        
        return answer

    def _get_additional_context(self, query: str, reflection_result: Dict) -> str:
        """
        根据反思结果获取额外的上下文信息
        """
        # 这里可以根据反思结果调整检索策略
        improvement_suggestions = reflection_result.get("improvement_suggestions", "")
        
        try:
            # 示例：根据建议重新检索
            additional_docs = self.retriever.invoke({"query": f"{query} {improvement_suggestions}"})
            return "\n".join([doc.page_content for doc in additional_docs])
        except Exception as e:
            print(f"获取额外上下文时出现错误: {e}")
            return ""

    def get_performance_summary(self) -> Dict:
        """
        获取系统性能摘要
        """
        if not self.performance_log:
            return {"message": "暂无性能数据"}
        
        total_questions = len(self.performance_log)
        avg_accuracy = sum([log["accuracy_score"] for log in self.performance_log]) / total_questions
        recent_improvements = len([log for log in self.performance_log if log["accuracy_score"] > 7])
        
        return {
            "total_questions": total_questions,
            "average_accuracy": round(avg_accuracy, 2),
            "high_quality_responses": recent_improvements,
            "improvement_rate": round(recent_improvements / total_questions * 100, 2)
        }

    def update_retrieval_tables(self, table_names: List[str]):
        """
        更新检索范围内的表
        """
        self.retrieval_tables = table_names
        print(f"已更新检索表列表: {table_names}")


if __name__ == '__main__':
    # 检查API密钥是否已设置
    print(f"DASHSCOPE_API_KEY: {'已设置' if ALIYUN_API_KEY else '未设置'}")
    print(f"OPENAI_API_KEY: {'已设置' if OPENAI_API_KEY else '未设置'}")
    
    if not ALIYUN_API_KEY and not OPENAI_API_KEY:
        print("错误：未找到API密钥，请检查.env文件或环境变量设置")
        exit(1)
    
    # 1. 初始化模型（用户可以自定义）
    try:
        from langchain_community.chat_models import ChatTongyi
        model = ChatTongyi(dashscope_api_key=ALIYUN_API_KEY, model_name="qwen-turbo")
    except Exception as e:
        print(f"ChatTongyi初始化失败: {e}")
        # 如果ChatTongyi不可用，使用OpenAI作为备选
        if OPENAI_API_KEY:
            model = ChatOpenAI(api_key=OPENAI_API_KEY, model_name="gpt-3.5-turbo")
        else:
            print("无法初始化任何模型，请检查API密钥")
            exit(1)
    
    # 2. 实例化 RAG 系统
    web_db_path = "./chroma_db_web" 
    print(f"--- 正在实例化RAG系统 (DB: '{web_db_path}') ---")
    
    # 定义需要检索的表（用户自定义）
    retrieval_tables = ["cultural_artifacts", "historical_records", "museum_info"]  # 示例表名
    
    rag_system = CulturalResourceRAG(
        model=model,
        persist_directory=web_db_path,
        retrieval_tables=retrieval_tables
    )

    print("\n--- 开始提问 ---")

    # 3. 提问
    question = "故宫博物院是在哪一年成立的？"
    answer = rag_system.ask(question)
    print(f"问题: {question}\n回答: {answer}\n")
    
    # 4. 获取性能摘要
    performance_summary = rag_system.get_performance_summary()
    print(f"系统性能摘要: {performance_summary}")
    
    # 5. 示例：更新检索表
    rag_system.update_retrieval_tables(["cultural_artifacts", "exhibition_info", "visitor_statistics"])
    
    # 6. 再次提问以测试自反思机制
    question2 = "故宫博物院有哪些著名的文物？"
    answer2 = rag_system.ask(question2)
    print(f"问题: {question2}\n回答: {answer2}\n")
    
    # 7. 再次获取性能摘要
    performance_summary2 = rag_system.get_performance_summary()
    print(f"更新后系统性能摘要: {performance_summary2}")



