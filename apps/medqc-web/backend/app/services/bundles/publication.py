"""Persistent fence and atomic publication for refreshed case Bundle variants."""

from __future__ import annotations

import re
import uuid
from typing import Any, Mapping, Sequence

from sqlalchemy import inspect, text

from ..case_identity import CaseRef
from .assembly import TASK_SYNC_INVALIDATED_POLICY_VERSION as INVALIDATED_POLICY_VERSION
from .contracts import BUNDLE_SCHEMA_VERSION_CURRENT


BUNDLE_VARIANTS = {
    "running_record_bundle": ("scene", "running"),
    "final_record_bundle": ("scene", "final"),
    "admission_domain_bundle": ("execution_domain", "admission"),
    "course_domain_bundle": ("execution_domain", "course"),
    "surgery_domain_bundle": ("execution_domain", "surgery"),
    "consult_discussion_domain_bundle": ("execution_domain", "consult_discussion"),
    "terminal_domain_bundle": ("execution_domain", "terminal"),
    "index_coding_settlement_domain_bundle": ("execution_domain", "index_coding_settlement"),
}
BUNDLE_TABLES = tuple(BUNDLE_VARIANTS)
_CHUNK_SIZE = 200
_STAGING_TOKEN = re.compile(rf"^{re.escape(INVALIDATED_POLICY_VERSION)}:[0-9a-f]{{32}}$")


def new_bundle_staging_token() -> str:
    return f"{INVALIDATED_POLICY_VERSION}:{uuid.uuid4().hex}"


def _tables_in_session(session: Any) -> tuple[str, ...]:
    bind = session.get_bind()
    inspector = inspect(bind)
    available = tuple(
        name for name in BUNDLE_TABLES if inspector.has_table(name, schema="public")
    )
    # Lightweight SQLite contract tests may omit all Bundle tables; partial schemas are never valid.
    if bind.dialect.name == "sqlite" and not available:
        return ()
    if len(available) != len(BUNDLE_TABLES):
        missing = set(BUNDLE_TABLES) - set(available)
        raise RuntimeError(f"缺少任务 Bundle 表: {', '.join(sorted(missing))}")
    return BUNDLE_TABLES


def _chunks(refs: Sequence[CaseRef]):
    for offset in range(0, len(refs), _CHUNK_SIZE):
        yield refs[offset:offset + _CHUNK_SIZE]


def _scope(chunk: Sequence[CaseRef]) -> tuple[str, dict[str, str]]:
    clauses = []
    params = {}
    for index, ref in enumerate(chunk):
        clauses.append(
            f"(institute_id = :institute_id_{index} "
            f"AND patient_id = :patient_id_{index} "
            f"AND visit_id = :visit_id_{index})"
        )
        params[f"institute_id_{index}"] = ref.institute_id
        params[f"patient_id_{index}"] = ref.patient_id
        params[f"visit_id_{index}"] = ref.visit_id
    return " OR ".join(clauses), params


def _checked_refs(refs: Sequence[CaseRef]) -> tuple[CaseRef, ...]:
    unique = tuple(refs)
    if len(set(unique)) != len(unique) or any(not all(ref) for ref in unique):
        raise ValueError("Bundle 病例三坐标缺失或重复")
    return unique


def invalidate_bundle_variants(refs: Sequence[CaseRef], *, session_factory: Any) -> None:
    """Fence all eight variants before the first independently committed CDM write."""
    unique = _checked_refs(refs)
    if not unique:
        return
    if session_factory is None:
        raise RuntimeError("数据库会话不可用")
    with session_factory.begin() as session:
        for table_name in _tables_in_session(session):
            variant_column, variant_value = BUNDLE_VARIANTS[table_name]
            for chunk in _chunks(unique):
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
                        {
                            **ref.as_dict(),
                            "variant_value": variant_value,
                            "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
                            "invalidated_policy_version": INVALIDATED_POLICY_VERSION,
                        }
                        for ref in chunk
                    ],
                )
                where, params = _scope(chunk)
                session.execute(
                    text(f"""
                        UPDATE public.{table_name}
                        SET policy_version = :invalidated_policy_version
                        WHERE {where}
                    """),
                    {**params, "invalidated_policy_version": INVALIDATED_POLICY_VERSION},
                )


def assert_complete_bundle_refresh(result: Any, visible_count: int) -> None:
    if not visible_count:
        return
    refresh = getattr(result, "bundle_refresh", None)
    if not isinstance(refresh, Mapping):
        raise RuntimeError("任务 Bundle 刷新结果缺失")
    variants = {
        "scenes": ("running", "final"),
        "domains": tuple(name.removesuffix("_domain_bundle") for name in BUNDLE_TABLES[2:]),
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


def publish_bundle_variants(
    refs: Sequence[CaseRef], *, staging_token: str,
    published_policy_version: str, session_factory: Any,
) -> None:
    """Validate exact staged identity/schema, then publish eight tables in one transaction."""
    unique = _checked_refs(refs)
    if not unique:
        return
    if not _STAGING_TOKEN.fullmatch(staging_token):
        raise ValueError("Bundle 暂存标记无效")
    if published_policy_version is None or published_policy_version == INVALIDATED_POLICY_VERSION \
            or _STAGING_TOKEN.fullmatch(published_policy_version):
        raise ValueError("Bundle 发布版本无效")
    if session_factory is None:
        raise RuntimeError("数据库会话不可用")
    with session_factory.begin() as session:
        tables = _tables_in_session(session)
        for table_name in tables:
            for chunk in _chunks(unique):
                where, params = _scope(chunk)
                count = session.execute(
                    text(f"""
                        SELECT COUNT(*) FROM public.{table_name}
                        WHERE ({where})
                          AND policy_version = :staging_token
                          AND bundle_schema_version = :bundle_schema_version
                    """),
                    {
                        **params,
                        "staging_token": staging_token,
                        "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
                    },
                ).scalar_one()
                if count != len(chunk):
                    raise RuntimeError("任务 Bundle 刷新不完整")
        for table_name in tables:
            for chunk in _chunks(unique):
                where, params = _scope(chunk)
                updated = session.execute(
                    text(f"""
                        UPDATE public.{table_name}
                        SET policy_version = :published_policy_version
                        WHERE ({where}) AND policy_version = :staging_token
                          AND bundle_schema_version = :bundle_schema_version
                    """),
                    {
                        **params,
                        "staging_token": staging_token,
                        "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
                        "published_policy_version": published_policy_version,
                    },
                )
                if updated.rowcount != len(chunk):
                    raise RuntimeError("任务 Bundle 发布数量不一致")
