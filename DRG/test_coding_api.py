#!/usr/bin/env python3
"""
测试第三方 ICD 编码 API
API 地址: http://122.51.111.253:8002
"""

import requests
import json
import time

# API 配置
HOST = "122.51.111.253"
PORT = 8002
BASE_URL = f"http://{HOST}:{PORT}"

# 测试病历文本（使用之前的 Demo 数据）
SAMPLE_MEDICAL_TEXT = """
【入院记录】
患者姓名：张伟，男，44岁，汉族，已婚，工人。身份证号：510101198101011234。
现住址：四川省泸州市江阳区某某街道 88 号。联系电话：13800001111。
联系人：李芳（妻子），电话：13800002222。

【主诉】
反复咳嗽、咳痰 3 周，加重伴气促 3 天。

【现病史】
患者于 3 周前无明显诱因出现咳嗽、咳痰，痰为白色黏液痰，量中等，伴低热（体温最高 37.8℃），
无畏寒、寒战，无胸痛、咯血。自行口服"阿莫西林"等药物治疗，症状无明显好转。
3 天前上述症状加重，出现气促，活动后明显，伴乏力、纳差，遂来我院就诊。

门诊以"肺炎？"收入院。

【既往史】
既往体健，否认高血压、糖尿病、冠心病等慢性病史。
否认肝炎、结核等传染病史。
否认手术、外伤史。
否认药物、食物过敏史。

【体格检查】
T 38.2℃，P 98次/分，R 22次/分，BP 125/78 mmHg。
神志清楚，精神可，急性病容。
双肺呼吸音粗，右下肺可闻及湿啰音。
心律齐，各瓣膜听诊区未闻及病理性杂音。
腹软，无压痛、反跳痛。

【辅助检查】
血常规：WBC 12.5×10^9/L，N% 78%，CRP 85 mg/L。
胸部CT：右下肺炎症，考虑细菌性肺炎。

【初步诊断】
1. 肺炎（右下肺）
2. 呼吸衰竭？
"""

def submit_coding_job(text_content):
    """提交编码任务"""
    url = f"{BASE_URL}/api/v1/coding/extract"
    
    payload = {
        "request_id": "test_req_001",
        "document_type": "admission_note",
        "text_content": text_content,
        "patient_context": {
            "gender": "M",
            "age": 44
        },
        "coding_mode": "default"
    }
    
    print("=" * 60)
    print("📤 提交编码任务...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:500]}...")
    print("=" * 60)
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        print(f"\n✅ HTTP Status: {resp.status_code}")
        print(f"Response Headers: {dict(resp.headers)}")
        
        if resp.status_code == 202:
            data = resp.json()
            print(f"\n📋 Response Body:")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            # 修复：从 data.data.job_id 提取
            job_id = data.get("data", {}).get("job_id")
            return job_id
        else:
            print(f"\n❌ 意外的状态码: {resp.status_code}")
            print(f"Response: {resp.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求失败: {e}")
        return None

def get_job_result(job_id, max_retries=10, interval=2):
    """轮询获取任务结果"""
    url = f"{BASE_URL}/api/v1/coding/jobs/{job_id}"
    
    print("\n" + "=" * 60)
    print(f"🔄 开始轮询任务结果...")
    print(f"Job ID: {job_id}")
    print(f"URL: {url}")
    print("=" * 60)
    
    for i in range(max_retries):
        try:
            print(f"\n[{i+1}/{max_retries}] 查询中...")
            resp = requests.get(url, timeout=10)
            
            print(f"HTTP Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                
                print(f"任务状态: {status}")
                
                if status == "processing":
                    print(f"⏳ 任务处理中，{interval}秒后重试...")
                    time.sleep(interval)
                    continue
                elif status == "completed":
                    print("\n✅ 任务完成！")
                    print("\n" + "=" * 60)
                    print("📊 编码结果:")
                    print("=" * 60)
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                    return data
                elif status == "failed":
                    print(f"\n❌ 任务失败")
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                    return data
                    
            elif resp.status_code == 422:
                print("\n⚠️  需要人工确认 (422)")
                data = resp.json()
                print(json.dumps(data, ensure_ascii=False, indent=2))
                return data
                
            elif resp.status_code == 500:
                print("\n❌ 服务异常 (500)")
                print(resp.text)
                return None
            else:
                print(f"\n❌ 意外状态码: {resp.status_code}")
                print(resp.text)
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"\n❌ 请求失败: {e}")
            if i < max_retries - 1:
                print(f"⏳ {interval}秒后重试...")
                time.sleep(interval)
            else:
                return None
    
    print(f"\n⏰ 超时：已重试 {max_retries} 次")
    return None

def main():
    print("\n" + "🏥" * 30)
    print("ICD 编码 API 测试工具")
    print("🏥" * 30)
    
    # 步骤1: 提交任务
    job_id = submit_coding_job(SAMPLE_MEDICAL_TEXT)
    
    if not job_id:
        print("\n❌ 提交任务失败，测试终止")
        return
    
    # 步骤2: 轮询结果
    result = get_job_result(job_id)
    
    if result:
        print("\n" + "=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
        
        # 提取关键信息
        if result.get("status") == "completed":
            coding_data = result.get("data", {}).get("coding_data", {})
            diagnoses = coding_data.get("diagnoses", [])
            procedures = coding_data.get("procedures", [])
            
            print("\n📋 诊断编码:")
            for diag in diagnoses:
                print(f"  - {diag.get('name')} ({diag.get('code')})")
                print(f"    置信度: {diag.get('confidence', 0):.2f}")
                
            print("\n🔧 手术编码:")
            for proc in procedures:
                print(f"  - {proc.get('name')} ({proc.get('code')})")
                print(f"    置信度: {proc.get('confidence', 0):.2f}")
    else:
        print("\n❌ 测试失败")

if __name__ == "__main__":
    main()
