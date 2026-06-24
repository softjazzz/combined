"""
编码质控 LLM 模型 Benchmark
============================
用 6 道标准化测试题对比不同模型在 ICD-10 编码质控任务上的表现。
每道题有预期答案（expected），用于自动评分。

测试维度：
  1. 主诊断选择（primary）
  2. 编码合并（merge）
  3. 编码互斥（exclusion）
  4. 编码一致性 - 性别（consistency-sex）
  5. 编码一致性 - 年龄（consistency-age）
  6. 正确编码 baseline（no-issue，不应报任何问题）
"""

import os, sys, time, json, httpx
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 平台配置
# ============================================================
DASHSCOPE_KEY = os.getenv("LLM_API_KEY")
DASHSCOPE_URL = os.getenv("LLM_API_ENDPOINT")
SILICONFLOW_KEY = os.getenv("SILICONFLOW_API_KEY")
SILICONFLOW_URL = os.getenv("SILICONFLOW_API_ENDPOINT")

# 模型列表：(显示名, API模型名, 平台)
MODELS = [
    ("qwen3.5-35b-a3b", "qwen3.5-35b-a3b",    "dashscope"),
    ("qwen3.5-27b",     "qwen3.5-27b",         "dashscope"),
    ("Qwen3.5-4B",      "Qwen/Qwen3.5-4B",     "siliconflow"),
    ("qwen3-14b",       "qwen3-14b",           "dashscope"),
    ("qwen3-8b",        "qwen3-8b",            "dashscope"),
    ("qwen3-4b",        "qwen3-4b",            "dashscope"),
]

# ============================================================
# System Prompt（与生产环境一致）
# ============================================================
SYSTEM_PROMPT = """你是医院病案编码质控专家，精通 ICD-10（国临版2.0）和 ICD-9-CM-3（2011临床修改版）编码规范。

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


# ============================================================
# 测试用例
# ============================================================
@dataclass
class TestCase:
    id: str
    title: str
    dimension: str           # 预期应报出问题的维度
    frontpage: dict          # 模拟首页数据
    expected_has_issue: bool # 是否应有问题
    expected_keywords: list  # 期望结果中包含的关键词
    description: str         # 题目说明

TEST_CASES = [
    # ---- 1. 主诊断选择 ----
    TestCase(
        id="T1",
        title="主诊断选择 - R码做主诊",
        dimension="primary",
        frontpage={
            "sex": "男", "age": "62",
            "diagnoses": [
                {"code": "R10.400", "name": "腹痛"},
                {"code": "K35.900", "name": "急性阑尾炎"},
            ],
            "surgeries": [
                {"code": "47.0901", "name": "阑尾切除术"},
            ],
        },
        expected_has_issue=True,
        expected_keywords=["主诊断", "R码", "阑尾炎", "症状"],
        description="腹痛(R码)做主诊，但实际做了阑尾切除术，应选急性阑尾炎做主诊",
    ),

    # ---- 2. 编码合并 ----
    TestCase(
        id="T2",
        title="编码合并 - 糖尿病+肾病并发症",
        dimension="merge",
        frontpage={
            "sex": "女", "age": "58",
            "diagnoses": [
                {"code": "E11.900", "name": "2型糖尿病"},
                {"code": "N08.300", "name": "糖尿病性肾病"},
                {"code": "I10.x02", "name": "高血压3级(极高危组)"},
            ],
            "surgeries": [],
        },
        expected_has_issue=True,
        expected_keywords=["合并", "E11", "糖尿病", "肾病"],
        description="2型糖尿病+糖尿病性肾病应合并编码为E11.621（2型糖尿病性肾病）",
    ),

    # ---- 3. 编码互斥 ----
    TestCase(
        id="T3",
        title="编码互斥 - 1型+2型糖尿病共存",
        dimension="exclusion",
        frontpage={
            "sex": "男", "age": "45",
            "diagnoses": [
                {"code": "E10.900", "name": "1型糖尿病"},
                {"code": "E11.900", "name": "2型糖尿病"},
                {"code": "I25.103", "name": "冠状动脉粥样硬化性心脏病"},
            ],
            "surgeries": [],
        },
        expected_has_issue=True,
        expected_keywords=["互斥", "1型", "2型", "不能同时"],
        description="1型和2型糖尿病不能同时存在于同一病例",
    ),

    # ---- 4. 一致性-性别 ----
    TestCase(
        id="T4",
        title="编码一致性 - 性别冲突",
        dimension="consistency",
        frontpage={
            "sex": "男", "age": "35",
            "diagnoses": [
                {"code": "N80.001", "name": "子宫内膜异位症"},
                {"code": "N73.001", "name": "慢性盆腔炎"},
            ],
            "surgeries": [],
        },
        expected_has_issue=True,
        expected_keywords=["性别", "男", "子宫", "女性"],
        description="男性患者不应有子宫内膜异位症和慢性盆腔炎等女性专属疾病",
    ),

    # ---- 5. 一致性-年龄 ----
    TestCase(
        id="T5",
        title="编码一致性 - 年龄冲突",
        dimension="consistency",
        frontpage={
            "sex": "男", "age": "3",
            "diagnoses": [
                {"code": "I25.103", "name": "冠状动脉粥样硬化性心脏病"},
                {"code": "I10.x02", "name": "高血压3级(极高危组)"},
            ],
            "surgeries": [],
        },
        expected_has_issue=True,
        expected_keywords=["年龄", "3岁", "冠心病", "儿童"],
        description="3岁儿童不应有冠心病和高血压3级，这是老年退行性疾病",
    ),

    # ---- 6. 正确编码（无问题 baseline） ----
    TestCase(
        id="T6",
        title="正确编码 - 不应报告问题",
        dimension="none",
        frontpage={
            "sex": "女", "age": "52",
            "diagnoses": [
                {"code": "K80.100", "name": "胆囊结石伴急性胆囊炎"},
            ],
            "surgeries": [
                {"code": "51.2200", "name": "腹腔镜下胆囊切除术"},
            ],
        },
        expected_has_issue=False,
        expected_keywords=["通过"],
        description="女性52岁胆囊结石伴急性胆囊炎，行腹腔镜胆囊切除术，编码完全正确",
    ),
]


# ============================================================
# 构建 prompt（与生产环境一致）
# ============================================================
def build_user_prompt(fp: dict) -> str:
    lines = ["请对以下病案首页编码进行质控审查：", ""]
    sex = fp.get("sex", "")
    age = fp.get("age", "")
    lines.append(f"【患者信息】{sex}，{age}岁" if age else f"【患者信息】{sex}")
    lines.append("")

    diagnoses = fp.get("diagnoses", [])
    if diagnoses:
        lines.append("【诊断编码】")
        for i, d in enumerate(diagnoses):
            prefix = "主诊断" if i == 0 else f"次诊断{i}"
            lines.append(f"  {prefix}：{d.get('code','')} {d.get('name','')}")
        lines.append("")

    surgeries = fp.get("surgeries", [])
    if surgeries:
        lines.append("【手术操作编码】")
        for i, s in enumerate(surgeries):
            prefix = "主手术" if i == 0 else f"其他手术{i}"
            lines.append(f"  {prefix}：{s.get('code','')} {s.get('name','')}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# 调用 LLM
# ============================================================
def call_llm(model_name: str, platform: str, user_prompt: str) -> dict:
    """调用 LLM 并返回 {ok, raw, parsed, elapsed}"""
    if platform == "dashscope":
        url = f"{DASHSCOPE_URL}/chat/completions"
        key = DASHSCOPE_KEY
    else:
        url = f"{SILICONFLOW_URL}/chat/completions"
        key = SILICONFLOW_KEY

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
        "enable_thinking": False,
    }

    t0 = time.time()
    try:
        r = httpx.post(url, headers=headers, json=body, timeout=120)
        elapsed = time.time() - t0
        if r.status_code != 200:
            err = r.json().get("error", {}).get("message", r.text[:100])
            return {"ok": False, "raw": err, "parsed": None, "elapsed": elapsed}

        raw = r.json()["choices"][0]["message"]["content"]

        # 尝试解析 JSON
        parsed = None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            import re
            m = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
            if not parsed:
                brace = raw.find("{")
                if brace >= 0:
                    depth = 0
                    for i in range(brace, len(raw)):
                        if raw[i] == "{": depth += 1
                        elif raw[i] == "}":
                            depth -= 1
                            if depth == 0:
                                try:
                                    parsed = json.loads(raw[brace:i+1])
                                except:
                                    pass
                                break

        return {"ok": True, "raw": raw, "parsed": parsed, "elapsed": elapsed}
    except Exception as e:
        return {"ok": False, "raw": str(e), "parsed": None, "elapsed": time.time() - t0}


# ============================================================
# 评分
# ============================================================
def score_result(tc: TestCase, result: dict) -> dict:
    """对模型输出评分，returns {detected, correct, keyword_hits, detail}"""
    if not result["ok"] or not result["parsed"]:
        return {"detected": None, "correct": False, "keyword_hits": 0, "detail": "解析失败"}

    parsed = result["parsed"]
    issues = parsed.get("issues", [])
    has_issues = len(issues) > 0
    assessment = parsed.get("summary", {}).get("overall_assessment", "")

    # 判断是否正确检测
    if tc.expected_has_issue:
        detected = has_issues
        # 关键词匹配
        all_text = json.dumps(parsed, ensure_ascii=False).lower()
        hits = sum(1 for kw in tc.expected_keywords if kw.lower() in all_text)
        correct = detected and hits >= 1
        detail = f"发现{len(issues)}个问题, 关键词命中{hits}/{len(tc.expected_keywords)}"
    else:
        detected = not has_issues
        correct = detected
        hits = 0
        if has_issues:
            descs = "; ".join([i.get("description", "")[:30] for i in issues[:2]])
            detail = f"误报{len(issues)}个问题: {descs}"
        else:
            detail = "正确通过，无误报"

    return {"detected": detected, "correct": correct, "keyword_hits": hits, "detail": detail}


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 80)
    print("编码质控 LLM 模型 Benchmark")
    print(f"测试用例: {len(TEST_CASES)} 题 × {len(MODELS)} 模型 = {len(TEST_CASES)*len(MODELS)} 次调用")
    print("=" * 80)

    # 打印题目概览
    print("\n📋 测试用例概览：")
    for tc in TEST_CASES:
        expect = "应报告问题" if tc.expected_has_issue else "不应报告问题"
        print(f"  [{tc.id}] {tc.title} → {expect}")
        print(f"       {tc.description}")
    print()

    # 执行测试
    results = {}  # {model_name: {test_id: score_dict}}

    for display_name, api_name, platform in MODELS:
        results[display_name] = {}
        print(f"\n🤖 测试模型: {display_name} ({platform})")
        print("-" * 60)

        for tc in TEST_CASES:
            user_prompt = build_user_prompt(tc.frontpage)
            sys.stdout.write(f"  [{tc.id}] {tc.title:30s} → ")
            sys.stdout.flush()

            llm_result = call_llm(api_name, platform, user_prompt)
            score = score_result(tc, llm_result)
            score["elapsed"] = llm_result["elapsed"]
            results[display_name][tc.id] = score

            mark = "✅" if score["correct"] else "❌"
            print(f"{mark} {score['detail']}  ({llm_result['elapsed']:.1f}s)")

    # ============================================================
    # 汇总表
    # ============================================================
    print("\n" + "=" * 80)
    print("📊 汇总对比表")
    print("=" * 80)

    # Header
    header = f"{'模型':<22}"
    for tc in TEST_CASES:
        header += f" {tc.id:^6}"
    header += f" {'得分':>6}  {'平均耗时':>8}"
    print(header)
    print("-" * len(header))

    # Rows
    ranking = []
    for display_name, _, _ in MODELS:
        row = f"{display_name:<22}"
        total = 0
        elapsed_sum = 0
        for tc in TEST_CASES:
            s = results[display_name][tc.id]
            mark = " ✅ " if s["correct"] else " ❌ "
            row += f" {mark:^6}"
            total += 1 if s["correct"] else 0
            elapsed_sum += s.get("elapsed", 0)
        avg_time = elapsed_sum / len(TEST_CASES)
        row += f" {total}/{len(TEST_CASES):>4}  {avg_time:>7.1f}s"
        ranking.append((display_name, total, avg_time))
        print(row)

    # 排名
    ranking.sort(key=lambda x: (-x[1], x[2]))
    print(f"\n🏆 排名（正确率 > 速度）：")
    for i, (name, score, avg) in enumerate(ranking):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f" {i+1}."
        print(f"  {medal} {name:<22} {score}/{len(TEST_CASES)} 正确  平均 {avg:.1f}s")

    # 写入详细结果到文件
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": [m[0] for m in MODELS],
        "test_cases": [{"id": tc.id, "title": tc.title, "dimension": tc.dimension} for tc in TEST_CASES],
        "results": results,
    }
    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n📁 详细结果已保存到 benchmark_results.json")


if __name__ == "__main__":
    main()
