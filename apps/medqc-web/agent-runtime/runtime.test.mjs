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
async function fixture(steps) {
  const root = await mkdtemp(join(tmpdir(), 'medqc-dsh-'))
  const adapter = new ScriptedAdapter(steps),
    callbacks = []
  const fetchImpl = async (url, options) => {
    callbacks.push({ url, authorization: options.headers.Authorization })
    return Response.json({
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
    })
  }
  const runtime = await createRuntime({ root, adapter, model: 'synthetic', fetchImpl })
  const sessionId = randomUUID(),
    context = { view: 'doctor', institute_id: 'S', patient_id: 'A', visit_id: 'A1' }
  await runtime.create(sessionId, { context, tools: [spec] })
  const body = {
    context,
    tools: [spec],
    run_id: randomUUID(),
    message: '查看当前病例问题',
    backend_url: 'http://127.0.0.1:8003',
    authorization: 'Bearer synthetic',
  }
  return { runtime, root, adapter, callbacks, sessionId, context, body, fetchImpl }
}

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
