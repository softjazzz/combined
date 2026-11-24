<template>
  <section
    v-if="presentation.metrics.length"
    :class="['timeliness-metrics', `is-${variant}`, `has-${presentation.metrics.length}-metrics`]"
    data-testid="timeliness-metrics"
  >
    <div
      v-for="row in presentation.metrics"
      :key="row.key"
      class="timeliness-metric"
      :class="{ 'is-overdue': variant === 'decision' && row.key === 'overdue_hours' }"
    >
      <span>{{ row.label }}</span>
      <strong>{{ row.value }}</strong>
    </div>
  </section>
  <div
    v-if="presentation.timeline.length"
    :class="['timeliness-timeline', `is-${variant}`]"
    data-testid="timeliness-timeline"
  >
    <template
      v-for="(row, index) in presentation.timeline"
      :key="row.key"
    >
      <span class="timeline-point">
        <small>{{ row.label }}</small>
        <strong>{{ row.value }}</strong>
      </span>
      <span
        v-if="index < presentation.timeline.length - 1"
        class="timeline-arrow"
        aria-hidden="true"
      >
        <ArrowRight
          :size="15"
          :stroke-width="1.8"
        />
      </span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'
import { computed } from 'vue'
import type { SingleRecordQcResultItem } from './single-record-result-model'
import { buildTimelinessResultPresentation } from './timelinessResultPresentation'

const props = withDefaults(
  defineProps<{
    item: SingleRecordQcResultItem
    variant: 'compliant' | 'decision'
  }>(),
  { variant: 'compliant' },
)

const presentation = computed(() => buildTimelinessResultPresentation(props.item))
const variant = computed(() => props.variant)
</script>

<style scoped>
.timeliness-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 10px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.timeliness-metrics.has-1-metrics {
  grid-template-columns: minmax(0, 1fr);
}

.timeliness-metrics.has-2-metrics {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.timeliness-metric {
  display: grid;
  gap: 2px;
  min-width: 0;
  padding: 7px 8px;
  border-right: 1px solid rgba(0, 0, 0, 0.07);
  text-align: center;
}

.timeliness-metric:last-child {
  border-right: 0;
}

.timeliness-metric span {
  color: rgba(29, 29, 31, 0.5);
  font-size: 11px;
  font-weight: 600;
  line-height: 17px;
}

.timeliness-metric strong {
  color: rgba(29, 29, 31, 0.9);
  font-size: 15px;
  font-weight: 650;
  line-height: 21px;
}

.timeliness-metric.is-overdue {
  background: rgba(248, 250, 252, 0.95);
}

.timeliness-metric.is-overdue strong {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--mq-text-primary, #0f172a);
  font-weight: 700;
}

.timeliness-metric.is-overdue strong::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #d97706;
  flex: none;
}

.timeliness-timeline {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 7px;
  color: rgba(29, 29, 31, 0.64);
}

.timeline-point {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 6px;
}

.timeline-point small {
  color: rgba(29, 29, 31, 0.5);
  font-size: 11px;
  line-height: 17px;
}

.timeline-point strong {
  color: rgba(29, 29, 31, 0.78);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.timeline-arrow {
  display: inline-flex;
  align-items: center;
  color: rgba(10, 108, 255, 0.5);
}

.timeliness-metrics.is-compliant {
  margin-top: 0;
}

.timeliness-metrics.is-compliant:not(:first-child),
.timeliness-timeline.is-compliant:not(:first-child) {
  margin-top: 9px;
  padding-top: 9px;
  border-top: 1px solid rgba(0, 0, 0, 0.065);
}

@container (max-width: 900px) {
  .timeliness-timeline {
    flex-wrap: wrap;
    gap: 6px 8px;
  }
}

@container (max-width: 560px) {
  .timeliness-metric {
    padding: 6px 4px;
  }

  .timeliness-metric strong {
    font-size: 13px;
    line-height: 20px;
  }
}
</style>
