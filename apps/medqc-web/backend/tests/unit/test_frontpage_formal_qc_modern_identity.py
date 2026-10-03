"""首页形式质控现代身份与失败关闭 - 独立反例测试（不连业务库、纯内存替身）。

合同（主协调 Agent 给定）：

- POST /api/v1/qc/formal-qc/validate 不再采信客户端 frontpage 正文：由服务端直接调用
  get_frontpage_sheet(patient_id, visit_id, institute_id?) 读取正式首页，并以读到的 basic
  三坐标作为唯一权威身份执行 FrontpageFormalQC；
- 请求体 frontpage 仅兼容接收，既不参与取数也不参与判定；
- 队列 start/finish 与 persist_analysis 共用同一核实身份及 source_key=frontpage_formal_qc
  （VerifiedQCIdentity 四维），不再出现“只有 visit 两键”的 legacy 落法；
- 固定脱敏失败语义：显式空机构/身份参数不合法 400、病例缺失 404、身份歧义或与请求坐标漂移 409、
  取数或落库不可用（含缺迁移列）503、局部筛选不能覆盖完整病例结果 422；任一步失败都不写结果、不进队列成功态；
- 结果已落库后队列 finish_success 失败只记日志：不得把已保存的质控谎报成未保存；
- 队列 finish_failed 自身异常不得覆盖原始固定 HTTP 错误。

本文件证明什么、不证明什么：

- 证明：路由层的取数入口、身份核对、固定错误映射、队列/落库身份一致性、失败关闭副作用边界；
- 不证明：真实 PG 上的三坐标读取正确性（由 test_medical_records_frontpage_sheet_identity.py
  与后续非生产库验收覆盖），也不触达任何数据库写或真实 E2E。

运行方式（不加载 conftest，避免连库）：

    cd backend
    python -m pytest tests/unit/test_frontpage_formal_qc_modern_identity.py --noconftest
"""

from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any, Dict, List, Optional, Tuple

import pytest
from fastapi import HTTPException
from starlette.requests import Request

# 先隔离 DATABASE_URL 再导入应用，禁止单元测试继承业务库连接。
_REFUSE_DSN = "postgresql://invalid:invalid@127.0.0.1:1/nonexistent"
if not os.environ.get("DATABASE_URL", "").strip():
    os.environ["DATABASE_URL"] = _REFUSE_DSN

import app.routers.qc as qc_module  # noqa: E402
from app.services import scoring_standard_service  # noqa: E402
from app.services.frontpage_formal_qc import FrontpageFormalQC  # noqa: E402
from app.services.medical_records.errors import (  # noqa: E402
    MedicalRecordsConflictError,
    MedicalRecordsNotFoundError,
    MedicalRecordsSourceUnavailableError,
    MedicalRecordsStorageError,
)
from app.services.qc_persistence_service import VerifiedQCIdentity  # noqa: E402

INSTITUTE_A = "INST-A"
INSTITUTE_B = "INST-B"
PATIENT = "P-1"
VISIT = "V-1"
VERIFIED = VerifiedQCIdentity(INSTITUTE_A, PATIENT, VISIT, "frontpage_formal_qc")


def _sheet(
    *,
    institute_id: str = INSTITUTE_A,
    patient_id: str = PATIENT,
    visit_id: str = VISIT,
    **basic_extra: Any,
) -> Dict[str, Any]:
    """服务端读到的正式首页（get_frontpage_sheet 返回形状）。"""

    basic: Dict[str, Any] = {
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
    }
    basic.update(basic_extra)
    return {
        "basic": basic,
        "diagnoses": [
            {
                "diagnosis_type": "主要诊断",
                "diagnosis_no": "1",
                "diagnosis_name": "高血压",
                "diagnosis_code": "I10",
            }
        ],
        "surgeries": [],
        "cost": None,
        "other_medical_info": {},
    }


class _QueueRecorder:
    """内存队列替身：记录身份，并可按需制造收尾失败。"""

    def __init__(
        self,
        start_error: Optional[Exception] = None,
        finish_success_error: Optional[Exception] = None,
        finish_failed_error: Optional[Exception] = None,
    ) -> None:
        self.started: List[Dict[str, Any]] = []
        self.succeeded: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, Any]] = []
        self.start_error = start_error
        self.finish_success_error = finish_success_error
        self.finish_failed_error = finish_failed_error

    def start_run(self, **kwargs: Any) -> str:
        if self.start_error is not None:
            raise self.start_error
        self.started.append(kwargs)
        return "run-frontpage-1"

    def finish_success(self, **kwargs: Any) -> bool:
        self.succeeded.append(kwargs)
        if self.finish_success_error is not None:
            raise self.finish_success_error
        return True

    def finish_failed(self, **kwargs: Any) -> bool:
        self.failed.append(kwargs)
        if self.finish_failed_error is not None:
            raise self.finish_failed_error
        return True


class _PersistenceRecorder:
    def __init__(self, failure: Optional[Exception] = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.failure = failure

    async def persist_analysis(self, result, *, actor=None, verified_identity=None):
        self.calls.append(
            {"result": result, "actor": actor, "verified_identity": verified_identity}
        )
        if self.failure is not None:
            raise self.failure
        return {"qc_result_id": "persisted-frontpage-qc"}


class _RecordingEngine:
    """记录引擎实际收到的首页对象，同时复用真实规则引擎产出报告。"""

    def __init__(self) -> None:
        self.sheets: List[Any] = []
        self._has_override = False
        self._override_report: Any = None

    def override(self, report: Any) -> None:
        """强制返回指定报告（可为 None，用于断言非预期报告结构的失败关闭）。"""

        self._has_override = True
        self._override_report = report

    def validate(self, frontpage, categories=None, severities=None):
        self.sheets.append(frontpage)
        if self._has_override:
            return self._override_report
        return FrontpageFormalQC().validate(
            frontpage, categories=categories, severities=severities
        )


def _empty_report() -> Any:
    return type("EmptyReport", (), {"total_rules": 0, "passed": 0, "failed": 0, "results": []})()


def _fake_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/qc/formal-qc/validate",
            "headers": [],
        }
    )


class _EndpointEnv:
    """内存替身环境：取数、队列、落库、引擎都不触库。"""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        resolver: Any = None,
    ) -> None:
        self.monkeypatch = monkeypatch
        self.queue = _QueueRecorder()
        self.persistence = _PersistenceRecorder()
        self.engine = _RecordingEngine()
        self.read_calls: List[Dict[str, Any]] = []
        self.resolver: Any = _sheet() if resolver is None else resolver
        monkeypatch.setattr(qc_module, "get_frontpage_sheet", self._read_sheet)
        monkeypatch.setattr(qc_module, "default_workflow_queue_state_service", self.queue)
        monkeypatch.setattr(qc_module, "default_qc_persistence_service", self.persistence)
        monkeypatch.setattr(qc_module, "_formal_qc_engine", self.engine)
        monkeypatch.setattr(scoring_standard_service, "get_default_standard", lambda _: None)

    def _read_sheet(
        self,
        patient_id: str,
        visit_id: str,
        institute_id: Optional[str] = None,
        session_factory: Any = None,
    ) -> Any:
        self.read_calls.append(
            {
                "patient_id": patient_id,
                "visit_id": visit_id,
                "institute_id": institute_id,
                "session_factory": session_factory,
            }
        )
        if isinstance(self.resolver, Exception):
            raise self.resolver
        return self.resolver

    def use_sheet(self, sheet: Any) -> None:
        self.resolver = sheet

    def use_error(self, error: Exception) -> None:
        self.resolver = error

    def use_queue(self, queue: _QueueRecorder) -> None:
        self.queue = queue
        self.monkeypatch.setattr(qc_module, "default_workflow_queue_state_service", queue)

    def fail_persistence(self, error: Exception) -> None:
        self.persistence = _PersistenceRecorder(error)
        self.monkeypatch.setattr(
            qc_module, "default_qc_persistence_service", self.persistence
        )

    def assert_no_side_effects(self) -> None:
        """失败关闭：不启动/收尾队列、不写任何结果。"""

        assert self.queue.started == []
        assert self.queue.succeeded == []
        assert self.queue.failed == []
        assert self.persistence.calls == []


@pytest.fixture()
def endpoint_env(monkeypatch: pytest.MonkeyPatch) -> _EndpointEnv:
    return _EndpointEnv(monkeypatch)


def _call_endpoint(payload: Dict[str, Any], roles: Tuple[str, ...] = ("admin",)) -> Dict[str, Any]:
    user = {"id": "user-1", "email": "qc@medqc.com", "roles": list(roles)}
    return asyncio.run(
        qc_module.validate_frontpage_formal(_fake_request(), payload, current_user=user)
    )


def _identity_payload(**extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"patient_id": PATIENT, "visit_id": VISIT}
    payload.update(extra)
    return payload


def test_scoring_failure_preserves_saved_formal_report(endpoint_env, monkeypatch):
    def failed(_):
        raise RuntimeError("合成配置不可用")

    monkeypatch.setattr(scoring_standard_service, "get_default_standard", failed)
    response = _call_endpoint(_identity_payload())
    assert response["success"] is True
    assert response["data"]["scoring"]["status"] == "unavailable"
    assert response["data"]["scoring"]["score"] is None
    assert response["data"]["persistence"]["qc_result_id"] == "persisted-frontpage-qc"
    assert len(endpoint_env.persistence.calls) == 1 and len(endpoint_env.queue.succeeded) == 1
    assert "scoring" not in endpoint_env.persistence.calls[0]["result"]


def test_scoring_uses_server_discharge_department_not_client(endpoint_env, monkeypatch):
    sheet = _sheet()
    sheet["hospitalization"] = {"discharge_dept": "合成出院科室"}
    endpoint_env.use_sheet(sheet)
    contexts = []

    def observed(report, **context):
        contexts.append(context)
        return {"status": "no_standard", "score": None}

    monkeypatch.setattr(qc_module, "score_frontpage_report", observed)
    response = _call_endpoint(_identity_payload(frontpage={"hospitalization": {"discharge_dept": "伪造科室"}}))
    assert response["success"] is True
    assert contexts[0]["department_name"] == "合成出院科室"
    assert contexts[0]["institute_id"] == INSTITUTE_A


def _modern_identity(kwargs: Dict[str, Any]) -> Tuple[Any, Any, Any, Any]:
    """队列现代身份四元组：source_key + 三坐标（legacy 两键落法会在此暴露为缺项）。"""

    return (
        kwargs.get("source_key"),
        kwargs.get("institute_id"),
        kwargs.get("patient_id"),
        kwargs.get("visit_id"),
    )


def _assert_all_queue_writes_are_modern(env: _EndpointEnv) -> None:
    expected = ("frontpage_formal_qc", INSTITUTE_A, PATIENT, VISIT)
    assert env.queue.started, "成功/失败路径都应先以现代身份启动队列"
    for call in env.queue.started + env.queue.succeeded + env.queue.failed:
        assert _modern_identity(call) == expected


class TestUntrustedClientBody:
    """客户端正文既不参与取数也不参与判定。"""

    def test_client_frontpage_body_is_ignored_for_read_and_judgement(self, endpoint_env):
        server_sheet = _sheet(patient_name="张三", sex="男")
        endpoint_env.use_sheet(server_sheet)
        forged_body = {
            "basic": {"institute_id": INSTITUTE_B, "patient_id": "P-BODY", "visit_id": "V-BODY"},
            "diagnoses": [{"diagnosis_type": "主要诊断", "diagnosis_name": "伪造诊断"}],
        }

        response = _call_endpoint(_identity_payload(frontpage=forged_body))

        assert response["success"] is True
        # 取数只用请求身份，且不带任何来自正文的坐标。
        assert len(endpoint_env.read_calls) == 1
        read_call = endpoint_env.read_calls[0]
        assert read_call["patient_id"] == PATIENT
        assert read_call["visit_id"] == VISIT
        assert read_call["institute_id"] is None
        # 引擎收到的是服务端读到的首页对象本身，伪造正文没有进入判定。
        assert endpoint_env.engine.sheets == [server_sheet]
        assert endpoint_env.engine.sheets[0] is server_sheet
        call = endpoint_env.persistence.calls[0]
        assert call["result"]["metadata"]["patient_id"] == PATIENT
        assert call["result"]["metadata"]["institute_id"] == INSTITUTE_A
        assert "P-BODY" not in str(call["result"])
        assert call["verified_identity"] == VERIFIED

    def test_forged_body_cannot_steer_identity_across_institutes(self, endpoint_env):
        """同患者就诊跨机构：显式机构下身份仍取服务端首页，正文声明的机构无效。"""

        endpoint_env.use_sheet(_sheet(institute_id=INSTITUTE_A))

        _call_endpoint(
            _identity_payload(
                institute_id=INSTITUTE_A,
                frontpage={
                    "basic": {
                        "institute_id": INSTITUTE_B,
                        "patient_id": PATIENT,
                        "visit_id": VISIT,
                    }
                },
            )
        )

        assert endpoint_env.read_calls[0]["institute_id"] == INSTITUTE_A
        assert endpoint_env.persistence.calls[0]["verified_identity"] == VERIFIED
        _assert_all_queue_writes_are_modern(endpoint_env)

    def test_body_only_payload_without_identity_is_400(self, endpoint_env):
        """只有 frontpage 正文（旧两键/纯正文）不再有 legacy 通道。"""

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint({"frontpage": {"patient_name": "张三"}, "visit_id": VISIT})

        assert excinfo.value.status_code == 400
        assert excinfo.value.detail == qc_module._FORMAL_QC_INVALID_IDENTITY_DETAIL
        assert endpoint_env.read_calls == []
        endpoint_env.assert_no_side_effects()

    def test_explicit_blank_institute_is_400_without_reading(self, endpoint_env):
        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload(institute_id="   "))

        assert excinfo.value.status_code == 400
        assert excinfo.value.detail == qc_module._FORMAL_QC_INVALID_IDENTITY_DETAIL
        assert endpoint_env.read_calls == []
        endpoint_env.assert_no_side_effects()


class TestSheetReadFailureSemantics:
    """取数与身份核对的固定失败语义，且失败不产生任何副作用。"""

    def test_missing_case_is_404_without_queue_or_persistence(self, endpoint_env):
        endpoint_env.use_error(MedicalRecordsNotFoundError("未找到病案首页数据"))

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 404
        assert excinfo.value.detail == qc_module._FORMAL_QC_NOT_FOUND_DETAIL
        endpoint_env.assert_no_side_effects()

    def test_cross_institute_ambiguity_without_institute_is_409(self, endpoint_env):
        """省略机构而 patient+visit 命中多机构：服务端拒绝，绝不按 first() 猜病例。"""

        endpoint_env.use_error(MedicalRecordsConflictError("病案首页定位不唯一，请指定机构号后重试"))

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 409
        assert excinfo.value.detail == qc_module._FORMAL_QC_AMBIGUOUS_DETAIL
        assert endpoint_env.read_calls[0]["institute_id"] is None
        endpoint_env.assert_no_side_effects()

    def test_sheet_identity_drift_from_request_is_409(self, endpoint_env):
        """服务端读到的 basic 与请求坐标不一致：拒绝，而不是按客户端坐标改写身份。"""

        endpoint_env.use_sheet(_sheet(patient_id="P-OTHER"))

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 409
        assert excinfo.value.detail == qc_module._FORMAL_QC_AMBIGUOUS_DETAIL
        endpoint_env.assert_no_side_effects()

    def test_sheet_with_blank_institute_coordinate_is_409(self, endpoint_env):
        endpoint_env.use_sheet(_sheet(institute_id=""))

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 409
        endpoint_env.assert_no_side_effects()

    @pytest.mark.parametrize(
        "error",
        [
            MedicalRecordsSourceUnavailableError(
                "病案首页取数失败 postgresql://invalid:invalid@127.0.0.1:1/nonexistent"
            ),
            MedicalRecordsStorageError("查询文书失败: invalid"),
            RuntimeError("unexpected driver error postgresql://invalid:invalid@127.0.0.1:1/nonexistent"),
        ],
    )
    def test_source_failures_are_sanitized_503(self, endpoint_env, error):
        endpoint_env.use_error(error)

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == qc_module._FORMAL_QC_SOURCE_UNAVAILABLE_DETAIL
        assert "invalid" not in excinfo.value.detail
        assert "postgresql" not in excinfo.value.detail
        endpoint_env.assert_no_side_effects()

    def test_malformed_category_filter_is_400_before_any_side_effect(self, endpoint_env):
        """畸形筛选值固定 400，不得落成未映射 500，也不得启动队列/写入。"""

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload(categories=["not-a-category"]))

        assert excinfo.value.status_code == 400
        assert endpoint_env.read_calls == []
        endpoint_env.assert_no_side_effects()

    def test_malformed_severity_filter_is_400_before_reading(self, endpoint_env):
        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload(severities=["catastrophic"]))

        assert excinfo.value.status_code == 400
        assert endpoint_env.read_calls == []
        endpoint_env.assert_no_side_effects()

    @pytest.mark.parametrize("invalid", ["required", 1, {"required": True}, [1]])
    def test_non_list_or_non_string_filter_is_400(self, endpoint_env, invalid):
        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload(categories=invalid))

        assert excinfo.value.status_code == 400
        assert endpoint_env.read_calls == []
        endpoint_env.assert_no_side_effects()


class TestModernIdentityPlumbing:
    """队列 start/finish 与落库共用同一个核实身份。"""

    def test_success_path_carries_verified_identity_everywhere(self, endpoint_env):
        endpoint_env.use_sheet(_sheet(admission_dept_name="心内科"))

        response = _call_endpoint(_identity_payload())

        assert response["success"] is True
        assert response["data"]["persistence"] == {"qc_result_id": "persisted-frontpage-qc"}
        call = endpoint_env.persistence.calls[0]
        assert call["verified_identity"] == VERIFIED
        assert call["result"]["patient_id"] == PATIENT
        assert call["result"]["visit_id"] == VISIT
        assert call["result"]["record_id"] == f"frontpage::{VISIT}"
        metadata = call["result"]["metadata"]
        assert (metadata["institute_id"], metadata["patient_id"], metadata["visit_id"]) == (
            INSTITUTE_A,
            PATIENT,
            VISIT,
        )
        assert metadata["data_source"] == "frontpage_formal_qc"
        assert metadata["workflow_type"] == "frontpage"
        assert metadata["department"] == "心内科"
        _assert_all_queue_writes_are_modern(endpoint_env)

    def test_inferred_institute_becomes_verified_identity(self, endpoint_env):
        """省略机构时，身份取服务端首页推断出的机构，而不是留空。"""

        endpoint_env.use_sheet(_sheet(institute_id=INSTITUTE_B))

        _call_endpoint(_identity_payload())

        assert endpoint_env.persistence.calls[0]["verified_identity"] == VerifiedQCIdentity(
            INSTITUTE_B, PATIENT, VISIT, "frontpage_formal_qc"
        )
        assert _modern_identity(endpoint_env.queue.started[0]) == (
            "frontpage_formal_qc",
            INSTITUTE_B,
            PATIENT,
            VISIT,
        )

    def test_queue_start_failure_does_not_write_results(self, endpoint_env):
        endpoint_env.use_queue(_QueueRecorder(start_error=RuntimeError("queue db down")))

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == qc_module._FORMAL_QC_FAILURE_DETAIL
        assert endpoint_env.persistence.calls == []
        assert endpoint_env.queue.succeeded == []
        assert endpoint_env.queue.failed == []


class TestZeroRuleFailClosed:
    """零规则/非预期报告结构不得被当成通过。"""

    def test_zero_rules_without_filter_is_503_and_persists_nothing(self, endpoint_env):
        endpoint_env.engine.override(_empty_report())

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == qc_module._FORMAL_QC_FAILURE_DETAIL
        assert endpoint_env.persistence.calls == []
        assert endpoint_env.queue.succeeded == []
        # 已启动的队列必须以现代身份收失败态。
        assert _modern_identity(endpoint_env.queue.failed[0]) == (
            "frontpage_formal_qc",
            INSTITUTE_A,
            PATIENT,
            VISIT,
        )

    def test_partial_scope_is_422_before_reading_or_writing(self, endpoint_env):
        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload(categories=["required"]))

        assert excinfo.value.status_code == 422
        assert excinfo.value.detail == qc_module._FORMAL_QC_PARTIAL_SCOPE_DETAIL
        assert endpoint_env.read_calls == []
        endpoint_env.assert_no_side_effects()

    @pytest.mark.parametrize(
        "report",
        [
            None,
            object(),
            type("BadCount", (), {"total_rules": "84", "passed": 0, "failed": 0, "results": []})(),
            type("BadResults", (), {"total_rules": 84, "passed": 0, "failed": 0, "results": None})(),
        ],
    )
    def test_unexpected_report_shape_is_503_and_persists_nothing(self, endpoint_env, report):
        endpoint_env.engine.override(report)

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == qc_module._FORMAL_QC_FAILURE_DETAIL
        assert endpoint_env.persistence.calls == []


class TestPersistAndFinishEdgeCases:
    """落库失败与队列收尾失败的边界。"""

    def test_missing_migration_columns_are_sanitized_503(self, endpoint_env):
        """缺现代身份列（迁移未部署）按 503 脱敏，不回显列名或连接细节。"""

        endpoint_env.fail_persistence(
            RuntimeError("qc.qc_results missing verified identity columns: ['identity_version']")
        )

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == qc_module._FORMAL_QC_FAILURE_DETAIL
        assert "identity_version" not in excinfo.value.detail
        assert endpoint_env.queue.succeeded == []
        failure_message = endpoint_env.queue.failed[0]["error_message"]
        assert failure_message == qc_module._FORMAL_QC_QUEUE_FAILURE_MESSAGE
        assert "identity_version" not in failure_message

    def test_persistence_failure_keeps_fixed_error_when_finish_failed_raises(self, endpoint_env):
        """队列失败收尾自身异常不得覆盖原始固定 HTTP 错误。"""

        endpoint_env.fail_persistence(RuntimeError("persist boom"))
        endpoint_env.queue.finish_failed_error = RuntimeError("queue boom")

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload())

        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == qc_module._FORMAL_QC_FAILURE_DETAIL
        assert endpoint_env.persistence.calls != []

    def test_finish_success_failure_after_persist_does_not_claim_unsaved(self, endpoint_env):
        """结果已保存：队列 finish_success 失败只记日志，不得谎称质控未保存。"""

        queue = _QueueRecorder(finish_success_error=RuntimeError("queue db down"))
        endpoint_env.use_queue(queue)

        response = _call_endpoint(_identity_payload())

        assert response["success"] is True
        assert len(endpoint_env.persistence.calls) == 1
        assert _modern_identity(queue.succeeded[0]) == (
            "frontpage_formal_qc",
            INSTITUTE_A,
            PATIENT,
            VISIT,
        )
        assert queue.failed == []


class TestAccessGate:
    """资源权限与角色边界：POST 独立校验，不靠 GET 的读取门。"""

    def test_resource_permission_gate_denies_roles_without_qc_results_create(
        self, monkeypatch
    ):
        env = _EndpointEnv(monkeypatch)

        with pytest.raises(HTTPException) as excinfo:
            _call_endpoint(_identity_payload(), roles=("doctor",))

        assert excinfo.value.status_code == 403
        assert env.read_calls == []
        env.assert_no_side_effects()

    def test_role_dependency_is_limited_to_admin_and_qc_manager(self):
        depends = inspect.signature(qc_module.validate_frontpage_formal).parameters[
            "current_user"
        ].default
        checker = depends.dependency
        assert checker is not None

        allowed = asyncio.run(checker({"id": "u-1", "roles": ["qc_manager"]}))
        assert allowed["roles"] == ["qc_manager"]

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(checker({"id": "u-2", "roles": ["qc_staff"]}))

        assert excinfo.value.status_code == 403
        assert "qc_manager" in excinfo.value.detail

    def test_endpoint_uses_modern_source_key_constant(self):
        assert qc_module._FORMAL_QC_SOURCE_KEY == "frontpage_formal_qc"
        assert qc_module._FORMAL_QC_WORKFLOW_TYPE == "frontpage_qc"
        assert VerifiedQCIdentity(
            INSTITUTE_A, PATIENT, VISIT, qc_module._FORMAL_QC_SOURCE_KEY
        ) == VERIFIED
