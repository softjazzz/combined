"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.v36_reports import QCRuleSetVersion
from .coding_rule_catalog import (
    CODING_EXECUTABLE_RULE_IDS,
    CODING_PENDING_RULE_IDS,
    CODING_RULE_SET_KEY,
    get_coding_rule_set,
)
from .frontpage_rule_catalog import (
    get_frontpage_rule_set,
)
from .luxian_0609 import load_luxian_0609_dependency_inventory
from .luxian_0609.phase_scope import load_luxian_0609_phase_scope
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .medical_core_system_catalog import CORE_SYSTEM_IDS
from .qc_rule_sets import QCRuleSet, get_sichuan_rule_set
from .sample_validation_rule_sets import (
    LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS,
    get_luxian_0609_customer_execution_scope,
)

VERSIONABLE_RULE_SET_KEYS = frozenset({LUXIAN_0609_RULE_SET_KEY, CODING_RULE_SET_KEY})
STATE_ACTIVE = "active"
STATE_PAUSED = "paused"
STATE_OFFLINE = "offline"
STATE_DELETED = "deleted"
ENTRY_STATES = (STATE_ACTIVE, STATE_PAUSED, STATE_OFFLINE, STATE_DELETED)
STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_RETIRED = "retired"
SOURCE_BUILTIN = "builtin"
DRAFT_VERSION_PREFIX = "__draft__"
MAX_ENTRIES = 1000
MAX_RULE_ID_LENGTH = 64
MAX_INSTITUTE_ID_LENGTH = 64
MAX_DEPARTMENT_NAME_LENGTH = 100
_TABLE = QCRuleSetVersion.__table__


class RuleSetVersionNotFound(LookupError):
    """规则集、版本或草稿不存在。"""


class RuleSetVersionInvalid(ValueError):
    """请求参数或发布内容不符合合同；problems 为逐条原因。"""

    def __init__(
        self, message: str, *, code: str = "invalid", problems: Sequence[str] = ()
    ) -> None:
        super().__init__(message)
        self.code = code
        self.problems = list(problems)


class RuleSetVersionUnavailable(RuntimeError):
    """数据库不可用、读写失败或已发布内容完整性校验失败；对外只给脱敏提示。"""


def _require_session_factory() -> Any:
    if SessionLocal is None:
        raise RuleSetVersionUnavailable("数据库会话不可用")
    return SessionLocal


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _rule_set(rule_set_key: Any) -> QCRuleSet:
    rule_set = (
        get_frontpage_rule_set(rule_set_key)
        or get_coding_rule_set(rule_set_key)
        or get_sichuan_rule_set(rule_set_key)
    )
    if rule_set is None:
        raise RuleSetVersionNotFound("规则集不存在")
    return rule_set


def _builtin_partition(
    rule_set: QCRuleSet,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """内置版本的 active/paused/excluded，与 prepare 现行“全选规则”计算严格等价。

    LX0609：先按客户排除名单剔除，再用 phase 划分拆出正式可执行与暂停规则；
    其余规则集：prepare 直接使用 rule_set.rule_ids，无暂停、无排除。
    """
    if rule_set.key == LUXIAN_0609_RULE_SET_KEY:
        # 目标目录含未注册条目，不能把总目录冒充客户交付范围；只消费既有权威投影。
        active, paused = get_luxian_0609_customer_execution_scope()
        excluded = tuple(
            rule_id
            for rule_id in rule_set.rule_ids
            if _clean(rule_id).upper() in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        )
        return tuple(active), tuple(paused), excluded
    if rule_set.key == CODING_RULE_SET_KEY:
        return (
            tuple(
                rule_id
                for rule_id in rule_set.rule_ids
                if rule_id not in CODING_PENDING_RULE_IDS
            ),
            tuple(
                rule_id
                for rule_id in rule_set.rule_ids
                if rule_id in CODING_PENDING_RULE_IDS
            ),
            (),
        )
    return tuple(rule_set.rule_ids), (), ()


def _entries_from_partition(
    active: Iterable[str],
    paused: Iterable[str],
    offline: Iterable[str],
    deleted: Iterable[str] = (),
) -> list[dict[str, str]]:
    entries = [
        *({"rule_id": rule_id, "state": STATE_ACTIVE} for rule_id in active),
        *({"rule_id": rule_id, "state": STATE_PAUSED} for rule_id in paused),
        *({"rule_id": rule_id, "state": STATE_OFFLINE} for rule_id in offline),
        *({"rule_id": rule_id, "state": STATE_DELETED} for rule_id in deleted),
    ]
    return sorted(entries, key=lambda item: item["rule_id"])


def executable_rule_ids(rule_set_key: Any) -> frozenset[str]:
    """当前可执行（可设为 active）的规则。

    LX0609：总表 phase_status 为 phase_1_target（总表已保证其 implementation_status=active，
    即目录已注册）且在执行依赖清单中有执行包；其余规则集：内置 rule_ids 全部视为可执行。
    """
    rule_set = _rule_set(rule_set_key)
    if rule_set.key == CODING_RULE_SET_KEY:
        return CODING_EXECUTABLE_RULE_IDS
    if rule_set.key != LUXIAN_0609_RULE_SET_KEY:
        return frozenset(rule_set.rule_ids)
    inventory = {item.rule_id for item in load_luxian_0609_dependency_inventory()}
    return frozenset(
        entry.rule_id
        for entry in load_luxian_0609_phase_scope()
        if entry.phase_status == "phase_1_target"
        and entry.catalog_registered
        and entry.rule_id in inventory
    )


def normalize_entries(raw: Any) -> list[dict[str, Any]]:
    """规范化版本条目；旧版本缺少适用配置时保留未配置语义。"""
    if not isinstance(raw, list):
        raise RuleSetVersionInvalid("entries 必须是数组")
    if len(raw) > MAX_ENTRIES:
        raise RuleSetVersionInvalid(f"entries 不能超过 {MAX_ENTRIES} 条")
    normalized: dict[str, dict[str, Any]] = {}
    allowed_keys = {
        "rule_id",
        "state",
        "department_scope_mode",
        "department_refs",
        "doctor_visible",
        "core_system_ids",
        "defect_category",
        "defect_type",
        "reminder_level",
    }
    for item in raw:
        if (
            not isinstance(item, Mapping)
            or not {"rule_id", "state"}.issubset(item)
            or set(item) - allowed_keys
        ):
            raise RuleSetVersionInvalid("entries 条目字段无效")
        rule_id = item.get("rule_id")
        state = item.get("state")
        if (
            not isinstance(rule_id, str)
            or not rule_id.strip()
            or len(rule_id.strip()) > MAX_RULE_ID_LENGTH
        ):
            raise RuleSetVersionInvalid("entries 中 rule_id 无效")
        if not isinstance(state, str) or state not in ENTRY_STATES:
            raise RuleSetVersionInvalid(
                "entries 中 state 只能是 active、paused、offline 或 deleted"
            )
        rule_id = rule_id.strip().upper()
        if rule_id in normalized:
            raise RuleSetVersionInvalid(f"entries 中规则重复：{rule_id}")
        normalized_item: dict[str, Any] = {"rule_id": rule_id, "state": state}
        for key in ("defect_category", "defect_type", "reminder_level"):
            if key in item:
                value = item[key]
                if value is not None and (
                    not isinstance(value, str)
                    or not value.strip()
                    or len(value.strip()) > 80
                ):
                    raise RuleSetVersionInvalid(
                        "缺陷分类/提醒等级必须为 1 到 80 字符或 null"
                    )
                normalized_item[key] = value.strip() if value is not None else None
        if "core_system_ids" in item:
            core_ids = item["core_system_ids"]
            if core_ids is not None and (
                not isinstance(core_ids, list)
                or any(
                    not isinstance(value, str) or value not in CORE_SYSTEM_IDS
                    for value in core_ids
                )
                or len(core_ids) != len(set(core_ids))
            ):
                raise RuleSetVersionInvalid(
                    "entries 中核心制度归属必须为固定制度ID数组或 null"
                )
            normalized_item["core_system_ids"] = (
                None if core_ids is None else sorted(core_ids)
            )
        configured = any(
            key in item
            for key in {"department_scope_mode", "department_refs", "doctor_visible"}
        )
        if configured:
            mode = item.get("department_scope_mode")
            refs = item.get("department_refs")
            doctor_visible = item.get("doctor_visible")
            if mode is not None and (
                not isinstance(mode, str) or mode not in {"all", "selected"}
            ):
                raise RuleSetVersionInvalid("entries 中科室范围模式无效")
            if refs is not None and not isinstance(refs, list):
                raise RuleSetVersionInvalid("entries 中科室范围引用无效")
            normalized_refs: list[dict[str, str]] | None = None
            if isinstance(refs, list):
                seen_refs: set[tuple[str, str]] = set()
                normalized_refs = []
                for ref in refs:
                    if not isinstance(ref, Mapping) or set(ref) != {
                        "institute_id",
                        "department_name",
                    }:
                        raise RuleSetVersionInvalid("entries 中科室范围引用无效")
                    institute_id = _clean(ref.get("institute_id"))
                    department_name = _clean(ref.get("department_name"))
                    if (
                        not institute_id
                        or not department_name
                        or len(institute_id) > MAX_INSTITUTE_ID_LENGTH
                        or len(department_name) > MAX_DEPARTMENT_NAME_LENGTH
                    ):
                        raise RuleSetVersionInvalid("entries 中科室范围引用无效")
                    pair = (institute_id, department_name)
                    if pair not in seen_refs:
                        seen_refs.add(pair)
                        normalized_refs.append(
                            {
                                "institute_id": institute_id,
                                "department_name": department_name,
                            }
                        )
                normalized_refs.sort(
                    key=lambda ref: (ref["institute_id"], ref["department_name"])
                )
            if doctor_visible is not None and type(doctor_visible) is not bool:
                raise RuleSetVersionInvalid("entries 中医生端开关无效")
            normalized_item.update(
                {
                    "department_scope_mode": mode,
                    "department_refs": normalized_refs,
                    "doctor_visible": doctor_visible,
                }
            )
        normalized[rule_id] = normalized_item
    return [normalized[rule_id] for rule_id in sorted(normalized)]


def dump_entries(entries: Sequence[Mapping[str, Any]]) -> str:
    """规范化序列化：按 rule_id 排序、键排序、紧凑分隔符、保留中文。"""
    ordered = sorted(
        (dict(item) for item in entries),
        key=lambda item: item["rule_id"],
    )
    return json.dumps(
        ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def compute_entries_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    """entries 规范化 JSON 的 UTF-8 SHA-256 十六进制摘要。"""
    return hashlib.sha256(dump_entries(entries).encode("utf-8")).hexdigest()


def _ordered(rule_set: QCRuleSet, rule_ids: Iterable[str]) -> list[str]:
    """按规则集目录顺序输出（目录外的按 rule_id 排在末尾），与 prepare 的目录顺序一致。"""
    order = {rule_id: index for index, rule_id in enumerate(rule_set.rule_ids)}
    return sorted(
        set(rule_ids), key=lambda rule_id: (order.get(rule_id, len(order)), rule_id)
    )


def _resolution(
    rule_set: QCRuleSet,
    *,
    version: str,
    source: str,
    entries: Sequence[Mapping[str, str]],
    content_digest: str,
) -> dict[str, Any]:
    by_state: dict[str, list[str]] = {state: [] for state in ENTRY_STATES}
    for item in entries:
        by_state[item["state"]].append(item["rule_id"])
    offline_rule_ids = _ordered(rule_set, by_state[STATE_OFFLINE])
    deleted_rule_ids = _ordered(rule_set, by_state[STATE_DELETED])
    return {
        "rule_set_key": rule_set.key,
        "version": version,
        "source": source,
        "active_rule_ids": _ordered(rule_set, by_state[STATE_ACTIVE]),
        "paused_rule_ids": _ordered(rule_set, by_state[STATE_PAUSED]),
        "offline_rule_ids": offline_rule_ids,
        "deleted_rule_ids": deleted_rule_ids,
        # 执行消费者继续只认 excluded；墓碑与下线规则都不得进入执行。
        "excluded_rule_ids": _ordered(rule_set, [*offline_rule_ids, *deleted_rule_ids]),
        "content_digest": content_digest,
        "entries": [dict(item) for item in entries],
    }


def _builtin_resolution(rule_set: QCRuleSet) -> dict[str, Any]:
    active, paused, excluded = _builtin_partition(rule_set)
    entries = _entries_from_partition(active, paused, excluded)
    return {
        "rule_set_key": rule_set.key,
        "version": rule_set.version,
        "source": SOURCE_BUILTIN,
        # 内置版本保持现行计算的原始顺序，不重排。
        "active_rule_ids": list(active),
        "paused_rule_ids": list(paused),
        "offline_rule_ids": list(excluded),
        "deleted_rule_ids": [],
        "excluded_rule_ids": list(excluded),
        "content_digest": compute_entries_digest(entries),
        "entries": entries,
    }


def _stored_entries(row: Any) -> list[dict[str, str]]:
    """读出已发布内容并校验完整性：内容必须是规范化形式且摘要一致，否则失败关闭。"""
    try:
        entries = normalize_entries(json.loads(row.entries_json))
    except (TypeError, ValueError) as exc:
        raise RuleSetVersionUnavailable("规则集版本内容损坏") from exc
    if row.status != STATUS_DRAFT and (
        dump_entries(entries) != row.entries_json
        or compute_entries_digest(entries) != row.content_digest
    ):
        raise RuleSetVersionUnavailable("规则集版本内容摘要不一致")
    return entries


_ROW_COLUMNS = tuple(_TABLE.c)


def _published_row(session: Any, rule_set_key: str, version: str) -> Any:
    return session.execute(
        select(*_ROW_COLUMNS).where(
            _TABLE.c.rule_set_key == rule_set_key,
            _TABLE.c.version == version,
            _TABLE.c.status.in_((STATUS_PUBLISHED, STATUS_RETIRED)),
        )
    ).first()


def _resolve_in_session(
    session: Any, rule_set: QCRuleSet, version: str
) -> dict[str, Any]:
    if version == rule_set.version:
        return _builtin_resolution(rule_set)
    if (
        rule_set.key not in VERSIONABLE_RULE_SET_KEYS
        or not version
        or version.startswith(DRAFT_VERSION_PREFIX)
    ):
        raise RuleSetVersionNotFound("规则集版本不存在")
    row = _published_row(session, rule_set.key, version)
    if row is None:
        raise RuleSetVersionNotFound("规则集版本不存在")
    return _resolution(
        rule_set,
        version=row.version,
        source=row.status,
        entries=_stored_entries(row),
        content_digest=row.content_digest,
    )


def _current_in_session(session: Any, rule_set: QCRuleSet) -> str:
    if rule_set.key not in VERSIONABLE_RULE_SET_KEYS:
        return rule_set.version
    row = session.execute(
        select(_TABLE.c.version)
        .where(
            _TABLE.c.rule_set_key == rule_set.key, _TABLE.c.status == STATUS_PUBLISHED
        )
        .order_by(
            _TABLE.c.published_at.desc(), _TABLE.c.created_at.desc(), _TABLE.c.id.desc()
        )
        .limit(1)
    ).first()
    return row.version if row is not None else rule_set.version


def resolve_rule_set_version(rule_set_key: Any, version: Any) -> dict[str, Any]:
    """规则集版本解析唯一 owner。

    返回 {rule_set_key, version, source(builtin|published|retired), active_rule_ids,
    paused_rule_ids, excluded_rule_ids, content_digest}；不存在抛 RuleSetVersionNotFound。
    内置版本不读数据库，表为空时行为与现行静态逻辑一致。
    """
    rule_set = _rule_set(rule_set_key)
    version = _clean(version)
    if version == rule_set.version:
        return _builtin_resolution(rule_set)
    if rule_set.key not in VERSIONABLE_RULE_SET_KEYS:
        raise RuleSetVersionNotFound("规则集版本不存在")
    factory = _require_session_factory()
    try:
        with factory() as session:
            return _resolve_in_session(session, rule_set, version)
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集版本读取失败") from exc


def current_version(rule_set_key: Any) -> str:
    """当前版本：最近一次 published 的版本；没有时为内置版本。非版本化规则集不读数据库。"""
    rule_set = _rule_set(rule_set_key)
    if rule_set.key not in VERSIONABLE_RULE_SET_KEYS:
        return rule_set.version
    factory = _require_session_factory()
    try:
        with factory() as session:
            return _current_in_session(session, rule_set)
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集版本读取失败") from exc


def known_versions(rule_set_key: Any) -> frozenset[str]:
    """读取侧版本集合唯一 owner（合同 8.2）：内置版本 + 全部 published/retired 版本（草稿除外）。

    非版本化规则集不读数据库，只返回内置版本；版本化规则集只执行一次查询，
    表中没有已发布/已下线行时返回 {内置}。读库失败抛 RuleSetVersionUnavailable（失败关闭）。
    """
    rule_set = _rule_set(rule_set_key)
    if rule_set.key not in VERSIONABLE_RULE_SET_KEYS:
        return frozenset({rule_set.version})
    factory = _require_session_factory()
    try:
        with factory() as session:
            rows = session.execute(
                select(_TABLE.c.version).where(
                    _TABLE.c.rule_set_key == rule_set.key,
                    _TABLE.c.status.in_((STATUS_PUBLISHED, STATUS_RETIRED)),
                )
            ).all()
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集版本读取失败") from exc
    return frozenset(
        {
            rule_set.version,
            *(_clean(row.version) for row in rows if _clean(row.version)),
        }
    )
