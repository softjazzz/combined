"""Wave 3 (clinical-d) 综合离线回归测试：覆盖 P1-D1/D2/D3/D4, P1-E5, P0-8, P2-B1, P2-D1, P2-D2。

全程使用内存/临时 SQLite 与 stub/mock，严禁连接正式库或真实 LLM。
"""
from __future__ import annotations

import inspect
import json
import logging
import threading
from io import BytesIO
from types import SimpleNamespace

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database.connection import Base


def _mem_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


# ============================================================================
# 1. P1-D1 + P1-E5 + P0-8: 首页抽取 / frontpage 路由 / 画像 / 快筛脱敏与三坐标
# ============================================================================


class TestFrontpageExtractionTriKeyAndPrivacy:
    def _build_cdm_sqlite_engine(self):
        eng = _mem_engine()
        with eng.begin() as conn:
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE inpat_registration (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        name TEXT,
                        sex_name TEXT,
                        age_year TEXT,
                        inpat_dept_name TEXT,
                        admission_datetime TEXT,
                        discharge_datetime TEXT
                    )
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE admission_record (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        record_content TEXT,
                        record_datetime TEXT
                    )
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE discharge_record (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        record_content TEXT,
                        record_datetime TEXT
                    )
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO inpat_registration VALUES
                        ('HOSP-A', 'P-A', 'V-DUP', '张三甲', '男', '52', '心内科', '2026-03-01 08:00:00', '2026-03-05 10:00:00'),
                        ('HOSP-B', 'P-B', 'V-DUP', '李四乙', '女', '41', '消化内科', '2026-03-02 09:00:00', '2026-03-06 11:00:00')
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO admission_record VALUES
                        ('HOSP-A', 'P-A', 'V-DUP', '患者张三甲，主诉胸痛3天，诊断冠心病。', '2026-03-01 09:00:00'),
                        ('HOSP-B', 'P-B', 'V-DUP', '患者李四乙，主诉腹痛2天，诊断急性胃炎。', '2026-03-02 10:00:00')
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO discharge_record VALUES
                        ('HOSP-A', 'P-A', 'V-DUP', '出院诊断：冠心病。', '2026-03-05 10:00:00'),
                        ('HOSP-B', 'P-B', 'V-DUP', '出院诊断：急性胃炎。', '2026-03-06 11:00:00')
                    """
                )
            )
        return eng

    @pytest.mark.asyncio
    async def test_tri_key_collision_fails_closed_and_explicit_tri_key_isolates(self, monkeypatch, caplog):
        from app.services import frontpage_extraction_service as mod

        eng = self._build_cdm_sqlite_engine()
        monkeypatch.setattr("app.database.connection.engine", eng)
        monkeypatch.setattr(mod, "clinical_table_sql", lambda name: name)

        service = mod.FrontPageExtractionService(llm_config={"api_endpoint": "", "api_key": ""})

        # 未传 institute_id/patient_id 且多院区重号 -> fail-closed 抛 FrontPageCaseIdentityConflictError
        with pytest.raises(mod.FrontPageCaseIdentityConflictError):
            await service._get_medical_text("V-DUP", allow_demo_fallback=False)

        with pytest.raises(mod.FrontPageCaseIdentityConflictError):
            await service._get_llm_context_text("V-DUP")

        # 显式传入完整三坐标 -> 精确隔离，不串院区
        text_a = await service._get_medical_text(
            "V-DUP",
            patient_id="P-A",
            institute_id="HOSP-A",
            allow_demo_fallback=False,
        )
        text_b = await service._get_medical_text(
            "V-DUP",
            patient_id="P-B",
            institute_id="HOSP-B",
            allow_demo_fallback=False,
        )
        assert "冠心病" in text_a and "急性胃炎" not in text_a
        assert "急性胃炎" in text_b and "冠心病" not in text_b

        # 日志不得泄露明文患者姓名
        with caplog.at_level(logging.INFO, logger=mod.__name__):
            prefill = await service._prefill_from_cdm("V-DUP", patient_id="P-A", institute_id="HOSP-A")
        assert prefill["basic_info"].get("patient_name") == "张三甲"
        assert "张三甲" not in caplog.text

    @pytest.mark.asyncio
    async def test_frontpage_llm_client_redacts_phi_before_sending(self, monkeypatch):
        from app.services import frontpage_extraction_service as mod

        captured = {}

        async def _fake_post_json(url, **kwargs):
            captured["payload"] = kwargs.get("payload")
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        monkeypatch.setattr(mod, "safe_post_json", _fake_post_json)
        client = mod.FrontPageLLMClient(
            config={
                "api_endpoint": "https://offline.local/v1",
                "api_key": "dummy-key",
                "model": "offline-model",
            }
        )
        await client.generate(
            "你是病案首页抽取助手。",
            "姓名：王小明\n身份证号：510521199001011234\n联系电话：13812345678\n出院诊断：急性阑尾炎",
        )
        sent_content = captured["payload"]["messages"][1]["content"]
        assert "王小明" not in sent_content
        assert "510521199001011234" not in sent_content
        assert "13812345678" not in sent_content
        assert "急性阑尾炎" in sent_content


class TestFrontpageRouterSecurityAndRedaction:
    def _make_client_and_engine(self, monkeypatch):
        from app.routers import frontpage as router_mod

        eng = _mem_engine()
        Base.metadata.create_all(bind=eng)
        with eng.begin() as conn:
            conn.execute(
                sql_text(
                    """
                    INSERT INTO mr (institute_id, patient_id, visit_id, name, sex, age_year, admission_dept_name)
                    VALUES
                        ('INST-A', 'PA1', 'V-SHARED', '患者甲', '男', '50', '心内科'),
                        ('INST-B', 'PB1', 'V-SHARED', '患者乙', '女', '40', '呼吸科'),
                        ('INST-A', 'PA2', 'V-ONLY-A', '患者丙', '男', '60', '骨科')
                    """
                )
            )

        monkeypatch.setattr(router_mod, "engine", eng)
        monkeypatch.setattr(router_mod, "clinical_table_sql", lambda name: name)
        monkeypatch.setattr(
            router_mod,
            "clinical_query",
            lambda session, *entities: session.query(*entities),
        )
        app = FastAPI()
        app.include_router(router_mod.router)
        return app, TestClient(app), router_mod

    def test_demo_preview_report_draft_and_profile_auth_scope_and_redaction(self, monkeypatch):
        app, client, router_mod = self._make_client_and_engine(monkeypatch)

        # 1) 未登录 401
        assert client.post("/api/v1/frontpage/demo-visit-preview", json={"visit_id": "V-ONLY-A"}).status_code == 401
        assert client.post("/api/v1/frontpage/generate-report-draft", json={"documents": [{"type": "admission_record", "content": "x"}]}).status_code == 401
        assert client.post("/api/v1/frontpage/profile/analyze", json={"medical_text": "出院诊断：肺炎"}).status_code == 401

        # 2) 非允许角色 403
        app.dependency_overrides[get_current_user] = lambda: {"id": "u-guest", "roles": ["guest"], "institute_id": "INST-A"}
        try:
            assert client.post("/api/v1/frontpage/demo-visit-preview", json={"visit_id": "V-ONLY-A"}).status_code == 403
            assert client.post("/api/v1/frontpage/generate-report-draft", json={"documents": [{"type": "admission_record", "content": "x"}]}).status_code == 403
            assert client.post("/api/v1/frontpage/profile/analyze", json={"medical_text": "出院诊断：肺炎"}).status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        # 3) 院区越权 403 (INST-B 账号访问 INST-A 病历)
        monkeypatch.setattr(router_mod, "resolve_non_global_institute_scope", lambda _u: "INST-B")
        app.dependency_overrides[get_current_user] = lambda: {"id": "u-b", "roles": ["coder"], "institute_id": "INST-B"}
        try:
            resp_cross = client.post(
                "/api/v1/frontpage/demo-visit-preview",
                json={"visit_id": "V-ONLY-A", "institute_id": "INST-A", "patient_id": "PA2"},
            )
            assert resp_cross.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        # 4) 全局角色但未提供 institute_id/patient_id 命中多院重号 -> 409
        app.dependency_overrides[get_current_user] = lambda: {"id": "u-admin", "roles": ["admin"]}
        try:
            resp_dup = client.post("/api/v1/frontpage/demo-visit-preview", json={"visit_id": "V-SHARED"})
            assert resp_dup.status_code == 409

            # 5) generate-report-draft 发往服务前脱敏 PHI
            captured_docs = []

            class _FakeReportSvc:
                async def generate(self, **kwargs):
                    captured_docs.append(kwargs.get("documents"))
                    return {"draft": "ok"}

            monkeypatch.setattr(router_mod, "default_frontpage_report_generation_service", _FakeReportSvc())
            resp_draft = client.post(
                "/api/v1/frontpage/generate-report-draft",
                json={
                    "documents": [
                        {
                            "type": "admission_record",
                            "content": "姓名：赵六\n身份证号：510521198802023333\n主诉：发热3天",
                        }
                    ]
                },
            )
            assert resp_draft.status_code == 200
            assert captured_docs
            sent_doc_content = captured_docs[0][0]["content"]
            assert "赵六" not in sent_doc_content
            assert "510521198802023333" not in sent_doc_content
            assert "发热3天" in sent_doc_content

            # 6) profile/analyze 发往服务前脱敏 PHI
            captured_profile = {}

            class _FakeProfileSvc:
                async def analyze_medical_profile(self, **kwargs):
                    captured_profile.update(kwargs)
                    return SimpleNamespace(to_dict=lambda: {"diagnosis_timeline": [], "surgery_verification": [], "discrepancies": []})

            monkeypatch.setattr(
                "app.services.diagnosis_surgery_profiling_service.get_profiling_service",
                lambda: _FakeProfileSvc(),
            )
            resp_prof = client.post(
                "/api/v1/frontpage/profile/analyze",
                json={"medical_text": "姓名：钱七\n电话：13987654321\n出院诊断：2型糖尿病"},
            )
            assert resp_prof.status_code == 200
            assert "钱七" not in captured_profile["medical_text"]
            assert "13987654321" not in captured_profile["medical_text"]
            assert "2型糖尿病" in captured_profile["medical_text"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestDiagnosisProfilingServicePrivacyAndTriKey:
    @pytest.mark.asyncio
    async def test_profiling_service_redacts_phi_and_uses_tri_key(self, monkeypatch):
        from app.services import diagnosis_surgery_profiling_service as mod

        sent_prompts = []

        async def _fake_post_json(url, **kwargs):
            payload = kwargs.get("payload") or {}
            # messages = [system, user]
            user_msg = payload["messages"][-1]["content"]
            sent_prompts.append(user_msg)
            return {"choices": [{"message": {"content": '{"diagnoses": [], "surgeries": []}'}}]}

        monkeypatch.setattr(mod, "safe_post_json", _fake_post_json)
        svc = mod.DiagnosisSurgeryProfilingService(
            llm_config={"api_endpoint": "https://offline.local/v1", "api_key": "dummy", "model": "m"}
        )

        # 通过 visit_id 加载时传递三坐标
        captured_tri_key = {}

        async def _fake_get_medical_text(visit_id, *, patient_id=None, institute_id=None, allow_demo_fallback=False):
            captured_tri_key.update(
                {"visit_id": visit_id, "patient_id": patient_id, "institute_id": institute_id, "allow_demo_fallback": allow_demo_fallback}
            )
            return "姓名：孙八\n身份证号：510521197703034444\n诊断：肺炎"

        monkeypatch.setattr(
            "app.services.frontpage_extraction_service.default_frontpage_service._get_medical_text",
            _fake_get_medical_text,
        )
        await svc.analyze_medical_profile(
            medical_text="",
            institute_id="INST-1",
            patient_id="PAT-1",
            visit_id="VIS-1",
        )
        assert captured_tri_key == {
            "visit_id": "VIS-1",
            "patient_id": "PAT-1",
            "institute_id": "INST-1",
            "allow_demo_fallback": False,
        }
        assert sent_prompts
        for prompt in sent_prompts:
            assert "孙八" not in prompt
            assert "510521197703034444" not in prompt
            assert "肺炎" in prompt


class TestFastScreenPrivacyTechErrorAndCopyCourseHardening:
    @pytest.mark.asyncio
    async def test_fast_screen_redacts_phi_and_marks_technical_error_internal(self, monkeypatch):
        from app.services import fast_screen_qc as mod
        from app.services.sichuan_qc_service import SichuanQCService

        captured_calls = []
        sqc = SichuanQCService()

        class _FakeRuleEngine:
            async def evaluate_batch_compact(self, **kwargs):
                captured_calls.append(kwargs)
                raise RuntimeError("simulated_llm_timeout")

        class _FakeQCService:
            def __init__(self):
                self.rule_engine = _FakeRuleEngine()
                self.client = SimpleNamespace(model="offline-mock")

            def get_rule_by_id(self, rule_id: str):
                return {
                    "rule_id": rule_id,
                    "rule_code": rule_id,
                    "name": f"规则{rule_id}",
                    "executor_type": "llm",
                    "rule_family": "mock",
                    "execution_domain": "mock",
                    "doc_scope": "primary",
                }

            def _ensure_rule_execution_meta(self, rule):
                return dict(rule)

            def _build_bundle_missing_doc_result_item(self, *, rule, **kwargs):
                return {
                    "rule_id": rule["rule_id"],
                    "rule_name": rule["name"],
                    "status": "not_applicable",
                    "is_compliant": True,
                    "metadata": {},
                }

            def _build_document_evaluation_result(self, *, document_id, document_type, rules, orchestrated):
                return sqc._build_document_evaluation_result(
                    document_id=document_id,
                    document_type=document_type,
                    rules=rules,
                    orchestrated=orchestrated,
                )

        fake_bundle = {
            "scene": "final",
            "institute_id": "INST-1",
            "patient_id": "PAT-1",
            "visit_id": "VIS-1",
            "patient_info": {"name": "周九", "id_card_no": "510521198505056666"},
            "document_hits": {"admission_record": True},
        }
        monkeypatch.setattr(mod, "assemble_final_record_bundle", lambda **_kw: fake_bundle)
        monkeypatch.setattr(
            mod,
            "_extract_bundle_documents",
            lambda _bundle: [
                {
                    "id": "1:admission",
                    "document_type": "入院记录",
                    "source_table": "admission_record",
                    "content": "姓名：周九\n身份证号：510521198505056666\n电话：13700001111\n主诉：咳嗽3天",
                }
            ],
        )

        res = await mod.run_final_fast_screen(
            qc_service=_FakeQCService(),
            institute_id="INST-1",
            patient_id="PAT-1",
            visit_id="VIS-1",
            rule_ids=["SC-004"],
            max_pack_retries=0,
        )

        # 1) 发往 LLM 前已脱敏
        assert captured_calls
        sent_blob = json.dumps(captured_calls[0], ensure_ascii=False, default=str)
        assert "周九" not in sent_blob
        assert "510521198505056666" not in sent_blob
        assert "13700001111" not in sent_blob
        assert "咳嗽3天" in sent_blob

        # 2) 技术失败标记为 technical_error_internal 而非 uncertain
        eval_results = res["evaluation_results"]
        assert len(eval_results) == 1
        assert eval_results[0]["status"] == "technical_error_internal"

        # 3) 与 SichuanQCService 汇总口径联动：技术错误计入 technical_error_count，分母为 0 -> compliance_rate 为 None
        summary = res["evaluation_summary"]
        assert summary["technical_error_count"] == 1
        assert summary["compliance_denominator"] == 0
        assert summary["compliance_rate"] is None

    def test_copy_course_query_tri_key_no_swallow_and_limit_n_plus_1(self, monkeypatch):
        from app.services import fast_screen_qc as mod

        eng = _mem_engine()
        with eng.begin() as conn:
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE first_course_record (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        document_id TEXT,
                        document_title TEXT,
                        record_time TEXT,
                        record_content TEXT
                    )
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE daily_course_record (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        document_id TEXT,
                        document_title TEXT,
                        record_time TEXT,
                        record_content TEXT
                    )
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE senior_course_record (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        document_id TEXT,
                        document_title TEXT,
                        record_time TEXT,
                        record_content TEXT
                    )
                    """
                )
            )
            for idx in range(9):
                conn.execute(
                    sql_text(
                        """
                        INSERT INTO daily_course_record VALUES
                            ('INST-1', 'PAT-1', 'V-1', :doc_id, '日常病程', :dt, :content)
                        """
                    ),
                    {
                        "doc_id": f"D-{idx}",
                        "dt": f"2026-03-0{idx+1} 08:00:00",
                        "content": f"INST-1 病程内容 {idx}",
                    },
                )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO daily_course_record VALUES
                        ('INST-2', 'PAT-2', 'V-1', 'D-OTHER', '他院病程', '2026-03-05 08:00:00', 'INST-2 绝不可串入')
                    """
                )
            )

        test_session_local = sessionmaker(bind=eng)
        monkeypatch.setattr(mod, "SessionLocal", test_session_local)
        monkeypatch.setattr(mod, "clinical_table_sql", lambda name: name)

        # 1) 缺三坐标直接抛错（拒绝裸 visit_id 跨院查库）
        with pytest.raises(ValueError):
            mod._load_copy_course_documents_for_visit("V-1")

        # 2) 完整三坐标：只返回 INST-1 数据，且检测到 truncated=True (9 > 8)
        docs, truncated = mod._load_copy_course_documents_for_visit(
            "V-1",
            institute_id="INST-1",
            patient_id="PAT-1",
            max_rows_per_table=8,
        )
        assert truncated is True
        assert len(docs) == 8
        assert all("INST-2" not in d["content"] for d in docs)

        # 3) DB 异常不再静默吞掉
        def _broken_session():
            raise RuntimeError("db_connection_broken")

        monkeypatch.setattr(mod, "SessionLocal", _broken_session)
        with pytest.raises(RuntimeError, match="db_connection_broken"):
            mod._load_copy_course_documents_for_visit("V-1", institute_id="INST-1", patient_id="PAT-1")


# ============================================================================
# 2. P1-D2: sichuan_qc_service 零分母合规率统一返回 None
# ============================================================================


class TestSichuanQCZeroDenominatorComplianceRate:
    @pytest.mark.asyncio
    async def test_all_zero_denominator_paths_return_none(self):
        from app.services.sichuan_qc_service import SichuanQCService

        svc = SichuanQCService()

        # 1) _build_document_evaluation_result 全不适用/资料缺口 -> None
        built = svc._build_document_evaluation_result(
            document_id="doc-0",
            document_type="入院记录",
            rules=[{"rule_id": "SC-001"}, {"rule_id": "SC-002"}],
            orchestrated={
                "results": [
                    {"rule_id": "SC-001", "status": "not_applicable", "is_compliant": True},
                    {"rule_id": "SC-002", "status": "data_gap", "is_compliant": False},
                ],
                "metrics": {"total_tokens": 0, "total_api_time": 0.0},
            },
        )
        assert built["evaluation_summary"]["compliance_denominator"] == 0
        assert built["evaluation_summary"]["compliance_rate"] is None

        # 2) evaluate_document_fast 无适用规则 -> None
        res_empty = await svc.evaluate_document_fast(
            document_id="doc-empty",
            content="无适用规则的测试文本",
            document_type="不存在的文书类型_XYZ",
        )
        assert res_empty["evaluation_summary"]["compliance_rate"] is None

        # 3) evaluate_multi_document 0 适用规则 -> overall 与 per-doc breakdown 均为 None
        res_multi = await svc.evaluate_multi_document(
            document_id="doc-multi-empty",
            document_content="测试文本",
            document_types=["不存在的文书类型_XYZ"],
        )
        assert res_multi["overall_summary"]["compliance_rate"] is None
        assert res_multi["overall_summary"]["document_breakdown"]["不存在的文书类型_XYZ"]["compliance_rate"] is None


# ============================================================================
# 3. P1-D3 + P2-B1: frontpage_formal_qc & settlement_service / settlement_formal_qc
# ============================================================================


class TestFrontpageFormalQCNumericAndFailClosed:
    def test_string_numeric_anomalies_are_caught_and_exception_fails_closed(self):
        from app.services.frontpage_formal_qc import Category, FrontpageFormalQCEngine, QCRule, Severity

        eng = FrontpageFormalQCEngine()
        data = {
            "patient_name": "测试患者",
            "sex": "男",
            "age": "250",
            "birth_date": "1990-01-01",
            "id_card": "510521199001011234",
            "admission_route": "1",
            "discharge_method": "1",
            "los_days": "-5",
            "total_cost": "-100",
            "main_diagnosis_name": "肺炎",
            "main_diagnosis_code": "J18.900",
        }
        report = eng.validate(data)
        failed_ids = {r.rule_id for r in report.results if not r.passed}
        assert "FQ-077" in failed_ids  # 年龄 250 异常必须检出
        assert "FQ-078" in failed_ids  # 住院天数 -5 异常必须检出
        assert "FQ-079" in failed_ids  # 总费用 -100 异常必须检出
        # 字符串合法编码 "1" 应通过 FQ-024 / FQ-072
        assert "FQ-024" not in failed_ids
        assert "FQ-072" not in failed_ids

        # 规则检查函数抛出异常时必须 fail-closed (passed=False)，绝不吞错判 True
        def _boom(_d):
            raise ValueError("unexpected_rule_crash")

        eng.rules.append(
            QCRule(
                rule_id="FQ-TEST-ERR",
                field_name="test",
                rule_name="异常规则",
                description="异常规则",
                severity=Severity.ERROR,
                category=Category.LOGIC,
                validate=_boom,
                message=lambda _fp: "不应吞错",
            )
        )
        try:
            report2 = eng.validate(data)
            err_res = next(r for r in report2.results if r.rule_id == "FQ-TEST-ERR")
            assert err_res.passed is False
            assert "ValueError" in err_res.message
        finally:
            eng.rules.pop()


class TestSettlementServiceAndFormalQC:
    def test_settlement_tri_key_id_card_no_and_formal_qc_rules(self, monkeypatch):
        from app.services import settlement_service as svc_mod
        from app.services.settlement_formal_qc import (
            Category,
            SettlementFormalQCEngine,
            SettlementQCRule,
            Severity,
        )

        eng = _mem_engine()
        Base.metadata.create_all(bind=eng)
        with eng.begin() as conn:
            conn.execute(
                sql_text(
                    """
                    INSERT INTO medical_insurance_settlement (
                        institute_id, patient_id, visit_id, mr_no, inpat_no,
                        admission_dept_name, discharge_dept_name,
                        admission_datetime, discharge_datetime,
                        admission_route, settlement_status
                    ) VALUES
                        ('INST-A', 'P001', 'V001', 'MR001', 'ZY001', '产科', '产科', '2026-03-01 08:00:00', '2026-03-03 10:00:00', '1', '已结算'),
                        ('INST-B', 'P001', 'V001', 'MR002', 'ZY002', '内科', '内科', '2026-03-01 08:00:00', '2026-03-03 10:00:00', '1', '已结算')
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO mr (
                        institute_id, patient_id, visit_id, name, sex, age_year,
                        birthday, id_card_no, contact_telephone, hospital_duration, leaving_hospital_way
                    ) VALUES
                        ('INST-A', 'P001', 'V001', '测试男患者', '男', '30', '1996-01-01', '5105211996010112X4', '13800138000', '2', '1'),
                        ('INST-B', 'P001', 'V001', '测试女患者', '女', '28', '1998-02-02', '510521199802021222', '13900139000', '2', '1')
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO diagnosis (
                        diagnosis_id, institute_id, patient_id, visit_id, diagnosis_no, main_diag_flag,
                        diagnosis_type, diagnosis_name, diagnosis_code, admission_condition
                    ) VALUES
                        ('DIAG-1', 'INST-A', 'P001', 'V001', '1', '1', '出院诊断', '单胎顺产', 'O80.000', '有'),
                        ('DIAG-2', 'INST-B', 'P001', 'V001', '1', '1', '出院诊断', '急性上呼吸道感染', 'J06.900', '有')
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO mr_cost (institute_id, patient_id, visit_id, total_cost, self_pay)
                    VALUES
                        ('INST-A', 'P001', 'V001', '3200.50', '500.00'),
                        ('INST-B', 'P001', 'V001', '1200.00', '200.00')
                    """
                )
            )

        monkeypatch.setattr(svc_mod, "engine", eng)
        monkeypatch.setattr(svc_mod, "clinical_query", lambda session, *entities: session.query(*entities))

        svc = svc_mod.SettlementService()

        # 1) list_settlements 支持 institute_id 隔离
        list_a = svc.list_settlements(institute_id="INST-A")
        assert list_a["total"] == 1
        assert list_a["items"][0]["institute_id"] == "INST-A"

        # 2) 未传 institute_id 命中多院重号 -> fail-closed 抛 ValueError
        with pytest.raises(ValueError, match="多院区"):
            svc.get_settlement_detail("P001", "V001")

        # 3) 显式传 institute_id="INST-A" -> 正确读取 mr.id_card_no 与诊断契约
        detail_a = svc.get_settlement_detail("P001", "V001", institute_id="INST-A")
        assert detail_a is not None
        assert detail_a["id_number"] == "5105211996010112X4"
        assert detail_a["patient_id_card"] == "5105211996010112X4"
        assert detail_a["sex"] == "男"

        # 4) 形式质控：男性 + 顺产 O80.0 (#135) 与 畸形身份证第17位非数字 (#113) 必须检出不通过
        qc_eng = SettlementFormalQCEngine()
        report = qc_eng.check(detail_a)
        failed_ids = {r.rule_id for r in report.results if not r.passed}
        assert "135" in failed_ids
        assert "113" in failed_ids

        # 5) 规则抛异常必须 fail-closed
        qc_eng.rules.append(
            SettlementQCRule(
                rule_id="TEST-ERR",
                field_name="test",
                rule_name="异常规则",
                description="不可吞错",
                severity=Severity.ERROR,
                category=Category.LOGIC,
                affects_grouping=False,
                validate=lambda _d: 1 / 0,
                message=lambda _d: "不可吞错",
            )
        )
        try:
            r2 = qc_eng.check(detail_a)
            err = next(x for x in r2.results if x.rule_id == "TEST-ERR")
            assert err.passed is False
            assert "ZeroDivisionError" in err.message
        finally:
            qc_eng.rules.pop()


# ============================================================================
# 4. P1-D4: sc083 / sc099 门控与 clinical_completeness 路由安全只读
# ============================================================================


class TestSC083AndSC099GatesHardening:
    def test_sc083_tri_key_isolation_no_swallow_and_truncation_detection(self, monkeypatch):
        from app.services.qc_applicability_gates import sc083_mdt_evidence_aggregator as mod
        from app.services.qc_applicability_gates.models import GateDecision

        eng = _mem_engine()
        with eng.begin() as conn:
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE consultation_record (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        document_id TEXT,
                        document_title TEXT,
                        record_datetime TEXT,
                        record_content TEXT
                    )
                    """
                )
            )
            # 插入 201 条 (> 默认 max_rows=200) 触发 run_sc083_gate LIMIT N+1 截断探测
            for i in range(201):
                conn.execute(
                    sql_text(
                        """
                        INSERT INTO consultation_record VALUES
                            ('INST-A', 'PA', 'V-83', :did, '普通会诊', '2026-03-01 08:00:00', '一般会诊记录')
                        """
                    ),
                    {"did": f"C-{i}"},
                )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO consultation_record VALUES
                        ('INST-B', 'PB', 'V-83', 'C-B', 'MDT多学科会诊', '2026-03-01 09:00:00', '多学科讨论：麻醉科、心内科、肿瘤科共同参与。')
                    """
                )
            )

        monkeypatch.setattr("app.database.connection.engine", eng)
        monkeypatch.setattr("app.services.clinical_read.clinical_read_schema", lambda: "")

        # 1) 缺三坐标拒绝查询
        with pytest.raises(ValueError):
            mod._db_rows("consultation_record", "V-83", ["document_id"], institute_id="", patient_id="")

        # 2) 三坐标隔离 + LIMIT N+1 截断探测
        rows_a, trunc_a = mod._db_rows(
            "consultation_record",
            "V-83",
            ["document_id", "record_content"],
            institute_id="INST-A",
            patient_id="PA",
            max_rows=40,
        )
        assert trunc_a is True
        assert len(rows_a) == 40
        assert all("多学科讨论" not in str(r.get("record_content") or "") for r in rows_a)

        # 3) run_sc083_gate 在发生截断时降级为 DATA_QUALITY_GAP
        gate_res = mod.run_sc083_gate(
            {"visit_id": "V-83", "patient_id": "PA", "institute_id": "INST-A"},
            context={
                "visit_id": "V-83",
                "patient_id": "PA",
                "institute_id": "INST-A",
                "visit_max_level": "四级",
                "visit_level4_evidence_code": "38.44",
                "visit_level4_evidence_name": "四级手术",
                "strong_match_type": "code_exact",
            },
        )
        assert gate_res.gate_decision == GateDecision.DATA_QUALITY_GAP
        assert gate_res.metadata.get("source_rows_truncated") is True

        # 4) DB 异常不再静默吞掉
        class _BadEngine:
            def connect(self):
                raise RuntimeError("sc083_db_down")

        monkeypatch.setattr(
            mod,
            "_db_table_schema",
            lambda _table: ("", {"institute_id", "patient_id", "visit_id", "document_id"}),
        )
        monkeypatch.setattr("app.database.connection.engine", _BadEngine())
        with pytest.raises(RuntimeError, match="sc083_db_down"):
            mod._db_rows("consultation_record", "V-83", ["document_id"], institute_id="INST-A", patient_id="PA")

    def test_sc099_tri_key_isolation_no_swallow_and_truncation_detection(self, monkeypatch):
        from app.services.qc_applicability_gates import sc099_pathology_specimen_gate as mod
        from app.services.qc_applicability_gates.models import GateDecision

        eng = _mem_engine()
        with eng.begin() as conn:
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE final_record_bundle (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        structured_context TEXT,
                        medical_text TEXT
                    )
                    """
                )
            )
            payload_a = json.dumps(
                {"document_inventory": [{"source_table": "surgery_record", "content": "常规手术操作，顺利结束，术中出血少。"}]}
            )
            payload_b = json.dumps(
                {"document_inventory": [{"source_table": "surgery_record", "content": "术中取材送病理检查。"}]}
            )
            # INST-A 插入 11 条 (> default _SC099_BUNDLE_MAX_ROWS=10) 触发截断；INST-B 插入带病理触发的干扰记录
            for _ in range(11):
                conn.execute(
                    sql_text("INSERT INTO final_record_bundle VALUES ('INST-A', 'PA', 'V-99', :js, '')"),
                    {"js": payload_a},
                )
            conn.execute(
                sql_text("INSERT INTO final_record_bundle VALUES ('INST-B', 'PB', 'V-99', :js, '')"),
                {"js": payload_b},
            )

        monkeypatch.setattr("app.database.connection.engine", eng)

        # 1) 缺三坐标拒绝裸 visit_id 查库
        with pytest.raises(ValueError):
            mod._load_persisted_bundle_context("V-99", institute_id="", patient_id="")

        # 2) 三坐标隔离 + LIMIT N+1 截断探测 -> run_sc099_gate 降级 DATA_QUALITY_GAP，且不串入 INST-B 病理触发
        res = mod.run_sc099_gate(
            {"visit_id": "V-99", "patient_id": "PA", "institute_id": "INST-A"},
            context={"visit_id": "V-99", "patient_id": "PA", "institute_id": "INST-A"},
        )
        assert res.gate_decision == GateDecision.DATA_QUALITY_GAP
        assert res.metadata.get("source_rows_truncated") is True
        assert res.metadata.get("trigger_status") == "absent"

        # 3) DB 异常不再静默吞掉
        class _BadEngine:
            dialect = SimpleNamespace(name="sqlite")

            def connect(self):
                raise RuntimeError("sc099_db_down")

        monkeypatch.setattr("app.database.connection.engine", _BadEngine())
        with pytest.raises(RuntimeError, match="sc099_db_down"):
            mod._load_persisted_bundle_context("V-99", institute_id="INST-A", patient_id="PA")


class TestClinicalCompletenessRouterHardening:
    def test_scope_checks_reject_get_force_refresh_and_allow_explicit_post_refresh(self, monkeypatch):
        from app.routers import clinical_completeness as mod

        eng = _mem_engine()
        Base.metadata.create_all(bind=eng)
        with eng.begin() as conn:
            conn.execute(
                sql_text(
                    """
                    INSERT INTO mr (institute_id, patient_id, visit_id, name)
                    VALUES
                        ('INST-A', 'PA1', 'V-100', '患者A'),
                        ('INST-A', 'PA2', 'V-DUP', '患者A2'),
                        ('INST-B', 'PB2', 'V-DUP', '患者B2')
                    """
                )
            )

        monkeypatch.setattr(mod, "engine", eng)
        monkeypatch.setattr(mod, "clinical_table_sql", lambda name: name)
        monkeypatch.setattr(mod, "clinical_query", lambda session, *entities: session.query(*entities))

        calls = {"readonly": 0, "write_cache": 0}

        monkeypatch.setattr(
            "app.services.bundles.assembly.assemble_final_record_bundle",
            lambda **kw: (calls.__setitem__("readonly", calls["readonly"] + 1) or {"documents": [], "case_key": kw}),
        )
        monkeypatch.setattr(
            "app.services.bundles.assembly.load_or_assemble_scene_bundle",
            lambda **kw: (calls.__setitem__("write_cache", calls["write_cache"] + 1) or {"documents": [], "case_key": kw}),
        )
        monkeypatch.setattr(
            mod.ClinicalTimelineService,
            "build_from_bundle",
            lambda self, bundle: SimpleNamespace(to_dict=lambda: {"ok": True, "case_key": bundle.get("case_key")}),
        )

        app = FastAPI()
        app.include_router(mod.router)
        client = TestClient(app)

        # 1) 未登录 401
        assert client.get("/api/v1/clinical-completeness/V-100").status_code == 401

        # 2) 非允许角色 403
        app.dependency_overrides[get_current_user] = lambda: {"id": "u-guest", "roles": ["guest"]}
        try:
            assert client.get("/api/v1/clinical-completeness/V-100").status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        # 3) 跨院区访问 403
        monkeypatch.setattr(mod, "resolve_non_global_institute_scope", lambda _u: "INST-B")
        app.dependency_overrides[get_current_user] = lambda: {"id": "u-b", "roles": ["coder"], "institute_id": "INST-B"}
        try:
            assert client.get("/api/v1/clinical-completeness/V-100?institute_id=INST-A&patient_id=PA1").status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        # 4) 全局管理员测试：GET force_refresh=true 返回 405；多院重号返回 409；未知病例拒绝写 ('', '', vid) 返回 400
        app.dependency_overrides[get_current_user] = lambda: {"id": "u-admin", "roles": ["admin"]}
        try:
            resp_405 = client.get("/api/v1/clinical-completeness/V-100?force_refresh=true")
            assert resp_405.status_code == 405

            resp_409 = client.get("/api/v1/clinical-completeness/V-DUP")
            assert resp_409.status_code == 409

            resp_400 = client.get("/api/v1/clinical-completeness/V-NONEXISTENT")
            assert resp_400.status_code == 400
            assert calls["write_cache"] == 0

            # 5) 合法 GET 只走只读 assemble_final_record_bundle，不写缓存
            resp_ok = client.get("/api/v1/clinical-completeness/V-100")
            assert resp_ok.status_code == 200
            assert calls["readonly"] == 1
            assert calls["write_cache"] == 0

            # 6) 显式 POST /{visit_id}/refresh 允许写缓存且强制携带非空三坐标
            resp_post = client.post(
                "/api/v1/clinical-completeness/V-100/refresh?institute_id=INST-A&patient_id=PA1"
            )
            assert resp_post.status_code == 200
            assert calls["write_cache"] == 1
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ============================================================================
# 5. P2-D1 + P2-D2: frontpage_qc_v2 6 处修复 & disease_change_015016 schema 路由
# ============================================================================


class TestFrontpageQcV2SixFixes:
    def test_values_finite_number_and_iso_microseconds(self):
        from app.services.frontpage_qc_v2 import values

        # ④ 拦截 NaN / inf / -inf 与 bool
        assert values.parse_number("NaN") is None
        assert values.parse_number("inf") is None
        assert values.parse_number("-inf") is None
        assert values.parse_number(float("nan")) is None
        assert values.parse_number(float("inf")) is None
        assert values.parse_number(True) is None
        assert values.parse_number("123.45") == pytest.approx(123.45)

        # ④ 支持微秒 ISO 时间
        dt = values.parse_datetime("2026-03-01T08:30:15.123456")
        assert dt is not None
        assert dt.year == 2026 and dt.hour == 8 and dt.microsecond == 123456

    def test_single_record_completeness_excludes_hint(self):
        from app.services.frontpage_qc_v2 import FrontpageRef, RawFrontpage, build_frontpage_doc, evaluate_frontpage
        from app.services.frontpage_qc_v2.catalog import RULES
        from app.services.frontpage_qc_v2.model import Severity, Verdict

        raw = RawFrontpage(
            ref=FrontpageRef("INST-1", "P1", "V1"),
            mr={
                "name": "测试",
                "sex": "男",
                "birthday": "1980-01-01",
                "admission_datetime": "2026-03-01 08:00:00",
                "discharge_datetime": "2026-03-05 10:00:00",
                "hospital_duration": "4",
                "leaving_hospital_way": "1",
                "admission_route": "1",
            },
            diagnosis_rows=[
                {
                    "diagnosis_type_name": "主要诊断",
                    "diagnosis_no": "1",
                    "diagnosis_name": "肺炎",
                    "diagnosis_code": "J18.900",
                    "admission_condition_name": "有",
                }
            ],
            diagnosis_source="diagnosis",
            surgery_rows=[],
            cost_row={"total_cost": "1000.00"},
        )
        doc = build_frontpage_doc(raw)
        outcome = evaluate_frontpage(doc)

        # 按院级口径手工重算：completeness 组排除 Severity.HINT（比例制 [0.0, 1.0]）
        non_hint_comp_rules = [
            r for r in RULES if r.group == "completeness" and r.severity != Severity.HINT
        ]
        passed_cnt = sum(
            1 for r in non_hint_comp_rules if outcome.rule_verdicts.get(r.rule_id) == Verdict.PASS.value
        )
        applicable_cnt = sum(
            1
            for r in non_hint_comp_rules
            if outcome.rule_verdicts.get(r.rule_id) in (Verdict.PASS.value, Verdict.FAIL.value)
        )
        expected = round(passed_cnt / applicable_cnt, 2) if applicable_cnt else None
        assert outcome.completeness_rate == expected

    def test_store_required_missing_l06_isolation_excel_escape_and_concurrency_locks(self, tmp_path):
        from app.services.frontpage_qc_v2 import FrontpageRef
        from app.services.frontpage_qc_v2.model import Finding, FrontpageQcOutcome, ItemScore, Verdict
        from app.services.frontpage_qc_v2.reporting import build_analytics, build_export_workbook
        from app.services.frontpage_qc_v2.store import FrontpageQcRunConflict, FrontpageQcStore

        db_path = tmp_path / "fp_v2_test.sqlite"
        eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        store = FrontpageQcStore(sessionmaker(bind=eng, expire_on_commit=False))
        store.create_all(eng)

        ref1 = FrontpageRef("INST-1", "P1", "V1")
        ref2 = FrontpageRef("INST-1", "P2", "V2")

        # ⑥ 并发 create_run_if_no_active 互斥：多线程同时建任务仅允许一个成功，另一个抛 FrontpageQcRunConflict
        barrier = threading.Barrier(2)
        created_runs = []
        conflicts = []

        def _worker():
            barrier.wait()
            try:
                run = store.create_run_if_no_active(
                    created_by="user-lock-test",
                    refs=[ref1, ref2],
                    filters={},
                    ruleset_version="v2.0",
                )
                created_runs.append(run)
            except FrontpageQcRunConflict as exc:
                conflicts.append(exc)

        t1 = threading.Thread(target=_worker)
        t2 = threading.Thread(target=_worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(created_runs) == 1
        assert len(conflicts) == 1
        run_id = created_runs[0]["id"]

        # 病例 1：仅缺 REQUIRED 必填项（无 fail / 无 data_gap）-> 验证 ① required_missing 筛选桶
        out1 = FrontpageQcOutcome(
            institute_id=ref1.institute_id,
            patient_id=ref1.patient_id,
            visit_id=ref1.visit_id,
            ruleset_version="v2.0",
            score=95.0,
            grade="甲",
            fail_count=0,
            hint_count=0,
            data_gap_count=0,
            required_missing_count=1,
            scorable_ratio=1.0,
            completeness_rate=0.90,
            findings=[
                Finding(
                    rule_id="C-10",
                    rule_name="必填项A",
                    group="completeness",
                    section="patient",
                    severity="required",
                    score_item=None,
                    verdict=Verdict.FAIL.value,
                    problem="必填项缺失",
                    reason="字段为空",
                    details=[],
                    deduction=5.0,
                )
            ],
            item_scores=[],
            rule_verdicts={"C-10": Verdict.FAIL.value},
            input_fingerprint="fp-1",
        )

        # 病例 2：L-06 仅其他诊断失败（score_item='other_diag_code'）-> 验证 ② L-06 不污染 main_diag_code 正确率
        out2 = FrontpageQcOutcome(
            institute_id=ref2.institute_id,
            patient_id=ref2.patient_id,
            visit_id=ref2.visit_id,
            ruleset_version="v2.0",
            score=92.0,
            grade="甲",
            fail_count=1,
            hint_count=0,
            data_gap_count=0,
            required_missing_count=0,
            scorable_ratio=1.0,
            completeness_rate=1.0,
            findings=[
                Finding(
                    rule_id="L-06",
                    rule_name="诊断编码格式",
                    group="logic",
                    section="diagnosis",
                    severity="must",
                    score_item="other_diag_code",
                    verdict=Verdict.FAIL.value,
                    problem="@SUM(1,2) 其他诊断编码格式错误",
                    reason="编码不规范",
                    details=[],
                    deduction=8.0,
                )
            ],
            item_scores=[
                ItemScore(
                    key="other_diag_code",
                    label="其他诊断编码",
                    section="diagnosis",
                    klass="B",
                    status="deducted",
                    deduction=8.0,
                    max_points=8.0,
                )
            ],
            rule_verdicts={"C-D06": Verdict.PASS.value, "L-06": Verdict.FAIL.value},
            input_fingerprint="fp-2",
        )

        store.save_outcome(run_id=run_id, outcome=out1, department="内科", discharge_date="2026-03-01")
        store.save_outcome(run_id=run_id, outcome=out2, department="-1+1", discharge_date="2026-03-02")

        # ① required_missing 筛选桶能召回病例 1
        req_items, req_total = store.query_latest(issue="required_missing")
        assert req_total == 1
        assert req_items[0]["visit_id"] == "V1"

        # ② L-06 其他诊断失败不得污染 main_diag_code 正确率（numerator=1, denominator=1, rate=1.0）
        analytics_rows = store.latest_rows_for_analytics()
        analytics = build_analytics(analytics_rows)
        main_diag_ind = next(i for i in analytics["indicators"] if i["key"] == "main_diag_code")
        assert main_diag_ind["denominator"] == 1
        assert main_diag_ind["numerator"] == 1
        assert main_diag_ind["rate"] == 1.0
        assert analytics["summary"]["required_missing_records"] == 1

        # ⑤ Excel 导出单元格公式注入转义（数值列保持数值）
        all_items, _ = store.query_latest()
        detail2 = store.latest_detail(ref2)
        res_by_visit = {item["visit_id"]: item for item in all_items}
        export_findings = [
            {**f, "result_id": res_by_visit["V2"]["id"]} for f in detail2["findings"]
        ]
        wb_bytes = build_export_workbook(
            filters_summary='=HYPERLINK("http://evil")',
            results=all_items,
            findings=export_findings,
            record_info={
                res_by_visit["V1"]["id"]: {
                    "inpat_no": "+cmd|' /C calc'!A0",
                    "patient_name": "\t=1+1",
                },
                res_by_visit["V2"]["id"]: {
                    "inpat_no": "=SUM(A1:A2)",
                    "patient_name": "@SUM(1,2)",
                },
            },
        )
        wb = openpyxl.load_workbook(BytesIO(wb_bytes))
        all_cells = [
            cell.value
            for name in wb.sheetnames
            for row in wb[name].iter_rows(min_row=1)
            for cell in row
        ]
        assert any(isinstance(v, str) and v.startswith("'=SUM(A1:A2)") for v in all_cells)
        assert any(isinstance(v, str) and v.startswith("'+cmd|") for v in all_cells)
        assert any(isinstance(v, str) and v.startswith("'-1+1") for v in all_cells)
        assert any(isinstance(v, str) and v.startswith("'@SUM(1,2)") for v in all_cells)
        assert any(isinstance(v, str) and v.startswith("'\t=1+1") for v in all_cells)
        assert any(isinstance(v, (int, float)) and v == 95.0 for v in all_cells)

        # ⑥ review_finding 在病例级锁保护下更新最新结果复核状态，且重跑后旧 finding 复核被拒绝、新结果沿用复核结论
        from app.services.frontpage_qc_v2.store import FrontpageQcNotFound

        finding_id = detail2["findings"][0]["id"]
        updated = store.review_finding(
            finding_id,
            status="false_alarm",
            note="人工复核确认误报",
            reviewer="qc-reviewer-1",
        )
        assert updated["review_status"] == "false_alarm"
        assert updated["reviewed_by"] == "qc-reviewer-1"

        # 重跑同一病例后：新 finding 沿用 false_alarm，对旧 finding_id 复核被 fail-closed 拒绝
        store.save_outcome(run_id=run_id, outcome=out2, department="-1+1", discharge_date="2026-03-02")
        detail2_after = store.latest_detail(ref2)
        assert detail2_after["findings"][0]["review_status"] == "false_alarm"
        with pytest.raises(FrontpageQcNotFound):
            store.review_finding(finding_id, status="confirmed", note="stale", reviewer="qc-reviewer-2")


class TestDiseaseChange015016SchemaRouting:
    def test_no_hardcoded_cdm_prefix_and_routes_via_clinical_table_sql(self, monkeypatch):
        from app.services.luxian_0916 import disease_change_015016 as mod

        eng = _mem_engine()
        with eng.begin() as conn:
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE inpat_nondrug_order (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        order_id TEXT,
                        order_name TEXT,
                        order_status TEXT,
                        prescribed_datetime TEXT
                    )
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE labtest_item_report (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        document_id TEXT,
                        test_id TEXT,
                        test_no TEXT,
                        item_id TEXT,
                        item_name TEXT,
                        result TEXT,
                        unit TEXT,
                        abnormal_indicator TEXT,
                        report_time TEXT
                    )
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    CREATE TABLE labtest_master (
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        test_id TEXT,
                        report_datetime TEXT
                    )
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO inpat_nondrug_order VALUES
                        ('INST-1', 'P1', 'V1', 'O1', '病危通知', '执行中', '2026-03-02 09:30:00')
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO labtest_master VALUES
                        ('INST-1', 'P1', 'V1', 'T1', '2026-03-02 10:00:00')
                    """
                )
            )
            conn.execute(
                sql_text(
                    """
                    INSERT INTO labtest_item_report VALUES
                        ('INST-1', 'P1', 'V1', 'DOC-1', 'T1', 'TN1', 'I1', '血钾', '6.8', 'mmol/L', 'PH', '2026-03-02 10:00:00')
                    """
                )
            )

        # 验证 SQLite 无 schema 前缀可直接执行（无硬编码 FROM cdm.*）
        monkeypatch.setattr(mod.clinical_connection, "configured", lambda: False)
        monkeypatch.setattr(mod, "engine", eng)
        monkeypatch.setattr(mod, "clinical_table_sql", lambda name: name)

        facts = mod.load_disease_change_015016_facts(institute_id="INST-1", patient_id="P1", visit_id="V1")
        assert facts["diagnostic"]["code"] == "structured_disease_change_trigger_ready"
        assert len(facts["event_facts"]["disease_changes"]) == 2

        # 验证源码无硬编码 FROM cdm.
        source = inspect.getsource(mod)
        assert "FROM cdm." not in source
