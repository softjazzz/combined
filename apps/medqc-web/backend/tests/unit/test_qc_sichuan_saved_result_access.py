from __future__ import annotations

import json
import os
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import qc_sichuan


def _payload() -> dict:
    return {
        "mode": "optimized_batch",
        "document_type": "course_record",
        "rule_ids": ["LX0609-001"],
        "medical_text_length": 0,
        "stats": {},
        "performance": {},
        "payload": {},
        "metadata": {},
    }


def _client(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    current_user = {"value": {"id": "owner-1", "roles": ["doctor"]}}
    app.dependency_overrides[get_current_user] = lambda: current_user["value"]

    # 让旧文件型存储也落到每个测试独立的临时目录中。
    monkeypatch.setattr(
        qc_sichuan,
        "__file__",
        str(tmp_path / "app" / "routers" / "qc_sichuan.py"),
    )
    return TestClient(app), current_user, tmp_path / "app" / "storage" / "qc_results"


def test_saved_result_is_bound_to_creator_and_legacy_result_is_admin_only(monkeypatch, tmp_path):
    client, current_user, storage_dir = _client(monkeypatch, tmp_path)
    saved = client.post("/api/v1/qc/sichuan/results/save", json=_payload())
    assert saved.status_code == 200, saved.text
    result_id = saved.json()["data"]["id"]
    assert uuid.UUID(result_id)
    assert saved.json()["data"]["path"] == f"/api/v1/qc/sichuan/results/{result_id}"
    owner_detail = client.get(f"/api/v1/qc/sichuan/results/{result_id}")
    assert owner_detail.status_code == 200
    assert owner_detail.json()["data"]["created_by"] == "owner-1"
    assert client.get("/api/v1/qc/sichuan/results/history").json()["data"]["records"][0]["id"] == result_id
    assert client.get("/api/v1/qc/sichuan/results/latest").json()["data"]["id"] == result_id
    os.utime(storage_dir / f"{result_id}.json", (1_000_000, 1_000_000))

    current_user["value"] = {"id": "other-1", "roles": ["doctor"]}
    assert client.get(f"/api/v1/qc/sichuan/results/{result_id}").status_code == 404
    second_saved = client.post("/api/v1/qc/sichuan/results/save", json=_payload())
    assert second_saved.status_code == 200, second_saved.text
    second_id = second_saved.json()["data"]["id"]
    assert client.get("/api/v1/qc/sichuan/results/history").json()["data"]["records"][0]["id"] == second_id
    assert client.get("/api/v1/qc/sichuan/results/latest").json()["data"]["id"] == second_id

    current_user["value"] = {"id": "owner-1", "roles": ["doctor"]}
    assert client.get("/api/v1/qc/sichuan/results/history").json()["data"]["records"][0]["id"] == result_id
    assert client.get("/api/v1/qc/sichuan/results/latest").json()["data"]["id"] == result_id

    legacy_id = str(uuid.uuid4())
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / f"{legacy_id}_legacy_20260921.json").write_text(
        json.dumps({"id": legacy_id, "created_at": "2026-09-21T00:00:00+00:00"}),
        encoding="utf-8",
    )
    current_user["value"] = {"id": "other-1", "roles": ["doctor"]}
    assert client.get(f"/api/v1/qc/sichuan/results/{legacy_id}").status_code == 404

    current_user["value"] = {"id": "admin-1", "roles": ["admin"]}
    assert client.get(f"/api/v1/qc/sichuan/results/{result_id}").status_code == 200
    assert client.get(f"/api/v1/qc/sichuan/results/{legacy_id}").status_code == 200


def test_result_detail_rejects_path_and_non_uuid_identifiers(monkeypatch, tmp_path):
    client, _current_user, storage_dir = _client(monkeypatch, tmp_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir.parent / "private.json").write_text(
        json.dumps({"id": "private", "medical_text": "不应读取到这里"}),
        encoding="utf-8",
    )

    for unsafe_id in (
        "..",
        "..%2F..%2Fsecrets",
        "..%5Cprivate",
        "C%3A%5CWindows%5Cwin.ini",
        "not-a-uuid",
    ):
        response = client.get(f"/api/v1/qc/sichuan/results/{unsafe_id}")
        assert response.status_code in {404, 422}
