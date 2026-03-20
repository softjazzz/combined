import pdfplumber, sys, re
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r'D:\大模型项目\lx0222\health-qc-monorepo\docs\四川省按病组（DRG）付费分组目录 2025.pdf'
with pdfplumber.open(pdf_path) as pdf:
    all_text = ''
    for page in pdf.pages:
        t = page.extract_text()
        if t: all_text += t + '\n'
    
    drg_codes = set(re.findall(r'\b([A-Z]{2}\d{2})\b', all_text))
    adrg_codes = set(re.findall(r'\b([A-Z]{2}\d)\b', all_text))
    mdc_codes = set(re.findall(r'\bMDC([A-Z])\b', all_text))
    
    print(f'MDC 数量: {len(mdc_codes)}: {sorted(mdc_codes)}')
    print(f'ADRG 数量: {len(adrg_codes)}')
    print(f'DRG 数量: {len(drg_codes)}')
    
    icd_pattern = re.findall(r'[A-Z]\d{2}\.\d', all_text)
    print(f'ICD 编码出现次数: {len(icd_pattern)}')
    
    proc_pattern = re.findall(r'\d{2}\.\d{4}', all_text)
    print(f'手术编码出现次数: {len(proc_pattern)}')
    
    for pg in [9, 19, 25]:
        text = pdf.pages[pg].extract_text()
        if text:
            print(f'\n=== 第{pg+1}页(采样) ===')
            for line in text.strip().split('\n')[:8]:
                print(line)
    
    keywords = ['MCC', 'CC', '严重合并症', '并发症', '手术', 'ICD', '诊断编码', '操作编码', '主要诊断']
    print('\n=== 关键词统计 ===')
    for kw in keywords:
        count = all_text.count(kw)
        if count > 0:
            print(f'  "{kw}" 出现 {count} 次')
