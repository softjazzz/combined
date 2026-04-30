"""
四川质控服务单元测试

测试目标：
1. 从 JSON 文件加载规则并按文书类型筛选
2. 使用 Prompt 模板构建 Prompt
3. 通过 SQLAlchemy 查询 CDM 表获取病历内容
4. 使用统一规则引擎进行质控评估

数据库策略：
- 单元测试使用 SQLite in-memory（与生产 PG 结构一致，SQLAlchemy 兼容）
- 规则数据来自真实 JSON 文件（sichuan_rules_146.json / custom_rules_33.json）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.sichuan_qc_service import SichuanQCService
from app.services.rule_domain_router import RuleExecutionInput
from app.database.connection import Base


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def test_engine():
    """创建 SQLite in-memory 引擎用于测试（结构与 PG 一致）"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="module")
def test_session_factory(test_engine):
    """创建 session 工厂"""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture
def db_session(test_session_factory):
    """单个测试用 session（每个测试后回滚）"""
    session = test_session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def seed_cdm_data(db_session):
    """向 CDM 表写入测试数据（每次测试前清理重建）"""
    # 清理旧数据
    for table in ['admission_record', 'first_course_record', 'daily_course_record',
                  'surgery_record', 'discharge_record']:
        db_session.execute(text(f"DELETE FROM {table} WHERE institute_id = 'TEST001'"))
    db_session.commit()
    # 入院记录
    db_session.execute(text("""
        INSERT INTO admission_record (institute_id, patient_id, visit_id, document_id, record_content)
        VALUES ('TEST001', 'P001', 'V001', 'D001',
                '入院记录\n患者男性，65岁，因胸痛3天入院。\n主诉：反复胸痛3天。\n现病史：患者3天前无明显诱因出现胸痛...\n既往史：高血压病史5年。\n个人史：无特殊。\n家族史：父亲有冠心病史。\n体格检查：T 36.5℃，P 80次/分，R 18次/分，BP 140/90mmHg。\n辅助检查：心电图示ST段改变。\n初步诊断：冠心病，不稳定型心绞痛。')
    """))
    # 首次病程记录
    db_session.execute(text("""
        INSERT INTO first_course_record (institute_id, patient_id, visit_id, document_id, record_content)
        VALUES ('TEST001', 'P001', 'V001', 'D002',
                '首次病程记录\n病例特点：患者男性，65岁，因胸痛3天入院。\n诊断依据：1. 老年男性；2. 反复胸痛3天；3. 心电图示ST段改变。\n鉴别诊断：需与急性心肌梗死、主动脉夹层鉴别。\n诊疗计划：1. 完善冠脉CTA；2. 抗血小板治疗；3. 监测心肌酶谱。')
    """))
    # 日常病程记录
    db_session.execute(text("""
        INSERT INTO daily_course_record (institute_id, patient_id, visit_id, document_id, record_content)
        VALUES ('TEST001', 'P001', 'V001', 'D003',
                '日常病程记录\n2025-01-02 查房记录\n患者胸痛较前缓解，夜间未发作。\n生命体征平稳，心率72次/分，血压132/82mmHg。\n治疗反应良好，继续当前治疗方案。')
    """))
    # 手术记录
    db_session.execute(text("""
        INSERT INTO surgery_record (institute_id, patient_id, visit_id, document_id, record_content)
        VALUES ('TEST001', 'P001', 'V001', 'D004',
                '手术记录\n手术名称：经皮冠状动脉介入治疗(PCI)\n手术日期：2025-01-03\n麻醉方式：局部麻醉\n手术经过：常规消毒铺巾，穿刺右桡动脉...\n术中出血量：约5ml\n术后诊断：冠心病，LAD中段狭窄90%')
    """))
    # 出院记录
    db_session.execute(text("""
        INSERT INTO discharge_record (institute_id, patient_id, visit_id, document_id, record_content)
        VALUES ('TEST001', 'P001', 'V001', 'D005',
                '出院记录\n入院日期：2025-01-01\n出院日期：2025-01-10\n入院诊断：冠心病\n出院诊断：冠心病，LAD中段狭窄（PCI术后）\n诊疗经过：入院后完善相关检查...行PCI术，术后恢复良好。\n出院医嘱：1. 继续口服阿司匹林；2. 1月后复查。')
    """))
    db_session.commit()
    return db_session


@pytest.fixture
def service():
    """创建 SichuanQCService 实例"""
    return SichuanQCService()


# ==================== 规则加载测试 ====================

class TestRuleLoading:
    """测试从 JSON 加载规则并按文书类型筛选"""

    def test_load_all_rules_from_json(self, service):
        """测试加载所有规则"""
        rules = service._load_rules_from_json()
        assert len(rules) == 179  # sichuan_rules_146.json: SC-068 启用 + LX-xxx 等
        assert all("rule_id" in r for r in rules)

    def test_load_custom_rules_from_json(self, service):
        """测试加载自定义规则"""
        rules = service._load_custom_rules_from_json()
        assert len(rules) > 0
        # 应包含 LX 和 LXE 系列
        lx_ids = [r["rule_id"] for r in rules if r["rule_id"].startswith("LX-")]
        lxe_ids = [r["rule_id"] for r in rules if r["rule_id"].startswith("LXE-")]
        assert len(lx_ids) == 33
        assert len(lxe_ids) > 0

    @pytest.mark.asyncio
    async def test_filter_rules_for_admission_record(self, service):
        """测试筛选入院记录适用规则"""
        rules = await service._load_applicable_rules("入院记录")
        assert len(rules) == 44  # SC + LX + LXE（按 rule_id 去重后）
        rule_ids = {r.get("rule_id") or r.get("rule_code") for r in rules}
        assert "SC-001" in rule_ids
        assert "SC-020" in rule_ids
        assert "LX-001" in rule_ids
        assert "LX-009" in rule_ids
        # 不应包含非入院记录的规则
        assert "SC-021" not in rule_ids  # 首次病程
        assert "SC-095" not in rule_ids  # 手术记录

    @pytest.mark.asyncio
    async def test_filter_rules_for_first_course(self, service):
        """测试筛选首次病程记录适用规则"""
        rules = await service._load_applicable_rules("首次病程记录")
        assert len(rules) >= 7  # SC-021~027 + LXE 展开后的 course_record 规则
        rule_ids = {r.get("rule_id") or r.get("rule_code") for r in rules}
        assert "SC-021" in rule_ids
        assert "SC-027" in rule_ids

    @pytest.mark.asyncio
    async def test_filter_rules_for_daily_course(self, service):
        """测试筛选日常病程记录适用规则"""
        rules = await service._load_applicable_rules("日常病程记录")
        assert len(rules) >= 34  # SC 29条 + LX 5条 + 跨文书
        rule_ids = {r.get("rule_id") or r.get("rule_code") for r in rules}
        assert "SC-028" in rule_ids
        assert "LX-010" in rule_ids
        assert "CL-004" in rule_ids
        assert "CL-010" in rule_ids

    @pytest.mark.asyncio
    async def test_filter_rules_for_course_record_alias(self, service):
        """测试“病程记录”粗粒度别名能展开到具体病程文书类型"""
        rules = await service._load_applicable_rules("病程记录")
        assert len(rules) > 0
        rule_ids = {r.get("rule_id") or r.get("rule_code") for r in rules}
        # 首次病程 + 日常病程规则都应能命中
        assert "SC-021" in rule_ids
        assert "SC-028" in rule_ids

    @pytest.mark.asyncio
    async def test_filter_rules_for_surgery_record(self, service):
        """测试筛选手术记录适用规则"""
        rules = await service._load_applicable_rules("手术记录")
        assert len(rules) >= 15  # SC 11条 + LX 4条 + 跨文书
        rule_ids = {r.get("rule_id") or r.get("rule_code") for r in rules}
        assert "SC-095" in rule_ids
        assert "LX-025" in rule_ids

    @pytest.mark.asyncio
    async def test_filter_rules_for_discharge_record(self, service):
        """测试筛选出院记录适用规则"""
        rules = await service._load_applicable_rules("出院记录")
        assert len(rules) >= 13  # SC 12条 + LX 1条 + 跨文书
        rule_ids = {r.get("rule_id") or r.get("rule_code") for r in rules}
        assert "SC-116" in rule_ids
        assert "LX-029" in rule_ids

    @pytest.mark.asyncio
    async def test_filter_rules_for_consultation(self, service):
        """测试筛选会诊记录适用规则"""
        rules = await service._load_applicable_rules("会诊记录")
        assert len(rules) >= 7  # SC 5条 + LX 2-3条
        rule_ids = {r.get("rule_id") or r.get("rule_code") for r in rules}
        assert "SC-067" in rule_ids
        assert "LX-015" in rule_ids
        assert "CL-006" in rule_ids

    @pytest.mark.asyncio
    async def test_unknown_document_type_returns_empty(self, service):
        """测试未知文书类型返回空列表（无通用规则）"""
        rules = await service._load_applicable_rules("不存在的文书类型")
        assert len(rules) == 0

    def test_doc_type_mapping_covers_all_types(self, service):
        """验证 doc_type_mapping 覆盖了所有精确文书类型"""
        expected_types = [
            "admission_record", "first_course_record", "daily_course_record",
            "senior_course_record", "rescue_record", "diffcase_discussion_record",
            "death_discussion", "consultation_record", "surgery_record",
            "presurg_summary", "presurg_discussion", "postsurg_firstcourse_record",
            "surgery_safecheck_record", "surgery_risk_assessment",
            "anesthesia_record", "newborn_record", "bloodtrans_record",
            "nursing_record", "discharge_record", "consent_form",
            "exam_item_report", "labtest_item_report", "medical_order",
        ]
        for eng_type in expected_types:
            assert eng_type in service.doc_type_mapping, \
                f"doc_type_mapping 缺少 '{eng_type}'"
            assert service.doc_type_mapping[eng_type] != eng_type, \
                f"'{eng_type}' 未转为中文"


# ==================== Prompt 构建测试 ====================

class TestPromptBuilding:
    """测试 Prompt 构建"""

    @pytest.mark.asyncio
    async def test_build_prompt_with_rules(self, service):
        """测试使用规则构建 Prompt"""
        rules = (await service._load_applicable_rules("入院记录"))[:3]
        content = "患者男性，65岁，因胸痛3天入院。主诉：反复胸痛3天。"

        prompt = await service._build_prompt(rules, content, "入院记录")

        assert "资深病案质控专家" in prompt
        assert "入院记录" in prompt
        assert f"适用规则数: {len(rules)}" in prompt
        assert content in prompt

    @pytest.mark.asyncio
    async def test_build_prompt_without_rules(self, service):
        """测试无规则时构建 Prompt"""
        content = "这是一份病程记录的内容..."

        prompt = await service._build_prompt([], content, "日常病程记录")

        assert "资深病案质控专家" in prompt
        assert "日常病程记录" in prompt
        assert "适用规则数: 0" in prompt
        assert "未加载到具体规则" in prompt

    def test_parse_llm_json_response_with_think_tags(self, service):
        """测试 JSON 解析前会清理 <think> 标签"""
        llm_output = """
<think>
先进行推理过程...
</think>
[
  {
    "rule_id": "SC-001",
    "rule_name": "测试规则",
    "is_compliant": true,
    "findings": "合规",
    "evidence": "",
    "location": "主诉",
    "suggestion": "",
    "confidence": 0.93
  }
]
"""
        parsed = service._parse_llm_json_response(llm_output, rules=[{"rule_id": "SC-001"}])
        assert len(parsed) == 1
        assert parsed[0]["rule_id"] == "SC-001"
        assert parsed[0]["is_compliant"] is True


# ==================== CDM 数据查询测试 ====================

class TestCDMDataAccess:
    """测试通过 SQLAlchemy 查询 CDM 表获取病历内容"""

    def test_query_admission_record(self, seed_cdm_data):
        """测试查询入院记录"""
        from app.database.models.cdm import AdmissionRecord

        session = seed_cdm_data
        records = session.query(AdmissionRecord).filter_by(
            institute_id="TEST001", patient_id="P001"
        ).all()

        assert len(records) == 1
        assert records[0].record_content is not None
        assert "胸痛" in records[0].record_content
        assert "初步诊断" in records[0].record_content

    def test_query_first_course_record(self, seed_cdm_data):
        """测试查询首次病程记录"""
        from app.database.models.cdm import FirstCourseRecord

        session = seed_cdm_data
        records = session.query(FirstCourseRecord).filter_by(
            institute_id="TEST001", patient_id="P001"
        ).all()

        assert len(records) == 1
        assert "鉴别诊断" in records[0].record_content
        assert "诊疗计划" in records[0].record_content

    def test_query_surgery_record(self, seed_cdm_data):
        """测试查询手术记录"""
        from app.database.models.cdm import SurgeryRecord

        session = seed_cdm_data
        records = session.query(SurgeryRecord).filter_by(
            institute_id="TEST001", patient_id="P001"
        ).all()

        assert len(records) == 1
        assert "手术名称" in records[0].record_content
        assert "PCI" in records[0].record_content

    def test_query_discharge_record(self, seed_cdm_data):
        """测试查询出院记录"""
        from app.database.models.cdm import DischargeRecord

        session = seed_cdm_data
        records = session.query(DischargeRecord).filter_by(
            institute_id="TEST001", patient_id="P001"
        ).all()

        assert len(records) == 1
        assert "出院诊断" in records[0].record_content
        assert "出院医嘱" in records[0].record_content


# ==================== 评估流程测试 ====================

class TestEvaluation:
    """测试完整评估流程"""

    @pytest.mark.asyncio
    async def test_evaluate_with_admission_rules(self, service):
        """测试使用入院记录规则进行评估"""
        # Mock 统一规则引擎的 evaluate 方法
        mock_engine_result = {
            "rule_id": "SC-001",
            "status": "compliant",
            "is_compliant": True,
            "findings": "主诉描述完整",
            "evidence": "",
            "confidence": 0.95,
            "metadata": {"tokens_used": 200, "api_time": 0.5}
        }

        with patch.object(service.rule_engine, 'evaluate',
                         new_callable=AsyncMock, return_value=mock_engine_result):
            result = await service.evaluate_document(
                document_id="test-admission-001",
                content="患者男性，65岁，因胸痛3天入院。主诉：反复胸痛3天。",
                document_type="入院记录"
            )

            assert result["document_id"] == "test-admission-001"
            assert result["document_type"] == "入院记录"
            assert result["total_rules"] == 44  # 入院记录规则（SC + LX + LXE，去重后）
            assert len(result["applicable_rules"]) == 44

    @pytest.mark.asyncio
    async def test_evaluate_with_first_course_rules(self, service):
        """测试使用首次病程记录规则进行评估"""
        mock_engine_result = {
            "rule_id": "SC-021",
            "status": "compliant",
            "is_compliant": True,
            "findings": "病情分析完整",
            "evidence": "",
            "confidence": 0.9,
            "metadata": {"tokens_used": 150, "api_time": 0.4}
        }

        with patch.object(service.rule_engine, 'evaluate',
                         new_callable=AsyncMock, return_value=mock_engine_result):
            result = await service.evaluate_document(
                document_id="test-first-course-001",
                content="首次病程记录内容...",
                document_type="首次病程记录"
            )

            assert result["document_id"] == "test-first-course-001"
            assert result["document_type"] == "首次病程记录"
            assert result["total_rules"] >= 7  # SC-021~027 + LXE 展开


    @pytest.mark.asyncio
    async def test_evaluate_compliance_rate(self, service):
        """测试合规率计算"""
        call_count = {"n": 0}

        async def mock_evaluate(rule, medical_record):
            call_count["n"] += 1
            # 前 20 条合规，后 9 条不合规
            is_compliant = call_count["n"] <= 20
            return {
                "rule_id": rule.get("rule_id", f"R-{call_count['n']}"),
                "status": "compliant" if is_compliant else "non_compliant",
                "is_compliant": is_compliant,
                "findings": "合规" if is_compliant else "不合规",
                "evidence": "",
                "confidence": 0.9,
                "metadata": {"tokens_used": 100, "api_time": 0.3}
            }

        with (
            patch.object(service.rule_orchestrator._program_executor, "can_execute", return_value=False),
            patch.object(service.rule_engine, 'evaluate', side_effect=mock_evaluate),
        ):
            result = await service.evaluate_document(
                document_id="test-compliance-001",
                content="入院记录内容...",
                document_type="入院记录"
            )

            assert result["total_rules"] == 44
            # 20/44 合规
            summary = result["evaluation_summary"]
            assert summary["compliance_rate"] == pytest.approx(45.45, abs=1)
            assert summary["compliant_rules"] == 20
            assert summary["issues_found"] == 24

    @pytest.mark.asyncio
    async def test_evaluate_with_specific_rule_ids(self, service):
        """测试指定 rule_ids 精确评估"""
        mock_engine_result = {
            "rule_id": "SC-001",
            "status": "compliant",
            "is_compliant": True,
            "findings": "合规",
            "evidence": "",
            "confidence": 0.95,
            "metadata": {"tokens_used": 100, "api_time": 0.3}
        }

        with patch.object(service.rule_engine, 'evaluate',
                         new_callable=AsyncMock, return_value=mock_engine_result):
            result = await service.evaluate_document(
                document_id="test-specific-001",
                content="入院记录内容...",
                document_type="入院记录",
                rule_ids=["SC-001", "SC-002"]
            )

            # 指定了 2 条规则
            assert result["total_rules"] == 2

    @pytest.mark.asyncio
    async def test_evaluate_multi_document_default_course_record_has_rules(self, service):
        """测试多文书评估默认文书类型“病程记录”不会出现 0 规则空跑"""
        mock_engine_result = {
            "rule_id": "SC-021",
            "status": "compliant",
            "is_compliant": True,
            "findings": "合规",
            "evidence": "",
            "confidence": 0.95,
            "metadata": {"tokens_used": 50, "api_time": 0.1}
        }

        with patch.object(service.rule_engine, 'evaluate', new_callable=AsyncMock, return_value=mock_engine_result):
            result = await service.evaluate_multi_document(
                document_id="test-multi-default-001",
                document_content="患者病程记录内容..."
            )

            assert result["overall_summary"]["total_rules"] > 0
            assert "病程记录" in result["document_results"]
            assert result["document_results"]["病程记录"]["total_rules"] > 0


def test_build_bundle_evidence_payload_should_include_adjacent_round_similarity_signal(service):
    primary_document = {
        "id": "senior-20260204",
        "document_type": "senior_course_record",
        "source_table": "senior_course_record",
        "document_title": "副主任医师查房记录",
        "display_time": "2026-02-04 08:10:00",
        "content": "今日查房，患者神清，精神可，诉腰背部疼痛伴活动受限明显好转，纳眠可，二便调。",
    }
    all_documents = [
        primary_document,
        {
            "id": "daily-20260203",
            "document_type": "daily_course_record",
            "source_table": "daily_course_record",
            "document_title": "主治医师查房记录",
            "display_time": "2026-02-03 08:06:00",
            "content": "今日查房，患者神清，精神可，诉腰背部疼痛伴活动受限明显好转，纳眠可，二便调。",
        },
        {
            "id": "daily-20260120",
            "document_type": "daily_course_record",
            "source_table": "daily_course_record",
            "document_title": "既往病程记录",
            "display_time": "2026-01-20 08:00:00",
            "content": "患者一般情况稳定。",
        },
    ]

    payload = service._build_bundle_evidence_payload_for_document(
        primary_document=primary_document,
        all_documents=all_documents,
        bundle={"timeline_facts": [], "document_hits": {"daily_course_record": True}, "data_quality_flags": []},
        rules=[{"rule_id": "SC-050"}],
    )

    derived_signals = list(payload.get("derived_signals") or [])
    assert len(derived_signals) == 1
    signal = derived_signals[0]
    assert signal["signal_type"] == "adjacent_round_similarity"
    assert signal["compare_source_table"] == "daily_course_record"
    assert float(signal["similarity_ratio"]) >= 0.5
    assert float(signal["later_to_earlier_sentence_coverage"]) >= 0.85
    assert signal["lookback_window"] == 3


def test_build_bundle_evidence_payload_should_pick_best_match_within_lookback(service):
    primary_document = {
        "id": "senior-20260204",
        "document_type": "senior_course_record",
        "source_table": "senior_course_record",
        "document_title": "副主任医师查房记录",
        "display_time": "2026-02-04 08:10:00",
        "content": "今日查房，患者神清，精神可，诉腰背部疼痛伴活动受限明显好转，纳眠可，二便调。查体：腰部压痛减轻。继续治疗。",
    }
    all_documents = [
        primary_document,
        {
            "id": "daily-20260203",
            "document_type": "daily_course_record",
            "source_table": "daily_course_record",
            "document_title": "主治医师查房记录",
            "display_time": "2026-02-03 08:06:00",
            "content": "患者一般情况可。继续观察。",
        },
        {
            "id": "daily-20260202",
            "document_type": "daily_course_record",
            "source_table": "daily_course_record",
            "document_title": "主治医师查房记录",
            "display_time": "2026-02-02 08:06:00",
            "content": "今日查房，患者神清，精神可，诉腰背部疼痛伴活动受限明显好转，纳眠可，二便调。查体：腰部压痛减轻。继续治疗。",
        },
        {
            "id": "daily-20260201",
            "document_type": "daily_course_record",
            "source_table": "daily_course_record",
            "document_title": "主治医师查房记录",
            "display_time": "2026-02-01 08:06:00",
            "content": "诉腰痛反复，纳眠一般。",
        },
    ]

    payload = service._build_bundle_evidence_payload_for_document(
        primary_document=primary_document,
        all_documents=all_documents,
        bundle={"timeline_facts": [], "document_hits": {"daily_course_record": True}, "data_quality_flags": []},
        rules=[{"rule_id": "SC-050"}],
    )

    signal = list(payload.get("derived_signals") or [])[0]
    assert signal["compare_display_time"] == "2026-02-02 08:06:00"
    assert float(signal["later_to_earlier_sentence_coverage"]) >= 0.85


def test_merge_rule_input_with_bundle_documents_should_preserve_full_source_content(service):
    rule_input = RuleExecutionInput(
        rule_id="SC-050",
        document_type="上级查房记录",
        execution_domain="course",
        primary_medical_text="2026-02-04 查房正文",
        supporting_evidence=[],
        timeline_facts=[],
        source_documents=[],
    )
    long_content = "查房内容：" + ("腰痛缓解，继续治疗。" * 120)
    bundle = {
        "source_documents": [
            {
                "document_type": "senior_course_record",
                "source_table": "senior_course_record",
                "document_id": "senior-20260203",
                "document_title": "副主任医师查房记录",
                "display_time": "2026-02-03 11:07:40",
                "content": long_content,
                "text_preview": long_content[:200],
                "hit": True,
            }
        ]
    }

    merged = service._merge_rule_input_with_bundle_documents(
        rule_input=rule_input,
        bundle=bundle,
        include_doc_types=("senior_course_record",),
    )

    assert merged.source_documents
    assert merged.source_documents[0]["content"] == long_content
    assert len(str(merged.supporting_evidence[0]["evidence_text"])) <= 800


def test_score_primary_candidate_for_sc050_should_penalize_discharge_round(service):
    discharge_candidate = {
        "document_title": "郑瑞清副主任医师出院前查房记录",
        "display_time": "2026-02-09 09:34:44",
        "content": "今日郑瑞清副主任医师查房。现患者症状基本缓解，要求办理出院，经上级医师查看后同意出院，拟于明日办理。出院医嘱：门诊随访。",
    }
    adjacent_round_candidate = {
        "document_title": "郑瑞清副主任医师查房记录",
        "display_time": "2026-02-04 11:08:49",
        "content": "今日郑瑞清副主任医师代主治医师查房。目前诊断明确，治疗有效，继续原方案，密观。",
    }

    discharge_score = service._score_primary_candidate_for_rule(rule_id="SC-050", candidate=discharge_candidate)
    adjacent_score = service._score_primary_candidate_for_rule(rule_id="SC-050", candidate=adjacent_round_candidate)

    assert adjacent_score > discharge_score


def test_apply_sc050_similarity_semantic_fallback_should_force_non_compliant(service):
    rule_input = RuleExecutionInput(
        rule_id="SC-050",
        document_type="上级医师查房记录",
        execution_domain="course",
        primary_medical_text="2026-02-04 查房记录正文",
        supporting_evidence=[],
        timeline_facts=[],
        source_documents=[
            {
                "document_type": "senior_course_record",
                "source_table": "senior_course_record",
                "document_title": "郑瑞清副主任医师查房记录",
                "display_time": "2026-02-04 11:08:49",
                "content": "今日查房，患者神清，精神可，诉腰背部疼痛伴活动受限明显好转，纳眠可，二便调。",
                "hit": True,
            },
            {
                "document_type": "daily_course_record",
                "source_table": "daily_course_record",
                "document_title": "颜明秀主治医师查房记录",
                "display_time": "2026-02-03 11:07:40",
                "content": "今日查房，患者神清，精神可，诉腰背部疼痛伴活动受限明显好转，纳眠可，二便调。",
                "hit": True,
            },
        ],
    )
    engine_result = {
        "rule_id": "SC-050",
        "status": "compliant",
        "is_compliant": True,
        "findings": "合规",
        "evidence": "原始证据",
        "suggestion": "",
        "confidence": 0.72,
        "semantic_checks": {
            "has_new_analysis": False,
            "has_new_plan": False,
        },
        "metadata": {},
    }

    normalized = service._apply_sc050_similarity_semantic_fallback(
        rule_input=rule_input,
        engine_result=engine_result,
    )

    assert normalized["status"] == "non_compliant"
    assert normalized["is_compliant"] is False
    assert float(normalized["confidence"]) >= 0.86
    assert "后一天被前一天句子覆盖率" in normalized["evidence"]
    assert (normalized.get("metadata") or {}).get("decision_fallback") == "sc050_similarity_plus_semantic_check"


# ==================== RuleRouter 测试 ====================

class TestRuleRouter:
    """测试规则路由"""

    def test_router_loads_all_rules(self):
        """测试路由器加载所有规则"""
        from app.services.rule_router import RuleRouter
        router = RuleRouter()
        assert len(router._all_rules) > 200  # sichuan 179 + custom 89

    def test_router_backward_compat_progress_note(self):
        """测试 progress_note 旧类型兼容"""
        from app.services.rule_router import RuleRouter
        router = RuleRouter()
        rules = router.get_rules_for_section("progress_note")
        # progress_note 展开为 first_course + daily_course + senior_course + rescue
        assert len(rules) > 0
        doc_types = set()
        for r in rules:
            doc_types.update(r.get("applicable_documents", []))
        assert "first_course_record" in doc_types or "daily_course_record" in doc_types

    def test_router_precise_type(self):
        """测试精确文书类型路由"""
        from app.services.rule_router import RuleRouter
        router = RuleRouter()
        rules = router.get_rules_for_section("admission_record")
        assert len(rules) >= 29

    def test_router_unknown_type(self):
        """测试未知类型返回空"""
        from app.services.rule_router import RuleRouter
        router = RuleRouter()
        rules = router.get_rules_for_section("unknown_type_xyz")
        assert len(rules) == 0
