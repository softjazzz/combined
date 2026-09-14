<template>
  <div class="draft-list-sidebar w-80 border-r flex flex-col h-full flex-shrink-0">
    <!-- Header -->
    <div class="draft-list-sidebar__header p-4 border-b flex-shrink-0">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-semibold flex items-center gap-2">
          <ProfileOutlined class="text-blue-500" />
          提取队列
        </h2>
        <span class="draft-list-sidebar__count px-2 py-0.5 rounded-full text-xs font-medium">
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
          class="draft-list-sidebar__search w-full rounded-lg pl-9 pr-3 py-1.5 text-sm focus:outline-none transition-all"
        >
      </div>

      <!-- Tags filter -->
      <div class="flex gap-2 mt-3 overflow-x-auto pb-1 hide-scrollbar">
        <button
          v-for="tab in filterTabs"
          :key="tab.value"
          class="px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors"
          :class="[
            currentFilter === tab.value
              ? 'draft-list-sidebar__filter--active'
              : 'draft-list-sidebar__filter--idle',
          ]"
          @click="currentFilter = tab.value"
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
        class="group relative rounded-xl p-3 cursor-pointer transition-all border"
        :class="[
          selectedId === record.id
            ? 'draft-list-sidebar__item--active shadow-sm'
            : 'draft-list-sidebar__item--idle hover:shadow-sm',
        ]"
        @click="$emit('select', record.id)"
      >
        <!-- Selection indicator -->
        <div
          v-if="selectedId === record.id"
          class="draft-list-sidebar__indicator absolute left-0 top-3 bottom-3 w-1 rounded-r-full"
        />

        <div class="flex justify-between items-start mb-2">
          <div class="flex items-center gap-2">
            <span class="text-sm font-semibold text-slate-800">{{ record.patientName }}</span>
            <span class="text-xs text-slate-500 font-mono">{{ record.id }}</span>
          </div>

          <!-- Status Badge -->
          <div class="flex items-center gap-1">
            <template v-if="record.status === 'completed'">
              <span
                class="draft-list-sidebar__status draft-list-sidebar__status--success flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none"
              >
                <CheckCircleOutlined /> 已提取
              </span>
            </template>
            <template v-else-if="record.status === 'processing'">
              <span
                class="draft-list-sidebar__status draft-list-sidebar__status--processing flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none animate-pulse"
              >
                <SyncOutlined spin /> 提取中
              </span>
            </template>
            <template v-else>
              <span
                class="draft-list-sidebar__status draft-list-sidebar__status--idle flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none"
              >
                未提取
              </span>
            </template>
          </div>
        </div>

        <div class="text-xs text-slate-600 mb-2 flex items-center gap-3">
          <span class="flex items-center gap-1.5">
            <BankOutlined class="text-slate-400" />
            {{ record.department }}
          </span>
          <span class="flex items-center gap-1.5">
            <ClockCircleOutlined class="text-slate-400" />
            {{ record.days }}天
          </span>
        </div>

        <div class="text-xs text-slate-500 line-clamp-1 flex items-start gap-1.5 pt-2 border-t">
          <span class="text-slate-400 flex-shrink-0 mt-0.5">主诉:</span>
          <span>{{ record.mainDiagnosis || '未知' }}</span>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-if="filteredRecords.length === 0"
        class="py-12 flex flex-col items-center justify-center text-center"
      >
        <div
          class="draft-list-sidebar__empty-icon w-12 h-12 rounded-full flex items-center justify-center mb-3"
        >
          <InboxOutlined class="text-slate-400 text-xl" />
        </div>
        <p class="text-sm text-slate-500">
          无匹配病案
        </p>
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
  InboxOutlined,
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
  { label: '已提取', value: 'completed' },
]

const filteredRecords = computed(() => {
  let result = props.records

  // Apply filter
  if (currentFilter.value !== 'all') {
    result = result.filter((r) =>
      currentFilter.value === 'completed' ? r.status === 'completed' : r.status !== 'completed',
    )
  }

  // Apply search
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(
      (r) =>
        r.patientName.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q) ||
        r.department.toLowerCase().includes(q),
    )
  }

  return result
})
</script>

<style scoped>
.draft-list-sidebar {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.draft-list-sidebar__header {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.draft-list-sidebar h2 {
  color: #1d1d1f !important;
}

.draft-list-sidebar :deep(.anticon),
.draft-list-sidebar .text-blue-500 {
  color: #2b6cf6 !important;
}

.draft-list-sidebar__count,
.draft-list-sidebar__filter--active {
  border: 1px solid rgba(43, 108, 246, 0.16);
  background: rgba(43, 108, 246, 0.08);
  color: #2b6cf6;
}

.draft-list-sidebar__search {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.9);
  color: #1d1d1f;
  font-family: inherit;
}

.draft-list-sidebar__search:focus {
  border-color: rgba(43, 108, 246, 0.32);
  box-shadow: 0 0 0 3px rgba(43, 108, 246, 0.08);
}

.draft-list-sidebar__filter--idle {
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.62);
}

.draft-list-sidebar__filter--idle:hover {
  background: rgba(0, 0, 0, 0.055);
  color: #1d1d1f;
}

.draft-list-sidebar__item--active {
  border-color: rgba(43, 108, 246, 0.18) !important;
  background: rgba(43, 108, 246, 0.07) !important;
}

.draft-list-sidebar__item--idle {
  border-color: rgba(0, 0, 0, 0.06) !important;
  background: rgba(255, 255, 255, 0.72) !important;
}

.draft-list-sidebar__item--idle:hover {
  border-color: rgba(0, 0, 0, 0.12) !important;
  background: rgba(255, 255, 255, 0.94) !important;
}

.draft-list-sidebar__indicator {
  background: #2b6cf6;
}

.draft-list-sidebar__status {
  border: 1px solid transparent;
}

.draft-list-sidebar__status--success {
  border-color: rgba(16, 185, 129, 0.18);
  background: rgba(16, 185, 129, 0.08);
  color: #047857;
}

.draft-list-sidebar__status--processing {
  border-color: rgba(43, 108, 246, 0.16);
  background: rgba(43, 108, 246, 0.08);
  color: #2b6cf6;
}

.draft-list-sidebar__status--idle {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.58);
}

.draft-list-sidebar .border-t {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.draft-list-sidebar__empty-icon {
  background: rgba(0, 0, 0, 0.04);
}

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
  background-color: rgba(29, 29, 31, 0.18);
  border-radius: 4px;
}
:deep(.dark) .custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(29, 29, 31, 0.18);
}
</style>
