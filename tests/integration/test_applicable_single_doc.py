#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
ADMIN_EMAIL = "admin@medqc.com"
ADMIN_PASSWORD = "admin123"

DEPT_ID = "11111111-1111-1111-1111-111111111111"  # TEST_CARDIO
# 映射：“首次病程记录” 对应系统内的文书类型为 “病程记录”
DOCUMENT_TYPE = "病程记录"


def login(email: str, password: str) -> str:
    r = requests.post(
        f"{API_BASE_URL}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("access_token")


def get_applicable_rules(token: str, dept_id: str, doc_type: str):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(
        f"{API_BASE_URL}/api/v1/qc/rules/department/applicable",
        params={"department_id": dept_id, "document_type": doc_type},
        headers=headers,
        timeout=20,
    )
    return r.status_code, r.text, r.json() if r.headers.get("Content-Type", "").startswith("application/json") else None


def main():
    print("== 单文书类型‘首次病程记录’（映射为‘病程记录’）获取适用规则 测试 ==")
    token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    print("登录成功，获取 Token 长度:", len(token or ""))

    status, text, data = get_applicable_rules(token, DEPT_ID, DOCUMENT_TYPE)
    print("HTTP 状态码:", status)

    if data and data.get("success"):
        rules = data.get("data", {}).get("rules", [])
        print("规则数:", len(rules))
        for i, r in enumerate(rules, 1):
            print(f"{i}. {r.get('rule_code')} | {r.get('name')} | scope={r.get('scope')} | source={r.get('source')}")
    else:
        print("响应体(前 500 字):", text[:500])


if __name__ == "__main__":
    main()

