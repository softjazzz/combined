"""特殊病历只读报表：完整出院队列、重叠分类、权威确认自动缺陷。"""

import csv
import io
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from ..database.connection import SessionLocal
from . import record_quality_report_service as base
from . import special_record_report_source_service as source

HOSPITAL_TZ = timezone(timedelta(hours=8))
MAX_CASES = 5000


def load_cohort(*, discharged_from, discharged_to, department, institute_id):
    from .case_scope_service import CaseScopeService

    rows = []
    start = discharged_from
    owner = CaseScopeService()
    while start <= discharged_to:
        end = min(start + timedelta(days=30), discharged_to)
        result = owner.resolve_hospitalization_scope(
            scope_mode="discharged",
            as_of_date=datetime.now(HOSPITAL_TZ).date(),
            admission_start_date=None,
            discharge_start_date=start,
            discharge_end_date=end,
            departments=[department] if department else [],
            institute_id=institute_id,
        )
        if result.source_status != "ready" or len(result.case_refs) != len(
            result.selected
        ):
            raise RuntimeError("出院队列来源不完整")
        for ref, row in zip(result.case_refs, result.selected):
            if tuple(row.get(field) for field in source.COORDINATES) != (
                ref.institute_id,
                ref.patient_id,
                ref.visit_id,
            ):
                raise RuntimeError("出院队列身份不一致")
            rows.append(row)
        if len(rows) > MAX_CASES:
            raise source.SpecialReportInvalid("出院队列超过5000例，请缩小范围")
        start = end + timedelta(days=1)
    return rows


def score_cases(results):
    from .special_report_scoring_service import score_special_report_cases

    return score_special_report_cases(results)


class SpecialRecordReportService:
    def __init__(
        self,
        *,
        session_factory=SessionLocal,
        cohort_loader=load_cohort,
        results_loader=base._default_results_loader,
        projector=base._default_projector,
        scorer=score_cases,
        version_loader=base._default_version_loader,
        rule_meta_loader=base._default_rule_meta_loader,
    ):
        self.sessions = session_factory
        self.cohort_loader = cohort_loader
        self.results_loader = results_loader
        self.projector = projector
        self.scorer = scorer
        self.version_loader = version_loader
        self.rule_meta_loader = rule_meta_loader

    def report(
        self,
        actor_id,
        *,
        institute_id,
        discharged_from,
        discharged_to,
        department=None,
        record_type=None,
        record_type_state="positive",
        grade=None,
        rule_id=None,
    ):
        if (
            not isinstance(discharged_from, date)
            or not isinstance(discharged_to, date)
            or isinstance(discharged_from, datetime)
            or isinstance(discharged_to, datetime)
            or discharged_from > discharged_to
            or (discharged_to - discharged_from).days > 365
            or discharged_to > datetime.now(HOSPITAL_TZ).date()
        ):
            raise source.SpecialReportInvalid(
                "出院日期须为不超过366天且不晚于医院今天的完整日期窗"
            )
        if record_type is not None and record_type not in source.TYPES:
            raise source.SpecialReportInvalid("特殊病历类型无效")
        if record_type_state not in {"positive", "negative", "unknown"}:
            raise source.SpecialReportInvalid("类型状态无效")
        with self.sessions() as session:
            institute_id = source.authorize(session, actor_id, institute_id)
            configuration = source.config_in_session(session, institute_id)
        raw_cohort = self.cohort_loader(
            discharged_from=discharged_from,
            discharged_to=discharged_to,
            department=department,
            institute_id=institute_id,
        )
        cohort = {}
        for row in raw_cohort:
            identity = tuple(
                str(row.get(field) or "").strip() for field in source.COORDINATES
            )
            if not all(identity):
                raise RuntimeError("出院队列身份不完整")
            if identity[0] != institute_id:
                continue
            if department and row.get("department") != department:
                continue
            discharge = row.get("discharge_time")
            if (
                row.get("hospitalization_status") != "discharged"
                or not isinstance(discharge, datetime)
                or not discharged_from
                <= (
                    discharge.astimezone(HOSPITAL_TZ) if discharge.tzinfo else discharge
                ).date()
                <= discharged_to
                or identity in cohort
            ):
                raise RuntimeError("出院队列重复或状态/日期不一致")
            cohort[identity] = row
        if len(cohort) > MAX_CASES:
            raise source.SpecialReportInvalid("出院队列超过5000例，请缩小范围")
        with self.sessions() as session:
            sources = source.load_sources(session, cohort)
        raw_results = (
            self.results_loader(
                [dict(zip(source.COORDINATES, identity)) for identity in cohort]
            )
            if cohort
            else {}
        )
        if not isinstance(raw_results, dict):
            raise RuntimeError("质控结果回执无效")
        rule_metadata = self.rule_meta_loader()
        score_inputs, defects_by_case = {}, {}
        unavailable = set()
        versions = {}
        for identity, record in cohort.items():
            raw = raw_results.get(identity)
            raw = raw if isinstance(raw, dict) else {}
            valid = (
                raw.get("status") == "ready"
                and isinstance(raw.get("items"), list)
                and raw.get("envelope_id")
                and raw.get("rule_set_version")
                and raw.get("rule_set_key") == "luxian_0609_qc_v1"
            )
            items = self.projector(raw["items"]) if valid else None
            if valid and (
                not isinstance(items, list)
                or any(
                    not isinstance(item, dict)
                    or not isinstance(item.get("rule_id"), str)
                    or not item["rule_id"].strip()
                    or not isinstance(item.get("is_confirmed_issue"), bool)
                    for item in items
                )
                or len({item["rule_id"] for item in items}) != len(items)
            ):
                valid, items = False, None
            if not valid:
                unavailable.add(identity)
            score_inputs[identity] = {
                **raw,
                "items": items,
                "department_name": record.get("department"),
            }
            defects_by_case[identity] = []
            if valid:
                version = (raw["rule_set_key"], raw["rule_set_version"])
                if version not in versions:
                    resolved = self.version_loader(*version)
                    entries = resolved.get("entries", []) if resolved else []
                    if not isinstance(entries, list):
                        raise RuntimeError("冻结规则分类来源无效")
                    versions[version] = {
                        item["rule_id"]: item for item in entries if item.get("rule_id")
                    }
                for item in items:
                    if item.get("is_confirmed_issue") is True:
                        rid = item.get("rule_id")
                        meta = versions[version].get(rid, {})
                        display = rule_metadata.get(rid, {})
                        name = item.get("rule_name")
                        if not name or name == rid:
                            name = display.get("rule_name") or rid
                        defects_by_case[identity].append(
                            {
                                "rule_id": rid,
                                "name": name,
                                "severity": meta.get("reminder_level")
                                or display.get("defect_level"),
                                "category": meta.get("defect_category"),
                                "type": meta.get("defect_type"),
                                "document": display.get("document"),
                            }
                        )
        scores, standard = self.scorer(score_inputs)
        rows = []
        for identity, record in cohort.items():
            raw = raw_results.get(identity)
            raw = raw if isinstance(raw, dict) else {}
            score = scores[identity]
            deductions = {
                item["rule_id"]: item for item in score.get("report_deductions") or []
            }
            for defect in defects_by_case[identity]:
                deduction = deductions.get(defect["rule_id"])
                defect["is_veto"] = deduction.get("is_veto") if deduction else None
            rows.append(
                {
                    **dict(zip(source.COORDINATES, identity)),
                    "patient_name": record.get("patient_name"),
                    "department": record.get("department"),
                    "discharged_at": (
                        record["discharge_time"].astimezone(HOSPITAL_TZ)
                        if record["discharge_time"].tzinfo
                        else record["discharge_time"].replace(tzinfo=HOSPITAL_TZ)
                    ).isoformat(),
                    "types": source.classify(
                        sources[identity], configuration["config"], record
                    ),
                    **score,
                    "historical_score": None,
                    "historical_grade": None,
                    "result_anchor": raw.get("envelope_id"),
                    "defects": defects_by_case[identity],
                    "defect_status": "unknown" if identity in unavailable else "known",
                }
            )
        rows.sort(
            key=lambda row: (row["discharged_at"], row["patient_id"], row["visit_id"]),
            reverse=True,
        )
        type_metrics = []
        for key, label in source.TYPES.items():
            counts = Counter(row["types"][key]["state"] for row in rows)
            type_metrics.append(
                {
                    "key": key,
                    "label": label,
                    "count": counts["positive"] if not counts["unknown"] else None,
                    "known_positive_total": counts["positive"],
                    "unknown_total": counts["unknown"],
                    "status": "known"
                    if not counts["unknown"]
                    else "partial"
                    if counts["positive"]
                    else "unknown",
                }
            )

        def selected(row):
            states = [value["state"] for value in row["types"].values()]
            state = (
                row["types"][record_type]["state"]
                if record_type
                else "positive"
                if "positive" in states
                else "unknown"
                if "unknown" in states
                else "negative"
            )
            return (
                state == record_type_state
                and (not grade or row["report_grade"] == grade)
                and (
                    not rule_id
                    or any(item["rule_id"] == rule_id for item in row["defects"])
                )
            )

        chosen = [row for row in rows if selected(row)]
        scored = [row for row in chosen if row["report_score_status"] == "scored"]
        grades = Counter(row["report_grade"] for row in scored)
        defects = aggregate_defects(chosen)
        departments = Counter(row["department"] or "未知科室" for row in chosen)
        return {
            "scope": {
                "institute_id": institute_id,
                "department": department,
                "discharged_from": discharged_from.isoformat(),
                "discharged_to": discharged_to.isoformat(),
                "timezone": "Asia/Shanghai",
                "archive_status": "unverified",
                "record_type": record_type,
                "record_type_state": record_type_state,
                "grade": grade,
                "rule_id": rule_id,
                "result_source": "luxian_0609_qc_v1",
                "defect_source": "confirmed_auto_only",
                "manual_status": "not_included",
                "type_count_basis": "complete_discharged_cohort",
                "metadata_source": "current_rule_catalog_display;classification_from_frozen_result_version",
                "classification_version_seq": configuration["version_seq"],
                "scoring_basis": "current_special_report_standard",
            },
            "summary": {
                "cohort_total": len(rows),
                "record_total": len(chosen),
                "unavailable_result_total": len(unavailable),
                "unknown_type_total": sum(
                    not any(f["state"] == "positive" for f in row["types"].values())
                    and any(f["state"] == "unknown" for f in row["types"].values())
                    for row in rows
                ),
                "unscored_total": len(chosen) - len(scored),
                "graded_total": len(scored),
                "ungraded_total": len(chosen) - len(scored),
                "grade_ratio_denominator": "graded_total",
                "known_result_total": sum(
                    row["defect_status"] == "known" for row in chosen
                ),
                "selected_unavailable_result_total": sum(
                    row["defect_status"] == "unknown" for row in chosen
                ),
                "defect_ratio_denominator": "confirmed_auto_defect_total",
            },
            "types": type_metrics,
            "top_departments": [
                {"name": name, "count": count}
                for name, count in sorted(
                    departments.items(), key=lambda pair: (-pair[1], pair[0])
                )[:5]
            ]
            if chosen
            else None,
            "grade_distribution": [
                {"grade": name, "count": count, "ratio": count / len(scored)}
                for name, count in sorted(grades.items())
            ]
            if scored
            else None,
            "top_defects": defects[:10]
            if any(row["defect_status"] == "known" for row in chosen)
            else None,
            "score_standard": standard,
            "_records": chosen,
            "_defects": defects,
        }


def aggregate_defects(rows):
    counts = {}
    for row in rows:
        for defect in row["defects"]:
            key = tuple(
                defect.get(field)
                for field in (
                    "rule_id",
                    "name",
                    "severity",
                    "category",
                    "type",
                    "document",
                    "is_veto",
                )
            )
            counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())
    fields = ("rule_id", "name", "severity", "category", "type", "document", "is_veto")
    return [
        {**dict(zip(fields, key)), "count": count, "ratio": count / total}
        for key, count in sorted(
            counts.items(), key=lambda pair: (-pair[1], str(pair[0]))
        )
    ]


def page(data, *, kind="records", page=1, page_size=20):
    if (
        kind not in {"records", "defects"}
        or isinstance(page, bool)
        or isinstance(page_size, bool)
        or page < 1
        or not 1 <= page_size <= 100
    ):
        raise source.SpecialReportInvalid("明细类型或分页参数无效")
    rows = data["_" + kind]
    start = (page - 1) * page_size
    return {
        "total": len(rows),
        "page": page,
        "page_size": page_size,
        "items": rows[start : start + page_size],
        "scope": data["scope"],
        "score_standard": data["score_standard"],
    }


def export_csv(data, *, kind="records"):
    if kind not in {"records", "defects", "summary"}:
        raise source.SpecialReportInvalid("导出类型无效")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    if kind == "summary":
        writer.writerow(["分区", "字段", "值"])
        for section in ("scope", "score_standard", "summary"):
            for key, value in data[section].items():
                writer.writerow(
                    [
                        section,
                        key,
                        base._csv_cell(value if value is not None else "未知"),
                    ]
                )
        for section in (
            "types",
            "top_departments",
            "grade_distribution",
            "top_defects",
        ):
            values = data[section]
            if values is None:
                writer.writerow([section, "状态", "未知"])
            else:
                for index, row in enumerate(values):
                    for key, value in row.items():
                        writer.writerow(
                            [
                                section,
                                f"{index + 1}.{key}",
                                base._csv_cell(value if value is not None else "未知"),
                            ]
                        )
        return ("\ufeff" + output.getvalue()).encode("utf-8")
    metadata_fields = (
        "scoring_purpose",
        "scoring_basis",
        "standard_id",
        "standard_version_seq",
        "binding_version_seq",
    )
    fields = (
        (
            "rule_id",
            "name",
            "severity",
            "category",
            "type",
            "document",
            "is_veto",
            "count",
            "ratio",
            *metadata_fields,
        )
        if kind == "defects"
        else (
            *source.COORDINATES,
            "patient_name",
            "department",
            "discharged_at",
            "report_score",
            "report_grade",
            "report_score_status",
            "reason_code",
            *metadata_fields,
            "historical_score",
            "historical_grade",
            "result_anchor",
            *source.TYPES,
        )
    )
    writer.writerow(fields)
    for row in data["_" + kind]:
        values = {
            **data["score_standard"],
            **row,
            "scoring_purpose": "special_report",
            "scoring_basis": data["scope"]["scoring_basis"],
        }
        writer.writerow(
            [
                base._csv_cell(
                    row["types"][field]["state"]
                    if field in source.TYPES
                    else values.get(field)
                )
                for field in fields
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")
