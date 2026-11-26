<template>
  <a-drawer
    :open="Boolean(jobId)"
    title="同步任务详情"
    width="min(720px, 100vw)"
    @close="emit('close')"
  >
    <a-alert
      v-if="error"
      type="error"
      :message="error"
      show-icon
    />
    <a-button
      :loading="loading"
      @click="load"
    >
      刷新详情
    </a-button>
    <template v-if="job">
      <p>任务 {{ job.job_id }} · {{ statusLabel(job.status) }}</p>
      <p>日期 {{ job.request?.start_date || '未返回' }} 至 {{ job.request?.end_date || '未返回' }} · 计划版本 {{ job.request?.plan_version ?? '未返回' }}</p>
      <p class="mq-card__desc">
        同步完成不代表质控材料已满足取材条件，不会自动启动质控。
      </p>
      <a-empty
        v-if="!job.units?.length"
        description="服务未返回日期单元"
      />
      <ul
        v-else
        class="sync-units"
      >
        <li
          v-for="(unit, index) in job.units"
          :key="unit.unit_id || index"
        >
          <strong>{{ unit.source_date || '日期未返回' }} · {{ unit.interface_name || '来源未返回' }}</strong>
          <p>{{ phaseLabel(unit.phase) }} · {{ statusLabel(unit.status) }} · 尝试 {{ unit.execution_attempts ?? '未返回' }} 次</p>
          <p v-if="unit.error?.code">
            失败原因 {{ unit.error.code }} · {{ unit.error.location || '位置未返回' }}
          </p>
          <p v-if="unit.result?.counts">
            {{ Object.entries(unit.result.counts).map(([k, v]) => `${k}: ${v}`).join(' · ') }}
          </p>
          <p v-if="unit.phase === 'publish'">
            待发布行数：{{ unit.result?.selected ?? '未返回' }}；实际写入行数：{{ unit.result?.written ?? '未返回' }}
          </p>
        </li>
      </ul>
      <a-button
        v-if="canRetry && ['failed', 'recovery_required'].includes(job.status)"
        :disabled="loading"
        @click="emit('retry', job)"
      >
        重试未完成单元
      </a-button>
    </template>
  </a-drawer>
</template>
<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { dataPipelinesApi, type IndependentSyncJob } from '@/api/dataPipelines'
const props = defineProps<{ jobId: string | null; canRetry: boolean }>()
const emit = defineEmits<{ close: []; retry: [job: IndependentSyncJob] }>()
function statusLabel(value?: string) {
  const labels: Record<string, string> = { queued: '排队中', running: '执行中', recovery_required: '等待恢复', succeeded: '已完成',
    completed_with_source_limitations: '完成（来源受限）', source_limited: '来源受限', failed: '执行失败', cancelled: '已取消' }
  return value ? labels[value] || `未识别状态（${value}）` : '状态未返回'
}
function phaseLabel(value?: string) {
  return value === 'extract' ? '抽取' : value === 'publish' ? '发布' : value || '阶段未返回'
}
const job = ref<IndependentSyncJob | null>(null), loading = ref(false), error = ref('')
let epoch = 0
async function load() {
  const id = props.jobId, ticket = ++epoch
  if (!id) return
  loading.value = true
  error.value = ''
  try {
    const value = await dataPipelinesApi.detail(id)
    if (ticket === epoch) job.value = value
  } catch {
    if (ticket === epoch) error.value = '详情读取失败；未重试任务，请刷新核对。'
  } finally {
    if (ticket === epoch) loading.value = false
  }
}
watch(() => props.jobId, () => { epoch++; job.value = null; error.value = ''; loading.value = false; void load() }, { immediate: true })
onUnmounted(() => { epoch++ })
</script>
<style scoped src="./styles/sync-job-detail.css"></style>
