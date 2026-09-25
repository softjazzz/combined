import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

import WorkstationV4AssistView from '@/views/workstation-v2/components/WorkstationV4AssistView.vue'
import ContentQCTab from '@/views/workstation-v2/components/ContentQCTab.vue'
import QCResultTab from '@/views/workstation-v2/components/QCResultTab.vue'
import type { PatientRecord } from '@/views/workstation-v2/types'

/**
 * shallowMount 默认把分析面板换成不渲染具名插槽的空壳，
 * 这里显式渲染 `content` / `qc` 插槽，才能检查子组件真实收到的 prop。
 */
const PanelStub = defineComponent({
  name: 'WorkstationAssistPanel',
  setup(_props, { slots }) {
    return () =>
      h('div', { class: 'assist-panel-stub' }, [
        slots.content?.(),
        slots.qc?.({ activeSubTab: 'form' }),
      ])
  },
})

/** 只补与本接线相关的字段，其余字段给出合法默认值，避免类型断言。 */
function patientRecord(overrides: Partial<PatientRecord> = {}): PatientRecord {
  return {
    id: 'visit-1',
    patientId: 'P-1',
    bedNo: '01',
    name: '测试患者',
    sex: '男',
    age: 60,
    insurance: '医保',
    department: '心内科',
    admissionDate: '2026-09-01',
    dischargeDate: '2026-09-10',
    days: 9,
    diagnosis: '主诊断',
    diagnosisCode: 'I10',
    doctor: '医师',
    status: 'pending',
    ...overrides,
  }
}

function baseProps(record: PatientRecord | null, selectedId = 'visit-1') {
  return {
    visible: true,
    assistTab: 'form' as const,
    selectedRecord: record,
    assistPatientInfo: null,
    contentQCCount: 0,
    assistBadgeCount: 0,
    frontpageDraft: null,
    frontpageGenerating: false,
    qcRefreshSeed: 0,
    selectedId,
    documentsList: [],
    notificationUnreadCount: 0,
    profileAnalyzed: false,
    profileAnalyzing: false,
    aiProfileModalVisible: false,
    combinedMedicalText: '',
    drgResult: null,
    drgLoading: false,
    drgDetailModalVisible: false,
    overviewViewMode: 'overview' as const,
    overviewDepartmentFilter: 'all',
    overviewTypeFilter: 'all',
    overviewSeverityFilter: 'all',
    notificationReadFilter: 'all' as const,
    overviewDepartments: [],
    overviewTypes: [],
    overviewSeverities: [],
    notificationLoading: false,
    overviewLoading: false,
    filteredNotificationOverviewItems: [],
    filteredAssistNotifications: [],
    formatRelativeTime: () => '',
    suggestionDrawerVisible: false,
    suggestions: [],
    suggestionsLoading: false,
    getSuggestionTitle: () => '',
    suggestionSeverityTag: () => 'blue',
    icdDrawerVisible: false,
    icdApplyTarget: '',
    icdTargetOptions: [],
    isOtherTarget: false,
    icdApplyIndex: 1,
    icdApplyLabel: '',
  }
}

function mountAssist(record: PatientRecord | null, selectedId = 'visit-1') {
  return shallowMount(WorkstationV4AssistView, {
    props: baseProps(record, selectedId),
    global: {
      stubs: {
        WorkstationAssistPanel: PanelStub,
        'a-drawer': true,
        'a-modal': true,
        'a-button': true,
        'a-segmented': true,
        'a-select': true,
        'a-input-number': true,
        'a-spin': true,
        'a-empty': true,
        'a-tag': true,
      },
    },
  })
}

describe('WorkstationV4AssistView 机构号接线', () => {
  it('把 selectedRecord.instituteId 透传给首页质控 QCResultTab', () => {
    const wrapper = mountAssist(patientRecord({ instituteId: 'hospital-1' }))

    const qcTab = wrapper.findComponent(QCResultTab)
    expect(qcTab.exists()).toBe(true)
    expect(qcTab.props('instituteId')).toBe('hospital-1')
  })

  it('内涵质控与首页质控拿到同一个机构号', () => {
    const wrapper = mountAssist(patientRecord({ instituteId: 'hospital-1' }))

    expect(wrapper.findComponent(ContentQCTab).props('instituteId')).toBe('hospital-1')
    expect(wrapper.findComponent(QCResultTab).props('instituteId')).toBe('hospital-1')
  })

  it('记录缺机构号时透传 undefined，不退化成空串或其它默认值', () => {
    const wrapper = mountAssist(patientRecord())

    expect(wrapper.findComponent(QCResultTab).props('instituteId')).toBeUndefined()
  })

  it('记录 id 与真实 visitId 不同时以 visitId 读取正式首页', () => {
    const wrapper = mountAssist(
      patientRecord({ id: 'row-key', visitId: 'visit-real', instituteId: 'hospital-1' }),
      'row-key',
    )

    expect(wrapper.findComponent(QCResultTab).props('visitId')).toBe('visit-real')
    expect(wrapper.findComponent(QCResultTab).props('instituteId')).toBe('hospital-1')
  })
})
