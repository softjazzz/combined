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
      <span
        class="customer-record-result-drawer__close-icon"
        title="关闭病历质控结果"
        aria-hidden="true"
      >
        <X :size="20" :stroke-width="2.35" />
      </span>
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
        <MedicalRecordContextBanner :context="focus" :qc-time-text="qcTimeText" />
        <div class="customer-record-result-title__actions">
          <QcDiagnosticExport
            v-if="open && latestResult && focus && !confirmedResultsOnly"
            :items="latestResult.items"
            :context="debugContext"
          />
          <button
            v-if="latestResult && !confirmedResultsOnly"
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

    <a-spin :spinning="loading">
      <section
        v-if="latestResult?.execution_status === 'partial_failed' || latestResult?.execution_status === 'failed'"
        role="alert"
        class="customer-record-result-warning"
        data-testid="record-result-partial-failure"
      >
        <strong>本次质控未全部完成</strong>
        <p>已保留 {{ latestResult.result_rule_count }} 项有效结果；{{ latestResult.failed_rule_count }} 项执行失败，未形成质控结论。</p>
        <p v-if="latestResult.failed_rule_ids?.length">
          失败项：{{ latestResult.failed_rule_ids.join('、') }}
        </p>
      </section>
      <section
        v-else-if="latestResult?.result_scope === 'targeted'"
        role="status"
        class="customer-record-result-warning"
      >
        当前为定向质控结果，仅覆盖本次选择的 {{ latestResult.expected_rule_count }} 项。
      </section>
      <QCRecordCompareWorkbench
        v-if="latestResult && focus.visitId"
        :visit-id="focus.visitId"
        source-view="current"
        :institute-id="focus.instituteId"
        :patient-id="focus.patientId"
        :admission-time="focus.admissionTime"
        :discharge-time="focus.dischargeTime"
        :record-ref="authorizedRecordRef"
        :job-id="latestResult.job_id"
        :feedback-available="!latestResult.execution_status"
        :issues="[]"
        :single-record-items="latestResult.items"
        :debug-context="debugContext"
        :presentation-mode="presentationMode"
      />
      <a-result
        v-else-if="loadError"
        status="warning"
        :title="loadError"
        sub-title="未打开批量结果页，也不会回退到其他病历的结果。"
      />
    </a-spin>
  </a-drawer>
</template>

<script setup lang="ts">
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import { message } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'
import { ShieldCheck, X } from 'lucide-vue-next'
import MedicalRecordContextBanner from './MedicalRecordContextBanner.vue'
import QcDiagnosticExport from '@/components/qc/QcDiagnosticExport.vue'
import {
  exportLatestLuxian0609RecordResult,
  getLatestLuxian0609RecordResult,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import QCRecordCompareWorkbench from '@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'
import type { SingleRecordQcResultPayload } from './single-record-result-model'
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
const exporting = ref(false)
const loadError = ref('')
const latestResult = ref<SingleRecordQcResultPayload | null>(null)
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
  if (confirmedResultsOnly.value) return
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

async function loadLatestResult() {
  const requestSequence = ++activeRequestSequence
  const focus = props.focus
  latestResult.value = null
  qcTimeText.value = ''
  authorizedRecordRef.value = ''
  loadError.value = ''
  loading.value = false
  if (!props.open || !focus?.instituteId || !focus.patientId || !focus.visitId) return

  loading.value = true
  try {
    const result = await getLatestLuxian0609RecordResult({
      instituteId: focus.instituteId,
      patientId: focus.patientId,
      visitId: focus.visitId,
    })
    if (requestSequence !== activeRequestSequence) return
    if (!result.success || !result.data) {
      loadError.value = result.message || '这份病历暂无已保存质控结果，请先质控后查看'
      return
    }
    if (result.data.state === 'technical_error') {
      loadError.value = '质控结果读取异常，请联系管理员核对结果交付'
      return
    }
    if (result.data.state !== 'ready') {
      loadError.value = '这份病历暂无已保存质控结果，请先质控后查看'
      return
    }
    authorizedRecordRef.value = String(result.data.record_ref || '').trim()
    if (!authorizedRecordRef.value) {
      loadError.value = '该质控任务缺少当前病历的服务端授权引用，已停止展示'
      return
    }
    latestResult.value = result.data
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
  ],
  () => void loadLatestResult(),
  { immediate: true },
)
</script>

<style scoped>
@import '../styles/qc-result-view-apple.css';
.customer-record-result-warning {
  margin: 12px 16px;
  padding: 12px 16px;
  color: #92400e;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 12px;
  overflow-wrap: anywhere;
}
.customer-record-result-warning p {
  margin: 4px 0 0;
}
.customer-record-result-drawer :deep(.ant-drawer-close) {
  display: grid;
  width: 38px;
  height: 38px;
  margin: 0 12px 0 0;
  place-items: center;
  border: 1px solid rgba(10, 108, 255, 0.18);
  border-radius: 11px;
  background: #f3f8ff;
  color: #31597f;
  box-shadow: 0 1px 2px rgba(28, 76, 120, 0.08);
  transition: 180ms ease;
}

.customer-record-result-drawer :deep(.ant-drawer-close:focus-visible) {
  outline: 3px solid rgba(10, 108, 255, 0.24);
  outline-offset: 2px;
}

.customer-record-result-drawer :deep(.ant-drawer-close:hover) {
  border-color: rgba(10, 108, 255, 0.38);
  background: #e7f1ff;
  color: #005eb8;
  box-shadow: 0 4px 12px rgba(10, 108, 255, 0.14);
  transform: translateY(-1px);
}

.customer-record-result-drawer__close-icon {
  display: grid;
  place-items: center;
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
