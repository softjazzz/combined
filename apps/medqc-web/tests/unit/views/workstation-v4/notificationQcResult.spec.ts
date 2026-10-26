import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  push: vi.fn(),
  route: { query: { notification_id: 'notice' } },
  auth: {
    user: { id: 'manager', institute_id: 'A', department: 'D', is_active: true },
    userRoles: ['qc_manager'],
  },
  debug: vi.fn(),
  export: vi.fn(),
  review: vi.fn(),
  download: vi.fn(),
  normalize: vi.fn(),
  error: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('ant-design-vue', () => ({ message: { error: mocks.error } }))
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: mocks.download,
  normalizeBatchExportBlob: mocks.normalize,
}))
vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push }),
}))
vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getNotificationQcResult: mocks.get,
  getSichuanWorkspaceBatchJobDebugSnapshot: mocks.debug,
  exportSichuanWorkspaceBatchJob: mocks.export,
  reviewSichuanWorkspaceBatchJob: mocks.review,
}))
vi.mock(
  '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue',
  () => ({
    default: {
      props: [
        'batchJobDetail',
        'close',
        'reviewBatchJobResult',
        'exportBatchJobReport',
        'fetchBatchJobDebugSnapshot',
        'reviewBatchJobLoading',
        'batchJobDebugLoading',
        'batchJobDebugSnapshot',
      ],
      template: `<section data-testid="result">{{ batchJobDetail.id }}
          <button data-testid="close" @click="close">返回</button>
          <button data-testid="review" :disabled="reviewBatchJobLoading" @click="reviewBatchJobResult">复核</button>
          <button data-testid="export" @click="exportBatchJobReport()">导出</button>
          <button data-testid="debug" :disabled="batchJobDebugLoading" @click="fetchBatchJobDebugSnapshot(batchJobDetail.id)">调试</button>
          <span data-testid="debug-result">{{ batchJobDebugSnapshot?.job_id }}</span>
        </section>`,
    },
  }),
)
import NotificationQcResult from '@/views/workstation/NotificationQcResult.vue'

function render() {
  return mount(NotificationQcResult, {
    global: {
      stubs: {
        'a-spin': true,
        'a-result': {
          props: ['subTitle'],
          template: '<div data-testid="error">{{ subTitle }}<slot name="extra" /></div>',
        },
        'a-button': { template: '<button><slot /></button>' },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  mocks.route = reactive({ query: { notification_id: 'notice' } })
  mocks.auth = reactive({
    user: { id: 'manager', institute_id: 'A', department: 'D', is_active: true },
    userRoles: ['qc_manager'],
  })
  mocks.normalize.mockResolvedValue(new Blob(['synthetic']))
})

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (cause: Error) => void
  const promise = new Promise<T>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

describe('结果就绪通知的精确V5下钻', () => {
  it('从通知授权接口加载已保存结果，沿用原结果抽屉', async () => {
    mocks.get.mockResolvedValue({ success: true, data: { id: 'saved-root' } })
    const wrapper = render()
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledWith('notice')
    expect(wrapper.get('[data-testid="result"]').text()).toContain('saved-root')
    await wrapper.get('[data-testid="close"]').trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/workstation-v5/messages')
    wrapper.unmount()
  })

  it('失效或越权不回退到最新结果，也不显示旧内容', async () => {
    mocks.get.mockResolvedValue({ success: false, message: '结果通知已失效' })
    const wrapper = render()
    await flushPromises()
    expect(wrapper.find('[data-testid="result"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="error"]').text()).toContain('结果通知已失效')
    wrapper.unmount()
  })

  it('切换通知时丢弃迟到的上一条请求', async () => {
    let finish: (value: unknown) => void = () => undefined
    mocks.get
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finish = resolve
        }),
      )
      .mockResolvedValueOnce({ success: true, data: { id: 'new-root' } })
    const wrapper = render()
    mocks.route.query.notification_id = 'new-notice'
    await flushPromises()
    finish({ success: true, data: { id: 'old-root' } })
    await flushPromises()
    expect(wrapper.get('[data-testid="result"]').text()).toContain('new-root')
    expect(wrapper.text()).not.toContain('old-root')
    wrapper.unmount()
  })

  it.each(['review', 'debug', 'export'] as const)('当前%s操作正常完成', async (operation) => {
    mocks.get.mockResolvedValue({ success: true, data: { id: 'saved-root' } })
    mocks.review.mockResolvedValue({ success: true, data: { job: { id: 'reviewed-root' } } })
    mocks.debug.mockResolvedValue({ success: true, data: { job_id: 'saved-root' } })
    mocks.export.mockResolvedValue({ success: true, data: new Blob(['synthetic']) })
    const wrapper = render()
    await flushPromises()
    await wrapper.get(`[data-testid="${operation}"]`).trigger('click')
    await flushPromises()
    if (operation === 'review') expect(wrapper.text()).toContain('reviewed-root')
    if (operation === 'debug')
      expect(wrapper.get('[data-testid="debug-result"]').text()).toBe('saved-root')
    if (operation === 'export')
      expect(mocks.download).toHaveBeenCalledWith(expect.any(Blob), 'qc-saved-root.html')
    expect(mocks.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it.each(['review', 'debug', 'export'] as const)(
    '切换通知后丢弃旧%s成功和失败应答',
    async (operation) => {
      for (const failed of [false, true]) {
        mocks.route.query.notification_id = 'notice'
        const pending = deferred<unknown>()
        mocks.get.mockImplementation(async (id: string) => ({ success: true, data: { id } }))
        mocks[operation].mockReturnValueOnce(pending.promise)
        const wrapper = render()
        await flushPromises()
        await wrapper.get(`[data-testid="${operation}"]`).trigger('click')
        await flushPromises()
        mocks.route.query.notification_id = 'next-notice'
        await flushPromises()
        if (failed) pending.reject(new Error('旧请求失败'))
        else
          pending.resolve({ success: true, data: { job: { id: 'old-root' }, job_id: 'old-root' } })
        await flushPromises()
        expect(wrapper.get('[data-testid="result"]').text()).toContain('next-notice')
        expect(wrapper.text()).not.toContain('old-root')
        expect(mocks.download).not.toHaveBeenCalled()
        expect(mocks.error).not.toHaveBeenCalled()
        wrapper.unmount()
      }
    },
  )

  it.each(['id', 'institute_id', 'department', 'roles', 'is_active', 'unmount'] as const)(
    '%s变化后旧导出不下载、不弹错',
    async (change) => {
      const pending = deferred<unknown>()
      mocks.get.mockResolvedValue({ success: true, data: { id: 'saved-root' } })
      mocks.export.mockReturnValueOnce(pending.promise)
      const wrapper = render()
      await flushPromises()
      await wrapper.get('[data-testid="export"]').trigger('click')
      await flushPromises()
      if (change === 'unmount') wrapper.unmount()
      else if (change === 'roles') mocks.auth.userRoles = ['doctor']
      else if (change === 'is_active') mocks.auth.user.is_active = false
      else mocks.auth.user[change] = 'changed'
      await flushPromises()
      pending.resolve({ success: true, data: new Blob(['old']) })
      await flushPromises()
      expect(mocks.download).not.toHaveBeenCalled()
      expect(mocks.error).not.toHaveBeenCalled()
      if (change !== 'unmount') wrapper.unmount()
    },
  )

  it('Blob转换期间切换通知也不下载旧文件', async () => {
    const pending = deferred<Blob>()
    mocks.get.mockResolvedValue({ success: true, data: { id: 'saved-root' } })
    mocks.export.mockResolvedValue({ success: true, data: new Blob(['synthetic']) })
    mocks.normalize.mockReturnValueOnce(pending.promise)
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="export"]').trigger('click')
    await flushPromises()
    mocks.route.query.notification_id = 'next'
    await flushPromises()
    pending.resolve(new Blob(['old']))
    await flushPromises()
    expect(mocks.download).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it.each(['review', 'debug'] as const)('旧%s的finally不清除新请求loading', async (operation) => {
    const old = deferred<unknown>()
    const current = deferred<unknown>()
    mocks.get.mockImplementation(async (id: string) => ({ success: true, data: { id } }))
    mocks[operation].mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    const wrapper = render()
    await flushPromises()
    await wrapper.get(`[data-testid="${operation}"]`).trigger('click')
    await flushPromises()
    mocks.route.query.notification_id = 'next'
    await flushPromises()
    await wrapper.get(`[data-testid="${operation}"]`).trigger('click')
    await flushPromises()
    old.reject(new Error('old'))
    await flushPromises()
    expect(wrapper.get(`[data-testid="${operation}"]`).attributes('disabled')).toBeDefined()
    current.resolve({ success: false, message: '当前失败' })
    await flushPromises()
    expect(wrapper.get(`[data-testid="${operation}"]`).attributes('disabled')).toBeUndefined()
    expect(mocks.error).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('正文请求reject时清理loading并显示错误，允许重试', async () => {
    mocks.get
      .mockRejectedValueOnce(new Error('连接失败'))
      .mockResolvedValueOnce({ success: true, data: { id: 'recovered' } })
    const wrapper = render()
    await flushPromises()
    expect(wrapper.get('[data-testid="error"]').text()).toContain('连接失败')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="result"]').text()).toContain('recovered')
    wrapper.unmount()
  })
})
