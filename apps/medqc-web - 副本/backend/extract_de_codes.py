"""提取 HTML 模板中所有 DE code"""
import re
with open(r'd:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\src\assets\templates\hm-frontpage\inpatient_record.html', 'r', encoding='utf-8') as f:
    html = f.read()

codes = re.findall(r'data-hm-code="([^"]+)"', html)
for c in sorted(set(codes)):
    # 找到对应的 data-hm-name
    pattern = f'data-hm-code="{re.escape(c)}"[^>]*data-hm-name="([^"]*)"'
    m = re.search(pattern, html)
    name = m.group(1) if m else ''
    # 也查反序
    if not name:
        pattern2 = f'data-hm-name="([^"]*)"[^>]*data-hm-code="{re.escape(c)}"'
        m2 = re.search(pattern2, html)
        name = m2.group(1) if m2 else ''
    print(f"  {c:40s} {name}")
