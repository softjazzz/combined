import { mount, RouterLinkStub } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TenderAcceptanceDashboard from '@/views/workstation-v4/components/TenderAcceptanceDashboard.vue'

describe('TenderAcceptanceDashboard', () => {
  it('shows all tender clauses and readonly acceptance status', () => {
    const wrapper = mount(TenderAcceptanceDashboard, {
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
        },
      },
    })

    expect(wrapper.text()).toContain('投标功能验收看板')
    expect(wrapper.text()).toContain('3.1.1')
    expect(wrapper.text()).toContain('6.3.1')
    expect(wrapper.findAll('.clause-card')).toHaveLength(11)
    expect(wrapper.text()).toContain('只读或草稿/模拟结果')
  })
})
