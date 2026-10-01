import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TaskRecordTypeFields from '@/components/qc/TaskRecordTypeFields.vue'

describe('任务源类型显式配置', () => {
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
    wrapper.findComponent('a-checkbox-stub').vm.$emit('update:checked', true)
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
