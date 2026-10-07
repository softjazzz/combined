<template>
  <div
    class="icd-detail-panel mq-card flex h-full flex-col overflow-hidden border border-[var(--mq-border)]"
  >
    <div
      v-if="!selectedCode"
      class="flex flex-1 flex-col items-center justify-center px-6 py-16 text-center"
    >
      <div
        class="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-[var(--mq-info-border)]"
      >
        <svg class="h-8 w-8 text-blue-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.5"
            d="M10 21h7a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v11m0 5l4.879-4.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242z"
          />
        </svg>
      </div>
      <h4 class="mb-2 text-[15px] font-semibold text-[var(--mq-text-primary)]">选择编码查看详情</h4>
      <p class="text-[13px] leading-relaxed text-[var(--mq-text-tertiary)]">
        从左侧搜索结果或树形目录中选择任意编码，<br />即可在这里查看完整信息。
      </p>
    </div>

    <template v-else>
      <div class="border-b border-slate-100 p-6">
        <div class="mb-3 flex items-center justify-between">
          <div>
            <div
              class="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--mq-text-tertiary)]"
            >
              知识侧栏
            </div>
            <div class="mt-1 text-[12px] text-[var(--mq-text-secondary)]">
              版本映射、层级归属、包含项与排除项
            </div>
          </div>
          <span
            class="rounded-full border border-[var(--mq-info-border)] bg-[var(--mq-info-bg)] px-2.5 py-1 text-[11px] font-semibold text-[var(--mq-info-text)]"
          >
            {{ selectedCode.type === 'icd10' ? '诊断' : '手术' }}
          </span>
        </div>

        <div class="mb-3 flex items-start justify-between">
          <span
            class="rounded-md border border-[var(--mq-info-border)] bg-[var(--mq-info-bg)] px-2.5 py-1 text-[11px] font-bold text-[var(--mq-info-text)]"
          >
            {{ selectedCode.type === 'icd10' ? 'ICD-10 诊断' : 'ICD-9-CM-3 手术' }}
          </span>

          <div class="flex items-center gap-2">
            <button
              class="group flex cursor-pointer items-center gap-1.5 rounded-xl border border-[var(--mq-border)] bg-white px-3 py-1.5 text-[12px] font-semibold text-[var(--mq-text-secondary)] shadow-sm transition-all hover:border-blue-300 hover:text-[#0a6cff]"
              @click="$emit('copy', selectedCode.code)"
            >
              <MqIcon
                name="copy"
                class="text-[var(--mq-text-tertiary)] transition-colors group-hover:text-[#0a6cff]"
              />
              复制
            </button>
            <button
              v-if="allowApply"
              class="flex cursor-pointer items-center gap-1.5 rounded-xl bg-gradient-to-r from-[#0a6cff] to-[#0a5fd6] px-3 py-1.5 text-[12px] font-semibold text-white transition-all hover:from-[#0a5fd6] hover:to-[#0a5fd6]"
              @click="$emit('apply', selectedCode)"
            >
              <MqIcon name="success" />
              {{ applyLabel || '采用' }}
            </button>
          </div>
        </div>

        <div
          class="mb-2 font-mono text-[28px] font-extrabold tracking-tight text-[var(--mq-info-text)]"
        >
          {{ selectedCode.code }}
        </div>
        <h2 class="text-[18px] font-bold leading-snug text-[var(--mq-text-primary)]">
          {{ selectedCode.name }}
        </h2>
      </div>

      <div class="custom-scrollbar flex-1 space-y-5 overflow-y-auto p-6">
        <div v-if="selectedCode.category_path?.length">
          <h4
            class="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--mq-text-tertiary)]"
          >
            层级归属
          </h4>
          <div class="flex flex-col gap-1.5 text-[13px]">
            <div
              v-for="(item, i) in selectedCode.category_path"
              :key="i"
              class="flex items-center gap-2 text-[var(--mq-text-secondary)]"
            >
              <span class="min-w-[12px] font-mono text-[12px] text-blue-300">{{
                i === selectedCode.category_path.length - 1 ? '└' : '├'
              }}</span>
              <span
                :class="
                  i === selectedCode.category_path.length - 1
                    ? 'font-medium text-[var(--mq-text-primary)]'
                    : ''
                "
                >{{ item }}</span
              >
            </div>
          </div>
        </div>

        <div v-if="selectedCode.mapped_code">
          <div class="mb-5 h-px w-full bg-slate-100" />
          <h4
            class="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--mq-text-tertiary)]"
          >
            版本对照
          </h4>
          <div
            class="rounded-2xl border border-[var(--mq-info-border)]/80 bg-[var(--mq-info-bg)]/50 p-3.5 text-[13px]"
          >
            <div class="mb-1 flex items-center gap-3">
              <span class="font-mono font-semibold text-[var(--mq-text-primary)]">{{
                selectedCode.code
              }}</span>
              <span class="text-[var(--mq-text-tertiary)]">→</span>
              <span class="font-mono font-semibold text-[var(--mq-info-text)]">
                {{ selectedCode.mapped_code }}
              </span>
            </div>
            <div class="flex items-center gap-1 text-[12px]">
              <span class="text-[#0a6cff]">
                {{ selectedCode.is_diff ? '编码有差异' : '编码一致' }}
              </span>
              <span
                v-if="selectedCode.mapped_name && selectedCode.is_diff"
                class="ml-2 text-[var(--mq-text-secondary)]"
              >
                {{ selectedCode.mapped_name }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="selectedCode.inclusions?.length">
          <div class="mb-5 h-px w-full bg-slate-100" />
          <h4
            class="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--mq-text-tertiary)]"
          >
            <span class="mr-1 text-blue-500">●</span> 包含
          </h4>
          <ul
            class="list-disc space-y-1 pl-4 text-[13px] text-[var(--mq-text-secondary)] marker:text-blue-400"
          >
            <li v-for="(item, i) in selectedCode.inclusions" :key="i">
              {{ item }}
            </li>
          </ul>
        </div>

        <div v-if="selectedCode.exclusions?.length">
          <div class="mb-5 h-px w-full bg-slate-100" />
          <h4
            class="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--mq-text-tertiary)]"
          >
            <span class="mr-1 text-blue-500">●</span> 排除
          </h4>
          <ul
            class="list-disc space-y-1 pl-4 text-[13px] text-[var(--mq-text-secondary)] marker:text-blue-300"
          >
            <li v-for="(item, i) in selectedCode.exclusions" :key="i">
              {{ item }}
            </li>
          </ul>
        </div>

        <div
          v-if="
            !selectedCode.category_path?.length &&
            !selectedCode.mapped_code &&
            !selectedCode.inclusions?.length
          "
        >
          <div class="mb-5 h-px w-full bg-slate-100" />
          <h4
            class="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--mq-text-tertiary)]"
          >
            知识摘要
          </h4>
          <div
            class="rounded-2xl border border-slate-100 bg-slate-50/80 p-3.5 text-[13px] leading-relaxed text-[var(--mq-text-secondary)]"
          >
            点击树形节点中的叶子编码，可查看更多层级归属与版本对照信息。
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import MqIcon from '@/components/icons/MqIcon.vue'

export interface ICDCodeDetail {
  code: string
  name: string
  type: 'icd10' | 'icd9cm3'
  category_path?: string[]
  mapped_code?: string
  mapped_name?: string
  mapped_version?: string
  is_diff?: boolean
  inclusions?: string[]
  exclusions?: string[]
}

defineProps<{
  selectedCode: ICDCodeDetail | null
  allowApply?: boolean
  applyLabel?: string
}>()

defineEmits<{
  copy: [code: string]
  apply: [detail: ICDCodeDetail]
}>()
</script>

<style scoped src="../styles/icd-detail-panel.css"></style>
