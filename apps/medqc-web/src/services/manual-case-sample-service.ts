import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type {
  ManualSamplePoolItemsResult,
  ManualSamplePoolListResult,
  ManualSamplePool,
  ManualSamplePoolRecordsResult,
  ManualSamplePoolRunResult,
  ManualSamplePoolSyncJob,
  HospitalizationScopePayload,
  HospitalizationScopePreview,
  ManualTestRecordCreateRequest,
  ManualTestRecordCreateResult,
  EditableMedicalRecordDocumentsResult,
  EditableMedicalRecordDocument,
  ManualLuxian0609RuleCatalogResult,
  ManualSampleValidationRuleSetListResult,
  Sheet2ExactReviewAcceptancePackage,
} from '@/views/workstation-v4/customer-sample-validation/types'
import { deduplicateMedicalDocumentSections } from '@/views/workstation-v4/customer-sample-validation/medicalDocumentDisplay'
import { normalizeFrontpageDisplay } from '@/views/workstation-v4/customer-sample-validation/frontpageDisplay'

type ServiceResult<T> = {
  success: boolean
  data?: T
  message?: string
  errorType?: 'timeout' | 'network' | 'server' | 'unknown'
}

const EDITABLE_MEDICAL_RECORD_DOCUMENTS_TIMEOUT_MS = 90000

function toErrorMessage(error: unknown, fallback: string): string {
  return extractApiErrorMessageFromError(error, fallback)
}

function classifyRequestError(error: unknown): ServiceResult<never>['errorType'] {
  if (error && typeof error === 'object') {
    const candidate = error as { code?: unknown; message?: unknown; response?: unknown }
    const code = String(candidate.code || '').toLowerCase()
    const message = String(candidate.message || '').toLowerCase()
    if (code === 'econnaborted' || message.includes('timeout')) {
      return 'timeout'
    }
    if (!candidate.response && (code === 'err_network' || message.includes('network'))) {
      return 'network'
    }
    if (candidate.response) {
      return 'server'
    }
  }
  return 'unknown'
}

async function requestEnvelope<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  fallbackMessage: string,
): Promise<ServiceResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return {
      success: normalized.success,
      data: normalized.data,
      message: normalized.message,
    }
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, fallbackMessage),
      errorType: classifyRequestError(error),
    }
  }
}

export async function listManualSamplePools(params: {
  q?: string
  page?: number
  page_size?: number
}) {
  return requestEnvelope<ManualSamplePoolListResult>(
    {
      method: 'GET',
      url: '/api/v1/qc/sample-pools',
      params,
    },
    '获取客户样本池失败',
  )
}

export async function deleteManualSamplePool(poolId: string) {
  return requestEnvelope<{
    deleted: boolean
    pool_id: string
    pool_name: string
    deleted_item_count: number
    deleted_sync_job_count: number
  }>(
    {
      method: 'DELETE',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}`,
    },
    '删除样本池失败',
  )
}

export async function importManualSamplePoolByUpload(payload: {
  pool_name: string
  source_sheet?: string
  description?: string
  scene?: string
  file: File
}) {
  const formData = new FormData()
  formData.append('pool_name', payload.pool_name)
  if (payload.source_sheet) {
    formData.append('source_sheet', payload.source_sheet)
  }
  formData.append('description', payload.description || '')
  formData.append('scene', payload.scene || 'running')
  formData.append('file', payload.file)

  return requestEnvelope<{
    id: string
    name: string
    imported_rows: number
  }>(
    {
      method: 'POST',
      url: '/api/v1/qc/sample-pools/import-upload',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    },
    '导入客户样本模板失败',
  )
}

export async function createManualTestMedicalRecord(payload: ManualTestRecordCreateRequest) {
  return requestEnvelope<ManualTestRecordCreateResult>(
    {
      method: 'POST',
      url: '/api/v1/qc/sample-pools/test-records',
      data: payload,
    },
    '创建测试病历失败',
  )
}

function readStringField(source: Record<string, unknown>, keys: string[], fallback = ''): string {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
    if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  }
  return fallback
}

function readDocumentSections(source: Record<string, unknown>) {
  const sectionsSource = Array.isArray(source.sections) ? source.sections : []
  const sections = sectionsSource
    .map((item, index) => {
      if (!item || typeof item !== 'object') return null
      const row = item as Record<string, unknown>
      const text = readStringField(row, ['text', 'content', 'value'])
      const label = readStringField(row, ['section_label', 'label', 'title'])
      if (!text || !label) return null
      const rawOrderIndex = row.order_index
      return {
        key: readStringField(row, ['section_key', 'key', 'source_field'], `section-${index + 1}`),
        label,
        text,
        source_field: readStringField(row, ['source_field']),
        order_index:
          typeof rawOrderIndex === 'number' && Number.isFinite(rawOrderIndex)
            ? rawOrderIndex
            : index,
      }
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
    .sort((left, right) => left.order_index - right.order_index)
  return deduplicateMedicalDocumentSections(sections)
}

function normalizeEditableDocumentsResponse(
  value: unknown,
  options: { includeSummaries?: boolean } = {},
): EditableMedicalRecordDocumentsResult {
  const payload =
    value && typeof value === 'object' && 'data' in value
      ? (value as { data?: unknown }).data
      : value
  const candidate =
    payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {}
  const documentsSource = Array.isArray(candidate.documents)
    ? candidate.documents
    : Array.isArray(candidate.items)
      ? candidate.items
      : Array.isArray(payload)
        ? payload
        : []
  const documents = documentsSource
    .map((item, index): EditableMedicalRecordDocument | null => {
      if (!item || typeof item !== 'object') return null
      const row = item as Record<string, unknown>
      const content = readStringField(row, [
        'content',
        'record_content',
        'text',
        'document_content',
        'original_text',
      ])
      const hasContent = row.has_content === true || Boolean(content)
      const title = readStringField(
        row,
        [
          'title',
          'document_title',
          'doc_name',
          'label',
          'doc_title',
          'name',
          'document_type',
          'doc_type',
          'type',
        ],
        `文书 ${index + 1}`,
      )
      const documentType = readStringField(
        row,
        ['document_type', 'doc_type', 'type', 'source_table', 'table_name'],
        title,
      )
      const rawRecordTime = readStringField(row, [
        'record_time',
        'record_datetime',
        'report_datetime',
        'order_datetime',
        'start_time',
        'start_datetime',
        'begin_time',
        'begin_datetime',
        'order_start_time',
      ])
      const orderDisplayTime =
        documentType === 'inpat_drug_order' || documentType === 'inpat_nondrug_order'
          ? readStringField(row, ['sort_time', 'display_time', 'prescribed_datetime'])
          : ''
      const submitTime = readStringField(row, ['submit_time', 'submit_datetime'])
      const reportItems = Array.isArray(row.report_items)
        ? row.report_items
            .filter((entry): entry is Record<string, unknown> =>
              Boolean(entry && typeof entry === 'object'),
            )
            .map((entry) => ({
              item_no: readStringField(entry, ['item_no']),
              item_id: readStringField(entry, ['item_id']),
              item_code: readStringField(entry, ['item_code']),
              item_name: readStringField(entry, ['item_name']),
              result: readStringField(entry, ['result']),
              abnormal_indicator: readStringField(entry, ['abnormal_indicator']),
              reference_range: readStringField(entry, ['reference_range']),
              referencevalue_min: readStringField(entry, ['referencevalue_min']),
              referencevalue_max: readStringField(entry, ['referencevalue_max']),
              unit: readStringField(entry, ['unit']),
              findings: readStringField(entry, ['findings']),
              impression: readStringField(entry, ['impression']),
            }))
        : []
      const reportMetadataSource =
        row.report_metadata && typeof row.report_metadata === 'object'
          ? (row.report_metadata as Record<string, unknown>)
          : {}
      const reportMetadata = Object.fromEntries(
        Object.entries(reportMetadataSource)
          .map(([key, fieldValue]) => [key, String(fieldValue ?? '').trim()])
          .filter(([, fieldValue]) => Boolean(fieldValue)),
      )
      const sourceDocumentAliases = Array.isArray(row.source_document_aliases)
        ? row.source_document_aliases
            .filter((entry): entry is Record<string, unknown> =>
              Boolean(entry && typeof entry === 'object'),
            )
            .map((entry) => {
              const sourceDocumentId = readStringField(entry, [
                'source_document_id',
                'document_id',
                'doc_id',
                'id',
              ])
              const sourceRef = readStringField(entry, ['source_ref'])
              if (!sourceDocumentId || !sourceRef) return null
              const sourceDocumentType = readStringField(entry, [
                'source_document_type',
                'document_type',
                'doc_type',
                'source_table',
              ])
              return {
                source_document_id: sourceDocumentId,
                source_ref: sourceRef,
                ...(sourceDocumentType ? { source_document_type: sourceDocumentType } : {}),
              }
            })
            .filter((item): item is NonNullable<typeof item> => Boolean(item))
        : []
      return {
        key: readStringField(
          row,
          ['key', 'doc_key', 'document_id', 'id'],
          `${documentType}-${index + 1}`,
        ),
        source_document_id: readStringField(row, ['document_id', 'doc_id', 'id']),
        source_ref: readStringField(row, ['source_ref']),
        source_document_aliases: sourceDocumentAliases,
        source_table: readStringField(row, ['source_table', 'table_name', 'doc_type']),
        document_type: documentType,
        pdf_review_parent_key: readStringField(row, ['pdf_review_parent_key']),
        pdf_review_relation:
          row.pdf_review_relation === 'same_content' ||
          row.pdf_review_relation === 'version_difference' ||
          row.pdf_review_relation === 'unmatched'
            ? row.pdf_review_relation
            : undefined,
        pdf_review_notes: Array.isArray(row.pdf_review_notes)
          ? row.pdf_review_notes.filter((note): note is string => typeof note === 'string')
          : undefined,
        pdf_source_file_id: readStringField(row, ['source_file_id']),
        pdf_source_pages: Array.isArray(row.source_pages)
          ? row.source_pages.filter(
              (page): page is number =>
                typeof page === 'number' && Number.isInteger(page) && page > 0,
            )
          : undefined,
        execution_domain: readStringField(row, ['execution_domain']),
        projection_incomplete: row.projection_incomplete === true,
        projection_notice:
          typeof row.projection_notice === 'string' ? row.projection_notice.trim() : '',
        title,
        sections: readDocumentSections(row),
        report_items: reportItems,
        report_metadata: reportMetadata,
        frontpage_display:
          documentType === 'mr' ? normalizeFrontpageDisplay(row.frontpage_display) : undefined,
        record_time: rawRecordTime || orderDisplayTime || submitTime,
        record_time_source:
          readStringField(row, ['record_time_source']) ||
          (!rawRecordTime && !orderDisplayTime && submitTime ? 'source_submit_time' : ''),
        submit_time: submitTime,
        order_start_time: readStringField(row, [
          'planned_start_datetime',
          'order_start_time',
          'start_time',
          'start_datetime',
          'begin_time',
          'begin_datetime',
          'order_datetime',
          'prescribed_datetime',
          'sort_time',
          'record_time',
          'record_datetime',
        ]),
        order_stop_time: readStringField(row, [
          'order_stop_time',
          'stop_time',
          'stop_datetime',
          'end_time',
          'end_datetime',
        ]),
        order_category: readStringField(row, [
          'order_category',
          'order_class',
          'order_type_name',
          'order_type',
          'item_type',
          'category',
        ]),
        order_item: readStringField(row, [
          'order_item',
          'order_name',
          'item_name',
          'project_name',
          'drug_name',
          'order_text',
          'order_content',
        ]),
        order_status: readStringField(row, ['order_status', 'status', 'order_state', 'state']),
        ...readEditableOrderDetails(row),
        doctor_name: readStringField(row, ['doctor_name', 'submitter', 'recorder']),
        doctor_code: readStringField(row, ['doctor_code', 'submitter_id']),
        enabled: true,
        has_content: hasContent,
        content_loaded: Boolean(content),
        content,
      }
    })
    .filter(
      (item): item is EditableMedicalRecordDocument =>
        Boolean(item) &&
        item.enabled !== false &&
        (Boolean(item.content.trim()) ||
          (options.includeSummaries === true && item.has_content === true)),
    )
  return {
    current_record:
      candidate.current_record && typeof candidate.current_record === 'object'
        ? {
            admission_time: readStringField(candidate.current_record as Record<string, unknown>, [
              'admission_time',
            ]),
            admission_time_source: readStringField(
              candidate.current_record as Record<string, unknown>,
              ['admission_time_source'],
            ),
            admission_time_state: readStringField(
              candidate.current_record as Record<string, unknown>,
              ['admission_time_state'],
            ),
          }
        : undefined,
    visit_id: readStringField(candidate, ['visit_id']),
    empty_reason: readStringField(candidate, [
      'empty_reason',
    ]) as EditableMedicalRecordDocumentsResult['empty_reason'],
    documents,
    raw: payload,
  }
}

function readEditableOrderDetails(
  row: Record<string, unknown>,
  fallback: Partial<EditableMedicalRecordDocument> = {},
) {
  return {
    order_id: readStringField(row, ['order_id'], fallback.order_id),
    order_planned_end_time: readStringField(
      row,
      ['order_planned_end_time', 'planned_end_time', 'planned_end_datetime'],
      fallback.order_planned_end_time,
    ),
    order_specification: readStringField(
      row,
      ['order_specification', 'specification', 'drug_specification'],
      fallback.order_specification,
    ),
    order_dosage: readStringField(row, ['order_dosage', 'dosage'], fallback.order_dosage),
    order_frequency: readStringField(
      row,
      ['order_frequency', 'drug_frequency', 'frequency'],
      fallback.order_frequency,
    ),
    order_route: readStringField(
      row,
      ['order_route', 'drug_apply_method', 'route'],
      fallback.order_route,
    ),
    order_quantity: readStringField(row, ['order_quantity', 'quantity'], fallback.order_quantity),
    order_prescribed_doctor: readStringField(
      row,
      ['order_prescribed_doctor', 'prescribed_doctor', 'doctor_name'],
      fallback.order_prescribed_doctor,
    ),
  }
}

function normalizeEditableDocumentRender(
  value: unknown,
  summary: EditableMedicalRecordDocument,
): EditableMedicalRecordDocument {
  const payload =
    value && typeof value === 'object' && 'data' in value
      ? (value as { data?: unknown }).data
      : value
  const candidate =
    payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {}
  const metadata =
    candidate.metadata && typeof candidate.metadata === 'object'
      ? (candidate.metadata as Record<string, unknown>)
      : {}
  const renderBlocks = Array.isArray(candidate.render_blocks)
    ? candidate.render_blocks.filter((block): block is Record<string, unknown> =>
        Boolean(block && typeof block === 'object'),
      )
    : []
  const sections = deduplicateMedicalDocumentSections(
    renderBlocks
      .map((block, index) => {
        const blockType = readStringField(block, ['block_type'])
        let text = readStringField(block, ['text'])
        if (!text && blockType === 'kv_section' && Array.isArray(block.fields)) {
          text = block.fields
            .filter((field): field is Record<string, unknown> =>
              Boolean(field && typeof field === 'object'),
            )
            .map((field) => {
              const label = readStringField(field, ['label', 'key'])
              const fieldValue = readStringField(field, ['value'])
              return label && fieldValue ? `${label}：${fieldValue}` : ''
            })
            .filter(Boolean)
            .join('\n')
        }
        if (!text) return null
        return {
          key: readStringField(block, ['block_id'], `section-${index + 1}`),
          label: readStringField(block, ['title'], '文书内容'),
          text,
          source_field: readStringField(block, ['source_field']),
          order_index: index,
        }
      })
      .filter((section): section is NonNullable<typeof section> => Boolean(section)),
  )
  const orderRow = renderBlocks
    .filter((block) => readStringField(block, ['block_type']) === 'order_table')
    .flatMap((block) => (Array.isArray(block.rows) ? block.rows : []))
    .find((row): row is Record<string, unknown> => Boolean(row && typeof row === 'object'))
  const content = readStringField(candidate, ['content'])
  return {
    ...summary,
    key: readStringField(metadata, ['doc_key'], summary.key),
    source_document_id: readStringField(
      metadata,
      ['document_id', 'doc_id'],
      summary.source_document_id,
    ),
    source_table: summary.source_table || readStringField(metadata, ['doc_type']),
    document_type: readStringField(metadata, ['doc_type'], summary.document_type),
    title: readStringField(metadata, ['doc_name'], summary.title),
    record_time: readStringField(metadata, ['record_time'], summary.record_time),
    sections,
    order_start_time: orderRow
      ? readStringField(orderRow, ['order_start_time', 'start_time'], summary.order_start_time)
      : summary.order_start_time,
    order_stop_time: orderRow
      ? readStringField(orderRow, ['order_stop_time', 'stop_time'], summary.order_stop_time)
      : summary.order_stop_time,
    order_category: orderRow
      ? readStringField(orderRow, ['order_category', 'order_type'], summary.order_category)
      : summary.order_category,
    order_item: orderRow
      ? readStringField(orderRow, ['order_item', 'item'], summary.order_item)
      : summary.order_item,
    order_status: orderRow
      ? readStringField(orderRow, ['order_status', 'status'], summary.order_status)
      : summary.order_status,
    ...readEditableOrderDetails(orderRow || {}, summary),
    content,
    has_content: Boolean(content) || summary.has_content === true,
    content_loaded: true,
  }
}

type EditableDocumentRequestParams = {
  institute_id?: string
  patient_id?: string
  visit_id?: string
  job_id?: string
  record_ref?: string
  view?: 'full' | 'summary'
  source_view?: 'saved' | 'current'
}

export async function getEditableMedicalRecordDocuments(
  visitId: string,
  params?: EditableDocumentRequestParams,
) {
  try {
    const response = await ApiService.requestRaw<unknown>({
      method: 'GET',
      url: `/api/v1/emr/${encodeURIComponent(visitId)}/documents`,
      timeout: EDITABLE_MEDICAL_RECORD_DOCUMENTS_TIMEOUT_MS,
      params: {
        ...(params || {}),
        visit_id: params?.visit_id || visitId,
      },
    })
    return {
      success: true,
      data: normalizeEditableDocumentsResponse(response.data, {
        includeSummaries: params?.view === 'summary',
      }),
    } satisfies ServiceResult<EditableMedicalRecordDocumentsResult>
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, '读取病历文书失败'),
      errorType: classifyRequestError(error),
    } satisfies ServiceResult<EditableMedicalRecordDocumentsResult>
  }
}

export async function getEditableMedicalRecordDocument(
  visitId: string,
  summary: EditableMedicalRecordDocument,
  params?: Omit<EditableDocumentRequestParams, 'view' | 'record_ref'>,
) {
  try {
    const response = await ApiService.requestRaw<unknown>({
      method: 'GET',
      url: `/api/v1/emr/${encodeURIComponent(visitId)}/render`,
      timeout: EDITABLE_MEDICAL_RECORD_DOCUMENTS_TIMEOUT_MS,
      params: {
        ...(params || {}),
        visit_id: params?.visit_id || visitId,
        execution_domain: summary.execution_domain,
        doc_type: summary.document_type,
        doc_id: summary.source_document_id || summary.key,
      },
    })
    return {
      success: true,
      data: normalizeEditableDocumentRender(response.data, summary),
    } satisfies ServiceResult<EditableMedicalRecordDocument>
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, '读取病历文书正文失败'),
      errorType: classifyRequestError(error),
    } satisfies ServiceResult<EditableMedicalRecordDocument>
  }
}

export async function getManualSamplePoolItems(
  poolId: string,
  params: {
    coverage_type?: string
    match_status?: string
    include_in_batch_1?: boolean
    q?: string
    page?: number
    page_size?: number
  },
) {
  return requestEnvelope<ManualSamplePoolItemsResult>(
    {
      method: 'GET',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/items`,
      params,
    },
    '获取客户样本明细失败',
  )
}

export async function getManualSamplePoolRecords(
  poolId: string,
  params: {
    coverage_type?: string
    match_status?: string
    include_in_batch_1?: boolean
    q?: string
    page?: number
    page_size?: number
  },
) {
  return requestEnvelope<ManualSamplePoolRecordsResult>(
    {
      method: 'GET',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/records`,
      params,
    },
    '获取客户样本病历列表失败',
  )
}

export async function matchManualSamplePool(poolId: string) {
  return requestEnvelope<{
    pool_id: string
    matched: number
    ambiguous: number
    unmatched: number
    pool?: ManualSamplePool
  }>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/match`,
    },
    '执行病历匹配失败',
  )
}

export async function syncManualSamplePoolRecords(
  poolId: string,
  payload?: {
    only_intrinsic?: boolean
    include_in_batch_1?: boolean
    table_groups?: string[]
  },
) {
  return requestEnvelope<{
    job_id: string
    pool_id: string
    status: string
    summary?: ManualSamplePoolSyncJob['summary']
  }>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/sync-records`,
      data: payload || {},
    },
    '同步样本病历失败',
  )
}

export async function listManualSamplePoolAdmissionDepartments() {
  return requestEnvelope<{ items: string[] }>(
    {
      method: 'GET',
      url: '/api/v1/qc/sample-pools/source-admission-departments',
    },
    '获取入院科室失败',
  )
}

export async function previewManualSamplePoolHospitalizationScope(
  poolId: string,
  payload: HospitalizationScopePayload,
) {
  return requestEnvelope<HospitalizationScopePreview>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/hospitalization-scope/preview`,
      data: payload,
    },
    '预览住院范围失败',
  )
}

export async function syncManualSamplePoolRecordsByHospitalization(
  poolId: string,
  payload: HospitalizationScopePayload,
) {
  return requestEnvelope<{
    job_id: string
    pool_id: string
    status: string
    summary?: ManualSamplePoolSyncJob['summary']
  }>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/sync-by-hospitalization`,
      data: payload,
    },
    '按住院范围同步病历失败',
  )
}

export async function syncManualSamplePoolRecordsByAdmission(
  poolId: string,
  payload: {
    start_date: string
    end_date: string
    departments?: string[]
  },
) {
  return requestEnvelope<{
    job_id: string
    pool_id: string
    status: string
    summary?: ManualSamplePoolSyncJob['summary']
  }>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/sync-by-admission`,
      data: payload,
    },
    '按条件同步病历失败',
  )
}

export async function getLatestManualSamplePoolSyncJob(poolId: string) {
  return requestEnvelope<ManualSamplePoolSyncJob | null>(
    {
      method: 'GET',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/sync-jobs/latest`,
    },
    '获取样本同步任务失败',
  )
}

export async function getManualSamplePoolSyncJob(jobId: string) {
  return requestEnvelope<ManualSamplePoolSyncJob>(
    {
      method: 'GET',
      url: `/api/v1/qc/sample-pools/sync-jobs/${encodeURIComponent(jobId)}`,
    },
    '获取样本同步任务失败',
  )
}

export type ManualSamplePoolRunRecordRef = {
  institute_id: string
  patient_id: string
  visit_id: string
}

export type ManualSamplePoolRunPayload = {
  department?: string
  doctor?: string
  model_code?: string
  top_p?: number
  temperature?: number
  max_tokens?: number
  max_parallel_records?: number
  sample_item_ids?: string[]
  record_refs?: ManualSamplePoolRunRecordRef[]
  selected_rule_ids?: string[]
  group_by_luxian_family?: boolean
  validation_mode?: string
  rule_set_key?: string
}

export async function runManualSamplePool(
  poolId: string,
  payload?: ManualSamplePoolRunPayload,
  options?: {
    timeout?: number
  },
) {
  const runtimePayload = (payload || {}) as ManualSamplePoolRunPayload & { record_ids?: unknown }
  if (
    Array.isArray(runtimePayload.record_ids) &&
    runtimePayload.record_ids.some((value) => String(value || '').trim())
  ) {
    throw new Error('record_ids 已停止用于新质控任务，请提交完整 record_refs 三坐标')
  }

  const normalizeUniqueValues = (values: string[] | undefined, fieldName: string) => {
    const normalized = (values || []).map((value) => String(value || '').trim()).filter(Boolean)
    if (new Set(normalized).size !== normalized.length) {
      throw new Error(`${fieldName} 存在重复值`)
    }
    return normalized
  }
  const sampleItemIds = normalizeUniqueValues(payload?.sample_item_ids, 'sample_item_ids')
  const selectedRuleIds = normalizeUniqueValues(payload?.selected_rule_ids, 'selected_rule_ids')
  const invalidLuxianRuleId = selectedRuleIds.find(
    (ruleId) => /^LX0609-/iu.test(ruleId) && !/^LX0609-\d{2}-\d{2}-\d{2}$/u.test(ruleId),
  )
  if (invalidLuxianRuleId) {
    throw new Error(`selected_rule_ids 包含无效的 LX0609 四段式编号：${invalidLuxianRuleId}`)
  }
  const recordRefs = (payload?.record_refs || []).map((item) => ({
    institute_id: String(item?.institute_id || '').trim(),
    patient_id: String(item?.patient_id || '').trim(),
    visit_id: String(item?.visit_id || '').trim(),
  }))
  if (recordRefs.some((item) => !item.institute_id || !item.patient_id || !item.visit_id)) {
    throw new Error('record_refs 必须包含完整的机构、患者和就诊三坐标')
  }
  const recordRefKeys = recordRefs.map((item) =>
    JSON.stringify([item.institute_id, item.patient_id, item.visit_id]),
  )
  if (new Set(recordRefKeys).size !== recordRefKeys.length) {
    throw new Error('record_refs 存在重复三坐标')
  }
  if (Boolean(sampleItemIds.length) !== Boolean(recordRefs.length)) {
    throw new Error('显式选择病历时必须同时提交 sample_item_ids 与 record_refs')
  }

  const data = {
    ...(payload?.department !== undefined ? { department: payload.department } : {}),
    ...(payload?.doctor !== undefined ? { doctor: payload.doctor } : {}),
    ...(payload?.model_code !== undefined ? { model_code: payload.model_code } : {}),
    ...(payload?.top_p !== undefined ? { top_p: payload.top_p } : {}),
    ...(payload?.temperature !== undefined ? { temperature: payload.temperature } : {}),
    ...(payload?.max_tokens !== undefined ? { max_tokens: payload.max_tokens } : {}),
    ...(payload?.max_parallel_records !== undefined
      ? { max_parallel_records: payload.max_parallel_records }
      : {}),
    ...(sampleItemIds.length ? { sample_item_ids: sampleItemIds } : {}),
    ...(recordRefs.length ? { record_refs: recordRefs } : {}),
    ...(payload?.selected_rule_ids !== undefined ? { selected_rule_ids: selectedRuleIds } : {}),
    ...(payload?.group_by_luxian_family !== undefined
      ? { group_by_luxian_family: payload.group_by_luxian_family }
      : {}),
    ...(payload?.validation_mode !== undefined ? { validation_mode: payload.validation_mode } : {}),
    ...(payload?.rule_set_key !== undefined ? { rule_set_key: payload.rule_set_key } : {}),
  }
  return requestEnvelope<ManualSamplePoolRunResult>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/run`,
      data,
      timeout: options?.timeout,
    },
    '创建客户样本验证任务失败',
  )
}

export async function getSheet2ExactReviewAcceptancePackage() {
  return requestEnvelope<Sheet2ExactReviewAcceptancePackage>(
    {
      method: 'GET',
      url: '/api/v1/qc/sample-pools/sheet2-exact-review/acceptance-package',
    },
    '获取 Sheet2 精确复核验收包失败',
  )
}

export async function listManualSampleValidationRuleSets() {
  return requestEnvelope<ManualSampleValidationRuleSetListResult>(
    {
      method: 'GET',
      url: '/api/v1/qc/sample-pools/rule-sets',
    },
    '获取样本验证规则集失败',
  )
}

export async function listLuxian0609CustomerRules() {
  return requestEnvelope<ManualLuxian0609RuleCatalogResult>(
    {
      method: 'GET',
      url: '/api/v1/qc/sichuan/rules',
      params: {
        rule_set_key: 'luxian_0609_qc_v1',
        _ts: Date.now(),
      },
    },
    '获取泸县0609质控点目录失败',
  )
}

export async function exportLuxian0609EvaluationReport(format: 'md' | 'csv' | 'json' = 'md') {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET',
      url: '/api/v1/qc/sample-pools/reports/luxian-0609',
      params: { format },
      responseType: 'blob',
    })
    return {
      success: true,
      data: response.data,
    }
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, '导出泸县0609质控点评估报告失败'),
      errorType: classifyRequestError(error),
    }
  }
}
