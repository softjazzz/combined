import { onScopeDispose, ref } from 'vue'
import {
  businessAgentApi,
  type BusinessAgentContext,
  type BusinessAgentTurn,
} from '@/api/businessAgent'

// 标签页只保留会话定位；执行历史由 DSH 提供。
export function useBusinessAgent() {
  const sessionId = ref('')
  const turns = ref<BusinessAgentTurn[]>([])
  const loading = ref(false)
  const error = ref('')
  let generation = 0
  let storageKey = ''
  let active: { sessionId: string; runId: string; controller: AbortController } | undefined
  function contextKey(context: BusinessAgentContext) {
    return JSON.stringify(
      Object.entries(context)
        .filter(([, value]) => value !== undefined && value !== null)
        .sort(([a], [b]) => a.localeCompare(b)),
    )
  }
  function storageScope(context: BusinessAgentContext) {
    const account = localStorage.getItem('auth_user') || localStorage.getItem('medqc_user') || ''
    return `medqc-business-agent:${JSON.stringify([account, contextKey(context)])}`
  }
  async function stop() {
    const current = active
    const epoch = ++generation
    active = undefined
    loading.value = false
    if (!current) return
    current.controller.abort()
    try {
      await businessAgentApi.stop(current.sessionId, current.runId)
    } catch {
      if (epoch === generation) error.value = '停止请求未确认，请刷新查看实际执行状态。'
    }
  }
  async function activate(context: BusinessAgentContext) {
    const current = active
    const epoch = ++generation
    active = undefined
    current?.controller.abort()
    if (current) void businessAgentApi.stop(current.sessionId, current.runId).catch(() => undefined)
    loading.value = false
    sessionId.value = ''
    turns.value = []
    error.value = ''
    storageKey = storageScope(context)
    const stored = sessionStorage.getItem(storageKey)
    if (!stored) return
    loading.value = true
    try {
      const session = await businessAgentApi.restore(stored)
      if (epoch !== generation) return
      if (contextKey(session.context) !== contextKey(context)) {
        sessionStorage.removeItem(storageKey)
        return
      }
      sessionId.value = session.session_id
      turns.value = session.turns
    } catch {
      if (epoch === generation) error.value = '会话恢复失败，可刷新重试或新建会话。'
    } finally {
      if (epoch === generation) loading.value = false
    }
  }
  async function send(message: string, context: BusinessAgentContext, referenceId?: string) {
    if (!message.trim() || loading.value) return
    if (storageKey !== storageScope(context)) await activate(context)
    const epoch = generation
    loading.value = true
    error.value = ''
    try {
      if (!sessionId.value) {
        const session = await businessAgentApi.create(context)
        if (epoch !== generation) return
        sessionId.value = session.session_id
        sessionStorage.setItem(storageKey || storageScope(context), session.session_id)
      }
      const current = {
        sessionId: sessionId.value,
        runId: crypto.randomUUID(),
        controller: new AbortController(),
      }
      active = current
      const turn = await businessAgentApi.chat(
        current.sessionId,
        current.runId,
        message.trim(),
        current.controller.signal,
        referenceId,
      )
      if (epoch === generation) turns.value.push(turn)
    } catch (cause) {
      if (epoch === generation)
        error.value = cause instanceof Error ? cause.message : '助手查询失败'
    } finally {
      if (epoch === generation) {
        active = undefined
        loading.value = false
      }
    }
  }
  async function reset(context: BusinessAgentContext) {
    await stop()
    sessionStorage.removeItem(storageKey)
    await activate(context)
  }
  onScopeDispose(() => {
    void stop()
  })
  return { sessionId, turns, loading, error, activate, send, stop, reset }
}
