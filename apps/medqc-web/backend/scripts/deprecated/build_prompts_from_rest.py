import os
import json
from typing import Any, Dict, List
import httpx


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
    "【病历片段】\n{section_text}\n"
    "【判定口径】\n"
    "- 结合上下文与医学常识进行语义判断，不做主观臆断\n"
    "- 仅依据提供的文本做出结论\n"
    "- 输出结构化 JSON（见下）\n"
    "【严重程度提示】{severity_hint}\n"
    "【输出JSON格式】\n"
    "{\n"
    "  \"violation\": <true|false>,\n"
    "  \"reason\": \"为何判定/不判定违规则，引用关键句\",\n"
    "  \"suggestion\": \"如有问题，提出改进建议\"\n"
    "}\n"
)


def build_prompt(rule: Dict[str, Any]) -> str:
    category = (rule.get("category") or "consistency").lower()
    severity = (rule.get("severity") or "minor").lower()
    intent = CATEGORY_INTENT.get(category, CATEGORY_INTENT["consistency"])
    severity_hint = SEVERITY_HINT.get(severity, SEVERITY_HINT["minor"])

    doc_types = rule.get("applicable_documents") or rule.get("applicable_record_types") or []
    sections = rule.get("target_sections") or []
    doc_type = (doc_types[0] if isinstance(doc_types, list) and doc_types else "通用文书")
    section = (sections[0] if isinstance(sections, list) and sections else "全文/相关章节")
    return BASE_TEMPLATE.format(intent=intent, doc_type=doc_type, section=section, severity_hint=severity_hint)


def fetch_rules(url: str, key: str) -> List[Dict[str, Any]]:
    params = {
        "select": "id,rule_code,name,category,severity,applicable_documents,applicable_record_types,target_sections,prompt_template",
        "limit": "200",
    }
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{url.rstrip('/')}/rest/v1/qc_rules", headers=headers, params=params)
        r.raise_for_status()
        return r.json()  # type: ignore[return-value]


def main() -> None:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))
    os.makedirs(base, exist_ok=True)
    supabase_url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not key:
        raise SystemExit("缺少 SUPABASE_URL 或 API KEY")

    rules = fetch_rules(supabase_url, key)
    enriched: List[Dict[str, Any]] = []
    for r in rules:
        prompt = r.get("prompt_template") or build_prompt(r)
        enriched.append({
            "id": r.get("id"),
            "rule_code": r.get("rule_code"),
            "name": r.get("name"),
            "prompt_template": prompt,
        })

    json_path = os.path.join(base, "prompts_68.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    # 生成 SQL（按 rule_code 更新，避免 id 差异）
    sql_lines = [
        "-- 更新 qc_rules.prompt_template（草案）",
        "-- 在 Supabase SQL 控制台执行；如启用 RLS，请使用 service role 权限",
    ]
    for item in enriched:
        rc = (item.get("rule_code") or "").replace("'", "''")
        if not rc:
            continue
        tmpl = (item.get("prompt_template") or "").replace("'", "''")
        sql_lines.append(
            f"update public.qc_rules set prompt_template='" + tmpl + f"' where rule_code='" + rc + "';"
        )

    sql_path = os.path.join(base, "prompts_68.sql")
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines) + "\n")

    print("生成完成：")
    print("-", json_path)
    print("-", sql_path)


if __name__ == "__main__":
    main()



