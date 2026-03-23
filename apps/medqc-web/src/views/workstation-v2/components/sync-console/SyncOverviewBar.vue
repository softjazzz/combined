<template>
  <div class="flex-shrink-0 flex flex-col lg:flex-row lg:items-center justify-between gap-5 w-full">
    <!-- 左：标题与环境 -->
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
          <span class="text-[12px] font-medium text-slate-400">本地环境</span>
        </div>
      </div>
    </div>

    <!-- 中：状态数据看板 (独立白底卡片) -->
    <div class="flex items-center gap-4 flex-1 lg:justify-end pr-4">
      <!-- Metric Card 1 -->
      <div class="flex flex-col bg-white rounded-[8px] px-5 py-2.5 border border-[#E5E7EB] shadow-[0_1px_2px_0_rgba(0,0,0,0.03)] min-w-[120px]">
        <div class="flex items-center justify-between gap-3 mb-1.5">
          <span class="text-[12px] font-medium text-slate-500">连通状态</span>
          <span class="relative flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
        </div>
        <div class="text-[15px] font-bold text-slate-800 font-mono tracking-tight">
          {{ state.stats.connectedCount }}<span class="text-[12px] text-slate-400 font-medium ml-1">/ {{ state.stats.totalSources }}</span>
        </div>
      </div>
        
      <!-- Metric Card 2 -->
      <div class="flex flex-col bg-white rounded-[8px] px-5 py-2.5 border border-[#E5E7EB] shadow-[0_1px_2px_0_rgba(0,0,0,0.03)] min-w-[140px]">
        <div class="flex items-center justify-between gap-3 mb-1.5">
          <span class="text-[12px] font-medium text-slate-500">上次同步</span>
        </div>
        <div class="text-[16px] font-bold text-slate-800 font-mono tracking-tight shadow-none leading-none">
          {{ state.stats.lastSyncTime || '—' }}
        </div>
      </div>

      <!-- Metric Card 3 -->
      <div class="flex flex-col bg-white rounded-[8px] px-5 py-2.5 border border-[#E5E7EB] shadow-[0_1px_2px_0_rgba(0,0,0,0.03)] min-w-[120px]">
        <div class="flex items-center justify-between gap-3 mb-1.5">
          <span class="text-[12px] font-medium text-slate-500">待处理</span>
        </div>
        <div class="text-[16px] font-bold text-slate-800 font-mono tracking-tight leading-none">
          {{ state.stats.pendingRecords.toLocaleString() }}
        </div>
      </div>

      <!-- Metric Card 4 -->
      <div
        v-if="state.stats.failedRecords > 0"
        class="flex flex-col bg-[#FEF2F2] rounded-[8px] px-5 py-2.5 border border-[#FCA5A5] shadow-[0_1px_2px_0_rgba(220,38,38,0.05)] min-w-[120px]"
      >
        <div class="flex items-center gap-2 mb-1.5">
          <svg
            class="w-3.5 h-3.5 text-red-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          ><path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          /></svg>
          <span class="text-[12px] font-bold text-red-600">异常</span>
        </div>
        <div class="text-[16px] font-bold text-red-600 font-mono tracking-tight leading-none">
          {{ state.stats.failedRecords }}
        </div>
      </div>
    </div>

    <!-- 右：主次按钮明确区分 -->
    <div class="flex items-center gap-3 shrink-0">
      <!-- Secondary Button -->
      <button class="px-5 py-2.5 rounded-[6px] text-[13px] font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-slate-200">
        测试全连接
      </button>
      <!-- Secondary Button -->
      <button
        class="px-5 py-2.5 rounded-[6px] text-[13px] font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 shadow-sm transition-all flex items-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-slate-200"
        :class="{'opacity-70 pointer-events-none': state.isSyncing}"
        @click="handleDryRun"
      >
        <svg
          v-if="state.isSyncing"
          class="animate-spin w-3.5 h-3.5"
          fill="none"
          viewBox="0 0 24 24"
        ><circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        /><path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        /></svg>
        试运行
      </button>
      <!-- Primary CTA -->
      <button
        class="px-6 py-2.5 rounded-[6px] text-[13px] font-bold text-white bg-[#1677FF] hover:bg-[#0052D9] shadow-sm transition-all border-none focus:outline-none focus:ring-2 focus:ring-[#1677FF]/50"
        :disabled="!state.dryRunResults || state.isSyncing"
        @click="handleExecute"
      >
        执行同步
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useDataSync } from '../../composables/useDataSync'
const { state, triggerDryRun, executeSync } = useDataSync()

const handleDryRun = () => {
  triggerDryRun()
}

const handleExecute = () => {
  executeSync()
}
</script>
