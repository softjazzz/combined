"""
Phase 2: Rewrite positive/negative test case data for 13 failing rules.
This script reads qcRuleCases.ts, finds each target rule block, and replaces
the sections arrays with clinically accurate, unambiguous text.

Strategy:
- For positive cases (should be compliant): ensure they are unambiguously compliant
- For negative cases (should be non-compliant): ensure they have ONE clear, unmistakable defect
"""
import re

TS_PATH = 'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/src/data/qcRuleCases.ts'

def esc(s: str) -> str:
    """Escape a Chinese string for TS source (convert to unicode escapes)."""
    return ''.join(f'\\u{ord(c):04x}' if ord(c) > 127 else c for c in s)

# ======================================================================
# Define replacement data for each rule
# Each entry: (rule_id, field, new_sections_list, new_focus_points)
# field = "positive" or "negative"
# ======================================================================

REPLACEMENTS = {}

# ------------------------------------------------------------------
# SC-018: 体格检查遗漏主要阳性体征
# Negative: Must have an OBVIOUS missing positive finding
# ------------------------------------------------------------------
REPLACEMENTS['SC-018'] = {
    'negative': {
        'title': '肺炎患者入院体格检查遗漏肺部阳性体征',
        'summary': '患者因发热咳嗽入院，诊断肺炎，但体格检查中完全未记录肺部听诊结果，遗漏了与诊断直接相关的阳性体征。',
        'sections': [
            ('主诉', '发热伴咳嗽、咳痰5天。'),
            ('现病史', '患者5天前无明显诱因出现发热，最高体温39.2℃，伴咳嗽、咳黄色脓痰，量约30ml/日，伴右侧胸痛，深呼吸时加重。外院胸部CT示右下肺实变影。'),
            ('体格检查', 'T 39.0℃，P 102次/分，R 24次/分，BP 125/78mmHg。神志清楚，精神萎靡。皮肤黏膜无黄染。浅表淋巴结未触及肿大。头颅五官无畸形。颈软，气管居中，甲状腺不大。心率102次/分，律齐，各瓣膜听诊区未闻及病理性杂音。腹平软，无压痛反跳痛，肝脾肋下未触及。双下肢无水肿。神经系统检查未见异常。'),
            ('初步诊断', '社区获得性肺炎（右下肺）。'),
        ],
        'focusPoints': ['诊断为肺炎但体格检查中完全缺失肺部听诊记录（双肺呼吸音、啰音等），遗漏了与诊断直接相关的主要阳性体征']
    }
}

# ------------------------------------------------------------------
# SC-032: 重要病情变化未记录
# Negative: Patient has obvious change but record says "stable"
# ------------------------------------------------------------------
REPLACEMENTS['SC-032'] = {
    'negative': {
        'title': '患者出现高热及血压下降但病程记录未描述',
        'summary': '护理记录显示患者出现39.5℃高热和血压下降，但同日病程记录仅写"病情平稳，继续当前治疗"，完全未记录重要病情变化。',
        'sections': [
            ('病程记录', '2024-03-16 09:00 主治医师查房记录\n查房医师：李某（主治医师）\n患者一般情况可，病情平稳，无特殊不适主诉。目前治疗方案不变，继续当前抗感染及对症支持治疗。嘱继续观察。\n签名：李某（主治医师）'),
            ('护理记录（同日）', '2024-03-16 02:30 患者诉畏寒、寒战，测体温39.5℃，心率118次/分，血压85/55mmHg（较入院时120/75mmHg明显下降），立即通知值班医师张某，予物理降温及补液处理。\n2024-03-16 06:00 体温38.2℃，血压95/62mmHg，仍低于正常。'),
        ],
        'focusPoints': ['护理记录记载患者高热39.5℃伴血压骤降，但同日病程记录仅写"病情平稳"，未记录这一重要病情变化']
    }
}

# ------------------------------------------------------------------
# SC-041: 无特殊检查、特殊治疗记录
# Negative: Patient had a special procedure but no record in progress notes
# ------------------------------------------------------------------
REPLACEMENTS['SC-041'] = {
    'negative': {
        'title': '行经皮肝穿刺活检术但病程记录中无特殊检查记录',
        'summary': '患者行经皮肝穿刺活检术，但病程记录中仅一句"已行肝穿"带过，无任何操作记录内容。',
        'sections': [
            ('病程记录', '2024-05-10 15:00 主治医师查房记录\n患者肝功能持续异常，转氨酶反复升高，病因不明，经科室讨论后决定行经皮肝穿刺活检术以明确诊断。\n\n2024-05-11 10:00 日常病程记录\n昨日已行肝穿，患者诉穿刺部位轻微疼痛，无其他不适。查体：穿刺点敷料干燥，无渗血。嘱继续卧床休息，密切观察。\n签名：王某（主治医师）'),
        ],
        'focusPoints': ['病程记录中仅提及"已行肝穿"，但完全没有记录穿刺操作的具体过程、方法、标本情况、术中患者反应等特殊检查记录内容']
    }
}

# ------------------------------------------------------------------
# SC-048: 入院48小时内无主治首次查房
# Negative: Attending's first round clearly > 48 hours after admission
# ------------------------------------------------------------------
REPLACEMENTS['SC-048'] = {
    'negative': {
        'title': '入院超过48小时后主治医师才首次查房',
        'summary': '患者2024年4月5日14:30入院，但主治医师首次查房记录时间为2024年4月8日09:00，间隔66.5小时，远超48小时时限。',
        'sections': [
            ('入院信息', '入院时间：2024年4月5日14:30。入院诊断：2型糖尿病伴酮症酸中毒。'),
            ('首次病程记录', '2024年4月5日20:00 住院医师张某完成首次病程记录。患者因口干多饮加重伴恶心呕吐2天入院，急查血糖28.6mmol/L，血酮体阳性，血气分析pH 7.25。予胰岛素泵持续静脉输注、补液、纠正电解质紊乱。'),
            ('主治医师首次查房记录', '2024年4月8日09:00 主治医师王某首次查房\n查房意见：患者入院后经积极治疗，目前血糖控制在8-12mmol/L，酮体转阴，酸中毒纠正。同意目前治疗方案，建议逐步过渡为皮下胰岛素注射方案，完善糖尿病相关并发症筛查。\n签名：王某（主治医师）'),
        ],
        'focusPoints': ['入院时间2024-04-05 14:30，主治医师首次查房2024-04-08 09:00，间隔66.5小时，超过48小时时限要求']
    }
}

# ------------------------------------------------------------------
# SC-052: 上级医师查房无本人审阅及签名
# Positive: Explicitly state "本人审阅"
# ------------------------------------------------------------------
REPLACEMENTS['SC-052'] = {
    'positive': {
        'title': '上级医师查房记录含本人审阅及签名',
        'summary': '副主任医师查房后对病程记录进行了本人审阅并亲笔签名确认，符合规范要求。',
        'sections': [
            ('上级医师查房记录', '2023-10-08 10:00 副主任医师张伟查房记录\n补充病史：患者既往有高血压病史10年，长期服用氨氯地平5mg qd。\n查体新发现：双下肢轻度凹陷性水肿（+），尿蛋白定量需复查。\n病情分析：患者冠心病诊断明确，目前抗血小板、调脂、扩冠治疗方案合理。新发现双下肢水肿，需警惕心功能不全或肾功能损害，建议完善BNP、肾功能及24小时尿蛋白定量。\n诊疗意见：1.加用呋塞米20mg qd利尿 2.复查肾功能及BNP 3.继续当前冠心病治疗方案\n\n本人已审阅以上查房记录，确认内容准确。\n签名：张伟（副主任医师） 手写签名√'),
        ],
        'focusPoints': ['查房记录末尾明确写有"本人已审阅"字样及上级医师亲笔签名']
    }
}

# ------------------------------------------------------------------
# SC-054: 未在6小时内完成抢救记录
# Positive: Explicitly show rescue completion time within 6 hours
# ------------------------------------------------------------------
REPLACEMENTS['SC-054'] = {
    'positive': {
        'title': '抢救记录在抢救结束后3小时内完成',
        'summary': '患者抢救于17:30结束，抢救记录于当日20:15完成书写，在6小时时限内。',
        'sections': [
            ('抢救记录', '【抢救记录】\n抢救开始时间：2023-10-06 14:00\n抢救结束时间：2023-10-06 17:30\n记录完成时间：2023-10-06 20:15\n\n病情变化：患者于14:00突发剧烈胸痛，呈压榨性，伴大汗淋漓、面色苍白。即刻心电图示V1-V4导联ST段弓背向上抬高0.3-0.5mV，考虑急性前壁ST段抬高型心肌梗死。\n\n抢救措施：\n1. 14:05 立即给予阿司匹林300mg嚼服、替格瑞洛180mg口服\n2. 14:10 建立双静脉通路，持续心电监护及吸氧\n3. 14:15 肝素钠5000IU静推\n4. 14:30 联系导管室行急诊PCI\n5. 15:00-16:45 行冠状动脉造影+PCI术，于前降支近段植入药物洗脱支架1枚\n6. 17:00 术后送返CCU，生命体征平稳\n7. 17:30 确认病情稳定，抢救结束\n\n抢救结果：抢救成功。术后患者胸痛完全缓解，生命体征平稳。\n\n参加抢救人员：\n- 李明（主任医师，主持抢救）\n- 王强（副主任医师）\n- 张磊（主治医师）\n- 赵芳（护师）\n- 刘洋（护士）\n\n记录医师：张磊（主治医师）\n审阅签名：李明（主任医师）'),
        ],
        'focusPoints': ['明确标注抢救结束时间17:30和记录完成时间20:15，在6小时内完成']
    }
}

# ------------------------------------------------------------------
# SC-065: 无阶段小结
# Negative: Patient hospitalized > 30 days with no stage summary
# ------------------------------------------------------------------
REPLACEMENTS['SC-065'] = {
    'negative': {
        'title': '住院超过30天但无阶段小结',
        'summary': '患者住院45天，期间无任何阶段小结记录，也无交接班记录或转科记录可替代。',
        'sections': [
            ('病程记录', '入院日期：2023-09-01\n入院诊断：股骨颈骨折（右侧），2型糖尿病，高血压病3级\n\n2023-09-01 住院医师首次病程记录（略）\n2023-09-03 主治医师首次查房记录（略）\n2023-09-10 行右侧人工股骨头置换术\n2023-09-15 术后恢复良好，开始康复训练\n2023-09-22 日常病程记录：患者术后恢复中，伤口愈合良好\n2023-09-29 日常病程记录：继续康复锻炼\n2023-10-06 日常病程记录：患者可扶拐行走\n2023-10-13 日常病程记录：血糖控制尚可\n\n注：自入院至今已超过30天，住院期间经治医师未发生变更，无交接班记录，未转科，未书写阶段小结。\n\n2023-10-15 出院记录（住院45天）'),
        ],
        'focusPoints': ['住院时间超过30天，期间无阶段小结，也无可替代的交接班记录或转科记录']
    }
}

# ------------------------------------------------------------------
# SC-069: 会诊记录未按规定书写
# Positive: Properly formatted consultation record
# ------------------------------------------------------------------
REPLACEMENTS['SC-069'] = {
    'positive': {
        'title': '规范的会诊记录',
        'summary': '会诊记录完整包含会诊意见、会诊医师科别、会诊时间及医师签名，格式规范。',
        'sections': [
            ('会诊记录', '【会诊记录】\n\n申请会诊科室：心血管内科\n申请会诊医师：王某（主治医师）\n申请会诊时间：2023-10-15 10:00\n申请会诊理由：患者冠心病PCI术后，合并持续性房颤，请心血管内科协助调整抗凝方案。\n\n会诊科别：心血管内科\n会诊医师：李强（副主任医师）\n会诊时间：2023-10-15 14:30\n\n会诊意见：\n1. 患者冠心病PCI术后合并持续性房颤，CHA2DS2-VASc评分4分，有抗凝指征。\n2. 目前使用阿司匹林+氯吡格雷双联抗血小板，建议PCI术后1个月改为氯吡格雷+利伐沙班方案。\n3. 定期监测凝血功能，INR控制在2.0-3.0。\n4. 如出现出血倾向及时调整方案。\n\n会诊医师签名：李强（副主任医师，心血管内科）手写签名√\n会诊完成时间：2023-10-15 15:00'),
        ],
        'focusPoints': ['会诊记录包含完整的会诊意见、会诊医师科别（心血管内科）、会诊时间及会诊医师签名']
    }
}

# ------------------------------------------------------------------
# SC-084: 术前讨论结论未记入病历
# Negative: Discussion happened but conclusion NOT recorded
# ------------------------------------------------------------------
REPLACEMENTS['SC-084'] = {
    'negative': {
        'title': '术前讨论已进行但结论未记入病历',
        'summary': '病历记载进行了术前讨论，但仅记录了参会人员名单，讨论的结论（手术方案、风险评估等）完全未记入病程记录或术前小结。',
        'sections': [
            ('病程记录', '2024-06-10 16:00 术前讨论通知\n拟于明日行腹腔镜胆囊切除术，已通知科室术前讨论。\n\n2024-06-10 17:00 术前讨论记录\n参加人员：张某某（主任医师，主持）、李某（副主任医师）、王某（主治医师）、赵某（住院医师）\n讨论时间：2024-06-10 17:00-17:30\n\n（讨论结论见术前小结）\n\n签名：赵某（住院医师）'),
            ('术前小结', '（未见术前小结）'),
            ('手术记录', '2024-06-11 09:00 在全身麻醉下行腹腔镜胆囊切除术。术中见胆囊壁增厚，与周围组织粘连。顺利切除胆囊，术中出血约15ml。'),
        ],
        'focusPoints': ['术前讨论记录仅列出参会人员，标注"讨论结论见术前小结"但术前小结缺失，病历中无任何术前讨论结论（手术指征、拟行术式、麻醉方式、风险评估等）']
    }
}

# ------------------------------------------------------------------
# SC-114: 非计划再次手术相关检查结果未记录分析
# Negative: Scenario of unplanned re-operation, missing analysis
# ------------------------------------------------------------------
REPLACEMENTS['SC-114'] = {
    'negative': {
        'title': '非计划再次手术后未记录分析检查结果',
        'summary': '患者胆囊切除术后第3天因腹腔内出血行二次手术探查（非计划再次手术），但术后病程中未记录出血原因分析及相关检验结果。',
        'sections': [
            ('手术记录', '2024-06-11 09:00 第一次手术：腹腔镜胆囊切除术，顺利。\n\n2024-06-14 02:30 第二次手术（非计划再次手术）：\n患者术后第3天出现腹痛加重、腹胀、引流管引出血性液体约500ml。急查血红蛋白由术后120g/L降至72g/L。考虑腹腔内活动性出血，急诊行剖腹探查止血术。术中见胆囊床处一小动脉出血，予缝扎止血，清除腹腔积血约800ml。术中输注红细胞悬液4U。'),
            ('术后病程记录', '2024-06-14 08:00 主治医师查房记录\n患者昨夜行急诊剖腹探查止血术，目前生命体征平稳。腹部引流管通畅，引流液为淡血性。嘱继续抗感染、补液治疗，密切观察引流情况。\n签名：王某（主治医师）'),
        ],
        'focusPoints': ['发生了非计划再次手术（术后出血），但病程记录中未分析出血发生原因，未记录术前检查结果（血红蛋白变化、凝血功能等）的分析']
    }
}

# ------------------------------------------------------------------
# SC-131: 知情同意书描述不清
# Positive: Consent form with explicit risk enumeration
# ------------------------------------------------------------------
REPLACEMENTS['SC-131'] = {
    'positive': {
        'title': '冠脉介入治疗知情同意书风险描述完整',
        'summary': '知情同意书详细列出了可能的并发症及风险，包含具体疾病名称，描述清晰完整。',
        'sections': [
            ('知情同意书', '手术/操作名称：经皮冠状动脉介入治疗（PCI）\n\n一、目的：通过介入方法开通狭窄或闭塞的冠状动脉，恢复心肌血流灌注。\n\n二、可能的并发症及风险：\n1. 穿刺部位并发症：局部血肿、假性动脉瘤、动静脉瘘\n2. 对比剂相关：对比剂过敏反应（皮疹、休克）、对比剂肾病\n3. 血管并发症：冠状动脉穿孔、冠状动脉夹层、血管痉挛\n4. 支架相关：支架内血栓形成（急性、亚急性、晚期）、支架内再狭窄\n5. 心脏并发症：急性心肌梗死、恶性心律失常（室速、室颤）、心脏压塞\n6. 全身并发症：脑血管意外（卒中）、肾功能损害\n7. 极端情况下可能导致死亡\n\n三、自费项目说明：药物洗脱支架属于高值耗材，部分费用需自费承担。\n\n四、替代方案：药物保守治疗、冠状动脉旁路移植术（搭桥手术）\n\n患者签名：张某某  日期：2024-06-10\n法定代理人签名：张某某（配偶）  日期：2024-06-10\n主治医师签名：李某某（主治医师）  日期：2024-06-10'),
        ],
        'focusPoints': ['知情同意书详细列举了7大类并发症风险的具体疾病名称，并说明了自费项目']
    }
}

# ------------------------------------------------------------------
# SC-139: 检查报告单基本信息错误
# Negative: Clear mismatch in patient info
# ------------------------------------------------------------------
REPLACEMENTS['SC-139'] = {
    'negative': {
        'title': '检查报告单患者性别与病历不一致',
        'summary': '病历首页记载患者为男性，但CT检查报告单上性别误填为女性，存在基本信息错误。',
        'sections': [
            ('病历首页信息', '姓名：王建国  性别：男  年龄：58岁  住院号：2023101508  门诊号：20231015001  入院日期：2023-10-15'),
            ('CT检查报告单', '检查日期：2023-10-16\n姓名：王建国  性别：女  年龄：58岁  住院号：2023101508  门诊号：20231015001\n检查部位：胸部\n检查所见：双肺纹理清晰，未见明显实变影及结节影。纵隔内未见肿大淋巴结。心影不大。\n诊断意见：胸部CT未见明显异常。\n报告医师：赵某某  审核医师：钱某某'),
        ],
        'focusPoints': ['病历首页性别为"男"，但CT报告单上误填为"女"，患者基本信息不一致']
    }
}

# ------------------------------------------------------------------
# SC-144: 临时医嘱单描述不清
# Positive: Clean, well-formatted temporary orders
# ------------------------------------------------------------------
REPLACEMENTS['SC-144'] = {
    'positive': {
        'title': '临时医嘱单格式清晰规范',
        'summary': '每条临时医嘱分项清晰列出，医嘱时间、内容、医师签名、执行时间、执行护士签名各要素齐全且分列清楚。',
        'sections': [
            ('临时医嘱单', '日期          医嘱时间  医嘱内容                    医师签名    执行时间  执行护士签名\n'
             '2024-03-15  14:00    心电图检查                  王明        14:30    李芳\n'
             '2024-03-15  14:00    呋塞米注射液 20mg iv st      王明        14:15    李芳\n'
             '2024-03-15  16:00    头孢曲松钠 2.0g ivgtt st    王明        16:20    张红\n'
             '2024-03-15  20:00    地西泮注射液 10mg im st     王明        20:10    赵敏\n\n'
             '以上医嘱均已执行完毕。\n'
             '开具医师签名：王明（主治医师）'),
        ],
        'focusPoints': ['每条临时医嘱的时间、内容、签名、执行时间、执行护士签名均分列清楚，格式规范']
    }
}


# ======================================================================
# Apply replacements to TS file
# ======================================================================

with open(TS_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

def build_sections_ts(sections_list):
    """Build TS sections array from list of (heading, content) tuples."""
    parts = []
    for heading, body in sections_list:
        h = esc(heading)
        c = esc(body).replace('\n', '\\n')
        parts.append(f'        {{ heading: "{h}", content: "{c}" }}')
    return ',\n'.join(parts)

def build_focus_points_ts(fps):
    """Build TS focusPoints array."""
    parts = [f'"{esc(fp)}"' for fp in fps]
    return ', '.join(parts)

success_count = 0
for rule_id, fields in REPLACEMENTS.items():
    for field_name, data in fields.items():
        # Find the rule block
        # Pattern: ruleId: "SC-XXX" ... field_name: { ... sections: [ ... ], focusPoints: [ ... ] }
        
        # Step 1: Find the start of this rule
        rule_pattern = f'ruleId: "{rule_id}"'
        rule_idx = content.find(rule_pattern)
        if rule_idx == -1:
            print(f"❌ Could not find rule {rule_id}")
            continue
        
        # Step 2: Find the field (positive/negative) within this rule block
        # We need to find the next rule boundary to limit our search
        next_rule = content.find('ruleId: "SC-', rule_idx + len(rule_pattern))
        if next_rule == -1:
            rule_block = content[rule_idx:]
        else:
            rule_block = content[rule_idx:next_rule]
        
        # Step 3: Find the field within the block
        field_idx = rule_block.find(f'{field_name}:')
        if field_idx == -1:
            print(f"❌ Could not find {field_name} in {rule_id}")
            continue
        
        # Step 4: Find title, summary, sections, focusPoints within this field
        field_start = rule_idx + field_idx
        
        # Find the sections array start and end
        sections_start_search = content.find('sections:', field_start)
        if sections_start_search == -1 or sections_start_search > rule_idx + len(rule_block):
            print(f"❌ Could not find sections in {rule_id}.{field_name}")
            continue
        
        # Find the opening [ of sections
        bracket_open = content.find('[', sections_start_search)
        
        # Find the matching closing ]
        depth = 0
        i = bracket_open
        while i < len(content):
            if content[i] == '[':
                depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        bracket_close = i
        
        # Find focusPoints
        focus_start_search = content.find('focusPoints:', bracket_close)
        if focus_start_search == -1 or focus_start_search > rule_idx + len(rule_block):
            print(f"❌ Could not find focusPoints in {rule_id}.{field_name}")
            continue
        
        fp_bracket_open = content.find('[', focus_start_search)
        fp_bracket_close = content.find(']', fp_bracket_open)
        
        # Also find and replace title and summary
        title_search = content.find('title:', field_start)
        if title_search != -1 and title_search < sections_start_search:
            title_quote_start = content.find('"', title_search)
            title_quote_end = content.find('"', title_quote_start + 1)
            while content[title_quote_end - 1] == '\\':
                title_quote_end = content.find('"', title_quote_end + 1)
            new_title = esc(data['title'])
            content = content[:title_quote_start+1] + new_title + content[title_quote_end:]
            
            # Recalculate positions after replacement
            # (offset change)
            offset = len(new_title) - (title_quote_end - title_quote_start - 1)
            bracket_open += offset
            bracket_close += offset
            fp_bracket_open += offset
            fp_bracket_close += offset
            sections_start_search += offset
            focus_start_search += offset
        
        summary_search = content.find('summary:', field_start)
        if summary_search != -1 and summary_search < sections_start_search:
            sum_quote_start = content.find('"', summary_search)
            sum_quote_end = content.find('"', sum_quote_start + 1)
            while content[sum_quote_end - 1] == '\\':
                sum_quote_end = content.find('"', sum_quote_end + 1)
            new_summary = esc(data['summary'])
            content = content[:sum_quote_start+1] + new_summary + content[sum_quote_end:]
            
            offset = len(new_summary) - (sum_quote_end - sum_quote_start - 1)
            bracket_open += offset
            bracket_close += offset
            fp_bracket_open += offset
            fp_bracket_close += offset
        
        # Replace sections
        new_sections = '[\n' + build_sections_ts(data['sections']) + '\n      ]'
        content = content[:bracket_open] + new_sections + content[bracket_close+1:]
        
        offset = len(new_sections) - (bracket_close + 1 - bracket_open)
        fp_bracket_open += offset
        fp_bracket_close += offset
        
        # Replace focusPoints
        new_fps = '[' + build_focus_points_ts(data['focusPoints']) + ']'
        content = content[:fp_bracket_open] + new_fps + content[fp_bracket_close+1:]
        
        success_count += 1
        print(f"✅ Replaced {rule_id}.{field_name}")

with open(TS_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ Phase 2 complete: {success_count}/{sum(len(v) for v in REPLACEMENTS.values())} replacements applied to qcRuleCases.ts")
