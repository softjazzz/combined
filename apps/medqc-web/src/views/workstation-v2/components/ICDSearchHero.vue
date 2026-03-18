<template>
  <div class="relative flex flex-col items-center overflow-hidden border-b border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(246,250,255,0.95)_100%)] pt-7 pb-5 z-20">
    <div class="pointer-events-none absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.12),transparent_68%)]"></div>

    <div class="relative z-10 mb-5 flex flex-col items-center text-center">
      <div class="mb-2 inline-flex items-center gap-1.5 rounded-full border border-sky-100 bg-white/90 px-3 py-1 text-[11px] font-semibold text-sky-700 shadow-[0_8px_20px_rgba(148,163,184,0.10)]">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        AI 智能编码引擎
      </div>
      <h1 class="mb-1 text-[28px] font-black tracking-[-0.03em] text-slate-900">
        ICD <span class="bg-gradient-to-r from-sky-600 to-cyan-600 bg-clip-text text-transparent">智能全域检索</span>
      </h1>
      <p class="text-[13px] font-medium text-slate-500">
        支持编码、名称极速匹配，精准定位诊断与手术
      </p>
    </div>

    <div class="group relative z-10 w-full max-w-3xl px-4">
      <SearchOutlined class="absolute left-8 top-1/2 z-10 -translate-y-1/2 text-lg text-slate-400 transition-colors group-focus-within:text-sky-600" />
      <input
        ref="searchInput"
        v-model="localQuery"
        type="text"
        :placeholder="localType === 'icd10' ? '输入诊断名称或 ICD-10 编码...' : '输入手术名称或 ICD-9 编码...'"
        class="w-full rounded-[22px] border border-slate-200 bg-white/95 py-3.5 pl-12 pr-16 text-[15px] font-medium text-slate-800 outline-none transition-all placeholder:text-slate-400 shadow-[0_14px_30px_rgba(148,163,184,0.10)] focus:border-sky-400 focus:shadow-[0_18px_36px_rgba(14,165,233,0.14)]"
        @keydown.enter="$emit('search', localQuery)"
        @input="onQueryChange"
      />
      <div class="absolute right-7 top-1/2 flex -translate-y-1/2 gap-1.5">
        <span v-if="localQuery.length > 0" class="mr-1 text-[12px] font-medium text-slate-400">Enter 搜索</span>
        <template v-else>
          <kbd class="rounded-md border border-slate-200/80 bg-slate-50 px-2 py-1 font-mono text-[11px] font-semibold text-slate-400 shadow-sm">Ctrl</kbd>
          <kbd class="rounded-md border border-slate-200/80 bg-slate-50 px-2 py-1 font-mono text-[11px] font-semibold text-slate-400 shadow-sm">K</kbd>
        </template>
      </div>
    </div>

    <div class="relative z-10 mt-4 flex w-full max-w-3xl flex-wrap items-center justify-center gap-4 px-6">
      <div class="flex rounded-2xl border border-slate-200/80 bg-white/80 p-1 shadow-[0_8px_22px_rgba(148,163,184,0.08)]">
        <button
          v-for="v in versionTabs"
          :key="v.value"
          :class="[
            localVersion === v.value
              ? 'bg-sky-50 text-sky-700 font-semibold shadow-sm ring-1 ring-sky-100'
              : 'text-slate-500 hover:text-slate-700 font-semibold',
            'rounded-lg px-5 py-2 text-sm transition-all duration-200',
          ]"
          @click="localVersion = v.value; $emit('update:codeVersion', v.value)"
        >
          {{ v.label }}
        </button>
      </div>

      <div class="h-5 w-px bg-slate-300"></div>

      <div class="flex rounded-2xl border border-slate-200/80 bg-white/80 p-1 shadow-[0_8px_22px_rgba(148,163,184,0.08)]">
        <button
          v-for="t in codeTypeTabs"
          :key="t.value"
          :class="[
            localType === t.value
              ? 'bg-sky-50 text-sky-700 font-semibold shadow-sm ring-1 ring-sky-100'
              : 'text-slate-500 hover:text-slate-700 font-semibold',
            'rounded-lg px-5 py-2 text-sm transition-all duration-200',
          ]"
          @click="localType = t.value; $emit('update:codeType', t.value)"
        >
          {{ t.label }}
        </button>
      </div>
    </div>

    <div class="relative z-10 mt-3 flex items-center justify-center gap-6 text-sm font-semibold text-slate-500">
      <span class="flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full bg-sky-500"></span>
        ICD-10 诊断 <strong class="text-slate-700">{{ stats.icd10Count?.toLocaleString() || '--' }}</strong>
      </span>
      <span class="h-4 w-px bg-slate-300"></span>
      <span class="flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
        ICD-9 手术 <strong class="text-slate-700">{{ stats.icd9Count?.toLocaleString() || '--' }}</strong>
      </span>
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
