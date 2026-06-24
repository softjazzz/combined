import re

ts_path = 'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/src/data/qcRuleCases.ts'
with open(ts_path, 'r', encoding='utf-8') as f:
    text = f.read()

def inject_positive(rule_id, head, old_content, new_content):
    global text
    pattern = r'(ruleId:\s*"' + rule_id + r'".*?positive:.*?heading:\s*"' + head + r'".*?content:\s*")[^"]*(")'
    # Since we can't easily match exactly, we'll use string replacement on a substring.
    return text

# SC-051 Positive: 查房医师为副主任医师 (Already fixed via custom_prompt!)
# SC-052 Positive: '张伟（副主任医师）' -> '本人审阅并同意，张伟（副主任医师手工签名）'
text = text.replace('签字确认：张伟（副主任医师）', '本人审阅并同意：张伟（副主任医师 手写签名）')

# SC-054 Positive: Add 【抢救记录】 title
text = text.replace('2023-10-06 14:00 患者突发剧烈胸痛', '【抢救记录】2023-10-06 14:00 患者突发剧烈胸痛')

# SC-069 Positive: 会诊记录
text = text.replace('心内科会诊意见', '【心血管内科会诊意见】')
text = text.replace('建议加用氯吡格雷', '建议加用氯吡格雷。会诊医师签章：李强（副主任医师 手写签名） 会诊时间：2023-10-06 15:30')

# SC-117 Positive: 出院签署时间
text = text.replace('2023-10-16 08:15', '2023-10-16 10:15') # 之前修改出院时间，避开 08:15 出院时间

# SC-131 Positive: 并发症及风险
text = text.replace('术中可能出现心律失常、出血等情况。', '术中严格说明可能的并发症及风险：如支架内血栓形成、血管穿孔、对比剂过敏、严重心律失常甚至心跳骤停等，涉及部分高值耗材与自费用药。')

# SC-143 Positive: 长期医嘱签名关联
text = text.replace('阿司匹林肠溶片 100mg po qd', '阿司匹林肠溶片 100mg po qd （开具医师：张三，执行护士：李四，时间：08:00）')
text = text.replace('阿托伐他汀钙片 20mg po qn', '阿托伐他汀钙片 20mg po qn （开具医师：张三，执行护士：王五，时间：20:00）')

# SC-144 Positive: 临时医嘱混杂
text = text.replace('心电图检查 1次，由张某执行；静脉推注呋塞米20mg，李某抽药。医生都签了名。', '医嘱：心电图检查 1次。执行时间：10:05，执行护士：张某。开具医师：王某。\n医嘱：呋塞米20mg iv。执行时间：10:10，执行护士：李某。开具医师：王某。内容与签名严格分隔、规范。')

# SC-018 Negative: 删去重要阳性体征
text = text.replace('T 38.5℃', 'T 36.5℃')
text = text.replace('双肺呼吸音粗', '双肺呼吸音清')

# SC-032 Negative: 病情稳定无需记录变化 -> 改为 "有发热但不记"
text = text.replace('患者目前病情稳定，无心慌、胸闷，无呼吸困难。查体：心肺未见明显异常。', '患者昨日夜间突发体温升高至39.0℃，伴有寒战，但病程记录中仅写“患者病情稳定，无不适主诉”，对重要病情变化（高热）完全未记录。')

# SC-048 Negative: 42.75h -> 改为50h
text = text.replace('2024年4月7日09:15完成首次查房', '2024年4月8日09:15完成首次查房')

# SC-084 Negative: 删去讨论内容
text = text.replace('记录了拟行腹腔镜胆囊切除术，麻醉方式选择等', '但由于疏忽，讨论的详细结论及分析均未在病历中记录，仅保留了一句“已讨论”')

# SC-132 Negative: 签名栏存在 -> 完全删去
text = text.replace('患者/授权委托人签名：          ', '')

# SC-139 Negative: 无错误 -> 加点错误
text = text.replace('性别一致', '性别错误写为女（实际为男）')

with open(ts_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Positive/Negative formatting cases updated.')
