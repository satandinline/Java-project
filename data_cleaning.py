# -*- coding: utf-8 -*-
"""
数据清洗程序
将数据库中cultural_resources、cultural_entities、crawled_images几个表的内容
按id分组，每个id聚合为一组发送给通义千问API进行清洗

需要清洗的字段：
- cultural_resources表：content_feature_data
- cultural_entities表：entity_name、entity_type、description、period_era、geo_coordinates、cultural_region、style_features、cultural_value
- crawled_images表：tags、festival_name
"""

import os
import sys
import json
import time
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from db_connection import get_default_db_connection

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

load_dotenv(override=True)


def is_chinese_traditional_festival(festival_name: str) -> bool:
    """
    判断是否是中国传统节日
    
    Args:
        festival_name: 节日名称
    
    Returns:
        True表示是中国传统节日，False表示不是
    """
    if not festival_name or festival_name.strip() == "" or festival_name == "无":
        return False
    
    festival_name = festival_name.strip()
    
    # 获取所有有效的中国传统节日名称
    if isinstance(FESTIVAL_NAME_MAP, dict):
        valid_festivals = set(FESTIVAL_NAME_MAP.keys())
    else:
        valid_festivals = FESTIVAL_NAME_MAP
    
    # 直接匹配
    if festival_name in valid_festivals:
        return True
    
    # 部分匹配（检查是否包含已知节日名称）
    for valid_festival in valid_festivals:
        if valid_festival in festival_name or festival_name in valid_festival:
            return True
    
    # 检查是否包含"节"或"日"字，且不是通用词汇
    if "节" in festival_name or "日" in festival_name:
        # 排除明显不是节日的词汇
        exclude_words = ["节日", "节庆", "习俗", "传统", "文化", "活动", "仪式", "当代", "现代"]
        if any(word in festival_name for word in exclude_words):
            return False
        # 如果包含节或日，且长度合理（2-10个字符），可能是节日
        if 2 <= len(festival_name) <= 10:
            return True
    
    return False


def search_period_era_online(festival_name: Optional[str] = None, entity_name: Optional[str] = None, description: Optional[str] = None) -> Optional[str]:
    """
    使用DeepSeek API通过网络搜索获取period_era信息
    
    Args:
        festival_name: 节日名称
        entity_name: 实体名称
        description: 描述信息
    
    Returns:
        时期年代字符串，如果搜索失败返回None
    """
    if not DEEPSEEK_API_KEY:
        return None
    
    try:
        # 构建搜索提示词
        desc_text = description[:200] if description else ''
        search_prompt = f"""请搜索并返回以下中国传统节日的准确历史起源时期：

节日名称：{festival_name or ''}
实体名称：{entity_name or ''}
描述：{desc_text}

请根据你的知识，返回这个节日的准确历史时期（如"唐代"、"宋代"、"明清时期"等）。
如果节日是少数民族的传统节日，请返回其实际的历史起源时期，不要返回"当代"或"现代"。

只返回时期名称，不需要其他说明文字。"""
        
        # 调用DeepSeek API进行搜索
        result = call_deepseek_api(search_prompt, max_retries=2, stream=False)
        
        if result:
            # 提取时期信息（去除可能的说明文字）
            result = result.strip()
            # 查找常见的时期关键词
            period_keywords = ["唐代", "宋代", "明代", "清代", "汉代", "唐代", "宋代", 
                             "明清", "唐宋", "元明", "古代", "近代", "现代", "当代"]
            for keyword in period_keywords:
                if keyword in result:
                    # 提取包含关键词的短语
                    import re
                    match = re.search(r'[^\s，,。.]*' + keyword + r'[^\s，,。.]*', result)
                    if match:
                        return match.group(0)
            # 如果没有找到关键词，返回前10个字符（可能是时期名称）
            if len(result) <= 15:
                return result
            return result[:10]
        
        return None
        
    except Exception as e:
        print(f"  网络搜索period_era失败: {e}")
        return None


def delete_invalid_festival_data(conn):
    """
    删除festival_name为"无"或不是中国传统节日的数据（级联删除）
    
    Args:
        conn: 数据库连接
    
    Returns:
        删除的记录数统计
    """
    deleted_counts = {
        "crawled_images": 0,
        "cultural_resources": 0,
        "cultural_entities": 0,
        "entity_relationships": 0
    }
    
    try:
        cursor = conn.cursor()
        
        print("\n" + "=" * 60)
        print("开始删除无效节日数据（级联删除）")
        print("=" * 60)
        
        # 1. 查找所有需要删除的festival_name
        cursor.execute("""
            SELECT DISTINCT festival_name, GROUP_CONCAT(DISTINCT resource_id) as resource_ids
            FROM crawled_images
            WHERE festival_name IS NOT NULL
            GROUP BY festival_name
        """)
        
        invalid_festivals = []
        all_resource_ids_to_delete = set()
        all_entity_ids_to_delete = set()
        
        for row in cursor.fetchall():
            festival_name = row["festival_name"]
            if not is_chinese_traditional_festival(festival_name):
                invalid_festivals.append(festival_name)
                resource_ids = [int(rid) for rid in str(row["resource_ids"]).split(",") if rid]
                all_resource_ids_to_delete.update(resource_ids)
        
        if not invalid_festivals:
            print("未找到需要删除的无效节日数据")
            return deleted_counts
        
        print(f"\n找到 {len(invalid_festivals)} 个无效节日名称：")
        for festival in invalid_festivals[:10]:  # 只显示前10个
            print(f"  - {festival}")
        if len(invalid_festivals) > 10:
            print(f"  ... 还有 {len(invalid_festivals) - 10} 个")
        
        print(f"\n涉及 {len(all_resource_ids_to_delete)} 个资源ID")
        
        # 2. 查找这些resource_id对应的entity_id
        if all_resource_ids_to_delete:
            placeholders = ','.join(['%s'] * len(all_resource_ids_to_delete))
            cursor.execute(f"""
                SELECT DISTINCT id
                FROM cultural_entities
                WHERE id IN ({placeholders})
            """, list(all_resource_ids_to_delete))
            
            for row in cursor.fetchall():
                all_entity_ids_to_delete.add(row["id"])
        
        print(f"涉及 {len(all_entity_ids_to_delete)} 个实体ID")
        
        # 3. 开始级联删除
        
        # 3.1 删除entity_relationships表中的关系（使用entity_id）
        if all_entity_ids_to_delete:
            placeholders = ','.join(['%s'] * len(all_entity_ids_to_delete))
            cursor.execute(f"""
                DELETE FROM entity_relationships
                WHERE source_entity_id IN ({placeholders})
                   OR target_entity_id IN ({placeholders})
            """, list(all_entity_ids_to_delete) * 2)
            deleted_counts["entity_relationships"] = cursor.rowcount
            print(f"  ✓ 删除 {deleted_counts['entity_relationships']} 条实体关系记录")
        
        # 3.2 删除crawled_images表中的记录
        if invalid_festivals:
            placeholders = ','.join(['%s'] * len(invalid_festivals))
            cursor.execute(f"""
                DELETE FROM crawled_images
                WHERE festival_name IN ({placeholders})
            """, invalid_festivals)
            deleted_counts["crawled_images"] = cursor.rowcount
            print(f"  ✓ 删除 {deleted_counts['crawled_images']} 条爬虫图像记录")
        
        # 3.3 删除cultural_entities表中的记录（使用entity_id，即resource_id）
        if all_entity_ids_to_delete:
            placeholders = ','.join(['%s'] * len(all_entity_ids_to_delete))
            cursor.execute(f"""
                DELETE FROM cultural_entities
                WHERE id IN ({placeholders})
            """, list(all_entity_ids_to_delete))
            deleted_counts["cultural_entities"] = cursor.rowcount
            print(f"  ✓ 删除 {deleted_counts['cultural_entities']} 条文化实体记录")
        
        # 3.4 删除cultural_resources表中的记录
        if all_resource_ids_to_delete:
            placeholders = ','.join(['%s'] * len(all_resource_ids_to_delete))
            cursor.execute(f"""
                DELETE FROM cultural_resources
                WHERE id IN ({placeholders})
            """, list(all_resource_ids_to_delete))
            deleted_counts["cultural_resources"] = cursor.rowcount
            print(f"  ✓ 删除 {deleted_counts['cultural_resources']} 条文化资源记录")
        
        # 提交事务
        conn.commit()
        
        print("\n" + "=" * 60)
        print("删除完成！")
        print(f"总计删除：")
        print(f"  - 文化资源: {deleted_counts['cultural_resources']} 条")
        print(f"  - 文化实体: {deleted_counts['cultural_entities']} 条")
        print(f"  - 爬虫图像: {deleted_counts['crawled_images']} 条")
        print(f"  - 实体关系: {deleted_counts['entity_relationships']} 条")
        print("=" * 60)
        
        return deleted_counts
        
    except Exception as e:
        conn.rollback()
        print(f"删除无效数据时出错: {e}")
        import traceback
        traceback.print_exc()
        return deleted_counts

# 通义千问API配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")

# DeepSeek API配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 请求延迟（秒），避免API限流
REQUEST_DELAY = 1

# 导入节日工具
try:
    from festival_name_utils import FESTIVAL_NAME_MAP
except ImportError:
    # 如果导入失败，定义基本节日列表
    FESTIVAL_NAME_MAP = {
        "春节", "新年", "农历新年", "元宵节", "上元节", "清明节", "清明", "寒食节",
        "端午节", "端阳节", "龙舟节", "中秋节", "中秋", "重阳节", "重阳",
        "冬至", "冬至节", "腊八节", "小年", "除夕", "除夕夜", "七夕节", "乞巧节",
        "中元节", "下元节", "花朝节", "上巳节", "寒衣节", "祭灶节",
        "泼水节", "火把节", "那达慕", "开斋节", "古尔邦节", "藏历新年",
        "雪顿节", "望果节"
    }


def call_qwen_api(prompt: str, max_retries: int = 3) -> Optional[str]:
    """
    调用通义千问API
    
    Args:
        prompt: 提示词
        max_retries: 最大重试次数
    
    Returns:
        API返回的文本内容，失败返回None
    """
    if not DASHSCOPE_API_KEY:
        print("错误：未设置DASHSCOPE_API_KEY或ALIYUN_API_KEY环境变量")
        return None
    
    try:
        from langchain_community.chat_models import ChatTongyi
        from pydantic import SecretStr
        
        model = ChatTongyi(api_key=SecretStr(DASHSCOPE_API_KEY), model="qwen-turbo")
        
        for attempt in range(max_retries):
            try:
                response = model.invoke(prompt)
                content = response.content
                # 确保返回字符串
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    return str(content[0]) if content else None
                else:
                    return str(content) if content else None
            except Exception as e:
                print(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    return None
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装 langchain-community 和 dashscope")
        return None
    
    return None


def call_deepseek_api(prompt: str, max_retries: int = 3, stream: bool = False, callback=None) -> Optional[str]:
    """
    调用DeepSeek API
    
    Args:
        prompt: 提示词
        max_retries: 最大重试次数
        stream: 是否使用流式输出
        callback: 流式输出的回调函数，接收文本块
    
    Returns:
        API返回的文本内容，失败返回None
    """
    if not DEEPSEEK_API_KEY:
        print("错误：未设置DEEPSEEK_API_KEY环境变量")
        return None
    
    try:
        import requests
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的数据清洗助手，负责清洗和填充中国传统节日文化资源数据库的字段。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "stream": stream
        }
        
        for attempt in range(max_retries):
            try:
                if stream:
                    # 流式输出
                    response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=120, stream=True)
                    response.raise_for_status()
                    
                    full_content = ""
                    for line in response.iter_lines():
                        if line:
                            line_text = line.decode('utf-8')
                            if line_text.startswith('data: '):
                                data_str = line_text[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    if "choices" in chunk and len(chunk["choices"]) > 0:
                                        delta = chunk["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            full_content += content
                                            if callback:
                                                callback(content)
                                except json.JSONDecodeError:
                                    continue
                    
                    return full_content if full_content else None
                else:
                    # 非流式输出
                    response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=60)
                    response.raise_for_status()
                    result = response.json()
                    
                    if "choices" in result and len(result["choices"]) > 0:
                        return result["choices"][0]["message"]["content"]
                    else:
                        print(f"API返回格式异常: {result}")
                        return None
                    
            except requests.exceptions.RequestException as e:
                print(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    return None
        
        return None
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装 requests")
        return None


def build_cleaning_prompt(group_data: Dict[str, Any], use_online_search: bool = False) -> str:
    """
    构建清洗提示词
    
    Args:
        group_data: 分组数据，包含cultural_resources、cultural_entities、crawled_images
    
    Returns:
        提示词字符串
    """
    prompt = """你是一个专业的数据清洗助手，负责清洗和填充中国传统节日文化资源数据库的字段。

请对以下数据进行清洗和填充，确保每个字段都有有效数据。

【字段说明】
1. content_feature_data: 存储用于知识图谱构建的实体向量或AI提取的语义特征，通常是JSON格式，包含title（标题）、text（详细文本描述）、meta（元数据）。注意：此字段应该只包含与当前资源/实体相关的核心内容，如果包含其他不相关的节日信息或页面内容，需要提取和清洗，只保留与当前实体相关的内容。
2. entity_name: 实体名称，即文化资源的名称（如"春节"、"端午节"等节日名称或相关习俗名称）
3. entity_type: 实体类型，只能是以下5种之一：人物、作品、事件、地点、其他
4. description: 详细描述，关于该文化资源的详细介绍
5. period_era: 时期年代，如"汉代"、"唐代"、"现代"等
6. geo_coordinates: 地理坐标，如"116.4074,39.9042"（经度,纬度格式）
7. cultural_region: 文化区域，如"华北地区"、"江南地区"、"西南地区"等
8. style_features: 风格特征，描述该文化资源的艺术风格或特点
9. cultural_value: 文化价值，直接阐述该节日或文化资源的文化价值、意义和影响（如：传承传统文化、增强民族凝聚力、促进文化交流等），不要对其他字段的内容进行评价或描述
10. tags: 标签，用于分类和检索的关键词
11. festival_name: 节日名称，关联的中国传统节日名称（如"春节"、"中秋节"等）

【清洗要求】
重要：清洗不是简化或概括，而是在去除无关信息的同时，保留和完善所有有效信息！

1. 字段清洗原则：
   - 去除无效字符、多余空格、格式错误等
   - 保留所有有效的信息细节和具体内容
   - 对于有效信息，要进行完善、修正和补充，而不是简化或概括
   - 对于空值或无效字段，根据上下文和已有信息进行合理填充和完善

2. 字段具体要求：
   - entity_type必须是以下5种之一：人物、作品、事件、地点、其他
   - festival_name应该是标准的中国传统节日名称（如春节、元宵节、清明节、端午节、中秋节、重阳节等）
   - 如果无法确定festival_name，根据entity_name和description推断最可能的节日名称

3. period_era字段处理：
   - 必须准确反映节日的实际历史起源时期
   - 如果是少数民族的传统节日，不能填写"当代"或"现代"
   - 应该根据节日的实际历史起源时期填写（如"唐代"、"宋代"、"明清时期"、"元代"等）
   - 如果有具体的历史年代信息，要保留并完善

4. content_feature_data字段处理：
   - 保留所有与当前节日或实体相关的有效信息
   - 去除不相关的页面导航、其他节日信息、无关链接等
   - 如果包含JSON格式，保持JSON结构，只去除不相关的内容，保留和补充相关内容的详细信息
   - 不要过度简化，要保留具体的描述、特征、历史背景等细节

5. description字段处理：
   - 保留和完善所有相关的历史背景、文化内涵、习俗特点等详细信息
   - 如果原文过于简略，要根据已有信息进行补充和完善
   - 不要概括成一句话，要提供充分的文化信息

6. cultural_value字段处理：
   - 直接阐述对应节日的文化价值、意义和影响
   - 例如：传承传统文化、增强民族凝聚力、促进文化交流、弘扬民族精神、体现文化多样性等
   - 不要对其他字段（如description、style_features等）的内容进行评价或描述
   - 要客观地说明该节日或文化资源的文化价值和社会意义

7. 其他字段：
   - 所有字段都要在保留有效信息的基础上进行完善
   - 不要为了简洁而丢失重要信息

【待清洗数据】
"""
    
    # 添加cultural_resources数据
    if group_data.get("cultural_resources"):
        cr = group_data["cultural_resources"]
        content_feature = cr.get('content_feature_data') or ''
        if isinstance(content_feature, str) and len(content_feature) > 500:
            content_feature = content_feature[:500] + '...'
        prompt += f"""
【文化资源表】
content_feature_data: {content_feature}
"""
    else:
        prompt += "\n【文化资源表】\n无数据\n"
    
    # 添加cultural_entities数据
    if group_data.get("cultural_entities"):
        ce = group_data["cultural_entities"]
        description = ce.get('description') or ''
        if isinstance(description, str) and len(description) > 500:
            description = description[:500] + '...'
        prompt += f"""
【文化实体表】
entity_name: {ce.get('entity_name') or ''}
entity_type: {ce.get('entity_type') or ''}
description: {description}
period_era: {ce.get('period_era') or ''}
geo_coordinates: {ce.get('geo_coordinates') or ''}
cultural_region: {ce.get('cultural_region') or ''}
style_features: {ce.get('style_features') or ''}
cultural_value: {ce.get('cultural_value') or ''}
"""
    else:
        prompt += "\n【文化实体表】\n无数据\n"
    
    # 添加crawled_images数据
    if group_data.get("crawled_images"):
        ci = group_data["crawled_images"]
        # 处理tags字段
        tags = ci.get('tags') or ''
        if isinstance(tags, str):
            # 如果是JSON字符串，尝试解析
            try:
                tags_list = json.loads(tags)
                if isinstance(tags_list, list):
                    tags = ', '.join(str(t) for t in tags_list)
            except:
                pass
        prompt += f"""
【爬虫图像表】
tags: {tags}
festival_name: {ci.get('festival_name') or ''}
"""
    else:
        prompt += "\n【爬虫图像表】\n无数据\n"
    
    prompt += """
【输出格式要求】
请严格按照以下格式输出清洗后的数据，每个字段占一行，使用"字段名: 值"的格式：

content_feature_data: 清洗后的内容（如果原内容是JSON格式请保持JSON格式，保留和完善所有相关细节）
entity_name: 清洗后的实体名称
entity_type: 人物/作品/事件/地点/其他（只能选择其中之一）
description: 清洗后的描述（要详细、完整，包含历史背景、文化内涵、具体特点等，不要简化）
period_era: 清洗后的时期年代
geo_coordinates: 清洗后的地理坐标（格式：经度,纬度）
cultural_region: 清洗后的文化区域
style_features: 清洗后的风格特征（要详细描述，保留具体特点）
cultural_value: 清洗后的文化价值（直接阐述节日的文化价值、意义和影响，不要评价其他字段内容）
tags: 清洗后的标签（多个标签用逗号分隔，不要使用JSON格式）
festival_name: 清洗后的节日名称

重要注意事项：
1. 每个字段都必须有值，不能为空
2. 清洗不等于简化：要在去除无关信息的同时，保留和完善所有有效信息的细节
3. description、style_features、cultural_value等字段要详细描述，不要概括成一句话
4. content_feature_data如果包含JSON，要保留JSON结构，只去除不相关内容，保留和补充相关详细信息
5. tags字段直接输出标签文字，多个标签用中文逗号分隔，不要使用[""]这样的JSON格式
6. 如果某个字段原本为空或过于简略，请根据上下文合理填充和完善，提供充分的信息
"""
    
    return prompt


def parse_cleaning_result(result_text: str, original_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    解析AI返回的清洗结果
    
    Args:
        result_text: AI返回的文本
        original_data: 原始数据，用于保留未清洗的字段
    
    Returns:
        解析后的字典，失败返回None
    """
    try:
        result = {
            "cultural_resources": {},
            "cultural_entities": {},
            "crawled_images": {}
        }
        
        # 按行解析
        lines = result_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            # 分割字段名和值
            colon_idx = line.find(':')
            if colon_idx == -1:
                continue
            
            field_name = line[:colon_idx].strip().lower()
            field_value = line[colon_idx + 1:].strip()
            
            # 跳过空值
            if not field_value:
                continue
            
            # 映射到对应的表
            if field_name == 'content_feature_data':
                result["cultural_resources"]["content_feature_data"] = field_value
            elif field_name == 'entity_name':
                result["cultural_entities"]["entity_name"] = field_value
            elif field_name == 'entity_type':
                # 验证entity_type
                valid_types = ['人物', '作品', '事件', '地点', '其他']
                if field_value in valid_types:
                    result["cultural_entities"]["entity_type"] = field_value
                else:
                    result["cultural_entities"]["entity_type"] = '其他'
            elif field_name == 'description':
                result["cultural_entities"]["description"] = field_value
            elif field_name == 'period_era':
                result["cultural_entities"]["period_era"] = field_value
            elif field_name == 'geo_coordinates':
                result["cultural_entities"]["geo_coordinates"] = field_value
            elif field_name == 'cultural_region':
                result["cultural_entities"]["cultural_region"] = field_value
            elif field_name == 'style_features':
                result["cultural_entities"]["style_features"] = field_value
            elif field_name == 'cultural_value':
                result["cultural_entities"]["cultural_value"] = field_value
            elif field_name == 'tags':
                # 处理tags，确保不是JSON格式
                tags_value = field_value
                # 去除可能的JSON格式
                if tags_value.startswith('[') and tags_value.endswith(']'):
                    try:
                        tags_list = json.loads(tags_value)
                        if isinstance(tags_list, list):
                            tags_value = ','.join(str(t) for t in tags_list)
                    except:
                        pass
                # 去除引号
                tags_value = tags_value.replace('"', '').replace("'", '')
                result["crawled_images"]["tags"] = tags_value
            elif field_name == 'festival_name':
                result["crawled_images"]["festival_name"] = field_value
        
        # 验证是否有有效数据
        has_valid_data = False
        for table_name, table_data in result.items():
            if table_data:
                has_valid_data = True
                break
        
        if not has_valid_data:
            print("解析结果中没有有效数据")
            return None
        
        return result
        
    except Exception as e:
        print(f"解析结果时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_data_groups(conn) -> List[Dict[str, Any]]:
    """
    从数据库获取按id分组的数据
    
    Args:
        conn: 数据库连接
    
    Returns:
        分组数据列表
    """
    groups = []
    
    try:
        cursor = conn.cursor()
        
        # 查询所有resource_id和entity_id相等的记录
        # 即cultural_resources.id = cultural_entities.id
        query = """
        SELECT DISTINCT cr.id as resource_id
        FROM cultural_resources cr
        INNER JOIN cultural_entities ce ON cr.id = ce.id
        ORDER BY cr.id
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        resource_ids = [row["resource_id"] for row in rows]
        
        print(f"找到 {len(resource_ids)} 个匹配的资源组")
        
        for resource_id in resource_ids:
            group = {"resource_id": resource_id}
            
            # 获取cultural_resources数据（只取需要清洗的字段）
            cursor.execute("""
                SELECT id, content_feature_data
                FROM cultural_resources
                WHERE id = %s
            """, (resource_id,))
            
            cr_row = cursor.fetchone()
            if cr_row:
                group["cultural_resources"] = {
                    "id": cr_row["id"],
                    "content_feature_data": cr_row["content_feature_data"]
                }
            
            # 获取cultural_entities数据（只取需要清洗的字段）
            cursor.execute("""
                SELECT id, entity_name, entity_type, description, period_era,
                       geo_coordinates, cultural_region, style_features, cultural_value
                FROM cultural_entities
                WHERE id = %s
            """, (resource_id,))
            
            ce_row = cursor.fetchone()
            if ce_row:
                group["cultural_entities"] = {
                    "id": ce_row["id"],
                    "entity_name": ce_row["entity_name"],
                    "entity_type": ce_row["entity_type"],
                    "description": ce_row["description"],
                    "period_era": ce_row["period_era"],
                    "geo_coordinates": ce_row["geo_coordinates"],
                    "cultural_region": ce_row["cultural_region"],
                    "style_features": ce_row["style_features"],
                    "cultural_value": ce_row["cultural_value"]
                }
            
            # 获取crawled_images第一条数据（只取需要清洗的字段：tags, festival_name）
            cursor.execute("""
                SELECT id, tags, festival_name, resource_id
                FROM crawled_images
                WHERE resource_id = %s
                ORDER BY id
                LIMIT 1
            """, (resource_id,))
            
            ci_row = cursor.fetchone()
            if ci_row:
                group["crawled_images"] = {
                    "id": ci_row["id"],
                    "tags": ci_row["tags"],
                    "festival_name": ci_row["festival_name"],
                    "resource_id": ci_row["resource_id"]
                }
            
            # 获取该resource_id对应的所有crawled_images记录ID（用于后续批量更新）
            cursor.execute("""
                SELECT id
                FROM crawled_images
                WHERE resource_id = %s
            """, (resource_id,))
            
            group["all_image_ids"] = [row["id"] for row in cursor.fetchall()]
            
            groups.append(group)
        
        return groups
        
    except Exception as e:
        print(f"获取数据组时出错: {e}")
        import traceback
        traceback.print_exc()
        return []


def update_database(conn, resource_id: int, cleaned_data: Dict[str, Any], all_image_ids: List[int]):
    """
    更新数据库
    
    Args:
        conn: 数据库连接
        resource_id: 资源ID
        cleaned_data: 清洗后的数据
        all_image_ids: 该resource_id对应的所有图像ID列表
    """
    try:
        cursor = conn.cursor()
        
        # 更新cultural_resources（只更新content_feature_data）
        if "cultural_resources" in cleaned_data and cleaned_data["cultural_resources"]:
            cr_data = cleaned_data["cultural_resources"]
            if cr_data.get("content_feature_data"):
                cursor.execute("""
                    UPDATE cultural_resources
                    SET content_feature_data = %s
                    WHERE id = %s
                """, (
                    cr_data.get("content_feature_data"),
                    resource_id
                ))
        
        # 更新cultural_entities
        if "cultural_entities" in cleaned_data and cleaned_data["cultural_entities"]:
            ce_data = cleaned_data["cultural_entities"]
            
            # 构建更新语句，只更新有值的字段
            update_fields = []
            update_values = []
            
            if ce_data.get("entity_name"):
                update_fields.append("entity_name = %s")
                update_values.append(ce_data["entity_name"])
            
            if ce_data.get("entity_type"):
                update_fields.append("entity_type = %s")
                update_values.append(ce_data["entity_type"])
            
            if ce_data.get("description"):
                update_fields.append("description = %s")
                update_values.append(ce_data["description"])
            
            if ce_data.get("period_era"):
                update_fields.append("period_era = %s")
                update_values.append(ce_data["period_era"])
            
            if ce_data.get("geo_coordinates"):
                update_fields.append("geo_coordinates = %s")
                update_values.append(ce_data["geo_coordinates"])
            
            if ce_data.get("cultural_region"):
                update_fields.append("cultural_region = %s")
                update_values.append(ce_data["cultural_region"])
            
            if ce_data.get("style_features"):
                update_fields.append("style_features = %s")
                update_values.append(ce_data["style_features"])
            
            if ce_data.get("cultural_value"):
                update_fields.append("cultural_value = %s")
                update_values.append(ce_data["cultural_value"])
            
            if update_fields:
                update_values.append(resource_id)
                sql = f"UPDATE cultural_entities SET {', '.join(update_fields)} WHERE id = %s"
                cursor.execute(sql, tuple(update_values))
        
        # 更新crawled_images（tags和festival_name）
        if "crawled_images" in cleaned_data and cleaned_data["crawled_images"] and all_image_ids:
            ci_data = cleaned_data["crawled_images"]
            
            # 处理tags字段 - 转换为JSON数组格式存储
            tags = ci_data.get("tags", "")
            if tags:
                # 如果是逗号分隔的字符串，转换为列表
                if isinstance(tags, str):
                    # 分割标签（支持中文逗号和英文逗号）
                    tags_list = [t.strip() for t in tags.replace('，', ',').split(',') if t.strip()]
                    # 转换为JSON格式存储
                    tags_json = json.dumps(tags_list, ensure_ascii=False)
                else:
                    tags_json = json.dumps([], ensure_ascii=False)
            else:
                tags_json = json.dumps([], ensure_ascii=False)
            
            festival_name = ci_data.get("festival_name", "")
            
            # 更新所有相同resource_id的记录
            for image_id in all_image_ids:
                update_fields = []
                update_values = []
                
                if tags:
                    update_fields.append("tags = %s")
                    update_values.append(tags_json)
                
                if festival_name:
                    update_fields.append("festival_name = %s")
                    update_values.append(festival_name)
                
                if update_fields:
                    update_values.append(image_id)
                    sql = f"UPDATE crawled_images SET {', '.join(update_fields)} WHERE id = %s"
                    cursor.execute(sql, tuple(update_values))
        
        conn.commit()
        print(f"  ✓ 资源ID {resource_id} 更新成功")
        
    except Exception as e:
        conn.rollback()
        print(f"  ✗ 更新资源ID {resource_id} 时出错: {e}")
        import traceback
        traceback.print_exc()


def main(use_deepseek: bool = True, use_qwen: bool = False):
    """
    主函数：先清洗和搜索，全部完成后再处理无效数据
    
    Args:
        use_deepseek: 是否使用DeepSeek API
        use_qwen: 是否使用通义千问API
    """
    print("=" * 60)
    if use_deepseek:
        print("数据清洗程序启动（使用DeepSeek API）")
    elif use_qwen:
        print("数据清洗程序启动（使用通义千问API）")
    else:
        print("数据清洗程序启动")
    print("=" * 60)
    
    # 检查API密钥
    if use_deepseek and not DEEPSEEK_API_KEY:
        print("错误：请设置DEEPSEEK_API_KEY环境变量")
        return
    if use_qwen and not DASHSCOPE_API_KEY:
        print("错误：请设置DASHSCOPE_API_KEY或ALIYUN_API_KEY环境变量")
        return
    
    # 连接数据库
    conn = get_default_db_connection()
    if not conn:
        print("错误：数据库连接失败")
        return
    
    try:
        # 步骤1: 获取数据组并进行清洗
        print("\n" + "=" * 60)
        print("步骤1: 数据清洗和网络搜索")
        print("=" * 60)
        print("\n正在从数据库获取数据...")
        groups = get_data_groups(conn)
        
        if not groups:
            print("未找到需要清洗的数据")
            return
        
        print(f"\n共找到 {len(groups)} 个数据组需要清洗")
        print("开始清洗...\n")
        
        # 使用DeepSeek或通义千问进行清洗
        if use_deepseek:
            result = clean_with_deepseek(groups, use_online_search=True)
            if result:
                success_count, fail_count = result
            else:
                success_count, fail_count = 0, len(groups)
        elif use_qwen:
            # 使用通义千问清洗（原有逻辑）
            success_count = 0
            fail_count = 0
            
            for idx, group in enumerate(groups, 1):
                resource_id = group["resource_id"]
                print(f"[{idx}/{len(groups)}] 处理资源ID: {resource_id}")
                
                # 构建提示词
                prompt = build_cleaning_prompt(group, use_online_search=True)
                
                # 调用API
                print("  正在调用通义千问API...")
                result_text = call_qwen_api(prompt)
                
                if not result_text:
                    print(f"  ✗ API调用失败，跳过资源ID {resource_id}")
                    fail_count += 1
                    time.sleep(REQUEST_DELAY)
                    continue
                
                # 解析结果
                print("  正在解析清洗结果...")
                cleaned_data = parse_cleaning_result(result_text, group)
                
                if not cleaned_data:
                    print(f"  ✗ 解析清洗结果失败，跳过资源ID {resource_id}")
                    fail_count += 1
                    time.sleep(REQUEST_DELAY)
                    continue
                
                # 更新数据库
                print("  正在更新数据库...")
                all_image_ids = group.get("all_image_ids", [])
                update_database(conn, resource_id, cleaned_data, all_image_ids)
                
                success_count += 1
                print(f"  ✓ 资源ID {resource_id} 清洗完成\n")
                
                # 延迟，避免API限流
                time.sleep(REQUEST_DELAY)
        else:
            print("错误：请指定使用DeepSeek或通义千问API")
            return
        
        print("\n" + "=" * 60)
        print(f"清洗完成！成功: {success_count}, 失败: {fail_count}")
        print("=" * 60)
        
        # 步骤2: 删除无效数据
        print("\n" + "=" * 60)
        print("步骤2: 删除无效节日数据")
        print("=" * 60)
        delete_invalid_festival_data(conn)
        
        print("\n" + "=" * 60)
        print("所有操作完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("\n数据库连接已关闭")


def clean_with_deepseek(groups: List[Dict[str, Any]], use_online_search: bool = True):
    """
    使用DeepSeek API清洗所有数据（支持实时输出进度）
    
    Args:
        groups: 需要清洗的数据组列表
        use_online_search: 是否使用网络搜索来验证period_era
    """
    print("=" * 60)
    print("使用DeepSeek API清洗数据（流式输出模式）")
    print("=" * 60)
    
    # 检查API密钥
    if not DEEPSEEK_API_KEY:
        print("错误：请设置DEEPSEEK_API_KEY环境变量")
        return
    
    # 连接数据库
    conn = get_default_db_connection()
    if not conn:
        print("错误：数据库连接失败")
        return
    
    try:
        cursor = conn.cursor()
        success_count = 0
        fail_count = 0
        
        for idx, group in enumerate(groups, 1):
            resource_id = group["resource_id"]
            print(f"\n[{idx}/{len(groups)}] 处理资源ID: {resource_id}")
            
            # 如果需要网络搜索，先搜索period_era
            if use_online_search and group.get("cultural_entities") and group.get("crawled_images"):
                festival_name = group["crawled_images"].get("festival_name")
                entity_name = group["cultural_entities"].get("entity_name")
                description = group["cultural_entities"].get("description")
                period_era = group["cultural_entities"].get("period_era")
                
                # 如果period_era是"当代"或"现代"，且是少数民族节日，尝试搜索
                if period_era in ["当代", "现代"] and festival_name:
                    print(f"  检测到period_era为'{period_era}'，正在搜索正确的历史时期...")
                    searched_period = search_period_era_online(festival_name, entity_name, description)
                    if searched_period:
                        group["cultural_entities"]["period_era"] = searched_period
                        print(f"  ✓ 搜索到正确时期: {searched_period}")
            
            # 构建提示词
            prompt = build_cleaning_prompt(group, use_online_search=use_online_search)
            
            # 调用DeepSeek API（流式输出）
            print("  正在调用DeepSeek API（流式输出）...")
            print("  ", end="", flush=True)
            
            result_text = None
            def stream_callback(chunk):
                """流式输出回调函数"""
                print(chunk, end="", flush=True)
            
            result_text = call_deepseek_api(prompt, stream=True, callback=stream_callback)
            print()  # 换行
            
            if not result_text:
                print(f"  ✗ API调用失败，跳过资源ID {resource_id}")
                fail_count += 1
                time.sleep(REQUEST_DELAY)
                continue
            
            # 解析结果
            print("  正在解析清洗结果...")
            cleaned_data = parse_cleaning_result(result_text, group)
            
            if not cleaned_data:
                print(f"  ✗ 解析清洗结果失败，跳过资源ID {resource_id}")
                fail_count += 1
                time.sleep(REQUEST_DELAY)
                continue
            
            # 更新数据库
            print("  正在更新数据库...")
            all_image_ids = group.get("all_image_ids", [])
            update_database(conn, resource_id, cleaned_data, all_image_ids)
            
            success_count += 1
            print(f"  ✓ 资源ID {resource_id} 清洗完成")
            
            # 延迟，避免API限流
            time.sleep(REQUEST_DELAY)
        
        print("\n" + "=" * 60)
        print(f"清洗完成！成功: {success_count}, 失败: {fail_count}")
        print("=" * 60)
        
        return success_count, fail_count
        
    except Exception as e:
        print(f"程序执行出错: {e}")
        import traceback
        traceback.print_exc()
        return 0, len(groups)
    finally:
        if conn:
            conn.close()


def clean_failed_records_with_deepseek(resource_ids: List[int]):
    """
    使用DeepSeek API清洗指定的失败记录（保持向后兼容）
    
    Args:
        resource_ids: 需要清洗的资源ID列表
    """
    # 检查API密钥
    if not DEEPSEEK_API_KEY:
        print("错误：请设置DEEPSEEK_API_KEY环境变量")
        return
    
    # 连接数据库获取数据组
    conn = get_default_db_connection()
    if not conn:
        print("错误：数据库连接失败")
        return
    
    try:
        cursor = conn.cursor()
        groups = []
        
        for resource_id in resource_ids:
            group: Dict[str, Any] = {"resource_id": resource_id}
            
            # 获取cultural_resources数据
            cursor.execute("""
                SELECT id, content_feature_data
                FROM cultural_resources
                WHERE id = %s
            """, (resource_id,))
            
            cr_row = cursor.fetchone()
            if cr_row:
                group["cultural_resources"] = {
                    "id": cr_row["id"],
                    "content_feature_data": cr_row["content_feature_data"]
                }
            
            # 获取cultural_entities数据
            cursor.execute("""
                SELECT id, entity_name, entity_type, description, period_era,
                       geo_coordinates, cultural_region, style_features, cultural_value
                FROM cultural_entities
                WHERE id = %s
            """, (resource_id,))
            
            ce_row = cursor.fetchone()
            if ce_row:
                group["cultural_entities"] = {
                    "id": ce_row["id"],
                    "entity_name": ce_row["entity_name"],
                    "entity_type": ce_row["entity_type"],
                    "description": ce_row["description"],
                    "period_era": ce_row["period_era"],
                    "geo_coordinates": ce_row["geo_coordinates"],
                    "cultural_region": ce_row["cultural_region"],
                    "style_features": ce_row["style_features"],
                    "cultural_value": ce_row["cultural_value"]
                }
            
            # 获取crawled_images第一条数据
            cursor.execute("""
                SELECT id, tags, festival_name, resource_id
                FROM crawled_images
                WHERE resource_id = %s
                ORDER BY id
                LIMIT 1
            """, (resource_id,))
            
            ci_row = cursor.fetchone()
            if ci_row:
                group["crawled_images"] = {
                    "id": ci_row["id"],
                    "tags": ci_row["tags"],
                    "festival_name": ci_row["festival_name"],
                    "resource_id": ci_row["resource_id"]
                }
            
            # 获取所有crawled_images记录ID
            cursor.execute("""
                SELECT id
                FROM crawled_images
                WHERE resource_id = %s
            """, (resource_id,))
            
            group["all_image_ids"] = [row["id"] for row in cursor.fetchall()]
            groups.append(group)
        
        # 使用新的清洗函数
        clean_with_deepseek(groups, use_online_search=True)
        
    except Exception as e:
        print(f"程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("\n数据库连接已关闭")


if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--deepseek":
            # 使用DeepSeek清洗指定记录
            if len(sys.argv) > 2:
                resource_ids = [int(x) for x in sys.argv[2:]]
                clean_failed_records_with_deepseek(resource_ids)
            else:
                # 使用DeepSeek清洗所有数据
                main(use_deepseek=True, use_qwen=False)
        elif sys.argv[1] == "--qwen":
            # 使用通义千问清洗所有数据
            main(use_deepseek=False, use_qwen=True)
        else:
            print("用法:")
            print("  python data_cleaning.py              # 使用DeepSeek清洗所有数据")
            print("  python data_cleaning.py --deepseek   # 使用DeepSeek清洗所有数据")
            print("  python data_cleaning.py --deepseek <id1> <id2> ...  # 清洗指定ID")
            print("  python data_cleaning.py --qwen       # 使用通义千问清洗所有数据")
    else:
        # 默认使用DeepSeek清洗所有数据
        main(use_deepseek=True, use_qwen=False)