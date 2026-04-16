from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.services.qc_rule_orchestrator import QCRuleOrchestrator


def _build_rules(count: int) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    for index in range(1, count + 1):
        rules.append(
            {
                "rule_id": f"SC-{index:03d}",
                "rule_code": f"SC-{index:03d}",
                "name": f"规则{index}",
                "description": "测试规则",
                "executor_type": "llm",
                "execution_domain": "course",
                "doc_scope": "primary",
                "rule_version": "v1",
                "prompt_version": "p1",
                "cost_class": "standard",
            }
        )
    return rules


@pytest.mark.asyncio
async def test_batch_compact_should_return_pack_metrics_and_metadata():
    orchestrator = QCRuleOrchestrator()
    rules = _build_rules(6)
    medical_record = {"id": "V001", "content": "病历正文", "document_type": "病程记录"}

    async def _single_llm(rule: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "rule_id": rule["rule_id"],
            "rule_name": rule["name"],
            "status": "compliant",
            "is_compliant": True,
            "findings": "合规",
            "evidence": "",
            "suggestion": "",
            "confidence": 0.9,
            "metadata": {"tokens_used": 12, "api_time": 0.01},
        }

    async def _batch_llm(batch_rules: List[Dict[str, Any]], record: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        results = []
        for rule in batch_rules:
            results.append(
                {
                    "rule_id": rule["rule_id"],
                    "rule_name": rule["name"],
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "合规",
                    "evidence": "病历正文",
                    "suggestion": "",
                    "confidence": 0.88,
                    "metadata": {},
                }
            )
        return {
            "results": results,
            "tokens_used": 120,
            "api_time": 0.6,
            "parse_error": False,
            "missing_rule_ids": [],
            "low_confidence_rule_ids": [],
            "context_tokens_estimate": 888,
        }

    result = await orchestrator.evaluate_rules(
        rules=rules,
        medical_record=medical_record,
        llm_evaluate=_single_llm,
        llm_batch_evaluate=_batch_llm,
        prompt_strategy="batch_compact_v1",
    )

    assert len(result["results"]) == 6
    pack_metrics = result.get("pack_metrics") or {}
    assert int(pack_metrics.get("total_packs") or 0) >= 1
    assert float(pack_metrics.get("avg_pack_size") or 0) >= 1

    first_metadata = (result["results"][0].get("metadata") or {})
    assert first_metadata.get("prompt_strategy") == "batch_compact_v1"
    assert int(first_metadata.get("pack_size") or 0) >= 1
    assert str(first_metadata.get("pack_id") or "").strip() != ""


@pytest.mark.asyncio
async def test_batch_compact_should_fallback_to_single_when_parse_failed():
    orchestrator = QCRuleOrchestrator()
    rules = _build_rules(4)
    medical_record = {"id": "V002", "content": "病历正文", "document_type": "病程记录"}
    single_calls = {"count": 0}

    async def _single_llm(rule: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
        single_calls["count"] += 1
        return {
            "rule_id": rule["rule_id"],
            "rule_name": rule["name"],
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "回退单条执行",
            "evidence": "",
            "suggestion": "建议",
            "confidence": 0.8,
            "metadata": {"tokens_used": 20, "api_time": 0.02},
        }

    async def _batch_llm(batch_rules: List[Dict[str, Any]], record: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "results": [],
            "tokens_used": 10,
            "api_time": 0.05,
            "parse_error": True,
            "missing_rule_ids": [rule["rule_id"] for rule in batch_rules],
            "low_confidence_rule_ids": [],
            "context_tokens_estimate": 666,
        }

    result = await orchestrator.evaluate_rules(
        rules=rules,
        medical_record=medical_record,
        llm_evaluate=_single_llm,
        llm_batch_evaluate=_batch_llm,
        prompt_strategy="batch_compact_v1",
    )

    assert len(result["results"]) == 4
    assert single_calls["count"] == 4
    pack_metrics = result.get("pack_metrics") or {}
    assert int(pack_metrics.get("pack_parse_retry_count") or 0) >= 1
    assert int(pack_metrics.get("single_rule_retries") or 0) >= 1
    assert int(pack_metrics.get("fallback_packs") or 0) >= 1
    assert any(bool((item.get("metadata") or {}).get("pack_fallback") is True) for item in result["results"])


@pytest.mark.asyncio
async def test_batch_compact_should_probe_pack_size_per_bucket():
    orchestrator = QCRuleOrchestrator()
    medical_record = {"id": "V003", "content": "病历正文", "document_type": "病程记录"}
    rules: List[Dict[str, Any]] = []
    for index in range(1, 7):
        rules.append(
            {
                "rule_id": f"COURSE-{index:03d}",
                "rule_code": f"COURSE-{index:03d}",
                "name": f"病程规则{index}",
                "description": "测试规则",
                "executor_type": "llm",
                "execution_domain": "course",
                "doc_scope": "primary",
                "rule_version": "v1",
                "prompt_version": "p1",
                "cost_class": "standard",
            }
        )
    for index in range(1, 7):
        rules.append(
            {
                "rule_id": f"SURGERY-{index:03d}",
                "rule_code": f"SURGERY-{index:03d}",
                "name": f"手术规则{index}",
                "description": "测试规则",
                "executor_type": "llm",
                "execution_domain": "surgery",
                "doc_scope": "primary",
                "rule_version": "v1",
                "prompt_version": "p1",
                "cost_class": "standard",
            }
        )

    async def _single_llm(rule: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "rule_id": rule["rule_id"],
            "rule_name": rule["name"],
            "status": "compliant",
            "is_compliant": True,
            "findings": "合规",
            "evidence": "",
            "suggestion": "",
            "confidence": 0.9,
            "metadata": {"tokens_used": 10, "api_time": 0.01},
        }

    async def _batch_llm(batch_rules: List[Dict[str, Any]], record: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(options.get("mode") or "")
        domain = str(options.get("execution_domain") or "")
        pack_size = int(options.get("pack_size") or 0)
        if mode == "probe":
            if domain == "surgery" and pack_size >= 5:
                return {
                    "results": [],
                    "tokens_used": 1,
                    "api_time": 0.01,
                    "parse_error": True,
                    "missing_rule_ids": [rule["rule_id"] for rule in batch_rules],
                    "low_confidence_rule_ids": [],
                    "context_tokens_estimate": 300,
                }
            return {
                "results": [
                    {
                        "rule_id": rule["rule_id"],
                        "rule_name": rule["name"],
                        "status": "compliant",
                        "is_compliant": True,
                        "findings": "探测通过",
                        "evidence": "病历正文",
                        "suggestion": "",
                        "confidence": 0.9,
                        "metadata": {},
                    }
                    for rule in batch_rules
                ],
                "tokens_used": 5,
                "api_time": 0.02,
                "parse_error": False,
                "missing_rule_ids": [],
                "low_confidence_rule_ids": [],
                "context_tokens_estimate": 300,
            }

        return {
            "results": [
                {
                    "rule_id": rule["rule_id"],
                    "rule_name": rule["name"],
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "执行通过",
                    "evidence": "病历正文",
                    "suggestion": "",
                    "confidence": 0.9,
                    "metadata": {},
                }
                for rule in batch_rules
            ],
            "tokens_used": 30,
            "api_time": 0.1,
            "parse_error": False,
            "missing_rule_ids": [],
            "low_confidence_rule_ids": [],
            "context_tokens_estimate": 500,
        }

    result = await orchestrator.evaluate_rules(
        rules=rules,
        medical_record=medical_record,
        llm_evaluate=_single_llm,
        llm_batch_evaluate=_batch_llm,
        prompt_strategy="batch_compact_v1",
    )

    assert len(result["results"]) == 12
    course_pack_sizes = {
        int((item.get("metadata") or {}).get("pack_size") or 0)
        for item in result["results"]
        if (item.get("metadata") or {}).get("execution_domain") == "course"
    }
    surgery_pack_sizes = {
        int((item.get("metadata") or {}).get("pack_size") or 0)
        for item in result["results"]
        if (item.get("metadata") or {}).get("execution_domain") == "surgery"
    }
    assert 5 in course_pack_sizes
    assert 3 in surgery_pack_sizes

    pack_metrics = result.get("pack_metrics") or {}
    selected_by_bucket = dict(pack_metrics.get("selected_pack_size_by_bucket") or {})
    assert int(selected_by_bucket.get("course::primary") or 0) == 5
    assert int(selected_by_bucket.get("surgery::primary") or 0) == 3
