"""质控医师签名及最近审核质控员分组，不伪造员工账号或未知组。"""
import pytest
from contextlib import contextmanager
from types import SimpleNamespace
from pydantic import ValidationError

from app.schemas.tasks import TaskCreateRequest, TaskTemplateConfig
from app.services import task_sampling_service as sampling, task_assignment_service as assignment


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["qc_physician", "qc_reviewer"])
@pytest.mark.parametrize("suffix,config,counts", [("count", {"total": 2}, [2, 1, 2]),
    ("ratio", {"percentage": 50, "max_per_group": 2}, [2, 1, 1])])
async def test_qc_groups_sample_per_institute_without_merging_names(monkeypatch, prefix, suffix, config, counts):
    candidates = [{"institute_id": institute, "patient_id": f"SYN-{group}-{n}", "visit_id": "SYN-V", "department": "合成科"}
        for group, (institute, total) in enumerate([("I", 5), ("I2", 1), ("I", 3)]) for n in range(total)]
    groups = {sampling.TaskSamplingService._identity(row): "同名" if row["patient_id"].split("-")[1] != "2" else "另一组"
        for row in candidates}
    async def source(*args):
        return candidates
    monkeypatch.setattr(sampling.TaskSamplingService, "_get_active_running_candidates", source)
    def signatures(identities, *, qc_physician):
        assert qc_physician is True and identities == set(groups)
        return groups
    monkeypatch.setattr(sampling, "_load_task_physician_signatures", signatures)
    def reviewers(rows):
        assert rows == candidates
        return groups
    monkeypatch.setattr(assignment, "load_latest_task_reviewers", reviewers)
    template = TaskTemplateConfig(scene="running", rule_set_key="SYN", sampling_method=f"{prefix}_{suffix}",
        sampling_config={"case_scope": "active", **config})
    result = await sampling.TaskSamplingService().sample(template.model_dump(mode="json"))
    actual = {}
    for row in result:
        key = row["institute_id"], groups[sampling.TaskSamplingService._identity(row)]
        actual[key] = actual.get(key, 0) + 1
    assert actual == dict(zip([("I", "同名"), ("I2", "同名"), ("I", "另一组")], counts))
    assert len({sampling.TaskSamplingService._identity(row) for row in result}) == len(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["qc_physician", "qc_reviewer"])
@pytest.mark.parametrize("failure", [False, True])
async def test_missing_group_and_source_failure_never_make_unknown_group(monkeypatch, prefix, failure):
    async def source(*args):
        return [{"institute_id": "I", "patient_id": "SYN-P", "visit_id": "V"}]
    def groups(*args, **kwargs):
        if failure:
            raise RuntimeError("SYN unavailable")
        return {}
    monkeypatch.setattr(sampling.TaskSamplingService, "_get_active_running_candidates", source)
    monkeypatch.setattr(sampling, "_load_task_physician_signatures", groups)
    monkeypatch.setattr(assignment, "load_latest_task_reviewers", groups)
    with pytest.raises(RuntimeError if failure else ValueError, match="来源不可用|缺少"):
        await sampling.TaskSamplingService().sample({"scene": "running", "sampling_method": f"{prefix}_count",
            "sampling_config": {"case_scope": "active", "total": 1}})


@pytest.mark.parametrize("method", ["qc_physician_count", "qc_physician_ratio", "qc_reviewer_count", "qc_reviewer_ratio"])
def test_specified_cases_reject_person_sampling(method):
    with pytest.raises(ValidationError, match="二次抽样"):
        TaskCreateRequest(task_name="SYN", scene="running", rule_set_key="SYN", sampling_method=method,
            record_refs=[{"institute_id": "I", "patient_id": "P", "visit_id": "V"}])


def test_qc_signature_does_not_replace_outpatient_source():
    with pytest.raises(ValidationError, match="运行和终末"):
        TaskTemplateConfig(scene="outpatient", rule_set_key="SYN", sampling_method="qc_physician_count", sampling_config={"total": 1})


@pytest.mark.parametrize("qc_physician,expected,forbidden", [
    (True, 'mr."QC_physician_sign"', 'mr.attending_physician_sign'),
    (False, 'mr.attending_physician_sign', 'mr."QC_physician_sign"'),
])
def test_frontpage_signature_source_selects_its_own_field(monkeypatch, qc_physician, expected, forbidden):
    from app.database import connection
    @contextmanager
    def session():
        def execute(statement):
            assert expected in str(statement) and forbidden not in str(statement)
            return SimpleNamespace(all=lambda: [("I", "P", "V", " 签名 ")])
        yield SimpleNamespace(execute=execute)
    monkeypatch.setattr(connection, "SessionLocal", session)
    assert sampling._load_task_physician_signatures({("I", "P", "V")}, qc_physician=qc_physician) == {("I", "P", "V"): "签名"}


def test_latest_reviewer_source_reuses_assignment_owner(monkeypatch):
    marker = object()
    @contextmanager
    def session():
        yield marker
    rows = [{"institute_id": "I", "patient_id": "P", "visit_id": "V"}]
    def latest(active, candidates):
        assert active is marker and candidates is rows
        return {("I", "P", "V"): "SYN-REVIEWER"}
    monkeypatch.setattr(assignment, "SessionLocal", session)
    monkeypatch.setattr(assignment, "_latest_reviewers", latest)
    assert assignment.load_latest_task_reviewers(rows) == {("I", "P", "V"): "SYN-REVIEWER"}
