"""手册科室抽样与指定病历固定集合合同，仅使用可识别的合成病例。"""

import pytest
from pydantic import ValidationError

from app.schemas.tasks import TaskCreateRequest, TaskTemplateConfig
from app.services.task_sampling_service import TaskSamplingService, validate_scoped_sampling_config
from app.services.task_sampling_persistence import SamplingConflict, _build_modern_task_records


def cases(institute, department, count):
    return [{"institute_id": institute, "patient_id": f"SYN-{institute}-{department}-{n}",
             "visit_id": f"SYN-{n}", "department": department} for n in range(count)]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,config,expected", [
    ("department_count", {"total": 3}, {("H1", "内科"): 3, ("H2", "内科"): 2, ("H1", "外科"): 3}),
    ("department_ratio", {"percentage": 50, "max_per_group": 3},
     {("H1", "内科"): 3, ("H2", "内科"): 1, ("H1", "外科"): 2}),
])
async def test_department_template_roundtrip_executes_per_institute_groups(monkeypatch, method, config, expected):
    candidates = cases("H1", "内科", 10) + cases("H2", "内科", 2) + cases("H1", "外科", 5)
    saved = TaskTemplateConfig(scene="running", rule_set_key="SYN-rules", sampling_method=method,
                               sampling_config={"case_scope": "active", **config})
    task = TaskTemplateConfig.model_validate(saved.model_dump(mode="json")).model_dump(mode="json")
    async def source(_self, _task):
        return candidates
    monkeypatch.setattr(TaskSamplingService, "_get_active_running_candidates", source)
    sampled = await TaskSamplingService().sample(task)
    counts = {}
    for row in sampled:
        key = row["institute_id"], row["department"]
        counts[key] = counts.get(key, 0) + 1
    assert counts == expected
    assert len({(row["institute_id"], row["patient_id"], row["visit_id"]) for row in sampled}) == len(sampled)
    assert all(row in candidates for row in sampled)


@pytest.mark.parametrize("method,config", [
    ("department_count", {}),
    ("department_count", {"total": 0}), ("department_count", {"total": True}),
    ("department_ratio", {"percentage": 10}),
    ("department_ratio", {"percentage": 101, "max_per_group": 5}),
    ("department_ratio", {"percentage": 10, "max_per_group": True}),
    ("department_ratio", {"percentage": 10, "max_per_group": 10001}),
    ("department_count", {"total": 1, "group_by": "doctor_name"}),
])
def test_department_config_rejected_by_execution_and_template(method, config):
    with pytest.raises(ValueError):
        validate_scoped_sampling_config("running", method, config)
    with pytest.raises(ValidationError):
        TaskTemplateConfig(scene="running", rule_set_key="SYN-rules", sampling_method=method,
                           sampling_config={"case_scope": "active", **config})


@pytest.mark.parametrize("field", ["institute_id", "department"])
def test_department_missing_group_owner_fails_closed(field):
    row = cases("H1", "内科", 1)[0]
    row[field] = None
    with pytest.raises(ValueError, match="可信机构或科室"):
        TaskSamplingService()._sample_by_department([row], "department_count", {"total": 1})


@pytest.mark.asyncio
@pytest.mark.parametrize("method,config", [
    ("count", {"total": 1}), ("percentage", {"percentage": 10}),
    ("department_count", {"total": 1}),
    ("department_ratio", {"percentage": 10, "max_per_group": 1}),
    ("all", {"total": 1}),
])
async def test_specified_cases_reject_resampling_before_source_access(monkeypatch, method, config):
    refs = [{key: row[key] for key in ("institute_id", "patient_id", "visit_id")}
            for row in cases("H1", "内科", 2)]
    task = {"scene": "running", "rule_set_key": "SYN-rules", "record_refs": refs,
            "sampling_method": method, "sampling_config": {"case_scope": "active", **config}}
    with pytest.raises(ValidationError, match="二次抽样"):
        TaskCreateRequest.model_validate({"task_name": "SYN-指定病例", **task})
    async def forbidden_source(*_args):
        pytest.fail("配置非法时不得读取病例源")
    monkeypatch.setattr(TaskSamplingService, "_get_active_running_candidates", forbidden_source)
    with pytest.raises(ValueError, match="二次抽样"):
        await TaskSamplingService().sample(task)


def test_persistence_requires_complete_specified_set():
    rows = cases("H1", "内科", 2)
    allowed = {(row["institute_id"], row["patient_id"], row["visit_id"]) for row in rows}
    with pytest.raises(SamplingConflict, match="完整保存"):
        _build_modern_task_records("SYN-task", rows[:1], allowed)
    assert len(_build_modern_task_records("SYN-task", rows, allowed)) == 2
