<template>
  <section
    v-if="job?.status === 'failed'"
    class="batch-task-failure mq-soft"
    role="status"
    data-testid="batch-task-failure"
  >
    <h3>任务未完成，已保存的结果保留</h3>
    <p>已保存 {{ savedCount }} 条结果；失败项未形成临床结论。</p>
    <p v-if="materialFailure">
      {{ materialFailure.message }} <code>{{ materialFailure.code }}</code>
    </p>
    <p v-else-if="!job.failed_records?.length">后台未提供具体错误原因，请保留任务 ID 供排查。</p>
    <details v-if="job.failed_records?.length" open>
      <summary>失败原因（{{ job.failed_records.length }} 项）</summary>
      <ul>
        <li v-for="(failure, index) in job.failed_records" :key="index">
          <strong>{{ failure.rule_id || (failure.error_phase === 'material_capture' ? '病历资料准备' : '任务执行') }}</strong>
          <span>{{
            failure.reason_code === 'model_transport_error' ? '模型请求失败' : '执行未完成'
          }}</span>
          <code v-if="failure.reason_code">{{ failure.reason_code }}</code>
          <span v-if="failure.error_phase">阶段：{{ failure.error_phase }}</span>
          <span v-if="!failure.reason_code">未返回受控错误码</span>
        </li>
      </ul>
    </details>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SichuanBatchJob } from '../types'
const props = defineProps<{ job?: SichuanBatchJob | null }>()
const savedCount = computed(() => props.job?.items?.length ?? 0)
const materialFailure = computed(() => props.job?.summary?.material_failure)
</script>

<style scoped src="./BatchTaskFailureSummary.css"></style>
