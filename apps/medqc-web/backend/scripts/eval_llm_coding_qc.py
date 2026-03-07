"""
LLM 编码质控能力评测脚本

用法：
  # 测试单个模型
  python scripts/eval_llm_coding_qc.py --model qwen3.5-27b

  # 测试所有模型
  python scripts/eval_llm_coding_qc.py --all

  # 只测试指定维度
  python scripts/eval_llm_coding_qc.py --model qwen3.5-27b --dims D1,D3

  # 指定平台
  python scripts/eval_llm_coding_qc.py --model Qwen/Qwen3.5-4B --provider siliconflow
"""
import asyncio
import json
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

# ==================== 模型 & 平台配置 ====================

PROVIDERS = {
    "dashscope": {
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "api_key": "sk-e2808814ae874c8f94e40f20c99bc3a3",
        "models": [
            "qwen2.5-14b-instruct",
            "qwen3-30b-a3b-instruct-2507",
            "qwen3.5-122b-a10b",
            "qwen3.5-27b",
            "qwen3.5-35b-a3b",
        ],
    },
    "siliconflow": {
        "endpoint": "https://api.siliconflow.cn/v1/chat/completions",
        "api_key": "sk-meraqcfdnjxvhixuacxreonlficdhovmuqqkvifchizakdnk",
        "models": [
            "Qwen/Qwen3.5-4B",
            "Qwen/Qwen3.5-9B",
        ],
    },
}

ALL_MODELS = [
    ("dashscope",  "qwen2.5-14b-instruct"),
    ("dashscope",  "qwen3-30b-a3b-instruct-2507"),
    ("dashscope",  "qwen3.5-122b-a10b"),
    ("dashscope",  "qwen3.5-27b"),
    ("dashscope",  "qwen3.5-35b-a3b"),
    ("siliconflow", "Qwen/Qwen3.5-4B"),
    ("siliconflow", "Qwen/Qwen3.5-9B"),
]


def find_provider(model: str) -> str:
    """根据模型名自动识别平台。"""
    for prov, cfg in PROVIDERS.items():
        if model in cfg["models"]:
            return prov
    # 默认 dashscope
    return "dashscope"


# ==================== LLM 调用 ====================

async def call_llm(provider: str, model: str, system_prompt: str,
                   user_prompt: str, timeout: int = 120) -> Dict[str, Any]:
    """调用 LLM API，返回解析后的内容。"""
    cfg = PROVIDERS[provider]
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 4000,
        "stream": False,
    }
    # Qwen 系列 非流式需要 enable_thinking=False
    if "qwen" in model.lower():
        payload["enable_thinking"] = False

    t0 = time.time()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(cfg["endpoint"], json=payload, headers=headers)
        resp.raise_for_status()

    elapsed = time.time() - t0
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {}).get("total_tokens", 0)
    return {
        "content": content,
        "tokens": tokens,
        "latency": round(elapsed, 2),
    }


def parse_json_from_llm(text: str) -> Optional[dict]:
    """从 LLM 输出中提取 JSON。"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试提取 ```json ... ```
    import re
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试提取 { ... } (第一个完整JSON)
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


# ==================== 系统提示词 ====================

SYSTEM_PROMPT = """你是医院病案编码质控专家，精通 ICD-10（国临版2.0）和 ICD-9-CM-3（2011临床修改版）编码规范。

你的任务是对病案首页的诊断编码和手术操作编码进行质控审查。

请严格按以下 JSON 格式输出审查结果，不要输出任何其他内容：
{
  "issues": [
    {
      "dimension": "format|existence|merge|exclusion|primary|consistency",
      "severity": "error|warning|info",
      "code": "涉及的编码",
      "description": "问题描述",
      "suggestion": "修改建议"
    }
  ],
  "summary": {
    "total_issues": 0,
    "errors": 0,
    "warnings": 0,
    "overall_assessment": "通过|需修改|严重问题"
  }
}

如果没有发现任何问题，issues 数组应为空，overall_assessment 为"通过"。
只报告确实存在的问题，不要过度报告。"""


# ==================== 测试用例定义 ====================

@dataclass
class TestCase:
    id: str
    dimension: str  # D1-D6
    description: str
    user_prompt: str
    expected_has_issues: bool  # 是否期望检出问题
    expected_dimension: str    # format/existence/merge/exclusion/primary/consistency
    expected_keywords: List[str] = field(default_factory=list)  # 期望出现的关键词


TEST_CASES: List[TestCase] = [
    # ==================== D1：编码格式校验 ====================
    TestCase(
        id="D1-01", dimension="D1", description="ICD-10 标准格式（正例）",
        user_prompt="请检查以下编码的格式是否正确：\n主诊断：I21.001 急性前壁ST段抬高型心肌梗死\n次诊断：E11.900 2型糖尿病",
        expected_has_issues=False, expected_dimension="format",
    ),
    TestCase(
        id="D1-02", dimension="D1", description="ICD-10 缺少亚目",
        user_prompt="请检查以下编码的格式是否正确：\n主诊断：I21 急性心肌梗死",
        expected_has_issues=True, expected_dimension="format",
        expected_keywords=["不完整", "亚目", "位数"],
    ),
    TestCase(
        id="D1-03", dimension="D1", description="ICD-10 缺少字母前缀",
        user_prompt="请检查以下编码的格式是否正确：\n主诊断：21.001 急性心肌梗死",
        expected_has_issues=True, expected_dimension="format",
        expected_keywords=["字母", "格式"],
    ),
    TestCase(
        id="D1-04", dimension="D1", description="ICD-9-CM-3 标准格式（正例）",
        user_prompt="请检查以下手术编码的格式是否正确：\n手术操作：36.0701 经皮冠状动脉支架植入术",
        expected_has_issues=False, expected_dimension="format",
    ),
    TestCase(
        id="D1-05", dimension="D1", description="ICD-9-CM-3 缺少分隔点",
        user_prompt="请检查以下手术编码的格式是否正确：\n手术操作：360701 经皮冠状动脉支架植入术",
        expected_has_issues=True, expected_dimension="format",
        expected_keywords=["分隔", "格式", "点"],
    ),

    # ==================== D2：编码真实性验证 ====================
    TestCase(
        id="D2-01", dimension="D2", description="真实编码+名称匹配（正例）",
        user_prompt="请验证以下编码是否真实存在，编码与名称是否匹配：\n诊断：I21.001 急性前壁ST段抬高型心肌梗死",
        expected_has_issues=False, expected_dimension="existence",
    ),
    TestCase(
        id="D2-02", dimension="D2", description="虚构亚目",
        user_prompt="请验证以下编码是否真实存在：\n诊断：I21.999 心肌梗死NOS",
        expected_has_issues=True, expected_dimension="existence",
        expected_keywords=["不存在", "虚构", "无效"],
    ),
    TestCase(
        id="D2-03", dimension="D2", description="虚构编码",
        user_prompt="请验证以下编码是否真实存在：\n诊断：Z99.999 未指定状态",
        expected_has_issues=True, expected_dimension="existence",
        expected_keywords=["不存在", "无效"],
    ),
    TestCase(
        id="D2-04", dimension="D2", description="编码与名称不匹配",
        user_prompt='请验证以下编码与名称是否匹配：\n诊断：I10 2型糖尿病\n（注意：I10 的标准名称应为"原发性高血压"）',
        expected_has_issues=True, expected_dimension="existence",
        expected_keywords=["不匹配", "高血压", "糖尿病"],
    ),
    TestCase(
        id="D2-05", dimension="D2", description="真实编码（正例）",
        user_prompt="请验证以下编码是否真实存在，编码与名称是否匹配：\n诊断：J18.900 肺炎",
        expected_has_issues=False, expected_dimension="existence",
    ),

    # ==================== D3：编码合并规则 ====================
    TestCase(
        id="D3-01", dimension="D3", description="糖尿病+并发症应合并编码",
        user_prompt="请检查以下编码是否存在应合并编码的情况：\n诊断1：E11.900 2型糖尿病\n诊断2：N08.300 糖尿病性肾病\n（注意：ICD-10 中 E11.200 表示\"2型糖尿病伴有肾脏并发症\"）",
        expected_has_issues=True, expected_dimension="merge",
        expected_keywords=["合并", "E11.2"],
    ),
    TestCase(
        id="D3-02", dimension="D3", description="高血压+高血压心脏病应合并",
        user_prompt="请检查以下编码是否存在应合并编码的情况：\n诊断1：I10 原发性高血压\n诊断2：I11.900 高血压性心脏病",
        expected_has_issues=True, expected_dimension="merge",
        expected_keywords=["合并", "I11", "高血压"],
    ),
    TestCase(
        id="D3-03", dimension="D3", description="胆囊结石+胆囊炎已有合并码",
        user_prompt="请检查以下编码是否存在应合并编码的情况：\n诊断1：K80.000 胆囊结石\n诊断2：K81.000 急性胆囊炎\n（注意：K80.100 表示\"胆囊结石伴有急性胆囊炎\"）",
        expected_has_issues=True, expected_dimension="merge",
        expected_keywords=["合并", "K80.1"],
    ),
    TestCase(
        id="D3-04", dimension="D3", description="阑尾炎编码已含穿孔",
        user_prompt="请检查以下编码是否存在编码重复：\n诊断1：K35.900 急性阑尾炎\n诊断2：K35.001 急性阑尾炎伴穿孔",
        expected_has_issues=True, expected_dimension="merge",
        expected_keywords=["重复", "K35"],
    ),
    TestCase(
        id="D3-05", dimension="D3", description="脑梗死+偏瘫正确分编（正例）",
        user_prompt="请检查以下编码是否存在应合并编码的情况：\n诊断1：I63.900 脑梗死\n诊断2：G81.900 偏瘫",
        expected_has_issues=False, expected_dimension="merge",
    ),

    # ==================== D4：编码互斥规则 ====================
    TestCase(
        id="D4-01", dimension="D4", description="自然分娩+剖宫产互斥",
        user_prompt="请检查以下编码组合是否存在互斥情况：\n诊断1：O80.000 自然分娩（顺产）\n诊断2：O82.000 经剖宫产术分娩",
        expected_has_issues=True, expected_dimension="exclusion",
        expected_keywords=["互斥", "不能同时"],
    ),
    TestCase(
        id="D4-02", dimension="D4", description="急性心梗+陈旧性心梗需确认",
        user_prompt="请检查以下编码组合是否有问题：\n诊断1：I21.001 急性前壁ST段抬高型心肌梗死\n诊断2：I25.100 陈旧性心肌梗死\n同次住院",
        expected_has_issues=True, expected_dimension="exclusion",
        expected_keywords=["急性", "陈旧", "确认", "时间"],
    ),
    TestCase(
        id="D4-03", dimension="D4", description="慢性肾衰分期互斥",
        user_prompt="请检查以下编码组合是否存在互斥情况：\n诊断1：N18.500 慢性肾脏病5期\n诊断2：N18.300 慢性肾脏病3期\n同一患者同次住院",
        expected_has_issues=True, expected_dimension="exclusion",
        expected_keywords=["互斥", "分期", "不能"],
    ),
    TestCase(
        id="D4-04", dimension="D4", description="1型+2型糖尿病互斥",
        user_prompt="请检查以下编码组合是否存在互斥情况：\n诊断1：E11.900 2型糖尿病\n诊断2：E10.900 1型糖尿病\n同一患者",
        expected_has_issues=True, expected_dimension="exclusion",
        expected_keywords=["互斥", "1型", "2型"],
    ),
    TestCase(
        id="D4-05", dimension="D4", description="COPD+肺炎可并存（正例）",
        user_prompt="请检查以下编码组合是否存在互斥情况：\n诊断1：J44.100 慢性阻塞性肺疾病急性加重\n诊断2：J18.900 肺炎",
        expected_has_issues=False, expected_dimension="exclusion",
    ),

    # ==================== D5：主诊断选择合理性 ====================
    TestCase(
        id="D5-01", dimension="D5", description="Z码做主诊断需审议",
        user_prompt="请评估主诊断选择是否合理：\n主诊断：Z51.100 化疗疗程\n次诊断：C34.901 肺恶性肿瘤\n手术操作：无",
        expected_has_issues=True, expected_dimension="primary",
        expected_keywords=["Z码", "主诊断", "化疗"],
    ),
    TestCase(
        id="D5-02", dimension="D5", description="症状码不应做主诊断",
        user_prompt="请评估主诊断选择是否合理：\n主诊断：R10.400 腹痛\n次诊断：K35.900 急性阑尾炎\n手术操作：47.0901 阑尾切除术",
        expected_has_issues=True, expected_dimension="primary",
        expected_keywords=["症状", "R码", "主诊断", "阑尾"],
    ),
    TestCase(
        id="D5-03", dimension="D5", description="消耗资源最大的诊断应做主诊断",
        user_prompt="请评估主诊断选择是否合理：\n主诊断：I10 原发性高血压\n次诊断：I21.001 急性前壁ST段抬高型心肌梗死\n手术操作：36.0701 经皮冠状动脉支架植入术(PCI)",
        expected_has_issues=True, expected_dimension="primary",
        expected_keywords=["主诊断", "心梗", "PCI"],
    ),
    TestCase(
        id="D5-04", dimension="D5", description="主诊断合理（正例）",
        user_prompt="请评估主诊断选择是否合理：\n主诊断：I21.001 急性前壁ST段抬高型心肌梗死\n次诊断：E11.900 2型糖尿病\n次诊断：I10 原发性高血压\n手术操作：36.0701 经皮冠状动脉支架植入术(PCI)",
        expected_has_issues=False, expected_dimension="primary",
    ),
    TestCase(
        id="D5-05", dimension="D5", description="观察码做主诊断不当",
        user_prompt="请评估主诊断选择是否合理：\n主诊断：Z03.800 医学观察\n出院时无其他确诊诊断",
        expected_has_issues=True, expected_dimension="primary",
        expected_keywords=["观察", "主诊断", "Z码"],
    ),

    # ==================== D6：编码与临床信息一致性 ====================
    TestCase(
        id="D6-01", dimension="D6", description="术后并发症遗漏编码",
        user_prompt="请根据病历摘要检查编码完整性：\n【病历摘要】患者因急性心肌梗死入院，行PCI手术，术后第3天出现心力衰竭，给予利尿、强心治疗后好转。\n【当前编码】\n主诊断：I21.001 急性前壁ST段抬高型心肌梗死\n手术操作：36.0701 PCI\n无其他诊断编码",
        expected_has_issues=True, expected_dimension="consistency",
        expected_keywords=["心力衰竭", "遗漏", "I50"],
    ),
    TestCase(
        id="D6-02", dimension="D6", description="性别与诊断编码冲突",
        user_prompt="请检查编码与患者信息的一致性：\n【患者信息】女性，55岁\n【诊断编码】N40 前列腺增生",
        expected_has_issues=True, expected_dimension="consistency",
        expected_keywords=["性别", "女性", "前列腺"],
    ),
    TestCase(
        id="D6-03", dimension="D6", description="年龄与新生儿编码冲突",
        user_prompt="请检查编码与患者信息的一致性：\n【患者信息】65岁，男性\n【诊断编码】P59.900 新生儿黄疸",
        expected_has_issues=True, expected_dimension="consistency",
        expected_keywords=["年龄", "新生儿", "65岁"],
    ),
    TestCase(
        id="D6-04", dimension="D6", description="手术操作编码缺失",
        user_prompt="请根据病历摘要检查编码完整性：\n【病历摘要】患者因右膝骨性关节炎入院，行全膝关节置换术。\n【当前编码】\n主诊断：M17.100 原发性膝关节炎\n手术操作编码：无",
        expected_has_issues=True, expected_dimension="consistency",
        expected_keywords=["手术", "缺失", "置换"],
    ),
    TestCase(
        id="D6-05", dimension="D6", description="糖尿病并发症遗漏编码",
        user_prompt="请根据病历摘要检查编码完整性：\n【病历摘要】患者2型糖尿病病史10年，本次因糖尿病肾病入院治疗。\n【当前编码】\n主诊断：E11.900 2型糖尿病\n无其他诊断编码",
        expected_has_issues=True, expected_dimension="consistency",
        expected_keywords=["糖尿病肾病", "遗漏", "E11.2"],
    ),
]


# ==================== 评测引擎 ====================

@dataclass
class CaseResult:
    case_id: str
    dimension: str
    description: str
    expected_has_issues: bool
    actual_has_issues: Optional[bool] = None
    is_correct: Optional[bool] = None
    json_valid: bool = False
    issues_found: int = 0
    relevant_keywords_hit: int = 0
    total_expected_keywords: int = 0
    latency: float = 0.0
    tokens: int = 0
    raw_output: str = ""
    error: str = ""


async def evaluate_case(provider: str, model: str, case: TestCase) -> CaseResult:
    """评测单个用例。"""
    result = CaseResult(
        case_id=case.id,
        dimension=case.dimension,
        description=case.description,
        expected_has_issues=case.expected_has_issues,
        total_expected_keywords=len(case.expected_keywords),
    )

    try:
        llm_resp = await call_llm(provider, model, SYSTEM_PROMPT, case.user_prompt)
        result.raw_output = llm_resp["content"]
        result.latency = llm_resp["latency"]
        result.tokens = llm_resp["tokens"]

        parsed = parse_json_from_llm(llm_resp["content"])
        if parsed is None:
            result.json_valid = False
            result.error = "无法解析 JSON"
            return result

        result.json_valid = True
        issues = parsed.get("issues", [])
        result.issues_found = len(issues)
        result.actual_has_issues = len(issues) > 0

        # 判定是否正确
        result.is_correct = (result.actual_has_issues == case.expected_has_issues)

        # 关键词命中检查（仅在有 issues 且期望有 issues 时）
        if case.expected_keywords and result.actual_has_issues:
            full_text = json.dumps(parsed, ensure_ascii=False).lower()
            for kw in case.expected_keywords:
                if kw.lower() in full_text:
                    result.relevant_keywords_hit += 1

    except Exception as e:
        result.error = str(e)
        logger.error(f"  ❌ {case.id} 异常: {e}")

    return result


async def run_model_evaluation(provider: str, model: str,
                               dimensions: Optional[List[str]] = None) -> List[CaseResult]:
    """对单个模型运行所有测试用例。"""
    cases = TEST_CASES
    if dimensions:
        cases = [c for c in cases if c.dimension in dimensions]

    logger.info(f"\n{'='*60}")
    logger.info(f"📊 开始评测: {model} ({provider})")
    logger.info(f"   测试用例: {len(cases)} 个")
    logger.info(f"{'='*60}")

    results = []
    for i, case in enumerate(cases, 1):
        logger.info(f"  [{i}/{len(cases)}] {case.id}: {case.description}")
        r = await evaluate_case(provider, model, case)
        status = "✅" if r.is_correct else ("❌" if r.is_correct is False else "⚠️")
        logger.info(f"    {status} 期望={'有问题' if case.expected_has_issues else '无问题'}, "
                     f"实际={'有问题' if r.actual_has_issues else '无问题' if r.actual_has_issues is not None else '解析失败'}, "
                     f"耗时={r.latency}s, Tokens={r.tokens}")
        results.append(r)
        # 避免 API 限流
        await asyncio.sleep(1)

    return results


# ==================== 报告生成 ====================

def generate_report(model: str, provider: str, results: List[CaseResult]) -> str:
    """生成评测报告。"""
    lines = []
    lines.append(f"\n{'#'*60}")
    lines.append(f"# 评测报告: {model}")
    lines.append(f"# 平台: {provider}")
    lines.append(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"{'#'*60}\n")

    # 总体统计
    total = len(results)
    correct = sum(1 for r in results if r.is_correct)
    json_valid = sum(1 for r in results if r.json_valid)
    errors = sum(1 for r in results if r.error)

    # 正例/反例分别计算
    pos_cases = [r for r in results if r.expected_has_issues]
    neg_cases = [r for r in results if not r.expected_has_issues]
    pos_correct = sum(1 for r in pos_cases if r.is_correct)
    neg_correct = sum(1 for r in neg_cases if r.is_correct)

    # 误报/漏报
    false_positive = sum(1 for r in neg_cases if r.actual_has_issues)
    false_negative = sum(1 for r in pos_cases if r.actual_has_issues is False)

    lines.append("## 总体指标")
    lines.append(f"  准确率:     {correct}/{total} = {correct/total*100:.1f}%")
    lines.append(f"  JSON合规:   {json_valid}/{total} = {json_valid/total*100:.1f}%")
    lines.append(f"  召回率:     {pos_correct}/{len(pos_cases)} = {pos_correct/len(pos_cases)*100:.1f}%" if pos_cases else "  召回率:     N/A")
    lines.append(f"  误报率:     {false_positive}/{len(neg_cases)} = {false_positive/len(neg_cases)*100:.1f}%" if neg_cases else "  误报率:     N/A")
    lines.append(f"  漏报数:     {false_negative}")
    lines.append(f"  平均耗时:   {sum(r.latency for r in results)/total:.2f}s")
    lines.append(f"  平均Tokens: {sum(r.tokens for r in results)//total}")
    lines.append(f"  异常数:     {errors}")

    # 按维度统计
    lines.append("\n## 分维度统计")
    lines.append(f"{'维度':<6} {'正确':>4} {'总数':>4} {'准确率':>8} {'决策':>12}")
    lines.append("-" * 40)
    for dim in ["D1", "D2", "D3", "D4", "D5", "D6"]:
        dim_results = [r for r in results if r.dimension == dim]
        if not dim_results:
            continue
        dim_correct = sum(1 for r in dim_results if r.is_correct)
        dim_total = len(dim_results)
        acc = dim_correct / dim_total * 100
        decision = "✅ LLM" if acc >= 80 else "⚠️ 混合" if acc >= 60 else "❌ 规则"
        dim_names = {
            "D1": "格式校验", "D2": "真实性", "D3": "合并规则",
            "D4": "互斥规则", "D5": "主诊断", "D6": "一致性"
        }
        lines.append(f"{dim} {dim_names.get(dim, ''):<6} {dim_correct:>4} {dim_total:>4} {acc:>7.1f}%  {decision}")

    # 逐条详情
    lines.append("\n## 逐条详情")
    for r in results:
        status = "✅" if r.is_correct else ("❌" if r.is_correct is False else "⚠️")
        lines.append(f"\n  {r.case_id} {status} {r.description}")
        lines.append(f"    期望: {'有问题' if r.expected_has_issues else '无问题'}, "
                     f"实际: {'有问题' if r.actual_has_issues else '无问题' if r.actual_has_issues is not None else '解析失败'}")
        lines.append(f"    检出问题数: {r.issues_found}, 关键词命中: {r.relevant_keywords_hit}/{r.total_expected_keywords}")
        lines.append(f"    耗时: {r.latency}s, Tokens: {r.tokens}")
        if r.error:
            lines.append(f"    ⚠️ 异常: {r.error}")

    return "\n".join(lines)


def generate_comparison_table(all_model_results: Dict[str, List[CaseResult]]) -> str:
    """生成多模型对比表。"""
    lines = []
    lines.append(f"\n{'='*80}")
    lines.append("📊 多模型对比总表")
    lines.append(f"{'='*80}\n")

    dim_names = {
        "D1": "格式校验", "D2": "真实性", "D3": "合并规则",
        "D4": "互斥规则", "D5": "主诊断", "D6": "一致性"
    }

    # 表头
    models = list(all_model_results.keys())
    short_names = [m.split("/")[-1][:15] for m in models]
    header = f"{'维度':<12} | " + " | ".join(f"{n:>15}" for n in short_names)
    lines.append(header)
    lines.append("-" * len(header))

    for dim in ["D1", "D2", "D3", "D4", "D5", "D6"]:
        row = f"{dim} {dim_names[dim]:<8} | "
        for model in models:
            results = all_model_results[model]
            dim_results = [r for r in results if r.dimension == dim]
            if dim_results:
                correct = sum(1 for r in dim_results if r.is_correct)
                acc = correct / len(dim_results) * 100
                emoji = "✅" if acc >= 80 else "⚠️" if acc >= 60 else "❌"
                row += f"{emoji} {acc:>5.0f}%{'':>8} | "
            else:
                row += f"{'N/A':>15} | "
        lines.append(row)

    # 总正确率
    lines.append("-" * len(header))
    row = f"{'总正确率':<12} | "
    for model in models:
        results = all_model_results[model]
        correct = sum(1 for r in results if r.is_correct)
        acc = correct / len(results) * 100
        emoji = "✅" if acc >= 80 else "⚠️" if acc >= 60 else "❌"
        row += f"{emoji} {acc:>5.0f}%{'':>8} | "
    lines.append(row)

    # 平均耗时
    row = f"{'平均耗时(s)':<12} | "
    for model in models:
        results = all_model_results[model]
        avg = sum(r.latency for r in results) / len(results)
        row += f"{avg:>13.1f}s | "
    lines.append(row)

    return "\n".join(lines)


# ==================== 主流程 ====================

async def main():
    parser = argparse.ArgumentParser(description="LLM 编码质控能力评测")
    parser.add_argument("--model", type=str, help="指定测试模型")
    parser.add_argument("--provider", type=str, help="指定平台 (dashscope/siliconflow)")
    parser.add_argument("--all", action="store_true", help="测试所有模型")
    parser.add_argument("--dims", type=str, help="指定维度，逗号分隔，如 D1,D3")
    parser.add_argument("--output", type=str, default="reports", help="报告输出目录")
    args = parser.parse_args()

    dims = args.dims.split(",") if args.dims else None

    # 确定要测试的模型
    if args.all:
        models_to_test = ALL_MODELS
    elif args.model:
        prov = args.provider or find_provider(args.model)
        models_to_test = [(prov, args.model)]
    else:
        # 默认只测最小的模型做快速验证
        models_to_test = [("siliconflow", "Qwen/Qwen3.5-4B")]

    # 输出目录
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_model_results = {}
    for prov, model in models_to_test:
        results = await run_model_evaluation(prov, model, dims)
        all_model_results[model] = results

        # 生成单模型报告
        report = generate_report(model, prov, results)
        print(report)

        # 保存报告
        safe_name = model.replace("/", "_").replace(".", "_")
        report_file = out_dir / f"eval_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_file.write_text(report, encoding="utf-8")
        logger.info(f"📄 报告已保存: {report_file}")

        # 保存原始 JSON 数据
        json_file = out_dir / f"eval_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_data = [asdict(r) for r in results]
        json_file.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 多模型对比
    if len(all_model_results) > 1:
        comparison = generate_comparison_table(all_model_results)
        print(comparison)
        comp_file = out_dir / f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        comp_file.write_text(comparison, encoding="utf-8")
        logger.info(f"📊 对比表已保存: {comp_file}")


if __name__ == "__main__":
    asyncio.run(main())
