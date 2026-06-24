#!/usr/bin/env python3
"""
测试API集成功能
"""

import requests
import json
from pathlib import Path
import time

def test_api_integration():
    """测试API集成功能"""
    print("🧪 API集成测试")
    print("=" * 50)
    
    base_url = "http://localhost:8001"
    
    # 1. 测试健康检查
    print("1️⃣ 测试健康检查...")
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ 健康检查通过")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 无法连接到API服务: {e}")
        print("💡 请确保后端服务正在运行: python main_api.py")
        return False
    
    # 2. 测试用户注册和登录
    print("\n2️⃣ 测试用户认证...")
    
    # 注册测试用户
    register_data = {
        "email": "test@example.com",
        "password": "test123456",
        "display_name": "测试用户",
        "department": "测试科",
        "role": "doctor"
    }
    
    try:
        response = requests.post(f"{base_url}/api/auth/register", json=register_data)
        if response.status_code in [200, 201]:
            print("✅ 用户注册成功")
        elif response.status_code == 400 and "already exists" in response.text:
            print("ℹ️ 用户已存在，继续测试")
        else:
            print(f"❌ 用户注册失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ 注册请求失败: {e}")
    
    # 登录获取token
    login_data = {
        "email": "test@example.com",
        "password": "test123456"
    }
    
    try:
        response = requests.post(f"{base_url}/api/auth/login", json=login_data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            if access_token:
                print("✅ 用户登录成功")
                headers = {"Authorization": f"Bearer {access_token}"}
            else:
                print("❌ 登录响应中没有access_token")
                return False
        else:
            print(f"❌ 用户登录失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return False
    
    # 3. 测试文件解析API
    print("\n3️⃣ 测试文件解析API...")
    
    # 创建测试文本文件
    test_content = """患者基本信息：
姓名：张三
性别：男
年龄：65岁
科室：心内科
病历号：2024001

入院记录：
患者张三，男，65岁，因"胸闷、胸痛3天"于2024年8月28日入院。

现病史：
患者3天前无明显诱因出现胸闷、胸痛，呈压榨性疼痛，持续时间约10-15分钟，休息后可缓解。

体格检查：
T：36.5℃，P：78次/分，R：18次/分，BP：140/90mmHg

初步诊断：
1. 不稳定性心绞痛
2. 高血压病3级"""
    
    # 创建临时文件
    test_file_path = Path(__file__).parent / "temp_test.txt"
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    try:
        # 测试文本文件解析
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            data = {'options': '{}'}
            
            response = requests.post(
                f"{base_url}/api/parse-medical-file",
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 文件解析API测试成功")
            print(f"  - 解析成功: {result.get('success', False)}")
            if result.get('data'):
                data = result['data']
                print(f"  - 解析方法: {data.get('method', 'N/A')}")
                print(f"  - 内容长度: {len(data.get('content', ''))}")
                print(f"  - 文件信息: {data.get('file_info', {})}")
                
                # 显示内容预览
                content = data.get('content', '')
                if content:
                    print(f"  - 内容预览: {content[:100]}...")
        else:
            print(f"❌ 文件解析API测试失败: {response.status_code}")
            print(f"    响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 文件解析API请求失败: {e}")
        return False
    finally:
        # 清理临时文件
        if test_file_path.exists():
            test_file_path.unlink()
    
    print("\n🎉 所有API集成测试通过！")
    return True

if __name__ == "__main__":
    success = test_api_integration()
    if success:
        print("\n✅ API集成测试完成")
    else:
        print("\n❌ API集成测试失败")
        exit(1)

