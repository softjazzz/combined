import { defineComponent } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RecordDetailWorkspace from '@/views/workstation-v4/components/RecordDetailWorkspace.vue'

const DrawerStub = defineComponent({
  name: 'BusinessAgentDrawer',
  props: { open: Boolean, userContext: Object, panels: Array },
  emits: ['open-panel', 'update:open'],
  template: '<div data-testid="drawer-stub" />',
})

function mountWorkspace() {
  return shallowMount(RecordDetailWorkspace, {
    props: {
      selectedRecord: {
        id: 'V',
        instituteId: 'H',
        patientId: 'P',
        visitId: 'V',
        name: '合成患者',
      } as never,
      emrRenderState: 'idle',
      concatLoading: false,
      concatText: '',
      concatSections: [],
      concatTotalChars: 0,
      allConcatSectionsExpanded: false,
      documentsLoading: false,
      isSectionExpanded: () => false,
    },
    global: { stubs: { BusinessAgentDrawer: DrawerStub } },
  })
}

describe('病历详情转发助手面板请求', () => {
  it('声明画像面板并只转发当前病例三坐标一致的请求', async () => {
    const wrapper = mountWorkspace()
    const drawer = wrapper.findComponent(DrawerStub)
    expect(drawer.props('panels')).toEqual(['profile'])
    drawer.vm.$emit('open-panel', {
      panel: 'profile',
      institute_id: 'H',
      patient_id: 'P2',
      visit_id: 'V',
    })
    expect(wrapper.emitted('open-assist-panel')).toBeUndefined()
    drawer.vm.$emit('open-panel', {
      panel: 'profile',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    expect(wrapper.emitted('open-assist-panel')).toEqual([
      [{ panel: 'profile', institute_id: 'H', patient_id: 'P', visit_id: 'V' }],
    ])
  })
})
