import { defineComponent } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import WorkstationV4AssistView from '@/views/workstation-v4/components/WorkstationV4AssistView.vue'

// 面板外壳只负责渲染 chat 插槽，便于单独验证“对话”页签的上下文与跨页签请求。
const PanelStub = defineComponent({
  name: 'WorkstationAssistPanel',
  template: '<div><slot name="chat" :active="true" /></div>',
})
const ChatStub = defineComponent({
  name: 'BusinessAgentDrawer',
  props: { open: Boolean, embedded: Boolean, userContext: Object, panels: Array },
  emits: ['open-panel', 'update:open'],
  template: '<div data-testid="chat-stub" />',
})

function mountView() {
  return shallowMount(WorkstationV4AssistView, {
    props: {
      visible: true,
      assistTab: 'chat',
      activeDocType: 'progress_note',
      documentsList: [],
      suggestions: [],
      icdTargetOptions: [],
      filteredAssistNotifications: [],
      filteredNotificationOverviewItems: [],
      overviewDepartments: [],
      overviewTypes: [],
      overviewSeverities: [],
      selectedRecord: {
        id: 'V',
        instituteId: 'H',
        patientId: 'P',
        visitId: 'V',
        name: '合成患者',
      } as never,
    } as never,
    global: { stubs: { WorkstationAssistPanel: PanelStub, BusinessAgentDrawer: ChatStub } },
  })
}

describe('智能助手面板的对话页签', () => {
  it('以内嵌方式沿用当前病例坐标、当前文书和画像入口声明', () => {
    const chat = mountView().findComponent(ChatStub)
    expect(chat.props('embedded')).toBe(true)
    expect(chat.props('open')).toBe(true)
    expect(chat.props('panels')).toEqual(['profile'])
    expect(chat.props('userContext')).toMatchObject({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
      patient_name: '合成患者',
      document_id: 'progress_note',
    })
  })

  it('只响应与当前病例三坐标一致的画像请求，并仅切换页签', () => {
    const wrapper = mountView()
    const chat = wrapper.findComponent(ChatStub)
    chat.vm.$emit('open-panel', {
      panel: 'profile',
      institute_id: 'H',
      patient_id: 'P2',
      visit_id: 'V',
    })
    expect(wrapper.emitted('tab-change')).toBeUndefined()
    chat.vm.$emit('open-panel', {
      panel: 'profile',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    expect(wrapper.emitted('tab-change')).toEqual([['profile']])
    expect(wrapper.emitted('open-ai-profile')).toBeUndefined()
  })
})
