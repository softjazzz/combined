"""独立同步服务应用层适配器；固定部署端点、零隐式重试，不读取临床正文。"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
import hashlib
import json
import os
import re
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx

from .data_pipeline_settings import PipelineError

MAX_RESPONSE_BYTES = 1024 * 1024
TOTAL_REQUEST_TIMEOUT = 15
JOB_STATES = {"queued", "running", "recovery_required", "succeeded", "completed_with_source_limitations", "failed", "cancelled"}


def deployment() -> tuple[str, str, str]:
    url = os.getenv("SYNC_CONTROL_API_URL", "").strip().rstrip("/")
    token = os.getenv("SYNC_CONTROL_API_TOKEN", "").strip()
    profile = os.getenv("SYNC_CONTROL_PROFILE", "accepted_manual").strip()
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"} or not parsed.port and parsed.netloc.endswith(":")):
            raise ValueError
        if not token or any(ord(c) < 33 or ord(c) == 127 for c in token):
            raise ValueError
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", profile):
            raise ValueError
    except ValueError:
        raise PipelineError("sync_control_deployment_not_configured") from None
    return url, token, profile


async def request(method: str, path: str, *, payload: dict | None = None, key: str | None = None) -> dict:
    try:
        return await asyncio.wait_for(_request_once(method, path, payload=payload, key=key), TOTAL_REQUEST_TIMEOUT)
    except asyncio.TimeoutError:
        raise PipelineError("sync_control_timeout_submission_may_be_accepted", 504) from None


async def _request_once(method: str, path: str, *, payload: dict | None = None, key: str | None = None) -> dict:
    url, token, _ = deployment()
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=3, write=5, pool=3),
            trust_env=False, follow_redirects=False,
        ) as client:
            async with client.stream(method, url + path, json=payload, headers=headers) as response:
                if response.status_code >= 300:
                    mapped = response.status_code if response.status_code in {403, 404, 409, 422, 429} else 503
                    raise PipelineError("sync_control_request_rejected", mapped)
                chunks, length = [], 0
                async for chunk in response.aiter_bytes():
                    length += len(chunk)
                    if length > MAX_RESPONSE_BYTES:
                        raise PipelineError("sync_control_response_too_large", 502)
                    chunks.append(chunk)
                data = json.loads(b"".join(chunks))
                if not isinstance(data, dict):
                    raise ValueError
                return data
    except httpx.TimeoutException:
        raise PipelineError("sync_control_timeout_submission_may_be_accepted", 504) from None
    except (httpx.HTTPError, ValueError):
        raise PipelineError("sync_control_unavailable", 503) from None


async def catalog() -> dict:
    _, _, profile = deployment()
    raw = await request("GET", "/v1/interfaces")
    profiles = raw.get("profiles")
    if not isinstance(profiles, list):
        raise PipelineError("sync_control_invalid_catalog", 502)
    matches = [p for p in profiles if isinstance(p, dict) and p.get("profile") == profile]
    if len(matches) != 1:
        raise PipelineError("sync_control_profile_unavailable", 409)
    found = matches[0]
    if found.get("enabled") is False or found.get("ready") is False:
        raise PipelineError("sync_control_profile_unavailable", 409)
    interfaces = []
    for item in found.get("interfaces", []):
        name = item if isinstance(item, str) else item.get("interface") if isinstance(item, dict) else None
        # 无allowed_modes的字符串目录仅用于已交接的人工验收profile。
        allowed = {"dry", "replay"} if isinstance(item, str) and profile == "accepted_manual" else set(
            item.get("allowed_modes", []) if isinstance(item, dict) else []
        )
        if isinstance(name, str) and re.fullmatch(r"web\.[a-z][a-z0-9_]{0,95}", name) and {"dry", "replay"} <= allowed:
            interfaces.append(name)
    if not interfaces or len(interfaces) != len(set(interfaces)):
        raise PipelineError("sync_control_invalid_catalog", 502)
    return {"profile": profile, "interfaces": sorted(interfaces), "manual_only": True}


def prepare_job(*, start_date: str, end_date: str, interfaces: list[str], publish: bool, dry: bool) -> dict:
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if start.isoformat() != start_date or end.isoformat() != end_date:
            raise ValueError
        if start < date(1900, 1, 1) or start > end or (end - start).days >= 7:
            raise ValueError
        if end >= datetime.now(ZoneInfo("Asia/Shanghai")).date():
            raise ValueError
        if not interfaces or len(interfaces) > 100 or len(interfaces) != len(set(interfaces)):
            raise ValueError
        if dry and publish:
            raise ValueError
    except (ValueError, TypeError):
        raise PipelineError("sync_control_invalid_job_scope", 422) from None
    return {"profile": deployment()[2], "interfaces": sorted(interfaces), "mode": "dry" if dry else "replay",
            "publish": publish, "start_date": start_date, "end_date": end_date}


async def submit(payload: dict, actor_id: str, operation_id: str) -> dict:
    allowed = await catalog()
    if not set(payload["interfaces"]) <= set(allowed["interfaces"]):
        raise PipelineError("sync_control_interface_not_approved", 422)
    # 相同操作标识+相同范围始终使用同一远端幂等键；超时后显式重试也不会另建任务。
    key = hashlib.sha256(json.dumps([actor_id, str(UUID(operation_id))]).encode()).hexdigest()
    return public_job(await request("POST", "/v1/jobs", payload=payload, key=key))


def public_job(raw: dict) -> dict:
    """收窄到控制面元数据；不转发任意上游载荷、错误原文或患者字段。"""
    try:
        job_id = str(UUID(raw["job_id"]))
        status = raw["status"]
        if status not in JOB_STATES:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        raise PipelineError("sync_control_invalid_job_response", 502) from None
    result = {"job_id": job_id, "status": status}
    for key in ("created_at", "updated_at", "started_at", "finished_at"):
        value = raw.get(key)
        if isinstance(value, str):
            try:
                result[key] = datetime.fromisoformat(value).isoformat()
            except ValueError:
                pass
    result["counts"] = {
        key: val for key, val in (raw.get("counts") or {}).items()
        if key in {"fetched", "inserted", "updated", "unchanged", "selected", "written", "units_total", "units_completed", "units_failed", "units_limited"}
        and type(val) is int and val >= 0
    } if isinstance(raw.get("counts"), dict) else {}
    result["cancel_requested"] = raw.get("cancel_requested") is True
    error = raw.get("error")
    if isinstance(error, dict):
        result["error"] = {key: val for key, val in error.items() if key in {"code", "location"}
                           and isinstance(val, str) and re.fullmatch(r"[a-z][a-z0-9_.:-]{0,127}", val)}
    req = raw.get("request")
    if isinstance(req, dict):
        result["mode"] = req.get("mode") if req.get("mode") in {"dry", "replay", "publish_only", "incremental"} else "unknown"
        result["published"] = req.get("publish") is True
    return result
