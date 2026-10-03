import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import QcBatchCaseActions from '../QcBatchCaseActions.vue'
import { ApiService } from '@/services/apiService'

vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: vi.fn() } }))
vi.mock('ant-design-vue', () => ({ Modal: { template: '<div><slot /></div>' } }))

const identity = { institute_id: 'A', patient_id: 'P', visit_id: 'V' }
type Request = { url: string; data: Record<string, string> }
const transport = vi.mocked(ApiService.requestRaw)

function prepared(data: Record<string, string>) {
  return { review: { can_submit: true, result: { job_id: `J-${data.visit_id}`, envelope_id: `E-${data.visit_id}` } },
    source: { ...data, root_job_id: `J-${data.visit_id}`, envelope_id: `E-${data.visit_id}` },
    doctors: [{ id: 'D', name: '合成医生' }] }
}

function success(data: unknown) {
  return { data: { success: true, data } }
}

function httpError(status: number) {
  return { isAxiosError: true, response: { status, data: { detail: `合成HTTP ${status}` } } }
}

function mountControl() {
  return mount(QcBatchCaseActions, { props: { recordRefs: [identity, { ...identity, visit_id: 'V2' }],
    actorKey: 'manager', carePhase: 'inpatient', allowed: true } })
}

async function prepare(wrapper: ReturnType<typeof mountControl>, action = 0) {
  await wrapper.findAll('button')[action]!.trigger('click')
  await flushPromises()
}

async function submit(wrapper: ReturnType<typeof mountControl>) {
  await wrapper.findAll('button')[2]!.trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  transport.mockImplementation(async (request) => {
    const { url, data } = request as Request
    return success(url.endsWith('/prepare') ? prepared(data) : { ...data, id: `receipt-${data.visit_id}`,
      decision: 'approved', state: 'approved' }) as Awaited<ReturnType<typeof ApiService.requestRaw>>
  })
})

describe('批量生产组件与真实API客户端', () => {
  it('部分403失败与成功分别展示，批次仅提交一次并触发列表刷新事件', async () => {
    transport.mockImplementation(async (request) => {
      const { url, data } = request as Request
      if (url.endsWith('/prepare')) return success(prepared(data)) as Awaited<ReturnType<typeof ApiService.requestRaw>>
      if (data.visit_id === 'V') throw httpError(403)
      return success({ ...data, id: 'receipt', decision: 'approved', state: 'approved' }) as Awaited<ReturnType<typeof ApiService.requestRaw>>
    })
    const wrapper = mountControl()
    await prepare(wrapper)
    expect(transport).toHaveBeenCalledTimes(2)
    await submit(wrapper)
    expect(wrapper.text()).toContain('未完成')
    expect(wrapper.text()).toContain('审核通过已保存')
    expect(wrapper.text()).not.toContain('结果未知，请核对')
    expect(wrapper.emitted('completed')).toHaveLength(1)
    await submit(wrapper)
    expect(transport).toHaveBeenCalledTimes(4)
    wrapper.unmount()
  })

  it('催办409为明确失败，网络中断为未知，两例仍保留各自回执', async () => {
    transport.mockImplementation(async (request) => {
      const { url, data } = request as Request
      if (url.endsWith('/prepare')) return success(prepared(data)) as Awaited<ReturnType<typeof ApiService.requestRaw>>
      if (data.visit_id === 'V') throw httpError(409)
      throw new Error('合成断网')
    })
    const wrapper = mountControl()
    await prepare(wrapper, 1)
    for (const select of wrapper.findAll('select')) await select.setValue('D')
    await submit(wrapper)
    const statuses = wrapper.findAll('[role="status"]').map(item => item.text())
    expect(statuses[0]).toContain('未完成')
    expect(statuses[1]).toContain('结果未知，请核对')
    expect(wrapper.text()).not.toContain('病历催办已发送')
    expect(wrapper.emitted('completed')).toHaveLength(1)
    expect(transport.mock.calls.slice(2).every(([request]) => request.url === '/api/v1/case-communications')).toBe(true)
    wrapper.unmount()
  })

  it.each([{ actorKey: 'other' }, { carePhase: 'discharged' as const }, { allowed: false }])(
    '上下文切换取消迟到响应和后续病例派发 %j', async props => {
      let finish: ((value: unknown) => void) | undefined
      transport.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }) as ReturnType<typeof ApiService.requestRaw>)
      const wrapper = mountControl()
      await wrapper.findAll('button')[0]!.trigger('click')
      await wrapper.setProps(props)
      finish?.(success(prepared({ ...identity, scene: 'running' })))
      await flushPromises()
      expect(transport).toHaveBeenCalledTimes(1)
      expect(wrapper.findAll('[role="status"]')).toHaveLength(0)
      expect(wrapper.emitted('completed')).toBeUndefined()
      wrapper.unmount()
    },
  )
})
