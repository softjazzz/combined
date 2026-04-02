<template>
  <QCOverviewView v-if="showHome" />
  <WorkstationV4View v-else />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import QCOverviewView from '@/views/workstation/QCOverviewView.vue'
import WorkstationV4View from './WorkstationV4View.vue'

const route = useRoute()
const authStore = useAuthStore()

const hasLaunchQuery = computed(() => {
  return ['record_id', 'action', 'from_stage', 'taskId', 'stage'].some((key) => {
    return typeof route.query[key] === 'string' && String(route.query[key] || '').trim() !== ''
  })
})

const isHomeRole = computed(() => authStore.hasRole('admin') || authStore.hasRole('qc_manager'))

const showHome = computed(() => isHomeRole.value && !hasLaunchQuery.value)
</script>
