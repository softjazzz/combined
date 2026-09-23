from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import psycopg2
import psycopg2.extras

from .case_identity import CaseRef


_SCOPE_MODES = {"active", "discharged", "active_and_discharged"}
_ADMISSION_TIME_COLUMNS = (
    "admission_datetime",
    "admission_time",
    "inpat_datetime",
    "inpat_time",
    "record_time",
)
_DISCHARGE_TIME_COLUMNS = (
    "discharge_datetime",
    "discharge_time",
    "discharge_date",
)
_HOSPITAL_TIMEZONE = timezone(timedelta(hours=8))
ACTIVE_ADMISSION_LOOKBACK_DAYS = 180


@dataclass(frozen=True)
class HospitalizationScopeResult:
    case_refs: tuple[CaseRef, ...]
    selected: tuple[dict[str, Any], ...]
    all_selected: tuple[dict[str, Any], ...]
    sources_used: tuple[str, ...]
    source_status: str
    warnings: tuple[str, ...]

    def to_legacy_dict(self) -> dict[str, Any]:
        return {
            "selected": [dict(row) for row in self.selected],
            "all_selected": [dict(row) for row in self.all_selected],
            "sources_used": list(self.sources_used),
            "source_status": self.source_status,
            "warnings": list(self.warnings),
        }


class CaseScopeService:
    """从源库按统一住院口径选择三坐标病例集合。"""

    def __init__(
        self,
        *,
        remote_url_loader: Callable[[], str] | None = None,
        db_config_loader: Callable[[], Mapping[str, Any]] | None = None,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._remote_url_loader = remote_url_loader or _default_remote_url_loader
        self._db_config_loader = db_config_loader or _default_db_config_loader
        self._connection_factory = connection_factory or psycopg2.connect

    def resolve_hospitalization_scope(
        self,
        *,
        scope_mode: str,
        as_of_date: date,
        discharge_start_date: date | None,
        discharge_end_date: date | None,
        departments: Sequence[str],
        admission_start_date: date | None = None,
    ) -> HospitalizationScopeResult:
        normalized_mode = _normalize_scope(
            scope_mode=scope_mode,
            admission_start_date=admission_start_date,
            as_of_date=as_of_date,
            discharge_start_date=discharge_start_date,
            discharge_end_date=discharge_end_date,
        )
        remote_url = self._remote_url_loader()
        if not remote_url:
            raise ValueError("远端 PG 未配置，无法读取住院范围")
        config = self._db_config_loader()
        remote_schema = _text(config.get("remote_schema"), "public") or "public"
        schema_ident = re.sub(r"[^A-Za-z0-9_]", "", remote_schema)
        if not schema_ident:
            raise ValueError("远端 schema 非法")

        candidate_tables = (
            "inpat_registration",
            "admission_record",
            "daily_admission_record",
            "discharge_record",
            "mr",
            "patient_information",
        )
        connection = self._connection_factory(remote_url, connect_timeout=10)
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cursor.execute(
                """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = ANY(%s)
                """,
                (remote_schema, list(candidate_tables)),
            )
            table_columns: dict[str, set[str]] = {}
            table_column_types: dict[str, dict[str, str]] = {}
            for row in cursor.fetchall() or []:
                table_name = _text(row.get("table_name"))
                column_name = _text(row.get("column_name"))
                if table_name and column_name:
                    table_columns.setdefault(table_name, set()).add(column_name)
                    table_column_types.setdefault(table_name, {})[column_name] = _text(
                        row.get("data_type")
                    ).lower()
            plan = _resolve_source_plan(
                table_columns=table_columns,
                table_column_types=table_column_types,
                scope_mode=normalized_mode,
                default_institute_id=_text(config.get("default_institute_id")),
            )
            default_institute_id = _text(config.get("default_institute_id"))

            def column_expr(
                *,
                columns: set[str],
                candidates: Sequence[str],
                alias: str,
            ) -> str:
                column = _first_available(columns, candidates)
                return f"{column} AS {alias}" if column else f"NULL AS {alias}"

            def fetch_source(
                role: str,
                source: Mapping[str, Any] | None,
            ) -> list[dict[str, Any]]:
                if source is None:
                    return []
                table_name = _text(source.get("table_name"))
                columns = set(source.get("columns") or set())
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
                    raise ValueError("住院来源表名称非法")
                admission_column = _text(source.get("admission_time_column"))
                discharge_column = _text(source.get("discharge_time_column"))
                admission_data_type = _text(source.get("admission_time_data_type")).lower()
                discharge_data_type = _text(source.get("discharge_time_data_type")).lower()
                institute_expr = (
                    "institute_id::text"
                    if "institute_id" in columns
                    else "%s::text"
                )
                identity_params: list[Any] = (
                    [] if "institute_id" in columns else [default_institute_id]
                )
                patient_name_expr = column_expr(
                    columns=columns,
                    candidates=("name", "patient_name"),
                    alias="patient_name",
                )
                mr_no_expr = column_expr(
                    columns=columns,
                    candidates=("mr_no", "inpat_no"),
                    alias="mr_no",
                )
                inpat_no_expr = column_expr(
                    columns=columns,
                    candidates=("inpat_no", "mr_no"),
                    alias="inpat_no",
                )
                admission_department_expr = column_expr(
                    columns=columns,
                    candidates=("admission_dept_name", "department_name"),
                    alias="admission_department",
                )
                current_department_expr = column_expr(
                    columns=columns,
                    candidates=(
                        "current_dept_name",
                        "dept_name",
                        "transfer_dept_name",
                    ),
                    alias="current_department",
                )
                discharge_department_expr = column_expr(
                    columns=columns,
                    candidates=(
                        "discharge_dept_name",
                        "dept_name",
                        "transfer_dept_name",
                    ),
                    alias="discharge_department",
                )
                if role in {"active", "active_admission"}:
                    admission_calendar_value = (
                        f"({admission_column} AT TIME ZONE 'Asia/Shanghai')"
                        if admission_data_type == "timestamp with time zone"
                        else admission_column
                    )
                    effective_admission_start = admission_start_date
                    if role == "active_admission" and effective_admission_start is None:
                        effective_admission_start = as_of_date - timedelta(
                            days=ACTIVE_ADMISSION_LOOKBACK_DAYS
                        )
                    admission_start_sql = (
                        f"{admission_calendar_value} >= %s::date AND "
                        if effective_admission_start
                        else ""
                    )
                    if role == "active":
                        discharge_calendar_value = (
                            f"({discharge_column} AT TIME ZONE 'Asia/Shanghai')"
                            if discharge_data_type == "timestamp with time zone"
                            else discharge_column
                        )
                        where_sql = (
                            admission_start_sql
                            + f"{admission_calendar_value} < (%s::date + INTERVAL '1 day') "
                            f"AND ({discharge_column} IS NULL "
                            f"OR {discharge_calendar_value} >= (%s::date + INTERVAL '1 day'))"
                        )
                    else:
                        where_sql = (
                            admission_start_sql
                            + f"{admission_calendar_value} < (%s::date + INTERVAL '1 day')"
                        )
                    date_params: list[Any] = []
                    if effective_admission_start:
                        date_params.append(effective_admission_start.isoformat())
                    date_params.append(as_of_date.isoformat())
                    if role == "active":
                        date_params.append(as_of_date.isoformat())
                    for index, exclusion_source in enumerate(
                        plan.get("active_exclusions") or ()
                    ):
                        exclusion_table = _text(exclusion_source.get("table_name"))
                        exclusion_columns = set(exclusion_source.get("columns") or set())
                        exclusion_discharge_column = _text(
                            exclusion_source.get("discharge_time_column")
                        )
                        exclusion_alias = f"discharged_{index}"
                        exclusion_discharge_value = (
                            f"({exclusion_alias}.{exclusion_discharge_column} "
                            "AT TIME ZONE 'Asia/Shanghai')"
                            if _text(exclusion_source.get("discharge_time_data_type")).lower()
                            == "timestamp with time zone"
                            else f"{exclusion_alias}.{exclusion_discharge_column}"
                        )
                        exclusion_type = _text(
                            exclusion_source.get("discharge_time_data_type")
                        ).lower()
                        if exclusion_type in {"text", "character varying", "character"}:
                            # ISO 日期前缀按字典序等价于日期序；不可识别的非空值保守排除在院。
                            discharge_condition = (
                                f"({exclusion_alias}.{exclusion_discharge_column} IS NOT NULL "
                                "AND CASE WHEN "
                                f"btrim({exclusion_discharge_value}) ~ "
                                "'^[1-9][0-9]{3}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
                                "([ T]([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?)?$' "
                                f"THEN left(btrim({exclusion_discharge_value}), 10) "
                                "<= %s::date::text ELSE TRUE END)"
                            )
                        else:
                            discharge_condition = (
                                f"({exclusion_alias}.{exclusion_discharge_column} IS NOT NULL "
                                f"AND {exclusion_discharge_value} "
                                "< (%s::date + INTERVAL '1 day'))"
                            )
                        date_params.append(as_of_date.isoformat())
                        if (
                            exclusion_discharge_column != "discharge_date"
                            and "discharge_date" in exclusion_columns
                            and exclusion_source.get("discharge_date_data_type") == "date"
                        ):
                            discharge_condition = (
                                f"({discharge_condition} OR "
                                f"{exclusion_alias}.discharge_date <= %s::date)"
                            )
                            date_params.append(as_of_date.isoformat())
                        institute_match = ""
                        if "institute_id" in columns and "institute_id" in exclusion_columns:
                            institute_match = (
                                f"AND {exclusion_alias}.institute_id::text "
                                "= source_row.institute_id::text "
                            )
                        elif "institute_id" in exclusion_columns:
                            institute_match = (
                                f"AND {exclusion_alias}.institute_id::text = %s::text "
                            )
                        elif "institute_id" in columns:
                            institute_match = "AND source_row.institute_id::text = %s::text "
                        where_sql += (
                            " AND NOT EXISTS ("
                            f"SELECT 1 FROM {schema_ident}.{exclusion_table} "
                            f"AS {exclusion_alias} "
                            f"WHERE {discharge_condition} "
                            f"AND {exclusion_alias}.patient_id::text "
                            "= source_row.patient_id::text "
                            f"AND {exclusion_alias}.visit_id::text "
                            "= source_row.visit_id::text "
                            f"{institute_match}"
                            ")"
                        )
                        if institute_match and "= %s::text" in institute_match:
                            date_params.append(default_institute_id)
                    if "institute_id" in columns and not any(
                        "institute_id" in set(source.get("columns") or set())
                        for source in plan.get("active_exclusions") or ()
                    ):
                        where_sql += " AND source_row.institute_id::text = %s::text"
                        date_params.append(default_institute_id)
                else:
                    if discharge_start_date is None or discharge_end_date is None:
                        raise ValueError("期间出院范围必须填写出院开始日期和结束日期")
                    discharge_calendar_value = (
                        f"({discharge_column} AT TIME ZONE 'Asia/Shanghai')"
                        if discharge_data_type == "timestamp with time zone"
                        else discharge_column
                    )
                    where_sql = (
                        f"{discharge_calendar_value}::date >= %s::date "
                        f"AND {discharge_calendar_value}::date <= %s::date"
                    )
                    date_params = [
                        discharge_start_date.isoformat(),
                        discharge_end_date.isoformat(),
                    ]
                admission_time_expr = (
                    f"{admission_column} AS admission_time"
                    if admission_column
                    else "NULL AS admission_time"
                )
                discharge_time_expr = (
                    f"{discharge_column} AS discharge_time"
                    if discharge_column
                    else "NULL AS discharge_time"
                )
                order_time_alias = (
                    "admission_time" if admission_column else "discharge_time"
                )
                cursor.execute(
                    f"""
                    WITH scoped AS (
                        SELECT
                            {institute_expr} AS institute_id,
                            patient_id::text AS patient_id,
                            visit_id::text AS visit_id,
                            {patient_name_expr},
                            {mr_no_expr},
                            {inpat_no_expr},
                            {admission_time_expr},
                            {discharge_time_expr},
                            {admission_department_expr},
                            {current_department_expr},
                            {discharge_department_expr}
                        FROM {schema_ident}.{table_name} AS source_row
                        WHERE {where_sql}
                    )
                    SELECT DISTINCT ON (institute_id, patient_id, visit_id) *
                    FROM scoped
                    ORDER BY institute_id, patient_id, visit_id,
                             {order_time_alias} DESC NULLS LAST
                    """,
                    [*identity_params, *date_params],
                )
                return [
                    {**dict(row), "source_table": table_name}
                    for row in (cursor.fetchall() or [])
                ]

            active_source = plan.get("active")
            active_candidates = fetch_source("active", active_source)
            used_sources: list[str] = []
            runtime_warnings = list(plan["warnings"])
            source_status = str(plan["source_status"])
            if active_candidates:
                used_sources.append(_text(active_source.get("table_name")))
                used_sources.extend(
                    _text(source.get("table_name"))
                    for source in plan.get("active_exclusions") or ()
                )
            elif plan.get("active_fallback") is not None:
                fallback_source = plan["active_fallback"]
                if not plan.get("active_exclusions"):
                    raise ValueError(
                        "源库缺少可关联的权威出院事实，无法安全识别当前在院患者"
                    )
                active_candidates = fetch_source("active_admission", fallback_source)
                used_sources.append(_text(fallback_source.get("table_name")))
                used_sources.extend(
                    _text(source.get("table_name"))
                    for source in plan.get("active_exclusions") or ()
                )
                source_status = "degraded"
                runtime_warnings.append(
                    "住院登记没有可用在院时间，已按最近"
                    f"{ACTIVE_ADMISSION_LOOKBACK_DAYS}天入院记录排除已出院病例。"
                )

            candidates = [*active_candidates]
            for discharged_source in plan.get("discharged") or ():
                candidates.extend(fetch_source("discharged", discharged_source))
                used_sources.append(_text(discharged_source.get("table_name")))
            missing_name_identities = sorted(
                {
                    (
                        _text(row.get("institute_id")),
                        _text(row.get("patient_id")),
                    )
                    for row in candidates
                    if _text(row.get("institute_id"))
                    and _text(row.get("patient_id"))
                    and not _text(row.get("patient_name"))
                }
            )
            patient_columns = set(table_columns.get("patient_information") or set())
            patient_name_column = _first_available(
                patient_columns,
                ("name", "patient_name"),
            )
            demographic_rows: list[dict[str, Any]] = []
            patient_identity_available = "institute_id" in patient_columns or bool(
                default_institute_id
            )
            if (
                missing_name_identities
                and patient_name_column
                and "patient_id" in patient_columns
                and patient_identity_available
            ):
                for start in range(0, len(missing_name_identities), 200):
                    chunk = missing_name_identities[start : start + 200]
                    if "institute_id" in patient_columns:
                        placeholders = ", ".join(["(%s, %s)"] * len(chunk))
                        patient_params: list[str] = []
                        for institute_id, patient_id in chunk:
                            patient_params.extend([institute_id, patient_id])
                        cursor.execute(
                            f"""
                            SELECT institute_id::text AS institute_id,
                                   patient_id::text AS patient_id,
                                   {patient_name_column}::text AS patient_name
                            FROM {schema_ident}.patient_information
                            WHERE (institute_id::text, patient_id::text)
                                  IN ({placeholders})
                            """,
                            patient_params,
                        )
                    else:
                        patient_ids = [patient_id for _institute_id, patient_id in chunk]
                        cursor.execute(
                            f"""
                            SELECT %s::text AS institute_id,
                                   patient_id::text AS patient_id,
                                   {patient_name_column}::text AS patient_name
                            FROM {schema_ident}.patient_information
                            WHERE patient_id::text = ANY(%s)
                            """,
                            [default_institute_id, patient_ids],
                        )
                    demographic_rows.extend(
                        dict(row) for row in (cursor.fetchall() or [])
                    )
                candidates = _backfill_patient_names(
                    source_rows=candidates,
                    demographic_rows=demographic_rows,
                )
            all_selected = _select_candidates(
                candidates=candidates,
                scope_mode=normalized_mode,
                as_of_date=as_of_date,
                admission_start_date=admission_start_date,
                discharge_start_date=discharge_start_date,
                discharge_end_date=discharge_end_date,
                departments=(),
            )
            selected = _select_candidates(
                candidates=all_selected,
                scope_mode=normalized_mode,
                as_of_date=as_of_date,
                admission_start_date=admission_start_date,
                discharge_start_date=discharge_start_date,
                discharge_end_date=discharge_end_date,
                departments=departments,
            )
            return HospitalizationScopeResult(
                case_refs=tuple(
                    CaseRef(
                        _text(row.get("institute_id")),
                        _text(row.get("patient_id")),
                        _text(row.get("visit_id")),
                    )
                    for row in selected
                ),
                selected=tuple(selected),
                all_selected=tuple(all_selected),
                sources_used=tuple(dict.fromkeys(filter(None, used_sources))),
                source_status=source_status,
                warnings=tuple(dict.fromkeys(runtime_warnings)),
            )
        finally:
            cursor.close()
            connection.close()


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    normalized = str(value).strip()
    return normalized or default


def _default_remote_url_loader() -> str:
    from .etl_sync import get_remote_db_url

    return get_remote_db_url()


def _default_db_config_loader() -> Mapping[str, Any]:
    from .etl_sync import load_db_config

    return load_db_config()


def _first_available(columns: set[str], candidates: Sequence[str]) -> str:
    return next((column for column in candidates if column in columns), "")


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _to_hospital_wall_time(value)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = _text(value)
    if not text:
        return None
    normalized = text.replace("/", "-").replace("T", " ")
    try:
        return _to_hospital_wall_time(datetime.fromisoformat(normalized))
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(normalized[:10]), datetime.min.time())
        except ValueError:
            return None


def _to_hospital_wall_time(value: datetime) -> datetime:
    """统一源库 timestamptz 与无时区日期边界，按医院本地时间进行范围判断。"""

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=None)
    return value.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)


def _select_candidates(
    *,
    candidates: Sequence[Mapping[str, Any]],
    scope_mode: str,
    as_of_date: date,
    admission_start_date: date | None,
    discharge_start_date: date | None,
    discharge_end_date: date | None,
    departments: Sequence[str],
) -> list[dict[str, Any]]:
    department_filter = {_text(item) for item in departments if _text(item)}
    as_of_end = datetime.combine(as_of_date + timedelta(days=1), datetime.min.time())
    selected_by_identity: dict[tuple[str, str, str], dict[str, Any]] = {}
    for candidate in candidates:
        institute_id = _text(candidate.get("institute_id"))
        patient_id = _text(candidate.get("patient_id"))
        visit_id = _text(candidate.get("visit_id"))
        identity = (institute_id, patient_id, visit_id)
        if not all(identity):
            continue
        admission_time = _parse_datetime(
            candidate.get("admission_time") or candidate.get("admission_datetime")
        )
        discharge_time = _parse_datetime(
            candidate.get("discharge_time") or candidate.get("discharge_datetime")
        )
        is_active = bool(
            admission_time
            and (admission_start_date is None or admission_time.date() >= admission_start_date)
            and admission_time < as_of_end
            and (discharge_time is None or discharge_time >= as_of_end)
        )
        is_period_discharge = bool(
            discharge_time
            and discharge_start_date
            and discharge_end_date
            and discharge_start_date <= discharge_time.date() <= discharge_end_date
        )
        status = ""
        if scope_mode in {"active", "active_and_discharged"} and is_active:
            status = "active"
        elif (
            scope_mode in {"discharged", "active_and_discharged"}
            and is_period_discharge
        ):
            status = "discharged"
        if not status:
            continue

        department_candidates = (
            (
                ("current_department", candidate.get("current_department")),
                ("admission_department", candidate.get("admission_department")),
            )
            if status == "active"
            else (
                ("discharge_department", candidate.get("discharge_department")),
                ("current_department", candidate.get("current_department")),
                ("admission_department", candidate.get("admission_department")),
            )
        )
        department_basis, department = next(
            (
                (basis, _text(value))
                for basis, value in department_candidates
                if _text(value)
            ),
            ("unavailable", ""),
        )
        if department_filter and department not in department_filter:
            continue

        normalized = dict(candidate)
        normalized.update(
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "admission_time": admission_time,
                "discharge_time": discharge_time,
                "hospitalization_status": status,
                "authoritative_time": (
                    admission_time if status == "active" else discharge_time
                ),
                "department": department,
                "department_basis": department_basis,
            }
        )
        existing = selected_by_identity.get(identity)
        if existing is None:
            selected_by_identity[identity] = normalized
            continue
        if existing.get("hospitalization_status") == "active" and status == "discharged":
            selected_by_identity[identity] = _fill_missing_candidate_fields(normalized, existing)
            continue
        selected_by_identity[identity] = _fill_missing_candidate_fields(existing, normalized)
    return list(selected_by_identity.values())


def _fill_missing_candidate_fields(
    authoritative: Mapping[str, Any],
    fallback: Mapping[str, Any],
) -> dict[str, Any]:
    """保留权威来源，只从后续来源补齐空白展示字段。"""

    merged = dict(authoritative)
    for key in (
        "patient_name",
        "mr_no",
        "inpat_no",
        "admission_time",
        "discharge_time",
        "admission_department",
        "current_department",
        "discharge_department",
    ):
        if not merged.get(key) and fallback.get(key):
            merged[key] = fallback.get(key)
    department_candidates = (
        (
            ("current_department", merged.get("current_department")),
            ("admission_department", merged.get("admission_department")),
        )
        if merged.get("hospitalization_status") == "active"
        else (
            ("discharge_department", merged.get("discharge_department")),
            ("current_department", merged.get("current_department")),
            ("admission_department", merged.get("admission_department")),
        )
    )
    merged["department_basis"], merged["department"] = next(
        ((basis, _text(value)) for basis, value in department_candidates if _text(value)),
        ("unavailable", ""),
    )
    return merged


def _backfill_patient_names(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    demographic_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    name_by_identity = {
        (
            _text(row.get("institute_id")),
            _text(row.get("patient_id")),
        ): _text(row.get("patient_name") or row.get("name"))
        for row in demographic_rows
        if _text(row.get("institute_id"))
        and _text(row.get("patient_id"))
        and _text(row.get("patient_name") or row.get("name"))
    }
    results: list[dict[str, Any]] = []
    for source_row in source_rows:
        row = dict(source_row)
        if not _text(row.get("patient_name")):
            row["patient_name"] = name_by_identity.get(
                (
                    _text(row.get("institute_id")),
                    _text(row.get("patient_id")),
                ),
                "",
            )
        results.append(row)
    return results


def _normalize_scope(
    *,
    scope_mode: str,
    admission_start_date: date | None,
    as_of_date: date,
    discharge_start_date: date | None,
    discharge_end_date: date | None,
) -> str:
    normalized_mode = _text(scope_mode).lower()
    if normalized_mode not in _SCOPE_MODES:
        raise ValueError("住院范围仅支持当前在院、期间出院或两者合并")
    if normalized_mode in {"active", "active_and_discharged"} and admission_start_date:
        if admission_start_date > as_of_date:
            raise ValueError("入院开始日期不能晚于在院截止日期")
        if (as_of_date - admission_start_date).days > 180:
            raise ValueError("入院日期范围最多 180 天")
    if normalized_mode in {"discharged", "active_and_discharged"}:
        if discharge_start_date is None or discharge_end_date is None:
            raise ValueError("期间出院范围必须填写出院开始日期和结束日期")
        if discharge_start_date > discharge_end_date:
            raise ValueError("出院开始日期不能晚于结束日期")
        if (discharge_end_date - discharge_start_date).days > 30:
            raise ValueError("出院日期范围最多 31 天")
    return normalized_mode


def _resolve_source_plan(
    *,
    table_columns: Mapping[str, set[str]],
    table_column_types: Mapping[str, Mapping[str, str]],
    scope_mode: str,
    default_institute_id: str,
) -> dict[str, Any]:
    blocked_by_missing_institute = False

    def choose_source(
        table_names: Sequence[str],
        *,
        require_admission_time: bool,
        require_discharge_time: bool = True,
    ) -> dict[str, Any] | None:
        nonlocal blocked_by_missing_institute
        for table_name in table_names:
            columns = set(table_columns.get(table_name) or set())
            if not {"patient_id", "visit_id"}.issubset(columns):
                continue
            admission_column = _first_available(columns, _ADMISSION_TIME_COLUMNS)
            discharge_column = _first_available(columns, _DISCHARGE_TIME_COLUMNS)
            if (require_admission_time and not admission_column) or (
                require_discharge_time and not discharge_column
            ):
                continue
            if "institute_id" not in columns and not default_institute_id:
                blocked_by_missing_institute = True
                continue
            return {
                "table_name": table_name,
                "columns": columns,
                "admission_time_column": admission_column,
                "admission_time_data_type": _text(
                    (table_column_types.get(table_name) or {}).get(admission_column)
                ).lower(),
                "discharge_time_column": discharge_column,
                "discharge_time_data_type": _text(
                    (table_column_types.get(table_name) or {}).get(discharge_column)
                ).lower(),
                "discharge_date_data_type": _text(
                    (table_column_types.get(table_name) or {}).get("discharge_date")
                ).lower(),
            }
        return None

    def choose_sources(
        table_names: Sequence[str],
        *,
        require_admission_time: bool,
        require_discharge_time: bool = True,
    ) -> tuple[dict[str, Any], ...]:
        """按权威优先级返回全部可用来源，避免仅首表存在就漏掉其他病例。"""

        sources: list[dict[str, Any]] = []
        for table_name in table_names:
            source = choose_source(
                (table_name,),
                require_admission_time=require_admission_time,
                require_discharge_time=require_discharge_time,
            )
            if source is not None:
                sources.append(source)
        return tuple(sources)

    needs_active = scope_mode in {"active", "active_and_discharged"}
    needs_discharged = scope_mode in {"discharged", "active_and_discharged"}
    active_source = (
        choose_source(("inpat_registration",), require_admission_time=True)
        if needs_active
        else None
    )
    active_fallback = (
        choose_source(
            ("admission_record",),
            require_admission_time=True,
            require_discharge_time=False,
        )
        if needs_active
        else None
    )
    text_types = {"text", "character varying", "character"}
    if active_source is not None and (
        active_source["admission_time_data_type"] in text_types
        or active_source["discharge_time_data_type"] in text_types
    ):
        active_source = None
    if active_fallback is not None and active_fallback["admission_time_data_type"] in text_types:
        active_fallback = None
    active_exclusions = (
        choose_sources(
            ("mr", "discharge_record"),
            require_admission_time=False,
            require_discharge_time=True,
        )
        if needs_active
        else ()
    )
    discharged_sources = (
        choose_sources(
            ("discharge_record", "mr", "inpat_registration", "admission_record"),
            require_admission_time=False,
        )
        if needs_discharged
        else ()
    )
    if (needs_active and active_source is None and active_fallback is None) or (
        needs_discharged and not discharged_sources
    ):
        if blocked_by_missing_institute:
            raise ValueError(
                "住院来源表缺少 institute_id，且未配置 default_institute_id"
            )
        if needs_active and active_source is None and active_fallback is None:
            raise ValueError("源库没有可识别的当前在院患者数据，请同步住院登记")
        raise ValueError("源库没有可识别的已出院患者数据，请同步出院记录或病案首页")
    if needs_active and not active_exclusions:
        raise ValueError("源库缺少可关联的权威出院事实，无法安全识别当前在院患者")

    warnings: list[str] = []
    if needs_active and len(active_exclusions) < 2:
        warnings.append("当前在院范围仅有部分权威出院反证来源，可能将已出院病例误判为在院。")
    if needs_active and any(
        "institute_id" not in source["columns"] for source in active_exclusions
    ) and any(
        source is not None and "institute_id" in source["columns"]
        for source in (active_source, active_fallback)
    ):
        warnings.append("部分出院反证来源缺少机构号，非默认机构仅可依据完整三坐标来源判断。")
    if (
        needs_discharged
        and discharged_sources
        and discharged_sources[0]["table_name"] != "discharge_record"
    ):
        warnings.append(
            "源库未提供可用出院记录表，已使用病案首页或住院记录识别期间出院患者。"
        )
    sources_used = list(
        dict.fromkeys(
            source["table_name"]
            for source in (active_source, *discharged_sources)
            if source is not None
        )
    )
    return {
        "active": active_source,
        "active_fallback": active_fallback,
        "active_exclusions": active_exclusions,
        "discharged": discharged_sources,
        "sources_used": sources_used,
        "source_status": "degraded" if warnings else "ready",
        "warnings": warnings,
    }
