// 原生模型文本的纯投影；完整卡片保留在 DSH presentationMeta，不另存结果。
const select = (value, keys) =>
  Object.fromEntries(
    keys.filter((key) => value?.[key] !== undefined).map((key) => [key, value[key]]),
  )

// 仅收紧模型可见上下文；授权身份和会话隔离仍使用原业务上下文。
export function businessModelContext(context) {
  if (context?.view === 'doctor')
    return {
      ...select(context, ['view', 'institute_id']),
      record_scope: '当前页面已选择且服务端授权的本次住院，身份见页面，不猜/复述标识。',
    }
  return { ...context }
}

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
      ...select(value, [
        'reason_code',
        'evidence_scope',
        'job_id',
        'rule_set_version',
        'result_time',
        'version_note',
      ]),
      evidence_index: (value.evidence || []).map((item, index) => ({
        evidence_position: index + 1,
        ...select(item, ['source_type', 'source_ref', 'record_time', 'field_path']),
      })),
      evidence_read_note:
        '本次模型仅收到保存结论、建议和证据定位索引，未读取证据摘录正文；证据序号仅为该问题证据数组位置，不是问题序号。完整保存证据由来源卡展示，不能补写或解释未读摘录，不能重新判定或新增原因。原因只能说明保存结论认为的内容；结论未说明的细节须明确无法确认。当前文书和规范原文均未读取，查看原文请使用该问题卡片的“查看依据与详情→查看对应文书原文”。',
    }
  if (name === 'query_followups')
    return {
      ...select(value, [
        'kind',
        'state',
        'page',
        'page_size',
        'has_more',
        'scan_limit_reached',
        'coverage_note',
        'status_note',
      ]),
      items: (value.items || []).map((item) => ({
        ...select(item, ['record_reference']),
        ...select(
          item,
          value.kind === 'notifications'
            ? ['id', 'type', 'title', 'content', 'severity', 'is_read', 'created_at']
            : [
                'id',
                'defect_type',
                'severity',
                'remediation_requirement',
                'deadline',
                'status',
                'created_at',
              ],
        ),
        identity: select(item.identity, ['institute_id', 'patient_id', 'visit_id']),
      })),
      read_note:
        '仅本页已核验授权的保存条目，不提供全局总量；空页或排除项不能解释为无待办。通过关联病例卡或record_reference读取该病例当前保存质控问题，关联病例不是统计结果。没有执行标记已读、提交、关闭或催办，不把保存状态说成本轮操作成功。',
    }
  if (name === 'search_rules')
    return {
      ...select(value, ['catalog_version', 'scope_note']),
      rule_search: select(value.rule_search, [
        'query',
        'page',
        'page_size',
        'total',
        'returned',
        'has_more',
      ]),
      rule_candidates: (value.rule_candidates || []).map((rule) =>
        select(rule, [
          'rule_id',
          'title',
          'implementation_status',
          'phase_status',
          'release_scope',
        ]),
      ),
    }
  if (name === 'read_rule')
    return {
      id: value.references?.[0]?.id,
      rule: {
        ...select(value.rule, [
          'rule_id',
          'title',
          'qc_point',
          'source_document',
          'implementation_status',
          'phase_status',
          'policy_summary',
          'definition_note',
          'release_scope',
          'active_criteria',
          'pending_criteria',
          'pending_reason_code',
        ]),
        title: value.rule?.title ?? value.references?.[0]?.title,
      },
      scope_note: value.scope_note,
      ...select(value, ['catalog_version', 'historical_definition_available']),
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
      display_note:
        '下方病例卡片完整展示本页病例，正文说明统计指标与本页范围并引导查看卡片，不重复列出部分病例冒充整页。record_page.total为分页总量，不表示本页全部返回；未展示页不能称已读取。追问具体病例时使用对应record_reference下钻。',
    }
  }
  throw new Error('未配置业务工具模型投影')
}
