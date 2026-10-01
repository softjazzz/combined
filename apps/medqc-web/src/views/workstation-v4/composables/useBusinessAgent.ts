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
  function accountIdentity(serialized: string): string | undefined {
    try {
      const account: unknown = JSON.parse(serialized)
      if (
        account &&
        typeof account === 'object' &&
        'id' in account &&
        typeof account.id === 'string' &&
        account.id &&
        account.id !== 'unknown'
      )
        return account.id
    } catch {
      /* 无有效身份时不跨资料版本寻找会话。 */
    }
    return undefined
  }
  function currentAccount() {
    return localStorage.getItem('auth_user') || localStorage.getItem('medqc_user') || ''
  }
  function storageScope(context: BusinessAgentContext) {
    const account = currentAccount()
    return `medqc-business-agent:v2:${JSON.stringify([accountIdentity(account) || account, contextKey(context)])}`
  }
  function legacySession(context: BusinessAgentContext) {
    const uid = accountIdentity(currentAccount())
    const candidates: { key: string; id: string }[] = []
    if (!uid) return candidates
    for (let index = 0; index < sessionStorage.length; index++) {
      const key = sessionStorage.key(index)
      if (!key?.startsWith('medqc-business-agent:')) continue
      try {
        const entry: unknown = JSON.parse(key.slice('medqc-business-agent:'.length))
        if (
          !Array.isArray(entry) ||
          entry.length !== 2 ||
          typeof entry[0] !== 'string' ||
          accountIdentity(entry[0]) !== uid ||
          entry[1] !== contextKey(context)
        )
          continue
        const id = sessionStorage.getItem(key)
        if (id) candidates.push({ key, id })
      } catch {
        /* 其他版本或损坏定位键不参与恢复。 */
      }
    }
    // 多个独立会话不能靠字段顺序选择；由用户明确新建。
    return new Set(candidates.map(({ id }) => id)).size === 1 ? candidates : []
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
    const legacy = sessionStorage.getItem(storageKey) ? [] : legacySession(context)
    const stored = sessionStorage.getItem(storageKey) || legacy[0]?.id
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
      // 服务端再次校验归属及权限、上下文一致后才迁移定位；不复制执行历史。
      if (legacy.length) {
        sessionStorage.setItem(storageKey, session.session_id)
        for (const { key } of legacy) sessionStorage.removeItem(key)
      }
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
