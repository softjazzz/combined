from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.custom_qc_service import evaluate_inline_rule_orchestrated
from app.services.qc_execution_cache import (
    QCExecutionCache,
    build_execution_cache_key,
    build_prompt_hash,
    build_record_snapshot_hash,
)
from app.services.qc_rule_orchestrator import QCRuleOrchestrator
from app.services.sichuan_qc import legacy_rule_service
from app.services.sichuan_qc_service import SichuanQCService


def _make_offline_service() -> tuple[SichuanQCService, list[str]]:
    service = SichuanQCService(
        {
            "provider_code": "deepseek",
            "api_endpoint": "http://127.0.0.1:0/v1",
            "api_key": "offline-test-key",
            "model": "test-model-v1",
            "allow_mock_when_unconfigured": True,
        }
    )
    prompts: list[str] = []

    async def _stub_generate(prompt: str) -> dict:
        call_no = len(prompts) + 1
        prompts.append(prompt)
        missing = "MISSING_CONSENT_SIGNAL" in prompt
        status = "non_compliant" if missing else "compliant"
        is_compliant = not missing
        findings = f"call#{call_no}: " + ("缺少知情同意书" if missing else "资料齐全")
        if "rule_id:" in prompt or "items" in prompt:
            payload = {
                "items": [
                    {
                        "rule_id": "SC-TEST-001",
                        "status": status,
                        "is_compliant": is_compliant,
                        "findings": findings,
                        "evidence": "2026-01-01 首次病程记录正文",
                        "suggestion": "请补充知情同意书" if missing else "无需修改",
                        "confidence": 0.95,
                    }
                ]
            }
        else:
            payload = {
                "is_compliant": is_compliant,
                "findings": findings,
                "evidence": "2026-01-01 首次病程记录正文",
                "suggestion": "请补充知情同意书" if missing else "无需修改",
                "confidence": 0.95,
            }
        return {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"total_tokens": 100, "prompt_tokens": 70, "completion_tokens": 30},
            "_api_time": 0.01,
        }

    service.client.generate = _stub_generate
    return service, prompts


def _sample_rule(rule_id: str = "SC-TEST-001", document_type: str = "病程记录") -> dict:
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "name": "测试结构化证据规则",
        "category": document_type,
        "applicable_documents": [document_type],
        "executor_type": "llm",
        "execution_domain": "course",
        "doc_scope": "primary",
        "rule_family": "general",
        "rule_version": "v1",
        "prompt_version": "v1",
        "custom_prompt": "请检查病历及结构化证据。\n{medical_text}",
    }


def test_record_snapshot_hash_isolates_evidence_payload_and_tenant_scope() -> None:
    base = {
        "id": "VISIT-1001",
        "document_type": "病程记录",
        "content": "患者一般情况可。",
        "institute_id": "HOSP_A",
        "patient_id": "PAT_1",
        "visit_id": "VISIT-1001",
        "source_schema": "schema_a",
        "evidence_payload": {
            "document_hits": {"consent": True, "admission": True},
            "supporting_documents": [{"document_type": "知情同意书", "evidence_text": "已签字"}],
            "timeline_facts": ["2026-01-01 已签署知情同意书"],
        },
    }
    reordered = {
        **base,
        "evidence_payload": {
            "timeline_facts": ["2026-01-01 已签署知情同意书"],
            "supporting_documents": [{"evidence_text": "已签字", "document_type": "知情同意书"}],
            "document_hits": {"admission": True, "consent": True},
        },
    }
    different_evidence = {
        **base,
        "evidence_payload": {
            "document_hits": {"consent": False, "admission": True},
            "supporting_documents": [{"document_type": "知情同意书", "evidence_text": "未见签字"}],
            "timeline_facts": ["2026-01-01 缺少知情同意书"],
        },
    }
    different_institute = {**base, "institute_id": "HOSP_B"}
    different_schema = {**base, "source_schema": "schema_b"}
    different_sampling = {**base, "llm_sampling_params": {"temperature": 0.7}}

    h_base = build_record_snapshot_hash(base)
    assert h_base == build_record_snapshot_hash(reordered)
    assert h_base != build_record_snapshot_hash(different_evidence)
    assert h_base != build_record_snapshot_hash(different_institute)
    assert h_base != build_record_snapshot_hash(different_schema)
    assert h_base != build_record_snapshot_hash(different_sampling)


def test_record_snapshot_hash_handles_non_json_types_and_fails_closed_on_unknown_objects() -> None:
    record_with_rich_types = {
        "id": "VISIT-2",
        "document_type": "病程记录",
        "content": "正文",
        "evidence_payload": {
            "ts": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            "day": date(2026, 1, 2),
            "score": Decimal("0.95"),
            "tags": {"b", "a"},
        },
    }
    h1 = build_record_snapshot_hash(record_with_rich_types)
    assert len(h1) == 64
    assert h1 == build_record_snapshot_hash(
        {
            **record_with_rich_types,
            "evidence_payload": {
                **record_with_rich_types["evidence_payload"],
                "tags": {"a", "b"},
            },
        }
    )

    none_hash = build_record_snapshot_hash({"id": "V1", "document_type": "病程记录", "content": "x"})
    empty_hash = build_record_snapshot_hash(
        {"id": "V1", "document_type": "病程记录", "content": "x", "evidence_payload": {}}
    )
    assert none_hash == empty_hash

    unserializable_hash = build_record_snapshot_hash(
        {
            "id": "V1",
            "document_type": "病程记录",
            "content": "x",
            "evidence_payload": {"opaque": object()},
        }
    )
    assert unserializable_hash == ""
    assert (
        build_execution_cache_key(
            record_snapshot_hash=unserializable_hash,
            rule_id="SC-001",
            rule_version="v1",
            prompt_hash="abc",
            model_version="m1",
        )
        == ""
    )


def test_prompt_hash_and_cache_key_cover_template_and_execution_dimensions() -> None:
    rule_a = {"rule_id": "R1", "name": "规则A", "prompt_template": "模板A"}
    rule_b = {"rule_id": "R1", "name": "规则A", "prompt_template": "模板B"}
    assert build_prompt_hash(rule_a) != build_prompt_hash(rule_b)

    # Backward-compatible 5-arg call
    legacy_key = build_execution_cache_key(
        record_snapshot_hash="snap-1",
        rule_id="SC-001",
        rule_version="v1",
        prompt_hash="p-1",
        model_version="model-1",
    )
    assert len(legacy_key) == 64

    base_kwargs = dict(
        record_snapshot_hash="snap-1",
        rule_id="SC-001",
        rule_version="v1",
        prompt_hash="p-1",
        model_version="model-1",
        prompt_version="pv1",
        evidence_source="bundle",
        prompt_strategy="batch_compact_v1",
        quality_profile="throughput_v1",
        batch_output_mode="full",
        bucket_strategy="domain_only",
    )
    base_key = build_execution_cache_key(**base_kwargs)
    for field, alt in [
        ("prompt_version", "pv2"),
        ("evidence_source", "custom_qc_workspace"),
        ("prompt_strategy", "single_rule_v1"),
        ("quality_profile", "effect_priority_v1"),
        ("batch_output_mode", "compact"),
        ("bucket_strategy", "domain_family"),
    ]:
        assert build_execution_cache_key(**{**base_kwargs, field: alt}) != base_key


@pytest.mark.asyncio
async def test_evaluate_document_with_rules_does_not_collide_on_evidence_payload_or_institute() -> None:
    service, prompts = _make_offline_service()
    rule = _sample_rule()

    # 1. Changing evidence_payload with identical document_id / document_type / content
    r1 = await service.evaluate_document_with_rules(
        document_id="VISIT-1001",
        content="2026-01-01 首次病程记录正文",
        document_type="病程记录",
        rules=[rule],
        evidence_source="bundle",
        evidence_payload={
            "supporting_documents": [{"document_type": "知情同意书", "evidence_text": "CONSENT_PRESENT_OK"}],
            "document_hits": {"consent": True},
        },
        source_institute_id="HOSP_A",
        source_patient_id="PAT_A",
        source_visit_id="VISIT-1001",
    )
    r2 = await service.evaluate_document_with_rules(
        document_id="VISIT-1001",
        content="2026-01-01 首次病程记录正文",
        document_type="病程记录",
        rules=[rule],
        evidence_source="bundle",
        evidence_payload={
            "supporting_documents": [{"document_type": "知情同意书", "evidence_text": "MISSING_CONSENT_SIGNAL"}],
            "document_hits": {"consent": False},
        },
        source_institute_id="HOSP_A",
        source_patient_id="PAT_A",
        source_visit_id="VISIT-1001",
    )
    res1 = r1["evaluation_results"][0]
    res2 = r2["evaluation_results"][0]
    assert len(prompts) == 2
    assert res1["status"] == "compliant"
    assert res1["metadata"]["cache_hit"] is False
    assert res2["status"] == "non_compliant"
    assert res2["metadata"]["cache_hit"] is False
    assert res1["metadata"]["cache_key"] != res2["metadata"]["cache_key"]

    # Repeating exact same second call should hit cache
    r2_repeat = await service.evaluate_document_with_rules(
        document_id="VISIT-1001",
        content="2026-01-01 首次病程记录正文",
        document_type="病程记录",
        rules=[rule],
        evidence_source="bundle",
        evidence_payload={
            "supporting_documents": [{"document_type": "知情同意书", "evidence_text": "MISSING_CONSENT_SIGNAL"}],
            "document_hits": {"consent": False},
        },
        source_institute_id="HOSP_A",
        source_patient_id="PAT_A",
        source_visit_id="VISIT-1001",
    )
    assert len(prompts) == 2
    assert r2_repeat["evaluation_results"][0]["metadata"]["cache_hit"] is True
    assert r2_repeat["evaluation_results"][0]["status"] == "non_compliant"

    # 2. Changing source_institute_id with identical document_id / document_type / content
    prompts.clear()
    service.execution_cache.clear()
    b1 = await service.evaluate_document_with_rules(
        document_id="VISIT-2002",
        content="2026-01-01 首次病程记录正文",
        document_type="病程记录",
        rules=[rule],
        evidence_source="medical_text",
        source_institute_id="HOSP_A",
        source_visit_id="VISIT-2002",
    )
    b2 = await service.evaluate_document_with_rules(
        document_id="VISIT-2002",
        content="2026-01-01 首次病程记录正文",
        document_type="病程记录",
        rules=[rule],
        evidence_source="medical_text",
        source_institute_id="HOSP_B",
        source_visit_id="VISIT-2002",
    )
    assert len(prompts) == 2
    assert b1["evaluation_results"][0]["metadata"]["cache_hit"] is False
    assert b2["evaluation_results"][0]["metadata"]["cache_hit"] is False
    assert b1["evaluation_results"][0]["metadata"]["cache_key"] != b2["evaluation_results"][0]["metadata"]["cache_key"]


@pytest.mark.asyncio
async def test_running_final_bundle_input_does_not_collide_across_institutes_or_supporting_docs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, prompts = _make_offline_service()
    rule = _sample_rule(document_type="首次病程记录")
    monkeypatch.setattr(service, "get_rule_by_id", lambda rid: rule if rid == "SC-TEST-001" else None)

    bundle_hosp_a = {
        "scene": "running",
        "institute_id": "HOSP_A",
        "patient_id": "PAT_A",
        "visit_id": "VISIT-3003",
        "source_schema": "hosp_a_schema",
        "medical_text": "2026-01-01 首次病程记录正文",
        "document_hits": {"first_course_record": True, "admission_record": True},
        "source_doc_priority": ["first_course_record", "admission_record"],
        "structured_context": {
            "first_course_record": "2026-01-01 首次病程记录正文",
            "admission_record": "CONSENT_PRESENT_OK 入院记录完整",
        },
        "timeline_facts": ["2026-01-01 已签署知情同意书"],
        "text_available": True,
    }
    bundle_hosp_b = {
        **bundle_hosp_a,
        "institute_id": "HOSP_B",
        "patient_id": "PAT_B",
        "source_schema": "hosp_b_schema",
        "structured_context": {
            "first_course_record": "2026-01-01 首次病程记录正文",
            "admission_record": "MISSING_CONSENT_SIGNAL 入院记录缺失关键项",
        },
        "timeline_facts": ["2026-01-01 未见知情同意书"],
    }

    r_a = await service.evaluate_running_final_bundle_input(bundle=bundle_hosp_a, rule_ids=["SC-TEST-001"])
    r_b = await service.evaluate_running_final_bundle_input(bundle=bundle_hosp_b, rule_ids=["SC-TEST-001"])
    r_b_again = await service.evaluate_running_final_bundle_input(bundle=bundle_hosp_b, rule_ids=["SC-TEST-001"])

    assert len(prompts) == 2
    assert r_a["evaluation_results"][0]["status"] == "compliant"
    assert r_a["evaluation_results"][0]["metadata"]["cache_hit"] is False
    assert r_b["evaluation_results"][0]["status"] == "non_compliant"
    assert r_b["evaluation_results"][0]["metadata"]["cache_hit"] is False
    assert r_b_again["evaluation_results"][0]["status"] == "non_compliant"
    assert r_b_again["evaluation_results"][0]["metadata"]["cache_hit"] is True


@pytest.mark.asyncio
async def test_legacy_rule_for_visit_forwards_tenant_coordinates(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = _make_offline_service()
    rule = _sample_rule(document_type="首次病程记录")
    captured: dict = {}

    async def _fake_orchestrated(**kwargs):
        captured.update(kwargs)
        return {
            "results": [
                {
                    "rule_id": "SC-TEST-001",
                    "rule_name": rule["name"],
                    "status": "compliant",
                    "is_compliant": True,
                    "metadata": {},
                }
            ]
        }

    fake_input = SimpleNamespace(
        document_type="首次病程记录",
        source_documents=[{"content": "2026-01-01 首次病程记录正文"}],
        to_dict=lambda: {},
    )
    monkeypatch.setattr(service, "get_rule_by_id", lambda _: rule)
    monkeypatch.setattr(service, "_build_rule_execution_input_from_bundle", lambda **_: fake_input)
    monkeypatch.setattr(service, "_score_primary_candidate_for_rule", lambda **_: 1)
    monkeypatch.setattr(service, "_build_copy_content_similarity_signals", lambda **_: [])
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _fake_orchestrated)
    monkeypatch.setattr(service, "_apply_rule_text_only_fallbacks", lambda **kw: kw["engine_result"])
    monkeypatch.setattr(
        legacy_rule_service,
        "route_rule_to_domain",
        lambda _: SimpleNamespace(execution_domain="course", to_dict=lambda: {}),
    )
    monkeypatch.setattr(legacy_rule_service, "render_rule_execution_medical_text", lambda _: "正文")
    monkeypatch.setattr(
        legacy_rule_service,
        "build_evidence_payload_from_rule_input",
        lambda **_: SimpleNamespace(to_dict=lambda: {}),
    )

    await legacy_rule_service.evaluate_legacy_rule_for_visit(
        service,
        load_domain_bundle=lambda **_: {},
        rule_id="SC-TEST-001",
        institute_id="HOSP_X",
        patient_id="PAT_X",
        visit_id="VISIT_X",
        source_schema="custom_schema",
    )

    assert captured["source_institute_id"] == "HOSP_X"
    assert captured["source_patient_id"] == "PAT_X"
    assert captured["source_visit_id"] == "VISIT_X"
    assert captured["source_schema"] == "custom_schema"


@pytest.mark.asyncio
async def test_custom_qc_inline_rule_isolates_institute_and_sampling_params() -> None:
    service, prompts = _make_offline_service()
    inline_rule = {
        "rule_code": "LXE-CACHE-01",
        "name": "内联测试规则",
        "description": "测试缓存隔离",
        "document_type": "病程记录",
        "prompt_template": "请检查：{medical_text}",
    }
    base_record = {
        "record_id": "V001",
        "visit_id": "V001",
        "institute_id": "HOSP_A",
        "medical_text": "2026-01-01 首次病程记录正文",
    }

    r1 = await evaluate_inline_rule_orchestrated(
        qc_service=service,
        rule=inline_rule,
        record=base_record,
        temperature=0.1,
    )
    r2_diff_hosp = await evaluate_inline_rule_orchestrated(
        qc_service=service,
        rule=inline_rule,
        record={**base_record, "institute_id": "HOSP_B"},
        temperature=0.1,
    )
    r3_diff_temp = await evaluate_inline_rule_orchestrated(
        qc_service=service,
        rule=inline_rule,
        record=base_record,
        temperature=0.7,
    )
    r4_repeat = await evaluate_inline_rule_orchestrated(
        qc_service=service,
        rule=inline_rule,
        record=base_record,
        temperature=0.7,
    )

    assert len(prompts) == 3
    assert r1["metadata"]["cache_hit"] is False
    assert r2_diff_hosp["metadata"]["cache_hit"] is False
    assert r3_diff_temp["metadata"]["cache_hit"] is False
    assert r4_repeat["metadata"]["cache_hit"] is True


@pytest.mark.asyncio
async def test_orchestrator_programmatic_rules_bypass_execution_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = QCRuleOrchestrator()
    cache = QCExecutionCache()
    rule = {
        "rule_id": "SC-PROG-01",
        "executor_type": "program",
        "execution_domain": "course",
        "doc_scope": "primary",
        "rule_family": "general",
        "rule_version": "v1",
        "prompt_version": "v1",
    }
    record = {"id": "V1", "document_type": "病程记录", "content": "正文"}

    # Pre-seed cache with a stale LLM result under the matching key
    stale_key = build_execution_cache_key(
        record_snapshot_hash=build_record_snapshot_hash(record),
        rule_id="SC-PROG-01",
        rule_version="v1",
        prompt_hash=build_prompt_hash(rule),
        model_version="m1",
        prompt_version="v1",
        evidence_source="medical_text",
        prompt_strategy="single_rule_v1",
        quality_profile="throughput_v1",
        batch_output_mode="full",
        bucket_strategy="domain_only",
    )
    cache.set(stale_key, {"rule_id": "SC-PROG-01", "status": "non_compliant", "is_compliant": False, "metadata": {"executor_type": "llm"}})

    monkeypatch.setattr(orchestrator._program_executor, "can_execute", lambda _rule: True)
    monkeypatch.setattr(
        orchestrator._program_executor,
        "evaluate",
        lambda **_kw: {"rule_id": "SC-PROG-01", "status": "compliant", "is_compliant": True, "metadata": {"executor_type": "program"}},
    )

    async def _never_llm(_rule, _record):
        raise AssertionError("programmatic rule should not invoke LLM")

    out = await orchestrator.evaluate_rules(
        rules=[rule],
        medical_record=record,
        llm_evaluate=_never_llm,
        model_version="m1",
        execution_cache=cache,
    )
    assert out["results"][0]["status"] == "compliant"
    assert out["results"][0]["metadata"]["executor_type"] == "program"
    assert out["results"][0]["metadata"]["cache_hit"] is False
    assert out["cache_breakdown"]["hit"] == 0
