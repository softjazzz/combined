"""病案首页四表的权威 schema 选择 — 独立反例测试（不连业务库/验证库）。

合同（主协调 Agent 给定）：

- ``get_frontpage_sheet`` 的四张 ORM 表（``mr`` / ``diagnosis`` / ``mr_surgery`` / ``mr_cost``）
  必须始终显式读 ``cdm``，不得经连接 search_path 命中 public 同名影子表；只有这一条主链。
- 三坐标、原生兜底与 400/404/409/503 语义不变；显式空机构仍 400。

本文件证明什么、不证明什么：

- 证明：真实执行（内存 SQLite：``main`` 放同三坐标毒行、attached ``cdm`` 放权威行）下，
  首页四表的 ORM 取数落在 ``cdm``，public(main) 毒行完全不出现；
- 证明：同一库上不加 ``cdm`` 限定的对照读法会读到 main 毒行，因此上面的反例是决定性的，
  不是空断言；只存在于 public 的三坐标必须 404，不能回退；
- 证明：四表取数源在 SQLite 与 PostgreSQL 两种方言下编译出的 SQL 都显式写 ``cdm.<table>``，
  且取数源不是裸 ORM 实体（无方言回退分支）；
- 不证明：业务库上 cdm/public 的实际部署形态或真实数据（本文件拒连业务库）。

运行：``cd backend; python -m pytest tests/unit/test_medical_records_frontpage_sheet_schema.py``
（根 conftest 已把 DATABASE_URL 指向拒连地址；本模块另行隔离默认 engine/会话工厂。）
"""

from __future__ import annotations

import inspect
import json
import os
import re
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import MetaData, create_engine, insert, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 先隔离 DATABASE_URL 再导入 app，避免 backend/.env 把业务库注入单元测试。
_REFUSE_DSN = "postgresql://invalid:invalid@127.0.0.1:1/nonexistent"
if not os.environ.get("DATABASE_URL", "").strip():
    os.environ["DATABASE_URL"] = _REFUSE_DSN

from app.database import connection as connection_module  # noqa: E402
from app.database.connection import Base  # noqa: E402
from app.database.models.cdm import (  # noqa: E402
    Diagnosis,
    MedicalRecordFrontpage,
    MrCost,
    MrSurgery,
)
from app.routers.medical_records_common import raise_medical_records_http_error  # noqa: E402
from app.services.medical_records import export_service  # noqa: E402


INST_A = "INST-A"
INST_B = "INST-B"
INST_SHADOW_ONLY = "INST-C"

# 权威行（attached cdm）与毒行（main = 等价 public 影子）共用同一三坐标。
PATIENT = "PAT-SCHEMA-1"
VISIT = "VISIT-SCHEMA-1"

PATIENT_MULTI = "PAT-SCHEMA-MULTI"
VISIT_MULTI = "VISIT-SCHEMA-MULTI"

# 只存在于 main 毒行的三坐标：显式 cdm 读取必须 404，禁止回退 public。
PATIENT_SHADOW_ONLY = "PAT-SHADOW-ONLY"
VISIT_SHADOW_ONLY = "VISIT-SHADOW-ONLY"

UNKNOWN = "COORD-SCHEMA-UNKNOWN"

CDM_MARKER = "cdm权威院"
SHADOW_MARKER = "public影子院"

_SHEET_MODELS = (MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost)


def _forbidden_session_factory(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("单元测试不得使用默认数据库会话工厂（必须显式指向内存库）")


@pytest.fixture(autouse=True)
def _forbid_default_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """把默认 engine/会话工厂置为不可用：任何真实库访问都会立刻失败而不是静默连库。"""

    monkeypatch.setattr(connection_module, "engine", None, raising=False)
    monkeypatch.setattr(export_service, "engine", None, raising=False)
    monkeypatch.setattr(export_service, "_session_factory", _forbidden_session_factory, raising=False)


def _orm_rows(
    institute: str,
    patient_id: str,
    visit_id: str,
    marker: str,
    cost: str,
    diagnosis_name: str,
) -> list[Any]:
    """一家机构在一个三坐标上的首页四件套（首页/诊断/手术/费用）。"""

    return [
        MedicalRecordFrontpage(
            institute_id=institute,
            patient_id=patient_id,
            visit_id=visit_id,
            institute_county_desc=marker,
            name="测试患者",
        ),
        Diagnosis(
            institute_id=institute,
            patient_id=patient_id,
            visit_id=visit_id,
            diagnosis_id="D1",
            diagnosis_type="出院诊断-主要诊断",
            diagnosis_no="1",
            diagnosis_name=diagnosis_name,
            diagnosis_code="I10",
        ),
        MrSurgery(
            institute_id=institute,
            patient_id=patient_id,
            visit_id=visit_id,
            surgery_id="S1",
            surgery_name=f"{marker}手术",
            surgery_code="47.0",
        ),
        MrCost(
            institute_id=institute,
            patient_id=patient_id,
            visit_id=visit_id,
            total_cost=cost,
        ),
    ]


def _row_values(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


@pytest.fixture
def sheet_schema_db(monkeypatch: pytest.MonkeyPatch) -> Any:
    """构造 ``cdm``（权威）与 ``main``（public 影子/毒行）同名四表的真实 SQLite 库。

    边界：SQLite 未限定表名按 ``temp → main → 已 attach 库`` 解析，与生产 search_path
    ``public`` 打头同名先命中一致，因此本夹具能真实复现“毒行先被读到”的反例；这里额外建
    空的 ``cdm.mr_diagnosis`` / ``cdm.discharge_record_diagnosis`` 供原生兜底查询。
    """

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")

    cdm_meta = MetaData()
    cdm_tables = {
        model.__table__.name: model.__table__.to_metadata(cdm_meta, schema=export_service.CDM_SCHEMA)
        for model in _SHEET_MODELS
    }
    cdm_meta.create_all(engine)
    Base.metadata.create_all(engine, tables=[model.__table__ for model in _SHEET_MODELS])
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE cdm.mr_diagnosis ("
            "institute_id TEXT, patient_id TEXT, visit_id TEXT, is_deleted TEXT, "
            "diagnosis_type TEXT, diagnosis_code TEXT, diagnosis_id TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE cdm.discharge_record_diagnosis ("
            "institute_id TEXT, patient_id TEXT, visit_id TEXT, is_deleted TEXT, "
            "diagnosis_type TEXT, diagnosis_main TEXT, diagnosis_no TEXT, diagnosis_id TEXT)"
        )

    cdm_rows = (
        _orm_rows(INST_A, PATIENT, VISIT, CDM_MARKER, "111.00", "cdm 诊断")
        + _orm_rows(INST_A, PATIENT_MULTI, VISIT_MULTI, CDM_MARKER, "211.00", "cdm 多院诊断甲")
        + _orm_rows(INST_B, PATIENT_MULTI, VISIT_MULTI, CDM_MARKER, "222.00", "cdm 多院诊断乙")
    )
    shadow_rows = (
        _orm_rows(INST_A, PATIENT, VISIT, SHADOW_MARKER, "999.00", "public 影子诊断")
        + _orm_rows(INST_SHADOW_ONLY, PATIENT_MULTI, VISIT_MULTI, SHADOW_MARKER, "888.00", "public 多院诊断")
        + _orm_rows(INST_A, PATIENT_SHADOW_ONLY, VISIT_SHADOW_ONLY, SHADOW_MARKER, "777.00", "public 独有诊断")
    )

    with engine.begin() as connection:
        for row in cdm_rows:
            connection.execute(insert(cdm_tables[row.__table__.name]).values(**_row_values(row)))

    session_local = sessionmaker(bind=engine)
    with session_local() as session:
        session.add_all(shadow_rows)
        session.commit()

    monkeypatch.setattr(export_service, "engine", engine, raising=False)
    monkeypatch.setattr(export_service, "_session_factory", session_local, raising=False)
    return SimpleNamespace(engine=engine, session_local=session_local)


def _sheet(patient_id: str, visit_id: str, institute_id: str | None = None) -> dict[str, Any]:
    return export_service.get_frontpage_sheet(
        patient_id, visit_id, institute_id=institute_id
    )


def _http_error(exc: BaseException) -> HTTPException:
    """按路由真实使用的映射函数取 HTTP 错误（与线上错误映射同一路径）。"""

    with pytest.raises(HTTPException) as captured:
        raise_medical_records_http_error(exc)
    return captured.value


# ---------------------------------------------------------------------------
# 真实执行：四表读 cdm，public 毒行不出现
# ---------------------------------------------------------------------------


def test_sheet_reads_cdm_rows_and_ignores_public_shadow(sheet_schema_db: Any) -> None:
    sheet = _sheet(PATIENT, VISIT, INST_A)

    assert sheet["basic"]["institute_county_desc"] == CDM_MARKER
    assert sheet["basic"]["institute_id"] == INST_A
    assert [item["diagnosis_name"] for item in sheet["diagnoses"]] == ["cdm 诊断"]
    assert [item["surgery_name"] for item in sheet["surgeries"]] == [f"{CDM_MARKER}手术"]
    assert sheet["cost"] is not None
    assert sheet["cost"]["total_cost"] == "111.00", "费用取到了 public 毒行"

    rendered = json.dumps(sheet, ensure_ascii=False)
    assert SHADOW_MARKER not in rendered
    assert "public 影子诊断" not in rendered
    assert "999.00" not in rendered


def test_control_without_cdm_scope_reads_public_shadow_on_same_db(sheet_schema_db: Any) -> None:
    """对照反例：不加 ``cdm`` 限定时，同一三坐标读到 main(public) 毒行。

    证明上面的用例是决定性的：毒行确实能被 search_path 式解析命中，
    只有显式 ``cdm`` 限定才能把它排除。
    """

    with sheet_schema_db.session_local() as session:
        rows = session.query(MedicalRecordFrontpage).filter_by(
            institute_id=INST_A, patient_id=PATIENT, visit_id=VISIT
        ).all()

    assert len(rows) == 1
    assert rows[0].institute_county_desc == SHADOW_MARKER, (
        "未限定 schema 时本应命中 main 毒行；若此处是 cdm 行，说明反例数据构造有误"
    )


# ---------------------------------------------------------------------------
# 语义保持：400 / 404 / 409 不回退 public
# ---------------------------------------------------------------------------


def test_shadow_only_coordinates_are_404_without_public_fallback(sheet_schema_db: Any) -> None:
    with pytest.raises(Exception) as captured:
        _sheet(PATIENT_SHADOW_ONLY, VISIT_SHADOW_ONLY, INST_A)

    assert _http_error(captured.value).status_code == 404, (
        "只存在于 public 毒行的三坐标不得被读取，必须 404"
    )


def test_explicit_institute_missing_in_cdm_is_404_even_if_public_has_it(
    sheet_schema_db: Any,
) -> None:
    with pytest.raises(Exception) as captured:
        _sheet(PATIENT_MULTI, VISIT_MULTI, INST_SHADOW_ONLY)

    assert _http_error(captured.value).status_code == 404


def test_omitted_institute_with_multiple_cdm_institutes_is_409(sheet_schema_db: Any) -> None:
    with pytest.raises(Exception) as captured:
        _sheet(PATIENT_MULTI, VISIT_MULTI, None)

    error = _http_error(captured.value)
    assert error.status_code == 409
    for token in (PATIENT_MULTI, VISIT_MULTI, INST_A, INST_B, INST_SHADOW_ONLY):
        assert token not in str(error.detail), f"错误信息泄露标识：{token}"


def test_explicit_blank_institute_is_400(sheet_schema_db: Any) -> None:
    with pytest.raises(Exception) as captured:
        _sheet(PATIENT, VISIT, "   ")

    assert _http_error(captured.value).status_code == 400


def test_missing_everywhere_is_404(sheet_schema_db: Any) -> None:
    with pytest.raises(Exception) as captured:
        _sheet(UNKNOWN, UNKNOWN, None)

    assert _http_error(captured.value).status_code == 404


# ---------------------------------------------------------------------------
# 单一主链：取数源始终 cdm，无方言回退
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", _SHEET_MODELS, ids=lambda model: model.__tablename__)
@pytest.mark.parametrize(
    "dialect",
    [sqlite.dialect(), postgresql.dialect()],
    ids=["sqlite", "postgresql"],
)
def test_sheet_source_sql_pins_cdm_for_every_table(model: Any, dialect: Any) -> None:
    source = export_service._frontpage_source(model)

    assert source is not model, "取数源不得回落裸 ORM 实体（否则 search_path 仍可命中 public）"

    compiled = str(select(source).compile(dialect=dialect))
    table_name = model.__tablename__
    assert f"cdm.{table_name}" in compiled, compiled
    assert not re.search(rf"FROM\s+{table_name}\b", compiled), (
        f"编译出的 SQL 仍含未限定表名：{compiled}"
    )


def test_sheet_source_is_stable_across_calls() -> None:
    """同一表只解析一次 cdm 源，避免每次取数重建别名造成读法漂移。"""

    assert export_service._frontpage_source(Diagnosis) is export_service._frontpage_source(Diagnosis)
    assert export_service.CDM_SCHEMA == "cdm"


# ---------------------------------------------------------------------------
# 失败关闭：取数不可用 503，不回显连接细节；默认库拒连
# ---------------------------------------------------------------------------


def test_cdm_source_unavailable_is_503_and_desensitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingSession:
        def __enter__(self) -> "FailingSession":
            return self

        def __exit__(self, *_exc: Any) -> bool:
            return False

        def query(self, _source: Any, *_args: Any, **_kwargs: Any) -> Any:
            raise SQLAlchemyError('connection to server at "10.0.0.9", port 5432 failed for PAT-SECRET')

    monkeypatch.setattr(export_service, "_session_factory", FailingSession, raising=False)

    with pytest.raises(Exception) as captured:
        _sheet("PAT-SECRET", "VISIT-SECRET", INST_A)

    error = _http_error(captured.value)
    assert error.status_code == 503
    detail = str(error.detail)
    assert "10.0.0.9" not in detail
    assert "5432" not in detail
    assert "PAT-SECRET" not in detail
    assert "SELECT" not in detail.upper()


def test_default_session_factory_is_refused() -> None:
    """未显式注入内存库时，默认会话工厂必须立刻失败，而不是静默连业务库。"""

    with pytest.raises(AssertionError):
        _sheet(PATIENT, VISIT, INST_A)


def test_service_signature_unchanged() -> None:
    params = inspect.signature(export_service.get_frontpage_sheet).parameters

    assert list(params) == ["patient_id", "visit_id", "institute_id", "session_factory"]
    assert params["institute_id"].default is None
    assert params["session_factory"].default is None
