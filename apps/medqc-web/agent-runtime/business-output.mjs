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
  if (name === 'compare_statistics') {
    const comparison = value.comparison || {}
    // 仅比较投影保留显式空值与非数组不足结构，不将缺失改写成零或空集合。
    const projectObject = (item, fields) =>
      item && typeof item === 'object' ? select(item, fields) : item
    const projectRows = (rows, fields) =>
      Array.isArray(rows)
        ? rows.map((row) => projectObject(row, typeof fields === 'function' ? fields(row) : fields))
        : projectObject(rows, typeof fields === 'function' ? fields(rows) : fields)
    const projectStatistics = (statistics) => {
      const result = select(statistics, [
        'scope',
        'kpis',
        'status_distribution',
        'rule_distribution',
      ])
      if ('scope' in result)
        result.scope = projectObject(result.scope, [
          'care_phase',
          'department',
          'doctor',
          'rule_id',
          'result_status',
          'completed_from',
          'completed_to',
        ])
      if ('kpis' in result) {
        // 真实回答曾将未期间过滤的病例池误称“同期总数”，单独标明其归属。
        const pool = select(result.kpis, ['scoped_record_total', 'unavailable_result_total'])
        if (Object.keys(pool).length) result.scope_pool_before_period_filter = pool
        result.kpis = projectObject(result.kpis, ['ready_record_total'])
      }
      if ('status_distribution' in result)
        result.status_distribution = projectRows(result.status_distribution, ['status', 'count'])
      if ('rule_distribution' in result)
        result.rule_distribution = projectRows(result.rule_distribution, (row) => [
          'rule_id',
          'rule_name',
          ...Object.keys(row || {}).filter((key) => key.endsWith('_count')),
        ])
      return result
    }
    return {
      metric_owner: value.metric_owner,
      comparison: {
        ...select(comparison, ['rule_id', 'same_rule_version_verified', 'limitations']),
        periods: (comparison.periods || []).map((period) => ({
          ...select(period, ['key', 'label', 'source_reference', 'data_notes']),
          filters: select(period.filters, [
            'institute_id',
            'department',
            'care_phase',
            'completed_from',
            'completed_to',
            'rule_id',
          ]),
          statistics: projectStatistics(period.statistics),
        })),
      },
      read_note:
        '仅描述两期正式接口返回的同一规则现存保存结果，不补零、不重算同比或环比正式指标，不从计数变化推断因果。来源卡对应各自期间；scope_pool_before_period_filter是日期过滤前的当前病例池，不能称同期病例总数或某月失败数，也不是期间分母；期间kpis仅保留ready_record_total。evaluated_count包含未执行和不适用。未验证历史规则版本、历史快照、完整执行覆盖或同步缺口，当前目录不能证明两期口径一致。保留各期不足提示，缺数据不能解释为零问题。',
    }
  }
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
        'source_gaps',
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
  if (name === 'preview_recheck' || name === 'preview_specialist_task')
    return {
      id: value.references?.[0]?.id,
      preview: select(value.preview, [
        'operation',
        'allowed',
        'blocked_reasons',
        'warnings',
        'record_count',
        'rule_ids',
      ]),
      must_tell_user: value.preview?.warnings || [],
      read_note:
        '这只是操作预览，尚未创建任务。可执行时请用户核对卡片后点击“确认执行”，助手不能代为确认；不可执行时说明原因。must_tell_user 非空时回答必须转述其内容，且不得说复检会读取或核对用户补写的新内容。不得称已复检、已创建任务或问题已解决；助手不会自动跟进结果，请用户在卡片上点“刷新任务进度”查看。',
    }
  if (name === 'trend_statistics') {
    const trend = value.trend || {}
    const ruleId = trend.rule_id
    return {
      id: value.references?.[0]?.id,
      rule_id: ruleId,
      metric_owner: value.metric_owner,
      periods: (trend.periods || []).map((period) => {
        const statistics = period.statistics || {}
        const rows = Array.isArray(statistics.rule_distribution) ? statistics.rule_distribution : []
        const picked = ruleId
          ? rows.filter((row) => row?.rule_id === ruleId)
          : [...rows]
              .filter((row) => row && typeof row === 'object')
              .sort(
                (a, b) =>
                  (b.non_compliant_count || 0) - (a.non_compliant_count || 0) ||
                  String(a.rule_id).localeCompare(String(b.rule_id)),
              )
              .slice(0, 5)
        return {
          completed_from: period.filters?.completed_from,
          completed_to: period.filters?.completed_to,
          ready_record_total: statistics.kpis?.ready_record_total,
          rules: picked.map((row) =>
            select(row, [
              'rule_id',
              'rule_name',
              ...Object.keys(row).filter((key) => key.endsWith('_count')),
            ]),
          ),
          data_notes: period.data_notes,
        }
      }),
      limitations: trend.limitations,
      read_note:
        '趋势卡片完整列出各期原值；回答按期描述原值和数据不足，不计算差值、增长率或百分比，不说“改善/恶化”或推断原因。',
    }
  }
  if (name === 'read_draft_facts')
    return {
      // 保存结论已作为序号0来源提供，不再重复字段。
      ...select(value, ['result_id', 'rule_id', 'title', 'suggestion', 'job_id', 'scope_note']),
      evidence: (value.evidence || []).map((item) =>
        select(item, ['evidence_position', 'source_type', 'record_time', 'excerpt']),
      ),
      draft_note:
        '只可复述上列摘录中的事实；摘录未写明的检查、诊疗、签名、时间或数值写成待医生补充。草稿不替代正式保存建议，不能称已整改。',
    }
  if (name === 'compose_reference_draft')
    return {
      id: value.references?.[0]?.id,
      draft: select(value.draft, ['result_id', 'segment_count', 'placeholder_count']),
      read_note:
        '草稿已通过来源校验并在卡片完整展示；回答只简述草稿用途和待医生补充项数量，不复述草稿全文，不称已整改或已写入病历。',
    }
  if (name === 'read_rule_validation')
    return {
      id: value.references?.[0]?.id,
      validation_record: select(value.validation_record, [
        'rule',
        'stage',
        'coverage',
        'runs',
        'run_limit',
        'has_more_runs',
        'data_notes',
        'scope_note',
      ]),
      read_note:
        '仅为已保存的规则验收摘要，不是当前病例或科室质控统计。当前目录启用不表示通过验收，运行成功不表示结论或批准通过；执行标识不能证明与当前部署一致。未知或缺失保持未取得，不补零。请用中文解释保存阶段及结论，完整入口见来源详情，不生成网址。',
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
        'scoped_record_total与unavailable_result_total属于当前科室授权病例池，未按质控完成期间过滤，不能作期间分母；ready_record_total才是期间内最新可读保存结果数。evaluated_count包含not_executed与not_applicable，不等于完成执行覆盖。下方病例卡片完整展示本页病例，正文说明统计指标与本页范围并引导查看卡片，不重复列出部分病例冒充整页。record_page.total为分页总量，不表示本页全部返回；未展示页不能称已读取。追问具体病例时使用对应record_reference下钻。',
    }
  }
  throw new Error('未配置业务工具模型投影')
}
