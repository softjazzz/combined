"""门急诊 CDM 身份与授权的独立反例；全部使用明确标记的合成文书。"""

from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import records
from app.services import defect_rectification_service as actor_owner
from app.services import outpatient_cdm_read_service as service
from app.services import outpatient_record_list_service as legacy


BASE = "/api/v1/records/outpatient-emergency"
KEY = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "document_id": "D1"}
LOAD_ACTOR = service.load_actor


def document(**changes):
    return {
        **KEY, "dept_name": "合成内科", "name": "合成患者", "outpat_no": "SYNTHETIC-001",
        "visit_datetime": "2026-10-02T09:00:00+08:00", "visit_type": "门诊",
        "document_name": "合成门诊记录", "record_content": "合成文书正文，不含真实患者信息",
        **changes,
    }


def actor(role="admin", **changes):
    return {"id": "synthetic-user", "roles": {role}, "institute_id": "H1",
            "department": "合成内科", **changes}


class Source:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def table(self, name):
        assert name == "cdm.outpat_record"
        query = Query(self)
        self.queries.append(query)
        return query


class Query:
    def __init__(self, source):
        self.source = source
        self.filters = {}
        self.orders = []
        self.bounds = None
        self.columns = None

    def select(self, fields, *, count):
        assert count == "exact"
        self.columns = fields
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, key, *, desc):
        assert desc is False
        self.orders.append(key)
        return self

    def range(self, start, end):
        self.bounds = (start, end)
        return self


async def execute(query):
    rows = [row for row in query.source.rows
            if all(row.get(key) == value for key, value in query.filters.items())]
    rows = sorted(rows, key=lambda row: tuple(row[key] for key in query.orders))
    start, end = query.bounds
    page = deepcopy(rows[start:end + 1])
    if query.columns != "*":
        page = [{key: row.get(key) for key in query.columns.split(",")} for row in page]
    return SimpleNamespace(data=page, count=len(rows))


def client(monkeypatch, rows, person=None):
    person = person or actor()
    source = Source(rows)
    monkeypatch.setattr(service, "load_actor", lambda user_id: person)
    monkeypatch.setattr(records, "get_supabase", lambda: source)
    monkeypatch.setattr(records, "async_execute", execute)
    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": person["id"], "roles": ["admin"],
    }
    return TestClient(app), source


def detail_request(http, **changes):
    return http.get(f"{BASE}/cdm-detail", params={"source": service.SOURCE, **KEY, **changes})


def test_same_patient_visit_and_document_numbers_in_other_institute_are_not_merged(monkeypatch):
    http, _ = client(monkeypatch, [document(), document(institute_id="H2", record_content="外院合成正文")])
    listing = http.get(BASE, params={"source": service.SOURCE})
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 2
    response = detail_request(http)
    assert response.status_code == 200
    docs = response.json()["data"]["documents"]["raw_documents"]
    assert len(docs) == 1 and docs[0]["institute_id"] == "H1"
    assert "外院" not in response.text
    assert response.json()["data"]["record"]["score"] is None
    assert response.json()["data"]["qc_data_status"] == "unavailable_outpatient_result"


@pytest.mark.parametrize("changes", [
    {"patient_id": "P2"}, {"visit_id": "V2"}, {"document_id": "D2"},
])
def test_coordinates_from_different_cases_do_not_resolve_by_single_number(monkeypatch, changes):
    http, _ = client(monkeypatch, [document(), document(patient_id="P2", visit_id="V2", document_id="D2")])
    assert detail_request(http, **changes).status_code == 404


@pytest.mark.parametrize("role", ["doctor", "qc_manager"])
def test_same_department_in_other_institute_is_forbidden_before_source_read(monkeypatch, role):
    http, source = client(monkeypatch, [document(institute_id="H2")], actor(role))
    assert detail_request(http, institute_id="H2").status_code == 403
    assert source.queries == []


@pytest.mark.parametrize("role", ["doctor", "qc_manager"])
def test_list_binds_persistent_institute_even_when_login_claim_is_admin(monkeypatch, role):
    http, source = client(monkeypatch, [document(), document(institute_id="H2")], actor(role))
    response = http.get(BASE, params={"source": service.SOURCE})
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    assert all(query.filters["institute_id"] == "H1" for query in source.queries)
    if role == "doctor":
        assert all(query.filters["dept_name"] == "合成内科" for query in source.queries)


@pytest.mark.parametrize("role", ["doctor", "qc_manager"])
def test_missing_persistent_institute_fails_closed(monkeypatch, role):
    http, source = client(monkeypatch, [document()], actor(role, institute_id=None))
    assert http.get(BASE, params={"source": service.SOURCE}).status_code == 403
    assert detail_request(http).status_code == 403
    assert source.queries == []


@pytest.mark.parametrize("department", ["合成外科", None, ""])
def test_detail_cannot_use_one_permitted_document_to_read_other_department(monkeypatch, department):
    http, _ = client(monkeypatch, [document(), document(document_id="D2", dept_name=department)], actor("doctor"))
    response = detail_request(http)
    assert response.status_code == 403
    assert "record_content" not in response.text


@pytest.mark.parametrize("missing", ["source", *KEY])
def test_detail_requires_explicit_source_and_every_coordinate(monkeypatch, missing):
    http, source = client(monkeypatch, [document()])
    params = {"source": service.SOURCE, **KEY}
    params.pop(missing)
    assert http.get(f"{BASE}/cdm-detail", params=params).status_code == 422
    assert source.queries == []


@pytest.mark.parametrize("source_name", ["legacy_medical_records", "outpatient", ""])
def test_detail_rejects_other_source_names(monkeypatch, source_name):
    http, source = client(monkeypatch, [document()])
    assert detail_request(http, source=source_name).status_code == 422
    assert source.queries == []


@pytest.mark.parametrize("value", ["", " P1", "P1 ", "P1\n"])
def test_detail_rejects_noncanonical_coordinates_before_read(monkeypatch, value):
    http, source = client(monkeypatch, [document()])
    assert detail_request(http, patient_id=value).status_code == 422
    assert source.queries == []


@pytest.mark.parametrize("filters", [
    {"scoring_standard": "legacy-v1"}, {"status": "passed"},
    {"sort_field": "score"}, {"sort_field": "defect_count"},
])
def test_cdm_does_not_apply_historical_scoring_or_quality_filters(monkeypatch, filters):
    http, source = client(monkeypatch, [document()])
    assert http.get(BASE, params={"source": service.SOURCE, **filters}).status_code == 422
    assert source.queries == []


@pytest.mark.parametrize("active,role,roles_json", [
    (False, "admin", None), (True, "admin", "broken"),
    (True, "admin", "[]"), (True, "admin", '["doctor", null]'),
    (True, "unknown", None), (True, None, None),
])
def test_persisted_inactive_or_invalid_roles_override_login_claims(monkeypatch, active, role, roles_json):
    http, source = client(monkeypatch, [document()])
    row = SimpleNamespace(id="synthetic-user", is_active=active, display_name="合成账号",
                          institute_id="H1", department="合成内科", role=role, roles_json=roles_json)
    session = SimpleNamespace(execute=lambda *_args, **_kwargs: SimpleNamespace(scalar_one_or_none=lambda: row))

    @contextmanager
    def sessions():
        yield session

    monkeypatch.setattr(service, "SessionLocal", sessions)
    monkeypatch.setattr(actor_owner, "user_owner_options", lambda _session: {})
    monkeypatch.setattr(service, "load_actor", LOAD_ACTOR)
    assert detail_request(http).status_code == 403
    assert source.queries == []


@pytest.mark.asyncio
@pytest.mark.parametrize("rows,count", [
    ([document()], None), ([document()], True), ([document()], 2),
    ([document(), document()], 2), ([document(patient_id="P2")], 1),
    ([document(institute_id="H2")], 1), ([document()], 10_001),
])
async def test_bad_count_duplicate_and_foreign_case_response_fail_closed(rows, count):
    async def inconsistent(_query):
        return SimpleNamespace(data=rows, count=count)

    with pytest.raises(legacy.OutpatientRecordSourceUnavailable):
        await service.detail(actor=actor(), source=Source([]), execute=inconsistent, coordinates=KEY)


@pytest.mark.asyncio
async def test_cross_page_count_change_fails_closed(monkeypatch):
    monkeypatch.setattr(service, "PAGE_SIZE", 1)
    responses = iter([
        SimpleNamespace(data=[document()], count=2),
        SimpleNamespace(data=[document(document_id="D2")], count=3),
    ])

    async def changing(_query):
        return next(responses)

    with pytest.raises(legacy.OutpatientRecordSourceUnavailable):
        await service.detail(actor=actor(), source=Source([]), execute=changing, coordinates=KEY)


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", [
    document(record_content="合成复读时正文变化"), document(document_id="D2"),
])
async def test_same_count_body_or_document_replacement_fails_closed(replacement):
    responses = iter([SimpleNamespace(data=[document()], count=1), SimpleNamespace(data=[replacement], count=1)])

    async def changing(_query):
        return next(responses)

    with pytest.raises(legacy.OutpatientRecordSourceUnavailable):
        await service.detail(actor=actor(), source=Source([]), execute=changing, coordinates=KEY)


def test_source_failure_is_not_successful_empty_detail_and_redacts_private_error(monkeypatch):
    http, _ = client(monkeypatch, [document()])

    async def failure(_query):
        raise RuntimeError("synthetic-private-secret")

    monkeypatch.setattr(records, "async_execute", failure)
    response = detail_request(http)
    assert response.status_code == 503
    assert "synthetic-private-secret" not in response.text


@pytest.mark.asyncio
async def test_list_projects_only_metadata_and_rejects_metadata_drift():
    source = Source([document()])
    calls = 0

    async def changing(query):
        nonlocal calls
        calls += 1
        assert "record_content" not in query.columns and query.columns != "*"
        if calls == 2:
            source.rows[0]["name"] = "合成姓名发生变化"
        return await execute(query)

    with pytest.raises(legacy.OutpatientRecordSourceUnavailable):
        await service.query_records(actor=actor(), source=source, execute=changing,
                                    filters=legacy.build_filter(), page=1, page_size=20)


@pytest.mark.asyncio
async def test_list_does_not_read_or_compare_unshown_patient_body():
    source = Source([document()])
    calls = 0

    async def changing(query):
        nonlocal calls
        calls += 1
        assert "record_content" not in query.columns and query.columns != "*"
        source.rows[0]["record_content"] = f"合成未展示正文版本{calls}"
        return await execute(query)

    result = await service.query_records(actor=actor(), source=source, execute=changing,
                                         filters=legacy.build_filter(), page=1, page_size=20)
    assert result.total == 1
    assert "record_content" not in result.items[0]


@pytest.mark.asyncio
async def test_complete_body_byte_limit_rejects_without_truncation(monkeypatch):
    monkeypatch.setattr(service, "MAX_DOCUMENT_BYTES", 1000)
    source = Source([document(record_content="合" * 400)])
    with pytest.raises(legacy.OutpatientRecordSourceUnavailable):
        await service.detail(actor=actor(), source=source, execute=execute, coordinates=KEY)
    assert len(source.queries) == 1


def test_legacy_list_default_still_calls_legacy_owner(monkeypatch):
    http, _ = client(monkeypatch, [])
    calls = []

    async def old_query(**kwargs):
        calls.append(kwargs)
        return legacy.OutpatientRecordPage(items=[], total=0)

    monkeypatch.setattr(legacy, "query_records", old_query)
    assert http.get(BASE).status_code == 200
    assert len(calls) == 1
