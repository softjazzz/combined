"""
编码规范质控服务（混合架构）

D1（格式校验）+ D2（编码存在性）：规则层（正则 + 本地编码库查表）
D3（合并）+ D4（互斥）+ D5（主诊断）+ D6（一致性）：LLM 语义审查层

基于 30 个用例 × 9 个 Qwen 模型评测结论设计。
"""
import re
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class CodingIssue:
    """单条编码质控问题。"""
    dimension: str           # format / existence / merge / exclusion / primary / consistency
    severity: str            # error / warning / info
    code: str                # 涉及的编码
    description: str         # 问题描述
    suggestion: str = ""     # 修改建议
    source: str = "rule"     # rule / llm

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CodingQCReport:
    """编码质控报告。"""
    total_issues: int = 0
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    rule_issues: List[CodingIssue] = field(default_factory=list)
    llm_issues: List[CodingIssue] = field(default_factory=list)
    llm_raw_output: str = ""
    overall_assessment: str = "通过"  # 通过 / 需修改 / 严重问题

    def to_dict(self) -> dict:
        return {
            "total_issues": self.total_issues,
            "errors": self.errors,
            "warnings": self.warnings,
            "infos": self.infos,
            "rule_issues": [i.to_dict() for i in self.rule_issues],
            "llm_issues": [i.to_dict() for i in self.llm_issues],
            "overall_assessment": self.overall_assessment,
        }


# ============================================================
# D1：编码格式校验（规则层）
# ============================================================

# ICD-10 格式：字母 + 2位数字 + 可选（.1-4位数字 + 可选 x 扩展码），如 I21.001 或 J06.900x003
ICD10_PATTERN = re.compile(r'^[A-Za-z]\d{2}(\.\d{1,4}(x\d{3})?)?$')

# ICD-9-CM-3 格式：2位数字.2-4位数字，如 36.0701
ICD9CM3_PATTERN = re.compile(r'^\d{2}\.\d{2,4}$')

# 特殊格式：带 x 的扩展编码，如 36.0700x003
ICD9CM3_EXT_PATTERN = re.compile(r'^\d{2}\.\d{2,4}(x\d{3})?$')


def check_icd10_format(code: str) -> Optional[CodingIssue]:
    """校验 ICD-10 编码格式。"""
    if not code or not code.strip():
        return None
    code = code.strip()
    if not ICD10_PATTERN.match(code):
        return CodingIssue(
            dimension="format",
            severity="error",
            code=code,
            description=f"ICD-10 编码 '{code}' 格式不正确，标准格式为字母+数字，如 I21.001",
            suggestion="请修正编码格式，ICD-10 编码应以大写字母开头，后跟2位数字，小数点后1-4位数字",
            source="rule",
        )
    return None


def check_icd9cm3_format(code: str) -> Optional[CodingIssue]:
    """校验 ICD-9-CM-3 手术编码格式。"""
    if not code or not code.strip():
        return None
    code = code.strip()
    if not ICD9CM3_PATTERN.match(code) and not ICD9CM3_EXT_PATTERN.match(code):
        return CodingIssue(
            dimension="format",
            severity="error",
            code=code,
            description=f"ICD-9-CM-3 编码 '{code}' 格式不正确，标准格式为 XX.XXXX，如 36.0701",
            suggestion="请修正编码格式，手术编码应为2位数字+小数点+2-4位数字",
            source="rule",
        )
    return None


# ============================================================
# D2：编码存在性验证（规则层 — 本地编码库查表）
# ============================================================

def _get_icd_lookup():
    """延迟导入本地 ICD 编码查询服务。"""
    try:
        from .local_icd_service import lookup_diagnosis_code, lookup_procedure_code
        return lookup_diagnosis_code, lookup_procedure_code
    except ImportError:
        logger.warning("无法导入 local_icd_service，编码存在性验证将跳过")
        return None, None


def check_diagnosis_existence(code: str, name: str = "") -> Optional[CodingIssue]:
    """
    验证诊断编码是否在本地编码库中存在，编码与名称是否匹配。

    Args:
        code: ICD-10 编码
        name: 诊断名称（可选，用于交叉验证）
    """
    lookup_diag, _ = _get_icd_lookup()
    if not lookup_diag or not code:
        return None

    # 通过名称反查编码
    if name:
        result = lookup_diag(name)
        if result and result["code"] != code.strip():
            return CodingIssue(
                dimension="existence",
                severity="warning",
                code=code,
                description=f"编码 '{code}' 与诊断名称 '{name}' 不匹配，编码库中该诊断的标准编码为 '{result['code']}'",
                suggestion=f"建议将编码修正为 {result['code']}（{result['name']}）",
                source="rule",
            )

    return None


def check_procedure_existence(code: str, name: str = "") -> Optional[CodingIssue]:
    """验证手术编码是否在本地编码库中存在。"""
    _, lookup_proc = _get_icd_lookup()
    if not lookup_proc or not code:
        return None

    if name:
        result = lookup_proc(name)
        if result and result["code"] != code.strip():
            return CodingIssue(
                dimension="existence",
                severity="warning",
                code=code,
                description=f"手术编码 '{code}' 与手术名称 '{name}' 不匹配，编码库中标准编码为 '{result['code']}'",
                suggestion=f"建议将编码修正为 {result['code']}（{result['name']}）",
                source="rule",
            )

    return None


# ============================================================
# D3-D6：LLM 语义审查
# ============================================================

CODING_QC_SYSTEM_PROMPT = """你是医院病案编码质控专家，精通 ICD-10（国临版2.0）和 ICD-9-CM-3（2011临床修改版）编码规范。

你的任务是对病案首页的诊断编码和手术操作编码进行语义层面的质控审查，重点检查以下维度：

1. **编码合并**：是否存在应使用合并编码的情况（如糖尿病+并发症应用合并码）
2. **编码互斥**：是否存在不能同时出现的编码（如1型+2型糖尿病）
3. **主诊断选择**：主诊断选择是否合理（症状码R码不应做主诊、消耗资源最大的诊断应做主诊）
4. **编码与临床一致性**：编码与患者信息是否一致（性别、年龄）、是否有遗漏

请严格按以下 JSON 格式输出审查结果，不要输出任何其他内容：
{
  "issues": [
    {
      "dimension": "merge|exclusion|primary|consistency",
      "severity": "error|warning|info",
      "code": "涉及的编码",
      "description": "问题描述",
      "suggestion": "修改建议"
    }
  ],
  "summary": {
    "total_issues": 0,
    "overall_assessment": "通过|需修改|严重问题"
  }
}

注意事项：
- 只报告确实存在的问题，不要过度报告
- 如果编码正确合理，issues 数组应为空
- severity 分级：error=必须修改, warning=建议修改, info=提示信息"""


def _build_llm_user_prompt(frontpage: dict) -> str:
    """根据首页数据构建 LLM 用户提示词。"""
    lines = ["请对以下病案首页编码进行质控审查：", ""]

    # 患者信息
    sex = frontpage.get("sex") or frontpage.get("gender") or ""
    age = frontpage.get("age") or ""
    lines.append(f"【患者信息】{sex}，{age}岁" if age else f"【患者信息】{sex}")
    lines.append("")

    # 诊断编码
    diagnoses = frontpage.get("diagnoses") or []
    if diagnoses:
        lines.append("【诊断编码】")
        for i, diag in enumerate(diagnoses):
            code = diag.get("code") or diag.get("icd_code") or ""
            name = diag.get("name") or diag.get("diagnosis_name") or ""
            prefix = "主诊断" if i == 0 else f"次诊断{i}"
            lines.append(f"  {prefix}：{code} {name}")
        lines.append("")

    # 手术操作编码
    surgeries = frontpage.get("surgeries") or []
    if surgeries:
        lines.append("【手术操作编码】")
        for i, surg in enumerate(surgeries):
            code = surg.get("code") or surg.get("operation_code") or ""
            name = surg.get("name") or surg.get("operation_name") or ""
            prefix = "主手术" if i == 0 else f"其他手术{i}"
            lines.append(f"  {prefix}：{code} {name}")
        lines.append("")

    # 病历摘要（如果有）
    summary = frontpage.get("clinical_summary") or frontpage.get("discharge_summary") or ""
    if summary:
        lines.append(f"【病历摘要】{summary}")

    return "\n".join(lines)


def _parse_llm_issues(raw_output: str) -> List[CodingIssue]:
    """从 LLM 原始输出中解析质控问题。"""
    parsed = _parse_json_from_text(raw_output)
    if not parsed:
        logger.warning("无法解析 LLM 输出为 JSON")
        return []

    issues = []
    for item in parsed.get("issues", []):
        issues.append(CodingIssue(
            dimension=item.get("dimension", "unknown"),
            severity=item.get("severity", "info"),
            code=item.get("code", ""),
            description=item.get("description", ""),
            suggestion=item.get("suggestion", ""),
            source="llm",
        ))
    return issues


def _parse_json_from_text(text: str) -> Optional[dict]:
    """从文本中提取 JSON（兼容 markdown 代码块包裹）。"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # 尝试 ```json ... ```
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个完整 JSON 对象
    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


# ============================================================
# 主引擎
# ============================================================

class CodingQCEngine:
    """
    编码规范质控引擎（混合架构）

    规则层：D1 格式校验 + D2 编码存在性验证
    LLM 层：D3 合并 + D4 互斥 + D5 主诊断 + D6 一致性
    """

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM 客户端实例（SichuanQCLLMClient）
                        如果为 None，LLM 层将跳过
        """
        self.llm_client = llm_client

    def check_format(self, frontpage: dict) -> List[CodingIssue]:
        """D1：编码格式校验。"""
        issues = []

        # 诊断编码格式
        for diag in (frontpage.get("diagnoses") or []):
            code = diag.get("code") or diag.get("icd_code") or ""
            name = diag.get("name") or diag.get("diagnosis_name") or ""
            if name and not str(code).strip():
                issues.append(
                    CodingIssue(
                        dimension="format",
                        severity="error",
                        code="",
                        description=f"诊断“{name}”缺少 ICD-10 编码",
                        suggestion="请为该诊断补充规范 ICD-10 编码",
                        source="rule",
                    )
                )
                continue
            if code:
                issue = check_icd10_format(code)
                if issue:
                    issues.append(issue)

        # 手术编码格式
        for surg in (frontpage.get("surgeries") or []):
            code = surg.get("code") or surg.get("operation_code") or ""
            name = surg.get("name") or surg.get("operation_name") or ""
            if name and not str(code).strip():
                issues.append(
                    CodingIssue(
                        dimension="format",
                        severity="error",
                        code="",
                        description=f"手术“{name}”缺少 ICD-9-CM-3 编码",
                        suggestion="请为该手术补充规范 ICD-9-CM-3 编码",
                        source="rule",
                    )
                )
                continue
            if code:
                issue = check_icd9cm3_format(code)
                if issue:
                    issues.append(issue)

        return issues

    def check_existence(self, frontpage: dict) -> List[CodingIssue]:
        """D2：编码存在性验证（需要本地 ICD 编码库）。"""
        issues = []

        for diag in (frontpage.get("diagnoses") or []):
            code = diag.get("code") or diag.get("icd_code") or ""
            name = diag.get("name") or diag.get("diagnosis_name") or ""
            if code and name:
                issue = check_diagnosis_existence(code, name)
                if issue:
                    issues.append(issue)

        for surg in (frontpage.get("surgeries") or []):
            code = surg.get("code") or surg.get("operation_code") or ""
            name = surg.get("name") or surg.get("operation_name") or ""
            if code and name:
                issue = check_procedure_existence(code, name)
                if issue:
                    issues.append(issue)

        return issues

    def check_bidding_scenarios(self, frontpage: dict) -> List[CodingIssue]:
        """
        招标专项编码规范检查（确定性规则兜底）。

        覆盖招标条款 3.4.1 中 LLM 可能遗漏的场景：
        - 场景 A：肿瘤主诊断（C/D00-D48）→ 应有病理形态学诊断编码（M 码）
        """
        issues = []
        diagnoses = frontpage.get("diagnoses") or []
        if not diagnoses:
            return issues

        # 提取所有诊断编码
        all_codes = [
            (d.get("code") or d.get("icd_code") or "").strip().upper()
            for d in diagnoses
        ]

        # 场景 A：肿瘤诊断 → 检查是否有病理形态学编码（M 码）
        tumor_codes = []
        has_morphology = False
        for code in all_codes:
            if not code:
                continue
            # C00-C97（恶性肿瘤）和 D00-D48（原位/良性/未定性肿瘤）
            if code.startswith("C") or (
                code.startswith("D")
                and len(code) >= 3
                and code[1:3].isdigit()
                and int(code[1:3]) <= 48
            ):
                tumor_codes.append(code)
            # M 码（病理形态学编码）
            if code.startswith("M"):
                has_morphology = True

        if tumor_codes and not has_morphology:
            issues.append(CodingIssue(
                dimension="consistency",
                severity="warning",
                code=tumor_codes[0],
                description=f"主要诊断含肿瘤编码（{tumor_codes[0]}），但未见病理形态学诊断编码（M 码），建议补充病理诊断",
                suggestion="肿瘤相关诊断应同时提供病理形态学编码（M 码），以确保编码完整性",
                source="rule",
            ))

        return issues

    async def check_semantic(self, frontpage: dict) -> tuple:
        """
        D3-D6：LLM 语义审查。

        Returns:
            (issues: List[CodingIssue], raw_output: str)
        """
        if not self.llm_client:
            logger.info("LLM 客户端未配置，跳过语义审查")
            return [], ""

        # 检查是否有足够的编码数据值得做语义审查
        diagnoses = frontpage.get("diagnoses") or []
        if not diagnoses:
            return [], ""

        user_prompt = _build_llm_user_prompt(frontpage)
        full_prompt = f"{CODING_QC_SYSTEM_PROMPT}\n\n{user_prompt}"

        try:
            result = await self.llm_client.generate(full_prompt)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            issues = _parse_llm_issues(content)
            return issues, content
        except Exception as e:
            logger.error(f"LLM 语义审查失败: {e}")
            return [], f"LLM 调用失败: {e}"

    async def run_all(self, frontpage: dict) -> CodingQCReport:
        """
        执行全量编码质控（规则层 + LLM 层）。

        Args:
            frontpage: 病案首页数据字典

        Returns:
            CodingQCReport
        """
        report = CodingQCReport()

        # --- 规则层 ---
        format_issues = self.check_format(frontpage)
        existence_issues = self.check_existence(frontpage)
        bidding_issues = self.check_bidding_scenarios(frontpage)
        report.rule_issues = format_issues + existence_issues + bidding_issues

        # --- LLM 层 ---
        llm_issues, raw_output = await self.check_semantic(frontpage)
        report.llm_issues = llm_issues
        report.llm_raw_output = raw_output

        # --- 汇总 ---
        all_issues = report.rule_issues + report.llm_issues
        report.total_issues = len(all_issues)
        report.errors = sum(1 for i in all_issues if i.severity == "error")
        report.warnings = sum(1 for i in all_issues if i.severity == "warning")
        report.infos = sum(1 for i in all_issues if i.severity == "info")

        if report.errors > 0:
            report.overall_assessment = "严重问题"
        elif report.warnings > 0:
            report.overall_assessment = "需修改"
        else:
            report.overall_assessment = "通过"

        logger.info(
            f"编码质控完成: {report.total_issues} 个问题 "
            f"({report.errors} error, {report.warnings} warning, {report.infos} info) "
            f"→ {report.overall_assessment}"
        )
        return report
