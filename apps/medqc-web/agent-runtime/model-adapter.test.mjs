import test from 'node:test'
import assert from 'node:assert/strict'
import { MedqcModelAdapter } from './model-adapter.mjs'

test('DSH 原生工具结果转换为供应商 tool 消息，中文跨字节保持完整', async () => {
  let body
  const encoded = new TextEncoder().encode(
    'data: {"choices":[{"delta":{"content":"病历证据"},"finish_reason":"stop"}]}\ndata: {"usage":{"prompt_tokens":9,"completion_tokens":4},"choices":[]}',
  )
  const adapter = new MedqcModelAdapter({
    endpoint: 'https://synthetic.invalid/v1',
    apiKey: 'synthetic',
    model: 'synthetic',
    fetchImpl: async (_, options) => {
      body = JSON.parse(options.body)
      return new Response(
        new ReadableStream({
          start(controller) {
            for (const byte of encoded) controller.enqueue(Uint8Array.of(byte))
            controller.close()
          },
        }),
      )
    },
  })
  const events = []
  for await (const event of adapter.stream({
    messages: [
      {
        role: 'user',
        content: [
          {
            type: 'tool-result',
            toolCallId: 'call-1',
            content: [{ type: 'text', text: '保存证据' }],
          },
        ],
      },
    ],
  }))
    events.push(event)
  assert.deepEqual(body.messages, [{ role: 'tool', tool_call_id: 'call-1', content: '保存证据' }])
  assert.equal(events.find((event) => event.type === 'text-delta').text, '病历证据')
  assert.deepEqual(events.find((event) => event.type === 'usage').usage, {
    inputTokens: 9,
    outputTokens: 4,
  })
})
