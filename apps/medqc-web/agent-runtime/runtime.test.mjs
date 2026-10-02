import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'
import { createServer } from 'node:http'
import { LlmAdapter, ToolCallId } from '@deepseek-ai/dsh-llm'
import { createRuntime } from './runtime.mjs'
import { MedqcModelAdapter } from './model-adapter.mjs'

class ScriptedAdapter extends LlmAdapter {
  constructor(steps) {
    super()
    this.steps = steps
    this.requests = []
  }
  async *stream(options) {
    this.requests.push(options)
    const step = this.steps.shift()
    if (step?.delay)
      await new Promise((resolve) =>
        options.signal.addEventListener('abort', resolve, { once: true }),
      )
    options.signal?.throwIfAborted()
    const block = step?.tool
      ? {
          type: 'tool-call',
          id: ToolCallId(randomUUID()),
          name: step.tool,
          arguments: JSON.stringify(step.args || {}),
        }
      : { type: 'text', text: step?.text || '已读取保存结果。' }
    yield { type: 'block-start', index: 0, blockType: block.type }
    yield { type: 'block-end', index: 0, block }
    yield { type: 'usage', usage: { inputTokens: 12, outputTokens: 4 } }
    yield { type: 'finish', reason: { kind: step?.tool ? 'tool-calls' : 'stop' } }
  }
}
const spec = {
  name: 'read_saved_results',
  description: '读取保存结果',
  parameters: { type: 'object', properties: {}, additionalProperties: false },
}
async function fixture(
  steps,
  response,
  toolSpec = spec,
  context = { view: 'doctor', institute_id: 'S', patient_id: 'A', visit_id: 'A1' },
) {
  const root = await mkdtemp(join(tmpdir(), 'medqc-dsh-'))
  const adapter = new ScriptedAdapter(steps),
    callbacks = []
  const fetchImpl = async (url, options) => {
    callbacks.push({
      url,
      authorization: options.headers.Authorization,
      args: JSON.parse(options.body),
    })
    return Response.json(
      response || {
        references: [
          {
            id: 'result:synthetic:2',
            kind: 'saved_result',
            title: '第二条问题',
            status: 'non_compliant',
            conclusion: '合成预期缺项',
            suggestion: '原保存建议',
          },
        ],
      },
    )
  }
  const runtime = await createRuntime({ root, adapter, model: 'synthetic', fetchImpl })
  const sessionId = randomUUID()
  await runtime.create(sessionId, { context, tools: [toolSpec] })
  const body = {
    context,
    tools: [toolSpec],
    run_id: randomUUID(),
    message: '查看当前病例问题',
    backend_url: 'http://127.0.0.1:8003',
    authorization: 'Bearer synthetic',
  }
  return { runtime, root, adapter, callbacks, sessionId, context, body, fetchImpl }
}

test('医生实际模型消息不发送患者及住院标识，正式来源与上下文隔离仍保留', async () => {
  const context = {
    view: 'doctor',
    institute_id: 'S',
    patient_id: 'internal-patient-unique',
    visit_id: 'internal-visit-unique',
  }
  const f = await fixture(
    [{ tool: 'read_saved_results' }, { text: '查看当前病例卡片。' }],
    undefined,
    spec,
    context,
  )
  try {
    const turn = await f.runtime.chat(f.sessionId, f.body)
    assert.equal(turn.status, 'completed')
    for (const request of f.adapter.requests) {
      const messages = JSON.stringify(request.messages)
      for (const forbidden of ['patient_id', 'visit_id', context.patient_id, context.visit_id])
        assert.ok(!messages.includes(forbidden), `模型消息不应包含 ${forbidden}`)
      assert.match(messages, /当前页面已选择且服务端授权的本次住院/)
      assert.match(messages, /身份见页面，不猜\/复述标识/)
    }
    assert.equal(turn.references[0].id, 'result:synthetic:2')
    assert.equal(turn.references[0].conclusion, '合成预期缺项')
    assert.deepEqual(f.context, context)
    await assert.rejects(
      f.runtime.chat(f.sessionId, {
        ...f.body,
        run_id: randomUUID(),
        context: { ...context, patient_id: 'other-patient' },
      }),
      /会话上下文不一致/,
    )
  } finally {
    await f.runtime.close()
  }
})

test('管理者实际模型消息保留原页面科室与质控完成日期范围', async () => {
  const context = {
    view: 'manager',
    institute_id: 'S',
    department: '内科',
    care_phase: 'inpatient',
    completed_from: '2026-09-01T00:00:00+08:00',
    completed_to: '2026-09-30T23:59:59+08:00',
  }
  const f = await fixture([{ text: '请按页面条件查看统计。' }], undefined, spec, context)
  try {
    await f.runtime.chat(f.sessionId, f.body)
    const messages = JSON.stringify(f.adapter.requests[0].messages)
    for (const value of Object.values(context)) assert.ok(messages.includes(value))
    assert.deepEqual(f.context, context)
  } finally {
    await f.runtime.close()
  }
})

test('跨期工具经DSH投影仅传正式原值，两期来源卡完整保存且恢复不泄漏正文与病例标识', async () => {
  const context = {
    view: 'manager',
    institute_id: 'S',
    department: '内科',
    care_phase: 'discharged',
    completed_from: '2026-09-01T00:00:00+08:00',
    completed_to: '2026-09-30T23:59:59+08:00',
  }
  const args = {
    rule_id: 'R',
    baseline_completed_from: '2026-08-01T00:00:00+08:00',
    baseline_completed_to: '2026-08-31T23:59:59+08:00',
  }
  const comparisonSpec = {
    name: 'compare_statistics',
    description: '两期正式统计',
    parameters: {
      type: 'object',
      properties: Object.fromEntries(Object.keys(args).map((key) => [key, { type: 'string' }])),
      required: Object.keys(args),
      additionalProperties: false,
    },
  }
  const references = ['current', 'baseline'].map((key) => ({
    id: `statistics:${key}`,
    kind: 'statistics',
    title: `${key}期间来源`,
    text: `仅来源卡完整正文-${key}`,
  }))
  const payload = {
    metric_owner: '正式结果分析接口',
    references,
    comparison: {
      rule_id: 'R',
      same_rule_version_verified: false,
      limitations: ['不是期间历史快照，未验证历史版本'],
      periods: ['current', 'baseline'].map((key, index) => ({
        key,
        label: index ? '基线期间' : '当前期间',
        source_reference: references[index].id,
        filters: { ...context, patient_id: '工具内部患者标识', visit_id: '工具内部住院标识' },
        data_notes: index ? ['未取得该期规则计数'] : [],
        statistics: {
          scope: { department: '内科', patient_id: '工具内部患者标识' },
          kpis: { ready_record_total: index ? 0 : 3 },
          ...(index
            ? {}
            : {
                rule_distribution: [{ rule_id: 'R', non_compliant_count: 2, evaluated_count: 3 }],
              }),
          record_page: { records: [{ visit_id: '工具内部住院标识' }] },
        },
      })),
    },
  }
  const f = await fixture(
    [{ tool: 'compare_statistics', args }, { text: '两期现存结果原值见来源。' }],
    payload,
    comparisonSpec,
    context,
  )
  try {
    const turn = await f.runtime.chat(f.sessionId, f.body)
    assert.equal(turn.status, 'completed')
    assert.equal(turn.tool_calls, 1)
    assert.deepEqual(f.callbacks[0].args, args)
    assert.deepEqual(turn.references, references)
    const messages = JSON.stringify(f.adapter.requests[1].messages)
    for (const forbidden of [
      '仅来源卡完整正文',
      '工具内部患者标识',
      '工具内部住院标识',
      'patient_id',
      'visit_id',
      'record_page',
    ])
      assert.ok(!messages.includes(forbidden), `比较模型消息不应包含 ${forbidden}`)
    assert.match(messages, /statistics:current/)
    assert.match(messages, /statistics:baseline/)
    assert.match(messages, /non_compliant_count/)
    assert.match(messages, /未取得该期规则计数/)
    assert.match(messages, /基线期间必须由用户明确给出/)
    const restored = await f.runtime.restore(f.sessionId, { context, tools: [comparisonSpec] })
    assert.deepEqual(restored.turns[0].references, references)
  } finally {
    await f.runtime.close()
  }
})

test('比较工具不能将用户明确规则换成另一条，纠正后才查询且保留原生失败调用', async () => {
  const expected = 'LX0609-06-01-05'
  const tool = {
    name: 'compare_statistics',
    description: '比较',
    parameters: {
      type: 'object',
      properties: { rule_id: { type: 'string' } },
      required: ['rule_id'],
    },
  }
  const f = await fixture(
    [
      { tool: tool.name, args: { rule_id: 'LX0609-02-02-03' } },
      { tool: tool.name, args: { rule_id: expected } },
      { text: '已按指定规则读取。' },
    ],
    { comparison: { rule_id: expected, periods: [] }, references: [] },
    tool,
    { view: 'manager', institute_id: 'S', department: '内科' },
  )
  try {
    const turn = await f.runtime.chat(f.sessionId, {
      ...f.body,
      message: `请比较${expected}的两期结果`,
    })
    assert.equal(turn.status, 'completed')
    assert.equal(turn.tool_calls, 2)
    assert.equal(f.callbacks.length, 1)
    assert.equal(f.callbacks[0].args.rule_id, expected)
    assert.match(JSON.stringify(f.adapter.requests[1].messages), /必须使用用户本轮明确指定的规则/)
  } finally {
    await f.runtime.close()
  }
})

test('无编号规则查询经目录候选读取详情，候选不冒充来源且恢复保留规则引用', async () => {
  const root = await mkdtemp(join(tmpdir(), 'medqc-rule-search-'))
  const ruleId = 'LX0609-01-01-01'
  const tools = [
    {
      name: 'search_rules',
      description: '搜索目录',
      parameters: {
        type: 'object',
        properties: { query: { type: 'string' } },
        required: ['query'],
        additionalProperties: false,
      },
    },
    {
      name: 'read_rule',
      description: '读取当前目录',
      parameters: {
        type: 'object',
        properties: { rule_id: { type: 'string' } },
        required: ['rule_id'],
        additionalProperties: false,
      },
    },
  ]
  const adapter = new ScriptedAdapter([
    { tool: 'search_rules', args: { query: '首次病程' } },
    { tool: 'read_rule', args: { rule_id: ruleId } },
    { text: '已读取当前规则，历史执行规则正文未提供。' },
  ])
  const calls = []
  const reference = {
    id: `rule:${ruleId}`,
    kind: 'rule',
    rule_id: ruleId,
    title: '首次病程记录',
    text: '当前目录完整口径',
    locator: '当前目录，非历史',
  }
  const fetchImpl = async (url, options) => {
    calls.push({ name: url.split('/').at(-1), args: JSON.parse(options.body) })
    return Response.json(
      url.endsWith('/search_rules')
        ? {
            rule_candidates: [
              {
                rule_id: ruleId,
                title: reference.title,
                implementation_status: 'active',
                phase_status: 'phase_1_partial',
              },
            ],
            rule_search: {
              query: '首次病程',
              page: 1,
              page_size: 5,
              total: 1,
              returned: 1,
              has_more: false,
            },
            catalog_version: 'current-2',
            scope_note: '目录候选',
          }
        : {
            references: [reference],
            rule: {
              rule_id: ruleId,
              title: reference.title,
              policy_summary: reference.text,
              release_scope: { active_criteria: ['已发布子项'], pending_criteria: ['未发布子项'] },
            },
            catalog_version: 'current-2',
            historical_definition_available: false,
            scope_note: '不是历史规则正文',
          },
    )
  }
  const runtime = await createRuntime({ root, adapter, model: 'synthetic', fetchImpl })
  const sessionId = randomUUID()
  const context = { view: 'doctor', institute_id: 'S', patient_id: 'A', visit_id: 'A1' }
  try {
    await runtime.create(sessionId, { context, tools })
    const turn = await runtime.chat(sessionId, {
      context,
      tools,
      run_id: randomUUID(),
      message: '首次病程记录时限有什么要求？',
      backend_url: 'http://127.0.0.1:8003',
      authorization: 'Bearer synthetic',
    })
    assert.equal(turn.status, 'completed')
    assert.deepEqual(calls, [
      { name: 'search_rules', args: { query: '首次病程' } },
      { name: 'read_rule', args: { rule_id: ruleId } },
    ])
    assert.deepEqual(turn.references, [reference])
    assert.match(JSON.stringify(adapter.requests[2].messages), /未发布子项/)
    assert.match(JSON.stringify(adapter.requests[2].messages), /historical_definition_available/)
    await runtime.close()
    const restored = await createRuntime({
      root,
      adapter: new ScriptedAdapter([]),
      model: 'synthetic',
      fetchImpl,
    })
    try {
      const session = await restored.restore(sessionId, { context, tools })
      assert.deepEqual(session.turns[0], turn)
    } finally {
      await restored.close()
    }
  } finally {
    await runtime.close()
  }
})

test('单问题只给模型证据位置，正式结论和来源卡片原始摘录保持不变', async () => {
  const evidence = [
    {
      source_ref: 'doc-a',
      source_type: 'course',
      record_time: '2026-09-01',
      field_path: 'content',
      evidence_excerpt: '唯一局部摘录，不进入模型……',
    },
  ]
  const reference = {
    id: 'saved:one',
    kind: 'saved_result',
    rule_id: 'R',
    title: '保存问题',
    conclusion: '正式结论保留否定条件',
    suggestion: '正式建议保留原文',
    evidence,
    text: evidence[0].evidence_excerpt,
  }
  const f = await fixture(
    [{ tool: 'read_saved_issue', args: {} }, { text: '保存结论认为存在问题，证据请查看来源卡。' }],
    { references: [reference], evidence },
    { ...spec, name: 'read_saved_issue' },
  )
  try {
    const turn = await f.runtime.chat(f.sessionId, f.body)
    assert.equal(turn.status, 'completed')
    assert.deepEqual(turn.references, [reference])
    const messages = JSON.stringify(f.adapter.requests[1].messages)
    assert.ok(!messages.includes(evidence[0].evidence_excerpt))
    assert.match(messages, /evidence_position/)
    assert.match(messages, /doc-a/)
    assert.match(messages, /正式结论保留否定条件/)
    assert.match(messages, /正式建议保留原文/)
    const restored = await f.runtime.restore(f.sessionId, {
      context: f.context,
      tools: f.body.tools,
    })
    assert.deepEqual(restored.turns[0].references, [reference])
  } finally {
    await f.runtime.close()
  }
})

test('提醒只读工具保留覆盖限制且不生成引用或操作成功', async () => {
  const root = await mkdtemp(join(tmpdir(), 'medqc-followups-'))
  const tools = [
    {
      name: 'query_followups',
      description: '读取台账',
      parameters: {
        type: 'object',
        properties: { kind: { type: 'string', enum: ['notifications', 'remediations'] } },
        required: ['kind'],
        additionalProperties: false,
      },
    },
  ]
  const adapter = new ScriptedAdapter([
    { tool: 'query_followups', args: { kind: 'notifications' } },
    { text: '本页没有可核验条目，不能据此判断没有待办。' },
  ])
  const calls = []
  const runtime = await createRuntime({
    root,
    adapter,
    model: 'synthetic',
    fetchImpl: async (url, options) => {
      calls.push({ url, body: JSON.parse(options.body) })
      return Response.json({
        kind: 'notifications',
        state: 'partial',
        items: [],
        page: 1,
        page_size: 5,
        has_more: true,
        coverage_note: '身份无法核验的条目已排除',
        status_note: '未执行任何办理',
        total: 0,
      })
    },
  })
  const sessionId = randomUUID()
  const context = { view: 'doctor', institute_id: 'H', patient_id: 'P', visit_id: 'V' }
  try {
    await runtime.create(sessionId, { context, tools })
    const turn = await runtime.chat(sessionId, {
      context,
      tools,
      run_id: randomUUID(),
      message: '这份病例有提醒吗？',
      backend_url: 'http://127.0.0.1:8003',
      authorization: 'Bearer synthetic',
    })
    assert.equal(turn.status, 'completed')
    assert.equal(calls.length, 1)
    assert.ok(calls[0].url.endsWith('/query_followups'))
    assert.deepEqual(calls[0].body, { kind: 'notifications' })
    assert.deepEqual(turn.references, [])
    const messages = JSON.stringify(adapter.requests[1].messages)
    assert.match(messages, /身份无法核验的条目已排除/)
    assert.match(messages, /未执行任何办理/)
    assert.ok(!messages.includes('"total":0'))
  } finally {
    await runtime.close()
  }
})

test('旧医生历史恢复后使用当前工具范围，历史统计调用不能重新执行', async () => {
  const oldStatistics = { ...spec, name: 'query_statistics' }
  const f = await fixture(
    [{ tool: 'query_statistics' }, { text: '旧轮次。' }],
    { statistics: {}, references: [] },
    oldStatistics,
  )
  await f.runtime.chat(f.sessionId, f.body)
  await f.runtime.close()
  const adapter = new ScriptedAdapter([
    { tool: 'query_statistics' },
    { tool: 'read_saved_results' },
    { text: '已读取当前病例。' },
  ])
  const restored = await createRuntime({
    root: f.root,
    adapter,
    model: 'synthetic',
    fetchImpl: f.fetchImpl,
  })
  const current = { ...f.body, tools: [spec] }
  try {
    await restored.restore(f.sessionId, current)
    const turn = await restored.chat(f.sessionId, { ...current, run_id: randomUUID() })
    assert.equal(turn.status, 'completed')
    assert.equal(f.callbacks.length, 2)
    assert.ok(f.callbacks[1].url.endsWith('/tools/read_saved_results'))
    for (const request of adapter.requests)
      assert.deepEqual(
        request.tools.map((tool) => tool.name),
        ['read_saved_results'],
      )
    assert.ok(
      adapter.requests[1].messages.some((message) =>
        message.content.some((block) => block.type === 'tool-result' && block.isError),
      ),
    )
  } finally {
    await restored.close()
  }
})

test('状态筛选数组在原生 schema 和业务传输中保持数组类型', async () => {
  const toolSpec = {
    ...spec,
    parameters: {
      type: 'object',
      properties: {
        statuses: { type: 'array', items: { type: 'string', enum: ['non_compliant', 'data_gap'] } },
      },
      additionalProperties: false,
    },
  }
  const f = await fixture(
    [{ tool: spec.name, args: { statuses: ['non_compliant'] } }, { text: '已读取筛选范围。' }],
    undefined,
    toolSpec,
  )
  try {
    const turn = await f.runtime.chat(f.sessionId, f.body)
    assert.equal(turn.status, 'completed')
    assert.equal(f.adapter.requests[0].tools[0].parameters.properties.statuses.type, 'array')
    assert.deepEqual(f.callbacks[0].args.statuses, ['non_compliant'])
  } finally {
    await f.runtime.close()
  }
})

test('saved_text也只向模型传索引，完整卡片持久化，空筛选不冒用上一页来源', async () => {
  const canonical = {
    state: 'ready',
    job_id: 'task-a',
    references: [
      {
        id: 'result:second',
        position: 2,
        kind: 'saved_result',
        title: '第二条',
        status: 'data_gap',
        conclusion: '完整卡片专有文字，不发送模型',
        suggestion: '原保存建议',
      },
    ],
    result_page: {
      detail: 'saved_text',
      page: 1,
      page_size: 10,
      total: 75,
      matched_total: 1,
      returned: 1,
      has_more: false,
      statuses: ['data_gap'],
      reference_ids: ['result:second'],
      status_counts: { data_gap: 1, compliant: 74 },
    },
  }
  const f = await fixture(
    [
      { tool: spec.name },
      { text: '查看下方第二条卡片。' },
      { tool: spec.name },
      { text: '本次筛选没有匹配项，其他类别仍有记录。' },
    ],
    canonical,
  )
  try {
    const first = await f.runtime.chat(f.sessionId, f.body)
    assert.equal(first.references[0].conclusion, canonical.references[0].conclusion)
    assert.equal(first.references[0].suggestion, canonical.references[0].suggestion)
    assert.equal(first.result_pages[0].total, 75)
    assert.ok(!JSON.stringify(f.adapter.requests[1].messages).includes('完整卡片专有文字'))
    assert.ok(!JSON.stringify(f.adapter.requests[1].messages).includes('原保存建议'))
    canonical.references = []
    canonical.result_page = {
      ...canonical.result_page,
      statuses: ['uncertain'],
      matched_total: 0,
      returned: 0,
      reference_ids: [],
    }
    const second = await f.runtime.chat(f.sessionId, { ...f.body, run_id: randomUUID() })
    assert.deepEqual(second.references, [])
    assert.equal(second.reference_scope, undefined)
    await f.runtime.close()
    const restored = await createRuntime({
      root: f.root,
      adapter: new ScriptedAdapter([{ text: '沿用来源。' }]),
      model: 'synthetic',
      fetchImpl: f.fetchImpl,
    })
    try {
      const session = await restored.restore(f.sessionId, { context: f.context, tools: [spec] })
      assert.deepEqual(session.turns[0].references, first.references)
      assert.equal(session.turns[0].result_pages[0].matched_total, 1)
    } finally {
      await restored.close()
    }
  } finally {
    await f.runtime.close()
  }
})

test('真实 DSH 内核调工具、续问、持久化恢复与幂等回读', async () => {
  const f = await fixture([
    { tool: spec.name },
    { text: '第二条存在缺项，建议保留原文。' },
    { text: '仍是上一轮第二条。' },
  ])
  try {
    const result = await f.runtime.chat(f.sessionId, f.body)
    assert.equal(result.status, 'completed')
    assert.equal(result.tool_calls, 1)
    assert.equal(result.model_calls, 2)
    assert.equal(result.references[0].suggestion, '原保存建议')
    assert.deepEqual(result.usage, { input_tokens: 24, output_tokens: 8 })
    assert.equal(f.callbacks[0].authorization, 'Bearer synthetic')
    assert.deepEqual(await f.runtime.chat(f.sessionId, f.body), result)
    const second = await f.runtime.chat(f.sessionId, {
      ...f.body,
      run_id: randomUUID(),
      message: '第二条为什么？',
      reference_id: result.references[0].id,
    })
    assert.equal(second.status, 'completed')
    assert.equal(second.reference_scope, 'prior_turns')
    assert.equal(second.question, '第二条为什么？')
    assert.ok(
      f.adapter.requests[2].messages.some((m) =>
        m.content.some(
          (block) => block.type === 'text' && block.text.includes(result.references[0].id),
        ),
      ),
    )
    assert.equal(second.references[0].id, result.references[0].id)
    assert.ok(
      f.adapter.requests[2].messages.some((m) =>
        m.content.some((block) => block.type === 'tool-result'),
      ),
    )
    await f.runtime.close()
    const restored = await createRuntime({
      root: f.root,
      adapter: new ScriptedAdapter([]),
      model: 'synthetic',
      fetchImpl: f.fetchImpl,
    })
    try {
      const session = await restored.restore(f.sessionId, { context: f.context, tools: [spec] })
      assert.equal(session.turns.length, 2)
      assert.equal(session.turns[0].run_id, f.body.run_id)
    } finally {
      await restored.close()
    }
  } finally {
    await f.runtime.close()
  }
})

test('停止实际中断 DSH 原生请求；停止先到时不发模型请求', async () => {
  const f = await fixture([{ delay: true }])
  try {
    const running = f.runtime.chat(f.sessionId, f.body)
    await new Promise((resolve) => setTimeout(resolve, 50))
    f.runtime.stop(f.sessionId, f.body.run_id)
    assert.equal((await running).status, 'stopped')
    const future = { ...f.body, run_id: randomUUID() }
    f.runtime.stop(f.sessionId, future.run_id)
    assert.equal((await f.runtime.chat(f.sessionId, future)).status, 'stopped')
    assert.equal(f.adapter.requests.length, 1)
  } finally {
    await f.runtime.close()
  }
})

test('供应商请求在首个流片段前取消仍保存停止状态', async () => {
  const f = await fixture([])
  await f.runtime.close()
  const adapter = new MedqcModelAdapter({
    endpoint: 'https://synthetic.invalid/v1',
    apiKey: 'synthetic',
    model: 'synthetic',
    fetchImpl: (_, options) =>
      new Promise((_, reject) =>
        options.signal.addEventListener(
          'abort',
          () => {
            // 模拟 Node fetch 对取消原因增加不可枚举 stack 的实际行为。
            Object.defineProperty(options.signal.reason, 'stack', {
              value: 'synthetic_fetch_stack',
              enumerable: false,
              configurable: true,
            })
            reject(options.signal.reason)
          },
          { once: true },
        ),
      ),
  })
  const runtime = await createRuntime({
    root: f.root,
    adapter,
    model: 'synthetic',
    fetchImpl: f.fetchImpl,
  })
  try {
    await runtime.create(f.sessionId, { context: f.context, tools: [spec] })
    const running = runtime.chat(f.sessionId, f.body)
    await new Promise((resolve) => setTimeout(resolve, 50))
    runtime.stop(f.sessionId, f.body.run_id)
    assert.equal((await running).status, 'stopped')
    assert.equal(
      (await runtime.restore(f.sessionId, { context: f.context, tools: [spec] })).turns[0].status,
      'stopped',
    )
  } finally {
    await runtime.close()
  }
})

test('会话上下文不可替换，工具预算最多八次实际业务读取', async () => {
  const f = await fixture(Array.from({ length: 10 }, () => ({ tool: spec.name })))
  try {
    await assert.rejects(
      f.runtime.chat(f.sessionId, { ...f.body, context: { ...f.context, patient_id: 'B' } }),
      /上下文/,
    )
    const result = await f.runtime.chat(f.sessionId, f.body)
    assert.equal(result.status, 'stopped')
    assert.equal(f.callbacks.length, 8)
  } finally {
    await f.runtime.close()
  }
})

test('知识库必须显式限定，未配置时不注册规范或委托问答工具', async () => {
  const f = await fixture([{ text: '知识库尚未配置，无法提供规范原文。' }])
  try {
    const result = await f.runtime.chat(f.sessionId, f.body)
    assert.equal(result.references.length, 0)
    assert.equal(
      f.adapter.requests[0].tools.some((t) => t.name.startsWith('weknora')),
      false,
    )
    assert.match(result.answer, /未配置/)
  } finally {
    await f.runtime.close()
  }
})

test('官方 WeKnora 插件的截断、名称命中、分页和知识库限制（合成 HTTP）', async () => {
  const requests = []
  const server = createServer(async (request, response) => {
    const url = new URL(request.url, 'http://synthetic')
    let body = ''
    for await (const chunk of request) body += chunk
    requests.push({ path: url.pathname, body: body ? JSON.parse(body) : undefined })
    response.setHeader('Content-Type', 'application/json')
    const data = url.pathname.endsWith('/knowledge-search')
      ? {
          data: [
            {
              id: 'chunk-1',
              knowledge_id: 'doc-1',
              knowledge_title: '合成规范',
              chunk_index: 0,
              content: '合成原文'.repeat(700),
            },
          ],
        }
      : url.pathname.endsWith('/knowledge/search')
        ? {
            data: [
              { id: 'doc-named', title: '名称命中文档', knowledge_base_id: 'kb-synthetic' },
              { id: 'doc-outside', title: '范围外文档', knowledge_base_id: 'kb-outside' },
            ],
          }
        : url.pathname.includes('/chunks/')
          ? {
              data: [{ chunk_index: 0, content: '合成规范正文' }],
              page: 1,
              page_size: 10,
              total: 11,
            }
          : {
              data: {
                title: '名称命中文档',
                knowledge_base_id: 'kb-synthetic',
                description: '这是生成摘要，不能冒充原文',
              },
            }
    response.end(JSON.stringify(data))
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const root = await mkdtemp(join(tmpdir(), 'medqc-weknora-'))
  const adapter = new ScriptedAdapter([
    { tool: 'weknora_search', args: { query: '合成规范' } },
    { tool: 'weknora_read_document', args: { knowledge_id: 'doc-named', page: 1, page_size: 10 } },
    { text: '已读取合成规范正文，仍有下一页。' },
    { tool: 'weknora_search', args: { query: '范围外', knowledge_base_ids: ['kb-outside'] } },
    { text: '范围外检索被拒绝。' },
  ])
  const runtime = await createRuntime({
    root,
    adapter,
    model: 'synthetic',
    weknora: {
      baseUrl: `http://127.0.0.1:${server.address().port}`,
      knowledgeBaseIds: ['kb-synthetic'],
    },
  })
  const sessionId = randomUUID(),
    context = { view: 'manager' }
  const body = { context, tools: [], run_id: randomUUID(), message: '读取合成规范' }
  try {
    await runtime.create(sessionId, body)
    const turn = await runtime.chat(sessionId, body)
    assert.equal(turn.status, 'completed')
    assert.ok(turn.references.some((r) => r.locator.includes('已截断')))
    assert.ok(turn.references.some((r) => r.id === 'guideline:doc-named:title'))
    const original = turn.references.find((r) => r.id === 'guideline:doc-named:page-1')
    assert.match(original.locator, /尚有未读取内容/)
    assert.equal(original.text, '合成规范正文')
    assert.equal(
      turn.references.some((r) => r.knowledge_id === 'doc-outside'),
      false,
    )
    assert.deepEqual(
      requests.find((r) => r.path.endsWith('/knowledge-search')).body.knowledge_base_ids,
      ['kb-synthetic'],
    )
    assert.equal(
      adapter.requests[0].tools.some((t) => t.name === 'weknora_ask'),
      false,
    )
    const before = requests.length
    await runtime.chat(sessionId, { ...body, run_id: randomUUID(), message: '查范围外知识库' })
    assert.equal(requests.length, before)
    const reread = await runtime.reference(sessionId, { ...body, reference_id: original.id })
    assert.equal(reread.text, '合成规范正文')
  } finally {
    await runtime.close()
    await new Promise((resolve) => server.close(resolve))
  }
})

test('模型准备阶段失败仍从 DSH 原生事件恢复失败轮次', async () => {
  const f = await fixture([])
  f.adapter.resolveModel = async () => {
    throw new Error('合成模型配置失败')
  }
  try {
    const result = await f.runtime.chat(f.sessionId, f.body)
    assert.equal(result.run_id, f.body.run_id)
    assert.equal(result.status, 'failed')
    assert.equal(result.tool_calls, 0)
    assert.equal(result.usage, undefined)
  } finally {
    await f.runtime.close()
  }
})

test('工具4xx时把后端简短中文原因交给模型改写，5xx不透传', async () => {
  const draftSpec = {
    name: 'compose_reference_draft',
    description: '提交参考草稿',
    parameters: { type: 'object', properties: {}, additionalProperties: true },
  }
  for (const [status, detail, expected] of [
    [422, '第1段含所引证据未出现的数值，请改为待医生补充', /HTTP 422：第1段含所引证据未出现的数值/],
    [503, '内部连接串不应出现', /HTTP 503(?!：)/],
  ]) {
    const f = await fixture(
      [{ tool: 'compose_reference_draft' }, { text: '已改写。' }],
      undefined,
      draftSpec,
    )
    const runtime = await createRuntime({
      root: f.root,
      adapter: f.adapter,
      model: 'synthetic',
      fetchImpl: async () => Response.json({ detail }, { status }),
    })
    try {
      await runtime.create(f.sessionId, { context: f.context, tools: [draftSpec] })
      await runtime.chat(f.sessionId, f.body)
      const followup = JSON.stringify(f.adapter.requests.at(-1).messages)
      assert.match(followup, expected)
      if (status >= 500) assert.ok(!followup.includes(detail))
    } finally {
      await runtime.close()
      await f.runtime.close()
    }
  }
})
test('@selected 只替换为本轮用户所选来源，未选择时原样交后端拒绝', async () => {
  for (const [referenceId, expected] of [
    ['result:job:rec:LX0609-01-01-01', 'result:job:rec:LX0609-01-01-01'],
    [undefined, '@selected'],
  ]) {
    const f = await fixture([
      { tool: 'read_saved_results', args: { result_id: '@selected', page: 1 } },
      { text: '已读取。' },
    ])
    try {
      await f.runtime.chat(f.sessionId, {
        ...f.body,
        ...(referenceId ? { reference_id: referenceId } : {}),
      })
      assert.equal(f.callbacks[0].args.result_id, expected)
      assert.equal(f.callbacks[0].args.page, 1)
    } finally {
      await f.runtime.close()
    }
  }
})

test('预览规则必须是用户点名的规则，@selected 取所选问题规则', async () => {
  const previewSpec = {
    name: 'preview_recheck',
    description: '复检预览',
    parameters: { type: 'object', properties: {}, additionalProperties: true },
  }
  const f = await fixture(
    [
      { tool: 'preview_recheck', args: { rule_ids: ['LX0609-25-07-18'] } },
      { tool: 'preview_recheck', args: { rule_ids: ['LX0609-06-01-04'] } },
      { text: '已生成预览。' },
    ],
    { references: [] },
    previewSpec,
  )
  try {
    await f.runtime.chat(f.sessionId, { ...f.body, message: '帮我复检 LX0609-06-01-04 这一条' })
    // 编造的编号在请求后端前被拒绝，只有纠正后的请求到达后端。
    assert.deepEqual(
      f.callbacks.map((call) => call.args.rule_ids),
      [['LX0609-06-01-04']],
    )
    assert.match(
      JSON.stringify(f.adapter.requests[1].messages),
      /预览只能使用用户本轮明确指定的规则/,
    )
  } finally {
    await f.runtime.close()
  }
  const g = await fixture(
    [{ tool: 'preview_recheck', args: { rule_ids: ['@selected'] } }, { text: '已生成预览。' }],
    { references: [] },
    previewSpec,
  )
  try {
    await g.runtime.chat(g.sessionId, {
      ...g.body,
      message: '我改好了，再检查一下',
      reference_id: 'result:job:rec:LX0609-06-01-04',
    })
    assert.deepEqual(g.callbacks[0].args.rule_ids, ['LX0609-06-01-04'])
  } finally {
    await g.runtime.close()
  }
})
