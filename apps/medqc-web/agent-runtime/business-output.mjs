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
    return {
      ...result,
      saved_result_coverage: select(value, [
        'is_complete',
        'missing_rule_ids',
        'conflicting_rule_ids',
      ]),
      task_status_scope:
        value.state === 'ready'
          ? '本工具未读取任务运行状态；保存结果完整性描述保存项覆盖及冲突，不能据此推断任务正在运行、未运行完或已停止。'
          : '本次未取得可读保存结果；按state和reason_code说明正式读取状态，不从结果为空推断任务运行状态。',
      results: (value.references || []).map((ref) => select(ref, fields)),
      display_note:
        '下方同序卡片完整展示保存结论与建议原文，本次模型仅收到问题索引，未读取这些字段全文。列表回答只说明本页范围并引导查看卡片，不从标题推断具体原因或建议。回答改写只能称概述，不能称原文照录。页码/范围不表示已读其他页；仅在用户追问原因或依据时按稳定id读取具体问题。',
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
      evidence_read_note:
        '本工具仅回读保存问题与证据摘录，当前文书和规范原文均未读取。摘录可能不完整，不能据此重新判定已保存状态或新增原因；保存依据不足以解释细节时应说明无法确认。查看当前文书请使用该问题卡片的“查看依据与详情→查看对应文书原文”。',
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
