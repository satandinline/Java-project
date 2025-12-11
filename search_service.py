# search_service.py
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from db_connection import get_default_db_connection

app = Flask(__name__)
app.json.ensure_ascii = False 
CORS(app) 

@app.route('/api/search', methods=['GET'])
def search_resources():
    keyword = request.args.get('q', '').strip()
    
    if not keyword:
        return jsonify({"code": 400, "msg": "请输入搜索关键词", "data": []})

    conn = get_default_db_connection()
    if not conn:
        return jsonify({"code": 500, "msg": "数据库连接失败", "data": []})

    try:
        with conn.cursor() as cursor:
            # -------------------------------------------------------------
            # 【核心修改】 使用 UNION 联合查询两张实体表
            # 表1: cultural_entities (传统实体)
            # 表2: AIGC_cultural_entities (AI生成实体)
            # -------------------------------------------------------------
            sql = """
                (SELECT 
                    id, 
                    entity_name as title, 
                    description, 
                    related_images_url as image_url,
                    source,
                    '传统实体' as type_tag
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
                    'AI实体' as type_tag
                FROM AIGC_cultural_entities 
                WHERE MATCH(entity_name, description) 
                AGAINST(%s IN NATURAL LANGUAGE MODE)
                LIMIT 25);
            """
            
            print(f"正在双表检索关键词: {keyword}")
            # 注意：因为有两个 %s 占位符，所以参数要传两次 keyword
            cursor.execute(sql, (keyword, keyword))
            results = cursor.fetchall()
            
            formatted_list = []
            
            for row in results:
                # 提取描述摘要
                desc = row.get('description', '')
                if desc:
                    # 截取前 100 个字作为摘要
                    snippet = desc[:100] + '...'
                else:
                    snippet = '暂无详细描述'
                
                # 提取图片
                # 实体表里的图片链接有时可能是 "http..." 或者是相对路径
                # 这里原样返回，由前端处理显示
                img = row.get('image_url')
                if not img or img == 'null':
                    img = None

                # 组装数据
                formatted_list.append({
                    "id": row['id'],
                    "title": row['title'],
                    "snippet": snippet,
                    # 这里的 tags 我们用 type_tag 代替，标识它是人工的还是AI的
                    "tags": [row['type_tag']], 
                    "source_url": row.get('source', '#'),
                    "image_url": img 
                })

            return jsonify({
                "code": 200,
                "msg": "success",
                "data": formatted_list
            })

    except Exception as e:
        print(f"搜索错误: {e}")
        return jsonify({"code": 500, "msg": str(e), "data": []})
        
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print(">>> 实体描述搜索服务已启动 (端口5050)...")
    # 保持 5050 端口，避免和原系统冲突
    app.run(host='0.0.0.0', port=5050, debug=True)