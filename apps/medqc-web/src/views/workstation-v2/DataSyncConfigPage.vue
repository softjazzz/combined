<template>
  <div class="sync-page">
    <div class="sync-page__inner">
      <DataSyncConfig />
    </div>
  </div>
</template>

<script setup lang="ts">
import DataSyncConfig from '@/components/settings/DataSyncConfig.vue'
</script>

<style scoped>
.sync-page {
  min-height: calc(100vh - 64px);
  padding: 24px;
  background: #f8fafc;
}

@media (min-width: 768px) {
  .sync-page {
    padding: 32px;
  }
}

.sync-page__inner {
  max-width: 1120px;
  margin: 0 auto;
}
</style>
