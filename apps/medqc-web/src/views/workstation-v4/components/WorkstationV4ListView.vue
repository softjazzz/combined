<template>
  <main class="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
    <div class="custom-scrollbar flex-1 overflow-y-auto px-4 pb-5 pt-4 xl:px-5">
      <div class="mx-auto w-full max-w-[1440px]">
        <div class="workstation-surface-enter">
          <PriorityLane
            :active-group="activePriorityGroup"
            class="mb-4"
            :groups="priorityGroups"
            :cards="priorityCardsFiltered"
            :readonly="isStageQueueMode"
            @update:active-group="emit('update:activePriorityGroup', $event)"
            @open-record="emit('priority-open', $event)"
            @defer-record="emit('priority-defer', $event)"
          />
        </div>

        <div class="workstation-surface-enter workstation-surface-enter--delay-1 mb-4">
          <div class="workstation-panel workstation-panel--filters">
            <div
              class="pointer-events-none absolute right-[-48px] top-[-72px] h-[220px] w-[220px] rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.68),rgba(255,255,255,0))]"
            />
            <div
              class="pointer-events-none absolute bottom-[-120px] left-[18%] h-[220px] w-[260px] rounded-full bg-[radial-gradient(circle,rgba(226,232,240,0.8),rgba(226,232,240,0))]"
            />

            <div class="relative workbench-hero">
              <div class="workbench-controls-panel">
                <div class="workbench-controls-search-row">
                  <a-input
                    :value="searchText"
                    class="workbench-controls__search-input"
                    placeholder="搜索病案号、姓名、住院号"
                    size="large"
                    allow-clear
                    @update:value="emit('update:searchText', $event)"
                  >
                    <template #prefix>
                      <SearchOutlined class="text-slate-400" />
                    </template>
                  </a-input>
                </div>

                <div class="workbench-dept-row">
                  <div class="workbench-dept-row__list">
                    <button
                      v-for="dept in visibleDepartments"
                      :key="dept.name"
                      type="button"
                      :class="[
                        'workbench-dept-chip',
                        activeDept === dept.name
                          ? 'workbench-dept-chip--active'
                          : 'workbench-dept-chip--idle',
                      ]"
                      @click="emit('selectDept', dept.name)"
                    >
                      <span>{{ dept.name }}</span>
                      <span class="workbench-dept-chip__count">{{ dept.total }}</span>
                    </button>

                    <a-dropdown
                      v-if="overflowDepartments.length > 0"
                      trigger="click"
                      placement="bottomRight"
                    >
                      <button
                        type="button"
                        class="workbench-dept-chip workbench-dept-chip--idle"
                      >
                        <span>更多科室</span>
                        <span class="workbench-dept-chip__count">{{
                          overflowDepartments.length
                        }}</span>
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
                              <span class="truncate font-medium text-slate-700">{{
                                dept.name
                              }}</span>
                              <span
                                class="rounded bg-slate-50 px-1.5 text-[11px] font-bold text-slate-400"
                              >{{ dept.total }}</span>
                            </div>
                          </a-menu-item>
                        </a-menu>
                      </template>
                    </a-dropdown>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="workstation-surface-enter workstation-surface-enter--delay-2">
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
          class="workstation-empty-state mt-4 flex min-h-[160px] flex-col items-center justify-center px-5 py-10 text-center"
        >
          <InboxOutlined class="workstation-empty-state__icon mb-3 text-[36px]" />
          <div class="workstation-empty-state__text text-[13px] font-medium">
            {{ stageEmptyText }}
          </div>
        </div>

        <div
          v-if="displayServerTotalPages > 1"
          class="workstation-pagination-shell mt-3 flex justify-center px-5 py-3"
        >
          <a-pagination
            class="workstation-pagination"
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

import PriorityLane from './workbench/PriorityLane.vue'
import BatchTablePanel, { type WorkbenchRow } from './workbench/BatchTablePanel.vue'
import type { DeptInfo } from '../types'

interface StageMetaLike {
  batchActionText: string
  singleActionText: string
}

interface PriorityGroupLike {
  key: string
  label: string
  count?: number
}

interface PriorityCardLike {
  id: string
}

defineProps<{
  activePriorityGroup: string
  priorityGroups: PriorityGroupLike[]
  priorityCardsFiltered: PriorityCardLike[]
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
