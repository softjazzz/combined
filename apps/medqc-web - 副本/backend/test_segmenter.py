"""Test segmenter + router: each section gets its own rules (no route-time dedup)."""
import sys
sys.path.insert(0, '.')

from app.services.document_segmenter import split_document, merge_small_sections
from app.services.rule_router import RuleRouter

with open('张伟_病程记录.txt', 'r', encoding='utf-8') as f:
    content = f.read()

sections = split_document(content)
sections = merge_small_sections(sections, min_chars=100)

router = RuleRouter()

print("=== Segmented QC Plan ===\n")
total = 0
all_rule_ids = set()
for i, s in enumerate(sections):
    rules = router.get_rules_for_section(s.section_type)
    total += len(rules)
    all_rule_ids.update(r['rule_id'] for r in rules)
    ts = s.timestamp or "N/A"
    print(f"{i+1}. [{s.section_type:22s}] {ts} | {s.char_count:4d}字 | {len(rules):2d}条规则 | {s.title[:35]}")

print(f"\n--- Summary ---")
print(f"Sections:                {len(sections)}")
print(f"Unique rules covered:    {len(all_rule_ids)} / 145")
print(f"Total rule evaluations:  {total} (some rules eval'd against multiple sections)")
print(f"Avg rules per section:   {total / len(sections):.0f}")
print(f"Avg chars per section:   {sum(s.char_count for s in sections) / len(sections):.0f}")
