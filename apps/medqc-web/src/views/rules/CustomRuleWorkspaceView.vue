<template>
  <div
    class="custom-workspace-page custom-scrollbar min-h-[calc(100vh-64px)] overflow-y-auto px-4 pb-5 pt-4 text-slate-700 xl:px-5"
  >
    <div class="mx-auto w-full max-w-[1440px] space-y-4">
      <section
        class="cw-analysis-overview workstation-surface-enter rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div class="max-w-3xl">
            <p
              class="cw-analysis-overview__eyebrow mb-1 text-[12px] font-bold uppercase tracking-[0.16em] text-blue-500/75"
            >
              规则工作区
            </p>
            <h1 class="cw-analysis-overview__title text-[24px] font-black text-slate-800">
              自定义规则工作台
            </h1>
            <p class="cw-analysis-overview__subtitle mt-1.5 text-[13px] leading-6 text-slate-500">
              上半部分维护规则，下半部分对终末病历做单条/批量测试。规则配置统一收进右侧抽屉，不再把创建区放在页面顶部。
            </p>
          </div>

          <div class="flex min-w-[340px] flex-col gap-3 xl:max-w-[430px]">
            <div class="grid grid-cols-3 gap-2">
              <div class="cw-kpi-card rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
                <div class="text-[12px] text-slate-400">
                  规则总数
                </div>
                <div class="mt-1 text-[20px] font-black text-slate-900">
                  {{ draftPagination.total }}
                </div>
              </div>
              <div class="cw-kpi-card rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
                <div class="text-[12px] text-slate-400">
                  {{ currentScopeLabel }}
                </div>
                <div class="mt-1 text-[20px] font-black text-slate-900">
                  {{ recordPagination.total }}
                </div>
              </div>
              <div class="cw-kpi-card rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
                <div class="text-[12px] text-slate-400">
                  最近任务
                </div>
                <div class="mt-1 text-[20px] font-black text-slate-900">
                  {{ recentBatchJobCount }}
                </div>
              </div>
            </div>

            <a-button
              type="primary"
              class="cw-primary-action"
              @click="openCreateDrawer"
            >
              <template #icon>
                <PlusOutlined />
              </template>
              自定义质控规则
            </a-button>
          </div>
        </div>
      </section>

      <section
        class="cw-panel workstation-surface-enter workstation-surface-enter--delay-1 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div class="mb-2 flex items-center justify-between gap-3">
          <div>
            <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              规则目录
            </p>
            <h2 class="text-lg font-black text-slate-900">
              自定义规则列表
            </h2>
          </div>
          <a-button
            size="small"
            class="!h-9 !rounded-lg !border-slate-200 !bg-white !text-slate-500 hover:!border-slate-300 hover:!text-slate-700"
            :loading="draftLoading"
            @click="loadDrafts"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            刷新
          </a-button>
          <span class="text-xs text-slate-400">已勾选 {{ selectedDraftIds.length }} 条用于执行</span>
        </div>

        <div class="mb-3 flex flex-wrap items-center gap-2 md:flex-nowrap">
          <a-input
            v-model:value="draftQuery.keyword"
            allow-clear
            placeholder="搜索规则编码/名称"
            class="min-w-[260px] flex-1 !h-9 !rounded-lg !border-slate-200"
            @press-enter="searchDrafts"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input>
          <a-select
            v-model:value="draftQuery.status"
            allow-clear
            placeholder="规则状态"
            :options="draftStatusOptions"
            class="w-[148px] [&_.ant-select-selector]:!h-9 [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200"
            @change="searchDrafts"
          />
        </div>

        <template v-if="drafts.length > 0 || draftLoading">
          <a-table
            row-key="id"
            size="small"
            :loading="draftLoading"
            :columns="draftColumns"
            :data-source="drafts"
            :row-selection="draftRowSelection"
            :pagination="draftPagination"
            :row-class-name="draftRowClassName"
            :custom-row="draftCustomRow"
            :scroll="{ y: 180 }"
            @change="handleDraftTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'rule_code'">
                <span class="font-mono font-bold text-slate-700">{{ record.rule_code }}</span>
              </template>
              <template v-else-if="column.key === 'name'">
                <div class="font-semibold text-slate-900">
                  {{ record.name || '未命名规则' }}
                </div>
                <div class="truncate text-xs text-slate-400">
                  {{ record.source_requirement || record.description || '-' }}
                </div>
              </template>
              <template v-else-if="column.key === 'scene'">
                <a-tag
                  class="cw-scene-tag"
                  :class="
                    record.scene === 'final' ? 'cw-scene-tag--final' : 'cw-scene-tag--running'
                  "
                >
                  {{ record.scene === 'final' ? '终末病历' : '运行病历' }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag
                  class="cw-status-tag"
                  :class="
                    record.status === 'published'
                      ? 'cw-status-tag--published'
                      : 'cw-status-tag--draft'
                  "
                >
                  {{ record.status === 'published' ? '已发布' : '草稿' }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'last_test_summary'">
                <div class="text-xs leading-5 text-slate-500">
                  <div>成功 {{ getSummarySuccessCount(record as CustomRuleDraft) }}</div>
                  <div>命中 {{ getSummaryIssueCount(record as CustomRuleDraft) }}</div>
                </div>
              </template>
              <template v-else-if="column.key === 'updated_at'">
                <span class="text-xs text-slate-500">{{ formatDateTime(record.updated_at) }}</span>
              </template>
              <template v-else-if="column.key === 'actions'">
                <div class="cw-draft-actions">
                  <a-button
                    type="text"
                    size="small"
                    class="cw-draft-action-btn cw-draft-action-btn--edit"
                    @click.stop="openEditDrawer(record as CustomRuleDraft)"
                  >
                    <template #icon>
                      <EditOutlined />
                    </template>
                  </a-button>
                  <a-button
                    type="text"
                    size="small"
                    class="cw-draft-action-btn cw-draft-action-btn--copy"
                    @click.stop="copyDraft(record as CustomRuleDraft)"
                  >
                    <template #icon>
                      <CopyOutlined />
                    </template>
                  </a-button>
                  <a-popconfirm
                    title="确认删除该规则草稿？"
                    @confirm="deleteDraft(record as CustomRuleDraft)"
                  >
                    <a-button
                      type="text"
                      danger
                      size="small"
                      class="cw-draft-action-btn cw-draft-action-btn--delete"
                      @click.stop
                    >
                      <template #icon>
                        <DeleteOutlined />
                      </template>
                    </a-button>
                  </a-popconfirm>
                  <a-button
                    v-if="record.status === 'draft'"
                    type="text"
                    size="small"
                    class="cw-draft-publish-btn"
                    :disabled="!canPublishRules || !canPublishRecord(record as CustomRuleDraft)"
                    @click.stop="publishDraftById(record.id)"
                  >
                    {{ canPublishRules ? '发布' : '待审核' }}
                  </a-button>
                </div>
              </template>
            </template>
          </a-table>
        </template>
        <a-empty
          v-else
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
          class="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 py-8"
        >
          <template #image>
            <div
              class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-300 shadow-sm"
            >
              <FileSearchOutlined class="text-[28px]" />
            </div>
          </template>
          <template #description>
            <div class="text-sm text-slate-400">
              暂无自定义规则，点击右上角“自定义质控规则”开始创建
            </div>
          </template>
        </a-empty>
      </section>

      <section
        class="cw-panel workstation-surface-enter workstation-surface-enter--delay-2 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div>
            <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              真实病历质控台
            </p>
            <h2 class="text-lg font-black text-slate-900">
              真实病历质控台
            </h2>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <a-button
              :disabled="!batchJobs.length"
              :loading="batchJobLoading"
              @click="openLatestBatchJobDrawer"
            >
              <template #icon>
                <FileSearchOutlined />
              </template>查看任务结果
            </a-button>
            <a-button
              :disabled="!hasSelectedRunDrafts || !allSelectedRunDraftPromptReady"
              :loading="testingBatch"
              @click="triggerBatchQcJob"
            >
              <template #icon>
                <PlayCircleOutlined />
              </template>发起批量质控
            </a-button>
            <a-button
              type="primary"
              :disabled="!selectedDraft || !canPublishRules || !canPublishSelectedDraft"
              :loading="publishingDraft"
              @click="publishSelectedDraft"
            >
              <template #icon>
                <RocketOutlined />
              </template>{{ publishActionLabel }}
            </a-button>
          </div>
        </div>

        <div
          v-if="selectedDraft"
          class="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-100 bg-blue-50/70 px-3 py-2"
        >
          <div>
            <span class="mr-2 text-xs font-bold text-blue-700">当前规则</span>
            <strong class="text-slate-900">{{
              selectedDraft.name || selectedDraft.rule_code
            }}</strong>
            <span class="ml-2 text-xs text-slate-500">{{ selectedDraft.document_type }} /
              {{ selectedDraft.scene === 'final' ? '终末病历' : '运行病历' }}</span>
            <span class="ml-2 text-xs text-blue-600">已勾选执行 {{ selectedDraftIds.length }} 条</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <a-tag :color="selectedDraft.status === 'published' ? 'success' : 'processing'">
              {{ selectedDraft.status === 'published' ? '已发布' : '草稿' }}
            </a-tag>
            <a-button
              size="small"
              @click="openEditDrawer(selectedDraft)"
            >
              <template #icon>
                <EditOutlined />
              </template>编辑规则
            </a-button>
          </div>
        </div>
        <div
          v-else
          class="mb-3 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
        >
          <span class="text-xs font-bold">!</span>
          <div>
            <div class="font-semibold">
              请先在上方选择一条自定义规则
            </div>
            <div class="text-xs text-amber-700">
              未选中规则时仍可浏览 {{ currentScopeLabel }}，但测试按钮会禁用。
            </div>
          </div>
        </div>

        <div class="mb-3 rounded-xl border border-slate-200 bg-slate-50/80 p-3">
          <div class="mb-2 flex items-center justify-between gap-2">
            <div>
              <div class="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
                批量任务
              </div>
              <div class="text-sm font-semibold text-slate-800">
                最近批量任务
              </div>
            </div>
            <span class="text-xs text-slate-400">共 {{ batchJobPagination.total }} 个</span>
          </div>
          <div class="mb-2 flex flex-wrap items-center gap-2">
            <div
              v-if="canViewProjectBatchJobs"
              class="flex rounded-lg border border-slate-200 bg-white p-1"
            >
              <button
                type="button"
                class="rounded-md px-2.5 py-1 text-xs font-medium transition"
                :class="
                  batchJobQuery.mineOnly
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                "
                @click="changeBatchJobOwnership(true)"
              >
                我的任务
              </button>
              <button
                type="button"
                class="rounded-md px-2.5 py-1 text-xs font-medium transition"
                :class="
                  !batchJobQuery.mineOnly
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                "
                @click="changeBatchJobOwnership(false)"
              >
                全部项目
              </button>
            </div>
            <div class="flex rounded-lg border border-slate-200 bg-white p-1">
              <button
                type="button"
                class="rounded-md px-2.5 py-1 text-xs font-medium transition"
                :class="
                  batchJobQuery.onlyCurrentRule
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                "
                @click="changeBatchJobRuleScope(true)"
              >
                当前规则
              </button>
              <button
                type="button"
                class="rounded-md px-2.5 py-1 text-xs font-medium transition"
                :class="
                  !batchJobQuery.onlyCurrentRule
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                "
                @click="changeBatchJobRuleScope(false)"
              >
                全部历史
              </button>
            </div>
            <a-input
              v-model:value="batchJobQuery.keyword"
              allow-clear
              placeholder="搜索规则名称/编码/任务ID"
              class="min-w-[220px] flex-1 !rounded-lg !border-slate-200 !bg-white"
              @press-enter="searchBatchJobs"
            >
              <template #prefix>
                <SearchOutlined />
              </template>
            </a-input>
            <a-select
              v-model:value="batchJobQuery.status"
              allow-clear
              placeholder="任务状态"
              :options="batchJobStatusOptions"
              class="w-[124px] [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-white"
              @change="searchBatchJobs"
            />
            <a-select
              v-model:value="batchJobQuery.scope"
              allow-clear
              placeholder="病历范围"
              :options="batchJobScopeOptions"
              class="w-[124px] [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-white"
              @change="searchBatchJobs"
            />
            <a-select
              v-model:value="batchJobQuery.execution_mode"
              allow-clear
              placeholder="执行类型"
              :options="batchJobExecutionModeOptions"
              class="w-[124px] [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-white"
              @change="searchBatchJobs"
            />
            <a-range-picker
              v-model:value="batchJobQuery.dateRange"
              class="w-[260px]"
              @change="searchBatchJobs"
            />
            <a-button
              class="!rounded-lg !border-slate-200 !bg-white !text-slate-500 hover:!border-slate-300 hover:!text-slate-700"
              :loading="batchJobLoading"
              @click="searchBatchJobs"
            >
              <template #icon>
                <ReloadOutlined />
              </template>
              刷新
            </a-button>
          </div>
          <a-empty
            v-if="!batchJobs.length && !batchJobLoading"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
            class="py-2"
            description="暂无批量任务"
          />
          <div
            v-else
            class="space-y-2"
          >
            <button
              v-for="job in batchJobs"
              :key="job.id"
              type="button"
              class="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition"
              :class="
                batchJobDetail?.id === job.id
                  ? 'border-blue-200 bg-blue-50'
                  : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
              "
              @click="openBatchJobDrawer(job)"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-semibold text-slate-800">{{
                    job.rule_name || job.rule_code
                  }}</span>
                  <a-tag :class="getBatchJobStatusTagClass(job.status)">
                    {{ getBatchJobStatusText(job.status) }}
                  </a-tag>
                  <a-tag>{{ scopeLabelMap[job.scope] }}</a-tag>
                  <a-tag>{{ job.execution_mode === 'single' ? '单条' : '批量' }}</a-tag>
                </div>
                <div class="mt-1 text-xs text-slate-500">
                  {{ formatDateTime(job.created_at) }} · 成功 {{ job.success_count }} · 失败
                  {{ job.failed_count }} · 命中 {{ job.issue_records }}
                </div>
                <div
                  v-if="!batchJobQuery.mineOnly"
                  class="mt-1 text-[11px] text-slate-400"
                >
                  发起人 {{ job.created_by || '-' }}
                </div>
              </div>
              <span class="text-xs text-slate-400">{{ job.record_ids?.length || job.total_records || 0 }} 条</span>
            </button>
            <div class="flex items-center justify-end">
              <a-pagination
                size="small"
                :current="batchJobPagination.current"
                :page-size="batchJobPagination.pageSize"
                :total="batchJobPagination.total"
                :show-size-changer="false"
                @change="(page, pageSize) => handleBatchJobTableChange({ current: page, pageSize })"
              />
            </div>
          </div>
        </div>

        <div
          class="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2.5"
        >
          <div class="flex rounded-lg border border-slate-200 bg-slate-50 p-1">
            <button
              v-for="scopeOption in scopeOptions"
              :key="scopeOption.value"
              type="button"
              class="rounded-md px-2.5 py-1 text-xs font-medium transition"
              :class="
                recordFilters.scope === scopeOption.value
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-500 hover:bg-white hover:text-slate-700'
              "
              @click="changeScope(scopeOption.value)"
            >
              {{ scopeOption.label }}
            </button>
          </div>
          <a-input
            v-model:value="recordFilters.keyword"
            allow-clear
            placeholder="搜索病历号 / 就诊号 / 患者姓名"
            class="min-w-[240px] flex-1 !rounded-lg !border-slate-200"
            @press-enter="searchRecords"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input>
          <a-select
            v-model:value="recordFilters.department"
            allow-clear
            show-search
            :options="departmentOptions"
            placeholder="科室"
            class="w-[112px] [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-white"
            @change="handleDepartmentChange"
          />
          <a-select
            v-model:value="recordFilters.doctor"
            allow-clear
            show-search
            :options="doctorOptions"
            placeholder="医生"
            class="w-[112px] [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-white"
          />
          <a-select
            v-model:value="recordFilters.date_field"
            :options="dateFieldOptions"
            class="w-[124px] [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200 [&_.ant-select-selector]:!bg-white"
          />
          <a-range-picker
            v-model:value="recordFilters.dateRange"
            class="w-[240px] !rounded-lg !border-slate-200 !bg-white"
          />
          <div class="ml-auto flex gap-1">
            <a-button
              type="text"
              size="small"
              class="!text-slate-500 hover:!text-slate-700"
              @click="searchRecords"
            >
              查询病历
            </a-button>
            <a-button
              type="text"
              size="small"
              class="!text-slate-500 hover:!text-slate-700"
              :loading="recordLoading"
              @click="refreshRecords"
            >
              <template #icon>
                <ReloadOutlined />
              </template>刷新
            </a-button>
          </div>
        </div>

        <a-collapse
          v-model:active-key="testSettingsActiveKeys"
          ghost
          class="mb-2"
        >
          <a-collapse-panel
            key="testing"
            header="测试设置"
          >
            <div class="grid gap-3 md:grid-cols-3">
              <a-form-item label="temperature">
                <a-input-number
                  v-model:value="advancedParams.temperature"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  class="w-full"
                />
              </a-form-item>
              <a-form-item label="top_p">
                <a-input-number
                  v-model:value="advancedParams.top_p"
                  :min="0"
                  :max="1"
                  :step="0.05"
                  class="w-full"
                />
              </a-form-item>
              <a-form-item label="max_tokens">
                <a-input-number
                  v-model:value="advancedParams.max_tokens"
                  :min="256"
                  :max="16000"
                  :step="256"
                  class="w-full"
                />
              </a-form-item>
            </div>
          </a-collapse-panel>
        </a-collapse>

        <div class="mb-2 flex items-center justify-between text-xs text-slate-500">
          <span>已选择 {{ selectedRecordKeys.length }} 条{{ currentScopeLabel }}</span>
          <div class="flex gap-1">
            <a-button
              type="text"
              size="small"
              class="!text-slate-500 hover:!text-slate-700"
              @click="selectCurrentPageRecords"
            >
              全选当前页
            </a-button>
            <a-button
              type="text"
              size="small"
              class="!text-slate-500 hover:!text-slate-700"
              @click="selectedRecordKeys = []"
            >
              清空
            </a-button>
          </div>
        </div>

        <a-table
          row-key="record_id"
          size="small"
          :loading="recordLoading"
          :columns="recordColumns"
          :data-source="records"
          :pagination="recordPagination"
          :row-selection="recordRowSelection"
          class="record-bench-table"
          :scroll="{ x: 1180, y: 420 }"
          @change="handleRecordTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'record_info'">
              <div>
                <div class="font-mono font-bold text-slate-800">
                  {{ record.record_id || '-' }}
                </div>
                <div class="text-xs text-slate-400">
                  {{ record.visit_id || '-' }}
                </div>
              </div>
            </template>
            <template v-else-if="column.key === 'patient_name'">
              <div class="min-w-0">
                <div class="truncate text-[13px] font-semibold text-slate-700">
                  {{ record.patient_name || '未知患者' }}
                </div>
                <div class="truncate text-[12px] text-slate-400">
                  {{ record.department || '-' }} / {{ record.doctor || '-' }}
                </div>
              </div>
            </template>
            <template v-else-if="column.key === 'department'">
              <div class="min-w-0">
                <div class="truncate text-[13px] font-medium text-slate-600">
                  {{ record.department || '-' }}
                </div>
                <div class="truncate text-[12px] text-slate-400">
                  {{ record.doctor || '-' }}
                </div>
              </div>
            </template>
            <template v-else-if="column.key === 'doctor'">
              <div class="min-w-0">
                <div class="truncate text-[13px] font-medium text-slate-600">
                  {{ record.doctor || '-' }}
                </div>
                <div class="truncate text-[12px] text-slate-400">
                  {{ record.discharge_date || '-' }}
                </div>
              </div>
            </template>
            <template v-else-if="column.key === 'latest_status'">
              <span
                class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium"
                :class="getRecordResultTagClass(record.record_id)"
              >
                {{ getRecordResultStatusText(record.record_id) }}
              </span>
            </template>
            <template v-else-if="column.key === 'latest_findings'">
              <span class="text-xs leading-6 text-slate-500">{{
                getRecordFindingPreview(record.record_id)
              }}</span>
            </template>
            <template v-else-if="column.key === 'actions'">
              <div class="record-action-cell flex items-center justify-end gap-2">
                <a-button
                  size="small"
                  class="record-action-btn"
                  :disabled="!hasSelectedRunDrafts || !allSelectedRunDraftPromptReady"
                  :loading="testingSingleRecordId === record.record_id"
                  @click="runSingleTest(record as CustomRuleWorkspaceRecord)"
                >
                  <template #icon>
                    <PlayCircleOutlined />
                  </template>
                  单条测试
                </a-button>
                <a-button
                  size="small"
                  class="record-action-btn"
                  :disabled="!hasRecordResult(record.record_id)"
                  @click="openSingleResultDrawer(record as CustomRuleWorkspaceRecord)"
                >
                  <template #icon>
                    <FileSearchOutlined />
                  </template>
                  查看结果
                </a-button>
              </div>
            </template>
          </template>
        </a-table>

        <div class="mt-4 rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
          <div class="mb-3 flex items-center justify-between gap-2">
            <div>
              <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
                结果中心
              </p>
              <h3 class="text-lg font-black text-slate-900">
                质控结果中心
              </h3>
            </div>
            <div class="flex items-center gap-2">
              <a-button
                v-if="activeBatchJob && activeBatchJob.status === 'completed'"
                :loading="batchJobDetailLoading"
                @click="exportBatchJobReport('xlsx')"
              >
                <template #icon>
                  <DownloadOutlined />
                </template>导出报告
              </a-button>
              <a-button
                v-if="activeBatchJob && ['queued', 'running'].includes(activeBatchJob.status)"
                danger
                :loading="cancellingBatchJobId === activeBatchJob.id"
                @click="cancelActiveBatchJob"
              >
                停止任务
              </a-button>
              <a-button @click="closeResultDrawer">
                清空展示
              </a-button>
            </div>
          </div>

          <template v-if="resultDrawerMode === 'batch' && activeBatchSummary">
            <div class="grid gap-3 md:grid-cols-5">
              <div class="rounded-xl border border-slate-200 bg-white p-3 text-center">
                <div class="text-xs text-slate-400">
                  总病历
                </div>
                <div class="text-xl font-bold text-slate-900">
                  {{ activeBatchSummary.total_records }}
                </div>
              </div>
              <div class="rounded-xl border border-slate-200 bg-white p-3 text-center">
                <div class="text-xs text-slate-400">
                  成功
                </div>
                <div class="text-xl font-bold text-slate-900">
                  {{ activeBatchSummary.success_count }}
                </div>
              </div>
              <div class="rounded-xl border border-slate-200 bg-white p-3 text-center">
                <div class="text-xs text-slate-400">
                  失败
                </div>
                <div class="text-xl font-bold text-slate-900">
                  {{ activeBatchSummary.failed_count }}
                </div>
              </div>
              <div class="rounded-xl border border-slate-200 bg-white p-3 text-center">
                <div class="text-xs text-slate-400">
                  命中
                </div>
                <div class="text-xl font-bold text-slate-900">
                  {{ activeBatchSummary.issue_records }}
                </div>
              </div>
              <div class="rounded-xl border border-slate-200 bg-white p-3 text-center">
                <div class="text-xs text-slate-400">
                  规则数
                </div>
                <div class="text-xl font-bold text-slate-900">
                  {{ activeBatchJob?.rule_count || activeBatchRuleResults.length || 1 }}
                </div>
              </div>
            </div>

            <div
              v-if="activeBatchRuleResults.length"
              class="mt-3 rounded-xl border border-slate-200 bg-white p-3"
            >
              <div class="mb-2 text-sm font-semibold text-slate-800">
                规则执行结果
              </div>
              <div class="space-y-2">
                <div
                  v-for="ruleResult in activeBatchRuleResults"
                  :key="ruleResult.id || `${ruleResult.draft_id}-${ruleResult.rule_code}`"
                  class="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs"
                >
                  <span class="font-medium text-slate-700">{{
                    ruleResult.rule_name || ruleResult.rule_code
                  }}</span>
                  <span class="text-slate-500">成功 {{ ruleResult.success_count || 0 }} · 失败
                    {{ ruleResult.failed_count || 0 }} · 命中
                    {{ ruleResult.issue_records || 0 }}</span>
                </div>
              </div>
            </div>

            <div class="mt-3 grid gap-3 md:grid-cols-2">
              <div class="rounded-xl border border-slate-200 bg-white p-3">
                <div class="mb-2 text-sm font-semibold text-slate-800">
                  命中明细
                </div>
                <div class="max-h-[320px] space-y-2 overflow-auto">
                  <div
                    v-for="item in activeBatchItems"
                    :key="`${item.record_id}-${item.rule_code || ''}-${item.findings || ''}`"
                    class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="font-medium text-slate-700">{{
                        item.patient_name || item.record_id
                      }}</span>
                      <a-tag :class="getQcOutcomeTagClass(item.is_compliant)">
                        {{ item.is_compliant ? '合规/不适用' : '命中问题' }}
                      </a-tag>
                    </div>
                    <div class="mt-1 text-xs text-slate-500">
                      {{ item.rule_name || item.rule_code || '-' }} · {{ item.record_id }} /
                      {{ item.department || '-' }}
                    </div>
                  </div>
                </div>
              </div>
              <div class="rounded-xl border border-slate-200 bg-white p-3">
                <div class="mb-2 text-sm font-semibold text-slate-800">
                  失败明细
                </div>
                <div class="max-h-[320px] space-y-2 overflow-auto">
                  <div
                    v-for="item in activeBatchFailedRecords"
                    :key="`${item.record_id}-${item.rule_code || ''}-${item.error}`"
                    class="rounded-lg border border-rose-100 bg-rose-50 px-3 py-2"
                  >
                    <div class="text-xs font-medium text-rose-700">
                      {{ item.rule_name || item.rule_code || '-' }}
                    </div>
                    <div class="mt-1 text-xs text-slate-500">
                      {{ item.record_id }} / {{ item.department || '-' }}
                    </div>
                    <div class="mt-1 text-xs text-rose-700">
                      {{ item.error }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="resultDrawerMode === 'single' && resultDrawerRecord">
            <div class="rounded-xl border border-slate-200 bg-white p-4">
              <div class="flex items-center justify-between gap-2">
                <strong>{{
                  resultDrawerRecord.patient_name || resultDrawerRecord.record_id
                }}</strong>
                <a-tag :class="getQcOutcomeTagClass(resultDrawerRecord.is_compliant)">
                  {{ resultDrawerRecord.is_compliant ? '合规/不适用' : '命中问题' }}
                </a-tag>
              </div>
              <div class="mt-2 text-xs text-slate-400">
                {{ resultDrawerRecord.rule_name || resultDrawerRecord.rule_code || '-' }} ·
                {{ resultDrawerRecord.record_id }} / {{ resultDrawerRecord.department || '-' }}
              </div>
              <div
                class="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-7 text-slate-600"
              >
                {{ resultDrawerRecord.findings || '无附加结论' }}
              </div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <div
                  class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600"
                >
                  <div class="mb-1 font-semibold text-slate-700">
                    证据
                  </div>
                  {{ resultDrawerRecord.evidence || '无' }}
                </div>
                <div
                  class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600"
                >
                  <div class="mb-1 font-semibold text-slate-700">
                    建议
                  </div>
                  {{ resultDrawerRecord.suggestion || '无' }}
                </div>
              </div>
            </div>
          </template>

          <a-empty
            v-else
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
            description="选择历史任务或执行测试后，这里展示结果"
          />
        </div>
      </section>
    </div>

    <a-modal
      v-model:open="batchLaunchModalOpen"
      title="发起批量质控"
      :confirm-loading="testingBatch"
      ok-text="确认发起"
      cancel-text="取消"
      @ok="confirmBatchLaunch"
    >
      <div class="space-y-3">
        <div
          class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500"
        >
          <div>
            已选择规则 {{ selectedRunDrafts.length }} 条
            <span v-if="selectedRunSceneLabel">（{{ selectedRunSceneLabel }}）</span>
          </div>
          <div
            v-if="selectedRecordKeys.length > 0"
            class="mt-1 text-blue-600"
          >
            已手动勾选 {{ selectedRecordKeys.length }} 条病历，执行时将优先使用勾选病历。
          </div>
        </div>
        <a-form layout="vertical">
          <div class="grid gap-3 md:grid-cols-2">
            <a-form-item label="病历范围">
              <a-select
                v-model:value="batchLaunchFilters.scope"
                :options="scopeOptions"
                :disabled="batchLaunchFiltersLoading"
                @change="(value) => handleBatchLaunchScopeChange(value as WorkspaceScope)"
              />
            </a-form-item>
            <a-form-item label="日期字段">
              <a-select
                v-model:value="batchLaunchFilters.date_field"
                :options="dateFieldOptions"
              />
            </a-form-item>
          </div>
          <div class="grid gap-3 md:grid-cols-2">
            <a-form-item label="科室">
              <a-select
                v-model:value="batchLaunchFilters.department"
                allow-clear
                show-search
                :options="batchLaunchDepartmentOptions"
                placeholder="全部科室"
                :loading="batchLaunchFiltersLoading"
                @change="handleBatchLaunchDepartmentChange"
              />
            </a-form-item>
            <a-form-item label="医生">
              <a-select
                v-model:value="batchLaunchFilters.doctor"
                allow-clear
                show-search
                :options="batchLaunchDoctorOptions"
                placeholder="全部医生"
                :loading="batchLaunchFiltersLoading"
              />
            </a-form-item>
          </div>
          <a-form-item label="日期范围">
            <a-range-picker
              v-model:value="batchLaunchFilters.dateRange"
              class="w-full"
            />
          </a-form-item>
          <a-form-item label="关键词（可选）">
            <a-input
              v-model:value="batchLaunchFilters.keyword"
              allow-clear
              placeholder="病历号 / 就诊号 / 患者姓名"
            />
          </a-form-item>
        </a-form>
      </div>
    </a-modal>

    <a-drawer
      :open="editorDrawerOpen"
      placement="right"
      :width="720"
      :closable="false"
      :body-style="{ padding: 0 }"
      @close="closeEditorDrawer"
    >
      <div class="flex h-full flex-col bg-slate-50">
        <div
          class="flex items-start justify-between gap-4 border-b border-slate-200 bg-white px-6 py-5"
        >
          <div>
            <p class="mb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              规则编辑
            </p>
            <h2 class="text-2xl font-black text-slate-900">
              {{ editorDrawerTitle }}
            </h2>
            <p class="mt-2 text-sm leading-6 text-slate-500">
              在抽屉内完成元数据、提示词、示例和发布动作。
            </p>
          </div>
          <a-button
            type="text"
            @click="closeEditorDrawer"
          >
            <template #icon>
              <CloseOutlined />
            </template>
          </a-button>
        </div>

        <div class="flex-1 space-y-4 overflow-auto p-6">
          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <a-form layout="vertical">
              <div class="grid gap-3 md:grid-cols-2">
                <a-form-item
                  label="规则名称"
                  required
                >
                  <a-input
                    v-model:value="draftForm.name"
                    placeholder="例如：出院记录缺少出院带药明细"
                    class="drawer-meta-control-input"
                  />
                </a-form-item>
                <a-form-item
                  label="适用文书"
                  required
                >
                  <a-select
                    v-model:value="draftForm.document_type"
                    :options="documentTypeOptions"
                    class="drawer-meta-control-select"
                  />
                </a-form-item>
              </div>
              <div class="grid gap-3 md:grid-cols-2">
                <a-form-item label="病历范围">
                  <a-select
                    v-model:value="draftForm.scene"
                    :options="sceneOptions"
                  />
                </a-form-item>
                <a-form-item label="复杂度">
                  <a-select
                    v-model:value="draftForm.complexity"
                    :options="complexityOptions"
                  />
                </a-form-item>
              </div>
              <div class="grid gap-3 md:grid-cols-2">
                <a-form-item label="缺陷级别">
                  <a-select
                    v-model:value="draftForm.defect_level"
                    :options="defectLevelOptions"
                  />
                </a-form-item>
                <a-form-item label="严重程度">
                  <a-select
                    v-model:value="draftForm.severity"
                    :options="severityOptions"
                  />
                </a-form-item>
              </div>
              <a-form-item
                label="需求描述"
                required
              >
                <a-textarea
                  v-model:value="draftForm.source_requirement"
                  :rows="5"
                  :maxlength="1200"
                  show-count
                />
              </a-form-item>
              <div class="mt-[-6px] flex justify-center">
                <a-button
                  type="primary"
                  :loading="drawerGenerateLoading"
                  @click="saveAndGeneratePromptFromDrawer"
                >
                  <template #icon>
                    <RobotOutlined />
                  </template>AI生成质控规则
                </a-button>
              </div>
            </a-form>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <p class="mb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              示例
            </p>
            <h3 class="text-lg font-black text-slate-900">
              示例区
            </h3>
            <div class="mt-3 grid gap-3 md:grid-cols-2">
              <a-form-item label="合规示例">
                <a-textarea
                  v-model:value="draftForm.positive_example"
                  :rows="4"
                />
              </a-form-item>
              <a-form-item label="不合规模例">
                <a-textarea
                  v-model:value="draftForm.negative_example"
                  :rows="4"
                />
              </a-form-item>
            </div>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <p class="mb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              提示词
            </p>
            <h3 class="text-lg font-black text-slate-900">
              质控提示词
            </h3>
            <p class="mt-1 text-xs text-slate-500">
              点击“AI生成质控规则”后可在此查看和手工调整提示词内容。
            </p>
            <a-form-item
              class="mt-3"
              label="提示词模板"
            >
              <a-textarea
                v-model:value="draftForm.prompt_template"
                :rows="12"
                :maxlength="20000"
                show-count
                placeholder="生成后将在此展示完整提示词，可手工微调。"
              />
            </a-form-item>
            <div
              v-if="draftForm.prompt_summary || draftForm.check_points.length"
              class="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3"
            >
              <div
                v-if="draftForm.prompt_summary"
                class="text-xs leading-5 text-slate-600"
              >
                <span class="font-semibold text-slate-700">摘要：</span>{{ draftForm.prompt_summary }}
              </div>
              <div v-if="draftForm.check_points.length">
                <div class="mb-1 text-xs font-semibold text-slate-700">
                  检查要点
                </div>
                <div class="flex flex-wrap gap-2">
                  <a-tag
                    v-for="(point, idx) in draftForm.check_points"
                    :key="`${idx}-${point}`"
                    color="blue"
                  >
                    {{ point }}
                  </a-tag>
                </div>
              </div>
            </div>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <p class="mb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              测试输入
            </p>
            <h3 class="text-lg font-black text-slate-900">
              抽屉内测试输入
            </h3>
            <div class="mt-3">
              <a-radio-group
                v-model:value="drawerTestInput.mode"
                size="small"
              >
                <a-radio-button value="selected_record">
                  选择内置病历
                </a-radio-button>
                <a-radio-button value="manual_text">
                  粘贴病历文本
                </a-radio-button>
              </a-radio-group>
            </div>
            <div
              v-if="drawerTestInput.mode === 'selected_record'"
              class="mt-3"
            >
              <a-select
                v-model:value="drawerTestInput.selected_record_id"
                show-search
                allow-clear
                placeholder="请选择测试病历（来自下方病历列表）"
                :options="drawerTestRecordOptions"
                class="w-full"
                :filter-option="
                  (input, option) =>
                    String(option?.label || '')
                      .toLowerCase()
                      .includes(String(input || '').toLowerCase())
                "
              />
              <p class="mt-2 text-xs text-slate-400">
                如不在此选择，也可以在下方病历列表勾选后测试。
              </p>
            </div>
            <div
              v-else
              class="mt-3 space-y-2"
            >
              <a-input
                v-model:value="drawerTestInput.manual_patient_name"
                placeholder="文本来源标识（可选）"
              />
              <a-textarea
                v-model:value="drawerTestInput.manual_text"
                :rows="6"
                :maxlength="20000"
                show-count
                placeholder="粘贴一段病历文本后，可直接触发规则测试"
              />
            </div>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <p class="mb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              最近测试摘要
            </p>
            <h3 class="text-lg font-black text-slate-900">
              测试摘要
            </h3>
            <div
              v-if="selectedDraft"
              class="mt-3 grid gap-3 md:grid-cols-4"
            >
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <div class="text-[11px] text-slate-400">
                  成功
                </div>
                <div class="mt-1 text-lg font-bold text-slate-900">
                  {{ getSummarySuccessCount(selectedDraft) }}
                </div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <div class="text-[11px] text-slate-400">
                  失败
                </div>
                <div class="mt-1 text-lg font-bold text-slate-900">
                  {{ getSummaryFailedCount(selectedDraft) }}
                </div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <div class="text-[11px] text-slate-400">
                  命中问题
                </div>
                <div class="mt-1 text-lg font-bold text-slate-900">
                  {{ getSummaryIssueCount(selectedDraft) }}
                </div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <div class="text-[11px] text-slate-400">
                  可发布
                </div>
                <div class="mt-1 text-lg font-bold text-slate-900">
                  {{ canPublishSelectedDraft ? '是' : '否' }}
                </div>
              </div>
            </div>
            <a-empty
              v-else
              description="新建规则保存后，将在这里展示最近一次测试摘要。"
            />
          </div>
        </div>

        <div
          class="flex items-center justify-end gap-2 border-t border-slate-200 bg-white px-6 py-4"
        >
          <span class="mr-auto text-xs text-slate-400">
            {{ drawerTestTargetHint }}
          </span>
          <a-button @click="closeEditorDrawer">
            取消
          </a-button>
          <a-button
            :loading="drawerPrimaryLoading"
            @click="saveDraftFromDrawer"
          >
            保存草稿
          </a-button>
          <a-button
            type="primary"
            ghost
            :loading="drawerTestActionLoading"
            :disabled="!drawerCanRunTest"
            @click="saveAndRunTestFromDrawer"
          >
            保存并测试
          </a-button>
          <a-button
            type="primary"
            :disabled="!selectedDraft || !canPublishRules || !canPublishSelectedDraft"
            :loading="publishingDraft"
            @click="publishSelectedDraft"
          >
            {{ publishActionLabel }}
          </a-button>
        </div>
      </div>
    </a-drawer>

    <a-drawer
      :open="resultDrawerOpen"
      placement="right"
      :width="620"
      :closable="false"
      :body-style="{ padding: 0 }"
      @close="closeResultDrawer"
    >
      <div class="flex h-full flex-col bg-slate-50">
        <div
          class="flex items-start justify-between gap-4 border-b border-slate-200 bg-white px-6 py-5"
        >
          <div>
            <p class="mb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              测试结果
            </p>
            <h2 class="text-2xl font-black text-slate-900">
              {{ resultDrawerMode === 'batch' ? '批量任务结果' : '单病历测试结果' }}
            </h2>
          </div>
          <div class="flex items-center gap-2">
            <a-button
              v-if="
                resultDrawerMode === 'batch' &&
                  activeBatchJob &&
                  activeBatchJob.status === 'completed'
              "
              :loading="batchJobDetailLoading"
              @click="exportBatchJobReport('xlsx')"
            >
              <template #icon>
                <DownloadOutlined />
              </template>
              导出报告
            </a-button>
            <a-button
              type="text"
              @click="closeResultDrawer"
            >
              <template #icon>
                <CloseOutlined />
              </template>
            </a-button>
          </div>
        </div>

        <div class="flex-1 space-y-4 overflow-auto p-6">
          <template v-if="resultDrawerMode === 'batch' && activeBatchSummary">
            <div
              v-if="activeBatchJob"
              class="rounded-2xl border border-slate-200 bg-white p-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div class="text-xs font-semibold text-slate-500">
                    {{ activeBatchJob.rule_name || activeBatchJob.rule_code }}
                  </div>
                  <div class="mt-1 text-sm text-slate-700">
                    {{ scopeLabelMap[activeBatchJob.scope] }} ·
                    {{ formatDateTime(activeBatchJob.created_at) }}
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <a-tag :class="getBatchJobStatusTagClass(activeBatchJob.status)">
                    {{ getBatchJobStatusText(activeBatchJob.status) }}
                  </a-tag>
                  <span class="text-xs text-slate-400">发起人 {{ activeBatchJob.created_by || '-' }}</span>
                </div>
              </div>
              <div
                v-if="activeBatchJob.error_message"
                class="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700"
              >
                {{ activeBatchJob.error_message }}
              </div>
            </div>
            <div class="grid gap-3 md:grid-cols-4">
              <div class="rounded-2xl border border-slate-200 bg-white p-3">
                <div class="text-[11px] text-slate-400">
                  总病历
                </div>
                <div class="mt-1 text-lg font-bold text-slate-900">
                  {{ activeBatchSummary.total_records }}
                </div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-3">
                <div class="text-[11px] text-slate-400">
                  成功
                </div>
                <div class="mt-1 text-lg font-bold text-slate-900">
                  {{ activeBatchSummary.success_count }}
                </div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-3">
                <div class="text-[11px] text-slate-400">
                  失败
                </div>
                <div class="mt-1 text-lg font-bold text-slate-900">
                  {{ activeBatchSummary.failed_count }}
                </div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-white p-3">
                <div class="text-[11px] text-slate-400">
                  命中问题
                </div>
                <div class="mt-1 text-lg font-bold text-slate-900">
                  {{ activeBatchSummary.issue_records }}
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 class="text-lg font-black text-slate-900">
                命中病历
              </h3>
              <a-empty
                v-if="activeBatchItems.length === 0"
                description="本次批量测试暂无命中病历"
              />
              <div
                v-else
                class="mt-3 space-y-2"
              >
                <div
                  v-for="item in activeBatchItems"
                  :key="item.record_id"
                  class="rounded-2xl border border-slate-200 bg-slate-50 p-3"
                >
                  <div class="flex items-center justify-between gap-2">
                    <strong>{{ item.patient_name || item.record_id }}</strong><a-tag :class="getQcOutcomeTagClass(item.is_compliant)">
                      {{ item.is_compliant ? '合规/不适用' : '命中问题' }}
                    </a-tag>
                  </div>
                  <p class="mt-2 text-sm leading-6 text-slate-500">
                    {{ item.findings || '无附加结论' }}
                  </p>
                  <p class="mt-2 text-xs text-slate-400">
                    {{ item.record_id }} / {{ item.department || '-' }}
                  </p>
                  <div class="mt-3 flex justify-end">
                    <a-button
                      size="small"
                      class="mr-2"
                      @click="openBatchItemEvidence(item)"
                    >
                      <template #icon>
                        <EyeOutlined />
                      </template>
                      查看规则证据
                    </a-button>
                    <a-button
                      size="small"
                      @click="openRecordInWorkstation(item.record_id, activeBatchJob)"
                    >
                      进入流程处理
                    </a-button>
                  </div>
                </div>
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 class="text-lg font-black text-slate-900">
                失败病历
              </h3>
              <a-empty
                v-if="activeBatchFailedRecords.length === 0"
                description="本次批量任务没有失败病历"
              />
              <div
                v-else
                class="mt-3 space-y-2"
              >
                <div
                  v-for="item in activeBatchFailedRecords"
                  :key="`${item.record_id}-${item.error}`"
                  class="rounded-2xl border border-rose-100 bg-rose-50/60 p-3"
                >
                  <div class="font-semibold text-slate-800">
                    {{ item.patient_name || item.record_id }}
                  </div>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ item.record_id }} / {{ item.visit_id || '-' }} / {{ item.department || '-' }}
                  </p>
                  <p class="mt-2 text-sm text-rose-700">
                    {{ item.error }}
                  </p>
                  <div class="mt-3 flex justify-end">
                    <a-button
                      size="small"
                      @click="openRecordInWorkstation(item.record_id, activeBatchJob)"
                    >
                      进入流程处理
                    </a-button>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="resultDrawerMode === 'single' && resultDrawerRecord">
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <div class="flex items-center justify-between gap-2">
                <strong>{{
                  resultDrawerRecord.patient_name || resultDrawerRecord.record_id
                }}</strong><a-tag :class="getQcOutcomeTagClass(resultDrawerRecord.is_compliant)">
                  {{ resultDrawerRecord.is_compliant ? '合规/不适用' : '命中问题' }}
                </a-tag>
              </div>
              <p class="mt-2 text-xs text-slate-400">
                {{ resultDrawerRecord.record_id }} / {{ resultDrawerRecord.visit_id || '-' }} /
                {{ resultDrawerRecord.department || '-' }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 class="text-lg font-black text-slate-900">
                发现问题
              </h3>
              <p class="mt-2 text-sm leading-7 text-slate-500">
                {{ resultDrawerRecord.findings || '无附加结论' }}
              </p>
            </div>
            <div
              v-if="resultDrawerRecord.issues && resultDrawerRecord.issues.length"
              class="rounded-2xl border border-slate-200 bg-white p-4"
            >
              <h3 class="text-lg font-black text-slate-900">
                问题列表
              </h3>
              <div class="mt-2 space-y-2">
                <div
                  v-for="(issue, idx) in getDisplayIssues(resultDrawerRecord)"
                  :key="`single-issue-${idx}-${issue.description}`"
                  class="rounded-lg border border-amber-100 bg-amber-50/50 px-3 py-2 text-sm text-slate-600"
                >
                  <div class="font-semibold text-slate-800">
                    {{ idx + 1 }}. {{ issue.description || '问题描述缺失' }}
                  </div>
                  <div
                    v-if="issue.evidence"
                    class="mt-1 text-xs text-slate-500"
                  >
                    证据：{{ issue.evidence }}
                  </div>
                </div>
                <p
                  v-if="(resultDrawerRecord.issues?.length || 0) > ISSUE_DISPLAY_LIMIT"
                  class="text-xs text-slate-400"
                >
                  仅展示前 {{ ISSUE_DISPLAY_LIMIT }} 条，共
                  {{ resultDrawerRecord.issues?.length }} 条。
                </p>
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 class="text-lg font-black text-slate-900">
                证据
              </h3>
              <p class="mt-2 whitespace-pre-wrap break-words text-sm leading-7 text-slate-500">
                {{ resultDrawerRecord.evidence || '无' }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 class="text-lg font-black text-slate-900">
                建议
              </h3>
              <p class="mt-2 whitespace-pre-wrap break-words text-sm leading-7 text-slate-500">
                {{ resultDrawerRecord.suggestion || '无' }}
              </p>
            </div>
            <div
              v-if="resultDrawerRecord.llm_raw_output"
              class="rounded-2xl border border-slate-200 bg-white p-4"
            >
              <h3 class="text-lg font-black text-slate-900">
                原始输出
              </h3>
              <details class="mt-2">
                <summary class="cursor-pointer text-xs text-slate-500">
                  展开查看模型原始输出
                </summary>
                <pre
                  class="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-600"
                >{{ resultDrawerRecord.llm_raw_output }}</pre>
              </details>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 class="text-lg font-black text-slate-900">
                置信度
              </h3>
              <p class="mt-2 text-sm leading-7 text-slate-500">
                {{ formatConfidence(resultDrawerRecord.confidence) }}
              </p>
            </div>
          </template>

          <a-empty
            v-else
            description="暂无测试结果"
          />
        </div>
      </div>
    </a-drawer>

    <a-drawer
      :open="evidenceDrawerOpen"
      placement="right"
      :width="560"
      @close="closeEvidenceDrawer"
    >
      <template #title>
        规则证据
      </template>
      <template v-if="evidenceDrawerRecord">
        <div class="space-y-4">
          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <div class="flex items-center justify-between gap-2">
              <strong>{{
                evidenceDrawerRecord.patient_name || evidenceDrawerRecord.record_id
              }}</strong>
              <a-tag :class="getQcOutcomeTagClass(evidenceDrawerRecord.is_compliant)">
                {{ evidenceDrawerRecord.is_compliant ? '合规/不适用' : '命中问题' }}
              </a-tag>
            </div>
            <p class="mt-2 text-xs text-slate-400">
              {{ evidenceDrawerRecord.record_id }} / {{ evidenceDrawerRecord.visit_id || '-' }} /
              {{ evidenceDrawerRecord.department || '-' }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 class="text-lg font-black text-slate-900">
              发现问题
            </h3>
            <p class="mt-2 text-sm leading-7 text-slate-500">
              {{ evidenceDrawerRecord.findings || '无附加结论' }}
            </p>
          </div>
          <div
            v-if="evidenceDrawerRecord.issues && evidenceDrawerRecord.issues.length"
            class="rounded-2xl border border-slate-200 bg-white p-4"
          >
            <h3 class="text-lg font-black text-slate-900">
              问题列表
            </h3>
            <div class="mt-2 space-y-2">
              <div
                v-for="(issue, idx) in getDisplayIssues(evidenceDrawerRecord)"
                :key="`batch-issue-${idx}-${issue.description}`"
                class="rounded-lg border border-amber-100 bg-amber-50/50 px-3 py-2 text-sm text-slate-600"
              >
                <div class="font-semibold text-slate-800">
                  {{ idx + 1 }}. {{ issue.description || '问题描述缺失' }}
                </div>
                <div
                  v-if="issue.evidence"
                  class="mt-1 text-xs text-slate-500"
                >
                  证据：{{ issue.evidence }}
                </div>
              </div>
              <p
                v-if="(evidenceDrawerRecord.issues?.length || 0) > ISSUE_DISPLAY_LIMIT"
                class="text-xs text-slate-400"
              >
                仅展示前 {{ ISSUE_DISPLAY_LIMIT }} 条，共
                {{ evidenceDrawerRecord.issues?.length }} 条。
              </p>
            </div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 class="text-lg font-black text-slate-900">
              证据
            </h3>
            <p class="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-500">
              {{ evidenceDrawerRecord.evidence || '无' }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 class="text-lg font-black text-slate-900">
              建议
            </h3>
            <p class="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-500">
              {{ evidenceDrawerRecord.suggestion || '无' }}
            </p>
          </div>
          <div
            v-if="evidenceDrawerRecord.llm_raw_output"
            class="rounded-2xl border border-slate-200 bg-white p-4"
          >
            <h3 class="text-lg font-black text-slate-900">
              原始输出
            </h3>
            <details class="mt-2">
              <summary class="cursor-pointer text-xs text-slate-500">
                展开查看模型原始输出
              </summary>
              <pre
                class="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-600"
              >{{ evidenceDrawerRecord.llm_raw_output }}</pre>
            </details>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 class="text-lg font-black text-slate-900">
              置信度
            </h3>
            <p class="mt-2 text-sm leading-7 text-slate-500">
              {{ formatConfidence(evidenceDrawerRecord.confidence) }}
            </p>
          </div>
          <div class="flex justify-end">
            <a-button
              type="primary"
              @click="openRecordInWorkstation(evidenceDrawerRecord.record_id, activeBatchJob)"
            >
              进入流程处理
            </a-button>
          </div>
        </div>
      </template>
      <a-empty
        v-else
        description="暂无规则证据"
      />
    </a-drawer>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import type { Dayjs } from 'dayjs'
import { useRouter } from 'vue-router'
import { Empty, Modal, message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import {
  CloseOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  EyeOutlined,
  FileSearchOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  RocketOutlined,
  SearchOutlined,
} from '@ant-design/icons-vue'
import {
  createWorkspaceDraft,
  deleteWorkspaceDraft,
  createWorkspaceBatchJob,
  cancelWorkspaceBatchJob,
  exportWorkspaceBatchJob,
  generateWorkspaceDraftPrompt,
  getWorkspaceBatchJob,
  getWorkspaceRecordFilters,
  getWorkspaceRecords,
  listWorkspaceDrafts,
  listWorkspaceBatchJobs,
  publishWorkspaceDraft,
  runWorkspaceBatchTest,
  runWorkspaceSingleTest,
  updateWorkspaceDraft,
} from '@/services/custom-rule-workspace-service'
import { useAuthStore } from '@/stores/auth'
import type {
  CustomRuleBatchJob,
  CustomRuleBatchJobRuleResult,
  CustomRuleBatchJobSummary,
  CustomRuleBatchJobStatus,
  CustomRuleBatchResult,
  CustomRuleDraft,
  CustomRuleDraftPayload,
  CustomRuleEditorDrawerMode,
  CustomRuleSingleTestResult,
  CustomRuleTestResultPanelState,
  CustomRuleWorkspaceRecord,
  WorkspaceScope,
  WorkspaceDraftStatus,
  WorkspaceSeverity,
} from '@/types/custom-rule-workspace'

type DateRangeValue = [Dayjs, Dayjs] | null
type WorkspaceDateField = 'admission' | 'discharge'

interface BatchLaunchFilters {
  scope: WorkspaceScope
  department?: string
  doctor?: string
  date_field: WorkspaceDateField
  dateRange: DateRangeValue
  keyword: string
}

interface RecordTestResultItem {
  draft_id?: string
  rule_code?: string
  rule_name?: string
  record_id: string
  visit_id?: string
  patient_name?: string
  department?: string
  status: string
  is_compliant: boolean
  issues?: Array<{ description: string; evidence?: string }>
  findings: string
  evidence: string
  suggestion: string
  confidence: number
  llm_raw_output?: string
}

const router = useRouter()
const authStore = useAuthStore()

const draftLoading = ref(false)
const creatingDraft = ref(false)
const savingDraft = ref(false)
const generatingPrompt = ref(false)
const publishingDraft = ref(false)
const testingBatch = ref(false)
const testingSingleRecordId = ref('')
const batchJobLoading = ref(false)
const batchJobDetailLoading = ref(false)
const cancellingBatchJobId = ref('')
const batchLaunchModalOpen = ref(false)
const batchLaunchFiltersLoading = ref(false)
const drafts = ref<CustomRuleDraft[]>([])
const selectedDraftId = ref('')
const selectedDraftIds = ref<string[]>([])
const batchResult = ref<CustomRuleBatchResult | null>(null)
const batchJobs = ref<CustomRuleBatchJob[]>([])
const batchJobDetail = ref<CustomRuleBatchJob | null>(null)
const singleResult = ref<CustomRuleSingleTestResult | null>(null)
const recordResults = ref<Record<string, RecordTestResultItem>>({})
const editorDrawerOpen = ref(false)
const editorDrawerMode = ref<CustomRuleEditorDrawerMode>('create')
const resultDrawerOpen = ref(false)
const resultDrawerMode = ref<CustomRuleTestResultPanelState>('empty')
const resultDrawerRecord = ref<RecordTestResultItem | null>(null)
const evidenceDrawerOpen = ref(false)
const evidenceDrawerRecord = ref<RecordTestResultItem | null>(null)
const testSettingsActiveKeys = ref<string[]>([])

const draftQuery = reactive({ keyword: '', status: undefined as WorkspaceDraftStatus | undefined })
const draftPagination = reactive({
  current: 1,
  pageSize: 8,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条`,
})
const batchJobPagination = reactive({
  current: 1,
  pageSize: 5,
  total: 0,
})
const batchJobQuery = reactive({
  keyword: '',
  status: undefined as CustomRuleBatchJobStatus | undefined,
  scope: undefined as WorkspaceScope | undefined,
  execution_mode: undefined as 'single' | 'batch' | undefined,
  dateRange: null as DateRangeValue,
  mineOnly: true,
  onlyCurrentRule: true,
})

const makeDraftDefaults = () => ({
  name: '',
  description: '',
  source_requirement: '',
  prompt_template: '',
  document_type: '出院记录',
  scene: 'final' as 'running' | 'final',
  severity: 'major' as WorkspaceSeverity,
  defect_level: '一般缺陷',
  complexity: '中复杂度',
  generation_mode: 'fallback_template' as 'llm' | 'fallback_template',
  positive_example: '',
  negative_example: '',
  check_logic: {} as Record<string, unknown>,
  prompt_summary: '',
  check_points: [] as string[],
})
const draftForm = reactive(makeDraftDefaults())
const drawerTestInput = reactive({
  mode: 'selected_record' as 'selected_record' | 'manual_text',
  selected_record_id: '',
  manual_patient_name: '',
  manual_text: '',
})

const draftStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已发布', value: 'published' },
]
const documentTypeOptions = [
  { label: '入院记录', value: '入院记录' },
  { label: '病程记录', value: '病程记录' },
  { label: '首次病程记录', value: '首次病程记录' },
  { label: '出院记录', value: '出院记录' },
  { label: '手术记录', value: '手术记录' },
]
const sceneOptions = [
  { label: '运行病历', value: 'running' },
  { label: '终末病历', value: 'final' },
]
const scopeOptions: Array<{ label: string; value: WorkspaceScope }> = [
  { label: '终末病历', value: 'final' },
  { label: '运行病历', value: 'running' },
  { label: '全量病历', value: 'all' },
]
const severityOptions = [
  { label: '严重', value: 'critical' },
  { label: '一般', value: 'major' },
  { label: '提示', value: 'minor' },
]
const defectLevelOptions = [
  { label: '严重缺陷', value: '严重缺陷' },
  { label: '一般缺陷', value: '一般缺陷' },
  { label: '提示性缺陷', value: '提示性缺陷' },
]
const complexityOptions = [
  { label: '低复杂度', value: '低复杂度' },
  { label: '中复杂度', value: '中复杂度' },
  { label: '高复杂度', value: '高复杂度' },
]
const dateFieldOptions = [
  { label: '按入院日期', value: 'admission' },
  { label: '按出院日期', value: 'discharge' },
]
const batchJobStatusOptions = [
  { label: '排队中', value: 'queued' },
  { label: '执行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已失败', value: 'failed' },
  { label: '已停止', value: 'canceled' },
]
const batchJobScopeOptions = [
  { label: '终末病历', value: 'final' },
  { label: '运行病历', value: 'running' },
  { label: '全量病历', value: 'all' },
]
const batchJobExecutionModeOptions = [
  { label: '单条', value: 'single' },
  { label: '批量', value: 'batch' },
]

const selectedDraft = computed(
  () => drafts.value.find((item) => item.id === selectedDraftId.value) || null,
)
const selectedRunDrafts = computed(() => {
  const selectedSet = new Set(selectedDraftIds.value)
  return drafts.value.filter((item) => selectedSet.has(item.id))
})
const selectedRunDraftIds = computed(() => selectedRunDrafts.value.map((item) => item.id))
const selectedRunScene = computed(() => {
  const sceneSet = Array.from(new Set(selectedRunDrafts.value.map((item) => item.scene)))
  return sceneSet.length === 1 ? sceneSet[0] : ''
})
const scopeLabelMap: Record<WorkspaceScope, string> = {
  final: '终末病历',
  running: '运行病历',
  all: '全量病历',
}
const selectedRunSceneLabel = computed(() =>
  selectedRunScene.value === 'running' || selectedRunScene.value === 'final'
    ? scopeLabelMap[selectedRunScene.value]
    : '',
)
const currentScopeLabel = computed(() => scopeLabelMap[recordFilters.scope] || '终末病历')
const recentBatchJobCount = computed(() => batchJobPagination.total)
const activeBatchJob = computed(() => batchJobDetail.value)
const activeBatchSummary = computed(
  () => activeBatchJob.value?.summary || batchResult.value?.summary || null,
)
const activeBatchItems = computed(
  () => activeBatchJob.value?.items || batchResult.value?.items || [],
)
const activeBatchFailedRecords = computed(
  () => activeBatchJob.value?.failed_records || batchResult.value?.failed_records || [],
)
const activeBatchRuleResults = computed(
  () => activeBatchJob.value?.rule_results || batchResult.value?.rule_results || [],
)
const hasPromptTemplate = computed(
  () => !!String(selectedDraft.value?.prompt_template || '').trim(),
)
const hasSelectedRunDrafts = computed(() => selectedRunDrafts.value.length > 0)
const allSelectedRunDraftPromptReady = computed(
  () =>
    selectedRunDrafts.value.length > 0 &&
    selectedRunDrafts.value.every((item) => !!String(item.prompt_template || '').trim()),
)
const canPublishSelectedDraft = computed(
  () => !!selectedDraft.value && canPublishRecord(selectedDraft.value),
)
const canPublishRules = computed(
  () => authStore.hasRole('admin') || authStore.hasRole('qc_manager'),
)
const canViewProjectBatchJobs = computed(
  () => authStore.hasRole('admin') || authStore.hasRole('qc_manager'),
)
const publishActionLabel = computed(() => (canPublishRules.value ? '发布规则' : '提交发布申请'))
const drawerPrimaryLoading = computed(() =>
  editorDrawerMode.value === 'create' ? creatingDraft.value : savingDraft.value,
)
const drawerGenerateLoading = computed(() => drawerPrimaryLoading.value || generatingPrompt.value)
const drawerTestActionLoading = computed(
  () => drawerPrimaryLoading.value || testingBatch.value || !!testingSingleRecordId.value,
)
const drawerMetaReady = computed(() => {
  const name = draftForm.name.trim()
  const requirement = draftForm.source_requirement.trim() || draftForm.description.trim()
  return !!name && !!requirement
})
const drawerPromptReady = computed(() => !!draftForm.prompt_template.trim())
const drawerTestReady = computed(() => drawerMetaReady.value && drawerPromptReady.value)
const drawerHasSelectedRecords = computed(() => selectedRecordKeys.value.length > 0)
const drawerTestRecordOptions = computed(() =>
  records.value.map((item) => ({
    value: item.record_id,
    label: `${item.record_id} · ${item.patient_name || '-'} · ${item.department || '-'}`,
  })),
)
const drawerHasInlineTarget = computed(() => {
  if (drawerTestInput.mode === 'manual_text') return !!drawerTestInput.manual_text.trim()
  return !!drawerTestInput.selected_record_id.trim()
})
const drawerCanRunTest = computed(
  () => drawerTestReady.value && (drawerHasInlineTarget.value || drawerHasSelectedRecords.value),
)
const drawerTestTargetHint = computed(() => {
  if (drawerTestInput.mode === 'manual_text' && drawerTestInput.manual_text.trim()) {
    return `抽屉文本 ${drawerTestInput.manual_text.trim().length} 字`
  }
  if (drawerTestInput.mode === 'selected_record' && drawerTestInput.selected_record_id.trim()) {
    return `抽屉病历 ${drawerTestInput.selected_record_id.trim()}`
  }
  return `已选病历 ${selectedRecordKeys.value.length} 条`
})
const editorDrawerTitle = computed(() =>
  editorDrawerMode.value === 'create'
    ? '自定义质控规则'
    : editorDrawerMode.value === 'copy'
      ? '复制并编辑规则'
      : '编辑自定义规则',
)

const draftColumns: TableColumnsType<CustomRuleDraft> = [
  { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 120 },
  { title: '规则名称', dataIndex: 'name', key: 'name' },
  { title: '适用文书', dataIndex: 'document_type', key: 'document_type', width: 110 },
  { title: '场景', dataIndex: 'scene', key: 'scene', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '最近测试摘要', key: 'last_test_summary', width: 120 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 150 },
  { title: '操作', key: 'actions', width: 180, fixed: 'right' },
]

const recordFilters = reactive({
  scope: 'final' as WorkspaceScope,
  department: undefined as string | undefined,
  doctor: undefined as string | undefined,
  date_field: 'discharge' as WorkspaceDateField,
  dateRange: null as DateRangeValue,
  keyword: '',
})
const batchLaunchFilters = reactive<BatchLaunchFilters>({
  scope: 'final',
  department: undefined,
  doctor: undefined,
  date_field: 'discharge',
  dateRange: null,
  keyword: '',
})
const departmentOptions = ref<Array<{ label: string; value: string }>>([])
const doctorOptions = ref<Array<{ label: string; value: string }>>([])
const batchLaunchDepartmentOptions = ref<Array<{ label: string; value: string }>>([])
const batchLaunchDoctorOptions = ref<Array<{ label: string; value: string }>>([])
const recordLoading = ref(false)
const records = ref<CustomRuleWorkspaceRecord[]>([])
const selectedRecordKeys = ref<string[]>([])
const recordPagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条病历`,
})
const recordColumns: TableColumnsType<CustomRuleWorkspaceRecord> = [
  { title: '病历号 / 就诊号', key: 'record_info', width: 160 },
  { title: '患者信息', dataIndex: 'patient_name', key: 'patient_name', width: 170 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 130 },
  { title: '医生', dataIndex: 'doctor', key: 'doctor', width: 130 },
  { title: '出院日期', dataIndex: 'discharge_date', key: 'discharge_date', width: 120 },
  { title: '最近测试状态', key: 'latest_status', width: 120 },
  { title: '最近命中结果摘要', key: 'latest_findings' },
  { title: '操作', key: 'actions', width: 150, fixed: 'right' as const },
]
function getBatchJobStatusText(status?: string) {
  switch (status) {
    case 'queued':
      return '排队中'
    case 'running':
      return '执行中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '已失败'
    case 'canceled':
      return '已停止'
    default:
      return '未知'
  }
}
function getBatchJobStatusTagClass(status?: string) {
  switch (status) {
    case 'queued':
      return 'cw-qc-tag cw-qc-tag--queued'
    case 'running':
      return 'cw-qc-tag cw-qc-tag--running'
    case 'completed':
      return 'cw-qc-tag cw-qc-tag--completed'
    case 'failed':
      return 'cw-qc-tag cw-qc-tag--failed'
    case 'canceled':
      return 'cw-qc-tag cw-qc-tag--canceled'
    default:
      return 'cw-qc-tag cw-qc-tag--queued'
  }
}
function getQcOutcomeTagClass(isCompliant: boolean) {
  return isCompliant ? 'cw-qc-tag cw-qc-tag--compliant' : 'cw-qc-tag cw-qc-tag--issue'
}
function resolveLaunchContext(params: {
  ruleName?: string
  scene?: 'running' | 'final' | string
  scope?: WorkspaceScope | string
  documentType?: string
}) {
  const text = [String(params.ruleName || ''), String(params.documentType || '')]
    .join(' ')
    .toLowerCase()
  if (/(医保|结算|清单|费用|控费)/.test(text)) {
    return {
      action: 'qc_settlement',
      from_stage: 'settlement_qc',
      stage: 'settlement_qc',
      detail_tab: 'settlement',
      assist_tab: 'cost',
    }
  }
  if (/(编码|icd|drg|dip)/.test(text)) {
    return {
      action: 'qc_coding',
      from_stage: 'coding_qc',
      stage: 'coding_qc',
      detail_tab: 'frontpage',
      assist_tab: 'coding',
    }
  }
  if (/(首页|病案首页|表单)/.test(text)) {
    return {
      action: 'qc_frontpage',
      from_stage: 'frontpage_qc',
      stage: 'frontpage_qc',
      detail_tab: 'frontpage',
      assist_tab: 'form',
    }
  }
  if (params.scene === 'running') {
    return {
      action: 'qc_coding',
      from_stage: 'coding_qc',
      stage: 'coding_qc',
      detail_tab: 'frontpage',
      assist_tab: 'coding',
    }
  }
  if (params.scope === 'all' || params.scope === 'final') {
    return {
      action: 'qc_frontpage',
      from_stage: 'frontpage_qc',
      stage: 'frontpage_qc',
      detail_tab: 'frontpage',
      assist_tab: 'form',
    }
  }
  return {
    action: 'qc_coding',
    from_stage: 'coding_qc',
    stage: 'coding_qc',
    detail_tab: 'frontpage',
    assist_tab: 'coding',
  }
}
function openRecordInWorkstation(recordId?: string, job?: CustomRuleBatchJob | null) {
  const targetRecordId = String(recordId || '').trim()
  if (!targetRecordId) {
    message.info('缺少病历标识，暂时无法打开')
    return
  }
  const draftContext = job?.draft_id
    ? drafts.value.find((item) => item.id === job.draft_id) || selectedDraft.value
    : selectedDraft.value
  const launchContext = resolveLaunchContext({
    ruleName: job?.rule_name || draftContext?.name,
    scene: job?.scene || draftContext?.scene,
    scope: job?.scope || recordFilters.scope,
    documentType: draftContext?.document_type,
  })
  router.push({
    path: '/workstation-v4/worklist',
    query: {
      source: 'dashboard',
      record_id: targetRecordId,
      action: launchContext.action,
      from_stage: launchContext.from_stage,
      stage: launchContext.stage,
      detail_tab: launchContext.detail_tab,
      assist_tab: launchContext.assist_tab,
      task_id: job?.id || undefined,
      launch_from: 'custom_workspace_batch_job',
    },
  })
}
const recordRowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRecordKeys.value,
  onChange: (keys: Array<string | number>) => {
    selectedRecordKeys.value = keys.map((item) => String(item))
  },
}))
const draftRowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedDraftIds.value,
  onChange: (keys: Array<string | number>) => {
    selectedDraftIds.value = Array.from(new Set(keys.map((item) => String(item))))
  },
}))
const advancedParams = reactive({ temperature: 0.2, top_p: 0.9, max_tokens: 4096 })
let batchJobPollTimer: number | null = null

function formatDateTime(value?: string) {
  return value ? String(value).replace('T', ' ').slice(0, 16) : '-'
}
function formatConfidence(value?: number) {
  return `${Math.round(Number(value || 0) * 100)}%`
}
function getSummarySuccessCount(draft: CustomRuleDraft) {
  return Number((draft.last_test_summary || {}).success_count || 0)
}
function getSummaryFailedCount(draft: CustomRuleDraft) {
  return Number((draft.last_test_summary || {}).failed_count || 0)
}
function getSummaryIssueCount(draft: CustomRuleDraft) {
  return Number((draft.last_test_summary || {}).issue_records || 0)
}
function canPublishRecord(draft: CustomRuleDraft) {
  return draft.status === 'draft' && getSummarySuccessCount(draft) > 0
}
function resetDraftForm() {
  Object.assign(draftForm, makeDraftDefaults())
}
function getExamplesFromDraft(draft: CustomRuleDraft) {
  const examples = Array.isArray(draft.examples) ? draft.examples : []
  return {
    positive: examples.find((item) => String(item.title || '').includes('合规'))?.content || '',
    negative: examples.find((item) => String(item.title || '').includes('不合规'))?.content || '',
  }
}
function hydrateDraftForm(draft: CustomRuleDraft) {
  const examples = getExamplesFromDraft(draft)
  const logic = (draft.check_logic || {}) as Record<string, unknown>
  const requirement = (draft.source_requirement || draft.description || '').trim()
  draftForm.name = draft.name || ''
  draftForm.source_requirement = requirement
  // Backward-compatible mirror field; UI now edits source_requirement only.
  draftForm.description = requirement
  draftForm.prompt_template = draft.prompt_template || ''
  draftForm.document_type = draft.document_type || '出院记录'
  draftForm.scene = draft.scene || 'final'
  draftForm.severity = draft.severity || 'major'
  draftForm.defect_level = draft.defect_level || '一般缺陷'
  draftForm.complexity = draft.complexity || '中复杂度'
  draftForm.generation_mode = draft.generation_mode || 'fallback_template'
  draftForm.positive_example = examples.positive
  draftForm.negative_example = examples.negative
  draftForm.check_logic = logic
  draftForm.prompt_summary = String(logic.last_prompt_summary || '')
  draftForm.check_points = Array.isArray(logic.generated_check_points)
    ? (logic.generated_check_points as string[])
    : []
}
function buildExamples() {
  const examples: Array<{ title: string; content: string }> = []
  if (draftForm.positive_example.trim())
    examples.push({ title: '合规示例', content: draftForm.positive_example.trim() })
  if (draftForm.negative_example.trim())
    examples.push({ title: '不合规模例', content: draftForm.negative_example.trim() })
  return examples
}
function validateDraftFormBase() {
  const name = draftForm.name.trim()
  const requirement = draftForm.source_requirement.trim()
  if (!name) return (message.warning('请先填写规则名称'), false)
  if (!requirement) return (message.warning('请先填写需求描述'), false)
  return true
}
function buildDraftPayload(): CustomRuleDraftPayload {
  const requirement = draftForm.source_requirement.trim()
  return {
    name: draftForm.name.trim(),
    description: requirement,
    source_requirement: requirement,
    prompt_template: draftForm.prompt_template.trim() || undefined,
    document_type: draftForm.document_type,
    severity: draftForm.severity,
    defect_level: draftForm.defect_level,
    complexity: draftForm.complexity,
    scene: draftForm.scene,
    generation_mode: draftForm.generation_mode,
    applicable_documents: [draftForm.document_type],
    examples: buildExamples(),
    check_logic: {
      ...(draftForm.check_logic || {}),
      source: 'custom_rule_workspace',
      scene: draftForm.scene,
      applicable_documents: [draftForm.document_type],
      last_prompt_summary: draftForm.prompt_summary,
      generated_check_points: draftForm.check_points,
    },
  }
}
async function loadDrafts() {
  draftLoading.value = true
  try {
    const response = await listWorkspaceDrafts({
      page: draftPagination.current,
      page_size: draftPagination.pageSize,
      status: draftQuery.status,
      q: draftQuery.keyword || undefined,
    })
    if (!response.success || !response.data) throw new Error(response.message || '获取规则列表失败')
    drafts.value = response.data.items
    draftPagination.total = response.data.total
    if (!selectedDraftId.value && drafts.value[0]) selectedDraftId.value = drafts.value[0].id
    if (!selectedDraftIds.value.length && selectedDraftId.value) {
      selectedDraftIds.value = [selectedDraftId.value]
    }
    selectedDraftIds.value = selectedDraftIds.value.filter((id) =>
      drafts.value.some((item) => item.id === id),
    )
    const current = drafts.value.find((item) => item.id === selectedDraftId.value)
    if (current && editorDrawerOpen.value && editorDrawerMode.value !== 'create')
      hydrateDraftForm(current)
  } catch (error: any) {
    message.error(error?.message || '获取规则列表失败')
  } finally {
    draftLoading.value = false
  }
}
function searchDrafts() {
  draftPagination.current = 1
  loadDrafts()
}
function handleDraftTableChange(pagination: { current?: number; pageSize?: number }) {
  draftPagination.current = pagination.current || 1
  draftPagination.pageSize = pagination.pageSize || 8
  loadDrafts()
}
function draftCustomRow(record: CustomRuleDraft) {
  return {
    onClick: () => {
      selectedDraftId.value = record.id
      if (!selectedDraftIds.value.includes(record.id)) {
        selectedDraftIds.value = Array.from(new Set([record.id, ...selectedDraftIds.value]))
      }
    },
  }
}
function draftRowClassName(record: CustomRuleDraft) {
  return record.id === selectedDraftId.value ? 'draft-row-active' : ''
}
function openCreateDrawer() {
  editorDrawerMode.value = 'create'
  resetDraftForm()
  editorDrawerOpen.value = true
}
function openEditDrawer(record: CustomRuleDraft) {
  selectedDraftId.value = record.id
  if (!selectedDraftIds.value.includes(record.id)) {
    selectedDraftIds.value = Array.from(new Set([record.id, ...selectedDraftIds.value]))
  }
  editorDrawerMode.value = 'edit'
  hydrateDraftForm(record)
  editorDrawerOpen.value = true
}
function closeEditorDrawer() {
  editorDrawerOpen.value = false
  if (selectedDraft.value) hydrateDraftForm(selectedDraft.value)
  else resetDraftForm()
}
async function persistDraftFromDrawer(
  options: { silentSuccess?: boolean } = {},
): Promise<CustomRuleDraft | null> {
  if (!validateDraftFormBase()) return null
  if (editorDrawerMode.value === 'create') {
    creatingDraft.value = true
    try {
      const response = await createWorkspaceDraft(buildDraftPayload())
      if (!response.success || !response.data) throw new Error(response.message || '创建草稿失败')
      selectedDraftId.value = response.data.id
      selectedDraftIds.value = Array.from(new Set([response.data.id, ...selectedDraftIds.value]))
      editorDrawerMode.value = 'edit'
      await loadDrafts()
      hydrateDraftForm(response.data)
      if (!options.silentSuccess) message.success(`草稿 ${response.data.rule_code} 已创建`)
      return response.data
    } catch (error: any) {
      message.error(error?.message || '创建草稿失败')
      return null
    } finally {
      creatingDraft.value = false
    }
  }
  if (!selectedDraft.value) return (message.warning('请先选择一条规则'), null)
  savingDraft.value = true
  try {
    const response = await updateWorkspaceDraft(selectedDraft.value.id, buildDraftPayload())
    if (!response.success || !response.data) throw new Error(response.message || '保存草稿失败')
    drafts.value = drafts.value.map((item) =>
      item.id === response.data!.id ? response.data! : item,
    )
    selectedDraftId.value = response.data.id
    if (!selectedDraftIds.value.includes(response.data.id)) {
      selectedDraftIds.value = Array.from(new Set([response.data.id, ...selectedDraftIds.value]))
    }
    hydrateDraftForm(response.data)
    if (!options.silentSuccess) message.success('草稿已保存')
    return response.data
  } catch (error: any) {
    message.error(error?.message || '保存草稿失败')
    return null
  } finally {
    savingDraft.value = false
  }
}
async function saveDraftFromDrawer() {
  await persistDraftFromDrawer()
}
async function generatePromptForDrawer(options: { successMessage?: string } = {}) {
  const draft = await persistDraftFromDrawer({ silentSuccess: true })
  if (!draft) return
  generatingPrompt.value = true
  try {
    const response = await generateWorkspaceDraftPrompt(draft.id)
    if (!response.success || !response.data) throw new Error(response.message || '生成 Prompt 失败')
    const { draft: nextDraft, prompt_result: promptResult } = response.data
    drafts.value = drafts.value.map((item) => (item.id === nextDraft.id ? nextDraft : item))
    selectedDraftId.value = nextDraft.id
    hydrateDraftForm(nextDraft)
    draftForm.prompt_summary = promptResult.summary || ''
    draftForm.check_points = promptResult.check_points || []
    if (options.successMessage) {
      message.success(options.successMessage)
    } else {
      message.success(
        promptResult.generation_mode === 'llm' ? 'Prompt 生成成功' : '已回退为模板 Prompt',
      )
    }
  } catch (error: any) {
    message.error(error?.message || '生成 Prompt 失败')
  } finally {
    generatingPrompt.value = false
  }
}
async function saveAndGeneratePromptFromDrawer() {
  await generatePromptForDrawer({ successMessage: '草稿已保存并生成 Prompt，可继续手工调整后测试' })
}
function resolveDrawerInlineTestRecord(): {
  record_id: string
  visit_id?: string
  patient_name?: string
  department?: string
  doctor?: string
  medical_text?: string
} | null {
  if (drawerTestInput.mode === 'manual_text') {
    const text = drawerTestInput.manual_text.trim()
    if (!text) return null
    const marker = `${Date.now()}`.slice(-6)
    return {
      record_id: `MANUAL-${marker}`,
      visit_id: `MANUAL-${marker}`,
      patient_name: drawerTestInput.manual_patient_name.trim() || '手工文本',
      medical_text: text,
    }
  }
  const recordId = drawerTestInput.selected_record_id.trim()
  if (!recordId) return null
  const target = records.value.find((item) => item.record_id === recordId)
  if (!target) return null
  return {
    record_id: target.record_id,
    visit_id: target.visit_id,
    patient_name: target.patient_name,
    department: target.department,
    doctor: target.doctor,
  }
}
async function runSingleTestByPayload(
  record: {
    record_id: string
    visit_id?: string
    patient_name?: string
    department?: string
    doctor?: string
    medical_text?: string
  },
  options: { successMessage?: string } = {},
) {
  const runDrafts = resolveSelectedRunDraftsForExecution()
  if (!runDrafts) return
  testingSingleRecordId.value = record.record_id
  try {
    const draftIds = runDrafts.map((item) => item.id)
    const response = await runWorkspaceSingleTest({
      draft_id: draftIds[0],
      draft_ids: draftIds,
      records: [record],
      temperature: advancedParams.temperature,
      top_p: advancedParams.top_p,
      max_tokens: advancedParams.max_tokens,
    })
    if (!response.success || !response.data) throw new Error(response.message || '单病历测试失败')
    singleResult.value = response.data
    batchResult.value = null
    syncDraftSummariesFromRuleResults(response.data.rule_results || [])
    if (!response.data.rule_results?.length) {
      syncDraftSummary(response.data.summary || {})
    }
    const rawResults =
      (Array.isArray(response.data.results) && response.data.results.length
        ? response.data.results
        : response.data.result
          ? [response.data.result]
          : []) || []
    const normalizedResults = rawResults.map((item) =>
      normalizeRecordResult(item as RecordTestResultItem),
    )
    const preferred =
      normalizedResults.find((item) => !item.is_compliant) || normalizedResults[0] || null
    if (preferred) {
      recordResults.value = { ...recordResults.value, [preferred.record_id]: preferred }
      resultDrawerRecord.value = preferred
    }
    resultDrawerMode.value = 'single'
    message.success(options.successMessage || '单病历测试完成')
  } catch (error: any) {
    message.error(error?.message || '单病历测试失败')
  } finally {
    testingSingleRecordId.value = ''
  }
}
async function saveAndRunTestFromDrawer() {
  const saved = await persistDraftFromDrawer({ silentSuccess: true })
  if (!saved) return
  if (!drawerPromptReady.value) return message.warning('请先生成或填写 Prompt 再测试')
  if (!drawerCanRunTest.value)
    return message.warning('请在抽屉选择测试病历或粘贴病历文本，或在列表中勾选病历')
  editorDrawerOpen.value = false
  await nextTick()
  const inlineRecord = resolveDrawerInlineTestRecord()
  if (inlineRecord) {
    await runSingleTestByPayload(inlineRecord, { successMessage: '规则测试完成' })
    return
  }
  await runBatchTest()
}
async function copyDraft(record: CustomRuleDraft) {
  try {
    const requirement = (record.source_requirement || record.description || '').trim()
    const response = await createWorkspaceDraft({
      name: `${record.name}-副本`,
      description: requirement,
      source_requirement: requirement,
      prompt_template: record.prompt_template,
      document_type: record.document_type,
      severity: record.severity,
      defect_level: record.defect_level,
      complexity: record.complexity,
      scene: record.scene,
      generation_mode: record.generation_mode,
      applicable_documents: record.applicable_documents,
      examples: record.examples,
      check_logic: record.check_logic,
    })
    if (!response.success || !response.data) throw new Error(response.message || '复制草稿失败')
    await loadDrafts()
    selectedDraftId.value = response.data.id
    selectedDraftIds.value = Array.from(new Set([response.data.id, ...selectedDraftIds.value]))
    editorDrawerMode.value = 'copy'
    hydrateDraftForm(response.data)
    editorDrawerOpen.value = true
    message.success('草稿已复制')
  } catch (error: any) {
    message.error(error?.message || '复制草稿失败')
  }
}
async function deleteDraft(record: CustomRuleDraft) {
  try {
    const response = await deleteWorkspaceDraft(record.id)
    if (!response.success) throw new Error(response.message || '删除草稿失败')
    selectedDraftIds.value = selectedDraftIds.value.filter((id) => id !== record.id)
    if (selectedDraftId.value === record.id) selectedDraftId.value = ''
    await loadDrafts()
    if (!selectedDraftId.value && drafts.value[0]) selectedDraftId.value = drafts.value[0].id
    message.success('草稿已删除')
  } catch (error: any) {
    message.error(error?.message || '删除草稿失败')
  }
}
async function publishDraftById(draftId: string) {
  publishingDraft.value = true
  try {
    const response = await publishWorkspaceDraft(draftId)
    if (!response.success || !response.data) throw new Error(response.message || '发布失败')
    await loadDrafts()
    message.success(`发布成功：${response.data.rule_code}`)
  } catch (error: any) {
    message.error(error?.message || '发布失败')
  } finally {
    publishingDraft.value = false
  }
}
async function publishSelectedDraft() {
  if (!selectedDraft.value) return message.warning('请先选择规则')
  if (!canPublishRules.value)
    return message.warning('当前账号无正式发布权限，请联系项目管理员审核发布')
  if (!canPublishSelectedDraft.value) return message.warning('请先完成至少一次成功测试')
  if (editorDrawerOpen.value) {
    const saved = await persistDraftFromDrawer({ silentSuccess: true })
    if (!saved) return
  }
  await publishDraftById(selectedDraft.value.id)
}

function parseLooseJsonObject(text: string): Record<string, unknown> | null {
  const raw = String(text || '').trim()
  if (!raw) return null

  const candidates: string[] = []
  candidates.push(raw)

  const fencedMatches = raw.matchAll(/```(?:json)?\s*([\s\S]*?)\s*```/gi)
  for (const match of fencedMatches) {
    const body = String(match?.[1] || '').trim()
    if (body) candidates.push(body)
  }

  const firstBrace = raw.indexOf('{')
  const lastBrace = raw.lastIndexOf('}')
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    candidates.push(raw.slice(firstBrace, lastBrace + 1))
  }

  const uniqueCandidates = Array.from(
    new Set(
      candidates
        .map((item) =>
          item
            .replace(/^```(?:json)?/i, '')
            .replace(/```$/i, '')
            .trim(),
        )
        .filter(Boolean),
    ),
  )

  for (const candidate of uniqueCandidates) {
    try {
      const parsed = JSON.parse(candidate)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      // ignore
    }
  }

  // 容错兜底：即使不是严格 JSON，也尽量抽取 status/reasons/suggestions
  const statusMatch = raw.match(/["'`]?status["'`]?\s*[:：]\s*["'`]([^"'`]+)["'`]/i)
  const reasonsMatch = raw.match(/["'`]?reasons?["'`]?\s*[:：]\s*\[([\s\S]*?)\]/i)
  const suggestionsMatch = raw.match(/["'`]?suggestions?["'`]?\s*[:：]\s*\[([\s\S]*?)\]/i)
  const extractQuotedItems = (block: string): string[] => {
    if (!block) return []
    const values: string[] = []
    for (const match of block.matchAll(/["'`]([^"'`]{2,})["'`]/g)) {
      const item = String(match[1] || '').trim()
      if (item) values.push(item)
    }
    return values
  }
  const reasons = extractQuotedItems(String(reasonsMatch?.[1] || ''))
  const suggestions = extractQuotedItems(String(suggestionsMatch?.[1] || ''))
  if (statusMatch?.[1] || reasons.length || suggestions.length) {
    return {
      status: String(statusMatch?.[1] || '').trim(),
      reasons,
      suggestions,
    }
  }
  return null
}

function deriveComplianceFromValue(value: unknown): boolean | null {
  if (typeof value === 'boolean') return value
  const text = String(value || '')
    .trim()
    .toLowerCase()
  if (!text) return null
  if (['true', '1', 'yes'].includes(text)) return true
  if (['false', '0', 'no'].includes(text)) return false
  if (
    ['non_compliant', '不合规', '不符合', '不通过', '命中问题', '违规'].some((hint) =>
      text.includes(hint),
    )
  ) {
    return false
  }
  if (
    ['compliant', '合规', '通过', 'not_applicable', '不适用', '未见明显问题'].some((hint) =>
      text.includes(hint),
    )
  ) {
    return true
  }
  return null
}

function looksJsonLike(text: string): boolean {
  const normalized = String(text || '').trim()
  if (!normalized) return false
  return (
    normalized.startsWith('{') ||
    normalized.startsWith('```') ||
    normalized.startsWith('json ') ||
    normalized.includes('"status"') ||
    normalized.includes('"reasons"')
  )
}

function normalizeRecordResult(result: {
  record_id: string
  visit_id?: string
  patient_name?: string
  department?: string
  status: string
  is_compliant: boolean
  issues?: Array<{ description: string; evidence?: string }>
  findings: string
  evidence: string
  suggestion: string
  confidence: number
  llm_raw_output?: string
}): RecordTestResultItem {
  const rawOutput = String(result.llm_raw_output || '').trim()
  const normalizedIssues = Array.isArray(result.issues)
    ? result.issues
        .map((item) => ({
          description: String(item?.description || '').trim(),
          evidence: String(item?.evidence || '').trim(),
        }))
        .filter((item) => !!item.description || !!item.evidence)
    : []

  const structuredPayload =
    parseLooseJsonObject(rawOutput) ||
    parseLooseJsonObject(String(result.evidence || '')) ||
    parseLooseJsonObject(String(result.findings || ''))

  const reasonsFromPayload = Array.isArray(structuredPayload?.reasons)
    ? structuredPayload?.reasons
        .map((item) => String(item || '').trim())
        .filter((item) => !!item) || []
    : []
  const payloadIssues =
    reasonsFromPayload.length > 0
      ? reasonsFromPayload.map((description) => ({ description, evidence: '' }))
      : []
  const mergedIssues = Array.from(
    new Map(
      [...normalizedIssues, ...payloadIssues]
        .filter((item) => !!item.description || !!item.evidence)
        .map((item) => [`${item.description}__${item.evidence || ''}`, item]),
    ).values(),
  )

  const findings = String(result.findings || '').trim()
  const evidence = String(result.evidence || '').trim()
  const suggestion = String(result.suggestion || '').trim()
  const complianceFromPayload = deriveComplianceFromValue(
    structuredPayload?.is_compliant ?? structuredPayload?.status,
  )
  const complianceFromStatus = deriveComplianceFromValue(result.status)

  const findingsFromPayload =
    String(
      structuredPayload?.findings ||
        structuredPayload?.summary ||
        structuredPayload?.conclusion ||
        structuredPayload?.judgement ||
        structuredPayload?.status ||
        '',
    ).trim() || (reasonsFromPayload.length > 0 ? reasonsFromPayload.slice(0, 3).join('；') : '')
  const evidenceFromPayload = String(
    structuredPayload?.evidence || structuredPayload?.evidence_text || '',
  ).trim()
  const suggestionsFromPayload = Array.isArray(structuredPayload?.suggestions)
    ? structuredPayload.suggestions
        .map((item) => String(item || '').trim())
        .filter((item) => !!item)
    : []
  const suggestionFromPayload =
    String(
      structuredPayload?.suggestion ||
        structuredPayload?.recommendation ||
        structuredPayload?.advice ||
        '',
    ).trim() ||
    (suggestionsFromPayload.length > 0
      ? suggestionsFromPayload.map((item, index) => `(${index + 1}) ${item}`).join('\n')
      : '')
  const confidenceFromPayload = Number(structuredPayload?.confidence)
  const normalizedConfidence = Number.isFinite(confidenceFromPayload)
    ? confidenceFromPayload
    : Number(result.confidence || 0.7)
  const inferredNonCompliantByPayload =
    reasonsFromPayload.length > 0 &&
    /(不合规|不通过|命中问题|违规|需整改|non_compliant)/i.test(
      `${String(structuredPayload?.status || '')} ${findingsFromPayload}`,
    )
  const finalIsCompliant =
    complianceFromPayload ??
    complianceFromStatus ??
    (inferredNonCompliantByPayload ? false : Boolean(result.is_compliant))

  const usePayloadAsPrimary =
    !!structuredPayload &&
    (!!reasonsFromPayload.length || !!findingsFromPayload || !!suggestionFromPayload)

  const fallbackFindings =
    (!usePayloadAsPrimary ? findings : findingsFromPayload || findings) ||
    (mergedIssues.length > 0
      ? `命中${mergedIssues.length}个问题：${mergedIssues
          .map((item) => item.description || '问题描述缺失')
          .slice(0, 3)
          .join('；')}`
      : finalIsCompliant
        ? '未发现质控问题'
        : '命中问题，但模型未返回详细结论')

  const fallbackEvidence =
    (!looksJsonLike(evidence) ? evidence : '') ||
    evidenceFromPayload ||
    mergedIssues.map((item) => item.evidence || '').find((item) => !!item) ||
    (!finalIsCompliant ? '未返回可引用证据' : '')

  const fallbackSuggestion =
    (!looksJsonLike(suggestion) ? suggestion : '') ||
    suggestionFromPayload ||
    (finalIsCompliant ? '' : '未返回整改建议，请在 Prompt 中强化 suggestion 输出要求后重试')

  const finalStatus = finalIsCompliant
    ? result.status === 'not_applicable'
      ? 'not_applicable'
      : 'compliant'
    : 'non_compliant'

  return {
    ...result,
    status: finalStatus,
    is_compliant: finalIsCompliant,
    issues: mergedIssues,
    findings: fallbackFindings,
    evidence: fallbackEvidence,
    suggestion: fallbackSuggestion,
    confidence: normalizedConfidence,
    llm_raw_output: rawOutput,
  }
}

const ISSUE_DISPLAY_LIMIT = 6

function getDisplayIssues(record: RecordTestResultItem | null) {
  if (!record?.issues?.length) return []
  return record.issues.slice(0, ISSUE_DISPLAY_LIMIT)
}
function syncDraftSummary(summary: Record<string, unknown>) {
  if (!selectedDraft.value) return
  drafts.value = drafts.value.map((item) =>
    item.id === selectedDraft.value?.id ? { ...item, last_test_summary: summary } : item,
  )
}
function toDraftSummaryRecord(
  summary: CustomRuleBatchJobSummary | Record<string, unknown> | null | undefined,
): Record<string, unknown> | null {
  if (!summary || typeof summary !== 'object') return null
  return summary as Record<string, unknown>
}
function syncDraftSummariesFromRuleResults(ruleResults: CustomRuleBatchJobRuleResult[] = []) {
  if (!Array.isArray(ruleResults) || ruleResults.length === 0) return
  const summaryByDraft = new Map<string, Record<string, unknown>>()
  ruleResults.forEach((item) => {
    const draftId = String(item?.draft_id || '').trim()
    const summary = toDraftSummaryRecord(item?.summary)
    if (!draftId || !summary) return
    summaryByDraft.set(draftId, summary)
  })
  if (!summaryByDraft.size) return
  drafts.value = drafts.value.map((item) =>
    summaryByDraft.has(item.id)
      ? { ...item, last_test_summary: summaryByDraft.get(item.id) as Record<string, unknown> }
      : item,
  )
}
function resolveSelectedRunDraftsForExecution(
  options: { requireScopeMatch?: boolean; scopeOverride?: WorkspaceScope } = {},
) {
  if (!selectedRunDrafts.value.length) {
    message.warning('请先勾选至少一条规则')
    return null
  }
  const invalidPrompt = selectedRunDrafts.value.find(
    (item) => !String(item.prompt_template || '').trim(),
  )
  if (invalidPrompt) {
    message.warning(`规则 ${invalidPrompt.rule_code || invalidPrompt.name} 尚未生成 Prompt`)
    return null
  }
  const sceneSet = new Set(selectedRunDrafts.value.map((item) => item.scene))
  if (sceneSet.size > 1) {
    message.warning('多选规则必须保持同一病历范围（运行/终末）')
    return null
  }
  const effectiveScope = options.scopeOverride || recordFilters.scope
  if (
    options.requireScopeMatch &&
    effectiveScope !== 'all' &&
    selectedRunScene.value &&
    selectedRunScene.value !== effectiveScope
  ) {
    message.warning(
      `所选规则范围为 ${selectedRunScene.value}，与当前执行范围 ${effectiveScope} 不一致`,
    )
    return null
  }
  return selectedRunDrafts.value
}
function cloneDateRange(value: DateRangeValue): DateRangeValue {
  if (!value) return null
  return [value[0], value[1]]
}
function resetBatchLaunchFiltersFromCurrent() {
  batchLaunchFilters.scope = recordFilters.scope
  batchLaunchFilters.department = recordFilters.department
  batchLaunchFilters.doctor = recordFilters.doctor
  batchLaunchFilters.date_field = recordFilters.date_field
  batchLaunchFilters.dateRange = cloneDateRange(recordFilters.dateRange)
  batchLaunchFilters.keyword = recordFilters.keyword || ''
}
async function loadBatchLaunchFilterOptions(options: { silent?: boolean } = {}) {
  batchLaunchFiltersLoading.value = true
  try {
    const response = await getWorkspaceRecordFilters({
      scope: batchLaunchFilters.scope,
      department: batchLaunchFilters.department,
    })
    if (!response.success || !response.data) throw new Error(response.message || '获取筛选项失败')
    batchLaunchDepartmentOptions.value = (response.data.departments || []).map((item) => ({
      label: item,
      value: item,
    }))
    batchLaunchDoctorOptions.value = (response.data.doctors || []).map((item) => ({
      label: item,
      value: item,
    }))
  } catch (error: any) {
    if (!options.silent) {
      message.error(error?.message || '获取筛选项失败')
    }
    throw error
  } finally {
    batchLaunchFiltersLoading.value = false
  }
}
async function loadRecordFilters(options: { silent?: boolean } = {}) {
  try {
    const response = await getWorkspaceRecordFilters({
      scope: recordFilters.scope,
      department: recordFilters.department,
    })
    if (!response.success || !response.data) throw new Error(response.message || '获取筛选项失败')
    departmentOptions.value = (response.data.departments || []).map((item) => ({
      label: item,
      value: item,
    }))
    doctorOptions.value = (response.data.doctors || []).map((item) => ({
      label: item,
      value: item,
    }))
  } catch (error: any) {
    if (!options.silent) {
      message.error(error?.message || '获取筛选项失败')
    }
    throw error
  }
}
async function loadRecords() {
  recordLoading.value = true
  try {
    const response = await getWorkspaceRecords({
      scope: recordFilters.scope,
      department: recordFilters.department,
      doctor: recordFilters.doctor,
      date_field: recordFilters.date_field,
      start_date: recordFilters.dateRange?.[0]?.format('YYYY-MM-DD'),
      end_date: recordFilters.dateRange?.[1]?.format('YYYY-MM-DD'),
      keyword: recordFilters.keyword || undefined,
      page: recordPagination.current,
      page_size: recordPagination.pageSize,
    })
    if (!response.success || !response.data) throw new Error(response.message || '获取病历列表失败')
    records.value = response.data.items
    recordPagination.total = response.data.total
  } catch (error: any) {
    message.error(error?.message || '获取病历列表失败')
  } finally {
    recordLoading.value = false
  }
}
async function loadBatchJobs() {
  if (batchJobQuery.onlyCurrentRule && !selectedDraftId.value) {
    batchJobs.value = []
    batchJobPagination.total = 0
    return
  }
  batchJobLoading.value = true
  try {
    const response = await listWorkspaceBatchJobs({
      draft_id: batchJobQuery.onlyCurrentRule ? selectedDraftId.value : undefined,
      mine_only: batchJobQuery.mineOnly,
      status: batchJobQuery.status,
      scope: batchJobQuery.scope,
      execution_mode: batchJobQuery.execution_mode,
      q: batchJobQuery.keyword || undefined,
      created_start_date: batchJobQuery.dateRange?.[0]?.format('YYYY-MM-DD'),
      created_end_date: batchJobQuery.dateRange?.[1]?.format('YYYY-MM-DD'),
      page: batchJobPagination.current,
      page_size: batchJobPagination.pageSize,
    })
    if (!response.success || !response.data) throw new Error(response.message || '获取批量任务失败')
    batchJobs.value = response.data.items
    batchJobPagination.total = response.data.total
    if (batchJobDetail.value) {
      const latest = response.data.items.find((item) => item.id === batchJobDetail.value?.id)
      if (latest) batchJobDetail.value = latest
    }
  } catch (error: any) {
    message.error(error?.message || '获取批量任务失败')
  } finally {
    batchJobLoading.value = false
  }
}
function handleBatchJobTableChange(pagination: { current?: number; pageSize?: number }) {
  batchJobPagination.current = pagination.current || 1
  batchJobPagination.pageSize = pagination.pageSize || 5
  void loadBatchJobs()
}
function searchBatchJobs() {
  batchJobPagination.current = 1
  void loadBatchJobs()
}
function changeBatchJobRuleScope(onlyCurrentRule: boolean) {
  if (batchJobQuery.onlyCurrentRule === onlyCurrentRule) return
  batchJobQuery.onlyCurrentRule = onlyCurrentRule
  searchBatchJobs()
}
function changeBatchJobOwnership(mineOnly: boolean) {
  if (batchJobQuery.mineOnly === mineOnly) return
  batchJobQuery.mineOnly = mineOnly
  searchBatchJobs()
}
function stopBatchJobPolling() {
  if (batchJobPollTimer !== null) {
    window.clearInterval(batchJobPollTimer)
    batchJobPollTimer = null
  }
}
function startBatchJobPolling(jobId: string) {
  stopBatchJobPolling()
  batchJobPollTimer = window.setInterval(async () => {
    const current = await fetchBatchJobDetail(jobId)
    await loadBatchJobs()
    if (!current || !['queued', 'running'].includes(current.status)) {
      stopBatchJobPolling()
    }
  }, 3000)
}
async function fetchBatchJobDetail(jobId: string) {
  batchJobDetailLoading.value = true
  try {
    const response = await getWorkspaceBatchJob(jobId)
    if (!response.success || !response.data) throw new Error(response.message || '获取任务详情失败')
    batchJobDetail.value = response.data
    resultDrawerMode.value = 'batch'
    resultDrawerRecord.value = null
    if (['queued', 'running'].includes(response.data.status)) startBatchJobPolling(response.data.id)
    else stopBatchJobPolling()
    return response.data
  } catch (error: any) {
    message.error(error?.message || '获取任务详情失败')
    return null
  } finally {
    batchJobDetailLoading.value = false
  }
}
function openBatchJobDrawer(job: CustomRuleBatchJob) {
  fetchBatchJobDetail(job.id)
}
function openLatestBatchJobDrawer() {
  if (batchJobDetail.value?.id) {
    openBatchJobDrawer(batchJobDetail.value)
    return
  }
  if (!batchJobs.value.length) return message.info('当前暂无批量任务')
  openBatchJobDrawer(batchJobs.value[0])
}
async function executeCancelBatchJob(jobId: string) {
  if (!jobId || cancellingBatchJobId.value) return
  cancellingBatchJobId.value = jobId
  try {
    const response = await cancelWorkspaceBatchJob(jobId)
    if (!response.success || !response.data) {
      throw new Error(response.message || '停止批量任务失败')
    }
    if (batchJobDetail.value?.id === response.data.id) {
      batchJobDetail.value = response.data
    }
    await loadBatchJobs()
    await fetchBatchJobDetail(jobId)
    stopBatchJobPolling()
    message.success('批量任务已停止')
  } catch (error: any) {
    message.error(error?.message || '停止批量任务失败')
  } finally {
    cancellingBatchJobId.value = ''
  }
}
function cancelActiveBatchJob() {
  const job = activeBatchJob.value
  if (!job || !['queued', 'running'].includes(job.status)) {
    message.info('当前任务无需停止')
    return
  }
  Modal.confirm({
    title: '确认停止当前批量任务？',
    content: '停止后将不再继续处理剩余病历，已完成部分会保留。',
    okText: '停止任务',
    cancelText: '取消',
    okButtonProps: { danger: true },
    onOk: () => executeCancelBatchJob(job.id),
  })
}
async function changeScope(scope: WorkspaceScope) {
  if (recordFilters.scope === scope) return
  recordFilters.scope = scope
  recordFilters.department = undefined
  recordFilters.doctor = undefined
  recordFilters.date_field = scope === 'running' ? 'admission' : 'discharge'
  recordFilters.dateRange = null
  selectedRecordKeys.value = []
  await searchRecords()
}
async function searchRecords() {
  recordPagination.current = 1
  await loadRecords()
  void loadRecordFilters({ silent: true }).catch(() => {
    message.warning('筛选项加载较慢，请稍后重试')
  })
}
async function refreshRecords() {
  await loadRecords()
  void loadRecordFilters({ silent: true }).catch(() => {
    message.warning('筛选项加载较慢，请稍后重试')
  })
}
async function handleDepartmentChange() {
  recordFilters.doctor = undefined
  await loadRecordFilters({ silent: true }).catch(() => {
    message.warning('医生筛选项加载失败，请重试')
  })
}
function handleRecordTableChange(pagination: { current?: number; pageSize?: number }) {
  recordPagination.current = pagination.current || 1
  recordPagination.pageSize = pagination.pageSize || 20
  loadRecords()
}
function selectCurrentPageRecords() {
  selectedRecordKeys.value = Array.from(
    new Set([...selectedRecordKeys.value, ...records.value.map((item) => item.record_id)]),
  )
}
function selectedTestRecords() {
  const keySet = new Set(selectedRecordKeys.value)
  return records.value
    .filter((item) => keySet.has(item.record_id))
    .map((item) => ({
      record_id: item.record_id,
      visit_id: item.visit_id,
      patient_name: item.patient_name,
      department: item.department,
      doctor: item.doctor,
    }))
}
async function runSingleTest(record: CustomRuleWorkspaceRecord) {
  await runSingleTestByPayload({
    record_id: record.record_id,
    visit_id: record.visit_id,
    patient_name: record.patient_name,
    department: record.department,
    doctor: record.doctor,
  })
}
async function runBatchTest() {
  const runDrafts = resolveSelectedRunDraftsForExecution()
  if (!runDrafts) return
  const selectedRecords = selectedTestRecords()
  if (selectedRecords.length === 0) return message.warning('请先选择病历')
  if (selectedRecords.length === 1) {
    const target = records.value.find((item) => item.record_id === selectedRecords[0].record_id)
    if (target) return runSingleTest(target)
  }
  testingBatch.value = true
  try {
    const draftIds = runDrafts.map((item) => item.id)
    const response = await runWorkspaceBatchTest({
      draft_id: draftIds[0],
      draft_ids: draftIds,
      records: selectedRecords,
      temperature: advancedParams.temperature,
      top_p: advancedParams.top_p,
      max_tokens: advancedParams.max_tokens,
    })
    if (!response.success || !response.data) throw new Error(response.message || '批量测试失败')
    batchResult.value = response.data
    singleResult.value = null
    syncDraftSummariesFromRuleResults(response.data.rule_results || [])
    if (!response.data.rule_results?.length) {
      syncDraftSummary(response.data.summary || {})
    }
    const nextMap = { ...recordResults.value }
    response.data.items.forEach((item) => {
      nextMap[item.record_id] = normalizeRecordResult(item)
    })
    recordResults.value = nextMap
    resultDrawerMode.value = 'batch'
    message.success('批量测试完成')
  } catch (error: any) {
    message.error(error?.message || '批量测试失败')
  } finally {
    testingBatch.value = false
  }
}
async function createBatchJobInternal(filters: BatchLaunchFilters): Promise<boolean> {
  const runDrafts = resolveSelectedRunDraftsForExecution({
    requireScopeMatch: true,
    scopeOverride: filters.scope,
  })
  if (!runDrafts) return false
  testingBatch.value = true
  try {
    const recordIds =
      selectedRecordKeys.value.length > 0 ? [...selectedRecordKeys.value] : undefined
    const draftIds = runDrafts.map((item) => item.id)
    const response = await createWorkspaceBatchJob({
      draft_id: draftIds[0],
      draft_ids: draftIds,
      scope: filters.scope,
      department: filters.department,
      doctor: filters.doctor,
      date_field: filters.date_field,
      start_date: filters.dateRange?.[0]?.format('YYYY-MM-DD'),
      end_date: filters.dateRange?.[1]?.format('YYYY-MM-DD'),
      keyword: filters.keyword || undefined,
      record_ids: recordIds,
      temperature: advancedParams.temperature,
      top_p: advancedParams.top_p,
      max_tokens: advancedParams.max_tokens,
    })
    if (!response.success || !response.data) throw new Error(response.message || '创建批量任务失败')
    batchResult.value = null
    singleResult.value = null
    batchJobDetail.value = response.data
    resultDrawerMode.value = 'batch'
    await loadBatchJobs()
    startBatchJobPolling(response.data.id)
    message.success(
      recordIds?.length
        ? `批量任务已创建，将处理 ${recordIds.length} 条${scopeLabelMap[filters.scope]}`
        : `批量任务已创建，将按筛选条件处理${scopeLabelMap[filters.scope]}`,
    )
    return true
  } catch (error: any) {
    message.error(error?.message || '创建批量任务失败')
    return false
  } finally {
    testingBatch.value = false
  }
}
async function handleBatchLaunchScopeChange(scope: WorkspaceScope) {
  batchLaunchFilters.scope = scope
  batchLaunchFilters.department = undefined
  batchLaunchFilters.doctor = undefined
  batchLaunchFilters.date_field = scope === 'running' ? 'admission' : 'discharge'
  await loadBatchLaunchFilterOptions({ silent: true }).catch(() => {
    message.warning('批量筛选项加载较慢，请稍后重试')
  })
}
async function handleBatchLaunchDepartmentChange() {
  batchLaunchFilters.doctor = undefined
  await loadBatchLaunchFilterOptions({ silent: true }).catch(() => {
    message.warning('批量医生筛选项加载失败，请重试')
  })
}
async function confirmBatchLaunch() {
  const ok = await createBatchJobInternal(batchLaunchFilters)
  if (ok) batchLaunchModalOpen.value = false
}
async function triggerBatchQcJob() {
  if (!resolveSelectedRunDraftsForExecution()) return
  resetBatchLaunchFiltersFromCurrent()
  batchLaunchModalOpen.value = true
  await loadBatchLaunchFilterOptions({ silent: true }).catch(() => {
    message.warning('批量筛选项加载较慢，请稍后重试')
  })
}
async function exportBatchJobReport(format: 'xlsx' | 'csv' = 'xlsx') {
  if (!activeBatchJob.value) return message.info('请先选择一个批量任务')
  const response = await exportWorkspaceBatchJob({ job_id: activeBatchJob.value.id, format })
  if (!response.success || !response.data) {
    message.error(response.message || '导出任务报告失败')
    return
  }
  const blob = response.data
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${activeBatchJob.value.rule_code || 'custom-qc'}-${activeBatchJob.value.id}.${format}`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  window.URL.revokeObjectURL(url)
  message.success('任务报告已开始下载')
}
function hasRecordResult(recordId: string) {
  return !!recordResults.value[recordId]
}
function getRecordResult(recordId: string) {
  return recordResults.value[recordId] || null
}
function getRecordResultTagColor(recordId: string) {
  const result = getRecordResult(recordId)
  return !result ? 'default' : result.is_compliant ? 'success' : 'error'
}
function getRecordResultStatusText(recordId: string) {
  const result = getRecordResult(recordId)
  return !result ? '未测试' : result.is_compliant ? '合规/不适用' : '命中问题'
}
function getRecordResultTagClass(recordId: string) {
  const result = getRecordResult(recordId)
  if (!result) return 'border-slate-200 bg-slate-50 text-slate-500'
  return result.is_compliant
    ? 'border-emerald-200 bg-emerald-50/70 text-emerald-700'
    : 'border-amber-200 bg-amber-50/70 text-amber-700'
}
function getRecordFindingPreview(recordId: string) {
  return getRecordResult(recordId)?.findings || '尚未执行该规则测试'
}
function openSingleResultDrawer(record: CustomRuleWorkspaceRecord) {
  const result = getRecordResult(record.record_id)
  if (!result) return message.info('当前病历暂无测试结果')
  resultDrawerMode.value = 'single'
  resultDrawerRecord.value = result
}
function openBatchItemEvidence(item: RecordTestResultItem) {
  resultDrawerMode.value = 'single'
  resultDrawerRecord.value = item
}
function openBatchResultDrawer() {
  if (!batchResult.value) return message.info('当前暂无批量测试结果')
  resultDrawerMode.value = 'batch'
}
function closeResultDrawer() {
  resultDrawerMode.value = 'empty'
  resultDrawerRecord.value = null
  batchResult.value = null
  singleResult.value = null
}
function closeEvidenceDrawer() {
  resultDrawerRecord.value = null
}

watch(selectedDraftId, async (next, prev) => {
  if (next === prev) return
  if (next && !selectedDraftIds.value.includes(next)) {
    selectedDraftIds.value = Array.from(new Set([next, ...selectedDraftIds.value]))
  }
  batchJobPagination.current = 1
  batchJobDetail.value = null
  stopBatchJobPolling()
  if (next) await loadBatchJobs()
})

onMounted(async () => {
  await Promise.allSettled([loadDrafts(), searchRecords()])
  await loadBatchJobs()
})

onUnmounted(() => {
  stopBatchJobPolling()
})
</script>

<style scoped>
.custom-workspace-page {
  --cw-color-bg: #f9fafb;
  --cw-color-surface: #ffffff;
  --cw-color-border: #e5e7eb;
  --cw-color-input-border: #d1d5db;
  --cw-color-title: #111827;
  --cw-color-body: #374151;
  --cw-color-muted: #6b7280;
  --cw-color-caption: #9ca3af;
  --cw-color-brand: #2563eb;
  --cw-color-brand-hover: #1d4ed8;
  --cw-shadow-surface: 0 1px 3px rgba(15, 23, 42, 0.08);
  background: var(--cw-color-bg);
  color: var(--cw-color-body);
  font-size: 12px;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(107, 114, 128, 0.32);
  border-radius: 999px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(75, 85, 99, 0.52);
}

.cw-analysis-overview {
  border-radius: 6px !important;
  border: 1px solid var(--cw-color-border) !important;
  background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
  box-shadow: var(--cw-shadow-surface);
}

.cw-analysis-overview__eyebrow {
  color: var(--cw-color-caption);
  font-size: 10px;
  font-weight: 700;
}

.cw-analysis-overview__title {
  color: var(--cw-color-title);
  font-size: 16px !important;
  font-weight: 700 !important;
  letter-spacing: 0;
}

.cw-analysis-overview__subtitle {
  color: var(--cw-color-muted);
  font-size: 12px;
  line-height: 1.5;
}

.cw-kpi-card {
  border-radius: 6px !important;
  border-color: var(--cw-color-border) !important;
  background: var(--cw-color-surface) !important;
  box-shadow: var(--cw-shadow-surface);
}

.cw-primary-action {
  height: 30px !important;
  padding: 4px 14px !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  border-radius: 4px !important;
  border: 1px solid var(--cw-color-brand) !important;
  background: var(--cw-color-brand) !important;
  box-shadow: none !important;
}

.cw-primary-action:hover {
  background: var(--cw-color-brand-hover) !important;
  border-color: var(--cw-color-brand-hover) !important;
}

.cw-panel {
  border-radius: 6px !important;
  border: 1px solid var(--cw-color-border) !important;
  background: var(--cw-color-surface) !important;
  box-shadow: var(--cw-shadow-surface);
}

.workstation-surface-enter {
  animation: workstationSurfaceEnter 260ms ease-out both;
}

.workstation-surface-enter--delay-1 {
  animation-delay: 50ms;
}

.workstation-surface-enter--delay-2 {
  animation-delay: 90ms;
}

@keyframes workstationSurfaceEnter {
  from {
    opacity: 0;
    transform: translateY(4px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

:deep(.draft-row-active > td) {
  background: #eef5ff !important;
}

:deep(.custom-workspace-page .rounded-2xl),
:deep(.custom-workspace-page .rounded-xl),
:deep(.custom-workspace-page .rounded-lg) {
  border-radius: 6px !important;
}

:deep(.custom-workspace-page .ant-btn) {
  height: 30px;
  padding: 4px 14px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
}

:deep(.custom-workspace-page .ant-btn-sm) {
  height: 22px;
  padding: 0 6px;
  font-size: 12px;
  font-weight: 400;
  border-radius: 2px;
}

:deep(.custom-workspace-page .ant-btn-lg) {
  height: 30px;
  padding: 4px 14px;
  font-size: 13px;
}

:deep(.custom-workspace-page .ant-input),
:deep(.custom-workspace-page .ant-select-selector),
:deep(.custom-workspace-page .ant-picker) {
  border-color: var(--cw-color-input-border) !important;
  border-radius: 4px !important;
  font-size: 12px !important;
}

:deep(.cw-panel .ant-input),
:deep(.cw-panel .ant-picker) {
  min-height: 28px !important;
  height: 28px !important;
  padding: 3px 8px !important;
}

:deep(.cw-panel .ant-select-single .ant-select-selector) {
  min-height: 28px !important;
  height: 28px !important;
  padding: 0 8px !important;
}

:deep(.cw-panel .ant-select-single .ant-select-selection-item),
:deep(.cw-panel .ant-select-single .ant-select-selection-placeholder) {
  line-height: 26px !important;
  font-size: 12px !important;
}

:deep(.cw-panel .ant-picker-input > input) {
  font-size: 12px !important;
}

:deep(.ant-table-thead > tr > th) {
  height: 40px;
  padding: 8px 6px !important;
  background: #f9fafb !important;
  color: #374151 !important;
  font-size: 11px;
  font-weight: 600 !important;
  white-space: nowrap;
}
:deep(.ant-table-tbody > tr > td) {
  height: 36px;
  padding: 4px 8px !important;
  border-bottom: 1px solid #f1f5f9 !important;
  color: #374151 !important;
  font-size: 12px;
}
:deep(.ant-table-tbody > tr:hover > td) {
  background: #eff6ff !important;
}
:deep(.record-bench-table .ant-table-tbody > tr:hover > td) {
  background: #eff6ff !important;
}
:deep(.record-bench-table .ant-table-tbody > tr > td) {
  vertical-align: middle;
}
:deep(.record-action-cell) {
  opacity: 0;
  transform: translateX(8px);
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
  pointer-events: none;
}
:deep(.record-bench-table .ant-table-tbody > tr:hover .record-action-cell) {
  opacity: 1;
  transform: translateX(0);
  pointer-events: auto;
}
:deep(.record-action-btn) {
  height: 22px !important;
  padding: 0 6px !important;
  border-radius: 2px !important;
  border: 1px solid #d1d5db !important;
  background: #ffffff !important;
  color: #2563eb !important;
  font-size: 12px !important;
  font-weight: 400 !important;
  box-shadow: none !important;
}
:deep(.record-action-btn:hover) {
  border-color: #2563eb !important;
  background: #eff6ff !important;
  color: #1d4ed8 !important;
}
:deep(.drawer-meta-control-input.ant-input) {
  height: 30px !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  font-size: 13px !important;
  line-height: 30px !important;
}
:deep(.drawer-meta-control-select.ant-select .ant-select-selector) {
  height: 30px !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  display: flex !important;
  align-items: center !important;
}
:deep(.drawer-meta-control-select.ant-select .ant-select-selection-item) {
  font-size: 13px !important;
  line-height: 30px !important;
}
:deep(.drawer-meta-control-select.ant-select .ant-select-selection-placeholder) {
  font-size: 13px !important;
  line-height: 30px !important;
}

:deep(.custom-workspace-page .ant-form-item-label > label) {
  color: var(--cw-color-body) !important;
  font-size: 12px !important;
  font-weight: 500 !important;
}

:deep(.custom-workspace-page .ant-tag) {
  border-radius: 2px !important;
  font-size: 11px !important;
  line-height: 16px !important;
  padding: 0 5px !important;
}

:deep(.cw-scene-tag.ant-tag),
:deep(.cw-status-tag.ant-tag) {
  display: inline-flex !important;
  align-items: center !important;
  height: 24px !important;
  padding: 0 10px !important;
  border-radius: 8px !important;
  border: 1px solid transparent !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  line-height: 22px !important;
  margin-inline-end: 0 !important;
}

:deep(.cw-scene-tag--final.ant-tag) {
  color: #1d4ed8 !important;
  background: #eff6ff !important;
  border-color: #bfdbfe !important;
}

:deep(.cw-scene-tag--running.ant-tag) {
  color: #7c3aed !important;
  background: #f5f3ff !important;
  border-color: #ddd6fe !important;
}

:deep(.cw-status-tag--published.ant-tag) {
  color: #15803d !important;
  background: #f0fdf4 !important;
  border-color: #bbf7d0 !important;
}

:deep(.cw-status-tag--draft.ant-tag) {
  color: #1d4ed8 !important;
  background: #dbeafe !important;
  border-color: #93c5fd !important;
}

:deep(.cw-qc-tag.ant-tag) {
  display: inline-flex !important;
  align-items: center !important;
  height: 24px !important;
  padding: 0 10px !important;
  border-radius: 8px !important;
  border: 1px solid transparent !important;
  margin-inline-end: 0 !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  line-height: 22px !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85) !important;
}

:deep(.cw-qc-tag--queued.ant-tag) {
  color: #334155 !important;
  background: #f8fafc !important;
  border-color: #cbd5e1 !important;
}

:deep(.cw-qc-tag--running.ant-tag) {
  color: #1d4ed8 !important;
  background: #eff6ff !important;
  border-color: #bfdbfe !important;
}

:deep(.cw-qc-tag--completed.ant-tag),
:deep(.cw-qc-tag--compliant.ant-tag) {
  color: #14532d !important;
  background: linear-gradient(180deg, #ecfdf3 0%, #dcfce8 100%) !important;
  border-color: #86efac !important;
}

:deep(.cw-qc-tag--failed.ant-tag),
:deep(.cw-qc-tag--issue.ant-tag) {
  color: #b91c1c !important;
  background: #fef2f2 !important;
  border-color: #fca5a5 !important;
}

:deep(.cw-qc-tag--canceled.ant-tag) {
  color: #92400e !important;
  background: #fffbeb !important;
  border-color: #fcd34d !important;
}

.cw-draft-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

:deep(.cw-draft-action-btn.ant-btn) {
  width: 24px !important;
  height: 24px !important;
  min-width: 24px !important;
  padding: 0 !important;
  border-radius: 6px !important;
  border: 1px solid #dbe2ea !important;
  background: #ffffff !important;
  color: #334155 !important;
  transition: all 0.2s ease;
}

:deep(.cw-draft-action-btn.ant-btn .anticon) {
  font-size: 14px !important;
}

:deep(.cw-draft-action-btn.ant-btn:hover) {
  border-color: #93c5fd !important;
  background: #eff6ff !important;
  color: #1d4ed8 !important;
}

:deep(.cw-draft-action-btn--delete.ant-btn) {
  border-color: #fecaca !important;
  color: #ef4444 !important;
}

:deep(.cw-draft-action-btn--delete.ant-btn:hover) {
  border-color: #fca5a5 !important;
  background: #fef2f2 !important;
  color: #dc2626 !important;
}

:deep(.cw-draft-publish-btn.ant-btn) {
  height: 24px !important;
  min-width: 48px !important;
  padding: 0 10px !important;
  border-radius: 6px !important;
  border: 1px solid #bfdbfe !important;
  background: #eff6ff !important;
  color: #2563eb !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  line-height: 22px !important;
}

:deep(.cw-draft-publish-btn.ant-btn:hover) {
  border-color: #93c5fd !important;
  background: #dbeafe !important;
  color: #1d4ed8 !important;
}

:deep(.cw-draft-publish-btn.ant-btn[disabled]) {
  color: #94a3b8 !important;
  border-color: #e2e8f0 !important;
  background: #f8fafc !important;
}

:deep(.custom-workspace-page .ant-empty-description) {
  color: var(--cw-color-muted) !important;
  font-size: 12px !important;
}

:deep(.custom-workspace-page .ant-pagination-item),
:deep(.custom-workspace-page .ant-pagination-prev),
:deep(.custom-workspace-page .ant-pagination-next) {
  min-width: 24px !important;
  height: 24px !important;
  line-height: 22px !important;
  font-size: 12px !important;
}

@media (max-width: 1279px) {
  .cw-analysis-overview {
    padding: 12px !important;
  }
}

@media (max-width: 1023px) {
  .custom-workspace-page {
    padding-top: 10px;
  }

  .cw-analysis-overview__title {
    font-size: 15px !important;
  }
}
</style>
