<template>
  <section class="priority-lane p-4">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
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
      class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5"
    >
      <article
        v-for="card in cards"
        :key="card.id"
        class="priority-lane__card priority-lane__card--stack group relative flex h-full flex-col overflow-hidden p-3.5 transition duration-200 hover:-translate-y-0.5"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex min-w-0 items-start gap-3">
            <span class="priority-lane__avatar">
              <UserOutlined />
            </span>
            <div class="min-w-0">
              <div class="priority-lane__card-name truncate">
                {{ card.patientName }}
              </div>
              <div class="priority-lane__meta mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
                <span class="priority-lane__visit-id inline-flex items-center font-mono">
                  {{ card.visitId }}
                </span>
                <span
                  v-if="card.isDemo"
                  class="priority-lane__pill priority-lane__pill--demo inline-flex items-center text-[11px] font-semibold"
                >
                  样例
                </span>
              </div>
            </div>
          </div>

          <div
            class="priority-lane__risk text-right"
            :class="riskBadgeClass(card.riskType)"
          >
            <div class="text-[11px] font-bold">
              {{ riskLabel(card.riskType) }}
            </div>
            <div class="mt-1 text-[16px] font-extrabold">
              {{ card.hospitalDays }} 天
            </div>
            <div class="mt-0.5 text-[10px] font-semibold opacity-70">
              {{ riskHint(card.riskType) }}
            </div>
          </div>
        </div>

        <div
          class="priority-lane__department mt-3 flex items-center gap-2 text-[12px] font-semibold"
        >
          <span class="priority-lane__department-dot inline-flex h-2 w-2 rounded-full" />
          {{ card.department || '未分科室' }}
        </div>
        <div
          v-if="card.riskText"
          class="priority-lane__risk-text mt-2 min-h-[54px] text-[12px] font-semibold leading-5"
        >
          {{ card.riskText }}
        </div>

        <div class="priority-lane__actions mt-3 flex items-center gap-2">
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
import { UserOutlined } from '@ant-design/icons-vue'

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

function riskHint(riskType: string) {
  if (riskType === 'timeout' || riskType === 'normal') return '剩余处理天数'
  return '超时时长'
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
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.96);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.98),
    0 14px 32px rgba(148, 163, 184, 0.12);
}

.priority-lane__title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--workstation-text-primary, #1d1d1f);
}

.priority-lane__segments {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.priority-lane__segment {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  border: 1px solid rgba(226, 232, 240, 0.86);
  border-radius: var(--workstation-radius-pill, 999px);
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.9);
  text-align: center;
  transition:
    background-color 180ms ease,
    color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.priority-lane__segment--idle {
  color: var(--workstation-text-secondary, rgb(71 85 105));
  background: rgba(255, 255, 255, 0.88);
}

.priority-lane__segment--idle:hover {
  background: var(--workstation-bg-surface-strong, rgba(255, 255, 255, 0.92));
  color: var(--workstation-text-primary, rgb(15 23 42));
  box-shadow: var(--workstation-shadow-card, 0 10px 24px rgba(148, 163, 184, 0.12));
}

.priority-lane__segment--active {
  border-color: rgba(43, 108, 246, 0.18);
  background: rgba(43, 108, 246, 0.1);
  color: var(--workstation-primary, #2b6cf6);
  box-shadow: none;
  transform: translateY(-1px);
}

.priority-lane__segment--active::before {
  display: none;
}

.priority-lane__empty {
  border-radius: var(--workstation-radius-card, 24px);
  border: 1px dashed var(--workstation-divider, rgba(226, 232, 240, 0.88));
  background: rgba(248, 251, 255, 0.86);
  color: var(--workstation-text-secondary, rgb(91 107 132));
  box-shadow: var(--workstation-shadow-card, 0 16px 30px rgba(148, 163, 184, 0.1));
}

.priority-lane__card {
  border-radius: 14px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(255, 255, 255, 0.96);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.96),
    0 10px 24px rgba(148, 163, 184, 0.1);
}

.priority-lane__card:hover {
  border-color: rgba(147, 197, 253, 0.86);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.98),
    0 14px 30px rgba(148, 163, 184, 0.14);
}

.priority-lane__card:first-child {
  border-color: rgba(43, 108, 246, 0.26);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.98),
    0 10px 24px rgba(43, 108, 246, 0.08);
}

.priority-lane__card--stack {
  min-height: 142px;
}

.priority-lane__avatar {
  display: inline-flex;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #eaf2ff;
  color: var(--workstation-primary, #2b6cf6);
  font-size: 14px;
}

.priority-lane__card-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--workstation-text-primary, #1d1d1f);
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
  border: 0;
  background: transparent;
  color: var(--workstation-text-secondary, #5b6b84);
  box-shadow: none;
}

.priority-lane__pill--demo,
.priority-lane__risk--demo {
  background: color-mix(in srgb, var(--workstation-state-demo-bg, #eaf5ff) 84%, white);
  color: var(--workstation-state-demo-text, #0f6cbd);
  border: 0;
}

.priority-lane__risk {
  min-width: 74px;
  border: 0;
  padding: 7px 10px;
  box-shadow: none;
}

.priority-lane__risk--warning {
  background: color-mix(in srgb, var(--workstation-state-warning-bg, #fff6e5) 82%, white);
  color: var(--workstation-state-warning-text, #b85a00);
  border-color: transparent;
}

.priority-lane__risk--danger {
  background: color-mix(in srgb, var(--workstation-state-danger-bg, #fdeded) 82%, white);
  color: var(--workstation-state-danger-text, #b94a48);
  border-color: transparent;
}

.priority-lane__risk--review {
  background: color-mix(in srgb, var(--workstation-state-review-bg, #f3eeff) 82%, white);
  color: var(--workstation-state-review-text, #6e56cf);
  border-color: transparent;
}

.priority-lane__risk--default {
  background: var(--workstation-bg-card-soft, rgba(248, 250, 252, 0.92));
  color: var(--workstation-text-secondary, #5b6b84);
  border-color: transparent;
}

.priority-lane__department {
  color: var(--workstation-text-secondary, #5b6b84);
}

.priority-lane__department-dot {
  background: #93c5fd;
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.86);
}

.priority-lane__risk-text {
  color: rgba(15, 23, 42, 0.92);
  letter-spacing: -0.01em;
}

.priority-lane__actions {
  margin-top: auto;
}

.priority-lane__action {
  height: 34px !important;
  border-radius: 9px !important;
  padding: 0 16px !important;
  font-size: 12px !important;
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
  background: #2b6cf6 !important;
  color: #fff !important;
  box-shadow: 0 5px 14px rgba(43, 108, 246, 0.18) !important;
}

.priority-lane__card:hover .priority-lane__action--primary,
.priority-lane__action--primary:hover {
  background: #0057b8 !important;
  border-color: transparent !important;
  color: #fff !important;
  box-shadow: 0 8px 18px rgba(43, 108, 246, 0.22) !important;
}

.priority-lane__action--secondary {
  border-color: transparent !important;
  background: transparent !important;
  color: var(--workstation-text-muted, #94a3b8) !important;
  box-shadow: none !important;
  padding: 0 6px !important;
  height: 34px !important;
}

.priority-lane__action--secondary:hover {
  background: transparent !important;
  color: var(--workstation-brand-600, #1e5ae0) !important;
}

.priority-lane__segment-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  opacity: 0.9;
}

.priority-lane__segment-count {
  font-size: 13px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: 0;
}

@media (max-width: 1279px) {
  .priority-lane__segments {
    width: 100%;
  }
}

@media (max-width: 767px) {
  .priority-lane {
    padding: 16px;
  }

  .priority-lane__title {
    font-size: 20px;
  }

  .priority-lane__segments {
    gap: 6px;
  }

  .priority-lane__segment {
    min-height: 32px;
    padding: 6px 10px;
  }

  .priority-lane__segment-count {
    font-size: 12px;
  }
}
</style>
