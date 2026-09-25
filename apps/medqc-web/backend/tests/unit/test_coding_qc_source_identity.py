"""编码质控取数身份（三坐标）聚焦测试。

覆盖 ``app/routers/qc.py`` 的编码质控取数分支：

- 三坐标唯一权威是 ``cdm.mr``：同三坐标重复拒绝、缺机构多候选拒绝、空机构失败
- 同一 visit+patient 跨机构的不同首页/诊断/手术/费用不得混读
- 缺机构时只允许唯一候选推断；歧义 409、缺失 404，两者都不写队列
- 取数、队列状态、结果写入、模型观测共用同一个服务端解析身份，请求体坐标不能改身份
- 队列 start/finish 携带 source_key='coding_qc' + 三坐标（现代身份 CAS）
- 数据库读取/落库异常脱敏，且不返回 None 让上层按“通过”收尾
- 无可评估编码数据不得报告“通过”
- 手工 frontpage 模式保持旧语义：无已验证身份、不推进队列
- 解析与全部编码取数显式限定 ``cdm`` schema：``public`` 同名影子行不得被认领或混读

不连接任何真实数据库：使用内存 SQLite，并 ``ATTACH`` 出 ``public``/``cdm`` 两个 schema
（``public`` 先挂载，复现 ``DB_SEARCH_PATH`` 允许 public 排在 cdm 前的同名表布局），
再显式替换取数入口的 engine。

运行方式（不加载根 conftest，避免连库）::

    DATABASE_URL=postgresql://invalid:invalid@127.0.0.1:1/nonexistent \
        python -m pytest tests/unit/test_coding_qc_source_identity.py --noconftest
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import pytest
from fastapi import HTTPException
from sqlalchemy import MetaData, create_engine, event, text
from starlette.requests import Request

import app.database.connection as connection
import app.routers.qc as qc_module
from app.database.models.cdm import (
    Diagnosis,
    MedicalRecordFrontpage,
    MrCost,
    MrSurgery,
)
from app.services.coding_qc_service import CodingQCEngine
from app.services.llm_observability import (
    current_llm_observation_context,
    llm_observation_context,
)
from app.services.qc_persistence_service import VerifiedQCIdentity

VISIT = "V-1"
PATIENT = "P-1"
INSTITUTE_A = "INST-A"
INSTITUTE_B = "INST-B"


SCHEMA_CDM = "cdm"
SCHEMA_PUBLIC = "public"
# 先挂 public 再挂 cdm：SQLite 未限定表名按附加顺序解析，public 同名表优先命中，
# 与 ``DB_SEARCH_PATH`` 把 public 排在 cdm 之前的布局同构。
_ATTACH_ORDER = (SCHEMA_PUBLIC, SCHEMA_CDM)
_CODING_SOURCE_TABLES = (
    MedicalRecordFrontpage.__table__,
    Diagnosis.__table__,
    MrSurgery.__table__,
    MrCost.__table__,
)
# mr_diagnosis 无 ORM 模型，按 CDM 视图字段最小化建表，供兜底查询使用。
_MR_DIAGNOSIS_DDL = (
    "CREATE TABLE {schema}.mr_diagnosis ("
    "institute_id VARCHAR(100), patient_id VARCHAR(100), visit_id VARCHAR(100), "
    "diagnosis_id VARCHAR(100), diagnosis_code VARCHAR(100), "
    "diagnosis_name VARCHAR(100), diagnosis_type VARCHAR(100), "
    "diagnosis_no VARCHAR(100), diagnosis_main VARCHAR(100), "
    "admission_condition VARCHAR(100), is_deleted VARCHAR(10))"
)


def _attach_schemas(engine) -> None:
    """为连接附加独立的 public/cdm 内存库，复现同名表跨 schema 的真实布局。"""

    @event.listens_for(engine, "connect")
    def _attach(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            for schema_name in _ATTACH_ORDER:
                cursor.execute(f"ATTACH DATABASE ':memory:' AS {schema_name}")
        finally:
            cursor.close()


def _create_schema_tables(engine, schema_name: str) -> None:
    """在指定 attached schema 内按 ORM 字段建同名表（含 mr_diagnosis）。"""
    metadata = MetaData()
    for table in _CODING_SOURCE_TABLES:
        copied = table.to_metadata(metadata, schema=schema_name)
        # 索引不参与取数语义，且 SQLite 的 CREATE INDEX 不接受 schema 限定表名。
        copied.indexes.clear()
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(_MR_DIAGNOSIS_DDL.format(schema=schema_name)))


@pytest.fixture()
def cdm_db(monkeypatch):
    """内存 SQLite 伪 CDM（attached schema）；只替换取数入口使用的 engine。

    ``cdm`` 是唯一权威库；``public`` 建同名空表作为影子守卫：任何未限定 schema 的
    解析/取数都会命中 public 而读不到权威行（旧实现即在此发生身份/取数漂移）。
    """
    engine = create_engine("sqlite://")
    _attach_schemas(engine)
    _create_schema_tables(engine, SCHEMA_CDM)
    _create_schema_tables(engine, SCHEMA_PUBLIC)
    monkeypatch.setattr(connection, "engine", engine)
    return engine


def _insert(engine, table: str, rows: List[Dict[str, Any]]) -> None:
    """写入伪数据；未带 schema 前缀的表名默认落在权威库 ``cdm``。

    需要构造 ``public`` 影子行时必须显式写 ``public.<table>``。
    """
    if not rows:
        return
    target = table if "." in table else f"{SCHEMA_CDM}.{table}"
    columns = ", ".join(rows[0])
    placeholders = ", ".join(f":{name}" for name in rows[0])
    with engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO {target} ({columns}) VALUES ({placeholders})"),
            rows,
        )


def _mr_row(institute_id: str, sex: str = "男", age_year: str = "60岁") -> Dict[str, Any]:
    return {
        "institute_id": institute_id,
        "patient_id": PATIENT,
        "visit_id": VISIT,
        "sex": sex,
        "age_year": age_year,
    }


def _diag_row(
    institute_id: str,
    code: str,
    name: str,
    diagnosis_id: str,
) -> Dict[str, Any]:
    return {
        "institute_id": institute_id,
        "patient_id": PATIENT,
        "visit_id": VISIT,
        "diagnosis_id": diagnosis_id,
        "diagnosis_code": code,
        "diagnosis_name": name,
        "diagnosis_type": "出院主要诊断",
        "diagnosis_no": "1",
    }


def _cost_row(institute_id: str, fee: str) -> Dict[str, Any]:
    return {
        "institute_id": institute_id,
        "patient_id": PATIENT,
        "visit_id": VISIT,
        "pathological_diagnostic_fee": fee,
    }


def _seed_two_institutes(engine) -> None:
    """同一三坐标在两家机构各有不同首页、诊断、手术和费用。"""
    _insert(engine, "mr", [_mr_row(INSTITUTE_A, sex="男"), _mr_row(INSTITUTE_B, sex="女")])
    _insert(
        engine,
        "diagnosis",
        [
            _diag_row(INSTITUTE_A, "I10", "高血压", "D-A1"),
            _diag_row(INSTITUTE_B, "J18.9", "肺炎", "D-B1"),
        ],
    )
    _insert(
        engine,
        "mr_surgery",
        [
            {
                "institute_id": INSTITUTE_A,
                "patient_id": PATIENT,
                "visit_id": VISIT,
                "surgery_id": "S-A1",
                "surgery_code": "47.0",
                "surgery_name": "阑尾切除术",
                "main_surgery_sign": "1",
            },
            {
                "institute_id": INSTITUTE_B,
                "patient_id": PATIENT,
                "visit_id": VISIT,
                "surgery_id": "S-B1",
                "surgery_code": "51.23",
                "surgery_name": "腹腔镜胆囊切除术",
                "main_surgery_sign": "1",
            },
        ],
    )
    _insert(
        engine,
        "mr_cost",
        [_cost_row(INSTITUTE_A, "100"), _cost_row(INSTITUTE_B, "200")],
    )


def _mr_diagnosis_row(
    institute_id: str,
    code: str,
    name: str,
    diagnosis_id: str,
    is_deleted: str = "0",
) -> Dict[str, Any]:
    return {
        "institute_id": institute_id,
        "patient_id": PATIENT,
        "visit_id": VISIT,
        "diagnosis_id": diagnosis_id,
        "diagnosis_code": code,
        "diagnosis_name": name,
        "diagnosis_type": "出院主要诊断",
        "diagnosis_no": "1",
        "diagnosis_main": "是",
        "is_deleted": is_deleted,
    }


def _broken_engine(tmp_path):
    """指向不存在目录的 SQLite engine：连接时必然失败，但不接触任何真实 DSN。"""
    return create_engine(f"sqlite:///{tmp_path / 'missing-dir' / 'qc.db'}")


def _resolve(patient_id: Optional[str], visit_id: str, institute_id: Optional[str] = None):
    return qc_module._resolve_coding_qc_identity(patient_id, visit_id, institute_id)


def _load(patient_id: Optional[str], visit_id: str, institute_id: Optional[str] = None):
    """按生产调用链先定身份再取数；身份缺失时返回 None。"""
    identity = _resolve(patient_id, visit_id, institute_id)
    if identity is None:
        return None
    return qc_module._load_frontpage_from_pg(identity)


def _expected_record_key_hash(triple: Tuple[str, str, str]) -> Optional[str]:
    """用公开观测边界推导期望身份哈希，避免直接依赖私有实现。"""
    with llm_observation_context(
        business_scene="coding_qc",
        record_identity=triple,
        executor_key="coding_qc_engine",
    ):
        return current_llm_observation_context().record_key_hash


class TestCodingQcIdentityResolution:
    """cdm.mr 是唯一权威；其余来源表只供取数。"""

    def test_two_institutes_on_same_visit_are_ambiguous(self, cdm_db):
        _seed_two_institutes(cdm_db)

        with pytest.raises(qc_module.CodingQcIdentityAmbiguousError):
            _resolve(PATIENT, VISIT)

    def test_explicit_institute_pins_single_candidate(self, cdm_db):
        _seed_two_institutes(cdm_db)

        identity = _resolve(PATIENT, VISIT, INSTITUTE_B)

        assert identity == qc_module.CodingQcIdentity(INSTITUTE_B, PATIENT, VISIT)

    def test_missing_institute_with_single_candidate_is_inferred(self, cdm_db):
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A)])

        identity = _resolve(PATIENT, VISIT)

        assert identity == qc_module.CodingQcIdentity(INSTITUTE_A, PATIENT, VISIT)

    def test_duplicate_same_coordinates_are_rejected(self, cdm_db):
        """同三坐标重复行必须拒绝，不能默认取第一行。"""
        with cdm_db.begin() as conn:
            conn.execute(text("DROP TABLE cdm.mr"))
            conn.execute(
                text(
                    "CREATE TABLE cdm.mr (institute_id VARCHAR(100), patient_id VARCHAR(100), "
                    "visit_id VARCHAR(100), sex VARCHAR(10), age_year VARCHAR(20))"
                )
            )
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A), _mr_row(INSTITUTE_A)])

        with pytest.raises(qc_module.CodingQcIdentityAmbiguousError):
            _resolve(PATIENT, VISIT, INSTITUTE_A)

    def test_empty_institute_is_rejected(self, cdm_db):
        _insert(cdm_db, "mr", [{**_mr_row(INSTITUTE_A), "institute_id": ""}])

        with pytest.raises(qc_module.CodingQcIdentityAmbiguousError):
            _resolve(PATIENT, VISIT)

    def test_missing_patient_id_with_two_patients_is_ambiguous(self, cdm_db):
        _insert(
            cdm_db,
            "mr",
            [
                {**_mr_row(INSTITUTE_A), "patient_id": "P-1"},
                {**_mr_row(INSTITUTE_A), "patient_id": "P-2"},
            ],
        )

        with pytest.raises(qc_module.CodingQcIdentityAmbiguousError):
            _resolve("", VISIT, INSTITUTE_A)

    def test_unknown_visit_has_no_identity(self, cdm_db):
        _seed_two_institutes(cdm_db)

        assert _resolve(PATIENT, "V-UNKNOWN") is None

    def test_wrong_institute_has_no_identity(self, cdm_db):
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A)])

        assert _resolve(PATIENT, VISIT, "INST-Z") is None

    def test_non_mr_sources_do_not_grant_identity(self, cdm_db):
        """只有诊断/费用、没有 cdm.mr 行时不得推断身份（与落库合同一致）。"""
        _insert(cdm_db, "diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])
        _insert(cdm_db, "mr_cost", [_cost_row(INSTITUTE_A, "100")])

        assert _resolve(PATIENT, VISIT, INSTITUTE_A) is None

    def test_resolution_read_failure_is_sanitized(self, tmp_path, monkeypatch):
        monkeypatch.setattr(connection, "engine", _broken_engine(tmp_path))

        with pytest.raises(qc_module.CodingQcSourceUnavailableError) as excinfo:
            _resolve(PATIENT, VISIT, INSTITUTE_A)

        assert str(excinfo.value) == "编码质控数据读取失败"
        assert "unable to open" not in str(excinfo.value)


class TestLoadFrontpageIdentity:
    """_load_frontpage_from_pg 的三坐标读取语义。"""

    def test_explicit_institute_does_not_mix_other_institute(self, cdm_db):
        _seed_two_institutes(cdm_db)

        frontpage = _load(PATIENT, VISIT, INSTITUTE_A)

        assert frontpage is not None
        assert [d["code"] for d in frontpage["diagnoses"]] == ["I10"]
        assert [s["code"] for s in frontpage["surgeries"]] == ["47.0"]
        assert frontpage["fees"]["pathology_diagnostic_fee"] == "100"
        assert frontpage["sex"] == "男"

    def test_missing_institute_with_two_candidates_is_ambiguous(self, cdm_db):
        _seed_two_institutes(cdm_db)

        with pytest.raises(qc_module.CodingQcIdentityAmbiguousError):
            _load(PATIENT, VISIT)

    def test_missing_institute_with_single_candidate_is_inferred(self, cdm_db):
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A)])
        _insert(cdm_db, "diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])

        frontpage = _load(PATIENT, VISIT)

        assert frontpage is not None
        assert [d["code"] for d in frontpage["diagnoses"]] == ["I10"]

    def test_wrong_institute_returns_none(self, cdm_db):
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A)])
        _insert(cdm_db, "diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])

        assert _load(PATIENT, VISIT, "INST-Z") is None

    def test_unknown_visit_returns_none(self, cdm_db):
        _seed_two_institutes(cdm_db)

        assert _load(PATIENT, "V-UNKNOWN") is None

    def test_patient_mismatch_returns_none(self, cdm_db):
        _insert(cdm_db, "diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])

        assert _load("P-OTHER", VISIT, INSTITUTE_A) is None

    def test_diagnosis_fallback_uses_same_coordinates(self, cdm_db):
        """diagnosis 为空走 mr_diagnosis 兜底时，仍按同一三坐标过滤并排除已删除行。"""
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A), _mr_row(INSTITUTE_B)])
        _insert(
            cdm_db,
            "mr_diagnosis",
            [
                _mr_diagnosis_row(INSTITUTE_A, "I10", "高血压", "D-A1"),
                _mr_diagnosis_row(INSTITUTE_B, "J18.9", "肺炎", "D-B1"),
                _mr_diagnosis_row(INSTITUTE_A, "E11", "2型糖尿病", "D-A9", is_deleted="1"),
            ],
        )

        frontpage = _load(PATIENT, VISIT, INSTITUTE_A)

        assert frontpage is not None
        assert [d["code"] for d in frontpage["diagnoses"]] == ["I10"]


class TestSourceUnavailable:
    """取数阶段数据库异常按“取数不可用”上报，不返回 None。"""

    def test_data_read_failure_after_identity_is_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(connection, "engine", _broken_engine(tmp_path))

        with pytest.raises(qc_module.CodingQcSourceUnavailableError):
            qc_module._load_frontpage_from_pg(
                qc_module.CodingQcIdentity(INSTITUTE_A, PATIENT, VISIT)
            )


class _QueueRecorder:
    def __init__(self) -> None:
        self.started: List[Dict[str, Any]] = []
        self.succeeded: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, Any]] = []

    def start_run(self, **kwargs) -> str:
        self.started.append(kwargs)
        return "run-coding-1"

    def finish_success(self, **kwargs) -> bool:
        self.succeeded.append(kwargs)
        return True

    def finish_failed(self, **kwargs) -> bool:
        self.failed.append(kwargs)
        return True


class _PersistenceRecorder:
    def __init__(self, failure: Optional[Exception] = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._failure = failure

    async def persist_analysis(self, result, *, actor=None, verified_identity=None):
        self.calls.append(
            {"result": result, "actor": actor, "verified_identity": verified_identity}
        )
        if self._failure is not None:
            raise self._failure
        return {"id": "persisted-coding-qc"}


class _CapturingEngine:
    """记录模型观测上下文，同时复用真实规则引擎产出报告。"""

    def __init__(self) -> None:
        self.contexts: List[Any] = []

    async def run_all(self, frontpage):
        self.contexts.append(current_llm_observation_context())
        return await CodingQCEngine(llm_client=None).run_all(frontpage)


def _fake_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/qc/coding-qc/check",
            "headers": [],
        }
    )


class _EndpointEnv:
    """内存替身：队列、落库、引擎都不触库；monkeypatch 由用例级 fixture 提供。"""

    def __init__(self, monkeypatch) -> None:
        self.queue = _QueueRecorder()
        self.persistence = _PersistenceRecorder()
        self.monkeypatch = monkeypatch
        monkeypatch.setattr(qc_module, "default_workflow_queue_state_service", self.queue)
        monkeypatch.setattr(qc_module, "default_qc_persistence_service", self.persistence)
        monkeypatch.setattr(
            qc_module, "_get_coding_qc_engine", lambda: CodingQCEngine(llm_client=None)
        )

    def use_engine(self, engine: Any) -> None:
        self.monkeypatch.setattr(qc_module, "_get_coding_qc_engine", lambda: engine)

    def use_identity(self, identity: qc_module.CodingQcIdentity) -> None:
        self.monkeypatch.setattr(
            qc_module, "_resolve_coding_qc_identity", lambda *args, **kwargs: identity
        )

    def fail_persistence(self, error: Exception) -> None:
        self.persistence = _PersistenceRecorder(error)
        self.monkeypatch.setattr(
            qc_module, "default_qc_persistence_service", self.persistence
        )


@pytest.fixture()
def endpoint_env(monkeypatch) -> _EndpointEnv:
    return _EndpointEnv(monkeypatch)


def _call_endpoint(payload: Dict[str, Any], roles: Tuple[str, ...] = ("admin",)):
    user = {"id": "user-1", "email": "qc@medqc.com", "roles": list(roles)}
    return asyncio.run(
        qc_module.check_coding_qc(_fake_request(), payload, current_user=user)
    )


def _visit_payload(**extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"visit_id": VISIT, "patient_id": PATIENT, "skip_llm": True}
    payload.update(extra)
    return payload


def _modern_identity(kwargs: Dict[str, Any]) -> Tuple[Any, Any, Any, Any]:
    """队列现代身份四元组：source_key + 三坐标。"""
    return (
        kwargs.get("source_key"),
        kwargs.get("institute_id"),
        kwargs.get("patient_id"),
        kwargs.get("visit_id"),
    )


class TestCheckCodingQcIdentityBranch:
    """/coding-qc/check 取数分支的状态与队列一致性。"""

    def test_ambiguous_identity_returns_409_without_queue_writes(self, cdm_db, endpoint_env):
        """同一 visit 在两家机构都有病历时，不得用请求体 visit 先起 legacy 队列。"""
        _seed_two_institutes(cdm_db)

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_visit_payload())

        assert excinfo.value.status_code == 409
        assert "机构" in excinfo.value.detail
        assert endpoint_env.queue.started == []
        assert endpoint_env.queue.failed == []
        assert endpoint_env.queue.succeeded == []
        assert endpoint_env.persistence.calls == []

    def test_missing_case_returns_404_without_queue_writes(self, cdm_db, endpoint_env):
        _seed_two_institutes(cdm_db)

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_visit_payload(visit_id="V-MISSING"))

        assert excinfo.value.status_code == 404
        assert endpoint_env.queue.started == []
        assert endpoint_env.queue.failed == []
        assert endpoint_env.persistence.calls == []

    def test_client_coordinates_cannot_steer_case_identity(self, cdm_db, endpoint_env):
        """请求体声明的机构/患者与唯一权威 cdm.mr 不符时拒绝，而不是按客户端坐标取数。"""
        _insert(cdm_db, "mr", [{**_mr_row(INSTITUTE_B), "patient_id": "P-SERVER"}])

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(
                _visit_payload(institute_id=INSTITUTE_A, patient_id="P-CLIENT")
            )

        assert excinfo.value.status_code == 404
        assert endpoint_env.queue.started == []
        assert endpoint_env.persistence.calls == []

    def test_db_error_returns_sanitized_503(self, tmp_path, endpoint_env, monkeypatch):
        monkeypatch.setattr(connection, "engine", _broken_engine(tmp_path))

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_visit_payload())

        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == "编码质控数据读取失败，请稍后重试"
        assert endpoint_env.queue.started == []
        assert endpoint_env.queue.failed == []
        assert endpoint_env.persistence.calls == []

    def test_read_failure_after_identity_fails_queue_sanitized(
        self, tmp_path, endpoint_env, monkeypatch
    ):
        """身份已确立后取数失败：队列按现代身份收尾，且不泄露底层错误。"""
        identity = qc_module.CodingQcIdentity(INSTITUTE_A, PATIENT, VISIT)
        endpoint_env.use_identity(identity)
        monkeypatch.setattr(connection, "engine", _broken_engine(tmp_path))

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_visit_payload())

        assert excinfo.value.status_code == 503
        assert _modern_identity(endpoint_env.queue.started[0]) == (
            "coding_qc",
            INSTITUTE_A,
            PATIENT,
            VISIT,
        )
        assert endpoint_env.queue.failed[0]["error_message"] == "编码质控数据读取失败，请稍后重试"
        assert "unable to open" not in str(endpoint_env.queue.failed[0]["error_message"])
        assert endpoint_env.persistence.calls == []

    def test_cost_only_case_is_not_reported_as_pass(self, cdm_db, endpoint_env):
        """只有费用/首页、没有诊断与手术时不得以“通过”结束。"""
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A)])
        _insert(cdm_db, "mr_cost", [_cost_row(INSTITUTE_A, "100")])

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_visit_payload())

        assert excinfo.value.status_code == 404
        assert "无可评估" in excinfo.value.detail
        assert _modern_identity(endpoint_env.queue.failed[0]) == (
            "coding_qc",
            INSTITUTE_A,
            PATIENT,
            VISIT,
        )
        assert endpoint_env.queue.succeeded == []
        assert endpoint_env.persistence.calls == []

    def test_single_institute_positive_path_carries_verified_identity(
        self, cdm_db, endpoint_env
    ):
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A)])
        _insert(cdm_db, "diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])

        response = _call_endpoint(_visit_payload())

        assert response["success"] is True
        assert endpoint_env.queue.succeeded and not endpoint_env.queue.failed
        assert len(endpoint_env.persistence.calls) == 1
        call = endpoint_env.persistence.calls[0]
        assert call["verified_identity"] == VerifiedQCIdentity(
            INSTITUTE_A, PATIENT, VISIT, "coding_qc"
        )
        assert call["result"]["metadata"]["institute_id"] == INSTITUTE_A
        assert call["result"]["metadata"]["patient_id"] == PATIENT
        assert call["result"]["metadata"]["visit_id"] == VISIT
        assert call["result"]["patient_id"] == PATIENT
        assert call["result"]["visit_id"] == VISIT

    def test_queue_start_and_finish_share_modern_identity(self, cdm_db, endpoint_env):
        """队列 start/finish 必须落在同一现代身份上（CAS 收尾不脱靶）。"""
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A)])
        _insert(cdm_db, "diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])

        _call_endpoint(_visit_payload())

        expected = ("coding_qc", INSTITUTE_A, PATIENT, VISIT)
        assert _modern_identity(endpoint_env.queue.started[0]) == expected
        assert _modern_identity(endpoint_env.queue.succeeded[0]) == expected
        assert endpoint_env.queue.failed == []

    def test_fetch_queue_write_observation_share_server_identity(self, cdm_db, endpoint_env):
        """缺机构时服务端推断的机构必须贯穿取数、队列、落库与模型观测。"""
        engine = _CapturingEngine()
        endpoint_env.use_engine(engine)
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_B)])
        _insert(cdm_db, "diagnosis", [_diag_row(INSTITUTE_B, "J18.9", "肺炎", "D-B1")])

        response = _call_endpoint(_visit_payload(skip_llm=False))

        assert response["success"] is True
        expected = ("coding_qc", INSTITUTE_B, PATIENT, VISIT)
        assert _modern_identity(endpoint_env.queue.started[0]) == expected
        assert _modern_identity(endpoint_env.queue.succeeded[0]) == expected
        assert endpoint_env.persistence.calls[0]["verified_identity"] == VerifiedQCIdentity(
            INSTITUTE_B, PATIENT, VISIT, "coding_qc"
        )
        assert engine.contexts and all(
            context.business_scene == "coding_qc"
            and context.executor_key == "coding_qc_engine"
            and context.record_key_hash == _expected_record_key_hash((INSTITUTE_B, PATIENT, VISIT))
            for context in engine.contexts
        )

    def test_persistence_failure_fails_queue_sanitized(self, cdm_db, endpoint_env):
        endpoint_env.fail_persistence(RuntimeError("dsn=postgresql://user:pw@host/db"))
        _insert(cdm_db, "mr", [_mr_row(INSTITUTE_A)])
        _insert(cdm_db, "diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_visit_payload())

        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == "编码质控执行或结果保存失败，请稍后重试"
        assert endpoint_env.queue.succeeded == []
        assert endpoint_env.queue.failed[0]["error_message"] == "编码质控执行或结果保存失败，请稍后重试"
        assert "postgresql://" not in str(endpoint_env.queue.failed[0]["error_message"])

    def test_doctor_role_is_forbidden(self, endpoint_env):
        """与 formal 一致：编码质控需要 MEDICAL_RECORDS.ANALYZE。"""
        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_visit_payload(), roles=("doctor",))

        assert excinfo.value.status_code == 403
        assert endpoint_env.queue.started == []
        assert endpoint_env.persistence.calls == []

    def test_manual_frontpage_mode_does_not_claim_verified_identity(self, endpoint_env):
        """旧手工 frontpage 模式保持可用，但不写入已验证身份、也不推进队列状态。"""
        response = _call_endpoint(
            {
                "frontpage": {
                    "sex": "男",
                    "age": "65岁",
                    "diagnoses": [{"code": "I10", "name": "高血压"}],
                    "surgeries": [],
                },
                "skip_llm": True,
                "institute_id": "CLIENT-CLAIMED",
                "patient_id": PATIENT,
            }
        )

        assert response["success"] is True
        call = endpoint_env.persistence.calls[0]
        assert call["verified_identity"] is None
        assert "institute_id" not in call["result"]["metadata"]
        assert endpoint_env.queue.started == []
        assert endpoint_env.queue.succeeded == []
        assert endpoint_env.queue.failed == []


class TestSchemaAuthorityNotSearchPath:
    """显式 cdm schema：public 同名影子行不得被认领、混读或写入身份。"""

    def test_public_shadow_rows_do_not_grant_identity(self, cdm_db, endpoint_env):
        """只有 public.mr/诊断行时不得定身份：解析为空、端点 404 且不写队列。"""
        _insert(cdm_db, "public.mr", [_mr_row(INSTITUTE_A)])
        _insert(cdm_db, "public.diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])

        assert _resolve(PATIENT, VISIT, INSTITUTE_A) is None

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_visit_payload(institute_id=INSTITUTE_A))

        assert excinfo.value.status_code == 404
        assert endpoint_env.queue.started == []
        assert endpoint_env.queue.failed == []
        assert endpoint_env.persistence.calls == []

    def test_public_shadow_rows_do_not_mix_into_frontpage(self, cdm_db):
        """cdm 与 public 同名表并存时，只按同一三坐标读 cdm 的首页/诊断/手术/费用。"""
        _insert(cdm_db, "cdm.mr", [_mr_row(INSTITUTE_A, sex="男")])
        _insert(cdm_db, "cdm.diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])
        _insert(
            cdm_db,
            "cdm.mr_surgery",
            [
                {
                    "institute_id": INSTITUTE_A,
                    "patient_id": PATIENT,
                    "visit_id": VISIT,
                    "surgery_id": "S-A1",
                    "surgery_code": "47.0",
                    "surgery_name": "阑尾切除术",
                    "main_surgery_sign": "1",
                }
            ],
        )
        _insert(cdm_db, "cdm.mr_cost", [_cost_row(INSTITUTE_A, "100")])

        # public 影子行：同 patient/visit，但机构与取数内容都不同
        _insert(cdm_db, "public.mr", [_mr_row(INSTITUTE_B, sex="女")])
        _insert(cdm_db, "public.diagnosis", [_diag_row(INSTITUTE_B, "J18.9", "肺炎", "D-B1")])
        _insert(
            cdm_db,
            "public.mr_surgery",
            [
                {
                    "institute_id": INSTITUTE_B,
                    "patient_id": PATIENT,
                    "visit_id": VISIT,
                    "surgery_id": "S-B1",
                    "surgery_code": "51.23",
                    "surgery_name": "腹腔镜胆囊切除术",
                    "main_surgery_sign": "1",
                }
            ],
        )
        _insert(cdm_db, "public.mr_cost", [_cost_row(INSTITUTE_B, "200")])

        frontpage = _load(PATIENT, VISIT, INSTITUTE_A)

        assert frontpage is not None
        assert frontpage["sex"] == "男"
        assert [d["code"] for d in frontpage["diagnoses"]] == ["I10"]
        assert [s["code"] for s in frontpage["surgeries"]] == ["47.0"]
        assert frontpage["fees"]["pathology_diagnostic_fee"] == "100"
        # public 影子行不构成可核验身份
        assert _load(PATIENT, VISIT, INSTITUTE_B) is None

    def test_diagnosis_fallback_reads_cdm_not_public(self, cdm_db):
        """diagnosis 为空走 mr_diagnosis 兜底时，也只读 cdm.mr_diagnosis。"""
        _insert(cdm_db, "cdm.mr", [_mr_row(INSTITUTE_A)])
        _insert(
            cdm_db,
            "cdm.mr_diagnosis",
            [_mr_diagnosis_row(INSTITUTE_A, "I10", "高血压", "D-A1")],
        )
        _insert(cdm_db, "public.mr", [_mr_row(INSTITUTE_B)])
        _insert(
            cdm_db,
            "public.mr_diagnosis",
            [_mr_diagnosis_row(INSTITUTE_B, "J18.9", "肺炎", "D-B1")],
        )

        frontpage = _load(PATIENT, VISIT, INSTITUTE_A)

        assert frontpage is not None
        assert [d["code"] for d in frontpage["diagnoses"]] == ["I10"]

    def test_endpoint_identity_and_queue_use_cdm_not_public_shadow(self, cdm_db, endpoint_env):
        """public 同名表存在同 visit 的多机构行时，端点仍按 cdm 身份取数并收尾队列。"""
        _insert(cdm_db, "cdm.mr", [_mr_row(INSTITUTE_A)])
        _insert(cdm_db, "cdm.diagnosis", [_diag_row(INSTITUTE_A, "I10", "高血压", "D-A1")])
        # 未限定 schema 的读取会在这里命中两个候选（旧实现据此报 409）
        _insert(cdm_db, "public.mr", [_mr_row(INSTITUTE_B), _mr_row("INST-PUBLIC-2")])
        _insert(cdm_db, "public.diagnosis", [_diag_row(INSTITUTE_B, "J18.9", "肺炎", "D-B1")])

        response = _call_endpoint(_visit_payload())

        assert response["success"] is True
        expected = ("coding_qc", INSTITUTE_A, PATIENT, VISIT)
        assert _modern_identity(endpoint_env.queue.started[0]) == expected
        assert _modern_identity(endpoint_env.queue.succeeded[0]) == expected
        assert endpoint_env.queue.failed == []
        assert endpoint_env.persistence.calls[0]["verified_identity"] == VerifiedQCIdentity(
            INSTITUTE_A, PATIENT, VISIT, "coding_qc"
        )
