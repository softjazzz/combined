<template>
  <!-- 左侧：全局搜索 -->
  <div class="flex items-center gap-1.5 flex-1 max-w-[400px]">
    <div class="relative w-full">
      <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
        <SearchOutlined class="text-[14px]" />
      </span>
      <input
        :value="keyword"
        maxlength="60"
        type="text"
        class="h-8 w-full rounded-md border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-[13px] text-slate-800 outline-none transition-all focus:border-blue-500 focus:bg-white focus:shadow-[0_0_0_2px_rgba(59,130,246,0.1)] hover:border-slate-300 placeholder-slate-400"
        placeholder="搜索患者、病历号 / ⌘K"
        @input="emit('update:keyword', ($event.target as HTMLInputElement).value)"
      >
      <span
        v-if="!keyword"
        class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-slate-200 bg-white px-1 py-0.5 text-[10px] font-bold text-slate-400 shadow-sm"
      >
        ⌘K
      </span>
    </div>
  </div>

  <!-- 右侧：过滤器组 -->
  <div class="flex items-center gap-3">
    <!-- 日期 -->
    <a-date-picker
      :value="selectedDate"
      :allow-clear="false"
      :disabled-date="disabledFutureDate"
      class="!h-8 !w-[130px] !rounded-md !border-slate-200 !bg-white !text-[13px] hover:!border-slate-300 focus:!border-blue-500 shadow-sm"
      @update:value="emit('update:selectedDate', $event)"
    />

    <!-- 科室下拉 -->
    <a-select
      :value="departmentFilter"
      class="!h-8 !w-[140px] shadow-sm [&_.ant-select-selector]:!rounded-md [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-white !text-[13px] hover:[&_.ant-select-selector]:!border-slate-300"
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

    <!-- 流程下拉 -->
    <a-select
      :value="workflowFilter"
      class="!h-8 !w-[130px] shadow-sm [&_.ant-select-selector]:!rounded-md [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-white !text-[13px] hover:[&_.ant-select-selector]:!border-slate-300"
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
      <div class="h-4 w-px bg-slate-200 mx-1" />

      <!-- 刷新按钮 -->
      <button
        type="button"
        class="flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm transition-all hover:bg-slate-50 hover:text-slate-800 disabled:opacity-50"
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
