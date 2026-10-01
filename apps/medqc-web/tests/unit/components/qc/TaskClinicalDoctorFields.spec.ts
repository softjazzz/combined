import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TaskClinicalDoctorFields from '@/components/qc/TaskClinicalDoctorFields.vue'

describe('任务临床医生筛选', () => {
  it('机构与签名分别编辑，移除最后引用恢复不限医生', () => {
    const wrapper = shallowMount(TaskClinicalDoctorFields, {
      props: {
        scene: 'running',
        modelValue: [{ institute_id: 'SYN-I', physician_name: '张医师' }],
      },
      global: {
        stubs: {
          'a-form-item': { template: '<div><slot /></div>' },
          'a-checkbox': true,
          'a-input': true,
          'a-button': true,
        },
      },
    })
    const vm = wrapper.vm as unknown as {
      update: (index: number, key: string, value: string) => void
      remove: (index: number) => void
    }
    vm.update(0, 'physician_name', '李医师')
    expect(wrapper.emitted('update:modelValue')?.[0]?.[0]).toEqual([
      { institute_id: 'SYN-I', physician_name: '李医师' },
    ])
    vm.remove(0)
    expect(wrapper.emitted('update:modelValue')?.[1]?.[0]).toBeUndefined()
  })
  it('门急诊缺少同一来源时不显示该筛选', () => {
    const wrapper = shallowMount(TaskClinicalDoctorFields, { props: { scene: 'outpatient' } })
    expect(wrapper.text()).toBe('')
  })
})
