"""语义抽取指令和固定事实交付保护；不冒充真实模型正确率。"""
from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.native_preop_content_execution import _prompt
from test_luxian_0609_preop_fact_protocol import SUMMARY, fact, present_items, publish


def test_prompt_defines_complete_review_separately_from_unknown():
    prompt = _prompt([("S1", "presurg_summary", "简要病情已记录。医师签名：测试医师。")], [SUMMARY])
    assert "完整核查后仅未找到对应内容，应返回missing" in prompt
    assert "材料不全、无法完成核查、候选含义不明或上下文冲突" in prompt
    assert "仅有医师签名或参加名单不能证明已经查看" in prompt
    assert "拟查看、请术者查看不能证明已经查看" in prompt


def test_prompt_preserves_diagnosis_and_preparation_semantic_scope():
    text = "检查提示甲病可能。综合临床诊断为乙病，拟行甲手术。拟完善心肺功能评估。"
    prompt = _prompt([("S1", "presurg_summary", text)], [SUMMARY])
    assert "不要求专名栏目或固定措辞" in prompt
    assert "医生结合检查明确采纳为本次术前诊断" in prompt
    assert "单独的影像所见、检查提示或既往诊断不能自动等同" in prompt
    assert "已完成或拟实施的术前检查、准备及禁忌评估" in prompt
    docs = json.loads(prompt.split("\n\n文书：\n", 1)[1])["documents"]
    assert "".join(s["text"] for s in docs[0]["spans"]) == text


@pytest.mark.parametrize(
    "state,reviewed,status",
    [("missing", True, "non_compliant"), ("unknown", True, "data_gap"), ("unknown", False, "data_gap")],
)
def test_signature_only_does_not_make_python_coerce_supplied_semantic_state(state, reviewed, status):
    # 与真实残留相同的边界：完整文书仅有签名。假LLM输入分别固定三态，
    # 验证执行器保持该态，不能靠Python见到签名/没找到就改判。
    items = present_items(SUMMARY)
    items["surgeon_preop_visit"] = fact(state, reviewed=reviewed)
    rows = {"presurg_summary": [{"document_id": "D1", "record_content": "拟行甲手术。医师签名：测试医师。"}]}
    final, _ = publish(SUMMARY, items=items, rows=rows)
    facts = final["customer_display_facts"]
    assert final["status"] == status
    assert facts["missing_fields"] == (["surgeon_preop_visit"] if state == "missing" else [])
    if state == "unknown":
        assert facts["uncertain_fields"] == ["surgeon_preop_visit"]
