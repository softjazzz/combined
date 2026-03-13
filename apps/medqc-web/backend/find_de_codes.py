"""从 HTML 模板提取地址相关 DE 编码"""
import re

with open(r'd:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\src\assets\templates\hm-frontpage\inpatient_record.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 找所有带 data-hm-code 的元素，提取 code 和 name
elements = re.findall(r'<[^>]+data-hm-code="([^"]+)"[^>]*data-hm-name="([^"]+)"[^>]*/?>|<[^>]+data-hm-name="([^"]+)"[^>]*data-hm-code="([^"]+)"[^>]*/?>', html)

# 整理结果
results = {}
for m in elements:
    if m[0]:  # code 在前
        results[m[0]] = m[1]
    elif m[3]:  # name 在前
        results[m[3]] = m[0] or m[2]

# 关键字搜索
keywords = ['出生地', '籍贯', '户口', '工作单位', '邮编', '现住', '联系人地址', '联系人电话',
            '联系人关系', '机构名称', '机构代码', '医疗机构', '组织机构']

print("=== 地址/机构相关 DE 编码 ===")
for code, name in sorted(results.items()):
    for kw in keywords:
        if kw in name:
            print(f"  {code:40s}  {name}")
            break

print(f"\n总计找到 {len(results)} 个元素")

# 也打印所有以 DE02 开头的（患者信息相关）
print("\n=== DE02 系列（患者信息）===")
for code, name in sorted(results.items()):
    if code.startswith('DE02'):
        print(f"  {code:40s}  {name}")
