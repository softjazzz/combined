<template>
  <section v-if="rules.length" class="top-issue-rules mq-card" data-testid="top-issue-rules">
    <header class="top-issue-rules__head">
      <div>
        <h3>问题最多的质控点</h3>
        <p>按涉及的病历数排序，同一病历同一质控点只计一次。</p>
      </div>
      <button
        v-if="rules.length > COLLAPSED_COUNT"
        type="button"
        class="top-issue-rules__more"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起' : `查看全部 ${rules.length} 项` }}
      </button>
    </header>
    <ol class="top-issue-rules__list">
      <li v-for="rule in visibleRules" :key="rule.ruleCode" class="top-issue-rules__row">
        <span class="top-issue-rules__title" :title="rule.title">{{ rule.title }}</span>
        <span class="top-issue-rules__bar">
          <span :style="{ width: `${barWidth(rule.recordCount)}%` }" />
        </span>
        <span class="top-issue-rules__count">{{ rule.recordCount }} 份病历</span>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TopIssueRule } from '@/views/workstation-v4/semantic-rules/batchRecordReviewModel'

const props = defineProps<{
  rules: TopIssueRule[]
  totalRecords: number
}>()

const COLLAPSED_COUNT = 5
const expanded = ref(false)

const visibleRules = computed(() =>
  expanded.value ? props.rules : props.rules.slice(0, COLLAPSED_COUNT),
)

function barWidth(count: number) {
  const total = Math.max(1, props.totalRecords)
  return Math.max(4, Math.round((count / total) * 100))
}
</script>

<style scoped>
.top-issue-rules {
  display: grid;
  gap: var(--mq-space-3);
  padding: 20px 28px 22px;
}

.top-issue-rules__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--mq-space-4);
}

.top-issue-rules__head h3 {
  margin: 0;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-display);
  font-size: var(--mq-font-16);
  font-weight: 600;
}

.top-issue-rules__head p {
  margin: var(--mq-space-1) 0 0;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.top-issue-rules__more {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--mq-brand-600);
  font: inherit;
  font-size: var(--mq-font-13);
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
}

.top-issue-rules__list {
  display: grid;
  gap: var(--mq-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.top-issue-rules__row {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(120px, 3fr) 80px;
  gap: var(--mq-space-3);
  align-items: center;
}

.top-issue-rules__title {
  overflow: hidden;
  color: var(--mq-text-primary);
  font-size: var(--mq-font-13);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-issue-rules__bar {
  height: 8px;
  overflow: hidden;
  border-radius: var(--mq-radius-tag);
  background: var(--mq-bg-muted);
}

.top-issue-rules__bar span {
  display: block;
  height: 100%;
  border-radius: var(--mq-radius-tag);
  background: var(--mq-danger-icon);
}

.top-issue-rules__count {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
  font-variant-numeric: tabular-nums;
  text-align: right;
}

@media (max-width: 900px) {
  .top-issue-rules {
    padding: 18px 20px;
  }

  .top-issue-rules__row {
    grid-template-columns: minmax(0, 1fr) 72px;
  }

  .top-issue-rules__bar {
    display: none;
  }
}
</style>
