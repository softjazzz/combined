<template>
  <span class="record-view-close-icon" :title="label" aria-hidden="true">
    <X :size="20" :stroke-width="2.35" />
  </span>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'
import '../styles/record-view-close.css'

defineProps<{ label: string }>()
</script>
