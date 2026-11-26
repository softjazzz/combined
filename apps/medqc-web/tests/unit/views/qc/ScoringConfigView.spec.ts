import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ScoringConfigView from '@/views/qc/ScoringConfigView.vue'

const { mockApiGet, mockApiPut, mockMessageSuccess, mockMessageError, mockAuthStore } = vi.hoisted(() => ({
  mockApiGet: vi.fn(),
  mockApiPut: vi.fn(),
  mockMessageSuccess: vi.fn(),
  mockMessageError: vi.fn(),
  mockAuthStore: {
    userRoles: ['admin'] as string[],
    user: { institute_id: '' } as { institute_id?: string | null } | null,
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}))

vi.mock('@/services/apiService', () => ({
  apiClient: {
    get: mockApiGet,
    put: mockApiPut,
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: mockMessageSuccess,
    error: mockMessageError,
  },
}))

function mountView() {
  return mount(ScoringConfigView, {
    global: {
      stubs: {
        'a-alert': {
          props: { message: { type: String, default: '' }, description: { type: String, default: '' } },
          template: '<div data-testid="scoring-readonly-alert">{{ message }} {{ description }}</div>',
        },
        'a-spin': { template: '<div><slot /></div>' },
        'a-tag': { template: '<span><slot /></span>' },
        'a-input-number': {
          props: { disabled: { type: Boolean, default: false } },
          template: '<input :disabled="disabled" />',
        },
        'a-table': { template: '<div />' },
        'a-button': {
          props: { disabled: { type: Boolean, default: false } },
          template: '<button type="button" :disabled="disabled"><slot /></button>',
        },
        SettingOutlined: true,
        TrophyOutlined: true,
        AlertOutlined: true,
        ControlOutlined: true,
        EyeOutlined: true,
        UndoOutlined: true,
        SaveOutlined: true,
      },
    },
  })
}

describe('ScoringConfigView 使用 apiClient 且如实展示错误', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockAuthStore.userRoles = ['admin']
    mockAuthStore.user = { institute_id: '' }
  })

  it('通过 apiClient 加载配置并在成功保存时提示成功', async () => {
    mockApiGet.mockResolvedValueOnce({
      data: {
        success: true,
        data: { base_score: 100, pass_score: 75 },
      },
    })
    mockApiPut.mockResolvedValueOnce({
      data: { success: true },
    })

    const wrapper = mountView()
    await flushPromises()
    expect(mockApiGet).toHaveBeenCalledWith('/api/v1/scoring-config')

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存配置'))!
    await saveBtn.trigger('click')
    await flushPromises()

    expect(mockApiPut).toHaveBeenCalledWith(
      '/api/v1/scoring-config',
      expect.objectContaining({ base_score: 100, pass_score: 75 }),
    )
    expect(mockMessageSuccess).toHaveBeenCalledWith('评分配置保存成功')
    expect(mockMessageError).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it.each([
    [401, '未登录或会话已过期'],
    [403, '需要管理员权限'],
    [500, '数据库写入失败'],
  ])('保存返回 HTTP %s 时绝不误报成功，且展示真实错误详情', async (status, detail) => {
    mockApiGet.mockResolvedValueOnce({ data: { success: true, data: {} } })
    mockApiPut.mockRejectedValueOnce({
      response: { status, data: { detail } },
    })

    const wrapper = mountView()
    await flushPromises()

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存配置'))!
    await saveBtn.trigger('click')
    await flushPromises()

    expect(mockMessageSuccess).not.toHaveBeenCalled()
    expect(mockMessageError).toHaveBeenCalledWith(detail)
    wrapper.unmount()
  })

  it('加载评分配置遇到 403/500 时展示错误提示', async () => {
    mockApiGet.mockRejectedValueOnce({
      response: { status: 403, data: { detail: '无权访问评分配置' } },
    })

    const wrapper = mountView()
    await flushPromises()

    expect(mockMessageError).toHaveBeenCalledWith('无权访问评分配置')
    wrapper.unmount()
  })

  it.each([
    { label: 'qc_manager', roles: ['qc_manager'], institute_id: '' },
    { label: '绑定院区 admin', roles: ['admin'], institute_id: 'H1' },
    { label: 'doctor', roles: ['doctor'], institute_id: '' },
  ])('$label 进入只读模式：展示只读提示、禁用保存与重置、点击不发起 PUT', async ({ roles, institute_id }) => {
    mockAuthStore.userRoles = roles
    mockAuthStore.user = { institute_id }
    mockApiGet.mockResolvedValueOnce({ data: { success: true, data: { base_score: 100, pass_score: 70 } } })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('[data-testid="scoring-readonly-alert"]').exists()).toBe(true)
    const saveBtn = wrapper.get('[data-testid="scoring-config-save"]')
    const resetBtn = wrapper.get('[data-testid="scoring-config-reset"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()
    expect(resetBtn.attributes('disabled')).toBeDefined()

    await saveBtn.trigger('click')
    await flushPromises()
    expect(mockApiPut).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it.each([
    { label: '全局 admin', roles: ['admin'], institute_id: '' },
    { label: 'super_admin (带院区)', roles: ['super_admin'], institute_id: 'H1' },
    { label: 'sync_admin (带院区)', roles: ['sync_admin'], institute_id: 'H1' },
  ])('$label 允许编辑评分配置', async ({ roles, institute_id }) => {
    mockAuthStore.userRoles = roles
    mockAuthStore.user = { institute_id }
    mockApiGet.mockResolvedValueOnce({ data: { success: true, data: { base_score: 100, pass_score: 70 } } })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('[data-testid="scoring-readonly-alert"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="scoring-config-save"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="scoring-config-reset"]').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })
})
