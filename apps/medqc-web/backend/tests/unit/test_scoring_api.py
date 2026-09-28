"""评分标准 HTTP 与服务合同：CRUD、CAS、启用替换默认、只读限制、422/403/503（SQLite 合成数据，不连真实库）。"""

from __future__ import annotations

import io
import logging

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCScoringGroup, QCScoringItem, QCScoringStandard
from app.routers import scoring as routes
from app.services import scoring_service
from app.services import scoring_standard_service as service

BASE = "/api/v1/scoring"
BANDS = [
    {"name": "甲", "min_score": 90, "max_score": 100},
    {"name": "乙", "min_score": 75, "max_score": 90},
    {"name": "丙", "min_score": 0, "max_score": 75},
]
GROUPS = [{"group_name": "病程记录", "max_deduction": 10}, {"group_name": "首页"}]
ITEMS = [
    {"group_name": "病程记录", "rule_id": "lx0609-001", "deduction": 2},
    {"group_name": "首页", "rule_id": "LX0609-002", "deduction": 1.5, "is_veto": True},
]


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for model in (QCScoringStandard, QCScoringGroup, QCScoringItem):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def client(roles=("qc_manager",), user_id="u-1"):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {"id": user_id, "roles": list(roles)}
    return TestClient(app)


def create(http, name="运行标准", scene="running", **extra):
    body = {"name": name, "scene": scene, "base_score": 100, "grade_bands": BANDS, "veto_grade": "丙", **extra}
    return http.post(f"{BASE}/standards", json=body)


def ready_draft(http, name="运行标准"):
    draft = create(http, name).json()["data"]
    saved = http.put(f"{BASE}/standards/{draft['id']}/items",
                     json={"version_seq": 1, "groups": GROUPS, "items": ITEMS})
    assert saved.status_code == 200, saved.text
    return saved.json()["data"]


def test_scene_catalog_maps_rule_sets_by_scope():
    assert service.scene_rule_set_keys("running") == ("luxian_0609_qc_v1",)  # 0916 不计分
    final = service.scene_rule_set_keys("final")
    assert "luxian_0609_qc_v1" in final and "sc_content_v1" in final
    assert service.scene_rule_set_keys("outpatient") == ()


def test_create_update_items_and_detail_flow(sessions):
    http = client()
    created = create(http)
    assert created.status_code == 200
    draft = created.json()["data"]
    assert draft["status"] == "draft" and draft["is_default"] is False and draft["version_seq"] == 1
    assert draft["rule_set_key"] == "luxian_0609_qc_v1" and draft["grade_bands"] == [
        {"name": band["name"], "min_score": float(band["min_score"]), "max_score": float(band["max_score"])}
        for band in BANDS
    ]
    assert create(http).json()["detail"]["code"] == "name_exists"

    updated = http.put(f"{BASE}/standards/{draft['id']}", json={"version_seq": 1, "name": "运行标准v2"})
    assert updated.status_code == 200 and updated.json()["data"]["version_seq"] == 2
    stale = http.put(f"{BASE}/standards/{draft['id']}", json={"version_seq": 1, "name": "x"})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "version_conflict"

    saved = http.put(f"{BASE}/standards/{draft['id']}/items",
                     json={"version_seq": 2, "groups": GROUPS, "items": ITEMS})
    assert saved.status_code == 200
    data = saved.json()["data"]
    assert data["version_seq"] == 3
    assert data["items"] == [
        {"group_name": "病程记录", "rule_id": "LX0609-001", "deduction": 2.0, "is_veto": False, "enabled": True},
        {"group_name": "首页", "rule_id": "LX0609-002", "deduction": 1.5, "is_veto": True, "enabled": True},
    ]
    assert data["groups"][0] == {"group_name": "病程记录", "max_deduction": 10.0, "sort_order": 1}
    assert data["groups"][1]["max_deduction"] is None
    # 整表替换
    again = http.put(f"{BASE}/standards/{draft['id']}/items",
                     json={"version_seq": 3, "groups": GROUPS[:1], "items": ITEMS[:1]})
    assert again.status_code == 200 and len(again.json()["data"]["items"]) == 1

    listed = http.get(f"{BASE}/standards", params={"scene": "running"}).json()["data"]
    assert [item["name"] for item in listed["items"]] == ["运行标准v2"] and "items" not in listed["items"][0]
    assert http.get(f"{BASE}/standards/{draft['id']}").json()["data"]["item_count"] == 1
    assert http.get(f"{BASE}/standards/nope").status_code == 404


def test_final_scene_requires_rule_set_key_matching_scene(sessions):
    http = client()
    missing = create(http, scene="final")
    assert missing.status_code == 422
    mismatch = create(http, scene="final", rule_set_key="luxian_0916_qc_v1")
    assert mismatch.status_code == 422 and mismatch.json()["detail"]["code"] == "rule_set_scene_mismatch"
    assert create(http, scene="final", rule_set_key="luxian_0609_qc_v1").status_code == 200
    outpatient = create(http, scene="outpatient")
    assert outpatient.status_code == 422 and outpatient.json()["detail"]["code"] == "scene_without_rule_set"


def test_bands_validation_is_422_with_problems(sessions):
    http = client()
    response = create(http, grade_bands=[BANDS[0], {"name": "乙", "min_score": 70, "max_score": 85}, BANDS[2]],
                      veto_grade="丁")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "standard_validation_failed"
    assert any("空隙" in problem for problem in detail["problems"])
    assert any("重叠" in problem for problem in detail["problems"])
    assert any("veto_grade" in problem for problem in detail["problems"])


def test_unknown_rule_ids_are_422(sessions):
    http = client()
    draft = create(http).json()["data"]
    response = http.put(f"{BASE}/standards/{draft['id']}/items", json={
        "version_seq": 1, "groups": GROUPS,
        "items": [*ITEMS, {"group_name": "首页", "rule_id": "LX0916-001", "deduction": 1},
                  {"group_name": "不存在", "rule_id": "LX0609-003", "deduction": 1},
                  {"group_name": "首页", "rule_id": "LX0609-001", "deduction": 1}],
    })
    assert response.status_code == 422
    problems = response.json()["detail"]["problems"]
    assert any("LX0916-001" in problem for problem in problems)
    assert any("所属项目组不存在" in problem for problem in problems)
    assert any("规则重复" in problem for problem in problems)
    assert http.get(f"{BASE}/standards/{draft['id']}").json()["data"]["version_seq"] == 1


def test_activate_replaces_default_in_same_scene_and_active_is_readonly(sessions):
    http = client()
    first = ready_draft(http, "标准一")
    empty = create(http, "空标准").json()["data"]
    no_items = http.post(f"{BASE}/standards/{empty['id']}/activate", json={"version_seq": 1})
    assert no_items.status_code == 422

    activated = http.post(f"{BASE}/standards/{first['id']}/activate", json={"version_seq": first["version_seq"]})
    assert activated.status_code == 200
    active = activated.json()["data"]
    assert active["status"] == "active" and active["is_default"] is True and active["activated_by"] == "u-1"
    assert service.get_default_standard("running")["id"] == first["id"]
    assert service.get_default_standard("final") is None

    # 启用中的标准不可编辑、不可删除
    edit = http.put(f"{BASE}/standards/{first['id']}", json={"version_seq": active["version_seq"], "name": "改"})
    assert edit.status_code == 409 and edit.json()["detail"]["code"] == "not_draft"
    items = http.put(f"{BASE}/standards/{first['id']}/items",
                     json={"version_seq": active["version_seq"], "groups": [], "items": []})
    assert items.status_code == 409
    delete = http.delete(f"{BASE}/standards/{first['id']}", params={"version_seq": active["version_seq"]})
    assert delete.status_code == 409

    # 复制成新草稿再启用：原默认在同一事务内归档
    copied = http.post(f"{BASE}/standards/{first['id']}/copy", json={"name": "标准二"}).json()["data"]
    assert copied["status"] == "draft" and copied["items"] == active["items"]
    second = http.post(f"{BASE}/standards/{copied['id']}/activate", json={"version_seq": 1})
    assert second.status_code == 200
    assert http.get(f"{BASE}/standards/{first['id']}").json()["data"]["status"] == "archived"
    assert service.get_default_standard("running")["id"] == copied["id"]

    # undefault：原默认保持 active 但取消默认
    third = http.post(f"{BASE}/standards/{copied['id']}/copy", json={"name": "标准三"}).json()["data"]
    response = http.post(f"{BASE}/standards/{third['id']}/activate",
                         json={"version_seq": 1, "replace_mode": "undefault"})
    assert response.status_code == 200
    previous = http.get(f"{BASE}/standards/{copied['id']}").json()["data"]
    assert previous["status"] == "active" and previous["is_default"] is False
    assert service.get_default_standard("running")["id"] == third["id"]


def test_activate_rolls_back_when_default_swap_fails(sessions, monkeypatch):
    http = client()
    first = ready_draft(http, "标准一")
    http.post(f"{BASE}/standards/{first['id']}/activate", json={"version_seq": first["version_seq"]})
    copied = http.post(f"{BASE}/standards/{first['id']}/copy", json={"name": "标准二"}).json()["data"]

    original = service._cas_update

    def failing(session, row, version_seq, **values):
        if values.get("status") == "active":
            raise service.ScoringStandardConflict("并发", code="version_conflict")
        return original(session, row, version_seq, **values)

    monkeypatch.setattr(service, "_cas_update", failing)
    response = http.post(f"{BASE}/standards/{copied['id']}/activate", json={"version_seq": 1})
    assert response.status_code == 409
    # 同一事务：原默认标准未被归档
    assert service.get_default_standard("running")["id"] == first["id"]


def test_active_non_default_can_be_set_default_without_copy(sessions):
    http = client()
    first = ready_draft(http, "标准一")
    draft_rejected = http.post(
        f"{BASE}/standards/{first['id']}/set-default", json={"version_seq": first["version_seq"]},
    )
    assert draft_rejected.status_code == 409
    assert draft_rejected.json()["detail"]["code"] == "not_active"
    first_active = http.post(
        f"{BASE}/standards/{first['id']}/activate", json={"version_seq": first["version_seq"]},
    ).json()["data"]
    second = http.post(f"{BASE}/standards/{first['id']}/copy", json={"name": "标准二"}).json()["data"]
    second_active = http.post(
        f"{BASE}/standards/{second['id']}/activate",
        json={"version_seq": second["version_seq"], "replace_mode": "undefault"},
    ).json()["data"]
    first_non_default = http.get(f"{BASE}/standards/{first['id']}").json()["data"]
    assert first_non_default["status"] == "active" and first_non_default["is_default"] is False

    restored = http.post(
        f"{BASE}/standards/{first['id']}/set-default",
        json={"version_seq": first_non_default["version_seq"], "replace_mode": "undefault"},
    )
    assert restored.status_code == 200
    restored_data = restored.json()["data"]
    assert restored_data["id"] == first_active["id"]
    assert restored_data["status"] == "active" and restored_data["is_default"] is True
    second_non_default = http.get(f"{BASE}/standards/{second['id']}").json()["data"]
    assert second_non_default["status"] == "active" and second_non_default["is_default"] is False

    stale = http.post(
        f"{BASE}/standards/{second['id']}/set-default",
        json={"version_seq": second_active["version_seq"], "replace_mode": "archive"},
    )
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "version_conflict"

    switched = http.post(
        f"{BASE}/standards/{second['id']}/set-default",
        json={"version_seq": second_non_default["version_seq"], "replace_mode": "archive"},
    )
    assert switched.status_code == 200 and switched.json()["data"]["is_default"] is True
    assert http.get(f"{BASE}/standards/{first['id']}").json()["data"]["status"] == "archived"

    already_default = http.post(
        f"{BASE}/standards/{second['id']}/set-default",
        json={"version_seq": switched.json()["data"]["version_seq"], "replace_mode": "undefault"},
    )
    assert already_default.status_code == 409
    assert already_default.json()["detail"]["code"] == "already_default"


def test_set_default_readback_failure_rolls_back_swap(sessions, monkeypatch):
    http = client()
    first = ready_draft(http, "标准一")
    http.post(f"{BASE}/standards/{first['id']}/activate", json={"version_seq": first["version_seq"]})
    second = http.post(f"{BASE}/standards/{first['id']}/copy", json={"name": "标准二"}).json()["data"]
    http.post(
        f"{BASE}/standards/{second['id']}/activate",
        json={"version_seq": second["version_seq"], "replace_mode": "undefault"},
    )
    first_non_default = http.get(f"{BASE}/standards/{first['id']}").json()["data"]
    second_default = http.get(f"{BASE}/standards/{second['id']}").json()["data"]

    original_detail = service._detail

    def failing_detail(session, row):
        if row.id == first["id"] and row.is_default:
            raise sa.exc.OperationalError("select", {}, Exception("回读失败"))
        return original_detail(session, row)

    monkeypatch.setattr(service, "_detail", failing_detail)
    response = http.post(
        f"{BASE}/standards/{first['id']}/set-default",
        json={"version_seq": first_non_default["version_seq"], "replace_mode": "archive"},
    )
    assert response.status_code == 503
    monkeypatch.setattr(service, "_detail", original_detail)

    first_after = http.get(f"{BASE}/standards/{first['id']}").json()["data"]
    second_after = http.get(f"{BASE}/standards/{second['id']}").json()["data"]
    assert first_after["status"] == "active" and first_after["is_default"] is False
    assert second_after["status"] == "active" and second_after["is_default"] is True
    assert second_after["version_seq"] == second_default["version_seq"]


def test_archive_and_delete_rules(sessions):
    http = client()
    draft = ready_draft(http)
    assert http.post(f"{BASE}/standards/{draft['id']}/archive", json={"version_seq": 2}).status_code == 409
    stale = http.delete(f"{BASE}/standards/{draft['id']}", params={"version_seq": 1})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "version_conflict"
    deleted = http.delete(f"{BASE}/standards/{draft['id']}", params={"version_seq": 2})
    assert deleted.status_code == 200 and deleted.json()["data"] == {"id": draft["id"], "deleted": True}
    with sessions() as session:
        assert session.execute(sa.select(sa.func.count()).select_from(QCScoringItem.__table__)).scalar() == 0

    other = ready_draft(http, "标准B")
    active = http.post(f"{BASE}/standards/{other['id']}/activate", json={"version_seq": 2}).json()["data"]
    archived = http.post(f"{BASE}/standards/{other['id']}/archive", json={"version_seq": active["version_seq"]})
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived" and archived.json()["data"]["is_default"] is False
    assert service.get_default_standard("running") is None


@pytest.mark.parametrize("method,path,body", [
    ("post", f"{BASE}/standards", {"name": "x", "scene": "running", "base_score": 100,
                                   "grade_bands": BANDS, "veto_grade": "丙"}),
    ("put", f"{BASE}/standards/s-1", {"version_seq": 1, "name": "x"}),
    ("put", f"{BASE}/standards/s-1/items", {"version_seq": 1, "groups": [], "items": []}),
    ("post", f"{BASE}/standards/s-1/copy", {"name": "x"}),
    ("post", f"{BASE}/standards/s-1/activate", {"version_seq": 1}),
    ("post", f"{BASE}/standards/s-1/set-default", {"version_seq": 1}),
    ("post", f"{BASE}/standards/s-1/archive", {"version_seq": 1}),
    ("delete", f"{BASE}/standards/s-1?version_seq=1", None),
])
def test_write_endpoints_require_admin_or_qc_manager(sessions, method, path, body):
    http = client(roles=("qc_doctor",))
    kwargs = {} if body is None else {"json": body}
    assert getattr(http, method)(path, **kwargs).status_code == 403
    assert service.list_standards()["items"] == []


def test_admin_can_write_and_any_user_can_read(sessions):
    assert create(client(roles=("admin",))).status_code == 200
    reader = client(roles=("qc_doctor",))
    assert reader.get(f"{BASE}/standards").status_code == 200
    assert reader.get(f"{BASE}/scenes").status_code == 200


def _renamed_workbook(content: bytes, name: str, *, formula: bool = False) -> bytes:
    workbook = load_workbook(io.BytesIO(content))
    workbook["评分标准"]["E2"] = name
    if formula:
        workbook["评分条目"]["E2"] = "=1+1"
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _workbook_with_rule_set(content: bytes, rule_set_key: str) -> bytes:
    workbook = load_workbook(io.BytesIO(content))
    workbook["评分标准"]["C2"] = rule_set_key
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_scoring_excel_export_import_roundtrip_creates_new_draft(sessions, caplog):
    manager = client()
    source = ready_draft(manager, "导出源标准")
    with caplog.at_level(logging.INFO, logger="app.audit"):
        exported = manager.get(f"{BASE}/standards/{source['id']}/export")
    assert exported.status_code == 200
    assert exported.headers["cache-control"] == "no-store"
    assert exported.headers["x-content-type-options"] == "nosniff"
    assert exported.content.startswith(b"PK")

    with caplog.at_level(logging.INFO, logger="app.audit"):
        imported = manager.post(
            f"{BASE}/standards/import",
            files={"file": ("standard.xlsx", _renamed_workbook(exported.content, "导入草稿"),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert imported.status_code == 200, imported.text
    data = imported.json()["data"]
    assert data["name"] == "导入草稿" and data["status"] == "draft"
    assert data["is_default"] is False and data["version_seq"] == 1
    assert data["grade_bands"] == source["grade_bands"]
    assert data["groups"] == source["groups"] and data["items"] == source["items"]
    assert manager.get(f"{BASE}/standards/{source['id']}").json()["data"]["name"] == "导出源标准"
    audit_lines = "\n".join(line for line in caplog.text.splitlines() if "audit.event" in line)
    assert "scoring.standard.export" in audit_lines and "scoring.standard.import" in audit_lines
    assert '"item_count": 2' in audit_lines and "导出源标准" not in audit_lines and "导入草稿" not in audit_lines


def test_scoring_excel_permissions_and_formula_validation_do_not_write(sessions):
    manager = client()
    source = ready_draft(manager, "权限源标准")
    exported = manager.get(f"{BASE}/standards/{source['id']}/export")
    reader = client(roles=("qc_doctor",))
    assert reader.get(f"{BASE}/standards/{source['id']}/export").status_code == 200
    denied = reader.post(
        f"{BASE}/standards/import",
        files={"file": ("standard.xlsx", exported.content, "application/octet-stream")},
    )
    assert denied.status_code == 403

    invalid = manager.post(
        f"{BASE}/standards/import",
        files={"file": ("standard.xlsx", _renamed_workbook(exported.content, "公式标准", formula=True),
                         "application/octet-stream")},
    )
    assert invalid.status_code == 422
    detail = invalid.json()["detail"]
    assert detail["code"] == "excel_validation_failed"
    assert any(problem["code"] == "formula_forbidden" for problem in detail["problems"])
    bad_key = manager.post(
        f"{BASE}/standards/import",
        files={"file": ("standard.xlsx", _workbook_with_rule_set(exported.content, "unknown_rules"),
                         "application/octet-stream")},
    )
    assert bad_key.status_code == 422
    assert bad_key.json()["detail"]["problems"][0]["code"] == "rule_set_scene_mismatch"
    assert [item["name"] for item in service.list_standards()["items"]] == ["权限源标准"]


def test_scoring_excel_import_readback_failure_rolls_back(sessions, monkeypatch):
    manager = client()
    source = ready_draft(manager, "回读源标准")
    exported = manager.get(f"{BASE}/standards/{source['id']}/export")
    original_detail = service._detail

    def failing_detail(session, row):
        if row.name == "回读失败标准":
            raise sa.exc.OperationalError("select", {}, Exception("readback failed"))
        return original_detail(session, row)

    monkeypatch.setattr(service, "_detail", failing_detail)
    response = manager.post(
        f"{BASE}/standards/import",
        files={"file": ("standard.xlsx", _renamed_workbook(exported.content, "回读失败标准"),
                         "application/octet-stream")},
    )
    assert response.status_code == 503
    monkeypatch.setattr(service, "_detail", original_detail)
    assert [item["name"] for item in service.list_standards()["items"]] == ["回读源标准"]


def test_scoring_excel_import_rechecks_version_inside_locked_transaction(sessions, monkeypatch):
    manager = client()
    source = ready_draft(manager, "版本源标准")
    exported = manager.get(f"{BASE}/standards/{source['id']}/export")
    renamed = _renamed_workbook(exported.content, "过期版本标准")
    identity = routes.inspect_scoring_workbook_identity(renamed)
    _, universe = routes.current_rule_set_snapshot(identity.rule_set_key)
    monkeypatch.setattr(routes, "current_rule_set_snapshot", lambda _key: (identity.rule_set_version, universe))
    snapshots = iter(((identity.rule_set_version, universe), ("new-version", universe)))
    monkeypatch.setattr(service, "current_rule_set_snapshot", lambda _key: next(snapshots))
    locks = []
    monkeypatch.setattr(service, "_lock_rule_set_version", lambda _session, key: locks.append(key))

    response = manager.post(
        f"{BASE}/standards/import",
        files={"file": ("standard.xlsx", renamed, "application/octet-stream")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "rule_set_version_mismatch"
    assert locks == [identity.rule_set_key]
    assert [item["name"] for item in service.list_standards()["items"]] == ["版本源标准"]


def test_database_failure_is_desensitized_503(monkeypatch, caplog):
    def broken():
        raise sa.exc.OperationalError("select", {}, Exception("password=secret host=db.internal"))

    monkeypatch.setattr(service, "SessionLocal", broken)
    http = client()
    with caplog.at_level(logging.ERROR):
        responses = [
            http.get(f"{BASE}/standards"),
            create(http),
            http.get(f"{BASE}/case", params={"institute_id": "H", "patient_id": "P", "visit_id": "V",
                                             "scene": "running"}),
        ]
    for response in responses:
        assert response.status_code == 503
        assert response.json()["detail"] == "评分服务暂不可用，请稍后重试"
        assert "secret" not in response.text and "db.internal" not in response.text
    assert "secret" not in caplog.text and "db.internal" not in caplog.text


def test_extra_fields_are_rejected(sessions):
    http = client()
    assert create(http, status="active").status_code == 422
    assert create(http, base_score=True).status_code == 422


def _case(http, scene="running"):
    return http.get(f"{BASE}/case", params={"institute_id": "H1", "patient_id": "P1", "visit_id": "V1",
                                            "scene": scene})


class _Workspace:
    def __init__(self, dto):
        self.dto = dto

    def build_latest_single_record_result_dto(self, **kwargs):
        return self.dto


def test_case_score_no_standard_no_result_and_scored(sessions, monkeypatch):
    http = client(roles=("qc_doctor",))
    assert _case(http).json()["data"] == {"status": "no_standard", "scene": "running"}

    manager = client()
    draft = ready_draft(manager)
    manager.post(f"{BASE}/standards/{draft['id']}/activate", json={"version_seq": 2})
    monkeypatch.setattr(scoring_service, "_default_workspace",
                        lambda: _Workspace({"state": "not_found", "items": []}))
    data = _case(http).json()["data"]
    assert data["status"] == "no_result" and data["result_state"] == "not_found"

    monkeypatch.setattr(scoring_service, "_default_workspace", lambda: _Workspace({
        "state": "ready", "job_id": "job-1", "rule_set_key": "luxian_0609_qc_v1",
        "items": [{"rule_id": "LX0609-002"}, {"rule_id": "LX0609-001"}],
    }))
    monkeypatch.setattr(scoring_service, "project_customer_items", lambda items: [
        {"rule_id": item["rule_id"], "is_confirmed_issue": item["rule_id"] == "LX0609-002"} for item in items
    ])
    data = _case(http).json()["data"]
    assert data["status"] == "scored" and data["score"] == 98.5 and data["veto_hit"] is True
    assert data["grade"] == "丙" and data["standard_id"] == draft["id"]
    assert data["deductions"] == [
        {"rule_id": "LX0609-002", "group_name": "首页", "deduction": 1.5, "is_veto": True},
    ]
    assert data["standard_updated_at"]


def test_case_score_rejects_bad_scene(sessions):
    assert _case(client(), scene="other").status_code == 422
