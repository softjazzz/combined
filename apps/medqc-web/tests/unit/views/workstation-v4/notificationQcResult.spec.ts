import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  task: vi.fn(),
  push: vi.fn(),
  route: { query: { notification_id: 'notice' } as Record<string, string> },
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
  success: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('ant-design-vue', () => ({ message: { error: mocks.error, success: mocks.success } }))
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
  getSichuanWorkspaceBatchJob: mocks.task,
  getSichuanWorkspaceBatchJobDebugSnapshot: mocks.debug,
  exportSichuanWorkspaceBatchJob: mocks.export,
  reviewSichuanWorkspaceBatchJob: mocks.review,
}))
vi.mock(
  '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue',
  () => ({
    default: {
      name: 'ResultDrawerStub',
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

function render(entryMode: 'notification' | 'task' = 'notification') {
  return mount(NotificationQcResult, {
    props: { entryMode },
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
    if (operation === 'review') {
      expect(wrapper.text()).toContain('reviewed-root')
      expect(mocks.success).toHaveBeenCalledTimes(1)
    }
    if (operation === 'debug')
      expect(wrapper.get('[data-testid="debug-result"]').text()).toBe('saved-root')
    if (operation === 'export')
      expect(mocks.download).toHaveBeenCalledWith(expect.any(Blob), 'qc-saved-root.html')
    // 复用已加载 job_id，不重复触发通知接口读取
    expect(mocks.get).toHaveBeenCalledTimes(1)
    expect(mocks.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('非受限账号打开时自动预加载调试快照；受限演示账号不自动拉取调试快照', async () => {
    mocks.auth.user = {
      id: 'super-1',
      institute_id: 'A',
      department: 'D',
      is_active: true,
      is_demo_account: false,
      roles: ['super_admin'],
    } as typeof mocks.auth.user
    mocks.auth.userRoles = ['super_admin']
    mocks.get.mockResolvedValue({ success: true, data: { id: 'saved-root' } })
    mocks.debug.mockResolvedValue({ success: true, data: { job_id: 'saved-root' } })
    const wrapper = render()
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(1)
    expect(mocks.debug).toHaveBeenCalledWith('saved-root', {
      rule_job_id: undefined,
      item_limit: undefined,
    })
    expect(wrapper.get('[data-testid="debug-result"]').text()).toBe('saved-root')
    wrapper.unmount()

    vi.clearAllMocks()
    mocks.auth.user = {
      id: 'demo-1',
      institute_id: 'A',
      department: 'D',
      is_active: true,
      is_demo_account: true,
      roles: ['admin'],
    } as typeof mocks.auth.user
    mocks.auth.userRoles = ['admin']
    mocks.get.mockResolvedValue({ success: true, data: { id: 'saved-root' } })
    const demoWrapper = render()
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(1)
    expect(mocks.debug).not.toHaveBeenCalled()
    demoWrapper.unmount()
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

describe('按任务ID读取失败及部分结果', () => {
  it('使用任务接口且不请求通知', async () => {
    mocks.route.query = { job_id: 'failed-job' }
    const partial = { id: 'failed-job', status: 'failed', items: [{ rule_id: 'R1', status: 'data_gap' }], failed_records: [{ reason_code: 'model_transport_error' }] }
    mocks.task.mockResolvedValue({ success: true, data: partial })
    const wrapper = render('task')
    await flushPromises()
    expect(mocks.task).toHaveBeenCalledWith('failed-job')
    expect(wrapper.findComponent({ name: 'ResultDrawerStub' }).props('batchJobDetail')).toEqual(partial)
    expect(mocks.get).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="result"]').text()).toContain('failed-job')
    await wrapper.get('[data-testid="close"]').trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/workstation-v5/records/running')
    wrapper.unmount()
  })
  it('任务拒绝访问时不回退通知或其他任务', async () => {
    mocks.route.query = { job_id: 'forbidden' }
    mocks.task.mockResolvedValue({ success: false, message: '批量任务不存在或无权限' })
    const wrapper = render('task')
    await flushPromises()
    expect(wrapper.get('[data-testid="error"]').text()).toContain('无权限')
    expect(wrapper.find('[data-testid="result"]').exists()).toBe(false)
    expect(mocks.get).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('切换任务时拒绝迟到响应', async () => {
    mocks.route.query = { job_id: 'old' }
    const old = deferred<unknown>()
    mocks.task
      .mockReturnValueOnce(old.promise)
      .mockResolvedValue({ success: true, data: { id: 'new' } })
    const wrapper = render('task')
    mocks.route.query.job_id = 'new'
    await flushPromises()
    old.resolve({ success: true, data: { id: 'old' } })
    await flushPromises()
    expect(wrapper.get('[data-testid="result"]').text()).toContain('new')
    expect(wrapper.text()).not.toContain('old')
    wrapper.unmount()
  })
  it('拒绝返回其他任务的数据', async () => {
    mocks.route.query = { job_id: 'requested' }
    mocks.task.mockResolvedValue({ success: true, data: { id: 'another' } })
    const wrapper = render('task')
    await flushPromises()
    expect(wrapper.find('[data-testid="result"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="error"]').text()).toContain('不一致')
    wrapper.unmount()
  })
  it('切换账号立即清空旧任务，重新授权失败不保留结果', async () => {
    mocks.route.query = { job_id: 'failed-job' }
    mocks.task
      .mockResolvedValueOnce({ success: true, data: { id: 'failed-job' } })
      .mockResolvedValueOnce({ success: false, message: '无权限' })
    const wrapper = render('task')
    await flushPromises()
    mocks.auth.user.id = 'another-user'
    await flushPromises()
    expect(wrapper.find('[data-testid="result"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('无权限')
    expect(mocks.get).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('未登录不请求任务接口', async () => {
    mocks.route.query = { job_id: 'failed-job' }
    mocks.auth.user.id = ''
    const wrapper = render('task')
    await flushPromises()
    expect(mocks.task).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('重新登录')
    wrapper.unmount()
  })
  it('任务模式不接受通知ID代替任务ID', async () => {
    const wrapper = render('task')
    await flushPromises()
    expect(mocks.task).not.toHaveBeenCalled()
    expect(mocks.get).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="error"]').text()).toContain('任务')
    wrapper.unmount()
  })
})
