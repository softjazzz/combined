<template>
  <BasicLayout>
    <div style="padding:16px">
      <h2>首页</h2>
      <div style="margin-top:16px">
        <a-button type="primary" @click="load">加载示例记录</a-button>
        <div v-if="error" style="color:red;margin-top:8px">{{ error }}</div>
        <div v-if="records.length" style="margin-top:12px; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px;">
          <RecordCard v-for="r in records" :key="r.id" :id="r.id" :title="'Record ' + r.id" :status="'normal'" :createdAt="r.created_at" />
        </div>
      </div>
    </div>
  </BasicLayout>
  </template>

<script setup lang="ts">
import { ref } from 'vue'
import { listMedicalRecords } from '@/lib/api'
import { RecordCard } from '@health-qc/ui-qc'
import BasicLayout from '@/layouts/BasicLayout.vue'

const records = ref<any[]>([])
const error = ref('')

async function load() {
  error.value = ''
  const res = await listMedicalRecords()
  if (res.success && res.data) {
    records.value = Array.isArray(res.data) ? res.data : []
  } else {
    error.value = res.error?.message || 'Failed to load records'
  }
}
</script>


