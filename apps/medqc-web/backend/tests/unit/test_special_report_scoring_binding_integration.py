"""专用默认绑定走真实评分写入链；仅使用 SQLite 合成数据。"""

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import (
    QCScoringDefaultBinding,
    QCScoringGroup,
    QCScoringItem,
    QCScoringStandard,
)
from app.services import scoring_standard_service as service


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for model in (QCScoringStandard, QCScoringGroup, QCScoringItem, QCScoringDefaultBinding):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def active(name, *, scene="final", replace_mode="undefault"):
    draft = service.create_standard(
        actor="synthetic-admin", name=name, scene=scene,
        rule_set_key="luxian_0609_qc_v1", base_score=100,
        grade_bands=[{"name": "合格", "min_score": 0, "max_score": 100}],
        veto_grade="合格",
    )
    saved = service.save_items(
        draft["id"], actor="synthetic-admin", version_seq=draft["version_seq"],
        groups=[{"group_name": "合成项目组"}],
        items=[{"group_name": "合成项目组", "rule_id": "LX0609-001", "deduction": 2,
                "department_scope_mode": "all", "department_refs": []}],
    )
    return service.activate_standard(
        saved["id"], actor="synthetic-admin", version_seq=saved["version_seq"],
        replace_mode=replace_mode,
    )


def bind(standard, version=0):
    return service.set_special_report_binding(
        actor="synthetic-admin", scene="final", version_seq=version,
        standard_id=standard["id"], standard_version_seq=standard["version_seq"],
    )


def test_create_activate_bind_consume_replace_and_unbind(sessions):
    assert service.get_special_report_default_standard("final") is None
    first = active("合成终末标准甲")
    second = active("合成终末标准乙")
    first = service.get_standard(first["id"])
    original_default = service.get_default_standard("final")
    before = {row["id"]: service.get_standard(row["id"]) for row in (first, second)}

    binding = bind(first)
    assert binding["status"] == "configured"
    assert binding["version_seq"] == 1
    consumed = service.get_special_report_default_standard("final")
    assert consumed["id"] == first["id"]
    assert consumed["binding_version_seq"] == 1
    assert consumed["binding_purpose"] == "special_report"

    replaced = bind(second, binding["version_seq"])
    assert replaced["version_seq"] == 2
    assert service.get_special_report_default_standard("final")["id"] == second["id"]
    assert service.get_default_standard("final") == original_default
    for identifier, detail in before.items():
        assert service.get_standard(identifier) == detail

    cleared = service.set_special_report_binding(
        actor="synthetic-admin", scene="final", version_seq=2,
        standard_id=None, standard_version_seq=None,
    )
    assert cleared["version_seq"] == 3
    assert cleared["status"] == "no_standard"
    assert service.get_special_report_default_standard("final") is None
    assert service.get_default_standard("final")["id"] == second["id"]


def test_stale_binding_and_standard_versions_do_not_overwrite(sessions):
    first = active("合成版本甲")
    second = active("合成版本乙")
    first = service.get_standard(first["id"])
    saved = bind(first)
    with pytest.raises(service.ScoringStandardConflict):
        bind(second, 0)
    assert service.get_special_report_binding("final") == saved
    with pytest.raises(service.ScoringStandardConflict):
        service.set_special_report_binding(
            actor="synthetic-admin", scene="final", version_seq=1,
            standard_id=second["id"], standard_version_seq=second["version_seq"] - 1,
        )
    assert service.get_special_report_binding("final") == saved


def test_two_editors_read_same_version_only_first_update_succeeds(sessions):
    first = active("合成双编辑甲")
    second = active("合成双编辑乙")
    first = service.get_standard(first["id"])
    bind(first)
    editor_a = service.get_special_report_binding("final")
    editor_b = service.get_special_report_binding("final")
    winner = bind(second, editor_a["version_seq"])
    with pytest.raises(service.ScoringStandardConflict):
        service.set_special_report_binding(
            actor="synthetic-other-admin", scene="final",
            version_seq=editor_b["version_seq"], standard_id=None,
            standard_version_seq=None,
        )
    assert service.get_special_report_binding("final") == winner


def test_archived_binding_is_unavailable_and_does_not_fall_back(sessions):
    first = active("合成被绑定标准")
    fallback = active("合成执行默认标准")
    first = service.get_standard(first["id"])
    bind(first)
    service.archive_standard(
        first["id"], actor="synthetic-admin", version_seq=first["version_seq"],
    )
    binding = service.get_special_report_binding("final")
    assert binding["status"] == "unavailable"
    assert binding["standard_id"] == first["id"]
    with pytest.raises(service.ScoringStandardUnavailable):
        service.get_special_report_default_standard("final")
    assert service.get_default_standard("final")["id"] == fallback["id"]


def test_active_standard_version_change_requires_explicit_reconfirmation(sessions):
    first = active("合成绑定版本冻结")
    active("合成另一执行默认")
    first = service.get_standard(first["id"])
    binding = bind(first)
    changed = service.set_default_standard(
        first["id"], actor="synthetic-admin", version_seq=first["version_seq"],
        replace_mode="undefault",
    )
    assert changed["status"] == "active"
    assert service.get_special_report_binding("final")["status"] == "unavailable"
    with pytest.raises(service.ScoringStandardUnavailable):
        service.get_special_report_default_standard("final")
    reconfirmed = bind(changed, binding["version_seq"])
    assert reconfirmed["standard_version_seq"] == changed["version_seq"]
    assert service.get_special_report_default_standard("final")["id"] == first["id"]


@pytest.mark.parametrize("scene", ["running", "outpatient", "special_report"])
def test_other_execution_scenes_are_rejected(sessions, scene):
    with pytest.raises(service.ScoringStandardInvalid):
        service.get_special_report_binding(scene)
    with pytest.raises(service.ScoringStandardInvalid):
        service.get_special_report_default_standard(scene)


def test_draft_and_wrong_scene_cannot_be_bound(sessions):
    draft = service.create_standard(
        actor="synthetic-admin", name="合成未启用", scene="final",
        rule_set_key="luxian_0609_qc_v1", base_score=100,
        grade_bands=[{"name": "合格", "min_score": 0, "max_score": 100}],
        veto_grade="合格",
    )
    with pytest.raises(service.ScoringStandardInvalid):
        bind(draft)
    running = active("合成运行标准", scene="running")
    with pytest.raises(service.ScoringStandardInvalid):
        bind(running)
    assert service.get_special_report_default_standard("final") is None
