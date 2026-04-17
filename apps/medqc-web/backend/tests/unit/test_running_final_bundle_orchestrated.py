import pytest

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

    async def _never_call_evaluate_document(*args, **kwargs):
        raise AssertionError("evaluate_running_final_bundle_input 不应回退到 evaluate_document 旧路径")

    monkeypatch.setattr(service, "evaluate_document", _never_call_evaluate_document)

    async def _fake_resolve_rules_for_document(*, document_type, rule_ids):
        assert document_type == "在院病历"
        assert rule_ids == ["SC-001"]
        return [{"rule_id": "SC-001", "rule_code": "SC-001", "name": "测试规则"}]

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

    monkeypatch.setattr(service, "_resolve_rules_for_document", _fake_resolve_rules_for_document)
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
    assert called["evidence_payload"]["supporting_documents"][0]["evidence_text"] == "辅助证据"
    assert called["bucket_strategy"] == "domain_family"
    assert called["use_execution_cache"] is False
    assert result["total_rules"] == 1
    assert result["bundle_metadata"]["scene"] == "running"
    assert result["bundle_metadata"]["adapter_version"] == "running-final-adapter-v1"
