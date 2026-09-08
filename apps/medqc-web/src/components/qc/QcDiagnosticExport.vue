<template>
  <a-button
    size="small"
    :disabled="!items.length"
    @click="prepare"
  >
    诊断导包
  </a-button>
  <a-modal
    :open="open"
    title="诊断导包 · 本地预览"
    :width="800"
    :footer="null"
    @cancel="close"
  >
    <p class="diagnostic-export__notice">
      包含当前已加载结果、原因码分组、证据来源索引及机器可读数据；仅为结果摘要，不含完整病历或模型原始请求，不支持自动回放，仅供人工核查。
      本操作不请求新数据、不重跑质控、不自动发送。请复核脱敏后再发送。
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
  </a-modal>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
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

function close() {
  preview.value = ''
  confirmed.value = false
  error.value = ''
  open.value = false
}

function prepare() {
  close()
  if (!props.items.length) return
  open.value = true
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
onBeforeUnmount(close)
</script>

<style scoped>
.diagnostic-export__notice {
  margin: 12px 0;
  color: var(--workstation-text-secondary, #64748b);
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
  color: var(--workstation-text-primary, #1d1d1f);
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
</style>
