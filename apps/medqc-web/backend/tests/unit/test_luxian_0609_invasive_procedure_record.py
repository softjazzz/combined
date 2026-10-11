"""075 有创操作目录与两步抽取协议（院方口径 2026-10-11）。"""

from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.continuity_result_mapping import (
    safe_continuity_customer_display_facts,
)
from app.services.luxian_0609.extended_document.invasive_procedure_record import (
    MAPPING_SCHEMA_VERSION,
    candidate_order_rows,
    front_page_triggers,
    load_invasive_procedure_catalog,
    map_orders_to_invasive_catalog,
)


def test_catalog_contains_the_92_therapeutic_and_interventional_items() -> None:
    catalog = load_invasive_procedure_catalog()

    assert len(catalog) == 92
    assert {"内镜下胃息肉切除术", "经导管肝动脉栓塞术", "血液透析"} <= {item.name for item in catalog}


def test_candidate_orders_keep_only_treatment_exam_surgery_types() -> None:
    rows = (
        {"order_name": "血常规", "order_type": "检验"},
        {"order_name": "引流管护理", "order_type": "护理"},
        {"order_name": "一次性使用吸引引流袋", "order_type": "其他"},
        {"order_name": "胸腔闭式引流术", "order_type": "治疗", "order_status": "作废"},
        {"order_name": "动脉穿刺置管术", "order_type": "治疗", "order_status": "执行"},
        {"order_name": "经纤支镜治疗(止血)", "order_type": "检查"},
        {"order_name": "胸腔闭式引流术", "order_type": "手术"},
        {"order_name": "新类型医嘱", "order_type": ""},
    )

    assert [row["order_name"] for row in candidate_order_rows(rows)] == [
        "动脉穿刺置管术", "经纤支镜治疗(止血)", "胸腔闭式引流术", "新类型医嘱",
    ]


def test_front_page_code_matches_catalog_exactly() -> None:
    triggers = front_page_triggers((
        {"surgery_code": "43.4105", "surgery_begin_datetime": "2026-06-01 00:00:00"},
        {"surgery_code": "32.4100", "surgery_begin_datetime": "2026-06-01 00:00:00"},
    ))

    assert [item.procedure.name for item in triggers] == ["内镜下胃息肉切除术"]


class _RawClient:
    def __init__(self, body) -> None:
        self.body = body

    async def generate(self, prompt, **_kwargs):
        return {
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(self.body)}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }


@pytest.mark.asyncio
async def test_mapping_rejects_ids_outside_catalog() -> None:
    result = await map_orders_to_invasive_catalog(
        ["经胃镜特殊治疗(息肉肿物切除)"],
        _RawClient({"schema_version": MAPPING_SCHEMA_VERSION, "matches": [{"id": "O001", "catalog": "C99"}]}),
    )

    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")


@pytest.mark.asyncio
async def test_mapping_rejects_duplicate_order_ids() -> None:
    result = await map_orders_to_invasive_catalog(
        ["甲", "乙"],
        _RawClient({
            "schema_version": MAPPING_SCHEMA_VERSION,
            "matches": [{"id": "O001", "catalog": "C01"}, {"id": "O001", "catalog": "C02"}],
        }),
    )

    assert result.state == "technical_error"


def test_anesthesia_orders_are_not_candidates() -> None:
    rows = ({"order_name": "腰麻硬膜外联合阻滞", "order_type": "麻醉"},)

    assert candidate_order_rows(rows) == ()


def test_customer_facts_only_accept_catalog_names() -> None:
    facts = {
        "failure_kind": "invasive_procedure_record_missing",
        "procedures": ["胃镜下切了个息肉"],
        "procedure_count": 1,
        "missing_procedures": ["胃镜下切了个息肉"],
    }

    assert safe_continuity_customer_display_facts(rule_id="LX0609-10-03-01", raw=facts) is None
