#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证“流式首页抽取 -> DRG 预分组”可行性。

用法示例：
  python backend/scripts/verify_drg_pre_grouping_via_stream.py --base-url http://localhost:8001
  python backend/scripts/verify_drg_pre_grouping_via_stream.py --text-file sample.txt --skip-grouping
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests


DEFAULT_MEDICAL_TEXT = """主诉：反复胸闷3年，加重伴胸痛1周

初步诊断：
1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛
2. 高血压病3级 极高危
3. 2型糖尿病

诊疗计划：拟行冠状动脉造影
"""


def _normalize_gender(raw: Any) -> str:
    text = str(raw or "").strip().upper()
    if text in {"F", "女", "2", "0"} or "女" in text:
        return "F"
    return "M"


def _extract_frontpage_stream(base_url: str, medical_text: str, timeout: int) -> Tuple[Dict[str, Any], int]:
    url = f"{base_url.rstrip('/')}/api/v1/frontpage/auto-generate-draft-stream"
    payload = {"medical_text": medical_text, "force_llm": False}

    resp = requests.post(url, json=payload, stream=True, timeout=timeout)
    resp.raise_for_status()

    latest_frontpage: Optional[Dict[str, Any]] = None
    event_name = "message"
    update_count = 0

    for raw in resp.iter_lines(decode_unicode=True):
        if not raw:
            continue
        line = raw.strip()

        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip() or "message"
            continue

        if not line.startswith("data: "):
            continue

        data_str = line[6:]
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        if isinstance(data.get("frontpage"), dict):
            latest_frontpage = data["frontpage"]

        if event_name == "update":
            update_count += 1

        if event_name == "done":
            break

    if not latest_frontpage:
        raise RuntimeError("stream finished but no frontpage payload found")
    return latest_frontpage, update_count


def _build_realtime_drg_payload(frontpage: Dict[str, Any], region: str) -> Dict[str, Any]:
    diagnoses = frontpage.get("diagnoses") or {}
    procedures = frontpage.get("procedures") or {}
    basic_info = frontpage.get("basic_info") or {}
    hospitalization = frontpage.get("hospitalization") or {}
    costs = frontpage.get("costs") or {}

    secondary_codes = [c for c in (diagnoses.get("discharge_other_icds") or []) if c]
    procedure_codes: List[str] = []
    if procedures.get("main_procedure_code"):
        procedure_codes.append(str(procedures.get("main_procedure_code")))
    for item in procedures.get("other_procedures") or []:
        if isinstance(item, dict) and item.get("code"):
            procedure_codes.append(str(item.get("code")))

    age = int(basic_info.get("age_years") or 50)
    gender = _normalize_gender(basic_info.get("gender_text") or basic_info.get("gender"))
    los = int(hospitalization.get("actual_hospital_days") or 7)
    total_cost = float(costs.get("total_cost") or 0)

    return {
        "primary_diagnosis_code": diagnoses.get("discharge_main_icd") or "",
        "primary_diagnosis_text": diagnoses.get("discharge_main_diagnosis_text"),
        "secondary_diagnosis_codes": secondary_codes,
        "procedure_codes": procedure_codes,
        "patient_age": age,
        "patient_gender": gender,
        "los": los,
        "total_cost": total_cost,
        "region": region,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="验证流式接口是否可用于 DRG 预分组")
    parser.add_argument("--base-url", default="http://localhost:8001", help="后端地址")
    parser.add_argument("--medical-text", default=None, help="直接传入病历文本")
    parser.add_argument("--text-file", default=None, help="从文本文件读取病历内容")
    parser.add_argument("--timeout", type=int, default=180, help="请求超时（秒）")
    parser.add_argument("--region", default="四川省", help="DRG 分组地区")
    parser.add_argument("--skip-grouping", action="store_true", help="只验证流式抽取，不调用 DRG 预分组")
    args = parser.parse_args()

    medical_text = args.medical_text or DEFAULT_MEDICAL_TEXT
    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8") as f:
            medical_text = f.read()
    if not medical_text.strip():
        print("[ERROR] medical_text 为空")
        return 2

    try:
        frontpage, update_count = _extract_frontpage_stream(args.base_url, medical_text, args.timeout)
    except Exception as exc:
        print(f"[ERROR] 流式抽取失败: {exc}")
        return 1

    diagnoses = frontpage.get("diagnoses") or {}
    procedures = frontpage.get("procedures") or {}
    print("=== Stream Extract Result ===")
    print(f"updates: {update_count}")
    print(f"main_diag_text: {diagnoses.get('discharge_main_diagnosis_text')}")
    print(f"main_diag_icd:  {diagnoses.get('discharge_main_icd')}")
    print(f"other_diag_icds: {diagnoses.get('discharge_other_icds')}")
    print(f"main_proc_text: {procedures.get('main_procedure_text')}")
    print(f"main_proc_code: {procedures.get('main_procedure_code')}")

    payload = _build_realtime_drg_payload(frontpage, args.region)
    if not payload["primary_diagnosis_code"]:
        print("[FAIL] 不可行：流式结果缺少 primary_diagnosis_code（discharge_main_icd）")
        return 3

    if args.skip_grouping:
        print("[PASS] 可行：流式结果已具备 DRG 预分组关键字段。")
        return 0

    try:
        url = f"{args.base_url.rstrip('/')}/api/v1/drg/predict-realtime"
        resp = requests.post(url, json=payload, timeout=args.timeout)
        resp.raise_for_status()
        result = resp.json()
    except Exception as exc:
        print(f"[ERROR] DRG 预分组调用失败: {exc}")
        print("[INFO] 但抽取字段完整，接口联调问题与可行性本身可分开看。")
        return 4

    drg_data = result.get("data") or {}
    print("=== DRG Predict Realtime ===")
    print(f"success: {drg_data.get('success')}")
    print(f"mdc: {drg_data.get('mdc_code')}")
    print(f"adrg: {drg_data.get('adrg_code')}")
    print(f"drg: {drg_data.get('drg_code')}")
    print(f"grouping_logic: {drg_data.get('grouping_logic')}")

    if not drg_data.get("success"):
        print("[WARN] 抽取可行，但当前预分组返回未成功，请结合 grouping_logic 排查分组条件。")
        return 5

    print("[PASS] 可行：流式抽取结果可直接驱动 DRG 预分组。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

