"""当前病例已有材料的身份上下文；只读内存，不补查数据库。"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from ..case_identity import CaseRef
from .evidence_material import Luxian0609EvidenceMaterialStore
from .evidence_snapshot import Luxian0609EvidenceSnapshot, build_luxian_0609_visit_ref
from .source_manifest import QueryStatus
from .source_registry import SourceAccessMode, resolve_luxian_0609_physical_source_entry


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


# 只列已合法读取的明确患者/联系人字段，不读取医生、药品、正文或任意嵌套name。
_ORM_IDENTITY_FIELDS = frozenset({
    "name", "mr_no", "inpat_no", "id_card_no", "insurance_no",
    "contact_number", "contact_name", "contact_address", "contact_telephone",
    "nativeplace", "currentaddress", "work_unit",
})
_ORM_PATIENT_SOURCES = frozenset({
    "mr", "inpat_registration", "admission_record", "discharge_record",
})


class _CaseIdentityValues:
    __slots__ = ("values", "has_raw_name", "invalid")

    def __init__(self) -> None:
        self.values: set[str] = set()
        self.has_raw_name = False
        self.invalid = False

    def __repr__(self) -> str:
        return "<LX0609 private case identity>"

    def __reduce_ex__(self, protocol):
        raise PrivacyIdentityContextUnavailable()


class _Luxian0609IdentityCollector:
    """仅本次worker请求内存；关闭清空，CaseRef严格隔离，不属于返回合同。"""
    __slots__ = ("_cases", "_active", "_invalid")

    def __init__(self) -> None:
        self._cases: dict[CaseRef, _CaseIdentityValues] = {}
        self._active = True
        self._invalid = False

    def __repr__(self) -> str:
        return "<LX0609 private identity collector>"

    def __reduce_ex__(self, protocol):
        raise PrivacyIdentityContextUnavailable()

    @staticmethod
    def _scalar(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise PrivacyIdentityContextUnavailable()
        return str(value).strip()

    def _capture_values(self, row: Mapping[str, Any], *, fields: frozenset[str], name_field: str) -> None:
        if not self._active:
            raise PrivacyIdentityContextUnavailable()
        holder = None
        try:
            ref = CaseRef(*(self._scalar(row.get(key)) for key in ("institute_id", "patient_id", "visit_id")))
            if not all(ref):
                raise PrivacyIdentityContextUnavailable()
            holder = self._cases.setdefault(ref, _CaseIdentityValues())
            values = {self._scalar(row.get(key)) for key in fields}
            name = self._scalar(row.get(name_field))
            holder.values.update(value for value in values if value)
            holder.has_raw_name |= bool(name and "*" not in name and "＊" not in name)
        except Exception:
            # 无法归属的来源不能成为任何病例的有效身份；错误正文不保留。
            if holder is None:
                self._invalid = True
            else:
                holder.invalid = True

    def capture(self, source_key: str, source: Any) -> None:
        if source_key not in _ORM_PATIENT_SOURCES:
            self._invalid = True
            return
        try:
            # 只读已加载列的__dict__；避免getattr触发ORM lazy load/额外查询。
            row = vars(source)
        except Exception:
            self._invalid = True
            return
        self._capture_values(row, fields=_ORM_IDENTITY_FIELDS, name_field="name")

    def capture_hydrated_record(self, record: Mapping[str, Any]) -> None:
        self._capture_values(
            record, fields=frozenset({"patient_name", "mr_no", "inpat_no"}),
            name_field="patient_name",
        )

    def provider_for_case(self, case_ref: CaseRef) -> Callable[[], tuple[str, ...]]:
        if not isinstance(case_ref, CaseRef) or not all(case_ref):
            raise PrivacyIdentityContextUnavailable()

        def provide() -> tuple[str, ...]:
            holder = self._cases.get(case_ref)
            if not self._active or self._invalid or holder is None or holder.invalid or not holder.has_raw_name:
                raise PrivacyIdentityContextUnavailable()
            return tuple(sorted(holder.values))

        return provide

    def close(self) -> None:
        self._active = False
        for holder in self._cases.values():
            holder.values.clear()
            holder.has_raw_name = False
        self._cases.clear()


def _is_controlled_fact_source(source_key: str) -> bool:
    try:
        entry = resolve_luxian_0609_physical_source_entry(source_key)
    except (KeyError, ValueError):
        return False
    return entry.access_mode is SourceAccessMode.CONTROLLED_FACT_V1


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
                    # 受控事实来源只产出有/无事实、不入材料库，没有可发送的原始行。
                    if _is_controlled_fact_source(observation.source_key):
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
