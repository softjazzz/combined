"""规则集版本 HTTP 合同：角色、状态码、409 code、脱敏 503（SQLite 合成数据，不连真实库）。"""

from __future__ import annotations

import logging
from io import BytesIO

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCRuleSetVersion
from app.routers import rule_set_versions as routes
from app.services import rule_set_version_service as service
from app.services import rule_set_version_excel_service as excel


BASE = "/api/v1/rule-set-versions"
KEY = "luxian_0609_qc_v1"
BUILTIN = "2026-06-09"


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCRuleSetVersion.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def client(roles=("qc_manager",), user_id="u-1"):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {"id": user_id, "roles": list(roles)}
    return TestClient(app)


def test_list_detail_draft_publish_retire_flow(sessions):
    http = client()
    listed = http.get(BASE, params={"rule_set_key": KEY})
    assert listed.status_code == 200
    data = listed.json()["data"]
    assert data["current_version"] == BUILTIN and data["versionable"] is True
    assert data["items"][0]["source"] == "builtin" and data["items"][0]["is_current"] is True

    detail = http.get(f"{BASE}/{KEY}/{BUILTIN}")
    assert detail.status_code == 200
    builtin = detail.json()["data"]
    assert builtin["resolution"]["source"] == "builtin"
    assert len(builtin["entries"]) == builtin["active_count"] + builtin["paused_count"] + builtin["offline_count"]

    created = http.post(f"{BASE}/{KEY}/draft", json={"note": "草稿"})
    assert created.status_code == 200
    draft = created.json()["data"]
    assert draft["status"] == "draft" and draft["version_seq"] == 1 and draft["version"] is None
    duplicate = http.post(f"{BASE}/{KEY}/draft", json={})
    assert duplicate.status_code == 409 and duplicate.json()["detail"]["code"] == "draft_exists"
    assert http.get(f"{BASE}/{KEY}/draft").json()["data"]["id"] == draft["id"]

    entries = [
        {
            "rule_id": item["rule_id"],
            "state": "active" if item["rule_id"] == "LX0609-033" else item["state"],
            "department_scope_mode": "all",
            "department_refs": [],
            "doctor_visible": False,
        }
        for item in draft["entries"]
    ]
    updated = http.put(f"{BASE}/{KEY}/draft", json={"version_seq": 1, "entries": entries})
    assert updated.status_code == 200, updated.json()
    assert updated.json()["data"]["version_seq"] == 2
    stale = http.put(f"{BASE}/{KEY}/draft", json={"version_seq": 1, "note": "旧"})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "version_conflict"

    published = http.post(f"{BASE}/{KEY}/draft/publish", json={"version": "2026-09-27.1", "note": "上线"})
    assert published.status_code == 200
    item = published.json()["data"]
    assert item["status"] == "published" and item["is_current"] is True
    assert item["content_digest"] == service.compute_entries_digest(entries)

    again = http.post(f"{BASE}/{KEY}/draft/publish", json={"version": "2026-09-27.2"})
    assert again.status_code == 404
    current = http.post(f"{BASE}/{KEY}/2026-09-27.1/retire")
    assert current.status_code == 409 and current.json()["detail"]["code"] == "current_version"
    builtin_retire = http.post(f"{BASE}/{KEY}/{BUILTIN}/retire")
    assert builtin_retire.status_code == 409 and builtin_retire.json()["detail"]["code"] == "builtin_version"

    listed = http.get(BASE, params={"rule_set_key": KEY}).json()["data"]
    assert listed["current_version"] == "2026-09-27.1" and listed["draft"] is None


def test_publish_validation_failure_is_422_with_problems(sessions):
    http = client()
    draft = http.post(f"{BASE}/{KEY}/draft", json={}).json()["data"]
    entries = [
        {"rule_id": item["rule_id"], "state": "active" if item["rule_id"] == "LX0609-020" else item["state"]}
        for item in draft["entries"]
    ]
    assert http.put(f"{BASE}/{KEY}/draft", json={"version_seq": 1, "entries": entries}).status_code == 200
    response = http.post(f"{BASE}/{KEY}/draft/publish", json={"version": "v1"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "publish_validation_failed"
    assert any("LX0609-020" in problem for problem in detail["problems"])


def test_entries_carry_readonly_executable_flag(sessions):
    http = client()
    executable = service.executable_rule_ids(KEY)
    detail = http.get(f"{BASE}/{KEY}/{BUILTIN}").json()["data"]
    flags = {item["rule_id"]: item["executable"] for item in detail["entries"]}
    assert flags["LX0609-033"] is True and flags["LX0609-020"] is False
    assert flags == {rule_id: rule_id in executable for rule_id in flags}
    # 摘要只覆盖 rule_id/state，附加字段不影响内容摘要。
    digest_entries = [
        {"rule_id": item["rule_id"], "state": item["state"]}
        for item in detail["entries"]
    ]
    assert detail["content_digest"] == service.compute_entries_digest(digest_entries)

    draft = http.post(f"{BASE}/{KEY}/draft", json={}).json()["data"]
    assert all(isinstance(item["executable"], bool) for item in draft["entries"])
    assert http.get(f"{BASE}/{KEY}/draft").json()["data"]["entries"] == draft["entries"]
    listed = http.get(BASE, params={"rule_set_key": KEY}).json()["data"]
    assert listed["draft"]["entries"] == draft["entries"]
    assert "entries" not in listed["items"][0]
    # 写接口仍只接受 rule_id/state，回传 executable 被拒绝。
    rejected = http.put(f"{BASE}/{KEY}/draft", json={"version_seq": 1, "entries": draft["entries"]})
    assert rejected.status_code == 422

    other = http.get(f"{BASE}/luxian_0916_qc_v1/2026-09-16").json()["data"]
    assert other["entries"] and all(item["executable"] is True for item in other["entries"])
    # 0916 暂无权威元数据：名称与文书为 null，不猜测。
    assert all(item["qc_point"] is None and item["source_document"] is None for item in other["entries"])


def test_entries_carry_rule_master_metadata_including_offline_rules(sessions):
    from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master

    http = client()
    master = {entry.rule_id: entry for entry in load_luxian_0609_rule_master()}
    detail = http.get(f"{BASE}/{KEY}/{BUILTIN}").json()["data"]
    by_id = {item["rule_id"]: item for item in detail["entries"]}
    offline = [item for item in detail["entries"] if item["state"] == "offline"]
    assert offline, "内置版本应含客户排除（下线）规则"
    for item in detail["entries"]:
        assert item["qc_point"] == master[item["rule_id"]].qc_point
        assert item["source_document"] == master[item["rule_id"]].source_document
    # 下线规则（如 LX0609-033）同样有名称与来源文书。
    assert by_id["LX0609-033"]["state"] == "offline" and by_id["LX0609-033"]["qc_point"]
    digest_entries = [
        {"rule_id": item["rule_id"], "state": item["state"]}
        for item in detail["entries"]
    ]
    assert detail["content_digest"] == service.compute_entries_digest(digest_entries)

    draft = http.post(f"{BASE}/{KEY}/draft", json={}).json()["data"]
    assert {item["rule_id"]: item["qc_point"] for item in draft["entries"]} == {
        rule_id: item["qc_point"] for rule_id, item in by_id.items()
    }
    # 写接口拒绝回传派生字段。
    polluted = [{"rule_id": item["rule_id"], "state": item["state"], "qc_point": item["qc_point"]} for item in draft["entries"]]
    assert http.put(f"{BASE}/{KEY}/draft", json={"version_seq": 1, "entries": polluted}).status_code == 422


def test_delete_draft_uses_version_seq(sessions):
    http = client()
    http.post(f"{BASE}/{KEY}/draft", json={})
    stale = http.delete(f"{BASE}/{KEY}/draft", params={"version_seq": 5})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "version_conflict"
    deleted = http.delete(f"{BASE}/{KEY}/draft", params={"version_seq": 1})
    assert deleted.status_code == 200 and deleted.json()["data"] == {"rule_set_key": KEY, "deleted": True}
    assert http.get(f"{BASE}/{KEY}/draft").status_code == 404


def test_0916_draft_is_409_unsupported_rule_set(sessions):
    http = client()
    response = http.post(f"{BASE}/luxian_0916_qc_v1/draft", json={})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "unsupported_rule_set"
    detail = http.get(f"{BASE}/luxian_0916_qc_v1/2026-09-16")
    assert detail.status_code == 200 and detail.json()["data"]["resolution"]["source"] == "builtin"


def test_unknown_rule_set_and_version_are_404(sessions):
    http = client()
    assert http.get(BASE, params={"rule_set_key": "no_such_key"}).status_code == 404
    assert http.get(f"{BASE}/{KEY}/2099-01-01").status_code == 404


@pytest.mark.parametrize("method,path,body", [
    ("post", f"{BASE}/{KEY}/draft", {}),
    ("put", f"{BASE}/{KEY}/draft", {"version_seq": 1, "note": "x"}),
    ("delete", f"{BASE}/{KEY}/draft?version_seq=1", None),
    ("post", f"{BASE}/{KEY}/draft/publish", {"version": "v1"}),
    ("post", f"{BASE}/{KEY}/v1/retire", None),
])
def test_write_endpoints_require_admin_or_qc_manager(sessions, method, path, body):
    http = client(roles=("qc_doctor",))
    kwargs = {} if body is None else {"json": body}
    response = getattr(http, method)(path, **kwargs)
    assert response.status_code == 403
    # 未产生任何写入。
    assert service.list_versions(KEY)["draft"] is None


def test_admin_can_write_and_any_user_can_read(sessions):
    assert client(roles=("admin",)).post(f"{BASE}/{KEY}/draft", json={}).status_code == 200
    assert client(roles=("qc_doctor",)).get(BASE, params={"rule_set_key": KEY}).status_code == 200


def test_database_failure_is_desensitized_503(monkeypatch, caplog):
    def broken():
        raise sa.exc.OperationalError("select", {}, Exception("password=secret host=db.internal"))

    monkeypatch.setattr(service, "SessionLocal", broken)
    http = client()
    with caplog.at_level(logging.ERROR):
        responses = [
            http.get(BASE, params={"rule_set_key": KEY}),
            http.post(f"{BASE}/{KEY}/draft", json={}),
            http.get(f"{BASE}/{KEY}/v1"),
        ]
    for response in responses:
        assert response.status_code == 503
        assert response.json()["detail"] == "规则集版本服务暂不可用，请稍后重试"
        assert "secret" not in response.text and "db.internal" not in response.text
    assert "secret" not in caplog.text and "db.internal" not in caplog.text


def test_extra_fields_are_rejected(sessions):
    http = client()
    response = http.post(f"{BASE}/{KEY}/draft", json={"status": "published"})
    assert response.status_code == 422


def _builtin_workbook():
    detail = service.with_executable_flags(KEY, service.get_version_detail(KEY, BUILTIN))
    return excel.build_workbook(
        detail,
        base_version=BUILTIN,
        base_content_digest=detail["content_digest"],
    )


def test_export_and_import_excel_create_then_cas_update_draft(sessions, caplog):
    http = client()
    with caplog.at_level(logging.INFO, logger="app.audit"):
        exported = http.get(f"{BASE}/{KEY}/{BUILTIN}/export")
        created = http.post(
            f"{BASE}/{KEY}/draft/import",
            files={"file": ("规则集.xlsx", exported.content, exported.headers["content-type"])},
        )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "no-store" in exported.headers["cache-control"]

    assert created.status_code == 200
    draft = created.json()["data"]
    assert draft["status"] == "draft" and draft["version_seq"] == 1
    assert service.current_version(KEY) == BUILTIN
    assert "rule_set_versions.version.export" in caplog.text
    assert "rule_set_versions.draft.import" in caplog.text
    assert '"entry_count": 79' in caplog.text
    assert "规则集.xlsx" not in caplog.text and "入院记录" not in caplog.text

    frozen_again = http.post(
        f"{BASE}/{KEY}/draft/import",
        files={"file": ("规则集.xlsx", exported.content, exported.headers["content-type"])},
    )
    assert frozen_again.status_code == 409
    assert frozen_again.json()["detail"]["code"] == "draft_exists"

    draft_export = http.get(f"{BASE}/{KEY}/draft/export")
    assert draft_export.status_code == 200
    workbook = load_workbook(BytesIO(draft_export.content))
    assert workbook[excel.INFO_SHEET]["G2"].value == 1
    workbook[excel.ENTRY_SHEET]["B2"] = "paused"
    edited = BytesIO()
    workbook.save(edited)
    workbook.close()
    updated = http.post(
        f"{BASE}/{KEY}/draft/import",
        files={"file": ("草稿.xlsx", edited.getvalue(), exported.headers["content-type"])},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["version_seq"] == 2

    stale = http.post(
        f"{BASE}/{KEY}/draft/import",
        files={"file": ("旧草稿.xlsx", draft_export.content, exported.headers["content-type"])},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "version_conflict"


def test_excel_import_validation_has_sheet_row_field_and_does_not_write(sessions):
    content = _builtin_workbook()
    workbook = load_workbook(BytesIO(content))
    workbook[excel.ENTRY_SHEET]["B2"] = "=1+1"
    broken = BytesIO()
    workbook.save(broken)
    workbook.close()
    response = client().post(
        f"{BASE}/{KEY}/draft/import",
        files={"file": ("bad.xlsx", broken.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "excel_validation_failed"
    assert any(
        issue["sheet"] == excel.ENTRY_SHEET and issue["row"] == 2
        and issue["field"] == "状态" and issue["code"] == "formula_not_allowed"
        for issue in detail["issues"]
    )
    assert service.list_versions(KEY)["draft"] is None


def test_excel_import_requires_manager_but_export_allows_authenticated_reader(sessions):
    reader = client(roles=("qc_doctor",))
    assert reader.get(f"{BASE}/{KEY}/{BUILTIN}/export").status_code == 200
    denied = reader.post(
        f"{BASE}/{KEY}/draft/import",
        files={"file": ("rules.xlsx", _builtin_workbook(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert denied.status_code == 403
    assert service.list_versions(KEY)["draft"] is None
