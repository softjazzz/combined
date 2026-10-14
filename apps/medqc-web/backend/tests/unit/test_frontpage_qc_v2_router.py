"""首页质控 V2 接口：SQLite 合成数据，后台任务同步执行；不连接业务库、不调用模型。"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, List

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.routers import frontpage_qc_v2 as api
from app.services.case_identity import normalize_case_refs
from app.services.frontpage_qc_v2 import FrontpageRef
from app.services.frontpage_qc_v2.store import FrontpageQcStore
from tests.unit.frontpage_qc_v2_support import seed_cdm_frontpages

USER = {"id": "qc-user-1", "roles": ["qc_manager"]}


def _ref(n: int) -> FrontpageRef:
    return FrontpageRef("INST-SYN", f"C{n:02d}", f"C{n:02d}-V1")


@dataclass
class _Listing:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class FakeRepository:
    """模拟病历池出院范围：只返回合成别名，不含真实患者信息。"""

    def __init__(self, refs: List[FrontpageRef]):
        self.records = [
            {
                "institute_id": ref.institute_id,
                "patient_id": ref.patient_id,
                "visit_id": ref.visit_id,
                "record_id": ref.visit_id,
                "patient_name": ref.patient_id,
                "inpat_no": f"ZY-{ref.patient_id}",
                "mr_no": f"MR-{ref.patient_id}",
                "department": "外科" if index % 2 == 0 else "内科",
                "discharge_date": f"2026-03-{index + 1:02d}",
            }
            for index, ref in enumerate(refs)
        ]

    def _filter(self, department=None, start_date=None, end_date=None, keyword=None, record_refs=None):
        items = self.records
        if record_refs:
            wanted = {tuple(ref) for ref in normalize_case_refs(record_refs)}
            items = [r for r in items if (r["institute_id"], r["patient_id"], r["visit_id"]) in wanted]
        if department:
            items = [r for r in items if r["department"] == department]
        if start_date:
            items = [r for r in items if r["discharge_date"] >= start_date]
        if end_date:
            items = [r for r in items if r["discharge_date"] <= end_date]
        if keyword:
            items = [r for r in items if keyword in r["patient_id"]]
        return list(items)

    def collect_records(self, *, scope, department, doctor, date_field, start_date, end_date, keyword, record_refs=None, **_):
        assert scope == "final"
        return self._filter(department, start_date, end_date, keyword, record_refs)

    def list_records(self, *, scope, department, doctor, date_field, start_date, end_date, keyword, page, page_size):
        items = self._filter(department, start_date, end_date, keyword)
        return _Listing(items[(page - 1) * page_size: page * page_size], len(items), page, page_size)

    def get_record_filters(self, *, scope, department):
        return {"departments": ["内科", "外科"], "date_bounds": {}}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'api.sqlite'}")
    factory = sessionmaker(bind=engine)
    refs = [_ref(n) for n in range(1, 5)]
    with factory() as session:
        seed_cdm_frontpages(session, refs, broken={_ref(2)})
    store = FrontpageQcStore(factory)
    store.create_all(engine)
    repository = FakeRepository(refs)

    monkeypatch.setattr(api, "_cdm_session_factory", lambda: factory)
    monkeypatch.setattr(api, "submit_detached_task", lambda _name, func, *args, **kwargs: func(*args, **kwargs))

    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.require_frontpage_qc_user] = lambda: USER
    app.dependency_overrides[api.get_frontpage_qc_store] = lambda: store
    app.dependency_overrides[api.get_record_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, store, refs
    engine.dispose()


def _ref_payload(ref: FrontpageRef) -> Dict[str, str]:
    return {"institute_id": ref.institute_id, "patient_id": ref.patient_id, "visit_id": ref.visit_id}


def test_rules_catalog_lists_enabled_and_disabled_rules(env):
    client, _store, _refs = env
    data = client.get("/api/v1/frontpage-qc/rules").json()["data"]
    by_id = {item["rule_id"]: item for item in data["items"]}
    assert by_id["C-H24"]["points"] == 4
    assert by_id["C-H28"]["enabled"] is False
    assert "admission_datetime" in data["source_gap_fields"]


def test_filtered_run_scores_all_records_and_lists_results(env):
    client, store, refs = env
    run = client.post("/api/v1/frontpage-qc/runs", json={}).json()["data"]
    finished = client.get(f"/api/v1/frontpage-qc/runs/{run['id']}").json()["data"]
    assert finished["status"] == "completed"
    assert finished["success_count"] == 4
    assert finished["issue_records"] == 1

    listing = client.get("/api/v1/frontpage-qc/records", params={"page_size": 10}).json()["data"]
    assert listing["total"] == 4
    assert all(item["result"] for item in listing["items"])
    assert {item["result"]["department"] for item in listing["items"]} == {"外科", "内科"}

    failing = client.get("/api/v1/frontpage-qc/records", params={"issue": "fail"}).json()["data"]
    assert failing["total"] == 1
    assert failing["items"][0]["patient_name"] == "C02"
    assert failing["items"][0]["result"]["score"] == 96


def test_selected_run_and_unchecked_filter(env):
    client, _store, refs = env
    client.post("/api/v1/frontpage-qc/runs", json={"record_refs": [_ref_payload(refs[0])]})

    unchecked = client.get("/api/v1/frontpage-qc/records", params={"issue": "unchecked"}).json()["data"]
    assert unchecked["total"] == 3
    assert all(item["result"] is None for item in unchecked["items"])


def test_selected_record_without_frontpage_is_reported_not_dropped(env):
    client, _store, _refs = env
    run = client.post("/api/v1/frontpage-qc/runs", json={"record_refs": [_ref_payload(_ref(9))]}).json()["data"]
    finished = client.get(f"/api/v1/frontpage-qc/runs/{run['id']}").json()["data"]
    assert finished["status"] == "failed"
    assert finished["failed_records"][0]["message"] == "未找到病案首页"


def test_active_run_blocks_new_run(env):
    client, store, refs = env
    store.create_run(created_by=USER["id"], refs=refs, filters={}, ruleset_version="v")
    response = client.post("/api/v1/frontpage-qc/runs", json={})
    assert response.status_code == 409


def test_run_size_limit(env, monkeypatch):
    client, _store, _refs = env
    monkeypatch.setattr(api, "MAX_RECORDS_PER_RUN", 2)
    response = client.post("/api/v1/frontpage-qc/runs", json={})
    assert response.status_code == 422
    assert "单次最多 2 份" in response.json()["detail"]


def test_record_detail_review_and_stale_flag(env):
    client, store, refs = env
    client.post("/api/v1/frontpage-qc/runs", json={"record_refs": [_ref_payload(refs[1])]})
    params = _ref_payload(refs[1])
    detail = client.get("/api/v1/frontpage-qc/record", params=params).json()["data"]
    assert detail["record"]["patient_name"] == "C02"
    assert detail["stale"] is False
    assert detail["frontpage"]["basic"]["leaving_hospital_way"] == ""
    finding = next(f for f in detail["result"]["findings"] if f["rule_id"] == "C-H24")
    assert finding["deduction"] == 4

    rejected = client.post(f"/api/v1/frontpage-qc/findings/{finding['id']}/review", json={"status": "false_alarm"})
    assert rejected.status_code == 422
    saved = client.post(
        f"/api/v1/frontpage-qc/findings/{finding['id']}/review",
        json={"status": "false_alarm", "note": "HIS 已填写"},
    ).json()["data"]
    assert saved["review_status"] == "false_alarm"
    assert saved["reviewed_by"] == USER["id"]

    # 首页内容变化后提示结果已过期
    with api._cdm_session_factory()() as session:
        session.execute(sa.text("UPDATE mr SET leaving_hospital_way='医嘱离院' WHERE patient_id='C02'"))
        session.commit()
    assert client.get("/api/v1/frontpage-qc/record", params=params).json()["data"]["stale"] is True


def test_record_detail_without_result(env):
    client, _store, refs = env
    detail = client.get("/api/v1/frontpage-qc/record", params=_ref_payload(refs[0])).json()["data"]
    assert detail["result"] is None
    assert detail["stale"] is False
    assert client.get("/api/v1/frontpage-qc/record", params=_ref_payload(_ref(9))).status_code == 404


def test_analytics_and_export(env):
    client, _store, _refs = env
    client.post("/api/v1/frontpage-qc/runs", json={})
    report = client.get("/api/v1/frontpage-qc/analytics").json()["data"]
    assert report["summary"]["records"] == 4
    assert report["top_rules"][0]["rule_id"] == "C-H24"

    response = client.post("/api/v1/frontpage-qc/records/export", json={"department": "内科"})
    assert response.status_code == 200
    assert response.headers["x-export-total"] == "2"
    from openpyxl import load_workbook

    workbook = load_workbook(BytesIO(response.content))
    assert "内科" in workbook["病历结果"]["A1"].value
    assert workbook["病历结果"]["A3"].value in {"C02", "C04"}


def test_rule_drilldown_lists_and_exports_matching_records(env):
    client, _store, _refs = env
    client.post("/api/v1/frontpage-qc/runs", json={})
    report = client.get("/api/v1/frontpage-qc/analytics").json()["data"]

    hit = client.get("/api/v1/frontpage-qc/records", params={"rule_id": "C-H24"}).json()["data"]
    assert hit["total"] == 1
    assert hit["items"][0]["patient_name"] == "C02"
    assert client.get("/api/v1/frontpage-qc/records", params={"rule_id": "C-P01"}).json()["data"]["total"] == 0

    assert report["top_rules"][0]["rule_id"] == "C-H24"
    gaps = client.get(
        "/api/v1/frontpage-qc/records", params={"rule_id": "C-H24", "rule_verdict": "data_gap"}
    ).json()["data"]
    assert gaps["total"] == 0

    response = client.post("/api/v1/frontpage-qc/records/export", json={"rule_id": "C-H24"})
    assert response.status_code == 200
    assert response.headers["x-export-total"] == "1"


def test_rule_drilldown_rejects_unknown_rule_and_unchecked(env):
    client, _store, _refs = env
    assert client.get("/api/v1/frontpage-qc/records", params={"rule_id": "X-99"}).status_code == 422
    assert (
        client.get("/api/v1/frontpage-qc/records", params={"rule_id": "C-H24", "issue": "unchecked"}).status_code
        == 422
    )
    assert client.post("/api/v1/frontpage-qc/records/export", json={"rule_id": "X-99"}).status_code == 422


def test_export_without_results_is_rejected(env):
    client, _store, _refs = env
    assert client.post("/api/v1/frontpage-qc/records/export", json={}).status_code == 422


def test_cancel_only_own_run(env):
    client, store, refs = env
    other = store.create_run(created_by="someone-else", refs=refs, filters={}, ruleset_version="v")
    assert client.post(f"/api/v1/frontpage-qc/runs/{other['id']}/cancel").status_code == 403
    mine = store.create_run(created_by=USER["id"], refs=refs, filters={}, ruleset_version="v")
    cancelled = client.post(f"/api/v1/frontpage-qc/runs/{mine['id']}/cancel").json()["data"]
    assert cancelled["status"] == "cancelled"


def test_store_unavailable_returns_503(tmp_path, monkeypatch):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'empty.sqlite'}")
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.require_frontpage_qc_user] = lambda: USER
    app.dependency_overrides[api.get_frontpage_qc_store] = lambda: FrontpageQcStore(sessionmaker(bind=engine))
    with TestClient(app) as client:
        response = client.get("/api/v1/frontpage-qc/analytics")
    assert response.status_code == 503
    assert "20261013_000048" in response.json()["detail"]


@pytest.mark.asyncio
async def test_role_guard_rejects_doctor():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        await api.require_frontpage_qc_user({"id": "d1", "roles": ["doctor"]})
    assert caught.value.status_code == 403
