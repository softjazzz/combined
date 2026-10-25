import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  push: vi.fn(),
  route: { query: { notification_id: 'notice' } },
}))
vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push }),
}))
vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getNotificationQcResult: mocks.get,
  getSichuanWorkspaceBatchJobDebugSnapshot: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  reviewSichuanWorkspaceBatchJob: vi.fn(),
}))
vi.mock(
  '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue',
  () => ({
    default: {
      props: ['batchJobDetail', 'close'],
      template:
        '<section data-testid="result">{{ batchJobDetail.id }}<button @click="close">返回</button></section>',
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
  vi.clearAllMocks()
  mocks.route = reactive({ query: { notification_id: 'notice' } })
})

describe('结果就绪通知的精确V5下钻', () => {
  it('从通知授权接口加载已保存结果，沿用原结果抽屉', async () => {
    mocks.get.mockResolvedValue({ success: true, data: { id: 'saved-root' } })
    const wrapper = render()
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledWith('notice')
    expect(wrapper.get('[data-testid="result"]').text()).toContain('saved-root')
    await wrapper.get('button').trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/workstation-v5/worklist?assist=message')
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
})
