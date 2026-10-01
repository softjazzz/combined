<template>
  <div v-if="showHome" class="wv4-home-entry">
    <QCOverviewView />
    <button
      type="button"
      class="wv4-home-entry__agent-button"
      data-testid="qc-agent-home-entry"
      @click="qcAgentOpen = true"
    >
      <span class="wv4-home-entry__agent-icon"> AI </span>
      <span class="wv4-home-entry__agent-text">智能助手</span>
      <span class="wv4-home-entry__agent-status" aria-hidden="true" />
    </button>
    <BusinessAgentDrawer
      v-model:open="qcAgentOpen"
      allow-case-selection
      :user-context="{ view: 'manager' }"
    />
  </div>
  <WorkstationV4View v-else />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import QCOverviewView from '@/views/workstation/QCOverviewView.vue'
import WorkstationV4View from './WorkstationV4View.vue'
import BusinessAgentDrawer from './components/BusinessAgentDrawer.vue'

const route = useRoute()
const qcAgentOpen = ref(false)

const hasLaunchQuery = computed(() => {
  return ['record_id', 'action', 'from_stage', 'taskId', 'stage'].some((key) => {
    return typeof route.query[key] === 'string' && String(route.query[key] || '').trim() !== ''
  })
})

// 当前为全院质控科单一工作台：登录由路由守卫负责，首页不再叠加角色门槛。
// 后续机构/角色授权接入时，必须在数据范围层而非首页展示层收紧。
const showHome = computed(() => !hasLaunchQuery.value)
</script>

<style scoped>
.wv4-home-entry {
  position: relative;
  min-height: 100vh;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}

/* v7.1 智能助手：悬浮玻璃胶囊 */
.wv4-home-entry__agent-button {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 30;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 46px;
  padding: 0 20px 0 10px;
  border: 1px solid var(--mq-glass-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
  box-shadow: 0 12px 32px rgba(10, 55, 115, 0.18);
  color: var(--mq-text-primary);
  font: inherit;
  font-size: var(--mq-font-14);
  font-weight: 600;
  cursor: pointer;
  transition:
    transform 200ms ease,
    box-shadow 200ms ease;
}

.wv4-home-entry__agent-icon {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--mq-brand-gradient);
  box-shadow: 0 0 12px rgba(10, 108, 255, 0.45);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
}

.wv4-home-entry__agent-status {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--mq-success-icon);
  box-shadow: 0 0 0 3px var(--mq-success-bg);
}

.wv4-home-entry__agent-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 36px rgba(10, 55, 115, 0.22);
}

.wv4-home-entry__agent-button:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .wv4-home-entry__agent-button {
    transition: none;
  }
}
</style>
