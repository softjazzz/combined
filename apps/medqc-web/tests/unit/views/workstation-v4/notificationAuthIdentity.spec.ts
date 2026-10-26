import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  login: vi.fn(),
  me: vi.fn(),
  profile: vi.fn(),
  get: vi.fn(),
  export: vi.fn(),
  download: vi.fn(),
  error: vi.fn(),
}))
vi.mock('@/services/apiService', () => ({
  ApiService: { login: mocks.login, getCurrentUser: mocks.me, updateProfile: mocks.profile },
}))
vi.mock('ant-design-vue', () => ({ message: { error: mocks.error, success: vi.fn() } }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { notification_id: 'notice-A' } }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getNotificationQcResult: mocks.get,
  exportSichuanWorkspaceBatchJob: mocks.export,
  getSichuanWorkspaceBatchJobDebugSnapshot: vi.fn(),
  reviewSichuanWorkspaceBatchJob: vi.fn(),
}))
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: mocks.download,
  normalizeBatchExportBlob: async (value: Blob) => value,
}))
vi.mock(
  '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue',
  () => ({
    default: {
      props: ['batchJobDetail', 'exportBatchJobReport'],
      template:
        '<section>{{ batchJobDetail.id }}<button @click="exportBatchJobReport()">导出</button></section>',
    },
  }),
)
import { useAuthStore } from '@/stores/auth'
import NotificationQcResult from '@/views/workstation/NotificationQcResult.vue'

beforeEach(() => {
  vi.resetAllMocks()
  localStorage.clear()
})

describe('真实认证Store到结果通知的机构上下文', () => {
  it('认证接口返回同账号的新机构后，旧导出应答不能下载', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const user = {
      id: 'manager',
      email: 'synthetic@example.invalid',
      department: '内科',
      roles: ['qc_manager'],
      institute_id: 'A',
      is_active: true,
    }
    mocks.login.mockResolvedValue({ success: true, data: { access_token: 'synthetic-token' } })
    mocks.me.mockResolvedValue({ success: true, data: user })
    mocks.profile.mockResolvedValue({ success: true, data: { ...user, institute_id: 'B' } })
    mocks.get.mockResolvedValue({ success: true, data: { id: 'saved-root' } })
    let resolve!: (value: unknown) => void
    mocks.export.mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    const store = useAuthStore()
    expect((await store.signIn('synthetic', 'synthetic-password')).success).toBe(true)
    const wrapper = mount(NotificationQcResult, {
      global: { plugins: [pinia], stubs: { 'a-spin': true, 'a-result': true, 'a-button': true } },
    })
    try {
      await flushPromises()
      await wrapper.get('button').trigger('click')
      await flushPromises()
      expect(mocks.export).toHaveBeenCalledOnce()
      // 只提交展示名；机构B来自服务端响应，客户端没有自行授予机构。
      await store.updateProfile({ display_name: '合成管理员' })
      await flushPromises()
      expect(store.user?.institute_id).toBe('B')
      expect(store.user?.id).toBe(user.id)
      resolve({ success: true, data: new Blob(['synthetic old export']) })
      await flushPromises()
      expect(mocks.download).not.toHaveBeenCalled()
      expect(mocks.error).not.toHaveBeenCalled()
    } finally {
      wrapper.unmount()
    }
  })
})
