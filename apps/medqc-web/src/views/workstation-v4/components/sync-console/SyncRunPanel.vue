<template>
  <div class="h-full flex flex-col bg-white overflow-hidden run-panel">
    <div
      class="px-5 py-3 border-b border-slate-100 bg-white flex justify-between items-center shrink-0"
    >
      <h2 class="text-[13px] font-semibold text-slate-900 tracking-tight">
        执行日志与历史
      </h2>
      <div class="flex items-center gap-2">
        <button
          class="text-[11px] text-slate-400 hover:text-slate-800 transition-colors font-medium"
          @click="handleRefreshHistory"
        >
          刷新历史
        </button>
        <button
          class="text-[11px] text-slate-400 hover:text-slate-800 transition-colors font-medium"
          @click="clearLogs"
        >
          清空日志
        </button>
      </div>
    </div>

    <div
      class="px-5 py-2 border-b border-slate-100 bg-slate-50 shrink-0 flex items-center gap-2 view-switch"
    >
      <button
        class="px-2 py-1 rounded text-[11px] transition-colors"
        :class="
          activeView === 'realtime'
            ? 'bg-white text-slate-800 border border-slate-200'
            : 'text-slate-500 hover:text-slate-700'
        "
        @click="activeView = 'realtime'"
      >
        实时日志
      </button>
      <button
        class="px-2 py-1 rounded text-[11px] transition-colors"
        :class="
          activeView === 'history'
            ? 'bg-white text-slate-800 border border-slate-200'
            : 'text-slate-500 hover:text-slate-700'
        "
        @click="activeView = 'history'"
      >
        运行历史
      </button>
    </div>

    <div
      v-if="state.isSyncing"
      class="px-5 py-2.5 bg-slate-50 border-b border-slate-100 shrink-0 sync-banner"
    >
      <div class="flex items-center justify-between">
        <span class="text-[11px] font-medium text-slate-700">同步任务执行中...</span>
        <span class="text-[11px] text-slate-500">轮询中</span>
      </div>
    </div>

    <div
      v-if="state.preflightResult"
      class="px-5 py-3 border-b border-slate-100 shrink-0 preflight-block"
    >
      <div class="text-[12px] font-semibold text-slate-800">
        预检结果：{{ state.preflightResult.executable ? '通过' : '未通过' }}
      </div>
      <div class="text-[11px] text-slate-500 mt-1 flex items-center">
        预计涉及 {{ state.preflightResult.estimated_impact }} 份病历，风险等级
        <a-tag
          :color="
            state.preflightResult.risk_level === 'high'
              ? 'red'
              : state.preflightResult.risk_level === 'medium'
                ? 'orange'
                : 'green'
          "
          class="ml-1"
        >
          {{ riskLevelLabel(state.preflightResult.risk_level) }}
        </a-tag>
      </div>
      <div class="text-[11px] text-slate-500 mt-1">
        模式：{{ state.preflightResult.mode || '-' }} · Schema：{{
          state.preflightResult.remote_schema || '-'
        }}
        · 矩阵范围：全量({{ state.preflightResult.matrix_scope?.full || 'all' }}) / 执行集({{
          state.preflightResult.matrix_scope?.execution || 'enabled'
        }})
      </div>
      <div
        v-if="state.preflightResult.blockers?.length"
        class="text-[11px] text-red-500 mt-1"
      >
        阻断项：{{ state.preflightResult.blockers.join('；') }}
      </div>
      <div
        v-if="state.preflightResult.warnings?.length"
        class="text-[11px] text-amber-600 mt-1"
      >
        告警：{{ state.preflightResult.warnings.join('；') }}
      </div>
      <div
        v-if="state.preflightResult.table_validations?.length"
        class="mt-2 text-[11px] text-slate-600"
      >
        全量矩阵：{{ passCount(state.preflightResult.table_validations) }}/{{
          state.preflightResult.table_validations.length
        }}
        可执行
      </div>
      <div
        v-if="state.preflightResult.execution_table_validations?.length"
        class="mt-1 text-[11px] text-slate-600"
      >
        执行集矩阵：{{ passCount(state.preflightResult.execution_table_validations) }}/{{
          state.preflightResult.execution_table_validations.length
        }}
        可执行
      </div>
      <div
        v-if="failedFullValidations.length"
        class="mt-2 rounded border border-amber-200 bg-amber-50/60 px-2 py-1.5"
      >
        <div class="text-[11px] font-semibold text-amber-700 mb-1">
          全量矩阵失败项（{{ failedFullValidations.length }}）
        </div>
        <div
          v-for="item in failedFullValidations"
          :key="`full-${item.table}`"
          class="text-[11px] text-amber-700 leading-5"
        >
          {{ item.table }}：{{ item.blockers.join('；') || '不可执行' }}
        </div>
      </div>
      <div
        v-if="failedExecutionValidations.length"
        class="mt-2 rounded border border-red-200 bg-red-50/60 px-2 py-1.5"
      >
        <div class="text-[11px] font-semibold text-red-700 mb-1">
          执行集失败项（{{ failedExecutionValidations.length }}）
        </div>
        <div
          v-for="item in failedExecutionValidations"
          :key="`execution-${item.table}`"
          class="text-[11px] text-red-700 leading-5"
        >
          {{ item.table }}：{{ item.blockers.join('；') || '不可执行' }}
        </div>
      </div>
    </div>

    <div
      v-if="activeView === 'realtime'"
      class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-2 text-[11.5px] font-mono bg-[#FAFAFA]"
    >
      <div
        v-if="state.currentRunLog.length === 0"
        class="text-slate-400"
      >
        > Ready. Waiting for command...
      </div>

      <div
        v-for="(log, idx) in state.currentRunLog"
        :key="idx"
        class="flex gap-3 leading-relaxed"
      >
        <span class="text-slate-400 shrink-0 select-none">[{{ log.timestamp }}]</span>
        <span
          class="whitespace-pre-wrap flex-1"
          :class="{
            'text-slate-700': log.level === 'info',
            'text-emerald-600': log.level === 'success',
            'text-amber-600': log.level === 'warn',
            'text-red-600': log.level === 'error',
          }"
        >{{ log.message }}</span>
      </div>
    </div>

    <div
      v-else
      class="flex-1 flex flex-col min-h-0"
    >
      <div
        v-if="state.loadErrors.history"
        class="px-5 py-2 border-b border-amber-200 bg-amber-50 text-[12px] text-amber-700"
      >
        {{ state.loadErrors.history }}
      </div>

      <div class="px-5 py-2 border-b border-slate-100 flex items-center gap-2 history-toolbar">
        <a-select
          v-model:value="state.runHistorySourceFilter"
          size="small"
          style="width: 110px"
          :options="sourceOptions"
          @change="handleFilterChange"
        />
        <a-select
          v-model:value="state.runHistoryTierFilter"
          size="small"
          style="width: 110px"
          :options="tierOptions"
          @change="handleFilterChange"
        />
        <span class="text-[11px] text-slate-400">共 {{ state.runHistoryTotal }} 条</span>
      </div>

      <div class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-2 bg-[#FAFAFA]">
        <div
          v-if="state.runsLoading"
          class="text-[12px] text-slate-500"
        >
          正在加载运行历史...
        </div>
        <div
          v-else-if="state.runHistory.length === 0"
          class="text-[12px] text-slate-500"
        >
          暂无运行历史记录。
        </div>
        <template v-else>
          <div
            v-for="item in state.runHistory"
            :key="item.id"
            class="rounded border border-slate-200 bg-white px-3 py-2"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="text-[12px] font-semibold text-slate-800">
                {{ item.source.toUpperCase() }} · {{ item.tier }}
              </div>
              <span
                class="text-[11px] font-medium"
                :class="statusClass(item.status)"
              >
                {{ statusText(item.status) }}
              </span>
            </div>
            <div class="mt-1 text-[11px] text-slate-500">
              开始：{{ formatTime(item.started_at) }} · 耗时：{{
                formatDuration(item.duration_ms)
              }}
              · 记录数：{{ item.total_records || 0 }}
            </div>
            <div
              v-if="item.error"
              class="mt-1 text-[11px] text-red-500"
            >
              错误：{{ item.error }}
            </div>
            <div
              v-if="item.operator?.email"
              class="mt-1 text-[11px] text-slate-400"
            >
              操作人：{{ item.operator.email }}
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import type { SyncTableValidationItem } from '@/api/sync'
import { useDataSync } from '../../composables/useDataSync'

const { state, clearLogs, loadRunHistory } = useDataSync()

const activeView = ref<'realtime' | 'history'>('realtime')

const sourceOptions = [
  { label: '全部来源', value: 'all' },
  { label: 'PG', value: 'pg' },
]

const tierOptions = [
  { label: '全部 Tier', value: 'all' },
  { label: 'Tier1', value: 'tier1' },
  { label: 'Tier2', value: 'tier2' },
  { label: 'Tier3', value: 'tier3' },
]

const failedFullValidations = computed(() => {
  const items = state.preflightResult?.table_validations || []
  return items.filter((item) => !item.executable)
})

const failedExecutionValidations = computed(() => {
  const preferred = state.preflightResult?.execution_table_validations
  const fallback = state.preflightResult?.table_validations
  const items = (preferred && preferred.length > 0 ? preferred : fallback) || []
  return items.filter((item) => !item.executable)
})

function passCount(items?: SyncTableValidationItem[]): number {
  if (!Array.isArray(items) || items.length === 0) {
    return 0
  }
  return items.filter((item) => item.executable).length
}

async function handleRefreshHistory() {
  try {
    await loadRunHistory()
  } catch {
    message.error('刷新运行历史失败')
  }
}

async function handleFilterChange() {
  await loadRunHistory({
    source: state.runHistorySourceFilter,
    tier: state.runHistoryTierFilter,
  })
}

function formatTime(value?: string): string {
  if (!value) {
    return '-'
  }
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) {
    return value
  }
  return dt.toLocaleString('zh-CN', { hour12: false })
}

function formatDuration(ms?: number): string {
  const value = Number(ms || 0)
  if (value <= 0) {
    return '-'
  }
  if (value < 1000) {
    return `${value}ms`
  }
  return `${(value / 1000).toFixed(1)}s`
}

function statusClass(status: string): string {
  if (status === 'success') {
    return 'text-emerald-600'
  }
  if (status === 'partial') {
    return 'text-amber-600'
  }
  if (status === 'failed') {
    return 'text-red-600'
  }
  return 'text-slate-500'
}

function statusText(status: string): string {
  if (status === 'success') return '成功'
  if (status === 'partial') return '部分完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '执行中'
  return '未知'
}

function riskLevelLabel(level?: string): string {
  if (level === 'high') return '高'
  if (level === 'medium') return '中'
  if (level === 'low') return '低'
  return '低'
}
</script>

<style scoped>
.run-panel {
  background: rgba(255, 255, 255, 0.9);
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.run-panel :deep(.font-mono) {
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
}

.run-panel > div:first-child {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
}

.view-switch {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(245, 245, 247, 0.68);
}

.view-switch button {
  border-radius: 8px;
  font-weight: 600;
}

.view-switch button:hover {
  color: #1d1d1f;
}

.view-switch :deep(.bg-white) {
  border-color: rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.07) !important;
  color: #0066cc !important;
}

.sync-banner {
  border-left: 3px solid #0066cc;
  background: rgba(0, 102, 204, 0.06);
}

.preflight-block {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
}

.history-toolbar {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(245, 245, 247, 0.68);
}

.run-panel :deep(.bg-\[\#FAFAFA\]) {
  background-color: rgba(245, 245, 247, 0.62) !important;
}

.run-panel :deep(.border-slate-100),
.run-panel :deep(.border-slate-200),
.run-panel :deep(.border-amber-200),
.run-panel :deep(.border-red-200) {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.run-panel :deep(.bg-amber-50),
.run-panel :deep(.bg-amber-50\/60) {
  background-color: rgba(255, 251, 235, 0.8) !important;
}

.run-panel :deep(.bg-red-50\/60) {
  background-color: rgba(239, 68, 68, 0.08) !important;
}

.run-panel :deep(.text-slate-900),
.run-panel :deep(.text-slate-800),
.run-panel :deep(.text-slate-700) {
  color: #1d1d1f !important;
}

.run-panel :deep(.text-slate-600),
.run-panel :deep(.text-slate-500) {
  color: rgba(29, 29, 31, 0.6) !important;
}

.run-panel :deep(.text-slate-400) {
  color: rgba(29, 29, 31, 0.38) !important;
}

.run-panel :deep(.text-emerald-600) {
  color: #047857 !important;
}

.run-panel :deep(.text-amber-600),
.run-panel :deep(.text-amber-700) {
  color: #b45309 !important;
}

.run-panel :deep(.text-red-500),
.run-panel :deep(.text-red-600),
.run-panel :deep(.text-red-700) {
  color: #b91c1c !important;
}

.run-panel :deep(.rounded.border.bg-white) {
  border-radius: 12px;
  background-color: rgba(255, 255, 255, 0.86) !important;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    background-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.run-panel :deep(.rounded.border.bg-white:hover) {
  border-color: rgba(0, 0, 0, 0.14) !important;
  background-color: rgba(255, 255, 255, 0.96) !important;
}
</style>
