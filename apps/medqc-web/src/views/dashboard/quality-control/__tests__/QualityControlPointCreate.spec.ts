import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import QualityControlPointCreate from '@/views/dashboard/quality-control/QualityControlPointCreate.vue'

const slot = { template: '<div><slot /></div>' }

describe('QualityControlPointCreate', () => {
  it('提示需执行器配合且保存按钮禁用', () => {
    const wrapper = mount(QualityControlPointCreate, {
      global: {
        stubs: {
          'router-link': slot, 'a-breadcrumb': slot, 'a-breadcrumb-item': slot,
          'a-steps': slot, 'a-step': slot, 'a-select': slot, 'a-select-option': slot,
          'a-input': slot, 'a-textarea': slot, 'a-form-item': slot,
          'a-form': { props: ['disabled'], template: '<form :data-disabled="String(disabled)"><slot /></form>' },
          'a-tooltip': slot,
          'a-alert': { props: ['message'], template: '<div class="alert">{{ message }}</div>' },
          'a-button': { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
        },
      },
    })
    expect(wrapper.find('.alert').text()).toBe('新建质控点需先完成执行器实现与规则主表登记，当前不可在界面创建')
    const save = wrapper.find('button')
    expect(save.text()).toBe('保存并下一步')
    expect(save.attributes('disabled')).toBeDefined()
    expect(wrapper.find('form').attributes('data-disabled')).not.toBe('false')
  })
})
