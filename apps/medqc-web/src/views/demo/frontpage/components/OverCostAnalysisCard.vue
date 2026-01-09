<template>
  <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
        <ExclamationCircleOutlined class="text-red-500" />
        超费原因分析
      </h3>
      <a-button size="small" type="link" @click="handleExportReport">
        <DownloadOutlined /> 导出分析报告
      </a-button>
    </div>

    <!-- Summary Stats -->
    <div class="grid grid-cols-3 gap-3 mb-4">
      <div class="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 text-center">
        <div class="text-2xl font-bold text-red-600">{{ lossCount }}</div>
        <div class="text-xs text-red-500">亏损病例</div>
      </div>
      <div class="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3 text-center">
        <div class="text-2xl font-bold text-orange-600">¥{{ totalLossAmount.toLocaleString() }}</div>
        <div class="text-xs text-orange-500">总亏损金额</div>
      </div>
      <div class="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3 text-center">
        <div class="text-2xl font-bold text-yellow-600">{{ avgLossRate.toFixed(1) }}%</div>
        <div class="text-xs text-yellow-500">平均超费率</div>
      </div>
    </div>

    <!-- Reason Distribution -->
    <div class="mb-4">
      <div class="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">超费原因分布</div>
      <div class="space-y-2">
        <div v-for="reason in reasonDistribution" :key="reason.type" class="flex items-center gap-2">
          <div class="w-24 text-xs text-slate-600 dark:text-slate-400 truncate">{{ reason.label }}</div>
          <div class="flex-1 bg-slate-100 dark:bg-slate-700 rounded-full h-4 overflow-hidden">
            <div 
              :class="['h-full rounded-full', reason.color]"
              :style="{ width: `${reason.percentage}%` }"
            ></div>
          </div>
          <div class="w-12 text-xs text-slate-500 text-right">{{ reason.count }}例</div>
        </div>
      </div>
    </div>

    <!-- Top Loss Cases -->
    <div>
      <div class="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">亏损TOP5病例</div>
      <div class="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
        <div 
          v-for="item in topLossCases" 
          :key="item.caseNo"
          class="flex items-center justify-between p-2 bg-slate-50 dark:bg-slate-700/50 rounded-lg text-xs"
        >
          <div class="flex items-center gap-2">
            <span class="text-slate-600 dark:text-slate-300 font-medium">{{ item.caseNo }}</span>
            <span class="text-slate-400">{{ item.drg }}</span>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-slate-500">{{ item.reason }}</span>
            <span class="text-red-600 font-medium">-¥{{ item.lossAmount.toLocaleString() }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Recommendations -->
    <div class="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
      <div class="text-xs font-medium text-blue-700 dark:text-blue-300 mb-1">优化建议</div>
      <ul class="text-xs text-blue-600/80 dark:text-blue-400/80 space-y-1">
        <li>• 加强住院日管理，{{ lossByLOS }}例因住院日超标导致亏损</li>
        <li>• 优化高值耗材使用，{{ lossByMaterial }}例耗材费用占比过高</li>
        <li>• 完善编码质量，{{ lossByCoding }}例存在编码问题影响入组</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ExclamationCircleOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'

const props = defineProps<{
  batchId?: string
}>()

// Mock data - 实际项目中需从后端获取
const lossCount = 23
const totalLossAmount = 185000
const avgLossRate = computed(() => (totalLossAmount / (lossCount * 15000)) * 100)

const lossByLOS = 8
const lossByMaterial = 7
const lossByCoding = 5

const reasonDistribution = computed(() => [
  { type: 'los', label: '住院日偏差', count: 8, percentage: 35, color: 'bg-red-500' },
  { type: 'material', label: '耗材超标', count: 7, percentage: 30, color: 'bg-orange-500' },
  { type: 'coding', label: '编码问题', count: 5, percentage: 22, color: 'bg-yellow-500' },
  { type: 'other', label: '其他原因', count: 3, percentage: 13, color: 'bg-slate-400' }
])

const topLossCases = [
  { caseNo: '#2026010105', drg: 'BR23', reason: '住院日超标', lossAmount: 15800 },
  { caseNo: '#2026010089', drg: 'IC19', reason: '耗材超标', lossAmount: 12500 },
  { caseNo: '#2026010067', drg: 'GD15', reason: '住院日超标', lossAmount: 9800 },
  { caseNo: '#2026010034', drg: 'EB13', reason: '编码问题', lossAmount: 8200 },
  { caseNo: '#2026010022', drg: 'FM19', reason: '耗材超标', lossAmount: 7500 }
]

const handleExportReport = () => {
  message.success('超费分析报告导出成功')
  // TODO: 实现实际导出逻辑
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 2px;
}
</style>
