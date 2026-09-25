"""现代质控快照路由 ``/api/v1/workstation/case-qc/snapshot`` 的 HTTP 边界。

覆盖：

- 未认证 401；非 admin/qc_manager（含 qc_staff/doctor）一律 403 且不触碰服务：
  本批临时按角色收窄，因为调用方自填三坐标、尚无机构对象级授权
- ``QC_RESULTS:READ`` 资源门独立保留：角色白名单通过但资源权限被收回时仍 403
- 四个必填 query（institute_id/patient_id/visit_id/source_key）缺一即 422
- 空白或非规范身份参数映射为脱敏 422，不回显原始值
- ``CaseNotFound`` -> 404、``CaseIdentityAmbiguous`` -> 409、``SchemaUnavailable``/
  ``SourceUnavailable`` -> 503、其它异常同样脱敏 503
- 只向服务传 ``VerifiedQCIdentity`` 与 ``recipient_id``，绝不传 ``record_id``
- 错误响应与日志都不泄露底层 DSN 或病例原文
- 同步 SQLAlchemy 读取在线程池执行：事件循环 ticker 不被饿死，且服务调用线程
  不等于事件循环线程（附内联阻塞反例自检）

测试只用内存假服务，不连接数据库、不加载根 conftest（根 conftest 会初始化 demo
SQLite 并引入其它副作用）：:

    DATABASE_URL=postgresql://invalid:invalid@127.0.0.1:1/nonexistent \
        python -m pytest tests/unit/test_workstation_modern_case_snapshot_api.py --noconftest
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Dict

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import workstation
from app.services import modern_case_qc_result_service as modern_case_service
from app.services.qc_persistence_service import VerifiedQCIdentity


SNAPSHOT_PATH = "/api/v1/workstation/case-qc/snapshot"
PRIVATE_DSN = "postgresql://qc_user:qc_pw@10.11.12.13:5432/cdm_private"
PRIVATE_PATIENT = "张三"

VALID_PARAMS: Dict[str, str] = {
    "institute_id": "inst-1",
    "patient_id": "patient-1",
    "visit_id": "visit-1",
    "source_key": "coding_qc",
}

SOURCE_KEYS = {
    "frontpage_formal_qc",
    "coding_qc",
    "settlement_qc",
    "settlement_generate_qc",
}

SNAPSHOT_DELAY_SECONDS = 0.2
TICK_SECONDS = 0.01


class RecordingSnapshotService:
    """记录调用实参与执行线程的假服务，用于证明坐标与线程边界。"""

    def __init__(
        self,
        result: Any = None,
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.result = {"case": {"visit_id": "visit-1"}} if result is None else result
        self.error = error
        self.delay = delay
        self.calls: list[Dict[str, Any]] = []
        self.thread_ids: list[int] = []

    def get_snapshot(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({"args": args, "kwargs": kwargs})
        self.thread_ids.append(threading.get_ident())
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


def user_with(roles: list[str], user_id: str = "qc-reader-1") -> Dict[str, Any]:
    return {
        "id": user_id,
        "name": "质控员",
        "email": "qc-reader@example.invalid",
        "roles": roles,
    }


def client_for(user: Dict[str, Any] | None) -> TestClient:
    app = FastAPI()
    app.include_router(workstation.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def install_service(monkeypatch: pytest.MonkeyPatch, service: RecordingSnapshotService) -> None:
    monkeypatch.setattr(
        workstation, "default_modern_case_qc_result_service", service, raising=False
    )


# --------------------------------------------------------------------------- 权限


def test_unauthenticated_request_is_401_without_touching_service(monkeypatch):
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)
    # 真实 get_current_user 在无凭据时直接 401，而不是返回 None。
    def reject_credentials() -> Dict[str, Any]:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    app = FastAPI()
    app.include_router(workstation.router)
    app.dependency_overrides[get_current_user] = reject_credentials

    response = TestClient(app).get(SNAPSHOT_PATH, params=VALID_PARAMS)

    assert response.status_code == 401
    assert service.calls == []


def test_role_without_qc_results_read_is_403_without_touching_service(monkeypatch):
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)

    response = client_for(user_with(["outsider"])).get(SNAPSHOT_PATH, params=VALID_PARAMS)

    assert response.status_code == 403
    assert service.calls == []


@pytest.mark.parametrize("role", ["outsider", "qc_staff", "doctor"])
def test_permission_denial_precedes_identity_validation(monkeypatch, role):
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)
    blank_params = {**VALID_PARAMS, "visit_id": "   "}

    response = client_for(user_with([role])).get(SNAPSHOT_PATH, params=blank_params)

    assert response.status_code == 403
    assert service.calls == []


@pytest.mark.parametrize("role", ["admin", "qc_manager", "qc_staff", "doctor"])
def test_only_management_roles_can_read_snapshot(monkeypatch, role):
    service = RecordingSnapshotService(result={"rules": [{"rule_id": "007"}]})
    install_service(monkeypatch, service)

    response = client_for(user_with([role])).get(SNAPSHOT_PATH, params=VALID_PARAMS)

    if role in ("admin", "qc_manager"):
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
        assert response.json()["data"] == {"rules": [{"rule_id": "007"}]}
        assert len(service.calls) == 1
    else:
        # qc_staff/doctor 持有 QC_RESULTS:READ，但仍不得按自填机构读全院病例。
        assert response.status_code == 403, response.text
        assert response.json()["detail"]
        assert service.calls == []


@pytest.mark.parametrize("role", ["qc_staff", "doctor"])
def test_non_management_clinical_roles_are_denied_without_service_call(monkeypatch, role):
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)
    # 自填机构 + 病例原文：拒绝路径不得回显，也不得落到服务。
    params = {**VALID_PARAMS, "patient_id": PRIVATE_PATIENT}

    response = client_for(user_with([role])).get(SNAPSHOT_PATH, params=params)

    assert response.status_code == 403, response.text
    assert service.calls == []
    assert PRIVATE_PATIENT not in response.text


def test_resource_gate_survives_role_narrowing(monkeypatch):
    from app.core import permissions as permissions_module

    monkeypatch.delitem(
        permissions_module.ROLE_PERMISSIONS[permissions_module.UserRole.QC_MANAGER],
        permissions_module.ResourceType.QC_RESULTS,
    )
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)

    response = client_for(user_with(["qc_manager"])).get(SNAPSHOT_PATH, params=VALID_PARAMS)

    assert response.status_code == 403, response.text
    assert service.calls == []


# ------------------------------------------------------------------ 成功与调用契约


def test_snapshot_passes_verified_identity_and_recipient_id_only(monkeypatch):
    service = RecordingSnapshotService(result={"summary": {"total": 3}})
    install_service(monkeypatch, service)

    response = client_for(user_with(["qc_manager"], user_id="qc-reader-9")).get(
        SNAPSHOT_PATH, params=VALID_PARAMS
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {"summary": {"total": 3}}
    assert body["trace_id"]

    assert len(service.calls) == 1
    call = service.calls[0]
    assert len(call["args"]) == 1
    identity = call["args"][0]
    assert isinstance(identity, VerifiedQCIdentity)
    assert identity.columns() == {
        "identity_version": 1,
        "source_key": "coding_qc",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
    }
    # 现代主链只按三坐标 + source_key 取数，绝不接受 record_id 旧坐标。
    assert call["kwargs"] == {"recipient_id": "qc-reader-9"}


def test_legacy_record_id_query_is_ignored(monkeypatch):
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)

    response = client_for(user_with(["qc_manager"])).get(
        SNAPSHOT_PATH, params={**VALID_PARAMS, "record_id": "legacy-record-77"}
    )

    assert response.status_code == 200, response.text
    assert len(service.calls) == 1
    identity = service.calls[0]["args"][0]
    assert isinstance(identity, VerifiedQCIdentity)
    assert "legacy-record-77" not in str(identity.columns())
    assert "record_id" not in service.calls[0]["kwargs"]


def test_openapi_requires_four_identity_query_params():
    app = FastAPI()
    app.include_router(workstation.router)
    operation = app.openapi()["paths"][SNAPSHOT_PATH]["get"]

    parameters = {param["name"]: param for param in operation["parameters"]}
    assert {"institute_id", "patient_id", "visit_id", "source_key"} <= set(parameters)
    assert all(parameters[name].get("required") for name in VALID_PARAMS)
    assert _enum_values(parameters["source_key"]["schema"]) == SOURCE_KEYS


def _enum_values(schema: Dict[str, Any]) -> set[str]:
    values = set(schema.get("enum") or [])
    if "const" in schema:
        values.add(schema["const"])
    for branch in list(schema.get("anyOf") or []) + list(schema.get("oneOf") or []):
        values.update(branch.get("enum") or [])
        if "const" in branch:
            values.add(branch["const"])
    return values


# ------------------------------------------------------------------ 参数校验 422


@pytest.mark.parametrize("missing", sorted(VALID_PARAMS))
def test_missing_required_query_param_is_422(monkeypatch, missing):
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)
    params = {key: value for key, value in VALID_PARAMS.items() if key != missing}

    response = client_for(user_with(["qc_manager"])).get(SNAPSHOT_PATH, params=params)

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize("value", ["", "   ", " visit-1", "visit-1 "])
def test_blank_or_noncanonical_identity_is_masked_422(monkeypatch, value):
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)
    params = {**VALID_PARAMS, "visit_id": value}

    response = client_for(user_with(["qc_manager"])).get(SNAPSHOT_PATH, params=params)

    assert response.status_code == 422
    assert service.calls == []
    # 固定脱敏文案：既不回显原始身份值，也不带出下层异常细节。
    assert response.json()["detail"] == "病例身份参数不合法"
    if value.strip():
        assert value.strip() not in response.text


def test_unknown_source_key_is_422_before_service_call(monkeypatch):
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)
    params = {**VALID_PARAMS, "source_key": "record_id_lookup"}

    response = client_for(user_with(["qc_manager"])).get(SNAPSHOT_PATH, params=params)

    assert response.status_code == 422
    assert service.calls == []


# ------------------------------------------------------------------ 状态码映射


@pytest.mark.parametrize(
    ("error_name", "expected_status"),
    [
        ("CaseNotFound", 404),
        ("CaseIdentityAmbiguous", 409),
        ("SchemaUnavailable", 503),
        ("SourceUnavailable", 503),
    ],
)
def test_service_errors_map_to_declared_status(monkeypatch, error_name, expected_status):
    error_cls = getattr(modern_case_service, error_name)
    service = RecordingSnapshotService(error=error_cls(f"{PRIVATE_PATIENT} {PRIVATE_DSN}"))
    install_service(monkeypatch, service)

    response = client_for(user_with(["qc_manager"])).get(SNAPSHOT_PATH, params=VALID_PARAMS)

    assert response.status_code == expected_status, response.text
    assert len(service.calls) == 1
    assert PRIVATE_DSN not in response.text
    assert PRIVATE_PATIENT not in response.text


def test_unexpected_service_error_is_sanitized_503(monkeypatch, caplog):
    service = RecordingSnapshotService(error=RuntimeError(f"could not connect to {PRIVATE_DSN}"))
    install_service(monkeypatch, service)

    with caplog.at_level("ERROR", logger="app.routers.workstation"):
        response = client_for(user_with(["qc_manager"])).get(SNAPSHOT_PATH, params=VALID_PARAMS)

    assert response.status_code == 503, response.text
    assert len(service.calls) == 1
    assert PRIVATE_DSN not in response.text
    assert PRIVATE_DSN not in caplog.text


def test_service_collects_recipient_id_from_current_user(monkeypatch):
    service = RecordingSnapshotService()
    install_service(monkeypatch, service)
    user = user_with(["qc_manager"], user_id="")
    user["user_id"] = "legacy-id-7"

    response = client_for(user).get(SNAPSHOT_PATH, params=VALID_PARAMS)

    assert response.status_code == 200, response.text
    assert service.calls[0]["kwargs"] == {"recipient_id": "legacy-id-7"}


# ------------------------------------------------------------ 并发与线程池


async def _ticks_during(work) -> int:
    """统计 ``work`` 执行期间事件循环被让出的次数（10ms 一跳）。"""

    ticks = 0
    finished = False

    async def ticker() -> None:
        nonlocal ticks
        while not finished:
            ticks += 1
            await asyncio.sleep(TICK_SECONDS)

    task = asyncio.create_task(ticker())
    try:
        await work()
    finally:
        finished = True
        await task
    return ticks


async def _get_via_asgi(app: FastAPI):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(SNAPSHOT_PATH, params=VALID_PARAMS)


def app_for(user: Dict[str, Any]) -> FastAPI:
    app = FastAPI()
    app.include_router(workstation.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def test_snapshot_runs_service_on_worker_thread(monkeypatch):
    """同步 SQLAlchemy 读取必须离开事件循环线程（与耗时无关的确定性不变量）。"""

    service = RecordingSnapshotService(delay=SNAPSHOT_DELAY_SECONDS)
    install_service(monkeypatch, service)

    async def scenario():
        loop_thread = threading.get_ident()
        response = await _get_via_asgi(app_for(user_with(["qc_manager"])))
        return loop_thread, response

    loop_thread, response = asyncio.run(scenario())

    assert response.status_code == 200, response.text
    assert len(service.thread_ids) == 1
    assert service.thread_ids[0] != loop_thread


def test_event_loop_keeps_ticking_while_snapshot_reads(monkeypatch):
    """阻塞读取在线程池执行时，ticker 仍能持续获得调度。"""

    service = RecordingSnapshotService(delay=SNAPSHOT_DELAY_SECONDS)
    install_service(monkeypatch, service)

    async def scenario() -> int:
        return await _ticks_during(lambda: _get_via_asgi(app_for(user_with(["admin"]))))

    ticks = asyncio.run(scenario())

    # 0.2s 阻塞 / 10ms tick：真线程池执行时事件循环可跑十几次；
    # 若把同步调用内联进事件循环（见下一个反例），这里会掉到 0～1。
    assert ticks >= 5
    assert len(service.calls) == 1


def test_ticker_counterexample_detects_inline_blocking():
    """反例自检：同一 ticker 对“内联同步阻塞”只能得到极少 tick。"""

    def inline_blocking() -> None:
        time.sleep(SNAPSHOT_DELAY_SECONDS)

    async def blocking_work() -> None:
        inline_blocking()

    ticks = asyncio.run(_ticks_during(blocking_work))

    assert ticks <= 1
