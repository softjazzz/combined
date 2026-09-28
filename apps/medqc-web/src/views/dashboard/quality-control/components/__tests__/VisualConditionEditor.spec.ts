import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import VisualConditionEditor from '../VisualConditionEditor.vue'
import type { VisualConditionOptions, VisualConditionTree } from '@/types/custom-rule-workspace'

const options: VisualConditionOptions = {
  schema_version: 'visual-condition-v1',
  fields: [{
    key: 'record.department', label: '当前科室', value_type: 'string', kind: 'record',
    operators: [
      { value: 'eq', label: '等于', value_required: true },
      { value: 'in', label: '属于', value_required: true, value_options: [{ value: '内科', label: '内科' }, { value: '外科', label: '外科' }] },
      { value: 'exists', label: '存在', value_required: false },
    ],
  }],
  document_types: [{ value: 'discharge_record', label: '出院记录' }],
  group_operators: ['all', 'any'],
  limits: { max_groups: 3, max_conditions_per_group: 4 },
  result_semantics: { true: 'non_compliant', false: 'compliant', unknown: 'data_gap' },
  timeliness: {
    start_fields: [{ value: 'record.admission_datetime', label: '入院时间' }, { value: 'record.discharge_datetime', label: '出院时间' }],
    end_fields: [{ value: 'document.discharge_record.latest', label: '出院记录时间' }],
    allowed_pairs: [{ start_fact: 'record.admission_datetime', end_fact: 'document.discharge_record.latest' }],
    operators: [{ value: 'gt', label: '超过' }, { value: 'lte', label: '不超过' }],
    units: [{ value: 'hours', label: '小时' }, { value: 'days', label: '天' }],
  },
}
const emptyTree: VisualConditionTree = {
  schema_version: 'visual-condition-v1', root_operator: 'all',
  groups: [{ id: 'group-1', operator: 'all', conditions: [] }],
}

describe('VisualConditionEditor', () => {
  it('空条件组拒绝保存且明确真值为缺陷触发', async () => {
    const wrapper = mount(VisualConditionEditor, { props: { modelValue: emptyTree, options } })
    expect(wrapper.text()).toContain('条件结果为真时触发缺陷')
    await wrapper.get('[data-testid="save-visual-condition"]').trigger('click')
    expect(wrapper.text()).toContain('条件组不能为空')
    expect(wrapper.emitted('save')).toBeUndefined()
  })

  it('编辑后上报未保存状态，服务端回读模型恢复后清除', async () => {
    const wrapper = mount(VisualConditionEditor, { props: { modelValue: emptyTree, options } })
    await wrapper.get('select').setValue('any')
    expect(wrapper.emitted('dirty')?.slice(-1)[0]).toEqual([true])
    const savedTree = { ...emptyTree, root_operator: 'any' as const }
    await wrapper.setProps({ modelValue: savedTree })
    expect(wrapper.emitted('dirty')?.slice(-1)[0]).toEqual([false])
  })

  it('字段与操作符来自目录且in提交真实数组', async () => {
    const wrapper = mount(VisualConditionEditor, { props: { modelValue: emptyTree, options } })
    await wrapper.get('.group-actions button').trigger('click')
    const selects = wrapper.findAll('.condition-row select')
    await selects[1].setValue('record.department')
    await selects[2].setValue('in')
    const multi = wrapper.get('select[aria-label="比较值"]')
    await multi.setValue(['内科', '外科'])
    await wrapper.get('[data-testid="save-visual-condition"]').trigger('click')
    const saved = wrapper.emitted('save')?.[0]?.[0] as VisualConditionTree
    expect(saved.groups[0].conditions[0]).toMatchObject({
      kind: 'field', fact_key: 'record.department', operator: 'in', value: ['内科', '外科'],
    })
  })

  it('in无枚举目录时逐项录入数组而不解析逗号字符串', async () => {
    const freeValueOptions: VisualConditionOptions = {
      ...options,
      fields: [{ ...options.fields[0], operators: options.fields[0].operators.map((item) => ({ ...item, value_options: undefined })) }],
    }
    const wrapper = mount(VisualConditionEditor, { props: { modelValue: emptyTree, options: freeValueOptions } })
    await wrapper.get('.group-actions button').trigger('click')
    const selects = wrapper.findAll('.condition-row select')
    await selects[1].setValue('record.department')
    await selects[2].setValue('in')
    await wrapper.get('.add-value-button').trigger('click')
    await wrapper.get('input[aria-label="比较值项"]').setValue('内科,外科')
    await wrapper.get('[data-testid="save-visual-condition"]').trigger('click')
    const saved = wrapper.emitted('save')?.[0]?.[0] as VisualConditionTree
    expect(saved.groups[0].conditions[0]).toMatchObject({ value: ['内科,外科'] })
  })

  it('切换字段操作符清除不兼容值', async () => {
    const tree: VisualConditionTree = {
      ...emptyTree,
      groups: [{ id: 'group-1', operator: 'all', conditions: [{ id: 'c1', kind: 'field', fact_key: 'record.department', operator: 'eq', value: '内科' }] }],
    }
    const wrapper = mount(VisualConditionEditor, { props: { modelValue: tree, options } })
    await wrapper.get('select[aria-label="操作符"]').setValue('exists')
    await wrapper.get('[data-testid="save-visual-condition"]').trigger('click')
    expect((wrapper.emitted('save')?.[0]?.[0] as VisualConditionTree).groups[0].conditions[0]).not.toHaveProperty('value')
  })

  it('时效终点只能选择服务端允许的起止配对', async () => {
    const wrapper = mount(VisualConditionEditor, { props: { modelValue: emptyTree, options } })
    await wrapper.findAll('.group-actions button')[2].trigger('click')
    await wrapper.get('select[aria-label="起点时间"]').setValue('record.discharge_datetime')
    expect(wrapper.get('select[aria-label="终点时间"]').findAll('option')).toHaveLength(1)
    await wrapper.get('select[aria-label="起点时间"]').setValue('record.admission_datetime')
    expect(wrapper.get('select[aria-label="终点时间"]').findAll('option')
      .map((item) => (item.element as HTMLOptionElement).value)).toContain('document.discharge_record.latest')
  })
})
