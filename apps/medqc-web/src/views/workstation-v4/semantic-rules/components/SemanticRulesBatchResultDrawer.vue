<template>
  <a-drawer
    :open="open"
    placement="right"
    :width="1100"
    :closable="false"
    :body-style="{ padding: 0 }"
    @close="close"
  >
    <div class="drawer-shell">
      <div class="drawer-head">
        <div>
          <p class="drawer-eyebrow">
            批量任务结果
          </p>
          <h2 class="drawer-title">
            任务详情
          </h2>
        </div>
        <div class="drawer-actions">
          <a-button
            v-if="batchJobDetail?.status === 'completed'"
            :loading="batchJobDetailLoading"
            @click="exportBatchJobReport('xlsx')"
          >
            导出报告
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
          v-if="batchJobDetail && statusHero"
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

        <div class="drawer-summary summary-grid-primary">
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
          v-if="isFocusedRecordMode"
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

        <div class="drawer-card">
          <div class="drawer-section-head">
            <div class="drawer-section-title-group">
              <div class="drawer-section-title">
                问题/待复核明细
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
          <div class="issue-toolbar">
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
            v-if="selectedClusterKey || activeRuleFilterLabel"
            class="aggregation-active-tip"
          >
            <span v-if="selectedClusterKey">聚合簇：{{ selectedClusterKey }}</span>
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
            v-if="businessIssueCards.length"
            class="issue-conclusion-list"
          >
            <div
              v-for="item in businessIssueCards"
              :key="`conclusion-${resolveIssueStableKey(item)}`"
              class="issue-conclusion-card"
            >
              <div class="issue-conclusion-head">
                <div class="issue-conclusion-head-main">
                  <span class="issue-conclusion-title">
                    {{ item.rule_code || item.rule_id || '未知规则' }} ·
                    {{ item.rule_name || '未知质控点' }}
                  </span>
                  <div class="issue-conclusion-meta">
                    <span>{{ item.record_id || '-' }}</span>
                    <span>{{
                      item.target_document_type || item.document_type || '未知文书域'
                    }}</span>
                    <span>{{ item.rule_family || 'general' }}</span>
                    <span>{{ item.defect_level || '未分级' }}</span>
                    <span v-if="item.refined">单条精审</span>
                  </div>
                </div>
                <a-tag class="aggregation-count-tag">
                  {{ resolveStatusText(item.status) }}
                </a-tag>
              </div>
              <div class="issue-conclusion-summary">
                <div class="issue-conclusion-row">
                  <span class="issue-conclusion-label">结论</span>
                  <div
                    v-if="isIssueExpanded(item)"
                    class="issue-conclusion-structured"
                  >
                    <template v-if="resolveStructuredText(item.findings).summary">
                      <p
                        v-for="(paragraph, index) in resolveStructuredText(item.findings).summary"
                        :key="`finding-summary-${resolveIssueStableKey(item)}-${index}`"
                        class="issue-conclusion-summary-text"
                      >
                        {{ paragraph }}
                      </p>
                    </template>
                    <div
                      v-for="(section, sectionIndex) in resolveStructuredText(item.findings)
                        .sections"
                      :key="`finding-section-${resolveIssueStableKey(item)}-${sectionIndex}`"
                      class="issue-conclusion-section"
                    >
                      <div class="issue-conclusion-section-title">
                        {{ section.title }}
                      </div>
                      <p
                        v-for="(paragraph, paragraphIndex) in section.paragraphs"
                        :key="`finding-section-paragraph-${resolveIssueStableKey(item)}-${sectionIndex}-${paragraphIndex}`"
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
                          :key="`finding-${resolveIssueStableKey(item)}-${sectionIndex}-${index}`"
                        >
                          {{ point }}
                        </li>
                      </ol>
                    </div>
                    <ol
                      v-if="resolveStructuredText(item.findings).points.length"
                      class="issue-conclusion-points"
                    >
                      <li
                        v-for="(point, index) in resolveStructuredText(item.findings).points"
                        :key="`finding-point-${resolveIssueStableKey(item)}-${index}`"
                      >
                        {{ point }}
                      </li>
                    </ol>
                    <span
                      v-if="
                        !resolveStructuredText(item.findings).summary.length &&
                          !resolveStructuredText(item.findings).sections.length &&
                          !resolveStructuredText(item.findings).points.length
                      "
                    >
                      无
                    </span>
                  </div>
                  <span v-else>
                    {{ truncateText(item.findings, 88) }}
                  </span>
                </div>
                <div class="issue-conclusion-row">
                  <span class="issue-conclusion-label">证据</span>
                  <div
                    v-if="isIssueExpanded(item)"
                    class="issue-conclusion-structured"
                  >
                    <template v-if="resolveStructuredText(item.evidence).summary">
                      <p
                        v-for="(paragraph, index) in resolveStructuredText(item.evidence).summary"
                        :key="`evidence-summary-${resolveIssueStableKey(item)}-${index}`"
                        class="issue-conclusion-summary-text"
                      >
                        {{ paragraph }}
                      </p>
                    </template>
                    <div
                      v-for="(section, sectionIndex) in resolveStructuredText(item.evidence)
                        .sections"
                      :key="`evidence-section-${resolveIssueStableKey(item)}-${sectionIndex}`"
                      class="issue-conclusion-section"
                    >
                      <div class="issue-conclusion-section-title">
                        {{ section.title }}
                      </div>
                      <p
                        v-for="(paragraph, paragraphIndex) in section.paragraphs"
                        :key="`evidence-section-paragraph-${resolveIssueStableKey(item)}-${sectionIndex}-${paragraphIndex}`"
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
                          :key="`evidence-${resolveIssueStableKey(item)}-${sectionIndex}-${index}`"
                        >
                          {{ point }}
                        </li>
                      </ol>
                    </div>
                    <ol
                      v-if="resolveStructuredText(item.evidence).points.length"
                      class="issue-conclusion-points"
                    >
                      <li
                        v-for="(point, index) in resolveStructuredText(item.evidence).points"
                        :key="`evidence-point-${resolveIssueStableKey(item)}-${index}`"
                      >
                        {{ point }}
                      </li>
                    </ol>
                    <span
                      v-if="
                        !resolveStructuredText(item.evidence).summary.length &&
                          !resolveStructuredText(item.evidence).sections.length &&
                          !resolveStructuredText(item.evidence).points.length
                      "
                    >
                      无
                    </span>
                  </div>
                  <span v-else>
                    {{ truncateText(item.evidence, 96) }}
                  </span>
                </div>
                <div class="issue-conclusion-row">
                  <span class="issue-conclusion-label">建议</span>
                  <div
                    v-if="isIssueExpanded(item)"
                    class="issue-conclusion-structured"
                  >
                    <template v-if="resolveStructuredText(item.suggestion).summary">
                      <p
                        v-for="(paragraph, index) in resolveStructuredText(item.suggestion).summary"
                        :key="`suggestion-summary-${resolveIssueStableKey(item)}-${index}`"
                        class="issue-conclusion-summary-text"
                      >
                        {{ paragraph }}
                      </p>
                    </template>
                    <div
                      v-for="(section, sectionIndex) in resolveStructuredText(item.suggestion)
                        .sections"
                      :key="`suggestion-section-${resolveIssueStableKey(item)}-${sectionIndex}`"
                      class="issue-conclusion-section"
                    >
                      <div class="issue-conclusion-section-title">
                        {{ section.title }}
                      </div>
                      <p
                        v-for="(paragraph, paragraphIndex) in section.paragraphs"
                        :key="`suggestion-section-paragraph-${resolveIssueStableKey(item)}-${sectionIndex}-${paragraphIndex}`"
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
                          :key="`suggestion-${resolveIssueStableKey(item)}-${sectionIndex}-${index}`"
                        >
                          {{ point }}
                        </li>
                      </ol>
                    </div>
                    <ol
                      v-if="resolveStructuredText(item.suggestion).points.length"
                      class="issue-conclusion-points"
                    >
                      <li
                        v-for="(point, index) in resolveStructuredText(item.suggestion).points"
                        :key="`suggestion-point-${resolveIssueStableKey(item)}-${index}`"
                      >
                        {{ point }}
                      </li>
                    </ol>
                    <span
                      v-if="
                        !resolveStructuredText(item.suggestion).summary.length &&
                          !resolveStructuredText(item.suggestion).sections.length &&
                          !resolveStructuredText(item.suggestion).points.length
                      "
                    >
                      无
                    </span>
                  </div>
                  <span v-else>
                    {{ truncateText(item.suggestion, 72) }}
                  </span>
                </div>
                <div
                  v-if="item.rewrite_example"
                  class="issue-conclusion-row"
                >
                  <span class="issue-conclusion-label">改写示例</span>
                  <div
                    v-if="isIssueExpanded(item)"
                    class="issue-conclusion-structured"
                  >
                    <template v-if="resolveStructuredText(item.rewrite_example).summary">
                      <p
                        v-for="(paragraph, index) in resolveStructuredText(item.rewrite_example)
                          .summary"
                        :key="`rewrite-summary-${resolveIssueStableKey(item)}-${index}`"
                        class="issue-conclusion-summary-text"
                      >
                        {{ paragraph }}
                      </p>
                    </template>
                    <div
                      v-for="(section, sectionIndex) in resolveStructuredText(item.rewrite_example)
                        .sections"
                      :key="`rewrite-section-${resolveIssueStableKey(item)}-${sectionIndex}`"
                      class="issue-conclusion-section"
                    >
                      <div class="issue-conclusion-section-title">
                        {{ section.title }}
                      </div>
                      <p
                        v-for="(paragraph, paragraphIndex) in section.paragraphs"
                        :key="`rewrite-section-paragraph-${resolveIssueStableKey(item)}-${sectionIndex}-${paragraphIndex}`"
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
                          :key="`rewrite-${resolveIssueStableKey(item)}-${sectionIndex}-${index}`"
                        >
                          {{ point }}
                        </li>
                      </ol>
                    </div>
                    <ol
                      v-if="resolveStructuredText(item.rewrite_example).points.length"
                      class="issue-conclusion-points"
                    >
                      <li
                        v-for="(point, index) in resolveStructuredText(item.rewrite_example).points"
                        :key="`rewrite-point-${resolveIssueStableKey(item)}-${index}`"
                      >
                        {{ point }}
                      </li>
                    </ol>
                  </div>
                  <span v-else>
                    {{ truncateText(item.rewrite_example, 96) }}
                  </span>
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
              </div>
            </div>
          </div>
          <a-empty
            v-else-if="issueViewMode === 'business'"
            description="暂无问题/待复核明细"
          />
          <a-pagination
            v-if="
              issueViewMode === 'business' && displayIssueItems.length > issuePagination.pageSize
            "
            v-model:current="issuePagination.current"
            :page-size="issuePagination.pageSize"
            :total="displayIssueItems.length"
            size="small"
            class="issue-pagination"
            :show-size-changer="false"
          />
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
            :locale="{ emptyText: '暂无问题/待复核明细' }"
            @change="handleIssueTableChange"
          />
        </div>

        <a-collapse
          v-model:active-key="advancedSectionKeys"
          ghost
          class="drawer-advanced-collapse"
        >
          <a-collapse-panel
            key="execution"
            header="执行详情与统计"
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
            header="结果聚合与命中分布"
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
                    <span class="aggregation-item-title">{{ cluster.cluster_key }}</span>
                    <a-tag class="aggregation-count-tag">
                      {{ cluster.records || 0 }} 次
                    </a-tag>
                  </div>
                  <div
                    v-if="cluster.sample_evidence"
                    class="aggregation-evidence"
                  >
                    {{ cluster.sample_evidence }}
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
                已按聚合簇过滤：{{ selectedClusterKey }}
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
            header="规则结果概览"
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
            header="执行调试快照"
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
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, h, nextTick, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import type {
  SichuanBatchIssueItem,
  SichuanBatchJobDebugSnapshot,
  SichuanBatchJob,
  SichuanBatchResultAggregation,
} from '@/views/workstation-v4/semantic-rules/types'
import { evaluateSichuanRuleForVisit } from '@/services/sichuan-rule-workspace-service'
import type { StructuredQCFilterState, StructuredQCIssue } from '@/views/workstation-v4/types'
import {
  createDefaultStructuredQCFilter,
  filterStructuredQCIssues,
  mapBatchJobToStructuredQC,
} from '@/views/workstation-v4/utils/structuredQc'

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
  exportBatchJobReport: (format?: 'xlsx' | 'csv') => void
  getBatchJobStatusTagClass: (status?: string) => string
  getBatchJobStatusText: (status?: string) => string
  formatDateTime: (value?: string | Date | null) => string
  focusVisitId?: string
  focusRecordId?: string
  focusRecordLabel?: string
}>()

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

const issueViewMode = ref<'business' | 'advanced'>('business')
const showAllStatuses = ref(false)
const issueFilter = ref<StructuredQCFilterState>(createDefaultStructuredQCFilter())
const advancedSectionKeys = ref<string[]>([])
const normalizedFocusVisitId = computed(() => String(props.focusVisitId || '').trim())
const normalizedFocusRecordId = computed(() => String(props.focusRecordId || '').trim())
const isFocusedRecordMode = computed(
  () => !!(normalizedFocusVisitId.value || normalizedFocusRecordId.value),
)

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
        h('span', { title: text || '' }, truncateText(text, 80)),
    },
    {
      title: '证据摘要',
      dataIndex: 'evidence',
      key: 'evidence',
      width: 280,
      customRender: ({ text }: { text?: string }) =>
        h('span', { title: text || '' }, truncateText(text, 72)),
    },
    {
      title: '整改建议',
      dataIndex: 'suggestion',
      key: 'suggestion',
      width: 260,
      customRender: ({ text }: { text?: string }) =>
        h('span', { title: text || '' }, truncateText(text, 68)),
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
      { title: 'Prompt版本', dataIndex: 'prompt_version', key: 'prompt_version', width: 120 },
      { title: '模型版本', dataIndex: 'model_version', key: 'model_version', width: 120 },
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

const batchJobDebugSnapshot = computed(() => props.batchJobDebugSnapshot || null)

const structuredResult = computed(() =>
  mapBatchJobToStructuredQC(props.batchJobDetail, batchJobDebugSnapshot.value),
)

const scopedStructuredIssues = computed<StructuredQCIssue[]>(() => {
  const issues = structuredResult.value.issues || []
  if (!isFocusedRecordMode.value) return issues
  return issues.filter((item) => matchesFocusedRecord(item))
})

const structuredIssues = computed<StructuredQCIssue[]>(() => {
  const baseFilter: StructuredQCFilterState = {
    ...issueFilter.value,
    statusList: showAllStatuses.value ? [] : ['non_compliant', 'uncertain'],
  }
  let list = filterStructuredQCIssues(scopedStructuredIssues.value, baseFilter).filter(
    (item) => !item.internalOnly,
  )
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

const issueItems = computed<SichuanBatchIssueItem[]>(() => {
  return structuredIssues.value.map((item) => {
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
      llm_fallback: item.metadata.llmFallback === null ? undefined : item.metadata.llmFallback,
      refined: item.metadata.refined === null ? undefined : item.metadata.refined,
      refine_reason: item.metadata.refineReason,
      screening_status: item.metadata.screeningStatus,
      final_decision_source: item.metadata.finalDecisionSource,
    }
  })
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

const displayIssueItems = computed<SichuanBatchIssueItem[]>(() => {
  const items = issueItems.value.filter((item) => {
    if (!selectedDebugRuleJobId.value) return true
    const itemRuleJobId = String(item.rule_job_id || '').trim()
    return itemRuleJobId === selectedDebugRuleJobId.value
  })
  const cluster = selectedCluster.value
  if (!cluster) return items
  return items.filter((item) => matchIssueItemWithCluster(item, cluster))
})

const businessIssueCards = computed(() => {
  const startIndex = (issuePagination.current - 1) * issuePagination.pageSize
  return displayIssueItems.value.slice(startIndex, startIndex + issuePagination.pageSize)
})

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

function isConfirmedDefectItem(item: SichuanBatchIssueItem): boolean {
  if (isPostprocessedFormalResult.value) {
    return item.can_show_as_defect === true || item.display_status === 'confirmed_defect'
  }
  return item.status === 'non_compliant'
}

function isNeedsReviewItem(item: SichuanBatchIssueItem): boolean {
  if (isPostprocessedFormalResult.value) {
    return item.display_status === 'needs_review'
  }
  return item.status === 'uncertain'
}

function isDataQualityGapItem(item: SichuanBatchIssueItem): boolean {
  return isPostprocessedFormalResult.value && item.display_status === 'data_quality_gap'
}

const ruleLevelSummary = computed(() => {
  const totalRules = Math.max(
    0,
    Number(props.batchJobDetail?.summary?.rule_count ?? props.batchJobDetail?.rule_count ?? 0) ||
      resolvedRuleResults.value.length,
  )
  const issueItemsList = issueItems.value
  const nonCompliantCount = issueItemsList.filter((item) => isConfirmedDefectItem(item)).length
  const uncertainCount = issueItemsList.filter((item) => isNeedsReviewItem(item)).length
  const dataQualityGapCount = issueItemsList.filter((item) => isDataQualityGapItem(item)).length
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
    props.batchJobDetail?.summary?.total_processing_time ??
      props.batchJobDetail?.total_processing_time ??
      0,
  )
  return {
    totalRules,
    nonCompliantCount,
    uncertainCount,
    dataQualityGapCount,
    focusCount,
    docIssueCount,
    docUncertainCount,
    processingTimeSeconds,
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
    const focusCount = issueRecords + uncertainRecords
    return {
      tone: 'completed',
      title: focusCount > 0 ? '任务已完成，已产出可处理问题' : '任务已完成，本次未发现问题',
      description:
        focusCount > 0
          ? '请优先查看下方“问题/待复核明细”，直接判断需要复核或整改的质控点。'
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
  const totalRecords = Number(summary?.total_records ?? props.batchJobDetail?.total_records ?? 0)
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
  const focusCount = ruleLevelSummary.value.focusCount
  const processingTimeSeconds = ruleLevelSummary.value.processingTimeSeconds
  return [
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
    { key: 'uncertain', label: '待复核规则', value: uncertainRecords, desc: '' },
    ...(isPostprocessedFormalResult.value
      ? [{ key: 'data-quality-gap', label: '数据缺口', value: dataQualityGapRecords, desc: '' }]
      : []),
    { key: 'focus', label: '重点结果', value: focusCount, desc: '' },
    {
      key: 'duration',
      label: '总耗时',
      value: processingTimeSeconds > 0 ? formatProcessingTime(processingTimeSeconds) : '-',
      desc: '',
    },
    { key: 'success', label: '执行成功', value: successCount, desc: '' },
    {
      key: 'issue-records',
      label: '涉及问题病历',
      value: ruleLevelSummary.value.docIssueCount,
      desc: '病历级去重统计',
    },
    {
      key: 'uncertain-records',
      label: '涉及待复核病历',
      value: ruleLevelSummary.value.docUncertainCount,
      desc: '病历级去重统计',
    },
  ]
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
        label: '待复核规则',
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
          ]
        : []),
      {
        key: 'duration',
        label: '总耗时',
        value:
          ruleLevelSummary.value.processingTimeSeconds > 0
            ? formatProcessingTime(ruleLevelSummary.value.processingTimeSeconds)
            : '-',
        desc: '当前仍展示任务总耗时',
      },
    ]
  }
  return primarySummaryCards.value.filter((item) =>
    ['total', 'issues', 'uncertain', 'data-quality-gap', 'duration'].includes(item.key),
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
    { key: 'llm', label: 'LLM执行', value: executionSummary.value.llmCount, desc: '' },
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

const advancedSummaryCards = computed(() => {
  const cards = [
    ...primarySummaryCards.value.filter(
      (item) => !['total', 'issues', 'uncertain', 'failed-records'].includes(item.key),
    ),
    ...executionSummaryCards.value,
    {
      key: 'rule-results',
      label: '规则结果条数',
      value: resolvedRuleResults.value.length,
      desc: '',
    },
    {
      key: 'issue-items',
      label: '问题/待复核明细',
      value: issueItems.value.length,
      desc: '',
    },
  ]
  return cards.filter((item) => item.value !== undefined && item.value !== null)
})

const issueFocusSummary = computed(() => {
  const total = issueItems.value.length
  if (!total) {
    return showAllStatuses.value ? '当前没有可展示的规则结果。' : '当前没有需要复核或整改的问题项。'
  }
  const nonCompliantCount = issueItems.value.filter((item) => isConfirmedDefectItem(item)).length
  const uncertainCount = issueItems.value.filter((item) => isNeedsReviewItem(item)).length
  const dataQualityGapCount = issueItems.value.filter((item) => isDataQualityGapItem(item)).length
  if (isPostprocessedFormalResult.value) {
    return `当前为正式质控后处理准入结果，共 ${total} 条重点结果，其中确认缺陷 ${nonCompliantCount} 条，待复核 ${uncertainCount} 条，数据缺口 ${dataQualityGapCount} 条。原始 LLM 不合规不会直接计入确认缺陷。`
  }
  if (issueViewMode.value === 'business') {
    if (isFastScreenResult.value) {
      return `当前为快速初筛结果（摘要版），共 ${total} 条重点结果，其中不合规 ${nonCompliantCount} 条，待复核 ${uncertainCount} 条。可先展开完整说明，再按需进入深度复核查看全文文书。`
    }
    return `当前共 ${total} 条重点结果，其中不合规 ${nonCompliantCount} 条，待复核 ${uncertainCount} 条。默认优先阅读问题卡片，高级表格已折叠到“高级视图”。`
  }
  return `当前共 ${total} 条重点结果，其中不合规 ${nonCompliantCount} 条，待复核 ${uncertainCount} 条。高级视图会展示完整表格和追溯字段。`
})

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
  return String(
    resolvedDeepReviewResult.value?.[field] || selectedDeepReviewIssue.value?.[field] || '',
  )
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
    .replace(/(^|[。；;]\s*)(\d+[.、]\s*)/g, '$1\n$2')

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

function resolveBreakdownLabel(kind: 'executor' | 'document' | 'defect' | 'status', key: string) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey) return '未命名'
  if (kind === 'executor') {
    const map: Record<string, string> = {
      program: '程序规则',
      llm: 'LLM 规则',
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
      uncertain: '待复核',
      compliant: '合规',
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
  if (normalized === 'uncertain') return '待复核'
  if (normalized === 'not_applicable') return '不适用'
  if (normalized === 'failed') return '失败'
  return '合规'
}

function resolveDisplayStatusText(item?: Pick<SichuanBatchIssueItem, 'display_status'> | null) {
  if (!isPostprocessedFormalResult.value || !item?.display_status) return ''
  const normalized = String(item.display_status || '')
    .trim()
    .toLowerCase()
  if (normalized === 'confirmed_defect') return '确认缺陷'
  if (normalized === 'needs_review') return '待复核'
  if (normalized === 'data_quality_gap') return '数据缺口'
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
    String(record.status || '')
      .trim()
      .toLowerCase() === 'uncertain'
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
</script>

<style scoped>
.drawer-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f8fafc;
}

.drawer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 18px 22px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
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
  flex: 1;
  overflow: auto;
  padding: 16px 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.drawer-card {
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 14px 16px;
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

.issue-conclusion-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

.issue-conclusion-card {
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
  padding: 14px 16px;
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.08);
}

.issue-conclusion-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.issue-conclusion-head-main {
  flex: 1;
  min-width: 0;
}

.issue-conclusion-title {
  display: block;
  font-size: 14px;
  line-height: 1.5;
  color: #0f172a;
  font-weight: 600;
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

.issue-conclusion-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.issue-conclusion-row {
  font-size: 12px;
  color: #334155;
  line-height: 1.7;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: 8px;
}

.issue-conclusion-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.issue-conclusion-label {
  color: #64748b;
  font-weight: 500;
}

.issue-conclusion-structured {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.issue-conclusion-summary-text {
  color: #0f172a;
  margin: 0;
}

.issue-conclusion-section {
  border-left: 3px solid #dbeafe;
  padding-left: 10px;
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
</style>
