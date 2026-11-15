"""病例材料唯一owner：短事务采集、不可变存储和源读回放；不判定临床结果。"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from functools import wraps
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile

PROTOCOL = "case-material-v1"
MAX_BYTES = 64 * 1024 * 1024
_active = ContextVar("case_material", default=None)
_recording = ContextVar("case_material_recording", default=None)


class MaterialSnapshotError(RuntimeError):
    """技术未完成；不可降为合规/不适用或用当前资料补造历史。"""


def encode(value):
    if isinstance(value, datetime):
        return {"$datetime": value.isoformat()}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, Decimal):
        return {"$decimal": str(value)}
    if type(value).__name__ == "SnapshotSourceRows":
        return {"$source_rows": {"source_key": value.source_key, "rows": encode(value.rows), "truncated": value.truncated, "limit_rows": value.limit_rows, **({"material_scope": encode(value.material_scope)} if value.material_scope is not None else {})}}
    if isinstance(value, Mapping):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    raise MaterialSnapshotError("material_value_type_unsupported")


def decode(value):
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"$datetime"}:
        return datetime.fromisoformat(value["$datetime"])
    if set(value) == {"$date"}:
        return date.fromisoformat(value["$date"])
    if set(value) == {"$decimal"}:
        return Decimal(value["$decimal"])
    if set(value) == {"$source_rows"}:
        from .luxian_0609.source_evidence_reader import SnapshotSourceRows
        return SnapshotSourceRows.create(**decode(value["$source_rows"]))
    return {key: decode(item) for key, item in value.items()}


def canonical(value):
    return json.dumps(encode(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def current():
    return _active.get()


def context():
    """受控投影读取捕获或冻结上下文；禁止调用者修改状态。"""
    return _active.get() if _active.get() is not None else _recording.get()


@contextmanager
def activate(material):
    token = _active.set(material)
    try:
        yield
    finally:
        _active.reset(token)


@contextmanager
def recording(state):
    token = _recording.set(state)
    try:
        yield
    finally:
        _recording.reset(token)


@contextmanager
def source_connection(engine):
    """受控来源使用同一短事务；物化后禁止未接入的源库SQL。"""
    state = _recording.get()
    if state is not None and engine is state["engine"]:
        with state["connection"].begin_nested():
            yield state["connection"]
    elif state is not None:
        raise MaterialSnapshotError("material_identity_or_source_mismatch")
    elif current() is not None:
        raise MaterialSnapshotError("uncaptured_source_query_forbidden")
    else:
        with engine.connect() as connection:
            yield connection


def source_binding(identity):
    """副本绑定业务库身份，普通病历保持既有独立CDM绑定；不读取口令。"""
    from .validation_material_source import is_material_copy
    if is_material_copy(identity[1], identity[2]):
        from ..database.connection import engine
        if engine is None:
            raise MaterialSnapshotError("material_source_unavailable")
        url = engine.url
        return "pdf-material-v1:" + fingerprint(
            [url.drivername, url.host, url.port, url.database, url.username])
    from ..database.clinical_connection import source_binding as clinical_binding
    return clinical_binding()


def identity_check(value, identity):
    if value["identity"] != list(identity) or value["binding"] != source_binding(identity):
        raise MaterialSnapshotError("material_identity_or_source_mismatch")


def frozen_columns(schema, table):
    value = current() or _recording.get()
    if value is None:
        return None
    if table not in value.get("columns", {}):
        if current() is not None:
            raise MaterialSnapshotError("uncaptured_material_columns")
        return None
    if schema != value["schema"]:
        raise MaterialSnapshotError("material_schema_mismatch")
    return tuple(value.get("columns", {}).get(table, ()))


def frozen_rows(schema, table, identity, limit):
    value = current() or _recording.get()
    if value is None or (current() is None and table not in value.get("tables", {})):
        return None
    identity_check(value, identity)
    if schema != value["schema"] or table not in value["tables"]:
        raise MaterialSnapshotError("uncaptured_material_table")
    contracts = value.get("read_contract", {}).get("table_identity_columns")
    if contracts is not None:
        from .clinical_source_contract import material_identity_columns
        columns = value.get("columns", {}).get(table, ())
        if not isinstance(contracts, dict):
            raise MaterialSnapshotError("material_identity_or_source_mismatch")
        if columns:
            if contracts.get(table) != list(material_identity_columns(table, columns)):
                raise MaterialSnapshotError("material_identity_or_source_mismatch")
            validate_table_identity(table, columns, identity, value["tables"][table])
        elif value["tables"][table]:
            raise MaterialSnapshotError("material_identity_or_source_mismatch")
    return deepcopy(value["tables"][table][:limit])


def validate_table_identity(table, columns, identity, rows):
    """不改行内容，不伪造就诊键；临床表不得借患者级表合同放行。"""
    from .clinical_source_contract import KEYS, material_identity_columns
    keys = material_identity_columns(table, columns)
    if len(identity) != 3 or not all(isinstance(item, str) and item.strip() for item in identity) or not set(keys).issubset(columns):
        raise MaterialSnapshotError("material_identity_or_source_mismatch")
    expected = dict(zip(KEYS, identity))
    for row in rows:
        if not isinstance(row, Mapping) or any(row.get(key) != expected[key] for key in keys):
            raise MaterialSnapshotError("material_identity_or_source_mismatch")


def query_key(name, arguments, schema):
    values = dict(arguments)
    if values.get("source_schema") not in (None, schema):
        raise MaterialSnapshotError("material_query_schema_mismatch")
    values["source_schema"] = schema
    return name + ":" + fingerprint(values)


def material_query(function):
    """保留既有函数输出和错误合同，不在回放层重做医学判断。"""
    @wraps(function)
    def read(**arguments):
        value = current()
        recorder = _recording.get()
        if value is None and recorder is None:
            return function(**arguments)
        state = value if value is not None else recorder
        coordinates = (arguments.get("institute_id"), arguments.get("patient_id", arguments.get("current_patient_id")), arguments.get("visit_id", arguments.get("current_visit_id")))
        identity_check(state, coordinates)
        key = query_key(function.__name__, arguments, state["schema"])
        if value is not None:
            result = value["queries"].get(key)
            if result is None:
                raise MaterialSnapshotError("uncaptured_material_query")
            if "error" in result:
                from .luxian_0609 import source_evidence_reader as reader
                raise getattr(reader, result["error"])()
            return decode(encode(result["value"]))
        if key in recorder["queries"]:
            result = recorder["queries"][key]
            if "error" not in result:
                return decode(encode(result["value"]))
        try:
            with recorder["connection"].begin_nested():
                result = function(**arguments)
        except Exception as error:
            name = type(error).__name__
            recorder["queries"][key] = {"error": name if name in {"SourceEvidenceUnavailable", "SourceEvidenceQueryError", "SourceEvidenceTruncated"} else "SourceEvidenceQueryError"}
            raise
        recorder["queries"][key] = {"value": encode(result)}
        return result
    return read


def storage_root():
    explicit = os.getenv("QC_CASE_MATERIAL_DIR", "").strip()
    dispatch = os.getenv("QC_DISPATCH_STATE_DIR", "").strip()
    root = Path(explicit) if explicit else Path(dispatch).parent / "case-materials" if dispatch else Path(__file__).resolve().parents[2] / "data/case-materials"
    return root.resolve()


def _reference(job_id, identity):
    if not job_id or not all(isinstance(part, str) and part for part in identity):
        raise MaterialSnapshotError("material_task_identity_required")
    return fingerprint([job_id, list(identity)])


def _read_object(root, digest):
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise MaterialSnapshotError("invalid_material_reference")
    path = root / "objects" / (digest + ".json.gz")
    if path.is_symlink():
        raise MaterialSnapshotError("material_symlink_forbidden")
    try:
        with gzip.open(path, "rb") as file:
            raw = file.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != digest:
            raise MaterialSnapshotError("material_integrity_failed")
        value = decode(json.loads(raw))
        if value.get("protocol") != PROTOCOL:
            raise MaterialSnapshotError("material_protocol_unsupported")
        value["fingerprint"] = digest
        return value
    except MaterialSnapshotError:
        raise
    except Exception:
        raise MaterialSnapshotError("material_object_unavailable") from None


def load(job_id, identity):
    root = storage_root()
    path = root / "tasks" / (_reference(job_id, identity) + ".json")
    if not path.exists():
        return None
    if path.is_symlink():
        raise MaterialSnapshotError("material_symlink_forbidden")
    try:
        reference = json.loads(path.read_text(encoding="utf-8"))
        value = _read_object(root, reference["fingerprint"])
        identity_check(value, identity)
        return value
    except MaterialSnapshotError:
        raise
    except Exception:
        raise MaterialSnapshotError("material_reference_corrupt") from None


def _exclusive(path, data):
    """同盘硬链接原子发布；已存在则保留，绝不覆盖。"""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise MaterialSnapshotError("material_symlink_forbidden")
    fd, name = tempfile.mkstemp(prefix=".material-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(name, path)
        except FileExistsError:
            pass
    finally:
        os.unlink(name)


def persist(job_id, value):
    identity = tuple(value["identity"])
    identity_check(value, identity)
    raw = canonical({key: item for key, item in value.items() if key != "fingerprint"})
    if len(raw) > MAX_BYTES:
        raise MaterialSnapshotError("material_snapshot_capacity_exceeded")
    digest = hashlib.sha256(raw).hexdigest()
    root = storage_root()
    _exclusive(root / "objects" / (digest + ".json.gz"), gzip.compress(raw, mtime=0))
    _read_object(root, digest)
    reference = {"fingerprint": digest, "captured_at": datetime.now().astimezone().isoformat()}
    _exclusive(root / "tasks" / (_reference(job_id, identity) + ".json"), canonical(reference))
    # 竞争中的首次发布者决定本轮材料；不能各自继续使用不同的候选材料。
    return load(job_id, identity)


def session_bind(engine):
    state = _recording.get()
    if state is not None and (engine is None or engine is state["engine"]):
        return state["connection"]
    if state is not None:
        raise MaterialSnapshotError("material_identity_or_source_mismatch")
    if current() is not None:
        raise MaterialSnapshotError("uncaptured_source_session_forbidden")
    return engine
