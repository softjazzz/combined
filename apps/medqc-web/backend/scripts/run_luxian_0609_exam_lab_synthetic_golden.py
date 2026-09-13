"""LX0609-010/011/012/014/015 单事件合成 Golden 烟测。

每份合成住院最多包含一个 CT/MRI 事件和一个培养事件。模型仅抽取语义与
文书关联，事件归属、权威时间和 24 小时边界均由 Python 判定。脚本不查询
或写入数据库，不落盘报告，也不输出正文、时间或病例坐标。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Mapping


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
from app.services.luxian_0609.exam_lab_fact_extraction import (
    build_exam_lab_text_projection,
    parse_exam_lab_fact_response,
)
from app.services.luxian_0609.native_exam_lab_execution import (
    EXAM_LAB_RULE_IDS,
    execute_luxian_0609_native_exam_lab_rules,
)
from app.services.qc_llm_client import SichuanQCLLMClient


@dataclass(frozen=True)
class Scenario:
    label: str
    expected: tuple[str, ...]
    expected_llm_calls: int = 0
    exam_rows: tuple[Mapping[str, Any], ...] = ()
    culture_rows: tuple[Mapping[str, Any], ...] = ()
    course_rows: tuple[Mapping[str, Any], ...] = ()
    discharge_datetime: str = "2026-04-30 12:00:00"


class _CapturingLLMClient:
    """只在本次合成 Golden 内保留响应，最终仅报告安全枚举。"""

    def __init__(self, delegate: SichuanQCLLMClient) -> None:
        self._delegate = delegate
        self.response: Mapping[str, Any] | None = None
        self.selected_rule_ids: tuple[str, ...] | None = None

    def reset(self) -> None:
        self.response = None
        self.selected_rule_ids = None

    @staticmethod
    def _rule_ids_from_response_format(
        response_format: Any,
    ) -> tuple[str, ...] | None:
        if not isinstance(response_format, Mapping):
            return None
        json_schema = response_format.get("json_schema")
        if not isinstance(json_schema, Mapping):
            return None
        schema = json_schema.get("schema")
        if not isinstance(schema, Mapping):
            return None
        properties = schema.get("properties")
        if not isinstance(properties, Mapping):
            return None
        facts = properties.get("facts")
        if not isinstance(facts, Mapping):
            return None
        items = facts.get("items")
        if not isinstance(items, Mapping):
            return None
        fact_properties = items.get("properties")
        if not isinstance(fact_properties, Mapping):
            return None
        rule_id = fact_properties.get("rule_id")
        if not isinstance(rule_id, Mapping):
            return None
        enum = rule_id.get("enum")
        if not isinstance(enum, list) or not enum:
            return None
        selected = tuple(str(value).strip().upper() for value in enum)
        return selected if len(selected) == len(set(selected)) else None

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.selected_rule_ids = self._rule_ids_from_response_format(
            kwargs.get("response_format")
        )
        self.response = await self._delegate.generate(prompt, **kwargs)
        return dict(self.response)

    def supports_strict_json_schema(self) -> bool:
        return self._delegate.supports_strict_json_schema()


_POSITIVE_EXAM = {
    "exam_name": "胸部CT",
    "exam_type": "CT",
    "exam_time": "2026-04-26 08:00:00",
    "report_time": "2026-04-26 12:00:00",
    "exam_conclusion": "右肺占位，考虑恶性，建议结合临床进一步处理。",
}
_POSITIVE_CULTURE = {
    "labtest_subject": "血培养及药敏",
    "specimen": "血液",
    "report_time": "2026-04-26 12:00:00",
    "result": "培养阳性：大肠埃希菌；药敏结果已报告。",
}
_PRE_EXAM_REASON = {
    "record_time": "2026-04-26 07:00:00",
    "record_content": "患者持续咳嗽并伴胸痛，为明确肺部病变原因拟行胸部CT检查。",
}


SCENARIOS = (
    Scenario(
        "golden-01-all-compliant",
        ("compliant",) * 5,
        expected_llm_calls=1,
        exam_rows=(_POSITIVE_EXAM,),
        culture_rows=(_POSITIVE_CULTURE,),
        course_rows=(
            _PRE_EXAM_REASON,
            {
                "record_time": "2026-04-26 13:00:00",
                "record_content": (
                    "已查看胸部CT报告，右肺占位考虑恶性，结合症状分析后拟进一步完善检查；"
                    "同时复核血培养阳性及药敏结果，根据敏感性调整抗感染方案。"
                ),
            },
        ),
    ),
    Scenario(
        "golden-02-all-missing-mature",
        ("non_compliant",) * 5,
        exam_rows=(_POSITIVE_EXAM,),
        culture_rows=(_POSITIVE_CULTURE,),
        course_rows=(),
    ),
    Scenario(
        "golden-03-exact-24h",
        ("compliant",) * 5,
        expected_llm_calls=1,
        exam_rows=(_POSITIVE_EXAM,),
        culture_rows=(_POSITIVE_CULTURE,),
        course_rows=(
            _PRE_EXAM_REASON,
            {
                "record_time": "2026-04-27 12:00:00",
                "record_content": (
                    "已查看胸部CT报告，报告结论为肺部占位考虑恶性，并分析后续处理；"
                    "已查看血培养报告，记录阳性菌及药敏结果，据此制定抗感染用药方案。"
                ),
            },
        ),
    ),
    Scenario(
        "golden-04-24h-plus-one-second",
        (
            "compliant",
            "non_compliant",
            "non_compliant",
            "non_compliant",
            "non_compliant",
        ),
        expected_llm_calls=1,
        exam_rows=(_POSITIVE_EXAM,),
        culture_rows=(_POSITIVE_CULTURE,),
        course_rows=(
            _PRE_EXAM_REASON,
            {
                "record_time": "2026-04-27 12:00:01",
                "record_content": (
                    "已查看胸部CT报告，报告结论为肺部占位考虑恶性，并分析后续处理；"
                    "已查看血培养报告，记录阳性菌及药敏结果，据此制定抗感染用药方案。"
                ),
            },
        ),
    ),
    Scenario(
        "golden-05-negative-results",
        ("compliant", "compliant", "not_applicable", "compliant", "not_applicable"),
        expected_llm_calls=1,
        exam_rows=({
            **_POSITIVE_EXAM,
            "exam_conclusion": "胸部CT未见明显异常。",
        },),
        culture_rows=({
            **_POSITIVE_CULTURE,
            "result": "培养无生长，未检出致病菌。",
        },),
        course_rows=(
            _PRE_EXAM_REASON,
            {
                "record_time": "2026-04-26 13:00:00",
                "record_content": "已记录CT未见异常及血培养无生长结果，继续观察。",
            },
        ),
    ),
    Scenario(
        "golden-06-non-target-zero-model",
        ("not_applicable",) * 5,
        exam_rows=({
            "exam_name": "腹部超声",
            "exam_time": "2026-04-26 08:00:00",
            "report_time": "2026-04-26 12:00:00",
            "exam_conclusion": "未见明显异常。",
        },),
        culture_rows=({
            "labtest_subject": "血常规",
            "report_time": "2026-04-26 12:00:00",
            "result": "白细胞计数正常。",
        },),
        course_rows=(),
    ),
    Scenario(
        "golden-07-grey-semantic-one-model",
        ("compliant",) * 5,
        expected_llm_calls=1,
        exam_rows=(_POSITIVE_EXAM,),
        culture_rows=(_POSITIVE_CULTURE,),
        course_rows=(
            {
                "record_time": "2026-04-26 07:00:00",
                "record_content": "本次检查因患者反复咳嗽两周，为查明症状病因而安排。",
            },
            {
                "record_time": "2026-04-26 13:00:00",
                "record_content": (
                    "影像报告提示右肺占位，结合临床考虑肿瘤可能，计划完善支气管镜；"
                    "微生物报告检出大肠埃希菌，对头孢类敏感，改用头孢曲松。"
                ),
            },
        ),
    ),
)


def _session_for(scenario: Scenario):
    rows = {
        "exam_master": scenario.exam_rows,
        "exam_item_report": (),
        "labtest_master": scenario.culture_rows,
        "labtest_item_report": (),
        "first_course_record": (),
        "daily_course_record": scenario.course_rows,
        "senior_course_record": (),
        "rescue_record": (),
        "inpat_registration.discharge_horizon": ({
            "discharge_datetime": scenario.discharge_datetime,
        },),
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
        selected_rule_ids=EXAM_LAB_RULE_IDS,
        institute_id="SYNTHETIC-I",
        patient_id="SYNTHETIC-P",
        visit_id=scenario.label,
        source_schema=None,
        created_at="2026-07-19T18:00:00+08:00",
        evaluation_as_of_date="2026-04-30",
        row_reader=reader,
    )


def _safe_parsed_fact_states(
    *,
    scenario: Scenario,
    response: Mapping[str, Any] | None,
    selected_rule_ids: tuple[str, ...] | None = None,
) -> tuple[tuple[str, str, str, str, int], ...] | tuple[()]:
    """诊断 parse/reducer 边界；绝不输出正文、提示词或模型响应。"""
    if response is None:
        return ()
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": scenario.exam_rows,
            "exam_item_report": (),
            "labtest_master": scenario.culture_rows,
            "labtest_item_report": (),
            "first_course_record": (),
            "daily_course_record": scenario.course_rows,
            "senior_course_record": (),
            "rescue_record": (),
            "inpat_registration.discharge_horizon": ({
                "discharge_datetime": scenario.discharge_datetime,
            },),
        }
    )
    try:
        facts = parse_exam_lab_fact_response(
            response=response,
            selected_rule_ids=selected_rule_ids or EXAM_LAB_RULE_IDS,
            projection=projection,
        )
    except ValueError:
        return (("parse_error", "", "", "", 0),)
    return tuple(
        (
            fact.rule_id,
            fact.applicability,
            fact.semantic_state,
            fact.positive_state,
            len(fact.course_doc_refs),
        )
        for fact in facts
    )


async def _run() -> dict[str, Any]:
    client = _CapturingLLMClient(
        SichuanQCLLMClient(build_adjudicator_runtime_config())
    )
    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        client.reset()
        session = _session_for(scenario)
        started = perf_counter()
        result = await execute_luxian_0609_native_exam_lab_rules(
            rule_ids=EXAM_LAB_RULE_IDS,
            decision_rule_ids=EXAM_LAB_RULE_IDS,
            wrapper_rules=(),
            evidence_payload={},
            llm_client=client,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        reduced = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=result.decisions,
            expected_rule_ids=EXAM_LAB_RULE_IDS,
            snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        actual = tuple(item.final_state.value for item in reduced)
        llm_calls = int(result.llm_call_count)
        result_repr = repr(result)
        privacy_safe = not any(
            marker in result_repr
            for marker in (
                "SYNTHETIC-I",
                "SYNTHETIC-P",
                "2026-04-26",
                "右肺占位",
                "大肠埃希菌",
            )
        )
        rows.append({
            "case": scenario.label,
            "expected": scenario.expected,
            "actual": actual,
            "expected_llm_calls": scenario.expected_llm_calls,
            "llm_calls": llm_calls,
            "llm_calls_match": llm_calls == scenario.expected_llm_calls,
            "executor_parse_failure_kinds": result.parse_failure_kinds,
            "passed": (
                actual == scenario.expected
                and llm_calls == scenario.expected_llm_calls
            ),
            "total_tokens": int(result.total_tokens),
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "privacy_safe": privacy_safe,
            "parsed_fact_states": _safe_parsed_fact_states(
                scenario=scenario,
                response=client.response,
                selected_rule_ids=client.selected_rule_ids,
            ),
        })
    return {
        "schema_version": "lx0609-exam-lab-single-event-golden-v1",
        "case_count": len(rows),
        "judgment_count": len(rows) * len(EXAM_LAB_RULE_IDS),
        "passed_cases": sum(1 for row in rows if row["passed"]),
        "passed_judgments": sum(
            sum(actual == expected for actual, expected in zip(row["actual"], row["expected"]))
            for row in rows
        ),
        "privacy_safe": all(row["privacy_safe"] for row in rows),
        "llm_call_contract_safe": all(row["llm_calls_match"] for row in rows),
        "technical_error_count": sum(
            actual == "technical_error" for row in rows for actual in row["actual"]
        ),
        "executor_parse_failure_count": sum(
            len(row["executor_parse_failure_kinds"]) for row in rows
        ),
        "cases": rows,
    }


def main() -> int:
    try:
        report = asyncio.run(_run())
    except Exception:
        print("LX0609 exam/lab synthetic Golden failed safely", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    complete = (
        report["passed_judgments"] == report["judgment_count"]
        and report["passed_cases"] == report["case_count"]
    )
    return 0 if complete and report["privacy_safe"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
