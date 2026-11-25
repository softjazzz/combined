<template>
  <section
    class="analytics-drilldown"
    role="status"
    data-testid="analytics-drilldown-bar"
  >
    <div class="analytics-drilldown__content">
      <span class="analytics-drilldown__source">来自统计分析 · 质控点下钻</span>
      <div class="analytics-drilldown__title">
        <strong data-testid="analytics-drilldown-rule">{{ drilldown.ruleId || '全部质控点' }}</strong>
        <span v-if="drilldown.ruleName">{{ drilldown.ruleName }}</span>
      </div>
      <p
        class="analytics-drilldown__desc"
        data-testid="analytics-drilldown-desc"
      >
        下方列表只显示{{ scopeLabel }}中命中该质控点的病历<template v-if="total !== null">，共
          <b>{{ total }}</b> 份</template>。
      </p>
      <div class="analytics-drilldown__chips">
        <span class="analytics-drilldown__chip">{{ scopeLabel }}</span>
        <span
          v-if="drilldown.department"
          class="analytics-drilldown__chip"
        >{{ drilldown.department }}</span>
        <span
          v-if="resultStatusLabel"
          class="analytics-drilldown__chip"
          data-testid="analytics-drilldown-result-status"
          :title="resultStatusTitle"
        >结论状态 {{ resultStatusLabel }}</span>
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
        type="primary"
        @click="emit('back')"
      >
        ← 返回统计分析
      </a-button>
      <a-button @click="emit('clear')">
        查看全部病历
      </a-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  analyticsResultStatusLabel,
  analyticsScopeLabel,
  parseAnalyticsResultStatuses,
  type AnalyticsDrilldown,
} from '../../utils/analyticsDrilldown'

const props = withDefaults(defineProps<{ drilldown: AnalyticsDrilldown; total?: number | null }>(), {
  total: null,
})
const emit = defineEmits<{ back: []; clear: [] }>()

const scopeLabel = computed(() => analyticsScopeLabel(props.drilldown.scope))
const resultStatusLabel = computed(() => analyticsResultStatusLabel(props.drilldown.resultStatus))
const resultStatusTitle = computed(() => {
  const statuses = parseAnalyticsResultStatuses(props.drilldown.resultStatus)
  if (statuses.length <= 1) return undefined
  return statuses.map((item) => analyticsResultStatusLabel(item)).join('、')
})
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
  gap: 14px 24px;
  padding: 16px 20px;
  border: 1px solid rgba(10, 108, 255, 0.24);
  border-left: 4px solid #0a6cff;
  border-radius: 12px;
  background: rgba(10, 108, 255, 0.05);
  color: #1d1d1f;
}

.analytics-drilldown__content {
  display: flex;
  min-width: 0;
  flex: 1 1 360px;
  flex-direction: column;
  gap: 6px;
}

.analytics-drilldown__source {
  color: #0a6cff;
  font-size: 12px;
  font-weight: 600;
}

.analytics-drilldown__title {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 10px;
}

.analytics-drilldown__title strong {
  font-size: 18px;
  font-weight: 700;
}

.analytics-drilldown__title span {
  color: #334155;
  font-size: 15px;
  font-weight: 600;
}

.analytics-drilldown__desc {
  margin: 0;
  color: #475569;
  font-size: 13px;
}

.analytics-drilldown__desc b {
  color: #0a6cff;
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

.analytics-drilldown__actions {
  display: flex;
  flex: none;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
</style>
