"""首页评分目录与配置合同；仅使用合成 SQLite，不执行真实质控。"""

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database.models.qc import QCScoringGroup, QCScoringItem, QCScoringStandard
from app.services import rule_set_version_service as versions
from app.services import scoring_standard_service as standards
from app.services.frontpage_formal_qc import FrontpageFormalQC
from app.services.frontpage_rule_catalog import (
    FRONTPAGE_DOCUMENT_TYPE,
    FRONTPAGE_RULE_IDS,
    FRONTPAGE_RULE_SET_KEY,
    FRONTPAGE_RULE_SET_VERSION,
    load_frontpage_rule_catalog,
)
from app.services.qc_rule_sets import SICHUAN_RULE_SETS


def test_catalog_directly_mirrors_complete_formal_owner():
    owner = FrontpageFormalQC().rules
    catalog = load_frontpage_rule_catalog()
    assert FRONTPAGE_RULE_IDS == tuple(rule.rule_id for rule in owner)
    assert len(catalog) == len(set(FRONTPAGE_RULE_IDS)) > 0
    for rule, entry in zip(owner, catalog, strict=True):
        assert entry == {
            "rule_id": rule.rule_id, "name": rule.rule_name,
            "description": rule.description, "field_name": rule.field_name,
            "category": rule.category.value, "severity": rule.severity.value,
            "source_document": FRONTPAGE_DOCUMENT_TYPE, "executable": True,
        }
    assert FRONTPAGE_RULE_SET_KEY not in SICHUAN_RULE_SETS


def test_builtin_directory_readable_without_database_but_never_publishable(monkeypatch):
    monkeypatch.setattr(versions, "SessionLocal", None)
    assert versions.current_version(FRONTPAGE_RULE_SET_KEY) == FRONTPAGE_RULE_SET_VERSION
    resolved = versions.resolve_rule_set_version(FRONTPAGE_RULE_SET_KEY, FRONTPAGE_RULE_SET_VERSION)
    assert resolved["active_rule_ids"] == list(FRONTPAGE_RULE_IDS)
    assert resolved["paused_rule_ids"] == resolved["excluded_rule_ids"] == []
    enriched = versions.with_executable_flags(FRONTPAGE_RULE_SET_KEY, resolved)
    names = {rule.rule_id: rule.rule_name for rule in FrontpageFormalQC().rules}
    assert all(entry["qc_point"] == names[entry["rule_id"]] and entry["executable"]
               and entry["source_document"] == "frontpage" for entry in enriched["entries"])
    assert versions.list_versions(FRONTPAGE_RULE_SET_KEY)["versionable"] is False
    with pytest.raises(versions.RuleSetVersionConflict) as exc:
        versions.create_draft(FRONTPAGE_RULE_SET_KEY, actor="synthetic-user")
    assert exc.value.code == "unsupported_rule_set"
    with pytest.raises(versions.RuleSetVersionNotFound):
        versions.resolve_rule_set_version(FRONTPAGE_RULE_SET_KEY, "not-published")


def test_frontpage_scene_does_not_borrow_inpatient_or_outpatient_catalog():
    assert standards.scene_rule_set_keys("frontpage") == (FRONTPAGE_RULE_SET_KEY,)
    assert standards.scene_rule_set_keys("outpatient") == ()
    assert FRONTPAGE_RULE_SET_KEY not in standards.scene_rule_set_keys("final")
    assert standards.scene_catalog()[-1] == {
        "scene": "frontpage", "rule_sets": [{
            "rule_set_key": FRONTPAGE_RULE_SET_KEY, "rule_set_name": "病案首页形式质控",
        }],
    }
    assert standards.rule_document_universe(FRONTPAGE_RULE_SET_KEY) == {
        rule_id: frozenset({"frontpage"}) for rule_id in FRONTPAGE_RULE_IDS
    }
    with pytest.raises(standards.ScoringStandardInvalid) as exc:
        standards.create_standard(actor="synthetic-user", name="错配", scene="frontpage",
                                  rule_set_key="luxian_0609_qc_v1", base_score=100,
                                  grade_bands=[], veto_grade=None)
    assert exc.value.code == "rule_set_scene_mismatch"


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine("sqlite://")
    for model in (QCScoringStandard, QCScoringGroup, QCScoringItem):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(standards, "SessionLocal", factory)
    yield factory
    engine.dispose()


def test_frontpage_standard_create_save_activate_and_independent_default(sessions):
    bands = [{"name": "合格", "min_score": 0, "max_score": 100}]
    draft = standards.create_standard(actor="synthetic-user", name="合成首页标准", scene="frontpage",
                                      base_score=100, grade_bands=bands, veto_grade="合格")
    assert draft["rule_set_key"] == FRONTPAGE_RULE_SET_KEY
    saved = standards.save_items(draft["id"], actor="synthetic-user", version_seq=1,
                                 groups=[{"group_name": "首页"}], items=[{
                                     "group_name": "首页", "rule_id": FRONTPAGE_RULE_IDS[0],
                                     "deduction": 2, "department_scope_mode": "all", "department_refs": [],
                                 }])
    with pytest.raises(standards.ScoringStandardInvalid):
        standards.save_items(draft["id"], actor="synthetic-user", version_seq=saved["version_seq"],
                             groups=[{"group_name": "首页"}], items=[{
                                 "group_name": "首页", "rule_id": "LX0609-001", "deduction": 2,
                                 "department_scope_mode": "all", "department_refs": [],
                             }])
    active = standards.activate_standard(draft["id"], actor="synthetic-user", version_seq=saved["version_seq"])
    assert active["is_default"] is True and active["scene"] == "frontpage"
    assert standards.get_default_standard("frontpage")["id"] == active["id"]
    assert standards.get_default_standard("final") is None
    assert standards.get_default_standard("outpatient") is None
