"""固定提交复审 F1：合成同号不同身份，禁止旧缓存补机构后交付。"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import records
from app.services import saved_result_access
from test_records_qc_detail_canonical import _FakeEngine


IDENTITY = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
PRIVATE = "SYNTHETIC-H2-PRIVATE-CONTENT"


def _install_cdm(monkeypatch, rows_by_model, *, fail_model=None):
    class Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *_):
            return self

        def with_entities(self, *_):
            return self

        def distinct(self):
            return self

        def limit(self, *_):
            return self

        def all(self):
            if self.model is fail_model:
                raise RuntimeError("synthetic unavailable clinical source")
            return [SimpleNamespace(**row) for row in rows_by_model.get(self.model, [])]

        def first(self):
            return next(iter(self.all()), None)

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(records, "SessionLocal", Session)
    monkeypatch.setattr(records, "clinical_query", lambda _session, model: Query(model))


@pytest.mark.parametrize("other_model", [records.MedicalRecordFrontpage, records.AdmissionRecord])
def test_single_number_rejects_same_table_and_cross_model_identity_ambiguity(monkeypatch, other_model):
    rows = {records.MedicalRecordFrontpage: [IDENTITY]}
    rows.setdefault(other_model, []).append({"institute_id": "H2", "patient_id": "P2", "visit_id": "V1"})
    _install_cdm(monkeypatch, rows)
    assert records._resolve_visit_identity("V1") == {}


def test_single_number_deduplicates_same_full_identity_documents(monkeypatch):
    _install_cdm(monkeypatch, {model: [IDENTITY, IDENTITY] for model in (
        records.MedicalRecordFrontpage, records.DischargeRecord, records.AdmissionRecord,
    )})
    assert records._resolve_visit_identity("V1") == IDENTITY


def test_single_number_original_identity_does_not_require_frontpage_row(monkeypatch):
    _install_cdm(monkeypatch, {records.AdmissionRecord: [IDENTITY]})
    assert records._resolve_visit_identity("V1") == IDENTITY


def test_single_number_source_failure_is_not_unique_identity_proof(monkeypatch):
    _install_cdm(monkeypatch, {records.MedicalRecordFrontpage: [IDENTITY]}, fail_model=records.AdmissionRecord)
    assert records._resolve_visit_identity("V1") == {}


class _Cache:
    def __init__(self):
        self.queries = []

    def table(self, name):
        self.queries.append(name)
        return self

    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: self


def _install_detail(monkeypatch, *, scope="H1", surface="batch", state="unavailable"):
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _actor: scope)
    monkeypatch.setattr(records, "_resolve_visit_identity", lambda _: dict(IDENTITY))
    monkeypatch.setattr(records, "_load_bundle_payload_for_record", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(records, "get_settings", lambda: SimpleNamespace(RECORDS_TABLE="records", DOCUMENTS_TABLE="documents"))
    monkeypatch.setattr(records, "_load_luxian_0609_review_items_from_canonical", lambda *_args, **_kwargs: {
        "review_items": [], "state": state,
    })
    monkeypatch.setattr(records, "medical_records_db", {"V1": {"id": "V1", "content": PRIVATE}} if surface == "memory" else {})
    cache = _Cache()
    monkeypatch.setattr(records, "get_supabase", lambda: cache if surface == "supabase" else None)

    async def cache_execute(_query):
        # 旧表只有单号，当前CDM的H1不能补进这条无归属记录。
        return SimpleNamespace(data=[{"id": "legacy", "record_id": "V1", "content": PRIVATE, "findings": PRIVATE}])

    monkeypatch.setattr(records, "async_execute", cache_execute)
    engine = _FakeEngine([{
        "id": "H2-newest-job", "created_at": "2026-11-14", "filters_json": {},
        "items_json": [{"record_id": "V1", "institute_id": "H2", "patient_id": "P2",
                        "rule_code": "LEGACY-1", "status": "non_compliant", "findings": PRIVATE}],
    }] if surface == "batch" else [])
    monkeypatch.setattr(records, "engine", engine)
    return cache, engine


def _call():
    return asyncio.run(records.get_record_qc_detail(
        request=SimpleNamespace(state=SimpleNamespace()), record_id="V1",
        current_user={"id": "synthetic-manager", "roles": ["qc_manager"]},
    ))


@pytest.mark.parametrize("surface", ["batch", "memory", "supabase"])
@pytest.mark.parametrize("state", ["unavailable", "identity_ambiguous", "identity_conflict"])
def test_scoped_authorization_does_not_authorize_unbound_legacy_returns(monkeypatch, surface, state):
    cache, engine = _install_detail(monkeypatch, surface=surface, state=state)
    response = _call()
    assert PRIVATE not in repr(response)
    assert response["data"]["review_result_state"] == records._controlled_review_state(state)
    assert cache.queries == []
    assert engine.executed == []


@pytest.mark.parametrize("surface", ["batch", "memory", "supabase"])
def test_global_scope_keeps_existing_legacy_delivery(monkeypatch, surface):
    _install_detail(monkeypatch, scope=None, surface=surface)
    assert PRIVATE in repr(_call())


@pytest.mark.parametrize("canonical_patient", ["P1", "P2"])
def test_scoped_detail_binds_authorized_identity_to_bundle_and_canonical(monkeypatch, canonical_patient):
    _install_detail(monkeypatch)
    captured = []

    def bundle(_record_id, *, authorized_identity=None):
        captured.append(authorized_identity)
        return {"documents": [{"document_type": "admission", "content": "合成本院正文"}]}

    def canonical(_record_id, *, authorize_identity):
        authorize_identity(("H1", canonical_patient, "V1"))
        return {"review_items": [{"status": "compliant"}], "state": "ready"}

    monkeypatch.setattr(records, "_load_bundle_payload_for_record", bundle)
    monkeypatch.setattr(records, "_load_luxian_0609_review_items_from_canonical", canonical)
    if canonical_patient == "P2":
        with pytest.raises(HTTPException) as caught:
            _call()
        assert caught.value.status_code == 403
    else:
        assert _call()["data"]["review_items"] == [{"status": "compliant"}]
    assert captured == [IDENTITY]


def test_scoped_route_rejects_ambiguous_number_before_any_payload_read(monkeypatch):
    original_resolver = records._resolve_visit_identity
    _install_detail(monkeypatch)
    monkeypatch.setattr(records, "_resolve_visit_identity", original_resolver)
    _install_cdm(monkeypatch, {records.MedicalRecordFrontpage: [
        IDENTITY, {"institute_id": "H2", "patient_id": "P2", "visit_id": "V1"},
    ]})
    monkeypatch.setattr(records, "_load_bundle_payload_for_record", lambda *_args, **_kwargs: pytest.fail("歧义单号不得读取正文"))
    monkeypatch.setattr(records, "get_supabase", lambda: pytest.fail("歧义单号不得读取旧缓存"))
    with pytest.raises(HTTPException) as caught:
        _call()
    assert caught.value.status_code == 403
