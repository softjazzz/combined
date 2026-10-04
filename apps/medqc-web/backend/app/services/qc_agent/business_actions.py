"""业务动作纯预览与确认校验；不创建任务、不写库、不发送通知。

调用方负责从权威服务读取授权/材料版本，持久保存预览并实现原子幂等。
确认摘要只绑定这一次已展示的参数，不是签名、授权或执行成功凭据。
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.luxian_0609.phase_scope import (
    get_luxian_0609_acceptance_only_rule_ids,
    partition_luxian_0609_rule_scope,
)
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609_rule_master import LUXIAN_0609_RULE_MASTER_VERSION
from app.services.sample_validation_rule_sets import get_luxian_0609_customer_delivery_rule_ids
from .business_schemas import BusinessContext


class ActionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ActionRecordRef(ActionModel):
    institute_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    visit_id: str = Field(min_length=1, max_length=128)


class MaterialVersion(ActionModel):
    record_ref: ActionRecordRef
    version: str = Field(min_length=1, max_length=256)
    # 必须来自同步/材料所有者，不允许把医生口述“改好了”当作同步证明。
    synchronization_verified: bool = False
    # 同步所有者明确报告失败时阻断；未知只警示，按当前已同步材料检查。
    synchronization_failed: bool = False


class ActionRequest(ActionModel):
    operation: Literal["single_recheck", "specialist_batch"]
    record_refs: tuple[ActionRecordRef, ...] = Field(min_length=1, max_length=100)
    rule_ids: tuple[str, ...] = Field(min_length=1, max_length=75)


class FormalTaskRequest(ActionModel):
    rule_set_key: str = LUXIAN_0609_RULE_SET_KEY
    rule_ids: tuple[str, ...]
    record_refs: tuple[ActionRecordRef, ...]
    scope: Literal["running", "final"]
    # 明确病例集合已冻结，不把统计完成日期误用为任务入院/出院筛选日期。


class ActionPreview(ActionModel):
    owner_id: str
    session_id: str
    expires_at: datetime
    context: BusinessContext
    request: ActionRequest
    catalog_version: str
    material_versions: tuple[MaterialVersion, ...]
    allowed: bool
    blocked_reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    formal_request: FormalTaskRequest | None
    confirmation_hash: str


class ActionConfirmation(ActionModel):
    confirmed: Literal[True]
    confirmation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def build_action_preview(
    request: ActionRequest, *, context: BusinessContext, owner_id: str, session_id: str,
    authorized_record_refs: tuple[ActionRecordRef, ...],
    material_versions: tuple[MaterialVersion, ...], expires_at: datetime, now: datetime,
) -> ActionPreview:
    """只读构建。authorized_record_refs 必须已按当前UID及context逐病例过滤。"""
    if not owner_id.strip() or not session_id.strip():
        raise ValueError("预览必须绑定账号和会话")
    if now.tzinfo is None or expires_at.tzinfo is None or expires_at <= now:
        raise ValueError("预览有效期必须是未来的带时区时间")
    reasons: list[str] = []
    refs = request.record_refs
    if len(set(refs)) != len(refs):
        reasons.append("病例不可重复")
    if any(ref not in authorized_record_refs for ref in refs):
        reasons.append("包含当前范围未授权病例")
    if any(ref.institute_id != context.institute_id for ref in refs):
        reasons.append("病例不属于当前机构")
    if context.care_phase not in {"inpatient", "discharged"}:
        reasons.append("需明确本次在院或出院质控范围")
    if context.view == "doctor":
        if request.operation != "single_recheck" or len(refs) != 1:
            reasons.append("医生仅可复检当前单病例")
        if any((ref.institute_id, ref.patient_id, ref.visit_id) !=
               (context.institute_id, context.patient_id, context.visit_id) for ref in refs):
            reasons.append("病例不匹配当前医生上下文")
    elif not context.department:
        reasons.append("管理操作需明确授权科室")
    if request.operation == "single_recheck" and len(refs) != 1:
        reasons.append("单病例复检仅允许一份病例")
    selected = request.rule_ids
    if len(set(selected)) != len(selected):
        reasons.append("规则不可重复")
    allowed_rules = set(get_luxian_0609_customer_delivery_rule_ids())
    acceptance_only = set(get_luxian_0609_acceptance_only_rule_ids())
    if any(rule not in allowed_rules or rule in acceptance_only for rule in selected):
        reasons.append("包含未知、排除或仅待验收规则")
    else:
        active, pending = partition_luxian_0609_rule_scope(selected)
        if pending or set(active) != set(selected):
            reasons.append("包含当前未正式执行规则，请重新选择并预览")
    versions = [item for item in material_versions if item.record_ref in refs]
    warnings: list[str] = []
    for ref in refs:
        matched = [item for item in versions if item.record_ref == ref]
        if len(matched) != 1:
            reasons.append("材料版本缺失或冲突，请核对后重新预览")
            break
        if matched[0].synchronization_failed:
            reasons.append("病例材料同步失败，请先处理同步问题再复检")
            break
        if not matched[0].synchronization_verified:
            warnings.append("未能证实最新修改的文书已同步；将检查当前已同步材料，结果不能证明新修改已被核对")
    warnings = list(dict.fromkeys(warnings))
    formal = None if reasons else FormalTaskRequest(
        rule_ids=selected, record_refs=refs,
        scope="running" if context.care_phase == "inpatient" else "final",
    )
    payload = dict(owner_id=owner_id, session_id=session_id, expires_at=expires_at,
                   context=context, request=request, catalog_version=LUXIAN_0609_RULE_MASTER_VERSION,
                   material_versions=tuple(versions), allowed=not reasons,
                   blocked_reasons=tuple(dict.fromkeys(reasons)), warnings=tuple(warnings), formal_request=formal,
                   confirmation_hash="")
    preview = ActionPreview(**payload)
    return preview.model_copy(update={"confirmation_hash": _digest(
        preview.model_dump(mode="json", exclude={"confirmation_hash"}))})


def validate_confirmation(
    preview: ActionPreview, confirmation: ActionConfirmation, *, owner_id: str, session_id: str,
    context: BusinessContext, authorized_record_refs: tuple[ActionRecordRef, ...],
    material_versions: tuple[MaterialVersion, ...], now: datetime,
) -> FormalTaskRequest:
    """只接受服务端保存的preview；返回待调用正式链的参数，不产生执行副作用。"""
    if (owner_id, session_id) != (preview.owner_id, preview.session_id):
        raise ValueError("预览不属于当前账号或会话")
    if now.tzinfo is None or preview.expires_at <= now:
        raise ValueError("预览已过期，请重新预览")
    expected = _digest(preview.model_dump(mode="json", exclude={"confirmation_hash"}))
    if not hmac.compare_digest(expected, preview.confirmation_hash) or not hmac.compare_digest(
        expected, confirmation.confirmation_hash
    ):
        raise ValueError("确认参数与服务端预览不一致")
    if not preview.allowed or preview.formal_request is None:
        raise ValueError("预览存在未满足的安全前置条件")
    current = build_action_preview(
        preview.request, context=context, owner_id=owner_id, session_id=session_id,
        authorized_record_refs=authorized_record_refs, material_versions=material_versions,
        expires_at=preview.expires_at, now=now,
    )
    if not current.allowed or not hmac.compare_digest(current.confirmation_hash, expected):
        raise ValueError("授权、范围、目录或材料版本已变化，请重新预览")
    return current.formal_request
