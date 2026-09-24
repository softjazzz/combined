"""Explicitly hydrate the saved case identities of a QC task."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from sqlalchemy import inspect, select, text

from ..database.connection import SessionLocal
from ..database.models.qc import QCTask, QCTaskRecord
from .bundles.assembly import (
    TASK_SYNC_INVALIDATED_POLICY_VERSION as INVALIDATED_POLICY_VERSION,
    _load_scene_bundle,
    _scene_bundle_has_usable_content,
)
from .bundles.contracts import BUNDLE_SCHEMA_VERSION_CURRENT
from .case_identity import CaseRef
from .case_set_sync_service import CaseSetSyncService
from .etl_sync import SYNC_TABLE_GROUPS, list_sync_table_groups
from .qc_workspace.record_repository import RecordRepository


logger = logging.getLogger(__name__)
TABLE_GROUP = "sample_full_domain"
CONTRACT_VERSION = "task-record-sync-v1"
MAX_RECORDS = 100
_BUNDLE_TABLES = (
    "running_record_bundle",
    "final_record_bundle",
    "admission_domain_bundle",
    "course_domain_bundle",
    "surgery_domain_bundle",
    "consult_discussion_domain_bundle",
    "terminal_domain_bundle",
    "index_coding_settlement_domain_bundle",
)
_BUNDLE_VARIANTS = {
    "running_record_bundle": ("scene", "running"),
    "final_record_bundle": ("scene", "final"),
    "admission_domain_bundle": ("execution_domain", "admission"),
    "course_domain_bundle": ("execution_domain", "course"),
    "surgery_domain_bundle": ("execution_domain", "surgery"),
    "consult_discussion_domain_bundle": ("execution_domain", "consult_discussion"),
    "terminal_domain_bundle": ("execution_domain", "terminal"),
    "index_coding_settlement_domain_bundle": ("execution_domain", "index_coding_settlement"),
}


class TaskRecordSyncNotFound(LookupError):
    pass


class TaskRecordSyncForbidden(PermissionError):
    pass


class TaskRecordSyncConflict(ValueError):
    pass


def _table_names() -> list[str]:
    raw_group = next((group for group in SYNC_TABLE_GROUPS if group["id"] == TABLE_GROUP), None)
    public_group = next((group for group in list_sync_table_groups() if group["id"] == TABLE_GROUP), None)
    names = list((raw_group or {}).get("table_names") or [])
    if not names or not public_group or names != public_group["table_names"]:
        raise TaskRecordSyncConflict("任务同步资料集配置不完整")
    return names


def load_task_refs_in_session(
    session: Any, task_id: str, actor_id: str, is_admin: bool, *, lock: bool = False,
) -> tuple[str, list[tuple[str, CaseRef]]]:
    query = select(QCTask.__table__).where(QCTask.id == task_id)
    task = session.execute(query.with_for_update() if lock else query).mappings().first()
    if task is None:
        raise TaskRecordSyncNotFound("任务不存在")
    if task["creator_id"] != actor_id and not is_admin:
        raise TaskRecordSyncForbidden("仅任务创建人或管理员可同步病历")
    scene = str(task.get("scene") or "")
    if scene not in {"running", "final"}:
        raise TaskRecordSyncConflict("当前任务场景尚无可执行资料链")
    if task["status"] not in {"sampling", "assigned", "in_progress", "completed"}:
        raise TaskRecordSyncConflict("任务未完成抽样或已取消")
    rows = session.execute(
        select(QCTaskRecord.__table__)
        .where(QCTaskRecord.task_id == task_id)
        .order_by(QCTaskRecord.created_at, QCTaskRecord.id)
    ).mappings().all()
    try:
        expected = int(task["total_records"])
    except (TypeError, ValueError) as exc:
        raise TaskRecordSyncConflict("任务抽样数量无效") from exc
    if expected <= 0 or expected != len(rows) or expected > MAX_RECORDS:
        raise TaskRecordSyncConflict(f"任务抽样数量不一致或超过单次 {MAX_RECORDS} 条上限")
    refs: list[tuple[str, CaseRef]] = []
    seen: set[CaseRef] = set()
    for row in rows:
        ref = CaseRef.from_mapping(row)
        if not all(ref) or any(len(value) > 100 for value in ref):
            raise TaskRecordSyncConflict("任务病历缺少完整三坐标")
        if row["record_id"] != row["id"] or ref in seen:
            raise TaskRecordSyncConflict("任务病历身份不符合三坐标抽样合同")
        seen.add(ref)
        refs.append((row["id"], ref))
    return scene, refs


def _load_task_refs(task_id: str, actor_id: str, is_admin: bool) -> tuple[str, list[tuple[str, CaseRef]]]:
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    with SessionLocal() as session:
        return load_task_refs_in_session(session, task_id, actor_id, is_admin)


def normalize_bundle_timestamp(value: Any) -> str:
    """将数据库的 UTC 时间统一成可跨事务比较的微秒精度时间。"""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("Bundle 更新时间缺失")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _ready_refs(scene: str, refs: list[CaseRef]) -> dict[CaseRef, dict[str, str]]:
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    records = RecordRepository(session_factory=SessionLocal).collect_records(
        scope=scene,
        department=None,
        doctor=None,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_refs=refs,
    )
    anchors = {CaseRef.from_mapping(row) for row in records}
    ready: dict[CaseRef, dict[str, str]] = {}
    for ref in refs:
        if ref not in anchors:
            continue
        bundle = _load_scene_bundle(
            scene=scene,
            institute_id=ref.institute_id,
            patient_id=ref.patient_id,
            visit_id=ref.visit_id,
            schema="public",
        )
        if (
            bundle
            and bundle.get("bundle_schema_version") == BUNDLE_SCHEMA_VERSION_CURRENT
            and bundle.get("policy_version") == CONTRACT_VERSION
            and _scene_bundle_has_usable_content(bundle)
        ):
            ready[ref] = {
                "bundle_schema_version": str(bundle["bundle_schema_version"]),
                "policy_version": str(bundle["policy_version"]),
                "bundle_updated_at": normalize_bundle_timestamp(bundle.get("bundle_updated_at")),
            }
    return ready


def _bundle_tables_in_session(session: Any) -> tuple[str, ...]:
    bind = session.get_bind()
    inspector = inspect(bind)
    available = tuple(
        table_name for table_name in _BUNDLE_TABLES
        if inspector.has_table(table_name, schema="public")
    )
    # 无 Bundle schema 的轻量 SQLite 单测沿用原有纯合同测试；部分建表不可跳过。
    if bind.dialect.name == "sqlite" and not available:
        return ()
    if len(available) != len(_BUNDLE_TABLES):
        missing = set(_BUNDLE_TABLES) - set(available)
        raise RuntimeError(f"缺少任务 Bundle 表: {', '.join(sorted(missing))}")
    return _BUNDLE_TABLES


def _bundle_params(ref: CaseRef) -> dict[str, str]:
    return {
        "institute_id": ref.institute_id,
        "patient_id": ref.patient_id,
        "visit_id": ref.visit_id,
    }


def _invalidate_existing_bundles(scene: str, refs: list[CaseRef]) -> None:
    """在任何独立提交的 CDM 写入前，为目标病例持久建立失效栅栏。"""
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    with SessionLocal.begin() as session:
        for table_name in _bundle_tables_in_session(session):
            variant_column, variant_value = _BUNDLE_VARIANTS[table_name]
            session.execute(
                text(f"""
                    INSERT INTO public.{table_name} (
                        institute_id, patient_id, visit_id, {variant_column},
                        bundle_schema_version, policy_version
                    ) VALUES (
                        :institute_id, :patient_id, :visit_id, :variant_value,
                        :bundle_schema_version, :invalidated_policy_version
                    ) ON CONFLICT (institute_id, patient_id, visit_id) DO NOTHING
                """),
                [
                    {**_bundle_params(ref), "variant_value": variant_value,
                     "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
                     "invalidated_policy_version": INVALIDATED_POLICY_VERSION}
                    for ref in refs
                ],
            )
            session.execute(
                text(f"""
                    UPDATE public.{table_name}
                    SET policy_version = :invalidated_policy_version
                    WHERE institute_id = :institute_id
                      AND patient_id = :patient_id
                      AND visit_id = :visit_id
                """),
                [
                    {**_bundle_params(ref), "invalidated_policy_version": INVALIDATED_POLICY_VERSION}
                    for ref in refs
                ],
            )


def _publish_refreshed_bundles(refs: list[CaseRef], staging_token: str) -> None:
    """八类 Bundle 验证齐备后，同一事务发布可执行版本。"""
    if not refs:
        return
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    with SessionLocal.begin() as session:
        tables = _bundle_tables_in_session(session)
        if not tables:
            return
        for table_name in tables:
            for ref in refs:
                row = session.execute(text(f"""
                    SELECT policy_version, bundle_schema_version
                    FROM public.{table_name}
                    WHERE institute_id = :institute_id
                      AND patient_id = :patient_id
                      AND visit_id = :visit_id
                """), _bundle_params(ref)).mappings().first()
                if (
                    row is None
                    or row["policy_version"] != staging_token
                    or row["bundle_schema_version"] != BUNDLE_SCHEMA_VERSION_CURRENT
                ):
                    raise RuntimeError("任务 Bundle 刷新不完整")
        for table_name in tables:
            updated = session.execute(
                text(f"""
                    UPDATE public.{table_name}
                    SET policy_version = :contract_version
                    WHERE institute_id = :institute_id
                      AND patient_id = :patient_id
                      AND visit_id = :visit_id
                      AND policy_version = :staging_token
                """),
                [
                    {**_bundle_params(ref), "contract_version": CONTRACT_VERSION,
                     "staging_token": staging_token}
                    for ref in refs
                ],
            )
            if updated.rowcount != len(refs):
                raise RuntimeError("任务 Bundle 发布数量不一致")


def _assert_complete_bundle_refresh(result: Any, visible_count: int) -> None:
    if not visible_count:
        return
    refresh = getattr(result, "bundle_refresh", None)
    if not isinstance(refresh, Mapping):
        raise RuntimeError("任务 Bundle 刷新结果缺失")
    variants = {
        "scenes": ("running", "final"),
        "domains": tuple(
            name.removesuffix("_domain_bundle")
            for name in _BUNDLE_TABLES[2:]
        ),
    }
    for group, names in variants.items():
        counts_by_name = refresh.get(group)
        if not isinstance(counts_by_name, Mapping):
            raise RuntimeError("任务 Bundle 刷新结果缺失")
        for name in names:
            counts = counts_by_name.get(name)
            if (
                not isinstance(counts, Mapping)
                or counts.get("updated") != visible_count
                or counts.get("processed") != visible_count
                or counts.get("failed") != 0
            ):
                raise RuntimeError("任务 Bundle 刷新不完整")


def sync_task_records(
    *,
    task_id: str,
    actor_id: str,
    is_admin: bool = False,
    sync_factory: Callable[[], CaseSetSyncService] = CaseSetSyncService,
    readiness_checker: Callable[[str, list[CaseRef]], Any] = _ready_refs,
    expected_records: list[dict[str, str]] | None = None,
    expected_scene: str | None = None,
) -> dict[str, Any]:
    """Synchronize a bounded saved set; source failures stay retryable and visible."""
    scene, records = _load_task_refs(task_id, actor_id, is_admin)
    if expected_scene is not None and scene != expected_scene:
        raise TaskRecordSyncConflict("任务场景已变化，请重新发起同步")
    if expected_records is not None:
        current = [
            {"task_record_id": record_id, "institute_id": ref.institute_id,
             "patient_id": ref.patient_id, "visit_id": ref.visit_id}
            for record_id, ref in records
        ]
        if current != expected_records:
            raise TaskRecordSyncConflict("任务抽样三坐标已变化，请重新发起同步")
    table_names = _table_names()
    refs = [ref for _, ref in records]
    try:
        _invalidate_existing_bundles(scene, refs)
    except Exception as exc:
        logger.warning("task_record_bundle_invalidation_failed task_id=%s error_type=%s", task_id, type(exc).__name__)
        raise RuntimeError("病历 Bundle 失效保护失败，未启动源端同步") from exc
    staging_token = f"{INVALIDATED_POLICY_VERSION}:{uuid.uuid4().hex}"
    try:
        result = sync_factory().sync_case_set(
            case_refs=refs,
            table_names=table_names,
            policy_version=CONTRACT_VERSION,
            bundle_policy_version=staging_token,
            sync_scene=scene,
            case_scene_by_ref={ref: scene for ref in refs},
        )
    except Exception as exc:
        logger.warning("task_record_sync_failed task_id=%s error_type=%s", task_id, type(exc).__name__)
        raise RuntimeError("病历资料同步失败，可重试；已同步的部分资料会在重试时复核") from exc

    synced_by_name = {str(item.get("table_name") or ""): item for item in result.synced_tables}
    unavailable = [
        name for name in table_names
        if synced_by_name.get(name, {}).get("sync_status") != "synced"
    ]
    visible_refs = set(result.visible_case_refs)
    if not visible_refs.issubset(refs):
        raise RuntimeError("源端返回了任务范围外的病例三坐标")
    if not unavailable:
        try:
            _assert_complete_bundle_refresh(result, len(visible_refs))
            _publish_refreshed_bundles(list(visible_refs), staging_token)
        except Exception as exc:
            logger.warning("task_record_bundle_publish_failed task_id=%s error_type=%s", task_id, type(exc).__name__)
            raise RuntimeError("病历 Bundle 发布失败，请重试") from exc
    try:
        ready_refs = readiness_checker(scene, refs) if not unavailable else set()
    except Exception as exc:
        logger.warning("task_record_readiness_failed task_id=%s error_type=%s", task_id, type(exc).__name__)
        raise RuntimeError("本地病历就绪检查失败，请稍后重试") from exc
    response_records = []
    for record_id, ref in records:
        if ref not in visible_refs:
            status, reason, message = "failed", "source_primary_missing", "源端未返回主记录"
        elif unavailable:
            status, reason, message = "failed", "source_detail_unavailable", "源端资料集不完整"
        elif ref not in ready_refs:
            status, reason, message = "failed", "workspace_not_ready", "本地病历或 Bundle 尚不可执行"
        else:
            status, reason, message = "ready", None, None
        receipt = ready_refs.get(ref) if isinstance(ready_refs, dict) and status == "ready" else None
        response_records.append({
            "task_record_id": record_id,
            "status": status,
            **({"reason_code": reason, "message": message} if reason else {}),
            **(receipt or {}),
        })
    ready_count = sum(item["status"] == "ready" for item in response_records)
    return {
        "task_id": task_id,
        "table_group": TABLE_GROUP,
        "contract_version": CONTRACT_VERSION,
        "total": len(records),
        "ready_count": ready_count,
        "failed_count": len(records) - ready_count,
        "records": response_records,
    }
