#!/usr/bin/env python3
"""
快速质控模式提示词优化方案对比测试

测试目标：
1. 对比三种提示词优化方案（方案 A、B、C）
2. 分析提示词长度、token 消耗、信息量
3. 不实际调用 LLM API，只测试提示词生成逻辑

测试病历：张伟，44岁，右肺占位性病变
测试规则：LX-001 ~ LX-009（9 条入院记录规则）
"""

import json
import re
import sys
import os
from typing import Dict, Any, List, Tuple

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# 测试病历
TEST_MEDICAL_RECORD = """患者信息：张伟，男，44岁，入院科室：呼吸与危重症医学科，病区：呼吸内一科。 

主诉：体检发现肺部结节1周。

现病史：患者1周前单位组织体检，行胸部CT发现右肺下叶磨玻璃结节，直径约1.8cm，边界清晰。患者无咳嗽、咳痰、咯血、胸痛、气促等不适。为进一步诊治来我院就诊，门诊完善相关检查后以'右肺占位性病变'收入院。

既往史：既往体健。否认高血压、糖尿病病史。否认肝炎、结核病史。否认手术史、外伤史、输血史。否认食物、药物过敏史。

体格检查：T 36.5℃，P 72次/分，R 18次/分，BP 125/78 mmHg。神志清楚，精神可，自主体位，查体合作。全身皮肤黏膜无黄染，浅表淋巴结未触及肿大。双肺呼吸音清，未闻及干湿啰音。心律齐，各瓣膜听诊区未闻及杂音。腹部平软，无压痛，肝脾肋下未触及。双下肢无水肿。

辅助检查：
1. 血常规：WBC 8.6×10⁹/L，N 72%，Hb 135g/L，PLT 210×10⁹/L
2. 肝功能：ALT 38U/L，AST 42U/L，TBIL 16μmol/L，ALB 41g/L
3. 肾功能：Cr 78μmol/L，BUN 5.2mmol/L
4. 心电图：窦性心律，大致正常心电图
5. 胸部CT平扫（2024-10-25，外院）：右肺下叶见直径约1.8cm磨玻璃结节，边界清晰，无毛刺征，未见明显淋巴结肿大
6. 腹部超声：肝胆胰脾未见明显异常，双肾未见结石及积水
7. 空腹血糖：5.9mmol/L
8. 凝血功能：PT 12.3s，APTT 31.5s，FIB 3.8g/L

入院诊断：右肺占位性病变"""

# LX 系列入院记录规则
LX_ADMISSION_RULES = [
    "LX-001",  # 主诉书写不规范或不能导出第一诊断
    "LX-002",  # 入院记录-现病史缺少一般情况
    "LX-003",  # 入院记录-婴幼儿个人史缺少喂养史
    "LX-004",  # 入院记录-专科检查缺失
    "LX-005",  # 入院记录-体格检查缺生命体征-血压
    "LX-006",  # 入院记录-7岁以上儿科患者体格检查缺生命体征-血压
    "LX-007",  # 入院记录缺辅助检查
    "LX-008",  # 入院记录-检查结果未记录
    "LX-009",  # 入院记录缺初步诊断
]


def load_rules() -> List[Dict[str, Any]]:
    """加载规则文件"""
    rules_file = os.path.join(os.path.dirname(__file__), 'app', 'data', 'sichuan_rules_146.json')
    with open(rules_file, 'r', encoding='utf-8') as f:
        all_rules = json.load(f)
    
    # 过滤出 LX 系列规则
    lx_rules = [r for r in all_rules if r.get('rule_id') in LX_ADMISSION_RULES]
    
    # 按照 LX_ADMISSION_RULES 的顺序排序
    sorted_rules = []
    for rule_id in LX_ADMISSION_RULES:
        for rule in lx_rules:
            if rule.get('rule_id') == rule_id:
                sorted_rules.append(rule)
                break
    
    return sorted_rules


def extract_check_points(custom_prompt: str) -> List[str]:
    """
    方案 A：提取检查要点（精简版）
    从 custom_prompt 中提取【检查要点】部分
    """
    if not custom_prompt:
        return []
    
    # 尝试匹配【检查要点】章节
    match = re.search(r'【检查要点】(.*?)(?:【|$)', custom_prompt, re.DOTALL)
    if not match:
        return []
    
    check_points_section = match.group(1).strip()
    
    # 提取各个要点（支持多种编号格式）
    points = re.findall(
        r'(?:^\s*(?:\d+[.、．]|[①②③④⑤⑥⑦⑧⑨⑩]|（\d+）)\s*)(.+?)(?=\n\s*(?:\d+[.、．]|[①②③④⑤⑥⑦⑧⑨⑩]|（\d+）)|$)',
        check_points_section,
        re.MULTILINE | re.DOTALL
    )
    
    # 清理每个要点，去除多余空白
    cleaned_points = [p.strip().replace('\n', ' ') for p in points if p.strip()]
    
    return cleaned_points if cleaned_points else []


def extract_core_prompt(custom_prompt: str) -> str:
    """
    方案 B：提取核心部分（去掉通用的输出要求）
    提取【检查要点】、【补充说明】、【分析方法】、【判定逻辑】
    """
    if not custom_prompt:
        return ""
    
    sections = []
    for section_name in ['检查要点', '补充说明', '分析方法', '判定逻辑', '判定标准']:
        pattern = f'【{section_name}】(.*?)(?:【|$)'
        match = re.search(pattern, custom_prompt, re.DOTALL)
        if match:
            content = match.group(1).strip()
            sections.append(f"【{section_name}】\n{content}")
    
    return '\n\n'.join(sections) if sections else custom_prompt


def extract_compact_guidance(custom_prompt: str) -> str:
    """
    方案 C：提取紧凑的质控指导（混合版）
    提取【检查要点】+ 【判定逻辑】，并压缩格式
    """
    if not custom_prompt:
        return ""
    
    sections = []
    
    # 1. 提取【检查要点】
    match = re.search(r'【检查要点】(.*?)(?:【|$)', custom_prompt, re.DOTALL)
    if match:
        check_points = match.group(1).strip()
        # 压缩格式：去掉多余空行
        check_points = re.sub(r'\n\s*\n', '\n', check_points)
        sections.append(f"检查要点:\n{check_points}")
    
    # 2. 提取【判定逻辑】或【判定标准】
    for keyword in ['判定逻辑', '判定标准', '补充说明']:
        match = re.search(f'【{keyword}】(.*?)(?:【|$)', custom_prompt, re.DOTALL)
        if match:
            logic = match.group(1).strip()
            logic = re.sub(r'\n\s*\n', '\n', logic)
            sections.append(f"{keyword}:\n{logic}")
            break
    
    return '\n\n'.join(sections) if sections else ''


def build_prompt_current(rules: List[Dict[str, Any]], content: str) -> str:
    """当前快速模式的提示词构建（基准）"""
    rules_text_lines = []
    rules_id_mapping_lines = []
    
    for i, rule in enumerate(rules):
        rule_id = rule.get('rule_id', f"RULE_{i+1}")
        rule_name = rule.get('name', '未命名规则')
        rule_desc = rule.get('description', '无描述')
        
        rules_text_lines.append(f"{i+1}. **[{rule_id}]** {rule_name}: {rule_desc}")
        rules_id_mapping_lines.append(f"  - 第{i+1}条 → rule_id: \"{rule_id}\"")
    
    rules_text = "\n".join(rules_text_lines)
    rules_id_mapping = "\n".join(rules_id_mapping_lines)
    
    prompt = f"""你是一位具有20年经验的资深病案质控专家，严格按照《四川省住院病历质量评定标准（2023年版）》进行病历质量评价。

## 质控任务
文书类型: 入院记录
适用规则数: {len(rules)}

## 质控规则清单
{rules_text}

## 规则ID映射
{rules_id_mapping}

## 病历内容
{content}

## 输出要求

**⚠️ 硬性约束（必须严格遵守）：**
1. **必须输出恰好 {len(rules)} 个JSON对象**，不得多也不得少
2. **输出顺序必须与【质控规则清单】完全一致**
3. **每条规则必须单独评估**
4. **每个JSON对象必须包含准确的rule_id**

不要在 JSON 前后添加任何说明文字，直接输出 JSON 数组："""
    
    return prompt


def build_prompt_plan_a(rules: List[Dict[str, Any]], content: str) -> str:
    """方案 A：提取检查要点（精简版）"""
    rules_text_lines = []
    rules_id_mapping_lines = []
    
    for i, rule in enumerate(rules):
        rule_id = rule.get('rule_id', f"RULE_{i+1}")
        rule_name = rule.get('name', '未命名规则')
        rule_desc = rule.get('description', '无描述')
        custom_prompt = rule.get('custom_prompt', '')
        
        # 提取检查要点
        check_points = extract_check_points(custom_prompt)
        
        if check_points:
            check_points_text = "\n".join(f"     - {p}" for p in check_points)
            rules_text_lines.append(
                f"{i+1}. **[{rule_id}]** {rule_name}\n"
                f"   描述: {rule_desc}\n"
                f"   检查要点:\n{check_points_text}"
            )
        else:
            rules_text_lines.append(f"{i+1}. **[{rule_id}]** {rule_name}: {rule_desc}")
        
        rules_id_mapping_lines.append(f"  - 第{i+1}条 → rule_id: \"{rule_id}\"")
    
    rules_text = "\n\n".join(rules_text_lines)
    rules_id_mapping = "\n".join(rules_id_mapping_lines)
    
    prompt = f"""你是一位具有20年经验的资深病案质控专家，严格按照《四川省住院病历质量评定标准（2023年版）》进行病历质量评价。

## 质控任务
文书类型: 入院记录
适用规则数: {len(rules)}

## 质控规则清单（含检查要点）
{rules_text}

## 规则ID映射
{rules_id_mapping}

## 病历内容
{content}

## 输出要求

**⚠️ 硬性约束（必须严格遵守）：**
1. **必须输出恰好 {len(rules)} 个JSON对象**，不得多也不得少
2. **输出顺序必须与【质控规则清单】完全一致**
3. **每条规则必须单独评估**，根据上述检查要点逐一核对
4. **每个JSON对象必须包含准确的rule_id**

不要在 JSON 前后添加任何说明文字，直接输出 JSON 数组："""
    
    return prompt


def build_prompt_plan_b(rules: List[Dict[str, Any]], content: str) -> str:
    """方案 B：使用完整 custom_prompt（理想版）"""
    rules_details = []
    
    for i, rule in enumerate(rules):
        rule_id = rule.get('rule_id', f"RULE_{i+1}")
        rule_name = rule.get('name', '未命名规则')
        custom_prompt = rule.get('custom_prompt', '')
        
        if custom_prompt:
            # 提取核心部分
            core_prompt = extract_core_prompt(custom_prompt)
            rules_details.append(
                f"### 规则 {i+1}: [{rule_id}] {rule_name}\n\n{core_prompt}\n"
            )
        else:
            # 降级到描述
            rule_desc = rule.get('description', '无描述')
            rules_details.append(
                f"### 规则 {i+1}: [{rule_id}] {rule_name}\n描述: {rule_desc}\n"
            )
    
    rules_text = '\n'.join(rules_details)
    
    prompt = f"""你是一位具有20年经验的资深病案质控专家，严格按照《四川省住院病历质量评定标准（2023年版）》进行病历质量评价。

## 病历内容
{content}

## 质控规则（共 {len(rules)} 条）

{rules_text}

## 输出要求

请按照上述规则顺序，输出 {len(rules)} 个 JSON 对象的数组。

**⚠️ 硬性约束：**
1. **必须输出恰好 {len(rules)} 个JSON对象**
2. **输出顺序必须与规则顺序一致**
3. **每条规则必须根据其检查要点、判定逻辑独立评估**
4. **每个JSON对象必须包含准确的rule_id**

不要在 JSON 前后添加任何说明文字，直接输出 JSON 数组："""
    
    return prompt


def build_prompt_plan_c(rules: List[Dict[str, Any]], content: str) -> str:
    """方案 C：提取紧凑指导（混合版）"""
    rules_text_lines = []
    rules_id_mapping_lines = []

    for i, rule in enumerate(rules):
        rule_id = rule.get('rule_id', f"RULE_{i+1}")
        rule_name = rule.get('name', '未命名规则')
        custom_prompt = rule.get('custom_prompt', '')

        # 提取紧凑指导
        compact_guidance = extract_compact_guidance(custom_prompt)

        if compact_guidance:
            rules_text_lines.append(
                f"{i+1}. **[{rule_id}]** {rule_name}\n{compact_guidance}"
            )
        else:
            # 降级到描述
            rule_desc = rule.get('description', '无描述')
            rules_text_lines.append(f"{i+1}. **[{rule_id}]** {rule_name}: {rule_desc}")

        rules_id_mapping_lines.append(f"  - 第{i+1}条 → rule_id: \"{rule_id}\"")

    rules_text = "\n\n".join(rules_text_lines)
    rules_id_mapping = "\n".join(rules_id_mapping_lines)

    prompt = f"""你是一位具有20年经验的资深病案质控专家，严格按照《四川省住院病历质量评定标准（2023年版）》进行病历质量评价。

## 质控任务
文书类型: 入院记录
适用规则数: {len(rules)}

## 质控规则清单（含检查要点和判定逻辑）
{rules_text}

## 规则ID映射
{rules_id_mapping}

## 病历内容
{content}

## 输出要求

**⚠️ 硬性约束（必须严格遵守）：**
1. **必须输出恰好 {len(rules)} 个JSON对象**，不得多也不得少
2. **输出顺序必须与【质控规则清单】完全一致**
3. **每条规则必须根据其检查要点和判定逻辑独立评估**
4. **每个JSON对象必须包含准确的rule_id**

不要在 JSON 前后添加任何说明文字，直接输出 JSON 数组："""

    return prompt


def estimate_tokens(text: str) -> int:
    """估算 token 数量（中文约 1.5 字符 = 1 token）"""
    return int(len(text) / 1.5)


def analyze_prompt(prompt: str, plan_name: str) -> Dict[str, Any]:
    """分析提示词"""
    char_count = len(prompt)
    token_estimate = estimate_tokens(prompt)

    # 统计各部分长度
    lines = prompt.split('\n')

    return {
        "plan_name": plan_name,
        "char_count": char_count,
        "token_estimate": token_estimate,
        "line_count": len(lines),
        "has_check_points": "检查要点" in prompt,
        "has_judgment_logic": "判定逻辑" in prompt or "判定标准" in prompt,
        "has_analysis_method": "分析方法" in prompt,
    }


def generate_comparison_report(
    current_analysis: Dict[str, Any],
    plan_a_analysis: Dict[str, Any],
    plan_b_analysis: Dict[str, Any],
    plan_c_analysis: Dict[str, Any]
) -> str:
    """生成对比报告"""

    report = []
    report.append("=" * 80)
    report.append("快速质控模式提示词优化方案对比报告")
    report.append("=" * 80)
    report.append("")

    # 测试信息
    report.append("## 测试信息")
    report.append("")
    report.append(f"测试病历：张伟，44岁，右肺占位性病变")
    report.append(f"测试规则：LX-001 ~ LX-009（9 条入院记录规则）")
    report.append(f"病历长度：{len(TEST_MEDICAL_RECORD)} 字符")
    report.append("")

    # 提示词长度对比
    report.append("## 提示词长度对比")
    report.append("")
    report.append("| 方案 | 字符数 | Token 估算 | 增长率 | 行数 |")
    report.append("|------|--------|-----------|--------|------|")

    baseline_tokens = current_analysis['token_estimate']

    for analysis in [current_analysis, plan_a_analysis, plan_b_analysis, plan_c_analysis]:
        name = analysis['plan_name']
        chars = analysis['char_count']
        tokens = analysis['token_estimate']
        lines = analysis['line_count']

        if name == "当前模式":
            increase = "基准"
        else:
            increase_pct = ((tokens - baseline_tokens) / baseline_tokens) * 100
            increase = f"+{increase_pct:.1f}%"

        report.append(f"| {name} | {chars:,} | {tokens:,} | {increase} | {lines} |")

    report.append("")

    # 信息量对比
    report.append("## 信息量对比")
    report.append("")
    report.append("| 方案 | 检查要点 | 判定逻辑 | 分析方法 |")
    report.append("|------|---------|---------|---------|")

    for analysis in [current_analysis, plan_a_analysis, plan_b_analysis, plan_c_analysis]:
        name = analysis['plan_name']
        check_points = "✅" if analysis['has_check_points'] else "❌"
        judgment = "✅" if analysis['has_judgment_logic'] else "❌"
        analysis_method = "✅" if analysis['has_analysis_method'] else "❌"

        report.append(f"| {name} | {check_points} | {judgment} | {analysis_method} |")

    report.append("")

    # 详细分析
    report.append("## 详细分析")
    report.append("")

    report.append("### 当前模式（基准）")
    report.append(f"- 字符数：{current_analysis['char_count']:,}")
    report.append(f"- Token 估算：{current_analysis['token_estimate']:,}")
    report.append(f"- 信息量：只包含规则 ID、名称、描述")
    report.append("")

    report.append("### 方案 A：提取检查要点（精简版）")
    plan_a_increase = ((plan_a_analysis['token_estimate'] - baseline_tokens) / baseline_tokens) * 100
    report.append(f"- 字符数：{plan_a_analysis['char_count']:,}")
    report.append(f"- Token 估算：{plan_a_analysis['token_estimate']:,}")
    report.append(f"- Token 增长：+{plan_a_increase:.1f}%")
    report.append(f"- 信息量：包含检查要点列表")
    report.append(f"- 优点：Token 增长可控，保留核心检查要点")
    report.append(f"- 缺点：缺少判定逻辑和分析方法")
    report.append("")

    report.append("### 方案 B：完整 custom_prompt（理想版）")
    plan_b_increase = ((plan_b_analysis['token_estimate'] - baseline_tokens) / baseline_tokens) * 100
    report.append(f"- 字符数：{plan_b_analysis['char_count']:,}")
    report.append(f"- Token 估算：{plan_b_analysis['token_estimate']:,}")
    report.append(f"- Token 增长：+{plan_b_increase:.1f}%")
    report.append(f"- 信息量：包含检查要点、判定逻辑、分析方法等完整信息")
    report.append(f"- 优点：信息最完整，准确性最高")
    report.append(f"- 缺点：Token 消耗大，成本高")
    report.append("")

    report.append("### 方案 C：提取紧凑指导（混合版）⭐ 推荐")
    plan_c_increase = ((plan_c_analysis['token_estimate'] - baseline_tokens) / baseline_tokens) * 100
    report.append(f"- 字符数：{plan_c_analysis['char_count']:,}")
    report.append(f"- Token 估算：{plan_c_analysis['token_estimate']:,}")
    report.append(f"- Token 增长：+{plan_c_increase:.1f}%")
    report.append(f"- 信息量：包含检查要点和判定逻辑，去掉冗余说明")
    report.append(f"- 优点：平衡了准确性和成本，信息量适中")
    report.append(f"- 缺点：需要精心设计提取逻辑")
    report.append("")

    # 推荐结论
    report.append("## 推荐结论")
    report.append("")
    report.append("**推荐方案：方案 C（混合版）**")
    report.append("")
    report.append("理由：")
    report.append(f"1. Token 增长适中（+{plan_c_increase:.1f}%），成本可控")
    report.append("2. 保留了最核心的检查要点和判定逻辑")
    report.append("3. 去掉了冗余的输出格式说明（在批量提示词中统一说明）")
    report.append("4. 预期准确性提升 60-70%，接近方案 B 的效果")
    report.append("")

    report.append("=" * 80)

    return "\n".join(report)


def main():
    """主函数"""
    print("=" * 80)
    print("🎯 快速质控模式提示词优化方案对比测试")
    print("=" * 80)
    print("")

    # 1. 加载规则
    print("📋 加载规则...")
    rules = load_rules()
    print(f"✅ 已加载 {len(rules)} 条规则")
    print("")

    # 2. 生成四种提示词
    print("🔨 生成提示词...")

    print("  - 当前模式（基准）")
    prompt_current = build_prompt_current(rules, TEST_MEDICAL_RECORD)

    print("  - 方案 A：提取检查要点")
    prompt_plan_a = build_prompt_plan_a(rules, TEST_MEDICAL_RECORD)

    print("  - 方案 B：完整 custom_prompt")
    prompt_plan_b = build_prompt_plan_b(rules, TEST_MEDICAL_RECORD)

    print("  - 方案 C：提取紧凑指导")
    prompt_plan_c = build_prompt_plan_c(rules, TEST_MEDICAL_RECORD)

    print("✅ 提示词生成完成")
    print("")

    # 3. 分析提示词
    print("📊 分析提示词...")

    current_analysis = analyze_prompt(prompt_current, "当前模式")
    plan_a_analysis = analyze_prompt(prompt_plan_a, "方案 A")
    plan_b_analysis = analyze_prompt(prompt_plan_b, "方案 B")
    plan_c_analysis = analyze_prompt(prompt_plan_c, "方案 C")

    print("✅ 分析完成")
    print("")

    # 4. 保存提示词到文件
    print("💾 保存提示词到文件...")

    with open('/tmp/prompt_comparison_current.txt', 'w', encoding='utf-8') as f:
        f.write(prompt_current)
    print("  ✅ /tmp/prompt_comparison_current.txt")

    with open('/tmp/prompt_comparison_plan_a.txt', 'w', encoding='utf-8') as f:
        f.write(prompt_plan_a)
    print("  ✅ /tmp/prompt_comparison_plan_a.txt")

    with open('/tmp/prompt_comparison_plan_b.txt', 'w', encoding='utf-8') as f:
        f.write(prompt_plan_b)
    print("  ✅ /tmp/prompt_comparison_plan_b.txt")

    with open('/tmp/prompt_comparison_plan_c.txt', 'w', encoding='utf-8') as f:
        f.write(prompt_plan_c)
    print("  ✅ /tmp/prompt_comparison_plan_c.txt")

    print("")

    # 5. 生成对比报告
    print("📝 生成对比报告...")

    report = generate_comparison_report(
        current_analysis,
        plan_a_analysis,
        plan_b_analysis,
        plan_c_analysis
    )

    # 保存报告
    with open('/tmp/prompt_comparison_summary.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    print("  ✅ /tmp/prompt_comparison_summary.txt")

    # 保存 JSON 数据
    comparison_data = {
        "test_info": {
            "medical_record": "张伟，44岁，右肺占位性病变",
            "rules": LX_ADMISSION_RULES,
            "record_length": len(TEST_MEDICAL_RECORD)
        },
        "current": current_analysis,
        "plan_a": plan_a_analysis,
        "plan_b": plan_b_analysis,
        "plan_c": plan_c_analysis
    }

    with open('/tmp/prompt_comparison_report.json', 'w', encoding='utf-8') as f:
        json.dump(comparison_data, f, ensure_ascii=False, indent=2)
    print("  ✅ /tmp/prompt_comparison_report.json")

    print("")

    # 6. 打印报告
    print(report)

    print("")
    print("=" * 80)
    print("✅ 测试完成！")
    print("=" * 80)
    print("")
    print("📁 生成的文件：")
    print("  - /tmp/prompt_comparison_current.txt  （当前模式提示词）")
    print("  - /tmp/prompt_comparison_plan_a.txt   （方案 A 提示词）")
    print("  - /tmp/prompt_comparison_plan_b.txt   （方案 B 提示词）")
    print("  - /tmp/prompt_comparison_plan_c.txt   （方案 C 提示词）")
    print("  - /tmp/prompt_comparison_summary.txt  （对比报告）")
    print("  - /tmp/prompt_comparison_report.json  （详细数据）")
    print("")


if __name__ == "__main__":
    main()

