<template>
  <a-button
    class="diagnostic-export__trigger"
    size="small"
    :disabled="!items.length"
    @click="prepare"
  >
    <FileArchive :size="15" />
    质控诊断包
  </a-button>
  <a-modal
    :open="open"
    title="质控诊断包"
    :width="800"
    :footer="null"
    @cancel="close"
  >
    <p class="diagnostic-export__notice">
      包含当前已加载结果、原因码分组、证据来源索引及机器可读数据；仅为结果摘要，不含完整病历或模型原始请求，不支持自动回放，仅供人工核查。
      摘要导出不请求新数据、不重跑质控、不自动发送。请复核脱敏后再发送。
    </p>
    <a-alert
      v-if="error"
      type="warning"
      :message="error"
      show-icon
    />
    <template v-if="preview">
      <pre
        class="diagnostic-export__preview"
        aria-label="诊断包文本预览"
      >{{ preview }}</pre>
      <a-checkbox v-model:checked="confirmed">
        我已复核以上内容的脱敏情况，确认下载此预览对应的文件
      </a-checkbox>
    </template>
    <div class="diagnostic-export__actions">
      <a-button @click="close">
        取消
      </a-button>
      <a-button
        type="primary"
        :disabled="!preview || !confirmed"
        @click="download"
      >
        下载诊断包
      </a-button>
    </div>
    <section class="diagnostic-export__capture">
      <h3>采集执行排障包</h3>
      <p class="diagnostic-export__notice">
        将重新执行本次病历质控并更新结果。包内包含必要医疗正文及模型输入输出，去除访问凭证，但不能保证匿名。
        下载后仍须人工复核，仅保存到本机，不自动发送。关闭窗口不终止服务器任务。
      </p>
      <a-button
        :disabled="!selection || captureAttempted || checkingCapture || restorationBlocked"
        :loading="starting || checkingCapture"
        @click="startCapture"
      >
        重新质控并采集排障包
      </a-button>
      <p v-if="!selection">
        缺少任务或病历身份信息，暂不能采集。
      </p>
      <p v-if="starting || captureStatus?.state === 'running'">
        正在执行并采集，请稍候。
      </p>
      <a-alert
        v-if="captureError"
        type="warning"
        :message="captureError"
        show-icon
      />
      <template v-if="captureStatus?.state === 'ready'">
        <p>
          {{
            captureStatus.capture_completeness === 'complete'
              ? '采集完整'
              : '采集不完整，请核对缺失项'
          }}
        </p>
        <p v-if="captureStatus.missing_components?.length">
          缺失项：{{ captureStatus.missing_components.join('、') }}
        </p>
        <p v-if="captureStatus.included?.length">
          包含：{{ captureStatus.included.join('、') }}
        </p>
        <p v-if="captureStatus.notice">
          {{ captureStatus.notice }}
        </p>
        <a-checkbox v-model:checked="captureConfirmed">
          我知悉包内可能包含敏感医疗信息，确认下载并在分享前人工复核
        </a-checkbox>
        <div class="diagnostic-export__actions">
          <a-button
            :disabled="!captureConfirmed || downloading"
            :loading="downloading"
            @click="downloadCapture"
          >
            下载执行排障包
          </a-button>
        </div>
      </template>
    </section>
  </a-modal>
</template>

<script setup lang="ts">
import { FileArchive } from 'lucide-vue-next'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { diagnosticCaptureFilename } from './diagnosticCaptureFilename'
import {
  startDiagnosticCapture,
  getDiagnosticCapture,
  downloadDiagnosticCapture,
  type DiagnosticSelection,
  type DiagnosticCaptureStatus,
} from '@/services/qc-diagnostics-service'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'
import {
  buildQcResultDebugText,
  type QcResultDebugContext,
} from '@/views/workstation-v4/customer-sample-validation/qcResultDebugExport'
import type { SingleRecordQcResultItem } from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'

const props = defineProps<{ items: SingleRecordQcResultItem[]; context?: QcResultDebugContext }>()
const open = ref(false)
const confirmed = ref(false)
const error = ref('')
const preview = ref('')
const MAX_ITEMS = 200
const MAX_BYTES = 2 * 1024 * 1024
const starting = ref(false)
const captureAttempted = ref(false)
const checkingCapture = ref(false)
const restorationBlocked = ref(false)
const downloading = ref(false)
const captureJobId = ref('')
const captureStatus = ref<DiagnosticCaptureStatus>()
const captureConfirmed = ref(false)
const captureError = ref('')
let generation = 0
let pollGeneration = 0
let timer: ReturnType<typeof setTimeout> | undefined
const selection = computed<DiagnosticSelection | undefined>(() => {
  const c = props.context
  if (!c?.jobId || !c.recordRef || !c.instituteId || !c.patientId || !c.visitId) return
  return {
    job_id: c.jobId,
    record_ref: c.recordRef,
    institute_id: c.instituteId,
    patient_id: c.patientId,
    visit_id: c.visitId,
  }
})

function stopPolling() {
  pollGeneration++
  clearTimeout(timer)
}

async function pollCapture() {
  if (!open.value || !captureJobId.value) return
  const current = pollGeneration
  const jobId = captureJobId.value
  try {
    const status = await getDiagnosticCapture(jobId)
    if (current !== pollGeneration || !open.value) return
    captureStatus.value = status
    captureError.value =
      status.state === 'failed' || status.state === 'unavailable'
        ? `排障包采集失败或不可用${status.error_code ? `（${status.error_code}）` : ''}。请检查后台日志。`
        : ''
    if (status.state === 'running') timer = setTimeout(pollCapture, 3000)
  } catch {
    if (current !== pollGeneration || !open.value) return
    captureError.value = '暂时无法读取采集状态，将自动重试。'
    timer = setTimeout(pollCapture, 3000)
  }
}

async function startCapture() {
  if (
    !selection.value ||
    captureAttempted.value ||
    checkingCapture.value ||
    restorationBlocked.value
  )
    return
  const current = generation
  captureAttempted.value = true
  starting.value = true
  captureError.value = ''
  try {
    const result = await startDiagnosticCapture(selection.value)
    if (current !== generation) return
    captureJobId.value = result.job_id
    captureStatus.value = { state: 'running' }
    void pollCapture()
  } catch {
    if (current === generation)
      captureError.value = '采集启动请求失败，任务状态可能不确定。请先检查任务列表，避免重复执行。'
  } finally {
    if (current === generation) starting.value = false
  }
}

async function restoreCapture() {
  if (!selection.value || captureJobId.value || captureAttempted.value) return
  const current = pollGeneration
  const jobId = selection.value.job_id
  checkingCapture.value = true
  try {
    const status = await getDiagnosticCapture(jobId)
    if (current !== pollGeneration || !open.value) return
    if (status.state === 'unavailable') return
    captureJobId.value = jobId
    captureAttempted.value = true
    captureStatus.value = status
    if (status.state === 'running') timer = setTimeout(pollCapture, 3000)
    if (status.state === 'failed') captureError.value = '该任务的排障包采集失败，请检查后台日志。'
  } catch (cause) {
    if (current !== pollGeneration || !open.value) return
    const status = (cause as { response?: { status?: number } })?.response?.status
    if (status !== 404) {
      captureError.value = '无法确认已有采集任务，请关闭后重试。'
      restorationBlocked.value = true
    }
  } finally {
    if (current === pollGeneration) checkingCapture.value = false
  }
}

async function downloadCapture() {
  if (!captureConfirmed.value || captureStatus.value?.state !== 'ready' || downloading.value) return
  const current = pollGeneration
  downloading.value = true
  try {
    const blob = await downloadDiagnosticCapture(captureJobId.value)
    if (current === pollGeneration && open.value)
      downloadBlob(blob, diagnosticCaptureFilename(props.context, captureJobId.value))
  } catch {
    if (current === pollGeneration) captureError.value = '下载失败，请检查网络及浏览器下载权限。'
  } finally {
    if (current === pollGeneration) downloading.value = false
  }
}

function close() {
  stopPolling()
  checkingCapture.value = false
  restorationBlocked.value = false
  captureConfirmed.value = false
  downloading.value = false
  preview.value = ''
  confirmed.value = false
  error.value = ''
  open.value = false
}

function prepare() {
  close()
  if (!props.items.length) return
  open.value = true
  if (captureJobId.value) void pollCapture()
  else void restoreCapture()
  if (props.items.length > MAX_ITEMS) {
    error.value = '当前结果超过 200 条，请缩小结果范围后再导出。'
    return
  }
  try {
    const snapshot = buildQcResultDebugText(props.items, props.context, { diagnosticPackage: true })
    if (new Blob([snapshot]).size > MAX_BYTES) {
      error.value = '诊断内容超过 2 MiB，请缩小结果范围后再导出。'
      return
    }
    preview.value = snapshot
  } catch {
    error.value = '无法生成诊断包，请刷新结果后重试。'
  }
}

function download() {
  if (!preview.value || !confirmed.value) return
  try {
    // 下载已复核的同一份快照，不再次脱敏生成临时别名。
    downloadBlob(
      new Blob([preview.value], { type: 'text/markdown;charset=utf-8' }),
      'qc-diagnostic.md',
    )
  } catch {
    error.value = '下载失败，请检查浏览器下载权限后重试。'
  }
}

watch(() => [props.items, props.context], close, { deep: true, flush: 'sync' })
watch(
  () => JSON.stringify(selection.value),
  () => {
    close()
    generation++
    starting.value = false
    captureAttempted.value = false
    captureJobId.value = ''
    captureStatus.value = undefined
    captureError.value = ''
  },
  { flush: 'sync' },
)
onBeforeUnmount(() => {
  generation++
  close()
})
</script>

<style scoped>
.diagnostic-export__trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding-inline: 11px;
  border-color: #d7e2ef;
  border-radius: 8px;
  color: #35516f;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 1px 2px rgba(36, 65, 100, 0.04);
}
.diagnostic-export__trigger:hover,
.diagnostic-export__trigger:focus-visible {
  border-color: #8db8e8;
  color: #1768b0;
  background: #fff;
}
.diagnostic-export__notice {
  margin: 12px 0;
  color: var(--mq-diagnostic-help-text);
  font-size: 13px;
  line-height: 1.65;
}
.diagnostic-export__preview {
  max-height: 50vh;
  margin: 16px 0;
  padding: 14px;
  overflow: auto;
  background: #f5f5f7;
  border-radius: 8px;
  color: var(--mq-text-primary);
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.diagnostic-export__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
.diagnostic-export__capture {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}
</style>
