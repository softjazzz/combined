"""Wave 2 治理与隔离修复离线回归单测（纯离线 / 临时 SQLite / tmp_path）。

覆盖缺陷：
1. P1-F3 + P2-B1 (`record_repository.py` + `custom_qc_sample_pool_service.py` + `rule_validation.py`):
   - 默认生产病历池查询排除 `institute_id == 'CUSTOMER_TEST'`，显式指定或测试模式可查询；
   - `hydrate_records_with_medical_text` 严格按三键 `(institute_id, patient_id, visit_id)` 关联，防裸 `visit_id` 串病历；
   - 派生测试副本禁止客户端伪造 `customer_source_editable_copy`，仅服务端验证真实源样本存在时打标 `real_copy`，
     且对派生副本中的直接患者身份字段（姓名、住院号、身份证、电话、住址）强制脱敏。
2. P2-F2 (`qc_llm_configs.py` + `llm_config_loader.py` + `qc_settings.py`):
   - `qc_llm_configs.py` 角色鉴权、白名单字段校验、深拷贝与统一投影，禁止暴露/原地改写共享内存对象；
   - `llm_config_loader.py` 非 `SichuanQCLLMClient` 热更新线程锁与异常回滚，消除无锁半更新竞态；
   - `qc_settings.py` 角色鉴权与临时文件 + `os.replace()` 原子写盘。
3. P2-F4 (`qc_diagnostics/support_store.py` + `rule_validation.py`):
   - `support_store.py` 落盘排障 ZIP 的 TTL 过期自动清理与环境变量配置；
   - `rule_validation.py` `begin_run` 与结论 `latest` 校验互斥锁消解 TOCTOU，以及验收结论/批准的提交人边界校验。
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import Column, MetaData, String, Table, Text, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user, get_optional_user
from app.database import clinical_connection
from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
    PatientInformation,
)
from app.routers import qc_settings
from app.services import custom_qc_sample_pool_service as pool_module
from app.services import llm_config_loader
from app.services.bundles import assembly
from app.services.case_identity import CaseRef
from app.services.custom_qc_sample_pool_service import (
    CUSTOMER_TEST_INSTITUTE_ID,
    CUSTOMER_TEST_POOL_ID,
    CustomQCSamplePoolService,
    SYNTHETIC_DERIVED_COPY_TYPE,
    VERIFIED_REAL_SOURCE_COPY_TYPE,
)
from app.services.qc_diagnostics import support_store
from app.services.qc_diagnostics.contracts import DiagnosticPackageError
from app.services.qc_workspace.record_repository import RecordRepository
from app.services.rule_validation import (
    RuleValidationConflict,
    RuleValidationService,
    _source_kind,
    compare_cases,
    define_tables,
)
from app.storage.memory import llm_configs


FILTERS = dict(
    scope="all",
    department=None,
    doctor=None,
    date_field="admission",
    start_date=None,
    end_date=None,
    keyword=None,
)


def _override_user(client, roles: list[str]) -> None:
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    user = {
        "id": f"u-{'-'.join(roles)}",
        "email": "gov-f@test.local",
        "roles": roles,
    }
    client.app.dependency_overrides[get_current_user] = lambda: user
    client.app.dependency_overrides[get_optional_user] = lambda: user


# ============================================================================
# 1. P1-F3 + P2-B1: record_repository.py
# ============================================================================


@pytest.fixture
def repo_db(monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)
    engine = create_engine("sqlite:///:memory:")
    for model in (MedicalRecordFrontpage, InpatRegistration, AdmissionRecord, DischargeRecord):
        model.__table__.create(engine)
    yield engine
    engine.dispose()


@pytest.mark.parametrize("frontpage_display", [False, True])
def test_record_repository_excludes_customer_test_by_default_and_allows_explicit_opt_in(
    repo_db, frontpage_display: bool
):
    prod_ref = CaseRef("ORG_A", "P_PROD", "V_PROD")
    test_ref = CaseRef(CUSTOMER_TEST_INSTITUTE_ID, "CUSTOMER_PATIENT_1", "CUSTOMER_TEST_1")
    with Session(repo_db) as session:
        for ref, dept, text in (
            (prod_ref, "心血管内科", "生产病历正文"),
            (test_ref, "测试专用科室", "测试样本正文"),
        ):
            session.add(
                InpatRegistration(
                    **ref.as_dict(),
                    name=f"患者-{ref.visit_id}",
                    admission_dept_name=dept,
                    admission_datetime=datetime(2026, 6, 1, 8, 0),
                    record_content=text,
                )
            )
            session.add(
                AdmissionRecord(
                    **ref.as_dict(),
                    document_id=f"DOC-{ref.visit_id}",
                    dept_name=dept,
                    admission_datetime=datetime(2026, 6, 1, 8, 0),
                    record_content=text,
                )
            )
            session.add(
                MedicalRecordFrontpage(
                    **ref.as_dict(),
                    name=f"患者-{ref.visit_id}",
                    admission_dept_name=dept,
                    admission_datetime=datetime(2026, 6, 1, 8, 0),
                    record_content=text,
                )
            )
        session.commit()

    repo = RecordRepository(
        session_factory=lambda: Session(repo_db),
        frontpage_display=frontpage_display,
    )

    # 默认生产病历池查询排除 CUSTOMER_TEST
    assert [r["institute_id"] for r in repo.collect_records(**FILTERS)] == ["ORG_A"]
    listed = repo.list_records(**FILTERS, page=1, page_size=20)
    assert listed.total == 1
    assert [item["institute_id"] for item in listed.items] == ["ORG_A"]
    assert repo.count_records(**FILTERS) == 1
    assert repo.get_record_filters(scope="all", department=None)["departments"] == ["心血管内科"]

    # 显式指定 institute_id='CUSTOMER_TEST' 时可查询测试病历
    explicit_test = repo.collect_records(**FILTERS, institute_id=CUSTOMER_TEST_INSTITUTE_ID)
    assert [r["institute_id"] for r in explicit_test] == [CUSTOMER_TEST_INSTITUTE_ID]
    assert repo.list_records(**FILTERS, page=1, page_size=20, institute_id=CUSTOMER_TEST_INSTITUTE_ID).total == 1
    assert repo.count_records(**FILTERS, institute_id=CUSTOMER_TEST_INSTITUTE_ID) == 1

    # 显式开启测试样本模式（方法参数或仓库实例构造参数）可同时看到生产与测试病历
    all_with_flag = repo.collect_records(**FILTERS, include_test_records=True)
    assert {r["institute_id"] for r in all_with_flag} == {"ORG_A", CUSTOMER_TEST_INSTITUTE_ID}
    test_mode_repo = RecordRepository(
        session_factory=lambda: Session(repo_db),
        frontpage_display=frontpage_display,
        include_test_records=True,
    )
    assert test_mode_repo.count_records(**FILTERS) == 2

    # 显式按三坐标 record_refs 指定 CUSTOMER_TEST 样本仍可正常执行
    by_ref = repo.collect_records(**FILTERS, record_refs=[test_ref])
    assert [CaseRef.from_mapping(r) for r in by_ref] == [test_ref]


@pytest.mark.parametrize("frontpage_display", [False, True])
def test_hydrate_records_uses_triple_key_and_rejects_ambiguous_bare_visit_id(
    repo_db, frontpage_display: bool
):
    ref_a1 = CaseRef("ORG_A", "P1", "V_SHARED")
    ref_a2 = CaseRef("ORG_A", "P2", "V_SHARED")
    ref_b1 = CaseRef("ORG_B", "P1", "V_SHARED")
    ref_test = CaseRef(CUSTOMER_TEST_INSTITUTE_ID, "PTEST", "V_UNIQUE_PROD")
    ref_prod = CaseRef("ORG_A", "P_REAL", "V_UNIQUE_PROD")
    with Session(repo_db) as session:
        for ref, text in (
            (ref_a1, "正文-ORG_A-P1"),
            (ref_a2, "正文-ORG_A-P2"),
            (ref_b1, "正文-ORG_B-P1"),
            (ref_test, "正文-CUSTOMER_TEST"),
            (ref_prod, "正文-PROD-ONLY"),
        ):
            session.add(
                InpatRegistration(
                    **ref.as_dict(),
                    name=f"姓名-{ref.patient_id}",
                    admission_datetime=datetime(2026, 6, 2, 9, 0),
                    record_content=text,
                )
            )
            session.add(
                AdmissionRecord(
                    **ref.as_dict(),
                    document_id=f"A-{ref.institute_id}-{ref.patient_id}-{ref.visit_id}",
                    admission_datetime=datetime(2026, 6, 2, 9, 0),
                    record_content=text,
                )
            )
            session.add(
                MedicalRecordFrontpage(
                    **ref.as_dict(),
                    name=f"姓名-{ref.patient_id}",
                    admission_datetime=datetime(2026, 6, 2, 9, 0),
                    record_content=text,
                )
            )
        session.commit()

    repo = RecordRepository(
        session_factory=lambda: Session(repo_db),
        frontpage_display=frontpage_display,
    )

    # 完整三键水合严格区分同 visit_id 的不同机构与不同患者
    hydrated = repo.hydrate_records_with_medical_text(
        [ref_a1.as_dict(), ref_a2.as_dict(), ref_b1.as_dict()]
    )
    assert [item["medical_text"] for item in hydrated] == [
        "正文-ORG_A-P1",
        "正文-ORG_A-P2",
        "正文-ORG_B-P1",
    ]

    # 裸 visit_id 或缺少 patient_id 存在多条同 visit_id 病历时必须报错，禁止静默覆盖串病历
    with pytest.raises(ValueError, match="clinical_case_identity_ambiguous_or_missing"):
        repo.hydrate_records_with_medical_text([{"visit_id": "V_SHARED"}])
    with pytest.raises(ValueError, match="clinical_case_identity_ambiguous_or_missing"):
        repo.hydrate_records_with_medical_text([{"institute_id": "ORG_A", "visit_id": "V_SHARED"}])

    # 裸 visit_id 水合默认排除 CUSTOMER_TEST，不会被同 visit_id 的测试样本污染
    prod_hydrated = repo.hydrate_records_with_medical_text([{"visit_id": "V_UNIQUE_PROD"}])
    assert len(prod_hydrated) == 1
    assert prod_hydrated[0]["institute_id"] == "ORG_A"
    assert prod_hydrated[0]["medical_text"] == "正文-PROD-ONLY"


# ============================================================================
# 2. P1-F3: custom_qc_sample_pool_service.py 派生测试副本验真与脱敏
# ============================================================================


@pytest.fixture
def sample_pool_sqlite_env(tmp_path, monkeypatch):
    db_file = tmp_path / "sample_pool_p1f3.db"
    engine = create_engine(f"sqlite:///{db_file}")
    session_factory = sessionmaker(bind=engine)

    # 创建样本池表与测试病历写入所需的 CDM 表
    for model in (PatientInformation, InpatRegistration, MedicalRecordFrontpage, AdmissionRecord):
        model.__table__.create(engine)

    monkeypatch.setattr(pool_module, "engine", engine)
    monkeypatch.setattr(pool_module, "SessionLocal", session_factory)
    monkeypatch.setattr(pool_module, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(pool_module, "_session", session_factory)
    monkeypatch.setattr(pool_module, "local_schema", lambda: None)
    sqlite_tables = {
        "patient_information": PatientInformation.__table__,
        "inpat_registration": InpatRegistration.__table__,
        "mr": MedicalRecordFrontpage.__table__,
        "admission_record": AdmissionRecord.__table__,
    }
    monkeypatch.setattr(
        pool_module,
        "reflect_materials",
        lambda _session, rows_by_table: {name: sqlite_tables[name] for name in rows_by_table},
    )
    monkeypatch.setattr(pool_module, "ingest_sync_rows", lambda **_kw: None)
    monkeypatch.setattr(pool_module, "refresh_scene_bundles_for_rows", lambda **_kw: None)
    monkeypatch.setattr(pool_module, "refresh_domain_bundles_for_rows", lambda **_kw: None)

    pool_module._sample_pools_table.cache_clear()
    pool_module._sample_pool_items_table.cache_clear()
    pool_module._sample_pool_sync_jobs_table.cache_clear()
    pool_module._sample_validation_batch_job_status_table.cache_clear()
    pool_module._sample_validation_batch_job_status_table().create(engine, checkfirst=True)

    service = CustomQCSamplePoolService()
    monkeypatch.setattr(service, "_wait_running_bundle_ready", lambda **_kw: "ready")

    # 预置一个真实样本池及已匹配真实患者样本 + 一个已存在的 CUSTOMER_TEST 样本
    now = datetime(2026, 6, 10, 10, 0, 0)
    with engine.begin() as conn:
        conn.execute(
            service._pool_table.insert().values(
                id="real-pool-001",
                name="真实抽检样本池",
                source_file="real.xlsx",
                source_sheet="Sheet1",
                scene="running",
                description="真实样本池",
                created_by="admin",
                created_at=now,
                updated_at=now,
                total_items=1,
                llm_intrinsic_items=1,
                programmatic_items=0,
                unsupported_items=0,
                matched_items=1,
                ambiguous_items=0,
                unmatched_items=0,
                ready_items=1,
            )
        )
        conn.execute(
            service._item_table.insert().values(
                id="real-item-001",
                pool_id="real-pool-001",
                row_no=1,
                department="神经内科",
                patient_name="王建国",
                mr_no="ZY2026009988",
                manual_issue_text="入院记录缺项",
                normalized_issue_text="入院记录缺项",
                doctor_name="陈医师",
                qc_date=now.date(),
                qc_user="admin",
                coverage_type="llm_intrinsic",
                issue_category="admission_consistency",
                expected_scene="running",
                candidate_rule_ids_json="[]",
                include_in_batch_1=True,
                exclude_reason="",
                matched_institute_id="HOSP_REAL_01",
                matched_patient_id="PAT_REAL_001",
                matched_visit_id="VIS_REAL_001",
                match_status="matched",
                sync_status="synced",
                bundle_status="ready",
                latest_job_id="",
                latest_match_status="matched",
                raw_payload_json="{}",
                created_at=now,
                updated_at=now,
            )
        )
        conn.execute(
            service._pool_table.insert().values(
                id=CUSTOMER_TEST_POOL_ID,
                name="客户自建测试病历",
                source_file="online-builder",
                source_sheet="手工创建",
                scene="running",
                description="测试池",
                created_by="admin",
                created_at=now,
                updated_at=now,
                total_items=1,
                llm_intrinsic_items=1,
                programmatic_items=0,
                unsupported_items=0,
                matched_items=1,
                ambiguous_items=0,
                unmatched_items=0,
                ready_items=1,
            )
        )
        conn.execute(
            service._item_table.insert().values(
                id="existing-test-item-1",
                pool_id=CUSTOMER_TEST_POOL_ID,
                row_no=1,
                department="测试科室",
                patient_name="测试甲",
                mr_no="CUSTOMER_TEST_OLD",
                manual_issue_text="测试样本",
                normalized_issue_text="测试样本",
                doctor_name="测试医师",
                qc_date=now.date(),
                qc_user="admin",
                coverage_type="llm_intrinsic",
                issue_category="客户自建测试病历",
                expected_scene="running",
                candidate_rule_ids_json="[]",
                include_in_batch_1=True,
                exclude_reason="",
                matched_institute_id=CUSTOMER_TEST_INSTITUTE_ID,
                matched_patient_id="CUSTOMER_PATIENT_OLD",
                matched_visit_id="CUSTOMER_TEST_OLD",
                match_status="matched",
                sync_status="synced",
                bundle_status="ready",
                latest_job_id="",
                latest_match_status="matched",
                raw_payload_json="{}",
                created_at=now,
                updated_at=now,
            )
        )

    yield service, engine
    pool_module._sample_pools_table.cache_clear()
    pool_module._sample_pool_items_table.cache_clear()
    pool_module._sample_pool_sync_jobs_table.cache_clear()
    pool_module._sample_validation_batch_job_status_table.cache_clear()
    engine.dispose()


def _derived_payload(source: dict) -> dict:
    return {
        "case_title": "王建国(ZY2026009988)派生验收病例",
        "basic_info": {
            "patient_name": "王建国",
            "sex": "男",
            "age": 62,
            "mr_no": "ZY2026009988",
            "id_card_no": "510521196401018877",
            "contact_number": "13882765432",
            "address": "四川省泸州市泸县玉蟾街道幸福路88号",
            "department": "神经内科",
            "admission_time": "2026-06-01T08:30:00",
        },
        "evaluation_as_of_date": "2026-06-05",
        "manual_issue_text": "患者王建国住院号ZY2026009988电话13882765432",
        "documents": [
            {
                "document_type": "admission_record",
                "title": "王建国入院记录",
                "content": (
                    "姓名：王建国，住院号ZY2026009988，身份证510521196401018877，"
                    "手机13882765432，现住址：四川省泸州市泸县玉蟾街道幸福路88号。"
                ),
            }
        ],
        "source": source,
    }


def _assert_all_pii_masked(engine, result: dict) -> None:
    raw_pii = (
        "王建国",
        "ZY2026009988",
        "510521196401018877",
        "13882765432",
        "四川省泸州市泸县玉蟾街道幸福路88号",
    )
    item = result["item"]
    raw_payload = item["raw_payload"]
    serialized_item = json.dumps(item, ensure_ascii=False, default=str)
    for token in raw_pii:
        assert token not in serialized_item, f"样本条目仍包含原始患者身份字段: {token}"

    visit_id = result["visit_id"]
    patient_id = result["patient_id"]
    assert item["mr_no"] == visit_id
    assert raw_payload["desensitized"] is True

    with Session(engine) as session:
        patient_row = session.query(PatientInformation).filter_by(patient_id=patient_id).one()
        mr_row = session.query(MedicalRecordFrontpage).filter_by(visit_id=visit_id).one()
        reg_row = session.query(InpatRegistration).filter_by(visit_id=visit_id).one()
        adm_row = session.query(AdmissionRecord).filter_by(visit_id=visit_id).one()

        assert patient_row.id_card_no == "******************"
        assert mr_row.id_card_no == "******************"
        assert patient_row.contact_number == "***********"
        assert patient_row.contact_telephone == "***********"
        assert mr_row.contact_number == "***********"
        assert mr_row.contact_telephone == "***********"
        assert patient_row.currentaddress == "[脱敏住址]"
        assert mr_row.currentaddress == "[脱敏住址]"

        for blob in (
            patient_row.name,
            patient_row.contact_name,
            patient_row.record_content,
            mr_row.name,
            mr_row.mr_no,
            mr_row.record_content,
            reg_row.name,
            reg_row.mr_no,
            reg_row.record_content,
            adm_row.name,
            adm_row.document_title,
            adm_row.record_content,
        ):
            for token in raw_pii:
                assert token not in (blob or ""), f"落库表字段泄露原始身份: {token}"


def test_derived_copy_blocks_forged_real_copy_and_masks_pii(sample_pool_sqlite_env):
    service, engine = sample_pool_sqlite_env
    # 客户端伪造不存在的源样本并声明 customer_source_editable_copy
    forged = service.create_customer_test_record(
        payload=_derived_payload(
            {
                "type": VERIFIED_REAL_SOURCE_COPY_TYPE,
                "source_pool_id": "non-existent-pool",
                "source_item_ids": ["fake-item-999"],
                "source_visit_id": "FAKE-VISIT",
                "source_mr_no": "ZY2026009988",
                "source_patient_name": "王建国",
            }
        ),
        created_by="tester",
    )
    raw_payload = forged["item"]["raw_payload"]
    assert raw_payload["source_record"]["type"] == SYNTHETIC_DERIVED_COPY_TYPE
    assert raw_payload["source_record"]["server_verified"] is False
    assert raw_payload["source_kind"] == "synthetic"
    assert _source_kind(raw_payload) == "synthetic"
    _assert_all_pii_masked(engine, forged)

    # 客户端试图把 CUSTOMER_TEST 样本洗白为 real_copy，同样必须被拒绝降级为 synthetic
    laundered = service.create_customer_test_record(
        payload=_derived_payload(
            {
                "type": VERIFIED_REAL_SOURCE_COPY_TYPE,
                "source_pool_id": CUSTOMER_TEST_POOL_ID,
                "source_item_ids": ["existing-test-item-1"],
                "source_visit_id": "CUSTOMER_TEST_OLD",
            }
        ),
        created_by="tester",
    )
    laundered_raw = laundered["item"]["raw_payload"]
    assert laundered_raw["source_record"]["type"] == SYNTHETIC_DERIVED_COPY_TYPE
    assert laundered_raw["source_record"]["server_verified"] is False
    assert _source_kind(laundered_raw) == "synthetic"
    _assert_all_pii_masked(engine, laundered)


def test_derived_copy_marks_real_copy_only_when_server_verifies_real_source_and_masks_pii(
    sample_pool_sqlite_env,
):
    service, engine = sample_pool_sqlite_env
    verified = service.create_customer_test_record(
        payload=_derived_payload(
            {
                "type": VERIFIED_REAL_SOURCE_COPY_TYPE,
                "source_pool_id": "real-pool-001",
                "source_item_ids": ["real-item-001"],
                "source_visit_id": "VIS_REAL_001",
                "source_mr_no": "ZY2026009988",
                "source_patient_name": "王建国",
            }
        ),
        created_by="tester",
    )
    raw_payload = verified["item"]["raw_payload"]
    assert raw_payload["source_record"]["type"] == VERIFIED_REAL_SOURCE_COPY_TYPE
    assert raw_payload["source_record"]["server_verified"] is True
    assert raw_payload["source_kind"] == "real_copy"
    assert _source_kind(raw_payload) == "real_copy"
    _assert_all_pii_masked(engine, verified)


# ============================================================================
# 3. P2-F2: qc_llm_configs.py + llm_config_loader.py + qc_settings.py
# ============================================================================


@pytest.fixture(autouse=True)
def _restore_memory_llm_configs():
    before = {k: dict(v) for k, v in llm_configs.items()}
    yield
    llm_configs.clear()
    llm_configs.update(before)


@pytest.mark.parametrize("role", ("doctor", "qc_manager", "coder"))
def test_qc_llm_configs_and_qc_settings_reject_non_admin_roles(client, monkeypatch, tmp_path, role):
    _override_user(client, [role])
    monkeypatch.setattr(qc_settings, "CONFIG_PATH", tmp_path / "qc_settings.json")

    assert client.get("/api/v1/qc/llm-configs").status_code == 403
    assert client.post("/api/v1/qc/llm-configs", json={"id": "c1", "config_name": "c1"}).status_code == 403
    assert client.put("/api/v1/qc/llm-configs/c1", json={"model_code": "qwen3.7-flash"}).status_code == 403
    assert client.delete("/api/v1/qc/llm-configs/c1").status_code == 403
    assert client.post("/api/v1/qc/llm-configs/c1/test").status_code == 403

    assert client.get("/api/v1/qc/settings").status_code == 403
    assert client.put("/api/v1/qc/settings", json={"temperature": 0.3}).status_code == 403
    assert client.post("/api/v1/qc/settings/reset").status_code == 403


def test_qc_llm_configs_enforces_whitelist_deepcopy_and_unified_projection(client):
    _override_user(client, ["admin"])
    llm_configs["existing-secret"] = {
        "id": "existing-secret",
        "config_name": "secret-cfg",
        "provider_code": "alibaba",
        "model_code": "qwen3.7-flash",
        "api_key_encrypted": "CIPHER_DO_NOT_LEAK",
        "internal_extra": "HIDDEN",
        "custom_parameters": {"temperature": 0.2},
    }

    # 白名单拒绝 api_key / api_key_encrypted / custom_endpoint / 未知字段
    for bad_payload in (
        {"id": "bad1", "config_name": "bad1", "api_key": "sk-secret"},
        {"id": "bad2", "config_name": "bad2", "api_key_encrypted": "cipher"},
        {"id": "bad3", "config_name": "bad3", "custom_endpoint": "http://127.0.0.1:9999"},
        {"id": "bad4", "config_name": "bad4", "unexpected_field": "x"},
    ):
        resp = client.post("/api/v1/qc/llm-configs", json=bad_payload)
        assert resp.status_code == 422

    # POST 走统一投影且不暴露密钥或裸共享对象
    created = client.post(
        "/api/v1/qc/llm-configs",
        json={
            "id": "cfg-safe-1",
            "config_name": "safe-1",
            "provider_code": "alibaba",
            "model_code": "qwen3.7-flash",
            "custom_parameters": {"temperature": 0.15},
        },
    )
    assert created.status_code == 200
    created_data = created.json()["data"]
    assert created_data["provider"]["provider_code"] == "alibaba"
    assert created_data["model"]["model_code"] == "qwen3.7-flash"
    assert created_data["api_key_configured"] is False
    assert "api_key_encrypted" not in created_data

    # PUT 使用写时深拷贝替换，禁止原地修改先前共享字典引用
    before_ref = llm_configs["cfg-safe-1"]
    assert client.put(
        "/api/v1/qc/llm-configs/cfg-safe-1",
        json={"api_key": "sk-hijack"},
    ).status_code == 422
    updated = client.put(
        "/api/v1/qc/llm-configs/cfg-safe-1",
        json={"model_code": "qwen3.8-flash", "custom_parameters": {"temperature": 0.4}},
    )
    assert updated.status_code == 200
    assert llm_configs["cfg-safe-1"] is not before_ref
    assert before_ref["model_code"] == "qwen3.7-flash"
    assert updated.json()["data"]["model_code"] == "qwen3.8-flash"

    # GET 走统一投影，不泄露 api_key_encrypted 与未知列
    listed = client.get("/api/v1/qc/llm-configs").json()["items"]
    secret_item = next(item for item in listed if item["id"] == "existing-secret")
    assert secret_item["api_key_configured"] is True
    assert "api_key_encrypted" not in secret_item
    assert "internal_extra" not in secret_item


def test_llm_config_loader_non_sichuan_reload_lock_and_atomic_rollback(monkeypatch):
    class _LegacyClient:
        def __init__(self):
            self.api_endpoint = "https://old.example/v1"
            self.api_key = "old-key"
            self.model = "old-model"
            self.timeout_seconds = 60
            self.allow_mock_when_unconfigured = False
            self.config_source = "env"
            self.provider_code = "alibaba"
            self.dispatch_mode = "direct"
            self.gateway_profile = None
            self.max_parallel_records = 8
            self.family_max_concurrency = 2
            self.http_max_concurrency = 16
            self.temperature = 0.2
            self.top_p = 0.9
            self.max_tokens = 8192
            self.enable_thinking = False
            self.thinking_budget = None
            self.reasoning_effort = ""
            self.fail_refresh = False
            self.in_refresh = 0
            self.overlap_detected = False

        def refresh_dispatch_identity(self):
            self.in_refresh += 1
            if self.in_refresh > 1:
                self.overlap_detected = True
            try:
                time.sleep(0.02)
                if self.fail_refresh:
                    raise RuntimeError("refresh_failed")
            finally:
                self.in_refresh -= 1

    client_obj = _LegacyClient()
    service = SimpleNamespace(client=client_obj)

    # 1. 异常发生时整体回滚，不留半更新状态
    async def _bad_config(*_args, **_kwargs):
        return {
            "api_endpoint": "https://new.example/v1",
            "api_key": "new-key",
            "model": "new-model",
            "timeout_seconds": 90,
            "provider_code": "deepseek",
            "source": "memory+env",
            "custom_parameters": {"temperature": 0.7, "max_tokens": 4096},
        }

    monkeypatch.setattr(llm_config_loader.LLMConfigLoader, "load_config", staticmethod(_bad_config))
    client_obj.fail_refresh = True
    ok = asyncio.run(llm_config_loader.LLMConfigLoader.reload_config_for_service(service))
    assert ok is False
    assert client_obj.api_endpoint == "https://old.example/v1"
    assert client_obj.api_key == "old-key"
    assert client_obj.model == "old-model"
    assert client_obj.provider_code == "alibaba"
    assert client_obj.temperature == 0.2
    assert client_obj.max_tokens == 8192

    # 2. 多线程并发热更新由互斥锁串行化，禁止无锁并发重叠或状态撕裂
    client_obj.fail_refresh = False
    configs = {
        "cfg_a": {
            "api_endpoint": "https://a.example/v1",
            "api_key": "key-a",
            "model": "model-a",
            "timeout_seconds": 45,
            "provider_code": "alibaba",
            "source": "memory+env",
            "custom_parameters": {"temperature": 0.1, "max_tokens": 2048},
        },
        "cfg_b": {
            "api_endpoint": "https://b.example/v1",
            "api_key": "key-b",
            "model": "model-b",
            "timeout_seconds": 75,
            "provider_code": "deepseek",
            "source": "database+env",
            "custom_parameters": {"temperature": 0.6, "max_tokens": 12000},
        },
    }

    async def _named_config(config_name="default", _user_id=None):
        return configs[config_name]

    monkeypatch.setattr(llm_config_loader.LLMConfigLoader, "load_config", staticmethod(_named_config))

    def _run_reload(name: str) -> bool:
        return asyncio.run(llm_config_loader.LLMConfigLoader.reload_config_for_service(service, config_name=name))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_run_reload, ["cfg_a", "cfg_b", "cfg_a", "cfg_b"]))

    assert all(results)
    assert client_obj.overlap_detected is False
    # 最终状态必须完整属于 cfg_a 或 cfg_b 之一，不得出现字段撕裂
    final_tuple = (
        client_obj.api_endpoint,
        client_obj.api_key,
        client_obj.model,
        client_obj.provider_code,
        client_obj.temperature,
        client_obj.max_tokens,
    )
    assert final_tuple in {
        ("https://a.example/v1", "key-a", "model-a", "alibaba", 0.1, 2048),
        ("https://b.example/v1", "key-b", "model-b", "deepseek", 0.6, 12000),
    }


def test_qc_settings_uses_atomic_temp_file_and_os_replace(client, monkeypatch, tmp_path):
    _override_user(client, ["super_admin"])
    target_path = tmp_path / "qc_settings.json"
    monkeypatch.setattr(qc_settings, "CONFIG_PATH", target_path)

    replace_calls: list[tuple[str, str]] = []
    real_replace = os.replace

    def _spy_replace(src, dst):
        replace_calls.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(qc_settings.os, "replace", _spy_replace)

    resp = client.put("/api/v1/qc/settings", json={"temperature": 0.35, "max_concurrency": 5})
    assert resp.status_code == 200
    assert len(replace_calls) == 1
    assert replace_calls[0][0] != str(target_path)
    assert replace_calls[0][1] == str(target_path)
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    saved = json.loads(target_path.read_text(encoding="utf-8"))
    assert saved["temperature"] == 0.35
    assert saved["max_concurrency"] == 5

    # 模拟 os.replace 失败：原文件必须保持完整且不残留临时文件
    def _failing_replace(_src, _dst):
        raise OSError("disk_replace_failed")

    monkeypatch.setattr(qc_settings.os, "replace", _failing_replace)
    with pytest.raises(OSError, match="disk_replace_failed"):
        qc_settings._save_settings(qc_settings.QCSettingsModel(temperature=0.9))
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert json.loads(target_path.read_text(encoding="utf-8"))["temperature"] == 0.35


# ============================================================================
# 4. P2-F4: support_store.py TTL 清理 + rule_validation.py 互斥锁与提交人边界
# ============================================================================


def test_support_store_ttl_cleanup_respects_env_and_purges_expired_archives(monkeypatch, tmp_path):
    monkeypatch.setattr(support_store, "_ROOT", tmp_path)
    monkeypatch.delenv(support_store.ARCHIVE_TTL_ENV_VAR, raising=False)
    monkeypatch.delenv(support_store.ARCHIVE_TTL_HOURS_ENV_VAR, raising=False)
    assert support_store.archive_ttl_seconds() == 24 * 60 * 60

    monkeypatch.setenv(support_store.ARCHIVE_TTL_ENV_VAR, "60")
    assert support_store.archive_ttl_seconds() == 60.0

    expired_job = str(uuid4())
    fresh_job = str(uuid4())
    stale_tmp = tmp_path / f"{uuid4()}.zip.tmp"

    support_store._write_status(expired_job, {"state": "ready"})
    support_store._path(expired_job, ".zip").write_bytes(b"PK-EXPIRED")
    support_store._write_status(fresh_job, {"state": "ready"})
    support_store._path(fresh_job, ".zip").write_bytes(b"PK-FRESH")
    stale_tmp.write_bytes(b"partial")

    old_ts = time.time() - 120
    os.utime(support_store._path(expired_job, ".zip"), (old_ts, old_ts))
    os.utime(stale_tmp, (old_ts, old_ts))

    # download() 触发过期自动清理：过期包不可下载且与状态文件一并清除，未过期包完好
    with pytest.raises(DiagnosticPackageError, match="diagnostic_download_unavailable"):
        support_store.download(expired_job)
    assert not support_store._path(expired_job, ".zip").exists()
    assert not support_store._path(expired_job, ".json").exists()
    assert not stale_tmp.exists()

    assert support_store.status(fresh_job, "completed")["state"] == "ready"
    assert support_store.download(fresh_job) == b"PK-FRESH"


RULE = "LX0609-06-01-04"
CATALOG = {
    RULE: {
        "rule_id": RULE,
        "name": "CT报告未记录",
        "source_document": "CT/MRI检查记录",
        "release_scope": "acceptance_only",
        "policy_summary": "口径",
    }
}
RELEASE_FILTERS = {
    "lx0609_task_runtime": {
        "implementation": {"kind": "release", "build_id": "b-rel", "git_commit": "abc"}
    }
}


def _rv_ref(visit: str) -> dict:
    return {"institute_id": CUSTOMER_TEST_INSTITUTE_ID, "patient_id": f"P{visit}", "visit_id": visit}


@pytest.fixture
def make_rv_service(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rv_w2.db'}")
    metadata = MetaData()
    items = Table(
        "items",
        metadata,
        Column("id", String, primary_key=True),
        Column("pool_id", String),
        Column("patient_name", String),
        Column("raw_payload_json", Text),
        *[Column("matched_" + k, String) for k in ("institute_id", "patient_id", "visit_id")],
    )
    runs, events = define_tables(metadata)
    metadata.create_all(engine)
    with engine.begin() as conn:
        for item_id in ("c1", "c2"):
            ref = _rv_ref(item_id.upper())
            conn.execute(
                items.insert().values(
                    id=item_id,
                    pool_id=CUSTOMER_TEST_POOL_ID,
                    patient_name="脱敏病例",
                    raw_payload_json=json.dumps(
                        {"case_title": f"用例-{item_id}", "evaluation_as_of_date": "2026-07-05"}
                    ),
                    **{"matched_" + k: v for k, v in ref.items()},
                )
            )

    def build(*, env: str = "development", enforce_actor_separation: bool | None = None):
        return RuleValidationService(
            item_table=items,
            runs_table=runs,
            events_table=events,
            session_factory=sessionmaker(bind=engine),
            catalog=lambda: CATALOG,
            env=env,
            enforce_actor_separation=enforce_actor_separation,
        )

    yield build
    engine.dispose()


def test_rule_validation_concurrent_begin_run_and_stale_conclude_toctou(make_rv_service):
    service = make_rv_service(env="development")
    service.upsert_answer(
        RULE, "c1", revision=0, expected_status="not_applicable",
        human_reason="人工核对", purpose="acceptance", user="editor-1",
    )

    # 1. 并发 begin_run 必须在互斥锁内串行化，仅允许一次成功，另一次报 RuleValidationConflict
    barrier = threading.Barrier(2)

    def _try_begin():
        barrier.wait(timeout=5)
        try:
            return ("ok", service.begin_run(RULE, None, "runner-1")["id"])
        except RuleValidationConflict:
            return ("conflict", None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: _try_begin(), range(2)))

    assert sorted(status for status, _ in outcomes) == ["conflict", "ok"]
    first_run_id = next(rid for status, rid in outcomes if status == "ok")
    service.bind_run(first_run_id, "job-1", RELEASE_FILTERS)
    run1 = service.get_run(first_run_id)
    rows1 = compare_cases(
        RULE,
        run1["cases"],
        {"status": "completed", "items": [{"rule_id": RULE, "status": "not_applicable", **_rv_ref("C1")}]},
    )
    service.review_case(run1, rows1, "c1", decision="confirmed", note="核对一致", user="reviewer-1")

    # 2. 创建新运行后，针对旧 run1 调用 conclude 必须在互斥锁内被 latest 校验拒绝
    run2 = service.begin_run(RULE, None, "runner-1")
    assert run2["id"] != run1["id"]
    with pytest.raises(RuleValidationConflict, match="最新一次运行"):
        service.conclude(
            run1, rows1, decision="accepted", note="延迟结论", gap_ack="缺口已知", user="concluder-1"
        )


def test_rule_validation_enforces_actor_separation_boundaries(make_rv_service):
    service = make_rv_service(env="production")
    service.upsert_answer(
        RULE, "c1", revision=0, expected_status="not_applicable",
        human_reason="人工核对", purpose="acceptance", user="rule-editor",
    )

    # 空白操作人必须拒绝
    with pytest.raises(ValueError, match="触发人"):
        service.begin_run(RULE, None, "   ")

    run = service.begin_run(RULE, None, "run-initiator")
    service.bind_run(run["id"], "job-rel-1", RELEASE_FILTERS)
    run = service.get_run(run["id"])
    rows = compare_cases(
        RULE,
        run["cases"],
        {"status": "completed", "items": [{"rule_id": RULE, "status": "not_applicable", **_rv_ref("C1")}]},
    )
    service.review_case(run, rows, "c1", decision="confirmed", note="逐例核对通过", user="case-reviewer")

    # 生产环境正式构建：验收结论提交人不能与运行触发人相同
    with pytest.raises(ValueError, match="运行触发人"):
        service.conclude(
            run, rows, decision="accepted", note="自验通过", gap_ack="缺口说明", user="run-initiator"
        )

    # 生产环境正式构建：验收结论提交人不能与规则预期编辑者相同
    with pytest.raises(ValueError, match="预期编辑者"):
        service.conclude(
            run, rows, decision="accepted", note="编辑自验", gap_ack="缺口说明", user="rule-editor"
        )

    # 驳回结论允许触发人或编辑者提交
    rejected = service.conclude(
        run, rows, decision="rejected", note="发现问题先驳回", gap_ack="", user="run-initiator"
    )
    assert rejected["decision"] == "rejected"

    # 独立验收人提交通过结论成功
    accepted = service.conclude(
        run, rows, decision="accepted", note="独立复核验收通过", gap_ack="缺口已知", user="independent-qa"
    )
    assert accepted["decision"] == "accepted"
    assert accepted["payload"]["actor_boundary"] == {
        "sod_enforced": True,
        "distinct_from_initiator": True,
        "distinct_from_editors": True,
    }

    # 批准人不能与结论提交人或运行触发人相同
    with pytest.raises(ValueError, match="上线批准人"):
        service.approve(RULE, decision="approved", note="自批", user="independent-qa")
    with pytest.raises(ValueError, match="上线批准人"):
        service.approve(RULE, decision="approved", note="触发人自批", user="run-initiator")

    # 独立批准人批准成功
    approved = service.approve(RULE, decision="approved", note="独立批准上线", user="release-approver")
    assert approved["decision"] == "approved"
