<template>
  <main class="synthetic-case-page">
    <header class="synthetic-case-header">
      <div class="synthetic-case-header-copy">
        <button
          class="synthetic-case-back"
          type="button"
          @click="goBack"
        >
          <ArrowLeft :size="16" />
          返回样本验证
        </button>
        <div class="synthetic-case-eyebrow">
          客户样本验证 / 测试病历构建
        </div>
        <h1>创建测试病历</h1>
        <p>通过模板或复制粘贴创建客户自建测试病历，保存到独立样本池后验证泸县0609质控点。</p>
        <div class="synthetic-case-summary">
          <span>模板 {{ syntheticCaseTemplates.length }} 个</span>
          <span>文书 {{ enabledDocumentCount }} 份</span>
          <span>预期 {{ form.goldenAnswers.length }} 条</span>
          <span>独立样本池</span>
        </div>
      </div>
      <div class="synthetic-case-header-actions">
        <a-button
          class="synthetic-case-ghost-button"
          @click="showPreview = true"
        >
          <template #icon>
            <Eye :size="15" />
          </template>
          预览病历包
        </a-button>
        <a-button
          type="primary"
          class="synthetic-case-primary-button"
          :loading="saving"
          @click="handleSave(false)"
        >
          保存到测试样本池
        </a-button>
        <a-button
          type="primary"
          class="synthetic-case-primary-button is-strong"
          :loading="savingAndRunning"
          @click="handleSave(true)"
        >
          保存并立即验证
        </a-button>
      </div>
    </header>

    <section class="synthetic-case-shell">
      <aside class="synthetic-case-sidebar">
        <div class="synthetic-case-step-card">
          <span>01</span>
          <strong>选择模板</strong>
          <p>从典型质控场景起步，也可完全手工编辑。</p>
        </div>
        <div class="synthetic-case-step-card">
          <span>02</span>
          <strong>编辑文书</strong>
          <p>修改记录时间、提交时间和正文内容。</p>
        </div>
        <div class="synthetic-case-step-card">
          <span>03</span>
          <strong>绑定预期</strong>
          <p>定义 golden answer 用于后续效果评估。</p>
        </div>

        <div class="synthetic-case-panel-title">
          <Layers :size="16" />
          模板库
        </div>
        <div class="synthetic-case-template-list">
          <button
            v-for="template in syntheticCaseTemplates"
            :key="template.key"
            class="synthetic-case-template"
            :class="{ 'is-active': form.templateKey === template.key }"
            type="button"
            @click="applyTemplate(template.key)"
          >
            <strong>{{ template.name }}</strong>
            <span>{{ template.family }}</span>
            <small>{{ template.description }}</small>
          </button>
        </div>

        <div class="synthetic-case-panel-title synthetic-case-doc-title">
          <FileText :size="16" />
          文书目录
        </div>
        <div class="synthetic-case-doc-nav">
          <button
            v-for="(document, index) in form.documents"
            :key="document.key"
            type="button"
            @click="scrollToDocument(document.key)"
          >
            <span>{{ String(index + 1).padStart(2, '0') }}</span>
            <div>
              <strong>{{ document.title || documentTypeLabel(document.document_type) }}</strong>
              <small>{{ documentTypeLabel(document.document_type) }}</small>
            </div>
          </button>
        </div>
      </aside>

      <div class="synthetic-case-editor">
        <section class="synthetic-case-card">
          <div class="synthetic-case-section-head">
            <div>
              <h2>基本信息</h2>
              <p>这些字段会写入测试病历主索引和样本池列表。</p>
            </div>
            <span class="synthetic-case-section-chip">
              {{ currentTemplate?.name || '手工创建' }}
            </span>
          </div>
          <div class="synthetic-case-form-grid">
            <label>
              <span>测试病历名称</span>
              <a-input
                v-model:value="form.caseTitle"
                placeholder="例如：术后记录超时测试"
              />
            </label>
            <label>
              <span>患者姓名</span>
              <a-input
                v-model:value="form.patientName"
                placeholder="脱敏姓名"
              />
            </label>
            <label>
              <span>性别</span>
              <a-select
                v-model:value="form.sex"
                :options="sexOptions"
              />
            </label>
            <label>
              <span>年龄</span>
              <a-input-number
                v-model:value="form.age"
                class="w-full"
                :min="0"
                :max="120"
              />
            </label>
            <label>
              <span>住院号</span>
              <a-input
                v-model:value="form.mrNo"
                placeholder="可选，留空自动生成"
              />
            </label>
            <label>
              <span>科室</span>
              <a-input
                v-model:value="form.department"
                placeholder="例如：普通外科"
              />
            </label>
            <label>
              <span>入院时间</span>
              <a-input
                v-model:value="form.admissionTime"
                type="datetime-local"
              />
            </label>
            <label>
              <span>出院时间</span>
              <a-input
                v-model:value="form.dischargeTime"
                type="datetime-local"
              />
            </label>
            <label class="is-wide">
              <span>主要诊断</span>
              <a-input
                v-model:value="form.mainDiagnosis"
                placeholder="可选，用于质控上下文"
              />
            </label>
            <label class="is-wide">
              <span>其他诊断</span>
              <a-textarea
                v-model:value="form.otherDiagnosesText"
                :rows="2"
                placeholder="每行一个诊断"
              />
            </label>
          </div>
        </section>

        <section class="synthetic-case-card">
          <div class="synthetic-case-section-head">
            <div>
              <h2>病历文书</h2>
              <p>逐份文书设置记录时间、提交时间和正文，长文本在这里完整编辑。</p>
            </div>
            <div class="synthetic-case-inline-actions">
              <a-select
                v-model:value="newDocumentType"
                class="synthetic-case-doc-select"
                :options="testRecordDocumentTypeOptions"
              />
              <a-button @click="addDocument">
                添加文书
              </a-button>
            </div>
          </div>

          <div class="synthetic-case-doc-list">
            <article
              v-for="(document, index) in form.documents"
              :id="`synthetic-doc-${document.key}`"
              :key="document.key"
              class="synthetic-case-doc"
            >
              <div class="synthetic-case-doc-head">
                <div>
                  <span>文书 {{ index + 1 }}</span>
                  <strong>{{ document.title || documentTypeLabel(document.document_type) }}</strong>
                </div>
                <div class="synthetic-case-inline-actions">
                  <span
                    class="synthetic-case-doc-status"
                    :class="{ 'is-disabled': !document.enabled }"
                  >
                    {{ document.enabled ? '已纳入' : '已停用' }}
                  </span>
                  <a-switch
                    v-model:checked="document.enabled"
                    size="small"
                  />
                  <a-button
                    size="small"
                    danger
                    :disabled="form.documents.length <= 1"
                    @click="removeDocument(index)"
                  >
                    删除
                  </a-button>
                </div>
              </div>
              <div class="synthetic-case-doc-grid">
                <label>
                  <span>文书类型</span>
                  <a-select
                    v-model:value="document.document_type"
                    :options="testRecordDocumentTypeOptions"
                    @change="syncDocumentTitle(document)"
                  />
                </label>
                <label>
                  <span>标题</span>
                  <a-input v-model:value="document.title" />
                </label>
                <label>
                  <span>记录/报告时间</span>
                  <a-input
                    v-model:value="document.record_time"
                    type="datetime-local"
                  />
                </label>
                <label>
                  <span>提交时间</span>
                  <a-input
                    v-model:value="document.submit_time"
                    type="datetime-local"
                  />
                </label>
                <label>
                  <span>记录医师</span>
                  <a-input
                    v-model:value="document.doctor_name"
                    placeholder="可选"
                  />
                </label>
              </div>
              <a-textarea
                v-model:value="document.content"
                :rows="10"
                placeholder="粘贴或编辑这份文书的完整文本。缺陷应由真实文书内容自然体现，不要写“备注：这里缺失”。"
              />
            </article>
          </div>
        </section>
      </div>

      <aside class="synthetic-case-right">
        <section class="synthetic-case-card synthetic-case-sticky-card">
          <div class="synthetic-case-section-head">
            <div>
              <h2>预期结果</h2>
              <p>用于后续评估系统结论是否符合人工预期。</p>
            </div>
            <span class="synthetic-case-section-chip">Golden</span>
            <a-button
              size="small"
              @click="addGoldenAnswer"
            >
              新增
            </a-button>
          </div>

          <div class="synthetic-case-golden-list">
            <article
              v-for="(answer, index) in form.goldenAnswers"
              :key="answer.id || index"
              class="synthetic-case-golden"
            >
              <div class="synthetic-case-golden-head">
                <strong>预期 {{ index + 1 }}</strong>
                <a-button
                  size="small"
                  danger
                  @click="removeGoldenAnswer(index)"
                >
                  删除
                </a-button>
              </div>
              <label>
                <span>质控点 ID</span>
                <a-input
                  v-model:value="answer.qc_point_id"
                  placeholder="LX0609-001"
                />
              </label>
              <label>
                <span>期望状态</span>
                <a-select
                  v-model:value="answer.expected_status"
                  :options="expectedStatusOptions"
                />
              </label>
              <label>
                <span>触发事实</span>
                <a-textarea
                  :value="answer.trigger_facts.join('\n')"
                  :rows="3"
                  placeholder="每行一个触发事实"
                  @change="answer.trigger_facts = splitLines($event.target.value)"
                />
              </label>
              <label>
                <span>证据关键词</span>
                <a-textarea
                  :value="answer.evidence_keywords.join('\n')"
                  :rows="3"
                  placeholder="每行一个证据关键词"
                  @change="answer.evidence_keywords = splitLines($event.target.value)"
                />
              </label>
              <label>
                <span>人工判定理由</span>
                <a-textarea
                  v-model:value="answer.human_reason"
                  :rows="3"
                />
              </label>
            </article>
            <a-empty
              v-if="form.goldenAnswers.length === 0"
              description="暂未设置预期结果"
            />
          </div>
        </section>
      </aside>
    </section>

    <a-modal
      v-model:open="showPreview"
      width="88vw"
      title="病历包预览"
      :footer="null"
      wrap-class-name="synthetic-case-preview-modal"
    >
      <div class="synthetic-case-preview">
        <aside>
          <strong>{{ form.caseTitle || '未命名测试病历' }}</strong>
          <span>{{ form.patientName }} · {{ form.department }}</span>
          <span>文书 {{ enabledDocumentCount }} 份</span>
          <span>预期 {{ form.goldenAnswers.length }} 条</span>
        </aside>
        <pre>{{ previewText }}</pre>
      </div>
    </a-modal>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeft, Eye, FileText, Layers } from 'lucide-vue-next'
import {
  createManualTestMedicalRecord,
  runManualSamplePool,
} from '@/services/manual-case-sample-service'
import type { SyntheticCaseTemplate } from './syntheticCaseTemplates'
import { syntheticCaseTemplates } from './syntheticCaseTemplates'
import type { TestRecordDocumentForm } from './types'
import {
  createDefaultSyntheticCaseForm,
  createGoldenAnswer,
  createSyntheticDocument,
  documentTypeLabel,
  expectedStatusOptions,
  findForbiddenSelfHints,
  normalizeSyntheticCasePayload,
  sexOptions,
  splitLines,
  testRecordDocumentTypeOptions,
} from './syntheticCaseBuilder'

const LUXIAN_0609_RULE_SET_KEY = 'luxian_0609_qc_v1'

const router = useRouter()
const form = ref(createDefaultSyntheticCaseForm())
const newDocumentType = ref('daily_course_record')
const saving = ref(false)
const savingAndRunning = ref(false)
const showPreview = ref(false)

const enabledDocumentCount = computed(
  () =>
    form.value.documents.filter((document) => document.enabled && document.content.trim()).length,
)
const currentTemplate = computed(() =>
  syntheticCaseTemplates.find((template) => template.key === form.value.templateKey),
)

const previewText = computed(() => {
  const lines = [
    `测试病历：${form.value.caseTitle}`,
    `患者：${form.value.patientName} ${form.value.sex} ${form.value.age}岁`,
    `科室：${form.value.department}`,
    `入院时间：${form.value.admissionTime}`,
    form.value.mainDiagnosis ? `主要诊断：${form.value.mainDiagnosis}` : '',
    '',
  ].filter(Boolean)
  form.value.documents
    .filter((document) => document.enabled)
    .forEach((document, index) => {
      lines.push(`【${index + 1}. ${document.title || documentTypeLabel(document.document_type)}】`)
      lines.push(`文书类型：${documentTypeLabel(document.document_type)}`)
      lines.push(`记录时间：${document.record_time || '-'}`)
      lines.push(`提交时间：${document.submit_time || '-'}`)
      lines.push(document.content || '')
      lines.push('')
    })
  return lines.join('\n')
})

function goBack() {
  router.push({ name: 'WorkstationV4CustomerSampleValidation' })
}

function applyTemplate(key: string) {
  const template = syntheticCaseTemplates.find((item) => item.key === key)
  if (!template) return
  form.value = {
    ...createDefaultSyntheticCaseForm(),
    caseTitle: template.basic.caseTitle,
    patientName: template.basic.patientName,
    sex: template.basic.sex,
    age: template.basic.age,
    department: template.basic.department,
    admissionTime: '2026-06-01T08:00',
    dischargeTime: '2026-06-06T10:00',
    mainDiagnosis: template.basic.mainDiagnosis || '',
    otherDiagnosesText: template.basic.otherDiagnosesText || '',
    manualIssueText: `${template.name}：${template.description}`,
    templateKey: template.key,
    selectedRuleIds: [...template.suggestedRuleIds],
    goldenAnswers: template.goldenAnswers.map((answer) => ({
      ...answer,
      id: answer.id || `${template.key}-${answer.qc_point_id}`,
      trigger_facts: [...answer.trigger_facts],
      evidence_keywords: [...answer.evidence_keywords],
    })),
    documents: template.documents.map((document) => ({
      ...document,
      key: createSyntheticDocument(document.document_type).key,
    })),
  }
}

function scrollToDocument(key: string) {
  document.getElementById(`synthetic-doc-${key}`)?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

function addDocument() {
  form.value.documents.push(createSyntheticDocument(newDocumentType.value))
}

function removeDocument(index: number) {
  if (form.value.documents.length <= 1) return
  form.value.documents.splice(index, 1)
}

function syncDocumentTitle(document: TestRecordDocumentForm) {
  if (!String(document.title || '').trim()) {
    document.title = documentTypeLabel(document.document_type)
  }
}

function addGoldenAnswer() {
  form.value.goldenAnswers.push(createGoldenAnswer())
}

function removeGoldenAnswer(index: number) {
  form.value.goldenAnswers.splice(index, 1)
}

function validateForm(): boolean {
  if (!form.value.caseTitle.trim()) {
    message.warning('请填写测试病历名称')
    return false
  }
  if (!form.value.patientName.trim()) {
    message.warning('请填写患者姓名')
    return false
  }
  if (!form.value.department.trim()) {
    message.warning('请填写科室')
    return false
  }
  if (!form.value.admissionTime) {
    message.warning('请填写入院时间')
    return false
  }
  if (enabledDocumentCount.value === 0) {
    message.warning('至少需要填写一份病历文书')
    return false
  }
  const forbiddenDocuments = findForbiddenSelfHints(form.value)
  if (forbiddenDocuments.length) {
    message.warning(`请移除文书中的自我提示文本：${forbiddenDocuments.join('、')}`)
    return false
  }
  const invalidGolden = form.value.goldenAnswers.find(
    (answer) =>
      answer.expected_status === 'non_compliant' &&
      (!answer.trigger_facts.length || !answer.evidence_keywords.length),
  )
  if (invalidGolden) {
    message.warning(`${invalidGolden.qc_point_id || '未命名质控点'} 缺少触发事实或证据关键词`)
    return false
  }
  return true
}

async function handleSave(runAfterSave: boolean) {
  if (!validateForm()) return
  if (runAfterSave) {
    savingAndRunning.value = true
  } else {
    saving.value = true
  }
  try {
    const payload = normalizeSyntheticCasePayload(form.value)
    const result = await createManualTestMedicalRecord(payload)
    if (!result.success || !result.data) {
      message.error(result.message || '创建测试病历失败')
      return
    }
    const poolId = result.data.pool?.id
    const visitId = result.data.visit_id
    if (runAfterSave && poolId && visitId) {
      const runResult = await runManualSamplePool(
        poolId,
        {
          rule_set_key: LUXIAN_0609_RULE_SET_KEY,
          validation_mode: 'customer',
          record_ids: [visitId],
          max_parallel_records: 1,
        },
        { timeout: 90000 },
      )
      if (!runResult.success || !runResult.data) {
        message.warning(result.message || '测试病历已保存，但验证任务创建失败')
      } else {
        message.success('测试病历已保存，验证任务已创建')
      }
    } else {
      message.success(`测试病历已创建：${result.data.mr_no || visitId}`)
    }
    await router.push({
      name: 'WorkstationV4CustomerSampleValidation',
      query: poolId ? { poolId } : undefined,
    })
  } finally {
    saving.value = false
    savingAndRunning.value = false
  }
}
</script>

<style scoped>
.synthetic-case-page {
  min-height: 100%;
  padding: 20px 24px 28px;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.synthetic-case-header,
.synthetic-case-shell,
.synthetic-case-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.04),
    0 10px 28px rgba(0, 0, 0, 0.055);
}

.synthetic-case-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin: 0 auto 14px;
  max-width: 1600px;
  border-radius: 18px;
  padding: 16px 18px;
}

.synthetic-case-header-copy {
  min-width: 0;
}

.synthetic-case-header h1 {
  margin: 2px 0 5px;
  font-size: 27px;
  font-weight: 700;
  line-height: 31px;
  letter-spacing: 0;
}

.synthetic-case-header p {
  margin: 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
}

.synthetic-case-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: #0066cc;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  padding: 0;
}

.synthetic-case-eyebrow {
  margin-top: 10px;
  color: #0066cc;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.synthetic-case-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.synthetic-case-summary span,
.synthetic-case-section-chip,
.synthetic-case-doc-status {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  padding: 3px 10px;
  color: rgba(29, 29, 31, 0.64);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.synthetic-case-section-chip {
  border-color: rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.07);
  color: #0066cc;
}

.synthetic-case-header-actions,
.synthetic-case-inline-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.synthetic-case-header-actions {
  flex: 0 0 auto;
  justify-content: flex-end;
}

.synthetic-case-ghost-button,
.synthetic-case-primary-button {
  display: inline-flex !important;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px !important;
  border-radius: 9px !important;
  font-size: 13px;
  font-weight: 600;
  line-height: 34px;
  white-space: nowrap;
}

.synthetic-case-ghost-button {
  min-width: 112px;
  border-color: rgba(0, 0, 0, 0.1);
  background: rgba(255, 255, 255, 0.72);
  color: rgba(29, 29, 31, 0.78);
}

.synthetic-case-primary-button {
  min-width: 128px;
  background: #0066cc;
  border-color: #0066cc;
  box-shadow: 0 7px 18px rgba(0, 102, 204, 0.18);
}

.synthetic-case-ghost-button :deep(.ant-btn-icon),
.synthetic-case-primary-button :deep(.ant-btn-icon) {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  margin-inline-end: 0 !important;
}

.synthetic-case-primary-button.is-strong {
  box-shadow: 0 9px 22px rgba(0, 102, 204, 0.24);
}

.synthetic-case-ghost-button:hover,
.synthetic-case-primary-button:hover {
  transform: translateY(-1px);
}

.synthetic-case-shell {
  display: grid;
  grid-template-columns: 244px minmax(0, 1fr) 340px;
  gap: 14px;
  margin: 0 auto;
  max-width: 1600px;
  border-radius: 20px;
  padding: 14px;
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.035),
    0 18px 42px rgba(0, 0, 0, 0.055);
}

.synthetic-case-sidebar,
.synthetic-case-right {
  min-width: 0;
}

.synthetic-case-step-card {
  position: relative;
  border-radius: 15px;
  background: rgba(0, 0, 0, 0.025);
  padding: 12px 13px 12px 42px;
}

.synthetic-case-step-card + .synthetic-case-step-card {
  margin-top: 8px;
}

.synthetic-case-step-card span {
  position: absolute;
  left: 12px;
  top: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 8px;
  background: rgba(0, 102, 204, 0.09);
  color: #0066cc;
  font-size: 11px;
  font-weight: 700;
}

.synthetic-case-step-card strong {
  display: block;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 700;
  line-height: 18px;
}

.synthetic-case-step-card p {
  margin: 3px 0 0;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  line-height: 18px;
}

.synthetic-case-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 18px 0 10px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
  font-weight: 700;
}

.synthetic-case-doc-title {
  margin-top: 18px;
}

.synthetic-case-template-list,
.synthetic-case-doc-nav,
.synthetic-case-doc-list,
.synthetic-case-golden-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.synthetic-case-template,
.synthetic-case-doc-nav button {
  width: 100%;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 13px;
  background: rgba(255, 255, 255, 0.66);
  color: #1d1d1f;
  cursor: pointer;
  padding: 11px 12px;
  text-align: left;
  transition: 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.synthetic-case-template:hover,
.synthetic-case-doc-nav button:hover {
  border-color: rgba(0, 102, 204, 0.28);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.08),
    0 6px 22px rgba(0, 0, 0, 0.055);
  transform: translateY(-1px);
}

.synthetic-case-template.is-active {
  border-color: rgba(0, 102, 204, 0.42);
  background: rgba(0, 102, 204, 0.08);
}

.synthetic-case-template strong,
.synthetic-case-doc-nav strong {
  display: block;
  font-size: 13px;
  font-weight: 650;
  line-height: 19px;
}

.synthetic-case-template span,
.synthetic-case-doc-nav span {
  color: #0066cc;
  font-size: 12px;
  font-weight: 700;
}

.synthetic-case-template small,
.synthetic-case-doc-nav small {
  display: block;
  margin-top: 4px;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  line-height: 18px;
}

.synthetic-case-doc-nav button {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  align-items: start;
  gap: 8px;
}

.synthetic-case-doc-nav button > span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 9px;
  background: rgba(0, 102, 204, 0.08);
}

.synthetic-case-editor {
  min-width: 0;
}

.synthetic-case-card {
  border-radius: 17px;
  padding: 18px 18px 20px;
  transition: 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.synthetic-case-card + .synthetic-case-card {
  margin-top: 14px;
}

.synthetic-case-card:hover {
  border-color: rgba(0, 0, 0, 0.12);
}

.synthetic-case-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.synthetic-case-section-head h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 650;
  line-height: 22px;
}

.synthetic-case-section-head p {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
}

.synthetic-case-form-grid,
.synthetic-case-doc-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 13px;
}

.synthetic-case-form-grid label,
.synthetic-case-doc-grid label,
.synthetic-case-golden label {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
  color: rgba(29, 29, 31, 0.64);
  font-size: 12px;
  font-weight: 650;
}

.synthetic-case-form-grid .is-wide {
  grid-column: span 2;
}

.synthetic-case-doc {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.72);
  padding: 14px 14px 15px;
  scroll-margin-top: 20px;
}

.synthetic-case-doc:hover {
  border-color: rgba(0, 102, 204, 0.18);
}

.synthetic-case-doc-head,
.synthetic-case-golden-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.synthetic-case-doc-head span {
  display: block;
  color: #0066cc;
  font-size: 12px;
  font-weight: 700;
}

.synthetic-case-doc-head strong,
.synthetic-case-golden-head strong {
  font-size: 14px;
  font-weight: 650;
  line-height: 20px;
}

.synthetic-case-doc-grid {
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  margin-bottom: 12px;
}

.synthetic-case-doc-select {
  width: 100%;
  min-width: 0;
}

.synthetic-case-doc-status {
  min-height: 24px;
  border-color: rgba(16, 185, 129, 0.18);
  background: rgba(16, 185, 129, 0.08);
  color: #047857;
}

.synthetic-case-doc-status.is-disabled {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.46);
}

.synthetic-case-sticky-card {
  position: sticky;
  top: 118px;
  max-height: calc(100vh - 138px);
  overflow: auto;
}

.synthetic-case-golden {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.7);
  padding: 12px 12px 14px;
}

.synthetic-case-golden label + label {
  margin-top: 10px;
}

.synthetic-case-preview {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
}

.synthetic-case-preview aside {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-radius: 16px;
  background: #f5f5f7;
  padding: 14px;
}

.synthetic-case-preview aside strong {
  font-size: 16px;
}

.synthetic-case-preview aside span {
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
}

.synthetic-case-preview pre {
  max-height: 68vh;
  overflow: auto;
  white-space: pre-wrap;
  border-radius: 16px;
  background: #f8fafc;
  color: #1d1d1f;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.9;
  margin: 0;
  padding: 16px;
}

.synthetic-case-page :deep(.ant-input),
.synthetic-case-page :deep(.ant-input-number),
.synthetic-case-page :deep(.ant-select-selector),
.synthetic-case-page :deep(.ant-input-number-input),
.synthetic-case-page :deep(.ant-btn),
.synthetic-case-page :deep(.ant-select-dropdown) {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.synthetic-case-page :deep(.ant-input),
.synthetic-case-page :deep(.ant-input-number),
.synthetic-case-page :deep(.ant-select-selector) {
  border-color: rgba(0, 0, 0, 0.1) !important;
  border-radius: 8px !important;
  background: rgba(255, 255, 255, 0.78) !important;
  font-size: 13px;
  font-weight: 400;
}

.synthetic-case-page :deep(.ant-input:not(textarea)),
.synthetic-case-page :deep(.ant-input-number),
.synthetic-case-page :deep(.ant-select-selector) {
  min-height: 34px;
}

.synthetic-case-page :deep(.ant-input-number-input),
.synthetic-case-page :deep(.ant-select-selection-item),
.synthetic-case-page :deep(.ant-select-selection-placeholder) {
  font-weight: 400;
}

.synthetic-case-page :deep(textarea.ant-input) {
  font-weight: 400;
  line-height: 1.85;
}

.synthetic-case-page :deep(.ant-input:focus),
.synthetic-case-page :deep(.ant-input-focused),
.synthetic-case-page :deep(.ant-select-focused .ant-select-selector) {
  border-color: rgba(0, 102, 204, 0.46) !important;
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.08) !important;
}

@media (max-width: 1280px) {
  .synthetic-case-header {
    position: static;
    align-items: flex-start;
    flex-direction: column;
  }

  .synthetic-case-header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .synthetic-case-shell {
    grid-template-columns: 220px minmax(0, 1fr);
  }

  .synthetic-case-right {
    grid-column: 1 / -1;
  }

  .synthetic-case-sticky-card {
    position: static;
    max-height: none;
  }
}

@media (max-width: 960px) {
  .synthetic-case-page {
    padding: 14px;
  }

  .synthetic-case-shell {
    grid-template-columns: minmax(0, 1fr);
  }

  .synthetic-case-form-grid,
  .synthetic-case-doc-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .synthetic-case-form-grid .is-wide {
    grid-column: span 2;
  }

  .synthetic-case-header-actions {
    flex-wrap: wrap;
  }
}
</style>
