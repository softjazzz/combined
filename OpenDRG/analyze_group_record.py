"""
从 OpenDRG 的 group_record 函数中提取完整的 ADRG 匹配规则
每个 ADRG 有对应的手术编码列表和匹配条件
"""
import re, json

# 读取四川方案 chunk 文件
with open('OpenDRG/opendrg.github.io/2002.js', 'r', encoding='utf-8') as f:
    content = f.read()

print(f'文件大小: {len(content)/1024:.0f} KB')

# 提取 ADRG 匹配规则
# 模式1: x.ssList[0] in [...] 或 includes(x.ssList[0])
# 例如: x.ssList.length>0&&["33.6x00"].includes(x.ssList[0])?"
# 对应 ADRG AA1, 然后检查 AA19_group
adrg_rules = {}

# 提取形如: x.ssList.length>0&&["code1","code2"].includes(x.ssList[0])
# 后面跟着 (new Q).XX19_group 或类似
pattern = r'\["([\d\.x,\"]+)"\]\.includes\(x\.ssList\[0\]\).*?\(new Q\)\.(\w{2}\d{2})_group'
matches = re.findall(pattern, content)
print(f'找到 {len(matches)} 个单列表匹配规则')

# 更完整的提取: 找到所有 ADRG 的手术编码映射
# 模式: 找到 "尝试XX" 后面的编码列表
adrg_pattern = r'D\("[^"]*?(\w{2}\d?).*?"\).*?(\[.*?\])\.includes\(x\.ssList\[0\]\).*?\(new Q\)\.(\w{2}\d{2})_group'

# 更简单的方式：直接找所有 XX_group 函数调用和前面的编码列表
# 格式: ["code1","code2",...].includes(x.ssList[0])?(D(...),...(new Q).ADRG_group(x)?"ADRG":"")
simple_pattern = r'\["((?:[\d\.x]+(?:",")?)*)"\]\.includes\(x\.ssList\[0\]\).*?\(new Q\)\.(\w{4})_group\(x\)\?["\'](\w{4})["\']'
matches2 = re.findall(simple_pattern, content)
print(f'简单模式找到 {len(matches2)} 个匹配')

# 更通用的方法：找所有 XXYY_group 调用，然后向前搜索最近的编码列表
# 步骤1：找到所有 ADRG_group 调用位置
group_calls = [(m.start(), m.group(1)) for m in re.finditer(r'\(new Q\)\.(\w{4})_group', content)]
print(f'\n找到 {len(group_calls)} 个 _group 调用')

# 步骤2：对每个调用，向前搜索最近的编码列表
for pos, drg_code in group_calls[:5]:
    # 向前 300 字符中找编码列表
    snippet = content[max(0, pos-300):pos]
    codes = re.findall(r'"([\d\.x]+)"', snippet)
    adrg = drg_code[:2]
    print(f'  {drg_code}: 前置编码 = {codes[:10]}')

# 另一种方法: 直接看函数中的 switch/case 或 if/else 结构
# 找到所有 MDC 分支
print('\n=== 尝试完整提取 ===')

# 找到所有 ADRG 和它们的手术编码
# 从 group_record 函数中提取  
# 格式通常是: 
# function(x){return x.ssList.length>0&&["code1","code2",...].includes(x.ssList[0])?(检查):""}
# 或带有 K(x.ssList, ["code1","code2",...]) 的双条件匹配

all_rules = {}
# 扫描每个 ADRG_group 调用，提取对应的手术编码
for pos, drg_code in group_calls:
    adrg = drg_code[:2]
    # 向前搜索（最多600字符）
    start = max(0, pos - 600)
    snippet = content[start:pos]
    
    # 提取手术编码列表
    code_lists = re.findall(r'\["((?:[\d\.x]+(?:",")?)+)"\]', snippet)
    
    # 取最后一个（最近的）编码列表
    codes = []
    for cl in code_lists:
        codes = [c.strip('"') for c in cl.split('","')]
    
    if codes:
        if adrg not in all_rules:
            all_rules[adrg] = {}
        all_rules[adrg][drg_code] = codes

print(f'提取了 {len(all_rules)} 个 ADRG 的手术编码规则')

# 保存
with open('OpenDRG/extracted_rules/province/sichuan_2024/adrg_procedure_rules.json', 'w', encoding='utf-8') as f:
    json.dump(all_rules, f, ensure_ascii=False, indent=2)

# 打印摘要
print('\nADRG 手术编码规则摘要:')
for adrg in sorted(all_rules.keys())[:20]:
    drg_codes = list(all_rules[adrg].keys())
    proc_count = sum(len(v) for v in all_rules[adrg].values())
    print(f'  {adrg}: {len(drg_codes)} 个 DRG, {proc_count} 个手术编码')

# 查看 GY 对应的规则 (K80.501 应该入 GY)
for adrg in ['GY', 'GA', 'GB', 'GC', 'GD']:
    if adrg in all_rules:
        for drg, codes in all_rules[adrg].items():
            print(f'\n{drg}: {codes[:20]}')
