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
    <div class="exam-event-list">
      <article
        v-for="event in presentation.events"
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
  </section>
</template>

<script setup lang="ts">
import type { ExamLabEventPresentation } from './examLabEventPresentation'

defineProps<{
  presentation: ExamLabEventPresentation
}>()
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
  gap: 6px;
  padding: 9px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.065);
}

.exam-event-summary span {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(0, 122, 255, 0.07);
  color: #366b9b;
  font-size: 12px;
  font-weight: 400;
  line-height: 18px;
}

.exam-event-summary span.is-danger {
  background: rgba(239, 68, 68, 0.08);
  color: #c62828;
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
