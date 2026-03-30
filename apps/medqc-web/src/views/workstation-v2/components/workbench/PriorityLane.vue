<template>
  <section class="priority-lane p-6">
    <div class="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 xl:max-w-[520px]">
        <h3 class="priority-lane__title">
          优先处理池
        </h3>
      </div>

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
      class="priority-lane__empty mt-5 px-4 py-10 text-center text-[13px]"
    >
      暂无高优病历，建议切换科室或放宽筛选条件。
    </div>

    <div
      v-else
      class="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6"
    >
      <article
        v-for="card in cards"
        :key="card.id"
        class="priority-lane__card group relative overflow-hidden p-3.5 transition duration-300 hover:-translate-y-1"
      >
        <div
          class="priority-lane__card-highlight pointer-events-none absolute inset-x-4 top-0 h-px"
        />

        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="priority-lane__card-name truncate">
              {{ card.patientName }}
            </div>
            <div class="priority-lane__meta mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
              <span
                class="priority-lane__visit-id inline-flex items-center px-2.5 py-1 font-mono text-[11px]"
              >
                {{ card.visitId }}
              </span>
              <span
                v-if="card.isDemo"
                class="priority-lane__pill priority-lane__pill--demo inline-flex items-center px-2.5 py-1 text-[11px] font-semibold"
              >
                Demo
              </span>
            </div>
          </div>

          <div
            class="priority-lane__risk text-right"
            :class="riskBadgeClass(card.riskType)"
          >
            <div class="text-[10px] font-bold uppercase tracking-[0.18em] opacity-70">
              {{ riskLabel(card.riskType) }}
            </div>
            <div class="mt-1 text-[12px] font-bold">
              {{ card.hospitalDays }} 天
            </div>
          </div>
        </div>

        <div
          class="priority-lane__department mt-3 flex items-center gap-2 text-[11px] font-semibold"
        >
          <span class="priority-lane__department-dot inline-flex h-2 w-2 rounded-full" />
          {{ card.department || '未分科室' }}
        </div>
        <div class="priority-lane__risk-text mt-2 min-h-[54px] text-[12px] font-semibold leading-5">
          {{ card.riskText }}
        </div>

        <div class="mt-3 flex items-center gap-2">
          <a-button
            type="primary"
            size="small"
            class="priority-lane__action priority-lane__action--primary group-hover:!translate-y-[-1px]"
            @click="emit('open-record', card.id)"
          >
            立即处理
          </a-button>
          <a-button
            size="small"
            class="priority-lane__action priority-lane__action--secondary"
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
  if (riskType === 'incomplete') return 'priority-lane__risk--danger'
  if (riskType === 'timeout') return 'priority-lane__risk--warning'
  if (riskType === 'ai_failed') return 'priority-lane__risk--review'
  if (riskType === 'demo') return 'priority-lane__risk--demo'
  return 'priority-lane__risk--default'
}
</script>

<style scoped>
.priority-lane {
  overflow: hidden;
  border-radius: 32px;
  border: 1px solid rgba(255, 255, 255, 0.85);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 248, 251, 0.96));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 28px 60px rgba(148, 163, 184, 0.14);
}

.priority-lane__title {
  font-size: 28px;
  font-weight: 900;
  letter-spacing: -0.05em;
  color: var(--workstation-text-primary, #0f172a);
}

.priority-lane__segments {
  display: grid;
  grid-template-columns: repeat(5, minmax(96px, 1fr));
  gap: 8px;
  border-radius: var(--workstation-radius-panel, 30px);
  background: var(--workstation-bg-card-soft, rgba(242, 245, 249, 0.9));
  padding: 8px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 18px 36px rgba(148, 163, 184, 0.12);
}

.priority-lane__segment {
  position: relative;
  display: grid;
  gap: 6px;
  justify-items: start;
  min-height: 82px;
  border-radius: var(--workstation-radius-card, 22px);
  padding: 14px 16px;
  text-align: left;
  transition:
    background-color 180ms ease,
    color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.priority-lane__segment--idle {
  color: var(--workstation-text-secondary, rgb(71 85 105));
  background: rgba(255, 255, 255, 0.6);
}

.priority-lane__segment--idle:hover {
  background: var(--workstation-bg-surface-strong, rgba(255, 255, 255, 0.92));
  color: var(--workstation-text-primary, rgb(15 23 42));
  box-shadow: var(--workstation-shadow-card, 0 10px 24px rgba(148, 163, 184, 0.12));
}

.priority-lane__segment--active {
  background: linear-gradient(
    180deg,
    var(--workstation-brand-050, rgba(234, 242, 255, 0.98)),
    rgba(245, 249, 255, 0.98)
  );
  color: var(--workstation-brand-600, rgb(30 90 224));
  box-shadow:
    0 18px 34px var(--workstation-brand-shadow, rgba(191, 219, 254, 0.3)),
    inset 0 1px 0 rgba(255, 255, 255, 0.98);
  transform: translateY(-1px);
}

.priority-lane__segment--active::before {
  content: '';
  position: absolute;
  left: 16px;
  right: 16px;
  top: 0;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(47, 111, 237, 0.88), rgba(147, 197, 253, 0.4));
}

.priority-lane__empty {
  border-radius: var(--workstation-radius-card, 24px);
  border: 1px dashed var(--workstation-divider, rgba(226, 232, 240, 0.88));
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(248, 250, 252, 0.9));
  color: var(--workstation-text-secondary, rgb(91 107 132));
  box-shadow: var(--workstation-shadow-card, 0 16px 30px rgba(148, 163, 184, 0.1));
}

.priority-lane__card {
  border-radius: 30px;
  border: 1px solid rgba(255, 255, 255, 0.78);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 252, 0.84)),
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.96),
    0 18px 44px rgba(191, 207, 228, 0.24),
    0 2px 10px rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(20px);
}

.priority-lane__card:hover {
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.98),
    0 24px 56px rgba(191, 207, 228, 0.32),
    0 2px 12px rgba(255, 255, 255, 0.72);
}

.priority-lane__card-highlight {
  background: linear-gradient(
    90deg,
    rgba(148, 163, 184, 0),
    rgba(255, 255, 255, 0.88),
    rgba(148, 163, 184, 0)
  );
}

.priority-lane__card-name {
  font-size: 19px;
  font-weight: 900;
  letter-spacing: -0.04em;
  color: var(--workstation-text-primary, #0f172a);
}

.priority-lane__meta {
  color: var(--workstation-text-secondary, #5b6b84);
}

.priority-lane__visit-id,
.priority-lane__pill,
.priority-lane__risk {
  border-radius: var(--workstation-radius-pill, 999px);
}

.priority-lane__visit-id {
  border: 1px solid rgba(255, 255, 255, 0.86);
  background: rgba(246, 248, 252, 0.88);
  color: var(--workstation-text-secondary, #5b6b84);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.88),
    0 6px 16px rgba(191, 207, 228, 0.12);
}

.priority-lane__pill--demo,
.priority-lane__risk--demo {
  background: var(--workstation-state-demo-bg, #eaf5ff);
  color: var(--workstation-state-demo-text, #0f6cbd);
  border: 1px solid rgba(191, 219, 254, 0.9);
}

.priority-lane__risk {
  border: 1px solid rgba(255, 255, 255, 0.78);
  padding: 8px 12px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 10px 24px rgba(191, 207, 228, 0.2);
  backdrop-filter: blur(16px);
}

.priority-lane__risk--warning {
  background: var(--workstation-state-warning-bg, #fff6e5);
  color: var(--workstation-state-warning-text, #b85a00);
  border-color: rgba(253, 230, 138, 0.9);
}

.priority-lane__risk--danger {
  background: var(--workstation-state-danger-bg, #fdeded);
  color: var(--workstation-state-danger-text, #b94a48);
  border-color: rgba(252, 165, 165, 0.9);
}

.priority-lane__risk--review {
  background: var(--workstation-state-review-bg, #f3eeff);
  color: var(--workstation-state-review-text, #6e56cf);
  border-color: rgba(216, 180, 254, 0.9);
}

.priority-lane__risk--default {
  background: var(--workstation-bg-card-soft, rgba(248, 250, 252, 0.92));
  color: var(--workstation-text-secondary, #5b6b84);
  border-color: var(--workstation-border-soft, rgba(15, 23, 42, 0.06));
}

.priority-lane__department {
  color: var(--workstation-text-secondary, #5b6b84);
}

.priority-lane__department-dot {
  background: linear-gradient(180deg, rgba(191, 219, 254, 0.98), rgba(148, 163, 184, 0.72));
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.86);
}

.priority-lane__risk-text {
  color: rgba(15, 23, 42, 0.92);
  letter-spacing: -0.01em;
}

.priority-lane__action {
  height: 38px !important;
  border-radius: var(--workstation-radius-pill, 999px) !important;
  padding: 0 16px !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  transition:
    transform 160ms ease,
    box-shadow 160ms ease,
    border-color 160ms ease,
    background-color 160ms ease,
    color 160ms ease;
}

.priority-lane__action--primary {
  border: 0 !important;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--workstation-brand-500, #2f6fed) 86%, white),
    var(--workstation-brand-500, #2f6fed)
  ) !important;
  color: #fff !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.24),
    0 14px 28px rgba(47, 111, 237, 0.28) !important;
}

.priority-lane__action--primary:hover {
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--workstation-brand-600, #1e5ae0) 84%, white),
    var(--workstation-brand-600, #1e5ae0)
  ) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.28),
    0 16px 30px rgba(47, 111, 237, 0.32) !important;
}

.priority-lane__action--secondary {
  border-color: rgba(191, 219, 254, 0.84) !important;
  background: rgba(255, 255, 255, 0.82) !important;
  color: var(--workstation-text-secondary, #5b6b84) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 10px 20px rgba(191, 207, 228, 0.16) !important;
  backdrop-filter: blur(14px);
}

.priority-lane__action--secondary:hover {
  border-color: rgba(191, 219, 254, 0.95) !important;
  color: var(--workstation-brand-600, #1e5ae0) !important;
}

.priority-lane__segment-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  opacity: 0.9;
}

.priority-lane__segment-count {
  font-size: 28px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.05em;
}

@media (max-width: 1279px) {
  .priority-lane__segments {
    width: 100%;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .priority-lane {
    padding: 20px;
  }

  .priority-lane__title {
    font-size: 24px;
  }

  .priority-lane__segments {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .priority-lane__segment {
    min-height: 72px;
    padding: 12px 14px;
  }

  .priority-lane__segment--active::before {
    left: 14px;
    right: 14px;
  }

  .priority-lane__segment-count {
    font-size: 22px;
  }
}
</style>
