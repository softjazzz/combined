import pytest

import app.services.qc_input_adapters as adapter_module
import app.services.qc_input_adapters.running_final_bundle_runtime as runtime_module
from app.services.qc_input_adapters.running_final_bundle_runtime import evaluate_running_final_bundle
from app.services.sichuan_qc_service import SichuanQCService


@pytest.mark.asyncio
async def test_service_facade_subclass_should_resolve_base_definition_module(monkeypatch):
    class _DerivedSichuanQCService(SichuanQCService):
        pass

    class _FacadeDependencyReached(RuntimeError):
        pass

    monkeypatch.setattr(
        "app.services.qc_input_adapters.adapt_bundle_to_sichuan_eval_args",
        lambda bundle, rule_ids: {
            "document_id": "V-SUBCLASS",
            "document_type": "在院病历",
            "content": "病历正文",
            "rule_ids": [],
            "evidence_payload": {},
        },
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.normalize_quality_profile",
        lambda _profile: (_ for _ in ()).throw(_FacadeDependencyReached()),
    )

    with pytest.raises(_FacadeDependencyReached):
        await _DerivedSichuanQCService().evaluate_running_final_bundle_input(
            {"scene": "running", "visit_id": "V-SUBCLASS"}
        )


@pytest.mark.asyncio
async def test_service_facade_should_forward_running_final_bundle_options(monkeypatch):
    service = SichuanQCService()
    bundle = {"scene": "final", "visit_id": "V-FACADE"}

    def cancellation_check():
        return False

    def trace_sink(_item):
        return None

    captured = {}

    async def _fake_evaluate(host, forwarded_bundle, **kwargs):
        captured.update(
            {
                "host": host,
                "bundle": forwarded_bundle,
                **kwargs,
            }
        )
        return {"facade": "ok"}

    monkeypatch.setattr(
        "app.services.sichuan_qc_service.evaluate_running_final_bundle_input",
        _fake_evaluate,
    )

    result = await service.evaluate_running_final_bundle_input(
        bundle,
        rule_ids=["LX0609-11-01-01"],
        bucket_strategy="domain_family",
        quality_profile="effect_priority_v1",
        batch_output_mode="minimal",
        enable_selective_refine=True,
        refine_confidence_threshold=0.71,
        max_refine_candidates=3,
        use_execution_cache=False,
        enable_pack_probe=True,
        rule_set_key="luxian_0609",
        evaluation_as_of_date="2026-08-16",
        evaluation_horizon_policy="frozen",
        evaluation_horizon_unavailable_reason="none",
        cancellation_check=cancellation_check,
        execution_trace_sink=trace_sink,
    )

    assert result == {"facade": "ok"}
    assert captured == {
        "host": service,
        "bundle": bundle,
        "rule_ids": ["LX0609-11-01-01"],
        "bucket_strategy": "domain_family",
        "quality_profile": "effect_priority_v1",
        "batch_output_mode": "minimal",
        "enable_selective_refine": True,
        "refine_confidence_threshold": 0.71,
        "max_refine_candidates": 3,
        "use_execution_cache": False,
        "enable_pack_probe": True,
        "rule_set_key": "luxian_0609",
        "evaluation_as_of_date": "2026-08-16",
        "evaluation_horizon_policy": "frozen",
        "evaluation_horizon_unavailable_reason": "none",
        "cancellation_check": cancellation_check,
        "execution_trace_sink": trace_sink,
    }


def test_load_running_final_bundle_should_use_scene_bundle_auto_refresh(monkeypatch):
    monkeypatch.setattr(runtime_module, "engine", object())

    calls = []

    def _fake_load_or_assemble_scene_bundle(**kwargs):
        calls.append(dict(kwargs))
        return {
            "scene": "final",
            "visit_id": "V001",
            "medical_text": "病历正文",
            "structured_context": {"documents": {"consultation_record": [{"text_preview": "会诊正文"}]}},
            "document_hits": {"consultation_record": True},
            "data_quality_flags": [],
            "source_doc_priority": ["consultation_record"],
            "text_available": True,
            "bundle_schema_version": "bundle-v2",
        }

    monkeypatch.setattr(runtime_module, "load_or_assemble_scene_bundle", _fake_load_or_assemble_scene_bundle)

    bundle = runtime_module.load_running_final_bundle(
        scene="final",
        institute_id="HOSP-001",
        patient_id="PAT-001",
        visit_id="V001",
        schema="public",
    )

    assert bundle["document_hits"]["consultation_record"] is True
    assert calls == [
        {
            "scene": "final",
            "institute_id": "HOSP-001",
            "patient_id": "PAT-001",
            "visit_id": "V001",
            "bundle_schema": "public",
            "force_refresh": False,
            "force_refresh_if_empty": True,
        }
    ]


@pytest.mark.asyncio
async def test_running_final_bundle_should_drive_orchestrator_with_evidence(monkeypatch):
    service = SichuanQCService()

    fake_eval_args = {
        "document_id": "V001",
        "content": "主文书内容",
        "document_type": "在院病历",
        "rule_ids": ["SC-001"],
        "metadata": {
            "adapter_version": "running-final-adapter-v1",
            "compat_strategy": "bundle-evidence-direct",
        },
        "evidence_payload": {
            "primary_document_text": "主文书内容",
            "supporting_documents": [{"document_type": "病程记录", "evidence_text": "辅助证据"}],
            "timeline_facts": ["2026-04-15 入院"],
            "document_hits": {"admission_record": True},
            "data_quality_flags": [],
        },
    }

    monkeypatch.setattr(
        "app.services.qc_input_adapters.adapt_bundle_to_sichuan_eval_args",
        lambda bundle, rule_ids: fake_eval_args,
    )
    monkeypatch.setattr(
        "app.services.qc_input_adapters.extract_bundle_documents",
        lambda bundle: [
            {
                "id": "V001:first_course_record",
                "document_type": "首次病程记录",
                "source_table": "first_course_record",
                "hit": True,
                "content": "首次病程正文",
            }
        ],
    )

    async def _never_call_evaluate_document(*args, **kwargs):
        raise AssertionError("evaluate_running_final_bundle_input 不应回退到 evaluate_document 旧路径")

    monkeypatch.setattr(service, "evaluate_document", _never_call_evaluate_document)

    called = {}

    async def _fake_evaluate_rules_orchestrated(**kwargs):
        called.update(kwargs)
        return {
            "results": [
                {
                    "rule_id": "SC-001",
                    "rule_name": "测试规则",
                    "is_compliant": True,
                    "status": "compliant",
                    "findings": "合规",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0.9,
                    "applicability": {"is_applicable": True, "reason": "", "method": "default"},
                    "evidence_verified": True,
                    "metadata": {"tokens_used": 0, "api_time": 0.0},
                }
            ],
            "total_tokens": 0,
            "total_api_time": 0.0,
            "executor_breakdown": {"program": 0, "llm": 1, "llm_fallback": 0},
            "cache_breakdown": {"hit": 0, "miss": 1},
            "trace": [],
        }

    monkeypatch.setattr(
        service,
        "get_rule_by_id",
        lambda rid: {
            "rule_id": "SC-001",
            "rule_code": "SC-001",
            "name": "测试规则",
            "applicable_documents": ["首次病程记录"],
        },
    )
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _fake_evaluate_rules_orchestrated)

    result = await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "visit_id": "V001",
            "policy_version": "policy-20260415T000000Z",
            "bundle_schema_version": "bundle-v1",
            "document_hits": {"admission_record": True},
            "text_available": True,
        },
        rule_ids=["SC-001"],
        bucket_strategy="domain_family",
        use_execution_cache=False,
    )

    assert called["evidence_source"] == "bundle"
    assert called["document_type"] == "首次病程记录"
    assert called["content"] == "首次病程正文"
    assert called["bucket_strategy"] == "domain_family"
    assert called["use_execution_cache"] is False
    assert result["total_rules"] == 1
    assert result["bundle_metadata"]["scene"] == "running"
    assert result["bundle_metadata"]["adapter_version"] == "running-final-adapter-v1"


@pytest.mark.asyncio
async def test_runtime_should_forward_effect_priority_options():
    called = {}

    class _Service:
        async def evaluate_running_final_bundle_input(self, **kwargs):
            called.update(kwargs)
            return {"evaluation_results": [], "bundle_metadata": {}}

    result = await evaluate_running_final_bundle(
        qc_service=_Service(),  # type: ignore[arg-type]
        bundle_input={"scene": "final", "visit_id": "V001"},
        rule_ids=["SC-023"],
        bucket_strategy="domain_family",
        quality_profile="effect_priority_v1",
        batch_output_mode="minimal",
        enable_selective_refine=True,
        refine_confidence_threshold=0.75,
        max_refine_candidates=2,
        use_execution_cache=False,
    )

    assert result["bundle_metadata"]["scene"] == "final"
    assert called["rule_ids"] == ["SC-023"]
    assert called["bucket_strategy"] == "domain_family"
    assert called["quality_profile"] == "effect_priority_v1"
    assert called["batch_output_mode"] == "minimal"
    assert called["enable_selective_refine"] is True
    assert called["refine_confidence_threshold"] == 0.75
    assert called["max_refine_candidates"] == 2
    assert called["use_execution_cache"] is False
    assert called["evaluation_as_of_date"] is None


@pytest.mark.asyncio
async def test_runtime_forwards_explicit_frozen_evaluation_as_of_date():
    called = {}

    class _Service:
        async def evaluate_running_final_bundle_input(self, **kwargs):
            called.update(kwargs)
            return {"evaluation_results": [], "bundle_metadata": {}}

    await evaluate_running_final_bundle(
        qc_service=_Service(),  # type: ignore[arg-type]
        bundle_input={"scene": "running", "visit_id": "V001"},
        rule_ids=["LX0609-02-01-04"],
        rule_set_key="luxian_0609",
        evaluation_as_of_date="2026-07-21",
    )

    assert called["evaluation_as_of_date"] == "2026-07-21"


@pytest.mark.asyncio
async def test_public_adapter_forwards_explicit_frozen_evaluation_as_of_date(monkeypatch):
    called = {}

    async def _fake_evaluate(**kwargs):
        called.update(kwargs)
        return {"evaluation_results": []}

    monkeypatch.setattr(runtime_module, "evaluate_running_final_bundle", _fake_evaluate)

    await adapter_module.evaluate_running_final_bundle(
        qc_service=object(),
        bundle_input={"scene": "running", "visit_id": "V001"},
        evaluation_as_of_date="2026-07-21",
    )

    assert called["evaluation_as_of_date"] == "2026-07-21"


@pytest.mark.asyncio
async def test_running_final_bundle_should_split_rules_by_actual_document_type(monkeypatch):
    service = SichuanQCService()

    monkeypatch.setattr(
        "app.services.qc_input_adapters.adapt_bundle_to_sichuan_eval_args",
        lambda bundle, rule_ids: {
            "document_id": "V001",
            "content": "整份病历",
            "document_type": "出院记录",
            "rule_ids": ["SC-023", "SC-123"],
            "metadata": {
                "adapter_version": "running-final-adapter-v1",
                "compat_strategy": "bundle-evidence-direct",
            },
            "evidence_payload": {
                "primary_document_text": "整份病历",
                "supporting_documents": [],
                "timeline_facts": [],
                "document_hits": {"first_course_record": True, "discharge_record": True},
                "data_quality_flags": [],
            },
        },
    )
    monkeypatch.setattr(
        "app.services.qc_input_adapters.extract_bundle_documents",
        lambda bundle: [
            {
                "id": "V001:first_course_record",
                "document_type": "首次病程记录",
                "source_table": "first_course_record",
                "hit": True,
                "content": "首次病程正文",
            },
            {
                "id": "V001:discharge_record",
                "document_type": "出院记录",
                "source_table": "discharge_record",
                "hit": True,
                "content": "出院记录正文",
            },
        ],
    )
    monkeypatch.setattr(
        service,
        "get_rule_by_id",
        lambda rid: {
            "SC-023": {
                "rule_id": "SC-023",
                "rule_code": "SC-023",
                "name": "首次病程记录无病例特点",
                "applicable_documents": ["首次病程记录"],
            },
            "SC-123": {
                "rule_id": "SC-123",
                "rule_code": "SC-123",
                "name": "出院带药不详细",
                "applicable_documents": ["出院记录"],
            },
        }.get(rid),
    )

    calls = []

    async def _fake_evaluate_rules_orchestrated(**kwargs):
        calls.append(
            {
                "document_type": kwargs["document_type"],
                "rule_ids": [item["rule_id"] for item in kwargs["rules"]],
            }
        )
        return {
            "results": [
                {
                    "rule_id": kwargs["rules"][0]["rule_id"],
                    "rule_name": kwargs["rules"][0]["name"],
                    "is_compliant": False,
                    "status": "non_compliant",
                    "findings": "命中问题",
                    "evidence": "证据",
                    "suggestion": "建议",
                    "confidence": 0.8,
                    "applicability": {"is_applicable": True, "reason": "", "method": "default"},
                    "evidence_verified": True,
                    "metadata": {"tokens_used": 10, "api_time": 1.0},
                }
            ],
            "total_tokens": 10,
            "total_api_time": 1.0,
            "executor_breakdown": {"program": 0, "llm": 1, "llm_fallback": 0},
            "cache_breakdown": {"hit": 0, "miss": 1},
            "pack_metrics": {"total_packs": 1, "avg_pack_size": 1.0, "bucket_count": 1},
            "refine_summary": {"enabled": False, "candidate_count": 0, "refined_rule_count": 0, "refine_failed_count": 0, "refine_reasons": {}},
            "trace": [],
        }

    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _fake_evaluate_rules_orchestrated)

    result = await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "final",
            "visit_id": "V001",
            "document_hits": {"first_course_record": True, "discharge_record": True},
            "text_available": True,
        },
        rule_ids=["SC-023", "SC-123"],
        bucket_strategy="domain_family",
        use_execution_cache=False,
    )

    assert calls == [
        {"document_type": "首次病程记录", "rule_ids": ["SC-023"]},
        {"document_type": "出院记录", "rule_ids": ["SC-123"]},
    ]
    assert result["total_rules"] == 2
    assert result["evaluation_summary"]["issues_found"] == 2


@pytest.mark.asyncio
async def test_selective_refine_should_respect_budget_and_skip_review_rules(monkeypatch):
    service = SichuanQCService()
    rules = [
        service._ensure_rule_execution_meta(
            {
                "rule_id": "SC-023",
                "rule_code": "SC-023",
                "name": "首次病程记录无病例特点",
                "defect_level": "严重缺陷",
            }
        ),
        service._ensure_rule_execution_meta(
            {
                "rule_id": "SC-033",
                "rule_code": "SC-033",
                "name": "病程记录中对病情变化无分析判断或无具体处理意见",
                "defect_level": "一般缺陷",
            }
        ),
        service._ensure_rule_execution_meta(
            {
                "rule_id": "SC-121",
                "rule_code": "SC-121",
                "name": "诊疗经过不全面、不详细",
                "defect_level": "一般缺陷",
            }
        ),
    ]
    orchestrated = {
        "results": [
            {
                "rule_id": "SC-023",
                "rule_name": "首次病程记录无病例特点",
                "status": "uncertain",
                "is_compliant": False,
                "findings": "待复核",
                "evidence": "病例特点：……",
                "suggestion": "建议复核",
                "confidence": 0.42,
                "metadata": {},
            },
            {
                "rule_id": "SC-033",
                "rule_name": "病程记录中对病情变化无分析判断或无具体处理意见",
                "status": "uncertain",
                "is_compliant": False,
                "findings": "待复核",
                "evidence": "今日治疗同前……",
                "suggestion": "建议复核",
                "confidence": 0.41,
                "metadata": {},
            },
            {
                "rule_id": "SC-121",
                "rule_name": "诊疗经过不全面、不详细",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "命中问题",
                "evidence": "出院记录原文……",
                "suggestion": "建议补充",
                "confidence": 0.43,
                "metadata": {},
            },
        ],
        "total_tokens": 0,
        "total_api_time": 0.0,
    }

    async def _fake_evaluate(rule, medical_record):
        return {
            "rule_id": rule["rule_id"],
            "rule_name": rule["name"],
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "精审命中",
            "evidence": "精审证据",
            "suggestion": "精审建议",
            "confidence": 0.86,
            "metadata": {"tokens_used": 10, "api_time": 1.0},
        }

    monkeypatch.setattr(service.rule_engine, "evaluate", _fake_evaluate)

    refined = await service._apply_selective_refine(
        orchestrated=orchestrated,
        rules=rules,
        medical_record={"content": "测试病历"},
        refine_confidence_threshold=0.75,
        max_refine_candidates=1,
    )

    summary = dict(refined.get("refine_summary") or {})
    assert summary["candidate_count"] == 3
    assert summary["eligible_candidate_count"] == 2
    assert summary["budget_applied"] == 1
    assert summary["budget_skipped_count"] == 1
    assert summary["refined_rule_count"] == 1
    results_by_rule = {item["rule_id"]: item for item in refined.get("results") or []}
    assert bool((results_by_rule["SC-023"].get("metadata") or {}).get("refined")) is False
    refined_rules = [
        rule_id
        for rule_id, item in results_by_rule.items()
        if bool((item.get("metadata") or {}).get("refined")) is True
    ]
    assert len(refined_rules) == 1
    assert refined_rules[0] in {"SC-033", "SC-121"}
