"""1026副本任务材料的不可变来源合同；只使用合成身份、配置和临时文件。"""
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from app.database import clinical_connection as clinical, connection as business
from app.services import case_material_snapshot as material

IDENTITY = ("SYNTHETIC-I", "pdfp_SYNTHETIC", "pdfv_SYNTHETIC")


@pytest.fixture
def business_source(monkeypatch, tmp_path):
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    engine = SimpleNamespace(url=make_url("postgresql://synthetic@invalid.test/synthetic"))
    monkeypatch.setattr(business, "engine", engine)
    return engine


def test_pdf_binding_uses_business_source_and_ignores_independent_selection(business_source):
    with clinical.selected({"id": "legacy_pg", "binding": ""}):
        binding = material.source_binding(IDENTITY)
        state = {"protocol": material.PROTOCOL, "identity": list(IDENTITY), "binding": binding,
                 "schema": "pdfmat_012345abcdef", "tables": {"daily_course_record": [{"record_content": "v1"}]}}
        frozen = material.persist("pdf-task", state)
    with clinical.selected({"id": "independent_cdm", "binding": "other-cdm"}):
        assert material.load("pdf-task", IDENTITY)["fingerprint"] == frozen["fingerprint"]
    business_source.url = make_url("postgresql://synthetic@invalid.test/another_source")
    with pytest.raises(material.MaterialSnapshotError, match="source_mismatch"):
        material.load("pdf-task", IDENTITY)


def test_recording_cannot_open_another_source_connection():
    engine = SimpleNamespace(connect=lambda: pytest.fail("跨来源连接不得进入捕获"))
    with material.recording({"engine": object(), "connection": object()}):
        with pytest.raises(material.MaterialSnapshotError, match="source_mismatch"):
            with material.source_connection(engine):
                pass


def test_recording_cannot_create_session_for_another_source():
    with material.recording({"engine": object(), "connection": object()}):
        with pytest.raises(material.MaterialSnapshotError, match="source_mismatch"):
            material.session_bind(object())


def test_pdf_retry_replays_original_without_reopening_current_source(monkeypatch, business_source):
    from app.services import case_material_capture as capture
    state = {"protocol": material.PROTOCOL, "identity": list(IDENTITY),
             "binding": material.source_binding(IDENTITY), "schema": "pdfmat_012345abcdef",
             "tables": {"daily_course_record": [{"record_content": "v1"}]}}
    frozen = material.persist("pdf-original", state)
    monkeypatch.setattr(capture, "capture", lambda **_: pytest.fail("重试不得补造当前材料"))
    assert capture.obtain("pdf-original", IDENTITY, retry=True) == frozen
    with pytest.raises(material.MaterialSnapshotError, match="original_task_material_not_retained"):
        capture.obtain("pdf-old-without-snapshot", IDENTITY, retry=True)


@pytest.mark.parametrize("missing_identity_column", [False, True])
def test_pdf_capture_validates_registry_in_the_single_readonly_transaction(monkeypatch, business_source, missing_identity_column):
    from app.services import case_material_capture as capture, validation_material_source as registry
    from app.services import sample_programmatic_evidence as evidence, daily_material_projection as daily
    from app.services.bundles import assembly, current_view
    from app.services.luxian_0609 import source_evidence_reader as reader
    # 服务模块有函数默认参数引用；先加载，避免临时reader替身泄漏到后续测试。
    from app.services.sichuan_qc_service import SichuanQCService  # noqa: F401

    events = []
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            events.append("closed")
        def execution_options(self, **options):
            assert options == {"isolation_level": "REPEATABLE READ"}
            return self
        def begin(self):
            return nullcontext()
        def begin_nested(self):
            return nullcontext()
        def exec_driver_sql(self, sql):
            events.append(sql)
    connection = Connection()
    business_source.connect = lambda: connection
    monkeypatch.setattr(assembly, "engine", business_source)
    monkeypatch.setattr(assembly, "_material_limits_for_variants", lambda **_: {"daily_course_record": 10})
    def register(conn, identity):
        assert conn is connection and identity == IDENTITY
        assert "SET TRANSACTION READ ONLY" in events
        events.append("registry")
        return {"identity": list(identity), "schema": "pdfmat_012345abcdef", "original_document_ids": ["SYNTHETIC-D"]}
    monkeypatch.setattr(registry, "capture_validation_material", register, raising=False)
    monkeypatch.setattr(registry, "material_source_schema", lambda **_: pytest.fail("登记不能先读当前连接"))
    monkeypatch.setattr(capture, "inspect", lambda conn: SimpleNamespace(
        has_table=lambda table, schema: table == "daily_course_record",
        get_columns=lambda table, schema: [{"name": key} for key in ("institute_id", "patient_id", "visit_id", "document_id", "record_content")
                                           if not (missing_identity_column and key == "institute_id")]))
    def select(**kwargs):
        assert events[-1] == "registry"
        assert material.context()["connection"] is connection
        assert kwargs["schema"] == "pdfmat_012345abcdef"
        return [{"document_id": "SYNTHETIC-D", "record_content": "v1"}] if kwargs["table"] == "daily_course_record" else []
    monkeypatch.setattr(assembly, "_select_records", select)
    monkeypatch.setattr(evidence, "capture_programmatic_sources", lambda state, check: {"daily_course_record": {"rows": state["tables"]["daily_course_record"]}})
    monkeypatch.setattr(current_view, "_assemble_current_documents", lambda **_: {"documents": [{"content": "v1"}]})
    monkeypatch.setattr(daily, "enabled", lambda: True)
    for name in ("read_luxian_0609_course_round_timeline", "has_luxian_0609_current_visit_unstable_order",
                 "read_luxian_0609_severity_order_rows", "read_luxian_0609_exam_lab_order_rows",
                 "read_luxian_0609_rescue_order_rows", "read_luxian_0609_discharge_horizon_rows",
                 "read_luxian_0609_snapshot_source_rows", "read_luxian_0609_native_source_rows",
                 "read_luxian_0609_runtime_source_rows"):
        monkeypatch.setattr(reader, name, lambda **_: None)
    with clinical.selected({"id": "independent_cdm", "binding": "unrelated-source"}):
        if missing_identity_column:
            with pytest.raises(material.MaterialSnapshotError, match="source_mismatch"):
                capture.obtain("pdf-captured", IDENTITY)
            assert material.load("pdf-captured", IDENTITY) is None
            return
        frozen = capture.obtain("pdf-captured", IDENTITY)
    assert events[-1] == "closed"
    assert frozen["schema"] == "pdfmat_012345abcdef"
    assert frozen["validation_material"]["original_document_ids"] == ["SYNTHETIC-D"]
    assert frozen["read_contract"]["read_only"] is True
    assert "daily_material_manifest" not in frozen
    assert "connection" not in frozen and "engine" not in frozen
    assert frozen["programmatic_sources"]["daily_course_record"]["rows"][0]["record_content"] == "v1"


@pytest.mark.asyncio
@pytest.mark.parametrize("retry", [False, True])
async def test_worker_captures_pdf_and_binds_every_result_item(monkeypatch, business_source, retry):
    from app.services import sichuan_workspace_batch_worker as worker, case_material_capture as capture
    from app.services.bundles import assembly
    from test_qc_sichuan_batch_throughput import _WorkspaceStub, _ServiceStub
    workspace = _WorkspaceStub()
    workspace.job["record_ids"] = [IDENTITY[2]]
    workspace.job["record_refs"] = [dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY))]
    workspace.collect_records = lambda **_: [{**dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY)),
                                              "record_id": IDENTITY[2], "scope": "final"}]
    service = _ServiceStub(status_by_rule={key: "non_compliant" for key in ("SC-001", "SC-002", "SC-003")})
    if retry:
        from app.services import clinical_sources, validation_material_source as registry
        from app.services.luxian_0609.clinical_material_policy import CLINICAL_MATERIAL_POLICY_VERSION
        workspace.job["filters"]["record_refs"] = workspace.job["record_refs"]
        workspace.job["filters"]["failed_rule_retry"] = {
            "schema_version": "failed-rule-retry-v1", "record_refs": workspace.job["record_refs"],
            "rule_ids": ["SC-001", "SC-002", "SC-003"], "record_rule_map": {},
        }
        workspace.job["failed_records"] = [
            {**workspace.job["record_refs"][0], "record_id": IDENTITY[2], "rule_id": rule_id, "error": "synthetic_failure"}
            for rule_id in ("SC-001", "SC-002", "SC-003")
        ]
        material.persist(workspace.job["id"], {
            "protocol": material.PROTOCOL, "identity": list(IDENTITY), "binding": material.source_binding(IDENTITY),
            "schema": "pdfmat_012345abcdef", "clinical_material_policy": CLINICAL_MATERIAL_POLICY_VERSION,
            "validation_material": {"schema": "pdfmat_012345abcdef", "identity": list(IDENTITY)},
            "tables": {"inpat_registration": [{"admission_datetime": "2026-11-01 08:00:00"}],
                       "admission_record": [], "discharge_record": []},
        })
        monkeypatch.setattr(clinical_sources, "fixed_cdm", lambda: True)
        monkeypatch.setattr(registry, "_registered_schema", lambda *_: pytest.fail("重试前置不得读当前登记"))
        workspace.collect_records = lambda **_: pytest.fail("重试不得当前collect")
        workspace.hydrate_records_with_medical_text = lambda *_: pytest.fail("重试不得当前hydrate")
    business_source.dialect = SimpleNamespace(name="postgresql")
    monkeypatch.setattr(assembly, "engine", business_source)
    captures = []
    def obtain(job_id, identity, **kwargs):
        captures.append(identity)
        return {"schema": "pdfmat_012345abcdef", "fingerprint": "a" * 64, "identity": list(identity)}
    def project(**kwargs):
        assert material.current()["identity"] == list(IDENTITY)
        return {"medical_text": "SYNTHETIC-FROZEN"}
    monkeypatch.setattr(capture, "obtain", obtain)
    monkeypatch.setattr(assembly, "_assemble_scene_bundle", project)
    monkeypatch.setattr(worker, "get_product_activation_service", lambda: SimpleNamespace(enforce=lambda: None))
    def unexpected_failure(error):
        raise error
    monkeypatch.setattr(worker, "safe_exception_failure", unexpected_failure)
    async def evaluate_fixture(**kwargs):
        return await service.evaluate_document(document_id=IDENTITY[2], content="SYNTHETIC", rule_ids=kwargs.get("rule_ids"))
    monkeypatch.setattr(worker, "evaluate_running_final_bundle", evaluate_fixture)
    async def provider():
        return service
    with clinical.selected({"id": "legacy_pg", "binding": ""}):
        await worker.run_sichuan_workspace_batch_job(workspace.job["id"], workspace=workspace, qc_service_provider=provider)
    assert captures == [IDENTITY]
    assert workspace.items
    assert all(item["case_material_fingerprint"] == "a" * 64 for item in workspace.items)


@pytest.mark.parametrize("saved", [None, "a" * 64, "b" * 64])
def test_worker_binds_receipt_without_overwriting_mismatched_material(saved):
    from app.services.sichuan_workspace_batch_worker import _bind_item_material
    receipt = {"rule_id": "SYNTHETIC-RULE"}
    if saved is not None:
        receipt["material_fingerprint"] = saved
    item = {"applicability_receipt": receipt}
    if saved == "b" * 64:
        with pytest.raises(material.MaterialSnapshotError, match="source_mismatch"):
            _bind_item_material(item, "a" * 64)
    else:
        bound = _bind_item_material(item, "a" * 64)
        assert bound["case_material_fingerprint"] == bound["applicability_receipt"]["material_fingerprint"] == "a" * 64
        assert bound["applicability_receipt"] is not receipt
    assert receipt.get("material_fingerprint") == saved


@pytest.mark.parametrize("condition", ["valid", "missing", "corrupt", "source", "lineage", "selection"])
def test_pdf_retry_preflight_checks_original_task_and_material_without_live_registration(monkeypatch, business_source, condition):
    import json
    from app.services.case_material_capture import pdf_retry_materials
    from app.services import validation_material_source as registry
    from test_material_job_lineage import retry
    ref = dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY))
    original = {"id": "synthetic-origin", "created_by": "synthetic-owner", "filters_json": json.dumps({
        "record_refs": [ref], "_lx0609_attempt_id": "a" * 32}), "parent_job_id": "", "job_kind": "leaf"}
    attempt = retry(original)
    monkeypatch.setattr(registry, "_registered_schema", lambda *_: pytest.fail("重试不得回当前登记"))
    if condition != "missing":
        frozen = material.persist(original["id"], {"protocol": material.PROTOCOL, "identity": list(IDENTITY),
            "binding": material.source_binding(IDENTITY), "schema": "pdfmat_012345abcdef",
            "validation_material": {"schema": "pdfmat_012345abcdef", "identity": list(IDENTITY)}})
    if condition == "corrupt":
        (material.storage_root() / "objects" / (frozen["fingerprint"] + ".json.gz")).write_bytes(b"broken")
    if condition == "source":
        business_source.url = make_url("postgresql://synthetic@invalid.test/other")
    if condition == "lineage":
        filters = json.loads(attempt["filters_json"])
        filters["retry_lineage"]["material_job_id"] = "unrelated"
        attempt["filters_json"] = json.dumps(filters)
    if condition == "selection":
        filters = json.loads(attempt["filters_json"])
        filters["clinical_source"] = {"id": "independent_cdm", "binding": "invalid", "url": "postgresql://synthetic@invalid.test/other"}
        attempt["filters_json"] = json.dumps(filters)
    if condition == "valid":
        assert pdf_retry_materials(attempt, {original["id"]: original}.get)[IDENTITY] == frozen
    else:
        with pytest.raises((material.MaterialSnapshotError, ValueError)):
            pdf_retry_materials(attempt, {original["id"]: original}.get)


def test_ordinary_retry_does_not_enter_pdf_snapshot_bypass(monkeypatch):
    from app.services.case_material_capture import pdf_retry_materials
    monkeypatch.setattr(material, "load", lambda *_: pytest.fail("普通来源不得借PDF准入"))
    assert pdf_retry_materials({"id": "ordinary", "filters": {"retry_lineage": {},
        "record_refs": [{"institute_id": "I", "patient_id": "P", "visit_id": "V"}]}}, lambda _: None) is None


def test_pdf_retry_does_not_relabel_unknown_lookup_value_error():
    from app.services.case_material_capture import pdf_retry_materials
    from test_material_job_lineage import retry
    import json
    origin = {"id": "synthetic-origin", "created_by": "synthetic-owner", "filters_json": json.dumps({
        "record_refs": [dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY))],
        "_lx0609_attempt_id": "a" * 32}), "parent_job_id": "", "job_kind": "leaf"}
    error = ValueError("retry_lineage_source_unavailable")
    def unexpected(_):
        raise error
    with pytest.raises(ValueError) as caught:
        pdf_retry_materials(retry(origin), unexpected)
    assert caught.value is error and not isinstance(caught.value, material.MaterialSnapshotError)


@pytest.mark.parametrize("wrong_identity", [False, True])
def test_pdf_retry_restores_private_identity_only_from_frozen_full_rows(wrong_identity):
    from app.services.sichuan_workspace_batch_worker import _capture_frozen_pdf_identities
    from app.services.luxian_0609.privacy_identity_context import _Luxian0609IdentityCollector
    from app.services.case_identity import CaseRef
    row = {**dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY)),
           "name": "合成姓名", "contact_name": "合成联系人", "contact_address": "合成地址"}
    if wrong_identity:
        row["patient_id"] = "pdfp_OTHER"
    state = {"programmatic_sources": {key: {"rows": [row] if key == "admission_record" else []}
             for key in ("inpat_registration", "admission_record", "discharge_record")}}
    collector = _Luxian0609IdentityCollector()
    if wrong_identity:
        with pytest.raises(material.MaterialSnapshotError, match="source_mismatch"):
            _capture_frozen_pdf_identities(collector, IDENTITY, state)
    else:
        _capture_frozen_pdf_identities(collector, IDENTITY, state)
        assert {"合成姓名", "合成联系人", "合成地址"}.issubset(collector.provider_for_case(CaseRef(*IDENTITY))())
