<template>
  <section
    class="priority-lane overflow-hidden rounded-[28px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(244,247,251,0.96))] p-5 shadow-[0_20px_48px_rgba(15,23,42,0.07)]"
  >
    <div class="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
      <div class="min-w-0">
        <div class="text-[11px] font-bold uppercase tracking-[0.22em] text-slate-400">
          Priority Lane
        </div>
        <div class="mt-2 flex flex-wrap items-end gap-3">
          <h3 class="text-[24px] font-black tracking-[-0.04em] text-slate-950">
            优先处理池
          </h3>
          <span class="inline-flex items-center rounded-full border border-slate-200/80 bg-white/90 px-3 py-1 text-[12px] font-semibold text-slate-500">
            首屏聚焦高风险与临期病历
          </span>
        </div>
        <p class="mt-2 max-w-[520px] text-[13px] leading-6 text-slate-500">
          先处理更容易影响当日清理进度的病历，再进入单案详情完成复核与补录。
        </p>
      </div>

      <div class="flex flex-wrap gap-2 rounded-[22px] border border-slate-200/70 bg-white/85 p-1.5 shadow-[0_10px_24px_rgba(15,23,42,0.04)]">
        <button
          v-for="group in groups"
          :key="group.key"
          type="button"
          :class="[
            'inline-flex items-center gap-2 rounded-[16px] px-3.5 py-2 text-[12px] font-semibold transition-all duration-200',
            group.key === activeGroup
              ? 'bg-slate-950 text-white shadow-[0_12px_22px_rgba(15,23,42,0.16)]'
              : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900',
          ]"
          @click="emit('update:activeGroup', group.key)"
        >
          <span>{{ group.label }}</span>
          <span
            :class="[
              'inline-flex min-w-[24px] items-center justify-center rounded-full px-1.5 py-0.5 text-[11px] font-bold',
              group.key === activeGroup ? 'bg-white/12 text-white' : 'bg-slate-100 text-slate-500',
            ]"
          >
            {{ group.count }}
          </span>
        </button>
      </div>
    </div>

    <div
      v-if="cards.length === 0"
      class="mt-5 rounded-[22px] border border-dashed border-slate-200/90 bg-white/75 px-4 py-10 text-center text-[13px] text-slate-500"
    >
      暂无高优病历，建议切换科室或放宽筛选条件。
    </div>

    <div
      v-else
      class="mt-5 grid grid-cols-1 gap-3.5 xl:grid-cols-4"
    >
      <article
        v-for="card in cards"
        :key="card.id"
        class="group relative overflow-hidden rounded-[24px] border border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(250,252,255,0.92))] p-4 shadow-[0_10px_30px_rgba(15,23,42,0.05)] transition duration-300 hover:-translate-y-1 hover:border-slate-300/70 hover:shadow-[0_20px_38px_rgba(15,23,42,0.1)]"
      >
        <div class="pointer-events-none absolute inset-x-0 top-0 h-1.5 bg-[linear-gradient(90deg,rgba(37,99,235,0.9),rgba(14,165,233,0.55),rgba(255,255,255,0))] opacity-75" />

        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="truncate text-[22px] font-black tracking-[-0.04em] text-slate-950">
              {{ card.patientName }}
            </div>
            <div class="mt-2 flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
              <span class="inline-flex items-center rounded-full bg-slate-100/90 px-2.5 py-1 font-mono text-[11px] text-slate-600">
                {{ card.visitId }}
              </span>
              <span
                v-if="card.isDemo"
                class="inline-flex items-center rounded-full border border-blue-200/80 bg-blue-50/90 px-2.5 py-1 text-[11px] font-semibold text-blue-700"
              >
                Demo
              </span>
            </div>
          </div>

          <div
            class="rounded-[18px] border px-3 py-2 text-right"
            :class="riskBadgeClass(card.riskType)"
          >
            <div class="text-[10px] font-bold uppercase tracking-[0.18em] opacity-70">
              {{ riskLabel(card.riskType) }}
            </div>
            <div class="mt-1 text-[14px] font-bold">
              {{ card.hospitalDays }} 天
            </div>
          </div>
        </div>

        <div class="mt-4 flex items-center gap-2 text-[12px] font-semibold text-slate-500">
          <span class="inline-flex h-2 w-2 rounded-full bg-blue-500/70" />
          {{ card.department || '未分科室' }}
        </div>
        <div class="mt-3 min-h-[44px] text-[13px] font-semibold leading-6 text-slate-700">
          {{ card.riskText }}
        </div>

        <div class="mt-4 flex items-center gap-2.5">
          <a-button
            type="primary"
            size="small"
            class="!h-9 !rounded-full !border-0 !bg-slate-950 !px-4 !font-semibold !shadow-[0_12px_20px_rgba(15,23,42,0.18)] transition group-hover:!translate-y-[-1px]"
            @click="emit('open-record', card.id)"
          >
            立即处理
          </a-button>
          <a-button
            size="small"
            class="!h-9 !rounded-full !border-slate-200/90 !bg-white/90 !px-4 !font-semibold !text-slate-600 !shadow-none"
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

function riskBadgeClass(riskType: string) {
  if (riskType === 'incomplete') return 'border-rose-200 bg-rose-50/90 text-rose-700'
  if (riskType === 'timeout') return 'border-amber-200 bg-amber-50/90 text-amber-700'
  if (riskType === 'ai_failed') return 'border-violet-200 bg-violet-50/90 text-violet-700'
  if (riskType === 'demo') return 'border-sky-200 bg-sky-50/90 text-sky-700'
  return 'border-slate-200 bg-slate-50/90 text-slate-600'
}
</script>
