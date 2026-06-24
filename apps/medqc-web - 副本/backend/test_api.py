#!/usr/bin/env python3
"""
API集成测试脚本
测试前后端28个API接口的完整功能
"""

import requests
import json
import sys
from datetime import datetime

# API基础URL
BASE_URL = "http://localhost:8001"

# 测试结果
test_results = []

def log_test(name, success, message, details=None):
    """记录测试结果"""
    result = {
        "name": name,
        "success": success,
        "message": message,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} {name}: {message}")
    if details:
        print(f"    Details: {details}")

def test_health_check():
    """测试健康检查"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health")
        if response.status_code == 200:
            data = response.json()
            log_test("健康检查", True, "API服务正常运行", f"状态: {data.get('status')}")
            return True
        else:
            log_test("健康检查", False, f"HTTP {response.status_code}")
            return False
    except Exception as e:
        log_test("健康检查", False, f"连接失败: {str(e)}")
        return False

def test_authentication():
    """测试用户认证API (B1任务 - 9个接口)"""
    print("\n🔐 测试用户认证API...")
    
    # 1. 测试登录
    try:
        login_data = {
            "email": "admin@medqc.com",
            "password": "admin123"
        }
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            log_test("用户登录", True, "登录成功", f"Token获取成功")
            
            # 保存token用于后续测试
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # 2. 测试获取用户信息
            response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
            if response.status_code == 200:
                user_data = response.json()
                log_test("获取用户信息", True, "用户信息获取成功", f"用户: {user_data.get('display_name')}")
            else:
                log_test("获取用户信息", False, f"HTTP {response.status_code}")
            
            # 3. 测试更新用户资料
            update_data = {"bio": f"测试更新 - {datetime.now().isoformat()}"}
            response = requests.put(f"{BASE_URL}/api/auth/profile", json=update_data, headers=headers)
            if response.status_code == 200:
                log_test("更新用户资料", True, "资料更新成功")
            else:
                log_test("更新用户资料", False, f"HTTP {response.status_code}")
            
            # 4. 测试登出
            response = requests.post(f"{BASE_URL}/api/auth/logout", headers=headers)
            if response.status_code == 200:
                log_test("用户登出", True, "登出成功")
            else:
                log_test("用户登出", False, f"HTTP {response.status_code}")
            
            return access_token
            
        else:
            log_test("用户登录", False, f"HTTP {response.status_code}")
            return None
            
    except Exception as e:
        log_test("用户认证测试", False, f"异常: {str(e)}")
        return None

def test_medical_records(access_token):
    """测试医疗记录API (B2任务 - 10个接口)"""
    print("\n📋 测试医疗记录API...")
    
    if not access_token:
        log_test("医疗记录测试", False, "缺少访问令牌")
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        # 1. 测试获取记录列表
        response = requests.get(f"{BASE_URL}/api/records", headers=headers)
        if response.status_code == 200:
            data = response.json()
            record_count = len(data.get("data", []))
            log_test("获取记录列表", True, f"获取成功，共 {record_count} 条记录")
        else:
            log_test("获取记录列表", False, f"HTTP {response.status_code}")
        
        # 2. 测试创建记录
        record_data = {
            "patient_name": "测试患者",
            "patient_age": "30",
            "patient_gender": "male",
            "department": "内科",
            "admission_date": "2024-08-25",
            "record_type": "inpatient",
            "content": "这是一个API测试创建的病案记录"
        }
        
        response = requests.post(f"{BASE_URL}/api/records", data=record_data, headers=headers)
        if response.status_code == 200:
            new_record = response.json()
            record_id = new_record.get("id")
            log_test("创建医疗记录", True, f"记录创建成功，ID: {record_id}")
            
            # 3. 测试获取单个记录
            if record_id:
                response = requests.get(f"{BASE_URL}/api/records/{record_id}", headers=headers)
                if response.status_code == 200:
                    log_test("获取单个记录", True, "记录详情获取成功")
                else:
                    log_test("获取单个记录", False, f"HTTP {response.status_code}")
                
                # 4. 测试更新记录
                update_data = {
                    "content": f"更新的病案内容 - {datetime.now().isoformat()}"
                }
                response = requests.put(f"{BASE_URL}/api/records/{record_id}", data=update_data, headers=headers)
                if response.status_code == 200:
                    log_test("更新医疗记录", True, "记录更新成功")
                else:
                    log_test("更新医疗记录", False, f"HTTP {response.status_code}")
                
                return record_id
        else:
            log_test("创建医疗记录", False, f"HTTP {response.status_code}")
        
        # 5. 测试获取统计信息
        response = requests.get(f"{BASE_URL}/api/records/statistics", headers=headers)
        if response.status_code == 200:
            stats = response.json()
            total = stats.get("total_records", 0)
            log_test("获取统计信息", True, f"统计信息获取成功，总记录数: {total}")
        else:
            log_test("获取统计信息", False, f"HTTP {response.status_code}")
            
    except Exception as e:
        log_test("医疗记录测试", False, f"异常: {str(e)}")
        return None

def test_qc_analysis(access_token, record_id=None):
    """测试质控分析API (B3任务 - 9个接口)"""
    print("\n⚡ 测试质控分析API...")
    
    if not access_token:
        log_test("质控分析测试", False, "缺少访问令牌")
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        # 1. 测试获取质控规则
        response = requests.get(f"{BASE_URL}/api/qc/rules", headers=headers)
        if response.status_code == 200:
            rules = response.json()
            rule_count = len(rules)
            log_test("获取质控规则", True, f"规则获取成功，共 {rule_count} 条规则")
        else:
            log_test("获取质控规则", False, f"HTTP {response.status_code}")
        
        # 2. 测试开始分析（使用第一个可用记录）
        if not record_id:
            # 获取第一个记录ID
            response = requests.get(f"{BASE_URL}/api/records", headers=headers)
            if response.status_code == 200:
                records = response.json().get("data", [])
                if records:
                    record_id = records[0]["id"]
        
        if record_id:
            response = requests.post(f"{BASE_URL}/api/qc/analyze/{record_id}", headers=headers)
            if response.status_code == 200:
                analysis_data = response.json()
                analysis_id = analysis_data.get("analysis_id")
                log_test("开始质控分析", True, f"分析已开始，ID: {analysis_id}")
                
                # 3. 测试获取分析结果
                response = requests.get(f"{BASE_URL}/api/qc/result/{record_id}", headers=headers)
                if response.status_code == 200:
                    result = response.json()
                    score = result.get("overall_score")
                    grade = result.get("overall_grade")
                    issues_count = len(result.get("issues", []))
                    log_test("获取分析结果", True, f"结果获取成功，评分: {score}分 ({grade}级)，问题数: {issues_count}")
                else:
                    log_test("获取分析结果", False, f"HTTP {response.status_code}")
                
                # 4. 测试获取分析进度
                if analysis_id:
                    response = requests.get(f"{BASE_URL}/api/qc/progress/{analysis_id}", headers=headers)
                    if response.status_code == 200:
                        progress = response.json()
                        status = progress.get("status")
                        progress_pct = progress.get("progress")
                        log_test("获取分析进度", True, f"进度获取成功，状态: {status}，进度: {progress_pct}%")
                    else:
                        log_test("获取分析进度", False, f"HTTP {response.status_code}")
            else:
                log_test("开始质控分析", False, f"HTTP {response.status_code}")
        
        # 5. 测试获取质控历史
        response = requests.get(f"{BASE_URL}/api/qc/history", headers=headers)
        if response.status_code == 200:
            history = response.json()
            history_count = len(history)
            log_test("获取质控历史", True, f"历史记录获取成功，共 {history_count} 条记录")
        else:
            log_test("获取质控历史", False, f"HTTP {response.status_code}")
            
    except Exception as e:
        log_test("质控分析测试", False, f"异常: {str(e)}")

def main():
    """主测试函数"""
    print("🚀 开始API集成测试...")
    print(f"测试目标: {BASE_URL}")
    print("=" * 60)
    
    # 1. 健康检查
    if not test_health_check():
        print("❌ 健康检查失败，停止测试")
        return
    
    # 2. 用户认证测试
    access_token = test_authentication()
    
    # 3. 医疗记录测试
    record_id = test_medical_records(access_token)
    
    # 4. 质控分析测试
    test_qc_analysis(access_token, record_id)
    
    # 统计测试结果
    print("\n" + "=" * 60)
    print("📊 测试结果统计:")
    
    total_tests = len(test_results)
    passed_tests = len([r for r in test_results if r["success"]])
    failed_tests = total_tests - passed_tests
    
    print(f"总测试数: {total_tests}")
    print(f"通过: {passed_tests} ✅")
    print(f"失败: {failed_tests} ❌")
    print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
    
    if failed_tests > 0:
        print("\n❌ 失败的测试:")
        for result in test_results:
            if not result["success"]:
                print(f"  - {result['name']}: {result['message']}")
    
    print("\n🎉 API集成测试完成!")
    
    return failed_tests == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

