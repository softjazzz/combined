"""当前病例已有材料的身份上下文；只读内存，不补查数据库。"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from .evidence_material import Luxian0609EvidenceMaterialStore
from .evidence_snapshot import Luxian0609EvidenceSnapshot, build_luxian_0609_visit_ref
from .source_manifest import QueryStatus


class PrivacyIdentityContextUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("LX0609 privacy identity context unavailable")


# 通用 name 仅在明确患者行/患者文书中表示患者，不递归扫描医师、药品和诊断。
_PATIENT_NAME_SOURCES = frozenset({
    "mr_frontpage", "inp_master", "inpat_registration", "admission_record",
    "first_course_record", "daily_course_record", "senior_course_record",
    "presurg_summary", "presurg_discussion", "postsurg_firstcourse_record",
    "surgery_record", "mr_surgery", "anesthesia_record", "discharge_record",
    "rescue_record", "consent_form", "surgery_inform_consent", "bloodtrans_record",
    "death_record", "death_discussion", "consultation_record", "handoff_record",
    "handover_record", "transfer_in_record", "transfer_out_record", "diffcase_discussion_record",
})
_IDENTITY_FIELDS = frozenset({
    "institute_id", "patient_id", "visit_id", "patient_name", "patientName",
    "mr_no", "inpat_no", "outpat_no", "medical_record_no", "medical_record_number",
    "id_card", "id_card_no", "identity_card", "identity_card_no", "identity_no",
    "phone", "mobile", "telephone", "patient_phone", "contact_phone", "contact_mobile",
    "contact_name", "contact_person", "contact_person_name", "guardian_name",
    "email", "address", "home_address", "contact_address",
})


def build_luxian_0609_identity_provider(
    *, institute_id: str = "", patient_id: str = "", visit_id: str = "",
    evidence_payload: Mapping[str, Any] | None = None,
    snapshot: Luxian0609EvidenceSnapshot | None = None,
    materials: Luxian0609EvidenceMaterialStore | None = None,
    snapshot_build_failed: bool = False,
) -> Callable[[], tuple[str, ...]]:
    """每次发送重新核验当前已有材料，不缓存或共用其他病例的身份集合。"""
    coordinates = {"institute_id": institute_id, "patient_id": patient_id, "visit_id": visit_id}

    def collect() -> tuple[str, ...]:
        values: set[str] = set()

        def scalar(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                raise PrivacyIdentityContextUnavailable()
            return str(value).strip()

        def row_values(row: Mapping[str, Any], source: str = "") -> None:
            if not isinstance(row, Mapping):
                raise PrivacyIdentityContextUnavailable()
            for key, wanted in coordinates.items():
                found = scalar(row.get(key))
                if found and scalar(wanted) and found != scalar(wanted):
                    raise PrivacyIdentityContextUnavailable()
            fields = _IDENTITY_FIELDS | ({"name"} if source in _PATIENT_NAME_SOURCES else set())
            for key in fields:
                value = scalar(row.get(key))
                if value:
                    values.add(value)

        try:
            if snapshot_build_failed:
                raise PrivacyIdentityContextUnavailable()
            row_values(coordinates)
            if evidence_payload is not None:
                row_values(evidence_payload)
                # sample_programmatic_evidence 构造的既有明确结构，不泛遍历嵌套 name。
                timeline = evidence_payload.get("programmatic_timeline")
                if timeline is not None:
                    row_values(timeline)
                    sources = timeline.get("structured_source_rows")
                    if sources is not None:
                        if not isinstance(sources, Mapping):
                            raise PrivacyIdentityContextUnavailable()
                        for source, rows in sources.items():
                            if not isinstance(source, str) or not isinstance(rows, (list, tuple)):
                                raise PrivacyIdentityContextUnavailable()
                            for row in rows:
                                row_values(row, source)
            if snapshot is None:
                if materials is not None:
                    raise PrivacyIdentityContextUnavailable()
            else:
                if not isinstance(snapshot, Luxian0609EvidenceSnapshot) or not isinstance(materials, Luxian0609EvidenceMaterialStore):
                    raise PrivacyIdentityContextUnavailable()
                if all(scalar(value) for value in coordinates.values()) and snapshot.visit_ref != build_luxian_0609_visit_ref(**coordinates):
                    raise PrivacyIdentityContextUnavailable()
                for observation in snapshot.observations:
                    # 没有可发送行的不可用来源不补查；声明有行却不可读则阻止本次发送。
                    if observation.query_state not in (QueryStatus.AVAILABLE, QueryStatus.EMPTY):
                        continue
                    for _, row in materials.document_rows(observation.source_key, snapshot=snapshot):
                        row_values(row, observation.source_key)
            if not values:
                raise PrivacyIdentityContextUnavailable()
        except Exception:
            # 读取异常可能携带患者/连接详情；只保留固定错误，禁止透传。
            raise PrivacyIdentityContextUnavailable() from None
        return tuple(sorted(values))

    return collect
