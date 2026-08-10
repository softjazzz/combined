import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  requestFrontpageDraft: vi.fn(),
  persistBatchFrontpageDraft: vi.fn(),
  createBatchSummaryNotification: vi.fn(),
  createSichuanWorkspaceBatchJob: vi.fn(),
  messageLoading: vi.fn(),
  messageSuccess: vi.fn(),
  messageInfo: vi.fn(),
  messageError: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    loading: mocks.messageLoading,
    success: mocks.messageSuccess,
    info: mocks.messageInfo,
    warning: vi.fn(),
    error: mocks.messageError,
  },
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  createSichuanWorkspaceBatchJob: mocks.createSichuanWorkspaceBatchJob,
}))

vi.mock('@/views/workstation-v4/workstationActions', () => ({
  requestFrontpageDraft: mocks.requestFrontpageDraft,
  persistBatchFrontpageDraft: mocks.persistBatchFrontpageDraft,
  requestCodingQc: vi.fn(),
  requestFrontpageQc: vi.fn(),
  requestSettlementQc: vi.fn(),
  createBatchSummaryNotification: mocks.createBatchSummaryNotification,
}))

import { runBatchExtract, runRecordPoolQc } from '@/views/workstation-v4/workstationBatchController'
import type { PatientRecord } from '@/views/workstation-v4/types'

function record(
  recordKey: string,
  visitId: string,
  identity: { instituteId?: string; patientId?: string } = {},
): PatientRecord {
  return {
    id: visitId,
    recordKey,
    visitId,
    instituteId: identity.instituteId,
    patientId: identity.patientId,
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
    mocks.createSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { id: 'job-1', status: 'queued', idempotency_reused: false },
    })
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

  it('fails closed when distinct triple record keys resolve to the same real visit ID', async () => {
    const firstKey = '["H-1","P-1","V-100"]'
    const secondKey = '["H-2","P-2","V-100"]'
    const findBatchRecordByKey = vi.fn((key: string) =>
      key === firstKey
        ? record(firstKey, 'V-100')
        : key === secondKey
          ? record(secondKey, 'V-100')
          : null,
    )
    const setBatchRuntimeStatus = vi.fn()
    const setSingleBatchRuntimeStatus = vi.fn()
    const setSelectedWorkbenchKeys = vi.fn()

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
      setSelectedWorkbenchKeys,
      fetchAssistNotifications: vi.fn().mockResolvedValue(undefined),
      refreshActiveWorklist: vi.fn().mockResolvedValue(undefined),
      refreshData: vi.fn().mockResolvedValue(undefined),
      refreshSelectedSnapshots: vi.fn().mockResolvedValue(undefined),
    })

    expect(mocks.requestFrontpageDraft).not.toHaveBeenCalled()
    expect(setBatchRuntimeStatus).not.toHaveBeenCalled()
    expect(setSingleBatchRuntimeStatus).not.toHaveBeenCalled()
    expect(setSelectedWorkbenchKeys).toHaveBeenCalledWith([firstKey, secondKey])
    expect(mocks.messageError).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining('无法确认') }),
    )
  })
})

describe('runRecordPoolQc', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { id: 'job-1', status: 'queued', idempotency_reused: false },
    })
  })

  function createParams(
    records: Record<string, PatientRecord | null>,
    keys = Object.keys(records),
  ) {
    return {
      keys,
      getBatchExtracting: () => false,
      setBatchExtracting: vi.fn(),
      findBatchRecordByKey: vi.fn((key: string) => records[key] || null),
      setSelectedWorkbenchKeys: vi.fn(),
    }
  }

  it('creates a single-record LX0609 task with only the complete triple record ref', async () => {
    const key = '["H-1","P-1","V-1"]'
    const params = createParams({
      [key]: record(key, 'V-1', { instituteId: 'H-1', patientId: 'P-1' }),
    })

    await runRecordPoolQc(params)

    expect(mocks.createSichuanWorkspaceBatchJob).toHaveBeenCalledWith({
      rule_set_key: 'luxian_0609_qc_v1',
      scope: 'all',
      date_field: 'admission',
      record_refs: [{ institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1' }],
    })
    expect(mocks.createSichuanWorkspaceBatchJob.mock.calls[0]?.[0]).not.toHaveProperty('record_ids')
    expect(params.setSelectedWorkbenchKeys).toHaveBeenCalledWith([])
    expect(mocks.messageSuccess).toHaveBeenCalledWith(
      expect.objectContaining({ content: '质控任务已创建，正在执行质控' }),
    )
  })

  it('keeps every selected triple when creating a multi-record task', async () => {
    const firstKey = '["H-1","P-1","V-1"]'
    const secondKey = '["H-2","P-2","V-2"]'
    const params = createParams({
      [firstKey]: record(firstKey, 'V-1', { instituteId: 'H-1', patientId: 'P-1' }),
      [secondKey]: record(secondKey, 'V-2', { instituteId: 'H-2', patientId: 'P-2' }),
    })

    await runRecordPoolQc(params)

    expect(mocks.createSichuanWorkspaceBatchJob).toHaveBeenCalledWith(
      expect.objectContaining({
        record_refs: [
          { institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1' },
          { institute_id: 'H-2', patient_id: 'P-2', visit_id: 'V-2' },
        ],
      }),
    )
  })

  it.each([
    {
      name: 'unknown selected key',
      records: { '["H-1","P-1","V-1"]': null },
      message: '身份已失效',
    },
    {
      name: 'missing triple coordinate',
      records: {
        '["H-1","P-1","V-1"]': record('["H-1","P-1","V-1"]', 'V-1', {
          instituteId: 'H-1',
        }),
      },
      message: '缺少完整病例标识',
    },
  ])('fails closed for $name and preserves the selection', async ({ records, message }) => {
    const keys = Object.keys(records)
    const params = createParams(records, keys)

    await runRecordPoolQc(params)

    expect(mocks.createSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
    expect(params.setBatchExtracting).not.toHaveBeenCalled()
    expect(params.setSelectedWorkbenchKeys).toHaveBeenCalledWith(keys)
    expect(mocks.messageError).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining(message) }),
    )
  })

  it('fails closed when distinct row keys resolve to the same triple identity', async () => {
    const firstKey = 'row-key-1'
    const secondKey = 'row-key-2'
    const first = record(firstKey, 'V-1', { instituteId: 'H-1', patientId: 'P-1' })
    const second = record(secondKey, 'V-1', { instituteId: 'H-1', patientId: 'P-1' })
    const params = createParams({ [firstKey]: first, [secondKey]: second })

    await runRecordPoolQc(params)

    expect(mocks.createSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
    expect(params.setBatchExtracting).not.toHaveBeenCalled()
    expect(params.setSelectedWorkbenchKeys).toHaveBeenCalledWith([firstKey, secondKey])
    expect(mocks.messageError).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining('身份冲突') }),
    )
  })

  it('preserves the selection and surfaces the safe service message when task creation fails', async () => {
    const key = '["H-1","P-1","V-1"]'
    const params = createParams({
      [key]: record(key, 'V-1', { instituteId: 'H-1', patientId: 'P-1' }),
    })
    mocks.createSichuanWorkspaceBatchJob.mockResolvedValue({
      success: false,
      message: '当前服务繁忙，请稍后重试',
    })

    await runRecordPoolQc(params)

    expect(params.setSelectedWorkbenchKeys).toHaveBeenCalledWith([key])
    expect(mocks.messageError).toHaveBeenCalledWith(
      expect.objectContaining({ content: '当前服务繁忙，请稍后重试' }),
    )
    expect(params.setBatchExtracting).toHaveBeenNthCalledWith(1, true)
    expect(params.setBatchExtracting).toHaveBeenLastCalledWith(false)
  })

  it('reports that an idempotently reused task continues executing', async () => {
    const key = '["H-1","P-1","V-1"]'
    const params = createParams({
      [key]: record(key, 'V-1', { instituteId: 'H-1', patientId: 'P-1' }),
    })
    mocks.createSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { id: 'job-1', status: 'running', idempotency_reused: true },
    })

    await runRecordPoolQc(params)

    expect(params.setSelectedWorkbenchKeys).toHaveBeenCalledWith([])
    expect(mocks.messageInfo).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining('继续执行质控') }),
    )
  })

  it('does not submit again while a record-pool QC task is being created', async () => {
    const key = '["H-1","P-1","V-1"]'
    const params = {
      ...createParams({
        [key]: record(key, 'V-1', { instituteId: 'H-1', patientId: 'P-1' }),
      }),
      getBatchExtracting: () => true,
    }

    await runRecordPoolQc(params)

    expect(mocks.createSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
    expect(params.setBatchExtracting).not.toHaveBeenCalled()
    expect(params.setSelectedWorkbenchKeys).not.toHaveBeenCalled()
  })
})
