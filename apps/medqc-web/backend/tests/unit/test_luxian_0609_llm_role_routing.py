"""按调用点切换裁决模型（LLM_ROLE_MODELS，2026-10-19）：未配置不变、脱敏不变、配置错误回退。"""

from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import llm_role_routing as routing
from app.services.luxian_0609.exam_finding_analysis import SCHEMA_VERSION, check_exam_finding_analysis
from app.services.luxian_0609.exam_finding_relevance import apply_relevance_hints
from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client


class _Capture:
    def __init__(self, outputs=()):
        self.prompts: list[str] = []
        self.outputs = list(outputs)

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        content = self.outputs.pop(0) if self.outputs else "{}"
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


def test_parse_role_models_keeps_known_roles_and_ignores_invalid_items():
    parsed = routing.parse_role_models(
        " exam_finding_analysis = DeepSeek/deepseek-flash , unknown_role=deepseek/x, broken, exam_finding_analysis=")
    assert parsed == {"exam_finding_analysis": ("deepseek", "deepseek-flash")}
    assert routing.parse_role_models(None) == {} and routing.parse_role_models("") == {}


def test_unconfigured_role_returns_the_same_client(monkeypatch):
    monkeypatch.setenv("LLM_ROLE_MODELS", "")
    client = wrap_luxian_0609_llm_client(_Capture())
    assert routing.client_for_role(client, "exam_finding_analysis") is client
    plain = object()
    assert routing.client_for_role(plain, "exam_finding_analysis") is plain


def test_unavailable_provider_falls_back_and_available_provider_builds_role_client(monkeypatch):
    monkeypatch.setenv("LLM_ROLE_MODELS", "exam_finding_analysis=deepseek/deepseek-flash")
    monkeypatch.setenv("LLM_VISIBLE_PROVIDERS", '["alibaba","deepseek"]')
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    assert routing.build_role_delegate("exam_finding_analysis") is None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-key")
    delegate = routing.build_role_delegate("exam_finding_analysis")
    assert delegate is not None
    assert (delegate.provider_code, delegate.model, delegate.enable_thinking) == ("deepseek", "deepseek-flash", False)


@pytest.mark.asyncio
async def test_role_client_keeps_identity_redaction(monkeypatch):
    judge = _Capture()
    monkeypatch.setattr(routing, "build_role_delegate", lambda role: judge)
    client = wrap_luxian_0609_llm_client(_Capture(), identity_values=("赵甲乙",))
    role_client = routing.client_for_role(client, "exam_finding_analysis")
    assert role_client is not client
    await role_client.generate("赵甲乙，老年男性，胸部CT示右肺结节。")
    assert judge.prompts and "赵甲乙" not in judge.prompts[0] and "胸部CT示右肺结节" in judge.prompts[0]


def test_role_switch_failure_never_interrupts_qc():
    class _Broken:
        def for_role(self, role):
            raise RuntimeError("bad config")

    broken = _Broken()
    assert routing.client_for_role(broken, "exam_finding_analysis") is broken


@pytest.mark.asyncio
async def test_finding_analysis_uses_the_configured_role_model(monkeypatch):
    projection = build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "EX-1", "exam_name": "胸部CT平扫", "exam_time": "2026-08-18 12:30:00",
                         "report_time": "2026-08-18 13:30:00", "exam_conclusion": "右肺结节。"},),
        "daily_course_record": ({"record_time": "2026-08-18 15:00:00",
                                 "record_content": "胸部CT示右肺结节，与咳嗽相符，请胸外科会诊。"},),
    })
    projection = apply_relevance_hints(projection, {1: "positive"})
    ref = next(iter(projection.course_times))
    answer = json.dumps({"schema_version": SCHEMA_VERSION, "docs": [{
        "event_position": 1, "course_doc_ref": ref, "quote_type": "none", "basis_relation": "none",
        "basis_fragment_ids": [], "course_fragment_ids": [], "report_fragment_id": ""}]})
    judge, main = _Capture([answer]), _Capture()
    monkeypatch.setattr(routing, "build_role_delegate", lambda role: judge if role == "exam_finding_analysis" else None)
    outcome = await check_exam_finding_analysis(projection, wrap_luxian_0609_llm_client(main))
    # 判为未分析时另有单独复核（用户决定 2026-10-19）；所有分析核验调用都走配置的判断模型。
    assert outcome.state == "ready" and len(judge.prompts) >= 1 and main.prompts == []
