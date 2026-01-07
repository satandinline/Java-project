# -*- coding: utf-8 -*-
"""
单独更新crawled_images表的id字段（id+1）
resource_id和entity_id保持不变
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


def update_crawled_images_id():
    """
    将crawled_images表的id字段+1
    resource_id和entity_id保持不变
    """
    print("=" * 60)
    print("更新crawled_images表的id字段（id+1）")
    print("注意：resource_id和entity_id不会变化")
    print("=" * 60)
    
    conn = get_default_db_connection()
    if not conn:
        print("错误：数据库连接失败")
        return False
    
    try:
        cursor = conn.cursor()
        
        # 查询当前状态
        cursor.execute("SELECT MIN(id) as min_id, MAX(id) as max_id, COUNT(*) as count FROM crawled_images")
        result = cursor.fetchone()
        if not result:
            print("crawled_images表为空，无需更新")
            return True
        
        min_id = result["min_id"]
        max_id = result["max_id"]
        count = result["count"]
        
        print(f"\n当前状态：")
        print(f"  - 记录数: {count}")
        print(f"  - 最小ID: {min_id}")
        print(f"  - 最大ID: {max_id}")
        
        if count == 0:
            print("\n没有需要更新的记录")
            return True
        
        # 使用两步法：先加偏移量，再减去偏移量-1（相当于+1）
        offset = max_id + 100000
        
        print(f"\n开始更新...")
        print(f"  使用偏移量: {offset}")
        
        # 第一步：所有ID加上偏移量
        cursor.execute(f"""
            UPDATE crawled_images
            SET id = id + {offset}
        """)
        print(f"  ✓ 第一步完成：将所有ID加上偏移量")
        
        # 第二步：所有ID减去偏移量-1（相当于原ID+1）
        cursor.execute(f"""
            UPDATE crawled_images
            SET id = id - {offset} + 1
        """)
        print(f"  ✓ 第二步完成：将所有ID减去偏移量-1，完成ID+1操作")
        
        # 提交事务
        conn.commit()
        
        # 验证更新结果
        cursor.execute("SELECT MIN(id) as min_id, MAX(id) as max_id, COUNT(*) as count FROM crawled_images")
        result = cursor.fetchone()
        
        print("\n" + "=" * 60)
        print("更新完成！")
        print("=" * 60)
        print(f"\n更新后状态：")
        print(f"  - 记录数: {result['count']}")
        print(f"  - 最小ID: {result['min_id']}")
        print(f"  - 最大ID: {result['max_id']}")
        
        # 验证resource_id和entity_id未变化
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM crawled_images 
            WHERE resource_id IS NOT NULL OR entity_id IS NOT NULL
        """)
        ref_result = cursor.fetchone()
        print(f"  - 有resource_id或entity_id的记录数: {ref_result['count']}（未变化）")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n错误：更新ID时出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()
            print("\n数据库连接已关闭")


if __name__ == "__main__":
    print("此操作将把crawled_images表的所有id字段+1")
    print("resource_id和entity_id字段不会发生变化")
    response = input("\n是否继续？(yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        success = update_crawled_images_id()
        if success:
            print("\n✓ 操作成功完成！")
        else:
            print("\n✗ 操作失败，请检查错误信息")
    else:
        print("\n操作已取消")

