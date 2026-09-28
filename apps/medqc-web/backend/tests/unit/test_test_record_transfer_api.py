from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import qc_sample_pools as routes


BASE = "/api/v1/qc/sample-pools/test-records"


def _client(role: str = "qc_manager") -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": f"user-{role}", "roles": [role],
    }
    return TestClient(app)


def test_export_returns_xlsx_headers_and_audits_counts_only(monkeypatch):
    audits = []
    captured = {}

    def export(**kwargs):
        captured.update(kwargs)
        return b"xlsx", 2

    monkeypatch.setattr(routes, "export_customer_test_records", export)
    monkeypatch.setattr(routes, "_current_version_rule_ids", lambda: {"LX0609-001"})
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))
    response = _client().post(f"{BASE}/export", json={"item_ids": ["ct-1", "ct-2"]})
    assert response.status_code == 200
    assert response.content == b"xlsx"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].endswith("V3.6-test-records.xlsx")
    assert captured == {
        "item_ids": ["ct-1", "ct-2"], "allowed_rule_ids": {"LX0609-001"},
    }
    assert audits[0]["details"] == {"selected_count": 2, "exported_count": 2}


def test_copy_forwards_cas_actor_and_returns_create_receipt(monkeypatch):
    captured = {}
    audits = []

    def copy(**kwargs):
        captured.update(kwargs)
        return {
            "item": {"id": "ct-copy"}, "visit_id": "CUSTOMER_TEST_NEW",
            "source_item_id": "ct-source", "source_updated_at": kwargs["expected_updated_at"],
        }

    monkeypatch.setattr(routes, "copy_customer_test_record", copy)
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))
    response = _client().post(f"{BASE}/ct-source/copy", json={
        "updated_at": "2026-09-28T08:00:00", "case_title": "副本",
    })
    assert response.status_code == 200
    assert response.json()["data"]["item"]["id"] == "ct-copy"
    assert captured == {
        "item_id": "ct-source", "expected_updated_at": "2026-09-28T08:00:00",
        "case_title": "副本", "created_by": "user-qc_manager",
    }
    assert audits[0]["details"] == {
        "source_item_id": "ct-source", "created_item_id": "ct-copy",
    }


def test_copy_unknown_result_is_audited_without_success_receipt(monkeypatch):
    audits = []

    def copy(**_kwargs):
        raise routes.CustomerTestRecordCopyResultUnknown(
            "测试病历可能已复制，请勿重试；请刷新列表并按来源或名称核对"
        )

    monkeypatch.setattr(routes, "copy_customer_test_record", copy)
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))
    response = _client().post(f"{BASE}/ct-source/copy", json={
        "updated_at": "2026-09-28T08:00:00",
    })

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "copy_result_unknown",
        "message": "测试病历可能已复制，请勿重试；请刷新列表并按来源或名称核对",
    }
    assert [item["outcome"] for item in audits] == ["unknown"]


def test_sync_admin_cannot_export_or_copy(monkeypatch):
    monkeypatch.setattr(
        routes, "export_customer_test_records",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不应导出")),
    )
    monkeypatch.setattr(
        routes, "copy_customer_test_record",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不应复制")),
    )
    client = _client("sync_admin")
    assert client.post(f"{BASE}/export", json={"item_ids": ["ct-1"]}).status_code == 403
    assert client.post(
        f"{BASE}/ct-1/copy", json={"updated_at": "2026-09-28T08:00:00"},
    ).status_code == 403
