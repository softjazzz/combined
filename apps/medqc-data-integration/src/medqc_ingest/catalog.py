"""生产注册表之外的候选接口元数据；候选项绝不授权真实调用。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from medqc_ingest.contracts import RAW_KEY_FIELDS


class DateSemantics(str, Enum):
    SINGLE_DAY = "single_day"
    RANGE_INCLUSIVE = "range_inclusive"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CandidateInterface:
    name: str
    argument_count: int
    date_semantics: DateSemantics
    registration_status: str
    key_fields: tuple[str, ...] = ()
    relation_keys: tuple[tuple[str, tuple[str, ...]], ...] = ()


_RANGE_NAMES = frozenset(
    {
        "web.exam_item_report",
        "web.pathology_exam_master",
        "web.pathology_exam_report",
        "web.inpat_bill_item",
        "web.medical_insurance_settlement",
        "web.medical_insurance_settlement_cost",
        "web.inpat_drug_order",
        "web.inpat_nondrug_order",
        "web.mr_icu",
    }
)

_SINGLE_NAMES = (
    "web.mr",
    "web.diagnosis",
    "web.discharge_record",
    "web.mr_surgery",
    "web.mr_cost",
    "web.labtest_master",
    "web.labtest_item_report",
    "web.labtest_item",
    "web.mr_bloodtrans",
    "web.mr_customize",
    "web.epidemic_record",
    "web.first_course_record",
    "web.daily_course_record",
    "web.senior_course_record",
    "web.postsurg_firstcourse_record",
    "web.rescue_record",
    "web.summary_record",
    "web.handoff_record",
    "web.handover_record",
    "web.consultation_record",
    "web.diffcase_discussion_record",
    "web.transfer_out_record",
    "web.transfer_in_record",
    "web.docpat_commu_record",
    "web.admission_record",
    "web.daily_admission_record",
    "web.death_record",
    "web.daily_death_record",
    "web.death_discussion",
    "web.surgery_application",
    "web.surgery_record",
    "web.surgery_risk_assessment",
    "web.presurg_discussion",
    "web.presurg_summary",
    "web.surgery_inform_consent",
    "web.surgery_safecheck_record",
    "web.surgery_inventory_record",
    "web.preane_surveil_record",
    "web.postane_surveil_record",
    "web.anesthesia_record",
    "web.blood_application",
    "web.bloodtrans_record",
    "web.nursing_record",
    "web.crisis_value_record",
    "web.newborn_record",
    "web.outpat_record",
    "web.inpat_registration",
)

_REGISTERED_NAMES = frozenset(RAW_KEY_FIELDS)


def _build_catalog() -> dict[str, CandidateInterface]:
    result: dict[str, CandidateInterface] = {}
    for name in (*_SINGLE_NAMES, *_RANGE_NAMES):
        registered = name in _REGISTERED_NAMES
        result[name] = CandidateInterface(
            name=name,
            argument_count=1 if name in _SINGLE_NAMES else 2,
            date_semantics=(
                DateSemantics.SINGLE_DAY
                if name in _SINGLE_NAMES
                else DateSemantics.RANGE_INCLUSIVE
            ),
            registration_status="registered" if registered else "candidate",
            key_fields=RAW_KEY_FIELDS.get(name, ()),
            relation_keys=(
                (("case", ("institute_id", "patient_id", "visit_id")),)
                if registered
                else ()
            ),
        )
    return dict(sorted(result.items()))


CANDIDATE_INTERFACE_CATALOG = _build_catalog()

if len(CANDIDATE_INTERFACE_CATALOG) != 56:  # pragma: no cover - import-time invariant
    raise RuntimeError("candidate interface catalog must contain 56 entries")
