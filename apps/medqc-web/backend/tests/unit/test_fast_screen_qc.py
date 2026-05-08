import asyncio
from typing import Any

import pytest

from app.services import fast_screen_qc
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


class _FakeFastScreenRuleEngine:
    def __init__(
        self,
        *,
        fail_pack_id: str = "",
        fail_once_pack_id: str = "",
        omit_rule_id: str = "",
        omit_once_rule_ids: set[str] | None = None,
    ) -> None:
        self.fail_pack_id = fail_pack_id
        self.fail_once_pack_id = fail_once_pack_id
        self.omit_rule_id = omit_rule_id
        self.omit_once_rule_ids = omit_once_rule_ids or set()
        self.running = 0
        self.max_running = 0
        self.call_order: list[str] = []
        self.call_counts: dict[str, int] = {}

    async def evaluate_batch_compact(self, *, rules: list[dict[str, Any]], pack_id: str, **kwargs: Any) -> dict[str, Any]:
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        self.call_order.append(pack_id)
        self.call_counts[pack_id] = int(self.call_counts.get(pack_id) or 0) + 1
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
                    "rule_id": rule["rule_id"],
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
    assert result["pack_metrics"]["retry_count"] == 1
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
async def test_run_final_fast_screen_missing_rule_item_should_be_uncertain_without_dropping_rule(monkeypatch: pytest.MonkeyPatch):
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
    assert by_rule["SC-023"]["status"] == "compliant"
    assert by_rule["SC-024"]["status"] == "uncertain"
    assert engine.call_counts["first_course_features"] == 1
    assert result["pack_metrics"]["provider_error_count"] == 0
    assert result["pack_metrics"]["retry_count"] == 0
