import test from 'node:test'
import assert from 'node:assert/strict'
import { businessModelValue } from './business-output.mjs'

test('规则检索只给目录候选，保存版本与当前目录版本分别透传', () => {
  const candidate = {
    rule_id: 'LX0609-01-01-01',
    title: '术前讨论',
    implementation_status: 'active',
    phase_status: '默认启用',
    release_scope: 'default',
  }
  const search = businessModelValue(
    'search_rules',
    {},
    {
      rule_candidates: [{ ...candidate, policy_summary: '候选阶段不展开全部口径' }],
      rule_search: {
        query: '术前讨论',
        page: 1,
        page_size: 5,
        total: 1,
        returned: 1,
        has_more: false,
      },
      catalog_version: 'current-v2',
      scope_note: '当前目录候选，不是历史规则正文',
      internal_debug: '不进入模型',
    },
  )
  assert.deepEqual(search.rule_candidates, [candidate])
  assert.equal(search.catalog_version, 'current-v2')
  assert.equal(search.rule_search.total, 1)
  assert.ok(!JSON.stringify(search).includes('不进入模型'))
  const issue = businessModelValue(
    'read_saved_issue',
    {},
    {
      references: [{ id: 'saved:a', conclusion: '原保存结论' }],
      job_id: 'job-a',
      rule_set_version: 'saved-v1',
      result_time: '2026-09-01T10:00:00+08:00',
      version_note: '保存版本标签不能代替历史规则正文',
    },
  )
  assert.equal(issue.rule_set_version, 'saved-v1')
  assert.equal(issue.version_note, '保存版本标签不能代替历史规则正文')
  const rule = businessModelValue(
    'read_rule',
    {},
    {
      rule: {
        ...candidate,
        active_criteria: ['published'],
        pending_criteria: ['pending'],
        pending_reason_code: 'pending_definition',
      },
      catalog_version: 'current-v2',
      historical_definition_available: false,
      references: [{ id: 'rule:current' }],
      scope_note: '当前目录',
    },
  )
  assert.equal(rule.catalog_version, 'current-v2')
  assert.equal(rule.historical_definition_available, false)
  assert.deepEqual(rule.rule.active_criteria, ['published'])
  assert.deepEqual(rule.rule.pending_criteria, ['pending'])
  assert.equal(issue.rule_set_version, 'saved-v1')
})

test('保存覆盖率不能冒充任务运行状态，摘录不冒充当前文书', () => {
  const canonical = {
    state: 'ready',
    is_complete: false,
    missing_rule_ids: ['R2'],
    references: [
      {
        id: 'result-a',
        status: 'non_compliant',
        conclusion: '否定条件必须保留',
        suggestion: '保存建议',
      },
    ],
  }
  const model = businessModelValue('read_saved_results', {}, canonical)
  assert.equal(model.is_complete, undefined)
  assert.deepEqual(model.saved_result_coverage, { is_complete: false, missing_rule_ids: ['R2'] })
  assert.match(model.task_status_scope, /未读取任务运行状态/)
  assert.match(model.display_note, /改写.*不能称.*原文/)
  const issue = businessModelValue(
    'read_saved_issue',
    {},
    {
      references: canonical.references,
      evidence: [{ evidence_excerpt: '未发现结果……' }],
      evidence_scope: '执行时保存摘录',
    },
  )
  assert.match(issue.evidence_read_note, /不能.*重新判定/)
  assert.match(issue.evidence_read_note, /当前文书.*未读取/)
  assert.equal(issue.evidence[0].evidence_excerpt, '未发现结果……')
  assert.equal(canonical.is_complete, false)
  const conflicted = businessModelValue(
    'read_saved_results',
    {},
    { ...canonical, missing_rule_ids: [], conflicting_rule_ids: ['R3'] },
  )
  assert.deepEqual(conflicted.saved_result_coverage, {
    is_complete: false,
    missing_rule_ids: [],
    conflicting_rule_ids: ['R3'],
  })
  const unavailable = businessModelValue(
    'read_saved_results',
    {},
    { state: 'technical_error', reason_code: 'canonical_result_envelope_invalid', references: [] },
  )
  assert.equal(unavailable.reason_code, 'canonical_result_envelope_invalid')
  assert.deepEqual(unavailable.saved_result_coverage, {})
  assert.match(unavailable.task_status_scope, /正式读取状态/)
})

test('统计概览缩小规则范围但保留正式计数与病例下钻标识', () => {
  const statistics = {
    kpis: { scoped_record_total: 13, ready_record_total: 6, unavailable_result_total: 7 },
    status_distribution: { non_compliant: 41, data_gap: 65, not_executed: 60 },
    rule_distribution: [
      { rule_id: 'R2', non_compliant_count: 5, data_gap_count: 2, evaluated_count: 6 },
      { rule_id: 'R1', non_compliant_count: 5, data_gap_count: 3, evaluated_count: 6 },
      { rule_id: 'R3', non_compliant_count: 6, data_gap_count: 0, evaluated_count: 6 },
    ],
    record_page: { page: 1, page_size: 20, total: 6 },
  }
  const value = {
    statistics,
    statistics_page: { rule_limit: 2 },
    references: [
      {
        id: 'record:bound',
        kind: 'record',
        title: '已授权病例',
        identity: '内部身份',
        text: '完整展示内容',
      },
    ],
  }
  const result = businessModelValue('query_statistics', {}, value)
  assert.deepEqual(result.kpis, statistics.kpis)
  assert.deepEqual(result.status_distribution, statistics.status_distribution)
  assert.deepEqual(result.rules, [statistics.rule_distribution[2], statistics.rule_distribution[1]])
  assert.deepEqual(result.rule_scope, {
    ordering: '不合规次数降序，同次数按规则id',
    total: 3,
    returned: 2,
    has_more: true,
  })
  assert.equal(result.record_page.records[0].record_reference, 'record:bound')
  assert.equal(statistics.rule_distribution.length, 3)
  assert.ok(!JSON.stringify(result).includes('完整展示内容'))
})

test('概览仅给同序稳定索引，完整展示文本不进入模型', () => {
  const references = [1, 2].map((position) => ({
    id: `result:${position}`,
    position,
    kind: 'saved_result',
    title: `问题${position}`,
    status: 'non_compliant',
    conclusion: '完整保存结论',
    suggestion: '完整保存建议',
    locator: '完整定位',
  }))
  const value = {
    state: 'ready',
    job_id: 'task-a',
    references,
    result_page: {
      detail: 'index',
      total: 75,
      matched_total: 7,
      returned: 2,
      has_more: true,
      page: 1,
      status_counts: { compliant: 68, non_compliant: 7 },
    },
  }
  const result = businessModelValue('read_saved_results', {}, value)
  assert.deepEqual(
    result.results.map((r) => [r.position, r.id]),
    [
      [1, 'result:1'],
      [2, 'result:2'],
    ],
  )
  assert.equal(result.result_page.total, 75)
  assert.ok(!JSON.stringify(result).includes('完整保存'))
  assert.equal(value.references[1].conclusion, '完整保存结论')
  const detailed = businessModelValue(
    'read_saved_results',
    {},
    { ...value, result_page: { ...value.result_page, detail: 'saved_text' } },
  )
  assert.deepEqual(detailed.results, result.results)
  assert.ok(!JSON.stringify(detailed).includes('完整保存'))
  assert.equal(value.references[1].suggestion, '完整保存建议')
})

test('单问题的否定条件和证据保持完整且只出现一次，规则不发送内部目录字段', () => {
  const evidence = [{ source_ref: 'src-a', evidence_excerpt: '未发现变化；不能据此判断缺失。' }]
  const ref = {
    id: 'result-a',
    rule_id: 'LX0609-01-01-01',
    title: '质控点',
    status: 'data_gap',
    conclusion: '不能判定不合规',
    suggestion: '先核对资料',
    evidence,
    text: '重复全文',
    locator: '展示定位',
  }
  const issue = businessModelValue(
    'read_saved_issue',
    {},
    { references: [ref], evidence, reason_code: 'source_missing', evidence_scope: '保存时摘录' },
  )
  assert.equal(issue.evidence[0].evidence_excerpt, evidence[0].evidence_excerpt)
  assert.equal(JSON.stringify(issue).split('未发现变化').length - 1, 1)
  assert.equal(issue.conclusion, ref.conclusion)
  assert.ok(!JSON.stringify(issue).includes('重复全文'))
  const rule = businessModelValue(
    'read_rule',
    {},
    {
      rule: {
        rule_id: 'R',
        title: '规则',
        policy_summary: '实施口径',
        phase_status: '部分启用',
        internal_large_catalog: '不发送',
      },
      scope_note: '当前版本，非历史',
      references: [{ id: 'rule:R', text: '重复口径' }],
    },
  )
  assert.equal(rule.rule.policy_summary, '实施口径')
  assert.ok(!JSON.stringify(rule).includes('不发送'))
})
