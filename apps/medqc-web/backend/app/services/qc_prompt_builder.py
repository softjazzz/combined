"""
质控 Prompt 构建器

负责：
- 从 custom_prompt 中提取检查要点、判定逻辑等
- 时间预计算（避免 LLM 算术幻觉）
- 智能截断
- 组装最终的 LLM prompt
"""
import re
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class QCPromptBuilder:
    """从 SichuanQCService 中拆出的 Prompt 构建逻辑。"""

    def __init__(self, enable_truncate: bool = True, max_content_length: int = 4000):
        self.enable_truncate = enable_truncate
        self.max_content_length = max_content_length

    # ──────────────────────────────────────────────────────
    # 智能截断
    # ──────────────────────────────────────────────────────

    def smart_truncate(self, content: str, max_length: int = 4000) -> str:
        """
        智能截断病历内容，优先保留完整段落，避免切断句子。

        Args:
            content: 原始病历内容
            max_length: 最大字符长度

        Returns:
            截断后的内容，带有截断提示
        """
        if len(content) <= max_length:
            return content

        # 预留截断提示的空间（约80字符）
        reserve_space = 80
        effective_max = max_length - reserve_space

        # 截断到有效长度
        truncated = content[:effective_max]

        # 向前查找最近的段落分隔符（\n\n 或 \n）
        last_paragraph = truncated.rfind('\n\n')
        last_newline = truncated.rfind('\n')

        # 如果段落边界在合理范围内（90%以上），使用段落边界
        if last_paragraph > effective_max * 0.9:
            result = truncated[:last_paragraph]
        elif last_newline > effective_max * 0.8:
            result = truncated[:last_newline]
        else:
            # 如果没有合适的边界，查找最后一个句号
            last_period = truncated.rfind('。')
            if last_period > effective_max * 0.8:
                result = truncated[:last_period + 1]
            else:
                result = truncated

        # 添加截断标记
        total_chars = len(content)
        kept_chars = len(result)
        truncated_chars = total_chars - kept_chars

        result += f"\n\n[注：病历内容过长，已截断 {truncated_chars} 字符（保留前 {kept_chars}/{total_chars} 字符）]"

        logger.info(f"智能截断: 原始 {total_chars} 字符 → 保留 {kept_chars} 字符（{kept_chars/total_chars*100:.1f}%）")

        return result

    # ──────────────────────────────────────────────────────
    # 检查要点提取
    # ──────────────────────────────────────────────────────

    def extract_check_points(self, custom_prompt: str) -> str:
        """
        从 custom_prompt 中提取检查要点

        Args:
            custom_prompt: 完整的自定义提示词

        Returns:
            提取的检查要点文本，如果没有则返回空字符串
        """
        if not custom_prompt:
            return ""

        # 查找【检查要点】部分
        start_marker = "【检查要点】"
        end_markers = ["【判定逻辑】", "【分析方法】", "【注意事项】", "【示例】"]

        start_idx = custom_prompt.find(start_marker)
        if start_idx == -1:
            return ""

        # 查找结束位置
        end_idx = len(custom_prompt)
        for marker in end_markers:
            idx = custom_prompt.find(marker, start_idx)
            if idx != -1 and idx < end_idx:
                end_idx = idx

        # 提取并清理
        check_points = custom_prompt[start_idx:end_idx].strip()
        return check_points

    def extract_core_guidance(self, custom_prompt: str) -> str:
        """
        提取核心指导信息（检查要点 + 判定逻辑 + 分析方法）- 方案 C

        Args:
            custom_prompt: 完整的自定义提示词

        Returns:
            提取的核心指导信息
        """
        if not custom_prompt:
            return ""

        parts = []

        # 提取【检查要点】
        check_points = self.extract_check_points(custom_prompt)
        if check_points:
            parts.append(check_points)

        # 提取【判定逻辑】
        logic_start = custom_prompt.find("【判定逻辑】")
        if logic_start != -1:
            logic_end_markers = ["【分析方法】", "【注意事项】", "【示例】"]
            logic_end = len(custom_prompt)
            for marker in logic_end_markers:
                idx = custom_prompt.find(marker, logic_start)
                if idx != -1 and idx < logic_end:
                    logic_end = idx

            logic = custom_prompt[logic_start:logic_end].strip()
            if logic:
                parts.append(logic)

        return "\n\n".join(parts)

    def extract_enhanced_guidance(self, custom_prompt: str, rule_id: str) -> str:
        """
        为复杂规则提取增强的指导信息（检查要点 + 判定逻辑）

        Args:
            custom_prompt: 完整的自定义提示词
            rule_id: 规则ID

        Returns:
            增强的指导信息
        """
        if not custom_prompt:
            return ""

        # 定义需要增强指导的复杂规则列表
        # 这些规则在测试中误判率较高，需要额外的判定逻辑
        complex_rules = {
            "LX-007",  # 入院记录缺辅助检查
            "LX-009",  # 入院记录缺初步诊断
            # 后续可以根据实际测试结果添加更多规则
        }

        # 如果不是复杂规则，只返回检查要点
        if rule_id not in complex_rules:
            return self.extract_check_points(custom_prompt)

        # 对于复杂规则，提取检查要点 + 判定逻辑
        parts = []

        # 提取【检查要点】
        check_points = self.extract_check_points(custom_prompt)
        if check_points:
            parts.append(check_points)

        # 提取【判定逻辑】
        logic_start = custom_prompt.find("【判定逻辑】")
        if logic_start != -1:
            logic_end_markers = ["【分析方法】", "【注意事项】", "【示例】"]
            logic_end = len(custom_prompt)
            for marker in logic_end_markers:
                idx = custom_prompt.find(marker, logic_start)
                if idx != -1 and idx < logic_end:
                    logic_end = idx

            logic = custom_prompt[logic_start:logic_end].strip()
            if logic:
                parts.append(logic)

        return "\n\n".join(parts)

    # ──────────────────────────────────────────────────────
    # 时间预计算
    # ──────────────────────────────────────────────────────

    def precompute_time_facts(self, rule_id: str, content: str) -> str:
        """
        For time-sensitive rules, extract timestamps from the medical text
        and pre-compute time differences using code, so the LLM doesn't
        need to do arithmetic (which it often gets wrong).

        Returns:
            A string like "【系统预计算】间隔时长：2小时45分钟（< 6小时，符合时效要求）"
            or empty string if not applicable.
        """
        TIME_RULES = {
            # rule_id: (label_start, label_end, limit_hours, limit_label)
            # ---- 入院相关 ----
            'SC-002': (
                ['入院时间', '入院日期'],
                ['书写时间', '记录完成时间', '完成时间', '入院记录书写'],
                24,
                '24小时'
            ),
            'SC-003': (
                ['入院时间', '入院日期'],
                ['书写时间', '记录完成时间', '完成时间'],
                24,
                '24小时'
            ),
            # ---- 首次病程 ----
            'SC-022': (
                ['入院时间', '入院日期'],
                ['首次病程记录时间', '书写时间', '记录完成时间', '首次病程.*?时间'],
                8,
                '8小时'
            ),
            # ---- 查房 ----
            'SC-048': (
                ['入院时间', '入院日期'],
                ['首次查房', '主治医师首次查房', '主治医师.*?查房'],
                48,
                '48小时'
            ),
            # ---- 抢救 ----
            'SC-054': (
                ['抢救结束时间', '抢救结束'],
                ['记录完成时间', '记录完成'],
                6,
                '6小时'
            ),
            # ---- 交接班 ----
            'SC-062': (
                ['交班时间', '变更时间'],
                ['记录完成时间', '交班记录.*?时间', '完成时间'],
                24,
                '24小时'
            ),
            # ---- 会诊 ----
            'SC-071': (
                ['申请时间', '会诊申请时间', '常规会诊申请时间'],
                ['会诊意见时间', '会诊完成时间', '完成时间'],
                24,
                '24小时'
            ),
            # ---- 手术记录 ----
            'SC-096': (
                ['手术结束时间', '手术结束', '术毕时间'],
                ['书写时间', '手术记录书写时间', '记录时间', '完成时间'],
                24,
                '24小时'
            ),
            # ---- 出院/死亡记录 ----
            'SC-117': (
                ['出院时间', '出院日期', '死亡时间'],
                ['书写时间', '出院记录书写时间', '记录时间', '完成时间'],
                24,
                '24小时'
            ),
            # ---- 泸县自定义 ----
            'LX-017': (
                ['申请时间', '常规会诊申请时间', '会诊申请时间'],
                ['完成时间', '会诊记录完成时间', '会诊完成时间'],
                48,
                '48小时'
            ),
            'LX-026': (
                ['手术结束时间', '手术结束', '术毕'],
                ['书写时间', '手术记录书写时间', '记录时间', '完成时间'],
                24,
                '24小时'
            ),
            'LX-029': (
                ['出院时间', '出院日期'],
                ['书写时间', '出院记录书写时间', '记录时间', '完成时间'],
                24,
                '24小时'
            ),
        }


        if rule_id not in TIME_RULES:
            return ""

        start_labels, end_labels, limit_h, limit_label = TIME_RULES[rule_id]

        # Common datetime patterns in Chinese medical records
        dt_patterns = [
            r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日号]?\s*(\d{1,2})[:时](\d{1,2})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})',
        ]

        def find_time_near_label(text: str, labels: list):
            for label in labels:
                match = re.search(label, text)
                if not match:
                    continue
                # Search within 80 chars after the label
                search_start = match.end()
                search_region = text[search_start:search_start + 80]
                for pat in dt_patterns:
                    m = re.search(pat, search_region)
                    if m:
                        try:
                            groups = m.groups()
                            return datetime(
                                int(groups[0]), int(groups[1]), int(groups[2]),
                                int(groups[3]), int(groups[4])
                            )
                        except (ValueError, IndexError):
                            continue
            return None

        t_start = find_time_near_label(content, start_labels)
        t_end = find_time_near_label(content, end_labels)

        if t_start is None or t_end is None:
            return ""

        delta = t_end - t_start
        total_minutes = delta.total_seconds() / 60
        hours = int(total_minutes // 60)
        minutes = int(total_minutes % 60)

        if total_minutes < 0:
            return ""

        compliant = total_minutes <= limit_h * 60
        verdict = "符合时效要求" if compliant else "超出时效要求"
        relation = "<" if compliant else ">"

        fact = (
            f"\n\n【系统预计算（以下为代码精确计算结果，请直接采信）】\n"
            f"起始时间：{t_start.strftime('%Y-%m-%d %H:%M')}\n"
            f"结束时间：{t_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"间隔时长：{hours}小时{minutes}分钟（{relation} {limit_label}，{verdict}）"
        )

        logger.info(f"时间预计算 [{rule_id}]: {hours}h{minutes}m, compliant={compliant}")
        return fact

    # ──────────────────────────────────────────────────────
    # 主构建方法
    # ──────────────────────────────────────────────────────

    async def build_prompt(
        self,
        rules: List[Dict[str, Any]],
        content: str,
        document_type: str,
        prompt_mode: str = "plan_a"
    ) -> str:
        """
        使用规则列表和病历内容构建质控分析 Prompt。

        Args:
            rules: 适用规则列表
            content: 病历内容
            document_type: 文书类型
            prompt_mode: 提示词优化方案
                - "current": 当前模式（只使用 rule_id + name + description）
                - "plan_a": 方案A - 精简版（提取【检查要点】）
                - "plan_b": 方案B - 完整版（使用完整 custom_prompt）
                - "plan_c": 方案C - 平衡版（提取【检查要点】+【判定逻辑】）

        Returns:
            完整的 Prompt 字符串
        """
        # 构建规则清单（根据 prompt_mode 决定提取内容）
        rules_text = ""
        rules_id_mapping_text = ""
        if rules:
            rules_text_lines = []
            rules_id_mapping_lines = []

            for i, rule in enumerate(rules):
                # GPT建议：使用 id 字段兜底，避免 None
                rule_id = rule.get('rule_id') or rule.get('id') or rule.get('rule_code') or f"RULE_{i+1}"
                rule_name = rule.get('name', '未命名规则')
                rule_desc = rule.get('description', '无描述')
                custom_prompt = rule.get('custom_prompt', '')

                # 根据 prompt_mode 提取不同的内容
                guidance = ""
                if prompt_mode == "current":
                    guidance = ""
                elif prompt_mode == "plan_a":
                    guidance = self.extract_enhanced_guidance(custom_prompt, rule_id)
                elif prompt_mode == "plan_b":
                    guidance = custom_prompt
                elif prompt_mode == "plan_c":
                    guidance = self.extract_core_guidance(custom_prompt)
                else:
                    guidance = self.extract_enhanced_guidance(custom_prompt, rule_id)

                # 时间预计算：对时间敏感型规则，用代码精确计算时间差并注入 guidance
                time_fact = self.precompute_time_facts(rule_id, content)
                if time_fact:
                    guidance = (guidance + time_fact) if guidance else time_fact

                # 规则清单：序号 + rule_id + 名称 + 描述 + 额外指导
                if guidance:
                    rules_text_lines.append(
                        f"{i+1}. **[{rule_id}]** {rule_name}: {rule_desc}\n\n{guidance}"
                    )
                else:
                    rules_text_lines.append(
                        f"{i+1}. **[{rule_id}]** {rule_name}: {rule_desc}"
                    )

                # 规则ID映射
                rules_id_mapping_lines.append(
                    f"  - 第{i+1}条 → rule_id: \"{rule_id}\""
                )

            rules_text = "\n\n".join(rules_text_lines)
            rules_id_mapping_text = "\n".join(rules_id_mapping_lines)

            # 统计提取情况
            rules_with_guidance = sum(1 for rule in rules if self.extract_enhanced_guidance(rule.get('custom_prompt', ''), rule.get('rule_id', '')))
            logger.info(f"快速质控提示词构建: 共 {len(rules)} 条规则, {rules_with_guidance} 条包含检查要点")
        else:
            rules_text = "（未加载到具体规则，将进行通用质控分析）"
            rules_id_mapping_text = "（无规则映射）"

        # Prompt 模板
        base_template = """你是一位具有20年经验的资深病案质控专家，严格按照《四川省住院病历质量评定标准（2023年版）》进行病历质量评价。

## 质控任务
文书类型: {document_type}
适用规则数: {rules_count}

## 质控规则清单
{rules_text}

## 规则ID映射
{rules_id_mapping}

## 病历内容
{content}

## 输出要求

**⚠️ 硬性约束（必须严格遵守）：**
1. **必须输出恰好 {rules_count} 个JSON对象**，不得多也不得少
2. **输出顺序必须与【质控规则清单】完全一致**，第1个对象对应第1条规则，第2个对象对应第2条规则，依此类推
3. **每条规则必须单独评估**，即使多条规则看起来相似，也不得合并输出
4. **每个JSON对象必须包含准确的rule_id**，对应关系见【规则ID映射】
5. **即使某条规则不适用当前文书，也必须输出对象**，is_compliant设为true，findings注明"不适用于当前文书类型"

**JSON对象格式：**
每条规则的评估结果必须包含以下字段：
- `rule_id`: 规则编号（字符串，**必填**，对应【规则ID映射】）
- `rule_name`: 规则名称（字符串）
- `is_compliant`: 是否符合规则（布尔值，true 或 false）
- `findings`: 评估发现（字符串，如果不符合，必须详细说明具体违反了哪个要求）
- `evidence`: 原文证据（字符串，**不符合时必须从病历中直接引用具体文本片段**）
- `location`: 问题定位（字符串，指出问题在病历的哪个部分）
- `suggestion`: 整改建议（字符串，不符合时给出具体的、可操作的改进建议）
- `confidence`: 评估置信度（浮点数，0.0-1.0之间）

**JSON 输出示例：**
```json
[
  {{
    "rule_id": "SC-001",
    "rule_name": "主诉应简明扼要",
    "is_compliant": false,
    "findings": "主诉过于冗长，包含了详细的病史描述，不符合'简明扼要'的要求",
    "evidence": "患者主诉：'反复胸痛、胸闷3年，加重伴气促1周。患者3年前无明显诱因出现胸痛...'（共120字）",
    "location": "主诉部分",
    "suggestion": "将主诉精简为：'反复胸痛、胸闷3年，加重伴气促1周'，详细病史移至现病史部分",
    "confidence": 0.95
  }},
  {{
    "rule_id": "SC-002",
    "rule_name": "现病史应包含起病时间",
    "is_compliant": true,
    "findings": "现病史明确记录了起病时间'3年前'和加重时间'1周前'",
    "evidence": "现病史：患者3年前无明显诱因出现胸痛...",
    "location": "现病史部分",
    "suggestion": "",
    "confidence": 0.98
  }}
]
```

**自检清单（输出前请确认）：**
- [ ] 输出了 {rules_count} 个对象？
- [ ] 顺序与规则清单一致？
- [ ] 每个对象都有rule_id？
- [ ] 不符合的规则都有evidence引用？

不要在 JSON 前后添加任何说明文字，直接输出 JSON 数组："""

        # 根据配置决定是否截断病历内容
        if self.enable_truncate:
            processed_content = self.smart_truncate(content, max_length=self.max_content_length)
            logger.info(f"智能截断已启用: 原始长度 {len(content)} → 处理后长度 {len(processed_content)}")
        else:
            processed_content = content
            logger.info(f"截断已禁用: 使用完整病历内容（长度 {len(content)} 字符）")

        prompt = base_template.format(
            document_type=document_type,
            rules_count=len(rules),
            rules_text=rules_text,
            rules_id_mapping=rules_id_mapping_text,
            content=processed_content
        )

        return prompt
