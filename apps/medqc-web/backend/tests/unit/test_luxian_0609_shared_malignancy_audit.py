"""原始规则两族共享恶性事实的并发风险审计；不访问数据库或真实模型。"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.malignancy_fact import MalignancyFactResolver


SURGERY_RULE = "LX0609-04-02-03"
TUMOR_RULE = "LX0609-08-01-04"


class _BarrierClient:
    def __init__(self, *, invalid: bool = False) -> None:
        self.calls = 0
        self.invalid = invalid
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, prompt: str, **kwargs):
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return {
            "choices": [{"message": {"content": "invalid" if self.invalid else json.dumps({
                "schema_version": "lx0609_malignancy_v1",
                "results": [{"ref": "D01", "state": "uncertain"}],
            })}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


class _SourceSpy(MalignancyFactResolver):
    def __init__(self, client):
        super().__init__(client)
        self.sources = []
        self.both_resolving = asyncio.Event()

    async def resolve(self, sources):
        self.sources.append(tuple(sources))
        if len(self.sources) >= 2:
            self.both_resolving.set()
        return await super().resolve(sources)


def _session():
    rows = {
        "surgery_record": ({
            "document_id": "synthetic-surgery",
            "surgery_name": "右肺切除术",
            "surgery_begin_time": "2026-01-01 08:00:00+08",
            "surgery_process": "完成切除，淋巴结处置记录待核。",
        },),
        "diagnosis": ({"document_id": "synthetic-diagnosis", "diagnosis_name": "右肺占位性质待定"},),
        "discharge_record": ({"document_id": "synthetic-discharge", "discharge_time": "2026-01-05 08:00:00+08"},),
    }

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(SURGERY_RULE, TUMOR_RULE),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-01-09T09:00:00+08:00", row_reader=reader,
    )


async def _families(session, client, resolver):
    common = {
        "evidence_payload": None,
        "institute_id": "I", "patient_id": "P", "visit_id": "V",
        "source_schema": None, "llm_client": client,
        "evidence_snapshot": session.snapshot,
        "evidence_materials": session.materials,
        "malignancy_resolver": resolver,
    }
    return await asyncio.gather(
        surgery.execute_luxian_0609_native_surgery_gate_rules(
            rule_ids=(SURGERY_RULE,), decision_rule_ids=(SURGERY_RULE,),
            wrapper_rules=[{"rule_id": SURGERY_RULE, "custom_prompt": "{medical_text}"}],
            **common,
        ),
        tumor.execute_luxian_0609_native_tumor_pathology_rules(
            rule_ids=(TUMOR_RULE,), decision_rule_ids=(TUMOR_RULE,),
            wrapper_rules=[{"rule_id": TUMOR_RULE, "custom_prompt": "{medical_text}"}],
            **common,
        ),
    )


@pytest.mark.asyncio
async def test_original_surgery_and_tumor_families_concurrently_resolve_same_source():
    session = _session()
    client = _BarrierClient()
    resolver = _SourceSpy(client)
    task = asyncio.create_task(_families(session, client, resolver))
    try:
        await asyncio.wait_for(resolver.both_resolving.wait(), timeout=3)
        await asyncio.wait_for(client.started.wait(), timeout=3)
    finally:
        client.release.set()
    surgery_result, tumor_result = await asyncio.wait_for(task, timeout=3)
    assert len(resolver.sources) == 2
    assert [tuple((s.source_key, s.rows) for s in sources) for sources in resolver.sources] == [
        (("diagnosis", session.materials.rows("diagnosis")),),
        (("diagnosis", session.materials.rows("diagnosis")),),
    ]
    assert {sources[0].state for sources in resolver.sources} == {"available", "present"}
    assert surgery_result.llm_call_count + tumor_result.llm_call_count == 1
    assert surgery_result.total_tokens + tumor_result.total_tokens == 15
    assert client.calls == 1


@pytest.mark.asyncio
async def test_shared_malignancy_invalid_response_is_shared_and_counted_once():
    session = _session()
    client = _BarrierClient(invalid=True)
    resolver = _SourceSpy(client)
    task = asyncio.create_task(_families(session, client, resolver))
    try:
        await asyncio.wait_for(resolver.both_resolving.wait(), timeout=3)
        await asyncio.wait_for(client.started.wait(), timeout=3)
    finally:
        client.release.set()
    surgery_result, tumor_result = await asyncio.wait_for(task, timeout=3)
    assert client.calls == 1
    assert surgery_result.llm_call_count + tumor_result.llm_call_count == 1
    assert surgery_result.total_tokens + tumor_result.total_tokens == 15
    reasons = [result.decisions[0].reason_code for result in (surgery_result, tumor_result)]
    assert reasons == ["model_transport_error", "executor_exception"]


@pytest.mark.asyncio
async def test_shared_malignancy_all_waiters_cancel_underlying_request():
    session = _session()
    client = _BarrierClient()
    resolver = _SourceSpy(client)
    task = asyncio.create_task(_families(session, client, resolver))
    await asyncio.wait_for(resolver.both_resolving.wait(), timeout=3)
    await asyncio.wait_for(client.started.wait(), timeout=3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert client.calls == 1
    assert resolver._slots == []
