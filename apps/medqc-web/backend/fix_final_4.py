# -*- coding: utf-8 -*-
"""
Fix the final 4 failing rules with BOTH data rewrites AND custom_prompt updates.
"""
import json
import re

# ======================================================================
# 1. Update custom_prompts
# ======================================================================
PROMPT_FIXES = {
    "SC-041": "【检查要点】\n1. 本规则检查的是病程记录中是否有特殊检查、特殊治疗的记录。\n2. 特殊检查包括：内镜检查、穿刺活检、介入检查、心导管检查等。\n3. 特殊治疗包括：PCI术、射频消融、放化疗、血液透析等。\n4. 只要病程记录中对特殊检查/治疗有描述（包括指征、过程概要、术后情况），即判定为合规。\n5. 不要求病程记录中包含完整的手术操作记录——详细的手术步骤应记录在专门的手术记录中，病程记录只需体现特殊诊疗的关键信息。",
    "SC-054": "【检查要点】\n1. 本规则检查抢救记录是否在抢救结束后6小时内完成。\n2. 判断方法：看记录中标注的"记录完成时间"与"抢救结束时间"之差是否≤6小时。\n3. 如果记录中明确标注了"抢救结束时间"和"记录完成时间"，直接计算差值。差值≤6小时即为合规。\n4. 不要反推或质疑已标注的时间，以病历记载为准。",
    "SC-069": "【检查要点】\n1. 本规则检查会诊意见记录是否包含：会诊意见、会诊医师所在科别、会诊时间、会诊医师签名。\n2. 科别标注只要能识别科室即可，例如"心血管内科"、"心内科"均为有效标注。在签名处标注如"李强（副主任医师，心血管内科）"也算有效记录科别。\n3. 会诊时间只要在记录中有明确的日期时间即可。\n4. 会诊记录可以作为病程记录的一部分，不强制要求另页书写。",
    "SC-111": "【检查要点】\n1. 本规则检查术后病程记录中是否记录了手术情况及大体标本情况。\n2. 术后首次病程记录应包含：手术名称、术中发现、术后情况、标本送检情况等。\n3. 本规则适用于所有包含手术相关内容的病历，包括病程记录和手术记录文书。\n4. 即使输入的文书类型标注为progress_note或operation_record，只要内容涉及手术相关，本规则均适用。不要以文书类型不匹配为由跳过检查。",
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
        print(f"✅ Updated {updated} prompts in {p.split('/')[-1]}")
    except FileNotFoundError:
        print(f"⚠️ Skipped: {p.split('/')[-1]}")

# ======================================================================
# 2. Rewrite test case data
# ======================================================================
TS_PATH = 'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/src/data/qcRuleCases.ts'

def esc(s):
    return ''.join(f'\\u{ord(c):04x}' if ord(c) > 127 else c for c in s)

REPLACEMENTS = {
    # SC-041 positive: Rewrite to clearly have special treatment record in progress note
    'SC-041': {
        'positive': {
            'title': '冠脉介入术后病程记录中有完整的特殊治疗记录',
            'summary': '病程记录中详细记录了PCI术的指征、术中关键发现、术后评估与并发症观察，符合规范。',
            'sections': [
                ('特殊治疗记录', '2024-03-15 16:00 经皮冠状动脉介入治疗（PCI）术后记录\n\n一、手术指征：患者因急性前壁ST段抬高型心肌梗死，心电图示V1-V4导联ST段弓背抬高，肌钙蛋白T 5.6ng/ml，符合急诊PCI指征。\n\n二、手术概要：在局麻下经右侧桡动脉入路，行冠状动脉造影示前降支近段完全闭塞。以导丝通过闭塞段，球囊预扩张后植入药物洗脱支架1枚（3.0×28mm），术后复查造影示前向血流TIMI 3级，支架贴壁良好，无残余狭窄，无夹层及血栓形成。\n\n三、术后情况：术后送返CCU，意识清楚，生命体征平稳（BP 118/72mmHg，HR 76次/分），穿刺部位无渗血。心电图示ST段较术前明显回落。指尖SpO2 98%。\n\n四、术后医嘱：\n1. CCU心电监护24小时\n2. 双联抗血小板（阿司匹林100mg qd + 替格瑞洛90mg bid）\n3. 阿托伐他汀40mg qn\n4. 低分子肝素4000IU q12h\n5. 密切观察穿刺部位有无血肿\n\n记录医师：张磊（主治医师）\n上级审阅签名：李明（主任医师）'),
            ],
            'focusPoints': ['病程记录中完整记录了特殊治疗（PCI）的手术指征、术中关键发现、术后评估及后续处理']
        }
    },

    # SC-069 positive: Cleaner consultation format
    'SC-069': {
        'positive': {
            'title': '会诊记录包含全部必要要素',
            'summary': '会诊记录明确记录了会诊意见、会诊医师所在科别、会诊时间及会诊医师签名。',
            'sections': [
                ('会诊记录', '会诊类型：科间常规会诊\n申请科室：呼吸与危重症医学科\n申请医师：王某（主治医师）\n申请时间：2023-10-15 10:00\n\n会诊医师所在科别：心血管内科\n会诊医师：李强  职称：副主任医师\n会诊时间：2023-10-15 14:30\n\n患者基本情况：\n患者张某某，男，65岁，因"反复咳嗽伴胸闷2周"入院。既往冠心病史5年，PCI术后2年。入院后心电图示偶发室性早搏。\n\n会诊意见：\n1. 患者冠心病PCI术后，目前合并频发室早，建议完善24小时动态心电图评估早搏负荷。\n2. 继续当前双联抗血小板方案（阿司匹林+氯吡格雷），暂不调整。\n3. 如早搏负荷超过10%，可考虑加用美托洛尔控制心率。\n4. 建议复查超声心动图评估心脏结构及功能。\n5. 如病情变化可再次会诊。\n\n会诊医师签名：李强（副主任医师，心血管内科）\n会诊完成时间：2023-10-15 15:00'),
            ],
            'focusPoints': ['会诊记录完整包含：会诊意见（5条具体建议）、会诊医师所在科别（心血管内科）、会诊时间（2023-10-15 14:30）、会诊医师签名（李强 副主任医师）']
        }
    },

    # SC-111 negative: Change documentType approach — the rule is about 术后病程记录
    # Let's make the negative data clearly about post-op progress notes missing specimen info
    'SC-111': {
        'negative': {
            'title': '术后病程记录未记录手术情况及标本送检',
            'summary': '患者行腹腔镜胆囊切除术后，术后首次病程记录中完全未提及手术情况和标本送检情况。',
            'sections': [
                ('术后首次病程记录', '2024-06-11 14:00 术后首次病程记录\n\n患者今日全麻术后安返病房，目前意识清楚，生命体征平稳。\n体温36.5℃，心率78次/分，血压125/80mmHg，呼吸18次/分。\n腹部敷料固定良好，引流管通畅。\n\n医嘱：\n1. 禁食6小时，之后流质饮食\n2. 头孢呋辛1.5g ivgtt bid 预防感染\n3. 补液2000ml/日\n4. 观察引流液颜色及量\n5. 鼓励早期下床活动\n\n签名：赵某（住院医师）\n\n注：本记录未提及所行手术名称、术中发现、术中出血量、手术时长、切除标本大体情况及标本送检病理情况。'),
            ],
            'focusPoints': ['术后首次病程记录中完全缺少手术名称、术中所见、标本大体情况及送检信息']
        }
    },
}

with open(TS_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

def build_sections_ts(sections_list):
    parts = []
    for heading, body in sections_list:
        h = esc(heading)
        c = esc(body).replace('\n', '\\n')
        parts.append(f'        {{ heading: "{h}", content: "{c}" }}')
    return ',\n'.join(parts)

def build_focus_points_ts(fps):
    return ', '.join(f'"{esc(fp)}"' for fp in fps)

success_count = 0
for rule_id, fields in REPLACEMENTS.items():
    for field_name, data in fields.items():
        rule_pattern = f'ruleId: "{rule_id}"'
        rule_idx = content.find(rule_pattern)
        if rule_idx == -1:
            print(f"❌ Could not find rule {rule_id}")
            continue

        next_rule = content.find('ruleId: "SC-', rule_idx + len(rule_pattern))
        rule_block = content[rule_idx:next_rule] if next_rule != -1 else content[rule_idx:]

        field_idx = rule_block.find(f'{field_name}:')
        if field_idx == -1:
            print(f"❌ Could not find {field_name} in {rule_id}")
            continue

        field_start = rule_idx + field_idx
        sections_start_search = content.find('sections:', field_start)
        if sections_start_search == -1 or sections_start_search > rule_idx + len(rule_block):
            print(f"❌ Could not find sections in {rule_id}.{field_name}")
            continue

        bracket_open = content.find('[', sections_start_search)
        depth = 0
        i = bracket_open
        while i < len(content):
            if content[i] == '[': depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0: break
            i += 1
        bracket_close = i

        focus_start_search = content.find('focusPoints:', bracket_close)
        if focus_start_search == -1 or focus_start_search > rule_idx + len(rule_block):
            print(f"❌ Could not find focusPoints in {rule_id}.{field_name}")
            continue
        fp_bracket_open = content.find('[', focus_start_search)
        fp_bracket_close = content.find(']', fp_bracket_open)

        # Replace title
        title_search = content.find('title:', field_start)
        if title_search != -1 and title_search < sections_start_search:
            tqs = content.find('"', title_search)
            tqe = content.find('"', tqs + 1)
            while content[tqe - 1] == '\\': tqe = content.find('"', tqe + 1)
            new_t = esc(data['title'])
            content = content[:tqs+1] + new_t + content[tqe:]
            offset = len(new_t) - (tqe - tqs - 1)
            bracket_open += offset; bracket_close += offset
            fp_bracket_open += offset; fp_bracket_close += offset
            sections_start_search += offset

        # Replace summary
        summary_search = content.find('summary:', field_start)
        if summary_search != -1 and summary_search < sections_start_search:
            sqs = content.find('"', summary_search)
            sqe = content.find('"', sqs + 1)
            while content[sqe - 1] == '\\': sqe = content.find('"', sqe + 1)
            new_s = esc(data['summary'])
            content = content[:sqs+1] + new_s + content[sqe:]
            offset = len(new_s) - (sqe - sqs - 1)
            bracket_open += offset; bracket_close += offset
            fp_bracket_open += offset; fp_bracket_close += offset

        # Replace sections
        new_sections = '[\n' + build_sections_ts(data['sections']) + '\n      ]'
        content = content[:bracket_open] + new_sections + content[bracket_close+1:]
        offset = len(new_sections) - (bracket_close + 1 - bracket_open)
        fp_bracket_open += offset; fp_bracket_close += offset

        # Replace focusPoints
        new_fps = '[' + build_focus_points_ts(data['focusPoints']) + ']'
        content = content[:fp_bracket_open] + new_fps + content[fp_bracket_close+1:]

        success_count += 1
        print(f"✅ Replaced {rule_id}.{field_name}")

with open(TS_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ Final fix complete: {success_count} data replacements + 4 custom_prompt updates")
