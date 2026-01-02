import json
import requests

"""
测试 DIP 分组接口，将结果保存到文件
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
    
    try:
        resp = requests.post(url, headers=HEADERS, json=PAYLOAD, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            
            # 保存到文件
            with open("dip_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print("✅ 成功！结果已保存到 dip_response.json")
            print(f"\n顶层键: {list(data.keys())}")
            
            # 提取关键信息
            if 'dip_code' in data:
                print(f"DIP 编码: {data['dip_code']}")
            if 'dip_name' in data:
                print(f"DIP 名称: {data['dip_name']}")
            if 'score' in data:
                print(f"分值: {data['score']}")
                
        else:
            print(f"❌ HTTP {resp.status_code}")
            
    except Exception as e:
        print(f"❌ 异常: {repr(e)}")

if __name__ == "__main__":
    main()
