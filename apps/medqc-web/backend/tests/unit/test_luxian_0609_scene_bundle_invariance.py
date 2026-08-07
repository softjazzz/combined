from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

import pytest

import app.services.luxian_0609.execution as execution
import app.services.luxian_0609.evidence_snapshot_provider as evidence_snapshot_provider
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.sichuan_qc_service import SichuanQCService


_CROSS_FAMILY_RULE_IDS = (
    "LX0609-016",  # 病程
    "LX0609-021",  # 会诊
    "LX0609-033",  # 手术
    "LX0609-012",  # 检查检验
    "LX0609-045",  # 输血
    "LX0609-052",  # 扩展文书（危急值）
)


class _FrozenExecutionDatetime(datetime):
    """固定公开入口内部生成的 created_at，避免测试比较到任务时钟。"""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        fixed = datetime(2026, 8, 7, 9, 0, 0, tzinfo=timezone.utc)
        return fixed.astimezone(tz) if tz is not None else fixed.replace(tzinfo=None)


def _scene_bundle(*, variant: str) -> dict[str, Any]:
    marker = "场景摘要A" if variant == "short" else "场景摘要B-不应进入原生判定或提示词"
    projected_count = 1 if variant == "short" else 9
    documents = [
        {
            "source_table": "daily_course_record",
            "content": f"{marker}-{index}",
            "text_preview": f"{marker}-{index}",
        }
        for index in range(projected_count)
    ]
    return {
        "scene": "running",
        "institute_id": "scene-test-institute",
        "patient_id": "scene-test-patient",
        "visit_id": "scene-test-visit",
        "medical_text": marker,
        "source_doc_priority": ["daily_course_record"],
        "structured_context": {"documents": {"daily_course_record": documents}},
        "source_documents": documents,
        "supporting_documents": [
            {"document_type": "病程记录", "evidence_text": marker}
        ],
        "document_hits": {"daily_course_record": variant == "long"},
        "text_available": True,
        "bundle_schema_version": "bundle-v5",
    }


def _empty_source_reader(*, source_key: str, **_: Any) -> SnapshotSourceRows:
    return SnapshotSourceRows.create(
        source_key=source_key,
        rows=(),
        truncated=False,
        limit_rows=50,
    )


def _projection(result: Mapping[str, Any]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            item.get("rule_id"),
            item.get("status"),
            (item.get("metadata") or {}).get("reason_code"),
            item.get("customer_display_facts"),
            item.get("evidence"),
        )
        for item in result.get("evaluation_results") or ()
    )


def _material_counts(session: Any) -> tuple[tuple[str, int], ...]:
    source_keys = tuple(session.materials.safe_summary()["sources"])
    return tuple(
        sorted(
            (str(source_key), len(tuple(session.materials.rows(str(source_key)))))
            for source_key in source_keys
        )
    )


@pytest.mark.asyncio
async def test_typed_native_mainline_is_invariant_to_scene_summary_projection_across_rule_families(
    monkeypatch,
):
    """真实生产入口只可把 Scene 作为任务载体，不能作为 Native 资料证据。"""

    real_build_session = evidence_snapshot_provider.build_luxian_0609_evidence_read_session
    captured_sessions: list[Any] = []
    real_executors = {
        "course": execution.execute_luxian_0609_native_course_quality_rules,
        "consultation": execution.execute_luxian_0609_native_consultation_episode_rules,
        "surgery": execution.execute_luxian_0609_native_surgery_gate_rules,
        "exam_lab": execution.execute_luxian_0609_native_exam_lab_rules,
        "transfusion": execution.execute_luxian_0609_native_transfusion_rules,
        "extended": execution.execute_luxian_0609_native_extended_document_rules,
    }
    executor_calls: list[tuple[str, tuple[str, ...], bool, bool]] = []

    def _build_session(**kwargs: Any):
        session = real_build_session(**kwargs, row_reader=_empty_source_reader)
        captured_sessions.append(session)
        return session

    def _spy(name: str):
        real_executor = real_executors[name]

        async def _wrapped(**kwargs: Any):
            executor_calls.append(
                (
                    name,
                    tuple(kwargs["rule_ids"]),
                    kwargs.get("evidence_snapshot") is not None,
                    kwargs.get("evidence_materials") is not None,
                )
            )
            return await real_executor(**kwargs)

        return _wrapped

    monkeypatch.setattr(execution, "datetime", _FrozenExecutionDatetime)
    monkeypatch.setattr(execution, "build_luxian_0609_evidence_read_session", _build_session)
    monkeypatch.setattr(execution, "execute_luxian_0609_native_course_quality_rules", _spy("course"))
    monkeypatch.setattr(execution, "execute_luxian_0609_native_consultation_episode_rules", _spy("consultation"))
    monkeypatch.setattr(execution, "execute_luxian_0609_native_surgery_gate_rules", _spy("surgery"))
    monkeypatch.setattr(execution, "execute_luxian_0609_native_exam_lab_rules", _spy("exam_lab"))
    monkeypatch.setattr(execution, "execute_luxian_0609_native_transfusion_rules", _spy("transfusion"))
    monkeypatch.setattr(execution, "execute_luxian_0609_native_extended_document_rules", _spy("extended"))

    service = SichuanQCService()
    short = await service.evaluate_running_final_bundle_input(
        bundle=_scene_bundle(variant="short"),
        rule_ids=list(_CROSS_FAMILY_RULE_IDS),
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        evaluation_as_of_date="2026-08-01",
        evaluation_horizon_policy="frozen_task_date",
        use_execution_cache=False,
    )
    long = await service.evaluate_running_final_bundle_input(
        bundle=_scene_bundle(variant="long"),
        rule_ids=list(_CROSS_FAMILY_RULE_IDS),
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        evaluation_as_of_date="2026-08-01",
        evaluation_horizon_policy="frozen_task_date",
        use_execution_cache=False,
    )

    assert len(captured_sessions) == 2
    assert [session.snapshot.snapshot_hash for session in captured_sessions] == [
        captured_sessions[0].snapshot.snapshot_hash,
        captured_sessions[0].snapshot.snapshot_hash,
    ]
    assert _material_counts(captured_sessions[0]) == _material_counts(captured_sessions[1])
    assert _projection(short) == _projection(long)
    assert short["token_usage"] == long["token_usage"]
    assert short["token_usage"]["total_tokens"] == 0
    assert {name for name, _, has_snapshot, has_materials in executor_calls} == set(real_executors)
    assert all(has_snapshot and has_materials for _, _, has_snapshot, has_materials in executor_calls)


class _PromptCaptureClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        course_match = re.search(r"COURSE_DOC=(\[[^\]]*\])", prompt)
        assert course_match is not None
        course_refs = json.loads(course_match.group(1))
        assert course_refs
        return {
            "choices": [{"message": {"content": json.dumps({
                "schema_version": "lx0609-exam-lab-text-facts-v3",
                "facts": [{
                    "rule_id": "LX0609-012",
                    "applicability": "applicable",
                    "semantic_state": "present",
                    "positive_state": "positive",
                    "course_doc_refs": [course_refs[-1]],
                }],
            }, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 37, "completion_tokens": 5, "total_tokens": 42},
            "_api_time": 0.01,
        }


@pytest.mark.asyncio
async def test_typed_native_prompt_and_canonical_are_invariant_to_scene_summary_projection(
    monkeypatch,
):
    """012 真实 LLM 事实提取的输入必须仅由 MaterialStore 裁剪资料决定。"""

    real_build_session = evidence_snapshot_provider.build_luxian_0609_evidence_read_session
    captured_sessions: list[Any] = []

    def _reader(*, source_key: str, **_: Any) -> SnapshotSourceRows:
        rows_by_source: dict[str, Sequence[Mapping[str, Any]]] = {
            "exam_master": ({
                "exam_name": "头颅MRI",
                "exam_type": "MRI",
                "exam_time": "2026-04-26 08:00:00",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "明确阳性：右侧硬膜下血肿。",
            },),
            "daily_course_record": (
                {
                    "record_time": "2026-04-26 07:00:00",
                    "record_content": "因颅脑损伤拟行头颅MRI明确病情。",
                },
                {
                    "record_time": "2026-04-26 13:00:00",
                    "record_content": "已查看MRI报告，继续观察。",
                },
            ),
            "inpat_registration": ({"admission_datetime": "2026-04-25 08:00:00"},),
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    def _build_session(**kwargs: Any):
        session = real_build_session(**kwargs, row_reader=_reader)
        captured_sessions.append(session)
        return session

    monkeypatch.setattr(execution, "datetime", _FrozenExecutionDatetime)
    monkeypatch.setattr(execution, "build_luxian_0609_evidence_read_session", _build_session)
    service = SichuanQCService()
    client = _PromptCaptureClient()
    service.adjudicator_client = client

    first = await service.evaluate_running_final_bundle_input(
        bundle=_scene_bundle(variant="short"),
        rule_ids=["LX0609-012"],
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        evaluation_as_of_date="2026-04-30",
        evaluation_horizon_policy="frozen_task_date",
        use_execution_cache=False,
    )
    second = await service.evaluate_running_final_bundle_input(
        bundle=_scene_bundle(variant="long"),
        rule_ids=["LX0609-012"],
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        evaluation_as_of_date="2026-04-30",
        evaluation_horizon_policy="frozen_task_date",
        use_execution_cache=False,
    )

    assert len(captured_sessions) == 2
    assert captured_sessions[0].snapshot.snapshot_hash == captured_sessions[1].snapshot.snapshot_hash
    assert _material_counts(captured_sessions[0]) == _material_counts(captured_sessions[1])
    assert len(client.prompts) == 2
    assert hashlib.sha256(client.prompts[0].encode("utf-8")).hexdigest() == hashlib.sha256(
        client.prompts[1].encode("utf-8")
    ).hexdigest()
    assert "场景摘要" not in client.prompts[0]
    assert _projection(first) == _projection(second)
    assert first["token_usage"] == second["token_usage"] == {
        "total_tokens": 42,
        "prompt_tokens": 37,
        "completion_tokens": 5,
    }
