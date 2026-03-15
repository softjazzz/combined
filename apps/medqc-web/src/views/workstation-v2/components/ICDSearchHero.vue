<template>
  <div class="relative bg-white border-b border-slate-200/80 pt-10 pb-6 flex flex-col items-center z-20 overflow-hidden">
    <!-- 背景光晕 -->
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] bg-gradient-to-b from-blue-50/80 to-transparent blur-3xl pointer-events-none"></div>

    <!-- Hero 标题 -->
    <div class="relative z-10 text-center mb-6 flex flex-col items-center">
      <div class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-100/50 text-blue-600 text-[12px] font-bold mb-3 shadow-sm">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        DeepCoder 知识引擎
      </div>
      <h1 class="text-3xl font-extrabold text-slate-900 tracking-tight mb-2">
        ICD <span class="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">智能全域检索</span>
      </h1>
      <p class="text-[13px] text-slate-500 font-medium">
        支持编码、名称极速匹配，精准定位诊断与手术
      </p>
    </div>

    <!-- 巨无霸搜索框 -->
    <div class="relative z-10 w-full max-w-3xl px-4 group">
      <SearchOutlined class="absolute left-8 top-1/2 -translate-y-1/2 text-lg text-slate-400 group-focus-within:text-blue-600 transition-colors z-10" />
      <input
        ref="searchInput"
        v-model="localQuery"
        type="text"
        :placeholder="localType === 'icd10' ? '输入诊断名称或 ICD-10 编码...' : '输入手术名称或 ICD-9 编码...'"
        class="w-full pl-12 pr-16 py-4 bg-white border-2 border-slate-200 focus:border-blue-500 rounded-2xl outline-none text-[16px] shadow-[0_4px_20px_rgba(0,0,0,0.03)] focus:shadow-[0_8px_30px_rgba(59,130,246,0.12)] transition-all placeholder:text-slate-400 font-medium text-slate-800"
        @keydown.enter="$emit('search', localQuery)"
        @input="onQueryChange"
      />
      <div class="absolute right-7 top-1/2 -translate-y-1/2 flex gap-1.5">
        <span v-if="localQuery.length > 0" class="text-[12px] text-slate-400 font-medium mr-1">Enter 搜索</span>
        <template v-else>
          <kbd class="px-2 py-1 bg-slate-50 border border-slate-200/80 rounded-md text-[11px] font-mono text-slate-400 font-semibold shadow-sm">Ctrl</kbd>
          <kbd class="px-2 py-1 bg-slate-50 border border-slate-200/80 rounded-md text-[11px] font-mono text-slate-400 font-semibold shadow-sm">K</kbd>
        </template>
      </div>
    </div>

    <!-- 筛选条件 + 统计 -->
    <div class="relative z-10 w-full max-w-3xl px-6 mt-4 flex flex-wrap items-center justify-between gap-4">
      <!-- 分段控制器 -->
      <div class="flex items-center gap-4">
        <div class="flex bg-slate-100/80 p-0.5 rounded-lg border border-slate-200/50">
          <button
            v-for="v in versionTabs"
            :key="v.value"
            :class="[
              localVersion === v.value
                ? 'bg-white text-blue-700 font-bold shadow-[0_1px_2px_rgba(0,0,0,0.04)]'
                : 'text-slate-500 hover:text-slate-800',
              'px-4 py-1.5 text-[12px] font-medium rounded-md transition-all duration-200'
            ]"
            @click="localVersion = v.value; $emit('update:codeVersion', v.value)"
          >
            {{ v.label }}
          </button>
        </div>
        <div class="w-px h-3.5 bg-slate-300"></div>
        <div class="flex bg-slate-100/80 p-0.5 rounded-lg border border-slate-200/50">
          <button
            v-for="t in codeTypeTabs"
            :key="t.value"
            :class="[
              localType === t.value
                ? 'bg-white text-indigo-700 font-bold shadow-[0_1px_2px_rgba(0,0,0,0.04)]'
                : 'text-slate-500 hover:text-slate-800',
              'px-4 py-1.5 text-[12px] font-medium rounded-md transition-all duration-200'
            ]"
            @click="localType = t.value; $emit('update:codeType', t.value)"
          >
            {{ t.label }}
          </button>
        </div>
      </div>

      <!-- 统计标签 -->
      <div class="flex items-center gap-4 text-[12px] font-medium text-slate-500">
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-blue-500"></span>
          ICD-10 <strong class="text-slate-700 ml-0.5">{{ stats.icd10Count?.toLocaleString() || '—' }}</strong>
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
          ICD-9 <strong class="text-slate-700 ml-0.5">{{ stats.icd9Count?.toLocaleString() || '—' }}</strong>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { SearchOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  codeVersion: string
  codeType: string
  searchQuery: string
  stats: { icd10Count?: number; icd9Count?: number }
}>()

const emit = defineEmits<{
  'update:codeVersion': [value: string]
  'update:codeType': [value: string]
  'update:searchQuery': [value: string]
  search: [value: string]
}>()

const localVersion = ref(props.codeVersion)
const localType = ref(props.codeType)
const localQuery = ref(props.searchQuery)
const searchInput = ref<HTMLInputElement>()

const versionTabs = [
  { label: '临床版 ICD-10', value: 'clinical' },
  { label: '医保版 2.0', value: 'insurance' },
]

const codeTypeTabs = [
  { label: '疾病诊断', value: 'icd10' },
  { label: '手术操作 (ICD-9)', value: 'icd9cm3' },
]

// Ctrl+K 快捷键聚焦搜索
onMounted(() => {
  const handler = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      searchInput.value?.focus()
    }
  }
  window.addEventListener('keydown', handler)
})

watch(() => props.codeVersion, (v) => { localVersion.value = v })
watch(() => props.codeType, (v) => { localType.value = v })
watch(() => props.searchQuery, (v) => { localQuery.value = v })

let debounceTimer: ReturnType<typeof setTimeout> | null = null
function onQueryChange() {
  emit('update:searchQuery', localQuery.value)
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    if (localQuery.value.length >= 2) {
      emit('search', localQuery.value)
    }
  }, 300)
}
</script>
