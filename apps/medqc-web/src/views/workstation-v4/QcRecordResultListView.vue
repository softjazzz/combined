<template>
  <main class="qc-record-result-list-view">
    <section class="qc-record-result-list-view__header">
      <div>
        <div class="qc-record-result-list-view__eyebrow">
          {{ carePhaseLabel }} · 质控结果
        </div>
        <h1>{{ pageTitle }}</h1>
        <p>仅展示最新已完成质控结果</p>
      </div>
      <span class="qc-record-result-list-view__scope">{{ scopeLabel }}</span>
    </section>

    <section
      class="qc-record-result-list-view__metrics"
      aria-label="质控结果汇总"
    >
      <div
        v-for="metric in metricItems"
        :key="metric.label"
        class="qc-record-result-list-view__metric"
      >
        <span>{{ metric.label }}</span>
        <strong>—</strong>
      </div>
    </section>

    <section class="qc-record-result-list-view__workbench">
      <div class="qc-record-result-list-view__toolbar">
        <div
          class="qc-record-result-list-view__filters"
          aria-label="待接入筛选条件"
        >
          <input
            disabled
            placeholder="关键词筛选（数据接入后可用）"
            aria-label="关键词筛选，数据接入后可用"
          >
          <select
            disabled
            aria-label="科室筛选，数据接入后可用"
          >
            <option>全部科室（数据接入后可用）</option>
          </select>
          <input
            disabled
            type="date"
            aria-label="日期筛选，数据接入后可用"
          >
        </div>
        <span class="qc-record-result-list-view__pending">数据接入后可筛选</span>
      </div>

      <QcRecordResultTable
        :care-phase="carePhase"
        :rows="rows"
        @open-result="handleOpenResult"
      />

      <p
        v-if="detailNotice"
        class="qc-record-result-list-view__notice"
        role="status"
      >
        {{ detailNotice }}
      </p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import QcRecordResultTable, {
  type QcRecordCarePhase,
  type QcRecordResultRow,
} from './components/qc/QcRecordResultTable.vue'

const props = defineProps<{
  carePhase: QcRecordCarePhase
}>()

const rows = ref<QcRecordResultRow[]>([])
const detailNotice = ref('')

const isInpatient = computed(() => props.carePhase === 'inpatient')
const pageTitle = computed(() => (isInpatient.value ? '运行病历质控' : '终末病历质控'))
const carePhaseLabel = computed(() => (isInpatient.value ? '在院病历' : '已出院病历'))
const scopeLabel = computed(() => (isInpatient.value ? '固定范围：在院' : '固定范围：已出院'))
const metricItems = [
  { label: '纳入病历' },
  { label: '已完成质控' },
  { label: '需优先复核' },
  { label: '资料待核实' },
]

function handleOpenResult(_recordKey: string) {
  detailNotice.value = '质控结果详情将在下一闭环接入'
}
</script>

<style scoped>
.qc-record-result-list-view {
  min-height: 100%;
  padding: 24px;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', Inter, 'PingFang SC',
    'Microsoft YaHei UI', sans-serif;
}

.qc-record-result-list-view__header,
.qc-record-result-list-view__workbench {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.035);
  backdrop-filter: blur(18px);
}

.qc-record-result-list-view__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 24px;
  border-radius: 20px;
}

.qc-record-result-list-view__eyebrow {
  color: #0066cc;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.qc-record-result-list-view h1 {
  margin: 4px 0 6px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 31px;
}

.qc-record-result-list-view p {
  margin: 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  line-height: 22px;
}

.qc-record-result-list-view__scope {
  margin-top: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.qc-record-result-list-view__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 16px 0;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
}

.qc-record-result-list-view__metric {
  position: relative;
  display: grid;
  gap: 8px;
  min-height: 88px;
  padding: 17px 20px;
}

.qc-record-result-list-view__metric + .qc-record-result-list-view__metric {
  border-left: 1px solid rgba(0, 0, 0, 0.07);
}

.qc-record-result-list-view__metric span {
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  font-weight: 600;
}

.qc-record-result-list-view__metric strong {
  color: #1d1d1f;
  font-size: 23px;
  font-weight: 700;
  line-height: 24px;
}

.qc-record-result-list-view__workbench {
  overflow: hidden;
  border-radius: 20px;
}

.qc-record-result-list-view__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
}

.qc-record-result-list-view__filters {
  display: flex;
  flex: 1;
  gap: 10px;
}

.qc-record-result-list-view__filters input,
.qc-record-result-list-view__filters select {
  height: 34px;
  border: 1px solid rgba(0, 0, 0, 0.09);
  border-radius: 8px;
  background: rgba(245, 245, 247, 0.8);
  color: rgba(29, 29, 31, 0.45);
  font: inherit;
  font-size: 13px;
}

.qc-record-result-list-view__filters input:first-child {
  min-width: 260px;
  padding: 0 11px;
}

.qc-record-result-list-view__filters select {
  min-width: 190px;
  padding: 0 10px;
}

.qc-record-result-list-view__filters input[type='date'] {
  min-width: 144px;
  padding: 0 8px;
}

.qc-record-result-list-view__pending {
  color: rgba(29, 29, 31, 0.45);
  font-size: 12px;
  white-space: nowrap;
}

.qc-record-result-list-view__notice {
  padding: 12px 20px;
  border-top: 1px solid rgba(0, 102, 204, 0.1);
  background: rgba(0, 102, 204, 0.045);
  color: #0066cc !important;
  font-weight: 600;
}

@media (max-width: 900px) {
  .qc-record-result-list-view {
    padding: 16px;
  }

  .qc-record-result-list-view__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .qc-record-result-list-view__metric:nth-child(3) {
    border-left: 0;
    border-top: 1px solid rgba(0, 0, 0, 0.07);
  }

  .qc-record-result-list-view__metric:nth-child(4) {
    border-top: 1px solid rgba(0, 0, 0, 0.07);
  }

  .qc-record-result-list-view__toolbar,
  .qc-record-result-list-view__filters {
    align-items: stretch;
    flex-direction: column;
  }

  .qc-record-result-list-view__filters input:first-child,
  .qc-record-result-list-view__filters select,
  .qc-record-result-list-view__filters input[type='date'] {
    width: 100%;
    min-width: 0;
  }
}

@media (max-width: 560px) {
  .qc-record-result-list-view__header {
    align-items: stretch;
    flex-direction: column;
  }

  .qc-record-result-list-view__scope {
    align-self: flex-start;
  }
}
</style>
