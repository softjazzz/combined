"""Quick test: verify the auto-batching logic works correctly"""
import sys
sys.path.insert(0, '.')
from app.services.segmented_qc_pipeline import SegmentedQCPipeline
from app.services.document_segmenter import split_document, merge_small_sections

# Load record
with open('张伟_病程记录.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Step 1: Segment
sections = split_document(content)
sections = merge_small_sections(sections, min_chars=100)

# Step 2: Route with batching (dry run, no LLM)
pipeline = SegmentedQCPipeline(max_concurrency=5)
tasks_info = []
total_rules = 0

for sec in sections:
    rules = pipeline.router.get_rules_for_section(sec.section_type)
    if not rules:
        continue
    
    if len(rules) > pipeline.MAX_RULES_PER_BATCH:
        batches = [
            rules[i:i + pipeline.MAX_RULES_PER_BATCH]
            for i in range(0, len(rules), pipeline.MAX_RULES_PER_BATCH)
        ]
        for batch_idx, batch in enumerate(batches, 1):
            tasks_info.append({'section': sec, 'rules': batch})
            total_rules += len(batch)
        print(f"  [{sec.section_type:22s}] {sec.title[:25]:25s} -> {len(rules):2d} rules (split into {len(batches)} batches: {[len(b) for b in batches]})")
    else:
        tasks_info.append({'section': sec, 'rules': rules})
        total_rules += len(rules)
        print(f"  [{sec.section_type:22s}] {sec.title[:25]:25s} -> {len(rules):2d} rules")

print(f"\nTotal tasks: {len(tasks_info)} (was 9 before batching)")
print(f"Total rules: {total_rules}")
print(f"Max rules per task: {max(len(t['rules']) for t in tasks_info)}")
