import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it } from 'vitest'

import OutpatientEmergencyDetailDrawer from '@/views/dashboard/records/OutpatientEmergencyDetailDrawer.vue'

const DrawerStub = defineComponent({
  props: { open: Boolean },
  setup(props, { slots }) {
    return () => props.open ? h('div', [slots.title?.(), slots.default?.()]) : null
  },
})

const SlotStub = defineComponent({
  setup(_, { slots }) {
    return () => h('div', slots.default?.())
  },
})

const ButtonStub = defineComponent({
  emits: ['click'],
  setup(_, { emit, slots }) {
    return () => h('button', { onClick: () => emit('click') }, slots.default?.())
  },
})

const EmptyStub = defineComponent({
  props: { description: { type: String, default: '' } },
  setup(props) {
    return () => h('div', props.description)
  },
})

function mountDrawer(detailData: Record<string, unknown> | null, error = '') {
  return mount(OutpatientEmergencyDetailDrawer, {
    props: {
      visible: true,
      loading: false,
      record: {
        id: 'row-1',
        task_id: 'task-1',
        record_id: 'MR-1',
        patient_name: '患者甲',
        status: 'pending',
        defect_count: 0,
        created_at: '2026-09-24T00:00:00Z',
      },
      detailData,
      error,
    },
    global: {
      stubs: {
        'a-drawer': DrawerStub,
        'a-button': ButtonStub,
        'a-tag': SlotStub,
        'a-skeleton': SlotStub,
        'a-tabs': SlotStub,
        'a-tab-pane': SlotStub,
        'a-timeline': SlotStub,
        'a-timeline-item': SlotStub,
        'a-list': SlotStub,
        'a-list-item': SlotStub,
        'a-empty': EmptyStub,
      },
    },
  })
}

describe('OutpatientEmergencyDetailDrawer 详情读取状态', () => {
  it('错误时显示病历上下文和重试，不渲染空缺陷或文书', async () => {
    const wrapper = mountDrawer(null, '详情服务暂不可用')
    expect(wrapper.text()).toContain('MR-1')
    expect(wrapper.get('[data-testid="outpatient-detail-error"]').text()).toContain('详情服务暂不可用')
    expect(wrapper.text()).not.toContain('暂无缺陷记录')
    expect(wrapper.text()).not.toContain('暂无内容')
    expect(wrapper.text()).toContain('质控状态不可用')
    expect(wrapper.text()).not.toContain('pending')

    await wrapper.get('[data-testid="retry-outpatient-detail"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('真实成功空集保留空态', () => {
    const wrapper = mountDrawer({ defects: [], documents: { raw_documents: [] } })
    expect(wrapper.text()).toContain('暂无缺陷记录')
    expect(wrapper.text()).toContain('暂无病历文书')
    expect(wrapper.find('[data-testid="outpatient-detail-error"]').exists()).toBe(false)
  })

  it('质控关联不可确认时仅展示已取得文书，不渲染缺陷与整改操作', () => {
    const wrapper = mountDrawer({
      qc_data_status: 'unavailable_identity_contract',
      defects: [],
      documents: {
        admissionNote: '',
        dischargeNote: '',
        progressNote: '',
        surgeryNote: '',
        raw_documents: [{ id: 'doc-1', document_title: '门诊病历', content: '已同步的病历文书' }],
      },
    })
    expect(wrapper.get('[data-testid="outpatient-qc-link-unavailable"]').text()).toContain('质控关联待核实')
    expect(wrapper.text()).toContain('已同步的病历文书')
    expect(wrapper.text()).not.toContain('暂无缺陷记录')
    expect(wrapper.text()).not.toContain('催办')
    expect(wrapper.text()).not.toContain('pending')
  })

  it('门诊原始文书可展开查看完整正文，不依赖四类住院文书映射', async () => {
    const content = `门诊病历正文${'临床内容'.repeat(90)}`
    const wrapper = mountDrawer({
      defects: [],
      documents: {
        admissionNote: '',
        dischargeNote: '',
        progressNote: '',
        surgeryNote: '',
        raw_documents: [{ id: 'doc-2', document_type: '门诊病历', content }],
      },
    })
    const document = wrapper.get('[data-testid="outpatient-raw-document"]')
    expect(document.text()).toContain('门诊病历')
    expect(document.text()).toContain(content)
    await document.get('summary').trigger('click')
    expect((document.element as HTMLDetailsElement).open).toBe(true)
    expect(wrapper.text()).not.toContain('暂无病历文书')
  })
})
