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

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

function mountDrawer() {
  return mount(QCReviewDrawer, {
    props: {
      visible: false,
      record: {
        id: 'record-pk',
        record_id: 'record-business-id',
        patient_name: '测试患者',
        status: 'passed',
        score: 100,
        defect_count: 2,
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
}

describe('QCReviewDrawer 质控关联隔离', () => {
  beforeEach(() => {
    mocks.getDefectList.mockReset()
    mocks.getRecordDetail.mockReset()
  })

  it.each([
    { name: '关联不可用', data: { qc_data_status: 'unavailable_identity_contract', defects: [] } },
    { name: '缺少关联状态', data: { defects: [] } },
  ])('$name 时不请求单键缺陷或伪称无缺陷', async ({ data }) => {
    mocks.getRecordDetail.mockResolvedValue({ success: true, data: { ...data, documents: {} } })
    const wrapper = mountDrawer()
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(mocks.getDefectList).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('质控关联待核实')
    expect(wrapper.text()).not.toContain('暂无质控问题')
    expect(wrapper.find('.review-summary__status').text()).toBe('质控关联待核实')
    expect(wrapper.findAll('.review-metric-card__value')[2]?.text()).toBe('-')
    expect(wrapper.findAll('.review-metric-card__value')[3]?.text()).toBe('-')
    expect(wrapper.find('.review-issues__reload').exists()).toBe(false)
    expect(wrapper.findAll('.review-issue-card')).toHaveLength(0)
    wrapper.unmount()
  })

  it('详情失败时仍不请求单键缺陷', async () => {
    mocks.getRecordDetail.mockRejectedValue(new Error('service unavailable'))
    const wrapper = mountDrawer()
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(mocks.getDefectList).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('质控关联待核实')
    expect(wrapper.text()).not.toContain('暂无质控问题')
    wrapper.unmount()
  })

  it('切换病历后丢弃旧详情响应', async () => {
    const first = deferred<unknown>()
    mocks.getRecordDetail
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce({
        success: true,
        data: { qc_data_status: 'unavailable_identity_contract', documents: { raw_documents: [] } },
      })
    const wrapper = mountDrawer()
    await wrapper.setProps({ visible: true })
    await wrapper.setProps({ record: { id: 'record-pk-2', record_id: 'record-business-id-2' } })
    await flushPromises()

    first.resolve({
      success: true,
      data: {
        qc_data_status: 'unavailable_identity_contract',
        documents: {
          raw_documents: [{ doc_type: 'admission_record', document_title: '旧病历文书', content: '旧内容' }],
        },
      },
    })
    await flushPromises()

    expect(mocks.getRecordDetail).toHaveBeenNthCalledWith(2, 'record-business-id-2')
    expect(mocks.getDefectList).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('旧病历文书')
    expect(wrapper.text()).toContain('质控关联待核实')
    wrapper.unmount()
  })
})
