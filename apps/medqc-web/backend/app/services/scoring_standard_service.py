"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.v36_reports import (
    QCScoringDefaultBinding,
    QCScoringGroup,
    QCScoringItem,
    QCScoringStandard,
)
from .frontpage_rule_catalog import (
    FRONTPAGE_DOCUMENT_TYPE,
    FRONTPAGE_RULE_IDS,
    FRONTPAGE_RULE_SET,
    FRONTPAGE_RULE_SET_KEY,
)
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY, load_luxian_0609_rules
from .qc_rule_sets import SICHUAN_RULE_SETS

SCENES = ("running", "final", "outpatient", "frontpage")
STATUS_DRAFT = "draft"
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
STATUSES = (STATUS_DRAFT, STATUS_ACTIVE, STATUS_ARCHIVED)
_SCENE_EXTRA_RULE_SET_KEYS: dict[str, tuple[str, ...]] = {
    "final": (LUXIAN_0609_RULE_SET_KEY,)
}
_SCORING_EXCLUDED_RULE_SET_KEYS = frozenset({"luxian_0916_qc_v1"})
_CENT = Decimal("0.01")
_STANDARDS = QCScoringStandard.__table__
_GROUPS = QCScoringGroup.__table__
_ITEMS = QCScoringItem.__table__
_BINDINGS = QCScoringDefaultBinding.__table__


class ScoringStandardNotFound(LookupError):
    """评分标准不存在。"""


class ScoringStandardInvalid(ValueError):
    """请求不符合合同；problems 为逐条原因。"""

    def __init__(
        self, message: str, *, code: str = "invalid", problems: Sequence[str] = ()
    ) -> None:
        super().__init__(message)
        self.code = code
        self.problems = list(problems)


class ScoringStandardUnavailable(RuntimeError):
    """数据库或规则集版本读取失败；对外只给脱敏提示。"""


def _require_session_factory() -> Any:
    if SessionLocal is None:
        raise ScoringStandardUnavailable("数据库会话不可用")
    return SessionLocal


def scene_rule_set_keys(scene: Any) -> tuple[str, ...]:
    """场景可用规则集（目录顺序）：scope 与场景一致者，加上场景额外允许的规则集。"""
    if scene not in SCENES:
        return ()
    if scene == "frontpage":
        return (FRONTPAGE_RULE_SET_KEY,)
    extra = _SCENE_EXTRA_RULE_SET_KEYS.get(scene, ())
    return tuple(
        key
        for key, rule_set in SICHUAN_RULE_SETS.items()
        if key not in _SCORING_EXCLUDED_RULE_SET_KEYS
        and (rule_set.scope == scene or key in extra)
    )


def scene_catalog() -> list[dict[str, Any]]:
    """供管理页选择：每个场景可用的规则集。"""
    return [
        {
            "scene": scene,
            "rule_sets": [
                {
                    "rule_set_key": key,
                    "rule_set_name": (
                        FRONTPAGE_RULE_SET.name
                        if key == FRONTPAGE_RULE_SET_KEY
                        else SICHUAN_RULE_SETS[key].name
                    ),
                }
                for key in scene_rule_set_keys(scene)
            ],
        }
        for scene in SCENES
    ]


def _scene(value: Any) -> str:
    if not isinstance(value, str) or value.strip() not in SCENES:
        raise ScoringStandardInvalid(
            "scene 只能是 running、final、outpatient 或 frontpage"
        )
    return value.strip()


def rule_document_universe(rule_set_key: str) -> dict[str, frozenset[str]]:
    """评分文书范围只引用现代规则目录，不另造文书归属。"""
    if rule_set_key == FRONTPAGE_RULE_SET_KEY:
        return {
            rule_id: frozenset({FRONTPAGE_DOCUMENT_TYPE})
            for rule_id in FRONTPAGE_RULE_IDS
        }
    if rule_set_key != LUXIAN_0609_RULE_SET_KEY:
        return {}
    return {
        str(rule.get("rule_id") or "").strip().upper(): frozenset(
            str(value).strip()
            for value in rule.get("applicable_documents") or []
            if isinstance(value, str) and value.strip()
        )
        for rule in load_luxian_0609_rules()
        if str(rule.get("rule_id") or "").strip()
    }


def _load_bands(raw: Any) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw)
        return [
            {
                "name": str(band["name"]),
                "min_score": Decimal(str(band["min_score"])).quantize(_CENT),
                "max_score": Decimal(str(band["max_score"])).quantize(_CENT),
            }
            for band in data
        ]
    except (TypeError, ValueError, KeyError, InvalidOperation) as exc:
        raise ScoringStandardUnavailable("评分标准档位数据损坏") from exc


def _number(value: Any) -> float | None:
    return None if value is None else float(Decimal(str(value)).quantize(_CENT))


def _standard_row(session: Any, standard_id: str, *, for_update: bool = False) -> Any:
    statement = select(*_STANDARDS.c).where(_STANDARDS.c.id == standard_id)
    if for_update:
        statement = statement.with_for_update()
    return session.execute(statement).first()


def _groups_items(
    session: Any, standard_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    group_rows = session.execute(
        select(*_GROUPS.c)
        .where(_GROUPS.c.standard_id == standard_id)
        .order_by(_GROUPS.c.sort_order, _GROUPS.c.group_name)
    ).all()
    item_rows = session.execute(
        select(*_ITEMS.c)
        .where(_ITEMS.c.standard_id == standard_id)
        .order_by(_ITEMS.c.rule_id)
    ).all()
    groups = [
        {
            "group_name": row.group_name,
            "max_deduction": _number(row.max_deduction),
            "sort_order": int(row.sort_order),
        }
        for row in group_rows
    ]
    items = [
        {
            "group_name": row.group_name,
            "rule_id": row.rule_id,
            "deduction": _number(row.deduction),
            "is_veto": bool(row.is_veto),
            "enabled": bool(row.enabled),
            "department_scope_mode": row.department_scope_mode,
            "department_refs": json.loads(row.department_refs_json),
        }
        for row in item_rows
    ]
    return groups, items


def _row_item(row: Any) -> dict[str, Any]:
    bands = _load_bands(row.grade_bands_json)
    return {
        "id": row.id,
        "name": row.name,
        "scene": row.scene,
        "rule_set_key": row.rule_set_key,
        "status": row.status,
        "is_default": bool(row.is_default),
        "base_score": _number(row.base_score),
        "grade_bands": [
            {
                "name": band["name"],
                "min_score": float(band["min_score"]),
                "max_score": float(band["max_score"]),
            }
            for band in bands
        ],
        "veto_grade": row.veto_grade,
        "version_seq": int(row.version_seq),
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at,
        "activated_by": row.activated_by,
        "activated_at": row.activated_at,
    }


def _detail(session: Any, row: Any) -> dict[str, Any]:
    groups, items = _groups_items(session, row.id)
    return {
        **_row_item(row),
        "groups": groups,
        "items": items,
        "group_count": len(groups),
        "item_count": len(items),
        "rule_document_types": {
            rule_id: sorted(values)
            for rule_id, values in rule_document_universe(row.rule_set_key).items()
        },
    }


def list_standards(*, scene: Any = None, status: Any = None) -> dict[str, Any]:
    """标准列表（不含条目）；可按场景、状态筛选；默认标准在前，其余按更新时间倒序。"""
    if scene is not None:
        scene = _scene(scene)
    if status is not None and status not in STATUSES:
        raise ScoringStandardInvalid("status 只能是 draft、active 或 archived")
    factory = _require_session_factory()
    try:
        with factory() as session:
            statement = select(*_STANDARDS.c)
            if scene is not None:
                statement = statement.where(_STANDARDS.c.scene == scene)
            if status is not None:
                statement = statement.where(_STANDARDS.c.status == status)
            rows = session.execute(
                statement.order_by(
                    _STANDARDS.c.is_default.desc(),
                    _STANDARDS.c.updated_at.desc(),
                    _STANDARDS.c.id,
                )
            ).all()
            return {
                "items": [_row_item(row) for row in rows],
                "scenes": scene_catalog(),
            }
    except SQLAlchemyError as exc:
        raise ScoringStandardUnavailable("评分标准读取失败") from exc


def get_standard(standard_id: Any) -> dict[str, Any]:
    factory = _require_session_factory()
    try:
        with factory() as session:
            row = _standard_row(session, str(standard_id or ""))
            if row is None:
                raise ScoringStandardNotFound("评分标准不存在")
            return _detail(session, row)
    except SQLAlchemyError as exc:
        raise ScoringStandardUnavailable("评分标准读取失败") from exc


def get_default_standard(scene: Any) -> dict[str, Any] | None:
    """场景当前默认标准（含项目组与条目）；没有时返回 None。供计分读取，一次读取。"""
    scene = _scene(scene)
    factory = _require_session_factory()
    try:
        with factory() as session:
            row = session.execute(
                select(*_STANDARDS.c).where(
                    _STANDARDS.c.scene == scene,
                    _STANDARDS.c.status == STATUS_ACTIVE,
                    _STANDARDS.c.is_default.is_(True),
                )
            ).first()
            return None if row is None else _detail(session, row)
    except SQLAlchemyError as exc:
        raise ScoringStandardUnavailable("评分标准读取失败") from exc


def _special_report_scene(scene: Any) -> str:
    if scene != "final":
        raise ScoringStandardInvalid("特殊病历报表当前仅支持 final 执行场景")
    return scene


def _special_report_binding(session: Any, *, detail: bool = False) -> dict[str, Any]:
    binding = session.execute(
        select(*_BINDINGS.c).where(
            _BINDINGS.c.purpose == "special_report",
            _BINDINGS.c.execution_scene == "final",
        )
    ).first()
    data = {
        "purpose": "special_report",
        "execution_scene": "final",
        "version_seq": int(binding.version_seq) if binding else 0,
        "standard_id": binding.standard_id if binding else None,
        "standard_version_seq": binding.standard_version_seq if binding else None,
        "status": "no_standard",
        "standard": None,
    }
    if binding is None or binding.standard_id is None:
        return data
    row = _standard_row(session, binding.standard_id)
    if (
        row is None
        or row.status != STATUS_ACTIVE
        or row.scene != "final"
        or int(row.version_seq) != binding.standard_version_seq
        or row.rule_set_key not in scene_rule_set_keys("final")
    ):
        data["status"] = "unavailable"
        return data
    data["status"] = "configured"
    data["standard"] = _detail(session, row) if detail else _row_item(row)
    return data


def get_special_report_binding(scene: Any = "final") -> dict[str, Any]:
    """读取消费绑定，不借用终末默认；迁移缺失和数据库故障失败关闭。"""
    _special_report_scene(scene)
    try:
        with _require_session_factory()() as session:
            return _special_report_binding(session)
    except SQLAlchemyError as exc:
        raise ScoringStandardUnavailable("特殊报表评分绑定读取失败") from exc


def get_special_report_default_standard(scene: Any = "final") -> dict[str, Any] | None:
    """报表专用消费读取；返回固定标准版本，不修改历史评分或 Canonical。"""
    _special_report_scene(scene)
    try:
        with _require_session_factory()() as session:
            binding = _special_report_binding(session, detail=True)
            if binding["status"] == "unavailable":
                raise ScoringStandardUnavailable("特殊报表评分绑定已失效")
            standard = binding["standard"]
            if standard is not None:
                standard["binding_version_seq"] = binding["version_seq"]
                standard["binding_purpose"] = "special_report"
            return standard
    except SQLAlchemyError as exc:
        raise ScoringStandardUnavailable("特殊报表评分绑定读取失败") from exc
