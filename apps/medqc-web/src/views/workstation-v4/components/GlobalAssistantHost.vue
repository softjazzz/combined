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
import { computed, onMounted, ref } from 'vue'
import { businessAgentApi } from '@/api/businessAgent'
import { hasLocalAssistant } from '../composables/useAssistantRegistry'
import BusinessAgentDrawer from './BusinessAgentDrawer.vue'
import WorkstationAssistPanel from './WorkstationAssistPanel.vue'

// 布局层常驻的智能助手：页面没有带病例上下文的面板时显示，只含“对话/问数”。
// 没有任何医生病例或管理范围授权的账号不显示入口，避免打开后只看到授权错误。
const visible = ref(false)
const authorized = ref(false)

onMounted(() => {
  businessAgentApi.access().then(
    (access) => {
      authorized.value = !!access.doctor_case_count || !!access.manager_scopes?.length
    },
    () => {
      authorized.value = false
    },
  )
})

const showHost = computed(() => authorized.value && !hasLocalAssistant.value)
</script>
