"""手术文书族只绑定实际触发/目标文书的回归。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import pytest
from luxian_0609_anesthesia_test_facts import ExplicitAnesthesiaFactClient

from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_surgery_document_execution import (
    execute_luxian_0609_native_surgery_document_rules,
)


class _NoLlm:
    async def generate(self, **_kwargs: Any) -> str:
        raise AssertionError("typed 手术文书族不得调用 LLM")


def _surgery(document_id: str = "surgery-1") -> dict[str, Any]:
    return {
        "document_id": document_id,
        "surgery_name": "腹腔镜阑尾切除术",
        "surgery_begin_time": datetime(2026, 9, 1, 8, tzinfo=timezone.utc),
        "surgery_end_time": datetime(2026, 9, 1, 9, tzinfo=timezone.utc),
        "surgeon": "医生甲",
        "surgeon_name": "医生甲",
        "anesthesia_method": "全身麻醉",
    }


def _rows_for(rule_id: str) -> dict[str, tuple[Mapping[str, Any], ...]]:
    anesthesia = {
        "document_id": "anesthesia-1",
        "anesthesia_method": "全身麻醉",
        "record_content": "麻醉诱导和复苏记录完整",
    }
    surgery = _surgery("mr-surgery-1")
    pre = {
        "document_id": "pre-1",
        "document_title": "麻醉术前访视记录",
        "record_content": "ASA II级，气道评估正常，禁食已确认，无麻醉史，已评估麻醉风险",
        "anesthetist_sign": "麻醉医生",
        "record_time": datetime(2026, 9, 1, 7, tzinfo=timezone.utc),
    }
    post = {
        "document_id": "post-1",
        "document_title": "麻醉术后访视记录",
        "record_content": "神志清楚，呼吸循环稳定，无麻醉并发症",
        "anesthetist_sign": "麻醉医生",
        "record_time": datetime(2026, 9, 1, 10, tzinfo=timezone.utc),
    }
    consent = {
        "document_id": "consent-1",
        "document_title": "麻醉知情同意书",
        "record_content": "已说明麻醉方式、风险和替代方案",
        "physician_sign": "麻醉医生",
        "physician_sign_datetime": datetime(2026, 9, 1, 7, tzinfo=timezone.utc),
    }
    if rule_id == "LX0609-04-01-01":
        return {
            "surgery_record": (_surgery(),),
            "presurg_summary": (
                {"document_id": "summary-1", "record_content": "拟行腹腔镜阑尾切除术"},
            ),
        }
    if rule_id == "LX0609-11-02-01":
        return {"anesthesia_record": (anesthesia,), "mr_surgery": (surgery,)}
    if rule_id == "LX0609-11-02-02":
        return {
            "anesthesia_record": (anesthesia,),
            "mr_surgery": (surgery,),
            "consent_form": (consent,),
        }
    if rule_id == "LX0609-04-04-01":
        return {
            "anesthesia_record": (anesthesia,),
            "mr_surgery": (surgery,),
            "preane_surveil_record": (pre,),
        }
    if rule_id == "LX0609-04-04-02":
        return {
            "anesthesia_record": (anesthesia,),
            "mr_surgery": (surgery,),
            "preane_surveil_record": (pre,),
            "postane_surveil_record": (post,),
        }
    if rule_id == "LX0609-04-04-03":
        return {"anesthesia_record": (anesthesia,), "mr_surgery": (surgery,)}
    return {"surgery_record": (_surgery("surgery-1"), _surgery("surgery-2"))}


def _session(rule_id: str):
    rows = _rows_for(rule_id)

    def reader(*, source_key: str, **_kwargs: Any) -> SnapshotSourceRows:
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        created_at="2026-09-07T08:00:00+08:00",
        row_reader=reader,
        additional_source_keys=tuple(rows),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rule_id", "expected_materials"),
    (
        ("LX0609-04-01-01", {("surgery_record", "surgery-1"), ("presurg_summary", "summary-1")} ),
        ("LX0609-11-02-01", {("anesthesia_record", "anesthesia-1")} ),
        ("LX0609-11-02-02", {("anesthesia_record", "anesthesia-1"), ("consent_form", "consent-1")} ),
        ("LX0609-04-04-01", {("anesthesia_record", "anesthesia-1"), ("preane_surveil_record", "pre-1")} ),
        ("LX0609-04-04-02", {("anesthesia_record", "anesthesia-1"), ("preane_surveil_record", "pre-1"), ("postane_surveil_record", "post-1")} ),
        ("LX0609-04-04-03", {("anesthesia_record", "anesthesia-1")} ),
        ("LX0609-04-01-02", {("surgery_record", "surgery-1"), ("surgery_record", "surgery-2")} ),
    ),
)
async def test_typed_surgery_document_rules_bind_only_actual_document_refs(
    rule_id: str, expected_materials: set[tuple[str, str]]
) -> None:
    session = _session(rule_id)
    execution = await execute_luxian_0609_native_surgery_document_rules(
        rule_ids=(rule_id,),
        wrapper_rules=({"rule_id": rule_id},),
        evidence_payload=None,
        llm_client=ExplicitAnesthesiaFactClient("precise_complete") if rule_id == "LX0609-04-04-02" else _NoLlm(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=(rule_id,),
    )
    decision = execution.decisions[0]
    coordinate_by_ref: dict[str, tuple[str, str]] = {}
    for source_key in session.materials.safe_summary()["sources"]:
        for ref, row in session.materials.document_rows(source_key, snapshot=session.snapshot):
            document_id = str(row.get("document_id") or row.get("order_id") or "").strip()
            coordinate_by_ref[ref] = (source_key, document_id)
    actual_materials = {
        coordinate_by_ref[ref] for ref in decision.fact_refs if ref in coordinate_by_ref
    }
    assert actual_materials == expected_materials
    if rule_id == "LX0609-04-04-02":
        assert execution.llm_call_count == 1
        assert (execution.prompt_tokens, execution.completion_tokens, execution.total_tokens) == (10, 5, 15)
    else:
        assert execution.llm_call_count == execution.total_tokens == 0
