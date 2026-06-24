"""
增强版API测试脚本
测试层级化医疗文书分类功能
"""

import requests
import json
from datetime import datetime
import time

# API配置
BASE_URL = "http://localhost:8001"
API_PREFIX = "/api/enhanced-classification"

def test_health_check():
    """测试健康检查"""
    print("🔍 测试健康检查...")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 健康检查通过: {data['status']}")
            print(f"   版本: {data['version']}")
            print(f"   功能: {', '.join(data['features'])}")
            return True
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 健康检查异常: {str(e)}")
        return False

def test_get_categories():
    """测试获取分类列表"""
    print("\n🔍 测试获取分类列表...")
    
    try:
        response = requests.get(f"{BASE_URL}{API_PREFIX}/categories")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 获取分类成功: {data['total']} 个一级分类")
            
            for category in data['categories']:
                print(f"   - {category['category_name']} ({len(category.get('types', []))} 个子类型)")
            
            return True, data
        else:
            print(f"❌ 获取分类失败: {response.status_code}")
            return False, None
    except Exception as e:
        print(f"❌ 获取分类异常: {str(e)}")
        return False, None

def test_classification():
    """测试文书分类功能"""
    print("\n🔍 测试文书分类功能...")
    
    # 使用我们测试成功的记录ID
    test_record_id = "b410f284-5b3d-42eb-893a-360f4fbb0b6f"
    
    # 测试文本（包含多种文书类型）
    test_text = """
入院记录
患者李四，女，58岁，因"腹痛2天"入院。
主诉：腹痛2天。
现病史：患者2天前进食后出现上腹部疼痛，呈持续性胀痛，伴恶心、呕吐。
既往史：胆囊炎病史3年。
体格检查：T 37.2℃，P 88次/分，R 20次/分，BP 130/80mmHg。
入院诊断：急性胆囊炎

首次病程记录
患者入院后完善相关检查，病情稳定。
病情分析：根据患者症状、体征及既往史，考虑急性胆囊炎诊断明确。
诊疗计划：1.禁食水 2.抗感染治疗 3.解痉止痛

护理记录
护理记录：患者意识清楚，精神一般，诉腹痛。
护理措施：1.密切观察病情变化 2.按时给药 3.心理护理

体温单
T:37.2℃ P:88次/分 R:20次/分 BP:130/80mmHg

长期医嘱
1.禁食水
2.头孢曲松 2g 静脉滴注 每日一次
3.山莨菪碱 10mg 肌肉注射 每8小时一次

出院记录
患者经治疗后腹痛症状明显缓解，体温正常，今日出院。
出院诊断：急性胆囊炎
出院医嘱：1.清淡饮食 2.定期复查
"""
    
    classification_request = {
        "recordId": test_record_id,
        "rawText": test_text,
        "enableHierarchicalClassification": True,
        "confidenceThreshold": 0.5
    }
    
    try:
        print(f"   使用记录ID: {test_record_id}")
        print(f"   文本长度: {len(test_text)} 字符")
        
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/classify",
            json=classification_request,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 分类成功: {data['statistics']['totalDocuments']} 个文书")
            print(f"   平均置信度: {data['statistics']['averageConfidence']:.3f}")
            print(f"   处理时间: {data['processingTime']:.2f}秒")
            
            if data.get('warnings'):
                print(f"   ⚠️ 警告: {len(data['warnings'])} 个")
                for warning in data['warnings']:
                    print(f"      - {warning}")
            
            print("   分类结果:")
            for doc in data['documents']:
                print(f"      - {doc['title']}: 置信度 {doc.get('classification_confidence', 0):.2f}")
            
            return True, data
        else:
            print(f"❌ 分类失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ 分类异常: {str(e)}")
        return False, None

def test_get_documents():
    """测试获取文书列表"""
    print("\n🔍 测试获取文书列表...")
    
    test_record_id = "b410f284-5b3d-42eb-893a-360f4fbb0b6f"
    
    try:
        response = requests.get(f"{BASE_URL}{API_PREFIX}/documents/{test_record_id}?include_qc=true")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 获取文书成功: {data['statistics']['totalDocuments']} 个文书")
            print(f"   平均置信度: {data['statistics']['averageConfidence']:.3f}")
            
            category_dist = data['statistics']['categoryDistribution']
            print("   分类分布:")
            for category, count in category_dist.items():
                print(f"      - {category}: {count} 个")
            
            if data['statistics'].get('qcStats'):
                qc_stats = data['statistics']['qcStats']
                print(f"   质控统计: {qc_stats['passedQC']}/{qc_stats['totalQC']} 通过")
            
            return True, data
        else:
            print(f"❌ 获取文书失败: {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"❌ 获取文书异常: {str(e)}")
        return False, None

def test_get_statistics():
    """测试获取统计信息"""
    print("\n🔍 测试获取统计信息...")
    
    try:
        response = requests.get(f"{BASE_URL}{API_PREFIX}/statistics")
        
        if response.status_code == 200:
            data = response.json()
            overview = data['overview']
            
            print(f"✅ 获取统计成功:")
            print(f"   总文书数: {overview['totalDocuments']}")
            print(f"   平均置信度: {overview['averageConfidence']:.3f}")
            
            qc_stats = overview['qcStats']
            print(f"   质控统计:")
            print(f"      - 总计: {qc_stats['totalQC']}")
            print(f"      - 通过: {qc_stats['passedQC']}")
            print(f"      - 失败: {qc_stats['failedQC']}")
            print(f"      - 警告: {qc_stats['warningQC']}")
            
            print("   分类统计:")
            for stat in data['categoryStats']:
                if stat['document_count'] > 0:
                    print(f"      - {stat['category_name']}/{stat['type_name']}: {stat['document_count']} 个")
            
            return True, data
        else:
            print(f"❌ 获取统计失败: {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"❌ 获取统计异常: {str(e)}")
        return False, None

def test_system_info():
    """测试系统信息"""
    print("\n🔍 测试系统信息...")
    
    try:
        response = requests.get(f"{BASE_URL}/system/info")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 系统信息获取成功:")
            print(f"   系统: {data['system']}")
            print(f"   版本: {data['version']}")
            
            capabilities = data['capabilities']
            print("   功能特性:")
            print(f"      - 分类: {capabilities['classification']['categories']} 个一级分类, {capabilities['classification']['types']} 个二级分类")
            print(f"      - 护理文书识别: {capabilities['recognition']['nursing_documents']}")
            print(f"      - 医嘱记录识别: {capabilities['recognition']['medical_orders']}")
            print(f"      - 质控模板: {capabilities['quality_control']['templates']} 个")
            
            return True, data
        else:
            print(f"❌ 获取系统信息失败: {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"❌ 获取系统信息异常: {str(e)}")
        return False, None

def run_all_tests():
    """运行所有测试"""
    print("🚀 开始增强版API功能测试...")
    print("=" * 50)
    
    start_time = time.time()
    
    # 测试结果统计
    results = {
        "health_check": False,
        "get_categories": False,
        "classification": False,
        "get_documents": False,
        "get_statistics": False,
        "system_info": False
    }
    
    # 执行测试
    results["health_check"] = test_health_check()
    results["system_info"] = test_system_info()[0] if test_system_info() else False
    results["get_categories"] = test_get_categories()[0] if test_get_categories() else False
    results["classification"] = test_classification()[0] if test_classification() else False
    results["get_documents"] = test_get_documents()[0] if test_get_documents() else False
    results["get_statistics"] = test_get_statistics()[0] if test_get_statistics() else False
    
    # 统计结果
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    end_time = time.time()
    
    print("\n" + "=" * 50)
    print("📊 测试结果总结:")
    print(f"   总测试数: {total_tests}")
    print(f"   通过数: {passed_tests}")
    print(f"   失败数: {total_tests - passed_tests}")
    print(f"   成功率: {passed_tests/total_tests*100:.1f}%")
    print(f"   总耗时: {end_time - start_time:.2f}秒")
    
    print("\n详细结果:")
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    if passed_tests == total_tests:
        print("\n🎉 所有测试通过！增强版API功能正常！")
    else:
        print(f"\n⚠️ {total_tests - passed_tests} 个测试失败，请检查相关功能")
    
    return results

if __name__ == "__main__":
    print("增强版医疗文书分类API测试")
    print("请确保API服务已启动 (python backend/main_enhanced.py)")
    print()
    
    # 等待用户确认
    input("按回车键开始测试...")
    
    # 运行测试
    test_results = run_all_tests()
    
    # 保存测试结果
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": test_results,
            "summary": {
                "total": len(test_results),
                "passed": sum(1 for r in test_results.values() if r),
                "failed": sum(1 for r in test_results.values() if not r)
            }
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 测试结果已保存到 test_results.json")

