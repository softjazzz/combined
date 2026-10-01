import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TaskRecordTypeFields from '@/components/qc/TaskRecordTypeFields.vue'

describe('任务源类型显式配置', () => {
  it('Select异常值不转换成码值数组，合法字符串数组正常保存', () => {
    const wrapper = shallowMount(TaskRecordTypeFields, {
      props: {
        modelValue: {
          institutes: [
            {
              institute_id: 'SYN-H',
              critical: { positive_codes: [], negative_codes: [] },
              difficult: { positive_codes: [], negative_codes: [] },
            },
          ],
        },
      },
      global: {
        stubs: {
          'a-checkbox': true,
          'a-input': true,
          'a-select': true,
          'a-button': true,
          'a-radio': true,
          'a-radio-group': true,
        },
      },
    })
    const select = wrapper.getComponent('a-select-stub')
    for (const value of ['C+', 1, ['C+', 2], [{ value: 'C+' }], null])
      select.vm.$emit('update:value', value)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    select.vm.$emit('update:value', ['C+'])
    expect(wrapper.emitted('update:modelValue')?.[0]?.[0]).toMatchObject({
      institutes: [{ critical: { positive_codes: ['C+'] } }],
    })
  })

  it('启用时不预填正负码或双阳性策略', () => {
    const wrapper = shallowMount(TaskRecordTypeFields, {
      global: {
        stubs: {
          'a-checkbox': true,
          'a-input': true,
          'a-select': true,
          'a-button': true,
          'a-radio': true,
          'a-radio-group': true,
        },
      },
    })
    wrapper.getComponent('a-checkbox-stub').vm.$emit('update:checked', true)
    expect(wrapper.emitted('update:modelValue')?.[0]?.[0]).toEqual({
      institutes: [
        {
          institute_id: '',
          critical: { positive_codes: [], negative_codes: [] },
          difficult: { positive_codes: [], negative_codes: [] },
        },
      ],
    })
  })
})
