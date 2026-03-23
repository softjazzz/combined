<template>
  <div class="flex-shrink-0 flex flex-col lg:flex-row lg:items-center justify-between gap-5 w-full">
    <div class="flex items-center gap-3 shrink-0">
      <div class="w-8 h-8 rounded-lg bg-blue-600 border border-blue-500 flex items-center justify-center shadow-sm">
        <svg
          class="w-4 h-4 text-white"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          stroke-width="2"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M13 10V3L4 14h7v7l9-11h-7z"
          />
        </svg>
      </div>
      <div>
        <h1 class="text-[20px] font-bold tracking-tight text-slate-800 leading-none">
          数据对接控制台
        </h1>
        <div class="mt-1.5 flex items-center gap-2">
          <span class="text-[12px] font-medium text-slate-500 tracking-wide uppercase">Data Sync Console</span>
          <span class="w-1.5 h-1.5 rounded-full bg-slate-300" />
          <span class="text-[12px] font-medium text-slate-400">Workstation V4</span>
        </div>
      </div>
    </div>

    <div class="flex items-center gap-4 flex-1 lg:justify-end pr-4">
      <div class="flex flex-col bg-white rounded-[8px] px-5 py-2.5 border border-[#E5E7EB] shadow-[0_1px_2px_0_rgba(0,0,0,0.03)] min-w-[120px]">
        <div class="flex items-center justify-between gap-3 mb-1.5">
          <span class="text-[12px] font-medium text-slate-500">连通状态</span>
        </div>
        <div class="text-[15px] font-bold text-slate-800 font-mono tracking-tight">
          {{ state.stats.connectedCount }}<span class="text-[12px] text-slate-400 font-medium ml-1">/ {{ state.stats.totalSources }}</span>
        </div>
      </div>

      <div class="flex flex-col bg-white rounded-[8px] px-5 py-2.5 border border-[#E5E7EB] shadow-[0_1px_2px_0_rgba(0,0,0,0.03)] min-w-[140px]">
        <div class="flex items-center justify-between gap-3 mb-1.5">
          <span class="text-[12px] font-medium text-slate-500">上次同步</span>
        </div>
        <div class="text-[16px] font-bold text-slate-800 font-mono tracking-tight leading-none">
          {{ state.stats.lastSyncTime || '—' }}
        </div>
      </div>

      <div class="flex flex-col bg-white rounded-[8px] px-5 py-2.5 border border-[#E5E7EB] shadow-[0_1px_2px_0_rgba(0,0,0,0.03)] min-w-[120px]">
        <div class="flex items-center justify-between gap-3 mb-1.5">
          <span class="text-[12px] font-medium text-slate-500">待处理</span>
        </div>
        <div class="text-[16px] font-bold text-slate-800 font-mono tracking-tight leading-none">
          {{ state.stats.pendingRecords.toLocaleString() }}
        </div>
      </div>

      <div
        v-if="state.stats.failedRecords > 0"
        class="flex flex-col bg-[#FEF2F2] rounded-[8px] px-5 py-2.5 border border-[#FCA5A5] shadow-[0_1px_2px_0_rgba(220,38,38,0.05)] min-w-[120px]"
      >
        <div class="flex items-center gap-2 mb-1.5">
          <span class="text-[12px] font-bold text-red-600">异常</span>
        </div>
        <div class="text-[16px] font-bold text-red-600 font-mono tracking-tight leading-none">
          {{ state.stats.failedRecords }}
        </div>
      </div>
    </div>

    <div class="flex items-center gap-3 shrink-0">
      <a-select
        v-model:value="state.selectedTier"
        size="small"
        style="width: 120px"
        :disabled="state.activeTab !== 'mongo'"
        :options="tierOptions"
      />

      <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '测试 Mongo + 远端 PG + 本地 PG 连通性'">
        <button
          class="px-5 py-2.5 rounded-[6px] text-[13px] font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 shadow-sm transition-all"
          :disabled="isReadonly || state.isTestingAll"
          @click="handleTestAll"
        >
          测试全连接
        </button>
      </a-tooltip>

      <a-tooltip :title="isReadonly ? '仅 admin 可执行' : `执行同步前预检，不落库（${activeSourceLabel}）`">
        <button
          class="px-5 py-2.5 rounded-[6px] text-[13px] font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 shadow-sm transition-all"
          :disabled="isReadonly || state.isPreflighting"
          @click="handlePreflight"
        >
          试运行
        </button>
      </a-tooltip>

      <a-tooltip :title="isReadonly ? '仅 admin 可执行' : `仅在预检通过后可执行（${activeSourceLabel}）`">
        <button
          class="px-6 py-2.5 rounded-[6px] text-[13px] font-bold text-white bg-[#1677FF] hover:bg-[#0052D9] shadow-sm transition-all border-none"
          :disabled="isReadonly || !hasPreflightPass || state.isSyncing"
          @click="handleExecute"
        >
          执行同步
        </button>
      </a-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { message } from 'ant-design-vue'
import { useDataSync } from '../../composables/useDataSync'

const { state, isReadonly, hasPreflightPass, testAllConnections, runPreflight, executeSync } = useDataSync()

const activeSource = computed(() => (state.activeTab === 'mongo' ? 'mongo' : 'pg'))
const activeSourceLabel = computed(() => (activeSource.value === 'mongo' ? 'Mongo' : 'PG'))
const tierOptions = [
  { label: '全部 Tier', value: 'all' },
  { label: 'Tier1', value: 'tier1' },
  { label: 'Tier2', value: 'tier2' },
  { label: 'Tier3', value: 'tier3' },
]

function parseMinuteOfDay(timeValue: string): number | null {
  const matched = /^(\d{2}):(\d{2})$/.exec(timeValue)
  if (!matched) {
    return null
  }
  const hour = Number(matched[1])
  const minute = Number(matched[2])
  if (Number.isNaN(hour) || Number.isNaN(minute) || hour > 23 || minute > 59) {
    return null
  }
  return hour * 60 + minute
}

function isNowInWindow(start: string, end: string): boolean {
  const startMinute = parseMinuteOfDay(start)
  const endMinute = parseMinuteOfDay(end)
  if (startMinute === null || endMinute === null) {
    return true
  }
  const now = new Date()
  const current = now.getHours() * 60 + now.getMinutes()
  if (startMinute <= endMinute) {
    return current >= startMinute && current <= endMinute
  }
  return current >= startMinute || current <= endMinute
}

const handleTestAll = async () => {
  try {
    const result = await testAllConnections()
    if (result.all_connected) {
      message.success('全连接测试通过')
    } else {
      message.warning(`全连接测试完成：${result.connected_count}/${result.total_sources} 可用`)
    }
  } catch {
    message.error('全连接测试失败')
  }
}

const handlePreflight = async () => {
  try {
    const result = await runPreflight(activeSource.value)
    if (result.executable) {
      message.success(`预检通过，预计影响 ${result.estimated_impact} 条记录`)
    } else {
      message.warning(`预检未通过：${result.blockers.join('；') || '存在阻断项'}`)
    }
  } catch {
    message.error('试运行失败')
  }
}

const handleExecute = async () => {
  try {
    if (state.selectedTier === 'tier3' && activeSource.value === 'mongo') {
      const inWindow = isNowInWindow(
        state.policyForm.night_window_start,
        state.policyForm.night_window_end,
      )
      if (!inWindow) {
        const confirmed = window.confirm(
          `当前不在夜间窗口 ${state.policyForm.night_window_start}-${state.policyForm.night_window_end}，继续执行 Tier3 可能影响线上性能。确认继续吗？`,
        )
        if (!confirmed) {
          return
        }
      }
    }

    if (state.stats.failedRecords > 0) {
      const confirmed = window.confirm(
        `当前存在 ${state.stats.failedRecords} 条失败记录，建议先排查后再执行。确认继续吗？`,
      )
      if (!confirmed) {
        return
      }
    }

    const result = await executeSync(activeSource.value)
    if (result.success) {
      message.success('同步任务已启动')
    } else {
      message.warning(result.error || result.message || '同步任务未启动')
    }
  } catch {
    message.error('执行同步失败')
  }
}
</script>
