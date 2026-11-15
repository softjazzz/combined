"""诊断辅助投影只使用合成旧表；不连接业务库或运行质控。"""
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.services import case_material_snapshot as material
from app.services import sichuan_qc_service as qc
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable

REF = dict(institute_id="SYN-I", patient_id="SYN-P", visit_id="SYN-V")
DIAG = "institute_id TEXT,patient_id TEXT,visit_id TEXT,diagnosis_no TEXT,diagnosis_type TEXT,diagnosis_code TEXT,diagnosis_name TEXT,dept_name TEXT,diagnosis_datetime TEXT"


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as c:
        c.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
        c.execute(text("CREATE TABLE cdm.diagnosis (" + DIAG + ")"))
        c.execute(text("CREATE TABLE cdm.first_course_record (institute_id TEXT,patient_id TEXT,visit_id TEXT,record_content TEXT)"))
        c.execute(text("INSERT INTO cdm.diagnosis VALUES ('SYN-I','SYN-P','SYN-V','1','主要','SYN','合成诊断','科','2026-01-01'),('SYN-I','PEER','PEER-V','1','主要','SYN','合成诊断','科','2026-01-02')"))
        c.execute(text("INSERT INTO cdm.first_course_record VALUES ('SYN-I','PEER','PEER-V','合成对照正文'),('SYN-I','WRONG','PEER-V','不可混读'),('OTHER','PEER','PEER-V','不可跨机构')"))
    monkeypatch.setattr(qc, "SessionLocal", lambda: Session(engine))
    from app.database import clinical_connection
    from app.services.bundles import assembly
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    yield engine
    engine.dispose()


def peer_args():
    return dict(institute_id=REF["institute_id"],current_patient_id=REF["patient_id"],current_visit_id=REF["visit_id"],dept_name="科",diagnosis_code="SYN",diagnosis_name="合成诊断",limit=10)


def test_legacy_columns_primary_and_peers_keep_exact_identity(database):
    queries = []
    event.listen(database, "before_cursor_execute", lambda c,cur,s,p,ctx,m: queries.append(s))
    assert qc.SichuanQCService._resolve_primary_diagnosis_context(**REF) == {"diagnosis_code":"SYN","diagnosis_name":"合成诊断"}
    peers = qc.SichuanQCService._load_same_disease_first_course_candidates(**peer_args())
    assert [(p["patient_id"],p["record_content"]) for p in peers] == [("PEER","合成对照正文")]
    assert all("main_diag_flag" not in sql and "created_at" not in sql for sql in queries)


@pytest.mark.parametrize("missing", ["diagnosis_type", "diagnosis_no"])
def test_missing_business_columns_are_source_gap(database, missing):
    with database.begin() as c:
        c.execute(text("ALTER TABLE cdm.diagnosis DROP COLUMN " + missing))
    with pytest.raises(SourceEvidenceUnavailable):
        qc.SichuanQCService._resolve_primary_diagnosis_context(**REF)


def test_diagnosis_name_can_supply_existing_name_match_branch(database):
    with database.begin() as c:
        c.execute(text("ALTER TABLE cdm.diagnosis DROP COLUMN diagnosis_code"))
    result = qc.SichuanQCService._resolve_primary_diagnosis_context(**REF)
    assert result == {"diagnosis_code":"", "diagnosis_name":"合成诊断"}
    args = {**peer_args(),"diagnosis_code":""}
    assert len(qc.SichuanQCService._load_same_disease_first_course_candidates(**args)) == 1
    with database.begin() as c:
        c.execute(text("ALTER TABLE cdm.diagnosis DROP COLUMN diagnosis_name"))
    with pytest.raises(SourceEvidenceUnavailable):
        qc.SichuanQCService._resolve_primary_diagnosis_context(**REF)


def test_missing_identity_is_not_downgraded_to_gap(database):
    with database.begin() as c:
        c.execute(text("ALTER TABLE cdm.diagnosis DROP COLUMN patient_id"))
    with pytest.raises(material.MaterialSnapshotError, match="identity_or_source_mismatch"):
        qc.SichuanQCService._resolve_primary_diagnosis_context(**REF)


def test_missing_table_is_gap(database):
    with database.begin() as c:
        c.execute(text("DROP TABLE cdm.diagnosis"))
    with pytest.raises(SourceEvidenceUnavailable):
        qc.SichuanQCService._resolve_primary_diagnosis_context(**REF)


def test_permission_failure_is_not_a_source_gap(database):
    def deny(c, cur, statement, params, context, many):
        if statement.lstrip().startswith("SELECT cdm.diagnosis"):
            raise PermissionError("synthetic denial")
    event.listen(database, "before_cursor_execute", deny)
    with pytest.raises(PermissionError):
        qc.SichuanQCService._resolve_primary_diagnosis_context(**REF)


def test_recorded_gap_replays_without_source_and_keeps_other_material(database, monkeypatch):
    monkeypatch.setattr(material, "source_binding", lambda _: "SYN")
    state = dict(identity=list(REF.values()), binding="SYN", schema="cdm",queries={},
                 columns={"diagnosis":()},tables={"daily_course_record":[{**REF,"record_content":"合成正文"}]})
    with database.connect() as connection:
        state.update(engine=database,connection=connection)
        with material.recording(state), pytest.raises(SourceEvidenceUnavailable):
            qc.SichuanQCService._resolve_primary_diagnosis_context(**REF)
    state.pop("engine");state.pop("connection")
    monkeypatch.setattr(qc, "SessionLocal", lambda: pytest.fail("冻结缺口不能回源"))
    with material.activate(state):
        with pytest.raises(SourceEvidenceUnavailable):
            qc.SichuanQCService._resolve_primary_diagnosis_context(**REF)
        assert material.frozen_rows("cdm","daily_course_record",tuple(REF.values()),1)[0]["record_content"]=="合成正文"


def test_peer_gap_and_empty_diagnosis(database):
    with database.begin() as c:
        c.execute(text("DELETE FROM cdm.diagnosis WHERE patient_id='SYN-P'"))
        c.execute(text("ALTER TABLE cdm.first_course_record DROP COLUMN record_content"))
    assert qc.SichuanQCService._resolve_primary_diagnosis_context(**REF) is None
    with pytest.raises(SourceEvidenceUnavailable):
        qc.SichuanQCService._load_same_disease_first_course_candidates(**peer_args())


def test_old_saved_query_never_reloads_current_source(monkeypatch):
    monkeypatch.setattr(material, "source_binding", lambda _: "SYN")
    monkeypatch.setattr(qc, "SessionLocal", lambda: pytest.fail("历史读取不得连接当前来源"))
    state = dict(identity=list(REF.values()),binding="SYN",schema="cdm",queries={})
    key = material.query_key("_resolve_primary_diagnosis_context",REF,"cdm")
    state["queries"][key] = {"value":{"diagnosis_code":"OLD","diagnosis_name":"历史合成"}}
    with material.activate(state):
        assert qc.SichuanQCService._resolve_primary_diagnosis_context(**REF)["diagnosis_code"] == "OLD"
    assert state["queries"][key]["value"]["diagnosis_code"] == "OLD"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,only_dependent", [(SourceEvidenceUnavailable,False), (PermissionError,False), (SourceEvidenceUnavailable,True)])
async def test_auxiliary_gap_only_blocks_dependent_rule(monkeypatch, failure, only_dependent):
    from types import SimpleNamespace
    from app.services import qc_input_adapters as adapters, sample_programmatic_evidence
    service = qc.SichuanQCService()
    service.client = SimpleNamespace(model="synthetic-no-model")
    docs = [{"id":"D1","source_table":"first_course_record","document_type":"首次病程记录","content":"合成正文"},
            {"id":"D2","source_table":"daily_course_record","document_type":"日常病程记录","content":"合成正文"}]
    ids = ["CL-276"] if only_dependent else ["CL-276","SC-001","SC-002"]
    monkeypatch.setattr(adapters,"adapt_bundle_to_sichuan_eval_args",lambda *a,**k: dict(document_id="SYN-V",document_type="终末病历",content="合成正文",rule_ids=ids,metadata={},evidence_payload={}))
    monkeypatch.setattr(adapters,"extract_bundle_documents",lambda _: docs)
    monkeypatch.setattr(service,"get_rule_by_id",lambda rid: {"rule_id":rid,"name":"合成规则"})
    monkeypatch.setattr(service,"_select_bundle_document_for_rule",lambda *,rule,bundle_documents: docs[1 if rule["rule_id"]=="SC-002" else 0])
    def unavailable(**_):
        raise failure()
    monkeypatch.setattr(service,"_build_same_disease_reasoning_peer_signal",unavailable)
    monkeypatch.setattr(sample_programmatic_evidence,"build_programmatic_evidence_payload",lambda **_: {})
    executed=[]
    async def fake_orchestrator(**kwargs):
        executed.extend(r["rule_id"] for r in kwargs["rules"])
        return {"results":[{"rule_id":r["rule_id"],"status":"compliant","is_compliant":True,"metadata":{}} for r in kwargs["rules"]]}
    monkeypatch.setattr(service,"_evaluate_rules_orchestrated",fake_orchestrator)
    if failure is PermissionError:
        with pytest.raises(PermissionError):
            await service.evaluate_running_final_bundle_input(bundle={"scene":"final"},rule_ids=ids,use_execution_cache=False)
        assert executed==[]
        return
    result=await service.evaluate_running_final_bundle_input(bundle={"scene":"final"},rule_ids=ids,use_execution_cache=False)
    assert executed==([] if only_dependent else ["SC-001","SC-002"])
    assert result["evaluation_summary"]["data_gap_count"]==1
    assert result["total_rules"]==len(ids)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [SourceEvidenceUnavailable, PermissionError, None])
async def test_legacy_rule_handles_gap_before_model(monkeypatch, failure):
    from types import SimpleNamespace
    from app.services.sichuan_qc import legacy_rule_service as legacy
    service = qc.SichuanQCService()
    rule={"rule_id":"CL-276","name":"合成规则"}
    inp=SimpleNamespace(document_type="首次病程记录",source_documents=[{"content":"合成正文"}],to_dict=lambda: {})
    monkeypatch.setattr(service,"get_rule_by_id",lambda _:rule)
    monkeypatch.setattr(service,"_build_rule_execution_input_from_bundle",lambda **_:inp)
    monkeypatch.setattr(service,"_score_primary_candidate_for_rule",lambda **_:1)
    monkeypatch.setattr(legacy,"route_rule_to_domain",lambda _:SimpleNamespace(execution_domain="course",to_dict=lambda: {}))
    monkeypatch.setattr(legacy,"render_rule_execution_medical_text",lambda _:"合成正文")
    monkeypatch.setattr(legacy,"build_evidence_payload_from_rule_input",lambda **_: SimpleNamespace(to_dict=lambda: {}))
    def signal(**_):
        if failure:
            raise failure()
        return [{"signal_type":"same_disease_reasoning_similarity"}]
    monkeypatch.setattr(service,"_build_copy_content_similarity_signals",signal)
    calls=[]
    async def orchestrator(**kwargs):
        calls.append(kwargs)
        return {"results":[{"rule_id":"CL-276","status":"compliant","metadata":{}}]}
    monkeypatch.setattr(service,"_evaluate_rules_orchestrated",orchestrator)
    monkeypatch.setattr(service,"_apply_rule_text_only_fallbacks",lambda **kw:kw["engine_result"])
    args=dict(host=service,load_domain_bundle=lambda **_: {},rule_id="CL-276",**REF)
    if failure is PermissionError:
        with pytest.raises(PermissionError):
            await legacy.evaluate_legacy_rule_for_visit(**args)
        assert calls==[]
        return
    result=await legacy.evaluate_legacy_rule_for_visit(**args)
    assert len(calls)==(1 if failure is None else 0)
    item=result["evaluation_results"][0]
    assert item["status"]==("compliant" if failure is None else "data_gap")
    if failure:
        assert item["is_compliant"] is None and item["reason_code"]=="source_unavailable"
        assert result["token_usage"]["total_tokens"]==0
