import requests
import json

BASE_URL = "https://medchat.fun/api/find-info-by-code"

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://medchat.fun",
    "Origin": "https://medchat.fun"
}

def test(code, city="四川省"):
    print(f"Testing code: {code}")
    payload = {
        "code": code,
        "city_name": city
    }
    
    try:
        resp = requests.post(BASE_URL, headers=HEADERS, json=payload, timeout=10)
        if resp.status_code == 200:
            print("Response:", json.dumps(resp.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Status: {resp.status_code}")
            print(resp.text[:200])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test("I21.001") # Known valid code
    test("糖尿病")   # User query
