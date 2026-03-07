import asyncio
import httpx
from pprint import pprint
import sys
import os

# 将当前目录加到 sys.path，以便导入 testCases
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def main():
    with open("src/views/demo/frontpage/data/testCases.ts", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 简单提取 CASE_1_TEXT 的内容 (粗略提取)
    import re
    match = re.search(r'const CASE_1_TEXT = `(.*?)`', content, re.DOTALL)
    if not match:
        print("未找到 CASE_1_TEXT")
        return
        
    medical_text = match.group(1)
    print(f"提取病历长度: {len(medical_text)}")
    
    print("\n提交抽取请求...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "http://localhost:8000/api/v1/frontpage/auto-generate-draft",
            json={"medical_text": medical_text}
        )
        
        if response.status_code == 200:
            data = response.json()
            frontpage = data.get("frontpage", {})
            
            print("\n==== 抽取结果验证 ====\n")
            
            print(f"【手术时间】开始: {frontpage.get('procedures', {}).get('main_procedure_start_time')} | 结束: {frontpage.get('procedures', {}).get('main_procedure_end_time')}")
            print(f"【手术分级】切口: {frontpage.get('procedures', {}).get('incision_grade')} | 麻醉: {frontpage.get('procedures', {}).get('anesthesia_grade')}")
            
            print(f"\n【质控签名】医师: {frontpage.get('staff', {}).get('qc_physician')} | 护士: {frontpage.get('staff', {}).get('qc_nurse')}")
            print(f"【质控日期质量】{frontpage.get('staff', {}).get('qc_date')} | 质量: {frontpage.get('staff', {}).get('medical_record_quality')}")
            
            print(f"\n【离院去向】离院方式: {frontpage.get('hospitalization', {}).get('leaving_hospital_way')}")
            print(f"【出院转归】主诊断转归: {frontpage.get('diagnoses', {}).get('discharge_main_outcome')}")
            
            print("\n【28类费用明细】")
            costs_cat = frontpage.get("costs", {}).get("categories", {})
            for k, v in costs_cat.items():
                print(f"  - {k}: {v}")
                
        else:
            print(f"Request failed [{response.status_code}]: {response.text[:1000]}")

if __name__ == "__main__":
    asyncio.run(main())
