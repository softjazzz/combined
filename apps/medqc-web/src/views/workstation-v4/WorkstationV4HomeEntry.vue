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

const hasLaunchQuery = computed(() => {
  return ['record_id', 'action', 'from_stage', 'taskId', 'stage'].some((key) => {
    return typeof route.query[key] === 'string' && String(route.query[key] || '').trim() !== ''
  })
})

// 兼容旧的统计下钻链接（指向工作台根路径）：带统计参数时直接展示病历列表。
const hasAnalyticsDrilldown = computed(() => readAnalyticsDrilldown(route.query) !== null)

// 当前为全院质控科单一工作台：登录由路由守卫负责，首页不再叠加角色门槛。
// 后续机构/角色授权接入时，必须在数据范围层而非首页展示层收紧。
const showHome = computed(() => !hasLaunchQuery.value && !hasAnalyticsDrilldown.value)
</script>

<style scoped>
.wv4-home-entry {
  position: relative;
  min-height: 100vh;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}
</style>
