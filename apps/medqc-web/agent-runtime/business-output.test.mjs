import test from 'node:test'
import assert from 'node:assert/strict'
import { businessModelValue } from './business-output.mjs'

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
  assert.equal(detailed.results[1].suggestion, '完整保存建议')
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
