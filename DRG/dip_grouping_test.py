import json
import requests

"""
DIP 分组 API 测试脚本（最终版）
支持单个病例测试和批量处理
"""

BASE_URL = "https://medchat.fun"
API_PATH = "/api/dip-grouping"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en,zh-CN;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Cookie": "acw_tc=ac11000117671003182365842e51844c0434005a4b044d38778238973e1e89",
    "Referer": "https://medchat.fun/medgroup",
    "Origin": "https://medchat.fun",
    "Priority": "u=1, i",
    "Sec-Ch-Ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

def call_dip_api(payload):
    """调用 DIP 分组 API"""
    url = BASE_URL.rstrip("/") + API_PATH
    
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ 请求异常: {repr(e)}")
        return None

def extract_dip_info(response_data):
    """从响应中提取 DIP 信息"""
    if not response_data or not response_data.get('success'):
        return None
    
    result = response_data.get('result', [{}])[0]
    dip_code = result.get('dipcode', 'N/A')
    
    # 从参考病种中查找名称
    dip_name = 'N/A'
    dip_type = 'N/A'
    
    for ref in response_data.get('reference_grouping', {}).get('pdx_related', []):
        if ref['dip_code'] == dip_code:
            dip_name = ref['dip_name']
            dip_type = ref['dip_type']
            break
    
    return {
        'dip_code': dip_code,
        'dip_name': dip_name,
        'dip_type': dip_type,
        'rule_source': response_data.get('rule_source', 'N/A'),
        'pdx': result.get('PDX', 'N/A'),
        'proc': result.get('PROC1', 'N/A'),
        'validation': response_data.get('grouping_path', {}).get('final_outcome', 'N/A')
    }

def test_single_case(city, pdx_code, proc_code="", gender="女", age=30, los=12):
    """测试单个病例"""
    payload = {
        "city_name": city,
        "pdx_code": pdx_code,
        "adx_code": "",
        "proc_code": proc_code,
        "patient_gender": gender,
        "birth_weight": 0,
        "fee_per_point": 60,
        "high_ratio_limit": 3,
        "icu": 0,
        "los": los,
        "low_ratio_limit": 0.5,
        "patient_age": age,
        "rate": 1,
        "settlement_source": "none",
        "total_fee": 0
    }
    
    print(f"\n{'='*60}")
    print(f"测试病例: {city} | {pdx_code} | {proc_code or '保守治疗'}")
    print(f"{'='*60}")
    
    response = call_dip_api(payload)
    
    if response:
        info = extract_dip_info(response)
        if info:
            print(f"✅ DIP 编码: {info['dip_code']}")
            print(f"   DIP 名称: {info['dip_name']}")
            print(f"   DIP 类型: {info['dip_type']}")
            print(f"   规则来源: {info['rule_source']}")
            print(f"   验证结果: {info['validation']}")
            return info
    
    return None

def show_related_dip(response_data):
    """显示相关病种"""
    if not response_data:
        return
    
    current_dip = response_data['result'][0]['dipcode']
    related = response_data.get('reference_grouping', {}).get('pdx_related', [])
    
    print(f"\n相关病种 (共 {len(related)} 个):")
    print("-" * 80)
    
    for dip in related[:10]:  # 只显示前10个
        marker = "✓" if dip['dip_code'] == current_dip else " "
        print(f"  [{marker}] {dip['dip_code']:<20} {dip['dip_name']}")
    
    if len(related) > 10:
        print(f"  ... 还有 {len(related) - 10} 个相关病种")

# 示例用法
if __name__ == "__main__":
    print("DIP 分组 API 测试")
    print("="*60)
    
    # 测试 1: 泸州市，肺炎，保守治疗
    result1 = test_single_case(
        city="泸州市",
        pdx_code="J18.900",
        proc_code="",
        gender="女",
        age=30,
        los=12
    )
    
    # 测试 2: 泸州市，肺炎，电子支气管镜检查
    result2 = test_single_case(
        city="泸州市",
        pdx_code="J18.900",
        proc_code="33.2302",
        gender="女",
        age=30,
        los=12
    )
    
    # 测试 3: 个旧市，肺炎，保守治疗（对比城市差异）
    result3 = test_single_case(
        city="个旧市",
        pdx_code="J18.900",
        proc_code="",
        gender="女",
        age=30,
        los=12
    )
    
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    
    if result1 and result3:
        if result1['dip_code'] == result3['dip_code']:
            print("✅ 不同城市使用相同的 DIP 分组规则")
        else:
            print("⚠️  不同城市的 DIP 分组规则存在差异")
            print(f"   泸州市: {result1['dip_code']}")
            print(f"   个旧市: {result3['dip_code']}")
    
    if result1 and result2:
        print(f"\n同一诊断，不同治疗方式:")
        print(f"   保守治疗: {result1['dip_code']}")
        print(f"   支气管镜: {result2['dip_code']}")
