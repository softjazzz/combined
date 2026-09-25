"""病案首页三坐标身份合同 — 独立反例测试（不连业务库/验证库）。

合同（主协调 Agent 给定）：

- ``get_frontpage_sheet(patient_id, visit_id, institute_id=None)`` 在 ``cdm.mr`` 上只认唯一三坐标
  ``institute_id + patient_id + visit_id``；
- 首页缺失 → 404；省略机构而 patient+visit 命中多机构/多行 → 409，绝不 ``.first()`` 猜首个；
- 显式机构只返回该机构首页（缺失即 404，不回退到别家）；显式空机构 → 400；
- Diagnosis / MrSurgery / MrCost 与原生 ``cdm.mr_diagnosis`` / ``cdm.discharge_record_diagnosis``
  兜底一律钉在解析出的同一三坐标上，禁止跨机构同号混读；
- 原生兜底读取失败：包括病理在内的来源均按“取数不可用”收口（503）；
- API ``institute_id`` 查询参数可选，错误固定脱敏（不回显患者/就诊/机构标识、SQL 或连接细节）。

本文件证明什么、不证明什么：

- 证明：ORM 取数路径在 SQLite 附加的 ``cdm`` schema 上执行三坐标过滤，覆盖跨机构同号
  的显式隔离、省略机构 409、缺失 404 / 空机构 400；
- 独立 schema 反例还需验证同名 ``main`` 毒行不会被读取；本文件不替代真实 PostgreSQL 验收；
- 显式 ``cdm.`` 限定只在原生 SQL 兜底上被断言（语句文本 + 绑定参数，未在 SQLite 执行）。

不连业务库的做法：

- 原生兜底 SQL 含 Postgres 专属语法（``~`` / ``::int`` / ``regexp_replace``），SQLite 无法解析，
  因此兜底的参数化/机构限定只用窄口径录制式假 Session 断言（不做通用 query 链模拟）。

运行：``cd backend; python -m pytest tests/unit/test_medical_records_frontpage_sheet_identity.py``
（根 conftest 已把 DATABASE_URL 指向拒连地址；``--noconftest`` 时本模块自行隔离。）
"""

from __future__ import annotations

import inspect
import os
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect
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
from app.routers import medical_records_export as export_router  # noqa: E402
from app.routers.medical_records_common import raise_medical_records_http_error  # noqa: E402
from app.core.security import get_current_user  # noqa: E402
from app.services.medical_records import export_service  # noqa: E402
from app.services.medical_records.errors import MedicalRecordsNotFoundError  # noqa: E402


INST_A = "INST-A"
INST_B = "INST-B"

PATIENT_MULTI = "PAT-MULTI-9"
VISIT_MULTI = "VISIT-MULTI-9"
PATIENT_SINGLE = "PAT-SINGLE-1"
VISIT_SINGLE = "VISIT-SINGLE-1"
UNKNOWN = "COORD-UNKNOWN-0"

_SHEET_TABLES = (
    MedicalRecordFrontpage.__table__,
    Diagnosis.__table__,
    MrSurgery.__table__,
    MrCost.__table__,
)


def _forbidden_session_factory(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("单元测试不得使用默认数据库会话工厂（必须显式指向内存库）")


@pytest.fixture(autouse=True)
def _forbid_default_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """把默认 engine/会话工厂置为不可用：任何真实库访问都会立刻失败而不是静默连库。"""

    monkeypatch.setattr(connection_module, "engine", None, raising=False)
    monkeypatch.setattr(export_service, "_session_factory", _forbidden_session_factory, raising=False)


def _bundle(
    institute: str,
    patient_id: str,
    visit_id: str,
    marker: str,
    cost: str,
    *,
    frontpage: bool = True,
) -> list[Any]:
    """一家机构在一个 patient+visit 上的首页四件套；号码两院相同，复现跨机构同号。

    ``frontpage=False`` 用于构造“只有关联表杂散行、没有首页行”的串机构反例。
    """

    rows: list[Any] = [
        Diagnosis(
            institute_id=institute,
            patient_id=patient_id,
            visit_id=visit_id,
            diagnosis_id="D1",
            diagnosis_type="出院诊断-主要诊断",
            diagnosis_no="1",
            diagnosis_name=f"{marker}诊断",
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
    if frontpage:
        rows.insert(
            0,
            MedicalRecordFrontpage(
                institute_id=institute,
                patient_id=patient_id,
                visit_id=visit_id,
                institute_county_desc=marker,
                name="测试患者",
            ),
        )
    return rows


def _seed_rows() -> list[Any]:
    """跨机构同号反例数据。

    - ``PATIENT_MULTI``/``VISIT_MULTI``：甲乙两院都有首页/诊断/手术/费用，且诊断号、手术号
      两院完全相同；按号码猜首或跨机构混读会立刻暴露。
    - ``PATIENT_SINGLE``/``VISIT_SINGLE``：首页只在 ``INST_A``，但 ``INST_B`` 有同 patient+visit 的
      杂散诊断/手术/费用；按解析三坐标读取时必须整体排除。
    """

    return (
        _bundle(INST_A, PATIENT_MULTI, VISIT_MULTI, "甲院", "100.00")
        + _bundle(INST_B, PATIENT_MULTI, VISIT_MULTI, "乙院", "999.00")
        + _bundle(INST_A, PATIENT_SINGLE, VISIT_SINGLE, "单院", "10.00")
        + _bundle(INST_B, PATIENT_SINGLE, VISIT_SINGLE, "串机构", "20.00", frontpage=False)
    )


@pytest.fixture
def sheet_db(monkeypatch: pytest.MonkeyPatch) -> Any:
    """把实现的默认会话钳到内存 SQLite（真实执行 SQL），并返回已注入的 engine。

    四张 ORM 表建在附加的 ``cdm`` 库，与服务端取数合同一致；另建空的 cdm.mr_diagnosis
    供病理兜底查询。Postgres 专属的诊断排序语法由录制式 Session 检查参数合同。
    任一实际兜底来源读取失败必须返回 503，不能把未知事实当空值。
    """

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
    cdm_engine = engine.execution_options(schema_translate_map={None: "cdm"})
    Base.metadata.create_all(cdm_engine, tables=list(_SHEET_TABLES))
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE cdm.mr_diagnosis ("
            "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
            "is_deleted TEXT, diagnosis_type TEXT, diagnosis_code TEXT, diagnosis_id TEXT)"
        )
    session_local = sessionmaker(bind=cdm_engine)
    with session_local() as session:
        session.add_all(_seed_rows())
        session.commit()

    for target in (export_service, connection_module):
        monkeypatch.setattr(target, "engine", engine, raising=False)
        monkeypatch.setattr(target, "SessionLocal", session_local, raising=False)
    monkeypatch.setattr(export_service, "_session_factory", session_local, raising=False)
    return engine


@pytest.fixture
def api_client() -> Any:
    """只挂载病案导出路由的最小应用，避免拉起整站依赖。"""

    app = FastAPI()
    app.include_router(export_router.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test-admin", "email": "test-admin@example.invalid", "roles": ["admin"]
    }
    with TestClient(app) as client:
        yield client


def _sheet(patient_id: str, visit_id: str, institute_id: str | None = None) -> dict[str, Any]:
    return export_router.get_frontpage_sheet(
        patient_id=patient_id,
        visit_id=visit_id,
        institute_id=institute_id,
    )


def _http_error(exc: BaseException) -> HTTPException:
    """按路由真实使用的映射函数取 HTTP 错误（与线上错误映射同一路径）。"""

    with pytest.raises(HTTPException) as captured:
        raise_medical_records_http_error(exc)
    return captured.value


# ---------------------------------------------------------------------------
# 签名合同
# ---------------------------------------------------------------------------


def test_service_signature_exposes_optional_institute_id() -> None:
    params = inspect.signature(export_router.get_frontpage_sheet).parameters

    assert "patient_id" in params
    assert "visit_id" in params
    assert "institute_id" in params, "缺少 institute_id 参数，无法显式指定机构"
    assert params["institute_id"].default is None, "institute_id 必须是可选参数"


# ---------------------------------------------------------------------------
# 跨机构同号：显式机构不得混读，省略机构不得猜首
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("institute", "own", "other", "total_cost", "diagnosis_names"),
    [
        (INST_A, "甲院", "乙院", "100.00", ["甲院诊断"]),
        (INST_B, "乙院", "甲院", "999.00", ["乙院诊断"]),
    ],
)
def test_explicit_institute_never_mixes_other_institute_rows(
    sheet_db: Any,
    institute: str,
    own: str,
    other: str,
    total_cost: str,
    diagnosis_names: list[str],
) -> None:
    sheet = _sheet(PATIENT_MULTI, VISIT_MULTI, institute)

    assert sheet["basic"]["institute_id"] == institute

    actual_diagnoses = [item["diagnosis_name"] for item in sheet["diagnoses"]]
    assert actual_diagnoses == diagnosis_names, f"诊断跨机构混读：{actual_diagnoses}"
    assert all(other not in name for name in actual_diagnoses)

    surgery_names = [item["surgery_name"] for item in sheet["surgeries"]]
    assert surgery_names == [f"{own}手术"], f"手术跨机构混读：{surgery_names}"

    assert sheet["cost"] is not None
    assert sheet["cost"]["institute_id"] == institute
    assert sheet["cost"]["total_cost"] == total_cost, "费用取到了其他机构记录"


def test_omitted_institute_single_candidate_scopes_associations(sheet_db: Any) -> None:
    """首页唯一候选时按解析出的三坐标读关联表，不读其他机构的同号杂散行。"""

    sheet = _sheet(PATIENT_SINGLE, VISIT_SINGLE, None)

    assert sheet["basic"]["institute_id"] == INST_A
    assert [item["diagnosis_name"] for item in sheet["diagnoses"]] == ["单院诊断"]
    assert [item["surgery_name"] for item in sheet["surgeries"]] == ["单院手术"]
    assert sheet["cost"] is not None
    assert sheet["cost"]["total_cost"] == "10.00"


def test_omitted_institute_with_multiple_institutes_is_409(sheet_db: Any) -> None:
    """同 patient+visit 命中多机构：必须 409，绝不 .first() 猜首个。"""

    with pytest.raises(Exception) as captured:
        _sheet(PATIENT_MULTI, VISIT_MULTI, None)

    assert _http_error(captured.value).status_code == 409, (
        "省略机构且多机构命中时必须 409（身份不唯一），不得静默返回某个机构首页"
    )


# ---------------------------------------------------------------------------
# 404 / 400
# ---------------------------------------------------------------------------


def test_missing_frontpage_is_404(sheet_db: Any) -> None:
    with pytest.raises(MedicalRecordsNotFoundError) as captured:
        _sheet(UNKNOWN, UNKNOWN, None)

    assert _http_error(captured.value).status_code == 404


def test_explicit_missing_institute_is_404_without_cross_institute_fallback(sheet_db: Any) -> None:
    """首页只在 INST_A/INST_B，显式请求别家必须 404，不能回退取其他机构首页。"""

    with pytest.raises(MedicalRecordsNotFoundError) as captured:
        _sheet(PATIENT_MULTI, VISIT_MULTI, "INST-C")

    assert _http_error(captured.value).status_code == 404


def test_explicit_blank_institute_is_400(sheet_db: Any) -> None:
    with pytest.raises(Exception) as captured:
        _sheet(PATIENT_MULTI, VISIT_MULTI, "   ")

    assert _http_error(captured.value).status_code == 400


# ---------------------------------------------------------------------------
# SQL / 参数安全：注入 payload 必须按绑定参数处理
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "calls",
    [
        pytest.param(lambda: _sheet(f"{PATIENT_MULTI}' OR '1'='1", VISIT_MULTI, None), id="patient_id"),
        pytest.param(lambda: _sheet(PATIENT_MULTI, f"{VISIT_MULTI}' OR '1'='1", None), id="visit_id"),
        pytest.param(lambda: _sheet(PATIENT_MULTI, VISIT_MULTI, f"{INST_A}' OR '1'='1"), id="institute_id"),
    ],
)
def test_injection_payload_is_bound_not_interpolated(sheet_db: Any, calls: Any) -> None:
    with pytest.raises(Exception) as captured:
        calls()

    assert _http_error(captured.value).status_code == 404, (
        "注入 payload 若被字符串拼接进 SQL，就会命中最先匹配的真实行并返回数据"
    )
    # 表未被破坏，正常三坐标仍可读（进一步证明 payload 没有被当 SQL 执行）。
    assert _sheet(PATIENT_MULTI, VISIT_MULTI, INST_A)["basic"]["institute_id"] == INST_A


# ---------------------------------------------------------------------------
# API：institute_id 可选，409/404 脱敏
# ---------------------------------------------------------------------------


def test_api_institute_id_is_optional_and_conflict_is_desensitized(
    api_client: Any, sheet_db: Any
) -> None:
    single = api_client.get(f"/frontpage-sheet/{PATIENT_SINGLE}/{VISIT_SINGLE}")
    assert single.status_code == 200
    assert single.json()["basic"]["institute_id"] == INST_A

    explicit = api_client.get(
        f"/frontpage-sheet/{PATIENT_MULTI}/{VISIT_MULTI}?institute_id={INST_B}"
    )
    assert explicit.status_code == 200
    assert explicit.json()["basic"]["institute_id"] == INST_B
    assert explicit.json()["cost"]["total_cost"] == "999.00"

    conflict = api_client.get(f"/frontpage-sheet/{PATIENT_MULTI}/{VISIT_MULTI}")
    assert conflict.status_code == 409
    for token in (PATIENT_MULTI, VISIT_MULTI, INST_A, INST_B):
        assert token not in conflict.text, f"错误信息泄露标识：{token}"

    missing = api_client.get(f"/frontpage-sheet/{UNKNOWN}/{UNKNOWN}")
    assert missing.status_code == 404
    assert UNKNOWN not in missing.text


def test_api_rejects_qc_staff_until_institute_authorization_exists(
    api_client: Any, sheet_db: Any
) -> None:
    api_client.app.dependency_overrides[get_current_user] = lambda: {
        "id": "test-staff", "email": "test-staff@example.invalid", "roles": ["qc_staff"]
    }

    response = api_client.get(
        f"/frontpage-sheet/{PATIENT_MULTI}/{VISIT_MULTI}?institute_id={INST_A}"
    )
    assert response.status_code == 403
    assert all(token not in response.text for token in (PATIENT_MULTI, VISIT_MULTI, INST_A))


# ---------------------------------------------------------------------------
# 原生兜底：三坐标参数化
# ---------------------------------------------------------------------------


class _Rows:
    """最小结果对象：只支持被测代码实际调用的读取链。"""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def filter_by(self, **_kwargs: Any) -> "_Rows":
        return self

    def order_by(self, *_args: Any, **_kwargs: Any) -> "_Rows":
        return self

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def mappings(self) -> "_Rows":
        return self


class _RecordingSession:
    """窄口径假 Session：只服务「原生兜底是否按三坐标参数化」这一个反例。

    首页行固定返回、关联表固定返回空，因此必然走到原生兜底分支；这里只记录
    ``execute(statement, params)``，不模拟任何身份判定（身份由 SQLite 用例覆盖）。
    """

    def __init__(
        self,
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        execute_error: Exception | None = None,
        fail_on_execute_number: int | None = None,
    ) -> None:
        self.native_statements: list[tuple[str, dict[str, Any]]] = []
        self._execute_error = execute_error
        self._fail_on_execute_number = fail_on_execute_number
        self._frontpage = SimpleNamespace(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            institute_county_desc="甲院",
        )

    def __enter__(self) -> "_RecordingSession":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    def query(self, model: Any = None, *_args: Any, **_kwargs: Any) -> _Rows:
        mapped_class = sa_inspect(model).mapper.class_ if model is not None else None
        return _Rows([self._frontpage] if mapped_class is MedicalRecordFrontpage else [])

    def execute(self, statement: Any, params: Any = None) -> _Rows:
        self.native_statements.append((str(statement), dict(params or {})))
        if self._execute_error is not None and (
            self._fail_on_execute_number is None
            or len(self.native_statements) == self._fail_on_execute_number
        ):
            raise self._execute_error
        return _Rows([])


def _use_recording_session(monkeypatch: pytest.MonkeyPatch, session: _RecordingSession) -> None:
    monkeypatch.setattr(export_service, "_session_factory", lambda: session, raising=False)
    monkeypatch.setattr(export_service, "engine", None, raising=False)
    monkeypatch.setattr(connection_module, "engine", None, raising=False)


@pytest.mark.parametrize("institute", [INST_A, INST_B])
def test_native_fallback_binds_three_coordinates(
    monkeypatch: pytest.MonkeyPatch, institute: str
) -> None:
    """每条原生兜底语句都必须显式限定 ``cdm.``、按三坐标绑定参数，且不拼接字面量。"""

    session = _RecordingSession(
        institute_id=institute, patient_id="P-FALLBACK", visit_id="V-FALLBACK"
    )
    _use_recording_session(monkeypatch, session)

    _sheet("P-FALLBACK", "V-FALLBACK", institute)

    assert session.native_statements, "兜底来源可读时必须执行原生兜底，否则该用例无覆盖"
    expected = {
        "institute_id": institute,
        "patient_id": "P-FALLBACK",
        "visit_id": "V-FALLBACK",
    }
    other = INST_B if institute == INST_A else INST_A
    for sql, params in session.native_statements:
        lowered = sql.lower()
        assert "cdm." in lowered, f"原生兜底 SQL 未显式限定 cdm schema：{sql}"
        assert "institute_id = :institute_id" in lowered, f"兜底 SQL 未按机构限定：{sql}"
        assert "patient_id = :patient_id" in lowered, f"兜底 SQL 未按患者绑定：{sql}"
        assert "visit_id = :visit_id" in lowered, f"兜底 SQL 未按就诊绑定：{sql}"
        assert params == expected, f"兜底 SQL 未绑定完整三坐标：{params}"
        assert institute not in sql and other not in sql, f"兜底 SQL 拼接了机构字面量：{sql}"


def test_native_fallback_unavailable_is_503_and_desensitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """诊断事实来源不可读时必须 503（取数不可用），且不回显连接细节。"""

    session = _RecordingSession(
        institute_id=INST_A,
        patient_id="P-FALLBACK",
        visit_id="V-FALLBACK",
        execute_error=SQLAlchemyError(
            'connection to server at "10.0.0.9", port 5432 failed: password authentication failed'
        ),
    )
    _use_recording_session(monkeypatch, session)

    with pytest.raises(Exception) as captured:
        _sheet("P-FALLBACK", "V-FALLBACK", INST_A)

    error = _http_error(captured.value)
    assert error.status_code == 503
    detail = str(error.detail)
    assert "10.0.0.9" not in detail
    assert "5432" not in detail
    assert "SELECT" not in detail.upper()


def test_frontpage_orm_source_unavailable_is_503_and_desensitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """首页首个 ORM 查询断库时不返回 500 或泄漏底层连接详情。"""

    class FailingSession:
        def __enter__(self) -> "FailingSession":
            return self

        def __exit__(self, *_args: Any) -> bool:
            return False

        def query(self, _model: Any) -> Any:
            raise SQLAlchemyError("connection to 10.0.0.9 failed for PAT-SECRET")

    monkeypatch.setattr(export_service, "_session_factory", FailingSession, raising=False)

    with pytest.raises(Exception) as captured:
        _sheet("PAT-SECRET", "VISIT-SECRET", INST_A)

    error = _http_error(captured.value)
    assert error.status_code == 503
    assert "10.0.0.9" not in str(error.detail)
    assert "PAT-SECRET" not in str(error.detail)


def test_pathology_fallback_unavailable_is_not_mistaken_for_empty_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """诊断兜底成功为空后，病理兜底报错也必须停止读取。"""

    session = _RecordingSession(
        institute_id=INST_A,
        patient_id="P-FALLBACK",
        visit_id="V-FALLBACK",
        execute_error=SQLAlchemyError("pathology source unavailable"),
        fail_on_execute_number=3,
    )
    _use_recording_session(monkeypatch, session)

    with pytest.raises(Exception) as captured:
        _sheet("P-FALLBACK", "V-FALLBACK", INST_A)

    assert len(session.native_statements) == 3
    error = _http_error(captured.value)
    assert error.status_code == 503
    assert "pathology source unavailable" not in str(error.detail)
