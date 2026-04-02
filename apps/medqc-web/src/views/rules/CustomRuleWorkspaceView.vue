<template>
  <div class="min-h-full space-y-3 p-4 text-slate-700">
    <section
      class="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-5 shadow-sm"
    >
      <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div class="max-w-3xl">
          <p class="mb-1 text-[12px] font-bold uppercase tracking-[0.16em] text-blue-500/75">
            Custom QC Workspace
          </p>
          <h1 class="text-[24px] font-black text-slate-800">
            自定义规则工作台
          </h1>
          <p class="mt-1.5 text-[13px] leading-6 text-slate-500">
            上半部分维护规则，下半部分对终末病历做单条/批量测试。规则配置统一收进右侧抽屉，不再把创建区放在页面顶部。
          </p>
        </div>

        <div class="flex min-w-[340px] flex-col gap-3">
          <div class="grid grid-cols-3 gap-2">
            <div class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
              <div class="text-[12px] text-slate-400">
                规则总数
              </div>
              <div class="mt-1 text-[20px] font-black text-slate-900">
                {{ draftPagination.total }}
              </div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
              <div class="text-[12px] text-slate-400">
                {{ currentScopeLabel }}
              </div>
              <div class="mt-1 text-[20px] font-black text-slate-900">
                {{ recordPagination.total }}
              </div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
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
            size="large"
            class="!h-11 !rounded-xl !border-0 !bg-blue-600 px-5 shadow-[0_10px_20px_-12px_rgba(37,99,235,0.8)] hover:!bg-blue-500"
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

    <section class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div class="mb-2 flex items-center justify-between gap-3">
        <div>
          <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
            Rule Catalog
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
      </div>

      <div class="mb-3 grid gap-2 md:grid-cols-[1fr_140px]">
        <a-input
          v-model:value="draftQuery.keyword"
          allow-clear
          placeholder="搜索规则编码/名称"
          class="!h-9 !rounded-lg !border-slate-200"
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
          class="[&_.ant-select-selector]:!h-9 [&_.ant-select-selector]:!rounded-lg [&_.ant-select-selector]:!border-slate-200"
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
                {{ record.description || record.source_requirement || '-' }}
              </div>
            </template>
            <template v-else-if="column.key === 'scene'">
              <a-tag :color="record.scene === 'final' ? 'blue' : 'gold'">
                {{ record.scene === 'final' ? '终末病历' : '运行病历' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.status === 'published' ? 'success' : 'processing'">
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
              <div class="flex items-center justify-end gap-1">
                <a-button
                  type="text"
                  size="small"
                  @click.stop="openEditDrawer(record as CustomRuleDraft)"
                >
                  <template #icon>
                    <EditOutlined />
                  </template>
                </a-button>
                <a-button
                  type="text"
                  size="small"
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
                    @click.stop
                  >
                    <template #icon>
                      <DeleteOutlined />
                    </template>
                  </a-button>
                </a-popconfirm>
                <a-button
                  v-if="record.status === 'draft'"
                  type="link"
                  size="small"
                  :disabled="!canPublishRecord(record as CustomRuleDraft)"
                  @click.stop="publishDraftById(record.id)"
                >
                  发布
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

    <section class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
            Real Record QC Bench
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
            :disabled="!selectedDraft || !hasPromptTemplate"
            :loading="testingBatch"
            @click="triggerBatchQcJob"
          >
            <template #icon>
              <PlayCircleOutlined />
            </template>发起批量质控
          </a-button>
          <a-button
            type="primary"
            :disabled="!selectedDraft || !canPublishSelectedDraft"
            :loading="publishingDraft"
            @click="publishSelectedDraft"
          >
            <template #icon>
              <RocketOutlined />
            </template>发布规则
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
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <div class="flex rounded-lg border border-slate-200 bg-white p-1">
            <button
              v-for="scopeOption in scopeOptions"
              :key="scopeOption.value"
              type="button"
              class="rounded-md px-2.5 py-1 text-xs font-medium transition"
              :class="
                recordFilters.scope === scopeOption.value
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'
              "
              @click="changeScope(scopeOption.value)"
            >
              {{ scopeOption.label }}
            </button>
          </div>
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
              Recent Batch Jobs
            </div>
            <div class="text-sm font-semibold text-slate-800">
              最近批量任务
            </div>
          </div>
          <span class="text-xs text-slate-400">共 {{ batchJobPagination.total }} 个</span>
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
                <a-tag :color="getBatchJobStatusTagColor(job.status)">
                  {{ getBatchJobStatusText(job.status) }}
                </a-tag>
                <a-tag>{{ scopeLabelMap[job.scope] }}</a-tag>
              </div>
              <div class="mt-1 text-xs text-slate-500">
                {{ formatDateTime(job.created_at) }} · 成功 {{ job.success_count }} · 失败
                {{ job.failed_count }} · 命中 {{ job.issue_records }}
              </div>
            </div>
            <span class="text-xs text-slate-400">{{ job.record_ids?.length || job.total_records || 0 }} 条</span>
          </button>
        </div>
      </div>

      <div
        class="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2.5"
      >
        <a-input
          v-model:value="recordFilters.keyword"
          allow-clear
          placeholder="搜索病历号 / visit / 患者姓名"
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
                :disabled="!selectedDraft || !hasPromptTemplate"
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
    </section>

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
              Rule Editor
            </p>
            <h2 class="text-2xl font-black text-slate-900">
              {{ editorDrawerTitle }}
            </h2>
            <p class="mt-2 text-sm leading-6 text-slate-500">
              在抽屉内完成元数据、Prompt、示例和发布动作。
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
                  />
                </a-form-item>
                <a-form-item
                  label="适用文书"
                  required
                >
                  <a-select
                    v-model:value="draftForm.document_type"
                    :options="documentTypeOptions"
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
              <a-form-item label="规则描述">
                <a-textarea
                  v-model:value="draftForm.description"
                  :rows="3"
                />
              </a-form-item>
            </a-form>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <div class="mb-3 flex items-center justify-between gap-3">
              <div>
                <p class="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
                  Prompt Builder
                </p>
                <h3 class="text-lg font-black text-slate-900">
                  Prompt 生成与编辑
                </h3>
              </div>
              <a-button
                :loading="generatingPrompt"
                @click="generatePromptForDrawer"
              >
                <template #icon>
                  <RobotOutlined />
                </template>AI 生成 Prompt
              </a-button>
            </div>
            <a-alert
              :type="drawerGenerationMode === 'llm' ? 'success' : 'warning'"
              show-icon
              :message="
                drawerGenerationMode === 'llm'
                  ? '当前 Prompt 来自 AI 生成'
                  : '当前 Prompt 为模板或待生成状态'
              "
              :description="drawerPromptSummary"
            />
            <div
              v-if="draftForm.check_points.length > 0"
              class="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-500"
            >
              <div class="mb-1 font-semibold text-slate-700">
                生成检查要点
              </div>
              <div
                v-for="(item, index) in draftForm.check_points"
                :key="`${index}-${item}`"
              >
                {{ index + 1 }}. {{ item }}
              </div>
            </div>
            <a-form
              layout="vertical"
              class="mt-3"
            >
              <a-form-item label="Prompt 模板">
                <a-textarea
                  v-model:value="draftForm.prompt_template"
                  :rows="10"
                />
              </a-form-item>
            </a-form>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-white p-4">
            <p class="mb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
              Examples
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
              Last Test Summary
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
            :disabled="!selectedDraft || !canPublishSelectedDraft"
            :loading="publishingDraft"
            @click="publishSelectedDraft"
          >
            发布规则
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
              Test Result
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
                  <a-tag :color="getBatchJobStatusTagColor(activeBatchJob.status)">
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
                    <strong>{{ item.patient_name || item.record_id }}</strong><a-tag :color="item.is_compliant ? 'success' : 'error'">
                      {{ item.is_compliant ? '合规/不适用' : '命中问题' }}
                    </a-tag>
                  </div>
                  <p class="mt-2 text-sm leading-6 text-slate-500">
                    {{ item.findings || '无附加结论' }}
                  </p>
                  <p class="mt-2 text-xs text-slate-400">
                    {{ item.record_id }} / {{ item.department || '-' }}
                  </p>
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
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="resultDrawerMode === 'single' && resultDrawerRecord">
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <div class="flex items-center justify-between gap-2">
                <strong>{{
                  resultDrawerRecord.patient_name || resultDrawerRecord.record_id
                }}</strong><a-tag :color="resultDrawerRecord.is_compliant ? 'success' : 'error'">
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
                Findings
              </h3>
              <p class="mt-2 text-sm leading-7 text-slate-500">
                {{ resultDrawerRecord.findings || '无附加结论' }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 class="text-lg font-black text-slate-900">
                Evidence
              </h3>
              <p class="mt-2 text-sm leading-7 text-slate-500">
                {{ resultDrawerRecord.evidence || '无' }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 class="text-lg font-black text-slate-900">
                Suggestion
              </h3>
              <p class="mt-2 text-sm leading-7 text-slate-500">
                {{ resultDrawerRecord.suggestion || '无' }}
              </p>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h3 class="text-lg font-black text-slate-900">
                Confidence
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
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import type { Dayjs } from 'dayjs'
import { Empty, Modal, message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import {
  CloseOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
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
import type {
  CustomRuleBatchJob,
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

interface RecordTestResultItem {
  record_id: string
  visit_id?: string
  patient_name?: string
  department?: string
  status: string
  is_compliant: boolean
  findings: string
  evidence: string
  suggestion: string
  confidence: number
}

const draftLoading = ref(false)
const creatingDraft = ref(false)
const savingDraft = ref(false)
const generatingPrompt = ref(false)
const publishingDraft = ref(false)
const testingBatch = ref(false)
const testingSingleRecordId = ref('')
const batchJobLoading = ref(false)
const batchJobDetailLoading = ref(false)
const drafts = ref<CustomRuleDraft[]>([])
const selectedDraftId = ref('')
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
const scopeOptions = [
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

const selectedDraft = computed(
  () => drafts.value.find((item) => item.id === selectedDraftId.value) || null,
)
const scopeLabelMap: Record<WorkspaceScope, string> = {
  final: '终末病历',
  running: '运行病历',
  all: '全量病历',
}
const currentScopeLabel = computed(() => scopeLabelMap[recordFilters.scope] || '终末病历')
const recentBatchJobCount = computed(() => batchJobPagination.total)
const selectedBatchJob = computed(() => {
  if (batchJobDetail.value && batchJobDetail.value.id) return batchJobDetail.value
  return batchJobs.value.find((item) => item.id === (batchJobDetail.value?.id || '')) || null
})
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
const hasPromptTemplate = computed(
  () => !!String(selectedDraft.value?.prompt_template || '').trim(),
)
const canPublishSelectedDraft = computed(
  () => !!selectedDraft.value && canPublishRecord(selectedDraft.value),
)
const drawerPrimaryLoading = computed(() =>
  editorDrawerMode.value === 'create' ? creatingDraft.value : savingDraft.value,
)
const drawerGenerationMode = computed(() => draftForm.generation_mode || 'fallback_template')
const drawerPromptSummary = computed(
  () => draftForm.prompt_summary || '请先生成或手工填写 Prompt，再执行病历测试。',
)
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
  date_field: 'discharge' as 'admission' | 'discharge',
  dateRange: null as DateRangeValue,
  keyword: '',
})
const departmentOptions = ref<Array<{ label: string; value: string }>>([])
const doctorOptions = ref<Array<{ label: string; value: string }>>([])
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
  { title: '病历号 / visit', key: 'record_info', width: 160 },
  { title: '患者信息', dataIndex: 'patient_name', key: 'patient_name', width: 170 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 130 },
  { title: '医生', dataIndex: 'doctor', key: 'doctor', width: 130 },
  { title: '出院日期', dataIndex: 'discharge_date', key: 'discharge_date', width: 120 },
  { title: '最近测试状态', key: 'latest_status', width: 120 },
  { title: '最近命中结果摘要', key: 'latest_findings' },
  { title: '操作', key: 'actions', width: 150, fixed: 'right' as const },
]
const recordRowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRecordKeys.value,
  onChange: (keys: Array<string | number>) => {
    selectedRecordKeys.value = keys.map((item) => String(item))
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
  draftForm.name = draft.name || ''
  draftForm.description = draft.description || ''
  draftForm.source_requirement = draft.source_requirement || ''
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
  const requirement = draftForm.source_requirement.trim() || draftForm.description.trim()
  if (!name) return (message.warning('请先填写规则名称'), false)
  if (!requirement) return (message.warning('请先填写需求描述'), false)
  return true
}
function buildDraftPayload(): CustomRuleDraftPayload {
  const requirement = draftForm.source_requirement.trim() || draftForm.description.trim()
  return {
    name: draftForm.name.trim(),
    description: draftForm.description.trim() || requirement,
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
async function generatePromptForDrawer() {
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
    message.success(
      promptResult.generation_mode === 'llm' ? 'Prompt 生成成功' : '已回退为模板 Prompt',
    )
  } catch (error: any) {
    message.error(error?.message || '生成 Prompt 失败')
  } finally {
    generatingPrompt.value = false
  }
}
async function copyDraft(record: CustomRuleDraft) {
  try {
    const response = await createWorkspaceDraft({
      name: `${record.name}-副本`,
      description: record.description,
      source_requirement: record.source_requirement,
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
  if (!canPublishSelectedDraft.value) return message.warning('请先完成至少一次成功测试')
  if (editorDrawerOpen.value) {
    const saved = await persistDraftFromDrawer({ silentSuccess: true })
    if (!saved) return
  }
  await publishDraftById(selectedDraft.value.id)
}

function normalizeRecordResult(result: {
  record_id: string
  visit_id?: string
  patient_name?: string
  department?: string
  status: string
  is_compliant: boolean
  findings: string
  evidence: string
  suggestion: string
  confidence: number
}): RecordTestResultItem {
  return { ...result }
}
function syncDraftSummary(summary: Record<string, unknown>) {
  if (!selectedDraft.value) return
  drafts.value = drafts.value.map((item) =>
    item.id === selectedDraft.value?.id ? { ...item, last_test_summary: summary } : item,
  )
}
async function loadRecordFilters() {
  const response = await getWorkspaceRecordFilters({
    scope: 'final',
    department: recordFilters.department,
  })
  if (!response.success || !response.data) throw new Error(response.message || '获取筛选项失败')
  departmentOptions.value = (response.data.departments || []).map((item) => ({
    label: item,
    value: item,
  }))
  doctorOptions.value = (response.data.doctors || []).map((item) => ({ label: item, value: item }))
}
async function loadRecords() {
  recordLoading.value = true
  try {
    const response = await getWorkspaceRecords({
      scope: 'final',
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
async function searchRecords() {
  recordPagination.current = 1
  await Promise.all([loadRecordFilters(), loadRecords()])
}
async function refreshRecords() {
  await Promise.all([loadRecordFilters(), loadRecords()])
}
async function handleDepartmentChange() {
  recordFilters.doctor = undefined
  await loadRecordFilters()
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
  if (!selectedDraft.value) return message.warning('请先选择规则')
  if (!hasPromptTemplate.value) return message.warning('请先为当前规则生成或填写 Prompt')
  testingSingleRecordId.value = record.record_id
  try {
    const response = await runWorkspaceSingleTest({
      draft_id: selectedDraft.value.id,
      records: [
        {
          record_id: record.record_id,
          visit_id: record.visit_id,
          patient_name: record.patient_name,
          department: record.department,
          doctor: record.doctor,
        },
      ],
      temperature: advancedParams.temperature,
      top_p: advancedParams.top_p,
      max_tokens: advancedParams.max_tokens,
    })
    if (!response.success || !response.data) throw new Error(response.message || '单病历测试失败')
    singleResult.value = response.data
    batchResult.value = null
    syncDraftSummary(response.data.summary || {})
    const normalized = normalizeRecordResult({
      record_id: response.data.result.record_id,
      visit_id: response.data.result.visit_id,
      patient_name: response.data.record.patient_name,
      department: response.data.record.department,
      status: response.data.result.status,
      is_compliant: response.data.result.is_compliant,
      findings: response.data.result.findings,
      evidence: response.data.result.evidence,
      suggestion: response.data.result.suggestion,
      confidence: response.data.result.confidence,
    })
    recordResults.value = { ...recordResults.value, [normalized.record_id]: normalized }
    resultDrawerMode.value = 'single'
    resultDrawerRecord.value = normalized
    resultDrawerOpen.value = true
    message.success('单病历测试完成')
  } catch (error: any) {
    message.error(error?.message || '单病历测试失败')
  } finally {
    testingSingleRecordId.value = ''
  }
}
async function runBatchTest() {
  if (!selectedDraft.value) return message.warning('请先选择规则')
  if (!hasPromptTemplate.value) return message.warning('请先为当前规则生成或填写 Prompt')
  const selectedRecords = selectedTestRecords()
  if (selectedRecords.length === 0) return message.warning('请先选择病历')
  if (selectedRecords.length === 1) {
    const target = records.value.find((item) => item.record_id === selectedRecords[0].record_id)
    if (target) return runSingleTest(target)
  }
  testingBatch.value = true
  try {
    const response = await runWorkspaceBatchTest({
      draft_id: selectedDraft.value.id,
      records: selectedRecords,
      temperature: advancedParams.temperature,
      top_p: advancedParams.top_p,
      max_tokens: advancedParams.max_tokens,
    })
    if (!response.success || !response.data) throw new Error(response.message || '批量测试失败')
    batchResult.value = response.data
    singleResult.value = null
    syncDraftSummary(response.data.summary || {})
    const nextMap = { ...recordResults.value }
    response.data.items.forEach((item) => {
      nextMap[item.record_id] = normalizeRecordResult(item)
    })
    recordResults.value = nextMap
    resultDrawerMode.value = 'batch'
    resultDrawerOpen.value = true
    message.success('批量测试完成')
  } catch (error: any) {
    message.error(error?.message || '批量测试失败')
  } finally {
    testingBatch.value = false
  }
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
  resultDrawerOpen.value = true
}
function openBatchResultDrawer() {
  if (!batchResult.value) return message.info('当前暂无批量测试结果')
  resultDrawerMode.value = 'batch'
  resultDrawerOpen.value = true
}
function closeResultDrawer() {
  resultDrawerOpen.value = false
  resultDrawerRecord.value = null
}

onMounted(async () => {
  await Promise.all([loadDrafts(), searchRecords()])
})
</script>

<style scoped>
:deep(.draft-row-active > td) {
  background: #eef5ff !important;
}
:deep(.ant-table-thead > tr > th) {
  background: #f8fafc !important;
  color: #64748b !important;
  font-size: 12px;
  font-weight: 600 !important;
}
:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #f1f5f9 !important;
}
:deep(.ant-table-tbody > tr:hover > td) {
  background: #f8fafc !important;
}
:deep(.record-bench-table .ant-table-tbody > tr:hover > td) {
  background: #f1f5f9 !important;
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
  border-radius: 8px !important;
  border: 1px solid #dbe2ea !important;
  background: #ffffff !important;
  color: #475569 !important;
  box-shadow: none !important;
}
:deep(.record-action-btn:hover) {
  border-color: #93c5fd !important;
  background: #eff6ff !important;
  color: #2563eb !important;
}
</style>
