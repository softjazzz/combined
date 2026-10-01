"""任务评分范围使用合成三坐标与已有评分 owner。"""
import pytest
from pydantic import ValidationError

from app.schemas.tasks import TaskCreateRequest, TaskTemplateConfig
from app.services.task_sampling_service import TaskSamplingService, validate_task_score_filter
from app.services.task_sampling_persistence import _ensure_snapshot_unchanged, SamplingConflict


@pytest.mark.parametrize("value", [{}, {"standard_id": "S", "score_min": True},
                                  {"standard_id": "S", "score_max": float("nan")},
                                  {"standard_id": "S", "score_min": 90, "score_max": 80},
                                  {"standard_id": "S", "grade": "甲"}])
def test_invalid_filter_rejected_by_template(value):
    with pytest.raises(ValueError):
        validate_task_score_filter("running", value)
    with pytest.raises(ValidationError):
        TaskTemplateConfig(scene="running", rule_set_key="SYN", sampling_config={"case_scope": "active", "score_filter": value})


def test_specified_set_rejects_score_filter():
    with pytest.raises(ValidationError, match="二次抽样"):
        TaskCreateRequest(task_name="合成测试", scene="running", rule_set_key="SYN",
                          record_refs=[{"institute_id": "SYN-I", "patient_id": "SYN-P", "visit_id": "SYN-V"}],
                          sampling_config={"case_scope": "active", "score_filter": {"standard_id": "S"}})


def test_score_filter_changed_conflicts_with_saved_snapshot():
    with pytest.raises(SamplingConflict, match="sampling_config"):
        _ensure_snapshot_unchanged({"sampling_config": {"score_filter": {"standard_id": "S", "score_min": 80}}},
                                   {"sampling_config": {"score_filter": {"standard_id": "S", "score_min": 90}}})


@pytest.mark.asyncio
async def test_score_filter_uses_full_candidates_before_count_and_drops_unknown(monkeypatch):
    from app.services import scoring_service as scoring
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    candidates = [{"institute_id": "SYN-I", "patient_id": f"SYN-{n}", "visit_id": "SYN-V"} for n in range(4)]
    identities = [TaskSamplingService._identity(row) for row in candidates]
    async def source(*_args):
        return candidates
    monkeypatch.setattr(TaskSamplingService, "_get_active_running_candidates", source)
    monkeypatch.setattr(scoring, "get_workstation_standard", lambda scene, standard_id: {"id": standard_id, "scene": scene})
    monkeypatch.setattr(CustomQCWorkspaceService, "__init__", lambda self: None)
    monkeypatch.setattr(CustomQCWorkspaceService, "build_luxian_0609_completed_record_result_summaries", lambda *args, **kwargs: {})
    def score(page_scenes, anchors, **kwargs):
        assert set(page_scenes) == set(identities)
        assert kwargs["strict"] is True
        assert kwargs["standard_loader"]("running")["id"] == "S"
        return dict(zip(identities, [
            {"status": "scored", "score": 80}, {"status": "scored", "score": 90},
            {"status": "unavailable", "score": 0}, {"status": "scored", "score": 100},
        ])), {}
    monkeypatch.setattr(scoring, "score_workstation_page", score)
    sampled = await TaskSamplingService().sample({"scene": "running", "sampling_method": "count",
        "sampling_config": {"case_scope": "active", "total": 1, "score_filter": {"standard_id": "S", "score_min": 80, "score_max": 90}}})
    assert len(sampled) == 1 and sampled[0] in candidates[:2]


@pytest.mark.asyncio
async def test_score_filter_limit_does_not_truncate():
    with pytest.raises(ValueError, match="5000"):
        await TaskSamplingService()._filter_scored_candidates([{}] * 5001, "running", {"standard_id": "S"})


@pytest.mark.parametrize("scene", ["outpatient", None])
def test_score_filter_requires_trusted_scene(scene):
    with pytest.raises(ValueError, match="运行和终末"):
        validate_task_score_filter(scene, {"standard_id": "S", "score_min": 0})


@pytest.mark.asyncio
async def test_score_source_failure_does_not_return_empty_success(monkeypatch):
    from app.services import scoring_service as scoring
    def unavailable(*args):
        raise RuntimeError("SYN source unavailable")
    monkeypatch.setattr(scoring, "get_workstation_standard", unavailable)
    with pytest.raises(RuntimeError, match="评分暂不可用"):
        await TaskSamplingService()._filter_scored_candidates([], "running", {"standard_id": "S"})


@pytest.mark.asyncio
async def test_required_department_source_failure_does_not_return_empty_success(monkeypatch):
    from app.services import scoring_service as scoring
    from app.services.medical_records import query_service
    monkeypatch.setattr(scoring, "get_workstation_standard", lambda *_: {"items": [{"department_scope_mode": "selected"}]})
    def unavailable(*args, **kwargs):
        raise RuntimeError("SYN department source unavailable")
    monkeypatch.setattr(query_service, "load_scoring_departments", unavailable)
    scored = []
    monkeypatch.setattr(scoring, "score_workstation_page", lambda *args, **kwargs: scored.append(True))
    with pytest.raises(RuntimeError, match="评分暂不可用"):
        await TaskSamplingService()._filter_scored_candidates(
            [{"institute_id": "SYN-I", "patient_id": "SYN-P", "visit_id": "SYN-V"}],
            "running", {"standard_id": "S"},
        )
    assert not scored


@pytest.mark.asyncio
async def test_department_preload_is_reused_by_scoring_owner(monkeypatch):
    from app.services import scoring_service as scoring
    from app.services.medical_records import query_service
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    candidate = {"institute_id": "SYN-I", "patient_id": "SYN-P", "visit_id": "SYN-V"}
    identity = TaskSamplingService._identity(candidate)
    calls = []
    monkeypatch.setattr(scoring, "get_workstation_standard", lambda *_: {"items": [{"department_scope_mode": "selected"}]})
    def departments(identities, **kwargs):
        calls.append(identities)
        return {identity: "合成内科"}
    monkeypatch.setattr(query_service, "load_scoring_departments", departments)
    monkeypatch.setattr(CustomQCWorkspaceService, "__init__", lambda self: None)
    monkeypatch.setattr(CustomQCWorkspaceService, "build_luxian_0609_completed_record_result_summaries", lambda *args, **kwargs: {})
    def score(*args, **kwargs):
        assert kwargs["department_loader"]([identity], session_factory=None) == {identity: "合成内科"}
        return {identity: {"status": "scored", "score": 80}}, {}
    monkeypatch.setattr(scoring, "score_workstation_page", score)
    assert await TaskSamplingService()._filter_scored_candidates([candidate], "running", {"standard_id": "S"}) == [candidate]
    assert calls == [[identity]]
