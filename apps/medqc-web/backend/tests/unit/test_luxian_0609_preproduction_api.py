from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import luxian_0609_preproduction
from app.services.luxian_0609 import evidence_snapshot_provider, execution
from app.services.luxian_0609 import preproduction_bundle_reader
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows


@pytest.fixture(autouse=True)
def _stub_preproduction_auth(monkeypatch):
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "resolve_current_user_from_token",
        lambda _token: {"id": "api-test-user"},
    )


def _build_client(*, enabled: bool) -> TestClient:
    app = FastAPI()
    app.include_router(luxian_0609_preproduction.router)
    app.dependency_overrides[
        luxian_0609_preproduction._settings_dependency
    ] = lambda: SimpleNamespace(LUXIAN_0609_PREPRODUCTION_API_ENABLED=enabled)
    client = TestClient(app)
    client.headers.update({"Authorization": "Bearer safe-test-token"})
    return client


def _request_body() -> dict:
    return {
        "scene": "running",
        "institute_id": "institute-safe-coordinate",
        "patient_id": "patient-safe-coordinate",
        "visit_id": "visit-safe-coordinate",
        "selected_customer_rule_ids": ["LX0609-007", "LX0609-008"],
        "evaluation_as_of_date": "2026-07-17",
    }


@pytest.mark.unit
def test_preproduction_api_flag_off_returns_404_before_client_or_runner(
    monkeypatch,
) -> None:
    calls = {"auth_db": 0, "loader": 0, "client": 0, "runner": 0}

    def resolve_user(_token):
        calls["auth_db"] += 1
        raise AssertionError("auth DB must not be called")

    def load_bundle(**_kwargs):
        calls["loader"] += 1
        raise AssertionError("loader must not be called")

    def build_client():
        calls["client"] += 1
        raise AssertionError("client must not be built")

    async def run_runner(**_kwargs):
        calls["runner"] += 1
        raise AssertionError("runner must not be called")

    monkeypatch.setattr(luxian_0609_preproduction, "_build_llm_client", build_client)
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "resolve_current_user_from_token",
        resolve_user,
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        load_bundle,
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "run_luxian_0609_preproduction",
        run_runner,
    )

    with _build_client(enabled=False) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=_request_body(),
        )

    assert response.status_code == 404
    assert calls == {"auth_db": 0, "loader": 0, "client": 0, "runner": 0}
    assert luxian_0609_preproduction.router.dependencies == []


@pytest.mark.unit
def test_preproduction_api_flag_off_does_not_parse_sensitive_malformed_body(
    monkeypatch,
    caplog,
) -> None:
    sensitive = "raw body Bearer_secret 13800138000"
    calls = {"auth_db": 0, "loader": 0, "client": 0, "runner": 0}

    def resolve_user(_token):
        calls["auth_db"] += 1
        raise AssertionError("auth DB must not be called")

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "resolve_current_user_from_token",
        resolve_user,
    )

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        lambda **_kwargs: calls.__setitem__("loader", calls["loader"] + 1),
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "_build_llm_client",
        lambda: calls.__setitem__("client", calls["client"] + 1),
    )

    async def run_runner(**_kwargs):
        calls["runner"] += 1

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "run_luxian_0609_preproduction",
        run_runner,
    )

    with _build_client(enabled=False) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            content=f'{{"bundle":"{sensitive}"',
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 404
    assert calls == {"auth_db": 0, "loader": 0, "client": 0, "runner": 0}
    assert sensitive not in response.text
    assert sensitive not in caplog.text


@pytest.mark.unit
def test_preproduction_api_requires_authenticated_user() -> None:
    app = FastAPI()
    app.include_router(luxian_0609_preproduction.router)
    app.dependency_overrides[
        luxian_0609_preproduction._settings_dependency
    ] = lambda: SimpleNamespace(LUXIAN_0609_PREPRODUCTION_API_ENABLED=True)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=_request_body(),
        )

    assert response.status_code in {401, 403}


@pytest.mark.unit
def test_preproduction_api_enabled_passes_exact_safe_contract_once(monkeypatch) -> None:
    fake_client = SimpleNamespace(model="model-for-preproduction")
    base_settings = SimpleNamespace(LUXIAN_0609_PREPRODUCTION_API_ENABLED=True)
    captured = {"settings": 0, "auth_db": 0, "loader": 0, "client": 0, "runner": 0}

    def settings_dependency():
        captured["settings"] += 1
        return base_settings

    def resolve_user(token):
        captured["auth_db"] += 1
        assert token == "safe-test-token"
        return {"id": "authenticated-user"}

    def load_bundle(**kwargs):
        captured["loader"] += 1
        captured["loader_kwargs"] = kwargs
        return {"scene": "running", "documents": {}}

    def build_client():
        captured["client"] += 1
        return fake_client

    async def run_runner(**kwargs):
        from app.services.llm_observability import current_llm_observation_context

        captured["runner"] += 1
        captured["kwargs"] = kwargs
        captured["observation_context"] = current_llm_observation_context()
        return {
            "schema_version": "lx0609-preproduction-runner-v1",
            "results": [{"rule_id": "LX0609-007", "status": "compliant"}],
            "metrics": {"total_tokens": 0},
        }

    monkeypatch.setattr(luxian_0609_preproduction, "_build_llm_client", build_client)
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "resolve_current_user_from_token",
        resolve_user,
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        load_bundle,
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "run_luxian_0609_preproduction",
        run_runner,
    )
    with _build_client(enabled=True) as client:
        client.app.dependency_overrides[
            luxian_0609_preproduction._settings_dependency
        ] = settings_dependency
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=_request_body(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "lx0609-preproduction-runner-v1",
        "results": [{"rule_id": "LX0609-007", "status": "compliant"}],
        "metrics": {"total_tokens": 0},
    }
    assert captured["settings"] == 1
    assert captured["auth_db"] == 1
    assert captured["loader"] == 1
    assert captured["client"] == 1
    assert captured["runner"] == 1
    assert captured["observation_context"].business_scene == "luxian_0609_preproduction"
    assert captured["observation_context"].record_key_hash
    assert captured["observation_context"].executor_key == "preproduction_adjudicator"
    assert captured["loader_kwargs"] == {
        "scene": "running",
        "institute_id": "institute-safe-coordinate",
        "patient_id": "patient-safe-coordinate",
        "visit_id": "visit-safe-coordinate",
        "schema": "public",
    }
    assert captured["kwargs"] == {
        "bundle": {"scene": "running", "documents": {}},
        "selected_customer_rule_ids": ["LX0609-007", "LX0609-008"],
        "evaluation_as_of_date": "2026-07-17",
        "llm_client": fake_client,
        "base_settings": base_settings,
        "model_name": "model-for-preproduction",
    }


@pytest.mark.unit
def test_preproduction_api_exam_lab_typed_entry_isolated_to_selected_rules(
    monkeypatch,
    caplog,
) -> None:
    """公共旁路只执行所选010-015 typed规则，不派发旧映射或其他客户规则。"""

    selected = (
        "LX0609-010",
        "LX0609-011",
        "LX0609-012",
        "LX0609-014",
        "LX0609-015",
    )
    captured: dict[str, object] = {"executor_calls": 0, "llm_calls": 0}

    class _ControlledFactClient:
        model = "controlled-test-model"

        async def generate(self, prompt):
            captured["llm_calls"] = int(captured["llm_calls"]) + 1
            response_payload = json.loads(prompt.strip().splitlines()[-1])
            for fact in response_payload["facts"]:
                rule_id = fact["rule_id"]
                fact["applicability"] = "applicable"
                fact["semantic_state"] = "present"
                fact["positive_state"] = (
                    "positive"
                    if rule_id in {"LX0609-012", "LX0609-015"}
                    else "not_relevant"
                )
                fact["course_doc_positions"] = [
                    1 if rule_id == "LX0609-010" else 2
                ]
            return {
                "choices": [{"message": {"content": json.dumps({
                    "schema_version": response_payload["schema_version"],
                    "facts": response_payload["facts"],
                }, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
                "_api_time": 0.1,
            }

    real_build_session = evidence_snapshot_provider.build_luxian_0609_evidence_read_session

    def build_session(**kwargs):
        rows_by_source = {
            "exam_master": ({
                "exam_name": "胸部CT",
                "exam_type": "CT",
                "exam_time": "2026-04-26 08:00:00",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "右肺占位，考虑恶性，建议进一步处理。",
            },),
            "labtest_master": ({
                "labtest_subject": "血培养及药敏",
                "specimen": "血液",
                "report_time": "2026-04-26 12:00:00",
                "result": "培养阳性，药敏结果已报告。",
            },),
            "daily_course_record": (
                {
                    "record_time": "2026-04-26 07:00:00",
                    "record_content": "因持续咳嗽伴胸痛，为明确肺部病因拟行胸部CT检查。",
                },
                {
                    "record_time": "2026-04-26 13:00:00",
                    "record_content": (
                        "已查看胸部CT报告并分析肺部占位的后续处理；"
                        "同时复核血培养阳性和药敏结果并调整抗感染方案。"
                    ),
                },
            ),
            "inpat_registration.discharge_horizon": ({
                "discharge_datetime": "2026-04-30 12:00:00",
            },),
        }

        def controlled_reader(**reader_kwargs):
            source_key = reader_kwargs["source_key"]
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=rows_by_source.get(source_key, ()),
                truncated=False,
                limit_rows=50,
            )

        return real_build_session(**kwargs, row_reader=controlled_reader)

    real_executor = execution.execute_luxian_0609_native_exam_lab_rules

    async def execute_exam_lab(**kwargs):
        # 透明观测 spy：不改变 executor 输入或返回值，真实 reducer/aggregator
        # 仍由公共 HTTP 路径完成。
        captured["executor_calls"] = int(captured["executor_calls"]) + 1
        captured["rule_ids"] = tuple(kwargs["rule_ids"])
        captured["decision_rule_ids"] = tuple(kwargs["decision_rule_ids"])
        captured["has_snapshot"] = kwargs["evidence_snapshot"] is not None
        captured["has_materials"] = kwargs["evidence_materials"] is not None
        result = await real_executor(**kwargs)
        captured["decision_count"] = len(result.decisions)
        captured["raw_result_count"] = len(result.results)
        return result

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        lambda **_: {
            "scene": "running",
            "institute_id": "institute-safe-coordinate",
            "patient_id": "patient-safe-coordinate",
            "visit_id": "visit-safe-coordinate",
            "structured_context": {"documents": {}},
        },
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "_build_llm_client",
        _ControlledFactClient,
    )
    monkeypatch.setattr(
        execution,
        "build_luxian_0609_evidence_read_session",
        build_session,
    )
    monkeypatch.setattr(
        execution,
        "execute_luxian_0609_native_exam_lab_rules",
        execute_exam_lab,
    )

    request_body = {
        "scene": "running",
        "institute_id": "institute-safe-coordinate",
        "patient_id": "patient-safe-coordinate",
        "visit_id": "visit-safe-coordinate",
        "selected_customer_rule_ids": list(selected),
        "evaluation_as_of_date": "2026-07-19",
    }
    with _build_client(enabled=True) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=request_body,
        )

    assert response.status_code == 200
    payload = response.json()
    assert tuple(item["rule_id"] for item in payload["results"]) == selected
    assert {item["status"] for item in payload["results"]} == {"compliant"}, [
        (
            item.get("rule_id"),
            item.get("status"),
            (item.get("metadata") or {}).get("reason_code"),
        )
        for item in payload["results"]
    ]
    assert payload["metrics"]["customer_rule_count"] == 5
    assert payload["metrics"]["legacy_projection_count"] == 0
    assert payload["metrics"]["llm_call_count"] == 1
    rendered = repr(payload) + caplog.text
    for private_marker in (
        "institute-safe-coordinate",
        "patient-safe-coordinate",
        "visit-safe-coordinate",
        "右肺占位",
        "血培养阳性",
        "持续咳嗽伴胸痛",
        "2026-04-26 08:00:00",
        "evidence_payload",
        "fact_refs",
    ):
        assert private_marker not in rendered
    assert captured == {
        "executor_calls": 1,
        "llm_calls": 1,
        "rule_ids": selected,
        "decision_rule_ids": selected,
        "has_snapshot": True,
        "has_materials": True,
        "decision_count": 5,
        "raw_result_count": 0,
    }


@pytest.mark.unit
@pytest.mark.parametrize("error_type", [ValueError, TypeError])
def test_preproduction_api_runner_contract_errors_are_safe_422(
    monkeypatch,
    error_type,
) -> None:
    sensitive = "raw SQL Bearer_secret 13800138000"

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "_build_llm_client",
        lambda: SimpleNamespace(model="safe-model"),
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        lambda **_kwargs: {"scene": "running", "documents": {}},
    )

    async def run_runner(**_kwargs):
        raise error_type(sensitive)

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "run_luxian_0609_preproduction",
        run_runner,
    )

    with _build_client(enabled=True) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=_request_body(),
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "准生产评估请求不符合安全契约"}
    assert sensitive not in response.text


@pytest.mark.unit
def test_preproduction_api_rejects_uploaded_bundle_and_source_schema_without_echo(
    caplog,
) -> None:
    sensitive = "raw SQL Bearer_secret 13800138000"
    body = {
        **_request_body(),
        "bundle": {"record_content": sensitive},
        "source_schema": sensitive,
    }

    with _build_client(enabled=True) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=body,
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "准生产评估请求不符合安全契约"}
    assert sensitive not in response.text
    assert sensitive not in caplog.text


@pytest.mark.unit
@pytest.mark.parametrize(
    "invalid_field",
    [
        {"patient_id": {"raw": "raw SQL Bearer_secret 13800138000"}},
        {"visit_id": "raw SQL Bearer_secret 13800138000" * 20},
        {"selected_customer_rule_ids": "raw SQL Bearer_secret 13800138000"},
        {"evaluation_as_of_date": {"raw": "raw SQL Bearer_secret 13800138000"}},
    ],
)
def test_preproduction_api_validation_is_safe_and_stops_before_loader(
    monkeypatch,
    caplog,
    invalid_field,
) -> None:
    sensitive = "raw SQL Bearer_secret 13800138000"
    loader_calls = 0

    def load_bundle(**_kwargs):
        nonlocal loader_calls
        loader_calls += 1
        raise AssertionError("loader must not be called")

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        load_bundle,
    )
    body = {**_request_body(), **invalid_field}

    with _build_client(enabled=True) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=body,
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "准生产评估请求不符合安全契约"}
    assert sensitive not in response.text
    assert sensitive not in caplog.text
    assert loader_calls == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("loader_error", "expected_status", "expected_detail"),
    [
        (LookupError("raw coordinate 13800138000"), 404, "准生产病例包不存在"),
        (RuntimeError("raw SQL Bearer_secret 13800138000"), 503, "准生产病例包暂不可用"),
    ],
)
def test_preproduction_api_loader_failure_is_safe_and_stops_downstream(
    monkeypatch,
    loader_error,
    expected_status,
    expected_detail,
) -> None:
    calls = {"client": 0, "runner": 0}

    def load_bundle(**_kwargs):
        raise loader_error

    def build_client():
        calls["client"] += 1
        raise AssertionError("client must not be built")

    async def run_runner(**_kwargs):
        calls["runner"] += 1
        raise AssertionError("runner must not be called")

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        load_bundle,
    )
    monkeypatch.setattr(luxian_0609_preproduction, "_build_llm_client", build_client)
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "run_luxian_0609_preproduction",
        run_runner,
    )

    with _build_client(enabled=True) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=_request_body(),
        )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert "13800138000" not in response.text
    assert "Bearer_secret" not in response.text
    assert calls == {"client": 0, "runner": 0}


@pytest.mark.unit
def test_preproduction_api_client_factory_failure_is_safe_503(monkeypatch) -> None:
    sensitive = "raw config Bearer_secret 13800138000"
    runner_calls = 0

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        lambda **_kwargs: {"scene": "running", "documents": {}},
    )

    def build_client():
        raise RuntimeError(sensitive)

    async def run_runner(**_kwargs):
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("runner must not be called")

    monkeypatch.setattr(luxian_0609_preproduction, "_build_llm_client", build_client)
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "run_luxian_0609_preproduction",
        run_runner,
    )

    with _build_client(enabled=True) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=_request_body(),
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "准生产评估服务暂不可用"}
    assert sensitive not in response.text
    assert runner_calls == 0


@pytest.mark.unit
def test_preproduction_api_unknown_runner_failure_is_safe_503(
    monkeypatch,
    caplog,
) -> None:
    sensitive = "raw bundle coordinate Bearer_secret 13800138000"
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        lambda **_kwargs: {"scene": "running", "documents": {}},
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "_build_llm_client",
        lambda: SimpleNamespace(model="safe-model"),
    )

    async def run_runner(**_kwargs):
        raise RuntimeError(sensitive)

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "run_luxian_0609_preproduction",
        run_runner,
    )

    with _build_client(enabled=True) as client:
        response = client.post(
            "/api/v1/qc/luxian-0609/preproduction/evaluate",
            json=_request_body(),
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "准生产评估服务暂不可用"}
    assert sensitive not in response.text
    assert sensitive not in caplog.text


@pytest.mark.unit
def test_preproduction_router_is_registered_and_statically_isolated_from_old_chain() -> None:
    from app.main import create_app

    def collect_paths(routes):
        paths = set()
        for route in routes:
            path = getattr(route, "path", None)
            if path:
                paths.add(path)
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                paths.update(collect_paths(original_router.routes))
        return paths

    paths = collect_paths(create_app().routes)
    assert "/api/v1/qc/luxian-0609/preproduction/evaluate" in paths

    source = inspect.getsource(luxian_0609_preproduction)
    assert "sichuan_qc_service" not in source.lower()
    assert "qc_sichuan" not in source.lower()
    assert "load_or_assemble" not in source.lower()
    assert "refresh" not in source.lower()
    assert "persist" not in source.lower()


@pytest.mark.unit
def test_main_app_defers_auth_until_preproduction_flag_is_enabled(monkeypatch) -> None:
    from app import main as main_module
    from app.core import access_control

    auth_calls = 0

    def resolve_user(token):
        nonlocal auth_calls
        auth_calls += 1
        assert token == "safe-main-token"
        return {"id": "authenticated-user"}

    monkeypatch.setattr(access_control, "resolve_current_user_from_token", resolve_user)
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "resolve_current_user_from_token",
        resolve_user,
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "load_running_final_bundle",
        lambda **_kwargs: {"scene": "running", "documents": {}},
    )
    monkeypatch.setattr(
        luxian_0609_preproduction,
        "_build_llm_client",
        lambda: SimpleNamespace(model="safe-model"),
    )

    async def run_runner(**_kwargs):
        return {"schema_version": "safe-v1", "results": [], "metrics": {}}

    monkeypatch.setattr(
        luxian_0609_preproduction,
        "run_luxian_0609_preproduction",
        run_runner,
    )

    off_app = main_module.create_app()
    off_app.dependency_overrides[
        luxian_0609_preproduction._settings_dependency
    ] = lambda: SimpleNamespace(LUXIAN_0609_PREPRODUCTION_API_ENABLED=False)
    off_client = TestClient(off_app)
    off_response = off_client.post(
        "/api/v1/qc/luxian-0609/preproduction/evaluate",
        json=_request_body(),
        headers={"Authorization": "Bearer safe-main-token"},
    )
    off_client.close()
    assert off_response.status_code == 404
    assert auth_calls == 0

    on_app = main_module.create_app()
    on_app.dependency_overrides[
        luxian_0609_preproduction._settings_dependency
    ] = lambda: SimpleNamespace(LUXIAN_0609_PREPRODUCTION_API_ENABLED=True)
    on_client = TestClient(on_app)
    no_token_response = on_client.post(
        "/api/v1/qc/luxian-0609/preproduction/evaluate",
        json=_request_body(),
    )
    assert no_token_response.status_code == 401
    assert auth_calls == 0

    valid_response = on_client.post(
        "/api/v1/qc/luxian-0609/preproduction/evaluate",
        json=_request_body(),
        headers={"Authorization": "Bearer safe-main-token"},
    )
    on_client.close()
    assert valid_response.status_code == 200
    assert auth_calls == 1


class _FakeMappings:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return _FakeMappings(self._row)


class _FakeConnection:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params):
        self.owner.calls.append((str(statement), dict(params)))
        return _FakeResult(self.owner.row)


class _FakeEngine:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def connect(self):
        return _FakeConnection(self)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("scene", "expected_table"),
    [("running", "running_record_bundle"), ("final", "final_record_bundle")],
)
def test_preproduction_bundle_reader_is_one_bounded_select_with_json_parsing(
    monkeypatch,
    scene,
    expected_table,
) -> None:
    engine = _FakeEngine(
        {
            "institute_id": "i-safe",
            "patient_id": "p-safe",
            "visit_id": "v-safe",
            "scene": scene,
            "department": "外科",
            "admission_datetime": None,
            "discharge_datetime": None,
            "medical_text": "internal-only",
            "structured_context": '{"facts": []}',
            "document_hits": '[{"source_table": "daily_course_record"}]',
            "text_available": True,
            "data_quality_flags": '{"missing": []}',
            "source_doc_priority": '["daily_course_record"]',
            "compat_strategy": "v1",
            "bundle_schema_version": "v1",
            "policy_version": "v1",
            "bundle_updated_at": None,
        }
    )
    monkeypatch.setattr(preproduction_bundle_reader, "engine", engine)

    result = preproduction_bundle_reader.read_luxian_0609_preproduction_bundle(
        scene=scene,
        institute_id="i-safe",
        patient_id="p-safe",
        visit_id="v-safe",
    )

    assert len(engine.calls) == 1
    sql, params = engine.calls[0]
    normalized_sql = " ".join(sql.split()).lower()
    assert normalized_sql.startswith("select ")
    assert "select *" not in normalized_sql
    assert expected_table in normalized_sql
    unexpected_table = (
        "final_record_bundle" if scene == "running" else "running_record_bundle"
    )
    assert unexpected_table not in normalized_sql
    assert "limit 1" in normalized_sql
    assert all(
        token not in normalized_sql
        for token in (
            " insert ",
            " update ",
            " delete ",
            " drop ",
            " alter ",
            " create ",
            " truncate ",
        )
    )
    assert params == {
        "institute_id": "i-safe",
        "patient_id": "p-safe",
        "visit_id": "v-safe",
    }
    assert result["structured_context"] == {"facts": []}
    assert result["document_hits"] == [{"source_table": "daily_course_record"}]
    assert result["data_quality_flags"] == {"missing": []}
    assert result["source_doc_priority"] == ["daily_course_record"]


@pytest.mark.unit
def test_preproduction_bundle_reader_source_statically_forbids_mutation_and_assembly() -> None:
    assert preproduction_bundle_reader._PROJECTION == (
        "institute_id",
        "patient_id",
        "visit_id",
        "scene",
        "department",
        "admission_datetime",
        "discharge_datetime",
        "medical_text",
        "structured_context",
        "document_hits",
        "text_available",
        "data_quality_flags",
        "source_doc_priority",
        "compat_strategy",
        "bundle_schema_version",
        "policy_version",
        "bundle_updated_at",
    )
    source = inspect.getsource(preproduction_bundle_reader).lower()
    for forbidden in (
        "load_or_assemble",
        "assemble_",
        "force_refresh",
        "insert ",
        "update ",
        "delete ",
        " upsert",
        " drop ",
        " alter ",
        " create ",
        " truncate ",
    ):
        assert forbidden not in source
