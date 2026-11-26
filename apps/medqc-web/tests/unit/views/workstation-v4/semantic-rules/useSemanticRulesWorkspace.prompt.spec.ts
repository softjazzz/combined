import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'

const mocks = vi.hoisted(() => ({
  fetchRulePrompt: vi.fn(),
  saveRulePrompt: vi.fn(),
  fetchSemanticRulesFromBackend: vi.fn(),
  fetchSichuanRuleSetsFromBackend: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn(),
  messageInfo: vi.fn(),
}))

vi.mock('@/data/qcRuleCases', () => ({
  qcRuleCaseMap: {},
  buildCaseText: vi.fn(() => ''),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: mocks.messageSuccess,
    error: mocks.messageError,
    warning: mocks.messageWarning,
    info: mocks.messageInfo,
  },
}))

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({ confirmedResultsOnly: ref(false) }),
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    getCurrentUser: vi.fn().mockResolvedValue({
      success: true,
      data: { id: 'super-1', roles: ['super_admin'], is_demo_account: false },
    }),
  },
}))

vi.mock('@/views/workstation-v4/semantic-rules/composables/useSichuanBatchJobs', () => ({
  useSichuanBatchJobs: () => ({
    batchJobs: ref([]),
    batchJobsLoading: ref(false),
    batchJobsError: ref(''),
    batchResultDrawerOpen: ref(false),
    batchJobDetail: ref(null),
    batchJobDetailLoading: ref(false),
    batchJobDebugSnapshot: ref(null),
    batchJobDebugLoading: ref(false),
    cancelBatchJobLoading: ref(false),
    loadBatchJobs: vi.fn(),
    openBatchJobDetail: vi.fn(),
    closeBatchJobDetail: vi.fn(),
    fetchBatchJobDebugSnapshot: vi.fn(),
    exportBatchJobReport: vi.fn(),
    cancelBatchJob: vi.fn(),
    resetBatchJobs: vi.fn(),
    getBatchJobStatusTagClass: vi.fn(),
    getBatchJobStatusText: vi.fn(),
  }),
}))

vi.mock('@/views/rules/composables/useCustomQcBatchLaunchFilters', () => ({
  useCustomQcBatchLaunchFilters: () => ({
    department: ref(''),
    recordStatus: ref(''),
    patientId: ref(''),
    visitId: ref(''),
    departments: ref([]),
    resetFilters: vi.fn(),
  }),
}))

vi.mock('@/views/workstation-v4/semantic-rules/service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/views/workstation-v4/semantic-rules/service')>()
  return {
    ...actual,
    fetchRulePrompt: mocks.fetchRulePrompt,
    saveRulePrompt: mocks.saveRulePrompt,
    fetchSemanticRulesFromBackend: mocks.fetchSemanticRulesFromBackend,
    fetchSichuanRuleSetsFromBackend: mocks.fetchSichuanRuleSetsFromBackend,
  }
})

import { useSemanticRulesWorkspace } from '@/views/workstation-v4/semantic-rules/composables/useSemanticRulesWorkspace'
import type { SemanticRuleItem } from '@/views/workstation-v4/semantic-rules/types'

const sampleRule: SemanticRuleItem = {
  rule_id: 'SC-010',
  rule_code: 'SC-010',
  name: '主诉与现病史一致性',
  description: '检查主诉与现病史一致',
  category: 'admission_record',
  complexity: 'high',
  defect_level: 'major',
  score_deduction: 5,
  applicable_documents: ['admission_record'],
  medical_domain: 'general',
  requires_rag: false,
  requires_cot: false,
  custom_prompt: '旧的自定义提示词',
}

describe('useSemanticRulesWorkspace savePromptChanges', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchSichuanRuleSetsFromBackend.mockResolvedValue([])
    mocks.fetchSemanticRulesFromBackend.mockResolvedValue({
      rules: [{ ...sampleRule }],
      stats: {
        total_rules: 1,
        rule_categories: ['admission_record'],
        complexity_distribution: { high: 1 },
        defect_level_distribution: { major: 1 },
      },
    })
    mocks.saveRulePrompt.mockResolvedValue(undefined)
  })

  it('保存空提示词恢复默认时清空 custom_prompt 并重新拉取默认提示词而非置空编辑器', async () => {
    mocks.fetchRulePrompt
      .mockResolvedValueOnce({
        prompt: '旧的自定义提示词',
        isDefaultPrompt: false,
      })
      .mockResolvedValueOnce({
        prompt: '系统默认 SC-010 提示词模板',
        isDefaultPrompt: true,
      })

    let workspace!: ReturnType<typeof useSemanticRulesWorkspace>
    const wrapper = mount(
      defineComponent({
        setup() {
          workspace = useSemanticRulesWorkspace()
          return () => h('div')
        },
      }),
    )
    await flushPromises()

    await workspace.openRuleDetail(workspace.filteredRules.value[0])
    await flushPromises()
    expect(workspace.currentPrompt.value).toBe('旧的自定义提示词')
    expect(workspace.selectedRule.value?.custom_prompt).toBe('旧的自定义提示词')

    workspace.startEditPrompt()
    workspace.editingPrompt.value = '   '
    await workspace.savePromptChanges()
    await flushPromises()

    expect(mocks.saveRulePrompt).toHaveBeenCalledWith('SC-010', '', { skipErrorToast: true })
    expect(mocks.fetchRulePrompt).toHaveBeenCalledTimes(2)
    expect(workspace.selectedRule.value?.custom_prompt).toBeUndefined()
    expect(workspace.currentPrompt.value).toBe('系统默认 SC-010 提示词模板')
    expect(workspace.editingPrompt.value).toBe('系统默认 SC-010 提示词模板')
    expect(workspace.isDefaultPrompt.value).toBe(true)
    expect(workspace.isEditingPrompt.value).toBe(false)
    expect(mocks.messageSuccess).toHaveBeenCalledWith('已恢复默认提示词')

    wrapper.unmount()
  })
})
