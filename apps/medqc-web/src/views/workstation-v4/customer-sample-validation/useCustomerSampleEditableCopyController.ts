import { SAMPLE_RULE_SET_RUN_TIMEOUT_MS } from '@/config/requestTimeouts'
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import { loadCurrentMedicalRecord } from '@/services/current-medical-record'
import { emptyMedicalOrderFilters, matchesMedicalOrderFilters } from './medicalOrderFilters'
import type {
  EditableMedicalRecordDocument,
  ManualSamplePool,
  ManualSamplePoolRecord,
  ManualSampleValidationMode,
  ManualTestRecordCreateRequest,
} from './types'
import {
  createManualTestMedicalRecord,
  getEditableMedicalRecordDocuments,
  runManualSamplePool,
} from '@/services/manual-case-sample-service'
import {
  type EditableCopyDocumentFilter,
  type EditableCopyDocumentGroup,
  type EditableCopyDraft,
} from './customerSampleValidationConfig'
import {
  CUSTOMER_TEST_POOL_ID,
  formatRecordDateTime,
  parseBackendDateTime,
  resolveRecordDisplayTitle,
  resolveRecordIdentifier,
  resolveRecordMainDiagnosis,
  resolveRecordPatientName,
} from './recordPresentation'
import {
  compareEditableOrderDocumentByTimeDesc,
  editableCopyDocumentGroupKey,
  editableCopyDocumentGroupLabel,
  editableDocumentTypeLabel,
  isEditableOrderDocument,
  parseEditableOrderRow,
  resolveEditableOrderTypeKey,
  resolveEditableOrderTypeLabel,
  type EditableCopyOrderRow,
  type EditableCopyOrderTypeFilter,
} from './editableCopyPresentation'

export interface CustomerSampleEditableCopyDependencies {
  selectedPool: Ref<ManualSamplePool | undefined>
  selectedPoolId: Ref<string | undefined>
  pools: Ref<ManualSamplePool[]>
  selectedValidationMode: Ref<ManualSampleValidationMode>
  selectedRuleSetPayloadKey: ComputedRef<string>
  isLuxian0609Mode: ComputedRef<boolean>
  selectedLuxianCustomerRuleIds: Ref<string[]>
  normalizeLuxianRuleIds: (ruleIds: string[]) => string[]
  loadPools: () => Promise<void>
  loadRecords: () => Promise<void>
  openBatchJob: (jobId: string) => Promise<void>
}

export function useCustomerSampleEditableCopyController(
  dependencies: CustomerSampleEditableCopyDependencies,
) {
  const {
    selectedPool,
    selectedPoolId,
    pools,
    selectedValidationMode,
    selectedRuleSetPayloadKey,
    isLuxian0609Mode,
    selectedLuxianCustomerRuleIds,
    normalizeLuxianRuleIds,
    loadPools,
    loadRecords,
    openBatchJob,
  } = dependencies

  const editableCopyOpen = ref(false)
  const editableCopyLoading = ref(false)
  const editableCopySaving = ref(false)
  const editableCopySaveAndRunLoading = ref(false)
  const editableCopyReadonly = ref(false)
  const editableCopySourceRecord = ref<ManualSamplePoolRecord | null>(null)
  const editableCopyDraft = ref<EditableCopyDraft | null>(null)
  const editableCopyNewDocumentType = ref('daily_course_record')
  const editableCopyDocumentQuery = ref('')
  const editableCopyDocumentFilter = ref<EditableCopyDocumentFilter>('all')
  const editableCopyOrderTypeFilter = ref<EditableCopyOrderTypeFilter>('temporary')
  const editableCopyOrderFilters = ref(emptyMedicalOrderFilters())
  const editableCopyActiveDocumentKey = ref('')
  const editableCopyExpandedGroupKeys = ref(new Set<string>())
  const editableCopyAllDocuments = computed(() => editableCopyDraft.value?.documents || [])
  const editableCopyEnabledDocumentCount = computed(
    () => editableCopyAllDocuments.value.filter((document) => document.enabled !== false).length,
  )
  const editableCopyOrderDocuments = computed(() =>
    editableCopyAllDocuments.value
      .filter((document) => isEditableOrderDocument(document))
      .slice()
      .sort(compareEditableOrderDocumentByTimeDesc),
  )
  const editableCopyOrderRows = computed<EditableCopyOrderRow[]>(() =>
    editableCopyOrderDocuments.value.map((document) => parseEditableOrderRow(document)),
  )
  const editableCopyScopedOrderRows = computed(() =>
    editableCopyOrderRows.value.filter(
      (row) => row.orderTypeKey === editableCopyOrderTypeFilter.value,
    ),
  )
  const editableCopyVisibleOrderRows = computed(() =>
    editableCopyScopedOrderRows.value.filter((row) =>
      matchesMedicalOrderFilters(row, editableCopyOrderFilters.value),
    ),
  )
  const editableCopyFilteredDocuments = computed(() => {
    const query = editableCopyDocumentQuery.value.trim().toLowerCase()
    return editableCopyAllDocuments.value.filter((document) => {
      if (editableCopyDocumentFilter.value === 'enabled' && document.enabled === false) return false
      if (editableCopyDocumentFilter.value === 'orders' && !isEditableOrderDocument(document))
        return false
      if (editableCopyDocumentFilter.value === 'new' && !document.is_new) return false
      if (!query) return true
      return [
        document.title,
        document.document_type,
        document.record_time,
        document.content,
        resolveEditableOrderTypeLabel(document),
      ]
        .join(' ')
        .toLowerCase()
        .includes(query)
    })
  })
  const editableCopyDocumentGroups = computed<EditableCopyDocumentGroup[]>(() => {
    const groups = new Map<string, EditableCopyDocumentGroup>()
    editableCopyFilteredDocuments.value.forEach((document) => {
      const key = editableCopyDocumentGroupKey(document)
      const label = editableCopyDocumentGroupLabel(key)
      if (!groups.has(key)) groups.set(key, { key, label, documents: [] })
      groups.get(key)?.documents.push(document)
    })
    return ['admission', 'course', 'surgery', 'exam_lab', 'other', 'order']
      .map((key) => groups.get(key))
      .filter((group): group is EditableCopyDocumentGroup => Boolean(group))
  })
  const editableCopyActiveDocument = computed(() => {
    const documents = editableCopyAllDocuments.value
    return (
      documents.find((document) => document.key === editableCopyActiveDocumentKey.value) ||
      editableCopyFilteredDocuments.value[0] ||
      documents[0] ||
      null
    )
  })
  const editableCopyActiveDocumentGroupKey = computed(() => {
    const document = editableCopyActiveDocument.value
    return document ? editableCopyDocumentGroupKey(document) : ''
  })

  let documentLoadSeq = 0

  function isSameEditableCopyRecord(
    left: ManualSamplePoolRecord | null,
    right: ManualSamplePoolRecord | null,
  ): boolean {
    if (!left || !right) return false
    if (left === right) return true
    return (
      String(left.id || '') === String(right.id || '') &&
      String(left.matched_institute_id || '') === String(right.matched_institute_id || '') &&
      String(left.matched_patient_id || '') === String(right.matched_patient_id || '') &&
      String(left.matched_visit_id || '') === String(right.matched_visit_id || '')
    )
  }

  async function loadEditableCopyDocuments(
    record: ManualSamplePoolRecord,
    options?: { readonly?: boolean },
  ): Promise<boolean> {
    const seq = ++documentLoadSeq
    const targetReadonly = Boolean(options?.readonly ?? editableCopyReadonly.value)
    editableCopyReadonly.value = targetReadonly
    editableCopyOrderFilters.value = emptyMedicalOrderFilters()
    editableCopySourceRecord.value = record
    editableCopyDraft.value = null
    editableCopyOpen.value = true
    editableCopyLoading.value = true
    const visitId = record.matched_visit_id || ''
    let result:
      | Awaited<ReturnType<typeof loadCurrentMedicalRecord>>
      | Awaited<ReturnType<typeof getEditableMedicalRecordDocuments>>
    try {
      result = await (targetReadonly
        ? loadCurrentMedicalRecord(visitId, {
            instituteId: record.matched_institute_id,
            patientId: record.matched_patient_id,
          })
        : getEditableMedicalRecordDocuments(visitId, {
            institute_id: record.matched_institute_id,
            patient_id: record.matched_patient_id,
            visit_id: record.matched_visit_id,
          }))
    } catch (error: any) {
      if (
        seq !== documentLoadSeq ||
        !editableCopyOpen.value ||
        !isSameEditableCopyRecord(editableCopySourceRecord.value, record)
      ) {
        return false
      }
      editableCopyLoading.value = false
      message.error(error?.message || '读取源病历文书失败')
      return false
    }
    if (
      seq !== documentLoadSeq ||
      !editableCopyOpen.value ||
      !isSameEditableCopyRecord(editableCopySourceRecord.value, record)
    ) {
      return false
    }
    editableCopyLoading.value = false
    if (!result.success || !result.data) {
      message.error(result.message || '读取源病历文书失败')
      return false
    }
    if (!result.data.documents.length) {
      message.warning('当前源病历未读取到可编辑文书')
    }
    const currentRecord = targetReadonly
      ? { ...record, admission_time: result.data.current_record?.admission_time || '' }
      : record
    editableCopyDraft.value = buildEditableCopyDraft(currentRecord, result.data.documents, {
      readonly: targetReadonly,
    })
    editableCopyDocumentQuery.value = ''
    editableCopyDocumentFilter.value = 'all'
    editableCopyOrderTypeFilter.value = editableCopyOrderRows.value.some(
      (row) => row.orderTypeKey === 'temporary',
    )
      ? 'temporary'
      : 'long'
    const documents = editableCopyDraft.value.documents
    const initialDocument =
      documents.find(
        (document) => editableDocumentTypeLabel(document.document_type) === '入院记录',
      ) || documents[0]
    editableCopyActiveDocumentKey.value = initialDocument?.key || ''
    return true
  }

  async function openMedicalRecordViewer(record: ManualSamplePoolRecord) {
    if (!record.matched_visit_id) {
      message.warning('当前样本尚未匹配到病历，无法查看原文')
      return
    }
    editableCopyReadonly.value = true
    await loadEditableCopyDocuments(record, { readonly: true })
  }

  function resolveEditableCopyTitle(record: ManualSamplePoolRecord): string {
    const title = resolveRecordDisplayTitle(record)
    if (title && title !== '-') return `${title}编辑副本`
    const patientName = resolveRecordPatientName(record)
    return `${patientName === '-' ? '源病历' : patientName}编辑副本`
  }

  function resolveEditableCopyAdmissionTime(record: ManualSamplePoolRecord): string {
    const admissionTime = formatRecordDateTime(record.admission_time)
    if (admissionTime) return admissionTime
    const raw = record.created_at || record.updated_at || new Date().toISOString()
    const parsed = parseBackendDateTime(raw)
    if (Number.isNaN(parsed.getTime())) return new Date().toISOString().slice(0, 16)
    return parsed.toISOString().slice(0, 16)
  }

  function selectEditableCopyDocument(key: string) {
    editableCopyActiveDocumentKey.value = key
    const document = editableCopyAllDocuments.value.find((item) => item.key === key)
    if (document && editableCopyReadonly.value) {
      editableCopyExpandedGroupKeys.value = new Set([editableCopyDocumentGroupKey(document)])
    }
    if (document && isEditableOrderDocument(document)) {
      editableCopyOrderTypeFilter.value = resolveEditableOrderTypeKey(document)
    }
  }

  function selectEditableCopyOrderGroup() {
    const rows = editableCopyVisibleOrderRows.value.length
      ? editableCopyVisibleOrderRows.value
      : editableCopyOrderRows.value
    const first = rows[0]?.document
    if (first) {
      editableCopyActiveDocumentKey.value = first.key
      if (editableCopyReadonly.value) {
        editableCopyExpandedGroupKeys.value = new Set(['order'])
      }
      editableCopyOrderTypeFilter.value = resolveEditableOrderTypeKey(first)
    }
  }

  function isEditableCopyDocumentGroupExpanded(groupKey: string): boolean {
    return !editableCopyReadonly.value || editableCopyExpandedGroupKeys.value.has(groupKey)
  }

  function toggleEditableCopyDocumentGroup(groupKey: string) {
    if (!editableCopyReadonly.value) return
    const next = new Set(editableCopyExpandedGroupKeys.value)
    if (next.has(groupKey)) next.delete(groupKey)
    else next.add(groupKey)
    editableCopyExpandedGroupKeys.value = next
  }

  function syncEditableCopyExpandedDocumentGroups() {
    if (!editableCopyReadonly.value) return
    const groupKeys = editableCopyDocumentGroups.value.map((group) => group.key)
    if (editableCopyDocumentQuery.value.trim()) {
      editableCopyExpandedGroupKeys.value = new Set(groupKeys)
      return
    }

    const activeGroupKey = editableCopyActiveDocumentGroupKey.value
    if (activeGroupKey && groupKeys.includes(activeGroupKey)) {
      editableCopyExpandedGroupKeys.value = new Set([activeGroupKey])
      return
    }

    if (!editableCopyExpandedGroupKeys.value.size && groupKeys[0]) {
      editableCopyExpandedGroupKeys.value = new Set([groupKeys[0]])
    }
  }

  watch(
    [
      editableCopyReadonly,
      editableCopyActiveDocumentGroupKey,
      editableCopyDocumentQuery,
      editableCopyDocumentFilter,
      () => editableCopyDocumentGroups.value.map((group) => group.key).join('|'),
    ],
    syncEditableCopyExpandedDocumentGroups,
    { immediate: true },
  )

  function createEditableCopyDocument(documentType: string): EditableMedicalRecordDocument {
    const normalizedType =
      String(documentType || 'daily_course_record').trim() || 'daily_course_record'
    const title = editableDocumentTypeLabel(normalizedType)
    const timestamp = Date.now()
    return {
      key: `editable-new-${normalizedType}-${timestamp}`,
      document_type: normalizedType,
      title,
      record_time: new Date().toISOString().slice(0, 16),
      submit_time: '',
      content:
        normalizedType === 'medical_order'
          ? '请填写医嘱名称、剂量、频次、用法、开立时间、停止时间及开立医师。'
          : `请填写${title}正文。`,
      doctor_name: '',
      enabled: true,
      is_new: true,
    }
  }

  function addEditableCopyDocument(documentType = editableCopyNewDocumentType.value) {
    if (!editableCopyDraft.value) return
    const document = createEditableCopyDocument(documentType)
    editableCopyDraft.value.documents.push(document)
    editableCopyActiveDocumentKey.value = document.key
  }

  function addEditableCopyOrderDocument() {
    addEditableCopyDocument('medical_order')
  }

  function removeEditableCopyDocument(document: EditableMedicalRecordDocument) {
    const draft = editableCopyDraft.value
    if (!draft) return
    if (document.is_new) {
      draft.documents = draft.documents.filter((item) => item.key !== document.key)
      if (editableCopyActiveDocumentKey.value === document.key) {
        editableCopyActiveDocumentKey.value = draft.documents[0]?.key || ''
      }
      return
    }
    document.enabled = document.enabled === false
    editableCopyActiveDocumentKey.value = document.key
  }

  function buildEditableCopyDraft(
    record: ManualSamplePoolRecord,
    documents: EditableMedicalRecordDocument[],
    options: { readonly?: boolean } = {},
  ): EditableCopyDraft {
    const patientName = resolveRecordPatientName(record)
    const readonlyMode = options.readonly === true
    const sourceTitle = resolveRecordDisplayTitle(record)
    const sourceDiagnosis = resolveRecordMainDiagnosis(record)
    const normalizedDocuments = documents.map((document, index) => ({
      ...document,
      key: document.key || `${document.document_type || 'document'}-${index + 1}`,
      title: document.title || document.document_type || `文书 ${index + 1}`,
      document_type: document.document_type || document.title || '日常病程记录',
      enabled: document.enabled !== false,
      content: document.content || '',
    }))
    return {
      caseTitle: readonlyMode
        ? sourceTitle || resolveRecordIdentifier(record)
        : resolveEditableCopyTitle(record),
      patientName: patientName === '-' ? '脱敏患者' : patientName,
      sex: '未说明',
      age: 50,
      mrNo: '',
      department: record.department || '未说明科室',
      admissionTime: readonlyMode
        ? formatRecordDateTime(record.admission_time)
        : resolveEditableCopyAdmissionTime(record),
      dischargeTime: formatRecordDateTime(record.discharge_time),
      mainDiagnosis: readonlyMode
        ? sourceDiagnosis || '未返回'
        : sourceDiagnosis || '源病历编辑副本',
      manualIssueText: readonlyMode
        ? `源病历：${resolveRecordIdentifier(record)}。当前仅查看已同步文书原文。`
        : `源病历编辑副本：${resolveRecordIdentifier(record)}。原始同步病历保持只读，本副本用于客户自定义修改后验证。`,
      documents: normalizedDocuments,
    }
  }

  async function openEditableCopyDrawer(record: ManualSamplePoolRecord) {
    if (!record.matched_visit_id) {
      message.warning('当前样本尚未匹配到病历，无法创建编辑副本')
      return
    }
    editableCopyReadonly.value = false
    await loadEditableCopyDocuments(record, { readonly: false })
  }

  function closeEditableCopyDrawer() {
    if (editableCopySaving.value || editableCopySaveAndRunLoading.value) return
    documentLoadSeq += 1
    editableCopyLoading.value = false
    editableCopyOpen.value = false
    editableCopyReadonly.value = false
    editableCopySourceRecord.value = null
    editableCopyDraft.value = null
    editableCopyActiveDocumentKey.value = ''
    editableCopyDocumentQuery.value = ''
    editableCopyDocumentFilter.value = 'all'
  }

  function buildEditableCopySourceMeta(record: ManualSamplePoolRecord) {
    return {
      type: 'customer_source_editable_copy',
      source_pool_id: selectedPool.value?.id || selectedPoolId.value || '',
      source_pool_name: selectedPool.value?.name || '',
      source_record_id: record.id,
      source_item_ids: record.sample_item_ids || [],
      source_visit_id: record.matched_visit_id || '',
      source_mr_no: record.mr_no || '',
      source_patient_name: record.patient_name || '',
      source_department: record.department || '',
      created_from: 'customer_sample_validation',
    }
  }

  function normalizeEditableCopyDateTime(value?: string): string | undefined {
    const text = String(value || '').trim()
    if (!text || text === '-' || text === '未返回') return undefined
    const parsed = parseBackendDateTime(text)
    if (Number.isNaN(parsed.getTime())) return undefined
    return parsed.toISOString()
  }

  function buildEditableCopyPayload(
    record: ManualSamplePoolRecord,
  ): ManualTestRecordCreateRequest | null {
    const draft = editableCopyDraft.value
    if (!draft) return null
    const enabledDocuments = draft.documents
      .filter((document) => document.enabled !== false)
      .map((document) => ({
        document_type: document.document_type,
        title: document.title,
        record_time: normalizeEditableCopyDateTime(document.record_time),
        submit_time: normalizeEditableCopyDateTime(document.submit_time),
        content: document.content,
        doctor_name: document.doctor_name,
        doctor_code: document.doctor_code,
        enabled: true,
      }))
      .filter((document) => document.content.trim())
    return {
      case_title: draft.caseTitle.trim() || resolveEditableCopyTitle(record),
      basic_info: {
        patient_name: draft.patientName.trim() || '脱敏患者',
        sex: draft.sex.trim() || '未说明',
        age: Number.isFinite(draft.age) ? draft.age : 50,
        mr_no: draft.mrNo.trim() || undefined,
        department: draft.department.trim() || record.department || '未说明科室',
        admission_time:
          normalizeEditableCopyDateTime(draft.admissionTime) || new Date().toISOString(),
        discharge_time: normalizeEditableCopyDateTime(draft.dischargeTime),
        main_diagnosis: draft.mainDiagnosis.trim() || '源病历编辑副本',
      },
      documents: enabledDocuments,
      selected_rule_ids: isLuxian0609Mode.value
        ? normalizeLuxianRuleIds(selectedLuxianCustomerRuleIds.value)
        : [],
      manual_issue_text: draft.manualIssueText.trim(),
      template_key: 'customer_source_editable_copy',
      source: buildEditableCopySourceMeta(record),
    }
  }

  async function saveEditableCopy(options: { runAfterSave: boolean }) {
    if (editableCopyReadonly.value) {
      message.warning('当前为只读查看模式，不能保存测试病历')
      return
    }
    const sourceRecord = editableCopySourceRecord.value
    const payload = sourceRecord ? buildEditableCopyPayload(sourceRecord) : null
    if (!sourceRecord || !payload) {
      message.warning('请先读取源病历文书')
      return
    }
    if (!payload.documents.length) {
      message.warning('至少保留一份有正文的文书后再保存')
      return
    }
    if (options.runAfterSave && isLuxian0609Mode.value && !payload.selected_rule_ids?.length) {
      message.warning('请先选择要验证的 LX0609 质控点')
      return
    }
    if (options.runAfterSave) {
      editableCopySaveAndRunLoading.value = true
    } else {
      editableCopySaving.value = true
    }
    const createResult = await createManualTestMedicalRecord(payload)
    if (options.runAfterSave) {
      editableCopySaveAndRunLoading.value = false
    } else {
      editableCopySaving.value = false
    }
    if (!createResult.success || !createResult.data) {
      message.error(createResult.message || '保存编辑副本失败')
      return
    }
    message.success('编辑副本已保存为自建测试病历')
    documentLoadSeq += 1
    editableCopyOpen.value = false
    await loadPools()
    if (selectedPoolId.value !== CUSTOMER_TEST_POOL_ID) {
      selectedPoolId.value = CUSTOMER_TEST_POOL_ID
      selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
    }
    await loadRecords()
    if (!options.runAfterSave) return

    const createdItem = createResult.data.item
    const createdSampleItemId = String(createdItem?.id || '').trim()
    const createdInstituteId = String(createdItem?.matched_institute_id || '').trim()
    const createdPatientId = String(createdItem?.matched_patient_id || '').trim()
    const createdVisitId = String(createdItem?.matched_visit_id || '').trim()
    if (!createdSampleItemId || !createdInstituteId || !createdPatientId || !createdVisitId) {
      message.error('编辑副本已保存，但病例三坐标尚未完整生成，未发起质控任务')
      return
    }
    const runPayload = {
      sample_item_ids: [createdSampleItemId],
      record_refs: [
        {
          institute_id: createdInstituteId,
          patient_id: createdPatientId,
          visit_id: createdVisitId,
        },
      ],
      max_parallel_records: 1,
      validation_mode: selectedValidationMode.value,
      rule_set_key: selectedRuleSetPayloadKey.value,
      selected_rule_ids: payload.selected_rule_ids,
    }
    const runResult = await runManualSamplePool(CUSTOMER_TEST_POOL_ID, runPayload, {
      timeout: SAMPLE_RULE_SET_RUN_TIMEOUT_MS,
    })
    if (!runResult.success || !runResult.data) {
      message.error(runResult.message || '编辑副本已保存，但发起验证失败')
      return
    }
    message.success('编辑副本验证任务已创建')
    await openBatchJob(runResult.data.job_id)
  }

  return {
    editableCopyOpen,
    editableCopyLoading,
    editableCopySaving,
    editableCopySaveAndRunLoading,
    editableCopyReadonly,
    editableCopySourceRecord,
    editableCopyDraft,
    editableCopyNewDocumentType,
    editableCopyDocumentQuery,
    editableCopyDocumentFilter,
    editableCopyOrderTypeFilter,
    editableCopyOrderFilters,
    editableCopyOrderRows,
    editableCopyScopedOrderRows,
    editableCopyEnabledDocumentCount,
    editableCopyVisibleOrderRows,
    editableCopyFilteredDocuments,
    editableCopyDocumentGroups,
    editableCopyActiveDocument,
    openMedicalRecordViewer,
    selectEditableCopyDocument,
    selectEditableCopyOrderGroup,
    isEditableCopyDocumentGroupExpanded,
    toggleEditableCopyDocumentGroup,
    addEditableCopyDocument,
    addEditableCopyOrderDocument,
    removeEditableCopyDocument,
    openEditableCopyDrawer,
    closeEditableCopyDrawer,
    saveEditableCopy,
  }
}
