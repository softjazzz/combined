"""真实_source与最新结果解析定向合同；窄读取桩，不连接业务库。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.services import case_communication_service as communication
from app.services import custom_qc_workspace_service as workspace
from app.services import record_review_service as review
from app.services.case_identity import CaseRef
from app.services.defect_rectification_service import RectificationError
from app.services.qc_workspace import canonical_result_store as canonical


@pytest.fixture
def source_chain(monkeypatch):
    identity = {"institute_id": "SYN-H", "patient_id": "SYN-P", "visit_id": "SYN-V"}
    data = {**identity, "scene": "running", "root_job_id": "SYN-current-job", "envelope_id": "SYN-current-envelope"}
    calls = []

    class Session:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement, parameters=None):
            # 真实事务锁调用可记录，其他数据库查询/写入均不得触发。
            assert "pg_advisory_xact_lock" in str(statement)
            assert parameters == {"key": "qc_canonical_case|SYN-H|SYN-P|SYN-V|luxian_0609_qc_v1"}
            calls.append("lock")

        def add(self, *_):
            pytest.fail("候选来源不得写入")

        def flush(self):
            pytest.fail("候选来源不得写入")

        def commit(self):
            pytest.fail("来源解析不得自行提交")

    session = Session()
    key = "synthetic-source-chain-hmac-key"
    monkeypatch.setattr(canonical, "customer_safe_projection_key", lambda: key)
    dto = {"state": "ready", "job_id": data["root_job_id"], "root_job_id": data["root_job_id"],
        "envelope_id": data["envelope_id"], "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "SYN-v1",
        "record_ref": canonical.keyed_ref("rec", CaseRef.from_mapping(identity).as_key(), hmac_key=key), "items": []}
    state = {"dto": dto, "scene": "running", "reads": []}

    class Workspace:
        def build_latest_single_record_result_dto(self, **kwargs):
            assert {name: kwargs[name] for name in identity} == identity
            assert set(kwargs) <= {*identity, "rule_set_key"}
            if "rule_set_key" in kwargs:
                assert kwargs["rule_set_key"] == "luxian_0609_qc_v1"
            calls.append("latest")
            value = state["reads"].pop(0) if state["reads"] else state["dto"]
            return deepcopy(value)

    def envelopes(active_session, *, job_id, identity: tuple, rule_set_key, rule_set_version):
        assert active_session is session
        assert identity == ("SYN-H", "SYN-P", "SYN-V")
        assert (job_id, rule_set_key, rule_set_version) == (data["root_job_id"], "luxian_0609_qc_v1", "SYN-v1")
        calls.append("envelope")
        return [data["envelope_id"]]

    def scene(active_session, *, job_id, identity):
        assert active_session is session and job_id == data["root_job_id"]
        assert identity == ("SYN-H", "SYN-P", "SYN-V")
        calls.append("scene")
        return state["scene"]

    monkeypatch.setattr(workspace, "CustomQCWorkspaceService", Workspace)
    monkeypatch.setattr(review, "_envelope_ids", envelopes)
    monkeypatch.setattr(review, "_workspace_review_scene", scene)
    return session, data, state, calls


def test_real_write_source_takes_same_case_lock_before_latest_and_transaction_reference_checks(source_chain):
    session, data, _, calls = source_chain
    result = communication._source(session, data)
    assert calls == ["lock", "latest", "envelope", "scene"]
    assert result == {**data, "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "SYN-v1"}


@pytest.mark.parametrize("field", ["root_job_id", "envelope_id"])
def test_real_write_source_rejects_stale_job_or_envelope_before_reference_consumption(source_chain, field):
    session, data, _, calls = source_chain
    with pytest.raises(review.RecordReviewConflict) as error:
        communication._source(session, {**data, field: "SYN-old-reference"})
    assert error.value.code == "result_changed"
    assert calls == ["lock", "latest"]


def test_real_source_rejects_scene_mismatch_after_frozen_reference_check(source_chain):
    session, data, state, calls = source_chain
    state["scene"] = "final"
    with pytest.raises(RectificationError, match="场景") as error:
        communication._source(session, data)
    assert error.value.status == 409
    assert calls == ["lock", "latest", "envelope", "scene"]


def test_candidate_is_read_only_and_resolves_actual_envelope_without_write_lock(source_chain):
    session, data, _, calls = source_chain
    request = {key: value for key, value in data.items() if key != "envelope_id"}
    result = communication._source(session, request, candidate=True)
    assert result["envelope_id"] == data["envelope_id"]
    assert calls == ["latest", "latest", "envelope", "scene"]


def test_candidate_latest_changes_between_anchor_and_resolver_fail_closed(source_chain):
    session, data, state, calls = source_chain
    state["reads"] = [state["dto"], {**state["dto"], "envelope_id": "SYN-new-envelope"}]
    with pytest.raises(review.RecordReviewConflict) as error:
        communication._source(session, data, candidate=True)
    assert error.value.code == "result_changed"
    assert calls == ["latest", "latest"]
