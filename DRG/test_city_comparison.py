import json
import requests

"""
测试不同城市参数对 DIP 分组的影响
DIP (Diagnosis-Intervention Packet) - 按病种分值付费
"""

BASE_URL = "https://medchat.fun"
API_PATH = "/api/dip-grouping"  # DIP 分组接口

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en,zh-CN;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Cookie": "acw_tc=ac1100117671003182365842e51844c0434005a4b044d38778238973e1e89",
    "Referer": "https://medchat.fun/medgroup",
    "Origin": "https://medchat.fun",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# 泸州市数据
PAYLOAD_LUZHOU = {
    "city_name": "泸州市",
    "pdx_code": "J18.900",
    "adx_code": "",
    "proc_code": "17.91350",
    "patient_gender": "女",
    "birth_weight": 0,
    "fee_per_point": 60,
    "high_ratio_limit": 3,
    "icu": 0,
    "los": 12,
    "low_ratio_limit": 0.5,
    "patient_age": 30,
    "rate": 1,
    "settlement_source": "none",
    "total_fee": 0
}

# 个旧市数据（对比）
PAYLOAD_GEJIU = {
    "city_name": "个旧市",
    "pdx_code": "J18.900",
    "adx_code": "",
    "proc_code": "17.91350",
    "patient_gender": "女",
    "birth_weight": 0,
    "fee_per_point": 60,
    "high_ratio_limit": 3,
    "icu": 0,
    "los": 12,
    "low_ratio_limit": 0.5,
    "patient_age": 30,
    "rate": 1,
    "settlement_source": "none",
    "total_fee": 0
}

def test_city(city_name, payload):
    """测试指定城市的 DRG 分组"""
    url = BASE_URL.rstrip("/") + API_PATH
    print(f"\n{'='*60}")
    print(f"测试城市: {city_name}")
    print(f"{'='*60}")
    
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        print(f"HTTP Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            # 提取关键信息
            drg_code = data.get('drg_code', 'N/A')
            drg_name = data.get('drg_name', 'N/A')
            score = data.get('score', 'N/A')
            status = data.get('status', 'N/A')
            
            print(f"\n✅ 分组成功:")
            print(f"  DRG 编码: {drg_code}")
            print(f"  DRG 名称: {drg_name}")
            print(f"  权重分值: {score}")
            print(f"  验证状态: {status}")
            
            return {
                'city': city_name,
                'drg_code': drg_code,
                'drg_name': drg_name,
                'score': score,
                'status': status,
                'full_response': data
            }
        else:
            print(f"❌ 请求失败: {resp.status_code}")
            print(resp.text[:500])
            return None
            
    except Exception as e:
        print(f"❌ 请求异常: {repr(e)}")
        return None

if __name__ == "__main__":
    print("DIP 分组 - 城市参数对比测试")
    print("="*60)
    
    # 测试泸州市
    result_luzhou = test_city("泸州市", PAYLOAD_LUZHOU)
    
    # 测试个旧市
    result_gejiu = test_city("个旧市", PAYLOAD_GEJIU)
    
    # 对比结果
    print(f"\n{'='*60}")
    print("对比分析")
    print(f"{'='*60}")
    
    if result_luzhou and result_gejiu:
        print(f"\n城市: 泸州市 vs 个旧市")
        print(f"DIP 编码: {result_luzhou['drg_code']} vs {result_gejiu['drg_code']}")
        print(f"权重分值: {result_luzhou['score']} vs {result_gejiu['score']}")
        
        if result_luzhou['drg_code'] == result_gejiu['drg_code']:
            print("\n✅ 结论: 相同诊断/手术在不同城市的 DIP 编码一致")
        else:
            print("\n⚠️  结论: 不同城市可能有不同的分组规则")
            
        if result_luzhou['score'] == result_gejiu['score']:
            print("✅ 结论: 权重分值相同")
        else:
            print("⚠️  结论: 不同城市的权重分值可能不同")
    
    print(f"\n{'='*60}")
