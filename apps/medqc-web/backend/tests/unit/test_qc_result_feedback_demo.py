from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.security import get_current_user
from app.routers import qc_sichuan as qc_sichuan_module
from app.schemas.qc_sichuan import QcResultFeedbackRequest
from app.services.qc_workspace import result_feedback_demo_store as store_module
from app.services.qc_workspace.result_feedback_demo_store import (
    ResultFeedbackDemoConflict,
    ResultFeedbackDemoNotFound,
    ResultFeedbackDemoStore,
    ResultFeedbackDemoStoreUnavailable,
)


DEMO_USER = {
    "id": "admin-001",
    "email": "admin@medqc.com",
    "username": "admin",
    "roles": ["admin", "qc_manager"],
}
OTHER_USER = {
    "id": "doctor-001",
    "email": "doctor@example.com",
    "username": "doctor",
    "roles": ["doctor"],
}


class _FeedbackStore:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    def list_for_record(self, *, root_job_id: str, record_ref: str, created_by: str):
        return {
            item["rule_id"]: item
            for item in self.saved
            if item["root_job_id"] == root_job_id
            and item["record_ref"] == record_ref
            and item["created_by"] == created_by
        }

    def list_all(self, *, created_by: str, limit: int):
        return [item for item in self.saved if item["created_by"] == created_by][:limit]

    def save(self, **kwargs):
        self.saved.append(
            {
                "root_job_id": kwargs["root_job_id"],
                "record_ref": kwargs["record_ref"],
                "rule_id": kwargs["rule_id"],
                "original_status": "non_compliant",
                "feedback_type": kwargs["payload"].feedback_type,
                "expected_status": kwargs["payload"].expected_status,
                "error_category": kwargs["payload"].error_category,
                "comment": kwargs["payload"].comment,
                "result_digest": "a" * 64,
                "created_by": kwargs["created_by"],
                "created_at": "2026-08-18T10:00:00+00:00",
                "updated_at": "2026-08-18T10:00:00+00:00",
            }
        )
        return self.saved[-1]


def _client(monkeypatch, user: dict, store: _FeedbackStore | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(qc_sichuan_module.router)
    app.dependency_overrides[get_current_user] = lambda: user
    if store is not None:
        monkeypatch.setattr(
            qc_sichuan_module,
            "get_result_feedback_demo_store",
            lambda: store,
            raising=False,
        )
    return TestClient(app)


def test_demo_account_can_load_current_feedback(monkeypatch):
    store = _FeedbackStore()
    store.saved.append(
        {
            "root_job_id": "root-1",
            "record_ref": "rec_0123456789abcdef01234567",
            "rule_id": "LX0609-01-01-01",
            "original_status": "compliant",
            "feedback_type": "correct",
            "expected_status": None,
            "error_category": None,
            "comment": "结果准确",
            "result_digest": "b" * 64,
            "created_by": "admin-001",
            "created_at": "2026-08-18T10:00:00+00:00",
            "updated_at": "2026-08-18T10:00:00+00:00",
        }
    )
    response = _client(monkeypatch, DEMO_USER, store).get(
        "/api/v1/qc/sichuan/workspace/result-feedback-demo",
        params={
            "root_job_id": "root-1",
            "record_ref": "rec_0123456789abcdef01234567",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["items"]["LX0609-01-01-01"]["feedback_type"] == "correct"


class _WorkspaceRecords:
    def collect_records(self, **_kwargs):
        return [
            {
                "institute_id": "hospital-1",
                "patient_id": "patient-1",
                "visit_id": "208790-合成检验v1",
                "patient_name": "冯丽平",
                "inpat_no": "208790",
                "department": "重症医学科（ICU）",
                "scope": "final",
            }
        ]


def test_demo_account_can_load_all_feedback_with_safe_record_context(monkeypatch):
    store = _FeedbackStore()
    store.saved.extend(
        [
            {
                "root_job_id": "root-1",
                "record_ref": "rec_0123456789abcdef01234567",
                "rule_id": "LX0609-01-01-01",
                "original_status": "compliant",
                "feedback_type": "correct",
                "expected_status": None,
                "error_category": None,
                "comment": "结果准确",
                "result_digest": "b" * 64,
                "created_by": "admin-001",
                "created_at": "2026-08-18T10:00:00+00:00",
                "updated_at": "2026-08-18T10:00:00+00:00",
            },
            {
                "root_job_id": "root-2",
                "record_ref": "rec_abcdefabcdefabcdefabcdef",
                "rule_id": "LX0609-06-01-05",
                "original_status": "non_compliant",
                "feedback_type": "incorrect",
                "expected_status": "data_gap",
                "error_category": "wrong_status",
                "comment": "需复核时间窗",
                "result_digest": "c" * 64,
                "created_by": "admin-001",
                "created_at": "2026-08-18T11:00:00+00:00",
                "updated_at": "2026-08-18T11:00:00+00:00",
                "rule_name": "CT/MRI阳性结果分析",
                "_record_identity": {
                    "institute_id": "hospital-1",
                    "patient_id": "patient-1",
                    "visit_id": "208790-合成检验v1",
                },
            },
        ]
    )

    monkeypatch.setattr(
        qc_sichuan_module,
        "_sichuan_workspace_service",
        lambda: _WorkspaceRecords(),
    )

    response = _client(monkeypatch, DEMO_USER, store).get(
        "/api/v1/qc/sichuan/workspace/result-feedback-demo/all"
    )

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 2
    feedback = response.json()["data"]["items"][1]
    assert feedback["rule_id"] == "LX0609-06-01-05"
    assert feedback["rule_name"] == "CT/MRI阳性结果分析"
    assert feedback["patient_name"] == "冯丽平"
    assert feedback["record_number"] == "208790"
    assert feedback["visit_id"] == "208790-合成检验v1"
    assert feedback["department"] == "重症医学科（ICU）"
    assert "hospital-1" not in response.text
    assert "patient-1" not in response.text


def test_non_demo_account_is_rejected_by_backend(monkeypatch):
    response = _client(monkeypatch, OTHER_USER, _FeedbackStore()).get(
        "/api/v1/qc/sichuan/workspace/result-feedback-demo",
        params={
            "root_job_id": "root-1",
            "record_ref": "rec_0123456789abcdef01234567",
        },
    )

    assert response.status_code == 403
    assert "admin@medqc.com" not in response.text

    all_response = _client(monkeypatch, OTHER_USER, _FeedbackStore()).get(
        "/api/v1/qc/sichuan/workspace/result-feedback-demo/all"
    )
    assert all_response.status_code == 403


def test_admin_role_without_fixed_demo_identity_is_rejected(monkeypatch):
    response = _client(
        monkeypatch,
        {
            "id": "another-admin",
            "email": "admin@other.example",
            "roles": ["admin"],
        },
        _FeedbackStore(),
    ).get(
        "/api/v1/qc/sichuan/workspace/result-feedback-demo",
        params={
            "root_job_id": "root-1",
            "record_ref": "rec_0123456789abcdef01234567",
        },
    )

    assert response.status_code == 403


def test_demo_account_can_submit_current_feedback(monkeypatch):
    store = _FeedbackStore()
    response = _client(monkeypatch, DEMO_USER, store).put(
        "/api/v1/qc/sichuan/workspace/result-feedback-demo/LX0609-01-01-01",
        json={
            "root_job_id": "root-1",
            "record_ref": "rec_0123456789abcdef01234567",
            "feedback_type": "incorrect",
            "expected_status": "not_applicable",
            "error_category": "wrong_status",
            "comment": "本次没有进行该项检查。",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["rule_id"] == "LX0609-01-01-01"
    assert store.saved[0]["root_job_id"] == "root-1"


def test_sensitive_comment_is_rejected_without_echoing_input(monkeypatch):
    sensitive_comment = "患者电话 13812345678"
    response = _client(monkeypatch, DEMO_USER, _FeedbackStore()).put(
        "/api/v1/qc/sichuan/workspace/result-feedback-demo/LX0609-01-01-01",
        json={
            "root_job_id": "root-1",
            "record_ref": "rec_0123456789abcdef01234567",
            "feedback_type": "note",
            "comment": sensitive_comment,
        },
    )

    assert response.status_code == 400
    assert sensitive_comment not in response.text


@pytest.mark.parametrize("sensitive_comment", [
    "住院号 1234567890",
    "身份证 510123199001011234",
])
def test_hospital_identity_like_digits_are_rejected_without_echoing_input(
    monkeypatch, sensitive_comment
):
    response = _client(monkeypatch, DEMO_USER, _FeedbackStore()).put(
        "/api/v1/qc/sichuan/workspace/result-feedback-demo/LX0609-01-01-01",
        json={
            "root_job_id": "root-1",
            "record_ref": "rec_0123456789abcdef01234567",
            "feedback_type": "note",
            "comment": sensitive_comment,
        },
    )

    assert response.status_code == 400
    assert sensitive_comment not in response.text


def test_feedback_table_unavailable_returns_delayed_503(monkeypatch):
    class _UnavailableStore:
        def list_for_record(self, **_kwargs):
            raise qc_sichuan_module.ResultFeedbackDemoStoreUnavailable()

    response = _client(monkeypatch, DEMO_USER, _UnavailableStore()).get(
        "/api/v1/qc/sichuan/workspace/result-feedback-demo",
        params={
            "root_job_id": "root-1",
            "record_ref": "rec_0123456789abcdef01234567",
        },
    )

    assert response.status_code == 503
    assert "反馈功能暂不可用" in response.text


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class _CanonicalReadSession:
    def __init__(self, canonical_rows, feedback_rows=None):
        self.canonical_rows = canonical_rows
        self.feedback_rows = feedback_rows or []
        self.executed_sql: list[str] = []

    def execute(self, statement):
        sql = str(statement)
        self.executed_sql.append(sql)
        if "luxian_0609_record_result_envelopes" in sql:
            return _Rows(self.canonical_rows)
        if "qc_result_feedback_demo" in sql and sql.lstrip().upper().startswith("SELECT"):
            return _Rows(self.feedback_rows)
        return _Rows([])

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def _canonical_row(*, root_job_id="root-1", record_ref="rec_0123456789abcdef01234567", version="v1"):
    import json

    return {
        "root_job_id": root_job_id,
        "created_by": "admin-001",
        "institute_id": "hospital-1",
        "patient_id": "patient-1",
        "visit_id": "208790-合成检验v1",
        "envelope_json": json.dumps(
            {
                "root_job_id": root_job_id,
                "record_ref": record_ref,
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": version,
                "items": [
                    {
                        "rule_id": "LX0609-01-01-01",
                        "rule_name": "入院记录完成时限",
                        "status": "non_compliant",
                        "reason_code": "missing_record",
                        "customer_display_facts": {"summary": "受控测试"},
                        "evidence": [],
                    }
                ],
            },
            ensure_ascii=False,
        ),
    }


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("schema_version", "unknown-envelope-v1"),
        ("delivery_mode", "legacy_items_json"),
    ],
)
def test_feedback_rejects_explicitly_invalid_canonical_envelope_metadata(
    field: str, invalid_value: str,
) -> None:
    import json

    row = _canonical_row()
    envelope = json.loads(row["envelope_json"])
    envelope[field] = invalid_value
    row["envelope_json"] = json.dumps(envelope, ensure_ascii=False)

    with pytest.raises(ResultFeedbackDemoConflict):
        ResultFeedbackDemoStore._canonical_item_from_row(
            row,
            root_job_id="root-1",
            record_ref="rec_0123456789abcdef01234567",
            rule_id="LX0609-01-01-01",
        )


def _feedback_row():
    return {
        "id": "feedback-1",
        "root_job_id": "root-1",
        "record_ref": "rec_0123456789abcdef01234567",
        "rule_id": "LX0609-01-01-01",
        "original_status": "non_compliant",
        "feedback_type": "incorrect",
        "expected_status": "not_applicable",
        "error_category": "wrong_status",
        "comment": "本次未发生该事件。",
        "result_digest": "a" * 64,
        "created_by": "admin-001",
        "created_at": "2026-08-18T10:00:00+00:00",
        "updated_at": "2026-08-18T10:00:00+00:00",
    }


def _payload(**overrides):
    values = {
        "root_job_id": "root-1",
        "record_ref": "rec_0123456789abcdef01234567",
        "feedback_type": "incorrect",
        "expected_status": "not_applicable",
        "error_category": "wrong_status",
        "comment": "本次未发生该事件。",
    }
    values.update(overrides)
    return QcResultFeedbackRequest.model_validate(values)


def test_store_rejects_child_root_or_missing_canonical_result(monkeypatch):
    session = _CanonicalReadSession([])
    monkeypatch.setattr(store_module, "engine", object())
    monkeypatch.setattr(store_module, "_session", lambda: session)
    store_module._feedback_table.cache_clear()
    store = ResultFeedbackDemoStore()

    with pytest.raises(ResultFeedbackDemoNotFound):
        store.save(
            root_job_id="child-1",
            record_ref="rec_0123456789abcdef01234567",
            rule_id="LX0609-01-01-01",
            created_by="admin-001",
            payload=_payload(root_job_id="child-1"),
        )


def test_store_rejects_duplicate_or_mismatched_rule_version_envelopes(monkeypatch):
    rows = [_canonical_row(version="v1"), _canonical_row(version="v2")]
    session = _CanonicalReadSession(rows)
    monkeypatch.setattr(store_module, "engine", object())
    monkeypatch.setattr(store_module, "_session", lambda: session)
    store_module._feedback_table.cache_clear()
    store = ResultFeedbackDemoStore()

    with pytest.raises(ResultFeedbackDemoConflict):
        store.save(
            root_job_id="root-1",
            record_ref="rec_0123456789abcdef01234567",
            rule_id="LX0609-01-01-01",
            created_by="admin-001",
            payload=_payload(),
        )


def _formal_canonical_row(item: dict) -> dict:
    """正式 Canonical Envelope：带 schema 与交付模式，条目逐项校验公开事实合同。"""

    import json

    from app.services.qc_workspace.canonical_result_store import (
        CANONICAL_RESULT_DELIVERY_MODE,
        RECORD_RESULT_ENVELOPE_SCHEMA,
    )

    row = _canonical_row()
    envelope = json.loads(row["envelope_json"])
    envelope["schema_version"] = RECORD_RESULT_ENVELOPE_SCHEMA
    envelope["delivery_mode"] = CANONICAL_RESULT_DELIVERY_MODE
    envelope["items"] = [item]
    row["envelope_json"] = json.dumps(envelope, ensure_ascii=False)
    return row


def _published_admission_item() -> dict:
    from tests.luxian_0609_published_result_support import published_lx0609_items

    return dict(published_lx0609_items(admission="late")["LX0609-01-01-01"])


def _store_for(monkeypatch, rows, **session_kwargs):
    session = _CanonicalReadSession(rows, **session_kwargs)
    monkeypatch.setattr(store_module, "engine", object())
    monkeypatch.setattr(store_module, "_session", lambda: session)
    store_module._feedback_table.cache_clear()
    return ResultFeedbackDemoStore()


@pytest.mark.parametrize("deprecated_seal", [False, True])
def test_store_accepts_published_formal_result_without_seal(monkeypatch, deprecated_seal):
    item = _published_admission_item()
    assert item["status"] == "non_compliant"
    assert "customer_text_seal" not in item
    if deprecated_seal:
        # 历史结果附带的废弃签章字段不校验，也不因失效而拒绝合法结果。
        item["customer_text_seal"] = "lx0609-customer-text-v1:" + "0" * 64
    store = _store_for(monkeypatch, [_formal_canonical_row(item)])

    result = store.save(
        root_job_id="root-1",
        record_ref="rec_0123456789abcdef01234567",
        rule_id="LX0609-01-01-01",
        created_by="admin-001",
        payload=_payload(),
    )

    assert result["original_status"] == "non_compliant"


def test_store_rejects_formal_result_missing_required_facts(monkeypatch):
    item = _published_admission_item()
    item["customer_display_facts"] = None
    store = _store_for(monkeypatch, [_formal_canonical_row(item)])

    with pytest.raises(ResultFeedbackDemoConflict):
        store.save(
            root_job_id="root-1",
            record_ref="rec_0123456789abcdef01234567",
            rule_id="LX0609-01-01-01",
            created_by="admin-001",
            payload=_payload(),
        )


def test_store_rejects_formal_result_missing_required_facts_when_reading_feedback(monkeypatch):
    item = _published_admission_item()
    item["customer_display_facts"] = None
    store = _store_for(
        monkeypatch, [_formal_canonical_row(item)], feedback_rows=[_feedback_row()],
    )

    with pytest.raises(ResultFeedbackDemoConflict):
        store.list_for_record(
            root_job_id="root-1",
            record_ref="rec_0123456789abcdef01234567",
            created_by="admin-001",
        )
    with pytest.raises(ResultFeedbackDemoConflict):
        store.list_all(created_by="admin-001", limit=20)


def test_store_rejects_envelope_owned_by_another_account(monkeypatch):
    session = _CanonicalReadSession([_canonical_row() | {"created_by": "other-user"}])
    monkeypatch.setattr(store_module, "engine", object())
    monkeypatch.setattr(store_module, "_session", lambda: session)
    store_module._feedback_table.cache_clear()
    store = ResultFeedbackDemoStore()

    with pytest.raises(ResultFeedbackDemoNotFound):
        store.save(
            root_job_id="root-1",
            record_ref="rec_0123456789abcdef01234567",
            rule_id="LX0609-01-01-01",
            created_by="admin-001",
            payload=_payload(),
        )


def test_store_fails_closed_when_canonical_table_provider_is_unavailable(monkeypatch):
    monkeypatch.setattr(store_module, "engine", object())
    monkeypatch.setattr(store_module, "_record_result_envelopes_table", lambda: None)
    store_module._feedback_table.cache_clear()

    with pytest.raises(ResultFeedbackDemoStoreUnavailable):
        ResultFeedbackDemoStore()


def test_store_reads_canonical_but_only_writes_feedback_table(monkeypatch):
    session = _CanonicalReadSession([_canonical_row()])
    monkeypatch.setattr(store_module, "engine", object())
    monkeypatch.setattr(store_module, "_session", lambda: session)
    store_module._feedback_table.cache_clear()
    store = ResultFeedbackDemoStore()

    result = store.save(
        root_job_id="root-1",
        record_ref="rec_0123456789abcdef01234567",
        rule_id="LX0609-01-01-01",
        created_by="admin-001",
        payload=_payload(),
    )

    assert result["original_status"] == "non_compliant"
    assert result["result_digest"]
    writes = [
        sql
        for sql in session.executed_sql
        if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
    ]
    assert any("qc_result_feedback_demo" in sql for sql in writes)
    assert all("luxian_0609_record_result_envelopes" not in sql for sql in writes)


def test_store_list_all_binds_feedback_to_canonical_record_context(monkeypatch):
    session = _CanonicalReadSession(
        [_canonical_row()],
        feedback_rows=[_feedback_row()],
    )
    monkeypatch.setattr(store_module, "engine", object())
    monkeypatch.setattr(store_module, "_session", lambda: session)
    store_module._feedback_table.cache_clear()

    items = ResultFeedbackDemoStore().list_all(created_by="admin-001", limit=200)

    assert items == [
        _feedback_row()
        | {
            "rule_name": "入院记录完成时限",
            "_record_identity": {
                "institute_id": "hospital-1",
                "patient_id": "patient-1",
                "visit_id": "208790-合成检验v1",
            },
        }
    ]
    assert "envelope_json" not in items[0]
