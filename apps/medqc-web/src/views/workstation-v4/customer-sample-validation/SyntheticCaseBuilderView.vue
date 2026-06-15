<template>
  <main class="synthetic-case-page">
    <header class="synthetic-case-header">
      <div>
        <button
          class="synthetic-case-back"
          type="button"
          @click="goBack"
        >
          <ArrowLeft :size="16" />
          返回样本验证
        </button>
        <h1>创建测试病历</h1>
        <p>通过模板或复制粘贴创建客户自建测试病历，保存到独立样本池后验证泸县0609质控点。</p>
      </div>
      <div class="synthetic-case-header-actions">
        <a-button
          class="!rounded-lg"
          @click="showPreview = true"
        >
          <template #icon>
            <EyeOutlined />
          </template>
          预览病历包
        </a-button>
        <a-button
          type="primary"
          class="!rounded-lg"
          :loading="saving"
          @click="handleSave(false)"
        >
          保存到测试样本池
        </a-button>
        <a-button
          type="primary"
          class="!rounded-lg"
          :loading="savingAndRunning"
          @click="handleSave(true)"
        >
          保存并立即验证
        </a-button>
      </div>
    </header>

    <section class="synthetic-case-shell">
      <aside class="synthetic-case-sidebar">
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
            <span>{{ index + 1 }}</span>
            <strong>{{ document.title || documentTypeLabel(document.document_type) }}</strong>
            <small>{{ documentTypeLabel(document.document_type) }}</small>
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
import { EyeOutlined } from '@ant-design/icons-vue'
import { ArrowLeft, FileText, Layers } from 'lucide-vue-next'
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
  padding: 18px 22px 24px;
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
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.04),
    0 10px 28px rgba(0, 0, 0, 0.06);
}

.synthetic-case-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin: 0 auto 16px;
  max-width: 1600px;
  border-radius: 20px;
  padding: 18px 20px;
}

.synthetic-case-header h1 {
  margin: 6px 0 4px;
  font-size: 28px;
  font-weight: 700;
  line-height: 31px;
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

.synthetic-case-header-actions,
.synthetic-case-inline-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.synthetic-case-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 360px;
  gap: 16px;
  margin: 0 auto;
  max-width: 1600px;
  border-radius: 22px;
  padding: 16px;
}

.synthetic-case-sidebar,
.synthetic-case-right {
  min-width: 0;
}

.synthetic-case-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
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
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  color: #1d1d1f;
  cursor: pointer;
  padding: 12px;
  text-align: left;
  transition: 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.synthetic-case-template:hover,
.synthetic-case-doc-nav button:hover {
  border-color: rgba(0, 102, 204, 0.28);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.synthetic-case-template.is-active {
  border-color: rgba(0, 102, 204, 0.42);
  background: rgba(0, 102, 204, 0.08);
}

.synthetic-case-template strong,
.synthetic-case-doc-nav strong {
  display: block;
  font-size: 14px;
  font-weight: 700;
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

.synthetic-case-editor {
  min-width: 0;
}

.synthetic-case-card {
  border-radius: 18px;
  padding: 18px;
}

.synthetic-case-card + .synthetic-case-card {
  margin-top: 16px;
}

.synthetic-case-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.synthetic-case-section-head h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
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
  gap: 14px;
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
  font-weight: 600;
}

.synthetic-case-form-grid .is-wide {
  grid-column: span 2;
}

.synthetic-case-doc {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.74);
  padding: 14px;
  scroll-margin-top: 20px;
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
  font-size: 15px;
  font-weight: 700;
}

.synthetic-case-doc-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin-bottom: 12px;
}

.synthetic-case-doc-select {
  width: 180px;
}

.synthetic-case-sticky-card {
  position: sticky;
  top: 12px;
  max-height: calc(100vh - 150px);
  overflow: auto;
}

.synthetic-case-golden {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.74);
  padding: 12px;
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

@media (max-width: 1280px) {
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
</style>
