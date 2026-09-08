import type { QcResultDebugContext } from './qcResultDebugExport'
import type { SingleRecordQcResultItem } from './single-record-result-model'

/** 仅汇总已脱敏的保存结果；证据数量不等于源库读取数量。 */
export function buildDiagnosticSummary(
  items: SingleRecordQcResultItem[],
  context?: QcResultDebugContext,
) {
  const ruleCounts = new Map<string, number>()
  const statusCounts: Record<string, number> = Object.create(null)
  const groups = new Map<string, { status: string; reason_code: string; rule_ids: string[] }>()
  const sources = new Map<string, { count: number; refs: Set<string>; rules: Set<string> }>()
  for (const item of items) {
    ruleCounts.set(item.rule_id, (ruleCounts.get(item.rule_id) || 0) + 1)
    statusCounts[item.status] = (statusCounts[item.status] || 0) + 1
    const reason = item.reason_code || 'unknown'
    const key = JSON.stringify([item.status, reason])
    const group = groups.get(key) || { status: item.status, reason_code: reason, rule_ids: [] }
    if (!group.rule_ids.includes(item.rule_id)) group.rule_ids.push(item.rule_id)
    groups.set(key, group)
    for (const evidence of item.evidence || []) {
      const sourceType = evidence.source_type || 'unknown'
      const source = sources.get(sourceType) || {
        count: 0,
        refs: new Set<string>(),
        rules: new Set<string>(),
      }
      source.count++
      if (evidence.source_ref) source.refs.add(evidence.source_ref)
      source.rules.add(item.rule_id)
      sources.set(sourceType, source)
    }
  }
  const duplicates = [...ruleCounts].filter(([, count]) => count > 1).map(([id]) => id)
  return {
    exported_result_count: items.length,
    unique_rule_count: ruleCounts.size,
    scope:
      context?.isComplete === true &&
      context.expectedRuleCount === items.length &&
      context.resultRuleCount === items.length &&
      !duplicates.length &&
      !context.missingRuleIds?.length &&
      !context.conflictingRuleIds?.length
        ? 'full_loaded_result'
        : 'partial_or_unknown',
    duplicate_rule_ids: duplicates,
    status_counts: statusCounts,
    reason_groups: [...groups.values()],
    evidence_sources: [...sources].map(([source_type, source]) => ({
      source_type,
      evidence_count: source.count,
      unique_reference_count: source.refs.size,
      rule_ids: [...source.rules],
    })),
  }
}
