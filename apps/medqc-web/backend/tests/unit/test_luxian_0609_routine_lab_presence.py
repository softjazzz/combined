"""血尿常规：完整同报告组合、48小时适用条件及可核验转抄。"""

from datetime import datetime, timedelta

import pytest

from app.services.luxian_0609.routine_lab_presence import (
    BLOOD_ITEMS,
    URINE_ITEMS,
    ITEM_SOURCE,
    evaluate_routine_lab_presence,
    safe_routine_lab_facts,
)

START = datetime(2026, 1, 1, 8)
BLOOD = "LX0609-06-03-05"
URINE = "LX0609-06-03-06"


def sources(rule=BLOOD, *, hours=72, report_hours=60):
    when = START + timedelta(hours=report_hours)
    catalog = BLOOD_ITEMS if rule == BLOOD else URINE_ITEMS
    return {
        "inpat_registration": (("admit", {"admission_datetime": START}),),
        "evaluation_context.horizon": (
            (
                "end",
                {
                    "basis": "discharge_date",
                    "horizon_datetime": START + timedelta(hours=hours),
                },
            ),
        ),
        "labtest_master": (
            (
                "master",
                {
                    "test_id": "T1",
                    "report_datetime": when,
                    "labtest_subject": "临检实验室",
                },
            ),
        ),
        ITEM_SOURCE: tuple(
            (
                f"item-{code}",
                {
                    "test_id": "T1",
                    "document_id": f"I-{code}",
                    "item_code": code,
                    "item_name": "*" + name,
                    "result": "1" if rule == BLOOD else "-",
                    "report_time": when,
                },
            )
            for code, name in catalog.items()
        ),
    }


def evaluate(rule=BLOOD, data=None, **kwargs):
    return evaluate_routine_lab_presence(
        rule_id=rule, sources=sources(rule) if data is None else data, **kwargs
    )


@pytest.mark.parametrize("rule,count", [(BLOOD, 24), (URINE, 10)])
def test_full_panel_in_single_report_is_a_pass_even_report_arrives_after_48_hours(
    rule, count
):
    outcome = evaluate(rule)
    assert outcome.status == "compliant"
    assert outcome.facts["matched_item_count"] == count
    assert len(outcome.refs) == count + 1


@pytest.mark.parametrize(
    "delta,status",
    [(-1, "not_applicable"), (0, "not_applicable"), (1, "non_compliant")],
)
def test_more_than_48_hours_is_eligibility_not_report_deadline(delta, status):
    data = sources(hours=48 + delta / 3600)
    data["labtest_master"] = ()
    data[ITEM_SOURCE] = ()
    assert evaluate(data=data).status == status


def test_partial_four_blood_components_do_not_replace_full_panel():
    data = sources()
    data[ITEM_SOURCE] = tuple(
        (ref, row)
        for ref, row in data[ITEM_SOURCE]
        if row["item_code"] in {"AA001", "AA012", "AA013", "AA020"}
    )
    assert evaluate(data=data).status == "data_gap"


@pytest.mark.parametrize("code,value", [("AA084", "Normal"), ("AA081", "+-")])
def test_actual_urine_vendor_qualitative_result_is_valid_only_in_full_report(
    code, value
):
    data = sources(URINE)
    data[ITEM_SOURCE] = tuple(
        (ref, {**row, "result": value} if row["item_code"] == code else row)
        for ref, row in data[ITEM_SOURCE]
    )
    assert evaluate(URINE, data=data).status == "compliant"
    data[ITEM_SOURCE] = tuple(
        (ref, row) for ref, row in data[ITEM_SOURCE] if row["item_code"] == code
    )
    assert evaluate(URINE, data=data).status == "data_gap"


@pytest.mark.parametrize("value", ["Normal", "+-"])
def test_urine_vendor_qualitative_values_cannot_replace_blood_numeric_results(value):
    data = sources()
    ref, row = data[ITEM_SOURCE][0]
    data[ITEM_SOURCE] = ((ref, {**row, "result": value}), *data[ITEM_SOURCE][1:])
    assert evaluate(data=data).status == "data_gap"


def test_results_cannot_be_patched_across_report_ids():
    data = sources()
    rows = list(data[ITEM_SOURCE])
    rows[0] = (rows[0][0], {**rows[0][1], "test_id": "T2"})
    data[ITEM_SOURCE] = rows
    assert evaluate(data=data).status == "data_gap"


@pytest.mark.parametrize(
    "field,value",
    [
        ("result", ""),
        ("result", "待报告"),
        ("item_name", "其他项目"),
        ("report_status", "待审核"),
        ("report_time", None),
        ("document_status", "已作废"),
    ],
)
def test_missing_conflicting_or_pending_component_is_not_a_pass(field, value):
    data = sources()
    rows = list(data[ITEM_SOURCE])
    rows[0] = (rows[0][0], {**rows[0][1], field: value})
    data[ITEM_SOURCE] = rows
    assert evaluate(data=data).status == "data_gap"


def test_component_report_clock_does_not_fall_back_to_record_or_submit_clock():
    data = sources()
    data[ITEM_SOURCE] = [
        (
            ref,
            {
                **row,
                "report_time": None,
                "record_time": row["report_time"],
                "submit_time": row["report_time"],
            },
        )
        for ref, row in data[ITEM_SOURCE]
    ]
    assert evaluate(data=data).status == "data_gap"


def test_duplicate_code_with_conflicting_result_is_not_chosen_by_order():
    data = sources()
    ref, row = data[ITEM_SOURCE][0]
    data[ITEM_SOURCE] = (*data[ITEM_SOURCE], ("other", {**row, "result": "2"}))
    assert evaluate(data=data).status == "data_gap"


def test_future_report_is_not_used_at_frozen_horizon():
    assert evaluate(data=sources(report_hours=73)).status == "non_compliant"


def test_generic_lab_subject_or_specimen_is_not_routine_panel_identity():
    data = sources()
    data[ITEM_SOURCE] = ()
    assert evaluate(data=data).status == "data_gap"


def test_irrelevant_complete_panel_does_not_count_as_blood_routine():
    data = sources()
    data[ITEM_SOURCE] = (
        (
            "lipid",
            {
                "test_id": "T1",
                "item_code": "OTHER",
                "item_name": "胆固醇",
                "result": "1",
                "report_time": START + timedelta(hours=60),
            },
        ),
    )
    assert evaluate(data=data).status == "non_compliant"


@pytest.mark.parametrize(
    "error", ["source_unavailable", "source_truncated", "source_query_failed"]
)
def test_incomplete_source_fails_closed(error):
    assert evaluate(source_error=error).status == "data_gap"


def copy_sources(text, *, rule=BLOOD, clock=None):
    data = sources(rule)
    data["labtest_master"] = ()
    data[ITEM_SOURCE] = ()
    data["admission_record"] = (
        (
            "copy",
            {
                "document_id": "COPY",
                "record_content": text,
                "record_time": clock or START + timedelta(hours=1),
            },
        ),
    )
    return data


@pytest.mark.parametrize(
    "rule,text",
    [
        (BLOOD, "2025-12-31门诊血常规：WBC 5.2，Hb 120。"),
        (URINE, "2025年12月31日门诊尿常规：尿蛋白阴性，尿比重1.020。"),
        (BLOOD, "2025-12-31门诊复查血常规：WBC 5.2。"),
    ],
)
def test_verifiable_outpatient_transcription_is_only_an_inpatient_exception(rule, text):
    outcome = evaluate(rule, copy_sources(text, rule=rule))
    assert outcome.status == "compliant"
    assert outcome.facts["evidence_kind"] == "outpatient_transcription"
    assert outcome.refs == ("copy",)


@pytest.mark.parametrize(
    "text",
    [
        "门诊血常规已查正常。",
        "门诊血常规：WBC 5.2。",
        "2026-01-02门诊血常规：WBC 5.2。",
        "2025-12-31门诊血常规；住院后WBC 5.2。",
    ],
)
def test_unverifiable_transcription_does_not_bypass_missing_data(text):
    assert evaluate(data=copy_sources(text)).status == "data_gap"


def test_followup_plan_is_not_a_completed_outpatient_result():
    assert (
        evaluate(data=copy_sources("建议2025-12-31门诊复查血常规：WBC拟查5.2。")).status
        == "non_compliant"
    )


def test_transcription_after_frozen_horizon_cannot_satisfy_current_result():
    data = copy_sources(
        "2025-12-31门诊血常规：WBC 5.2。", clock=START + timedelta(hours=80)
    )
    assert evaluate(data=data).status == "data_gap"


def test_date_only_horizon_does_not_invent_a_precise_48_hour_boundary():
    data = sources()
    data["evaluation_context.horizon"] = (
        ("end", {"basis": "evaluation_as_of", "horizon_date": "2026-01-03"}),
    )
    assert evaluate(data=data).status == "data_gap"


def test_pub_facts_are_exactly_transported_and_reject_private_or_wrong_types():
    facts = evaluate().facts
    assert safe_routine_lab_facts(BLOOD, facts) == facts
    for bad in (
        {**facts, "source_document_id": "PRIVATE"},
        {**facts, "minimum_stay_hours": True},
        {**facts, "report_time": "2026-01-03"},
    ):
        assert safe_routine_lab_facts(BLOOD, bad) is None


def test_inpatient_result_cannot_be_borrowed_by_outpatient_normal_statement():
    outcome = evaluate(
        data=copy_sources("2025-12-31门诊血常规已查正常，住院后WBC 5.2。")
    )
    assert outcome.status == "data_gap"


@pytest.mark.parametrize(
    "text",
    [
        "2025-12-31门诊尿常规未见结果，血常规白细胞5.2。",
        "2025-12-31门诊尿常规已查，血常规白细胞5.2。",
        "2025-12-31门诊尿常规已查，胸水白细胞5.2。",
    ],
)
def test_outpatient_copy_cannot_borrow_a_later_different_panel(text):
    assert evaluate(URINE, copy_sources(text, rule=URINE)).status == "data_gap"


@pytest.mark.parametrize("state", ["held", "version_review"])
def test_unapproved_copy_document_never_satisfies_result(state):
    data = copy_sources("2025-12-31门诊血常规：WBC 5.2。")
    data["admission_record"] = tuple(
        (ref, {**row, "validation_material_state": state})
        for ref, row in data["admission_record"]
    )
    assert evaluate(data=data).status != "compliant"


@pytest.mark.parametrize(
    "state", ["审核中", "待最终确认", "初审", "unknown", "in_progress"]
)
def test_nonfinal_report_state_is_not_inferred_final_from_numeric_values(state):
    data = sources()
    data[ITEM_SOURCE] = tuple(
        (ref, {**row, "report_status": state}) for ref, row in data[ITEM_SOURCE]
    )
    assert evaluate(data=data).status == "data_gap"


def test_copy_requires_a_resolvable_document_identity():
    data = copy_sources("2025-12-31门诊血常规：WBC 5.2。")
    data["admission_record"] = tuple(
        (ref, {k: v for k, v in row.items() if k != "document_id"})
        for ref, row in data["admission_record"]
    )
    assert evaluate(data=data).status == "data_gap"


async def final_result(
    rule=BLOOD,
    data=None,
    *,
    unavailable=(),
    truncated=(),
    identity=("I", "P", "V"),
    created_at="2026-01-05T12:00:00+08:00",
    frozen_horizon=None,
):
    from app.services.luxian_0609.evidence_snapshot_provider import (
        SnapshotSourceRows,
        build_luxian_0609_evidence_read_session,
    )
    from app.services.luxian_0609.source_evidence_reader import (
        SourceEvidenceUnavailable,
    )
    from app.services.luxian_0609.native_exam_lab_execution import (
        execute_luxian_0609_native_exam_lab_rules,
    )
    from app.services.luxian_0609.decision_binding import (
        bind_and_reduce_luxian_0609_rule_decisions,
    )
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )

    if data is None:
        pure = sources(rule)
        data = {
            source: [row for _, row in rows]
            for source, rows in pure.items()
            if source != "evaluation_context.horizon"
        }
        data["labtest_item_report"] = data[ITEM_SOURCE]
        data["inpat_registration.discharge_horizon"] = [
            {"discharge_datetime": START + timedelta(hours=72)}
        ]

    def reader(**kwargs):
        source = kwargs["source_key"]
        if source in unavailable:
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(
            source_key=source,
            rows=data.get(source, ()),
            truncated=source in truncated,
            limit_rows=5000,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,),
        institute_id=identity[0],
        patient_id=identity[1],
        visit_id=identity[2],
        source_schema=None,
        created_at=created_at,
        evaluation_horizon_policy="authoritative_discharge",
        evaluation_horizon_snapshot=frozen_horizon,
        row_reader=reader,
    )
    execution = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,),
        decision_rule_ids=(rule,),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert execution.llm_call_count == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", [BLOOD, URINE])
async def test_actual_native_binding_and_canonical_roundtrip(rule):
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    result = await final_result(rule)
    assert result["status"] == "compliant"
    loaded = saved_roundtrip(result)
    assert loaded["customer_display_facts"] == result["customer_display_facts"]
    assert len(loaded["evidence"]) >= len(BLOOD_ITEMS if rule == BLOOD else URINE_ITEMS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source",
    [
        "labtest_master",
        "labtest_item_report",
        ITEM_SOURCE,
        "admission_record",
        "inpat_registration",
    ],
)
async def test_actual_source_unavailable_fails_closed(source):
    assert (await final_result(unavailable=(source,)))["status"] == "data_gap"


@pytest.mark.asyncio
async def test_actual_truncated_items_do_not_count_as_complete_panel():
    assert (await final_result(truncated=(ITEM_SOURCE,)))["status"] == "data_gap"


@pytest.mark.asyncio
async def test_actual_noncompliant_and_transcription_roundtrip():
    from test_luxian_0609_death_record_timeliness import saved_roundtrip

    data = {
        "inpat_registration": [{"admission_datetime": START}],
        "inpat_registration.discharge_horizon": [
            {"discharge_datetime": START + timedelta(hours=72)}
        ],
    }
    result = await final_result(data=data)
    assert result["status"] == "non_compliant"
    assert saved_roundtrip(result)["status"] == "non_compliant"
    data["admission_record"] = [
        {
            "document_id": "COPY",
            "record_time": START + timedelta(hours=1),
            "record_content": "2025-12-31门诊血常规：WBC 5.2。",
        }
    ]
    result = await final_result(data=data)
    assert result["status"] == "compliant"
    assert (
        saved_roundtrip(result)["customer_display_facts"]["evidence_kind"]
        == "outpatient_transcription"
    )


def test_new_projection_reads_status_without_expanding_old_projection(monkeypatch):
    from app.services.luxian_0609 import source_evidence_reader as reader
    from test_luxian_0609_source_evidence_reader import _SourceRowsConnection, _Engine

    connection = _SourceRowsConnection(
        [
            {
                "document_id": "D",
                "test_id": "T",
                "item_code": "AA001",
                "report_status": "待审核",
            }
        ]
    )
    monkeypatch.setattr(reader.bundle_assembly, "engine", _Engine(connection))
    monkeypatch.setattr(reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(
        reader.bundle_assembly,
        "_get_table_columns",
        lambda schema, table: [
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "test_id",
            "item_code",
            "report_status",
            "private_extra_field",
        ],
    )
    result = reader.read_luxian_0609_snapshot_source_rows(
        source_key=ITEM_SOURCE,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
    )
    sql, params = connection.calls[0]
    assert result.source_key == ITEM_SOURCE
    assert (
        '"labtest_item_report"' in sql
        and '"report_status"' in sql
        and "private_extra_field" not in sql
    )
    assert all(
        f'"{key}" = :{key}' in sql for key in ("institute_id", "patient_id", "visit_id")
    )
    assert params["limit_rows"] == result.limit_rows + 1
    assert "report_status" not in reader._SNAPSHOT_SOURCE_FIELDS["labtest_item_report"]


@pytest.mark.asyncio
async def test_published_facts_reject_private_identifiers_missing_and_wrong_shapes():
    from app.services.luxian_0609.canonical_result_finalizer import (
        validate_luxian_0609_published_customer_display_facts,
    )

    facts = (await final_result())["customer_display_facts"]
    for bad in (
        None,
        {**facts, "source_document_id": "PRIVATE"},
        {**facts, "minimum_stay_hours": True},
    ):
        with pytest.raises(ValueError, match="解释合同不完整"):
            validate_luxian_0609_published_customer_display_facts(
                rule_id=BLOOD, raw=bad, status="compliant"
            )
