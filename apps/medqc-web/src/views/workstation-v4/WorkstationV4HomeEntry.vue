<template>
  <div v-if="showHome" class="wv4-home-entry">
    <QCOverviewView />
  </div>
  <WorkstationV4View v-else />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import QCOverviewView from '@/views/workstation/QCOverviewView.vue'
import WorkstationV4View from './WorkstationV4View.vue'
import { readAnalyticsDrilldown } from './utils/analyticsDrilldown'

const route = useRoute()

const HOME_LAUNCH_QUERY_KEYS = [
  'record_id',
  'action',
  'from_stage',
  'taskId',
  'task_id',
  'stage',
] as const

function hasNonEmptyQueryValue(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some((item) => typeof item === 'string' && item.trim() !== '')
  }
  return typeof value === 'string' && value.trim() !== ''
}

const hasLaunchQuery = computed(() =>
  HOME_LAUNCH_QUERY_KEYS.some((key) => hasNonEmptyQueryValue(route.query[key])),
)

// 兼容旧的统计下钻链接（指向工作台根路径）：带统计参数时直接展示病历列表。
const hasAnalyticsDrilldown = computed(() => readAnalyticsDrilldown(route.query) !== null)

// 当前为全院质控科单一工作台：登录由路由守卫负责，首页不再叠加角色门槛。
// 后续机构/角色授权接入时，必须在数据范围层而非首页展示层收紧。
const showHome = computed(() => !hasLaunchQuery.value && !hasAnalyticsDrilldown.value)
</script>

<style scoped>
.wv4-home-entry {
  position: relative;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}
</style>
