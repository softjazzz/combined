"""
ICD 编码提取脚本：从医保2.0版 PDF 提取带层级的 JSON 数据

输入:
  - ICD-10医保2.0版.pdf (4038 页)
  - ICD-9-CM3医保2.0版.pdf (1064 页)

输出:
  - icd10_hierarchical.json (章→节→类目→亚目→诊断)
  - icd9cm3_hierarchical.json (章→节→类目→亚目→手术)
  - 同时更新扁平的 icd10_diagnoses.json / icd9cm3_procedures.json
"""

import pdfplumber
import json
import re
import sys
import os
from collections import OrderedDict

# ============================================================
# ICD-10 提取
# ============================================================

def extract_icd10(pdf_path: str) -> dict:
    """从 ICD-10 医保2.0版 PDF 提取层级数据"""
    print(f"正在提取 ICD-10: {pdf_path}")
    pdf = pdfplumber.open(pdf_path)
    total_pages = len(pdf.pages)
    print(f"  总页数: {total_pages}")

    # 表头: 章, 章代码范围, 章的名称, 节代码范围, 节名称, 类目代码, 类目名称, 亚目代码, 亚目名称, 诊断代码, 诊断名称
    all_rows = []
    for i, page in enumerate(pdf.pages):
        if i % 200 == 0:
            print(f"  处理第 {i}/{total_pages} 页...")
        tables = page.extract_tables()
        if not tables:
            continue
        for table in tables:
            for row in table:
                # 跳过表头行
                if row and row[0] and '章' in str(row[0]) and '代码' in str(row[1] or ''):
                    continue
                if row and len(row) >= 10:
                    # 清理换行符
                    cleaned = [str(cell or '').replace('\n', '').strip() for cell in row]
                    all_rows.append(cleaned)

    pdf.close()
    print(f"  提取原始行数: {len(all_rows)}")

    # 构建层级结构
    chapters = OrderedDict()  # key: chapter_num
    flat_items = []  # 扁平列表 {code, name}

    for row in all_rows:
        try:
            ch_num = row[0].strip()
            ch_range = row[1].strip()
            ch_name = row[2].strip()
            sec_range = row[3].strip()
            sec_name = row[4].strip()
            cat_code = row[5].strip()
            cat_name = row[6].strip()

            # 亚目和诊断可能在不同列位置
            if len(row) >= 11:
                sub_code = row[7].strip()
                sub_name = row[8].strip()
                diag_code = row[9].strip()
                diag_name = row[10].strip()
            else:
                sub_code = row[7].strip()
                sub_name = row[8].strip()
                diag_code = row[9].strip() if len(row) > 9 else ''
                diag_name = ''

            if not ch_num or not cat_code:
                continue

            # 构建层级
            if ch_num not in chapters:
                chapters[ch_num] = {
                    'chapter': ch_num,
                    'code_range': ch_range,
                    'name': ch_name,
                    'sections': OrderedDict()
                }
            ch = chapters[ch_num]

            sec_key = sec_range or 'unknown'
            if sec_key not in ch['sections']:
                ch['sections'][sec_key] = {
                    'code_range': sec_range,
                    'name': sec_name,
                    'categories': OrderedDict()
                }
            sec = ch['sections'][sec_key]

            if cat_code not in sec['categories']:
                sec['categories'][cat_code] = {
                    'code': cat_code,
                    'name': cat_name,
                    'subcategories': OrderedDict()
                }
            cat = sec['categories'][cat_code]

            # 亚目级
            if sub_code:
                if sub_code not in cat['subcategories']:
                    cat['subcategories'][sub_code] = {
                        'code': sub_code,
                        'name': sub_name,
                        'diagnoses': []
                    }
                sub = cat['subcategories'][sub_code]

                # 诊断级
                if diag_code:
                    sub['diagnoses'].append({
                        'code': diag_code,
                        'name': diag_name
                    })
                    flat_items.append({'code': diag_code, 'name': diag_name})
                elif sub_code and sub_name:
                    # 有些亚目就是最终诊断
                    flat_items.append({'code': sub_code, 'name': sub_name})
            elif cat_code and cat_name:
                flat_items.append({'code': cat_code, 'name': cat_name})

        except (IndexError, ValueError) as e:
            continue

    # 转换 OrderedDict → list
    result = {
        'version': '医保2.0',
        'type': 'ICD-10',
        'chapters': []
    }
    for ch in chapters.values():
        ch_data = {
            'chapter': ch['chapter'],
            'code_range': ch['code_range'],
            'name': ch['name'],
            'sections': []
        }
        for sec in ch['sections'].values():
            sec_data = {
                'code_range': sec['code_range'],
                'name': sec['name'],
                'categories': []
            }
            for cat in sec['categories'].values():
                cat_data = {
                    'code': cat['code'],
                    'name': cat['name'],
                    'subcategories': []
                }
                for sub in cat['subcategories'].values():
                    cat_data['subcategories'].append({
                        'code': sub['code'],
                        'name': sub['name'],
                        'diagnoses': sub['diagnoses']
                    })
                sec_data['categories'].append(cat_data)
            ch_data['sections'].append(sec_data)
        result['chapters'].append(ch_data)

    # 去重扁平列表
    seen = set()
    unique_flat = []
    for item in flat_items:
        if item['code'] not in seen:
            seen.add(item['code'])
            unique_flat.append(item)

    print(f"  层级: {len(result['chapters'])} 章")
    print(f"  扁平去重: {len(unique_flat)} 条")
    return result, unique_flat


# ============================================================
# ICD-9-CM-3 提取（结构类似）
# ============================================================

def extract_icd9(pdf_path: str) -> dict:
    """从 ICD-9-CM-3 医保2.0版 PDF 提取层级数据"""
    print(f"\n正在提取 ICD-9-CM-3: {pdf_path}")
    pdf = pdfplumber.open(pdf_path)
    total_pages = len(pdf.pages)
    print(f"  总页数: {total_pages}")

    all_rows = []
    for i, page in enumerate(pdf.pages):
        if i % 100 == 0:
            print(f"  处理第 {i}/{total_pages} 页...")
        tables = page.extract_tables()
        if not tables:
            continue
        for table in tables:
            for row in table:
                if row and row[0] and '章' in str(row[0]) and '名称' in str(row[1] or ''):
                    continue
                if row and len(row) >= 8:
                    cleaned = [str(cell or '').replace('\n', '').strip() for cell in row]
                    all_rows.append(cleaned)

    pdf.close()
    print(f"  提取原始行数: {len(all_rows)}")

    # ICD-9 表头: 章, 章的名称, 类目代码, 类目名称, 亚目代码, 亚目名称, 手术操作代码, 手术操作名称
    # 实际字段可能略有不同，先看第一行推断
    if all_rows:
        print(f"  首行样本: {all_rows[0][:10]}")

    chapters = OrderedDict()
    flat_items = []

    for row in all_rows:
        try:
            ch_num = row[0].strip()
            ch_name = row[1].strip()

            # 根据列数自适应
            if len(row) >= 10:
                cat_code = row[2].strip()
                cat_name = row[3].strip()
                sub_code = row[4].strip()
                sub_name = row[5].strip()
                proc_code = row[6].strip() if len(row) > 6 else ''
                proc_name = row[7].strip() if len(row) > 7 else ''
                detail_code = row[8].strip() if len(row) > 8 else ''
                detail_name = row[9].strip() if len(row) > 9 else ''
            elif len(row) >= 8:
                cat_code = row[2].strip()
                cat_name = row[3].strip()
                sub_code = row[4].strip()
                sub_name = row[5].strip()
                proc_code = row[6].strip()
                proc_name = row[7].strip()
                detail_code = ''
                detail_name = ''
            else:
                continue

            if not ch_num or not cat_code:
                continue

            if ch_num not in chapters:
                chapters[ch_num] = {
                    'chapter': ch_num,
                    'name': ch_name,
                    'categories': OrderedDict()
                }
            ch = chapters[ch_num]

            if cat_code not in ch['categories']:
                ch['categories'][cat_code] = {
                    'code': cat_code,
                    'name': cat_name,
                    'subcategories': OrderedDict()
                }
            cat = ch['categories'][cat_code]

            if sub_code:
                if sub_code not in cat['subcategories']:
                    cat['subcategories'][sub_code] = {
                        'code': sub_code,
                        'name': sub_name,
                        'procedures': []
                    }
                sub = cat['subcategories'][sub_code]

                # 最终手术操作
                final_code = detail_code or proc_code
                final_name = detail_name or proc_name
                if final_code:
                    sub['procedures'].append({
                        'code': final_code,
                        'name': final_name
                    })
                    flat_items.append({'code': final_code, 'name': final_name})
                elif sub_code and sub_name:
                    flat_items.append({'code': sub_code, 'name': sub_name})
            elif cat_code and cat_name:
                flat_items.append({'code': cat_code, 'name': cat_name})

        except (IndexError, ValueError):
            continue

    # 转换 → list
    result = {
        'version': '医保2.0',
        'type': 'ICD-9-CM-3',
        'chapters': []
    }
    for ch in chapters.values():
        ch_data = {
            'chapter': ch['chapter'],
            'name': ch['name'],
            'categories': []
        }
        for cat in ch['categories'].values():
            cat_data = {
                'code': cat['code'],
                'name': cat['name'],
                'subcategories': []
            }
            for sub in cat['subcategories'].values():
                cat_data['subcategories'].append({
                    'code': sub['code'],
                    'name': sub['name'],
                    'procedures': sub['procedures']
                })
            ch_data['categories'].append(cat_data)
        result['chapters'].append(ch_data)

    # 去重
    seen = set()
    unique_flat = []
    for item in flat_items:
        if item['code'] not in seen:
            seen.add(item['code'])
            unique_flat.append(item)

    print(f"  层级: {len(result['chapters'])} 章")
    print(f"  扁平去重: {len(unique_flat)} 条")
    return result, unique_flat


# ============================================================
# 主程序
# ============================================================

def main():
    base_dir = r'D:\大模型项目\lx0222'
    output_dir = os.path.join(base_dir, 'health-qc-monorepo', 'apps', 'medqc-web', 'backend', 'data')
    os.makedirs(output_dir, exist_ok=True)

    # ICD-10
    icd10_pdf = os.path.join(base_dir, 'ICD-10医保2.0版.pdf')
    if os.path.exists(icd10_pdf):
        icd10_tree, icd10_flat = extract_icd10(icd10_pdf)
        
        # 保存层级 JSON
        with open(os.path.join(output_dir, 'icd10_hierarchical.json'), 'w', encoding='utf-8') as f:
            json.dump(icd10_tree, f, ensure_ascii=False, indent=2)
        print(f"  ✅ 已保存 icd10_hierarchical.json")

        # 更新扁平 JSON（如果新数据更多）
        existing_path = os.path.join(output_dir, 'icd10_diagnoses.json')
        if os.path.exists(existing_path):
            with open(existing_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            print(f"  现有扁平数据: {len(existing)} 条")
        else:
            existing = []

        if len(icd10_flat) >= len(existing):
            with open(existing_path, 'w', encoding='utf-8') as f:
                json.dump(icd10_flat, f, ensure_ascii=False, indent=2)
            print(f"  ✅ 已更新 icd10_diagnoses.json ({len(icd10_flat)} 条)")
        else:
            print(f"  ⚠️ 新数据 ({len(icd10_flat)}) 少于现有 ({len(existing)})，保留现有数据")
    else:
        print(f"  ❌ 未找到: {icd10_pdf}")

    # ICD-9-CM-3
    icd9_pdf = os.path.join(base_dir, 'ICD-9-CM3医保2.0版.pdf')
    if os.path.exists(icd9_pdf):
        icd9_tree, icd9_flat = extract_icd9(icd9_pdf)

        with open(os.path.join(output_dir, 'icd9cm3_hierarchical.json'), 'w', encoding='utf-8') as f:
            json.dump(icd9_tree, f, ensure_ascii=False, indent=2)
        print(f"  ✅ 已保存 icd9cm3_hierarchical.json")

        existing_path = os.path.join(output_dir, 'icd9cm3_procedures.json')
        if os.path.exists(existing_path):
            with open(existing_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            print(f"  现有扁平数据: {len(existing)} 条")
        else:
            existing = []

        if len(icd9_flat) >= len(existing):
            with open(existing_path, 'w', encoding='utf-8') as f:
                json.dump(icd9_flat, f, ensure_ascii=False, indent=2)
            print(f"  ✅ 已更新 icd9cm3_procedures.json ({len(icd9_flat)} 条)")
        else:
            print(f"  ⚠️ 新数据 ({len(icd9_flat)}) 少于现有 ({len(existing)})，保留现有数据")
    else:
        print(f"  ❌ 未找到: {icd9_pdf}")

    print("\n🎉 提取完成！")


if __name__ == '__main__':
    main()
