import requests
import json

BASE_URL = "https://medchat.fun/api/find-info-by-code"

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://medchat.fun/medgroup",
    "Origin": "https://medchat.fun"
}

def test_search(keyword):
    print(f"Testing search for: {keyword}")
    
    # Attempt 1: POST with json (Most likely for this site based on previous API)
    payloads = [
        {"code": keyword},
        {"keyword": keyword},
        {"search": keyword},
        {"key": keyword}
    ]
    
    for p in payloads:
        try:
            print(f"Trying POST with payload: {p}")
            resp = requests.post(BASE_URL, headers=HEADERS, json=p, timeout=10)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                try:
                    print("Response:", json.dumps(resp.json(), indent=2, ensure_ascii=False))
                    return
                except:
                    print("Response text:", resp.text[:200])
        except Exception as e:
            print(f"Error: {e}")

    # Attempt 2: GET
    try:
        print(f"Trying GET with query params")
        resp = requests.get(BASE_URL, headers=HEADERS, params={"code": keyword}, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
             print("Response:", resp.text[:500])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search("糖尿病")
    print("-" * 30)
    test_search("E11") # Try a code just in case
