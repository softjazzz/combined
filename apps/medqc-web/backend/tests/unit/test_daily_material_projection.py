"""日常补充材料：仅合成数据，无模型、源接口或既有数据库。"""
import importlib.util
from types import SimpleNamespace
import pytest


def test_readonly_contract_is_packaged_with_business():
    assert importlib.util.find_spec("app.services.daily_material_readonly") is not None


def test_projection_has_one_shared_owner():
    assert importlib.util.find_spec("app.services.daily_material_projection") is not None


def test_reader_borrows_sqlalchemy_driver_without_transaction_ownership(monkeypatch):
    from app.services import daily_material_readonly as reader
    from app.services import daily_material_projection as projection
    calls = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=None): calls.append(sql)
        def fetchone(self): return ("delivery_cdm_012345abcdef", "on", "repeatable read")
        def fetchall(self):
            if "FROM cdm.daily_course_record" in calls[-1]: return []
            return [(reader.digest(("canonical-I", "P", "V")), {"canonical_case":["canonical-I","P","V"], "native_cases":[["cache","I","P","V"]], "identity_version":"1", "type_version":"1", "rule_version":"1", "approval_id":"synthetic"})]
    driver = SimpleNamespace(cursor=Cursor)
    connection = SimpleNamespace(connection=SimpleNamespace(driver_connection=driver),
        engine=SimpleNamespace(url=SimpleNamespace(host="127.0.0.1", port=55499, database="delivery_cdm_012345abcdef")))
    monkeypatch.setattr(reader, "_read_manifest", lambda cursor, case_id, contract: {"case_id":case_id})
    result = projection.read_manifest(connection, ("I", "P", "V"))
    assert result["case_id"] == reader.digest(("canonical-I", "P", "V"))
    assert result["business_binding"]["policy"]["canonical_case"] == ["canonical-I", "P", "V"]
    assert result["business_binding"]["native_case"] == ["I", "P", "V"]
    assert len(calls) == 3


def test_all_daily_source_readers_use_selected_manifest_and_scope(monkeypatch):
    from contextlib import nullcontext
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material
    from app.services.bundles import assembly
    from app.services.luxian_0609 import source_evidence_reader as reader
    from app.services import sample_programmatic_evidence as programmatic
    from app.services import daily_material_projection as projection
    value = synthetic_manifest()
    state = {"identity":["I","P","V"], "binding":"", "schema":"cdm", "daily_material_manifest":value, "queries":{}, "columns":{"daily_course_record":[]}, "tables":{}, "engine":object(), "connection":SimpleNamespace(begin_nested=nullcontext)}
    monkeypatch.setattr(assembly, "_source_engine", lambda *args: pytest.fail("daily bypassed manifest"))
    args = dict(institute_id="I", patient_id="P", visit_id="V", source_schema="cdm")
    with clinical.selected({"id":"legacy_pg", "binding":""}), material.recording(state):
        native = reader.read_luxian_0609_native_source_rows(source_key="daily_course_record", **args)
        snapshot = reader.read_luxian_0609_snapshot_source_rows(source_key="daily_course_record", **args)
        bundle = assembly._select_records(schema="cdm", table="daily_course_record", institute_id="I", patient_id="P", visit_id="V")
        assert native[0]["version_id"] == snapshot.rows[0]["version_id"] == bundle[0]["version_id"] == "a"
        assert snapshot.rows[0]["record_content"] == "synthetic body"
        assert not projection.permits_absence("daily_course_record")
        assert projection.permits_absence("admission_record")


def synthetic_manifest():
    return {"business_binding":{"policy":{"status_rules":[["clinical",None,"valid"],["cache",None,"valid"]]}}, "contract":"daily-material-r2-v3", "items":[{"version_id":"a", "record_identity":"ra", "native_key":["I","P","V","D"], "source_namespace":"clinical", "source_object":"clinical.public.daily_course_record", "body":"synthetic body", "title":"日常病程", "record_time":"2026-11-01T08:00:00", "selected":True, "rule_usable":True, "native_fields":{"zero":0,"flag":False}, "target_payload":{}}], "fresh":True, "coverage":{}, "can_judge_clinical_absence":False}


def test_scope_survives_snapshot_encoding_including_empty_source_and_affects_identity():
    from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
    from app.services.luxian_0609.evidence_material import build_material_snapshot_ref
    from app.services.luxian_0609.evidence_snapshot import SourceCompleteness
    from app.services.luxian_0609.source_manifest import QueryStatus
    from app.services import case_material_snapshot as material
    scope = {"can_judge_clinical_absence":False, "coverage":{"cache":{"state":"UNKNOWN"}}}
    rows = SnapshotSourceRows.create(source_key="daily_course_record", rows=[], truncated=False, limit_rows=10, material_scope=scope)
    replay = material.decode(material.encode(rows))
    assert replay.material_scope == scope
    args = dict(source_key="daily_course_record", query_version="synthetic", query_state=QueryStatus.EMPTY, completeness=SourceCompleteness.COMPLETE, document_refs=())
    assert build_material_snapshot_ref(**args, material_scope=scope) != build_material_snapshot_ref(**args)


def test_readonly_failures_are_controlled():
    from app.services import daily_material_readonly as reader
    with pytest.raises(reader.IngestError):
        reader.require(False, "synthetic_boundary")
    with pytest.raises(reader.IngestError):
        reader.CasePolicy.from_dict({"canonical_case":["I","P","V"], "native_cases":[], "identity_version":"1", "type_version":"1", "rule_version":"1", "approval_id":"synthetic"})


def test_version_locator_rejects_ambiguous_original_id():
    from app.services import daily_material_projection as projection
    from app.services.bundles.emr_view import pick_document
    from copy import deepcopy
    value = synthetic_manifest()
    duplicate = deepcopy(value["items"][0])
    duplicate.update(version_id="b", record_identity="rb", source_namespace="cache", rule_usable=False, body="other body")
    value["items"].append(duplicate)
    docs = projection.project_documents(value)
    assert pick_document(documents=docs, doc_type="daily_course_record", doc_id="D") is None
    assert pick_document(documents=docs, doc_type="daily_course_record", doc_id=docs[1]["doc_key"])["content"] == "other body"
    assert pick_document(documents=docs, doc_type="daily_course_record", doc_id="daily_course_record::missing::version") is None


def test_manifest_and_confirmation_are_immutable_across_root_retry(monkeypatch, tmp_path):
    from copy import deepcopy
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material
    from app.services import case_material_capture as capture
    from app.services import daily_material_projection as projection
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    value = synthetic_manifest()
    value["confirmation_basis"] = {"a":{"synthetic":False,"zero":0}}
    value["items"][0]["confirmation"] = {"proof":"complete retained proof", "zero":0}
    state = {"protocol":material.PROTOCOL, "identity":["I","P","V"], "binding":"", "schema":"cdm", "queries":{}, "daily_material_manifest":value, "documents":{"documents":projection.project_documents(value)}}
    with clinical.selected({"id":"legacy_pg", "binding":""}):
        first = material.persist("root", state)
        changed = deepcopy(state)
        changed["daily_material_manifest"]["items"][0]["body"] = "new task body"
        second = material.persist("new", changed)
        monkeypatch.setattr(capture, "capture", lambda **kw: pytest.fail("retry queried latest"))
        replay = capture.obtain("root", ("I","P","V"), retry=True)
        assert replay == first and replay["fingerprint"] != second["fingerprint"]
        assert replay["daily_material_manifest"]["confirmation_basis"] == value["confirmation_basis"]
        assert replay["daily_material_manifest"]["items"][0]["confirmation"] == value["items"][0]["confirmation"]


def test_summary_and_signed_locator_keep_full_version_identity(monkeypatch):
    from app.services import daily_material_projection as projection
    from app.services.bundles.emr_view import summarize_frozen_documents
    from app.routers import emr_render
    docs = projection.project_documents(synthetic_manifest())
    summary = summarize_frozen_documents(documents=docs)
    assert summary["documents"][0]["doc_key"] == docs[0]["doc_key"]
    assert summary["documents"][0]["version_id"] == "a"
    monkeypatch.setattr(emr_render, "customer_safe_projection_key", lambda: "synthetic-key")
    projected = emr_render._project_customer_safe_source_refs(summary)["documents"][0]
    assert projected["source_ref"] == emr_render.keyed_ref("src", docs[0]["doc_key"], hmac_key="synthetic-key")


def test_default_off_and_old_snapshot_compatibility(monkeypatch):
    from app.services import daily_material_projection as projection
    from app.services import case_material_snapshot as material
    monkeypatch.delenv("QC_DAILY_MATERIAL_ENABLED", raising=False)
    assert projection.manifest() is None
    monkeypatch.setenv("QC_DAILY_MATERIAL_ENABLED", "true")
    assert projection.manifest(("I","pdfp_P","pdfv_V")) is None
    with projection.live_context(("I","pdfp_P","pdfv_V")):
        assert material.context() is None
    with material.activate({"protocol":material.PROTOCOL}):
        assert projection.manifest() is None
    with pytest.raises(material.MaterialSnapshotError, match="capture_required"):
        projection.manifest()


def test_capture_to_real_provider_file_and_history_use_one_material_version(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from datetime import datetime, timedelta, timezone
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material, case_material_capture as capture, daily_material_projection as projection
    from app.services import clinical_source_contract
    from app.services.bundles import assembly
    from app.services.sichuan_qc_service import SichuanQCService
    from app.services.luxian_0609 import source_evidence_reader as reader
    from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
    calls = []
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execution_options(self, **kw): calls.append(kw); return self
        def begin(self): return nullcontext()
        def begin_nested(self): return nullcontext()
        def exec_driver_sql(self, sql): calls.append(sql)
    connection = Connection()
    engine = SimpleNamespace(connect=lambda: connection)
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR",str(tmp_path))
    monkeypatch.setenv("QC_DAILY_MATERIAL_ENABLED","true")
    monkeypatch.setenv("QC_CDM_CAPTURE_WINDOW_UNTIL",(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    monkeypatch.setattr(clinical,"configured",lambda:True)
    monkeypatch.setattr(assembly,"_source_engine",lambda schema:engine)
    monkeypatch.setattr(clinical_source_contract,"inspect_source",lambda *args,**kw:{"ok":True,"read_only":True,"account_read_only":True,"dependencies":[]})
    from app.services import cdm_publication_evidence
    monkeypatch.setattr(cdm_publication_evidence,"read_publication",lambda *a:{"status":"metadata_unavailable","rows":{}})
    monkeypatch.setattr(capture,"inspect",lambda conn:SimpleNamespace(has_table=lambda *args,**kw:False))
    monkeypatch.setattr(SichuanQCService,"_resolve_primary_diagnosis_context",lambda **kw:None)
    def manifest(conn, identity):
        assert conn is connection
        calls.append("manifest")
        return synthetic_manifest()
    monkeypatch.setattr(projection,"read_manifest",manifest)
    with clinical.selected({"id":"independent_cdm","binding":"synthetic"}):
        captured = capture.capture(identity=("I","P","V"))
        assert calls.count("manifest") == 1
        assert calls.index("SET TRANSACTION READ ONLY") < calls.index("manifest")
        assert captured["programmatic_sources"]["daily_course_record"]["rows"][0]["version_id"] == "a"
        stored = material.persist("root",captured)
        monkeypatch.setattr(assembly,"_source_engine",lambda *args:pytest.fail("history read latest"))
        with material.activate(stored):
            provider = build_luxian_0609_evidence_read_session(selected_rule_ids=("LX0609-02-01-01",),institute_id="I",patient_id="P",visit_id="V",source_schema="cdm",created_at="2026-11-01T10:00:00+08:00",evaluation_as_of_date="2026-11-01")
            assert provider.materials.rows("daily_course_record")[0]["version_id"] == "a"
            assert provider.materials.scope("daily_course_record")["can_judge_clinical_absence"] is False
            from app.services.sample_programmatic_evidence import build_programmatic_evidence_payload
            payload = build_programmatic_evidence_payload(bundle={"institute_id":"I", "patient_id":"P", "visit_id":"V", "source_documents":[{"source_table":"daily_course_record", "document_id":"conflict", "content":"unusable inventory body"}]})
            timeline = payload["programmatic_timeline"]
            assert timeline["material_scope"]["daily_course_record"]["can_judge_clinical_absence"] is False
            assert len(timeline["documents"]["daily_course_record"]) == 1
            assert timeline["documents"]["daily_course_record"][0]["document_id"] == "daily_course_record::ra::a"
            assert timeline["documents"]["daily_course_record"][0]["content"] == "synthetic body"
            assert stored["documents"]["documents"][0]["version_id"] == "a"
            assert "synthetic body" in stored["documents"]["documents"][0]["content"]


@pytest.mark.parametrize("phase", ["before_reference", "after_reference"])
def test_file_reference_failure_recovery_never_recaptures_retry(monkeypatch, tmp_path, phase):
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material, case_material_capture as capture
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR",str(tmp_path))
    state = {"protocol":material.PROTOCOL,"identity":["I","P","V"],"binding":"", "daily_material_manifest":synthetic_manifest()}
    original = material._exclusive
    def fault(path, data):
        if path.parent.name == "tasks":
            if phase == "after_reference": original(path,data)
            raise OSError("synthetic reference fault")
        original(path,data)
    monkeypatch.setattr(material,"_exclusive",fault)
    monkeypatch.setattr(capture,"capture",lambda **kw:pytest.fail("retry read latest"))
    with clinical.selected({"id":"legacy_pg","binding":""}):
        with pytest.raises(OSError): material.persist("root",state)
        assert len(list((tmp_path/"objects").glob("*.gz"))) == 1
        if phase == "before_reference":
            with pytest.raises(material.MaterialSnapshotError, match="original_task_material_not_retained"):
                capture.obtain("root",("I","P","V"),retry=True)
        else:
            recovered = capture.obtain("root",("I","P","V"),retry=True)
            assert recovered["daily_material_manifest"] == state["daily_material_manifest"]


def test_projection_keeps_conflicts_in_inventory_but_only_usable_selected_rows():
    from app.services import daily_material_projection as projection
    manifest = {"business_binding":{"policy":{"status_rules":[["clinical",None,"valid"]]}}, "items": [
        {"version_id":"a", "record_identity":"ra", "native_key":["I","P","V","same"], "source_namespace":"clinical", "source_object":"clinical.public.daily_course_record", "body":"reliable", "record_time":"2026-11-01T08:00:00", "selected":True, "rule_usable":True, "native_fields":{"zero":0,"flag":False}},
        {"version_id":"b", "record_identity":"rb", "native_key":["I","P","V","same"], "source_namespace":"cache", "source_object":"web.daily_course_record", "body":"conflict", "selected":True, "rule_usable":False},
    ], "coverage":{"cache":{"state":"UNKNOWN"}}, "can_judge_clinical_absence":False}
    rows = projection.project_rows(manifest)
    assert len(rows) == 1 and rows[0]["record_content"] == "reliable"
    assert rows[0]["daily_material"]["native_fields"] == {"zero":0,"flag":False}
    docs = projection.project_documents(manifest)
    assert len(docs) == 2 and len({doc["doc_key"] for doc in docs}) == 2
    assert not projection.scope_from_manifest(manifest)["can_judge_clinical_absence"]


@pytest.mark.parametrize("other_time,related", [("2026-11-01T08:00:00",True),("2026-11-03T08:00:00",False),(None,True)])
def test_fixed_contract_same_body_keeps_distinct_known_events(other_time, related):
    from app.services import daily_material_readonly as reader
    left = {"body":"同一合成正文", "record_time":"2026-11-01T08:00:00"}
    right = {"body":"同一合成正文", "record_time":other_time}
    assert reader.body_relation_hint(left,right) is related


def test_new_cache_equivalent_selection_does_not_change_retained_supplement(monkeypatch,tmp_path):
    from copy import deepcopy
    from app.services import case_material_snapshot as material, daily_material_projection as projection
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR",str(tmp_path))
    old = synthetic_manifest()
    new = deepcopy(old)
    new["items"][0].update(selected=False,rule_usable=False,state="EQUIVALENT_SUPPRESSED")
    cache = deepcopy(old["items"][0])
    cache.update(version_id="cache-new",record_identity="rc",source_namespace="cache",source_object="web.daily_course_record")
    new["items"].append(cache)
    def state(value): return {"protocol":material.PROTOCOL,"identity":["I","P","V"],"binding":"","daily_material_manifest":value}
    saved = material.persist("old",state(old))
    material.persist("new",state(new))
    assert len(projection.project_rows(new)) == 1
    assert projection.project_rows(new)[0]["version_id"] == "cache-new"
    assert material.load("old", ("I","P","V"))["daily_material_manifest"] == saved["daily_material_manifest"]


def test_packaged_readonly_definitions_keep_pinned_source_hashes():
    import ast
    import hashlib
    from pathlib import Path
    from app.services import daily_material_readonly as reader
    source = Path(reader.__file__).read_text(encoding="utf-8")
    nodes = {node.name:node for node in ast.parse(source).body if isinstance(node,(ast.ClassDef,ast.FunctionDef))}
    for key, expected in reader.EXTRACTED_SOURCE_SHA256.items():
        node = nodes[key.split(":")[1]]
        start = min([node.lineno, *(item.lineno for item in node.decorator_list)])
        segment = "\n".join(source.splitlines()[start-1:node.end_lineno])
        assert hashlib.sha256(segment.encode("utf-8")).hexdigest() == expected, key


@pytest.mark.parametrize("state", [("delivery_cdm_012345abcdef","off","repeatable read"),("delivery_cdm_012345abcdef","on","read committed")])
def test_readonly_rejects_wrong_transaction_without_owning_connection(state):
    from app.services import daily_material_readonly as reader
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,*args): pass
        def fetchone(self): return state
    settings = SimpleNamespace(host="127.0.0.1",port=55499,database="delivery_cdm_012345abcdef")
    with pytest.raises(reader.IngestError,match="material_capture_transaction_required"):
        reader.read_manifest_in_transaction(settings,SimpleNamespace(cursor=Cursor),"synthetic",reader.clinical_contract())


def test_readonly_missing_policy_is_controlled():
    from app.services import daily_material_readonly as reader
    cursor = SimpleNamespace(execute=lambda *args:None,fetchone=lambda:None)
    with pytest.raises(reader.IngestError,match="material_case_policy_missing"):
        reader._inputs(cursor,"synthetic")


@pytest.mark.parametrize("meaning,availability,count", [(None,"UNCONFIRMED",0),("cancelled","SEMANTICS_APPROVED",0),("valid","SEMANTICS_APPROVED",1),("unsupported","SEMANTICS_APPROVED",0)])
def test_frozen_status_semantics_control_formal_rows(meaning, availability, count):
    from app.services import daily_material_projection as projection
    value = synthetic_manifest()
    value["items"][0].update(source_status="Save",state="SUPPLEMENT_CONFIRMED",field_availability={"source_status":availability})
    value["business_binding"] = {"policy":{"status_rules":[] if meaning is None else [["clinical","Save",meaning]]}}
    assert len(projection.project_rows(value)) == count
    assert len(projection.project_documents(value)) == 1
    if meaning not in ("valid","cancelled"):
        value["can_judge_clinical_absence"] = True
        assert not projection.scope_from_manifest(value)["can_judge_clinical_absence"]


def test_material_display_is_safe_in_summary_full_and_empty_scope():
    from app.services import daily_material_projection as projection
    from app.services.bundles.emr_view import summarize_frozen_documents, build_render_view
    value = synthetic_manifest()
    value["fresh"] = False
    value["items"][0].update(state="CONTENT_CONFLICT",rule_usable=False)
    doc = projection.project_documents(value)[0]
    summary = summarize_frozen_documents(documents=[doc])["documents"][0]
    full = build_render_view(doc)["document_meta"]
    for result in (summary,full):
        assert result["material_source_label"] == "临床补充"
        assert "冲突" in result["material_notice"]
        assert "body" not in result and "daily_material" not in result
    assert "待更新" in projection.display_scope(value)["notice"]
    value["items"] = []
    assert "暂无" in projection.display_scope(value)["notice"]


@pytest.mark.parametrize("prior",[False,True])
def test_current_base_observation_is_inventory_only(prior, monkeypatch, tmp_path):
    from app.services import daily_material_projection as projection, daily_material_readonly as reader
    value = synthetic_manifest()
    if not prior: value["items"] = []
    value["fresh"] = False
    raw = {"institute_id":"I","patient_id":"P","visit_id":"V","document_id":"new", "record_content":"new base body", "document_status":"Save"}
    value["business_base_inventory"] = projection.observed_base_inventory([tuple(raw.get(key) for key in reader.CACHE_COLUMNS)],value,("I","P","V"))
    assert len(projection.project_rows(value)) == int(prior)
    docs = projection.project_documents(value)
    assert len(docs) == 1 + int(prior)
    observed = docs[-1]
    assert observed["content"] == "new base body"
    assert observed["daily_material"]["source_revision"] == "UNCONFIRMED"
    assert observed["version_id"].startswith("observed-")
    assert observed["material_rule_usable"] is False
    assert projection.observed_base_inventory([tuple(raw.get(key) for key in reader.CACHE_COLUMNS)], {"items":[observed["daily_material"]]},("I","P","V")) == []
    from app.services import case_material_snapshot as material
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR",str(tmp_path))
    material.persist("observed-root", {"protocol":material.PROTOCOL,"identity":["I","P","V"],"binding":"","daily_material_manifest":value})
    value["business_base_inventory"][0]["body"] = "later base body"
    assert material.load("observed-root",("I","P","V"))["daily_material_manifest"]["business_base_inventory"][0]["body"] == "new base body"



def test_missing_binding_is_rejected_by_formal_reader():
    from app.services import daily_material_projection as projection
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self,*args): pass
        def fetchall(self): return []
    conn = SimpleNamespace(connection=SimpleNamespace(driver_connection=SimpleNamespace(cursor=Cursor)),engine=SimpleNamespace(url=SimpleNamespace(host="127.0.0.1",port=55499,database="delivery_cdm_012345abcdef")))
    with pytest.raises(projection.MissingDailyBinding): projection.read_manifest(conn,("I","P","V"))


def test_live_view_missing_binding_keeps_only_same_connection_base(monkeypatch):
    from contextlib import nullcontext
    from app.database import clinical_connection as clinical
    from app.services import daily_material_projection as projection
    from app.services.bundles import assembly
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execution_options(self,**kw): assert kw == {"isolation_level":"REPEATABLE READ"}; return self
        def begin(self): return nullcontext()
        def exec_driver_sql(self,sql): pass
    connection = Connection()
    monkeypatch.setenv("QC_DAILY_MATERIAL_ENABLED","true")
    monkeypatch.setattr(clinical,"configured",lambda:True)
    monkeypatch.setattr(assembly,"_source_engine",lambda schema:SimpleNamespace(connect=lambda:connection))
    def missing(conn,identity):
        assert conn is connection
        raise projection.MissingDailyBinding("daily_material_binding_missing")
    monkeypatch.setattr(projection,"read_manifest",missing)
    def base(conn,value,identity):
        assert conn is connection
        item = synthetic_manifest()["items"][0]
        return [{**item,"state":"PENDING_RECONCILIATION","selected":False,"rule_usable":False}]
    monkeypatch.setattr(projection,"read_base_inventory",base)
    with projection.live_context(("I","P","V"), allow_unbound_view=True):
        value = projection.manifest(("I","P","V"))
        assert len(projection.project_documents(value)) == 1
        assert projection.project_rows(value) == []
        assert value["business_binding"]["state"] == "UNAPPROVED"
        assert not projection.scope_from_manifest(value)["can_judge_clinical_absence"]


@pytest.fixture
def standalone_daily_owner(monkeypatch):
    from contextlib import nullcontext
    from app.database import clinical_connection as clinical
    from app.services import daily_material_projection as projection
    from app.services.bundles import assembly
    calls = []
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execution_options(self,**kw): assert kw == {"isolation_level":"REPEATABLE READ"}; return self
        def begin(self): return nullcontext()
        def exec_driver_sql(self,sql): pass
    connection = Connection()
    monkeypatch.setenv("QC_DAILY_MATERIAL_ENABLED","true")
    monkeypatch.setattr(clinical,"configured",lambda:True)
    monkeypatch.setattr(assembly,"_source_engine",lambda schema:SimpleNamespace(connect=lambda:connection))
    def read(conn,identity):
        assert conn is connection
        calls.append(identity)
        return synthetic_manifest()
    monkeypatch.setattr(projection,"read_manifest",read)
    for name in ("ensure_scene_bundle_tables","ensure_domain_bundle_tables","_upsert_scene_bundle","_upsert_domain_bundle","mark_bundle_refresh_success"):
        monkeypatch.setattr(assembly,name,lambda **kw:None)
    def assembled(**kw):
        identity = tuple(kw[key] for key in ("institute_id","patient_id","visit_id"))
        return {"rows":projection.rows(identity)}
    monkeypatch.setattr(assembly,"_assemble_scene_bundle",assembled)
    monkeypatch.setattr(assembly,"assemble_domain_bundle",assembled)
    return assembly,calls


@pytest.mark.parametrize("kind",["scene","domain","direct","index","render"])
def test_standalone_bundle_owner_reads_manifest_instead_of_old_cache(standalone_daily_owner,kind,monkeypatch):
    assembly,calls = standalone_daily_owner
    monkeypatch.setattr(assembly,"_load_scene_bundle",lambda **kw:pytest.fail("stale scene cache read"))
    kwargs = dict(institute_id="I",patient_id="P",visit_id="V")
    if kind == "scene": result = assembly.load_or_assemble_scene_bundle(scene="running",**kwargs)
    elif kind == "domain": result = assembly.load_or_assemble_domain_bundle(execution_domain="course",**kwargs)
    elif kind == "direct": result = assembly.load_domain_bundle(execution_domain="course",**kwargs)
    elif kind == "index": result = assembly.load_domain_bundle_document_index(execution_domain="course",**kwargs)
    else: result = assembly.load_domain_bundle_for_emr_render(execution_domain="course",doc_type="daily_course_record",doc_id="D",**kwargs)
    assert result["rows"][0]["record_content"] == "synthetic body"
    assert calls == [("I","P","V")]


def test_unified_refresh_owns_one_context_per_case(standalone_daily_owner,monkeypatch):
    from app.services import daily_material_projection as projection
    assembly,calls = standalone_daily_owner
    def snapshot(**kw):
        assert projection.rows(tuple(kw[key] for key in ("institute_id","patient_id","visit_id")))[0]["version_id"] == "a"
        return SimpleNamespace(material_reads=1)
    monkeypatch.setattr(assembly,"_build_material_snapshot",snapshot)
    result = assembly.refresh_all_bundle_variants_for_rows(rows=[{"institute_id":"I","patient_id":"P","visit_id":visit} for visit in ("V","V2")],scenes=["running","final"],domains=["course"],continue_on_error=False)
    assert calls == [("I","P","V"),("I","P","V2")]
    assert result["scenes"]["running"]["updated"] == 2
    assert result["domains"]["course"]["updated"] == 2



def test_recording_column_inspection_uses_owned_connection(standalone_daily_owner,monkeypatch):
    from app.services import daily_material_projection as projection, case_material_snapshot as material
    assembly,_ = standalone_daily_owner
    inspected = []
    def inspect(connection):
        assert connection is material.context()["connection"]
        inspected.append(connection)
        return SimpleNamespace(has_table=lambda **kw:True,get_columns=lambda **kw:[{"name":"document_id"}])
    monkeypatch.setattr(assembly,"inspect",inspect)
    with projection.live_context(("I","P","V")):
        assert assembly._get_table_columns("cdm","senior_course_record") == ("document_id",)
        assert assembly._get_table_columns("cdm","senior_course_record") == ("document_id",)
    assert len(inspected) == 1


def test_daily_manifest_overrides_unattested_bundle_material_snapshot(standalone_daily_owner):
    from app.services import daily_material_projection as projection
    assembly,_ = standalone_daily_owner
    stale = SimpleNamespace(rows_for=lambda **kw:pytest.fail("old snapshot supplied daily"))
    with projection.live_context(("I","P","V")):
        result = assembly._material_rows(material_snapshot=stale,source_schema="cdm",table="daily_course_record",institute_id="I",patient_id="P",visit_id="V",limit=5)
    assert result[0]["record_content"] == "synthetic body"


@pytest.mark.parametrize("kind",["all","domain"])
def test_bundle_capture_failure_only_fails_its_case(standalone_daily_owner,monkeypatch,kind):
    from app.services import daily_material_projection as projection
    assembly,calls = standalone_daily_owner
    original = projection.read_manifest
    def read(conn,identity):
        if identity[-1] == "V": raise projection.MissingDailyBinding("daily_material_binding_missing")
        return original(conn,identity)
    monkeypatch.setattr(projection,"read_manifest",read)
    monkeypatch.setattr(assembly,"_build_material_snapshot",lambda **kw:SimpleNamespace(material_reads=1))
    failures = []
    monkeypatch.setattr(assembly,"record_bundle_refresh_failure",lambda **kw:failures.append(kw))
    rows=[{"institute_id":"I","patient_id":"P","visit_id":visit} for visit in ("V","V2")]
    if kind == "all":
        result=assembly.refresh_all_bundle_variants_for_rows(rows=rows,scenes=["running"],domains=["course"],continue_on_error=True)
        assert result["scenes"]["running"] == {"processed":2,"updated":1,"failed":1,"skipped":0}
        assert len(failures) == 1 and failures[0]["error_stage"] == "material_capture"
        result=result["domains"]["course"]
    else: result=assembly.refresh_domain_bundles_for_rows(rows=rows,domains=["course"],continue_on_error=True)
    assert result == {"processed":2,"updated":1,"failed":1,"skipped":0}
    assert calls == [("I","P","V2")]



def test_bundle_owner_keeps_pdf_material_snapshot_when_daily_enabled(monkeypatch):
    from app.services.bundles import assembly
    from app.services import validation_material_source
    monkeypatch.setenv("QC_DAILY_MATERIAL_ENABLED","true")
    monkeypatch.setattr(validation_material_source,"is_material_copy",lambda *args:True)
    snapshot = object()
    owner = assembly._daily_bundle_owner(lambda **kwargs:kwargs["material_snapshot"])
    assert owner(institute_id="I",patient_id="PDF-P",visit_id="PDF-V",material_snapshot=snapshot) is snapshot
