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
    global: { stubs: {
      'a-button': { template: '<button><slot /></button>' },
      'a-spin': true,
      AsyncEMRViewer: { template: '<div data-testid="original-emr" />' },
    } },
  })
}

describe('病历详情的助手入口', () => {
  it('入口只通知宿主打开分析面板的“内涵质控”页签，自身不持有抽屉', async () => {
    const wrapper = mountWorkspace({ id: 'V', instituteId: 'H', patientId: 'P', visitId: 'V' })
    expect(wrapper.findComponent({ name: 'BusinessAgentDrawer' }).exists()).toBe(false)
    await wrapper.get('[data-testid="business-agent-record-entry"]').trigger('click')
    expect(wrapper.emitted('open-content-qc')).toHaveLength(1)
  })

  it('没有选中病例时不显示入口', () => {
    const wrapper = mountWorkspace(null)
    expect(wrapper.find('[data-testid="business-agent-record-entry"]').exists()).toBe(false)
  })

  it('东华病例无AI草稿也挂载原始文书查看器并传递三坐标', () => {
    const wrapper = mountWorkspace({
      id: 'V', instituteId: 'H', patientId: 'P', visitId: 'V', sourceId: 'independent_cdm',
    })
    const viewer = wrapper.find('[data-testid="original-emr"]')
    expect(viewer.exists()).toBe(true)
    expect(viewer.attributes()).toMatchObject({
      'visit-id': 'V', 'patient-id': 'P', 'institute-id': 'H',
    })
  })

  it('查看病历的目录加载阶段显示医院标识，并在响应后切换到文书查看器', async () => {
    const wrapper = mountWorkspace({ id: 'V', instituteId: 'H', patientId: 'P', visitId: 'V' })
    await wrapper.setProps({ documentsLoading: true })
    expect(wrapper.get('hospital-loading-stub').attributes('label')).toBe('正在读取病历文书目录')
    await wrapper.setProps({ documentsLoading: false })
    expect(wrapper.find('hospital-loading-stub').exists()).toBe(false)
    expect(wrapper.find('[data-testid="original-emr"]').exists()).toBe(true)
  })
})


it('空目录进入fallback后仍保留来源覆盖待核提示', async () => {
  const wrapper = mountWorkspace({id:'V',instituteId:'I',patientId:'P',visitId:'V'})
  await wrapper.setProps({emrRenderState:'fallback',documents:[],materialNotice:'补充来源尚未批准关联；材料选择待更新'})
  expect(wrapper.text()).toContain('补充来源尚未批准关联；材料选择待更新')
})
