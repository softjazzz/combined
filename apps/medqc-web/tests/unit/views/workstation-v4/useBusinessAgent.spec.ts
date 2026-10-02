import { effectScope } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  BusinessAgentContext,
  BusinessAgentSession,
  BusinessAgentTurn,
} from '@/api/businessAgent'

const api = vi.hoisted(() => ({ create: vi.fn(), restore: vi.fn(), chat: vi.fn(), stop: vi.fn() }))
vi.mock('@/api/businessAgent', () => ({ businessAgentApi: api }))
import { useBusinessAgent } from '@/views/workstation-v4/composables/useBusinessAgent'

const A: BusinessAgentContext = {
  view: 'doctor',
  institute_id: 'S',
  patient_id: 'A',
  visit_id: 'A1',
}
const B: BusinessAgentContext = { ...A, patient_id: 'B', visit_id: 'B1' }
const turn: BusinessAgentTurn = {
  run_id: 'run-a',
  question: 'A的问题',
  answer: 'A的回答',
  status: 'completed',
  references: [],
  tool_calls: 1,
  elapsed_ms: 1,
}
function setup() {
  const scope = effectScope()
  const agent = scope.run(useBusinessAgent)!
  return { agent, close: () => scope.stop() }
}
describe('业务助手病例与账号隔离', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    localStorage.clear()
    sessionStorage.clear()
    localStorage.setItem('auth_user', '{"id":"account-a"}')
    api.create.mockImplementation(
      async (context: BusinessAgentContext): Promise<BusinessAgentSession> => ({
        session_id: context.patient_id || 'manager',
        context,
        turns: [],
      }),
    )
    api.stop.mockResolvedValue(undefined)
  })
  it('A→B 后迟到响应被丢弃，回到 A 可恢复，字段顺序不影响恢复', async () => {
    let finish!: (value: BusinessAgentTurn) => void
    api.chat.mockImplementationOnce(
      () =>
        new Promise<BusinessAgentTurn>((resolve) => {
          finish = resolve
        }),
    )
    const { agent, close } = setup()
    try {
      await agent.activate(A)
      const running = agent.send('A的问题', A)
      await vi.waitFor(() => expect(api.chat).toHaveBeenCalledOnce())
      await agent.activate(B)
      finish(turn)
      await running
      expect(agent.turns.value).toEqual([])
      expect(api.stop).toHaveBeenCalledWith('A', expect.any(String))
      api.restore.mockResolvedValue({
        session_id: 'A',
        context: { visit_id: 'A1', patient_id: 'A', institute_id: 'S', view: 'doctor' },
        turns: [turn],
      })
      await agent.activate(A)
      expect(agent.turns.value).toEqual([turn])
    } finally {
      close()
    }
  })
  it('停止和清空隔离旧请求，账号切换不恢复前一个账号会话', async () => {
    api.chat.mockResolvedValue(turn)
    const { agent, close } = setup()
    try {
      await agent.activate(A)
      await agent.send('A的问题', A)
      localStorage.setItem('auth_user', '{"id":"account-b"}')
      await agent.activate(A)
      expect(api.restore).not.toHaveBeenCalled()
      expect(agent.turns.value).toEqual([])
      await agent.reset(A)
      expect(agent.sessionId.value).toBe('')
    } finally {
      close()
    }
  })
  it('同一UID更新资料后仍恢复既有会话，并兼容旧定位键', async () => {
    const oldAccount = JSON.stringify({ id: 'account-a', display_name: '旧名' })
    const key = `medqc-business-agent:${JSON.stringify([oldAccount, JSON.stringify(Object.entries(A).sort(([a], [b]) => a.localeCompare(b)))])}`
    sessionStorage.setItem(key, 'legacy-a')
    localStorage.setItem('auth_user', JSON.stringify({ display_name: '新名', id: 'account-a' }))
    api.restore.mockResolvedValue({ session_id: 'legacy-a', context: A, turns: [turn] })
    const { agent, close } = setup()
    try {
      await agent.activate(A)
      expect(api.restore).toHaveBeenCalledWith('legacy-a')
      expect(agent.turns.value).toEqual([turn])
      localStorage.setItem('auth_user', JSON.stringify({ id: 'account-a', last_login: 'new-time' }))
      await agent.activate(A)
      expect(agent.sessionId.value).toBe('legacy-a')
      await agent.reset(A)
      expect(agent.sessionId.value).toBe('')
      expect(agent.turns.value).toEqual([])
    } finally {
      close()
    }
  })
  it('旧定位键属于其他UID、患者或含多个候选时不猜测恢复', async () => {
    const context = JSON.stringify(Object.entries(A).sort(([a], [b]) => a.localeCompare(b)))
    const put = (account: object, id: string) =>
      sessionStorage.setItem(
        `medqc-business-agent:${JSON.stringify([JSON.stringify(account), context])}`,
        id,
      )
    put({ id: 'account-b' }, 'other')
    const { agent, close } = setup()
    try {
      await agent.activate(A)
      expect(api.restore).not.toHaveBeenCalled()
      put({ id: 'account-a', display_name: 'old-1' }, 'one')
      put({ id: 'account-a', display_name: 'old-2' }, 'two')
      await agent.activate(A)
      expect(api.restore).not.toHaveBeenCalled()
      expect(agent.turns.value).toEqual([])
    } finally {
      close()
    }
  })
  it('恢复完成前不发送新问题，避免迟到历史覆盖新回答', async () => {
    api.chat.mockResolvedValue(turn)
    const { agent, close } = setup()
    try {
      await agent.activate(A)
      await agent.send('A的问题', A)
      let restore!: (value: BusinessAgentSession) => void
      api.restore.mockImplementationOnce(
        () =>
          new Promise<BusinessAgentSession>((resolve) => {
            restore = resolve
          }),
      )
      const restoring = agent.activate(A)
      expect(agent.loading.value).toBe(true)
      await agent.send('新问题', A)
      expect(api.chat).toHaveBeenCalledTimes(1)
      restore({ session_id: 'A', context: A, turns: [turn] })
      await restoring
      expect(agent.loading.value).toBe(false)
      await agent.send('新问题', A)
      expect(agent.turns.value).toHaveLength(2)
    } finally {
      close()
    }
  })
  it('恢复失败后不覆盖旧会话定位，重试成功才继续同一会话', async () => {
    api.chat.mockResolvedValue(turn)
    const { agent, close } = setup()
    try {
      await agent.activate(A)
      await agent.send('A的问题', A)
      const savedLocators = Object.entries(sessionStorage)
      api.create.mockResolvedValue({ session_id: 'replacement', context: A, turns: [] })
      api.restore.mockRejectedValueOnce(new Error('暂时无法连接'))
      await agent.activate(A)
      expect(agent.error.value).toContain('会话恢复失败')
      api.restore.mockRejectedValueOnce(new Error('仍无法连接'))
      await agent.send('继续追问', A)
      expect(api.create).toHaveBeenCalledTimes(1)
      expect(api.chat).toHaveBeenCalledTimes(1)
      expect(Object.entries(sessionStorage)).toEqual(savedLocators)
      expect(agent.error.value).toContain('会话恢复失败')
      api.restore.mockResolvedValue({ session_id: 'A', context: A, turns: [turn] })
      await agent.send('继续追问', A)
      expect(api.chat).toHaveBeenLastCalledWith(
        'A',
        expect.any(String),
        '继续追问',
        expect.any(AbortSignal),
        undefined,
      )
      expect(agent.turns.value).toHaveLength(2)
    } finally {
      close()
    }
  })
  it('发送前恢复期间切到B，A恢复完成后不得继续创建或发送问题', async () => {
    api.chat.mockResolvedValue(turn)
    const { agent, close } = setup()
    try {
      await agent.activate(A)
      await agent.send('A的问题', A)
      api.restore.mockRejectedValueOnce(new Error('暂时无法连接'))
      await agent.activate(A)
      let restore!: (value: BusinessAgentSession) => void
      api.restore.mockImplementationOnce(
        () =>
          new Promise<BusinessAgentSession>((resolve) => {
            restore = resolve
          }),
      )
      const retrying = agent.send('A的追问', A)
      await agent.activate(B)
      restore({ session_id: 'A', context: A, turns: [turn] })
      await retrying
      expect(api.create).toHaveBeenCalledTimes(1)
      expect(api.chat).toHaveBeenCalledTimes(1)
      expect(agent.sessionId.value).toBe('')
      expect(agent.turns.value).toEqual([])
      expect(agent.loading.value).toBe(false)
    } finally {
      close()
    }
  })
  it('新建等待停止期间切到B，迟到的A新建操作不清除B定位或切回A', async () => {
    const bTurn = { ...turn, run_id: 'run-b', question: 'B的问题', answer: 'B的回答' }
    api.chat.mockResolvedValueOnce(bTurn)
    api.restore.mockImplementation(async (id: string) => ({
      session_id: id,
      context: id === 'B' ? B : A,
      turns: id === 'B' ? [bTurn] : [],
    }))
    const { agent, close } = setup()
    let finish!: (value: BusinessAgentTurn) => void
    let stopped!: () => void
    try {
      await agent.activate(B)
      await agent.send('B的问题', B)
      await agent.activate(A)
      api.chat.mockImplementationOnce(
        () =>
          new Promise<BusinessAgentTurn>((resolve) => {
            finish = resolve
          }),
      )
      const running = agent.send('A的问题', A)
      await vi.waitFor(() => expect(api.chat).toHaveBeenCalledTimes(2))
      api.stop.mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            stopped = resolve
          }),
      )
      const resetting = agent.reset(A)
      await agent.activate(B)
      const beforeStopConfirmed = Object.entries(sessionStorage)
      stopped()
      await resetting
      finish(turn)
      await running
      expect(agent.sessionId.value).toBe('B')
      expect(agent.turns.value).toEqual([bTurn])
      expect(Object.entries(sessionStorage)).toEqual(beforeStopConfirmed)
    } finally {
      close()
    }
  })
  it.each(['v2', 'legacy'])(
    '恢复失败后只有明确新建才替换 %s 定位，不借用旧会话',
    async (version) => {
      api.chat.mockResolvedValue(turn)
      const { agent, close } = setup()
      try {
        await agent.activate(A)
        await agent.send('A的问题', A)
        if (version === 'legacy') {
          sessionStorage.clear()
          const account = JSON.stringify({ id: 'account-a', display_name: '旧名' })
          const context = JSON.stringify(Object.entries(A).sort(([a], [b]) => a.localeCompare(b)))
          sessionStorage.setItem(`medqc-business-agent:${JSON.stringify([account, context])}`, 'A')
        }
        api.restore.mockRejectedValue(new Error('暂时无法连接'))
        await agent.activate(A)
        await agent.reset(A)
        api.create.mockResolvedValue({ session_id: 'new-a', context: A, turns: [] })
        await agent.send('新会话的问题', A)
        expect(api.create).toHaveBeenCalledTimes(2)
        expect(api.chat).toHaveBeenLastCalledWith(
          'new-a',
          expect.any(String),
          '新会话的问题',
          expect.any(AbortSignal),
          undefined,
        )
        expect(agent.turns.value).toEqual([turn])
        expect(Object.values(sessionStorage)).toEqual(['new-a'])
      } finally {
        close()
      }
    },
  )
})
