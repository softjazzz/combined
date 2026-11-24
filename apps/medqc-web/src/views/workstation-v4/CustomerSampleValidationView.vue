<template>
  <main class="customer-sample-page relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
    <div
      class="customer-sample-scroll custom-scrollbar flex-1 overflow-y-auto px-4 pt-4 xl:px-5"
      :class="{
        'has-work-dock': hasWorkDock,
      }"
    >
      <div class="customer-sample-container mx-auto w-full max-w-[1440px]">
        <div class="customer-sample-workspace">
          <div class="customer-sample-main-column">
            <!-- 页头：眉标 + 大标题；右侧为页面级操作 -->
            <div class="customer-sample-toolbar mq-page-head">
              <div class="customer-sample-page-title mq-page-head__copy">
                <span class="mq-page-eyebrow">质控作业 · 规则集质控</span>
                <h1 class="mq-page-title">客户样本验证</h1>
              </div>

              <div class="customer-sample-toolbar-actions mq-page-head__actions">
                <a-button
                  class="customer-sample-guide-action"
                  data-customer-guide="guide-entry"
                  @click="openCustomerSampleGuide"
                >
                  <Compass :size="15" />
                  功能导览
                </a-button>
                <a-button
                  class="customer-sample-create-action"
                  data-customer-guide="create-record"
                  :class="customerSampleGuideTargetClass('create-record')"
                  @click="openTestRecordDrawer"
                >
                  <FilePlus2 :size="15" />
                  创建测试病历
                </a-button>
                <a-button
                  type="primary"
                  data-customer-guide="run-validation"
                  :class="customerSampleGuideTargetClass('run-validation')"
                  :disabled="runButtonDisabled"
                  :loading="runLoading"
                  @click="handleRunPool"
                >
                  {{ runButtonText }}
                </a-button>
                <a-button class="customer-sample-task-history-action" @click="openTaskHistoryPage">
                  <span class="customer-sample-task-history-icon">
                    <History :size="15" />
                  </span>
                  <span class="customer-sample-task-history-label">查看质控记录</span>
                </a-button>
                <a-dropdown :trigger="['click']">
                  <a-button> 更多操作 </a-button>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item @click="handleMoreActionKey('refresh')">
                        刷新样本池
                      </a-menu-item>
                      <!-- 自建测试病历创建后固定，源库匹配/同步会改写病例绑定，后端同样拒绝 -->
                      <a-menu-item
                        :disabled="
                          !selectedPoolId || selectedPoolId === CUSTOMER_TEST_POOL_ID || syncLoading
                        "
                        @click="handleMoreActionKey('sync')"
                      >
                        同步样本病历
                      </a-menu-item>
                      <a-menu-item
                        :disabled="
                          !selectedPoolId || selectedPoolId === CUSTOMER_TEST_POOL_ID || syncLoading
                        "
                        @click="handleMoreActionKey('sync-by-hospitalization')"
                      >
                        按住院范围同步…
                      </a-menu-item>
                      <a-menu-item
                        :disabled="
                          !selectedPoolId ||
                          selectedPoolId === CUSTOMER_TEST_POOL_ID ||
                          matchLoading
                        "
                        @click="handleMoreActionKey('match')"
                      >
                        执行病历匹配
                      </a-menu-item>
                      <a-menu-item
                        :disabled="!selectedPool?.latest_job_id"
                        @click="handleMoreActionKey('latest')"
                      >
                        查看最近任务
                      </a-menu-item>
                      <a-menu-divider />
                      <a-menu-item @click="handleMoreActionKey('surgery-catalog')">
                        手术分级目录
                      </a-menu-item>
                      <a-menu-divider />
                      <a-sub-menu key="luxian-report" title="导出报告">
                        <a-menu-item @click="handleMoreActionKey('export-luxian-md')">
                          Markdown 评估报告
                        </a-menu-item>
                        <a-menu-item @click="handleMoreActionKey('export-luxian-csv')">
                          CSV 指标明细
                        </a-menu-item>
                      </a-sub-menu>
                      <a-menu-divider />
                      <a-sub-menu key="developer-admin" title="开发/管理员">
                        <a-menu-item @click="handleMoreActionKey('import')"> 导入模板 </a-menu-item>
                        <a-menu-item @click="handleMoreActionKey('export-luxian-json')">
                          JSON 原始结果
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item @click="handleMoreActionKey('mode-sc-full')">
                          SC 内涵质控全量 v1
                        </a-menu-item>
                        <a-menu-item @click="handleMoreActionKey('mode-sc')">
                          SC 样本规则模式
                        </a-menu-item>
                        <a-menu-item @click="handleMoreActionKey('mode-programmatic')">
                          硬门槛程序规则模式
                        </a-menu-item>
                        <a-menu-item @click="handleMoreActionKey('mode-legacy-customer')">
                          历史客户包
                        </a-menu-item>
                      </a-sub-menu>
                    </a-menu>
                  </template>
                </a-dropdown>
              </div>
            </div>

            <section class="customer-sample-console">
              <div class="customer-sample-command-bar">
                <div
                  class="customer-sample-field"
                  data-customer-guide="sample-pool"
                  :class="customerSampleGuideTargetClass('sample-pool')"
                >
                  <div class="customer-sample-field-label">当前样本池</div>
                  <div class="flex items-center gap-2">
                    <a-select
                      v-model:value="selectedPoolId"
                      class="w-full customer-sample-toolbar-select"
                      size="middle"
                      :loading="poolLoading"
                      :options="poolOptions"
                      placeholder="请选择样本池"
                      show-search
                      option-filter-prop="label"
                      @change="handlePoolChange"
                    />
                    <a-button
                      class="customer-sample-pool-manage-button"
                      @click="openPoolManagement"
                    >
                      <Settings2 :size="15" />
                      管理
                    </a-button>
                    <span
                      v-if="ruleSetDirectoryFallbackActive"
                      class="shrink-0 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[12px] font-medium text-amber-700"
                    >
                      内置目录
                    </span>
                  </div>
                </div>

                <div
                  class="customer-sample-field"
                  data-customer-guide="sample-rule"
                  :class="customerSampleGuideTargetClass('sample-rule')"
                >
                  <div class="customer-sample-field-label">验证规则集</div>
                  <div class="customer-sample-rule-switcher" role="group" aria-label="验证规则集">
                    <button
                      v-for="ruleSet in mainRuleSets"
                      :key="ruleSet.rule_set_key"
                      type="button"
                      class="customer-sample-rule-card"
                      :data-rule-set-key="ruleSet.rule_set_key"
                      :aria-pressed="selectedRuleSet?.rule_set_key === ruleSet.rule_set_key"
                      :class="ruleSetCardClass(ruleSet)"
                      @click="handleRuleSetChange(ruleSet.rule_set_key)"
                    >
                      <span>{{ ruleSet.rule_set_name }}</span>
                      <em>{{
                        Number(ruleSet.rule_count || 0) > 0 ? `${ruleSet.rule_count}` : '动态'
                      }}</em>
                    </button>
                  </div>
                </div>
              </div>

              <div class="customer-sample-status-strip">
                <div
                  v-for="step in workflowSteps"
                  :key="step.label"
                  class="customer-sample-step"
                  :class="step.className"
                >
                  <span>{{ step.label }}</span>
                  <strong>{{ step.value }}</strong>
                </div>
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="text-[14px] font-semibold text-slate-900">
                      {{ selectedRuleSet?.rule_set_name || '泸县0609质控点验证 v1' }}
                    </span>
                    <span class="customer-sample-meta-chip"
                      >场景 {{ ruleSetScopeLabel(selectedRuleSet?.scope) }}</span
                    >
                  </div>
                </div>
                <div class="customer-sample-rule-summary">
                  <span class="customer-sample-coverage-chip border-sky-200 bg-sky-50 text-sky-700">
                    规则数 {{ selectedRuleSetRuleCountText }}
                  </span>
                  <span
                    v-if="
                      selectedRuleSet?.artifact_freshness?.status &&
                      selectedRuleSet.artifact_freshness.status !== 'fresh'
                    "
                    class="customer-sample-coverage-chip border-amber-200 bg-amber-50 text-amber-700"
                  >
                    验收工件需刷新
                  </span>
                  <button
                    type="button"
                    class="customer-sample-internal-toggle"
                    @click="openTaskHistoryPage"
                  >
                    质控记录
                  </button>
                  <button
                    v-if="selectedRuleSetCoverageChips.length"
                    type="button"
                    class="customer-sample-internal-toggle"
                    @click="toggleInternalDiagnostic"
                  >
                    内部覆盖详情
                  </button>
                </div>
              </div>

              <section
                v-if="importWorkflow"
                class="rounded-[22px] border border-slate-200/80 bg-white px-5 py-4 shadow-[0_12px_28px_rgba(148,163,184,0.12)]"
              >
                <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="text-[16px] font-semibold text-slate-900">导入样本 ID 结果</span>
                      <span
                        class="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[12px] font-medium text-slate-500"
                      >
                        {{ importWorkflow.poolName }}
                      </span>
                    </div>
                    <div
                      class="mt-2 grid gap-2 text-[13px] leading-6 text-slate-600 md:grid-cols-3"
                    >
                      <div>
                        已导入
                        <strong class="text-slate-900">{{ importWorkflow.importedRows }}</strong> 条
                        ID
                      </div>
                      <div>
                        匹配 <strong class="text-slate-900">{{ importWorkflow.matched }}</strong> 份
                        <span class="text-slate-400">/</span>
                        待确认 {{ importWorkflow.ambiguous }} 份
                        <span class="text-slate-400">/</span>
                        未找到 {{ importWorkflow.unmatched }} 份
                      </div>
                      <div
                        :class="
                          importWorkflow.status === 'no_match' ||
                          importWorkflow.status === 'match_failed'
                            ? 'text-amber-700'
                            : 'text-slate-500'
                        "
                      >
                        {{ importWorkflow.message }}
                      </div>
                    </div>
                  </div>
                  <div class="flex shrink-0 flex-wrap items-center gap-2">
                    <a-button
                      :loading="importWorkflow.matching || matchLoading"
                      @click="runPoolMatch({ source: 'workflow' })"
                    >
                      重新匹配
                    </a-button>
                    <a-button
                      type="primary"
                      :disabled="importWorkflow.matched <= 0 || syncLoading"
                      :loading="syncLoading || importWorkflow.status === 'syncing'"
                      @click="handleSyncPoolRecords"
                    >
                      开始同步匹配到的病历
                    </a-button>
                  </div>
                </div>
                <div class="mt-4 grid gap-2 md:grid-cols-3">
                  <div
                    v-for="step in importWorkflowSteps"
                    :key="step.label"
                    class="rounded-2xl border px-3 py-2 text-[13px]"
                    :class="step.className"
                  >
                    <div class="font-semibold">
                      {{ step.label }}
                    </div>
                    <div class="mt-1 text-[12px] leading-5">
                      {{ step.description }}
                    </div>
                  </div>
                </div>
              </section>

              <details
                v-if="isLuxian0609Mode"
                id="customer-sample-luxian-scope"
                data-customer-guide="lx0609-scope"
                class="customer-sample-scope-disclosure"
                :class="customerSampleGuideTargetClass('lx0609-scope')"
                :open="
                  customerSampleGuideOpen &&
                  currentCustomerSampleGuideStep?.target === 'lx0609-scope'
                    ? true
                    : undefined
                "
              >
                <summary class="customer-sample-scope-summary">
                  <span class="customer-sample-scope-summary__title">质控点范围</span>
                  <span class="customer-sample-scope-summary__value">{{
                    luxianScopeModeText
                  }}</span>
                  <span class="customer-sample-scope-summary__action">调整范围</span>
                </summary>
                <LuxianRuleScopePanel
                  :families="luxianRuleFamilies"
                  :selected-rule-ids="selectedLuxianCustomerRuleIds"
                  :expanded-family-keys="expandedLuxianRuleFamilyKeys"
                  :helper-text="luxianScopeHelperText"
                  :mode-text="luxianScopeModeText"
                  :all-rule-ids="allLuxianRuleIds"
                  :selected-family-count="selectedLuxianFamilyCount"
                  :all-rules-selected="isAllLuxianRulesSelected"
                  @select-all="toggleAllLuxianRuleFamilies"
                  @clear="clearLuxianRuleScope"
                  @toggle-family="selectLuxianRuleFamily"
                  @toggle-expanded="toggleLuxianRuleFamilyExpanded"
                  @toggle-rule="toggleLuxianRule"
                />
              </details>
            </section>

            <section class="customer-sample-diagnostic-panel">
              <a-collapse
                v-model:active-key="internalDiagnosticKeys"
                ghost
                class="customer-sample-internal-collapse"
                @change="handleInternalDiagnosticChange"
              >
                <a-collapse-panel key="sheet2" header="内部验收诊断">
                  <div class="border-b border-slate-200/80 px-5 pb-4">
                    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                      <div class="min-w-0">
                        <div class="text-[17px] font-semibold text-slate-900">
                          客户验收口径与规则增强诊断
                        </div>
                        <div class="mt-1 text-[13px] leading-6 text-slate-500">
                          该区域仅供内部验收、复核和下一轮规则治理使用，默认不展示给操作员。
                        </div>
                      </div>
                      <div class="text-[12px] leading-6 text-slate-400">
                        更新时间：{{ exactReviewAcceptance?.generated_at || '—' }}
                      </div>
                    </div>
                  </div>

                  <a-spin :spinning="exactReviewLoading">
                    <div v-if="exactReviewAcceptance" class="space-y-4 px-5 py-4">
                      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <div
                          v-for="item in exactReviewStatusCards"
                          :key="item.label"
                          class="rounded-[20px] border px-4 py-4 shadow-[0_10px_24px_rgba(148,163,184,0.10)]"
                          :class="item.cardClass"
                        >
                          <div class="text-[12px] font-medium text-slate-500">
                            {{ item.label }}
                          </div>
                          <div class="mt-3 text-[30px] font-semibold leading-none text-slate-900">
                            {{ item.value }}
                          </div>
                          <div class="mt-3 text-[12px] leading-6 text-slate-500">
                            {{ item.help }}
                          </div>
                        </div>
                      </div>

                      <div
                        class="rounded-[20px] border border-amber-200 bg-amber-50 px-4 py-4 text-[13px] leading-6 text-amber-900"
                      >
                        <div class="font-semibold text-amber-950">blocked_with_reason 口径</div>
                        <div class="mt-1">
                          {{ exactReviewAcceptance.explanations.blocked_with_reason }}
                        </div>
                        <div class="mt-2 text-amber-800">
                          {{ exactReviewAcceptance.explanations.acceptance_note }}
                        </div>
                      </div>

                      <div class="flex flex-wrap gap-2">
                        <span
                          v-for="item in exactReviewReasonTags"
                          :key="item.label"
                          class="inline-flex rounded-full border px-3 py-1 text-[12px] font-medium"
                          :class="item.className"
                        >
                          {{ item.label }}：{{ item.value }}
                        </span>
                      </div>

                      <div class="grid gap-4 xl:grid-cols-2">
                        <article
                          v-for="bucket in exactReviewBacklogBuckets"
                          :key="bucket.category"
                          class="rounded-[20px] border px-4 py-4"
                          :class="backlogBucketCardClass(bucket.category)"
                        >
                          <div class="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <div class="text-[16px] font-semibold text-slate-900">
                                {{ bucket.category }}
                              </div>
                              <div class="mt-1 text-[13px] leading-6 text-slate-500">
                                {{ bucket.definition }}
                              </div>
                            </div>
                            <span
                              class="inline-flex rounded-full border px-3 py-1 text-[12px] font-semibold"
                              :class="backlogBucketTagClass(bucket.category)"
                            >
                              {{ bucket.count }} 条
                            </span>
                          </div>
                          <div
                            class="mt-3 rounded-2xl border border-white/70 bg-white/80 px-3 py-3 text-[13px] leading-6 text-slate-600"
                          >
                            下一轮动作：{{ bucket.next_action }}
                          </div>
                          <div
                            v-if="bucket.top_issue_families.length"
                            class="mt-3 flex flex-wrap gap-2"
                          >
                            <span
                              v-for="family in bucket.top_issue_families"
                              :key="`${bucket.category}-${family.issue_family}`"
                              class="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[12px] text-slate-600"
                            >
                              {{ family.issue_family }} × {{ family.count }}
                            </span>
                          </div>
                        </article>
                      </div>

                      <div
                        v-if="exactReviewAcceptance.archive_summary"
                        class="rounded-[20px] border border-slate-200 bg-slate-50 px-4 py-4 text-[13px] leading-6 text-slate-600"
                      >
                        已归档临时 probe/report
                        {{ exactReviewAcceptance.archive_summary.archived_file_count }} 个；
                        归档目录：{{ exactReviewAcceptance.archive_summary.archive_dir }}
                      </div>
                    </div>

                    <div v-else class="px-5 py-6 text-[13px] leading-6 text-rose-600">
                      {{ exactReviewError || '暂未读取到 Sheet2 精确复核验收包。' }}
                    </div>
                  </a-spin>
                </a-collapse-panel>
              </a-collapse>
            </section>

            <section
              v-if="showSyncStatusBar"
              class="flex min-h-[52px] items-center gap-3 rounded-xl border px-4 py-2.5"
              :class="syncStatusBar.className"
              aria-live="polite"
            >
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" :class="syncStatusBar.dotClassName" />
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <span class="text-[13px] font-semibold">{{ syncStatusBar.title }}</span>
                  <span class="truncate text-[13px] text-slate-600">
                    {{ syncStatusBar.summary }}
                  </span>
                </div>
                <div
                  v-if="syncStatusBar.description"
                  class="mt-0.5 truncate text-[12px] text-slate-500"
                >
                  {{ syncStatusBar.description }}
                </div>
              </div>
              <div class="flex shrink-0 items-center gap-1">
                <a-button
                  v-if="syncStatusBar.canRetry"
                  type="link"
                  size="small"
                  class="!px-2"
                  @click="handleRetrySync"
                >
                  重试
                </a-button>
                <a-button type="link" size="small" class="!px-2" @click="openSyncDetailDrawer">
                  查看详情
                </a-button>
                <a-button
                  v-if="syncStatusBar.canDismiss"
                  type="text"
                  size="small"
                  class="!px-2 !text-slate-500"
                  aria-label="关闭同步提示"
                  @click="dismissSyncStatusBar"
                >
                  关闭
                </a-button>
              </div>
            </section>

            <section
              class="customer-sample-list-panel"
              data-customer-guide="record-list"
              :class="customerSampleGuideTargetClass('record-list')"
            >
              <div class="border-b border-slate-200/80 px-5 py-4">
                <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-3">
                      <div class="text-[18px] font-semibold text-slate-900">病历池</div>
                      <div class="customer-sample-inline-metrics">
                        <span v-for="item in summaryCards" :key="item.label">
                          {{ item.label }} <strong>{{ item.value }}</strong>
                        </span>
                      </div>
                    </div>
                    <div class="mt-1 text-[13px] leading-6 text-slate-500">
                      搜索、筛选并勾选病历后发起当前模式的质控任务。
                    </div>
                  </div>
                  <div class="customer-sample-scope-pill">
                    {{ currentScopeDescription }}
                  </div>
                </div>
              </div>

              <div class="space-y-3 px-5 py-4">
                <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                  <div class="flex flex-1 flex-col gap-3 xl:flex-row xl:items-center">
                    <a-input
                      v-model:value="filters.query"
                      class="w-full xl:min-w-[320px] xl:flex-1 customer-sample-toolbar-input"
                      size="middle"
                      placeholder="搜索患者、住院号或问题摘要"
                      @press-enter="loadRecords()"
                    />
                  </div>

                  <div class="flex flex-wrap gap-2 xl:justify-end">
                    <a-select
                      v-model:value="filters.coverageType"
                      class="min-w-[140px] customer-sample-toolbar-select"
                      size="middle"
                      allow-clear
                      placeholder="样本范围"
                      :options="coverageOptions"
                    />
                    <a-select
                      v-model:value="filters.matchStatus"
                      class="min-w-[140px] customer-sample-toolbar-select"
                      size="middle"
                      allow-clear
                      placeholder="病历关联"
                      :options="matchStatusOptions"
                    />
                    <div
                      class="flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 text-[13px] text-slate-600"
                    >
                      <span class="mr-2">{{
                        isSyncedOnlyValidationMode ? '首批筛选已关闭' : '仅首批'
                      }}</span>
                      <a-switch
                        v-model:checked="filters.includeInBatch"
                        :disabled="isSyncedOnlyValidationMode"
                      />
                    </div>
                    <div
                      class="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 text-[13px] text-slate-600"
                    >
                      <span>并发病历数</span>
                      <a-select
                        v-model:value="runOptions.maxParallelRecords"
                        :disabled="initialConfigLoading"
                        class="w-[88px] customer-sample-toolbar-select"
                        size="middle"
                        :options="parallelOptions"
                      />
                    </div>
                    <a-button type="primary" class="!rounded-full" @click="loadRecords()">
                      查询
                    </a-button>
                    <a-button class="!rounded-full" @click="resetFilters"> 重置 </a-button>
                  </div>
                </div>

                <a-table
                  class="customer-sample-record-table"
                  row-key="id"
                  size="middle"
                  :loading="itemLoading"
                  :columns="itemColumns"
                  :data-source="records"
                  :row-selection="rowSelection"
                  :pagination="paginationConfig"
                  :scroll="{ x: 1120 }"
                  :locale="{ emptyText: tableEmptyText }"
                />
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="hasWorkDock"
      class="customer-sample-work-dock"
      :class="{ 'is-compact': isWorkDockTaskCompact }"
      data-testid="customer-sample-work-dock"
      aria-live="polite"
    >
      <div v-if="currentQcTask" class="customer-sample-work-dock__task">
        <CustomerSampleQcTaskStatusBar
          :task="currentQcTask"
          :loading="currentQcTaskLoading"
          :canceling="cancelBatchJobLoading"
          :reviewing="reviewBatchJobLoadingId === currentQcTask?.id"
          :compact="isWorkDockTaskCompact"
          :collapsible="canCollapseWorkDockTask"
          @view-result="openCurrentTaskResult"
          @cancel="confirmCancelBatchJob"
          @review="handleReviewCurrentTask"
          @export="handleExportCurrentTask"
          @open-history="openTaskHistoryPage"
          @toggle-compact="toggleWorkDockTaskCompact"
        />
      </div>

      <div
        v-if="currentQcTask && selectedRecordStats.selectedCount > 0"
        class="customer-sample-work-dock__divider"
        aria-hidden="true"
      />

      <div
        v-if="selectedRecordStats.selectedCount > 0"
        class="customer-sample-work-dock__selection"
      >
        <div class="customer-sample-selection-run-summary">
          <strong>已选择 {{ selectedRecordStats.selectedCount }} 份病历</strong>
          <span>
            可质控 {{ selectedRecordStats.runnableCount }} 份
            <template v-if="selectedRecordStats.blockedCount > 0">
              ，{{ selectedRecordStats.blockedCount }} 份当前阻塞（不会缩小范围执行）
            </template>
            · 当前范围：{{ selectedRunScopeSummary }}
          </span>
          <div
            v-if="runLoading"
            class="customer-sample-selection-run-notice"
            data-testid="customer-sample-run-creating-notice"
            role="status"
          >
            <span class="customer-sample-selection-run-notice__spinner" aria-hidden="true" />
            <span>
              <strong>正在创建质控任务</strong>
              <small>任务创建完成后将自动显示实时执行进度</small>
            </span>
          </div>
        </div>
        <div class="customer-sample-selection-run-actions">
          <a-button @click="clearSelectedRecords"> 清空选择 </a-button>
          <a-button v-if="isLuxian0609Mode" @click="scrollToLuxianScope"> 调整质控范围 </a-button>
          <a-button
            type="primary"
            :disabled="runButtonDisabled"
            :loading="runLoading"
            @click="handleRunPool"
          >
            {{ runLoading ? '正在创建…' : '开始质控' }}
          </a-button>
        </div>
      </div>
    </div>

    <div v-if="customerSampleGuideOpen" class="customer-sample-tour-layer">
      <div class="customer-sample-tour-scrim" />
      <div class="customer-sample-tour-card" :style="customerSampleTourCardStyle">
        <div class="customer-sample-tour-kicker">客户演示主流程</div>
        <div class="customer-sample-tour-count">
          {{ customerSampleGuideStepIndex + 1 }} / {{ customerSampleGuideSteps.length }}
        </div>
        <h3>{{ currentCustomerSampleGuideStep.title }}</h3>
        <p>{{ currentCustomerSampleGuideStep.description }}</p>
        <div class="customer-sample-tour-dots">
          <button
            v-for="(_, index) in customerSampleGuideSteps"
            :key="index"
            type="button"
            :class="{ 'is-active': index === customerSampleGuideStepIndex }"
            :aria-label="`查看第 ${index + 1} 步`"
            @click="goToCustomerSampleGuideStep(index)"
          />
        </div>
        <div class="customer-sample-guide-footer">
          <a-button class="customer-sample-guide-dismiss" @click="closeCustomerSampleGuide">
            跳过
          </a-button>
          <a-button class="customer-sample-guide-start" @click="startSyntheticCaseFromGuide">
            创建测试病历
          </a-button>
          <a-button
            v-if="customerSampleGuideStepIndex > 0"
            @click="goToPreviousCustomerSampleGuideStep"
          >
            上一步
          </a-button>
          <a-button
            type="primary"
            class="customer-sample-guide-next"
            @click="goToNextCustomerSampleGuideStep"
          >
            {{ isLastCustomerSampleGuideStep ? '完成导览' : '下一步' }}
          </a-button>
        </div>
      </div>
    </div>

    <a-modal
      v-model:open="poolManagementOpen"
      title="管理样本池"
      :width="680"
      :footer="null"
      destroy-on-close
    >
      <div class="pool-management-panel">
        <div class="pool-management-toolbar">
          <a-input-search
            v-model:value="poolManagementQuery"
            allow-clear
            placeholder="搜索样本池名称或来源文件"
            @search="handlePoolManagementSearch"
          />
          <span>共 {{ poolManagementPagination.total }} 个</span>
        </div>

        <a-spin :spinning="poolManagementLoading">
          <div v-if="managedPools.length" class="pool-management-list">
            <div v-for="pool in managedPools" :key="pool.id" class="pool-management-row">
              <div class="pool-management-main">
                <div class="pool-management-title-line">
                  <strong>{{ pool.name || '未命名样本池' }}</strong>
                  <span v-if="pool.id === selectedPoolId" class="pool-management-current">
                    当前
                  </span>
                  <span v-if="pool.id === CUSTOMER_TEST_POOL_ID" class="pool-management-protected">
                    系统池
                  </span>
                </div>
                <div class="pool-management-meta">
                  <span>{{ pool.total_items || 0 }} 份样本</span>
                  <span>更新于 {{ formatPaddedQcTaskDateTime(pool.updated_at || pool.created_at) }}</span>
                  <span v-if="pool.latest_job_status">
                    最近任务：{{ poolJobStatusLabel(pool.latest_job_status) }}
                  </span>
                </div>
              </div>
              <a-button
                type="text"
                danger
                class="pool-management-delete"
                :disabled="poolDeletionDisabled(pool)"
                :loading="deletingPoolIds.includes(pool.id)"
                @click="confirmDeletePool(pool)"
              >
                <Trash2 :size="15" />
                删除
              </a-button>
            </div>
          </div>
          <a-empty v-else description="没有找到样本池" class="!my-8" />
        </a-spin>

        <div
          v-if="poolManagementPagination.total > poolManagementPagination.pageSize"
          class="pool-management-pagination"
        >
          <a-pagination
            v-model:current="poolManagementPagination.page"
            :page-size="poolManagementPagination.pageSize"
            :total="poolManagementPagination.total"
            :show-size-changer="false"
            size="small"
            @change="loadManagedPools"
          />
        </div>
        <div class="pool-management-note">
          删除样本池不会删除原始病历、Bundle
          或已完成的质控结果。正在同步或质控的样本池需先结束任务。
        </div>
      </div>
    </a-modal>

    <a-drawer
      v-model:open="syncDetailDrawerOpen"
      title="样本病历同步详情"
      placement="right"
      :width="680"
    >
      <div v-if="syncJobDetail" class="space-y-5">
        <div class="flex items-start justify-between gap-4 border-b border-slate-100 pb-4">
          <div class="min-w-0">
            <div class="text-[15px] font-semibold text-slate-900">
              {{ syncStatusBar.title }}
            </div>
            <div class="mt-1 text-[13px] leading-6 text-slate-500">
              {{ syncStatusBar.summary }}
            </div>
          </div>
          <a-tag :color="syncJobStatusColor(syncJobDetail.status)">
            {{ syncJobStatusText(syncJobDetail.status) }}
          </a-tag>
        </div>

        <div
          v-if="syncResultNotice"
          class="rounded-xl border px-4 py-3 text-[13px] leading-6"
          :class="syncResultNotice.className"
        >
          <div class="font-semibold">
            {{ syncResultNotice.title }}
          </div>
          <div class="mt-1">
            {{ syncResultNotice.description }}
          </div>
        </div>

        <div
          v-if="syncHospitalizationSummary"
          class="rounded-xl border border-blue-100 bg-blue-50/70 px-4 py-3 text-[13px] leading-6 text-slate-600"
        >
          <span class="font-semibold text-slate-800">本次住院范围：</span>
          {{ syncHospitalizationSummary.range }}；新增
          {{ syncHospitalizationSummary.newCount }} 份，已存在
          {{ syncHospitalizationSummary.existingCount }} 份，失败
          {{ syncHospitalizationSummary.failedCount }} 份。
        </div>

        <div class="grid grid-cols-2 border-y border-slate-200 sm:grid-cols-4">
          <div class="px-3 py-4 text-center">
            <div class="text-[12px] text-slate-400">病历进度</div>
            <div class="mt-1 text-[19px] font-semibold text-slate-900">
              {{ syncRecordProgress.completed }}/{{ syncRecordProgress.total }}
            </div>
          </div>
          <div class="border-l border-slate-200 px-3 py-4 text-center">
            <div class="text-[12px] text-slate-400">文书就绪</div>
            <div class="mt-1 text-[19px] font-semibold text-slate-900">
              {{ syncRecordProgress.ready }} 份
            </div>
          </div>
          <div class="border-l border-slate-200 px-3 py-4 text-center">
            <div class="text-[12px] text-slate-400">源库匹配</div>
            <div class="mt-1 text-[19px] font-semibold text-slate-900">
              {{ syncResolvedStats.matched }} 份
            </div>
          </div>
          <div class="border-l border-slate-200 px-3 py-4 text-center">
            <div class="text-[12px] text-slate-400">表进度</div>
            <div class="mt-1 text-[19px] font-semibold text-slate-900">
              {{ syncProgress.processed_tables ?? 0 }}/{{ syncProgress.total_tables ?? 0 }}
            </div>
          </div>
        </div>

        <div class="space-y-3 text-[13px] leading-6 text-slate-600">
          <div class="flex items-start justify-between gap-4">
            <span class="shrink-0 text-slate-400">当前步骤</span>
            <span class="text-right font-medium text-slate-800">
              {{ syncCustomerStepText }}
            </span>
          </div>
          <div class="flex items-start justify-between gap-4">
            <span class="shrink-0 text-slate-400">当前数据表</span>
            <span class="min-w-0 break-all text-right">
              {{ syncProgress.current_table || '—' }}
            </span>
          </div>
          <div class="flex items-start justify-between gap-4">
            <span class="shrink-0 text-slate-400">数据行</span>
            <span class="text-right">
              拉取 {{ syncProgress.total_rows_pulled ?? 0 }} 行，写入
              {{ syncProgress.total_rows_upserted ?? 0 }} 行
            </span>
          </div>
          <div class="flex items-start justify-between gap-4">
            <span class="shrink-0 text-slate-400">匹配情况</span>
            <span class="text-right">
              待确认 {{ syncResolvedStats.ambiguous }} 份，未找到
              {{ syncResolvedStats.unmatched }} 份
            </span>
          </div>
          <div
            v-if="syncRecordProgress.missingMr > 0"
            class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800"
          >
            有 {{ syncRecordProgress.missingMr }}
            份病历尚未写入主记录，暂时不会出现在病历池中。
          </div>
        </div>

        <div v-if="syncStatusBar.canRetry" class="flex justify-end border-t border-slate-100 pt-4">
          <a-button type="primary" :loading="syncLoading" @click="handleRetrySync">
            重新同步
          </a-button>
        </div>
      </div>
    </a-drawer>

    <a-modal
      v-model:open="importModalOpen"
      title="导入客户样本模板"
      :confirm-loading="importingPool"
      ok-text="开始导入"
      cancel-text="取消"
      @ok="handleImportPool"
      @cancel="resetImportForm"
    >
      <div class="space-y-4 pt-2">
        <div>
          <div class="mb-2 text-[13px] font-medium text-slate-700">样本池名称</div>
          <a-input
            v-model:value="importForm.poolName"
            placeholder="例如：手工问题样本池-第二轮"
            :maxlength="60"
          />
        </div>
        <div>
          <div class="mb-2 text-[13px] font-medium text-slate-700">备注</div>
          <a-textarea
            v-model:value="importForm.description"
            :rows="3"
            placeholder="可选，记录这次导入的说明"
            :maxlength="200"
          />
        </div>
        <div>
          <div
            class="mb-2 flex items-center justify-between gap-3 text-[13px] font-medium text-slate-700"
          >
            <span>Excel 模板</span>
            <a-button type="link" class="!px-0" @click="handleDownloadTemplate">
              下载模板
            </a-button>
          </div>
          <a-upload-dragger
            v-model:file-list="importFileList"
            :before-upload="handleImportFileSelect"
            :multiple="false"
            :max-count="1"
            accept=".xls,.xlsx"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p class="ant-upload-text">点击或拖拽上传 Excel 模板</p>
            <p class="ant-upload-hint">支持 .xls / .xlsx，默认读取第一个工作表。</p>
            <p class="mt-2 text-[12px] text-slate-400">
              优先填写就诊ID，可补充住院流水号、病案号和患者姓名。
            </p>
          </a-upload-dragger>
        </div>
      </div>
    </a-modal>

    <a-modal
      v-model:open="hospitalizationSyncModalOpen"
      title="住院范围同步"
      :width="620"
      :confirm-loading="hospitalizationSyncSubmitting"
      :ok-button-props="{ disabled: !hospitalizationSyncCanSubmit }"
      :ok-text="hospitalizationSyncOkText"
      cancel-text="取消"
      @ok="handleHospitalizationSync"
    >
      <div class="space-y-4 pt-2">
        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <div class="text-[12px] text-slate-400">当前样本池</div>
            <div class="mt-1 text-[15px] font-semibold text-slate-800">
              {{ selectedPool?.name || '未选择样本池' }}
            </div>
          </div>
          <span class="text-[12px] text-slate-400">按住院三坐标去重</span>
        </div>

        <label class="block">
          <span class="mb-1.5 block text-[13px] font-medium text-slate-700">病例范围</span>
          <a-segmented
            v-model:value="hospitalizationSyncForm.scopeMode"
            :options="hospitalizationScopeOptions"
            block
            @change="refreshHospitalizationScopePreview"
          />
        </label>

        <div
          class="grid grid-cols-1 gap-3"
          :class="hospitalizationScopeNeedsDischargeRange ? 'sm:grid-cols-3' : ''"
        >
          <label v-if="hospitalizationSyncForm.scopeMode !== 'discharged'" class="block">
            <span class="mb-1.5 block text-[13px] font-medium text-slate-700">在院统计日期</span>
            <a-date-picker
              v-model:value="hospitalizationSyncForm.asOfDate"
              class="w-full"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              :allow-clear="false"
              @change="refreshHospitalizationScopePreview"
            />
          </label>
          <label v-if="hospitalizationScopeNeedsDischargeRange" class="block">
            <span class="mb-1.5 block text-[13px] font-medium text-slate-700">出院开始日期</span>
            <a-date-picker
              v-model:value="hospitalizationSyncForm.dischargeStartDate"
              class="w-full"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              :allow-clear="false"
              @change="refreshHospitalizationScopePreview"
            />
          </label>
          <label v-if="hospitalizationScopeNeedsDischargeRange" class="block">
            <span class="mb-1.5 block text-[13px] font-medium text-slate-700">出院结束日期</span>
            <a-date-picker
              v-model:value="hospitalizationSyncForm.dischargeEndDate"
              class="w-full"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              :allow-clear="false"
              @change="refreshHospitalizationScopePreview"
            />
          </label>
        </div>

        <label class="block">
          <div class="mb-1.5 flex items-center justify-between">
            <span class="text-[13px] font-medium text-slate-700">科室（可不选）</span>
            <a-button
              v-if="hospitalizationSyncPreviewError"
              type="link"
              size="small"
              class="!h-auto !p-0 !text-[12px]"
              @click="refreshHospitalizationScopePreview"
            >
              重新加载
            </a-button>
          </div>
          <a-select
            v-model:value="hospitalizationSyncForm.departments"
            mode="multiple"
            allow-clear
            :loading="hospitalizationSyncPreviewLoading"
            :options="hospitalizationSyncDepartmentOptions"
            :placeholder="
              hospitalizationSyncPreviewError
                ? '科室加载失败，可重试或同步全部科室'
                : '不选择则同步范围内全部科室'
            "
            class="w-full"
            :max-tag-count="3"
            @change="refreshHospitalizationScopePreview"
          />
        </label>

        <div
          v-if="hospitalizationSyncPreviewLoading"
          class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-5 text-center text-[13px] text-slate-500"
        >
          正在核对当前在院和期间出院病历…
        </div>
        <div
          v-else-if="hospitalizationSyncPreviewError"
          class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] leading-6 text-amber-800"
        >
          {{ hospitalizationSyncPreviewError }}
        </div>
        <div
          v-else-if="hospitalizationSyncPreview"
          class="rounded-xl border border-blue-100 bg-blue-50/70 px-4 py-3"
        >
          <div class="grid grid-cols-5 gap-2 text-center">
            <div v-for="item in hospitalizationPreviewMetrics" :key="item.label">
              <div class="text-[11px] text-slate-500">
                {{ item.label }}
              </div>
              <div class="mt-1 text-[18px] font-semibold text-slate-900">
                {{ item.value }}
              </div>
            </div>
          </div>
          <div
            v-if="hospitalizationSyncPreview.warnings.length"
            class="mt-3 border-t border-blue-100 pt-2 text-[12px] leading-5 text-slate-600"
          >
            {{ hospitalizationSyncPreview.warnings.join('；') }}
          </div>
        </div>
        <div class="text-[12px] leading-5 text-slate-500">
          当前在院按统计日判断；期间出院按出院日期判断。开始后继续复用现有文书、医嘱和 Bundle
          同步链路。
        </div>
      </div>
    </a-modal>

    <a-drawer :open="detailOpen" width="720" title="病历关联问题" @close="detailOpen = false">
      <div v-if="activeRecord" class="space-y-5">
        <a-card size="small" class="rounded-2xl">
          <template #title> 病历概况 </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">科室：</span
              >{{ activeRecord.department || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">患者：</span
              >{{ activeRecord.patient_name || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">住院号：</span
              >{{ activeRecord.mr_no || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">visit_id：</span
              >{{ activeRecord.matched_visit_id || '-' }}
            </div>
          </div>
        </a-card>

        <a-card size="small" class="rounded-2xl">
          <template #title> 识别范围 </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">文书范围：</span>
              {{ summarizeRecordScope(activeRecord) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">验证说明：</span>
              {{ recordScopeHint(activeRecord) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">样本范围：</span>
              {{ activeRecord.coverage_types.map((item) => coverageLabel(item)).join('、') || '-' }}
            </div>
          </div>
        </a-card>

        <a-card size="small" class="rounded-2xl">
          <template #title> 病历关联 </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">关联结果：</span
              >{{ matchStatusLabel(activeRecord.match_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">下一步：</span
              >{{ matchStatusHint(activeRecord.match_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">visit_id：</span
              >{{ activeRecord.matched_visit_id || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">同步状态：</span
              >{{ activeRecord.sync_status || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">文书就绪：</span
              >{{ bundleStatusLabel(activeRecord.bundle_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">处理建议：</span
              >{{ bundleStatusHint(activeRecord.bundle_status) }}
            </div>
          </div>
        </a-card>

        <a-card size="small" class="rounded-2xl">
          <template #title> 关联人工问题 </template>
          <div class="space-y-3">
            <div
              v-for="sample in activeRecord.sample_items"
              :key="sample.id"
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-700"
            >
              <div class="font-medium text-slate-900">
                行号 {{ sample.row_no }} · {{ sample.issue_category || '未分类' }}
              </div>
              <div class="mt-1">
                {{ sample.manual_issue_text || '-' }}
              </div>
            </div>
          </div>
        </a-card>
      </div>
    </a-drawer>

    <a-modal
      v-model:open="editableCopyOpen"
      :title="null"
      :width="editableCopyReadonly ? '100vw' : 'min(1720px, calc(100vw - 24px))'"
      :style="editableCopyReadonly ? { top: '0', paddingBottom: '0', maxWidth: 'none' } : undefined"
      :body-style="
        editableCopyReadonly ? { height: '100%', padding: 0, overflow: 'hidden' } : undefined
      "
      :footer="null"
      :destroy-on-close="false"
      :centered="!editableCopyReadonly"
      :wrap-class-name="
        editableCopyReadonly
          ? 'editable-copy-workstation-modal-wrap is-readonly-fullscreen'
          : 'editable-copy-workstation-modal-wrap'
      "
      :class="[
        'editable-copy-workstation-modal',
        { 'is-readonly-fullscreen': editableCopyReadonly },
      ]"
      @cancel="closeEditableCopyDrawer"
    >
      <template v-if="editableCopyReadonly" #closeIcon>
        <RecordViewCloseIcon label="关闭病历" />
      </template>
      <div class="editable-copy-drawer">
        <ReadonlyMedicalRecordHeader
          v-if="editableCopyReadonly"
          class="editable-copy-readonly-header"
          :context="editableCopySourceRecord ? resolveRecordResultFocus(editableCopySourceRecord) : null"
        />
        <header v-else class="editable-copy-hero">
          <div>
            <div v-if="!editableCopyReadonly" class="editable-copy-eyebrow">
              客户样本验证 / {{ editableCopyReadonly ? '查看病历' : '编辑副本' }}
            </div>
            <h2>{{ editableCopyReadonly ? '查看病历' : '创建可编辑测试病历副本' }}</h2>
            <p v-if="!editableCopyReadonly">
              从已同步病历读取文书，复制成新的客户自建测试病历；本页所有修改只写入新副本。
            </p>
          </div>
          <div class="editable-copy-source-card">
            <span>{{ editableCopyReadonly ? '只读' : '来源病历' }}</span>
            <strong>{{ editableCopySourceRecord?.patient_name || '-' }}</strong>
            <em>{{ editableCopySourceRecord?.department || '-' }}</em>
          </div>
        </header>

        <div v-if="!editableCopyReadonly" class="editable-copy-notice">
          <div class="editable-copy-notice-title">原始同步病历保持只读</div>
          <div>
            {{
              editableCopyReadonly
                ? '这里展示的是已同步病历文书原文，只用于浏览和定位，不提供编辑、新增或删除文书。'
                : '这里会基于已同步病历创建一份新的客户自建测试病历。修改只保存到新副本，不会写回客户源库或原样本池。'
            }}
          </div>
        </div>

        <HospitalLoading
          v-if="showReadonlyRecordLoading"
          label="正在读取病历文书"
          fill
        />
        <a-spin v-else :spinning="editableCopyLoading">
          <div v-if="editableCopyDraft" class="editable-copy-content">
            <section v-if="!editableCopyReadonly" class="editable-copy-section">
              <h3>副本信息</h3>
              <div class="editable-copy-form-grid">
                <label>
                  <span>病历名称</span>
                  <a-input
                    v-model:value="editableCopyDraft.caseTitle"
                    :readonly="editableCopyReadonly"
                  />
                </label>
                <label>
                  <span>患者</span>
                  <a-input
                    v-model:value="editableCopyDraft.patientName"
                    :readonly="editableCopyReadonly"
                  />
                </label>
                <label>
                  <span>科室</span>
                  <a-input
                    v-model:value="editableCopyDraft.department"
                    :readonly="editableCopyReadonly"
                  />
                </label>
                <label>
                  <span>入院时间</span>
                  <a-input
                    v-model:value="editableCopyDraft.admissionTime"
                    :readonly="editableCopyReadonly"
                  />
                </label>
                <label v-if="!editableCopyReadonly || editableCopyDraft.dischargeTime">
                  <span>出院时间</span>
                  <a-input
                    v-model:value="editableCopyDraft.dischargeTime"
                    :readonly="editableCopyReadonly"
                  />
                </label>
                <label class="editable-copy-form-wide">
                  <span>主要诊断</span>
                  <a-input
                    v-model:value="editableCopyDraft.mainDiagnosis"
                    :readonly="editableCopyReadonly"
                  />
                </label>
              </div>
            </section>

            <QCRecordCompareWorkbench
              v-if="editableCopyReadonly"
              :visit-id="editableCopySourceRecord?.matched_visit_id || ''"
              :institute-id="editableCopySourceRecord?.matched_institute_id"
              :patient-id="editableCopySourceRecord?.matched_patient_id"
              :issues="[]"
              :provided-documents="editableCopyDraft.documents"
              :admission-time="editableCopyDraft.admissionTime"
              :discharge-time="editableCopyDraft.dischargeTime"
              document-only
            />
            <section v-else class="editable-copy-section editable-copy-document-workbench-section">
              <div class="editable-copy-section-header">
                <div>
                  <h3>文书内容</h3>
                  <p>
                    {{
                      editableCopyReadonly
                        ? '左侧按文书类型定位，右侧查看当前文书。当前模式不支持编辑和新增。'
                        : '左侧按文书类型定位，右侧编辑当前文书。删除仅影响新测试病历副本，原始同步病历不受影响。'
                    }}
                  </p>
                </div>
                <span>
                  {{
                    editableCopyReadonly
                      ? `${editableCopyDraft.documents.length} 份文书`
                      : `${editableCopyEnabledDocumentCount} / ${editableCopyDraft.documents.length} 份将保存`
                  }}
                </span>
              </div>
              <div v-if="!editableCopyReadonly" class="editable-copy-document-toolbar">
                <a-select
                  v-model:value="editableCopyNewDocumentType"
                  :options="testRecordDocumentTypeOptions"
                  class="editable-copy-document-type-select"
                />
                <a-button @click="addEditableCopyDocument()"> 新增文书 </a-button>
                <a-button @click="addEditableCopyOrderDocument()"> 新增医嘱 </a-button>
              </div>

              <div class="editable-copy-document-workbench">
                <aside class="editable-copy-document-directory">
                  <div class="editable-copy-document-directory-head">
                    <strong>文书目录</strong>
                    <span
                      >{{ editableCopyFilteredDocuments.length }} /
                      {{ editableCopyDraft.documents.length }}</span
                    >
                  </div>
                  <a-input
                    v-model:value="editableCopyDocumentQuery"
                    placeholder="搜索标题、正文或医嘱"
                    class="editable-copy-document-search"
                  />
                  <div class="editable-copy-document-filter">
                    <button
                      type="button"
                      :class="{ 'is-active': editableCopyDocumentFilter === 'all' }"
                      @click="editableCopyDocumentFilter = 'all'"
                    >
                      全部
                    </button>
                    <button
                      type="button"
                      :class="{ 'is-active': editableCopyDocumentFilter === 'enabled' }"
                      @click="editableCopyDocumentFilter = 'enabled'"
                    >
                      {{ editableCopyReadonly ? '有正文' : '将保存' }}
                    </button>
                    <button
                      type="button"
                      :class="{ 'is-active': editableCopyDocumentFilter === 'orders' }"
                      @click="editableCopyDocumentFilter = 'orders'"
                    >
                      医嘱
                    </button>
                    <button
                      v-if="!editableCopyReadonly"
                      type="button"
                      :class="{ 'is-active': editableCopyDocumentFilter === 'new' }"
                      @click="editableCopyDocumentFilter = 'new'"
                    >
                      新增
                    </button>
                  </div>
                  <div
                    class="editable-copy-document-directory-list"
                    :class="{ 'is-tree': editableCopyReadonly }"
                  >
                    <template v-for="group in editableCopyDocumentGroups" :key="group.key">
                      <button
                        v-if="editableCopyReadonly"
                        type="button"
                        class="editable-copy-document-group-title is-collapsible"
                        :aria-expanded="isEditableCopyDocumentGroupExpanded(group.key)"
                        :data-testid="`editable-copy-group-toggle-${group.key}`"
                        @click="toggleEditableCopyDocumentGroup(group.key)"
                      >
                        <span>
                          <i />
                          <b class="editable-copy-document-group-chevron" aria-hidden="true">{{
                            isEditableCopyDocumentGroupExpanded(group.key) ? '⌄' : '›'
                          }}</b>
                          {{ group.label }}
                        </span>
                        <em>{{ group.documents.length }}</em>
                      </button>
                      <div v-else class="editable-copy-document-group-title">
                        <span>{{ group.label }}</span>
                        <em>{{ group.documents.length }}</em>
                      </div>
                      <button
                        v-if="
                          (!editableCopyReadonly ||
                            isEditableCopyDocumentGroupExpanded(group.key)) &&
                          group.key === 'order'
                        "
                        type="button"
                        class="editable-copy-document-nav-item"
                        :class="{
                          'is-active': isEditableOrderDocument(editableCopyActiveDocument || {}),
                        }"
                        @click="selectEditableCopyOrderGroup"
                      >
                        <span>医嘱</span>
                        <small>{{ formatEditableCopyOrderGroupMeta(group.documents) }}</small>
                      </button>
                      <template
                        v-else-if="
                          !editableCopyReadonly || isEditableCopyDocumentGroupExpanded(group.key)
                        "
                      >
                        <button
                          v-for="document in group.documents"
                          :key="document.key"
                          type="button"
                          class="editable-copy-document-nav-item"
                          :class="{
                            'is-active': editableCopyActiveDocument?.key === document.key,
                            'is-disabled': document.enabled === false,
                          }"
                          @click="selectEditableCopyDocument(document.key)"
                        >
                          <span>{{ document.title || document.document_type }}</span>
                          <small>{{ formatEditableCopyDocumentMeta(document) }}</small>
                        </button>
                      </template>
                    </template>
                    <div
                      v-if="!editableCopyFilteredDocuments.length"
                      class="editable-copy-document-empty"
                    >
                      没有匹配的文书
                    </div>
                  </div>
                </aside>

                <article v-if="editableCopyActiveDocument" class="editable-copy-document-editor">
                  <div class="editable-copy-document-editor-head">
                    <div>
                      <span>{{
                        isEditableOrderDocument(editableCopyActiveDocument)
                          ? resolveEditableOrderTypeLabel(editableCopyActiveDocument)
                          : editableCopyActiveDocument.document_type
                      }}</span>
                      <h4>{{ editableCopyActiveDocument.title || '未命名文书' }}</h4>
                    </div>
                    <div class="editable-copy-document-actions">
                      <span v-if="editableCopyReadonly" class="editable-copy-readonly-pill">
                        只读原文
                      </span>
                      <label v-else class="editable-copy-document-toggle">
                        <input v-model="editableCopyActiveDocument.enabled" type="checkbox" />
                        <span>写入副本</span>
                      </label>
                      <a-button
                        v-if="!editableCopyReadonly"
                        size="small"
                        @click="removeEditableCopyDocument(editableCopyActiveDocument)"
                      >
                        {{
                          editableCopyActiveDocument.is_new
                            ? '删除'
                            : editableCopyActiveDocument.enabled === false
                              ? '恢复'
                              : '从副本删除'
                        }}
                      </a-button>
                    </div>
                  </div>
                  <div
                    v-if="isEditableOrderDocument(editableCopyActiveDocument)"
                    class="editable-copy-order-table-panel"
                  >
                    <div class="editable-copy-order-type-switch">
                      <button
                        type="button"
                        :class="{ 'is-active': editableCopyOrderTypeFilter === 'long' }"
                        @click="editableCopyOrderTypeFilter = 'long'"
                      >
                        长期医嘱
                      </button>
                      <button
                        type="button"
                        :class="{ 'is-active': editableCopyOrderTypeFilter === 'temporary' }"
                        @click="editableCopyOrderTypeFilter = 'temporary'"
                      >
                        临时医嘱
                      </button>
                    </div>
                    <MedicalOrderFilterBar
                      v-model="editableCopyOrderFilters"
                      :rows="editableCopyOrderRows"
                      :visible-count="editableCopyVisibleOrderRows.length"
                      :total-count="editableCopyScopedOrderRows.length"
                    />
                    <div class="editable-copy-order-table-wrap">
                      <table class="editable-copy-order-table">
                        <thead>
                          <tr>
                            <th>开始时间</th>
                            <th>医嘱类型</th>
                            <th>医嘱项目</th>
                            <th>医嘱号</th>
                            <th title="北京时间；计划结束不代表已实际停止">计划结束时间</th>
                            <th>实际停止时间</th>
                            <th>医嘱状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr
                            v-for="order in editableCopyVisibleOrderRows"
                            :key="order.document.key"
                            :class="{
                              'is-active': editableCopyActiveDocument?.key === order.document.key,
                              'is-disabled': order.document.enabled === false,
                            }"
                            @click="selectEditableCopyDocument(order.document.key)"
                          >
                            <td>{{ order.startTime }}</td>
                            <td>{{ order.orderType }}</td>
                            <td>{{ order.item }}</td>
                            <td :title="order.orderId">
                              {{ order.orderId || '-' }}
                            </td>
                            <td>{{ order.plannedEndTime || '-' }}</td>
                            <td>{{ order.stopTime || '-' }}</td>
                            <td>{{ order.status }}</td>
                          </tr>
                          <tr v-if="!editableCopyVisibleOrderRows.length">
                            <td colspan="7" class="editable-copy-order-empty">
                              暂无符合当前条件的医嘱
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div class="editable-copy-document-fields">
                    <label>
                      <span>文书标题</span>
                      <a-input
                        v-model:value="editableCopyActiveDocument.title"
                        :readonly="editableCopyReadonly"
                      />
                    </label>
                    <label>
                      <span>记录时间</span>
                      <a-input
                        v-model:value="editableCopyActiveDocument.record_time"
                        :readonly="editableCopyReadonly"
                      />
                    </label>
                    <label>
                      <span>提交时间</span>
                      <a-input
                        v-model:value="editableCopyActiveDocument.submit_time"
                        :readonly="editableCopyReadonly"
                      />
                    </label>
                  </div>
                  <ReadonlyMedicalDocumentContent
                    v-if="
                      editableCopyReadonly && !isEditableOrderDocument(editableCopyActiveDocument)
                    "
                    :document="editableCopyActiveDocument"
                  />
                  <a-textarea
                    v-else
                    v-model:value="editableCopyActiveDocument.content"
                    :rows="isEditableOrderDocument(editableCopyActiveDocument) ? 12 : 16"
                    :readonly="editableCopyReadonly"
                  />
                </article>

                <article
                  v-else
                  class="editable-copy-document-editor editable-copy-document-editor-empty"
                >
                  请选择左侧文书进行编辑
                </article>
              </div>
            </section>

            <section v-if="!editableCopyReadonly" class="editable-copy-section">
              <h3>验证说明</h3>
              <a-textarea v-model:value="editableCopyDraft.manualIssueText" :rows="3" />
            </section>
          </div>
        </a-spin>

        <div class="editable-copy-footer">
          <a-button @click="closeEditableCopyDrawer">
            {{ editableCopyReadonly ? '关闭' : '取消' }}
          </a-button>
          <a-button
            v-if="!editableCopyReadonly"
            :loading="editableCopySaving"
            @click="saveEditableCopy({ runAfterSave: false })"
          >
            保存为测试病历
          </a-button>
          <a-button
            v-if="!editableCopyReadonly"
            type="primary"
            :loading="editableCopySaveAndRunLoading"
            :disabled="initialConfigLoading"
            @click="saveEditableCopy({ runAfterSave: true })"
          >
            保存并验证
          </a-button>
        </div>
      </div>
    </a-modal>

    <SemanticRulesBatchResultDrawer
      v-if="mountedDrawers.batch || batchResultOpen"
      :open="batchResultOpen"
      :batch-job-detail="batchJobDetail"
      :batch-job-detail-loading="batchJobLoading"
      :cancel-batch-job="handleCancelBatchJob"
      :cancel-batch-job-loading="cancelBatchJobLoading"
      :batch-job-debug-snapshot="batchJobDebugSnapshot"
      :batch-job-debug-loading="batchJobDebugLoading"
      :fetch-batch-job-debug-snapshot="fetchBatchJobDebugSnapshot"
      :close="closeBatchDrawer"
      :export-batch-job-report="handleExportBatchReport"
      :review-batch-job-result="handleReviewBatchResult"
      :review-batch-job-loading="Boolean(reviewBatchJobLoadingId)"
      :get-batch-job-status-tag-class="getBatchJobStatusTagClass"
      :get-batch-job-status-text="getBatchJobStatusText"
      :format-date-time="formatPaddedQcTaskDateTime"
    />

    <QCRecordResultComparisonDrawer
      v-if="mountedDrawers.comparison || recordResultComparisonOpen"
      :open="recordResultComparisonOpen"
      :focus="recordResultComparisonFocus"
      @close="closeRecordResultComparison"
    />

    <a-drawer
      :open="luxianAggregateOpen"
      title="泸县0609总任务"
      width="min(960px, calc(100vw - 24px))"
      placement="right"
      class="customer-sample-luxian-aggregate-drawer"
      @close="closeLuxianAggregateDrawer"
    >
      <div class="customer-sample-luxian-aggregate">
        <div class="customer-sample-luxian-aggregate-head">
          <div>
            <strong>质控结果概览</strong>
            <p>{{ luxianAggregateHeadline }}</p>
          </div>
          <a-button
            size="small"
            :loading="luxianAggregateLoading"
            @click="() => refreshLuxianAggregateJobs()"
          >
            刷新
          </a-button>
        </div>

        <div class="customer-sample-luxian-aggregate-summary">
          <div class="is-danger">
            <span>确定问题</span>
            <strong>{{ luxianAggregateResultOverview.nonCompliant }}</strong>
            <small>需要优先处理</small>
          </div>
          <div class="is-review">
            <span>建议复核</span>
            <strong>{{ luxianAggregateResultOverview.review }}</strong>
            <small>需人工确认</small>
          </div>
          <div class="is-warning">
            <span>待补资料</span>
            <strong>{{ luxianAggregateResultOverview.dataGap }}</strong>
            <small>暂不能形成结论</small>
          </div>
          <div class="is-muted">
            <span>不适用</span>
            <strong>{{ luxianAggregateResultOverview.notApplicable }}</strong>
            <small>当前病历无需核查</small>
          </div>
        </div>

        <div class="customer-sample-luxian-aggregate-list">
          <article
            v-for="item in luxianAggregateSortedJobs"
            :key="item.family.key"
            class="customer-sample-luxian-aggregate-item"
            :class="luxianAggregateItemPriorityClass(item)"
          >
            <div class="customer-sample-luxian-aggregate-main">
              <div class="customer-sample-luxian-aggregate-title">
                <strong>{{ item.family.name }}</strong>
                <em :class="getBatchJobStatusTagClass(item.status || 'queued')">
                  {{ getBatchJobStatusText(item.status || 'queued') }}
                </em>
              </div>
              <div class="customer-sample-luxian-aggregate-meta">
                <span>{{ item.family.ruleIds.length }} 个客户质控点</span>
              </div>
              <div
                v-if="luxianAggregateStatusChips(item).length"
                class="customer-sample-luxian-aggregate-chips"
              >
                <span
                  v-for="chip in luxianAggregateStatusChips(item)"
                  :key="chip.key"
                  class="customer-sample-luxian-aggregate-chip"
                  :class="chip.className"
                >
                  {{ chip.label }} {{ chip.value }}
                </span>
              </div>
              <div v-if="item.errorMessage" class="customer-sample-luxian-aggregate-error">
                {{ item.errorMessage }}
              </div>
              <div
                v-else-if="!luxianAggregateStatusChips(item).length"
                class="customer-sample-luxian-aggregate-result"
              >
                {{ luxianAggregateResultSummary(item) }}
              </div>
            </div>
            <div class="customer-sample-luxian-aggregate-actions">
              <a-button
                size="small"
                :disabled="!item.jobId"
                @click="openLuxianAggregateChildJob(item)"
              >
                {{ luxianAggregateActionText(item) }}
              </a-button>
            </div>
          </article>
        </div>
      </div>
    </a-drawer>

    <QCReviewDrawer
      v-if="mountedDrawers.review || reviewDrawerVisible"
      :visible="reviewDrawerVisible"
      :record="reviewDrawerRecord"
      @update:visible="reviewDrawerVisible = $event"
      @close="reviewDrawerVisible = false"
      @refresh="loadRecords"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch, watchEffect } from 'vue'
import { formatPaddedQcTaskDateTime } from './utils/qcTaskTime'
import { isBatchJobPollingActive } from './semantic-rules/utils/batchJobStatus'
import { deferredComponent } from './customer-sample-validation/deferredComponent'
const QCRecordCompareWorkbench = deferredComponent(() => import('./semantic-rules/components/QCRecordCompareWorkbench.vue'))
import MedicalOrderFilterBar from './customer-sample-validation/MedicalOrderFilterBar.vue'
import HospitalLoading from '@/components/qc/HospitalLoading.vue'
import { useMinimumLoading } from '@/composables/useMinimumLoading'
import RecordViewCloseIcon from './components/RecordViewCloseIcon.vue'
import ReadonlyMedicalRecordHeader from './components/ReadonlyMedicalRecordHeader.vue'
import { useCustomerSampleValidationController } from './customer-sample-validation/useCustomerSampleValidationController'

const {
  initialConfigLoading,
  activeRecord,
  addEditableCopyDocument,
  addEditableCopyOrderDocument,
  allLuxianRuleIds,
  backlogBucketCardClass,
  backlogBucketTagClass,
  batchJobDetail,
  batchJobDebugLoading,
  batchJobDebugSnapshot,
  batchJobLoading,
  batchResultOpen,
  bundleStatusHint,
  bundleStatusLabel,
  cancelBatchJobLoading,
  clearLuxianRuleScope,
  clearSelectedRecords,
  closeBatchDrawer,
  closeCustomerSampleGuide,
  closeEditableCopyDrawer,
  closeLuxianAggregateDrawer,
  closeRecordResultComparison,
  Compass,
  confirmCancelBatchJob,
  confirmDeletePool,
  coverageLabel,
  coverageOptions,
  currentCustomerSampleGuideStep,
  currentQcTask,
  currentQcTaskLoading,
  currentScopeDescription,
  CUSTOMER_TEST_POOL_ID,
  customerSampleGuideOpen,
  customerSampleGuideStepIndex,
  customerSampleGuideSteps,
  customerSampleGuideTargetClass,
  CustomerSampleQcTaskStatusBar,
  customerSampleTourCardStyle,
  deletingPoolIds,
  detailOpen,
  dismissSyncStatusBar,
  editableCopyActiveDocument,
  editableCopyDocumentFilter,
  editableCopyDocumentGroups,
  editableCopyDocumentQuery,
  editableCopyDraft,
  editableCopyEnabledDocumentCount,
  editableCopyFilteredDocuments,
  editableCopyLoading,
  editableCopyNewDocumentType,
  editableCopyOpen,
  editableCopyOrderTypeFilter,
  editableCopyOrderFilters,
  editableCopyOrderRows,
  editableCopyScopedOrderRows,
  editableCopyReadonly,
  editableCopySaveAndRunLoading,
  editableCopySaving,
  editableCopySourceRecord,
  editableCopyVisibleOrderRows,
  exactReviewAcceptance,
  exactReviewBacklogBuckets,
  exactReviewError,
  exactReviewLoading,
  exactReviewReasonTags,
  exactReviewStatusCards,
  expandedLuxianRuleFamilyKeys,
  fetchBatchJobDebugSnapshot,
  FilePlus2,
  filters,
  formatEditableCopyDocumentMeta,
  formatEditableCopyOrderGroupMeta,
  getBatchJobStatusTagClass,
  getBatchJobStatusText,
  goToCustomerSampleGuideStep,
  goToNextCustomerSampleGuideStep,
  goToPreviousCustomerSampleGuideStep,
  handleCancelBatchJob,
  handleDownloadTemplate,
  handleExportBatchReport,
  handleExportCurrentTask,
  handleHospitalizationSync,
  handleImportFileSelect,
  handleImportPool,
  handleInternalDiagnosticChange,
  handleMoreActionKey,
  handlePoolChange,
  handlePoolManagementSearch,
  handleRetrySync,
  handleReviewBatchResult,
  handleReviewCurrentTask,
  handleRuleSetChange,
  handleRunPool,
  handleSyncPoolRecords,
  History,
  hospitalizationPreviewMetrics,
  hospitalizationScopeNeedsDischargeRange,
  hospitalizationScopeOptions,
  hospitalizationSyncCanSubmit,
  hospitalizationSyncDepartmentOptions,
  hospitalizationSyncForm,
  hospitalizationSyncModalOpen,
  hospitalizationSyncOkText,
  hospitalizationSyncPreview,
  hospitalizationSyncPreviewError,
  hospitalizationSyncPreviewLoading,
  hospitalizationSyncSubmitting,
  importFileList,
  importForm,
  importingPool,
  importModalOpen,
  importWorkflow,
  importWorkflowSteps,
  InboxOutlined,
  internalDiagnosticKeys,
  isAllLuxianRulesSelected,
  isEditableCopyDocumentGroupExpanded,
  isEditableOrderDocument,
  isLastCustomerSampleGuideStep,
  isLuxian0609Mode,
  isSyncedOnlyValidationMode,
  itemColumns,
  itemLoading,
  loadManagedPools,
  loadRecords,
  luxianAggregateActionText,
  luxianAggregateHeadline,
  luxianAggregateItemPriorityClass,
  luxianAggregateLoading,
  luxianAggregateOpen,
  luxianAggregateResultOverview,
  luxianAggregateResultSummary,
  luxianAggregateSortedJobs,
  luxianAggregateStatusChips,
  luxianRuleFamilies,
  LuxianRuleScopePanel,
  luxianScopeHelperText,
  luxianScopeModeText,
  mainRuleSets,
  managedPools,
  matchLoading,
  matchStatusHint,
  matchStatusLabel,
  matchStatusOptions,
  openBatchJob,
  openCurrentTaskResult,
  openCustomerSampleGuide,
  openLuxianAggregateChildJob,
  openPoolManagement,
  openSyncDetailDrawer,
  openTaskHistoryPage,
  openTestRecordDrawer,
  paginationConfig,
  parallelOptions,
  poolDeletionDisabled,
  poolJobStatusLabel,
  poolLoading,
  poolManagementLoading,
  poolManagementOpen,
  poolManagementPagination,
  poolManagementQuery,
  poolOptions,
  QCRecordResultComparisonDrawer,
  QCReviewDrawer,
  ReadonlyMedicalDocumentContent,
  recordResultComparisonFocus,
  recordResultComparisonOpen,
  records,
  recordScopeHint,
  refreshHospitalizationScopePreview,
  refreshLuxianAggregateJobs,
  removeEditableCopyDocument,
  resetFilters,
  resetImportForm,
  resolveEditableOrderTypeLabel,
  resolveRecordResultFocus,
  reviewBatchJobLoadingId,
  reviewDrawerRecord,
  reviewDrawerVisible,
  rowSelection,
  ruleSetCardClass,
  ruleSetDirectoryFallbackActive,
  ruleSetScopeLabel,
  runButtonDisabled,
  runButtonText,
  runLoading,
  runOptions,
  runPoolMatch,
  saveEditableCopy,
  scrollToLuxianScope,
  selectEditableCopyDocument,
  selectEditableCopyOrderGroup,
  selectedLuxianCustomerRuleIds,
  selectedLuxianFamilyCount,
  selectedPool,
  selectedPoolId,
  selectedRecordStats,
  selectedRuleSet,
  selectedRuleSetCoverageChips,
  selectedRuleSetRuleCountText,
  selectedRunScopeSummary,
  selectLuxianRuleFamily,
  SemanticRulesBatchResultDrawer,
  Settings2,
  showSyncStatusBar,
  startSyntheticCaseFromGuide,
  summarizeRecordScope,
  summaryCards,
  syncCustomerStepText,
  syncDetailDrawerOpen,
  syncHospitalizationSummary,
  syncJobDetail,
  syncJobStatusColor,
  syncJobStatusText,
  syncLoading,
  syncProgress,
  syncRecordProgress,
  syncResolvedStats,
  syncResultNotice,
  syncStatusBar,
  tableEmptyText,
  testRecordDocumentTypeOptions,
  toggleAllLuxianRuleFamilies,
  toggleEditableCopyDocumentGroup,
  toggleInternalDiagnostic,
  toggleLuxianRule,
  toggleLuxianRuleFamilyExpanded,
  Trash2,
  workflowSteps,
} = useCustomerSampleValidationController()

const showReadonlyRecordLoading = useMinimumLoading(
  () => editableCopyLoading.value,
  () => editableCopyOpen.value && editableCopyReadonly.value,
)

// 首次打开才挂载；关闭后保留组件，维持原抽屉内的页签和筛选状态。
const mountedDrawers = reactive({ batch: false, comparison: false, review: false })
watchEffect(() => {
  if (batchResultOpen.value) mountedDrawers.batch = true
  if (recordResultComparisonOpen.value) mountedDrawers.comparison = true
  if (reviewDrawerVisible.value) mountedDrawers.review = true
})

const hasWorkDock = computed(
  () =>
    Boolean(currentQcTask.value) || selectedRecordStats.value.selectedCount > 0 || runLoading.value,
)

const isCurrentQcTaskRunning = computed(() => isBatchJobPollingActive(currentQcTask.value))

const canCollapseWorkDockTask = computed(
  () =>
    Boolean(currentQcTask.value) &&
    !isCurrentQcTaskRunning.value &&
    selectedRecordStats.value.selectedCount === 0 &&
    !runLoading.value,
)

// 历史终态任务默认以单行紧凑底栏呈现，避免挤压病历池空间；新任务运行或勾选病历时自动展开。
const workDockTaskCompact = ref(true)

const isWorkDockTaskCompact = computed(
  () => canCollapseWorkDockTask.value && workDockTaskCompact.value,
)

function toggleWorkDockTaskCompact() {
  if (!canCollapseWorkDockTask.value) return
  workDockTaskCompact.value = !workDockTaskCompact.value
}

watch(
  [isCurrentQcTaskRunning, () => selectedRecordStats.value.selectedCount, runLoading],
  ([running, selectedCount, loading]) => {
    if (running || selectedCount > 0 || loading) {
      workDockTaskCompact.value = false
    }
  },
  { immediate: true },
)

watch(selectedPoolId, () => {
  if (
    !isCurrentQcTaskRunning.value &&
    selectedRecordStats.value.selectedCount === 0 &&
    !runLoading.value
  ) {
    workDockTaskCompact.value = true
  }
})
</script>

<style scoped src="./CustomerSampleValidationView.css"></style>

<style scoped src="./styles/customer-sample-refined.css"></style>
