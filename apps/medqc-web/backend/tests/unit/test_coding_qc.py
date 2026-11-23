"""
编码质控服务单元测试

测试 D1（格式校验）和 D2（存在性验证）规则层，
以及 D3-D6 LLM 层的 JSON 解析逻辑。
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.coding_qc_service import (
    CodingQCEngine,
    CodingIssue,
    CodingQCReport,
    check_icd10_format,
    check_icd9cm3_format,
    _parse_json_from_text,
    _build_llm_user_prompt,
    _parse_llm_issues,
)


# ============================================================
# D1：格式校验测试
# ============================================================

class TestICD10Format:
    """ICD-10 编码格式校验。"""

    def test_valid_standard(self):
        """I21.001 标准格式应通过。"""
        assert check_icd10_format("I21.001") is None

    def test_valid_short(self):
        """I10 短格式（无亚目）应通过。"""
        assert check_icd10_format("I10") is None

    def test_valid_one_decimal(self):
        """E11.9 一位小数应通过。"""
        assert check_icd10_format("E11.9") is None

    def test_valid_cross_asterisk_code(self):
        """E11.401+G63.2* 剑号星号组合码应通过。"""
        assert check_icd10_format("E11.401+G63.2*") is None

    def test_valid_morphology_code(self):
        """M80451/3 病理形态学编码应通过。"""
        assert check_icd10_format("M80451/3") is None

    def test_valid_tumor_with_morphology_code(self):
        """C22.101M81600/3 肿瘤诊断拼接 M 码应通过。"""
        assert check_icd10_format("C22.101M81600/3") is None

    def test_invalid_missing_letter(self):
        """21.001 缺字母前缀应报错。"""
        issue = check_icd10_format("21.001")
        assert issue is not None
        assert issue.dimension == "format"
        assert issue.severity == "error"

    def test_invalid_number_only(self):
        """纯数字应报错。"""
        issue = check_icd10_format("123456")
        assert issue is not None

    def test_empty_string(self):
        """空字符串应返回 None（跳过）。"""
        assert check_icd10_format("") is None
        assert check_icd10_format(None) is None


class TestICD9CM3Format:
    """ICD-9-CM-3 手术编码格式校验。"""

    def test_valid_standard(self):
        """36.0701 标准格式应通过。"""
        assert check_icd9cm3_format("36.0701") is None

    def test_valid_short(self):
        """47.09 短格式应通过。"""
        assert check_icd9cm3_format("47.09") is None

    def test_valid_extended(self):
        """36.0700x003 扩展格式应通过。"""
        assert check_icd9cm3_format("36.0700x003") is None

    def test_valid_local_icd9_x_codes(self):
        """本地 ICD-9-CM-3 库中的 x 扩展编码应通过。"""
        assert check_icd9cm3_format("54.3x01") is None
        assert check_icd9cm3_format("54.4x00x035") is None

    def test_invalid_no_dot(self):
        """360701 缺分隔点应报错。"""
        issue = check_icd9cm3_format("360701")
        assert issue is not None
        assert issue.dimension == "format"
        assert issue.severity == "error"

    def test_invalid_letter_prefix(self):
        """A36.07 手术编码不应有字母前缀。"""
        issue = check_icd9cm3_format("A36.07")
        assert issue is not None

    def test_empty_string(self):
        """空字符串应返回 None。"""
        assert check_icd9cm3_format("") is None


# ============================================================
# D1：引擎级格式校验
# ============================================================

class TestCodingQCEngineFormat:
    """CodingQCEngine.check_format() 集成测试。"""

    def setup_method(self):
        self.engine = CodingQCEngine(llm_client=None)

    def test_all_valid_codes(self):
        """所有编码格式正确时应无问题。"""
        fp = {
            "diagnoses": [
                {"code": "I21.001", "name": "急性心梗"},
                {"code": "E11.900", "name": "2型糖尿病"},
                {"code": "E11.401+G63.2*", "name": "2型糖尿病性周围神经病"},
                {"code": "M80451/3", "name": "小细胞-腺癌"},
            ],
            "surgeries": [
                {"code": "36.0701", "name": "PCI"},
                {"code": "54.3x01", "name": "腹壁病损切除术"},
                {"code": "54.4x00x035", "name": "盆腔病损切除术"},
            ],
        }
        issues = self.engine.check_format(fp)
        assert len(issues) == 0

    def test_mixed_valid_invalid(self):
        """混合正确和错误编码。"""
        fp = {
            "diagnoses": [
                {"code": "I21.001", "name": "正确"},
                {"code": "21.001", "name": "缺字母"},
            ],
            "surgeries": [
                {"code": "360701", "name": "缺分隔点"},
            ],
        }
        issues = self.engine.check_format(fp)
        assert len(issues) == 2  # 一个诊断 + 一个手术

    def test_empty_frontpage(self):
        """空首页应无问题。"""
        issues = self.engine.check_format({})
        assert len(issues) == 0

    def test_missing_code_field(self):
        """诊断无编码字段应报错（缺少 ICD 编码）。"""
        fp = {"diagnoses": [{"name": "无编码诊断"}]}
        issues = self.engine.check_format(fp)
        assert len(issues) == 1
        assert issues[0].dimension == "format"
        assert issues[0].severity == "error"


# ============================================================
# LLM 输出解析测试
# ============================================================

class TestLLMParsing:
    """LLM 输出 JSON 解析。"""

    def test_parse_clean_json(self):
        """直接 JSON 应能解析。"""
        text = '{"issues": [{"dimension": "merge", "severity": "warning", "code": "E11.900", "description": "test", "suggestion": "fix"}], "summary": {"total_issues": 1, "overall_assessment": "需修改"}}'
        result = _parse_json_from_text(text)
        assert result is not None
        assert len(result["issues"]) == 1

    def test_parse_markdown_wrapped(self):
        """```json 包裹应能解析。"""
        text = '一些前缀文字\n```json\n{"issues": [], "summary": {"total_issues": 0}}\n```\n后缀文字'
        result = _parse_json_from_text(text)
        assert result is not None
        assert len(result["issues"]) == 0

    def test_parse_mixed_text(self):
        """混合文本中提取 JSON。"""
        text = '分析结果如下：\n{"issues": [{"dimension": "exclusion", "severity": "error", "code": "O80", "description": "互斥", "suggestion": "修改"}], "summary": {"total_issues": 1}}\n以上。'
        result = _parse_json_from_text(text)
        assert result is not None
        assert result["issues"][0]["dimension"] == "exclusion"

    def test_parse_invalid(self):
        """无效文本应返回 None。"""
        assert _parse_json_from_text("这不是JSON") is None
        assert _parse_json_from_text("") is None

    def test_parse_llm_issues(self):
        """_parse_llm_issues 应正确转换为 CodingIssue 列表。"""
        raw = '{"issues": [{"dimension": "merge", "severity": "warning", "code": "E11.900", "description": "应合并", "suggestion": "使用E11.200"}], "summary": {"total_issues": 1}}'
        issues = _parse_llm_issues(raw)
        assert len(issues) == 1
        assert issues[0].dimension == "merge"
        assert issues[0].source == "llm"


# ============================================================
# Prompt 构建测试
# ============================================================

class TestPromptBuilder:
    """LLM 提示词构建。"""

    def test_full_frontpage(self):
        """完整首页数据应生成包含所有信息的 prompt。"""
        fp = {
            "sex": "男",
            "age": 65,
            "diagnoses": [
                {"code": "I21.001", "name": "急性心梗"},
                {"code": "E11.900", "name": "2型糖尿病"},
            ],
            "surgeries": [
                {"code": "36.0701", "name": "PCI"},
            ],
            "clinical_summary": "患者因胸痛入院",
        }
        prompt = _build_llm_user_prompt(fp)
        assert "男" in prompt
        assert "65" in prompt
        assert "I21.001" in prompt
        assert "主诊断" in prompt
        assert "次诊断" in prompt
        assert "PCI" in prompt
        assert "胸痛" in prompt

    def test_minimal_frontpage(self):
        """最小首页数据也应能构建。"""
        prompt = _build_llm_user_prompt({"sex": "女"})
        assert "女" in prompt


# ============================================================
# run_all 集成测试（Mock LLM）
# ============================================================

class TestCodingQCEngineRunAll:
    """CodingQCEngine.run_all() 完整流程。"""

    @pytest.mark.asyncio
    async def test_run_all_rules_only(self):
        """无 LLM 客户端时只执行规则层。"""
        engine = CodingQCEngine(llm_client=None)
        fp = {
            "diagnoses": [
                {"code": "I21.001", "name": "急性心梗"},
                {"code": "21.001", "name": "缺字母"},  # 格式错误
            ],
        }
        report = await engine.run_all(fp)
        assert isinstance(report, CodingQCReport)
        assert report.total_issues >= 1
        assert report.errors >= 1
        assert report.overall_assessment == "严重问题"

    @pytest.mark.asyncio
    async def test_run_all_with_mock_llm(self):
        """带 Mock LLM 的完整流程。"""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = {
            "choices": [{
                "message": {
                    "content": '{"issues": [{"dimension": "merge", "severity": "warning", "code": "E11.900", "description": "应合并编码", "suggestion": "使用E11.200"}], "summary": {"total_issues": 1, "overall_assessment": "需修改"}}'
                }
            }]
        }

        engine = CodingQCEngine(llm_client=mock_llm)
        fp = {
            "diagnoses": [
                {"code": "I21.001", "name": "心梗"},
                {"code": "E11.900", "name": "糖尿病"},
            ],
        }
        report = await engine.run_all(fp)
        assert report.total_issues >= 1
        assert len(report.llm_issues) == 1
        assert report.llm_issues[0].source == "llm"

    @pytest.mark.asyncio
    async def test_run_all_empty_frontpage(self):
        """空首页应顺利执行。"""
        engine = CodingQCEngine(llm_client=None)
        report = await engine.run_all({})
        assert report.total_issues == 0
        assert report.overall_assessment == "通过"

    @pytest.mark.asyncio
    async def test_report_to_dict(self):
        """报告序列化为 dict。"""
        engine = CodingQCEngine(llm_client=None)
        report = await engine.run_all({})
        d = report.to_dict()
        assert "total_issues" in d
        assert "rule_issues" in d
        assert "llm_issues" in d
        assert "overall_assessment" in d
        assert d["llm_review_completed"] is False
        assert d["llm_review_status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_run_all_llm_timeout_marks_semantic_incomplete(self):
        """LLM 超时时，应显式返回 llm_review_completed=False 且 llm_review_status='timeout'。"""
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = TimeoutError("upstream timeout")

        engine = CodingQCEngine(llm_client=mock_llm)
        fp = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
        report = await engine.run_all(fp)
        d = report.to_dict()
        assert report.llm_review_completed is False
        assert report.llm_review_status == "timeout"
        assert d["llm_review_completed"] is False
        assert d["llm_review_status"] == "timeout"
        assert d["llm_issues"] == []

    @pytest.mark.asyncio
    async def test_run_all_llm_error_marks_semantic_incomplete(self):
        """LLM 抛出一般异常时，应显式返回 llm_review_completed=False 且 llm_review_status='error'。"""
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = RuntimeError("connection reset")

        engine = CodingQCEngine(llm_client=mock_llm)
        fp = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
        report = await engine.run_all(fp)
        d = report.to_dict()
        assert d["llm_review_completed"] is False
        assert d["llm_review_status"] == "error"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_content",
        [
            "",
            "这不是合法 JSON 输出",
            "{}",
            '{"summary": {"total_issues": 0}}',
            '{"issues": "not-a-list"}',
            "[]",
            '[{"issues": []}]',
            '结果：[{"issues":[]}',
            '```json\n{"issues": []}',
            '```json\n[{"issues": []}]\n```',
            '分析结果如下：\n[{"issues": []}]\n以上。',
            '{"issues": []}]',
            '{"issues": [{}]}',
            '{"issues": [{"severity": "high"}]}',
            '{"issues": [{"dimension": "merge"}]}',
            '{"issues": [{"description": "缺少维度"}]}',
            '{"issues": [{"dimension": "merge", "description": "缺severity"}]}',
            '{"issues": [{"dimension": "merge", "severity": null, "description": "null severity"}]}',
            '{"issues": [{"dimension": "merge", "severity": "high", "description": "无效严重级别"}]}',
        ],
    )
    async def test_run_all_llm_unparseable_or_empty_marks_parse_failed(self, bad_content):
        """LLM 输出为空、非顶层对象、顶层/截断数组、未闭合围栏或 issue 缺少必填字段时，应标记 parse_failed 且未完成。"""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = {
            "choices": [{"message": {"content": bad_content}}]
        }

        engine = CodingQCEngine(llm_client=mock_llm)
        fp = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
        report = await engine.run_all(fp)
        d = report.to_dict()
        assert d["llm_review_completed"] is False
        assert d["llm_review_status"] == "parse_failed"
        assert d["llm_issues"] == []

    @pytest.mark.asyncio
    async def test_run_all_llm_valid_issue_payload_marks_completed(self):
        """LLM 返回包含完整合法 issue 对象的 JSON 时，应标记 completed 且保留解析结果。"""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = {
            "choices": [{
                "message": {
                    "content": (
                        '{"issues": [{"dimension": "exclusion", "severity": "error", '
                        '"code": "E10/E11", "description": "1型与2型糖尿病互斥", '
                        '"suggestion": "核实分型后仅保留其一"}]}'
                    )
                }
            }]
        }

        engine = CodingQCEngine(llm_client=mock_llm)
        fp = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
        report = await engine.run_all(fp)
        d = report.to_dict()
        assert d["llm_review_completed"] is True
        assert d["llm_review_status"] == "completed"
        assert len(d["llm_issues"]) == 1
        assert d["llm_issues"][0]["dimension"] == "exclusion"
        assert d["llm_issues"][0]["description"] == "1型与2型糖尿病互斥"

    @pytest.mark.asyncio
    async def test_run_all_llm_valid_empty_issues_marks_completed(self):
        """LLM 正常返回 0 问题合法 JSON 时，应标记 completed 且 llm_review_completed=True。"""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = {
            "choices": [{
                "message": {
                    "content": '{"issues": [], "summary": {"total_issues": 0, "overall_assessment": "通过"}}'
                }
            }]
        }

        engine = CodingQCEngine(llm_client=mock_llm)
        fp = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
        report = await engine.run_all(fp)
        d = report.to_dict()
        assert d["llm_review_completed"] is True
        assert d["llm_review_status"] == "completed"
        assert d["llm_issues"] == []

    @pytest.mark.asyncio
    async def test_run_all_skip_llm_marks_skipped(self):
        """显式 skip_llm=True 时不调用 LLM，并标记 skipped 且未完成。"""
        mock_llm = AsyncMock()
        engine = CodingQCEngine(llm_client=mock_llm)
        fp = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
        report = await engine.run_all(fp, skip_llm=True)
        d = report.to_dict()
        mock_llm.generate.assert_not_awaited()
        assert d["llm_review_completed"] is False
        assert d["llm_review_status"] == "skipped"
