from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from scripts.review_luxian_0609_semantic20 import (
    SemanticReviewContractError,
    build_semantic20_review,
)


RULE_COUNTS = {
    "LX0609-017": 20,
    "LX0609-020": 14,
    "LX0609-021": 16,
    "LX0609-022": 16,
    "LX0609-023": 14,
}


def _case_map() -> dict:
    return {
        "schema_version": "lx0609-preproduction-benchmark20-case-map-v1",
        "selector_version": "semantic-review-test-v1",
        "cases": [
            {
                "case_label": f"case-{index:02d}",
                "scene": "running",
                "institute_id": f"hospital-{index}",
                "patient_id": f"patient-{index}",
                "visit_id": f"visit-{index}",
            }
            for index in range(1, 21)
        ],
    }


def _candidate() -> dict:
    return {
        "schema_version": "candidate-v1",
        "rows": [
            {
                "case_label": f"case-{case_index:02d}",
                "selector_digest": "a" * 64,
                "rule_id": f"LX0609-{rule_index:03d}",
                "observed_state": "data_gap",
                "observed_reason_code": "candidate_reason_marker",
                "evidence_ref_hashes": ["b" * 64],
                "review_status": "pending",
                "decision_kind": "semantic",
            }
            for case_index in range(1, 21)
            for rule_index in range(1, 50)
        ],
    }


def _review_queue() -> list[dict]:
    rows: list[dict] = []
    for rule_id, count in RULE_COUNTS.items():
        rows.extend(
            {
                "case_label": f"case-{index:02d}",
                "rule_id": rule_id,
                "expected_state": "",
                "expected_reason_code": "",
                "reviewer_code": "review-B",
                "review_status": "needs_second_review",
            }
            for index in range(1, count + 1)
        )
    return rows


class _Client:
    def __init__(
        self, *, confidence: str = "high", invalid: bool = False,
        state: str = "compliant",
    ):
        self.prompts: list[str] = []
        self.confidence = confidence
        self.invalid = invalid
        self.state = state

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        if self.invalid:
            return {
                "choices": [{"message": {"content": "RAW_RESPONSE_SECRET"}}],
                "usage": {"total_tokens": 7},
            }
        selected = re.search(r"本次规则=\[([^]]+)\]", prompt)
        requested = [] if selected is None else selected.group(1).split(",")
        reasons = {
            "LX0609-017": (
                "insufficient_comparable_records"
                if self.state == "not_applicable"
                else "unreasonable_copy_not_established"
            ),
            "LX0609-020": "execution_record_present",
            "LX0609-021": "purpose_clear",
            "LX0609-022": "opinion_clear",
            "LX0609-023": "execution_specific",
        }
        reviews = []
        for rule_id in requested:
            review = {
                "rule_id": rule_id,
                "state": self.state,
                "confidence_bucket": self.confidence,
                "reason_code": reasons[rule_id],
            }
            if rule_id == "LX0609-017" and self.state != "not_applicable":
                review.update(
                    {
                        "substantive_updates": {
                            "symptom": False,
                            "objective": False,
                            "assessment": False,
                            "plan": True,
                        },
                        "template_only_overlap": False,
                        "unreasonable_copy": False,
                    }
                )
            reviews.append(review)
        return {
            "choices": [{"message": {"content": json.dumps({"reviews": reviews})}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }


def _row_loader_factory(calls: list[tuple[str, str]]):
    def _loader(**kwargs):
        source_key = kwargs["source_key"]
        visit_id = kwargs["visit_id"]
        calls.append((visit_id, source_key))
        marker = "PHONE_13800138000_BEARER_SECRET"
        if source_key in {"daily_course_record", "senior_course_record"}:
            shared = "患者今日一般情况稳定，查体及治疗计划如下。" * 20
            suffix = "继续当前治疗。" if source_key == "daily_course_record" else "调整治疗计划。"
            return [{"record_content": shared + suffix + marker, "record_time": "2026-01-01"}]
        return [{"record_content": "会诊申请及会诊意见内容" + marker, "record_time": "2026-01-01"}]

    return _loader


@pytest.mark.asyncio
async def test_review_maps_exact_80_queue_and_rejects_candidate_duplicates_or_missing():
    calls: list[tuple[str, str]] = []
    output = await build_semantic20_review(
        case_map=_case_map(),
        candidate=_candidate(),
        review_queue=_review_queue(),
        llm_client=_Client(),
        row_loader=_row_loader_factory(calls),
    )
    assert output["summary"]["review_count"] == 80
    assert output["summary"]["rule_counts"] == RULE_COUNTS

    duplicate = _candidate()
    duplicate["rows"].append(dict(duplicate["rows"][0]))
    with pytest.raises(SemanticReviewContractError):
        await build_semantic20_review(
            case_map=_case_map(), candidate=duplicate, review_queue=_review_queue(),
            llm_client=_Client(), row_loader=_row_loader_factory([]),
        )
    missing = _candidate()
    missing["rows"] = missing["rows"][1:]
    with pytest.raises(SemanticReviewContractError):
        await build_semantic20_review(
            case_map=_case_map(), candidate=missing, review_queue=_review_queue(),
            llm_client=_Client(), row_loader=_row_loader_factory([]),
        )


@pytest.mark.asyncio
async def test_candidate_state_never_enters_prompt_and_each_case_uses_at_most_two_calls():
    calls: list[tuple[str, str]] = []
    client = _Client()
    output = await build_semantic20_review(
        case_map=_case_map(), candidate=_candidate(), review_queue=_review_queue(),
        llm_client=client, row_loader=_row_loader_factory(calls),
    )
    assert len(client.prompts) <= 40
    assert all("candidate_reason_marker" not in prompt for prompt in client.prompts)
    copy_prompts = [prompt for prompt in client.prompts if "只复核LX0609-017" in prompt]
    assert len(copy_prompts) == 20
    # fake行是生产强高相似终端路径；二审仍必须拿到最佳双文书，而不是空gray_context。
    assert all("PHONE_13800138000_BEARER_SECRET" in prompt for prompt in copy_prompts)
    assert all("略高于70%" not in prompt for prompt in copy_prompts)
    consultation_prompts = [prompt for prompt in client.prompts if "逐张会诊" in prompt]
    assert consultation_prompts
    for business_contract in (
        "笼统‘遵会诊意见’算有执行记录",
        "只看申请段",
        "只看意见段",
        "完全没有执行记录=not_applicable",
        "关联不唯一=evaluation_unknown而不是data_gap",
        "只能返回本次规则列表中的ID",
    ):
        assert all(business_contract in prompt for prompt in consultation_prompts)
    per_case_sources = {}
    for visit_id, source_key in calls:
        per_case_sources.setdefault((visit_id, source_key), 0)
        per_case_sources[(visit_id, source_key)] += 1
    assert max(per_case_sources.values()) == 1
    assert output["usage"]["call_count"] == len(client.prompts)


@pytest.mark.asyncio
async def test_medium_or_low_confidence_is_forced_to_unknown():
    output = await build_semantic20_review(
        case_map=_case_map(), candidate=_candidate(), review_queue=_review_queue(),
        llm_client=_Client(confidence="medium"), row_loader=_row_loader_factory([]),
    )
    copy_rows = [row for row in output["rows"] if row["rule_id"] == "LX0609-017"]
    consultation_rows = [row for row in output["rows"] if row["rule_id"] != "LX0609-017"]
    assert {row["review_state"] for row in copy_rows} == {"compliant"}
    assert {row["review_reason_code"] for row in copy_rows} == {
        "substantive_dynamic_update_present"
    }
    assert {row["review_state"] for row in consultation_rows} == {"evaluation_unknown"}
    assert {row["review_reason_code"] for row in consultation_rows} == {
        "semantic_low_confidence"
    }


@pytest.mark.asyncio
async def test_not_applicable_is_a_valid_high_confidence_review_state():
    output = await build_semantic20_review(
        case_map=_case_map(), candidate=_candidate(), review_queue=_review_queue(),
        llm_client=_Client(state="not_applicable"), row_loader=_row_loader_factory([]),
    )
    assert {row["review_status"] for row in output["rows"]} == {"completed"}
    assert {row["review_state"] for row in output["rows"]} == {"not_applicable"}


@pytest.mark.asyncio
async def test_one_invalid_consultation_rule_does_not_fail_three_valid_rules():
    class MixedClient(_Client):
        changed = False

        async def generate(self, prompt: str) -> dict:
            response = await super().generate(prompt)
            if not self.changed and "LX0609-020" in prompt and "逐张会诊" in prompt:
                payload = json.loads(response["choices"][0]["message"]["content"])
                next(row for row in payload["reviews"] if row["rule_id"] == "LX0609-020")[
                    "state"
                ] = "invalid_state"
                response["choices"][0]["message"]["content"] = json.dumps(payload)
                self.changed = True
            return response

    output = await build_semantic20_review(
        case_map=_case_map(), candidate=_candidate(), review_queue=_review_queue(),
        llm_client=MixedClient(), row_loader=_row_loader_factory([]),
    )
    assert output["summary"]["review_error_count"] == 1
    assert output["summary"]["review_error_reason_counts"] == {"parse_invalid_state": 1}
    first_case = [row for row in output["rows"] if row["case_label"] == "case-01"]
    assert sum(row["review_status"] == "review_error" for row in first_case) == 1
    assert sum(row["review_status"] == "completed" for row in first_case) == 4


@pytest.mark.asyncio
async def test_consultation_accepts_complete_json_list_inside_think_fence_and_prose():
    class WrappedListClient(_Client):
        async def generate(self, prompt: str) -> dict:
            response = await super().generate(prompt)
            if "逐张会诊" in prompt:
                payload = json.loads(response["choices"][0]["message"]["content"])
                response["choices"][0]["message"]["content"] = (
                    "<think>internal reasoning withheld</think>前言\n```json\n"
                    + json.dumps(payload["reviews"], ensure_ascii=False)
                    + "\n```\n尾注"
                )
            return response

    output = await build_semantic20_review(
        case_map=_case_map(), candidate=_candidate(), review_queue=_review_queue(),
        llm_client=WrappedListClient(), row_loader=_row_loader_factory([]),
    )
    assert output["summary"]["review_error_count"] == 0
    assert output["summary"]["completed_count"] == 80


@pytest.mark.asyncio
async def test_copy_template_shell_or_dynamic_update_is_synthesized_compliant():
    class CopyFactsClient(_Client):
        def __init__(self, *, template_only: bool, dynamic_update: bool):
            super().__init__(confidence="low")
            self.template_only = template_only
            self.dynamic_update = dynamic_update

        async def generate(self, prompt: str) -> dict:
            response = await super().generate(prompt)
            if "本次规则=[LX0609-017]" in prompt:
                payload = json.loads(response["choices"][0]["message"]["content"])
                row = payload["reviews"][0]
                row["substantive_updates"] = {
                    "symptom": self.dynamic_update,
                    "objective": False,
                    "assessment": False,
                    "plan": False,
                }
                row["template_only_overlap"] = self.template_only
                row["unreasonable_copy"] = True
                row["reason_code"] = "unreasonable_copy_present"
                response["choices"][0]["message"]["content"] = json.dumps(payload)
            return response

    for client in (
        CopyFactsClient(template_only=True, dynamic_update=False),
        CopyFactsClient(template_only=False, dynamic_update=True),
    ):
        output = await build_semantic20_review(
            case_map=_case_map(), candidate=_candidate(), review_queue=_review_queue(),
            llm_client=client, row_loader=_row_loader_factory([]),
        )
        copy_rows = [row for row in output["rows"] if row["rule_id"] == "LX0609-017"]
        assert {row["review_state"] for row in copy_rows} == {"compliant"}


@pytest.mark.asyncio
async def test_invalid_json_is_review_error_and_does_not_echo_raw_response():
    output = await build_semantic20_review(
        case_map=_case_map(), candidate=_candidate(), review_queue=_review_queue(),
        llm_client=_Client(invalid=True), row_loader=_row_loader_factory([]),
    )
    encoded = json.dumps(output, ensure_ascii=False)
    assert output["summary"]["review_error_count"] == 80
    assert {row["review_status"] for row in output["rows"]} == {"review_error"}
    assert "RAW_RESPONSE_SECRET" not in encoded


@pytest.mark.asyncio
async def test_transport_error_is_review_error():
    class FailedClient:
        async def generate(self, prompt: str) -> dict:
            raise RuntimeError("Bearer secret 13800138000")

    output = await build_semantic20_review(
        case_map=_case_map(), candidate=_candidate(), review_queue=_review_queue(),
        llm_client=FailedClient(), row_loader=_row_loader_factory([]),
    )
    assert output["summary"]["review_error_count"] == 80
    assert "13800138000" not in json.dumps(output, ensure_ascii=False)


@pytest.mark.asyncio
async def test_output_is_allowlisted_and_contains_no_raw_body_coordinates_or_prompt():
    output = await build_semantic20_review(
        case_map=_case_map(), candidate=_candidate(), review_queue=_review_queue(),
        llm_client=_Client(), row_loader=_row_loader_factory([]),
    )
    assert set(output) == {"schema_version", "review_version", "rows", "summary", "usage"}
    assert set(output["rows"][0]) == {
        "case_label", "rule_id", "candidate_state", "candidate_reason_code",
        "review_status", "review_state", "review_reason_code", "confidence_bucket",
        "agreement", "evidence_ref_hashes",
    }
    encoded = json.dumps(output, ensure_ascii=False)
    for forbidden in (
        "PHONE_13800138000_BEARER_SECRET", "hospital-", "patient-", "visit-",
        "record_content", "record_time", '"prompt":', '"raw_response":',
    ):
        assert forbidden not in encoded
