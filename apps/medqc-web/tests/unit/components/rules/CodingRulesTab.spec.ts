import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'

describe('CodingRulesTab', () => {
  it('只接入共享编码版本管理，不保留本地新建、查看或编辑入口', () => {
    const wrapper = shallowMount(CodingRulesTab, {
      global: {
        stubs: {
          QualityControlPointManagement: {
            name: 'QualityControlPointManagement',
            props: { managementMode: String, embedded: Boolean },
            template: '<div class="shared-coding-management" />',
          },
        },
      },
    })

    const management = wrapper.findComponent({ name: 'QualityControlPointManagement' })
    expect(management.props()).toMatchObject({ managementMode: 'coding', embedded: true })
    expect(wrapper.text()).not.toMatch(/新建|查看|编辑|复制/)
  })
})
