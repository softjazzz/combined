#!/usr/bin/env python3
"""
测试PDF文件解析API
"""

import requests
import json
from pathlib import Path

def test_pdf_api():
    """测试PDF文件解析API"""
    print("🧪 PDF文件解析API测试")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # 1. 登录获取token
    print("1️⃣ 获取访问令牌...")
    login_data = {
        "email": "admin@medqc.com",
        "password": "admin123"
    }
    
    try:
        response = requests.post(f"{base_url}/api/auth/login", json=login_data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            if access_token:
                print("✅ 登录成功")
                headers = {"Authorization": f"Bearer {access_token}"}
            else:
                print("❌ 登录响应中没有access_token")
                return False
        else:
            print(f"❌ 登录失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return False
    
    # 2. 测试PDF文件解析
    print("\n2️⃣ 测试PDF文件解析...")
    
    # 查找测试PDF文件
    pdf_file_path = Path(__file__).parent / "test_sample.pdf"
    
    if not pdf_file_path.exists():
        print("❌ 测试PDF文件不存在，先创建一个...")
        # 创建测试PDF
        try:
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            
            medical_text = """患者基本信息：
姓名：李明
性别：男
年龄：45岁
科室：心内科
病历号：2024003

入院记录：
患者李明，男，45岁，因"胸痛、气短2天"入院。

现病史：
患者2天前无明显诱因出现胸痛，呈压榨性疼痛，伴气短、出汗。

体格检查：
T：36.8℃，P：85次/分，R：22次/分，BP：150/95mmHg
心界稍大，心率85次/分，律齐。

辅助检查：
心电图：ST段压低
心肌酶：肌钙蛋白I升高

初步诊断：
1. 急性心肌梗死
2. 高血压病"""
            
            page.insert_text((50, 50), medical_text, fontsize=12)
            doc.save(str(pdf_file_path))
            doc.close()
            print("✅ 创建测试PDF文件成功")
            
        except Exception as e:
            print(f"❌ 创建测试PDF失败: {e}")
            return False
    
    try:
        # 测试PDF文件解析
        with open(pdf_file_path, 'rb') as f:
            files = {'file': ('test_medical.pdf', f, 'application/pdf')}
            data = {'options': '{}'}
            
            print(f"📤 上传PDF文件: {pdf_file_path.name} ({pdf_file_path.stat().st_size} bytes)")
            
            response = requests.post(
                f"{base_url}/api/parse-medical-file",
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ PDF文件解析API测试成功")
            print(f"  - 解析成功: {result.get('success', False)}")
            
            if result.get('data'):
                data = result['data']
                print(f"  - 解析方法: {data.get('method', 'N/A')}")
                print(f"  - 页数: {data.get('pages', 0)}")
                print(f"  - 内容长度: {len(data.get('content', ''))}")
                print(f"  - 文件信息: {data.get('file_info', {})}")
                
                # 显示医疗信息提取结果
                medical_info = data.get('medical_info', {})
                if medical_info:
                    print(f"  - 提取的医疗信息:")
                    for key, value in medical_info.items():
                        if value:
                            print(f"    * {key}: {value}")
                
                # 显示内容预览
                content = data.get('content', '')
                if content:
                    print(f"\n📝 解析内容预览:")
                    print("-" * 40)
                    print(content[:300])
                    if len(content) > 300:
                        print("...(内容已截断)")
                    print("-" * 40)
                    
            return True
        else:
            print(f"❌ PDF文件解析API测试失败: {response.status_code}")
            print(f"    响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ PDF文件解析API请求失败: {e}")
        return False

if __name__ == "__main__":
    success = test_pdf_api()
    if success:
        print("\n🎉 PDF文件解析API测试完成！")
    else:
        print("\n❌ PDF文件解析API测试失败！")
        exit(1)



