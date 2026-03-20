"""
对比四川 DRG 2024 vs 2025 的差异
1. 从 PDF 提取 2025 DRG 目录
2. 从 2024 chunk 提取 DRG 列表
3. 对比差异
"""
import pdfplumber, json, re, sys
sys.stdout.reconfigure(encoding='utf-8')

# === 1. 提取 2025 PDF 中的 DRG 列表 ===
pdf_path = r'D:\大模型项目\lx0222\health-qc-monorepo\docs\四川省按病组（DRG）付费分组目录 2025.pdf'
drg_2025 = {}
adrg_2025 = {}

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                if not row or len(row) < 7:
                    continue
                # 序号, MDC编码, MDC名称, ADRG编码, ADRG名称, DRG编码, DRG名称
                seq, mdc_code, mdc_name, adrg_code, adrg_name, drg_code, drg_name = row[:7]
                if drg_code and re.match(r'^[A-Z]{2}\d', drg_code):
                    drg_2025[drg_code] = {
                        'mdc': mdc_code or '',
                        'mdc_name': mdc_name or '',
                        'adrg': adrg_code or '',
                        'adrg_name': adrg_name or '',
                        'drg_name': drg_name or '',
                    }
                    if adrg_code and re.match(r'^[A-Z]{2}\d', adrg_code):
                        adrg_2025[adrg_code] = adrg_name or ''

print(f'2025 PDF: {len(drg_2025)} DRG, {len(adrg_2025)} ADRG')

# === 2. 从 2024 chunk 提取 DRG 列表 ===
# drg_groups.json 的结构: { "ADRG": { "DRG_CODE": { "suffix": "...", "condition": "..." } } }
with open(r'OpenDRG\extracted_rules\province\sichuan_2024\drg_groups.json', 'r', encoding='utf-8') as f:
    groups_2024 = json.load(f)

drg_2024 = set()
adrg_2024 = set()
for adrg, drgs in groups_2024.items():
    adrg_2024.add(adrg)
    for drg_code in drgs:
        drg_2024.add(drg_code)

print(f'2024 chunk: {len(drg_2024)} DRG, {len(adrg_2024)} ADRG')

# === 3. 对比 ===
drg_2025_set = set(drg_2025.keys())

# 新增的 DRG
added = drg_2025_set - drg_2024
removed = drg_2024 - drg_2025_set
common = drg_2025_set & drg_2024

print(f'\n=== DRG 对比 ===')
print(f'共同: {len(common)}')
print(f'2025 新增: {len(added)}')
print(f'2024 有但 2025 没有: {len(removed)}')

if added:
    print(f'\n新增 DRG:')
    for code in sorted(added)[:30]:
        info = drg_2025[code]
        print(f'  {code}: {info["drg_name"]} (ADRG: {info["adrg"]}, MDC: {info["mdc"]})')
    if len(added) > 30:
        print(f'  ... 共 {len(added)} 个')

if removed:
    print(f'\n移除 DRG:')
    for code in sorted(removed)[:30]:
        print(f'  {code}')
    if len(removed) > 30:
        print(f'  ... 共 {len(removed)} 个')

# ADRG 对比
adrg_2025_set = set(adrg_2025.keys())
adrg_added = adrg_2025_set - adrg_2024
adrg_removed = adrg_2024 - adrg_2025_set
print(f'\n=== ADRG 对比 ===')
print(f'共同: {len(adrg_2025_set & adrg_2024)}')
print(f'新增: {len(adrg_added)}: {sorted(adrg_added)[:20]}')
print(f'移除: {len(adrg_removed)}: {sorted(adrg_removed)[:20]}')

# 结论
print(f'\n=== 结论 ===')
change_rate = (len(added) + len(removed)) / max(len(drg_2024), len(drg_2025_set)) * 100
print(f'DRG 变化率: {change_rate:.1f}%')
if change_rate < 20:
    print('变化较小，可以考虑: 2024 引擎 + 2025 目录覆盖')
else:
    print('变化较大，需要更完整的数据')
