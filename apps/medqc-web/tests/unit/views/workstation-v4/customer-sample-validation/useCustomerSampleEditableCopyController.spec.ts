import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  formatLocalDateTimeInput,
  normalizeEditableCopyDateTime,
  useCustomerSampleEditableCopyController,
} from '@/views/workstation-v4/customer-sample-validation/useCustomerSampleEditableCopyController'
import { CUSTOMER_TEST_POOL_ID } from '@/views/workstation-v4/customer-sample-validation/recordPresentation'
import type {
  ManualSamplePool,
  ManualSamplePoolRecord,
  ManualSampleValidationMode,
} from '@/views/workstation-v4/customer-sample-validation/types'

const {
  message,
  Modal,
  loadCurrentMedicalRecord,
  createManualTestMedicalRecord,
  getEditableMedicalRecordDocuments,
  runManualSamplePool,
} = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
  Modal: {
    confirm: vi.fn(),
  },
  loadCurrentMedicalRecord: vi.fn(),
  createManualTestMedicalRecord: vi.fn(),
  getEditableMedicalRecordDocuments: vi.fn(),
  runManualSamplePool: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({ message, Modal }))
vi.mock('@/services/current-medical-record', () => ({ loadCurrentMedicalRecord }))
vi.mock('@/services/manual-case-sample-service', () => ({
  createManualTestMedicalRecord,
  getEditableMedicalRecordDocuments,
  runManualSamplePool,
}))

function buildRecord(overrides: Partial<ManualSamplePoolRecord> = {}): ManualSamplePoolRecord {
  return {
    id: 'rec-1',
    matched_institute_id: 'INST-1',
    matched_patient_id: 'PAT-1',
    matched_visit_id: 'VIS-1',
    patient_name: '张某某',
    patient_sex: '女',
    patient_age: '63岁',
    mr_no: 'MR001',
    department: '呼吸内科',
    admission_time: '2026-06-18 07:02:00',
    discharge_time: '2026-06-26 08:31:00',
    match_status: 'matched',
    sync_status: 'synced',
    bundle_status: 'ready',
    coverage_types: [],
    candidate_rule_ids: [],
    document_scope_labels: [],
    issue_count: 0,
    issue_preview: [],
    issue_preview_text: '',
    sample_item_ids: ['item-1'],
    sample_items: [],
    ...overrides,
  }
}

function createController(options?: { isLuxian0609?: boolean }) {
  const is0609 = options?.isLuxian0609 ?? true
  const testPool: ManualSamplePool = {
    id: CUSTOMER_TEST_POOL_ID,
    name: '客户自建测试病历',
    source_file: '',
    source_sheet: '',
    scene: 'customer',
    created_by: 'tester',
    total_items: 1,
    llm_intrinsic_items: 0,
    programmatic_items: 0,
    unsupported_items: 0,
    matched_items: 1,
    ambiguous_items: 0,
    unmatched_items: 0,
    ready_items: 1,
  }
  const sourcePool: ManualSamplePool = { ...testPool, id: 'pool-source', name: '真实样本池' }
  const pools = ref<ManualSamplePool[]>([sourcePool, testPool])
  const selectedPoolId = ref<string | undefined>('pool-source')
  const selectedPool = ref<ManualSamplePool | undefined>(sourcePool)
  const selectedValidationMode = ref<ManualSampleValidationMode>(
    is0609 ? 'customer' : 'formal_fast_screen_full',
  )
  const selectedRuleSetPayloadKey = computed(() =>
    is0609 ? 'luxian_0609_qc_v1' : 'sc_content_full_v1',
  )
  const isLuxian0609Mode = computed(() => is0609)
  const selectedLuxianCustomerRuleIds = ref<string[]>(['LX0609-01-01-01'])
  const loadPools = vi.fn(async () => undefined)
  const loadRecords = vi.fn(async () => undefined)
  const openBatchJob = vi.fn(async () => undefined)
  const loadLatestSyncJob = vi.fn(async () => undefined)
  const restoreCurrentQcTaskForSelectedPool = vi.fn(async () => undefined)
  const onPoolSwitched = vi.fn(async () => undefined)

  const controller = useCustomerSampleEditableCopyController({
    selectedPool,
    selectedPoolId,
    pools,
    selectedValidationMode,
    selectedRuleSetPayloadKey,
    isLuxian0609Mode,
    selectedLuxianCustomerRuleIds,
    normalizeLuxianRuleIds: (ids) => [...ids],
    loadPools,
    loadRecords,
    openBatchJob,
    loadLatestSyncJob,
    restoreCurrentQcTaskForSelectedPool,
    onPoolSwitched,
  })

  return {
    controller,
    selectedPoolId,
    loadPools,
    loadRecords,
    openBatchJob,
    loadLatestSyncJob,
    restoreCurrentQcTaskForSelectedPool,
    onPoolSwitched,
  }
}

describe('useCustomerSampleEditableCopyController (P1-9 & P1-10)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getEditableMedicalRecordDocuments.mockResolvedValue({
      success: true,
      data: {
        documents: [
          {
            key: 'doc-1',
            document_type: 'admission_record',
            title: '入院记录',
            record_time: '2026-06-18 09:00:00',
            content: '患者因咳嗽咳痰入院。',
            enabled: true,
          },
        ],
      },
    })
    createManualTestMedicalRecord.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'CUSTOMER_TEST_1',
        mr_no: 'MR_TEST_1',
        patient_id: 'PAT_TEST_1',
        inserted_tables: {},
        bundle_status: 'ready',
        item: {
          id: 'sample-item-new',
          matched_institute_id: 'INST-1',
          matched_patient_id: 'PAT_TEST_1',
          matched_visit_id: 'CUSTOMER_TEST_1',
        },
      },
    })
    runManualSamplePool.mockResolvedValue({
      success: true,
      data: { job_id: 'job-new-1' },
    })
  })

  it('读取真实 patient_sex 和 patient_age，缺失时回退为默认值，并保留北京时间 +08:00', async () => {
    expect(normalizeEditableCopyDateTime('2026-06-18 07:02:00')).toBe('2026-06-18T07:02:00+08:00')
    expect(normalizeEditableCopyDateTime('2026-06-18T07:02')).toBe('2026-06-18T07:02:00+08:00')
    expect(normalizeEditableCopyDateTime('2026-06-17T23:02:00Z')).toBe('2026-06-18T07:02:00+08:00')
    expect(normalizeEditableCopyDateTime('invalid-date')).toBeUndefined()
    expect(normalizeEditableCopyDateTime('2026-02-30 10:00')).toBeUndefined()

    const { controller } = createController()
    await controller.openEditableCopyDrawer(buildRecord({ patient_sex: '女', patient_age: '63岁' }))
    expect(controller.editableCopyDraft.value?.sex).toBe('女')
    expect(controller.editableCopyDraft.value?.age).toBe(63)

    // 新增文书使用本地 YYYY-MM-DDTHH:mm
    const expectedNow = formatLocalDateTimeInput(new Date())
    controller.addEditableCopyDocument('daily_course_record')
    const added = controller.editableCopyDraft.value?.documents.at(-1)
    expect(added?.record_time).toBe(expectedNow)

    // 缺失或非法性别/年龄回退默认值，但 0 岁有效
    await controller.openEditableCopyDrawer(
      buildRecord({ patient_sex: '', patient_age: undefined }),
    )
    expect(controller.editableCopyDraft.value?.sex).toBe('未说明')
    expect(controller.editableCopyDraft.value?.age).toBe(50)

    await controller.openEditableCopyDrawer(buildRecord({ patient_sex: '男', patient_age: 0 }))
    expect(controller.editableCopyDraft.value?.sex).toBe('男')
    expect(controller.editableCopyDraft.value?.age).toBe(0)
  })

  it('校验 admissionTime、dischargeTime、record_time 格式，不再静默替换为当前时间', async () => {
    const { controller } = createController()
    await controller.openEditableCopyDrawer(buildRecord())

    controller.editableCopyDraft.value!.admissionTime = 'not-a-date'
    await controller.saveEditableCopy({ runAfterSave: false })
    expect(createManualTestMedicalRecord).not.toHaveBeenCalled()
    expect(message.warning).toHaveBeenCalledWith('入院时间格式无效，请检查后重试')

    controller.editableCopyDraft.value!.admissionTime = '2026-06-18 07:02:00'
    controller.editableCopyDraft.value!.dischargeTime = '2026-13-40 99:00'
    await controller.saveEditableCopy({ runAfterSave: false })
    expect(createManualTestMedicalRecord).not.toHaveBeenCalled()
    expect(message.warning).toHaveBeenCalledWith('出院时间格式无效，请检查后重试')

    controller.editableCopyDraft.value!.dischargeTime = '2026-06-26 08:31:00'
    controller.editableCopyDraft.value!.documents[0].record_time = 'bad-time'
    await controller.saveEditableCopy({ runAfterSave: false })
    expect(createManualTestMedicalRecord).not.toHaveBeenCalled()
    expect(message.warning).toHaveBeenCalledWith('文书「入院记录」的记录时间格式无效')
  })

  it('非 0609 模式下省略 selected_rule_ids，且保存并验证期间全程保持 loading 并防止重入', async () => {
    const {
      controller,
      selectedPoolId,
      loadPools,
      loadRecords,
      loadLatestSyncJob,
      restoreCurrentQcTaskForSelectedPool,
      onPoolSwitched,
      openBatchJob,
    } = createController({ isLuxian0609: false })

    let loadingDuringLoadPools = false
    let loadingDuringLoadRecords = false
    let loadingDuringRun = false
    loadPools.mockImplementation(async () => {
      loadingDuringLoadPools = controller.editableCopySaveAndRunLoading.value
    })
    loadRecords.mockImplementation(async () => {
      loadingDuringLoadRecords = controller.editableCopySaveAndRunLoading.value
    })
    let resolveRun!: (v: unknown) => void
    const runDeferred = new Promise((resolve) => {
      resolveRun = resolve
    })
    runManualSamplePool.mockImplementationOnce(() => {
      loadingDuringRun = controller.editableCopySaveAndRunLoading.value
      return runDeferred
    })

    await controller.openEditableCopyDrawer(buildRecord())
    const firstSave = controller.saveEditableCopy({ runAfterSave: true })
    // 并发重入应直接忽略
    await controller.saveEditableCopy({ runAfterSave: true })
    expect(createManualTestMedicalRecord).toHaveBeenCalledTimes(1)

    await Promise.resolve()
    resolveRun({ success: true, data: { job_id: 'job-non-0609' } })
    await firstSave

    expect(loadingDuringLoadPools).toBe(true)
    expect(loadingDuringLoadRecords).toBe(true)
    expect(loadingDuringRun).toBe(true)
    expect(controller.editableCopySaveAndRunLoading.value).toBe(false)
    expect(controller.editableCopyOpen.value).toBe(false)
    expect(controller.editableCopyDraft.value).toBeNull()
    expect(selectedPoolId.value).toBe(CUSTOMER_TEST_POOL_ID)
    expect(loadLatestSyncJob).toHaveBeenCalledTimes(1)
    expect(restoreCurrentQcTaskForSelectedPool).toHaveBeenCalledTimes(1)
    expect(onPoolSwitched).toHaveBeenCalledWith(CUSTOMER_TEST_POOL_ID)
    expect(openBatchJob).toHaveBeenCalledWith('job-new-1'.replace('job-new-1', 'job-non-0609'))

    const createPayload = createManualTestMedicalRecord.mock.calls[0][0]
    expect('selected_rule_ids' in createPayload).toBe(false)
    expect(createPayload.basic_info.admission_time).toBe('2026-06-18T07:02:00+08:00')
    const runPayload = runManualSamplePool.mock.calls[0][1]
    expect('selected_rule_ids' in runPayload).toBe(false)
  })

  it('手动关闭已修改草稿时弹出未保存确认，显式强制关闭时跳过确认', async () => {
    const { controller } = createController()
    await controller.openEditableCopyDrawer(buildRecord())

    // 未修改直接关闭，不弹确认
    controller.closeEditableCopyDrawer()
    expect(Modal.confirm).not.toHaveBeenCalled()
    expect(controller.editableCopyOpen.value).toBe(false)

    // 修改草稿后手动关闭（即使传入 MouseEvent 也不会误判为 force=true）
    await controller.openEditableCopyDrawer(buildRecord())
    controller.editableCopyDraft.value!.caseTitle = '修改后的副本标题'
    expect(controller.isEditableCopyDirty.value).toBe(true)

    controller.closeEditableCopyDrawer({ type: 'click' } as unknown as Event)
    expect(Modal.confirm).toHaveBeenCalledTimes(1)
    expect(controller.editableCopyOpen.value).toBe(true)

    // 确认放弃后关闭并清理状态
    const confirmConfig = Modal.confirm.mock.calls[0][0] as { onOk?: () => void }
    confirmConfig.onOk?.()
    expect(controller.editableCopyOpen.value).toBe(false)
    expect(controller.editableCopyDraft.value).toBeNull()
  })
})
