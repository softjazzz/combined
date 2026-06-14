<template>
  <section
    class="rounded-[16px] border border-slate-200 bg-white shadow-[0_2px_8px_-2px_rgba(0,0,0,0.02)] flex flex-col h-full overflow-hidden"
  >
    <header
      class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3 shadow-sm relative z-10 shrink-0"
    >
      <div>
        <div class="text-[11px] font-semibold text-[#0066cc]">优先处理队列</div>
        <h3 class="text-[18px] font-semibold text-[#1d1d1f]">关键问题病历</h3>
      </div>
      <div class="flex items-center gap-2">
        <div class="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-600">
          {{ total }} 条
        </div>
      </div>
    </header>

    <div class="border-b border-slate-100 px-5 py-2.5 bg-slate-50/50 shrink-0">
      <div class="flex flex-wrap items-center gap-2">
        <a-select
          :value="severityFilter"
          class="!h-8 [&_.ant-select-selector]:!rounded-md [&_.ant-select-selector]:!border-slate-200 !text-[12px]"
          style="width: 120px"
          @update:value="emit('update:severityFilter', String($event || 'all'))"
        >
          <a-select-option value="all"> 全部级别 </a-select-option>
          <a-select-option value="critical"> 严重 </a-select-option>
          <a-select-option value="high"> 高风险 </a-select-option>
          <a-select-option value="warning"> 警告 </a-select-option>
          <a-select-option value="info"> 提示 </a-select-option>
        </a-select>
        <a-select
          :value="workflowFilter"
          class="!h-8 [&_.ant-select-selector]:!rounded-md [&_.ant-select-selector]:!border-slate-200 !text-[12px]"
          style="width: 120px"
          @update:value="emit('update:workflowFilter', String($event || 'all'))"
        >
          <a-select-option value="all"> 全部流程 </a-select-option>
          <a-select-option value="frontpage"> 首页质控 </a-select-option>
          <a-select-option value="coding"> 编码质控 </a-select-option>
          <a-select-option value="settlement"> 结算质控 </a-select-option>
        </a-select>
        <a-select
          :value="sortBy"
          class="!h-8 [&_.ant-select-selector]:!rounded-md [&_.ant-select-selector]:!border-slate-200 !text-[12px]"
          style="width: 120px"
          @update:value="emit('update:sortBy', String($event || 'default'))"
        >
          <a-select-option value="default"> 默认排序 </a-select-option>
          <a-select-option value="recent"> 最近时间 </a-select-option>
          <a-select-option value="severity"> 风险优先 </a-select-option>
          <a-select-option value="unread"> 未读优先 </a-select-option>
          <a-select-option value="defects"> 缺陷优先 </a-select-option>
        </a-select>
      </div>
    </div>

    <div v-if="items.length" class="flex-1 overflow-y-auto custom-scrollbar">
      <div
        class="grid gap-3 border-b border-slate-200 bg-white px-5 py-2 text-[11px] font-semibold text-slate-500 sticky top-0 z-10"
        :style="{ gridTemplateColumns: columnTemplate }"
      >
        <div>患者信息</div>
        <div>科室</div>
        <div>流程</div>
        <div>风险级别</div>
        <div>问题摘要</div>
        <div>活跃缺陷</div>
        <div>最新状态</div>
        <div>最近时间</div>
        <div class="text-right">操作</div>
      </div>

      <button
        v-for="item in items"
        :key="item.id"
        type="button"
        class="grid w-full gap-3 border-b border-slate-100 px-5 py-3 text-left transition-colors hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
        :style="{ gridTemplateColumns: columnTemplate }"
        :class="
          item.id === selectedId
            ? 'bg-[#eaf2ff]/60 relative before:absolute before:left-0 before:top-0 before:bottom-0 before:w-1 before:bg-[#0066cc]'
            : 'bg-white'
        "
        @click="emit('select', item.id)"
      >
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span
              v-if="item.unread_count > 0"
              class="h-1.5 w-1.5 shrink-0 rounded-full bg-red-500"
            />
            <div class="truncate text-[13px] font-bold text-slate-900">
              {{ item.patient_name || '--' }}
            </div>
          </div>
          <div
            class="mt-0.5 text-[11px] text-slate-500 font-mono"
            style="font-variant-numeric: tabular-nums"
          >
            {{ item.visit_id || item.record_id || '--' }}
          </div>
        </div>

        <div class="min-w-0 flex items-center">
          <div class="truncate text-[12px] text-slate-600">
            {{ item.department || '未分科室' }}
          </div>
        </div>

        <div class="min-w-0 flex items-center">
          <span
            class="rounded border border-[#0066cc]/15 bg-[#eaf2ff] px-1.5 py-0.5 text-[11px] font-medium text-[#0066cc] truncate"
          >
            {{ workflowLabel(item.workflow_type) }}
          </span>
        </div>

        <div class="min-w-0 flex items-center">
          <a-tag :color="severityColor(item.severity)" class="!mr-0 !text-[10px] !leading-[18px]">
            {{ severityLabel(item.severity) }}
          </a-tag>
        </div>

        <div class="min-w-0">
          <div class="truncate text-[12px] font-bold text-slate-800">
            {{ item.title }}
          </div>
          <div class="mt-0.5 truncate text-[11px] text-slate-500">
            {{ item.summary }}
          </div>
        </div>

        <div class="min-w-0 flex items-center">
          <span
            class="inline-flex min-w-[42px] items-center justify-center rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-bold text-red-600"
          >
            {{ item.active_defect_count || 0 }}
          </span>
        </div>

        <div class="min-w-0">
          <div class="text-[12px] font-medium text-slate-800">
            {{ queueStatusLabel(item.queue_status) }}
          </div>
          <div class="mt-0.5 text-[11px] text-slate-500">
            {{ item.latest_qc_grade || '暂无结果' }}
          </div>
        </div>

        <div
          class="min-w-0 flex flex-col justify-center text-[11px] text-slate-500 font-mono"
          style="font-variant-numeric: tabular-nums"
        >
          {{ formatDateTime(item.latest_created_at) }}
        </div>

        <div class="flex items-center justify-end gap-2">
          <span class="text-[12px] font-semibold text-slate-500">查看详情</span>
          <span class="text-[12px] font-semibold text-[#0066cc]">→</span>
        </div>
      </button>
    </div>

    <div v-else class="flex-1 flex flex-col items-center justify-center p-8 bg-slate-50/50">
      <div class="text-[13px] font-medium text-slate-500">当前筛选下无关键问题病历</div>
    </div>

    <footer
      v-if="total > 0"
      class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-5 py-3 bg-white shrink-0"
    >
      <div class="text-[11px] text-slate-500">第 {{ page }} 页，共 {{ total }} 条</div>
      <a-pagination
        size="small"
        :current="page"
        :page-size="pageSize"
        :total="total"
        :show-size-changer="false"
        @update:current="emit('update:page', $event)"
      />
    </footer>
  </section>
</template>

<script setup lang="ts">
import type { WorkstationHomeHotspotItem } from '@/views/workstation-v2/types'

const columnTemplate = '1fr 0.75fr 0.8fr 0.75fr 1.55fr 0.7fr 0.95fr 0.95fr 0.85fr'

defineProps<{
  items: WorkstationHomeHotspotItem[]
  selectedId: string
  total: number
  page: number
  pageSize: number
  sortBy: string
  severityFilter: string
  workflowFilter: string
  formatDateTime: (value?: string | null) => string
  severityLabel: (value?: string) => string
  severityColor: (value?: string) => string
  workflowLabel: (value?: string) => string
  queueStatusLabel: (value?: string) => string
}>()

const emit = defineEmits<{
  select: [id: string]
  'update:page': [value: number]
  'update:sortBy': [value: string]
  'update:severityFilter': [value: string]
  'update:workflowFilter': [value: string]
}>()
</script>
