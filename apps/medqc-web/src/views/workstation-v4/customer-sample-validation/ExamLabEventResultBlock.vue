<template>
  <section
    class="exam-event-block"
    data-testid="exam-event-facts"
  >
    <header class="exam-event-header">
      <h4>逐次检查核对</h4>
      <span>按报告时间展示适用性与分析记录</span>
    </header>
    <div
      class="exam-event-summary"
      data-testid="exam-event-summary"
    >
      <span>{{ presentation.totalLabel }}</span>
      <span>{{ presentation.positiveLabel }}</span>
      <span class="is-danger">{{ presentation.issueLabel }}</span>
    </div>
    <!-- 明细行只做展示：当前数据没有「每次检查 → 具体文书」的对应关系，不提供逐次跳转 -->
    <div class="exam-event-list">
      <article
        v-for="event in attentionEvents"
        :key="event.eventPosition"
        class="exam-event-row"
        data-testid="exam-event-row"
      >
        <div class="exam-event-row-head">
          <span class="exam-event-position">第 {{ event.eventPosition }} 次</span>
          <time>{{ event.reportTime }}</time>
          <span
            class="exam-event-status"
            :class="`is-${event.tone}`"
          >{{ event.statusLabel }}</span>
        </div>
        <p>{{ event.description }}</p>
      </article>
    </div>
    <details
      v-if="otherEvents.length"
      class="exam-event-more"
      data-testid="exam-event-more"
    >
      <summary>另有 {{ otherEvents.length }} 次：{{ otherSummary }}</summary>
      <div class="exam-event-list">
        <article
          v-for="event in otherEvents"
          :key="event.eventPosition"
          class="exam-event-row"
          data-testid="exam-event-row"
        >
          <div class="exam-event-row-head">
            <span class="exam-event-position">第 {{ event.eventPosition }} 次</span>
            <time>{{ event.reportTime }}</time>
            <span
              class="exam-event-status"
              :class="`is-${event.tone}`"
            >{{ event.statusLabel }}</span>
          </div>
          <p>{{ event.description }}</p>
        </article>
      </div>
    </details>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ExamLabEventPresentation } from './examLabEventPresentation'

const props = defineProps<{
  presentation: ExamLabEventPresentation
}>()

// 需要质控员处理的次数（未记录/未完成分析、待核实）默认展示；
// 已记录、已完成、不适用的次数收进折叠区，内容与顺序不变，只是默认不展开。
// 若没有需处理的次数，则全部直接展示。
const isAttention = (tone: string) => tone === 'danger' || tone === 'warning'
const hasAttention = computed(() =>
  props.presentation.events.some((event) => isAttention(event.tone)),
)
const attentionEvents = computed(() =>
  hasAttention.value
    ? props.presentation.events.filter((event) => isAttention(event.tone))
    : props.presentation.events,
)
const otherEvents = computed(() =>
  hasAttention.value ? props.presentation.events.filter((event) => !isAttention(event.tone)) : [],
)
const otherSummary = computed(() => {
  const counts = new Map<string, number>()
  for (const event of otherEvents.value) {
    counts.set(event.statusLabel, (counts.get(event.statusLabel) || 0) + 1)
  }
  return [...counts.entries()].map(([label, count]) => `${label} ${count}`).join(' · ')
})
</script>

<style scoped>
.exam-event-block {
  margin: 0 14px 12px;
  overflow: hidden;
  border: 1px solid rgba(99, 119, 145, 0.12);
  border-radius: 10px;
  background: #f8fafc;
}

.exam-event-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(18, 38, 63, 0.07);
  background: rgba(255, 255, 255, 0.88);
}

.exam-event-header h4 {
  margin: 0;
  color: #344256;
  font-size: 13px;
  font-weight: 500;
  line-height: 18px;
}

.exam-event-header > span {
  color: rgba(20, 42, 68, 0.5);
  font-size: 12px;
  line-height: 17px;
}

.exam-event-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 0;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.065);
}

.exam-event-summary span {
  color: #4a5468;
  font-size: 12px;
  font-weight: 400;
  line-height: 18px;
}

.exam-event-summary span + span::before {
  margin: 0 6px;
  color: #c4ccd7;
  content: '·';
}

.exam-event-summary span.is-danger {
  color: #c62828;
  font-weight: 500;
}

.exam-event-more {
  border-top: 1px solid rgba(0, 0, 0, 0.055);
}

.exam-event-more > summary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  color: #6b7280;
  font-size: 12px;
  line-height: 18px;
  cursor: pointer;
  list-style: none;
}

.exam-event-more > summary::-webkit-details-marker {
  display: none;
}

.exam-event-more > summary::before {
  display: inline-block;
  color: #8a93a3;
  font-size: 10px;
  content: '▶';
  transition: transform 140ms ease;
}

.exam-event-more[open] > summary::before {
  transform: rotate(90deg);
}

.exam-event-more .exam-event-row {
  background: rgba(255, 255, 255, 0.5);
}

.exam-event-list {
  display: grid;
}

.exam-event-row {
  display: grid;
  gap: 4px;
  padding: 11px 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.055);
}

.exam-event-row:first-child {
  border-top: 0;
}

.exam-event-row-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}

.exam-event-position {
  color: rgba(29, 29, 31, 0.72);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
}

.exam-event-row time {
  color: rgba(29, 29, 31, 0.54);
  font-family: inherit;
  font-size: 12px;
  line-height: 18px;
  font-variant-numeric: tabular-nums;
}

.exam-event-status {
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 400;
  line-height: 18px;
  white-space: nowrap;
}

.exam-event-status.is-danger {
  background: rgba(239, 68, 68, 0.08);
  color: #c62828;
}

.exam-event-status.is-success {
  background: rgba(16, 185, 129, 0.09);
  color: #087443;
}

.exam-event-status.is-warning {
  background: rgba(245, 158, 11, 0.1);
  color: #9a6200;
}

.exam-event-row p {
  margin: 0;
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
  font-weight: 400;
  line-height: 21px;
}

@container (max-width: 560px) {
  .exam-event-row-head {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .exam-event-status {
    grid-column: 1 / -1;
    justify-self: start;
  }
}
</style>
