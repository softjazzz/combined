<template>
  <details
    v-if="comparison"
    data-testid="regression-comparison"
  >
    <summary>查看事实、证据与调用统计</summary>
    <p class="rv-muted">
      基线运行：{{ comparison.baseline_run_id || '未记录' }}
    </p>
    <p v-if="!comparison.baseline">
      保存基线缺失或不可读取，不能确认无回归。
    </p>
    <p v-else>
      {{ comparison.changed_fields.length ? '以下内容发生变化' : '状态、原因、公开事实、证据和文案一致' }}
    </p>
    <div
      v-for="change in changes"
      :key="change.key"
    >
      <b>{{ change.label }}</b>
      <p>基线：{{ change.before }}</p>
      <p>本次：{{ change.after }}</p>
    </div>
    <table class="mq-table">
      <caption>整任务统计（共享抽取，不分摊到单条规则）</caption>
      <thead><tr><th>指标</th><th>基线</th><th>本次</th><th>增减</th></tr></thead>
      <tbody>
        <tr
          v-for="metric in metrics"
          :key="metric.key"
        >
          <td>{{ metric.label }}</td>
          <td>{{ comparison.metrics.baseline[metric.key] ?? '未记录' }}</td>
          <td>{{ comparison.metrics.current[metric.key] ?? '未记录' }}</td>
          <td>{{ comparison.metrics.delta?.[metric.key] ?? '不可直接比较' }}</td>
        </tr>
      </tbody>
    </table>
    <p>基线 {{ comparison.metrics.baseline_scope.record_count }} 例 / {{ comparison.metrics.baseline_scope.rule_ids.length }} 条规则；本次 {{ comparison.metrics.current_scope.record_count }} 例 / {{ comparison.metrics.current_scope.rule_ids.length }} 条规则。</p>
    <p class="rv-muted">
      {{ comparison.metrics.reason }}
    </p>
  </details>
  <span
    v-else
    class="rv-muted"
  >尚无事实与统计对照</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ComparisonRow, RegressionMetrics } from '@/services/rule-validation-service'

const props = defineProps<{ row: ComparisonRow }>()
const comparison = computed(() => props.row.regression_comparison)
const labels: Record<string, string> = {
  status: '状态', reason_code: '原因', customer_display_facts: '判定事实', criterion_results: '逐项事实',
  findings: '判定说明', evidence: '证据', customer_conclusion: '结论', conclusion: '结论别名',
  customer_suggestion: '建议', suggestion: '建议别名',
}
const display = (value: unknown) => value == null ? '未记录' : typeof value === 'string' ? value : JSON.stringify(value)
const changes = computed(() => (comparison.value?.changed_fields ?? []).map((key) => ({
  key, label: labels[key] ?? key,
  before: display((comparison.value?.baseline as Record<string, unknown> | null)?.[key]),
  after: display((props.row.result as Record<string, unknown> | undefined)?.[key]),
})))
const metrics: { key: keyof RegressionMetrics; label: string }[] = [
  { key: 'llm_calls', label: '模型调用次数' }, { key: 'tokens', label: 'Token' },
  { key: 'elapsed_seconds', label: '任务耗时（秒）' },
]
</script>

<style scoped>
details { min-width: 250px; max-width: 620px; }
summary { cursor: pointer; color: var(--mq-brand-600); }
p { white-space: pre-wrap; overflow-wrap: anywhere; }
caption { text-align: left; color: var(--mq-text-secondary); }
</style>
