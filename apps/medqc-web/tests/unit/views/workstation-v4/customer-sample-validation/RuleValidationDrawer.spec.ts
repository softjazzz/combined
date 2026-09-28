import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import RuleValidationDrawer from '@/views/workstation-v4/customer-sample-validation/RuleValidationDrawer.vue'
import * as api from '@/services/test-case-validation-service'
vi.mock('@/services/test-case-validation-service', () => ({ readValidation: vi.fn(), saveValidation: vi.fn(), startValidation: vi.fn(), readValidationResult: vi.fn(), reviewValidation: vi.fn() }))
const answer = { qc_point_id: 'LX0609-01-01-01', expected_status: 'non_compliant' as const, human_reason: '超时', trigger_facts: [], evidence_keywords: [] }
const initial = { revision: 1, answers: [answer], runs: [], rule_options: [] }
const wrap = { template: '<div><slot /></div>' }
const input = defineComponent({ props: ['value'], emits: ['update:value'], template: `<textarea :value="value" @input="$emit('update:value', $event.target.value)" />` })
const select = defineComponent({ props: ['value', 'options'], emits: ['update:value', 'change'], template: `<select :value="value" @change="$emit('update:value', $event.target.value); $emit('change', $event.target.value)"><option v-for="o in options" :key="o.value" :value="o.value">{{o.label}}</option></select>` })
function create(itemId = 'case') {
  return mount(RuleValidationDrawer, { props: { itemId }, global: { stubs: {
    ADrawer: wrap, ASpin: wrap, AAlert: { props: ['message'], template: '<p>{{ message }}</p>' },
    ASelect: select, ATextarea: input, AButton: { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' }, ATable: true,
  } } })
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.readValidation).mockResolvedValue({ success: true, data: structuredClone(initial) })
})
describe('单病例规则验收', () => {
  it('编辑后禁止直接运行；保存成功后恢复可运行', async () => {
    const wrapper = create()
    await flushPromises()
    const start = () => wrapper.findAll('button').find(b => b.text() === '按已保存预期启动验证')!
    expect(start().attributes('disabled')).toBeUndefined()
    await wrapper.find('[aria-label="人工预期依据"]').setValue('新的人工依据')
    expect(start().attributes('disabled')).toBeDefined()
    vi.mocked(api.saveValidation).mockResolvedValue({ success: true, data: { ...initial, revision: 2, answers: [{ ...answer, human_reason: '新的人工依据' }] } })
    await wrapper.findAll('button').find(b => b.text() === '保存预期')!.trigger('click')
    await flushPromises()
    expect(api.saveValidation).toHaveBeenCalledWith('case', 1, expect.arrayContaining([expect.objectContaining({ human_reason: '新的人工依据' })]))
    expect(start().attributes('disabled')).toBeUndefined()
  })
  it('切换病例后丢弃旧病例迟到响应', async () => {
    let resolveOld!: (value: Awaited<ReturnType<typeof api.readValidation>>) => void
    vi.mocked(api.readValidation).mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve }))
    const wrapper = create('old')
    await wrapper.setProps({ itemId: 'new' })
    await flushPromises()
    resolveOld({ success: true, data: { ...initial, revision: 99 } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('修订 99')
    expect(wrapper.text()).toContain('修订 1')
  })
  it('失败响应保留错误，不当作空列表或通过', async () => {
    vi.mocked(api.readValidation).mockResolvedValue({ success: false, error: '无权限' })
    const wrapper = create()
    await flushPromises()
    expect(wrapper.text()).toContain('无权限')
    expect(wrapper.text()).not.toContain('人工确认通过')
  })
})
