"""金样参考：规则集版本读取侧版本化前（提交 7faa55e80）的读取入口原实现，逐字冻结。

仅供等价性金样测试对比使用，禁止修改或在业务代码中引用。冻结方式：

- custom_qc_workspace_service 中本批改动的函数/方法原样复制；方法去掉类缩进变为以 ``self``
  为首参的模块函数，调用时传入真实 ``CustomQCWorkspaceService`` 实例（未改动的方法如
  ``_aggregate_parent_job``、``_load_record_result_envelope_with_id`` 仍经 ``self`` 调用）。
- 冻结方法之间的 ``self.xxx(`` 调用改为调用本文件中的冻结函数（两处），避免落到新实现。
- record_result_read_model.select_latest_authoritative_record_result_job 同样原样冻结。
- 其余未改动的模块级依赖复制自原模块命名空间；测试替换 ``_session`` 时须同时替换本模块。
"""
# ruff: noqa

from __future__ import annotations

from app.services import custom_qc_workspace_service as _workspace_module

globals().update(
    {key: value for key, value in vars(_workspace_module).items() if not key.startswith("__")}
)
from app.services.luxian_0609.record_result_read_model import (
    LatestRecordResultJobSelection,
    _record_ids,
    _text,
)
# 原模块自 customer_renderer 导入的静态版本号（读取侧版本化后已不再导入）。
from app.services.luxian_0609.customer_renderer import RULE_SET_VERSION


def select_latest_authoritative_record_result_job(
    candidates: Iterable[Mapping[str, Any]],
    *,
    record_id: str,
    rule_set_key: str,
    rule_set_version: str,
) -> LatestRecordResultJobSelection:
    """按任务身份选唯一权威任务，不以状态、文案或解释完整度裁决。

    上游已使用三坐标把候选限制为同一病历；本函数再只保留已完成、明确
    包含目标就诊号、且规则集与当前版本完全一致的任务。全院质控视图按
    跨创建者的最新完成代次选择；完成时间与创建时间均并列时无法确定当前
    代次，必须 fail-closed。
    """

    normalized_record_id = _text(record_id)
    normalized_rule_set_key = _text(rule_set_key)
    normalized_rule_set_version = _text(rule_set_version)
    if not all(
        (
            normalized_record_id,
            normalized_rule_set_key,
            normalized_rule_set_version,
        )
    ):
        raise ValueError("record_id、rule_set_key、rule_set_version 均不能为空")

    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        if _text(candidate.get("status")).lower() != "completed":
            continue
        if normalized_record_id not in _record_ids(candidate):
            continue
        if _rule_set_value(candidate, "rule_set_key") != normalized_rule_set_key:
            continue
        if _rule_set_value(candidate, "rule_set_version") != normalized_rule_set_version:
            continue
        eligible.append(dict(candidate))

    if not eligible:
        return LatestRecordResultJobSelection(
            state="not_found",
            reason_code="record_result_not_found",
            candidate_count=0,
        )

    newest_generation = max(_generation_key(candidate) for candidate in eligible)
    newest = [candidate for candidate in eligible if _generation_key(candidate) == newest_generation]
    if len(newest) != 1:
        return LatestRecordResultJobSelection(
            state="technical_error",
            reason_code="record_result_task_generation_conflict",
            candidate_count=len(newest),
        )
    return LatestRecordResultJobSelection(
        state="ready",
        reason_code="",
        job=newest[0],
        candidate_count=len(eligible),
    )


def _is_visible_luxian_customer_item(item: Dict[str, Any], *, enabled: bool) -> bool:
    if not enabled:
        return True
    rule_id = _customer_result_rule_id(item)
    if not rule_id or rule_id not in _luxian_0609_catalog_rule_ids():
        raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
    return rule_id not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS


def iter_unique_customer_result_source_items(
    job: Dict[str, Any],
    *,
    hmac_key: str,
    _validate_luxian: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """按统一优先级返回供 API、复核和导出共用的去重原始行集。"""

    validate_luxian = (
        _is_luxian_0609_export_job(job)
        if _validate_luxian is None
        else _validate_luxian
    )
    if validate_luxian:
        _validate_luxian_batch_rule_ids(job)

    children = [
        child
        for child in list(job.get("child_jobs") or job.get("children") or [])
        if isinstance(child, dict)
    ]
    sources = children or [job]
    raw_items: List[Dict[str, Any]] = []
    for source in sources:
        raw_items.extend(item for item in list(source.get("items") or []) if isinstance(item, dict))
    if not raw_items:
        summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
        for rule_result in list(summary.get("rule_results") or job.get("rule_results") or []):
            if isinstance(rule_result, dict):
                raw_items.extend(
                    item for item in list(rule_result.get("items") or []) if isinstance(item, dict)
                )
    # 同一父任务的分族子任务、重试残留或兼容路径都可能带来同一
    # record_ref + rule_id 的多条结果。客户结果必须是“一病历一规则一结论”，
    # 不能因为状态或原因码不同而把旧、新结论并排展示。
    unique_by_rule: Dict[tuple[str, str], tuple[tuple[int, int], Dict[str, Any]]] = {}
    for index, item in enumerate(raw_items):
        if not _is_visible_luxian_customer_item(item, enabled=validate_luxian):
            continue
        if not _is_current_rule_contract_result(item):
            continue
        is_current_luxian_canonical = (
            _safe_text(item.get("rule_id") or item.get("rule_code")).startswith("LX0609-")
            and _safe_text(item.get("schema_version")) == LUXIAN_0609_CUSTOMER_SCHEMA_VERSION
            and bool(_safe_text(item.get("status")))
            and bool(_safe_text(item.get("result_status")))
        )
        if validate_luxian and not is_current_luxian_canonical:
            # 旧批任务项没有 Canonical 交付合同。读取 API 明确隔离为既有
            # technical_error，绝不在此重算状态或客户结论，也不让单条旧项
            # 中断整个任务详情。
            source_item = {
                **item,
                "status": "technical_error",
                "result_status": "technical_error",
                "is_compliant": None,
                "reason_code": "canonical_result_envelope_invalid",
            }
        else:
            source_item = item
        projected = project_customer_safe_result_item(source_item, hmac_key=hmac_key)
        identity = (
            _safe_text(projected.get("record_ref")),
            _safe_text(projected.get("rule_id")),
        )
        # 规则专属事实/子结论比空泛历史状态更有权威性；在解释能力相同的
        # 情况下，保留输入序列中较后的候选，以适配同一任务内重跑后的追加结果。
        authority = (
            int(bool(projected.get("customer_display_facts") or projected.get("criterion_results"))),
            index,
        )
        current = unique_by_rule.get(identity)
        if current is None or authority > current[0]:
            unique_by_rule[identity] = (authority, source_item)
    return [item for _, item in unique_by_rule.values()]


def flatten_customer_safe_result_items(
    job: Dict[str, Any],
    *,
    hmac_key: str,
    _validate_luxian: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """按内部结果原顺序生成供 API、复核和全部导出共用的唯一行集。"""

    return [
        project_customer_safe_result_item(item, hmac_key=hmac_key)
        for item in iter_unique_customer_result_source_items(
            job,
            hmac_key=hmac_key,
            _validate_luxian=_validate_luxian,
        )
    ]


def _safe_review_report(
    value: Any,
    *,
    hmac_key: str,
    _validate_luxian: bool = False,
) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    findings: List[Dict[str, Any]] = []
    for raw_finding in list(value.get("findings") or []):
        if not isinstance(raw_finding, dict):
            continue
        # 复核 finding 是审核元数据，不是规则执行结果。直接投影其受控身份和
        # 状态字段，避免为了生成引用而伪造一条缺少解释事实的规则结果。
        rule_id = _customer_result_rule_id(raw_finding)
        if _validate_luxian:
            if not rule_id or rule_id not in _luxian_0609_catalog_rule_ids():
                raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
            if rule_id in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS:
                continue
        rule = get_luxian_0609_rule(rule_id) or {}
        canonical_status = _canonical_customer_status(
            {
                "status": raw_finding.get("original_status")
                or raw_finding.get("canonical_status")
                or raw_finding.get("status")
            }
        )
        existing_ref = _safe_text(raw_finding.get("record_ref"))
        record_ref = (
            existing_ref
            if re.fullmatch(r"rec_[0-9a-f]{24}", existing_ref)
            else _keyed_ref(
                "rec",
                raw_finding.get("finding_key") or rule_id,
                hmac_key=hmac_key,
            )
        )
        reason_code = _canonical_reason_code(
            {
                "reason_code": raw_finding.get("original_reason_code")
                or raw_finding.get("reason_code")
            }
        )
        severity = _safe_text(raw_finding.get("severity")).upper()
        risk_type = _safe_text(raw_finding.get("risk_type")).lower()
        suggested = _canonical_customer_status(
            {"status": raw_finding.get("suggested_status")}
        )
        findings.append(
            {
                "finding_ref": _keyed_ref(
                    "finding",
                    raw_finding.get("finding_key")
                    or f"{record_ref}:{rule_id}:{risk_type}",
                    hmac_key=hmac_key,
                ),
                "record_ref": record_ref,
                "rule_id": rule_id,
                "rule_name": _safe_text(
                    rule.get("rule_name") or rule.get("name"),
                    rule_id,
                ),
                "canonical_status": canonical_status,
                "reason_code": reason_code,
                "suggested_status": suggested,
                "severity": severity if severity in {"P0", "P1", "P2"} else "P2",
                "risk_type": (
                    risk_type
                    if _REASON_CODE_PATTERN.fullmatch(risk_type)
                    else "review_finding"
                ),
                "customer_message": _GENERIC_CUSTOMER_TEXT[suggested][0],
                "requires_human_review": bool(
                    raw_finding.get("requires_human_review", True)
                ),
            }
        )
    summary = {"total_findings": len(findings), "p0": 0, "p1": 0, "p2": 0}
    for finding in findings:
        summary[finding["severity"].lower()] += 1
    return {
        "review_status": _safe_text(value.get("review_status"), "completed"),
        "reviewed_at": _safe_text(value.get("reviewed_at")),
        "scope": _safe_text(value.get("scope")),
        "summary": summary,
        "findings": findings,
        "llm_review_status": _safe_text(value.get("llm_review_status"), "skipped"),
    }


def project_customer_safe_batch_job(
    job: Dict[str, Any],
    *,
    hmac_key: str,
    _validate_luxian: Optional[bool] = None,
) -> Dict[str, Any]:
    """生成 API/复核共用的客户任务 DTO，不回传原始 filters/summary 技术对象。"""

    validate_luxian = (
        _is_luxian_0609_export_job(job)
        if _validate_luxian is None
        else _validate_luxian
    )
    if validate_luxian:
        _validate_luxian_batch_rule_ids(job)
    items = flatten_customer_safe_result_items(
        job,
        hmac_key=hmac_key,
        _validate_luxian=validate_luxian,
    )
    status_counts: Dict[str, int] = {}
    for item in items:
        status = _safe_text(item.get("status"), "uncertain")
        status_counts[status] = status_counts.get(status, 0) + 1
    issue_refs = {
        _safe_text(item.get("record_ref"))
        for item in items
        if item.get("is_confirmed_issue") is True
    }
    raw_summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    progress = _safe_operational_progress(
        raw_summary.get("progress") or job.get("progress")
    )
    review_report = _safe_review_report(
        raw_summary.get("review_report"),
        hmac_key=hmac_key,
        _validate_luxian=validate_luxian,
    )
    safe_summary: Dict[str, Any] = {
        "total_records": _to_int(raw_summary.get("total_records"), _to_int(job.get("total_records"))),
        "success_count": _to_int(raw_summary.get("success_count"), _to_int(job.get("success_count"))),
        "failed_count": _to_int(raw_summary.get("failed_count"), _to_int(job.get("failed_count"))),
        "compliant_records": len(
            {
                _safe_text(item.get("record_ref"))
                for item in items
                if item.get("status") == "compliant"
            }
        ),
        "result_count": len(items),
        "issue_records": len(issue_refs),
        "status_counts": status_counts,
        "status_breakdown": status_counts,
        "display_status_counts": status_counts,
        "uncertain_records": len(
            {
                _safe_text(item.get("record_ref"))
                for item in items
                if item.get("status")
                in {"ai_suggested_non_compliant", "ai_suggested_compliant", "uncertain"}
            }
        ),
        "progress": progress,
        "progress_percent": progress.get("progress_percent", 0),
        "rule_count": _to_int(raw_summary.get("rule_count"), _to_int(job.get("rule_count"))),
        "customer_rule_count": _to_int(
            raw_summary.get("customer_rule_count")
            or filters.get("customer_rule_count")
            or job.get("customer_rule_count")
        ),
        "execution_rule_count": _to_int(
            raw_summary.get("execution_rule_count")
            or filters.get("execution_rule_count")
            or job.get("execution_rule_count")
        ),
        "processed_rule_count": _to_int(
            progress.get("processed_rule_count"),
            _to_int(raw_summary.get("processed_rule_count")),
        ),
        "retryable_rule_count": _to_int(raw_summary.get("retryable_rule_count")),
        "total_tokens": _to_int(raw_summary.get("total_tokens"), _to_int(job.get("total_tokens"))),
        "total_processing_time": _to_float(
            raw_summary.get("total_processing_time"),
            _to_float(job.get("total_processing_time")),
        ),
        "wall_clock_time": _to_float(
            raw_summary.get("wall_clock_time"),
            _to_float(job.get("wall_clock_time")),
        ),
        "history_issue_summaries": [
            {
                "rule_id": _safe_text(item.get("rule_id")),
                "status": _safe_text(item.get("status")),
                "text": _safe_text(item.get("conclusion")),
            }
            for item in items
            if item.get("status") == "non_compliant"
        ][:6],
    }
    if raw_summary.get("execution_status") in {"completed", "partial_failed", "failed"}:
        safe_summary["execution_status"] = raw_summary["execution_status"]
        for count_key in ("completed_rule_count", "failed_rule_count"):
            safe_summary[count_key] = max(0, _to_int(raw_summary.get(count_key)))
        safe_summary["failed_rule_ids"] = sorted({
            _safe_text(rule_id).upper()
            for rule_id in (raw_summary.get("failed_rule_ids") or [])
            if re.fullmatch(r"LX0609-\d{3}", _safe_text(rule_id).upper())
        })
    raw_automatic_retry = (
        raw_summary.get("automatic_failed_rule_retry")
        if isinstance(raw_summary.get("automatic_failed_rule_retry"), dict)
        else {}
    )
    automatic_retry_status = _safe_text(raw_automatic_retry.get("status")).lower()
    if automatic_retry_status in {
        "queued",
        "running",
        "completed",
        "exhausted",
        "not_applicable",
        "not_retryable",
    }:
        safe_automatic_retry: Dict[str, Any] = {
            "status": automatic_retry_status,
            "max_attempts": max(0, _to_int(raw_automatic_retry.get("max_attempts"))),
            "completed_attempts": max(
                0,
                _to_int(raw_automatic_retry.get("completed_attempts")),
            ),
            "remaining_failure_count": max(
                0,
                _to_int(raw_automatic_retry.get("remaining_failure_count")),
            ),
        }
        if isinstance(raw_automatic_retry.get("should_retry"), bool):
            safe_automatic_retry["should_retry"] = raw_automatic_retry["should_retry"]
        if raw_automatic_retry.get("next_attempt") is not None:
            safe_automatic_retry["next_attempt"] = max(
                0,
                _to_int(raw_automatic_retry.get("next_attempt")),
            )
        if raw_automatic_retry.get("delay_seconds") is not None:
            safe_automatic_retry["delay_seconds"] = max(
                0.0,
                _to_float(raw_automatic_retry.get("delay_seconds")),
            )
        safe_summary["automatic_failed_rule_retry"] = safe_automatic_retry
    model_counts = _normalize_luxian_model_execution_stats(raw_summary.get("model_execution_stats"))
    if model_counts is not None:
        safe_summary["model_execution_stats"] = _build_luxian_model_execution_summary(model_counts)
    raw_profile = (
        raw_summary.get("performance_profile")
        if isinstance(raw_summary.get("performance_profile"), dict)
        else {}
    )
    numeric_profile_keys = (
        "tokens_total",
        "prompt_tokens",
        "completion_tokens",
        "unattributed_tokens",
        "wall_clock_time_seconds",
        "total_processing_time_seconds",
        "llm_call_count",
        "program_call_count",
        "actual_llm_pack_call_count",
        "retry_count",
        "latency_p50_ms",
        "latency_p95_ms",
        "processing_p50_ms",
        "processing_p95_ms",
    )
    safe_performance_profile = {
        key: _to_float(raw_profile.get(key))
        if key.endswith(("_seconds", "_ms"))
        else _to_int(raw_profile.get(key))
        for key in numeric_profile_keys
        if raw_profile.get(key) is not None
    }
    if isinstance(raw_profile.get("token_breakdown_complete"), bool):
        safe_performance_profile["token_breakdown_complete"] = raw_profile[
            "token_breakdown_complete"
        ]
    safe_summary["performance_profile"] = safe_performance_profile
    safe_summary["total_tokens"] = _to_int(
        safe_performance_profile.get("tokens_total"),
        safe_summary["total_tokens"],
    )
    safe_summary["prompt_tokens"] = _to_int(
        safe_performance_profile.get("prompt_tokens"),
        _to_int(raw_summary.get("prompt_tokens")),
    )
    safe_summary["completion_tokens"] = _to_int(
        safe_performance_profile.get("completion_tokens"),
        _to_int(raw_summary.get("completion_tokens")),
    )
    safe_summary["unattributed_tokens"] = _to_int(
        safe_performance_profile.get("unattributed_tokens"),
        _to_int(raw_summary.get("unattributed_tokens")),
    )
    safe_summary["llm_call_count"] = _to_int(
        safe_performance_profile.get("llm_call_count"),
        _to_int(raw_summary.get("llm_call_count")),
    )
    safe_summary["retry_count"] = _to_int(
        safe_performance_profile.get("retry_count"),
        _to_int(raw_summary.get("retry_count")),
    )
    if review_report:
        safe_summary["review_report"] = review_report
    safe_rule_results: List[Dict[str, Any]] = []
    for raw_rule in list(job.get("rule_results") or []):
        if not isinstance(raw_rule, dict):
            continue
        raw_rule_id = _customer_result_rule_id(raw_rule)
        if validate_luxian:
            if not raw_rule_id or raw_rule_id not in _luxian_0609_catalog_rule_ids():
                raise ValueError(LX0609_CUSTOMER_RESULT_CONTRACT_ERROR)
            if raw_rule_id in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS:
                continue
        raw_rule_items = [
            project_customer_safe_result_item(item, hmac_key=hmac_key)
            for item in list(raw_rule.get("items") or [])
            if isinstance(item, dict)
            and _is_visible_luxian_customer_item(item, enabled=validate_luxian)
            and _is_current_rule_contract_result(item)
        ]
        safe_rule_results.append(
            {
                "id": _safe_text(raw_rule.get("id")),
                "job_id": _safe_text(raw_rule.get("job_id")),
                "rule_code": _safe_text(raw_rule.get("rule_code")).upper(),
                "rule_name": _safe_text(raw_rule.get("rule_name")),
                "status": _safe_text(raw_rule.get("status")).lower(),
                "progress": _safe_operational_progress(raw_rule.get("progress")),
                "items": raw_rule_items,
                "total_records": _to_int(raw_rule.get("total_records")),
                "success_count": _to_int(raw_rule.get("success_count")),
                "failed_count": _to_int(raw_rule.get("failed_count")),
                "issue_records": len(
                    {
                        _safe_text(item.get("record_ref"))
                        for item in raw_rule_items
                        if item.get("is_confirmed_issue") is True
                    }
                ),
            }
        )
    safe_children = [
        project_customer_safe_batch_job(
            child,
            hmac_key=hmac_key,
            _validate_luxian=validate_luxian,
        )
        for child in list(job.get("child_jobs") or job.get("children") or [])
        if isinstance(child, dict)
    ]
    failed_records = [
        {
            "record_ref": project_customer_safe_result_item(
                {
                    **item,
                    "status": "technical_error",
                    "reason_code": "record_execution_failed",
                },
                hmac_key=hmac_key,
            )["record_ref"],
            "status": "technical_error",
            "reason_code": "record_execution_failed",
            "rule_id": _safe_text(item.get("rule_id")).upper()
            if re.fullmatch(r"LX0609-\d{3}", _safe_text(item.get("rule_id")).upper()) else "",
        }
        for item in list(job.get("failed_records") or [])
        if isinstance(item, dict)
    ]
    if safe_summary.get("execution_status") in {"partial_failed", "failed"}:
        failed_refs = {failure["record_ref"] for failure in failed_records}
        safe_summary["compliant_records"] = len({
            _safe_text(item.get("record_ref"))
            for item in items
            if item.get("status") == "compliant" and item.get("record_ref") not in failed_refs
        })
    item_record_refs = {
        _safe_text(item.get("record_ref"))
        for item in items
        if _safe_text(item.get("record_ref"))
    }
    safe_record_focus = (
        {"record_ref": next(iter(item_record_refs))}
        if len(item_record_refs) == 1
        else None
    )
    execution_scope_hash = _safe_text(filters.get("execution_scope_hash")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", execution_scope_hash):
        execution_scope_hash = ""
    return {
        "schema_version": "customer-qc-job-v1",
        "id": _safe_text(job.get("id")),
        "job_id": _safe_text(job.get("id")),
        "operation_ref": _keyed_ref("op", job.get("id"), hmac_key=hmac_key),
        "execution_scope_hash": execution_scope_hash,
        "deduplicated": bool(filters.get("deduplicated") or job.get("idempotency_reused")),
        "status": _safe_text(job.get("status")).lower(),
        "draft_id": _safe_text(job.get("draft_id")),
        "job_kind": _safe_text(job.get("job_kind")),
        "parent_job_id": _safe_text(job.get("parent_job_id")),
        "child_job_ids": [
            _safe_text(value)
            for value in list(job.get("child_job_ids") or [])
            if _safe_text(value)
        ],
        "rule_code": _safe_text(job.get("rule_code")).upper(),
        "rule_name": _safe_text(job.get("rule_name")),
        "scene": _safe_text(job.get("scene")),
        "scope": _safe_text(job.get("scope")),
        "execution_mode": _safe_text(job.get("execution_mode"), "batch"),
        "progress": progress,
        "created_at": _safe_text(job.get("created_at")),
        "started_at": _safe_text(job.get("started_at")),
        "finished_at": _safe_text(job.get("finished_at")),
        "updated_at": _safe_text(job.get("updated_at")),
        "total_records": safe_summary["total_records"],
        "success_count": safe_summary["success_count"],
        "failed_count": safe_summary["failed_count"],
        "issue_records": safe_summary["issue_records"],
        "compliant_records": safe_summary["compliant_records"],
        "rule_count": safe_summary["rule_count"],
        "customer_rule_count": safe_summary["customer_rule_count"],
        "execution_rule_count": safe_summary["execution_rule_count"],
        "total_tokens": safe_summary["total_tokens"],
        "prompt_tokens": safe_summary["prompt_tokens"],
        "completion_tokens": safe_summary["completion_tokens"],
        "unattributed_tokens": safe_summary["unattributed_tokens"],
        "llm_call_count": safe_summary["llm_call_count"],
        "retry_count": safe_summary["retry_count"],
        "total_processing_time": safe_summary["total_processing_time"],
        "wall_clock_time": safe_summary["wall_clock_time"],
        "rule_set_key": _safe_text(
            filters.get("rule_set_key")
            or filters.get("rule_set_id")
            or job.get("rule_set_key")
            or job.get("rule_set_id")
            or raw_summary.get("rule_set_key")
            or raw_summary.get("rule_set_id")
        ),
        "rule_set_name": _safe_text(
            filters.get("rule_set_name") or raw_summary.get("rule_set_name")
        ),
        "rule_set_version": _safe_text(
            filters.get("rule_set_version") or raw_summary.get("rule_set_version")
        ),
        "draft_ids": [
            _safe_text(value)
            for value in list(
                filters.get("selected_rule_ids")
                or filters.get("rule_ids")
                or job.get("draft_ids")
                or []
            )
            if _safe_text(value)
        ],
        "summary": safe_summary,
        "items": items,
        "failed_records": failed_records,
        "rule_results": safe_rule_results,
        "child_jobs": safe_children,
        "children": safe_children,
        "record_focus": safe_record_focus,
    }


def build_latest_single_record_result_dto(
    self,
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
    rule_set_version: str = RULE_SET_VERSION,
    expected_rule_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """读取一份病历当前规则代次的唯一客户结果。

    这是单病历结果页唯一允许使用的读取入口。候选首先由三坐标
    ``institute_id + patient_id + visit_id`` 限定，再从全院所有创建者中
    选择已为该病历写入 Canonical Envelope 的当前规则代次最新唯一根任务；
    不得以批次整体状态、文案丰富度、证据数量或完整度替换较新的任务。
    """

    normalized_institute_id = _safe_text(institute_id)
    normalized_patient_id = _safe_text(patient_id)
    normalized_visit_id = _safe_text(visit_id)
    normalized_rule_set_key = _safe_text(rule_set_key)
    normalized_rule_set_version = _safe_text(rule_set_version)
    expected_rule_ids_for_count = [
        _safe_text(rule_id).upper()
        for rule_id in list(expected_rule_ids or [])
        if _safe_text(rule_id)
        and _safe_text(rule_id).upper() not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
    ]
    if not expected_rule_ids_for_count:
        expected_rule_ids_for_count = [
            _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            for item in load_luxian_0609_rules()
            if _safe_text(item.get("rule_id") or item.get("rule_code"))
            and _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        ]
    if not all(
        (
            normalized_institute_id,
            normalized_patient_id,
            normalized_visit_id,
            normalized_rule_set_key,
            normalized_rule_set_version,
        )
    ):
        raise ValueError("单病历结果读取缺少三坐标身份或规则集参数")

    session = _session()
    try:
        root_rows = (
            session.execute(
                select(self._batch_job_table)
                .join(
                    self._record_result_envelope_table,
                    self._record_result_envelope_table.c.root_job_id
                    == self._batch_job_table.c.id,
                )
                .where(
                    and_(
                        self._batch_job_table.c.status.in_(
                            ("completed", "failed", "running", "queued", "canceled")
                        ),
                        or_(
                            self._batch_job_table.c.parent_job_id.is_(None),
                            self._batch_job_table.c.parent_job_id == "",
                        ),
                        self._record_result_envelope_table.c.institute_id
                        == normalized_institute_id,
                        self._record_result_envelope_table.c.patient_id
                        == normalized_patient_id,
                        self._record_result_envelope_table.c.visit_id == normalized_visit_id,
                        self._record_result_envelope_table.c.rule_set_key
                        == normalized_rule_set_key,
                        self._record_result_envelope_table.c.rule_set_version
                        == normalized_rule_set_version,
                    )
                )
                .distinct()
                .order_by(
                    desc(self._batch_job_table.c.finished_at),
                    desc(self._batch_job_table.c.created_at),
                )
            )
            .mappings()
            .all()
        )
        candidates = []
        for row in root_rows:
            candidate = self._aggregate_parent_job(
                session,
                _row_to_batch_job(dict(row)),
            )
            if _safe_text(candidate.get("status")).lower() != "completed":
                # 批次可因其他病历失败、取消或仍在收尾，但精确 Envelope 的
                # 存在已证明当前病历独立交付完成。这里只投影读取状态，不改库。
                candidate = {**candidate, "status": "completed"}
            candidates.append(candidate)
        selection = select_latest_authoritative_record_result_job(
            candidates,
            record_id=normalized_visit_id,
            rule_set_key=normalized_rule_set_key,
            rule_set_version=normalized_rule_set_version,
        )
        if selection.state != "ready" or not isinstance(selection.job, dict):
            return {
                "schema_version": "lx0609-single-record-result-v1",
                "state": selection.state,
                "reason_code": selection.reason_code,
                "record_ref": "",
                "job_id": "",
                "items": [],
                "expected_rule_count": len(expected_rule_ids_for_count),
                "result_rule_count": 0,
                "is_complete": False,
            }

        selected_job = selection.job
        envelope, envelope_id = self._load_record_result_envelope_with_id(
            session,
            root_job_id=_safe_text(selected_job.get("id")),
            institute_id=normalized_institute_id,
            patient_id=normalized_patient_id,
            visit_id=normalized_visit_id,
            rule_set_key=normalized_rule_set_key,
            rule_set_version=normalized_rule_set_version,
        )
        if not envelope:
            return {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "technical_error",
                "reason_code": "canonical_result_envelope_missing",
                "data_origin": "canonical_result_envelope",
                "record_ref": "",
                "job_id": _safe_text(selected_job.get("id")),
                "items": [],
                "expected_rule_count": len(expected_rule_ids_for_count),
                "result_rule_count": 0,
                "is_complete": False,
            }
        raw_items = envelope.get("items")
        resolved_expected_rule_ids = list(
            dict.fromkeys(
                _safe_text(rule_id).upper()
                for rule_id in expected_rule_ids_for_count
                if _safe_text(rule_id)
            )
        )
        if not resolved_expected_rule_ids:
            resolved_expected_rule_ids = [
                _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                for item in load_luxian_0609_rules()
                if _safe_text(item.get("rule_id") or item.get("rule_code"))
                and _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
                not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
            ]
        if not _canonical_envelope_items_are_consistent(raw_items):
            return {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "technical_error",
                "reason_code": "canonical_result_envelope_invalid",
                "data_origin": "canonical_result_envelope",
                "record_ref": "",
                "job_id": _safe_text(selected_job.get("id")),
                "items": [],
                "expected_rule_count": len(resolved_expected_rule_ids),
                "result_rule_count": 0,
                "is_complete": False,
            }
        raw_rule_ids = [
            _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            for item in raw_items
        ]
        if normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY:
            unexpected_rule_ids = sorted(
                set(raw_rule_ids) - _luxian_0609_catalog_rule_ids()
            )
            if unexpected_rule_ids:
                return {
                    "schema_version": "lx0609-single-record-result-v1",
                    "state": "technical_error",
                    "reason_code": "canonical_result_envelope_invalid",
                    "data_origin": "canonical_result_envelope",
                    "record_ref": "",
                    "job_id": _safe_text(selected_job.get("id")),
                    "items": [],
                    "expected_rule_count": len(resolved_expected_rule_ids),
                    "result_rule_count": 0,
                    "is_complete": False,
                }
        items = [
            dict(item)
            for item in raw_items
            if _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        ]
        delivered_rule_ids = [
            _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            for item in items
        ]
        valid_rule_ids = [rule_id for rule_id in delivered_rule_ids if rule_id]
        conflicting_rule_ids = sorted(
            rule_id
            for rule_id in set(valid_rule_ids)
            if valid_rule_ids.count(rule_id) > 1
        )
        rule_master_by_id = {
            entry.rule_id: entry for entry in load_luxian_0609_rule_master()
        }
        projected_items = []
        for item, rule_id in zip(items, valid_rule_ids):
            projected_item = dict(item)
            master_entry = rule_master_by_id.get(rule_id)
            if master_entry is not None:
                projected_item["source_document"] = master_entry.source_document
                projected_item["qc_point"] = master_entry.qc_point
            projected_items.append(projected_item)

        missing_rule_ids = [
            rule_id for rule_id in resolved_expected_rule_ids if rule_id not in set(valid_rule_ids)
        ]
        return {
            "schema_version": "lx0609-single-record-result-v1",
            "state": "ready",
            "reason_code": "",
            "data_origin": "canonical_result_envelope",
            "record_ref": _safe_text(envelope.get("record_ref")),
            "job_id": _safe_text(selected_job.get("id")),
            # 仅供病历审核锚定结果对象，不改变选择行为；前端不展示。
            "root_job_id": _safe_text(selected_job.get("id")),
            "envelope_id": envelope_id,
            "rule_set_key": normalized_rule_set_key,
            "rule_set_version": normalized_rule_set_version,
            "items": projected_items,
            "expected_rule_count": len(resolved_expected_rule_ids),
            "result_rule_count": len(items),
            "is_complete": not missing_rule_ids and not conflicting_rule_ids,
            "missing_rule_ids": missing_rule_ids,
            "conflicting_rule_ids": sorted(conflicting_rule_ids),
        }
    finally:
        session.close()


def build_luxian_0609_completed_record_result_summaries(
    self,
    *,
    record_refs: Sequence[Mapping[str, Any]],
    rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
    rule_set_version: str = RULE_SET_VERSION,
    session_factory: Optional[Callable[[], Session]] = None,
    include_items: bool = False,
) -> Dict[tuple[str, str, str], Dict[str, Any]]:
    """批量读取病历池可展示的最新 Canonical 结果摘要。

    只读取完成的根任务及其显式 Envelope。它不会读取 legacy items、Bundle
    或 QCResult；无法以三坐标确认的结果不允许进入 ``ready`` 状态。
    """

    identities = {
        (
            _safe_text(ref.get("institute_id")),
            _safe_text(ref.get("patient_id")),
            _safe_text(ref.get("visit_id")),
        )
        for ref in record_refs
        if isinstance(ref, Mapping)
    }
    identities = {identity for identity in identities if all(identity)}
    if not identities:
        return {}

    normalized_rule_set_key = _safe_text(rule_set_key)
    normalized_rule_set_version = _safe_text(rule_set_version)
    if not normalized_rule_set_key or not normalized_rule_set_version:
        raise ValueError("病历池结果摘要缺少规则集身份")

    visit_ids = sorted({identity[2] for identity in identities})
    escaped_visit_ids = {
        visit_id: visit_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace('"', '\\"')
        for visit_id in visit_ids
    }
    record_id_conditions = [
        self._batch_job_table.c.record_ids_json.ilike(
            f'%"{escaped_visit_ids[visit_id]}"%',
            escape="\\",
        )
        for visit_id in visit_ids
    ]
    # 规则集身份仍由 Python 做精确校验；这里仅以文本预筛掉与当前 LX0609
    # 代次无关的历史任务，避免全院首页解析大批无关 filters/summary JSON。
    # 两处都保留，是为了维持读取模型“filters 优先、summary 兼容回退”的合同。
    filters_rule_set_candidate = self._batch_job_table.c.filters_json.ilike(
        f"%{normalized_rule_set_key}%"
    )
    filters_rule_version_candidate = self._batch_job_table.c.filters_json.ilike(
        f"%{normalized_rule_set_version}%"
    )
    summary_rule_set_candidate = self._batch_job_table.c.summary_json.ilike(
        f"%{normalized_rule_set_key}%"
    )
    summary_rule_version_candidate = self._batch_job_table.c.summary_json.ilike(
        f"%{normalized_rule_set_version}%"
    )
    rule_set_candidate = or_(filters_rule_set_candidate, summary_rule_set_candidate)
    rule_version_candidate = or_(filters_rule_version_candidate, summary_rule_version_candidate)
    session = (session_factory or _session)()
    try:
        base_job_predicate = and_(
            self._batch_job_table.c.status.in_(
                ("completed", "failed", "running", "queued", "canceled")
            ),
            or_(
                self._batch_job_table.c.parent_job_id.is_(None),
                self._batch_job_table.c.parent_job_id == "",
            ),
            or_(*record_id_conditions),
        )
        job_columns = (
            self._batch_job_table.c.id,
            self._batch_job_table.c.status,
            self._batch_job_table.c.created_at,
            self._batch_job_table.c.finished_at,
            self._batch_job_table.c.filters_json,
            self._batch_job_table.c.record_ids_json,
            # filters_json 已包含当前规则集身份时，避免读取可能很大的
            # summary_json TOAST 值；旧任务才保留摘要兼容回退。
            case(
                (
                    and_(filters_rule_set_candidate, filters_rule_version_candidate),
                    None,
                ),
                else_=self._batch_job_table.c.summary_json,
            ).label("summary_json"),
        )
        # 新任务的规则集身份保存在 filters_json。病历池只需要选择字段，
        # 只有 filters_json 不完整的旧任务才会通过 CASE 读取 summary_json。
        job_rows = (
            session.execute(
                select(*job_columns).where(
                    and_(base_job_predicate, rule_set_candidate, rule_version_candidate)
                )
            )
            .mappings()
            .all()
        )
        # 首页/病历池只需要“选择当前 Canonical 结果”的最小任务字段。
        # 不能为每个候选完整反序列化 items、子任务和运行摘要；真实全院范围
        # 会把同一批任务 JSON 反复解析数十万次，且不会增加任何判定事实。
        jobs_by_id: Dict[str, Dict[str, Any]] = {}
        current_jobs_by_visit: Dict[str, list[Dict[str, Any]]] = {}
        requested_visit_ids = set(visit_ids)
        for raw_row in job_rows:
            row = dict(raw_row)
            job_id = _safe_text(row.get("id"))
            if not job_id:
                continue
            raw_filters = row.get("filters")
            raw_summary = row.get("summary")
            raw_filters_text = _safe_text(row.get("filters_json"))
            raw_summary_text = _safe_text(row.get("summary_json"))
            if (
                not isinstance(raw_filters, dict)
                and not isinstance(raw_summary, dict)
                and (
                    normalized_rule_set_key not in raw_filters_text
                    and normalized_rule_set_key not in raw_summary_text
                    or normalized_rule_set_version not in raw_filters_text
                    and normalized_rule_set_version not in raw_summary_text
                )
            ):
                continue
            filters = (
                raw_filters
                if isinstance(raw_filters, dict)
                else _safe_json_loads(row.get("filters_json"), {})
            )
            filters_dict = filters if isinstance(filters, dict) else {}
            filter_rule_set_key = _safe_text(filters_dict.get("rule_set_key"))
            filter_rule_set_version = _safe_text(filters_dict.get("rule_set_version"))
            if (
                (
                    filter_rule_set_key
                    and filter_rule_set_key != normalized_rule_set_key
                )
                or (
                    filter_rule_set_version
                    and filter_rule_set_version != normalized_rule_set_version
                )
            ):
                continue
            summary = (
                raw_summary
                if isinstance(raw_summary, dict)
                # filters 已具备当前规则集身份时，summary 不会参与读取模型的
                # 选择；避免解析其中可能很大的运行态/明细 JSON。
                else (
                    None
                    if (
                        filter_rule_set_key == normalized_rule_set_key
                        and filter_rule_set_version == normalized_rule_set_version
                    )
                    else _safe_json_loads(row.get("summary_json"), None)
                )
            )
            raw_record_ids = row.get("record_ids")
            record_ids = (
                raw_record_ids
                if isinstance(raw_record_ids, list)
                else _safe_json_loads(row.get("record_ids_json"), [])
            )
            job = {
                "id": job_id,
                "status": _safe_text(row.get("status"), "queued"),
                "created_at": row.get("created_at"),
                "finished_at": row.get("finished_at"),
                "record_ids": record_ids if isinstance(record_ids, list) else [],
                "filters": filters if isinstance(filters, dict) else {},
                "summary": summary if isinstance(summary, dict) else None,
            }
            jobs_by_id[job_id] = job
            if (
                _rule_set_value(job, "rule_set_key") != normalized_rule_set_key
                or _rule_set_value(job, "rule_set_version") != normalized_rule_set_version
            ):
                continue
            for visit_id in set(_safe_text(value) for value in job["record_ids"]):
                if (
                    visit_id in requested_visit_ids
                    and _safe_text(job.get("status")).lower() == "completed"
                ):
                    current_jobs_by_visit.setdefault(visit_id, []).append(job)
        if not jobs_by_id:
            return {identity: {"status": "not_run"} for identity in identities}

        envelope_rows = (
            session.execute(
                select(self._record_result_envelope_table).where(
                    and_(
                        self._record_result_envelope_table.c.root_job_id.in_(list(jobs_by_id)),
                        self._record_result_envelope_table.c.visit_id.in_(visit_ids),
                    )
                )
            )
            .mappings()
            .all()
        )
        envelopes_by_identity: Dict[tuple[str, str, str], Dict[str, list[Dict[str, Any]]]] = {}
        current_envelopes_by_job_visit: Dict[tuple[str, str], list[Dict[str, Any]]] = {}
        for raw_row in envelope_rows:
            row = dict(raw_row)
            identity = (
                _safe_text(row.get("institute_id")),
                _safe_text(row.get("patient_id")),
                _safe_text(row.get("visit_id")),
            )
            job_id = _safe_text(row.get("root_job_id"))
            if not job_id or not all(identity):
                continue
            if (
                _safe_text(row.get("rule_set_key")) == normalized_rule_set_key
                and _safe_text(row.get("rule_set_version")) == normalized_rule_set_version
            ):
                current_envelopes_by_job_visit.setdefault((job_id, identity[2]), []).append(row)
                if identity in identities:
                    envelopes_by_identity.setdefault(identity, {}).setdefault(job_id, []).append(row)

        ambiguous_current_jobs_by_visit: Dict[str, list[Dict[str, Any]]] = {}
        for visit_id, candidates in current_jobs_by_visit.items():
            ambiguous_current_jobs_by_visit[visit_id] = [
                job
                for job in candidates
                if not current_envelopes_by_job_visit.get((_safe_text(job.get("id")), visit_id), [])
            ]

        projections: Dict[tuple[str, str, str], Dict[str, Any]] = {}
        for identity in identities:
            _, _, visit_id = identity
            exact_envelopes = envelopes_by_identity.get(identity, {})
            ready_candidates: list[Dict[str, Any]] = []
            for job_id, record_envelopes in exact_envelopes.items():
                if job_id not in jobs_by_id:
                    continue
                candidate = dict(jobs_by_id[job_id])
                if _safe_text(candidate.get("status")).lower() != "completed":
                    # Canonical Envelope 的存在只代表这一份病历已经完整交付。
                    # 选择器仍坚持 completed 合同，因此在本次单病历选择范围内
                    # 将任务投影为完成，并用 Envelope 写入时间作为完成时间。
                    delivered_at = [
                        envelope.get("updated_at")
                        for envelope in record_envelopes
                        if envelope.get("updated_at") is not None
                    ]
                    candidate["status"] = "completed"
                    if delivered_at:
                        candidate["finished_at"] = max(
                            delivered_at,
                            key=lambda value: str(value),
                        )
                ready_candidates.append(candidate)
            ready_selection = select_latest_authoritative_record_result_job(
                ready_candidates,
                record_id=visit_id,
                rule_set_key=normalized_rule_set_key,
                rule_set_version=normalized_rule_set_version,
            )
            # 只有当前规则版本、且没有任何当前版本同 visit Envelope 的根任务
            # 才是无法确认三坐标归属的缺失候选。旧版本 Envelope 完全不参与
            # 当前代次选择，也不能遮蔽当前版本的交付缺口。
            ambiguous_candidates = ambiguous_current_jobs_by_visit.get(visit_id, [])
            if ready_selection.state == "technical_error":
                projections[identity] = {
                    "status": "technical_error",
                    "reason_code": "generation_conflict",
                }
                continue
            if ready_selection.state == "ready" and isinstance(ready_selection.job, dict):
                ready_generation = _generation_key(ready_selection.job)
                ambiguous_generation = max(
                    (_generation_key(job) for job in ambiguous_candidates),
                    default=None,
                )
                if ambiguous_generation is not None and ambiguous_generation >= ready_generation:
                    projections[identity] = {
                        "status": "technical_error",
                        "reason_code": "canonical_envelope_missing",
                    }
                    continue
                selected_job_id = _safe_text(ready_selection.job.get("id"))
                selected_envelopes = exact_envelopes.get(selected_job_id, [])
                if len(selected_envelopes) != 1:
                    projections[identity] = {
                        "status": "technical_error",
                        "reason_code": "canonical_result_envelope_invalid",
                    }
                    continue
                summary = _summarize_completed_record_result_envelope(
                    envelope_row=selected_envelopes[0],
                    completed_at=ready_selection.job.get("finished_at"),
                    include_items=include_items,
                    rule_set_key=normalized_rule_set_key,
                )
                if summary.get("status") == "ready":
                    # 仅供病历审核锚定结果对象，不改变选择行为；病历池输出会按白名单裁剪。
                    summary["root_job_id"] = selected_job_id
                    summary["envelope_id"] = _safe_text(selected_envelopes[0].get("id"))
                projections[identity] = summary
                continue

            # 仅以 visit_id 保存的历史根任务不能形成 ready。若该任务已有同
            # visit 的其他三坐标 Envelope，明确排除，避免把别的病历标记为缺失。
            ambiguous_selection = select_latest_authoritative_record_result_job(
                ambiguous_candidates,
                record_id=visit_id,
                rule_set_key=normalized_rule_set_key,
                rule_set_version=normalized_rule_set_version,
            )
            if ambiguous_selection.state == "technical_error":
                projections[identity] = {
                    "status": "technical_error",
                    "reason_code": "generation_conflict",
                }
            elif ambiguous_selection.state == "ready":
                projections[identity] = {
                    "status": "technical_error",
                    "reason_code": "canonical_envelope_missing",
                }
            else:
                projections[identity] = {"status": "not_run"}
        return projections
    finally:
        session.close()


def _summarize_completed_record_result_envelope(
    *,
    envelope_row: Mapping[str, Any],
    completed_at: Any,
    include_items: bool = False,
    rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
) -> Dict[str, Any]:
    """把一份通过结构校验的 Canonical Envelope 缩减为病历池摘要。"""

    envelope = _safe_json_loads(envelope_row.get("envelope_json"), {})
    if (
        not isinstance(envelope, dict)
        or envelope.get("schema_version") != _RECORD_RESULT_ENVELOPE_SCHEMA
        or envelope.get("delivery_mode") != _CANONICAL_RESULT_DELIVERY_MODE
        or not isinstance(envelope.get("items"), list)
    ):
        return {
            "status": "technical_error",
            "reason_code": "canonical_result_envelope_invalid",
        }

    if not _canonical_envelope_items_are_consistent(envelope["items"]):
        return {
            "status": "technical_error",
            "reason_code": "canonical_result_envelope_invalid",
        }

    if _safe_text(rule_set_key) == LUXIAN_0609_RULE_SET_KEY:
        envelope_rule_ids = {
            _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            for item in envelope["items"]
        }
        if envelope_rule_ids - _luxian_0609_catalog_rule_ids():
            return {
                "status": "technical_error",
                "reason_code": "canonical_result_envelope_invalid",
            }

    excluded_rule_ids = (
        LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        if _safe_text(rule_set_key) == LUXIAN_0609_RULE_SET_KEY
        else frozenset()
    )
    visible_items = [
        item
        for item in envelope["items"]
        if _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
        not in excluded_rule_ids
    ]

    status_counts: Dict[str, int] = {}
    for item in visible_items:
        status = _safe_text(item.get("status"))
        status_counts[status] = status_counts.get(status, 0) + 1
    if isinstance(completed_at, datetime):
        completed_at_value = completed_at.isoformat()
    else:
        completed_at_value = _safe_text(completed_at)
    result: Dict[str, Any] = {
        "status": "ready",
        "completed_at": completed_at_value or None,
        "total_rule_count": len(visible_items),
        "status_counts": dict(sorted(status_counts.items())),
    }
    if include_items:
        rule_master_by_id = {
            entry.rule_id: entry for entry in load_luxian_0609_rule_master()
        }
        projected_items: List[Dict[str, Any]] = []
        for item in visible_items:
            projected_item = dict(item)
            rule_id = _safe_text(
                projected_item.get("rule_id") or projected_item.get("rule_code")
            ).upper()
            master_entry = rule_master_by_id.get(rule_id)
            if master_entry is not None:
                projected_item["source_document"] = master_entry.source_document
                projected_item["qc_point"] = master_entry.qc_point
            projected_items.append(projected_item)
        result.update(
            {
                "record_ref": _safe_text(envelope.get("record_ref")),
                "items": projected_items,
            }
        )
    return result


def build_latest_luxian_0609_record_result_dtos(
    self,
    *,
    record_refs: Sequence[Mapping[str, Any]],
    rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
    rule_set_version: str = RULE_SET_VERSION,
    session_factory: Optional[Callable[[], Session]] = None,
) -> Dict[tuple[str, str, str], Dict[str, Any]]:
    """一次读取一组病历的最新 Canonical 完整结果，供服务端全量导出。"""

    projections = build_luxian_0609_completed_record_result_summaries(
        self,
        record_refs=record_refs,
        rule_set_key=rule_set_key,
        rule_set_version=rule_set_version,
        session_factory=session_factory,
        include_items=True,
    )
    expected_rule_ids = [
        _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
        for item in load_luxian_0609_rules()
        if _safe_text(item.get("rule_id") or item.get("rule_code"))
        and _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
        not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
    ]
    results: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    for identity, projection in projections.items():
        status = _safe_text(projection.get("status"))
        if status != "ready":
            results[identity] = {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "not_found" if status == "not_run" else "technical_error",
                "reason_code": _safe_text(projection.get("reason_code")),
                "record_ref": "",
                "items": [],
                "expected_rule_count": len(expected_rule_ids),
                "result_rule_count": 0,
                "is_complete": False,
            }
            continue
        items = [
            dict(item)
            for item in projection.get("items") or []
            if isinstance(item, dict)
            and _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        ]
        delivered_rule_ids = {
            _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
            for item in items
            if _safe_text(item.get("rule_id") or item.get("rule_code"))
        }
        missing_rule_ids = [
            rule_id for rule_id in expected_rule_ids if rule_id not in delivered_rule_ids
        ]
        results[identity] = {
            "schema_version": "lx0609-single-record-result-v1",
            "state": "ready",
            "data_origin": "canonical_result_envelope",
            "record_ref": _safe_text(projection.get("record_ref")),
            # 与单病历 DTO 同源同义：仅供病历审核锚定结果对象，不改变选择行为、不进入工作簿。
            "root_job_id": _safe_text(projection.get("root_job_id")),
            "envelope_id": _safe_text(projection.get("envelope_id")),
            "rule_set_key": rule_set_key,
            "rule_set_version": rule_set_version,
            "items": items,
            "expected_rule_count": len(expected_rule_ids),
            "result_rule_count": len(items),
            "is_complete": not missing_rule_ids,
            "missing_rule_ids": missing_rule_ids,
        }
    return results


def find_terminal_reevaluation_candidates(
    self,
    *,
    record_refs: Sequence[CaseRefInput],
    rule_set_key: str = LUXIAN_0609_RULE_SET_KEY,
    rule_set_version: str = RULE_SET_VERSION,
    session_factory: Optional[Callable[[], Session]] = None,
) -> tuple[CaseRef, ...]:
    """筛出已有运行期结果、且尚未启动终末复评的出院病历。"""

    normalized_refs = normalize_case_refs(record_refs)
    if not normalized_refs:
        return ()
    normalized_rule_set_key = _safe_text(rule_set_key)
    normalized_rule_set_version = _safe_text(rule_set_version)
    if not normalized_rule_set_key or not normalized_rule_set_version:
        raise ValueError("终末复评候选读取缺少规则集参数")

    identities = [
        (ref.institute_id, ref.patient_id, ref.visit_id) for ref in normalized_refs
    ]
    session = (session_factory or _session)()
    try:
        completed_rows = (
            session.execute(
                select(
                    self._batch_job_table.c.id,
                    self._batch_job_table.c.scope,
                    self._batch_job_table.c.status,
                    self._batch_job_table.c.created_at,
                    self._batch_job_table.c.finished_at,
                    self._batch_job_table.c.filters_json,
                    self._record_result_envelope_table.c.institute_id,
                    self._record_result_envelope_table.c.patient_id,
                    self._record_result_envelope_table.c.visit_id,
                )
                .join(
                    self._record_result_envelope_table,
                    self._record_result_envelope_table.c.root_job_id
                    == self._batch_job_table.c.id,
                )
                .where(
                    and_(
                        self._batch_job_table.c.status == "completed",
                        or_(
                            self._batch_job_table.c.parent_job_id.is_(None),
                            self._batch_job_table.c.parent_job_id == "",
                        ),
                        self._record_result_envelope_table.c.rule_set_key
                        == normalized_rule_set_key,
                        self._record_result_envelope_table.c.rule_set_version
                        == normalized_rule_set_version,
                        tuple_(
                            self._record_result_envelope_table.c.institute_id,
                            self._record_result_envelope_table.c.patient_id,
                            self._record_result_envelope_table.c.visit_id,
                        ).in_(identities),
                    )
                )
                .order_by(
                    desc(self._batch_job_table.c.finished_at),
                    desc(self._batch_job_table.c.created_at),
                )
            )
            .mappings()
            .all()
        )
        active_final_rows = (
            session.execute(
                select(
                    self._batch_job_table.c.scope,
                    self._batch_job_table.c.status,
                    self._batch_job_table.c.filters_json,
                ).where(
                    and_(
                        self._batch_job_table.c.status.in_(["queued", "running"]),
                        self._batch_job_table.c.filters_json.ilike(
                            f"%{normalized_rule_set_key}%"
                        ),
                        self._batch_job_table.c.filters_json.ilike(
                            f"%{normalized_rule_set_version}%"
                        ),
                        or_(
                            self._batch_job_table.c.parent_job_id.is_(None),
                            self._batch_job_table.c.parent_job_id == "",
                        ),
                    )
                )
            )
            .mappings()
            .all()
        )

        active_final_identities: set[tuple[str, str, str]] = set()

        def _record_scene(
            filters: Mapping[str, Any],
            identity: tuple[str, str, str],
            fallback_scope: Any,
        ) -> str:
            for raw_snapshot in filters.get("record_scene_snapshot") or []:
                if not isinstance(raw_snapshot, Mapping):
                    continue
                snapshot_identity = (
                    _safe_text(raw_snapshot.get("institute_id")),
                    _safe_text(raw_snapshot.get("patient_id")),
                    _safe_text(raw_snapshot.get("visit_id")),
                )
                if snapshot_identity != identity:
                    continue
                scene = _safe_text(
                    raw_snapshot.get("resolved_scene")
                    or raw_snapshot.get("record_scene")
                ).lower()
                if scene in {"running", "final"}:
                    return scene
            fallback = _safe_text(fallback_scope).lower()
            return fallback if fallback in {"running", "final"} else "unknown"

        for row in active_final_rows:
            filters = _safe_json_loads(row.get("filters_json"), {})
            if not isinstance(filters, dict):
                continue
            if _safe_text(filters.get("rule_set_key")) != normalized_rule_set_key:
                continue
            if _safe_text(filters.get("rule_set_version")) != normalized_rule_set_version:
                continue
            try:
                active_refs = normalize_case_refs(filters.get("record_refs") or [])
            except (TypeError, ValueError):
                continue
            for ref in active_refs:
                identity = (ref.institute_id, ref.patient_id, ref.visit_id)
                if _record_scene(filters, identity, row.get("scope")) == "final":
                    active_final_identities.add(identity)

        rows_by_identity: Dict[tuple[str, str, str], List[Dict[str, Any]]] = {}
        for raw_row in completed_rows:
            row = dict(raw_row)
            identity = (
                _safe_text(row.get("institute_id")),
                _safe_text(row.get("patient_id")),
                _safe_text(row.get("visit_id")),
            )
            if all(identity):
                rows_by_identity.setdefault(identity, []).append(row)

        eligible: List[CaseRef] = []
        for ref in normalized_refs:
            identity = (ref.institute_id, ref.patient_id, ref.visit_id)
            if identity in active_final_identities:
                continue
            rows = rows_by_identity.get(identity) or []
            if not rows:
                continue
            latest_key = max(_generation_key(row) for row in rows)
            latest_rows = [row for row in rows if _generation_key(row) == latest_key]
            if len({_safe_text(row.get("id")) for row in latest_rows}) != 1:
                continue
            latest_filters = _safe_json_loads(
                latest_rows[0].get("filters_json"),
                {},
            )
            if not isinstance(latest_filters, dict):
                continue
            if _record_scene(
                latest_filters,
                identity,
                latest_rows[0].get("scope"),
            ) != "running":
                continue
            eligible.append(ref)
        return tuple(eligible)
    finally:
        session.close()
