import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  requestFrontpageDraft: vi.fn(),
  persistBatchFrontpageDraft: vi.fn(),
  createBatchSummaryNotification: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    loading: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@/views/workstation-v4/workstationActions', () => ({
  requestFrontpageDraft: mocks.requestFrontpageDraft,
  persistBatchFrontpageDraft: mocks.persistBatchFrontpageDraft,
  requestCodingQc: vi.fn(),
  requestFrontpageQc: vi.fn(),
  requestSettlementQc: vi.fn(),
  createBatchSummaryNotification: mocks.createBatchSummaryNotification,
}))

import { runBatchExtract } from '@/views/workstation-v4/workstationBatchController'
import type { PatientRecord } from '@/views/workstation-v4/types'

function record(recordKey: string, visitId: string): PatientRecord {
  return {
    id: visitId,
    recordKey,
    visitId,
    bedNo: '',
    name: '患者',
    sex: '未知',
    age: 0,
    insurance: '',
    department: '内科',
    admissionDate: '',
    dischargeDate: '',
    days: 0,
    diagnosis: '',
    diagnosisCode: '',
    doctor: '',
    status: 'pending',
  }
}

describe('runBatchExtract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.requestFrontpageDraft.mockResolvedValue({ draft: {}, highRiskCount: 0 })
    mocks.persistBatchFrontpageDraft.mockResolvedValue(undefined)
    mocks.createBatchSummaryNotification.mockResolvedValue(undefined)
  })

  it('resolves selected triple record keys before sending only real visit IDs to stage actions', async () => {
    const firstKey = '["H-1","P-1","V-100"]'
    const secondKey = '["H-2","P-2","V-100"]'
    const first = record(firstKey, 'V-100-A')
    const second = record(secondKey, 'V-100-B')
    const findBatchRecordByKey = vi.fn((key: string) =>
      key === firstKey ? first : key === secondKey ? second : null,
    )
    const setBatchRuntimeStatus = vi.fn()
    const setSingleBatchRuntimeStatus = vi.fn()

    await runBatchExtract({
      keys: [firstKey, secondKey],
      currentStageFilter: 'frontpage_generate',
      isStageQueueMode: true,
      isAggregatedStageMode: true,
      getBatchExtracting: () => false,
      setBatchExtracting: vi.fn(),
      findBatchRecordByKey,
      setBatchRuntimeStatus,
      setSingleBatchRuntimeStatus,
      setSelectedWorkbenchKeys: vi.fn(),
      fetchAssistNotifications: vi.fn().mockResolvedValue(undefined),
      refreshActiveWorklist: vi.fn().mockResolvedValue(undefined),
      refreshData: vi.fn().mockResolvedValue(undefined),
      refreshSelectedSnapshots: vi.fn().mockResolvedValue(undefined),
    })

    expect(findBatchRecordByKey).toHaveBeenCalledWith(firstKey)
    expect(findBatchRecordByKey).toHaveBeenCalledWith(secondKey)
    expect(setBatchRuntimeStatus).toHaveBeenCalledWith(
      'frontpage_generate',
      ['V-100-A', 'V-100-B'],
      'running',
    )
    expect(mocks.requestFrontpageDraft).toHaveBeenNthCalledWith(1, 'V-100-A')
    expect(mocks.requestFrontpageDraft).toHaveBeenNthCalledWith(2, 'V-100-B')
    expect(setSingleBatchRuntimeStatus).toHaveBeenCalledWith(
      'frontpage_generate',
      'V-100-A',
      'submitted',
    )
    expect(setSingleBatchRuntimeStatus).toHaveBeenCalledWith(
      'frontpage_generate',
      'V-100-B',
      'submitted',
    )
  })
})
