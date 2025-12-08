# -*- coding: utf-8 -*-
"""
节日名称转换工具
将中文节日名称转换为英文名称
"""

# 常见传统节日的中英文映射
FESTIVAL_NAME_MAP = {
    # 主要传统节日
    "春节": "Spring Festival",
    "新年": "Spring Festival",
    "农历新年": "Spring Festival",
    "元宵节": "Lantern Festival",
    "上元节": "Lantern Festival",
    "清明节": "Qingming Festival",
    "清明": "Qingming Festival",
    "寒食节": "Cold Food Festival",
    "端午节": "Dragon Boat Festival",
    "端阳节": "Dragon Boat Festival",
    "龙舟节": "Dragon Boat Festival",
    "中秋节": "Mid-Autumn Festival",
    "中秋": "Mid-Autumn Festival",
    "重阳节": "Double Ninth Festival",
    "重阳": "Double Ninth Festival",
    "冬至": "Winter Solstice",
    "冬至节": "Winter Solstice",
    "腊八节": "Laba Festival",
    "小年": "Little New Year",
    "除夕": "New Year's Eve",
    "除夕夜": "New Year's Eve",
    
    # 其他传统节日
    "七夕节": "Qixi Festival",
    "乞巧节": "Qixi Festival",
    "中元节": "Ghost Festival",
    "下元节": "Xia Yuan Festival",
    "花朝节": "Flower Festival",
    "上巳节": "Shangsi Festival",
    "寒衣节": "Cold Clothing Festival",
    "祭灶节": "Kitchen God Festival",
    
    # 少数民族节日
    "泼水节": "Water-Splashing Festival",
    "火把节": "Torch Festival",
    "那达慕": "Naadam Festival",
    "开斋节": "Eid al-Fitr",
    "古尔邦节": "Eid al-Adha",
    "藏历新年": "Tibetan New Year",
    "雪顿节": "Shoton Festival",
    "望果节": "Ongkor Festival",
    
    # 默认值
    "传统节日": "Traditional Festival",
    "节日": "Festival",
}


def chinese_to_english_festival(chinese_name: str) -> str:
    """
    将中文节日名称转换为英文
    
    Args:
        chinese_name: 中文节日名称
    
    Returns:
        英文节日名称，如果找不到映射则返回原名称的拼音形式或"Traditional Festival"
    """
    if not chinese_name:
        return "Traditional Festival"
    
    # 去除可能的空格和标点
    chinese_name = chinese_name.strip()
    
    # 直接匹配
    if chinese_name in FESTIVAL_NAME_MAP:
        return FESTIVAL_NAME_MAP[chinese_name]
    
    # 部分匹配（检查是否包含已知节日名称）
    for cn_name, en_name in FESTIVAL_NAME_MAP.items():
        if cn_name in chinese_name:
            return en_name
    
    # 如果没有找到匹配，返回原名称（可能是英文或拼音）
    # 如果包含中文字符，返回默认值
    if any('\u4e00' <= char <= '\u9fff' for char in chinese_name):
        return "Traditional Festival"
    
    return chinese_name


def extract_and_convert_festival_name(text: str) -> str:
    """
    从文本中提取节日名称并转换为英文
    
    Args:
        text: 包含节日信息的文本
    
    Returns:
        英文节日名称
    """
    if not text:
        return "Traditional Festival"
    
    # 尝试提取节日名称（使用常见的节日关键词）
    import re
    festival_patterns = [
        r'([\u4e00-\u9fa5]{2,10}节)',
        r'([\u4e00-\u9fa5]{2,10}日)',
    ]
    
    for pattern in festival_patterns:
        matches = re.findall(pattern, text)
        if matches:
            # 取第一个匹配的节日名称
            chinese_name = matches[0]
            return chinese_to_english_festival(chinese_name)
    
    # 如果没有找到，返回默认值
    return "Traditional Festival"

