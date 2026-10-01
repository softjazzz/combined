"""临床医生筛选只消费三坐标病案首页签名事实。"""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.tasks import TaskCreateRequest, TaskTemplateConfig
from app.services.task_sampling_service import TaskSamplingService, validate_task_clinical_doctors
from app.services.task_sampling_persistence import _ensure_snapshot_unchanged, SamplingConflict


@pytest.mark.parametrize("value", [[], [{"institute_id": "I"}], [{"institute_id": "", "physician_name": "张医师"}],
    [{"institute_id": "I", "physician_name": "张医师", "doctor_id": "D"}],
    [{"institute_id": "I", "physician_name": "张医师"}] * 2])
def test_invalid_refs_rejected_by_execution_and_template(value):
    with pytest.raises(ValueError):
        validate_task_clinical_doctors("running", value)
    with pytest.raises(ValidationError):
        TaskTemplateConfig(scene="running", rule_set_key="SYN", sampling_config={"case_scope": "active", "clinical_doctors": value})


def test_specified_set_rejects_secondary_doctor_filter():
    with pytest.raises(ValidationError, match="二次抽样"):
        TaskCreateRequest(task_name="SYN", scene="running", rule_set_key="SYN",
            record_refs=[{"institute_id": "I", "patient_id": "P", "visit_id": "V"}],
            sampling_config={"case_scope": "active", "clinical_doctors": [{"institute_id": "I", "physician_name": "张医师"}]})


@pytest.mark.asyncio
async def test_doctor_source_exact_identity_institute_and_signature_then_sample(monkeypatch):
    from app.database import connection
    candidates = [{"institute_id": institute, "patient_id": patient, "visit_id": "SYN-V"}
                  for institute, patient in [("I", "P1"), ("I", "P2"), ("I2", "P3"), ("I", "P4")]]
    calls = []
    @contextmanager
    def session():
        def execute(statement):
            calls.append(statement.compile().params)
            return SimpleNamespace(all=lambda: [("I", "P1", "SYN-V", " 张医师 "),
                ("I", "P2", "SYN-V", None), ("I2", "P3", "SYN-V", "张医师"),
                ("I", "P4", "SYN-V", "张医师")])
        yield SimpleNamespace(execute=execute)
    monkeypatch.setattr(connection, "SessionLocal", session)
    async def source(*args):
        return candidates
    monkeypatch.setattr(TaskSamplingService, "_get_active_running_candidates", source)
    config = TaskTemplateConfig(scene="running", rule_set_key="SYN", sampling_method="count",
        sampling_config={"case_scope": "active", "total": 1, "clinical_doctors": [{"institute_id": "I", "physician_name": "张医师"}]})
    result = await TaskSamplingService().sample(config.model_dump(mode="json"))
    assert len(result) == 1 and result[0] in [candidates[0], candidates[3]]
    assert len(calls) == 1
    assert set(next(iter(calls[0].values()))) == {TaskSamplingService._identity(row) for row in candidates}


@pytest.mark.asyncio
async def test_doctor_source_failure_is_not_empty_success(monkeypatch):
    from app.database import connection
    def unavailable():
        raise RuntimeError("SYN unavailable")
    monkeypatch.setattr(connection, "SessionLocal", unavailable)
    with pytest.raises(RuntimeError, match="临床医生筛选来源不可用"):
        await TaskSamplingService()._filter_clinical_doctor_candidates([], [{"institute_id": "I", "physician_name": "张医师"}])


def test_doctor_change_invalidates_sampling_snapshot():
    with pytest.raises(SamplingConflict, match="sampling_config"):
        _ensure_snapshot_unchanged({"sampling_config": {"clinical_doctors": [{"institute_id": "I", "physician_name": "甲"}]}},
            {"sampling_config": {"clinical_doctors": [{"institute_id": "I", "physician_name": "乙"}]}})
