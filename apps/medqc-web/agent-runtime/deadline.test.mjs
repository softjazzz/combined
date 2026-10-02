import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'
import { createRuntime } from './runtime.mjs'
import { MedqcModelAdapter } from './model-adapter.mjs'

const context = { view: 'doctor', institute_id: 'synthetic', patient_id: 'A', visit_id: 'V' }
const complete = () =>
  new Response(
    'data: {"choices":[{"delta":{"content":"完成"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
  )

for (const phase of ['connection', 'body']) {
  test(`真实传输信号中止${phase}等待并持久化停止，重启不重发`, { timeout: 5000 }, async () => {
    const root = await mkdtemp(join(tmpdir(), 'medqc-deadline-'))
    let calls = 0
    let aborted = false
    const adapter = new MedqcModelAdapter({
      endpoint: 'https://synthetic.invalid/v1',
      apiKey: 'synthetic',
      model: 'synthetic',
      fetchImpl: (_, { signal }) => {
        calls += 1
        if (calls > 1) return Promise.resolve(complete())
        assert.equal(signal.aborted, false)
        if (phase === 'connection')
          return new Promise((_, reject) => {
            signal.addEventListener(
              'abort',
              () => {
                aborted = true
                reject(signal.reason)
              },
              { once: true },
            )
          })
        return Promise.resolve(
          new Response(
            new ReadableStream({
              start(controller) {
                signal.addEventListener(
                  'abort',
                  () => {
                    aborted = true
                    controller.error(signal.reason)
                  },
                  { once: true },
                )
              },
            }),
          ),
        )
      },
    })
    let runtime = await createRuntime({ root, adapter, model: 'synthetic', budgetMs: 80 })
    const sessionId = randomUUID()
    const body = { context, tools: [], run_id: randomUUID(), message: '合成阻塞请求' }
    try {
      await runtime.create(sessionId, body)
      const started = Date.now()
      const turn = await runtime.chat(sessionId, body)
      assert.equal(aborted, true, '必须实际取消传输，不只是结束chat等待')
      assert.equal(turn.status, 'stopped')
      assert.ok(Date.now() - started < 1500)
      assert.equal(calls, 1)
      await runtime.close()
      runtime = await createRuntime({ root, adapter, model: 'synthetic', budgetMs: 1000 })
      const restored = await runtime.restore(sessionId, body)
      assert.equal(restored.turns[0].status, 'stopped')
      assert.equal(calls, 1, '恢复不重新启动旧模型请求')
      assert.equal((await runtime.chat(sessionId, body)).status, 'stopped')
      assert.equal(calls, 1, '同run重试沿用持久化终态')
      const next = await runtime.chat(sessionId, {
        ...body,
        run_id: randomUUID(),
        message: '下一轮',
      })
      assert.equal(next.status, 'completed')
      assert.equal(calls, 2)
    } finally {
      await runtime.close()
    }
  })
}

test('用户停止也立即中止连接并保留原生终态', { timeout: 5000 }, async () => {
  const root = await mkdtemp(join(tmpdir(), 'medqc-stop-'))
  let arrived
  const started = new Promise((resolve) => {
    arrived = resolve
  })
  let aborted = false
  const adapter = new MedqcModelAdapter({
    endpoint: 'https://synthetic.invalid/v1',
    apiKey: 'synthetic',
    model: 'synthetic',
    fetchImpl: (_, { signal }) =>
      new Promise((_, reject) => {
        signal.addEventListener(
          'abort',
          () => {
            aborted = true
            reject(signal.reason)
          },
          { once: true },
        )
        arrived()
      }),
  })
  const runtime = await createRuntime({ root, adapter, model: 'synthetic', budgetMs: 4000 })
  const sessionId = randomUUID()
  const body = { context, tools: [], run_id: randomUUID(), message: '合成停止' }
  try {
    await runtime.create(sessionId, body)
    const pending = runtime.chat(sessionId, body)
    await started
    runtime.stop(sessionId, body.run_id)
    assert.equal((await pending).status, 'stopped')
    assert.equal(aborted, true)
    assert.equal((await runtime.restore(sessionId, body)).turns[0].status, 'stopped')
  } finally {
    await runtime.close()
  }
})

test('六次工具后第七次模型阻塞仍受整轮deadline约束', { timeout: 5000 }, async () => {
  const root = await mkdtemp(join(tmpdir(), 'medqc-multistep-deadline-'))
  let calls = 0
  let aborted = false
  let toolCalls = 0
  const adapter = new MedqcModelAdapter({
    endpoint: 'https://synthetic.invalid/v1',
    apiKey: 'synthetic',
    model: 'synthetic',
    fetchImpl: (_, { signal }) => {
      calls += 1
      if (calls <= 6)
        return Promise.resolve(
          new Response(
            `data: ${JSON.stringify({
              choices: [
                {
                  delta: {
                    tool_calls: [
                      {
                        index: 0,
                        id: `call-${calls}`,
                        function: { name: 'read_saved_results', arguments: '{}' },
                      },
                    ],
                  },
                  finish_reason: 'tool_calls',
                },
              ],
            })}\n\ndata: [DONE]\n\n`,
          ),
        )
      return new Promise((_, reject) =>
        signal.addEventListener(
          'abort',
          () => {
            aborted = true
            reject(signal.reason)
          },
          { once: true },
        ),
      )
    },
  })
  const runtime = await createRuntime({
    root,
    adapter,
    model: 'synthetic',
    budgetMs: 400,
    fetchImpl: async () => {
      toolCalls += 1
      return Response.json({ state: 'ready', references: [] })
    },
  })
  const body = {
    context,
    run_id: randomUUID(),
    message: '合成多步阻塞',
    backend_url: 'http://synthetic',
    authorization: 'synthetic',
    tools: [
      {
        name: 'read_saved_results',
        description: '合成读取',
        parameters: { type: 'object', properties: {} },
      },
    ],
  }
  const sessionId = randomUUID()
  try {
    await runtime.create(sessionId, body)
    const turn = await runtime.chat(sessionId, body)
    assert.equal(calls, 7)
    assert.equal(toolCalls, 6)
    assert.equal(aborted, true)
    assert.equal(turn.status, 'stopped')
    assert.ok(turn.elapsed_ms < 1500)
  } finally {
    await runtime.close()
  }
})

test('原生cancel未传播时独立传输deadline仍取消请求并记录失败终态', { timeout: 5000 }, async () => {
  const root = await mkdtemp(join(tmpdir(), 'medqc-independent-abort-'))
  let aborted = false
  const adapter = new MedqcModelAdapter({
    endpoint: 'https://synthetic.invalid/v1',
    apiKey: 'synthetic',
    model: 'synthetic',
    fetchImpl: (_, { signal }) =>
      new Promise((_, reject) => {
        signal.addEventListener(
          'abort',
          () => {
            aborted = true
            reject(signal.reason)
          },
          { once: true },
        )
      }),
  })
  const runtime = await createRuntime({ root, adapter, model: 'synthetic', budgetMs: 80 })
  const sessionId = randomUUID()
  const body = { context, tools: [], run_id: randomUUID(), message: '合成取消传播故障' }
  let agent, originalCancel
  try {
    await runtime.create(sessionId, body)
    agent = runtime.ctx.agents.get(sessionId)
    originalCancel = agent.cancel
    // 受控注入取消传播故障；独立信号必须实际中止底层请求，不让whenIdle挂起。
    agent.cancel = () => {}
    const turn = await runtime.chat(sessionId, body)
    assert.equal(aborted, true)
    assert.equal(turn.status, 'failed')
    assert.equal((await runtime.restore(sessionId, body)).turns[0].status, 'failed')
  } finally {
    if (agent) agent.cancel = originalCancel
    await runtime.close()
  }
})
