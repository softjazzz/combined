import pytest

from app.services.qc_input_adapters.running_final_bundle_runtime import evaluate_running_final_bundle
from app.services.sichuan_qc_service import SichuanQCService


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
        enable_selective_refine=True,
        refine_confidence_threshold=0.75,
        use_execution_cache=False,
    )

    assert result["bundle_metadata"]["scene"] == "final"
    assert called["rule_ids"] == ["SC-023"]
    assert called["bucket_strategy"] == "domain_family"
    assert called["quality_profile"] == "effect_priority_v1"
    assert called["enable_selective_refine"] is True
    assert called["refine_confidence_threshold"] == 0.75
    assert called["use_execution_cache"] is False


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
