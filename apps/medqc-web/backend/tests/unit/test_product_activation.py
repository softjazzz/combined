from __future__ import annotations

import json
import base64
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.routers import custom_qc, qc_sample_pools, qc_sichuan, sync
from app.services import product_activation
from app.services.product_activation import (
    ACTIVATION_PRODUCT,
    ProductActivationError,
    ProductActivationService,
    build_activation_code,
)


def _keypair(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_key, public_path


def _code(private_key, *, expires_days=30, **overrides):
    now = datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc)
    payload = {
        "version": "1",
        "product": ACTIVATION_PRODUCT,
        "customer": "演示医院",
        "edition": "customer",
        "serial": "DEMO-001",
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(days=expires_days)).isoformat().replace("+00:00", "Z"),
    }
    payload.update(overrides)
    return build_activation_code(private_key, payload)


def test_valid_code_activates_and_persists_only_safe_state(tmp_path):
    private_key, public_path = _keypair(tmp_path)
    service = ProductActivationService(
        required=True,
        state_path=tmp_path / "state.json",
        public_key_path=public_path,
        now=lambda: datetime(2026, 8, 20, tzinfo=timezone.utc),
    )

    result = service.activate(_code(private_key))

    assert result["status"] == "active"
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert set(saved) == {"activation_code", "activated_at", "payload"}
    assert saved["payload"]["customer"] == "演示医院"
    assert "private" not in json.dumps(saved)
    assert service.status()["status"] == "active"


def test_explicit_offline_activation_does_not_load_application_settings(tmp_path, monkeypatch):
    def unavailable_settings():
        raise RuntimeError("离线发行环境没有应用配置")

    monkeypatch.setattr(product_activation, "get_settings", unavailable_settings)
    private_key, public_path = _keypair(tmp_path)
    state_path = tmp_path / "offline-state.json"
    service = ProductActivationService(
        required=True,
        state_path=state_path,
        public_key_path=public_path,
        now=lambda: datetime(2026, 8, 20, tzinfo=timezone.utc),
    )

    activation_code = _code(private_key)
    assert service.activate(activation_code)["status"] == "active"
    assert json.loads(state_path.read_text(encoding="utf-8"))["activation_code"] == activation_code
    assert service.status()["status"] == "active"
    service.enforce()


@pytest.mark.parametrize("explicit_field", [None, "required", "state_path"])
def test_missing_activation_options_use_application_settings(tmp_path, monkeypatch, explicit_field):
    configured_path = tmp_path / "configured-state.json"
    settings = SimpleNamespace(
        PRODUCT_ACTIVATION_REQUIRED=True,
        PRODUCT_ACTIVATION_STATE_PATH=str(configured_path),
    )
    calls = []

    def application_settings():
        calls.append(True)
        return settings

    monkeypatch.setattr(product_activation, "get_settings", application_settings)
    options = {}
    if explicit_field == "required":
        options["required"] = False
    elif explicit_field == "state_path":
        options["state_path"] = tmp_path / "explicit-state.json"

    service = ProductActivationService(**options)

    assert calls == [True]
    assert service.required is (explicit_field != "required")
    assert service.state_path == options.get("state_path", configured_path)


@pytest.mark.parametrize(
    "overrides",
    [
        {"product": "other-product"},
        {"expires_at": "2026-08-19T00:00:00Z"},
        {"customer": ""},
    ],
)
def test_invalid_code_is_rejected_without_replacing_previous_active_state(tmp_path, overrides):
    private_key, public_path = _keypair(tmp_path)
    state_path = tmp_path / "state.json"
    service = ProductActivationService(
        required=True,
        state_path=state_path,
        public_key_path=public_path,
        now=lambda: datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    valid = _code(private_key)
    service.activate(valid)

    with pytest.raises(ProductActivationError):
        service.activate(_code(private_key, **overrides))

    assert service.status()["status"] == "active"
    assert json.loads(state_path.read_text(encoding="utf-8"))["activation_code"] == valid


def test_required_false_always_allows_and_required_true_missing_or_expired_denies(tmp_path):
    private_key, public_path = _keypair(tmp_path)
    def now():
        return datetime(2026, 8, 20, tzinfo=timezone.utc)
    missing = ProductActivationService(
        required=True, state_path=tmp_path / "missing.json", public_key_path=public_path, now=now
    )
    assert missing.status()["status"] == "missing"
    with pytest.raises(ProductActivationError):
        missing.enforce()

    expired = ProductActivationService(
        required=True, state_path=tmp_path / "expired.json", public_key_path=public_path, now=now
    )
    with pytest.raises(ProductActivationError):
        expired.activate(_code(private_key, expires_days=-1))

    optional = ProductActivationService(
        required=False, state_path=tmp_path / "optional.json", public_key_path=public_path, now=now
    )
    optional.enforce()
    assert optional.status()["status"] == "not_required"


def test_payload_has_exact_fields_and_rejects_tampering(tmp_path):
    private_key, public_path = _keypair(tmp_path)
    service = ProductActivationService(
        required=True, state_path=tmp_path / "state.json", public_key_path=public_path
    )
    valid = _code(private_key)
    prefix, payload_part, signature = valid.split(".")
    tampered_payload = payload_part[:-1] + ("A" if payload_part[-1] != "A" else "B")
    with pytest.raises(ProductActivationError):
        service.activate(f"{prefix}.{tampered_payload}.{signature}")

    extra = _code(private_key, extra_field="nope")
    with pytest.raises(ProductActivationError):
        service.activate(extra)

    base_payload = {
        "version": "1",
        "product": ACTIVATION_PRODUCT,
        "customer": "演示医院",
        "edition": "customer",
        "serial": "DEMO-001",
        "issued_at": "2026-08-19T08:00:00Z",
        "expires_at": "2026-09-19T08:00:00Z",
    }
    missing_field = dict(base_payload)
    missing_field.pop("serial")
    invalid_type = {**base_payload, "customer": True}
    for payload in (missing_field, invalid_type):
        with pytest.raises(ProductActivationError):
            service.activate(build_activation_code(private_key, payload))


def test_signed_but_noncanonical_payload_encoding_is_rejected(tmp_path):
    private_key, public_path = _keypair(tmp_path)
    service = ProductActivationService(
        required=True,
        state_path=tmp_path / "state.json",
        public_key_path=public_path,
        now=lambda: datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    payload = {
        "version": "1",
        "product": ACTIVATION_PRODUCT,
        "customer": "演示医院",
        "edition": "customer",
        "serial": "DEMO-001",
        "issued_at": "2026-08-19T08:00:00Z",
        "expires_at": "2026-09-19T08:00:00Z",
    }
    noncanonical_json = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    ).encode("utf-8")
    payload_part = base64.urlsafe_b64encode(noncanonical_json).rstrip(b"=").decode("ascii")
    message = f"MQ1.{payload_part}".encode("ascii")
    signature = base64.urlsafe_b64encode(private_key.sign(message)).rstrip(b"=").decode("ascii")

    with pytest.raises(ProductActivationError, match="编码"):
        service.activate(f"MQ1.{payload_part}.{signature}")


def test_issuer_can_write_bootstrap_state_without_printing_activation_code(tmp_path):
    _, public_path = _keypair(tmp_path)
    private_path = tmp_path / "private.pem"
    state_path = tmp_path / "product_activation_bootstrap.json"
    issuer_script = Path(__file__).resolve().parents[3] / "scripts" / "generate_medqc_activation_code.py"
    expires_at = (datetime.now(timezone.utc) + timedelta(days=100)).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")

    completed = subprocess.run(
        [
            sys.executable,
            str(issuer_script),
            "--private-key",
            str(private_path),
            "--public-key",
            str(public_path),
            "--customer",
            "三个月预激活验收",
            "--edition",
            "trial",
            "--serial",
            "TRIAL-TEST-001",
            "--expires-at",
            expires_at,
            "--state-output",
            str(state_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    assert state_path.is_file()
    assert "MQ1." not in (completed.stdout or "")
    assert "MQ1." not in (completed.stderr or "")
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["payload"]["customer"] == "三个月预激活验收"
    assert saved["payload"]["expires_at"] == expires_at
    service = ProductActivationService(
        required=True,
        state_path=state_path,
        public_key_path=public_path,
    )
    assert service.status()["status"] == "active"


def test_activation_api_is_readable_by_logged_in_user_but_write_is_admin_only(client):
    admin = client.post("/api/v1/auth/login", json={"email": "admin@medqc.com", "password": "admin888"})
    doctor = client.post("/api/v1/auth/login", json={"email": "doctor@medqc.com", "password": "doctor123"})
    assert admin.status_code == 200
    assert doctor.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin.json()['data']['access_token']}"}
    doctor_headers = {"Authorization": f"Bearer {doctor.json()['data']['access_token']}"}

    read_response = client.get("/api/v1/product-activation/status", headers=doctor_headers)
    assert read_response.status_code == 200
    assert read_response.json()["data"]["status"] == "not_required"

    write_response = client.post(
        "/api/v1/product-activation/activate",
        headers=doctor_headers,
        json={"activation_code": "not-a-real-code"},
    )
    assert write_response.status_code == 403

    invalid_admin_response = client.post(
        "/api/v1/product-activation/activate",
        headers=admin_headers,
        json={"activation_code": "not-a-real-code"},
    )
    assert invalid_admin_response.status_code == 422


def test_new_work_creation_routes_have_activation_gate(app):
    from app.services.product_activation import require_product_activation

    expected = {
        ("POST", "/api/v1/qc/sichuan/workspace/batch-jobs"),
        ("POST", "/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/retry"),
        ("POST", "/api/v1/qc/sample-pools/{pool_id}/run"),
        ("POST", "/api/v1/sync/trigger"),
    }
    for route in app.routes:
        methods = getattr(route, "methods", set())
        key = next(((method, route.path) for method in methods if (method, route.path) in expected), None)
        if key is None:
            continue
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert require_product_activation in dependency_calls, key


def test_missing_required_activation_locks_all_new_work_before_business_services(
    client,
    app,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@medqc.com", "password": "admin888"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    monkeypatch.setenv("PRODUCT_ACTIVATION_REQUIRED", "true")
    monkeypatch.setenv(
        "PRODUCT_ACTIVATION_STATE_PATH", str(tmp_path / "missing-activation.json")
    )

    calls = {
        "qc_service": 0,
        "workspace": 0,
        "sample_pool": 0,
        "sync": 0,
        "custom_workspace": 0,
    }

    async def _forbidden_qc_service():
        calls["qc_service"] += 1
        raise AssertionError("激活门禁前不得创建质控服务")

    def _forbidden_workspace():
        calls["workspace"] += 1
        raise AssertionError("激活门禁前不得访问任务存储")

    def _forbidden_sample_pool():
        calls["sample_pool"] += 1
        raise AssertionError("激活门禁前不得访问样本池服务")

    def _forbidden_sync(*_args, **_kwargs):
        calls["sync"] += 1
        raise AssertionError("激活门禁前不得创建同步任务")

    def _forbidden_custom_workspace():
        calls["custom_workspace"] += 1
        raise AssertionError("激活门禁前不得访问自定义质控任务存储")

    app.dependency_overrides[qc_sichuan.get_qc_service] = _forbidden_qc_service
    app.dependency_overrides[custom_qc.get_workspace_service] = _forbidden_custom_workspace
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", _forbidden_workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", _forbidden_sample_pool)
    monkeypatch.setattr(sync, "enforce_rate_limit", _forbidden_sync)
    try:
        responses = (
            client.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                headers=headers,
                json={"rule_set_key": "luxian_0609_qc_v1", "scope": "running"},
            ),
            client.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs/job-never-created/retry",
                headers=headers,
            ),
            client.post(
                "/api/v1/qc/sample-pools/pool-never-read/run",
                headers=headers,
                json={},
            ),
            client.post(
                "/api/v1/sync/trigger",
                headers=headers,
                json={"source": "pg", "tier": "all"},
            ),
            client.post(
                "/api/v1/custom-qc/workspace/batch-jobs",
                headers=headers,
                json={},
            ),
            client.post(
                "/api/v1/custom-qc/workspace/batch-jobs/job-never-created/retry",
                headers=headers,
            ),
        )
    finally:
        app.dependency_overrides.pop(qc_sichuan.get_qc_service, None)
        app.dependency_overrides.pop(custom_qc.get_workspace_service, None)

    assert [response.status_code for response in responses] == [423, 423, 423, 423, 423, 423]
    assert all(response.headers["X-Product-Activation"] == "missing" for response in responses)
    assert calls == {
        "qc_service": 0,
        "workspace": 0,
        "sample_pool": 0,
        "sync": 0,
        "custom_workspace": 0,
    }


@pytest.mark.asyncio
async def test_activation_dependency_allows_new_work_when_requirement_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services.product_activation import require_product_activation

    monkeypatch.setenv("PRODUCT_ACTIVATION_REQUIRED", "false")

    current_user = {"id": "admin-user"}
    assert await require_product_activation(current_user) is current_user
