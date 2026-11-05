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
