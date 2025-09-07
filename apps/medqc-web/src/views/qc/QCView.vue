<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">质控管理</h1>
      <a-button type="primary" :icon="h(PlayCircleOutlined)">
        批量质控
      </a-button>
    </div>
    
    <a-card>
      <div class="text-center p-8">
        <CheckCircleOutlined class="text-6xl text-blue-500 mb-4" />
        <h3 class="text-xl font-semibold mb-2">质控管理中心</h3>
        <p class="text-gray-600">智能病案质量控制系统</p>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { PlayCircleOutlined, CheckCircleOutlined } from '@ant-design/icons-vue'
</script>

<style scoped>
.page-container {
  @apply p-6;
}
.page-header {
  @apply flex items-center justify-between mb-6;
}
.page-title {
  @apply text-2xl font-bold text-gray-900;
}
</style> 