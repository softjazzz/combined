from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
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


def test_saved_result_rejects_symlink_even_when_target_is_in_storage_directory(monkeypatch, tmp_path):
    client, _current_user, storage_dir = _client(monkeypatch, tmp_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    result_id = str(uuid.uuid4())
    target = storage_dir / "ordinary-result.json"
    target.write_text(
        json.dumps({"id": result_id, "created_by": "owner-1", "payload": {}}),
        encoding="utf-8",
    )
    link = storage_dir / f"{result_id}.json"
    try:
        os.symlink(target.name, link)
    except OSError as exc:
        pytest.skip(f"当前 Windows 环境不允许创建符号链接: {exc}")

    assert link.is_symlink()
    assert link.resolve().parent == storage_dir.resolve()
    assert not qc_sichuan._is_saved_qc_result_file_within_directory(link, storage_dir)
    with pytest.raises(OSError, match="链接或重解析点"):
        qc_sichuan._read_saved_qc_result_file(link, storage_dir)
    assert client.get(f"/api/v1/qc/sichuan/results/{result_id}").status_code == 404


def test_saved_result_rejects_link_entry_when_platform_cannot_create_symlink(monkeypatch, tmp_path):
    """无符号链接权限的 Windows 测试环境也要覆盖拒绝分支。"""

    client, _current_user, storage_dir = _client(monkeypatch, tmp_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    result_id = str(uuid.uuid4())
    candidate = storage_dir / f"{result_id}.json"
    candidate.write_text(
        json.dumps({"id": result_id, "created_by": "owner-1", "payload": {}}),
        encoding="utf-8",
    )
    path_type = type(candidate)
    original_is_symlink = path_type.is_symlink
    monkeypatch.setattr(
        path_type,
        "is_symlink",
        lambda path: path == candidate or original_is_symlink(path),
    )

    assert not qc_sichuan._is_saved_qc_result_file_within_directory(candidate, storage_dir)
    with pytest.raises(OSError, match="链接或重解析点"):
        qc_sichuan._read_saved_qc_result_file(candidate, storage_dir)
    assert client.get(f"/api/v1/qc/sichuan/results/{result_id}").status_code == 404


def test_saved_result_reader_rejects_regular_file_replacement_between_check_and_open(monkeypatch, tmp_path):
    """即使替换为存储目录内另一普通文件，也不能读取检查后的不同对象。"""

    _client(monkeypatch, tmp_path)
    storage_dir = qc_sichuan._saved_qc_results_directory()
    storage_dir.mkdir(parents=True, exist_ok=True)
    result_id = str(uuid.uuid4())
    candidate = storage_dir / f"{result_id}.json"
    replacement = storage_dir / "replacement.json"
    candidate.write_text(
        json.dumps({"id": result_id, "created_by": "owner-1", "payload": {}}),
        encoding="utf-8",
    )
    replacement.write_text(
        json.dumps({"id": "replacement", "created_by": "outside", "payload": {}}),
        encoding="utf-8",
    )

    original_open = os.open
    replaced = {"value": False}

    def replace_before_open(path, flags, *args):
        if Path(path) == candidate and not replaced["value"]:
            replaced["value"] = True
            candidate.unlink()
            replacement.replace(candidate)
        return original_open(path, flags, *args)

    monkeypatch.setattr(qc_sichuan.os, "open", replace_before_open)

    with pytest.raises(OSError, match="被替换"):
        qc_sichuan._read_saved_qc_result_file(candidate, storage_dir)
    assert replaced["value"]


def test_result_detail_rejects_symlink_swapped_in_after_initial_check(monkeypatch, tmp_path):
    """detail 必须从已验证描述符读取，不能在路径检查后跟随新换入的链接。"""

    client, _current_user, storage_dir = _client(monkeypatch, tmp_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    result_id = str(uuid.uuid4())
    candidate = storage_dir / f"{result_id}.json"
    outside = tmp_path / "outside.json"
    candidate.write_text(
        json.dumps({"id": result_id, "created_by": "owner-1", "payload": {}}),
        encoding="utf-8",
    )
    outside.write_text(
        json.dumps({"id": result_id, "created_by": "owner-1", "medical_text": "目录外内容"}),
        encoding="utf-8",
    )

    try:
        probe = storage_dir / "link-permission-probe.json"
        os.symlink(outside, probe)
        probe.unlink()
    except OSError as exc:
        pytest.skip(f"当前 Windows 环境不允许创建符号链接: {exc}")

    original_open = os.open
    replaced = {"value": False}

    def replace_before_open(path, flags, *args):
        if Path(path) == candidate and not replaced["value"]:
            replaced["value"] = True
            candidate.unlink()
            os.symlink(outside, candidate)
        return original_open(path, flags, *args)

    monkeypatch.setattr(qc_sichuan.os, "open", replace_before_open)

    response = client.get(f"/api/v1/qc/sichuan/results/{result_id}")
    assert response.status_code == 404
    assert replaced["value"]
    assert "目录外内容" not in response.text


def test_detail_history_and_latest_share_verified_saved_result_reader(monkeypatch, tmp_path):
    client, _current_user, storage_dir = _client(monkeypatch, tmp_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    result_id = str(uuid.uuid4())
    candidate = storage_dir / f"{result_id}.json"
    candidate.write_text(
        json.dumps({"id": result_id, "created_by": "owner-1", "payload": {}}),
        encoding="utf-8",
    )
    original_reader = qc_sichuan._read_saved_qc_result_file
    reader_calls: list[Path] = []

    def tracking_reader(filepath, base_dir):
        reader_calls.append(filepath)
        return original_reader(filepath, base_dir)

    monkeypatch.setattr(qc_sichuan, "_read_saved_qc_result_file", tracking_reader)

    assert client.get(f"/api/v1/qc/sichuan/results/{result_id}").status_code == 200
    assert client.get("/api/v1/qc/sichuan/results/history").status_code == 200
    assert client.get("/api/v1/qc/sichuan/results/latest").status_code == 200
    assert reader_calls == [candidate, candidate, candidate]


def test_detail_history_and_latest_sort_without_following_result_path(monkeypatch, tmp_path):
    """候选排序不能在受控读取前调用会跟随链接的 ``Path.stat``。"""

    client, _current_user, storage_dir = _client(monkeypatch, tmp_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    result_id = str(uuid.uuid4())
    candidate = storage_dir / f"{result_id}_legacy.json"
    candidate.write_text(
        json.dumps({"id": result_id, "created_by": "owner-1", "payload": {}}),
        encoding="utf-8",
    )
    path_type = type(candidate)
    original_stat = path_type.stat

    def reject_candidate_stat(path, *args, **kwargs):
        if path == candidate and kwargs.get("follow_symlinks", True):
            raise AssertionError("候选排序不得跟随结果路径")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(path_type, "stat", reject_candidate_stat)

    assert client.get(f"/api/v1/qc/sichuan/results/{result_id}").status_code == 200
    assert client.get("/api/v1/qc/sichuan/results/history").status_code == 200
    assert client.get("/api/v1/qc/sichuan/results/latest").status_code == 200
