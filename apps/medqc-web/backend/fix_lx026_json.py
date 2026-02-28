"""直接修改 lx_cases_extracted.json 中 LX-026 的时间数据，补充完整日期"""
import json

filepath = 'lx_cases_extracted.json'
cases = json.load(open(filepath, 'r', encoding='utf-8'))

for c in cases:
    if c['ruleId'] == 'LX-026':
        # 正例: 补充手术开始/结束时间的日期
        pos = c['positive_example']
        pos = pos.replace('手术开始时间：10:40，手术结束时间：12:15', 
                          '手术开始时间：2023年10月15日10:40，手术结束时间：2023年10月15日12:15')
        c['positive_example'] = pos
        
        # 反例: 补充手术开始/结束时间的日期
        neg = c['negative_example']
        neg = neg.replace('手术开始时间08:50，结束时间09:40',
                          '手术开始时间2023年10月18日08:50，手术结束时间2023年10月18日09:40')
        c['negative_example'] = neg
        
        print("正例修改后片段:", c['positive_example'][100:200])
        print("反例修改后片段:", c['negative_example'][50:150])
        break

json.dump(cases, open(filepath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print("\nlx_cases_extracted.json 已更新")
