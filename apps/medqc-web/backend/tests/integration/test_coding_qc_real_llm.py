"""
编码质控 D3-D6 真实 LLM 集成测试。

调用真实 LLM API 验证语义审查能力，覆盖：
  D3 合并编码  — 可合并的诊断是否被建议合并
  D4 互斥编码  — 性别/年龄矛盾是否被检出
  D5 主诊断选择 — 术后并发症是否建议作为主诊断
  D6 临床一致性 — 诊断与手术是否一致

运行方式：
  MEDQC_ALLOW_REAL_LLM=1 pytest tests/integration/test_coding_qc_real_llm.py -v -s
  （未设置该变量时由 tests/conftest.py 统一跳过，避免全量测试意外计费）
  （需要 LLM 服务可用，预计单个用例 3-8 秒）
"""

import pytest
import asyncio
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def llm_engine():
    """初始化真实 LLM 编码质控引擎。"""
    from app.services.coding_qc_service import CodingQCEngine
    try:
        from app.services.qc_llm_client import SichuanQCLLMClient
        client = SichuanQCLLMClient()
        engine = CodingQCEngine(llm_client=client)
        logger.info("✅ 真实 LLM 引擎初始化成功")
        return engine
    except Exception as e:
        pytest.skip(f"LLM 客户端不可用: {e}")


@pytest.fixture(scope="module")
def rules_only_engine():
    """无 LLM 的纯规则引擎（用于对比）。"""
    from app.services.coding_qc_service import CodingQCEngine
    return CodingQCEngine(llm_client=None)


# ============================================================
# D3：合并编码测试
# ============================================================

class TestD3MergeCoding:
    """D3 合并编码：LLM 应识别可合并的诊断对。"""

    @pytest.mark.asyncio
    async def test_diabetes_with_diabetic_nephropathy(self, llm_engine):
        """
        场景：糖尿病 + 糖尿病肾病 → 应建议使用合并编码 E11.2
        国标编码规则：糖尿病伴有并发症时应使用合并编码。
        """
        fp = {
            "sex": "男",
            "age": "62岁",
            "diagnoses": [
                {"code": "E11.9", "name": "2型糖尿病"},
                {"code": "N08.3", "name": "糖尿病肾病"},
            ],
            "surgeries": [],
            "clinical_summary": "患者因2型糖尿病伴肾功能不全入院，查肌酐升高。"
        }
        t0 = time.time()
        report = await llm_engine.run_all(fp)
        elapsed = time.time() - t0
        logger.info(f"⏱ D3 糖尿病+肾病 耗时 {elapsed:.1f}s，检出 {report.total_issues} 个问题")

        # 验证
        assert report is not None
        llm_issues = report.llm_issues
        logger.info(f"LLM issues: {[i.description for i in llm_issues]}")

        # 应至少有一个关于合并/重复编码的建议
        merge_hints = [
            i for i in llm_issues
            if any(kw in i.description for kw in ["合并", "组合", "并发症", "重复", "E11.2"])
        ]
        assert len(merge_hints) > 0, \
            f"未检出糖尿病+糖尿病肾病的合并编码建议。LLM 输出: {report.llm_raw_output[:500]}"

    @pytest.mark.asyncio
    async def test_hypertension_with_heart_disease(self, llm_engine):
        """
        场景：高血压 + 高血压性心脏病 → 应建议合并编码 I11
        """
        fp = {
            "sex": "女",
            "age": "70岁",
            "diagnoses": [
                {"code": "I10", "name": "原发性高血压"},
                {"code": "I11.9", "name": "高血压性心脏病"},
            ],
            "surgeries": [],
            "clinical_summary": "患者长期高血压，心脏彩超示左室肥厚。"
        }
        report = await llm_engine.run_all(fp)
        llm_issues = report.llm_issues
        logger.info(f"D3 高血压+心脏病: {[i.description for i in llm_issues]}")

        merge_hints = [
            i for i in llm_issues
            if any(kw in i.description for kw in ["合并", "重复", "包含", "I11"])
        ]
        assert len(merge_hints) > 0, \
            f"未检出高血压+高血压心脏病的编码冗余。输出: {report.llm_raw_output[:500]}"


# ============================================================
# D4：互斥编码测试
# ============================================================

class TestD4MutualExclusion:
    """D4 互斥编码：LLM 应检出逻辑矛盾的编码组合。"""

    @pytest.mark.asyncio
    async def test_male_with_uterine_fibroid(self, llm_engine):
        """
        场景：男性 + 子宫肌瘤(D25) → 明显的性别-诊断矛盾
        """
        fp = {
            "sex": "男",
            "age": "45岁",
            "diagnoses": [
                {"code": "D25.9", "name": "子宫平滑肌瘤"},
                {"code": "I10", "name": "高血压"},
            ],
            "surgeries": [],
        }
        report = await llm_engine.run_all(fp)
        llm_issues = report.llm_issues
        logger.info(f"D4 男性+子宫肌瘤: {[i.description for i in llm_issues]}")

        # 应检出性别矛盾
        gender_issues = [
            i for i in llm_issues
            if any(kw in i.description for kw in ["性别", "男性", "子宫", "矛盾", "互斥", "不符"])
        ]
        assert len(gender_issues) > 0, \
            f"未检出男性-子宫肌瘤的性别矛盾。输出: {report.llm_raw_output[:500]}"

    @pytest.mark.asyncio
    async def test_child_with_senile_disease(self, llm_engine):
        """
        场景：5岁儿童 + 老年性白内障(H25) → 年龄-诊断矛盾
        """
        fp = {
            "sex": "男",
            "age": "5岁",
            "diagnoses": [
                {"code": "H25.9", "name": "老年性白内障"},
            ],
            "surgeries": [],
        }
        report = await llm_engine.run_all(fp)
        llm_issues = report.llm_issues
        logger.info(f"D4 儿童+老年白内障: {[i.description for i in llm_issues]}")

        age_issues = [
            i for i in llm_issues
            if any(kw in i.description for kw in ["年龄", "儿童", "老年", "矛盾", "不符", "不适"])
        ]
        assert len(age_issues) > 0, \
            f"未检出5岁儿童-老年白内障的年龄矛盾。输出: {report.llm_raw_output[:500]}"


# ============================================================
# D5：主诊断选择测试
# ============================================================

class TestD5PrimaryDiagnosis:
    """D5 主诊断选择：LLM 应对不合理的主诊断提出建议。"""

    @pytest.mark.asyncio
    async def test_complication_should_be_primary(self, llm_engine):
        """
        场景：主诊断为高血压，但实际做了阑尾切除术 →
              应建议将急性阑尾炎作为主诊断
        """
        fp = {
            "sex": "男",
            "age": "35岁",
            "diagnoses": [
                {"code": "I10", "name": "原发性高血压"},   # 主诊断
                {"code": "K35.8", "name": "急性阑尾炎"},  # 其他诊断
            ],
            "surgeries": [
                {"code": "47.09", "name": "阑尾切除术"},
            ],
            "clinical_summary": "患者因转移性右下腹痛6小时入院，诊断急性阑尾炎行阑尾切除术。"
        }
        report = await llm_engine.run_all(fp)
        llm_issues = report.llm_issues
        logger.info(f"D5 主诊断选择: {[i.description for i in llm_issues]}")

        primary_issues = [
            i for i in llm_issues
            if any(kw in i.description for kw in ["主诊断", "阑尾", "手术", "选择", "调整", "不当"])
        ]
        assert len(primary_issues) > 0, \
            f"未建议将阑尾炎调整为主诊断。输出: {report.llm_raw_output[:500]}"

    @pytest.mark.asyncio
    async def test_correct_primary_no_warning(self, llm_engine):
        """
        场景：主诊断为急性阑尾炎，手术为阑尾切除术 → 应无主诊断问题
        """
        fp = {
            "sex": "女",
            "age": "28岁",
            "diagnoses": [
                {"code": "K35.8", "name": "急性阑尾炎"},  # 主诊断
                {"code": "I10", "name": "高血压"},
            ],
            "surgeries": [
                {"code": "47.09", "name": "阑尾切除术"},
            ],
        }
        report = await llm_engine.run_all(fp)
        llm_issues = report.llm_issues
        logger.info(f"D5 正确主诊断: {[i.description for i in llm_issues]}")

        # 主诊断选择正确，不应有主诊断相关的严重问题
        primary_errors = [
            i for i in llm_issues
            if i.severity == "error" and
            any(kw in i.description for kw in ["主诊断选择不当", "主诊断错误"])
        ]
        assert len(primary_errors) == 0, \
            f"正确的主诊断不应报错。输出: {report.llm_raw_output[:500]}"


# ============================================================
# D6：临床一致性测试
# ============================================================

class TestD6ClinicalConsistency:
    """D6 临床一致性：LLM 应检出诊断与手术不匹配的情况。"""

    @pytest.mark.asyncio
    async def test_surgery_without_matching_diagnosis(self, llm_engine):
        """
        场景：做了胆囊切除术，但诊断中没有胆囊相关疾病
        """
        fp = {
            "sex": "女",
            "age": "50岁",
            "diagnoses": [
                {"code": "J18.9", "name": "肺炎"},
            ],
            "surgeries": [
                {"code": "51.22", "name": "胆囊切除术"},
            ],
            "clinical_summary": "患者因肺炎入院治疗。"
        }
        report = await llm_engine.run_all(fp)
        llm_issues = report.llm_issues
        logger.info(f"D6 手术-诊断不匹配: {[i.description for i in llm_issues]}")

        consistency_issues = [
            i for i in llm_issues
            if any(kw in i.description for kw in [
                "胆囊", "手术", "诊断", "不匹配", "不一致", "缺少", "遗漏"
            ])
        ]
        assert len(consistency_issues) > 0, \
            f"未检出胆囊切除术缺少对应诊断的问题。输出: {report.llm_raw_output[:500]}"

    @pytest.mark.asyncio
    async def test_postop_complication_missing(self, llm_engine):
        """
        场景：做了冠脉支架植入术，但诊断中未包含术后状态编码
        """
        fp = {
            "sex": "男",
            "age": "58岁",
            "diagnoses": [
                {"code": "I21.0", "name": "急性前壁心肌梗死"},
            ],
            "surgeries": [
                {"code": "36.07", "name": "冠状动脉支架植入术"},
            ],
            "clinical_summary": "患者因急性心梗行PCI术，术后恢复良好。"
        }
        report = await llm_engine.run_all(fp)
        llm_issues = report.llm_issues
        logger.info(f"D6 术后编码缺失: {[i.description for i in llm_issues]}")

        # 应建议补充术后编码或支架状态编码
        postop_hints = [
            i for i in llm_issues
            if any(kw in i.description for kw in [
                "术后", "PCI", "支架", "Z95", "补充", "遗漏", "冠脉"
            ])
        ]
        # 这个是建议级别，不强制断言但记录
        if len(postop_hints) == 0:
            logger.warning("⚠️ LLM 未建议补充术后编码（可接受但非最优）")

    @pytest.mark.asyncio
    async def test_consistent_case_no_issue(self, llm_engine):
        """
        场景：诊断与手术完全一致 → 不应有一致性问题
        """
        fp = {
            "sex": "男",
            "age": "45岁",
            "diagnoses": [
                {"code": "K80.1", "name": "胆囊结石伴胆囊炎"},
            ],
            "surgeries": [
                {"code": "51.22", "name": "胆囊切除术"},
            ],
            "clinical_summary": "患者因反复右上腹痛入院，诊断胆囊结石伴胆囊炎行胆囊切除术。"
        }
        report = await llm_engine.run_all(fp)
        llm_issues = report.llm_issues
        logger.info(f"D6 一致性良好: {[i.description for i in llm_issues]}")

        # 完全一致的情况不应有严重错误
        severe_issues = [i for i in llm_issues if i.severity == "error"]
        assert len(severe_issues) == 0, \
            f"完全一致的诊断-手术不应有严重错误。输出: {report.llm_raw_output[:500]}"


# ============================================================
# 综合场景测试
# ============================================================

class TestComprehensiveScenario:
    """综合场景：多个维度同时触发。"""

    @pytest.mark.asyncio
    async def test_multiple_issues_combined(self, llm_engine):
        """
        场景：同时包含多种问题
        - 男性 + 子宫肌瘤（D4 互斥）
        - 高血压为主诊断但做了阑尾切除（D5 主诊断）
        - 格式错误 12345（D1 规则层）
        """
        fp = {
            "sex": "男",
            "age": "40岁",
            "diagnoses": [
                {"code": "I10", "name": "原发性高血压"},
                {"code": "K35.8", "name": "急性阑尾炎"},
                {"code": "D25.9", "name": "子宫平滑肌瘤"},
                {"code": "12345", "name": "无效编码"},
            ],
            "surgeries": [
                {"code": "47.09", "name": "阑尾切除术"},
            ],
        }
        report = await llm_engine.run_all(fp)
        logger.info(
            f"综合场景: 总{report.total_issues}个问题 "
            f"(rule={len(report.rule_issues)}, llm={len(report.llm_issues)})"
        )
        for i in report.rule_issues:
            logger.info(f"  [规则] {i.dimension}: {i.description}")
        for i in report.llm_issues:
            logger.info(f"  [LLM]  {i.dimension}: {i.description}")

        # 至少应有 3 个问题（格式 + 性别互斥 + 主诊断）
        assert report.total_issues >= 3, \
            f"综合场景应至少检出 3 个问题，实际 {report.total_issues}"

    @pytest.mark.asyncio
    async def test_performance_within_budget(self, llm_engine):
        """性能测试：单次完整质控应在 15 秒内完成。"""
        fp = {
            "sex": "女",
            "age": "65岁",
            "diagnoses": [
                {"code": "I21.0", "name": "急性前壁心肌梗死"},
                {"code": "E11.9", "name": "2型糖尿病"},
                {"code": "I10", "name": "高血压"},
                {"code": "N18.3", "name": "慢性肾脏病3期"},
            ],
            "surgeries": [
                {"code": "36.07", "name": "冠状动脉支架植入术"},
            ],
            "clinical_summary": "患者因胸痛3小时入院，诊断急性心梗行PCI术，合并糖尿病、高血压、慢性肾病。"
        }
        t0 = time.time()
        report = await llm_engine.run_all(fp)
        elapsed = time.time() - t0
        logger.info(f"⏱ 性能测试: {elapsed:.1f}s, {report.total_issues} 个问题")

        assert elapsed < 15, f"LLM 编码质控耗时 {elapsed:.1f}s 超过 15s 预算"
        assert report is not None
