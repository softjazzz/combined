"""源接口到 CDM、bundle 与质控家族的静态证据合同。"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from medqc_ingest.catalog import CANDIDATE_INTERFACE_CATALOG
from medqc_ingest.domain import ErrorKind, IngestError


class CoverageStatus(str, Enum):
    DIRECT = "direct"
    DERIVED = "derived"
    PARTIAL = "partial"
    MISSING = "missing"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class CoverageContract:
    source_type: str
    source_interface: str
    source_field: str
    cdm_target: str
    bundle_usage: str
    qc_family: str
    transform_authority: str
    status: CoverageStatus
    evidence: str


_BUNDLE_SOURCE_TYPES = (
    "admission_record",
    "admission_record_diagnosis",
    "first_course_record",
    "first_course_record_diagnosis",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "summary_record",
    "transfer_in_record",
    "transfer_out_record",
    "newborn_record",
    "medical_order",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "inpat_bill_item",
    "blood_application",
    "bloodtrans_record",
    "crisis_value_record",
    "exam_master",
    "exam_item",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "pathology_exam_master",
    "pathology_exam_report",
    "presurg_summary",
    "presurg_discussion",
    "surgery_record",
    "anesthesia_record",
    "consent_form",
    "surgery_inform_consent",
    "surgery_application",
    "postsurg_firstcourse_record",
    "surgery_safecheck_record",
    "surgery_risk_assessment",
    "surgery_inventory_record",
    "postane_surveil_record",
    "docpat_commu_record",
    "consultation_record",
    "diffcase_discussion_record",
    "death_discussion",
    "handoff_record",
    "handover_record",
    "discharge_record",
    "discharge_record_diagnosis",
    "death_record",
    "mr",
    "diagnosis",
    "mr_surgery",
    "mr_cost",
    "medical_insurance_settlement",
    "medical_insurance_settlement_cost",
    "patient_information",
)

_DERIVATION_GAPS = frozenset(
    {
        "admission_record_diagnosis",
        "discharge_record_diagnosis",
        "first_course_record_diagnosis",
        "exam_item",
        "exam_master",
        "patient_information",
    }
)
_MISSING_GAPS = frozenset({"consent_form", "medical_order"})


def build_coverage_contracts() -> tuple[CoverageContract, ...]:
    rows: list[CoverageContract] = []
    for source_type in _BUNDLE_SOURCE_TYPES:
        interface = f"web.{source_type}"
        if source_type == "mr":
            rows.append(
                CoverageContract(
                    source_type=source_type,
                    source_interface="web.mr",
                    source_field="*:77-source-columns",
                    cdm_target="cdm.mr:*:78-target-columns",
                    bundle_usage="index_coding_settlement",
                    qc_family="unverified",
                    transform_authority="explicit_projection_contract",
                    status=CoverageStatus.DIRECT,
                    evidence="frozen_v5_contract_requires_export_recheck",
                )
            )
            continue
        if source_type in _MISSING_GAPS:
            status = CoverageStatus.MISSING
            evidence = "explicit_gap_no_callable_verified_source"
            interface = ""
            authority = "none"
        elif source_type in _DERIVATION_GAPS:
            status = CoverageStatus.BLOCKED
            evidence = "derivation_candidate_without_field_or_relation_evidence"
            interface = "web.mr" if source_type == "patient_information" else ""
            authority = "unverified_derivation"
        else:
            status = CoverageStatus.BLOCKED
            evidence = "name_match_only_not_field_verified"
            authority = "candidate_same_name"
            if interface not in CANDIDATE_INTERFACE_CATALOG:
                interface = ""
                evidence = "bundle_requirement_without_candidate_catalog_entry"
        rows.append(
            CoverageContract(
                source_type=source_type,
                source_interface=interface,
                source_field="*",
                cdm_target=f"candidate:cdm.{source_type}",
                bundle_usage=source_type,
                qc_family="unverified",
                transform_authority=authority,
                status=status,
                evidence=evidence,
            )
        )
    return tuple(rows)


def write_coverage_report(
    output: Path, contracts: tuple[CoverageContract, ...], report_format: str
) -> None:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if output.exists():
        raise IngestError(ErrorKind.CONFIGURATION, "coverage_output_exists")
    rows = [
        {**asdict(contract), "status": contract.status.value} for contract in contracts
    ]
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(output, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            if report_format == "json":
                json.dump(rows, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            elif report_format == "csv":
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            else:
                raise IngestError(ErrorKind.CONFIGURATION, "coverage_format")
    except Exception:
        output.unlink(missing_ok=True)
        raise


if len(_BUNDLE_SOURCE_TYPES) != 53:  # pragma: no cover - import-time invariant
    raise RuntimeError("bundle coverage catalog must contain 53 source types")
