# -*- coding: utf-8 -*-
"""
爬虫主运行文件
统一运行所有爬虫
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from minzu_festivals_spider import MinzuFestivalsSpider
from wikipedia_spider import WikipediaSpider


def main():
    """主函数：依次运行所有爬虫"""
    print("=" * 60)
    print("开始运行所有爬虫...")
    print("=" * 60)
    
    spiders = []
    
    try:
        # 1. 运行中国民族文化资源库爬虫
        print("\n" + "=" * 60)
        print("1. 运行中国民族文化资源库爬虫")
        print("=" * 60)
        minzu_spider = MinzuFestivalsSpider()
        spiders.append(minzu_spider)
        minzu_spider.run(max_pages=50)
        minzu_spider.close()
        print("✓ 中国民族文化资源库爬虫完成")
        
        # 2. 运行维基百科爬虫
        print("\n" + "=" * 60)
        print("2. 运行维基百科爬虫")
        print("=" * 60)
        wiki_spider = WikipediaSpider()
        spiders.append(wiki_spider)
        wiki_spider.run()
        wiki_spider.close()
        print("✓ 维基百科爬虫完成")
        
        print("\n" + "=" * 60)
        print("所有爬虫运行完成！")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n用户中断，正在关闭所有爬虫...")
        for spider in spiders:
            try:
                spider.close()
            except:
                pass
        sys.exit(0)
    except Exception as e:
        print(f"\n\n发生错误: {e}")
        # 确保所有爬虫都关闭
        for spider in spiders:
            try:
                spider.close()
            except:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()

