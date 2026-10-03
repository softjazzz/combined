<template>
  <a-drawer
    :open="open"
    :width="drawerWidth"
    :closable="false"
    :body-style="{ padding: 0 }"
    root-class-name="business-agent-drawer"
    @close="open = false"
  >
    <div class="business-agent">
      <header class="ba-head">
        <span class="ba-avatar ba-avatar--lg" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4z" />
            <path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
          </svg>
        </span>
        <div class="ba-head__copy">
          <strong class="ba-head__title">{{
            context.view === 'doctor' ? '病历助手' : '质控分析助手'
          }}</strong>
          <span class="ba-head__sub"><i class="ba-dot" />{{ contextLabel }} · 只读</span>
        </div>
        <div
          v-if="allowCaseSelection && caseOptions.length && scopeOptions.length"
          class="ba-segmented"
        >
          <button
            type="button"
            :class="{ 'is-active': activeView === 'doctor' }"
            @click="selectedView = 'doctor'"
          >
            病例问题
          </button>
          <button
            type="button"
            :class="{ 'is-active': activeView === 'manager' }"
            @click="selectedView = 'manager'"
          >
            科室问数
          </button>
        </div>
        <button
          type="button"
          class="ba-icon-btn"
          aria-label="新建会话"
          title="新建会话"
          @click="reset(context)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
          </svg>
        </button>
        <button type="button" class="ba-icon-btn" aria-label="关闭" @click="open = false">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </header>

      <section
        v-if="(allowCaseSelection && context.view === 'doctor') || context.view === 'manager'"
        class="ba-scope"
      >
        <template v-if="allowCaseSelection && context.view === 'doctor'">
          <span class="ba-scope__label">授权病例</span>
          <a-select
            v-model:value="selectedCase"
            class="ba-scope__select ba-scope__select--wide"
            :options="caseOptions"
            :loading="accessLoading"
            placeholder="选择已授权病例"
            aria-label="授权病例"
            data-testid="business-agent-case-scope"
          />
          <p v-if="!caseOptions.length && !accessLoading" class="ba-muted">
            当前入口没有可选择的授权病例，请从已授权病历详情进入或核对访问范围。
          </p>
        </template>
        <template v-if="context.view === 'manager'">
          <span class="ba-scope__label">管理问数范围</span>
          <a-select
            v-model:value="selectedScope"
            class="ba-scope__select ba-scope__select--wide"
            :options="scopeOptions"
            :loading="accessLoading"
            placeholder="选择已授权科室"
            aria-label="机构/科室"
            data-testid="business-agent-manager-scope"
          />
          <a-select
            v-model:value="carePhase"
            class="ba-scope__select"
            :options="carePhaseOptions"
            aria-label="病例范围"
          />
          <a-range-picker
            v-model:value="dates"
            class="ba-scope__select"
            value-format="YYYY-MM-DD"
            aria-label="质控完成日期"
            :placeholder="['质控完成起', '质控完成止']"
          />
        </template>
      </section>
      <a-alert
        v-if="accessError"
        class="ba-alert"
        type="warning"
        :message="accessError"
        show-icon
      />

      <section
        ref="turnsElement"
        class="ba-thread"
        aria-live="polite"
        data-testid="business-agent-turns"
      >
        <div v-if="!turns.length" class="ba-welcome">
          <span class="ba-avatar ba-avatar--xl" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
              <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4z" />
              <path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
            </svg>
          </span>
          <h2 class="ba-welcome__title">
            {{ context.view === 'doctor' ? '你好，我是病历助手' : '你好，我是质控分析助手' }}
          </h2>
          <p class="ba-welcome__lead">
            {{
              context.view === 'doctor'
                ? '我会读取这份病历最近一次的正式质控结果，帮你看懂问题、找到原文和规范，再协助你修改。'
                : '我会沿用正式统计口径回答指标问题，可以下钻到病例、比较期间，或起草质量分析报告。'
            }}
          </p>
          <p class="ba-welcome__note" data-testid="business-agent-readonly-notice">
            支持查询与解释、查看提醒与整改记录；异议反馈需本人填写理由并提交，不改变质控结论。
          </p>
          <div v-if="canOpenProfile" class="ba-welcome__extra">
            <a-button
              type="link"
              data-testid="business-agent-open-profile"
              @click="openProfilePanel"
            >
              打开本病例画像面板
            </a-button>
            <span class="ba-muted">打开面板不会自动分析；是否运行画像分析由您在面板中决定。</span>
          </div>
        </div>
        <template v-else>
          <p class="ba-sr-only" data-testid="business-agent-readonly-notice">
            支持查询与解释、查看提醒与整改记录；异议反馈需本人填写理由并提交，不改变质控结论。
          </p>
          <div v-if="canOpenProfile" class="ba-inline-tools">
            <a-button
              type="link"
              size="small"
              data-testid="business-agent-open-profile"
              @click="openProfilePanel"
            >
              打开本病例画像面板
            </a-button>
            <span class="ba-muted">打开面板不会自动分析</span>
          </div>
        </template>
        <a-button
          v-if="summaryRunId"
          class="ba-return"
          size="small"
          data-testid="business-agent-return-summary"
          @click="returnToSummary"
        >
          返回同一汇总（当时结果，未刷新）
        </a-button>
        <article
          v-for="(turn, turnIndex) in turns"
          :key="turn.run_id"
          :data-run-id="turn.run_id"
          tabindex="-1"
          class="ba-turn"
        >
          <div class="ba-msg ba-msg--user">
            <p class="ba-bubble ba-bubble--user">
              {{ turn.question }}
            </p>
          </div>
          <div class="ba-msg ba-msg--assistant">
            <span class="ba-avatar" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4z" />
              </svg>
            </span>
            <div class="ba-msg__body">
              <span class="ba-steps" :class="`ba-steps--${turn.status}`">
                <svg
                  v-if="turn.status === 'completed'"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.6"
                >
                  <path d="M5 12l5 5L20 7" />
                </svg>
                {{ turnSummary(turn) }}
              </span>
              <div class="ba-bubble ba-bubble--assistant">
                <p class="business-agent__answer">
                  {{ turn.answer || turn.error || '本轮未完成，可重新查询。' }}
                </p>
                <div
                  v-for="(page, pageIndex) in turn.result_pages || []"
                  :key="pageIndex"
                  class="ba-page"
                  data-testid="business-agent-result-page"
                >
                  <p>
                    读取范围：{{
                      page.statuses.length ? page.statuses.map(statusLabel).join('、') : '全部状态'
                    }}
                    · 第 {{ page.page }} 页；本页 {{ page.returned }} 条，匹配共
                    {{ page.matched_total }} 条，保存结果共 {{ page.total }} 条。
                  </p>
                  <p class="ba-chips">
                    <span
                      v-for="[status, count] in Object.entries(page.status_counts)"
                      :key="status"
                      class="mq-status"
                      :class="statusTone(status)"
                      >{{ statusLabel(status) }} {{ count }} 条</span
                    >
                  </p>
                  <p v-if="page.has_more" class="ba-muted">此范围还有后续页，可继续查询下一页。</p>
                </div>
                <p v-if="turn.reference_scope === 'prior_turns'" class="ba-muted">
                  本轮沿用此前读取的来源，未刷新业务结果。
                </p>
                <p
                  v-if="turn.references.some((reference) => reference.kind === 'guideline')"
                  class="ba-muted"
                  data-testid="business-agent-retrieval-notice"
                >
                  规范检索资料：以下命中或读取的资料不代表均支持上方回答，请核对条款及适用范围。
                </p>
                <div
                  v-for="(reference, index) in turn.references"
                  :key="reference.id"
                  class="ba-card"
                  :class="`ba-card--${reference.kind}`"
                >
                  <div class="ba-card__head">
                    <span class="ba-card__index">{{ reference.position || index + 1 }}</span>
                    <strong class="ba-card__title">{{ reference.title }}</strong>
                    <span
                      v-if="reference.status && reference.kind !== 'action'"
                      class="mq-status"
                      :class="statusTone(reference.status)"
                      >{{ statusLabel(reference.status) }}</span
                    >
                  </div>
                  <p
                    v-if="reference.kind === 'guideline'"
                    class="ba-muted"
                    data-testid="business-agent-guideline-candidate"
                  >
                    检索资料 · 待核对适用性
                  </p>
                  <div v-if="reference.conclusion || reference.suggestion" class="ba-card__body">
                    <p v-if="reference.conclusion">
                      {{ reference.conclusion }}
                    </p>
                    <p v-if="reference.suggestion" class="ba-card__suggestion">
                      建议：{{ reference.suggestion }}
                    </p>
                  </div>
                  <p v-if="reference.locator || reference.rule_id" class="ba-card__meta">
                    <span v-if="reference.locator">{{ reference.locator }}</span>
                    <span v-if="reference.rule_id" class="ba-mono"
                      >规则编号：{{ reference.rule_id }}</span
                    >
                  </p>
                  <template v-if="reference.kind === 'action'">
                    <p class="ba-block" data-testid="business-agent-action-text">
                      {{ actionView(reference).text }}
                    </p>
                    <div class="ba-card__confirm">
                      <a-button
                        v-if="canConfirm(actionView(reference))"
                        type="primary"
                        :loading="actionBusy === reference.id"
                        :disabled="!!actionBusy"
                        data-testid="business-agent-action-confirm"
                        @click="confirmAction(reference)"
                      >
                        确认执行
                      </a-button>
                      <a-button
                        v-else-if="actionView(reference).status !== 'previewed'"
                        :loading="actionBusy === reference.id"
                        :disabled="!!actionBusy"
                        data-testid="business-agent-action-refresh"
                        @click="refreshAction(reference)"
                      >
                        刷新任务进度
                      </a-button>
                    </div>
                    <p class="ba-muted">
                      助手不会自行执行；确认后由正式质控任务服务创建任务，停止对话不会取消已创建任务。
                    </p>
                  </template>
                  <template v-if="reference.kind === 'draft'">
                    <p class="ba-block ba-block--draft" data-testid="business-agent-draft-text">
                      {{ reference.text }}
                    </p>
                    <div class="ba-card__actions">
                      <a-button
                        size="small"
                        :disabled="!reference.text"
                        data-testid="business-agent-draft-copy"
                        @click="copyDraft(reference)"
                      >
                        复制参考草稿
                      </a-button>
                      <span
                        v-if="copiedDraftId === reference.id"
                        class="ba-muted"
                        data-testid="business-agent-draft-copied"
                      >
                        已复制；复制不等于整改完成，请核对原文后在病历系统中书写。
                      </span>
                    </div>
                  </template>
                  <p
                    v-if="reference.kind === 'saved_result' && !linkedRule(reference)"
                    class="ba-muted"
                  >
                    {{
                      reference.rule_id
                        ? '尚未读取对应规则，查询将发起新一轮问答。'
                        : '保存结果未提供规则编号，暂无法关联规则详情。'
                    }}
                  </p>
                  <div class="ba-card__actions">
                    <a-button
                      type="link"
                      size="small"
                      class="ba-link--primary"
                      @click="openReference(reference.id)"
                    >
                      查看{{
                        reference.kind === 'guideline'
                          ? '规范原文'
                          : isRuleValidation(reference)
                            ? '验收记录'
                            : reference.kind === 'rule'
                              ? '规则详情'
                              : reference.kind === 'draft'
                                ? '最新校验的草稿'
                                : reference.kind === 'action'
                                  ? '操作最新状态'
                                  : '依据与详情'
                      }}
                    </a-button>
                    <template v-if="reference.kind === 'saved_result'">
                      <a-button
                        v-if="linkedRule(reference)"
                        type="link"
                        size="small"
                        @click="openReference(linkedRule(reference)!.id)"
                      >
                        查看对应规则
                      </a-button>
                      <a-button
                        v-else-if="reference.rule_id"
                        type="link"
                        size="small"
                        :disabled="loading || !canQuery"
                        @click="queryRule(reference)"
                      >
                        查询这条规则
                      </a-button>
                      <a-button
                        type="link"
                        size="small"
                        :disabled="loading || !canQuery"
                        @click="explainReference(reference)"
                      >
                        解释这条
                      </a-button>
                      <a-button
                        v-if="reference.status === 'non_compliant' && activeView === 'doctor'"
                        type="link"
                        size="small"
                        :disabled="loading || !canQuery"
                        data-testid="business-agent-draft-request"
                        @click="requestDraft(reference)"
                      >
                        生成参考补充文字
                      </a-button>
                      <a-button
                        type="link"
                        size="small"
                        class="ba-link--muted"
                        :disabled="!sessionId || feedbackSubmitting"
                        data-testid="business-agent-feedback-open"
                        @click="openFeedback(reference.id)"
                      >
                        提交异议反馈
                      </a-button>
                    </template>
                    <a-button
                      v-if="reference.kind === 'record'"
                      type="link"
                      size="small"
                      :disabled="loading || !canQuery"
                      @click="explainReference(reference, turn.run_id)"
                    >
                      查看病例问题
                    </a-button>
                  </div>
                </div>
              </div>
              <div
                v-if="turnIndex === turns.length - 1 && !loading && followups(turn).length"
                class="ba-followups"
                data-testid="business-agent-followups"
              >
                <button
                  v-for="item in followups(turn)"
                  :key="item.label"
                  type="button"
                  class="ba-chip"
                  :disabled="!canQuery"
                  @click="item.run()"
                >
                  {{ item.label }}
                </button>
              </div>
            </div>
          </div>
        </article>
        <div v-if="loading" class="ba-msg ba-msg--assistant" role="status">
          <span class="ba-avatar ba-avatar--pulse" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4z" />
            </svg>
          </span>
          <div class="ba-bubble ba-bubble--thinking">
            <span>正在读取结果和依据</span>
            <span class="ba-typing" aria-hidden="true"><i /><i /><i /></span>
          </div>
        </div>
      </section>

      <footer class="ba-composer">
        <a-alert v-if="error" type="warning" :message="error" show-icon />
        <div class="ba-prompts">
          <button
            v-for="prompt in prompts"
            :key="prompt"
            type="button"
            class="ba-chip"
            :disabled="loading || !canQuery"
            @click="draft = prompt"
          >
            {{ prompt }}
          </button>
        </div>
        <div class="ba-input">
          <a-textarea
            v-model:value="draft"
            class="ba-input__field"
            :bordered="false"
            :disabled="loading || !canQuery"
            :auto-size="{ minRows: 1, maxRows: 5 }"
            :placeholder="
              context.view === 'doctor'
                ? '问我这份病历的问题、依据，或让我帮你写补充…'
                : '问指标、比较期间、下钻病例，或让我写报告…'
            "
            aria-label="向助手提问"
            @keydown.enter.exact.prevent="submit"
          />
          <button v-if="loading" type="button" class="ba-stop" @click="stop">
            <i aria-hidden="true" />停止
          </button>
          <button
            v-else
            type="button"
            class="ba-send"
            :disabled="loading || !canQuery || !draft.trim()"
            @click="submit"
          >
            发送
          </button>
        </div>
        <p class="ba-footnote">
          {{
            context.view === 'doctor'
              ? '回答基于正式保存结果与规范原文，结论以质控系统为准'
              : '数值来自正式统计并可回查，不含因果推断'
          }}
        </p>
      </footer>
    </div>
    <a-modal
      :open="feedbackOpen"
      title="质控异议反馈"
      wrap-class-name="mq-modal"
      :footer="null"
      @cancel="closeFeedback"
    >
      <p v-if="feedbackLoading">正在核对反馈对象与已提交记录…</p>
      <template v-if="feedbackPreview">
        <p data-testid="business-agent-feedback-target">
          机构 {{ feedbackPreview.target.institute_id }} · 患者
          {{ feedbackPreview.target.patient_id }} · 住院 {{ feedbackPreview.target.visit_id }}
        </p>
        <p>{{ feedbackPreview.target.title }} · {{ feedbackPreview.target.rule_id }}</p>
        <p class="business-agent__muted">提交后登记异议供复核，不改变当前质控状态。</p>
        <template v-if="feedbackPreview.data">
          <a-alert type="success" message="异议反馈已提交" show-icon />
          <p>{{ feedbackPreview.data.comment }}</p>
          <p class="business-agent__muted">提交时间：{{ feedbackPreview.data.created_at }}</p>
        </template>
        <template v-else>
          <label class="mq-field"
            >异议理由（必填，最多500字）
            <a-textarea
              v-model:value="feedbackComment"
              :maxlength="500"
              :disabled="feedbackSubmitting"
              :auto-size="{ minRows: 3, maxRows: 6 }"
              data-testid="business-agent-feedback-comment"
            />
          </label>
          <a-button
            type="primary"
            :loading="feedbackSubmitting"
            :disabled="
              feedbackSubmitting || !feedbackComment.trim() || feedbackComment.trim().length > 500
            "
            data-testid="business-agent-feedback-submit"
            @click="submitFeedback"
          >
            {{ feedbackError ? '重试提交' : '确认提交异议' }}
          </a-button>
        </template>
      </template>
      <a-alert v-if="feedbackError" type="warning" :message="feedbackError" show-icon />
      <a-button
        v-if="!feedbackPreview && !feedbackLoading"
        @click="openFeedback(feedbackReferenceId)"
      >
        重新核对反馈对象
      </a-button>
    </a-modal>
    <a-modal
      v-model:open="referenceOpen"
      wrap-class-name="mq-modal"
      :title="selectedReference?.title || '依据详情'"
      :footer="null"
      :width="720"
    >
      <p v-if="referenceLoading">正在读取原文…</p>
      <a-alert v-else-if="referenceError" type="warning" :message="referenceError" />
      <template v-else-if="selectedReference">
        <p v-if="isRuleValidation(selectedReference)" class="business-agent__muted">
          已保存的规则验收摘要；不是当前规则目录口径，也不代表当前部署规则已完成验收。
        </p>
        <p v-else-if="selectedReference.kind === 'rule'" class="business-agent__muted">
          当前规则目录口径；历史执行版本与规范原文需另行核对。
        </p>
        <a-button
          v-if="ruleValidationPath"
          type="link"
          :href="ruleValidationPath"
          data-testid="business-agent-rule-validation-link"
        >
          打开规则验收记录
        </a-button>
        <template v-if="selectedReference.evidence?.length">
          <p>{{ selectedReference.conclusion }}</p>
          <p v-if="selectedReference.suggestion">建议：{{ selectedReference.suggestion }}</p>
          <article
            v-for="(evidence, index) in selectedReference.evidence"
            :key="index"
            class="mq-inset business-agent__reference"
          >
            <small v-if="evidence.record_time">{{ evidence.record_time }}</small>
            <p class="business-agent__answer">
              {{ evidence.evidence_excerpt || '该证据未提供摘录。' }}
            </p>
            <a-button type="link" @click="openEvidenceDocument(selectedReference.id, index)">
              查看对应文书原文
            </a-button>
          </article>
        </template>
        <template v-else>
          <p>{{ selectedReference.locator }}</p>
          <pre class="business-agent__answer">{{
            selectedReference.text ||
            selectedReference.conclusion ||
            '当前来源未提供原文，请核对材料范围。'
          }}</pre>
        </template>
      </template>
    </a-modal>
    <a-modal
      v-model:open="documentOpen"
      wrap-class-name="mq-modal"
      :title="evidenceDocument?.title || '对应文书原文'"
      :footer="null"
      :width="800"
    >
      <p v-if="documentLoading">正在读取对应文书…</p>
      <a-alert v-else-if="documentError" type="warning" :message="documentError" />
      <template v-else-if="evidenceDocument">
        <a-alert
          :type="evidenceDocument.state === 'located' ? 'info' : 'warning'"
          :message="evidenceDocument.note"
        />
        <p class="business-agent__muted">
          当前文书 · {{ evidenceDocument.record_time || '未提供记录时间' }}
        </p>
        <p>保存结果中的摘录：</p>
        <p class="mq-inset business-agent__answer">
          {{ evidenceDocument.quote || '未提供摘录' }}
        </p>
        <pre
          v-if="evidenceDocument.content"
          class="business-agent__answer business-agent__document"
          data-testid="business-agent-document">{{ documentSegments.before }}<mark
v-if="documentSegments.quote"
                                                                                                                                              data-testid="business-agent-document-location"
        >{{ documentSegments.quote }}</mark>{{ documentSegments.after }}</pre>
      </template>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  businessAgentApi,
  type BusinessAgentContext,
  type BusinessAgentReference,
  type BusinessAgentTurn,
  type BusinessAgentAccess,
  type BusinessEvidenceDocument,
  type BusinessFeedbackPreview,
} from '@/api/businessAgent'
import { useBusinessAgent } from '../composables/useBusinessAgent'
import {
  followupIntents,
  statusTone,
  turnSummary,
  type FollowupIntent,
} from './businessAgentPresentation'

const open = defineModel<boolean>('open', { default: false })
const props = defineProps<{
  userContext?: BusinessAgentContext
  allowCaseSelection?: boolean
  // 宿主声明可打开的同病例辅助面板；未声明时不显示入口。
  panels?: 'profile'[]
}>()
const emitPanel = defineEmits<{
  'open-panel': [
    payload: { panel: 'profile'; institute_id: string; patient_id: string; visit_id: string },
  ]
}>()
const canOpenProfile = computed(
  () =>
    !!props.panels?.includes('profile') &&
    activeView.value === 'doctor' &&
    !!context.value.institute_id &&
    !!context.value.patient_id &&
    !!context.value.visit_id,
)
function openProfilePanel() {
  const current = context.value
  if (!canOpenProfile.value || !current.institute_id || !current.patient_id || !current.visit_id)
    return
  emitPanel('open-panel', {
    panel: 'profile',
    institute_id: current.institute_id,
    patient_id: current.patient_id,
    visit_id: current.visit_id,
  })
}
const accessScope = ref<BusinessAgentAccess>()
const accessLoading = ref(false)
const accessError = ref('')
const selectedScope = ref('')
const selectedCase = ref('')
const selectedView = ref<'doctor' | 'manager'>('manager')
const activeView = computed(() =>
  props.allowCaseSelection ? selectedView.value : props.userContext?.view || 'manager',
)
const caseOptions = computed(() =>
  (accessScope.value?.doctor_cases || []).map((record) => ({
    value: JSON.stringify([record.institute_id, record.patient_id, record.visit_id]),
    label: `住院 ${record.visit_id} · 患者 ${record.patient_id} · ${record.institute_id}`,
  })),
)
const doctorCase = computed(() =>
  accessScope.value?.doctor_cases?.find(
    (record) =>
      JSON.stringify([record.institute_id, record.patient_id, record.visit_id]) ===
      selectedCase.value,
  ),
)
const scopeOptions = computed(() =>
  (accessScope.value?.manager_scopes || []).map((scope) => ({
    value: JSON.stringify([scope.institute_id, scope.department]),
    label: `${scope.department} · ${scope.institute_id}`,
  })),
)
const managerScope = computed(() =>
  accessScope.value?.manager_scopes.find(
    (scope) => JSON.stringify([scope.institute_id, scope.department]) === selectedScope.value,
  ),
)
let accessGeneration = 0
watch(
  open,
  async (visible) => {
    const epoch = ++accessGeneration
    accessScope.value = undefined
    selectedScope.value = ''
    selectedCase.value = ''
    accessError.value = ''
    accessLoading.value = false
    if (!visible) return
    accessLoading.value = true
    try {
      const result = await businessAgentApi.access()
      if (epoch !== accessGeneration) return
      accessScope.value = result
      if (props.allowCaseSelection)
        selectedView.value = result.manager_scopes.length ? 'manager' : 'doctor'
      const requested = result.manager_scopes.find(
        (scope) =>
          scope.institute_id === props.userContext?.institute_id &&
          scope.department === props.userContext?.department,
      )
      const initial =
        requested || (result.manager_scopes.length === 1 ? result.manager_scopes[0] : undefined)
      if (initial) selectedScope.value = JSON.stringify([initial.institute_id, initial.department])
      if (
        props.allowCaseSelection
          ? !result.doctor_case_count && !result.manager_scopes.length
          : props.userContext?.view === 'doctor'
            ? !result.doctor_case_count
            : !result.manager_scopes.length
      )
        accessError.value = '当前账号没有此入口的明确授权范围。'
    } catch {
      if (epoch === accessGeneration) accessError.value = '访问范围读取失败，请确认账号授权配置。'
    } finally {
      if (epoch === accessGeneration) accessLoading.value = false
    }
  },
  { immediate: true },
)
const carePhase = ref<'inpatient' | 'discharged'>('discharged')
const dates = ref<[string, string]>()
const carePhaseOptions = [
  { value: 'inpatient', label: '在院' },
  { value: 'discharged', label: '已出院' },
]
const context = computed<BusinessAgentContext>(() =>
  activeView.value === 'doctor'
    ? props.allowCaseSelection
      ? { view: 'doctor', ...doctorCase.value }
      : props.userContext || { view: 'doctor' }
    : {
        view: 'manager',
        institute_id: managerScope.value?.institute_id,
        department: managerScope.value?.department,
        care_phase: carePhase.value,
        completed_from: dates.value ? `${dates.value[0]}T00:00:00+08:00` : undefined,
        completed_to: dates.value ? `${dates.value[1]}T23:59:59+08:00` : undefined,
      },
)
const canQuery = computed(
  () =>
    !!accessScope.value &&
    !accessError.value &&
    (context.value.view === 'doctor'
      ? !!accessScope.value.doctor_case_count &&
        !!context.value.institute_id &&
        !!context.value.patient_id &&
        !!context.value.visit_id &&
        (!props.allowCaseSelection || !!doctorCase.value)
      : !!managerScope.value && !!dates.value?.[0] && !!dates.value?.[1]),
)
const contextLabel = computed(() =>
  context.value.view === 'doctor'
    ? `${context.value.patient_name || '当前患者'} · 住院 ${context.value.visit_id || '未选定'}`
    : `${context.value.department || '当前账号可见科室'} · 按质控完成时间统计`,
)
const prompts = computed(() =>
  context.value.view === 'doctor'
    ? ['这份病历有哪些已保存的质控问题？', '第二条为什么不合规？', '这条规则的要求来自哪里？']
    : ['当前范围哪些质控问题最多？', '列出这些问题对应的病例', '查询规则的当前启用状态'],
)
const draft = ref('')
// 窄窗口不超出视口，避免内容被裁切。
const drawerWidth = 'min(600px, 100vw)'
function followups(turn: BusinessAgentTurn) {
  return followupIntents(turn, context.value.view).map((intent: FollowupIntent) => ({
    label: intent.label,
    run: () =>
      intent.kind === 'ask'
        ? send(intent.message, context.value)
        : intent.kind === 'draft'
          ? requestDraft(intent.reference)
          : intent.kind === 'rule'
            ? queryRule(intent.reference)
            : explainReference(intent.reference),
  }))
}
const { sessionId, turns, loading, error, activate, send, stop, reset } = useBusinessAgent()
const feedbackOpen = ref(false)
const feedbackLoading = ref(false)
const feedbackSubmitting = ref(false)
const feedbackReferenceId = ref('')
const feedbackPreview = ref<BusinessFeedbackPreview>()
const feedbackComment = ref('')
const feedbackError = ref('')
let feedbackGeneration = 0
let feedbackController: AbortController | undefined
let feedbackRequest: { request_id: string; comment: string } | undefined
function closeFeedback() {
  feedbackGeneration += 1
  feedbackController?.abort()
  feedbackController = undefined
  feedbackOpen.value = false
  feedbackLoading.value = false
  feedbackSubmitting.value = false
  feedbackPreview.value = undefined
  feedbackComment.value = ''
  feedbackError.value = ''
  feedbackRequest = undefined
}
watch([context, sessionId, open], closeFeedback, { deep: true, flush: 'sync' })
onBeforeUnmount(closeFeedback)
function feedbackFailure(cause: unknown) {
  const status = (cause as { response?: { status?: number } })?.response?.status
  if (status === 403 || status === 404) return '反馈对象或授权已失效，请重新读取该问题。'
  if (status === 409) return '结果版本或已提交反馈发生变化，请关闭后重新核对。'
  if (status === 503) return '反馈服务暂不可用，未确认提交成功，请稍后重试。'
  return '未确认反馈提交结果，请重试核对；重试不会重复登记同一反馈。'
}
async function openFeedback(referenceId: string) {
  if (!sessionId.value || feedbackSubmitting.value) return
  closeFeedback()
  const epoch = feedbackGeneration
  feedbackReferenceId.value = referenceId
  feedbackOpen.value = true
  feedbackLoading.value = true
  feedbackController = new AbortController()
  try {
    const result = await businessAgentApi.feedback(
      sessionId.value,
      referenceId,
      feedbackController.signal,
    )
    if (epoch === feedbackGeneration) feedbackPreview.value = result
  } catch (cause) {
    if (epoch === feedbackGeneration) feedbackError.value = feedbackFailure(cause)
  } finally {
    if (epoch === feedbackGeneration) feedbackLoading.value = false
  }
}
async function submitFeedback() {
  const preview = feedbackPreview.value
  const comment = feedbackComment.value.trim()
  if (!preview || preview.data || feedbackSubmitting.value || !comment || comment.length > 500)
    return
  const epoch = feedbackGeneration
  // 网络失败重试沿用同一请求标识，修改理由才生成新标识；最终去重由服务端负责。
  if (!feedbackRequest || feedbackRequest.comment !== comment)
    feedbackRequest = { request_id: crypto.randomUUID(), comment }
  feedbackSubmitting.value = true
  feedbackError.value = ''
  feedbackController = new AbortController()
  try {
    const result = await businessAgentApi.submitFeedback(
      sessionId.value,
      {
        ...feedbackRequest,
        reference_id: preview.target.reference_id,
      },
      feedbackController.signal,
    )
    if (epoch === feedbackGeneration) feedbackPreview.value = { ...preview, data: result }
  } catch (cause) {
    if (epoch === feedbackGeneration) feedbackError.value = feedbackFailure(cause)
  } finally {
    if (epoch === feedbackGeneration) feedbackSubmitting.value = false
  }
}
watch(
  context,
  (value) => {
    draft.value = ''
    void activate(value)
  },
  { immediate: true, deep: true },
)
async function submit() {
  if (!canQuery.value) return
  const message = draft.value
  draft.value = ''
  const candidates =
    turns.value
      .at(-1)
      ?.references.filter(
        (reference) => reference.kind === 'saved_result' && reference.position === 2,
      ) || []
  if (message === '第二条为什么不合规？' && candidates.length > 1) {
    error.value = '存在多个第二条，请点击具体问题卡片的“解释这条”。'
    return
  }
  error.value = ''
  // 固定快捷追问绑定页面可见的稳定问题，不要求模型再次排序。
  if (message === '第二条为什么不合规？' && candidates.length === 1)
    await send(message, context.value, candidates[0].id)
  else await send(message, context.value)
}
const turnsElement = ref<HTMLElement>()
const summaryRunId = ref('')
watch([context, sessionId], () => {
  summaryRunId.value = ''
})
watch(
  turns,
  (value) => {
    if (!value.some((turn) => turn.run_id === summaryRunId.value)) summaryRunId.value = ''
  },
  { deep: true },
)
function returnToSummary() {
  const target = Array.from(
    turnsElement.value?.querySelectorAll<HTMLElement>('[data-run-id]') || [],
  ).find((element) => element.dataset.runId === summaryRunId.value)
  target?.scrollIntoView({ block: 'start' })
  target?.focus({ preventScroll: true })
}
// 操作卡的最新状态只来自确认/回读接口，不改写会话历史中的原卡片。
const actionUpdates = ref<Record<string, BusinessAgentReference>>({})
const actionBusy = ref('')
function actionView(reference: BusinessAgentReference) {
  return actionUpdates.value[reference.id] || reference
}
function canConfirm(reference: BusinessAgentReference) {
  return (
    reference.status === 'previewed' &&
    reference.allowed === true &&
    !!reference.confirmation_hash &&
    !!reference.expires_at &&
    Date.parse(reference.expires_at) > Date.now()
  )
}
watch(sessionId, () => {
  actionUpdates.value = {}
  actionBusy.value = ''
})
async function confirmAction(reference: BusinessAgentReference) {
  const current = actionView(reference)
  const owner = sessionId.value
  if (!owner || !current.action_id || !current.confirmation_hash) return
  actionBusy.value = reference.id
  error.value = ''
  try {
    const updated = await businessAgentApi.confirmAction(
      owner,
      current.action_id,
      current.confirmation_hash,
    )
    // 切换会话后迟到的响应不写入新会话。
    if (owner === sessionId.value)
      actionUpdates.value = { ...actionUpdates.value, [reference.id]: updated }
  } catch (cause) {
    if (owner !== sessionId.value) return
    const status = (cause as { response?: { status?: number } })?.response?.status
    error.value =
      status === 409
        ? '授权、范围、规则或材料状态已变化，预览已失效；请重新发起预览。本次未提交任务。'
        : '确认请求未完成，未能确认是否已提交；请点击刷新查看该操作状态，不要重复发起新预览。'
  } finally {
    actionBusy.value = ''
  }
}
async function refreshAction(reference: BusinessAgentReference) {
  const current = actionView(reference)
  const owner = sessionId.value
  if (!owner || !current.action_id) return
  actionBusy.value = reference.id
  error.value = ''
  try {
    const updated = await businessAgentApi.readAction(owner, current.action_id)
    if (owner === sessionId.value)
      actionUpdates.value = { ...actionUpdates.value, [reference.id]: updated }
  } catch {
    if (owner !== sessionId.value) return
    error.value = '任务进度读取失败；任务状态以正式任务列表为准。'
  } finally {
    actionBusy.value = ''
  }
}
const copiedDraftId = ref('')
async function copyDraft(reference: BusinessAgentReference) {
  if (!reference.text) return
  try {
    await navigator.clipboard.writeText(reference.text)
    copiedDraftId.value = reference.id
  } catch {
    error.value = '复制失败，请手动选择草稿文字复制'
  }
}
async function requestDraft(reference: BusinessAgentReference) {
  if (!canQuery.value) return
  await send(
    `请为“${reference.title}”起草一段参考补充文字：只复述保存证据中的事实，无法证实的内容列为待医生补充`,
    context.value,
    reference.id,
  )
}
async function queryRule(reference: BusinessAgentReference) {
  if (!canQuery.value || !reference.rule_id) return
  await send(
    `查询规则 ${reference.rule_id} 的当前目录口径、启用状态与依据`,
    context.value,
    reference.id,
  )
}
function linkedRule(reference: BusinessAgentReference) {
  if (!reference.rule_id) return undefined
  return turns.value
    .flatMap((turn) => turn.references)
    .find(
      (item) =>
        item.kind === 'rule' && item.rule_id === reference.rule_id && !isRuleValidation(item),
    )
}
// 验收记录沿用 rule 来源类型，以稳定标识区分，不能当作当前目录规则详情。
function isRuleValidation(reference: BusinessAgentReference) {
  return (
    reference.kind === 'rule' &&
    !!reference.rule_id &&
    reference.id === `rule-validation:${reference.rule_id}`
  )
}
async function explainReference(reference: BusinessAgentReference, sourceRunId?: string) {
  if (!canQuery.value) return
  error.value = ''
  if (reference.kind === 'record' && context.value.view === 'manager') {
    const sourceIndex = turns.value.findIndex((turn) => turn.run_id === sourceRunId)
    const prior = turns.value.slice(0, sourceIndex + 1)
    // 无工具追问会混合回填此前引用；返回位置只取首次真实读取该病例的轮次。
    const originIndex = prior.findIndex(
      (turn) =>
        turn.reference_scope !== 'prior_turns' &&
        turn.references.some((item) => item.kind === 'record' && item.id === reference.id),
    )
    const origin = prior[originIndex]
    // 提醒也能提供病例入口；只有该病例来源轮本身含统计，才能返回其汇总。
    summaryRunId.value = origin?.references.some((item) => item.kind === 'statistics')
      ? origin.run_id
      : ''
  }
  await send(
    reference.kind === 'record'
      ? `查看“${reference.title}”的保存质控问题`
      : `解释“${reference.title}”，查看病历证据与规则依据`,
    context.value,
    reference.id,
  )
}
const labels: Record<string, string> = {
  non_compliant: '不合规',
  compliant: '合规',
  data_gap: '资料不足',
  needs_review: '待复核',
  not_applicable: '不适用',
  not_executed: '未执行',
}
function statusLabel(status: string) {
  return labels[status] || '状态待核对'
}
const selectedReference = ref<BusinessAgentReference>()
const ruleValidationPath = computed(() => {
  const reference = selectedReference.value
  if (
    activeView.value !== 'manager' ||
    !reference ||
    !isRuleValidation(reference) ||
    !reference.rule_id ||
    !/^LX0609-\d{2}-\d{2}-\d{2}$/.test(reference.rule_id)
  )
    return undefined
  const expected = `/workstation-v4/rules/validation/${reference.rule_id}`
  return reference.entry_path === expected ? expected : undefined
})
const referenceOpen = ref(false)
const referenceLoading = ref(false)
const referenceError = ref('')
let referenceGeneration = 0
const evidenceDocument = ref<BusinessEvidenceDocument>()
const documentOpen = ref(false)
const documentLoading = ref(false)
const documentError = ref('')
let documentGeneration = 0
const documentSegments = computed(() => {
  const document = evidenceDocument.value
  const content = document?.content || ''
  if (
    document?.state !== 'located' ||
    document.offset_unit !== 'unicode_code_points' ||
    document.start === undefined ||
    document.end === undefined
  )
    return { before: content, quote: '', after: '' }
  // 后端坐标按 Unicode 字符计算，避免表情等字符的 UTF-16 长度错位。
  const chars = Array.from(content)
  return {
    before: chars.slice(0, document.start).join(''),
    quote: chars.slice(document.start, document.end).join(''),
    after: chars.slice(document.end).join(''),
  }
})
watch([context, open, sessionId], () => {
  referenceGeneration += 1
  documentGeneration += 1
  referenceOpen.value = false
  documentOpen.value = false
  selectedReference.value = undefined
  evidenceDocument.value = undefined
})
async function openEvidenceDocument(referenceId: string, evidenceIndex: number) {
  const epoch = ++documentGeneration
  documentOpen.value = true
  documentLoading.value = true
  documentError.value = ''
  evidenceDocument.value = undefined
  try {
    const document = await businessAgentApi.evidenceDocument(
      sessionId.value,
      referenceId,
      evidenceIndex,
    )
    if (epoch === documentGeneration) evidenceDocument.value = document
  } catch {
    if (epoch === documentGeneration)
      documentError.value = '对应文书读取失败，请重新核对保存结果与授权范围。'
  } finally {
    if (epoch === documentGeneration) documentLoading.value = false
  }
}
async function openReference(referenceId: string) {
  const epoch = ++referenceGeneration
  referenceOpen.value = true
  referenceLoading.value = true
  referenceError.value = ''
  selectedReference.value = undefined
  try {
    const reference = await businessAgentApi.reference(sessionId.value, referenceId)
    if (epoch === referenceGeneration) selectedReference.value = reference
  } catch {
    if (epoch === referenceGeneration) referenceError.value = '依据读取失败，未取得原文。'
  } finally {
    if (epoch === referenceGeneration) referenceLoading.value = false
  }
}
</script>

<style scoped src="../styles/business-agent.css"></style>
