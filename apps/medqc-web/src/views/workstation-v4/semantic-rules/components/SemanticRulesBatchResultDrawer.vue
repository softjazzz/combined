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
          <a-button class="drawer-back-button" @click="close">
            <MqIcon name="back" :size="16" />
            {{ props.backLabel || '返回样本验证' }}
          </a-button>
          <div>
            <p class="drawer-eyebrow">批量任务结果</p>
            <h2 class="drawer-title">任务详情</h2>
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
          <!-- 明细导出、诊断包、复核、高级视图属于管理排查操作，收进“更多”，主操作只留导出报告（2026-10-23） -->
          <a-dropdown v-if="batchJobDetail && !confirmedResultsOnly" :trigger="['click']">
            <a-button
              :loading="diagnosticPackageLoading || reviewBatchJobLoading"
              data-testid="batch-result-more"
            >
              更多
            </a-button>
            <template #overlay>
              <a-menu @click="handleMoreMenuClick">
                <template v-if="batchJobDetail?.status === 'completed'">
                  <a-menu-item key="html" data-menu-key="html"> 导出 HTML 明细 </a-menu-item>
                  <a-menu-item key="xlsx" data-menu-key="xlsx"> 导出 Excel 明细 </a-menu-item>
                  <a-menu-item key="csv" data-menu-key="csv"> 导出 CSV 明细 </a-menu-item>
                </template>
                <a-menu-item key="diagnostic" data-menu-key="diagnostic">
                  下载质控诊断包
                </a-menu-item>
                <a-menu-item
                  v-if="batchJobDetail?.status === 'completed' && isLuxian0609BatchJob"
                  key="review"
                  data-menu-key="review"
                >
                  复核本次结果
                </a-menu-item>
                <a-menu-item key="advanced" data-menu-key="advanced">
                  {{ issueViewMode === 'advanced' ? '返回结果视图' : '高级视图（排查用）' }}
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
          <a-button
            v-if="batchJobDetail?.status === 'completed' && !confirmedResultsOnly"
            type="primary"
            :loading="batchJobDetailLoading"
            data-testid="batch-result-export-report"
            @click="handleExportMenuClick({ key: 'html' })"
          >
            <MqIcon name="download" :size="16" />
            导出质控报告
          </a-button>
        </div>
        <button
          type="button"
          class="record-view-close-button drawer-close-button"
          aria-label="关闭任务结果"
          @click="close"
        >
          <RecordViewCloseIcon label="关闭任务结果" />
        </button>
      </div>

      <div class="drawer-body">
        <p v-if="batchJobDetail?.retry_lineage" class="mq-soft" data-testid="retry-lineage">
          第 {{ batchJobDetail.retry_lineage.attempt }} 次重试 · 来源任务 {{ batchJobDetail.retry_lineage.source_job_id }}。
          本次结果独立保存，原任务结果保留。
        </p>
        <BatchTaskFailureSummary :job="batchJobDetail" />
        <BatchResultOverview :model="resultReviewOverviewModel" />

        <div
          v-if="partialFailureItems.length && isLuxian0609BatchJob"
          class="partial-failure-notice mq-soft"
          data-testid="partial-failure-notice"
        >
          <p>
            有 {{ partialFailureSummary.failedCount }} 项质控点本次未能完成判定， 已保留
            {{ partialFailureSummary.completedCount }} 项有效结果。
            {{ failedRuleRetryMessage }}
            <button type="button" @click="showFailureDetail = !showFailureDetail">
              {{ showFailureDetail ? '收起明细' : '查看明细' }}
            </button>
          </p>
          <ul v-if="showFailureDetail">
            <li
              v-for="(failure, index) in partialFailureItems"
              :key="`${failure.record_ref || failure.record_id || index}-${failure.rule_id || index}`"
            >
              <span class="mq-mono">{{ failure.rule_id || '未知规则' }}</span>
              <span>{{ failureRecordLabel(failure) }}</span>
              <span>执行失败，未形成质控结论</span>
            </li>
          </ul>
        </div>
        <section v-else-if="partialFailureItems.length" class="partial-failure-panel">
          <div class="partial-failure-head">
            <div>
              <strong>部分执行失败</strong>
              <p>
                已保留并可查看 {{ partialFailureSummary.completedCount }} 项有效结果；
                {{ partialFailureSummary.failedCount }} 项执行失败未形成临床结论。
              </p>
            </div>
            <span>{{ failedRuleRetryMessage }}</span>
          </div>
          <div class="partial-failure-list">
            <div
              v-for="(failure, index) in partialFailureItems"
              :key="`${failure.record_ref || failure.record_id || index}-${failure.rule_id || index}`"
              class="partial-failure-item"
            >
              <strong>{{ failure.rule_id || '未知规则' }}</strong>
              <span>{{
                failure.record_ref || failure.visit_id || failure.record_id || '未知病历'
              }}</span>
              <em>执行失败，未形成质控结论</em>
            </div>
          </div>
        </section>

        <div
          v-if="batchJobDetail && statusHero && !showResultReviewOverview && !isLuxian0609BatchJob"
          class="status-hero"
          :class="`status-hero--${statusHero.tone}`"
        >
          <div class="status-hero-main">
            <div v-if="statusHero.pulse" class="status-hero-pulse" />
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
              <div v-if="statusHero.description" class="status-hero-desc">
                {{ statusHero.description }}
              </div>
              <div v-if="isRunningBatchJob" class="status-hero-live">
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
              <div v-if="isRunningBatchJob" class="status-hero-flow">
                <div
                  class="status-hero-flow-bar"
                  :style="{ width: `${progressSummary?.percent ?? 0}%` }"
                />
              </div>
            </div>
          </div>
          <div class="status-hero-side">
            <div class="status-hero-percent">{{ progressSummary?.percent ?? 0 }}%</div>
            <div class="status-hero-side-label">
              {{ progressSummary?.stepLabel || '准备中' }}
            </div>
          </div>
        </div>

        <div
          v-if="!confirmedResultsOnly && focusedSummaryCards.length && !isLuxian0609BatchJob"
          class="drawer-summary summary-grid-primary"
        >
          <div v-for="item in focusedSummaryCards" :key="item.key" class="summary-card">
            <div class="summary-label">
              {{ item.label }}
            </div>
            <div class="summary-value">
              {{ item.value }}
            </div>
            <div v-if="item.desc" class="summary-desc">
              {{ item.desc }}
            </div>
          </div>
        </div>

        <div
          v-if="isFocusedRecordMode && !showResultReviewOverview && !isLuxian0609BatchJob"
          class="drawer-card focus-record-card"
        >
          <div class="drawer-section-title">当前仅查看单份病历结果</div>
          <div class="focus-record-meta">
            <span v-if="isLuxian0609BatchJob">
              {{ focusedLuxianRecordLabel }}
            </span>
            <template v-else>
              <span v-if="props.focusRecordLabel">{{ props.focusRecordLabel }}</span>
              <span v-if="props.focusVisitId">visit_id：{{ props.focusVisitId }}</span>
              <span v-if="props.focusRecordId">记录标识：{{ props.focusRecordId }}</span>
            </template>
          </div>
        </div>

        <div v-if="!confirmedResultsOnly && luxianReviewReport" class="drawer-card luxian-review-card">
          <div class="drawer-section-head">
            <div class="drawer-section-title-group">
              <div class="drawer-section-title">结果复核建议</div>
              <span class="summary-mode-badge">
                {{ luxianReviewSummaryText }}
              </span>
            </div>
          </div>
          <div v-if="luxianReviewFindings.length" class="luxian-review-list">
            <article
              v-for="finding in luxianReviewFindings"
              :key="finding.id || `${finding.record_ref}-${finding.rule_id}-${finding.risk_type}`"
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
              <small v-if="finding.record_ref">
                {{ finding.record_ref }}
              </small>
            </article>
          </div>
          <div v-else class="luxian-review-empty">已完成复核，暂无高风险复核建议。</div>
        </div>

        <!-- 多份病历的泸县 0609 任务：客户视图（问题排行 + 按病历查看）；高级视图保留原排查卡片 -->
        <template v-if="showCustomerReview">
          <TopIssueRulesCard
            :rules="customerTopIssueRules"
            :total-records="customerReviewRecords.length"
          />
          <BatchRecordReviewPanel :records="customerReviewRecords" :confirmed-only="confirmedResultsOnly" />
        </template>
        <div
          v-else
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
              <span v-if="isFastScreenResult" class="summary-mode-badge">
                快速初筛结果（摘要版）
              </span>
            </div>
            <div class="drawer-section-actions">
              <a-radio-group v-if="!confirmedResultsOnly" v-model:value="issueViewMode" size="small">
                <a-radio-button value="business"> 业务视图 </a-radio-button>
                <a-radio-button
                  v-if="enableRecordComparison && isFocusedSingleRecordScope"
                  value="compare"
                >
                  病历原文对照
                </a-radio-button>
                <a-radio-button value="advanced"> 高级视图 </a-radio-button>
              </a-radio-group>
              <a-switch v-if="!confirmedResultsOnly" v-model:checked="showAllStatuses" size="small" />
              <span class="drawer-section-meta">
                {{ confirmedResultsOnly ? '确定问题' : showAllStatuses ? '全部状态' : '仅问题项' }}
              </span>
            </div>
          </div>
          <div class="issue-toolbar" :class="{ 'issue-toolbar--single': isSingleRecordIssueMode }">
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
              <a-button size="small" @click="resetIssueFilters"> 重置 </a-button>
            </div>
          </div>
          <div v-if="isMultiRecordIssueMode" class="issue-record-switcher">
            <div class="issue-record-switcher-head">
              <span>先选病历，再看质控点</span>
              <small
                >本次涉及 {{ issueRecordGroups.length }} 份病历，默认按病历分组展示结果。</small
              >
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
                <span v-if="confirmedResultsOnly">确定问题 {{ group.nonCompliant }} 条</span>
                <span v-else>
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
          <div v-if="selectedClusterKey || activeRuleFilterLabel" class="aggregation-active-tip">
            <span v-if="selectedClusterKey"
              >聚合簇：{{ resolveCustomerEvidenceText(selectedClusterKey) }}</span
            >
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
            v-if="
              issueViewMode === 'compare' &&
              enableRecordComparison &&
              isFocusedSingleRecordScope &&
              recordCompareCoordinates.visitId
            "
            class="issue-record-compare"
          >
            <QCRecordCompareWorkbench
              :visit-id="recordCompareCoordinates.visitId"
              :institute-id="recordCompareCoordinates.instituteId"
              :patient-id="recordCompareCoordinates.patientId"
              :issues="recordCompareIssues"
              :active-issue-key="selectedBusinessIssueKey"
              @select-issue="selectRecordCompareIssue"
            />
          </div>
          <div
            v-else-if="
              issueViewMode === 'compare' && enableRecordComparison && isFocusedSingleRecordScope
            "
            class="issue-business-empty-state"
          >
            <a-empty description="当前病历缺少可授权定位的病历坐标" />
          </div>
          <div
            v-else-if="issueViewMode === 'business'"
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
              <template v-for="group in singleIssueNavGroups" :key="`items-${group.key}`">
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
              <section
                v-if="!confirmedResultsOnly && transfusionDocumentationSummary"
                class="transfusion-documentation-summary"
                :class="{
                  'transfusion-documentation-summary--complete':
                    transfusionDocumentationSummary.complete,
                }"
                data-testid="transfusion-documentation-summary"
              >
                <div class="transfusion-documentation-summary-head">
                  <strong>输血相关三项</strong>
                  <span>{{
                    transfusionDocumentationSummary.complete ? '资料齐备' : '需要关注'
                  }}</span>
                </div>
                <p>{{ transfusionDocumentationSummary.summaryText }}</p>
                <div
                  v-if="!transfusionDocumentationSummary.complete"
                  class="transfusion-documentation-summary-statuses"
                >
                  <span v-for="entry in transfusionDocumentationSummary.entries" :key="entry.ruleId"
                    >{{ entry.label }}：{{ entry.statusText }}</span
                  >
                </div>
              </section>
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
                      <span>{{ resolveIssueDisplayRecordRef(selectedBusinessIssueCard) }}</span>
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
                <div v-if="selectedIssuePatientContext" class="issue-patient-context-card">
                  <div class="issue-patient-avatar">
                    {{ selectedIssuePatientContext.initial }}
                  </div>
                  <div class="issue-patient-context-main">
                    <div class="issue-patient-context-kicker">当前病历</div>
                    <div class="issue-patient-context-id">
                      {{ selectedIssuePatientContext.recordId }}
                    </div>
                    <div class="issue-patient-context-meta">
                      <span>
                        <em>姓名</em>
                        {{ selectedIssuePatientContext.patientName }}
                      </span>
                      <span v-if="selectedIssuePatientContext.department">
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
                  <CustomerQcResultDetailCard
                    v-if="
                      isLuxian0609BatchJob && selectedBusinessIssueCard.customer_display?.isEnhanced
                    "
                    :model="selectedBusinessIssueCard.customer_display"
                  />
                  <section v-else class="issue-detail-section issue-detail-section--conclusion">
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
                      <p
                        v-if="isLuxian0609BatchJob && selectedBusinessIssueCard.reason_code"
                        class="issue-detail-reason"
                      >
                        判定依据：{{ selectedBusinessIssueCard.customer_reason_code_text }}
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
                    <section
                      v-if="selectedBusinessIssueCard.customer_suggestion_text"
                      class="issue-detail-section"
                    >
                      <QcRemediationSuggestion
                        :suggestion="selectedBusinessIssueCard.customer_suggestion_text"
                        :status="resolveIssueCanonicalStatus(selectedBusinessIssueCard)"
                        :rule-id="
                          selectedBusinessIssueCard.rule_code || selectedBusinessIssueCard.rule_id
                        "
                        :record-context="recordCompareCoordinates"
                      />
                    </section>
                  </div>
                </div>
                <div
                  v-if="resolveCopyEvidenceCompare(selectedBusinessIssueCard)"
                  class="copy-evidence-compare"
                >
                  <div class="copy-evidence-head">
                    <strong>重复内容对照</strong>
                    <span
                      >用于核对两份病程/查房记录是否只是复制粘贴；重点看本次记录是否有新增病情变化、分析和诊疗计划。</span
                    >
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
                    <div class="copy-evidence-label">重复度指标</div>
                    <blockquote>
                      {{ resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.metric }}
                    </blockquote>
                  </div>
                  <div
                    v-if="resolveCopyEvidenceCompare(selectedBusinessIssueCard)?.differenceGap"
                    class="copy-evidence-column copy-evidence-column--gap"
                  >
                    <div class="copy-evidence-label">缺少差异说明</div>
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
                      <div class="evidence-chain-title">完整说明</div>
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
                      <div class="evidence-chain-block-title">触发事实</div>
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
                      <div class="evidence-chain-block-title">数据依赖</div>
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
                      <div class="evidence-chain-block-title">判断过程</div>
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
                    v-if="!confirmedResultsOnly"
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
              <div v-else-if="businessIssueCards.length" class="issue-conclusion-list">
                <div
                  v-for="group in businessIssueCardGroups"
                  :key="group.key"
                  class="issue-record-result-group"
                >
                  <div v-if="shouldShowIssueRecordGroupHeader" class="issue-record-result-head">
                    <div>
                      <strong>{{ group.label }}</strong>
                      <span>{{ group.meta || '未返回科室/住院号' }}</span>
                    </div>
                    <div class="issue-record-result-stats">
                      <span>结果 {{ group.total }}</span>
                      <span>不合规 {{ group.nonCompliant }}</span>
                      <span v-if="!confirmedResultsOnly">数据不足 {{ group.dataGap }}</span>
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
                            <span>{{ resolveIssueDisplayRecordRef(item) }}</span>
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
                          <div class="issue-glance-label">质控结论</div>
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
                          <div class="issue-glance-label">关键证据</div>
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
                        <div v-if="item.customer_suggestion_text" class="issue-glance-block">
                          <QcRemediationSuggestion
                            :suggestion="item.customer_suggestion_text"
                            :status="resolveIssueCanonicalStatus(item)"
                            :rule-id="item.rule_code || item.rule_id"
                            :record-context="recordCompareCoordinates"
                            dense
                          />
                        </div>
                      </div>
                      <div v-if="resolveCopyEvidenceCompare(item)" class="copy-evidence-compare">
                        <div class="copy-evidence-head">
                          <strong>重复内容对照</strong>
                          <span
                            >用于核对前后记录是否只是复制粘贴，重点看本次记录有没有新增病情变化、分析和诊疗计划。</span
                          >
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
                          <div class="copy-evidence-label">重复度指标</div>
                          <blockquote>{{ resolveCopyEvidenceCompare(item)?.metric }}</blockquote>
                        </div>
                        <div
                          v-if="resolveCopyEvidenceCompare(item)?.differenceGap"
                          class="copy-evidence-column copy-evidence-column--gap"
                        >
                          <div class="copy-evidence-label">缺少差异说明</div>
                          <blockquote>
                            {{ resolveCopyEvidenceCompare(item)?.differenceGap }}
                          </blockquote>
                        </div>
                      </div>
                      <div v-if="hasEvidenceChain(item)" class="evidence-chain-strip">
                        <span>
                          状态口径：{{
                            resolveEvidenceStatusText(resolveIssueCanonicalStatus(item))
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
                            <div class="evidence-chain-title">证据链</div>
                            <div class="evidence-chain-subtitle">
                              按触发事实、依赖数据、来源证据和判断口径展示
                            </div>
                          </div>
                          <a-tag class="evidence-chain-tag">
                            {{ resolveExecutorTypeText(item.executor_type) }}
                          </a-tag>
                        </div>
                        <div class="evidence-chain-grid">
                          <div v-if="resolveTriggerFacts(item).length" class="evidence-chain-block">
                            <div class="evidence-chain-block-title">触发事实</div>
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
                            <div class="evidence-chain-block-title">数据依赖</div>
                            <div
                              v-for="row in resolveDependencyRows(item)"
                              :key="row.key"
                              class="evidence-chain-line"
                            >
                              <span>{{ row.label }}</span>
                              <strong>{{ row.value }}</strong>
                            </div>
                          </div>
                          <div v-if="resolveDecisionRows(item).length" class="evidence-chain-block">
                            <div class="evidence-chain-block-title">判断过程</div>
                            <div
                              v-for="row in resolveDecisionRows(item)"
                              :key="row.key"
                              class="evidence-chain-line"
                            >
                              <span>{{ row.label }}</span>
                              <strong>{{ row.value }}</strong>
                            </div>
                          </div>
                          <div v-if="resolveReviewRows(item).length" class="evidence-chain-block">
                            <div class="evidence-chain-block-title">质控确认</div>
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
                          <div class="evidence-chain-block-title">关键证据</div>
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
                      <div v-if="isIssueExpanded(item)" class="issue-conclusion-summary">
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
                        <div v-if="item.rewrite_example" class="issue-conclusion-row">
                          <span class="issue-conclusion-label">改写示例</span>
                          <div class="issue-conclusion-structured">
                            {{ item.rewrite_example }}
                          </div>
                        </div>
                      </div>
                      <div class="issue-conclusion-actions">
                        <a-button type="link" size="small" @click="toggleIssueExpanded(item)">
                          {{ isIssueExpanded(item) ? '收起完整说明' : '展开完整说明' }}
                        </a-button>
                        <a-button
                          v-if="!confirmedResultsOnly"
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
              <div v-else-if="isWaitingFirstResult" class="stream-waiting-card">
                <div class="stream-waiting-scan" />
                <div class="stream-waiting-lines">
                  <span />
                  <span />
                  <span />
                </div>
                <div class="stream-waiting-text">正在等待首份病历结果</div>
                <div class="stream-waiting-subtext">
                  {{ waitingFirstResultDescription }}
                </div>
              </div>
              <a-empty v-else :description="emptyIssueText" />
              <section
                v-if="!confirmedResultsOnly && !showAllStatuses && noIssueEvidenceItems.length"
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
                  <a-button type="link" size="small" @click="showAllStatuses = true">
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
            :scroll="{ x: 1850 }"
            :pagination="issuePagination"
            :row-class-name="resolveIssueRowClassName"
            :locale="{ emptyText: emptyIssueText }"
            @change="handleIssueTableChange"
          >
            <template #bodyCell="{ column, record }">
              <div v-if="column.key === 'actions'" class="issue-table-actions">
                <a-button
                  v-if="canShowResultTrace"
                  type="link"
                  size="small"
                  data-testid="advanced-issue-trace-btn"
                  @click="openIssueTrace(record as SichuanBatchIssueItem)"
                >
                  诊断追踪
                </a-button>
                <a-button
                  v-if="!confirmedResultsOnly"
                  type="link"
                  size="small"
                  data-testid="advanced-issue-deep-review-btn"
                  @click="openIssueDeepReview(record as SichuanBatchIssueItem)"
                >
                  深度复核
                </a-button>
              </div>
            </template>
          </a-table>
        </div>

        <a-collapse
          v-if="issueViewMode === 'advanced'"
          v-model:active-key="advancedSectionKeys"
          ghost
          class="drawer-advanced-collapse"
        >
          <a-collapse-panel key="execution" header="技术详情：执行统计">
            <div v-if="progressSummary" class="drawer-card drawer-card--nested">
              <div class="drawer-section-head">
                <div class="drawer-section-title">任务进度</div>
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
                <span
                  >已处理 {{ progressSummary.processedRecords }} /
                  {{ progressSummary.totalRecords }} 份病历</span
                >
                <span>规则 {{ progressSummary.ruleIndex }} / {{ progressSummary.ruleCount }}</span>
              </div>
            </div>

            <div v-if="advancedSummaryCards.length" class="drawer-summary summary-grid-secondary">
              <div v-for="item in advancedSummaryCards" :key="item.key" class="summary-card">
                <div class="summary-label">
                  {{ item.label }}
                </div>
                <div class="summary-value">
                  {{ item.value }}
                </div>
                <div v-if="item.desc" class="summary-desc">
                  {{ item.desc }}
                </div>
              </div>
            </div>
          </a-collapse-panel>

          <a-collapse-panel v-if="resultAggregation" key="aggregation" header="技术详情：结果聚合">
            <div class="drawer-card drawer-card--nested">
              <div class="drawer-section-head">
                <div class="drawer-section-title">结果聚合</div>
                <div class="drawer-section-meta">
                  簇数 {{ resultAggregation.cluster_count || 0 }} · 重复命中
                  {{ resultAggregation.duplicate_hits || 0 }}
                </div>
              </div>
              <div v-if="aggregationBreakdownSections.length" class="aggregation-breakdown-grid">
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
                  <div v-if="section.items.length" class="aggregation-breakdown-items">
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
                  <div v-else class="aggregation-breakdown-empty">暂无分解数据</div>
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
                    <a-tag class="aggregation-count-tag"> {{ cluster.records || 0 }} 次 </a-tag>
                  </div>
                  <div v-if="cluster.sample_evidence" class="aggregation-evidence">
                    {{ resolveCustomerEvidenceText(cluster.sample_evidence) }}
                  </div>
                  <div class="aggregation-meta">
                    病历 {{ cluster.records || 0 }} 条 · 规则 {{ cluster.rules?.length || 0 }} 条
                  </div>
                </div>
              </div>
              <div v-if="selectedClusterKey" class="aggregation-active-tip">
                已按聚合簇过滤：{{ resolveCustomerEvidenceText(selectedClusterKey) }}
                <a-button type="link" size="small" @click.stop="clearClusterFilter">
                  清除
                </a-button>
              </div>
            </div>
          </a-collapse-panel>

          <a-collapse-panel key="rules" header="技术详情：规则结果">
            <div class="drawer-card drawer-card--nested">
              <div class="drawer-section-head">
                <div class="drawer-section-title">规则结果概览</div>
                <div v-if="activeRuleFilterLabel" class="drawer-section-meta">
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
        </a-collapse>

        <!-- 调试快照属于排查信息：泸县 0609 任务只在高级视图出现 -->
        <a-collapse
          v-if="canLoadDebugSnapshot && (issueViewMode === 'advanced' || !isLuxian0609BatchJob)"
          ghost
          class="drawer-advanced-collapse"
        >
          <a-collapse-panel key="debug" header="技术详情：调试快照">
            <div v-if="!batchJobDebugSnapshot" class="drawer-card drawer-card--nested">
              <a-spin :spinning="batchJobDebugLoading">
                <a-empty
                  :description="batchJobDebugLoading ? '正在加载调试快照…' : '调试快照暂未加载'"
                >
                  <a-button
                    v-if="!batchJobDebugLoading"
                    size="small"
                    @click="handleDebugRuleChange(undefined)"
                  >
                    重新加载
                  </a-button>
                </a-empty>
              </a-spin>
            </div>
            <div v-else class="drawer-card drawer-card--nested">
              <div class="drawer-section-head">
                <div class="drawer-section-title">执行调试快照</div>
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
              <div v-if="debugProgressEntries.length" class="debug-pill-block">
                <div class="debug-pill-title">current_rule.progress</div>
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
              <div v-if="debugDetailEntries.length" class="debug-pill-block">
                <div class="debug-pill-title">current_rule.debug</div>
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
            <span>{{ resolveIssueDisplayRecordRef(selectedDeepReviewIssue) }}</span>
            <span>{{
              selectedDeepReviewIssue.target_document_type ||
              selectedDeepReviewIssue.document_type ||
              '未知文书域'
            }}</span>
            <span>{{ selectedDeepReviewIssue.rule_family || 'general' }}</span>
            <span>{{ selectedDeepReviewIssue.defect_level || '未分级' }}</span>
            <span v-if="selectedDeepReviewIssue.refined">单条精审</span>
          </div>
          <div v-if="hasEvidenceChain(selectedDeepReviewIssue)" class="deep-review-chain">
            <div class="evidence-chain-panel-head">
              <div>
                <div class="evidence-chain-title">证据链</div>
                <div class="evidence-chain-subtitle">触发事实、依赖数据、来源证据和判断阈值</div>
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
                <div class="evidence-chain-block-title">触发事实</div>
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
                <div class="evidence-chain-block-title">数据依赖</div>
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
                <div class="evidence-chain-block-title">判断过程</div>
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
                <div class="evidence-chain-block-title">执行信息</div>
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
              <div class="evidence-chain-block-title">关键证据</div>
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
          <a-alert v-if="deepReviewError" type="warning" show-icon :message="deepReviewError" />
          <a-spin :spinning="deepReviewLoading">
            <div class="deep-review-section">
              <div class="deep-review-label">复核结论</div>
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
                  <ol v-if="section.points.length" class="issue-conclusion-points">
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
              <div class="deep-review-label">复核证据</div>
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
                  <ol v-if="section.points.length" class="issue-conclusion-points">
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
              <div class="deep-review-label">复核建议</div>
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
                  <ol v-if="section.points.length" class="issue-conclusion-points">
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
    <BatchResultTraceModal
      :open="resultTraceModalOpen"
      :loading="resultTraceLoading"
      :error="resultTraceError"
      :sections="resultTraceSections"
      @close="closeIssueTrace"
    />
  </a-drawer>
</template>

<script setup lang="ts">
import BatchTaskFailureSummary from './BatchTaskFailureSummary.vue'
import { ref } from 'vue'
import type { SichuanBatchIssueItem } from '@/views/workstation-v4/semantic-rules/types'
import MqIcon from '@/components/icons/MqIcon.vue'
import RecordViewCloseIcon from '../../components/RecordViewCloseIcon.vue'
import BatchRecordReviewPanel from '@/views/workstation-v4/semantic-rules/components/BatchRecordReviewPanel.vue'
import TopIssueRulesCard from '@/views/workstation-v4/semantic-rules/components/TopIssueRulesCard.vue'
import QcRemediationSuggestion from '@/views/workstation-v4/components/qc/QcRemediationSuggestion.vue'
import {
  useSemanticRulesBatchResultDrawerController,
  type SemanticRulesBatchResultDrawerProps,
} from '@/views/workstation-v4/semantic-rules/useSemanticRulesBatchResultDrawerController'

const props = defineProps<SemanticRulesBatchResultDrawerProps & { backLabel?: string }>()

const showFailureDetail = ref(false)

const {
  confirmedResultsOnly,
  customerReviewRecords,
  customerTopIssueRules,
  failureRecordLabel,
  handleMoreMenuClick,
  showCustomerReview,
  activeRuleFilterLabel,
  advancedSectionKeys,
  advancedSummaryCards,
  aggregationBreakdownSections,
  ALL_RECORDS_KEY,
  batchJobDebugSnapshot,
  BatchResultOverview,
  BatchResultTraceModal,
  businessIssueCardGroups,
  businessIssueCards,
  canLoadDebugSnapshot,
  canCancelBatchJob,
  cancelBatchJobLoading,
  canShowResultTrace,
  clearClusterFilter,
  closeDeepReviewModal,
  closeIssueTrace,
  confirmCancelBatchJob,
  currentDebugRule,
  currentStreamRecordLabel,
  CustomerQcResultDetailCard,
  debugDetailEntries,
  debugProgressEntries,
  debugRuleOptions,
  diagnosticPackageLoading,
  deepReviewError,
  deepReviewLoading,
  deepReviewModalOpen,
  displayIssueItems,
  displayRuleResults,
  emptyIssueText,
  focusedLuxianRecordLabel,
  focusedSummaryCards,
  handleDebugRuleChange,
  downloadBatchJobDiagnosticPackage,
  handleExportMenuClick,
  handleIssueTableChange,
  handleReviewBatchJobResult,
  hasEvidenceChain,
  hasStructuredText,
  incrementalResultTip,
  isFastScreenResult,
  isFocusedRecordMode,
  isFocusedSingleRecordScope,
  isIssueExpanded,
  isLuxian0609BatchJob,
  isMultiRecordIssueMode,
  isRunningBatchJob,
  isSingleRecordIssueMode,
  issueColumns,
  issueDefectLevelOptions,
  issueDocumentTypeOptions,
  issueExecutionDomainOptions,
  issueFilter,
  issueFocusSummary,
  issuePagination,
  issueRecordGroups,
  issueRecordTotalCount,
  issueSectionTitle,
  issueViewMode,
  isWaitingFirstResult,
  liveElapsedLabel,
  luxianReviewFindings,
  luxianReviewReport,
  luxianReviewSummaryText,
  mapStructuredStatusLabel,
  noIssueEvidenceItems,
  noIssueEvidenceTotalCount,
  openIssueDeepReview,
  openIssueTrace,
  partialFailureItems,
  partialFailureSummary,
  failedRuleRetryMessage,
  progressSummary,
  QCRecordCompareWorkbench,
  recordCompareCoordinates,
  recordCompareIssues,
  resetIssueFilters,
  resolveAuditRows,
  resolveCopyEvidenceCompare,
  resolveCustomerEvidenceText,
  resolveDecisionRows,
  resolveDeepReviewText,
  resolveDependencyRows,
  resolveDisplayStatusText,
  resolveEvidenceChainItems,
  resolveEvidenceStatusText,
  resolveExecutorTypeText,
  resolveIssueCanonicalStatus,
  resolveIssueDisplayRecordRef,
  resolveIssueResultKindClass,
  resolveIssueResultKindText,
  resolveIssueReviewNavClass,
  resolveIssueRowClassName,
  resolveIssueSeverityText,
  resolveIssueStableKey,
  resolveMissingSources,
  resolveReviewRows,
  resolveStatusText,
  resolveStructuredText,
  resolveTriggerFacts,
  resultAggregation,
  resultReviewOverviewModel,
  resultTraceError,
  resultTraceLoading,
  resultTraceModalOpen,
  resultTraceSections,
  ruleColumns,
  sanitizeCustomerVisibleText,
  selectBusinessIssue,
  selectedBusinessIssueCard,
  selectedBusinessIssueKey,
  selectedClusterKey,
  selectedDebugRuleJobId,
  selectedDeepReviewIssue,
  selectedIssuePatientContext,
  selectedIssueRecordKey,
  selectRecordCompareIssue,
  shouldShowIssueRecordGroupHeader,
  showAllStatuses,
  showResultReviewOverview,
  singleIssueNavGroups,
  statusHero,
  streamUpdatedAtText,
  toggleClusterFilter,
  toggleIssueExpanded,
  topAggregationClusters,
  transfusionDocumentationSummary,
  truncateText,
  waitingFirstResultDescription,
} = useSemanticRulesBatchResultDrawerController(props)
</script>

<style scoped src="./SemanticRulesBatchResultDrawer.css"></style>
