import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Panel from '@/views/workstation-v4/components/system-config/AccountManagementPanel.vue'
import type { AccountPage, ManagedAccount } from '@/api/accountManagement'

const api = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  resetPassword: vi.fn(),
  success: vi.fn(),
}))
const actor = reactive({ id: 'admin', roles: ['admin'] })
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return { id: actor.id }
    },
    get userRoles() {
      return actor.roles
    },
  }),
}))
vi.mock('@/api/accountManagement', () => ({
  listManagedAccounts: api.list,
  createManagedAccount: api.create,
  updateManagedAccount: api.update,
  resetManagedAccountPassword: api.resetPassword,
}))
vi.mock('ant-design-vue', () => ({ message: { success: api.success } }))
const row: ManagedAccount = {
  id: 'doc',
  username: 'doctor1',
  email: 'doctor1@example.com',
  display_name: '合成医生',
  institute_id: 'A',
  department: '内科',
  roles: ['doctor'],
  is_active: true,
  created_at: '2026-10-25T01:00:00+00:00',
  updated_at: '2026-10-25T01:00:00+00:00',
  last_login_at: null,
}
const payload: AccountPage = {
  items: [row],
  total: 1,
  actor_id: 'admin',
  managed_institute_id: 'A',
  page: 1,
  page_size: 20,
}
function make() {
  return mount(Panel, {
    global: {
      stubs: { AModal: { props: ['open'], template: '<aside v-if="open"><slot/></aside>' } },
    },
  })
}
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}
beforeEach(() => {
  vi.clearAllMocks()
  actor.id = 'admin'
  actor.roles = ['admin']
  api.list.mockResolvedValue(structuredClone(payload))
  api.create.mockResolvedValue(row)
  api.update.mockResolvedValue(row)
  api.resetPassword.mockResolvedValue({ ...row, updated_at: '2026-10-25T02:00:00+00:00' })
})

describe('V5 持久账号管理', () => {
  it('超级管理员角色正确显示，仍由专用权限系统维护', async () => {
    actor.roles = ['sync_admin', 'admin']
    api.list.mockResolvedValue({
      ...payload,
      managed_institute_id: null,
      items: [{ ...row, display_name: '超级管理员验收', roles: ['sync_admin'] }],
    })
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('超级管理员')
    expect(wrapper.text()).not.toContain('未知角色')
    expect(wrapper.get('[aria-label="编辑超级管理员验收"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('无邮箱注册用户可以显示和编辑，不要求补填邮箱', async () => {
    api.list.mockResolvedValue({ ...payload, items: [{ ...row, email: null }] })
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('合成医生')
    await wrapper.get('[aria-label="编辑合成医生"]').trigger('click')
    expect((wrapper.get('input[aria-label="邮箱"]').element as HTMLInputElement).value).toBe('')
    await wrapper.get('.accounts-editor').trigger('submit')
    await flushPromises()
    expect(api.update).toHaveBeenCalledWith('doc', expect.not.objectContaining({ email: expect.anything() }))
    wrapper.unmount()
  })
  it('超级管理员的全局DTO不锁机构输入，可创建其他机构账号', async () => {
    actor.roles = ['sync_admin', 'admin']
    api.list.mockResolvedValue({ ...structuredClone(payload), managed_institute_id: null })
    const wrapper = make()
    await flushPromises()
    await wrapper.get('.accounts-actions button:last-child').trigger('click')
    expect(wrapper.get('input[aria-label="机构 ID"]').attributes('readonly')).toBeUndefined()
    for (const [label, value] of Object.entries({
      用户名: 'other_doctor',
      邮箱: 'other@example.com',
      姓名: '其他机构医生',
      '机构 ID': 'B',
      科室: '外科',
      初始口令: 'test-only-password!',
    }))
      await wrapper.get(`input[aria-label="${label}"]`).setValue(value)
    await wrapper.get('.accounts-editor').trigger('submit')
    await flushPromises()
    expect(api.create).toHaveBeenCalledWith(expect.objectContaining({ institute_id: 'B' }))
    wrapper.unmount()
  })

  it('真实列表、加载、未知范围及错误状态不使用演示用户', async () => {
    const request = deferred<AccountPage>()
    api.list.mockReturnValueOnce(request.promise)
    const wrapper = make()
    expect(wrapper.text()).toContain('正在读取账号')
    request.resolve(payload)
    await flushPromises()
    expect(wrapper.text()).toContain('合成医生')
    expect(wrapper.text()).toContain('尚未登录')
    api.list.mockRejectedValueOnce(new Error('仅持久系统管理员可以管理账号'))
    await wrapper.get('.accounts-actions button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('仅持久系统管理员可以管理账号')
    expect(wrapper.text()).not.toContain('合成医生')
    expect(wrapper.get('.accounts-actions button:last-child').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('新建账号仅提交正式字段且取消即清空口令', async () => {
    const wrapper = make()
    await flushPromises()
    await wrapper.get('.accounts-actions button:last-child').trigger('click')
    for (const [label, value] of Object.entries({
      用户名: 'doc_new',
      邮箱: 'new@example.com',
      姓名: '新医生',
      科室: '外科',
      初始口令: 'test-only-password!',
    }))
      await wrapper.get(`input[aria-label="${label}"]`).setValue(value)
    expect(wrapper.get('input[aria-label="机构 ID"]').attributes('readonly')).toBeDefined()
    await wrapper.get('.accounts-editor').trigger('submit')
    await flushPromises()
    expect(api.create).toHaveBeenCalledWith({
      username: 'doc_new',
      email: 'new@example.com',
      display_name: '新医生',
      institute_id: 'A',
      department: '外科',
      password: 'test-only-password!',
      roles: ['doctor'],
    })
    expect(wrapper.find('aside').exists()).toBe(false)
    await wrapper.get('.accounts-actions button:last-child').trigger('click')
    expect((wrapper.get('input[aria-label="初始口令"]').element as HTMLInputElement).value).toBe('')
    wrapper.unmount()
  })
  it('编辑保持唯一身份，传递并发版本，停用经确认保存', async () => {
    const wrapper = make()
    await flushPromises()
    await wrapper.get('[aria-label="编辑合成医生"]').trigger('click')
    expect(wrapper.get('input[aria-label="用户名"]').attributes('readonly')).toBeDefined()
    await wrapper.get('.accounts-enabled input').setValue(false)
    await wrapper.get('.accounts-editor').trigger('submit')
    await flushPromises()
    expect(api.update).toHaveBeenCalledWith('doc', {
      display_name: '合成医生',
      institute_id: 'A',
      department: '内科',
      roles: ['doctor'],
      is_active: false,
      expected_updated_at: row.updated_at,
    })
    wrapper.unmount()
  })
  it('409不乐观改列表，不丢编辑内容，不重复提交', async () => {
    const pending = deferred<ManagedAccount>()
    api.update.mockReturnValueOnce(pending.promise)
    const wrapper = make()
    await flushPromises()
    await wrapper.get('[aria-label="编辑合成医生"]').trigger('click')
    await wrapper.get('input[aria-label="姓名"]').setValue('修改草稿')
    await wrapper.get('.accounts-editor').trigger('submit')
    await wrapper.get('.accounts-editor').trigger('submit')
    expect(api.update).toHaveBeenCalledTimes(1)
    pending.resolve(row)
    await flushPromises()
    api.update.mockRejectedValueOnce(new Error('账号已被修改，请刷新后再操作'))
    await wrapper.get('[aria-label="编辑合成医生"]').trigger('click')
    await wrapper.get('.accounts-editor').trigger('submit')
    await flushPromises()
    expect(wrapper.get('aside').text()).toContain('账号已被修改')
    expect(wrapper.get('tbody').text()).toContain('合成医生')
    wrapper.unmount()
  })
  it('切换账号后旧读取不显示，旧保存不提示成功', async () => {
    const pending = deferred<ManagedAccount>()
    api.create.mockReturnValueOnce(pending.promise)
    const wrapper = make()
    await flushPromises()
    await wrapper.get('.accounts-actions button:last-child').trigger('click')
    await wrapper.get('input[aria-label="初始口令"]').setValue('test-only-password!')
    await wrapper.get('.accounts-editor').trigger('submit')
    actor.roles = ['doctor']
    actor.id = 'other'
    await flushPromises()
    pending.resolve(row)
    await flushPromises()
    expect(wrapper.find('aside').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('合成医生')
    expect(api.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('角色筛选和分页使用同一服务，不截取前端假数据', async () => {
    api.list.mockResolvedValue({ ...payload, total: 25 })
    const wrapper = make()
    await flushPromises()
    await wrapper.get('select[aria-label="筛选角色"]').setValue('qc_staff')
    await wrapper.get('select[aria-label="筛选状态"]').setValue('inactive')
    await wrapper.get('.accounts-filters').trigger('submit')
    await flushPromises()
    expect(api.list).toHaveBeenLastCalledWith({
      keyword: '',
      role: 'qc_staff',
      active: false,
      page: 1,
      page_size: 20,
    })
    await wrapper.get('[aria-label="下一页账号"]').trigger('click')
    await flushPromises()
    expect(api.list).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }))
    wrapper.unmount()
  })
  it('自身账号不可停用或变更角色科室，且不显示重置密码入口', async () => {
    api.list.mockResolvedValue({ ...payload, items: [{ ...row, id: 'admin', roles: ['admin'] }] })
    const wrapper = make()
    await flushPromises()
    await wrapper.get('[aria-label="编辑合成医生"]').trigger('click')
    expect(wrapper.get('.accounts-role-fields').attributes('disabled')).toBeDefined()
    expect(wrapper.get('.accounts-enabled input').attributes('disabled')).toBeDefined()
    expect(wrapper.get('input[aria-label="科室"]').attributes('readonly')).toBeDefined()
    expect(wrapper.find('[data-testid="toggle-reset-password"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('编辑无邮箱与历史用户名账号时取消只读字段的原生必填与正则校验', async () => {
    api.list.mockResolvedValue({
      ...payload,
      items: [{ ...row, username: 'legacy@user', email: null }],
    })
    const wrapper = make()
    await flushPromises()
    // 新建时仍保留 required 与 pattern
    await wrapper.get('.accounts-actions button:last-child').trigger('click')
    expect(wrapper.get('input[aria-label="用户名"]').attributes('required')).toBeDefined()
    expect(wrapper.get('input[aria-label="用户名"]').attributes('pattern')).toBe(
      '[A-Za-z0-9][A-Za-z0-9_.-]+',
    )
    expect(wrapper.get('input[aria-label="邮箱"]').attributes('required')).toBeDefined()
    await wrapper.get('.accounts-editor-actions button[type="button"]').trigger('click')

    // 编辑历史账号时取消必填、最小长度与正则约束
    await wrapper.get('[aria-label="编辑合成医生"]').trigger('click')
    expect(wrapper.get('input[aria-label="用户名"]').attributes('required')).toBeUndefined()
    expect(wrapper.get('input[aria-label="用户名"]').attributes('pattern')).toBeUndefined()
    expect(wrapper.get('input[aria-label="用户名"]').attributes('minlength')).toBeUndefined()
    expect(wrapper.get('input[aria-label="邮箱"]').attributes('required')).toBeUndefined()
    wrapper.unmount()
  })
  it('编辑未绑定全局管理员允许保持机构 ID 为空而不强制降级', async () => {
    actor.roles = ['super_admin']
    api.list.mockResolvedValue({
      ...payload,
      managed_institute_id: null,
      items: [
        {
          ...row,
          id: 'global-admin',
          username: 'global_admin',
          display_name: '全局管理员',
          institute_id: null,
          roles: ['admin'],
        },
      ],
    })
    const wrapper = make()
    await flushPromises()
    await wrapper.get('[aria-label="编辑全局管理员"]').trigger('click')
    expect(wrapper.get('input[aria-label="机构 ID"]').attributes('required')).toBeUndefined()
    await wrapper.get('input[aria-label="姓名"]').setValue('全局管理员已改')
    await wrapper.get('.accounts-editor').trigger('submit')
    await flushPromises()
    expect(api.update).toHaveBeenCalledWith(
      'global-admin',
      expect.objectContaining({
        display_name: '全局管理员已改',
        institute_id: null,
        roles: ['admin'],
      }),
    )
    wrapper.unmount()
  })
  it('支持编码员(coder)角色展示、筛选与编辑', async () => {
    api.list.mockResolvedValue({
      ...payload,
      items: [{ ...row, id: 'coder1', display_name: '编码员甲', roles: ['coder'] }],
    })
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('编码员')
    const editBtn = wrapper.get('[aria-label="编辑编码员甲"]')
    expect(editBtn.attributes('disabled')).toBeUndefined()
    await editBtn.trigger('click')
    const coderCheckbox = wrapper.get('.accounts-role-fields input[value="coder"]')
    expect((coderCheckbox.element as HTMLInputElement).checked).toBe(true)
    wrapper.unmount()
  })
  it('编辑非本人账号支持重置密码、校验口令并同步更新时间', async () => {
    const wrapper = make()
    await flushPromises()
    await wrapper.get('[aria-label="编辑合成医生"]').trigger('click')
    await wrapper.get('[data-testid="toggle-reset-password"]').trigger('click')

    // 短口令不触发请求
    await wrapper.get('input[aria-label="新口令"]').setValue('too-short')
    await wrapper.get('.accounts-reset-form').trigger('submit')
    expect(api.resetPassword).not.toHaveBeenCalled()
    expect(wrapper.get('.accounts-reset-section').text()).toContain('至少12个字符')

    // 合法口令提交后提示成功、清空输入并更新 expected_updated_at
    await wrapper.get('input[aria-label="新口令"]').setValue('new-valid-password-123!')
    await wrapper.get('.accounts-reset-form').trigger('submit')
    await flushPromises()
    expect(api.resetPassword).toHaveBeenCalledWith('doc', {
      password: 'new-valid-password-123!',
      expected_updated_at: row.updated_at,
    })
    expect(api.success).toHaveBeenCalledWith('密码已重置')
    expect(wrapper.get('.accounts-reset-section').text()).toContain('密码已重置')

    // 后续保存使用更新后的 updated_at，不触发 409
    await wrapper.get('.accounts-editor').trigger('submit')
    await flushPromises()
    expect(api.update).toHaveBeenCalledWith(
      'doc',
      expect.objectContaining({ expected_updated_at: '2026-10-25T02:00:00+00:00' }),
    )
    wrapper.unmount()
  })
})
