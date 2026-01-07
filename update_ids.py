# -*- coding: utf-8 -*-
"""
更新数据库ID脚本
删除id=1的记录后，将所有相关表的ID都减1
"""

import sys
import os
from db_connection import get_default_db_connection

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass


def update_all_ids():
    """
    更新所有相关表的ID（所有ID减1）
    """
    print("=" * 60)
    print("开始更新数据库ID（所有ID减1）")
    print("=" * 60)
    
    conn = get_default_db_connection()
    if not conn:
        print("错误：数据库连接失败")
        return False
        
    
    try:
        cursor = conn.cursor()
        
        # 禁用外键检查（临时）
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 1. 更新entity_relationships表的source_entity_id和target_entity_id
        print("\n1. 更新entity_relationships表的source_entity_id和target_entity_id...")
        cursor.execute("""
            UPDATE entity_relationships
            SET source_entity_id = source_entity_id - 1
            WHERE source_entity_id > 1
        """)
        source_count = cursor.rowcount
        print(f"   更新了 {source_count} 条source_entity_id记录")
        
        cursor.execute("""
            UPDATE entity_relationships
            SET target_entity_id = target_entity_id - 1
            WHERE target_entity_id > 1
        """)
        target_count = cursor.rowcount
        print(f"   更新了 {target_count} 条target_entity_id记录")
        
        # 2. 更新crawled_images表的resource_id和entity_id
        print("\n2. 更新crawled_images表的resource_id和entity_id...")
        cursor.execute("""
            UPDATE crawled_images
            SET resource_id = resource_id - 1
            WHERE resource_id > 1 AND resource_id IS NOT NULL
        """)
        resource_count = cursor.rowcount
        print(f"   更新了 {resource_count} 条resource_id记录")
        
        cursor.execute("""
            UPDATE crawled_images
            SET entity_id = entity_id - 1
            WHERE entity_id > 1 AND entity_id IS NOT NULL
        """)
        entity_count = cursor.rowcount
        print(f"   更新了 {entity_count} 条entity_id记录")
        
        # 3. 更新cultural_entities表的id（注意：这个表的id就是主键，需要特殊处理）
        print("\n3. 更新cultural_entities表的id...")
        # 由于id是主键，需要使用两步法：先加一个大偏移量，再减去偏移量+1
        cursor.execute("SELECT MAX(id) as max_id, COUNT(*) as count FROM cultural_entities")
        result = cursor.fetchone()
        max_id = result["max_id"] if result and result["max_id"] else 0
        count = result["count"] if result and result["count"] else 0
        
        if count > 0:
            # 使用一个足够大的偏移量（比最大ID大）
            offset = max_id + 100000
            
            # 第一步：所有ID加上偏移量
            cursor.execute(f"""
                UPDATE cultural_entities
                SET id = id + {offset}
            """)
            print(f"   第一步：将所有ID加上偏移量 {offset}")
            
            # 第二步：所有ID减去偏移量+1（相当于原ID-1）
            cursor.execute(f"""
                UPDATE cultural_entities
                SET id = id - {offset} - 1
            """)
            print(f"   第二步：将所有ID减去偏移量+1，完成ID-1操作")
            print(f"   更新了 {count} 条cultural_entities记录")
        else:
            print("   没有需要更新的cultural_entities记录")
        
        # 4. 更新cultural_resources表的id
        print("\n4. 更新cultural_resources表的id...")
        cursor.execute("SELECT MAX(id) as max_id, COUNT(*) as count FROM cultural_resources")
        result = cursor.fetchone()
        max_id = result["max_id"] if result and result["max_id"] else 0
        count = result["count"] if result and result["count"] else 0
        
        if count > 0:
            # 使用一个足够大的偏移量（比最大ID大）
            offset = max_id + 100000
            
            # 第一步：所有ID加上偏移量
            cursor.execute(f"""
                UPDATE cultural_resources
                SET id = id + {offset}
            """)
            print(f"   第一步：将所有ID加上偏移量 {offset}")
            
            # 第二步：所有ID减去偏移量+1（相当于原ID-1）
            cursor.execute(f"""
                UPDATE cultural_resources
                SET id = id - {offset} - 1
            """)
            print(f"   第二步：将所有ID减去偏移量+1，完成ID-1操作")
            print(f"   更新了 {count} 条cultural_resources记录")
        else:
            print("   没有需要更新的cultural_resources记录")
        
        # 5. 更新crawled_images表的id（id+1，resource_id和entity_id不变）
        print("\n5. 更新crawled_images表的id（id+1）...")
        cursor.execute("SELECT MAX(id) as max_id, COUNT(*) as count FROM crawled_images")
        result = cursor.fetchone()
        max_id = result["max_id"] if result and result["max_id"] else 0
        count = result["count"] if result and result["count"] else 0
        
        if count > 0:
            # 使用两步法：先加偏移量，再减去偏移量-1（相当于+1）
            offset = max_id + 100000
            
            # 第一步：所有ID加上偏移量
            cursor.execute(f"""
                UPDATE crawled_images
                SET id = id + {offset}
            """)
            print(f"   第一步：将所有ID加上偏移量 {offset}")
            
            # 第二步：所有ID减去偏移量-1（相当于原ID+1）
            cursor.execute(f"""
                UPDATE crawled_images
                SET id = id - {offset} + 1
            """)
            print(f"   第二步：将所有ID减去偏移量-1，完成ID+1操作")
            print(f"   更新了 {count} 条crawled_images记录的id（resource_id和entity_id未变化）")
        else:
            print("   没有需要更新的crawled_images记录")
        
        # 6. 更新其他可能引用resource_id或entity_id的表
        # 6.1 annotation_tasks表的resource_id
        print("\n6. 更新其他引用表...")
        try:
            cursor.execute("""
                UPDATE annotation_tasks
                SET resource_id = resource_id - 1
                WHERE resource_id > 1 AND resource_id IS NOT NULL
            """)
            annotation_count = cursor.rowcount
            if annotation_count > 0:
                print(f"   更新了 {annotation_count} 条annotation_tasks.resource_id记录")
        except Exception as e:
            print(f"   跳过annotation_tasks表（可能不存在相关字段）: {e}")
        
        # 5.2 user_ratings表的resource_id
        try:
            cursor.execute("""
                UPDATE user_ratings
                SET resource_id = resource_id - 1
                WHERE resource_id > 1 AND resource_id IS NOT NULL
            """)
            ratings_count = cursor.rowcount
            if ratings_count > 0:
                print(f"   更新了 {ratings_count} 条user_ratings.resource_id记录")
        except Exception as e:
            print(f"   跳过user_ratings表（可能不存在相关字段）: {e}")
        
        # 5.3 user_comments表的resource_id
        try:
            cursor.execute("""
                UPDATE user_comments
                SET resource_id = resource_id - 1
                WHERE resource_id > 1 AND resource_id IS NOT NULL
            """)
            comments_count = cursor.rowcount
            if comments_count > 0:
                print(f"   更新了 {comments_count} 条user_comments.resource_id记录")
        except Exception as e:
            print(f"   跳过user_comments表（可能不存在相关字段）: {e}")
        
        # 恢复外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        # 提交事务
        conn.commit()
        
        print("\n" + "=" * 60)
        print("ID更新完成！")
        print("=" * 60)
        
        # 验证更新结果
        print("\n验证更新结果：")
        cursor.execute("SELECT MIN(id) as min_id, MAX(id) as max_id, COUNT(*) as count FROM cultural_resources")
        result = cursor.fetchone()
        if result:
            print(f"cultural_resources表: 最小ID={result['min_id']}, 最大ID={result['max_id']}, 记录数={result['count']}")
        
        cursor.execute("SELECT MIN(id) as min_id, MAX(id) as max_id, COUNT(*) as count FROM cultural_entities")
        result = cursor.fetchone()
        if result:
            print(f"cultural_entities表: 最小ID={result['min_id']}, 最大ID={result['max_id']}, 记录数={result['count']}")
        
        cursor.execute("SELECT COUNT(*) as count FROM crawled_images WHERE resource_id = 1")
        result = cursor.fetchone()
        if result:
            print(f"crawled_images表中resource_id=1的记录数: {result['count']}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n错误：更新ID时出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 确保恢复外键检查
        try:
            temp_cursor = conn.cursor()
            temp_cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        except:
            pass
        
        return False
    finally:
        if conn:
            conn.close()
            print("\n数据库连接已关闭")


if __name__ == "__main__":
    print("警告：此操作将更新数据库中所有相关表的ID（所有ID减1）")
    print("请确保已经删除了id=1的记录")
    response = input("\n是否继续？(yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        success = update_all_ids()
        if success:
            print("\n✓ 操作成功完成！")
        else:
            print("\n✗ 操作失败，请检查错误信息")
    else:
        print("\n操作已取消")

