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
      <span class="wv4-home-entry__agent-icon">
        AI
      </span>
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
import { useAuthStore } from '@/stores/auth'
import QCOverviewView from '@/views/workstation/QCOverviewView.vue'
import WorkstationV4View from './WorkstationV4View.vue'
import QCAgentChatDrawer from './components/QCAgentChatDrawer.vue'

const route = useRoute()
const authStore = useAuthStore()
const qcAgentOpen = ref(false)

const hasLaunchQuery = computed(() => {
  return ['record_id', 'action', 'from_stage', 'taskId', 'stage'].some((key) => {
    return typeof route.query[key] === 'string' && String(route.query[key] || '').trim() !== ''
  })
})

const isHomeRole = computed(() => authStore.hasRole('admin') || authStore.hasRole('qc_manager'))

const showHome = computed(() => isHomeRole.value && !hasLaunchQuery.value)
</script>

<style scoped>
.wv4-home-entry {
  position: relative;
  min-height: calc(100vh - 64px);
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
  min-width: 138px;
  height: 46px;
  overflow: hidden;
  border: 1px solid rgba(147, 197, 253, 0.58);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(6, 182, 212, 0.28) 0%, rgba(6, 182, 212, 0) 34%),
    linear-gradient(180deg, #3b82f6 0%, #2563eb 48%, #1d4ed8 100%);
  box-shadow:
    0 16px 34px rgba(37, 99, 235, 0.28),
    0 0 0 1px rgba(255, 255, 255, 0.08) inset,
    inset 0 1px 0 rgba(255, 255, 255, 0.34);
  color: #ffffff;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0;
  cursor: pointer;
  transition:
    transform 0.16s ease,
    box-shadow 0.16s ease,
    background-color 0.16s ease;
}

.wv4-home-entry__agent-button::before {
  position: absolute;
  top: 0;
  bottom: 0;
  left: -42%;
  width: 38%;
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.28) 52%,
    rgba(255, 255, 255, 0) 100%
  );
  content: '';
  transform: skewX(-18deg);
  transition: left 0.38s ease;
}

.wv4-home-entry__agent-icon {
  position: relative;
  z-index: 1;
  display: inline-flex;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
  font-size: 11px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
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
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.16);
}

.wv4-home-entry__agent-button:hover,
.wv4-home-entry__agent-button:focus-visible {
  background:
    linear-gradient(135deg, rgba(6, 182, 212, 0.34) 0%, rgba(6, 182, 212, 0) 34%),
    linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%);
  box-shadow:
    0 18px 38px rgba(37, 99, 235, 0.34),
    0 0 0 1px rgba(255, 255, 255, 0.1) inset,
    inset 0 1px 0 rgba(255, 255, 255, 0.24);
  transform: translateY(-2px);
}

.wv4-home-entry__agent-button:hover::before,
.wv4-home-entry__agent-button:focus-visible::before {
  left: 112%;
}

.wv4-home-entry__agent-button:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 3px;
}
</style>
