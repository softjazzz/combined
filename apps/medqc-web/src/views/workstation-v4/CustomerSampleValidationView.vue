<template>
  <main class="customer-sample-page relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
    <div
      class="customer-sample-scroll custom-scrollbar flex-1 overflow-y-auto px-4 pb-5 pt-4 xl:px-5"
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
              <a-dropdown :trigger="['click']">
                <a-button class="!rounded-lg">
                  更多操作
                </a-button>
                <template #overlay>
                  <a-menu>
                    <a-menu-item @click="handleMoreActionKey('import')">
                      导入模板
                    </a-menu-item>
                    <a-menu-item @click="handleMoreActionKey('create-test-record')">
                      创建测试病历
                    </a-menu-item>
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
                      title="导出泸县0609报告"
                    >
                      <a-menu-item @click="handleMoreActionKey('export-luxian-md')">
                        Markdown 评估报告
                      </a-menu-item>
                      <a-menu-item @click="handleMoreActionKey('export-luxian-csv')">
                        CSV 指标明细
                      </a-menu-item>
                      <a-menu-item @click="handleMoreActionKey('export-luxian-json')">
                        JSON 原始结果
                      </a-menu-item>
                    </a-sub-menu>
                    <a-menu-divider />
                    <a-sub-menu
                      key="advanced"
                      title="高级模式"
                    >
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
                <p>
                  默认运行全量 0609 客户质控点；勾选后仅验证选中的 LX0609 质控点。
                </p>
              </div>
              <div class="customer-sample-luxian-scope-actions">
                <span>{{ luxianScopeModeText }}</span>
                <a-button
                  size="small"
                  class="!rounded-lg"
                  @click="clearLuxianRuleScope"
                >
                  全量运行
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
                    <strong>{{ family.name }}</strong>
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
                    v-for="rule in family.rules"
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
              </div>
            </div>
          </section>
        </section>

        <section class="customer-sample-diagnostic-panel">
          <a-collapse
            v-model:active-key="internalDiagnosticKeys"
            ghost
            class="customer-sample-internal-collapse"
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
          v-if="syncJobDetail && isSyncJobRunning(syncJobDetail.status)"
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
          <div class="grid gap-4 px-5 py-4 md:grid-cols-2 xl:grid-cols-5">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                样本病历
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.total_candidates ?? 0 }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                可同步病历
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.eligible_visits ?? 0 }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                已完成表数
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.processed_tables ?? 0 }}/{{ syncProgress.total_tables ?? 0 }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                已拉取行数
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.total_rows_pulled ?? 0 }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                已写入行数
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.total_rows_upserted ?? 0 }}
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
              模板只需填写住院号，一行一个。
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
import { Compass, FilePlus2 } from 'lucide-vue-next'
import type {
  ManualSamplePool,
  ManualSamplePoolRecord,
  ManualSampleValidationMode,
  ManualSampleValidationRuleSet,
  ManualSamplePoolSyncJob,
  Sheet2ExactReviewAcceptancePackage,
} from './customer-sample-validation/types'
import {
  exportLuxian0609EvaluationReport,
  getSheet2ExactReviewAcceptancePackage,
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  importManualSamplePoolByUpload,
  listManualSampleValidationRuleSets,
  listManualSamplePools,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
} from '@/services/manual-case-sample-service'
import { syntheticCaseRuleFamilies } from './customer-sample-validation/syntheticCaseTemplates'
import {
  cancelSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import QCReviewDrawer from '@/components/qc/QCReviewDrawer.vue'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'
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
let customerSampleGuidePositionTimer: ReturnType<typeof setTimeout> | null = null

type CustomerSampleGuideTarget =
  | 'sample-pool'
  | 'sample-rule'
  | 'lx0609-scope'
  | 'create-record'
  | 'record-list'
  | 'run-validation'

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
    description: '这里选择本次运行的规则包。客户演示优先使用泸县0609质控点验证，页面会显示规则数量和覆盖状态。',
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

const batchResultOpen = ref(false)
const batchJobDetail = ref<SichuanBatchJob | null>(null)
const batchJobLoading = ref(false)
const cancelBatchJobLoading = ref(false)
const batchResultFocusRecord = ref<{
  visitId: string
  recordId: string
  label: string
} | null>(null)
let batchJobPollTimer: ReturnType<typeof setInterval> | null = null
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
}>()

const poolOptions = computed(() =>
  pools.value.map((item) => ({
    label: `${item.name}（${item.total_items}）`,
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
const luxianRuleFamilies = computed(() =>
  syntheticCaseRuleFamilies.map((family) => ({
    key: family.key,
    name: family.name,
    description: family.description,
    rules: family.rules,
    ruleIds: family.rules.map((rule) => rule.ruleId),
  })),
)
const luxianScopeModeText = computed(() =>
  selectedLuxianCustomerRuleIds.value.length
    ? `scoped run：${selectedLuxianCustomerRuleIds.value.length} 个客户质控点`
    : '全量 0609 客户质控点',
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
  let runnableHelp = '文书已就绪，可直接发起当前模式质控'
  if (isLuxian0609Mode.value) {
    runnableHelp = '已关联真实病历即可发起泸县0609验证；可再限定 LX0609 质控点范围'
  } else if (isFormalFastScreenMode.value) {
    runnableHelp = '已匹配且已同步，可发起正式 84 条质控'
  } else if (selectedValidationMode.value === 'programmatic') {
    runnableHelp = '已匹配且已同步，可直接发起程序规则验证'
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

const runButtonText = computed(() =>
  isFormalFastScreenMode.value
    ? selectedRecordStats.value.selectedCount > 0
      ? `发起SC全量验证（${selectedRecordStats.value.selectedCount}）`
      : '请选择病历后发起SC全量验证'
    : isLuxian0609Mode.value
      ? selectedRecordStats.value.selectedCount > 0
        ? `发起泸县0609验证（${selectedRecordStats.value.selectedCount}）`
        : '请选择病历后发起泸县0609验证'
      : selectedRecordStats.value.selectedCount > 0
        ? `发起样本验证（${selectedRecordStats.value.selectedCount}）`
        : '发起样本验证',
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
    width: 120,
    customRender: ({ record, index }) =>
      h(
        'span',
        {
          class: 'customer-sample-record-code',
          title: resolveRecordIdentifier(record),
        },
        resolveRecordDisplayCode(record, Number(index || 0)),
      ),
  },
  {
    title: '创建时间',
    key: 'created_time',
    width: 150,
    customRender: ({ record }) =>
      h(
        'span',
        { class: 'customer-sample-created-time' },
        resolveRecordCreatedTime(record) || '-',
      ),
  },
  {
    title: '患者信息',
    key: 'patient',
    width: 260,
    customRender: ({ record }) =>
      h('div', { class: 'customer-sample-patient-cell' }, [
        h('div', { class: 'customer-sample-patient-avatar' }, patientInitial(record)),
        h('div', { class: 'min-w-0' }, [
          h('div', { class: 'customer-sample-patient-name' }, resolveRecordDisplayTitle(record)),
          h('div', { class: 'customer-sample-patient-meta' }, [
            h('span', resolveRecordPatientLine(record)),
          ]),
        ]),
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
    title: '样本问题与文书范围',
    key: 'issue_scope',
    width: 560,
    customRender: ({ record }) => renderRecordSummary(record),
  },
  {
    title: '状态与操作',
    key: 'status_actions',
    width: 280,
    customRender: ({ record }) =>
      h('div', { class: 'customer-sample-state-action-cell' }, [
        renderRecordStatus(record),
        h('div', { class: 'customer-sample-action-cell' }, [
          renderPrimaryAction(record),
          h('div', { class: 'customer-sample-secondary-actions' }, buildSecondaryActions(record)),
        ]),
      ]),
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

function matchStatusTagClass(value: string): string {
  if (value === 'matched') {
    return 'customer-sample-status-badge is-success'
  }
  if (value === 'ambiguous') {
    return 'customer-sample-status-badge is-warning'
  }
  return 'customer-sample-status-badge is-danger'
}

function bundleStatusLabel(value: string): string {
  if (value === 'ready') return '已就绪'
  if (value === 'missing') return '待同步'
  if (value === 'pending') return '准备中'
  return value || '-'
}

function bundleStatusHint(value: string): string {
  if (value === 'ready') return '可以查看病历并发起样本验证。'
  if (value === 'pending') return '正在刷新文书和 bundle，请稍后再看。'
  if (value === 'missing') return '下一步执行“同步样本病历”。'
  return '请先完成病历同步。'
}

function bundleStatusTagClass(value: string): string {
  if (value === 'ready') {
    return 'customer-sample-status-badge is-success'
  }
  if (value === 'pending') {
    return 'customer-sample-status-badge is-warning'
  }
  return 'customer-sample-status-badge is-muted'
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

function resolveIssueSummaryLines(record: ManualSamplePoolRecord): string[] {
  const previews = (record.issue_preview || []).filter(Boolean)
  if (previews.length > 0) {
    return previews.slice(0, 2)
  }
  return record.issue_preview_text && record.issue_preview_text !== '-'
    ? [record.issue_preview_text]
    : []
}

function patientInitial(record: ManualSamplePoolRecord): string {
  const name = resolveRecordPatientName(record).trim()
  if (!name || name === '-') return '病'
  return name.slice(0, 1)
}

function renderRecordSummary(record: ManualSamplePoolRecord) {
  const lines = resolveIssueSummaryLines(record)
  const displayLines = lines.length ? lines.slice(0, 2) : ['当前没有人工问题摘要']
  const scopeText = summarizeRecordScope(record)
  return h('div', { class: 'customer-sample-summary-cell' }, [
    h(
      'div',
      { class: lines.length ? 'customer-sample-issue-lines' : 'customer-sample-empty-issue' },
      displayLines.map((line, index) =>
        h(
          'div',
          {
            class:
              index === 0 ? 'customer-sample-issue-primary' : 'customer-sample-issue-secondary',
          },
          line,
        ),
      ),
    ),
    h('div', { class: 'customer-sample-row-meta' }, [
      h('span', { class: 'customer-sample-issue-count' }, `共 ${record.issue_count || 0} 条问题`),
      h('span', { class: 'customer-sample-row-dot' }, '·'),
      h(
        'span',
        { class: 'customer-sample-scope-text' },
        scopeText === '-' ? '文书范围待识别' : scopeText,
      ),
    ]),
  ])
}

function renderRecordStatus(record: ManualSamplePoolRecord) {
  return h('div', { class: 'customer-sample-status-cell' }, [
    h('div', { class: 'customer-sample-status-line' }, [
      h('span', { class: 'customer-sample-status-label' }, '病历'),
      h(
        'span',
        {
          class: matchStatusTagClass(String(record.match_status || '')),
        },
        matchStatusLabel(String(record.match_status || '')),
      ),
    ]),
    h('div', { class: 'customer-sample-status-line' }, [
      h('span', { class: 'customer-sample-status-label' }, '文书'),
      h(
        'span',
        {
          class: bundleStatusTagClass(String(record.bundle_status || '')),
        },
        bundleStatusLabel(String(record.bundle_status || '')),
      ),
    ]),
  ])
}

function renderPrimaryAction(record: ManualSamplePoolRecord) {
  const primary = resolvePrimaryAction(record)
  return h(
    'button',
    {
      type: 'button',
      class: 'customer-sample-primary-action',
      onClick: primary.handler,
    },
    primary.label,
  )
}

function buildSecondaryActions(record: ManualSamplePoolRecord) {
  const actions = []
  const primary = resolvePrimaryAction(record).key
  if (primary !== 'detail') {
    actions.push(
      h(
        'a',
        {
          class: 'customer-sample-secondary-link',
          onClick: () => openRecordDetail(record),
        },
        '查看详情',
      ),
    )
  }
  if (record.matched_visit_id && primary !== 'review') {
    actions.push(
      h(
        'a',
        {
          class: 'customer-sample-secondary-link',
          onClick: () => openReviewDrawer(record),
        },
        '查看病历',
      ),
    )
  }
  if (selectedPool.value?.latest_job_id && record.matched_visit_id) {
    actions.push(
      h(
        'a',
        {
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
  return actions
}

function resolvePrimaryAction(record: ManualSamplePoolRecord): {
  key: 'detail' | 'review'
  label: string
  handler: () => void
} {
  if (record.matched_visit_id && record.bundle_status === 'ready') {
    return {
      key: 'review',
      label: '查看病历',
      handler: () => openReviewDrawer(record),
    }
  }
  return {
    key: 'detail',
    label: '查看详情',
    handler: () => openRecordDetail(record),
  }
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
    return '当前选中的病历还未完成病历关联，暂时无法发起泸县0609验证'
  }
  if (selectedValidationMode.value === 'formal_fast_screen_full') {
    return '当前选中的病历还未完成匹配或同步，暂时无法发起正式质控 84 条'
  }
  if (selectedValidationMode.value === 'programmatic') {
    return '当前选中的病历还未完成匹配或同步，暂时无法发起程序规则验证'
  }
  return '当前选中的病历还未完成匹配、同步或 bundle 准备，暂时无法发起验证'
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
  internalDiagnosticKeys.value = internalDiagnosticKeys.value.includes('sheet2') ? [] : ['sheet2']
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

async function loadPools() {
  poolLoading.value = true
  const result = await listManualSamplePools({ page: 1, page_size: 50 })
  poolLoading.value = false
  await loadExactReviewAcceptance()
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
  const shouldSortCustomerTestPool = poolId === 'customer-created-test-records-v1'
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
        .map((ruleId) => String(ruleId || '').trim().toUpperCase())
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

function clearLuxianRuleScope() {
  selectedLuxianCustomerRuleIds.value = []
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
  resetImportForm()
  message.success(`导入成功，共写入 ${result.data.imported_rows} 条样本`)
  await loadPools()
}

async function handleDownloadTemplate() {
  const XLSX = await import('xlsx')
  const workbook = XLSX.utils.book_new()
  const worksheet = XLSX.utils.aoa_to_sheet([['住院号'], ['2248248'], ['161241']])
  worksheet['!cols'] = [{ wch: 18 }]
  XLSX.utils.book_append_sheet(workbook, worksheet, '住院号')
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

function resolveRecordDisplayTitle(record: ManualSamplePoolRecord): string {
  const caseTitle = resolveRecordCaseTitle(record)
  if (caseTitle) {
    const cleaned = caseTitle
      .replace(/[-_]\d{10,}$/u, '')
      .replace(/CUSTOMER_TEST_\d+[A-Z0-9]*$/u, '')
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

function resolveRecordPatientLine(record: ManualSamplePoolRecord): string {
  const patientName = resolveRecordPatientName(record)
  const department = String(record.department || '').trim()
  return [patientName === '-' ? '' : patientName, department].filter(Boolean).join(' · ') || '-'
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

function resolveRecordDisplayCode(record: ManualSamplePoolRecord, index = 0): string {
  if (/^CUSTOMER_TEST_/u.test(resolveRecordIdentifier(record))) {
    return `测试-${String(index + 1).padStart(3, '0')}`
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

function resolveRecordCreatedTime(record: ManualSamplePoolRecord): string {
  const raw = recordSortTime(record)
  if (!raw) return ''
  return formatCompactDateTime(raw)
}

function formatCompactDateTime(value: string): string {
  const text = value.trim()
  if (!text) return ''
  const directMatch = text.match(/^(\d{4})[-/](\d{2})[-/](\d{2})[ T](\d{2}):(\d{2})/u)
  if (directMatch) {
    const [, year, month, day, hour, minute] = directMatch
    return `${year}-${month}-${day} ${hour}:${minute}`
  }
  const normalized = text.includes('T') ? text : text.replace(' ', 'T')
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const date = new Date(hasTimezone ? normalized : `${normalized}Z`)
  if (Number.isNaN(date.getTime())) return text
  const parts = new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const getPart = (type: string) => parts.find((part) => part.type === type)?.value || ''
  return `${getPart('year')}-${getPart('month')}-${getPart('day')} ${getPart('hour')}:${getPart('minute')}`
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

async function handleMatchPool() {
  if (!selectedPoolId.value) return
  matchLoading.value = true
  const result = await matchManualSamplePool(selectedPoolId.value)
  matchLoading.value = false
  if (!result.success) {
    message.error(result.message || '执行病历匹配失败')
    return
  }
  message.success('病历匹配完成')
  await loadPools()
}

async function handleSyncPoolRecords() {
  if (!selectedPoolId.value) return
  syncLoading.value = true
  const limitToIntrinsic = !isSyncedOnlyValidationMode.value
  const result = await syncManualSamplePoolRecords(selectedPoolId.value, {
    only_intrinsic: limitToIntrinsic,
    include_in_batch_1: limitToIntrinsic,
  })
  syncLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '同步样本病历失败')
    return
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
    if (lastRunSubmission.value.jobId) {
      message.info('任务已创建，正在打开进度')
      await openBatchJob(lastRunSubmission.value.jobId)
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
  const runPayload = {
    record_ids: runnableRecordIds,
    max_parallel_records: runOptions.value.maxParallelRecords,
    validation_mode: selectedValidationMode.value,
    rule_set_key: selectedRuleSetPayloadKey.value,
  } as {
    record_ids: string[]
    max_parallel_records: number
    validation_mode: ManualSampleValidationMode
    rule_set_key: string
    selected_rule_ids?: string[]
  }
  if (isLuxian0609Mode.value && selectedLuxianCustomerRuleIds.value.length) {
    runPayload.selected_rule_ids = selectedLuxianCustomerRuleIds.value
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
      await loadPools()
      await loadRecords()
    }
  }, 3000)
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

async function handleExportBatchReport(format: 'xlsx' | 'csv' = 'xlsx') {
  const jobId = String(batchJobDetail.value?.id || '').trim()
  if (!jobId) {
    message.warning('当前任务详情未加载完成，暂时无法导出报告')
    return
  }
  const result = await exportSichuanWorkspaceBatchJob({ job_id: jobId, format })
  if (!result.success || !result.data) {
    message.error(result.message || '导出验证任务失败')
    return
  }
  const blob = new Blob([result.data], {
    type:
      format === 'csv'
        ? 'text/csv;charset=utf-8'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `manual-sample-validation-${jobId}.${format}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
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

.customer-sample-luxian-rule-group-head strong {
  color: var(--customer-sample-text);
  font-size: 13px;
  font-weight: 700;
  line-height: 19px;
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

.customer-sample-patient-avatar {
  display: inline-flex;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 102, 204, 0.14);
  border-radius: 50%;
  background: var(--customer-sample-primary-soft);
  color: var(--customer-sample-primary);
  font-size: 13px;
  font-weight: 700;
}

.customer-sample-patient-name {
  overflow: hidden;
  max-width: 172px;
  color: var(--customer-sample-text);
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.customer-sample-patient-meta {
  display: flex;
  max-width: 220px;
  flex-wrap: wrap;
  gap: 3px 8px;
  color: var(--customer-sample-muted);
  font-size: 12px;
  line-height: 18px;
}

.customer-sample-record-code {
  display: inline-flex;
  max-width: 96px;
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
  gap: 8px;
  min-width: 0;
}

.customer-sample-issue-lines {
  display: grid;
  gap: 3px;
}

.customer-sample-issue-primary,
.customer-sample-issue-secondary,
.customer-sample-empty-issue {
  display: -webkit-box;
  overflow: hidden;
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
  line-height: 21px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.customer-sample-issue-secondary {
  color: rgba(29, 29, 31, 0.56);
}

.customer-sample-empty-issue {
  color: rgba(29, 29, 31, 0.38);
}

.customer-sample-row-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
}

.customer-sample-issue-count {
  color: rgba(29, 29, 31, 0.38);
  font-size: 12px;
  line-height: 18px;
}

.customer-sample-row-dot {
  color: rgba(29, 29, 31, 0.24);
  font-size: 12px;
  line-height: 18px;
}

.customer-sample-scope-text {
  overflow: hidden;
  max-width: 420px;
  color: rgba(29, 29, 31, 0.56);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.customer-sample-status-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.customer-sample-status-line {
  display: inline-grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 6px;
}

.customer-sample-status-label {
  color: rgba(29, 29, 31, 0.38);
  font-size: 12px;
  line-height: 18px;
}

.customer-sample-status-badge {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: rgba(245, 245, 247, 0.82);
  padding: 3px 9px;
  color: rgba(29, 29, 31, 0.56);
  white-space: nowrap;
  font-size: 12px;
  font-weight: 700;
  line-height: 17px;
}

.customer-sample-status-badge.is-success {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #047857;
}

.customer-sample-status-badge.is-warning {
  border-color: #fde68a;
  background: #fffbeb;
  color: #b45309;
}

.customer-sample-status-badge.is-danger {
  border-color: #fecdd3;
  background: #fff1f2;
  color: #be123c;
}

.customer-sample-status-badge.is-muted {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: var(--customer-sample-muted);
}

.customer-sample-action-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
}

.customer-sample-primary-action {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  border: 1px solid rgba(0, 102, 204, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  padding: 5px 12px;
  color: var(--customer-sample-primary);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
  transition:
    border-color 0.16s ease,
    background-color 0.16s ease;
}

.customer-sample-primary-action:hover {
  border-color: rgba(0, 102, 204, 0.32);
  background: var(--customer-sample-primary-soft);
}

.customer-sample-secondary-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  font-size: 12px;
  line-height: 18px;
}

.customer-sample-secondary-link {
  color: var(--customer-sample-muted);
  cursor: pointer;
  transition: color 0.16s ease;
}

.customer-sample-secondary-link:hover {
  color: var(--customer-sample-primary);
}

.customer-sample-department {
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
  font-weight: 520;
  white-space: nowrap;
}

.customer-sample-state-action-cell {
  display: grid;
  gap: 10px;
  min-width: 0;
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

@media (max-width: 768px) {
  .customer-sample-tour-card {
    max-width: calc(100vw - 32px);
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
