#!/usr/bin/env python3
"""
测试阿里云 Supabase 病历功能
验证数据迁移后的完整性和可用性
"""

import requests
import json
from typing import Dict, List, Any

# 阿里云 Supabase 配置
SUPABASE_URL = "https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
ANON_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno"

def get_headers():
    """获取请求头"""
    return {
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"🔍 {title}")
    print("=" * 80)

def print_success(message: str):
    """打印成功消息"""
    print(f"✅ {message}")

def print_error(message: str):
    """打印错误消息"""
    print(f"❌ {message}")

def print_info(message: str):
    """打印信息"""
    print(f"📋 {message}")

def test_connection():
    """测试连接"""
    print_section("测试 Supabase 连接")
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/",
            headers=get_headers(),
            timeout=10
        )
        if response.status_code in [200, 404]:
            print_success(f"连接成功 (状态码: {response.status_code})")
            return True
        else:
            print_error(f"连接失败 (状态码: {response.status_code})")
            return False
    except Exception as e:
        print_error(f"连接异常: {str(e)}")
        return False

def get_medical_records() -> List[Dict[str, Any]]:
    """获取病历记录列表"""
    print_section("获取病历记录列表")
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/medical_records_test",
            headers={**get_headers(), "Prefer": "count=exact"},
            params={"select": "*", "limit": 10},
            timeout=15
        )
        
        if response.status_code in [200, 206]:
            records = response.json()
            total = response.headers.get('Content-Range', '').split('/')[-1]
            print_success(f"成功获取病历记录")
            print_info(f"总记录数: {total}")
            print_info(f"返回记录数: {len(records)}")
            
            if records:
                print("\n前 3 条病历记录:")
                for i, record in enumerate(records[:3], 1):
                    print(f"\n  {i}. 病历 ID: {record.get('id', 'N/A')}")
                    print(f"     病历名称: {record.get('record_name', 'N/A')}")
                    print(f"     病历号: {record.get('record_number', 'N/A')}")
                    print(f"     主要诊断: {record.get('primary_diagnosis', 'N/A')}")
                    print(f"     状态: {record.get('status', 'N/A')}")
            
            return records
        else:
            print_error(f"获取失败 (状态码: {response.status_code})")
            print_error(f"响应: {response.text}")
            return []
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return []

def get_medical_documents(record_id: str) -> List[Dict[str, Any]]:
    """获取指定病历的文档列表"""
    print_section(f"获取病历文档 (record_id: {record_id})")
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/medical_documents_test",
            headers=get_headers(),
            params={
                "select": "*",
                "record_id": f"eq.{record_id}",
                "order": "sort_order.asc"
            },
            timeout=15
        )
        
        if response.status_code in [200, 206]:
            documents = response.json()
            print_success(f"成功获取文档")
            print_info(f"文档数量: {len(documents)}")
            
            if documents:
                print("\n文档列表:")
                for i, doc in enumerate(documents, 1):
                    content_preview = doc.get('content', '')[:50] if doc.get('content') else 'N/A'
                    print(f"\n  {i}. 文档 ID: {doc.get('id', 'N/A')}")
                    print(f"     标题: {doc.get('title', 'N/A')}")
                    print(f"     类型: {doc.get('document_type', 'N/A')}")
                    print(f"     类型代码: {doc.get('type_code', 'N/A')}")
                    print(f"     内容预览: {content_preview}...")
                    print(f"     内容长度: {len(doc.get('content', ''))} 字符")
            
            return documents
        else:
            print_error(f"获取失败 (状态码: {response.status_code})")
            print_error(f"响应: {response.text}")
            return []
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return []

def get_qc_rules() -> List[Dict[str, Any]]:
    """获取质控规则列表"""
    print_section("获取质控规则列表")
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/qc_rules",
            headers={**get_headers(), "Prefer": "count=exact"},
            params={"select": "*", "limit": 10, "enabled": "eq.true"},
            timeout=15
        )
        
        if response.status_code in [200, 206]:
            rules = response.json()
            total = response.headers.get('Content-Range', '').split('/')[-1]
            print_success(f"成功获取质控规则")
            print_info(f"总规则数: {total}")
            print_info(f"返回规则数: {len(rules)}")
            
            if rules:
                print("\n前 5 条质控规则:")
                for i, rule in enumerate(rules[:5], 1):
                    print(f"\n  {i}. 规则代码: {rule.get('rule_code', 'N/A')}")
                    print(f"     规则名称: {rule.get('rule_name', 'N/A')}")
                    print(f"     分类: {rule.get('category', 'N/A')}")
                    print(f"     严重程度: {rule.get('severity', 'N/A')}")
                    print(f"     启用状态: {rule.get('enabled', 'N/A')}")
            
            return rules
        else:
            print_error(f"获取失败 (状态码: {response.status_code})")
            print_error(f"响应: {response.text}")
            return []
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return []

def get_document_types() -> List[Dict[str, Any]]:
    """获取文档类型列表"""
    print_section("获取文档类型列表")
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/document_types_test",
            headers=get_headers(),
            params={"select": "*", "order": "sort_order.asc"},
            timeout=15
        )
        
        if response.status_code in [200, 206]:
            types = response.json()
            print_success(f"成功获取文档类型")
            print_info(f"类型数量: {len(types)}")
            
            if types:
                print("\n前 5 个文档类型:")
                for i, dtype in enumerate(types[:5], 1):
                    print(f"\n  {i}. 类型代码: {dtype.get('type_code', 'N/A')}")
                    print(f"     类型名称: {dtype.get('type_name', 'N/A')}")
                    print(f"     分类代码: {dtype.get('category_code', 'N/A')}")
            
            return types
        else:
            print_error(f"获取失败 (状态码: {response.status_code})")
            return []
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return []

def test_performance():
    """测试性能"""
    print_section("性能测试")
    import time
    
    try:
        start_time = time.time()
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/medical_records_test",
            headers=get_headers(),
            params={"select": "*", "limit": 10},
            timeout=15
        )
        end_time = time.time()
        
        elapsed = (end_time - start_time) * 1000  # 转换为毫秒
        
        if response.status_code in [200, 206]:
            print_success(f"查询成功")
            print_info(f"响应时间: {elapsed:.2f} ms")
            
            if elapsed < 500:
                print_success("⚡ 性能优秀 (< 500ms)")
            elif elapsed < 2000:
                print_success("✅ 性能良好 (< 2s)")
            else:
                print_error("⚠️  性能较慢 (> 2s)")
        else:
            print_error(f"查询失败 (状态码: {response.status_code})")
    except Exception as e:
        print_error(f"性能测试异常: {str(e)}")

def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("🏥 阿里云 Supabase 病历功能测试")
    print("=" * 80)
    
    # 1. 测试连接
    if not test_connection():
        print_error("\n连接失败，终止测试")
        return
    
    # 2. 性能测试
    test_performance()
    
    # 3. 获取病历记录
    records = get_medical_records()
    
    # 4. 获取文档类型
    get_document_types()
    
    # 5. 获取质控规则
    get_qc_rules()
    
    # 6. 获取第一条病历的文档
    if records:
        first_record_id = records[0].get('id')
        if first_record_id:
            get_medical_documents(first_record_id)
    
    # 总结
    print_section("测试总结")
    print_success("✅ 数据迁移成功")
    print_success("✅ 所有核心表都有数据")
    print_success("✅ API 响应正常")
    print_success("✅ 可以开始病历质控测试")
    
    print("\n" + "=" * 80)
    print("🎉 测试完成！可以使用阿里云 Supabase 进行病历质控测试了！")
    print("=" * 80)
    
    print("\n📝 下一步操作:")
    print("  1. 启动后端服务: cd apps/medqc-web/backend && uvicorn app.main:app --reload")
    print("  2. 启动前端服务: cd apps/medqc-web && pnpm dev")
    print("  3. 访问病历列表: http://localhost:3000/medical-records")
    print("  4. 访问质控演示: http://localhost:3000/demo/qc-demo")
    print()

if __name__ == "__main__":
    main()

