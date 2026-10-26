"""核心制度专题：仅聚合冻结分类与权威客户可见问题，不判断医学事实。"""

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from ..database.connection import SessionLocal
from .defect_rectification_service import RectificationError, _person
from .medical_core_system_catalog import CORE_SYSTEM_IDS, CORE_SYSTEMS
from .record_quality_report_service import (
    MAX_REPORT_CASES,
    SCENE_SCOPES,
    SCENES,
    RecordQualityReportInvalid,
    RecordQualityReportTooLarge,
    _default_projector,
    _default_scope_loader,
)
from .rule_set_version_service import RuleSetVersionNotFound, resolve_rule_set_version
from .workstation.luxian_0609_result_analysis_service import (
    _as_utc,
    _parse_completed_at,
)

CONTRACT = "已配置质控点范围的问题率：分母为实际返回且冻结版本显式归属本制度的已质控病例，分子为其中至少一个权威确认问题的病例；不代表全院制度合规率。未知分类与不可用结果另列。"


def _results(refs):
    from .custom_qc_workspace_service import CustomQCWorkspaceService

    return CustomQCWorkspaceService(
        readonly=True
    ).build_luxian_0609_completed_record_result_summaries(
        record_refs=refs,
        include_items=True,
        include_rule_set_context=True,
    )


def reference():
    data = json.loads(
        (
            Path(__file__).parent / "resources" / "medical_core_systems_2018.json"
        ).read_text(encoding="utf-8")
    )
    if [(row["id"], row["name"]) for row in data["systems"]] != [
        (row["id"], row["name"]) for row in CORE_SYSTEMS
    ]:
        raise RuntimeError("制度参考目录不匹配")
    return data


class CoreSystemReportService:
    def __init__(
        self,
        session_factory=SessionLocal,
        scope_loader=_default_scope_loader,
        results_loader=_results,
        projector=_default_projector,
        version_resolver=resolve_rule_set_version,
    ):
        self.session_factory = session_factory
        self.scope_loader = scope_loader
        self.results_loader = results_loader
        self.projector = projector
        self.version_resolver = version_resolver

    def report(
        self,
        actor_id,
        *,
        scene="running",
        institute_id=None,
        department=None,
        doctor=None,
        completed_from=None,
        completed_to=None,
        system_id=None,
        rule_id=None,
        problems_only=False,
        page=1,
        page_size=20,
    ):
        if scene not in SCENES or (
            system_id and system_id not in CORE_SYSTEM_IDS | {"unknown"}
        ):
            raise RecordQualityReportInvalid("场景或制度无效")
        if page < 1 or not 1 <= page_size <= 100:
            raise RecordQualityReportInvalid("分页参数无效")
        start = _as_utc(completed_from) if completed_from else None
        end = _as_utc(completed_to) if completed_to else None
        if start and end and start > end:
            raise RecordQualityReportInvalid("完成时间起不能晚于止")
        with self.session_factory() as session:
            actor = _person(session, actor_id)
        if not actor["roles"] & {"admin", "qc_manager"}:
            raise RectificationError("无权读取制度专题报表", 403)
        if "admin" not in actor["roles"]:
            if not actor["institute_id"] or (
                institute_id and institute_id != actor["institute_id"]
            ):
                raise RectificationError("无权读取其他机构", 403)
            institute_id = actor["institute_id"]
        if department and not institute_id:
            raise RecordQualityReportInvalid("科室筛选须同时指定机构")
        records = self.scope_loader(
            department=department,
            doctor=doctor,
            hospital_status=SCENES[scene],
            institute_id=institute_id,
        )
        if not isinstance(records, list):
            raise RuntimeError("病历来源回执无效")
        identities = {}
        for record in records:
            identity = tuple(
                str(record.get(key) or "").strip()
                for key in ("institute_id", "patient_id", "visit_id")
            )
            if not all(identity):
                raise RuntimeError("病历来源身份不完整")
            if institute_id and identity[0] != institute_id:
                continue
            if department and record.get("department") != department:
                continue
            if doctor and record.get("attending_physician") != doctor:
                continue
            identities.setdefault(identity, record)
        if len(identities) > MAX_REPORT_CASES:
            raise RecordQualityReportTooLarge("候选病历超过5000例，请缩小范围")
        raw = (
            self.results_loader(
                [
                    dict(zip(("institute_id", "patient_id", "visit_id"), identity))
                    for identity in identities
                ]
            )
            if identities
            else {}
        )
        if not isinstance(raw, dict):
            raise RuntimeError("结果来源回执无效")
        versions = {}
        cases = []
        for identity, record in identities.items():
            result = raw.get(identity)
            row = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
            row.update(
                patient_name=record.get("patient_name") or "",
                department=record.get("department") or "",
                doctor=record.get("attending_physician") or "",
                completed_at=None,
                root_job_id=None,
                envelope_id=None,
                rule_set_key=None,
                rule_set_version=None,
                points=[],
                coverage="unavailable",
            )
            if not isinstance(result, dict) or result.get("status") != "ready":
                cases.append(row)
                continue
            completed = _parse_completed_at(result.get("completed_at"))
            if completed is None or not isinstance(result.get("items"), list):
                cases.append(row)
                continue
            if (start and completed < start) or (end and completed > end):
                continue
            for key in (
                "root_job_id",
                "envelope_id",
                "rule_set_key",
                "rule_set_version",
            ):
                row[key] = result.get(key) or None
            row["completed_at"] = completed.isoformat()
            version = (row["rule_set_key"], row["rule_set_version"])
            entries = None
            if all(version) and row["root_job_id"] and row["envelope_id"]:
                if version not in versions:
                    try:
                        resolution = self.version_resolver(*version)
                    except RuleSetVersionNotFound:
                        resolution = None
                    if resolution is not None:
                        if not isinstance(resolution.get("entries"), list):
                            raise RuntimeError("冻结分类来源回执无效")
                        classified = {}
                        for entry in resolution["entries"]:
                            rid = str(entry.get("rule_id") or "").strip().upper()
                            ids = entry.get("core_system_ids")
                            if (
                                not rid
                                or rid in classified
                                or (
                                    ids is not None
                                    and (
                                        not isinstance(ids, list)
                                        or any(
                                            value not in CORE_SYSTEM_IDS
                                            for value in ids
                                        )
                                    )
                                )
                            ):
                                raise RuntimeError("冻结分类来源回执无效")
                            classified[rid] = ids
                        versions[version] = classified
                    else:
                        versions[version] = None
                entries = versions[version]
            projected = self.projector(result["items"])
            if not isinstance(projected, list):
                raise RuntimeError("质控条目投影回执无效")
            seen = set()
            for point in projected:
                rid = str(point.get("rule_id") or "").strip().upper()
                if (
                    not rid
                    or rid in seen
                    or not isinstance(point.get("is_confirmed_issue"), bool)
                ):
                    raise RuntimeError("质控条目身份或确认状态无效")
                seen.add(rid)
                ids = entries.get(rid) if entries is not None else None
                row["points"].append(
                    {
                        "rule_id": rid,
                        "rule_name": str(
                            point.get("rule_name") or point.get("name") or rid
                        ),
                        "status": str(point.get("status") or "unknown"),
                        "is_confirmed_issue": point["is_confirmed_issue"],
                        "system_ids": ids,
                    }
                )
            row["coverage"] = (
                "unknown"
                if not projected or any(p["system_ids"] is None for p in row["points"])
                else "known"
            )
            cases.append(row)
        systems = []
        for system in CORE_SYSTEMS:
            relevant = [
                (
                    row,
                    [
                        p
                        for p in row["points"]
                        if p["system_ids"] and system["id"] in p["system_ids"]
                    ],
                )
                for row in cases
            ]
            relevant = [(row, points) for row, points in relevant if points]
            issues = sum(
                any(p["is_confirmed_issue"] for p in points) for _, points in relevant
            )
            defects = sum(
                p["is_confirmed_issue"] for _, points in relevant for p in points
            )
            points_by_version = {}
            for row, points in relevant:
                for point in points:
                    key = (
                        row["rule_set_key"],
                        row["rule_set_version"],
                        point["rule_id"],
                    )
                    bucket = points_by_version.setdefault(
                        key,
                        {
                            "rule_id": point["rule_id"],
                            "rule_name": point["rule_name"],
                            "system_ids": point["system_ids"],
                            "rule_set_key": key[0],
                            "rule_set_version": key[1],
                            "record_count": 0,
                            "problem_records": 0,
                        },
                    )
                    bucket["record_count"] += 1
                    bucket["problem_records"] += int(point["is_confirmed_issue"])
            systems.append(
                {
                    **system,
                    "record_count": len(relevant) or None,
                    "problem_records": issues if relevant else None,
                    "defect_total": defects if relevant else None,
                    "problem_rate": issues / len(relevant) if relevant else None,
                    "points": list(points_by_version.values()),
                }
            )
        selected = []
        for row in cases:
            points = row["points"]
            if system_id == "unknown":
                points = [p for p in points if p["system_ids"] is None]
                if not points and row["coverage"] == "known":
                    continue
            elif system_id:
                points = [
                    p
                    for p in points
                    if p["system_ids"] and system_id in p["system_ids"]
                ]
                if not points:
                    continue
            if rule_id:
                points = [p for p in points if p["rule_id"] == rule_id.strip().upper()]
                if not points:
                    continue
            if problems_only and not any(p["is_confirmed_issue"] for p in points):
                continue
            selected.append({**row, "points": points})
        ref = reference()
        return {
            "scene": scene,
            "scope": SCENE_SCOPES[scene],
            "contract": CONTRACT,
            "as_of": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "reference": ref,
            "systems": systems,
            "top_systems": [
                {
                    "id": system["id"],
                    "name": system["name"],
                    "defect_total": system["defect_total"],
                }
                for system in sorted(
                    (system for system in systems if system["defect_total"]),
                    key=lambda system: (-system["defect_total"], system["id"]),
                )[:20]
            ],
            "summary": {
                "candidate_records": len(cases),
                "unknown_records": sum(row["coverage"] == "unknown" for row in cases),
                "unavailable_records": sum(
                    row["coverage"] == "unavailable" for row in cases
                ),
                "unknown_points": sum(
                    p["system_ids"] is None for row in cases for p in row["points"]
                ),
                "unknown_defects": sum(
                    p["system_ids"] is None and p["is_confirmed_issue"]
                    for row in cases
                    for p in row["points"]
                ),
            },
            "items": selected[(page - 1) * page_size : page * page_size],
            "total": len(selected),
            "page": page,
            "page_size": page_size,
            "_export_rows": selected,
        }


def csv_export(data):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "统计口径",
            CONTRACT,
            "生成时间",
            data["as_of"],
            "制度原文版本",
            "2018-04-18参考",
        ]
    )
    writer.writerow(
        [
            "未知覆盖",
            "分类未知病例",
            data.get("summary", {}).get("unknown_records"),
            "结果不可用病例",
            data.get("summary", {}).get("unavailable_records"),
            "未知分类确认缺陷",
            data.get("summary", {}).get("unknown_defects", "未知"),
        ]
    )
    writer.writerow(
        [
            "制度汇总",
            "制度标识",
            "制度名称",
            "已配置点范围病例",
            "问题病例",
            "已配置质控点范围的问题率",
            "确认缺陷数",
        ]
    )
    for system in data.get("systems", []):
        writer.writerow(
            [
                "制度汇总",
                system["id"],
                system["name"],
                system["record_count"]
                if system["record_count"] is not None
                else "无配置数据",
                system["problem_records"]
                if system["problem_records"] is not None
                else "无配置数据",
                system["problem_rate"]
                if system["problem_rate"] is not None
                else "无配置数据",
                system.get("defect_total")
                if system.get("defect_total") is not None
                else "未知",
            ]
        )
    writer.writerow(
        [
            "机构",
            "患者标识",
            "就诊标识",
            "姓名",
            "科室",
            "主治医师",
            "完成时间",
            "运行",
            "结果",
            "规则集",
            "冻结版本",
            "覆盖",
            "质控点",
            "制度",
            "状态",
            "确认问题",
        ]
    )
    for row in data["_export_rows"]:
        for point in row["points"] or [{}]:
            values = [
                row[key]
                for key in (
                    "institute_id",
                    "patient_id",
                    "visit_id",
                    "patient_name",
                    "department",
                    "doctor",
                    "completed_at",
                    "root_job_id",
                    "envelope_id",
                    "rule_set_key",
                    "rule_set_version",
                    "coverage",
                )
            ]
            ids = point.get("system_ids")
            values.extend(
                [
                    point.get("rule_id"),
                    "未知" if ids is None else ";".join(ids) or "明确非核心",
                    point.get("status"),
                    point.get("is_confirmed_issue"),
                ]
            )
            writer.writerow(
                [
                    "'" + str(value)
                    if str(value).lstrip().startswith(("=", "+", "-", "@"))
                    or str(value).startswith(("\t", "\r", "\n"))
                    else value
                    for value in values
                ]
            )
    return "\ufeff" + output.getvalue()
