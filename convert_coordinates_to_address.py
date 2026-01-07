# -*- coding: utf-8 -*-
"""
将 cultural_entities 表中的 geo_coordinates 字段从坐标转换为具体地址
使用网络搜索获取地址信息
"""

import os
import sys
import json
import time
import io
import re
import requests
from typing import Dict, Optional, Tuple, List
from db_connection import get_spider_db_connection
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

# 设置 Windows 控制台编码为 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def parse_coordinates(coords_str: str) -> Optional[Tuple[float, float]]:
    """解析坐标字符串"""
    if not coords_str or not isinstance(coords_str, str):
        return None
    
    coords_str = coords_str.strip()
    coord_pattern = r'([0-9]+\.[0-9]+)[,，\s]+([0-9]+\.[0-9]+)'
    match = re.search(coord_pattern, coords_str)
    if not match:
        return None
    
    try:
        first = float(match.group(1))
        second = float(match.group(2))
        
        if 73 <= first <= 135 and 18 <= second <= 54:
            return (first, second)
        elif 18 <= first <= 54 and 73 <= second <= 135:
            return (second, first)
        else:
            return None
    except ValueError:
        return None


def get_address_from_coordinates(lat: float, lon: float) -> Optional[str]:
    """使用高德地图API获取坐标对应的地址"""
    try:
        # 获取高德API密钥
        gaode_api_key = os.getenv("GAODE_API_KEY")
        if not gaode_api_key:
            print("    [WARN] 未找到GAODE_API_KEY环境变量，无法使用高德API")
            return None
        
        # 使用高德地图逆地理编码API
        url = "https://restapi.amap.com/v3/geocode/regeo"
        params = {
            "key": gaode_api_key,
            "location": f"{lon},{lat}",  # 高德API格式：经度,纬度
            "output": "json",
            "radius": 1000,  # 搜索半径（米）
            "extensions": "base"  # 基础信息即可
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # 检查API返回状态
            if data.get('status') == '1' and 'regeocode' in data:
                regeocode = data['regeocode']
                if 'addressComponent' in regeocode:
                    addr_component = regeocode['addressComponent']
                    
                    # 构建地址字符串（精确到县级或市级）
                    address_parts = []
                    
                    # 辅助函数：安全获取字符串值（处理可能是列表的情况）
                    def safe_get_str(value, default=''):
                        if isinstance(value, list):
                            return value[0] if value else default
                        return str(value).strip() if value else default
                    
                    # 提取省/自治区/直辖市
                    province = safe_get_str(addr_component.get('province', ''))
                    if province:
                        # 高德返回的省名可能不包含"省"字，需要判断
                        if '省' not in province and '自治区' not in province and '特别行政区' not in province and '市' not in province:
                            # 判断是否是直辖市
                            if province in ['北京', '上海', '天津', '重庆']:
                                province += '市'
                            else:
                                province += '省'
                        address_parts.append(province)
                    
                    # 提取市/州/盟
                    city = safe_get_str(addr_component.get('city', ''))
                    district = safe_get_str(addr_component.get('district', ''))
                    
                    # 判断是否是直辖市（直辖市的city字段通常为空或与province相同）
                    is_municipality = province in ['北京市', '上海市', '天津市', '重庆市'] or (not city or city == province.replace('市', ''))
                    
                    if is_municipality:
                        # 直辖市：省+区
                        if district:
                            # district通常已经包含"区"后缀，直接使用
                            address_parts.append(district)
                    else:
                        # 非直辖市：省+市+县/区
                        if city:
                            # 添加市后缀（如果还没有）
                            if '市' not in city and '州' not in city and '盟' not in city and '地区' not in city:
                                city += '市'
                            address_parts.append(city)
                        
                        # 添加县/区
                        if district:
                            # district通常已经包含"县"或"区"后缀，直接使用
                            address_parts.append(district)
                    
                    if address_parts:
                        result = ''.join(address_parts)
                        # 确保至少包含省和市/县
                        if len(result) >= 4:
                            return result
                    
                    # 如果address_parts为空，尝试使用formatted_address
                    formatted_address = regeocode.get('formatted_address', '')
                    if formatted_address:
                        # 从格式化地址中提取省市区
                        chinese_places = re.findall(r'[\u4e00-\u9fa5]+(?:省|市|区|县|自治区|州|盟|特别行政区)', formatted_address)
                        if chinese_places:
                            # 取前3个（省、市、县/区）
                            address_parts = chinese_places[:3]
                            if address_parts:
                                result = ''.join(address_parts)
                                if len(result) >= 4:
                                    return result
                else:
                    # API返回错误信息
                    info = data.get('info', '未知错误')
                    print(f"    [WARN] 高德API返回错误: {info}")
            else:
                # API返回错误
                info = data.get('info', '未知错误')
                print(f"    [WARN] 高德API调用失败: {info}")
        
        # 延迟0.2秒，避免请求过快（高德API有QPS限制，但比Nominatim宽松）
        time.sleep(0.2)
        
    except Exception as e:
        print(f"    网络请求失败: {e}")
        time.sleep(0.2)  # 即使失败也延迟，避免请求过快
        return None
    
    return None


def update_address(conn, entity_id: int, address: str) -> bool:
    """更新数据库中的地址"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE cultural_entities
            SET geo_coordinates = %s
            WHERE id = %s
        """, (address, entity_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"  [ERROR] 更新数据库失败: {e}")
        return False


def get_records_to_process(conn):
    """获取需要处理的记录列表"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, entity_name, geo_coordinates
        FROM cultural_entities
        WHERE geo_coordinates IS NOT NULL
        AND geo_coordinates != ''
        AND geo_coordinates REGEXP '[0-9]+\\.[0-9]+[,，\\s]+[0-9]+\\.[0-9]+'
        AND geo_coordinates NOT REGEXP '[省市区县街道路号]'
        ORDER BY id
    """)
    return cursor.fetchall()


def process_single_record(conn, record):
    """处理单条记录：从高德地图API获取地址并更新数据库"""
    entity_id = record['id']
    entity_name = record['entity_name']
    coords_str = record['geo_coordinates']
    
    # 解析坐标
    coords = parse_coordinates(coords_str)
    if not coords:
        return False, "无法解析坐标格式"
    
    lon, lat = coords
    
    # 通过高德地图API获取地址
    address = get_address_from_coordinates(lat, lon)
    
    if address:
        # 更新数据库
        if update_address(conn, entity_id, address):
            return True, address
        else:
            return False, "数据库更新失败"
    else:
        return False, "无法从高德地图API获取地址"


def main():
    """主函数 - 使用高德地图API逐个处理坐标"""
    print("=" * 60)
    print("坐标转地址工具（使用高德地图API）")
    print("=" * 60)
    
    # 检查API密钥
    gaode_api_key = os.getenv("GAODE_API_KEY")
    if not gaode_api_key:
        print("\n[ERROR] 未找到GAODE_API_KEY环境变量")
        print("请在.env文件中配置GAODE_API_KEY")
        return
    else:
        print(f"\n[OK] 高德API密钥已配置（长度: {len(gaode_api_key)}）")
    
    conn = None
    try:
        # 连接数据库
        conn = get_spider_db_connection()
        if not conn:
            print("\n[ERROR] 数据库连接失败")
            return
        
        print("[OK] 数据库连接成功")
        
        # 获取需要处理的记录
        records = get_records_to_process(conn)
        
        if not records:
            print("\n[OK] 未发现需要转换的坐标记录")
            return
        
        print(f"\n发现 {len(records)} 条需要转换的记录")
        print("开始使用高德地图API进行地址转换")
        print("注意：为避免请求过快，每条记录之间会延迟0.2秒\n")
        
        converted_count = 0
        failed_count = 0
        skipped_count = 0
        
        # 处理所有记录
        for i, record in enumerate(records, 1):
            entity_id = record['id']
            entity_name = record['entity_name']
            coords_str = record['geo_coordinates']
            
            print(f"\n[{i}/{len(records)}] 处理记录 ID {entity_id}: {entity_name}")
            print(f"  原始坐标: {coords_str}")
            
            # 解析坐标
            coords = parse_coordinates(coords_str)
            if not coords:
                print(f"  [SKIP] 无法解析坐标格式")
                skipped_count += 1
                continue
            
            lon, lat = coords
            print(f"  解析结果: 经度 {lon}, 纬度 {lat}")
            print(f"  正在通过高德地图API获取地址...")
            
            # 处理单条记录
            success, message = process_single_record(conn, record)
            
            if success:
                print(f"  [OK] 转换成功: {message}")
                converted_count += 1
            else:
                print(f"  [FAIL] {message}")
                failed_count += 1
            
            # 延迟0.2秒，避免请求过快（高德API有QPS限制）
            if i < len(records):
                time.sleep(0.2)
            
            # 每处理10条记录，输出一次进度
            if i % 10 == 0:
                print(f"\n  进度: {i}/{len(records)} ({i*100//len(records)}%)")
                print(f"  成功: {converted_count}, 失败: {failed_count}, 跳过: {skipped_count}")
        
        print(f"\n" + "=" * 60)
        print("处理完成统计：")
        print("=" * 60)
        print(f"  - 成功转换: {converted_count} 条")
        print(f"  - 转换失败: {failed_count} 条")
        print(f"  - 跳过记录: {skipped_count} 条")
        print(f"  - 总计: {len(records)} 条")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
