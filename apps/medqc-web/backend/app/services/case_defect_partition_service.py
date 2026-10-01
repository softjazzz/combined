"""单病历详情缺陷分区装配（V3.6 PRD 第 28 项，合同见
``docs/plans/2026-09-30-v36-case-defect-partitions-design.md``）。

本模块只做装配，不判定任何状态：

- 确认缺陷：单病历 DTO 条目经 ``project_customer_items``（客户可见投影）后
  ``is_confirmed_issue is True`` 的 rule_id；投影是唯一 owner。
- 单否：``scoring_service.score_case`` 按场景默认标准计分，``deductions`` 中
  ``is_veto`` 为真的 rule_id；计分服务是唯一 owner。计分复用本次已读取的 DTO，
  保证两个分区锚定同一结果对象。
- 核心制度：仅消费结果冻结版本的管理员显式分类，不从规则名称猜测。

人工缺陷与编码缺陷由前端直接读取各自 owner 的既有只读接口，本模块不代理。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Mapping

from .case_identity import CaseRef
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from . import scoring_service
from .rule_set_version_service import resolve_rule_set_version
from .medical_core_system_catalog import CORE_SYSTEMS

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "case-defect-partitions-v1"
CORE_SYSTEM_REASON = "core_system_classification_missing"
SCORING_SCENES = frozenset({"running", "final", "outpatient"})
CANONICAL_SOURCE = "luxian_0609_canonical_projection"
VETO_SOURCE = "scoring_deductions"
CORE_SOURCE = "core_system_classification"


class _PinnedDtoWorkspace:
    """把计分服务的结果读取钉在本次已读取的 DTO 上；其他规则集照常委托。"""

    def __init__(self, dto: Mapping[str, Any], identity: CaseRef, delegate: Any) -> None:
        self._dto = dto
        self._identity = identity
        self._delegate = delegate

    def build_latest_single_record_result_dto(self, **kwargs: Any) -> Any:
        same_identity = CaseRef.from_mapping(kwargs) == self._identity
        rule_set_key = str(kwargs.get("rule_set_key") or LUXIAN_0609_RULE_SET_KEY)
        if same_identity and rule_set_key == str(self._dto.get("rule_set_key") or ""):
            return self._dto
        return self._delegate.build_latest_single_record_result_dto(**kwargs)


def _rule_ids(values: Iterable[Any]) -> list[str]:
    return sorted({str(value or "").strip().upper() for value in values if str(value or "").strip()})


def _confirmed_partition(
    dto: Mapping[str, Any],
    projector: Callable[[Iterable[Mapping[str, Any]]], list[dict[str, Any]]],
) -> dict[str, Any]:
    try:
        projected = projector(list(dto.get("items") or []))
    except Exception as exc:  # noqa: BLE001 - 投影合同失败只让本分区不可用
        logger.warning("缺陷分区确认缺陷投影失败 error_type=%s", type(exc).__name__)
        return {
            "status": "unavailable",
            "source": CANONICAL_SOURCE,
            "rule_ids": [],
            "reason_code": "projection_failed",
        }
    return {
        "status": "ready",
        "source": CANONICAL_SOURCE,
        "rule_ids": _rule_ids(
            item.get("rule_id")
            for item in projected
            if isinstance(item, Mapping) and item.get("is_confirmed_issue") is True
        ),
        "reason_code": None,
    }


def _veto_partition(
    *,
    identity: CaseRef,
    dto: Mapping[str, Any],
    scene: str | None,
    workspace: Any,
    scorer: Callable[..., Mapping[str, Any]],
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source": VETO_SOURCE,
        "rule_ids": [],
        "standard_name": None,
        "reason_code": None,
    }
    if not scene:
        return {**base, "status": "no_scene"}
    if scene not in SCORING_SCENES:
        return {**base, "status": "unavailable", "reason_code": "invalid_scene"}
    try:
        scored = scorer(
            **identity.as_dict(),
            scene=scene,
            workspace_factory=lambda: _PinnedDtoWorkspace(dto, identity, workspace),
        )
    except Exception as exc:  # noqa: BLE001 - 计分失败只让单否分区不可用
        logger.warning("缺陷分区单否计分失败 error_type=%s", type(exc).__name__)
        return {**base, "status": "unavailable", "reason_code": "score_unavailable"}
    status = str((scored or {}).get("status") or "")
    if status == scoring_service.STATE_NO_STANDARD:
        return {**base, "status": "no_standard"}
    if status != scoring_service.STATE_SCORED:
        return {**base, "status": "unavailable", "reason_code": "score_no_result"}
    scored_job_id = str(scored.get("job_id") or "").strip()
    dto_job_id = str(dto.get("job_id") or "").strip()
    if not scored_job_id or not dto_job_id or scored_job_id != dto_job_id:
        # 计分与分区必须锚定同一结果对象；不一致时不展示单否，避免错配。
        return {**base, "status": "unavailable", "reason_code": "result_changed"}
    deductions = scored.get("deductions") or []
    return {
        **base,
        "status": "ready",
        "standard_name": scored.get("standard_name"),
        "rule_ids": _rule_ids(
            item.get("rule_id")
            for item in deductions
            if isinstance(item, Mapping) and item.get("is_veto") is True
        ),
    }


def build_case_defect_partitions(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    scene: str | None,
    workspace: Any,
    scorer: Callable[..., Mapping[str, Any]] | None = None,
    projector: Callable[[Iterable[Mapping[str, Any]]], list[dict[str, Any]]] | None = None,
    version_resolver: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """按三坐标装配确认缺陷、单否与核心制度三类分区的 rule_id 集合。

    只返回 rule_id 与状态，不返回病历正文或结论文案。结果读取异常原样上抛，
    由路由脱敏。``state`` 与单病历结果接口一致：非 ready 时分区为空。
    """

    identity = CaseRef(
        str(institute_id or "").strip(),
        str(patient_id or "").strip(),
        str(visit_id or "").strip(),
    )
    if not all(identity):
        raise ValueError("缺陷分区读取缺少三坐标身份")
    dto = workspace.build_latest_single_record_result_dto(**identity.as_dict())
    state = str((dto or {}).get("state") or "") if isinstance(dto, Mapping) else ""
    core = {
        "status": "not_integrated",
        "source": CORE_SOURCE,
        "reason_code": CORE_SYSTEM_REASON,
    }
    identity_payload = identity.as_dict()
    job_id = str((dto or {}).get("job_id") or "").strip() if isinstance(dto, Mapping) else ""
    if state != "ready" or not job_id:
        reason_code = "result_identity_missing" if state == "ready" else "result_not_ready"
        return {
            "schema_version": SCHEMA_VERSION,
            **identity_payload,
            "state": "technical_error" if state == "ready" else state or "technical_error",
            "job_id": "",
            "confirmed": {
                "status": "unavailable",
                "source": CANONICAL_SOURCE,
                "rule_ids": [],
                "reason_code": reason_code,
            },
            "veto": {
                "status": "unavailable",
                "source": VETO_SOURCE,
                "rule_ids": [],
                "standard_name": None,
                "reason_code": reason_code,
            },
            "core": core,
        }
    confirmed = _confirmed_partition(dto, projector or scoring_service.project_customer_items)
    if confirmed["status"] == "ready" and dto.get("rule_set_version"):
        try:
            resolution = (version_resolver or resolve_rule_set_version)(dto.get("rule_set_key"), dto.get("rule_set_version"))
            entries = {item["rule_id"]: item for item in resolution["entries"]}
            unknown = [rule_id for rule_id in confirmed["rule_ids"] if entries.get(rule_id, {}).get("core_system_ids") is None]
            matched = [rule_id for rule_id in confirmed["rule_ids"] if entries.get(rule_id, {}).get("core_system_ids")]
            # 无确认缺陷时也需要整份版本分类已配置，不能把历史未配置伪装成零。
            configured = any(item.get("core_system_ids") is not None for item in entries.values())
            core = {
                "source": CORE_SOURCE, "status": "partial" if unknown and matched else "not_integrated" if unknown or not configured else "ready",
                "reason_code": CORE_SYSTEM_REASON if unknown or not configured else None,
                "rule_ids": matched, "unknown_rule_ids": unknown,
                "systems": [{**system, "rule_ids": [rule_id for rule_id in matched if system["id"] in entries[rule_id]["core_system_ids"]]} for system in CORE_SYSTEMS],
            }
        except Exception as exc:  # noqa: BLE001 - 分类故障不影响其他分区
            logger.warning("核心制度分类读取失败 error_type=%s", type(exc).__name__)
            core = {"source": CORE_SOURCE, "status": "unavailable", "reason_code": "classification_unavailable", "rule_ids": []}
    return {
        "schema_version": SCHEMA_VERSION,
        **identity_payload,
        "state": "ready",
        "job_id": job_id,
        "confirmed": confirmed,
        "veto": _veto_partition(
            identity=identity,
            dto=dto,
            scene=scene,
            workspace=workspace,
            scorer=scorer or scoring_service.score_case,
        ),
        "core": core,
    }


__all__ = [
    "build_case_defect_partitions",
    "CANONICAL_SOURCE",
    "CORE_SOURCE",
    "CORE_SYSTEM_REASON",
    "SCHEMA_VERSION",
    "VETO_SOURCE",
]
