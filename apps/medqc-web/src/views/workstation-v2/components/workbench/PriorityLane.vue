<template>
  <section
    class="rounded-2xl border border-slate-200/70 bg-white p-4 shadow-[0_8px_24px_rgba(15,23,42,0.05)]"
  >
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h3 class="text-[18px] font-bold tracking-tight text-slate-900">
          优先处理池
        </h3>
        <p class="mt-1 text-[12px] text-slate-500">
          先处理高风险与临期病案，提升日清效率。
        </p>
      </div>
      <a-space
        size="small"
        wrap
      >
        <a-tag
          v-for="group in groups"
          :key="group.key"
          :color="group.key === activeGroup ? 'blue' : 'default'"
          class="cursor-pointer select-none"
          @click="emit('update:activeGroup', group.key)"
        >
          {{ group.label }} {{ group.count }}
        </a-tag>
      </a-space>
    </div>

    <div
      v-if="cards.length === 0"
      class="mt-4 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-[13px] text-slate-500"
    >
      暂无高优病历，建议切换科室或放宽筛选条件。
    </div>

    <div
      v-else
      class="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-4"
    >
      <article
        v-for="card in cards"
        :key="card.id"
        class="rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition hover:-translate-y-0.5 hover:shadow-[0_10px_18px_rgba(15,23,42,0.08)]"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="truncate text-[18px] font-black tracking-tight text-slate-900">
              {{ card.patientName }}
            </div>
            <div class="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
              <span class="font-mono">{{ card.visitId }}</span>
              <a-tag
                v-if="card.isDemo"
                color="blue"
              >
                Demo
              </a-tag>
            </div>
          </div>
          <a-tag color="red">
            住院 {{ card.hospitalDays }} 天
          </a-tag>
        </div>

        <div class="mt-3 text-[13px] text-slate-600">
          {{ card.department || '未分科室' }}
        </div>
        <div class="mt-1 text-[12px] font-medium text-amber-700">
          {{ card.riskText }}
        </div>

        <div class="mt-3 flex gap-2">
          <a-button
            type="primary"
            size="small"
            @click="emit('open-record', card.id)"
          >
            立即处理
          </a-button>
          <a-button
            size="small"
            :disabled="readonly"
            @click="emit('defer-record', card.id)"
          >
            标记稍后
          </a-button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
export interface PriorityGroup {
  key: string
  label: string
  count: number
}

export interface PriorityCard {
  id: string
  patientName: string
  visitId: string
  department: string
  hospitalDays: number
  riskType: string
  riskText: string
  isDemo: boolean
  updatedAt: string
}

defineProps<{
  groups: PriorityGroup[]
  activeGroup: string
  cards: PriorityCard[]
  readonly?: boolean
}>()

const emit = defineEmits<{
  'update:activeGroup': [value: string]
  'open-record': [id: string]
  'defer-record': [id: string]
}>()
</script>
