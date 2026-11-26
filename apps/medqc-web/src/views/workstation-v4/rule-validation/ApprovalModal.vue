<template>
  <a-modal
    :open="open"
    :footer="null"
    :width="640"
    centered
    wrap-class-name="mq-modal"
    :mask-style="{ backdropFilter: 'blur(6px)' }"
    @cancel="emit('close')"
  >
    <div
      v-if="open"
      class="rv-approval-modal"
      data-testid="approval-modal"
    >
      <div class="rv-approval-modal__head">
        <MqIconTile
          name="rule_validation"
          tone="brand"
          :size="48"
          :icon-size="26"
        />
        <div>
          <h2>{{ sheet ? '发布单' : '批准上线' }}</h2>
          <p class="rv-muted">
            <span class="mq-mono">{{ detail.rule.rule_id }}</span> {{ detail.rule.name }} · {{ detail.rule.source_document }}
          </p>
        </div>
      </div>

      <p class="rv-approval-modal__lead">
        批准后生成发布单。平台不会改变执行范围；由开发按发布单修改规则目录，随版本部署后该规则才进入默认质控。
      </p>

      <dl class="mq-soft rv-approval-modal__summary">
        <div>
          <dt>验收运行</dt>
          <dd>{{ runSummary }}</dd>
        </div>
        <div>
          <dt>执行版本</dt>
          <dd>
            <span :class="statusClass(isRelease ? 'success' : 'warning')">{{ buildLabel(run) }}</span>
            <span
              v-if="!isRelease"
              class="rv-muted"
            > 仅开发环境可批准，发布单将标注开发版本</span>
          </dd>
        </div>
        <div>
          <dt>测试病例</dt>
          <dd>{{ caseSummary }}</dd>
        </div>
        <div>
          <dt>覆盖</dt>
          <dd>{{ coverageSummary }}</dd>
        </div>
        <div>
          <dt>验收结论</dt>
          <dd>{{ conclusionSummary }}</dd>
        </div>
        <div>
          <dt>影响范围</dt>
          <dd>
            {{ detail.rule.impact?.label || '未声明' }}
            <span
              v-if="run && run.scope_rule_ids.length > 1"
              class="rv-muted"
            > · 同族回归 {{ run.regression_cases.length }} 例{{ run.regression_gaps.length ? `，${run.regression_gaps.length} 条同族无保护集` : '' }}</span>
          </dd>
        </div>
      </dl>

      <template v-if="sheet">
        <div class="mq-field">
          <span class="mq-field__label">发布单（交开发修改规则目录）</span>
          <pre class="mq-inset rv-approval-modal__sheet">{{ sheetText }}</pre>
        </div>
        <div class="rv-approval-modal__actions">
          <button
            type="button"
            class="mq-btn"
            @click="emit('close')"
          >
            关闭
          </button>
          <button
            type="button"
            class="mq-btn mq-btn--primary"
            @click="copySheet"
          >
            复制发布单
          </button>
        </div>
      </template>
      <template v-else>
        <div class="rv-approval-modal__rule">
          <b>发布单要求</b>
          <span>1. 修改 <span class="mq-mono">luxian_0609_rule_master_v1.json</span>：<span class="mq-mono">release_scope</span> 由 <span class="mq-mono">acceptance_only</span> 改为 <span class="mq-mono">default</span>，提交信息引用本发布单。</span>
          <span>2. 部署后用本次验收病例在发布构建上复验，结果须与本次一致。</span>
        </div>
        <label class="mq-field">
          <span class="mq-field__label">批准意见<span class="mq-field__required">*</span></span>
          <a-textarea
            v-model:value="note"
            aria-label="批准意见"
            :rows="3"
            :maxlength="4000"
            placeholder="批准范围与注意事项"
          />
        </label>
        <a-alert
          v-if="error"
          type="error"
          :message="error"
          show-icon
        />
        <div class="rv-approval-modal__actions">
          <button
            type="button"
            class="mq-btn"
            :disabled="busy || !note.trim()"
            @click="submit('rejected')"
          >
            驳回
          </button>
          <button
            type="button"
            class="mq-btn mq-btn--primary"
            data-testid="approve-rule"
            :disabled="busy || !note.trim()"
            @click="submit('approved')"
          >
            批准并生成发布单
          </button>
        </div>
      </template>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { approveRule } from '@/services/rule-validation-service'
import type { RuleDetail, ValidationEvent } from '@/services/rule-validation-service'
import { EXPECTED_STATUSES, STATUS, buildLabel, formatTime, statusClass } from './presentation'

const props = defineProps<{ open: boolean; detail: RuleDetail; approval: ValidationEvent | null }>()
const emit = defineEmits<{ close: []; done: [] }>()

const note = ref('')
const busy = ref(false)
const error = ref('')

const conclusion = computed(
  () => [...props.detail.events].reverse().find((e) => e.kind === 'conclusion') ?? null,
)
const run = computed(() => props.detail.runs.find((r) => r.id === conclusion.value?.run_id) ?? props.detail.runs[0] ?? null)
const isRelease = computed(() => run.value?.build_kind === 'release')
const sheet = computed(() =>
  props.approval?.decision === 'approved' ? (props.approval.payload as Record<string, unknown>) : null,
)
const runSummary = computed(() =>
  run.value ? `${formatTime(run.value.created_at)} · ${run.value.cases.length} 例 · 任务 ${run.value.job_id ?? '未绑定'}` : '—',
)
const caseSummary = computed(() => {
  const cases = run.value?.cases ?? []
  const real = cases.filter((c) => c.source_kind === 'real_copy').length
  const acceptance = cases.filter((c) => c.purpose === 'acceptance').length
  return `${cases.length} 例（真实副本 ${real}，独立验收集 ${acceptance}）`
})
const coverageSummary = computed(() =>
  EXPECTED_STATUSES.map((s) => {
    const n = props.detail.coverage.counts[s] ?? { synthetic: 0, real_copy: 0 }
    return `${STATUS[s].label} ${n.synthetic + n.real_copy}`
  }).join(' · '),
)
const conclusionSummary = computed(() =>
  conclusion.value
    ? `${conclusion.value.decision === 'accepted' ? '通过' : '不通过'} · ${conclusion.value.actor} · ${formatTime(conclusion.value.created_at)}`
    : '尚无结论',
)
const sheetText = computed(() => (sheet.value ? JSON.stringify(sheet.value, null, 2) : ''))

watch(
  () => props.open,
  () => {
    note.value = ''
    error.value = ''
  },
)

async function submit(decision: 'approved' | 'rejected') {
  busy.value = true
  error.value = ''
  try {
    const response = await approveRule(props.detail.rule.rule_id, decision, note.value.trim())
    if (!response.success) {
      error.value = response.error || '提交失败'
      return
    }
    note.value = ''
    message.success(decision === 'approved' ? '已批准，发布单已生成' : '已驳回')
    emit('done')
    if (decision === 'rejected') {
      emit('close')
    }
  } finally {
    busy.value = false
  }
}

async function copySheet() {
  try {
    await navigator.clipboard.writeText(sheetText.value)
    message.success('发布单已复制')
  } catch {
    message.warning('复制失败，请手动选择文本复制')
  }
}
</script>

<style scoped>
.rv-approval-modal {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.rv-approval-modal__head {
  display: flex;
  align-items: center;
  gap: 14px;
}

.rv-approval-modal__head h2 {
  margin: 0;
  font-size: var(--mq-font-20);
}

.rv-approval-modal__head p,
.rv-approval-modal__lead {
  margin: 0;
}

.rv-approval-modal__lead {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  line-height: 1.6;
}

.rv-muted {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.rv-approval-modal__summary {
  margin: 0;
  padding: 8px 18px;
}

.rv-approval-modal__summary div {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 12px;
  padding: 9px 0;
  border-top: 0.5px solid var(--mq-bg-muted);
  font-size: var(--mq-font-13);
}

.rv-approval-modal__summary div:first-child {
  border-top: 0;
}

.rv-approval-modal__summary dt {
  color: var(--mq-text-tertiary);
}

.rv-approval-modal__summary dd {
  margin: 0;
}

.rv-approval-modal__rule {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  line-height: 1.7;
}

.rv-approval-modal__rule b {
  color: var(--mq-text-primary);
}

.rv-approval-modal__sheet {
  max-height: 260px;
  margin: 0;
  padding: 12px 14px;
  overflow: auto;
  font-family: var(--mq-font-mono);
  font-size: var(--mq-font-12);
  white-space: pre-wrap;
}

.rv-approval-modal__actions {
  display: flex;
  gap: 12px;
}

.rv-approval-modal__actions > * {
  flex: 1 1 0;
}
</style>
