<template>
  <section class="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
    <div
      class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50 px-4 py-2.5"
    >
      <a-space>
        <a-select
          v-if="documentTypeOptions.length > 0"
          mode="multiple"
          allow-clear
          :value="documentTypeSet"
          :max-tag-count="1"
          style="width: 260px"
          :placeholder="documentTypePlaceholder"
          :options="documentTypeOptions"
          @update:value="emit('update:documentTypeSet', ($event || []) as string[])"
        />
        <a-segmented
          :value="viewMode"
          :options="viewOptions"
          @change="emit('update:viewMode', $event as any)"
        />
        <a-select
          :value="sortBy"
          style="width: 130px"
          :options="sortOptions"
          @update:value="emit('update:sortBy', $event as any)"
        />
        <a-select
          :value="statusFilter"
          style="width: 110px"
          :options="statusOptions"
          @update:value="emit('update:statusFilter', $event as any)"
        />
      </a-space>
      <div class="text-[12px] text-slate-500">
        共 {{ pagination.total }} 条
      </div>
    </div>

    <a-table
      :data-source="items"
      :loading="loading"
      :size="viewMode === 'compact' ? 'small' : 'middle'"
      :pagination="{
        current: pagination.current,
        pageSize: pagination.pageSize,
        total: pagination.total,
        size: 'small',
      }"
      row-key="id"
      :row-class-name="rowClassName"
      @row-click="(_record: any) => void 0"
      @change="onTableChange"
    >
      <a-table-column
        key="name"
        title="规则名称"
      >
        <template #default="{ record }">
          <div class="font-semibold text-slate-900">
            {{ record.name }}
          </div>
          <div
            v-if="viewMode !== 'compact'"
            class="text-[12px] text-slate-500 mt-0.5"
          >
            {{ record.conditionSummary }}
          </div>
        </template>
      </a-table-column>
      <a-table-column
        key="status"
        title="状态"
        width="90"
      >
        <template #default="{ record }">
          <a-tag
            :color="
              record.status === 'published'
                ? 'blue'
                : record.status === 'draft'
                  ? 'gold'
                  : 'default'
            "
          >
            {{
              record.status === 'published' ? '已发布' : record.status === 'draft' ? '草稿' : '停用'
            }}
          </a-tag>
        </template>
      </a-table-column>
      <a-table-column
        key="risk"
        title="风险"
        data-index="riskLevel"
        width="80"
      />
      <a-table-column
        key="hits"
        title="近7天命中"
        data-index="hitCount7d"
        width="110"
      />
      <a-table-column
        key="updated"
        title="最近修改"
        width="180"
      >
        <template #default="{ record }">
          <div class="text-[12px] text-slate-700">
            {{ record.updatedBy }}
          </div>
          <div class="text-[12px] text-slate-500">
            {{ record.updatedAt || '-' }}
          </div>
        </template>
      </a-table-column>
      <a-table-column
        key="action"
        title="操作"
        width="210"
      >
        <template #default="{ record }">
          <a-space size="small">
            <a-button
              type="link"
              size="small"
              @click="emit('select-rule', { id: record.id })"
            >
              查看详情
            </a-button>
            <a-button
              type="link"
              size="small"
              @click="emit('duplicate-rule', { id: record.id })"
            >
              复制
            </a-button>
            <a-button
              type="link"
              size="small"
              :disabled="readonly"
              @click="emit('disable-rule', { id: record.id })"
            >
              停用
            </a-button>
          </a-space>
        </template>
      </a-table-column>
    </a-table>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RuleListItem } from './types'

const props = defineProps<{
  items: RuleListItem[]
  selectedRuleId?: string
  loading: boolean
  viewMode: 'list' | 'compact'
  sortBy: 'updated_at' | 'hit_rate' | 'risk'
  statusFilter: 'all' | 'published' | 'draft' | 'disabled'
  pagination: { current: number; pageSize: number; total: number }
  readonly: boolean
  documentTypeSet?: string[]
  documentTypeOptions?: Array<{ label: string; value: string }>
  documentTypePlaceholder?: string
}>()

const emit = defineEmits<{
  'select-rule': [payload: { id: string }]
  'update:viewMode': [value: 'list' | 'compact']
  'update:sortBy': [value: 'updated_at' | 'hit_rate' | 'risk']
  'update:statusFilter': [value: 'all' | 'published' | 'draft' | 'disabled']
  'update:documentTypeSet': [value: string[]]
  'duplicate-rule': [payload: { id: string }]
  'disable-rule': [payload: { id: string }]
  'delete-rule': [payload: { id: string }]
  'page-change': [payload: { current: number; pageSize: number }]
}>()

const documentTypeOptions = computed(() => props.documentTypeOptions || [])
const documentTypeSet = computed(() => props.documentTypeSet || [])
const documentTypePlaceholder = computed(() => props.documentTypePlaceholder || '病历文书类型')

const viewOptions = [
  { label: '列表', value: 'list' },
  { label: '紧凑', value: 'compact' },
]
const sortOptions = [
  { label: '最近修改', value: 'updated_at' },
  { label: '命中率', value: 'hit_rate' },
  { label: '风险', value: 'risk' },
]
const statusOptions = [
  { label: '全部', value: 'all' },
  { label: '已发布', value: 'published' },
  { label: '草稿', value: 'draft' },
  { label: '停用', value: 'disabled' },
]

function rowClassName(record: RuleListItem) {
  const selected = record.id === props.selectedRuleId ? 'bg-blue-50/60' : ''
  const compact = props.viewMode === 'compact' ? 'rules-list-compact-row' : ''
  return `${selected} ${compact}`.trim()
}

function onTableChange(pagination: any) {
  emit('page-change', {
    current: Number(pagination?.current || 1),
    pageSize: Number(pagination?.pageSize || 20),
  })
}
</script>

<style scoped>
:deep(.rules-list-compact-row td) {
  padding-top: 8px !important;
  padding-bottom: 8px !important;
}
</style>
