import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AppealList from '@/views/qc/AppealList.vue'
import { AppealStatus, AppealType } from '@/types/appeal'

const { mockGetAppeals, mockWithdrawAppeal } = vi.hoisted(() => ({
  mockGetAppeals: vi.fn(),
  mockWithdrawAppeal: vi.fn(),
}))

const mockAuthStore = reactive({
  user: { id: 'doc-1' } as { id: string } | null,
  userRoles: ['doctor'] as string[],
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}))

vi.mock('@/api/appeal', () => ({
  getAppeals: mockGetAppeals,
  withdrawAppeal: mockWithdrawAppeal,
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

const sampleAppeals = [
  {
    id: 'appeal-own',
    defectId: 'd-1',
    recordId: 'r-1',
    appellantId: 'doc-1',
    appellantName: '张医生',
    appealType: AppealType.INCORRECT_RULE,
    appealReason: '系统误判',
    status: AppealStatus.PENDING,
    createdAt: '2026-10-01T10:00:00',
    reviewerName: null,
    reviewedAt: null,
  },
  {
    id: 'appeal-other',
    defectId: 'd-2',
    recordId: 'r-2',
    appellantId: 'doc-2',
    appellantName: '李医生',
    appealType: AppealType.SPECIAL_CASE,
    appealReason: '特殊病情',
    status: AppealStatus.PENDING,
    createdAt: '2026-10-01T11:00:00',
    reviewerName: null,
    reviewedAt: null,
  },
]

function mountAppealList() {
  return mount(AppealList, {
    global: {
      stubs: {
        'a-page-header': { template: '<div />' },
        'a-card': { template: '<div><slot /></div>' },
        'a-form': { template: '<form><slot /></form>' },
        'a-form-item': { template: '<div><slot /></div>' },
        'a-select': { template: '<select><slot /></select>' },
        'a-select-option': { template: '<option><slot /></option>' },
        'a-tag': { template: '<span><slot /></span>' },
        'a-space': { template: '<div><slot /></div>' },
        'a-popconfirm': { template: '<span class="withdraw-confirm"><slot /></span>' },
        'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        AppealReviewModal: { template: '<div />' },
        'a-table': {
          props: ['dataSource', 'columns'],
          template: `
            <table>
              <tbody>
                <tr v-for="record in dataSource" :key="record.id" :data-appeal-id="record.id">
                  <td>
                    <slot name="bodyCell" :column="{ key: 'action' }" :record="record" />
                  </td>
                </tr>
              </tbody>
            </table>
          `,
        },
      },
    },
  })
}

describe('AppealList 权限推导', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockGetAppeals.mockResolvedValue({ items: sampleAppeals, total: sampleAppeals.length })
  })

  it('普通医生无审核权限，且仅能撤销自己的待审核申诉', async () => {
    mockAuthStore.user = { id: 'doc-1' }
    mockAuthStore.userRoles = ['doctor']

    const wrapper = mountAppealList()
    await flushPromises()

    const ownRow = wrapper.get('tr[data-appeal-id="appeal-own"]')
    const otherRow = wrapper.get('tr[data-appeal-id="appeal-other"]')

    expect(ownRow.text()).not.toContain('审核')
    expect(ownRow.text()).toContain('撤销')
    expect(otherRow.text()).not.toContain('审核')
    expect(otherRow.text()).not.toContain('撤销')
    wrapper.unmount()
  })

  it.each(['admin', 'qc_manager', 'sync_admin', 'super_admin'])(
    '角色 %s 拥有待审核申诉的审核权限',
    async (role) => {
      mockAuthStore.user = { id: 'reviewer-1' }
      mockAuthStore.userRoles = [role]

      const wrapper = mountAppealList()
      await flushPromises()

      const ownRow = wrapper.get('tr[data-appeal-id="appeal-own"]')
      expect(ownRow.text()).toContain('审核')
      expect(ownRow.text()).not.toContain('撤销')
      wrapper.unmount()
    },
  )

  it('未登录用户既无审核权限也无撤销权限', async () => {
    mockAuthStore.user = null
    mockAuthStore.userRoles = []

    const wrapper = mountAppealList()
    await flushPromises()

    const tbodyText = wrapper.get('tbody').text()
    expect(tbodyText).not.toContain('审核')
    expect(tbodyText).not.toContain('撤销')
    wrapper.unmount()
  })
})
