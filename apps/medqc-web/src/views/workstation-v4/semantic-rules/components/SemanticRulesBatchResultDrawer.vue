<template>
  <a-drawer
    :open="open"
    placement="right"
    :width="'min(1480px, 96vw)'"
    :closable="false"
    :body-style="{ padding: 0 }"
    @close="close"
  >
    <div class="drawer-shell">
      <div class="drawer-head result-review-header">
        <div class="drawer-title-group">
          <a-button
            class="drawer-back-button"
            @click="close"
          >
            返回样本验证
          </a-button>
          <div>
            <p class="drawer-eyebrow">
              批量任务结果
            </p>
            <h2 class="drawer-title">
              任务详情
            </h2>
          </div>
        </div>
        <div class="drawer-actions">
          <a-button
            v-if="canCancelBatchJob"
            danger
            :loading="cancelBatchJobLoading"
            @click="confirmCancelBatchJob"
          >
            停止任务
          </a-button>
          <a-dropdown v-if="batchJobDetail?.status === 'completed'">
            <a-button :loading="batchJobDetailLoading">
              导出 HTML 明细
            </a-button>
            <template #overlay>
              <a-menu @click="handleExportMenuClick">
                <a-menu-item key="html">
                  导出 HTML 明细
                </a-menu-item>
                <a-menu-item key="xlsx">
                  导出 Excel
                </a-menu-item>
                <a-menu-item key="csv">
                  导出 CSV
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
          <a-button
            v-if="batchJobDetail?.status === 'completed' && isLuxian0609BatchJob"
            type="primary"
            :loading="reviewBatchJobLoading"
            @click="handleReviewBatchJobResult"
          >
            复核本次结果
          </a-button>
          <a-button
            type="text"
            @click="close"
          >
            关闭
          </a-button>
        </div>
      </div>

      <div class="drawer-body">
        <div
          v-if="showResultReviewOverview"
          class="result-review-overview result-overview-card"
        >
          <div class="result-overview-card-main">
            <div class="result-overview-identity">
              <div class="result-overview-icon">
                <span>质</span>
              </div>
              <div class="result-review-overview-copy">
                <div class="result-review-overview-title-row">
                  <h3>{{ resultReviewOverviewTitle }}</h3>
                  <span
                    class="result-review-status-chip"
                    :class="getBatchJobStatusTagClass(batchJobDetail?.status || 'queued')"
                  >
                    {{ getBatchJobStatusText(batchJobDetail?.status || 'queued') }}
                  </span>
                </div>
                <div class="result-review-overview-meta">
                  <span v-if="batchJobDetail?.created_at">
                    创建时间：{{ formatDateTime(batchJobDetail.created_at) }}
                  </span>
                  <span v-if="batchJobDetail?.finished_at">
                    完成时间：{{ formatDateTime(batchJobDetail.finished_at) }}
                  </span>
                  <span>规则集：泸县0609质控点验证 v1</span>
                  <span>执行病历：{{ resultReviewRecordCount }} 份</span>
                </div>
                <p class="result-review-overview-desc">
                  {{ resultReviewOutcomeText }}
                </p>
                <p class="result-review-overview-scope">
                  {{ resultReviewScopeText }}
                </p>
              </div>
            </div>
            <div class="result-review-overview-stats">
              <div>
                <span>病历</span>
                <strong>{{ resultReviewRecordCount }}</strong>
                <small>份</small>
              </div>
              <div>
                <span>客户质控点</span>
                <strong>{{ resultReviewCustomerRuleCount }}</strong>
                <small>个</small>
              </div>
              <div>
                <span>结果</span>
                <strong>{{ resultReviewResultCount }}</strong>
                <small>条</small>
              </div>
            </div>
            <div class="result-overview-status-block">
              <span class="result-overview-status-label">状态分布</span>
              <div class="result-review-status-pills">
                <span
                  v-for="item in resultReviewStatusPills"
                  :key="item.key"
                  class="result-review-status-pill"
                  :class="item.className"
                >
                  {{ item.label }} <strong>{{ item.value }}</strong>
                </span>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="batchJobDetail && statusHero && !showResultReviewOverview"
          class="status-hero"
          :class="`status-hero--${statusHero.tone}`"
        >
          <div class="status-hero-main">
            <div
              v-if="statusHero.pulse"
              class="status-hero-pulse"
            />
            <div>
              <div class="status-hero-title-row">
                <span class="status-hero-title">{{ statusHero.title }}</span>
                <a-tag
                  class="status-hero-tag"
                  :class="getBatchJobStatusTagClass(batchJobDetail.status)"
                >
                  {{ getBatchJobStatusText(batchJobDetail.status) }}
                </a-tag>
              </div>
              <div class="status-hero-jobline">
                <div class="status-hero-job-name">
                  {{ batchJobDetail.rule_name || batchJobDetail.rule_code }}
                </div>
              </div>
              <div
                v-if="statusHero.description"
                class="status-hero-desc"
              >
                {{ statusHero.description }}
              </div>
              <div
                v-if="isRunningBatchJob"
                class="status-hero-live"
              >
                <span>
                  已完成 {{ progressSummary?.processedRecords ?? 0 }} /
                  {{ progressSummary?.totalRecords ?? 0 }} 份病历
                </span>
                <span v-if="currentStreamRecordLabel">
                  正在分析：{{ currentStreamRecordLabel }}
                </span>
                <span>{{ liveElapsedLabel }}</span>
                <span v-if="streamUpdatedAtText">最近更新：{{ streamUpdatedAtText }}</span>
              </div>
              <div
                v-if="isRunningBatchJob"
                class="status-hero-flow"
              >
                <div
                  class="status-hero-flow-bar"
                  :style="{ width: `${progressSummary?.percent ?? 0}%` }"
                />
              </div>
            </div>
          </div>
          <div class="status-hero-side">
            <div class="status-hero-percent">
              {{ progressSummary?.percent ?? 0 }}%
            </div>
            <div class="status-hero-side-label">
              {{ progressSummary?.stepLabel || '准备中' }}
            </div>
          </div>
        </div>

        <div
          v-if="focusedSummaryCards.length && !isLuxian0609BatchJob"
          class="drawer-summary summary-grid-primary"
        >
          <div
            v-for="item in focusedSummaryCards"
            :key="item.key"
            class="summary-card"
          >
            <div class="summary-label">
              {{ item.label }}
            </div>
            <div class="summary-value">
              {{ item.value }}
            </div>
            <div
              v-if="item.desc"
              class="summary-desc"
            >
              {{ item.desc }}
            </div>
          </div>
        </div>

        <div
          v-if="isFocusedRecordMode && !showResultReviewOverview"
          class="drawer-card focus-record-card"
        >
          <div class="drawer-section-title">
            当前仅查看单份病历结果
          </div>
          <div class="focus-record-meta">
            <span v-if="props.focusRecordLabel">{{ props.focusRecordLabel }}</span>
            <span v-if="props.focusVisitId">visit_id：{{ props.focusVisitId }}</span>
            <span v-if="props.focusRecordId">记录标识：{{ props.focusRecordId }}</span>
          </div>
        </div>

        <div
          v-if="isLuxian0609BatchJob && !showResultReviewOverview"
          class="drawer-card luxian-scope-card"
        >
          <div class="drawer-section-head">
            <div class="drawer-section-title-group">
              <div class="drawer-section-title">
                泸县0609验证范围
              </div>
              <span class="summary-mode-badge">
                {{ luxianScopeModeLabel }}
              </span>
            </div>
          </div>
          <div class="luxian-scope-grid">
            <div
              v-for="item in luxianScopeCards"
              :key="item.key"
              class="luxian-scope-stat"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.desc }}</small>
            </div>
          </div>
          <div class="luxian-scope-section">
            <div class="luxian-scope-label">
              用户选择的 LX0609 质控点
            </div>
            <div class="luxian-scope-chips">
              <span
                v-for="ruleId in luxianSelectedRuleIdsPreview"
                :key="ruleId"
                class="luxian-scope-chip"
              >
                {{ ruleId }}
              </span>
              <span
                v-if="!luxianSelectedRuleIds.length"
                class="luxian-scope-muted"
              >
                {{ isLuxianScopedRun ? '未返回' : '未限定，执行全量 0609 质控点' }}
              </span>
              <span
                v-else-if="luxianSelectedRuleIds.length > luxianSelectedRuleIdsPreview.length"
                class="luxian-scope-muted"
              >
                另有 {{ luxianSelectedRuleIds.length - luxianSelectedRuleIdsPreview.length }} 条
              </span>
            </div>
          </div>
          <div class="luxian-scope-section">
            <div class="luxian-scope-label">
              病历-规则映射摘要
            </div>
            <div class="luxian-scope-map">
              {{ luxianRecordRuleMapSummary }}
            </div>
          </div>
          <div class="luxian-scope-section">
            <div class="luxian-scope-label">
              状态分布
            </div>
            <div class="luxian-status-grid">
              <span
                v-for="item in luxianStatusDistribution"
                :key="item.key"
                class="luxian-status-pill"
                :class="item.className"
              >
                {{ item.label }} {{ item.value }}
              </span>
            </div>
          </div>
        </div>

        <div
          v-if="luxianReviewReport"
          class="drawer-card luxian-review-card"
        >
          <div class="drawer-section-head">
            <div class="drawer-section-title-group">
              <div class="drawer-section-title">
                结果复核建议
              </div>
              <span class="summary-mode-badge">
                {{ luxianReviewSummaryText }}
              </span>
            </div>
          </div>
          <div
            v-if="luxianReviewFindings.length"
            class="luxian-review-list"
          >
            <article
              v-for="finding in luxianReviewFindings"
              :key="finding.id || `${finding.record_id}-${finding.rule_id}-${finding.risk_type}`"
              class="luxian-review-item"
            >
              <div class="luxian-review-item-head">
                <strong>{{ finding.rule_id || '未返回质控点' }}</strong>
                <span>{{ finding.severity || '建议' }}</span>
                <em v-if="finding.suggested_status">
                  建议口径：{{ mapStructuredStatusLabel(finding.suggested_status) }}
                </em>
              </div>
              <p>
                {{
                  sanitizeCustomerVisibleText(
                    finding.customer_message || finding.reason || '建议质控员确认该质控点结论。',
                  )
                }}
              </p>
              <small v-if="finding.record_id || finding.patient_name">
                {{ [finding.record_id, finding.patient_name].filter(Boolean).join(' · ') }}
              </small>
            </article>
          </div>
          <div
            v-else
            class="luxian-review-empty"
          >
            已完成复核，暂无高风险复核建议。
          </div>
        </div>

        <div
          class="drawer-card issue-review-workbench-card"
          :class="{
            'issue-review-workbench-card--single': isSingleRecordIssueMode,
            'issue-review-workbench-card--multi': isMultiRecordIssueMode,
          }"
        >
          <div class="drawer-section-head">
            <div class="drawer-section-title-group">
              <div class="drawer-section-title">
                {{ issueSectionTitle }}
              </div>
              <span
                v-if="isFastScreenResult"
                class="summary-mode-badge"
              >
                快速初筛结果（摘要版）
              </span>
            </div>
            <div class="drawer-section-actions">
              <a-radio-group
                v-model:value="issueViewMode"
                size="small"
              >
                <a-radio-button value="business">
                  业务视图
                </a-radio-button>
                <a-radio-button value="advanced">
                  高级视图
                </a-radio-button>
              </a-radio-group>
              <a-switch
                v-model:checked="showAllStatuses"
                size="small"
              />
              <span class="drawer-section-meta">
                {{ showAllStatuses ? '全部状态' : '仅问题项' }}
              </span>
            </div>
          </div>
          <div
            class="issue-toolbar"
            :class="{ 'issue-toolbar--single': isSingleRecordIssueMode }"
          >
            <div class="issue-focus-summary">
              {{ issueFocusSummary }}
            </div>
            <div class="issue-filter-bar">
              <a-input
                v-model:value="issueFilter.keyword"
                allow-clear
                placeholder="搜索规则/病历号/结论"
                class="issue-filter-item issue-filter-item--keyword"
              />
              <a-select
                v-model:value="issueFilter.documentType"
                allow-clear
                placeholder="文书域"
                class="issue-filter-item"
                :options="issueDocumentTypeOptions"
              />
              <a-select
                v-model:value="issueFilter.executionDomain"
                allow-clear
                placeholder="规则域"
                class="issue-filter-item"
                :options="issueExecutionDomainOptions"
              />
              <a-select
                v-model:value="issueFilter.defectLevel"
                allow-clear
                placeholder="缺陷等级"
                class="issue-filter-item"
                :options="issueDefectLevelOptions"
              />
              <a-button
                size="small"
                @click="resetIssueFilters"
              >
                重置
              </a-button>
            </div>
          </div>
          <div
            v-if="isMultiRecordIssueMode"
            class="issue-record-switcher"
          >
            <div class="issue-record-switcher-head">
              <span>先选病历，再看质控点</span>
              <small>本次涉及 {{ issueRecordGroups.length }} 份病历，默认按病历分组展示结果。</small>
            </div>
            <div class="issue-record-tabs">
              <button
                v-for="group in issueRecordGroups"
                :key="group.key"
                type="button"
                class="issue-record-tab"
                :class="{ 'issue-record-tab--active': selectedIssueRecordKey === group.key }"
                @click="selectedIssueRecordKey = group.key"
              >
                <strong>{{ group.label }}</strong>
                <span>
                  {{ group.total }} 条 · 不合规 {{ group.nonCompliant }} · 数据不足
                  {{ group.dataGap }}
                </span>
              </button>
              <button
                type="button"
                class="issue-record-tab issue-record-tab--all"
                :class="{ 'issue-record-tab--active': selectedIssueRecordKey === ALL_RECORDS_KEY }"
                @click="selectedIssueRecordKey = ALL_RECORDS_KEY"
              >
                <strong>全部病历</strong>
                <span>{{ issueRecordTotalCount }} 条结果</span>
              </button>
            </div>
          </div>
          <div
            v-if="selectedClusterKey || activeRuleFilterLabel"
            class="aggregation-active-tip"
          >
            <span v-if="selectedClusterKey">聚合簇：{{ resolveCustomerEvidenceText(selectedClusterKey) }}</span>
            <span v-if="selectedClusterKey && activeRuleFilterLabel">·</span>
            <span v-if="activeRuleFilterLabel">规则：{{ activeRuleFilterLabel }}</span>
            <a-button
              v-if="selectedClusterKey"
              type="link"
              size="small"
              @click.stop="clearClusterFilter"
            >
              清除聚合过滤
            </a-button>
            <a-button
              v-if="activeRuleFilterLabel"
              type="link"
              size="small"
              @click.stop="handleDebugRuleChange(undefined)"
            >
              清除规则过滤
            </a-button>
          </div>
          <div
            v-if="incrementalResultTip"
            class="stream-result-tip"
            :class="{ 'stream-result-tip--waiting': isWaitingFirstResult }"
          >
            <span class="stream-result-tip-dot" />
            <span>{{ incrementalResultTip }}</span>
          </div>
          <div
            v-if="issueViewMode === 'business'"
            class="issue-business-workbench issue-review-layout"
            :class="{
              'issue-business-workbench--single': isSingleRecordIssueMode,
              'issue-business-workbench--multi': isMultiRecordIssueMode,
            }"
          >
            <aside
              v-if="isSingleRecordIssueMode && displayIssueItems.length"
              class="issue-review-nav issue-group-list"
            >
              <div class="issue-review-nav-head">
                <strong>质控点审阅列表</strong>
                <span>单份病历 · {{ displayIssueItems.length }} 条结果</span>
              </div>
              <div
                v-for="group in singleIssueNavGroups"
                :key="group.key"
                class="issue-review-nav-group"
                :class="group.className"
              >
                <span>{{ group.title }}</span>
                <em>{{ group.items.length }}</em>
              </div>
              <template
                v-for="group in singleIssueNavGroups"
                :key="`items-${group.key}`"
              >
                <button
                  v-for="item in group.items"
                  :key="`review-nav-${resolveIssueStableKey(item)}`"
                  type="button"
                  class="issue-review-nav-item"
                  :class="[
                    resolveIssueReviewNavClass(item),
                    {
                      'issue-review-nav-item--active':
                        selectedBusinessIssueKey === resolveIssueStableKey(item),
                    },
                  ]"
                  @click="selectBusinessIssue(item)"
                >
                  <div>
                    <strong class="issue-review-nav-code">{{
                      item.rule_code || item.rule_id || '未知规则'
                    }}</strong>
                    <span class="issue-review-nav-title">{{
                      truncateText(item.rule_name || '未知质控点', 44)
                    }}</span>
                  </div>
                  <em>{{ resolveIssueResultKindText(item) }}</em>
                </button>
              </template>
            </aside>
            <div class="issue-business-main">
              <div
                v-if="isSingleRecordIssueMode && selectedBusinessIssueCard"
                class="issue-conclusion-card issue-detail-panel"
                :class="selectedBusinessIssueCard.issue_card_class"
              >
                <div class="issue-detail-head">
                  <div>
                    <div class="issue-detail-title-row">
                      <span class="issue-rule-code">
                        {{
                          selectedBusinessIssueCard.rule_code ||
                            selectedBusinessIssueCard.rule_id ||
                            '未知规则'
                        }}
                      </span>
                      <span class="issue-detail-title-separator">·</span>
                      <strong>{{ selectedBusinessIssueCard.rule_name || '未知质控点' }}</strong>
                    </div>
                    <div class="issue-conclusion-meta">
                      <span>{{ selectedBusinessIssueCard.record_id || '-' }}</span>
                      <span>{{
                        selectedBusinessIssueCard.target_document_type ||
                          selectedBusinessIssueCard.document_type ||
                          '未知文书域'
                      }}</span>
                      <span>{{ resolveIssueSeverityText(selectedBusinessIssueCard) }}</span>
                    </div>
                  </div>
                  <div class="issue-conclusion-status">
                    <span
                      class="issue-result-kind"
                      :class="resolveIssueResultKindClass(selectedBusinessIssueCard)"
                    >
                      {{ resolveIssueResultKindText(selectedBusinessIssueCard) }}
                    </span>
                    <a-tag class="aggregation-count-tag">
                      {{
                        resolveDisplayStatusText(selectedBusinessIssueCard) ||
                          resolveStatusText(selectedBusinessIssueCard.status)
                      }}
                    </a-tag>
                  </div>
                </div>
                <div class="issue-review-reading-path">
                  <div class="issue-review-reading-step is-active">
                    <span>1</span>
                    <strong>先看结论</strong>
                    <em>{{ resolveIssueResultKindText(selectedBusinessIssueCard) }}</em>
                  </div>
                  <div class="issue-review-reading-step">
                    <span>2</span>
                    <strong>核对证据</strong>
                    <em>{{
                      resolveCopyEvidenceCompare(selectedBusinessIssueCard)
                        ? '前后记录对照'
                        : '来源片段与字段'
                    }}</em>
                  </div>
                  <div class="issue-review-reading-step">
                    <span>3</span>
                    <strong>处理建议</strong>
                    <em>复核或补充记录</em>
                  </div>
                </div>
                <div
                  v-if="selectedIssuePatientContext"
                  class="issue-patient-context-card"
                >
                  <div class="issue-patient-avatar">
                    {{ selectedIssuePatientContext.initial }}
                  </div>
                  <div class="issue-patient-context-main">
                    <div class="issue-patient-context-kicker">
                      当前病历
                    </div>
                    <div class="issue-patient-context-id">
                      {{ selectedIssuePatientContext.recordId }}
                    </div>
                    <div class="issue-patient-context-meta">
                      <span>
                        <em>姓名</em>
                        {{ selectedIssuePatientContext.patientName }}
                      </span>
                      <span>
                        <em>科室</em>
                        {{ selectedIssuePatientContext.department }}
                      </span>
                      <span>
                        <em>文书域</em>
                        {{ selectedIssuePatientContext.documentType }}
                      </span>
                    </div>
                  </div>
                </div>
                <div class="issue-detail-body">
                  <section class="issue-detail-section issue-detail-section--conclusion">
                    <div class="issue-detail-section-title">
                      <span>01</span>
                      质控结论
                    </div>
                    <div class="issue-detail-text">
                      <template
                        v-if="hasStructuredText(selectedBusinessIssueCard.customer_findings_text)"
                      >
                        <p
                          v-for="(paragraph, index) in resolveStructuredText(
                            selectedBusinessIssueCard.customer_findings_text,
                          ).summary"
                          :key="`selected-findings-summary-${index}`"
                        >
                          {{ paragraph }}
                        </p>
                        <div
                          v-for="(section, sectionIndex) in resolveStructuredText(
                            selectedBusinessIssueCard.customer_findings_text,
                          ).sections"
                          :key="`selected-findings-section-${sectionIndex}`"
                          class="structured-text-section"
                        >
                          <strong>{{ section.title }}</strong>
                          <p
                            v-for="(paragraph, index) in section.paragraphs"
                            :key="`selected-findings-section-${sectionIndex}-p-${index}`"
                          >
                            {{ paragraph }}
                          </p>
                          <ul v-if="section.points.length">
                            <li
                              v-for="(point, index) in section.points"
                              :key="`selected-findings-section-${sectionIndex}-point-${index}`"
                            >
                              {{ point }}
                            </li>
                          </ul>
                        </div>
                        <ul
                          v-if="
                            resolveStructuredText(selectedBusinessIssueCard.customer_findings_text)
                              .points.length
                          "
                        >
                          <li
                            v-for="(point, index) in resolveStructuredText(
                              selectedBusinessIssueCard.customer_findings_text,
                            ).points"
                            :key="`selected-findings-point-${index}`"
                          >
                            {{ point }}
                          </li>
                        </ul>
                      </template>
                      <p v-else>
                        {{ selectedBusinessIssueCard.customer_findings_text || '未返回结论' }}
                      </p>
                    </div>
                  </section>
                  <div class="issue-detail-main-grid">
                    <section class="issue-detail-section evidence-table-card">
                      <div class="issue-detail-section-title">
                        <span>02</span>
                        关键证据
                      </div>
                      <div
                        v-if="resolveEvidenceChainItems(selectedBusinessIssueCard, 1600).length"
                        class="structured-evidence-list"
                      >
                        <div
                          v-for="evidence in resolveEvidenceChainItems(
                            selectedBusinessIssueCard,
                            1600,
                          )"
                          :key="evidence.key"
                          class="structured-evidence-card"
                        >
                          <div class="structured-evidence-card-head">
                            <strong>{{ evidence.source }}</strong>
                            <span v-if="evidence.fieldPath">{{ evidence.fieldPath }}</span>
                            <span v-if="evidence.recordTime">{{ evidence.recordTime }}</span>
                          </div>
                          <blockquote>{{ evidence.quote }}</blockquote>
                        </div>
                      </div>
                      <div
                        v-else-if="selectedBusinessIssueCard.evidence_summary_parts.length"
                        class="evidence-table"
                      >
                        <div
                          v-for="part in selectedBusinessIssueCard.evidence_summary_parts"
                          :key="part.key"
                          class="evidence-table-row"
                          :class="`evidence-table-row--${part.kind}`"
                        >
                          <span>{{ part.label }}</span>
                          <strong>{{ part.value }}</strong>
                        </div>
                      </div>
                      <p v-else>
                        {{ selectedBusinessIssueCard.evidence_summary }}
                      </p>
                    </section>
                    <section class="suggestion-panel">
                      <div class="issue-detail-section-title">
                        <span>03</span>
                        处理建议
                      </div>
                      <div class="issue-detail-text">
                        <template
                          v-if="
                            hasStructuredText(selectedBusinessIssueCard.customer_suggestion_text)
                          "
                        >
                          <p
                            v-for="(paragraph, index) in resolveStructuredText(
                              selectedBusinessIssueCard.customer_suggestion_text,
                            ).summary"
                            :key="`selected-suggestion-summary-${index}`"
                          >
                            {{ paragraph }}
                          </p>
                          <div
                            v-for="(section, sectionIndex) in resolveStructuredText(
                              selectedBusinessIssueCard.customer_suggestion_text,
                            ).sections"
                            :key="`selected-suggestion-section-${sectionIndex}`"
                            class="structured-text-section"
                          >
                            <strong>{{ section.title }}</strong>
                            <p
                              v-for="(paragraph, index) in section.paragraphs"
                              :key="`selected-suggestion-section-${sectionIndex}-p-${index}`"
                            >
                              {{ paragraph }}
                            </p>
                            <ul v-if="section.points.length">
                              <li
                                v-for="(point, index) in section.points"
                                :key="`selected-suggestion-section-${sectionIndex}-point-${index}`"
                              >
                                {{ point }}
                              </li>
                            </ul>
                          </div>
                          <ul
                            v-if="
                              resolveStructuredText(
                                selectedBusinessIssueCard.customer_suggestion_text,
                              ).points.length
                            "
                          >
                            <li
                              v-for="(point, index) in resolveStructuredText(
                                selectedBusinessIssueCard.customer_suggestion_text,
                              ).points"
                              :key="`selected-suggestion-point-${index}`"
                            >
                              {{ point }}
                            </li>
                          </ul>
                        </template>
                        <p v-else>
                          {{
                            selectedBusinessIssueCard.customer_suggestion_text ||
                              '请结合病历原文确认。'
                          }}
                        </p>
                      </div>
                    </section>
                  </div>
                </div>
                <div
                  v-if="resolveCopyEvidenceCompare(selectedBusinessIssueCard)"
                  class="copy-evidence-compare"
                >
                  <div class="copy-evidence-head">
                    <strong>重复内容对照</strong>
                    <span>用于核对两份病程/查房记录是否只是复制粘贴；重点看本次记录是否有新增病情变化、分析和诊疗计划。</span>
                  </div>
                  <div
                    v-if="resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.legacyNotice"
                    class="copy-evidence-legacy-note"
                  >
                    {{ resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.legacyNotice }}
                  </div>
                  <template
                    v-if="resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.pairs?.length"
                  >
                    <div
                      v-for="pair in resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.pairs"
                      :key="pair.key"
                      class="copy-evidence-pair"
                    >
                      <div class="copy-evidence-pair-head">
                        <strong>重复片段 {{ pair.index }}</strong>
                        <span v-if="pair.similarity">{{ pair.similarity }}</span>
                      </div>
                      <div class="copy-evidence-pair-grid">
                        <div class="copy-evidence-column">
                          <div class="copy-evidence-label">
                            {{ pair.leftLabel }}
                          </div>
                          <blockquote>{{ pair.leftQuote }}</blockquote>
                        </div>
                        <div class="copy-evidence-column">
                          <div class="copy-evidence-label">
                            {{ pair.rightLabel }}
                          </div>
                          <blockquote>{{ pair.rightQuote }}</blockquote>
                        </div>
                      </div>
                    </div>
                  </template>
                  <template
                    v-else-if="!resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.legacyNotice"
                  >
                    <div class="copy-evidence-column">
                      <div class="copy-evidence-label">
                        {{ resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.left.label }}
                      </div>
                      <blockquote>
                        {{ resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.left.quote }}
                      </blockquote>
                    </div>
                    <div class="copy-evidence-column">
                      <div class="copy-evidence-label">
                        {{ resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.right.label }}
                      </div>
                      <blockquote>
                        {{ resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.right.quote }}
                      </blockquote>
                    </div>
                  </template>
                  <div
                    v-if="resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.metric"
                    class="copy-evidence-column copy-evidence-column--metric"
                  >
                    <div class="copy-evidence-label">
                      重复度指标
                    </div>
                    <blockquote>
                      {{ resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.metric }}
                    </blockquote>
                  </div>
                  <div
                    v-if="resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.differenceGap"
                    class="copy-evidence-column copy-evidence-column--gap"
                  >
                    <div class="copy-evidence-label">
                      缺少差异说明
                    </div>
                    <blockquote>
                      {{ resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.differenceGap }}
                    </blockquote>
                  </div>
                </div>
                <div
                  v-if="hasEvidenceChain(selectedBusinessIssueCard)"
                  class="evidence-chain-strip"
                >
                  <span>
                    状态口径：{{
                      resolveEvidenceStatusText(
                        selectedBusinessIssueCard.result_status || selectedBusinessIssueCard.status,
                      )
                    }}
                  </span>
                  <span v-if="resolveEvidenceChainItems(selectedBusinessIssueCard, 1600).length">
                    证据 {{ resolveEvidenceChainItems(selectedBusinessIssueCard, 1600).length }} 条
                  </span>
                  <span v-if="resolveMissingSources(selectedBusinessIssueCard).length">
                    缺少数据 {{ resolveMissingSources(selectedBusinessIssueCard).length }} 项
                  </span>
                </div>
                <div
                  v-if="
                    isIssueExpanded(selectedBusinessIssueCard) &&
                      hasEvidenceChain(selectedBusinessIssueCard)
                  "
                  class="evidence-chain-panel"
                >
                  <div class="evidence-chain-panel-head">
                    <div>
                      <div class="evidence-chain-title">
                        完整说明
                      </div>
                      <div class="evidence-chain-subtitle">
                        展示来源证据、判断过程和质控确认口径
                      </div>
                    </div>
                  </div>
                  <div class="evidence-chain-grid">
                    <div
                      v-if="resolveTriggerFacts(selectedBusinessIssueCard).length"
                      class="evidence-chain-block"
                    >
                      <div class="evidence-chain-block-title">
                        触发事实
                      </div>
                      <div
                        v-for="fact in resolveTriggerFacts(selectedBusinessIssueCard)"
                        :key="fact.key"
                        class="evidence-chain-line"
                      >
                        <span>{{ fact.label }}</span>
                        <strong>{{ fact.value }}</strong>
                      </div>
                    </div>
                    <div class="evidence-chain-block">
                      <div class="evidence-chain-block-title">
                        数据依赖
                      </div>
                      <div
                        v-for="row in resolveDependencyRows(selectedBusinessIssueCard)"
                        :key="row.key"
                        class="evidence-chain-line"
                      >
                        <span>{{ row.label }}</span>
                        <strong>{{ row.value }}</strong>
                      </div>
                    </div>
                    <div
                      v-if="resolveDecisionRows(selectedBusinessIssueCard).length"
                      class="evidence-chain-block"
                    >
                      <div class="evidence-chain-block-title">
                        判断过程
                      </div>
                      <div
                        v-for="row in resolveDecisionRows(selectedBusinessIssueCard)"
                        :key="row.key"
                        class="evidence-chain-line"
                      >
                        <span>{{ row.label }}</span>
                        <strong>{{ row.value }}</strong>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="issue-conclusion-actions">
                  <a-button
                    type="link"
                    size="small"
                    @click="toggleIssueExpanded(selectedBusinessIssueCard)"
                  >
                    {{
                      isIssueExpanded(selectedBusinessIssueCard) ? '收起完整说明' : '展开完整说明'
                    }}
                  </a-button>
                  <a-button
                    type="link"
                    size="small"
                    @click="openIssueDeepReview(selectedBusinessIssueCard)"
                  >
                    深度复核
                  </a-button>
                  <a-button
                    v-if="canShowResultTrace"
                    type="link"
                    size="small"
                    @click="openIssueTrace(selectedBusinessIssueCard)"
                  >
                    诊断追踪
                  </a-button>
                </div>
              </div>
              <div
                v-else-if="businessIssueCards.length"
                class="issue-conclusion-list"
              >
                <div
                  v-for="group in businessIssueCardGroups"
                  :key="group.key"
                  class="issue-record-result-group"
                >
                  <div
                    v-if="shouldShowIssueRecordGroupHeader"
                    class="issue-record-result-head"
                  >
                    <div>
                      <strong>{{ group.label }}</strong>
                      <span>{{ group.meta || '未返回科室/住院号' }}</span>
                    </div>
                    <div class="issue-record-result-stats">
                      <span>结果 {{ group.total }}</span>
                      <span>不合规 {{ group.nonCompliant }}</span>
                      <span>数据不足 {{ group.dataGap }}</span>
                    </div>
                  </div>
                  <TransitionGroup
                    name="issue-stream"
                    tag="div"
                    class="issue-conclusion-list-inner"
                  >
                    <div
                      v-for="item in group.items"
                      :key="`conclusion-${resolveIssueStableKey(item)}`"
                      class="issue-conclusion-card"
                      :class="item.issue_card_class"
                    >
                      <div class="issue-conclusion-head">
                        <div class="issue-conclusion-head-main">
                          <div class="issue-conclusion-title-row">
                            <span class="issue-conclusion-title">
                              <span class="issue-rule-code">
                                {{ item.rule_code || item.rule_id || '未知规则' }}
                              </span>
                              ·
                              {{ item.rule_name || '未知质控点' }}
                            </span>
                          </div>
                          <div class="issue-conclusion-meta">
                            <span>{{ item.record_id || '-' }}</span>
                            <span>{{
                              item.target_document_type || item.document_type || '未知文书域'
                            }}</span>
                            <span>{{ resolveIssueSeverityText(item) }}</span>
                            <span v-if="item.refined">单条精审</span>
                          </div>
                        </div>
                        <div class="issue-conclusion-status">
                          <span
                            class="issue-result-kind"
                            :class="resolveIssueResultKindClass(item)"
                          >
                            {{ resolveIssueResultKindText(item) }}
                          </span>
                          <a-tag class="aggregation-count-tag">
                            {{ resolveDisplayStatusText(item) || resolveStatusText(item.status) }}
                          </a-tag>
                        </div>
                      </div>
                      <div class="issue-at-a-glance">
                        <div class="issue-glance-block issue-glance-block--conclusion">
                          <div class="issue-glance-label">
                            质控结论
                          </div>
                          <div class="issue-glance-text">
                            <template v-if="hasStructuredText(item.customer_findings_text)">
                              <p
                                v-for="(paragraph, index) in resolveStructuredText(
                                  item.customer_findings_text,
                                ).summary.slice(0, 2)"
                                :key="`glance-findings-summary-${resolveIssueStableKey(item)}-${index}`"
                              >
                                {{ paragraph }}
                              </p>
                              <ul
                                v-if="
                                  resolveStructuredText(item.customer_findings_text).points.length
                                "
                              >
                                <li
                                  v-for="(point, index) in resolveStructuredText(
                                    item.customer_findings_text,
                                  ).points.slice(0, 2)"
                                  :key="`glance-findings-point-${resolveIssueStableKey(item)}-${index}`"
                                >
                                  {{ point }}
                                </li>
                              </ul>
                            </template>
                            <p v-else>
                              {{ item.customer_findings_text || '未返回结论' }}
                            </p>
                          </div>
                        </div>
                        <div class="issue-glance-block">
                          <div class="issue-glance-label">
                            关键证据
                          </div>
                          <div
                            v-if="item.evidence_summary_parts.length"
                            class="issue-evidence-facts"
                          >
                            <div
                              v-for="part in item.evidence_summary_parts"
                              :key="part.key"
                              class="issue-evidence-fact"
                              :class="`issue-evidence-fact--${part.kind}`"
                            >
                              <span>{{ part.label }}：</span>
                              <strong>{{ part.value }}</strong>
                            </div>
                          </div>
                          <div
                            v-else-if="resolveEvidenceChainItems(item).length"
                            class="issue-evidence-facts issue-evidence-facts--structured"
                          >
                            <div
                              v-for="evidence in resolveEvidenceChainItems(item).slice(0, 3)"
                              :key="evidence.key"
                              class="issue-evidence-fact"
                            >
                              <span>
                                {{
                                  [evidence.source, evidence.fieldPath]
                                    .filter(Boolean)
                                    .join(' · ') || '来源证据'
                                }}
                              </span>
                              <strong>{{ evidence.quote }}</strong>
                            </div>
                          </div>
                          <span v-else>
                            {{ item.evidence_summary }}
                          </span>
                        </div>
                        <div class="issue-glance-block">
                          <div class="issue-glance-label">
                            处理建议
                          </div>
                          <div class="issue-glance-text">
                            <template v-if="hasStructuredText(item.customer_suggestion_text)">
                              <p
                                v-for="(paragraph, index) in resolveStructuredText(
                                  item.customer_suggestion_text,
                                ).summary.slice(0, 2)"
                                :key="`glance-suggestion-summary-${resolveIssueStableKey(item)}-${index}`"
                              >
                                {{ paragraph }}
                              </p>
                              <ul
                                v-if="
                                  resolveStructuredText(item.customer_suggestion_text).points.length
                                "
                              >
                                <li
                                  v-for="(point, index) in resolveStructuredText(
                                    item.customer_suggestion_text,
                                  ).points.slice(0, 2)"
                                  :key="`glance-suggestion-point-${resolveIssueStableKey(item)}-${index}`"
                                >
                                  {{ point }}
                                </li>
                              </ul>
                            </template>
                            <p v-else>
                              {{ item.customer_suggestion_text || '请结合病历原文确认。' }}
                            </p>
                          </div>
                        </div>
                      </div>
                      <div
                        v-if="resolveCopyEvidenceCompare(item)"
                        class="copy-evidence-compare"
                      >
                        <div class="copy-evidence-head">
                          <strong>重复内容对照</strong>
                          <span>用于核对前后记录是否只是复制粘贴，重点看本次记录有没有新增病情变化、分析和诊疗计划。</span>
                        </div>
                        <div
                          v-if="resolveCopyEvidenceCompare(item)?.legacyNotice"
                          class="copy-evidence-legacy-note"
                        >
                          {{ resolveCopyEvidenceCompare(item)?.legacyNotice }}
                        </div>
                        <template v-if="resolveCopyEvidenceCompare(item)?.pairs?.length">
                          <div
                            v-for="pair in resolveCopyEvidenceCompare(item)?.pairs"
                            :key="pair.key"
                            class="copy-evidence-pair"
                          >
                            <div class="copy-evidence-pair-head">
                              <strong>重复片段 {{ pair.index }}</strong>
                              <span v-if="pair.similarity">{{ pair.similarity }}</span>
                            </div>
                            <div class="copy-evidence-pair-grid">
                              <div class="copy-evidence-column">
                                <div class="copy-evidence-label">
                                  {{ pair.leftLabel }}
                                </div>
                                <blockquote>{{ pair.leftQuote }}</blockquote>
                              </div>
                              <div class="copy-evidence-column">
                                <div class="copy-evidence-label">
                                  {{ pair.rightLabel }}
                                </div>
                                <blockquote>{{ pair.rightQuote }}</blockquote>
                              </div>
                            </div>
                          </div>
                        </template>
                        <template v-else-if="!resolveCopyEvidenceCompare(item)?.legacyNotice">
                          <div class="copy-evidence-column">
                            <div class="copy-evidence-label">
                              {{ resolveCopyEvidenceCompare(item)?.left.label }}
                            </div>
                            <blockquote>
                              {{ resolveCopyEvidenceCompare(item)?.left.quote }}
                            </blockquote>
                          </div>
                          <div class="copy-evidence-column">
                            <div class="copy-evidence-label">
                              {{ resolveCopyEvidenceCompare(item)?.right.label }}
                            </div>
                            <blockquote>
                              {{ resolveCopyEvidenceCompare(item)?.right.quote }}
                            </blockquote>
                          </div>
                        </template>
                        <div
                          v-if="resolveCopyEvidenceCompare(item)?.metric"
                          class="copy-evidence-column copy-evidence-column--metric"
                        >
                          <div class="copy-evidence-label">
                            重复度指标
                          </div>
                          <blockquote>{{ resolveCopyEvidenceCompare(item)?.metric }}</blockquote>
                        </div>
                        <div
                          v-if="resolveCopyEvidenceCompare(item)?.differenceGap"
                          class="copy-evidence-column copy-evidence-column--gap"
                        >
                          <div class="copy-evidence-label">
                            缺少差异说明
                          </div>
                          <blockquote>
                            {{ resolveCopyEvidenceCompare(item)?.differenceGap }}
                          </blockquote>
                        </div>
                      </div>
                      <div
                        v-if="hasEvidenceChain(item)"
                        class="evidence-chain-strip"
                      >
                        <span>
                          状态口径：{{
                            resolveEvidenceStatusText(item.result_status || item.status)
                          }}
                        </span>
                        <span v-if="resolveTriggerFacts(item).length">
                          触发事实 {{ resolveTriggerFacts(item).length }} 条
                        </span>
                        <span v-if="resolveEvidenceChainItems(item).length">
                          证据 {{ resolveEvidenceChainItems(item).length }} 条
                        </span>
                        <span v-if="resolveMissingSources(item).length">
                          缺少数据 {{ resolveMissingSources(item).length }} 项
                        </span>
                      </div>
                      <div
                        v-if="isIssueExpanded(item) && hasEvidenceChain(item)"
                        class="evidence-chain-panel"
                      >
                        <div class="evidence-chain-panel-head">
                          <div>
                            <div class="evidence-chain-title">
                              证据链
                            </div>
                            <div class="evidence-chain-subtitle">
                              按触发事实、依赖数据、来源证据和判断口径展示
                            </div>
                          </div>
                          <a-tag class="evidence-chain-tag">
                            {{ resolveExecutorTypeText(item.executor_type) }}
                          </a-tag>
                        </div>
                        <div class="evidence-chain-grid">
                          <div
                            v-if="resolveTriggerFacts(item).length"
                            class="evidence-chain-block"
                          >
                            <div class="evidence-chain-block-title">
                              触发事实
                            </div>
                            <div
                              v-for="fact in resolveTriggerFacts(item)"
                              :key="fact.key"
                              class="evidence-chain-line"
                            >
                              <span>{{ fact.label }}</span>
                              <strong>{{ fact.value }}</strong>
                            </div>
                          </div>
                          <div class="evidence-chain-block">
                            <div class="evidence-chain-block-title">
                              数据依赖
                            </div>
                            <div
                              v-for="row in resolveDependencyRows(item)"
                              :key="row.key"
                              class="evidence-chain-line"
                            >
                              <span>{{ row.label }}</span>
                              <strong>{{ row.value }}</strong>
                            </div>
                          </div>
                          <div
                            v-if="resolveDecisionRows(item).length"
                            class="evidence-chain-block"
                          >
                            <div class="evidence-chain-block-title">
                              判断过程
                            </div>
                            <div
                              v-for="row in resolveDecisionRows(item)"
                              :key="row.key"
                              class="evidence-chain-line"
                            >
                              <span>{{ row.label }}</span>
                              <strong>{{ row.value }}</strong>
                            </div>
                          </div>
                          <div
                            v-if="resolveReviewRows(item).length"
                            class="evidence-chain-block"
                          >
                            <div class="evidence-chain-block-title">
                              质控确认
                            </div>
                            <div
                              v-for="row in resolveReviewRows(item)"
                              :key="row.key"
                              class="evidence-chain-line"
                            >
                              <span>{{ row.label }}</span>
                              <strong>{{ row.value }}</strong>
                            </div>
                          </div>
                        </div>
                        <div
                          v-if="resolveEvidenceChainItems(item, 1200).length"
                          class="evidence-chain-evidence-list"
                        >
                          <div class="evidence-chain-block-title">
                            关键证据
                          </div>
                          <div
                            v-for="evidence in resolveEvidenceChainItems(item, 1200)"
                            :key="evidence.key"
                            class="evidence-chain-evidence"
                          >
                            <div class="evidence-chain-evidence-meta">
                              <span>{{ evidence.source }}</span>
                              <span v-if="evidence.recordTime">{{ evidence.recordTime }}</span>
                              <span v-if="evidence.fieldPath">{{ evidence.fieldPath }}</span>
                            </div>
                            <div class="evidence-chain-quote">
                              {{ evidence.quote }}
                            </div>
                          </div>
                        </div>
                      </div>
                      <div
                        v-if="isIssueExpanded(item)"
                        class="issue-conclusion-summary"
                      >
                        <div class="issue-conclusion-row">
                          <span class="issue-conclusion-label">结论</span>
                          <div class="issue-conclusion-structured">
                            <template v-if="hasStructuredText(item.customer_findings_text)">
                              <p
                                v-for="(paragraph, index) in resolveStructuredText(
                                  item.customer_findings_text,
                                ).summary"
                                :key="`findings-summary-${index}`"
                              >
                                {{ paragraph }}
                              </p>
                              <div
                                v-for="(section, sectionIndex) in resolveStructuredText(
                                  item.customer_findings_text,
                                ).sections"
                                :key="`findings-section-${sectionIndex}`"
                                class="structured-text-section"
                              >
                                <strong>{{ section.title }}</strong>
                                <p
                                  v-for="(paragraph, paragraphIndex) in section.paragraphs"
                                  :key="`findings-section-${sectionIndex}-p-${paragraphIndex}`"
                                >
                                  {{ paragraph }}
                                </p>
                                <ul v-if="section.points.length">
                                  <li
                                    v-for="(point, pointIndex) in section.points"
                                    :key="`findings-section-${sectionIndex}-point-${pointIndex}`"
                                  >
                                    {{ point }}
                                  </li>
                                </ul>
                              </div>
                              <ul
                                v-if="
                                  resolveStructuredText(item.customer_findings_text).points.length
                                "
                              >
                                <li
                                  v-for="(point, index) in resolveStructuredText(
                                    item.customer_findings_text,
                                  ).points"
                                  :key="`findings-point-${index}`"
                                >
                                  {{ point }}
                                </li>
                              </ul>
                            </template>
                            <span v-else>无</span>
                          </div>
                        </div>
                        <div class="issue-conclusion-row">
                          <span class="issue-conclusion-label">证据</span>
                          <div class="issue-conclusion-structured">
                            <div
                              v-if="resolveEvidenceChainItems(item, 1200).length"
                              class="structured-evidence-list structured-evidence-list--inline"
                            >
                              <div
                                v-for="evidence in resolveEvidenceChainItems(item, 1200)"
                                :key="`expanded-${evidence.key}`"
                                class="structured-evidence-card"
                              >
                                <div class="structured-evidence-card-head">
                                  <strong>{{ evidence.source }}</strong>
                                  <span v-if="evidence.fieldPath">{{ evidence.fieldPath }}</span>
                                  <span v-if="evidence.recordTime">{{ evidence.recordTime }}</span>
                                </div>
                                <blockquote>{{ evidence.quote }}</blockquote>
                              </div>
                            </div>
                            <template v-else-if="hasStructuredText(item.customer_evidence_text)">
                              <p
                                v-for="(paragraph, index) in resolveStructuredText(
                                  item.customer_evidence_text,
                                ).summary"
                                :key="`evidence-summary-${index}`"
                              >
                                {{ paragraph }}
                              </p>
                              <div
                                v-for="(section, sectionIndex) in resolveStructuredText(
                                  item.customer_evidence_text,
                                ).sections"
                                :key="`evidence-section-${sectionIndex}`"
                                class="structured-text-section"
                              >
                                <strong>{{ section.title }}</strong>
                                <p
                                  v-for="(paragraph, paragraphIndex) in section.paragraphs"
                                  :key="`evidence-section-${sectionIndex}-p-${paragraphIndex}`"
                                >
                                  {{ paragraph }}
                                </p>
                                <ul v-if="section.points.length">
                                  <li
                                    v-for="(point, pointIndex) in section.points"
                                    :key="`evidence-section-${sectionIndex}-point-${pointIndex}`"
                                  >
                                    {{ point }}
                                  </li>
                                </ul>
                              </div>
                              <ul
                                v-if="
                                  resolveStructuredText(item.customer_evidence_text).points.length
                                "
                              >
                                <li
                                  v-for="(point, index) in resolveStructuredText(
                                    item.customer_evidence_text,
                                  ).points"
                                  :key="`evidence-point-${index}`"
                                >
                                  {{ point }}
                                </li>
                              </ul>
                            </template>
                            <span v-else>无</span>
                          </div>
                        </div>
                        <div class="issue-conclusion-row">
                          <span class="issue-conclusion-label">建议</span>
                          <div class="issue-conclusion-structured">
                            <template v-if="hasStructuredText(item.customer_suggestion_text)">
                              <p
                                v-for="(paragraph, index) in resolveStructuredText(
                                  item.customer_suggestion_text,
                                ).summary"
                                :key="`suggestion-summary-${index}`"
                              >
                                {{ paragraph }}
                              </p>
                              <div
                                v-for="(section, sectionIndex) in resolveStructuredText(
                                  item.customer_suggestion_text,
                                ).sections"
                                :key="`suggestion-section-${sectionIndex}`"
                                class="structured-text-section"
                              >
                                <strong>{{ section.title }}</strong>
                                <p
                                  v-for="(paragraph, paragraphIndex) in section.paragraphs"
                                  :key="`suggestion-section-${sectionIndex}-p-${paragraphIndex}`"
                                >
                                  {{ paragraph }}
                                </p>
                                <ul v-if="section.points.length">
                                  <li
                                    v-for="(point, pointIndex) in section.points"
                                    :key="`suggestion-section-${sectionIndex}-point-${pointIndex}`"
                                  >
                                    {{ point }}
                                  </li>
                                </ul>
                              </div>
                              <ul
                                v-if="
                                  resolveStructuredText(item.customer_suggestion_text).points.length
                                "
                              >
                                <li
                                  v-for="(point, index) in resolveStructuredText(
                                    item.customer_suggestion_text,
                                  ).points"
                                  :key="`suggestion-point-${index}`"
                                >
                                  {{ point }}
                                </li>
                              </ul>
                            </template>
                            <span v-else>无</span>
                          </div>
                        </div>
                        <div
                          v-if="item.rewrite_example"
                          class="issue-conclusion-row"
                        >
                          <span class="issue-conclusion-label">改写示例</span>
                          <div class="issue-conclusion-structured">
                            {{ item.rewrite_example }}
                          </div>
                        </div>
                      </div>
                      <div class="issue-conclusion-actions">
                        <a-button
                          type="link"
                          size="small"
                          @click="toggleIssueExpanded(item)"
                        >
                          {{ isIssueExpanded(item) ? '收起完整说明' : '展开完整说明' }}
                        </a-button>
                        <a-button
                          type="link"
                          size="small"
                          @click="openIssueDeepReview(item)"
                        >
                          深度复核
                        </a-button>
                        <a-button
                          v-if="canShowResultTrace"
                          type="link"
                          size="small"
                          @click="openIssueTrace(item)"
                        >
                          诊断追踪
                        </a-button>
                      </div>
                    </div>
                  </TransitionGroup>
                </div>
              </div>
              <div
                v-else-if="isWaitingFirstResult"
                class="stream-waiting-card"
              >
                <div class="stream-waiting-scan" />
                <div class="stream-waiting-lines">
                  <span />
                  <span />
                  <span />
                </div>
                <div class="stream-waiting-text">
                  正在等待首份病历结果
                </div>
                <div class="stream-waiting-subtext">
                  {{ waitingFirstResultDescription }}
                </div>
              </div>
              <a-empty
                v-else
                :description="emptyIssueText"
              />
              <section
                v-if="!showAllStatuses && noIssueEvidenceItems.length"
                class="no-issue-evidence-panel"
              >
                <div class="no-issue-evidence-head">
                  <div>
                    <strong>未提示问题的依据</strong>
                    <span>
                      本次另有
                      {{ noIssueEvidenceTotalCount }}
                      条合规或不适用结果，以下展示可帮助核对系统为什么未列为问题。
                    </span>
                  </div>
                  <a-button
                    type="link"
                    size="small"
                    @click="showAllStatuses = true"
                  >
                    查看全部状态
                  </a-button>
                </div>
                <div class="no-issue-evidence-list">
                  <details
                    v-for="item in noIssueEvidenceItems"
                    :key="`no-issue-${resolveIssueStableKey(item)}`"
                    class="no-issue-evidence-item"
                  >
                    <summary>
                      <span class="issue-rule-code">
                        {{ item.rule_code || item.rule_id || '未知规则' }}
                      </span>
                      <strong>{{ item.rule_name || '未知质控点' }}</strong>
                      <em>{{ item.no_issue_status_text }}</em>
                    </summary>
                    <div class="no-issue-evidence-body">
                      <span>{{ item.no_issue_basis_label }}</span>
                      <p>{{ item.no_issue_basis_text }}</p>
                    </div>
                  </details>
                </div>
              </section>
              <a-pagination
                v-if="
                  !isSingleRecordIssueMode && displayIssueItems.length > issuePagination.pageSize
                "
                v-model:current="issuePagination.current"
                :page-size="issuePagination.pageSize"
                :total="displayIssueItems.length"
                size="small"
                class="issue-pagination"
                :show-size-changer="false"
              />
            </div>
          </div>
          <a-table
            v-if="issueViewMode === 'advanced'"
            :columns="issueColumns"
            class="batch-issue-table"
            :data-source="displayIssueItems"
            :row-key="resolveIssueStableKey"
            size="small"
            :scroll="{ x: 1700 }"
            :pagination="issuePagination"
            :row-class-name="resolveIssueRowClassName"
            :locale="{ emptyText: emptyIssueText }"
            @change="handleIssueTableChange"
          />
        </div>

        <a-collapse
          v-if="issueViewMode === 'advanced'"
          v-model:active-key="advancedSectionKeys"
          ghost
          class="drawer-advanced-collapse"
        >
          <a-collapse-panel
            key="execution"
            header="技术详情：执行统计"
          >
            <div
              v-if="progressSummary"
              class="drawer-card drawer-card--nested"
            >
              <div class="drawer-section-head">
                <div class="drawer-section-title">
                  任务进度
                </div>
                <div class="drawer-section-meta">
                  {{ progressSummary.stepLabel }}
                </div>
              </div>
              <a-progress
                :percent="progressSummary.percent"
                :status="progressSummary.status"
                :stroke-color="progressSummary.status === 'exception' ? '#ef4444' : '#2563eb'"
              />
              <div class="progress-meta">
                <span>已处理 {{ progressSummary.processedRecords }} /
                  {{ progressSummary.totalRecords }} 份病历</span>
                <span>规则 {{ progressSummary.ruleIndex }} / {{ progressSummary.ruleCount }}</span>
              </div>
            </div>

            <div
              v-if="advancedSummaryCards.length"
              class="drawer-summary summary-grid-secondary"
            >
              <div
                v-for="item in advancedSummaryCards"
                :key="item.key"
                class="summary-card"
              >
                <div class="summary-label">
                  {{ item.label }}
                </div>
                <div class="summary-value">
                  {{ item.value }}
                </div>
                <div
                  v-if="item.desc"
                  class="summary-desc"
                >
                  {{ item.desc }}
                </div>
              </div>
            </div>
          </a-collapse-panel>

          <a-collapse-panel
            v-if="resultAggregation"
            key="aggregation"
            header="技术详情：结果聚合"
          >
            <div class="drawer-card drawer-card--nested">
              <div class="drawer-section-head">
                <div class="drawer-section-title">
                  结果聚合
                </div>
                <div class="drawer-section-meta">
                  簇数 {{ resultAggregation.cluster_count || 0 }} · 重复命中
                  {{ resultAggregation.duplicate_hits || 0 }}
                </div>
              </div>
              <div
                v-if="aggregationBreakdownSections.length"
                class="aggregation-breakdown-grid"
              >
                <div
                  v-for="section in aggregationBreakdownSections"
                  :key="section.key"
                  class="aggregation-breakdown-card"
                >
                  <div class="aggregation-breakdown-head">
                    <div class="aggregation-breakdown-title">
                      {{ section.title }}
                    </div>
                    <div class="aggregation-breakdown-count">
                      {{ section.total }}
                    </div>
                  </div>
                  <div
                    v-if="section.items.length"
                    class="aggregation-breakdown-items"
                  >
                    <div
                      v-for="item in section.items"
                      :key="`${section.key}-${item.label}`"
                      class="aggregation-breakdown-item"
                    >
                      <span class="aggregation-breakdown-item-label">{{ item.label }}</span>
                      <a-tag class="aggregation-breakdown-item-tag">
                        {{ item.count }}
                      </a-tag>
                    </div>
                  </div>
                  <div
                    v-else
                    class="aggregation-breakdown-empty"
                  >
                    暂无分解数据
                  </div>
                </div>
              </div>
              <div class="aggregation-list">
                <div
                  v-for="cluster in topAggregationClusters"
                  :key="cluster.cluster_key"
                  class="aggregation-item"
                  :class="{ active: selectedClusterKey === cluster.cluster_key }"
                  @click="toggleClusterFilter(cluster.cluster_key)"
                >
                  <div class="aggregation-item-head">
                    <span class="aggregation-item-title">
                      {{ resolveCustomerEvidenceText(cluster.cluster_key) }}
                    </span>
                    <a-tag class="aggregation-count-tag">
                      {{ cluster.records || 0 }} 次
                    </a-tag>
                  </div>
                  <div
                    v-if="cluster.sample_evidence"
                    class="aggregation-evidence"
                  >
                    {{ resolveCustomerEvidenceText(cluster.sample_evidence) }}
                  </div>
                  <div class="aggregation-meta">
                    病历 {{ cluster.records || 0 }} 条 · 规则 {{ cluster.rules?.length || 0 }} 条
                  </div>
                </div>
              </div>
              <div
                v-if="selectedClusterKey"
                class="aggregation-active-tip"
              >
                已按聚合簇过滤：{{ resolveCustomerEvidenceText(selectedClusterKey) }}
                <a-button
                  type="link"
                  size="small"
                  @click.stop="clearClusterFilter"
                >
                  清除
                </a-button>
              </div>
            </div>
          </a-collapse-panel>

          <a-collapse-panel
            key="rules"
            header="技术详情：规则结果"
          >
            <div class="drawer-card drawer-card--nested">
              <div class="drawer-section-head">
                <div class="drawer-section-title">
                  规则结果概览
                </div>
                <div
                  v-if="activeRuleFilterLabel"
                  class="drawer-section-meta"
                >
                  已按规则过滤：{{ activeRuleFilterLabel }}
                </div>
              </div>
              <a-table
                :columns="ruleColumns"
                :data-source="displayRuleResults"
                row-key="id"
                size="small"
                :pagination="false"
                :locale="{
                  emptyText: '暂无规则结果（任务可能仍在执行中，或该任务为旧格式历史数据）',
                }"
              />
            </div>
          </a-collapse-panel>

          <a-collapse-panel
            v-if="batchJobDebugSnapshot"
            key="debug"
            header="技术详情：调试快照"
          >
            <div class="drawer-card drawer-card--nested">
              <div class="drawer-section-head">
                <div class="drawer-section-title">
                  执行调试快照
                </div>
                <div class="debug-toolbar">
                  <a-select
                    :value="selectedDebugRuleJobId || undefined"
                    allow-clear
                    placeholder="按规则筛选调试快照"
                    class="debug-rule-select"
                    :options="debugRuleOptions"
                    :loading="batchJobDebugLoading"
                    @change="handleDebugRuleChange"
                  />
                  <div class="drawer-section-meta">
                    {{ batchJobDebugSnapshot.status }} ·
                    {{ batchJobDebugSnapshot.execution_mode || 'unknown' }}
                  </div>
                </div>
              </div>
              <div class="debug-current-rule">
                <div class="debug-current-rule-main">
                  <span class="debug-current-rule-label">当前规则</span>
                  <span class="debug-current-rule-value">
                    {{
                      batchJobDebugSnapshot.current_rule?.rule_code ||
                        currentDebugRule?.rule_code ||
                        '未定位'
                    }}
                  </span>
                </div>
                <div class="debug-current-rule-sub">
                  {{
                    batchJobDebugSnapshot.current_rule?.rule_name ||
                      currentDebugRule?.rule_name ||
                      '暂无规则名称'
                  }}
                </div>
              </div>
              <div class="debug-meta-grid">
                <div class="debug-meta-item">
                  <span class="debug-meta-label">规则总数</span>
                  <span class="debug-meta-value">{{ batchJobDebugSnapshot.rule_count || 0 }}</span>
                </div>
                <div class="debug-meta-item">
                  <span class="debug-meta-label">筛选规则</span>
                  <span class="debug-meta-value">{{
                    batchJobDebugSnapshot.filtered_rule_count || 0
                  }}</span>
                </div>
                <div class="debug-meta-item">
                  <span class="debug-meta-label">更新时间</span>
                  <span class="debug-meta-value">{{
                    formatDateTime(batchJobDebugSnapshot.updated_at)
                  }}</span>
                </div>
                <div class="debug-meta-item">
                  <span class="debug-meta-label">任务状态</span>
                  <span class="debug-meta-value">{{ batchJobDebugSnapshot.status }}</span>
                </div>
              </div>
              <div
                v-if="debugProgressEntries.length"
                class="debug-pill-block"
              >
                <div class="debug-pill-title">
                  current_rule.progress
                </div>
                <div class="debug-pill-list">
                  <span
                    v-for="item in debugProgressEntries"
                    :key="`progress-${item.label}`"
                    class="debug-pill"
                  >
                    {{ item.label }}: {{ item.value }}
                  </span>
                </div>
              </div>
              <div
                v-if="debugDetailEntries.length"
                class="debug-pill-block"
              >
                <div class="debug-pill-title">
                  current_rule.debug
                </div>
                <div class="debug-pill-list">
                  <span
                    v-for="item in debugDetailEntries"
                    :key="`debug-${item.label}`"
                    class="debug-pill debug-pill-muted"
                  >
                    {{ item.label }}: {{ item.value }}
                  </span>
                </div>
              </div>
            </div>
          </a-collapse-panel>
        </a-collapse>
      </div>
    </div>
    <a-modal
      :open="deepReviewModalOpen"
      title="深度复核"
      width="820px"
      :footer="null"
      @cancel="closeDeepReviewModal"
    >
      <template v-if="selectedDeepReviewIssue">
        <div class="deep-review-modal">
          <div class="deep-review-head">
            <div class="deep-review-title">
              {{
                selectedDeepReviewIssue.rule_code || selectedDeepReviewIssue.rule_id || '未知规则'
              }}
              ·
              {{ selectedDeepReviewIssue.rule_name || '未知质控点' }}
            </div>
            <a-tag class="aggregation-count-tag">
              {{ resolveStatusText(selectedDeepReviewIssue.status) }}
            </a-tag>
          </div>
          <div class="deep-review-meta">
            <span>{{ selectedDeepReviewIssue.record_id || '-' }}</span>
            <span>{{
              selectedDeepReviewIssue.target_document_type ||
                selectedDeepReviewIssue.document_type ||
                '未知文书域'
            }}</span>
            <span>{{ selectedDeepReviewIssue.rule_family || 'general' }}</span>
            <span>{{ selectedDeepReviewIssue.defect_level || '未分级' }}</span>
            <span v-if="selectedDeepReviewIssue.refined">单条精审</span>
          </div>
          <div
            v-if="hasEvidenceChain(selectedDeepReviewIssue)"
            class="deep-review-chain"
          >
            <div class="evidence-chain-panel-head">
              <div>
                <div class="evidence-chain-title">
                  证据链
                </div>
                <div class="evidence-chain-subtitle">
                  触发事实、依赖数据、来源证据和判断阈值
                </div>
              </div>
              <a-tag class="evidence-chain-tag">
                {{
                  resolveEvidenceStatusText(
                    selectedDeepReviewIssue.result_status || selectedDeepReviewIssue.status,
                  )
                }}
              </a-tag>
            </div>
            <div class="evidence-chain-grid">
              <div
                v-if="resolveTriggerFacts(selectedDeepReviewIssue).length"
                class="evidence-chain-block"
              >
                <div class="evidence-chain-block-title">
                  触发事实
                </div>
                <div
                  v-for="fact in resolveTriggerFacts(selectedDeepReviewIssue)"
                  :key="fact.key"
                  class="evidence-chain-line"
                >
                  <span>{{ fact.label }}</span>
                  <strong>{{ fact.value }}</strong>
                </div>
              </div>
              <div class="evidence-chain-block">
                <div class="evidence-chain-block-title">
                  数据依赖
                </div>
                <div
                  v-for="row in resolveDependencyRows(selectedDeepReviewIssue)"
                  :key="row.key"
                  class="evidence-chain-line"
                >
                  <span>{{ row.label }}</span>
                  <strong>{{ row.value }}</strong>
                </div>
              </div>
              <div
                v-if="resolveDecisionRows(selectedDeepReviewIssue).length"
                class="evidence-chain-block"
              >
                <div class="evidence-chain-block-title">
                  判断过程
                </div>
                <div
                  v-for="row in resolveDecisionRows(selectedDeepReviewIssue)"
                  :key="row.key"
                  class="evidence-chain-line"
                >
                  <span>{{ row.label }}</span>
                  <strong>{{ row.value }}</strong>
                </div>
              </div>
              <div
                v-if="resolveAuditRows(selectedDeepReviewIssue).length"
                class="evidence-chain-block"
              >
                <div class="evidence-chain-block-title">
                  执行信息
                </div>
                <div
                  v-for="row in resolveAuditRows(selectedDeepReviewIssue)"
                  :key="row.key"
                  class="evidence-chain-line"
                >
                  <span>{{ row.label }}</span>
                  <strong>{{ row.value }}</strong>
                </div>
              </div>
            </div>
            <div
              v-if="resolveEvidenceChainItems(selectedDeepReviewIssue, 1600).length"
              class="evidence-chain-evidence-list"
            >
              <div class="evidence-chain-block-title">
                关键证据
              </div>
              <div
                v-for="evidence in resolveEvidenceChainItems(selectedDeepReviewIssue, 1600)"
                :key="evidence.key"
                class="evidence-chain-evidence"
              >
                <div class="evidence-chain-evidence-meta">
                  <span>{{ evidence.source }}</span>
                  <span v-if="evidence.recordTime">{{ evidence.recordTime }}</span>
                  <span v-if="evidence.fieldPath">{{ evidence.fieldPath }}</span>
                </div>
                <div class="evidence-chain-quote">
                  {{ evidence.quote }}
                </div>
              </div>
            </div>
          </div>
          <a-alert
            v-if="deepReviewError"
            type="warning"
            show-icon
            :message="deepReviewError"
          />
          <a-spin :spinning="deepReviewLoading">
            <div class="deep-review-section">
              <div class="deep-review-label">
                复核结论
              </div>
              <div class="deep-review-content">
                <template
                  v-if="resolveStructuredText(resolveDeepReviewText('findings')).summary.length"
                >
                  <p
                    v-for="(paragraph, index) in resolveStructuredText(
                      resolveDeepReviewText('findings'),
                    ).summary"
                    :key="`deep-review-findings-summary-${index}`"
                    class="issue-conclusion-summary-text"
                  >
                    {{ paragraph }}
                  </p>
                </template>
                <div
                  v-for="(section, sectionIndex) in resolveStructuredText(
                    resolveDeepReviewText('findings'),
                  ).sections"
                  :key="`deep-review-findings-section-${sectionIndex}`"
                  class="issue-conclusion-section"
                >
                  <div class="issue-conclusion-section-title">
                    {{ section.title }}
                  </div>
                  <p
                    v-for="(paragraph, paragraphIndex) in section.paragraphs"
                    :key="`deep-review-findings-paragraph-${sectionIndex}-${paragraphIndex}`"
                    class="issue-conclusion-summary-text"
                  >
                    {{ paragraph }}
                  </p>
                  <ol
                    v-if="section.points.length"
                    class="issue-conclusion-points"
                  >
                    <li
                      v-for="(point, index) in section.points"
                      :key="`deep-review-findings-point-${sectionIndex}-${index}`"
                    >
                      {{ point }}
                    </li>
                  </ol>
                </div>
                <ol
                  v-if="resolveStructuredText(resolveDeepReviewText('findings')).points.length"
                  class="issue-conclusion-points"
                >
                  <li
                    v-for="(point, index) in resolveStructuredText(
                      resolveDeepReviewText('findings'),
                    ).points"
                    :key="`deep-review-findings-root-point-${index}`"
                  >
                    {{ point }}
                  </li>
                </ol>
              </div>
            </div>
            <div class="deep-review-section">
              <div class="deep-review-label">
                复核证据
              </div>
              <div class="deep-review-content">
                <template
                  v-if="resolveStructuredText(resolveDeepReviewText('evidence')).summary.length"
                >
                  <p
                    v-for="(paragraph, index) in resolveStructuredText(
                      resolveDeepReviewText('evidence'),
                    ).summary"
                    :key="`deep-review-evidence-summary-${index}`"
                    class="issue-conclusion-summary-text"
                  >
                    {{ paragraph }}
                  </p>
                </template>
                <div
                  v-for="(section, sectionIndex) in resolveStructuredText(
                    resolveDeepReviewText('evidence'),
                  ).sections"
                  :key="`deep-review-evidence-section-${sectionIndex}`"
                  class="issue-conclusion-section"
                >
                  <div class="issue-conclusion-section-title">
                    {{ section.title }}
                  </div>
                  <p
                    v-for="(paragraph, paragraphIndex) in section.paragraphs"
                    :key="`deep-review-evidence-paragraph-${sectionIndex}-${paragraphIndex}`"
                    class="issue-conclusion-summary-text"
                  >
                    {{ paragraph }}
                  </p>
                  <ol
                    v-if="section.points.length"
                    class="issue-conclusion-points"
                  >
                    <li
                      v-for="(point, index) in section.points"
                      :key="`deep-review-evidence-point-${sectionIndex}-${index}`"
                    >
                      {{ point }}
                    </li>
                  </ol>
                </div>
                <ol
                  v-if="resolveStructuredText(resolveDeepReviewText('evidence')).points.length"
                  class="issue-conclusion-points"
                >
                  <li
                    v-for="(point, index) in resolveStructuredText(
                      resolveDeepReviewText('evidence'),
                    ).points"
                    :key="`deep-review-evidence-root-point-${index}`"
                  >
                    {{ point }}
                  </li>
                </ol>
              </div>
            </div>
            <div class="deep-review-section">
              <div class="deep-review-label">
                复核建议
              </div>
              <div class="deep-review-content">
                <template
                  v-if="resolveStructuredText(resolveDeepReviewText('suggestion')).summary.length"
                >
                  <p
                    v-for="(paragraph, index) in resolveStructuredText(
                      resolveDeepReviewText('suggestion'),
                    ).summary"
                    :key="`deep-review-suggestion-summary-${index}`"
                    class="issue-conclusion-summary-text"
                  >
                    {{ paragraph }}
                  </p>
                </template>
                <div
                  v-for="(section, sectionIndex) in resolveStructuredText(
                    resolveDeepReviewText('suggestion'),
                  ).sections"
                  :key="`deep-review-suggestion-section-${sectionIndex}`"
                  class="issue-conclusion-section"
                >
                  <div class="issue-conclusion-section-title">
                    {{ section.title }}
                  </div>
                  <p
                    v-for="(paragraph, paragraphIndex) in section.paragraphs"
                    :key="`deep-review-suggestion-paragraph-${sectionIndex}-${paragraphIndex}`"
                    class="issue-conclusion-summary-text"
                  >
                    {{ paragraph }}
                  </p>
                  <ol
                    v-if="section.points.length"
                    class="issue-conclusion-points"
                  >
                    <li
                      v-for="(point, index) in section.points"
                      :key="`deep-review-suggestion-point-${sectionIndex}-${index}`"
                    >
                      {{ point }}
                    </li>
                  </ol>
                </div>
                <ol
                  v-if="resolveStructuredText(resolveDeepReviewText('suggestion')).points.length"
                  class="issue-conclusion-points"
                >
                  <li
                    v-for="(point, index) in resolveStructuredText(
                      resolveDeepReviewText('suggestion'),
                    ).points"
                    :key="`deep-review-suggestion-root-point-${index}`"
                  >
                    {{ point }}
                  </li>
                </ol>
              </div>
            </div>
          </a-spin>
        </div>
      </template>
    </a-modal>
    <a-modal
      :open="resultTraceModalOpen"
      title="诊断追踪"
      width="900px"
      :footer="null"
      @cancel="closeIssueTrace"
    >
      <div class="result-trace-modal">
        <a-alert
          type="info"
          show-icon
          message="仅供管理员或实施人员排查使用"
          description="这里展示的是脱敏后的结果链路：最终客户点结果、聚合/后处理、门控依赖和可安全展示的底层线索，不返回模型原始输出或完整病历正文。"
        />
        <a-alert
          v-if="resultTraceError"
          type="warning"
          show-icon
          :message="resultTraceError"
        />
        <a-spin :spinning="resultTraceLoading">
          <div
            v-if="resultTraceData"
            class="result-trace-sections"
          >
            <section
              v-for="section in resultTraceSections"
              :key="section.key"
              class="result-trace-section"
            >
              <div class="result-trace-section-head">
                <div>
                  <h4>{{ section.title }}</h4>
                  <p>{{ section.description }}</p>
                </div>
                <a-tag v-if="section.badge">
                  {{ section.badge }}
                </a-tag>
              </div>
              <div
                v-if="section.rows.length"
                class="result-trace-grid"
              >
                <div
                  v-for="row in section.rows"
                  :key="`${section.key}-${row.key}`"
                  class="result-trace-row"
                >
                  <span>{{ row.label }}</span>
                  <strong>{{ row.value }}</strong>
                </div>
              </div>
              <div
                v-else
                class="result-trace-empty"
              >
                当前结果未保存该层级的可展示诊断数据。
              </div>
            </section>
          </div>
        </a-spin>
      </div>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type {
  SichuanBatchIssueItem,
  SichuanBatchJobDebugSnapshot,
  SichuanBatchJobResultTrace,
  SichuanBatchJob,
  SichuanBatchResultAggregation,
  Luxian0609ReviewFinding,
  Luxian0609ReviewReport,
} from '@/views/workstation-v4/semantic-rules/types'
import {
  evaluateSichuanRuleForVisit,
  getSichuanWorkspaceBatchJobResultTrace,
} from '@/services/sichuan-rule-workspace-service'
import type {
  StructuredQCFilterState,
  StructuredQCIssue,
  StructuredQCStatus,
} from '@/views/workstation-v4/types'
import {
  createDefaultStructuredQCFilter,
  filterStructuredQCIssues,
  mapBatchJobToStructuredQC,
} from '@/views/workstation-v4/utils/structuredQc'
import { isBatchJobCancelable } from '@/views/workstation-v4/semantic-rules/utils/batchJobStatus'

const props = defineProps<{
  open: boolean
  batchJobDetail: SichuanBatchJob | null
  batchJobDebugSnapshot?: SichuanBatchJobDebugSnapshot | null
  batchJobDebugLoading?: boolean
  fetchBatchJobDebugSnapshot?: (
    jobId: string,
    options?: { ruleJobId?: string; itemLimit?: number },
  ) => Promise<SichuanBatchJobDebugSnapshot | null>
  batchJobDetailLoading: boolean
  close: () => void
  exportBatchJobReport: (format?: 'xlsx' | 'csv' | 'html') => void
  reviewBatchJobResult?: () => Promise<void> | void
  reviewBatchJobLoading?: boolean
  cancelBatchJob?: (jobId: string) => Promise<void> | void
  cancelBatchJobLoading?: boolean
  getBatchJobStatusTagClass: (status?: string) => string
  getBatchJobStatusText: (status?: string) => string
  formatDateTime: (value?: string | Date | null) => string
  focusVisitId?: string
  focusRecordId?: string
  focusRecordLabel?: string
}>()

type BatchJobExportFormat = 'xlsx' | 'csv' | 'html'

function handleExportMenuClick(event: { key?: unknown }) {
  const format = String(event?.key || 'html') as BatchJobExportFormat
  props.exportBatchJobReport(['xlsx', 'csv', 'html'].includes(format) ? format : 'html')
}

async function handleReviewBatchJobResult() {
  if (!props.reviewBatchJobResult) {
    message.warning('当前页面暂未接入复核功能')
    return
  }
  await props.reviewBatchJobResult()
}

const scopeLabelMap: Record<string, string> = {
  running: '运行病历',
  final: '终末病历',
  all: '全量病历',
}

const PROGRESS_STEP_LABEL_MAP: Record<string, string> = {
  queued: '排队中',
  prepare: '收集病历与装配证据',
  filter: '病历筛选完成，准备执行规则',
  run: '正在执行质控规则',
  aggregate: '正在汇总结果',
  completed: '已完成',
  failed: '执行失败',
  canceled: '已取消',
}

const LUXIAN_0609_RULE_SET_KEY = 'luxian_0609_qc_v1'
const LUXIAN_0609_NATIVE_RULE_IDS = new Set(['LX0609-029', 'LX0609-030', 'LX0609-032'])
const LUXIAN_0609_FOCUS_STATUSES: StructuredQCStatus[] = [
  'non_compliant',
  'ai_suggested_non_compliant',
  'uncertain',
  'data_gap',
  'not_executed',
  'technical_error',
  'failed',
]
const LUXIAN_0609_STATUS_ORDER = [
  'non_compliant',
  'ai_suggested_non_compliant',
  'compliant',
  'ai_suggested_compliant',
  'not_applicable',
  'data_gap',
  'uncertain',
  'not_executed',
  'technical_error',
]
const ISSUE_RESULT_DISPLAY_STATUS_ORDER = [
  'non_compliant',
  'ai_suggested_non_compliant',
  'technical_error',
  'data_gap',
  'uncertain',
  'not_executed',
  'not_applicable',
  'ai_suggested_compliant',
  'compliant',
]
const ALL_RECORDS_KEY = '__all_records__'

interface IssueRecordGroup<T extends SichuanBatchIssueItem = SichuanBatchIssueItem> {
  key: string
  label: string
  meta: string
  total: number
  nonCompliant: number
  dataGap: number
  uncertain: number
  technicalError: number
  items: T[]
}

function normalizeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  const seen = new Set<string>()
  const result: string[] = []
  value.forEach((item) => {
    const normalized = String(item || '').trim()
    if (!normalized || seen.has(normalized)) return
    seen.add(normalized)
    result.push(normalized)
  })
  return result
}

function optionalNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatTokenNumber(value: unknown): string {
  const parsed = optionalNumber(value)
  if (parsed === null) return '-'
  return Math.round(parsed).toLocaleString('zh-CN')
}

function normalizeLuxianStatusKey(status?: string) {
  const normalized = String(status || '')
    .trim()
    .toLowerCase()
  if (normalized === 'technical_error_internal' || normalized === 'error') return 'technical_error'
  if (normalized === 'unsupported' || normalized === 'not_run') return 'not_executed'
  if (normalized === 'data_quality_gap') return 'data_gap'
  if (normalized === 'needs_manual_review') return 'ai_suggested_non_compliant'
  return normalized
}

function parseBackendDateTimeMs(value?: string | Date | null): number {
  if (!value) return 0
  if (value instanceof Date) {
    const timestamp = value.getTime()
    return Number.isFinite(timestamp) ? timestamp : 0
  }
  const text = String(value).trim()
  if (!text) return 0
  const normalized = text.includes('T') ? text : text.replace(' ', 'T')
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const timestamp = Date.parse(hasTimezone ? normalized : `${normalized}Z`)
  return Number.isFinite(timestamp) ? timestamp : 0
}

const liveNow = ref(Date.now())
let liveTicker: ReturnType<typeof setInterval> | null = null

const issueViewMode = ref<'business' | 'advanced'>('business')
const showAllStatuses = ref(false)
const issueFilter = ref<StructuredQCFilterState>(createDefaultStructuredQCFilter())
const advancedSectionKeys = ref<string[]>([])
const normalizedFocusVisitId = computed(() => String(props.focusVisitId || '').trim())
const normalizedFocusRecordId = computed(() => String(props.focusRecordId || '').trim())
const cancelBatchJobLoading = computed(() => props.cancelBatchJobLoading === true)
const canCancelBatchJob = computed(
  () =>
    Boolean(props.cancelBatchJob) &&
    Boolean(props.batchJobDetail?.id) &&
    isBatchJobCancelable(props.batchJobDetail?.status),
)
const isFocusedRecordMode = computed(
  () => !!(normalizedFocusVisitId.value || normalizedFocusRecordId.value),
)

function confirmCancelBatchJob() {
  const jobId = String(props.batchJobDetail?.id || '').trim()
  if (!jobId || !props.cancelBatchJob) return
  Modal.confirm({
    title: '停止质控任务',
    content: '确定停止当前质控任务？已完成结果将保留，未完成规则不再继续执行。',
    okText: '停止任务',
    okType: 'danger',
    cancelText: '继续等待',
    async onOk() {
      try {
        await props.cancelBatchJob?.(jobId)
      } catch (error) {
        const text = error instanceof Error ? error.message : ''
        message.error(text || '停止任务失败')
        throw error
      }
    },
  })
}

function matchesFocusedRecord(
  item: Pick<SichuanBatchIssueItem, 'visit_id' | 'record_id'> | StructuredQCIssue,
) {
  if (!isFocusedRecordMode.value) return true
  const candidateVisitId =
    'visitId' in item ? String(item.visitId || '').trim() : String(item.visit_id || '').trim()
  const candidateRecordId =
    'recordId' in item ? String(item.recordId || '').trim() : String(item.record_id || '').trim()
  if (normalizedFocusVisitId.value && candidateVisitId === normalizedFocusVisitId.value) return true
  if (normalizedFocusVisitId.value && candidateRecordId === normalizedFocusVisitId.value)
    return true
  if (normalizedFocusRecordId.value && candidateRecordId === normalizedFocusRecordId.value)
    return true
  return false
}

const ruleColumns = computed(() => [
  { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 120 },
  { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', width: 220 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 110 },
  { title: '命中问题', dataIndex: 'issue_records', key: 'issue_records', width: 100 },
  { title: '成功', dataIndex: 'success_count', key: 'success_count', width: 90 },
  { title: '失败', dataIndex: 'failed_count', key: 'failed_count', width: 90 },
])

const issueColumns = computed(() => {
  const columns: Array<Record<string, any>> = [
    { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 96 },
    { title: '病历号', dataIndex: 'record_id', key: 'record_id', width: 120 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 92,
      customRender: ({ text, record }: { text?: string; record: SichuanBatchIssueItem }) =>
        resolveDisplayStatusText(record) || resolveStatusText(text),
    },
    {
      title: '质控结论',
      dataIndex: 'findings',
      key: 'findings',
      width: 320,
      customRender: ({ text }: { text?: string }) =>
        h(
          'span',
          { title: sanitizeCustomerVisibleText(text) },
          truncateText(sanitizeCustomerVisibleText(text), 80),
        ),
    },
    {
      title: '证据摘要',
      dataIndex: 'evidence',
      key: 'evidence',
      width: 280,
      customRender: ({ text }: { text?: string }) =>
        h(
          'span',
          { title: resolveCustomerEvidenceText(text) },
          truncateText(resolveCustomerEvidenceText(text), 72),
        ),
    },
    {
      title: '整改建议',
      dataIndex: 'suggestion',
      key: 'suggestion',
      width: 260,
      customRender: ({ text }: { text?: string }) =>
        h(
          'span',
          { title: sanitizeCustomerVisibleText(text) },
          truncateText(sanitizeCustomerVisibleText(text), 68),
        ),
    },
    {
      title: '文书域',
      dataIndex: 'target_document_type',
      key: 'target_document_type',
      width: 108,
      customRender: ({ record }: { record: SichuanBatchIssueItem }) =>
        record.target_document_type || record.document_type || '-',
    },
    { title: '规则域', dataIndex: 'execution_domain', key: 'execution_domain', width: 112 },
    { title: '规则族', dataIndex: 'rule_family', key: 'rule_family', width: 128 },
    { title: '缺陷等级', dataIndex: 'defect_level', key: 'defect_level', width: 110 },
    {
      title: '精审',
      dataIndex: 'refined',
      key: 'refined',
      width: 72,
      customRender: ({ text }: { text?: boolean }) => (text ? '是' : '否'),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 88,
      customRender: ({ text }: { text?: number }) => Number(text || 0).toFixed(2),
    },
  ]
  if (issueViewMode.value === 'advanced') {
    columns.push(
      { title: '执行器', dataIndex: 'executor_type', key: 'executor_type', width: 84 },
      { title: '规则版本', dataIndex: 'rule_version', key: 'rule_version', width: 112 },
    )
    if (!isLuxianNativeSliceBatchJob.value) {
      columns.push(
        { title: 'Prompt版本', dataIndex: 'prompt_version', key: 'prompt_version', width: 120 },
        { title: '模型版本', dataIndex: 'model_version', key: 'model_version', width: 120 },
      )
    }
    columns.push(
      { title: '证据来源', dataIndex: 'evidence_source', key: 'evidence_source', width: 110 },
      { title: 'trace_id', dataIndex: 'trace_id', key: 'trace_id', width: 140 },
      {
        title: 'cache_hit',
        dataIndex: 'cache_hit',
        key: 'cache_hit',
        width: 90,
        customRender: ({ text }: { text?: boolean | null }) =>
          text === null || text === undefined ? '-' : text ? 'true' : 'false',
      },
    )
  }
  return columns
})

const resolvedRuleResults = computed(() => {
  const ruleResults = props.batchJobDetail?.rule_results
  if (Array.isArray(ruleResults) && ruleResults.length > 0) {
    if (!isFocusedRecordMode.value) return ruleResults
    return ruleResults
      .map((ruleResult) => ({
        ...ruleResult,
        items: (ruleResult.items || []).filter((item) => matchesFocusedRecord(item)),
      }))
      .filter((ruleResult) => (ruleResult.items || []).length > 0)
  }
  return []
})

const selectedClusterKey = ref('')
const selectedDebugRuleJobId = ref('')
const selectedIssueRecordKey = ref(ALL_RECORDS_KEY)
const selectedBusinessIssueKey = ref('')
const issuePagination = reactive({
  current: 1,
  pageSize: 8,
  showSizeChanger: false,
})
const expandedIssueKeys = ref<string[]>([])
const deepReviewModalOpen = ref(false)
const selectedDeepReviewIssue = ref<SichuanBatchIssueItem | null>(null)
const deepReviewLoading = ref(false)
const deepReviewError = ref('')
const deepReviewResult = ref<Record<string, unknown> | null>(null)
const resultTraceModalOpen = ref(false)
const resultTraceLoading = ref(false)
const resultTraceError = ref('')
const resultTraceData = ref<SichuanBatchJobResultTrace | null>(null)

const batchJobDebugSnapshot = computed(() => props.batchJobDebugSnapshot || null)
const canShowResultTrace = computed(() => issueViewMode.value === 'advanced')

type ResultTraceRow = {
  key: string
  label: string
  value: string
}

type ResultTraceSection = {
  key: string
  title: string
  description: string
  badge?: string
  rows: ResultTraceRow[]
}

const resultTraceSections = computed<ResultTraceSection[]>(() => {
  const trace = resultTraceData.value
  if (!trace) return []
  return [
    {
      key: 'final_result',
      title: '最终客户点结果',
      description: '页面最终展示给客户的质控点结论和状态。',
      badge: stringifyTraceValue(
        trace.final_result?.status || trace.final_result?.display_status || '',
      ),
      rows: traceObjectRows(trace.final_result),
    },
    {
      key: 'aggregation_trace',
      title: '聚合与后处理',
      description: '用于判断状态是否被客户点聚合、规则保护或后处理改写。',
      rows: traceObjectRows(trace.aggregation_trace),
    },
    {
      key: 'decision',
      title: '门控、依赖与判定',
      description: '规则触发、依赖字段和判定过程的可展示诊断信息。',
      rows: [
        ...traceObjectRows(trace.trigger, '触发'),
        ...traceObjectRows(trace.dependencies, '依赖'),
        ...traceObjectRows(trace.decision, '判定'),
      ],
    },
    {
      key: 'source_execution_results',
      title: '底层执行线索',
      description: '底层规则或映射结果的脱敏摘要；如果为空，说明该任务未保存可展示的底层明细。',
      rows: traceListRows(trace.source_execution_results),
    },
    {
      key: 'safety',
      title: '安全过滤',
      description: '确认诊断追踪没有返回模型原始输出、完整病历正文或向量等敏感字段。',
      rows: traceObjectRows(trace.safety),
    },
  ]
})

const structuredResult = computed(() =>
  mapBatchJobToStructuredQC(props.batchJobDetail, batchJobDebugSnapshot.value),
)

const scopedStructuredIssues = computed<StructuredQCIssue[]>(() => {
  const issues = structuredResult.value.issues || []
  if (!isFocusedRecordMode.value) return issues
  return issues.filter((item) => matchesFocusedRecord(item))
})

const structuredIssues = computed<StructuredQCIssue[]>(() => {
  const defaultStatusList = isLuxian0609BatchJob.value
    ? LUXIAN_0609_FOCUS_STATUSES
    : (['non_compliant', 'uncertain'] satisfies StructuredQCStatus[])
  const baseFilter: StructuredQCFilterState = {
    ...issueFilter.value,
    statusList: showAllStatuses.value ? [] : defaultStatusList,
  }
  let list = filterStructuredQCIssues(scopedStructuredIssues.value, baseFilter)
  if (!showAllStatuses.value) {
    list = list.filter((item) => !item.internalOnly)
  }
  if (selectedDebugRuleJobId.value) {
    list = list.filter((item) => item.ruleJobId === selectedDebugRuleJobId.value)
  }
  return list
})

function resolveIssueSourceKey(
  issue: Pick<
    SichuanBatchIssueItem,
    'rule_job_id' | 'rule_id' | 'rule_code' | 'record_id' | 'visit_id'
  >,
) {
  return [
    issue.rule_job_id || '',
    issue.rule_id || issue.rule_code || '',
    issue.record_id || '',
    issue.visit_id || '',
  ].join('|')
}

const sourceIssueMap = computed(() => {
  const map = new Map<string, SichuanBatchIssueItem>()
  ;(props.batchJobDetail?.items || []).forEach((item) => {
    map.set(resolveIssueSourceKey(item), item)
  })
  return map
})

function mapStructuredIssueToBatchIssueItem(item: StructuredQCIssue): SichuanBatchIssueItem {
  const sourceIssue =
    sourceIssueMap.value.get(
      resolveIssueSourceKey({
        rule_job_id: item.ruleJobId || undefined,
        rule_id: item.ruleId || item.ruleCode,
        rule_code: item.ruleCode || item.ruleId,
        record_id: item.recordId || '-',
        visit_id: item.visitId || '',
      }),
    ) || ({} as Partial<SichuanBatchIssueItem>)
  return {
    ...sourceIssue,
    rule_job_id: item.ruleJobId || undefined,
    rule_id: item.ruleId || item.ruleCode,
    rule_code: item.ruleCode || item.ruleId,
    rule_name: item.ruleName,
    record_id: item.recordId || '-',
    visit_id: item.visitId || '',
    patient_name: item.patientName || '',
    department: item.department || '',
    status: item.status,
    is_compliant: item.status === 'compliant' || item.status === 'not_applicable',
    display_status: item.displayStatus || sourceIssue.display_status,
    display_bucket: item.displayBucket || sourceIssue.display_bucket,
    postprocess_label: item.postprocessLabel || sourceIssue.postprocess_label,
    postprocess_reason: item.postprocessReason || sourceIssue.postprocess_reason,
    evidence_problem_type: item.evidenceProblemType || sourceIssue.evidence_problem_type,
    can_show_as_defect: item.canShowAsDefect,
    can_show_to_doctor: item.canShowToDoctor,
    internal_only: item.internalOnly,
    postprocess_mode: item.postprocessMode || sourceIssue.postprocess_mode,
    first_pass_status: item.firstPassStatus || sourceIssue.first_pass_status,
    first_pass_display_status: item.firstPassDisplayStatus || sourceIssue.first_pass_display_status,
    adjudicated_display_status:
      item.adjudicatedDisplayStatus || sourceIssue.adjudicated_display_status,
    adjudicator_reason: item.adjudicatorReason || sourceIssue.adjudicator_reason,
    adjudicator_supporting_quote:
      item.adjudicatorSupportingQuote || sourceIssue.adjudicator_supporting_quote,
    adjudicator_confidence: item.adjudicatorConfidence || sourceIssue.adjudicator_confidence,
    rule_requirement_match: item.ruleRequirementMatch || sourceIssue.rule_requirement_match,
    findings: item.findings,
    evidence: item.evidence,
    suggestion: item.suggestion,
    confidence: item.confidence,
    executor_type: item.executorType,
    rule_version: item.metadata.ruleVersion,
    prompt_version: item.metadata.promptVersion,
    model_version: item.metadata.modelVersion,
    evidence_source: item.metadata.evidenceSource,
    cache_hit: item.metadata.cacheHit === null ? undefined : item.metadata.cacheHit,
    trace_id: item.metadata.traceId,
    cache_key: item.metadata.cacheKey,
    execution_domain: item.executionDomain,
    rule_family: item.ruleFamily,
    doc_scope: item.metadata.docScope,
    cost_class: item.metadata.costClass,
    document_type: item.documentType,
    defect_level: item.defectLevel,
    qc_point_id: item.qcPointId || sourceIssue.qc_point_id,
    rule_set_key: item.ruleSetKey || sourceIssue.rule_set_key,
    rule_set_version: item.ruleSetVersion || sourceIssue.rule_set_version,
    schema_version: item.schemaVersion || sourceIssue.schema_version,
    result_status: item.resultStatus || sourceIssue.result_status,
    trigger: item.trigger || sourceIssue.trigger,
    dependencies: item.dependencies || sourceIssue.dependencies,
    evidence_items:
      item.evidenceItems && item.evidenceItems.length > 0
        ? item.evidenceItems
        : sourceIssue.evidence_items,
    decision: item.decision || sourceIssue.decision,
    review: item.review || sourceIssue.review,
    audit: item.audit || sourceIssue.audit,
    llm_fallback: item.metadata.llmFallback === null ? undefined : item.metadata.llmFallback,
    refined: item.metadata.refined === null ? undefined : item.metadata.refined,
    refine_reason: item.metadata.refineReason,
    screening_status: item.metadata.screeningStatus,
    final_decision_source: item.metadata.finalDecisionSource,
  }
}

const issueItems = computed<SichuanBatchIssueItem[]>(() => {
  return structuredIssues.value.map(mapStructuredIssueToBatchIssueItem)
})

const resolvedDeepReviewResult = computed(() => {
  if (!deepReviewResult.value) return null
  const evaluationResults = Array.isArray(deepReviewResult.value.evaluation_results)
    ? (deepReviewResult.value.evaluation_results as Array<Record<string, unknown>>)
    : []
  return evaluationResults[0] || deepReviewResult.value
})

const issueDocumentTypeOptions = computed(() => {
  const set = new Set<string>()
  scopedStructuredIssues.value.forEach((item) => {
    const value = String(item.documentType || '').trim()
    if (value) set.add(value)
  })
  return Array.from(set).map((value) => ({ label: value, value }))
})

const issueExecutionDomainOptions = computed(() => {
  const set = new Set<string>()
  scopedStructuredIssues.value.forEach((item) => {
    const value = String(item.executionDomain || '').trim()
    if (value) set.add(value)
  })
  return Array.from(set).map((value) => ({ label: value, value }))
})

const issueDefectLevelOptions = computed(() => {
  const set = new Set<string>()
  scopedStructuredIssues.value.forEach((item) => {
    const value = String(item.defectLevel || '').trim()
    if (value) set.add(value)
  })
  return Array.from(set).map((value) => ({ label: value, value }))
})

watch(
  () => props.batchJobDetail?.id,
  () => {
    selectedClusterKey.value = ''
    selectedDebugRuleJobId.value = ''
    selectedIssueRecordKey.value = ALL_RECORDS_KEY
    selectedBusinessIssueKey.value = ''
    issueViewMode.value = 'business'
    advancedSectionKeys.value = []
    expandedIssueKeys.value = []
    closeDeepReviewModal()
    resetIssueFilters()
  },
)

watch(
  () => [
    issueFilter.value.keyword,
    issueFilter.value.documentType,
    issueFilter.value.executionDomain,
    issueFilter.value.defectLevel,
    showAllStatuses.value,
    selectedDebugRuleJobId.value,
    selectedClusterKey.value,
    selectedIssueRecordKey.value,
    selectedBusinessIssueKey.value,
  ],
  () => {
    issuePagination.current = 1
  },
)

const resultAggregation = computed<SichuanBatchResultAggregation | null>(() => {
  return props.batchJobDetail?.summary?.result_aggregation || null
})

const topAggregationClusters = computed(() => {
  return (resultAggregation.value?.clusters || []).slice(0, 8)
})

const aggregationBreakdownSections = computed(() => {
  const aggregation = resultAggregation.value
  if (!aggregation) return []
  return [
    {
      key: 'rule',
      title: '按规则',
      total:
        aggregation.rule_breakdown?.reduce((sum, item) => sum + Number(item.hits || 0), 0) || 0,
      items: normalizeBreakdownItems(
        (aggregation.rule_breakdown || []).map((item) => ({
          label: item.rule_name || item.rule_id,
          count: Number(item.hits || 0),
        })),
      ),
    },
    {
      key: 'executor',
      title: '按执行器',
      total:
        aggregation.executor_breakdown?.reduce((sum, item) => sum + Number(item.count || 0), 0) ||
        0,
      items: normalizeBreakdownItems(
        (aggregation.executor_breakdown || []).map((item) => ({
          label: resolveBreakdownLabel('executor', item.key),
          count: Number(item.count || 0),
        })),
      ),
    },
    {
      key: 'document',
      title: '按文书',
      total:
        aggregation.document_breakdown?.reduce((sum, item) => sum + Number(item.count || 0), 0) ||
        0,
      items: normalizeBreakdownItems(
        (aggregation.document_breakdown || []).map((item) => ({
          label: resolveBreakdownLabel('document', item.key),
          count: Number(item.count || 0),
        })),
      ),
    },
    {
      key: 'status',
      title: '按状态',
      total:
        aggregation.status_breakdown?.reduce((sum, item) => sum + Number(item.count || 0), 0) || 0,
      items: normalizeBreakdownItems(
        (aggregation.status_breakdown || []).map((item) => ({
          label: resolveBreakdownLabel('status', item.key),
          count: Number(item.count || 0),
        })),
      ),
    },
    {
      key: 'defect',
      title: '按缺陷级别',
      total:
        aggregation.defect_level_breakdown?.reduce(
          (sum, item) => sum + Number(item.count || 0),
          0,
        ) || 0,
      items: normalizeBreakdownItems(
        (aggregation.defect_level_breakdown || []).map((item) => ({
          label: resolveBreakdownLabel('defect', item.key),
          count: Number(item.count || 0),
        })),
      ),
    },
  ]
})

const debugRuleOptions = computed(() => {
  return (batchJobDebugSnapshot.value?.rules || []).map((rule) => ({
    label: `${rule.rule_code} · ${rule.rule_name}`,
    value: rule.rule_job_id,
  }))
})

const currentDebugRule = computed(() => {
  const snapshot = batchJobDebugSnapshot.value
  if (!snapshot) return null
  if (selectedDebugRuleJobId.value) {
    return (
      (snapshot.rules || []).find((rule) => rule.rule_job_id === selectedDebugRuleJobId.value) ||
      null
    )
  }
  const currentRuleJobId = String(snapshot.current_rule?.rule_job_id || '').trim()
  if (currentRuleJobId) {
    const matched = (snapshot.rules || []).find((rule) => rule.rule_job_id === currentRuleJobId)
    if (matched) return matched
  }
  return (
    (snapshot.rules || []).find((rule) => String(rule.status || '').toLowerCase() === 'running') ||
    snapshot.rules?.[0] ||
    null
  )
})

const debugProgressEntries = computed(() => {
  const progress =
    batchJobDebugSnapshot.value?.current_rule?.progress || currentDebugRule.value?.progress || {}
  return objectEntriesToCompactList(progress)
})

const debugDetailEntries = computed(() => {
  return objectEntriesToCompactList(currentDebugRule.value?.debug || {})
})

const activeRuleFilterLabel = computed(() => {
  if (!selectedDebugRuleJobId.value) return ''
  const matched = (batchJobDebugSnapshot.value?.rules || []).find(
    (rule) => rule.rule_job_id === selectedDebugRuleJobId.value,
  )
  if (!matched) return ''
  return `${matched.rule_code} · ${matched.rule_name}`
})

const selectedCluster = computed(() => {
  if (!selectedClusterKey.value) return null
  return (
    (resultAggregation.value?.clusters || []).find(
      (cluster) => cluster.cluster_key === selectedClusterKey.value,
    ) || null
  )
})

function resolveIssueRecordKey(item: Pick<SichuanBatchIssueItem, 'visit_id' | 'record_id'>) {
  const visitId = String(item.visit_id || '').trim()
  const recordId = String(item.record_id || '').trim()
  return visitId || recordId || 'unknown-record'
}

function resolveIssueRecordLabel(item: SichuanBatchIssueItem) {
  const patientName = String(item.patient_name || '').trim()
  const recordId = String(item.record_id || '').trim()
  const visitId = String(item.visit_id || '').trim()
  if (patientName && recordId && patientName !== recordId) return `${patientName} · ${recordId}`
  if (patientName) return patientName
  if (recordId) return `病历 ${recordId}`
  if (visitId) return `病历 ${visitId}`
  return '未返回病历标识'
}

function resolveIssueRecordMeta(item: SichuanBatchIssueItem) {
  const values = [
    String(item.department || '').trim(),
    String(item.visit_id || '').trim() ? `visit_id ${String(item.visit_id).trim()}` : '',
    String(item.record_id || '').trim() ? `记录 ${String(item.record_id).trim()}` : '',
  ].filter(Boolean)
  return Array.from(new Set(values)).join(' · ')
}

function createIssueRecordGroup<T extends SichuanBatchIssueItem>(
  key: string,
  item: T,
): IssueRecordGroup<T> {
  return {
    key,
    label: resolveIssueRecordLabel(item),
    meta: resolveIssueRecordMeta(item),
    total: 0,
    nonCompliant: 0,
    dataGap: 0,
    uncertain: 0,
    technicalError: 0,
    items: [],
  }
}

function buildIssueRecordGroups<T extends SichuanBatchIssueItem>(
  items: T[],
): Array<IssueRecordGroup<T>> {
  const map = new Map<string, IssueRecordGroup<T>>()
  items.forEach((item) => {
    const key = resolveIssueRecordKey(item)
    if (!map.has(key)) {
      map.set(key, createIssueRecordGroup(key, item))
    }
    const group = map.get(key)
    if (!group) return
    group.items.push(item)
    group.total += 1
    const status = normalizeLuxianStatusKey(
      item.result_status || item.status || item.display_status,
    )
    if (status === 'non_compliant') {
      group.nonCompliant += 1
    }
    if (status === 'data_gap') group.dataGap += 1
    if (status === 'uncertain' || status === 'ai_suggested_non_compliant') group.uncertain += 1
    if (status === 'technical_error') group.technicalError += 1
  })
  return Array.from(map.values())
}

function resolveIssueResultSortRank(item: Partial<SichuanBatchIssueItem>): number {
  const status = normalizeLuxianStatusKey(item.result_status || item.status || item.display_status)
  const index = ISSUE_RESULT_DISPLAY_STATUS_ORDER.indexOf(status)
  return index >= 0 ? index : ISSUE_RESULT_DISPLAY_STATUS_ORDER.length
}

function sortIssueItemsForBusinessDisplay<T extends SichuanBatchIssueItem>(items: T[]): T[] {
  return [...items].sort((left, right) => {
    const statusRank = resolveIssueResultSortRank(left) - resolveIssueResultSortRank(right)
    if (statusRank !== 0) return statusRank
    const leftRule = String(left.rule_code || left.rule_id || '').trim()
    const rightRule = String(right.rule_code || right.rule_id || '').trim()
    if (leftRule !== rightRule) return leftRule.localeCompare(rightRule, 'zh-Hans-CN')
    return String(left.record_id || left.visit_id || '').localeCompare(
      String(right.record_id || right.visit_id || ''),
      'zh-Hans-CN',
    )
  })
}

const displayIssueItemsBeforeRecordFilter = computed<SichuanBatchIssueItem[]>(() => {
  const items = issueItems.value.filter((item) => {
    if (!selectedDebugRuleJobId.value) return true
    const itemRuleJobId = String(item.rule_job_id || '').trim()
    return itemRuleJobId === selectedDebugRuleJobId.value
  })
  const cluster = selectedCluster.value
  if (!cluster) return items
  return items.filter((item) => matchIssueItemWithCluster(item, cluster))
})

const issueRecordGroups = computed(() =>
  buildIssueRecordGroups(displayIssueItemsBeforeRecordFilter.value),
)

const issueRecordTotalCount = computed(() =>
  issueRecordGroups.value.reduce((sum, group) => sum + group.total, 0),
)

const isMultiRecordIssueMode = computed(() => issueRecordGroups.value.length > 1)
const isSingleRecordIssueMode = computed(
  () => issueViewMode.value === 'business' && issueRecordGroups.value.length <= 1,
)

const displayIssueItems = computed<SichuanBatchIssueItem[]>(() => {
  let items = displayIssueItemsBeforeRecordFilter.value
  if (selectedIssueRecordKey.value === ALL_RECORDS_KEY) {
    return sortIssueItemsForBusinessDisplay(items)
  }
  const exists = issueRecordGroups.value.some((group) => group.key === selectedIssueRecordKey.value)
  if (exists) {
    items = items.filter((item) => resolveIssueRecordKey(item) === selectedIssueRecordKey.value)
  } else if (issueRecordGroups.value.length > 1) {
    const fallbackKey = issueRecordGroups.value[0]?.key
    if (fallbackKey) {
      items = items.filter((item) => resolveIssueRecordKey(item) === fallbackKey)
    }
  }
  return sortIssueItemsForBusinessDisplay(items)
})

const noIssueEvidenceSourceItems = computed<SichuanBatchIssueItem[]>(() => {
  const baseFilter: StructuredQCFilterState = {
    ...issueFilter.value,
    statusList: ['compliant', 'not_applicable'] satisfies StructuredQCStatus[],
  }
  let items = filterStructuredQCIssues(scopedStructuredIssues.value, baseFilter)
  if (!showAllStatuses.value) {
    items = items.filter((item) => !item.internalOnly)
  }
  let mappedItems = items.map(mapStructuredIssueToBatchIssueItem)
  if (selectedDebugRuleJobId.value) {
    mappedItems = mappedItems.filter((item) => {
      const itemRuleJobId = String(item.rule_job_id || '').trim()
      return itemRuleJobId === selectedDebugRuleJobId.value
    })
  }
  const cluster = selectedCluster.value
  if (cluster) {
    mappedItems = mappedItems.filter((item) => matchIssueItemWithCluster(item, cluster))
  }
  if (
    selectedIssueRecordKey.value &&
    selectedIssueRecordKey.value !== ALL_RECORDS_KEY &&
    issueRecordGroups.value.some((group) => group.key === selectedIssueRecordKey.value)
  ) {
    mappedItems = mappedItems.filter(
      (item) => resolveIssueRecordKey(item) === selectedIssueRecordKey.value,
    )
  }
  return sortIssueItemsForBusinessDisplay(mappedItems)
})

const noIssueEvidenceTotalCount = computed(() => noIssueEvidenceSourceItems.value.length)

const noIssueEvidenceItems = computed(() =>
  noIssueEvidenceSourceItems.value.slice(0, 8).map(enrichNoIssueEvidenceItem),
)

function enrichBusinessIssueCard(item: SichuanBatchIssueItem) {
  const customerEvidenceText = resolveCustomerEvidenceText(item.evidence)
  return {
    ...item,
    customer_findings_text: sanitizeCustomerVisibleText(item.findings),
    customer_suggestion_text: sanitizeCustomerVisibleText(item.suggestion),
    customer_evidence_text: customerEvidenceText,
    customer_evidence_structured: resolveStructuredText(customerEvidenceText),
    evidence_summary: resolveIssueEvidenceSummary(item),
    evidence_summary_parts: resolveIssueEvidenceSummaryParts(item),
    issue_card_class: resolveIssueCardClass(item),
  }
}

function resolveNoIssueEvidenceBasisLabel(item: Partial<SichuanBatchIssueItem>) {
  const status = normalizeLuxianStatusKey(item.result_status || item.status || item.display_status)
  if (status === 'not_applicable') return '不适用依据'
  if (status === 'compliant') return '未发现问题依据'
  return '判定依据'
}

function resolveNoIssueEvidenceBasisText(item: Partial<SichuanBatchIssueItem>) {
  const status = normalizeLuxianStatusKey(item.result_status || item.status || item.display_status)
  const structuredEvidence = resolveEvidenceChainItems(item, 320)
    .slice(0, 2)
    .map(formatEvidenceSummaryItem)
    .join('；')
  const evidenceText =
    structuredEvidence ||
    resolveIssueEvidenceSummary(item) ||
    sanitizeCustomerVisibleText(item.findings) ||
    sanitizeCustomerVisibleText(item.evidence)
  if (evidenceText && !isGenericCustomerEvidenceText(evidenceText)) {
    return truncateText(evidenceText, 220)
  }
  if (status === 'not_applicable') {
    return '本次未发现该质控点适用的强触发事实，因此未列为问题项。'
  }
  return '本次已完成该质控点检查，未发现需要整改、补资料或质控确认的结果。'
}

function enrichNoIssueEvidenceItem(item: SichuanBatchIssueItem) {
  return {
    ...item,
    no_issue_status_text:
      resolveDisplayStatusText(item) ||
      resolveStatusText(item.result_status || item.status || item.display_status),
    no_issue_basis_label: resolveNoIssueEvidenceBasisLabel(item),
    no_issue_basis_text: resolveNoIssueEvidenceBasisText(item),
  }
}

const allBusinessIssueCards = computed(() => displayIssueItems.value.map(enrichBusinessIssueCard))

const businessIssueCards = computed(() => {
  if (isSingleRecordIssueMode.value) {
    const selected =
      allBusinessIssueCards.value.find(
        (item) => resolveIssueStableKey(item) === selectedBusinessIssueKey.value,
      ) || allBusinessIssueCards.value[0]
    return selected ? [selected] : []
  }
  const startIndex = (issuePagination.current - 1) * issuePagination.pageSize
  return displayIssueItems.value
    .slice(startIndex, startIndex + issuePagination.pageSize)
    .map(enrichBusinessIssueCard)
})

const selectedBusinessIssueCard = computed(() => businessIssueCards.value[0] || null)

const selectedIssuePatientContext = computed(() => {
  const item = selectedBusinessIssueCard.value
  if (!item) return null
  const recordId = String(item.record_id || item.visit_id || item.patient_id || '-').trim() || '-'
  const patientName = String(item.patient_name || '').trim() || '未返回患者'
  const department = String(item.department || '').trim() || '未返回科室'
  const documentType =
    String(item.target_document_type || item.document_type || '').trim() || '未知文书域'
  const initial = patientName && patientName !== '未返回患者' ? patientName.slice(0, 1) : '病'
  return {
    recordId,
    patientName,
    department,
    documentType,
    initial,
  }
})

const businessIssueCardGroups = computed(() => buildIssueRecordGroups(businessIssueCards.value))

const shouldShowIssueRecordGroupHeader = computed(
  () =>
    isMultiRecordIssueMode.value ||
    (selectedIssueRecordKey.value !== ALL_RECORDS_KEY && !isSingleRecordIssueMode.value),
)

const singleIssueContext = computed(() => {
  if (!isSingleRecordIssueMode.value) return null
  return buildIssueRecordGroups(displayIssueItems.value)[0] || issueRecordGroups.value[0] || null
})

const singleIssueNavGroups = computed(() => {
  const groups = [
    {
      key: 'non_compliant',
      title: '优先处理：确定问题',
      className: 'issue-review-nav-group--danger',
      items: [] as SichuanBatchIssueItem[],
    },
    {
      key: 'data_gap',
      title: '需补资料：数据不足',
      className: 'issue-review-nav-group--warning',
      items: [] as SichuanBatchIssueItem[],
    },
    {
      key: 'uncertain',
      title: 'AI判断：建议确认',
      className: 'issue-review-nav-group--review',
      items: [] as SichuanBatchIssueItem[],
    },
    {
      key: 'not_applicable',
      title: '无需处理：不适用',
      className: 'issue-review-nav-group--muted',
      items: [] as SichuanBatchIssueItem[],
    },
    {
      key: 'other',
      title: '其他结果',
      className: 'issue-review-nav-group--muted',
      items: [] as SichuanBatchIssueItem[],
    },
  ]
  const groupMap = new Map(groups.map((group) => [group.key, group]))
  displayIssueItems.value.forEach((item) => {
    const status = normalizeLuxianStatusKey(
      item.result_status || item.status || item.display_status,
    )
    const group =
      groupMap.get(
        status === 'technical_error'
          ? 'non_compliant'
          : status === 'ai_suggested_non_compliant'
            ? 'uncertain'
            : status === 'ai_suggested_compliant'
              ? 'not_applicable'
              : status === 'not_executed'
                ? 'uncertain'
                : status,
      ) || groupMap.get('other')
    group?.items.push(item)
  })
  return groups.filter((group) => group.items.length > 0)
})

function selectBusinessIssue(item: SichuanBatchIssueItem) {
  selectedBusinessIssueKey.value = resolveIssueStableKey(item)
}

function resolveIssueReviewNavClass(item: SichuanBatchIssueItem) {
  const status = normalizeLuxianStatusKey(item.result_status || item.status || item.display_status)
  if (status === 'non_compliant') return 'issue-review-nav-item--danger'
  if (status === 'technical_error') return 'issue-review-nav-item--error'
  if (status === 'data_gap' || status === 'uncertain' || status === 'ai_suggested_non_compliant')
    return 'issue-review-nav-item--warning'
  if (status === 'not_executed' || status === 'not_applicable')
    return 'issue-review-nav-item--muted'
  if (status === 'compliant' || status === 'ai_suggested_compliant')
    return 'issue-review-nav-item--ok'
  return ''
}

function syncSelectedIssueRecord(groups = issueRecordGroups.value) {
  if (groups.length > 1) {
    const hasSelected = groups.some((group) => group.key === selectedIssueRecordKey.value)
    if (!hasSelected || selectedIssueRecordKey.value === ALL_RECORDS_KEY) {
      selectedIssueRecordKey.value = groups[0]?.key || ALL_RECORDS_KEY
    }
    return
  }
  if (selectedIssueRecordKey.value !== ALL_RECORDS_KEY) {
    selectedIssueRecordKey.value = ALL_RECORDS_KEY
  }
}

function syncSelectedBusinessIssue(items = displayIssueItems.value) {
  if (!items.length) {
    selectedBusinessIssueKey.value = ''
    return
  }
  const hasSelected = items.some(
    (item) => resolveIssueStableKey(item) === selectedBusinessIssueKey.value,
  )
  if (!hasSelected) {
    selectedBusinessIssueKey.value = resolveIssueStableKey(items[0])
  }
}

const linkedIssueRowKey = computed(() => {
  if (!selectedCluster.value) return ''
  return resolveIssueStableKey(displayIssueItems.value[0])
})

const displayRuleResults = computed(() => {
  const items = resolvedRuleResults.value
  if (!selectedDebugRuleJobId.value) return items
  return items.filter((item) => String(item.id || '').trim() === selectedDebugRuleJobId.value)
})

const progressSummary = computed(() => {
  const progressCandidate =
    props.batchJobDetail?.progress || props.batchJobDetail?.summary?.progress || {}
  const progress =
    progressCandidate && typeof progressCandidate === 'object'
      ? (progressCandidate as Record<string, unknown>)
      : {}
  const totalRecords = Number(progress.total_records || props.batchJobDetail?.total_records || 0)
  const processedRecords = Number(
    progress.processed_records || (props.batchJobDetail?.status === 'completed' ? totalRecords : 0),
  )
  const rawRuleCount = Number(progress.rule_count || props.batchJobDetail?.rule_count || 0)
  const ruleCount = Math.max(1, rawRuleCount || resolvedRuleResults.value.length || 1)
  const ruleIndex = Math.min(
    ruleCount,
    Math.max(
      0,
      Number(progress.rule_index || (props.batchJobDetail?.status === 'completed' ? ruleCount : 0)),
    ),
  )
  const status = String(props.batchJobDetail?.status || '')
  const stepKey = String(progress.step_key || status || 'queued').toLowerCase()
  let percent = 0
  if (totalRecords > 0) {
    percent = Math.min(100, Math.round((processedRecords / totalRecords) * 100))
  } else if (status === 'completed') {
    percent = 100
  }
  const progressStatus =
    status === 'failed' ? 'exception' : status === 'completed' ? 'success' : 'active'
  return {
    percent,
    processedRecords,
    totalRecords,
    ruleIndex,
    ruleCount,
    stepLabel: PROGRESS_STEP_LABEL_MAP[stepKey] || stepKey || '执行中',
    status: progressStatus as 'active' | 'success' | 'exception',
  }
})

const streamState = computed(() => {
  const state = props.batchJobDetail?.summary?.stream_state
  return state && typeof state === 'object' ? state : null
})

const isRunningBatchJob = computed(() => {
  const status = String(props.batchJobDetail?.status || '')
    .trim()
    .toLowerCase()
  return status === 'queued' || status === 'running'
})

const isWaitingFirstResult = computed(
  () =>
    isRunningBatchJob.value &&
    issueItems.value.length === 0 &&
    (progressSummary.value?.processedRecords || 0) === 0,
)

const currentStreamRecordLabel = computed(() => {
  const state = streamState.value
  const latestVisitId = String(state?.latest_visit_id || '').trim()
  const latestRecordId = String(state?.latest_record_id || '').trim()
  return latestVisitId || latestRecordId || ''
})

const streamUpdatedAtText = computed(() => {
  const updatedAt = streamState.value?.updated_at || props.batchJobDetail?.updated_at
  if (!updatedAt) return ''
  return props.formatDateTime(updatedAt)
})

const liveStartedAtMs = computed(() => {
  const startValue = props.batchJobDetail?.started_at || streamState.value?.started_at
  return parseBackendDateTimeMs(startValue)
})

const liveElapsedSeconds = computed(() => {
  const detail = props.batchJobDetail
  if (!detail) return 0
  const finalSeconds = Number(
    detail.summary?.wall_clock_time ?? detail.wall_clock_time ?? detail.total_processing_time ?? 0,
  )
  if (!isRunningBatchJob.value) return finalSeconds
  if (!liveStartedAtMs.value) return finalSeconds
  return Math.max(finalSeconds, (liveNow.value - liveStartedAtMs.value) / 1000)
})

const liveElapsedText = computed(() => formatProcessingTime(liveElapsedSeconds.value))
const liveElapsedLabel = computed(() => {
  if (isRunningBatchJob.value && !liveStartedAtMs.value && liveElapsedSeconds.value <= 0) {
    return '运行中'
  }
  return `运行 ${liveElapsedText.value}`
})

const incrementalResultTip = computed(() => {
  if (!isRunningBatchJob.value) return ''
  if (issueItems.value.length > 0) {
    return `已返回 ${issueItems.value.length} 条结果，任务仍在继续，后续病历完成后会自动追加。`
  }
  if ((progressSummary.value?.processedRecords || 0) > 0) {
    return '已完成部分病历，当前暂无需要展示的问题项，系统仍在继续质控。'
  }
  return isLuxianNativeSliceBatchJob.value
    ? '正在等待首份病历结果，系统正在执行质控，结果会自动出现。'
    : '正在等待首份病历结果，模型仍在处理，结果会自动出现。'
})

const waitingFirstResultDescription = computed(() =>
  isLuxianNativeSliceBatchJob.value
    ? '系统正在执行首份病历质控，结果会自动出现在这里。'
    : '模型仍在处理首份病历，结果会自动出现在这里。',
)

const executionSummary = computed(() => {
  const summary = props.batchJobDetail?.summary
  const fromSummary = summary?.executor_breakdown
  const cacheFromSummary = summary?.cache_breakdown
  if (fromSummary || cacheFromSummary) {
    return {
      programCount: Number(fromSummary?.program || 0),
      llmCount: Number(fromSummary?.llm || 0),
      cacheHit: Number(cacheFromSummary?.hit || 0),
      cacheMiss: Number(cacheFromSummary?.miss || 0),
    }
  }
  const items = issueItems.value
  if (!items.length) return null
  const programCount = items.filter(
    (item) => String(item.executor_type || '').toLowerCase() === 'program',
  ).length
  const llmCount = items.filter(
    (item) => String(item.executor_type || '').toLowerCase() !== 'program',
  ).length
  const cacheHit = items.filter((item) => item.cache_hit === true).length
  const cacheMiss = items.length - cacheHit
  return { programCount, llmCount, cacheHit, cacheMiss }
})

const isPostprocessedFormalResult = computed(() => {
  const detail = props.batchJobDetail
  const summary = detail?.summary
  const filters = (detail?.filters || {}) as Record<string, unknown>
  return Boolean(
    summary?.postprocess_summary ||
      summary?.display_status_counts ||
      filters.validation_mode === 'formal_fast_screen_full' ||
      filters.rule_set_key === 'sc_content_full_v1' ||
      summary?.rule_set_key === 'sc_content_full_v1',
  )
})

const batchJobFilters = computed<Record<string, unknown>>(() => {
  const filters = props.batchJobDetail?.filters
  return filters && typeof filters === 'object' ? filters : {}
})

const isLuxian0609BatchJob = computed(() => {
  const detail = props.batchJobDetail
  const summary = detail?.summary
  const filters = batchJobFilters.value
  return (
    String(detail?.rule_set_key || summary?.rule_set_key || filters.rule_set_key || '')
      .trim()
      .toLowerCase() === LUXIAN_0609_RULE_SET_KEY
  )
})

const luxianSelectedRuleIds = computed(() => {
  const filters = batchJobFilters.value
  return normalizeStringList(filters.selected_rule_ids).length
    ? normalizeStringList(filters.selected_rule_ids)
    : normalizeStringList(filters.scoped_customer_rule_ids)
})

const luxianRecordRuleMapEntries = computed(() => {
  const rawMap = batchJobFilters.value.record_rule_map
  if (!rawMap || typeof rawMap !== 'object' || Array.isArray(rawMap)) return []
  return Object.entries(rawMap as Record<string, unknown>)
})

const isLuxianScopedRun = computed(
  () => luxianSelectedRuleIds.value.length > 0 || luxianRecordRuleMapEntries.value.length > 0,
)

const luxianScopeModeLabel = computed(() =>
  isLuxianScopedRun.value ? '选定质控点验证' : '全量 0609 规则集',
)

const luxianSelectedRuleIdsPreview = computed(() => luxianSelectedRuleIds.value.slice(0, 12))

const luxianExecutionRuleIds = computed(() => {
  const filters = batchJobFilters.value
  return normalizeStringList(filters.rule_ids).length
    ? normalizeStringList(filters.rule_ids)
    : normalizeStringList(props.batchJobDetail?.draft_ids)
})

const isLuxianNativeSliceBatchJob = computed(() => {
  const executionRuleIds = luxianExecutionRuleIds.value.map((ruleId) => ruleId.toUpperCase())
  return (
    isLuxian0609BatchJob.value &&
    executionRuleIds.length > 0 &&
    executionRuleIds.every((ruleId) => LUXIAN_0609_NATIVE_RULE_IDS.has(ruleId))
  )
})

const luxianCustomerRuleCount = computed(() => {
  const detail = props.batchJobDetail
  const summary = detail?.summary
  const filters = batchJobFilters.value
  return (
    optionalNumber(detail?.customer_rule_count) ??
    optionalNumber(summary?.customer_rule_count) ??
    optionalNumber(filters.customer_rule_count) ??
    luxianSelectedRuleIds.value.length
  )
})

const luxianExecutionRuleCount = computed(() => {
  const detail = props.batchJobDetail
  const summary = detail?.summary
  const filters = batchJobFilters.value
  return (
    optionalNumber(detail?.execution_rule_count) ??
    optionalNumber(summary?.execution_rule_count) ??
    optionalNumber(filters.execution_rule_count) ??
    luxianExecutionRuleIds.value.length
  )
})

const luxianGenericRuleCount = computed(() => {
  const detail = props.batchJobDetail
  const summary = detail?.summary
  const filters = batchJobFilters.value
  return (
    optionalNumber(summary?.rule_count) ??
    optionalNumber(detail?.rule_count) ??
    optionalNumber(filters.rule_count)
  )
})

watch(
  issueRecordGroups,
  (groups) => {
    syncSelectedIssueRecord(groups)
  },
  { immediate: true },
)

watch(
  displayIssueItems,
  (items) => {
    syncSelectedBusinessIssue(items)
  },
  { immediate: true },
)

const luxianRecordRuleMapSummary = computed(() => {
  const entries = luxianRecordRuleMapEntries.value
  if (!entries.length)
    return isLuxianScopedRun.value
      ? '未返回'
      : isLuxianNativeSliceBatchJob.value
        ? '全量运行，不按单病历限定质控点'
        : '全量运行，不按单病历限定执行规则'
  const uniqueRules = new Set<string>()
  entries.forEach(([, ruleIds]) => {
    normalizeStringList(ruleIds).forEach((ruleId) => uniqueRules.add(ruleId))
  })
  const sample = entries
    .slice(0, 2)
    .map(
      ([recordId, ruleIds]) =>
        `${recordId}: ${normalizeStringList(ruleIds).length || 0} 条${isLuxianNativeSliceBatchJob.value ? '质控点' : '执行规则'}`,
    )
    .join('；')
  const suffix = entries.length > 2 ? `；另有 ${entries.length - 2} 份病历` : ''
  return isLuxianNativeSliceBatchJob.value
    ? `${entries.length} 份病历执行 ${uniqueRules.size} 个质控点。${sample}${suffix}`
    : `${entries.length} 份病历映射到 ${uniqueRules.size} 条底层执行规则。${sample}${suffix}`
})

const luxianScopeCards = computed(() => [
  {
    key: 'customer',
    label: '客户质控点数',
    value: luxianCustomerRuleCount.value > 0 ? luxianCustomerRuleCount.value : '未返回',
    desc: isLuxianScopedRun.value ? '来自本次选定的 LX0609 质控点' : '全量 0609 客户质控点',
  },
  {
    key: 'execution',
    label: isLuxianNativeSliceBatchJob.value ? '本次执行质控点数' : '底层执行规则数',
    value: luxianExecutionRuleCount.value > 0 ? luxianExecutionRuleCount.value : '未返回',
    desc: isLuxianNativeSliceBatchJob.value
      ? '系统实际执行的 LX0609 质控点'
      : '系统实际调用的执行规则',
  },
  {
    key: 'rule-count',
    label: '任务规则数',
    value: luxianGenericRuleCount.value !== null ? luxianGenericRuleCount.value : '未返回',
    desc: '任务记录中的规则数量',
  },
])

const luxianStatusDistribution = computed(() => {
  const counts = new Map<string, number>()
  const sourceItems = scopedStructuredIssues.value.length
    ? scopedStructuredIssues.value.map((item) => ({ status: item.status }))
    : (props.batchJobDetail?.items || []).map((item) => ({
        status: item.result_status || item.status || item.display_status,
      }))
  sourceItems.forEach((item) => {
    const key = normalizeLuxianStatusKey(item.status)
    if (!key) return
    counts.set(key, Number(counts.get(key) || 0) + 1)
  })
  return LUXIAN_0609_STATUS_ORDER.map((key) => ({
    key,
    label: resolveEvidenceStatusText(key),
    value: Number(counts.get(key) || 0),
    className:
      key === 'non_compliant' || key === 'technical_error'
        ? 'is-danger'
        : key === 'data_gap' ||
            key === 'uncertain' ||
            key === 'ai_suggested_non_compliant' ||
            key === 'not_executed'
          ? 'is-warning'
          : key === 'compliant' || key === 'ai_suggested_compliant'
            ? 'is-success'
            : 'is-muted',
  }))
})

const showResultReviewOverview = computed(
  () => isLuxian0609BatchJob.value && issueViewMode.value === 'business',
)

const resultReviewOverviewTitle = computed(() => {
  const name = String(props.batchJobDetail?.rule_name || '').trim()
  if (name) return name
  const code = String(props.batchJobDetail?.rule_code || '').trim()
  return code || '泸县0609质控点验证任务'
})

const resultReviewOutcomeText = computed(() => {
  const heroTitle = String(statusHero.value?.title || '').trim()
  if (heroTitle) return heroTitle
  return '当前展示泸县0609质控点验证结果。'
})

const resultReviewScopeText = computed(() => {
  if (isLuxianScopedRun.value) {
    const countText = luxianSelectedRuleIds.value.length
      ? `已限定 ${luxianSelectedRuleIds.value.length} 个 LX0609 质控点`
      : '已限定质控点，具体 ID 未返回'
    return `${countText}；${luxianRecordRuleMapSummary.value}`
  }
  return `未限定，执行全量 0609 质控点；${luxianRecordRuleMapSummary.value}`
})

const resultReviewRecordCount = computed(() => {
  const summary = props.batchJobDetail?.summary
  const filters = batchJobFilters.value
  const authoritativeCount =
    optionalNumber(summary?.total_records) ??
    optionalNumber(filters.dedup_record_count) ??
    optionalNumber(props.batchJobDetail?.total_records)
  if (authoritativeCount !== null) return authoritativeCount
  if (issueRecordGroups.value.length > 0) return issueRecordGroups.value.length
  const selectedRecordIds = Array.isArray(filters.selected_record_ids)
    ? filters.selected_record_ids
    : []
  return selectedRecordIds.length
})

const resultReviewResultCount = computed(() => {
  if (displayIssueItemsBeforeRecordFilter.value.length > 0) {
    return displayIssueItemsBeforeRecordFilter.value.length
  }
  return Number(
    props.batchJobDetail?.summary?.processed_rule_count ??
      props.batchJobDetail?.summary?.rule_count ??
      props.batchJobDetail?.rule_count ??
      0,
  )
})

const resultReviewCustomerRuleCount = computed(() => {
  if (luxianCustomerRuleCount.value > 0) return luxianCustomerRuleCount.value
  if (luxianSelectedRuleIds.value.length > 0) return luxianSelectedRuleIds.value.length
  return resultReviewResultCount.value
})

const resultReviewStatusPills = computed(() =>
  luxianStatusDistribution.value.filter(
    (item) =>
      item.value > 0 ||
      [
        'non_compliant',
        'ai_suggested_non_compliant',
        'data_gap',
        'uncertain',
        'not_applicable',
      ].includes(item.key),
  ),
)

const resultReviewSingleRecordSummary = computed(() => {
  const context = singleIssueContext.value
  if (!context) return issueFocusSummary.value
  const parts = [
    `${context.total} 条质控点结果`,
    context.nonCompliant > 0 ? `确定问题 ${context.nonCompliant}` : '',
    context.dataGap > 0 ? `数据不足 ${context.dataGap}` : '',
    context.uncertain > 0 ? `AI判断 ${context.uncertain}` : '',
  ].filter(Boolean)
  return parts.join(' · ')
})

const luxianReviewReport = computed<Luxian0609ReviewReport | null>(() => {
  const report = props.batchJobDetail?.summary?.review_report
  return report && typeof report === 'object' ? report : null
})

const luxianReviewFindings = computed<Luxian0609ReviewFinding[]>(
  () => luxianReviewReport.value?.findings?.slice(0, 8) || [],
)

const luxianReviewSummaryText = computed(() => {
  const summary = luxianReviewReport.value?.summary
  const total = Number(summary?.total_findings || 0)
  if (!total) return '暂无高风险建议'
  return `共 ${total} 条建议：P0 ${Number(summary?.p0 || 0)} · P1 ${Number(summary?.p1 || 0)} · P2 ${Number(summary?.p2 || 0)}`
})

function mapStructuredStatusLabel(status?: string): string {
  const normalized = String(status || '')
    .trim()
    .toLowerCase()
  if (normalized === 'non_compliant') return '不合规'
  if (normalized === 'ai_suggested_non_compliant') return 'AI判断：疑似问题'
  if (normalized === 'ai_suggested_compliant') return 'AI判断：未见问题'
  if (normalized === 'compliant') return '合规'
  if (normalized === 'not_applicable') return '不适用'
  if (normalized === 'data_gap') return '数据不足'
  if (normalized === 'uncertain') return 'AI判断'
  if (normalized === 'not_executed') return '未执行'
  if (normalized === 'technical_error') return '技术异常'
  return status || 'AI判断'
}

function isConfirmedDefectItem(item: SichuanBatchIssueItem): boolean {
  if (isLuxian0609BatchJob.value) {
    return (
      normalizeLuxianStatusKey(item.result_status || item.status || item.display_status) ===
      'non_compliant'
    )
  }
  if (isPostprocessedFormalResult.value) {
    return item.can_show_as_defect === true || item.display_status === 'confirmed_defect'
  }
  return item.status === 'non_compliant'
}

function isNeedsReviewItem(item: SichuanBatchIssueItem): boolean {
  if (isLuxian0609BatchJob.value) {
    return (
      normalizeLuxianStatusKey(item.result_status || item.status || item.display_status) ===
        'uncertain' ||
      normalizeLuxianStatusKey(item.result_status || item.status || item.display_status) ===
        'ai_suggested_non_compliant'
    )
  }
  if (isPostprocessedFormalResult.value) {
    return false
  }
  return item.status === 'uncertain'
}

function isDataQualityGapItem(item: SichuanBatchIssueItem): boolean {
  if (isLuxian0609BatchJob.value) {
    return (
      normalizeLuxianStatusKey(item.result_status || item.status || item.display_status) ===
      'data_gap'
    )
  }
  return isPostprocessedFormalResult.value && item.display_status === 'data_quality_gap'
}

function isRejectedBySystemItem(item: SichuanBatchIssueItem): boolean {
  return isPostprocessedFormalResult.value && item.display_status === 'rejected_by_system'
}

const ruleLevelSummary = computed(() => {
  const totalRules = Math.max(
    0,
    Number(props.batchJobDetail?.summary?.rule_count ?? props.batchJobDetail?.rule_count ?? 0) ||
      resolvedRuleResults.value.length,
  )
  const issueItemsList = issueItems.value
  const summary = props.batchJobDetail?.summary
  const nonCompliantCount = issueItemsList.filter((item) => isConfirmedDefectItem(item)).length
  const uncertainCount = issueItemsList.filter((item) => isNeedsReviewItem(item)).length
  const dataQualityGapCount = issueItemsList.filter((item) => isDataQualityGapItem(item)).length
  const technicalErrorCount = isPostprocessedFormalResult.value
    ? Number(
        summary?.technical_error_internal_count ??
          summary?.postprocess_summary?.technical_error_internal_count ??
          issueItemsList.filter((item) => item.display_status === 'technical_error_internal')
            .length,
      )
    : issueItemsList.filter(
        (item) =>
          normalizeLuxianStatusKey(item.result_status || item.status || item.display_status) ===
          'technical_error',
      ).length
  const rejectedBySystemCount = isPostprocessedFormalResult.value
    ? Number(
        summary?.rejected_by_system_count ??
          summary?.postprocess_summary?.rejected_by_system_count ??
          0,
      )
    : issueItemsList.filter((item) => isRejectedBySystemItem(item)).length
  const focusCount = nonCompliantCount + uncertainCount + dataQualityGapCount
  const docIssueCount = new Set(
    issueItemsList
      .filter((item) => isConfirmedDefectItem(item))
      .map((item) => String(item.record_id || item.visit_id || '').trim())
      .filter(Boolean),
  ).size
  const docUncertainCount = new Set(
    issueItemsList
      .filter((item) => isNeedsReviewItem(item))
      .map((item) => String(item.record_id || item.visit_id || '').trim())
      .filter(Boolean),
  ).size
  const processingTimeSeconds = Number(
    props.batchJobDetail?.summary?.wall_clock_time ??
      props.batchJobDetail?.wall_clock_time ??
      props.batchJobDetail?.total_processing_time ??
      0,
  )
  const modelProcessingTimeSeconds = Number(
    props.batchJobDetail?.summary?.total_processing_time ??
      props.batchJobDetail?.total_processing_time ??
      0,
  )
  return {
    totalRules,
    nonCompliantCount,
    uncertainCount,
    dataQualityGapCount,
    rejectedBySystemCount,
    technicalErrorCount,
    focusCount,
    docIssueCount,
    docUncertainCount,
    processingTimeSeconds,
    modelProcessingTimeSeconds,
  }
})

const statusHero = computed(() => {
  const detail = props.batchJobDetail
  if (!detail) return null
  const status = String(detail.status || '')
    .trim()
    .toLowerCase()
  const processedRecords = progressSummary.value?.processedRecords ?? 0
  const totalRecords = progressSummary.value?.totalRecords ?? Number(detail.total_records || 0)
  const issueRecords = ruleLevelSummary.value.nonCompliantCount
  const uncertainRecords = ruleLevelSummary.value.uncertainCount
  const dataQualityGapRecords = ruleLevelSummary.value.dataQualityGapCount
  const finishedAt = detail.finished_at || detail.updated_at
  const meta: string[] = []
  if (totalRecords > 0) {
    meta.push(`已处理 ${processedRecords}/${totalRecords} 份病历`)
  }
  if ((progressSummary.value?.ruleCount || 0) > 0) {
    meta.push(
      `规则 ${progressSummary.value?.ruleIndex || 0}/${progressSummary.value?.ruleCount || 0}`,
    )
  }
  if (status === 'completed') {
    if (ruleLevelSummary.value.processingTimeSeconds > 0) {
      meta.push(`总耗时 ${formatProcessingTime(ruleLevelSummary.value.processingTimeSeconds)}`)
    }
    if (
      isPostprocessedFormalResult.value &&
      !isLuxianNativeSliceBatchJob.value &&
      ruleLevelSummary.value.modelProcessingTimeSeconds > 0
    ) {
      meta.push(
        `累计模型处理耗时 ${formatProcessingTime(ruleLevelSummary.value.modelProcessingTimeSeconds)}`,
      )
    }
    if (finishedAt) {
      meta.push(`完成于 ${props.formatDateTime(finishedAt)}`)
    }
  }
  if (status === 'failed' && detail.error_message) {
    meta.push('请优先查看下方失败原因与调试快照')
  }
  if (status === 'canceled' && finishedAt) {
    meta.push(`停止于 ${props.formatDateTime(finishedAt)}`)
  }
  if (status === 'queued') {
    return {
      tone: 'queued',
      title: '任务已创建，等待执行',
      description:
        '系统已接收任务，正在分配执行资源。抽屉内容会自动刷新，不需要手动反复关闭再打开。',
      meta,
      pulse: true,
    }
  }
  if (status === 'running') {
    return {
      tone: 'running',
      title: '任务执行中，请直接关注这里的进度',
      description: '结果会随着轮询自动刷新。任务结束后会弹出强提醒，并保留最终结果在当前抽屉中。',
      meta,
      pulse: true,
    }
  }
  if (status === 'completed') {
    const focusCount =
      issueRecords +
      uncertainRecords +
      (isLuxian0609BatchJob.value || isPostprocessedFormalResult.value ? dataQualityGapRecords : 0)
    if (isLuxian0609BatchJob.value) {
      return {
        tone: 'completed',
        title:
          focusCount > 0
            ? '任务已完成，已发现泸县0609质控点问题'
            : '任务已完成，本次未发现泸县0609质控点问题',
        description:
          focusCount > 0
            ? `请查看下方客户质控点明细：不合规 ${issueRecords} 条，数据不足 ${dataQualityGapRecords} 条，AI判断 ${uncertainRecords} 条。`
            : '当前所选 LX0609 质控点未返回不合规、数据不足或 AI 判断结果。',
        meta,
        pulse: false,
      }
    }
    return {
      tone: 'completed',
      title: focusCount > 0 ? '任务已完成，已产出可处理问题' : '任务已完成，本次未发现问题',
      description:
        focusCount > 0
          ? isPostprocessedFormalResult.value
            ? '请优先查看下方四层准入明细，确认缺陷可直接处理，数据缺口需排查链路。'
            : '请优先查看下方“问题/AI判断明细”，直接判断需要确认或整改的质控点。'
          : '本次批量质控已执行完毕，当前规则集下没有发现需要处理的问题。',
      meta,
      pulse: false,
    }
  }
  if (status === 'failed') {
    return {
      tone: 'failed',
      title: '任务执行失败，需要人工处理',
      description: detail.error_message || '后端在执行中断，请检查失败原因，必要时点击重试。',
      meta,
      pulse: false,
    }
  }
  return {
    tone: 'canceled',
    title: '任务已取消',
    description: '该任务已被手动停止，不会继续产生新的质控结果。',
    meta,
    pulse: false,
  }
})

const primarySummaryCards = computed(() => {
  const summary = props.batchJobDetail?.summary
  const totalRecords = Number(
    optionalNumber(summary?.total_records) ??
      optionalNumber(batchJobFilters.value.dedup_record_count) ??
      optionalNumber(props.batchJobDetail?.total_records) ??
      0,
  )
  const successCount = Number(summary?.success_count ?? props.batchJobDetail?.success_count ?? 0)
  const failedRecordCount = Number(
    summary?.failed_record_count ?? props.batchJobDetail?.failed_count ?? 0,
  )
  const failedAttemptCount = Number(
    summary?.failed_count ?? props.batchJobDetail?.failed_count ?? 0,
  )
  const issueRecords = ruleLevelSummary.value.nonCompliantCount
  const uncertainRecords = ruleLevelSummary.value.uncertainCount
  const dataQualityGapRecords = ruleLevelSummary.value.dataQualityGapCount
  const rejectedBySystemRecords = ruleLevelSummary.value.rejectedBySystemCount
  const technicalErrorRecords = ruleLevelSummary.value.technicalErrorCount
  const focusCount = ruleLevelSummary.value.focusCount
  const processingTimeSeconds = isRunningBatchJob.value
    ? liveElapsedSeconds.value
    : ruleLevelSummary.value.processingTimeSeconds
  const cards = [
    { key: 'total', label: '总病历', value: totalRecords, desc: '' },
    { key: 'rules', label: '总规则', value: ruleLevelSummary.value.totalRules, desc: '' },
    { key: 'failed-records', label: '失败病历', value: failedRecordCount, desc: '去重后的病历数' },
    {
      key: 'failed-attempts',
      label: '失败次数',
      value: failedAttemptCount,
      desc: '规则执行失败总次数',
    },
    {
      key: 'issues',
      label: isPostprocessedFormalResult.value ? '确认缺陷' : '不合规规则',
      value: issueRecords,
      desc: isPostprocessedFormalResult.value ? '后处理准入后可展示为缺陷' : '',
    },
    ...(isPostprocessedFormalResult.value
      ? []
      : [
          {
            key: 'uncertain',
            label: 'AI判断规则',
            value: uncertainRecords,
            desc: '',
          },
        ]),
    ...(isPostprocessedFormalResult.value
      ? [
          { key: 'data-quality-gap', label: '数据缺口', value: dataQualityGapRecords, desc: '' },
          {
            key: 'rejected-by-system',
            label: '系统驳回',
            value: rejectedBySystemRecords,
            desc: '仅内部诊断',
          },
          {
            key: 'technical-error',
            label: '技术异常',
            value: technicalErrorRecords,
            desc: '仅内部诊断',
          },
        ]
      : []),
    { key: 'focus', label: '重点结果', value: focusCount, desc: '' },
    {
      key: 'duration',
      label: '总耗时',
      value: processingTimeSeconds > 0 ? formatProcessingTime(processingTimeSeconds) : '-',
      desc: '',
    },
    ...(isPostprocessedFormalResult.value && !isLuxianNativeSliceBatchJob.value
      ? [
          {
            key: 'model-duration',
            label: '累计模型处理耗时',
            value:
              ruleLevelSummary.value.modelProcessingTimeSeconds > 0
                ? formatProcessingTime(ruleLevelSummary.value.modelProcessingTimeSeconds)
                : '-',
            desc: '并发 pack 的模型耗时累计',
          },
        ]
      : []),
    { key: 'success', label: '执行成功', value: successCount, desc: '' },
    {
      key: 'issue-records',
      label: '涉及问题病历',
      value: ruleLevelSummary.value.docIssueCount,
      desc: '病历级去重统计',
    },
    {
      key: 'uncertain-records',
      label: '涉及AI判断病历',
      value: ruleLevelSummary.value.docUncertainCount,
      desc: '病历级去重统计',
    },
  ]
  return isPostprocessedFormalResult.value
    ? cards.filter((item) => item.key !== 'uncertain-records')
    : cards
})

const focusedSummaryCards = computed(() => {
  if (isFocusedRecordMode.value) {
    return [
      { key: 'total', label: '总病历', value: 1, desc: '当前仅展示选中病历' },
      {
        key: 'issues',
        label: isPostprocessedFormalResult.value ? '确认缺陷' : '不合规规则',
        value: issueItems.value.filter((item) => isConfirmedDefectItem(item)).length,
        desc: '',
      },
      {
        key: 'uncertain',
        label: 'AI判断规则',
        value: issueItems.value.filter((item) => isNeedsReviewItem(item)).length,
        desc: '',
      },
      ...(isPostprocessedFormalResult.value
        ? [
            {
              key: 'data-quality-gap',
              label: '数据缺口',
              value: issueItems.value.filter((item) => isDataQualityGapItem(item)).length,
              desc: '',
            },
            {
              key: 'rejected-by-system',
              label: '系统驳回',
              value: ruleLevelSummary.value.rejectedBySystemCount,
              desc: '仅内部诊断',
            },
            {
              key: 'technical-error',
              label: '技术异常',
              value: ruleLevelSummary.value.technicalErrorCount,
              desc: '仅内部诊断',
            },
          ]
        : []),
      {
        key: 'duration',
        label: '总耗时',
        value:
          ruleLevelSummary.value.processingTimeSeconds > 0
            ? formatProcessingTime(ruleLevelSummary.value.processingTimeSeconds)
            : '-',
        desc: isPostprocessedFormalResult.value ? '真实任务墙钟耗时' : '任务总耗时',
      },
    ].filter((item) => !(isPostprocessedFormalResult.value && item.key === 'uncertain'))
  }
  return primarySummaryCards.value.filter((item) =>
    [
      'total',
      'issues',
      ...(isPostprocessedFormalResult.value ? [] : ['uncertain']),
      'data-quality-gap',
      'rejected-by-system',
      'technical-error',
      'duration',
      'model-duration',
    ].includes(item.key),
  )
})

const ruleSetDisplay = computed(() => {
  const detail = props.batchJobDetail
  const summary = detail?.summary
  const filters = (detail?.filters || {}) as Record<string, unknown>
  const filterRuleIds = Array.isArray(filters.rule_ids)
    ? filters.rule_ids.filter((item) => String(item || '').trim())
    : []
  const effectiveRuleCount = Number(
    summary?.rule_count ??
      detail?.rule_count ??
      filterRuleIds.length ??
      (detail?.draft_ids || []).length ??
      0,
  )
  return {
    name:
      String(
        detail?.rule_set_name || summary?.rule_set_name || filters.rule_set_name || '',
      ).trim() || '手工选择规则',
    key: String(detail?.rule_set_key || summary?.rule_set_key || filters.rule_set_key || '').trim(),
    ruleCount: effectiveRuleCount,
    qualityProfile:
      String(
        detail?.quality_profile || summary?.quality_profile || filters.quality_profile || '',
      ).trim() || '-',
    bucketStrategy:
      String(
        detail?.bucket_strategy || summary?.bucket_strategy || filters.bucket_strategy || '',
      ).trim() || '-',
    refinedCount: Number(
      summary?.refined_rule_count ||
        summary?.refine_summary?.refined_rule_count ||
        detail?.refine_summary?.refined_rule_count ||
        0,
    ),
  }
})

const isFastScreenResult = computed(() => {
  const detail = props.batchJobDetail
  const summary = detail?.summary
  return (
    String(detail?.execution_strategy || summary?.execution_strategy || '')
      .trim()
      .toLowerCase() === 'fast_screen' ||
    String(detail?.rule_set_key || summary?.rule_set_key || '')
      .trim()
      .toLowerCase() === 'sc_content_fast_v1'
  )
})

const executionSummaryCards = computed(() => {
  if (!executionSummary.value) return []
  const summary = props.batchJobDetail?.summary
  const packMetrics = summary?.pack_metrics || {}
  const cards = [
    { key: 'program', label: 'Program执行', value: executionSummary.value.programCount, desc: '' },
    ...(isLuxianNativeSliceBatchJob.value
      ? []
      : [{ key: 'llm', label: '语义规则', value: executionSummary.value.llmCount, desc: '' }]),
    { key: 'hit', label: '缓存命中', value: executionSummary.value.cacheHit, desc: '' },
    { key: 'miss', label: '缓存未命中', value: executionSummary.value.cacheMiss, desc: '' },
  ]
  if (summary?.refine_summary || summary?.refined_rule_count) {
    cards.push({
      key: 'refined',
      label: '单条精审',
      value: Number(summary.refined_rule_count || summary.refine_summary?.refined_rule_count || 0),
      desc: '',
    })
  }
  if (packMetrics.total_packs !== undefined) {
    cards.push({
      key: 'packs',
      label: '分包数',
      value: Number(packMetrics.total_packs || 0),
      desc: '',
    })
  }
  return cards
})

const performanceProfile = computed(
  () => props.batchJobDetail?.summary?.performance_profile || null,
)

const performanceProfileCards = computed(() => {
  if (isLuxianNativeSliceBatchJob.value) return []
  const profile = performanceProfile.value
  if (!profile) return []
  const unattributedTokens = optionalNumber(profile.unattributed_tokens)
  const breakdownComplete =
    profile.token_breakdown_complete === true ||
    (unattributedTokens !== null && unattributedTokens === 0)
  return [
    {
      key: 'tokens-total',
      label: '总 Token',
      value: formatTokenNumber(profile.tokens_total ?? props.batchJobDetail?.summary?.total_tokens),
      desc: '本次任务模型服务返回的 token 总量',
    },
    {
      key: 'prompt-tokens',
      label: '输入 Token',
      value: formatTokenNumber(profile.prompt_tokens),
      desc: '可归因到输入上下文的 token',
    },
    {
      key: 'completion-tokens',
      label: '输出 Token',
      value: formatTokenNumber(profile.completion_tokens),
      desc: '可归因到模型输出的 token',
    },
    {
      key: 'unattributed-tokens',
      label: '未归因 Token',
      value: formatTokenNumber(profile.unattributed_tokens),
      desc: '模型服务未拆分到输入/输出的 token',
    },
    {
      key: 'token-breakdown-complete',
      label: 'Token 拆分',
      value: breakdownComplete ? '完整' : '有未归因',
      desc: breakdownComplete ? '输入/输出 token 已覆盖总量' : '需结合未归因 token 评估成本',
    },
  ]
})

const advancedSummaryCards = computed(() => {
  const cards = [
    ...primarySummaryCards.value.filter(
      (item) => !['total', 'issues', 'uncertain', 'failed-records'].includes(item.key),
    ),
    ...performanceProfileCards.value,
    ...executionSummaryCards.value,
    {
      key: 'rule-results',
      label: '规则结果条数',
      value: resolvedRuleResults.value.length,
      desc: '',
    },
    {
      key: 'issue-items',
      label: isPostprocessedFormalResult.value ? '四层准入明细' : '问题/AI判断明细',
      value: issueItems.value.length,
      desc: '',
    },
  ]
  return cards.filter((item) => item.value !== undefined && item.value !== null)
})

const issueFocusSummary = computed(() => {
  const currentItems = displayIssueItems.value
  const total = currentItems.length
  if (!total) {
    return showAllStatuses.value ? '当前没有可展示的规则结果。' : '当前没有需要复核或整改的问题项。'
  }
  const selectedRecord = issueRecordGroups.value.find(
    (group) => group.key === selectedIssueRecordKey.value,
  )
  const scopePrefix =
    selectedRecord && selectedIssueRecordKey.value !== ALL_RECORDS_KEY
      ? `${selectedRecord.label}：`
      : ''
  const nonCompliantCount = currentItems.filter((item) => isConfirmedDefectItem(item)).length
  const uncertainCount = currentItems.filter((item) => isNeedsReviewItem(item)).length
  const dataQualityGapCount = currentItems.filter((item) => isDataQualityGapItem(item)).length
  const rejectedBySystemCount = ruleLevelSummary.value.rejectedBySystemCount
  const technicalErrorCount = currentItems.filter(
    (item) =>
      normalizeLuxianStatusKey(item.result_status || item.status || item.display_status) ===
      'technical_error',
  ).length
  if (isLuxian0609BatchJob.value) {
    const modeText = isLuxianScopedRun.value ? '选定质控点验证' : '全量 0609 规则集'
    return `${scopePrefix}当前展示泸县0609${modeText}结果，共 ${total} 条客户质控点结果，其中不合规 ${nonCompliantCount} 条，数据不足 ${dataQualityGapCount} 条，AI判断 ${uncertainCount} 条，技术异常 ${technicalErrorCount} 条。`
  }
  if (isPostprocessedFormalResult.value) {
    return `${scopePrefix}当前为正式质控四层准入结果，共 ${total} 条可查看结果，其中确认缺陷 ${nonCompliantCount} 条，数据缺口 ${dataQualityGapCount} 条，系统驳回 ${rejectedBySystemCount} 条，技术异常 ${technicalErrorCount} 条。原始语义判断不会直接计入确认缺陷。`
  }
  if (issueViewMode.value === 'business') {
    if (isFastScreenResult.value) {
      return `${scopePrefix}当前为快速初筛结果（摘要版），共 ${total} 条重点结果，其中不合规 ${nonCompliantCount} 条，AI判断 ${uncertainCount} 条。可先展开完整说明，再按需进入深度复核查看全文文书。`
    }
    return `${scopePrefix}当前共 ${total} 条重点结果，其中不合规 ${nonCompliantCount} 条，AI判断 ${uncertainCount} 条。默认优先阅读问题卡片，高级表格已折叠到“高级视图”。`
  }
  return `${scopePrefix}当前共 ${total} 条重点结果，其中不合规 ${nonCompliantCount} 条，AI判断 ${uncertainCount} 条。高级视图会展示完整表格和追溯字段。`
})

const issueSectionTitle = computed(() =>
  isLuxian0609BatchJob.value
    ? 'LX0609 客户质控点结果'
    : isPostprocessedFormalResult.value
      ? '确认缺陷/数据缺口/系统驳回'
      : '问题/AI判断明细',
)

const emptyIssueText = computed(() =>
  isLuxian0609BatchJob.value
    ? '暂无 LX0609 不合规、数据不足或 AI 判断结果'
    : isPostprocessedFormalResult.value
      ? '暂无确认缺陷、数据缺口或系统驳回项'
      : '暂无问题/AI判断明细',
)

watch(
  () => [batchJobDebugSnapshot.value?.job_id, batchJobDebugSnapshot.value?.rules?.length],
  () => {
    if (!batchJobDebugSnapshot.value) {
      selectedDebugRuleJobId.value = ''
      return
    }
    if (!selectedDebugRuleJobId.value) return
    const hasSelected = (batchJobDebugSnapshot.value.rules || []).some(
      (rule) => rule.rule_job_id === selectedDebugRuleJobId.value,
    )
    if (!hasSelected) {
      selectedDebugRuleJobId.value = ''
    }
  },
  { immediate: true },
)

async function handleDebugRuleChange(value: string | undefined) {
  selectedDebugRuleJobId.value = value || ''
  const jobId = props.batchJobDetail?.id
  if (!jobId || !props.fetchBatchJobDebugSnapshot) return
  await props.fetchBatchJobDebugSnapshot(jobId, {
    ruleJobId: value || undefined,
  })
}

function toggleClusterFilter(clusterKey: string) {
  selectedClusterKey.value = selectedClusterKey.value === clusterKey ? '' : clusterKey
  issuePagination.current = 1
  void nextTick(() => scrollToLinkedIssueRow())
}

function clearClusterFilter() {
  selectedClusterKey.value = ''
  issuePagination.current = 1
}

function handleIssueTableChange(pagination: { current?: number; pageSize?: number }) {
  issuePagination.current = Number(pagination.current || 1)
  issuePagination.pageSize = Number(pagination.pageSize || 8)
}

function resetIssueFilters() {
  issueFilter.value = createDefaultStructuredQCFilter()
  showAllStatuses.value = false
  issuePagination.current = 1
}

function resolveIssueStableKey(item?: SichuanBatchIssueItem) {
  if (!item) return ''
  return [
    item.rule_job_id || '',
    item.rule_id || item.rule_code || '',
    item.record_id || '',
    item.visit_id || '',
    item.trace_id || '',
  ].join('|')
}

function isIssueExpanded(item: SichuanBatchIssueItem) {
  const key = resolveIssueStableKey(item)
  return expandedIssueKeys.value.includes(key)
}

function toggleIssueExpanded(item: SichuanBatchIssueItem) {
  const key = resolveIssueStableKey(item)
  if (!key) return
  expandedIssueKeys.value = expandedIssueKeys.value.includes(key)
    ? expandedIssueKeys.value.filter((itemKey) => itemKey !== key)
    : [...expandedIssueKeys.value, key]
}

function stringifyTraceValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (Array.isArray(value)) {
    if (value.length === 0) return '-'
    return value
      .map((item) => stringifyTraceValue(item))
      .filter((item) => item && item !== '-')
      .join('；')
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

function humanizeTraceKey(key: string): string {
  const keyMap: Record<string, string> = {
    rule_id: '规则ID',
    rule_code: '规则编码',
    qc_point_id: '客户质控点',
    rule_name: '质控点名称',
    record_id: '病历号',
    visit_id: '就诊ID',
    patient_name: '患者',
    department: '科室',
    status: '状态',
    display_status: '展示状态',
    result_status: '结果状态',
    is_compliant: '合规布尔值',
    defect_level: '缺陷等级',
    findings: '质控结论',
    evidence: '证据摘要',
    suggestion: '处理建议',
    target_document_type: '目标文书',
    document_type: '文书类型',
    rule_family: '规则族',
    trace_id: 'Trace ID',
    model_version: '模型版本',
    executor_type: '执行器',
    final_status: '最终状态',
    final_decision_source: '最终状态来源',
    postprocess_label: '后处理标签',
    postprocess_reason: '后处理原因',
    first_pass_status: '初判状态',
    adjudicated_display_status: '裁决后展示状态',
    adjudicator_reason: '裁决原因',
    customer_display_guard: '客户展示保护',
    rule_requirement_match: '规则口径匹配',
    source_execution_count: '底层结果数',
    sensitive_fields_removed: '已移除敏感字段',
    raw_output_returned: '是否返回原始输出',
    note: '说明',
  }
  return keyMap[key] || key.replace(/_/g, ' ')
}

function traceObjectRows(value?: Record<string, unknown>, prefix = ''): ResultTraceRow[] {
  if (!value || typeof value !== 'object') return []
  return Object.entries(value)
    .filter(([, item]) => item !== null && item !== undefined && stringifyTraceValue(item) !== '-')
    .map(([key, item]) => ({
      key: prefix ? `${prefix}-${key}` : key,
      label: prefix ? `${prefix} · ${humanizeTraceKey(key)}` : humanizeTraceKey(key),
      value: stringifyTraceValue(item),
    }))
}

function traceListRows(value?: Array<Record<string, unknown>>): ResultTraceRow[] {
  if (!Array.isArray(value) || value.length === 0) return []
  return value.flatMap((item, index) =>
    traceObjectRows(item, `底层结果 ${index + 1}`).map((row) => ({
      ...row,
      key: `${index}-${row.key}`,
    })),
  )
}

async function openIssueTrace(item: SichuanBatchIssueItem) {
  const jobId = props.batchJobDetail?.id
  if (!jobId) {
    message.warning('当前任务缺少任务 ID，无法查看诊断追踪。')
    return
  }
  resultTraceModalOpen.value = true
  resultTraceLoading.value = true
  resultTraceError.value = ''
  resultTraceData.value = null
  const response = await getSichuanWorkspaceBatchJobResultTrace(jobId, {
    record_id: String(item.record_id || '').trim() || undefined,
    visit_id: String(item.visit_id || '').trim() || undefined,
    rule_id: String(item.qc_point_id || item.rule_id || item.rule_code || '').trim() || undefined,
  })
  resultTraceLoading.value = false
  if (!response.success || !response.data) {
    resultTraceError.value = response.message || '诊断追踪获取失败'
    message.warning(resultTraceError.value)
    return
  }
  resultTraceData.value = response.data
}

function closeIssueTrace() {
  resultTraceModalOpen.value = false
  resultTraceLoading.value = false
  resultTraceError.value = ''
  resultTraceData.value = null
}

async function openIssueDeepReview(item: SichuanBatchIssueItem) {
  selectedDeepReviewIssue.value = item
  deepReviewModalOpen.value = true
  deepReviewLoading.value = true
  deepReviewError.value = ''
  deepReviewResult.value = null
  const ruleId = String(item.rule_id || item.rule_code || '').trim()
  const instituteId = String(item.institute_id || '').trim()
  const patientId = String(item.patient_id || '').trim()
  const visitId = String(item.visit_id || '').trim()
  if (!ruleId || !instituteId || !patientId || !visitId) {
    deepReviewLoading.value = false
    deepReviewError.value = '当前结果缺少单条复核所需病历主键，无法发起深度复核。'
    return
  }
  const response = await evaluateSichuanRuleForVisit({
    rule_id: ruleId,
    institute_id: instituteId,
    patient_id: patientId,
    visit_id: visitId,
    source_schema: 'cdm',
    bundle_schema: 'public',
    force_refresh_bundle: false,
  })
  deepReviewLoading.value = false
  if (!response.success || !response.data) {
    deepReviewError.value = response.message || '深度复核失败'
    message.warning(deepReviewError.value)
    return
  }
  deepReviewResult.value = response.data
}

function closeDeepReviewModal() {
  deepReviewModalOpen.value = false
  selectedDeepReviewIssue.value = null
  deepReviewLoading.value = false
  deepReviewError.value = ''
  deepReviewResult.value = null
}

function formatProcessingTime(seconds: number) {
  const safeSeconds = Math.max(0, Number(seconds || 0))
  if (safeSeconds <= 0) return '-'
  if (safeSeconds < 60) return `${safeSeconds.toFixed(1)} 秒`
  const minutes = Math.floor(safeSeconds / 60)
  const remainSeconds = safeSeconds % 60
  return `${minutes}分${remainSeconds.toFixed(1)}秒`
}

function scrollToLinkedIssueRow() {
  const linkedKey = linkedIssueRowKey.value
  if (!linkedKey) return
  const row = document.querySelector<HTMLElement>(
    `.batch-issue-table tbody tr[data-row-key="${linkedKey.replace(/"/g, '\\"')}"]`,
  )
  if (row) {
    row.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }
}

function normalizeBreakdownItems(items: Array<{ label: string; count: number }>) {
  return items
    .filter((item) => item.label)
    .sort((left, right) => right.count - left.count)
    .slice(0, 4)
}

function truncateText(text?: string, limit = 80) {
  const value = String(text || '').trim()
  if (!value) return '-'
  return value.length > limit ? `${value.slice(0, limit)}...` : value
}

function resolveDeepReviewText(field: 'findings' | 'evidence' | 'suggestion') {
  const text = String(
    resolvedDeepReviewResult.value?.[field] || selectedDeepReviewIssue.value?.[field] || '',
  )
  if (field === 'evidence') return resolveCustomerEvidenceText(text)
  if (field === 'findings') return sanitizeCustomerVisibleText(text)
  return sanitizeCustomerVisibleText(text)
}

type EvidenceDisplayRow = {
  key: string
  label: string
  value: string
}

type EvidenceDisplayItem = {
  key: string
  source: string
  recordTime: string
  fieldPath: string
  quote: string
}

type EvidenceSummaryPart = {
  key: string
  label: string
  value: string
  kind: 'time' | 'source' | 'delta' | 'field' | 'text'
}

type CopyEvidenceCompare = {
  left: {
    label: string
    quote: string
  }
  right: {
    label: string
    quote: string
  }
  pairs?: Array<{
    key: string
    index: number
    leftLabel: string
    leftQuote: string
    rightLabel: string
    rightQuote: string
    similarity?: string
  }>
  metric?: string
  differenceGap?: string
  legacyNotice?: string
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function toRecordList(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return []
  return value.filter(
    (item): item is Record<string, unknown> =>
      !!item && typeof item === 'object' && !Array.isArray(item),
  )
}

function normalizeEvidenceText(value: unknown, limit = 120) {
  const text = String(value ?? '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit)}...` : text
}

function normalizeEvidencePartValue(value: string, limit = 96) {
  return normalizeEvidenceText(
    value
      .replace(/\s+/g, ' ')
      .replace(/[；;，,。\s]+$/gu, '')
      .trim(),
    limit,
  )
}

function normalizeEvidencePartLabel(value: string) {
  const label = value
    .replace(/\s+/g, '')
    .replace(/[；;，,。]+$/gu, '')
    .trim()
  const map: Record<string, string> = {
    authored_at: '记录时间',
    record_time: '记录时间',
    submit_time: '提交时间',
    submitted_at: '提交时间',
    admission_time: '入院时间',
    discharge_time: '出院时间',
    deadline: '截止时间',
    elapsed: '间隔',
    delta: '差值',
  }
  return map[label] || label
}

function resolveEvidencePartKind(label: string, value: string): EvidenceSummaryPart['kind'] {
  const text = `${label} ${value}`
  if (/间隔|差值|超时|超过|小时|天/.test(text)) return 'delta'
  if (/时间|日期|入院|出院|记录|提交|截止/.test(label)) return 'time'
  if (/来源|文书|字段/.test(label)) return 'source'
  if (/^[a-z_]+$/i.test(label)) return 'field'
  return 'text'
}

function parseEvidenceSummaryParts(text?: string | null): EvidenceSummaryPart[] {
  const raw = sanitizeCustomerVisibleText(text)
  if (!raw) return []
  return raw
    .split(/[；;\n]/u)
    .map((part) => part.trim())
    .filter((part) => part.length >= 4)
    .map((part, index): EvidenceSummaryPart | null => {
      const segments = part
        .split(/：/u)
        .map((segment) => segment.trim())
        .filter(Boolean)
      if (segments.length < 2) return null

      const first = normalizeEvidencePartLabel(segments[0] || '')
      const second = normalizeEvidencePartLabel(segments[1] || '')
      const secondIsTechnicalField = /^[a-z_]+$/i.test(segments[1] || '')
      const label = secondIsTechnicalField ? `${first} · ${second}` : first
      const value = normalizeEvidencePartValue(
        secondIsTechnicalField ? segments.slice(2).join('：') : segments.slice(1).join('：'),
      )
      if (!label || !value) return null
      return {
        key: `evidence-part-${index}-${label}`,
        label,
        value,
        kind: resolveEvidencePartKind(label, value),
      }
    })
    .filter((part): part is EvidenceSummaryPart => Boolean(part))
    .slice(0, 6)
}

const INTERNAL_EVIDENCE_LABELS = [
  '证据模板',
  '触发门控',
  '触发状态',
  '触发说明',
  '触发关键词',
  '匹配关键词',
  '来源线索',
  '映射执行规则',
  '应包含证据要素',
  '质控点',
]

const CUSTOMER_EVIDENCE_PRIORITY_LABELS = ['执行证据', '关键证据', '判定依据', '判断依据']

const EVIDENCE_LABELS = [
  ...INTERNAL_EVIDENCE_LABELS,
  ...CUSTOMER_EVIDENCE_PRIORITY_LABELS,
  '数据缺口',
]

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function resolveLabeledEvidenceValue(text: string, label: string) {
  const labelPattern = new RegExp(`${escapeRegExp(label)}[：:]\\s*`, 'u')
  const match = labelPattern.exec(text)
  if (!match) return ''
  const start = match.index + match[0].length
  const nextLabelIndexes = EVIDENCE_LABELS.filter((candidate) => candidate !== label)
    .map((candidate) => {
      const nextPattern = new RegExp(`${escapeRegExp(candidate)}[：:]\\s*`, 'u')
      const nextMatch = nextPattern.exec(text.slice(start))
      return nextMatch ? start + nextMatch.index : -1
    })
    .filter((index) => index >= 0)
  const end = nextLabelIndexes.length ? Math.min(...nextLabelIndexes) : text.length
  return text.slice(start, end).replace(/\s+/g, ' ').trim()
}

function removeInternalEvidenceSegments(text: string) {
  let output = text
  output = output
    .replace(/来源未标注\s*[·:：]\s*evidence[：:]?\s*/giu, '')
    .replace(/\bevidence[：:]\s*/giu, '')
    .replace(/\btrigger_status[：:]\s*unknown[。；;]*/giu, '')
    .replace(/\bunknown\b/giu, '')
    .replace(/LLM\s*语义规则/giu, '语义规则')
    .replace(/LLM\s*返回(?:了)?非结构化结果[，,。；;]*/giu, '自动判定未形成可靠结构化结论，')
    .replace(/请查看原始输出[。；;]*/gu, '')
    .replace(/本质控点按现有文书和结构化数据直接复核[。；;]*/gu, '')
    .replace(/判定依据[：:]\s*本质控点按现有文书和结构化数据直接复核[。；;]*/gu, '')
    .replace(/判定依据[：:]\s*已发现相关事件[，,]进入规则复核[。；;]*/gu, '')
    .replace(/已发现相关事件[，,]进入规则复核[。；;]*/gu, '')
  INTERNAL_EVIDENCE_LABELS.forEach((label) => {
    const labelPattern = new RegExp(`${escapeRegExp(label)}[：:]\\s*`, 'u')
    let match = labelPattern.exec(output)
    while (match) {
      const start = match.index
      const contentStart = start + match[0].length
      const nextLabelIndexes = EVIDENCE_LABELS.filter((candidate) => candidate !== label)
        .map((candidate) => {
          const nextPattern = new RegExp(`${escapeRegExp(candidate)}[：:]\\s*`, 'u')
          const nextMatch = nextPattern.exec(output.slice(contentStart))
          return nextMatch ? contentStart + nextMatch.index : -1
        })
        .filter((index) => index >= 0)
      const end = nextLabelIndexes.length ? Math.min(...nextLabelIndexes) : output.length
      output = `${output.slice(0, start)} ${output.slice(end)}`
      match = labelPattern.exec(output)
    }
  })
  return output.replace(/\s+/g, ' ').trim()
}

function sanitizeCustomerVisibleText(text?: string | null) {
  const cleaned = removeInternalEvidenceSegments(String(text || ''))
    .replace(/来源未标注\s*[·:：]\s*/gu, '')
    .replace(/待人工复核/gu, 'AI判断后建议确认')
    .replace(/待人工核对/gu, 'AI判断后建议确认')
    .replace(/建议人工复核/gu, '建议结合原文确认')
    .replace(/建议人工核对/gu, '建议结合原文确认')
    .replace(/需人工复核/gu, '需结合原文确认')
    .replace(/需人工核对/gu, '需结合原文确认')
    .replace(/需要人工复核/gu, '需要结合原文确认')
    .replace(/需要人工核对/gu, '需要结合原文确认')
    .replace(/人工复核/gu, '结合原文确认')
    .replace(/人工核对/gu, '结合原文确认')
    .replace(/\s+/g, ' ')
    .trim()
  return cleaned
}

function normalizeCustomerDataGapText(text?: string | null) {
  return String(text || '')
    .replace(/^数据缺口[：:]\s*/u, '')
    .replace(/复制病历比对未执行[。.]?/u, '复制病历比对未执行')
    .replace(/[；;]/gu, '，')
    .replace(/[，。、\s]+$/gu, '')
    .trim()
}

function normalizeCustomerEvidenceLabel(value: unknown) {
  const normalized = String(value || '').trim()
  if (!normalized || normalized === 'evidence') return ''
  const labelMap: Record<string, string> = {
    source_document: '来源文书',
    source_field: '来源字段',
    field_path: '来源字段',
    quote: '原文片段',
    supporting_evidence: '关键证据',
    text_evidence: '关键证据',
  }
  return labelMap[normalized] || normalized
}

function resolveCustomerEvidenceText(text?: string | null) {
  const raw = String(text || '').trim()
  if (!raw) return ''
  const priorityEvidence = CUSTOMER_EVIDENCE_PRIORITY_LABELS.map((label) =>
    removeInternalEvidenceSegments(resolveLabeledEvidenceValue(raw, label)),
  ).find(Boolean)
  if (priorityEvidence) return priorityEvidence
  return removeInternalEvidenceSegments(raw)
}

function isGenericCustomerEvidenceText(text: string) {
  const normalized = text.replace(/\s+/g, '')
  return (
    !normalized ||
    /^判定依据[:：]?未发现与本质控点直接相关的适用事件[。.]?$/.test(text.trim()) ||
    normalized === '未发现与本质控点直接相关的适用事件' ||
    normalized === '本质控点按现有文书和结构化数据直接复核'
  )
}

function resolveRichCustomerEvidenceText(item: Partial<SichuanBatchIssueItem>) {
  const evidenceText = resolveCustomerEvidenceText(item.evidence)
  if (!evidenceText || isGenericCustomerEvidenceText(evidenceText)) return ''
  return evidenceText
}

function resolveEvidenceDataGapText(text?: string | null) {
  const raw = String(text || '').trim()
  if (!raw) return ''
  return normalizeEvidenceText(
    normalizeCustomerDataGapText(resolveLabeledEvidenceValue(raw, '数据缺口')),
    80,
  )
}

function hasEvidenceChain(item?: Partial<SichuanBatchIssueItem> | null) {
  if (!item) return false
  return Boolean(
    item.result_status ||
      item.qc_point_id ||
      item.schema_version ||
      item.trigger ||
      item.dependencies ||
      item.decision ||
      item.review ||
      item.audit ||
      (Array.isArray(item.evidence_items) && item.evidence_items.length > 0),
  )
}

function resolveEvidenceStatusText(status?: string) {
  const normalized = String(status || '')
    .trim()
    .toLowerCase()
  const map: Record<string, string> = {
    non_compliant: '不合规',
    ai_suggested_non_compliant: 'AI判断：疑似问题',
    compliant: '合规',
    ai_suggested_compliant: 'AI判断：未见问题',
    not_applicable: '不适用',
    data_gap: '数据不足',
    uncertain: 'AI判断',
    not_executed: '未执行',
    technical_error: '技术异常',
    failed: '失败',
    error: '错误',
  }
  return map[normalized] || resolveStatusText(normalized)
}

function resolveIssueSeverityText(item: Partial<SichuanBatchIssueItem>) {
  const status = normalizeLuxianStatusKey(item.result_status || item.status || item.display_status)
  if (status === 'data_gap') return '数据不足，需补充资料'
  if (status === 'ai_suggested_non_compliant' || status === 'uncertain') return 'AI判断'
  if (status === 'ai_suggested_compliant') return 'AI未见问题'
  if (status === 'not_applicable') return '不适用'
  if (status === 'not_executed') return '未执行'
  if (status === 'technical_error') return '技术异常'
  return item.defect_level || '未分级'
}

function resolveIssueCardClass(item: Partial<SichuanBatchIssueItem>) {
  const status = normalizeLuxianStatusKey(item.result_status || item.status || item.display_status)
  return {
    'issue-conclusion-card--danger': status === 'non_compliant' || status === 'technical_error',
    'issue-conclusion-card--warning':
      status === 'data_gap' ||
      status === 'uncertain' ||
      status === 'ai_suggested_non_compliant' ||
      status === 'not_executed',
    'issue-conclusion-card--success': status === 'compliant' || status === 'ai_suggested_compliant',
    'issue-conclusion-card--muted': status === 'not_applicable',
  }
}

function resolveIssueResultKindText(item: Partial<SichuanBatchIssueItem>) {
  const status = normalizeLuxianStatusKey(item.result_status || item.status || item.display_status)
  if (status === 'non_compliant') return '确定问题'
  if (status === 'ai_suggested_non_compliant') return 'AI判断'
  if (status === 'ai_suggested_compliant') return 'AI未见问题'
  if (status === 'technical_error') return '技术异常'
  if (status === 'data_gap') return '数据不足'
  if (status === 'uncertain') return 'AI判断'
  if (status === 'not_executed') return '未执行'
  if (status === 'not_applicable') return '不适用'
  if (status === 'compliant') return '合规'
  return '结果项'
}

function resolveIssueResultKindClass(item: Partial<SichuanBatchIssueItem>) {
  const status = normalizeLuxianStatusKey(item.result_status || item.status || item.display_status)
  return {
    'issue-result-kind--danger': status === 'non_compliant',
    'issue-result-kind--error': status === 'technical_error',
    'issue-result-kind--review':
      status === 'data_gap' ||
      status === 'uncertain' ||
      status === 'ai_suggested_non_compliant' ||
      status === 'not_executed',
    'issue-result-kind--muted': status === 'not_applicable',
    'issue-result-kind--ok': status === 'compliant' || status === 'ai_suggested_compliant',
  }
}

function resolveExecutorTypeText(value?: string) {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
  if (normalized === 'program') return '自动规则'
  if (normalized === 'llm') return '语义规则'
  if (normalized === 'hybrid') return '混合执行'
  return value || '执行器未标注'
}

function resolveTriggerFacts(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
  const trigger = toRecord(item.trigger)
  const facts = toRecordList(trigger?.trigger_facts)
  const rows = facts
    .map((fact, index) => {
      const label =
        normalizeEvidenceText(fact.fact_label, 30) ||
        normalizeEvidenceText(fact.fact_type, 30) ||
        `触发事实 ${index + 1}`
      const sourceParts = [
        normalizeEvidenceText(fact.source_document_type, 24),
        normalizeEvidenceText(fact.source_document_id, 24),
        normalizeEvidenceText(fact.record_time, 24),
      ].filter(Boolean)
      const value = [
        normalizeEvidenceText(fact.fact_value, 120),
        sourceParts.length ? `来源：${sourceParts.join(' / ')}` : '',
      ]
        .filter(Boolean)
        .join('；')
      return {
        key: `trigger-${index}`,
        label,
        value,
      }
    })
    .filter((row) => row.value)
  const notApplicableReason = normalizeEvidenceText(trigger?.not_applicable_reason, 120)
  if (notApplicableReason) {
    rows.push({
      key: 'not-applicable-reason',
      label: '不适用原因',
      value: notApplicableReason,
    })
  }
  return rows
}

function resolveSourceNames(value: unknown) {
  const rows = toRecordList(value)
    .map((item) => {
      return (
        normalizeEvidenceText(item.source_name, 40) ||
        normalizeEvidenceText(item.table, 40) ||
        normalizeEvidenceText(item.source_table, 40)
      )
    })
    .filter(Boolean)
  return rows.length ? rows.join('、') : ''
}

function resolveMissingSources(item: Partial<SichuanBatchIssueItem>) {
  const dependencies = toRecord(item.dependencies)
  return toRecordList(dependencies?.missing_sources)
}

function resolveDependencyRows(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
  const dependencies = toRecord(item.dependencies)
  if (!dependencies) {
    return [
      {
        key: 'dependency-empty',
        label: '依赖数据',
        value: '暂无可展示的数据依赖',
      },
    ]
  }
  const rows: EvidenceDisplayRow[] = []
  const requiredSources = resolveSourceNames(dependencies.required_sources)
  if (requiredSources) {
    rows.push({ key: 'required-sources', label: '需要数据', value: requiredSources })
  }
  const missingSources = resolveSourceNames(dependencies.missing_sources)
  if (missingSources) {
    rows.push({ key: 'missing-sources', label: '缺失数据', value: missingSources })
  }
  const gapReason = normalizeEvidenceText(dependencies.data_gap_reason, 120)
  if (gapReason) rows.push({ key: 'data-gap-reason', label: '缺口说明', value: gapReason })
  const coverage = normalizeEvidenceText(dependencies.source_coverage_level, 32)
  if (coverage) {
    const coverageMap: Record<string, string> = {
      full: '数据完整',
      partial: '部分覆盖',
      missing: '缺少关键数据',
      unknown: '未标注',
    }
    rows.push({
      key: 'coverage',
      label: '覆盖程度',
      value: coverageMap[coverage] || coverage,
    })
  }
  return rows.length
    ? rows
    : [
        {
          key: 'dependency-empty',
          label: '依赖数据',
          value: '暂无可展示的数据依赖',
        },
      ]
}

function resolveEvidenceChainItems(
  item: Partial<SichuanBatchIssueItem>,
  quoteLimit = 260,
): EvidenceDisplayItem[] {
  const evidenceItems = toRecordList(item.evidence_items)
    .map((evidence, index) => {
      const source =
        normalizeEvidenceText(evidence.source_document_name, 40) ||
        normalizeEvidenceText(evidence.source_document_type, 40) ||
        normalizeEvidenceText(evidence.source_table, 40) ||
        '质控依据'
      return {
        key: normalizeEvidenceText(evidence.evidence_id, 24) || `evidence-${index}`,
        source,
        recordTime: normalizeEvidenceText(evidence.record_time, 32),
        fieldPath: normalizeCustomerEvidenceLabel(evidence.field_path),
        quote: normalizeEvidenceText(
          resolveCustomerEvidenceText(String(evidence.quote || '')),
          quoteLimit,
        ),
      }
    })
    .filter((item) => item.quote)
  const richEvidenceText = resolveRichCustomerEvidenceText(item)
  if (richEvidenceText) {
    const currentQuoteText = evidenceItems.map((evidence) => evidence.quote).join(' ')
    const shouldPrepend =
      richEvidenceText.length > 36 &&
      richEvidenceText.length > currentQuoteText.length + 16 &&
      !currentQuoteText.includes(richEvidenceText.slice(0, 24))
    if (shouldPrepend) {
      return [
        {
          key: 'customer-evidence-summary',
          source: '质控结果',
          recordTime: '',
          fieldPath: '关键证据',
          quote: normalizeEvidenceText(richEvidenceText, Math.max(quoteLimit, 320)),
        },
        ...evidenceItems,
      ]
    }
  }
  return evidenceItems
}

function formatEvidenceSummaryItem(evidence: EvidenceDisplayItem) {
  if (evidence.source === '质控结果' && evidence.fieldPath === '关键证据') {
    return evidence.quote
  }
  if (evidence.source === '质控结果') {
    return evidence.fieldPath ? `${evidence.fieldPath}：${evidence.quote}` : evidence.quote
  }
  const source = [evidence.source, evidence.fieldPath].filter(Boolean).join(' · ')
  return source ? `${source}：${evidence.quote}` : evidence.quote
}

function isCopyRule(item: Partial<SichuanBatchIssueItem>) {
  const ruleText = [item.rule_code, item.rule_id, item.rule_name, item.findings, item.evidence]
    .filter(Boolean)
    .join(' ')
  return /LX0609-0?1[67]|复制|重复|完全相同|相似度/.test(ruleText)
}

function evidenceRoleText(evidence: Record<string, unknown>) {
  return [
    evidence.source_document_name,
    evidence.source_document_type,
    evidence.source_field,
    evidence.field_path,
    evidence.evidence_role,
  ]
    .map((value) => String(value || '').trim())
    .filter(Boolean)
    .join(' ')
}

function normalizeCopyEvidenceSourceLabel(value: unknown) {
  const text = normalizeEvidenceText(value, 32)
  const mapping: Record<string, string> = {
    daily_course_record: '日常病程记录',
    senior_course_record: '上级医师查房记录',
    first_course_record: '首次病程记录',
    admission_record: '入院记录',
    copy_compare: '复制病历比对',
  }
  return mapping[text] || text
}

function resolveCopyEvidenceCompare(
  item: Partial<SichuanBatchIssueItem>,
): CopyEvidenceCompare | null {
  if (!isCopyRule(item)) return null
  const evidenceRows = toRecordList(item.evidence_items)
    .map((evidence, index) => {
      const quote = normalizeEvidenceText(evidence.quote, 180)
      if (!quote) return null
      const roleText = evidenceRoleText(evidence)
      const source =
        normalizeCopyEvidenceSourceLabel(evidence.source_document_name) ||
        normalizeCopyEvidenceSourceLabel(evidence.source_document_type) ||
        `文书片段 ${index + 1}`
      return {
        quote,
        roleText,
        source,
        evidenceId: normalizeEvidenceText(evidence.evidence_id, 32),
        actualValue: normalizeEvidenceText(evidence.actual_value, 64),
      }
    })
    .filter(
      (
        row,
      ): row is {
        quote: string
        roleText: string
        source: string
        evidenceId: string
        actualValue: string
      } => Boolean(row),
    )

  const metricEvidence = evidenceRows.find((row) =>
    /COPY-METRIC|复制病历比对指标|重复度判定|相似度|覆盖率/.test(
      [row.evidenceId, row.roleText, row.source, row.quote].join(' '),
    ),
  )
  const metric = metricEvidence?.quote
  const differenceEvidence = evidenceRows.find((row) =>
    /COPY-MISSING-DIFFERENCE|差异不足|缺少差异|新增内容|病情变化/.test(
      [row.evidenceId, row.roleText, row.source, row.quote].join(' '),
    ),
  )
  const differenceGap = differenceEvidence?.quote
  const pairMap = new Map<
    string,
    {
      index: number
      previous?: (typeof evidenceRows)[number]
      current?: (typeof evidenceRows)[number]
    }
  >()
  evidenceRows.forEach((row) => {
    const match = row.evidenceId.match(/^COPY-PAIR-(\d+)-(PREVIOUS|CURRENT)$/)
    if (!match) return
    const key = match[1] || ''
    const existing = pairMap.get(key) || { index: Number(key) || pairMap.size + 1 }
    if (match[2] === 'PREVIOUS') {
      existing.previous = row
    } else {
      existing.current = row
    }
    pairMap.set(key, existing)
  })
  const pairs = Array.from(pairMap.values())
    .filter((pair) => pair.previous?.quote && pair.current?.quote)
    .sort((a, b) => a.index - b.index)
    .map((pair) => ({
      key: `copy-pair-${pair.index}`,
      index: pair.index,
      leftLabel: pair.previous?.source || `前次记录片段 ${pair.index}`,
      leftQuote: pair.previous?.quote || '',
      rightLabel: pair.current?.source || `本次记录片段 ${pair.index}`,
      rightQuote: pair.current?.quote || '',
      similarity: pair.current?.actualValue || pair.previous?.actualValue || '',
    }))
  const legacyNotice = pairs.length
    ? ''
    : '当前任务结果只保存了单组对照片段。请重新发起质控，生成多片段对照、相似度指标和差异不足说明。'
  const admissionEvidence = evidenceRows.find((row) =>
    /入院记录|admission|source|原文/.test(row.roleText),
  )
  const courseEvidence = evidenceRows.find((row) =>
    /首次病程|日常病程|病程记录|course|target|对比/.test(row.roleText),
  )
  if (admissionEvidence && courseEvidence) {
    return {
      left: {
        label: admissionEvidence.source || '入院记录片段',
        quote: admissionEvidence.quote,
      },
      right: {
        label: courseEvidence.source || '病程记录片段',
        quote: courseEvidence.quote,
      },
      pairs,
      metric,
      differenceGap,
      legacyNotice,
    }
  }

  const customerEvidence = resolveCustomerEvidenceText(item.evidence)
  const parts = customerEvidence
    .split(/[；;]/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 8)
  if (parts.length >= 3) {
    return {
      left: {
        label: '入院记录/首次病程片段',
        quote: truncateText(parts[1], 180),
      },
      right: {
        label: '病程记录片段',
        quote: truncateText(parts[2], 180),
      },
      pairs,
      metric,
      differenceGap,
      legacyNotice,
    }
  }
  const snippetRows = evidenceRows.filter(
    (row) =>
      row.evidenceId !== 'COPY-METRIC' &&
      row.evidenceId !== 'COPY-MISSING-DIFFERENCE' &&
      !/^COPY-PAIR-\d+-(PREVIOUS|CURRENT)$/.test(row.evidenceId),
  )
  if (snippetRows.length >= 2) {
    return {
      left: {
        label: snippetRows[0].source,
        quote: snippetRows[0].quote,
      },
      right: {
        label: snippetRows[1].source,
        quote: snippetRows[1].quote,
      },
      pairs,
      metric,
      differenceGap,
      legacyNotice,
    }
  }
  if (pairs.length) {
    return {
      left: {
        label: pairs[0].leftLabel,
        quote: pairs[0].leftQuote,
      },
      right: {
        label: pairs[0].rightLabel,
        quote: pairs[0].rightQuote,
      },
      pairs,
      metric,
      differenceGap,
      legacyNotice,
    }
  }
  return null
}

function resolveIssueEvidenceSummary(item: Partial<SichuanBatchIssueItem>) {
  const status = normalizeLuxianStatusKey(item.result_status || item.status || item.display_status)
  if (status === 'data_gap') {
    const missingSources = resolveSourceNames(toRecord(item.dependencies)?.missing_sources)
    if (missingSources) {
      return truncateText(
        `已识别相关触发事实，但缺少${normalizeCustomerDataGapText(missingSources)}，需补齐后再自动判定。`,
        140,
      )
    }
    const dataGapText = resolveEvidenceDataGapText(item.evidence)
    if (dataGapText) {
      return truncateText(
        `已识别相关触发事实，但缺少${normalizeCustomerDataGapText(dataGapText)}，需补齐后再自动判定。`,
        140,
      )
    }
  }
  const evidences = resolveEvidenceChainItems(item)
  if (evidences.length) {
    const richEvidenceText = resolveRichCustomerEvidenceText(item)
    const evidenceSummaryText = evidences.slice(0, 2).map(formatEvidenceSummaryItem).join('；')
    if (richEvidenceText && richEvidenceText.length > evidenceSummaryText.length + 16) {
      return truncateText(richEvidenceText, 180)
    }
    return truncateText(evidences.slice(0, 2).map(formatEvidenceSummaryItem).join('；'), 180)
  }
  const triggerFact = resolveTriggerFacts(item)[0]
  if (triggerFact?.value) {
    return truncateText(`${triggerFact.label}：${triggerFact.value}`, 118)
  }
  const decision = resolveDecisionRows(item).find((row) => row.key === 'decision-summary')
  if (decision?.value) {
    return truncateText(decision.value, 118)
  }
  return truncateText(resolveCustomerEvidenceText(item.evidence), 140)
}

function resolveIssueEvidenceSummaryParts(item: Partial<SichuanBatchIssueItem>) {
  const evidenceCandidates = [
    resolveRichCustomerEvidenceText(item),
    resolveEvidenceChainItems(item).slice(0, 2).map(formatEvidenceSummaryItem).join('；'),
    resolveCustomerEvidenceText(item.evidence),
    resolveIssueEvidenceSummary(item),
  ].filter(Boolean)
  for (const evidenceText of evidenceCandidates) {
    const parts = parseEvidenceSummaryParts(evidenceText)
    if (parts.length >= 2) return parts
  }
  return []
}

function resolveDecisionRows(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
  const decision = toRecord(item.decision)
  if (!decision) return []
  const rows: EvidenceDisplayRow[] = [
    {
      key: 'decision-summary',
      label: '判断摘要',
      value: normalizeEvidenceText(decision.decision_summary, 160),
    },
    {
      key: 'threshold',
      label: '判断阈值',
      value: normalizeEvidenceText(decision.threshold, 120),
    },
    {
      key: 'expected',
      label: '期望值',
      value: normalizeEvidenceText(decision.expected_value, 120),
    },
    {
      key: 'actual',
      label: '实际值',
      value: normalizeEvidenceText(decision.actual_value, 120),
    },
    {
      key: 'delta',
      label: '差值',
      value: normalizeEvidenceText(decision.delta, 80),
    },
    {
      key: 'suggestion',
      label: '处理建议',
      value: normalizeEvidenceText(decision.suggestion, 160),
    },
  ]
  return rows.filter((row) => row.value)
}

function resolveReviewRows(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
  const review = toRecord(item.review)
  if (!review) return []
  const reviewStatus = normalizeEvidenceText(review.review_status, 32)
  const statusMap: Record<string, string> = {
    pending: '待确认',
    not_required: '无需复核',
    reviewed: '已复核',
  }
  const rows: EvidenceDisplayRow[] = []
  if (reviewStatus) {
    rows.push({
      key: 'review-status',
      label: '复核状态',
      value: statusMap[reviewStatus] || reviewStatus,
    })
  }
  const finalStatus = normalizeEvidenceText(review.final_status, 32)
  if (finalStatus) rows.push({ key: 'final-status', label: '最终状态', value: finalStatus })
  const comment = normalizeEvidenceText(review.review_comment, 140)
  if (comment) rows.push({ key: 'review-comment', label: '复核意见', value: comment })
  return rows
}

function resolveAuditRows(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
  const audit = toRecord(item.audit)
  if (!audit) return []
  const rows: EvidenceDisplayRow[] = [
    { key: 'visit-id', label: '住院号', value: normalizeEvidenceText(audit.visit_id, 48) },
    ...(isLuxianNativeSliceBatchJob.value
      ? []
      : [
          {
            key: 'model-name',
            label: '执行方式',
            value: normalizeEvidenceText(audit.model_name, 80),
          },
        ]),
    { key: 'executed-at', label: '执行时间', value: normalizeEvidenceText(audit.executed_at, 48) },
    { key: 'elapsed', label: '耗时', value: normalizeEvidenceText(audit.elapsed_ms, 32) },
    {
      key: 'technical-status',
      label: '技术状态',
      value: normalizeEvidenceText(audit.technical_status, 40),
    },
  ]
  return rows.filter((row) => row.value)
}

type StructuredTextSection = {
  title: string
  paragraphs: string[]
  points: string[]
}

function resolveStructuredText(text?: string | null) {
  const raw = String(text || '')
    .replace(/\r\n/g, '\n')
    .replace(/\u00a0/g, ' ')
    .trim()
  if (!raw) {
    return {
      summary: [] as string[],
      sections: [] as StructuredTextSection[],
      points: [] as string[],
    }
  }

  const prepared = raw
    .replace(/(【[^】]{1,40}】)/g, '\n$1\n')
    .replace(/(\*\*[^*]{1,60}\*\*[：:]?)/g, '\n$1\n')
    .replace(/(^|[。；;：:]\s*)(\d+[.、]\s*)/g, '$1\n$2')

  const lines = prepared
    .split('\n')
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean)

  const summary: string[] = []
  const sections: StructuredTextSection[] = []
  const rootPoints: string[] = []
  let currentSection: StructuredTextSection | null = null

  const pushParagraph = (target: StructuredTextSection | null, value: string) => {
    const normalized = value.trim()
    if (!normalized) return
    if (target) {
      target.paragraphs.push(normalized)
    } else {
      summary.push(normalized)
    }
  }

  const createSection = (title: string, trailingContent = '') => {
    currentSection = {
      title: title.replace(/[：:]+$/g, '').trim(),
      paragraphs: [],
      points: [],
    }
    sections.push(currentSection)
    if (trailingContent.trim()) {
      currentSection.paragraphs.push(trailingContent.trim())
    }
  }

  lines.forEach((line) => {
    const markdownHeading = line.match(/^\*\*([^*]{1,80})\*\*[：:]?\s*(.*)$/)
    if (markdownHeading) {
      createSection(markdownHeading[1], markdownHeading[2] || '')
      return
    }

    const bracketHeading = line.match(/^【([^】]{1,80})】\s*(.*)$/)
    if (bracketHeading) {
      createSection(bracketHeading[1], bracketHeading[2] || '')
      return
    }

    const shortHeading = line.match(/^([^，。；;：:\s]{2,24})[：:]\s*(.+)$/)
    if (shortHeading && shortHeading[1].length <= 18) {
      createSection(shortHeading[1], shortHeading[2] || '')
      return
    }

    const numberedPoint = line.match(/^\d+[.、]\s*(.+)$/)
    if (numberedPoint) {
      if (currentSection) {
        currentSection.points.push(numberedPoint[1].trim())
      } else {
        rootPoints.push(numberedPoint[1].trim())
      }
      return
    }

    pushParagraph(currentSection, line)
  })

  return { summary, sections, points: rootPoints }
}

function hasStructuredText(text?: string | null) {
  const structured = resolveStructuredText(text)
  return Boolean(
    structured.summary.length || structured.sections.length || structured.points.length,
  )
}

function resolveBreakdownLabel(kind: 'executor' | 'document' | 'defect' | 'status', key: string) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey) return '未命名'
  if (kind === 'executor') {
    const map: Record<string, string> = {
      program: '程序规则',
      llm: '语义规则',
    }
    return map[normalizedKey.toLowerCase()] || normalizedKey
  }
  if (kind === 'defect') {
    const map: Record<string, string> = {
      critical: '严重缺陷',
      major: '重大缺陷',
      moderate: '中度缺陷',
      minor: '轻微缺陷',
      high: '高风险',
      medium: '中风险',
      low: '低风险',
    }
    return map[normalizedKey.toLowerCase()] || normalizedKey
  }
  if (kind === 'status') {
    const map: Record<string, string> = {
      non_compliant: '不合规',
      ai_suggested_non_compliant: 'AI判断：疑似问题',
      uncertain: 'AI判断',
      compliant: '合规',
      ai_suggested_compliant: 'AI判断：未见问题',
      not_applicable: '不适用',
      failed: '失败',
    }
    return map[normalizedKey.toLowerCase()] || normalizedKey
  }
  return normalizedKey
}

function resolveStatusText(status?: string) {
  const normalized = String(status || '')
    .trim()
    .toLowerCase()
  if (normalized === 'non_compliant') return '不合规'
  if (normalized === 'ai_suggested_non_compliant') return 'AI判断：疑似问题'
  if (normalized === 'uncertain') return 'AI判断'
  if (normalized === 'ai_suggested_compliant') return 'AI判断：未见问题'
  if (normalized === 'not_applicable') return '不适用'
  if (normalized === 'data_gap') return '数据不足'
  if (normalized === 'not_executed') return '未执行'
  if (normalized === 'technical_error' || normalized === 'technical_error_internal')
    return '技术异常'
  if (normalized === 'failed') return '失败'
  return '合规'
}

function resolveDisplayStatusText(item?: Pick<SichuanBatchIssueItem, 'display_status'> | null) {
  if (!isPostprocessedFormalResult.value || !item?.display_status) return ''
  const normalized = String(item.display_status || '')
    .trim()
    .toLowerCase()
  if (normalized === 'confirmed_defect') return '确认缺陷'
  if (normalized === 'qc_review_candidate' || normalized === 'needs_review') return '系统驳回'
  if (normalized === 'data_quality_gap') return '数据缺口'
  if (normalized === 'rejected_by_system') return '系统驳回'
  if (normalized === 'technical_error_internal') return '内部技术异常'
  if (normalized === 'not_applicable') return '不适用'
  if (normalized === 'compliant') return '合规'
  return ''
}

function objectEntriesToCompactList(input: Record<string, unknown> | unknown) {
  if (!input || typeof input !== 'object') return []
  return Object.entries(input)
    .map(([label, value]) => ({
      label,
      value: formatCompactValue(value),
    }))
    .filter((item) => item.label && item.value)
    .slice(0, 8)
}

function formatCompactValue(value: unknown) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) {
    const list = value
      .slice(0, 3)
      .map((item) => formatCompactValue(item))
      .filter(Boolean)
    const suffix = value.length > 3 ? '…' : ''
    return list.join('、') + suffix
  }
  if (value instanceof Date) {
    return value.toISOString()
  }
  try {
    const json = JSON.stringify(value)
    return json.length > 72 ? `${json.slice(0, 72)}…` : json
  } catch {
    return String(value)
  }
}

function resolveIssueRowClassName(record: SichuanBatchIssueItem) {
  const linkedKey = linkedIssueRowKey.value
  const currentKey = resolveIssueStableKey(record)
  if (linkedKey && currentKey === linkedKey) return 'issue-row-highlight issue-row-linked'
  if (
    ['uncertain', 'ai_suggested_non_compliant'].includes(
      normalizeLuxianStatusKey(record.result_status || record.status || record.display_status),
    )
  )
    return 'issue-row-uncertain'
  if (!selectedCluster.value) return ''
  return matchIssueItemWithCluster(record, selectedCluster.value) ? 'issue-row-highlight' : ''
}

// 聚合簇命中判定：优先规则ID/编码匹配，其次回退到证据文本匹配。
function matchIssueItemWithCluster(
  item: SichuanBatchIssueItem,
  cluster: SichuanBatchResultAggregation['clusters'][number],
) {
  const clusterRuleIdSet = new Set(
    (cluster.rules || []).map((rule) => String(rule.rule_id || '').toLowerCase()).filter(Boolean),
  )
  const itemRuleCode = String(item.rule_code || '').toLowerCase()
  const itemRuleId = String(item.rule_id || '').toLowerCase()
  const byRule =
    (itemRuleId && clusterRuleIdSet.has(itemRuleId)) ||
    (itemRuleCode && clusterRuleIdSet.has(itemRuleCode))
  if (byRule) return true
  const finding = String(item.findings || '')
  const evidence = String(item.evidence || '')
  const sampleEvidence = String(cluster.sample_evidence || '').trim()
  if (sampleEvidence && (finding.includes(sampleEvidence) || evidence.includes(sampleEvidence))) {
    return true
  }
  const clusterKey = String(cluster.cluster_key || '').trim()
  if (clusterKey && (finding.includes(clusterKey) || evidence.includes(clusterKey))) {
    return true
  }
  return false
}

watch(
  () => [selectedClusterKey.value, displayIssueItems.value.length],
  async () => {
    if (!selectedClusterKey.value) return
    issuePagination.current = 1
    await nextTick()
    scrollToLinkedIssueRow()
  },
)

onMounted(() => {
  liveTicker = setInterval(() => {
    liveNow.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (liveTicker) {
    clearInterval(liveTicker)
    liveTicker = null
  }
})
</script>

<style scoped>
.drawer-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100vh;
  min-height: 0;
  background: #f8fafc;
}

.drawer-head {
  display: flex;
  flex: 0 0 auto;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 18px 22px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}

.result-review-header {
  min-height: 82px;
  padding-right: 24px;
  padding-left: 24px;
}

.drawer-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.drawer-back-button {
  flex: 0 0 auto;
  border-color: rgba(0, 102, 204, 0.2);
  color: #005bb5;
  font-weight: 650;
}

.drawer-back-button::before {
  content: '←';
  margin-right: 6px;
}

.drawer-eyebrow {
  margin: 0;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
  font-weight: 600;
}

.drawer-title {
  margin: 4px 0 0;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.drawer-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.drawer-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 16px 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-body > * {
  flex: 0 0 auto;
}

.status-hero {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 16px;
  border-radius: 22px;
  border: 1px solid #dbeafe;
  padding: 18px 20px;
  box-shadow: 0 14px 34px rgba(148, 163, 184, 0.16);
}

.status-hero--queued,
.status-hero--running {
  background: linear-gradient(135deg, #eff6ff 0%, #ffffff 100%);
  border-color: #bfdbfe;
}

.status-hero--completed {
  background: linear-gradient(135deg, #ecfdf5 0%, #ffffff 100%);
  border-color: #bbf7d0;
}

.status-hero--failed {
  background: linear-gradient(135deg, #fff1f2 0%, #ffffff 100%);
  border-color: #fecdd3;
}

.status-hero--canceled {
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
  border-color: #cbd5e1;
}

.status-hero-main {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  flex: 1;
  min-width: 0;
}

.status-hero-pulse {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  margin-top: 6px;
  background: #2563eb;
  box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.5);
  animation: statusPulse 1.8s infinite;
  flex: none;
}

.status-hero-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.status-hero-title {
  font-size: 18px;
  line-height: 1.35;
  font-weight: 700;
  color: #0f172a;
}

.status-hero-tag {
  margin: 0;
}

.status-hero-desc {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.65;
  color: #334155;
}

.status-hero-jobline {
  margin-top: 12px;
}

.status-hero-job-name {
  font-size: 16px;
  line-height: 1.45;
  font-weight: 700;
  color: #0f172a;
}

.status-hero-job-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.status-hero-live {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.status-hero-live span {
  border-radius: 999px;
  border: 1px solid rgba(0, 102, 204, 0.16);
  background: rgba(255, 255, 255, 0.82);
  color: #1d4ed8;
  padding: 3px 9px;
  font-size: 12px;
  line-height: 1.5;
  font-weight: 600;
}

.status-hero-flow {
  position: relative;
  height: 7px;
  margin-top: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(191, 219, 254, 0.52);
}

.status-hero-flow::after {
  position: absolute;
  inset: 0;
  content: '';
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.72), transparent);
  animation: streamScan 1.8s infinite;
}

.status-hero-flow-bar {
  position: relative;
  z-index: 1;
  height: 100%;
  min-width: 8px;
  border-radius: inherit;
  background: linear-gradient(90deg, #60a5fa, #0066cc);
  transition: width 0.45s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.status-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.status-hero-meta-item {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.24);
  padding: 3px 9px;
  font-size: 11px;
  line-height: 1.5;
  color: #475569;
}

.status-hero-side {
  min-width: 124px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.18);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 10px 12px;
  flex: none;
}

.status-hero-percent {
  font-size: 32px;
  line-height: 1;
  font-weight: 800;
  color: #0f172a;
}

.status-hero-side-label {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
  text-align: center;
}

.result-review-overview {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.04);
  padding: 18px 20px;
}

.result-overview-card {
  border-color: rgba(191, 219, 254, 0.86);
  background:
    linear-gradient(135deg, rgba(239, 246, 255, 0.92), rgba(255, 255, 255, 0.98) 44%), #ffffff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

.result-overview-card-main {
  display: grid;
  grid-template-columns: minmax(420px, 1fr) auto minmax(430px, 0.92fr);
  gap: 20px;
  align-items: center;
}

.result-overview-identity {
  display: grid;
  grid-template-columns: 50px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  min-width: 0;
}

.result-overview-icon {
  display: inline-flex;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 18px;
  font-weight: 850;
  box-shadow: inset 0 0 0 6px rgba(255, 255, 255, 0.62);
}

.result-overview-status-block {
  min-width: 0;
  border-left: 1px solid rgba(203, 213, 225, 0.72);
  padding-left: 20px;
}

.result-overview-status-label {
  display: block;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  line-height: 18px;
}

.result-overview-status-block .result-review-status-pills {
  margin-top: 0;
}

.result-review-overview-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: center;
}

.result-review-overview-copy {
  min-width: 0;
}

.result-review-overview-title-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.result-review-overview-title-row h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 800;
  line-height: 26px;
}

.result-review-status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border-radius: 999px;
  border: 1px solid rgba(16, 185, 129, 0.22);
  background: #ecfdf5;
  color: #047857;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 800;
  line-height: 20px;
}

.result-review-overview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
  line-height: 20px;
}

.result-review-overview-desc,
.result-review-overview-scope {
  margin: 8px 0 0;
  color: #334155;
  font-size: 12px;
  line-height: 20px;
}

.result-review-overview-scope {
  margin-top: 6px;
  color: #64748b;
}

.result-review-overview-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(106px, 1fr));
  gap: 0;
}

.result-review-overview-stats div {
  min-width: 104px;
  border-left: 1px solid rgba(203, 213, 225, 0.78);
  padding: 0 20px;
}

.result-review-overview-stats span {
  display: block;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
  line-height: 20px;
}

.result-review-overview-stats strong {
  margin-right: 4px;
  color: #0f172a;
  font-size: 30px;
  font-weight: 850;
  line-height: 34px;
}

.result-review-overview-stats small {
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.result-review-status-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

.result-review-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 800;
}

.result-review-status-pill strong {
  font-size: 15px;
}

.result-review-status-pill.is-danger {
  border-color: rgba(239, 68, 68, 0.22);
  background: #fef2f2;
  color: #b91c1c;
}

.result-review-status-pill.is-warning {
  border-color: rgba(245, 158, 11, 0.24);
  background: #fffbeb;
  color: #92400e;
}

.result-review-status-pill.is-success {
  border-color: rgba(16, 185, 129, 0.18);
  background: #ecfdf5;
  color: #047857;
}

.result-review-status-pill.is-muted {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #64748b;
}

.drawer-card {
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 14px 16px;
}

.issue-review-workbench-card {
  overflow: hidden;
  padding: 0;
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
}

.issue-review-workbench-card--single {
  border-color: rgba(226, 232, 240, 0.82);
  background: #fff;
}

.issue-review-workbench-card > .drawer-section-head {
  padding: 16px 18px 10px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.72);
}

.issue-review-workbench-card--single > .drawer-section-head,
.issue-review-workbench-card--single > .issue-toolbar {
  display: none;
}

.drawer-card--nested {
  margin-top: 8px;
}

.drawer-error {
  margin-top: 10px;
  border-radius: 12px;
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
  padding: 10px 12px;
  font-size: 12px;
}

.rule-set-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.rule-set-strip--hero {
  margin-top: 10px;
}

.rule-set-strip span {
  border-radius: 999px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 3px 8px;
  font-size: 11px;
  line-height: 1.5;
}

.drawer-summary {
  display: grid;
  gap: 12px;
}

.summary-grid-primary {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.summary-grid-secondary {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.summary-grid-tertiary {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.drawer-summary .summary-card {
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 14px 16px;
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.1);
}

.luxian-scope-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.luxian-scope-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.luxian-scope-stat {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 10px 12px;
}

.luxian-scope-stat span,
.luxian-scope-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.luxian-scope-stat strong {
  display: block;
  margin-top: 4px;
  font-size: 20px;
  line-height: 1.2;
  color: #0f172a;
}

.luxian-scope-stat small,
.luxian-scope-muted {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: #94a3b8;
}

.luxian-scope-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.luxian-scope-chips,
.luxian-status-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.luxian-scope-chip,
.luxian-status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: #fff;
  padding: 4px 9px;
  font-size: 12px;
  line-height: 1.4;
  color: #334155;
}

.luxian-scope-map {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 9px 11px;
  font-size: 12px;
  line-height: 1.65;
  color: #334155;
}

.luxian-status-pill.is-danger {
  border-color: #fecdd3;
  background: #fff1f2;
  color: #be123c;
}

.luxian-status-pill.is-warning {
  border-color: #fde68a;
  background: #fffbeb;
  color: #b45309;
}

.luxian-status-pill.is-success {
  border-color: #bbf7d0;
  background: #ecfdf5;
  color: #047857;
}

.luxian-status-pill.is-muted {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #64748b;
}

.luxian-review-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #f8fbff;
  border-color: #bfdbfe;
}

.luxian-review-list {
  display: grid;
  gap: 10px;
}

.luxian-review-item {
  border-radius: 12px;
  border: 1px solid #dbeafe;
  background: #fff;
  padding: 10px 12px;
}

.luxian-review-item-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.luxian-review-item-head strong {
  font-size: 13px;
  color: #0f172a;
}

.luxian-review-item-head span,
.luxian-review-item-head em {
  border-radius: 999px;
  background: #eff6ff;
  padding: 2px 7px;
  font-size: 11px;
  font-style: normal;
  color: #1d4ed8;
}

.luxian-review-item p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.65;
  color: #334155;
}

.luxian-review-item small,
.luxian-review-empty {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}

.summary-label {
  font-size: 12px;
  color: #94a3b8;
}

.summary-value {
  margin-top: 4px;
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
}

.summary-desc {
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}

.progress-meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
  flex-wrap: wrap;
}

.issue-toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.issue-toolbar--single {
  display: none;
}

.single-issue-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, auto);
  gap: 18px;
  align-items: center;
  margin: 0;
  border: 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 0;
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.92), rgba(255, 255, 255, 0.96)), #fff;
  padding: 18px 20px;
}

.single-issue-hero-main {
  min-width: 0;
}

.single-issue-hero-main span {
  display: block;
  color: #0066cc;
  font-size: 12px;
  font-weight: 750;
  line-height: 18px;
}

.single-issue-hero-main strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 24px;
  font-weight: 800;
  line-height: 30px;
}

.single-issue-hero-main p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 20px;
}

.single-issue-hero-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(96px, 1fr));
  gap: 10px;
}

.single-issue-hero-stats div {
  min-width: 96px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  padding: 12px 14px;
}

.single-issue-hero-stats span,
.single-issue-hero-stats strong {
  display: block;
}

.single-issue-hero-stats span {
  color: #64748b;
  font-size: 11px;
  font-weight: 650;
  line-height: 16px;
}

.single-issue-hero-stats strong {
  margin-top: 2px;
  color: #0f172a;
  font-size: 28px;
  font-weight: 800;
  line-height: 32px;
}

.issue-record-switcher {
  margin: 10px 0 12px;
  border: 1px solid rgba(0, 102, 204, 0.12);
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.82);
  padding: 12px;
}

.issue-record-switcher-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.issue-record-switcher-head span {
  color: #0f172a;
  font-size: 13px;
  font-weight: 750;
  line-height: 20px;
}

.issue-record-switcher-head small {
  color: #64748b;
  font-size: 12px;
  line-height: 18px;
}

.issue-record-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.issue-record-tab {
  flex: 0 0 auto;
  min-width: 178px;
  max-width: 240px;
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.86);
  color: #475569;
  cursor: pointer;
  padding: 8px 10px;
  text-align: left;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.issue-record-tab strong,
.issue-record-tab span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.issue-record-tab strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 750;
  line-height: 19px;
}

.issue-record-tab span {
  margin-top: 2px;
  color: #64748b;
  font-size: 11px;
  line-height: 16px;
}

.issue-record-tab--active {
  border-color: rgba(0, 102, 204, 0.34);
  background: rgba(0, 102, 204, 0.08);
  box-shadow: 0 6px 16px rgba(0, 102, 204, 0.08);
}

.issue-record-tab--all {
  min-width: 132px;
  max-width: 160px;
  background: rgba(248, 250, 252, 0.72);
}

.issue-business-workbench {
  margin-bottom: 12px;
}

.issue-review-layout {
  background: #f8fbff;
}

.issue-business-workbench--single {
  display: grid;
  grid-template-columns: minmax(300px, 350px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  padding: 18px;
}

.issue-group-list {
  align-self: start;
}

.issue-business-main {
  min-width: 0;
}

.issue-review-nav {
  position: sticky;
  top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: min(640px, calc(100vh - 180px));
  overflow: auto;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  padding: 16px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.035);
}

.issue-review-nav-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 2px 8px;
}

.issue-review-nav-head strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 750;
  line-height: 18px;
}

.issue-review-nav-head span {
  color: #64748b;
  font-size: 11px;
  line-height: 16px;
}

.issue-review-nav-group {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 12px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.025);
  padding: 6px 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  line-height: 18px;
}

.issue-review-nav-group:first-of-type {
  margin-top: 2px;
}

.issue-review-nav-group em {
  border-radius: 999px;
  background: #f1f5f9;
  padding: 1px 7px;
  color: #475569;
  font-size: 11px;
  font-style: normal;
  line-height: 16px;
}

.issue-review-nav-group--danger {
  color: #dc2626;
}

.issue-review-nav-group--warning {
  color: #b45309;
}

.issue-review-nav-group--review {
  color: #7c3aed;
}

.issue-review-nav-group--muted {
  color: #64748b;
}

.issue-review-nav-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  width: 100%;
  border: 1px solid rgba(226, 232, 240, 0.82);
  border-radius: 10px;
  background: #fff;
  padding: 11px 12px;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.issue-review-nav-item strong,
.issue-review-nav-item span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.issue-review-nav-item strong {
  color: #0f172a;
  font-size: 12px;
  font-weight: 750;
  line-height: 18px;
}

.issue-review-nav-item span {
  margin-top: 1px;
  color: #64748b;
  font-size: 11px;
  line-height: 16px;
}

.issue-review-nav-item em {
  border-radius: 999px;
  background: rgba(241, 245, 249, 0.94);
  color: #475569;
  padding: 2px 7px;
  font-size: 11px;
  font-style: normal;
  font-weight: 750;
  line-height: 16px;
  white-space: nowrap;
}

.issue-review-nav-item--active {
  border-color: rgba(0, 102, 204, 0.42);
  background: rgba(239, 246, 255, 0.98);
  box-shadow: 0 8px 20px rgba(0, 102, 204, 0.1);
}

.issue-review-nav-item--danger {
  border-color: rgba(239, 68, 68, 0.16);
}

.issue-review-nav-item--error {
  border-color: rgba(185, 28, 28, 0.16);
}

.issue-review-nav-item--warning {
  border-color: rgba(245, 158, 11, 0.16);
}

.issue-review-nav-item--muted {
  border-color: rgba(148, 163, 184, 0.18);
}

.issue-review-nav-item--ok {
  border-color: rgba(16, 185, 129, 0.16);
}

.issue-conclusion-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

.issue-record-result-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.issue-record-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(241, 245, 249, 0.74);
  padding: 10px 12px;
}

.issue-record-result-head strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
  font-weight: 750;
  line-height: 19px;
}

.issue-record-result-head span {
  color: #64748b;
  font-size: 12px;
  line-height: 18px;
}

.issue-record-result-stats {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.issue-record-result-stats span {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #475569;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 650;
  line-height: 18px;
}

.issue-conclusion-list-inner {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stream-result-tip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  max-width: 100%;
  margin: 0 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(0, 102, 204, 0.16);
  background: rgba(239, 246, 255, 0.9);
  color: #1d4ed8;
  padding: 6px 10px;
  font-size: 12px;
  line-height: 1.5;
  font-weight: 600;
}

.stream-result-tip--waiting {
  background: rgba(248, 250, 252, 0.96);
  color: #475569;
}

.stream-result-tip-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #0066cc;
  box-shadow: 0 0 0 0 rgba(0, 102, 204, 0.38);
  animation: statusPulse 1.8s infinite;
  flex: none;
}

.stream-waiting-card {
  position: relative;
  overflow: hidden;
  min-height: 188px;
  margin-bottom: 12px;
  border-radius: 16px;
  border: 1px dashed rgba(0, 102, 204, 0.2);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 252, 0.86)), #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.stream-waiting-scan {
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent 20%, rgba(0, 102, 204, 0.08), transparent 56%);
  animation: streamScan 2s infinite;
}

.stream-waiting-lines {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(360px, 64%);
}

.stream-waiting-lines span {
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, #e2e8f0, #f8fafc, #e2e8f0);
}

.stream-waiting-lines span:nth-child(2) {
  width: 84%;
}

.stream-waiting-lines span:nth-child(3) {
  width: 58%;
}

.stream-waiting-text {
  position: relative;
  z-index: 1;
  margin-top: 6px;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.stream-waiting-subtext {
  position: relative;
  z-index: 1;
  font-size: 12px;
  color: #64748b;
}

.no-issue-evidence-panel {
  display: grid;
  gap: 12px;
  margin-top: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: #ffffff;
  padding: 14px;
}

.no-issue-evidence-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
}

.no-issue-evidence-head > div {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.no-issue-evidence-head strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 750;
  line-height: 20px;
}

.no-issue-evidence-head span {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  line-height: 18px;
}

.no-issue-evidence-list {
  display: grid;
  gap: 8px;
}

.no-issue-evidence-item {
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.72);
}

.no-issue-evidence-item summary {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-height: 42px;
  padding: 10px 12px;
  cursor: pointer;
  list-style: none;
}

.no-issue-evidence-item summary::-webkit-details-marker {
  display: none;
}

.no-issue-evidence-item summary strong {
  overflow: hidden;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 700;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-issue-evidence-item summary em {
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
  color: rgba(29, 29, 31, 0.66);
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
  line-height: 20px;
  padding: 0 8px;
}

.no-issue-evidence-body {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  background: #ffffff;
  padding: 10px 12px 12px;
}

.no-issue-evidence-body span {
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 700;
  line-height: 20px;
}

.no-issue-evidence-body p {
  margin: 0;
  color: rgba(29, 29, 31, 0.82);
  font-size: 13px;
  font-weight: 600;
  line-height: 22px;
}

.issue-stream-enter-active,
.issue-stream-leave-active {
  transition: all 0.32s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.issue-stream-enter-from,
.issue-stream-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.issue-conclusion-card {
  position: relative;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
  padding: 16px 18px 14px;
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.08);
}

.issue-conclusion-card::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 5px;
  background: #94a3b8;
  content: '';
}

.issue-conclusion-card--danger {
  border-color: rgba(239, 68, 68, 0.22);
  background: linear-gradient(90deg, rgba(254, 242, 242, 0.76), #fff 34%);
}

.issue-conclusion-card--danger::before {
  background: #ef4444;
}

.issue-conclusion-card--warning {
  border-color: rgba(245, 158, 11, 0.24);
  background: linear-gradient(90deg, rgba(255, 251, 235, 0.72), #fff 36%);
}

.issue-conclusion-card--warning::before {
  background: #f59e0b;
}

.issue-conclusion-card--success::before {
  background: #10b981;
}

.issue-conclusion-card--muted::before {
  background: #94a3b8;
}

.issue-business-workbench--single .issue-conclusion-card {
  border-radius: 18px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.issue-business-workbench--single .issue-conclusion-card--danger,
.issue-business-workbench--single .issue-conclusion-card--warning {
  background: #fff;
}

.issue-business-workbench--single .issue-conclusion-card::before {
  width: 4px;
}

.issue-business-workbench--single .issue-at-a-glance {
  grid-template-columns: minmax(0, 1fr) minmax(300px, 0.72fr);
  gap: 12px;
}

.issue-business-workbench--single .issue-glance-block {
  min-height: 0;
  border-color: rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.72);
}

.issue-business-workbench--single .issue-glance-block--conclusion {
  grid-column: 1 / -1;
  background: rgba(255, 255, 255, 0.86);
}

.issue-detail-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 560px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: #fff;
  padding: 0;
  overflow: hidden;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
}

.issue-detail-panel::before {
  width: 3px;
  background: rgba(29, 29, 31, 0.18);
}

.issue-detail-panel.issue-conclusion-card--danger {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-detail-panel.issue-conclusion-card--danger::before {
  background: #ef4444;
}

.issue-detail-panel.issue-conclusion-card--warning {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-detail-panel.issue-conclusion-card--warning::before {
  background: #f59e0b;
}

.issue-detail-panel.issue-conclusion-card--muted {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-detail-panel.issue-conclusion-card--muted::before {
  background: rgba(29, 29, 31, 0.2);
}

.issue-detail-panel.issue-conclusion-card--success {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-detail-panel.issue-conclusion-card--success::before {
  background: #10b981;
}

.issue-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.82);
  padding: 20px 22px 15px;
}

.issue-detail-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.issue-detail-title-row strong {
  color: #0f172a;
  font-size: 18px;
  font-weight: 800;
  line-height: 24px;
}

.issue-detail-body {
  display: grid;
  gap: 16px;
  padding: 0 22px 20px;
}

.issue-review-reading-path {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 0 22px;
  border-radius: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.72);
  padding: 10px;
}

.issue-review-reading-step {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  grid-template-areas:
    'num title'
    'num desc';
  column-gap: 8px;
  align-items: center;
  min-width: 0;
  border-radius: 10px;
  padding: 8px;
}

.issue-review-reading-step.is-active {
  background: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(0, 102, 204, 0.14);
}

.issue-review-reading-step span {
  grid-area: num;
  display: inline-flex;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-size: 12px;
  font-weight: 800;
}

.issue-review-reading-step.is-active span {
  background: rgba(0, 102, 204, 0.1);
  color: #0066cc;
}

.issue-review-reading-step strong {
  grid-area: title;
  overflow: hidden;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 750;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.issue-review-reading-step em {
  grid-area: desc;
  overflow: hidden;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-style: normal;
  font-weight: 600;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.issue-patient-context-card {
  position: relative;
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  margin: 0 22px;
  border: 1px solid rgba(0, 102, 204, 0.14);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.72), rgba(255, 255, 255, 0.94));
  padding: 14px 16px;
  box-shadow: 0 6px 20px rgba(0, 102, 204, 0.055);
}

.issue-patient-avatar {
  display: inline-flex;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid rgba(0, 102, 204, 0.18);
  background: #ffffff;
  color: #0066cc;
  font-size: 17px;
  font-weight: 800;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.08);
}

.issue-patient-context-main {
  display: grid;
  grid-template-columns: minmax(160px, auto) minmax(0, 1fr);
  gap: 4px 16px;
  align-items: center;
  min-width: 0;
}

.issue-patient-context-kicker {
  grid-column: 1;
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.issue-patient-context-id {
  grid-column: 1;
  display: block;
  color: #1d1d1f;
  font-size: 20px;
  font-weight: 800;
  line-height: 26px;
  letter-spacing: 0;
}

.issue-patient-context-meta {
  grid-row: 1 / span 2;
  grid-column: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.issue-patient-context-meta span {
  display: inline-flex;
  max-width: 100%;
  min-height: 30px;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  padding: 4px 10px;
  color: rgba(29, 29, 31, 0.78);
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.issue-patient-context-meta em {
  color: rgba(29, 29, 31, 0.46);
  font-style: normal;
  font-weight: 700;
}

.issue-detail-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
  gap: 16px;
  align-items: stretch;
}

.issue-detail-section {
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: #ffffff;
  padding: 14px 16px;
}

.issue-detail-section--conclusion {
  border-color: rgba(0, 0, 0, 0.08);
  background: #ffffff;
}

.issue-detail-panel.issue-conclusion-card--warning .issue-detail-section--conclusion {
  border-color: rgba(0, 0, 0, 0.08);
  background: #ffffff;
}

.issue-detail-panel.issue-conclusion-card--muted .issue-detail-section--conclusion {
  border-color: rgba(0, 0, 0, 0.08);
  background: #ffffff;
}

.issue-detail-section-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 800;
  line-height: 20px;
}

.issue-detail-section-title span {
  display: inline-flex;
  min-width: 24px;
  height: 20px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-size: 11px;
  font-weight: 850;
}

.issue-detail-section p {
  margin: 0;
  color: #0f172a;
  font-size: 14px;
  font-weight: 600;
  line-height: 24px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.issue-detail-text {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.issue-detail-text ul {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 18px;
  color: rgba(29, 29, 31, 0.82);
  font-size: 14px;
  line-height: 24px;
}

.issue-detail-text li {
  padding-left: 2px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.evidence-table-card {
  padding: 0;
  overflow: hidden;
}

.evidence-table-card .issue-detail-section-title {
  margin: 0;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 12px 16px;
}

.evidence-table {
  display: grid;
  gap: 0;
}

.evidence-table-row {
  position: relative;
  display: grid;
  grid-template-columns: minmax(148px, 0.42fr) minmax(0, 1fr);
  gap: 18px;
  align-items: center;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
  padding: 13px 16px;
}

.evidence-table-row:last-child {
  border-bottom: 0;
}

.evidence-table-row span {
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
  line-height: 20px;
}

.evidence-table-row strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
  line-height: 22px;
  word-break: break-word;
}

.evidence-table-row--threshold,
.evidence-table-row--gap,
.evidence-table-row--duration {
  background: rgba(248, 250, 252, 0.72);
}

.evidence-table-card > p {
  margin: 0;
  padding: 14px 16px;
}

.structured-evidence-list {
  display: grid;
  gap: 10px;
  padding: 12px 16px 14px;
}

.structured-evidence-list--inline {
  padding: 0;
}

.structured-evidence-card {
  display: grid;
  gap: 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.84);
  padding: 10px 12px;
}

.structured-evidence-card-head {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.structured-evidence-card-head strong,
.structured-evidence-card-head span {
  display: inline-flex;
  min-height: 22px;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.structured-evidence-card-head strong {
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
}

.structured-evidence-card-head span {
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.62);
}

.structured-evidence-card blockquote {
  margin: 0;
  border-left: 3px solid rgba(0, 102, 204, 0.16);
  padding-left: 10px;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 650;
  line-height: 1.75;
  word-break: break-word;
}

.suggestion-panel {
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.72);
  padding: 14px 16px;
}

.suggestion-panel p {
  margin: 0;
  color: #0f172a;
  font-size: 14px;
  line-height: 24px;
}

.issue-detail-panel .copy-evidence-compare,
.issue-detail-panel .evidence-chain-strip,
.issue-detail-panel .evidence-chain-panel,
.issue-detail-panel .issue-conclusion-actions {
  margin-right: 20px;
  margin-left: 20px;
}

.issue-detail-panel .issue-conclusion-actions {
  border-top: 1px solid rgba(226, 232, 240, 0.82);
  padding: 12px 0 14px;
}

.issue-conclusion-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.issue-conclusion-status {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.issue-result-kind {
  display: inline-flex;
  min-height: 24px;
  align-items: center;
  border-radius: 999px;
  padding: 0 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  line-height: 20px;
  white-space: nowrap;
}

.issue-result-kind--danger {
  border-color: rgba(239, 68, 68, 0.2);
  background: #fef2f2;
  color: #b91c1c;
}

.issue-result-kind--error {
  border-color: rgba(127, 29, 29, 0.18);
  background: #fff1f2;
  color: #9f1239;
}

.issue-result-kind--review {
  border-color: rgba(245, 158, 11, 0.2);
  background: #fffbeb;
  color: #92400e;
}

.issue-result-kind--muted {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #64748b;
}

.issue-result-kind--ok {
  border-color: rgba(16, 185, 129, 0.18);
  background: #ecfdf5;
  color: #047857;
}

.issue-conclusion-head-main {
  flex: 1;
  min-width: 0;
}

.issue-conclusion-title-row {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 8px;
}

.issue-rule-code {
  flex-shrink: 0;
  border-radius: 8px;
  background: rgba(0, 102, 204, 0.09);
  color: #0066cc;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 750;
  line-height: 18px;
}

.issue-conclusion-title {
  display: block;
  font-size: 14px;
  line-height: 1.5;
  color: #0f172a;
  font-weight: 700;
  word-break: break-word;
}

.issue-conclusion-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0 0;
}

.issue-conclusion-meta span {
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  padding: 2px 7px;
  font-size: 11px;
}

.issue-at-a-glance {
  display: grid;
  grid-template-columns: 1.1fr 1.4fr 1.1fr;
  gap: 10px;
  margin: 12px 0;
}

.issue-glance-block {
  min-width: 0;
  border: 1px solid rgba(226, 232, 240, 0.82);
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.82);
  padding: 10px 12px;
}

.issue-glance-block--conclusion {
  background: rgba(239, 68, 68, 0.045);
}

.issue-glance-label {
  margin-bottom: 5px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.issue-glance-block strong,
.issue-glance-block span {
  display: block;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.65;
  word-break: break-word;
}

.issue-glance-block strong {
  font-weight: 750;
}

.issue-glance-text {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.issue-glance-text p {
  margin: 0;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 650;
  line-height: 21px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.issue-glance-text ul {
  display: grid;
  gap: 4px;
  margin: 0;
  padding-left: 17px;
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

.issue-glance-text li {
  overflow-wrap: anywhere;
  word-break: break-word;
}

.issue-evidence-facts {
  display: grid;
  gap: 6px;
}

.issue-evidence-fact {
  display: grid;
  grid-template-columns: minmax(76px, 0.42fr) minmax(0, 1fr);
  align-items: start;
  gap: 8px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.72);
  padding: 6px 8px;
}

.issue-evidence-fact span {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.issue-evidence-fact strong {
  color: #0f172a;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.issue-evidence-fact--delta {
  border-color: rgba(245, 158, 11, 0.22);
  background: rgba(255, 251, 235, 0.72);
}

.issue-evidence-fact--time {
  border-color: rgba(0, 102, 204, 0.14);
  background: rgba(239, 246, 255, 0.64);
}

.copy-evidence-compare {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 2px 22px 12px;
  border-radius: 16px;
  border: 1px solid rgba(245, 158, 11, 0.22);
  background: linear-gradient(180deg, rgba(255, 251, 235, 0.58), rgba(255, 255, 255, 0.92));
  padding: 12px;
}

.copy-evidence-head {
  grid-column: 1 / -1;
  display: grid;
  gap: 3px;
}

.copy-evidence-head strong {
  color: #92400e;
  font-size: 14px;
  font-weight: 800;
  line-height: 20px;
}

.copy-evidence-head span {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.copy-evidence-legacy-note {
  grid-column: 1 / -1;
  border: 1px solid rgba(0, 102, 204, 0.16);
  border-radius: 12px;
  background: rgba(239, 246, 255, 0.72);
  padding: 8px 10px;
  color: #0052a3;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.copy-evidence-column {
  min-width: 0;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.88);
  padding: 10px 12px;
}

.copy-evidence-column--metric {
  grid-column: 1 / -1;
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(255, 251, 235, 0.86);
}

.copy-evidence-column--gap {
  grid-column: 1 / -1;
  border-color: rgba(0, 102, 204, 0.16);
  background: rgba(239, 246, 255, 0.72);
}

.copy-evidence-pair {
  grid-column: 1 / -1;
  min-width: 0;
  display: grid;
  gap: 8px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.62);
  padding: 10px;
}

.copy-evidence-pair-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #92400e;
  font-size: 12px;
  font-weight: 800;
  line-height: 18px;
}

.copy-evidence-pair-head span {
  flex: none;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.12);
  padding: 2px 8px;
  color: #b45309;
  font-size: 11px;
  font-weight: 800;
}

.copy-evidence-pair-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.copy-evidence-label {
  margin-bottom: 6px;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.copy-evidence-column blockquote {
  margin: 0;
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.72);
  padding: 8px 10px;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.7;
  word-break: break-word;
}

.evidence-chain-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0 12px;
}

.evidence-chain-strip span,
.evidence-chain-tag {
  border-radius: 999px;
  border: 1px solid rgba(0, 102, 204, 0.18);
  background: rgba(0, 102, 204, 0.06);
  color: #0066cc;
  padding: 2px 8px;
  font-size: 11px;
  line-height: 1.5;
  font-weight: 600;
}

.evidence-chain-panel,
.deep-review-chain {
  border-radius: 16px;
  border: 1px solid rgba(0, 102, 204, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 252, 0.86));
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
  padding: 12px 14px;
  margin: 8px 0 12px;
}

.evidence-chain-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.evidence-chain-title {
  font-size: 14px;
  line-height: 1.5;
  color: #0f172a;
  font-weight: 700;
}

.evidence-chain-subtitle {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}

.evidence-chain-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.evidence-chain-block {
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.78);
  padding: 10px 12px;
  min-width: 0;
}

.evidence-chain-block-title {
  margin-bottom: 8px;
  color: #475569;
  font-size: 12px;
  line-height: 1.4;
  font-weight: 700;
}

.evidence-chain-line {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.evidence-chain-line + .evidence-chain-line {
  border-top: 1px dashed rgba(203, 213, 225, 0.75);
}

.evidence-chain-line strong {
  min-width: 0;
  color: #0f172a;
  font-weight: 500;
  word-break: break-word;
}

.evidence-chain-evidence-list {
  margin-top: 12px;
  border-top: 1px solid rgba(226, 232, 240, 0.86);
  padding-top: 10px;
}

.evidence-chain-evidence {
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.88);
  border: 1px solid rgba(226, 232, 240, 0.86);
  padding: 10px 12px;
}

.evidence-chain-evidence + .evidence-chain-evidence {
  margin-top: 8px;
}

.evidence-chain-evidence-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.evidence-chain-evidence-meta span {
  border-radius: 999px;
  background: #eef2f7;
  color: #475569;
  padding: 2px 7px;
  font-size: 11px;
  line-height: 1.4;
}

.evidence-chain-quote {
  color: #0f172a;
  font-size: 12px;
  line-height: 1.75;
  word-break: break-word;
}

.issue-conclusion-summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
  border-top: 1px solid rgba(226, 232, 240, 0.9);
  padding-top: 12px;
}

.issue-conclusion-row {
  font-size: 13px;
  color: #334155;
  line-height: 1.7;
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr);
  gap: 10px;
}

.issue-conclusion-actions {
  margin-top: 12px;
  border-top: 1px solid rgba(226, 232, 240, 0.82);
  padding-top: 8px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.issue-conclusion-label {
  color: #64748b;
  font-weight: 700;
}

.issue-conclusion-structured {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.issue-conclusion-structured p {
  margin: 0;
  color: #1d1d1f;
  font-size: 13px;
  line-height: 1.8;
}

.issue-conclusion-structured ul {
  display: grid;
  gap: 5px;
  margin: 0;
  padding-left: 18px;
  color: #334155;
}

.issue-conclusion-structured li {
  line-height: 1.75;
}

.structured-text-section {
  display: grid;
  gap: 6px;
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.72);
  padding: 8px 10px;
}

.structured-text-section > strong {
  color: #475569;
  font-size: 12px;
  font-weight: 800;
  line-height: 18px;
}

.issue-conclusion-summary-text {
  color: #0f172a;
  margin: 0;
}

.issue-conclusion-section {
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.68);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.issue-conclusion-section-title {
  font-size: 12px;
  line-height: 1.6;
  font-weight: 700;
  color: #1e3a8a;
}

.issue-conclusion-points {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #334155;
}

.issue-conclusion-points li::marker {
  color: #64748b;
}

.drawer-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 10px;
}

.drawer-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.drawer-section-head .drawer-section-title {
  margin-bottom: 0;
}

.drawer-section-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.summary-mode-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 2px 8px;
  font-size: 11px;
  line-height: 1.4;
  font-weight: 600;
}

.deep-review-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.deep-review-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.deep-review-title {
  font-size: 16px;
  line-height: 1.5;
  font-weight: 700;
  color: #0f172a;
}

.deep-review-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.deep-review-meta span {
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  padding: 2px 8px;
  font-size: 11px;
  line-height: 1.4;
}

.deep-review-section {
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 12px 14px;
}

.deep-review-label {
  font-size: 12px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 8px;
}

.deep-review-content {
  font-size: 13px;
  line-height: 1.8;
  color: #0f172a;
  white-space: pre-wrap;
  word-break: break-word;
}

.result-trace-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-trace-sections {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 14px;
}

.result-trace-section {
  border: 1px solid rgba(226, 232, 240, 0.92);
  border-radius: 10px;
  background: #fff;
  padding: 14px;
}

.result-trace-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.result-trace-section-head h4 {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}

.result-trace-section-head p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.result-trace-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.result-trace-row {
  border-radius: 8px;
  background: #f8fafc;
  min-width: 0;
  padding: 8px 10px;
}

.result-trace-row span {
  display: block;
  color: #64748b;
  font-size: 12px;
  margin-bottom: 4px;
}

.result-trace-row strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.result-trace-empty {
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  font-size: 13px;
  padding: 12px;
}

.drawer-section-meta {
  font-size: 12px;
  color: #64748b;
}

.drawer-section-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.issue-focus-summary {
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.88);
  background: rgba(248, 250, 252, 0.9);
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
  padding: 9px 12px;
}

.issue-filter-bar {
  display: grid;
  grid-template-columns: minmax(160px, 1.4fr) repeat(3, minmax(90px, 1fr)) auto;
  gap: 8px;
}

.issue-filter-item {
  min-width: 0;
}

.debug-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.debug-rule-select {
  min-width: 240px;
}

.aggregation-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.aggregation-breakdown-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.aggregation-breakdown-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 10px 12px;
}

.aggregation-breakdown-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.aggregation-breakdown-title {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
}

.aggregation-breakdown-count {
  font-size: 13px;
  font-weight: 700;
  color: #1e40af;
}

.aggregation-breakdown-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.aggregation-breakdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.aggregation-breakdown-item-label {
  font-size: 12px;
  color: #475569;
  line-height: 1.45;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.aggregation-breakdown-item-tag {
  color: #1e40af;
  border-color: #bfdbfe;
  background: #eff6ff;
  margin: 0;
}

.aggregation-breakdown-empty {
  margin-top: 10px;
  font-size: 12px;
  color: #94a3b8;
}

.aggregation-item {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 10px 12px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.aggregation-item.active {
  border-color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(191, 219, 254, 0.45);
}

.aggregation-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.aggregation-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.aggregation-count-tag {
  color: #1e40af;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.aggregation-evidence {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #475569;
}

.aggregation-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}

.aggregation-active-tip {
  margin-bottom: 12px;
  border-radius: 10px;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1e3a8a;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
}

.issue-pagination {
  display: flex;
  justify-content: flex-end;
}

.drawer-advanced-collapse {
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  overflow: hidden;
}

:deep(.drawer-advanced-collapse .ant-collapse-item) {
  border-bottom: 1px solid #e2e8f0;
}

:deep(.drawer-advanced-collapse .ant-collapse-item:last-child) {
  border-bottom: none;
}

:deep(.drawer-advanced-collapse .ant-collapse-header) {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  background: #fff;
}

:deep(.drawer-advanced-collapse .ant-collapse-content-box) {
  padding: 0 16px 16px;
  background: #f8fafc;
}

.debug-current-rule {
  border-radius: 12px;
  border: 1px solid #dbeafe;
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.95), #fff);
  padding: 10px 12px;
}

.debug-current-rule-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.debug-current-rule-label {
  font-size: 11px;
  color: #64748b;
}

.debug-current-rule-value {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.debug-current-rule-sub {
  margin-top: 6px;
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}

.debug-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.debug-meta-item {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 8px 10px;
}

.debug-meta-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
}

.debug-meta-value {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  color: #0f172a;
  font-weight: 600;
  word-break: break-word;
}

.debug-pill-block {
  margin-top: 12px;
}

.debug-pill-title {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
}

.debug-pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.debug-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 999px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1e40af;
  padding: 4px 10px;
  font-size: 12px;
  line-height: 1.4;
}

.debug-pill-muted {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #475569;
}

.focus-record-card {
  margin-bottom: 16px;
}

.focus-record-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

/* Result review follows workstation-v4 light medical back-office tokens. */
.drawer-shell {
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.result-review-header {
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(18px);
}

.result-review-header .drawer-back-button,
.result-review-header :deep(.ant-btn:not(.ant-btn-primary)) {
  border-color: rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 600;
}

.result-review-header :deep(.ant-btn-primary) {
  border-color: #0066cc;
  border-radius: 8px;
  background: #0066cc;
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.16);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}

.result-review-header .drawer-back-button {
  color: #0066cc;
}

.result-overview-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.045),
    0 6px 22px rgba(0, 0, 0, 0.04);
  backdrop-filter: blur(18px);
}

.result-overview-icon {
  border-color: rgba(0, 102, 204, 0.16);
  border-radius: 12px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  box-shadow: none;
}

.result-review-overview-title-row h3,
.issue-detail-title-row strong,
.issue-patient-context-id,
.issue-review-nav-head strong,
.issue-review-nav-item strong,
.issue-detail-section p,
.suggestion-panel p,
.result-review-overview-stats strong {
  color: #1d1d1f;
}

.result-review-overview-title-row h3 {
  font-size: 17px;
  line-height: 22px;
  font-weight: 600;
}

.result-review-overview-meta,
.result-review-overview-desc,
.result-review-overview-scope,
.result-overview-status-label,
.result-review-overview-stats span,
.result-review-overview-stats small,
.issue-review-nav-head span,
.issue-review-nav-item span,
.issue-detail-section-title,
.evidence-table-row span {
  color: rgba(29, 29, 31, 0.6);
}

.result-review-overview-stats div,
.result-overview-status-block {
  border-left-color: rgba(0, 0, 0, 0.08);
}

.result-review-overview-stats strong {
  font-size: 28px;
  line-height: 32px;
}

.result-review-status-chip,
.result-review-status-pill,
.issue-result-kind,
.aggregation-count-tag {
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.result-review-status-chip {
  border-color: rgba(16, 185, 129, 0.18);
  background: rgba(16, 185, 129, 0.08);
  color: #087f5b;
}

.result-review-status-pill {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.82);
  color: rgba(29, 29, 31, 0.72);
}

.result-review-status-pill.is-danger {
  border-color: rgba(239, 68, 68, 0.24);
  background: rgba(239, 68, 68, 0.08);
  color: #c92a2a;
}

.result-review-status-pill.is-warning {
  border-color: rgba(245, 158, 11, 0.24);
  background: rgba(245, 158, 11, 0.08);
  color: #b45309;
}

.result-review-status-pill.is-success {
  border-color: rgba(16, 185, 129, 0.2);
  background: rgba(16, 185, 129, 0.08);
  color: #087f5b;
}

.issue-review-workbench-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.04),
    0 6px 22px rgba(0, 0, 0, 0.035);
  backdrop-filter: blur(18px);
}

.issue-review-workbench-card--single {
  padding: 16px;
  overflow: visible;
}

.issue-review-layout {
  background: transparent;
  gap: 16px;
}

.issue-review-nav,
.issue-detail-panel {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: none;
}

.issue-review-nav-item {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.72);
  transition:
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    background 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.issue-review-nav-item:hover {
  transform: translateY(-1px);
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.06),
    0 6px 22px rgba(0, 0, 0, 0.04);
}

.issue-review-nav-item--active {
  border-color: rgba(0, 102, 204, 0.28);
  background: rgba(0, 102, 204, 0.08);
  box-shadow: none;
}

.issue-review-nav-item--danger {
  border-color: rgba(239, 68, 68, 0.16);
}

.issue-review-nav-item--warning {
  border-color: rgba(245, 158, 11, 0.16);
}

.issue-review-nav-item--muted,
.issue-review-nav-item--ok {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-review-nav-group {
  color: rgba(29, 29, 31, 0.72);
}

.issue-review-nav-group em,
.issue-review-nav-item em {
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.72);
  font-weight: 600;
}

.issue-detail-panel {
  overflow: visible;
}

.issue-detail-panel::before,
.issue-detail-panel.issue-conclusion-card::before,
.issue-business-workbench--single .issue-conclusion-card::before {
  display: none;
}

.issue-detail-panel.issue-conclusion-card--danger {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-detail-panel.issue-conclusion-card--warning {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-detail-panel.issue-conclusion-card--muted,
.issue-detail-panel.issue-conclusion-card--success {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-detail-head {
  border-bottom-color: rgba(0, 0, 0, 0.08);
}

.issue-rule-code {
  border-color: rgba(0, 102, 204, 0.12);
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
}

.issue-detail-section,
.evidence-table-card,
.suggestion-panel {
  border-color: rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
}

.issue-patient-context-card {
  border-color: rgba(0, 102, 204, 0.14);
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.72), rgba(255, 255, 255, 0.94));
}

.issue-patient-avatar {
  border-color: rgba(0, 102, 204, 0.14);
  background: #ffffff;
  color: #0066cc;
}

.issue-detail-section--conclusion {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.82);
}

.issue-detail-panel.issue-conclusion-card--danger .issue-detail-section--conclusion {
  border-color: rgba(239, 68, 68, 0.18);
  background: rgba(239, 68, 68, 0.045);
}

.issue-detail-panel.issue-conclusion-card--warning .issue-detail-section--conclusion {
  border-color: rgba(245, 158, 11, 0.18);
  background: rgba(245, 158, 11, 0.055);
}

.evidence-table-card .issue-detail-section-title {
  border-bottom-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.025);
}

.evidence-table-row {
  border-bottom-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.74);
}

.evidence-table-row--threshold,
.evidence-table-row--gap,
.evidence-table-row--duration {
  background: rgba(245, 158, 11, 0.06);
}

.evidence-table-row strong {
  color: #1d1d1f;
}

.suggestion-panel {
  border-color: rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.045);
}

.issue-result-kind--danger,
.issue-result-kind--error {
  border-color: rgba(239, 68, 68, 0.22);
  background: rgba(239, 68, 68, 0.08);
  color: #c92a2a;
}

.issue-result-kind--review {
  border-color: rgba(245, 158, 11, 0.22);
  background: rgba(245, 158, 11, 0.08);
  color: #b45309;
}

.issue-result-kind--muted {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.6);
}

.issue-result-kind--ok {
  border-color: rgba(16, 185, 129, 0.18);
  background: rgba(16, 185, 129, 0.08);
  color: #087f5b;
}

/* Reduce chroma density: keep status color in compact tags only. */
.issue-review-nav-group--danger,
.issue-review-nav-group--warning,
.issue-review-nav-group--review,
.issue-review-nav-group--muted {
  color: rgba(29, 29, 31, 0.7);
}

.issue-review-nav-item--danger,
.issue-review-nav-item--error,
.issue-review-nav-item--warning,
.issue-review-nav-item--muted,
.issue-review-nav-item--ok {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-review-nav-item--active {
  border-color: rgba(0, 102, 204, 0.28);
  background: rgba(0, 102, 204, 0.055);
}

.issue-detail-panel.issue-conclusion-card--danger,
.issue-detail-panel.issue-conclusion-card--warning,
.issue-detail-panel.issue-conclusion-card--muted,
.issue-detail-panel.issue-conclusion-card--success {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-detail-section--conclusion,
.issue-detail-panel.issue-conclusion-card--danger .issue-detail-section--conclusion,
.issue-detail-panel.issue-conclusion-card--warning .issue-detail-section--conclusion,
.issue-detail-panel.issue-conclusion-card--muted .issue-detail-section--conclusion {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.62);
}

.evidence-table-row--threshold,
.evidence-table-row--gap,
.evidence-table-row--duration {
  background: rgba(248, 250, 252, 0.72);
}

.suggestion-panel {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.72);
}

.copy-evidence-compare {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.82);
}

.copy-evidence-head strong,
.copy-evidence-pair-head {
  color: #1d1d1f;
}

.copy-evidence-column--metric,
.copy-evidence-column--gap {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.72);
}

.copy-evidence-pair {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
}

.copy-evidence-pair-head span {
  background: rgba(0, 0, 0, 0.045);
  color: rgba(29, 29, 31, 0.62);
}

.issue-evidence-fact--delta,
.issue-evidence-fact--time {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.72);
}

/* Final low-chroma pass: reserve strong color for primary action and confirmed problem only. */
.result-review-status-pill.is-warning,
.result-review-status-pill.is-success,
.result-review-status-pill.is-muted,
.issue-result-kind--review,
.issue-result-kind--ok,
.issue-result-kind--muted,
.aggregation-count-tag,
.evidence-chain-strip span,
.evidence-chain-tag {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.035);
  color: rgba(29, 29, 31, 0.68);
}

.result-review-status-pill.is-danger,
.issue-result-kind--danger,
.issue-result-kind--error {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.055);
  color: #b42318;
}

.issue-review-reading-step.is-active {
  background: rgba(0, 102, 204, 0.045);
  box-shadow: inset 0 0 0 1px rgba(0, 102, 204, 0.12);
}

.copy-evidence-legacy-note,
.evidence-chain-panel,
.deep-review-chain {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.72);
  color: rgba(29, 29, 31, 0.7);
  box-shadow: none;
}

.evidence-chain-block,
.evidence-chain-evidence {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.74);
}

.evidence-chain-title,
.evidence-chain-block-title,
.evidence-chain-line strong,
.evidence-chain-evidence-meta strong {
  color: #1d1d1f;
}

/* Workstation-v4 result detail polish: quiet medical review surface. */
.issue-business-workbench--single {
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 18px;
  background: #f5f5f7;
  padding: 16px;
}

.issue-review-nav {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: none;
}

.issue-review-nav-group {
  border-radius: 0;
  background: transparent;
  padding: 10px 2px 6px;
  color: rgba(29, 29, 31, 0.64);
}

.issue-review-nav-group--danger,
.issue-review-nav-group--warning,
.issue-review-nav-group--review,
.issue-review-nav-group--muted {
  color: rgba(29, 29, 31, 0.72);
}

.issue-review-nav-item {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: none;
}

.issue-review-nav-item--active {
  border-color: rgba(0, 102, 204, 0.2);
  background: rgba(0, 102, 204, 0.055);
  box-shadow: none;
}

.issue-review-nav-item--danger,
.issue-review-nav-item--error,
.issue-review-nav-item--warning,
.issue-review-nav-item--muted,
.issue-review-nav-item--ok {
  border-color: rgba(0, 0, 0, 0.08);
}

.issue-review-nav-item .issue-review-nav-code,
.issue-review-nav-item .issue-review-nav-title {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.issue-review-nav-item .issue-review-nav-code {
  color: #0f172a;
  font-size: 12px;
  font-weight: 700;
  line-height: 17px;
}

.issue-review-nav-item .issue-review-nav-title {
  margin-top: 3px;
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
  font-weight: 600;
  line-height: 18px;
}

.issue-detail-panel,
.issue-detail-panel.issue-conclusion-card--danger,
.issue-detail-panel.issue-conclusion-card--warning,
.issue-detail-panel.issue-conclusion-card--muted,
.issue-detail-panel.issue-conclusion-card--success {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.04),
    0 6px 22px rgba(0, 0, 0, 0.035);
}

.issue-detail-panel::before,
.issue-detail-panel.issue-conclusion-card--danger::before,
.issue-detail-panel.issue-conclusion-card--warning::before,
.issue-detail-panel.issue-conclusion-card--muted::before,
.issue-detail-panel.issue-conclusion-card--success::before {
  display: none;
}

.issue-detail-head {
  padding: 18px 22px 14px;
}

.issue-detail-title-row strong {
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 700;
  line-height: 24px;
}

.issue-review-reading-path {
  margin: 0 22px;
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.72);
}

.issue-review-reading-step {
  background: transparent;
}

.issue-review-reading-step.is-active {
  background: rgba(255, 255, 255, 0.76);
  box-shadow: inset 0 0 0 1px rgba(0, 102, 204, 0.1);
}

.issue-patient-context-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: #ffffff;
  box-shadow: none;
}

.issue-patient-avatar {
  border: 1px solid rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.06);
  box-shadow: none;
}

.issue-patient-context-meta span {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.82);
}

.issue-detail-section,
.evidence-table-card,
.suggestion-panel,
.copy-evidence-compare,
.evidence-chain-panel,
.deep-review-chain {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: #ffffff;
  box-shadow: none;
}

.issue-detail-section--conclusion,
.issue-detail-panel.issue-conclusion-card--danger .issue-detail-section--conclusion,
.issue-detail-panel.issue-conclusion-card--warning .issue-detail-section--conclusion,
.issue-detail-panel.issue-conclusion-card--muted .issue-detail-section--conclusion,
.issue-detail-panel.issue-conclusion-card--success .issue-detail-section--conclusion {
  border-color: rgba(0, 0, 0, 0.08);
  background: #ffffff;
}

.issue-detail-section--conclusion p {
  color: #1d1d1f;
  font-weight: 650;
}

.evidence-table-card .issue-detail-section-title {
  border-bottom-color: rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.72);
}

.evidence-table-row,
.evidence-table-row--threshold,
.evidence-table-row--gap,
.evidence-table-row--duration {
  border-bottom-color: rgba(0, 0, 0, 0.08);
  background: #ffffff;
}

.evidence-table-row span {
  color: rgba(29, 29, 31, 0.58);
  font-weight: 650;
}

.evidence-table-row strong {
  color: #1d1d1f;
  font-weight: 700;
}

.suggestion-panel {
  background: rgba(248, 250, 252, 0.72);
}

.suggestion-panel p,
.suggestion-panel li {
  color: rgba(29, 29, 31, 0.82);
  font-weight: 550;
}

.copy-evidence-head,
.copy-evidence-pair-head {
  border-bottom-color: rgba(0, 0, 0, 0.08);
}

.copy-evidence-pair,
.copy-evidence-column,
.copy-evidence-column--metric,
.copy-evidence-column--gap,
.evidence-chain-block,
.evidence-chain-evidence {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(248, 250, 252, 0.72);
}

.copy-evidence-column blockquote,
.evidence-chain-quote {
  color: rgba(29, 29, 31, 0.82);
}

@media (max-width: 767px) {
  .status-hero {
    flex-direction: column;
  }

  .status-hero-side {
    width: 100%;
    min-width: 0;
  }

  .summary-grid-primary,
  .summary-grid-secondary,
  .aggregation-breakdown-grid,
  .debug-meta-grid {
    grid-template-columns: 1fr;
  }

  .issue-filter-bar {
    grid-template-columns: 1fr;
  }

  .single-issue-hero,
  .issue-business-workbench--single {
    grid-template-columns: 1fr;
  }

  .single-issue-hero-stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .issue-review-nav {
    position: relative;
    top: auto;
    max-height: none;
  }

  .issue-at-a-glance {
    grid-template-columns: 1fr;
  }

  .copy-evidence-compare {
    grid-template-columns: 1fr;
  }

  .copy-evidence-pair-grid {
    grid-template-columns: 1fr;
  }

  .issue-conclusion-title-row {
    flex-direction: column;
    gap: 6px;
  }

  .issue-conclusion-status {
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .issue-conclusion-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}

:deep(.issue-row-highlight td) {
  background: rgba(239, 246, 255, 0.66);
}

:deep(.issue-row-linked td) {
  background: rgba(219, 234, 254, 0.85);
}

:deep(.issue-row-uncertain td) {
  background: rgba(254, 243, 199, 0.55);
}

@keyframes statusPulse {
  0% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.42);
  }
  70% {
    box-shadow: 0 0 0 12px rgba(37, 99, 235, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
  }
}

@keyframes streamScan {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}
</style>
