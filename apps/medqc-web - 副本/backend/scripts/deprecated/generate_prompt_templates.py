import os
import sys
from typing import Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.supabase_client import get_supabase


CATEGORY_INTENT = {
    "consistency": "检查跨文书/章节语义一致性",
    "completeness": "检查必填信息是否完整齐全",
    "accuracy": "检查叙述是否准确、证据是否充分",
    "timeliness": "检查记录是否按时完成，时间顺序是否合理",
    "compliance": "检查是否符合规范与政策要求",
}

SEVERITY_HINT = {
    "critical": "此类问题为严重缺陷，如发现需明确指出关键依据。",
    "major": "此类问题为一般缺陷，应给出改进建议。",
    "minor": "此类问题为轻微缺陷，可给简要说明。",
}

BASE_TEMPLATE = (
    "你是一名资深临床质控专家，负责住院病历语义质量核查。\n"
    "【任务目标】{intent}\n"
    "【输入文书】类型：{doc_type}；章节：{section}\n"
    "【病历片段】\n{{section_text}}\n"
    "【判定口径】\n"
    "- 结合上下文与医学常识进行语义判断，不做主观臆断\n"
    "- 仅依据提供的文本做出结论\n"
    "- 输出结构化 JSON（见下）\n"
    "【严重程度提示】{severity_hint}\n"
    "【输出JSON格式】\n"
    "{{\n"
    "  \"violation\": <true|false>,\n"
    "  \"reason\": \"为何判定/不判定违规则，引用关键句\",\n"
    "  \"suggestion\": \"如有问题，提出改进建议\"\n"
    "}}\n"
)


def build_prompt(rule: Dict[str, Any]) -> str:
    category = (rule.get("category") or "consistency").lower()
    severity = (rule.get("severity") or "minor").lower()
    intent = CATEGORY_INTENT.get(category, CATEGORY_INTENT["consistency"])
    severity_hint = SEVERITY_HINT.get(severity, SEVERITY_HINT["minor"])

    # 取第一个文书/章节作为模板展示，不锁死具体类型
    doc_types = rule.get("applicable_documents") or rule.get("applicable_record_types") or []
    sections = rule.get("target_sections") or []
    doc_type = doc_types[0] if doc_types else "通用文书"
    section = sections[0] if sections else "全文/相关章节"

    return BASE_TEMPLATE.format(intent=intent, doc_type=doc_type, section=section, severity_hint=severity_hint)


def main(dry_run: bool = False) -> None:
    sb = get_supabase()
    if not sb:
        print("Supabase 未初始化，请检查环境变量")
        sys.exit(1)

    # 仅获取缺失 prompt_template 的规则
    data = sb.table("qc_rules").select("id, rule_code, name, category, severity, applicable_record_types, target_sections, prompt_template").is_("prompt_template", None).execute()
    rules = data.data or []
    print(f"待补全规则数: {len(rules)}")

    updated = 0
    for r in rules:
        prompt = build_prompt(r)
        if dry_run:
            print(f"\n[DRY-RUN] {r.get('rule_code') or r.get('id')} -> 预览模板:\n{prompt}\n")
            continue

        sb.table("qc_rules").update({"prompt_template": prompt}).eq("id", r["id"]).execute()
        updated += 1

    print(f"已更新 prompt_template: {updated} 条")


if __name__ == "__main__":
    dry = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")
    main(dry_run=dry)


