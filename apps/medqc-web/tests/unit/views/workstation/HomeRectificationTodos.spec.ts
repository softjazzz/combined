import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import HomeRectificationTodos from '@/views/workstation/HomeRectificationTodos.vue'

const mocks = vi.hoisted(() => ({ list: vi.fn(), detail: vi.fn(), act: vi.fn() }))
vi.mock('@/api/defectRectifications', () => ({
  listRectifications: mocks.list,
  getRectification: mocks.detail,
  actOnRectification: mocks.act,
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: 'd1', roles: ['doctor'] },
    hasRole: (role: string) => role === 'doctor',
  }),
}))
const task = {
  id: 'r1',
  institute_id: 'H1',
  patient_id: 'P1',
  visit_id: 'V1',
  department: '内科',
  target_id: 'R1',
  assignee_id: 'd1',
  assignee_name: '医生一',
  status: 'pending',
  version: 1,
  requirement: '请补齐相应病历资料并提交',
  events: [],
}
function make() {
  return mount(HomeRectificationTodos, {
    global: {
      stubs: {
        'a-button': { template: '<button><slot/></button>' },
        'a-alert': { props: ['message'], template: '<p>{{message}}</p>' },
        'a-spin': { template: '<div><slot/></div>' },
        'a-select': true,
        'a-pagination': true,
        'a-drawer': { props: ['open'], template: '<div v-if="open"><slot/></div>' },
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
  mocks.list.mockResolvedValue({ items: [task], total: 1 })
  mocks.detail.mockResolvedValue(task)
  mocks.act.mockResolvedValue({ ...task, status: 'submitted' })
})
describe('站内整改待办', () => {
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
