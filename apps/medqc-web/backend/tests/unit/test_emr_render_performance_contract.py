from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import emr_render as emr_router_module
from app.services.bundles import assembly as assembly_module
from app.services.bundles import emr_view as emr_view_module


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(emr_router_module.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-qc",
        "roles": ["qc_manager"],
        "role": "qc_manager",
    }
    return TestClient(app)


def test_documents_summary_view_does_not_load_or_return_full_document_content(monkeypatch):
    calls: list[str] = []

    def load_summaries(**_kwargs):
        calls.append("summary")
        return {
            "layout_version": "bundle_struct_v1",
            "documents": [
                {
                    "id": "DOC-1",
                    "doc_key": "daily_course_record::DOC-1",
                    "doc_type": "daily_course_record",
                    "doc_name": "日常病程记录",
                    "execution_domain": "course",
                    "has_content": True,
                    "length": 128,
                }
            ],
            "documents_tree": [],
            "domain_bundle_hits": {"course": True},
            "empty_reason": "",
        }

    def reject_full_load(**_kwargs):
        raise AssertionError("摘要目录不得加载完整 Bundle 文书")

    monkeypatch.setattr(
        emr_router_module,
        "_load_document_summaries_from_bundle",
        load_summaries,
        raising=False,
    )
    monkeypatch.setattr(emr_router_module, "_load_documents_from_bundle", reject_full_load)

    response = _client().get(
        "/api/v1/emr/V1/documents",
        params={
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "view": "summary",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert calls == ["summary"]
    assert payload["documents"][0]["execution_domain"] == "course"
    assert "content" not in payload["documents"][0]


def test_documents_summary_view_projects_customer_safe_source_ref(monkeypatch):
    monkeypatch.setattr(
        emr_router_module,
        "load_bundle_document_summaries",
        lambda **_kwargs: {
            "layout_version": "bundle_struct_v1",
            "documents": [
                {
                    "document_id": "DOC-1",
                    "doc_id": "DOC-1",
                    "doc_type": "daily_course_record",
                    "execution_domain": "course",
                    "has_content": True,
                }
            ],
            "documents_tree": [],
            "domain_bundle_hits": {"course": True},
            "empty_reason": "",
        },
    )

    payload = emr_router_module._load_document_summaries_from_bundle(
        record_id="V1",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
    )

    assert payload["documents"][0]["source_ref"] == (
        emr_router_module.build_customer_safe_source_ref("DOC-1")
    )


def test_render_with_execution_domain_loads_only_the_selected_domain(monkeypatch):
    calls: list[tuple[str, str]] = []

    def load_one_document(**kwargs):
        calls.append((kwargs["execution_domain"], kwargs["doc_id"]))
        return {
            "id": "DOC-1",
            "doc_key": "daily_course_record::DOC-1",
            "doc_type": "daily_course_record",
            "doc_name": "日常病程记录",
            "document_id": "DOC-1",
            "content": "受控测试正文",
            "group_key": "course",
            "execution_domain": "course",
            "has_content": True,
            "length": 6,
        }

    monkeypatch.setattr(
        emr_router_module,
        "_load_document_from_bundle",
        load_one_document,
        raising=False,
    )
    monkeypatch.setattr(emr_router_module, "get_supabase", lambda: None)

    response = _client().get(
        "/api/v1/emr/V1/render",
        params={
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "doc_type": "daily_course_record",
            "doc_id": "DOC-1",
            "execution_domain": "course",
        },
    )

    assert response.status_code == 200
    assert calls == [("course", "DOC-1")]
    assert response.json()["data"]["content"] == "受控测试正文"


def test_bundle_document_summary_projection_keeps_metadata_but_drops_heavy_fields(monkeypatch):
    def load_index(*, execution_domain: str, **_kwargs):
        if execution_domain != "course":
            return None
        return {
            "bundle_schema_version": "domain_bundle_v4",
            "source_documents": [
                {
                    "document_type": "daily_course_record",
                    "document_id": "DOC-1",
                    "document_title": "日常病程记录",
                    "display_time": "2026-08-01 09:00:00",
                    "record_time": "2026-08-01 09:00:00",
                    "has_content": True,
                    "length": 128,
                    "projection_incomplete": False,
                    "projection_notice": "",
                    "content": "摘要接口不得返回的正文",
                    "source_fields": [{"raw_value_preview": "不得返回"}],
                }
            ],
            "structured_context": {"domain_projection": {"per_source": {}}},
        }

    monkeypatch.setattr(
        emr_view_module,
        "load_domain_bundle_document_index",
        load_index,
        raising=False,
    )

    payload = emr_view_module.load_bundle_document_summaries(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        bundle_schema="public",
    )

    assert len(payload["documents"]) == 1
    document = payload["documents"][0]
    assert document["document_id"] == "DOC-1"
    assert document["execution_domain"] == "course"
    assert document["has_content"] is True
    assert document["length"] == 128
    assert "content" not in document
    assert "source_fields" not in document
    assert payload["documents_tree"] == []


def test_direct_bundle_document_read_uses_one_domain_bundle(monkeypatch):
    calls: list[str] = []

    def load_render_bundle(*, execution_domain: str, doc_type: str, doc_id: str, **_kwargs):
        calls.append(execution_domain)
        assert doc_type == "daily_course_record"
        assert doc_id == "DOC-1"
        return {
            "bundle_schema_version": "domain_bundle_v4",
            "source_documents": [
                {
                    "document_type": "daily_course_record",
                    "document_id": "DOC-1",
                    "document_title": "日常病程记录",
                    "display_time": "2026-08-01 09:00:00",
                    "record_time": "2026-08-01 09:00:00",
                    "content": "受控测试正文",
                }
            ],
            "structured_context": {
                "source_table_coverage": {
                    "exam_master": {},
                    "exam_item_report": {},
                    "labtest_master": {},
                    "labtest_item_report": {},
                    "pathology_exam_master": {},
                    "pathology_exam_report": {},
                },
                "domain_projection": {"per_source": {}},
            },
        }

    monkeypatch.setattr(
        emr_view_module,
        "load_domain_bundle_for_emr_render",
        load_render_bundle,
        raising=False,
    )

    document = emr_view_module.load_bundle_document(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        execution_domain="course",
        doc_type="daily_course_record",
        doc_id="DOC-1",
        bundle_schema="public",
    )

    assert calls == ["course"]
    assert document is not None
    assert document["content"] == "受控测试正文"


def test_direct_bundle_document_read_locates_missing_document_id_by_summary_key(monkeypatch):
    class _MappingsResult:
        def __init__(self, row):
            self._row = row

        def mappings(self):
            return self

        def first(self):
            return self._row

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            sql = str(statement)
            locator_matches = (
                params.get("has_fallback_doc_index") is True
                and params.get("fallback_doc_index") == 1
                and "ordinal - 1" in sql
            )
            return _MappingsResult(
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "execution_domain": "course",
                    "bundle_schema_version": "domain_bundle_v4",
                    "bundle_updated_at": None,
                    "source_documents": [
                        {
                            "document_type": "daily_course_record",
                            "document_id": "",
                            "document_title": "查房记录",
                            "content": "客户源数据未提供文书编号时的正文",
                        }
                    ]
                    if locator_matches
                    else [],
                    "structured_context": {},
                }
            )

    class _Engine:
        def connect(self):
            return _Connection()

    monkeypatch.setattr(assembly_module, "engine", _Engine())

    document = emr_view_module.load_bundle_document(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        execution_domain="course",
        doc_type="daily_course_record",
        doc_id="daily_course_record::1",
        bundle_schema="public",
    )

    assert document is not None
    assert document["content"] == "客户源数据未提供文书编号时的正文"
