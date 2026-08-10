import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createWorkspaceBatchJob: vi.fn(),
  updateWorkspaceDraft: vi.fn(),
  message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({ message: mocks.message }))

vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return {
    CopyOutlined: icon,
    DeleteOutlined: icon,
    EditOutlined: icon,
    PlayCircleOutlined: icon,
    PlusOutlined: icon,
    ReloadOutlined: icon,
    RobotOutlined: icon,
    SearchOutlined: icon,
  }
})

vi.mock('@/services/custom-rule-workspace-service', () => ({
  cancelWorkspaceBatchJob: vi.fn(),
  createWorkspaceBatchJob: mocks.createWorkspaceBatchJob,
  createWorkspaceDraft: vi.fn(),
  deleteWorkspaceDraft: vi.fn(),
  exportWorkspaceBatchJob: vi.fn(),
  generateWorkspaceDraftPrompt: vi.fn(),
  getWorkspaceBatchJob: vi.fn(),
  getWorkspaceRecordFilters: vi.fn().mockResolvedValue({
    success: true,
    data: {
      departments: [],
      doctors: [],
      date_bounds: {
        admission: { min: '', max: '' },
        discharge: { min: '', max: '' },
      },
    },
  }),
  getWorkspaceRecords: vi.fn().mockResolvedValue({
    success: true,
    data: { items: [], total: 0, page: 1, page_size: 20 },
  }),
  listWorkspaceBatchJobs: vi.fn().mockResolvedValue({
    success: true,
    data: { items: [], total: 0, page: 1, page_size: 5 },
  }),
  listWorkspaceDrafts: vi.fn().mockResolvedValue({
    success: true,
    data: {
      items: [
        {
          id: 'draft-1',
          rule_code: 'CUSTOM-001',
          name: '测试规则',
          description: '测试说明',
          source_requirement: '测试说明',
          prompt_template: '检查病历',
          document_type: 'course_record',
          severity: 'major',
          complexity: '中复杂度',
          scene: 'final',
          status: 'draft',
        },
      ],
      total: 1,
      page: 1,
      page_size: 8,
    },
  }),
  publishWorkspaceDraft: vi.fn(),
  retryWorkspaceBatchJob: vi.fn(),
  runWorkspaceSingleTest: vi.fn(),
  updateWorkspaceDraft: mocks.updateWorkspaceDraft,
}))

import CustomRuleWorkspaceView from '@/views/rules/CustomRuleWorkspaceView.vue'

type WorkspaceViewVm = {
  records: Array<Record<string, unknown>>
  selectedRecordKeys: string[]
  selectCurrentPageRecords: () => void
  runBatchJob: () => Promise<void>
}

function createRecord(recordKey: string, instituteId: string, patientId: string, visitId: string) {
  return {
    record_key: recordKey,
    institute_id: instituteId,
    patient_id: patientId,
    record_id: visitId,
    visit_id: visitId,
    patient_name: '不得进入任务载荷',
    scope: 'final',
    department: '测试科室',
    doctor: '测试医生',
    admission_date: '2026-01-01',
    discharge_date: '2026-01-02',
    status: '已出院',
    medical_text_length: 1,
  }
}

async function mountView() {
  mocks.updateWorkspaceDraft.mockResolvedValue({
    success: true,
    data: {
      id: 'draft-1',
      rule_code: 'CUSTOM-001',
      name: '测试规则',
      description: '测试说明',
      source_requirement: '测试说明',
      prompt_template: '检查病历',
      document_type: 'course_record',
      severity: 'major',
      complexity: '中复杂度',
      scene: 'final',
      status: 'draft',
    },
  })
  mocks.createWorkspaceBatchJob.mockResolvedValue({
    success: true,
    data: { id: 'job-1', status: 'queued', items: [], failed_records: [] },
  })
  const wrapper = shallowMount(CustomRuleWorkspaceView, {
    global: {
      stubs: {
        'a-alert': true,
        'a-button': true,
        'a-drawer': true,
        'a-empty': true,
        'a-form': true,
        'a-form-item': true,
        'a-input': true,
        'a-input-number': true,
        'a-popconfirm': true,
        'a-radio-button': true,
        'a-radio-group': true,
        'a-range-picker': true,
        'a-select': true,
        'a-switch': true,
        'a-table': true,
        'a-tag': true,
        'a-textarea': true,
        'a-tooltip': true,
      },
    },
  })
  await flushPromises()
  return { wrapper, vm: wrapper.vm as unknown as WorkspaceViewVm }
}

describe('CustomRuleWorkspaceView batch record refs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('跨页保留同visit不同三坐标，并只提交record_refs', async () => {
    const { vm } = await mountView()
    vm.records = [createRecord('key-a', 'HOSP-A', 'PAT-A', 'VISIT-1')]
    vm.selectCurrentPageRecords()
    vm.records = [createRecord('key-b', 'HOSP-B', 'PAT-B', 'VISIT-1')]
    vm.selectCurrentPageRecords()

    await vm.runBatchJob()

    expect(mocks.createWorkspaceBatchJob).toHaveBeenCalledOnce()
    const payload = mocks.createWorkspaceBatchJob.mock.calls[0][0]
    expect(payload.record_refs).toEqual([
      { institute_id: 'HOSP-A', patient_id: 'PAT-A', visit_id: 'VISIT-1' },
      { institute_id: 'HOSP-B', patient_id: 'PAT-B', visit_id: 'VISIT-1' },
    ])
    expect(payload).not.toHaveProperty('record_ids')
    expect(JSON.stringify(payload)).not.toContain('不得进入任务载荷')
  })

  it.each([
    {
      title: '三坐标不完整',
      records: [createRecord('key-a', '', 'PAT-A', 'VISIT-1')],
    },
    {
      title: '不同key映射同一三坐标',
      records: [
        createRecord('key-a', 'HOSP-A', 'PAT-A', 'VISIT-1'),
        createRecord('key-b', 'HOSP-A', 'PAT-A', 'VISIT-1'),
      ],
    },
  ])('$title时失败关闭、保留选择且不调用任何写接口', async ({ records }) => {
    const { vm } = await mountView()
    vm.records = records
    vm.selectCurrentPageRecords()
    const selectedBefore = [...vm.selectedRecordKeys]

    await vm.runBatchJob()

    expect(mocks.updateWorkspaceDraft).not.toHaveBeenCalled()
    expect(mocks.createWorkspaceBatchJob).not.toHaveBeenCalled()
    expect(vm.selectedRecordKeys).toEqual(selectedBefore)
    expect(mocks.message.error).toHaveBeenCalled()
  })

  it('跨页选择键丢失映射时失败关闭并保留选择', async () => {
    const { vm } = await mountView()
    vm.selectedRecordKeys = ['missing-record-key']

    await vm.runBatchJob()

    expect(mocks.updateWorkspaceDraft).not.toHaveBeenCalled()
    expect(mocks.createWorkspaceBatchJob).not.toHaveBeenCalled()
    expect(vm.selectedRecordKeys).toEqual(['missing-record-key'])
    expect(mocks.message.error).toHaveBeenCalled()
  })
})
