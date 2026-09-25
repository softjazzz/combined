"""旧 QC 单坐标读取端点不得认领现代三坐标结果。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import qc


_ADMIN = {"id": "admin-1", "email": "admin@medqc.com", "roles": ["admin"]}


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def _patch_reads(monkeypatch, rows) -> None:
    monkeypatch.setattr(qc, "get_supabase", lambda: MagicMock())
    monkeypatch.setattr(
        qc, "async_execute", AsyncMock(return_value=SimpleNamespace(data=rows))
    )


@pytest.mark.asyncio
async def test_result_hides_modern_identity_row(monkeypatch):
    """单坐标 result 端点命中现代行时必须 fail-closed 返回 404。"""
    _patch_reads(monkeypatch, [{
        "id": "modern", "record_id": "record-1", "identity_version": 1,
        "source_key": "settlement_qc", "patient_id": "patient-b",
    }])

    with pytest.raises(HTTPException) as exc:
        await qc.get_result("record-1", current_user=dict(_ADMIN))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_result_keeps_legacy_row_compatible(monkeypatch):
    """无 identity_version 的旧行仍可被单坐标端点读取。"""
    _patch_reads(monkeypatch, [{
        "id": "legacy", "record_id": "record-1", "overall_score": 88,
    }])

    response = await qc.get_result("record-1", current_user=dict(_ADMIN))
    assert response["id"] == "legacy"


@pytest.mark.asyncio
async def test_history_drops_modern_rows(monkeypatch):
    """旧历史端点只返回旧行，不暴露现代三坐标结果。"""
    _patch_reads(monkeypatch, [
        {"id": "legacy", "record_id": "record-1"},
        {
            "id": "modern", "record_id": "record-2", "identity_version": 1,
            "source_key": "settlement_qc",
        },
    ])

    response = await qc.get_history(_request(), current_user=dict(_ADMIN))
    assert [item["id"] for item in response["data"]["items"]] == ["legacy"]
    assert response["data"]["total"] == 1


@pytest.mark.asyncio
async def test_history_runs_when_identity_column_absent(monkeypatch):
    """旧表尚无 identity_version 列时，历史端点仍可正常运行。"""
    _patch_reads(monkeypatch, [
        {"id": "legacy-a", "record_id": "record-1"},
        {"id": "legacy-b", "record_id": "record-2"},
    ])

    response = await qc.get_history(_request(), current_user=dict(_ADMIN))
    assert [item["id"] for item in response["data"]["items"]] == [
        "legacy-a",
        "legacy-b",
    ]
    assert response["data"]["total"] == 2


@pytest.mark.asyncio
async def test_history_requires_qc_read_permission(monkeypatch):
    read = AsyncMock()
    monkeypatch.setattr(qc, "async_execute", read)

    with pytest.raises(HTTPException) as exc:
        await qc.get_history(_request(), current_user=None)
    assert exc.value.status_code == 401
    read.assert_not_awaited()
