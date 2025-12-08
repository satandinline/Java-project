# -*- coding: utf-8 -*-
"""
实体类型工具
用于标准化实体类型，确保只使用允许的类型值
"""

# 允许的实体类型
ALLOWED_ENTITY_TYPES = ['人物', '作品', '事件', '地点', '其他']


def normalize_entity_type(entity_type: str) -> str:
    """
    标准化实体类型，确保只返回允许的类型值
    
    Args:
        entity_type: 原始实体类型
    
    Returns:
        标准化后的实体类型（人物、作品、事件、地点、其他）
    """
    if not entity_type:
        return '其他'
    
    entity_type = entity_type.strip()
    
    # 直接匹配
    if entity_type in ALLOWED_ENTITY_TYPES:
        return entity_type
    
    # 模糊匹配（处理一些常见变体）
    entity_type_lower = entity_type.lower()
    
    # 人物相关
    if any(keyword in entity_type_lower for keyword in ['人物', '人', '角色', '人物', 'person', 'character']):
        return '人物'
    
    # 作品相关
    if any(keyword in entity_type_lower for keyword in ['作品', '作品', '创作', '艺术品', 'work', 'artwork', 'creation']):
        return '作品'
    
    # 事件相关
    if any(keyword in entity_type_lower for keyword in ['事件', '活动', '仪式', '庆典', 'event', 'activity', 'ceremony']):
        return '事件'
    
    # 地点相关
    if any(keyword in entity_type_lower for keyword in ['地点', '地方', '位置', '场所', 'place', 'location', 'site']):
        return '地点'
    
    # 默认返回"其他"
    return '其他'


def detect_entity_type_from_content(content: str, entity_name: str = "") -> str:
    """
    从内容中检测实体类型
    
    Args:
        content: 实体描述内容
        entity_name: 实体名称（可选）
    
    Returns:
        检测到的实体类型
    """
    if not content:
        return '其他'
    
    text = (entity_name + " " + content).lower()
    
    # 人物关键词
    person_keywords = ['人物', '人', '角色', '传说', '历史人物', '名人', 'person', 'character', 'legend']
    if any(keyword in text for keyword in person_keywords):
        return '人物'
    
    # 作品关键词
    work_keywords = ['作品', '创作', '艺术品', '绘画', '雕塑', '文学', 'work', 'artwork', 'creation', 'painting']
    if any(keyword in text for keyword in work_keywords):
        return '作品'
    
    # 事件关键词
    event_keywords = ['事件', '活动', '仪式', '庆典', '节日', '习俗', 'event', 'activity', 'ceremony', 'festival']
    if any(keyword in text for keyword in event_keywords):
        return '事件'
    
    # 地点关键词
    place_keywords = ['地点', '地方', '位置', '场所', '建筑', '遗址', 'place', 'location', 'site', 'building']
    if any(keyword in text for keyword in place_keywords):
        return '地点'
    
    return '其他'

