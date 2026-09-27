"""评分标准服务（V3.6 P2-S 评分标准与计分服务合同第 2、4 节）。

- 标准的创建、修改、复制、启用、归档、删除；项目组与扣分条目整表保存。
- 只有 draft 可编辑/删除；active 不可改，须复制为新草稿再启用；archived 只读。
- 所有写操作以 version_seq 做 CAS；启用时在同一事务内处理同场景原默认标准
  （归档或只取消默认标记，由 replace_mode 决定），部分唯一索引兜底“每场景最多一个默认”。
- 场景可用规则集（``scene_rule_set_keys``）：按 ``SICHUAN_RULE_SETS`` 的 scope 匹配，另把
  LX0609 纳入 final（见 ``_SCENE_EXTRA_RULE_SET_KEYS`` 注释）；标准的 rule_set_key 必须属于其场景。
- 条目 rule_id 必须属于该规则集当前版本全集（active + paused + excluded），否则 422。
- 档位 bands 校验失败 422 并逐条列出问题；数据库故障统一抛 ScoringStandardUnavailable（对外脱敏）。

本模块不计分；计分唯一 owner 为 ``scoring_service.score_result``。
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCScoringGroup, QCScoringItem, QCScoringStandard
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .qc_rule_sets import SICHUAN_RULE_SETS
from .rule_set_version_service import (
    RuleSetVersionNotFound,
    RuleSetVersionUnavailable,
    current_version,
    resolve_rule_set_version,
)

SCENES = ("running", "final", "outpatient")
STATUS_DRAFT = "draft"
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
STATUSES = (STATUS_DRAFT, STATUS_ACTIVE, STATUS_ARCHIVED)

REPLACE_ARCHIVE = "archive"
REPLACE_UNDEFAULT = "undefault"
REPLACE_MODES = (REPLACE_ARCHIVE, REPLACE_UNDEFAULT)

# LX0609 目录 scope 登记为 running，但同一规则集在终末场景同样执行：任务 filters 的
# record_scene_snapshot 按病历记录 running/final（custom_qc_workspace_service._record_scene），
# V5 终末列表读取的也是 LX0609 结果。因此终末场景额外允许 LX0609。
_SCENE_EXTRA_RULE_SET_KEYS: dict[str, tuple[str, ...]] = {"final": (LUXIAN_0609_RULE_SET_KEY,)}
# 0916 规则集说明明确“不计算评分”，不进入任何场景。
_SCORING_EXCLUDED_RULE_SET_KEYS = frozenset({"luxian_0916_qc_v1"})

MAX_NAME_LENGTH = 100
MAX_GROUP_NAME_LENGTH = 100
MAX_GRADE_NAME_LENGTH = 50
MAX_RULE_ID_LENGTH = 64
MAX_ACTOR_LENGTH = 64
MAX_BANDS = 20
MAX_GROUPS = 200
MAX_ITEMS = 1000
_MAX_AMOUNT = Decimal("9999.99")
_CENT = Decimal("0.01")

_STANDARDS = QCScoringStandard.__table__
_GROUPS = QCScoringGroup.__table__
_ITEMS = QCScoringItem.__table__


class ScoringStandardNotFound(LookupError):
    """评分标准不存在。"""


class ScoringStandardInvalid(ValueError):
    """请求不符合合同；problems 为逐条原因。"""

    def __init__(self, message: str, *, code: str = "invalid", problems: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.problems = list(problems)


class ScoringStandardConflict(ValueError):
    """CAS 冲突、名称重复、状态不允许等。"""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class ScoringStandardUnavailable(RuntimeError):
    """数据库或规则集版本读取失败；对外只给脱敏提示。"""


def _require_session_factory() -> Any:
    if SessionLocal is None:
        raise ScoringStandardUnavailable("数据库会话不可用")
    return SessionLocal


def _now() -> datetime:
    # 与其他 qc 表一致：库内存无时区 UTC。
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# 场景与规则集
# ---------------------------------------------------------------------------


def scene_rule_set_keys(scene: Any) -> tuple[str, ...]:
    """场景可用规则集（目录顺序）：scope 与场景一致者，加上场景额外允许的规则集。"""
    if scene not in SCENES:
        return ()
    extra = _SCENE_EXTRA_RULE_SET_KEYS.get(scene, ())
    return tuple(
        key for key, rule_set in SICHUAN_RULE_SETS.items()
        if key not in _SCORING_EXCLUDED_RULE_SET_KEYS and (rule_set.scope == scene or key in extra)
    )


def scene_catalog() -> list[dict[str, Any]]:
    """供管理页选择：每个场景可用的规则集。"""
    return [
        {
            "scene": scene,
            "rule_sets": [
                {"rule_set_key": key, "rule_set_name": SICHUAN_RULE_SETS[key].name}
                for key in scene_rule_set_keys(scene)
            ],
        }
        for scene in SCENES
    ]


def _scene(value: Any) -> str:
    if not isinstance(value, str) or value.strip() not in SCENES:
        raise ScoringStandardInvalid("scene 只能是 running、final 或 outpatient")
    return value.strip()


def _scene_rule_set(scene: str, rule_set_key: Any) -> str:
    """校验标准规则集属于场景；缺省时场景只有一个可用规则集才自动选定。"""
    available = scene_rule_set_keys(scene)
    if not available:
        raise ScoringStandardInvalid("该场景暂无可评分的规则集", code="scene_without_rule_set")
    if rule_set_key is None or (isinstance(rule_set_key, str) and not rule_set_key.strip()):
        if len(available) != 1:
            raise ScoringStandardInvalid(
                "该场景有多个可用规则集，须指定 rule_set_key", problems=list(available),
            )
        return available[0]
    if not isinstance(rule_set_key, str) or rule_set_key.strip() not in available:
        raise ScoringStandardInvalid(
            "rule_set_key 与场景不一致", code="rule_set_scene_mismatch", problems=list(available),
        )
    return rule_set_key.strip()


def rule_set_universe(rule_set_key: str) -> frozenset[str]:
    """规则集当前版本全集（active + paused + excluded），规则 id 大写。"""
    try:
        resolution = resolve_rule_set_version(rule_set_key, current_version(rule_set_key))
    except RuleSetVersionUnavailable as exc:
        raise ScoringStandardUnavailable("规则集版本读取失败") from exc
    except RuleSetVersionNotFound as exc:
        raise ScoringStandardUnavailable("规则集当前版本不可解析") from exc
    return frozenset(
        str(rule_id).strip().upper()
        for key in ("active_rule_ids", "paused_rule_ids", "excluded_rule_ids")
        for rule_id in resolution[key]
    )


# ---------------------------------------------------------------------------
# 数值与档位
# ---------------------------------------------------------------------------


def _amount(value: Any, label: str, problems: list[str], *, allow_zero: bool = True) -> Decimal | None:
    """解析两位小数金额：非布尔的有限数，0（或 >0）到 9999.99。"""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        problems.append(f"{label} 必须是数字")
        return None
    if isinstance(value, float) and not math.isfinite(value):
        problems.append(f"{label} 必须是有限数字")
        return None
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        problems.append(f"{label} 必须是数字")
        return None
    if not number.is_finite():
        problems.append(f"{label} 必须是有限数字")
        return None
    if number != number.quantize(_CENT, rounding=ROUND_HALF_UP):
        problems.append(f"{label} 最多保留两位小数")
        return None
    number = number.quantize(_CENT)
    if number < 0 or (not allow_zero and number == 0):
        problems.append(f"{label} 必须{'大于' if not allow_zero else '不小于'} 0")
        return None
    if number > _MAX_AMOUNT:
        problems.append(f"{label} 不能超过 {_MAX_AMOUNT}")
        return None
    return number


def _text(value: Any, label: str, max_length: int, problems: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{label} 不能为空")
        return None
    value = value.strip()
    if len(value) > max_length:
        problems.append(f"{label} 不能超过 {max_length} 个字符")
        return None
    return value


def validate_grade_bands(
    raw_bands: Any, base_score: Decimal | None, veto_grade: Any,
) -> tuple[list[dict[str, Any]], str | None, list[str]]:
    """档位校验（合同第 2 节）：返回 (规范化 bands, veto_grade, 问题列表)。

    bands 必须按分数降序排列；区间左闭右开、最高档右闭；相邻档位首尾相接（无空隙、无重叠），
    最高档上限等于 base_score、最低档下限为 0，即恰好覆盖 [0, base_score]；档位个数不固定。
    """
    problems: list[str] = []
    bands: list[dict[str, Any]] = []
    if not isinstance(raw_bands, list) or not raw_bands:
        problems.append("grade_bands 至少需要 1 个档位")
        raw_bands = []
    elif len(raw_bands) > MAX_BANDS:
        problems.append(f"grade_bands 不能超过 {MAX_BANDS} 个档位")
        raw_bands = []
    names: set[str] = set()
    for index, raw in enumerate(raw_bands, start=1):
        label = f"第 {index} 档"
        if not isinstance(raw, Mapping) or set(raw) != {"name", "min_score", "max_score"}:
            problems.append(f"{label} 必须且只能包含 name、min_score、max_score")
            continue
        name = _text(raw.get("name"), f"{label}名称", MAX_GRADE_NAME_LENGTH, problems)
        low = _amount(raw.get("min_score"), f"{label} min_score", problems)
        high = _amount(raw.get("max_score"), f"{label} max_score", problems)
        if name is not None:
            if name in names:
                problems.append(f"档位名称重复：{name}")
            names.add(name)
        if low is not None and high is not None and low >= high:
            problems.append(f"{label}（{name or '?'}）min_score 必须小于 max_score")
        bands.append({"name": name, "min_score": low, "max_score": high})

    complete = bands and not problems and all(
        band["min_score"] is not None and band["max_score"] is not None for band in bands
    )
    if complete:
        for previous, current in zip(bands, bands[1:]):
            if current["max_score"] > previous["max_score"]:
                problems.append("grade_bands 必须按分数降序排列")
                break
        else:
            for previous, current in zip(bands, bands[1:]):
                if current["max_score"] < previous["min_score"]:
                    problems.append(
                        f"档位 {current['name']} 与 {previous['name']} 之间有空隙："
                        f"[{current['max_score']}, {previous['min_score']})"
                    )
                elif current["max_score"] > previous["min_score"]:
                    problems.append(
                        f"档位 {current['name']} 与 {previous['name']} 重叠："
                        f"[{previous['min_score']}, {current['max_score']})"
                    )
            if base_score is not None and bands[0]["max_score"] != base_score:
                problems.append(f"最高档上限必须等于满分 {base_score}（当前 {bands[0]['max_score']}）")
            if bands[-1]["min_score"] != 0:
                problems.append(f"最低档下限必须为 0（当前 {bands[-1]['min_score']}），否则低分无档位")
    veto = veto_grade.strip() if isinstance(veto_grade, str) else None
    if not veto:
        problems.append("veto_grade 不能为空")
    elif names and veto not in names:
        problems.append(f"veto_grade（{veto}）必须是档位名称之一")
    return bands, veto, problems


def _dump_bands(bands: Iterable[Mapping[str, Any]]) -> str:
    return json.dumps(
        [
            {"name": band["name"], "min_score": float(band["min_score"]), "max_score": float(band["max_score"])}
            for band in bands
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


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


# ---------------------------------------------------------------------------
# 项目组与条目
# ---------------------------------------------------------------------------


def normalize_groups_items(
    raw_groups: Any, raw_items: Any, universe: frozenset[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """整表校验：组名唯一、条目所属组存在、rule_id 唯一且属于规则集当前版本全集。"""
    problems: list[str] = []
    if not isinstance(raw_groups, list) or not isinstance(raw_items, list):
        raise ScoringStandardInvalid("groups 与 items 必须是数组")
    if len(raw_groups) > MAX_GROUPS or len(raw_items) > MAX_ITEMS:
        raise ScoringStandardInvalid(f"项目组不能超过 {MAX_GROUPS} 个，条目不能超过 {MAX_ITEMS} 条")
    groups: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_groups, start=1):
        if not isinstance(raw, Mapping) or not set(raw) <= {"group_name", "max_deduction", "sort_order"}:
            problems.append(f"第 {index} 个项目组字段无效")
            continue
        name = _text(raw.get("group_name"), f"第 {index} 个项目组名称", MAX_GROUP_NAME_LENGTH, problems)
        max_deduction = None
        if raw.get("max_deduction") is not None:
            max_deduction = _amount(raw.get("max_deduction"), f"项目组 {name or index} 封顶分", problems)
        sort_order = raw.get("sort_order", index)
        if isinstance(sort_order, bool) or not isinstance(sort_order, int) or not 0 <= sort_order <= 100000:
            problems.append(f"项目组 {name or index} sort_order 无效")
            sort_order = index
        if name is None:
            continue
        if name in groups:
            problems.append(f"项目组名称重复：{name}")
            continue
        groups[name] = {"group_name": name, "max_deduction": max_deduction, "sort_order": sort_order}

    items: dict[str, dict[str, Any]] = {}
    unknown: list[str] = []
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, Mapping) or not {"group_name", "rule_id", "deduction"} <= set(raw) or not set(
            raw
        ) <= {"group_name", "rule_id", "deduction", "is_veto", "enabled"}:
            problems.append(f"第 {index} 条条目字段无效")
            continue
        rule_id = _text(raw.get("rule_id"), f"第 {index} 条 rule_id", MAX_RULE_ID_LENGTH, problems)
        rule_id = rule_id.upper() if rule_id else None
        group_name = raw.get("group_name").strip() if isinstance(raw.get("group_name"), str) else None
        deduction = _amount(raw.get("deduction"), f"条目 {rule_id or index} 扣分", problems)
        is_veto = raw.get("is_veto", False)
        enabled = raw.get("enabled", True)
        if not isinstance(is_veto, bool) or not isinstance(enabled, bool):
            problems.append(f"条目 {rule_id or index} is_veto/enabled 必须是布尔值")
            continue
        if not group_name or group_name not in groups:
            problems.append(f"条目 {rule_id or index} 所属项目组不存在：{group_name or '空'}")
            continue
        if rule_id is None or deduction is None:
            continue
        if rule_id in items:
            problems.append(f"规则重复（一条规则在一个标准内只属于一个项目组）：{rule_id}")
            continue
        if rule_id not in universe:
            unknown.append(rule_id)
        items[rule_id] = {
            "group_name": group_name, "rule_id": rule_id, "deduction": deduction,
            "is_veto": is_veto, "enabled": enabled,
        }
    if unknown:
        problems.append(f"以下规则不属于该规则集当前版本：{','.join(sorted(unknown))}")
    if problems:
        raise ScoringStandardInvalid("评分条目校验未通过", code="items_validation_failed", problems=problems)
    ordered_groups = sorted(groups.values(), key=lambda group: (group["sort_order"], group["group_name"]))
    return ordered_groups, [items[rule_id] for rule_id in sorted(items)]


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------


def _number(value: Any) -> float | None:
    return None if value is None else float(Decimal(str(value)).quantize(_CENT))


def _standard_row(session: Any, standard_id: str, *, for_update: bool = False) -> Any:
    statement = select(*_STANDARDS.c).where(_STANDARDS.c.id == standard_id)
    if for_update:
        statement = statement.with_for_update()
    return session.execute(statement).first()


def _groups_items(session: Any, standard_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    group_rows = session.execute(
        select(*_GROUPS.c).where(_GROUPS.c.standard_id == standard_id)
        .order_by(_GROUPS.c.sort_order, _GROUPS.c.group_name)
    ).all()
    item_rows = session.execute(
        select(*_ITEMS.c).where(_ITEMS.c.standard_id == standard_id).order_by(_ITEMS.c.rule_id)
    ).all()
    groups = [
        {"group_name": row.group_name, "max_deduction": _number(row.max_deduction), "sort_order": int(row.sort_order)}
        for row in group_rows
    ]
    items = [
        {
            "group_name": row.group_name, "rule_id": row.rule_id, "deduction": _number(row.deduction),
            "is_veto": bool(row.is_veto), "enabled": bool(row.enabled),
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
            {"name": band["name"], "min_score": float(band["min_score"]), "max_score": float(band["max_score"])}
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
    return {**_row_item(row), "groups": groups, "items": items, "group_count": len(groups), "item_count": len(items)}


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
                    _STANDARDS.c.is_default.desc(), _STANDARDS.c.updated_at.desc(), _STANDARDS.c.id,
                )
            ).all()
            return {"items": [_row_item(row) for row in rows], "scenes": scene_catalog()}
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


# ---------------------------------------------------------------------------
# 写入
# ---------------------------------------------------------------------------


def _actor(actor: Any) -> str:
    if not isinstance(actor, str) or not actor.strip() or len(actor) > MAX_ACTOR_LENGTH:
        raise ScoringStandardInvalid("当前用户缺少有效身份")
    return actor


def _version_seq(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise ScoringStandardInvalid("version_seq 无效")
    return value


def _checked_header(name: Any, base_score: Any, grade_bands: Any, veto_grade: Any) -> dict[str, Any]:
    problems: list[str] = []
    name = _text(name, "name", MAX_NAME_LENGTH, problems)
    base = _amount(base_score, "base_score", problems, allow_zero=False)
    bands, veto, band_problems = validate_grade_bands(grade_bands, base, veto_grade)
    problems.extend(band_problems)
    if problems:
        raise ScoringStandardInvalid("评分标准校验未通过", code="standard_validation_failed", problems=problems)
    return {"name": name, "base_score": base, "grade_bands_json": _dump_bands(bands), "veto_grade": veto}


def _lock_scene(session: Any, scene: str) -> None:
    """同一场景的启用/归档串行化（默认标准替换）。SQLite 单测跳过。"""
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"qc_scoring_standards:{scene}"})


def _locked_draft(session: Any, standard_id: str, version_seq: int) -> Any:
    row = _standard_row(session, standard_id, for_update=True)
    if row is None:
        raise ScoringStandardNotFound("评分标准不存在")
    if row.status != STATUS_DRAFT:
        raise ScoringStandardConflict("只有草稿可以修改，启用中的标准请复制为新草稿", code="not_draft")
    if int(row.version_seq) != version_seq:
        raise ScoringStandardConflict("评分标准已被修改，请刷新后重试", code="version_conflict")
    return row


def _cas_update(session: Any, row: Any, version_seq: int, **values: Any) -> None:
    updated = session.execute(
        update(_STANDARDS)
        .where(
            _STANDARDS.c.id == row.id, _STANDARDS.c.status == row.status,
            _STANDARDS.c.version_seq == version_seq,
        )
        .values(**values, version_seq=version_seq + 1)
    )
    if updated.rowcount != 1:
        raise ScoringStandardConflict("评分标准已被修改，请刷新后重试", code="version_conflict")


def _insert_children(
    session: Any, standard_id: str, groups: Sequence[Mapping[str, Any]], items: Sequence[Mapping[str, Any]],
) -> None:
    if groups:
        session.execute(insert(_GROUPS), [
            {
                "id": str(uuid4()), "standard_id": standard_id, "group_name": group["group_name"],
                "max_deduction": group["max_deduction"], "sort_order": group["sort_order"],
            }
            for group in groups
        ])
    if items:
        session.execute(insert(_ITEMS), [
            {
                "id": str(uuid4()), "standard_id": standard_id, "group_name": item["group_name"],
                "rule_id": item["rule_id"], "deduction": item["deduction"],
                "is_veto": item["is_veto"], "enabled": item["enabled"],
            }
            for item in items
        ])


def _write(action: str, func: Any) -> dict[str, Any]:
    """统一事务外壳：名称唯一冲突 409，其余数据库错误脱敏为不可用。"""
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                standard_id = func(session)
            row = _standard_row(session, standard_id)
            return _detail(session, row)
    except IntegrityError as exc:
        raise ScoringStandardConflict("同一场景下已有同名评分标准，或默认标准并发冲突", code="conflict") from exc
    except SQLAlchemyError as exc:
        raise ScoringStandardUnavailable(f"评分标准{action}失败") from exc


def _name_taken(session: Any, name: str, scene: str, *, exclude_id: str | None = None) -> bool:
    statement = select(_STANDARDS.c.id).where(_STANDARDS.c.name == name, _STANDARDS.c.scene == scene)
    if exclude_id is not None:
        statement = statement.where(_STANDARDS.c.id != exclude_id)
    return session.execute(statement.limit(1)).first() is not None


def create_standard(
    *, actor: str, name: Any, scene: Any, base_score: Any, grade_bands: Any, veto_grade: Any,
    rule_set_key: Any = None,
) -> dict[str, Any]:
    """新建草稿（不含条目）。"""
    actor = _actor(actor)
    scene = _scene(scene)
    rule_set_key = _scene_rule_set(scene, rule_set_key)
    header = _checked_header(name, base_score, grade_bands, veto_grade)
    standard_id = str(uuid4())

    def run(session: Any) -> str:
        if _name_taken(session, header["name"], scene):
            raise ScoringStandardConflict("同一场景下已有同名评分标准", code="name_exists")
        now = _now()
        session.execute(insert(_STANDARDS).values(
            id=standard_id, scene=scene, rule_set_key=rule_set_key, status=STATUS_DRAFT,
            is_default=False, version_seq=1, created_by=actor, created_at=now,
            updated_by=actor, updated_at=now, **header,
        ))
        return standard_id

    return _write("保存", run)


def update_standard(
    standard_id: Any, *, actor: str, version_seq: Any, name: Any = None, base_score: Any = None,
    grade_bands: Any = None, veto_grade: Any = None,
) -> dict[str, Any]:
    """按 version_seq CAS 修改草稿基本信息；None 字段保持不变，合并后整体重新校验档位。"""
    actor = _actor(actor)
    version_seq = _version_seq(version_seq)
    if name is None and base_score is None and grade_bands is None and veto_grade is None:
        raise ScoringStandardInvalid("没有需要更新的字段")
    standard_id = str(standard_id or "")

    def run(session: Any) -> str:
        row = _locked_draft(session, standard_id, version_seq)
        header = _checked_header(
            row.name if name is None else name,
            row.base_score if base_score is None else base_score,
            _load_bands(row.grade_bands_json) if grade_bands is None else grade_bands,
            row.veto_grade if veto_grade is None else veto_grade,
        )
        if _name_taken(session, header["name"], row.scene, exclude_id=row.id):
            raise ScoringStandardConflict("同一场景下已有同名评分标准", code="name_exists")
        _cas_update(session, row, version_seq, updated_by=actor, updated_at=_now(), **header)
        return row.id

    return _write("保存", run)


def save_items(
    standard_id: Any, *, actor: str, version_seq: Any, groups: Any, items: Any,
) -> dict[str, Any]:
    """项目组与条目整表保存（先删后插），按 version_seq CAS；rule_id 须属于规则集当前版本全集。"""
    actor = _actor(actor)
    version_seq = _version_seq(version_seq)
    standard_id = str(standard_id or "")
    # 先读规则集键以校验 rule_id；规则集版本读取在本事务外（它有自己的会话）。
    rule_set_key = get_standard(standard_id)["rule_set_key"]
    normalized_groups, normalized_items = normalize_groups_items(groups, items, rule_set_universe(rule_set_key))

    def run(session: Any) -> str:
        row = _locked_draft(session, standard_id, version_seq)
        if row.rule_set_key != rule_set_key:
            raise ScoringStandardConflict("评分标准已被修改，请刷新后重试", code="version_conflict")
        _cas_update(session, row, version_seq, updated_by=actor, updated_at=_now())
        # 显式删除子表（SQLite 默认不执行外键级联）。
        session.execute(delete(_ITEMS).where(_ITEMS.c.standard_id == row.id))
        session.execute(delete(_GROUPS).where(_GROUPS.c.standard_id == row.id))
        _insert_children(session, row.id, normalized_groups, normalized_items)
        return row.id

    return _write("保存", run)


def copy_standard(standard_id: Any, *, actor: str, name: Any) -> dict[str, Any]:
    """任意状态的标准复制为新草稿（含项目组与条目），名称由调用方给出。"""
    actor = _actor(actor)
    problems: list[str] = []
    new_name = _text(name, "name", MAX_NAME_LENGTH, problems)
    if problems:
        raise ScoringStandardInvalid("评分标准校验未通过", code="standard_validation_failed", problems=problems)
    source_id = str(standard_id or "")
    new_id = str(uuid4())

    def run(session: Any) -> str:
        source = _standard_row(session, source_id)
        if source is None:
            raise ScoringStandardNotFound("评分标准不存在")
        if _name_taken(session, new_name, source.scene):
            raise ScoringStandardConflict("同一场景下已有同名评分标准", code="name_exists")
        groups, items = _groups_items(session, source.id)
        now = _now()
        session.execute(insert(_STANDARDS).values(
            id=new_id, name=new_name, scene=source.scene, rule_set_key=source.rule_set_key,
            status=STATUS_DRAFT, is_default=False, base_score=source.base_score,
            grade_bands_json=source.grade_bands_json, veto_grade=source.veto_grade, version_seq=1,
            created_by=actor, created_at=now, updated_by=actor, updated_at=now,
        ))
        _insert_children(
            session, new_id,
            [{**group, "max_deduction": None if group["max_deduction"] is None else Decimal(str(group["max_deduction"]))}
             for group in groups],
            [{**item, "deduction": Decimal(str(item["deduction"]))} for item in items],
        )
        return new_id

    return _write("复制", run)


def activate_standard(
    standard_id: Any, *, actor: str, version_seq: Any, replace_mode: Any = REPLACE_ARCHIVE,
) -> dict[str, Any]:
    """草稿 → active 并设为场景默认；同一事务内把原默认标准归档或只取消默认标记。

    启用前重新校验档位与条目（规则集当前版本可能已变化），且至少有 1 条启用条目。
    """
    actor = _actor(actor)
    version_seq = _version_seq(version_seq)
    if replace_mode not in REPLACE_MODES:
        raise ScoringStandardInvalid("replace_mode 只能是 archive 或 undefault")
    standard_id = str(standard_id or "")
    snapshot = get_standard(standard_id)
    universe = rule_set_universe(snapshot["rule_set_key"])

    def run(session: Any) -> str:
        _lock_scene(session, snapshot["scene"])
        row = _locked_draft(session, standard_id, version_seq)
        # 只做校验：不通过抛 422。
        _checked_header(row.name, row.base_score, _load_bands(row.grade_bands_json), row.veto_grade)
        groups, items = _groups_items(session, row.id)
        normalize_groups_items(groups, items, universe)
        if not any(item["enabled"] for item in items):
            raise ScoringStandardInvalid(
                "评分标准校验未通过", code="standard_validation_failed", problems=["至少需要 1 条启用的扣分条目"],
            )
        now = _now()
        previous = session.execute(
            select(_STANDARDS.c.id).where(
                _STANDARDS.c.scene == row.scene, _STANDARDS.c.status == STATUS_ACTIVE,
                _STANDARDS.c.is_default.is_(True),
            ).with_for_update()
        ).all()
        for item in previous:
            values: dict[str, Any] = {"is_default": False, "updated_by": actor, "updated_at": now}
            if replace_mode == REPLACE_ARCHIVE:
                values["status"] = STATUS_ARCHIVED
            session.execute(
                update(_STANDARDS).where(_STANDARDS.c.id == item.id)
                .values(**values, version_seq=_STANDARDS.c.version_seq + 1)
            )
        _cas_update(
            session, row, version_seq, status=STATUS_ACTIVE, is_default=True,
            activated_by=actor, activated_at=now, updated_by=actor, updated_at=now,
        )
        return row.id

    return _write("启用", run)


def archive_standard(standard_id: Any, *, actor: str, version_seq: Any) -> dict[str, Any]:
    """active → archived（同时取消默认）；草稿请直接删除。"""
    actor = _actor(actor)
    version_seq = _version_seq(version_seq)
    standard_id = str(standard_id or "")

    def run(session: Any) -> str:
        row = _standard_row(session, standard_id, for_update=True)
        if row is None:
            raise ScoringStandardNotFound("评分标准不存在")
        if row.status != STATUS_ACTIVE:
            raise ScoringStandardConflict("只有启用中的标准可以归档", code="not_active")
        if int(row.version_seq) != version_seq:
            raise ScoringStandardConflict("评分标准已被修改，请刷新后重试", code="version_conflict")
        _cas_update(
            session, row, version_seq, status=STATUS_ARCHIVED, is_default=False,
            updated_by=actor, updated_at=_now(),
        )
        return row.id

    return _write("归档", run)


def delete_standard(standard_id: Any, *, actor: str, version_seq: Any) -> dict[str, Any]:
    """只能删除草稿（含其项目组与条目）。"""
    _actor(actor)
    version_seq = _version_seq(version_seq)
    standard_id = str(standard_id or "")
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                row = _locked_draft(session, standard_id, version_seq)
                session.execute(delete(_ITEMS).where(_ITEMS.c.standard_id == row.id))
                session.execute(delete(_GROUPS).where(_GROUPS.c.standard_id == row.id))
                deleted = session.execute(
                    delete(_STANDARDS).where(
                        _STANDARDS.c.id == row.id, _STANDARDS.c.status == STATUS_DRAFT,
                        _STANDARDS.c.version_seq == version_seq,
                    )
                )
                if deleted.rowcount != 1:
                    raise ScoringStandardConflict("评分标准已被修改，请刷新后重试", code="version_conflict")
    except SQLAlchemyError as exc:
        raise ScoringStandardUnavailable("评分标准删除失败") from exc
    return {"id": standard_id, "deleted": True}


__all__ = [
    "REPLACE_MODES",
    "SCENES",
    "STATUSES",
    "ScoringStandardConflict",
    "ScoringStandardInvalid",
    "ScoringStandardNotFound",
    "ScoringStandardUnavailable",
    "activate_standard",
    "archive_standard",
    "copy_standard",
    "create_standard",
    "delete_standard",
    "get_default_standard",
    "get_standard",
    "list_standards",
    "normalize_groups_items",
    "rule_set_universe",
    "save_items",
    "scene_catalog",
    "scene_rule_set_keys",
    "update_standard",
    "validate_grade_bands",
]
