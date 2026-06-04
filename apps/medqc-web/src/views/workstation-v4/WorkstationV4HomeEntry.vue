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
      质控助手
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
  min-width: 104px;
  height: 38px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #2563eb;
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.18);
  color: #ffffff;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition:
    transform 0.16s ease,
    box-shadow 0.16s ease,
    background-color 0.16s ease;
}

.wv4-home-entry__agent-button:hover,
.wv4-home-entry__agent-button:focus-visible {
  background: #1d4ed8;
  box-shadow: 0 14px 32px rgba(37, 99, 235, 0.22);
  transform: translateY(-1px);
}

.wv4-home-entry__agent-button:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 3px;
}
</style>
