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
        <div class="customer-record-result-title__context" :aria-label="recordContextAriaLabel">
          <span class="customer-record-result-title__context-label">当前病历</span>
          <span class="customer-record-result-title__context-details">
            <span class="customer-record-result-title__context-value">
              {{ focus?.label || '病历原文与质控结果对照' }}
            </span>
            <span v-if="hospitalizationTimeText" class="customer-record-result-title__context-time">
              {{ hospitalizationTimeText }}
            </span>
          </span>
          <span v-if="qcTimeText" class="customer-record-result-title__qc-time">
            {{ qcTimeText }}
          </span>
        </div>
        <QcDiagnosticExport
          v-if="open && latestResult && focus"
          :items="latestResult.items"
          :context="debugContext"
        />
        <button
          v-if="latestResult"
          type="button"
          class="customer-record-result-title__export"
          :disabled="exporting"
          @click="exportCurrentRecord"
        >
          {{ exporting ? '正在导出…' : '导出本病历 HTML' }}
        </button>
      </div>
    </template>

    <a-spin :spinning="loading">
      <QCRecordCompareWorkbench
        v-if="latestResult && focus.visitId"
        :visit-id="focus.visitId"
        :institute-id="focus.instituteId"
        :patient-id="focus.patientId"
        :admission-time="focus.admissionTime"
        :discharge-time="focus.dischargeTime"
        :record-ref="authorizedRecordRef"
        :job-id="latestResult.job_id"
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
import { message } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'
import { ShieldCheck, X } from 'lucide-vue-next'
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
  patientName?: string
  admissionTime?: string
  dischargeTime?: string
  label: string
}

const props = withDefaults(
  defineProps<{
    open: boolean
    focus: QCRecordResultFocus | null
    presentationMode?: 'flat' | 'grouped'
  }>(),
  { presentationMode: 'flat' },
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

const hospitalizationTimeText = computed(() => {
  const admissionTime = props.focus?.admissionTime
  const dischargeTime = props.focus?.dischargeTime
  if (admissionTime && dischargeTime) return `住院时间 ${admissionTime} → ${dischargeTime}`
  if (admissionTime) return `入院时间 ${admissionTime}`
  if (dischargeTime) return `出院时间 ${dischargeTime}`
  return ''
})

const recordContextAriaLabel = computed(() =>
  [
    `当前病历：${props.focus?.label || '病历原文与质控结果对照'}`,
    props.focus?.admissionTime ? `入院时间：${props.focus.admissionTime}` : '',
    props.focus?.dischargeTime ? `出院时间：${props.focus.dischargeTime}` : '',
  ]
    .filter(Boolean)
    .join('，'),
)

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
    void loadQcTime(result.data.job_id, requestSequence)
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
    } else if (job?.status === 'completed' && job.finished_at) {
      // 任务服务以无时区 UTC 保存时间；已有偏移量的值保持原有时区含义。
      const rawTime = job.finished_at.trim().replace(' ', 'T')
      const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(rawTime) ? rawTime : `${rawTime}Z`)
      qcTimeText.value = Number.isNaN(date.getTime())
        ? '质控完成时间未返回'
        : `质控完成时间：${date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}`
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
.customer-record-result-drawer :deep(.ant-drawer-close) {
  display: grid;
  width: 38px;
  height: 38px;
  margin: 0 12px 0 0;
  place-items: center;
  border: 1px solid rgba(0, 102, 204, 0.18);
  border-radius: 11px;
  background: #f3f8ff;
  color: #31597f;
  box-shadow: 0 1px 2px rgba(28, 76, 120, 0.08);
  transition: 180ms ease;
}

.customer-record-result-drawer :deep(.ant-drawer-close:focus-visible) {
  outline: 3px solid rgba(0, 102, 204, 0.24);
  outline-offset: 2px;
}

.customer-record-result-drawer :deep(.ant-drawer-close:hover) {
  border-color: rgba(0, 102, 204, 0.38);
  background: #e7f1ff;
  color: #005eb8;
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.14);
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
  border: 1px solid rgba(0, 102, 204, 0.14);
  border-radius: 10px;
  background: #edf5ff;
  color: #0066cc;
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
.customer-record-result-title__context {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 7px 12px 7px 10px;
  border: 1px solid rgba(0, 102, 204, 0.12);
  border-left: 3px solid #0066cc;
  border-radius: 11px;
  background: #f5f9ff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}
.customer-record-result-title__context-label {
  flex: none;
  padding: 2px 7px;
  border-radius: 6px;
  background: rgba(0, 102, 204, 0.11);
  color: #0066cc;
  font-size: 12px;
  font-weight: 650;
  line-height: 20px;
}
.customer-record-result-title__context-value {
  min-width: 0;
  overflow: hidden;
  color: rgba(29, 29, 31, 0.8);
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.customer-record-result-title__context-details {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.customer-record-result-title__context-time {
  flex: none;
  padding-left: 10px;
  border-left: 1px solid rgba(0, 102, 204, 0.14);
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 500;
  line-height: 20px;
  white-space: nowrap;
}
.customer-record-result-title__qc-time {
  margin-left: auto;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  line-height: 20px;
  white-space: nowrap;
}
.customer-record-result-title__export {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid rgba(0, 102, 204, 0.22);
  border-radius: 10px;
  background: #f7fbff;
  color: #0066cc;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  transition: 180ms ease;
}
.customer-record-result-title__export:hover:not(:disabled) {
  border-color: rgba(0, 102, 204, 0.38);
  background: #edf5ff;
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.1);
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
