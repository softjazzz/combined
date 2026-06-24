<template>
  <div class="analytics-view">
    <AnalyticsDashboard />
  </div>
</template>

<script setup lang="ts">
import AnalyticsDashboard from '../../components/analytics/AnalyticsDashboard.vue'
</script>

<style scoped>
.analytics-view {
  height: 100vh;
  overflow: auto;
}
</style> 