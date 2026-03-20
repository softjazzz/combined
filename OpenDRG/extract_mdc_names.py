import pdfplumber, sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r'D:\大模型项目\lx0222\health-qc-monorepo\docs\四川省按病组（DRG）付费分组目录 2025.pdf'
mdc_map = {}
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                if not row or len(row) < 3:
                    continue
                mdc_code = (row[1] or '').strip()
                mdc_name = (row[2] or '').strip()
                if mdc_code.startswith('MDC') and len(mdc_code) == 4 and mdc_name:
                    letter = mdc_code[3]
                    if letter not in mdc_map:
                        mdc_map[letter] = mdc_name

for letter in sorted(mdc_map.keys()):
    print(f"  '{letter}': '{mdc_map[letter]}',")
