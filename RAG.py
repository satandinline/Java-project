import concurrent.futures
import hashlib
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union
import json
import random
import textwrap

import pandas as pd
from dotenv import load_dotenv
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from sqlalchemy import create_engine, text, inspect
from tqdm import tqdm

# 兼容Chroma向量库导入（根据langchain版本调整）
from langchain_community.vectorstores import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import WebBaseLoader
from openai import OpenAI

# 加载环境变量（覆盖已有变量）
load_dotenv(override=True)

# 读取各类API密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")


class CulturalResourceRAG:
    """
    传统文化资源RAG系统
    功能：
    1. 基于向量检索+大模型实现传统文化问答
    2. 支持从节日主题生成原创文化资源（故事/仪式/象征等）
    3. 内置自反思机制评估回答质量
    4. 兼容多模型/多检索器接口
    """

    def __init__(self, model, embedding_model_name='text-embedding-ada-002',
                 persist_directory="./chroma_db", database_name="culture",
                 retrieval_tables=None):
        print("正在初始化 RAG 系统")
        self.model = model

        # 初始化嵌入模型（优先阿里云通义，降级为OpenAI）
        try:
            from langchain_community.embeddings import DashScopeEmbeddings
            self.embedding_model = DashScopeEmbeddings(
                dashscope_api_key=ALIYUN_API_KEY,
                model="text-embedding-v2"
            )
        except Exception as e:
            print(f"DashScopeEmbeddings 初始化失败: {e}，使用 OpenAIEmbeddings 作为备选。")
            self.embedding_model = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

        # 文本分割器（按固定长度分割，保留重叠部分保证上下文连续）
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

        # 初始化Chroma向量库（持久化存储）
        self.vector_store = Chroma(persist_directory=persist_directory, embedding_function=self.embedding_model)
        self._persist_directory = persist_directory

        # 初始化检索器（返回Top5相关文档）
        try:
            self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
            print("检索器初始化成功")
        except Exception as e:
            print(f"创建 retriever 出错: {e}")
            self.retriever = None

        # 数据库配置（占位，不进行实际连接）
        self.database_name = database_name
        self.retrieval_tables = retrieval_tables or []

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

        # 问答Prompt模板（清理缩进保证格式正确）
        template = textwrap.dedent("""
        你是一位精通中国传统文化的资深研究员。请利用提供的【参考资料】来回答用户的【问题】。

        【参考资料】：
        {context}

        【用户问题】：
        {question}

        【回答要求】：
        1. 准确性：严格基于参考资料回答，不要编造。如果资料不足，请明确说明。
        2. 结构化：必须按照指定的JSON格式输出，不要包含任何其他解释性文字。
        3. 风格：用词需优美、得体，符合公共文化服务的调性。

        {format_instructions}
        """)
        self.rag_prompt = PromptTemplate(template=template,
                                         input_variables=["context", "question"],
                                         partial_variables={"format_instructions": self.format_instructions})

        # 自反思Prompt模板（评估回答质量）
        self.reflection_prompt = PromptTemplate(
            template=textwrap.dedent("""
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

        # 文化资源生成Prompt模板
        self.gen_prompt_template = PromptTemplate(
            template=textwrap.dedent("""
            你是一个富有创造力且有文化学素养的民俗学家/故事匠人。
            输入：一个已存在的节日名称："{festival}"，以及可选提示："{hint}"。
            任务：基于该节日的主题与情感，创造一个全新的公共文化资源（可以是新的故事、仪式、象征或节庆活动），
            要求：
              1) 必须原创，不要复刻或明显模仿任何已知传说或真实节日活动。
              2) 风格自然、具有人情味，避免模板化文本。
              3) 输出必须严格按照指定的JSON格式（不要包含多余文字）。
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
            if hasattr(self.model, "invoke"):
                resp = self.model.invoke(prompt_text)
                if isinstance(resp, str):
                    return resp
                if hasattr(resp, "content"):
                    return resp.content
                if hasattr(resp, "text"):
                    return resp.text
                return str(resp)
            elif callable(self.model):
                resp = self.model(prompt_text)
                if isinstance(resp, str):
                    return resp
                if hasattr(resp, "content"):
                    return resp.content
                if hasattr(resp, "text"):
                    return resp.text
                return str(resp)
            else:
                raise RuntimeError("未知模型接口：既没有 invoke 方法，也不可直接调用。")
        except Exception as e:
            print(f"模型调用错误: {e}")
            raise

    def _call_retriever(self, query: str) -> List[Document]:
        """
        统一检索器调用接口，兼容不同实现方式
        :param query: 检索关键词
        :return: 检索到的Document列表（无结果返回空列表）
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

    def query_database(self, query: str, table_names: List[str] = None) -> List[Dict]:
        """
        占位函数：从指定数据库表中检索相关内容（不执行实际数据库操作）
        :param query: 检索关键词
        :param table_names: 要查询的表名列表（默认使用初始化时的retrieval_tables）
        :return: 空列表（占位返回）
        """
        print("数据库查询功能已被禁用，返回空结果。")
        return []

    def ingest_data(self, documents: List[Document]):
        """
        将文档分割后入库向量库
        :param documents: 待入库的Document列表
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
            elif hasattr(self.vector_store, "add"):
                self.vector_store.add(chunks)
            else:
                raise RuntimeError("当前 VectorStore 不支持 add_documents/add 方法")
            if hasattr(self.vector_store, "persist"):
                self.vector_store.persist()
            print(f"数据已成功加载并索引到 {self._persist_directory}")
        except Exception as e:
            print(f"向量库写入错误: {e}")

    def self_reflect(self, question: str, answer: str, context: str) -> Dict:
        """
        对回答进行自反思评估
        :param question: 用户问题
        :param answer: RAG生成的回答
        :param context: 检索到的上下文
        :return: 反思评估结果（包含准确性评分、改进建议等）
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

    def ask(self, query: str) -> Dict:
        """
        RAG核心问答接口
        :param query: 用户问题
        :return: 结构化回答（包含answer/key_entities/sources/confidence字段）
        """
        print(f"收到问题: {query}")
        # 1. 向量库检索上下文
        try:
            docs = self._call_retriever(query)
            context = "\n".join([getattr(d, "page_content", str(d)) for d in docs]) if docs else ""
        except Exception as e:
            print(f"向量数据库检索错误: {e}")
            context = ""

        # 2. 数据库检索补充上下文（占位，不执行实际操作）
        if self.retrieval_tables:
            try:
                print("跳过数据库查询（功能已禁用）")
            except Exception as e:
                print(f"数据库查询过程中出现错误: {e}")

        # 3. 生成回答（保证结构化输出）
        try:
            prompt_text = self.rag_prompt.format(context=context or "", question=query or "")
            raw_text = self._call_model(prompt_text)
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
                print(f"解析回答失败: {e}\nraw_text:\n{raw_text}")
                # 解析失败时返回标准格式
                parsed = {
                    "answer": raw_text,
                    "key_entities": [],
                    "sources": "",
                    "confidence": 0
                }
        except Exception as e:
            print(f"生成回答时出现错误: {e}")
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

        # 5. 记录性能日志
        try:
            self.performance_log.append({
                "question": query,
                "answer": parsed,
                "accuracy_score": reflection_result.get("accuracy_score", 5),
                "timestamp": datetime.now()
            })
        except Exception as e:
            print(f"记录性能日志失败: {e}")

        return parsed

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
        基于节日主题生成原创文化资源
        :param festival: 节日名称（如中秋节）
        :param user_hint: 额外创作提示（可选）
        :return: 结构化原创资源（包含title/type/story等字段）
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
        将生成的结构化文化资源转换为易读的文本格式（完整提取所有字段）
        :param resource_dict: generate_resource_from_festival返回的结构化字典
        :return: 整合后的纯文本字符串
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
        单独提取文化资源的所有字段（返回元组，便于单独使用）
        :param resource_dict: generate_resource_from_festival返回的结构化字典
        :return: (title, type, story, rituals, symbols, usage, novelty_explanation)
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
        获取系统性能统计摘要
        :return: 包含总问题数、平均准确率、高质量回答数等统计信息
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
        更新数据库检索表列表（占位函数）
        :param table_names: 新的检索表名列表
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

    # 初始化模型（优先通义千问，降级为OpenAI）
    try:
        from langchain_community.chat_models import ChatTongyi
        model = ChatTongyi(dashscope_api_key=ALIYUN_API_KEY, model_name="qwen-turbo")
    except Exception as e:
        print(f"ChatTongyi 初始化失败: {e}，尝试使用 OpenAI ChatOpenAI 作为后备。")
        if OPENAI_API_KEY:
            model = ChatOpenAI(api_key=OPENAI_API_KEY, model_name="gpt-3.5-turbo")
        else:
            print("无法初始化任何模型，请检查 API 密钥")
            exit(1)

    # 初始化RAG系统
    web_db_path = "./chroma_db_web"
    retrieval_tables = ["cultural_artifacts", "historical_records", "museum_info"]
    rag_system = CulturalResourceRAG(model=model, persist_directory=web_db_path, retrieval_tables=retrieval_tables)

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



