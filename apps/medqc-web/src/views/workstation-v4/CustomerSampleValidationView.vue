<template>
  <main class="customer-sample-page relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
    <div
      class="customer-sample-scroll custom-scrollbar flex-1 overflow-y-auto px-4 pb-5 pt-4 xl:px-5"
      :class="{ 'has-selection-run-bar': selectedRecordStats.selectedCount > 0 }"
    >
      <div class="customer-sample-container mx-auto w-full max-w-[1440px] space-y-4">
        <section class="customer-sample-console">
          <div class="customer-sample-toolbar">
            <div class="customer-sample-page-title">
              <span>客户样本验证</span>
              <small>规则集质控</small>
            </div>

            <div class="customer-sample-toolbar-actions">
              <a-button
                class="customer-sample-guide-action !rounded-lg"
                data-customer-guide="guide-entry"
                @click="openCustomerSampleGuide"
              >
                <Compass :size="15" />
                功能导览
              </a-button>
              <a-button
                class="customer-sample-create-action !rounded-lg"
                data-customer-guide="create-record"
                :class="customerSampleGuideTargetClass('create-record')"
                @click="openTestRecordDrawer"
              >
                <FilePlus2 :size="15" />
                创建测试病历
              </a-button>
              <a-button
                type="primary"
                class="!rounded-lg"
                data-customer-guide="run-validation"
                :class="customerSampleGuideTargetClass('run-validation')"
                :disabled="runButtonDisabled"
                :loading="runLoading"
                @click="handleRunPool"
              >
                {{ runButtonText }}
              </a-button>
              <a-button
                class="customer-sample-task-history-action !rounded-lg"
                @click="openTaskHistoryDrawer"
              >
                <span class="customer-sample-task-history-icon">
                  <History :size="15" />
                </span>
                <span class="customer-sample-task-history-label">查看质控记录</span>
                <span
                  v-if="taskHistoryTotal > 0"
                  class="customer-sample-task-history-count"
                >
                  {{ taskHistoryTotal > 99 ? '99+' : taskHistoryTotal }}
                </span>
              </a-button>
              <a-dropdown :trigger="['click']">
                <a-button class="!rounded-lg">
                  更多操作
                </a-button>
                <template #overlay>
                  <a-menu>
                    <a-menu-item @click="handleMoreActionKey('refresh')">
                      刷新样本池
                    </a-menu-item>
                    <a-menu-item
                      :disabled="!selectedPoolId || syncLoading"
                      @click="handleMoreActionKey('sync')"
                    >
                      同步样本病历
                    </a-menu-item>
                    <a-menu-item
                      :disabled="!selectedPoolId || matchLoading"
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
                    <a-sub-menu
                      key="luxian-report"
                      title="导出报告"
                    >
                      <a-menu-item @click="handleMoreActionKey('export-luxian-md')">
                        Markdown 评估报告
                      </a-menu-item>
                      <a-menu-item @click="handleMoreActionKey('export-luxian-csv')">
                        CSV 指标明细
                      </a-menu-item>
                    </a-sub-menu>
                    <a-menu-divider />
                    <a-sub-menu
                      key="developer-admin"
                      title="开发/管理员"
                    >
                      <a-menu-item @click="handleMoreActionKey('import')">
                        导入模板
                      </a-menu-item>
                      <a-menu-item @click="handleMoreActionKey('export-luxian-json')">
                        JSON 原始结果
                      </a-menu-item>
                      <a-menu-divider />
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

          <div class="customer-sample-command-bar">
            <div
              class="customer-sample-field"
              data-customer-guide="sample-pool"
              :class="customerSampleGuideTargetClass('sample-pool')"
            >
              <div class="customer-sample-field-label">
                当前样本池
              </div>
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
              <div class="customer-sample-field-label">
                验证规则集
              </div>
              <div class="customer-sample-rule-switcher">
                <button
                  v-for="ruleSet in mainRuleSets"
                  :key="ruleSet.rule_set_key"
                  type="button"
                  class="customer-sample-rule-card"
                  :data-rule-set-key="ruleSet.rule_set_key"
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
                <span class="customer-sample-meta-chip">场景 {{ ruleSetScopeLabel(selectedRuleSet?.scope) }}</span>
              </div>
            </div>
            <div class="customer-sample-rule-summary">
              <span class="customer-sample-coverage-chip border-sky-200 bg-sky-50 text-sky-700">
                规则数 {{ selectedRuleSetRuleCountText }}
              </span>
              <button
                type="button"
                class="customer-sample-internal-toggle"
                @click="openTaskHistoryDrawer"
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
                <div class="mt-2 grid gap-2 text-[13px] leading-6 text-slate-600 md:grid-cols-3">
                  <div>
                    已导入
                    <strong class="text-slate-900">{{ importWorkflow.importedRows }}</strong> 条 ID
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
                  class="!rounded-lg"
                  @click="runPoolMatch({ source: 'workflow' })"
                >
                  重新匹配
                </a-button>
                <a-button
                  type="primary"
                  class="!rounded-lg"
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

          <section
            v-if="isLuxian0609Mode"
            class="customer-sample-luxian-scope"
            data-customer-guide="lx0609-scope"
            :class="customerSampleGuideTargetClass('lx0609-scope')"
          >
            <div class="customer-sample-luxian-scope-head">
              <div>
                <div class="customer-sample-luxian-scope-title">
                  泸县0609质控点范围
                </div>
                <p>未勾选时按完整 0609 规则集运行；勾选后仅验证选中的 LX0609 质控点。</p>
              </div>
              <div class="customer-sample-luxian-scope-actions">
                <span>{{ luxianScopeModeText }}</span>
                <a-button
                  size="small"
                  class="!rounded-lg"
                  @click="toggleAllLuxianRuleFamilies"
                >
                  {{
                    isAllLuxianRulesSelected
                      ? '取消全部勾选'
                      : `勾选全部${luxianRuleFamilies.length}个质控族`
                  }}
                </a-button>
                <a-button
                  v-if="selectedLuxianCustomerRuleIds.length && !isAllLuxianRulesSelected"
                  size="small"
                  class="!rounded-lg"
                  @click="clearLuxianRuleScope"
                >
                  清空勾选
                </a-button>
              </div>
            </div>
            <div class="customer-sample-luxian-rule-groups">
              <div
                v-for="family in luxianRuleFamilies"
                :key="family.key"
                class="customer-sample-luxian-rule-group"
              >
                <div class="customer-sample-luxian-rule-group-head">
                  <div>
                    <div class="customer-sample-luxian-rule-group-title">
                      <strong>{{ family.name }}</strong>
                      <span>{{ family.rules.length }} 条</span>
                    </div>
                    <small>{{ family.description }}</small>
                  </div>
                  <button
                    type="button"
                    @click="selectLuxianRuleFamily(family.ruleIds)"
                  >
                    {{ isLuxianRuleFamilySelected(family.ruleIds) ? '取消本组' : '选择本组' }}
                  </button>
                </div>
                <div class="customer-sample-luxian-rule-options">
                  <label
                    v-for="rule in visibleLuxianFamilyRules(family)"
                    :key="rule.ruleId"
                    class="customer-sample-luxian-rule-option"
                    :class="{ 'is-selected': selectedLuxianCustomerRuleIds.includes(rule.ruleId) }"
                    :title="`${rule.ruleId} ${rule.name}`"
                  >
                    <input
                      type="checkbox"
                      class="luxian-rule-checkbox"
                      :value="rule.ruleId"
                      :checked="selectedLuxianCustomerRuleIds.includes(rule.ruleId)"
                      @change="toggleLuxianRule(rule.ruleId)"
                    >
                    <span>{{ rule.ruleId }}</span>
                    <em>{{ rule.name }}</em>
                  </label>
                </div>
                <button
                  v-if="hiddenLuxianFamilyRuleCount(family) > 0"
                  type="button"
                  class="customer-sample-luxian-rule-expand"
                  @click="toggleLuxianRuleFamilyExpanded(family.key)"
                >
                  {{
                    isLuxianRuleFamilyExpanded(family.key)
                      ? '收起'
                      : `展开剩余 ${hiddenLuxianFamilyRuleCount(family)} 条`
                  }}
                </button>
              </div>
            </div>
          </section>
        </section>

        <section class="customer-sample-diagnostic-panel">
          <a-collapse
            v-model:active-key="internalDiagnosticKeys"
            ghost
            class="customer-sample-internal-collapse"
            @change="handleInternalDiagnosticChange"
          >
            <a-collapse-panel
              key="sheet2"
              header="内部验收诊断"
            >
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
                <div
                  v-if="exactReviewAcceptance"
                  class="space-y-4 px-5 py-4"
                >
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
                    <div class="font-semibold text-amber-950">
                      blocked_with_reason 口径
                    </div>
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

                <div
                  v-else
                  class="px-5 py-6 text-[13px] leading-6 text-rose-600"
                >
                  {{ exactReviewError || '暂未读取到 Sheet2 精确复核验收包。' }}
                </div>
              </a-spin>
            </a-collapse-panel>
          </a-collapse>
        </section>

        <section
          v-if="syncJobDetail"
          class="rounded-[24px] border border-slate-200/80 bg-white shadow-[0_14px_34px_rgba(148,163,184,0.12)]"
        >
          <div class="border-b border-slate-200/80 px-5 py-4">
            <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
              <div class="min-w-0">
                <div class="text-[17px] font-semibold text-slate-900">
                  样本病历同步进度
                </div>
                <div class="mt-1 text-[13px] leading-6 text-slate-500">
                  按样本池定向从源库拉取真实病历到本地 PG，并刷新 running bundle。
                </div>
              </div>
              <a-tag :color="syncJobStatusColor(syncJobDetail.status)">
                {{ syncJobStatusText(syncJobDetail.status) }}
              </a-tag>
            </div>
          </div>
          <div
            v-if="syncResultNotice"
            class="mx-5 mt-4 rounded-2xl border px-4 py-3 text-[13px] leading-6"
            :class="syncResultNotice.className"
          >
            <div class="font-semibold">
              {{ syncResultNotice.title }}
            </div>
            <div class="mt-1">
              {{ syncResultNotice.description }}
            </div>
          </div>
          <div class="grid gap-4 px-5 py-4 md:grid-cols-2 xl:grid-cols-4">
            <div class="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                病历进度
              </div>
              <div class="mt-2 text-[26px] font-semibold leading-none text-slate-900">
                已同步 {{ syncRecordProgress.completed }} / {{ syncRecordProgress.total }} 份
              </div>
              <div class="mt-2 text-[12px] leading-5 text-slate-500">
                按病历主记录已写入本地计算。
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                文书就绪
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncRecordProgress.ready }} 份
              </div>
              <div
                class="mt-2 text-[12px] leading-5"
                :class="
                  syncRecordProgress.completed > syncRecordProgress.ready
                    ? 'text-amber-700'
                    : 'text-slate-500'
                "
              >
                {{ syncRecordProgress.readyHint }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                源库匹配
              </div>
              <div class="mt-2 text-[20px] font-semibold leading-none text-slate-900">
                {{ syncResolvedStats.matched }} 份匹配
              </div>
              <div class="mt-2 text-[12px] leading-5 text-slate-500">
                待确认 {{ syncResolvedStats.ambiguous }} 份，未找到
                {{ syncResolvedStats.unmatched }} 份。
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                表/行进度
              </div>
              <div class="mt-2 text-[20px] font-semibold leading-none text-slate-900">
                {{ syncProgress.processed_tables ?? 0 }}/{{ syncProgress.total_tables ?? 0 }} 表
              </div>
              <div class="mt-2 text-[12px] leading-5 text-slate-500">
                拉取 {{ syncProgress.total_rows_pulled ?? 0 }} 行，写入
                {{ syncProgress.total_rows_upserted ?? 0 }} 行。
              </div>
            </div>
          </div>
          <div class="space-y-3 px-5 pb-5">
            <div
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] leading-6 text-slate-600"
            >
              <div class="font-medium text-slate-700">
                {{ syncProgress.step_label || '等待同步开始' }}
              </div>
              <div class="mt-1">
                当前表：{{ syncProgress.current_table || '—' }}；剩余表数：{{
                  syncProgress.remaining_tables ?? 0
                }}
              </div>
              <div class="mt-1">
                已同步 {{ syncRecordProgress.completed }} /
                {{ syncRecordProgress.total }} 份病历；文书就绪 {{ syncRecordProgress.ready }} 份。
                明细文书、医嘱、检查检验等仍以表进度和文书就绪状态为准。
              </div>
              <div
                v-if="syncRecordProgress.missingMr > 0"
                class="mt-1 text-amber-700"
              >
                有 {{ syncRecordProgress.missingMr }} 份病历尚未写入主记录，暂时不会出现在病历池中。
              </div>
              <div
                v-if="syncJobDetail.error_message"
                class="mt-2 text-rose-600"
              >
                {{ syncJobDetail.error_message }}
              </div>
            </div>
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
                  <div class="text-[18px] font-semibold text-slate-900">
                    病历池
                  </div>
                  <div class="customer-sample-inline-metrics">
                    <span
                      v-for="item in summaryCards"
                      :key="item.label"
                    >
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
                    class="w-[88px] customer-sample-toolbar-select"
                    size="middle"
                    :options="parallelOptions"
                  />
                </div>
                <a-button
                  type="primary"
                  class="!rounded-full"
                  @click="loadRecords()"
                >
                  查询
                </a-button>
                <a-button
                  class="!rounded-full"
                  @click="resetFilters"
                >
                  重置
                </a-button>
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

    <div
      v-if="selectedRecordStats.selectedCount > 0"
      class="customer-sample-selection-run-bar"
      data-testid="customer-sample-selection-run-bar"
      aria-live="polite"
    >
      <div class="customer-sample-selection-run-summary">
        <strong>已选 {{ selectedRecordStats.selectedCount }} 份病历</strong>
        <span>
          可质控 {{ selectedRecordStats.runnableCount }} 份
          <template v-if="selectedRecordStats.skippedCount > 0">
            ，{{ selectedRecordStats.skippedCount }} 份将自动跳过
          </template>
        </span>
      </div>
      <div class="customer-sample-selection-run-actions">
        <a-button
          class="!rounded-lg"
          @click="clearSelectedRecords"
        >
          取消选择
        </a-button>
        <a-button
          type="primary"
          class="!rounded-lg"
          :disabled="runButtonDisabled"
          :loading="runLoading"
          @click="handleRunPool"
        >
          {{ runButtonActionText }}
        </a-button>
      </div>
    </div>

    <div
      v-if="customerSampleGuideOpen"
      class="customer-sample-tour-layer"
    >
      <div class="customer-sample-tour-scrim" />
      <div
        class="customer-sample-tour-card"
        :style="customerSampleTourCardStyle"
      >
        <div class="customer-sample-tour-kicker">
          客户演示主流程
        </div>
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
          <a-button
            class="customer-sample-guide-dismiss !rounded-lg"
            @click="closeCustomerSampleGuide"
          >
            跳过
          </a-button>
          <a-button
            class="customer-sample-guide-start !rounded-lg"
            @click="startSyntheticCaseFromGuide"
          >
            创建测试病历
          </a-button>
          <a-button
            v-if="customerSampleGuideStepIndex > 0"
            class="!rounded-lg"
            @click="goToPreviousCustomerSampleGuideStep"
          >
            上一步
          </a-button>
          <a-button
            type="primary"
            class="customer-sample-guide-next !rounded-lg"
            @click="goToNextCustomerSampleGuideStep"
          >
            {{ isLastCustomerSampleGuideStep ? '完成导览' : '下一步' }}
          </a-button>
        </div>
      </div>
    </div>

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
          <div class="mb-2 text-[13px] font-medium text-slate-700">
            样本池名称
          </div>
          <a-input
            v-model:value="importForm.poolName"
            placeholder="例如：手工问题样本池-第二轮"
            :maxlength="60"
          />
        </div>
        <div>
          <div class="mb-2 text-[13px] font-medium text-slate-700">
            备注
          </div>
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
            <a-button
              type="link"
              class="!px-0"
              @click="handleDownloadTemplate"
            >
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
            <p class="ant-upload-text">
              点击或拖拽上传 Excel 模板
            </p>
            <p class="ant-upload-hint">
              支持 .xls / .xlsx，默认读取第一个工作表。
            </p>
            <p class="mt-2 text-[12px] text-slate-400">
              优先填写就诊ID，可补充住院流水号、病案号和患者姓名。
            </p>
          </a-upload-dragger>
        </div>
      </div>
    </a-modal>

    <a-drawer
      :open="detailOpen"
      width="720"
      title="病历关联问题"
      @close="detailOpen = false"
    >
      <div
        v-if="activeRecord"
        class="space-y-5"
      >
        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            病历概况
          </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">科室：</span>{{ activeRecord.department || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">患者：</span>{{ activeRecord.patient_name || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">住院号：</span>{{ activeRecord.mr_no || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">visit_id：</span>{{ activeRecord.matched_visit_id || '-' }}
            </div>
          </div>
        </a-card>

        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            识别范围
          </template>
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

        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            病历关联
          </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">关联结果：</span>{{ matchStatusLabel(activeRecord.match_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">下一步：</span>{{ matchStatusHint(activeRecord.match_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">visit_id：</span>{{ activeRecord.matched_visit_id || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">同步状态：</span>{{ activeRecord.sync_status || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">文书就绪：</span>{{ bundleStatusLabel(activeRecord.bundle_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">处理建议：</span>{{ bundleStatusHint(activeRecord.bundle_status) }}
            </div>
          </div>
        </a-card>

        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            关联人工问题
          </template>
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
      :width="1120"
      :footer="null"
      :destroy-on-close="false"
      centered
      class="editable-copy-workstation-modal"
      @cancel="closeEditableCopyDrawer"
    >
      <div class="editable-copy-drawer">
        <header class="editable-copy-hero">
          <div>
            <div class="editable-copy-eyebrow">
              客户样本验证 / {{ editableCopyReadonly ? '查看病历' : '编辑副本' }}
            </div>
            <h2>{{ editableCopyReadonly ? '查看病历文书' : '创建可编辑测试病历副本' }}</h2>
            <p>
              {{
                editableCopyReadonly
                  ? '按文书目录查看已同步病历原文；当前模式只读，不会修改源病历。'
                  : '从已同步病历读取文书，复制成新的客户自建测试病历；本页所有修改只写入新副本。'
              }}
            </p>
          </div>
          <div class="editable-copy-source-card">
            <span>来源病历</span>
            <strong>{{ editableCopySourceRecord?.patient_name || '-' }}</strong>
            <em>{{ editableCopySourceRecord?.department || '-' }}</em>
          </div>
        </header>

        <div class="editable-copy-notice">
          <div class="editable-copy-notice-title">
            原始同步病历保持只读
          </div>
          <div>
            {{
              editableCopyReadonly
                ? '这里展示的是已同步病历文书原文，只用于浏览和定位，不提供编辑、新增或删除文书。'
                : '这里会基于已同步病历创建一份新的客户自建测试病历。修改只保存到新副本，不会写回客户源库或原样本池。'
            }}
          </div>
        </div>

        <a-spin :spinning="editableCopyLoading">
          <div
            v-if="editableCopyDraft"
            class="editable-copy-content"
          >
            <section class="editable-copy-section">
              <h3>{{ editableCopyReadonly ? '病历信息' : '副本信息' }}</h3>
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
                <label class="editable-copy-form-wide">
                  <span>主要诊断</span>
                  <a-input
                    v-model:value="editableCopyDraft.mainDiagnosis"
                    :readonly="editableCopyReadonly"
                  />
                </label>
              </div>
            </section>

            <section class="editable-copy-section editable-copy-document-workbench-section">
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
              <div
                v-if="!editableCopyReadonly"
                class="editable-copy-document-toolbar"
              >
                <a-select
                  v-model:value="editableCopyNewDocumentType"
                  :options="testRecordDocumentTypeOptions"
                  class="editable-copy-document-type-select"
                />
                <a-button @click="addEditableCopyDocument()">
                  新增文书
                </a-button>
                <a-button @click="addEditableCopyOrderDocument()">
                  新增医嘱
                </a-button>
              </div>

              <div class="editable-copy-document-workbench">
                <aside class="editable-copy-document-directory">
                  <div class="editable-copy-document-directory-head">
                    <strong>文书目录</strong>
                    <span>{{ editableCopyFilteredDocuments.length }} /
                      {{ editableCopyDraft.documents.length }}</span>
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
                    <template
                      v-for="group in editableCopyDocumentGroups"
                      :key="group.key"
                    >
                      <div class="editable-copy-document-group-title">
                        <span>
                          <i v-if="editableCopyReadonly" />
                          {{ group.label }}
                        </span>
                        <em>{{ group.documents.length }}</em>
                      </div>
                      <button
                        v-if="group.key === 'order'"
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
                      <template v-else>
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

                <article
                  v-if="editableCopyActiveDocument"
                  class="editable-copy-document-editor"
                >
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
                      <span
                        v-if="editableCopyReadonly"
                        class="editable-copy-readonly-pill"
                      >
                        只读原文
                      </span>
                      <label
                        v-else
                        class="editable-copy-document-toggle"
                      >
                        <input
                          v-model="editableCopyActiveDocument.enabled"
                          type="checkbox"
                        >
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
                    <div class="editable-copy-order-table-wrap">
                      <table class="editable-copy-order-table">
                        <thead>
                          <tr>
                            <th>开始时间</th>
                            <th>医嘱类型</th>
                            <th>医嘱项目</th>
                            <th>停止时间</th>
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
                            <td>{{ order.stopTime }}</td>
                            <td>{{ order.status }}</td>
                          </tr>
                          <tr v-if="!editableCopyVisibleOrderRows.length">
                            <td
                              colspan="5"
                              class="editable-copy-order-empty"
                            >
                              暂无{{
                                editableCopyOrderTypeFilter === 'long' ? '长期医嘱' : '临时医嘱'
                              }}
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
                  <a-textarea
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

            <section
              v-if="!editableCopyReadonly"
              class="editable-copy-section"
            >
              <h3>验证说明</h3>
              <a-textarea
                v-model:value="editableCopyDraft.manualIssueText"
                :rows="3"
              />
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
            @click="saveEditableCopy({ runAfterSave: true })"
          >
            保存并验证
          </a-button>
        </div>
      </div>
    </a-modal>

    <SemanticRulesBatchResultDrawer
      :open="batchResultOpen"
      :batch-job-detail="batchJobDetail"
      :batch-job-detail-loading="batchJobLoading"
      :cancel-batch-job="handleCancelBatchJob"
      :cancel-batch-job-loading="cancelBatchJobLoading"
      :batch-job-debug-snapshot="null"
      :batch-job-debug-loading="false"
      :fetch-batch-job-debug-snapshot="undefined"
      :focus-visit-id="batchResultFocusRecord?.visitId"
      :focus-record-id="batchResultFocusRecord?.recordId"
      :focus-record-label="batchResultFocusRecord?.label"
      :close="closeBatchDrawer"
      :export-batch-job-report="handleExportBatchReport"
      :get-batch-job-status-tag-class="getBatchJobStatusTagClass"
      :get-batch-job-status-text="getBatchJobStatusText"
      :format-date-time="formatDateTime"
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
            <strong>按 7 个质控族并发执行</strong>
            <p>前端展示为一个总任务，后端按质控族拆成子任务执行；每个子任务可单独查看结果。</p>
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
          <div>
            <span>总进度</span>
            <strong>
              已完成 {{ luxianAggregateSummary.completed }} /
              {{ luxianAggregateSummary.total }} 个质控族
            </strong>
          </div>
          <div>
            <span>运行中</span>
            <strong>{{ luxianAggregateSummary.running }} 个</strong>
          </div>
          <div>
            <span>异常</span>
            <strong>{{ luxianAggregateSummary.failed }} 个</strong>
          </div>
        </div>

        <div class="customer-sample-luxian-aggregate-list">
          <article
            v-for="item in luxianAggregateJobs"
            :key="item.family.key"
            class="customer-sample-luxian-aggregate-item"
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
                <span :title="item.jobId ? `子任务编号：${item.jobId}` : '任务创建中'">
                  {{ item.jobId ? '子任务已生成' : '任务创建中' }}
                </span>
              </div>
              <div
                v-if="item.errorMessage"
                class="customer-sample-luxian-aggregate-error"
              >
                {{ item.errorMessage }}
              </div>
              <div
                v-else
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
                查看结果
              </a-button>
            </div>
          </article>
        </div>
      </div>
    </a-drawer>

    <a-drawer
      :open="taskHistoryOpen"
      title="质控记录"
      width="min(920px, calc(100vw - 24px))"
      placement="right"
      class="customer-sample-task-history-drawer"
      @close="closeTaskHistoryDrawer"
    >
      <div class="customer-sample-task-history">
        <div class="customer-sample-task-history-head">
          <div>
            <strong>历史质控任务</strong>
            <p>按发起时间倒序展示最近任务，可直接查看结果抽屉。</p>
          </div>
          <a-button
            size="small"
            :loading="taskHistoryLoading"
            @click="loadTaskHistory"
          >
            刷新
          </a-button>
        </div>

        <a-spin :spinning="taskHistoryLoading">
          <div
            v-if="taskHistoryJobs.length === 0"
            class="customer-sample-task-history-empty"
          >
            暂无质控记录。发起验证后，最近任务会显示在这里。
          </div>

          <div
            v-else
            class="customer-sample-task-history-list"
          >
            <article
              v-for="job in taskHistoryJobs"
              :key="job.id"
              class="customer-sample-task-history-item"
            >
              <div class="customer-sample-task-history-item-main">
                <div class="customer-sample-task-history-title">
                  <span>{{ taskHistoryRuleSetText(job) }}</span>
                  <em :class="getBatchJobStatusTagClass(job.status)">
                    {{ getBatchJobStatusText(job.status) }}
                  </em>
                </div>
                <div class="customer-sample-task-history-meta">
                  <span>{{ formatDateTime(job.created_at) || '未返回时间' }}</span>
                  <span>{{ taskHistoryScopeText(job) }}</span>
                  <span>{{ taskHistoryRecordText(job) }}</span>
                </div>
                <div class="customer-sample-task-history-overview">
                  <strong>{{ taskHistoryOverviewText(job) }}</strong>
                  <span>{{ taskHistorySecondaryText(job) }}</span>
                  <span
                    v-if="taskHistoryIssueSummaryText(job)"
                    class="customer-sample-task-history-issue-line"
                  >
                    {{ taskHistoryIssueSummaryText(job) }}
                  </span>
                </div>
                <div
                  v-if="taskHistoryStatusChips(job).length"
                  class="customer-sample-task-history-status-grid"
                >
                  <span
                    v-for="chip in taskHistoryStatusChips(job)"
                    :key="chip.key"
                    :class="chip.className"
                  >
                    <em>{{ chip.label }}</em>
                    <strong>{{ chip.value }}</strong>
                  </span>
                </div>
              </div>
              <div class="customer-sample-task-history-actions">
                <a-button
                  size="small"
                  @click="openTaskHistoryJob(job)"
                >
                  查看结果
                </a-button>
                <a-button
                  v-if="job.status === 'completed'"
                  size="small"
                  @click="handleExportTaskHistoryJob(job)"
                >
                  导出HTML
                </a-button>
              </div>
            </article>
          </div>
        </a-spin>
      </div>
    </a-drawer>

    <QCReviewDrawer
      :visible="reviewDrawerVisible"
      :record="reviewDrawerRecord"
      @update:visible="reviewDrawerVisible = $event"
      @close="reviewDrawerVisible = false"
      @refresh="loadRecords"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onMounted, onUnmounted, ref } from 'vue'
import type { CSSProperties } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { UploadFile, UploadProps } from 'ant-design-vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { Compass, FilePlus2, History } from 'lucide-vue-next'
import type {
  ManualSamplePool,
  ManualSamplePoolRecord,
  ManualTestRecordCreateRequest,
  EditableMedicalRecordDocument,
  ManualSampleValidationMode,
  ManualSampleValidationRuleSet,
  ManualSamplePoolRunResult,
  ManualLuxian0609RuleCatalogItem,
  ManualSamplePoolSyncJob,
  Sheet2ExactReviewAcceptancePackage,
} from './customer-sample-validation/types'
import {
  createManualTestMedicalRecord,
  exportLuxian0609EvaluationReport,
  getEditableMedicalRecordDocuments,
  getSheet2ExactReviewAcceptancePackage,
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  importManualSamplePoolByUpload,
  listLuxian0609CustomerRules,
  listManualSampleValidationRuleSets,
  listManualSamplePools,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
} from '@/services/manual-case-sample-service'
import { syntheticCaseRuleFamilies } from './customer-sample-validation/syntheticCaseTemplates'
import { testRecordDocumentTypeOptions } from './customer-sample-validation/syntheticCaseBuilder'
import {
  cancelSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
  listSichuanWorkspaceBatchJobs,
} from '@/services/sichuan-rule-workspace-service'
import QCReviewDrawer from '@/components/qc/QCReviewDrawer.vue'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import type {
  SichuanBatchJob,
  SichuanBatchIssueItem,
  SichuanBatchJobStatus,
} from '@/views/workstation-v4/semantic-rules/types'
import { isBatchJobCancelable } from '@/views/workstation-v4/semantic-rules/utils/batchJobStatus'

const poolLoading = ref(false)
const route = useRoute()
const router = useRouter()
const itemLoading = ref(false)
const matchLoading = ref(false)
const runLoading = ref(false)
const syncLoading = ref(false)
const importingPool = ref(false)
const selectedRowKeys = ref<string[]>([])
const initialQueryJobHandled = ref(false)
const initialFocusedRecordSearchHandled = ref(false)
const importModalOpen = ref(false)
const importFileList = ref<UploadFile[]>([])
const customerSampleGuideOpen = ref(false)
const customerSampleGuideStepIndex = ref(0)
const customerSampleTourCardStyle = ref<CSSProperties>({})
const LUXIAN_0609_RULE_SET_KEY = 'luxian_0609_qc_v1'
const FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY = 'sc_content_full_v1'
const SC_SAMPLE_RULE_SET_KEY = 'sc_sample_running_v1'
const PROGRAMMATIC_RULE_SET_KEY = 'sample_programmatic_gate_v1'
const LEGACY_CUSTOMER_RULE_SET_KEY = 'customer_luxian_full_v1'
const SAMPLE_RULE_SET_RUN_TIMEOUT_MS = 90000
const RUN_DUPLICATE_GUARD_MS = 120000
const CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY = 'medqc_customer_sample_validation_guide_seen_v1'
const CUSTOMER_TEST_POOL_ID = 'customer-created-test-records-v1'
const LUXIAN_RULE_FAMILY_PREVIEW_LIMIT = 5
const TASK_HISTORY_ISSUE_PREVIEW_LIMIT = 3
const HTML_EXPORT_MISMATCH_MESSAGE =
  '后端未返回 HTML 明细文件，请确认客户机后端已更新到支持 HTML 导出的版本。'
let customerSampleGuidePositionTimer: ReturnType<typeof setTimeout> | null = null

async function normalizeBatchExportBlob(
  blob: Blob,
  format: 'xlsx' | 'csv' | 'html',
): Promise<Blob> {
  if (format !== 'html') return blob
  const contentType = String(blob.type || '').toLowerCase()
  if (
    contentType.includes('spreadsheet') ||
    contentType.includes('officedocument') ||
    contentType.includes('zip')
  ) {
    throw new Error(HTML_EXPORT_MISMATCH_MESSAGE)
  }
  if (blob.size <= 0) {
    return new Blob([], { type: 'text/html;charset=utf-8' })
  }
  const preview = await blob.slice(0, 96).text()
  if (/^\s*PK/u.test(preview) || preview.includes('[Content_Types].xml')) {
    throw new Error(HTML_EXPORT_MISMATCH_MESSAGE)
  }
  const text = await blob.text()
  return new Blob([text.startsWith('\ufeff') ? text : `\ufeff${text}`], {
    type: 'text/html;charset=utf-8',
  })
}

const TASK_HISTORY_ATTENTION_STATUSES = new Set([
  'non_compliant',
  'data_gap',
  'uncertain',
  'not_executed',
  'technical_error',
])

const LUXIAN_0609_HISTORY_BRIEF_BY_ID: Record<string, string> = {
  'LX0609-001': '入院记录未在24小时内完成',
  'LX0609-002': '首次病程记录时间超过8小时',
  'LX0609-003': '手术记录未在术后24小时内完成',
  'LX0609-005': '入院48小时内无主治医师首次查房记录',
  'LX0609-007': '病情稳定患者3天内无查房病程记录',
  'LX0609-008': '病重患者2天内无查房病程记录',
  'LX0609-009': '病危患者未每天记录查房病程',
  'LX0609-012': '检查阳性结果未在24小时内分析',
  'LX0609-014': '细菌培养结果未在病程中记录',
  'LX0609-016': '首次病程与入院记录存在复制风险',
  'LX0609-017': '多次病程记录高度重复',
  'LX0609-018': '主诉不能导出第一诊断',
  'LX0609-019': '取材情况未在病程或手术记录中记录',
  'LX0609-020': '会诊后未记录会诊意见执行情况',
  'LX0609-021': '会诊申请目的不明确',
  'LX0609-022': '会诊意见不明确',
  'LX0609-024': '恶性肿瘤手术记录未描述淋巴结清扫',
  'LX0609-026': '化疗记录与医嘱不一致',
  'LX0609-038': '缺少麻醉记录单',
  'LX0609-041': '缺少输血知情同意书',
  'LX0609-043': '输血前常规检查不完整',
  'LX0609-044': '输血前评估记录不完整',
  'LX0609-047': '缺少输血后评价',
  'LX0609-049': '输血医嘱与收费不一致',
}

type TaskHistoryIssueSummary = {
  key: string
  ruleId: string
  text: string
}

type LuxianRuleOption = {
  ruleId: string
  name: string
  description: string
  requiredDocumentsLabel: string
}

type LuxianRuleFamilyView = {
  key: string
  name: string
  description: string
  rules: LuxianRuleOption[]
  ruleIds: string[]
}

type SamplePoolRunPayload = {
  record_ids: string[]
  max_parallel_records: number
  validation_mode: ManualSampleValidationMode
  rule_set_key: string
  selected_rule_ids?: string[]
  group_by_luxian_family?: boolean
}

type LuxianFamilyRunScope = {
  key: string
  name: string
  ruleIds: string[]
}

type LuxianAggregateJob = {
  family: LuxianFamilyRunScope
  jobId: string
  status: SichuanBatchJobStatus
  detail?: SichuanBatchJob
  errorMessage?: string
}

type EditableCopyDraft = {
  caseTitle: string
  patientName: string
  sex: string
  age: number
  mrNo: string
  department: string
  admissionTime: string
  dischargeTime: string
  mainDiagnosis: string
  manualIssueText: string
  documents: EditableMedicalRecordDocument[]
}

type EditableCopyDocumentFilter = 'all' | 'enabled' | 'orders' | 'new'

type EditableCopyDocumentGroup = {
  key: string
  label: string
  documents: EditableMedicalRecordDocument[]
}

type EditableCopyOrderTypeFilter = 'long' | 'temporary'

type EditableCopyOrderRow = {
  document: EditableMedicalRecordDocument
  startTime: string
  stopTime: string
  orderType: string
  item: string
  status: string
  orderTypeKey: EditableCopyOrderTypeFilter
}

const LUXIAN_0609_RULE_FAMILY_DEFINITIONS = [
  {
    key: 'basic_timeliness',
    name: '基础时限',
    description: '覆盖入院记录、首次病程、抢救记录和上级医师首次查房时限。',
    ruleIds: ['LX0609-001', 'LX0609-002', 'LX0609-004', 'LX0609-005', 'LX0609-006'],
  },
  {
    key: 'course_quality',
    name: '查房病程',
    description: '覆盖查房频次、病程复制、主诉和诊断依据等病程质量问题。',
    ruleIds: ['LX0609-007', 'LX0609-008', 'LX0609-009', 'LX0609-016', 'LX0609-017', 'LX0609-018'],
  },
  {
    key: 'exam_lab',
    name: '检查检验',
    description: '覆盖 CT/MRI、细菌培养结果记录与阳性结果分析。',
    ruleIds: ['LX0609-010', 'LX0609-011', 'LX0609-012', 'LX0609-014', 'LX0609-015'],
  },
  {
    key: 'consultation_quality',
    name: '会诊质量',
    description: '覆盖会诊目的、会诊意见和会诊执行记录。',
    ruleIds: ['LX0609-020', 'LX0609-021', 'LX0609-022', 'LX0609-023'],
  },
  {
    key: 'surgery_anesthesia',
    name: '手术麻醉',
    description: '覆盖手术记录、术前小结、知情同意、核查表、麻醉记录和术前讨论。',
    ruleIds: [
      'LX0609-003',
      'LX0609-024',
      'LX0609-025',
      'LX0609-028',
      'LX0609-029',
      'LX0609-030',
      'LX0609-031',
      'LX0609-032',
      'LX0609-033',
      'LX0609-034',
      'LX0609-035',
      'LX0609-036',
      'LX0609-037',
      'LX0609-038',
      'LX0609-039',
      'LX0609-040',
    ],
  },
  {
    key: 'transfusion',
    name: '输血',
    description: '覆盖输血知情同意、输血前检查、输血前后评价和医嘱收费一致性。',
    ruleIds: [
      'LX0609-041',
      'LX0609-042',
      'LX0609-043',
      'LX0609-044',
      'LX0609-045',
      'LX0609-046',
      'LX0609-047',
      'LX0609-048',
      'LX0609-049',
    ],
  },
  {
    key: 'tumor_pathology',
    name: '肿瘤病理',
    description: '覆盖病理结果、取材情况、化疗记录和肿瘤出院治疗计划。',
    ruleIds: ['LX0609-013', 'LX0609-019', 'LX0609-026', 'LX0609-027'],
  },
] as const

type CustomerSampleGuideTarget =
  | 'sample-pool'
  | 'sample-rule'
  | 'lx0609-scope'
  | 'create-record'
  | 'record-list'
  | 'run-validation'

type ImportWorkflowState = {
  poolId: string
  poolName: string
  importedRows: number
  matching: boolean
  matched: number
  ambiguous: number
  unmatched: number
  status:
    | 'imported'
    | 'matching'
    | 'matched'
    | 'no_match'
    | 'match_failed'
    | 'syncing'
    | 'synced'
    | 'sync_failed'
  message: string
}

const customerSampleGuideSteps: Array<{
  target: CustomerSampleGuideTarget
  title: string
  description: string
}> = [
  {
    target: 'sample-pool',
    title: '先选择样本池',
    description:
      '这里切换要验证的病历来源：客户自建测试病历用于现场演示，泸县0609合成质控样本用于回归验证，真实样本池用于客户数据复核。',
  },
  {
    target: 'sample-rule',
    title: '确认验证规则集',
    description:
      '这里选择本次运行的规则包。客户演示优先使用泸县0609质控点验证，页面会显示规则数量和覆盖状态。',
  },
  {
    target: 'lx0609-scope',
    title: '限定 LX0609 质控点范围',
    description: '默认运行全量 0609；勾选质控点后，只验证选中的 LX0609 客户质控点。',
  },
  {
    target: 'create-record',
    title: '创建测试病历',
    description: '点击这里可按质控点生成测试病历，保存后回到病历池继续验证。',
  },
  {
    target: 'record-list',
    title: '勾选要验证的病历',
    description: '在病历池中搜索、筛选并勾选病历；未选择病历时页面会提示先选择。',
  },
  {
    target: 'run-validation',
    title: '查看任务结果与证据链',
    description: '发起验证后打开结果抽屉，查看进度、状态分布、命中的客户质控点和证据摘要。',
  },
]

const fallbackRuleSets: ManualSampleValidationRuleSet[] = [
  {
    rule_set_key: LUXIAN_0609_RULE_SET_KEY,
    rule_set_name: '泸县0609质控点验证 v1',
    rule_set_version: '2026-06-09',
    scope: 'running',
    rule_count: 59,
    validation_mode: 'customer',
    advanced: false,
    display_group: 'main',
    coverage_summary: {
      已达正式口径: 6,
      证据待补强: 10,
      跨文书待完善: 14,
      跨表联查待接入: 15,
      待实现规则: 4,
    },
    coverage_status:
      '正式上线闸门未通过：通过 3 项，失败 6 项，未验证 0 项；当前 6 条达到 formal_ready，其余规则仍需补证据、跨文书或跨表执行链路。',
    release_gate_summary: {
      release_ready: false,
      passed_checks: 3,
      failed_checks: 6,
      unverified_checks: 0,
      blocking_count: 6,
    },
    evaluation_summary: {
      rule_count: 49,
      rules_with_all_case_types: 0,
      rules_missing_case_types: 49,
      hit_count: 0,
      manual_confirmed_correct_count: 0,
      false_positive_count: 0,
      false_negative_count: 0,
      unknown_count: 0,
      evidence_missing_count: 0,
      launch_status: { not_ready: 49 },
    },
    work_package_summary: {
      package_count: 49,
      phase_counts: {
        阶段3样本验证集建设: 6,
        阶段2证据链补强: 10,
        阶段2跨文书执行链路: 14,
        阶段2跨表数据联查: 15,
        阶段2新增规则实现: 4,
      },
      priority_counts: {
        P0: 14,
        P1: 22,
        P2: 13,
      },
    },
    page_closure_summary: {
      page_verified: false,
      capability_count: 8,
      passed_capabilities: 4,
      partial_capabilities: 4,
      failed_capabilities: 0,
      blocking_count: 4,
      status_counts: {
        pass: 4,
        partial: 4,
      },
    },
    note: '客户第一批专项验证规则包；当前为验证版，未达到正式上线闸门。',
  },
  {
    rule_set_key: FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
    rule_set_name: 'SC 内涵质控全量 v1',
    rule_set_version: '2026-04-20',
    scope: 'final',
    rule_count: 84,
    validation_mode: 'formal_fast_screen_full',
    requires_synced: true,
    advanced: false,
    display_group: 'main',
    coverage_status: 'SC146 中 84 条内涵规则全量基线',
    note: '正式终末内涵质控全量规则，用于与客户专项验证结果做基线对照。',
  },
  {
    rule_set_key: SC_SAMPLE_RULE_SET_KEY,
    rule_set_name: 'SC 样本规则模式',
    rule_set_version: 'running-batch-1',
    scope: 'running',
    rule_count: 0,
    validation_mode: 'sc',
    advanced: true,
    display_group: 'advanced',
    coverage_status: '规则数量由样本候选规则动态决定',
  },
  {
    rule_set_key: PROGRAMMATIC_RULE_SET_KEY,
    rule_set_name: '样本硬门槛程序规则包 v1',
    rule_set_version: '2026-04-27',
    scope: 'running',
    rule_count: 17,
    validation_mode: 'programmatic',
    requires_synced: true,
    advanced: true,
    display_group: 'advanced',
    coverage_status: '固定程序硬门槛规则包',
  },
  {
    rule_set_key: LEGACY_CUSTOMER_RULE_SET_KEY,
    rule_set_name: '客户专项规则包 v1（历史）',
    rule_set_version: '2026-04-30',
    scope: 'running',
    rule_count: 0,
    validation_mode: 'customer',
    advanced: true,
    display_group: 'advanced',
    coverage_status: '历史客户包，仅用于兼容旧样本复现',
  },
]

const pools = ref<ManualSamplePool[]>([])
const selectedPoolId = ref<string>()
const selectedPool = ref<ManualSamplePool>()
const records = ref<ManualSamplePoolRecord[]>([])
const ruleSets = ref<ManualSampleValidationRuleSet[]>(fallbackRuleSets)
const selectedRuleSetKey = ref<string>(LUXIAN_0609_RULE_SET_KEY)
const ruleSetDirectoryFallbackActive = ref(false)
const internalDiagnosticKeys = ref<string[]>([])
const selectedLuxianCustomerRuleIds = ref<string[]>([])
const luxian0609RuleCatalog = ref<ManualLuxian0609RuleCatalogItem[]>([])
const expandedLuxianRuleFamilyKeys = ref<string[]>([])
const importWorkflow = ref<ImportWorkflowState | null>(null)

const detailOpen = ref(false)
const activeRecord = ref<ManualSamplePoolRecord>()
const reviewDrawerVisible = ref(false)
const reviewDrawerRecord = ref<{
  id: string
  record_id: string
  patient_name?: string
  department?: string
  discharge_date?: string
  score?: number
  defect_count?: number
  status?: string
} | null>(null)
const editableCopyOpen = ref(false)
const editableCopyLoading = ref(false)
const editableCopySaving = ref(false)
const editableCopySaveAndRunLoading = ref(false)
const editableCopyReadonly = ref(false)
const editableCopySourceRecord = ref<ManualSamplePoolRecord | null>(null)
const editableCopyDraft = ref<EditableCopyDraft | null>(null)
const editableCopyNewDocumentType = ref('daily_course_record')
const editableCopyDocumentQuery = ref('')
const editableCopyDocumentFilter = ref<EditableCopyDocumentFilter>('all')
const editableCopyOrderTypeFilter = ref<EditableCopyOrderTypeFilter>('temporary')
const editableCopyActiveDocumentKey = ref('')
const editableCopyAllDocuments = computed(() => editableCopyDraft.value?.documents || [])
const editableCopyEnabledDocumentCount = computed(
  () => editableCopyAllDocuments.value.filter((document) => document.enabled !== false).length,
)
const editableCopyOrderDocuments = computed(() =>
  editableCopyAllDocuments.value
    .filter((document) => isEditableOrderDocument(document))
    .slice()
    .sort(compareEditableOrderDocumentByTimeDesc),
)
const editableCopyOrderRows = computed<EditableCopyOrderRow[]>(() =>
  editableCopyOrderDocuments.value.map((document) => parseEditableOrderRow(document)),
)
const editableCopyVisibleOrderRows = computed(() =>
  editableCopyOrderRows.value.filter(
    (row) => row.orderTypeKey === editableCopyOrderTypeFilter.value,
  ),
)
const editableCopyFilteredDocuments = computed(() => {
  const query = editableCopyDocumentQuery.value.trim().toLowerCase()
  return editableCopyAllDocuments.value.filter((document) => {
    if (editableCopyDocumentFilter.value === 'enabled' && document.enabled === false) return false
    if (editableCopyDocumentFilter.value === 'orders' && !isEditableOrderDocument(document))
      return false
    if (editableCopyDocumentFilter.value === 'new' && !document.is_new) return false
    if (!query) return true
    return [
      document.title,
      document.document_type,
      document.record_time,
      document.content,
      resolveEditableOrderTypeLabel(document),
    ]
      .join(' ')
      .toLowerCase()
      .includes(query)
  })
})
const editableCopyDocumentGroups = computed<EditableCopyDocumentGroup[]>(() => {
  const groups = new Map<string, EditableCopyDocumentGroup>()
  editableCopyFilteredDocuments.value.forEach((document) => {
    const key = editableCopyDocumentGroupKey(document)
    const label = editableCopyDocumentGroupLabel(key)
    if (!groups.has(key)) groups.set(key, { key, label, documents: [] })
    groups.get(key)?.documents.push(document)
  })
  return ['admission', 'course', 'surgery', 'exam_lab', 'other', 'order']
    .map((key) => groups.get(key))
    .filter((group): group is EditableCopyDocumentGroup => Boolean(group))
})
const editableCopyActiveDocument = computed(() => {
  const documents = editableCopyAllDocuments.value
  return (
    documents.find((document) => document.key === editableCopyActiveDocumentKey.value) ||
    editableCopyFilteredDocuments.value[0] ||
    documents[0] ||
    null
  )
})

const batchResultOpen = ref(false)
const batchJobDetail = ref<SichuanBatchJob | null>(null)
const batchJobLoading = ref(false)
const cancelBatchJobLoading = ref(false)
const taskHistoryOpen = ref(false)
const taskHistoryLoading = ref(false)
const taskHistoryJobs = ref<SichuanBatchJob[]>([])
const taskHistoryTotal = ref(0)
const luxianAggregateOpen = ref(false)
const luxianAggregateLoading = ref(false)
const luxianAggregateJobs = ref<LuxianAggregateJob[]>([])
const luxianAggregateParentJobId = ref('')
const luxianAggregateSummary = computed(() => {
  const total = luxianAggregateJobs.value.length
  const completed = luxianAggregateJobs.value.filter((item) => item.status === 'completed').length
  const failed = luxianAggregateJobs.value.filter((item) =>
    ['failed', 'canceled'].includes(item.status),
  ).length
  const running = luxianAggregateJobs.value.filter((item) => isBatchJobRunning(item.status)).length
  return {
    total,
    completed,
    failed,
    running,
  }
})
const batchResultFocusRecord = ref<{
  visitId: string
  recordId: string
  label: string
} | null>(null)
let batchJobPollTimer: ReturnType<typeof setInterval> | null = null
let taskHistoryPollTimer: ReturnType<typeof setInterval> | null = null
let luxianAggregatePollTimer: ReturnType<typeof setInterval> | null = null
let syncJobPollTimer: ReturnType<typeof setInterval> | null = null
const syncJobDetail = ref<ManualSamplePoolSyncJob>()
const exactReviewAcceptance = ref<Sheet2ExactReviewAcceptancePackage | null>(null)
const exactReviewLoading = ref(false)
const exactReviewError = ref('')

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0,
})

const filters = ref({
  query: '',
  coverageType: undefined as string | undefined,
  matchStatus: undefined as string | undefined,
  includeInBatch: true,
})
const importForm = ref({
  poolName: '',
  description: '',
})
const runOptions = ref({
  maxParallelRecords: 4,
})
const selectedValidationMode = ref<ManualSampleValidationMode>('customer')
const isFormalFastScreenMode = computed(
  () => selectedValidationMode.value === 'formal_fast_screen_full',
)
const isSyncedOnlyValidationMode = computed(
  () => selectedValidationMode.value === 'programmatic' || isFormalFastScreenMode.value,
)
const lastRunSubmission = ref<{
  key: string
  startedAt: number
  jobId?: string
  jobIds?: string[]
}>()

function formatSamplePoolOptionLabel(pool: ManualSamplePool): string {
  const name = String(pool.name || '未命名样本池').trim() || '未命名样本池'
  const total = Number(pool.total_items || 0)
  const countText = `（${total}）`
  return name.endsWith(countText) ? name : `${name}${countText}`
}

const poolOptions = computed(() =>
  pools.value.map((item) => ({
    label: formatSamplePoolOptionLabel(item),
    value: item.id,
  })),
)

const coverageOptions = [
  { label: '内涵验证', value: 'llm_intrinsic' },
  { label: '程序规则', value: 'programmatic' },
  { label: '未纳入', value: 'unsupported' },
]

const matchStatusOptions = [
  { label: '已关联病历', value: 'matched' },
  { label: '待人工确认', value: 'ambiguous' },
  { label: '未找到病历', value: 'unmatched' },
]
const parallelOptions = [
  { label: '1', value: 1 },
  { label: '2', value: 2 },
  { label: '4', value: 4 },
]
const selectedRuleSet = computed(() => {
  return (
    ruleSets.value.find((item) => item.rule_set_key === selectedRuleSetKey.value) ||
    fallbackRuleSets.find((item) => item.rule_set_key === selectedRuleSetKey.value) ||
    fallbackRuleSets[0]
  )
})
const selectedRuleSetPayloadKey = computed(() =>
  selectedValidationMode.value === 'sc' ? '' : selectedRuleSet.value?.rule_set_key || '',
)
const isLuxian0609Mode = computed(
  () => selectedRuleSet.value?.rule_set_key === LUXIAN_0609_RULE_SET_KEY,
)
const luxianRuleFamilies = computed<LuxianRuleFamilyView[]>(() => {
  if (luxian0609RuleCatalog.value.length) {
    return buildLuxian0609RuleFamilies(luxian0609RuleCatalog.value)
  }
  return syntheticCaseRuleFamilies.map((family) => ({
    key: family.key,
    name: family.name,
    description: family.description,
    rules: family.rules.map((rule) => ({
      ruleId: rule.ruleId,
      name: rule.name,
      description: rule.name,
      requiredDocumentsLabel: rule.requiredDocumentsLabel,
    })),
    ruleIds: family.rules.map((rule) => rule.ruleId),
  }))
})
const allLuxianRuleIds = computed(() =>
  normalizeLuxianRuleIds(luxianRuleFamilies.value.flatMap((family) => family.ruleIds)),
)
const isAllLuxianRulesSelected = computed(() => {
  if (!allLuxianRuleIds.value.length) return false
  const selected = new Set(selectedLuxianCustomerRuleIds.value)
  return allLuxianRuleIds.value.every((ruleId) => selected.has(ruleId))
})
const luxianScopeModeText = computed(() =>
  selectedLuxianCustomerRuleIds.value.length
    ? isAllLuxianRulesSelected.value
      ? `当前范围：已勾选全部 ${selectedLuxianCustomerRuleIds.value.length} 个质控点`
      : `当前范围：已勾选 ${selectedLuxianCustomerRuleIds.value.length} 个质控点`
    : '当前范围：完整 0609 规则集',
)
const currentCustomerSampleGuideStep = computed(
  () => customerSampleGuideSteps[customerSampleGuideStepIndex.value] || customerSampleGuideSteps[0],
)
const isLastCustomerSampleGuideStep = computed(
  () => customerSampleGuideStepIndex.value >= customerSampleGuideSteps.length - 1,
)
const mainRuleSets = computed(() =>
  ruleSets.value.filter((item) => !item.advanced && (item.display_group || 'main') === 'main'),
)
const selectedRuleSetRuleCountText = computed(() => {
  const count = Number(selectedRuleSet.value?.rule_count || 0)
  return count > 0 ? `${count} 条` : '动态规则数'
})
const selectedRuleSetCoverageChips = computed(() => {
  const summary = selectedRuleSet.value?.coverage_summary || {}
  const entries = Object.entries(summary)
  const gate = selectedRuleSet.value?.release_gate_summary
  const evaluation = selectedRuleSet.value?.evaluation_summary
  const extraChips: Array<{ label: string; value: string | number; className: string }> = []
  if (selectedRuleSet.value?.rule_set_key === LUXIAN_0609_RULE_SET_KEY) {
    if (gate) {
      extraChips.push({
        label: gate.release_ready ? '发布闸门' : '闸门未过',
        value: gate.release_ready
          ? '通过'
          : `${Number(gate.passed_checks || 0)}/${Number(gate.passed_checks || 0) + Number(gate.failed_checks || 0) + Number(gate.unverified_checks || 0)}`,
        className: gate.release_ready
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
          : 'border-rose-200 bg-rose-50 text-rose-700',
      })
    }
    if (evaluation) {
      extraChips.push(
        {
          label: '三类样本齐备',
          value: Number(evaluation.rules_with_all_case_types || 0),
          className:
            Number(evaluation.rules_with_all_case_types || 0) > 0
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-amber-200 bg-amber-50 text-amber-700',
        },
        {
          label: '命中',
          value: Number(evaluation.hit_count || 0),
          className: 'border-sky-200 bg-sky-50 text-sky-700',
        },
        {
          label: '误报',
          value: Number(evaluation.false_positive_count || 0),
          className:
            Number(evaluation.false_positive_count || 0) > 0
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : 'border-slate-200 bg-slate-50 text-slate-600',
        },
        {
          label: '漏报',
          value: Number(evaluation.false_negative_count || 0),
          className:
            Number(evaluation.false_negative_count || 0) > 0
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : 'border-slate-200 bg-slate-50 text-slate-600',
        },
        {
          label: '不可判定',
          value: Number(evaluation.unknown_count || 0),
          className:
            Number(evaluation.unknown_count || 0) > 0
              ? 'border-amber-200 bg-amber-50 text-amber-700'
              : 'border-slate-200 bg-slate-50 text-slate-600',
        },
      )
    }
    const pageClosure = selectedRuleSet.value?.page_closure_summary
    if (pageClosure) {
      const capabilityCount = Number(pageClosure.capability_count || 0)
      const passedCapabilities = Number(pageClosure.passed_capabilities || 0)
      extraChips.push({
        label: pageClosure.page_verified ? '页面闭环' : '页面待闭环',
        value: capabilityCount > 0 ? `${passedCapabilities}/${capabilityCount}` : '-',
        className: pageClosure.page_verified
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
          : 'border-amber-200 bg-amber-50 text-amber-700',
      })
    }
  }
  if (!entries.length) {
    return [
      {
        label: '覆盖状态',
        value: coverageStatusText(selectedRuleSet.value),
        className: 'border-sky-200 bg-sky-50 text-sky-700',
      },
      ...extraChips,
    ]
  }
  return [
    ...extraChips,
    ...entries.map(([label, value]) => ({
      label,
      value,
      className:
        label.includes('待补') || label.includes('联查')
          ? 'border-amber-200 bg-amber-50 text-amber-700'
          : label.includes('近似')
            ? 'border-cyan-200 bg-cyan-50 text-cyan-700'
            : 'border-emerald-200 bg-emerald-50 text-emerald-700',
    })),
  ]
})

const workflowSteps = computed(() => {
  const pool = selectedPool.value
  const runnableValue = isLuxian0609Mode.value
    ? (pool?.matched_items ?? 0)
    : isSyncedOnlyValidationMode.value
      ? (pool?.matched_items ?? 0)
      : (pool?.ready_items ?? 0)
  return [
    {
      label: '匹配',
      value: pool?.matched_items ?? 0,
      className: (pool?.matched_items ?? 0) > 0 ? 'is-ready' : '',
    },
    {
      label: isSyncedOnlyValidationMode.value ? '同步' : '就绪',
      value: runnableValue,
      className: runnableValue > 0 ? 'is-ready' : '',
    },
    {
      label: '已选',
      value: selectedRecordStats.value.selectedCount,
      className: selectedRecordStats.value.selectedCount > 0 ? 'is-active' : '',
    },
  ]
})

const summaryCards = computed(() => {
  const pool = selectedPool.value
  const runnableValue = isLuxian0609Mode.value
    ? (pool?.matched_items ?? 0)
    : isSyncedOnlyValidationMode.value
      ? (pool?.matched_items ?? 0)
      : (pool?.ready_items ?? 0)
  let runnableHelp = '文书已就绪，可直接开始当前模式质控'
  if (isLuxian0609Mode.value) {
    runnableHelp = '已关联真实病历即可开始0609质控；可再限定 LX0609 质控点范围'
  } else if (isFormalFastScreenMode.value) {
    runnableHelp = '已匹配且已同步，可开始正式 84 条质控'
  } else if (selectedValidationMode.value === 'programmatic') {
    runnableHelp = '已匹配且已同步，可直接开始程序规则验证'
  }
  const latestStatus = pool?.latest_job_status
  return [
    { label: '样本总数', value: pool?.total_items ?? 0, help: '当前样本池导入的记录数' },
    { label: '已匹配病历', value: pool?.matched_items ?? 0, help: '已映射到系统病历主键的样本数' },
    {
      label: '可质控病历',
      value: runnableValue,
      help: runnableHelp,
    },
    {
      label: '最近任务状态',
      value: latestStatus ? getBatchJobStatusText(latestStatus) : '暂无',
      help: '可在“更多”中查看最近任务详情',
    },
  ]
})

const exactReviewStatusCards = computed(() => {
  const acceptance = exactReviewAcceptance.value
  const status = acceptance?.status_breakdown
  const explanations = acceptance?.explanations
  return [
    {
      label: '精确命中',
      value: status?.exact_confirmed ?? 0,
      help: explanations?.exact_confirmed || '已与人工问题精确对齐的条目。',
      cardClass: 'border-emerald-200 bg-emerald-50/70',
    },
    {
      label: '已复核阻塞',
      value: status?.blocked_with_reason ?? 0,
      help:
        explanations?.blocked_with_reason || '已复核，但当前规则或证据链还不能精确复现人工问题。',
      cardClass: 'border-amber-200 bg-amber-50/80',
    },
    {
      label: '缺文书跳过',
      value: status?.skip ?? 0,
      help: explanations?.skip || '原始正文缺失，按既定口径归入 skip。',
      cardClass: 'border-slate-200 bg-slate-50/90',
    },
    {
      label: '复核总量',
      value: acceptance?.total_rows ?? 0,
      help: 'Sheet2 全量逐条精确复核样本规模。',
      cardClass: 'border-sky-200 bg-sky-50/70',
    },
  ]
})

const exactReviewReasonTags = computed(() => {
  const breakdown = exactReviewAcceptance.value?.blocked_reason_breakdown || {}
  const order = ['规则不支持', '证据链不足', '人工问题原文不可判']
  return order
    .filter((label) => typeof breakdown[label] === 'number')
    .map((label) => ({
      label,
      value: breakdown[label],
      className:
        label === '规则不支持'
          ? 'border-sky-200 bg-sky-50 text-sky-700'
          : label === '证据链不足'
            ? 'border-orange-200 bg-orange-50 text-orange-700'
            : 'border-rose-200 bg-rose-50 text-rose-700',
    }))
})

const exactReviewBacklogBuckets = computed(
  () => exactReviewAcceptance.value?.blocked_backlog_breakdown || [],
)

const syncProgress = computed(() => syncJobDetail.value?.summary?.progress || {})
const syncRecordProgress = computed(() => {
  const summary = syncJobDetail.value?.summary || {}
  const rawProgress = syncProgress.value.record_progress || summary.record_progress || {}
  const total = Number(
    rawProgress.total ??
      syncProgress.value.eligible_visits ??
      summary.eligible_visits ??
      selectedPool.value?.matched_items ??
      0,
  )
  const fallbackCompleted = records.value.filter((record) =>
    isRecordSyncedForValidation(record),
  ).length
  const completed = Math.min(
    Math.max(0, Number(rawProgress.completed ?? fallbackCompleted ?? 0)),
    Math.max(total, 0),
  )
  const remaining = Math.max(0, Number(rawProgress.remaining ?? Math.max(total - completed, 0)))
  const missingMr = Math.max(0, Number(rawProgress.missing_mr ?? remaining))
  const ready =
    total > 0
      ? Math.min(
          Math.max(
            0,
            Number(
              selectedPool.value?.ready_items ??
                records.value.filter((record) => record.bundle_status === 'ready').length,
            ),
          ),
          Math.max(total, 0),
        )
      : 0
  const readyHint =
    completed > ready
      ? '有病历已同步，文书仍在整理中。'
      : ready > 0
        ? '文书已可用于质控。'
        : '等待文书整理完成。'
  return {
    total,
    completed,
    remaining,
    missingMr,
    detailOnly: Math.max(0, Number(rawProgress.detail_only ?? 0)),
    ready,
    readyHint,
  }
})
const syncResolvedStats = computed(() => {
  const summary = syncJobDetail.value?.summary || {}
  const progress = syncProgress.value
  return {
    matched: Number(progress.matched ?? summary.matched ?? 0),
    ambiguous: Number(progress.ambiguous ?? summary.ambiguous ?? 0),
    unmatched: Number(progress.unmatched ?? summary.unmatched ?? 0),
  }
})
const syncResultNotice = computed(() => {
  const job = syncJobDetail.value
  if (!job) return null
  const normalizedStatus = String(job.status || '').toLowerCase()
  const summary = job.summary || {}
  const progress = syncProgress.value
  const totalCandidates = Number(progress.total_candidates ?? 0)
  const eligibleVisits = Number(progress.eligible_visits ?? summary.eligible_visits ?? 0)
  const rowsUpserted = Number(progress.total_rows_upserted ?? summary.total_rows_upserted ?? 0)
  if (normalizedStatus === 'failed') {
    return {
      title: '同步失败',
      description:
        job.error_message || '后台同步任务失败，请检查客户源库连接、源表权限或后端日志。',
      className: 'border-rose-200 bg-rose-50 text-rose-700',
    }
  }
  if (normalizedStatus === 'completed' && totalCandidates === 0) {
    return {
      title: '没有找到可同步样本',
      description:
        '当前筛选条件下没有进入同步的样本病历，请检查是否被“仅内涵/仅首批”过滤，或先执行病历匹配。',
      className: 'border-amber-200 bg-amber-50 text-amber-800',
    }
  }
  if (normalizedStatus === 'completed' && eligibleVisits === 0) {
    return {
      title: '源库未匹配到可同步病历',
      description:
        '同步任务已结束，但没有解析到可拉取的真实病历。请检查住院号/visit_id 是否能在客户源库 mr 表中匹配，以及远端 PG 配置是否指向正确库。',
      className: 'border-amber-200 bg-amber-50 text-amber-800',
    }
  }
  if (normalizedStatus === 'completed' && rowsUpserted === 0) {
    return {
      title: '未写入任何病历数据',
      description:
        '已找到可同步病历，但本次没有写入本地数据。请检查源表是否有文书记录、同步表组是否完整，以及后端是否跳过了可选表。',
      className: 'border-amber-200 bg-amber-50 text-amber-800',
    }
  }
  return null
})

const importWorkflowSteps = computed(() => {
  const workflow = importWorkflow.value
  if (!workflow) return []
  const isImported = workflow.importedRows > 0
  const isMatched =
    workflow.status === 'matched' ||
    workflow.status === 'syncing' ||
    workflow.status === 'synced' ||
    workflow.status === 'sync_failed'
  const hasNoMatch = workflow.status === 'no_match'
  return [
    {
      label: '1. 导入样本 ID',
      description: isImported ? `已读取 ${workflow.importedRows} 条 ID。` : '等待上传模板。',
      className: isImported
        ? 'border-sky-200 bg-sky-50 text-sky-800'
        : 'border-slate-200 bg-slate-50 text-slate-500',
    },
    {
      label: '2. 匹配源库病历',
      description: workflow.matching
        ? '正在按就诊ID、住院号、病案号匹配源库。'
        : hasNoMatch
          ? '未匹配到病历，请检查 ID 类型或源库配置。'
          : `匹配 ${workflow.matched} 份，待确认 ${workflow.ambiguous} 份，未找到 ${workflow.unmatched} 份。`,
      className: workflow.matching
        ? 'border-blue-200 bg-blue-50 text-blue-800'
        : hasNoMatch
          ? 'border-amber-200 bg-amber-50 text-amber-800'
          : isMatched
            ? 'border-sky-200 bg-sky-50 text-sky-800'
            : 'border-slate-200 bg-slate-50 text-slate-500',
    },
    {
      label: '3. 同步病历文书',
      description:
        workflow.status === 'syncing'
          ? '同步任务已创建，请在下方查看进度。'
          : workflow.status === 'synced'
            ? workflow.message
            : workflow.status === 'sync_failed'
              ? workflow.message
              : workflow.matched > 0
                ? '可开始同步匹配到的病历文书。'
                : '匹配到病历后才能同步文书。',
      className:
        workflow.status === 'syncing'
          ? 'border-blue-200 bg-blue-50 text-blue-800'
          : workflow.status === 'sync_failed'
            ? 'border-rose-200 bg-rose-50 text-rose-700'
            : workflow.status === 'synced' || workflow.matched > 0
              ? 'border-sky-200 bg-sky-50 text-sky-800'
              : 'border-slate-200 bg-slate-50 text-slate-500',
    },
  ]
})

const currentScopeDescription = computed(() => {
  const total = pagination.value.total || 0
  const matched = records.value.filter((record) => record.match_status === 'matched').length
  const ready = records.value.filter((record) => record.bundle_status === 'ready').length
  const synced = records.value.filter((record) => isRecordSyncedForValidation(record)).length
  const filterLabels = [
    `验证规则集：${selectedRuleSet.value?.rule_set_name || validationModeLabel(selectedValidationMode.value)}`,
    filters.value.coverageType ? `样本范围：${coverageLabel(filters.value.coverageType)}` : '',
    filters.value.matchStatus ? `病历关联：${matchStatusLabel(filters.value.matchStatus)}` : '',
    !isSyncedOnlyValidationMode.value && filters.value.includeInBatch ? '仅看首批样本' : '',
  ].filter(Boolean)
  const base = isLuxian0609Mode.value
    ? `当前列表展示的是去重后的真实病历池，共 ${total} 份病历；其中已关联 ${matched} 份，可按全量或选定 LX0609 质控点发起验证。`
    : isSyncedOnlyValidationMode.value
      ? `当前列表展示的是去重后的真实病历池，共 ${total} 份病历；其中已关联 ${matched} 份、已同步 ${synced} 份。`
      : `当前列表展示的是去重后的真实病历池，共 ${total} 份病历；其中已关联 ${matched} 份，文书已就绪 ${ready} 份。`
  if (!filterLabels.length) {
    return `${base} ${runnableRequirementHint()}`
  }
  return `${base} 当前筛选：${filterLabels.join('，')}。${runnableRequirementHint()}`
})

const selectedRecordStats = computed(() => {
  const selectedRecords = records.value.filter((record) =>
    selectedRowKeys.value.includes(record.id),
  )
  const runnableRecords = selectedRecords.filter((record) => isRunnableRecord(record))
  return {
    selectedCount: selectedRecords.length,
    runnableCount: runnableRecords.length,
    skippedCount: Math.max(0, selectedRecords.length - runnableRecords.length),
    runnableRecordIds: runnableRecords
      .map((record) => String(record.matched_visit_id || '').trim())
      .filter((recordId) => Boolean(recordId)),
  }
})

const requiresSelectedRecords = computed(
  () => isFormalFastScreenMode.value || isLuxian0609Mode.value,
)

const runButtonDisabled = computed(
  () => runLoading.value || !selectedPoolId.value || !selectedPool.value?.total_items,
)

const runButtonActionText = computed(() =>
  isFormalFastScreenMode.value
    ? '开始SC质控'
    : isLuxian0609Mode.value
      ? '开始0609质控'
      : '开始样本验证',
)

const runButtonText = computed(() =>
  isFormalFastScreenMode.value
    ? selectedRecordStats.value.selectedCount > 0
      ? `${runButtonActionText.value}（已选 ${selectedRecordStats.value.selectedCount} 份）`
      : '请先选择病历'
    : isLuxian0609Mode.value
      ? selectedRecordStats.value.selectedCount > 0
        ? `${runButtonActionText.value}（已选 ${selectedRecordStats.value.selectedCount} 份）`
        : '请先选择病历'
      : selectedRecordStats.value.selectedCount > 0
        ? `${runButtonActionText.value}（已选 ${selectedRecordStats.value.selectedCount} 份）`
        : runButtonActionText.value,
)

const paginationConfig = computed(() => ({
  current: pagination.value.page,
  pageSize: pagination.value.pageSize,
  total: pagination.value.total,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
  onChange: (page: number, pageSize: number) => {
    pagination.value.page = page
    pagination.value.pageSize = pageSize
    loadRecords()
  },
}))

const tableEmptyText = computed(() => `${emptyTitle.value}。${emptyDescription.value}`)

const emptyTitle = computed(() => {
  if (!selectedPoolId.value) return '请先选择样本池'
  if (!selectedPool.value?.matched_items) return '当前还没有匹配成功的病历'
  if (!pagination.value.total) return '当前筛选条件下没有样本'
  return '暂无样本数据'
})

const emptyDescription = computed(() => {
  if (!selectedPoolId.value) {
    return '先选择一个客户样本池，再查看问题样本和匹配状态。'
  }
  if (!selectedPool.value?.matched_items) {
    return '请先执行病历匹配，并确认当前环境已经同步到客户真实病历数据。'
  }
  if (!pagination.value.total) {
    return '可以放宽覆盖类型、匹配状态或关闭“仅首批”后重新查询。'
  }
  return '当前没有可展示的样本。'
})

const itemColumns: TableColumnsType<ManualSamplePoolRecord> = [
  {
    title: '编号',
    key: 'record_code',
    width: 150,
    customRender: ({ record }) =>
      h(
        'span',
        {
          class: 'customer-sample-record-code',
          title: resolveRecordIdentifier(record),
        },
        resolveRecordDisplayCode(record),
      ),
  },
  {
    title: '创建日期',
    key: 'created_time',
    width: 120,
    customRender: ({ record }) =>
      h('span', { class: 'customer-sample-created-time' }, resolveRecordCreatedDate(record) || '-'),
  },
  {
    title: '病历',
    key: 'patient',
    width: 300,
    customRender: ({ record }) =>
      h('div', { class: 'customer-sample-patient-cell' }, [
        h(
          'div',
          {
            class: 'customer-sample-patient-name',
            title: resolveRecordPatientTitle(record),
          },
          resolveRecordPatientTitle(record),
        ),
      ]),
  },
  {
    title: '科室',
    dataIndex: 'department',
    width: 120,
    customRender: ({ value }) =>
      h('span', { class: 'customer-sample-department' }, String(value || '-')),
  },
  {
    title: '验证范围',
    key: 'issue_scope',
    width: 460,
    customRender: ({ record }) => renderRecordSummary(record),
  },
  {
    title: '操作',
    key: 'actions',
    width: 260,
    customRender: ({ record }) =>
      h('div', { class: 'customer-sample-action-cell' }, buildRecordActions(record)),
  },
]

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys) => {
    selectedRowKeys.value = keys.map((key) => String(key))
  },
}))

function coverageLabel(value: string): string {
  if (value === 'llm_intrinsic') return '内涵验证'
  if (value === 'programmatic') return '程序规则'
  if (value === 'unsupported') return '未纳入'
  return value || '-'
}

function validationModeLabel(value: string): string {
  if (value === 'formal_fast_screen_full') return '正式84条质控'
  if (value === 'programmatic') return '硬门槛程序规则'
  if (value === 'sc') return 'SC 样本规则'
  return '客户样本复现'
}

function ruleSetScopeLabel(value?: string): string {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
  if (normalized === 'final') return '终末病历'
  if (normalized === 'running') return '运行中病历'
  if (normalized === 'all') return '运行中/终末'
  return value || '-'
}

function coverageStatusText(ruleSet?: ManualSampleValidationRuleSet): string {
  if (!ruleSet) return '-'
  const explicitStatus = String(ruleSet.coverage_status || '').trim()
  if (explicitStatus) return explicitStatus
  const coverageSummary = ruleSet.coverage_summary || {}
  const summaryText = Object.entries(coverageSummary)
    .filter(([, value]) => Number.isFinite(Number(value)))
    .map(([label, value]) => `${label} ${value}`)
    .join(' / ')
  if (summaryText) return summaryText
  if (ruleSet.advanced) return '高级验证模式'
  return '已纳入主验证规则集'
}

function ruleSetCardClass(ruleSet: ManualSampleValidationRuleSet): string {
  return ruleSet.rule_set_key === selectedRuleSetKey.value ? 'is-selected' : ''
}

function matchStatusLabel(value: string): string {
  if (value === 'matched') return '已关联病历'
  if (value === 'ambiguous') return '待人工确认'
  if (value === 'unmatched') return '未找到病历'
  return value || '-'
}

function matchStatusHint(value: string): string {
  if (value === 'matched') return '已定位到真实病历，可继续同步文书。'
  if (value === 'ambiguous') return '同号命中多次住院，请先确认归属病历。'
  if (value === 'unmatched') return '请核对住院号、姓名或日期后重新匹配。'
  return '请先完成病历匹配。'
}

function bundleStatusLabel(value: string): string {
  if (value === 'ready') return '已就绪'
  if (value === 'missing') return '待同步'
  if (value === 'pending') return '准备中'
  return value || '-'
}

function bundleStatusHint(value: string): string {
  if (value === 'ready') return '可以查看病历并开始样本验证。'
  if (value === 'pending') return '正在刷新文书和 bundle，请稍后再看。'
  if (value === 'missing') return '下一步执行“同步样本病历”。'
  return '请先完成病历同步。'
}

function backlogBucketCardClass(category: string): string {
  if (category === '可补规则') {
    return 'border-sky-200 bg-[linear-gradient(180deg,rgba(239,246,255,0.95),rgba(255,255,255,0.98))]'
  }
  if (category === '需补源文书') {
    return 'border-orange-200 bg-[linear-gradient(180deg,rgba(255,247,237,0.95),rgba(255,255,255,0.98))]'
  }
  if (category === '需客户确认口径') {
    return 'border-fuchsia-200 bg-[linear-gradient(180deg,rgba(253,244,255,0.95),rgba(255,255,255,0.98))]'
  }
  return 'border-rose-200 bg-[linear-gradient(180deg,rgba(255,241,242,0.95),rgba(255,255,255,0.98))]'
}

function backlogBucketTagClass(category: string): string {
  if (category === '可补规则') {
    return 'border-sky-200 bg-sky-50 text-sky-700'
  }
  if (category === '需补源文书') {
    return 'border-orange-200 bg-orange-50 text-orange-700'
  }
  if (category === '需客户确认口径') {
    return 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700'
  }
  return 'border-rose-200 bg-rose-50 text-rose-700'
}

function summarizeRuleScopes(ruleIds: string[]): string {
  const scopes: string[] = []
  const pushScope = (label: string) => {
    if (!scopes.includes(label)) scopes.push(label)
  }
  const rules = new Set((ruleIds || []).map((item) => String(item || '').trim()).filter(Boolean))
  for (const ruleId of rules) {
    if (ruleId.startsWith('CL-')) {
      pushScope('客户专项规则包')
      continue
    }
    const num = Number.parseInt(ruleId.replace('SC-', ''), 10)
    if (Number.isNaN(num)) continue
    if (num <= 20) {
      pushScope('入院记录')
    } else if (num <= 27) {
      pushScope('首次病程')
    } else if (
      num <= 49 ||
      num === 70 ||
      num === 73 ||
      num === 74 ||
      num === 79 ||
      num === 143 ||
      num === 146
    ) {
      pushScope('日常病程')
    } else if (num <= 60) {
      pushScope('查房讨论')
    } else if (num <= 76) {
      pushScope('交接会诊')
    } else if (num <= 115) {
      pushScope('手术麻醉')
    } else if (num <= 127) {
      pushScope('出院记录')
    } else if (num <= 136) {
      pushScope('知情同意')
    } else if (num <= 140) {
      pushScope('检查检验')
    }
  }
  return scopes.join(' / ') || '-'
}

function summarizeRecordScope(record: ManualSamplePoolRecord): string {
  const labels = (record.document_scope_labels || []).filter(Boolean)
  if (labels.length) {
    return labels.join(' / ')
  }
  if (selectedValidationMode.value === 'formal_fast_screen_full') {
    return '正式终末全量内涵 84 条'
  }
  if (selectedValidationMode.value === 'programmatic') {
    return '样本硬门槛程序规则包 v1'
  }
  if (selectedValidationMode.value === 'customer') {
    return selectedRuleSet.value?.rule_set_name || '客户专项规则包'
  }
  return summarizeRuleScopes(record.candidate_rule_ids || [])
}

function recordScopeHint(record: ManualSamplePoolRecord): string {
  if (selectedValidationMode.value === 'formal_fast_screen_full') {
    return '当前按正式终末全量内涵 84 条执行，不依赖单条样本候选规则。'
  }
  if ((record.document_scope_labels || []).length > 0) {
    return '已按当前病历实际同步到的文书类型识别验证范围。'
  }
  if (selectedValidationMode.value === 'programmatic') {
    return '当前按固定硬门槛程序规则包执行，不再依赖单条样本候选规则。'
  }
  if (selectedValidationMode.value === 'customer') {
    return '当前按选中的客户验证规则集执行，原始 Excel 问题仅作为对照上下文保留。'
  }
  if ((record.candidate_rule_ids || []).length > 0) {
    return '当前仍按样本问题推断范围，待同步后会自动刷新。'
  }
  return '当前还没有可识别的文书范围。'
}

function normalizeLuxianRuleIdsForSummary(ruleIds: unknown[]): string[] {
  const normalized: string[] = []
  for (const item of ruleIds || []) {
    const ruleId = String(item || '')
      .trim()
      .toUpperCase()
    if (!/^LX0609-\d{3}$/u.test(ruleId)) continue
    if (!normalized.includes(ruleId)) normalized.push(ruleId)
  }
  return normalized
}

function resolveRecordLuxianRuleIds(record: ManualSamplePoolRecord): string[] {
  const rawPayloadRuleIds = record.sample_items.flatMap((item) => {
    const rawPayload = item.raw_payload || {}
    const selectedRuleIds = rawPayload.selected_rule_ids
    if (Array.isArray(selectedRuleIds)) return selectedRuleIds
    const goldenAnswers = rawPayload.golden_answers
    if (Array.isArray(goldenAnswers)) {
      return goldenAnswers
        .map((answer) =>
          answer && typeof answer === 'object'
            ? (answer as Record<string, unknown>).qc_point_id
            : '',
        )
        .filter(Boolean)
    }
    return []
  })
  const preferredRuleIds = normalizeLuxianRuleIdsForSummary(rawPayloadRuleIds)
  if (preferredRuleIds.length > 0) return preferredRuleIds
  return normalizeLuxianRuleIdsForSummary(record.candidate_rule_ids || [])
}

function resolveLuxianRuleFamilyNames(ruleIds: string[]): string[] {
  if (!ruleIds.length) return []
  const ruleSet = new Set(ruleIds)
  const familyNames = LUXIAN_0609_RULE_FAMILY_DEFINITIONS.filter((family) =>
    family.ruleIds.some((ruleId) => ruleSet.has(ruleId)),
  ).map((family) => family.name)
  return familyNames.length ? familyNames : ['泸县0609']
}

function resolveRecordIssueDisplayText(record: ManualSamplePoolRecord, ruleIds: string[]): string {
  const rawText = (record.issue_preview?.[0] || record.issue_preview_text || '').trim()
  const normalized = rawText.replace(/\s+/gu, ' ')
  if (/^按质控点创建/u.test(normalized)) {
    const familyNames = resolveLuxianRuleFamilyNames(ruleIds)
    return ['按质控点创建', familyNames.slice(0, 2).join('、')].filter(Boolean).join(' · ')
  }
  if (!normalized || normalized === '-') return '当前没有人工问题摘要'
  return normalized
}

function formatCompactLuxianRuleIds(ruleIds: string[]): string {
  if (!ruleIds.length) return ''
  const visible = ruleIds
    .slice(0, 3)
    .map((ruleId, index) => (index === 0 ? ruleId : ruleId.replace(/^LX0609-/u, '')))
  const remainingCount = Math.max(0, ruleIds.length - visible.length)
  return `${visible.join('、')}${remainingCount > 0 ? ` +${remainingCount}` : ''}`
}

function resolveRecordRuleSummary(record: ManualSamplePoolRecord) {
  const ruleIds = resolveRecordLuxianRuleIds(record)
  const familyNames = resolveLuxianRuleFamilyNames(ruleIds)
  const issueText = resolveRecordIssueDisplayText(record, ruleIds)
  const scopeText = summarizeRecordScope(record)
  return {
    ruleIds,
    issueText,
    familyText: familyNames.slice(0, 2).join('、') || '验证范围待识别',
    familyOverflowCount: Math.max(0, familyNames.length - 2),
    ruleIdText: formatCompactLuxianRuleIds(ruleIds),
    countText:
      ruleIds.length > 0 ? `${ruleIds.length}个质控点` : `${record.issue_count || 0}条问题`,
    scopeText: scopeText === '-' ? '文书范围待识别' : scopeText,
    title: [
      issueText,
      ruleIds.length ? `质控点：${ruleIds.join('、')}` : '',
      scopeText && scopeText !== '-' ? `文书范围：${scopeText}` : '',
    ]
      .filter(Boolean)
      .join('\n'),
  }
}

function renderRecordSummary(record: ManualSamplePoolRecord) {
  const summary = resolveRecordRuleSummary(record)
  const scopeSummary = `${summary.familyText}${summary.countText}`
  return h('div', { class: 'customer-sample-summary-cell' }, [
    h('div', { class: 'customer-sample-rule-summary' }, [
      h(
        'span',
        {
          class: 'customer-sample-family-chip',
          title: summary.title,
        },
        scopeSummary,
      ),
    ]),
  ])
}

function buildRecordActions(record: ManualSamplePoolRecord) {
  const actions = []
  if (record.matched_visit_id) {
    actions.push(
      h(
        'button',
        {
          type: 'button',
          class: 'customer-sample-secondary-link',
          onClick: () => openMedicalRecordViewer(record),
        },
        '查看病历',
      ),
    )
  }
  if (selectedPool.value?.latest_job_id && record.matched_visit_id) {
    actions.push(
      h(
        'button',
        {
          type: 'button',
          class: 'customer-sample-secondary-link',
          onClick: () =>
            openBatchJob(selectedPool.value?.latest_job_id || '', {
              visitId: record.matched_visit_id || '',
              recordId: resolveRecordIdentifier(record),
              label: [
                resolveRecordPatientName(record) === '-' ? '' : resolveRecordPatientName(record),
                record.department || '',
                resolveRecordIdentifier(record),
              ]
                .filter(Boolean)
                .join(' · '),
            }),
        },
        '查看结果',
      ),
    )
  }
  if (record.matched_visit_id && record.bundle_status === 'ready') {
    actions.push(
      h(
        'button',
        {
          type: 'button',
          class: 'customer-sample-secondary-link',
          onClick: () => openEditableCopyDrawer(record),
        },
        '创建副本',
      ),
    )
  }
  return actions
}

function isRecordSyncedForValidation(record: ManualSamplePoolRecord): boolean {
  return record.sync_status === 'synced' || record.sync_status === 'synthetic_seeded'
}

function isRunnableRecord(record: ManualSamplePoolRecord): boolean {
  if (isLuxian0609Mode.value) {
    return record.match_status === 'matched' && !!record.matched_visit_id
  }
  if (isSyncedOnlyValidationMode.value) {
    return (
      record.match_status === 'matched' &&
      isRecordSyncedForValidation(record) &&
      !!record.matched_visit_id
    )
  }
  return (
    record.match_status === 'matched' &&
    isRecordSyncedForValidation(record) &&
    record.bundle_status === 'ready' &&
    !!record.matched_visit_id
  )
}

function runnableRequirementHint(): string {
  if (isLuxian0609Mode.value) {
    return '泸县0609支持从已关联真实病历直接发起验证；选择质控族/质控点只限定规则范围，不会限制样本池或病历选择。'
  }
  if (selectedValidationMode.value === 'formal_fast_screen_full') {
    return '未关联真实病历或尚未同步到本地 PG 的病历不会进入正式质控；若后台 final scope 收集不到，会返回终末病历未同步错误。'
  }
  if (selectedValidationMode.value === 'programmatic') {
    return '未关联到真实病历或尚未同步的病历不会进入程序规则批量验证。'
  }
  return '未关联到真实病历或文书未就绪的病历不会进入当前规则集验证。'
}

function selectedRecordNotRunnableMessage(): string {
  if (isLuxian0609Mode.value) {
    return '当前选中的病历还未完成病历关联，暂时无法开始0609质控'
  }
  if (selectedValidationMode.value === 'formal_fast_screen_full') {
    return '当前选中的病历还未完成匹配或同步，暂时无法发起正式质控 84 条'
  }
  if (selectedValidationMode.value === 'programmatic') {
    return '当前选中的病历还未完成匹配或同步，暂时无法发起程序规则验证'
  }
  return '当前选中的病历还未完成匹配、同步或 bundle 准备，暂时无法发起验证'
}

function clearSelectedRecords() {
  selectedRowKeys.value = []
}

function normalizeRuleSetKey(
  ruleSetKey: unknown,
  validationMode: ManualSampleValidationMode,
): string {
  const normalizedKey = String(ruleSetKey || '').trim()
  if (normalizedKey) return normalizedKey
  if (validationMode === 'sc') return SC_SAMPLE_RULE_SET_KEY
  return normalizedKey
}

function normalizeRuleSetItem(raw: ManualSampleValidationRuleSet): ManualSampleValidationRuleSet {
  const validationMode = normalizeValidationMode(raw.validation_mode || 'customer')
  const ruleIds = Array.isArray(raw.rule_ids) ? raw.rule_ids.map((item) => String(item)) : undefined
  const ruleCount = Number(raw.rule_count ?? ruleIds?.length ?? 0)
  const ruleSetKey = normalizeRuleSetKey(raw.rule_set_key, validationMode)
  return {
    ...raw,
    rule_set_key: ruleSetKey,
    rule_set_name: String(raw.rule_set_name || ruleSetKey || validationModeLabel(validationMode)),
    rule_set_version: String(raw.rule_set_version || 'v1'),
    scope: String(
      raw.scope || (validationMode === 'formal_fast_screen_full' ? 'final' : 'running'),
    ),
    rule_ids: ruleIds,
    rule_count: Number.isFinite(ruleCount) ? ruleCount : 0,
    validation_mode: validationMode,
    advanced: Boolean(raw.advanced),
    display_group: raw.display_group || (raw.advanced ? 'advanced' : 'main'),
  }
}

function buildRuleSetDirectory(
  items: ManualSampleValidationRuleSet[],
): ManualSampleValidationRuleSet[] {
  const fallbackByKey = new Map(fallbackRuleSets.map((item) => [item.rule_set_key, item]))
  const mergedByKey = new Map<string, ManualSampleValidationRuleSet>()
  for (const item of fallbackRuleSets) {
    mergedByKey.set(item.rule_set_key, item)
  }
  for (const raw of items) {
    const normalized = normalizeRuleSetItem(raw)
    if (!normalized.rule_set_key) continue
    const fallback = fallbackByKey.get(normalized.rule_set_key)
    mergedByKey.set(normalized.rule_set_key, {
      ...(fallback || {}),
      ...normalized,
      advanced: normalized.advanced ?? fallback?.advanced ?? false,
      display_group: normalized.display_group || fallback?.display_group || 'main',
    })
  }
  const priority = [
    LUXIAN_0609_RULE_SET_KEY,
    FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
    SC_SAMPLE_RULE_SET_KEY,
    PROGRAMMATIC_RULE_SET_KEY,
    LEGACY_CUSTOMER_RULE_SET_KEY,
  ]
  return Array.from(mergedByKey.values()).sort((left, right) => {
    const leftIndex = priority.indexOf(left.rule_set_key)
    const rightIndex = priority.indexOf(right.rule_set_key)
    const leftRank = leftIndex >= 0 ? leftIndex : priority.length
    const rightRank = rightIndex >= 0 ? rightIndex : priority.length
    if (leftRank !== rightRank) return leftRank - rightRank
    if (Boolean(left.advanced) !== Boolean(right.advanced)) return left.advanced ? 1 : -1
    return left.rule_set_name.localeCompare(right.rule_set_name, 'zh-CN')
  })
}

function normalizeLuxianCatalogRule(
  rule: ManualLuxian0609RuleCatalogItem,
): LuxianRuleOption | null {
  const ruleId = normalizeLuxianRuleIds([rule.rule_id || rule.rule_code || ''])[0]
  if (!ruleId) return null
  const requiredDocumentsLabel =
    rule.required_documents_label ||
    (Array.isArray(rule.applicable_document_labels)
      ? rule.applicable_document_labels.join('、')
      : '')
  return {
    ruleId,
    name: String(rule.name || rule.description || ruleId).trim() || ruleId,
    description: String(rule.description || rule.name || '').trim(),
    requiredDocumentsLabel: String(requiredDocumentsLabel || '').trim(),
  }
}

function buildLuxian0609RuleFamilies(
  rules: ManualLuxian0609RuleCatalogItem[],
): LuxianRuleFamilyView[] {
  const ruleById = new Map<string, LuxianRuleOption>()
  rules.forEach((rule) => {
    const normalized = normalizeLuxianCatalogRule(rule)
    if (normalized) {
      ruleById.set(normalized.ruleId, normalized)
    }
  })
  const usedRuleIds = new Set<string>()
  const families: LuxianRuleFamilyView[] = LUXIAN_0609_RULE_FAMILY_DEFINITIONS.map((family) => {
    const familyRules = family.ruleIds
      .map((ruleId) => ruleById.get(ruleId))
      .filter((rule): rule is LuxianRuleOption => Boolean(rule))
    familyRules.forEach((rule) => usedRuleIds.add(rule.ruleId))
    return {
      key: family.key,
      name: family.name,
      description: family.description,
      rules: familyRules,
      ruleIds: familyRules.map((rule) => rule.ruleId),
    }
  }).filter((family) => family.rules.length > 0)

  const uncategorizedRules = Array.from(ruleById.values())
    .filter((rule) => !usedRuleIds.has(rule.ruleId))
    .sort((left, right) => left.ruleId.localeCompare(right.ruleId))
  if (uncategorizedRules.length) {
    families.push({
      key: 'other',
      name: '其他',
      description: '后端目录中未归入固定业务族的 LX0609 质控点。',
      rules: uncategorizedRules,
      ruleIds: uncategorizedRules.map((rule) => rule.ruleId),
    })
  }
  return families
}

function openTestRecordDrawer() {
  const selectedRuleIds = isLuxian0609Mode.value
    ? normalizeLuxianRuleIds(selectedLuxianCustomerRuleIds.value)
    : []
  const routeTarget: { name: string; query?: Record<string, string> } = {
    name: 'WorkstationV4SyntheticCaseNew',
  }
  if (selectedRuleIds.length) {
    routeTarget.query = {
      ruleIds: selectedRuleIds.join(','),
      ruleFamily: resolveLuxianRuleFamilyKey(selectedRuleIds),
    }
  }
  router.push(routeTarget)
}

function hasCustomerSampleGuideTourQuery(): boolean {
  const raw = route?.query?.tour
  return Array.isArray(raw) ? raw.includes('1') : raw === '1'
}

function hasSeenCustomerSampleGuide(): boolean {
  try {
    return window.localStorage?.getItem(CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function markCustomerSampleGuideSeen() {
  try {
    window.localStorage?.setItem(CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY, 'true')
  } catch {
    // localStorage 可能被浏览器策略禁用，不影响导览关闭。
  }
}

function customerSampleGuideTargetClass(target: CustomerSampleGuideTarget) {
  return {
    'customer-sample-tour-target': customerSampleGuideOpen.value,
    'is-current-tour-target':
      customerSampleGuideOpen.value && currentCustomerSampleGuideStep.value.target === target,
  }
}

function clampTourPosition(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function updateCustomerSampleTourCardPosition() {
  if (!customerSampleGuideOpen.value) return
  const target = currentCustomerSampleGuideStep.value.target
  const element = document.querySelector(`[data-customer-guide="${target}"]`)
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
    left = clampTourPosition(rect.left, gap, maxLeft)
    top = rect.bottom + gap
    if (top + cardHeight > viewportHeight - gap) {
      top = rect.top - cardHeight - gap
    }
  }

  customerSampleTourCardStyle.value = {
    width: `${cardWidth}px`,
    left: `${clampTourPosition(left, gap, maxLeft)}px`,
    top: `${clampTourPosition(top, gap, maxTop)}px`,
  }
}

function scheduleCustomerSampleTourCardPositionUpdate() {
  if (customerSampleGuidePositionTimer) {
    clearTimeout(customerSampleGuidePositionTimer)
  }
  updateCustomerSampleTourCardPosition()
  customerSampleGuidePositionTimer = setTimeout(updateCustomerSampleTourCardPosition, 320)
}

function scrollCustomerSampleGuideTarget() {
  const target = currentCustomerSampleGuideStep.value.target
  void nextTick(() => {
    const element = document.querySelector(`[data-customer-guide="${target}"]`)
    if (typeof element?.scrollIntoView === 'function') {
      element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
    }
    scheduleCustomerSampleTourCardPositionUpdate()
  })
}

function openCustomerSampleGuide() {
  customerSampleGuideStepIndex.value = 0
  customerSampleGuideOpen.value = true
  scrollCustomerSampleGuideTarget()
}

function toggleInternalDiagnostic() {
  const shouldOpen = !internalDiagnosticKeys.value.includes('sheet2')
  internalDiagnosticKeys.value = shouldOpen ? ['sheet2'] : []
  if (shouldOpen) {
    void ensureExactReviewAcceptanceLoaded()
  }
}

function isSheet2DiagnosticOpen(keys: string | string[]) {
  return Array.isArray(keys) ? keys.includes('sheet2') : keys === 'sheet2'
}

function handleInternalDiagnosticChange(keys: string | string[]) {
  if (isSheet2DiagnosticOpen(keys)) {
    void ensureExactReviewAcceptanceLoaded()
  }
}

function closeCustomerSampleGuide() {
  customerSampleGuideOpen.value = false
  customerSampleTourCardStyle.value = {}
  markCustomerSampleGuideSeen()
}

function startSyntheticCaseFromGuide() {
  closeCustomerSampleGuide()
  openTestRecordDrawer()
}

function goToCustomerSampleGuideStep(index: number) {
  customerSampleGuideStepIndex.value = Math.min(
    Math.max(index, 0),
    customerSampleGuideSteps.length - 1,
  )
  scrollCustomerSampleGuideTarget()
}

function goToPreviousCustomerSampleGuideStep() {
  goToCustomerSampleGuideStep(customerSampleGuideStepIndex.value - 1)
}

function goToNextCustomerSampleGuideStep() {
  if (isLastCustomerSampleGuideStep.value) {
    closeCustomerSampleGuide()
    return
  }
  goToCustomerSampleGuideStep(customerSampleGuideStepIndex.value + 1)
}

function openInitialCustomerSampleGuide() {
  if (hasCustomerSampleGuideTourQuery() || !hasSeenCustomerSampleGuide()) {
    openCustomerSampleGuide()
  }
}

async function loadRuleSets() {
  const result = await listManualSampleValidationRuleSets()
  if (!result.success || !result.data) {
    ruleSets.value = fallbackRuleSets
    ruleSetDirectoryFallbackActive.value = true
    applyValidationModeEffects(
      normalizeValidationMode(selectedRuleSet.value?.validation_mode || 'customer'),
    )
    return
  }
  const mergedRuleSets = buildRuleSetDirectory(result.data.items || [])
  ruleSets.value = mergedRuleSets.length > 0 ? mergedRuleSets : fallbackRuleSets
  ruleSetDirectoryFallbackActive.value = mergedRuleSets.length === 0
  if (!ruleSets.value.some((item) => item.rule_set_key === selectedRuleSetKey.value)) {
    selectedRuleSetKey.value = LUXIAN_0609_RULE_SET_KEY
  }
  applyValidationModeEffects(
    normalizeValidationMode(selectedRuleSet.value?.validation_mode || 'customer'),
  )
}

async function loadLuxian0609RuleCatalog() {
  const result = await listLuxian0609CustomerRules()
  if (!result.success || !result.data) {
    luxian0609RuleCatalog.value = []
    return
  }
  luxian0609RuleCatalog.value = Array.isArray(result.data.rules) ? result.data.rules : []
}

async function loadPools() {
  poolLoading.value = true
  const result = await listManualSamplePools({ page: 1, page_size: 50 })
  poolLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '获取样本池失败')
    return
  }
  pools.value = result.data.items
  const queryPoolId = String(route?.query?.poolId || '').trim()
  if (queryPoolId && pools.value.some((item) => item.id === queryPoolId)) {
    selectedPoolId.value = queryPoolId
  }
  if (!selectedPoolId.value && pools.value.length > 0) {
    selectedPoolId.value = pools.value[0].id
  }
  selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
  if (selectedPoolId.value) {
    await loadLatestSyncJob()
    await loadRecords()
    await openInitialQueryJob()
  }
}

async function ensureExactReviewAcceptanceLoaded() {
  if (exactReviewLoading.value || exactReviewAcceptance.value) {
    return
  }
  await loadExactReviewAcceptance()
}

async function loadExactReviewAcceptance() {
  exactReviewLoading.value = true
  exactReviewError.value = ''
  const result = await getSheet2ExactReviewAcceptancePackage()
  exactReviewLoading.value = false
  if (!result.success || !result.data) {
    exactReviewAcceptance.value = null
    exactReviewError.value = result.message || '获取 Sheet2 精确复核验收包失败'
    return
  }
  exactReviewAcceptance.value = result.data
}

async function loadRecords() {
  if (!selectedPoolId.value) {
    records.value = []
    pagination.value.total = 0
    return
  }
  itemLoading.value = true
  const result = await getManualSamplePoolRecords(selectedPoolId.value, {
    coverage_type: filters.value.coverageType,
    match_status: filters.value.matchStatus,
    include_in_batch_1: isSyncedOnlyValidationMode.value ? undefined : filters.value.includeInBatch,
    q: filters.value.query || undefined,
    page: pagination.value.page,
    page_size: pagination.value.pageSize,
  })
  itemLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '获取样本明细失败')
    return
  }
  selectedPool.value = result.data.pool
  const focusedRecordId = String(route?.query?.recordId || '').trim()
  records.value = sortManualSampleRecordsForDisplay(
    result.data.items,
    selectedPoolId.value,
    focusedRecordId,
  )
  pagination.value.total = result.data.total
  if (
    focusedRecordId &&
    !initialFocusedRecordSearchHandled.value &&
    !records.value.some((record) => isFocusedRecord(record, focusedRecordId))
  ) {
    initialFocusedRecordSearchHandled.value = true
    filters.value.query = focusedRecordId
    pagination.value.page = 1
    await loadRecords()
    return
  }
  selectedRowKeys.value = selectedRowKeys.value.filter((key) =>
    records.value.some((item) => item.id === key),
  )
}

async function openInitialQueryJob() {
  if (initialQueryJobHandled.value) return
  const jobId = String(route?.query?.jobId || '').trim()
  if (!jobId) return
  initialQueryJobHandled.value = true
  message.info('验证任务已创建，正在打开任务进度')
  await openBatchJob(jobId)
}

function recordSortTime(record: ManualSamplePoolRecord): string {
  const fromRecord = String(record.created_at || record.updated_at || '').trim()
  if (fromRecord) return fromRecord
  return String(
    record.sample_items?.[0]?.created_at || record.sample_items?.[0]?.updated_at || '',
  ).trim()
}

function isFocusedRecord(record: ManualSamplePoolRecord, focusedRecordId: string): boolean {
  const normalizedFocus = String(focusedRecordId || '').trim()
  if (!normalizedFocus) return false
  return [record.id, record.matched_visit_id, record.mr_no].some(
    (value) => String(value || '').trim() === normalizedFocus,
  )
}

function sortManualSampleRecordsForDisplay(
  items: ManualSamplePoolRecord[],
  poolId: string,
  focusedRecordId = '',
): ManualSamplePoolRecord[] {
  const shouldSortCustomerTestPool = poolId === CUSTOMER_TEST_POOL_ID
  if (!shouldSortCustomerTestPool && !focusedRecordId) return items
  return [...items].sort((left, right) => {
    const leftFocused = isFocusedRecord(left, focusedRecordId)
    const rightFocused = isFocusedRecord(right, focusedRecordId)
    if (leftFocused !== rightFocused) return leftFocused ? -1 : 1
    if (shouldSortCustomerTestPool) {
      return recordSortTime(right).localeCompare(recordSortTime(left))
    }
    return 0
  })
}

async function handlePoolChange() {
  pagination.value.page = 1
  selectedRowKeys.value = []
  selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
  if (importWorkflow.value && importWorkflow.value.poolId !== selectedPoolId.value) {
    importWorkflow.value = null
  }
  await loadLatestSyncJob()
  await loadRecords()
}

function normalizeValidationMode(mode: string | number): ManualSampleValidationMode {
  const value = String(mode)
  if (value === 'formal_fast_screen_full') return 'formal_fast_screen_full'
  if (value === 'programmatic') return 'programmatic'
  if (value === 'sc') return 'sc'
  return 'customer'
}

function applyValidationModeEffects(normalizedMode: ManualSampleValidationMode) {
  selectedValidationMode.value = normalizedMode
  if (normalizedMode === 'programmatic') {
    filters.value.coverageType = 'programmatic'
    filters.value.includeInBatch = false
  } else if (normalizedMode === 'formal_fast_screen_full') {
    filters.value.coverageType = undefined
    filters.value.includeInBatch = false
  } else if (normalizedMode === 'sc' && filters.value.coverageType === 'programmatic') {
    filters.value.coverageType = 'llm_intrinsic'
    filters.value.includeInBatch = true
  } else {
    filters.value.includeInBatch = true
  }
}

function normalizeLuxianRuleIds(ruleIds: string[]): string[] {
  return Array.from(
    new Set(
      ruleIds
        .map((ruleId) =>
          String(ruleId || '')
            .trim()
            .toUpperCase(),
        )
        .filter((ruleId) => /^LX0609-\d{3}$/u.test(ruleId)),
    ),
  ).sort()
}

function resolveLuxianRuleFamilyKey(ruleIds: string[]): string {
  const normalizedRuleIds = normalizeLuxianRuleIds(ruleIds)
  if (!normalizedRuleIds.length) return ''
  const normalizedSet = new Set(normalizedRuleIds)
  const exactFamily = luxianRuleFamilies.value.find(
    (family) =>
      family.ruleIds.length > 0 && family.ruleIds.every((ruleId) => normalizedSet.has(ruleId)),
  )
  if (exactFamily) return exactFamily.key
  return (
    luxianRuleFamilies.value.find((family) =>
      family.ruleIds.some((ruleId) => normalizedSet.has(ruleId)),
    )?.key || ''
  )
}

function toggleLuxianRule(ruleId: string) {
  const normalizedRuleId = normalizeLuxianRuleIds([ruleId])[0]
  if (!normalizedRuleId) return
  const current = new Set(selectedLuxianCustomerRuleIds.value)
  if (current.has(normalizedRuleId)) {
    current.delete(normalizedRuleId)
  } else {
    current.add(normalizedRuleId)
  }
  selectedLuxianCustomerRuleIds.value = normalizeLuxianRuleIds([...current])
}

function isLuxianRuleFamilySelected(ruleIds: string[]): boolean {
  const normalizedRuleIds = normalizeLuxianRuleIds(ruleIds)
  if (!normalizedRuleIds.length) return false
  const current = new Set(selectedLuxianCustomerRuleIds.value)
  return normalizedRuleIds.every((ruleId) => current.has(ruleId))
}

function isLuxianRuleFamilyExpanded(familyKey: string): boolean {
  return expandedLuxianRuleFamilyKeys.value.includes(familyKey)
}

function visibleLuxianFamilyRules(family: LuxianRuleFamilyView): LuxianRuleOption[] {
  if (isLuxianRuleFamilyExpanded(family.key)) {
    return family.rules
  }
  return family.rules.slice(0, LUXIAN_RULE_FAMILY_PREVIEW_LIMIT)
}

function hiddenLuxianFamilyRuleCount(family: LuxianRuleFamilyView): number {
  if (isLuxianRuleFamilyExpanded(family.key)) return 0
  return Math.max(0, family.rules.length - LUXIAN_RULE_FAMILY_PREVIEW_LIMIT)
}

function toggleLuxianRuleFamilyExpanded(familyKey: string) {
  if (isLuxianRuleFamilyExpanded(familyKey)) {
    expandedLuxianRuleFamilyKeys.value = expandedLuxianRuleFamilyKeys.value.filter(
      (key) => key !== familyKey,
    )
    return
  }
  expandedLuxianRuleFamilyKeys.value = [...expandedLuxianRuleFamilyKeys.value, familyKey]
}

function selectLuxianRuleFamily(ruleIds: string[]) {
  const normalizedRuleIds = normalizeLuxianRuleIds(ruleIds)
  const current = new Set(selectedLuxianCustomerRuleIds.value)
  if (normalizedRuleIds.every((ruleId) => current.has(ruleId))) {
    normalizedRuleIds.forEach((ruleId) => current.delete(ruleId))
  } else {
    normalizedRuleIds.forEach((ruleId) => current.add(ruleId))
  }
  selectedLuxianCustomerRuleIds.value = normalizeLuxianRuleIds([...current])
}

function toggleAllLuxianRuleFamilies() {
  selectedLuxianCustomerRuleIds.value = isAllLuxianRulesSelected.value
    ? []
    : normalizeLuxianRuleIds(allLuxianRuleIds.value)
}

function clearLuxianRuleScope() {
  selectedLuxianCustomerRuleIds.value = []
}

function buildLuxianFamilyRunScopes(ruleIds: string[]): LuxianFamilyRunScope[] {
  const selectedRuleIds = normalizeLuxianRuleIds(ruleIds)
  if (!selectedRuleIds.length) return []
  const selectedSet = new Set(selectedRuleIds)
  const coveredRuleIds = new Set<string>()
  const scopes = luxianRuleFamilies.value
    .map((family) => {
      const familyRuleIds = normalizeLuxianRuleIds(family.ruleIds).filter((ruleId) =>
        selectedSet.has(ruleId),
      )
      familyRuleIds.forEach((ruleId) => coveredRuleIds.add(ruleId))
      return {
        key: family.key,
        name: family.name,
        ruleIds: familyRuleIds,
      }
    })
    .filter((scope) => scope.ruleIds.length > 0)

  const orphanRuleIds = selectedRuleIds.filter((ruleId) => !coveredRuleIds.has(ruleId))
  if (orphanRuleIds.length) {
    scopes.push({
      key: 'other',
      name: '其他质控点',
      ruleIds: orphanRuleIds,
    })
  }
  return scopes
}

function shouldRunLuxianFamiliesInParallel(ruleIds: string[]): boolean {
  return isLuxian0609Mode.value && buildLuxianFamilyRunScopes(ruleIds).length > 1
}

async function handleRuleSetChange(ruleSetKey: string | number) {
  const nextKey = String(ruleSetKey || '').trim() || LUXIAN_0609_RULE_SET_KEY
  selectedRuleSetKey.value = nextKey
  applyValidationModeEffects(
    normalizeValidationMode(selectedRuleSet.value?.validation_mode || 'customer'),
  )
  if (!isLuxian0609Mode.value) {
    clearLuxianRuleScope()
  }
  pagination.value.page = 1
  selectedRowKeys.value = []
  await loadRecords()
}

async function handleValidationModeChange(mode: ManualSampleValidationMode | string | number) {
  const normalizedMode = normalizeValidationMode(mode)
  const matchedRuleSet =
    ruleSets.value.find(
      (item) => item.advanced && normalizeValidationMode(item.validation_mode) === normalizedMode,
    ) ||
    fallbackRuleSets.find(
      (item) => item.advanced && normalizeValidationMode(item.validation_mode) === normalizedMode,
    ) ||
    ruleSets.value.find(
      (item) => normalizeValidationMode(item.validation_mode) === normalizedMode,
    ) ||
    fallbackRuleSets.find(
      (item) => normalizeValidationMode(item.validation_mode) === normalizedMode,
    )
  selectedRuleSetKey.value = matchedRuleSet?.rule_set_key || LUXIAN_0609_RULE_SET_KEY
  await handleRuleSetChange(selectedRuleSetKey.value)
}

async function handleMoreActionKey(key: string) {
  if (key === 'import') {
    importModalOpen.value = true
    return
  }
  if (key === 'create-test-record') {
    openTestRecordDrawer()
    return
  }
  if (key === 'refresh') {
    await loadPools()
    return
  }
  if (key === 'sync') {
    await handleSyncPoolRecords()
    return
  }
  if (key === 'match') {
    await handleMatchPool()
    return
  }
  if (key === 'latest') {
    await openLatestJob()
    return
  }
  if (key === 'export-luxian-md') {
    await handleExportLuxianReport('md')
    return
  }
  if (key === 'export-luxian-csv') {
    await handleExportLuxianReport('csv')
    return
  }
  if (key === 'export-luxian-json') {
    await handleExportLuxianReport('json')
    return
  }
  if (key === 'mode-sc') {
    await handleValidationModeChange('sc')
    return
  }
  if (key === 'mode-programmatic') {
    await handleValidationModeChange('programmatic')
    return
  }
  if (key === 'mode-legacy-customer') {
    selectedRuleSetKey.value = LEGACY_CUSTOMER_RULE_SET_KEY
    await handleRuleSetChange(selectedRuleSetKey.value)
  }
}

async function handleExportLuxianReport(format: 'md' | 'csv' | 'json') {
  const result = await exportLuxian0609EvaluationReport(format)
  if (!result.success || !result.data) {
    message.error(result.message || '导出泸县0609质控点评估报告失败')
    return
  }
  const blob = new Blob([result.data], {
    type:
      format === 'json'
        ? 'application/json;charset=utf-8'
        : format === 'csv'
          ? 'text/csv;charset=utf-8'
          : 'text/markdown;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `泸县0609质控点评估报告.${format}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  message.success('泸县0609质控点评估报告已导出')
}

function resetFilters() {
  filters.value = {
    query: '',
    coverageType: undefined,
    matchStatus: undefined,
    includeInBatch: !isSyncedOnlyValidationMode.value,
  }
  pagination.value.page = 1
  selectedRowKeys.value = []
  loadRecords()
}

function resetImportForm() {
  importModalOpen.value = false
  importForm.value = {
    poolName: '',
    description: '',
  }
  importFileList.value = []
}

const handleImportFileSelect: UploadProps['beforeUpload'] = (file) => {
  importFileList.value = [
    {
      uid: file.uid,
      name: file.name,
      status: 'done',
      size: file.size,
      type: file.type,
      originFileObj: file,
    },
  ]
  return false
}

async function handleImportPool() {
  const poolName = importForm.value.poolName.trim()
  const file = importFileList.value[0]?.originFileObj
  if (!poolName) {
    message.warning('请先填写样本池名称')
    return
  }
  if (!file) {
    message.warning('请先上传 Excel 模板')
    return
  }
  importingPool.value = true
  const result = await importManualSamplePoolByUpload({
    pool_name: poolName,
    description: importForm.value.description.trim(),
    scene: 'running',
    file,
  })
  importingPool.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '导入客户样本模板失败')
    return
  }
  selectedPoolId.value = result.data.id
  importWorkflow.value = {
    poolId: result.data.id,
    poolName: result.data.name || poolName,
    importedRows: Number(result.data.imported_rows || 0),
    matching: true,
    matched: 0,
    ambiguous: 0,
    unmatched: 0,
    status: 'matching',
    message: '已导入样本 ID，正在自动匹配源库病历...',
  }
  resetImportForm()
  message.success(`导入成功，共写入 ${result.data.imported_rows} 条样本，正在匹配源库病历`)
  await loadPools()
  await runPoolMatch({ source: 'import' })
}

async function handleDownloadTemplate() {
  const XLSX = await import('xlsx')
  const workbook = XLSX.utils.book_new()
  const worksheet = XLSX.utils.aoa_to_sheet([
    ['就诊ID', '住院流水号', '病案号', '患者姓名', '备注'],
    ['1870471', 'IP0000135258', '362948', '蒲云鹏', '示例：优先填写就诊ID'],
    ['1430048', '', '', '', '没有住院流水号/病案号时，可只填就诊ID'],
  ])
  worksheet['!cols'] = [{ wch: 18 }, { wch: 20 }, { wch: 16 }, { wch: 14 }, { wch: 34 }]
  XLSX.utils.book_append_sheet(workbook, worksheet, '样本ID')

  const instructionSheet = XLSX.utils.aoa_to_sheet([
    ['字段', '是否必填', '说明'],
    ['就诊ID', '推荐必填', '最可靠的匹配字段，对应源库 visit_id。'],
    ['住院流水号', '可选', '对应源库 inpat_no，例如 IP0000135258。'],
    ['病案号', '可选', '对应源库 mr_no，例如 362948。'],
    ['患者姓名', '可选', '只用于人工核对，不作为唯一匹配键。'],
    ['备注', '可选', '客户自定义来源或批次说明。'],
  ])
  instructionSheet['!cols'] = [{ wch: 16 }, { wch: 12 }, { wch: 48 }]
  XLSX.utils.book_append_sheet(workbook, instructionSheet, '填写说明')
  XLSX.writeFile(workbook, '客户样本导入模板.xlsx')
}

function resolveRecordPatientName(record: ManualSamplePoolRecord): string {
  return String(record.patient_name || '').trim() || '-'
}

function resolveRecordCaseTitle(record: ManualSamplePoolRecord): string {
  const caseTitle = record.sample_items
    .map((item) => {
      const rawPayload = item.raw_payload || {}
      return typeof rawPayload.case_title === 'string' ? rawPayload.case_title.trim() : ''
    })
    .find(Boolean)
  return caseTitle || ''
}

function resolveRecordMainDiagnosis(record: ManualSamplePoolRecord): string {
  for (const item of record.sample_items || []) {
    const rawPayload = item.raw_payload || {}
    const basicInfo = rawPayload.basic_info
    const candidates = [
      rawPayload.main_diagnosis,
      rawPayload.diagnosis,
      typeof basicInfo === 'object' && basicInfo !== null
        ? (basicInfo as Record<string, unknown>).main_diagnosis
        : undefined,
      typeof basicInfo === 'object' && basicInfo !== null
        ? (basicInfo as Record<string, unknown>).diagnosis
        : undefined,
    ]
    const diagnosis = candidates
      .map((value) => (typeof value === 'string' ? value.trim() : ''))
      .find(Boolean)
    if (diagnosis) return diagnosis
  }
  return ''
}

function resolveRecordDisplayTitle(record: ManualSamplePoolRecord): string {
  const caseTitle = resolveRecordCaseTitle(record)
  if (caseTitle) {
    const cleaned = caseTitle
      .replace(/[-_]\d{10,}$/u, '')
      .replace(/CUSTOMER_TEST_\d+[A-Z0-9]*$/u, '')
      .replace(/[｜|]\s*LX(?:0609-)?\d{3}(?:[/、,，]\s*(?:LX(?:0609-)?)?\d{3})*\s*/u, '')
      .replace(/[｜|]\s*\d{2,4}[-_/年]?\d{1,2}[-_/月]?\d{1,2}日?\s*\d{0,2}:?\d{0,2}\s*$/u, '')
      .replace(/[｜|]\s*\d{4}[-_/]?\d{2}[-_/]?\d{2}[-_/]?\d{0,6}\s*$/u, '')
      .replace(/[｜|]\s*\d{4}-\d{4}\s*$/u, '')
      .replace(/[-_]\d{13,}$/u, '')
      .replace(/\s+/gu, ' ')
      .trim()
    return cleaned || caseTitle
  }
  return resolveRecordPatientName(record)
}

function resolveRecordPatientTitle(record: ManualSamplePoolRecord): string {
  const patientName = resolveRecordPatientName(record)
  let title = resolveRecordDisplayTitle(record).replace(/病历$/u, '').trim()
  if (patientName !== '-' && title.startsWith(patientName)) {
    title = title
      .slice(patientName.length)
      .replace(/^[\s·・,，:：-]+/u, '')
      .trim()
  }
  if (!title || title === patientName) return patientName === '-' ? '-' : patientName
  return [patientName === '-' ? '' : patientName, title].filter(Boolean).join(' · ') || '-'
}

function resolveRecordIdentifier(record: ManualSamplePoolRecord): string {
  const rawVisitId = String(record.sample_items?.[0]?.visit_id || '').trim()
  return (
    String(record.mr_no || '').trim() ||
    rawVisitId ||
    String(record.matched_visit_id || '').trim() ||
    '-'
  )
}

function resolveRecordDisplayCode(record: ManualSamplePoolRecord): string {
  const identifier = resolveRecordIdentifier(record)
  if (/^CUSTOMER_TEST_/u.test(identifier.trim())) {
    const displayTime = formatRecordCodeTime(recordSortTime(record))
    if (displayTime) return `测试-${displayTime}`
  }
  const customerTestMatch = identifier
    .trim()
    .match(/^CUSTOMER_TEST_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})\d{0,2}[A-Z0-9]*$/u)
  if (customerTestMatch) {
    const [, , month, day, hour, minute] = customerTestMatch
    return `测试-${month}${day}-${hour}${minute}`
  }
  return resolveRecordShortIdentifier(record).replace(/^编号\s*/u, '')
}

function resolveRecordShortIdentifier(record: ManualSamplePoolRecord): string {
  const identifier = resolveRecordIdentifier(record)
  if (identifier === '-') return '-'
  const normalized = identifier.trim()
  const customerTestMatch = normalized.match(/^CUSTOMER_TEST_(\d{8})(\d{4,6})([A-Z0-9]+)$/u)
  if (customerTestMatch) {
    const [, , , suffix] = customerTestMatch
    return `编号 ${suffix.slice(-6)}`
  }
  return normalized.length > 22 ? `编号 ...${normalized.slice(-10)}` : `编号 ${normalized}`
}

function resolveRecordCreatedDate(record: ManualSamplePoolRecord): string {
  const raw = recordSortTime(record)
  if (!raw) return ''
  return formatCompactDate(raw)
}

function formatRecordCodeTime(value: string): string {
  const text = value.trim()
  if (!text) return ''
  const date = parseBackendDateTime(text)
  if (Number.isNaN(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const getPart = (type: string) => parts.find((part) => part.type === type)?.value || ''
  return `${getPart('month')}${getPart('day')}-${getPart('hour')}${getPart('minute')}`
}

function formatCompactDate(value: string): string {
  const text = value.trim()
  if (!text) return ''
  const date = parseBackendDateTime(text)
  if (Number.isNaN(date.getTime())) return text
  const parts = new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const getPart = (type: string) => parts.find((part) => part.type === type)?.value || ''
  return `${getPart('year')}-${getPart('month')}-${getPart('day')}`
}

function parseBackendDateTime(value: string): Date {
  const text = value.trim()
  const normalized = text.includes('T') ? text : text.replace(' ', 'T')
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const normalizedWithMilliseconds = normalized.replace(/\.(\d{3})\d+/u, '.$1')
  return new Date(hasTimezone ? normalizedWithMilliseconds : `${normalizedWithMilliseconds}Z`)
}

function openRecordDetail(record: ManualSamplePoolRecord) {
  activeRecord.value = record
  detailOpen.value = true
}

function openReviewDrawer(record: ManualSamplePoolRecord) {
  if (!record.matched_visit_id) {
    message.warning('当前样本尚未匹配到病历，无法查看原文')
    return
  }
  reviewDrawerRecord.value = {
    id: record.id,
    record_id: record.matched_visit_id,
    patient_name: record.patient_name,
    department: record.department,
    defect_count: 0,
    status: record.match_status || 'pending',
  }
  reviewDrawerVisible.value = true
}

async function loadEditableCopyDocuments(record: ManualSamplePoolRecord): Promise<boolean> {
  editableCopySourceRecord.value = record
  editableCopyDraft.value = null
  editableCopyOpen.value = true
  editableCopyLoading.value = true
  const result = await getEditableMedicalRecordDocuments(record.matched_visit_id || '', {
    institute_id: record.matched_institute_id,
    patient_id: record.matched_patient_id,
    visit_id: record.matched_visit_id,
  })
  editableCopyLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '读取源病历文书失败')
    return false
  }
  if (!result.data.documents.length) {
    message.warning('当前源病历未读取到可编辑文书')
  }
  editableCopyDraft.value = buildEditableCopyDraft(record, result.data.documents, {
    readonly: editableCopyReadonly.value,
  })
  editableCopyDocumentQuery.value = ''
  editableCopyDocumentFilter.value = 'all'
  editableCopyOrderTypeFilter.value = editableCopyOrderRows.value.some(
    (row) => row.orderTypeKey === 'temporary',
  )
    ? 'temporary'
    : 'long'
  editableCopyActiveDocumentKey.value = editableCopyDraft.value.documents[0]?.key || ''
  return true
}

async function openMedicalRecordViewer(record: ManualSamplePoolRecord) {
  if (!record.matched_visit_id) {
    message.warning('当前样本尚未匹配到病历，无法查看原文')
    return
  }
  editableCopyReadonly.value = true
  await loadEditableCopyDocuments(record)
}

function resolveEditableCopyTitle(record: ManualSamplePoolRecord): string {
  const title = resolveRecordDisplayTitle(record)
  if (title && title !== '-') return `${title}编辑副本`
  const patientName = resolveRecordPatientName(record)
  return `${patientName === '-' ? '源病历' : patientName}编辑副本`
}

function resolveEditableCopyAdmissionTime(record: ManualSamplePoolRecord): string {
  const raw = record.created_at || record.updated_at || new Date().toISOString()
  const parsed = parseBackendDateTime(raw)
  if (Number.isNaN(parsed.getTime())) return new Date().toISOString().slice(0, 16)
  return parsed.toISOString().slice(0, 16)
}

function isEditableOrderDocument(
  document?: Partial<EditableMedicalRecordDocument> | null,
): boolean {
  const probe = [document?.document_type, document?.title, document?.source_table, document?.key]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  return (
    probe.includes('order') ||
    probe.includes('医嘱') ||
    probe.includes('长期') ||
    probe.includes('临时')
  )
}

function editableOrderContentLines(document: EditableMedicalRecordDocument): string[] {
  return String(document.content || '')
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean)
}

function resolveEditableOrderKindFromContent(
  document: EditableMedicalRecordDocument,
): EditableCopyOrderTypeFilter | null {
  const firstLine = editableOrderContentLines(document)[0] || ''
  const normalized = firstLine.replace(/\s+/gu, '')
  if (/^长期(医嘱)?[:：]?$/u.test(normalized) || /^长期医嘱[:：]/u.test(normalized)) return 'long'
  if (/^临时(医嘱)?[:：]?$/u.test(normalized) || /^临时医嘱[:：]/u.test(normalized))
    return 'temporary'
  return null
}

function resolveEditableOrderTypeLabel(document: EditableMedicalRecordDocument): string {
  const kindFromContent = resolveEditableOrderKindFromContent(document)
  if (kindFromContent === 'long') return '长期医嘱'
  if (kindFromContent === 'temporary') return '临时医嘱'
  const probe = [document.document_type, document.title, document.source_table, document.key]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  if (probe.includes('临时') || probe.includes('temp')) return '临时医嘱'
  if (probe.includes('长期') || probe.includes('long')) return '长期医嘱'
  if (probe.includes('出院')) return '出院医嘱'
  if (probe.includes('drug') || probe.includes('药')) return '药品医嘱'
  return '医嘱'
}

function resolveEditableOrderTypeKey(
  document: EditableMedicalRecordDocument,
): EditableCopyOrderTypeFilter {
  const kindFromContent = resolveEditableOrderKindFromContent(document)
  if (kindFromContent) return kindFromContent
  const label = resolveEditableOrderTypeLabel(document)
  if (label.includes('长期')) return 'long'
  if (label.includes('临时')) return 'temporary'
  const probe = [document.document_type, document.title, document.source_table, document.key]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  if (probe.includes('long') || probe.includes('长期')) return 'long'
  return 'temporary'
}

function normalizeEditableOrderTimeText(value?: string, fallback = '-'): string {
  const raw = String(value || '').trim()
  if (!raw) return fallback
  const parsed = parseBackendDateTime(raw)
  if (Number.isNaN(parsed.getTime())) return raw.replace('T', ' ').slice(0, 19)
  return parsed.toISOString().slice(0, 19).replace('T', ' ')
}

function resolveEditableOrderStartTimeValue(document: EditableMedicalRecordDocument): string {
  return document.order_start_time || document.record_time || document.submit_time || ''
}

function resolveEditableOrderStopTimeValue(document: EditableMedicalRecordDocument): string {
  return document.order_stop_time || ''
}

function editableOrderTimeValue(document: EditableMedicalRecordDocument): number {
  const parsed = parseBackendDateTime(resolveEditableOrderStartTimeValue(document))
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime()
}

function compareEditableOrderDocumentByTimeDesc(
  left: EditableMedicalRecordDocument,
  right: EditableMedicalRecordDocument,
): number {
  return editableOrderTimeValue(right) - editableOrderTimeValue(left)
}

function stripEditableOrderPrefix(value: string): string {
  return value
    .replace(/^(长期医嘱|临时医嘱|医嘱记录|医嘱)[:：]\s*/u, '')
    .replace(/^(长期|临时)(医嘱)?[:：]?\s*/u, '')
    .trim()
}

function isEditableOrderKindLine(value: string): boolean {
  return /^(长期|临时)(医嘱)?[:：]?$/u.test(value.replace(/\s+/gu, ''))
}

function isEditableOrderStatusLine(value: string): boolean {
  return /^(新开|开立|停止|停用|作废|撤销|执行中|已执行|未执行)$/u.test(value.trim())
}

function isEditableOrderCategoryLine(value: string): boolean {
  return /^(用药|药品|护理|治疗|处置|检查|检验|手术|麻醉|输血|会诊|康复|膳食|嘱托|其他)$/u.test(
    value.trim(),
  )
}

function resolveEditableOrderCategoryText(document: EditableMedicalRecordDocument): string {
  const lines = editableOrderContentLines(document)
    .map((line) => stripEditableOrderPrefix(line))
    .filter(Boolean)
  const explicitCategory = lines.find((line) => isEditableOrderCategoryLine(line))
  if (explicitCategory) return explicitCategory === '药品' ? '用药' : explicitCategory

  const probe = [
    document.document_type,
    document.title,
    document.source_table,
    document.key,
    document.content,
  ]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  if (probe.includes('drug') || probe.includes('药')) return '用药'
  if (probe.includes('nursing') || probe.includes('护理')) return '护理'
  if (probe.includes('blood') || probe.includes('输血')) return '输血'
  if (probe.includes('exam') || probe.includes('检查')) return '检查'
  if (probe.includes('lab') || probe.includes('检验')) return '检验'
  if (probe.includes('surg') || probe.includes('手术')) return '手术'
  return '医嘱'
}

function resolveEditableOrderItemText(document: EditableMedicalRecordDocument): string {
  const lines = editableOrderContentLines(document)
    .map((line) => stripEditableOrderPrefix(line))
    .filter(
      (line) => Boolean(line) && !isEditableOrderKindLine(line) && !isEditableOrderStatusLine(line),
    )
  const category = lines.find((line) => isEditableOrderCategoryLine(line))
  const candidateLines =
    category && lines.length > 1 ? lines.filter((line) => line !== category) : lines
  const firstLine =
    candidateLines[0] || stripEditableOrderPrefix(document.title || document.document_type || '')
  if (!firstLine || isEditableOrderKindLine(firstLine)) return '-'
  return firstLine.replace(/\s+/gu, ' ').slice(0, 80)
}

function resolveEditableOrderStatus(document: EditableMedicalRecordDocument): string {
  if (document.enabled === false) return '不写入'
  const lines = editableOrderContentLines(document).map((line) => stripEditableOrderPrefix(line))
  const explicitStatus = lines.find((line) => isEditableOrderStatusLine(line))
  if (explicitStatus) return explicitStatus
  const text = `${document.title || ''} ${document.content || ''}`.toLowerCase()
  if (text.includes('停止') || text.includes('停用') || text.includes('停')) return '停止'
  if (text.includes('新开') || text.includes('开立') || document.is_new) return '新开'
  if (text.includes('执行')) return '执行中'
  return '新开'
}

function parseEditableOrderRow(document: EditableMedicalRecordDocument): EditableCopyOrderRow {
  const orderTypeKey = resolveEditableOrderTypeKey(document)
  return {
    document,
    startTime: normalizeEditableOrderTimeText(resolveEditableOrderStartTimeValue(document)),
    stopTime: normalizeEditableOrderTimeText(resolveEditableOrderStopTimeValue(document), ''),
    orderType: resolveEditableOrderCategoryText(document),
    item: resolveEditableOrderItemText(document),
    status: resolveEditableOrderStatus(document),
    orderTypeKey,
  }
}

function editableDocumentTypeLabel(documentType: string): string {
  return (
    testRecordDocumentTypeOptions.find((option) => option.value === documentType)?.label ||
    documentType ||
    '文书'
  )
}

function editableCopyDocumentGroupKey(document: EditableMedicalRecordDocument): string {
  const probe = `${document.document_type || ''} ${document.title || ''}`.toLowerCase()
  if (isEditableOrderDocument(document)) return 'order'
  if (probe.includes('入院')) return 'admission'
  if (probe.includes('病程') || probe.includes('查房') || probe.includes('course')) return 'course'
  if (
    probe.includes('手术') ||
    probe.includes('麻醉') ||
    probe.includes('surg') ||
    probe.includes('anesthesia')
  ) {
    return 'surgery'
  }
  if (
    probe.includes('检查') ||
    probe.includes('检验') ||
    probe.includes('报告') ||
    probe.includes('影像') ||
    probe.includes('培养') ||
    probe.includes('lab') ||
    probe.includes('exam')
  ) {
    return 'exam_lab'
  }
  return 'other'
}

function editableCopyDocumentGroupLabel(key: string): string {
  const labels: Record<string, string> = {
    admission: '入院记录',
    course: '病程记录',
    order: '医嘱',
    surgery: '手术麻醉',
    exam_lab: '检查检验',
    other: '其他文书',
  }
  return labels[key] || '其他文书'
}

function formatEditableCopyDocumentMeta(document: EditableMedicalRecordDocument): string {
  const timeText = document.record_time || '未返回时间'
  const lengthText = `${String(document.content || '').trim().length}字`
  const stateText =
    document.enabled === false ? '已从副本删除' : document.is_new ? '新增' : '源文书'
  return `${timeText} · ${lengthText} · ${stateText}`
}

function formatEditableCopyOrderGroupMeta(documents: EditableMedicalRecordDocument[]): string {
  const longCount = documents.filter(
    (document) => resolveEditableOrderTypeKey(document) === 'long',
  ).length
  const temporaryCount = documents.filter(
    (document) => resolveEditableOrderTypeKey(document) === 'temporary',
  ).length
  return `长期 ${longCount} 条 · 临时 ${temporaryCount} 条`
}

function selectEditableCopyDocument(key: string) {
  editableCopyActiveDocumentKey.value = key
  const document = editableCopyAllDocuments.value.find((item) => item.key === key)
  if (document && isEditableOrderDocument(document)) {
    editableCopyOrderTypeFilter.value = resolveEditableOrderTypeKey(document)
  }
}

function selectEditableCopyOrderGroup() {
  const rows = editableCopyVisibleOrderRows.value.length
    ? editableCopyVisibleOrderRows.value
    : editableCopyOrderRows.value
  const first = rows[0]?.document
  if (first) {
    editableCopyActiveDocumentKey.value = first.key
    editableCopyOrderTypeFilter.value = resolveEditableOrderTypeKey(first)
  }
}

function createEditableCopyDocument(documentType: string): EditableMedicalRecordDocument {
  const normalizedType =
    String(documentType || 'daily_course_record').trim() || 'daily_course_record'
  const title = editableDocumentTypeLabel(normalizedType)
  const timestamp = Date.now()
  return {
    key: `editable-new-${normalizedType}-${timestamp}`,
    document_type: normalizedType,
    title,
    record_time: new Date().toISOString().slice(0, 16),
    submit_time: '',
    content:
      normalizedType === 'medical_order'
        ? '请填写医嘱名称、剂量、频次、用法、开立时间、停止时间及开立医师。'
        : `请填写${title}正文。`,
    doctor_name: '',
    enabled: true,
    is_new: true,
  }
}

function addEditableCopyDocument(documentType = editableCopyNewDocumentType.value) {
  if (!editableCopyDraft.value) return
  const document = createEditableCopyDocument(documentType)
  editableCopyDraft.value.documents.push(document)
  editableCopyActiveDocumentKey.value = document.key
}

function addEditableCopyOrderDocument() {
  addEditableCopyDocument('medical_order')
}

function removeEditableCopyDocument(document: EditableMedicalRecordDocument) {
  const draft = editableCopyDraft.value
  if (!draft) return
  if (document.is_new) {
    draft.documents = draft.documents.filter((item) => item.key !== document.key)
    if (editableCopyActiveDocumentKey.value === document.key) {
      editableCopyActiveDocumentKey.value = draft.documents[0]?.key || ''
    }
    return
  }
  document.enabled = document.enabled === false
  editableCopyActiveDocumentKey.value = document.key
}

function buildEditableCopyDraft(
  record: ManualSamplePoolRecord,
  documents: EditableMedicalRecordDocument[],
  options: { readonly?: boolean } = {},
): EditableCopyDraft {
  const patientName = resolveRecordPatientName(record)
  const readonlyMode = options.readonly === true
  const sourceTitle = resolveRecordDisplayTitle(record)
  const sourceDiagnosis = resolveRecordMainDiagnosis(record)
  const normalizedDocuments = documents.map((document, index) => ({
    ...document,
    key: document.key || `${document.document_type || 'document'}-${index + 1}`,
    title: document.title || document.document_type || `文书 ${index + 1}`,
    document_type: document.document_type || document.title || '日常病程记录',
    enabled: document.enabled !== false,
    content: document.content || '',
  }))
  return {
    caseTitle: readonlyMode
      ? sourceTitle || resolveRecordIdentifier(record)
      : resolveEditableCopyTitle(record),
    patientName: patientName === '-' ? '脱敏患者' : patientName,
    sex: '未说明',
    age: 50,
    mrNo: '',
    department: record.department || '未说明科室',
    admissionTime: resolveEditableCopyAdmissionTime(record),
    dischargeTime: '',
    mainDiagnosis: readonlyMode ? sourceDiagnosis || '未返回' : sourceDiagnosis || '源病历编辑副本',
    manualIssueText: readonlyMode
      ? `源病历：${resolveRecordIdentifier(record)}。当前仅查看已同步文书原文。`
      : `源病历编辑副本：${resolveRecordIdentifier(record)}。原始同步病历保持只读，本副本用于客户自定义修改后验证。`,
    documents: normalizedDocuments,
  }
}

async function openEditableCopyDrawer(record: ManualSamplePoolRecord) {
  if (!record.matched_visit_id) {
    message.warning('当前样本尚未匹配到病历，无法创建编辑副本')
    return
  }
  editableCopyReadonly.value = false
  await loadEditableCopyDocuments(record)
}

function closeEditableCopyDrawer() {
  if (editableCopySaving.value || editableCopySaveAndRunLoading.value) return
  editableCopyOpen.value = false
  editableCopyReadonly.value = false
  editableCopySourceRecord.value = null
  editableCopyDraft.value = null
  editableCopyActiveDocumentKey.value = ''
  editableCopyDocumentQuery.value = ''
  editableCopyDocumentFilter.value = 'all'
}

function buildEditableCopySourceMeta(record: ManualSamplePoolRecord) {
  return {
    type: 'customer_source_editable_copy',
    source_pool_id: selectedPool.value?.id || selectedPoolId.value || '',
    source_pool_name: selectedPool.value?.name || '',
    source_record_id: record.id,
    source_item_ids: record.sample_item_ids || [],
    source_visit_id: record.matched_visit_id || '',
    source_mr_no: record.mr_no || '',
    source_patient_name: record.patient_name || '',
    source_department: record.department || '',
    created_from: 'customer_sample_validation',
  }
}

function normalizeEditableCopyDateTime(value?: string): string | undefined {
  const text = String(value || '').trim()
  if (!text || text === '-' || text === '未返回') return undefined
  const parsed = parseBackendDateTime(text)
  if (Number.isNaN(parsed.getTime())) return undefined
  return parsed.toISOString()
}

function buildEditableCopyPayload(
  record: ManualSamplePoolRecord,
): ManualTestRecordCreateRequest | null {
  const draft = editableCopyDraft.value
  if (!draft) return null
  const enabledDocuments = draft.documents
    .filter((document) => document.enabled !== false)
    .map((document) => ({
      document_type: document.document_type,
      title: document.title,
      record_time: normalizeEditableCopyDateTime(document.record_time),
      submit_time: normalizeEditableCopyDateTime(document.submit_time),
      content: document.content,
      doctor_name: document.doctor_name,
      doctor_code: document.doctor_code,
      enabled: true,
    }))
    .filter((document) => document.content.trim())
  return {
    case_title: draft.caseTitle.trim() || resolveEditableCopyTitle(record),
    basic_info: {
      patient_name: draft.patientName.trim() || '脱敏患者',
      sex: draft.sex.trim() || '未说明',
      age: Number.isFinite(draft.age) ? draft.age : 50,
      mr_no: draft.mrNo.trim() || undefined,
      department: draft.department.trim() || record.department || '未说明科室',
      admission_time:
        normalizeEditableCopyDateTime(draft.admissionTime) || new Date().toISOString(),
      discharge_time: normalizeEditableCopyDateTime(draft.dischargeTime),
      main_diagnosis: draft.mainDiagnosis.trim() || '源病历编辑副本',
    },
    documents: enabledDocuments,
    selected_rule_ids: isLuxian0609Mode.value
      ? normalizeLuxianRuleIds(selectedLuxianCustomerRuleIds.value)
      : [],
    manual_issue_text: draft.manualIssueText.trim(),
    template_key: 'customer_source_editable_copy',
    source: buildEditableCopySourceMeta(record),
  }
}

async function saveEditableCopy(options: { runAfterSave: boolean }) {
  if (editableCopyReadonly.value) {
    message.warning('当前为只读查看模式，不能保存测试病历')
    return
  }
  const sourceRecord = editableCopySourceRecord.value
  const payload = sourceRecord ? buildEditableCopyPayload(sourceRecord) : null
  if (!sourceRecord || !payload) {
    message.warning('请先读取源病历文书')
    return
  }
  if (!payload.documents.length) {
    message.warning('至少保留一份有正文的文书后再保存')
    return
  }
  if (options.runAfterSave && isLuxian0609Mode.value && !payload.selected_rule_ids?.length) {
    message.warning('请先选择要验证的 LX0609 质控点')
    return
  }
  if (options.runAfterSave) {
    editableCopySaveAndRunLoading.value = true
  } else {
    editableCopySaving.value = true
  }
  const createResult = await createManualTestMedicalRecord(payload)
  if (options.runAfterSave) {
    editableCopySaveAndRunLoading.value = false
  } else {
    editableCopySaving.value = false
  }
  if (!createResult.success || !createResult.data) {
    message.error(createResult.message || '保存编辑副本失败')
    return
  }
  message.success('编辑副本已保存为自建测试病历')
  editableCopyOpen.value = false
  const createdVisitId = createResult.data.visit_id
  await loadPools()
  if (selectedPoolId.value !== CUSTOMER_TEST_POOL_ID) {
    selectedPoolId.value = CUSTOMER_TEST_POOL_ID
    selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
  }
  await loadRecords()
  if (!options.runAfterSave) return

  const runPayload = {
    record_ids: [createdVisitId],
    max_parallel_records: 1,
    validation_mode: selectedValidationMode.value,
    rule_set_key: selectedRuleSetPayloadKey.value,
    selected_rule_ids: payload.selected_rule_ids,
  }
  const runResult = await runManualSamplePool(CUSTOMER_TEST_POOL_ID, runPayload, {
    timeout: SAMPLE_RULE_SET_RUN_TIMEOUT_MS,
  })
  if (!runResult.success || !runResult.data) {
    message.error(runResult.message || '编辑副本已保存，但发起验证失败')
    return
  }
  message.success('编辑副本验证任务已创建')
  await openBatchJob(runResult.data.job_id, {
    visitId: createdVisitId,
    recordId: createResult.data.item?.id || createdVisitId,
    label: [payload.basic_info.patient_name, payload.basic_info.department, createdVisitId]
      .filter(Boolean)
      .join(' · '),
  })
}

function formatMatchSummary(matched: number, ambiguous: number, unmatched: number) {
  return `匹配 ${matched} 份，待人工确认 ${ambiguous} 份，未找到 ${unmatched} 份`
}

async function runPoolMatch(options: { source: 'import' | 'manual' | 'workflow' }) {
  void options
  if (!selectedPoolId.value) return
  matchLoading.value = true
  if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
    importWorkflow.value = {
      ...importWorkflow.value,
      matching: true,
      status: 'matching',
      message: '正在按就诊ID、住院号、病案号匹配源库病历...',
    }
  }
  const result = await matchManualSamplePool(selectedPoolId.value)
  matchLoading.value = false
  if (!result.success) {
    if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
      importWorkflow.value = {
        ...importWorkflow.value,
        matching: false,
        status: 'match_failed',
        message: result.message || '病历匹配失败，请检查源库连接或稍后重试。',
      }
    }
    message.error(result.message || '执行病历匹配失败')
    return
  }
  const matched = Number(result.data?.matched ?? 0)
  const ambiguous = Number(result.data?.ambiguous ?? 0)
  const unmatched = Number(result.data?.unmatched ?? 0)
  const summary = formatMatchSummary(matched, ambiguous, unmatched)
  if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
    importWorkflow.value = {
      ...importWorkflow.value,
      matching: false,
      matched,
      ambiguous,
      unmatched,
      status: matched > 0 ? 'matched' : 'no_match',
      message:
        matched > 0
          ? '已匹配到源库病历，可以开始同步病历文书。'
          : '没有匹配到病历，请检查 ID 类型或源库配置。',
    }
  }
  if (matched > 0) {
    message.success(summary)
  } else {
    message.warning(`${summary}。没有匹配到病历，请检查 ID 类型或源库配置。`)
  }
  await loadPools()
}

async function handleMatchPool() {
  await runPoolMatch({ source: 'manual' })
}

async function handleSyncPoolRecords() {
  if (!selectedPoolId.value) return
  syncLoading.value = true
  if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
    importWorkflow.value = {
      ...importWorkflow.value,
      status: 'syncing',
      message: '同步任务已创建后会在下方展示进度。',
    }
  }
  const limitToIntrinsic = !isSyncedOnlyValidationMode.value
  const result = await syncManualSamplePoolRecords(selectedPoolId.value, {
    only_intrinsic: limitToIntrinsic,
    include_in_batch_1: limitToIntrinsic,
  })
  syncLoading.value = false
  if (!result.success || !result.data) {
    if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
      importWorkflow.value = {
        ...importWorkflow.value,
        status: importWorkflow.value.matched > 0 ? 'matched' : 'no_match',
        message: result.message || '同步任务创建失败，请检查源库连接或稍后重试。',
      }
    }
    message.error(result.message || '同步样本病历失败')
    return
  }
  if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
    importWorkflow.value = {
      ...importWorkflow.value,
      status: 'syncing',
      message: '同步任务已创建，请在下方查看进度。',
    }
  }
  message.success('样本病历同步任务已创建')
  await openSyncJob(result.data.job_id)
}

async function handleRunPool() {
  if (runLoading.value) return
  if (!selectedPoolId.value) return
  const { selectedCount, runnableCount, skippedCount, runnableRecordIds } =
    selectedRecordStats.value
  if (requiresSelectedRecords.value && selectedCount === 0) {
    message.warning('请先选择要质控的病历')
    return
  }
  if (selectedCount > 0 && runnableCount === 0) {
    message.warning(selectedRecordNotRunnableMessage())
    return
  }
  if (selectedCount > 0 && skippedCount > 0) {
    message.info(
      `已选 ${selectedCount} 份病历，其中 ${runnableCount} 份可执行，${skippedCount} 份将自动跳过`,
    )
  }
  const runKey = buildRunSubmissionKey(
    selectedPoolId.value,
    selectedRuleSetPayloadKey.value,
    selectedValidationMode.value,
    runnableRecordIds,
    isLuxian0609Mode.value ? selectedLuxianCustomerRuleIds.value : [],
  )
  const now = Date.now()
  if (
    lastRunSubmission.value?.key === runKey &&
    now - lastRunSubmission.value.startedAt < RUN_DUPLICATE_GUARD_MS
  ) {
    const reusableJobId = lastRunSubmission.value.jobId || lastRunSubmission.value.jobIds?.[0]
    if (reusableJobId) {
      message.info('任务已创建，正在打开进度')
      await openBatchJob(reusableJobId)
    } else {
      message.info('正式84条质控任务已提交，正在准备执行')
    }
    return
  }
  runLoading.value = true
  lastRunSubmission.value = {
    key: runKey,
    startedAt: now,
  }
  const creatingMessage = isLuxian0609Mode.value
    ? '正在创建泸县0609验证任务...'
    : isFormalFastScreenMode.value
      ? '正式84条质控任务已提交，正在准备执行'
      : '正在创建样本验证任务...'
  message.loading({
    content: creatingMessage,
    key: runKey,
    duration: 0,
  })
  const runPayload: SamplePoolRunPayload = {
    record_ids: runnableRecordIds,
    max_parallel_records: runOptions.value.maxParallelRecords,
    validation_mode: selectedValidationMode.value,
    rule_set_key: selectedRuleSetPayloadKey.value,
  }
  if (isLuxian0609Mode.value && selectedLuxianCustomerRuleIds.value.length) {
    runPayload.selected_rule_ids = selectedLuxianCustomerRuleIds.value
  }
  if (shouldRunLuxianFamiliesInParallel(selectedLuxianCustomerRuleIds.value)) {
    await runLuxianFamilyScopedJobs({
      runKey,
      startedAt: now,
      basePayload: runPayload,
    })
    return
  }
  const result = await runManualSamplePool(
    selectedPoolId.value,
    runPayload,
    requiresSelectedRecords.value ? { timeout: SAMPLE_RULE_SET_RUN_TIMEOUT_MS } : undefined,
  )
  if (!result.success || !result.data) {
    if (
      requiresSelectedRecords.value &&
      (result.errorType === 'timeout' || result.errorType === 'network')
    ) {
      message.info('请求等待较久，正在确认后台任务状态')
      const recovered = await recoverRunAfterSlowRequest({
        poolId: selectedPoolId.value,
        recordIds: runnableRecordIds,
        startedAt: now,
        previousJobId: selectedPool.value?.latest_job_id,
        runKey,
        ruleSetKey: selectedRuleSetPayloadKey.value,
        selectedRuleIds: isLuxian0609Mode.value ? selectedLuxianCustomerRuleIds.value : [],
      })
      runLoading.value = false
      if (recovered) {
        return
      }
    } else {
      runLoading.value = false
    }
    message.destroy(runKey)
    if (lastRunSubmission.value?.key === runKey && !lastRunSubmission.value.jobId) {
      lastRunSubmission.value = undefined
    }
    message.error(result.message || '创建样本验证任务失败')
    return
  }
  runLoading.value = false
  lastRunSubmission.value = {
    key: runKey,
    startedAt: now,
    jobId: result.data.job_id,
  }
  const ruleSetName = String(
    result.data.rule_set_name || validationModeLabel(selectedValidationMode.value),
  ).trim()
  const ruleSetKey = String(result.data.rule_set_key || '').trim()
  const ruleSetDisplay = ruleSetKey ? `${ruleSetKey} / ${ruleSetName}` : ruleSetName
  message.success({
    content: `任务已创建，正在打开进度。${ruleSetDisplay}，覆盖 ${result.data.sample_item_count} 条样本 / ${result.data.record_count} 份病历 / ${result.data.rule_count} 条规则，并发 ${runOptions.value.maxParallelRecords} 份病历`,
    key: runKey,
    duration: 3,
  })
  selectedRowKeys.value = []
  await openBatchJob(result.data.job_id)
  void loadPools()
}

async function runLuxianFamilyScopedJobs(options: {
  runKey: string
  startedAt: number
  basePayload: SamplePoolRunPayload
}) {
  const familyScopes = buildLuxianFamilyRunScopes(selectedLuxianCustomerRuleIds.value)
  const scopedPayload: SamplePoolRunPayload = {
    ...options.basePayload,
    group_by_luxian_family: true,
    selected_rule_ids: selectedLuxianCustomerRuleIds.value,
  }
  const result = await runManualSamplePool(
    selectedPoolId.value,
    scopedPayload,
    requiresSelectedRecords.value ? { timeout: SAMPLE_RULE_SET_RUN_TIMEOUT_MS } : undefined,
  )
  if (!result.success || !result.data) {
    runLoading.value = false
    message.destroy(options.runKey)
    lastRunSubmission.value = undefined
    message.error(result.message || '创建泸县0609总任务失败')
    return
  }

  runLoading.value = false
  const jobId = String(result.data.job_id || '').trim()
  const childJobIds = Array.isArray(result.data.child_job_ids)
    ? result.data.child_job_ids.map((item) => String(item)).filter(Boolean)
    : []
  lastRunSubmission.value = {
    key: options.runKey,
    startedAt: options.startedAt,
    jobId,
    jobIds: [jobId, ...childJobIds],
  }
  message.success({
    content: `已创建泸县0609总任务，${familyScopes.length} 个质控族已并发入队`,
    key: options.runKey,
    duration: 4,
  })
  selectedRowKeys.value = []
  await openLuxianAggregateParentJob(jobId, result.data)
  void loadPools()
}

function buildRunSubmissionKey(
  poolId: string,
  ruleSetKey: string,
  validationMode: ManualSampleValidationMode,
  recordIds: string[],
  selectedRuleIds: string[] = [],
): string {
  const normalizedRecordIds = recordIds.map((item) => String(item)).sort()
  const normalizedRuleIds = normalizeLuxianRuleIds(selectedRuleIds)
  return [
    poolId,
    ruleSetKey || '-',
    validationMode,
    normalizedRecordIds.join(',') || 'all',
    normalizedRuleIds.join(',') || 'full',
  ].join('|')
}

function isCloseToRunStart(createdAt: string | undefined, startedAt: number): boolean {
  if (!createdAt) return true
  const createdTime = new Date(createdAt).getTime()
  if (Number.isNaN(createdTime)) return false
  return Math.abs(createdTime - startedAt) <= 5 * 60 * 1000
}

function isSameRecordScope(job: SichuanBatchJob, recordIds: string[]): boolean {
  if (!recordIds.length || !Array.isArray(job.record_ids) || !job.record_ids.length) {
    return true
  }
  const expected = recordIds
    .map((item) => String(item))
    .sort()
    .join('|')
  const actual = job.record_ids
    .map((item) => String(item))
    .sort()
    .join('|')
  return expected === actual
}

function isSameLuxianRuleScope(job: SichuanBatchJob, selectedRuleIds: string[]): boolean {
  const expected = normalizeLuxianRuleIds(selectedRuleIds)
  const filters = job.filters && typeof job.filters === 'object' ? job.filters : {}
  const actual = normalizeLuxianRuleIds(
    Array.isArray(filters.selected_rule_ids)
      ? filters.selected_rule_ids.map((item) => String(item))
      : [],
  )
  if (!expected.length) {
    return actual.length === 0
  }
  return expected.join('|') === actual.join('|')
}

function isRecoverableRunJob(
  job: SichuanBatchJob,
  recordIds: string[],
  startedAt: number,
  ruleSetKey = FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
  selectedRuleIds: string[] = [],
): boolean {
  return (
    job.rule_set_key === ruleSetKey &&
    isSameRecordScope(job, recordIds) &&
    isSameLuxianRuleScope(job, selectedRuleIds) &&
    isCloseToRunStart(job.created_at, startedAt)
  )
}

async function recoverRunAfterSlowRequest(options: {
  poolId: string
  recordIds: string[]
  startedAt: number
  previousJobId?: string
  runKey: string
  ruleSetKey: string
  selectedRuleIds?: string[]
}): Promise<boolean> {
  await loadPools()
  const refreshedPool = pools.value.find((item) => item.id === options.poolId)
  const latestJobId = refreshedPool?.latest_job_id
  if (!latestJobId || latestJobId === options.previousJobId) {
    return false
  }
  const jobResult = await getSichuanWorkspaceBatchJob(latestJobId)
  if (!jobResult.success || !jobResult.data) {
    return false
  }
  if (
    !isRecoverableRunJob(
      jobResult.data,
      options.recordIds,
      options.startedAt,
      options.ruleSetKey,
      options.selectedRuleIds || [],
    )
  ) {
    return false
  }
  lastRunSubmission.value = {
    key: options.runKey,
    startedAt: options.startedAt,
    jobId: latestJobId,
  }
  message.success({
    content: '任务已创建，正在打开进度',
    key: options.runKey,
    duration: 3,
  })
  await openBatchJob(latestJobId)
  return true
}

async function openLatestJob() {
  if (!selectedPool.value?.latest_job_id) return
  await openBatchJob(selectedPool.value.latest_job_id)
}

async function loadTaskHistory() {
  taskHistoryLoading.value = true
  try {
    const result = await listSichuanWorkspaceBatchJobs({
      page: 1,
      page_size: 20,
    })
    if (!result.success || !result.data) {
      message.error(result.message || '获取质控记录失败')
      return
    }
    taskHistoryJobs.value = result.data.items || []
    taskHistoryTotal.value = Number(result.data.total || taskHistoryJobs.value.length || 0)
    if (taskHistoryJobs.value.some((job) => isBatchJobRunning(job.status))) {
      startTaskHistoryPolling()
    } else {
      stopTaskHistoryPolling()
    }
  } finally {
    taskHistoryLoading.value = false
  }
}

async function openTaskHistoryDrawer() {
  taskHistoryOpen.value = true
  await loadTaskHistory()
}

function closeTaskHistoryDrawer() {
  taskHistoryOpen.value = false
  stopTaskHistoryPolling()
}

async function openTaskHistoryJob(job: SichuanBatchJob) {
  taskHistoryOpen.value = false
  stopTaskHistoryPolling()
  await openBatchJob(job.id)
}

function resolveLuxianFamilyFromChildJob(
  job: SichuanBatchJob,
  fallbackIndex = 0,
): LuxianFamilyRunScope {
  const filters = job.filters && typeof job.filters === 'object' ? job.filters : {}
  const ruleIds = normalizeLuxianRuleIds(
    Array.isArray(filters.scoped_customer_rule_ids)
      ? filters.scoped_customer_rule_ids.map((item) => String(item))
      : Array.isArray(filters.selected_rule_ids)
        ? filters.selected_rule_ids.map((item) => String(item))
        : [],
  )
  const familyKey = String(
    job.family_key || filters.family_key || `family-${fallbackIndex + 1}`,
  ).trim()
  const familyName = String(
    job.family_name || filters.family_name || `质控族 ${fallbackIndex + 1}`,
  ).trim()
  return {
    key: familyKey,
    name: familyName,
    ruleIds,
  }
}

function buildLuxianAggregateJobsFromParentJob(parentJob: SichuanBatchJob): LuxianAggregateJob[] {
  const childJobs = Array.isArray(parentJob.child_jobs)
    ? parentJob.child_jobs
    : Array.isArray(parentJob.children)
      ? parentJob.children
      : []
  if (childJobs.length > 0) {
    return childJobs
      .map((childJob, index) => ({
        family: resolveLuxianFamilyFromChildJob(childJob, index),
        jobId: String(childJob.id || '').trim(),
        status: childJob.status,
        detail: childJob,
        errorMessage: '',
      }))
      .filter((item) => item.jobId)
  }
  const filters =
    parentJob.filters && typeof parentJob.filters === 'object' ? parentJob.filters : {}
  const familyScopes = Array.isArray(filters.family_scopes)
    ? (filters.family_scopes as Array<Record<string, unknown>>)
    : []
  const childJobIds = Array.isArray(parentJob.child_job_ids)
    ? parentJob.child_job_ids.map((item) => String(item)).filter(Boolean)
    : []
  return childJobIds.map((jobId, index) => {
    const familyScope = familyScopes[index] || {}
    return {
      family: {
        key: String(familyScope.key || `family-${index + 1}`),
        name: String(familyScope.name || `质控族 ${index + 1}`),
        ruleIds: normalizeLuxianRuleIds(
          Array.isArray(familyScope.rule_ids)
            ? familyScope.rule_ids.map((item) => String(item))
            : [],
        ),
      },
      jobId,
      status: 'queued' as SichuanBatchJobStatus,
    }
  })
}

async function openLuxianAggregateParentJob(
  parentJobId: string,
  initialRunResult?: ManualSamplePoolRunResult,
) {
  stopLuxianAggregatePolling()
  luxianAggregateParentJobId.value = parentJobId
  if (Array.isArray(initialRunResult?.child_jobs) && initialRunResult.child_jobs.length > 0) {
    luxianAggregateJobs.value = buildLuxianAggregateJobsFromParentJob({
      id: parentJobId,
      status: 'queued',
      scope: 'all',
      rule_code: '',
      rule_name: '',
      filters: {
        family_scopes: initialRunResult.family_scopes || [],
      },
      child_job_ids: initialRunResult.child_job_ids || [],
      child_jobs: initialRunResult.child_jobs,
    })
  } else {
    luxianAggregateJobs.value = (initialRunResult?.child_job_ids || []).map((jobId, index) => {
      const familyScope = Array.isArray(initialRunResult?.family_scopes)
        ? initialRunResult.family_scopes[index]
        : undefined
      return {
        family: {
          key: String(familyScope?.key || `family-${index + 1}`),
          name: String(familyScope?.name || `质控族 ${index + 1}`),
          ruleIds: normalizeLuxianRuleIds(
            Array.isArray(familyScope?.rule_ids)
              ? familyScope.rule_ids.map((item) => String(item))
              : [],
          ),
        },
        jobId: String(jobId),
        status: 'queued' as SichuanBatchJobStatus,
      }
    })
  }
  luxianAggregateOpen.value = true
  void refreshLuxianAggregateJobs(parentJobId)
  startLuxianAggregatePolling()
}

async function refreshLuxianAggregateJobs(parentJobId?: string) {
  const effectiveParentJobId = parentJobId || luxianAggregateParentJobId.value
  if (!luxianAggregateJobs.value.length && !effectiveParentJobId) return
  luxianAggregateLoading.value = true
  try {
    if (effectiveParentJobId) {
      const parentResult = await getSichuanWorkspaceBatchJob(effectiveParentJobId)
      if (parentResult.success && parentResult.data) {
        const aggregateJobs = buildLuxianAggregateJobsFromParentJob(parentResult.data)
        if (aggregateJobs.length > 0) {
          luxianAggregateJobs.value = aggregateJobs
        }
      }
    }
    const nextJobs = await Promise.all(
      luxianAggregateJobs.value.map(async (item) => {
        if (!item.jobId) return item
        const result = await getSichuanWorkspaceBatchJob(item.jobId)
        if (!result.success || !result.data) {
          return {
            ...item,
            errorMessage: result.message || '获取子任务状态失败',
          }
        }
        return {
          ...item,
          status: result.data.status,
          detail: result.data,
          errorMessage: '',
        }
      }),
    )
    luxianAggregateJobs.value = nextJobs
    if (nextJobs.every((item) => !isBatchJobRunning(item.status))) {
      stopLuxianAggregatePolling()
      await loadPools()
      await loadRecords()
    }
  } finally {
    luxianAggregateLoading.value = false
  }
}

function startLuxianAggregatePolling() {
  stopLuxianAggregatePolling()
  luxianAggregatePollTimer = setInterval(() => {
    if (!luxianAggregateOpen.value) {
      stopLuxianAggregatePolling()
      return
    }
    void refreshLuxianAggregateJobs()
  }, 3000)
}

function stopLuxianAggregatePolling() {
  if (luxianAggregatePollTimer) {
    clearInterval(luxianAggregatePollTimer)
    luxianAggregatePollTimer = null
  }
}

function closeLuxianAggregateDrawer() {
  stopLuxianAggregatePolling()
  luxianAggregateOpen.value = false
  luxianAggregateParentJobId.value = ''
}

async function openLuxianAggregateChildJob(item: LuxianAggregateJob) {
  const jobId = String(item.jobId || '').trim()
  if (!jobId) return
  luxianAggregateOpen.value = false
  stopLuxianAggregatePolling()
  await openBatchJob(jobId)
}

function luxianAggregateResultSummary(item: LuxianAggregateJob): string {
  if (item.detail) return taskHistoryResultSummary(item.detail)
  if (item.status === 'queued') return '任务已创建，等待后台执行。'
  if (item.status === 'running') return '任务执行中，等待结果回写。'
  return item.errorMessage || '暂无结果摘要。'
}

function taskHistoryRuleSetText(job: SichuanBatchJob): string {
  return (
    job.rule_set_name ||
    job.summary?.rule_set_name ||
    (job.rule_set_key === LUXIAN_0609_RULE_SET_KEY ? '泸县0609质控点验证' : job.rule_name) ||
    '样本质控任务'
  )
}

function taskHistoryScopeText(job: SichuanBatchJob): string {
  const filters = job.filters || {}
  const selectedRuleIds = Array.isArray(filters.selected_rule_ids)
    ? filters.selected_rule_ids.map((item) => String(item)).filter(Boolean)
    : []
  const customerRuleCount = Number(job.customer_rule_count || job.summary?.customer_rule_count || 0)
  const executionRuleCount = Number(
    job.execution_rule_count || job.summary?.execution_rule_count || 0,
  )
  if (selectedRuleIds.length > 0) {
    const preview = selectedRuleIds.slice(0, 3).join('、')
    const suffix = selectedRuleIds.length > 3 ? ` +${selectedRuleIds.length - 3}` : ''
    return `${selectedRuleIds.length} 个 LX0609 质控点：${preview}${suffix}`
  }
  if (job.rule_set_key === LUXIAN_0609_RULE_SET_KEY) {
    return customerRuleCount > 0
      ? `全量 0609 规则集 · ${customerRuleCount} 个客户质控点`
      : '全量 0609 规则集'
  }
  if (executionRuleCount > 0) return `${executionRuleCount} 条执行规则`
  return '规则范围未返回'
}

function taskHistoryRecordText(job: SichuanBatchJob): string {
  const totalRecords = Number(
    job.summary?.total_records || job.total_records || job.record_ids?.length || 0,
  )
  if (totalRecords > 0) return `${totalRecords} 份病历`
  return '病历数未返回'
}

function taskHistoryDisplayCounts(job: SichuanBatchJob): Record<string, number> {
  const displayCounts =
    job.summary?.display_status_counts ||
    job.summary?.status_breakdown ||
    job.summary?.postprocess_summary?.display_status_counts ||
    {}
  return {
    non_compliant: Number(displayCounts.non_compliant || 0),
    compliant: Number(displayCounts.compliant || 0),
    not_applicable: Number(displayCounts.not_applicable || 0),
    data_gap: Number(displayCounts.data_gap || 0),
    uncertain: Number(displayCounts.uncertain || 0),
    not_executed: Number(displayCounts.not_executed || 0),
    technical_error: Number(displayCounts.technical_error || 0),
  }
}

function taskHistoryStatusChips(job: SichuanBatchJob) {
  const counts = taskHistoryDisplayCounts(job)
  const chips = [
    {
      key: 'non_compliant',
      label: '不合规',
      value: counts.non_compliant,
      className: 'is-danger',
    },
    {
      key: 'data_gap',
      label: '数据不足',
      value: counts.data_gap,
      className: 'is-warning',
    },
    {
      key: 'uncertain',
      label: '待复核',
      value: counts.uncertain,
      className: 'is-review',
    },
    {
      key: 'technical_error',
      label: '技术异常',
      value: counts.technical_error,
      className: 'is-danger',
    },
    {
      key: 'not_executed',
      label: '未执行',
      value: counts.not_executed,
      className: 'is-neutral',
    },
    {
      key: 'not_applicable',
      label: '不适用',
      value: counts.not_applicable,
      className: 'is-muted',
    },
    {
      key: 'compliant',
      label: '合规',
      value: counts.compliant,
      className: 'is-ok',
    },
  ].filter((chip) => chip.value > 0)

  if (chips.length) return chips

  const issueRecords = Number(job.summary?.issue_records || job.issue_records || 0)
  const compliantRecords = Number(job.summary?.compliant_records || job.compliant_records || 0)
  return [
    issueRecords > 0
      ? {
          key: 'issue_records',
          label: '有问题病历',
          value: issueRecords,
          className: 'is-danger',
        }
      : undefined,
    compliantRecords > 0
      ? {
          key: 'compliant_records',
          label: '合规病历',
          value: compliantRecords,
          className: 'is-ok',
        }
      : undefined,
  ].filter(Boolean) as Array<{ key: string; label: string; value: number; className: string }>
}

function taskHistoryOverviewText(job: SichuanBatchJob): string {
  if (job.status === 'failed') return '任务失败，需要查看错误原因'
  if (isBatchJobRunning(job.status)) {
    const progressPercent = Number(
      job.summary?.progress_percent || job.progress?.progress_percent || 0,
    )
    return progressPercent > 0
      ? `任务执行中，已完成 ${progressPercent}%`
      : '任务执行中，等待结果回写'
  }

  const counts = taskHistoryDisplayCounts(job)
  const issueCount =
    counts.non_compliant + counts.data_gap + counts.uncertain + counts.technical_error
  if (issueCount > 0) {
    const parts = [
      counts.non_compliant > 0 ? `不合规 ${counts.non_compliant}` : '',
      counts.data_gap > 0 ? `数据不足 ${counts.data_gap}` : '',
      counts.uncertain > 0 ? `待复核 ${counts.uncertain}` : '',
      counts.technical_error > 0 ? `技术异常 ${counts.technical_error}` : '',
    ].filter(Boolean)
    return `发现需关注结果：${parts.join('，')}`
  }

  const issueRecords = Number(job.summary?.issue_records || job.issue_records || 0)
  const compliantRecords = Number(job.summary?.compliant_records || job.compliant_records || 0)
  if (issueRecords > 0) return `发现有问题病历 ${issueRecords} 份`
  if (compliantRecords > 0 || counts.compliant > 0) return '本次未发现明确不合规'
  return '暂无结果摘要，点击查看详情'
}

function readTaskHistoryString(value: unknown, key: string): string {
  if (!value || typeof value !== 'object') return ''
  const fieldValue = (value as Record<string, unknown>)[key]
  return typeof fieldValue === 'string' ? fieldValue.trim() : ''
}

function normalizeTaskHistoryIssueStatus(item: SichuanBatchIssueItem): string {
  return String(item.result_status || item.status || '')
    .trim()
    .toLowerCase()
}

function isTaskHistoryAttentionItem(item: SichuanBatchIssueItem): boolean {
  const status = normalizeTaskHistoryIssueStatus(item)
  if (TASK_HISTORY_ATTENTION_STATUSES.has(status)) return true
  return item.is_compliant === false && status !== 'compliant' && status !== 'not_applicable'
}

function normalizeTaskHistoryRuleId(value: unknown): string {
  return normalizeLuxianRuleIds([String(value || '')])[0] || ''
}

function resolveTaskHistoryRuleId(item: SichuanBatchIssueItem): string {
  return (
    normalizeTaskHistoryRuleId(item.qc_point_id) ||
    normalizeTaskHistoryRuleId(item.rule_code) ||
    normalizeTaskHistoryRuleId(item.rule_id)
  )
}

function cleanTaskHistoryIssueSentence(value: string): string {
  const cleaned = String(value || '')
    .replace(/质控结论[:：]/gu, '')
    .replace(/关键证据[:：]/gu, '')
    .replace(/处理建议[:：]/gu, '')
    .replace(/证据模板[:：][^。；;]*[。；;]?/gu, '')
    .replace(/映射执行规则[:：][^。；;]*[。；;]?/gu, '')
    .replace(/来源未标注\s*[·-]?\s*evidence[:：]?/giu, '')
    .replace(/\s+/gu, ' ')
    .trim()
  const firstSentence = cleaned.split(/[。；;\n]/u).find((part) => part.trim()) || cleaned
  const normalized = firstSentence.trim()
  return normalized.length > 34 ? `${normalized.slice(0, 34)}...` : normalized
}

function resolveLuxianHistoryRuleBrief(ruleId: string, fallbackRuleName = ''): string {
  const normalizedRuleId = normalizeTaskHistoryRuleId(ruleId)
  if (!normalizedRuleId) return cleanTaskHistoryIssueSentence(fallbackRuleName)
  if (LUXIAN_0609_HISTORY_BRIEF_BY_ID[normalizedRuleId]) {
    return LUXIAN_0609_HISTORY_BRIEF_BY_ID[normalizedRuleId]
  }
  const catalogRule = luxianRuleFamilies.value
    .flatMap((family) => family.rules)
    .find((rule) => rule.ruleId === normalizedRuleId)
  const rawName = fallbackRuleName || catalogRule?.name || normalizedRuleId
  return cleanTaskHistoryIssueSentence(
    rawName
      .replace(normalizedRuleId, '')
      .replace(/^[\s·:：-]+/u, '')
      .trim(),
  )
}

function resolveTaskHistoryIssueText(item: SichuanBatchIssueItem, ruleId: string): string {
  const decisionConclusion = readTaskHistoryString(item.decision, 'conclusion')
  const issueDescription =
    Array.isArray(item.issues) && item.issues.length
      ? String(item.issues[0]?.description || '').trim()
      : ''
  const rawText =
    item.findings ||
    decisionConclusion ||
    issueDescription ||
    readTaskHistoryString(item.review, 'conclusion') ||
    readTaskHistoryString(item.audit, 'conclusion') ||
    item.rule_name ||
    ''
  const cleaned = cleanTaskHistoryIssueSentence(rawText)
  return cleaned || resolveLuxianHistoryRuleBrief(ruleId, item.rule_name)
}

function collectTaskHistoryIssueItems(job: SichuanBatchJob): SichuanBatchIssueItem[] {
  const items: SichuanBatchIssueItem[] = []
  if (Array.isArray(job.items)) {
    items.push(...job.items)
  }
  for (const ruleResult of job.rule_results || []) {
    if (Array.isArray(ruleResult.items)) {
      items.push(...ruleResult.items)
    }
  }
  return items.filter(isTaskHistoryAttentionItem)
}

function taskHistoryIssueSummaries(job: SichuanBatchJob): TaskHistoryIssueSummary[] {
  const seen = new Set<string>()
  const summaries: TaskHistoryIssueSummary[] = []
  for (const item of collectTaskHistoryIssueItems(job)) {
    const ruleId = resolveTaskHistoryRuleId(item)
    if (!ruleId) continue
    const text = resolveTaskHistoryIssueText(item, ruleId)
    if (!text) continue
    const key = `${ruleId}|${text}`
    if (seen.has(key)) continue
    seen.add(key)
    summaries.push({ key, ruleId, text })
  }
  if (summaries.length) return summaries

  const counts = taskHistoryDisplayCounts(job)
  const attentionCount =
    counts.non_compliant +
    counts.data_gap +
    counts.uncertain +
    counts.not_executed +
    counts.technical_error
  if (attentionCount <= 0) return []

  const filters = job.filters || {}
  const selectedRuleIds = normalizeLuxianRuleIds(
    Array.isArray(filters.selected_rule_ids)
      ? filters.selected_rule_ids.map((item) => String(item))
      : Array.isArray(filters.scoped_customer_rule_ids)
        ? filters.scoped_customer_rule_ids.map((item) => String(item))
        : [],
  )
  return selectedRuleIds.slice(0, attentionCount).map((ruleId) => ({
    key: ruleId,
    ruleId,
    text: resolveLuxianHistoryRuleBrief(ruleId),
  }))
}

function taskHistoryIssueSummaryText(job: SichuanBatchJob): string {
  const summaries = taskHistoryIssueSummaries(job)
  if (!summaries.length) return ''
  const visible = summaries.slice(0, TASK_HISTORY_ISSUE_PREVIEW_LIMIT)
  const suffix = summaries.length > visible.length ? ` 等 ${summaries.length} 个问题点` : ''
  return `问题点：${visible.map((item) => `${item.ruleId} ${item.text}`).join('；')}${suffix}`
}

function taskHistorySecondaryText(job: SichuanBatchJob): string {
  const counts = taskHistoryDisplayCounts(job)
  const totalResults = Object.values(counts).reduce((sum, value) => sum + value, 0)
  const totalRecords = Number(
    job.summary?.total_records || job.total_records || job.record_ids?.length || 0,
  )
  const ruleCount = Number(job.customer_rule_count || job.summary?.customer_rule_count || 0)
  const parts = [
    totalRecords > 0 ? `${totalRecords} 份病历` : '',
    ruleCount > 0 ? `${ruleCount} 个客户质控点` : '',
    totalResults > 0 ? `${totalResults} 条结果` : '',
  ].filter(Boolean)
  if (parts.length) return parts.join(' · ')
  return taskHistoryResultSummary(job)
}

function taskHistoryResultSummary(job: SichuanBatchJob): string {
  if (job.status === 'failed') {
    return job.error_message || '任务失败，点击查看详情。'
  }
  const displayCounts = taskHistoryDisplayCounts(job)
  const statusLabels: Record<string, string> = {
    non_compliant: '不合规',
    compliant: '合规',
    not_applicable: '不适用',
    data_gap: '数据不足',
    uncertain: '待复核',
    not_executed: '未执行',
    technical_error: '技术异常',
  }
  const summary = Object.entries(statusLabels)
    .map(([key, label]) => {
      const count = Number(displayCounts[key] || 0)
      return count > 0 ? `${label} ${count}` : ''
    })
    .filter(Boolean)
    .join('，')
  if (summary) return summary
  const issueRecords = Number(job.summary?.issue_records || job.issue_records || 0)
  const compliantRecords = Number(job.summary?.compliant_records || job.compliant_records || 0)
  if (issueRecords || compliantRecords) {
    return `有问题病历 ${issueRecords}，合规病历 ${compliantRecords}`
  }
  if (isBatchJobRunning(job.status)) {
    const progressPercent = Number(
      job.summary?.progress_percent || job.progress?.progress_percent || 0,
    )
    return progressPercent > 0 ? `任务执行中，进度 ${progressPercent}%` : '任务执行中，等待结果回写'
  }
  return '暂无结果摘要，点击查看详情。'
}

async function loadLatestSyncJob() {
  if (!selectedPoolId.value) {
    syncJobDetail.value = undefined
    stopSyncJobPolling()
    return
  }
  const result = await getLatestManualSamplePoolSyncJob(selectedPoolId.value)
  if (!result.success) return
  syncJobDetail.value = result.data || undefined
  if (syncJobDetail.value && isSyncJobRunning(syncJobDetail.value.status)) {
    startSyncJobPolling(syncJobDetail.value.id)
  } else {
    stopSyncJobPolling()
  }
}

async function openSyncJob(jobId: string) {
  stopSyncJobPolling()
  const result = await getManualSamplePoolSyncJob(jobId)
  if (!result.success || !result.data) {
    message.error(result.message || '获取样本同步任务失败')
    return
  }
  syncJobDetail.value = result.data
  if (isSyncJobRunning(result.data.status)) {
    startSyncJobPolling(jobId)
  } else {
    updateImportWorkflowFromSyncJob(result.data)
    await loadPools()
    await loadRecords()
  }
}

async function openBatchJob(
  jobId: string,
  focusRecord?: { visitId?: string; recordId?: string; label?: string } | null,
) {
  stopBatchJobPolling()
  batchJobLoading.value = true
  batchResultOpen.value = true
  const focusVisitId = String(focusRecord?.visitId || '').trim()
  const focusRecordId = String(focusRecord?.recordId || '').trim()
  batchResultFocusRecord.value =
    focusVisitId || focusRecordId
      ? {
          visitId: focusVisitId,
          recordId: focusRecordId,
          label: String(focusRecord?.label || '').trim(),
        }
      : null
  const result = await getSichuanWorkspaceBatchJob(jobId)
  batchJobLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '获取任务详情失败')
    return
  }
  if (String(result.data.job_kind || '').toLowerCase() === 'parent') {
    batchResultOpen.value = false
    batchJobDetail.value = null
    batchResultFocusRecord.value = null
    await openLuxianAggregateParentJob(jobId)
    return
  }
  batchJobDetail.value = result.data
  if (isBatchJobRunning(result.data.status)) {
    startBatchJobPolling(jobId)
  }
}

function closeBatchDrawer() {
  stopBatchJobPolling()
  batchResultOpen.value = false
  batchJobDetail.value = null
  batchResultFocusRecord.value = null
}

function isBatchJobRunning(status?: string) {
  return isBatchJobCancelable(status)
}

function stopBatchJobPolling() {
  if (batchJobPollTimer) {
    clearInterval(batchJobPollTimer)
    batchJobPollTimer = null
  }
}

function startTaskHistoryPolling() {
  if (taskHistoryPollTimer) return
  taskHistoryPollTimer = setInterval(() => {
    if (!taskHistoryOpen.value) {
      stopTaskHistoryPolling()
      return
    }
    void loadTaskHistory()
  }, 5000)
}

function stopTaskHistoryPolling() {
  if (taskHistoryPollTimer) {
    clearInterval(taskHistoryPollTimer)
    taskHistoryPollTimer = null
  }
}

function isSyncJobRunning(status?: string) {
  const normalized = String(status || '').toLowerCase()
  return normalized === 'queued' || normalized === 'running'
}

function stopSyncJobPolling() {
  if (syncJobPollTimer) {
    clearInterval(syncJobPollTimer)
    syncJobPollTimer = null
  }
}

function startSyncJobPolling(jobId: string) {
  stopSyncJobPolling()
  syncJobPollTimer = setInterval(async () => {
    const result = await getManualSamplePoolSyncJob(jobId)
    if (!result.success || !result.data) return
    syncJobDetail.value = result.data
    if (!isSyncJobRunning(result.data.status)) {
      stopSyncJobPolling()
      updateImportWorkflowFromSyncJob(result.data)
      await loadPools()
      await loadRecords()
    }
  }, 3000)
}

function updateImportWorkflowFromSyncJob(job: ManualSamplePoolSyncJob) {
  if (!importWorkflow.value || importWorkflow.value.poolId !== job.pool_id) return
  const status = String(job.status || '').toLowerCase()
  if (status === 'failed') {
    importWorkflow.value = {
      ...importWorkflow.value,
      status: 'sync_failed',
      message: job.error_message || '同步失败，请检查源库连接或后端日志。',
    }
    return
  }
  if (status !== 'completed') return
  const progress = syncRecordProgress.value
  importWorkflow.value = {
    ...importWorkflow.value,
    status: 'synced',
    message: `已同步 ${progress.completed}/${progress.total} 份病历，文书就绪 ${progress.ready} 份。`,
  }
}

function startBatchJobPolling(jobId: string) {
  stopBatchJobPolling()
  batchJobPollTimer = setInterval(async () => {
    if (!batchResultOpen.value) {
      stopBatchJobPolling()
      return
    }
    const result = await getSichuanWorkspaceBatchJob(jobId)
    if (!result.success || !result.data) return
    batchJobDetail.value = result.data
    if (!isBatchJobRunning(result.data.status)) {
      stopBatchJobPolling()
      await loadPools()
      await loadRecords()
    }
  }, 3000)
}

async function handleCancelBatchJob(jobId: string) {
  const normalizedJobId = String(jobId || '').trim()
  if (!normalizedJobId) return
  cancelBatchJobLoading.value = true
  try {
    const result = await cancelSichuanWorkspaceBatchJob(normalizedJobId)
    if (!result.success || !result.data) {
      message.error(result.message || '停止质控任务失败')
      return
    }
    stopBatchJobPolling()
    batchJobDetail.value = result.data
    message.success('质控任务已停止')
    await loadPools()
    await loadRecords()
  } finally {
    cancelBatchJobLoading.value = false
  }
}

async function downloadBatchReport(jobId: string, format: 'xlsx' | 'csv' | 'html') {
  if (!jobId) {
    message.warning('当前任务详情未加载完成，暂时无法导出报告')
    return
  }
  const result = await exportSichuanWorkspaceBatchJob({ job_id: jobId, format })
  if (!result.success || !result.data) {
    message.error(result.message || '导出验证任务失败')
    return
  }
  let blob: Blob
  try {
    blob = await normalizeBatchExportBlob(result.data, format)
  } catch (error: any) {
    message.error(error?.message || '导出验证任务失败')
    return
  }
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `manual-sample-validation-${jobId}.${format}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
  message.success(format === 'html' ? 'HTML 质控明细已开始下载' : '质控报告已开始下载')
}

async function handleExportBatchReport(format: 'xlsx' | 'csv' | 'html' = 'html') {
  const jobId = String(batchJobDetail.value?.id || '').trim()
  await downloadBatchReport(jobId, format)
}

async function handleExportTaskHistoryJob(job: SichuanBatchJob) {
  const jobId = String(job?.id || '').trim()
  await downloadBatchReport(jobId, 'html')
}

function getBatchJobStatusText(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return '已完成'
  if (normalized === 'running') return '执行中'
  if (normalized === 'failed') return '失败'
  if (normalized === 'canceled') return '已取消'
  return '排队中'
}

function getBatchJobStatusTagClass(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (normalized === 'running') return 'border-blue-200 bg-blue-50 text-[#0057b8]'
  if (normalized === 'failed') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (normalized === 'canceled') return 'border-slate-200 bg-slate-100 text-slate-600'
  return 'border-amber-200 bg-amber-50 text-amber-700'
}

function syncJobStatusText(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return '已完成'
  if (normalized === 'running') return '执行中'
  if (normalized === 'failed') return '失败'
  return '排队中'
}

function syncJobStatusColor(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return 'success'
  if (normalized === 'running') return 'processing'
  if (normalized === 'failed') return 'error'
  return 'default'
}

function formatDateTime(value?: string) {
  if (!value) return '-'
  const text = value.trim()
  const normalized = text.includes('T') ? text : text.replace(' ', 'T')
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const date = new Date(hasTimezone ? normalized : `${normalized}Z`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

onMounted(async () => {
  window.addEventListener('resize', updateCustomerSampleTourCardPosition)
  window.addEventListener('scroll', updateCustomerSampleTourCardPosition, true)
  await loadRuleSets()
  await loadLuxian0609RuleCatalog()
  await loadPools()
  openInitialCustomerSampleGuide()
})

onUnmounted(() => {
  window.removeEventListener('resize', updateCustomerSampleTourCardPosition)
  window.removeEventListener('scroll', updateCustomerSampleTourCardPosition, true)
  if (customerSampleGuidePositionTimer) {
    clearTimeout(customerSampleGuidePositionTimer)
    customerSampleGuidePositionTimer = null
  }
  stopBatchJobPolling()
  stopTaskHistoryPolling()
  stopLuxianAggregatePolling()
  stopSyncJobPolling()
})
</script>

<style scoped>
.customer-sample-page {
  --customer-sample-canvas: #f5f5f7;
  --customer-sample-surface: rgba(255, 255, 255, 0.86);
  --customer-sample-surface-strong: rgba(255, 255, 255, 0.94);
  --customer-sample-surface-soft: rgba(255, 255, 255, 0.72);
  --customer-sample-border: rgba(0, 0, 0, 0.08);
  --customer-sample-border-strong: rgba(0, 0, 0, 0.14);
  --customer-sample-text: #1d1d1f;
  --customer-sample-muted: rgba(29, 29, 31, 0.6);
  --customer-sample-subtle: rgba(29, 29, 31, 0.38);
  --customer-sample-primary: #0066cc;
  --customer-sample-primary-soft: rgba(0, 102, 204, 0.08);

  background: var(--customer-sample-canvas);
  color: var(--customer-sample-text);
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.customer-sample-page :deep(.ant-btn),
.customer-sample-page :deep(.ant-input),
.customer-sample-page :deep(.ant-select),
.customer-sample-page :deep(.ant-table),
.customer-sample-page :deep(.ant-tag),
.customer-sample-page :deep(.ant-dropdown-menu),
.customer-sample-page :deep(.ant-pagination),
.customer-sample-page :deep(.ant-collapse) {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei', 'Microsoft YaHei UI', system-ui, sans-serif;
}

.customer-sample-scroll {
  background: var(--customer-sample-canvas);
}

.customer-sample-scroll.has-selection-run-bar {
  padding-bottom: 108px;
}

.customer-sample-container {
  padding-top: 2px;
}

.customer-sample-console {
  border: 1px solid var(--customer-sample-border);
  border-radius: 20px;
  background: var(--customer-sample-surface);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.04),
    0 8px 22px rgba(0, 0, 0, 0.045);
  padding: 20px;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-console:hover,
.customer-sample-list-panel:hover {
  border-color: var(--customer-sample-border-strong);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}

.customer-sample-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.customer-sample-page-title {
  display: inline-flex;
  align-items: baseline;
  gap: 10px;
}

.customer-sample-page-title span {
  color: var(--customer-sample-text);
  font-family:
    'Source Han Sans SC', 'SF Pro Display', 'San Francisco', 'SF Pro Text', Inter, 'PingFang SC',
    'Microsoft YaHei UI', system-ui, sans-serif;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 31px;
}

.customer-sample-page-title small {
  color: var(--customer-sample-muted);
  font-size: 13px;
  font-weight: 500;
}

.customer-sample-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.customer-sample-toolbar-actions :deep(.ant-btn) {
  height: 36px;
  border-radius: 10px !important;
  font-size: 13px;
  font-weight: 600;
}

.customer-sample-toolbar-actions :deep(.ant-btn-primary) {
  background: #0066cc;
  border-color: #0066cc;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 4px 10px rgba(0, 102, 204, 0.16);
}

.customer-sample-toolbar-actions :deep(.ant-btn-primary:hover),
.customer-sample-toolbar-actions :deep(.ant-btn-primary:focus) {
  background: #0057b8;
  border-color: #0057b8;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 5px 12px rgba(0, 102, 204, 0.18);
}

.customer-sample-toolbar-actions :deep(.ant-btn-default) {
  border-color: rgba(29, 29, 31, 0.1);
  background: rgba(255, 255, 255, 0.92);
  color: rgba(29, 29, 31, 0.68);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 1px rgba(0, 0, 0, 0.035);
}

.customer-sample-toolbar-actions :deep(.ant-btn-default:hover),
.customer-sample-toolbar-actions :deep(.ant-btn-default:focus) {
  border-color: rgba(29, 29, 31, 0.15);
  background: rgba(255, 255, 255, 0.98);
  color: #1d1d1f;
}

.customer-sample-toolbar-actions :deep(.customer-sample-create-action.ant-btn) {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border-color: #0066cc;
  background: #0066cc;
  color: #fff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.2),
    0 4px 10px rgba(0, 102, 204, 0.16);
}

.customer-sample-toolbar-actions :deep(.customer-sample-create-action.ant-btn:hover),
.customer-sample-toolbar-actions :deep(.customer-sample-create-action.ant-btn:focus) {
  border-color: #0057b8;
  background: #0057b8;
  color: #fff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.2),
    0 5px 12px rgba(0, 102, 204, 0.18);
  transform: translateY(-1px);
}

.customer-sample-toolbar-actions :deep(.customer-sample-create-action svg) {
  flex: 0 0 auto;
  stroke-width: 2.2;
}

.customer-sample-toolbar-actions :deep(.customer-sample-guide-action.ant-btn) {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #0066cc;
}

.customer-sample-toolbar-actions :deep(.customer-sample-guide-action svg) {
  flex: 0 0 auto;
  stroke-width: 2.2;
}

.customer-sample-toolbar-actions :deep(.customer-sample-task-history-action.ant-btn) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 13px 0 11px;
  border-color: rgba(0, 102, 204, 0.26);
  background: linear-gradient(180deg, #ffffff 0%, rgba(234, 242, 255, 0.92) 100%);
  color: #0057b8;
  font-weight: 700;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.85),
    0 5px 12px rgba(0, 102, 204, 0.1);
  transition:
    border-color 220ms cubic-bezier(0.25, 0.1, 0.25, 1),
    background 220ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 220ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 220ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-toolbar-actions :deep(.customer-sample-task-history-action.ant-btn:hover),
.customer-sample-toolbar-actions :deep(.customer-sample-task-history-action.ant-btn:focus) {
  border-color: rgba(0, 102, 204, 0.42);
  background: linear-gradient(180deg, #ffffff 0%, rgba(223, 236, 255, 0.96) 100%);
  color: #0066cc;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 8px 18px rgba(0, 102, 204, 0.15);
  transform: translateY(-1px);
}

.customer-sample-task-history-icon {
  display: inline-flex;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.1);
  color: #0066cc;
}

.customer-sample-task-history-label {
  line-height: 20px;
  white-space: nowrap;
}

.customer-sample-task-history-icon svg {
  flex: 0 0 auto;
  stroke-width: 2.2;
}

.customer-sample-task-history-count {
  display: inline-flex;
  min-width: 18px;
  height: 18px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #0066cc;
  color: #fff;
  font-size: 11px;
  font-weight: 750;
  padding: 0 5px;
}

.customer-sample-command-bar {
  margin-top: 18px;
  display: grid;
  grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
  gap: 14px;
  align-items: end;
}

.customer-sample-field {
  min-width: 0;
}

.customer-sample-field-label {
  margin-bottom: 6px;
  color: var(--customer-sample-muted);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.customer-sample-rule-switcher {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  border: 1px solid var(--customer-sample-border);
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.035);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.76);
  padding: 4px;
}

@media (max-width: 1024px) {
  .customer-sample-command-bar,
  .customer-sample-rule-switcher {
    grid-template-columns: 1fr;
  }
}

.customer-sample-step {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--customer-sample-muted);
  font-size: 12px;
  line-height: 18px;
}

.customer-sample-step strong {
  color: var(--customer-sample-text);
  font-size: 15px;
  font-weight: 700;
}

.customer-sample-step.is-ready,
.customer-sample-step.is-active {
  color: var(--customer-sample-primary);
}

.customer-sample-rule-card {
  display: flex;
  min-height: 36px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  padding: 6px 10px;
  color: var(--customer-sample-muted);
  text-align: center;
  transition:
    background 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    color 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-rule-card span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 560;
  line-height: 18px;
}

.customer-sample-rule-card em {
  flex: 0 0 auto;
  color: rgba(29, 29, 31, 0.4);
  font-style: normal;
  font-size: 12px;
  font-weight: 700;
}

.customer-sample-rule-card:hover {
  background: rgba(255, 255, 255, 0.82);
  color: var(--customer-sample-primary);
}

.customer-sample-rule-card.is-selected {
  background: rgba(255, 255, 255, 0.96);
  color: var(--customer-sample-primary);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 2px 8px rgba(0, 0, 0, 0.055);
}

.customer-sample-rule-card.is-selected em {
  color: var(--customer-sample-primary);
}

.customer-sample-rule-badge,
.customer-sample-meta-chip,
.customer-sample-coverage-chip {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.customer-sample-rule-badge {
  border: 1px solid rgba(0, 102, 204, 0.14);
  background: var(--customer-sample-primary-soft);
  color: var(--customer-sample-primary);
  padding: 4px 9px;
}

.customer-sample-meta-chip {
  border: 1px solid var(--customer-sample-border);
  background: var(--customer-sample-surface-soft);
  color: var(--customer-sample-muted);
  padding: 3px 9px;
}

.customer-sample-status-strip {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.68);
  padding: 10px 12px;
}

.customer-sample-coverage-chip {
  padding: 4px 10px;
}

.customer-sample-rule-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.customer-sample-internal-toggle {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  padding: 4px 10px;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
  cursor: pointer;
}

.customer-sample-internal-toggle:hover {
  border-color: rgba(0, 102, 204, 0.16);
  background: rgba(234, 242, 255, 0.72);
  color: #0066cc;
}

.customer-sample-selection-run-bar {
  position: fixed;
  right: max(24px, calc((100vw - 1440px) / 2 + 24px));
  bottom: 22px;
  left: max(24px, calc((100vw - 1440px) / 2 + 24px));
  z-index: 120;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  max-width: 1120px;
  margin: 0 auto;
  padding: 12px 14px 12px 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow:
    0 14px 34px rgba(15, 23, 42, 0.14),
    0 1px 2px rgba(15, 23, 42, 0.06);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.customer-sample-selection-run-summary {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.customer-sample-selection-run-summary strong {
  color: var(--customer-sample-text);
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
}

.customer-sample-selection-run-summary span {
  color: var(--customer-sample-muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
}

.customer-sample-selection-run-actions {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.customer-sample-selection-run-actions :deep(.ant-btn) {
  height: 34px;
  border-radius: 9px !important;
  font-size: 13px;
  font-weight: 600;
}

.customer-sample-selection-run-actions :deep(.ant-btn-primary) {
  background: #0066cc;
  border-color: #0066cc;
  box-shadow: 0 5px 14px rgba(0, 102, 204, 0.18);
}

.customer-sample-task-history {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  gap: 14px;
}

.customer-sample-task-history-drawer :deep(.ant-drawer-body),
.customer-sample-luxian-aggregate-drawer :deep(.ant-drawer-body) {
  overflow-x: hidden;
}

.customer-sample-task-history-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(250, 250, 252, 0.72);
  padding: 14px;
}

.customer-sample-task-history-head strong {
  display: block;
  color: #1d1d1f;
  font-size: 15px;
  font-weight: 700;
}

.customer-sample-task-history-head p {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.56);
  font-size: 13px;
  line-height: 20px;
}

.customer-sample-task-history-empty {
  border-radius: 16px;
  border: 1px dashed rgba(0, 0, 0, 0.12);
  background: rgba(250, 250, 252, 0.62);
  color: rgba(29, 29, 31, 0.52);
  font-size: 13px;
  line-height: 22px;
  padding: 28px 16px;
  text-align: center;
}

.customer-sample-task-history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.customer-sample-task-history-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
  padding: 14px;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.customer-sample-task-history-item:hover {
  border-color: rgba(0, 102, 204, 0.14);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.customer-sample-task-history-item-main {
  min-width: 0;
}

.customer-sample-task-history-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.customer-sample-task-history-title > span {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
}

.customer-sample-task-history-title em {
  border-radius: 999px;
  border-width: 1px;
  border-style: solid;
  font-size: 12px;
  font-style: normal;
  font-weight: 650;
  line-height: 18px;
  padding: 2px 8px;
}

.customer-sample-task-history-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.customer-sample-task-history-meta span {
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  padding: 3px 8px;
}

.customer-sample-task-history-overview {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  border-radius: 12px;
  background: rgba(0, 102, 204, 0.045);
  padding: 10px 12px;
}

.customer-sample-task-history-overview strong {
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 750;
  line-height: 20px;
}

.customer-sample-task-history-overview span {
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.customer-sample-task-history-overview .customer-sample-task-history-issue-line {
  color: rgba(29, 29, 31, 0.76);
  font-weight: 700;
  line-height: 20px;
}

.customer-sample-task-history-status-grid {
  margin-top: 9px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.customer-sample-task-history-status-grid span {
  display: inline-flex;
  min-width: 72px;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(250, 250, 252, 0.9);
  padding: 6px 8px;
}

.customer-sample-task-history-status-grid em {
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  font-style: normal;
  font-weight: 650;
  line-height: 16px;
}

.customer-sample-task-history-status-grid strong {
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 800;
  line-height: 16px;
}

.customer-sample-task-history-status-grid .is-danger {
  border-color: rgba(239, 68, 68, 0.18);
  background: rgba(254, 242, 242, 0.86);
}

.customer-sample-task-history-status-grid .is-danger strong {
  color: #dc2626;
}

.customer-sample-task-history-status-grid .is-warning {
  border-color: rgba(245, 158, 11, 0.24);
  background: rgba(255, 251, 235, 0.9);
}

.customer-sample-task-history-status-grid .is-warning strong {
  color: #b45309;
}

.customer-sample-task-history-status-grid .is-review {
  border-color: rgba(124, 58, 237, 0.16);
  background: rgba(245, 243, 255, 0.86);
}

.customer-sample-task-history-status-grid .is-review strong {
  color: #6d28d9;
}

.customer-sample-task-history-status-grid .is-ok {
  border-color: rgba(0, 102, 204, 0.16);
  background: rgba(234, 242, 255, 0.86);
}

.customer-sample-task-history-status-grid .is-ok strong {
  color: #0066cc;
}

.customer-sample-task-history-status-grid .is-muted,
.customer-sample-task-history-status-grid .is-neutral {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(250, 250, 252, 0.92);
}

.customer-sample-task-history-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.customer-sample-luxian-aggregate {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  gap: 14px;
}

.customer-sample-luxian-aggregate-head,
.customer-sample-luxian-aggregate-summary,
.customer-sample-luxian-aggregate-item {
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.9);
}

.customer-sample-luxian-aggregate-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 14px;
}

.customer-sample-luxian-aggregate-head strong {
  display: block;
  color: #1d1d1f;
  font-size: 15px;
  font-weight: 700;
}

.customer-sample-luxian-aggregate-head p {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
  line-height: 20px;
}

.customer-sample-luxian-aggregate-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
}

.customer-sample-luxian-aggregate-summary div {
  border-radius: 12px;
  background: rgba(0, 102, 204, 0.06);
  padding: 10px 12px;
}

.customer-sample-luxian-aggregate-summary span {
  display: block;
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
  font-weight: 650;
}

.customer-sample-luxian-aggregate-summary strong {
  display: block;
  margin-top: 4px;
  color: #1d1d1f;
  font-size: 15px;
  font-weight: 750;
}

.customer-sample-luxian-aggregate-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.customer-sample-luxian-aggregate-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 14px;
}

.customer-sample-luxian-aggregate-main {
  min-width: 0;
}

.customer-sample-luxian-aggregate-title,
.customer-sample-luxian-aggregate-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.customer-sample-luxian-aggregate-title strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 750;
}

.customer-sample-luxian-aggregate-title em {
  border-radius: 999px;
  border-width: 1px;
  border-style: solid;
  font-size: 12px;
  font-style: normal;
  font-weight: 650;
  line-height: 18px;
  padding: 2px 8px;
}

.customer-sample-luxian-aggregate-meta {
  margin-top: 8px;
}

.customer-sample-luxian-aggregate-meta span {
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  padding: 3px 8px;
}

.customer-sample-luxian-aggregate-result,
.customer-sample-luxian-aggregate-error {
  margin-top: 8px;
  font-size: 13px;
  line-height: 20px;
}

.customer-sample-luxian-aggregate-result {
  color: rgba(29, 29, 31, 0.68);
}

.customer-sample-luxian-aggregate-error {
  color: #c2410c;
}

.customer-sample-luxian-aggregate-actions {
  flex: 0 0 auto;
}

@media (max-width: 640px) {
  .customer-sample-task-history-head,
  .customer-sample-task-history-item,
  .customer-sample-luxian-aggregate-head,
  .customer-sample-luxian-aggregate-item {
    flex-direction: column;
    align-items: stretch;
  }

  .customer-sample-task-history-actions,
  .customer-sample-luxian-aggregate-actions {
    width: 100%;
  }

  .customer-sample-task-history-actions :deep(.ant-btn),
  .customer-sample-luxian-aggregate-actions :deep(.ant-btn) {
    width: 100%;
  }

  .customer-sample-luxian-aggregate-summary {
    grid-template-columns: 1fr;
  }
}

.customer-sample-luxian-scope {
  margin-top: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  padding: 12px 14px 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.035);
}

.customer-sample-luxian-scope-head,
.customer-sample-luxian-rule-group-head,
.customer-sample-luxian-scope-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.customer-sample-luxian-scope-head,
.customer-sample-luxian-rule-group-head {
  justify-content: space-between;
}

.customer-sample-luxian-scope-head {
  gap: 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding-bottom: 10px;
}

.customer-sample-luxian-scope-title {
  color: var(--customer-sample-text);
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
}

.customer-sample-luxian-scope p,
.customer-sample-luxian-rule-group-head small {
  margin: 2px 0 0;
  color: var(--customer-sample-muted);
  font-size: 12px;
  line-height: 18px;
}

.customer-sample-luxian-scope-actions span {
  white-space: nowrap;
  border: 1px solid rgba(0, 102, 204, 0.12);
  border-radius: 999px;
  background: rgba(234, 242, 255, 0.72);
  padding: 4px 10px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.customer-sample-luxian-rule-groups {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 10px 12px;
}

.customer-sample-luxian-rule-group {
  min-width: 0;
  border: 1px solid rgba(0, 0, 0, 0.065);
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.64);
  padding: 10px;
}

.customer-sample-luxian-rule-group-head {
  align-items: flex-start;
  gap: 8px;
}

.customer-sample-luxian-rule-group-head > div {
  min-width: 0;
}

.customer-sample-luxian-rule-group-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.customer-sample-luxian-rule-group-head strong {
  color: var(--customer-sample-text);
  font-size: 13px;
  font-weight: 700;
  line-height: 19px;
}

.customer-sample-luxian-rule-group-title span {
  flex: 0 0 auto;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  padding: 2px 7px;
  color: var(--customer-sample-primary);
  font-size: 11px;
  font-weight: 750;
  line-height: 16px;
}

.customer-sample-luxian-rule-group-head small {
  display: block;
  overflow: hidden;
  max-width: 100%;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.customer-sample-luxian-rule-group-head button {
  flex: 0 0 auto;
  border: 0;
  border-radius: 8px;
  background: rgba(0, 102, 204, 0.07);
  padding: 4px 8px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
  cursor: pointer;
  transition:
    background 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    color 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-luxian-rule-group-head button:hover {
  background: rgba(0, 102, 204, 0.12);
}

.customer-sample-luxian-rule-options {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.customer-sample-luxian-rule-expand {
  margin-top: 8px;
  border: 0;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.035);
  padding: 5px 9px;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
  cursor: pointer;
  transition:
    background 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    color 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-luxian-rule-expand:hover {
  background: rgba(0, 102, 204, 0.08);
  color: var(--customer-sample-primary);
}

.customer-sample-luxian-rule-option {
  min-width: 0;
  max-width: 100%;
  display: inline-grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.8);
  padding: 5px 9px;
  color: var(--customer-sample-muted);
  transition:
    border-color 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    background 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-luxian-rule-option.is-selected {
  border-color: rgba(0, 102, 204, 0.26);
  background: rgba(234, 242, 255, 0.9);
  color: var(--customer-sample-primary);
  box-shadow: 0 1px 3px rgba(0, 102, 204, 0.08);
}

.customer-sample-luxian-rule-option input {
  width: 14px;
  height: 14px;
  margin: 0;
}

.customer-sample-luxian-rule-option span {
  font-size: 12px;
  font-weight: 800;
  line-height: 18px;
}

.customer-sample-luxian-rule-option em {
  overflow: hidden;
  max-width: 260px;
  color: var(--customer-sample-text);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-style: normal;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

@media (max-width: 900px) {
  .customer-sample-luxian-scope-head,
  .customer-sample-luxian-scope-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .customer-sample-luxian-rule-groups {
    grid-template-columns: 1fr;
  }
}

.customer-sample-list-panel {
  overflow: hidden;
  border: 1px solid var(--customer-sample-border);
  border-radius: 20px;
  background: var(--customer-sample-surface);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.04),
    0 8px 22px rgba(0, 0, 0, 0.045);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-diagnostic-panel {
  overflow: hidden;
  border: 1px solid var(--customer-sample-border);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.7);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.customer-sample-inline-metrics {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.customer-sample-inline-metrics span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--customer-sample-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  padding: 3px 9px;
  color: var(--customer-sample-muted);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.customer-sample-inline-metrics strong {
  color: var(--customer-sample-primary);
  font-weight: 700;
}

.customer-sample-scope-pill {
  max-width: 720px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  padding: 6px 12px;
  color: var(--customer-sample-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  line-height: 18px;
}

.customer-sample-patient-cell {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  min-width: 0;
}

.customer-sample-patient-name {
  overflow: hidden;
  max-width: 260px;
  color: var(--customer-sample-text);
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.customer-sample-record-code {
  display: inline-flex;
  max-width: 132px;
  flex: 0 0 auto;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.8);
  padding: 3px 8px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.customer-sample-created-time {
  display: inline-flex;
  color: rgba(29, 29, 31, 0.64);
  font-size: 13px;
  font-weight: 560;
  line-height: 20px;
  white-space: nowrap;
}

.customer-sample-summary-cell {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.customer-sample-rule-summary {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.customer-sample-family-chip {
  display: inline-flex;
  max-width: 100%;
  overflow: hidden;
  align-items: center;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.82);
  padding: 3px 9px;
  color: rgba(29, 29, 31, 0.62);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
  border-color: rgba(0, 102, 204, 0.12);
  background: rgba(234, 242, 255, 0.78);
  color: var(--customer-sample-primary);
}

:deep(.customer-sample-action-cell) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
}

:deep(.customer-sample-primary-action) {
  display: inline-flex;
  width: fit-content;
  min-height: 30px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 102, 204, 0.38);
  border-radius: 8px;
  background: #eaf2ff;
  box-shadow: 0 1px 2px rgba(0, 102, 204, 0.08);
  padding: 5px 11px;
  color: #0057b8;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background-color 0.16s ease,
    box-shadow 0.16s ease;
}

:deep(.customer-sample-primary-action:hover) {
  border-color: rgba(0, 102, 204, 0.52);
  background: #dbeafe;
  box-shadow: 0 2px 6px rgba(0, 102, 204, 0.14);
}

:deep(.customer-sample-secondary-actions) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  line-height: 18px;
}

:deep(.customer-sample-secondary-link) {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 102, 204, 0.24);
  border-radius: 8px;
  background: rgba(234, 242, 255, 0.72);
  box-shadow: 0 1px 2px rgba(0, 102, 204, 0.06);
  padding: 5px 10px;
  color: #0057b8;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease;
}

:deep(.customer-sample-secondary-link:hover) {
  border-color: rgba(0, 102, 204, 0.42);
  background: #dbeafe;
  color: #004a9f;
  box-shadow: 0 2px 6px rgba(0, 102, 204, 0.12);
}

.customer-sample-page :deep(.editable-copy-workstation-modal .ant-modal-content) {
  background: #f5f5f7;
  padding: 0;
  overflow: hidden;
  border-radius: 20px;
}

.customer-sample-page :deep(.editable-copy-workstation-modal .ant-modal-body) {
  max-height: min(86vh, 920px);
  overflow: hidden;
}

.customer-sample-page :deep(.editable-copy-workstation-modal .ant-modal-close) {
  top: 16px;
  right: 16px;
  color: rgba(29, 29, 31, 0.5);
}

.editable-copy-drawer {
  display: flex;
  height: min(86vh, 920px);
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
  padding: 22px;
  color: #1d1d1f;
  overscroll-behavior: contain;
}

.editable-copy-drawer :deep(.ant-spin-nested-loading),
.editable-copy-drawer :deep(.ant-spin-container) {
  display: flex;
  min-height: auto;
  flex: 0 0 auto;
  flex-direction: column;
}

.editable-copy-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
  padding: 18px 20px;
}

.editable-copy-eyebrow {
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.editable-copy-hero h2 {
  margin: 4px 0 0;
  color: #1d1d1f;
  font-size: 22px;
  font-weight: 750;
  line-height: 30px;
}

.editable-copy-hero p {
  margin: 6px 0 0;
  max-width: 640px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 21px;
}

.editable-copy-source-card {
  display: flex;
  min-width: 160px;
  flex-direction: column;
  gap: 2px;
  border-radius: 14px;
  background: rgba(0, 102, 204, 0.06);
  padding: 10px 12px;
  text-align: right;
}

.editable-copy-source-card span,
.editable-copy-source-card em {
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  font-style: normal;
  line-height: 18px;
}

.editable-copy-source-card strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
}

.editable-copy-notice {
  border: 1px solid rgba(0, 102, 204, 0.12);
  border-radius: 12px;
  background: rgba(234, 242, 255, 0.7);
  padding: 10px 12px;
  color: rgba(29, 29, 31, 0.68);
  font-size: 13px;
  line-height: 22px;
}

.editable-copy-notice-title {
  margin-bottom: 2px;
  color: var(--customer-sample-primary);
  font-size: 14px;
  font-weight: 750;
}

.editable-copy-content {
  display: flex;
  min-height: auto;
  flex: 0 0 auto;
  flex-direction: column;
  gap: 14px;
  overflow: visible;
}

.editable-copy-section {
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
  padding: 16px;
}

.editable-copy-section h3 {
  margin: 0 0 10px;
  color: #1d1d1f;
  font-size: 15px;
  font-weight: 750;
  line-height: 22px;
}

.editable-copy-document-workbench-section {
  display: flex;
  min-height: auto;
  flex: 0 0 auto;
  flex-direction: column;
  overflow: visible;
}

.editable-copy-section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.editable-copy-section-header p {
  margin: -4px 0 10px;
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
  line-height: 20px;
}

.editable-copy-section-header > span {
  flex: 0 0 auto;
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.95);
  padding: 3px 9px;
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
  font-weight: 650;
}

.editable-copy-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.editable-copy-form-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 650;
}

.editable-copy-form-grid :deep(.ant-input),
.editable-copy-section :deep(.ant-input),
.editable-copy-section :deep(.ant-input-affix-wrapper) {
  height: 38px;
  border-color: rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  color: rgba(29, 29, 31, 0.82);
  font-size: 14px;
  font-weight: 500;
}

.editable-copy-section :deep(textarea.ant-input) {
  height: auto;
  min-height: 184px;
  padding: 11px 12px;
  color: rgba(29, 29, 31, 0.82);
  font-size: 13px;
  font-weight: 500;
  line-height: 22px;
}

.editable-copy-form-wide {
  grid-column: 1 / -1;
}

.editable-copy-document-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.78);
  padding: 10px;
}

.editable-copy-document-type-select {
  min-width: 210px;
}

.editable-copy-document-toolbar :deep(.ant-btn),
.editable-copy-document-actions :deep(.ant-btn) {
  height: 32px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 650;
}

.editable-copy-document-workbench {
  display: grid;
  min-height: 520px;
  flex: 0 0 auto;
  grid-template-columns: minmax(250px, 300px) minmax(0, 1fr);
  overflow: visible;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.86);
}

.editable-copy-document-directory {
  display: flex;
  height: 100%;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  border-right: 1px solid rgba(0, 0, 0, 0.07);
  background: rgba(255, 255, 255, 0.74);
}

.editable-copy-document-directory-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 14px 8px;
}

.editable-copy-document-directory-head strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 760;
  line-height: 20px;
}

.editable-copy-document-directory-head span {
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  padding: 2px 8px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 700;
}

.editable-copy-document-search {
  margin: 0 14px 10px;
  width: calc(100% - 28px);
}

.editable-copy-document-filter {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  padding: 0 14px 12px;
}

.editable-copy-document-filter button {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.8);
  padding: 5px 4px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
  cursor: pointer;
}

.editable-copy-document-filter button.is-active {
  border-color: rgba(0, 102, 204, 0.22);
  background: rgba(0, 102, 204, 0.08);
  color: var(--customer-sample-primary);
}

.editable-copy-document-directory-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 4px 10px 12px;
}

.editable-copy-document-directory-list.is-tree {
  padding: 8px 12px 14px 18px;
}

.editable-copy-document-group-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 6px 6px;
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
  font-weight: 720;
  line-height: 18px;
}

.editable-copy-document-directory-list.is-tree .editable-copy-document-group-title {
  position: relative;
  padding: 14px 6px 7px 0;
  color: rgba(29, 29, 31, 0.54);
}

.editable-copy-document-directory-list.is-tree .editable-copy-document-group-title span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.editable-copy-document-directory-list.is-tree .editable-copy-document-group-title i {
  width: 7px;
  height: 7px;
  border: 2px solid rgba(0, 102, 204, 0.55);
  border-radius: 999px;
  background: #ffffff;
}

.editable-copy-document-group-title em {
  font-style: normal;
  font-weight: 650;
}

.editable-copy-document-nav-item {
  position: relative;
  display: block;
  width: 100%;
  margin: 0 0 6px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  padding: 8px 9px;
  text-align: left;
  cursor: pointer;
}

.editable-copy-document-directory-list.is-tree .editable-copy-document-nav-item {
  margin-left: 10px;
  width: calc(100% - 10px) !important;
  border-radius: 8px;
  padding: 7px 9px 7px 16px;
}

.editable-copy-document-directory-list.is-tree .editable-copy-document-nav-item::before {
  position: absolute;
  top: -8px;
  bottom: -8px;
  left: -6px;
  width: 1px;
  background: rgba(0, 102, 204, 0.16);
  content: '';
}

.editable-copy-document-directory-list.is-tree .editable-copy-document-nav-item::after {
  position: absolute;
  top: 18px;
  left: -6px;
  width: 12px;
  height: 1px;
  background: rgba(0, 102, 204, 0.2);
  content: '';
}

.editable-copy-document-nav-item:hover {
  background: rgba(0, 0, 0, 0.035);
}

.editable-copy-document-nav-item.is-active {
  border-color: rgba(0, 102, 204, 0.2);
  background: rgba(0, 102, 204, 0.08);
}

.editable-copy-document-nav-item.is-disabled {
  opacity: 0.56;
}

.editable-copy-document-nav-item span {
  display: block;
  overflow: hidden;
  color: rgba(29, 29, 31, 0.82);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 700;
  line-height: 20px;
}

.editable-copy-document-nav-item small {
  display: block;
  overflow: hidden;
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.48);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  line-height: 18px;
}

.editable-copy-document-empty {
  margin: 20px 8px;
  color: rgba(29, 29, 31, 0.46);
  font-size: 13px;
  text-align: center;
}

.editable-copy-document-editor {
  overflow: visible;
  min-width: 0;
  padding: 16px;
  background: rgba(255, 255, 255, 0.8);
}

.editable-copy-document-editor-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(29, 29, 31, 0.46);
  font-size: 14px;
  font-weight: 650;
}

.editable-copy-document-editor-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.editable-copy-document-editor-head h4 {
  margin: 7px 0 0;
  color: #1d1d1f;
  font-size: 20px;
  font-weight: 780;
  line-height: 28px;
}

.editable-copy-document-editor-head > div:first-child > span {
  display: inline-flex;
  border-radius: 999px;
  background: rgba(234, 242, 255, 0.82);
  padding: 3px 9px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.editable-copy-document-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.editable-copy-document {
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.84);
  padding: 14px;
}

.editable-copy-document-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.editable-copy-document-actions {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.editable-copy-document-actions > span {
  flex: 0 0 auto;
  border-radius: 999px;
  background: rgba(234, 242, 255, 0.78);
  padding: 2px 8px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 650;
}

.editable-copy-readonly-pill {
  background: rgba(0, 0, 0, 0.045) !important;
  color: rgba(29, 29, 31, 0.56) !important;
}

.editable-copy-workstation-modal :deep(.ant-input[readonly]),
.editable-copy-workstation-modal :deep(textarea.ant-input[readonly]) {
  border-color: rgba(0, 0, 0, 0.06);
  background: rgba(248, 250, 252, 0.72);
  color: rgba(29, 29, 31, 0.76);
  cursor: default;
}

.editable-copy-document-fields {
  display: grid;
  grid-template-columns: minmax(220px, 1.2fr) minmax(160px, 0.8fr) minmax(160px, 0.8fr);
  gap: 10px;
  margin: 10px 0;
}

.editable-copy-document-fields label,
.editable-copy-order-meta label {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.editable-copy-document-fields label > span,
.editable-copy-order-meta label > span {
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
}

.editable-copy-document-fields :deep(.ant-input),
.editable-copy-order-meta :deep(.ant-input) {
  height: 32px;
  border-radius: 8px;
  font-size: 12px;
}

.editable-copy-document-toggle {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 720;
}

.editable-copy-document-toggle span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.editable-copy-document-meta {
  margin: 6px 0 10px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  line-height: 18px;
}

.editable-copy-order-table-panel {
  margin-top: 12px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.86);
}

.editable-copy-order-type-switch {
  display: flex;
  gap: 10px;
  align-items: center;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding: 12px 14px;
}

.editable-copy-order-type-switch button {
  position: relative;
  border: 0;
  background: transparent;
  padding: 0 0 0 22px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
  font-weight: 650;
  line-height: 20px;
  cursor: pointer;
}

.editable-copy-order-type-switch button::before {
  position: absolute;
  top: 50%;
  left: 0;
  width: 14px;
  height: 14px;
  border: 1px solid rgba(0, 0, 0, 0.18);
  border-radius: 999px;
  background: #fff;
  content: '';
  transform: translateY(-50%);
}

.editable-copy-order-type-switch button.is-active {
  color: #1d1d1f;
}

.editable-copy-order-type-switch button.is-active::before {
  border: 4px solid #0066cc;
}

.editable-copy-order-table-wrap {
  max-height: none;
  overflow: visible;
}

.editable-copy-order-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
  line-height: 20px;
}

.editable-copy-order-table th {
  position: sticky;
  z-index: 1;
  top: 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(245, 245, 247, 0.96);
  padding: 9px 10px;
  color: rgba(29, 29, 31, 0.56);
  font-weight: 700;
  text-align: left;
}

.editable-copy-order-table th:nth-child(1) {
  width: 170px;
}

.editable-copy-order-table th:nth-child(2) {
  width: 96px;
}

.editable-copy-order-table th:nth-child(4) {
  width: 140px;
}

.editable-copy-order-table th:nth-child(5) {
  width: 88px;
}

.editable-copy-order-table td {
  overflow: hidden;
  border-bottom: 1px solid rgba(0, 0, 0, 0.055);
  padding: 9px 10px;
  color: #1d1d1f;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.editable-copy-order-table tbody tr {
  cursor: pointer;
}

.editable-copy-order-table tbody tr:hover {
  background: rgba(0, 102, 204, 0.045);
}

.editable-copy-order-table tbody tr.is-active {
  background: rgba(0, 102, 204, 0.1);
}

.editable-copy-order-table tbody tr.is-disabled td {
  color: rgba(29, 29, 31, 0.38);
  text-decoration: line-through;
}

.editable-copy-order-empty {
  color: rgba(29, 29, 31, 0.48) !important;
  text-align: center;
  text-decoration: none !important;
}

.editable-copy-order-editor {
  margin-top: 12px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.86);
}

.editable-copy-order-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding: 12px 14px;
}

.editable-copy-order-head strong {
  display: block;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 750;
  line-height: 20px;
}

.editable-copy-order-head span {
  display: block;
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
  line-height: 18px;
}

.editable-copy-order-head em {
  flex: 0 0 auto;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  padding: 3px 9px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
}

.editable-copy-order-list {
  display: flex;
  max-height: 520px;
  flex-direction: column;
  overflow: auto;
}

.editable-copy-order-row {
  display: grid;
  grid-template-columns: 28px minmax(170px, 220px) minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  border-bottom: 1px solid rgba(0, 0, 0, 0.055);
  padding: 11px 14px;
}

.editable-copy-order-row:last-child {
  border-bottom: 0;
}

.editable-copy-order-check {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}

.editable-copy-order-meta {
  min-width: 0;
}

.editable-copy-order-meta span {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  background: rgba(234, 242, 255, 0.8);
  padding: 2px 8px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.editable-copy-order-meta button {
  margin-top: 8px;
  border: 1px solid rgba(0, 102, 204, 0.22);
  border-radius: 8px;
  background: rgba(234, 242, 255, 0.72);
  padding: 3px 9px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
  cursor: pointer;
}

.editable-copy-order-meta button:hover {
  border-color: rgba(0, 102, 204, 0.36);
  background: rgba(0, 102, 204, 0.1);
}

.editable-copy-order-row :deep(textarea.ant-input) {
  min-height: 74px;
  font-size: 13px;
  line-height: 21px;
}

.editable-copy-footer {
  display: flex;
  flex: 0 0 auto;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  background: rgba(245, 245, 247, 0.94);
  padding: 12px 0 0;
}

.editable-copy-footer :deep(.ant-btn) {
  height: 34px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 650;
}

.editable-copy-footer :deep(.ant-btn-primary) {
  border-color: var(--customer-sample-primary);
  background: var(--customer-sample-primary);
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.16);
}

.customer-sample-department {
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
  font-weight: 520;
  white-space: nowrap;
}

.customer-sample-empty-state {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  text-align: center;
}

.customer-sample-empty-icon {
  margin-bottom: 12px;
  color: var(--customer-sample-subtle);
  font-size: 36px;
}

.customer-sample-empty-title {
  color: rgba(29, 29, 31, 0.72);
  font-size: 15px;
  font-weight: 600;
}

.customer-sample-empty-desc {
  max-width: 420px;
  margin-top: 8px;
  color: var(--customer-sample-muted);
  font-size: 13px;
  line-height: 22px;
}

:deep(.customer-sample-record-table .ant-table) {
  overflow: hidden;
  color: rgba(29, 29, 31, 0.76);
  border: 1px solid rgba(0, 0, 0, 0.075);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
}

:deep(.customer-sample-record-table .ant-table-container) {
  border-start-start-radius: 16px;
  border-start-end-radius: 16px;
}

:deep(.customer-sample-record-table .ant-table-cell) {
  border-inline-end: 0 !important;
}

:deep(.customer-sample-record-table .ant-table-thead > tr > th) {
  background: rgba(248, 250, 252, 0.92) !important;
  color: var(--customer-sample-subtle);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  border-color: rgba(0, 0, 0, 0.06);
}

:deep(.customer-sample-record-table .ant-table-thead > tr > th::before) {
  display: none !important;
}

:deep(.customer-sample-record-table .ant-table-tbody > tr > td) {
  padding: 15px 12px;
  border-color: rgba(0, 0, 0, 0.06);
  vertical-align: top;
  background: rgba(255, 255, 255, 0.86);
}

:deep(.customer-sample-record-table .ant-table-tbody > tr:hover > td) {
  background: rgba(0, 102, 204, 0.035) !important;
}

:deep(.customer-sample-record-table .ant-table-tbody > tr:nth-child(even) > td) {
  background: rgba(248, 250, 252, 0.56);
}

:deep(.customer-sample-record-table .ant-checkbox-wrapper),
:deep(.customer-sample-record-table .ant-checkbox) {
  align-self: flex-start;
}

:deep(.customer-sample-record-table .ant-table-selection-column) {
  width: 42px;
  min-width: 42px;
}

:deep(.customer-sample-record-table .ant-table-cell-fix-right),
:deep(.customer-sample-record-table .ant-table-cell-fix-right-first::after),
:deep(.customer-sample-record-table .ant-table-cell-fix-right-last::after) {
  box-shadow: none !important;
}

.customer-sample-toolbar-input {
  height: 36px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 22px;
  border-color: rgba(29, 29, 31, 0.1);
  background: rgba(255, 255, 255, 0.92);
}

.customer-sample-toolbar-input::placeholder {
  font-size: 13px;
}

:deep(.customer-sample-toolbar-select .ant-select-selector) {
  height: 36px !important;
  border-radius: 10px !important;
  border-color: rgba(29, 29, 31, 0.1) !important;
  background: rgba(255, 255, 255, 0.92) !important;
  padding: 0 12px !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 1px rgba(0, 0, 0, 0.035) !important;
}

:deep(.customer-sample-toolbar-select .ant-select-selection-placeholder),
:deep(.customer-sample-toolbar-select .ant-select-selection-item) {
  font-size: 13px;
  line-height: 34px !important;
}

:deep(.customer-sample-toolbar-select .ant-select-selection-search-input) {
  height: 34px !important;
}

:deep(.customer-sample-internal-collapse .ant-collapse-header) {
  padding: 10px 16px !important;
  color: var(--customer-sample-muted) !important;
  font-size: 13px;
  font-weight: 600;
}

:deep(.customer-sample-internal-collapse .ant-collapse-content-box) {
  padding: 0 0 16px !important;
}

/* Apple workstation convergence overrides */
.customer-sample-page .rounded-\[24px\],
.customer-sample-page .rounded-\[20px\],
.customer-sample-page .rounded-2xl {
  border-color: var(--customer-sample-border) !important;
  background-color: var(--customer-sample-surface) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.customer-sample-page .bg-slate-50,
.customer-sample-page .bg-slate-50\/90,
.customer-sample-page .bg-slate-100,
.customer-sample-page .bg-white,
.customer-sample-page .bg-white\/80,
.customer-sample-page .bg-sky-50,
.customer-sample-page .bg-sky-50\/70,
.customer-sample-page .bg-blue-50,
.customer-sample-page .bg-emerald-50,
.customer-sample-page .bg-emerald-50\/70,
.customer-sample-page .bg-cyan-50,
.customer-sample-page .bg-fuchsia-50 {
  background-color: var(--customer-sample-surface-soft) !important;
}

.customer-sample-page .border-slate-200,
.customer-sample-page .border-slate-200\/80,
.customer-sample-page .border-slate-300,
.customer-sample-page .border-white\/70,
.customer-sample-page .border-sky-200,
.customer-sample-page .border-blue-200,
.customer-sample-page .border-emerald-200,
.customer-sample-page .border-cyan-200,
.customer-sample-page .border-fuchsia-200 {
  border-color: var(--customer-sample-border) !important;
}

.customer-sample-page .text-slate-900,
.customer-sample-page .text-slate-800,
.customer-sample-page .text-slate-700 {
  color: var(--customer-sample-text) !important;
}

.customer-sample-page .text-slate-600,
.customer-sample-page .text-slate-500,
.customer-sample-page .text-slate-400 {
  color: var(--customer-sample-muted) !important;
}

.customer-sample-page .font-semibold,
.customer-sample-page .font-bold {
  font-weight: 600 !important;
}

.customer-sample-page .text-sky-700,
.customer-sample-page .text-\[\#0057b8\],
.customer-sample-page .text-cyan-700 {
  color: var(--customer-sample-primary) !important;
}

.customer-sample-page .text-emerald-700 {
  color: #047857 !important;
}

.customer-sample-page .text-amber-700,
.customer-sample-page .text-amber-800,
.customer-sample-page .text-amber-900,
.customer-sample-page .text-amber-950,
.customer-sample-page .text-orange-700 {
  color: #b45309 !important;
}

.customer-sample-page .text-rose-600,
.customer-sample-page .text-rose-700 {
  color: #be123c !important;
}

.customer-sample-page [class*='shadow-['] {
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.04),
    0 4px 14px rgba(0, 0, 0, 0.045) !important;
}

.customer-sample-page [class*='bg-[linear-gradient'] {
  background-image: none !important;
  background-color: var(--customer-sample-surface-soft) !important;
}

.customer-sample-page .bg-amber-50,
.customer-sample-page .bg-orange-50 {
  background-color: rgba(245, 158, 11, 0.1) !important;
}

.customer-sample-page .bg-rose-50 {
  background-color: rgba(239, 68, 68, 0.09) !important;
}

.customer-sample-page .border-amber-200,
.customer-sample-page .border-orange-200 {
  border-color: rgba(245, 158, 11, 0.22) !important;
}

.customer-sample-page .border-rose-200 {
  border-color: rgba(239, 68, 68, 0.2) !important;
}

.customer-sample-console,
.customer-sample-list-panel,
.customer-sample-diagnostic-panel,
.customer-sample-page .rounded-\[24px\],
.customer-sample-page .rounded-\[20px\],
.customer-sample-page .rounded-2xl {
  transition:
    border-color 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.customer-sample-page .rounded-\[24px\]:hover,
.customer-sample-page .rounded-\[20px\]:hover,
.customer-sample-page .rounded-2xl:hover {
  border-color: var(--customer-sample-border-strong) !important;
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075) !important;
  transform: translateY(-2px);
}

.customer-sample-page .rounded-full {
  border-color: var(--customer-sample-border) !important;
}

.customer-sample-page :deep(.ant-card),
.customer-sample-page :deep(.ant-upload-drag) {
  border-color: var(--customer-sample-border);
  border-radius: 16px;
  background: var(--customer-sample-surface-soft);
  box-shadow: none;
}

.customer-sample-page :deep(.ant-upload-drag:hover) {
  border-color: rgba(0, 102, 204, 0.28);
}

.customer-sample-page :deep(.ant-input:hover),
.customer-sample-page :deep(.ant-input-affix-wrapper:hover),
.customer-sample-page :deep(.ant-select-selector:hover) {
  border-color: rgba(0, 102, 204, 0.28) !important;
}

.customer-sample-page :deep(.ant-input:focus),
.customer-sample-page :deep(.ant-input-focused),
.customer-sample-page :deep(.ant-input-affix-wrapper-focused),
.customer-sample-page :deep(.ant-select-focused .ant-select-selector) {
  border-color: rgba(0, 102, 204, 0.5) !important;
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.08) !important;
}

.customer-sample-page :deep(.ant-modal-content),
.customer-sample-page :deep(.ant-drawer-content) {
  background: var(--customer-sample-surface-strong);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  color: var(--customer-sample-text);
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.customer-sample-page :deep(.ant-modal-title),
.customer-sample-page :deep(.ant-drawer-title) {
  color: var(--customer-sample-text);
  font-weight: 650;
}

.customer-sample-tour-layer {
  position: fixed;
  inset: 0;
  z-index: 70;
  pointer-events: none;
}

.customer-sample-tour-scrim {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.08);
}

.customer-sample-tour-card {
  position: absolute;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow:
    0 12px 36px rgba(15, 23, 42, 0.16),
    0 2px 8px rgba(15, 23, 42, 0.08);
  padding: 16px;
  pointer-events: auto;
}

.customer-sample-tour-kicker {
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.customer-sample-tour-count {
  margin-top: 8px;
  display: inline-flex;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  padding: 3px 9px;
  color: #0066cc;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.customer-sample-tour-card h3 {
  margin: 10px 0 0;
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 750;
  line-height: 24px;
}

.customer-sample-tour-card p {
  margin: 7px 0 0;
  color: rgba(29, 29, 31, 0.64);
  font-size: 13px;
  line-height: 21px;
}

.customer-sample-tour-dots {
  margin-top: 13px;
  display: flex;
  gap: 6px;
}

.customer-sample-tour-dots button {
  width: 26px;
  height: 5px;
  border: 0;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.12);
  cursor: pointer;
}

.customer-sample-tour-dots button.is-active {
  background: #0066cc;
}

.customer-sample-guide-footer {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.customer-sample-guide-footer :deep(.ant-btn) {
  height: 34px;
  font-size: 13px;
  font-weight: 600;
}

.customer-sample-guide-footer :deep(.ant-btn-primary) {
  border-color: #0066cc;
  background: #0066cc;
}

.customer-sample-tour-target {
  position: relative;
}

.customer-sample-tour-target.is-current-tour-target {
  z-index: 80;
  border-radius: 14px;
  outline: 3px solid #f59e0b;
  outline-offset: 5px;
  box-shadow:
    0 0 0 10px rgba(245, 158, 11, 0.24),
    0 0 0 16px rgba(255, 255, 255, 0.82),
    0 14px 34px rgba(180, 83, 9, 0.22);
}

/* Ant Design Modal uses teleport; keep the editable-copy document manager stable even if inherited modal/table styles change. */
.editable-copy-workstation-modal .editable-copy-document-workbench {
  display: flex !important;
  align-items: stretch;
  height: auto;
  min-height: 520px;
}

.editable-copy-workstation-modal .editable-copy-document-directory {
  flex: 0 0 300px;
  width: 300px;
  max-width: 300px;
  min-height: 0;
}

.editable-copy-workstation-modal .editable-copy-document-editor {
  flex: 1 1 auto;
  min-width: 0;
}

.editable-copy-workstation-modal .editable-copy-document-filter {
  display: grid !important;
}

.editable-copy-workstation-modal .editable-copy-document-nav-item {
  display: block !important;
  width: 100% !important;
}

.editable-copy-workstation-modal .editable-copy-document-nav-item span,
.editable-copy-workstation-modal .editable-copy-document-nav-item small {
  display: block !important;
}

@media (max-width: 768px) {
  .editable-copy-workstation-modal .editable-copy-document-workbench {
    flex-direction: column;
  }

  .editable-copy-workstation-modal .editable-copy-document-directory {
    width: 100%;
    max-width: none;
    flex-basis: auto;
    border-right: 0;
    border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  }

  .customer-sample-tour-card {
    max-width: calc(100vw - 32px);
  }

  .customer-sample-selection-run-bar {
    right: 12px;
    bottom: 12px;
    left: 12px;
    flex-direction: column;
    align-items: stretch;
  }

  .customer-sample-selection-run-actions {
    justify-content: flex-end;
  }
}

.customer-sample-page :deep(.ant-switch-checked) {
  background: var(--customer-sample-primary);
}

.customer-sample-page :deep(.ant-select-selector),
.customer-sample-page :deep(.ant-input),
.customer-sample-page :deep(.ant-input-affix-wrapper) {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif !important;
}
</style>
