"""026关联缺口合同与隔离SQLite保存回读；仅合成事实，无模型/客户PG。"""

import json
from datetime import datetime

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace
from app.services.luxian_0609.tumor_pathology_result_mapping import (
    safe_tumor_pathology_customer_display_facts as sanitize,
    tumor_pathology_customer_fact_status_is_valid as valid,
)
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    envelope_item_from_rule_result,
)

RULE = "LX0609-05-02-01"


def facts(**overrides):
    return {
        "verification_kind": "chemotherapy_order_course_comparison",
        "order_count": 2,
        "field_results": dict.fromkeys(
            ("drug_name", "dose", "route", "time"), "unknown"
        ),
        "missing_order_fields": [],
        "unresolved_event_count": 1,
        **overrides,
    }


@pytest.mark.parametrize("count", [-1, 3, True, False, 1.0, "1", None])
def test_invalid_count_rejected(count):
    raw = facts(unresolved_event_count=count)
    assert sanitize(rule_id=RULE, raw=raw) is None
    assert not valid(rule_id=RULE, status="data_gap", safe_facts=raw)


@pytest.mark.parametrize("order_count", [0, -1, True, 1.0, "2"])
def test_invalid_order_count_rejected(order_count):
    assert sanitize(rule_id=RULE, raw=facts(order_count=order_count)) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"missing_order_fields": ["dose"]},
        {
            "order_count": 1,
            "field_results": {
                "drug_name": "matched",
                "dose": "mismatched",
                "route": "matched",
                "time": "matched",
            },
        },
        {
            "order_count": 1,
            "field_results": {
                "drug_name": "matched",
                "dose": "matched",
                "route": "matched",
                "time": "unknown",
            },
        },
    ],
)
def test_conflicting_association_counts_rejected(changes):
    assert sanitize(rule_id=RULE, raw=facts(**changes)) is None


@pytest.mark.parametrize(
    "state,count,expected",
    [
        ("matched", 0, "compliant"),
        ("mismatched", 0, "non_compliant"),
        ("unknown", 0, "data_gap"),
        ("matched", 1, "data_gap"),
        ("mismatched", 1, "data_gap"),
        ("unknown", 1, "data_gap"),
    ],
)
def test_only_authoritative_status_matches_valid_count(state, count, expected):
    raw = facts(unresolved_event_count=count)
    if count == 0:
        raw["field_results"] = dict.fromkeys(raw["field_results"], "matched")
    raw["field_results"]["dose"] = (
        "unknown" if count > 0 and state == "matched" else state
    )
    safe = sanitize(rule_id=RULE, raw=raw)
    assert safe is not None
    assert safe["unresolved_event_count"] == count
    for status in ("compliant", "non_compliant", "data_gap"):
        assert valid(rule_id=RULE, status=status, safe_facts=safe) is (
            status == expected
        )


def test_legacy_absent_count_and_private_fields_never_create_gap():
    raw = facts(private_patient_text="synthetic private", private_event_id="private")
    del raw["unresolved_event_count"]
    raw["field_results"] = dict.fromkeys(raw["field_results"], "matched")
    safe = sanitize(rule_id=RULE, raw=raw)
    assert set(safe) == {
        "verification_kind",
        "order_count",
        "field_results",
        "missing_order_fields",
    }
    assert valid(rule_id=RULE, status="compliant", safe_facts=safe)
    assert not valid(rule_id=RULE, status="data_gap", safe_facts=safe)


def test_positive_gap_count_does_not_preserve_private_fields():
    safe = sanitize(rule_id=RULE, raw=facts(private_event_id="synthetic-secret"))
    assert safe["unresolved_event_count"] == 1
    assert set(safe) == {
        "verification_kind",
        "order_count",
        "field_results",
        "missing_order_fields",
        "unresolved_event_count",
    }


def assert_sqlite_roundtrip(final):
    """正式保存器INSERT/commit后关闭Session，新Session用生产load_selected读取。"""
    table = workspace._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None
    )
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    item = {
        **final,
        "rule_id": RULE,
        "record_id": "safe-visit",
        "visit_id": "safe-visit",
        "institute_id": "safe-institute",
        "patient_id": "safe-patient",
    }
    try:
        with Session(engine) as write_session:
            store.replace_for_job(
                write_session,
                job_row={
                    "id": "synthetic-association-job",
                    "created_by": "test",
                    "filters_json": json.dumps(
                        {
                            "rule_set_key": "luxian_0609_qc_v1",
                            "rule_set_version": "2026-06-09",
                        }
                    ),
                },
                items=[item],
                now=datetime(2026, 10, 7, 12),
                projector=lambda raw: envelope_item_from_rule_result(
                    raw, hmac_key="synthetic-only"
                ),
                projection_key="synthetic-only",
            )
            write_session.commit()
        with Session(engine) as read_session:
            loaded = store.load_selected(
                read_session,
                root_job_id="synthetic-association-job",
                institute_id="safe-institute",
                patient_id="safe-patient",
                visit_id="safe-visit",
                rule_set_key="luxian_0609_qc_v1",
                rule_set_version="2026-06-09",
            )
        restored = loaded["items"][0]
        assert restored["status"] == final["status"]
        assert restored["reason_code"] == final["reason_code"]
        assert restored["findings"] == final["findings"]
        assert restored["customer_display_facts"] == final["customer_display_facts"]
        assert (
            restored["customer_display_facts"]["unresolved_event_count"]
            == final["customer_display_facts"]["unresolved_event_count"]
        )
    finally:
        engine.dispose()


@pytest.mark.parametrize("status", ["compliant", "data_gap", "non_compliant"])
def test_positive_count_never_allows_all_matched(status):
    raw = facts(
        field_results=dict.fromkeys(("drug_name", "dose", "route", "time"), "matched")
    )
    assert sanitize(rule_id=RULE, raw=raw) is None
    assert not valid(rule_id=RULE, status=status, safe_facts=raw)


@pytest.mark.asyncio
async def test_absent_target_drug_preserves_defect_without_claiming_other_fields_match():
    from test_round2_tumor_dose_discharge_boundaries import execute

    final = await execute(RULE, course="2026-04-26 使用紫杉醇130mg 静滴。")
    assert final["status"] == "non_compliant"
    assert final["reason_code"] == "requirement_violated"
    assert final["customer_display_facts"]["field_results"] == {
        "drug_name": "mismatched",
        "dose": "unknown",
        "route": "unknown",
        "time": "unknown",
    }


@pytest.mark.parametrize(
    "field", ["missing_course_event_count", "unknown_time_event_count"]
)
@pytest.mark.parametrize("count", [-1, True, 1.0, "1", None, 3])
def test_missing_course_and_time_counts_strict(field, count):
    raw = facts(
        unresolved_event_count=0,
        missing_course_event_count=0,
        unknown_time_event_count=0,
    )
    raw[field] = count
    assert sanitize(rule_id=RULE, raw=raw) is None
    assert not valid(rule_id=RULE, status="data_gap", safe_facts=raw)


@pytest.mark.parametrize(
    "changes",
    [
        {"missing_course_event_count": 1},
        {"missing_course_event_count": 1, "unknown_time_event_count": 0},
        {"missing_course_event_count": 1, "unknown_time_event_count": 2},
        {
            "unknown_time_event_count": 1,
            "field_results": dict.fromkeys(
                ("drug_name", "dose", "route", "time"), "matched"
            ),
        },
        {"unknown_time_event_count": 1, "missing_order_fields": ["dose"]},
    ],
)
def test_forged_cause_count_combinations_rejected(changes):
    raw = facts(unresolved_event_count=0, **changes)
    assert sanitize(rule_id=RULE, raw=raw) is None


# 2026-11-08 口径：完整病程中的未记录可独立成立，另一事件时间未知不能掩盖。
@pytest.mark.parametrize("unknown_time,status", [(0, "non_compliant"), (1, "non_compliant")])
def test_missing_course_controlled_cause_preserves_status_precedence(
    unknown_time, status
):
    raw = facts(
        unresolved_event_count=0,
        missing_course_event_count=1,
        unknown_time_event_count=unknown_time,
        private_event_id="synthetic-private",
    )
    raw["field_results"]["drug_name"] = "mismatched"
    safe = sanitize(rule_id=RULE, raw=raw)
    assert safe is not None and "private_event_id" not in safe
    for candidate in ("non_compliant", "compliant", "data_gap"):
        assert valid(rule_id=RULE, status=candidate, safe_facts=safe) is (
            candidate == status
        )


def _legacy_missing_order_with_undated_difference():
    # 05455b87f 已保存事实形状：缺字段提前返回时未写入零确认计数。
    return facts(
        missing_order_fields=["dose"], missing_order_event_count=1,
        unresolved_event_count=0, missing_course_event_count=0, unknown_time_event_count=1,
        field_results={"drug_name": "unknown", "dose": "unknown", "route": "mismatched", "time": "unknown"},
    )


@pytest.mark.parametrize("explicit_count,expected", [(False, "non_compliant"), (True, "data_gap")])
def test_missing_order_new_proof_contract_and_legacy_are_distinct(explicit_count, expected):
    raw = _legacy_missing_order_with_undated_difference()
    if explicit_count:
        raw["confirmed_mismatch_event_count"] = 0
    safe = sanitize(rule_id=RULE, raw=raw)
    assert safe == raw
    # 再次投影也保留显式零，不能回落到 legacy 的全局差异旁路。
    assert sanitize(rule_id=RULE, raw=safe) == safe
    for status in ("compliant", "non_compliant", "data_gap"):
        assert valid(rule_id=RULE, status=status, safe_facts=safe) is (status == expected)


@pytest.mark.parametrize("count", [-1, True, False, 1.0, "0", None, 3])
def test_confirmed_count_remains_strict_and_bounded(count):
    raw = _legacy_missing_order_with_undated_difference()
    raw["confirmed_mismatch_event_count"] = count
    assert sanitize(rule_id=RULE, raw=raw) is None


@pytest.mark.asyncio
async def test_legacy_saved_missing_order_result_is_read_without_rejudgment():
    from test_luxian_0609_chemo_closure import _course, _run

    _, _, final = await _run(_course("2026-04-26 使用奥沙利铂120mg 静滴。"))
    legacy = {
        **final,
        "customer_display_facts": _legacy_missing_order_with_undated_difference(),
        "findings": "已读取 2 条化疗医嘱及对应病程，使用方法记录不一致；药物名称、剂量、用药时间尚无法核对，未能完成全部项目的一致性核对。",
    }
    assert legacy["status"] == "non_compliant"
    # 正式 Canonical INSERT/commit、关闭 Session、新 Session load，原状态/原因/事实/文案不变。
    assert_sqlite_roundtrip(legacy)
    # 同样的无证明事实若来自新执行，既有 Finalizer 必须拒绝发布确定不合规。
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
    )
    new_unproven = {**legacy, "customer_display_facts": {
        **legacy["customer_display_facts"], "confirmed_mismatch_event_count": 0,
    }}
    rejected, handled = finalize_luxian_0609_executor_customer_display_facts(
        result=new_unproven, raw_facts=new_unproven["customer_display_facts"],
    )
    assert handled
    assert (rejected["status"], rejected["reason_code"]) == ("technical_error", "model_invalid_output")
    assert "customer_display_facts" not in rejected
