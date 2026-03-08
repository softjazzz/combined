<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

    <!-- 卡片 2: 缺陷级别 (进度条) -->
    <div class="bg-white p-6 rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 group hover:shadow-lg transition-shadow duration-300">
      <div class="flex justify-between items-start mb-4">
        <h3 class="text-slate-700 font-semibold text-sm">缺陷级别分布</h3>
        <div class="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center text-slate-400 group-hover:text-orange-500 group-hover:bg-orange-50 transition-colors">
          <ExclamationCircleOutlined />
        </div>
      </div>
      <div class="space-y-4">
        <div>
          <div class="flex justify-between text-xs mb-1.5">
            <span class="text-slate-500 font-medium">严重缺陷 (阻断)</span>
            <span class="text-red-500 font-bold">{{ statistics.critical }}</span>
          </div>
          <div class="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
            <div class="bg-red-500 h-2.5 rounded-full transition-all duration-1000 ease-out shadow-sm" :style="{ width: `${(statistics.critical / (statistics.total || 1)) * 100}%` }"></div>
          </div>
        </div>
        <div>
          <div class="flex justify-between text-xs mb-1.5">
            <span class="text-slate-500 font-medium">一般缺陷 (警告)</span>
            <span class="text-orange-400 font-bold">{{ Math.floor(statistics.total * 0.4) }}</span>
          </div>
          <div class="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
            <div class="bg-orange-400 h-2.5 rounded-full transition-all duration-1000 ease-out shadow-sm" :style="{ width: '40%' }"></div>
          </div>
        </div>
        <div>
          <div class="flex justify-between text-xs mb-1.5">
            <span class="text-slate-500 font-medium">轻微缺陷 (提示)</span>
            <span class="text-blue-400 font-bold">{{ Math.floor(statistics.total * 0.3) }}</span>
          </div>
          <div class="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
            <div class="bg-blue-400 h-2.5 rounded-full transition-all duration-1000 ease-out shadow-sm" :style="{ width: '30%' }"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 卡片 3: 规则分类 (极简数字) -->
    <div class="bg-white p-6 rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 flex flex-col justify-between group hover:shadow-lg transition-shadow duration-300">
      <div class="flex justify-between items-start">
        <h3 class="text-slate-700 font-semibold text-sm">规则分类统计</h3>
        <div class="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center text-slate-400 group-hover:text-violet-500 group-hover:bg-violet-50 transition-colors">
          <AppstoreOutlined />
        </div>
      </div>
      <div class="grid grid-cols-3 gap-3 mt-4">
        <div class="text-center p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-blue-200 hover:bg-blue-50/50 transition-colors">
          <div class="text-2xl font-bold text-slate-800">{{ statistics.categories }}</div>
          <div class="text-[11px] font-medium text-slate-400 mt-1">完整性</div>
        </div>
        <div class="text-center p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-green-200 hover:bg-green-50/50 transition-colors">
          <div class="text-2xl font-bold text-slate-800">{{ Math.floor(statistics.total * 0.2) }}</div>
          <div class="text-[11px] font-medium text-slate-400 mt-1">一致性</div>
        </div>
        <div class="text-center p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-purple-200 hover:bg-purple-50/50 transition-colors">
          <div class="text-2xl font-bold text-slate-800">{{ Math.floor(statistics.total * 0.15) }}</div>
          <div class="text-[11px] font-medium text-slate-400 mt-1">合理性</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  ExclamationCircleOutlined,
  AppstoreOutlined
} from '@ant-design/icons-vue'

interface Statistics {
  total: number
  active: number
  critical: number
  categories: number
}

defineProps<{
  statistics: Statistics
}>()
</script>
