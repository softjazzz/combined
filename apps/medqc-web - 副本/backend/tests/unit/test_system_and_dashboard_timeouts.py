import asyncio

import pytest

from app.routers import dashboard_api, system


class _DummyQuery:
    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self


class _DummySupabase:
    def table(self, *args, **kwargs):
        return _DummyQuery()


@pytest.mark.asyncio
async def test_health_probe_skips_remote_check_by_default(monkeypatch):
    monkeypatch.setattr(system, "_HEALTH_REMOTE_CHECK_ENABLED", False)
    monkeypatch.setitem(system._llm_health_cache, "expires_at", 0.0)
    monkeypatch.setitem(system._llm_health_cache, "llm_ok", False)

    called = False

    async def _unexpected_call(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("remote probe should not run")

    monkeypatch.setattr(system, "async_execute", _unexpected_call)

    result = await system._get_llm_health_cached(_DummySupabase())

    assert result is False
    assert called is False


@pytest.mark.asyncio
async def test_dashboard_db_stats_timeout_returns_none(monkeypatch):
    monkeypatch.setattr(dashboard_api, "_DB_STATS_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(dashboard_api, "get_supabase", lambda: _DummySupabase())

    async def _slow_execute(*args, **kwargs):
        await asyncio.sleep(0.05)
        return None

    monkeypatch.setattr(dashboard_api, "async_execute", _slow_execute)

    result = await dashboard_api._get_db_stats()

    assert result is None
