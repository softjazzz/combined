from types import SimpleNamespace

import pytest

from app.services import outpatient_cdm_read_service as service
from app.services.outpatient_record_list_service import build_filter, OutpatientRecordInvalid, OutpatientRecordSourceUnavailable
from app.services.defect_rectification_service import RectificationError


def document(institute="I", patient="P", visit="V", doc="D", **values):
    return {"institute_id": institute, "patient_id": patient, "visit_id": visit, "document_id": doc,
            "name": "合成患者", "dept_name": "合成科室", "visit_datetime": "2026-10-02T09:00:00",
            "record_content": "合成全文", **values}


class Database:
    def __init__(self, rows):
        self.rows, self.reads, self.hook = rows, [], None

    def table(self, name):
        assert name == "cdm.outpat_record"
        return Query(self)


class Query:
    def __init__(self, db):
        self.db, self.filters, self.orders = db, {}, []

    def select(self, columns, count):
        assert columns in {"*", service.LIST_COLUMNS} and count == "exact"
        self.columns = columns
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, key, desc):
        assert desc is False
        self.orders.append(key)
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self


async def execute(query):
    db = query.db
    assert tuple(query.orders) == service.COORDINATES
    db.reads.append((dict(query.filters), query.start, query.end))
    rows = [row.copy() for row in db.rows if all(row.get(key) == value for key, value in query.filters.items())]
    rows.sort(key=lambda row: tuple(str(row.get(key)) for key in service.COORDINATES))
    if query.columns != "*":
        rows = [{key: row.get(key) for key in query.columns.split(",")} for row in rows]
    result = SimpleNamespace(data=rows[query.start:query.end + 1], count=len(rows))
    return db.hook(result, len(db.reads)) if db.hook else result


ADMIN = {"id": "admin", "roles": {"admin"}, "institute_id": None, "department": None}
DOCTOR = {"id": "doctor", "roles": {"doctor"}, "institute_id": "I", "department": "合成科室"}


@pytest.mark.asyncio
async def test_same_visit_across_institute_and_patient_never_collapses_or_leaks():
    db = Database([document(), document(doc="D2"), document("I2"), document(patient="P2")])
    page = await service.query_records(actor=ADMIN, source=db, execute=execute, filters=build_filter(), page=1, page_size=20)
    assert page.total == 3
    assert len({row["id"] for row in page.items}) == 3
    detail = await service.detail(actor=ADMIN, source=db, execute=execute, coordinates=document())
    assert [row["document_id"] for row in detail["documents"]["raw_documents"]] == ["D", "D2"]
    assert detail["record"]["score"] is None and detail["record"]["defect_count"] is None


@pytest.mark.asyncio
async def test_full_paging_and_structured_source_fields(monkeypatch):
    monkeypatch.setattr(service, "PAGE_SIZE", 2)
    docs = [document(doc=f"D{index}", chief_complaint="合成主诉", submitter="提交人不是医生", extra_field="完整尾字段") for index in range(5)]
    db = Database(docs)
    payload = await service.detail(actor=DOCTOR, source=db, execute=execute, coordinates=docs[0])
    assert len(db.reads) == 6
    assert payload["record"]["doctor_name"] is None
    assert payload["qc_data_status"] == "unavailable_outpatient_result"
    assert payload["documents"]["raw_documents"][-1]["source_fields"] == docs[-1]


@pytest.mark.parametrize("roles,institute,department", [({"qc_manager"}, None, None), ({"doctor"}, "I", None), ({"sync_admin"}, "I", None), (set(), "I", "合成科室")])
def test_missing_persistent_scope_fails_closed(roles, institute, department):
    with pytest.raises(RectificationError) as caught:
        service.authorize({"roles": roles, "institute_id": institute, "department": department})
    assert caught.value.status == 403


@pytest.mark.asyncio
async def test_doctor_filters_source_and_rejects_cross_department_detail():
    db = Database([document(), document("I2"), document(patient="P2", dept_name="其他科室")])
    page = await service.query_records(actor=DOCTOR, source=db, execute=execute, filters=build_filter(), page=1, page_size=20)
    assert page.total == 1
    assert all(filters == {"institute_id": "I", "dept_name": "合成科室"} for filters, _, _ in db.reads)
    with pytest.raises(RectificationError) as caught:
        await service.detail(actor=DOCTOR, source=db, execute=execute, coordinates=document(patient="P2"))
    assert caught.value.status == 403
    with pytest.raises(RectificationError):
        await service.detail(actor=DOCTOR, source=db, execute=execute, coordinates=document("I2"))


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["count", "duplicate", "replace", "content", "short", "invalid", "limit"])
async def test_source_drift_duplicates_incomplete_or_limit_refused(monkeypatch, mutation):
    monkeypatch.setattr(service, "PAGE_SIZE", 2)
    db = Database([document(doc=f"D{index}") for index in range(3)])
    def hook(result, call):
        if mutation == "count" and call == 2:
            result.count += 1
        if mutation == "duplicate" and call == 2:
            result.data[0]["document_id"] = "D0"
        if mutation in {"replace", "content"} and call == 3:
            result.data[0]["document_id" if mutation == "replace" else "record_content"] = "CHANGED"
        if mutation == "short" and call == 1:
            result.data.pop()
        if mutation == "invalid":
            result.data[0]["patient_id"] = ""
        if mutation == "limit":
            result.count = service.MAX_DOCUMENTS + 1
        return result
    db.hook = hook
    with pytest.raises(OutpatientRecordSourceUnavailable):
        await service.load_documents(source=db, execute=execute)


@pytest.mark.asyncio
@pytest.mark.parametrize("filters", [{"scoring_standard": "历史标准"}, {"status": "approved"}, {"sort_field": "score"}])
async def test_cdm_never_silently_applies_legacy_scoring(filters):
    db = Database([document()])
    with pytest.raises(OutpatientRecordInvalid):
        await service.query_records(actor=ADMIN, source=db, execute=execute, filters=build_filter(**filters), page=1, page_size=20)
    assert not db.reads


def test_conflicting_metadata_and_missing_dates_stay_unknown():
    row = service.record([document(), document(doc="D2", name="另一姓名", dept_name="另一科室", visit_datetime="2026-10-03T09:00:00")])
    assert row["patient_name"] is row["department"] is row["visit_date"] is None
    assert service.record([document(visit_datetime=None)])["visit_date"] is None


@pytest.mark.asyncio
async def test_document_anchor_must_exist_inside_exact_case():
    with pytest.raises(RectificationError) as caught:
        await service.detail(actor=ADMIN, source=Database([document()]), execute=execute, coordinates=document(doc="other"))
    assert caught.value.status == 404


@pytest.mark.asyncio
async def test_list_projection_avoids_full_document_and_detail_size_refuses_truncation(monkeypatch):
    monkeypatch.setattr(service, "MAX_DOCUMENT_BYTES", 100)
    db = Database([document(record_content="完整正文" * 100)])
    page = await service.query_records(actor=ADMIN, source=db, execute=execute, filters=build_filter(), page=1, page_size=20)
    assert page.total == 1
    with pytest.raises(OutpatientRecordSourceUnavailable):
        await service.detail(actor=ADMIN, source=db, execute=execute, coordinates=document())
