<template>
  <div v-if="drgResult" class="space-y-6 pb-10">
    <!-- DRG Key Metrics -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- DRG Code -->
      <div
        class="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-5 text-white shadow-lg shadow-blue-500/30 flex flex-col justify-between relative overflow-hidden group"
      >
        <div
          class="absolute right-0 top-0 opacity-10 transform translate-x-1/3 -translate-y-1/3 transition-transform group-hover:scale-110 duration-500"
        >
          <AppstoreOutlined style="font-size: 100px" />
        </div>
        <div class="z-10">
          <div class="text-blue-100 text-xs font-semibold uppercase tracking-wider mb-2">
            DRG 组编码
          </div>
          <div class="text-4xl font-bold font-mono tracking-tight">
            {{ drgResult.code }}
          </div>
          <div class="text-blue-100 mt-2 font-medium truncate" :title="drgResult.name">
            {{ drgResult.name }}
          </div>
        </div>
        <div
          class="z-10 mt-4 flex items-center gap-2 text-xs bg-white/20 w-fit px-2 py-1 rounded-lg backdrop-blur-sm"
        >
          <span>RW: {{ drgResult.weight }}</span>
        </div>
      </div>

      <!-- Payment Prediction -->
      <div
        class="bg-white dark:bg-slate-700/50 rounded-xl p-5 border border-slate-200 dark:border-slate-600 shadow-sm flex flex-col justify-between"
      >
        <div class="flex justify-between items-start">
          <div>
            <div
              class="text-slate-500 dark:text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2"
            >
              预估支付额
            </div>
            <div class="text-3xl font-bold text-slate-800 dark:text-white font-mono">
              ¥ {{ drgResult.payment?.toLocaleString() }}
            </div>
          </div>
          <div
            class="w-10 h-10 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center text-green-500"
          >
            <DollarOutlined class="text-xl" />
          </div>
        </div>
        <div class="mt-4 text-xs text-slate-500 flex items-center justify-between">
          <span
            >实际费用:
            <span class="font-medium"
              >¥ {{ drgResult.actual_cost?.toLocaleString() || '-' }}</span
            ></span
          >
          <span :class="drgResult.profit >= 0 ? 'text-green-500' : 'text-red-500'">
            {{ drgResult.profit >= 0 ? '+' : '' }}{{ drgResult.profit?.toLocaleString() }}
          </span>
        </div>
        <!-- Cost Consumption Rate Progress -->
        <div v-if="drgResult.payment > 0" class="mt-3">
          <div class="flex justify-between text-[10px] text-slate-400 mb-1">
            <span>费用消耗率</span>
            <span>{{ Math.round((drgResult.actual_cost / drgResult.payment) * 100) }}%</span>
          </div>
          <div class="w-full bg-slate-100 dark:bg-slate-600 h-1.5 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-1000"
              :class="
                drgResult.actual_cost / drgResult.payment > 1
                  ? 'bg-red-500'
                  : drgResult.actual_cost / drgResult.payment > 0.8
                    ? 'bg-yellow-500'
                    : 'bg-green-500'
              "
              :style="{
                width: Math.min((drgResult.actual_cost / drgResult.payment) * 100, 100) + '%',
              }"
            />
          </div>
        </div>
      </div>

      <!-- CMI/Efficiency -->
      <div
        class="bg-white dark:bg-slate-700/50 rounded-xl p-5 border border-slate-200 dark:border-slate-600 shadow-sm flex flex-col justify-between"
      >
        <div class="flex justify-between items-start">
          <div>
            <div
              class="text-slate-500 dark:text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2"
            >
              盈亏分析
            </div>
            <div
              class="text-3xl font-bold font-mono"
              :class="drgResult.profit >= 0 ? 'text-green-600' : 'text-red-600'"
            >
              {{ drgResult.profit >= 0 ? '盈利' : '亏损' }}
            </div>
          </div>
          <div
            class="w-10 h-10 rounded-full bg-orange-50 dark:bg-orange-900/20 flex items-center justify-center text-orange-500"
          >
            <RiseOutlined v-if="drgResult.profit >= 0" class="text-xl" />
            <FallOutlined v-else class="text-xl" />
          </div>
        </div>
        <div class="mt-4 w-full bg-slate-100 dark:bg-slate-600 h-2 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-1000"
            :class="drgResult.profit >= 0 ? 'bg-green-500' : 'bg-red-500'"
            :style="{
              width:
                Math.min(Math.abs((drgResult.profit / (drgResult.payment || 1)) * 100), 100) + '%',
            }"
          />
        </div>
      </div>
    </div>

    <!-- Grouping Details -->
    <div
      class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-6 border border-slate-100 dark:border-slate-700"
    >
      <h4 class="font-bold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
        <CalculatorOutlined class="text-blue-500" /> 入组详情
      </h4>
      <div class="space-y-4">
        <div
          class="flex flex-col md:flex-row md:items-center gap-4 p-4 bg-white dark:bg-slate-800 rounded-lg border border-slate-100 dark:border-slate-600"
        >
          <span class="text-slate-500 text-sm whitespace-nowrap w-20">主诊断</span>
          <div class="flex-1 font-medium text-slate-800 dark:text-white flex items-center gap-2">
            <span
              class="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-mono dark:bg-blue-900 dark:text-blue-300"
            >
              {{ mainDiagnosisCode }}
            </span>
            {{ mainDiagnosisText }}
          </div>
        </div>
        <div
          class="flex flex-col md:flex-row md:items-center gap-4 p-4 bg-white dark:bg-slate-800 rounded-lg border border-slate-100 dark:border-slate-600"
        >
          <span class="text-slate-500 text-sm whitespace-nowrap w-20">主手术</span>
          <div class="flex-1 font-medium text-slate-800 dark:text-white flex items-center gap-2">
            <template v-if="mainProcedureCode">
              <span
                class="bg-orange-100 text-orange-700 px-2 py-0.5 rounded text-xs font-mono dark:bg-orange-900 dark:text-orange-300"
              >
                {{ mainProcedureCode }}
              </span>
              {{ mainProcedureName }}
            </template>
            <span v-else class="text-slate-400 italic">无手术操作</span>
          </div>
        </div>
        <div
          v-if="drgResult.messages && drgResult.messages.length > 0"
          class="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-100 dark:border-yellow-900/40"
        >
          <div class="text-yellow-700 dark:text-yellow-500 font-medium text-sm mb-2">入组提示</div>
          <ul class="list-disc list-inside text-xs text-yellow-600 dark:text-yellow-400 space-y-1">
            <li v-for="(msg, idx) in drgResult.messages" :key="idx">
              {{ msg }}
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex justify-center pt-4">
      <button
        class="bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-blue-600 px-6 py-2 rounded-xl text-sm font-medium transition-all shadow-sm flex items-center gap-2 group"
        @click="$emit('openOptimization')"
      >
        <ThunderboltOutlined class="group-hover:text-amber-500 transition-colors" />
        AI 编码优化建议
      </button>
    </div>
  </div>

  <!-- Empty State -->
  <div v-else class="h-full flex flex-col items-center justify-center text-center p-6">
    <div
      class="w-20 h-20 bg-blue-50 dark:bg-blue-900/20 rounded-2xl mb-5 flex items-center justify-center"
    >
      <AppstoreOutlined class="text-4xl text-blue-500" />
    </div>
    <h3 class="text-lg font-semibold text-slate-800 dark:text-white mb-2">DRG/DIP 智能分组</h3>
    <p class="text-sm text-slate-500 dark:text-slate-400 mb-6 max-w-xs">
      基于病案首页数据进行预分组，预测入组结果、RW值及支付费用。
    </p>
    <button
      :disabled="!hasFrontpage"
      class="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl text-sm font-medium transition-all shadow-lg shadow-blue-500/25 flex items-center gap-2"
      @click="$emit('group')"
    >
      <CalculatorOutlined />
      {{ loading ? '正在分组...' : '开始分组预测' }}
    </button>
    <p v-if="!hasFrontpage" class="text-xs text-orange-500 mt-3">请先完成 AI 结构化提取</p>
  </div>
</template>

<script setup lang="ts">
import {
  AppstoreOutlined,
  DollarOutlined,
  RiseOutlined,
  FallOutlined,
  CalculatorOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'

export interface DRGResult {
  code: string
  name: string
  weight: number
  payment: number
  actual_cost: number
  profit: number
  messages?: string[]
}

defineProps<{
  drgResult: DRGResult | null
  loading: boolean
  hasFrontpage: boolean
  mainDiagnosisCode?: string
  mainDiagnosisText?: string
  mainProcedureCode?: string
  mainProcedureName?: string
}>()

defineEmits<{
  (e: 'group'): void
  (e: 'openOptimization'): void
}>()
</script>
