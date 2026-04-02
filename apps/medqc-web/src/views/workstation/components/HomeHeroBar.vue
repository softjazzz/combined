<template>
  <div
    class="flex flex-wrap items-center gap-2.5 rounded-[8px] bg-slate-50/90 backdrop-blur-sm px-3 py-2 border border-slate-200 shadow-sm"
  >
    <div class="relative flex-1 min-w-[200px] max-w-[360px]">
      <span class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400">
        <SearchOutlined class="text-[13px]" />
      </span>
      <a-input
        :value="keyword"
        :maxlength="60"
        class="!h-[32px] !rounded !border-transparent !bg-white/80 hover:!bg-white focus:!bg-white !pl-7 text-[13px] !text-slate-800 w-full transition-all ring-1 ring-slate-200/50 hover:ring-slate-300 focus:ring-blue-500 shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
        placeholder="搜索患者、病历号 / ⌘K"
        allow-clear
        @update:value="emit('update:keyword', String($event || ''))"
      />
    </div>

    <div class="flex items-center gap-2 ml-auto">
      <a-date-picker
        :value="selectedDate"
        :allow-clear="false"
        :disabled-date="disabledFutureDate"
        class="!h-[32px] !w-[124px] !rounded !border-transparent !bg-white/80 text-[13px] ring-1 ring-slate-200/50 hover:ring-slate-300 hover:!bg-white transition-all shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
        @update:value="emit('update:selectedDate', $event)"
      />

      <a-select
        :value="departmentFilter"
        class="!h-[32px] !w-[124px] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-all [&_.ant-select-selector]:!rounded [&_.ant-select-selector]:!border-transparent [&_.ant-select-selector]:!bg-white/80 [&_.ant-select-selector]:hover:!bg-white [&_.ant-select-selector]:ring-1 [&_.ant-select-selector]:ring-slate-200/50 text-[13px] hover:[&_.ant-select-selector]:ring-slate-300"
        @update:value="emit('update:departmentFilter', String($event || 'all'))"
      >
        <a-select-option value="all">
          全部科室
        </a-select-option>
        <a-select-option
          v-for="dept in departmentOptions"
          :key="dept"
          :value="dept"
        >
          {{ dept }}
        </a-select-option>
      </a-select>

      <a-select
        :value="workflowFilter"
        class="!h-[32px] !w-[124px] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-all [&_.ant-select-selector]:!rounded [&_.ant-select-selector]:!border-transparent [&_.ant-select-selector]:!bg-white/80 [&_.ant-select-selector]:hover:!bg-white [&_.ant-select-selector]:ring-1 [&_.ant-select-selector]:ring-slate-200/50 text-[13px] hover:[&_.ant-select-selector]:ring-slate-300"
        @update:value="emit('update:workflowFilter', String($event || 'all'))"
      >
        <a-select-option value="all">
          全部流程
        </a-select-option>
        <a-select-option value="frontpage">
          首页质控
        </a-select-option>
        <a-select-option value="coding">
          编码质控
        </a-select-option>
        <a-select-option value="settlement">
          结算质控
        </a-select-option>
      </a-select>

      <div class="w-px h-4 bg-slate-300/60 mx-1" />

      <a-button
        type="text"
        class="!h-[32px] !w-[32px] !p-0 !text-slate-500 hover:!bg-slate-200/70 hover:!text-slate-800 rounded transition-colors flex items-center justify-center"
        :loading="loading"
        title="刷新"
        @click="emit('refresh')"
      >
        <template #icon>
          <ReloadOutlined class="text-[13px] leading-none" />
        </template>
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import type { Dayjs } from 'dayjs'

defineProps<{
  keyword: string
  selectedDate: Dayjs
  departmentFilter: string
  workflowFilter: string
  departmentOptions: string[]
  loading: boolean
  disabledFutureDate: (current: Dayjs) => boolean
}>()

const emit = defineEmits([
  'update:keyword',
  'update:selectedDate',
  'update:departmentFilter',
  'update:workflowFilter',
  'refresh',
])
</script>
