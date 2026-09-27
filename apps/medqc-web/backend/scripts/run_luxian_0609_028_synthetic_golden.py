"""LX0609-05-01-01 合成 Golden 无持久化烟测。

基于已验证的手术病例证据结构，在内存副本中注入预防抗菌药时间与语义，
调用当前配置的裁决模型做一次事实抽取，再由 Python 完成来源校验和时长判定。
脚本不查询或写入数据库，也不输出正文、时间或病例坐标。
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
from app.services.qc_llm_client import SichuanQCLLMClient


RULE_ID = "LX0609-05-01-01"


@dataclass(frozen=True)
class Scenario:
    label: str
    expected: str
    incision: str
    drug_text: str
    course_text: str = ""


SCENARIOS = (
    Scenario("golden-01-24h", "compliant", "I", "明确为围术期预防用药。2026-01-01 08:00实际首次给药，2026-01-02 08:00实际停止。"),
    Scenario("golden-02-24h01-no-reason", "non_compliant", "I", "明确为围术期预防用药。2026-01-01 08:00实际首次给药，2026-01-02 08:01实际停止。完整病程未记录延长用药的特殊理由。"),
    Scenario("golden-03-30h-with-reason", "compliant", "II", "明确为围术期预防用药。2026-01-01 08:00实际首次给药，2026-01-02 14:00实际停止。", "因术中污染风险增加，病程明确记录继续预防用药至术后30小时。"),
    Scenario("golden-04-48h-with-reason", "compliant", "II", "明确为围术期预防用药。2026-01-01 08:00实际首次给药，2026-01-03 08:00实际停止。", "因术中污染风险增加，病程明确记录特殊延长理由。"),
    Scenario("golden-05-30h-no-reason", "non_compliant", "I", "明确为围术期预防用药。2026-01-01 08:00实际首次给药，2026-01-02 14:00实际停止。完整病程未记录特殊延长理由。"),
    Scenario("golden-06-48h01", "non_compliant", "II", "明确为围术期预防用药。2026-01-01 08:00实际首次给药，2026-01-03 08:01实际停止。", "病程记录存在特殊延长理由。"),
    Scenario("golden-07-planned-only-time", "data_gap", "I", "计划于2026-01-01 08:00开始预防用药，计划于2026-01-02 08:00停药，尚无实际执行记录。"),
    Scenario("golden-08-conversion-separated", "compliant", "II", "围术期预防用药于2026-01-01 08:00实际首次给药，2026-01-01 20:00结束预防阶段。", "2026-01-01 20:00因明确感染转为治疗性抗菌药，治疗继续至2026-01-04 08:00；预防阶段与治疗阶段已明确分开。"),
    Scenario("golden-09-conversion-unsplittable", "data_gap", "II", "围术期开始使用抗菌药，后转治疗，总疗程至2026-01-04 08:00，但没有记录预防阶段停止或转换的准确时间。"),
    Scenario("golden-10-incision-other", "not_applicable", "III", "2026-01-01 08:00实际首次给药，2026-01-02 08:00实际停止。"),
)


def _session_for(scenario: Scenario):
    rows = {
        "surgery_record": ({
            "surgery_begin_time": "2026-01-01 07:30:00+08",
            "surgery_name": "本次已实施手术",
            "surgery_process": "手术已完成。",
        },),
        "mr_surgery": ({
            "surgery_name": "本次已实施手术",
            "surgial_incision_level": scenario.incision,
        },),
        "inpat_drug_order": ({"record_content": scenario.drug_text},),
        "daily_course_record": (
            ({"record_content": scenario.course_text},)
            if scenario.course_text
            else ()
        ),
    }

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE_ID,),
        institute_id="SYNTHETIC-I",
        patient_id="SYNTHETIC-P",
        visit_id=scenario.label,
        source_schema=None,
        created_at="2026-07-19T12:00:00+08:00",
        row_reader=reader,
    )


async def _run() -> dict[str, Any]:
    client = SichuanQCLLMClient(build_adjudicator_runtime_config())
    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        session = _session_for(scenario)
        started = perf_counter()
        result = await execute_luxian_0609_native_surgery_gate_rules(
            rule_ids=(RULE_ID,),
            decision_rule_ids=(RULE_ID,),
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
            expected_rule_ids=(RULE_ID,),
            snapshot=session.snapshot,
        )
        actual = reduced[0].final_state.value
        result_repr = repr(result)
        privacy_safe = not any(
            marker in result_repr
            for marker in (
                scenario.drug_text,
                scenario.course_text,
                "SYNTHETIC-I",
                "SYNTHETIC-P",
                "2026-01-01",
            )
            if marker
        )
        rows.append({
            "case": scenario.label,
            "expected": scenario.expected,
            "actual": actual,
            "passed": actual == scenario.expected,
            "llm_calls": int(result.llm_call_count),
            "total_tokens": int(result.total_tokens),
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "privacy_safe": privacy_safe,
        })
    return {
        "schema_version": "lx0609-028-synthetic-golden-v1",
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
        print("LX0609-05-01-01 synthetic Golden failed safely", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0 if report["passed"] == report["case_count"] and report["privacy_safe"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
