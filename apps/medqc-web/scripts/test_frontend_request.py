#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试前端发送的质控请求格式
模拟前端实际发送的请求数据
"""

import json
import requests
from typing import Dict, Any

API_BASE_URL = "http://localhost:8001"

def get_documents_data():
    """获取实际的文书数据"""
    record_id = "7fcb8e4c-3892-40c4-92f3-19bf5061aa41"
    response = requests.get(f"{API_BASE_URL}/api/medical-records/{record_id}/documents")
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ 获取文书数据失败: {response.status_code}")
        return None

def build_documents_by_type(data, document_types):
    """构建文书类型映射，模拟前端逻辑"""
    
    # 文书类型映射
    type_mapping = {
        # 入院记录相关
        '入院记录': '入院记录',
        '住院病历': '入院记录',
        '入院病历': '入院记录',
        '入院诊断': '入院记录',
        
        # 病程记录相关
        '病程记录': '病程记录',
        '日常病程': '病程记录',
        '首次病程': '病程记录',
        '首次病程记录': '病程记录',
        '主治医师查房': '病程记录',
        '上级医师查房': '病程记录',
        '上级医师查房记录': '病程记录',
        '主任医师查房': '病程记录',
        '主任医师查房记录': '病程记录',
        '日常病程记录': '病程记录',
        '病程记录单': '病程记录',
        
        # 手术记录相关
        '手术记录': '手术记录',
        '手术操作记录': '手术记录',
        '术前小结': '手术记录',
        '术后记录': '手术记录',
        '术前讨论': '手术记录',
        '术前讨论记录': '手术记录',
        '术前查房': '手术记录',
        '术前查房记录': '手术记录',
        '手术同意书': '手术记录',
        
        # 出院记录相关
        '出院记录': '出院记录',
        '出院小结': '出院记录',
        '出院诊断': '出院记录',
        '出院医嘱': '出院记录'
    }
    
    documents_by_type = {}
    
    # 遍历分类数据
    if data.get('categories') and isinstance(data['categories'], list):
        for category in data['categories']:
            if category.get('documents') and isinstance(category['documents'], list):
                for doc in category['documents']:
                    # 映射文书类型名称
                    original_type_name = doc.get('type_info', {}).get('type_name', '') or doc.get('type_name', '')
                    doc_type_name = type_mapping.get(original_type_name, original_type_name)
                    
                    print(f"📋 文书映射: \"{original_type_name}\" -> \"{doc_type_name}\"")
                    
                    if doc_type_name in document_types and doc.get('content'):
                        if doc_type_name not in documents_by_type:
                            documents_by_type[doc_type_name] = []
                        documents_by_type[doc_type_name].append(doc['content'])
                        print(f"✅ 添加文书内容: {doc_type_name} ({len(doc['content'])}字符)")
                    else:
                        print(f"⚠️ 跳过文书: {doc_type_name} (不在需要的类型中或无内容)")
    
    # 合并同类型文书内容
    merged_documents = {}
    for doc_type, contents in documents_by_type.items():
        if contents:
            merged_documents[doc_type] = '\n\n'.join(contents)
    
    return merged_documents if merged_documents else None

def test_frontend_request():
    """测试前端请求格式"""
    print("🧪 测试前端质控请求格式")
    
    # 1. 获取文书数据
    print("📋 获取文书数据...")
    documents_data = get_documents_data()
    if not documents_data:
        return False
    
    # 2. 构建文书映射
    document_types = ['入院记录', '病程记录', '手术记录', '出院记录']
    documents_by_type = build_documents_by_type(documents_data, document_types)
    
    print(f"📊 构建的文书映射: {list(documents_by_type.keys()) if documents_by_type else '无'}")
    
    # 3. 构建请求数据（模拟前端）
    evaluation_request = {
        "document_id": "7fcb8e4c-3892-40c4-92f3-19bf5061aa41",
        "document_content": "完整病历内容...",  # 前端会传递完整内容
        "document_type": "病程记录",  # 兼容性字段
        "document_types": document_types,
        "rule_ids": [],  # 空数组表示使用所有规则
        "use_multi_document_mode": True,
        "documents_by_type": documents_by_type,
        "patient_info": {
            "name": "张伟",
            "age": "44",
            "gender": "男",
            "record_id": "7fcb8e4c-3892-40c4-92f3-19bf5061aa41"
        }
    }
    
    print("📤 发送质控评估请求:")
    print(json.dumps(evaluation_request, ensure_ascii=False, indent=2))
    
    # 4. 发送请求
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/qc/sichuan/evaluate",
            json=evaluation_request,
            timeout=120
        )
        
        print(f"📡 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功!")
            print(f"📊 合规率: {result['evaluation_summary']['compliance_rate']:.1%}")
            return True
        elif response.status_code == 422:
            print("❌ 422 Unprocessable Content 错误")
            try:
                error_detail = response.json()
                print("错误详情:", json.dumps(error_detail, ensure_ascii=False, indent=2))
            except:
                print("错误响应:", response.text)
            return False
        else:
            print(f"❌ 其他错误: {response.status_code}")
            print("响应内容:", response.text)
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def test_simple_request():
    """测试简化的请求格式"""
    print("\n🧪 测试简化的请求格式")
    
    simple_request = {
        "document_id": "test_simple",
        "document_content": "简单测试内容",
        "document_type": "病程记录",
        "use_multi_document_mode": True,
        "documents_by_type": {
            "病程记录": "患者张伟，性别男，年龄44岁，以发现肛旁肿物疼痛2+天为主诉入院。"
        }
    }
    
    print("📤 发送简化请求:")
    print(json.dumps(simple_request, ensure_ascii=False, indent=2))
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/qc/sichuan/evaluate",
            json=simple_request,
            timeout=60
        )
        
        print(f"📡 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 简化请求成功!")
            return True
        elif response.status_code == 422:
            print("❌ 422 错误")
            try:
                error_detail = response.json()
                print("错误详情:", json.dumps(error_detail, ensure_ascii=False, indent=2))
            except:
                print("错误响应:", response.text)
            return False
        else:
            print(f"❌ 其他错误: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始测试前端请求格式")
    print("=" * 60)
    
    # 检查后端服务
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/health", timeout=5)
        if response.status_code != 200:
            print("❌ 后端服务不可用")
            return
    except Exception as e:
        print(f"❌ 无法连接后端服务: {e}")
        return
    
    print("✅ 后端服务连接正常\n")
    
    # 运行测试
    success_count = 0
    total_count = 2
    
    if test_simple_request():
        success_count += 1
    
    if test_frontend_request():
        success_count += 1
    
    print("\n" + "=" * 60)
    print(f"🎯 测试完成: {success_count}/{total_count} 成功")
    
    if success_count == total_count:
        print("🎉 所有测试通过!")
    else:
        print("⚠️ 部分测试失败，需要进一步调试")

if __name__ == "__main__":
    main()

