import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import HomeRectificationTodos from '@/views/workstation/HomeRectificationTodos.vue'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  detail: vi.fn(),
  act: vi.fn(),
  comparison: vi.fn(),
  roles: ['doctor'],
  userId: 'd1',
}))
vi.mock('@/api/defectRectifications', () => ({
  listRectifications: mocks.list,
  getRectification: mocks.detail,
  actOnRectification: mocks.act,
  getRectificationComparison: mocks.comparison,
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: mocks.userId, roles: mocks.roles },
    hasRole: (role: string) => mocks.roles.includes(role),
  }),
}))
const task = {
  id: 'r1',
  institute_id: 'H1',
  patient_id: 'P1',
  visit_id: 'V1',
  department: '内科',
  target_id: 'R1',
  target_kind: 'canonical_defect',
  scene: 'running',
  root_job_id: 'J1',
  envelope_id: 'E1',
  assignee_id: 'd1',
  assignee_name: '医生一',
  status: 'pending',
  version: 1,
  requirement: '请补齐相应病历资料并提交',
  events: [],
}
const Drawer = defineComponent({
  props: ['open', 'rootStyle'],
  template: '<div v-if="open"><slot/></div>',
})
const Select = defineComponent({
  props: ['getPopupContainer'],
  template: '<div />',
})
function make(props = {}) {
  return mount(HomeRectificationTodos, {
    props,
    global: {
      stubs: {
        'a-button': { template: '<button><slot/></button>' },
        'a-alert': { props: ['message'], template: '<p>{{message}}</p>' },
        'a-spin': { template: '<div><slot/></div>' },
        'a-select': Select,
        'a-pagination': true,
        'a-drawer': Drawer,
        'a-descriptions': { template: '<div><slot/></div>' },
        'a-descriptions-item': { template: '<div><slot/></div>' },
        'a-form': { template: '<div><slot/></div>' },
        'a-form-item': { template: '<div><slot/></div>' },
        'a-space': { template: '<div><slot/></div>' },
        'a-timeline': { template: '<div><slot/></div>' },
        'a-timeline-item': { template: '<div><slot/></div>' },
        'a-textarea': {
          props: ['value'],
          emits: ['update:value'],
          template:
            '<textarea :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
        },
      },
    },
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.roles = ['doctor']
  mocks.userId = 'd1'
  mocks.list.mockResolvedValue({ items: [task], total: 1 })
  mocks.detail.mockResolvedValue(task)
  mocks.act.mockResolvedValue({ ...task, status: 'submitted' })
})
describe('站内整改待办', () => {
  it('独立页使用V7.1页头，嵌入缺陷时不重复外壳且筛选有真实标签', async () => {
    const page = make()
    await flushPromises()
    expect(page.classes()).toContain('mq-page')
    expect(page.get('label').attributes('for')).toBe('rectification-status')
    expect(page.getComponent(Select).attributes('id')).toBe('rectification-status')
    page.unmount()
    const embedded = make({ scope: task })
    await flushPromises()
    expect(embedded.classes()).not.toContain('mq-page')
    expect(embedded.get('label').attributes('for')).toBe('defect-rectification-status')
    expect(embedded.getComponent(Select).attributes('id')).toBe('defect-rectification-status')
    embedded.unmount()
  })
  it('状态菜单跟随当前容器，嵌入处理弹窗时仍可选择', async () => {
    const wrapper = make()
    await flushPromises()
    const container = document.createElement('div')
    const trigger = document.createElement('div')
    container.append(trigger)
    const popup = wrapper.getComponent(Select).props('getPopupContainer')
    expect(popup).toBeTypeOf('function')
    expect(popup(trigger)).toBe(container)
    wrapper.unmount()
  })
  it('任务详情高于1200层处理弹窗，任务按钮不会提交外层派发表单', async () => {
    const wrapper = make()
    await flushPromises()
    expect(wrapper.get('li button').attributes('type')).toBe('button')
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    expect(wrapper.getComponent(Drawer).props('rootStyle')).toEqual({ zIndex: 1300 })
    wrapper.unmount()
  })
  it.each([
    ['doctor', 'pending'],
    ['qc_manager', 'submitted'],
  ])('%s 默认定位本人待处理环节', async (role, state) => {
    mocks.roles = [role]
    const wrapper = make()
    await flushPromises()
    expect(mocks.list).toHaveBeenCalledWith(state, 1)
    wrapper.unmount()
  })
  it('按需读取选中提交版本，字段差异高亮且不推断整改完成', async () => {
    mocks.detail.mockResolvedValue({
      ...task,
      events: [
        {
          id: 'submit1',
          action: 'submit',
          comment: '合成提交',
          created_at: '2026-10-01',
          version: 2,
        },
      ],
    })
    const before = {
      label: '合成入院记录',
      content: '合成前正文',
      sections: [{ source_field: 'history', label: '现病史', text: '合成前字段' }],
    }
    const after = {
      ...before,
      content: '合成后正文',
      sections: [{ source_field: 'history', label: '现病史', text: '合成后字段' }],
    }
    mocks.comparison.mockResolvedValue({
      available: true,
      documents: [
        { key: ['admission', 'admission_record', 'doc1'], state: 'matched', before, after },
      ],
    })
    const wrapper = make()
    await flushPromises()
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    expect(mocks.comparison).not.toHaveBeenCalled()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '查看本次正文比较')!
      .trigger('click')
    await flushPromises()
    expect(mocks.comparison).toHaveBeenCalledWith('r1', 'submit1')
    expect(wrapper.text()).toContain('派发时 / 本次提交时正文')
    expect(wrapper.get('.comparison-row.changed').text()).toContain('合成前字段')
    expect(wrapper.text()).toContain('合成后正文')
    expect(mocks.act).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('旧整改缺少快照明确不可比较，读取故障不显示无差异', async () => {
    mocks.detail.mockResolvedValue({
      ...task,
      events: [
        {
          id: 'submit1',
          action: 'submit',
          comment: '合成提交',
          created_at: '2026-10-01',
          version: 2,
        },
      ],
    })
    mocks.comparison.mockResolvedValue({
      available: false,
      reason: '缺少派发快照不可比较',
      documents: [],
    })
    const wrapper = make()
    await flushPromises()
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    const button = wrapper.findAll('button').find((item) => item.text() === '查看本次正文比较')!
    await button.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('缺少派发快照不可比较')
    mocks.comparison.mockRejectedValue(new Error('文书读取失败'))
    await button.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('文书读取失败')
    expect(wrapper.text()).not.toContain('缺少派发快照不可比较')
    wrapper.unmount()
  })
  it('切换所选缺陷后丢弃迟到的私有正文比较', async () => {
    mocks.detail.mockResolvedValue({
      ...task,
      events: [
        {
          id: 'submit1',
          action: 'submit',
          comment: '合成提交',
          created_at: '2026-10-01',
          version: 2,
        },
      ],
    })
    let resolve!: (value: unknown) => void
    mocks.comparison.mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    )
    const wrapper = make()
    await flushPromises()
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((item) => item.text() === '查看本次正文比较')!
      .trigger('click')
    await wrapper.setProps({ refreshKey: 1 })
    resolve({
      available: true,
      documents: [
        {
          key: ['admission', 'record', 'doc'],
          state: 'matched',
          before: { label: '不应显示', content: '迟到私有正文', sections: [] },
          after: { label: '不应显示', content: '迟到私有正文', sections: [] },
        },
      ],
    })
    await flushPromises()
    expect(wrapper.text()).not.toContain('迟到私有正文')
    wrapper.unmount()
  })
  it('八维所选缺陷范围查询全部状态并拒绝串入新轮详情', async () => {
    const scope = {
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      scene: 'running',
      target_kind: 'canonical_defect',
      target_id: 'R1',
      root_job_id: 'J1',
      envelope_id: 'E1',
    }
    mocks.detail.mockResolvedValue({ ...task, envelope_id: 'E2' })
    const wrapper = make({ scope })
    await flushPromises()
    expect(mocks.list).toHaveBeenCalledWith(undefined, 1, scope)
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('整改来源与所选缺陷不一致')
    expect(wrapper.findAll('button').some((button) => button.text() === '提交整改')).toBe(false)
    wrapper.unmount()
  })
  it('质控人员撤回有效催办时精确发送事件与当前整改版本', async () => {
    mocks.roles = ['qc_manager']
    mocks.userId = 'q1'
    mocks.detail.mockResolvedValue({
      ...task,
      version: 2,
      events: [
        {
          id: 'urge1',
          action: 'urge',
          comment: '合成催办',
          created_at: '2026-10-01',
          version: 2,
          can_withdraw: true,
        },
      ],
    })
    const wrapper = make()
    await flushPromises()
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    await wrapper.get('textarea').setValue('已与医生沟通撤回本次催办提醒')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '撤回该催办')!
      .trigger('click')
    await flushPromises()
    expect(mocks.act).toHaveBeenCalledWith(
      'r1',
      2,
      'withdraw_urge',
      '已与医生沟通撤回本次催办提醒',
      'urge1',
    )
    wrapper.unmount()
  })
  it('受领医生可从待办查看历史并按当前版本提交', async () => {
    const wrapper = make()
    await flushPromises()
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('提交整改')
    expect(wrapper.text()).not.toContain('验收通过')
    await wrapper.get('textarea').setValue('已核实并补全所有相关病历记录')
    const submit = wrapper.findAll('button').find((button) => button.text() === '提交整改')!
    await submit.trigger('click')
    await flushPromises()
    expect(mocks.act).toHaveBeenCalledWith('r1', 1, 'submit', '已核实并补全所有相关病历记录')
    wrapper.unmount()
  })
  it('读取失败不能显示没有待办', async () => {
    mocks.list.mockRejectedValue(new Error('整改服务暂不可用'))
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('整改服务暂不可用')
    expect(wrapper.text()).not.toContain('没有待处理整改')
    wrapper.unmount()
  })
  it('写入结果未知时禁止盲目重试', async () => {
    mocks.act.mockRejectedValue(new Error('请刷新核对'))
    const wrapper = make()
    await flushPromises()
    await wrapper.get('li button').trigger('click')
    await flushPromises()
    await wrapper.get('textarea').setValue('已核实并补全所有相关病历记录')
    const submit = wrapper.findAll('button').find((button) => button.text() === '提交整改')!
    await submit.trigger('click')
    await flushPromises()
    await submit.trigger('click')
    expect(mocks.act).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
})
