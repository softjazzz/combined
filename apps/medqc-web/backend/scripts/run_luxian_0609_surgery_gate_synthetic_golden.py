"""LX0609-024/025/033 合成 Golden 的无持久化真实模型验证。

每个场景只构造当前就诊、当前规则最小文书投影；脚本不访问数据库、
不创建任务或客户结果，也不输出病例正文、提示词、原始模型回复或坐标。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.llm_config_loader import build_adjudicator_runtime_config
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_surgery_gate_execution import (
    execute_luxian_0609_native_surgery_gate_rules,
)
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceQueryError
from app.services.qc_llm_client import SichuanQCLLMClient


@dataclass(frozen=True)
class Scenario:
    label: str
    rule_id: str
    expected: str
    surgery_text: str
    supplement_text: str = ""
    consent_text: str = ""
    consent_source_state: str = "available"


SCENARIOS = (
    Scenario(
        "golden-024-complete", "LX0609-024", "compliant",
        "本次已实施恶性肿瘤根治手术，术中完成区域淋巴结清扫并记录。",
    ),
    Scenario(
        "golden-024-missing-lymph", "LX0609-024", "non_compliant",
        "本次已实施恶性肿瘤根治手术；手术记录未记录淋巴结清扫。",
    ),
    Scenario(
        "golden-024-nonmalignant", "LX0609-024", "not_applicable",
        "本次已实施良性病变手术，明确不是恶性肿瘤手术。",
    ),
    Scenario(
        "golden-024-linkage-unclear", "LX0609-024", "data_gap",
        "本次已实施手术；病理性质待明确，无法判断是否属于恶性肿瘤手术。",
    ),
    Scenario(
        "golden-025-complete", "LX0609-025", "compliant",
        "本次手术实际永久植入人工关节假体；名称、类型、规格、材料、数量及条码均已记录。",
    ),
    Scenario(
        "golden-025-missing-field", "LX0609-025", "non_compliant",
        "本次手术实际永久植入人工关节假体；名称、类型、规格、材料、数量已记录，但未记录条码。",
    ),
    Scenario(
        "golden-025-explicit-none", "LX0609-025", "not_applicable",
        "本次手术明确未植入任何永久性植入物。",
    ),
    Scenario(
        "golden-025-generic-material", "LX0609-025", "data_gap",
        "手术中使用常规耗材，未说明是否实际永久植入。",
    ),
    Scenario(
        "golden-033-signed", "LX0609-033", "compliant",
        "本次已实施手术。",
        consent_text="本次手术知情同意书，关联本次手术；患者已签名，术者已签名。",
    ),
    Scenario(
        "golden-033-missing-patient-sign", "LX0609-033", "non_compliant",
        "本次已实施手术。",
        consent_text="本次手术知情同意书，关联本次手术；患者签名缺失，术者已签名。",
    ),
    Scenario(
        "golden-033-source-unproven", "LX0609-033", "data_gap",
        "本次已实施手术。",
        consent_source_state="empty",
    ),
    Scenario(
        "golden-033-source-error", "LX0609-033", "technical_error",
        "本次已实施手术。",
        consent_source_state="error",
    ),
)


def _session_for(scenario: Scenario):
    rows = {
        # 025/033 的现有 typed 旁路只在受控“已实施手术”事实成立后才允许
        # 进入裁剪模型；Golden 必须提供与生产合同一致的严格 +08 时间字段。
        "surgery_record": ({
            "record_content": scenario.surgery_text,
            "surgery_begin_time": "2026-07-20 08:00:00+08",
        },),
        "mr_surgery": ({"record_content": scenario.surgery_text},),
        "pathology_exam_master": ({"record_content": scenario.supplement_text},),
        "pathology_exam_report": ({"record_content": scenario.supplement_text},),
        "diagnosis": ({"record_content": scenario.supplement_text},),
        "surgery_inform_consent": (
            ({"record_content": scenario.consent_text},)
            if scenario.consent_source_state == "available" and scenario.consent_text
            else ()
        ),
    }

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        if (
            scenario.rule_id == "LX0609-033"
            and source_key == "surgery_inform_consent"
            and scenario.consent_source_state == "error"
        ):
            raise SourceEvidenceQueryError("SYNTHETIC_CONSENT_SOURCE_ERROR")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(scenario.rule_id,),
        institute_id="SYNTHETIC-I",
        patient_id="SYNTHETIC-P",
        visit_id=scenario.label,
        source_schema=None,
        created_at="2026-07-20T12:00:00+08:00",
        row_reader=reader,
    )


async def _run() -> dict[str, Any]:
    client = SichuanQCLLMClient(build_adjudicator_runtime_config())
    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        session = _session_for(scenario)
        started = perf_counter()
        result = await execute_luxian_0609_native_surgery_gate_rules(
            rule_ids=(scenario.rule_id,),
            decision_rule_ids=(scenario.rule_id,),
            wrapper_rules=[],
            evidence_payload={},
            institute_id="SYNTHETIC-I",
            patient_id="SYNTHETIC-P",
            visit_id=scenario.label,
            source_schema=None,
            llm_client=client,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        reduced = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=result.decisions,
            expected_rule_ids=(scenario.rule_id,),
            snapshot=session.snapshot,
        )
        actual = reduced[0].final_state.value
        result_repr = repr(result)
        privacy_safe = not any(
            marker in result_repr
            for marker in (
                scenario.surgery_text,
                scenario.supplement_text,
                scenario.consent_text,
                "SYNTHETIC-I",
                "SYNTHETIC-P",
                "2026-07-20",
                "SYNTHETIC_CONSENT_SOURCE_ERROR",
            )
            if marker
        )
        rows.append({
            "case": scenario.label,
            "rule_id": scenario.rule_id,
            "expected": scenario.expected,
            "actual": actual,
            "passed": actual == scenario.expected,
            "llm_calls": int(result.llm_call_count),
            "total_tokens": int(result.total_tokens),
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "privacy_safe": privacy_safe,
        })
    return {
        "schema_version": "lx0609-surgery-024-025-033-synthetic-golden-v1",
        "case_count": len(rows),
        "passed": sum(1 for row in rows if row["passed"]),
        "privacy_safe": all(row["privacy_safe"] for row in rows),
        "technical_error_count": sum(
            1 for row in rows if row["actual"] == "technical_error"
        ),
        "cases": rows,
    }


def main() -> int:
    try:
        report = asyncio.run(_run())
    except Exception:
        print("LX0609 surgery synthetic Golden failed safely", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0 if report["passed"] == report["case_count"] and report["privacy_safe"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
