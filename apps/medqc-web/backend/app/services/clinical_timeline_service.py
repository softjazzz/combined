"""诊断及手术操作时间轴服务。

该服务用于 3.4.3 的确定性基础能力：从已组装的病历 bundle 中提取
诊断出现证据、手术计划证据和手术执行证据，不调用 LLM，不写正式首页。
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

from app.schemas.clinical_timeline import (
    ClinicalCompletenessIssue,
    ClinicalEvidence,
    ClinicalTimeline,
    DiagnosisStatus,
    DiagnosisTimelineItem,
    ProcedureStatus,
    ProcedureTimelineItem,
)


DIAGNOSIS_LABEL_PATTERN = re.compile(
    r"(?:入院诊断|初步诊断|出院诊断|主要诊断|诊断)[:：]\s*([^\n。；;]+)"
)
ICD10_PATTERN = re.compile(r"([A-Z]\d{2}(?:\.[0-9xX]{1,7})?)")
ICD9_PATTERN = re.compile(r"(\d{2}\.\d{2,4}(?:x\d{3})?)", re.IGNORECASE)
PROCEDURE_LABEL_PATTERN = re.compile(
    r"(?:手术名称|手术操作|拟行|计划行|建议行|行)[:：]?\s*([^\n。；;]*?(?:术|操作|治疗))"
)
PROCEDURE_NAME_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9（）()、+\-]{2,40}(?:术|操作|治疗))")

PLAN_DOC_HINTS = ("presurg", "pre_surg", "术前", "计划", "讨论", "审批", "医嘱")
EXECUTION_DOC_HINTS = ("surgery_record", "anesthesia", "postsurg", "手术记录", "麻醉", "术后")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_time(doc: dict[str, Any]) -> str:
    for key in ("record_time", "display_time", "document_time", "create_time", "update_time"):
        value = _text(doc.get(key))
        if value:
            return value
    return ""


def _document_text(doc: dict[str, Any]) -> str:
    for key in ("content", "record_content", "text", "assembled_text", "text_preview"):
        value = _text(doc.get(key))
        if value:
            return value
    sections = doc.get("sections")
    if isinstance(sections, list):
        chunks = []
        for section in sections:
            if isinstance(section, dict):
                chunks.append(_text(section.get("content") or section.get("text")))
        return "\n".join(chunk for chunk in chunks if chunk)
    return ""


def _doc_type(doc: dict[str, Any]) -> str:
    return _text(doc.get("document_type") or doc.get("__document_type") or doc.get("source_table"))


def _doc_title(doc: dict[str, Any]) -> str:
    return _text(doc.get("document_title") or doc.get("title") or _doc_type(doc))


def _clean_name(raw: str) -> str:
    value = re.sub(r"\s+", "", _text(raw))
    value = re.sub(r"^[：:，,、\s]+", "", value)
    value = re.sub(r"[，,、；;。].*$", "", value)
    value = re.sub(ICD10_PATTERN, "", value)
    value = re.sub(ICD9_PATTERN, "", value)
    return value.strip("：:，,、；;。 ")


def _split_diagnosis_names(raw: str) -> list[str]:
    names = []
    for part in re.split(r"[，,、；;]", raw):
        name = _clean_name(part)
        if name and len(name) >= 2 and "诊断" not in name:
            names.append(name)
    return names


def _normalize_procedure_name(name: str) -> str:
    value = _clean_name(name)
    value = value.replace("腹腔镜下", "").replace("经皮", "")
    value = value.replace("＋", "+")
    return value


def _status_from_text(text: str, doc_type: str, title: str) -> str:
    combined = f"{doc_type} {title} {text}"
    if any(token in combined for token in ("排除", "不考虑", "未支持")):
        return "ruled_out"
    if any(token in combined for token in ("出院诊断", "确诊", "诊断明确", "discharge")):
        return "confirmed"
    return "suspected"


def _is_plan_doc(doc_type: str, title: str) -> bool:
    combined = f"{doc_type} {title}".lower()
    return any(token.lower() in combined for token in PLAN_DOC_HINTS)


def _is_execution_doc(doc_type: str, title: str) -> bool:
    combined = f"{doc_type} {title}".lower()
    return any(token.lower() in combined for token in EXECUTION_DOC_HINTS)


def _match_key(name: str) -> str:
    value = _normalize_procedure_name(name)
    value = value.replace("急性", "").replace("慢性", "")
    return re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", value).lower()


def _matches_any(name: str, candidates: list[str]) -> bool:
    key = _match_key(name)
    if not key:
        return False
    for candidate in candidates:
        candidate_key = _match_key(candidate)
        if not candidate_key:
            continue
        if key == candidate_key or key in candidate_key or candidate_key in key:
            return True
    return False


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = _text(value)
        if not normalized:
            continue
        key = _match_key(normalized)
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _diag_name_from_frontpage(item: dict[str, Any]) -> str:
    return _text(item.get("name") or item.get("diagnosis_name") or item.get("main_diagnosis_name"))


def _procedure_name_from_frontpage(item: dict[str, Any]) -> str:
    return _text(item.get("name") or item.get("operation_name") or item.get("procedure_name") or item.get("surgery_name"))


class ClinicalTimelineService:
    """从病历 bundle 构建诊断/手术时间轴。"""

    def build_from_bundle(self, bundle: dict[str, Any], frontpage: dict[str, Any] | None = None) -> ClinicalTimeline:
        documents = self._collect_documents(bundle)
        diagnoses = self._extract_diagnoses(documents)
        procedures = self._extract_procedures(documents)
        frontpage_payload = frontpage if frontpage is not None else self._extract_frontpage_payload(bundle)
        issues = self.compare_with_frontpage(diagnoses, procedures, frontpage_payload)
        flags = []
        if not documents:
            flags.append("missing_source_documents")
        if not diagnoses:
            flags.append("no_diagnosis_evidence")
        return ClinicalTimeline(
            visit_id=_text(bundle.get("visit_id")),
            diagnoses=diagnoses,
            procedures=procedures,
            issues=issues,
            data_quality_flags=flags,
        )

    def compare_with_frontpage(
        self,
        diagnoses: list[DiagnosisTimelineItem],
        procedures: list[ProcedureTimelineItem],
        frontpage: dict[str, Any] | None,
    ) -> list[ClinicalCompletenessIssue]:
        """对照时间轴证据和草稿首页字段，输出漏填/错填提示。"""
        if not frontpage:
            return []
        issues: list[ClinicalCompletenessIssue] = []
        frontpage_diagnoses = self._frontpage_diagnosis_names(frontpage)
        frontpage_procedures = self._frontpage_procedure_names(frontpage)

        for diagnosis in diagnoses:
            if diagnosis.status != "confirmed":
                continue
            if not _matches_any(diagnosis.diagnosis_name, frontpage_diagnoses):
                issues.append(ClinicalCompletenessIssue(
                    issue_type="missing_in_frontpage",
                    item_category="diagnosis",
                    item_name=diagnosis.diagnosis_name,
                    severity="warning",
                    suggestion=f"病历中已确认“{diagnosis.diagnosis_name}”，建议核对是否应补入病案首页诊断。",
                    evidence_summary=diagnosis.first_mention_source,
                ))

        timeline_diagnosis_names = [item.diagnosis_name for item in diagnoses if item.status != "ruled_out"]
        for name in frontpage_diagnoses:
            if not _matches_any(name, timeline_diagnosis_names):
                issues.append(ClinicalCompletenessIssue(
                    issue_type="not_supported_by_record",
                    item_category="diagnosis",
                    item_name=name,
                    severity="error",
                    suggestion=f"病案首页诊断“{name}”在病历时间轴中未找到明确支持证据，请复核。",
                    evidence_summary="frontpage_only",
                ))

        for procedure in procedures:
            if procedure.status in ("verified", "executed_only") and not _matches_any(
                procedure.procedure_name,
                frontpage_procedures,
            ):
                issues.append(ClinicalCompletenessIssue(
                    issue_type="missing_in_frontpage",
                    item_category="procedure",
                    item_name=procedure.procedure_name,
                    severity="warning",
                    suggestion=f"病历中存在已执行手术/操作“{procedure.procedure_name}”，建议核对是否应补入病案首页手术操作。",
                    evidence_summary=procedure.execution_source,
                ))
            if procedure.status == "planned_only":
                issues.append(ClinicalCompletenessIssue(
                    issue_type="inconsistent",
                    item_category="procedure",
                    item_name=procedure.procedure_name,
                    severity="warning",
                    suggestion=f"病历中仅见“{procedure.procedure_name}”计划，未找到执行记录，请确认是否取消或漏传手术记录。",
                    evidence_summary=procedure.plan_source,
                ))

        return issues

    def _collect_documents(self, bundle: dict[str, Any]) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        source_documents = bundle.get("source_documents")
        if isinstance(source_documents, list):
            docs.extend(doc for doc in source_documents if isinstance(doc, dict))
        document_hits = bundle.get("document_hits")
        if isinstance(document_hits, dict):
            for value in document_hits.values():
                if isinstance(value, list):
                    docs.extend(doc for doc in value if isinstance(doc, dict))
                elif isinstance(value, dict):
                    docs.append(value)
        return docs

    def _extract_frontpage_payload(self, bundle: dict[str, Any]) -> dict[str, Any] | None:
        for key in ("frontpage", "frontpage_draft", "case_front_page"):
            value = bundle.get(key)
            if isinstance(value, dict):
                return value
        structured_context = bundle.get("structured_context")
        if isinstance(structured_context, dict):
            for key in ("frontpage", "frontpage_draft", "frontpage_coding", "case_front_page"):
                value = structured_context.get(key)
                if isinstance(value, dict):
                    return value
        return None

    def _frontpage_diagnosis_names(self, frontpage: dict[str, Any]) -> list[str]:
        diagnoses = frontpage.get("diagnoses") or frontpage.get("diagnosis_list") or []
        names: list[str] = []
        if isinstance(diagnoses, list):
            for item in diagnoses:
                if isinstance(item, dict):
                    name = _diag_name_from_frontpage(item)
                    if name:
                        names.append(name)
                elif isinstance(item, str) and item.strip():
                    names.append(item.strip())
        for key in ("main_diagnosis", "primary_diagnosis", "diagnosis_name"):
            value = frontpage.get(key)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
            elif isinstance(value, dict):
                name = _diag_name_from_frontpage(value)
                if name:
                    names.append(name)
        return _dedupe(names)

    def _frontpage_procedure_names(self, frontpage: dict[str, Any]) -> list[str]:
        procedures = frontpage.get("surgeries") or frontpage.get("procedures") or frontpage.get("operations") or []
        names: list[str] = []
        if isinstance(procedures, list):
            for item in procedures:
                if isinstance(item, dict):
                    name = _procedure_name_from_frontpage(item)
                    if name:
                        names.append(name)
                elif isinstance(item, str) and item.strip():
                    names.append(item.strip())
        for key in ("main_surgery", "primary_surgery", "main_procedure", "operation_name"):
            value = frontpage.get(key)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
            elif isinstance(value, dict):
                name = _procedure_name_from_frontpage(value)
                if name:
                    names.append(name)
        return _dedupe(names)

    def _extract_diagnoses(self, documents: Iterable[dict[str, Any]]) -> list[DiagnosisTimelineItem]:
        evidence_by_name: dict[str, list[ClinicalEvidence]] = defaultdict(list)
        for doc in documents:
            content = _document_text(doc)
            if not content:
                continue
            doc_type = _doc_type(doc)
            title = _doc_title(doc)
            for match in DIAGNOSIS_LABEL_PATTERN.finditer(content):
                raw = match.group(1)
                code_match = ICD10_PATTERN.search(raw)
                code = code_match.group(1).upper() if code_match else ""
                for name in _split_diagnosis_names(raw):
                    evidence_by_name[name].append(
                        ClinicalEvidence(
                            kind="diagnosis",
                            name=name,
                            code=code,
                            record_time=_source_time(doc),
                            source_doc_type=doc_type,
                            source_title=title,
                            status=_status_from_text(content, doc_type, title),
                            evidence=match.group(0)[:240],
                        )
                    )
        return [self._build_diagnosis_item(name, evidence) for name, evidence in sorted(evidence_by_name.items())]

    def _build_diagnosis_item(self, name: str, evidence: list[ClinicalEvidence]) -> DiagnosisTimelineItem:
        ordered = sorted(evidence, key=lambda item: item.record_time or "9999")
        confirmed = [item for item in ordered if item.status == "confirmed"]
        ruled_out = [item for item in ordered if item.status == "ruled_out"]
        status: DiagnosisStatus = "confirmed" if confirmed else "ruled_out" if ruled_out else "suspected"
        first = ordered[0]
        code = next((item.code for item in ordered if item.code), "")
        return DiagnosisTimelineItem(
            diagnosis_name=name,
            icd_code=code,
            first_mention_time=first.record_time,
            first_mention_source=first.source_title or first.source_doc_type,
            status=status,
            evidence=ordered,
        )

    def _extract_procedures(self, documents: Iterable[dict[str, Any]]) -> list[ProcedureTimelineItem]:
        plan_by_name: dict[str, list[ClinicalEvidence]] = defaultdict(list)
        execution_by_name: dict[str, list[ClinicalEvidence]] = defaultdict(list)
        for doc in documents:
            content = _document_text(doc)
            if not content:
                continue
            doc_type = _doc_type(doc)
            title = _doc_title(doc)
            candidates = self._procedure_candidates(content)
            if not candidates:
                continue
            is_plan = _is_plan_doc(doc_type, title) or "拟行" in content or "计划行" in content
            is_execution = _is_execution_doc(doc_type, title) or "手术经过" in content or "已行" in content
            for raw_name, raw_evidence in candidates:
                name = _normalize_procedure_name(raw_name)
                if not name:
                    continue
                code_match = ICD9_PATTERN.search(raw_evidence)
                evidence = ClinicalEvidence(
                    kind="procedure",
                    name=name,
                    code=code_match.group(1) if code_match else "",
                    record_time=_source_time(doc),
                    source_doc_type=doc_type,
                    source_title=title,
                    status="executed" if is_execution else "planned",
                    evidence=raw_evidence[:240],
                )
                if is_plan:
                    plan_by_name[name].append(evidence)
                if is_execution or not is_plan:
                    execution_by_name[name].append(evidence)

        names = sorted(set(plan_by_name) | set(execution_by_name))
        return [
            self._build_procedure_item(name, plan_by_name.get(name, []), execution_by_name.get(name, []))
            for name in names
        ]

    def _procedure_candidates(self, content: str) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []
        for line in content.splitlines() or [content]:
            for match in PROCEDURE_LABEL_PATTERN.finditer(line):
                candidates.append((match.group(1), line))
        if candidates:
            return candidates
        for line in content.splitlines():
            if not any(token in line for token in ("手术", "操作", "PCI", "支架", "切除")):
                continue
            for match in PROCEDURE_NAME_PATTERN.finditer(line):
                candidates.append((match.group(1), line))
        return candidates

    def _build_procedure_item(
        self,
        name: str,
        plan_evidence: list[ClinicalEvidence],
        execution_evidence: list[ClinicalEvidence],
    ) -> ProcedureTimelineItem:
        plans = sorted(plan_evidence, key=lambda item: item.record_time or "9999")
        executions = sorted(execution_evidence, key=lambda item: item.record_time or "9999")
        if plans and executions:
            status: ProcedureStatus = "verified"
        elif plans:
            status = "planned_only"
        else:
            status = "executed_only"
        code = next((item.code for item in [*executions, *plans] if item.code), "")
        first_plan = plans[0] if plans else None
        first_execution = executions[0] if executions else None
        return ProcedureTimelineItem(
            procedure_name=name,
            icd9_code=code,
            plan_time=first_plan.record_time if first_plan else "",
            plan_source=(first_plan.source_title or first_plan.source_doc_type) if first_plan else "",
            execution_time=first_execution.record_time if first_execution else "",
            execution_source=(first_execution.source_title or first_execution.source_doc_type) if first_execution else "",
            status=status,
            evidence=[*plans, *executions],
        )
