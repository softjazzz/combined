import asyncio
import json
from typing import Any

import pytest

from app.services import fast_screen_qc
from app.services.formal_qc_rule_criteria import (
    RULE_CRITERIA_VERSION,
    enrich_rule_with_specific_criteria,
    rule_criteria_metadata,
)
from app.services.fast_screen_qc import (
    EXECUTION_STRATEGY_FAST_SCREEN,
    EXECUTION_STRATEGY_STANDARD,
    get_fast_screen_full_rule_ids,
    get_fast_screen_pack_definitions,
    get_fast_screen_rule_ids,
    normalize_execution_strategy,
)


def test_fast_screen_pack_definitions_should_match_fixed_grouping():
    packs = get_fast_screen_pack_definitions()

    assert [pack.pack_id for pack in packs] == [
        "first_course_features",
        "first_course_reasoning",
        "daily_course_core",
        "discharge_core",
    ]
    assert [list(pack.rule_ids) for pack in packs] == [
        ["SC-023", "SC-024"],
        ["SC-025", "SC-026", "SC-027"],
        ["SC-032", "SC-033", "SC-036"],
        ["SC-121", "SC-122", "SC-123", "SC-125"],
    ]
    assert max(len(pack.rule_ids) for pack in packs) <= 10
    assert tuple(sorted(get_fast_screen_rule_ids())) == tuple(
        sorted(
            [
                "SC-023",
                "SC-024",
                "SC-025",
                "SC-026",
                "SC-027",
                "SC-032",
                "SC-033",
                "SC-036",
                "SC-121",
                "SC-122",
                "SC-123",
                "SC-125",
            ]
        )
    )


def test_high_false_positive_rule_should_be_enriched_with_specific_criteria():
    rule = {
        "rule_id": "SC-121",
        "name": "诊疗经过不全面、不详细",
        "custom_prompt": "检查诊疗经过是否完整。",
        "prompt_version": "custom-v1",
    }

    enriched = enrich_rule_with_specific_criteria(rule)

    assert enriched["rule_criteria_version"] == RULE_CRITERIA_VERSION
    assert RULE_CRITERIA_VERSION in enriched["prompt_version"]
    assert "required_document=discharge_record/出院记录" in enriched["custom_prompt"]
    assert "一审用于候选召回" in enriched["custom_prompt"]
    assert "has_discharge_medication_text=false" in enriched["custom_prompt"]
    assert "检查诊疗经过是否完整" in enriched["custom_prompt"]


def test_sc118_first_pass_criteria_should_keep_discharge_candidates_for_second_pass():
    rule = {
        "rule_id": "SC-118",
        "name": "出院记录缺项或内容错误",
        "custom_prompt": "检查出院记录字段是否完整。",
    }

    enriched = enrich_rule_with_specific_criteria(rule)

    prompt = enriched["custom_prompt"]
    assert "required_section=完整出院记录字段矩阵" in prompt
    assert "不要把 confirmed 条件当作一审硬过滤" in prompt
    assert "保留 qc_review_candidate" in prompt


def test_rule_criteria_metadata_should_expose_required_document_and_fields():
    metadata = rule_criteria_metadata("SC-123")

    assert metadata["rule_criteria_version"] == RULE_CRITERIA_VERSION
    assert metadata["required_document"] == "discharge_record/出院记录"
    assert metadata["required_section"] == "出院带药/出院用药"
    assert metadata["field_matrix_evidence"]["drug_name"] == "required"


def test_fast_screen_pack_definitions_should_filter_by_rule_ids():
    packs = get_fast_screen_pack_definitions(["SC-024", "SC-026", "SC-123"])

    assert [pack.pack_id for pack in packs] == [
        "first_course_features",
        "first_course_reasoning",
        "discharge_core",
    ]
    assert [list(pack.rule_ids) for pack in packs] == [
        ["SC-024"],
        ["SC-026"],
        ["SC-123"],
    ]


def test_fast_screen_full_rule_ids_should_cover_all_84_intrinsic_rules():
    rule_ids = get_fast_screen_full_rule_ids()

    assert len(rule_ids) == 84
    assert len(set(rule_ids)) == 84
    assert "SC-004" in rule_ids
    assert "SC-146" in rule_ids


def test_fast_screen_pack_definitions_should_expand_to_full_intrinsic_buckets_when_requested():
    packs = get_fast_screen_pack_definitions(["SC-004", "SC-015", "SC-121", "SC-146"])

    assert [pack.pack_id for pack in packs] == [
        "admission_content_core",
        "admission_consistency_core",
        "discharge_procedure",
        "daily_order_consistency",
    ]
    assert [list(pack.rule_ids) for pack in packs] == [
        ["SC-004"],
        ["SC-015"],
        ["SC-121"],
        ["SC-146"],
    ]


def test_fast_screen_rule_id_normalizer_should_accept_sc146_variants():
    assert fast_screen_qc._normalize_fast_screen_rule_id("SC146") == "SC-146"
    assert fast_screen_qc._normalize_fast_screen_rule_id("sc－146") == "SC-146"
    assert fast_screen_qc._normalize_fast_screen_rule_id(" SC_146 ") == "SC-146"


def test_fast_screen_full_buckets_should_cover_all_rules_without_overlap():
    rule_to_pack: dict[str, str] = {}

    for pack in get_fast_screen_pack_definitions(get_fast_screen_full_rule_ids()):
        for rule_id in pack.rule_ids:
            assert rule_id not in rule_to_pack
            rule_to_pack[rule_id] = pack.pack_id

    assert len(rule_to_pack) == 84


def test_normalize_execution_strategy_should_fall_back_to_standard():
    assert normalize_execution_strategy("fast_screen") == EXECUTION_STRATEGY_FAST_SCREEN
    assert normalize_execution_strategy("FAST_SCREEN") == EXECUTION_STRATEGY_FAST_SCREEN
    assert normalize_execution_strategy("unknown") == EXECUTION_STRATEGY_STANDARD
    assert normalize_execution_strategy(None) == EXECUTION_STRATEGY_STANDARD


def test_targeted_evidence_payload_should_include_sc083_sc019_sc100_contexts():
    docs = [
        {"id": "1:admission", "document_type": "入院记录", "source_table": "admission_record", "content": "辅助检查：院外CT提示肺部结节。"},
        {"id": "1:first", "document_type": "首次病程记录", "source_table": "first_course_record", "content": "诊断依据：院外CT提示肺部结节。"},
        {"id": "1:exam", "document_type": "检查报告", "source_table": "exam_item_report", "content": "胸部CT报告：肺部结节。"},
        {"id": "1:surg", "document_type": "手术记录", "source_table": "surgery_record", "content": "手术名称：腰椎内固定术，植入椎弓根螺钉。"},
        {"id": "1:disc", "document_type": "术前讨论", "source_table": "presurg_discussion", "content": "参与人员：外科医师讨论。"},
        {"id": "1:bill", "document_type": "费用清单", "source_table": "inpat_bill_item", "content": "一次性内固定材料。"},
        {"id": "1:daily", "document_type": "日常病程记录", "source_table": "daily_course_record", "content": "炎症指标稍高，继续观察。"},
        {"id": "1:order", "document_type": "长期医嘱", "source_table": "inpat_drug_order", "content": "头孢呋辛 静滴 bid。"},
        {"id": "1:discharge", "document_type": "出院记录", "source_table": "discharge_record", "content": "出院诊断：肺部结节。出院带药：阿莫西林胶囊 口服 bid*3天。"},
    ]
    payload = fast_screen_qc._build_evidence_payload(
        primary_document=docs[0],
        all_documents=docs,
        bundle={
            "document_hits": {
                "admission_record": True,
                "first_course_record": True,
                "surgery_record": True,
                "presurg_discussion": True,
                "inpat_bill_item": True,
                "daily_course_record": True,
                "inpat_drug_order": True,
                "discharge_record": True,
            }
        },
        pack_id="surgery_procedure",
        rule_ids=("SC-013", "SC-019", "SC-036", "SC-083", "SC-100", "SC-118"),
    )

    by_rule = {item["rule_id"]: item for item in payload["targeted_evidence_context"]}
    assert {"SC-019", "SC-083", "SC-100"} <= set(by_rule)
    by_applied_rule = fast_screen_qc._targeted_context_by_rule(payload["targeted_evidence_context"])
    assert {"SC-013", "SC-036", "SC-118"} <= set(by_applied_rule)
    assert by_applied_rule["SC-013"]["coverage_flags"]["has_admission_record_source"] is True
    assert by_applied_rule["SC-036"]["coverage_flags"]["has_daily_course_source"] is True
    assert by_applied_rule["SC-118"]["coverage_flags"]["has_discharge_record_source"] is True
    assert by_rule["SC-019"]["coverage_flags"]["has_source_report"] is True
    assert by_rule["SC-019"]["coverage_flags"]["has_admission_record_source"] is True
    assert by_rule["SC-083"]["coverage_flags"]["has_presurg_discussion"] is True
    assert by_rule["SC-100"]["coverage_flags"]["has_surgery_record"] is True
    assert by_rule["SC-100"]["coverage_flags"]["has_consumable_cross_source"] is True
    assert by_rule["SC-100"]["coverage_flags"]["has_barcode_source"] is False
    assert by_rule["SC-100"]["coverage_flags"]["has_implant_trigger"] is True
    assert by_rule["SC-100"]["coverage_flags"]["has_implant_material_record"] is True
    assert by_rule["SC-100"]["coverage_flags"]["has_implant_barcode_source"] is False
    assert by_rule["SC-100"]["coverage_flags"]["implant_detail_completeness"] == "partial"


def test_surgery_context_should_expose_pathology_and_implant_applicability_flags():
    docs = [
        {
            "id": "1915580:surg",
            "document_type": "手术记录",
            "source_table": "surgery_record",
            "content": "胸椎骨折切开复位内固定术，置入椎弓根螺钉6枚，连接棒2根，骨水泥5ml。",
        },
        {
            "id": "1915580:mr",
            "document_type": "手术清单",
            "source_table": "mr_surgery",
            "content": "骨髓穿刺术；胸椎骨折切开复位内固定术。",
        },
    ]

    context = fast_screen_qc._build_surgery_evidence_context(
        all_documents=docs,
        bundle={"document_hits": {"surgery_record": True, "mr_surgery": True}},
    )
    flags = context["coverage_flags"]

    assert flags["has_specimen_or_pathology_trigger"] is True
    assert flags["has_pathology_source"] is False
    assert flags["specimen_pathology_coverage"] == "source_missing"
    assert flags["has_implant_trigger"] is True
    assert flags["has_implant_material_record"] is True
    assert flags["has_implant_barcode_source"] is False
    assert flags["implant_detail_completeness"] == "partial"
    assert "椎弓根螺钉" in context["implant_detail_quote"]


class _FakeFastScreenRuleEngine:
    def __init__(
        self,
        *,
        fail_pack_id: str = "",
        fail_once_pack_id: str = "",
        omit_rule_id: str = "",
        omit_once_rule_ids: set[str] | None = None,
        rule_id_aliases: dict[str, str] | None = None,
    ) -> None:
        self.fail_pack_id = fail_pack_id
        self.fail_once_pack_id = fail_once_pack_id
        self.omit_rule_id = omit_rule_id
        self.omit_once_rule_ids = omit_once_rule_ids or set()
        self.rule_id_aliases = rule_id_aliases or {}
        self.running = 0
        self.max_running = 0
        self.call_order: list[str] = []
        self.call_counts: dict[str, int] = {}
        self.last_rules_by_pack: dict[str, list[dict[str, Any]]] = {}
        self.last_medical_record_by_pack: dict[str, dict[str, Any]] = {}

    def _build_batch_prompt_compact(
        self,
        rules: list[dict[str, Any]],
        medical_record: dict[str, Any],
        **kwargs: Any,
    ) -> tuple[str, int]:
        prompt = json.dumps(
            {
                "rules": [rule.get("rule_id") for rule in rules],
                "content": medical_record.get("content"),
                "evidence_payload": medical_record.get("evidence_payload"),
                "quality_profile": kwargs.get("quality_profile"),
                "batch_output_mode": kwargs.get("batch_output_mode"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return prompt, max(1, len(prompt) // 3)

    async def evaluate_batch_compact(self, *, rules: list[dict[str, Any]], pack_id: str, **kwargs: Any) -> dict[str, Any]:
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        self.call_order.append(pack_id)
        self.call_counts[pack_id] = int(self.call_counts.get(pack_id) or 0) + 1
        self.last_rules_by_pack[pack_id] = [dict(rule) for rule in rules]
        self.last_medical_record_by_pack[pack_id] = dict(kwargs.get("medical_record") or {})
        await asyncio.sleep(0.01)
        self.running -= 1
        if pack_id == self.fail_once_pack_id and self.call_counts[pack_id] == 1:
            raise RuntimeError("mock transient provider failure")
        if pack_id == self.fail_pack_id:
            raise RuntimeError("mock pack failure")
        omit_rule_ids = {self.omit_rule_id} if self.omit_rule_id else set()
        if self.call_counts[pack_id] == 1:
            omit_rule_ids |= self.omit_once_rule_ids
        return {
            "results": [
                {
                    "rule_id": self.rule_id_aliases.get(rule["rule_id"], rule["rule_id"]),
                    "rule_name": rule["name"],
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0.9,
                    "metadata": {
                        "pack_id": pack_id,
                        "pack_size": len(rules),
                        "tokens_used": 10,
                        "prompt_tokens": 8,
                        "completion_tokens": 2,
                        "api_time": 0.01,
                        "first_result_latency": 0.01,
                        "context_tokens_estimate": 100,
                    },
                }
                for rule in rules
                if rule["rule_id"] not in omit_rule_ids
            ],
            "tokens_used": 10 * len(rules),
            "prompt_tokens": 8 * len(rules),
            "completion_tokens": 2 * len(rules),
            "api_time": 0.01,
            "first_result_latency": 0.01,
            "context_tokens_estimate": 100,
            "cot_observation": {},
            "raw_output": json.dumps(
                {
                    "results": [
                        {
                            "rule_id": self.rule_id_aliases.get(rule["rule_id"], rule["rule_id"]),
                            "status": "compliant",
                        }
                        for rule in rules
                        if rule["rule_id"] not in omit_rule_ids
                    ]
                },
                ensure_ascii=False,
            ),
        }


class _FakeFastScreenService:
    def __init__(self, engine: _FakeFastScreenRuleEngine) -> None:
        self.rule_engine = engine
        self.client = type("Client", (), {"model": "mock-model"})()

    def get_rule_by_id(self, rule_id: str) -> dict[str, Any]:
        return {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "name": f"规则{rule_id}",
            "executor_type": "llm",
            "rule_family": "mock",
            "execution_domain": "mock",
            "doc_scope": "primary",
        }

    def _ensure_rule_execution_meta(self, rule: dict[str, Any]) -> dict[str, Any]:
        return dict(rule)

    def _build_bundle_missing_doc_result_item(self, *, rule: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return {
            "rule_id": rule["rule_id"],
            "rule_name": rule["name"],
            "status": "not_applicable",
            "is_compliant": True,
            "metadata": {"pack_id": "", "tokens_used": 0, "api_time": 0},
        }

    def _build_document_evaluation_result(
        self,
        *,
        document_id: str,
        document_type: str,
        rules: list[dict[str, Any]],
        orchestrated: dict[str, Any],
    ) -> dict[str, Any]:
        results = list(orchestrated.get("results") or [])
        return {
            "document_id": document_id,
            "document_type": document_type,
            "total_rules": len(rules),
            "evaluation_results": results,
            "parsed_evaluation_results": results,
            "token_usage": {
                "total_tokens": int(orchestrated.get("total_tokens") or 0),
                "prompt_tokens": int(orchestrated.get("total_prompt_tokens") or 0),
                "completion_tokens": int(orchestrated.get("total_completion_tokens") or 0),
            },
            "api_time": float(orchestrated.get("total_api_time") or 0.0),
            "first_result_latency": float(orchestrated.get("first_result_latency") or 0.0),
            "pack_metrics": orchestrated.get("pack_metrics") or {},
            "executor_breakdown": orchestrated.get("executor_breakdown") or {},
            "cache_breakdown": orchestrated.get("cache_breakdown") or {},
            "evaluation_summary": {
                "total_rules": len(rules),
                "issues_found": sum(1 for item in results if item.get("status") == "non_compliant"),
                "not_applicable": sum(1 for item in results if item.get("status") == "not_applicable"),
                "pack_metrics": orchestrated.get("pack_metrics") or {},
            },
        }


def _patch_fast_screen_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fast_screen_qc, "assemble_final_record_bundle", lambda **kwargs: {"scene": "final", "document_hits": {}})
    monkeypatch.setattr(
        fast_screen_qc,
        "_extract_bundle_documents",
        lambda bundle: [
            {"id": "1:admission", "document_type": "入院记录", "source_table": "admission_record", "content": "入院记录正文"},
            {"id": "1:first", "document_type": "首次病程记录", "source_table": "first_course_record", "content": "首次病程正文"},
            {"id": "1:daily", "document_type": "日常病程记录", "source_table": "daily_course_record", "content": "日常病程正文"},
            {"id": "1:discharge", "document_type": "出院记录", "source_table": "discharge_record", "content": "出院记录正文"},
        ],
    )


def _patch_fast_screen_bundle_with_anchor_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        fast_screen_qc,
        "assemble_final_record_bundle",
        lambda **kwargs: {
            "scene": "final",
            "document_hits": {"admission_record": True},
            "structured_context": {
                "documents": {
                    "admission_record": [
                        {
                            "history_of_present_illness": "患者1小时前外伤致左手疼痛出血，院外未做处理后急诊入院。"
                        }
                    ]
                }
            },
        },
    )
    monkeypatch.setattr(
        fast_screen_qc,
        "_extract_bundle_documents",
        lambda bundle: [
            {"id": "1:admission", "document_type": "入院记录", "source_table": "admission_record", "content": "入院记录正文"},
        ],
    )


@pytest.mark.asyncio
async def test_run_final_fast_screen_pack_concurrency_one_should_keep_stable_order(monkeypatch: pytest.MonkeyPatch):
    _patch_fast_screen_bundle(monkeypatch)
    engine = _FakeFastScreenRuleEngine()
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-004", "SC-023", "SC-032", "SC-121"],
        pack_concurrency=1,
    )

    assert [item["rule_id"] for item in result["evaluation_results"]] == ["SC-004", "SC-023", "SC-032", "SC-121"]
    metrics = result["pack_metrics"]
    assert metrics["execution_mode"] == "serial"
    assert metrics["observed_max_concurrency"] == 1
    assert metrics["total_packs"] == 4


@pytest.mark.asyncio
async def test_run_final_fast_screen_should_execute_packs_concurrently_and_keep_output_order(monkeypatch: pytest.MonkeyPatch):
    _patch_fast_screen_bundle(monkeypatch)
    engine = _FakeFastScreenRuleEngine()
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-004", "SC-023", "SC-032", "SC-121"],
        pack_concurrency=3,
    )

    assert engine.max_running > 1
    assert [item["rule_id"] for item in result["evaluation_results"]] == ["SC-004", "SC-023", "SC-032", "SC-121"]
    metrics = result["pack_metrics"]
    assert metrics["execution_mode"] == "concurrent"
    assert metrics["configured_concurrency"] == 3
    assert metrics["observed_max_concurrency"] > 1
    assert len(metrics["pack_diagnostics"]) == 4


@pytest.mark.asyncio
async def test_run_final_fast_screen_pack_failure_should_only_mark_that_pack_uncertain(monkeypatch: pytest.MonkeyPatch):
    _patch_fast_screen_bundle(monkeypatch)
    engine = _FakeFastScreenRuleEngine(fail_pack_id="first_course_features")
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-004", "SC-023", "SC-032", "SC-121"],
        pack_concurrency=3,
    )

    by_rule = {item["rule_id"]: item for item in result["evaluation_results"]}
    assert by_rule["SC-023"]["status"] == "uncertain"
    assert by_rule["SC-004"]["status"] == "compliant"
    assert by_rule["SC-032"]["status"] == "compliant"
    assert by_rule["SC-121"]["status"] == "compliant"
    assert result["pack_metrics"]["provider_error_count"] == 1
    assert result["pack_metrics"]["retry_count"] == 2
    assert by_rule["SC-023"]["metadata"]["technical_error_internal"] is True
    assert by_rule["SC-023"]["metadata"]["final_decision_source"] == "technical_error_fallback"


@pytest.mark.asyncio
async def test_run_final_fast_screen_pack_transient_failure_should_retry_and_return_success(monkeypatch: pytest.MonkeyPatch):
    _patch_fast_screen_bundle(monkeypatch)
    engine = _FakeFastScreenRuleEngine(fail_once_pack_id="first_course_features")
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-004", "SC-023", "SC-032"],
        pack_concurrency=3,
    )

    by_rule = {item["rule_id"]: item for item in result["evaluation_results"]}
    assert by_rule["SC-023"]["status"] == "compliant"
    assert engine.call_counts["first_course_features"] == 2
    assert result["pack_metrics"]["provider_error_count"] == 0
    assert result["pack_metrics"]["retry_count"] == 1
    assert by_rule["SC-023"]["metadata"]["pack_retry_attempts"] == 1
    assert by_rule["SC-023"]["metadata"]["pack_retry_success"] is True
    assert by_rule["SC-023"]["metadata"]["final_decision_source"] == "batch_retry"


@pytest.mark.asyncio
async def test_run_final_fast_screen_majority_missing_rule_items_should_retry_once(monkeypatch: pytest.MonkeyPatch):
    _patch_fast_screen_bundle(monkeypatch)
    engine = _FakeFastScreenRuleEngine(omit_once_rule_ids={"SC-023", "SC-024"})
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-023", "SC-024"],
        pack_concurrency=3,
    )

    by_rule = {item["rule_id"]: item for item in result["evaluation_results"]}
    assert by_rule["SC-023"]["status"] == "compliant"
    assert by_rule["SC-024"]["status"] == "compliant"
    assert engine.call_counts["first_course_features"] == 2
    assert result["pack_metrics"]["retry_count"] == 1


@pytest.mark.asyncio
async def test_run_final_fast_screen_single_missing_rule_item_should_retry_once(monkeypatch: pytest.MonkeyPatch):
    _patch_fast_screen_bundle(monkeypatch)
    engine = _FakeFastScreenRuleEngine(omit_once_rule_ids={"SC-024"})
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-023", "SC-024"],
        pack_concurrency=3,
    )

    by_rule = {item["rule_id"]: item for item in result["evaluation_results"]}
    assert by_rule["SC-023"]["status"] == "compliant"
    assert by_rule["SC-024"]["status"] == "compliant"
    assert engine.call_counts["first_course_features"] == 2
    assert result["pack_metrics"]["retry_count"] == 1
    assert by_rule["SC-024"]["metadata"]["pack_retry_success"] is True


@pytest.mark.asyncio
async def test_run_final_fast_screen_missing_rule_item_after_retry_should_be_uncertain_without_dropping_rule(monkeypatch: pytest.MonkeyPatch):
    _patch_fast_screen_bundle(monkeypatch)
    engine = _FakeFastScreenRuleEngine(omit_rule_id="SC-024")
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-023", "SC-024"],
        pack_concurrency=3,
    )

    by_rule = {item["rule_id"]: item for item in result["evaluation_results"]}
    assert set(by_rule) == {"SC-023", "SC-024"}
    assert by_rule["SC-023"]["status"] == "uncertain"
    assert by_rule["SC-024"]["status"] == "uncertain"
    assert engine.call_counts["first_course_features"] == 3
    assert result["pack_metrics"]["provider_error_count"] == 0
    assert result["pack_metrics"]["retry_count"] == 2
    assert by_rule["SC-023"]["metadata"]["pack_retry_reason"] == "missing_rule_items"
    assert by_rule["SC-024"]["metadata"]["pack_retry_reason"] == "missing_rule_items"
    assert by_rule["SC-024"]["metadata"]["error_class"] == "missing_rule_items"
    assert by_rule["SC-024"]["metadata"]["raw_output_summary"]


@pytest.mark.asyncio
async def test_run_final_fast_screen_sc146_single_rule_should_accept_rule_id_alias_without_retry(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_fast_screen_bundle(monkeypatch)
    engine = _FakeFastScreenRuleEngine(rule_id_aliases={"SC-146": "SC146"})
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-146"],
        pack_concurrency=1,
    )

    by_rule = {item["rule_id"]: item for item in result["evaluation_results"]}
    metadata = by_rule["SC-146"]["metadata"]
    diagnostic = result["pack_metrics"]["pack_diagnostics"][0]
    assert by_rule["SC-146"]["status"] == "compliant"
    assert engine.call_counts["daily_order_consistency"] == 1
    assert result["pack_metrics"]["retry_count"] == 0
    assert metadata["actual_rule_ids"] == ["SC146"]
    assert metadata["missing_rule_ids"] == []
    assert metadata["sc146_single_rule_strict_json_prompt"] is True
    assert metadata["first_pass_prompt_hash"]
    assert metadata["first_pass_prompt_chars"] > 0
    assert metadata["targeted_evidence_context_hash"]
    assert metadata["targeted_evidence_context_chars"] > 0
    assert diagnostic["raw_output_summary"]


@pytest.mark.asyncio
async def test_run_final_fast_screen_sc146_single_rule_should_inject_strict_json_prompt(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_fast_screen_bundle(monkeypatch)
    engine = _FakeFastScreenRuleEngine()
    service = _FakeFastScreenService(engine)

    await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-146"],
        pack_concurrency=1,
    )

    rules = engine.last_rules_by_pack["daily_order_consistency"]
    assert rules[0]["sc146_single_rule_strict_json_prompt"] is True
    assert "只评估 rule_id=SC-146" in rules[0]["custom_prompt"]
    assert "不得输出 Markdown" in rules[0]["custom_prompt"]


@pytest.mark.asyncio
async def test_run_final_fast_screen_sc146_should_use_compact_evidence_payload(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(fast_screen_qc, "assemble_final_record_bundle", lambda **kwargs: {"scene": "final", "document_hits": {}})
    long_daily = "病程记录：" + ("患者继续治疗，复查检查，调整医嘱。无关长文本。" * 300)
    monkeypatch.setattr(
        fast_screen_qc,
        "_extract_bundle_documents",
        lambda bundle: [
            {"id": "1:daily", "document_type": "日常病程记录", "source_table": "daily_course_record", "content": long_daily},
            {"id": "1:order", "document_type": "长期医嘱", "source_table": "inpat_drug_order", "content": "医嘱：胃复安 静推 一次。"},
            {"id": "1:consult", "document_type": "会诊记录", "source_table": "consultation_record", "content": "会诊意见：继续观察。"},
        ],
    )
    engine = _FakeFastScreenRuleEngine()
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-146"],
        pack_concurrency=1,
    )

    medical_record = engine.last_medical_record_by_pack["daily_order_consistency"]
    payload = medical_record["evidence_payload"]
    metadata = result["evaluation_results"][0]["metadata"]
    assert payload["sc146_compact_evidence_context"] is True
    assert len(medical_record["content"]) < len(long_daily)
    assert metadata["sc146_compact_evidence_context"] is True
    assert metadata["targeted_evidence_context"]["sc146_compact_evidence_context"] is True


@pytest.mark.asyncio
async def test_run_final_fast_screen_should_emit_subitem_anchors_without_changing_parent_rule_count(monkeypatch: pytest.MonkeyPatch):
    _patch_fast_screen_bundle_with_anchor_docs(monkeypatch)
    engine = _FakeFastScreenRuleEngine()
    service = _FakeFastScreenService(engine)

    result = await fast_screen_qc.run_final_fast_screen(
        qc_service=service,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_ids=["SC-009"],
        pack_concurrency=1,
    )

    assert [item["rule_id"] for item in result["evaluation_results"]] == ["SC-009"]
    anchors = result["subitem_anchor_results"]
    assert len(anchors) == 1
    assert anchors[0]["anchor_id"] == "SC-009-trauma-location"
    assert anchors[0]["display_status"] == "needs_review"
    assert anchors[0]["can_show_as_defect"] is False
    assert result["evaluation_results"][0]["metadata"]["subitem_anchor_count"] == 1
    assert result["pack_metrics"]["subitem_anchor_count"] == 1
