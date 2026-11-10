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
                chunks, length = [], 0
                async for chunk in response.aiter_bytes():
                    length += len(chunk)
                    if length > MAX_RESPONSE_BYTES:
                        raise PipelineError("sync_control_response_too_large", 502)
                    chunks.append(chunk)
                if response.status_code >= 300:
                    mapped = response.status_code if response.status_code in {403, 404, 409, 422, 429} else 503
                    try:
                        rejected = json.loads(b"".join(chunks))
                        safe = public_error(rejected.get("error", {})) if isinstance(rejected, dict) else {}
                    except ValueError:
                        safe = {}
                    error = PipelineError("sync_control_request_rejected", mapped)
                    error.public_details = safe
                    raise error
                data = json.loads(b"".join(chunks))
                if not isinstance(data, dict):
                    raise ValueError
                return data
    except httpx.TimeoutException:
        raise PipelineError("sync_control_timeout_submission_may_be_accepted", 504) from None
    except PipelineError:
        raise
    except (httpx.HTTPError, ValueError):
        raise PipelineError("sync_control_unavailable", 503) from None


async def catalog() -> dict:
    _, _, profile = deployment()
    capabilities = await session()
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
    return {"profile": profile, "interfaces": sorted(interfaces), "manual_only": True, "session": capabilities}


def prepare_job(*, start_date: str, end_date: str, interfaces: list[str], publish: bool, dry: bool, capabilities: dict) -> dict:
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if start.isoformat() != start_date or end.isoformat() != end_date:
            raise ValueError
        if start < date(1900, 1, 1) or start > end or (end - start).days >= capabilities["max_manual_days"]:
            raise ValueError
        if end > date.fromisoformat(capabilities["last_complete_date"]):
            raise ValueError
        if not interfaces or len(interfaces) > 100 or len(interfaces) != len(set(interfaces)):
            raise ValueError
        if dry and publish:
            raise ValueError
    except (ValueError, TypeError):
        raise PipelineError("sync_control_invalid_job_scope", 422) from None
    payload = {"profile": deployment()[2], "interfaces": sorted(interfaces), "mode": "dry" if dry else "replay",
               "publish": publish, "start_date": start_date, "end_date": end_date}
    if payload["profile"] in capabilities["features"]["date_recovery_profiles"]:
        payload["plan_version"] = 2
    return payload


async def submit(payload: dict, actor_id: str, operation_id: str) -> dict:
    allowed = await catalog()
    require_permission(allowed["session"], "run")
    if not set(payload["interfaces"]) <= set(allowed["interfaces"]):
        raise PipelineError("sync_control_interface_not_approved", 422)
    payload = prepare_job(start_date=payload["start_date"], end_date=payload["end_date"],
        interfaces=payload["interfaces"], publish=payload["publish"], dry=payload["mode"] == "dry",
        capabilities=allowed["session"])
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
        result["request"] = public_request(req)
    if "units" in raw:
        if not isinstance(raw["units"], list):
            raise PipelineError("sync_control_invalid_job_response", 502)
        result["units"] = [public_unit(unit) for unit in raw["units"]]
    return result


def require_permission(capabilities: dict, permission: str) -> None:
    if permission not in capabilities["permissions"]:
        raise PipelineError("sync_control_permission_denied", 403)


async def session() -> dict:
    """服务端能力是唯一日期策略；缺失或畸形时不猜测默认值。"""
    raw = await request("GET", "/v1/session")
    try:
        permissions = raw["permissions"]
        last = raw["last_complete_date"]
        days = raw["max_manual_days"]
        features = raw["features"]
        if (not isinstance(permissions, list) or any(p not in {"read", "run", "schedule"} for p in permissions)
                or raw["timezone"] != "Asia/Shanghai" or date.fromisoformat(last).isoformat() != last
                or type(days) is not int or days < 1 or not isinstance(features, dict)):
            raise ValueError
        profiles = features.get("date_recovery_profiles", [])
        if not isinstance(profiles, list) or any(not isinstance(p, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", p) for p in profiles):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise PipelineError("sync_control_invalid_session", 502) from None
    return {"permissions": list(dict.fromkeys(permissions)), "timezone": "Asia/Shanghai",
            "last_complete_date": last, "max_manual_days": days,
            "features": {"schedule_drafts": features.get("schedule_drafts") is True,
                         "schedule_controls": False, "date_recovery_profiles": profiles}}


def public_error(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k in {
        "code", "location", "error_kind", "error_location", "category", "retry_policy", "failure_scope",
    } and isinstance(v, str) and re.fullmatch(r"[a-z][a-z0-9_.:-]{0,127}", v)}


def public_request(raw: dict) -> dict:
    result = {k: raw[k] for k in ("profile", "start_date", "end_date") if isinstance(raw.get(k), str)
              and re.fullmatch(r"[a-z0-9_-]{1,64}", raw[k])}
    if isinstance(raw.get("interfaces"), list):
        result["interfaces"] = [name for name in raw["interfaces"] if isinstance(name, str) and re.fullmatch(r"web\.[a-z][a-z0-9_]{0,95}", name)]
    if isinstance(raw.get("mode"), str) and raw["mode"] in {"dry", "replay", "publish_only", "incremental"}:
        result["mode"] = raw["mode"]
    result["publish"] = raw.get("publish") is True
    if type(raw.get("plan_version")) is int and raw["plan_version"] in {1, 2}:
        result["plan_version"] = raw["plan_version"]
    return result


def public_unit(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise PipelineError("sync_control_invalid_unit", 502)
    result = {}
    for key in ("unit_id", "interface_name", "source_date", "phase", "status", "started_at", "finished_at", "retry_at"):
        value = raw.get(key)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:+-]{1,128}", value):
            result[key] = value
    for key in ("sequence", "execution_attempts"):
        if type(raw.get(key)) is int and raw[key] >= 0:
            result[key] = raw[key]
    result["error"] = public_error(raw.get("error"))
    if isinstance(raw.get("result"), dict):
        result["result"] = {"counts": {k: v for k, v in raw["result"].get("counts", {}).items()
            if k in {"fetched", "inserted", "updated", "unchanged", "selected", "written"} and type(v) is int and v >= 0}} if isinstance(raw["result"].get("counts"), dict) else {}
        result["result"].update(public_error(raw["result"]))
    return result


def public_schedule(raw: dict) -> dict:
    try:
        config = raw["config"]
        if (type(raw["version"]) is not int or raw["version"] < 1 or type(raw["enabled"]) is not bool
                or not isinstance(config, dict) or not isinstance(config.get("request"), dict)):
            raise ValueError
        if (config.get("frequency") not in {"daily", "weekly"} or config.get("timezone") != "Asia/Shanghai"
                or type(config.get("window_days")) is not int or not 1 <= config["window_days"] <= 60
                or not isinstance(config.get("local_time"), str)
                or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", config["local_time"])
                or (config["frequency"] == "weekly" and (type(config.get("weekday")) is not int or not 0 <= config["weekday"] <= 6))):
            raise ValueError
        result = {"schedule_id": str(UUID(raw["schedule_id"])), "version": raw["version"], "enabled": raw["enabled"],
                  "next_fire_at": None, "config": {"request": public_request(config["request"])}}
        for key in ("frequency", "local_time", "timezone"):
            value = config.get(key)
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_/:+-]{1,64}", value):
                raise ValueError
            result["config"][key] = value
        for key in ("window_days", "weekday"):
            if type(config.get(key)) is int:
                result["config"][key] = config[key]
        if raw.get("next_fire_at") is not None and not isinstance(raw["next_fire_at"], str):
            raise ValueError
        if isinstance(raw.get("next_fire_at"), str):
            result["next_fire_at"] = datetime.fromisoformat(raw["next_fire_at"]).isoformat()
        return result
    except (ValueError, KeyError, TypeError):
        raise PipelineError("sync_control_invalid_schedule_response", 502) from None
