from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def _load_openapi() -> dict:
    sys.path.insert(0, str(ROOT))
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/openapi.json")
        if resp.status_code != 200:
            raise RuntimeError(f"openapi endpoint failed: {resp.status_code}")
        return resp.json()


def _require_path(spec: dict, path: str, method: str) -> tuple[bool, str]:
    operation = spec.get("paths", {}).get(path, {}).get(method)
    ok = operation is not None
    return ok, f"[openapi] {method.upper()} {path}: {'OK' if ok else 'MISSING'}"


def _check_refresh_json_contract(spec: dict) -> tuple[bool, str]:
    op = spec.get("paths", {}).get("/api/v1/auth/refresh", {}).get("post", {})
    body = op.get("requestBody", {}).get("content", {})
    schema = body.get("application/json", {}).get("schema", {})
    has_json = "application/json" in body
    has_refresh_field = False
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        ref_schema = spec.get("components", {}).get("schemas", {}).get(ref, {})
        has_refresh_field = "refresh_token" in (ref_schema.get("properties") or {})
    else:
        has_refresh_field = "refresh_token" in (schema.get("properties") or {})
    ok = has_json and has_refresh_field
    return ok, (
        "[openapi] refresh contract: "
        f"{'OK' if ok else 'MISMATCH'} "
        f"(application/json={has_json}, refresh_token_field={has_refresh_field})"
    )


def _check_sync_security_declared(spec: dict) -> tuple[bool, str]:
    op = spec.get("paths", {}).get("/api/v1/sync/trigger", {}).get("post", {})
    security = op.get("security", [])
    ok = bool(security)
    return ok, f"[openapi] sync trigger security: {'OK' if ok else 'MISSING'}"


def main() -> int:
    try:
        spec = _load_openapi()
    except Exception as exc:
        print(f"[openapi] failed to load spec: {exc}")
        return 1

    checks: list[tuple[bool, str]] = []
    checks.append(_require_path(spec, "/api/v1/auth/login", "post"))
    checks.append(_require_path(spec, "/api/v1/auth/refresh", "post"))
    checks.append(_require_path(spec, "/api/v1/sync/trigger", "post"))
    checks.append(_require_path(spec, "/api/v1/sync/config/pg", "get"))
    checks.append(_require_path(spec, "/api/v1/sync/config/pg", "put"))
    checks.append(_check_refresh_json_contract(spec))
    checks.append(_check_sync_security_declared(spec))

    failed = [msg for ok, msg in checks if not ok]
    for _, msg in checks:
        print(msg)

    if failed:
        print("[openapi] failed checks:")
        for msg in failed:
            print(f"- {msg}")
        return 1

    print(
        "[openapi] PASS "
        + json.dumps(
            {
                "paths": len(spec.get("paths", {})),
                "schemas": len(spec.get("components", {}).get("schemas", {})),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
