"""用户个人筛选模板服务（V3.6 P1-A 合同第 2–3 节）。

- 模板只属于 owner_id 本人：所有读写都带 owner_id 谓词，他人模板一律视为不存在；
- page_key 与 filters 键均为白名单，逐键校验类型与取值；不保存页码与分页大小；
- 每人每页最多 MAX_TEMPLATES_PER_PAGE 个：写事务内先取 (owner_id, page_key) 事务级锁再计数；
- 设为默认时在同一事务内取消该页原默认（被取消的行 version 同步 +1）；
- 更新/删除以 version 做 CAS；数据库故障统一抛 FilterTemplateUnavailable，对外脱敏。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCUserFilterTemplate

PAGE_KEYS = frozenset({
    "v5_records_inpatient",
    "v5_records_discharged",
    "v5_records_outpatient_emergency",
})
MAX_TEMPLATES_PER_PAGE = 20
MAX_NAME_LENGTH = 50
MAX_OWNER_ID_LENGTH = 64
MAX_TEXT_FILTER_LENGTH = 100

REVIEW_STATES = ("pending_review", "pending_recheck", "approved", "doubtful")
_TEXT_FILTER_KEYS = ("dept", "doctor", "keyword")
_DATE_FILTER_KEYS = ("start_date", "end_date")
_ENUM_FILTERS = {
    "date_field": frozenset({"visit", "admission", "discharge", "updated"}),
    "inpatient_sort": frozenset({"default", "longest", "recent"}),
}
FILTER_KEYS = frozenset({*_TEXT_FILTER_KEYS, *_DATE_FILTER_KEYS, *_ENUM_FILTERS, "review_state"})
OUTPATIENT_PAGE_KEY = "v5_records_outpatient_emergency"
OUTPATIENT_FILTER_KEYS = frozenset({"dept", "keyword", "start_date", "end_date", "date_field"})

_TABLE = QCUserFilterTemplate.__table__


class FilterTemplateNotFound(LookupError):
    """模板不存在或不属于当前用户。"""


class FilterTemplateInvalid(ValueError):
    """请求参数不符合合同。"""


class FilterTemplateConflict(ValueError):
    """重名、超出上限或版本冲突。"""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class FilterTemplateUnavailable(RuntimeError):
    """数据库不可用或读写失败；对外只给脱敏提示。"""


def _require_session_factory() -> Any:
    if SessionLocal is None:
        raise FilterTemplateUnavailable("数据库会话不可用")
    return SessionLocal


def _now() -> datetime:
    # 与其他 qc 表一致：库内存无时区 UTC。
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# 参数校验
# ---------------------------------------------------------------------------


def _owner(owner_id: Any) -> str:
    if (
        not isinstance(owner_id, str) or not owner_id.strip()
        or len(owner_id) > MAX_OWNER_ID_LENGTH
    ):
        raise FilterTemplateInvalid("当前用户缺少有效身份")
    return owner_id


def _page_key(page_key: Any) -> str:
    if not isinstance(page_key, str) or page_key not in PAGE_KEYS:
        raise FilterTemplateInvalid("page_key 无效")
    return page_key


def _name(name: Any) -> str:
    if not isinstance(name, str):
        raise FilterTemplateInvalid("模板名称无效")
    normalized = name.strip()
    if not normalized:
        raise FilterTemplateInvalid("模板名称不能为空")
    if len(normalized) > MAX_NAME_LENGTH:
        raise FilterTemplateInvalid(f"模板名称不能超过 {MAX_NAME_LENGTH} 个字符")
    return normalized


def _version(version: Any) -> int:
    if type(version) is not int or version < 1:
        raise FilterTemplateInvalid("version 无效")
    return version


def _iso_date(key: str, value: Any) -> str:
    if not isinstance(value, str) or len(value) != 10:
        raise FilterTemplateInvalid(f"筛选项 {key} 必须是 YYYY-MM-DD 日期")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise FilterTemplateInvalid(f"筛选项 {key} 必须是 YYYY-MM-DD 日期") from None


def validate_filters(filters: Any, *, page_key: str | None = None) -> dict[str, Any]:
    """逐键校验筛选条件；未知键或非法值抛 FilterTemplateInvalid。

    None 与空字符串/空数组视为“未设置”，不写入模板；返回规范化后的新字典。
    """
    if not isinstance(filters, dict):
        raise FilterTemplateInvalid("filters 必须是对象")
    unknown = sorted(str(key) for key in filters if key not in FILTER_KEYS)
    if unknown:
        raise FilterTemplateInvalid(f"filters 含不支持的键：{', '.join(unknown)}")
    if page_key == OUTPATIENT_PAGE_KEY:
        unsupported = sorted(str(key) for key in filters if key not in OUTPATIENT_FILTER_KEYS)
        if unsupported:
            raise FilterTemplateInvalid(f"门急诊筛选模板含不支持的键：{', '.join(unsupported)}")
        if filters.get("date_field") != "visit":
            raise FilterTemplateInvalid("门急诊筛选模板 date_field 必须为 visit")
    normalized: dict[str, Any] = {}
    for key, value in filters.items():
        if value is None:
            continue
        if key in _TEXT_FILTER_KEYS:
            if not isinstance(value, str):
                raise FilterTemplateInvalid(f"筛选项 {key} 必须是字符串")
            value = value.strip()
            if len(value) > MAX_TEXT_FILTER_LENGTH:
                raise FilterTemplateInvalid(f"筛选项 {key} 不能超过 {MAX_TEXT_FILTER_LENGTH} 个字符")
            if value:
                normalized[key] = value
        elif key in _DATE_FILTER_KEYS:
            if value == "":
                continue
            normalized[key] = _iso_date(key, value)
        elif key in _ENUM_FILTERS:
            if not isinstance(value, str) or value not in _ENUM_FILTERS[key]:
                raise FilterTemplateInvalid(f"筛选项 {key} 取值无效")
            normalized[key] = value
        else:  # review_state
            if not isinstance(value, list) or any(
                not isinstance(item, str) or item not in REVIEW_STATES for item in value
            ):
                raise FilterTemplateInvalid("筛选项 review_state 取值无效")
            if value:
                normalized[key] = list(dict.fromkeys(value))
    if (
        "start_date" in normalized and "end_date" in normalized
        and normalized["start_date"] > normalized["end_date"]
    ):
        raise FilterTemplateInvalid("开始日期不能晚于结束日期")
    if page_key == OUTPATIENT_PAGE_KEY and (
        ("start_date" in normalized) != ("end_date" in normalized)
    ):
        raise FilterTemplateInvalid("门急诊筛选模板开始日期与结束日期必须同时设置")
    return normalized


def _dump_filters(filters: dict[str, Any]) -> str:
    return json.dumps(filters, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_filters(raw: Any, *, page_key: str) -> dict[str, Any] | None:
    """读出时再按白名单校验；损坏或越界的存量内容返回 None（前端显示为不可用），不伪造空筛选。"""
    try:
        return validate_filters(json.loads(raw), page_key=page_key)
    except (TypeError, ValueError):
        return None


def _item(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "page_key": row.page_key,
        "name": row.name,
        "filters": _load_filters(row.filters_json, page_key=row.page_key),
        "is_default": bool(row.is_default),
        "version": int(row.version),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


_COLUMNS = (
    QCUserFilterTemplate.id, QCUserFilterTemplate.page_key, QCUserFilterTemplate.name,
    QCUserFilterTemplate.filters_json, QCUserFilterTemplate.is_default,
    QCUserFilterTemplate.version, QCUserFilterTemplate.created_at,
    QCUserFilterTemplate.updated_at,
)


# ---------------------------------------------------------------------------
# 事务内辅助
# ---------------------------------------------------------------------------


def _lock_owner_page(session: Any, owner_id: str, page_key: str) -> None:
    """同一 (owner_id, page_key) 的写入串行化，保证计数上限与默认唯一在并发下成立。

    行锁无法阻止并发插入的新行（幻读），因此在 PostgreSQL 上用事务级 advisory lock；
    SQLite 单测无此函数且本身串行写，跳过该语句。
    """
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"qc_user_filter_templates:{owner_id}:{page_key}"},
    )


def _name_taken(session: Any, owner_id: str, page_key: str, name: str, *, exclude_id: str | None = None) -> bool:
    predicates = [
        _TABLE.c.owner_id == owner_id, _TABLE.c.page_key == page_key, _TABLE.c.name == name,
    ]
    if exclude_id is not None:
        predicates.append(_TABLE.c.id != exclude_id)
    return session.execute(select(_TABLE.c.id).where(*predicates).limit(1)).first() is not None


def _clear_default(
    session: Any, owner_id: str, page_key: str, now: datetime, *, exclude_id: str | None = None,
) -> None:
    """取消该页原默认；被取消的模板状态已变，version 同步 +1 以维持 CAS 语义。"""
    predicates = [
        _TABLE.c.owner_id == owner_id, _TABLE.c.page_key == page_key,
        _TABLE.c.is_default.is_(True),
    ]
    if exclude_id is not None:
        predicates.append(_TABLE.c.id != exclude_id)
    session.execute(
        update(_TABLE).where(*predicates)
        .values(is_default=False, version=_TABLE.c.version + 1, updated_at=now)
    )


def _read_one(session: Any, owner_id: str, template_id: str) -> Any:
    return session.execute(
        select(*_COLUMNS).where(_TABLE.c.id == template_id, _TABLE.c.owner_id == owner_id)
    ).first()


def _template_id(template_id: Any) -> str:
    if not isinstance(template_id, str) or not template_id.strip() or len(template_id) > 36:
        raise FilterTemplateNotFound("筛选模板不存在")
    return template_id


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------


def list_templates(*, owner_id: str, page_key: str) -> dict[str, Any]:
    """本人该页全部模板：is_default 降序，再按 name 排序。"""
    owner_id = _owner(owner_id)
    page_key = _page_key(page_key)
    factory = _require_session_factory()
    try:
        with factory() as session:
            rows = session.execute(
                select(*_COLUMNS)
                .where(_TABLE.c.owner_id == owner_id, _TABLE.c.page_key == page_key)
                .order_by(_TABLE.c.is_default.desc(), _TABLE.c.name.asc(), _TABLE.c.id.asc())
            ).all()
    except SQLAlchemyError as exc:
        raise FilterTemplateUnavailable("筛选模板读取失败") from exc
    return {
        "items": [_item(row) for row in rows],
        "page_key": page_key,
        "max_per_page": MAX_TEMPLATES_PER_PAGE,
    }


def create_template(
    *, owner_id: str, page_key: str, name: str, filters: Any, is_default: bool = False,
) -> dict[str, Any]:
    owner_id = _owner(owner_id)
    page_key = _page_key(page_key)
    name = _name(name)
    filters_json = _dump_filters(validate_filters(filters, page_key=page_key))
    if type(is_default) is not bool:
        raise FilterTemplateInvalid("is_default 必须是布尔值")
    factory = _require_session_factory()
    template_id = str(uuid4())
    try:
        with factory() as session:
            with session.begin():
                _lock_owner_page(session, owner_id, page_key)
                count = session.execute(
                    select(func.count(_TABLE.c.id)).where(
                        _TABLE.c.owner_id == owner_id, _TABLE.c.page_key == page_key,
                    )
                ).scalar_one()
                if int(count) >= MAX_TEMPLATES_PER_PAGE:
                    raise FilterTemplateConflict(
                        f"每个页面最多保存 {MAX_TEMPLATES_PER_PAGE} 个筛选模板", code="limit_reached",
                    )
                if _name_taken(session, owner_id, page_key, name):
                    raise FilterTemplateConflict("已存在同名筛选模板", code="name_conflict")
                now = _now()
                if is_default:
                    _clear_default(session, owner_id, page_key, now)
                session.execute(insert(_TABLE).values(
                    id=template_id, owner_id=owner_id, page_key=page_key, name=name,
                    filters_json=filters_json, is_default=is_default, version=1,
                    created_at=now, updated_at=now,
                ))
            row = _read_one(session, owner_id, template_id)
    except IntegrityError as exc:
        # 已在锁内预检；此处仅兜底并发下的同名唯一约束冲突。
        raise FilterTemplateConflict("已存在同名筛选模板", code="name_conflict") from exc
    except SQLAlchemyError as exc:
        raise FilterTemplateUnavailable("筛选模板保存失败") from exc
    return _item(row)


def update_template(
    *, owner_id: str, template_id: str, version: int,
    name: str | None = None, filters: Any = None, is_default: bool | None = None,
) -> dict[str, Any]:
    owner_id = _owner(owner_id)
    template_id = _template_id(template_id)
    version = _version(version)
    changes: dict[str, Any] = {}
    if name is not None:
        changes["name"] = _name(name)
    if is_default is not None:
        if type(is_default) is not bool:
            raise FilterTemplateInvalid("is_default 必须是布尔值")
        changes["is_default"] = is_default
    if not changes and filters is None:
        raise FilterTemplateInvalid("没有需要更新的字段")
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                current = _read_one(session, owner_id, template_id)
                if current is None:
                    raise FilterTemplateNotFound("筛选模板不存在")
                page_key = current.page_key
                if filters is not None:
                    changes["filters_json"] = _dump_filters(
                        validate_filters(filters, page_key=page_key)
                    )
                _lock_owner_page(session, owner_id, page_key)
                current = session.execute(
                    select(_TABLE.c.id, _TABLE.c.version)
                    .where(_TABLE.c.id == template_id, _TABLE.c.owner_id == owner_id)
                    .with_for_update()
                ).first()
                if current is None:
                    raise FilterTemplateNotFound("筛选模板不存在")
                if int(current.version) != version:
                    raise FilterTemplateConflict("筛选模板已被修改，请刷新后重试", code="version_conflict")
                if "name" in changes and _name_taken(
                    session, owner_id, page_key, changes["name"], exclude_id=template_id,
                ):
                    raise FilterTemplateConflict("已存在同名筛选模板", code="name_conflict")
                now = _now()
                if changes.get("is_default") is True:
                    _clear_default(session, owner_id, page_key, now, exclude_id=template_id)
                updated = session.execute(
                    update(_TABLE)
                    .where(
                        _TABLE.c.id == template_id, _TABLE.c.owner_id == owner_id,
                        _TABLE.c.version == version,
                    )
                    .values(**changes, version=version + 1, updated_at=now)
                )
                if updated.rowcount != 1:
                    raise FilterTemplateConflict("筛选模板已被修改，请刷新后重试", code="version_conflict")
            row = _read_one(session, owner_id, template_id)
    except IntegrityError as exc:
        raise FilterTemplateConflict("已存在同名筛选模板", code="name_conflict") from exc
    except SQLAlchemyError as exc:
        raise FilterTemplateUnavailable("筛选模板保存失败") from exc
    return _item(row)


def delete_template(*, owner_id: str, template_id: str, version: int) -> dict[str, Any]:
    owner_id = _owner(owner_id)
    template_id = _template_id(template_id)
    version = _version(version)
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                current = session.execute(
                    select(_TABLE.c.id, _TABLE.c.version)
                    .where(_TABLE.c.id == template_id, _TABLE.c.owner_id == owner_id)
                    .with_for_update()
                ).first()
                if current is None:
                    raise FilterTemplateNotFound("筛选模板不存在")
                if int(current.version) != version:
                    raise FilterTemplateConflict("筛选模板已被修改，请刷新后重试", code="version_conflict")
                deleted = session.execute(
                    delete(_TABLE).where(
                        _TABLE.c.id == template_id, _TABLE.c.owner_id == owner_id,
                        _TABLE.c.version == version,
                    )
                )
                if deleted.rowcount != 1:
                    raise FilterTemplateConflict("筛选模板已被修改，请刷新后重试", code="version_conflict")
    except SQLAlchemyError as exc:
        raise FilterTemplateUnavailable("筛选模板删除失败") from exc
    return {"id": template_id, "deleted": True}
