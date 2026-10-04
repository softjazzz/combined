"""质量分析报告草稿：只引用本会话统计来源，数值须为来源原值，统计变化后回读409；仅合成数据。"""
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

CONTEXT = dict(view="manager", institute_id="H", department="科室", care_phase="discharged",
               completed_from="2026-09-01T00:00:00+08:00", completed_to="2026-09-30T23:59:59+08:00")
USER = {"id": "m", "roles": ["doctor", "qc_manager"]}


def payload(count=5):
    return {"kpis": {"scoped_record_total": 50, "ready_record_total": 6, "unavailable_result_total": 2},
            "rule_distribution": [{"rule_id": "LX0609-01-01-01", "rule_name": "规则甲", "evaluated_count": 6, "non_compliant_count": count, "data_gap_count": 1}],
            "record_page": {"items": []}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_schemas import BusinessContext
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store
    store = BusinessSessionStore(tmp_path)
    state = {"payload": payload()}
    monkeypatch.setattr(api, "api_client", lambda _: httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"data": state["payload"]}))))
    access = BusinessAccess({"version": 1, "accounts": {"m": {"doctor_cases": [{"institute_id": "H", "patient_id": "P", "visit_id": "V"}], "manager_scopes": [{"institute_id": "H", "department": "科室"}]}}})
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    client = TestClient(app)

    def session(context=CONTEXT):
        return f"/business/sessions/{store.create(USER, BusinessContext(**context))['session_id']}"
    return client, session, state


def statistics_id(client, url):
    return next(ref["id"] for ref in client.post(url + "/tools/query_statistics", json={}).json()["references"] if ref["kind"] == "statistics")


def test_report_uses_session_sources_by_default_and_rereads(env):
    client, session, state = env
    url = session()
    statistics_id(client, url)
    body = {"title": "9月外科质控", "body": "总体情况\n期间内有效保存结果6份，规则甲不合规5次、资料不足1次。"}
    response = client.post(url + "/tools/compose_quality_report", json=body)
    assert response.status_code == 200, response.text
    card = response.json()["references"][0]
    assert card["kind"] == "draft" and card["id"].startswith("report:")
    assert "规则甲不合规5次、资料不足1次。" in card["text"] and "1. 当前范围质控统计" in card["text"]
    assert "不是正式质量报告" in card["text"] and "数据限制" in card["text"]
    assert client.get(url + "/references/" + card["id"]).json() == card
    state["payload"] = payload(count=7)
    changed = client.get(url + "/references/" + card["id"])
    assert changed.status_code == 409 and "来源统计已更新" in changed.json()["detail"]


@pytest.mark.parametrize("text,message", [("不合规率为83.3%。", "未出现的数值"), ("较上月增加2次。", "比较、变化或因果"), ("整改后明显改善。", "比较、变化或因果")])
def test_computed_numbers_and_comparisons_are_rejected(env, text, message):
    client, session, _ = env
    url = session()
    statistics_id(client, url)
    response = client.post(url + "/tools/compose_quality_report", json={"title": "报告", "body": text})
    assert response.status_code == 422 and message in response.json()["detail"]


def test_sources_must_be_session_statistics_and_view_manager(env):
    client, session, _ = env
    url = session()
    empty = client.post(url + "/tools/compose_quality_report", json={"title": "报告", "body": "说明"})
    assert empty.status_code == 422 and "尚未读取统计" in empty.json()["detail"]
    bad = client.post(url + "/tools/compose_quality_report", json={"title": "报告", "body": "说明", "source_ids": ["statistics:unknown"]})
    assert bad.status_code == 422 and "本会话已读取" in bad.json()["detail"]
    doctor = session({"view": "doctor", "institute_id": "H", "patient_id": "P", "visit_id": "V"})
    assert client.post(doctor + "/tools/compose_quality_report", json={"title": "报告", "body": "说明"}).status_code == 422


def test_contract_error_names_field_and_type_without_values(env):
    client, session, _ = env
    url = session()
    response = client.post(url + "/tools/compose_quality_report", json={"title": "报告", "body": "敏感内容" * 500})
    detail = response.json()["detail"]
    assert response.status_code == 422 and "body 超过长度上限" in detail and "敏感内容" not in detail


def test_date_formats_compare_by_value():
    from app.services.qc_agent import business_reports as reports
    assert reports.numbers("2026年09月01日 16.010") == reports.numbers("2026年9月1日 16.01")

def test_negated_disclaimer_is_not_a_comparison_claim():
    from app.services.qc_agent import business_reports as reports
    report = reports.ComposeReport(title="报告", body="本报告未作差值、比例或增长率计算，也未作环比比较。\n规则甲不合规5次。")
    reports.validate_report(report, {"s": {"title": "t", "text": "规则甲 不合规 5"}})
    for claim in ("较上月增加5次。", "与8月相比有所变化。", "整改后明显改善。"):
        try:
            reports.validate_report(reports.ComposeReport(title="报告", body=claim), {"s": {"title": "t", "text": "5 8"}})
        except Exception as exc:
            assert "比较、变化或因果" in exc.detail
        else:
            raise AssertionError(claim)

def test_status_distribution_values_are_valid_sources(env):
    client, session, state = env
    state["payload"] = {**payload(), "status_distribution": [{"status": "not_applicable", "count": 164}, {"status": "compliant", "count": 71}]}
    url = session()
    statistics_id(client, url)
    ok = client.post(url + "/tools/compose_quality_report", json={"title": "报告", "body": "规则结果中不适用164条、合规71条。"})
    assert ok.status_code == 200 and "规则结果条数：不适用 164；合规 71" in client.get(url + "/references/" + next(
        key for key in client.app.dependency_overrides[__import__("app.services.qc_agent.business_store", fromlist=["x"]).get_business_store]().get(url.rsplit("/", 1)[1], USER)["references"] if key.startswith("statistics:"))).json()["text"]
    bad = client.post(url + "/tools/compose_quality_report", json={"title": "报告", "body": "合计235条。"})
    assert bad.status_code == 422 and "235" in bad.json()["detail"]