<template>
  <div class="flex-1 flex flex-col bg-white overflow-hidden">
    <!-- Header -->
    <div class="px-5 py-3 border-b border-slate-100 bg-white flex justify-between items-center shrink-0">
      <div class="flex items-center gap-2">
        <div class="flex items-center">
          <span class="relative flex h-2 w-2 mr-2">
            <span
              v-if="state.isSyncing"
              class="animate-ping absolute inline-flex h-full w-full rounded-full bg-slate-400 opacity-75"
            />
            <span
              class="relative inline-flex rounded-full h-2 w-2"
              :class="state.isSyncing ? 'bg-slate-600' : 'bg-slate-200'"
            />
          </span>
          <h2 class="text-[13px] font-semibold text-slate-900 tracking-tight">
            执行日志
          </h2>
        </div>
      </div>
      <button
        class="text-[11px] text-slate-400 hover:text-slate-800 transition-colors font-medium"
        @click="handleClear"
      >
        Clear
      </button>
    </div>

    <!-- Active Tasks Progress (Minimal Progress Line) -->
    <div
      v-if="state.isSyncing"
      class="px-5 py-2.5 bg-slate-50 border-b border-slate-100 shrink-0"
    >
      <div class="flex justify-between items-end mb-1.5">
        <span class="text-[11px] font-medium text-slate-700 font-mono tracking-tight">Syncing his_emr...</span>
        <span class="text-[10px] font-semibold text-slate-500">45%</span>
      </div>
      <div class="w-full bg-slate-200 rounded-full h-1 overflow-hidden">
        <div
          class="bg-slate-800 h-1 rounded-full transition-all duration-300"
          style="width: 45%"
        />
      </div>
    </div>

    <!-- Logs Body (Light theme, Airbyte/Fivetran style) -->
    <div class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-2 text-[11.5px] font-mono bg-[#FAFAFA]">
      <div class="text-slate-400 pb-1 border-b border-slate-100 border-dashed">
        > Ready. Waiting for master signal...
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

      <!-- Dry Run Results View (Minimalist Info Block) -->
      <div
        v-if="state.dryRunResults && !state.isSyncing"
        class="mt-4 p-3 bg-white border border-slate-200 shadow-sm rounded-md font-sans"
      >
        <div class="text-[11.5px] font-semibold text-slate-800 mb-1.5 flex items-center gap-1.5">
          <svg
            class="w-3.5 h-3.5 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          ><path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          /></svg>
          试运行准入评估通过
        </div>
        <div class="text-[11px] text-slate-600 space-y-1">
          <div class="flex justify-between">
            <span class="text-slate-500">评估受影响记录:</span>
            <span class="font-mono font-medium text-slate-800">{{ state.dryRunResults.estimatedImpact }}</span>
          </div>
        </div>
        
        <div class="mt-2.5 pt-2.5 border-t border-slate-100">
          <div class="text-[11px] font-medium text-slate-500 mb-1">
            风险提示:
          </div>
          <ul class="list-disc pl-4 text-[10.5px] text-slate-600 space-y-0.5">
            <li
              v-for="w in state.dryRunResults.warnings"
              :key="w"
            >
              {{ w }}
            </li>
          </ul>
        </div>
        
        <div class="mt-3">
          <button
            class="w-full py-1.5 text-[11.5px] font-medium text-white bg-slate-900 border border-slate-800 hover:bg-slate-800 rounded transition-colors shadow-sm"
            @click="handleExecute"
          >
            确认安全，提交流水线
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useDataSync } from '../../composables/useDataSync'
const { state, executeSync } = useDataSync()

const handleExecute = () => {
  executeSync()
}

const handleClear = () => {
  state.currentRunLog.splice(0)
}
</script>
