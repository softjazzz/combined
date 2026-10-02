"""门急诊 CDM 只读入口：身份、授权与完整文书读取，不装配质控结果。"""

from datetime import date, datetime
import json
from zoneinfo import ZoneInfo

from ..database.connection import SessionLocal
from .defect_rectification_service import _person, RectificationError
from .outpatient_record_list_service import OutpatientRecordInvalid, OutpatientRecordSourceUnavailable, OutpatientRecordPage

SOURCE = "cdm_outpat_record"
TABLE = "cdm.outpat_record"
COORDINATES = ("institute_id", "patient_id", "visit_id", "document_id")
PAGE_SIZE = 500
MAX_DOCUMENTS = 10_000
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
LIST_COLUMNS = "institute_id,patient_id,visit_id,document_id,name,dept_name,outpat_no,visit_datetime,visit_type"
HOSPITAL_TZ = ZoneInfo("Asia/Shanghai")


def identity(row):
    values = tuple(row.get(key) for key in COORDINATES)
    if any(not isinstance(value, str) or not value or value != value.strip()
           or any(ord(char) < 32 for char in value) for value in values):
        raise OutpatientRecordInvalid("门急诊文书四坐标不完整或无效")
    return values


def load_actor(actor_id):
    with SessionLocal() as session:
        return _person(session, actor_id)


def authorize(actor, *, institute_id=None, department=None):
    roles = actor["roles"]
    if "admin" in roles:
        return institute_id, department
    own_institute = actor.get("institute_id")
    if not own_institute or (institute_id and institute_id != own_institute):
        raise RectificationError("无权读取该机构门急诊病历", 403)
    if "qc_manager" in roles:
        return own_institute, department
    own_department = actor.get("department")
    if "doctor" not in roles or not own_department or (department and department != own_department):
        raise RectificationError("无权读取该科室门急诊病历", 403)
    return own_institute, own_department


async def load_documents(*, source, execute, institute_id=None, department=None, case=None, full=True):
    if source is None:
        raise OutpatientRecordSourceUnavailable("门急诊 CDM 数据源不可用")

    async def scan():
        rows, expected_count, previous, byte_size = [], None, None, 0
        while True:
            query = source.table(TABLE).select("*" if full else LIST_COLUMNS, count="exact")
            if institute_id:
                query = query.eq("institute_id", institute_id)
            if department:
                query = query.eq("dept_name", department)
            if case:
                for key, value in zip(COORDINATES[:3], case):
                    query = query.eq(key, value)
            for key in COORDINATES:
                query = query.order(key, desc=False)
            offset = len(rows)
            response = await execute(query.range(offset, offset + PAGE_SIZE - 1))
            page, count = getattr(response, "data", None), getattr(response, "count", None)
            if (not isinstance(page, list) or not isinstance(count, int) or isinstance(count, bool)
                or count < 0 or count > MAX_DOCUMENTS or count < offset + len(page)
                or len(page) != min(PAGE_SIZE, count - offset)
                or (expected_count is not None and count != expected_count)):
                raise OutpatientRecordSourceUnavailable("门急诊文书读取不完整或来源发生变化")
            expected_count = count
            for row in page:
                if not isinstance(row, dict):
                    raise OutpatientRecordSourceUnavailable("门急诊文书来源无效")
                key = identity(row)
                if (previous is not None and key <= previous) or (case and key[:3] != case):
                    raise OutpatientRecordSourceUnavailable("门急诊文书重复或分页顺序发生变化")
                if institute_id and key[0] != institute_id:
                    raise OutpatientRecordSourceUnavailable("门急诊文书机构范围不一致")
                if department and row.get("dept_name") != department:
                    raise OutpatientRecordSourceUnavailable("门急诊文书科室范围不一致")
                previous = key
                if full:
                    byte_size += len(json.dumps(row, ensure_ascii=False, default=str).encode("utf-8"))
                    if byte_size > MAX_DOCUMENT_BYTES:
                        raise OutpatientRecordSourceUnavailable("门急诊完整文书超过读取大小上限")
            rows.extend(page)
            if len(rows) == count:
                return rows

    try:
        rows = await scan()
        # 适配客户端每页独立事务；完整复读也校验同数量替换和正文漂移。
        if rows != await scan():
            raise OutpatientRecordSourceUnavailable("门急诊文书读取期间发生变化")
        return rows
    except OutpatientRecordSourceUnavailable:
        raise
    except Exception as exc:
        raise OutpatientRecordSourceUnavailable("门急诊 CDM 文书不可用") from exc


def visit_date(value):
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, datetime):
            return (value.astimezone(HOSPITAL_TZ) if value.tzinfo else value).date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
    except ValueError:
        pass
    raise OutpatientRecordSourceUnavailable("门急诊就诊时间无效")


def record(documents):
    row = documents[0]
    key = identity(row)
    # 多文书元数据冲突时不选一个值冒充病例权威属性。
    def shared(column):
        values = {str(doc.get(column)) for doc in documents if doc.get(column) not in (None, "")}
        return next(iter(values)) if len(values) == 1 else None
    return {
        **dict(zip(COORDINATES, key)), "id": json.dumps(key[:3], ensure_ascii=False),
        "record_id": shared("outpat_no") or key[2], "patient_name": shared("name"),
        "department": shared("dept_name"), "visit_type": shared("visit_type"),
        "visit_date": visit_date(shared("visit_datetime")),
        "doctor_name": None, "status": None, "score": None, "defect_count": None,
        "source": SOURCE, "document_count": len(documents),
    }


async def query_records(*, actor, source, execute, filters, page, page_size):
    if filters.scoring_standard or filters.status or filters.sort_field in {"score", "defect_count"}:
        raise OutpatientRecordInvalid("CDM 来源尚无可信质控评分或状态，请切换历史病历来源")
    institute_id, department = authorize(actor, department=filters.department)
    documents = await load_documents(source=source, execute=execute, institute_id=institute_id, department=department, full=False)
    grouped = {}
    for doc in documents:
        grouped.setdefault(identity(doc)[:3], []).append(doc)
    rows = [record(docs) for docs in grouped.values()]
    if filters.keyword:
        rows = [row for row in rows if any(filters.keyword.casefold() in str(row.get(key) or "").casefold()
                                          for key in ("record_id", "patient_name", "visit_id", "patient_id"))]
    if filters.start_date:
        rows = [row for row in rows if row["visit_date"] and row["visit_date"] >= filters.start_date.isoformat()]
    if filters.end_date:
        rows = [row for row in rows if row["visit_date"] and row["visit_date"] <= filters.end_date.isoformat()]
    known = [row for row in rows if row.get(filters.sort_field)]
    unknown = [row for row in rows if not row.get(filters.sort_field)]
    known.sort(key=lambda row: str(row[filters.sort_field]), reverse=filters.sort_order == "desc")
    rows = known + unknown
    offset = (page - 1) * page_size
    return OutpatientRecordPage(rows[offset:offset + page_size], len(rows))


async def detail(*, actor, source, execute, coordinates):
    key = identity(coordinates)
    institute_id, _ = authorize(actor, institute_id=key[0])
    docs = await load_documents(source=source, execute=execute, institute_id=institute_id, case=key[:3])
    if not any(identity(doc) == key for doc in docs):
        raise RectificationError("门急诊文书不存在", 404)
    # 同就诊的每份文书都须属于医生本科室，不能借同 visit 横向读取。
    for doc in docs:
        authorize(actor, institute_id=key[0], department=doc.get("dept_name"))
        if "admin" not in actor["roles"] and "qc_manager" not in actor["roles"] and doc.get("dept_name") != actor.get("department"):
            raise RectificationError("门急诊文书缺少可信科室", 403)
    payload = {
        "record": record(docs), "exists": True, "qc_data_status": "unavailable_outpatient_result",
        "defects": [], "remediation": [], "appeals": [], "operation_history": [],
        "documents": {"raw_documents": [{**doc, "source": SOURCE, "id": doc["document_id"],
                                         "document_title": doc.get("document_name") or doc["document_id"],
                                         "content": doc.get("record_content"), "source_fields": dict(doc)} for doc in docs]},
    }
    if len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise OutpatientRecordSourceUnavailable("门急诊完整文书超过响应大小上限")
    return payload
