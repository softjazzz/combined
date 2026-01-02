import json
import requests

"""
DRG 分组 API 测试脚本
DRG (Diagnosis Related Groups) - 按疾病诊断相关分组
"""

BASE_URL = "https://medchat.fun"
API_PATH = "/api/drg-grouping"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en,zh-CN;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Cookie": "acw_tc=ac11000117671024951721484edd9575d3a8bd27e3e385850319c1fd267de8",
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

def call_drg_api(payload):
    """调用 DRG 分组 API"""
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

def extract_drg_info(response_data):
    """从响应中提取 DRG 信息"""
    if not response_data or not response_data.get('success'):
        return None
    
    result = response_data.get('result', [{}])[0]
    grouping_path = response_data.get('grouping_path', {})
    grouping_actual = grouping_path.get('grouping_actual', {})
    
    return {
        'mdc_code': result.get('MDCCode', 'N/A'),
        'adrg_code': result.get('ADRGCode', 'N/A'),
        'drg_code': result.get('DRGCode', 'N/A'),
        'cc_status': result.get('CCStatus', 'N/A'),
        'rule_source': response_data.get('rule_source', 'N/A'),
        'pdx': result.get('PDX', 'N/A'),
        'adxs': result.get('ADXs', 'N/A'),
        'procs': result.get('PROCs', 'N/A'),
        'validation': grouping_path.get('final_outcome', 'N/A'),
        'mdc_check': grouping_path.get('mdc_check', {}).get('message', 'N/A'),
        'adrg_check': grouping_path.get('adrg_check', {}).get('message', 'N/A'),
        'drg_check': grouping_path.get('drg_check', {}).get('message', 'N/A')
    }

def test_single_case(city, pdx_code, adx_code="", proc_code="", gender="女", age=30, los=12):
    """测试单个病例"""
    payload = {
        "city_name": city,
        "pdx_code": pdx_code,
        "adx_code": adx_code,
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
    
    print(f"\n{'='*70}")
    print(f"测试病例: {city} | PDX:{pdx_code} | PROC:{proc_code or '无'}")
    print(f"{'='*70}")
    
    response = call_drg_api(payload)
    
    if response:
        info = extract_drg_info(response)
        if info:
            print(f"✅ DRG 分组成功:")
            print(f"   MDC (主要诊断类别): {info['mdc_code']}")
            print(f"   ADRG (邻近诊断组): {info['adrg_code']}")
            print(f"   DRG (诊断相关组): {info['drg_code']}")
            print(f"   CC/MCC 状态: {info['cc_status']}")
            print(f"   规则来源: {info['rule_source']}")
            print(f"\n   验证结果:")
            print(f"   - MDC: {info['mdc_check']}")
            print(f"   - ADRG: {info['adrg_check']}")
            print(f"   - DRG: {info['drg_check']}")
            return info
    
    return None

# 示例用法
if __name__ == "__main__":
    print("DRG 分组 API 测试")
    print("="*70)
    
    # 测试 1: 四川省，肺炎，无并发症
    result1 = test_single_case(
        city="四川省",
        pdx_code="J18.900",
        adx_code="",
        proc_code="17.91350",
        gender="女",
        age=30,
        los=12
    )
    
    # 测试 2: 四川省，肺炎伴糖尿病（有并发症）
    result2 = test_single_case(
        city="四川省",
        pdx_code="J18.900",
        adx_code="E10.000x002",  # 1型糖尿病
        proc_code="",
        gender="女",
        age=30,
        los=12
    )
    
    # 测试 3: 泸州市 vs 四川省（对比地区规则）
    result3 = test_single_case(
        city="泸州市",
        pdx_code="J18.900",
        adx_code="",
        proc_code="",
        gender="女",
        age=30,
        los=12
    )
    
    print(f"\n{'='*70}")
    print("测试总结")
    print(f"{'='*70}")
    
    if result1:
        print(f"\n基础病例 (无并发症):")
        print(f"  DRG: {result1['drg_code']} | CC状态: {result1['cc_status']}")
    
    if result2:
        print(f"\n伴并发症病例:")
        print(f"  DRG: {result2['drg_code']} | CC状态: {result2['cc_status']}")
    
    if result1 and result2:
        if result1['drg_code'] != result2['drg_code']:
            print(f"\n✅ 并发症影响分组: {result1['drg_code']} → {result2['drg_code']}")
        else:
            print(f"\n⚠️  并发症未影响 DRG 分组")
    
    if result1 and result3:
        if result1['rule_source'] != result3['rule_source']:
            print(f"\n⚠️  不同地区使用不同规则:")
            print(f"  四川省: {result1['rule_source']}")
            print(f"  泸州市: {result3['rule_source']}")
        else:
            print(f"\n✅ 使用相同规则来源: {result1['rule_source']}")
