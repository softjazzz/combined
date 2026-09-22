<template>
  <div
    v-if="showHome"
    class="wv4-home-entry"
  >
    <QCOverviewView />
    <button
      type="button"
      class="wv4-home-entry__agent-button"
      data-testid="qc-agent-home-entry"
      @click="qcAgentOpen = true"
    >
      <span class="wv4-home-entry__agent-icon"> AI </span>
      <span class="wv4-home-entry__agent-text">智能助手</span>
      <span
        class="wv4-home-entry__agent-status"
        aria-hidden="true"
      />
    </button>
    <QCAgentChatDrawer
      v-model:open="qcAgentOpen"
      context-label="工作台首页，可输入 visit_id、住院号、患者姓名或科室"
      :user-context="{}"
    />
  </div>
  <WorkstationV4View v-else />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import QCOverviewView from '@/views/workstation/QCOverviewView.vue'
import WorkstationV4View from './WorkstationV4View.vue'
import QCAgentChatDrawer from './components/QCAgentChatDrawer.vue'

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
  min-height: calc(100vh - 64px);
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.wv4-home-entry__agent-button {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 30;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 132px;
  height: 44px;
  overflow: hidden;
  border: 1px solid rgba(43, 108, 246, 0.24);
  border-radius: 12px;
  background: rgba(43, 108, 246, 0.92);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    0 8px 22px rgba(43, 108, 246, 0.22);
  color: #ffffff;
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0;
  cursor: pointer;
  transition:
    transform 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    background-color 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.wv4-home-entry__agent-icon {
  position: relative;
  z-index: 1;
  display: inline-flex;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.32);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
  letter-spacing: 0;
  line-height: 1;
}

.wv4-home-entry__agent-text {
  position: relative;
  z-index: 1;
}

.wv4-home-entry__agent-status {
  position: relative;
  z-index: 1;
  width: 7px;
  height: 7px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.16);
}

.wv4-home-entry__agent-button:hover,
.wv4-home-entry__agent-button:focus-visible {
  border-color: rgba(43, 108, 246, 0.32);
  background: #0057b8;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    0 10px 26px rgba(43, 108, 246, 0.26);
  transform: translateY(-2px);
}

.wv4-home-entry__agent-button:focus-visible {
  outline: 2px solid rgba(43, 108, 246, 0.24);
  outline-offset: 3px;
}
</style>
