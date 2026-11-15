from copy import deepcopy
import pytest
from app.services.custom_qc_workspace_service import project_customer_safe_result_item


def test_old_result_marks_missing_evidence_without_mutation():
    raw={"rule_id":"LX0609-09-01-01","status":"not_applicable","reason_code":"trigger_absent_complete"}
    original=deepcopy(raw)
    result=project_customer_safe_result_item(raw,hmac_key="synthetic-key")
    assert result["audit_evidence_status"]=="not_retained"
    assert result["material_evidence_status"]=="not_retained"
    assert result["status"]=="not_applicable"
    assert raw==original


def test_saved_material_digest_preserved_without_loading_source():
    raw={"rule_id":"LX0609-09-01-01","status":"not_applicable","reason_code":"trigger_absent_complete","case_material_fingerprint":"a"*64}
    result=project_customer_safe_result_item(raw,hmac_key="synthetic-key")
    assert result["case_material_fingerprint"]=="a"*64
    assert result["material_evidence_status"]=="retained"


@pytest.mark.parametrize("bad",["patient/raw-text","A"*64,"a"*63,{},None])
def test_invalid_saved_material_digest_is_rejected(bad):
    with pytest.raises(ValueError):
        project_customer_safe_result_item({"rule_id":"LX0609-09-01-01","status":"not_applicable","reason_code":"trigger_absent_complete","case_material_fingerprint":bad},hmac_key="synthetic-key")


def _receipt_item():
    from tests.unit.test_luxian_0609_applicability_receipt import _case, _reduce
    from app.services.luxian_0609.applicability_receipt import build_applicability_receipt
    snapshot, store, decision = _case()
    receipt = build_applicability_receipt(decision=_reduce(snapshot,store,decision),snapshot=snapshot,materials=store)
    receipt["material_fingerprint"]="b"*64
    return {"rule_id":receipt["rule_id"],"status":"not_applicable","result_status":"not_applicable","reason_code":"trigger_absent_complete","case_material_fingerprint":"b"*64,"applicability_receipt":receipt}


def test_receipt_survives_envelope_and_read_projection_without_identity_leak():
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result
    raw=_receipt_item()
    original=deepcopy(raw)
    saved=envelope_item_from_rule_result(raw,hmac_key="synthetic-key")
    projected=project_customer_safe_result_item(saved,hmac_key="synthetic-key")
    assert projected["applicability_receipt"]==raw["applicability_receipt"]
    assert projected["audit_evidence_status"]=="retained"
    assert projected["material_evidence_status"]=="retained"
    assert raw==original


@pytest.mark.parametrize("change",["rule","material","status","unsafe"])
def test_receipt_mismatch_fails_closed(change):
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result
    raw=_receipt_item()
    if change=="rule":raw["rule_id"]="LX0609-03-01-01"
    if change=="material":raw["case_material_fingerprint"]="c"*64
    if change=="status":raw["status"]="data_gap"
    if change=="unsafe":raw["applicability_receipt"]["raw_text"]="private"
    with pytest.raises(ValueError):envelope_item_from_rule_result(raw,hmac_key="synthetic-key")


def test_saved_pdf_source_does_not_require_current_registration(monkeypatch):
    from starlette.requests import Request
    from app.services import clinical_sources, validation_material_source
    def forbidden(*_args,**_kwargs): pytest.fail("historical view queried current registration")
    monkeypatch.setattr(validation_material_source,"material_source_schema",forbidden)
    def saved(request,job):
        request.state.material_root_job_id=job
        return clinical_sources.legacy_snapshot()
    monkeypatch.setattr(clinical_sources,"source_for_saved_job",saved)
    request=Request({"type":"http","method":"GET","path":"/api/v1/emr/pdfv_V/documents","query_string":b"institute_id=I&patient_id=pdfp_P&visit_id=pdfv_V&job_id=OLD","headers":[]})
    clinical_sources.prepare_request(request)
    assert request.state.material_root_job_id=="OLD"


def test_single_record_saved_text_and_review_dto_keep_audit_markers():
    from app.services.custom_qc_workspace_service import _customer_filtered_saved_text
    from app.routers.records import _map_canonical_item_to_review_item
    raw={"rule_id":"LX0609-03-01-02","status":"not_applicable","conclusion":"无适用事件","reason_code":"trigger_absent_complete"}
    projected=_customer_filtered_saved_text(raw,identity={})
    assert projected["audit_evidence_status"]=="not_retained"
    review=_map_canonical_item_to_review_item(projected,job_id="synthetic",record_id="synthetic",index=0)
    assert review["audit_evidence_status"]=="not_retained"
    assert "audit_evidence_status" not in raw


@pytest.mark.parametrize("tampered",[False,True])
def test_synthetic_saved_envelope_load_validates_receipt(tampered):
    import json
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result, RECORD_RESULT_ENVELOPE_SCHEMA
    from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
    engine=sa.create_engine("sqlite://")
    table=sa.Table("synthetic_envelopes",sa.MetaData(),*[sa.Column(k,sa.String) for k in ("root_job_id","record_id","institute_id","patient_id","visit_id","rule_set_key","rule_set_version","envelope_json")])
    table.create(engine)
    item=envelope_item_from_rule_result(_receipt_item(),hmac_key="synthetic")
    if tampered:item["applicability_receipt"]["raw_error"]="private"
    envelope={"schema_version":RECORD_RESULT_ENVELOPE_SCHEMA,"delivery_mode":CANONICAL_RESULT_DELIVERY_MODE,"record_id":"V","items":[item]}
    with engine.begin() as conn:conn.execute(table.insert().values(root_job_id="J",record_id="V",institute_id="I",patient_id="P",visit_id="V",rule_set_key="S",rule_set_version="1",envelope_json=json.dumps(envelope)))
    with Session(engine) as session:
        def load():return CanonicalResultStore(table).load_selected(session,root_job_id="J",institute_id="I",patient_id="P",visit_id="V",rule_set_key="S",rule_set_version="1")
        if tampered:
            with pytest.raises(ValueError):load()
        else:
            result=load()
            assert result["items"][0]["applicability_receipt"]==item["applicability_receipt"]
    engine.dispose()
