"""
Phase 1: Update custom_prompts for SC-016, SC-117, SC-035
Phase 2: Rewrite test case data for 13 rules in qcRuleCases.ts
"""
import json

# ======================================================================
# PHASE 1: Update custom_prompts in both JSON files
# ======================================================================
PROMPT_FIXES = {
    "SC-016": "【检查要点】\n1. 本规则检查的是儿童患者入院记录中是否包含婴幼儿喂养史和生长发育史。\n2. 注意：规则名称\u201c无婴幼儿喂养史\u201d描述的是【缺陷状态】，不是【合规标准】。\n3. 如果病历中已完整记录了婴幼儿喂养史（如母乳喂养、辅食添加等）和生长发育史（如抬头、坐稳、行走、语言等），则判定为【合规】。\n4. 仅当病历中完全缺失喂养史或生长发育史时，才判定为【不合规】。",
    "SC-117": "【检查要点】\n1. 核查出院记录或死亡记录是否在患者出院（死亡）后24小时内完成。\n2. 注意：出院记录的签署时间等于或早于出院时间是完全合理的\u2014\u2014医师通常在出院当天上午提前完成记录书写，这属于正常工作流程。\n3. 只有当签署时间晚于出院时间超过24小时时，才判定为不合规。\n4. 签署时间与出院时间相同不构成违规。",
    "SC-035": "【检查要点】\n1. 检查病程记录中是否存在不合理的检查或不合理用药。\n2. 不合理检查包括：无指征的检查、重复检查、与诊断无关的检查。\n3. 不合理用药包括：无指征用药、剂量不当、疗程不当、配伍禁忌。\n4. 【格式要求】你必须严格返回纯JSON格式，禁止输出任何分析过程、思考步骤或解释性文字。",
}

json_paths = [
    'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/data/sichuan_rules_146.json',
    'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/sichuan_rules_146.json',
    'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/data/sichuan_rules_146_updated.json',
]

for p in json_paths:
    try:
        with open(p, 'r', encoding='utf-8') as f:
            rules = json.load(f)
        updated = 0
        for r in rules:
            if r['rule_id'] in PROMPT_FIXES:
                r['custom_prompt'] = PROMPT_FIXES[r['rule_id']]
                updated += 1
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        print(f"✅ Updated {updated} rules in {p.split('/')[-1]}")
    except FileNotFoundError:
        print(f"⚠️ Skipped (not found): {p.split('/')[-1]}")

print("\n✅ Phase 1 complete: custom_prompts updated for SC-016, SC-117, SC-035")
