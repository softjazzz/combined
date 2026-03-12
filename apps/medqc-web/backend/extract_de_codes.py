"""完整列出 HTML 模板中所有 DE 编码和对应标签"""
import re

html_path = r"d:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\src\assets\templates\hm-frontpage\inpatient_record.html"
with open(html_path, encoding='utf-8') as f:
    content = f.read()

# 提取所有 data-hm-code
all_codes = re.findall(r'data-hm-code="([^"]+)"', content)
unique_codes = sorted(set(all_codes))
print(f"总共 {len(unique_codes)} 个唯一 DE 编码\n")

for code in unique_codes:
    idx = content.find(f'data-hm-code="{code}"')
    # 向前搜索最近的中文标签
    before = content[max(0, idx-300):idx]
    after = content[idx:min(len(content), idx+300)]
    
    # 提取标签：通常在 span 的前一个 td 里
    before_chinese = re.findall(r'[\u4e00-\u9fff（）/]+', before)
    after_chinese = re.findall(r'[\u4e00-\u9fff（）/]+', after)
    
    label = before_chinese[-1] if before_chinese else ''
    print(f"{code:40s} ← {label}")
