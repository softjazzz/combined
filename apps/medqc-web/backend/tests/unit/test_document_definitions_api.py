from __future__ import annotations

import io

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDocumentDefinition
from app.routers import document_definitions as routes
from app.services import document_definition_service as service
from app.services.document_definition_excel_service import SHEET_NAME, build_document_definition_template

BASE = "/api/v1/document-definitions"


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCDocumentDefinition.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _client(roles=("admin",)):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {
        "id": "user-1", "roles": list(roles),
    }
    return TestClient(app)


def _xlsx(*rows):
    workbook = load_workbook(io.BytesIO(build_document_definition_template()))
    sheet = workbook[SHEET_NAME]
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_template_import_and_list_http_contract(sessions):
    http = _client(("qc_manager",))
    template = http.get(f"{BASE}/import-template")
    assert template.status_code == 200
    assert template.headers["cache-control"] == "no-store"
    assert "V3.6-document-definition-import-template.xlsx" in template.headers["content-disposition"]

    imported = http.post(
        f"{BASE}/import",
        files={"file": ("definitions.xlsx", _xlsx(("DOC-01", "入院记录", "住院", "正文")),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert imported.status_code == 200
    data = imported.json()["data"]
    assert data["imported_count"] == 1
    assert data["items"][0]["template_content"] == "正文"
    assert data["items"][0]["created_at"].endswith("Z")

    listed = http.get(BASE, params={"page": 1, "page_size": 20})
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1
    assert listed.json()["data"]["items"][0]["code"] == "DOC-01"


def test_duplicate_is_409_and_bad_row_is_422(sessions):
    http = _client()
    payload = _xlsx(("DOC-01", "入院记录", "住院", "正文"))
    assert http.post(f"{BASE}/import", files={"file": ("a.xlsx", payload)}).status_code == 200
    duplicate = http.post(f"{BASE}/import", files={"file": ("a.xlsx", payload)})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "document_definition_code_conflict"
    invalid = http.post(
        f"{BASE}/import", files={"file": ("bad.xlsx", _xlsx(("", "甲", "住院", "正文")))},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["problems"][0]["row"] == 2


def test_role_and_extension_are_rejected(sessions):
    assert _client(("doctor",)).get(BASE).status_code == 403
    response = _client().post(f"{BASE}/import", files={"file": ("a.csv", b"x", "text/csv")})
    assert response.status_code == 422


def test_unknown_import_result_warns_not_to_retry(monkeypatch):
    monkeypatch.setattr(routes, "parse_document_definition_workbook", lambda _content: (object(),))
    monkeypatch.setattr(
        routes, "import_document_definitions",
        lambda **_kwargs: (_ for _ in ()).throw(service.DocumentDefinitionUnavailable("secret SQL")),
    )
    response = _client().post(f"{BASE}/import", files={"file": ("a.xlsx", b"stub")})
    assert response.status_code == 503
    assert "勿直接重复导入" in response.json()["detail"]
    assert "secret" not in response.text
