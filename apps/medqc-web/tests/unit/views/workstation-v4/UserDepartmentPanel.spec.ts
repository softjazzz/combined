import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ list: vi.fn(), update: vi.fn() }))

vi.mock('@/api/adminUsers', () => ({
  DEPARTMENT_MAX_LENGTH: 100,
  UNASSIGNED_DEPARTMENT: '__unassigned__',
  listAdminUsers: mocks.list,
  updateUserDepartment: mocks.update,
}))

import UserDepartmentPanel from '@/views/workstation-v4/components/system-config/UserDepartmentPanel.vue'

function user(id: string, department: string | null) {
  return {
    id, username: id, display_name: `用户${id}`, department, roles: ['doctor'],
    is_active: true, updated_at: '2026-09-30T08:00:00',
  }
}

function page(items: unknown[]) {
  return { success: true, data: { items, total: items.length, page: 1, page_size: 20, departments: ['心内科'] } }
}

function render() {
  return mount(UserDepartmentPanel, {
    global: { stubs: { 'a-alert': { props: ['message', 'description'], template: '<div class="alert">{{ message }} {{ description }}</div>' } } },
  })
}

describe('UserDepartmentPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.list.mockResolvedValue(page([user('d1', '心内科'), user('d2', null)]))
  })

  it('读取账号并把未分配科室明确标出', async () => {
    const wrapper = render()
    await flushPromises()
    expect(mocks.list).toHaveBeenCalledWith({ page: 1, page_size: 20, q: '', department: '' })
    expect(wrapper.get('tr[data-id="d1"]').text()).toContain('心内科')
    expect(wrapper.get('tr[data-id="d2"]').text()).toContain('未分配')
  })

  it('按关键字与未分配筛选查询', async () => {
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="user-department-keyword"]').setValue(' 张 ')
    await wrapper.get('[data-testid="user-department-filter"]').setValue('__unassigned__')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.list).toHaveBeenLastCalledWith({ page: 1, page_size: 20, q: '张', department: '__unassigned__' })
  })

  it('保存科室携带账号版本并就地回显', async () => {
    mocks.update.mockResolvedValue({
      success: true, resultUnknown: false, conflict: false,
      data: { ...user('d2', '骨科'), updated_at: '2026-09-30T09:00:00' },
    })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="user-department-edit-d2"]').trigger('click')
    await wrapper.get('[data-testid="user-department-input-d2"]').setValue(' 骨科 ')
    await wrapper.get('[data-testid="user-department-save-d2"]').trigger('click')
    await flushPromises()
    expect(mocks.update).toHaveBeenCalledWith('d2', { department: '骨科', expected_updated_at: '2026-09-30T08:00:00' })
    expect(wrapper.get('tr[data-id="d2"]').text()).toContain('骨科')
    expect(wrapper.get('[data-testid="user-department-notice"]').text()).toContain('骨科')
  })

  it('版本冲突提示并回读列表', async () => {
    mocks.update.mockResolvedValue({ success: false, resultUnknown: false, conflict: true, message: '账号已被修改，请刷新后重试' })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="user-department-edit-d1"]').trigger('click')
    await wrapper.get('[data-testid="user-department-input-d1"]').setValue('骨科')
    await wrapper.get('[data-testid="user-department-save-d1"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="user-department-notice"]').text()).toContain('已被修改')
    expect(mocks.list).toHaveBeenCalledTimes(2)
  })

  it('结果未知时锁定修改且不自动重试，刷新后解除', async () => {
    mocks.update.mockResolvedValue({ success: false, resultUnknown: true, conflict: false, message: '科室保存结果无法确认' })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="user-department-edit-d1"]').trigger('click')
    await wrapper.get('[data-testid="user-department-input-d1"]').setValue('骨科')
    await wrapper.get('[data-testid="user-department-save-d1"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="user-department-unknown"]').exists()).toBe(true)
    expect(mocks.update).toHaveBeenCalledTimes(1)
    expect(mocks.list).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="user-department-refresh"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="user-department-unknown"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="user-department-edit-d1"]').attributes('disabled')).toBeUndefined()
  })

  it('未修改时不发请求', async () => {
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="user-department-edit-d1"]').trigger('click')
    await wrapper.get('[data-testid="user-department-save-d1"]').trigger('click')
    expect(mocks.update).not.toHaveBeenCalled()
  })
})
