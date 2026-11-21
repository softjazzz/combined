<template>
  <a-drawer
    :open="open"
    placement="right"
    width="min(1720px, 100vw)"
    :body-style="{ padding: 0 }"
    class="customer-record-result-drawer"
    @close="emit('close')"
  >
    <template #closeIcon>
      <RecordViewCloseIcon label="关闭病历质控结果" />
    </template>
    <template #title>
      <div class="customer-record-result-title">
        <div class="customer-record-result-title__brand">
          <span class="customer-record-result-title__icon" aria-hidden="true">
            <ShieldCheck :size="18" />
          </span>
          <span class="customer-record-result-title__heading">
            <small>质控工作台</small>
            <strong>病历质控结果</strong>
          </span>
        </div>
        <MedicalRecordContextBanner
          :context="focus"
          :qc-time-text="qcTimeText || (latestResult && !historyView && focus?.listQcTime) || ''"
        />
        <div class="customer-record-result-title__actions">
          <QcDiagnosticExport
            v-if="open && latestResult && focus && !confirmedResultsOnly && !historyView"
            :items="latestResult.items"
            :context="debugContext"
          />
          <button
            v-if="latestResult && !confirmedResultsOnly && !historyView"
            type="button"
            class="customer-record-result-title__export"
            :disabled="exporting"
            @click="exportCurrentRecord"
          >
            {{ exporting ? '正在导出…' : '导出本病历 HTML' }}
          </button>
        </div>
      </div>
    </template>

    <HospitalLoading v-if="showLoading" label="正在读取质控结果" fill />
    <template v-if="!loading">
      <div
        v-if="historyView"
        v-show="!showLoading"
        class="result-history-nav mq-soft"
      >
        <strong>{{ latestResult && historyView.anchorJobId ? '上一次有效质控结果' : '历史质控结果' }}</strong>
        <span v-if="historyView.anchorJobId">最近一次资料准备失败</span>
        <button
          type="button"
          class="mq-btn"
          @click="loadResult()"
        >
          返回最近一次
        </button>
      </div>
      <section
        v-if="latestResult?.result_scope === 'targeted' && !latestResult.execution_status"
        v-show="!showLoading"
        role="status"
        class="customer-record-result-warning"
      >
        当前为定向质控结果，仅覆盖本次选择的 {{ latestResult.expected_rule_count }} 项。
      </section>
      <QCRecordCompareWorkbench
        v-if="latestResult && focus.visitId"
        v-show="!showLoading"
        :visit-id="focus.visitId"
        source-view="saved"
        lazy-result-documents
        :institute-id="focus.instituteId"
        :patient-id="focus.patientId"
        :admission-time="focus.admissionTime"
        :discharge-time="focus.dischargeTime"
        :record-ref="authorizedRecordRef"
        :job-id="latestResult.job_id"
        :feedback-available="!historyView && !latestResult.execution_status"
        :issues="[]"
        :single-record-items="latestResult.items"
        :debug-context="historyView ? undefined : debugContext"
        :presentation-mode="presentationMode"
      />
      <a-result
        v-else-if="loadError"
        v-show="!showLoading"
        status="warning"
        :title="loadError"
      >
        <template
          v-if="previousRequest"
          #extra
        >
          <button
            type="button"
            class="mq-btn mq-btn--primary"
            @click="loadResult(previousRequest)"
          >
            {{ previousRequest.anchorJobId ? '查看上一次有效结果' : '查找可查看的历史结果' }}
          </button>
        </template>
      </a-result>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import { useMinimumLoading } from '@/composables/useMinimumLoading'
import { message } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'
import { ShieldCheck } from 'lucide-vue-next'
import RecordViewCloseIcon from '../components/RecordViewCloseIcon.vue'
import MedicalRecordContextBanner from './MedicalRecordContextBanner.vue'
import QcDiagnosticExport from '@/components/qc/QcDiagnosticExport.vue'
import HospitalLoading from '@/components/qc/HospitalLoading.vue'
import {
  exportLatestLuxian0609RecordResult,
  getLatestLuxian0609RecordResult,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import QCRecordCompareWorkbench from '@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'
import {
  CAPTURE_FAILED_NOTICE,
  previousResultRequest,
  type PreviousResultRequest,
  type SingleRecordQcResultPayload,
} from './single-record-result-model'
import { formatQcCompletedAt } from '../components/qc/latestQcSummaryPresentation'
import { downloadBlob, normalizeBatchExportBlob } from './batchExport'

export interface QCRecordResultFocus {
  visitId: string
  instituteId: string
  patientId: string
  recordId: string
  recordRef?: string
  patientSex?: string
  patientAge?: number
  patientName?: string
  admissionTime?: string
  dischargeTime?: string
  listQcTime?: string
  previousResult?: PreviousResultRequest
  label: string
}

const { confirmedResultsOnly } = useQcResultVisibility()

const props = withDefaults(
  defineProps<{
    open: boolean
    focus: QCRecordResultFocus | null
    presentationMode?: 'flat' | 'grouped'
    loadJobMetadata?: boolean
  }>(),
  { presentationMode: 'flat', loadJobMetadata: true },
)

const emit = defineEmits<{
  (event: 'close'): void
}>()

const loading = ref(false)
const showLoading = useMinimumLoading(() => loading.value, () => props.open)
const exporting = ref(false)
const loadError = ref('')
const latestResult = ref<SingleRecordQcResultPayload | null>(null)
const previousRequest = ref<PreviousResultRequest>()
const historyView = ref<PreviousResultRequest>()
const authorizedRecordRef = ref('')
const qcTimeText = ref('')
let activeRequestSequence = 0

const debugContext = computed(() => {
  const result = latestResult.value
  const focus = props.focus
  if (!result || !focus) return undefined
  return {
    instituteId: focus.instituteId,
    patientId: focus.patientId,
    visitId: focus.visitId,
    recordId: focus.recordId,
    recordRef: result.record_ref,
    jobId: result.job_id,
    ruleSetKey: result.rule_set_key,
    ruleSetVersion: result.rule_set_version,
    resultSchemaVersion: result.schema_version,
    expectedRuleCount: result.expected_rule_count,
    resultRuleCount: result.result_rule_count,
    isComplete: result.is_complete,
    missingRuleIds: result.missing_rule_ids,
    conflictingRuleIds: result.conflicting_rule_ids,
    patientName: focus.patientName,
  }
})

async function exportCurrentRecord() {
  if (confirmedResultsOnly.value || historyView.value) return
  const focus = props.focus
  if (
    !latestResult.value ||
    !focus?.instituteId ||
    !focus.patientId ||
    !focus.visitId ||
    exporting.value
  )
    return
  exporting.value = true
  try {
    const response = await exportLatestLuxian0609RecordResult({
      instituteId: focus.instituteId,
      patientId: focus.patientId,
      visitId: focus.visitId,
    })
    if (!response.success || !response.data) {
      message.error(response.message || '导出单病历质控结果失败')
      return
    }
    const blob = await normalizeBatchExportBlob(response.data, 'html')
    if (confirmedResultsOnly.value) return
    downloadBlob(blob, '单病历质控结果.html')
    message.success('单病历质控结果已开始下载')
  } catch {
    message.error('导出单病历质控结果失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

async function loadResult(previous?: PreviousResultRequest) {
  const requestSequence = ++activeRequestSequence
  const focus = props.focus
  latestResult.value = null
  previousRequest.value = undefined
  historyView.value = previous
  qcTimeText.value = ''
  authorizedRecordRef.value = ''
  loadError.value = ''
  loading.value = false
  if (!props.open || !focus?.instituteId || !focus.patientId || !focus.visitId) return

  loading.value = true
  try {
    const identity = {
      instituteId: focus.instituteId,
      patientId: focus.patientId,
      visitId: focus.visitId,
    }
    const result = previous
      ? await getLatestLuxian0609RecordResult(identity, previous)
      : await getLatestLuxian0609RecordResult(identity)
    if (requestSequence !== activeRequestSequence) return
    if (!previous) previousRequest.value = previousResultRequest(result)
    if (!result.success || !result.data) {
      if (previous && result.status === 404) loadError.value = '暂无可查看的历史质控结果'
      else loadError.value = result.message || '质控结果读取失败，请稍后重试'
      return
    }
    if (result.data.state === 'technical_error') {
      loadError.value = previousRequest.value?.anchorJobId
        ? CAPTURE_FAILED_NOTICE : '质控结果读取异常，请联系管理员核对结果交付'
      return
    }
    if (result.data.state !== 'ready') {
      loadError.value = previous ? '暂无可查看的历史质控结果' : '这份病历暂无已保存质控结果，请先质控后查看'
      return
    }
    if (previous && (result.data.result_view !== 'previous_valid' || result.data.read_only !== true
        || !result.data.job_id || result.data.job_id === previous.anchorJobId || !result.data.items?.length)) {
      loadError.value = '历史结果版本无法确认，请返回最近一次重新查看'
      return
    }
    authorizedRecordRef.value = String(result.data.record_ref || '').trim()
    if (!authorizedRecordRef.value) {
      loadError.value = '该质控任务缺少当前病历的服务端授权引用，已停止展示'
      return
    }
    latestResult.value = result.data
    if (previous) {
      const completed = formatQcCompletedAt(result.data.completed_at)
      qcTimeText.value = completed === '—' ? '历史结果结束时间未返回' : `历史结果结束时间 ${completed}`
      return
    }
    // V5列表已展示病例范围内的完成时间，不额外请求任务创建者权限接口。
    if (props.loadJobMetadata) void loadQcTime(result.data.job_id, requestSequence)
  } catch {
    if (requestSequence === activeRequestSequence) {
      loadError.value = '质控结果读取失败，请稍后重试'
    }
  } finally {
    if (requestSequence === activeRequestSequence) {
      loading.value = false
    }
  }
}

async function loadQcTime(jobId: string, requestSequence: number) {
  if (!jobId) return
  try {
    const response = await getSichuanWorkspaceBatchJob(jobId)
    if (requestSequence !== activeRequestSequence) return
    const job = response.success ? response.data : undefined
    if (job?.status === 'running' || job?.status === 'queued') {
      qcTimeText.value = '质控进行中'
    } else if (job?.finished_at && (job.status === 'completed' || latestResult.value?.execution_status)) {
      // 任务服务以无时区 UTC 保存时间；已有偏移量的值保持原有时区含义。
      const rawTime = job.finished_at.trim().replace(' ', 'T')
      const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(rawTime) ? rawTime : `${rawTime}Z`)
      qcTimeText.value = Number.isNaN(date.getTime())
        ? '质控完成时间未返回'
        : `${latestResult.value?.execution_status ? '质控结束时间' : '质控完成时间'}：${date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}`
    } else {
      qcTimeText.value = '质控完成时间未返回'
    }
  } catch {
    if (requestSequence === activeRequestSequence) qcTimeText.value = '质控时间暂不可用'
  }
}

watch(
  () => [
    props.open,
    props.focus?.instituteId,
    props.focus?.patientId,
    props.focus?.visitId,
    props.focus?.recordId,
    props.focus?.recordRef,
    props.focus?.previousResult,
  ],
  () => void loadResult(props.focus?.previousResult),
  { immediate: true },
)
</script>

<style scoped>
@import '../styles/qc-result-view-apple.css';
.result-history-nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin: 8px 16px;
  padding: 8px 16px;
}
.result-history-nav button { margin-inline-start: auto; }
.customer-record-result-warning {
  margin: 12px 16px;
  padding: 12px 16px;
  color: #92400e;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 12px;
  overflow-wrap: anywhere;
}
:global(.customer-record-result-drawer .ant-drawer-title) {
  min-width: 0;
}

:global(.customer-record-result-drawer .ant-drawer-close) {
  order: 1;
  flex: 0 0 38px;
  align-self: flex-start;
  margin: 0;
  margin-inline-start: 12px;
}

.customer-record-result-title {
  width: 100%;
  display: grid;
  grid-template-columns: 180px minmax(280px, 1fr) auto;
  align-items: center;
  gap: 18px;
}

.customer-record-result-title__brand {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.customer-record-result-title__icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border: 1px solid rgba(10, 108, 255, 0.14);
  border-radius: 10px;
  background: #edf5ff;
  color: #0a6cff;
}

.customer-record-result-title__heading {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.customer-record-result-title__heading small {
  color: rgba(29, 29, 31, 0.42);
  font-size: 10px;
  line-height: 14px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.customer-record-result-title__heading strong {
  color: #1d1d1f;
  font-size: 16px;
  line-height: 21px;
  font-weight: 700;
  white-space: nowrap;
}
.customer-record-result-title__export {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid rgba(10, 108, 255, 0.22);
  border-radius: 10px;
  background: #f7fbff;
  color: #0a6cff;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  transition: 180ms ease;
}
.customer-record-result-title__export:hover:not(:disabled) {
  border-color: rgba(10, 108, 255, 0.38);
  background: #edf5ff;
  box-shadow: 0 4px 12px rgba(10, 108, 255, 0.1);
  transform: translateY(-1px);
}
.customer-record-result-title__export:disabled {
  cursor: wait;
  opacity: 0.58;
}

@media (max-width: 900px) {
  .customer-record-result-title {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 10px;
  }

  .customer-record-result-title__brand {
    grid-column: 1 / -1;
  }

  .customer-record-result-title__context {
    grid-column: 1 / -1;
    grid-row: 2;
  }
}
</style>
