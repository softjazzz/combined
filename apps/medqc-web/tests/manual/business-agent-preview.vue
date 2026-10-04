<template>
  <main style="padding: 24px">
    <h1>智能业务助手合成联调</h1>
    <p>真实 DSH 与已配置模型，业务接口使用合成数据，未连接客户数据库。</p>
    <a-space>
      <a-button @click="select('A')"> 合成病例 A </a-button>
      <a-button @click="select('B')"> 合成病例 B </a-button>
      <a-button @click="select('manager')"> 管理问数 </a-button>
    </a-space>
    <BusinessAgentDrawer v-model:open="open" :user-context="context" />
  </main>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import BusinessAgentDrawer from '@/views/workstation-v4/components/BusinessAgentDrawer.vue'
import type { BusinessAgentContext } from '@/api/businessAgent'
const open = ref(false)
const context = ref<BusinessAgentContext>({ view: 'manager', department: '合成科室' })
function select(value: string) {
  context.value =
    value === 'manager'
      ? { view: 'manager', department: '合成科室' }
      : {
          view: 'doctor',
          institute_id: 'SYNTHETIC',
          patient_id: value,
          visit_id: `${value}1`,
          patient_name: `合成病例${value}`,
        }
  open.value = true
}
</script>
