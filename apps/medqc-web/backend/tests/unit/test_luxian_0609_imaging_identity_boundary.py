"""影像身份、正文引导标签和主从冲突的执行边界。"""

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.exam_lab_fact_extraction import (
    build_exam_lab_text_projection,
)
from test_luxian_0609_native_exam_lab_execution import _Client, _typed_session, _wrapper


def _rows(master_identity, detail_identity):
    base = {
        "exam_id": "SYN-IDENTITY",
        "exam_time": "2026-04-26 10:00:00",
        "report_time": "2026-04-26 11:00:00",
    }
    return dict(base, **master_identity), dict(
        base, impression="未见明显异常。", **detail_identity
    )


@pytest.mark.parametrize(
    "master_identity,detail_identity",
    [
        ({"exam_name": "胸部CT"}, {"exam_name": "胸部DR"}),
        ({"performed_dept": "CT室"}, {"exam_name": "胸部DR"}),
        ({"exam_name": "胸部DR"}, {"exam_name": "胸部CT"}),
        ({"exam_name": "CT", "modality": "DR"}, {}),
        ({"exam_name": "胸部CT"}, {"performed_dept": "DR室"}),
        ({"performed_dept": "超声医学科"}, {"exam_name": "胸部CT"}),
    ],
)
def test_modality_conflict_is_neither_confirmed_nor_absent(
    master_identity, detail_identity
):
    master, detail = _rows(master_identity, detail_identity)
    event = build_exam_lab_text_projection(
        rows_by_source={"exam_master": (master,), "exam_item_report": (detail,)}
    ).imaging_events[0]
    assert not event.target_confirmed
    assert not event.target_explicitly_absent
    assert "event_binding" in event.conflict_roles
    assert not event.guidance_only
    assert len(event.document_refs) == 2


@pytest.mark.parametrize(
    "master_identity", [{"exam_name": "胸部CT"}, {"performed_dept": "CT室"}]
)
@pytest.mark.asyncio
async def test_modality_conflict_closes_formal_execution_without_model(
    monkeypatch, master_identity
):
    master, detail = _rows(master_identity, {"exam_name": "胸部DR"})
    snapshot, materials = _typed_session(
        monkeypatch, exam_rows=(master,), exam_report_rows=(detail,)
    )
    rules = ("LX0609-06-01-02", "LX0609-06-01-04", "LX0609-06-01-05")
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rules,
        wrapper_rules=[_wrapper(r) for r in rules],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=rules,
    )
    assert result.llm_call_count == 0
    assert all(d.reason_code == "association_failed" for d in result.decisions)
    assert len(result.decisions) == 3


@pytest.mark.parametrize(
    "identity", [{"exam_name": "胸部DR"}, {"exam_name": "超声"}, {}]
)
@pytest.mark.parametrize(
    "content",
    [
        "请结合CT或MR检查。",
        "与前次CT比较无明显变化。",
        "建议CT引导下操作。",
        "既往CT引导下操作。",
    ],
)
def test_suggestion_or_history_is_not_current_ct_identity(identity, content):
    master, detail = _rows(identity, {})
    detail.update(record_content=content, impression=content)
    event = build_exam_lab_text_projection(
        rows_by_source={"exam_master": (master,), "exam_item_report": (detail,)}
    ).imaging_events[0]
    assert not event.target_confirmed
    assert not event.guidance_only


@pytest.mark.parametrize(
    "identity",
    [{"exam_name": "胸部CT"}, {"exam_name": "胸部MRI"}, {"performed_dept": "CT室"}],
)
def test_untyped_report_keeps_confirmed_master(identity):
    master, detail = _rows(identity, {})
    event = build_exam_lab_text_projection(
        rows_by_source={"exam_master": (master,), "exam_item_report": (detail,)}
    ).imaging_events[0]
    assert event.target_confirmed
    assert not event.conflict_roles
    assert len(event.document_refs) == 2


def test_body_guidance_label_cannot_override_master_dr_identity():
    master, detail = _rows({"exam_name": "胸部DR"}, {})
    detail.update(record_content="CT引导下操作。", impression="CT引导下操作。")
    event = build_exam_lab_text_projection(
        rows_by_source={"exam_master": (master,), "exam_item_report": (detail,)}
    ).imaging_events[0]
    assert not event.target_confirmed
    assert not event.target_explicitly_absent
    assert not event.guidance_only
    assert "event_binding" in event.conflict_roles
