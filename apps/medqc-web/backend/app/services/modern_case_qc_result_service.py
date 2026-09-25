"""现代病例质控结果只读快照。

身份与来源合同见 docs/plans/2026-09-24-v36-qc-case-identity-source-design.md：
只读取 ``identity_version = 1`` 且 ``source_key`` + 三坐标完全匹配的现代行；
通知再按真实 ``result.id``（写入侧 ``related_id``）关联本次结果；不按 ``record_id``
或通知 ``type`` 兜底，也不把“无现代结果”解释为质控通过。
对外只投影客户可见字段白名单，SQL 层不拉取 raw_output/evidence/recipient_id 等内部列。
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import MetaData, Table, desc, func, nullslast, or_, select
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal, engine
from .qc_persistence_service import VerifiedQCIdentity


# 三表必须共同部署的现代身份列。
IDENTITY_COLUMNS = ("identity_version", "source_key", "institute_id", "patient_id", "visit_id")
# cdm.mr 的病例三坐标。
CASE_COLUMNS = ("institute_id", "patient_id", "visit_id")
STORE_TABLES = ("qc_results", "qc_defects", "notifications")
# 客户可见字段白名单：既是对外投影，也是查询列（缺列即 SchemaUnavailable）。
RESULT_COLUMNS = (
    "id",
    "rule_set",
    "overall_score",
    "grade",
    "defect_count",
    "analysis_date",
    "created_at",
)
DEFECT_COLUMNS = (
    "id",
    "rule_code",
    "rule_name",
    "description",
    "severity",
    "category",
    "location",
    "suggestion",
    "status",
    "created_at",
    "updated_at",
)
NOTIFICATION_COLUMNS = (
    "id",
    "type",
    "title",
    "content",
    "severity",
    "is_read",
    "read_at",
    "created_at",
)
# 仅用于过滤/排序、不对外投影的内部列。
TABLE_QUERY_COLUMNS = {
    "qc_results": (),
    "qc_defects": ("result_id",),
    "notifications": ("recipient_id", "related_id"),
}
TABLE_PROJECTIONS = {
    "qc_results": RESULT_COLUMNS,
    "qc_defects": DEFECT_COLUMNS,
    "notifications": NOTIFICATION_COLUMNS,
}
COMPLETED_STATUS = "completed"
# 最新 1 条 + 最近最多 5 条，两组互不重叠。
LATEST_RESULT_LIMIT = 1
RECENT_RESULT_LIMIT = 5
# 缺陷分页：单组默认 20 条、上限 50 条；SQL 多取 1 条只用于判定是否还有下一页。
DEFAULT_DEFECTS_LIMIT = 20
MIN_DEFECTS_LIMIT = 1
MAX_DEFECTS_LIMIT = 50


class ModernCaseQCResultError(RuntimeError):
    """现代病例快照的失败语义基类；消息不携带底层异常文本。"""

    code = "modern_case_qc_result_error"


class CaseNotFound(ModernCaseQCResultError):
    """cdm.mr 中不存在该三坐标病例。"""

    code = "case_not_found"


class CaseIdentityAmbiguous(ModernCaseQCResultError):
    """同一三坐标在 cdm.mr 中命中多行，无法安全归属。"""

    code = "case_identity_ambiguous"


class SchemaUnavailable(ModernCaseQCResultError):
    """qc 现代身份合同或 cdm.mr 身份列未部署、缺列。"""

    code = "schema_unavailable"


class SourceUnavailable(ModernCaseQCResultError):
    """数据库、反射或查询不可用。"""

    code = "source_unavailable"


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """白名单投影后的传输归一：只把时间转成 ISO，其余原样。"""

    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in row.items()
    }


def _projection(table: Table) -> List[Any]:
    return [table.c[name] for name in TABLE_PROJECTIONS[table.name]]


@lru_cache(maxsize=8)
def _table(schema: str, table_name: str) -> Table:
    if engine is None:
        raise SourceUnavailable("modern case QC source is unavailable")
    metadata = MetaData()
    return Table(table_name, metadata, schema=schema, autoload_with=engine)


class ModernCaseQCResultService:
    """只读装配单个现代病例的结果、缺陷与通知。"""

    def __init__(self, session_factory: Optional[Any] = None) -> None:
        # 不在导入期强制数据库可用；无 DATABASE_URL 时由 get_snapshot 返回 SourceUnavailable。
        self._session_factory = session_factory or SessionLocal

    def get_snapshot(
        self,
        identity: VerifiedQCIdentity,
        recipient_id: Optional[str] = None,
        *,
        active_defects_offset: int = 0,
        current_result_defects_offset: int = 0,
        defects_limit: int = DEFAULT_DEFECTS_LIMIT,
    ) -> Dict[str, Any]:
        if not isinstance(identity, VerifiedQCIdentity):
            raise TypeError("identity must be VerifiedQCIdentity")
        # 分页参数在触碰数据库前校验：非法参数不得退回成来源不可用。
        if active_defects_offset < 0 or current_result_defects_offset < 0:
            raise ValueError("defects offset must be a non-negative integer")
        if not MIN_DEFECTS_LIMIT <= defects_limit <= MAX_DEFECTS_LIMIT:
            raise ValueError("defects_limit must be between 1 and 50")
        if self._session_factory is None:
            raise SourceUnavailable("modern case QC source is unavailable")
        try:
            session: Session = self._session_factory()
        except Exception:
            raise SourceUnavailable("modern case QC source is unavailable") from None
        try:
            return self._build_snapshot(
                session,
                identity,
                recipient_id,
                active_defects_offset=active_defects_offset,
                current_result_defects_offset=current_result_defects_offset,
                defects_limit=defects_limit,
            )
        except ModernCaseQCResultError:
            raise
        except Exception:
            raise SourceUnavailable("modern case QC source is unavailable") from None
        finally:
            try:
                session.close()
            except Exception:
                pass

    def _build_snapshot(
        self,
        session: Session,
        identity: VerifiedQCIdentity,
        recipient_id: Optional[str],
        *,
        active_defects_offset: int = 0,
        current_result_defects_offset: int = 0,
        defects_limit: int = DEFAULT_DEFECTS_LIMIT,
    ) -> Dict[str, Any]:
        self._require_exact_case(session, identity)
        tables = self._require_modern_tables()
        snapshot: Dict[str, Any] = {
            "identity_status": "verified",
            "source_key": identity.source_key,
            "institute_id": identity.institute_id,
            "patient_id": identity.patient_id,
            "visit_id": identity.visit_id,
            "latest_qc_result": None,
            "recent_results": [],
            "active_defects": [],
            "current_result_defects": [],
            "active_defects_has_more": False,
            "current_result_defects_has_more": False,
            "active_defects_next_offset": None,
            "current_result_defects_next_offset": None,
            "latest_notification": None,
        }
        results = self._load_results(session, tables["qc_results"], identity)
        if not results:
            # 无现代结果：不回退历史行、不猜测通过，缺陷与通知一律为空，分页游标不作数。
            return snapshot
        latest_id = _safe_text(results[0]["id"]).strip()
        snapshot["latest_qc_result"] = results[0]
        snapshot["recent_results"] = results[1:]
        active_defects, active_has_more = self._load_defects(
            session,
            tables["qc_defects"],
            identity,
            offset=active_defects_offset,
            limit=defects_limit,
        )
        snapshot["active_defects"] = active_defects
        snapshot["active_defects_has_more"] = active_has_more
        snapshot["active_defects_next_offset"] = (
            active_defects_offset + len(active_defects) if active_has_more else None
        )
        current_defects, current_has_more = self._load_defects(
            session,
            tables["qc_defects"],
            identity,
            result_id=latest_id,
            offset=current_result_defects_offset,
            limit=defects_limit,
        )
        snapshot["current_result_defects"] = current_defects
        snapshot["current_result_defects_has_more"] = current_has_more
        snapshot["current_result_defects_next_offset"] = (
            current_result_defects_offset + len(current_defects) if current_has_more else None
        )
        recipient = _safe_text(recipient_id).strip()
        if recipient:
            snapshot["latest_notification"] = self._load_notification(
                session, tables["notifications"], identity, recipient, latest_id
            )
        return snapshot

    @staticmethod
    def _reflect(schema: str, table_name: str) -> Table:
        return _table(schema, table_name)

    def _require_exact_case(self, session: Session, identity: VerifiedQCIdentity) -> None:
        mr = self._reflect("cdm", "mr")
        missing = [name for name in CASE_COLUMNS if name not in mr.c]
        if missing:
            raise SchemaUnavailable(f"cdm.mr missing case identity columns: {sorted(missing)}")
        count = session.execute(
            select(func.count()).select_from(mr).where(
                *(mr.c[name] == getattr(identity, name) for name in CASE_COLUMNS)
            )
        ).scalar_one()
        if count == 0:
            raise CaseNotFound("modern case is absent from cdm.mr")
        if count != 1:
            raise CaseIdentityAmbiguous("modern case identity matches multiple cdm.mr rows")

    def _require_modern_tables(self) -> Dict[str, Table]:
        tables: Dict[str, Table] = {}
        for name in STORE_TABLES:
            table = self._reflect("qc", name)
            missing = [column for column in IDENTITY_COLUMNS if column not in table.c]
            if missing:
                raise SchemaUnavailable(
                    f"qc.{name} missing modern identity columns: {sorted(missing)}"
                )
            required = (*TABLE_PROJECTIONS[name], *TABLE_QUERY_COLUMNS[name])
            missing = [column for column in required if column not in table.c]
            if missing:
                raise SchemaUnavailable(f"qc.{name} missing required columns: {sorted(missing)}")
            tables[name] = table
        return tables

    @staticmethod
    def _owner_clause(table: Table, identity: VerifiedQCIdentity) -> List[Any]:
        return [table.c[name] == value for name, value in identity.columns().items()]

    def _load_results(
        self, session: Session, table: Table, identity: VerifiedQCIdentity
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(*_projection(table))
            .where(*self._owner_clause(table, identity))
            .order_by(
                nullslast(desc(table.c.analysis_date)),
                nullslast(desc(table.c.created_at)),
                desc(table.c.id),
            )
            .limit(LATEST_RESULT_LIMIT + RECENT_RESULT_LIMIT)
        )
        return [_serialize_row(dict(row)) for row in session.execute(stmt).mappings().all()]

    def _load_defects(
        self,
        session: Session,
        table: Table,
        identity: VerifiedQCIdentity,
        *,
        result_id: Optional[str] = None,
        offset: int = 0,
        limit: int = DEFAULT_DEFECTS_LIMIT,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        conditions = self._owner_clause(table, identity)
        if result_id is None:
            # 未关闭缺陷与已关闭缺陷分开呈现；历史 NULL 状态按未关闭处理。
            conditions.append(or_(table.c.status.is_(None), table.c.status != COMPLETED_STATUS))
        else:
            conditions.append(table.c.result_id == result_id)
        stmt = (
            select(*_projection(table))
            .where(*conditions)
            .order_by(
                nullslast(desc(table.c.updated_at)),
                nullslast(desc(table.c.created_at)),
                desc(table.c.id),
            )
            .offset(offset)
            .limit(limit + 1)
        )
        rows = [_serialize_row(dict(row)) for row in session.execute(stmt).mappings().all()]
        # 多取的第 limit+1 条只用来判定 has_more，不对外返回。
        return rows[:limit], len(rows) > limit

    def _load_notification(
        self,
        session: Session,
        table: Table,
        identity: VerifiedQCIdentity,
        recipient_id: str,
        result_id: str,
    ) -> Optional[Dict[str, Any]]:
        # 只认本次最新结果对应的通知：旧结果或另一轮写入的通知不得挂到最新结果下。
        stmt = (
            select(*_projection(table))
            .where(
                *self._owner_clause(table, identity),
                table.c.recipient_id == recipient_id,
                table.c.related_id == result_id,
            )
            .order_by(nullslast(desc(table.c.created_at)), desc(table.c.id))
            .limit(1)
        )
        row = session.execute(stmt).mappings().first()
        return _serialize_row(dict(row)) if row else None


default_modern_case_qc_result_service = ModernCaseQCResultService()
