"""medical_documents 文书顺序字段的发布合同。"""

from dataclasses import dataclass
import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from app.database.models.qc import MedicalDocument
from app.main import create_app


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260811_000031_add_medical_document_sort_order.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "medical_document_sort_order_migration",
        MIGRATION_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class _Result:
    data: list[dict]


class _SchemaAwareQuery:
    def __init__(self, table_name: str) -> None:
        self.table_name = table_name

    def select(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def order(self, column_name: str, *_args, **_kwargs):
        if self.table_name == "medical_documents":
            assert column_name in MedicalDocument.__table__.columns
        return self

    def execute(self) -> _Result:
        if self.table_name == "medical_records":
            return _Result(
                data=[
                    {
                        "id": "record-sort-contract",
                        "patient_name": "发布烟测病例",
                        "created_at": "2026-08-11T00:00:00",
                    }
                ]
            )
        return _Result(
            data=[
                {
                    "id": "document-sort-contract",
                    "record_id": "record-sort-contract",
                    "content": "文书正文",
                    "sort_order": 0,
                }
            ]
        )


class _SchemaAwareClient:
    def table(self, table_name: str) -> _SchemaAwareQuery:
        return _SchemaAwareQuery(table_name)


def test_medical_document_model_exposes_non_nullable_sort_order() -> None:
    """公开病历接口按 sort_order 查询时，ORM 与数据库必须共同拥有该字段。"""

    column = MedicalDocument.__table__.columns.get("sort_order")

    assert column is not None
    assert column.nullable is False
    assert column.default is not None
    assert column.default.arg == 0


def test_sort_order_migration_follows_single_and_split_schema_contract(monkeypatch) -> None:
    """迁移必须跟随已有的单 schema/拆分 schema 部署合同。"""

    migration = _load_migration()

    assert migration.revision == "20260811_000031"
    assert migration.down_revision == "20260811_000030"

    monkeypatch.setenv("DB_SCHEMA_MODE", "single")
    assert migration._target_schema() == "public"

    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    assert migration._target_schema() == "cdm"


def test_records_api_delivers_documents_with_sort_order_contract(monkeypatch) -> None:
    """公开病历接口必须交付文书，不能把缺失排序字段降级成空列表。"""

    monkeypatch.setattr("app.routers.records.get_supabase", lambda: _SchemaAwareClient())
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@medqc.com", "password": "admin888"},
    )
    assert login.status_code == 200
    token = (login.json().get("data") or login.json())["access_token"]

    response = client.get(
        "/api/v1/records?page=1&page_size=5",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert items[0]["documents"][0]["id"] == "document-sort-contract"
