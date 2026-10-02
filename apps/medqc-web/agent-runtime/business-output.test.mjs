import test from 'node:test'
import assert from 'node:assert/strict'
import { businessModelContext, businessModelValue } from './business-output.mjs'

test('跨期正式统计保留缺键、null、None条目及非数组不足结构，不崩溃或补零', () => {
  const values = [
    {},
    { scope: null, kpis: null, status_distribution: null, rule_distribution: null },
    {
      kpis: { ready_record_total: null },
      status_distribution: [null],
      rule_distribution: [null, { rule_id: 'R', non_compliant_count: null }],
    },
    { status_distribution: '未提供数组', rule_distribution: '未提供数组' },
  ]
  for (const statistics of values) {
    const payload = {
      comparison: {
        rule_id: 'R',
        periods: [{ key: 'baseline', statistics, data_notes: ['正式统计结构不足'] }],
      },
    }
    const result = businessModelValue('compare_statistics', {}, payload).comparison.periods[0]
    assert.deepEqual(result.statistics, statistics)
    assert.deepEqual(result.data_notes, ['正式统计结构不足'])
    assert.deepEqual(payload.comparison.periods[0].statistics, statistics)
  }
})

test('跨期统计仅搬运两期权威计数、来源与不足，不补零或生成变化率', () => {
  const payload = {
    metric_owner: 'LX0609 正式结果分析接口',
    comparison: {
      rule_id: 'R',
      same_rule_version_verified: false,
      limitations: ['现存最新保存结果，非历史快照；无法验证历史版本及完整执行覆盖'],
      periods: [
        {
          key: 'current',
          label: '当前期间',
          source_reference: 'stats:current',
          filters: {
            completed_from: '2026-09-01T00:00:00+08:00',
            completed_to: '2026-09-30T23:59:59+08:00',
            department: '内科',
          },
          data_notes: [],
          statistics: {
            scope: { department: '内科', rule_id: 'R', patient_id: '私有', visit_id: '私有' },
            kpis: {
              scoped_record_total: 90,
              ready_record_total: 4,
              unavailable_result_total: 2,
              internal: '私有',
            },
            status_distribution: [{ status: 'not_executed', count: 3, internal: '私有' }],
            rule_distribution: [
              {
                rule_id: 'R',
                rule_name: '规则',
                evaluated_count: 4,
                non_compliant_count: 1,
                not_executed_count: 3,
                raw_payload: '私有',
              },
            ],
            record_page: { records: [{ patient_id: '私有' }] },
          },
        },
        {
          key: 'baseline',
          label: '基线期间',
          source_reference: 'stats:baseline',
          filters: {
            completed_from: '2026-08-01T00:00:00+08:00',
            completed_to: '2026-08-31T23:59:59+08:00',
          },
          data_notes: ['未取得选中规则的计数'],
          statistics: { kpis: { ready_record_total: 0 } },
        },
      ],
    },
    references: [{ id: 'stats:current', text: '完整卡片私有' }],
  }
  const before = structuredClone(payload)
  const result = businessModelValue('compare_statistics', {}, payload)
  assert.equal(result.comparison.same_rule_version_verified, false)
  assert.deepEqual(result.comparison.limitations, payload.comparison.limitations)
  const [current, baseline] = result.comparison.periods
  assert.equal(current.source_reference, 'stats:current')
  assert.deepEqual(current.filters, payload.comparison.periods[0].filters)
  assert.deepEqual(current.statistics.scope_pool_before_period_filter, {
    scoped_record_total: 90,
    unavailable_result_total: 2,
  })
  assert.deepEqual(current.statistics.kpis, { ready_record_total: 4 })
  assert.equal(current.statistics.kpis.scoped_record_total, undefined)
  assert.deepEqual(current.statistics.status_distribution, [{ status: 'not_executed', count: 3 }])
  assert.deepEqual(current.statistics.rule_distribution, [
    {
      rule_id: 'R',
      rule_name: '规则',
      evaluated_count: 4,
      non_compliant_count: 1,
      not_executed_count: 3,
    },
  ])
  assert.equal(baseline.statistics.rule_distribution, undefined)
  assert.equal(baseline.statistics.status_distribution, undefined)
  assert.deepEqual(baseline.data_notes, ['未取得选中规则的计数'])
  assert.equal(baseline.source_reference, 'stats:baseline')
  assert.ok(!JSON.stringify(result).includes('私有'))
  assert.equal(result.comparison.delta, undefined)
  assert.equal(result.comparison.change_rate, undefined)
  assert.match(result.read_note, /不补零、不重算同比或环比/)
  assert.match(result.read_note, /当前目录不能证明两期口径一致/)
  assert.match(result.read_note, /缺数据不能解释为零问题/)
  assert.deepEqual(payload, before)
})

test('医生模型上下文仅保留视图与机构，不改动正式授权上下文', () => {
  const context = Object.freeze({
    view: 'doctor',
    institute_id: 'H',
    patient_id: 'patient-internal',
    visit_id: 'visit-internal',
    department: '内科',
  })
  assert.deepEqual(businessModelContext(context), {
    view: 'doctor',
    institute_id: 'H',
    record_scope: '当前页面已选择且服务端授权的本次住院，身份见页面，不猜/复述标识。',
  })
  assert.equal(context.patient_id, 'patient-internal')
  assert.equal(context.visit_id, 'visit-internal')
})

test('管理者模型上下文保留页面范围与日期，返回独立投影', () => {
  const context = Object.freeze({
    view: 'manager',
    institute_id: 'H',
    department: '内科',
    care_phase: 'discharged',
    completed_from: '2026-09-01T00:00:00+08:00',
    completed_to: '2026-09-30T23:59:59+08:00',
  })
  const projected = businessModelContext(context)
  assert.deepEqual(projected, context)
  assert.notEqual(projected, context)
})

test('read_rule使用真实dataclass字段保留质控点时限，标题取同一规则来源', () => {
  // 后端asdict只有qc_point/source_document，title是计算属性，仅在引用中返回。
  const payload = {
    rule: {
      rule_id: 'LX0609-01-02-01',
      source_document: '首次病程',
      qc_point: '入院后8小时内无首次病程记录',
      definition_note: '',
      policy_summary: '当前按客户已确认的《首次病程》质控点执行；新增或变更口径须单独验收。',
    },
    references: [
      {
        id: 'rule:LX0609-01-02-01',
        rule_id: 'LX0609-01-02-01',
        title: '首次病程：入院后8小时内无首次病程记录',
      },
    ],
  }
  const projected = businessModelValue('read_rule', {}, payload)
  assert.equal(projected.rule.qc_point, payload.rule.qc_point)
  assert.equal(projected.rule.source_document, payload.rule.source_document)
  assert.equal(projected.rule.title, payload.references[0].title)
  assert.equal(projected.rule.definition_note, '')
  assert.equal(projected.rule.policy_summary, payload.rule.policy_summary)
  assert.equal(payload.rule.title, undefined)
})

test('提醒与整改仅投影授权本页及范围限制，不透传总量或操作成功', () => {
  for (const kind of ['notifications', 'remediations']) {
    const value = businessModelValue(
      'query_followups',
      {},
      {
        kind,
        state: 'partial',
        page: 2,
        page_size: 5,
        has_more: true,
        coverage_note: '身份不明条目已排除',
        scan_limit_reached: true,
        status_note: '保存状态未重判',
        total: 0,
        success: true,
        internal: '秘密',
        items: [
          {
            id: 'saved',
            record_reference: 'record:authorized-case',
            title: '提醒',
            content: '保存内容',
            status: 'submitted',
            remediation_requirement: '保存要求',
            deadline: '2020-01-01',
            identity: { institute_id: 'H', patient_id: 'P', visit_id: 'V', extra: '秘密' },
            raw_output: '秘密',
            action_success: true,
          },
        ],
      },
    )
    assert.equal(value.state, 'partial')
    assert.equal(value.coverage_note, '身份不明条目已排除')
    assert.equal(value.has_more, true)
    assert.equal(value.scan_limit_reached, true)
    assert.equal(value.items.length, 1)
    assert.equal(value.items[0].record_reference, 'record:authorized-case')
    assert.match(value.read_note, /关联病例卡/)
    assert.equal(value.total, undefined)
    assert.equal(value.success, undefined)
    assert.ok(!JSON.stringify(value).includes('秘密'))
    assert.equal(value.items[0].status, kind === 'remediations' ? 'submitted' : undefined)
    assert.match(value.read_note, /空页.*不能解释为无待办/)
  }
  const empty = businessModelValue(
    'query_followups',
    {},
    { kind: 'notifications', state: 'partial', items: [] },
  )
  assert.deepEqual(empty.items, [])
  assert.equal(empty.total, undefined)
})

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
  assert.equal(issue.evidence, undefined)
  assert.deepEqual(issue.evidence_index, [{ evidence_position: 1 }])
  assert.ok(!JSON.stringify(issue).includes('未发现结果……'))
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
  assert.deepEqual(result.record_page, {
    page: 1,
    page_size: 20,
    total: 6,
    records: [{ record_reference: 'record:bound', title: '已授权病例' }],
  })
  assert.match(result.display_note, /卡片完整展示本页病例/)
  assert.match(result.display_note, /不重复列出部分病例冒充整页/)
  assert.match(result.display_note, /未展示页不能称已读取/)
  assert.match(result.display_note, /未按质控完成期间过滤，不能作期间分母/)
  assert.match(result.display_note, /ready_record_total才是期间内最新可读保存结果数/)
  assert.match(result.display_note, /evaluated_count包含not_executed与not_applicable/)
  assert.match(result.display_note, /不等于完成执行覆盖/)
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

test('单问题保留正式结论建议，摘录仅留原卡片，规则不发送内部目录字段', () => {
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
  assert.equal(issue.evidence, undefined)
  assert.deepEqual(issue.evidence_index, [{ evidence_position: 1, source_ref: 'src-a' }])
  assert.ok(!JSON.stringify(issue).includes(evidence[0].evidence_excerpt))
  assert.equal(JSON.stringify(issue).split('未发现变化').length - 1, 0)
  assert.equal(issue.conclusion, ref.conclusion)
  assert.equal(issue.suggestion, ref.suggestion)
  assert.equal(ref.evidence[0].evidence_excerpt, evidence[0].evidence_excerpt)
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

test('验收摘要与保存缺口只给模型白名单字段，不带入口地址或原始文本', () => {
  const validation = businessModelValue(
    'read_rule_validation',
    { rule_id: 'LX0609-01-01-01' },
    {
      validation_record: {
        rule: { rule_id: 'LX0609-01-01-01' },
        stage: 'pending_approval',
        coverage: { acceptance_cases: 2 },
        runs: [],
        run_limit: 5,
        has_more_runs: false,
        data_notes: [],
        scope_note: '不是当前病例统计',
        entry_path: '/workstation-v4/rules/validation/LX0609-01-01-01',
        internal_debug: '不进入模型',
      },
      references: [{ id: 'rule-validation:LX0609-01-01-01', text: '来源卡全文不进入模型' }],
    },
  )
  assert.equal(validation.id, 'rule-validation:LX0609-01-01-01')
  assert.equal(validation.validation_record.stage, 'pending_approval')
  assert.ok(!('entry_path' in validation.validation_record))
  assert.ok(validation.read_note.includes('不表示结论或批准通过'))
  assert.ok(!JSON.stringify(validation).includes('不进入模型'))
  const gaps = { missing_sources: ['检验结果明细'], projection_notes: ['不重判'] }
  const issue = businessModelValue(
    'read_saved_issue',
    {},
    {
      references: [{ id: 'saved:gap', status: 'data_gap', conclusion: '原保存结论' }],
      source_gaps: gaps,
    },
  )
  assert.deepEqual(issue.source_gaps, gaps)
  assert.equal(issue.conclusion, '原保存结论')
  const plain = businessModelValue('read_saved_issue', {}, { references: [{ id: 'saved:ok' }] })
  assert.ok(!('source_gaps' in plain))
})

test('参考草稿：模型仅收到截断摘录与校验后摘要，不收到草稿全文', () => {
  const facts = businessModelValue(
    'read_draft_facts',
    {},
    {
      result_id: 'result:a',
      conclusion: '原保存结论',
      suggestion: '原保存建议',
      evidence: [{ evidence_position: 1, excerpt: '保存摘录', source_ref: '内部来源不进入模型' }],
      references: [],
    },
  )
  assert.equal(facts.evidence[0].excerpt, '保存摘录')
  assert.ok(!JSON.stringify(facts).includes('内部来源不进入模型'))
  assert.match(facts.draft_note, /待医生补充/)
  const composed = businessModelValue(
    'compose_reference_draft',
    {},
    {
      draft: { result_id: 'result:a', segment_count: 2, placeholder_count: 1 },
      references: [{ id: 'draft:x', text: '草稿全文不进入模型' }],
    },
  )
  assert.equal(composed.id, 'draft:x')
  assert.deepEqual(composed.draft, {
    result_id: 'result:a',
    segment_count: 2,
    placeholder_count: 1,
  })
  assert.ok(!JSON.stringify(composed).includes('草稿全文不进入模型'))
})

test('科室趋势只把各期原值和数据不足给模型，不含病例下钻或派生比例', () => {
  const rows = [1, 2, 3, 4, 5, 6].map((n) => ({
    rule_id: `LX0609-01-01-0${n}`,
    non_compliant_count: n,
    data_gap_count: 0,
    internal_debug: '不进入模型',
  }))
  const value = businessModelValue(
    'trend_statistics',
    {},
    {
      trend: {
        rule_id: null,
        periods: [
          {
            filters: { completed_from: 'a', completed_to: 'b' },
            statistics: {
              kpis: { ready_record_total: 3 },
              rule_distribution: rows,
              record_page: { items: [{ patient_id: 'p' }] },
            },
            data_notes: ['该期说明'],
          },
        ],
        limitations: ['不计算差值'],
      },
      references: [{ id: 'trend:x', text: '卡片全文' }],
    },
  )
  assert.equal(value.id, 'trend:x')
  assert.deepEqual(
    value.periods[0].rules.map((row) => row.rule_id),
    ['LX0609-01-01-06', 'LX0609-01-01-05', 'LX0609-01-01-04', 'LX0609-01-01-03', 'LX0609-01-01-02'],
  )
  assert.equal(value.periods[0].ready_record_total, 3)
  const text = JSON.stringify(value)
  for (const forbidden of ['不进入模型', 'patient_id', '卡片全文'])
    assert.ok(!text.includes(forbidden))
})
