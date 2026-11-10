"""首页导出权限冲突不能被改写成来源故障；全程禁网/内存。"""
import asyncio
import pytest
from fastapi import HTTPException
from starlette.requests import Request


def test_actual_export_route_preserves_institute_conflict(monkeypatch):
    from app.routers import medical_records_export as route
    from app.database import clinical_connection
    monkeypatch.setattr(clinical_connection, "configured", lambda: True)
    monkeypatch.setattr(route, "get_frontpage_sheet", lambda *a, **k: pytest.fail("冲突不允许读取材料"))
    request = Request({"type":"http", "method":"GET", "path":"/frontpage-sheet/P/V", "headers":[], "query_string":b"institute_id=OTHER"})
    request.state.doctor_case_identity = {"institute_id":"OWN"}
    with pytest.raises(HTTPException) as error:
        asyncio.run(route.get_frontpage_sheet_api(request, "P", "V"))
    assert error.value.status_code == 403
    assert error.value.detail == "clinical_case_identity_forbidden"


@pytest.mark.parametrize("status", [403,404,409])
def test_http_exception_identity_preserved(status):
    from app.routers.medical_records_common import raise_medical_records_http_error
    original = HTTPException(status,"controlled",headers={"X-Test":"preserved"})
    with pytest.raises(HTTPException) as error:
        raise_medical_records_http_error(original)
    assert error.value is original


def test_unknown_source_error_still_sanitized(monkeypatch):
    from app.routers.medical_records_common import raise_medical_records_http_error
    from app.database import clinical_connection
    monkeypatch.setattr(clinical_connection, "configured", lambda: True)
    with pytest.raises(HTTPException) as error:
        raise_medical_records_http_error(RuntimeError("private detail"))
    assert error.value.status_code == 503
    assert error.value.detail == "clinical_source_read_unavailable"
