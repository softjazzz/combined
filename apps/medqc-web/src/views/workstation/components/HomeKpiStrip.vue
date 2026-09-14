<template>
  <section class="mt-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
    <button
      v-for="card in cards"
      :key="card.key"
      type="button"
      class="group relative overflow-hidden rounded-[16px] border p-4 text-left shadow-[0_1px_3px_rgba(0,0,0,0.02)] transition-all duration-200"
      :class="
        activeKey === card.key
          ? 'border-[#2b6cf6]/35 bg-[#eaf2ff]/60'
          : 'border-black/10 bg-white/85 hover:border-black/15 hover:bg-white'
      "
      @click="emit('select', card.key)"
    >
      <div
        class="absolute inset-y-0 left-0 w-1 transition-all"
        :class="[
          card.barColor,
          activeKey === card.key ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
        ]"
      />
      <div class="flex items-start justify-between gap-3 relative z-10">
        <div class="min-w-0">
          <div class="text-[12px] font-bold text-slate-500">
            {{ card.label }}
          </div>
          <div
            class="mt-1.5 text-[24px] font-bold text-[#1d1d1f] font-mono"
            style="font-variant-numeric: tabular-nums"
          >
            {{ card.value }}
          </div>
          <div class="mt-1 text-[11px] text-slate-400">
            {{ card.desc }}
          </div>
        </div>
        <div
          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
          :class="card.iconTint"
        >
          <component
            :is="card.icon"
            class="text-[16px]"
            :class="card.iconColor"
          />
        </div>
      </div>
    </button>
  </section>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  cards: Array<{
    key: string
    label: string
    value: number
    desc: string
    icon: Component
    iconTint: string
    iconColor: string
    barColor: string
  }>
  activeKey: string
}>()

const emit = defineEmits<{
  select: [key: string]
}>()
</script>
