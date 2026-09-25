import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getDefectList: vi.fn(),
  getRecordDetail: vi.fn(),
}))

vi.mock('@/api/qcAdmin', () => ({
  getDefectList: mocks.getDefectList,
  getRecordDetail: mocks.getRecordDetail,
}))

import QCReviewDrawer from '@/components/qc/QCReviewDrawer.vue'

const SlotStub = defineComponent({
  setup(_, { slots }) {
    return () => h('div', slots.default?.())
  },
})

describe('QCReviewDrawer 旧详情来源保护', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getRecordDetail.mockResolvedValue({
      success: true,
      data: { documents: { raw_documents: [{ content: '其他患者的旧文书' }] } },
    })
  })

  it.each([
    ['未知来源', undefined],
    ['CDM 来源', 'cdm'],
    ['未认证的旧来源字段', 'legacy_medical_records'],
  ])('%s 不请求旧单键详情', async (_name, source) => {
    const wrapper = mount(QCReviewDrawer, {
      props: {
        visible: false,
        record: {
          id: 'row-key',
          record_id: 'shared-visit-id',
          source,
          patient_name: '测试患者',
        },
      },
      global: {
        stubs: {
          'a-drawer': SlotStub,
          'a-spin': SlotStub,
          'a-button': SlotStub,
          QCReviewActionBar: true,
        },
      },
    })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(mocks.getRecordDetail).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('其他患者的旧文书')
    expect(wrapper.text()).toContain('质控关联待核实')
    wrapper.unmount()
  })
})
