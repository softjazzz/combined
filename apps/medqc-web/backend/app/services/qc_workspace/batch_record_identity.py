"""批量任务结果页的病历身份回查：把客户安全引用（rec_）映射回可读的病历标识。

背景（2026-10-23 用户确认方案 A）：泸县 0609 正式结果只携带不可逆的 ``record_ref``，客户在结果页
无法对应到具体病历。本模块只在已授权读取该任务的会话中，按任务自身的病历范围（filters.record_refs）
正向重算引用并返回住院号、科室、主治医生、入出院日期；不返回患者姓名，不改变结果数据本身。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from ..case_identity import CaseRef
from .canonical_result_store import customer_safe_projection_key, keyed_ref

# 单个任务最多回查的病历数；超出时只回查前若干份，前端对未匹配的引用按序号展示。
MAX_IDENTITY_RECORDS = 500
_IDENTITY_FIELDS = ("department", "doctor", "admission_date", "discharge_date")


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _job_case_refs(job: Mapping[str, Any]) -> List[CaseRef]:
    filters = job.get("filters") if isinstance(job.get("filters"), Mapping) else {}
    refs: List[CaseRef] = []
    seen: set[CaseRef] = set()
    for raw in filters.get("record_refs") or ():
        if not isinstance(raw, Mapping):
            continue
        ref = CaseRef(_text(raw.get("institute_id")), _text(raw.get("patient_id")), _text(raw.get("visit_id")))
        if not all(ref) or ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
        if len(refs) >= MAX_IDENTITY_RECORDS:
            break
    return refs


def build_batch_job_record_identities(
    *,
    job: Mapping[str, Any],
    collect_records: Callable[..., Sequence[Mapping[str, Any]]],
    case_refs: Optional[Sequence[CaseRef]] = None,
    hmac_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """按任务病历范围返回 ``record_ref`` → 可读标识；顺序即任务中的病历顺序（序号从 1 起）。

    ``case_refs`` 优先取自正式结果信封（生成 record_ref 的同一来源）；缺省时退回任务筛选条件。
    """

    case_refs = list(dict.fromkeys(case_refs or ()))[:MAX_IDENTITY_RECORDS] or _job_case_refs(job)
    if not case_refs:
        return []
    key = hmac_key or customer_safe_projection_key()
    records = collect_records(
        scope="all", department=None, doctor=None, date_field="admission", start_date=None,
        end_date=None, keyword=None,
        record_refs=[{"institute_id": ref[0], "patient_id": ref[1], "visit_id": ref[2]} for ref in case_refs],
    )
    by_ref: Dict[CaseRef, Mapping[str, Any]] = {}
    for record in records or ():
        if not isinstance(record, Mapping):
            continue
        ref = CaseRef(_text(record.get("institute_id")), _text(record.get("patient_id")), _text(record.get("visit_id")))
        by_ref.setdefault(ref, record)
    identities: List[Dict[str, Any]] = []
    for sequence, ref in enumerate(case_refs, start=1):
        record = by_ref.get(ref, {})
        identity: Dict[str, Any] = {
            # 与正式结果信封同一算法（三坐标键 + 客户安全密钥），前端按此匹配结果中的 record_ref。
            "record_ref": keyed_ref("rec", ref.as_key(), hmac_key=key),
            "sequence": sequence,
            "inpatient_no": _text(record.get("mr_no")) or _text(record.get("inpat_no")),
        }
        identity.update({field: _text(record.get(field)) for field in _IDENTITY_FIELDS})
        identities.append(identity)
    return identities


__all__ = ["MAX_IDENTITY_RECORDS", "build_batch_job_record_identities"]
