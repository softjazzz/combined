import { LlmAdapter, LlmError, ToolCallId } from '@deepseek-ai/dsh-llm'

// 只适配供应商协议；多轮与工具调度始终由 DSH AgentLoop 执行。
export class MedqcModelAdapter extends LlmAdapter {
  constructor({ endpoint, apiKey, model, fetchImpl = fetch }) {
    super()
    this.endpoint = endpoint.endsWith('/chat/completions')
      ? endpoint
      : `${endpoint.replace(/\/$/, '')}/chat/completions`
    this.apiKey = apiKey
    this.model = model
    this.fetchImpl = fetchImpl
  }
  async resolveModel(provider, model) {
    if (model !== this.model) throw new LlmError('模型未配置', 'MODEL_NOT_CONFIGURED')
    return { provider, id: model, name: model }
  }
  async *stream(options) {
    const messages = []
    for (const message of options.messages) {
      if (message.content.some((block) => block.type === 'tool-result')) {
        for (const block of message.content) {
          if (block.type === 'tool-result')
            messages.push({
              role: 'tool',
              tool_call_id: block.toolCallId,
              content: block.content
                .filter((b) => b.type === 'text')
                .map((b) => b.text)
                .join('\n'),
            })
        }
        continue
      }
      const text = message.content
        .filter((b) => b.type === 'text')
        .map((b) => b.text)
        .join('\n')
      const calls = message.content
        .filter((b) => b.type === 'tool-call')
        .map((b) => ({
          id: b.id,
          type: 'function',
          function: { name: b.name, arguments: b.arguments },
        }))
      messages.push({
        role: message.role,
        content: text || (calls.length ? null : ''),
        ...(calls.length ? { tool_calls: calls } : {}),
      })
    }
    const response = await this.fetchImpl(this.endpoint, {
      method: 'POST',
      signal: options.signal,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${this.apiKey}` },
      body: JSON.stringify({
        model: this.model,
        messages,
        stream: true,
        stream_options: { include_usage: true },
        max_tokens: options.maxTokens || 2048,
        enable_thinking: false,
        ...(options.tools?.length
          ? { tools: options.tools.map((tool) => ({ type: 'function', function: tool })) }
          : {}),
      }),
    })
    if (!response.ok) throw new LlmError(`模型服务返回 HTTP ${response.status}`, 'MODEL_HTTP_ERROR')
    let buffer = '',
      text = '',
      finish = '',
      usage
    const calls = new Map(),
      decoder = new TextDecoder()
    const consume = (line) => {
      if (!line.startsWith('data:') || line.slice(5).trim() === '[DONE]') return
      const payload = JSON.parse(line.slice(5))
      if (payload.error) throw new LlmError('模型流返回错误', 'MODEL_STREAM_ERROR')
      if (payload.usage)
        usage = {
          inputTokens: payload.usage.prompt_tokens,
          outputTokens: payload.usage.completion_tokens,
        }
      const choice = payload.choices?.[0]
      if (!choice) return
      finish = choice.finish_reason || finish
      text += choice.delta?.content || ''
      for (const delta of choice.delta?.tool_calls || []) {
        const call = calls.get(delta.index) || { id: '', name: '', arguments: '' }
        call.id += delta.id || ''
        call.name += delta.function?.name || ''
        call.arguments += delta.function?.arguments || ''
        calls.set(delta.index, call)
      }
    }
    for await (const bytes of response.body) {
      options.signal?.throwIfAborted()
      buffer += decoder.decode(bytes, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()
      for (const line of lines) consume(line)
    }
    buffer += decoder.decode()
    if (buffer.trim()) consume(buffer)
    let index = 0
    if (text) {
      yield { type: 'block-start', index, blockType: 'text' }
      yield { type: 'text-delta', index, text }
      yield { type: 'block-end', index: index++, block: { type: 'text', text } }
    }
    for (const call of calls.values()) {
      yield { type: 'block-start', index, blockType: 'tool-call' }
      yield {
        type: 'tool-call-delta',
        index,
        id: ToolCallId(call.id),
        name: call.name,
        argumentsDelta: call.arguments,
      }
      yield {
        type: 'block-end',
        index: index++,
        block: {
          type: 'tool-call',
          id: ToolCallId(call.id),
          name: call.name,
          arguments: call.arguments,
        },
      }
    }
    if (usage && Number.isFinite(usage.inputTokens) && Number.isFinite(usage.outputTokens))
      yield { type: 'usage', usage }
    if (!finish) throw new LlmError('模型流未完整结束', 'MODEL_STREAM_INCOMPLETE')
    yield {
      type: 'finish',
      reason: { kind: finish === 'length' ? 'max-tokens' : calls.size ? 'tool-calls' : 'stop' },
    }
  }
}
