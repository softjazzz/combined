from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Callable, Dict, List, Literal, Mapping, Optional, Sequence

from fastapi import HTTPException
from pydantic import BaseModel

from ..core.settings import get_settings
from ..services.case_identity import CaseRef, case_refs_from_records
from ..services.custom_qc_workspace_service import CustomQCWorkspaceService
from ..services.fast_screen_qc import normalize_execution_strategy
from ..services.luxian_0609 import (
    LUXIAN_0609_RULE_SET_KEY,
    build_luxian_0609_package_plan_from_settings,
    load_luxian_0609_dependency_inventory,
)
from ..services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot
from ..services.luxian_0609.native_package import assert_luxian_0609_formal_package_plan_native_only
from ..services.luxian_0609.rule_decision_settings import (
    assert_luxian_0609_customer_native_delivery_ready,
    resolve_mainline_rule_decision_settings,
)
from ..services.qc_rule_sets import get_sichuan_rule_set
from ..services.rule_set_version_service import (
    RuleSetVersionNotFound,
    RuleSetVersionUnavailable,
    current_version,
    resolve_rule_set_version,
)
from ..services.sichuan_qc_service import SichuanQCService
from ..services.sichuan_workspace_batch_worker import (
    _assert_luxian_0609_formal_customer_rule_ids,
    _enforce_sc_source_guard,
    _resolve_workspace_bundle_scene,
    _normalize_quality_profile,
    _normalize_bucket_strategy,
    _normalize_refine_threshold,
    _normalize_batch_output_mode,
    _normalize_max_refine_candidates,
    _normalize_run_mode,
)


@dataclass(frozen=True)
class PreparedWorkspaceBatchJob:
    create_kwargs: Dict[str, Any]
    response_fields: Dict[str, Any]
    idempotency_key: str


_SUPPORTED_WORKSPACE_SCOPES = frozenset({"all", "running", "final"})
_UNSUPPORTED_WORKSPACE_SCOPE_DETAIL = (
    "质控范围仅支持 all/running/final；门诊/急诊范围暂不支持质控任务"
)


class SichuanWorkspaceBatchJobCreateRequest(BaseModel):
    diagnostic_capture: bool = False
    rule_ids: Optional[List[str]] = None
    rule_set_key: Optional[str] = None
    execution_strategy: Optional[str] = None
    quality_profile: Optional[str] = None
    bucket_strategy: Optional[str] = None
    batch_output_mode: Optional[str] = None
    enable_selective_refine: Optional[bool] = None
    refine_confidence_threshold: Optional[float] = None
    max_refine_candidates: Optional[int] = None
    scope: str = "final"
    sync_scope: Literal["all", "today_inpatient"] = "all"
    department: Optional[str] = None
    doctor: Optional[str] = None
    date_field: str = "discharge"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keyword: Optional[str] = None
    record_ids: Optional[List[str]] = None
    record_refs: Optional[List[Dict[str, str]]] = None
    run_mode: Optional[str] = None


def _build_workspace_record_scene_snapshot(
    records: Sequence[Dict[str, Any]],
    *,
    query_scope: str,
) -> List[Dict[str, str]]:
    snapshot: List[Dict[str, str]] = []
    for record in records:
        record_id = str(record.get("record_id") or record.get("visit_id") or "").strip()
        if not record_id:
            continue
        record_ref = CaseRef.from_mapping(record)
        normalized_record_scene = str(record.get("scope") or "").strip().lower()
        record_scene = (
            normalized_record_scene
            if normalized_record_scene in {"running", "final"}
            else "unknown"
        )
        snapshot.append(
            {
                "record_id": record_id,
                **(
                    {
                        **record_ref.as_dict(),
                        "record_key": record_ref.as_key(),
                    }
                    if all(record_ref)
                    else {}
                ),
                "record_scene": record_scene,
                "resolved_scene": _resolve_workspace_bundle_scene(
                    query_scope=query_scope,
                    record_scope=normalized_record_scene,
                ),
                "discharge_snapshot": str(
                    record.get("discharge_datetime") or record.get("discharge_date") or ""
                ).strip(),
            }
        )
    return sorted(snapshot, key=lambda item: item.get("record_key") or item["record_id"])


def _normalize_scope(scope: Optional[str]) -> str:
    """把质控范围收敛为受控枚举。

    内部未传范围时沿用历史默认 all；显式空值、门诊/急诊或未知范围一律失败。
    静默回退为 all/final 会让请求先按住院范围 collect_records 取数，
    外层归档守卫只是随后才 422，取数副作用已经发生。
    """

    if scope is None:
        return "all"
    value = str(scope).strip().lower()
    if value not in _SUPPORTED_WORKSPACE_SCOPES:
        raise HTTPException(status_code=422, detail=_UNSUPPORTED_WORKSPACE_SCOPE_DETAIL)
    return value


def _normalize_date_field(date_field: Optional[str]) -> str:
    value = str(date_field or "").strip().lower()
    if value not in {"visit", "admission", "discharge"}:
        return "admission"
    return value


def _resolve_prepare_rule_set_version(
    rule_set_key: str,
    *,
    task_run_context: Mapping[str, str] | None,
    frozen_rule_set_version: str | None,
) -> Dict[str, Any]:
    """按规则集版本解析结果确定本次执行范围（合同第 5 节）。

    任务运行只按任务冻结版本解析，缺失即失败关闭；其他入口按当前版本解析。
    解析 owner 是 rule_set_version_service，本函数只做错误语义映射。
    """
    try:
        if task_run_context is not None:
            version = str(frozen_rule_set_version or "").strip()
            if not version:
                raise HTTPException(status_code=422, detail="任务运行上下文缺少冻结规则集版本")
        else:
            version = str(frozen_rule_set_version or "").strip() or current_version(rule_set_key)
        return resolve_rule_set_version(rule_set_key, version)
    except RuleSetVersionNotFound as exc:
        raise HTTPException(status_code=409, detail="规则集版本不存在或已不可用") from exc
    except RuleSetVersionUnavailable as exc:
        raise HTTPException(status_code=503, detail="规则集版本暂不可读取，请稍后重试") from exc


def _partition_by_rule_set_version(
    selected_rule_ids: Sequence[str],
    resolution: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """所选规则按解析版本拆为执行（active）与暂停（paused），顺序沿用解析结果。

    内置版本的 active/paused 即现行 phase 划分（总表目录顺序、逐条判定），
    故与 partition_luxian_0609_rule_scope(selected) 结果逐项相同。
    """
    selected = {str(rule_id or "").strip().upper() for rule_id in selected_rule_ids if str(rule_id or "").strip()}
    active = tuple(rule_id for rule_id in resolution["active_rule_ids"] if rule_id in selected)
    paused = tuple(rule_id for rule_id in resolution["paused_rule_ids"] if rule_id in selected)
    if len(active) + len(paused) != len(selected):
        raise HTTPException(status_code=422, detail="所选规则不在当前规则集版本范围")
    return active, paused


def prepare_workspace_batch_job(
    payload: SichuanWorkspaceBatchJobCreateRequest,
    *,
    current_user: Mapping[str, Any] | None = None,
    qc_service: SichuanQCService,
    workspace: CustomQCWorkspaceService | None = None,
    workspace_provider: Callable[[], CustomQCWorkspaceService] | None = None,
    settings_provider: Callable[[], Any] = get_settings,
    task_run_context: Mapping[str, str] | None = None,
    frozen_rule_set_version: str | None = None,
) -> PreparedWorkspaceBatchJob:
    # 显式声明的范围必须先受控校验：规则集默认范围允许覆盖 payload 范围，
    # 但不得把显式 outpatient/未知范围掩盖成可执行的住院取数范围。
    _normalize_scope(payload.scope)

    requested_rule_set = get_sichuan_rule_set(payload.rule_set_key)
    if payload.diagnostic_capture:
        if not set((current_user or {}).get("roles", [])).intersection({"admin", "super_admin"}):
            raise HTTPException(403, "仅管理员可采集完整排障包")
        if payload.rule_set_key != LUXIAN_0609_RULE_SET_KEY or len(payload.record_refs or []) != 1:
            raise HTTPException(422, "排障采集仅支持单病历泸县0609质控")
    if payload.rule_set_key and not requested_rule_set:
        raise HTTPException(status_code=422, detail=f"未知规则集: {payload.rule_set_key}")
    rule_set_resolution = (
        _resolve_prepare_rule_set_version(
            requested_rule_set.key,
            task_run_context=task_run_context,
            frozen_rule_set_version=frozen_rule_set_version,
        )
        if requested_rule_set
        else None
    )
    excluded_customer_rule_ids = frozenset(
        (rule_set_resolution or {}).get("excluded_rule_ids") or ()
    )

    requested_payload_rule_ids = [
        str(item or "").strip().upper()
        for item in (payload.rule_ids or [])
        if str(item or "").strip()
    ]
    requested_rule_set_rule_ids = list(
        requested_payload_rule_ids
        or (requested_rule_set.rule_ids if requested_rule_set else ())
    )
    if requested_rule_set and requested_rule_set.key == LUXIAN_0609_RULE_SET_KEY:
        requested_rule_set_rule_ids = [
            rule_id
            for rule_id in requested_rule_set_rule_ids
            if str(rule_id).strip().upper() not in excluded_customer_rule_ids
        ]
        if requested_payload_rule_ids and not requested_rule_set_rule_ids:
            raise HTTPException(status_code=422, detail="所选规则不在当前客户运行范围")
    try:
        direct_native_rule_ids = _assert_luxian_0609_formal_customer_rule_ids(
            rule_set_key=(requested_rule_set.key if requested_rule_set else ""),
            rule_ids=tuple(requested_rule_set_rule_ids),
            context="workspace_batch_create",
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    is_direct_native_selection = bool(
        requested_rule_set
        and requested_rule_set.key == LUXIAN_0609_RULE_SET_KEY
        and requested_rule_set_rule_ids
        and len(direct_native_rule_ids) == len(set(requested_rule_set_rule_ids))
    )
    active_customer_rule_ids, pending_customer_rule_ids = (
        _partition_by_rule_set_version(direct_native_rule_ids, rule_set_resolution)
        if is_direct_native_selection and rule_set_resolution is not None
        else ((), ())
    )

    if requested_rule_set:
        rule_ids = (
            list(active_customer_rule_ids)
            if is_direct_native_selection
            else list(requested_rule_set.rule_ids)
        )
        effective_scope = (
            payload.scope
            if is_direct_native_selection
            else requested_rule_set.scope or payload.scope
        )
        rule_set_key = requested_rule_set.key
        rule_set_name = requested_rule_set.name
        rule_set_version = str((rule_set_resolution or {}).get("version") or "")
        execution_strategy = normalize_execution_strategy(requested_rule_set.execution_strategy)
        quality_profile = requested_rule_set.quality_profile
        bucket_strategy = requested_rule_set.bucket_strategy
        batch_output_mode = requested_rule_set.batch_output_mode
        enable_selective_refine = requested_rule_set.enable_selective_refine
        refine_confidence_threshold = requested_rule_set.refine_confidence_threshold
        max_refine_candidates = requested_rule_set.max_refine_candidates
    else:
        rule_ids = [str(item).strip() for item in (payload.rule_ids or []) if str(item).strip()]
        effective_scope = payload.scope
        rule_set_key = ""
        rule_set_name = ""
        rule_set_version = ""
        execution_strategy = normalize_execution_strategy(payload.execution_strategy)
        quality_profile = _normalize_quality_profile(payload.quality_profile)
        bucket_strategy = _normalize_bucket_strategy(payload.bucket_strategy)
        batch_output_mode = _normalize_batch_output_mode(
            payload.batch_output_mode,
            quality_profile=quality_profile,
        )
        enable_selective_refine = bool(payload.enable_selective_refine is True)
        refine_confidence_threshold = _normalize_refine_threshold(payload.refine_confidence_threshold)
        max_refine_candidates = _normalize_max_refine_candidates(payload.max_refine_candidates)

    if not rule_ids:
        raise HTTPException(status_code=422, detail="rule_ids 不能为空")
    if is_direct_native_selection and payload.record_ids:
        raise HTTPException(
            status_code=422,
            detail="LX0609质控任务不接受 record_ids，请改用 record_refs",
        )
    if is_direct_native_selection:
        effective_settings = resolve_mainline_rule_decision_settings(settings_provider())
        try:
            assert_luxian_0609_customer_native_delivery_ready(
                effective_settings,
                context="workspace_batch_create",
            )
            formal_package_plan = build_luxian_0609_package_plan_from_settings(
                inventory=load_luxian_0609_dependency_inventory(),
                selected_rule_ids=direct_native_rule_ids,
                settings=effective_settings,
            )
            assert_luxian_0609_formal_package_plan_native_only(
                formal_package_plan,
                context="workspace_batch_create",
            )
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    compatibility_rule_ids = (
        formal_package_plan.compatibility_execution_rule_ids
        if is_direct_native_selection
        else tuple(rule_ids)
    )
    if compatibility_rule_ids:
        _enforce_sc_source_guard(
            qc_service,
            context="workspace_batch_create",
            rule_ids=list(compatibility_rule_ids),
            block_batch=True,
        )

    normalized_scope = _normalize_scope(effective_scope)
    run_mode = _normalize_run_mode(payload.run_mode) if payload.run_mode else "parallel"
    try:
        requested_record_refs = (
            case_refs_from_records(payload.record_refs or []) if payload.record_refs else ()
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.record_refs and len(requested_record_refs) != len(payload.record_refs):
        raise HTTPException(status_code=422, detail="record_refs 不可重复")
    collect_kwargs: Dict[str, Any] = dict(
        scope=normalized_scope,
        department=payload.department,
        doctor=payload.doctor,
        date_field=_normalize_date_field(payload.date_field),
        start_date=payload.start_date,
        end_date=payload.end_date,
        keyword=payload.keyword,
        record_ids=None if requested_record_refs else payload.record_ids or None,
        record_refs=requested_record_refs or None,
    )
    if payload.sync_scope == "today_inpatient":
        collect_kwargs["sync_scope"] = payload.sync_scope
    if workspace is None:
        if workspace_provider is None:
            raise RuntimeError("workspace service 未配置")
        workspace = workspace_provider()
    records = workspace.collect_records(**collect_kwargs)
    if not records:
        raise HTTPException(status_code=422, detail="当前筛选条件下没有可执行病历")

    try:
        effective_record_refs = case_refs_from_records(records)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="病历缺少完整三坐标，无法创建质控任务") from exc
    if requested_record_refs and set(effective_record_refs) != set(requested_record_refs):
        raise HTTPException(status_code=422, detail="所选病历与服务端匹配结果不一致，请刷新后重试")
    if payload.record_ids and not requested_record_refs:
        refs_by_visit: Dict[str, set[CaseRef]] = {}
        for ref in effective_record_refs:
            refs_by_visit.setdefault(ref.visit_id, set()).add(ref)
        ambiguous_visit_ids = sorted(
            visit_id for visit_id, refs in refs_by_visit.items() if len(refs) > 1
        )
        if ambiguous_visit_ids:
            raise HTTPException(
                status_code=422,
                detail="所选住院号对应多份病历，请使用三坐标重新选择",
            )
    effective_record_ids = sorted({ref.visit_id for ref in effective_record_refs})
    effective_record_ref_payload = [ref.as_dict() for ref in effective_record_refs]
    record_scene_snapshot = _build_workspace_record_scene_snapshot(
        records,
        query_scope=normalized_scope,
    )
    task_frozen_date = (
        datetime.now().astimezone().date().isoformat()
        if is_direct_native_selection
        else ""
    )
    record_evaluation_snapshot = (
        build_record_evaluation_horizon_snapshot(
            records,
            task_frozen_date=task_frozen_date,
        )
        if task_frozen_date
        else []
    )
    idempotency_payload = {
        **({"diagnostic_capture": True} if payload.diagnostic_capture else {}),
        "scope": normalized_scope,
        "query_scope": normalized_scope,
        **(
            {"sync_scope": payload.sync_scope}
            if payload.sync_scope == "today_inpatient"
            else {}
        ),
        "department": payload.department or "",
        "doctor": payload.doctor or "",
        "date_field": _normalize_date_field(payload.date_field),
        "start_date": payload.start_date or "",
        "end_date": payload.end_date or "",
        "keyword": payload.keyword or "",
        "record_refs": effective_record_ref_payload,
        "record_scene_snapshot": record_scene_snapshot,
        "rule_set_key": rule_set_key,
        **(
            {"rule_set_content_digest": rule_set_resolution["content_digest"]}
            if rule_set_resolution is not None
            else {}
        ),
        "rule_ids": sorted({str(rule_id).strip().upper() for rule_id in rule_ids if str(rule_id).strip()}),
        **(
            {
                "customer_rule_ids": sorted(
                    {str(rule_id).strip().upper() for rule_id in direct_native_rule_ids if str(rule_id).strip()}
                )
            }
            if is_direct_native_selection
            else {}
        ),
        "execution_strategy": execution_strategy,
        "quality_profile": quality_profile,
        "bucket_strategy": bucket_strategy,
        "batch_output_mode": batch_output_mode,
        "run_mode": run_mode,
        **({"task_frozen_date": task_frozen_date} if task_frozen_date else {}),
        **(
            {"record_evaluation_snapshot": record_evaluation_snapshot}
            if record_evaluation_snapshot
            else {}
        ),
    }
    task_context_filters: Dict[str, Any] = {}
    if task_run_context is not None:
        task_id = str(task_run_context.get("task_id") or "").strip()
        run_number = str(task_run_context.get("run_number") or "").strip()
        if not task_id or not run_number:
            raise HTTPException(status_code=422, detail="任务运行上下文不完整")
        task_context_filters = {"task_id": task_id, "task_run_number": run_number}
        idempotency_payload["task_run_context"] = task_context_filters
    idempotency_digest = hashlib.sha256(
        json.dumps(idempotency_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    idempotency_key = f"sichuan-workspace-run:{idempotency_digest}"

    pseudo_draft = {
        "id": "sichuan-rule-library",
        "rule_code": "SC-BATCH",
        "name": f"{rule_set_name or '四川规则库'}批量任务({len(rule_ids)}条规则)",
        "scene": "running" if normalized_scope == "running" else "final",
    }
    create_kwargs = dict(
        draft=pseudo_draft,
        scope=normalized_scope,
        filters={
            "department": payload.department,
            "doctor": payload.doctor,
            **(
                {"sync_scope": payload.sync_scope}
                if payload.sync_scope == "today_inpatient"
                else {}
            ),
            "date_field": _normalize_date_field(payload.date_field),
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "keyword": payload.keyword,
            "record_refs": effective_record_ref_payload,
            "query_scope": normalized_scope,
            "rule_ids": rule_ids,
            "paused_customer_rule_ids": list(pending_customer_rule_ids),
            "rule_set_key": rule_set_key,
            "rule_set_name": rule_set_name,
            "rule_set_version": rule_set_version,
            **(
                {
                    "rule_set_content_digest": rule_set_resolution["content_digest"],
                    "excluded_customer_rule_ids": list(rule_set_resolution["excluded_rule_ids"]),
                }
                if rule_set_resolution is not None
                else {}
            ),
            "execution_strategy": execution_strategy,
            "quality_profile": quality_profile,
            "bucket_strategy": bucket_strategy,
            "batch_output_mode": batch_output_mode,
            "enable_selective_refine": enable_selective_refine,
            "refine_confidence_threshold": refine_confidence_threshold,
            "max_refine_candidates": max_refine_candidates,
            "source": "sichuan_rule_workspace",
            **task_context_filters,
            **({"diagnostic_capture": True} if payload.diagnostic_capture else {}),
            "run_mode": run_mode,
            **({"task_frozen_date": task_frozen_date} if task_frozen_date else {}),
            "idempotency_key": idempotency_key,
            "idempotency_payload": idempotency_payload,
            "record_scene_snapshot": record_scene_snapshot,
            **(
                {"record_evaluation_snapshot": record_evaluation_snapshot}
                if record_evaluation_snapshot
                else {}
            ),
            **(
                {
                    "selected_rule_ids": list(direct_native_rule_ids),
                    "scoped_customer_rule_ids": list(direct_native_rule_ids),
                    "active_customer_rule_ids": list(active_customer_rule_ids),
                    "pending_customer_rule_ids": list(pending_customer_rule_ids),
                    "record_rule_map": {
                        ref.as_key(): list(direct_native_rule_ids)
                        for ref in effective_record_refs
                    },
                    "validation_mode": "programmatic",
                    "customer_rule_count": len(direct_native_rule_ids),
                    "execution_rule_count": len(active_customer_rule_ids),
                    "pending_rule_count": len(pending_customer_rule_ids),
                }
                if is_direct_native_selection
                else {}
            ),
        },
        record_ids=effective_record_ids,
        total_records=len(records),
        record_refs=effective_record_refs,
        draft_ids=rule_ids,
        execution_mode="multi",
        run_mode=run_mode,
        rule_count=len(rule_ids),
    )
    response_fields = {
        "execution_mode": "batch",
        "rule_count": len(rule_ids),
        "draft_ids": rule_ids,
        "rule_set_key": rule_set_key,
        "rule_set_name": rule_set_name,
        "rule_set_version": rule_set_version,
        "execution_strategy": execution_strategy,
        "quality_profile": quality_profile,
        "bucket_strategy": bucket_strategy,
        "batch_output_mode": batch_output_mode,
        "max_refine_candidates": max_refine_candidates,
        "run_mode": run_mode,
    }
    return PreparedWorkspaceBatchJob(
        create_kwargs=create_kwargs,
        response_fields=response_fields,
        idempotency_key=idempotency_key,
    )
