"""计分服务（V3.6 P2-S 评分标准与计分服务合同第 3、5 节）。

- 计分唯一 owner：纯函数 ``score_result(items, standard)``。输入为客户可见条目
  （``project_customer_safe_result_item`` 的输出），只对 ``is_confirmed_issue is True`` 的条目扣分；
  待核实、未执行、不适用都不扣。不改执行器、不重判状态。
- ``score_cases(results, scene)``：一次读取场景默认标准，逐病例纯函数计分，供列表与报表。
- ``score_case(...)``：单病历按最新 ready 结果和场景默认标准计分（GET /api/v1/scoring/case）。
- ``score_workstation_page(...)``：V5 列表本页 ready 病例批量计分，失败降级 unavailable。
- 按需计算、不落库：响应带 standard_id 与标准 updated_at 标明计分依据。
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from hmac import compare_digest
from typing import Any, Callable, Iterable, Mapping, Sequence

from .case_identity import CaseRef
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .scoring_standard_service import ScoringStandardUnavailable, get_default_standard

logger = logging.getLogger(__name__)

STATE_SCORED = "scored"
STATE_NO_STANDARD = "no_standard"
STATE_UNAVAILABLE = "unavailable"
STATE_NO_RESULT = "no_result"

_CENT = Decimal("0.01")


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(_CENT)


def _float(value: Decimal) -> float:
    return float(value.quantize(_CENT))


def grade_for(score: Decimal, bands: Sequence[Mapping[str, Any]]) -> str | None:
    """按档位定级：区间左闭右开 [min, max)，最高档（第一档）右闭 [min, max]。"""
    for index, band in enumerate(bands):
        low = _decimal(band["min_score"])
        high = _decimal(band["max_score"])
        if low <= score < high or (index == 0 and score == high):
            return str(band["name"])
    return None


def score_result(items: Iterable[Mapping[str, Any]], standard: Mapping[str, Any]) -> dict[str, Any]:
    """纯函数计分。同一条目集合配同一标准，结果恒定（与条目顺序无关）。

    返回 {score, grade, veto_hit, deductions, group_deductions, unscored_rule_ids, base_score,
    standard_id, standard_updated_at}。扣分与未配置规则按 rule_id 去重。
    """
    configured = {str(item["rule_id"]).strip().upper(): item for item in standard.get("items") or []}
    groups = {str(group["group_name"]): group for group in standard.get("groups") or []}
    confirmed = sorted({
        str(item.get("rule_id") or "").strip().upper()
        for item in items
        if isinstance(item, Mapping) and item.get("is_confirmed_issue") is True
        and str(item.get("rule_id") or "").strip()
    })

    deductions: list[dict[str, Any]] = []
    unscored: list[str] = []
    raw_by_group: dict[str, Decimal] = {}
    veto_hit = False
    for rule_id in confirmed:
        config = configured.get(rule_id)
        if config is None:
            unscored.append(rule_id)
            continue
        if not config.get("enabled", True):
            continue
        amount = _decimal(config["deduction"])
        group_name = str(config["group_name"])
        is_veto = bool(config.get("is_veto"))
        veto_hit = veto_hit or is_veto
        raw_by_group[group_name] = raw_by_group.get(group_name, Decimal("0")) + amount
        deductions.append({
            "rule_id": rule_id, "group_name": group_name, "deduction": _float(amount), "is_veto": is_veto,
        })

    def group_order(name: str) -> tuple[int, str]:
        group = groups.get(name) or {}
        return (int(group.get("sort_order") or 0), name)

    group_deductions = []
    total = Decimal("0")
    for name in sorted(raw_by_group, key=group_order):
        raw = raw_by_group[name]
        cap = (groups.get(name) or {}).get("max_deduction")
        applied = raw if cap is None else min(raw, _decimal(cap))
        total += applied
        group_deductions.append({
            "group_name": name, "raw_deduction": _float(raw), "applied_deduction": _float(applied),
            "max_deduction": None if cap is None else _float(_decimal(cap)),
        })
    deductions.sort(key=lambda item: (group_order(item["group_name"]), item["rule_id"]))

    base = _decimal(standard["base_score"])
    score = max(Decimal("0"), base - total)
    grade = standard["veto_grade"] if veto_hit else grade_for(score, standard.get("grade_bands") or [])
    return {
        "score": _float(score),
        "grade": grade,
        "veto_hit": veto_hit,
        "base_score": _float(base),
        "deductions": deductions,
        "group_deductions": group_deductions,
        "unscored_rule_ids": unscored,
        "standard_id": standard.get("id"),
        "standard_updated_at": standard.get("updated_at"),
    }


def _state(status: str, *, standard: Mapping[str, Any] | None = None, reason_code: str | None = None,
           scored: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """列表 score_state 固定形状：{status, score, grade, veto_hit, standard_id, reason_code}。"""
    return {
        "status": status,
        "score": None if scored is None else scored["score"],
        "grade": None if scored is None else scored["grade"],
        "veto_hit": None if scored is None else scored["veto_hit"],
        "standard_id": None if standard is None else standard.get("id"),
        "reason_code": reason_code,
    }


def score_cases(
    results: Mapping[Any, Mapping[str, Any]],
    scene: str,
    *,
    standard_loader: Callable[[str], Mapping[str, Any] | None] = get_default_standard,
) -> dict[Any, dict[str, Any]]:
    """批量计分：一次读取场景默认标准，逐病例纯函数计分。

    results 为 {key: {"items": 客户可见条目, "rule_set_key": 可选}}；返回 {key: score_state}。
    标准读取失败时全部 unavailable；单病例异常只影响该病例。
    """
    if not results:
        return {}
    try:
        standard = standard_loader(scene)
    except Exception as exc:  # noqa: BLE001 - 标准读取失败降级，不阻断调用方
        logger.warning("评分标准读取失败，计分降级 error_type=%s", type(exc).__name__)
        return {key: _state(STATE_UNAVAILABLE, reason_code="standard_unavailable") for key in results}
    if standard is None:
        return {key: _state(STATE_NO_STANDARD) for key in results}
    states: dict[Any, dict[str, Any]] = {}
    for key, result in results.items():
        rule_set_key = result.get("rule_set_key") if isinstance(result, Mapping) else None
        if rule_set_key and rule_set_key != standard.get("rule_set_key"):
            states[key] = _state(STATE_UNAVAILABLE, standard=standard, reason_code="rule_set_mismatch")
            continue
        try:
            scored = score_result(result.get("items") or [], standard)
        except Exception as exc:  # noqa: BLE001 - 单病例降级
            logger.warning("单病例计分失败，降级 error_type=%s", type(exc).__name__)
            states[key] = _state(STATE_UNAVAILABLE, standard=standard, reason_code="score_failed")
            continue
        states[key] = _state(STATE_SCORED, standard=standard, scored=scored)
    return states


def project_customer_items(raw_items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """把 Canonical 原始条目投影为客户可见条目；is_confirmed_issue 的唯一 owner 为投影函数。"""
    from .custom_qc_workspace_service import project_customer_safe_result_item
    from .qc_workspace.canonical_result_store import customer_safe_projection_key

    hmac_key = customer_safe_projection_key()
    return [project_customer_safe_result_item(dict(item), hmac_key=hmac_key) for item in raw_items]


def _default_workspace() -> Any:
    from .custom_qc_workspace_service import CustomQCWorkspaceService

    return CustomQCWorkspaceService()


def _score_case_references(
    *, identity: CaseRef, dto: Mapping[str, Any], standard: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """只搬运已由本次读取核实的结果和标准引用；旧响应缺字段时保持可读。"""
    from .qc_workspace.canonical_result_store import customer_safe_projection_key, keyed_ref

    def reference_text(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    dto_rule_set_key = reference_text(dto.get("rule_set_key"))
    standard_rule_set_key = reference_text(standard.get("rule_set_key"))
    if dto_rule_set_key and dto_rule_set_key != standard_rule_set_key:
        raise ScoringStandardUnavailable("质控结果引用不一致")

    record_ref = reference_text(dto.get("record_ref"))
    if record_ref:
        expected_record_ref = keyed_ref(
            "rec", identity.as_key(), hmac_key=customer_safe_projection_key(),
        )
        if not compare_digest(record_ref, expected_record_ref):
            raise ScoringStandardUnavailable("质控结果引用不一致")

    job_id = reference_text(dto.get("job_id"))
    root_job_id = reference_text(dto.get("root_job_id"))
    if job_id and root_job_id and job_id != root_job_id:
        raise ScoringStandardUnavailable("质控结果引用不一致")

    envelope_id = reference_text(dto.get("envelope_id"))
    rule_set_version = reference_text(dto.get("rule_set_version"))
    result_ref = None
    if all((record_ref, envelope_id, root_job_id, dto_rule_set_key, rule_set_version)):
        result_ref = {
            "envelope_id": envelope_id,
            "root_job_id": root_job_id,
            **identity.as_dict(),
            "rule_set_key": dto_rule_set_key,
            "rule_set_version": rule_set_version,
        }

    standard_id = reference_text(standard.get("id"))
    standard_version_seq = standard.get("version_seq")
    standard_updated_at = standard.get("updated_at")
    valid_updated_at = isinstance(standard_updated_at, datetime)
    if isinstance(standard_updated_at, str) and standard_updated_at.strip():
        try:
            datetime.fromisoformat(standard_updated_at.strip().replace("Z", "+00:00"))
            valid_updated_at = True
        except ValueError:
            valid_updated_at = False
    standard_ref = None
    if (
        standard_id
        and type(standard_version_seq) is int
        and standard_version_seq >= 1
        and valid_updated_at
    ):
        standard_ref = {
            "standard_id": standard_id,
            "version_seq": standard_version_seq,
            "updated_at": standard_updated_at,
        }
    return result_ref, standard_ref


def score_case(
    *, institute_id: str, patient_id: str, visit_id: str, scene: str,
    standard_loader: Callable[[str], Mapping[str, Any] | None] | None = None,
    workspace_factory: Callable[[], Any] | None = None,
    projector: Callable[[Iterable[Mapping[str, Any]]], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """单病历计分：场景默认标准 + 单病历最新 ready 结果。

    无默认标准 {status: no_standard}；无 ready 结果 {status: no_result, result_state}；
    标准读取失败抛 ScoringStandardUnavailable，结果读取失败原样上抛（路由脱敏为 503）。
    """
    identity = CaseRef(
        str(institute_id or "").strip(),
        str(patient_id or "").strip(),
        str(visit_id or "").strip(),
    )
    standard = (standard_loader or get_default_standard)(scene)
    if standard is None:
        return {"status": STATE_NO_STANDARD, "scene": scene}
    dto = (workspace_factory or _default_workspace)().build_latest_single_record_result_dto(
        **identity.as_dict(),
        rule_set_key=standard["rule_set_key"],
    )
    state = str((dto or {}).get("state") or "") if isinstance(dto, Mapping) else ""
    if state != "ready":
        return {
            "status": STATE_NO_RESULT, "scene": scene, "result_state": state or "unknown",
            "standard_id": standard.get("id"),
        }
    result_ref, standard_ref = _score_case_references(
        identity=identity, dto=dto, standard=standard,
    )
    scored = score_result((projector or project_customer_items)(dto.get("items") or []), standard)
    return {
        "status": STATE_SCORED,
        "scene": scene,
        "standard_name": standard.get("name"),
        "rule_set_key": dto.get("rule_set_key"),
        "rule_set_version": dto.get("rule_set_version"),
        "job_id": dto.get("job_id"),
        "result_ref": result_ref,
        "standard_ref": standard_ref,
        **scored,
    }


def _load_page_results(
    refs: list[dict[str, str]], session_factory: Callable[[], Any] | None,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """本页条目：复用病历池读取器 include_items=True，只对本页 ready 病例再读一次（≤ page_size）。"""
    return _default_workspace().build_luxian_0609_completed_record_result_summaries(
        record_refs=refs, session_factory=session_factory, include_items=True,
    )


def score_workstation_page(
    page_scenes: Mapping[tuple[str, str, str], str],
    anchors: Mapping[tuple[str, str, str], Mapping[str, Any]],
    *,
    session_factory: Callable[[], Any] | None = None,
    standard_loader: Callable[[str], Mapping[str, Any] | None] = get_default_standard,
    results_loader: Callable[..., Mapping[tuple[str, str, str], Mapping[str, Any]]] = _load_page_results,
    projector: Callable[[Iterable[Mapping[str, Any]]], list[dict[str, Any]]] = project_customer_items,
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    """V5 列表本页 ready 病例计分。

    page_scenes 为 {三坐标: 场景}；anchors 为读取器原始摘要（取 envelope_id 核对结果对象未变）。
    返回 (每病例 score_state, 每场景标准概况)。没有默认标准的场景不读条目（零额外成本）。
    """
    standards: dict[str, Mapping[str, Any] | None] = {}
    overview: dict[str, dict[str, Any]] = {}
    states: dict[tuple[str, str, str], dict[str, Any]] = {}
    for scene in sorted(set(page_scenes.values())):
        try:
            standards[scene] = standard_loader(scene)
            standard = standards[scene]
            overview[scene] = (
                {"status": "no_standard", "standard_id": None, "standard_name": None, "standard_updated_at": None}
                if standard is None
                else {
                    "status": "configured", "standard_id": standard.get("id"),
                    "standard_name": standard.get("name"), "standard_updated_at": standard.get("updated_at"),
                }
            )
        except Exception as exc:  # noqa: BLE001 - 标准不可用降级
            logger.warning("病历列表评分标准读取失败，降级 error_type=%s", type(exc).__name__)
            standards[scene] = None
            overview[scene] = {
                "status": "unavailable", "standard_id": None, "standard_name": None, "standard_updated_at": None,
            }

    to_score: dict[tuple[str, str, str], str] = {}
    for identity, scene in page_scenes.items():
        standard = standards.get(scene)
        if overview[scene]["status"] == "unavailable":
            states[identity] = _state(STATE_UNAVAILABLE, reason_code="standard_unavailable")
        elif standard is None:
            states[identity] = _state(STATE_NO_STANDARD)
        elif standard.get("rule_set_key") != LUXIAN_0609_RULE_SET_KEY:
            # 病历池只读取 LX0609 结果；默认标准指向其他规则集时无法计分。
            states[identity] = _state(STATE_UNAVAILABLE, standard=standard, reason_code="rule_set_mismatch")
        else:
            to_score[identity] = scene
    if not to_score:
        return states, overview

    try:
        loaded = results_loader(
            [{"institute_id": i, "patient_id": p, "visit_id": v} for i, p, v in sorted(to_score)],
            session_factory,
        )
    except Exception as exc:  # noqa: BLE001 - 条目读取失败降级
        logger.warning("病历列表计分条目读取失败，降级 error_type=%s", type(exc).__name__)
        loaded = None
    for identity, scene in to_score.items():
        standard = standards[scene]
        result = loaded.get(identity) if isinstance(loaded, Mapping) else None
        anchor = anchors.get(identity) or {}
        if not isinstance(result, Mapping) or result.get("status") != "ready":
            states[identity] = _state(STATE_UNAVAILABLE, standard=standard, reason_code="result_unavailable")
            continue
        if str(result.get("envelope_id") or "") != str(anchor.get("envelope_id") or ""):
            # 两次读取之间结果对象已变化：不以新结果给旧摘要计分。
            states[identity] = _state(STATE_UNAVAILABLE, standard=standard, reason_code="result_changed")
            continue
        try:
            scored = score_result(projector(result.get("items") or []), standard)
        except Exception as exc:  # noqa: BLE001 - 单病例降级
            logger.warning("病历列表单病例计分失败，降级 error_type=%s", type(exc).__name__)
            states[identity] = _state(STATE_UNAVAILABLE, standard=standard, reason_code="score_failed")
            continue
        states[identity] = _state(STATE_SCORED, standard=standard, scored=scored)
    return states, overview


__all__ = [
    "ScoringStandardUnavailable",
    "grade_for",
    "project_customer_items",
    "score_case",
    "score_cases",
    "score_result",
    "score_workstation_page",
]
