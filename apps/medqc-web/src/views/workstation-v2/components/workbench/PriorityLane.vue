<template>
  <section class="priority-lane mb-4">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
      <h3 class="priority-lane__title">优先处理池</h3>

      <div class="priority-lane__segments">
        <button
          v-for="group in groups"
          :key="group.key"
          type="button"
          :class="[
            'priority-lane__segment',
            group.key === activeGroup
              ? 'priority-lane__segment--active'
              : 'priority-lane__segment--idle',
          ]"
          @click="emit('update:activeGroup', group.key)"
        >
          <span class="priority-lane__segment-label">{{ group.label }}</span>
          <span class="priority-lane__segment-count">{{ group.count }}</span>
        </button>
      </div>
    </div>

    <div
      v-if="cards.length === 0"
      class="priority-lane__empty mt-4 px-4 py-8 text-center text-[13px]"
    >
      暂无高优病历，建议切换科室或放宽筛选条件。
    </div>

    <div v-else class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-5">
      <article
        v-for="card in cards"
        :key="card.id"
        class="priority-lane__card group flex flex-col"
        :class="`priority-lane__card--${riskTypeClass(card.riskType)}`"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="priority-lane__card-name truncate" :title="card.patientName">
              {{ card.patientName }}
            </div>
            <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
              <span class="priority-lane__visit-id">
                {{ card.visitId }}
              </span>
              <span
                v-if="card.isDemo"
                class="priority-lane__pill--demo inline-flex items-center px-1.5 py-0.5 text-[10px] font-semibold rounded"
              >
                Demo
              </span>
            </div>
          </div>

          <div class="priority-lane__risk pt-1">
            <div class="priority-lane__risk-label">
              {{ riskLabel(card.riskType) }}
            </div>
            <div class="priority-lane__risk-value mt-0.5" title="住院天数">
              {{ card.hospitalDays }} 天
            </div>
          </div>
        </div>

        <div
          class="priority-lane__department mt-3 flex items-center gap-1.5 text-[12px] font-semibold"
        >
          <span class="priority-lane__department-dot inline-flex h-1.5 w-1.5 rounded-full" />
          {{ card.department || '未分科室' }}
        </div>
        <div v-if="card.riskText" class="priority-lane__risk-text mt-2 text-[12px] min-h-[36px]">
          {{ card.riskText }}
        </div>

        <div class="priority-lane__actions mt-4 flex items-center gap-2">
          <a-button type="primary" class="flex-1 rounded-md" @click="emit('open-record', card.id)">
            立即处理
          </a-button>
          <a-button
            class="rounded-md text-slate-500 hover:text-blue-600 border-none bg-slate-50 hover:bg-blue-50"
            :disabled="readonly"
            @click="emit('defer-record', card.id)"
          >
            稍后
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

function riskLabel(riskType: string) {
  const labels: Record<string, string> = {
    incomplete: '资料缺口',
    timeout: '临期处理',
    ai_failed: '待复核',
    demo: '演示样例',
    normal: '常规',
  }
  return labels[riskType] || '常规'
}

function riskTypeClass(riskType: string) {
  if (riskType === 'incomplete') return 'danger'
  if (riskType === 'timeout') return 'warning'
  if (riskType === 'ai_failed') return 'review'
  if (riskType === 'demo') return 'demo'
  return 'default'
}
</script>

<style src="./PriorityLane.style.css" scoped></style>

<style scoped>
@media (max-width: 1279px) {
  .priority-lane__segments {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 767px) {
  .priority-lane__segment {
    min-height: 40px;
    padding: 6px 10px;
  }
  .priority-lane__segment-count {
    font-size: 14px;
  }
}
</style>
