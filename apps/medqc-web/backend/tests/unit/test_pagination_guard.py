import pytest
from unittest.mock import MagicMock, patch

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user


@pytest.fixture(autouse=True)
def _pagination_auth_overrides(client):
    async def _noop_auth_gate():
        return None

    def _admin_user():
        return {
            "id": "test-user",
            "user_id": "test-user",
            "display_name": "Test User",
            "roles": ["admin", "qc_manager", "doctor", "reviewer"],
        }

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    client.app.dependency_overrides[get_current_user] = _admin_user
    yield
    client.app.dependency_overrides.pop(enforce_default_auth, None)
    client.app.dependency_overrides.pop(get_current_user, None)


def _assert_validation_shell(response, expected_field: str):
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "VALIDATION_ERROR"
    assert body["trace_id"]
    assert body["error"] == "请求参数验证失败"
    assert any(expected_field in item["field"] for item in body["details"])


class TestMedicalRecordsPaginationGuard:
    def test_list_defaults_to_shared_page_size(self, client):
        repo = MagicMock()
        repo.list_patients.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }

        with patch("app.services.medical_records.query_service.get_repository", return_value=repo):
            response = client.get("/api/medical-records/list")

        assert response.status_code == 200
        repo.list_patients.assert_called_once_with(
            dept=None,
            keyword=None,
            start_date=None,
            end_date=None,
            page=1,
            page_size=20,
        )
        assert response.json()["page_size"] == 20

    def test_list_rejects_page_size_overflow(self, client):
        repo = MagicMock()

        with patch("app.services.medical_records.query_service.get_repository", return_value=repo):
            response = client.get("/api/medical-records/list?page_size=101")

        _assert_validation_shell(response, "page_size")
        repo.list_patients.assert_not_called()

    def test_list_rejects_invalid_page(self, client):
        repo = MagicMock()

        with patch("app.services.medical_records.query_service.get_repository", return_value=repo):
            response = client.get("/api/medical-records/list?page=0")

        _assert_validation_shell(response, "page")
        repo.list_patients.assert_not_called()

    def test_departments_use_repository_lookup(self, client):
        repo = MagicMock()
        repo.list_departments.return_value = ["心内科", "外二科"]

        with patch("app.services.medical_records.query_service.get_repository", return_value=repo):
            response = client.get("/api/medical-records/departments")

        assert response.status_code == 200
        assert response.json() == ["心内科", "外二科"]
        repo.list_departments.assert_called_once()


class TestSettlementPaginationGuard:
    def test_list_defaults_to_shared_page_size(self, client):
        svc = MagicMock()
        svc.list_settlements.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }

        with patch("app.routers.settlement.get_settlement_service", return_value=svc):
            response = client.get("/api/medical-records/settlement/list")

        assert response.status_code == 200
        svc.list_settlements.assert_called_once_with(
            dept=None,
            keyword=None,
            page=1,
            page_size=20,
        )
        assert response.json()["page_size"] == 20

    def test_list_rejects_page_size_overflow(self, client):
        svc = MagicMock()

        with patch("app.routers.settlement.get_settlement_service", return_value=svc):
            response = client.get("/api/medical-records/settlement/list?page_size=101")

        _assert_validation_shell(response, "page_size")
        svc.list_settlements.assert_not_called()

    def test_list_rejects_invalid_page(self, client):
        svc = MagicMock()

        with patch("app.routers.settlement.get_settlement_service", return_value=svc):
            response = client.get("/api/medical-records/settlement/list?page=0")

        _assert_validation_shell(response, "page")
        svc.list_settlements.assert_not_called()
