<template>
  <div class="perf-board">
    <div class="board-header">
      <h3 class="board-title">
        <TrophyOutlined class="title-icon" />
        工作表现
      </h3>
      <div
        class="period-switch"
        role="group"
        aria-label="统计周期"
      >
        <button
          v-for="option in PERIOD_OPTIONS"
          :key="option.value"
          type="button"
          :class="['period-option', { 'is-active': option.value === period }]"
          :aria-pressed="option.value === period"
          :data-testid="`perf-period-${option.value}`"
          @click="selectPeriod(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <div
      v-if="rangeText"
      class="range-text"
      data-testid="perf-range"
    >
      统计区间：{{ rangeText }}
    </div>

    <div
      v-if="status === 'loading'"
      class="state-box"
      data-testid="perf-loading"
    >
      <span class="text-gray-400 text-xs">加载中…</span>
    </div>

    <div
      v-else-if="status === 'error' || !data"
      class="state-box state-error"
      data-testid="perf-error"
    >
      <span class="text-xs">排名加载失败{{ errorMessage ? `：${errorMessage}` : '' }}</span>
      <button
        type="button"
        class="retry-btn"
        data-testid="perf-retry"
        @click="emit('retry')"
      >
        重试
      </button>
    </div>

    <div
      v-else
      class="board-content"
    >
      <section
        v-for="section in sections"
        :key="section.key"
        class="ranking-section"
        :data-testid="`perf-section-${section.key}`"
      >
        <div class="section-title">
          <component :is="section.icon" /> {{ section.title }}
        </div>
        <div
          v-if="section.items === null"
          class="state-box"
          data-testid="perf-unavailable"
        >
          <span class="text-gray-400 text-xs">{{ unavailableText }}</span>
        </div>
        <div
          v-else-if="section.items.length === 0"
          class="state-box"
          data-testid="perf-empty"
        >
          <span class="text-gray-400 text-xs">本期暂无</span>
        </div>
        <ol
          v-else
          class="ranking-list"
        >
          <li
            v-for="row in section.items"
            :key="`${section.key}-${row.userId}`"
            class="ranking-item"
            data-testid="perf-item"
          >
            <span :class="['rank-badge', `rank-${row.rank}`]">{{ row.rank }}</span>
            <div class="rank-main">
              <div class="rank-line">
                <span
                  class="rank-name"
                  :title="row.label"
                >{{ row.label }}</span>
                <span class="rank-value">{{ row.count }}{{ section.key === 'record' ? '份' : '项' }}</span>
              </div>
              <div class="rank-bar-container">
                <div
                  :class="['rank-bar', section.barClass]"
                  :style="{ width: barWidth(row.count, section.max) + '%' }"
                />
              </div>
              <div class="rank-detail">
                {{ row.detail }}
              </div>
            </div>
          </li>
        </ol>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import { TrophyOutlined, BugOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import type {
  DefectRankingItem,
  PerformanceData,
  PerformancePeriod,
  RecordRankingItem,
} from '@/api/dashboard'

export type PerformanceBoardStatus = 'loading' | 'ready' | 'error'

const props = withDefaults(defineProps<{
  period: PerformancePeriod
  status: PerformanceBoardStatus
  data: PerformanceData | null
  errorMessage?: string
}>(), {
  errorMessage: '',
})

const emit = defineEmits<{
  (e: 'period-change', period: PerformancePeriod): void
  (e: 'retry'): void
}>()

const PERIOD_OPTIONS: ReadonlyArray<{ label: string; value: PerformancePeriod }> = [
  { label: '本周', value: 'this_week' },
  { label: '上周', value: 'last_week' },
  { label: '本月', value: 'this_month' },
]

/** 展示行：由服务端排名项直接搬运，不重算名次或计数 */
interface RankingRow {
  userId: string
  label: string
  count: number
  rank: number
  detail: string
}

interface RankingSection {
  key: 'defect' | 'record'
  title: string
  icon: Component
  barClass: string
  items: RankingRow[] | null
  max: number
}

const selectPeriod = (value: PerformancePeriod) => {
  if (value === props.period) return
  emit('period-change', value)
}

const unavailableText = computed(() =>
  props.data?.unavailable_reason === 'scene_not_attributable' ? '该场景暂不支持' : '暂不可用',
)

/** 仅截取 ISO 字符串中的日期时间，不做时区换算，保持服务端（医院时区）口径 */
const formatIso = (iso: string) => iso.slice(0, 16).replace('T', ' ')
const rangeText = computed(() => {
  if (props.status !== 'ready' || !props.data) return ''
  const { start, end } = props.data.range
  return `${formatIso(start)} ~ ${formatIso(end)}`
})

// name 缺失时回退显示 user_id
const displayName = (item: { name: string | null; user_id: string }) => item.name || item.user_id

const defectRows = (items: DefectRankingItem[] | null): RankingRow[] | null =>
  items?.map((item) => ({
    userId: item.user_id,
    label: displayName(item),
    count: item.count,
    rank: item.rank,
    detail: `通过 ${item.approved_count} / 驳回 ${item.rejected_count}`,
  })) ?? null

const recordRows = (items: RecordRankingItem[] | null): RankingRow[] | null =>
  items?.map((item) => ({
    userId: item.user_id,
    label: displayName(item),
    count: item.count,
    rank: item.rank,
    detail: `初审病历 ${item.initial_count} / 复审病历 ${item.recheck_count}`,
  })) ?? null

const maxCount = (rows: RankingRow[] | null) =>
  rows?.length ? Math.max(...rows.map((row) => row.count)) : 0

const sections = computed<RankingSection[]>(() => {
  const defect = defectRows(props.data?.defect_ranking ?? null)
  const record = recordRows(props.data?.record_ranking ?? null)
  return [
    {
      key: 'defect',
      title: '质控缺陷排名',
      icon: BugOutlined,
      barClass: '',
      items: defect,
      max: maxCount(defect),
    },
    {
      key: 'record',
      title: '质控病历排名',
      icon: FileTextOutlined,
      barClass: 'rank-bar-green',
      items: record,
      max: maxCount(record),
    },
  ]
})

const barWidth = (value: number, max: number) => (max > 0 ? (value / max) * 100 : 0)
</script>

<style scoped>
.perf-board {
  background: white;
  border-radius: 16px;
  border: 1px solid #f0f0f0;
  padding: 20px 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  height: 100%;
}
.board-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 16px;
}
.board-title {
  font-size: 16px;
  font-weight: 700;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  white-space: nowrap;
}
.title-icon { color: #faad14; }

.period-switch {
  display: inline-flex;
  padding: 2px;
  background: #f5f5f5;
  border-radius: 6px;
  gap: 2px;
}
.period-option {
  border: none;
  background: transparent;
  padding: 2px 10px;
  font-size: 12px;
  color: #595959;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
}
.period-option.is-active {
  background: #fff;
  color: #1a1a1a;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}

.range-text {
  font-size: 12px;
  color: #8c8c8c;
  margin: -8px 0 12px;
}

.board-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.ranking-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ranking-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
}

.rank-badge {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #999;
  background: #f5f5f5;
  flex-shrink: 0;
}
.rank-1 { background: linear-gradient(135deg, #ffd700, #ffaa00); color: white; }
.rank-2 { background: linear-gradient(135deg, #c0c0c0, #a0a0a0); color: white; }
.rank-3 { background: linear-gradient(135deg, #cd7f32, #b87333); color: white; }

.rank-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.rank-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.rank-name {
  min-width: 0;
  color: #333;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rank-value {
  font-weight: 700;
  color: #333;
  flex-shrink: 0;
}
.rank-detail {
  font-size: 12px;
  color: #8c8c8c;
}

.rank-bar-container {
  height: 6px;
  background: #f5f5f5;
  border-radius: 3px;
  overflow: hidden;
}
.rank-bar {
  height: 100%;
  background: linear-gradient(90deg, #2b6cf6, #4096ff);
  border-radius: 3px;
  transition: width 0.6s ease;
}
.rank-bar-green {
  background: linear-gradient(90deg, #52c41a, #73d13d);
}

.state-box {
  padding: 16px;
  text-align: center;
  background: #fafafa;
  border-radius: 8px;
}
.state-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #cf1322;
  background: #fff1f0;
}
.retry-btn {
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 4px;
  padding: 2px 12px;
  font-size: 12px;
  color: #2b6cf6;
  cursor: pointer;
}
</style>
