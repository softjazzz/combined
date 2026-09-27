<template>
  <section
    v-if="!forbidden"
    class="case-score"
    data-testid="case-score"
    aria-label="本病例得分"
  >
    <header class="case-score__header">
      <strong>病历得分</strong>
      <span
        v-if="scored"
        class="case-score__basis"
        data-testid="case-score-basis"
      >计分依据：{{ scored.standard_name || '未知标准' }}（满分 {{ formatNumber(scored.base_score) }}）</span>
    </header>

    <p
      v-if="loading"
      class="case-score__hint"
      role="status"
    >
      正在计算本病例得分…
    </p>
    <div
      v-else-if="loadError"
      class="case-score__error"
      role="alert"
      data-testid="case-score-error"
    >
      <span>{{ loadError }}</span>
      <button
        type="button"
        class="case-score__retry"
        data-testid="case-score-retry"
        @click="load"
      >
        重试
      </button>
    </div>
    <p
      v-else-if="result?.status === 'no_standard'"
      class="case-score__hint"
      data-testid="case-score-no-standard"
    >
      未配置评分标准：{{ sceneLabel }}尚未启用默认评分标准，暂不计分。
    </p>
    <p
      v-else-if="result?.status === 'no_result'"
      class="case-score__hint"
      data-testid="case-score-no-result"
    >
      暂无可计分的质控结果：本病历没有已完成（ready）的质控结果。
    </p>
    <template v-else-if="scored">
      <div class="case-score__summary">
        <span class="case-score__metric">
          <small>得分</small>
          <strong data-testid="case-score-value">{{ formatNumber(scored.score) }}</strong>
        </span>
        <span class="case-score__metric">
          <small>等级</small>
          <strong data-testid="case-score-grade">{{ scored.grade || '未知' }}</strong>
        </span>
        <span
          v-if="scored.veto_hit"
          class="case-score__veto"
          data-testid="case-score-veto"
        >命中单项否决，等级强制为 {{ scored.grade || '未知' }}</span>
      </div>

      <p
        v-if="!groupedDeductions.length"
        class="case-score__hint"
      >
        无扣分项
      </p>
      <ul
        v-else
        class="case-score__groups"
      >
        <li
          v-for="group in groupedDeductions"
          :key="group.group_name"
          class="case-score__group"
          data-testid="case-score-group"
        >
          <div class="case-score__group-heading">
            <strong>{{ group.group_name }}</strong>
            <span>扣 {{ formatNumber(group.applied_deduction) }} 分</span>
            <span
              v-if="group.capped"
              class="case-score__cap"
              data-testid="case-score-group-capped"
            >已封顶（原扣 {{ formatNumber(group.raw_deduction) }}，封顶 {{ formatNumber(group.max_deduction) }}）</span>
          </div>
          <ul class="case-score__items">
            <li
              v-for="item in group.items"
              :key="item.rule_id"
              data-testid="case-score-deduction"
            >
              <span class="case-score__rule">{{ item.rule_id }}</span>
              <span>-{{ formatNumber(item.deduction) }}</span>
              <span
                v-if="item.is_veto"
                class="case-score__veto-tag"
              >单项否决</span>
            </li>
          </ul>
        </li>
      </ul>

      <div
        v-if="scored.unscored_rule_ids.length"
        class="case-score__unscored"
        data-testid="case-score-unscored"
      >
        <span>以下确定问题未配置扣分：</span>
        <span
          v-for="ruleId in scored.unscored_rule_ids"
          :key="ruleId"
          class="case-score__rule"
        >{{ ruleId }}</span>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
/**
 * 结果抽屉内的本病例得分分区（只读）。计分唯一 owner 为后端计分服务，本组件只搬运：
 * 场景由调用方传入；no_standard / no_result 显示说明；403 整块隐藏；
 * 读取失败可重试，不伪造分数；三坐标或场景切换时丢弃迟到响应。
 */
import { computed, ref, watch } from 'vue'
import { getCaseScore } from '@/api/scoring'
import type { CaseScore, CaseScoreScored, ScoringDeduction, ScoringScene } from '@/api/scoring'

const props = defineProps<{
  instituteId: string
  patientId: string
  visitId: string
  scene: ScoringScene
}>()

const emit = defineEmits<{
  forbidden: []
}>()

const SCENE_LABELS: Record<ScoringScene, string> = {
  running: '运行病历',
  final: '终末病历',
  outpatient: '门急诊',
}

const loading = ref(false)
const forbidden = ref(false)
const loadError = ref('')
const result = ref<CaseScore | null>(null)
let requestSequence = 0

const sceneLabel = computed(() => SCENE_LABELS[props.scene] ?? '当前场景')
const scored = computed<CaseScoreScored | null>(() =>
  result.value?.status === 'scored' ? result.value : null,
)

interface GroupView {
  group_name: string
  raw_deduction: number
  applied_deduction: number
  max_deduction: number | null
  capped: boolean
  items: ScoringDeduction[]
}

/** 按服务端 group_deductions 的顺序分组展示扣分明细（组内顺序同服务端）。 */
const groupedDeductions = computed<GroupView[]>(() => {
  const data = scored.value
  if (!data) return []
  return data.group_deductions.map((group) => ({
    ...group,
    capped: group.max_deduction !== null && group.applied_deduction < group.raw_deduction,
    items: data.deductions.filter((item) => item.group_name === group.group_name),
  }))
})

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** 校验响应形状；scored 缺关键字段时视为不可用，不伪造分数。 */
function isCaseScore(data: unknown): data is CaseScore {
  if (!data || typeof data !== 'object') return false
  const value = data as Record<string, unknown>
  if (value.status === 'no_standard' || value.status === 'no_result') return true
  return (
    value.status === 'scored' &&
    isFiniteNumber(value.score) &&
    isFiniteNumber(value.base_score) &&
    typeof value.veto_hit === 'boolean' &&
    Array.isArray(value.deductions) &&
    Array.isArray(value.group_deductions) &&
    Array.isArray(value.unscored_rule_ids)
  )
}

function formatNumber(value: number | null | undefined): string {
  return isFiniteNumber(value) ? String(Number(value.toFixed(2))) : '未知'
}

async function load() {
  const sequence = ++requestSequence
  loading.value = true
  loadError.value = ''
  result.value = null
  try {
    const response = await getCaseScore({
      institute_id: props.instituteId,
      patient_id: props.patientId,
      visit_id: props.visitId,
      scene: props.scene,
    })
    if (sequence !== requestSequence) return
    if (response.status === 403) {
      forbidden.value = true
      emit('forbidden')
      return
    }
    if (!response.success) {
      loadError.value = response.message || '读取本病例得分失败'
      return
    }
    if (!isCaseScore(response.data)) {
      loadError.value = '得分数据不完整，已停止展示'
      return
    }
    result.value = response.data
  } catch {
    if (sequence === requestSequence) loadError.value = '读取本病例得分失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

watch(
  () => [props.instituteId, props.patientId, props.visitId, props.scene],
  () => {
    forbidden.value = false
    void load()
  },
  { immediate: true },
)
</script>

<style scoped>
.case-score {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: #fff;
}

.case-score__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  color: #1d1d1f;
  font-size: 14px;
}

.case-score__basis {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
}

.case-score__hint {
  margin: 4px 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
}

.case-score__error {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #cf1322;
  font-size: 13px;
}

.case-score__retry {
  padding: 2px 10px;
  border: 1px solid rgba(43, 108, 246, 0.3);
  border-radius: 6px;
  background: #f7fbff;
  color: #2b6cf6;
  cursor: pointer;
}

.case-score__summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 20px;
  margin-bottom: 8px;
}

.case-score__metric {
  display: grid;
  gap: 2px;
}

.case-score__metric small {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
}

.case-score__metric strong {
  color: #1d1d1f;
  font-size: 20px;
  font-variant-numeric: tabular-nums;
}

.case-score__veto,
.case-score__veto-tag {
  padding: 0 8px;
  border: 1px solid rgba(180, 35, 24, 0.24);
  border-radius: 6px;
  background: #fef3f2;
  color: #b42318;
  font-size: 12px;
  line-height: 20px;
}

.case-score__groups {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.case-score__group {
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
}

.case-score__group-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: #334155;
  font-size: 13px;
}

.case-score__cap {
  color: #b54708;
  font-size: 12px;
}

.case-score__items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
  color: #475569;
  font-size: 12px;
}

.case-score__items li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.case-score__rule {
  font-variant-numeric: tabular-nums;
  color: #1d1d1f;
}

.case-score__unscored {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  margin-top: 8px;
  color: #b54708;
  font-size: 12px;
}
</style>
