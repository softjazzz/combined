"""源科室读取使用固定应答；源连接等待不能阻塞Web事件循环。"""
import asyncio
import threading

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import sync as router
from app.services import etl_sync


def request():
    return Request({"type": "http", "method": "GET", "path": "/api/v1/sync/departments", "headers": []})


@pytest.mark.asyncio
async def test_waiting_for_source_departments_does_not_block_other_requests(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    progressed = []

    def read_source(limit):
        assert limit == 500
        entered.set()
        progressed.append(release.wait(.5))
        return {"items": ["合成科室"], "schema": "synthetic", "source_table": "discharge_record", "source_column": "dept_name"}

    async def independent_request():
        for _ in range(100):
            if entered.is_set():
                release.set()
                return
            await asyncio.sleep(.001)
        pytest.fail("未进入源科室读取")

    monkeypatch.setattr(etl_sync, "list_remote_departments", read_source)
    result, _ = await asyncio.gather(router.get_departments(request(), {}), independent_request())
    assert progressed == [True], "源科室查询阻塞了事件循环，其他请求无法继续"
    assert result["data"]["items"] == ["合成科室"]
    assert result["data"]["source"] == "pg"
    assert result["data"]["meta"]["source_table"] == "discharge_record"


@pytest.mark.asyncio
@pytest.mark.parametrize("error,status", [(etl_sync.psycopg2.OperationalError("synthetic timeout"), 503), (ValueError("synthetic source not configured"), 422)])
async def test_source_failure_remains_failure_without_local_fallback(monkeypatch, error, status):
    calls = []

    def fail_source(limit):
        calls.append(limit)
        raise error

    monkeypatch.setattr(etl_sync, "list_remote_departments", fail_source)
    with pytest.raises(HTTPException) as raised:
        await router.get_departments(request(), {})
    assert raised.value.status_code == status
    assert calls == [500]
