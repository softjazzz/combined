import re

filepath = 'src/data/customRuleCases.ts'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace positive example
content = content.replace(
    '手术开始时间：10:40，手术结束时间：12:15。',
    '手术开始时间：2023年10月15日10:40，手术结束时间：2023年10月15日12:15。'
)

# Replace negative example
content = content.replace(
    '手术开始时间08:50，结束时间09:40。',
    '手术开始时间2023年10月18日08:50，结束时间2023年10月18日09:40。'
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Dates supplemented.")
