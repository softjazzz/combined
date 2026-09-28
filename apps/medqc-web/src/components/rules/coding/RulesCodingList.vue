<template>
  <section class="rules-list rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
    <div
      class="rules-list__toolbar flex flex-wrap items-center justify-between gap-2 px-4 py-2.5"
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
      <div class="rules-list__count">
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
          <div class="rules-list__name">
            {{ record.name }}
          </div>
          <div
            v-if="viewMode !== 'compact'"
            class="rules-list__summary"
          >
            {{ record.conditionSummary }}
          </div>
        </template>
      </a-table-column>
      <a-table-column
        key="status"
        title="状态"
        :width="92"
      >
        <template #default="{ record }">
          <span
            class="mq-status"
            :class="STATUS_META[record.status as RuleStatus]?.tone"
          >
            {{ STATUS_META[record.status as RuleStatus]?.label || '停用' }}
          </span>
        </template>
      </a-table-column>
      <a-table-column
        key="risk"
        title="风险"
        :width="76"
      >
        <template #default="{ record }">
          <span
            class="rules-list__risk"
            :class="`rules-list__risk--${record.riskLevel}`"
          >
            {{ RISK_LABEL[record.riskLevel as RuleRiskLevel] || record.riskLevel }}
          </span>
        </template>
      </a-table-column>
      <a-table-column
        key="hits"
        title="近7天命中"
        :width="104"
        align="right"
      >
        <template #default="{ record }">
          <span class="rules-list__number">{{ record.hitCount7d }}</span>
        </template>
      </a-table-column>
      <a-table-column
        key="updated"
        title="最近修改"
        :width="112"
      >
        <template #default="{ record }">
          <div class="rules-list__updated-by">
            {{ record.updatedBy }}
          </div>
          <div class="rules-list__updated-at">
            {{ record.updatedAt || '-' }}
          </div>
        </template>
      </a-table-column>
      <a-table-column
        key="action"
        title="操作"
        :width="172"
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
import type { RuleListItem, RuleRiskLevel, RuleStatus } from './types'

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

const STATUS_META: Record<RuleStatus, { label: string; tone: string }> = {
  published: { label: '已发布', tone: 'mq-status--info' },
  draft: { label: '草稿', tone: 'mq-status--warning' },
  disabled: { label: '停用', tone: '' },
}
const RISK_LABEL: Record<RuleRiskLevel, string> = { high: '高', medium: '中', low: '低' }

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
/* v7.1：工具条去灰底，行名不加粗（Windows 微软雅黑 600 即粗黑体），风险用中文色点 */
.rules-list__toolbar {
  border-bottom: 0.5px solid var(--mq-border);
}

.rules-list__count {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.rules-list__name {
  color: var(--mq-text-primary);
  font-size: var(--mq-font-14);
  font-weight: 500;
  line-height: 22px;
}

.rules-list__summary {
  margin-top: 2px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  line-height: 18px;
}

.rules-list__risk {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
}

.rules-list__risk::before {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #a1a7b3;
  content: '';
}

.rules-list__risk--high::before {
  background: var(--mq-danger-icon);
}

.rules-list__risk--medium::before {
  background: var(--mq-warning-icon);
}

.rules-list__number {
  color: var(--mq-text-primary);
  font-size: var(--mq-font-13);
  font-variant-numeric: tabular-nums;
}

.rules-list__updated-by {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
}

.rules-list__updated-at {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.rules-list :deep(.ant-table-thead > tr > th) {
  white-space: nowrap;
}

.rules-list :deep(.ant-btn-link) {
  padding-inline: 4px;
}

:deep(.rules-list-compact-row td) {
  padding-top: 8px !important;
  padding-bottom: 8px !important;
}
</style>
