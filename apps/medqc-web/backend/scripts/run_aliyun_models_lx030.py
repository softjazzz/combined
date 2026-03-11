#!/usr/bin/env python3
"""
依次切换系统中配置的所有阿里云（通义千问）模型，调用 /api/v1/qc/sichuan/test-rule
对 LX-030（病案首页诊断 vs 出院诊断）进行质控，统计哪些模型能识别诊断遗漏问题。

用法：
    ALIYUN_API_KEY=sk-xxx python3 scripts/run_aliyun_models_lx030.py
可选环境变量：
    QC_BACKEND_BASE_URL   默认为 http://127.0.0.1:8001
    QC_CONFIG_NAME        默认为 default
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx


BASE_URL = os.getenv("QC_BACKEND_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
CONFIG_NAME = os.getenv("QC_CONFIG_NAME", "default")
ALIYUN_API_KEY = os.getenv("ALIYUN_API_KEY") or os.getenv("SICHUAN_API_KEY")
PROVIDER_CODE = "alibaba"
TEST_RULE_ID = "LX-030"
TEST_DOCUMENT = """出院记录

姓名：张三
性别：男
年龄：58岁
住院号：2025100123
入院日期：2025-10-01
出院日期：2025-10-15
出院医嘱下达时间：2025-10-15 10:00
住院天数：14天

病案首页诊断：
1. 冠心病 急性非ST段抬高型心肌梗死
   冠状动脉粥样硬化性心脏病
   经皮冠状动脉介入治疗术后（前降支支架植入术后）
2. 心功能不全 心功能Ⅱ级（NYHA分级）
3. 高血压病 3级 极高危
4. 2型糖尿病
5. 高脂血症

入院诊断：
1. 冠心病 急性非ST段抬高型心肌梗死
2. 心功能不全 心功能Ⅲ级（NYHA分级）
3. 高血压病 3级 极高危
4. 2型糖尿病

出院诊断：
1. 冠心病 急性非ST段抬高型心肌梗死
   冠状动脉粥样硬化性心脏病
   经皮冠状动脉介入治疗术后（前降支支架植入术后）
2. 心功能不全 心功能Ⅱ级（NYHA分级）
3. 高血压病 3级 极高危
4. 2型糖尿病

诊疗经过略。
"""

# 当接口无法提供动态模型列表时的兜底
FALLBACK_MODELS: List[Dict[str, str]] = [
    {"model_code": "qwen-plus", "model_name": "Qwen-Plus"},
    {"model_code": "qwen-turbo", "model_name": "Qwen-Turbo"},
    {"model_code": "qwen-max", "model_name": "Qwen-Max"},
    {"model_code": "qwen3-30b-a3b", "model_name": "Qwen3-30B-A3B"},
    {"model_code": "qwen3-30b-a3b-instruct-2507", "model_name": "Qwen3-30B-A3B (2507)"},
    {"model_code": "qwen3-14b", "model_name": "Qwen3-14B"},
    {"model_code": "qwen3-8b", "model_name": "Qwen3-8B"},
    {"model_code": "qwen3-4b", "model_name": "Qwen3-4B"},
    {"model_code": "qwen3-235b-a22b-instruct-2507", "model_name": "Qwen3-235B"},
    {"model_code": "qwen2.5-32b-instruct", "model_name": "Qwen2.5-32B-Instruct"},
    {"model_code": "qwen2.5-14b-instruct", "model_name": "Qwen2.5-14B-Instruct"},
    {"model_code": "qwen2.5-7b-1m", "model_name": "Qwen2.5-7B-1M"},
    {"model_code": "qwen-flash-2025-07-28", "model_name": "Qwen Flash (2025-07-28)"},
]


def require_api_key() -> None:
    if not ALIYUN_API_KEY:
        raise SystemExit(
            "请先设置 ALIYUN_API_KEY（或 SICHUAN_API_KEY）环境变量，脚本才能调用 DashScope 接口。"
        )


async def fetch_aliyun_models() -> List[Dict[str, str]]:
    """调用后端 models 接口，读取当前系统配置的阿里云模型列表。"""
    if os.getenv("QC_USE_FALLBACK_MODELS") == "1":
        return FALLBACK_MODELS

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BASE_URL}/api/v1/llm/models",
                params={"provider_id": PROVIDER_CODE},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return FALLBACK_MODELS

    data = payload.get("data") or []
    models: List[Dict[str, str]] = []
    for item in data:
        provider = (
            str(item.get("provider_id") or item.get("provider") or item.get("provider_code") or "")
            .lower()
        )
        if provider and "ali" not in provider:
            continue
        code = item.get("model_code") or item.get("id") or item.get("value")
        name = item.get("model_name") or item.get("label") or code
        if not code:
            continue
        models.append({"model_code": code, "model_name": name})

    return models or FALLBACK_MODELS


async def save_config(model_code: str) -> bool:
    """将指定模型写入 /api/v1/llm/configs。"""
    payload = {
        "config_name": CONFIG_NAME,
        "provider_code": PROVIDER_CODE,
        "model_code": model_code,
        "api_key": ALIYUN_API_KEY,
        "custom_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "is_active": True,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/api/v1/llm/configs", json=payload)
        if resp.status_code != 200:
            print(f"❌ 保存配置失败 ({model_code}): {resp.text}")
            return False
        return True


async def reload_config() -> bool:
    params = {"config_name": CONFIG_NAME}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/api/v1/qc/sichuan/reload-config", params=params)
        if resp.status_code != 200:
            print(f"❌ 重新加载配置失败: {resp.text}")
            return False
        return True


async def get_current_model() -> str | None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/api/v1/qc/sichuan/current-config")
        if resp.status_code != 200:
            return None
        data = resp.json().get("data") or {}
        return data.get("model")


async def run_test_rule() -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=180.0) as client:
        start = time.time()
        resp = await client.post(
            f"{BASE_URL}/api/v1/qc/sichuan/test-rule",
            json={
                "rule_id": TEST_RULE_ID,
                "medical_text": TEST_DOCUMENT,
            },
        )
        elapsed = time.time() - start
        result = resp.json()
        result["_http_status"] = resp.status_code
        result["_elapsed"] = elapsed
        return result


def summarize_detection(result: Dict[str, Any]) -> Dict[str, Any]:
    """提取是否成功发现高脂血症遗漏。"""
    data = result.get("data") or {}
    issues = data.get("issues") or []
    descriptions = [issue.get("description", "") for issue in issues]
    evidence = data.get("evidence", "")

    detected = not data.get("is_compliant", True)
    if not detected:
        # 再次兜底：查找文本是否提到“未见”或“遗漏”
        text_block = " ".join(descriptions + [evidence])
        if "未见" in text_block or "遗漏" in text_block:
            detected = True

    return {
        "http_status": result.get("_http_status"),
        "elapsed_seconds": result.get("_elapsed"),
        "is_compliant": data.get("is_compliant"),
        "status": data.get("status"),
        "issues": issues,
        "detected": detected,
        "findings": data.get("findings", ""),
        "evidence": evidence,
        "token_usage": (data.get("metadata") or {}).get("tokens_used"),
    }


async def test_model(model: Dict[str, str]) -> Dict[str, Any]:
    code = model["model_code"]
    name = model.get("model_name") or code

    print(f"\n{'=' * 80}")
    print(f"🧪 测试模型: {name} ({code})")
    print(f"{'-' * 80}")

    if not await save_config(code):
        return {"model_code": code, "model_name": name, "error": "保存配置失败"}

    if not await reload_config():
        return {"model_code": code, "model_name": name, "error": "重新加载配置失败"}

    await asyncio.sleep(1.0)  # 等配置完全应用

    current = await get_current_model()
    if current != code:
        return {
            "model_code": code,
            "model_name": name,
            "error": f"配置验证失败（当前: {current}）",
        }

    result = await run_test_rule()
    summary = summarize_detection(result)

    outcome = "✅ 检出" if summary["detected"] else "⚠️ 未检出"
    print(f"{outcome} | is_compliant={summary['is_compliant']} | status={summary['status']} | token={summary['token_usage']} | 用时 {summary['elapsed_seconds']:.2f}s")

    if not summary["detected"]:
        print(f"   ↪ findings: {summary['findings']}")

    return {
        "model_code": code,
        "model_name": name,
        "detected": summary["detected"],
        "summary": summary,
        "raw_response": result,
    }


async def main() -> None:
    require_api_key()
    print("🎯 LX-030 阿里云模型质控对比")
    print(f"🔗 后端接口: {BASE_URL}")
    print(f"🗂 质控规则: {TEST_RULE_ID}")
    print(f"⚙️ 配置名称: {CONFIG_NAME}")

    models = await fetch_aliyun_models()
    print(f"📋 本次共测试 {len(models)} 个模型。")

    results: List[Dict[str, Any]] = []
    for model in models:
        res = await test_model(model)
        results.append(res)
        await asyncio.sleep(1.5)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).resolve().parents[1] / "app" / "storage" / "qc_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"aliyun_lx030_model_report_{timestamp}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n📁 详细结果已写入: {output_path}")

    success_models = [r for r in results if r.get("detected")]
    fail_models = [r for r in results if not r.get("detected")]

    print(f"\n{'=' * 80}")
    print("📊 汇总")
    print(f"{'=' * 80}")
    print(f"✅ 正确检出的模型: {len(success_models)}")
    for item in success_models:
        print(f"   - {item['model_name']} ({item['model_code']})")

    print(f"⚠️ 未检出的模型: {len(fail_models)}")
    for item in fail_models:
        print(f"   - {item['model_name']} ({item['model_code']}): {item.get('error') or item['summary']['findings']}")


if __name__ == "__main__":
    asyncio.run(main())

