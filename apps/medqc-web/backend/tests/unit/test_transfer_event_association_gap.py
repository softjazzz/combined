"""072/073 转科触发与多事件关联缺口的最小回归合同。"""

from __future__ import annotations

import pytest

from app.services.luxian_0609.extended_document.transfer_documentation import (
    evaluate_transfer_documentation,
)
from app.services.luxian_0609.continuity_result_mapping import (
    safe_continuity_customer_display_facts,
)
from app.services.luxian_0609.continuity_evidence_selection import (
    bind_transfer_evidence,
)
from test_luxian_0609_native_extended_document_execution import _session


@pytest.mark.parametrize("order_name", ("转入胸外科", "转入ICU", "转入外一科"))
def test_department_transfer_in_order_is_an_applicable_transfer_event(
    order_name: str,
) -> None:
    outcome = evaluate_transfer_documentation(
        rule_id="LX0609-10-02-02",
        nondrug_order_error="",
        transfer_in_error="",
        transfer_out_error="",
        nondrug_order_rows=(
            {
                "order_name": order_name,
                "order_status": "新开",
                "prescribed_datetime": "2025-08-25 16:23:59",
            },
        ),
        transfer_in_rows=({"record_time": "2025-08-25 17:00:00"},),
        transfer_out_rows=({"record_time": "2025-08-25 18:00:00"},),
    )

    assert (outcome.final_state, outcome.reason_code) == (
        "compliant",
        "requirement_satisfied",
    )


@pytest.mark.parametrize(
    "order",
    (
        {"order_name": "拟转入骨科", "order_status": "新开"},
        {"order_name": "拟转科", "order_status": "新开"},
        {"order_name": "转入骨科", "order_status": "已取消"},
        {"order_name": "转科医嘱", "order_status": "作废"},
        {"order_name": "药品转入外科库房", "order_status": "新开"},
        {"order_name": "病案转入内科归档", "order_status": "新开"},
        {"order_name": "其他转入", "order_status": "新开"},
        {"order_name": "未转入ICU", "order_status": "新开"},
        {"order_name": "取消转入ICU", "order_status": "新开"},
        {"order_name": "患者昨日转入ICU继续治疗", "order_status": "新开"},
        {"order_name": "转入ICU", "order_status": "未执行"},
    ),
)
def test_non_final_or_non_clinical_transfer_text_does_not_trigger(
    order: dict[str, str],
) -> None:
    outcome = evaluate_transfer_documentation(
        rule_id="LX0609-10-02-02",
        nondrug_order_error="",
        transfer_in_error="",
        transfer_out_error="",
        nondrug_order_rows=(order,),
        transfer_in_rows=(),
        transfer_out_rows=(),
    )

    assert (outcome.final_state, outcome.reason_code, outcome.display_facts) == (
        "not_applicable",
        "trigger_absent_complete",
        None,
    )


@pytest.mark.parametrize("rule_id", ("LX0609-10-02-01", "LX0609-10-02-02"))
@pytest.mark.parametrize(
    ("order_names", "transfer_in_count", "transfer_out_count"),
    (
        (("转入胸外科", "转入ICU", "转入胸外科"), 2, 1),
        (("转入ICU", "转入外一科"), 1, 0),
    ),
)
def test_multiple_transfer_events_report_count_only_association_gap(
    rule_id: str,
    order_names: tuple[str, ...],
    transfer_in_count: int,
    transfer_out_count: int,
) -> None:
    outcome = evaluate_transfer_documentation(
        rule_id=rule_id,
        nondrug_order_error="",
        transfer_in_error="",
        transfer_out_error="",
        nondrug_order_rows=tuple(
            {
                "order_name": order_name,
                "order_status": "新开",
                "prescribed_datetime": f"2025-08-{13 + index:02d} 08:00:00",
            }
            for index, order_name in enumerate(order_names)
        ),
        transfer_in_rows=tuple({"submit_datetime": None} for _ in range(transfer_in_count)),
        transfer_out_rows=tuple({"submit_datetime": None} for _ in range(transfer_out_count)),
    )

    assert (outcome.final_state, outcome.reason_code) == (
        "data_gap",
        "association_failed",
    )
    assert outcome.display_facts == {
        "failure_kind": "transfer_event_association_gap",
        "transfer_order_count": len(order_names),
        "transfer_in_count": transfer_in_count,
        "transfer_out_count": transfer_out_count,
    }


@pytest.mark.parametrize("rule_id", ("LX0609-10-02-01", "LX0609-10-02-02"))
def test_transfer_event_association_gap_accepts_only_nonnegative_counts(
    rule_id: str,
) -> None:
    raw = {
        "failure_kind": "transfer_event_association_gap",
        "transfer_order_count": 3,
        "transfer_in_count": 2,
        "transfer_out_count": 1,
    }

    assert safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw) == raw


@pytest.mark.parametrize(
    "raw",
    (
        {
            "failure_kind": "transfer_event_association_gap",
            "transfer_order_count": -1,
            "transfer_in_count": 0,
            "transfer_out_count": 0,
        },
        {
            "failure_kind": "transfer_event_association_gap",
            "transfer_order_count": 1,
            "transfer_in_count": 1,
            "transfer_out_count": 1,
        },
        {
            "failure_kind": "transfer_event_association_gap",
            "transfer_order_count": "2",
            "transfer_in_count": 1,
            "transfer_out_count": 0,
        },
        {
            "failure_kind": "transfer_event_association_gap",
            "transfer_order_count": 2,
            "transfer_in_count": True,
            "transfer_out_count": 0,
        },
        {
            "failure_kind": "transfer_event_association_gap",
            "transfer_order_count": 2,
            "transfer_in_count": 1,
            "transfer_out_count": 0,
            "order_id": "must-not-leak",
        },
    ),
)
def test_transfer_event_association_gap_rejects_invalid_or_extra_fields(
    raw: dict[str, object],
) -> None:
    assert (
        safe_continuity_customer_display_facts(rule_id="LX0609-10-02-01", raw=raw)
        is None
    )


def test_multi_event_gap_binds_only_counted_transfer_orders_and_candidate_records() -> None:
    orders = (
        {
            "document_id": "ORDER-ICU",
            "order_name": "转入ICU",
            "order_status": "新开",
            "prescribed_datetime": "2025-08-25 16:23:59",
        },
        {
            "document_id": "ORDER-SURGERY",
            "order_name": "转入外一科",
            "order_status": "新开",
            "prescribed_datetime": "2025-08-26 10:13:04",
        },
        {
            "document_id": "ORDER-UNRELATED",
            "order_name": "普通非药物医嘱",
            "order_status": "新开",
        },
        {
            "document_id": "ORDER-CANCELLED",
            "order_name": "转入骨科",
            "order_status": "已取消",
        },
    )
    transfer_in_rows = (
        {"document_id": "TRANSFER-IN-CANDIDATE", "submit_datetime": None},
    )
    snapshot, materials = _session(
        {
            "inpat_nondrug_order": orders,
            "transfer_in_record": transfer_in_rows,
            "transfer_out_record": (),
        }
    )
    display_facts = {
        "failure_kind": "transfer_event_association_gap",
        "transfer_order_count": 2,
        "transfer_in_count": 1,
        "transfer_out_count": 0,
    }

    binding = bind_transfer_evidence(
        snapshot=snapshot,
        materials=materials,
        nondrug_order_rows=orders,
        transfer_in_rows=transfer_in_rows,
        transfer_out_rows=(),
        display_facts=display_facts,
    )
    selected_ids = {
        row["document_id"]
        for source_key in (
            "inpat_nondrug_order",
            "transfer_in_record",
            "transfer_out_record",
        )
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
        if reference in binding.document_refs
    }

    assert not binding.binding_failed
    assert selected_ids == {
        "ORDER-ICU",
        "ORDER-SURGERY",
        "TRANSFER-IN-CANDIDATE",
    }


def test_single_department_transfer_in_reuses_trigger_for_exact_binding() -> None:
    order = {
        "document_id": "ORDER-ICU",
        "order_name": "转入ICU",
        "order_status": "新开",
        "prescribed_datetime": "2025-08-25 16:23:59",
    }
    transfer_in = {
        "document_id": "TRANSFER-IN",
        "record_time": "2025-08-25 17:00:00",
    }
    transfer_out = {
        "document_id": "TRANSFER-OUT",
        "record_time": "2025-08-25 18:00:00",
    }
    snapshot, materials = _session(
        {
            "inpat_nondrug_order": (order,),
            "transfer_in_record": (transfer_in,),
            "transfer_out_record": (transfer_out,),
        }
    )
    outcome = evaluate_transfer_documentation(
        rule_id="LX0609-10-02-02",
        nondrug_order_error="",
        transfer_in_error="",
        transfer_out_error="",
        nondrug_order_rows=(order,),
        transfer_in_rows=(transfer_in,),
        transfer_out_rows=(transfer_out,),
    )

    binding = bind_transfer_evidence(
        snapshot=snapshot,
        materials=materials,
        nondrug_order_rows=(order,),
        transfer_in_rows=(transfer_in,),
        transfer_out_rows=(transfer_out,),
        display_facts=outcome.display_facts,
    )
    selected_ids = {
        row["document_id"]
        for source_key in (
            "inpat_nondrug_order",
            "transfer_in_record",
            "transfer_out_record",
        )
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
        if reference in binding.document_refs
    }

    assert not binding.binding_failed
    assert selected_ids == {"ORDER-ICU", "TRANSFER-IN", "TRANSFER-OUT"}
