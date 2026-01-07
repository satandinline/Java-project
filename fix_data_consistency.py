# -*- coding: utf-8 -*-
"""
数据一致性修复脚本
1. 检查并删除孤立的 crawled_images 记录
2. 为缺失的 cultural_resources 记录创建对应的 crawled_images 记录
3. 重新排序所有表的 id（从1开始按顺序叠加）
"""

import os
import json
import sys
import io
from typing import Dict, List, Optional, Any
from PIL import Image
from db_connection import get_spider_db_connection

# 设置 Windows 控制台编码为 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_default_image_info():
    """获取default.jpg的信息（尺寸等）"""
    default_image_path = os.path.join(BASE_DIR, "FrontEnd", "public", "default.jpg")
    dimensions = "200x200"  # 默认尺寸
    
    if os.path.exists(default_image_path):
        try:
            with Image.open(default_image_path) as img:
                dimensions = f"{img.width}x{img.height}"
        except:
            pass
    
    return dimensions


def delete_orphaned_crawled_images(conn):
    """
    删除孤立的 crawled_images 记录
    即 resource_id 或 entity_id 在对应表中不存在的记录
    """
    print("\n" + "=" * 60)
    print("步骤1: 删除孤立的 crawled_images 记录")
    print("=" * 60)
    
    cursor = conn.cursor()
    
    try:
        # 查找孤立的记录（resource_id 不为空但在 cultural_resources 中不存在）
        cursor.execute("""
            SELECT ci.id, ci.resource_id, ci.entity_id
            FROM crawled_images ci
            LEFT JOIN cultural_resources cr ON ci.resource_id = cr.id
            WHERE ci.resource_id IS NOT NULL AND cr.id IS NULL
        """)
        orphaned_by_resource = cursor.fetchall()
        
        # 查找孤立的记录（entity_id 不为空但在 cultural_entities 中不存在）
        cursor.execute("""
            SELECT ci.id, ci.resource_id, ci.entity_id
            FROM crawled_images ci
            LEFT JOIN cultural_entities ce ON ci.entity_id = ce.id
            WHERE ci.entity_id IS NOT NULL AND ce.id IS NULL
        """)
        orphaned_by_entity = cursor.fetchall()
        
        # 合并并去重
        orphaned_ids = set()
        orphaned_info = []
        
        for row in orphaned_by_resource:
            orphaned_ids.add(row['id'])
            orphaned_info.append({
                'id': row['id'],
                'resource_id': row['resource_id'],
                'entity_id': row['entity_id'],
                'reason': 'resource_id 不存在'
            })
        
        for row in orphaned_by_entity:
            if row['id'] not in orphaned_ids:
                orphaned_ids.add(row['id'])
                orphaned_info.append({
                    'id': row['id'],
                    'resource_id': row['resource_id'],
                    'entity_id': row['entity_id'],
                    'reason': 'entity_id 不存在'
                })
        
        if orphaned_ids:
            print(f"\n发现 {len(orphaned_ids)} 条孤立的 crawled_images 记录：")
            for info in orphaned_info:
                print(f"  - ID: {info['id']}, resource_id: {info['resource_id']}, entity_id: {info['entity_id']}, 原因: {info['reason']}")
            
            # 删除孤立的记录
            placeholders = ','.join(['%s'] * len(orphaned_ids))
            cursor.execute(f"""
                DELETE FROM crawled_images
                WHERE id IN ({placeholders})
            """, list(orphaned_ids))
            
            conn.commit()
            print(f"\n[OK] 已删除 {len(orphaned_ids)} 条孤立的 crawled_images 记录")
        else:
            print("\n[OK] 未发现孤立的 crawled_images 记录")
        
        return len(orphaned_ids)
        
    except Exception as e:
        print(f"\n[ERROR] 删除孤立记录时出错: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return 0


def create_missing_crawled_images(conn):
    """
    为 cultural_resources 表中没有对应 crawled_images 记录的记录创建默认图片记录
    """
    print("\n" + "=" * 60)
    print("步骤2: 为缺失的 cultural_resources 创建 crawled_images 记录")
    print("=" * 60)
    
    cursor = conn.cursor()
    
    try:
        # 查找没有对应 crawled_images 记录的 cultural_resources
        cursor.execute("""
            SELECT cr.id, cr.title, cr.resource_type, cr.file_format
            FROM cultural_resources cr
            LEFT JOIN crawled_images ci ON cr.id = ci.resource_id
            WHERE ci.id IS NULL
        """)
        missing_resources = cursor.fetchall()
        
        if not missing_resources:
            print("\n[OK] 所有 cultural_resources 都有对应的 crawled_images 记录")
            return 0
        
        print(f"\n发现 {len(missing_resources)} 条 cultural_resources 记录缺少对应的 crawled_images 记录")
        
        # 获取默认图片信息
        dimensions = get_default_image_info()
        file_name = "default.jpg"
        storage_path = "FrontEnd/public/default.jpg"
        
        created_count = 0
        
        for resource in missing_resources:
            resource_id = resource['id']
            title = resource['title']
            festival_name = title  # 使用 title 作为 festival_name
            
            # 查找对应的 entity_id（如果有的话）
            entity_id = None
            cursor.execute("""
                SELECT id FROM cultural_entities
                WHERE entity_name = %s
                LIMIT 1
            """, (title,))
            entity_result = cursor.fetchone()
            if entity_result:
                entity_id = entity_result['id']
            
            # 创建标签
            tags_json = None
            if festival_name:
                tags_json = json.dumps([festival_name], ensure_ascii=False)
            
            # 插入 crawled_images 记录
            try:
                cursor.execute("""
                    INSERT INTO crawled_images 
                    (file_name, storage_path, dimensions, tags, crawl_time, resource_id, entity_id, festival_name)
                    VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s)
                """, (file_name, storage_path, dimensions, tags_json, resource_id, entity_id, festival_name))
                
                created_count += 1
                print(f"  [OK] 为资源 ID {resource_id} ({title}) 创建了默认图片记录")
                
            except Exception as e:
                print(f"  [ERROR] 为资源 ID {resource_id} 创建图片记录失败: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        print(f"\n[OK] 已为 {created_count} 条 cultural_resources 记录创建了对应的 crawled_images 记录")
        
        return created_count
        
    except Exception as e:
        print(f"\n[ERROR] 创建缺失记录时出错: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return 0


def reorder_table_ids(conn, table_name: str, primary_key: str = 'id'):
    """
    重新排序指定表的 id（从1开始按顺序叠加）
    
    Args:
        conn: 数据库连接
        table_name: 表名
        primary_key: 主键字段名，默认为 'id'
    """
    cursor = conn.cursor()
    
    try:
        # 获取所有记录，按当前 id 排序
        cursor.execute(f"SELECT {primary_key} FROM {table_name} ORDER BY {primary_key}")
        records = cursor.fetchall()
        
        if not records:
            return 0
        
        # 创建临时映射表：旧 id -> 新 id
        id_mapping = {}
        new_id = 1
        for record in records:
            old_id = record[primary_key]
            if old_id != new_id:
                id_mapping[old_id] = new_id
            new_id += 1
        
        if not id_mapping:
            return 0  # 无需重新排序
        
        # 禁用外键检查（临时）
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 获取表的所有外键引用信息
        cursor.execute("""
            SELECT 
                CONSTRAINT_NAME,
                TABLE_NAME,
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
            AND REFERENCED_TABLE_NAME = %s
            AND REFERENCED_COLUMN_NAME = %s
        """, (table_name, primary_key))
        foreign_keys = cursor.fetchall()
        
        # 使用临时 id 避免冲突
        # 先计算一个足够大的临时偏移量
        max_existing_id = max(record[primary_key] for record in records)
        temp_offset = max(max_existing_id, 1000000) + 1
        
        # 第一步：将需要更新的记录先移到临时 id
        for old_id, new_id in id_mapping.items():
            cursor.execute(f"""
                UPDATE {table_name}
                SET {primary_key} = %s
                WHERE {primary_key} = %s
            """, (old_id + temp_offset, old_id))
        
        # 第二步：更新所有引用该表的外键（使用临时 id）
        for fk in foreign_keys:
            ref_table = fk['TABLE_NAME']
            ref_column = fk['COLUMN_NAME']
            
            # 更新外键引用：从旧 id 更新到临时 id
            for old_id, new_id in id_mapping.items():
                cursor.execute(f"""
                    UPDATE {ref_table}
                    SET {ref_column} = %s
                    WHERE {ref_column} = %s
                """, (old_id + temp_offset, old_id))
        
        # 第三步：将临时 id 更新为最终 id
        for old_id, new_id in id_mapping.items():
            cursor.execute(f"""
                UPDATE {table_name}
                SET {primary_key} = %s
                WHERE {primary_key} = %s
            """, (new_id, old_id + temp_offset))
        
        # 第四步：更新外键引用：从临时 id 更新到新 id
        for fk in foreign_keys:
            ref_table = fk['TABLE_NAME']
            ref_column = fk['COLUMN_NAME']
            
            for old_id, new_id in id_mapping.items():
                cursor.execute(f"""
                    UPDATE {ref_table}
                    SET {ref_column} = %s
                    WHERE {ref_column} = %s
                """, (new_id, old_id + temp_offset))
        
        # 更新 AUTO_INCREMENT
        max_id = len(records)
        cursor.execute(f"ALTER TABLE {table_name} AUTO_INCREMENT = {max_id + 1}")
        
        # 重新启用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        
        return len(id_mapping)
        
    except Exception as e:
        print(f"\n[ERROR] 重新排序表 {table_name} 的 id 时出错: {e}")
        conn.rollback()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        import traceback
        traceback.print_exc()
        return 0


def reorder_all_tables(conn):
    """
    重新排序所有相关表的 id（从1开始按顺序叠加）
    按照依赖关系排序：先排序被引用的表，再排序引用表
    """
    print("\n" + "=" * 60)
    print("步骤3: 重新排序所有表的 id（从1开始按顺序叠加）")
    print("=" * 60)
    
    # 按照依赖关系排序：cultural_resources 和 cultural_entities 先排序，然后 crawled_images
    tables = [
        ('cultural_resources', 'id'),
        ('cultural_entities', 'id'),
        ('crawled_images', 'id'),
    ]
    
    total_reordered = 0
    
    for table_name, primary_key in tables:
        print(f"\n正在重新排序表 {table_name}...")
        reordered_count = reorder_table_ids(conn, table_name, primary_key)
        if reordered_count > 0:
            print(f"  [OK] 表 {table_name} 已重新排序，更新了 {reordered_count} 条记录的 id")
            total_reordered += reordered_count
        else:
            print(f"  [OK] 表 {table_name} 的 id 已经是连续的，无需重新排序")
    
    print(f"\n[OK] 所有表重新排序完成，共更新了 {total_reordered} 条记录的 id")
    
    return total_reordered


def verify_data_consistency(conn):
    """
    验证数据一致性
    """
    print("\n" + "=" * 60)
    print("步骤4: 验证数据一致性")
    print("=" * 60)
    
    cursor = conn.cursor()
    
    try:
        # 检查孤立的 crawled_images 记录
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM crawled_images ci
            LEFT JOIN cultural_resources cr ON ci.resource_id = cr.id
            WHERE ci.resource_id IS NOT NULL AND cr.id IS NULL
        """)
        orphaned_by_resource = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM crawled_images ci
            LEFT JOIN cultural_entities ce ON ci.entity_id = ce.id
            WHERE ci.entity_id IS NOT NULL AND ce.id IS NULL
        """)
        orphaned_by_entity = cursor.fetchone()['count']
        
        # 检查缺失的 crawled_images 记录
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM cultural_resources cr
            LEFT JOIN crawled_images ci ON cr.id = ci.resource_id
            WHERE ci.id IS NULL
        """)
        missing_images = cursor.fetchone()['count']
        
        print(f"\n数据一致性检查结果：")
        print(f"  - 孤立的 crawled_images 记录（resource_id 不存在）: {orphaned_by_resource} 条")
        print(f"  - 孤立的 crawled_images 记录（entity_id 不存在）: {orphaned_by_entity} 条")
        print(f"  - 缺失的 crawled_images 记录: {missing_images} 条")
        
        if orphaned_by_resource == 0 and orphaned_by_entity == 0 and missing_images == 0:
            print("\n[OK] 数据一致性验证通过！")
            return True
        else:
            print("\n[ERROR] 数据一致性验证失败，仍有不一致的数据")
            return False
        
    except Exception as e:
        print(f"\n[ERROR] 验证数据一致性时出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("数据一致性修复脚本")
    print("=" * 60)
    
    conn = None
    try:
        # 连接数据库
        conn = get_spider_db_connection()
        if not conn:
            print("[ERROR] 数据库连接失败")
            return
        
        print("[OK] 数据库连接成功")
        
        # 步骤1: 删除孤立的 crawled_images 记录
        deleted_count = delete_orphaned_crawled_images(conn)
        
        # 步骤2: 为缺失的 cultural_resources 创建 crawled_images 记录
        created_count = create_missing_crawled_images(conn)
        
        # 步骤3: 重新排序所有表的 id
        reordered_count = reorder_all_tables(conn)
        
        # 步骤4: 验证数据一致性
        is_consistent = verify_data_consistency(conn)
        
        print("\n" + "=" * 60)
        print("修复完成！")
        print("=" * 60)
        print(f"  - 删除孤立记录: {deleted_count} 条")
        print(f"  - 创建缺失记录: {created_count} 条")
        print(f"  - 重新排序记录: {reordered_count} 条")
        print(f"  - 数据一致性: {'通过' if is_consistent else '失败'}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("\n数据库连接已关闭")


if __name__ == "__main__":
    main()

