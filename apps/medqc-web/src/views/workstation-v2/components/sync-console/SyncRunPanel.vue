<template>
  <div class="h-full flex flex-col bg-white overflow-hidden run-panel">
    <div
      class="px-5 py-3 border-b border-slate-100 bg-white flex justify-between items-center shrink-0"
    >
      <h2 class="text-[13px] font-semibold text-slate-900 tracking-tight">执行日志与历史</h2>
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
        预计影响 {{ state.preflightResult.estimated_impact }} 条，风险等级
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
          {{ state.preflightResult.risk_level }}
        </a-tag>
      </div>
      <div v-if="state.preflightResult.blockers?.length" class="text-[11px] text-red-500 mt-1">
        阻断项：{{ state.preflightResult.blockers.join('；') }}
      </div>
      <div v-if="state.preflightResult.warnings?.length" class="text-[11px] text-amber-600 mt-1">
        告警：{{ state.preflightResult.warnings.join('；') }}
      </div>
    </div>

    <div
      v-if="activeView === 'realtime'"
      class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-2 text-[11.5px] font-mono bg-[#FAFAFA]"
    >
      <div v-if="state.currentRunLog.length === 0" class="text-slate-400">
        > Ready. Waiting for command...
      </div>

      <div v-for="(log, idx) in state.currentRunLog" :key="idx" class="flex gap-3 leading-relaxed">
        <span class="text-slate-400 shrink-0 select-none">[{{ log.timestamp }}]</span>
        <span
          class="whitespace-pre-wrap flex-1"
          :class="{
            'text-slate-700': log.level === 'info',
            'text-emerald-600': log.level === 'success',
            'text-amber-600': log.level === 'warn',
            'text-red-600': log.level === 'error',
          }"
          >{{ log.message }}</span
        >
      </div>
    </div>

    <div v-else class="flex-1 flex flex-col min-h-0">
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
        <div v-if="state.runsLoading" class="text-[12px] text-slate-500">正在加载运行历史...</div>
        <div v-else-if="state.runHistory.length === 0" class="text-[12px] text-slate-500">
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
              <span class="text-[11px] font-medium" :class="statusClass(item.status)">
                {{ item.status }}
              </span>
            </div>
            <div class="mt-1 text-[11px] text-slate-500">
              开始：{{ formatTime(item.started_at) }} · 耗时：{{
                formatDuration(item.duration_ms)
              }}
              · 记录数：{{ item.total_records || 0 }}
            </div>
            <div v-if="item.error" class="mt-1 text-[11px] text-red-500">
              错误：{{ item.error }}
            </div>
            <div v-if="item.operator?.email" class="mt-1 text-[11px] text-slate-400">
              操作人：{{ item.operator.email }}
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
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
</script>

<style scoped>
.run-panel {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.view-switch {
  background: linear-gradient(90deg, #f8fafc 0%, #f1f5f9 100%);
}

.sync-banner {
  border-left: 3px solid #2563eb;
}

.preflight-block {
  background: #f8fafc;
}

.history-toolbar {
  background: #f8fafc;
}
</style>
