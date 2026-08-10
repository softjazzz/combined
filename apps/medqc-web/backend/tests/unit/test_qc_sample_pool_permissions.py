from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers import qc_sample_pools


class _PoolListService:
    def list_pools(self, *, page: int, page_size: int, query: str | None):
        return SimpleNamespace(items=[], total=0, page=page, page_size=page_size)


@pytest.fixture(autouse=True)
def _auth_and_service_overrides(client, monkeypatch):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: _PoolListService())
    yield
    client.app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.api
def test_sample_pool_role_contract_allows_sync_admin_but_rejects_doctor(client):
    def _set_role(role: str) -> None:
        client.app.dependency_overrides[get_current_user] = lambda: {
            "id": f"user-{role}",
            "email": f"{role}@test.local",
            "roles": [role],
        }

    _set_role("sync_admin")
    assert client.get("/api/v1/qc/sample-pools").status_code == 200

    _set_role("doctor")
    assert client.get("/api/v1/qc/sample-pools").status_code == 403
