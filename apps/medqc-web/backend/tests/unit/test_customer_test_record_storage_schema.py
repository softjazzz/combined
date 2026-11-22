"""自建病例来源及API失败合同，固定应答、零数据库。"""

import pytest
from starlette.requests import Request
from fastapi import HTTPException
from app.services.customer_test_storage import (
    business_material_operation,
    CustomerTestStorageError,
)


def test_explicit_business_source_restored_after_error():
    from app.database import clinical_connection
    from app.services.clinical_sources import legacy_snapshot

    outer = {"id": "independent_cdm", "binding": "synthetic"}

    @business_material_operation
    def fail():
        assert clinical_connection.current_selection() == legacy_snapshot()
        raise CustomerTestStorageError("synthetic")

    with clinical_connection.selected(outer):
        with pytest.raises(CustomerTestStorageError):
            fail()
        assert clinical_connection.current_selection() == outer


@pytest.mark.asyncio
async def test_material_failure_is_http_503_not_synced(monkeypatch):
    from app.routers import qc_sample_pools as router

    class Service:
        def create_customer_test_record(self, **kwargs):
            raise CustomerTestStorageError(
                "customer_material_permissions:cdm.exam_item_report"
            )

    monkeypatch.setattr(router, "_service", lambda: Service())
    payload = router.TestRecordCreateRequest(
        case_title="synthetic",
        basic_info=router.TestRecordBasicInfo(
            patient_name="synthetic",
            department="synthetic",
            admission_time="2026-01-01T08:00:00",
        ),
        documents=[
            router.TestRecordDocument(
                document_type="admission_record", title="synthetic", content="synthetic"
            )
        ],
    )
    with pytest.raises(HTTPException) as error:
        await router.create_test_record(
            Request({"type": "http", "headers": []}), payload, {"id": "synthetic"}
        )
    assert error.value.status_code == 503
    assert error.value.detail == "customer_material_permissions:cdm.exam_item_report"


class _ReflectedSuccessfully(CustomerTestStorageError):
    """仅在真实创建器通过真实字段校验后终止，不执行任何业务DML。"""


def _check_creator_materials(monkeypatch, documents, *, expected_organization=None):
    from datetime import datetime
    from types import SimpleNamespace
    from app.database.models import cdm
    from app.database import connection
    from app.services import customer_test_storage as storage
    from app.services import custom_qc_sample_pool_service as pool

    models = {table.name: table for table in cdm.Base.metadata.tables.values()}
    monkeypatch.setattr(connection, "DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(pool, "engine", object())
    physical = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
        execute=lambda *a, **k: SimpleNamespace(scalar=lambda: True),
    )
    session = SimpleNamespace(
        connection=lambda: physical, rollback=lambda: None, close=lambda: None
    )
    monkeypatch.setattr(pool, "_session", lambda: session)

    def reflect(name, metadata, *, schema, autoload_with):
        assert schema == "cdm" and autoload_with is physical
        return models[name]

    monkeypatch.setattr(storage.sa, "Table", reflect)
    seen = {}

    def checked(current_session, rows):
        tables = storage.reflect_materials(current_session, rows)
        seen.update(rows)
        if expected_organization is not None:
            row = rows["mr"][0]
            assert (row["institute_county_desc"], row["institute_code"]) == expected_organization
        for row in [
            r
            for name, values in rows.items()
            if name
            not in {"patient_information", "inpat_registration", "mr", "diagnosis"}
            for r in values
        ]:
            if row["document_title"].startswith("submit-only"):
                assert row.get("record_datetime") is None
                assert row.get("record_time") is None
                assert row["submit_datetime"] == datetime(2026, 1, 3, 10, 0)
        assert tables
        raise _ReflectedSuccessfully("captured_after_real_reflection")

    monkeypatch.setattr(pool, "reflect_materials", checked)
    service = object.__new__(pool.CustomQCSamplePoolService)
    service.create_customer_test_record(
        payload={
            "basic_info": {
                "patient_name": "synthetic",
                "department": "synthetic",
                "admission_time": "2026-01-01T08:00:00",
            },
            "evaluation_as_of_date": "2026-01-04",
            "documents": documents,
        },
        created_by="synthetic",
    )
    return seen


def _time_document(kind, explicit=False):
    return {
        "document_type": kind,
        "title": ("explicit" if explicit else "submit-only") + kind,
        "content": "synthetic-" + kind,
        "submit_time": "2026-01-03T10:00:00",
        **({"record_time": "2026-01-03T09:00:00"} if explicit else {}),
    }


@pytest.mark.parametrize(
    "kind", ["discharge_record", "senior_course_record", "surgery_record"]
)
@pytest.mark.parametrize("explicit", [False, True])
def test_actual_creator_distinguishes_submit_only_from_explicit_record_time(
    monkeypatch, kind, explicit
):
    if explicit:
        with pytest.raises(
            CustomerTestStorageError, match="customer_material_time_column:cdm." + kind
        ):
            _check_creator_materials(monkeypatch, [_time_document(kind, True)])
    else:
        with pytest.raises(_ReflectedSuccessfully):
            _check_creator_materials(monkeypatch, [_time_document(kind)])


def test_mixed_submit_only_documents_do_not_invent_record_clock(monkeypatch):
    docs = [
        _time_document(kind)
        for kind in ["discharge_record", "senior_course_record", "surgery_record"]
    ]
    docs.append(_time_document("admission_record", True))
    with pytest.raises(_ReflectedSuccessfully):
        _check_creator_materials(monkeypatch, docs)


def test_customer_test_record_uses_deployment_organization(monkeypatch):
    monkeypatch.setenv("MEDQC_HOSPITAL_NAME", "新区医院")
    monkeypatch.setenv("MEDQC_HOSPITAL_CODE", "SITE-B-CODE")
    with pytest.raises(_ReflectedSuccessfully):
        _check_creator_materials(
            monkeypatch, [_time_document("discharge_record")],
            expected_organization=("新区医院", "SITE-B-CODE"),
        )


@pytest.mark.parametrize("explicit_first", [False, True])
def test_any_explicit_record_clock_without_storage_refuses_mixed_rows(
    monkeypatch, explicit_first
):
    docs = [
        _time_document("senior_course_record", value)
        for value in [explicit_first, not explicit_first]
    ]
    with pytest.raises(
        CustomerTestStorageError,
        match="customer_material_time_column:cdm.senior_course_record",
    ):
        _check_creator_materials(monkeypatch, docs)
