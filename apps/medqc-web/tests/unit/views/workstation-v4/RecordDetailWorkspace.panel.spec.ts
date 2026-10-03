import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RecordDetailWorkspace from '@/views/workstation-v4/components/RecordDetailWorkspace.vue'

function mountWorkspace(selectedRecord: unknown) {
  return shallowMount(RecordDetailWorkspace, {
    props: {
      selectedRecord: selectedRecord as never,
      emrRenderState: 'idle',
      concatLoading: false,
      concatText: '',
      concatSections: [],
      concatTotalChars: 0,
      allConcatSectionsExpanded: false,
      documentsLoading: false,
      isSectionExpanded: () => false,
    },
    global: { stubs: { 'a-button': { template: '<button><slot /></button>' } } },
  })
}

describe('病历详情的助手入口', () => {
  it('入口只通知宿主打开智能助手面板的“对话”页签，自身不再持有抽屉', async () => {
    const wrapper = mountWorkspace({ id: 'V', instituteId: 'H', patientId: 'P', visitId: 'V' })
    expect(wrapper.findComponent({ name: 'BusinessAgentDrawer' }).exists()).toBe(false)
    await wrapper.get('[data-testid="business-agent-record-entry"]').trigger('click')
    expect(wrapper.emitted('open-assist-chat')).toHaveLength(1)
  })

  it('没有选中病例时不显示入口', () => {
    const wrapper = mountWorkspace(null)
    expect(wrapper.find('[data-testid="business-agent-record-entry"]').exists()).toBe(false)
  })
})
