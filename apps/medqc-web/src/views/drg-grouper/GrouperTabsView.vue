<template>
  <div class="h-screen bg-slate-50 flex flex-col font-sans overflow-hidden">
    <!-- 顶部 Header -->
    <div class="bg-white px-8 py-4 border-b border-slate-200/80 flex items-center gap-8 shrink-0 z-20">
      <!-- 左侧标题 -->
      <div class="flex items-center gap-3 shrink-0">
        <div class="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center shadow-sm">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
        </div>
        <h1 class="text-xl font-extrabold text-slate-900 tracking-tight">医保分组器</h1>
      </div>

      <!-- Tab 切换器 -->
      <div class="flex bg-slate-100 p-1.5 rounded-xl border border-slate-200/60 gap-1">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="px-6 py-2.5 rounded-lg text-[15px] font-semibold transition-all flex items-center gap-2.5 cursor-pointer whitespace-nowrap"
          :class="activeTab === tab.key
            ? 'bg-white shadow-md ring-1 ring-black/[0.04] ' + tab.activeText
            : 'text-slate-400 hover:text-slate-600 hover:bg-white/50'"
          @click="activeTab = tab.key"
        >
          <!-- CHS-DRG 图标 -->
          <svg v-if="tab.icon === 'drg'" class="w-[18px] h-[18px]" :class="activeTab === tab.key ? tab.iconColor : 'text-slate-300'" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" /></svg>
          <!-- CN-DRG 图标 (绩效监测) -->
          <svg v-else-if="tab.icon === 'cndrg'" class="w-[18px] h-[18px]" :class="activeTab === tab.key ? tab.iconColor : 'text-slate-300'" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
          <!-- DIP 图标 -->
          <svg v-else class="w-[18px] h-[18px]" :class="activeTab === tab.key ? tab.iconColor : 'text-slate-300'" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
          {{ tab.label }}
          <span class="text-[12px] font-mono font-normal px-1.5 py-0.5 rounded"
            :class="activeTab === tab.key ? tab.badgeStyle : 'text-slate-300 bg-transparent'">
            {{ tab.version }}
          </span>
        </button>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="flex-1 overflow-hidden">
      <DrgGrouperView v-if="activeTab === 'drg'" />
      <CnDrgGrouperView v-if="activeTab === 'cndrg'" />
      <DipGrouperView v-if="activeTab === 'dip'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import DrgGrouperView from './DrgGrouperView.vue'
import CnDrgGrouperView from './CnDrgGrouperView.vue'
import DipGrouperView from './DipGrouperView.vue'

const tabs = [
  {
    key: 'drg', label: 'CHS-DRG', version: '2.0 四川',
    icon: 'drg',
    activeText: 'text-blue-700',
    iconColor: 'text-blue-500',
    badgeStyle: 'text-blue-500 bg-blue-50',
  },
  {
    key: 'cndrg', label: 'CN-DRG', version: '2023 绩效',
    icon: 'cndrg',
    activeText: 'text-amber-700',
    iconColor: 'text-amber-500',
    badgeStyle: 'text-amber-500 bg-amber-50',
  },
  {
    key: 'dip', label: 'DIP 分组', version: '四川 DIP',
    icon: 'dip',
    activeText: 'text-emerald-700',
    iconColor: 'text-emerald-500',
    badgeStyle: 'text-emerald-500 bg-emerald-50',
  },
]

const activeTab = ref('drg')
</script>

