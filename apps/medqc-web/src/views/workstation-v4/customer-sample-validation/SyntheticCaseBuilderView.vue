<template>
  <main class="synthetic-case-page mq-page">
    <header class="synthetic-case-header mq-page-head">
      <div class="synthetic-case-header-copy mq-page-head__copy">
        <button class="synthetic-case-back" type="button" @click="goBack">
          <MqIcon name="back" :size="16" />
          返回样本验证
        </button>
        <div class="synthetic-case-eyebrow mq-page-eyebrow">客户样本验证 / 测试病历构建</div>
        <h1 class="mq-page-title">创建测试病历</h1>
        <p>选择已配置模板的主要质控点后生成可编辑病历，用于验证规则效果。</p>
        <div class="synthetic-case-summary">
          <span>规则集：泸县0609质控点验证 v1</span>
          <span>模板质控点 {{ configuredRuleCount }} 条</span>
          <span>已选 {{ selectedRuleSelection.length }} 条</span>
          <span>文书 {{ enabledDocumentCount }} 份</span>
          <span>独立样本池</span>
        </div>
      </div>
      <div class="synthetic-case-header-actions mq-page-head__actions">
        <a-button class="synthetic-case-ghost-button" @click="openSyntheticCaseGuide">
          <template #icon>
            <MqIcon name="rules" :size="15" />
          </template>
          功能导览
        </a-button>
        <a-button
          v-if="wizardStep > 1"
          class="synthetic-case-ghost-button"
          @click="showPreview = true"
        >
          <template #icon>
            <MqIcon name="doc" :size="15" />
          </template>
          预览病历包
        </a-button>
        <a-button
          v-if="wizardStep === 1"
          type="primary"
          class="synthetic-case-primary-button"
          @click="generateRuleDrivenCase"
        >
          生成并进入编辑
        </a-button>
        <a-button
          v-if="wizardStep === 2"
          class="synthetic-case-ghost-button"
          @click="goWizardStep(1)"
        >
          返回选择
        </a-button>
        <a-button
          v-if="wizardStep === 2"
          type="primary"
          class="synthetic-case-primary-button is-strong"
          @click="goWizardStep(3)"
        >
          下一步
        </a-button>
        <a-button
          v-if="wizardStep === 3"
          type="primary"
          class="synthetic-case-primary-button"
          :loading="saving"
          @click="handleSave(false)"
        >
          仅保存测试病历
        </a-button>
        <a-button
          v-if="wizardStep === 3"
          type="primary"
          class="synthetic-case-primary-button is-strong"
          :loading="savingAndRunning"
          @click="handleSave(true)"
        >
          保存并验证选中质控点
        </a-button>
      </div>
    </header>

    <nav
      class="synthetic-case-wizard"
      aria-label="创建测试病历步骤"
      data-synthetic-guide="wizard"
      :class="syntheticCaseGuideTargetClass('wizard')"
    >
      <button
        v-for="step in builderSteps"
        :key="step.key"
        type="button"
        :class="{
          'is-active': wizardStep === step.key,
          'is-complete': wizardStep > step.key,
        }"
        @click="goWizardStep(step.key)"
      >
        <span>{{ String(step.key).padStart(2, '0') }}</span>
        <div>
          <strong>{{ step.title }}</strong>
          <small>{{ step.description }}</small>
        </div>
      </button>
    </nav>

    <section class="synthetic-case-shell mq-card">
      <aside class="synthetic-case-sidebar">
        <div class="synthetic-case-rule-set-card">
          <span>固定规则集</span>
          <strong>泸县0609质控点验证 v1</strong>
          <small>保存后仅验证本页选中的 LX0609 质控点。</small>
        </div>

        <template v-if="wizardStep === 1">
          <div class="synthetic-case-panel-title">
            <MqIcon name="stack" :size="16" />
            规则族
          </div>
          <div
            class="synthetic-case-template-list"
            data-synthetic-guide="rule-family"
            :class="syntheticCaseGuideTargetClass('rule-family')"
          >
            <button
              v-for="family in availableRuleFamilies"
              :key="family.key"
              class="synthetic-case-template"
              :class="{ 'is-active': form.selectedRuleFamilyKey === family.key }"
              type="button"
              @click="selectRuleFamily(family.key)"
            >
              <strong>{{ family.name }}</strong>
              <span>{{ family.rules.length }} 条规则</span>
              <small>{{ family.description }}</small>
            </button>
          </div>
        </template>

        <div v-if="wizardStep > 1" class="synthetic-case-panel-title synthetic-case-doc-title">
          <MqIcon name="doc" :size="16" />
          文书目录
        </div>
        <div v-if="wizardStep > 1" class="synthetic-case-doc-nav">
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
        <div
          v-if="wizardStep === 2"
          class="synthetic-case-editor-tabs"
          data-synthetic-guide="editor-tabs"
          :class="syntheticCaseGuideTargetClass('editor-tabs')"
        >
          <button
            v-for="tab in editorTabs"
            :key="tab.key"
            type="button"
            :class="{ 'is-active': editorTab === tab.key }"
            @click="editorTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <section
          v-if="wizardStep === 1"
          class="synthetic-case-card mq-card synthetic-case-selection-card"
        >
          <div class="synthetic-case-section-head">
            <div>
              <h2>选择要验证的质控点</h2>
              <p>先选规则族，再勾选质控点。系统会根据已配置模板生成可编辑病历草稿。</p>
            </div>
            <span class="synthetic-case-section-chip">
              已选 {{ selectedRuleSelection.length }} 条
            </span>
          </div>
          <div v-if="isDraftStale" class="synthetic-case-warning-banner">
            质控点选择已变更，当前病历草稿仍是旧范围。请重新生成病历草稿后再保存或验证。
          </div>

          <div class="synthetic-case-selection-layout">
            <div class="synthetic-case-selection-main">
              <div
                v-if="selectedRuleFamily"
                class="synthetic-case-rule-grid"
                data-synthetic-guide="rule-selection"
                :class="syntheticCaseGuideTargetClass('rule-selection')"
              >
                <div class="synthetic-case-rule-grid-head">
                  <div>
                    <strong>{{ selectedRuleFamily.name }}</strong>
                    <small
                      >本组 {{ selectedRuleFamily.rules.length }} 条，已选
                      {{ selectedFamilyRuleSelectionCount }} 条</small
                    >
                  </div>
                  <button type="button" @click="toggleSelectedRuleFamily">
                    {{ isSelectedRuleFamilyFullySelected ? '取消本组' : '全选本组' }}
                  </button>
                </div>
                <label
                  v-for="rule in selectedRuleFamily.rules"
                  :key="rule.ruleId"
                  class="synthetic-case-rule-card"
                  :class="{ 'is-selected': selectedRuleSelection.includes(rule.ruleId) }"
                >
                  <input
                    :checked="selectedRuleSelection.includes(rule.ruleId)"
                    type="checkbox"
                    @change="
                      toggleRuleSelection(rule.ruleId, ($event.target as HTMLInputElement).checked)
                    "
                  />
                  <div>
                    <strong>{{ rule.ruleId }}</strong>
                    <span>{{ rule.name }}</span>
                    <small>需要材料：{{ rule.requiredDocumentsLabel }}</small>
                  </div>
                </label>
              </div>
            </div>

            <aside
              class="synthetic-case-selection-summary"
              data-synthetic-guide="expectation"
              :class="syntheticCaseGuideTargetClass('expectation')"
            >
              <div>
                <span>本轮期望结果</span>
                <div class="synthetic-case-fixed-status">
                  <strong>有缺陷</strong>
                  <small
                    >当前版本提供缺陷验证模板；无缺陷、不适用和数据不足需专用模板后开放。</small
                  >
                </div>
              </div>
              <div>
                <span>关键材料</span>
                <ul v-if="selectedRequiredMaterials.length" class="synthetic-case-material-list">
                  <li v-for="material in selectedRequiredMaterials" :key="material">
                    {{ material }}
                  </li>
                </ul>
                <p v-else>请选择质控点后查看需要准备的文书和结构化材料。</p>
              </div>
              <div>
                <span>已选质控点</span>
                <div v-if="selectedRules.length" class="synthetic-case-selected-rules">
                  <em v-for="rule in selectedRules" :key="rule.ruleId">
                    {{ rule.ruleId }} · {{ rule.familyName }}
                  </em>
                </div>
                <p v-else>尚未选择质控点。</p>
              </div>
              <a-button
                type="primary"
                block
                class="synthetic-case-generate-button"
                data-synthetic-guide="generate"
                :class="syntheticCaseGuideTargetClass('generate')"
                @click="generateRuleDrivenCase"
              >
                生成病历草稿
              </a-button>
            </aside>
          </div>
        </section>

        <section
          v-if="wizardStep === 2 && editorTab === 'overview'"
          class="synthetic-case-card mq-card"
          data-synthetic-guide="basic-info"
          :class="syntheticCaseGuideTargetClass('basic-info')"
        >
          <div class="synthetic-case-section-head">
            <div>
              <h2>基本信息</h2>
              <p>
                {{
                  form.builderMode === 'rule'
                    ? '这份病历由已选质控点自动生成骨架，下面字段仍可继续人工调整。'
                    : '这些字段会写入测试病历主索引和样本池列表。'
                }}
              </p>
            </div>
            <span class="synthetic-case-section-chip">
              {{ currentCaseSourceLabel }}
            </span>
          </div>
          <div class="synthetic-case-form-grid">
            <label>
              <span>测试病历名称</span>
              <a-input v-model:value="form.caseTitle" placeholder="例如：术后记录超时测试" />
            </label>
            <label>
              <span>患者姓名</span>
              <a-input v-model:value="form.patientName" placeholder="脱敏姓名" />
            </label>
            <label>
              <span>性别</span>
              <a-select v-model:value="form.sex" :options="sexOptions" />
            </label>
            <label>
              <span>年龄</span>
              <a-input-number v-model:value="form.age" class="w-full" :min="0" :max="120" />
            </label>
            <label>
              <span>住院号</span>
              <a-input v-model:value="form.mrNo" placeholder="可选，留空自动生成" />
            </label>
            <label>
              <span>科室</span>
              <a-input v-model:value="form.department" placeholder="例如：普通外科" />
            </label>
            <label>
              <span>入院时间</span>
              <a-input v-model:value="form.admissionTime" type="datetime-local" />
            </label>
            <label>
              <span>出院时间</span>
              <a-input v-model:value="form.dischargeTime" type="datetime-local" />
            </label>
            <label>
              <span>评价时间点</span>
              <a-input
                v-model:value="form.evaluationAsOfDate"
                type="date"
                aria-label="评价时间点"
                placeholder="留空取创建当天"
              />
              <small class="field-hint">未出院病例的时限规则按此日期评价，创建后固定</small>
            </label>
            <label class="is-wide">
              <span>主要诊断</span>
              <a-input v-model:value="form.mainDiagnosis" placeholder="可选，用于质控上下文" />
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

        <section
          v-if="wizardStep === 2 && editorTab === 'documents'"
          class="synthetic-case-card mq-card"
          data-synthetic-guide="documents"
          :class="syntheticCaseGuideTargetClass('documents')"
        >
          <div class="synthetic-case-section-head">
            <div>
              <h2>病历文书</h2>
            </div>
            <div class="synthetic-case-inline-actions">
              <a-select
                v-model:value="newDocumentType"
                class="synthetic-case-doc-select"
                popup-class-name="synthetic-case-doc-type-dropdown"
                :options="testRecordDocumentTypeOptions"
              />
              <a-button @click="addDocument"> 添加文书 </a-button>
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
                  <a-switch v-model:checked="document.enabled" size="small" />
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
                    popup-class-name="synthetic-case-doc-type-dropdown"
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
                  <a-input v-model:value="document.record_time" type="datetime-local" />
                </label>
                <label>
                  <span>提交时间</span>
                  <a-input v-model:value="document.submit_time" type="datetime-local" />
                </label>
                <label>
                  <span>记录医师</span>
                  <a-input v-model:value="document.doctor_name" placeholder="可选" />
                </label>
              </div>
              <a-textarea
                v-model:value="document.content"
                :rows="10"
                placeholder="粘贴或编辑这份文书的完整文本。缺陷应由真实文书内容自然体现，不要写“备注：这里缺失”。"
              />
              <div class="synthetic-case-doc-edit-footer">
                <span
                  class="synthetic-case-doc-edit-status"
                  :class="{ 'is-dirty': isDocumentDirty(document) }"
                >
                  {{ documentEditStatusText(document) }}
                </span>
                <div class="synthetic-case-inline-actions">
                  <a-button
                    size="small"
                    :disabled="!isDocumentDirty(document)"
                    @click="applyDocumentEdit(document)"
                  >
                    应用修改
                  </a-button>
                  <a-button
                    size="small"
                    :disabled="!canRestoreDocumentTemplate(document)"
                    @click="restoreDocumentTemplate(document)"
                  >
                    还原模板
                  </a-button>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section
          v-if="wizardStep === 2 && editorTab === 'orders'"
          class="synthetic-case-card mq-card"
        >
          <div class="synthetic-case-section-head">
            <div>
              <h2>医嘱费用</h2>
              <p>这里集中编辑医嘱、输血申请、输血记录等与跨表质控相关的材料。</p>
            </div>
            <span class="synthetic-case-section-chip">
              {{ tabDocumentCount('orders') }} 份材料
            </span>
          </div>
          <div class="synthetic-case-tab-doc-list">
            <button
              v-for="document in tabDocuments('orders')"
              :key="document.key"
              type="button"
              @click="openDocumentEditor(document.key)"
            >
              <strong>{{ document.title || documentTypeLabel(document.document_type) }}</strong>
              <span>{{ documentTypeLabel(document.document_type) }}</span>
            </button>
            <p v-if="!tabDocumentCount('orders')">
              当前所选质控点未生成医嘱费用材料，可在“文书”中手动添加。
            </p>
          </div>
        </section>

        <section
          v-if="wizardStep === 2 && editorTab === 'exams'"
          class="synthetic-case-card mq-card"
        >
          <div class="synthetic-case-section-head">
            <div>
              <h2>检查检验</h2>
              <p>集中查看检查报告、检验报告和对应病程分析材料。</p>
            </div>
            <span class="synthetic-case-section-chip">
              {{ tabDocumentCount('exams') }} 份材料
            </span>
          </div>
          <div class="synthetic-case-tab-doc-list">
            <button
              v-for="document in tabDocuments('exams')"
              :key="document.key"
              type="button"
              @click="openDocumentEditor(document.key)"
            >
              <strong>{{ document.title || documentTypeLabel(document.document_type) }}</strong>
              <span>{{ documentTypeLabel(document.document_type) }}</span>
            </button>
            <p v-if="!tabDocumentCount('exams')">
              当前所选质控点未生成检查检验材料，可在“文书”中手动添加。
            </p>
          </div>
        </section>

        <section
          v-if="wizardStep === 2 && editorTab === 'preview'"
          class="synthetic-case-card mq-card"
        >
          <div class="synthetic-case-section-head">
            <div>
              <h2>预览</h2>
              <p>保存前检查整份病历包文本，不展示 PG 表字段或内部 bundle。</p>
            </div>
          </div>
          <pre class="synthetic-case-inline-preview">{{ previewText }}</pre>
        </section>

        <section
          v-if="wizardStep === 3"
          class="synthetic-case-card mq-card synthetic-case-confirm-card"
          data-synthetic-guide="confirm"
          :class="syntheticCaseGuideTargetClass('confirm')"
        >
          <div class="synthetic-case-section-head">
            <div>
              <h2>保存并验证</h2>
              <p>确认后会保存到客户自建样本池，并只验证本次选择的 LX0609 质控点。</p>
            </div>
            <span class="synthetic-case-section-chip"> 期望：有缺陷 </span>
          </div>

          <div class="synthetic-case-confirm-grid">
            <div class="synthetic-case-confirm-block">
              <span>测试病历</span>
              <strong>{{ form.caseTitle }}</strong>
              <p>
                {{ form.patientName }} · {{ form.sex }} · {{ form.age }}岁 · {{ form.department }}
              </p>
            </div>
            <div class="synthetic-case-confirm-block">
              <span>验证范围</span>
              <strong>{{ form.selectedRuleIds.length }} 条 LX0609 质控点</strong>
              <p>不会扩展到 49 条全集。</p>
            </div>
            <div class="synthetic-case-confirm-block">
              <span>病历材料</span>
              <strong>{{ enabledDocumentCount }} 份文书</strong>
              <p>{{ generatedRequiredMaterials.join('、') || '按当前文书内容保存' }}</p>
            </div>
          </div>

          <div class="synthetic-case-confirm-list">
            <div v-for="rule in generatedRules" :key="rule.ruleId">
              <strong>{{ rule.ruleId }}</strong>
              <span>{{ rule.name }}</span>
              <small>{{ rule.familyName }} · {{ rule.requiredDocumentsLabel }}</small>
            </div>
          </div>

          <div class="synthetic-case-confirm-actions">
            <a-button @click="goWizardStep(2)"> 返回编辑 </a-button>
            <a-button type="primary" :loading="saving" @click="handleSave(false)">
              仅保存测试病历
            </a-button>
            <a-button
              type="primary"
              class="synthetic-case-primary-button is-strong"
              :loading="savingAndRunning"
              data-synthetic-guide="save-run"
              :class="syntheticCaseGuideTargetClass('save-run')"
              @click="handleSave(true)"
            >
              保存并验证选中质控点
            </a-button>
          </div>
        </section>
      </div>
    </section>

    <a-modal
      v-model:open="showPreview"
      width="88vw"
      title="病历包预览"
      :footer="null"
      wrap-class-name="mq-modal synthetic-case-preview-modal"
    >
      <div class="synthetic-case-preview">
        <aside>
          <strong>{{ form.caseTitle || '未命名测试病历' }}</strong>
          <span>{{ form.patientName }} · {{ form.department }}</span>
          <span>文书 {{ enabledDocumentCount }} 份</span>
        </aside>
        <pre>{{ previewText }}</pre>
      </div>
    </a-modal>

    <div v-if="syntheticCaseGuideOpen" class="synthetic-case-tour-layer">
      <div class="synthetic-case-tour-scrim" />
      <div class="synthetic-case-tour-card" :style="syntheticCaseTourCardStyle">
        <div class="synthetic-case-tour-kicker">创建测试病历导览</div>
        <div class="synthetic-case-tour-count">
          {{ syntheticCaseGuideStepIndex + 1 }} / {{ syntheticCaseGuideSteps.length }}
        </div>
        <h3>{{ currentSyntheticCaseGuideStep.title }}</h3>
        <p>{{ currentSyntheticCaseGuideStep.description }}</p>
        <div class="synthetic-case-tour-dots">
          <button
            v-for="(_, index) in syntheticCaseGuideSteps"
            :key="index"
            type="button"
            :class="{ 'is-active': index === syntheticCaseGuideStepIndex }"
            :aria-label="`查看第 ${index + 1} 步`"
            @click="goToSyntheticCaseGuideStep(index)"
          />
        </div>
        <div class="synthetic-case-tour-actions">
          <a-button class="!rounded-lg" @click="closeSyntheticCaseGuide"> 跳过 </a-button>
          <a-button
            v-if="syntheticCaseGuideStepIndex > 0"
            class="!rounded-lg"
            @click="goToPreviousSyntheticCaseGuideStep"
          >
            上一步
          </a-button>
          <a-button type="primary" class="!rounded-lg" @click="goToNextSyntheticCaseGuideStep">
            {{ isLastSyntheticCaseGuideStep ? '完成导览' : '下一步' }}
          </a-button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import MqIcon from '@/components/icons/MqIcon.vue'
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import type { CSSProperties } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'

import {
  createManualTestMedicalRecord,
  listLuxian0609CustomerRules,
  runManualSamplePool,
} from '@/services/manual-case-sample-service'
import type { SyntheticCaseTemplate } from './syntheticCaseTemplates'
import { syntheticCaseRuleFamilies, syntheticCaseTemplates } from './syntheticCaseTemplates'
import type {
  SyntheticCaseBuilderMode,
  SyntheticCaseRuleFamily,
  TestRecordDocumentForm,
} from './types'
import {
  buildSyntheticCaseRunPayload,
  buildRuleDrivenCaseTitle,
  buildSyntheticCaseRuleFamiliesFromCatalog,
  createDefaultSyntheticCaseForm,
  createSyntheticDocument,
  documentTypeLabel,
  findForbiddenSelfHints,
  hasSameRuleScope,
  normalizeSyntheticCasePayload,
  normalizeRuleIds,
  sexOptions,
  testRecordDocumentTypeOptions,
} from './syntheticCaseBuilder'

const router = useRouter()
const route = useRoute()
const form = ref(createDefaultSyntheticCaseForm())
const newDocumentType = ref('daily_course_record')
const saving = ref(false)
const savingAndRunning = ref(false)
const showPreview = ref(false)
const wizardStep = ref<1 | 2 | 3>(1)
const editorTab = ref<'overview' | 'documents' | 'orders' | 'exams' | 'preview'>('overview')
const selectedRuleSelection = ref<string[]>([])
const luxianRuleCatalogFamilies = ref<SyntheticCaseRuleFamily[]>([])
const syntheticCaseGuideOpen = ref(false)
const syntheticCaseGuideStepIndex = ref(0)
const syntheticCaseTourCardStyle = ref<CSSProperties>({})
let syntheticCaseGuidePositionTimer: ReturnType<typeof setTimeout> | null = null

type SyntheticCaseGuideTarget =
  | 'wizard'
  | 'rule-family'
  | 'rule-selection'
  | 'expectation'
  | 'generate'
  | 'editor-tabs'
  | 'basic-info'
  | 'documents'
  | 'confirm'
  | 'save-run'

const SYNTHETIC_CASE_GUIDE_STORAGE_KEY = 'medqc_synthetic_case_builder_guide_seen_v1'

const syntheticCaseGuideSteps: Array<{
  target: SyntheticCaseGuideTarget
  title: string
  description: string
  wizardStep: 1 | 2 | 3
  editorTab?: typeof editorTab.value
}> = [
  {
    target: 'wizard',
    title: '三步创建测试病历',
    description: '先选质控点，再编辑自动生成的病历草稿，最后保存到客户自建样本池并验证。',
    wizardStep: 1,
  },
  {
    target: 'rule-family',
    title: '选择规则族',
    description: '左侧按规则族组织 LX0609 质控点，例如基础时限、会诊质量、手术麻醉等。',
    wizardStep: 1,
  },
  {
    target: 'rule-selection',
    title: '勾选本次要验证的质控点',
    description: '勾选后，后续保存验证只会运行这些 LX0609 质控点，不会扩展到全集。',
    wizardStep: 1,
  },
  {
    target: 'expectation',
    title: '确认期望结果和材料',
    description: '右侧会提示当前模板的期望结果、关键材料和已选质控点，便于演示前确认范围。',
    wizardStep: 1,
  },
  {
    target: 'generate',
    title: '生成病历草稿',
    description: '点击后系统会按所选质控点生成真实病历风格草稿，进入可编辑状态。',
    wizardStep: 1,
  },
  {
    target: 'basic-info',
    title: '编辑基本信息',
    description: '这里调整病历名称、患者脱敏信息、科室和入院时间，这些内容会显示在样本池列表里。',
    wizardStep: 2,
    editorTab: 'overview',
  },
  {
    target: 'documents',
    title: '检查和编辑文书',
    description: '这里编辑入院记录、病程、会诊、手术麻醉等文书正文，缺陷应由文书事实自然体现。',
    wizardStep: 2,
    editorTab: 'documents',
  },
  {
    target: 'confirm',
    title: '确认保存范围',
    description: '保存前确认测试病历、验证范围和文书数量，确保只跑选中的 LX0609 质控点。',
    wizardStep: 3,
  },
  {
    target: 'save-run',
    title: '保存并验证',
    description: '点击后会保存到客户自建样本池，并立即创建只包含选中质控点的验证任务。',
    wizardStep: 3,
  },
]

const builderSteps = [
  {
    key: 1,
    title: '选择质控点',
    description: '固定泸县0609规则集，选择本次要验证的质控点。',
  },
  {
    key: 2,
    title: '编辑测试病历',
    description: '系统生成真实病历风格草稿，客户只调整关键事实。',
  },
  {
    key: 3,
    title: '保存并验证',
    description: '保存到客户自建样本池，并只跑选中的 LX0609 规则。',
  },
] as const
const editorTabs = [
  { key: 'overview', label: '病历概览' },
  { key: 'documents', label: '文书' },
  { key: 'orders', label: '医嘱费用' },
  { key: 'exams', label: '检查检验' },
  { key: 'preview', label: '预览' },
] as const

const enabledDocumentCount = computed(
  () =>
    form.value.documents.filter((document) => document.enabled && document.content.trim()).length,
)
const configuredRuleCount = computed(
  () =>
    new Set(
      syntheticCaseRuleFamilies.flatMap((family) =>
        family.rules.map((rule) =>
          String(rule.ruleId || '')
            .trim()
            .toUpperCase(),
        ),
      ),
    ).size,
)
const availableRuleFamilies = computed(() =>
  luxianRuleCatalogFamilies.value.length
    ? luxianRuleCatalogFamilies.value
    : syntheticCaseRuleFamilies,
)
const selectedRuleFamily = computed(() =>
  availableRuleFamilies.value.find((family) => family.key === form.value.selectedRuleFamilyKey),
)
const selectedFamilyRuleIds = computed(
  () => selectedRuleFamily.value?.rules.map((rule) => rule.ruleId) || [],
)
const selectedFamilyRuleSelectionCount = computed(
  () =>
    selectedFamilyRuleIds.value.filter((ruleId) => selectedRuleSelection.value.includes(ruleId))
      .length,
)
const isSelectedRuleFamilyFullySelected = computed(
  () =>
    selectedFamilyRuleIds.value.length > 0 &&
    selectedFamilyRuleSelectionCount.value === selectedFamilyRuleIds.value.length,
)
const allRuleOptions = computed(() =>
  availableRuleFamilies.value.flatMap((family) =>
    family.rules.map((rule) => ({
      ...rule,
      familyKey: family.key,
      familyName: family.name,
      templateKey: family.templateKey,
    })),
  ),
)
const selectedRules = computed(() =>
  allRuleOptions.value.filter((rule) => selectedRuleSelection.value.includes(rule.ruleId)),
)
const generatedRules = computed(() =>
  allRuleOptions.value.filter((rule) => form.value.selectedRuleIds.includes(rule.ruleId)),
)
const selectedRuleFamilies = computed(() =>
  availableRuleFamilies.value.filter((family) =>
    family.rules.some((rule) => selectedRuleSelection.value.includes(rule.ruleId)),
  ),
)
const selectedRequiredMaterials = computed(() => {
  const materials = new Set<string>()
  selectedRules.value.forEach((rule) => {
    rule.requiredDocumentsLabel
      .split(/[、,，/]/u)
      .map((item) => item.trim())
      .filter(Boolean)
      .forEach((item) => materials.add(item))
  })
  return Array.from(materials)
})
const generatedRequiredMaterials = computed(() => {
  const materials = new Set<string>()
  generatedRules.value.forEach((rule) => {
    rule.requiredDocumentsLabel
      .split(/[、,，/]/u)
      .map((item) => item.trim())
      .filter(Boolean)
      .forEach((item) => materials.add(item))
  })
  return Array.from(materials)
})
const isDraftStale = computed(
  () =>
    form.value.builderMode === 'rule' &&
    form.value.selectedRuleIds.length > 0 &&
    !hasSameRuleScope(selectedRuleSelection.value, form.value.selectedRuleIds),
)
const currentSyntheticCaseGuideStep = computed(
  () => syntheticCaseGuideSteps[syntheticCaseGuideStepIndex.value] || syntheticCaseGuideSteps[0],
)
const isLastSyntheticCaseGuideStep = computed(
  () => syntheticCaseGuideStepIndex.value >= syntheticCaseGuideSteps.length - 1,
)
const currentCaseSourceLabel = computed(() => {
  if (form.value.builderMode === 'rule') {
    if (form.value.selectedRuleIds.length) {
      return `泸县0609 · ${form.value.selectedRuleIds.length} 条规则`
    }
    return '按质控点创建'
  }
  return '手工创建'
})

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

function isTabDocument(document: TestRecordDocumentForm, tab: 'orders' | 'exams'): boolean {
  if (tab === 'orders') {
    return ['medical_order', 'blood_application', 'bloodtrans_record'].includes(
      document.document_type,
    )
  }
  return ['exam_report', 'lab_report', 'daily_course_record'].includes(document.document_type)
}

function tabDocuments(tab: 'orders' | 'exams') {
  return form.value.documents.filter((document) => document.enabled && isTabDocument(document, tab))
}

function tabDocumentCount(tab: 'orders' | 'exams') {
  return tabDocuments(tab).length
}

function goBack() {
  router.push({ name: 'WorkstationV4CustomerSampleValidation' })
}

function parseRouteRuleIds(value: unknown): string[] {
  const items = Array.isArray(value) ? value : [value]
  return normalizeRuleIds(
    items.flatMap((item) =>
      String(item || '')
        .split(/[,\s，、]+/u)
        .map((ruleId) => ruleId.trim()),
    ),
  )
}

function resolveInitialRuleFamilyKey(ruleIds: string[], routeFamilyKey: unknown): string {
  const requestedFamilyKey = String(
    Array.isArray(routeFamilyKey) ? routeFamilyKey[0] || '' : routeFamilyKey || '',
  ).trim()
  if (
    requestedFamilyKey &&
    availableRuleFamilies.value.some((family) => family.key === requestedFamilyKey)
  ) {
    return requestedFamilyKey
  }
  const selectedRuleSet = new Set(ruleIds)
  const exactFamily = availableRuleFamilies.value.find(
    (family) =>
      family.rules.length > 0 && family.rules.every((rule) => selectedRuleSet.has(rule.ruleId)),
  )
  if (exactFamily) return exactFamily.key
  return (
    availableRuleFamilies.value.find((family) =>
      family.rules.some((rule) => selectedRuleSet.has(rule.ruleId)),
    )?.key ||
    availableRuleFamilies.value[0]?.key ||
    ''
  )
}

function initializeRuleSelectionFromRoute() {
  if (!syntheticCaseRuleFamilies.length) return
  form.value.builderMode = 'rule'
  const routeRuleIds = parseRouteRuleIds(route.query.ruleIds)
  if (routeRuleIds.length) {
    selectedRuleSelection.value = routeRuleIds
    selectRuleFamily(resolveInitialRuleFamilyKey(routeRuleIds, route.query.ruleFamily))
    return
  }
  selectRuleFamily(syntheticCaseRuleFamilies[0].key)
}

async function loadLuxian0609RuleCatalog() {
  const result = await listLuxian0609CustomerRules()
  if (!result.success || !result.data?.rules?.length) {
    luxianRuleCatalogFamilies.value = []
    return
  }
  luxianRuleCatalogFamilies.value = buildSyntheticCaseRuleFamiliesFromCatalog(result.data.rules)
  if (selectedRuleSelection.value.length) {
    selectRuleFamily(
      resolveInitialRuleFamilyKey(selectedRuleSelection.value, route.query.ruleFamily),
    )
  }
}

function createFormFromTemplate(
  template: SyntheticCaseTemplate,
  options: {
    builderMode?: SyntheticCaseBuilderMode
    selectedRuleIds?: string[]
    selectedRuleFamilyKey?: string
  } = {},
) {
  const selectedRuleIds = options.selectedRuleIds?.length
    ? [...options.selectedRuleIds]
    : [...template.suggestedRuleIds]
  const selectedRuleSet = new Set(selectedRuleIds)
  return {
    ...createDefaultSyntheticCaseForm(),
    builderMode: options.builderMode || 'case',
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
    selectedRuleFamilyKey: options.selectedRuleFamilyKey || '',
    selectedRuleIds,
    goldenAnswers: template.goldenAnswers
      .filter((answer) => selectedRuleSet.has(answer.qc_point_id))
      .map((answer) => ({
        ...answer,
        id: answer.id || `${template.key}-${answer.qc_point_id}`,
        trigger_facts: [...answer.trigger_facts],
        evidence_keywords: [...answer.evidence_keywords],
      })),
    documents: template.documents.map((document) => ({
      ...document,
      key: createSyntheticDocument(document.document_type).key,
      originalContent: String(document.originalContent ?? document.content ?? ''),
      appliedContent: String(document.appliedContent ?? document.content ?? ''),
    })),
  }
}

function cloneTemplateDocument(document: TestRecordDocumentForm): TestRecordDocumentForm {
  const content = String(document.content || '')
  return {
    ...document,
    key: createSyntheticDocument(document.document_type).key,
    originalContent: String(document.originalContent ?? content),
    appliedContent: String(document.appliedContent ?? content),
  }
}

function uniqueDocumentsFromTemplates(
  templates: SyntheticCaseTemplate[],
): TestRecordDocumentForm[] {
  const seen = new Set<string>()
  const seenSingletonTypes = new Set<string>()
  const singletonDocumentTypes = new Set([
    'admission_record',
    'first_course_record',
    'discharge_record',
  ])
  const documents: TestRecordDocumentForm[] = []
  templates.forEach((template) => {
    template.documents.forEach((document) => {
      if (singletonDocumentTypes.has(document.document_type)) {
        if (seenSingletonTypes.has(document.document_type)) return
        seenSingletonTypes.add(document.document_type)
      }
      const key = `${document.document_type}:${document.title}:${document.content.slice(0, 36)}`
      if (seen.has(key)) return
      seen.add(key)
      documents.push(cloneTemplateDocument(document))
    })
  })
  return documents
}

function createRuleDrivenForm() {
  const normalizedSelection = normalizeRuleIds(selectedRuleSelection.value)
  const selectedRuleSet = new Set(normalizedSelection)
  const families = selectedRuleFamilies.value
  const templates = families
    .map((family) => syntheticCaseTemplates.find((template) => template.key === family.templateKey))
    .filter((template): template is SyntheticCaseTemplate => Boolean(template))
  const seedTemplate = templates[0]
  if (!seedTemplate) return null

  const nextForm = createFormFromTemplate(seedTemplate, {
    builderMode: 'rule',
    selectedRuleIds: normalizedSelection,
    selectedRuleFamilyKey: families[0]?.key || form.value.selectedRuleFamilyKey || '',
  })
  const familyNames = families.map((family) => family.name)
  nextForm.caseTitle = buildRuleDrivenCaseTitle(familyNames, normalizedSelection)
  nextForm.manualIssueText = `按质控点创建：${normalizedSelection.join('、')}。`
  nextForm.documents = uniqueDocumentsFromTemplates(templates)
  nextForm.goldenAnswers = templates
    .flatMap((template) => template.goldenAnswers)
    .filter((answer) => selectedRuleSet.has(answer.qc_point_id))
    .map((answer) => ({
      ...answer,
      id: answer.id || `rule-driven-${answer.qc_point_id}`,
      trigger_facts: [...answer.trigger_facts],
      evidence_keywords: [...answer.evidence_keywords],
    }))
  nextForm.selectedRuleIds = normalizedSelection
  return nextForm
}

function selectRuleFamily(key: string) {
  form.value.selectedRuleFamilyKey = key
}

function toggleRuleSelection(ruleId: string, checked: boolean) {
  if (checked) {
    if (!selectedRuleSelection.value.includes(ruleId)) {
      selectedRuleSelection.value = [...selectedRuleSelection.value, ruleId]
    }
    return
  }
  selectedRuleSelection.value = selectedRuleSelection.value.filter((item) => item !== ruleId)
}

function toggleSelectedRuleFamily() {
  const familyRuleIds = selectedFamilyRuleIds.value
  if (!familyRuleIds.length) return
  if (isSelectedRuleFamilyFullySelected.value) {
    selectedRuleSelection.value = selectedRuleSelection.value.filter(
      (ruleId) => !familyRuleIds.includes(ruleId),
    )
    return
  }
  selectedRuleSelection.value = normalizeRuleIds([...selectedRuleSelection.value, ...familyRuleIds])
}

function generateRuleDrivenCase() {
  if (!selectedRuleFamily.value) {
    message.warning('请先选择一个规则族')
    return
  }
  if (!selectedRuleSelection.value.length) {
    message.warning('请至少勾选一个质控点')
    return
  }
  const nextForm = createRuleDrivenForm()
  if (!nextForm) {
    message.error('当前规则族缺少对应模板，请先补齐模板配置')
    return
  }
  form.value = nextForm
  selectedRuleSelection.value = [...nextForm.selectedRuleIds]
  wizardStep.value = 2
  editorTab.value = 'overview'
  message.success(`已根据 ${selectedRuleSelection.value.length} 条质控点生成病历草稿`)
}

function syntheticCaseGuideTargetClass(target: SyntheticCaseGuideTarget) {
  return {
    'synthetic-case-tour-target': syntheticCaseGuideOpen.value,
    'is-current-tour-target':
      syntheticCaseGuideOpen.value && currentSyntheticCaseGuideStep.value.target === target,
  }
}

function clampSyntheticCaseTourPosition(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function updateSyntheticCaseTourCardPosition() {
  if (!syntheticCaseGuideOpen.value) return
  const target = currentSyntheticCaseGuideStep.value.target
  const element = document.querySelector(`[data-synthetic-guide="${target}"]`)
  if (!element) return
  const rect = element.getBoundingClientRect()
  const gap = 18
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  const cardWidth = Math.min(420, Math.max(280, viewportWidth - 32))
  const cardHeight = 238
  const maxLeft = Math.max(gap, viewportWidth - cardWidth - gap)
  const maxTop = Math.max(gap, viewportHeight - cardHeight - gap)
  let left = rect.right + gap
  let top = rect.top
  if (left + cardWidth > viewportWidth - gap) {
    left = rect.left - cardWidth - gap
  }
  if (left < gap) {
    left = clampSyntheticCaseTourPosition(rect.left, gap, maxLeft)
    top = rect.bottom + gap
    if (top + cardHeight > viewportHeight - gap) {
      top = rect.top - cardHeight - gap
    }
  }
  syntheticCaseTourCardStyle.value = {
    width: `${cardWidth}px`,
    left: `${clampSyntheticCaseTourPosition(left, gap, maxLeft)}px`,
    top: `${clampSyntheticCaseTourPosition(top, gap, maxTop)}px`,
  }
}

function scheduleSyntheticCaseTourCardPositionUpdate() {
  if (syntheticCaseGuidePositionTimer) {
    clearTimeout(syntheticCaseGuidePositionTimer)
  }
  updateSyntheticCaseTourCardPosition()
  syntheticCaseGuidePositionTimer = setTimeout(updateSyntheticCaseTourCardPosition, 320)
}

function applySyntheticCaseGuideStep() {
  const step = currentSyntheticCaseGuideStep.value
  wizardStep.value = step.wizardStep
  if (step.editorTab) {
    editorTab.value = step.editorTab
  }
  void nextTick(() => {
    const element = document.querySelector(`[data-synthetic-guide="${step.target}"]`)
    if (typeof element?.scrollIntoView === 'function') {
      element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
    }
    scheduleSyntheticCaseTourCardPositionUpdate()
  })
}

function hasSeenSyntheticCaseGuide(): boolean {
  try {
    return window.localStorage?.getItem(SYNTHETIC_CASE_GUIDE_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function markSyntheticCaseGuideSeen() {
  try {
    window.localStorage?.setItem(SYNTHETIC_CASE_GUIDE_STORAGE_KEY, 'true')
  } catch {
    // localStorage 可能被浏览器策略禁用，不影响导览关闭。
  }
}

function openSyntheticCaseGuide() {
  syntheticCaseGuideStepIndex.value = 0
  syntheticCaseGuideOpen.value = true
  applySyntheticCaseGuideStep()
}

function closeSyntheticCaseGuide() {
  syntheticCaseGuideOpen.value = false
  syntheticCaseTourCardStyle.value = {}
  markSyntheticCaseGuideSeen()
}

function goToSyntheticCaseGuideStep(index: number) {
  syntheticCaseGuideStepIndex.value = Math.min(
    Math.max(index, 0),
    syntheticCaseGuideSteps.length - 1,
  )
  applySyntheticCaseGuideStep()
}

function goToPreviousSyntheticCaseGuideStep() {
  goToSyntheticCaseGuideStep(syntheticCaseGuideStepIndex.value - 1)
}

function goToNextSyntheticCaseGuideStep() {
  if (isLastSyntheticCaseGuideStep.value) {
    closeSyntheticCaseGuide()
    return
  }
  goToSyntheticCaseGuideStep(syntheticCaseGuideStepIndex.value + 1)
}

function goWizardStep(step: 1 | 2 | 3) {
  if (step > 1 && !form.value.selectedRuleIds.length) {
    message.warning('请先选择质控点并生成测试病历')
    return
  }
  if (step > 1 && isDraftStale.value) {
    message.warning('质控点选择已变更，请重新生成病历草稿')
    return
  }
  wizardStep.value = step
}

function scrollToDocument(key: string) {
  document.getElementById(`synthetic-doc-${key}`)?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

function openDocumentEditor(key: string) {
  editorTab.value = 'documents'
  scrollToDocument(key)
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

function ensureDocumentEditBaseline(document: TestRecordDocumentForm) {
  const content = String(document.content || '')
  if (document.originalContent === undefined) {
    document.originalContent = content
  }
  if (document.appliedContent === undefined) {
    document.appliedContent = content
  }
}

function isDocumentDirty(document: TestRecordDocumentForm): boolean {
  ensureDocumentEditBaseline(document)
  return String(document.content || '') !== String(document.appliedContent || '')
}

function canRestoreDocumentTemplate(document: TestRecordDocumentForm): boolean {
  ensureDocumentEditBaseline(document)
  return String(document.content || '') !== String(document.originalContent || '')
}

function documentEditStatusText(document: TestRecordDocumentForm): string {
  if (isDocumentDirty(document)) {
    return '已修改，保存病历后生效'
  }
  return '已应用到当前草稿'
}

function applyDocumentEdit(document: TestRecordDocumentForm) {
  ensureDocumentEditBaseline(document)
  document.appliedContent = String(document.content || '')
  message.success('文书修改已应用到当前病历草稿')
}

function restoreDocumentTemplate(document: TestRecordDocumentForm) {
  ensureDocumentEditBaseline(document)
  document.content = String(document.originalContent || '')
  document.appliedContent = String(document.originalContent || '')
  message.success('已还原为模板文书内容')
}

function validateForm(): boolean {
  if (form.value.builderMode === 'rule') {
    if (!form.value.selectedRuleFamilyKey) {
      message.warning('请先选择规则族')
      return false
    }
    if (!form.value.selectedRuleIds.length) {
      message.warning('请先按质控点生成病历草稿')
      return false
    }
    if (isDraftStale.value) {
      message.warning('质控点选择已变更，请重新生成病历草稿')
      return false
    }
  }
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
    let createdJobId = ''
    if (runAfterSave) {
      const createdItem = result.data.item
      const sampleItemId = String(createdItem?.id || '').trim()
      const instituteId = String(createdItem?.matched_institute_id || '').trim()
      const patientId = String(createdItem?.matched_patient_id || '').trim()
      const matchedVisitId = String(createdItem?.matched_visit_id || '').trim()
      if (!poolId || !sampleItemId || !instituteId || !patientId || !matchedVisitId) {
        message.warning('测试病历已保存，但病例三坐标尚未完整生成，未发起验证任务')
      } else {
        const runResult = await runManualSamplePool(
          poolId,
          buildSyntheticCaseRunPayload(form.value, {
            sampleItemId,
            instituteId,
            patientId,
            visitId: matchedVisitId,
          }),
          { timeout: 90000 },
        )
        if (!runResult.success || !runResult.data) {
          message.warning(runResult.message || '测试病历已保存，但验证任务创建失败')
        } else {
          createdJobId = runResult.data.job_id
          message.success('测试病历已保存，验证任务已创建')
        }
      }
    } else {
      message.success(`测试病历已创建：${result.data.mr_no || visitId}`)
    }
    await router.push({
      name: 'WorkstationV4CustomerSampleValidation',
      query: poolId
        ? {
            poolId,
            recordId: visitId,
            ...(createdJobId ? { jobId: createdJobId } : {}),
          }
        : undefined,
    })
  } finally {
    saving.value = false
    savingAndRunning.value = false
  }
}

initializeRuleSelectionFromRoute()

onMounted(() => {
  window.addEventListener('resize', updateSyntheticCaseTourCardPosition)
  window.addEventListener('scroll', updateSyntheticCaseTourCardPosition, true)
  void loadLuxian0609RuleCatalog()
  if (!hasSeenSyntheticCaseGuide()) {
    openSyntheticCaseGuide()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', updateSyntheticCaseTourCardPosition)
  window.removeEventListener('scroll', updateSyntheticCaseTourCardPosition, true)
  if (syntheticCaseGuidePositionTimer) {
    clearTimeout(syntheticCaseGuidePositionTimer)
    syntheticCaseGuidePositionTimer = null
  }
})
</script>

<style scoped src="../styles/synthetic-case.css"></style>
