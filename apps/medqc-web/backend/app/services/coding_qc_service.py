"""
编码规范质控服务（混合架构）

D1（格式校验）+ D2（编码存在性）：规则层（正则 + 本地编码库查表）
D3（合并）+ D4（互斥）+ D5（主诊断）+ D6（一致性）：LLM 语义审查层

基于 30 个用例 × 9 个 Qwen 模型评测结论设计。
"""
import asyncio
import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
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
    rule_id: str = ""        # 确定性规则编号
    rule_name: str = ""      # 规则名称
    location: str = "病案首页编码区"
    evidence: str = ""

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
    llm_review_completed: bool = False
    llm_review_status: str = "skipped"  # completed / skipped / unavailable / timeout / error / parse_failed

    def to_dict(self) -> dict:
        return {
            "total_issues": self.total_issues,
            "errors": self.errors,
            "warnings": self.warnings,
            "infos": self.infos,
            "rule_issues": [i.to_dict() for i in self.rule_issues],
            "llm_issues": [i.to_dict() for i in self.llm_issues],
            "overall_assessment": self.overall_assessment,
            "llm_review_completed": self.llm_review_completed,
            "llm_review_status": self.llm_review_status,
        }


# ============================================================
# D1：编码格式校验（规则层）
# ============================================================

# ICD-10/医保诊断编码格式：普通 ICD-10、剑号星号组合码、病理形态学 M 码、肿瘤诊断+M 码。
ICD10_BASE = r'[A-Za-z]\d{2}(?:\.[A-Za-z0-9]{1,9})?'
MORPHOLOGY_BASE = r'M\d{4,5}/\d'
ICD10_PATTERN = re.compile(
    rf'^(?:'
    rf'{ICD10_BASE}(?:\*)?(?:\+{ICD10_BASE}(?:\*)?)?'
    rf'|{MORPHOLOGY_BASE}'
    rf'|{ICD10_BASE}{MORPHOLOGY_BASE}'
    rf')$',
    re.IGNORECASE,
)

# ICD-9-CM-3 手术操作编码格式：2位数字 + 小数点 + 数字/x 扩展，如 36.0701、54.3x01、54.4x00x035。
ICD9CM3_PATTERN = re.compile(r'^\d{2}\.\d[0-9x]{1,9}$', re.IGNORECASE)


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
            description=f"ICD-10/诊断编码 '{code}' 格式不正确，标准格式如 I21.001、E11.401+G63.2* 或 M81400/3",
            suggestion="请核对诊断编码格式；本地编码库支持 ICD-10 扩展码、剑号星号组合码和病理形态学 M 码",
            source="rule",
        )
    return None


def check_icd9cm3_format(code: str) -> Optional[CodingIssue]:
    """校验 ICD-9-CM-3 手术编码格式。"""
    if not code or not code.strip():
        return None
    code = code.strip()
    if not ICD9CM3_PATTERN.match(code):
        return CodingIssue(
            dimension="format",
            severity="error",
            code=code,
            description=f"ICD-9-CM-3 编码 '{code}' 格式不正确，标准格式如 36.0701、54.3x01 或 54.4x00x035",
            suggestion="请核对手术操作编码格式；本地编码库支持数字小数码和 x 扩展码",
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

    策略：
      1. 精确匹配 → 直接通过
      2. 病历用上级码，库里有更精确子码 → 通过，但给 info 级推荐建议
      3. 编码库中完全找不到 → warning，按名称反查给出建议
    """
    lookup_diag, _ = _get_icd_lookup()
    if not lookup_diag or not code:
        return None

    code = code.strip()

    try:
        from .local_icd_service import _get_icd_data
        clinical_data, insurance_data, _, _ = _get_icd_data()
        source = clinical_data if clinical_data else insurance_data
        if source:
            # 先查精确匹配
            for item in source:
                if item['code'] == code:
                    return None  # 精确命中，无需任何提示

            # 再查上级码匹配（库中有以 code 为前缀的更精确子码）
            specific_candidates = [
                item for item in source
                if item['code'].startswith(code) and item['code'] != code
            ]
            if specific_candidates:
                # 按编码长度升序，取最短（即最直接的子码）
                specific_candidates.sort(key=lambda x: len(x['code']))
                best = specific_candidates[0]
                return CodingIssue(
                    dimension="existence",
                    severity="info",
                    code=code,
                    description=(
                        f"编码 '{code}' 为上级类目码，编码库中存在更精确的子码 "
                        f"'{best['code']}'（{best['name']}）"
                    ),
                    suggestion=f"建议使用更精确的编码 {best['code']}（{best['name']}），以提升编码质量",
                    source="rule",
                )
    except Exception:
        pass

    # 编码库中完全找不到该编码 → 按名称反查给出建议
    if name:
        result = lookup_diag(name)
        if result:
            return CodingIssue(
                dimension="existence",
                severity="warning",
                code=code,
                description=f"编码 '{code}' 未在本地编码库中找到，根据诊断名称 '{name}' 查询，建议编码为 '{result['code']}'",
                suggestion=f"建议将编码修正为 {result['code']}（{result['name']}）",
                source="rule",
            )
        else:
            return CodingIssue(
                dimension="existence",
                severity="info",
                code=code,
                description=f"编码 '{code}'（{name}）未在本地编码库中找到，请人工核实",
                suggestion="请核实该编码是否正确",
                source="rule",
            )

    return None




def check_procedure_existence(code: str, name: str = "") -> Optional[CodingIssue]:
    """验证手术编码是否在本地编码库中存在（编码优先正查）。"""
    _, lookup_proc = _get_icd_lookup()
    if not lookup_proc or not code:
        return None

    code = code.strip()

    # 1. 先按编码正查
    try:
        from .local_icd_service import _get_icd_data
        _, _, icd9_data, _ = _get_icd_data()
        if icd9_data:
            for item in icd9_data:
                lib_code = item['code']
                # 精确匹配 或 库码是病历码的扩展（病历用上级码兜底）
                if lib_code == code or lib_code.startswith(code):
                    return None  # 编码存在，直接通过
    except Exception:
        pass

    # 2. 编码不存在 → 名称反查
    if name:
        result = lookup_proc(name)
        if result:
            return CodingIssue(
                dimension="existence",
                severity="warning",
                code=code,
                description=f"手术编码 '{code}' 未在本地编码库中找到，根据手术名称 '{name}' 查询，建议编码为 '{result['code']}'",
                suggestion=f"建议将编码修正为 {result['code']}（{result['name']}）",
                source="rule",
            )

    return None


def _diag_code(diag: dict) -> str:
    return str(diag.get("code") or diag.get("icd_code") or diag.get("diagnosis_code") or "").strip().upper()


def _diag_name(diag: dict) -> str:
    return str(diag.get("name") or diag.get("diagnosis_name") or "").strip()


def _surgery_code(surgery: dict) -> str:
    return str(surgery.get("code") or surgery.get("operation_code") or surgery.get("procedure_code") or "").strip()


def _surgery_name(surgery: dict) -> str:
    return str(surgery.get("name") or surgery.get("operation_name") or surgery.get("procedure_name") or "").strip()


def _is_tumor_code(code: str) -> bool:
    if code.startswith("C"):
        return True
    return (
        code.startswith("D")
        and len(code) >= 3
        and code[1:3].isdigit()
        and int(code[1:3]) <= 48
    )


def _has_positive_pathology_fee(frontpage: dict) -> bool:
    """判断病理诊断费是否有有效金额。"""
    candidate_keys = (
        "pathology_fee",
        "pathology_diagnosis_fee",
        "pathology_diagnostic_fee",
        "pathology_diagnosis_cost",
        "pathological_diagnostic",
        "病理诊断费",
    )
    containers = [
        frontpage,
        frontpage.get("fees") if isinstance(frontpage.get("fees"), dict) else {},
        frontpage.get("costs") if isinstance(frontpage.get("costs"), dict) else {},
        frontpage.get("fee_info") if isinstance(frontpage.get("fee_info"), dict) else {},
        frontpage.get("settlement") if isinstance(frontpage.get("settlement"), dict) else {},
    ]
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in candidate_keys:
            value = container.get(key)
            if value in (None, ""):
                continue
            try:
                if float(str(value).replace(",", "")) > 0:
                    return True
            except (TypeError, ValueError):
                continue
    return False


# ============================================================
# D3-D6：LLM 语义审查
# ============================================================

CODING_QC_SYSTEM_PROMPT = """你是一位具有临床医学知识和 ICD 病案信息学知识的资深编码质控专家。
你精通《疾病分类与代码国家临床版2.0》(ICD-10) 和《手术操作分类代码国家临床版3.0》(ICD-9-CM-3) 编码规范。

你的任务是对病案首页的诊断编码和手术操作编码进行质控审查。请逐条检查以下维度：

## 1. 编码合并 (merge)
当以下情况出现时，应使用合并编码而非分别编码：
- 同一疾病及其并发症：如2型糖尿病伴肾病应编 E11.2，不应分编 E11.9 + N08.3
- 病因与器官损害：如高血压性心脏病应编 I11，不应分编 I10 + I51
- 感染病原体+部位：如肺炎链球菌性肺炎应编 J13，不应分编 B95.3 + J18
- 阑尾炎伴腹膜炎 → 应用合并码 K35.2/K35.8，不应分编 K35.9 + K65.0

## 2. 编码互斥 (exclusion)
以下编码不能同时出现：
- 同一疾病的不同阶段：急性 vs 慢性（如急性心梗 I21 与慢性缺血性心脏病 I25）
- 不同性质：良性 vs 恶性肿瘤不应同一部位共存
- 不同病因分类：1型糖尿病 E10 与 2型糖尿病 E11 互斥
- 上下级包含关系：具体诊断已包含上级分类时，不应重复编码上级

## 3. 主诊断选择 (primary)
依据《病案首页填写规范》主要诊断选择原则：
- 主诊断应为本次住院对健康危害最大、消耗医疗资源最多、住院时间最长的疾病
- 病因诊断能包括临床表现时，选病因诊断（如有明确肺炎，不应选R50发热做主诊断）
- 以手术治疗为目的的，选与手术一致的疾病做主诊断
- 症状码(R码)仅在出院时诊断仍不明确时才可做主诊断
- 仅针对并发症治疗时，该并发症可做主诊断
- 肿瘤规则：
  · 针对肿瘤手术/确诊 → 肿瘤为主诊断
  · 针对继发肿瘤手术 → 继发肿瘤为主诊断（即使原发仍在）
  · 仅做放疗/化疗 → Z51（放化疗）**可以且应当**做主诊断
  · 针对肿瘤并发症治疗 → 并发症为主诊断
- 中毒以治疗中毒为目的时，中毒为主诊断
- 疾病的临终状态不能做主诊断

## 3b. 主手术选择 (primary_surgery)
- 主手术应与主诊断相对应
- 多个手术时，选择技术难度最大、过程最复杂、风险最高的手术
- 治疗性手术优先于诊断性操作（如支架植入优先于造影术）
- 既有手术又有操作时，手术优先

## 4. 编码一致性 (consistency)
- 编码与患者性别是否一致（如妇科诊断/手术不应出现在男性患者）
- 编码与患者年龄是否一致（如围产期编码P码不应出现在成人）
- 主手术与主诊断在解剖部位/系统上应对应

## 5. 另编码/附加编码 (additional)
以下手术操作必须附加相应编码：
- 冠状动脉支架植入术(36.06/36.07) → 必须附加 00.66(支架数目) 和 00.40(血管内操作数目)
- 全髋关节置换术(81.51) → 必须附加 00.70(假体类型) 和 00.73(假体轴承面类型)
- 全膝关节置换术(81.54) → 必须附加 00.80(膝关节假体类型)
- 椎体融合术(81.0x) → 必须附加 81.62-81.64(融合节段数) 和 84.51(脊柱内固定装置植入)
- 经皮血管成形术 → 必须附加 00.40(血管内操作数目)

以下诊断必须附加相应编码：
- 损伤/中毒(S00-T98) → 必须附加外部原因编码(V01-Y98)
- 肿瘤**作为主诊断**(C00-C97) → 必须附加病理形态学编码(M码，如 M8140/3)
  M码仅主诊断为肿瘤时必需；次诊断、既往史中提及的肿瘤不需要M码

请严格按以下 JSON 格式输出，不要输出任何其他内容：
{
  "issues": [
    {
      "dimension": "merge|exclusion|primary|consistency|additional",
      "severity": "error|warning|info",
      "code": "涉及的编码",
      "description": "问题描述（含编码规则依据）",
      "suggestion": "具体的修改建议（含推荐编码）"
    }
  ],
  "summary": {
    "total_issues": 0,
    "overall_assessment": "通过|需修改|严重问题"
  }
}

重要原则：
- 只审查已编码的内容，不要基于临床推测或常识假设来报告未编码的问题
- 只报告确实存在的问题，不要过度报告
- 非肿瘤疾病不需要M码；肿瘤仅在**主诊断**时才需要M码，次诊断/既往史不需要
- severity 分级：error=编码规则明确禁止, warning=建议修改, info=可优化"""


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


def _is_timeout_exception(exc: BaseException) -> bool:
    """判断异常是否属于超时类型（兼容标准库与 httpx 等第三方异常）。"""
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return True
    return "timeout" in type(exc).__name__.lower()


def _parse_llm_issues_with_status(raw_output: str) -> Tuple[List[CodingIssue], bool]:
    """从 LLM 原始输出中解析质控问题，返回 (issues, parsed_ok)。"""
    parsed = _parse_json_from_text(raw_output)
    if not isinstance(parsed, dict):
        logger.warning("无法解析 LLM 输出为有效 JSON 对象")
        return [], False

    raw_issues = parsed.get("issues")
    if not isinstance(raw_issues, list):
        logger.warning("LLM 输出缺少有效的 issues 列表字段")
        return [], False

    issues: List[CodingIssue] = []
    for item in raw_issues:
        if not isinstance(item, dict):
            logger.warning("LLM 输出的 issues 列表包含非对象项")
            return [], False
        issues.append(CodingIssue(
            dimension=item.get("dimension", "unknown"),
            severity=item.get("severity", "info"),
            code=item.get("code", ""),
            description=item.get("description", ""),
            suggestion=item.get("suggestion", ""),
            source="llm",
        ))
    return issues, True


def _parse_llm_issues(raw_output: str) -> List[CodingIssue]:
    """从 LLM 原始输出中解析质控问题。"""
    issues, _ = _parse_llm_issues_with_status(raw_output)
    return issues


def _parse_json_from_text(text: str) -> Optional[dict]:
    """从文本中提取 JSON（兼容 markdown 代码块包裹）。"""
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # 尝试 ```json ... ```
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(1))
            if isinstance(parsed, dict):
                return parsed
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
                        parsed = json.loads(text[brace_start:i + 1])
                        if isinstance(parsed, dict):
                            return parsed
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
        - 场景 B：存在病理编码或肿瘤诊断 → 病理诊断费字段应保持一致
        - 场景 C：阑尾炎与腹膜炎同时出现 → 提示合并编码
        - 场景 D：冠状动脉支架置入术 → 提示补充附加编码
        """
        issues = []
        diagnoses = frontpage.get("diagnoses") or []
        surgeries = frontpage.get("surgeries") or []
        if not diagnoses and not surgeries:
            return issues

        diagnosis_codes = [_diag_code(d) for d in diagnoses]
        diagnosis_names = [_diag_name(d) for d in diagnoses]
        surgery_codes = [_surgery_code(s) for s in surgeries]
        surgery_names = [_surgery_name(s) for s in surgeries]

        # 场景 A：肿瘤主诊断 → 检查是否有病理形态学编码（M 码）
        primary_code = diagnosis_codes[0] if diagnosis_codes else ""
        primary_tumor_code = primary_code if _is_tumor_code(primary_code) else ""
        has_morphology = False
        for code in diagnosis_codes:
            if not code:
                continue
            # M 码（病理形态学编码）
            if code.startswith("M"):
                has_morphology = True

        if primary_tumor_code and not has_morphology:
            issues.append(CodingIssue(
                dimension="consistency",
                severity="warning",
                code=primary_tumor_code,
                description=f"出院主要诊断为肿瘤编码（{primary_tumor_code}），但未见病理形态学诊断编码（M 码），建议补充病理诊断",
                suggestion="肿瘤相关诊断应同时提供病理形态学编码（M 码），以确保编码完整性",
                source="rule",
                rule_id="CQ-TENDER-001",
                rule_name="肿瘤诊断病理形态学编码完整性",
                evidence="; ".join(code for code in diagnosis_codes if code),
            ))

        # 场景 B：病理编码或肿瘤诊断存在时，病理诊断费字段应一致。
        if (primary_tumor_code or has_morphology) and not _has_positive_pathology_fee(frontpage):
            issues.append(CodingIssue(
                dimension="consistency",
                severity="warning",
                code=primary_tumor_code or "M",
                description="存在肿瘤诊断或病理形态学编码，但未见病理诊断费字段有效金额，需核对病理诊断与费用一致性",
                suggestion="请核对首页/结算清单病理诊断费，确认是否漏填或费用归类错误",
                source="rule",
                rule_id="CQ-TENDER-002",
                rule_name="病理编码与病理诊断费一致性",
                evidence="; ".join(code for code in diagnosis_codes if code),
            ))

        # 场景 C：阑尾炎与腹膜炎同时出现时，提示是否应合并编码。
        has_appendicitis = any(
            code.startswith("K35") or "阑尾炎" in name
            for code, name in zip(diagnosis_codes, diagnosis_names)
        )
        has_peritonitis = any(
            code.startswith("K65") or "腹膜炎" in name
            for code, name in zip(diagnosis_codes, diagnosis_names)
        )
        has_appendicitis_combined_code = any(code.startswith(("K35.2", "K35.3")) for code in diagnosis_codes)
        if has_appendicitis and has_peritonitis and not has_appendicitis_combined_code:
            issues.append(CodingIssue(
                dimension="merge",
                severity="warning",
                code="K35/K65",
                description="阑尾炎与腹膜炎诊断同时出现，可能需要使用急性阑尾炎伴腹膜炎合并编码，而不是分开编码",
                suggestion="请优先核对 K35.2 或 K35.3 等急性阑尾炎伴腹膜炎编码是否更符合病案首页编码规范",
                source="rule",
                rule_id="CQ-TENDER-003",
                rule_name="阑尾炎伴腹膜炎合并编码提示",
                evidence="; ".join(
                    f"{code} {name}".strip()
                    for code, name in zip(diagnosis_codes, diagnosis_names)
                    if code or name
                ),
            ))

        # 场景 D：冠状动脉支架置入术需要共同使用附加编码。
        has_coronary_stent = any(
            code.startswith(("36.06", "36.07")) or "支架" in name or "PCI" in name.upper()
            for code, name in zip(surgery_codes, surgery_names)
        )
        has_stent_count_code = any(code.startswith("00.66") for code in surgery_codes)
        has_vessel_count_code = any(code.startswith("00.40") for code in surgery_codes)
        if has_coronary_stent and (not has_stent_count_code or not has_vessel_count_code):
            missing_codes = []
            if not has_stent_count_code:
                missing_codes.append("00.66 支架数目")
            if not has_vessel_count_code:
                missing_codes.append("00.40 血管内操作数目")
            issues.append(CodingIssue(
                dimension="additional",
                severity="warning",
                code="36.06/36.07",
                description="冠状动脉支架置入术应补充共同使用的附加编码",
                suggestion=f"请补充或核对附加编码：{'、'.join(missing_codes)}",
                source="rule",
                rule_id="CQ-TENDER-004",
                rule_name="冠状动脉支架置入术附加编码完整性",
                evidence="; ".join(
                    f"{code} {name}".strip()
                    for code, name in zip(surgery_codes, surgery_names)
                    if code or name
                ),
            ))

        return issues

    async def _run_semantic_check(self, frontpage: dict) -> Tuple[List[CodingIssue], str, bool, str]:
        """
        D3-D6：LLM 语义审查（返回明确完成状态）。

        Returns:
            (issues: List[CodingIssue], raw_output: str, llm_review_completed: bool, llm_review_status: str)
        """
        if not self.llm_client:
            logger.info("LLM 客户端未配置，跳过语义审查")
            return [], "", False, "unavailable"

        # 检查是否有足够的编码数据值得做语义审查
        diagnoses = frontpage.get("diagnoses") or []
        if not diagnoses:
            return [], "", False, "skipped"

        user_prompt = _build_llm_user_prompt(frontpage)
        full_prompt = f"{CODING_QC_SYSTEM_PROMPT}\n\n{user_prompt}"

        try:
            result = await self.llm_client.generate(full_prompt)
            if not isinstance(result, dict):
                logger.warning("LLM 语义审查返回非字典结果: %s", type(result).__name__)
                return [], str(result or ""), False, "parse_failed"
            choices = result.get("choices")
            first_choice = (
                choices[0]
                if isinstance(choices, list) and choices and isinstance(choices[0], dict)
                else {}
            )
            message = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
            content = message.get("content", "")
            if not isinstance(content, str):
                content = "" if content is None else str(content)
            issues, parsed_ok = _parse_llm_issues_with_status(content)
            if not parsed_ok:
                logger.warning("LLM 语义审查输出解析失败，标记语义审查未完成")
                return [], content, False, "parse_failed"
            return issues, content, True, "completed"
        except Exception as e:
            status = "timeout" if _is_timeout_exception(e) else "error"
            logger.error(f"LLM 语义审查失败({status}): {e}")
            return [], f"LLM 调用失败: {e}", False, status

    async def check_semantic(self, frontpage: dict) -> tuple:
        """
        D3-D6：LLM 语义审查。

        Returns:
            (issues: List[CodingIssue], raw_output: str)
        """
        issues, raw_output, _, _ = await self._run_semantic_check(frontpage)
        return issues, raw_output

    async def run_all(self, frontpage: dict, *, skip_llm: bool = False) -> CodingQCReport:
        """
        执行全量编码质控（规则层 + LLM 层）。

        Args:
            frontpage: 病案首页数据字典
            skip_llm: 是否显式跳过 LLM 语义审查

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
        if skip_llm:
            report.llm_issues = []
            report.llm_raw_output = ""
            report.llm_review_completed = False
            report.llm_review_status = "skipped"
        else:
            llm_issues, raw_output, llm_completed, llm_status = await self._run_semantic_check(frontpage)
            report.llm_issues = llm_issues
            report.llm_raw_output = raw_output
            report.llm_review_completed = llm_completed
            report.llm_review_status = llm_status

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
