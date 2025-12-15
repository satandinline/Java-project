# search_service.py
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from db_connection import get_default_db_connection
import os
import sys

# 导入RAG系统
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from langchain_community.chat_models import ChatTongyi
from pydantic import SecretStr
from AIGC.RAG import CulturalResourceRAG

app = Flask(__name__)
app.json.ensure_ascii = False 
CORS(app)

# 初始化RAG系统
print("正在初始化AI辅助检索系统...")
ALIYUN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")
if not ALIYUN_API_KEY:
    print("警告：未找到通义千问API密钥，请设置DASHSCOPE_API_KEY或ALIYUN_API_KEY环境变量")
tongyi_model = ChatTongyi(api_key=SecretStr(ALIYUN_API_KEY or ""), model="qwen-turbo")
rag_system = CulturalResourceRAG(model=tongyi_model, persist_directory="./chroma_db")

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

@app.route('/api/search', methods=['GET'])
def search_resources():
    keyword = request.args.get('q', '').strip()
    user_id = request.args.get('user_id', None)
    
    if not keyword:
        return jsonify({"code": 400, "msg": "请输入搜索关键词", "data": []})

    conn = get_default_db_connection()
    if not conn:
        return jsonify({"code": 500, "msg": "数据库连接失败", "data": []})

    try:
        # ------------------------
        # 1. AI语义提取构建高级检索式
        # ------------------------
        print(f"正在进行AI语义分析: {keyword}")
        extraction_result = rag_system.model.invoke(
            semantic_extraction_prompt.format(query=keyword)
        ).content
        
        # 解析AI返回的结果
        try:
            ai_analysis = json.loads(extraction_result)
            advanced_query = ai_analysis.get("advanced_query", keyword)
            keywords = ai_analysis.get("keywords", [keyword])
            print(f"AI分析结果 - 关键词: {keywords}, 高级检索式: {advanced_query}")
        except:
            # 如果解析失败，使用原始关键词
            advanced_query = keyword
            keywords = [keyword]
            print(f"AI分析失败，使用原始关键词: {keyword}")

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
            
            print(f"正在双表检索，查询词: {advanced_query}")
            cursor.execute(sql, (advanced_query, advanced_query, advanced_query, advanced_query))
            results = cursor.fetchall()
            
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
        print(f"搜索错误: {e}")
        return jsonify({"code": 500, "msg": str(e), "data": []})
        
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print(">>> AI辅助检索服务已启动 (端口5050)...")
    app.run(host='0.0.0.0', port=5050, debug=True)
