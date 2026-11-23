"""特殊病历来源：限定结构化字段、显式院方码、机构配置 CAS。"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import MetaData, Table, inspect, select, text, tuple_
from sqlalchemy.exc import IntegrityError

from ..database import clinical_connection
from ..database.connection import SessionLocal
from .clinical_read import clinical_read_schema
from .defect_rectification_service import RectificationError, _person

COORDINATES = ("institute_id", "patient_id", "visit_id")
TYPES = {
    "death": "死亡",
    "critical": "危重",
    "difficult": "疑难",
    "consultation": "会诊",
    "transfusion": "输血",
    "surgery": "手术",
    "surgery_ge3": "三级及以上手术",
    "surgery_ge4": "四级及以上手术",
}
SOURCES = {
    "death_record": ("death_datetime",),
    "daily_death_record": ("death_datetime",),
    "mr_customize": ("criticalcare_record_sign", "difficult_record_sign"),
    "consultation_record": ("consultation_time", "consultation_datetime"),
    "bloodtrans_record": ("transfution_datetime", "blood_transfusion_volume"),
    "surgery_record": (
        "surgery_begin_time",
        "surgery_end_time",
        "surgery_begin_datetime",
        "surgery_end_datetime",
        "surgery_level",
        "surgical_level",
    ),
}


class SpecialReportInvalid(ValueError):
    pass


class SpecialReportConflict(ValueError):
    pass


def empty_config():
    return {
        "critical": {"positive_codes": [], "negative_codes": []},
        "difficult": {"positive_codes": [], "negative_codes": []},
        "surgery_level_codes": {str(level): [] for level in range(1, 5)},
    }


def validate_config(config):
    if not isinstance(config, dict) or set(config) != set(empty_config()):
        raise SpecialReportInvalid("类型配置字段不完整或不在白名单中")
    groups = []
    for flag in ("critical", "difficult"):
        if not isinstance(config[flag], dict) or set(config[flag]) != {
            "positive_codes",
            "negative_codes",
        }:
            raise SpecialReportInvalid("危重和疑难须分别配置正负码")
        groups.append(config[flag])
    levels = config["surgery_level_codes"]
    if not isinstance(levels, dict) or set(levels) != {"1", "2", "3", "4"}:
        raise SpecialReportInvalid("须明确配置四档手术级别代码")
    groups.append(levels)
    for group in groups:
        seen = set()
        for codes in group.values():
            if (
                not isinstance(codes, list)
                or len(codes) > 100
                or any(
                    not isinstance(code, str)
                    or not code.strip()
                    or code != code.strip()
                    or len(code) > 100
                    for code in codes
                )
                or len(codes) != len(set(codes))
                or seen.intersection(codes)
            ):
                raise SpecialReportInvalid("代码须为不重复且互不重叠的非空字符串")
            seen.update(codes)
    return config


def authorize(session, actor_id, institute_id):
    if (
        not isinstance(institute_id, str)
        or not institute_id.strip()
        or len(institute_id) > 100
    ):
        raise SpecialReportInvalid("必须填写有效机构ID")
    institute_id = institute_id.strip()
    actor = _person(session, actor_id)
    if not actor["roles"] & {"admin", "qc_manager"}:
        raise RectificationError("无权读取特殊病历报表", 403)
    if "admin" not in actor["roles"] and actor["institute_id"] != institute_id:
        raise RectificationError("无权访问其他机构", 403)
    return institute_id


def _sync_config_registry_table(session) -> str:
    """按 single/split schema 模式解析配置注册表名，移除硬编码 qc.sync_config_registry。"""
    from ..database import connection as db_connection

    if (
        str(getattr(db_connection, "DB_SCHEMA_MODE", "") or "").strip().lower()
        == "split"
    ):
        return "qc.sync_config_registry"
    conn = session.connection()
    if conn is not None and conn.dialect.name == "sqlite":
        inspector = inspect(conn)
        if not inspector.has_table("sync_config_registry") and inspector.has_table(
            "sync_config_registry", schema="qc"
        ):
            return "qc.sync_config_registry"
    return "sync_config_registry"


def config_in_session(session, institute_id):
    registry_table = _sync_config_registry_table(session)
    row = session.execute(
        text(
            f"SELECT payload_json FROM {registry_table} "
            "WHERE namespace=:ns AND config_key=:key"
        ),
        {"ns": "special_record_report", "key": institute_id},
    ).first()
    data = json.loads(row[0]) if row else {"version_seq": 0, "config": empty_config()}
    if (
        set(data) != {"version_seq", "config"}
        or isinstance(data["version_seq"], bool)
        or not isinstance(data["version_seq"], int)
        or data["version_seq"] < 0
    ):
        raise RuntimeError("类型配置回执无效")
    validate_config(data["config"])
    return {"institute_id": institute_id, **data, "sources": SOURCES}


def read_config(actor_id, institute_id, *, session_factory=None):
    with (session_factory or SessionLocal)() as session:
        institute_id = authorize(session, actor_id, institute_id)
        return config_in_session(session, institute_id)


def write_config(actor_id, institute_id, *, version_seq, config, session_factory=None):
    validate_config(config)
    if (
        isinstance(version_seq, bool)
        or not isinstance(version_seq, int)
        or version_seq < 0
    ):
        raise SpecialReportInvalid("配置版本必须为非负整数")
    try:
        with (session_factory or SessionLocal)() as session, session.begin():
            institute_id = authorize(session, actor_id, institute_id)
            registry_table = _sync_config_registry_table(session)
            params = {"ns": "special_record_report", "key": institute_id}
            lock = (
                " FOR UPDATE" if session.get_bind().dialect.name == "postgresql" else ""
            )
            row = session.execute(
                text(
                    f"SELECT payload_json FROM {registry_table} "
                    "WHERE namespace=:ns AND config_key=:key" + lock
                ),
                params,
            ).first()
            previous = json.loads(row[0]) if row else {"version_seq": 0}
            if (
                not isinstance(previous, dict)
                or type(previous.get("version_seq")) is not int
                or previous["version_seq"] < 0
            ):
                raise RuntimeError("持久类型配置版本无效")
            if previous.get("version_seq") != version_seq:
                raise SpecialReportConflict("类型配置已变化，请刷新后重试")
            params.update(
                payload=json.dumps(
                    {"version_seq": version_seq + 1, "config": config},
                    ensure_ascii=False,
                ),
                actor=actor_id,
            )
            if row:
                params["previous"] = row[0]
                changed = session.execute(
                    text(
                        f"UPDATE {registry_table} SET payload_json=:payload, "
                        "updated_by=:actor, updated_at=CURRENT_TIMESTAMP "
                        "WHERE namespace=:ns AND config_key=:key AND payload_json=:previous"
                    ),
                    params,
                )
                if changed.rowcount != 1:
                    raise SpecialReportConflict("类型配置并发冲突")
            else:
                session.execute(
                    text(
                        f"INSERT INTO {registry_table} "
                        "(namespace,config_key,payload_json,updated_by,source,change_reason,updated_at) "
                        "VALUES (:ns,:key,:payload,:actor,'special_report','院方显式代码配置',CURRENT_TIMESTAMP)"
                    ),
                    params,
                )
            return config_in_session(session, institute_id)
    except IntegrityError as exc:
        raise SpecialReportConflict("类型配置并发冲突") from exc


def _load_sources_from_bind(executor, bind, identities, *, schema):
    inspector = inspect(bind)
    result = {identity: {name: None for name in SOURCES} for identity in identities}
    ordered = sorted(identities)
    for name, allowed in SOURCES.items():
        if not inspector.has_table(name, schema=schema):
            continue
        columns = {column["name"] for column in inspector.get_columns(name, schema=schema)}
        if not set(COORDINATES).issubset(columns):
            continue
        selected = [field for field in allowed if field in columns]
        if not selected:
            continue
        table = Table(name, MetaData(), schema=schema, autoload_with=bind)
        for identity in identities:
            result[identity][name] = []
        total = 0
        for start in range(0, len(ordered), 500):
            rows = (
                executor.execute(
                    select(*(table.c[field] for field in (*COORDINATES, *selected)))
                    .where(
                        tuple_(*(table.c[field] for field in COORDINATES)).in_(
                            ordered[start : start + 500]
                        )
                    )
                    .limit(50001 - total)
                )
                .mappings()
                .all()
            )
            total += len(rows)
            if total > 50000:
                raise SpecialReportInvalid("特殊病历来源明细超过上限")
            for row in rows:
                identity = tuple(str(row[field]).strip() for field in COORDINATES)
                result[identity][name].append(dict(row))
    return result


def load_sources(session, identities):
    """只反射白名单字段；按临床只读路由区分 single/split/独立CDM；缺表/列保留未知。"""
    if not identities:
        return {}
    if clinical_connection.configured():
        clinical_engine = clinical_connection.get_engine()
        if clinical_engine is None:
            raise RuntimeError("独立临床库只读连接不可用")
        with clinical_engine.connect() as connection:
            return _load_sources_from_bind(
                connection, connection, identities, schema="cdm"
            )
    conn = session.connection()
    return _load_sources_from_bind(
        session, conn, identities, schema=clinical_read_schema()
    )


def time_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass
    return None


def fact(state="unknown", reason="source_missing"):
    return {"state": state, "reason_code": reason}


def classify(sources, config, record):
    hospital_tz = timezone(timedelta(hours=8))

    def event_time(value):
        parsed = time_value(value)
        if parsed is None:
            return None
        parsed = datetime.fromisoformat(parsed)
        parsed = (
            parsed.astimezone(hospital_tz).replace(tzinfo=None)
            if parsed.tzinfo
            else parsed
        )
        end = record.get("discharge_time")
        start = record.get("admission_time")
        end = (
            end.astimezone(hospital_tz).replace(tzinfo=None)
            if end and end.tzinfo
            else end
        )
        start = (
            start.astimezone(hospital_tz).replace(tzinfo=None)
            if start and start.tzinfo
            else start
        )
        if (
            not isinstance(end, datetime)
            or parsed > end
            or parsed > datetime.now(hospital_tz).replace(tzinfo=None)
            or (isinstance(start, datetime) and parsed < start)
        ):
            return None
        return parsed

    def consistent_time(row, fields):
        times = {
            event_time(row[field]) for field in fields if row.get(field) is not None
        }
        return next(iter(times)) if len(times) == 1 and None not in times else None

    result = {key: fact() for key in TYPES}
    for key, column in (
        ("critical", "criticalcare_record_sign"),
        ("difficult", "difficult_record_sign"),
    ):
        rows = sources.get("mr_customize")
        values = {row.get(column) for row in rows or []}
        dictionary = config[key]
        if len(values) == 1:
            code = next(iter(values))
            state = (
                "positive"
                if code in dictionary["positive_codes"]
                else "negative"
                if code in dictionary["negative_codes"]
                else "unknown"
            )
            result[key] = fact(
                state,
                "explicit_institute_code" if state != "unknown" else "code_unmapped",
            )
        elif values:
            result[key] = fact(reason="source_conflict")
    death_rows = [
        row
        for name in ("death_record", "daily_death_record")
        for row in sources.get(name) or []
    ]
    if any(event_time(row.get("death_datetime")) for row in death_rows):
        result["death"] = fact("positive", "death_time_present")
    for row in sources.get("consultation_record") or []:
        if consistent_time(row, ("consultation_time", "consultation_datetime")):
            result["consultation"] = fact("positive", "consultation_completed")
    for row in sources.get("bloodtrans_record") or []:
        try:
            volume = Decimal(str(row.get("blood_transfusion_volume")))
        except InvalidOperation:
            continue
        if (
            volume.is_finite()
            and volume > 0
            and event_time(row.get("transfution_datetime"))
        ):
            result["transfusion"] = fact("positive", "transfusion_performed")
    levels, unknown_level = [], False
    for row in sources.get("surgery_record") or []:
        begin = consistent_time(row, ("surgery_begin_time", "surgery_begin_datetime"))
        end = consistent_time(row, ("surgery_end_time", "surgery_end_datetime"))
        raw_begin = any(
            row.get(field) is not None
            for field in ("surgery_begin_time", "surgery_begin_datetime")
        )
        raw_end = any(
            row.get(field) is not None
            for field in ("surgery_end_time", "surgery_end_datetime")
        )
        if (
            not (begin or end)
            or (raw_begin and not begin)
            or (raw_end and not end)
            or (begin and end and begin > end)
        ):
            unknown_level = True
            continue
        result["surgery"] = fact("positive", "surgery_performed")
        codes = {
            row[field]
            for field in ("surgery_level", "surgical_level")
            if row.get(field) not in (None, "")
        }
        mapped = {
            int(level)
            for level, values in config["surgery_level_codes"].items()
            if codes.intersection(values)
        }
        if len(codes) != 1 or len(mapped) != 1:
            unknown_level = True
        else:
            levels.extend(mapped)
    for key, threshold in (("surgery_ge3", 3), ("surgery_ge4", 4)):
        if any(level >= threshold for level in levels):
            result[key] = fact("positive", "explicit_surgery_level")
        elif levels and not unknown_level:
            result[key] = fact("negative", "explicit_surgery_level")
    return result
