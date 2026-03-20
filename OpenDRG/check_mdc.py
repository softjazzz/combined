"""生成 CCE 值(ADRG序号) → ADRG编码 的映射表"""
import json

# 加载 drg_groups 获取 ADRG 列表（按顺序）
drg = json.load(open(r'OpenDRG\extracted_rules\province\sichuan_2024\drg_groups.json', 'r', encoding='utf-8'))
adrgs = list(drg.keys())
print(f'共 {len(adrgs)} 个 ADRG')

# 加载 CCE 数据
cce = json.load(open(r'OpenDRG\extracted_rules\province\sichuan_2024\cce_icd_to_mdc.json', 'r', encoding='utf-8'))
cce_vals = sorted(set(cce.values()), key=int)
print(f'CCE 值范围: {cce_vals[0]}~{cce_vals[-1]}, 共 {len(cce_vals)} 个唯一值')

# 推断映射：CCE 值是 1-based 索引到 ADRG 列表中
# 但 ADRG 有 252 个，CCE 值只到 211，所以不是所有 ADRG 都在 CCE 中
# 可能是：一个 CCE 值对应一个 ADRG（前 211 个）

# 验证：K80.501(胆总管结石) → CCE值113 → 第113个ADRG
if len(adrgs) >= 113:
    print(f'\n验证: K80.501 -> CCE值113 -> ADRG[112] = {adrgs[112]}')
    # K80.501 是胆总管结石，应该在 MDC G (肝胆胰) 下
    # 看看第113个 ADRG 是否以 G 开头（MDC G）
    print(f'  该 ADRG 以 {adrgs[112][0]} 开头 -> MDC {adrgs[112][0]}')

# 打印前 20 个映射
print('\n前 20 个 ADRG 映射:')
for i, adrg in enumerate(adrgs[:20]):
    print(f'  CCE值={i+1} -> ADRG={adrg}')

# 验证几个已知编码
test_codes = {
    'A00.000x001': '1',   # 应该是 MDC A 下的某 ADRG
    'K80.501': '113',     # 应该是 MDC G 下的某 ADRG
}
print('\n验证已知编码:')
for icd, val in test_codes.items():
    idx = int(val) - 1
    if idx < len(adrgs):
        print(f'  {icd} -> CCE值={val} -> ADRG={adrgs[idx]} (MDC {adrgs[idx][0]})')

# 生成完整映射表
mapping = {}
for i, adrg in enumerate(adrgs):
    mapping[str(i + 1)] = adrg

# 保存映射表
output_path = r'apps\medqc-web\public\drg-rules\sichuan_2024\cce_index_to_adrg.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)
print(f'\n映射表已保存到 {output_path}')
print(f'共 {len(mapping)} 条映射')
