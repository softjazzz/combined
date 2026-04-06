<template>
  <main class="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden bg-transparent">
    <div class="custom-scrollbar flex-1 overflow-y-auto px-6 pb-6 pt-4">
      <div class="mx-auto w-full max-w-[1600px]">
        <!-- Header Fusion: Compact Global Toolbar -->
        <div
          class="bg-white border border-slate-200 rounded-xl px-4 py-3 mb-6 flex items-center shadow-[0_2px_8px_-2px_rgba(0,0,0,0.02)]"
        >
          <div class="flex flex-1 items-center gap-4 min-w-0">
            <!-- Search -->
            <div class="w-[300px] shrink-0">
              <a-input
                :value="searchText"
                placeholder="搜索病案号、姓名、住院号"
                allow-clear
                @update:value="emit('update:searchText', $event)"
              >
                <template #prefix>
                  <SearchOutlined class="text-slate-400" />
                </template>
              </a-input>
            </div>

            <div class="h-5 w-px bg-slate-200 shrink-0" />

            <!-- Dept Chips -->
            <div class="flex items-center gap-2 overflow-x-auto custom-scrollbar pb-0">
              <button
                v-for="dept in visibleDepartments"
                :key="dept.name"
                type="button"
                :class="[
                  'px-3 py-1.5 rounded-lg text-[13px] font-semibold transition-colors whitespace-nowrap flex items-center gap-1.5',
                  activeDept === dept.name
                    ? 'bg-blue-50 text-blue-700'
                    : 'bg-transparent text-slate-600 hover:bg-slate-100',
                ]"
                @click="emit('selectDept', dept.name)"
              >
                <span>{{ dept.name }}</span>
                <span
                  :class="[
                    'text-[11px] px-1.5 rounded-full font-mono font-bold leading-5',
                    activeDept === dept.name
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-slate-200 text-slate-500',
                  ]"
                >{{ dept.total }}</span>
              </button>

              <a-dropdown
                v-if="overflowDepartments.length > 0"
                trigger="click"
                placement="bottomRight"
              >
                <button
                  type="button"
                  class="px-3 py-1.5 rounded-lg text-[13px] font-semibold whitespace-nowrap flex items-center gap-1.5 bg-transparent text-slate-600 hover:bg-slate-100"
                >
                  <span>更多科室</span>
                  <DownOutlined class="text-[10px]" />
                </button>
                <template #overlay>
                  <a-menu
                    class="max-h-[320px] w-[220px] overflow-y-auto rounded-xl p-1.5 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.1)]"
                  >
                    <a-menu-item
                      v-for="dept in overflowDepartments"
                      :key="`overflow-${dept.name}`"
                      class="rounded-lg py-2"
                      @click="emit('selectDept', dept.name)"
                    >
                      <div class="flex items-center justify-between gap-3">
                        <span class="truncate font-medium text-slate-700">{{ dept.name }}</span>
                        <span
                          class="rounded bg-slate-100 px-1.5 text-[11px] font-bold text-slate-500 font-mono"
                        >{{ dept.total }}</span>
                      </div>
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </div>
          </div>
        </div>

        <PriorityLane
          :active-group="activePriorityGroup"
          class="mb-6"
          :groups="priorityGroups"
          :cards="priorityCardsFiltered"
          :readonly="isStageQueueMode"
          @update:active-group="emit('update:activePriorityGroup', $event)"
          @open-record="emit('priority-open', $event)"
          @defer-record="emit('priority-defer', $event)"
        />

        <!-- Batch Table -->
        <div
          class="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-[0_2px_8px_-2px_rgba(0,0,0,0.02)]"
        >
          <BatchTablePanel
            :rows="workbenchRows"
            :selected-row-keys="selectedWorkbenchKeys"
            :summary-text="tableSummaryText"
            :loading="displayLoading"
            :primary-action-label="stageMeta.batchActionText"
            :row-action-label="stageMeta.singleActionText"
            :show-primary-action="isStageQueueMode"
            :show-defer-action="false"
            :show-assign-action="false"
            @update:selected-row-keys="emit('update:selectedRowKeys', $event)"
            @open-record="emit('open-record', $event)"
            @batch-extract="emit('batch-extract', $event)"
            @batch-defer="emit('batch-defer', $event)"
            @batch-assign="emit('batch-assign', $event)"
            @clear-filters="emit('clear-filters')"
          />
        </div>

        <div
          v-if="listRecords.length === 0"
          class="mt-6 flex min-h-[160px] flex-col items-center justify-center rounded-xl bg-slate-50/80 border border-slate-200/60 px-5 py-8 text-center"
        >
          <InboxOutlined class="mb-3 text-[36px] text-slate-300" />
          <div class="text-[13px] font-medium text-slate-500">
            {{ stageEmptyText }}
          </div>
        </div>

        <div
          v-if="displayServerTotalPages > 1"
          class="mt-4 flex justify-center py-4"
        >
          <a-pagination
            :current="currentPage"
            :total="displayServerTotal"
            :page-size="50"
            size="small"
            show-quick-jumper
            :show-total="(value: number) => `共 ${value} 例`"
            @change="emit('page-change', $event)"
          />
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { DownOutlined, InboxOutlined, SearchOutlined } from '@ant-design/icons-vue'

import PriorityLane, { type PriorityCard, type PriorityGroup } from './workbench/PriorityLane.vue'
import BatchTablePanel, { type WorkbenchRow } from './workbench/BatchTablePanel.vue'
import type { DeptInfo } from '../types'

interface StageMetaLike {
  batchActionText: string
  singleActionText: string
}

defineProps<{
  activePriorityGroup: string
  priorityGroups: PriorityGroup[]
  priorityCardsFiltered: PriorityCard[]
  isStageQueueMode: boolean
  searchText: string
  visibleDepartments: DeptInfo[]
  overflowDepartments: DeptInfo[]
  activeDept: string
  workbenchRows: WorkbenchRow[]
  selectedWorkbenchKeys: string[]
  tableSummaryText: string
  displayLoading: boolean
  stageMeta: StageMetaLike
  listRecords: unknown[]
  stageEmptyText: string
  displayServerTotalPages: number
  currentPage: number
  displayServerTotal: number
}>()

const emit = defineEmits<{
  'update:activePriorityGroup': [value: string]
  'update:searchText': [value: string]
  'update:selectedRowKeys': [keys: string[]]
  'priority-open': [recordId: string]
  'priority-defer': [recordId: string]
  selectDept: [deptName: string]
  'open-record': [recordId: string]
  'batch-extract': [keys: string[]]
  'batch-defer': [keys: string[]]
  'batch-assign': [keys: string[]]
  'clear-filters': []
  'page-change': [page: number]
}>()
</script>
