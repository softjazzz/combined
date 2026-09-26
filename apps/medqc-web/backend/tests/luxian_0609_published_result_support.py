"""经正式 prepare→原生执行器→聚合发布链生成 LX0609 合法 Canonical 结果。

保存、读取、复核测试用它取得真实执行器发布的产物，而不是手写“看似合法”
的字典。只使用纯程序判定规则与合成来源行，不调用模型、不含患者原文。
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.settings import get_settings
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)

ADMISSION_TIMELINESS_RULE_ID = "LX0609-01-01-01"
RESCUE_TIMELINESS_RULE_ID = "LX0609-09-01-01"
# 因上游会诊申请单来源缺失而暂停；合法发布形态只能是阶段门控 not_executed。
PAUSED_CONSULTATION_RULE_ID = "LX0609-03-01-01"

_ADMISSION_TIMES = {"within": "2026-06-01 20:00:00", "late": "2026-06-02 12:00:00"}
_RESCUE_CONTENT = {
    "within": "抢救结束时间：2026年06月01日 09:00。",
    "late": "抢救结束时间：2026年06月01日 03:00。",
    "end_time_missing": "患者病情危重，予以抢救。",
}


def _rows(*, admission: str, rescue: str) -> dict[str, list[dict[str, Any]]]:
    return {
        "inpat_registration": [{"admission_datetime": "2026-06-01 08:00:00"}],
        "admission_record": [{
            "document_id": "synthetic-admission-1",
            "document_title": "入院记录",
            "record_time": _ADMISSION_TIMES[admission],
            "chief_complaint": "发热3天",
            "history_of_present_illness": "合成现病史。",
            "record_content": "入院记录\n主诉：发热3天\n现病史：合成现病史。",
        }],
        "rescue_record": [{
            "document_id": "synthetic-rescue-1",
            "document_title": "抢救记录",
            "record_time": "2026-06-01 11:00:00",
            "record_content": _RESCUE_CONTENT[rescue],
        }],
    }


async def _publish(
    selected: tuple[str, ...], rows: dict[str, list[dict[str, Any]]], *, visit_id: str,
) -> list[dict[str, Any]]:
    def read(**kwargs: Any) -> SnapshotSourceRows:
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=rows.get(kwargs["source_key"], []),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="synthetic-institute",
        patient_id="synthetic-patient",
        visit_id=visit_id,
        source_schema=None,
        created_at="2026-06-05T12:00:00+08:00",
        evaluation_as_of_date="2026-06-05",
        row_reader=read,
        additional_source_keys=("admission_record", "inpat_registration", "rescue_record"),
    )
    original = luxian_execution.build_luxian_0609_evidence_read_session
    luxian_execution.build_luxian_0609_evidence_read_session = lambda **_kwargs: session
    try:
        _executable, context = await luxian_execution.prepare_luxian_0609_execution(
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
            prepared_rules=[],
            visit_id=visit_id,
            medical_text="",
            evidence_payload=None,
            llm_client=None,
            settings=get_settings(),
            institute_id="synthetic-institute",
            patient_id="synthetic-patient",
            selected_customer_rule_ids=selected,
            evaluation_as_of_date="2026-06-05",
        )
    finally:
        luxian_execution.build_luxian_0609_evidence_read_session = original
    orchestrated = luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id=visit_id,
        model_name="synthetic-no-model",
        evidence_payload={},
    )
    return [dict(item) for item in orchestrated["results"]]


def published_lx0609_items(
    *,
    admission: str = "within",
    rescue: str = "within",
    include_paused_consultation: bool = False,
    visit_id: str = "synthetic-visit",
) -> dict[str, dict[str, Any]]:
    """按规则号返回正式链路发布的结果；admission/rescue 选择合成时间场景。"""

    selected: tuple[str, ...] = (ADMISSION_TIMELINESS_RULE_ID, RESCUE_TIMELINESS_RULE_ID)
    if include_paused_consultation:
        selected = (*selected, PAUSED_CONSULTATION_RULE_ID)
    items = asyncio.run(
        _publish(selected, _rows(admission=admission, rescue=rescue), visit_id=visit_id)
    )
    by_rule = {str(item["rule_id"]): item for item in items}
    assert tuple(by_rule) == selected
    return by_rule
