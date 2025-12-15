#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试后端服务是否正常运行
"""
import requests
import json

def test_backend():
    """测试后端服务"""
    base_url = "http://localhost:8000"
    
    print("=" * 60)
    print("测试后端服务")
    print("=" * 60)
    
    # 1. 测试健康检查
    print("\n1. 测试健康检查端点...")
    try:
        response = requests.get(f"{base_url}/api/health", timeout=5)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"   错误: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ❌ 无法连接到后端服务！")
        print("   请确认后端服务（aigc_api_server.py）是否正在运行")
        return False
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False
    
    # 2. 测试资源列表接口
    print("\n2. 测试资源列表接口...")
    try:
        response = requests.get(f"{base_url}/api/home/resources?page=1&page_size=8", timeout=10)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                resources = data.get('resources', [])
                pagination = data.get('pagination', {})
                print(f"   ✅ 成功获取 {len(resources)} 条资源")
                print(f"   分页信息: 第 {pagination.get('page', 1)} 页，共 {pagination.get('total_pages', 0)} 页")
                if len(resources) == 0:
                    print("   ⚠️  资源列表为空，可能是数据库中没有数据")
            else:
                print(f"   ❌ 接口返回失败: {data.get('message', '未知错误')}")
        else:
            print(f"   ❌ HTTP错误: {response.status_code}")
            print(f"   响应: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    return True

if __name__ == '__main__':
    test_backend()
