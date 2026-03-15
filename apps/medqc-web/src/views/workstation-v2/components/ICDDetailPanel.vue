<template>
  <div class="h-full bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
    <!-- 空状态 -->
    <div v-if="!selectedCode" class="flex-1 flex flex-col items-center justify-center px-6 py-16 text-center">
      <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center mb-4">
        <svg class="w-8 h-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10 21h7a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v11m0 5l4.879-4.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242z" />
        </svg>
      </div>
      <h4 class="text-[15px] font-semibold text-slate-700 mb-2">选择编码查看详情</h4>
      <p class="text-[13px] text-slate-400 leading-relaxed">从左侧列表点击任意编码<br/>即可在此处查看完整信息</p>
    </div>

    <!-- 已选编码：知识卡片 -->
    <template v-else>
      <!-- 卡片头部 -->
      <div class="p-6 border-b border-slate-100 bg-gradient-to-b from-slate-50/50 to-white">
        <div class="flex items-start justify-between mb-3">
          <span
            :class="[
              'px-2.5 py-1 text-[11px] font-bold rounded-md border',
              selectedCode.type === 'icd10'
                ? 'bg-indigo-50 text-indigo-600 border-indigo-100/50'
                : 'bg-emerald-50 text-emerald-600 border-emerald-100/50'
            ]"
          >
            {{ selectedCode.type === 'icd10' ? 'ICD-10 诊断' : 'ICD-9-CM-3 手术' }}
          </span>

          <!-- 操作按钮组 -->
          <div class="flex items-center gap-2">
            <button
              @click="$emit('copy', selectedCode.code)"
              class="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:border-blue-400 hover:text-blue-600 text-slate-600 text-[12px] font-semibold rounded-lg shadow-sm transition-all cursor-pointer group"
            >
              <CopyOutlined class="text-slate-400 group-hover:text-blue-500 transition-colors" />
              复制
            </button>
            <button
              v-if="allowApply"
              @click="$emit('apply', selectedCode)"
              class="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-[12px] font-semibold rounded-lg shadow-sm transition-all cursor-pointer"
            >
              <CheckCircleOutlined />
              {{ applyLabel || '采用' }}
            </button>
          </div>
        </div>

        <!-- 大号编码 + 名称 -->
        <div
          class="font-mono text-3xl font-extrabold tracking-tight mb-2"
          :class="selectedCode.type === 'icd10' ? 'text-blue-700' : 'text-emerald-700'"
        >
          {{ selectedCode.code }}
        </div>
        <h2 class="text-lg font-bold text-slate-900 leading-snug">
          {{ selectedCode.name }}
        </h2>
      </div>

      <!-- 卡片内容区（可滚动） -->
      <div class="flex-1 p-6 overflow-y-auto custom-scrollbar space-y-5">
        <!-- 层级归属 -->
        <div v-if="selectedCode.category_path?.length">
          <h4 class="text-[12px] font-bold text-slate-400 uppercase tracking-wider mb-2">层级归属</h4>
          <div class="flex flex-col gap-1.5 text-[13px]">
            <div
              v-for="(item, i) in selectedCode.category_path"
              :key="i"
              class="flex items-center gap-2 text-slate-500"
            >
              <span class="font-mono text-slate-400 text-[12px]">{{ i === selectedCode.category_path.length - 1 ? '└' : '├' }}</span>
              <span :class="i === selectedCode.category_path.length - 1 ? 'font-medium text-slate-700' : ''">{{ item }}</span>
            </div>
          </div>
        </div>

        <!-- 版本对照 -->
        <div v-if="selectedCode.mapped_code">
          <div class="w-full h-px bg-slate-100 mb-5"></div>
          <h4 class="text-[12px] font-bold text-slate-400 uppercase tracking-wider mb-2">版本对照</h4>
          <div
            :class="[
              'rounded-lg p-3 text-[13px] border',
              selectedCode.is_diff
                ? 'bg-amber-50 border-amber-100'
                : 'bg-slate-50 border-slate-100'
            ]"
          >
            <div class="flex items-center gap-3 mb-1">
              <span class="font-mono font-semibold text-slate-700">{{ selectedCode.code }}</span>
              <span class="text-slate-400">→</span>
              <span class="font-mono font-semibold" :class="selectedCode.is_diff ? 'text-amber-700' : 'text-slate-700'">
                {{ selectedCode.mapped_code }}
              </span>
            </div>
            <div class="flex items-center gap-1 text-[12px]">
              <span :class="selectedCode.is_diff ? 'text-amber-600' : 'text-emerald-600'">
                {{ selectedCode.is_diff ? '⚠ 编码不同' : '✓ 编码相同' }}
              </span>
              <span v-if="selectedCode.mapped_name && selectedCode.is_diff" class="text-amber-600 ml-2">
                {{ selectedCode.mapped_name }}
              </span>
            </div>
          </div>
        </div>

        <!-- 包含说明 -->
        <div v-if="selectedCode.inclusions?.length">
          <div class="w-full h-px bg-slate-100 mb-5"></div>
          <h4 class="text-[12px] font-bold text-slate-400 uppercase tracking-wider mb-2">
            <span class="text-emerald-500 mr-1">●</span> 包含
          </h4>
          <ul class="space-y-1 pl-4 text-[13px] text-slate-600 list-disc marker:text-emerald-400">
            <li v-for="(item, i) in selectedCode.inclusions" :key="i">{{ item }}</li>
          </ul>
        </div>

        <!-- 排除说明 -->
        <div v-if="selectedCode.exclusions?.length">
          <div class="w-full h-px bg-slate-100 mb-5"></div>
          <h4 class="text-[12px] font-bold text-slate-400 uppercase tracking-wider mb-2">
            <span class="text-red-500 mr-1">●</span> 排除
          </h4>
          <ul class="space-y-1 pl-4 text-[13px] text-slate-600 list-disc marker:text-red-400">
            <li v-for="(item, i) in selectedCode.exclusions" :key="i">{{ item }}</li>
          </ul>
        </div>

        <!-- 编码规则提示（结构占位） -->
        <div v-if="!selectedCode.category_path?.length && !selectedCode.mapped_code && !selectedCode.inclusions?.length">
          <div class="w-full h-px bg-slate-100 mb-5"></div>
          <h4 class="text-[12px] font-bold text-slate-400 uppercase tracking-wider mb-2">编码信息</h4>
          <div class="bg-slate-50 border border-slate-100 rounded-lg p-3 text-[13px] text-slate-500 leading-relaxed">
            点击树形节点中的叶子编码，可查看更多层级归属和版本对照信息。
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  CopyOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'

export interface ICDCodeDetail {
  code: string
  name: string
  type: 'icd10' | 'icd9cm3'
  category_path?: string[]
  mapped_code?: string
  mapped_name?: string
  mapped_version?: string
  is_diff?: boolean
  inclusions?: string[]
  exclusions?: string[]
}

defineProps<{
  selectedCode: ICDCodeDetail | null
  allowApply?: boolean
  applyLabel?: string
}>()

defineEmits<{
  copy: [code: string]
  apply: [detail: ICDCodeDetail]
}>()
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}
</style>
