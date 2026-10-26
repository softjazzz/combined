"""可重复的医生/质控HTTP闭环模拟；只由专属合成PG运行器启动。"""

import csv
import io
import json

import sqlalchemy as sa
from test_report_alembic_upgrade import snapshot
from test_v5_feedback_pg import IDENTITY

pytest_plugins = ("test_v5_feedback_pg",)
BASE = "/api/v1/defect-rectifications"
REPORT = "/api/v1/quality-reports/record-quality/remediations"
NOTICES = "/api/v1/notifications"


def test_doctor_to_qc_closed_cycle(feedback, monkeypatch, record_property):
    engine, _, _, service, http, actor, job, scene = feedback
    trace = []

    def request(user, method, path, *, expected=200, **kwargs):
        actor(user)
        response = http.request(method, path, **kwargs)
        assert response.status_code == expected, response.text
        return response

    def data(user, path, **params):
        return request(user, "GET", path, params=params).json()["data"]

    def report(label):
        return data("qc", REPORT, scene=scene, defect_source="auto", label=label)

    def notices():
        result = data("doc", NOTICES)
        unread = data("doc", NOTICES, is_read=False)
        assert unread["total"] == result["unread_count"]
        return result

    assert report("not_dispatched")["total"] == 1
    assert notices()["total"] == 0
    with engine.connect() as conn:
        before = snapshot(conn)
    candidates = data("qc", f"{BASE}/candidates", **IDENTITY, expected_job_id=job["id"])
    assert len(candidates["targets"]) == 1
    target = {k: v for k, v in candidates["targets"][0].items() if k != "label"}
    payload = {
        **IDENTITY,
        **target,
        "assignee_id": "doc",
        "requirement": "合成验收：请补全记录并提交整改说明",
    }
    task = request("qc", "POST", BASE, json=payload).json()["data"]
    url = f"{BASE}/{task['id']}"

    def state(step, status, version, doctor_todo, qc_todo, label, notification_count):
        detail = data("qc", url)
        assert (detail["status"], detail["version"]) == (status, version)
        for user, statuses, expected in (
            ("doc", ("pending", "rejected"), doctor_todo),
            ("qc", ("submitted",), qc_todo),
        ):
            total = 0
            for value in statuses:
                page = data(user, BASE, state=value)
                assert all(item["id"] == task["id"] for item in page["items"])
                total += page["total"]
            assert total == expected
        analysis = report(label)
        assert analysis["total"] == 1
        row = analysis["items"][0]
        assert row["rectification_id"] == task["id"]
        report_state = "pending_acceptance" if status == "submitted" else status
        assert row["rectification_state"] == report_state
        assert row["root_job_id"] == job["id"]
        assert row["envelope_id"] == target["envelope_id"]
        messages = notices()
        assert messages["total"] == notification_count
        assert all(
            item["interaction_target"] == {"kind": "rectification", "id": task["id"]}
            for item in messages["items"]
        )
        assert data("other", NOTICES)["total"] == 0
        assert data("cross", NOTICES)["total"] == 0
        trace.append(
            {
                "step": step,
                "status": status,
                "version": version,
                "doctor_todo": doctor_todo,
                "qc_todo": qc_todo,
                "report_label": label,
                "notifications": notification_count,
            }
        )
        return detail

    def act(user, version, action, expected=200):
        return request(
            user,
            "POST",
            f"{url}/actions",
            expected=expected,
            json={
                "version": version,
                "action": action,
                "comment": f"合成闭环第{version}版：{action}的处理说明，不作为医疗结论",
            },
        )

    state("质控派发", "pending", 1, 1, 0, "not_urged_pending", 1)
    request("qc", "POST", BASE, expected=409, json=payload)
    request("other", "GET", url, expected=403)
    request("cross", "GET", url, expected=403)
    act("other", 1, "submit", 403)
    act("qc", 1, "submit", 403)
    assigned = notices()["items"][0]
    request("other", "PUT", f"{NOTICES}/{assigned['id']}/read", expected=404)
    request("doc", "PUT", f"{NOTICES}/{assigned['id']}/read")
    assert notices()["unread_count"] == 0
    state("医生接收消息（已读不代替提交）", "pending", 1, 1, 0, "not_urged_pending", 1)
    act("qc", 1, "urge")
    state("质控催办", "pending", 2, 1, 0, "urged_pending", 2)
    act("doc", 1, "submit", 409)

    def edit_synthetic_document(round_number):
        # 模拟外部电子病历系统保存，只写专属测试集群的合成文书，不冒充产品编辑API。
        with engine.begin() as conn:
            document = sa.Table(
                "admission_record", sa.MetaData(), schema="cdm", autoload_with=conn
            )
            result = conn.execute(
                document.update()
                .where(*(document.c[key] == value for key, value in IDENTITY.items()))
                .values(
                    record_content=f"合成第{round_number}次整改正文",
                    chief_complaint=f"合成第{round_number}次整改主诉",
                )
            )
            assert result.rowcount == 1

    edit_synthetic_document(1)
    act("doc", 2, "submit")
    submitted = state("医生首次提交", "submitted", 3, 0, 1, "pending_acceptance", 2)
    first_event = submitted["events"][-1]["id"]
    first_comparison = data("qc", f"{url}/comparison", event_id=first_event)
    assert first_comparison["available"] is True

    def admission_comparison(result):
        return next(
            document
            for document in result["documents"]
            if document["key"][1] == "admission_record"
        )

    first_document = admission_comparison(first_comparison)
    assert first_document["state"] == "matched"
    assert "合成整改前主诉" in first_document["before"]["content"]
    assert "合成第1次整改主诉" in first_document["after"]["content"]
    act("doc", 3, "approve", 403)

    def fail_notification(*_args, **_kwargs):
        raise RuntimeError("synthetic notification failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(service, "notification_writer", fail_notification)
        act("qc", 3, "reject", 503)
    rolled_back = state(
        "通知失败整笔回滚", "submitted", 3, 0, 1, "pending_acceptance", 2
    )
    assert rolled_back["events"] == submitted["events"]
    act("qc", 3, "reject")
    state("质控驳回", "rejected", 4, 1, 0, "not_urged_pending", 3)
    assert any(item["title"] == "整改驳回待重提" for item in notices()["items"])
    edit_synthetic_document(2)
    act("doc", 4, "submit")
    resubmitted = state("医生重提", "submitted", 5, 0, 1, "pending_acceptance", 3)
    second_event = resubmitted["events"][-1]["id"]
    assert data("qc", f"{url}/comparison", event_id=first_event) == first_comparison
    comparison = data("qc", f"{url}/comparison", event_id=second_event)
    second_document = admission_comparison(comparison)
    assert second_document["before"] == first_document["before"]
    assert "合成第2次整改主诉" in second_document["after"]["content"]
    act("qc", 5, "approve")
    completed = state("质控验收", "approved", 6, 0, 0, "self_rectified", 4)
    assert [event["action"] for event in completed["events"]] == [
        "assign",
        "urge",
        "submit",
        "reject",
        "submit",
        "approve",
    ]
    act("qc", 5, "approve", 409)
    act("doc", 6, "submit", 409)
    for message in notices()["items"]:
        request("doc", "PUT", f"{NOTICES}/{message['id']}/read")
    assert notices()["unread_count"] == 0
    state("医生读取验收结果", "approved", 6, 0, 0, "self_rectified", 4)
    exported = request(
        "qc",
        "GET",
        f"{REPORT}/export",
        params={
            "scene": scene,
            "defect_source": "auto",
            "label": "self_rectified",
        },
    )
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["rectification_id"] == task["id"]
    assert rows[0]["rectification_state"] == "approved"
    assert report("pending_acceptance")["total"] == 0
    assert report("urged_rectified")["total"] == 0
    request("doc", "GET", REPORT, expected=403, params={"scene": scene})
    assert data("cross", REPORT, scene=scene)["total"] == 0

    allowed = {
        ("qc", "qc_defect_rectifications"),
        ("qc", "qc_defect_rectification_events"),
        ("qc", "notifications"),
        ("cdm", "admission_record"),
    }
    with engine.connect() as conn:
        after = snapshot(conn)
    assert before.keys() == after.keys()
    for key, old in before.items():
        for field in ("columns", "indexes", "constraints"):
            assert old[field] == after[key][field], (key, field)
        if key not in allowed:
            assert old["rows"] == after[key]["rows"], key
    evidence = {
        "scene": scene,
        "task_id": task["id"],
        "synthetic_only": True,
        "transport": "FastAPI TestClient (in-process HTTP)",
        "normal_login": True,
        "steps": trace,
        "events": len(completed["events"]),
        "report_and_csv_agree": True,
        "saved_results_unchanged": True,
        "notification_failure_rolled_back": True,
        "business_database_writes": 0,
        "real_model_calls": 0,
    }
    record_property("v5_doctor_qc_cycle", json.dumps(evidence, ensure_ascii=False))
    print("V5_DOCTOR_QC_CYCLE=" + json.dumps(evidence, ensure_ascii=False))
