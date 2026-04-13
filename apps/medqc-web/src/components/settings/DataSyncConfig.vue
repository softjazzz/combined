<template>
  <div class="ds-root">
    <div class="ds-card">
      <h3 class="ds-title">
        数据同步配置（PG）
      </h3>
      <p class="ds-desc">
        旧数据源配置入口已下线。当前系统仅支持 PG 同步链路：远端 PG → 本地 PG。
      </p>
      <div class="ds-row">
        <span>远端连接：</span>
        <strong>{{ remoteConnected ? '已连接' : '未连接' }}</strong>
      </div>
      <div class="ds-row">
        <span>本地连接：</span>
        <strong>{{ localConnected ? '已连接' : '未连接' }}</strong>
      </div>
      <div class="ds-actions">
        <a-button
          :loading="loading"
          @click="reload"
        >
          刷新状态
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { syncApi } from '@/api/sync'

const loading = ref(false)
const remoteConnected = ref(false)
const localConnected = ref(false)

async function reload() {
  loading.value = true
  try {
    const status = await syncApi.testAllConnections()
    remoteConnected.value = Boolean(status.pg_remote?.connected)
    localConnected.value = Boolean(status.pg_local?.connected)
  } catch (error: any) {
    message.error(error?.response?.data?.detail || error?.message || '刷新连接状态失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void reload()
})
</script>

<style scoped>
.ds-root {
  padding: 16px;
}

.ds-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  padding: 16px;
}

.ds-title {
  margin: 0 0 8px;
  font-size: 16px;
}

.ds-desc {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 13px;
}

.ds-row {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.ds-actions {
  margin-top: 12px;
}
</style>
