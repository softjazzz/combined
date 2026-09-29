"""自建测试病历创建后固定：源库匹配、同步入口不得改写测试池的病例绑定。"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import qc_sample_pools
from app.services import custom_qc_sample_pool_service as pools
from app.services.custom_qc_sample_pool_service import CUSTOMER_TEST_POOL_ID


def _service_without_db():
    # 拦截发生在任何数据库访问之前，无需真实表。
    return object.__new__(pools.CustomQCSamplePoolService)


def _fail_session():
    raise AssertionError("测试池拦截必须早于数据库访问")


@pytest.fixture(autouse=True)
def _no_database(monkeypatch):
    monkeypatch.setattr(pools, "_session", _fail_session)


_SCOPE_ARGS = dict(
    scope_mode="running",
    as_of_date=date(2026, 9, 29),
    discharge_start_date=None,
    discharge_end_date=None,
    departments=[],
)


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.create_sync_job(pool_id=CUSTOMER_TEST_POOL_ID, created_by="u", payload={}),
        lambda s: s.match_pool_items(pool_id=CUSTOMER_TEST_POOL_ID),
        lambda s: s.match_pool_items_from_source(pool_id=CUSTOMER_TEST_POOL_ID),
        lambda s: s.sync_pool_records(pool_id=CUSTOMER_TEST_POOL_ID),
        lambda s: s.preview_hospitalization_scope(pool_id=CUSTOMER_TEST_POOL_ID, **_SCOPE_ARGS),
        lambda s: s.append_pool_items_by_hospitalization_scope(pool_id=CUSTOMER_TEST_POOL_ID, **_SCOPE_ARGS),
    ],
    ids=["create_sync_job", "match", "match_from_source", "sync_records", "preview_scope", "append_scope"],
)
def test_customer_test_pool_rejects_source_match_and_sync(call):
    with pytest.raises(ValueError, match="创建后固定"):
        call(_service_without_db())


def test_other_pools_are_not_blocked_by_guard():
    pools._reject_customer_test_pool_source_write("some-customer-sample-pool")


@pytest.mark.asyncio
async def test_match_endpoint_returns_422_for_customer_test_pool(monkeypatch):
    service = _service_without_db()
    monkeypatch.setattr(service, "get_pool", lambda *, pool_id: {"id": pool_id}, raising=False)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: service)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.match_sample_pool(
            SimpleNamespace(state=SimpleNamespace()),
            CUSTOMER_TEST_POOL_ID,
            current_user={"id": "u"},
        )

    assert exc_info.value.status_code == 422
    assert "创建后固定" in exc_info.value.detail
