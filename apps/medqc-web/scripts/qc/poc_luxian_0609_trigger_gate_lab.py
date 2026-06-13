from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.medical_records.detail_service import get_documents  # noqa: E402

from poc_luxian_0609_pack_strategy_lab import (  # noqa: E402
    DEFAULT_RULE_SET_KEY,
    DEFAULT_VISIT_ID,
    LabConfig,
    Luxian0609PackStrategyLab,
    _compact_rule_result,
    _load_customer_point_count,
    _rule_id,
    _safe_text,
)


DEFAULT_OUTPUT_DIR = ROOT / ".runtime-logs" / "qc-pack-poc"
SURGERY_EVENT_RULE_IDS = {
    "CL-108",
    "CL-173",
    "CL-181",
    "CL-208",
    "LX-019",
    "LX-020",
    "LX-022",
    "LX-025",
    "LX-026",
    "LX-027",
    "LXE-31",
    "LXE-33",
    "SC-082",
    "SC-083",
    "SC-087",
    "SC-090",
    "SC-095",
    "SC-096",
    "SC-098",
    "SC-100",
    "SC-101",
    "SC-102",
}
TRANSFUSION_EVENT_RULE_IDS = {
    "CL-255",
    "CL-256",
    "LX-018",
    "LXE-52",
    "SC-073",
    "SC-074",
    "SC-133",
    "SC-134",
}
CRITICAL_STATUS_RULE_IDS = {
    "CL-231",
    "SC-051",
    "SC-054",
}
PATHOLOGY_EVENT_RULE_IDS = {
    "SC-037",
    "SC-099",
}
ABNORMAL_LAB_RULE_IDS = {
    "CL-071",
    "LX-031",
    "LXE-24",
    "SC-114",
    "SC-138",
}
ABNORMAL_IMAGING_RULE_IDS = {
    "LXE-23",
}
EVENT_REQUIRED_RULE_IDS = {
    **{rule_id: "surgery_event" for rule_id in SURGERY_EVENT_RULE_IDS},
    **{rule_id: "transfusion_event" for rule_id in TRANSFUSION_EVENT_RULE_IDS},
    **{rule_id: "critical_status" for rule_id in CRITICAL_STATUS_RULE_IDS},
    **{rule_id: "pathology_event" for rule_id in PATHOLOGY_EVENT_RULE_IDS},
    **{rule_id: "abnormal_lab" for rule_id in ABNORMAL_LAB_RULE_IDS},
    **{rule_id: "abnormal_imaging" for rule_id in ABNORMAL_IMAGING_RULE_IDS},
}


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _clip(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _rule_text(rule: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "rule_id",
        "rule_code",
        "name",
        "rule_name",
        "description",
        "check_content",
        "applicable_documents",
        "rule_family",
    ):
        value = rule.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value or ""))
    return " ".join(parts).lower()


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _has_effective_text(value: Any) -> bool:
    text = re.sub(r"\s+", "", str(value or ""))
    if not text:
        return False
    label_chars = set("记录时间科室病房记录者手术医生签名术前小结手术项目编码等级医师助麻醉方式诊断经过切口愈合开始结束失血量其他内容:")
    non_label_chars = [char for char in text if char not in label_chars]
    return len(non_label_chars) >= 8


def _load_latest_baseline_report(output_dir: Path) -> Path | None:
    candidates = sorted(
        output_dir.glob("luxian_0609_pack_strategy_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "baseline_current" in dict(data.get("strategies") or {}):
            return path
    return None


def _result_map(strategy_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _safe_text(item.get("rule_id")).upper(): dict(item)
        for item in strategy_summary.get("rule_results") or []
        if _safe_text(item.get("rule_id"))
    }


@dataclass(frozen=True)
class TriggerFacts:
    has_effective_surgery: bool
    has_empty_shell_surgery_record: bool
    has_transfusion_event: bool
    has_critical_status: bool
    has_pathology_event: bool
    has_abnormal_lab_signal: bool
    has_abnormal_imaging_signal: bool
    evidence: dict[str, str]


@dataclass(frozen=True)
class GateDecision:
    rule_id: str
    gate_family: str
    action: str
    status: str
    reason: str
    evidence: str


class Luxian0609TriggerGateLab(Luxian0609PackStrategyLab):
    def load_document_bundle(self) -> dict[str, Any]:
        return get_documents(self.config.visit_id)

    @staticmethod
    def build_trigger_facts(record: dict[str, Any], document_bundle: dict[str, Any]) -> TriggerFacts:
        medical_text = _safe_text(record.get("medical_text") or record.get("content"))
        documents = list(document_bundle.get("documents") or [])
        docs_by_type: dict[str, list[dict[str, Any]]] = {}
        for doc in documents:
            docs_by_type.setdefault(str(doc.get("type") or ""), []).append(dict(doc))

        surgery_docs = docs_by_type.get("surgery_record") or []
        effective_surgery_docs = [
            doc
            for doc in surgery_docs
            if bool(doc.get("has_content") is True)
            and _has_effective_text(doc.get("content") or doc.get("raw_text") or doc.get("text"))
        ]
        empty_shell_surgery = bool(surgery_docs) and not effective_surgery_docs

        transfusion_docs = [
            doc
            for doc_type in ("bloodtrans_record", "blood_application", "mr_bloodtrans")
            for doc in docs_by_type.get(doc_type, [])
            if bool(doc.get("has_content") is True)
        ]
        transfusion_text = " ".join(str(doc.get("content") or doc.get("raw_text") or "") for doc in transfusion_docs)
        transfusion_signal_text = transfusion_text or medical_text
        negated_transfusion_only = "否认输血史" in transfusion_signal_text and not _contains_any(
            transfusion_signal_text,
            ("输血记录", "输血医嘱", "输血申请", "红细胞", "血浆", "血小板", "输注"),
        )

        critical_signal = _contains_any(medical_text, ("病危", "病重", "危重", "抢救记录", "抢救医嘱"))
        pathology_signal = _contains_any(medical_text, ("病理报告", "病理检查", "病理诊断", "病理标本", "病理取材", "送病理"))
        lab_signal = _contains_any(medical_text, ("血常规", "肾功", "肌酐", "尿素", "细菌培养", "金黄色葡萄球菌", "mrsa", "异常"))
        imaging_signal = _contains_any(medical_text, ("ct", "mri", "螺旋ct", "彩超", "dr正侧位", "影像"))

        evidence = {
            "surgery_event": "手术记录为空壳；未见本次住院有效手术名称、手术时间或手术经过。"
            if empty_shell_surgery
            else ("存在有效手术记录。" if effective_surgery_docs else "未见本次住院有效手术事件。"),
            "transfusion_event": "入院记录仅见“否认输血史”，未见本次住院输血医嘱、输血记录或输血申请。"
            if negated_transfusion_only
            else ("存在输血相关文书或输血关键词。" if transfusion_docs else "未见本次住院输血事件。"),
            "critical_status": "病历文本未见病危/病重医嘱、告知或抢救状态。"
            if not critical_signal
            else "病历文本存在病危/病重/抢救相关信号。",
            "pathology_event": "未见病理申请、病理报告或手术取材；细菌培养不作为病理触发。"
            if not pathology_signal
            else "病历文本存在病理或取材相关信号。",
            "abnormal_lab": "病程/会诊中存在肾功异常、细菌培养阳性等检验信号。"
            if lab_signal
            else "未见明确异常检验信号。",
            "abnormal_imaging": "病程/查房中存在 CT、彩超、DR 等检查影像信号。"
            if imaging_signal
            else "未见明确影像检查信号。",
        }
        return TriggerFacts(
            has_effective_surgery=bool(effective_surgery_docs),
            has_empty_shell_surgery_record=empty_shell_surgery,
            has_transfusion_event=bool(transfusion_docs) or (
                not negated_transfusion_only
                and _contains_any(transfusion_signal_text, ("输血记录", "输血医嘱", "输血申请", "红细胞", "血浆", "血小板", "输注"))
            ),
            has_critical_status=critical_signal,
            has_pathology_event=pathology_signal,
            has_abnormal_lab_signal=lab_signal,
            has_abnormal_imaging_signal=imaging_signal,
            evidence=evidence,
        )

    @staticmethod
    def classify_gate_family(rule: dict[str, Any]) -> str:
        rid = _rule_id(rule)
        if rid in EVENT_REQUIRED_RULE_IDS:
            return EVENT_REQUIRED_RULE_IDS[rid]
        text = _rule_text(rule)
        if _contains_any(text, ("细菌培养", "检验", "危急值", "血常规", "肾功", "肌酐")):
            return "abnormal_lab"
        if _contains_any(text, ("ct", "mri", "影像", "检查结果")):
            return "abnormal_imaging"
        return "general"

    @staticmethod
    def decide_gate(rule: dict[str, Any], facts: TriggerFacts) -> GateDecision:
        rid = _rule_id(rule)
        family = Luxian0609TriggerGateLab.classify_gate_family(rule)
        action = "pass_to_llm"
        status = "pass_to_llm"
        reason = "规则不属于当前硬门控拦截范围，或触发事件已存在。"
        evidence = "保留进入 LLM pack。"

        if family == "surgery_event" and not facts.has_effective_surgery:
            action = "not_applicable"
            status = "not_applicable"
            reason = "未发现本次住院有效手术事件，手术/麻醉/术后规则不得交给 LLM 自由推断缺陷。"
            evidence = facts.evidence["surgery_event"]
        elif family == "transfusion_event" and not facts.has_transfusion_event:
            action = "not_applicable"
            status = "not_applicable"
            reason = "未发现本次住院输血事件，输血规则不适用。"
            evidence = facts.evidence["transfusion_event"]
        elif family == "critical_status" and not facts.has_critical_status:
            action = "not_applicable"
            status = "not_applicable"
            reason = "未发现病危/病重/抢救触发状态，危重相关规则不适用。"
            evidence = facts.evidence["critical_status"]
        elif family == "pathology_event" and not facts.has_pathology_event:
            action = "not_applicable"
            status = "not_applicable"
            reason = "未发现病理申请、病理报告或手术取材，病理记录规则不适用。"
            evidence = facts.evidence["pathology_event"]
        elif family == "abnormal_lab":
            evidence = facts.evidence["abnormal_lab"]
            if not facts.has_abnormal_lab_signal:
                action = "not_applicable"
                status = "not_applicable"
                reason = "未发现异常检验或阳性培养触发信号。"
            else:
                reason = "发现异常检验/阳性培养触发信号，需要进入 LLM 判断病程分析处理是否充分。"
        elif family == "abnormal_imaging":
            evidence = facts.evidence["abnormal_imaging"]
            if not facts.has_abnormal_imaging_signal:
                action = "not_applicable"
                status = "not_applicable"
                reason = "未发现影像阳性或重要检查触发信号。"
            else:
                reason = "发现影像/检查触发信号，需要进入 LLM 判断病程记录是否反映和分析。"

        return GateDecision(
            rule_id=rid,
            gate_family=family,
            action=action,
            status=status,
            reason=reason,
            evidence=evidence,
        )

    @staticmethod
    def build_gate_result(rule: dict[str, Any], decision: GateDecision, strategy_name: str) -> dict[str, Any]:
        return {
            "rule_id": decision.rule_id,
            "rule_name": _safe_text(rule.get("name") or rule.get("rule_name") or rule.get("description")),
            "status": decision.status,
            "is_compliant": True,
            "confidence": 0.99,
            "findings": decision.reason,
            "evidence": decision.evidence,
            "suggestion": "本次未触发该规则；无需进入 LLM 判断缺陷。",
            "metadata": {
                "strategy": strategy_name,
                "trigger_gate": True,
                "gate_family": decision.gate_family,
                "gate_action": decision.action,
                "gate_reason": decision.reason,
                "bucket_key": f"trigger_gate::{decision.gate_family}",
                "pack_id": "trigger_gate",
                "pack_size": 0,
                "pack_fallback": False,
            },
        }

    def build_gate_plan(self, rules: list[dict[str, Any]], facts: TriggerFacts) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        pass_rules: list[dict[str, Any]] = []
        gated_results: list[dict[str, Any]] = []
        gate_rows: list[dict[str, Any]] = []

        for rule in rules:
            decision = self.decide_gate(rule, facts)
            gate_rows.append(
                {
                    "rule_id": decision.rule_id,
                    "rule_name": _safe_text(rule.get("name") or rule.get("rule_name") or rule.get("description")),
                    "gate_family": decision.gate_family,
                    "action": decision.action,
                    "status": decision.status,
                    "reason": decision.reason,
                    "evidence": decision.evidence,
                }
            )
            if decision.action == "pass_to_llm":
                pass_rules.append(rule)
            else:
                gated_results.append(self.build_gate_result(rule, decision, self.config.strategies[0]))
        return pass_rules, gated_results, gate_rows

    @staticmethod
    def merge_strategy_summary(
        *,
        strategy_name: str,
        llm_summary: dict[str, Any],
        gated_results: list[dict[str, Any]],
        original_llm_rule_count: int,
    ) -> dict[str, Any]:
        compact_gated = [_compact_rule_result(item) for item in gated_results]
        merged_rule_results = sorted(
            list(llm_summary.get("rule_results") or []) + compact_gated,
            key=lambda item: str(item.get("rule_id") or ""),
        )
        status_counter: Counter[str] = Counter()
        for item in merged_rule_results:
            status_counter[str(item.get("status") or "unknown")] += 1

        summary = dict(llm_summary)
        summary["strategy"] = f"trigger_gate_{strategy_name}"
        summary["base_strategy"] = strategy_name
        summary["trigger_gate_enabled"] = True
        summary["original_llm_rule_count"] = original_llm_rule_count
        summary["pass_to_llm_rule_count"] = int(llm_summary.get("llm_rule_count") or len(llm_summary.get("rule_results") or []))
        summary["gated_rule_count"] = len(gated_results)
        summary["final_result_count"] = len(merged_rule_results)
        summary["accepted_rule_count"] = len(merged_rule_results)
        summary["terminal_status_count"] = dict(status_counter)
        summary["rule_results"] = merged_rule_results
        return summary

    @staticmethod
    def compare_with_baseline(
        *,
        baseline_report_path: Path | None,
        baseline_strategy: str,
        merged_summary: dict[str, Any],
        gate_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if baseline_report_path is None or not baseline_report_path.exists():
            return {
                "baseline_report_path": None,
                "different_decision_count": 0,
                "impacted_gated_rule_count": 0,
                "differences": [],
            }

        baseline_report = json.loads(baseline_report_path.read_text(encoding="utf-8"))
        baseline_summary = dict((baseline_report.get("strategies") or {}).get(baseline_strategy) or {})
        baseline_map = _result_map(baseline_summary)
        merged_map = _result_map(merged_summary)
        gate_by_rule = {str(item.get("rule_id") or "").upper(): item for item in gate_rows}
        differences: list[dict[str, Any]] = []

        for rule_id in sorted(set(baseline_map) | set(merged_map)):
            left = baseline_map.get(rule_id)
            right = merged_map.get(rule_id)
            gate_row = gate_by_rule.get(rule_id) or {}
            if not right and gate_row.get("action") == "pass_to_llm":
                continue
            left_status = _safe_text((left or {}).get("status")) or "missing"
            right_status = _safe_text((right or {}).get("status")) or "missing"
            left_compliant = bool((left or {}).get("is_compliant") is True)
            right_compliant = bool((right or {}).get("is_compliant") is True)
            if (left_status, left_compliant) == (right_status, right_compliant):
                continue
            differences.append(
                {
                    "rule_id": rule_id,
                    "rule_name": _safe_text(((left or right or {}).get("rule_name"))),
                    "baseline_status": left_status,
                    "baseline_is_compliant": left_compliant,
                    "trigger_gate_status": right_status,
                    "trigger_gate_is_compliant": right_compliant,
                    "gate_action": gate_row.get("action") or "",
                    "gate_family": gate_row.get("gate_family") or "",
                    "baseline_findings": _clip((left or {}).get("findings"), 180),
                    "trigger_gate_findings": _clip((right or {}).get("findings"), 180),
                    "gate_reason": _clip(gate_row.get("reason"), 180),
                }
            )

        impacted = [item for item in differences if item.get("gate_action") and item.get("gate_action") != "pass_to_llm"]
        return {
            "baseline_report_path": str(baseline_report_path),
            "baseline_strategy": baseline_strategy,
            "different_decision_count": len(differences),
            "impacted_gated_rule_count": len(impacted),
            "differences": differences,
        }

    async def run_trigger_gate(self, baseline_report_path: Path | None, baseline_strategy: str) -> dict[str, Any]:
        started = time.perf_counter()
        self._record = self.load_record()
        document_bundle = self.load_document_bundle()
        facts = self.build_trigger_facts(self._record, document_bundle)
        rules, missing_configured_rule_ids = self.load_rules()
        program_rules, llm_rules, program_fallback_rule_ids = self.split_executor_types(rules)
        pass_rules, gated_results, gate_rows = self.build_gate_plan(llm_rules, facts)

        strategy_name = self.config.strategies[0]
        llm_summary = await self.run_strategy(strategy_name, pass_rules)
        llm_summary["llm_rule_count"] = len(pass_rules)
        merged_summary = self.merge_strategy_summary(
            strategy_name=strategy_name,
            llm_summary=llm_summary,
            gated_results=gated_results,
            original_llm_rule_count=len(llm_rules),
        )
        comparison = self.compare_with_baseline(
            baseline_report_path=baseline_report_path,
            baseline_strategy=baseline_strategy,
            merged_summary=merged_summary,
            gate_rows=gate_rows,
        )
        gate_counter = Counter(str(item.get("action") or "unknown") for item in gate_rows)
        family_counter = Counter(str(item.get("gate_family") or "unknown") for item in gate_rows)

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run": self.config.dry_run,
            "visit_id": self.config.visit_id,
            "rule_set_key": self.config.rule_set_key,
            "customer_qc_point_count": _load_customer_point_count(),
            "configured_execution_rule_count": len(rules) + len(missing_configured_rule_ids),
            "loaded_execution_rule_count": len(rules),
            "missing_configured_rule_ids": missing_configured_rule_ids,
            "llm_rule_count_before_gate": len(llm_rules),
            "program_rule_count": len(program_rules),
            "program_rule_ids": [_rule_id(rule) for rule in program_rules],
            "program_fallback_rule_ids": program_fallback_rule_ids,
            "pass_to_llm_rule_count": len(pass_rules),
            "gated_rule_count": len(gated_results),
            "gate_action_count": dict(gate_counter),
            "gate_family_count": dict(family_counter),
            "model": str(getattr(self.qc_service.client, "model", "") or ""),
            "record": {
                "visit_id": self._record.get("visit_id"),
                "patient_name": self._record.get("patient_name"),
                "department": self._record.get("department"),
                "scope": self._record.get("scope"),
                "medical_text_length": len(_safe_text(self._record.get("medical_text"))),
                "medical_text_source": self._record.get("medical_text_source"),
                "document_count": len([doc for doc in document_bundle.get("documents") or [] if doc.get("has_content") is True]),
            },
            "trigger_facts": {
                "has_effective_surgery": facts.has_effective_surgery,
                "has_empty_shell_surgery_record": facts.has_empty_shell_surgery_record,
                "has_transfusion_event": facts.has_transfusion_event,
                "has_critical_status": facts.has_critical_status,
                "has_pathology_event": facts.has_pathology_event,
                "has_abnormal_lab_signal": facts.has_abnormal_lab_signal,
                "has_abnormal_imaging_signal": facts.has_abnormal_imaging_signal,
                "evidence": facts.evidence,
            },
            "gate_rows": gate_rows,
            "strategies": {merged_summary["strategy"]: merged_summary},
            "baseline_comparison": comparison,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }


def render_markdown(report: dict[str, Any]) -> str:
    facts = report.get("trigger_facts") or {}
    comparison = report.get("baseline_comparison") or {}
    lines: list[str] = []
    lines.append("# 泸县0609 Trigger Gate 旁路 POC 报告")
    lines.append("")
    lines.append(f"- 生成时间：{report.get('generated_at')}")
    lines.append(f"- dry-run：{'是' if report.get('dry_run') else '否'}")
    lines.append(f"- 病历：`{report.get('visit_id')}`")
    lines.append(f"- 规则集：`{report.get('rule_set_key')}`")
    lines.append(f"- 模型：`{report.get('model') or '-'}`")
    lines.append(f"- LLM 规则数：{report.get('llm_rule_count_before_gate')}")
    lines.append(f"- 进入 LLM：{report.get('pass_to_llm_rule_count')}")
    lines.append(f"- gate 拦截：{report.get('gated_rule_count')}")
    lines.append(f"- baseline 报告：`{comparison.get('baseline_report_path') or '-'}`")
    lines.append("")
    lines.append("## 触发事实")
    lines.append("")
    lines.append("| 触发族 | 是否存在 | 证据摘要 |")
    lines.append("| --- | --- | --- |")
    fact_rows = [
        ("surgery_event", facts.get("has_effective_surgery")),
        ("transfusion_event", facts.get("has_transfusion_event")),
        ("critical_status", facts.get("has_critical_status")),
        ("pathology_event", facts.get("has_pathology_event")),
        ("abnormal_lab", facts.get("has_abnormal_lab_signal")),
        ("abnormal_imaging", facts.get("has_abnormal_imaging_signal")),
    ]
    evidence = facts.get("evidence") or {}
    for key, exists in fact_rows:
        lines.append(f"| `{key}` | {'是' if exists else '否'} | {_clip(evidence.get(key), 120)} |")
    lines.append("")
    lines.append("## 门控分布")
    lines.append("")
    lines.append(f"- 动作分布：`{json.dumps(report.get('gate_action_count') or {}, ensure_ascii=False)}`")
    lines.append(f"- 规则族分布：`{json.dumps(report.get('gate_family_count') or {}, ensure_ascii=False)}`")
    lines.append("")
    lines.append("## 被 gate 拦截的规则")
    lines.append("")
    lines.append("| 规则 | 名称 | 规则族 | 状态 | 原因 | 证据 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    gated = [item for item in report.get("gate_rows") or [] if item.get("action") != "pass_to_llm"]
    if gated:
        for item in gated:
            lines.append(
                "| "
                f"{item.get('rule_id')} | {_clip(item.get('rule_name'), 34)} | `{item.get('gate_family')}` | "
                f"`{item.get('status')}` | {_clip(item.get('reason'), 80)} | {_clip(item.get('evidence'), 80)} |"
            )
    else:
        lines.append("| - | - | - | - | - | - |")
    lines.append("")
    lines.append("## 进入 LLM 的目标规则族")
    lines.append("")
    pass_rows = [item for item in report.get("gate_rows") or [] if item.get("action") == "pass_to_llm"]
    pass_counter = Counter(str(item.get("gate_family") or "unknown") for item in pass_rows)
    lines.append(f"- pass_to_llm 规则族：`{json.dumps(dict(pass_counter), ensure_ascii=False)}`")
    lines.append("")
    lines.append("## 与 baseline_current 的差异")
    lines.append("")
    lines.append(f"- 结论不同规则数：{comparison.get('different_decision_count')}")
    lines.append(f"- 其中 gate 直接影响规则数：{comparison.get('impacted_gated_rule_count')}")
    lines.append("")
    diffs = list(comparison.get("differences") or [])
    if diffs:
        lines.append("| 规则 | 名称 | baseline | trigger_gate | gate 动作 | 原因 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in diffs[:80]:
            lines.append(
                "| "
                f"{item.get('rule_id')} | {_clip(item.get('rule_name'), 32)} | `{item.get('baseline_status')}` | "
                f"`{item.get('trigger_gate_status')}` | `{item.get('gate_action') or '-'}` | {_clip(item.get('gate_reason') or item.get('trigger_gate_findings'), 90)} |"
            )
    else:
        lines.append("- 无可比较差异，或未找到 baseline 报告。")
    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- 本报告由旁路脚本生成，不创建正式任务，不写正式质控结果。")
    lines.append("- `not_applicable` 表示规则触发事件不存在；`pass_to_llm` 表示触发存在或当前 POC 不做硬拦截。")
    lines.append("- dry-run 模式不会调用模型，只验证门控计划和 baseline 受影响范围。")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    json_path = output_dir / f"luxian_0609_trigger_gate_{stamp}.json"
    md_path = output_dir / f"luxian_0609_trigger_gate_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def parse_args() -> tuple[LabConfig, Path | None, str]:
    parser = argparse.ArgumentParser(description="泸县0609质控 Trigger Gate 旁路 POC")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID)
    parser.add_argument("--rule-set-key", default=DEFAULT_RULE_SET_KEY)
    parser.add_argument("--strategy", default="baseline_current")
    parser.add_argument("--baseline-strategy", default="baseline_current")
    parser.add_argument("--baseline-report", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--low-confidence-threshold", type=float, default=0.45)
    parser.add_argument("--network-retry", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-rules", type=int, default=0, help="调试用；0 表示不限制规则数")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    baseline_report = Path(args.baseline_report) if str(args.baseline_report).strip() else _load_latest_baseline_report(output_dir)
    config = LabConfig(
        visit_id=str(args.visit_id),
        rule_set_key=str(args.rule_set_key),
        strategies=[str(args.strategy)],
        output_dir=output_dir,
        low_confidence_threshold=float(args.low_confidence_threshold),
        dry_run=bool(args.dry_run),
        max_rules=max(0, int(args.max_rules)),
        network_retry=max(0, int(args.network_retry)),
    )
    return config, baseline_report, str(args.baseline_strategy)


async def main_async() -> int:
    config, baseline_report, baseline_strategy = parse_args()
    lab = Luxian0609TriggerGateLab(config)
    report = await lab.run_trigger_gate(baseline_report, baseline_strategy)
    json_path, md_path = write_report(report, config.output_dir)
    print(f"Trigger Gate JSON: {json_path}")
    print(f"Trigger Gate Markdown: {md_path}")
    print(
        "gate: "
        f"pass_to_llm={report.get('pass_to_llm_rule_count')} "
        f"gated={report.get('gated_rule_count')} "
        f"baseline_diff={(report.get('baseline_comparison') or {}).get('different_decision_count')}"
    )
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
