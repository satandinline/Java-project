import concurrent.futures
import hashlib
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union

import pandas as pd
from dotenv import load_dotenv
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from sqlalchemy import create_engine
from tqdm import tqdm
from langchain_dashscope import ChatDashScope
from langchain_community.vectorstores import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from langchain_community.document_loaders import WebBaseLoader
from langchain_community.embeddings import DashScopeEmbeddings

load_dotenv(override=True)



DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY")


model_test = ChatDashScope(api_key=ALIYUN_API_KEY)
question = "王云琦是不是pig?"
thing = model_test.invoke(f"问题{question}中提到的事物是什么？只需要回答事物的中文名称。").content
man = model_test.invoke(f"问题{question}中提到的人是谁？只需要给出人名。").content
answer_prompt = f"只能回答{man}是或yes或不如{thing},并给出理由。"
result = model_test.invoke(f"{question}{answer_prompt}")
print(f" {result.content}")



class CulturalResourseRag:
    
    def __init__(self, embedding_model_name='text-embedding-ada-002', llm_model_name='qwen-turbo', persist_directory="./chroma_db"):
        print(f"正在初始化 RAG 系统，使用LLM: {llm_model_name}")
        
        self.embedding_model = DashScopeEmbeddings(
            api_key=ALIYUN_API_KEY, 
            model="text-embedding-v2"
        )

        # 2. LLM 
        if llm_model_name == 'qwen-turbo':
            self.llm = ChatDashScope(api_key=ALIYUN_API_KEY, model_name="qwen-turbo")
            if not ALIYUN_API_KEY:
                print("未找到 DASHSCOPE_API_KEY")
        elif llm_model_name == 'deepseek-chat':
            self.llm = ChatOpenAI(model_name="deepseek-chat", api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")
        else:
            self.llm = ChatOpenAI(api_key=OPENAI_API_KEY, model_name="gpt-3.5-turbo")

        # 3. 文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        
        # 4. 向量数据库
        self.vector_store = Chroma(persist_directory=persist_directory, embedding_function=self.embedding_model)
        
        # 5. 检索器
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
        
        # 6. Prompt模板
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
        
        # 7. RAG链
        self.rag_chain = (
            {"context": self.retriever, "question": RunnablePassthrough()}
            | self.rag_prompt
            | self.llm
            | StrOutputParser()
        )
        print("RAG初始化完成。")

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

    def ask(self, query: str) -> str:
        print(f"收到问题: {query}")
        answer = self.rag_chain.invoke(query)
        return answer


if __name__ == '__main__':
    
    # 1. 实例化 RAG 系统
    web_db_path = "./chroma_db_web" 
    print(f"--- 正在实例化RAG系统 (LLM: 'qwen-turbo', DB: '{web_db_path}') ---")
    rag_system = CulturalResourseRag(
        llm_model_name='qwen-turbo', 
        persist_directory=web_db_path
    )

    # 2. 定义要爬取的网页
    url = "https://www.dpm.org.cn/about/introduction.html"
    
    # 3. 加载数据
    if not os.path.exists(web_db_path):
        print(f"未找到本地数据库 '{web_db_path}'，开始从 {url} 爬取并加载数据...")
        
        try:
            # 3a. 爬取网页
            loader = WebBaseLoader(url)
            scraped_docs = loader.load() 
            
            if not scraped_docs:
                print("爬取失败")
                exit()
                
            print(f"爬取成功，获取到 {len(scraped_docs)} 个文档。")
            print(f"内容预览 (前200字符): {scraped_docs[0].page_content[:200]}...")

            # 3b. 加载数据
            rag_system.ingest_data(scraped_docs)
            
        except Exception as e:
            print(f"爬取或加载数据时出错: {e}")
            exit()
    else:
        print(f"检测到本地数据库 '{web_db_path}'，跳过数据爬取和加载。")


    print("\n--- 开始提问 ---")

    # 4. 提问
    question = "故宫博物院是在哪一年成立的？"
    answer = rag_system.ask(question)
    print(f"问题: {question}\n回答: {answer}\n")