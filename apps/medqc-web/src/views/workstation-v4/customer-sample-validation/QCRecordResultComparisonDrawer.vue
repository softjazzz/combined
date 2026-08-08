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
import { ref, watch } from 'vue'
import { getLatestLuxian0609RecordResult } from '@/services/sichuan-rule-workspace-service'
import QCRecordCompareWorkbench from '@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'
import type { SingleRecordQcResultPayload } from './single-record-result-model'

export interface QCRecordResultFocus {
  visitId: string
  instituteId: string
  patientId: string
  recordId: string
  recordRef?: string
  label: string
}

const props = defineProps<{
  open: boolean
  focus: QCRecordResultFocus | null
}>()

const emit = defineEmits<{
  (event: 'close'): void
}>()

const loading = ref(false)
const loadError = ref('')
const latestResult = ref<SingleRecordQcResultPayload | null>(null)
const authorizedRecordRef = ref('')

async function loadLatestResult() {
  const focus = props.focus
  latestResult.value = null
  authorizedRecordRef.value = ''
  loadError.value = ''
  if (!props.open || !focus?.instituteId || !focus.patientId || !focus.visitId) return

  loading.value = true
  try {
    const result = await getLatestLuxian0609RecordResult({
      instituteId: focus.instituteId,
      patientId: focus.patientId,
      visitId: focus.visitId,
    })
    if (!result.success || !result.data) {
      loadError.value = result.message || '这份病历暂无已保存质控结果，请先质控后查看'
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
  } finally {
    loading.value = false
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
</style>
