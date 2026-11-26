<template>
  <WorkstationAssistPanel
    v-if="showHost"
    v-model:visible="visible"
    :available-tabs="['chat']"
    default-tab="chat"
    chat-label="问数"
    data-testid="global-assistant-host"
  >
    <template #chat="{ active }">
      <BusinessAgentDrawer
        embedded
        allow-case-selection
        :open="active"
        :user-context="{ view: 'manager' }"
      />
    </template>
  </WorkstationAssistPanel>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { businessAgentApi } from '@/api/businessAgent'
import { useAuthStore } from '@/stores/auth'
import { hasLocalAssistant } from '../composables/useAssistantRegistry'
import BusinessAgentDrawer from './BusinessAgentDrawer.vue'
import WorkstationAssistPanel from './WorkstationAssistPanel.vue'

// 布局层常驻的智能助手：页面没有带病例上下文的面板时显示，只含“对话/问数”。
// 没有任何医生病例或管理范围授权的账号不显示入口，避免打开后只看到授权错误。
function resolveAuthStore() {
  try {
    return useAuthStore()
  } catch {
    return null
  }
}

const authStore = resolveAuthStore()
const visible = ref(false)
const authorized = ref(false)
let requestSeq = 0

async function refreshAccess() {
  const seq = ++requestSeq
  authorized.value = false
  visible.value = false
  if (authStore && !authStore.user?.id) {
    return
  }
  try {
    const access = await businessAgentApi.access()
    if (seq !== requestSeq) return
    authorized.value = !!access.doctor_case_count || !!access.manager_scopes?.length
  } catch (cause) {
    if (seq !== requestSeq) return
    // 403 / 无授权属于预期场景，静默隐藏入口，不向控制台刷错。
    if (isAxiosError(cause) && cause.response?.status === 403) {
      authorized.value = false
      visible.value = false
      return
    }
    authorized.value = false
    visible.value = false
  }
}

if (authStore) {
  watch(
    () => authStore.user?.id ?? '',
    () => {
      void refreshAccess()
    },
    { immediate: true },
  )
} else {
  onMounted(() => {
    void refreshAccess()
  })
}

onBeforeUnmount(() => {
  requestSeq += 1
})

const showHost = computed(() => authorized.value && !hasLocalAssistant.value)
</script>
