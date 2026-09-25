"""旧文书单键读取不得认领现代三坐标质控结果。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import medical_documents


_ADMIN = {"id": "admin-1", "email": "admin@medqc.com", "roles": ["admin"]}


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


@pytest.mark.asyncio
async def test_document_result_hides_modern_identity_row(monkeypatch):
    monkeypatch.setattr(medical_documents, "get_supabase", lambda: MagicMock())
    monkeypatch.setattr(
        medical_documents,
        "async_execute",
        AsyncMock(return_value=SimpleNamespace(data=[{
            "id": "modern", "record_id": "document-1", "identity_version": 1,
            "source_key": "settlement_qc", "patient_id": "patient-b",
        }])),
    )

    with pytest.raises(HTTPException) as exc:
        await medical_documents.get_document_qc_results(
            _request(), "document-1", current_user=dict(_ADMIN)
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_document_result_keeps_legacy_row_compatible(monkeypatch):
    monkeypatch.setattr(medical_documents, "get_supabase", lambda: MagicMock())
    monkeypatch.setattr(
        medical_documents,
        "async_execute",
        AsyncMock(return_value=SimpleNamespace(data=[{
            "id": "legacy", "record_id": "document-1",
        }])),
    )

    response = await medical_documents.get_document_qc_results(
        _request(), "document-1", current_user=dict(_ADMIN)
    )
    assert response["data"]["id"] == "legacy"


@pytest.mark.asyncio
async def test_document_result_requires_qc_read_permission(monkeypatch):
    read = AsyncMock()
    monkeypatch.setattr(medical_documents, "async_execute", read)

    with pytest.raises(HTTPException) as exc:
        await medical_documents.get_document_qc_results(
            _request(), "document-1", current_user=None
        )
    assert exc.value.status_code == 401
    read.assert_not_awaited()
