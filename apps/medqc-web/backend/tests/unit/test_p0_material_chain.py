"""五类验收必须拒绝中间层丢字段与假通过；不连接业务数据库。"""

import pytest

from app.services.dual_source_sync import SourceSnapshot
from app.services.qc_workspace.material_chain_acceptance import SPECS, check_table_chain, summarize_checks


CASE = {"institute_id": "synthetic-hospital", "patient_id": "synthetic-patient", "visit_id": "synthetic-visit"}
INSTITUTES = {"clinical_data": CASE["institute_id"], "homology": "synthetic-source", "local": CASE["institute_id"]}


def run(spec, row, *, bundles=None, rules=None, local=None, source_status="ok", homology=None):
    raw = {**CASE, spec.key: "synthetic-document", **row}
    doc = {**raw, "source_table": spec.table, "document_id": "synthetic-document", "content": str(raw.get("record_content") or "")}
    return check_table_chain(spec=spec, sample="C18", case=CASE,
        clinical=SourceSnapshot("clinical_data", (raw,), status=source_status),
        homology=SourceSnapshot("homology", tuple(homology or ())),
        local_rows=[raw] if local is None else local, source_institutes=INSTITUTES,
        bundles={key: [doc] for key in ("final", *spec.domains)} if bundles is None else bundles,
        rules={"native": [raw], "snapshot": [raw]} if rules is None else rules)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.table)
def test_all_five_categories_keep_values_across_each_layer(spec):
    row = {field: "合成正文" for field in spec.fields if field != "signature_names"}
    for field in tuple(row):
        if field.endswith("datetime"):
            row[field] = "2026-01-01T10:00:00+08:00"
        if field == "v2_schema":
            row[field] = {"synthetic": "value"}
    if spec.category == "signatures":
        row = {"record_content": "合成病程。 医师签名：甲医生 乙医生"}
    result = run(spec, row)
    assert result["passed"] is True
    assert result["source_nonempty_fields"] > 0


@pytest.mark.parametrize("layer", ["final", "course", "consult_discussion"])
def test_order_time_missing_in_any_bundle_identifies_loss_layer(layer):
    spec = next(spec for spec in SPECS if spec.table == "inpat_drug_order")
    row = {**CASE, "order_id": "synthetic-document", "planned_end_datetime": "2026-01-01T10:00:00+08:00"}
    doc = {**row, "source_table": spec.table, "document_id": "synthetic-document"}
    bundles = {key: [dict(doc)] for key in ("final", *spec.domains)}
    bundles[layer][0].pop("planned_end_datetime")
    result = run(spec, row, bundles=bundles)
    assert not result["passed"]
    assert any(gap["stage"] == "bundle:" + layer and gap["field"] == "planned_end_datetime" for gap in result["gaps"])


def test_missing_transfusion_record_is_not_hidden_by_other_source_rows():
    spec = SPECS[0]
    result = run(spec, {"record_content": "合成输血记录"}, local=[])
    assert any(gap["stage"] == "local_pg" and gap["reason"] == "record_missing" for gap in result["gaps"])


def test_source_read_failure_is_not_counted_as_zero():
    result = run(SPECS[0], {"record_content": "合成输血记录"}, source_status="read_error")
    assert not result["passed"]
    assert result["source_status"]["clinical_data"] == "read_error"


def test_second_body_signature_cannot_be_dropped():
    spec = next(spec for spec in SPECS if spec.table == "senior_course_record")
    raw = {**CASE, "document_id": "synthetic-document", "record_content": "合成病程。 医师签名：甲医生"}
    result = run(spec, {"record_content": "合成病程。 医师签名：甲医生 乙医生"}, rules={"native": [raw], "snapshot": [raw]})
    assert any(gap["stage"] == "rule:native" and gap["field"] == "signature_names" for gap in result["gaps"])


def test_planned_end_cannot_be_replaced_with_stop_time():
    spec = next(spec for spec in SPECS if spec.table == "inpat_drug_order")
    raw = {**CASE, "order_id": "synthetic-document", "stop_time": "2026-01-01T10:00:00+08:00"}
    result = run(spec, {"planned_end_datetime": "2026-01-01T10:00:00+08:00"}, rules={"native": [raw], "snapshot": [raw]})
    assert not result["passed"]


def test_signature_clock_cannot_be_replaced_with_submit_time():
    spec = next(spec for spec in SPECS if spec.table == "discharge_record")
    raw = {**CASE, "document_id": "synthetic-document", "submit_datetime": "2026-01-01T10:00:00+08:00"}
    result = run(spec, {"chief_physician_sign_datetime": "2026-01-01T10:00:00+08:00"}, rules={"native": [raw], "snapshot": [raw]})
    assert not result["passed"]


def test_source_conflict_does_not_disappear_when_local_matches_one_side():
    spec = SPECS[0]
    other = {**CASE, "institute_id": INSTITUTES["homology"], "document_id": "synthetic-document", "record_content": "另一份正文"}
    result = run(spec, {"record_content": "合成输血记录"}, homology=[other])
    assert not result["passed"] and result["conflicts"]


def test_empty_or_incomplete_scope_never_passes():
    assert not summarize_checks([], cases=0)["passed"]
    assert not summarize_checks([run(SPECS[0], {"record_content": "合成输血记录"})], cases=1)["passed"]


def test_empty_values_are_distinguished_from_coverage():
    checks = [run(spec, {}) for spec in SPECS]
    result = summarize_checks(checks, cases=1)
    assert not result["passed"]
    assert not any(category["source_nonempty_fields"] for category in result["categories"].values())


def test_unknown_bundle_shape_is_unavailable():
    spec = SPECS[0]
    result = run(spec, {"record_content": "合成输血记录"}, bundles={"final": None, "course": []})
    assert any(gap["reason"] == "layer_unavailable" for gap in result["gaps"])


def test_declared_display_limit_does_not_hide_rule_reader_loss():
    spec = SPECS[0]
    raw = {**CASE, "document_id": "synthetic-document", "record_content": "合成正文"}
    kwargs = dict(spec=spec, sample="C18", case=CASE,
        clinical=SourceSnapshot("clinical_data", (raw,)), homology=SourceSnapshot("homology"),
        local_rows=[raw], source_institutes=INSTITUTES,
        bundles={"final": [], "course": [dict(raw, source_table=spec.table)]},
        projections={"final": {"is_evidence_source": False, "per_source": {spec.table: {"has_more": True}}}})
    valid = check_table_chain(**kwargs, rules={"native": [raw], "snapshot": [raw]})
    assert valid["passed"] and len(valid["display_projection_omissions"]) == 1
    invalid = check_table_chain(**kwargs, rules={"native": [], "snapshot": [raw]})
    assert not invalid["passed"]


def test_bracket_placeholder_is_not_source_content_coverage():
    result = run(SPECS[0], {"record_content": "[]"})
    assert result["source_nonempty_fields"] == 0
