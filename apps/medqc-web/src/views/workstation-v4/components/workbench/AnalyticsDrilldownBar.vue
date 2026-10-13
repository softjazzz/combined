<template>
  <section
    class="analytics-drilldown"
    role="status"
    data-testid="analytics-drilldown-bar"
  >
    <div class="analytics-drilldown__content">
      <div class="analytics-drilldown__heading">
        <strong>统计下钻</strong>
        <span>当前列表仅显示统计分析中命中该条件的病历</span>
      </div>
      <div class="analytics-drilldown__chips">
        <span
          v-if="drilldown.ruleId"
          class="analytics-drilldown__chip analytics-drilldown__chip--primary"
          data-testid="analytics-drilldown-rule"
        >规则 {{ drilldown.ruleId }}</span>
        <span class="analytics-drilldown__chip">{{ scopeLabel }}</span>
        <span
          v-if="drilldown.department"
          class="analytics-drilldown__chip"
        >{{ drilldown.department }}</span>
        <span
          v-if="periodText"
          class="analytics-drilldown__chip"
        >完成时间 {{ periodText }}</span>
        <span
          v-if="drilldown.jobId"
          class="analytics-drilldown__chip"
        >任务 {{ drilldown.jobId }}</span>
      </div>
    </div>
    <div class="analytics-drilldown__actions">
      <a-button
        size="small"
        @click="emit('back')"
      >
        返回统计
      </a-button>
      <a-button
        size="small"
        type="link"
        @click="emit('clear')"
      >
        清除下钻
      </a-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { analyticsScopeLabel, type AnalyticsDrilldown } from '../../utils/analyticsDrilldown'

const props = defineProps<{ drilldown: AnalyticsDrilldown }>()
const emit = defineEmits<{ back: []; clear: [] }>()

const scopeLabel = computed(() => analyticsScopeLabel(props.drilldown.scope))
const periodText = computed(() => {
  const { completedFrom, completedTo } = props.drilldown
  if (!completedFrom && !completedTo) return ''
  return `${completedFrom || '不限'} 至 ${completedTo || '不限'}`
})
</script>

<style scoped>
.analytics-drilldown {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px 20px;
  padding: 12px 16px;
  border: 1px solid rgba(10, 108, 255, 0.18);
  border-radius: 10px;
  background: rgba(10, 108, 255, 0.04);
  color: #1d1d1f;
}

.analytics-drilldown__content {
  display: flex;
  min-width: 0;
  flex: 1 1 320px;
  flex-direction: column;
  gap: 8px;
}

.analytics-drilldown__heading {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 10px;
}

.analytics-drilldown__heading strong {
  font-size: 14px;
  font-weight: 600;
}

.analytics-drilldown__heading span {
  color: #64748b;
  font-size: 12px;
}

.analytics-drilldown__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.analytics-drilldown__chip {
  padding: 2px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  font-size: 12px;
  white-space: nowrap;
}

.analytics-drilldown__chip--primary {
  border-color: rgba(10, 108, 255, 0.3);
  color: #0a6cff;
  font-weight: 600;
}

.analytics-drilldown__actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 4px;
}
</style>
