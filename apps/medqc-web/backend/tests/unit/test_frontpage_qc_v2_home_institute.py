"""首页质控默认只看本院：病历池按机构过滤，以及本院机构的判定。只用合成机构与别名。"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.routers import frontpage_qc_v2 as api
from app.services.qc_workspace import record_repository as module


@pytest.fixture()
def repo():
    engine = create_engine("sqlite:///:memory:")
    for model in (module.MedicalRecordFrontpage, module.InpatRegistration, module.AdmissionRecord, module.DischargeRecord):
        model.__table__.create(bind=engine)
    session = Session(engine)
    for institute, patient, dept in (("HOME", "C01", "内科"), ("HOME", "C02", "外科"), ("SYN-TEST", "C90", "测试科室")):
        session.add(
            module.MedicalRecordFrontpage(
                institute_id=institute,
                patient_id=patient,
                visit_id=f"{patient}-V1",
                discharge_dept_name=dept,
                admission_datetime=datetime(2026, 3, 1, 9),
                discharge_datetime=datetime(2026, 3, 8, 10),
            )
        )
    session.commit()
    yield module.RecordRepository(session_factory=lambda: session)
    session.close()
    engine.dispose()


def _list(repo, **kwargs):
    return repo.list_records(
        scope="final", department=None, doctor=None, date_field="discharge", start_date=None, end_date=None,
        keyword=None, page=1, page_size=10, **kwargs,
    )


def test_repository_filters_by_institute_only_when_given(repo):
    assert _list(repo).total == 3
    assert _list(repo, institute_id="HOME").total == 2
    assert {r["institute_id"] for r in _list(repo, institute_id="SYN-TEST").items} == {"SYN-TEST"}

    collected = repo.collect_records(
        scope="final", department=None, doctor=None, date_field="discharge", start_date=None, end_date=None,
        keyword=None, institute_id="HOME",
    )
    assert len(collected) == 2

    assert "测试科室" in repo.get_record_filters(scope="final", department=None)["departments"]
    assert "测试科室" not in repo.get_record_filters(scope="final", department=None, institute_id="HOME")["departments"]


@pytest.fixture()
def resolver(repo, monkeypatch):
    def configure(value):
        import app.services.etl_sync as etl_sync

        monkeypatch.setattr(etl_sync, "load_db_config", lambda: {"default_institute_id": value})
        monkeypatch.setattr(api, "get_record_repository", lambda: repo)
        api._home_institute_cache.update(value=None, at=None)
        return api.get_home_institute()

    yield configure
    api._home_institute_cache.update(value=None, at=None)


def test_home_institute_is_configured_value_with_records(resolver):
    assert resolver("HOME") == "HOME"


def test_home_institute_ignores_value_without_records(resolver):
    # 沿用默认 LOCAL-HOSPITAL 而病历池里没有该机构时，不能按它过滤把真实病历藏掉
    assert resolver("LOCAL-HOSPITAL") == ""
    assert resolver("") == ""
