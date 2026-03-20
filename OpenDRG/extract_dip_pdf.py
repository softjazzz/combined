"""
深度分析四川 DIP 病种库：
1. 统计病种数量
2. 分析编码格式  
3. 统计有/无手术操作的比例
4. 查看是否有分值信息
5. 生成 DIP 编码（诊断+手术组合）
"""
import pdfplumber, sys, json
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r'D:\大模型项目\lx0222\health-qc-monorepo\docs\四川省按病种分值（DIP）付费病种库.pdf'

all_rows = []
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                # 跳过表头
                if row[0] == '序号':
                    continue
                all_rows.append(row)

print(f"总病种数: {len(all_rows)}")

# 清洗数据
records = []
for row in all_rows:
    seq = row[0].strip() if row[0] else ''
    zd_code = row[1].strip().replace('\n', '') if row[1] else ''
    zd_name = row[2].strip().replace('\n', '') if row[2] else ''
    ss_code = row[3].strip().replace('\n', '') if row[3] else '-'
    ss_name = row[4].strip().replace('\n', '') if row[4] else '-'
    rel_ss_code = row[5].strip().replace('\n', '') if row[5] else '-'
    rel_ss_name = row[6].strip().replace('\n', '') if row[6] else '-'
    
    records.append({
        'seq': seq,
        'zd_code': zd_code,
        'zd_name': zd_name,
        'ss_code': ss_code,
        'ss_name': ss_name,
        'rel_ss_code': rel_ss_code,
        'rel_ss_name': rel_ss_name,
    })

# 统计
no_surgery = [r for r in records if r['ss_code'] == '-']
with_surgery = [r for r in records if r['ss_code'] != '-']
with_rel_surgery = [r for r in records if r['rel_ss_code'] != '-']

print(f"无手术操作病种: {len(no_surgery)}")
print(f"有手术操作病种: {len(with_surgery)}")
print(f"有相关手术操作: {len(with_rel_surgery)}")

# 统计唯一诊断编码数
unique_zd = set(r['zd_code'] for r in records)
unique_ss = set(r['ss_code'] for r in records if r['ss_code'] != '-')
print(f"唯一诊断编码数: {len(unique_zd)}")
print(f"唯一手术操作编码数: {len(unique_ss)}")

# 诊断编码格式示例
print("\n=== 诊断编码格式示例 ===")
zd_samples = sorted(list(unique_zd))[:20]
for code in zd_samples:
    print(f"  {code}")

# 手术编码格式示例
print("\n=== 手术编码格式示例 ===")
ss_samples = sorted(list(unique_ss))[:20]
for code in ss_samples:
    print(f"  {code}")

# 有相关手术的示例
print("\n=== 有相关手术操作的示例 ===")
for r in with_rel_surgery[:10]:
    print(f"  {r['zd_code']} + {r['ss_code']} + 相关:{r['rel_ss_code']} ({r['rel_ss_name']})")

# 生成 DIP 编码
print("\n=== DIP 编码生成分析 ===")
# DIP 编码通常是 主诊断编码 + 主手术编码 的组合
# 例如: A01.0 + - = "A01.0-" (纯诊断)
#       A15.6 + 34.2000 = "A15.6+34.2000" (诊断+手术)
dip_codes = set()
for r in records:
    if r['ss_code'] == '-':
        dip_code = r['zd_code']
    else:
        dip_code = f"{r['zd_code']}+{r['ss_code']}"
    dip_codes.add(dip_code)

print(f"唯一 DIP 编码数: {len(dip_codes)}")

# 检查是否有分值信息
print("\n=== 注意：PDF 中是否包含分值？ ===")
print("当前表格列: 序号, 主要诊断代码, 主要诊断名称, 主要手术操作代码, 主要手术操作名称, 相关手术操作代码, 相关手术操作名称")
print(">>> PDF 中不包含分值!!! DIP 分组只有病种目录，分值需要从 OpenDIP 引擎中获取 <<<")

# 保存为 JSON 供后续使用
with open(r'D:\大模型项目\lx0222\health-qc-monorepo\OpenDRG\sichuan_dip_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
print(f"\n已保存到 sichuan_dip_catalog.json ({len(records)} 条)")
