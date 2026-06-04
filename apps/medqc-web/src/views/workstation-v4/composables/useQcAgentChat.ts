import { computed, ref } from 'vue'

import {
  qcAgentApi,
  type QCAgentCandidate,
  type QCAgentChatRequest,
  type QCAgentChatResponse,
  type QCAgentConfirmSelection,
  type QCAgentUserContext,
} from '@/api/qcAgent'

const SENSITIVE_KEYS = new Set([
  'medical_text',
  'record_content',
  'documents',
  'bundle',
  'structured_context',
  'internal_data',
  'prompt',
  'examples',
  'raw_llm_output',
])

export type QCAgentMessageRole = 'user' | 'assistant' | 'system'

export interface QCAgentMessage {
  id: string
  role: QCAgentMessageRole
  content: string
  response?: QCAgentChatResponse
}

export interface QCAgentChatOptions {
  userContext?: QCAgentUserContext
}

function createMessageId() {
  return `qc-agent-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function sanitizeQcAgentPayload<T = unknown>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeQcAgentPayload(item)) as T
  }
  if (value && typeof value === 'object') {
    const output: Record<string, unknown> = {}
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (SENSITIVE_KEYS.has(key)) continue
      output[key] = sanitizeQcAgentPayload(item)
    }
    return output as T
  }
  return value
}

function responseTitle(response: QCAgentChatResponse) {
  if (response.status === 'completed') return '已完成只读文书质控'
  if (response.status === 'needs_confirmation') return '命中多份病历，请确认单份病历'
  if (response.status === 'needs_clarification') return '需要补充信息后继续'
  if (response.status === 'unsupported') return '该操作不在受控助手范围内'
  return `质控助手返回：${response.status}`
}

export function useQcAgentChat() {
  const messages = ref<QCAgentMessage[]>([])
  const loading = ref(false)
  const lastResponse = ref<QCAgentChatResponse | null>(null)
  const error = ref('')
  const lastMessage = ref('')

  const hasMessages = computed(() => messages.value.length > 0)

  async function chat(message: string, options: QCAgentChatOptions = {}) {
    const content = message.trim()
    if (!content || loading.value) return null

    loading.value = true
    error.value = ''
    lastMessage.value = content
    messages.value.push({
      id: createMessageId(),
      role: 'user',
      content,
    })

    try {
      const request: QCAgentChatRequest = {
        message: content,
      }
      if (options.userContext) request.user_context = sanitizeQcAgentPayload(options.userContext)
      const response = sanitizeQcAgentPayload(await qcAgentApi.chat(request))
      lastResponse.value = response
      messages.value.push({
        id: createMessageId(),
        role: 'assistant',
        content: responseTitle(response),
        response,
      })
      return response
    } catch (err) {
      const reason = err instanceof Error ? err.message : '质控助手调用失败'
      error.value = reason
      messages.value.push({
        id: createMessageId(),
        role: 'system',
        content: reason,
      })
      return null
    } finally {
      loading.value = false
    }
  }

  async function confirmCandidate(candidate: QCAgentCandidate, options: QCAgentChatOptions = {}) {
    const visitId = String(candidate.visit_id || '').trim()
    if (!visitId || !lastMessage.value || loading.value) return null

    loading.value = true
    error.value = ''
    const confirmSelection: QCAgentConfirmSelection = {
      visit_id: visitId,
      patient_id: candidate.patient_id,
    }
    messages.value.push({
      id: createMessageId(),
      role: 'user',
      content: `选择病历 ${visitId} 并继续`,
    })

    try {
      const request: QCAgentChatRequest = {
        message: lastMessage.value,
        confirm_selection: confirmSelection,
      }
      if (options.userContext) request.user_context = sanitizeQcAgentPayload(options.userContext)
      const response = sanitizeQcAgentPayload(await qcAgentApi.chat(request))
      lastResponse.value = response
      messages.value.push({
        id: createMessageId(),
        role: 'assistant',
        content: responseTitle(response),
        response,
      })
      return response
    } catch (err) {
      const reason = err instanceof Error ? err.message : '候选病历确认失败'
      error.value = reason
      messages.value.push({
        id: createMessageId(),
        role: 'system',
        content: reason,
      })
      return null
    } finally {
      loading.value = false
    }
  }

  function clear() {
    messages.value = []
    lastResponse.value = null
    error.value = ''
    lastMessage.value = ''
  }

  return {
    messages,
    loading,
    lastResponse,
    error,
    hasMessages,
    chat,
    confirmCandidate,
    clear,
  }
}
