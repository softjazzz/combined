<template>
  <a-drawer
    :open="open"
    placement="right"
    width="min(1720px, 100vw)"
    :body-style="{ padding: 0 }"
    class="customer-record-result-drawer"
    @close="emit('close')"
  >
    <template #title>
      <div class="customer-record-result-title">
        <strong>病历质控结果</strong>
        <span>{{ focus?.label || '病历原文与质控结果对照' }}</span>
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
        :record-ref="authorizedRecordRef"
        :job-id="latestResult.job_id"
        :issues="[]"
        :single-record-items="latestResult.items"
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
import { ref, watch } from 'vue'
import {
  exportLatestLuxian0609RecordResult,
  getLatestLuxian0609RecordResult,
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
let activeRequestSequence = 0

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
.customer-record-result-title {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 16px;
}
.customer-record-result-title strong {
  font-size: 18px;
  color: #17233d;
}
.customer-record-result-title span {
  margin-left: auto;
  color: #7a8699;
  font-size: 13px;
  text-align: right;
}
.customer-record-result-title__export {
  min-height: 34px;
  padding: 0 13px;
  border: 1px solid rgba(0, 102, 204, 0.22);
  border-radius: 9px;
  background: rgba(0, 102, 204, 0.07);
  color: #0066cc;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}
.customer-record-result-title__export:disabled {
  cursor: wait;
  opacity: 0.58;
}
</style>
