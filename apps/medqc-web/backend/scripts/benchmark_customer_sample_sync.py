from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


CASE_SIZES = (8, 30, 100)
METRIC_NAMES = (
    "source_resolve_ms",
    "primary_visible_ms",
    "detail_sync_ms",
    "bundle_refresh_ms",
    "total_duration_ms",
    "rows_pulled",
    "rows_upserted",
    "tables_skipped_unchanged",
    "visits_refreshed",
    "retry_count",
)
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "canceled"}


def empty_metrics() -> dict[str, int | float | None]:
    return {name: None for name in METRIC_NAMES}


def build_acceptance_template() -> dict[str, Any]:
    measurements: dict[str, Any] = {}
    for size in CASE_SIZES:
        measurements[str(size)] = {
            "baseline_first": empty_metrics(),
            "baseline_second_unchanged": empty_metrics(),
            "optimized_first": empty_metrics(),
            "optimized_second_unchanged": empty_metrics(),
        }
    payload = {
        "schema_version": "customer-sample-sync-performance-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "measurement_status": "待客户机实测",
        "measurements": measurements,
    }
    payload["acceptance"] = evaluate_acceptance(payload)
    return payload


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _duration_ms(started_at: Any, completed_at: Any) -> float | None:
    if not isinstance(started_at, str) or not isinstance(completed_at, str):
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return round(max((end - start).total_seconds() * 1000, 0), 2)
    except ValueError:
        return None


def extract_metrics(
    job: dict[str, Any],
    *,
    observed_source_resolve_ms: float | None = None,
    observed_primary_visible_ms: float | None = None,
) -> dict[str, int | float | None]:
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    performance = (
        summary.get("sync_performance")
        if isinstance(summary.get("sync_performance"), dict)
        else {}
    )
    bundle_refresh = (
        summary.get("bundle_refresh")
        if isinstance(summary.get("bundle_refresh"), dict)
        else {}
    )
    synced_tables = (
        summary.get("synced_tables")
        if isinstance(summary.get("synced_tables"), list)
        else []
    )
    explicit_skipped_unchanged = [
        item
        for item in synced_tables
        if isinstance(item, dict)
        and (
            str(item.get("sync_status") or "").lower() == "skipped_unchanged"
            or str(item.get("skip_reason") or "").lower() == "unchanged"
        )
    ]
    skipped_unchanged = _number(performance.get("tables_skipped_unchanged"))
    if skipped_unchanged is None:
        skipped_unchanged = _number(summary.get("tables_skipped_unchanged"))
    if skipped_unchanged is None and explicit_skipped_unchanged:
        skipped_unchanged = len(explicit_skipped_unchanged)
    primary_visible_ms = _number(performance.get("primary_visible_ms"))
    if primary_visible_ms is None:
        primary_visible_ms = _duration_ms(
            job.get("started_at"),
            summary.get("primary_completed_at"),
        )
    if primary_visible_ms is None:
        primary_visible_ms = observed_primary_visible_ms

    source_resolve_ms = _number(performance.get("source_resolve_ms"))
    if source_resolve_ms is None:
        source_resolve_ms = observed_source_resolve_ms
    visits_refreshed = _number(performance.get("visits_refreshed"))
    if visits_refreshed is None:
        visits_refreshed = _number(bundle_refresh.get("processed"))

    return {
        "source_resolve_ms": source_resolve_ms,
        "primary_visible_ms": primary_visible_ms,
        "detail_sync_ms": _number(performance.get("detail_sync_ms")),
        "bundle_refresh_ms": _number(
            performance.get("bundle_refresh_ms")
            if "bundle_refresh_ms" in performance
            else performance.get("bundle_refresh_duration_ms")
        ),
        "total_duration_ms": _number(performance.get("total_duration_ms")),
        "rows_pulled": _number(summary.get("total_rows_pulled")),
        "rows_upserted": _number(summary.get("total_rows_upserted")),
        "tables_skipped_unchanged": skipped_unchanged,
        "visits_refreshed": visits_refreshed,
        "retry_count": _number(
            performance.get("retry_count")
            if "retry_count" in performance
            else (
                job.get("retry_count")
                if "retry_count" in job
                else summary.get("retry_count")
            )
        )
        or 0,
    }


def build_sync_payload(table_groups: list[str]) -> dict[str, Any]:
    return {
        "only_intrinsic": False,
        "include_in_batch_1": False,
        **({"table_groups": table_groups} if table_groups else {}),
    }


def get_job_progress(job: dict[str, Any]) -> dict[str, Any]:
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    progress = summary.get("progress")
    return progress if isinstance(progress, dict) else {}


def _reduction_percent(baseline: Any, optimized: Any) -> float | None:
    baseline_number = _number(baseline)
    optimized_number = _number(optimized)
    if baseline_number is None or optimized_number is None or baseline_number <= 0:
        return None
    return round((baseline_number - optimized_number) / baseline_number * 100, 2)


def _check_reduction(
    *,
    check_id: str,
    label: str,
    baseline: Any,
    optimized: Any,
    minimum_percent: float,
) -> dict[str, Any]:
    reduction = _reduction_percent(baseline, optimized)
    status = "pending" if reduction is None else ("pass" if reduction >= minimum_percent else "fail")
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "minimum_reduction_percent": minimum_percent,
        "measured_reduction_percent": reduction,
    }


def evaluate_acceptance(payload: dict[str, Any]) -> dict[str, Any]:
    measurements = payload.get("measurements")
    measurements = measurements if isinstance(measurements, dict) else {}
    checks: list[dict[str, Any]] = []
    for size in CASE_SIZES:
        group = measurements.get(str(size))
        group = group if isinstance(group, dict) else {}
        baseline_first = group.get("baseline_first")
        baseline_first = baseline_first if isinstance(baseline_first, dict) else {}
        optimized_first = group.get("optimized_first")
        optimized_first = optimized_first if isinstance(optimized_first, dict) else {}
        checks.append(
            _check_reduction(
                check_id=f"size_{size}_primary_visible",
                label=f"{size}份病例首次可见时间下降至少70%",
                baseline=baseline_first.get("primary_visible_ms"),
                optimized=optimized_first.get("primary_visible_ms"),
                minimum_percent=70,
            )
        )
        checks.append(
            _check_reduction(
                check_id=f"size_{size}_first_total",
                label=f"{size}份病例首次完整同步耗时下降至少40%",
                baseline=baseline_first.get("total_duration_ms"),
                optimized=optimized_first.get("total_duration_ms"),
                minimum_percent=40,
            )
        )

    group_30 = measurements.get("30")
    group_30 = group_30 if isinstance(group_30, dict) else {}
    baseline_second = group_30.get("baseline_second_unchanged")
    baseline_second = baseline_second if isinstance(baseline_second, dict) else {}
    optimized_second = group_30.get("optimized_second_unchanged")
    optimized_second = optimized_second if isinstance(optimized_second, dict) else {}
    checks.append(
        _check_reduction(
            check_id="size_30_second_unchanged",
            label="30份病例第二次无变化同步耗时下降至少70%",
            baseline=baseline_second.get("total_duration_ms"),
            optimized=optimized_second.get("total_duration_ms"),
            minimum_percent=70,
        )
    )
    refreshed = _number(optimized_second.get("visits_refreshed"))
    checks.append(
        {
            "id": "size_30_second_no_bundle_rebuild",
            "label": "30份病例第二次无变化同步不重建Bundle",
            "status": "pending" if refreshed is None else ("pass" if refreshed == 0 else "fail"),
            "measured_visits_refreshed": refreshed,
        }
    )
    statuses = {item["status"] for item in checks}
    overall = "fail" if "fail" in statuses else ("pending" if "pending" in statuses else "pass")
    return {"overall": overall, "checks": checks}


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "customer-sample-sync-performance-v1":
        errors.append("schema_version 不受支持")
    measurements = payload.get("measurements")
    if not isinstance(measurements, dict):
        return [*errors, "measurements 必须是对象"]
    for size in CASE_SIZES:
        group = measurements.get(str(size))
        if not isinstance(group, dict):
            errors.append(f"缺少 {size} 份病例的测量组")
            continue
        for run_name in (
            "baseline_first",
            "baseline_second_unchanged",
            "optimized_first",
            "optimized_second_unchanged",
        ):
            metrics = group.get(run_name)
            if not isinstance(metrics, dict):
                errors.append(f"{size}.{run_name} 必须是对象")
                continue
            missing = [name for name in METRIC_NAMES if name not in metrics]
            if missing:
                errors.append(f"{size}.{run_name} 缺少指标: {', '.join(missing)}")
    return errors


def _request_json(
    *,
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url=url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(
            f"服务返回 HTTP {exc.code}，请检查样本池、登录权限和后端状态。"
        ) from exc
    except URLError as exc:
        raise RuntimeError("无法连接质控服务，请检查 base URL、网络和后端进程。") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("服务返回的不是有效 JSON，请确认访问的是新版后端 API。") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("服务返回格式异常：顶层必须是 JSON 对象。")
    data = decoded.get("data", decoded)
    if not isinstance(data, dict):
        raise RuntimeError("服务返回格式异常：data 必须是 JSON 对象。")
    return data


def run_sync_once(
    *,
    base_url: str,
    pool_id: str,
    token: str,
    poll_seconds: float,
    timeout_seconds: float,
    table_groups: list[str],
) -> dict[str, int | float | None]:
    started = time.monotonic()
    created = _request_json(
        method="POST",
        url=f"{base_url}/api/v1/qc/sample-pools/{quote(pool_id, safe='')}/sync-records",
        token=token,
        payload=build_sync_payload(table_groups),
        timeout_seconds=timeout_seconds,
    )
    job_id = str(created.get("job_id") or "").strip()
    if not job_id:
        raise RuntimeError("同步任务创建成功但未返回 job_id，请检查后端版本。")

    observed_source_resolve_ms: float | None = None
    observed_primary_visible_ms: float | None = None
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        job = _request_json(
            method="GET",
            url=f"{base_url}/api/v1/qc/sample-pools/sync-jobs/{quote(job_id, safe='')}",
            token=token,
            timeout_seconds=timeout_seconds,
        )
        progress = get_job_progress(job)
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        if observed_source_resolve_ms is None and progress.get("step_key") in {
            "resolved",
            "primary_visible",
            "syncing",
            "matching",
        }:
            observed_source_resolve_ms = elapsed_ms
        if observed_primary_visible_ms is None and (
            progress.get("primary_visible") is True
            or progress.get("step_key") == "primary_visible"
        ):
            observed_primary_visible_ms = elapsed_ms
        status = str(job.get("status") or "").lower()
        if status in TERMINAL_STATUSES:
            if status != "completed":
                message = str(job.get("error_message") or "同步任务未完成")
                raise RuntimeError(f"同步任务失败：{message}")
            return extract_metrics(
                job,
                observed_source_resolve_ms=observed_source_resolve_ms,
                observed_primary_visible_ms=observed_primary_visible_ms,
            )
        time.sleep(poll_seconds)
    raise RuntimeError("同步任务等待超时，请稍后查看任务状态，或增大 --timeout-seconds。")


def parse_pool_specs(values: list[str]) -> dict[int, str]:
    pools: dict[int, str] = {}
    for value in values:
        size_text, separator, pool_id = value.partition(":")
        if not separator or not size_text.isdigit() or not pool_id.strip():
            raise ValueError("--pool 格式应为 病例数:样本池ID，例如 8:pool-8")
        size = int(size_text)
        if size not in CASE_SIZES:
            raise ValueError("--pool 的病例数仅支持 8、30、100")
        pools[size] = pool_id.strip()
    missing = [str(size) for size in CASE_SIZES if size not in pools]
    if missing:
        raise ValueError(f"缺少病例规模对应的样本池：{', '.join(missing)}")
    return pools


def _safe_base_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--base-url 必须是有效的 http/https 地址")
    if parsed.username or parsed.password:
        raise ValueError("--base-url 不得包含用户名或密码")
    return value.rstrip("/")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="客户样本两阶段增量同步性能验收工具（不会记录 token、密码或服务地址）"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template-output", type=Path, help="生成待填写的验收 JSON 模板")
    mode.add_argument("--validate", type=Path, help="校验已有验收 JSON 并重新计算结论")
    mode.add_argument("--run", action="store_true", help="连接客户机后端执行两轮同步")
    parser.add_argument("--output", type=Path, help="实测结果 JSON 输出路径")
    parser.add_argument("--base-url", help="客户机后端地址，不得包含账号密码")
    parser.add_argument(
        "--pool",
        action="append",
        default=[],
        help="病例数:样本池ID；实测需分别提供 8、30、100",
    )
    parser.add_argument(
        "--token-env",
        default="MEDQC_BENCHMARK_TOKEN",
        help="Bearer token 所在环境变量名；token 不会写入结果",
    )
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--table-group", action="append", default=[])
    args = parser.parse_args(argv)

    try:
        if args.template_output:
            write_json(args.template_output, build_acceptance_template())
            print(f"已生成验收模板：{args.template_output}")
            return 0
        if args.validate:
            payload = json.loads(args.validate.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("验收 JSON 顶层必须是对象")
            errors = validate_payload(payload)
            if errors:
                raise ValueError("；".join(errors))
            payload["acceptance"] = evaluate_acceptance(payload)
            write_json(args.validate, payload)
            print(json.dumps(payload["acceptance"], ensure_ascii=False, indent=2))
            return 1 if payload["acceptance"]["overall"] == "fail" else 0

        if not args.output or not args.base_url:
            raise ValueError("--run 必须同时提供 --base-url 和 --output")
        pools = parse_pool_specs(args.pool)
        base_url = _safe_base_url(args.base_url)
        token = os.getenv(args.token_env, "")
        result = build_acceptance_template()
        for size in CASE_SIZES:
            print(f"正在执行 {size} 份病例首次同步……", flush=True)
            result["measurements"][str(size)]["optimized_first"] = run_sync_once(
                base_url=base_url,
                pool_id=pools[size],
                token=token,
                poll_seconds=max(args.poll_seconds, 0.1),
                timeout_seconds=max(args.timeout_seconds, 1),
                table_groups=args.table_group,
            )
            print(f"正在执行 {size} 份病例第二次无变化同步……", flush=True)
            result["measurements"][str(size)]["optimized_second_unchanged"] = run_sync_once(
                base_url=base_url,
                pool_id=pools[size],
                token=token,
                poll_seconds=max(args.poll_seconds, 0.1),
                timeout_seconds=max(args.timeout_seconds, 1),
                table_groups=args.table_group,
            )
        result["measurement_status"] = "客户机已实测，基线指标仍需按实际填写"
        result["acceptance"] = evaluate_acceptance(result)
        write_json(args.output, result)
        print(f"实测完成：{args.output}")
        print(json.dumps(result["acceptance"], ensure_ascii=False, indent=2))
        return 1 if result["acceptance"]["overall"] == "fail" else 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"验收工具未完成：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
