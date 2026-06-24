<template>
  <section class="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
    <div
      class="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-4 py-2.5"
    >
      <div class="text-[13px] font-semibold text-slate-800">
        变更与发布记录
      </div>
      <a-button
        size="small"
        type="link"
        @click="emit('toggle-collapsed', !collapsed)"
      >
        {{ collapsed ? '展开' : '收起' }}
      </a-button>
    </div>
    <div
      v-if="!collapsed"
      class="p-3"
    >
      <a-table
        :data-source="items"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="small"
      >
        <a-table-column
          key="time"
          title="时间"
          data-index="time"
          width="160"
        />
        <a-table-column
          key="operator"
          title="操作人"
          data-index="operator"
          width="120"
        />
        <a-table-column
          key="action"
          title="动作"
          data-index="action"
          width="120"
        />
        <a-table-column
          key="ruleCount"
          title="规则数"
          data-index="ruleCount"
          width="90"
        />
        <a-table-column
          key="impactCount"
          title="影响病历"
          data-index="impactCount"
          width="100"
        />
        <a-table-column
          key="version"
          title="版本号"
          data-index="version"
        />
        <a-table-column
          key="rollback"
          title="回滚"
          width="90"
        >
          <template #default="{ record }">
            <a-button
              v-if="record.rollbackable"
              size="small"
              type="link"
              @click="emit('rollback', { id: record.id, version: record.version })"
            >
              回滚
            </a-button>
            <span
              v-else
              class="text-slate-300"
            >-</span>
          </template>
        </a-table-column>
      </a-table>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { RuleChangeLogItem } from './types'

defineProps<{
  items: RuleChangeLogItem[]
  loading: boolean
  collapsed: boolean
}>()

const emit = defineEmits<{
  'toggle-collapsed': [value: boolean]
  rollback: [payload: { id: string; version?: string }]
}>()
</script>
