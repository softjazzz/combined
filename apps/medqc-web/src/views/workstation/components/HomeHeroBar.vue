<template>
  <div class="flex min-w-[280px] flex-1 items-center gap-2">
    <div class="relative w-full">
      <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
        <SearchOutlined class="text-[14px]" />
      </span>
      <input
        :value="keyword"
        maxlength="60"
        type="text"
        class="h-10 w-full rounded-xl border border-slate-200/80 bg-white/85 pl-9 pr-3 text-[13px] text-slate-800 shadow-sm outline-none transition-all placeholder:text-slate-400 hover:border-slate-300 focus:border-sky-400 focus:bg-white focus:shadow-[0_0_0_3px_rgba(14,165,233,0.12)]"
        placeholder="搜索患者、病历号"
        @input="emit('update:keyword', ($event.target as HTMLInputElement).value)"
      >
    </div>
  </div>

  <div class="flex flex-wrap items-center justify-end gap-2.5">
    <a-date-picker
      :value="selectedDate"
      :allow-clear="false"
      :disabled-date="disabledFutureDate"
      class="!h-10 !w-[144px] !rounded-xl !border-slate-200/80 !bg-white/85 !text-[13px] shadow-sm hover:!border-slate-300 focus:!border-sky-400"
      @update:value="emit('update:selectedDate', $event)"
    />

    <a-select
      :value="departmentFilter"
      class="!h-10 !w-[156px] !text-[13px] shadow-sm [&_.ant-select-selector]:!h-10 [&_.ant-select-selector]:!rounded-xl [&_.ant-select-selector]:!border-slate-200/80 [&_.ant-select-selector]:!bg-white/85 hover:[&_.ant-select-selector]:!border-slate-300"
      @update:value="emit('update:departmentFilter', String($event || 'all'))"
    >
      <a-select-option value="all">
        全量科室范围
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
      class="!h-10 !w-[148px] !text-[13px] shadow-sm [&_.ant-select-selector]:!h-10 [&_.ant-select-selector]:!rounded-xl [&_.ant-select-selector]:!border-slate-200/80 [&_.ant-select-selector]:!bg-white/85 hover:[&_.ant-select-selector]:!border-slate-300"
      @update:value="emit('update:workflowFilter', String($event || 'all'))"
    >
      <a-select-option value="all">
        所有质控流程
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

    <template v-if="showRefresh !== false">
      <div class="mx-1 h-5 w-px bg-slate-200" />

      <button
        type="button"
        class="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/80 bg-white/85 text-slate-500 shadow-sm transition-all hover:bg-white hover:text-slate-800 disabled:opacity-50"
        :disabled="loading"
        title="刷新数据"
        @click="emit('refresh')"
      >
        <LoadingOutlined
          v-if="loading"
          class="text-[13px]"
        />
        <ReloadOutlined
          v-else
          class="text-[13px]"
        />
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { SearchOutlined, ReloadOutlined, LoadingOutlined } from '@ant-design/icons-vue'
import type { Dayjs } from 'dayjs'

defineProps<{
  keyword: string
  selectedDate: Dayjs
  departmentFilter: string
  workflowFilter: string
  departmentOptions: string[]
  loading: boolean
  disabledFutureDate: (current: Dayjs) => boolean
  showRefresh?: boolean
}>()

const emit = defineEmits([
  'update:keyword',
  'update:selectedDate',
  'update:departmentFilter',
  'update:workflowFilter',
  'refresh',
])
</script>
