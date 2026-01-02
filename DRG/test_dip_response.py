import json
import requests

"""
测试 DIP 分组接口，查看完整返回结构
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

# 泸州市数据
PAYLOAD = {
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

def main():
    url = BASE_URL.rstrip("/") + API_PATH
    print(f"POST {url}")
    print(f"\nPayload:")
    print(json.dumps(PAYLOAD, ensure_ascii=False, indent=2))
    
    try:
        resp = requests.post(url, headers=HEADERS, json=PAYLOAD, timeout=30)
    except Exception as e:
        print(f"❌ 请求异常: {repr(e)}")
        return
    
    print(f"\nHTTP Status: {resp.status_code}")
    
    # 查看完整返回
    try:
        data = resp.json()
        print("\n✅ 完整返回 JSON：")
        print("="*80)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print("="*80)
        
        # 分析结构
        print("\n📊 返回数据结构分析：")
        print(f"顶层键: {list(data.keys())}")
        
    except Exception:
        print("⚠️ 非 JSON 返回：")
        print(resp.text)

if __name__ == "__main__":
    main()
