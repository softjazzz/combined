"""规则集版本服务（V3.6 P1-E1 规则集版本发布合同第 2、3、4 节）。

- 解析唯一 owner：``resolve_rule_set_version(key, version)``。内置版本（``SICHUAN_RULE_SETS``
  当前 version）直接复用现行静态逻辑：phase 划分（``partition_luxian_0609_rule_scope``）与
  客户排除名单（``LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS``），不读数据库；已发布/已下线
  版本取自 ``entries_json`` 并校验 content_digest，摘要不符失败关闭。
- ``current_version(key)``：最近一次 published 的版本；没有则为内置版本。
- 草稿：每个规则集最多一份（部分唯一索引兜底），更新/删除/发布以 version_seq 做 CAS；
  发布在同一事务内完成校验、摘要写入与状态迁移；已发布版本只允许 published → retired。
- 本批只有 LX0609 可建草稿；其余已知规则集（含 0916）只支持内置版本。
- 数据库故障统一抛 RuleSetVersionUnavailable，对外脱敏。

本模块不改动任务创建、prepare、worker 与执行器判定（合同第 5 节由后续任务接入）。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCRuleSetVersion
from .luxian_0609 import load_luxian_0609_dependency_inventory
from .luxian_0609.phase_scope import (
    load_luxian_0609_phase_scope,
    partition_luxian_0609_rule_scope,
)
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .luxian_0609_rule_master import load_luxian_0609_rule_master
from .qc_rule_sets import QCRuleSet, get_sichuan_rule_set
from .coding_rule_catalog import (
    CODING_EXECUTABLE_RULE_IDS,
    CODING_PENDING_RULE_IDS,
    CODING_RULE_SET_KEY,
    coding_rule_metadata,
    get_coding_rule_set,
)
from .frontpage_rule_catalog import (
    FRONTPAGE_RULE_SET_KEY,
    frontpage_rule_metadata,
    get_frontpage_rule_set,
)
from .sample_validation_rule_sets import LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
from .medical_core_system_catalog import CORE_SYSTEM_IDS

# 本批允许 LX0609 与编码质控发布新版本；0916 等其余规则集只支持内置版本。
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

# 草稿尚无发布版本号；用唯一占位值满足 (rule_set_key, version) 非空唯一约束，对外不输出。
DRAFT_VERSION_PREFIX = "__draft__"
MAX_VERSION_LENGTH = 64
MAX_ACTOR_LENGTH = 64
MAX_NOTE_LENGTH = 1000
MAX_ENTRIES = 1000
MAX_RULE_ID_LENGTH = 64
MAX_INSTITUTE_ID_LENGTH = 64
MAX_DEPARTMENT_NAME_LENGTH = 100
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_TABLE = QCRuleSetVersion.__table__


class RuleSetVersionNotFound(LookupError):
    """规则集、版本或草稿不存在。"""


class RuleSetVersionInvalid(ValueError):
    """请求参数或发布内容不符合合同；problems 为逐条原因。"""

    def __init__(self, message: str, *, code: str = "invalid", problems: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.problems = list(problems)


class RuleSetVersionConflict(ValueError):
    """草稿已存在、版本号重复、CAS 冲突、不支持的规则集或不允许的状态迁移。"""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class RuleSetVersionUnavailable(RuntimeError):
    """数据库不可用、读写失败或已发布内容完整性校验失败；对外只给脱敏提示。"""


def _require_session_factory() -> Any:
    if SessionLocal is None:
        raise RuleSetVersionUnavailable("数据库会话不可用")
    return SessionLocal


def _now() -> datetime:
    # 与其他 qc 表一致：库内存无时区 UTC。
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean(value: Any) -> str:
    return str(value or "").strip()


# ---------------------------------------------------------------------------
# 规则集与内置版本
# ---------------------------------------------------------------------------


def _rule_set(rule_set_key: Any) -> QCRuleSet:
    rule_set = (
        get_frontpage_rule_set(rule_set_key)
        or get_coding_rule_set(rule_set_key)
        or get_sichuan_rule_set(rule_set_key)
    )
    if rule_set is None:
        raise RuleSetVersionNotFound("规则集不存在")
    return rule_set


def _versionable_rule_set(rule_set_key: Any) -> QCRuleSet:
    rule_set = _rule_set(rule_set_key)
    if rule_set.key not in VERSIONABLE_RULE_SET_KEYS:
        raise RuleSetVersionConflict("该规则集本批只支持内置版本", code="unsupported_rule_set")
    return rule_set


def _builtin_partition(rule_set: QCRuleSet) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """内置版本的 active/paused/excluded，与 prepare 现行“全选规则”计算严格等价。

    LX0609：先按客户排除名单剔除，再用 phase 划分拆出正式可执行与暂停规则；
    其余规则集：prepare 直接使用 rule_set.rule_ids，无暂停、无排除。
    """
    if rule_set.key == LUXIAN_0609_RULE_SET_KEY:
        selected = [
            rule_id for rule_id in rule_set.rule_ids
            if _clean(rule_id).upper() not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        ]
        active, paused = partition_luxian_0609_rule_scope(selected)
        excluded = tuple(
            rule_id for rule_id in rule_set.rule_ids
            if _clean(rule_id).upper() in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
        )
        return tuple(active), tuple(paused), excluded
    if rule_set.key == CODING_RULE_SET_KEY:
        return (
            tuple(rule_id for rule_id in rule_set.rule_ids if rule_id not in CODING_PENDING_RULE_IDS),
            tuple(rule_id for rule_id in rule_set.rule_ids if rule_id in CODING_PENDING_RULE_IDS),
            (),
        )
    return tuple(rule_set.rule_ids), (), ()


def _entries_from_partition(
    active: Iterable[str], paused: Iterable[str], offline: Iterable[str],
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


def _rule_display_metadata(rule_set_key: str) -> dict[str, dict[str, str | None]]:
    """规则展示元数据 {rule_id: {qc_point, source_document, category, category_name}}。

    LX0609 取规则主表（含已下线规则，一次加载且模块内缓存）；其余规则集暂无权威元数据，返回空映射，
    调用方给 null（前端显示未知，不猜测）。
    """
    if rule_set_key == CODING_RULE_SET_KEY:
        return coding_rule_metadata()
    if rule_set_key == FRONTPAGE_RULE_SET_KEY:
        return frontpage_rule_metadata()
    if rule_set_key != LUXIAN_0609_RULE_SET_KEY:
        return {}
    return {
        entry.rule_id: {
            "qc_point": entry.qc_point or None,
            "source_document": entry.source_document or None,
            "category": None,
            "category_name": None,
        }
        for entry in load_luxian_0609_rule_master()
    }


def with_executable_flags(rule_set_key: Any, item: Mapping[str, Any]) -> dict[str, Any]:
    """只读派生：为响应 entries 的每条规则附加 executable、qc_point、source_document。

    executable 的判定唯一 owner 仍为 ``executable_rule_ids``；qc_point/source_document 只搬运
    规则主表字段。这些字段不入库、不参与摘要，写接口的 entries 只接受 rule_id 与 state，
    调用方回传前须去掉。
    """
    entries = item.get("entries")
    if not isinstance(entries, list):
        return dict(item)
    rule_set = _rule_set(rule_set_key)
    executable = executable_rule_ids(rule_set.key)
    metadata = _rule_display_metadata(rule_set.key)
    flagged = []
    for entry in entries:
        display = metadata.get(entry["rule_id"], {})
        flagged.append({
            **entry,
            "executable": entry["rule_id"] in executable,
            "qc_point": display.get("qc_point"),
            "source_document": display.get("source_document"),
            "category": display.get("category"),
            "category_name": display.get("category_name"),
        })
    return {**item, "entries": flagged}


# ---------------------------------------------------------------------------
# entries 规范化与摘要
# ---------------------------------------------------------------------------


def normalize_entries(raw: Any) -> list[dict[str, Any]]:
    """规范化版本条目；旧版本缺少适用配置时保留未配置语义。"""
    if not isinstance(raw, list):
        raise RuleSetVersionInvalid("entries 必须是数组")
    if len(raw) > MAX_ENTRIES:
        raise RuleSetVersionInvalid(f"entries 不能超过 {MAX_ENTRIES} 条")
    normalized: dict[str, dict[str, Any]] = {}
    allowed_keys = {
        "rule_id", "state", "department_scope_mode", "department_refs", "doctor_visible", "core_system_ids",
        "defect_category", "defect_type", "reminder_level",
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
        if not isinstance(rule_id, str) or not rule_id.strip() or len(rule_id.strip()) > MAX_RULE_ID_LENGTH:
            raise RuleSetVersionInvalid("entries 中 rule_id 无效")
        if not isinstance(state, str) or state not in ENTRY_STATES:
            raise RuleSetVersionInvalid("entries 中 state 只能是 active、paused、offline 或 deleted")
        rule_id = rule_id.strip().upper()
        if rule_id in normalized:
            raise RuleSetVersionInvalid(f"entries 中规则重复：{rule_id}")
        normalized_item: dict[str, Any] = {"rule_id": rule_id, "state": state}
        for key in ("defect_category", "defect_type", "reminder_level"):
            if key in item:
                value = item[key]
                if value is not None and (not isinstance(value, str) or not value.strip() or len(value.strip()) > 80):
                    raise RuleSetVersionInvalid("缺陷分类/提醒等级必须为 1 到 80 字符或 null")
                normalized_item[key] = value.strip() if value is not None else None
        if "core_system_ids" in item:
            core_ids = item["core_system_ids"]
            if core_ids is not None and (
                not isinstance(core_ids, list)
                or any(not isinstance(value, str) or value not in CORE_SYSTEM_IDS for value in core_ids)
                or len(core_ids) != len(set(core_ids))
            ):
                raise RuleSetVersionInvalid("entries 中核心制度归属必须为固定制度ID数组或 null")
            normalized_item["core_system_ids"] = None if core_ids is None else sorted(core_ids)
        configured = any(key in item for key in {"department_scope_mode", "department_refs", "doctor_visible"})
        if configured:
            mode = item.get("department_scope_mode")
            refs = item.get("department_refs")
            doctor_visible = item.get("doctor_visible")
            if mode is not None and (not isinstance(mode, str) or mode not in {"all", "selected"}):
                raise RuleSetVersionInvalid("entries 中科室范围模式无效")
            if refs is not None and not isinstance(refs, list):
                raise RuleSetVersionInvalid("entries 中科室范围引用无效")
            normalized_refs: list[dict[str, str]] | None = None
            if isinstance(refs, list):
                seen_refs: set[tuple[str, str]] = set()
                normalized_refs = []
                for ref in refs:
                    if not isinstance(ref, Mapping) or set(ref) != {"institute_id", "department_name"}:
                        raise RuleSetVersionInvalid("entries 中科室范围引用无效")
                    institute_id = _clean(ref.get("institute_id"))
                    department_name = _clean(ref.get("department_name"))
                    if (
                        not institute_id or not department_name
                        or len(institute_id) > MAX_INSTITUTE_ID_LENGTH
                        or len(department_name) > MAX_DEPARTMENT_NAME_LENGTH
                    ):
                        raise RuleSetVersionInvalid("entries 中科室范围引用无效")
                    pair = (institute_id, department_name)
                    if pair not in seen_refs:
                        seen_refs.add(pair)
                        normalized_refs.append({
                            "institute_id": institute_id, "department_name": department_name,
                        })
                normalized_refs.sort(key=lambda ref: (ref["institute_id"], ref["department_name"]))
            if doctor_visible is not None and type(doctor_visible) is not bool:
                raise RuleSetVersionInvalid("entries 中医生端开关无效")
            normalized_item.update({
                "department_scope_mode": mode,
                "department_refs": normalized_refs,
                "doctor_visible": doctor_visible,
            })
        normalized[rule_id] = normalized_item
    return [normalized[rule_id] for rule_id in sorted(normalized)]


def dump_entries(entries: Sequence[Mapping[str, Any]]) -> str:
    """规范化序列化：按 rule_id 排序、键排序、紧凑分隔符、保留中文。"""
    ordered = sorted(
        (dict(item) for item in entries),
        key=lambda item: item["rule_id"],
    )
    return json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_entries_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    """entries 规范化 JSON 的 UTF-8 SHA-256 十六进制摘要。"""
    return hashlib.sha256(dump_entries(entries).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------


def _ordered(rule_set: QCRuleSet, rule_ids: Iterable[str]) -> list[str]:
    """按规则集目录顺序输出（目录外的按 rule_id 排在末尾），与 prepare 的目录顺序一致。"""
    order = {rule_id: index for index, rule_id in enumerate(rule_set.rule_ids)}
    return sorted(set(rule_ids), key=lambda rule_id: (order.get(rule_id, len(order)), rule_id))


def _resolution(
    rule_set: QCRuleSet, *, version: str, source: str, entries: Sequence[Mapping[str, str]],
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


def _resolve_in_session(session: Any, rule_set: QCRuleSet, version: str) -> dict[str, Any]:
    if version == rule_set.version:
        return _builtin_resolution(rule_set)
    if rule_set.key not in VERSIONABLE_RULE_SET_KEYS or not version or version.startswith(DRAFT_VERSION_PREFIX):
        raise RuleSetVersionNotFound("规则集版本不存在")
    row = _published_row(session, rule_set.key, version)
    if row is None:
        raise RuleSetVersionNotFound("规则集版本不存在")
    return _resolution(
        rule_set, version=row.version, source=row.status,
        entries=_stored_entries(row), content_digest=row.content_digest,
    )


def _entries_for_version_in_session(
    session: Any, rule_set: QCRuleSet, version: str,
) -> list[dict[str, Any]]:
    if version == rule_set.version:
        active, paused, excluded = _builtin_partition(rule_set)
        return _entries_from_partition(active, paused, excluded)
    row = _published_row(session, rule_set.key, version)
    if row is None:
        raise RuleSetVersionNotFound("规则集版本不存在")
    return _stored_entries(row)


def _current_in_session(session: Any, rule_set: QCRuleSet) -> str:
    if rule_set.key not in VERSIONABLE_RULE_SET_KEYS:
        return rule_set.version
    row = session.execute(
        select(_TABLE.c.version)
        .where(_TABLE.c.rule_set_key == rule_set.key, _TABLE.c.status == STATUS_PUBLISHED)
        .order_by(_TABLE.c.published_at.desc(), _TABLE.c.created_at.desc(), _TABLE.c.id.desc())
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
    return frozenset({rule_set.version, *(_clean(row.version) for row in rows if _clean(row.version))})


# ---------------------------------------------------------------------------
# 发布校验
# ---------------------------------------------------------------------------


def _all_rule_ids(resolution: Mapping[str, Any]) -> set[str]:
    return {
        *resolution["active_rule_ids"], *resolution["paused_rule_ids"], *resolution["excluded_rule_ids"],
    }


def _entries_from_resolution(resolution: Mapping[str, Any]) -> list[dict[str, str]]:
    """精确恢复四态；deleted 不能经 excluded 投影退化为 offline。"""
    deleted = set(resolution.get("deleted_rule_ids") or ())
    offline = resolution.get("offline_rule_ids")
    if offline is None:
        offline = [
            rule_id for rule_id in resolution["excluded_rule_ids"]
            if rule_id not in deleted
        ]
    return _entries_from_partition(
        resolution["active_rule_ids"],
        resolution["paused_rule_ids"],
        offline,
        deleted,
    )


def _deleted_transition_problems(
    current: Mapping[str, Any], entries: Sequence[Mapping[str, str]],
) -> list[str]:
    """墓碑不可复活；当前启用项必须先发布暂停/下线版本才能删除。"""
    current_by_id = {
        item["rule_id"]: item["state"] for item in _entries_from_resolution(current)
    }
    requested = {item["rule_id"]: item["state"] for item in entries}
    problems: list[str] = []
    revived = sorted(
        rule_id for rule_id, state in current_by_id.items()
        if state == STATE_DELETED and requested.get(rule_id) != STATE_DELETED
    )
    if revived:
        problems.append(f"已删除规则不能恢复或遗漏：{','.join(revived)}")
    active_deleted = sorted(
        rule_id for rule_id, state in requested.items()
        if state == STATE_DELETED and current_by_id.get(rule_id) == STATE_ACTIVE
    )
    if active_deleted:
        problems.append(
            f"启用中的规则不能直接删除，请先发布暂停或下线版本：{','.join(active_deleted)}"
        )
    return problems


def _require_deleted_transitions(
    current: Mapping[str, Any], entries: Sequence[Mapping[str, str]],
) -> None:
    problems = _deleted_transition_problems(current, entries)
    if problems:
        raise RuleSetVersionInvalid(
            "规则删除状态不符合要求", code="delete_validation_failed", problems=problems,
        )


def validate_publish_entries(
    rule_set: QCRuleSet, base: Mapping[str, Any], entries: Sequence[Mapping[str, Any]],
    *, current: Mapping[str, Any] | None = None, require_applicability: bool = True,
) -> None:
    """发布校验（合同第 4 节）；不通过抛 RuleSetVersionInvalid，problems 逐条列出原因。"""
    rule_ids = {item["rule_id"] for item in entries}
    catalog = set(rule_set.rule_ids)
    problems: list[str] = []
    unknown = sorted(rule_ids - catalog)
    if unknown:
        problems.append(f"不能引入规则主表之外的规则：{','.join(unknown)}")
    missing_base = sorted(_all_rule_ids(base) - rule_ids)
    if missing_base:
        problems.append(f"未覆盖基础版本的规则：{','.join(missing_base)}")
    missing_catalog = sorted(catalog - rule_ids - set(missing_base))
    if missing_catalog:
        problems.append(f"遗漏规则主表已有规则：{','.join(missing_catalog)}")
    executable = executable_rule_ids(rule_set.key)
    not_executable = sorted(
        item["rule_id"] for item in entries
        if item["state"] == STATE_ACTIVE and item["rule_id"] not in executable
    )
    if not_executable:
        problems.append(f"以下规则当前不可执行，只能设为 paused 或 offline：{','.join(not_executable)}")
    if not any(item["state"] == STATE_ACTIVE for item in entries):
        problems.append("至少需要 1 条 active 规则")
    unconfigured = sorted(
        item["rule_id"] for item in entries
        if item["state"] != STATE_DELETED and (
            item.get("department_scope_mode") not in {"all", "selected"}
            or item.get("doctor_visible") is None
            or not isinstance(item.get("department_refs"), list)
        )
    )
    invalid_scope = sorted(
        item["rule_id"] for item in entries
        if item["state"] != STATE_DELETED and (
            (item.get("department_scope_mode") == "selected" and not item.get("department_refs"))
            or (item.get("department_scope_mode") == "all" and item.get("department_refs"))
        )
    )
    if require_applicability and unconfigured:
        problems.append(f"以下规则尚未配置科室范围或医生端开关：{','.join(unconfigured)}")
    if invalid_scope:
        problems.append(f"以下规则科室范围配置无效：{','.join(invalid_scope)}")
    if current is not None:
        problems.extend(_deleted_transition_problems(current, entries))
    if problems:
        raise RuleSetVersionInvalid(
            "规则集版本发布校验未通过", code="publish_validation_failed", problems=problems,
        )


def validate_department_refs(
    entries: Sequence[Mapping[str, Any]], *, session: Any,
) -> None:
    """指定科室必须来自病例权威院科选项，不接受任意客户端字符串。"""

    requested = {
        (ref["institute_id"], ref["department_name"])
        for item in entries if item.get("department_scope_mode") == "selected"
        for ref in item.get("department_refs") or []
    }
    if not requested:
        return
    try:
        from .medical_records.query_service import list_scoring_department_options

        options = list_scoring_department_options(session=session)
    except Exception as exc:  # noqa: BLE001 - 权威选项不可用时禁止发布
        raise RuleSetVersionUnavailable("院科范围选项暂不可用") from exc
    authoritative = {
        (_clean(item.get("institute_id")), _clean(item.get("department_name")))
        for item in options if isinstance(item, Mapping)
    }
    unknown = sorted(requested - authoritative)
    if unknown:
        raise RuleSetVersionInvalid(
            "规则集版本发布校验未通过",
            code="publish_validation_failed",
            problems=[
                "以下院科组合不存在：" + ",".join(
                    f"{institute_id}|{department_name}"
                    for institute_id, department_name in unknown
                )
            ],
        )


# ---------------------------------------------------------------------------
# 参数校验与事务辅助
# ---------------------------------------------------------------------------


def _actor(actor: Any) -> str:
    if not isinstance(actor, str) or not actor.strip() or len(actor) > MAX_ACTOR_LENGTH:
        raise RuleSetVersionInvalid("当前用户缺少有效身份")
    return actor


def _note(note: Any) -> str | None:
    if note is None:
        return None
    if not isinstance(note, str):
        raise RuleSetVersionInvalid("note 必须是字符串")
    note = note.strip()
    if len(note) > MAX_NOTE_LENGTH:
        raise RuleSetVersionInvalid(f"note 不能超过 {MAX_NOTE_LENGTH} 个字符")
    return note


def _version_seq(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise RuleSetVersionInvalid("version_seq 无效")
    return value


def _publish_version(value: Any) -> str:
    if not isinstance(value, str) or not _VERSION_PATTERN.fullmatch(value.strip()):
        raise RuleSetVersionInvalid(
            "版本号只能包含字母、数字、点、下划线和连字符，且以字母或数字开头，最长 64 个字符"
        )
    return value.strip()


def _lock_rule_set(session: Any, rule_set_key: str) -> None:
    """同一规则集的写入串行化（草稿唯一、当前版本判断、发布/下线）。SQLite 单测跳过。"""
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"qc_rule_set_versions:{rule_set_key}"},
    )


def _draft_row(session: Any, rule_set_key: str, *, for_update: bool = False) -> Any:
    statement = select(*_ROW_COLUMNS).where(
        _TABLE.c.rule_set_key == rule_set_key, _TABLE.c.status == STATUS_DRAFT,
    )
    if for_update:
        statement = statement.with_for_update()
    return session.execute(statement).first()


def _draft_export_version(row: Any) -> str:
    """Excel 使用的不可复用草稿身份；从持久化 row.version 派生，防删除重建 ABA。"""
    stored = _clean(row.version)
    suffix = stored[len(DRAFT_VERSION_PREFIX):] if stored.startswith(DRAFT_VERSION_PREFIX) else stored
    return f"draft:{suffix}"


def _counts(entries: Sequence[Mapping[str, str]]) -> dict[str, int]:
    return {
        f"{state}_count": sum(item["state"] == state for item in entries) for state in ENTRY_STATES
    }


def _row_item(row: Any, *, current: str, with_entries: bool) -> dict[str, Any]:
    entries = _stored_entries(row)
    item: dict[str, Any] = {
        "id": row.id,
        "rule_set_key": row.rule_set_key,
        "version": None if row.status == STATUS_DRAFT else row.version,
        "status": row.status,
        "source": None if row.status == STATUS_DRAFT else row.status,
        "base_version": row.base_version,
        "content_digest": row.content_digest,
        "note": row.note,
        "version_seq": int(row.version_seq),
        "created_by": row.created_by,
        "created_at": row.created_at,
        "published_by": row.published_by,
        "published_at": row.published_at,
        "retired_by": row.retired_by,
        "retired_at": row.retired_at,
        "is_current": row.status == STATUS_PUBLISHED and row.version == current,
        **_counts(entries),
    }
    if with_entries:
        item["entries"] = entries
    return item


def _builtin_item(rule_set: QCRuleSet, *, current: str, with_entries: bool) -> dict[str, Any]:
    resolution = _builtin_resolution(rule_set)
    entries = _entries_from_partition(
        resolution["active_rule_ids"], resolution["paused_rule_ids"], resolution["excluded_rule_ids"],
    )
    item: dict[str, Any] = {
        "id": None,
        "rule_set_key": rule_set.key,
        "version": rule_set.version,
        "status": SOURCE_BUILTIN,
        "source": SOURCE_BUILTIN,
        "base_version": None,
        "content_digest": resolution["content_digest"],
        "note": rule_set.description or None,
        "version_seq": None,
        "created_by": None,
        "created_at": None,
        "published_by": None,
        "published_at": None,
        "retired_by": None,
        "retired_at": None,
        "is_current": rule_set.version == current,
        **_counts(entries),
    }
    if with_entries:
        item["entries"] = entries
    return item


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------


def list_versions(rule_set_key: Any) -> dict[str, Any]:
    """版本列表：内置版本 + 已发布/已下线版本（发布时间倒序），并标明当前版本与草稿。"""
    rule_set = _rule_set(rule_set_key)
    versionable = rule_set.key in VERSIONABLE_RULE_SET_KEYS
    rows: list[Any] = []
    draft = None
    current = rule_set.version
    if versionable:
        factory = _require_session_factory()
        try:
            with factory() as session:
                current = _current_in_session(session, rule_set)
                rows = session.execute(
                    select(*_ROW_COLUMNS)
                    .where(_TABLE.c.rule_set_key == rule_set.key)
                    .order_by(_TABLE.c.published_at.desc(), _TABLE.c.created_at.desc(), _TABLE.c.id.desc())
                ).all()
        except SQLAlchemyError as exc:
            raise RuleSetVersionUnavailable("规则集版本读取失败") from exc
    items = []
    for row in rows:
        if row.status == STATUS_DRAFT:
            draft = _row_item(row, current=current, with_entries=True)
        else:
            items.append(_row_item(row, current=current, with_entries=False))
    items.append(_builtin_item(rule_set, current=current, with_entries=False))
    return {
        "rule_set_key": rule_set.key,
        "versionable": versionable,
        "builtin_version": rule_set.version,
        "current_version": current,
        "items": items,
        "draft": draft,
    }


def get_version_detail(rule_set_key: Any, version: Any) -> dict[str, Any]:
    """版本详情：解析结果 + entries + 元数据。"""
    rule_set = _rule_set(rule_set_key)
    version = _clean(version)
    if rule_set.key not in VERSIONABLE_RULE_SET_KEYS:
        if version != rule_set.version:
            raise RuleSetVersionNotFound("规则集版本不存在")
        item = _builtin_item(rule_set, current=rule_set.version, with_entries=True)
        return {**item, "resolution": _builtin_resolution(rule_set)}
    factory = _require_session_factory()
    try:
        with factory() as session:
            current = _current_in_session(session, rule_set)
            resolution = _resolve_in_session(session, rule_set, version)
            if resolution["source"] == SOURCE_BUILTIN:
                item = _builtin_item(rule_set, current=current, with_entries=True)
            else:
                item = _row_item(
                    _published_row(session, rule_set.key, version), current=current, with_entries=True,
                )
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集版本读取失败") from exc
    return {**item, "resolution": resolution}


def get_draft(rule_set_key: Any) -> dict[str, Any]:
    rule_set = _versionable_rule_set(rule_set_key)
    factory = _require_session_factory()
    try:
        with factory() as session:
            current = _current_in_session(session, rule_set)
            row = _draft_row(session, rule_set.key)
            if row is None:
                raise RuleSetVersionNotFound("草稿不存在")
            return _row_item(row, current=current, with_entries=True)
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集草稿读取失败") from exc


def get_draft_export_snapshot(rule_set_key: Any) -> dict[str, Any]:
    """在同一会话读取草稿及其冻结基础摘要，供 Excel 导出。"""
    rule_set = _versionable_rule_set(rule_set_key)
    factory = _require_session_factory()
    try:
        with factory() as session:
            current = _current_in_session(session, rule_set)
            row = _draft_row(session, rule_set.key)
            if row is None:
                raise RuleSetVersionNotFound("草稿不存在")
            try:
                base = _resolve_in_session(session, rule_set, row.base_version)
            except RuleSetVersionNotFound as exc:
                raise RuleSetVersionUnavailable("草稿的基础版本不可解析") from exc
            snapshot = _row_item(row, current=current, with_entries=True)
            snapshot["draft_version"] = _draft_export_version(row)
            return {
                "snapshot": snapshot,
                "base_version": base["version"],
                "base_content_digest": base["content_digest"],
            }
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集草稿读取失败") from exc


# ---------------------------------------------------------------------------
# 草稿与发布
# ---------------------------------------------------------------------------


def create_draft(
    rule_set_key: Any, *, actor: str, base_version: Any = None, entries: Any = None, note: Any = None,
) -> dict[str, Any]:
    """从基础版本（默认当前版本）创建草稿；entries 缺省时复制基础版本内容。已有草稿 409 draft_exists。"""
    rule_set = _versionable_rule_set(rule_set_key)
    actor = _actor(actor)
    note = _note(note)
    normalized_entries = None if entries is None else normalize_entries(entries)
    if base_version is not None and not isinstance(base_version, str):
        raise RuleSetVersionInvalid("base_version 无效")
    factory = _require_session_factory()
    draft_id = str(uuid4())
    try:
        with factory() as session:
            with session.begin():
                _lock_rule_set(session, rule_set.key)
                current = _current_in_session(session, rule_set)
                base_name = _clean(base_version) or current
                try:
                    base = _resolve_in_session(session, rule_set, base_name)
                except RuleSetVersionNotFound:
                    raise RuleSetVersionInvalid("基础版本不存在") from None
                if _draft_row(session, rule_set.key) is not None:
                    raise RuleSetVersionConflict("该规则集已有草稿", code="draft_exists")
                if normalized_entries is None:
                    normalized_entries = _entries_for_version_in_session(
                        session, rule_set, base["version"],
                    )
                    current_resolution = _resolve_in_session(session, rule_set, current)
                    current_deleted = set(current_resolution.get("deleted_rule_ids") or ())
                    normalized_entries = [
                        {
                            **item,
                            "state": STATE_DELETED if item["rule_id"] in current_deleted else item["state"],
                        }
                        for item in normalized_entries
                    ]
                else:
                    current_resolution = _resolve_in_session(session, rule_set, current)
                _require_deleted_transitions(current_resolution, normalized_entries)
                session.execute(insert(_TABLE).values(
                    id=draft_id, rule_set_key=rule_set.key,
                    version=f"{DRAFT_VERSION_PREFIX}{draft_id}", status=STATUS_DRAFT,
                    base_version=base["version"], entries_json=dump_entries(normalized_entries),
                    content_digest=None, note=note, version_seq=1,
                    created_by=actor, created_at=_now(),
                ))
            row = _draft_row(session, rule_set.key)
            return _row_item(row, current=current, with_entries=True)
    except IntegrityError as exc:
        # 已在锁内预检；此处仅兜底并发下的草稿部分唯一索引冲突。
        raise RuleSetVersionConflict("该规则集已有草稿", code="draft_exists") from exc
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集草稿保存失败") from exc


def update_draft(
    rule_set_key: Any, *, actor: str, version_seq: Any, entries: Any = None, note: Any = None,
) -> dict[str, Any]:
    """按 version_seq 做 CAS 修改草稿；None 字段保持不变。"""
    rule_set = _versionable_rule_set(rule_set_key)
    _actor(actor)
    version_seq = _version_seq(version_seq)
    changes: dict[str, Any] = {}
    if entries is not None:
        changes["entries_json"] = dump_entries(normalize_entries(entries))
    if note is not None:
        changes["note"] = _note(note)
    if not changes:
        raise RuleSetVersionInvalid("没有需要更新的字段")
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                _lock_rule_set(session, rule_set.key)
                row = _draft_row(session, rule_set.key, for_update=True)
                if row is None:
                    raise RuleSetVersionNotFound("草稿不存在")
                if int(row.version_seq) != version_seq:
                    raise RuleSetVersionConflict("草稿已被修改，请刷新后重试", code="version_conflict")
                current = _current_in_session(session, rule_set)
                if entries is not None:
                    _require_deleted_transitions(
                        _resolve_in_session(session, rule_set, current),
                        normalize_entries(entries),
                    )
                updated = session.execute(
                    update(_TABLE)
                    .where(
                        _TABLE.c.id == row.id, _TABLE.c.status == STATUS_DRAFT,
                        _TABLE.c.version_seq == version_seq,
                    )
                    .values(**changes, version_seq=version_seq + 1)
                )
                if updated.rowcount != 1:
                    raise RuleSetVersionConflict("草稿已被修改，请刷新后重试", code="version_conflict")
            row = _draft_row(session, rule_set.key)
            return _row_item(row, current=current, with_entries=True)
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集草稿保存失败") from exc


def preflight_draft_import_snapshot(
    rule_set_key: Any, *, base_version: Any, base_content_digest: Any, entries: Any,
) -> dict[str, Any]:
    """导入写事务前的完整生命周期预检；事务方法会再次执行同样的关键校验。"""
    rule_set = _versionable_rule_set(rule_set_key)
    base_version = _clean(base_version)
    digest = _clean(base_content_digest).lower()
    if not base_version:
        raise RuleSetVersionInvalid("基础版本不能为空", code="base_version_required")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuleSetVersionInvalid("基础内容摘要无效", code="base_digest_invalid")
    normalized_entries = normalize_entries(entries)
    factory = _require_session_factory()
    try:
        with factory() as session:
            try:
                base = _resolve_in_session(session, rule_set, base_version)
            except RuleSetVersionNotFound:
                raise RuleSetVersionInvalid(
                    "基础版本不存在，请重新导出", code="base_version_not_found",
                ) from None
            if base["content_digest"] != digest:
                raise RuleSetVersionInvalid(
                    "基础版本内容摘要已变化，请重新导出", code="base_digest_mismatch",
                )
            current_name = _current_in_session(session, rule_set)
            current = _resolve_in_session(session, rule_set, current_name)
            validate_publish_entries(
                rule_set, base, normalized_entries, current=current,
                require_applicability=False,
            )
            validate_department_refs(normalized_entries, session=session)
            return {
                "base": base,
                "entries": normalized_entries,
                "catalog_entries": _entries_from_resolution(base),
            }
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集版本导入预检失败") from exc


def import_draft_snapshot(
    rule_set_key: Any,
    *,
    actor: str,
    base_version: Any,
    base_content_digest: Any,
    entries: Any,
    expected_draft_version: Any = None,
    expected_draft_version_seq: Any = None,
) -> dict[str, Any]:
    """把已完成文件预检的快照原子导入草稿。

    冻结基础摘要与用户编辑后的 entries 分开校验。无草稿时只能由冻结版本文件创建；
    有草稿时必须携带同一草稿导出的 version_seq，并在事务内做 CAS。事务提交前回读，
    回读失败会回滚写入。
    """
    rule_set = _versionable_rule_set(rule_set_key)
    actor = _actor(actor)
    base_version = _clean(base_version)
    if not base_version:
        raise RuleSetVersionInvalid("基础版本不能为空", code="base_version_required")
    digest = _clean(base_content_digest).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuleSetVersionInvalid("基础内容摘要无效", code="base_digest_invalid")
    normalized_entries = normalize_entries(entries)
    expected_version = _clean(expected_draft_version) or None
    if expected_version is not None and not expected_version.startswith("draft:"):
        raise RuleSetVersionInvalid("草稿导出身份无效", code="draft_version_invalid")
    expected_seq = None if expected_draft_version_seq is None else _version_seq(expected_draft_version_seq)
    if (expected_version is None) != (expected_seq is None):
        raise RuleSetVersionInvalid("草稿身份与版本序号必须同时提供", code="draft_identity_incomplete")
    factory = _require_session_factory()
    draft_id = str(uuid4())
    try:
        with factory() as session:
            with session.begin():
                _lock_rule_set(session, rule_set.key)
                try:
                    base = _resolve_in_session(session, rule_set, base_version)
                except RuleSetVersionNotFound:
                    raise RuleSetVersionInvalid(
                        "基础版本不存在，请重新导出", code="base_version_not_found",
                    ) from None
                if base["content_digest"] != digest:
                    raise RuleSetVersionInvalid(
                        "基础版本内容摘要已变化，请重新导出", code="base_digest_mismatch",
                    )
                # 生命周期规则只在这里判定，Excel 解析器不另造 owner。
                current_name = _current_in_session(session, rule_set)
                current_resolution = _resolve_in_session(session, rule_set, current_name)
                validate_publish_entries(
                    rule_set, base, normalized_entries, current=current_resolution,
                    require_applicability=False,
                )
                validate_department_refs(normalized_entries, session=session)
                row = _draft_row(session, rule_set.key, for_update=True)
                if row is None:
                    if expected_version is not None:
                        raise RuleSetVersionConflict(
                            "导出的草稿已不存在，请刷新后重新导出", code="draft_changed",
                        )
                    session.execute(insert(_TABLE).values(
                        id=draft_id,
                        rule_set_key=rule_set.key,
                        version=f"{DRAFT_VERSION_PREFIX}{draft_id}",
                        status=STATUS_DRAFT,
                        base_version=base["version"],
                        entries_json=dump_entries(normalized_entries),
                        content_digest=None,
                        note=None,
                        version_seq=1,
                        created_by=actor,
                        created_at=_now(),
                    ))
                else:
                    if expected_version is None:
                        raise RuleSetVersionConflict(
                            "该规则集已有草稿，请导出当前草稿后再修改导入", code="draft_exists",
                        )
                    if _draft_export_version(row) != expected_version:
                        raise RuleSetVersionConflict(
                            "导出的草稿已被替换，请刷新后重新导出", code="draft_changed",
                        )
                    if row.base_version != base["version"]:
                        raise RuleSetVersionConflict(
                            "草稿基础版本已变化，请刷新后重新导出", code="draft_changed",
                        )
                    if int(row.version_seq) != expected_seq:
                        raise RuleSetVersionConflict(
                            "草稿已被修改，请刷新后重新导出", code="version_conflict",
                        )
                    updated = session.execute(
                        update(_TABLE)
                        .where(
                            _TABLE.c.id == row.id,
                            _TABLE.c.status == STATUS_DRAFT,
                            _TABLE.c.version_seq == expected_seq,
                            _TABLE.c.base_version == base["version"],
                        )
                        .values(entries_json=dump_entries(normalized_entries), version_seq=expected_seq + 1)
                    )
                    if updated.rowcount != 1:
                        raise RuleSetVersionConflict(
                            "草稿已被修改，请刷新后重新导出", code="version_conflict",
                        )
                # 必须在事务内回读；这里失败时 session.begin 会回滚。
                current = _current_in_session(session, rule_set)
                imported = _draft_row(session, rule_set.key)
                if imported is None:
                    raise RuleSetVersionUnavailable("规则集草稿回读失败")
                return _row_item(imported, current=current, with_entries=True)
    except IntegrityError as exc:
        raise RuleSetVersionConflict("该规则集已有草稿", code="draft_exists") from exc
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集草稿导入失败") from exc


def delete_draft(rule_set_key: Any, *, actor: str, version_seq: Any) -> dict[str, Any]:
    rule_set = _versionable_rule_set(rule_set_key)
    _actor(actor)
    version_seq = _version_seq(version_seq)
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                _lock_rule_set(session, rule_set.key)
                row = _draft_row(session, rule_set.key, for_update=True)
                if row is None:
                    raise RuleSetVersionNotFound("草稿不存在")
                if int(row.version_seq) != version_seq:
                    raise RuleSetVersionConflict("草稿已被修改，请刷新后重试", code="version_conflict")
                deleted = session.execute(
                    delete(_TABLE).where(
                        _TABLE.c.id == row.id, _TABLE.c.status == STATUS_DRAFT,
                        _TABLE.c.version_seq == version_seq,
                    )
                )
                if deleted.rowcount != 1:
                    raise RuleSetVersionConflict("草稿已被修改，请刷新后重试", code="version_conflict")
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集草稿删除失败") from exc
    return {"rule_set_key": rule_set.key, "deleted": True}


def publish_draft(
    rule_set_key: Any, *, actor: str, version: Any, note: Any = None, version_seq: Any = None,
) -> dict[str, Any]:
    """草稿 → published：同一事务内完成发布校验、摘要计算与条件更新。

    version_seq 可选；传入时做 CAS，避免发布他人刚改过的草稿。版本号不得与内置版本或已有版本重复。
    """
    rule_set = _versionable_rule_set(rule_set_key)
    actor = _actor(actor)
    version = _publish_version(version)
    note = _note(note)
    expected_seq = None if version_seq is None else _version_seq(version_seq)
    if version.startswith(DRAFT_VERSION_PREFIX):
        raise RuleSetVersionInvalid("版本号不能使用草稿保留前缀")
    if version == rule_set.version:
        raise RuleSetVersionConflict("版本号与内置版本重复", code="version_exists")
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                _lock_rule_set(session, rule_set.key)
                row = _draft_row(session, rule_set.key, for_update=True)
                if row is None:
                    raise RuleSetVersionNotFound("草稿不存在")
                seq = int(row.version_seq)
                if expected_seq is not None and seq != expected_seq:
                    raise RuleSetVersionConflict("草稿已被修改，请刷新后重试", code="version_conflict")
                exists = session.execute(
                    select(_TABLE.c.id).where(
                        _TABLE.c.rule_set_key == rule_set.key, _TABLE.c.version == version,
                    ).limit(1)
                ).first()
                if exists is not None:
                    raise RuleSetVersionConflict("版本号已存在", code="version_exists")
                entries = _stored_entries(row)
                try:
                    base = _resolve_in_session(session, rule_set, row.base_version)
                except RuleSetVersionNotFound as exc:
                    # 基础版本只能下线不能删除；解析不到视为数据异常而非用户错误，失败关闭。
                    raise RuleSetVersionUnavailable("草稿的基础版本不可解析") from exc
                current_name = _current_in_session(session, rule_set)
                current_resolution = _resolve_in_session(session, rule_set, current_name)
                validate_publish_entries(rule_set, base, entries, current=current_resolution)
                validate_department_refs(entries, session=session)
                now = _now()
                updated = session.execute(
                    update(_TABLE)
                    .where(
                        _TABLE.c.id == row.id, _TABLE.c.status == STATUS_DRAFT,
                        _TABLE.c.version_seq == seq,
                    )
                    .values(
                        status=STATUS_PUBLISHED, version=version,
                        entries_json=dump_entries(entries),
                        content_digest=compute_entries_digest(entries),
                        note=row.note if note is None else note,
                        published_by=actor, published_at=now, version_seq=seq + 1,
                    )
                )
                if updated.rowcount != 1:
                    raise RuleSetVersionConflict("草稿已被修改，请刷新后重试", code="version_conflict")
                current = _current_in_session(session, rule_set)
            published = _published_row(session, rule_set.key, version)
            return _row_item(published, current=current, with_entries=True)
    except IntegrityError as exc:
        raise RuleSetVersionConflict("版本号已存在", code="version_exists") from exc
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集版本发布失败") from exc


def retire_version(rule_set_key: Any, version: Any, *, actor: str) -> dict[str, Any]:
    """published → retired；不能下线内置版本，也不能下线当前版本。"""
    rule_set = _versionable_rule_set(rule_set_key)
    actor = _actor(actor)
    version = _clean(version)
    if version == rule_set.version:
        raise RuleSetVersionConflict("内置版本不能下线", code="builtin_version")
    if not version or version.startswith(DRAFT_VERSION_PREFIX):
        raise RuleSetVersionNotFound("规则集版本不存在")
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                _lock_rule_set(session, rule_set.key)
                row = session.execute(
                    select(_TABLE.c.id, _TABLE.c.status).where(
                        _TABLE.c.rule_set_key == rule_set.key, _TABLE.c.version == version,
                        _TABLE.c.status.in_((STATUS_PUBLISHED, STATUS_RETIRED)),
                    ).with_for_update()
                ).first()
                if row is None:
                    raise RuleSetVersionNotFound("规则集版本不存在")
                if row.status == STATUS_RETIRED:
                    raise RuleSetVersionConflict("该版本已下线", code="already_retired")
                current = _current_in_session(session, rule_set)
                if version == current:
                    raise RuleSetVersionConflict("当前版本不能下线", code="current_version")
                updated = session.execute(
                    update(_TABLE)
                    .where(_TABLE.c.id == row.id, _TABLE.c.status == STATUS_PUBLISHED)
                    .values(
                        status=STATUS_RETIRED, retired_by=actor, retired_at=_now(),
                        version_seq=_TABLE.c.version_seq + 1,
                    )
                )
                if updated.rowcount != 1:
                    raise RuleSetVersionConflict("版本状态已变化，请刷新后重试", code="version_conflict")
            retired = _published_row(session, rule_set.key, version)
            return _row_item(retired, current=current, with_entries=True)
    except SQLAlchemyError as exc:
        raise RuleSetVersionUnavailable("规则集版本下线失败") from exc


__all__ = [
    "ENTRY_STATES",
    "VERSIONABLE_RULE_SET_KEYS",
    "RuleSetVersionConflict",
    "RuleSetVersionInvalid",
    "RuleSetVersionNotFound",
    "RuleSetVersionUnavailable",
    "compute_entries_digest",
    "create_draft",
    "current_version",
    "delete_draft",
    "dump_entries",
    "executable_rule_ids",
    "get_draft",
    "get_version_detail",
    "list_versions",
    "normalize_entries",
    "publish_draft",
    "resolve_rule_set_version",
    "retire_version",
    "update_draft",
    "validate_publish_entries",
    "with_executable_flags",
]
