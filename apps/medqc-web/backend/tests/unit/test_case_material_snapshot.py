"""材料内容、任务版本和读取隔离；只用临时文件和固定应答。"""
from contextlib import nullcontext
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.services import case_material_snapshot as material
from app.database import clinical_connection as clinical
from app.services.bundles import assembly

IDENTITY = ("SYNTHETIC-I", "SYNTHETIC-P", "SYNTHETIC-V")


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    with clinical.selected({"id": "legacy_pg", "binding": ""}):
        yield


def dataset(body="v1"):
    row = {"document_id": "D", "record_content": body, "document_status": "valid", "record_datetime": datetime(2026, 11, 1, 8)}
    return {"protocol": material.PROTOCOL, "identity": list(IDENTITY), "binding": "", "schema": "cdm",
            "columns": {"daily_course_record": list(row)}, "tables": {"daily_course_record": [row]}, "queries": {},
            "documents": {"documents": [{"id": "D", "doc_type": "daily_course_record", "content": body}], "documents_tree": []}}


@pytest.mark.parametrize("binding", ["", "synthetic-cdm-binding"])
def test_formal_adapter_uses_frozen_supplements_and_registration(monkeypatch, binding):
    from types import SimpleNamespace
    from app.services import sample_programmatic_evidence as evidence
    from app.services.qc_input_adapters.running_final_bundle_adapter import adapt_bundle_to_evidence_payload

    # 当前库可能已修改，或同键属于另一来源；正式适配链不可建立任何回源连接。
    monkeypatch.setattr(evidence, "engine", SimpleNamespace(connect=lambda: pytest.fail("snapshot bypassed to current business database")))
    monkeypatch.setattr(evidence, "get_documents", lambda **_: pytest.fail("unscoped detail fallback"))
    state = dataset("frozen-course")
    for table in (*evidence._SOURCE_TABLES, "inpat_registration"):
        state["tables"].setdefault(table, [])
        state["columns"].setdefault(table, [])
    state["tables"]["inpat_registration"] = [{"admission_datetime": "2026-11-01 08:00:00", "discharge_datetime": "2026-11-03 08:00:00"}]
    state["columns"]["inpat_registration"] = list(state["tables"]["inpat_registration"][0])
    state["programmatic_sources"] = {table: {"rows": state["tables"][table]} for table in (*evidence._SOURCE_TABLES, "inpat_registration")}
    state["binding"] = binding
    bundle = {**dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY)), "scene": "running",
              "medical_text": "existing inventory", "source_documents": [{"source_table": "admission_record", "document_id": "A", "content": "inventory-body"}]}
    with clinical.selected({"id": "independent_cdm" if binding else "legacy_pg", "binding": binding}):
        frozen = material.persist("adapter-case", state)
        with material.activate(frozen):
            result = adapt_bundle_to_evidence_payload(bundle)["programmatic_timeline"]
    assert "frozen-course" in str(result)
    assert result["admission_time"] == "2026-11-01 08:00:00"


def test_formal_adapter_missing_snapshot_table_fails_instead_of_reading_live(monkeypatch):
    from app.services import sample_programmatic_evidence as evidence
    from app.services.qc_input_adapters.running_final_bundle_adapter import adapt_bundle_to_evidence_payload
    monkeypatch.setattr(evidence, "engine", None)
    monkeypatch.setattr(evidence, "get_documents", lambda **_: pytest.fail("unscoped detail fallback"))
    with material.activate(material.persist("missing-table", dataset())):
        with pytest.raises(material.MaterialSnapshotError, match="uncaptured"):
            adapt_bundle_to_evidence_payload({**dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY)), "scene": "final"})


def test_empty_captured_sources_do_not_enter_live_detail_fallback(monkeypatch):
    from app.services import sample_programmatic_evidence as evidence
    monkeypatch.setattr(evidence, "get_documents", lambda **_: pytest.fail("unscoped detail fallback"))
    state = dataset()
    state["programmatic_sources"] = {table: {"rows": []} for table in (*evidence._SOURCE_TABLES, "inpat_registration")}
    with material.activate(material.persist("empty", state)):
        result = evidence.build_programmatic_evidence_payload(bundle=dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY)))
        assert not any(result["programmatic_timeline"]["documents"].values())
        with pytest.raises(material.MaterialSnapshotError, match="forbidden"):
            evidence._fetch_detail_service_fallback_items(IDENTITY[-1])


def test_snapshot_supplement_preserves_structured_fields_limits_and_missing_tables():
    from app.services import sample_programmatic_evidence as evidence
    state = dataset()
    state["programmatic_sources"] = {table: {"rows": []} for table in (*evidence._SOURCE_TABLES, "inpat_registration")}
    state["programmatic_sources"]["labtest_master"] = {"unavailable": True}
    state["programmatic_sources"]["labtest_item_report"] = {"rows": [
        {"document_id": "L1", "test_id": "T1", "result": "5.5", "unit": "synthetic-unit"},
        {"document_id": "L2", "test_id": "T2", "result": "6.5"},
    ]}
    bundle = dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY))
    with material.activate(material.persist("lab", state)):
        evidence._fetch_source_table_fallback_items(bundle, strict_structured_source_limits={"labtest_master": 1, "labtest_item_report": 1})
    assert bundle["_structured_source_readiness"] == {"labtest_master": "unavailable", "labtest_item_report": "partial"}
    row, = bundle["_structured_source_rows"]["labtest_item_report"]
    assert (row["test_id"], row["result"], row["unit"]) == ("T1", "5.5", "synthetic-unit")


@pytest.mark.parametrize("change", ["body", "time", "status", "add", "remove"])
def test_changes_new_task_but_original_task_is_immutable(change):
    first = material.persist("original", dataset())
    updated = dataset()
    rows = updated["tables"]["daily_course_record"]
    if change == "body":
        rows[0]["record_content"] = "v2"
    elif change == "time":
        rows[0]["record_datetime"] = datetime(2026, 11, 1, 9)
    elif change == "status":
        rows[0]["document_status"] = "withdrawn"
    elif change == "add":
        rows.append({**rows[0], "document_id": "NEW"})
    else:
        rows.clear()
    second = material.persist("new-task", updated)
    assert first["fingerprint"] != second["fingerprint"]
    assert material.load("original", IDENTITY)["tables"]["daily_course_record"][0]["record_content"] == "v1"
    assert material.persist("original", updated)["fingerprint"] == first["fingerprint"]


def test_equal_content_can_reuse_immutable_object():
    one = material.persist("one", dataset())
    two = material.persist("two", dataset())
    assert one["fingerprint"] == two["fingerprint"]
    assert len(list((material.storage_root() / "objects").glob("*.gz"))) == 1


def test_dates_precision_and_timezone_roundtrip():
    value = {"exact": datetime(2026, 11, 1, tzinfo=timezone.utc), "day": date(2026, 11, 1), "amount": Decimal("1.50")}
    assert material.decode(material.encode(value)) == value
    assert material.fingerprint(value) != material.fingerprint({**value, "day": datetime(2026, 11, 1)})


def test_corrupt_object_is_not_replaced_or_read_as_current():
    frozen = material.persist("task", dataset())
    path = material.storage_root() / "objects" / (frozen["fingerprint"] + ".json.gz")
    path.write_bytes(b"broken")
    with pytest.raises(material.MaterialSnapshotError):
        material.load("task", IDENTITY)
    with pytest.raises(material.MaterialSnapshotError):
        material.persist("task", dataset())


def test_case_and_source_mismatch_fail_closed():
    material.persist("task", dataset())
    assert material.load("task", ("OTHER", *IDENTITY[1:])) is None
    with clinical.selected({"id": "independent_cdm", "binding": "other-source"}):
        with pytest.raises(material.MaterialSnapshotError, match="source_mismatch"):
            material.load("task", IDENTITY)


@pytest.mark.parametrize("cohort_aliases", [False, True])
def test_query_replays_original_and_never_reenters_source(cohort_aliases):
    class Connection:
        def begin_nested(self):
            return nullcontext()
    calls = []
    @material.material_query
    def fixed_query(**kwargs):
        calls.append(kwargs)
        return {"body": "first"}
    state = dataset()
    state.update(connection=Connection(), engine=object())
    args = dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY))
    if cohort_aliases:
        args = {"institute_id": IDENTITY[0], "current_patient_id": IDENTITY[1], "current_visit_id": IDENTITY[2]}
    with material.recording(state):
        assert fixed_query(**args) == {"body": "first"}
    state.pop("connection")
    state.pop("engine")
    frozen = material.persist("task", state)
    with material.activate(frozen):
        assert fixed_query(**args) == {"body": "first"}
        with pytest.raises(material.MaterialSnapshotError, match="uncaptured"):
            fixed_query(**args, source_key="new-query")
        with pytest.raises(material.MaterialSnapshotError, match="forbidden"):
            with material.source_connection(object()):
                pytest.fail("live source entered")
    assert len(calls) == 1


def test_bundle_requires_current_content_fingerprint():
    frozen = material.persist("task", dataset())
    with material.activate(frozen):
        assert not assembly._cache_source_matches({"clinical_source_binding": ""}, IDENTITY[1], IDENTITY[2])
        assert assembly._cache_source_matches({"clinical_source_binding": "", "case_material_fingerprint": frozen["fingerprint"]}, IDENTITY[1], IDENTITY[2])
        assert not assembly._cache_source_matches({"clinical_source_binding": "", "case_material_fingerprint": "stale"}, IDENTITY[1], IDENTITY[2])


def test_history_document_uses_original_body_without_bundle(monkeypatch):
    from app.routers import emr_render
    monkeypatch.setattr(emr_render, "customer_safe_projection_key", lambda: "synthetic-key")
    monkeypatch.setattr(emr_render, "load_bundle_documents", lambda **_: pytest.fail("mutable Bundle entered"))
    frozen = material.persist("task", dataset())
    with material.activate(frozen):
        result = emr_render._load_documents_from_bundle(record_id=IDENTITY[2], institute_id=IDENTITY[0], patient_id=IDENTITY[1], visit_id=IDENTITY[2])
    assert result["documents"][0]["content"] == "v1"


def test_no_original_snapshot_retry_does_not_capture(monkeypatch):
    from app.services import case_material_capture
    monkeypatch.setattr(case_material_capture, "capture", lambda **_: pytest.fail("recaptured current source"))
    with pytest.raises(material.MaterialSnapshotError, match="not_retained"):
        case_material_capture.obtain("old-task", IDENTITY, retry=True)


@pytest.mark.parametrize(("stage", "code"), [
    ("source_read", "source_database_operational_error"),
    ("source_read", "source_connection_pool_timeout"),
    ("source_validation", "unknown"),
    ("source_read", "material_capture_timeout"),
    ("source_read", "unknown"),
    ("snapshot_persist", "material_value_type_unsupported"),
    ("snapshot_persist", "snapshot_io_error"),
])
def test_obtain_logs_only_stage_and_approved_reason(monkeypatch, caplog, stage, code):
    from unittest.mock import MagicMock
    from sqlalchemy.exc import OperationalError, TimeoutError
    from app.services import case_material_capture as capture, clinical_source_contract
    from app.services.material_admission import safe_material_failure
    from app.services.qc_execution_errors import safe_exception_failure

    private = "SYNTHETIC-BODY postgresql://synthetic-user:synthetic-password@db/test"
    job_id = "SYNTHETIC-JOB"
    public_error = "material_capture_failed"
    if stage == "source_read":
        error = {
            "source_database_operational_error": OperationalError(private, IDENTITY, RuntimeError(private)),
            "source_connection_pool_timeout": TimeoutError(private),
            "material_capture_timeout": material.MaterialSnapshotError(code),
            "unknown": material.MaterialSnapshotError(private),
        }[code]
        if isinstance(error, material.MaterialSnapshotError):
            public_error = str(error)

        def unavailable(_schema):
            raise error

        monkeypatch.setattr(assembly, "_source_engine", unavailable)
    elif stage == "source_validation":
        engine = MagicMock()
        monkeypatch.setattr(assembly, "_source_engine", lambda _: engine)
        monkeypatch.setattr(assembly, "_default_source_schema", lambda: "cdm")
        monkeypatch.setattr(clinical, "configured", lambda: True)
        # 缺少 dependencies，在真实合同校验函数中触发意外 KeyError。
        monkeypatch.setattr(clinical_source_contract, "inspect_source", lambda *a, **kw: {
            "read_only": True, "account_read_only": True, "private": private,
        })
    elif code == "material_value_type_unsupported":
        from datetime import time
        public_error = code
        monkeypatch.setattr(capture, "capture", lambda **_: dataset(time(8, 0)))
    else:
        def write_failed(*_):
            raise type("SyntheticPrivateKey", (PermissionError,), {})(private)

        monkeypatch.setattr(capture, "capture", lambda **_: dataset(private))
        monkeypatch.setattr(material, "_exclusive", write_failed)

    with pytest.raises(material.MaterialSnapshotError) as caught:
        capture.obtain(job_id, IDENTITY)
    assert str(caught.value) == public_error
    assert safe_material_failure(str(caught.value))["code"] == "material_capture_failed"
    if public_error == "material_capture_failed":
        assert safe_exception_failure(caught.value)["retryable"] is False
        assert caught.value.__suppress_context__
    [record] = [record for record in caplog.records if record.name == capture.__name__]
    assert record.getMessage() == f"material_capture_failed stage={stage} code={code}"
    assert record.exc_info is None and record.stack_info is None
    assert all(secret not in caplog.text for secret in (private, *IDENTITY, job_id, "SyntheticPrivateKey", "dependencies"))


def test_obtain_propagates_known_failure_and_cancellation(monkeypatch, caplog):
    from app.services import case_material_capture as capture
    from app.services.qc_cancellation import QCJobCancelled

    for failure in (material.MaterialSnapshotError("material_source_unavailable"), QCJobCancelled()):
        def fail(**_):
            raise failure

        monkeypatch.setattr(capture, "capture", fail)
        with pytest.raises(type(failure)) as caught:
            capture.obtain("synthetic-task", IDENTITY)
        assert caught.value is failure
    assert not [record for record in caplog.records if record.name == capture.__name__]


def test_capacity_refused_without_task_reference(monkeypatch):
    monkeypatch.setattr(material, "MAX_BYTES", 20)
    with pytest.raises(material.MaterialSnapshotError, match="capacity"):
        material.persist("task", dataset())
    assert material.load("task", IDENTITY) is None


def test_atomic_concurrent_publish_has_one_task_winner():
    from concurrent.futures import ThreadPoolExecutor
    def publish(body):
        with clinical.selected({"id": "legacy_pg", "binding": ""}):
            return material.persist("same-task", dataset(body))["fingerprint"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        winners = list(pool.map(publish, ("one", "two", "three", "four")))
    assert len(set(winners)) == 1


def test_historical_wrong_document_id_never_falls_back(monkeypatch):
    from app.routers import emr_render
    monkeypatch.setattr(emr_render, "customer_safe_projection_key", lambda: "synthetic-key")
    frozen = material.persist("task", dataset())
    with material.activate(frozen):
        result = emr_render._load_document_from_bundle(record_id=IDENTITY[2], institute_id=IDENTITY[0],
            patient_id=IDENTITY[1], visit_id=IDENTITY[2], execution_domain="course",
            doc_type="daily_course_record", doc_id="WRONG")
    assert result is None


@pytest.mark.parametrize("existing,current_view", [(False,False),(True,True)])
def test_history_missing_or_current_conflict_is_explicit(existing, current_view):
    import asyncio
    from fastapi import HTTPException
    from starlette.requests import Request
    from app.services import clinical_sources
    if existing:
        material.persist("task", dataset())
    query = "&".join(f"{key}={value}" for key,value in zip(("institute_id","patient_id","visit_id"),IDENTITY))
    if current_view:
        query += "&source_view=current"
    req = Request({"type":"http","method":"GET","path":"/api/v1/emr/V/documents", "query_string":query.encode(),"headers":[]})
    req.state.material_root_job_id = "task"
    req.state.clinical_source = {"id":"legacy_pg","binding":""}
    async def read():
        generator = clinical_sources.bind_request(req)
        with pytest.raises(HTTPException) as error:
            await generator.__anext__()
        assert error.value.status_code == 409
        assert ("conflict" if current_view else "not_retained") in error.value.detail
    asyncio.run(read())


def test_no_manual_window_still_rejects_unavailable_source(monkeypatch):
    from app.services.case_material_capture import capture
    monkeypatch.delenv("QC_CDM_CAPTURE_WINDOW_UNTIL",raising=False)
    monkeypatch.setattr(assembly, "_source_engine", lambda _: None)
    with clinical.selected({"id":"independent_cdm","binding":"source"}):
        with pytest.raises(material.MaterialSnapshotError,match="material_source_unavailable"):
            capture(identity=IDENTITY)


@pytest.mark.asyncio
async def test_two_batches_share_four_cdm_capture_slots(monkeypatch):
    import asyncio
    from threading import Event, Lock

    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import QueuePool

    from app.services import case_material_capture as capture, cdm_publication_evidence, clinical_source_contract
    from app.services import sample_programmatic_evidence
    from app.services.bundles import current_view
    from app.services.luxian_0609 import source_evidence_reader
    from app.services.sichuan_qc_service import SichuanQCService

    engine = create_engine("sqlite://", poolclass=QueuePool, pool_size=3, max_overflow=2,
                           pool_timeout=0.1, connect_args={"check_same_thread": False})
    alias = engine.execution_options()
    full, release = Event(), Event()
    counts_lock = Lock()
    held = peak = 0

    @event.listens_for(engine, "set_connection_execution_options")
    def sqlite_isolation(_connection, options):
        if options.get("isolation_level") == "REPEATABLE READ":
            options["isolation_level"] = "SERIALIZABLE"

    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def sqlite_transaction_commands(_connection, _cursor, statement, params, _context, _many):
        if statement in {"SET TRANSACTION READ ONLY", "SET LOCAL statement_timeout=10000"}:
            return "SELECT 1", ()
        return statement, params

    def hold_transaction(*args, **kwargs):
        nonlocal held, peak
        with counts_lock:
            held += 1
            peak = max(held, peak)
            if held == 4:
                full.set()
        try:
            assert release.wait(5), "synthetic capture release was not signaled"
            return {"read_only": True, "account_read_only": True, "dependencies": []}
        finally:
            with counts_lock:
                held -= 1

    monkeypatch.setattr(clinical, "get_engine", lambda: alias if clinical.current_selection()["batch"] else engine)
    monkeypatch.setattr(clinical_source_contract, "inspect_source", hold_transaction)
    monkeypatch.setattr(assembly, "_select_records", lambda **_: [])
    monkeypatch.setattr(cdm_publication_evidence, "read_publication", lambda *_: {"rows": {}, "status": "synthetic"})
    monkeypatch.setattr(sample_programmatic_evidence, "capture_programmatic_sources", lambda *_: {})
    monkeypatch.setattr(current_view, "_assemble_current_documents", lambda **_: dataset()["documents"])
    monkeypatch.setattr(SichuanQCService, "_resolve_primary_diagnosis_context", lambda **_: None)
    for name in (
        "read_luxian_0609_course_round_timeline", "has_luxian_0609_current_visit_unstable_order",
        "read_luxian_0609_severity_order_rows", "read_luxian_0609_exam_lab_order_rows",
        "read_luxian_0609_rescue_order_rows", "read_luxian_0609_discharge_horizon_rows",
        "read_luxian_0609_snapshot_source_rows", "read_luxian_0609_native_source_rows",
        "read_luxian_0609_runtime_source_rows",
    ):
        monkeypatch.setattr(source_evidence_reader, name, lambda **_: [])

    all_submitted, cancellation_queued = asyncio.Event(), asyncio.Event()
    submit_capture = clinical.submit_capture
    submissions = 0
    queued_cancellation = None

    def track_submission(*args, **kwargs):
        nonlocal submissions, queued_cancellation
        result = submit_capture(*args, **kwargs)
        submissions += 1
        if submissions == 16:
            all_submitted.set()
        elif submissions == 17:
            queued_cancellation = result
            cancellation_queued.set()
        return result

    monkeypatch.setattr(clinical, "submit_capture", track_submission)

    async def batch(index):
        job = f"synthetic-batch-{index}"
        identities = [("I", f"P{index}-{n}", f"V{index}-{n}") for n in range(8)]
        with clinical.selected({"id": "independent_cdm", "binding": "synthetic-cdm", "batch": index}):
            results = await asyncio.gather(*(capture.obtain_for_batch(job, identity) for identity in identities))
            assert [value["identity"] for value in results] == [list(identity) for identity in identities]
            assert all(material.load(job, identity)["fingerprint"] == value["fingerprint"]
                       for identity, value in zip(identities, results))

    batches = asyncio.gather(batch(0), batch(1))
    try:
        try:
            await asyncio.wait_for(all_submitted.wait(), 3)
            assert await asyncio.wait_for(asyncio.to_thread(full.wait, 1), 2)
            cancelled_identity = ("I", "cancelled-patient", "cancelled-visit")
            with clinical.selected({"id": "independent_cdm", "binding": "synthetic-cdm", "batch": 0}):
                waiting = asyncio.create_task(capture.obtain_for_batch("synthetic-batch-0", cancelled_identity))
                try:
                    await asyncio.wait_for(cancellation_queued.wait(), 1)
                finally:
                    waiting.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await waiting
                assert queued_cancellation is not None and queued_cancellation.cancelled()
            # 通用工作线程仍能执行模型审计这样的后台操作，浏览也能取得第五条连接。
            with engine.connect() as online:
                assert online.exec_driver_sql("SELECT 1").scalar() == 1
            await asyncio.sleep(0.15)  # 超过合成连接池的 checkout 超时。
        finally:
            release.set()
            await batches
        assert peak == 4
        assert engine.pool.checkedout() == 0
        with clinical.selected({"id": "independent_cdm", "binding": "synthetic-cdm", "batch": 0}):
            assert material.load("synthetic-batch-0", cancelled_identity) is None
    finally:
        engine.dispose()


def test_directory_does_not_infer_inpatient_and_keeps_date_precision():
    from app.services import clinical_case_catalog as catalog
    from sqlalchemy import column, table, select
    from sqlalchemy.dialects import postgresql
    src = table("cases",*(column(k) for k in (*catalog.KEYS,"discharge","admission")))
    sql = str(select(src).where(*catalog._predicates(src,hospital_status="inpatient")).compile(dialect=postgresql.dialect(),compile_kwargs={"literal_binds":True}))
    assert "false" in sql and "admission IS NOT NULL" not in sql
    assert type(catalog._datetime("2026-11-01")) is date
    assert catalog._datetime("2026-11-01T00:00:00Z") == datetime(2026,11,1,8)
    assert "admission_date" in catalog.FIELDS["admission"]


def test_dependency_inventory_covers_physical_readers():
    from app.services.clinical_source_contract import TABLES, OPTIONAL
    from app.services.luxian_0609 import source_evidence_reader as reader
    planned = assembly._material_limits_for_variants(scenes=tuple(assembly._SCENE_DOC_PRIORITY),domains=tuple(assembly._DOMAIN_DOC_PRIORITY))
    physical = set(planned) | {k.split(".")[0] for k in reader._NATIVE_SOURCE_FIELDS}
    assert physical <= set(TABLES)
    assert "inpat_registration" in OPTIONAL and "daily_course_record" not in OPTIONAL


@pytest.mark.asyncio
@pytest.mark.parametrize("case_index,mature,expected", [(0,True,"compliant"),(1,True,"non_compliant"),(1,False,"data_gap")])
async def test_frozen_material_survives_native_binding_and_canonical(monkeypatch, tmp_path, case_index, mature, expected):
    # 主抽取与专项均为固定夹具；只验材料重放/正式结果合同，不声称医学模型准确性。
    from tests.unit import test_exam_poc_acceptance as acceptance
    from app.services.luxian_0609 import source_evidence_reader as reader
    from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
    old = acceptance._typed_session
    replayed = []
    def frozen_session(patch, **kwargs):
        snapshot, store = old(patch, **kwargs)
        value = dataset()
        value["identity"] = ["safe-institute","safe-patient","safe-visit"]
        coordinates = dict(zip(("institute_id","patient_id","visit_id"),value["identity"]))
        for key, rows in store.diagnostic_sources(snapshot=snapshot).items():
            arguments = {**coordinates,"source_schema":"cdm","source_key":key}
            query = material.query_key("read_luxian_0609_snapshot_source_rows", arguments,"cdm")
            value["queries"][query] = {"value":material.encode(rows)}
        frozen = material.persist("formal-test",value)
        sources = {}
        with material.activate(frozen):
            for key in store.diagnostic_sources(snapshot=snapshot):
                sources[key] = reader.read_luxian_0609_snapshot_source_rows(source_key=key,source_schema="cdm",**coordinates)
                replayed.append(key)
        return snapshot, Luxian0609EvidenceMaterialStore.create(snapshot=snapshot,sources=sources)
    monkeypatch.setattr(acceptance,"_typed_session",frozen_session)
    case = acceptance.CASES[case_index]
    recording = acceptance.synthetic_recording()
    # 每个场景按reference/cascade顺序保存，reference只是固定应答标识。
    response = recording["requests"][case_index*2]["completion"]
    result = await acceptance.formal_replay(monkeypatch,tmp_path,case=case,recordings=[{"completion":response}],arm="reference",mature=mature)
    assert replayed and result["native_status"] == expected
    assert result["saved"]["status"] == expected
    assert result["new_model_calls"] == 0


@pytest.mark.asyncio
async def test_worker_capture_failure_keeps_other_case_results(monkeypatch):
    from types import SimpleNamespace
    from app.services import sichuan_workspace_batch_worker as worker, case_material_capture
    from test_qc_sichuan_batch_throughput import _WorkspaceStub, _ServiceStub
    workspace, service = _WorkspaceStub(), _ServiceStub(status_by_rule={key:"non_compliant" for key in ("SC-001","SC-002","SC-003")})
    captured = []
    def obtain(job_id, identity, **kwargs):
        captured.append(identity)
        if identity[-1] == "visit-001":
            raise material.MaterialSnapshotError("material_source_contract_incomplete")
        value = dataset()
        value["identity"] = list(identity)
        return material.persist(job_id, value)
    def project(**kwargs):
        frozen = material.current()
        assert frozen is not None and frozen["identity"][-1] == "visit-002"
        return {"medical_text":"SYNTHETIC-FROZEN"}
    monkeypatch.setattr(assembly,"engine",SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    monkeypatch.setattr(assembly,"_assemble_scene_bundle",project)
    monkeypatch.setattr(case_material_capture,"obtain",obtain)
    monkeypatch.setattr(worker,"get_product_activation_service",lambda:SimpleNamespace(enforce=lambda:None))
    async def provider():
        return service
    await worker.run_sichuan_workspace_batch_job(workspace.job["id"],workspace=workspace,qc_service_provider=provider)
    assert {identity[-1] for identity in captured} == {"visit-001","visit-002"}
    assert service.evaluate_calls == 1
    assert workspace.items and {item["visit_id"] for item in workspace.items} == {"visit-002"}
    assert workspace.failed_records and all("material_source_contract_incomplete" in row["error"] for row in workspace.failed_records)
    assert workspace.job["status"] != "running"



def test_catalog_no_registration_keeps_unknown_and_date_only(monkeypatch):
    from sqlalchemy import create_engine, text
    from app.services import clinical_case_catalog as catalog
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
            for name in ("mr","admission_record","discharge_record"):
                connection.execute(text(f"CREATE TABLE cdm.{name}(institute_id TEXT,patient_id TEXT,visit_id TEXT,admission_datetime TEXT,admission_date TEXT,discharge_date TEXT)"))
            connection.execute(text("INSERT INTO cdm.admission_record VALUES('I','P1','V1','2026-11-01 08:00:00',NULL,NULL)"))
            connection.execute(text("INSERT INTO cdm.discharge_record VALUES('I','P2','V2',NULL,'2026-11-01','2026-11-03')"))
        monkeypatch.setattr(clinical,"get_engine",lambda:engine)
        unknown = catalog.workstation(hospital_status="unknown",qc_projection_loader=lambda _: {})
        assert unknown["total"] == 1 and unknown["records"][0]["hospitalizationStatus"] == "unknown"
        assert catalog.workstation(hospital_status="inpatient",qc_projection_loader=lambda _: {})["total"] == 0
        discharged = catalog.workstation(hospital_status="discharged",qc_projection_loader=lambda _: {})
        assert discharged["total"] == 1
        row = discharged["records"][0]
        assert row["admissionDate"] == "2026-11-01" and row["admissionPrecision"] == "date"
        assert row["dischargeDate"] == "2026-11-03" and row["dischargeDatetime"] is None
    finally:
        catalog.catalog.cache_clear()
        engine.dispose()



def test_pdf_material_copy_without_business_source_fails_closed(monkeypatch):
    from app.services.case_material_capture import capture
    monkeypatch.setattr(assembly, "engine", None)
    with pytest.raises(material.MaterialSnapshotError,match="material_source_unavailable"):
        capture(identity=("I","pdfp_P","pdfv_V"))
    assert material.load("pdf-task", ("I","pdfp_P","pdfv_V")) is None


@pytest.mark.asyncio
async def test_pdf_history_without_material_is_rejected_not_reloaded(monkeypatch):
    from starlette.requests import Request
    from app.services import clinical_sources, validation_material_source
    monkeypatch.setattr(validation_material_source,"_registered_schema",lambda *_:"pdfmat_012345abcdef")
    def saved_source(request, job_id):
        request.state.material_root_job_id = job_id
        return clinical_sources.legacy_snapshot()
    monkeypatch.setattr(clinical_sources,"source_for_saved_job",saved_source)
    request = Request({"type":"http","method":"GET","path":"/api/v1/emr/pdfv_V/documents",
        "query_string":b"institute_id=I&patient_id=pdfp_P&visit_id=pdfv_V&job_id=PDF-JOB","headers":[]})
    clinical_sources.prepare_request(request)
    monkeypatch.setattr(material, "load", lambda *_: None)
    generator = clinical_sources.bind_request(request)
    from fastapi import HTTPException
    try:
        with pytest.raises(HTTPException, match="historical_material_snapshot_not_retained"):
            await generator.__anext__()
    finally:
        await generator.aclose()




def test_http_history_context_reaches_threaded_document_reader(monkeypatch):
    import asyncio
    from fastapi import Depends, FastAPI, Request
    from fastapi.testclient import TestClient
    from app.routers import emr_render
    from app.services import clinical_sources
    material.persist("HTTP-TASK",dataset("original-http-body"))
    monkeypatch.setattr(emr_render,"customer_safe_projection_key",lambda:"synthetic-key")
    monkeypatch.setattr(emr_render,"load_bundle_documents",lambda **_:pytest.fail("live Bundle reached"))
    app = FastAPI()
    @app.middleware("http")
    async def bound(request, call_next):
        request.state.clinical_source = clinical_sources.legacy_snapshot()
        request.state.material_root_job_id = "HTTP-TASK"
        return await call_next(request)
    @app.get("/documents", dependencies=[Depends(clinical_sources.bind_request)])
    async def read(request: Request):
        assert material.current()["identity"] == list(IDENTITY)
        return await asyncio.to_thread(emr_render._load_documents_from_bundle, record_id=IDENTITY[2],
            institute_id=IDENTITY[0],patient_id=IDENTITY[1],visit_id=IDENTITY[2])
    with TestClient(app) as client:
        response = client.get("/documents",params=dict(zip(("institute_id","patient_id","visit_id"),IDENTITY)))
    assert response.status_code == 200
    assert response.json()["documents"][0]["content"] == "original-http-body"
    assert material.current() is None



def test_history_summary_is_lightweight_and_keeps_document_identity(monkeypatch):
    from app.routers import emr_render
    monkeypatch.setattr(emr_render,"customer_safe_projection_key",lambda:"synthetic-key")
    value = dataset("SYNTHETIC-LONG-BODY"*1000)
    value["documents"]["documents"][0].update(sections=[{"text":"PRIVATE-SECTION"}],render_blocks=[{"text":"PRIVATE-BLOCK"}])
    frozen = material.persist("SUMMARY-TASK",value)
    with material.activate(frozen):
        result = emr_render._load_document_summaries_from_bundle(record_id=IDENTITY[2], institute_id=IDENTITY[0],patient_id=IDENTITY[1],visit_id=IDENTITY[2])
    [summary] = result["documents"]
    assert summary["id"] == "D" and summary["has_content"] is True
    assert result["documents_tree"] == []
    assert not {"content","sections","render_blocks","source_fields"} & set(summary)
