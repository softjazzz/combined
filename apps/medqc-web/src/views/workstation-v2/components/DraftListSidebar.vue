<template>
  <div class="draft-list-sidebar w-80 bg-white border-r border-slate-200 dark:bg-slate-900 dark:border-slate-800 flex flex-col h-full flex-shrink-0">
    <!-- Header -->
    <div class="p-4 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <ProfileOutlined class="text-blue-500" /> 
          提取队列
        </h2>
        <span class="bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full text-xs font-medium dark:bg-blue-900/30 dark:text-blue-400">
          {{ filteredRecords.length }}
        </span>
      </div>
      
      <!-- Search -->
      <div class="relative">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
          <SearchOutlined />
        </span>
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="搜索姓名、科室或病案号..." 
          class="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 transition-all placeholder:text-slate-400"
        >
      </div>
      
      <!-- Tags filter -->
      <div class="flex gap-2 mt-3 overflow-x-auto pb-1 hide-scrollbar">
        <button 
          v-for="tab in filterTabs" 
          :key="tab.value"
          @click="currentFilter = tab.value"
          class="px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors"
          :class="[
            currentFilter === tab.value 
              ? 'bg-blue-500 text-white shadow-sm shadow-blue-500/20' 
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700'
          ]"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <!-- List -->
    <div class="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
      <div 
        v-for="record in filteredRecords" 
        :key="record.id"
        @click="$emit('select', record.id)"
        class="group relative rounded-xl p-3 cursor-pointer transition-all border"
        :class="[
          selectedId === record.id 
            ? 'bg-blue-50/80 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800/50 shadow-sm' 
            : 'bg-white border-slate-100 hover:border-slate-300 hover:shadow-sm dark:bg-slate-800/50 dark:border-slate-700/50 dark:hover:border-slate-600'
        ]"
      >
        <!-- Selection indicator -->
        <div 
          v-if="selectedId === record.id"
          class="absolute left-0 top-3 bottom-3 w-1 bg-blue-500 rounded-r-full"
        ></div>

        <div class="flex justify-between items-start mb-2">
          <div class="flex items-center gap-2">
            <span class="text-sm font-bold text-slate-800 dark:text-slate-100">{{ record.patientName }}</span>
            <span class="text-xs text-slate-500 dark:text-slate-400 font-mono">{{ record.id }}</span>
          </div>
          
          <!-- Status Badge -->
          <div class="flex items-center gap-1">
            <template v-if="record.status === 'completed'">
              <span class="flex items-center gap-1 bg-green-50 text-green-600 border border-green-200 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none dark:bg-green-900/30 dark:border-green-800 dark:text-green-400">
                <CheckCircleOutlined /> 已提取
              </span>
            </template>
            <template v-else-if="record.status === 'processing'">
              <span class="flex items-center gap-1 bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none dark:bg-blue-900/30 dark:border-blue-800 dark:text-blue-400 animate-pulse">
                <SyncOutlined spin /> 提取中
              </span>
            </template>
            <template v-else>
              <span class="flex items-center gap-1 bg-slate-100 text-slate-500 border border-slate-200 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none dark:bg-slate-700 dark:border-slate-600 dark:text-slate-300">
                未提取
              </span>
            </template>
          </div>
        </div>

        <div class="text-xs text-slate-600 dark:text-slate-300 mb-2 flex items-center gap-3">
          <span class="flex items-center gap-1.5">
            <BankOutlined class="text-slate-400" />
            {{ record.department }}
          </span>
          <span class="flex items-center gap-1.5">
            <ClockCircleOutlined class="text-slate-400" />
            {{ record.days }}天
          </span>
        </div>

        <div class="text-xs text-slate-500 dark:text-slate-400 line-clamp-1 flex items-start gap-1.5 pt-2 border-t border-slate-100 dark:border-slate-700/50">
          <span class="text-slate-400 flex-shrink-0 mt-0.5">主诉:</span>
          <span>{{ record.mainDiagnosis || '未知' }}</span>
        </div>
      </div>
      
      <!-- Empty state -->
      <div v-if="filteredRecords.length === 0" class="py-12 flex flex-col items-center justify-center text-center">
        <div class="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-3 dark:bg-slate-800">
          <InboxOutlined class="text-slate-400 text-xl" />
        </div>
        <p class="text-sm text-slate-500 dark:text-slate-400">无匹配病案</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { 
  ProfileOutlined, 
  SearchOutlined, 
  BankOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  InboxOutlined
} from '@ant-design/icons-vue'

export interface DraftRecord {
  id: string
  patientName: string
  department: string
  days: number
  admissionDate: string
  dischargeDate: string
  mainDiagnosis: string
  status: 'pending' | 'processing' | 'completed' | 'error'
  hasWarnings?: boolean
}

const props = defineProps<{
  records: DraftRecord[]
  selectedId: string | null
}>()

defineEmits<{
  (e: 'select', id: string): void
}>()

const searchQuery = ref('')
const currentFilter = ref('all')

const filterTabs = [
  { label: '全部', value: 'all' },
  { label: '未提取', value: 'pending' },
  { label: '已提取', value: 'completed' }
]

const filteredRecords = computed(() => {
  let result = props.records
  
  // Apply filter
  if (currentFilter.value !== 'all') {
    result = result.filter(r => 
      currentFilter.value === 'completed' 
        ? r.status === 'completed' 
        : r.status !== 'completed'
    )
  }
  
  // Apply search
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(r => 
      r.patientName.toLowerCase().includes(q) || 
      r.id.toLowerCase().includes(q) ||
      r.department.toLowerCase().includes(q)
    )
  }
  
  return result
})
</script>

<style scoped>
.hide-scrollbar::-webkit-scrollbar {
  display: none;
}
.hide-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 4px;
}
:deep(.dark) .custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #475569;
}
</style>
