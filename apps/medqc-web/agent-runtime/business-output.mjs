// 原生模型文本的纯投影；完整卡片保留在 DSH presentationMeta，不另存结果。
const select = (value, keys) =>
  Object.fromEntries(
    keys.filter((key) => value?.[key] !== undefined).map((key) => [key, value[key]]),
  )
export function businessModelValue(name, _args, value) {
  if (name === 'read_saved_results') {
    const result = select(value, [
      'state',
      'reason_code',
      'job_id',
      'rule_set_version',
      'is_complete',
      'missing_rule_ids',
      'result_time',
      'result_time_note',
      'result_page',
    ])
    if (result.result_page)
      result.result_page = select(result.result_page, [
        'statuses',
        'page',
        'page_size',
        'total',
        'matched_total',
        'returned',
        'has_more',
        'status_counts',
      ])
    const fields = ['position', 'id', 'rule_id', 'title', 'status']
    if (value.result_page?.detail === 'saved_text') fields.push('conclusion', 'suggestion')
    return {
      ...result,
      results: (value.references || []).map((ref) => select(ref, fields)),
      display_note:
        '下方同序卡片保留原结论建议；页码/范围不表示已读其他页。仅解释时按稳定id读取证据。',
    }
  }
  if (name === 'read_saved_issue')
    return {
      ...select(value.references?.[0], [
        'id',
        'rule_id',
        'title',
        'status',
        'conclusion',
        'suggestion',
      ]),
      ...select(value, ['reason_code', 'evidence_scope']),
      evidence: value.evidence || [],
    }
  if (name === 'read_rule')
    return {
      id: value.references?.[0]?.id,
      rule: select(value.rule, [
        'rule_id',
        'title',
        'implementation_status',
        'phase_status',
        'policy_summary',
        'definition_note',
        'release_scope',
      ]),
      scope_note: value.scope_note,
    }
  if (name === 'query_statistics') {
    const statistics = value.statistics || {}
    const rules = [...(statistics.rule_distribution || [])].sort(
      (a, b) =>
        (b.non_compliant_count || 0) - (a.non_compliant_count || 0) ||
        a.rule_id.localeCompare(b.rule_id),
    )
    const limit = value.statistics_page?.rule_limit || 5
    const records = (value.references || []).filter((ref) => ref.kind === 'record')
    return {
      filters: value.filters,
      metric_owner: value.metric_owner,
      kpis: statistics.kpis,
      status_distribution: statistics.status_distribution,
      rule_scope: {
        ordering: '不合规次数降序，同次数按规则id',
        total: rules.length,
        returned: Math.min(limit, rules.length),
        has_more: rules.length > limit,
      },
      rules: rules
        .slice(0, limit)
        .map((row) =>
          select(row, [
            'rule_id',
            'rule_name',
            ...Object.keys(row).filter((key) => key.endsWith('_count')),
          ]),
        ),
      record_page: {
        ...select(statistics.record_page, ['page', 'page_size', 'total']),
        records: records.map((ref) => ({ record_reference: ref.id, title: ref.title })),
      },
    }
  }
  throw new Error('未配置业务工具模型投影')
}
