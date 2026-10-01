import { createServer } from 'node:http'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { timingSafeEqual } from 'node:crypto'
import { Buffer } from 'node:buffer'
import { createRuntime } from './runtime.mjs'
import { MedqcModelAdapter } from './model-adapter.mjs'

process.loadEnvFile(fileURLToPath(new URL('../backend/.env', import.meta.url)))
const key = process.env.MEDQC_AGENT_RUNTIME_KEY
if (!key) throw new Error('backend/.env 缺少 MEDQC_AGENT_RUNTIME_KEY')
const model = process.env.LLM_MODEL
// 与现有 MedQC 默认供应商使用相同凭据优先级，不另选模型。
const provider = process.env.LLM_DEFAULT_PROVIDER
const endpoint =
  (provider === 'alibaba'
    ? process.env.DASHSCOPE_BASE_URL
    : provider === 'deepseek'
      ? process.env.DEEPSEEK_BASE_URL
      : undefined) || process.env.LLM_API_ENDPOINT
const apiKey =
  (provider === 'alibaba'
    ? process.env.DASHSCOPE_API_KEY
    : provider === 'deepseek'
      ? process.env.DEEPSEEK_API_KEY
      : undefined) || process.env.LLM_API_KEY
if (!model || !endpoint || !apiKey) throw new Error('backend/.env 缺少既有模型配置')
const kbIds = (process.env.WEKNORA_KNOWLEDGE_BASE_IDS || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean)
const wkUrl = process.env.WEKNORA_BASE_URL
if (wkUrl && !kbIds.length) throw new Error('WeKnora 服务必须同时配置允许检索的知识库 ID')
const runtime = await createRuntime({
  root: resolve(
    fileURLToPath(new URL('../.tmp/0910-full-audit/business-agent-dsh-private', import.meta.url)),
  ),
  model,
  adapter: new MedqcModelAdapter({ endpoint, apiKey, model }),
  weknora: wkUrl
    ? {
        baseUrl: wkUrl,
        apiKey: process.env.WEKNORA_API_KEY,
        tenantId: process.env.WEKNORA_TENANT_ID,
        knowledgeBaseIds: kbIds,
      }
    : undefined,
})
const server = createServer(async (request, response) => {
  response.setHeader('Content-Type', 'application/json; charset=utf-8')
  const received = Buffer.from(String(request.headers['x-medqc-runtime-key'] || ''))
  const expected = Buffer.from(key)
  if (received.length !== expected.length || !timingSafeEqual(received, expected)) {
    response.writeHead(401).end(JSON.stringify({ error: '运行时认证失败' }))
    return
  }
  try {
    const chunks = []
    let bodyBytes = 0
    for await (const chunk of request) {
      bodyBytes += chunk.length
      if (bodyBytes > 256000) throw Object.assign(new Error('请求过大'), { status: 413 })
      chunks.push(chunk)
    }
    const bodyText = Buffer.concat(chunks).toString('utf8')
    const body = bodyText ? JSON.parse(bodyText) : {}
    const url = new URL(request.url, 'http://127.0.0.1')
    if (url.pathname === '/health' && request.method === 'GET') {
      response.end(JSON.stringify(runtime.health()))
      return
    }
    const match = url.pathname.match(
      /^\/sessions\/([a-f0-9-]{36})(?:\/(restore|chat|stop|reference))?$/,
    )
    if (!match || request.method !== 'POST') {
      response.writeHead(404).end('{}')
      return
    }
    const [, sessionId, action] = match
    const result = !action
      ? await runtime.create(sessionId, body)
      : action === 'restore'
        ? await runtime.restore(sessionId, body)
        : action === 'chat'
          ? await runtime.chat(sessionId, body)
          : action === 'reference'
            ? await runtime.reference(sessionId, body)
            : runtime.stop(sessionId, body.run_id)
    response.end(JSON.stringify(result))
  } catch (error) {
    response
      .writeHead(error.status || 503)
      .end(JSON.stringify({ error: '助手步骤执行失败，请检查配置与服务状态' }))
  }
})
server.listen(8013, '127.0.0.1', () =>
  console.log(
    `MedQC DSH 0.1.5-rc.2 · ${model} · http://127.0.0.1:8013 · WeKnora ${wkUrl ? '已配置，兼容待验证' : '未配置'}`,
  ),
)
for (const signal of ['SIGINT', 'SIGTERM'])
  process.once(signal, async () => {
    server.close()
    await runtime.close()
    process.exit(0)
  })
