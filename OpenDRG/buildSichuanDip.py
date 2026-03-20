"""
将四川 DIP 病种库 JSON 转换为 TypeScript 可用的分组数据
输出: sichuanDipData.ts — 包含 DIP 病种查找表
"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

# 读取 PDF 提取的数据
with open(r'D:\大模型项目\lx0222\health-qc-monorepo\OpenDRG\sichuan_dip_catalog.json', 'r', encoding='utf-8') as f:
    records = json.load(f)

print(f"读取 {len(records)} 条记录")

# 构建三种查找表
# 1. 纯诊断 → DIP (无手术操作)
#    key: 主诊断编码, value: { name: 病种名, seq: 序号 }
zd_only = {}

# 2. 诊断+手术 → DIP
#    key: "主诊断编码|主手术编码", value: { name: 病种名, seq: 序号 }  
zd_ss = {}

# 3. 诊断+手术+相关手术 → DIP (最精确匹配)
#    key: "主诊断编码|主手术编码|相关手术编码", value: { name: 病种名, seq: 序号 }
zd_ss_rel = {}

# 4. DIP 编码 → 病种完整信息
dip_info = {}

for r in records:
    zd_code = r['zd_code'].strip()
    zd_name = r['zd_name'].strip()
    ss_code = r['ss_code'].strip()
    ss_name = r['ss_name'].strip()
    rel_ss_code = r['rel_ss_code'].strip()
    rel_ss_name = r['rel_ss_name'].strip()
    seq = r['seq'].strip()
    
    if ss_code == '-' or ss_code == '':
        # 纯诊断病种
        dip_code = zd_code
        zd_only[zd_code] = {
            'name': zd_name,
            'seq': seq
        }
    elif rel_ss_code != '-' and rel_ss_code != '':
        # 有相关手术
        dip_code = f"{zd_code}+{ss_code}"
        key = f"{zd_code}|{ss_code}|{rel_ss_code}"
        zd_ss_rel[key] = {
            'name': f"{zd_name}+{ss_name}+{rel_ss_name}",
            'seq': seq,
            'dip': dip_code,
            'rel_ss_code': rel_ss_code,
            'rel_ss_name': rel_ss_name
        }
        # 同时也在普通诊断+手术表中注册
        key2 = f"{zd_code}|{ss_code}"
        if key2 not in zd_ss:
            zd_ss[key2] = {
                'name': f"{zd_name}+{ss_name}",
                'seq': seq
            }
    else:
        # 诊断+手术
        dip_code = f"{zd_code}+{ss_code}"
        key = f"{zd_code}|{ss_code}"
        zd_ss[key] = {
            'name': f"{zd_name}+{ss_name}",
            'seq': seq
        }
    
    # 记录完整信息
    dip_info[dip_code] = {
        'zd_code': zd_code,
        'zd_name': zd_name,
        'ss_code': ss_code if ss_code != '-' else '',
        'ss_name': ss_name if ss_name != '-' else '',
        'rel_ss_code': rel_ss_code if rel_ss_code != '-' else '',
        'rel_ss_name': rel_ss_name if rel_ss_name != '-' else '',
    }

print(f"纯诊断条目: {len(zd_only)}")
print(f"诊断+手术条目: {len(zd_ss)}")
print(f"诊断+手术+相关手术条目: {len(zd_ss_rel)}")
print(f"DIP 信息总条目: {len(dip_info)}")

# 生成 TypeScript 文件
output_path = r'D:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\src\views\drg-grouper\sichuanDipData.ts'

with open(output_path, 'w', encoding='utf-8') as f:
    f.write('/**\n')
    f.write(' * 四川省 DIP 病种库数据\n')
    f.write(' * 来源：四川省按病种分值（DIP）付费病种库 PDF\n')
    f.write(f' * 总病种数：{len(records)} 条\n')
    f.write(f' * 生成时间：自动生成\n')
    f.write(' */\n\n')
    
    # 1. 纯诊断映射表 — key: 诊断编码, value: 病种名称
    f.write('/** 纯诊断 → 病种名称（无手术操作的病种） */\n')
    f.write('export const ZD_ONLY_MAP: Record<string, string> = {\n')
    for code in sorted(zd_only.keys()):
        name = zd_only[code]['name'].replace("'", "\\'")
        f.write(f"  '{code}': '{name}',\n")
    f.write('};\n\n')
    
    # 2. 诊断+手术映射表 — key: "诊断|手术", value: 病种名称
    f.write('/** 诊断+手术 → 病种名称 (key格式: "诊断编码|手术编码") */\n')
    f.write('export const ZD_SS_MAP: Record<string, string> = {\n')
    for key in sorted(zd_ss.keys()):
        name = zd_ss[key]['name'].replace("'", "\\'")
        f.write(f"  '{key}': '{name}',\n")
    f.write('};\n\n')
    
    # 3. 含相关手术映射表
    f.write('/** 诊断+手术+相关手术 → 病种名称 (key格式: "诊断编码|手术编码|相关手术编码") */\n')
    f.write('export const ZD_SS_REL_MAP: Record<string, string> = {\n')
    for key in sorted(zd_ss_rel.keys()):
        info = zd_ss_rel[key]
        name = info['name'].replace("'", "\\'")
        f.write(f"  '{key}': '{name}',\n")
    f.write('};\n\n')
    
    # 4. 所有有效诊断编码集合（用于快速验证）
    all_zd_codes = sorted(set(r['zd_code'] for r in records))
    f.write('/** 所有有效的主诊断编码 */\n')
    f.write('export const VALID_ZD_CODES: Set<string> = new Set([\n')
    for code in all_zd_codes:
        f.write(f"  '{code}',\n")
    f.write(']);\n\n')
    
    # 5. 诊断编码 → 诊断名称
    zd_names = {}
    for r in records:
        zd_names[r['zd_code']] = r['zd_name']
    f.write('/** 诊断编码 → 诊断名称 */\n')
    f.write('export const ZD_NAMES: Record<string, string> = {\n')
    for code in sorted(zd_names.keys()):
        name = zd_names[code].replace("'", "\\'")
        f.write(f"  '{code}': '{name}',\n")
    f.write('};\n')

print(f"\n已生成: {output_path}")

# 统计文件大小
import os
size = os.path.getsize(output_path)
print(f"文件大小: {size / 1024:.1f} KB")
