#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试脚本 - 验证多文书质控系统基本功能
"""

import sys
import os

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

def test_document_separator():
    """测试文书分离功能"""
    print("🔍 测试文书分离功能...")
    
    try:
        from services.document_separator import DocumentSeparator
        
        # 简单的测试内容
        test_content = """
        入院记录
        患者姓名：张三
        主诉：胸痛3天
        现病史：患者3天前出现胸痛...
        
        病程记录
        2024-01-15 首次病程记录
        患者入院后完善检查...
        
        手术记录
        手术名称：PCI
        手术过程：患者取仰卧位...
        
        出院记录
        出院诊断：急性心肌梗死
        出院医嘱：阿司匹林100mg...
        """
        
        separator = DocumentSeparator()
        sections = separator.separate_document(test_content)
        
        print(f"✅ 成功分离 {len(sections)} 种文书类型:")
        for doc_type, section in sections.items():
            print(f"  📋 {doc_type}: {len(section.content)}字符 (置信度: {section.confidence:.2f})")
        
        return True
        
    except Exception as e:
        print(f"❌ 文书分离测试失败: {e}")
        return False

def test_multi_document_engine():
    """测试多文书质控引擎"""
    print("🔄 测试多文书质控引擎...")
    
    try:
        from services.multi_document_qc_engine import MultiDocumentQCEngine
        
        # 创建模拟的LLM客户端
        class MockLLMClient:
            async def generate_response(self, prompt):
                return {
                    "status": "success",
                    "content": '''[
                        {
                            "rule_id": "SC-001",
                            "is_compliant": true,
                            "findings": "测试发现",
                            "evidence": "测试证据",
                            "confidence": 0.9
                        }
                    ]''',
                    "token_usage": {"total_tokens": 100}
                }
        
        engine = MultiDocumentQCEngine(MockLLMClient())
        print("✅ 多文书质控引擎初始化成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 多文书质控引擎测试失败: {e}")
        return False

def test_sichuan_qc_service():
    """测试四川省质控服务"""
    print("🏥 测试四川省质控服务...")
    
    try:
        from services.sichuan_qc_service import SichuanQCService
        
        service = SichuanQCService()
        print("✅ 四川省质控服务初始化成功")
        
        # 测试获取规则
        rules = service.get_applicable_rules("病程记录")
        print(f"✅ 获取到 {len(rules)} 条适用规则")
        
        return True
        
    except Exception as e:
        print(f"❌ 四川省质控服务测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始快速测试")
    print("=" * 50)
    
    tests = [
        test_document_separator,
        test_multi_document_engine,
        test_sichuan_qc_service
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            print()
    
    print("=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统重构成功！")
        print("\n📋 下一步操作:")
        print("1. 启动后端服务: python backend/main_api.py")
        print("2. 启动前端服务: npm run dev")
        print("3. 在浏览器中测试多文书质控功能")
    else:
        print("⚠️ 部分测试失败，请检查相关组件")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
