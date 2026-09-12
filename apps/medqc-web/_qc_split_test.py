import os
"""
按文书类型切分病历，导入 PG 各表，逐文书调 QC API

修复版：动态检测每个表的列，只写存在的列
"""
import json, re, time, requests, sqlalchemy as sa
from _import_and_test_qc import CASE_1_ZHANGSAN

DB_URL = os.environ["DATABASE_URL"]
API = 'http://localhost:8001'
PID = 'P-ZS-2026'
VID = 'V-ZS-001'


def split_by_section(text):
    sections = []
    title = None
    lines = []
    for line in text.split('\n'):
        if re.match(r'^={10,}$', line.strip()):
            continue
        m = re.match(r'^【(.+?)】\s*$', line.strip())
        if m:
            if title and lines:
                sections.append((title, '\n'.join(lines).strip()))
            title = m.group(1)
            lines = []
            continue
        lines.append(line)
    if title and lines:
        sections.append((title, '\n'.join(lines).strip()))
    return sections


TITLE_MAP = {
    '入院记录':       ('admission_record',     'admission_record'),
    '首次病程记录':   ('first_course_record',  'first_course_record'),
    '日常病程记录':   ('daily_course_record',  'daily_course_record'),
    '主任查房记录':   ('senior_course_record', 'senior_course_record'),
    '手术记录':       ('surgery_record',       'surgery_record'),
    '术后病程记录':   ('daily_course_record',  'daily_course_record'),
    '病程记录':       ('daily_course_record',  'daily_course_record'),
    '出院记录':       ('discharge_record',     'discharge_record'),
}

# 要写入的数据字段
BASE_DATA = {
    'institute_id': 'SCPH',
    'patient_id': PID,
    'visit_id': VID,
    'name': 'Zhang San',
    'sex': 'M',
    'age_year': 58,
    'dept_name': 'Cardiology',
}


def get_table_columns(conn, table_name):
    rows = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
    ), {'t': table_name}).fetchall()
    return {r[0] for r in rows}


def import_to_pg(sections):
    engine = sa.create_engine(DB_URL)
    imported = []
    doc_counter = {}  # 用于跟踪同一个表的多个文书段
    
    with engine.connect() as conn:
        # 先清理旧数据（所有相关表）
        for table_name in set(v[0] for v in TITLE_MAP.values()):
            table_cols = get_table_columns(conn, table_name)
            if 'patient_id' in table_cols and 'visit_id' in table_cols:
                conn.execute(sa.text(
                    f'DELETE FROM "{table_name}" WHERE patient_id = :pid AND visit_id = :vid'
                ), {'pid': PID, 'vid': VID})
        
        for title, content in sections:
            mapping = TITLE_MAP.get(title)
            if not mapping:
                print(f"  [skip] {title}")
                continue
            
            table_name, doc_type = mapping
            table_cols = get_table_columns(conn, table_name)
            
            # 为同表多段生成唯一 document_id
            doc_counter[table_name] = doc_counter.get(table_name, 0) + 1
            idx = doc_counter[table_name]
            
            # 构建数据：只写表中存在的列
            data = {}
            for k, v in BASE_DATA.items():
                if k in table_cols:
                    data[k] = v
            
            # 补齐 NOT NULL 列
            if 'document_id' in table_cols:
                data['document_id'] = f'DOC-{doc_type}-{PID}-{idx}'
            
            # record_content 或 content
            if 'record_content' in table_cols:
                data['record_content'] = content
            elif 'content' in table_cols:
                data['content'] = content
            
            # 动态 INSERT
            cols = ', '.join(data.keys())
            vals = ', '.join(f':{k}' for k in data.keys())
            conn.execute(sa.text(
                f'INSERT INTO "{table_name}" ({cols}) VALUES ({vals})'
            ), data)
            
            imported.append((title, table_name, doc_type, len(content)))
            print(f"  [OK] {title} -> {table_name} ({len(content)} chars)")
        
        conn.commit()
    return imported


def test_qc(imported):
    results = []
    engine = sa.create_engine(DB_URL)
    
    for title, table_name, doc_type, chars in imported:
        print(f"\n--- QC: {title} ({doc_type}) ---")
        
        with engine.connect() as conn:
            content_col = 'record_content'
            table_cols = get_table_columns(conn, table_name)
            if 'record_content' not in table_cols and 'content' in table_cols:
                content_col = 'content'
            
            row = conn.execute(sa.text(
                f'SELECT {content_col} FROM "{table_name}" WHERE patient_id = :pid AND visit_id = :vid LIMIT 1'
            ), {'pid': PID, 'vid': VID}).fetchone()
        
        if not row or not row[0]:
            print(f"  No data!")
            continue
        
        start = time.time()
        try:
            resp = requests.post(f"{API}/api/v1/qc/sichuan/evaluate", json={
                "document_id": f"split-{doc_type}-{PID}",
                "document_content": row[0],
                "document_type": doc_type,
                "persist": False,
                "prompt_mode": "plan_a",
            }, timeout=120)
            elapsed = time.time() - start
            
            if resp.status_code != 200:
                print(f"  FAILED: {resp.text[:200]}")
                continue
            
            result = resp.json()
            s = result.get('evaluation_summary', {})
            p = result.get('performance_metrics', {})
            evals = result.get('evaluation_results', [])
            nc = [r for r in evals if not r.get('is_compliant', True)]
            
            print(f"  Rules: {s.get('total_rules',0)} | "
                  f"Issues: {s.get('issues_found',0)} | "
                  f"Rate: {s.get('compliance_rate',0)}% | "
                  f"Time: {elapsed:.1f}s | "
                  f"Tokens: {p.get('token_usage',0)}")
            
            for r in nc[:3]:
                print(f"    [{r.get('rule_id')}] {r.get('rule_name','')[:50]}")
            if len(nc) > 3:
                print(f"    ... +{len(nc)-3} more")
            
            results.append({
                'title': title,
                'doc_type': doc_type,
                'chars': chars,
                'total_rules': s.get('total_rules', 0),
                'issues': s.get('issues_found', 0),
                'compliance_rate': s.get('compliance_rate', 0),
                'tokens': p.get('token_usage', 0),
                'time': round(elapsed, 1),
                'non_compliant': [{'rule_id': r.get('rule_id'), 'rule_name': r.get('rule_name'), 'findings': r.get('findings', '')[:200]} for r in nc],
            })
        except Exception as e:
            print(f"  ERROR: {e}")
    
    return results


def main():
    print("="*60)
    print("  Per-Document QC Test")
    print("="*60)
    
    sections = split_by_section(CASE_1_ZHANGSAN)
    print(f"\n[1] Split: {len(sections)} sections")
    for t, c in sections:
        print(f"    {t}: {len(c)} chars")
    
    print(f"\n[2] Import to PG...")
    imported = import_to_pg(sections)
    
    print(f"\n[3] QC per document ({len(imported)} docs)...")
    results = test_qc(imported)
    
    # Save
    with open('_qc_per_doc_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Summary table
    print(f"\n{'='*60}")
    print(f"{'Document':<20} {'Rules':>5} {'Issues':>6} {'Rate':>6} {'Tokens':>6} {'Time':>5}")
    print(f"{'-'*60}")
    total_r = total_i = total_t = 0
    for r in results:
        print(f"{r['title']:<20} {r['total_rules']:>5} {r['issues']:>6} "
              f"{r['compliance_rate']:>5.1f}% {r['tokens']:>6} {r['time']:>4.1f}s")
        total_r += r['total_rules']
        total_i += r['issues']
        total_t += r['tokens']
    print(f"{'-'*60}")
    print(f"{'TOTAL':<20} {total_r:>5} {total_i:>6} {'':>6} {total_t:>6}")


if __name__ == "__main__":
    main()
