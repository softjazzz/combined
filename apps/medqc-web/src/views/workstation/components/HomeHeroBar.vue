<template>
  <div
    class="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-2.5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
  >
    <div class="relative flex-1 min-w-[200px]">
      <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
        <SearchOutlined class="text-[13px]" />
      </span>
      <a-input
        :value="keyword"
        :maxlength="60"
        class="!h-8 !rounded-lg !border-slate-200 !bg-slate-50 !pl-8 !text-[13px] !text-slate-800 w-full"
        placeholder="搜索患者、病历号、visit"
        allow-clear
        @update:value="emit('update:keyword', String($event || ''))"
      />
    </div>

    <a-date-picker
      :value="selectedDate"
      :allow-clear="false"
      :disabled-date="disabledFutureDate"
      class="!h-8 !w-[130px] !rounded-lg !border-slate-200 !bg-slate-50 !text-[13px]"
      @update:value="emit('update:selectedDate', $event)"
    />

    <a-select
      :value="departmentFilter"
      class="!h-8 !w-[140px] [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-slate-50 !text-[13px]"
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
      class="!h-8 !w-[130px] [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-slate-50 !text-[13px]"
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

    <a-button
      class="!h-8 !rounded-lg !border-0 !bg-blue-600 !px-4 !text-[13px] !font-semibold !text-white hover:!bg-blue-500 !shadow-sm"
      :loading="loading"
      @click="emit('refresh')"
    >
      <template #icon>
        <ReloadOutlined />
      </template>
      刷新
    </a-button>
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
