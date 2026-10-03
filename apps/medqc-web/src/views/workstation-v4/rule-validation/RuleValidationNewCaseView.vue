<template>
  <main
    class="mq-page rule-validation-page"
    data-testid="rule-validation-new-case"
  >
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">
          <router-link :to="{ name: 'WorkstationV4RuleValidation' }">规则验收</router-link> ·
          <router-link :to="detailRoute"><span class="mq-mono">{{ ruleId }}</span> {{ rule?.name }}</router-link> · 新建测试病例
        </span>
        <h1 class="mq-page-title">
          新建测试病例
        </h1>
      </div>
      <div class="mq-page-head__actions">
        <router-link
          class="mq-btn"
          :to="detailRoute"
        >
          取消
        </router-link>
        <button
          type="button"
          class="mq-btn mq-btn--primary"
          data-testid="save-case"
          :disabled="saving || loading"
          @click="save"
        >
          保存并关联本规则
        </button>
      </div>
    </header>

    <a-alert
      v-if="error"
      type="error"
      :message="error"
      show-icon
    />

    <section
      v-if="copySource"
      class="mq-inset nc-copy-banner"
      data-testid="copy-banner"
    >
      <div>
        <b>复制自：{{ copySource.case_title }}</b>
        <small class="rv-muted">已带入病例信息和全部文书；保存后生成新病例，原病例保持不变。仅可复制自建测试池中的病例。</small>
      </div>
      <button
        type="button"
        class="rv-link nc-text-btn"
        @click="resetToBlank"
      >
        改为空白新建
      </button>
    </section>

    <a-spin :spinning="loading">
      <div class="nc-layout">
        <div class="nc-main">
          <section class="mq-card mq-card--padded rv-section">
            <div>
              <div class="rv-section__title">
                <span class="rv-step__no is-current">1</span>
                <h2 class="mq-card__title">
                  病例信息
                </h2>
              </div>
              <p class="mq-card__desc">
                只写合成内容，不填真实患者身份信息。评价时间点决定未出院病例时限规则的评价终点，创建后固定。
              </p>
            </div>
            <div class="nc-grid">
              <label class="mq-field nc-span-2">
                <span class="mq-field__label">病例标题<span class="mq-field__required">*</span></span>
                <a-input
                  v-model:value="draft.title"
                  aria-label="病例标题"
                  :maxlength="80"
                  placeholder="例如：抢救记录缺参加人员职称"
                  :addon-before="CASE_TITLE_PREFIX"
                />
              </label>
              <label class="mq-field">
                <span class="mq-field__label">科室<span class="mq-field__required">*</span></span>
                <a-input
                  v-model:value="draft.department"
                  aria-label="科室"
                  :maxlength="40"
                />
              </label>
              <label class="mq-field">
                <span class="mq-field__label">主要诊断</span>
                <a-input
                  v-model:value="draft.mainDiagnosis"
                  aria-label="主要诊断"
                  :maxlength="80"
                />
              </label>
              <label class="mq-field">
                <span class="mq-field__label">入院时间<span class="mq-field__required">*</span></span>
                <input
                  v-model="draft.admissionTime"
                  class="mq-input"
                  type="datetime-local"
                  aria-label="入院时间"
                >
              </label>
              <label class="mq-field">
                <span class="mq-field__label">出院时间</span>
                <input
                  v-model="draft.dischargeTime"
                  class="mq-input"
                  type="datetime-local"
                  aria-label="出院时间"
                >
              </label>
              <label class="mq-field">
                <span class="mq-field__label">评价时间点<span class="mq-field__required">*</span></span>
                <input
                  v-model="draft.evaluationDate"
                  class="mq-input"
                  type="date"
                  aria-label="评价时间点"
                >
              </label>
              <div class="mq-field">
                <span class="mq-field__label">病历场景</span>
                <div class="mq-soft nc-scene">
                  {{ draft.dischargeTime ? '终末病历（以出院时间为评价终点）' : '运行病历（未填出院时间）' }}
                </div>
              </div>
            </div>
          </section>

          <section class="mq-card mq-card--padded rv-section">
            <div>
              <div class="rv-section__title">
                <span class="rv-step__no is-current">2</span>
                <h2 class="mq-card__title">
                  病历文书
                </h2>
                <span class="rv-tag">{{ draft.documents.length }} 份</span>
              </div>
              <p class="mq-card__desc">
                按规则需要自由添加文书，不依赖模板。{{ relatedHint }}
              </p>
            </div>
            <div
              class="nc-chips"
              role="group"
              aria-label="添加文书"
            >
              <span class="rv-muted">添加文书</span>
              <button
                v-for="type in suggestedTypes"
                :key="type"
                type="button"
                class="nc-chip"
                @click="addDocument(type)"
              >
                + {{ typeLabel(type) }}
              </button>
              <a-select
                v-model:value="otherType"
                class="nc-other"
                aria-label="其他文书类型"
                placeholder="+ 其他类型…"
                :options="otherTypeOptions"
                @change="addOtherDocument"
              />
            </div>

            <div
              v-for="(doc, index) in draft.documents"
              :key="doc.key"
              class="mq-inset nc-doc"
              data-testid="draft-document"
            >
              <div class="nc-doc__head">
                <span :class="['rv-tag', isRuleRelated(doc.type, ruleFamily) ? 'rv-tag--blue' : '']">
                  {{ isRuleRelated(doc.type, ruleFamily) ? '本规则相关' : '其他文书' }}
                </span>
                <label class="mq-field">
                  <span class="mq-field__label">文书类型</span>
                  <a-select
                    v-model:value="doc.type"
                    :aria-label="`文书${index + 1}类型`"
                    :options="typeOptions"
                  />
                </label>
                <label class="mq-field">
                  <span class="mq-field__label">记录时间</span>
                  <input
                    v-model="doc.time"
                    class="mq-input"
                    type="datetime-local"
                    :aria-label="`文书${index + 1}记录时间`"
                  >
                </label>
                <label class="mq-field">
                  <span class="mq-field__label">文书标题</span>
                  <a-input
                    v-model:value="doc.title"
                    :aria-label="`文书${index + 1}标题`"
                    :maxlength="60"
                  />
                </label>
                <button
                  type="button"
                  class="mq-btn nc-remove"
                  :aria-label="`删除文书${index + 1}`"
                  @click="draft.documents.splice(index, 1)"
                >
                  ×
                </button>
              </div>
              <label class="mq-field">
                <span class="mq-field__label">正文</span>
                <a-textarea
                  v-model:value="doc.content"
                  :aria-label="`文书${index + 1}正文`"
                  :auto-size="{ minRows: 3, maxRows: 14 }"
                  :maxlength="20000"
                  placeholder="填写合成病历正文"
                />
              </label>
              <small class="rv-muted">正文 {{ doc.content.trim().length }} 字 · 合成内容</small>
            </div>
            <p
              v-if="!draft.documents.length"
              class="rv-empty"
            >
              还没有文书，请从上方添加。
            </p>
          </section>
        </div>

        <aside class="nc-side">
          <section class="mq-card mq-card--padded rv-section">
            <div>
              <div class="rv-section__title">
                <span class="rv-step__no is-current">3</span>
                <h2 class="mq-card__title">
                  本规则人工预期
                </h2>
              </div>
              <p class="mq-card__desc">
                <span class="mq-mono">{{ ruleId }}</span> {{ rule?.name }}
              </p>
            </div>
            <div class="mq-field">
              <span class="mq-field__label">预期状态<span class="mq-field__required">*</span></span>
              <div
                class="mq-segmented nc-status"
                role="radiogroup"
                aria-label="预期状态"
              >
                <button
                  v-for="status in expectedStatuses(ruleId)"
                  :key="status"
                  type="button"
                  role="radio"
                  class="mq-segmented__item"
                  :class="{ 'is-active': draft.expectedStatus === status }"
                  :aria-checked="draft.expectedStatus === status"
                  @click="draft.expectedStatus = status"
                >
                  {{ STATUS[status].label }}
                </button>
              </div>
            </div>
            <div class="mq-field">
              <span class="mq-field__label">病例用途</span>
              <a-radio-group
                v-model:value="draft.purpose"
                aria-label="病例用途"
              >
                <a-radio value="development">
                  开发集
                </a-radio>
                <a-radio value="acceptance">
                  独立验收集
                </a-radio>
              </a-radio-group>
            </div>
            <label class="mq-field">
              <span class="mq-field__label">人工预期依据<span class="mq-field__required">*</span></span>
              <a-textarea
                v-model:value="draft.reason"
                aria-label="人工预期依据"
                :rows="4"
                :maxlength="4000"
                placeholder="写明判定所依据的原文事实"
              />
            </label>
            <div class="mq-soft nc-note">
              人工预期只用于运行后比较，不进入质控任务；保存后在规则详情页可继续修改（产生新修订）。
            </div>
          </section>
          <section class="mq-soft nc-after">
            <b>保存后</b>
            <ol>
              <li>病例写入客户自建测试池，内容与评价时间点固定。</li>
              <li>为本规则保存预期（修订 r1）。</li>
              <li>回到规则详情，病例出现在“测试病例与预期”，可直接运行。</li>
            </ol>
          </section>
        </aside>
      </div>
    </a-spin>

    <a-modal
      :open="leaveOpen"
      :footer="null"
      :width="420"
      centered
      wrap-class-name="mq-modal"
      @cancel="leaveOpen = false"
    >
      <div
        class="nc-leave"
        data-testid="leave-confirm"
      >
        <h2>放弃未保存的内容？</h2>
        <p class="rv-muted">
          当前填写的病例信息、文书和预期尚未保存，离开后将丢失。
        </p>
        <div class="rv-actions">
          <button
            type="button"
            class="mq-btn"
            @click="leaveOpen = false"
          >
            继续编辑
          </button>
          <button
            type="button"
            class="mq-btn mq-btn--primary"
            @click="confirmLeave"
          >
            放弃并离开
          </button>
        </div>
      </div>
    </a-modal>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import { message } from 'ant-design-vue'
import { getValidationRule, saveCaseAnswer } from '@/services/rule-validation-service'
import type { RuleInfo, ValidationCase } from '@/services/rule-validation-service'
import { createManualTestMedicalRecord, getEditableMedicalRecordDocuments } from '@/services/manual-case-sample-service'
import { testRecordDocumentTypeOptions } from '@/views/workstation-v4/customer-sample-validation/syntheticCaseBuilder'
import { expectedStatuses, STATUS } from './presentation'
import {
  CASE_TITLE_PREFIX,
  blankDocument,
  buildCreatePayload,
  copyDocuments,
  emptyDraft,
  isRuleRelated,
  stripPrefix,
  suggestedDocumentTypes,
  toInputDateTime,
  typeLabel,
  validateDraft,
} from './caseDraft'
import type { CaseDraft } from './caseDraft'

const route = useRoute()
const router = useRouter()
const ruleId = computed(() => String(route.params.ruleId || ''))
const copyFromId = computed(() => (typeof route.query.copyFrom === 'string' ? route.query.copyFrom : ''))
const detailRoute = computed(() => ({ name: 'WorkstationV4RuleValidationDetail', params: { ruleId: ruleId.value } }))

const rule = ref<RuleInfo | null>(null)
const copySource = ref<ValidationCase | null>(null)
const draft = reactive<CaseDraft>(emptyDraft())
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const otherType = ref<string>()
// 未保存离开保护：加载完成时记快照，内容变化后离开需确认
const baseline = ref('')
const saved = ref(false)
const leaveOpen = ref(false)
let pendingLeave: RouteLocationRaw | null = null
let leaving = false
const dirty = computed(() => Boolean(baseline.value) && !saved.value && JSON.stringify(draft) !== baseline.value)
function markClean() {
  baseline.value = JSON.stringify(draft)
}

const ruleFamily = computed(() => rule.value?.source_document ?? '')
const suggestedTypes = computed(() => suggestedDocumentTypes(ruleFamily.value))
const typeOptions = testRecordDocumentTypeOptions.map((o) => ({ value: o.value, label: o.label }))
const otherTypeOptions = computed(() => typeOptions.filter((o) => !suggestedTypes.value.includes(o.value)))
const relatedHint = computed(() => {
  const related = suggestedTypes.value.filter((t) => isRuleRelated(t, ruleFamily.value)).map(typeLabel)
  return related.length ? `本规则相关文书：${related.join('、')}。` : ''
})

function defaultDocumentTime() {
  return draft.documents.at(-1)?.time || draft.admissionTime
}
function addDocument(type: string) {
  draft.documents.push(blankDocument(type, defaultDocumentTime()))
}
function addOtherDocument(value: unknown) {
  if (typeof value === 'string' && value) addDocument(value)
  otherType.value = undefined
}

function resetToBlank() {
  // 去掉 copyFrom 会触发重新加载：表单与离开保护快照一并重置
  copySource.value = null
  void router.replace({ query: {} })
}

function confirmLeave() {
  leaveOpen.value = false
  leaving = true
  if (pendingLeave) void router.push(pendingLeave)
}

onBeforeRouteLeave((to) => {
  if (leaving || !dirty.value) return true
  pendingLeave = to.fullPath
  leaveOpen.value = true
  return false
})

function warnUnload(event: BeforeUnloadEvent) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}
onMounted(() => window.addEventListener('beforeunload', warnUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', warnUnload))

async function load() {
  loading.value = true
  error.value = ''
  const response = await getValidationRule(ruleId.value)
  if (!response.success) {
    loading.value = false
    error.value = response.error || '规则加载失败'
    return
  }
  rule.value = response.data.rule
  Object.assign(draft, emptyDraft())
  if (!copyFromId.value) {
    addDocument(suggestedTypes.value[0] ?? 'daily_course_record')
    markClean()
    loading.value = false
    return
  }
  // 只允许复制已关联本规则的自建测试病例（列表来自规则验收接口，均在测试池内）
  const source = response.data.cases.find((c) => c.item_id === copyFromId.value) ?? null
  if (!source) {
    loading.value = false
    error.value = '复制来源不是本规则已关联的测试病例，已改为空白新建'
    addDocument(suggestedTypes.value[0] ?? 'daily_course_record')
    markClean()
    return
  }
  // source_view=current 才返回登记入院时间（current_record），复制时用来还原入院时间
  const docs = await getEditableMedicalRecordDocuments(source.record_ref.visit_id, {
    ...source.record_ref,
    source_view: 'current',
  })
  loading.value = false
  if (!docs.success || !docs.data) {
    error.value = docs.message || '读取源病例文书失败'
    return
  }
  copySource.value = source
  Object.assign(draft, {
    title: `${stripPrefix(source.case_title)}（副本）`,
    department: source.department ?? '',
    admissionTime: toInputDateTime(docs.data.current_record?.admission_time) || draft.admissionTime,
    evaluationDate: source.evaluation_as_of_date || draft.evaluationDate,
    documents: copyDocuments(docs.data.documents),
    expectedStatus: source.expected_status,
    purpose: source.purpose,
    reason: '',
  })
  markClean()
}

async function save() {
  const problem = validateDraft(draft)
  if (problem) {
    error.value = problem
    return
  }
  saving.value = true
  error.value = ''
  const created = await createManualTestMedicalRecord(
    buildCreatePayload(draft, ruleId.value, copySource.value ? { itemId: copySource.value.item_id } : undefined),
  )
  const itemId = created.success ? created.data?.item?.id : undefined
  if (!itemId) {
    saving.value = false
    error.value = created.success ? '病例已提交但未返回病例编号，请到规则详情用“关联已有病例”核对' : created.message || '创建测试病例失败'
    return
  }
  const answered = await saveCaseAnswer(ruleId.value, itemId, {
    revision: 0,
    expected_status: draft.expectedStatus,
    human_reason: draft.reason.trim(),
    purpose: draft.purpose,
  })
  saving.value = false
  if (!answered.success) {
    error.value = `病例已创建，但保存预期失败：${answered.error || '未知错误'}。请在规则详情用“关联已有病例”补标预期。`
    return
  }
  saved.value = true
  message.success('测试病例已创建并关联本规则')
  await router.push(detailRoute.value)
}

watch([ruleId, copyFromId], () => void load(), { immediate: true })
</script>

<style scoped src="./styles/rule-validation.css"></style>
<style scoped>
.nc-copy-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  border-color: var(--mq-info-border);
  background: var(--mq-info-bg);
}

.nc-copy-banner div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: var(--mq-font-13);
}

.nc-text-btn {
  border: 0;
  background: transparent;
  font: inherit;
  font-size: var(--mq-font-13);
  cursor: pointer;
}

.nc-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  align-items: start;
  gap: 20px;
}

.nc-main,
.nc-side {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.nc-side {
  position: sticky;
  top: 16px;
}

.nc-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.nc-span-2 {
  grid-column: span 2;
}

.nc-scene {
  display: flex;
  align-items: center;
  min-height: 36px;
  padding: 0 12px;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
}

.nc-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.nc-chip {
  height: 30px;
  padding: 0 12px;
  border: 1px dashed var(--mq-info-border);
  border-radius: var(--mq-radius-tag);
  background: var(--mq-info-bg);
  color: var(--mq-info-text);
  font: inherit;
  font-size: var(--mq-font-12);
  cursor: pointer;
}

.nc-other {
  width: 150px;
}

.nc-doc {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px;
}

.nc-doc__head {
  display: grid;
  grid-template-columns: auto 170px 210px minmax(0, 1fr) auto;
  align-items: end;
  gap: 10px;
}

.nc-doc__head > .rv-tag {
  align-self: center;
}

.nc-remove {
  width: 32px;
  padding: 0;
  font-size: 16px;
}

.nc-status {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.nc-note {
  padding: 12px 14px;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
  line-height: 1.7;
}

.nc-leave {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.nc-leave h2 {
  margin: 0;
  font-size: var(--mq-font-20);
}

.nc-leave p {
  margin: 0;
}

.nc-after {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 20px;
  font-size: var(--mq-font-13);
}

.nc-after ol {
  margin: 0;
  padding-left: 18px;
  color: var(--mq-text-secondary);
  line-height: 1.8;
}

@media (max-width: 1180px) {
  .nc-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .nc-side {
    position: static;
  }

  .nc-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .nc-doc__head {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
