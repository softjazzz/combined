"""真实SQLite默认配置到实际形式质控路由；病例读取/结果保存为内存替身。"""
import threading

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCScoringGroup, QCScoringItem, QCScoringStandard
from app.services import scoring_standard_service as standards
from tests.unit.test_frontpage_formal_qc_modern_identity import (
    _EndpointEnv, _call_endpoint, _identity_payload, _sheet,
)
from tests.unit.test_frontpage_scoring_service import standard


def test_route_consumes_persisted_default_off_event_loop_without_rewriting_history(monkeypatch):
    loader = standards.get_default_standard
    env = _EndpointEnv(monkeypatch)
    sheet = _sheet()
    sheet["hospitalization"] = {"discharge_dept": "合成科室"}
    env.use_sheet(sheet)
    engine = sa.create_engine("sqlite://", poolclass=StaticPool,
                              connect_args={"check_same_thread": False})
    for model in (QCScoringStandard, QCScoringGroup, QCScoringItem):
        model.__table__.create(engine)
    monkeypatch.setattr(standards, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    calls = []

    def observed(scene):
        calls.append((scene, threading.get_ident()))
        return loader(scene)

    monkeypatch.setattr(standards, "get_default_standard", observed)
    try:
        chosen = standard()
        draft = standards.create_standard(actor="synthetic-user", name="合成路由首页标准", scene="frontpage",
                                           base_score=100, grade_bands=chosen["grade_bands"], veto_grade="乙")
        saved = standards.save_items(draft["id"], actor="synthetic-user", version_seq=draft["version_seq"],
                                     groups=chosen["groups"], items=chosen["items"])
        active = standards.activate_standard(saved["id"], actor="synthetic-user", version_seq=saved["version_seq"])
        response = _call_endpoint(_identity_payload())
        data = response["data"]
        assert response["success"] is True
        assert data["scoring"]["status"] == "scored" and data["scoring"]["score"] == 98
        assert data["scoring"]["standard_id"] == active["id"]
        assert len(calls) == 1 and calls[0][0] == "frontpage"
        assert calls[0][1] != threading.get_ident()
        assert data["pass_rate"] == round(data["passed"] / data["total_rules"] * 100, 1)
        assert "scoring" not in env.persistence.calls[0]["result"]
        original_saved = env.persistence.calls[0]["result"]
        standards.archive_standard(active["id"], actor="synthetic-user", version_seq=active["version_seq"])
        repeated = _call_endpoint(_identity_payload())["data"]
        assert repeated["scoring"]["status"] == "no_standard" and repeated["scoring"]["score"] is None
        assert repeated["results"] == data["results"] and repeated["pass_rate"] == data["pass_rate"]
        assert env.persistence.calls[0]["result"] == original_saved
    finally:
        engine.dispose()
