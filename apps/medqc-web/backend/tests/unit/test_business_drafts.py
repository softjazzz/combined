"""参考草稿：事实须有保存证据、数值不得虚构、仅医生不合规问题、回读重验版本；仅合成数据。"""
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


RULE = "LX0609-01-01-01"
IDENTITY = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
EVIDENCE = [{"source_type": "daily_course_record", "source_ref": "S1", "record_time": "2026-09-03 08:30",
             "evidence_excerpt": "患者行胸部CT检查，结果示右下肺斑片影。"}]


def build(tmp_path, monkeypatch, saved, view="doctor"):
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_schemas import BusinessContext
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store

    user = {"id": "doctor", "roles": ["doctor", "qc_manager"]}
    store = BusinessSessionStore(tmp_path)
    context = {"view": "doctor", **IDENTITY} if view == "doctor" else {
        "view": "manager", "institute_id": "H", "department": "科室", "care_phase": "discharged",
        "completed_from": "2026-09-01T00:00:00+08:00", "completed_to": "2026-09-30T23:59:59+08:00"}
    session = store.create(user, BusinessContext(**context))
    access = BusinessAccess({"version": 1, "accounts": {user["id"]: {"doctor_cases": [IDENTITY], "manager_scopes": [{"institute_id": "H", "department": "科室"}]}}})
    monkeypatch.setattr(api, "api_client", lambda _: httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"data": saved}))))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    return TestClient(app), f"/business/sessions/{session['session_id']}", store, session, user


def saved_payload(status="non_compliant"):
    return {"state": "ready", "job_id": "job", "record_ref": "rec", "is_complete": True, "missing_rule_ids": [], "conflicting_rule_ids": [],
            "items": [{"rule_id": RULE, "status": status, "conclusion": "报告后24小时内未记录，间隔16.01小时", "suggestion": "补记CT检查原因", "evidence": EVIDENCE}]}


def test_saved_conclusion_is_position_zero_source(tmp_path, monkeypatch):
    client, url, *_ = build(tmp_path, monkeypatch, saved_payload())
    result_id = viewed(client, url)
    facts = client.post(url + "/tools/read_draft_facts", json={"result_id": result_id}).json()
    assert facts["evidence"][0] == {"evidence_position": 0, "source_type": "saved_conclusion", "record_time": None,
                                    "excerpt": "报告后24小时内未记录，间隔16.01小时"}
    ok = client.post(url + "/tools/compose_reference_draft", json={"result_id": result_id, "segments": [
        {"kind": "fact", "text": "间隔16.01小时。", "evidence_positions": [0]}]})
    assert ok.status_code == 200 and "［依据保存结论］" in ok.json()["references"][0]["text"]
    # 结论里的数值不能挂到未包含该数值的证据上。
    bad = client.post(url + "/tools/compose_reference_draft", json={"result_id": result_id, "segments": [
        {"kind": "fact", "text": "间隔16.01小时。", "evidence_positions": [1]}]})
    assert bad.status_code == 422


def viewed(client, url):
    return client.post(url + "/tools/read_saved_results", json={}).json()["references"][0]["id"]


def test_facts_then_validated_draft_card_and_reread(tmp_path, monkeypatch):
    saved = saved_payload()
    client, url, store, session, user = build(tmp_path, monkeypatch, saved)
    result_id = viewed(client, url)
    facts = client.post(url + "/tools/read_draft_facts", json={"result_id": result_id}).json()
    assert facts["evidence"][1]["excerpt"] == EVIDENCE[0]["evidence_excerpt"]
    assert facts["suggestion"] == "补记CT检查原因"
    segments = [{"kind": "fact", "text": "2026-09-03 08:30 行胸部CT检查，示右下肺斑片影。", "evidence_positions": [1]},
                {"kind": "placeholder", "text": "待医生补充：本次CT检查的临床指征及申请原因"}]
    response = client.post(url + "/tools/compose_reference_draft", json={"result_id": result_id, "segments": segments})
    assert response.status_code == 200
    card = response.json()["references"][0]
    assert card["kind"] == "draft" and card["id"].startswith("draft:")
    assert "参考草稿" in card["text"] and "复制或采用草稿不等于整改完成" in card["text"]
    assert "［依据保存证据1］" in card["text"] and "【待医生补充：本次CT检查的临床指征及申请原因】" in card["text"]
    assert "正式保存建议（原文，未改动）：\n补记CT检查原因" in card["text"]
    assert response.json()["draft"] == {"result_id": result_id, "segment_count": 2, "placeholder_count": 1}
    again = client.get(url + "/references/" + card["id"])
    assert again.status_code == 200 and again.json() == card
    # 保存版本变化后不再展示旧草稿，也不改用新结果起草。
    saved["job_id"] = "replacement"
    assert client.get(url + "/references/" + card["id"]).status_code == 409


def test_placeholder_may_use_known_limits_and_prefix_is_normalized():
    from app.services.qc_agent import business_drafts as drafts
    segments = [drafts.DraftSegment(kind="placeholder", text="（待医生补充）报告后24小时内的记录时间")]
    evidence = drafts.draft_evidence([], "报告后24小时内未记录")
    drafts.validate_segments(segments, evidence, "请在报告出具后24小时内记录")
    text = drafts.draft_card_text({"suggestion": "建议"}, segments)
    assert "【待医生补充：报告后24小时内的记录时间】" in text and "（待医生补充）" not in text


@pytest.mark.parametrize("segment,message", [
    ({"kind": "fact", "text": "2026-09-04 行CT检查。", "evidence_positions": [1]}, "数值"),
    ({"kind": "fact", "text": "行CT检查。", "evidence_positions": [2]}, "不存在"),
    ({"kind": "placeholder", "text": "待医生补充：检查时间 10:00"}, "均未出现"),
])
def test_unsupported_numbers_or_positions_are_rejected(tmp_path, monkeypatch, segment, message):
    client, url, store, session, user = build(tmp_path, monkeypatch, saved_payload())
    result_id = viewed(client, url)
    response = client.post(url + "/tools/compose_reference_draft", json={"result_id": result_id, "segments": [segment]})
    assert response.status_code == 422 and message in response.json()["detail"]
    assert not any(binding["kind"] == "draft" for binding in store.get(session["session_id"], user)["references"].values())


def test_schema_rejects_fact_without_evidence_and_placeholder_with_evidence(tmp_path, monkeypatch):
    client, url, *_ = build(tmp_path, monkeypatch, saved_payload())
    result_id = viewed(client, url)
    for segment in ({"kind": "fact", "text": "行CT检查"}, {"kind": "placeholder", "text": "待补充", "evidence_positions": [1]}):
        assert client.post(url + "/tools/compose_reference_draft", json={"result_id": result_id, "segments": [segment]}).status_code == 422


def test_only_doctor_non_compliant_issue_can_be_drafted(tmp_path, monkeypatch):
    client, url, *_ = build(tmp_path, monkeypatch, saved_payload("data_gap"))
    result_id = viewed(client, url)
    response = client.post(url + "/tools/read_draft_facts", json={"result_id": result_id})
    assert response.status_code == 422 and "不合规" in response.json()["detail"]
    client, url, *_ = build(tmp_path / "m", monkeypatch, saved_payload(), view="manager")
    assert client.post(url + "/tools/read_draft_facts", json={"result_id": "result:job:rec:" + RULE}).status_code == 422
    # 未查看的问题不能起草。
    client, url, *_ = build(tmp_path / "d", monkeypatch, saved_payload())
    assert client.post(url + "/tools/read_draft_facts", json={"result_id": "result:job:rec:" + RULE}).status_code == 404


def test_tool_specs_expose_draft_only_to_doctor():
    from app.services.qc_agent.business_tools import tool_specs
    assert {"read_draft_facts", "compose_reference_draft"} <= {spec["name"] for spec in tool_specs("doctor")}
    assert not {"read_draft_facts", "compose_reference_draft"} & {spec["name"] for spec in tool_specs("manager")}


def test_fact_dates_compare_by_value_not_leading_zero():
    from app.services.qc_agent import business_drafts as drafts
    evidence = drafts.draft_evidence([{"evidence_excerpt": "检查于2025-08-03完成", "record_time": "2025-08-03 08:05"}])
    drafts.validate_segments([drafts.DraftSegment(kind="fact", text="2025年8月3日8时5分完成检查", evidence_positions=[1])], evidence)

@pytest.mark.parametrize("source,text", [
    ("剂量为0.5 mg。", "剂量为5 mg。"),
    ("剂量为0.5 mg。", "剂量为5.0 mg。"),
    ("数值为-0.5。", "数值为0.5。"),
    ("剂量为0.5 mg。", "剂量为0.5 g。"),
    ("剂量为0.5 mg，用药5天。", "5 mg。"),
    ("剂量为0.5 mg。", "剂量为0.5 m。"),
    ("数值为+0.5。", "数值为-0.5。"),
    ("剂量为1,000 mg。", "0 mg。"),
    ("数值为−0.5。", "数值为0.5。"),
    ("甲药剂量为0.5 mg，乙药剂量为5 mg。", "甲药剂量为5 mg。"),
])
def test_numeric_fact_cannot_change_value_unit_or_field(tmp_path, monkeypatch, source, text):
    saved = saved_payload()
    saved["items"][0]["evidence"] = [{"evidence_excerpt": source}]
    client, url, store, metadata, user = build(tmp_path, monkeypatch, saved)
    result_id = viewed(client, url)
    response = client.post(url + "/tools/compose_reference_draft", json={"result_id": result_id,
        "segments": [{"kind": "fact", "text": text, "evidence_positions": [1]}]})
    assert response.status_code == 422
    assert not any(ref["kind"] == "draft" for ref in store.get(metadata["session_id"], user)["references"].values())


@pytest.mark.parametrize("text", ["剂量为0.5 mg。", "数值为-0.5。", "数值为+0.5。", "间隔16.01小时。"])
def test_supported_complete_numeric_clause_is_preserved(text):
    from app.services.qc_agent import business_drafts as drafts
    evidence = drafts.draft_evidence([{"evidence_excerpt": text}])
    segments = [drafts.DraftSegment(kind="fact", text=text, evidence_positions=[1])]
    drafts.validate_segments(segments, evidence)
    assert text + "［依据保存证据1］" in drafts.draft_card_text({}, segments)
