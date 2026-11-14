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
    <p v-else-if="job.summary?.execution_error">
      {{ errorLabel(job.summary.execution_error.error_category) }}；{{ retryLabel(job.summary.execution_error.retryable) }}
    </p>
    <p v-else-if="!job.failed_records?.length">后台未提供具体错误原因，请保留任务 ID 供排查。</p>
    <details v-if="job.failed_records?.length" open>
      <summary>失败原因（{{ job.failed_records.length }} 项）</summary>
      <ul>
        <li v-for="(failure, index) in job.failed_records" :key="index">
          <strong>{{ failure.rule_id || (failure.error_phase === 'material_capture' ? '病历资料准备' : '任务执行') }}</strong>
          <span>{{
            failure.error_category ? errorLabel(failure.error_category) : failure.reason_code === 'model_transport_error' ? '模型请求失败' : '执行未完成'
          }}</span>
          <span>{{ retryLabel(failure.retryable) }}</span>
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
const errorLabels: Record<string, string> = {
  model_timeout: '模型请求超时', model_connection: '模型连接失败',
  model_rate_limit: '模型服务限流', model_unavailable: '模型服务暂不可用',
  model_request: '模型请求被拒绝', model_configuration: '模型配置不可用',
  model_output: '模型响应不符合合同', privacy_guard: '隐私保护检查未通过',
  model_context: '模型输入超出上下文限制', material: '病历资料准备失败',
}
function errorLabel(category?: string) {
  return category && Object.prototype.hasOwnProperty.call(errorLabels, category) ? errorLabels[category] : '执行未完成'
}
function retryLabel(retryable?: boolean) {
  return retryable === true ? '具备自动重试条件，是否执行以任务计划为准'
    : retryable === false ? '不会自动重试，处理原因后可另行发起新尝试'
      : '自动重试属性未确认'
}
</script>

<style scoped src="./BatchTaskFailureSummary.css"></style>
