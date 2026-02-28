# Pure ASCII script that loads data from JSON
import json

with open('final_2_data.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 1. Update custom_prompts
json_paths = [
    'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/data/sichuan_rules_146.json',
    'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/sichuan_rules_146.json',
    'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/data/sichuan_rules_146_updated.json',
]

prompt_fixes = config['prompt_fixes']
for p in json_paths:
    try:
        with open(p, 'r', encoding='utf-8') as f:
            rules = json.load(f)
        updated = 0
        for r in rules:
            if r['rule_id'] in prompt_fixes:
                r['custom_prompt'] = prompt_fixes[r['rule_id']]
                updated += 1
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        print("OK prompts: %s (%d)" % (p.split('/')[-1], updated))
    except FileNotFoundError:
        print("SKIP: %s" % p.split('/')[-1])

# 2. Rewrite test case data
TS_PATH = 'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/src/data/qcRuleCases.ts'

with open(TS_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

def esc(s):
    out = []
    for c in s:
        if ord(c) > 127:
            out.append('\\u%04x' % ord(c))
        else:
            out.append(c)
    return ''.join(out)

def build_sections_ts(sections_list):
    parts = []
    for item in sections_list:
        heading = item[0]
        body = item[1]
        h = esc(heading)
        c = esc(body).replace('\n', '\\n')
        parts.append('        { heading: "%s", content: "%s" }' % (h, c))
    return ',\n'.join(parts)

def build_focus_points_ts(fps):
    return ', '.join('"%s"' % esc(fp) for fp in fps)

data_fixes = config['data_fixes']
ok = 0
for rule_id, fields in data_fixes.items():
    for field_name, data in fields.items():
        rule_pattern = 'ruleId: "%s"' % rule_id
        rule_idx = content.find(rule_pattern)
        if rule_idx == -1:
            print("MISS rule: %s" % rule_id)
            continue
        next_rule = content.find('ruleId: "SC-', rule_idx + len(rule_pattern))
        rule_block = content[rule_idx:next_rule] if next_rule != -1 else content[rule_idx:]
        field_idx = rule_block.find('%s:' % field_name)
        if field_idx == -1:
            print("MISS field: %s.%s" % (rule_id, field_name))
            continue
        field_start = rule_idx + field_idx
        sections_start = content.find('sections:', field_start)
        if sections_start == -1 or sections_start > rule_idx + len(rule_block):
            print("MISS sections: %s.%s" % (rule_id, field_name))
            continue
        bo = content.find('[', sections_start)
        depth = 0
        i = bo
        while i < len(content):
            if content[i] == '[':
                depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        bc = i
        fss = content.find('focusPoints:', bc)
        if fss == -1 or fss > rule_idx + len(rule_block):
            print("MISS focusPoints: %s.%s" % (rule_id, field_name))
            continue
        fbo = content.find('[', fss)
        fbc = content.find(']', fbo)
        # Replace title
        ts = content.find('title:', field_start)
        if ts != -1 and ts < sections_start:
            tqs = content.find('"', ts)
            tqe = content.find('"', tqs + 1)
            while content[tqe - 1] == '\\':
                tqe = content.find('"', tqe + 1)
            nt = esc(data['title'])
            content = content[:tqs+1] + nt + content[tqe:]
            off = len(nt) - (tqe - tqs - 1)
            bo += off; bc += off; fbo += off; fbc += off; sections_start += off
        # Replace summary
        ss = content.find('summary:', field_start)
        if ss != -1 and ss < sections_start:
            sqs = content.find('"', ss)
            sqe = content.find('"', sqs + 1)
            while content[sqe - 1] == '\\':
                sqe = content.find('"', sqe + 1)
            ns = esc(data['summary'])
            content = content[:sqs+1] + ns + content[sqe:]
            off = len(ns) - (sqe - sqs - 1)
            bo += off; bc += off; fbo += off; fbc += off
        # Replace sections
        new_sec = '[\n' + build_sections_ts(data['sections']) + '\n      ]'
        content = content[:bo] + new_sec + content[bc+1:]
        off = len(new_sec) - (bc + 1 - bo)
        fbo += off; fbc += off
        # Replace focusPoints
        new_fp = '[' + build_focus_points_ts(data['focusPoints']) + ']'
        content = content[:fbo] + new_fp + content[fbc+1:]
        ok += 1
        print("OK data: %s.%s" % (rule_id, field_name))

with open(TS_PATH, 'w', encoding='utf-8') as f:
    f.write(content)
print("\nDone: %d data replacements + 4 prompt updates" % ok)
