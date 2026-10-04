<template>
  <figure class="bac" data-testid="business-agent-chart">
    <div class="bac__bar">
      <figcaption class="bac__metric">{{ chart.metric }}（{{ chart.unit }}）</figcaption>
      <div class="bac__seg" role="group" aria-label="切换图表与数据">
        <button
          type="button"
          class="bac__seg-item"
          :class="{ 'is-active': mode === 'chart' }"
          :aria-pressed="mode === 'chart'"
          @click="mode = 'chart'"
        >
          图表
        </button>
        <button
          type="button"
          class="bac__seg-item"
          :class="{ 'is-active': mode === 'table' }"
          :aria-pressed="mode === 'table'"
          data-testid="business-agent-chart-table-toggle"
          @click="mode = 'table'"
        >
          数据
        </button>
      </div>
    </div>

    <table v-if="mode === 'table'" class="bac__table" data-testid="business-agent-chart-table">
      <thead>
        <tr>
          <th scope="col">
            {{ chart.type === 'line' ? '期间' : '规则' }}
          </th>
          <th scope="col" class="bac__num">
            {{ chart.metric }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="point in chart.points" :key="point.label">
          <td>{{ point.label }}</td>
          <td class="bac__num">
            {{ point.value === null ? '未提供' : point.value }}
          </td>
        </tr>
      </tbody>
    </table>

    <template v-else-if="chart.type === 'line'">
      <div v-if="numeric < 2" class="bac__single" data-testid="business-agent-chart-single">
        <p v-if="numeric === 1" class="bac__single-value">
          <strong>{{ onlyPoint?.value }}</strong>
          <span>{{ chart.unit }} · {{ onlyPoint?.label }}</span>
        </p>
        <p class="bac__hint">
          {{
            numeric === 1
              ? chart.points.length > 1
                ? `仅 ${onlyPoint?.label} 有数据，其余 ${chart.points.length - 1} 个期间没有可显示的数据（不按 0 处理），无法绘制趋势。`
                : '仅有 1 个期间的数据，无法绘制趋势。可指定更多期间后再次提问。'
              : '各期暂无可显示的数据，不按 0 处理。'
          }}
        </p>
      </div>
      <svg
        v-else
        class="bac__svg"
        :viewBox="`0 0 ${view.width} ${view.height}`"
        role="img"
        :aria-label="label"
      >
        <g v-for="tick in line.grid" :key="tick.value">
          <line
            :x1="view.left"
            :x2="view.width - view.right"
            :y1="tick.y"
            :y2="tick.y"
            class="bac__grid"
          />
          <text :x="view.left - 8" :y="tick.y + 4" text-anchor="end" class="bac__axis">
            {{ tick.value }}
          </text>
        </g>
        <polygon v-for="area in line.areas" :key="area" :points="area" class="bac__area" />
        <polyline
          v-for="segment in line.segments"
          :key="segment"
          :points="segment"
          class="bac__line"
        />
        <g v-for="(point, index) in line.points" :key="point.label">
          <template v-if="point.y !== null">
            <circle
              :cx="point.x"
              :cy="point.y"
              :r="index === line.points.length - 1 ? 5 : 3.5"
              :class="index === line.points.length - 1 ? 'bac__dot bac__dot--last' : 'bac__dot'"
            />
            <text :x="point.x" :y="point.y - 11" text-anchor="middle" class="bac__value">
              {{ point.value }}
            </text>
          </template>
          <text
            :x="point.x"
            :y="view.height - view.bottom + 22"
            text-anchor="middle"
            class="bac__axis"
          >
            {{ point.label }}
          </text>
          <text
            v-if="point.y === null"
            :x="point.x"
            :y="view.height - view.bottom - 8"
            text-anchor="middle"
            class="bac__axis"
          >
            无数据
          </text>
        </g>
      </svg>
    </template>

    <ol v-else class="bac__rank" :aria-label="label">
      <li v-for="(point, index) in chart.points" :key="point.label" class="bac__rank-item">
        <div class="bac__rank-row">
          <span class="bac__rank-index">{{ index + 1 }}</span>
          <span class="bac__rank-name" :class="{ 'is-top': index === 0 }">{{ point.label }}</span>
          <strong class="bac__rank-value">{{ point.value ?? '未提供' }}</strong>
          <span class="bac__rank-unit">{{ chart.unit }}</span>
        </div>
        <div class="bac__track" aria-hidden="true">
          <div
            class="bac__fill"
            :class="{ 'is-top': index === 0 }"
            :style="{ width: barWidth(point.value) }"
          />
        </div>
      </li>
    </ol>

    <p class="bac__caption">
      {{ chart.caption }}
    </p>
  </figure>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { BusinessAgentChart } from '@/api/businessAgent'
import { LINE_VIEW, buildLine, chartLabel, numericCount } from './businessAgentChart'

const props = defineProps<{ chart: BusinessAgentChart }>()
const mode = ref<'chart' | 'table'>('chart')
const view = LINE_VIEW
const label = computed(() => chartLabel(props.chart))
const numeric = computed(() => numericCount(props.chart))
const onlyPoint = computed(() => props.chart.points.find((point) => point.value !== null))
const line = computed(() => buildLine(props.chart))
const maxValue = computed(() =>
  Math.max(
    0,
    ...props.chart.points.flatMap((point) => (point.value === null ? [] : [point.value])),
  ),
)
// 条长只是视觉比例（相对最大值），不作为占比指标展示。
function barWidth(value: number | null) {
  return value === null || maxValue.value === 0 ? '0%' : `${(value / maxValue.value) * 100}%`
}
</script>

<style scoped>
.bac {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
}
.bac__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.bac__metric {
  font-size: 12px;
  color: var(--mq-text-secondary);
}
.bac__seg {
  display: inline-flex;
  padding: 2px;
  border-radius: var(--mq-radius-control);
  background: var(--mq-neutral-bg);
}
.bac__seg-item {
  padding: 2px 10px;
  border: 0;
  border-radius: var(--mq-radius-control);
  background: transparent;
  color: var(--mq-text-secondary);
  font-size: 12px;
  cursor: pointer;
}
.bac__seg-item.is-active {
  background: #fff;
  color: var(--mq-info-text);
  font-weight: 600;
}
.bac__svg {
  width: 100%;
  height: auto;
}
.bac__grid {
  stroke: var(--mq-border);
  stroke-dasharray: 3 4;
}
.bac__axis {
  font-size: 11px;
  fill: var(--mq-text-tertiary);
}
.bac__value {
  font-size: 12px;
  font-weight: 600;
  fill: var(--mq-text-primary);
}
.bac__line {
  fill: none;
  stroke: var(--mq-info-icon);
  stroke-width: 2.5;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.bac__area {
  fill: var(--mq-info-bg);
}
.bac__dot {
  fill: var(--mq-info-icon);
}
.bac__dot--last {
  fill: #fff;
  stroke: var(--mq-info-icon);
  stroke-width: 2.5;
}
.bac__single {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bac__single-value {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: 13px;
}
.bac__single-value strong {
  font-size: 32px;
  color: var(--mq-text-primary);
}
.bac__hint {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--mq-radius-control);
  background: var(--mq-neutral-bg);
  color: var(--mq-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.bac__rank {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.bac__rank-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.bac__rank-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  background: var(--mq-info-bg);
  color: var(--mq-info-text);
  font-size: 11px;
  font-weight: 700;
}
.bac__rank-name {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--mq-text-primary);
}
.bac__rank-name.is-top {
  font-weight: 700;
}
.bac__rank-unit {
  color: var(--mq-text-tertiary);
  font-size: 12px;
}
.bac__track {
  height: 8px;
  margin-top: 5px;
  border-radius: 999px;
  background: var(--mq-neutral-bg);
}
.bac__fill {
  height: 8px;
  border-radius: 999px;
  background: var(--mq-info-icon);
  opacity: 0.5;
}
.bac__fill.is-top {
  opacity: 1;
}
.bac__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.bac__table th,
.bac__table td {
  padding: 6px 4px;
  border-bottom: 1px solid var(--mq-border);
  text-align: left;
}
.bac__table th {
  color: var(--mq-text-tertiary);
  font-size: 12px;
  font-weight: 500;
}
.bac__num {
  text-align: right !important;
  font-variant-numeric: tabular-nums;
}
.bac__caption {
  margin: 0;
  color: var(--mq-text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}
</style>
