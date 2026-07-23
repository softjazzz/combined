#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""客户样本验证端到端验收器。

默认 ``--dry-run`` 只检查服务、LX0609 规则、隔离样本池和病历就绪状态。
只有显式提供 ``--allow-local-writes`` 才允许创建任务、复核和导出检查。
验收器永远不自动导入、重匹配或重同步 fixture，避免破坏隔离样本。
输出始终是去标识化安全台账。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import requests


SCHEMA_VERSION = "customer-sample-validation-e2e-v1"
RULE_SET_KEY = "luxian_0609_qc_v1"
FIXTURE_ALIASES = {
    "lx0609-e2e-v1": {
        "pool_id": "luxian-0609-synthetic-v1",
        "pool_name": "泸县0609合成质控样本 v1",
        "source_file": "synthetic://luxian_0609_synthetic_cases_v1",
        "visit_prefix": "LX0609_SYN_",
    }
}
STAGE_NAMES = (
    "preflight",
    "fixture_import",
    "match_sync",
    "run_poll",
    "review_export_privacy",
)
_TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "canceled"})
_READY_SYNC_STATUSES = frozenset({"synced", "synthetic_seeded"})
_READY_BUNDLE_STATUS = "ready"
_SAFE_RESULT_STATUSES = frozenset(
    {
        "compliant",
        "non_compliant",
        "not_applicable",
        "data_gap",
        "evaluation_unknown",
        "ai_suggested_non_compliant",
        "technical_error",
        "inputs_unavailable",
        "skipped",
    }
)
_RULE_ID_PATTERN = re.compile(r"^LX0609-\d{3}$")
_OPERATION_REF_PATTERN = re.compile(r"^sample-op-[0-9a-f]{24}$")
_SCOPE_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_EXPORT_MIME_MARKERS = {
    "html": "text/html",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_FORBIDDEN_KEYS = frozenset(
    {
        "patient_id",
        "patient_name",
        "visit_id",
        "institute_id",
        "record_id",
        "sample_item_id",
        "pool_id",
        "job_id",
        "mr_no",
        "inpat_no",
        "medical_text",
        "record_content",
        "documents",
        "document_text",
        "primary_document_text",
        "prompt",
        "raw_prompt",
        "raw_response",
        "source_quote",
        "sql",
        "error_message",
        "record_time",
        "admission_time",
        "discharge_time",
    }
)


class E2EContractError(ValueError):
    """验收器调用合同不满足。"""


class E2EPrivacyError(ValueError):
    """安全台账包含禁止输出。"""


class E2EApiError(RuntimeError):
    """API 调用失败，仅携带受控原因码。"""

    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


class StageFailure(RuntimeError):
    """单阶段失败，停止后续有副作用的步骤。"""

    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


def _safe_ref(namespace: str, value: str) -> str:
    digest = hashlib.sha256(f"{namespace}:{value}".encode("utf-8")).hexdigest()
    return f"{namespace}_{digest[:16]}"


def _unwrap_response(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload and (
        "success" in payload or "trace_id" in payload
    ):
        return payload.get("data")
    return payload


class RequestsApiClient:
    """极小 API 客户端；错误不回显响应正文或请求路径。"""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        token: str = "",
        email: str = "",
        password: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        if token.strip():
            self.session.headers["Authorization"] = f"Bearer {token.strip()}"
        elif email.strip() and password:
            self._login(email=email.strip(), password=password)

    def _login(self, *, email: str, password: str) -> None:
        started = time.perf_counter()
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"email": email, "password": password},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise E2EApiError("auth_transport_error") from exc
        _ = (time.perf_counter() - started) * 1000
        if response.status_code >= 400:
            raise E2EApiError(f"auth_http_{response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise E2EApiError("auth_invalid_json") from exc
        data = _unwrap_response(payload)
        access_token = data.get("access_token") if isinstance(data, dict) else None
        if not str(access_token or "").strip():
            raise E2EApiError("auth_token_missing")
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_data: dict | None = None,
        binary: bool = False,
    ) -> dict:
        started = time.perf_counter()
        try:
            response = self.session.request(
                method=method.upper(),
                url=f"{self.base_url}{path}",
                params=params,
                json=json_data,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise E2EApiError("api_transport_error") from exc
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        if response.status_code >= 400:
            raise E2EApiError(f"api_http_{response.status_code}")

        if binary:
            data = None
            byte_count = len(response.content or b"")
        else:
            try:
                data = _unwrap_response(response.json())
            except ValueError as exc:
                raise E2EApiError("api_invalid_json") from exc
            byte_count = len(response.content or b"")
        return {
            "data": data,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
            "content_type": str(response.headers.get("content-type") or ""),
            "byte_count": byte_count,
        }


def _normalize_rule_ids(values: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        rule_id = str(value or "").strip().upper()
        if not rule_id:
            continue
        if not _RULE_ID_PATTERN.fullmatch(rule_id):
            raise E2EContractError(f"非法 LX0609 规则编号: {rule_id}")
        if rule_id not in normalized:
            normalized.append(rule_id)
    if not normalized:
        raise E2EContractError("selected-rule-ids 不能为空")
    return tuple(normalized)


def _items(data: Any) -> list[dict]:
    if isinstance(data, dict):
        for key in ("items", "rules"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _catalog_rule_ids(data: Any) -> set[str]:
    result: set[str] = set()
    for row in _items(data):
        for key in ("rule_id", "rule_code", "id"):
            value = str(row.get(key) or "").strip().upper()
            if _RULE_ID_PATTERN.fullmatch(value):
                result.add(value)
                break
    return result


def _find_rule_set(data: Any) -> dict | None:
    for row in _items(data):
        key = str(row.get("rule_set_key") or row.get("key") or "").strip()
        if key == RULE_SET_KEY:
            return row
    return None


def _record_readiness(record: dict) -> str:
    match_status = str(record.get("match_status") or "").strip().lower()
    sync_status = str(record.get("sync_status") or "").strip().lower()
    bundle_status = str(record.get("bundle_status") or "").strip().lower()
    if match_status == "ambiguous":
        return "ambiguous"
    if match_status != "matched":
        return "unmatched"
    if sync_status not in _READY_SYNC_STATUSES:
        return "not_synced"
    if bundle_status != _READY_BUNDLE_STATUS:
        return "bundle_not_ready"
    if not str(record.get("matched_visit_id") or "").strip():
        return "unmatched"
    return "ready"


def _fetch_all_records(api: Any, pool_id: str) -> list[dict]:
    page = 1
    page_size = 200
    records: list[dict] = []
    while True:
        response = api.request(
            "GET",
            f"/api/v1/qc/sample-pools/{pool_id}/records",
            params={"page": page, "page_size": page_size},
        )
        data = response.get("data")
        rows = _items(data)
        records.extend(rows)
        total = int(data.get("total") or len(records)) if isinstance(data, dict) else len(records)
        if not rows or len(records) >= total:
            return records
        page += 1


def _stage(name: str, *, status: str, elapsed_ms: float, reason_code: str) -> dict:
    return {
        "name": name,
        "status": status,
        "elapsed_ms": round(max(0.0, elapsed_ms), 3),
        "reason_code": reason_code,
    }


def _flatten_job_items(job: dict) -> list[dict]:
    rows: list[dict] = []
    direct = job.get("items")
    if isinstance(direct, list):
        rows.extend(item for item in direct if isinstance(item, dict))
    for key in ("child_jobs", "children"):
        children = job.get(key)
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    rows.extend(_flatten_job_items(child))
            if children:
                break
    return rows


def _status_counts(items: Iterable[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or item.get("final_state") or "").strip().lower()
        if not status:
            continue
        safe_status = status if status in _SAFE_RESULT_STATUSES else "unknown_status"
        counts[safe_status] = counts.get(safe_status, 0) + 1
    return dict(sorted(counts.items()))


def _metric(job: dict, key: str) -> int:
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    profile = (
        summary.get("performance_profile")
        if isinstance(summary.get("performance_profile"), dict)
        else {}
    )
    for source in (profile, summary, job):
        value = source.get(key) if isinstance(source, dict) else None
        if value is not None:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                return 0
    return 0


def _review_finding_count(data: Any) -> int:
    if not isinstance(data, dict):
        raise StageFailure("review_report_invalid")
    report = data.get("review_report")
    if not isinstance(report, dict):
        raise StageFailure("review_report_invalid")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise StageFailure("review_report_invalid")
    total_findings = summary.get("total_findings")
    if (
        isinstance(total_findings, bool)
        or not isinstance(total_findings, int)
        or total_findings < 0
    ):
        raise StageFailure("review_report_invalid")
    return total_findings


def assert_safe_ledger(
    ledger: Any,
    *,
    private_values: Sequence[str] = (),
) -> None:
    """拒绝禁用字段和调用过程中出现过的私有值。"""

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                normalized_key = str(key).strip().lower()
                if normalized_key in _FORBIDDEN_KEYS:
                    raise E2EPrivacyError(f"forbidden ledger field: {normalized_key}")
                walk(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                walk(nested)

    walk(ledger)
    serialized = json.dumps(ledger, ensure_ascii=False, sort_keys=True)
    for private_value in private_values:
        marker = str(private_value or "").strip()
        if len(marker) >= 4 and marker in serialized:
            raise E2EPrivacyError("private runtime value leaked into safe ledger")


def write_safe_ledger(path: Path, ledger: dict) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def run_e2e(
    *,
    api: Any,
    fixture_pool: str,
    selected_rule_ids: Sequence[str],
    dry_run: bool,
    allow_local_writes: bool,
    output_path: Path | None = None,
    poll_timeout_seconds: float = 900,
    poll_interval_seconds: float = 1.0,
) -> dict:
    """执行五阶段验收；任何阶段失败后均停止下游动作。"""

    fixture_pool = str(fixture_pool or "").strip()
    if not fixture_pool:
        raise E2EContractError("fixture-pool 不能为空")
    fixture_contract = FIXTURE_ALIASES.get(fixture_pool)
    if fixture_contract is None:
        raise E2EContractError("fixture-pool 必须使用已登记的隔离验收别名")
    rules = _normalize_rule_ids(selected_rule_ids)
    if not dry_run and not allow_local_writes:
        raise E2EContractError("非 dry-run 必须显式提供 --allow-local-writes")
    if poll_timeout_seconds <= 0:
        raise E2EContractError("poll timeout 必须大于 0")

    ledger: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mode": "dry_run" if dry_run else "controlled_local_write",
        "fixture_pool_ref": _safe_ref("pool", fixture_pool),
        "selected_rule_ids": list(rules),
        "stages": [],
        "summary": {
            "record_count": 0,
            "ready_record_count": 0,
            "result_status_counts": {},
            "llm_call_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "review_finding_count": 0,
            "export_format_count": 0,
            "release_artifact_status": "unknown",
            "release_gate_ready": False,
        },
    }
    private_values: list[str] = [
        fixture_pool,
        fixture_contract["pool_id"],
        fixture_contract["pool_name"],
        fixture_contract["source_file"],
    ]
    pool_id = ""
    records: list[dict] = []
    job_id = ""
    operation_ref = ""
    execution_scope_hash = ""
    failed = False

    def execute_stage(name: str, action: Any) -> Any:
        nonlocal failed
        if failed:
            ledger["stages"].append(
                _stage(
                    name,
                    status="skipped",
                    elapsed_ms=0,
                    reason_code="upstream_failed",
                )
            )
            return None
        started = time.perf_counter()
        try:
            result = action()
        except (E2EApiError, StageFailure) as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            reason_code = getattr(exc, "reason_code", "stage_failed")
            ledger["stages"].append(
                _stage(
                    name,
                    status="failed",
                    elapsed_ms=elapsed_ms,
                    reason_code=str(reason_code),
                )
            )
            failed = True
            return None
        elapsed_ms = (time.perf_counter() - started) * 1000
        ledger["stages"].append(
            _stage(
                name,
                status="passed",
                elapsed_ms=elapsed_ms,
                reason_code="verified",
            )
        )
        return result

    def preflight() -> None:
        health = api.request("GET", "/api/v1/health").get("data")
        if not isinstance(health, dict) or str(health.get("status") or "").lower() not in {
            "healthy",
            "ok",
        }:
            raise StageFailure("service_not_ready")
        rule_sets = api.request(
            "GET",
            "/api/v1/qc/sample-pools/rule-sets",
        ).get("data")
        selected_rule_set = _find_rule_set(rule_sets)
        if selected_rule_set is None:
            raise StageFailure("lx0609_rule_set_missing")
        artifact_freshness = (
            selected_rule_set.get("artifact_freshness")
            if isinstance(selected_rule_set.get("artifact_freshness"), dict)
            else {}
        )
        release_gate = (
            selected_rule_set.get("release_gate_summary")
            if isinstance(selected_rule_set.get("release_gate_summary"), dict)
            else {}
        )
        artifact_status = str(artifact_freshness.get("status") or "unknown").strip()
        ledger["summary"]["release_artifact_status"] = artifact_status
        ledger["summary"]["release_gate_ready"] = bool(
            release_gate.get("release_ready")
        )
        if artifact_status != "fresh":
            raise StageFailure("release_artifact_not_fresh")
        catalog = api.request(
            "GET",
            "/api/v1/qc/sichuan/rules",
            params={"rule_set_key": RULE_SET_KEY},
        ).get("data")
        catalog_ids = _catalog_rule_ids(catalog)
        if not set(rules).issubset(catalog_ids):
            raise StageFailure("selected_rule_missing")

    execute_stage("preflight", preflight)

    def fixture_import() -> None:
        nonlocal pool_id
        pools_data = api.request(
            "GET",
            "/api/v1/qc/sample-pools",
            params={
                "q": fixture_contract["pool_name"],
                "page": 1,
                "page_size": 100,
            },
        ).get("data")
        pool_rows = _items(pools_data)
        same_id_matches = [
            pool
            for pool in pool_rows
            if str(pool.get("id") or "").strip() == fixture_contract["pool_id"]
        ]
        exact_matches = [
            pool
            for pool in pool_rows
            if str(pool.get("id") or "").strip() == fixture_contract["pool_id"]
            and str(pool.get("name") or "").strip() == fixture_contract["pool_name"]
            and str(pool.get("source_file") or "").strip()
            == fixture_contract["source_file"]
        ]
        if len(exact_matches) != 1:
            raise StageFailure(
                "fixture_pool_identity_mismatch"
                if same_id_matches
                else "fixture_pool_missing"
                if not exact_matches
                else "fixture_pool_ambiguous"
            )
        pool_id = str(exact_matches[0].get("id") or "").strip()
        if not pool_id:
            raise StageFailure("fixture_pool_id_missing")
        private_values.append(pool_id)

    execute_stage("fixture_import", fixture_import)

    def inspect_records() -> list[dict]:
        nonlocal records
        records = _fetch_all_records(api, pool_id)
        if not records:
            raise StageFailure("fixture_records_empty")
        if any(
            not str(record.get("matched_visit_id") or "").strip().startswith(
                fixture_contract["visit_prefix"]
            )
            for record in records
        ):
            raise StageFailure("fixture_record_identity_mismatch")
        ledger["summary"]["record_count"] = len(records)
        readiness = [_record_readiness(record) for record in records]
        ledger["summary"]["ready_record_count"] = sum(
            1 for state in readiness if state == "ready"
        )
        for record in records:
            private_values.extend(
                str(record.get(key) or "").strip()
                for key in (
                    "id",
                    "matched_institute_id",
                    "matched_patient_id",
                    "matched_visit_id",
                    "patient_name",
                    "mr_no",
                )
            )
        if any(state == "ambiguous" for state in readiness):
            raise StageFailure("fixture_match_ambiguous")
        if any(state == "unmatched" for state in readiness):
            raise StageFailure("fixture_unmatched")
        if any(state == "not_synced" for state in readiness):
            raise StageFailure("fixture_not_synced")
        if any(state == "bundle_not_ready" for state in readiness):
            raise StageFailure("fixture_bundle_not_ready")
        return records

    def match_sync() -> None:
        # 固定 fixture 的匹配、同步和 bundle 必须在验收前完成。这里即使具备
        # 本地写权限也只读核验，避免远端重匹配破坏 synthetic_seeded 状态。
        inspect_records()

    execute_stage("match_sync", match_sync)

    if dry_run and not failed:
        ledger["stages"].append(
            _stage(
                "run_poll",
                status="skipped",
                elapsed_ms=0,
                reason_code="dry_run",
            )
        )
        ledger["stages"].append(
            _stage(
                "review_export_privacy",
                status="skipped",
                elapsed_ms=0,
                reason_code="dry_run",
            )
        )
    else:
        final_job: dict[str, Any] = {}

        def run_poll() -> None:
            nonlocal job_id, operation_ref, execution_scope_hash, final_job
            record_ids = [
                str(record.get("matched_visit_id") or "").strip()
                for record in records
                if str(record.get("matched_visit_id") or "").strip()
            ]
            if not record_ids:
                raise StageFailure("ready_record_ids_missing")
            run_data = api.request(
                "POST",
                f"/api/v1/qc/sample-pools/{pool_id}/run",
                json_data={
                    "record_ids": record_ids,
                    "selected_rule_ids": list(rules),
                    "group_by_luxian_family": True,
                    "validation_mode": "customer",
                    "rule_set_key": RULE_SET_KEY,
                },
            ).get("data")
            if not isinstance(run_data, dict):
                raise StageFailure("run_response_invalid")
            job_id = str(run_data.get("job_id") or "").strip()
            if not job_id:
                raise StageFailure("run_job_missing")
            private_values.append(job_id)
            operation_ref = str(run_data.get("operation_ref") or "").strip()
            execution_scope_hash = str(
                run_data.get("execution_scope_hash") or ""
            ).strip()
            if not _OPERATION_REF_PATTERN.fullmatch(operation_ref):
                raise StageFailure("operation_ref_invalid")
            if not _SCOPE_HASH_PATTERN.fullmatch(execution_scope_hash):
                raise StageFailure("execution_scope_hash_invalid")
            deadline = time.monotonic() + poll_timeout_seconds
            while True:
                job_data = api.request(
                    "GET",
                    f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}",
                ).get("data")
                if not isinstance(job_data, dict):
                    raise StageFailure("job_response_invalid")
                job_status = str(job_data.get("status") or "").strip().lower()
                if job_status in _TERMINAL_JOB_STATUSES:
                    final_job = job_data
                    break
                if time.monotonic() >= deadline:
                    raise StageFailure("job_poll_timeout")
                if poll_interval_seconds > 0:
                    time.sleep(poll_interval_seconds)
            if str(final_job.get("status") or "").strip().lower() != "completed":
                raise StageFailure("job_not_completed")
            ledger["job_ref"] = _safe_ref("job", job_id)
            if operation_ref:
                ledger["operation_ref"] = operation_ref
            if execution_scope_hash:
                ledger["execution_scope_hash"] = execution_scope_hash
            status_counts = _status_counts(_flatten_job_items(final_job))
            if "unknown_status" in status_counts:
                raise StageFailure("job_result_status_invalid")
            ledger["summary"]["result_status_counts"] = status_counts
            for metric_key in (
                "llm_call_count",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            ):
                ledger["summary"][metric_key] = _metric(final_job, metric_key)

        execute_stage("run_poll", run_poll)

        def review_export_privacy() -> None:
            review_data = api.request(
                "POST",
                f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/review",
            ).get("data")
            ledger["summary"]["review_finding_count"] = _review_finding_count(
                review_data
            )
            export_count = 0
            for export_format in ("html", "csv", "xlsx"):
                export_response = api.request(
                    "GET",
                    f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}/export",
                    params={"format": export_format},
                    binary=True,
                )
                content_type = str(
                    export_response.get("content_type") or ""
                ).strip().lower()
                if (
                    int(export_response.get("status_code") or 0) == 200
                    and int(export_response.get("byte_count") or 0) > 0
                    and _EXPORT_MIME_MARKERS[export_format] in content_type
                ):
                    export_count += 1
            ledger["summary"]["export_format_count"] = export_count
            if export_count != 3:
                raise StageFailure("export_format_incomplete")

        execute_stage("review_export_privacy", review_export_privacy)

    if len(ledger["stages"]) < len(STAGE_NAMES):
        existing = {stage["name"] for stage in ledger["stages"]}
        for stage_name in STAGE_NAMES:
            if stage_name not in existing:
                ledger["stages"].append(
                    _stage(
                        stage_name,
                        status="skipped",
                        elapsed_ms=0,
                        reason_code="upstream_failed",
                    )
                )
    ledger["stages"].sort(key=lambda row: STAGE_NAMES.index(row["name"]))
    ledger["overall_status"] = "failed" if failed else "passed"
    assert_safe_ledger(ledger, private_values=private_values)
    if output_path is not None:
        write_safe_ledger(output_path, ledger)
    return ledger


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="客户样本验证端到端验收器")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--fixture-pool", required=True)
    parser.add_argument("--selected-rule-ids", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-local-writes", action="store_true")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--poll-timeout", type=float, default=900)
    parser.add_argument("--poll-interval", type=float, default=1)
    parser.add_argument("--token", default=os.getenv("MEDQC_API_TOKEN", ""))
    parser.add_argument("--email", default=os.getenv("MEDQC_API_EMAIL", ""))
    parser.add_argument("--password", default=os.getenv("MEDQC_API_PASSWORD", ""))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        api = RequestsApiClient(
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            token=args.token,
            email=args.email,
            password=args.password,
        )
        ledger = run_e2e(
            api=api,
            fixture_pool=args.fixture_pool,
            selected_rule_ids=tuple(args.selected_rule_ids.split(",")),
            dry_run=bool(args.dry_run),
            allow_local_writes=bool(args.allow_local_writes),
            output_path=args.output,
            poll_timeout_seconds=args.poll_timeout,
            poll_interval_seconds=args.poll_interval,
        )
    except (E2EContractError, E2EApiError, E2EPrivacyError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "overall_status": "failed",
                    "reason_code": getattr(exc, "reason_code", "contract_error"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    summary = {
        "schema_version": ledger["schema_version"],
        "overall_status": ledger["overall_status"],
        "mode": ledger["mode"],
        "output_written": bool(args.output),
    }
    failed_stage = next(
        (stage for stage in ledger["stages"] if stage["status"] == "failed"),
        None,
    )
    if failed_stage is not None:
        summary["failed_stage"] = failed_stage["name"]
        summary["reason_code"] = failed_stage["reason_code"]
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if ledger["overall_status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
