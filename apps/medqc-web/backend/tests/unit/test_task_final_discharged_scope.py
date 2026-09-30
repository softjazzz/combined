"""终末任务“已出院”范围（终末口径 B，2026-09-30）：日期窗、统一校验入口、候选与模板合同。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.schemas.tasks import TaskTemplateConfig
from app.services import task_sampling_service as sampling
from app.services.case_identity import CaseRef
from app.services.task_sampling_service import TaskSamplingService

HOSPITAL_TODAY = datetime.now(timezone(timedelta(hours=8))).date()
START = HOSPITAL_TODAY - timedelta(days=10)
END = HOSPITAL_TODAY - timedelta(days=1)
DATE_RANGE = {"start": START.isoformat(), "end": END.isoformat()}


def discharged_source(monkeypatch, rows, *, status="ready", failure=None):
    from app.services import case_scope_service

    calls = []

    def resolve(self, **kwargs):
        calls.append(kwargs)
        if failure:
            raise failure
        return SimpleNamespace(
            source_status=status,
            case_refs=tuple(CaseRef(row["institute_id"], row["patient_id"], row["visit_id"]) for row in rows),
            selected=tuple(rows),
        )

    monkeypatch.setattr(case_scope_service.CaseScopeService, "resolve_hospitalization_scope", resolve)
    return calls


def discharged_row(hospital, patient, visit, discharged=None, department="内科", status="discharged"):
    return {
        "institute_id": hospital,
        "patient_id": patient,
        "visit_id": visit,
        "hospitalization_status": status,
        "discharge_time": datetime.combine(discharged or END, datetime.min.time()),
        "department": department,
    }


def final_task(**overrides):
    return {
        "scene": "final",
        "sampling_method": "all",
        "sampling_config": {"case_scope": "discharged"},
        "date_range": DATE_RANGE,
        **overrides,
    }


# ---------------------------------------------------------------------------
# 出院日期窗
# ---------------------------------------------------------------------------


def test_discharge_window_requires_both_bounds_and_limits_span():
    assert sampling.validate_discharged_final_date_range(DATE_RANGE) == (START, END)
    with pytest.raises(ValueError, match="必须填写出院"):
        sampling.validate_discharged_final_date_range({"start": START.isoformat()})
    with pytest.raises(ValueError, match="必须填写出院日期范围"):
        sampling.validate_discharged_final_date_range(None)
    with pytest.raises(ValueError, match="不能晚于结束日期"):
        sampling.validate_discharged_final_date_range({"start": END.isoformat(), "end": START.isoformat()})
    with pytest.raises(ValueError, match="不能晚于今天"):
        sampling.validate_discharged_final_date_range(
            {"start": HOSPITAL_TODAY.isoformat(), "end": (HOSPITAL_TODAY + timedelta(days=1)).isoformat()}
        )
    with pytest.raises(ValueError, match="最多 31 天"):
        sampling.validate_discharged_final_date_range(
            {"start": (END - timedelta(days=31)).isoformat(), "end": END.isoformat()}
        )
    # 恰好 31 天（含首尾）允许。
    assert sampling.validate_discharged_final_date_range(
        {"start": (END - timedelta(days=30)).isoformat(), "end": END.isoformat()}
    ) == (END - timedelta(days=30), END)
    with pytest.raises(ValueError, match="日期范围格式无效"):
        sampling.validate_discharged_final_date_range({"start": "2026/09/01", "end": END.isoformat()})


# ---------------------------------------------------------------------------
# 统一校验入口
# ---------------------------------------------------------------------------


def test_scene_case_scope_validates_only_explicit_scopes():
    sampling.validate_scene_case_scope("final", "all", {"case_scope": "discharged"}, DATE_RANGE)
    with pytest.raises(ValueError, match="必须填写出院"):
        sampling.validate_scene_case_scope("final", "all", {"case_scope": "discharged"}, {})
    with pytest.raises(ValueError, match="抽样数量必须为正整数"):
        sampling.validate_scene_case_scope(
            "final", "count", {"case_scope": "discharged", "total": 0}, DATE_RANGE,
        )
    # 场景与范围错配一律拒绝。
    for scene, scope in (("final", "active"), ("running", "discharged"), ("final", "unknown")):
        with pytest.raises(ValueError, match="病例范围与任务场景不匹配"):
            sampling.validate_scene_case_scope(scene, "all", {"case_scope": scope}, DATE_RANGE)
    # 未带 case_scope 的历史运行/终末配置保持兼容，不做新合同校验。
    sampling.validate_scene_case_scope("final", "all", {}, None)
    sampling.validate_scene_case_scope("running", "all", {}, None)


def test_template_schema_accepts_discharged_only_for_final():
    base = {
        "rule_set_key": "sc_content_v1",
        "sampling_method": "all",
        "date_range": DATE_RANGE,
        "department_filter": [],
        "assign_method": "by_ratio",
        "assignee_config": {},
    }
    config = TaskTemplateConfig.model_validate({
        **base, "scene": "final", "sampling_config": {"case_scope": "discharged"},
    })
    assert config.sampling_config["case_scope"] == "discharged"
    TaskTemplateConfig.model_validate({**base, "scene": "final", "sampling_config": {}})
    with pytest.raises(ValueError, match="终末病历模板仅支持已出院范围"):
        TaskTemplateConfig.model_validate({**base, "scene": "final", "sampling_config": {"case_scope": "active"}})
    with pytest.raises(ValueError, match="运行病历模板当前仅支持当前在院范围"):
        TaskTemplateConfig.model_validate({
            **base, "rule_set_key": "luxian_0609_qc_v1", "scene": "running",
            "sampling_config": {"case_scope": "discharged"},
        })


# ---------------------------------------------------------------------------
# 终末候选
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_final_discharged_uses_scope_window_and_preserves_institution(monkeypatch):
    rows = [discharged_row("H1", "P1", "V1"), discharged_row("H2", "P1", "V1", department="外科")]
    calls = discharged_source(monkeypatch, rows)

    result = await TaskSamplingService().sample(final_task())

    assert {(row["institute_id"], row["patient_id"], row["visit_id"]) for row in result} == {
        ("H1", "P1", "V1"), ("H2", "P1", "V1"),
    }
    assert result[0]["discharge_date"] == END.isoformat()
    assert calls == [{
        "scope_mode": "discharged",
        "as_of_date": HOSPITAL_TODAY,
        "admission_start_date": None,
        "discharge_start_date": START,
        "discharge_end_date": END,
        "departments": [],
    }]


@pytest.mark.asyncio
async def test_final_discharged_requested_refs_must_be_in_scope(monkeypatch):
    discharged_source(monkeypatch, [discharged_row("H1", "P1", "V1"), discharged_row("H1", "P2", "V2")])
    picked = await TaskSamplingService().sample(final_task(
        record_refs=[{"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"}],
    ))
    assert [(row["patient_id"], row["visit_id"]) for row in picked] == [("P2", "V2")]
    with pytest.raises(ValueError, match="不属于出院筛选范围"):
        await TaskSamplingService().sample(final_task(
            record_refs=[{"institute_id": "H9", "patient_id": "P2", "visit_id": "V2"}],
        ))


@pytest.mark.asyncio
@pytest.mark.parametrize("row", [
    discharged_row("H1", "P1", "V1", status="active"),
    discharged_row("H1", "P1", "V1", discharged=HOSPITAL_TODAY - timedelta(days=40)),
    {**discharged_row("H1", "P1", "V1"), "discharge_time": None},
    {**discharged_row("H1", "P1", "V1"), "discharge_time": datetime.now(timezone.utc)},
])
async def test_final_discharged_rejects_rows_outside_contract(monkeypatch, row):
    discharged_source(monkeypatch, [row])
    with pytest.raises(RuntimeError, match="终末任务候选病历数据无效"):
        await TaskSamplingService().sample(final_task())


@pytest.mark.asyncio
async def test_final_discharged_department_filter_and_source_failures(monkeypatch):
    discharged_source(monkeypatch, [discharged_row("H1", "P1", "V1", department="外科")])
    with pytest.raises(RuntimeError, match="终末任务候选病历数据无效"):
        await TaskSamplingService().sample(final_task(department_filter=["内科"]))

    discharged_source(monkeypatch, [], status="unavailable")
    with pytest.raises(RuntimeError, match="未就绪"):
        await TaskSamplingService().sample(final_task())

    discharged_source(monkeypatch, [], failure=RuntimeError("remote P001 secret"))
    with pytest.raises(RuntimeError, match="候选病历数据源不可用") as exc:
        await TaskSamplingService().sample(final_task())
    assert "P001" not in str(exc.value)

    discharged_source(monkeypatch, [])
    with pytest.raises(ValueError, match="出院筛选范围内无候选病历"):
        await TaskSamplingService().sample(final_task())


@pytest.mark.asyncio
async def test_final_without_scope_stays_unavailable_and_legacy_ids_rejected(monkeypatch):
    calls = discharged_source(monkeypatch, [discharged_row("H1", "P1", "V1")])
    with pytest.raises(NotImplementedError):
        await TaskSamplingService().sample({"scene": "final", "sampling_config": {}})
    with pytest.raises(ValueError, match="终末任务不能使用旧病历 ID"):
        await TaskSamplingService().sample(final_task(record_ids=["legacy-1"]))
    with pytest.raises(ValueError, match="必须填写出院"):
        await TaskSamplingService().sample(final_task(date_range={}))
    assert calls == []

