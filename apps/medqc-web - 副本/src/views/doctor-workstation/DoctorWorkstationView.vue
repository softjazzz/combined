<template>
  <div class="doctor-workstation-view">
    <DoctorWorkstation />
  </div>
</template>

<script setup lang="ts">
import DoctorWorkstation from '@/components/doctor-workstation/DoctorWorkstation.vue'

// 设置页面元信息
defineOptions({
  name: 'DoctorWorkstationView'
})
</script>

<style scoped>
.doctor-workstation-view {
  height: 100vh;
  overflow: hidden;
}
</style>
