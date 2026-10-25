<template>
  <div class="custom-rule-workspace mq-page">
    <!-- 页头：眉标 + 大标题；右侧切换执行 / 设计视图 -->
    <header class="crw-head mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">规则 · 自定义质控点</span>
        <h1 class="mq-page-title">
          自定义规则工作台
        </h1>
        <p class="crw-head__desc">
          {{ workspaceModeTip }}
        </p>
      </div>
      <div
        class="mq-segmented"
        role="group"
        aria-label="工作台视图"
      >
        <button
          type="button"
          class="mq-segmented__item"
          :class="{ 'is-active': workspaceMode === 'batch' }"
          @click="workspaceMode = 'batch'"
        >
          批量执行视图
        </button>
        <button
          type="button"
          class="mq-segmented__item"
          :class="{ 'is-active': workspaceMode === 'design' }"
          @click="workspaceMode = 'design'"
        >
          规则设计视图
        </button>
      </div>
    </header>

    <p v-if="isBusinessReadOnly" class="mq-soft" role="status">当前账号仅可查看自定义质控点和已有任务，不能编辑、发布或运行。</p>

    <section class="ops-overview mq-card">
      <div class="ops-kpis">
        <article class="kpi-card">
          <span class="kpi-label">草稿总数</span>
          <strong class="kpi-value">{{ draftPagination.total }}</strong>
        </article>
        <article class="kpi-card">
          <span class="kpi-label">执行规则</span>
          <strong class="kpi-value">{{ effectiveExecutionDraftIds.length }}</strong>
        </article>
        <article class="kpi-card">
          <span class="kpi-label">已选病历</span>
          <strong class="kpi-value">{{ selectedRecordKeys.length }}</strong>
        </article>
        <article class="kpi-card">
          <span class="kpi-label">任务状态</span>
          <strong class="kpi-value">{{
            activeBatchJob ? jobStatusText(activeBatchJob.status) : '未启动'
          }}</strong>
        </article>
      </div>
    </section>

    <section
      v-if="workspaceMode === 'batch'"
      class="step-nav-shell"
    >
      <div class="step-nav">
        <button
          v-for="item in stepItems"
          :key="item.anchor"
          type="button"
          class="step-pill"
          :class="[`step-pill--${item.status}`, { 'is-active': activeStep === item.anchor }]"
          :aria-pressed="activeStep === item.anchor"
          @click="scrollToStep(item.anchor)"
        >
          <span class="step-index">{{ item.index }}</span>
          <span class="step-label">{{ item.label }}</span>
          <span class="step-state">{{ item.statusLabel }}</span>
        </button>
      </div>
    </section>

    <section
      v-show="isStepVisible('step-rules')"
      id="step-rules"
      class="workspace-grid"
    >
      <article class="workspace-panel">
        <div class="panel-head">
          <div>
            <p class="panel-eyebrow">
              步骤一
            </p>
            <h2 class="panel-title">
              规则草稿列表
            </h2>
          </div>
          <div class="panel-actions">
            <a-button
              size="small"
              :loading="draftLoading"
              @click="loadDrafts"
            >
              <template #icon>
                <ReloadOutlined />
              </template>
              刷新
            </a-button>
            <a-button
              :disabled="isBusinessReadOnly"
              type="primary"
              @click="openCreateDrawer"
            >
              <template #icon>
                <PlusOutlined />
              </template>
              新建草稿
            </a-button>
          </div>
        </div>

        <div class="draft-filters">
          <a-input
            v-model:value="draftQuery.keyword"
            allow-clear
            placeholder="搜索规则编码/名称"
            @press-enter="searchDrafts"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input>
          <a-select
            v-model:value="draftQuery.status"
            allow-clear
            placeholder="状态"
            :options="draftStatusOptions"
            @change="searchDrafts"
          />
        </div>

        <a-table
          row-key="id"
          size="small"
          :loading="draftLoading"
          :columns="draftColumns"
          :data-source="drafts"
          :pagination="draftPagination"
          :row-selection="draftRowSelection"
          :scroll="{ y: 280 }"
          :custom-row="buildDraftRow"
          @change="handleDraftTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'rule_code'">
              <span
                class="rule-code-pill"
                :class="{ active: selectedDraftId === record.id }"
              >
                {{ record.rule_code }}
              </span>
            </template>
            <template v-else-if="column.key === 'name'">
              <div class="draft-title">
                {{ record.name || '未命名草稿' }}
              </div>
              <div class="draft-subtitle">
                {{ record.description || '-' }}
              </div>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.status === 'published' ? 'success' : 'processing'">
                {{ record.status === 'published' ? '已发布' : '草稿' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'actions'">
              <div class="draft-actions">
                <a-tooltip :title="isBusinessReadOnly ? '查看规则' : '继续编辑'">
                  <a-button
                    type="text"
                    size="small"
                    @click.stop="selectDraft(record as CustomRuleDraft)"
                  >
                    <template #icon>
                      <EditOutlined />
                    </template>
                  </a-button>
                </a-tooltip>
                <a-tooltip title="复制草稿">
                  <a-button
                    :disabled="isBusinessReadOnly"
                    type="text"
                    size="small"
                    @click.stop="copyDraft(record as CustomRuleDraft)"
                  >
                    <template #icon>
                      <CopyOutlined />
                    </template>
                  </a-button>
                </a-tooltip>
                <a-popconfirm
                  :disabled="isBusinessReadOnly"
                  title="确认删除该草稿？"
                  @confirm="deleteDraft(record as CustomRuleDraft)"
                >
                  <a-button
                    type="text"
                    danger
                    :disabled="isBusinessReadOnly"
                    size="small"
                    @click.stop
                  >
                    <template #icon>
                      <DeleteOutlined />
                    </template>
                  </a-button>
                </a-popconfirm>
              </div>
            </template>
          </template>
        </a-table>
      </article>
    </section>

    <section
      v-show="isStepVisible('step-create')"
      id="step-create"
      class="workspace-panel step-inline-panel"
    >
      <div class="panel-head">
        <div>
          <p class="panel-eyebrow">
            步骤二
          </p>
          <h2 class="panel-title">
            规则创建（抽屉）
          </h2>
        </div>
        <a-button
          :disabled="isBusinessReadOnly"
          type="primary"
          @click="openCreateDrawer"
        >
          <template #icon>
            <PlusOutlined />
          </template>
          新建草稿
        </a-button>
      </div>
      <div class="step-inline-grid">
        <div class="step-inline-card">
          <p class="step-inline-label">
            当前编辑对象
          </p>
          <p class="step-inline-value">
            {{ selectedDraft ? `${selectedDraft.rule_code} ${selectedDraft.name}` : '未选择草稿' }}
          </p>
        </div>
        <div class="step-inline-card">
          <p class="step-inline-label">
            当前执行集合
          </p>
          <p class="step-inline-value">
            {{ effectiveExecutionDraftIds.length }} 条规则
          </p>
        </div>
        <div class="step-inline-card">
          <p class="step-inline-label">
            操作入口
          </p>
          <p class="step-inline-value">
            新建规则通过右侧抽屉完成，创建后可自动加入执行集合。
          </p>
        </div>
      </div>
    </section>

    <a-drawer
      v-model:open="createDrawerVisible"
      title="步骤2：创建规则草稿"
      placement="right"
      :width="560"
    >
      <template #extra>
        <a-switch
          v-model:checked="createAutoJoinExecutionSet"
          checked-children="加入执行集"
          un-checked-children="仅编辑"
        />
      </template>
      <a-form layout="vertical">
        <div class="form-grid">
          <a-form-item
            label="规则名称"
            required
          >
            <a-input
              v-model:value="createForm.name"
              placeholder="例如：出院记录缺少出院带药明细"
            />
          </a-form-item>
          <a-form-item
            label="适用文书"
            required
          >
            <a-select
              v-model:value="createForm.document_type"
              :options="documentTypeOptions"
            />
          </a-form-item>
        </div>
        <div class="form-grid">
          <a-form-item label="病历范围">
            <a-select
              v-model:value="createForm.scene"
              :options="sceneOptions"
            />
          </a-form-item>
          <a-form-item label="复杂度">
            <a-select
              v-model:value="createForm.complexity"
              :options="complexityOptions"
            />
          </a-form-item>
        </div>
        <div class="form-grid">
          <a-form-item label="缺陷级别">
            <a-select
              v-model:value="createForm.defect_level"
              :options="defectLevelOptions"
            />
          </a-form-item>
          <a-form-item label="严重程度">
            <a-select
              v-model:value="createForm.severity"
              :options="severityOptions"
            />
          </a-form-item>
        </div>
        <a-form-item
          label="需求描述"
          required
        >
          <a-textarea
            v-model:value="createForm.source_requirement"
            :rows="5"
            :maxlength="1200"
            show-count
            placeholder="描述你希望 AI 检查的问题边界、证据形式和建议口径。"
          />
        </a-form-item>
      </a-form>
      <template #footer>
        <div class="drawer-footer">
          <a-button @click="createDrawerVisible = false">
            取消
          </a-button>
          <a-button
            :disabled="isBusinessReadOnly"
            type="primary"
            :loading="creatingDraft"
            @click="createDraft"
          >
            创建草稿
          </a-button>
        </div>
      </template>
    </a-drawer>

    <section
      v-if="workspaceMode === 'batch'"
      v-show="isStepVisible('step-prompt')"
      id="step-prompt"
      class="workspace-panel"
    >
      <div class="panel-head">
        <div>
          <p class="panel-eyebrow">
            步骤三
          </p>
          <h2 class="panel-title">
            Prompt 生成与编辑
          </h2>
        </div>
        <div class="panel-actions">
          <a-tag :color="promptReady ? 'success' : 'warning'">
            {{ promptReady ? '就绪' : '待补全' }}
          </a-tag>
          <a-button
            :disabled="!selectedDraft"
            @click="openPromptDrawer"
          >
            <template #icon>
              <EditOutlined />
            </template>
            打开编辑器
          </a-button>
          <a-button
            :disabled="isBusinessReadOnly || !selectedDraft"
            :loading="generatingPrompt"
            @click="generatePromptForDraft"
          >
            <template #icon>
              <RobotOutlined />
            </template>
            AI 生成 Prompt
          </a-button>
        </div>
      </div>

      <div class="prompt-compact">
        <div class="prompt-compact-main">
          <a-tag :color="editorGenerationMode === 'llm' ? 'success' : 'warning'">
            {{ editorGenerationMode === 'llm' ? 'AI生成' : '模板回退' }}
          </a-tag>
          <span class="prompt-compact-text">{{ promptPreviewInline }}</span>
        </div>
        <div
          v-if="editorCheckPoints.length > 0"
          class="prompt-compact-points"
        >
          <a-tag
            v-for="(item, idx) in editorCheckPoints.slice(0, 2)"
            :key="`${idx}-${item}`"
          >
            {{ item }}
          </a-tag>
        </div>
      </div>
    </section>

    <section
      v-else
      id="step-prompt"
      class="workspace-panel"
    >
      <div class="panel-head">
        <div>
          <p class="panel-eyebrow">
            规则设计区
          </p>
          <h2 class="panel-title">
            Prompt 与规则内容
          </h2>
        </div>
        <div class="panel-actions">
          <a-tag :color="promptReady ? 'success' : 'warning'">
            {{ promptReady ? '可发布' : '待补全' }}
          </a-tag>
          <a-button
            :disabled="isBusinessReadOnly || !selectedDraft"
            :loading="generatingPrompt"
            @click="generatePromptForDraft"
          >
            <template #icon>
              <RobotOutlined />
            </template>
            AI 生成 Prompt
          </a-button>
          <a-button
            :disabled="!selectedDraft"
            @click="openPromptDrawer"
          >
            <template #icon>
              <EditOutlined />
            </template>
            打开编辑器
          </a-button>
          <a-button
            type="primary"
            :disabled="isBusinessReadOnly || !selectedDraft"
            :loading="savingDraft"
            @click="saveDraftEditor"
          >
            保存草稿
          </a-button>
        </div>
      </div>

      <div class="design-meta-grid">
        <div class="design-meta-item">
          <span class="design-meta-label">规则编码</span>
          <strong class="design-meta-value">{{ selectedDraft?.rule_code || '-' }}</strong>
        </div>
        <div class="design-meta-item">
          <span class="design-meta-label">规则名称</span>
          <strong class="design-meta-value">{{ editorForm.name || '-' }}</strong>
        </div>
        <div class="design-meta-item">
          <span class="design-meta-label">适用文书</span>
          <strong class="design-meta-value">{{ editorForm.document_type || '-' }}</strong>
        </div>
        <div class="design-meta-item">
          <span class="design-meta-label">病历范围</span>
          <strong class="design-meta-value">{{
            editorForm.scene === 'final' ? '终末病历' : '运行病历'
          }}</strong>
        </div>
      </div>

      <div class="prompt-summary">
        <p class="prompt-summary-title">
          Prompt 摘要
        </p>
        <p class="prompt-summary-text">
          {{ promptPreviewText }}
        </p>
        <div
          v-if="editorCheckPoints.length > 0"
          class="prompt-summary-points"
        >
          <a-tag
            v-for="(item, idx) in editorCheckPoints.slice(0, 4)"
            :key="`${idx}-${item}`"
          >
            {{ item }}
          </a-tag>
        </div>
      </div>
    </section>

    <a-drawer
      v-model:open="promptDrawerVisible"
      title="步骤3：Prompt 生成与编辑"
      placement="right"
      :width="780"
    >
      <template #extra>
        <div class="panel-actions">
          <a-button
            :disabled="isBusinessReadOnly || !selectedDraft"
            :loading="generatingPrompt"
            @click="generatePromptForDraft"
          >
            <template #icon>
              <RobotOutlined />
            </template>
            AI 生成
          </a-button>
          <a-button
            type="primary"
            :disabled="isBusinessReadOnly || !selectedDraft"
            :loading="savingDraft"
            @click="saveDraftEditor"
          >
            保存草稿
          </a-button>
        </div>
      </template>
      <a-alert
        :type="editorGenerationMode === 'llm' ? 'success' : 'warning'"
        show-icon
        :message="
          editorGenerationMode === 'llm' ? '当前 Prompt 来自 AI 生成' : '当前 Prompt 为模板回退'
        "
        :description="editorPromptSummary || '请先选中草稿后生成 Prompt，也可手工编辑。'"
      />
      <div
        v-if="editorCheckPoints.length > 0"
        class="check-point-list mt-10"
      >
        <div class="check-point-title">
          生成检查要点
        </div>
        <div
          v-for="(item, idx) in editorCheckPoints"
          :key="`drawer-${idx}-${item}`"
          class="check-point-item"
        >
          {{ idx + 1 }}. {{ item }}
        </div>
      </div>

      <a-form
        layout="vertical"
        class="mt-10"
      >
        <div class="form-grid">
          <a-form-item
            label="规则名称"
            required
          >
            <a-input
              v-model:value="editorForm.name"
              :disabled="!selectedDraft"
            />
          </a-form-item>
          <a-form-item label="适用文书">
            <a-select
              v-model:value="editorForm.document_type"
              :options="documentTypeOptions"
              :disabled="!selectedDraft"
            />
          </a-form-item>
        </div>
        <a-form-item
          label="规则描述"
          required
        >
          <a-textarea
            v-model:value="editorForm.description"
            :rows="4"
            :disabled="!selectedDraft"
          />
        </a-form-item>
        <a-form-item
          label="Prompt 模板"
          required
        >
          <a-textarea
            v-model:value="editorForm.prompt_template"
            :rows="10"
            :disabled="!selectedDraft"
          />
        </a-form-item>
        <div class="form-grid">
          <a-form-item label="合规示例">
            <a-textarea
              v-model:value="editorForm.positive_example"
              :rows="4"
              :disabled="!selectedDraft"
            />
          </a-form-item>
          <a-form-item label="不合规模例">
            <a-textarea
              v-model:value="editorForm.negative_example"
              :rows="4"
              :disabled="!selectedDraft"
            />
          </a-form-item>
        </div>
      </a-form>
      <template #footer>
        <div class="drawer-footer">
          <a-button @click="promptDrawerVisible = false">
            关闭
          </a-button>
          <a-button
            type="primary"
            :disabled="isBusinessReadOnly || !selectedDraft"
            :loading="savingDraft"
            @click="saveDraftEditor"
          >
            保存草稿
          </a-button>
        </div>
      </template>
    </a-drawer>

    <section
      v-if="workspaceMode === 'batch'"
      v-show="isStepVisible('step-records')"
      id="step-records"
      class="workspace-panel"
    >
      <div class="panel-head">
        <div>
          <p class="panel-eyebrow">
            步骤四
          </p>
          <h2 class="panel-title">
            病历筛选与任务执行
          </h2>
        </div>
        <div class="panel-actions">
          <a-radio-group
            v-model:value="executionMode"
            button-style="solid"
            size="small"
          >
            <a-radio-button value="single">
              单规则
            </a-radio-button>
            <a-radio-button value="multi">
              多规则串行
            </a-radio-button>
          </a-radio-group>
          <a-button
            type="primary"
            :disabled="isBusinessReadOnly || !canRunBatchJob"
            :loading="runningBatchJob"
            @click="runBatchJob"
          >
            <template #icon>
              <PlayCircleOutlined />
            </template>
            发起任务
          </a-button>
          <a-button
            :disabled="!activeBatchJob"
            @click="refreshActiveBatchJob"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            刷新任务
          </a-button>
          <a-button
            :disabled="!activeBatchJob"
            @click="exportActiveBatchJob('xlsx')"
          >
            导出
          </a-button>
        </div>
      </div>

      <div class="execution-tips">
        <a-alert
          show-icon
          type="info"
          :message="
            executionMode === 'single' ? '当前模式：单规则批量' : '当前模式：多规则串行批量'
          "
          :description="executionTipText"
        />
      </div>

      <div class="record-filter-grid">
        <a-select
          v-model:value="recordFilters.scope"
          :options="scopeOptions"
        />
        <a-select
          v-model:value="recordFilters.department"
          allow-clear
          show-search
          :options="departmentOptions"
          placeholder="科室"
          @change="handleDepartmentChange"
        />
        <a-select
          v-model:value="recordFilters.doctor"
          allow-clear
          show-search
          :options="doctorOptions"
          placeholder="医生"
        />
        <a-select
          v-model:value="recordFilters.date_field"
          :options="dateFieldOptions"
        />
        <a-range-picker v-model:value="recordFilters.dateRange" />
        <a-input
          v-model:value="recordFilters.keyword"
          allow-clear
          placeholder="关键词：患者/住院号/visit"
          @press-enter="searchRecords"
        />
        <a-button
          :loading="recordLoading"
          @click="searchRecords"
        >
          查询病历
        </a-button>
      </div>

      <a-form
        layout="vertical"
        class="advanced-grid"
      >
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
      </a-form>

      <div class="record-toolbar">
        <span>已选择 {{ selectedRecordKeys.length }} 条病历</span>
        <div class="panel-actions">
          <a-button
            size="small"
            @click="selectCurrentPageRecords"
          >
            全选当前页
          </a-button>
          <a-button
            size="small"
            @click="clearSelectedRecords"
          >
            清空
          </a-button>
        </div>
      </div>

      <a-table
        row-key="record_key"
        size="small"
        :loading="recordLoading"
        :columns="recordColumns"
        :data-source="records"
        :pagination="recordPagination"
        :row-selection="recordRowSelection"
        :scroll="{ x: 1100, y: 320 }"
        @change="handleRecordTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'scope'">
            <a-tag
              :color="
                record.scope === 'final' ? 'blue' : record.scope === 'running' ? 'gold' : 'default'
              "
            >
              {{ scopeLabelMap[record.scope] }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button
              type="link"
              size="small"
              :disabled="isBusinessReadOnly || !selectedDraft"
              :loading="testingSingleRecordId === record.record_id"
              @click="runSingleTest(record as CustomRuleWorkspaceRecord)"
            >
              单条质控
            </a-button>
          </template>
        </template>
      </a-table>

      <div class="batch-shell">
        <div class="batch-shell-head">
          <div>
            <p class="panel-eyebrow">
              批量任务
            </p>
            <h3 class="batch-shell-title">
              任务列表
            </h3>
          </div>
          <a-button
            size="small"
            :loading="batchJobLoading"
            @click="loadBatchJobs"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            刷新任务
          </a-button>
        </div>
        <div class="batch-filters">
          <a-input
            v-model:value="batchJobQuery.keyword"
            allow-clear
            placeholder="搜索规则名称/编码/任务ID"
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
            @change="searchBatchJobs"
          />
          <a-select
            v-model:value="batchJobQuery.scope"
            allow-clear
            placeholder="病历范围"
            :options="scopeOptions"
            @change="searchBatchJobs"
          />
        </div>

        <a-table
          row-key="id"
          size="small"
          :loading="batchJobLoading"
          :columns="batchJobColumns"
          :data-source="batchJobs"
          :pagination="batchJobPagination"
          :scroll="{ x: 960 }"
          @change="handleBatchJobTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'rule'">
              <div class="batch-rule-name">
                {{ record.rule_name || record.rule_code }}
              </div>
              <div class="batch-rule-meta">
                {{ record.execution_mode === 'multi' ? '多规则串行' : '单规则' }} ·
                {{ record.rule_count || 1 }} 条规则
              </div>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :class="`job-status job-status--${record.status}`">
                {{ jobStatusText(record.status) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'progress'">
              <div class="job-progress-text">
                {{ formatJobProgress(record) }}
              </div>
            </template>
            <template v-else-if="column.key === 'created_at'">
              <span class="cell-muted">{{ formatDateTime(record.created_at) }}</span>
            </template>
            <template v-else-if="column.key === 'actions'">
              <div class="batch-actions">
                <a-button
                  size="small"
                  @click="openBatchJob(record as CustomRuleBatchJob)"
                >
                  查看
                </a-button>
                <a-button
                  :disabled="isBusinessReadOnly"
                  v-if="record.cancellable"
                  size="small"
                  danger
                  :loading="cancellingBatchJobId === record.id"
                  @click="cancelBatchJob(record.id)"
                >
                  停止
                </a-button>
                <a-button
                  :disabled="isBusinessReadOnly"
                  v-else
                  size="small"
                  :loading="retryingBatchJobId === record.id"
                  @click="retryBatchJob(record.id)"
                >
                  重试
                </a-button>
              </div>
            </template>
          </template>
        </a-table>
      </div>

      <div class="result-grid">
        <div class="result-panel">
          <h3>任务概览</h3>
          <a-empty
            v-if="!activeBatchJob"
            description="选择任务后查看"
          />
          <template v-else>
            <div class="result-kpis">
              <div class="result-kpi">
                <span>状态</span>
                <strong>{{ jobStatusText(activeBatchJob.status) }}</strong>
              </div>
              <div class="result-kpi">
                <span>规则数</span>
                <strong>{{ activeBatchJob.rule_count || 1 }}</strong>
              </div>
              <div class="result-kpi">
                <span>病历数</span>
                <strong>{{
                  activeBatchJob.summary?.total_records || activeBatchJob.total_records || 0
                }}</strong>
              </div>
              <div class="result-kpi">
                <span>成功</span>
                <strong>{{
                  activeBatchJob.summary?.success_count || activeBatchJob.success_count || 0
                }}</strong>
              </div>
              <div class="result-kpi">
                <span>失败</span>
                <strong>{{
                  activeBatchJob.summary?.failed_count || activeBatchJob.failed_count || 0
                }}</strong>
              </div>
            </div>
            <p class="result-text">
              进度：{{ formatJobProgress(activeBatchJob) }}
            </p>
            <p
              v-if="activeBatchJob.error_message"
              class="result-text result-text--danger"
            >
              错误：{{ activeBatchJob.error_message }}
            </p>
          </template>
        </div>

        <div class="result-panel">
          <h3>按规则汇总</h3>
          <a-empty
            v-if="ruleResultRows.length === 0"
            description="暂无规则汇总"
          />
          <a-table
            v-else
            row-key="rule_code"
            size="small"
            :pagination="false"
            :columns="ruleResultColumns"
            :data-source="ruleResultRows"
            :scroll="{ y: 220 }"
          />
        </div>

        <div class="result-panel">
          <h3>按病历明细</h3>
          <a-empty
            v-if="recordResultRows.length === 0"
            description="暂无病历明细"
          />
          <a-table
            v-else
            row-key="record_id"
            size="small"
            :pagination="false"
            :columns="recordResultColumns"
            :data-source="recordResultRows"
            :scroll="{ y: 220, x: 760 }"
          />
        </div>

        <div class="result-panel">
          <h3>失败明细</h3>
          <a-empty
            v-if="failedResultRows.length === 0"
            description="暂无失败记录"
          />
          <a-table
            v-else
            row-key="record_id"
            size="small"
            :pagination="false"
            :columns="failedResultColumns"
            :data-source="failedResultRows"
            :scroll="{ y: 220, x: 760 }"
          />
        </div>
      </div>
    </section>
  </div>
</template>
<script setup lang="ts">
import { useBusinessReadAccess } from '@/composables/useBusinessReadAccess'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import {
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SearchOutlined,
} from '@ant-design/icons-vue'
import {
  cancelWorkspaceBatchJob,
  createWorkspaceBatchJob,
  createWorkspaceDraft,
  deleteWorkspaceDraft,
  exportWorkspaceBatchJob,
  generateWorkspaceDraftPrompt,
  getWorkspaceBatchJob,
  getWorkspaceRecordFilters,
  getWorkspaceRecords,
  listWorkspaceBatchJobs,
  listWorkspaceDrafts,
  publishWorkspaceDraft,
  retryWorkspaceBatchJob,
  runWorkspaceSingleTest,
  updateWorkspaceDraft,
} from '@/services/custom-rule-workspace-service'
import {
  STANDARD_DOCUMENT_TYPE_OPTIONS,
  defaultDocumentTypeByScene,
  normalizeWorkspaceDocumentType,
} from '@/constants/standard-document-types'
import type {
  CustomRuleBatchJob,
  CustomRuleBatchJobProgress,
  CustomRuleBatchJobQuery,
  CustomRuleBatchJobRuleResult,
  CustomRuleDraft,
  CustomRuleDraftPayload,
  CustomRuleSingleTestResult,
  CustomRuleWorkspaceRecord,
  CustomRuleWorkspaceRecordRef,
  WorkspaceDraftStatus,
  WorkspaceScope,
  WorkspaceSeverity,
} from '@/types/custom-rule-workspace'

type DateRangeValue = [Dayjs, Dayjs] | null

type StepStatus = 'pending' | 'ready' | 'running' | 'done'

const { isBusinessReadOnly } = useBusinessReadAccess()

const JOB_POLL_INTERVAL_MS = 3000

const draftLoading = ref(false)
const creatingDraft = ref(false)
const savingDraft = ref(false)
const generatingPrompt = ref(false)
const publishingDraft = ref(false)
const runningBatchJob = ref(false)
const testingSingleRecordId = ref('')

const drafts = ref<CustomRuleDraft[]>([])
const selectedDraftId = ref('')
const selectedDraftIds = ref<string[]>([])
const createAutoJoinExecutionSet = ref(true)
const createDrawerVisible = ref(false)
const promptDrawerVisible = ref(false)
const workspaceMode = ref<'batch' | 'design'>('batch')

const singleResult = ref<CustomRuleSingleTestResult | null>(null)

const draftQuery = reactive({
  keyword: '',
  status: undefined as WorkspaceDraftStatus | undefined,
})

const draftPagination = reactive({
  current: 1,
  pageSize: 8,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

const createForm = reactive({
  name: '',
  source_requirement: '',
  document_type: defaultDocumentTypeByScene('running'),
  scene: 'running' as 'running' | 'final',
  severity: 'major' as WorkspaceSeverity,
  defect_level: '一般缺陷',
  complexity: '中复杂度',
})

const editorForm = reactive({
  name: '',
  description: '',
  prompt_template: '',
  source_requirement: '',
  document_type: defaultDocumentTypeByScene('running'),
  scene: 'running' as 'running' | 'final',
  severity: 'major' as WorkspaceSeverity,
  defect_level: '一般缺陷',
  complexity: '中复杂度',
  generation_mode: 'fallback_template' as 'llm' | 'fallback_template',
  positive_example: '',
  negative_example: '',
  check_logic: {} as Record<string, unknown>,
})

const editorPromptSummary = ref('')
const editorCheckPoints = ref<string[]>([])

const draftStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已发布', value: 'published' },
]

const documentTypeOptions = STANDARD_DOCUMENT_TYPE_OPTIONS

const sceneOptions = [
  { label: '运行病历', value: 'running' },
  { label: '终末病历', value: 'final' },
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

const selectedDraft = computed(
  () => drafts.value.find((item) => item.id === selectedDraftId.value) || null,
)

const executionMode = ref<'single' | 'multi'>('single')

const effectiveExecutionDraftIds = computed(() => {
  if (executionMode.value === 'single') {
    return selectedDraftId.value ? [selectedDraftId.value] : []
  }
  if (selectedDraftIds.value.length > 0) {
    return selectedDraftIds.value
  }
  return selectedDraftId.value ? [selectedDraftId.value] : []
})

const promptReady = computed(() => {
  return Boolean(
    editorForm.name.trim() && editorForm.description.trim() && editorForm.prompt_template.trim(),
  )
})

const workspaceModeTip = computed(() => {
  if (workspaceMode.value === 'batch') {
    return '面向执行：规则选择、病历筛选、任务执行与结果复盘在同一屏完成。'
  }
  return '面向设计：聚焦规则与 Prompt 调整，完整编辑放入右侧抽屉，避免主页面拥挤。'
})

const promptPreviewText = computed(() => {
  const text = editorForm.prompt_template.trim()
  if (!text) return '尚未填写 Prompt 模板，可点击“打开编辑器”补全。'
  return text.length > 220 ? `${text.slice(0, 220)}...` : text
})

const promptPreviewInline = computed(() => {
  const text = editorForm.prompt_template.replace(/\s+/g, ' ').trim()
  if (!text) return '尚未填写 Prompt 模板'
  return text.length > 88 ? `${text.slice(0, 88)}...` : text
})

const editorGenerationMode = computed(
  () => editorForm.generation_mode || selectedDraft.value?.generation_mode || 'fallback_template',
)

const scopeLabelMap: Record<WorkspaceScope, string> = {
  all: '全部病历',
  running: '运行病历',
  final: '终末病历',
}

const scopeOptions = [
  { label: scopeLabelMap.all, value: 'all' },
  { label: scopeLabelMap.running, value: 'running' },
  { label: scopeLabelMap.final, value: 'final' },
]

const dateFieldOptions = [
  { label: '按入院日期', value: 'admission' },
  { label: '按出院日期', value: 'discharge' },
]

const recordFilters = reactive({
  scope: 'all' as WorkspaceScope,
  department: undefined as string | undefined,
  doctor: undefined as string | undefined,
  date_field: 'admission' as 'admission' | 'discharge',
  dateRange: null as DateRangeValue,
  keyword: '',
})

const departmentOptions = ref<Array<{ label: string; value: string }>>([])
const doctorOptions = ref<Array<{ label: string; value: string }>>([])
const recordLoading = ref(false)
const records = ref<CustomRuleWorkspaceRecord[]>([])
const selectedRecordKeys = ref<string[]>([])
const selectedRecordRefByKey = new Map<string, CustomRuleWorkspaceRecordRef>()
const invalidSelectedRecordKeys = new Set<string>()

const recordPagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条病历`,
})

const advancedParams = reactive({
  temperature: 0.2,
  top_p: 0.9,
  max_tokens: 4096,
})

const recordColumns: TableColumnsType<CustomRuleWorkspaceRecord> = [
  { title: '患者', dataIndex: 'patient_name', key: 'patient_name', width: 120 },
  { title: '住院号/visit', dataIndex: 'visit_id', key: 'visit_id', width: 140 },
  { title: '病历范围', dataIndex: 'scope', key: 'scope', width: 100 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 140 },
  { title: '医生', dataIndex: 'doctor', key: 'doctor', width: 140 },
  { title: '入院日期', dataIndex: 'admission_date', key: 'admission_date', width: 120 },
  { title: '出院日期', dataIndex: 'discharge_date', key: 'discharge_date', width: 120 },
  { title: '操作', key: 'actions', width: 110, fixed: 'right' as const },
]

const recordRowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRecordKeys.value,
  preserveSelectedRowKeys: true,
  onChange: (keys: Array<string | number>) => {
    const nextKeys = keys.map((item) => String(item))
    const nextKeySet = new Set(nextKeys)
    for (const record of records.value) {
      const key = String(record.record_key || '').trim()
      if (!key) continue
      if (nextKeySet.has(key)) {
        cacheSelectedRecordRef(record)
      } else {
        selectedRecordRefByKey.delete(key)
        invalidSelectedRecordKeys.delete(key)
      }
    }
    selectedRecordKeys.value = nextKeys
  },
}))

const draftColumns: TableColumnsType<CustomRuleDraft> = [
  { title: '编码', dataIndex: 'rule_code', key: 'rule_code', width: 120 },
  { title: '规则', dataIndex: 'name', key: 'name' },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '操作', key: 'actions', width: 120, fixed: 'right' },
]

const draftRowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedDraftIds.value,
  onChange: (keys: Array<string | number>) => {
    selectedDraftIds.value = keys.map((item) => String(item))
  },
}))

function buildDraftRow(record: CustomRuleDraft) {
  return {
    class: record.id === selectedDraftId.value ? 'draft-row-active' : '',
    onClick: () => {
      selectDraft(record)
    },
  }
}

function getExamplesFromDraft(draft: CustomRuleDraft): { positive: string; negative: string } {
  const examples = Array.isArray(draft.examples) ? draft.examples : []
  const positive = examples.find((item) => String(item.title || '').includes('合规'))?.content || ''
  const negative =
    examples.find((item) => String(item.title || '').includes('不合规'))?.content || ''
  return { positive, negative }
}

function hydrateEditorFromDraft(draft: CustomRuleDraft) {
  const examples = getExamplesFromDraft(draft)
  editorForm.name = draft.name || ''
  editorForm.description = draft.description || ''
  editorForm.prompt_template = draft.prompt_template || ''
  editorForm.source_requirement = draft.source_requirement || ''
  editorForm.document_type = normalizeWorkspaceDocumentType(
    draft.document_type || '',
    defaultDocumentTypeByScene(draft.scene || 'running'),
  )
  editorForm.scene = draft.scene || 'running'
  editorForm.severity = draft.severity || 'major'
  editorForm.defect_level = draft.defect_level || '一般缺陷'
  editorForm.complexity = draft.complexity || '中复杂度'
  editorForm.generation_mode = draft.generation_mode || 'fallback_template'
  editorForm.positive_example = examples.positive
  editorForm.negative_example = examples.negative
  editorForm.check_logic = (draft.check_logic || {}) as Record<string, unknown>
  editorPromptSummary.value = String((draft.check_logic || {}).last_prompt_summary || '')
  editorCheckPoints.value = Array.isArray((draft.check_logic || {}).generated_check_points)
    ? ((draft.check_logic || {}).generated_check_points as string[])
    : []
}

function mapDefectLevelToSeverity(defectLevel: string): WorkspaceSeverity {
  if (defectLevel === '严重缺陷') return 'critical'
  if (defectLevel === '提示性缺陷') return 'minor'
  return 'major'
}

function formatDateTime(value?: string | Date | null): string {
  if (!value) return '-'
  const dt = dayjs(value)
  if (!dt.isValid()) return String(value)
  return dt.format('YYYY-MM-DD HH:mm:ss')
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
    if (!response.success || !response.data) {
      throw new Error(response.message || '获取草稿列表失败')
    }
    drafts.value = response.data.items
    draftPagination.total = response.data.total

    if (drafts.value.length === 0) {
      selectedDraftId.value = ''
      selectedDraftIds.value = []
      return
    }

    const draftIdSet = new Set(drafts.value.map((item) => item.id))
    if (!selectedDraftId.value || !draftIdSet.has(selectedDraftId.value)) {
      selectedDraftId.value = drafts.value[0].id
    }
    selectedDraftIds.value = selectedDraftIds.value.filter((id) => draftIdSet.has(id))
    if (selectedDraftIds.value.length === 0 && selectedDraftId.value) {
      selectedDraftIds.value = [selectedDraftId.value]
    }

    const currentDraft = drafts.value.find((item) => item.id === selectedDraftId.value)
    if (currentDraft) {
      hydrateEditorFromDraft(currentDraft)
    }
  } catch (error: any) {
    message.error(error?.message || '获取草稿列表失败')
  } finally {
    draftLoading.value = false
  }
}

function searchDrafts() {
  draftPagination.current = 1
  void loadDrafts()
}

function handleDraftTableChange(pagination: { current?: number; pageSize?: number }) {
  draftPagination.current = pagination.current || 1
  draftPagination.pageSize = pagination.pageSize || 8
  void loadDrafts()
}

function selectDraft(record: CustomRuleDraft) {
  selectedDraftId.value = record.id
  hydrateEditorFromDraft(record)
  singleResult.value = null
}

function openCreateDrawer() {
  if (isBusinessReadOnly.value) return
  createDrawerVisible.value = true
}

function openPromptDrawer() {
  if (!selectedDraft.value) {
    message.warning('请先选择草稿')
    return
  }
  promptDrawerVisible.value = true
}
async function createDraft() {
  if (isBusinessReadOnly.value) return
  const name = createForm.name.trim()
  const requirement = createForm.source_requirement.trim()
  if (!name) {
    message.warning('请先填写规则名称')
    return
  }
  if (!requirement) {
    message.warning('请先填写需求描述')
    return
  }

  const normalizedDocumentType = normalizeWorkspaceDocumentType(
    createForm.document_type,
    defaultDocumentTypeByScene(createForm.scene),
  )
  creatingDraft.value = true
  try {
    const payload: CustomRuleDraftPayload = {
      name,
      description: requirement,
      source_requirement: requirement,
      document_type: normalizedDocumentType,
      severity: createForm.severity || mapDefectLevelToSeverity(createForm.defect_level),
      defect_level: createForm.defect_level,
      complexity: createForm.complexity,
      scene: createForm.scene,
      applicable_documents: [normalizedDocumentType],
      generation_mode: 'fallback_template',
      check_logic: {
        source: 'custom_rule_workspace',
        scene: createForm.scene,
        applicable_documents: [normalizedDocumentType],
      },
    }
    const response = await createWorkspaceDraft(payload)
    if (!response.success || !response.data) {
      throw new Error(response.message || '创建草稿失败')
    }
    message.success(`草稿 ${response.data.rule_code} 已创建`)
    selectedDraftId.value = response.data.id
    if (createAutoJoinExecutionSet.value) {
      selectedDraftIds.value = Array.from(new Set([...selectedDraftIds.value, response.data.id]))
    }
    createDrawerVisible.value = false
    await loadDrafts()
    selectDraft(response.data)
  } catch (error: any) {
    message.error(error?.message || '创建草稿失败')
  } finally {
    creatingDraft.value = false
  }
}

function buildEditorExamples() {
  const examples: Array<{ title: string; content: string }> = []
  if (editorForm.positive_example.trim()) {
    examples.push({ title: '合规示例', content: editorForm.positive_example.trim() })
  }
  if (editorForm.negative_example.trim()) {
    examples.push({ title: '不合规模例', content: editorForm.negative_example.trim() })
  }
  return examples
}

function validateEditorReady(showWarning = true): boolean {
  const ready = Boolean(
    editorForm.name.trim() && editorForm.description.trim() && editorForm.prompt_template.trim(),
  )
  if (!ready && showWarning) {
    message.warning('规则名称、描述、Prompt 均不能为空')
  }
  return ready
}

async function saveDraftEditor() {
  if (isBusinessReadOnly.value) return
  if (!selectedDraft.value) {
    message.warning('请先选择草稿')
    return false
  }
  if (!validateEditorReady()) {
    return false
  }
  savingDraft.value = true
  try {
    const normalizedDocumentType = normalizeWorkspaceDocumentType(
      editorForm.document_type,
      defaultDocumentTypeByScene(editorForm.scene),
    )
    const response = await updateWorkspaceDraft(selectedDraft.value.id, {
      name: editorForm.name.trim(),
      description: editorForm.description.trim(),
      source_requirement: editorForm.source_requirement || editorForm.description,
      prompt_template: editorForm.prompt_template.trim(),
      document_type: normalizedDocumentType,
      scene: editorForm.scene,
      severity: editorForm.severity,
      defect_level: editorForm.defect_level,
      complexity: editorForm.complexity,
      generation_mode: editorForm.generation_mode,
      examples: buildEditorExamples(),
      check_logic: {
        ...(editorForm.check_logic || {}),
        last_prompt_summary: editorPromptSummary.value,
        generated_check_points: editorCheckPoints.value,
      },
      applicable_documents: [normalizedDocumentType],
    })
    if (!response.success || !response.data) {
      throw new Error(response.message || '保存草稿失败')
    }
    const next = response.data
    drafts.value = drafts.value.map((item) => (item.id === next.id ? next : item))
    selectDraft(next)
    message.success('草稿已保存')
    return true
  } catch (error: any) {
    message.error(error?.message || '保存草稿失败')
    return false
  } finally {
    savingDraft.value = false
  }
}

async function generatePromptForDraft() {
  if (isBusinessReadOnly.value) return
  if (!selectedDraft.value) {
    message.warning('请先选择草稿')
    return
  }
  generatingPrompt.value = true
  try {
    const saved = await saveDraftEditor()
    if (!saved) return
    const response = await generateWorkspaceDraftPrompt(selectedDraft.value.id)
    if (!response.success || !response.data) {
      throw new Error(response.message || '生成 Prompt 失败')
    }
    const { draft, prompt_result: promptResult } = response.data
    drafts.value = drafts.value.map((item) => (item.id === draft.id ? draft : item))
    selectDraft(draft)
    editorPromptSummary.value = promptResult.summary || ''
    editorCheckPoints.value = promptResult.check_points || []
    message.success(
      promptResult.generation_mode === 'llm' ? 'Prompt 生成成功' : '已回退模板 Prompt',
    )
  } catch (error: any) {
    message.error(error?.message || '生成 Prompt 失败')
  } finally {
    generatingPrompt.value = false
  }
}

async function copyDraft(record: CustomRuleDraft) {
  if (isBusinessReadOnly.value) return
  const normalizedDocumentType = normalizeWorkspaceDocumentType(
    record.document_type,
    defaultDocumentTypeByScene(record.scene || 'running'),
  )
  try {
    const response = await createWorkspaceDraft({
      name: `${record.name}-副本`,
      description: record.description,
      source_requirement: record.source_requirement,
      prompt_template: record.prompt_template,
      document_type: normalizedDocumentType,
      severity: record.severity,
      defect_level: record.defect_level,
      complexity: record.complexity,
      scene: record.scene,
      generation_mode: record.generation_mode,
      applicable_documents: [normalizedDocumentType],
      examples: record.examples,
      check_logic: record.check_logic,
    })
    if (!response.success || !response.data) {
      throw new Error(response.message || '复制草稿失败')
    }
    message.success('草稿已复制')
    selectedDraftId.value = response.data.id
    selectedDraftIds.value = Array.from(new Set([...selectedDraftIds.value, response.data.id]))
    await loadDrafts()
  } catch (error: any) {
    message.error(error?.message || '复制草稿失败')
  }
}

async function deleteDraft(record: CustomRuleDraft) {
  if (isBusinessReadOnly.value) return
  try {
    const response = await deleteWorkspaceDraft(record.id)
    if (!response.success) {
      throw new Error(response.message || '删除草稿失败')
    }
    message.success('草稿已删除')
    if (selectedDraftId.value === record.id) {
      selectedDraftId.value = ''
    }
    selectedDraftIds.value = selectedDraftIds.value.filter((id) => id !== record.id)
    await loadDrafts()
  } catch (error: any) {
    message.error(error?.message || '删除草稿失败')
  }
}

async function publishDraftById(draftId: string) {
  if (isBusinessReadOnly.value) return
  publishingDraft.value = true
  try {
    const response = await publishWorkspaceDraft(draftId)
    if (!response.success || !response.data) {
      throw new Error(response.message || '发布失败')
    }
    message.success(`发布成功：${response.data.rule_code}`)
    await loadDrafts()
  } catch (error: any) {
    message.error(error?.message || '发布失败')
  } finally {
    publishingDraft.value = false
  }
}

async function loadRecordFilters() {
  const response = await getWorkspaceRecordFilters({
    scope: recordFilters.scope,
    department: recordFilters.department,
  })
  if (!response.success || !response.data) {
    throw new Error(response.message || '获取筛选项失败')
  }
  departmentOptions.value = (response.data.departments || []).map((item) => ({
    label: item,
    value: item,
  }))
  doctorOptions.value = (response.data.doctors || []).map((item) => ({
    label: item,
    value: item,
  }))
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
    if (!response.success || !response.data) {
      throw new Error(response.message || '获取病历列表失败')
    }
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

async function handleDepartmentChange() {
  recordFilters.doctor = undefined
  await loadRecordFilters()
}

function handleRecordTableChange(pagination: { current?: number; pageSize?: number }) {
  recordPagination.current = pagination.current || 1
  recordPagination.pageSize = pagination.pageSize || 20
  void loadRecords()
}

function selectCurrentPageRecords() {
  if (records.value.some((item) => !String(item.record_key || '').trim())) {
    message.error('当前页存在缺少稳定病历标识的数据，无法加入批量任务')
    return
  }
  const nextKeys = new Set(selectedRecordKeys.value)
  for (const record of records.value) {
    const key = String(record.record_key).trim()
    nextKeys.add(key)
    cacheSelectedRecordRef(record)
  }
  selectedRecordKeys.value = Array.from(nextKeys)
}

function clearSelectedRecords() {
  selectedRecordKeys.value = []
  selectedRecordRefByKey.clear()
  invalidSelectedRecordKeys.clear()
}

function normalizeWorkspaceRecordRef(
  record: Pick<CustomRuleWorkspaceRecord, 'institute_id' | 'patient_id' | 'visit_id'>,
): CustomRuleWorkspaceRecordRef | null {
  const recordRef = {
    institute_id: String(record.institute_id || '').trim(),
    patient_id: String(record.patient_id || '').trim(),
    visit_id: String(record.visit_id || '').trim(),
  }
  return recordRef.institute_id && recordRef.patient_id && recordRef.visit_id ? recordRef : null
}

function workspaceRecordRefKey(recordRef: CustomRuleWorkspaceRecordRef): string {
  return JSON.stringify([recordRef.institute_id, recordRef.patient_id, recordRef.visit_id])
}

function cacheSelectedRecordRef(record: CustomRuleWorkspaceRecord) {
  const key = String(record.record_key || '').trim()
  if (!key) return
  const recordRef = normalizeWorkspaceRecordRef(record)
  const current = selectedRecordRefByKey.get(key)
  if (
    !recordRef ||
    (current && workspaceRecordRefKey(current) !== workspaceRecordRefKey(recordRef))
  ) {
    selectedRecordRefByKey.delete(key)
    invalidSelectedRecordKeys.add(key)
    return
  }
  selectedRecordRefByKey.set(key, recordRef)
  invalidSelectedRecordKeys.delete(key)
}

function buildSelectedRecordRefs():
  | { success: true; recordRefs: CustomRuleWorkspaceRecordRef[] }
  | { success: false; message: string } {
  const recordRefs: CustomRuleWorkspaceRecordRef[] = []
  const ownerByRef = new Map<string, string>()
  for (const key of selectedRecordKeys.value) {
    const recordRef = selectedRecordRefByKey.get(key)
    if (invalidSelectedRecordKeys.has(key) || !recordRef) {
      return { success: false, message: '所选病历身份不完整或映射已失效，请刷新病历列表后重试' }
    }
    const refKey = workspaceRecordRefKey(recordRef)
    const existingOwner = ownerByRef.get(refKey)
    if (existingOwner && existingOwner !== key) {
      return { success: false, message: '所选病历存在重复身份映射，已停止创建任务' }
    }
    ownerByRef.set(refKey, key)
    recordRefs.push({ ...recordRef })
  }
  return { success: true, recordRefs }
}

async function runSingleTest(record: CustomRuleWorkspaceRecord) {
  if (isBusinessReadOnly.value) return
  if (!selectedDraft.value) {
    message.warning('请先选择草稿规则')
    return
  }
  testingSingleRecordId.value = record.record_id
  try {
    const saved = await saveDraftEditor()
    if (!saved) return
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
    if (!response.success || !response.data) {
      throw new Error(response.message || '单病历测试失败')
    }
    singleResult.value = response.data
    message.success('单病历测试完成')
  } catch (error: any) {
    message.error(error?.message || '单病历测试失败')
  } finally {
    testingSingleRecordId.value = ''
  }
}
const batchJobLoading = ref(false)
const batchJobs = ref<CustomRuleBatchJob[]>([])
const activeBatchJob = ref<CustomRuleBatchJob | null>(null)
const activeBatchJobId = ref('')
const cancellingBatchJobId = ref('')
const retryingBatchJobId = ref('')

const batchJobQuery = reactive({
  keyword: '',
  status: undefined as CustomRuleBatchJobQuery['status'],
  scope: undefined as WorkspaceScope | undefined,
})

const batchJobPagination = reactive({
  current: 1,
  pageSize: 5,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 个任务`,
})

const batchJobStatusOptions = [
  { label: '排队中', value: 'queued' },
  { label: '执行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已失败', value: 'failed' },
  { label: '已取消', value: 'canceled' },
]

const batchJobColumns: TableColumnsType<CustomRuleBatchJob> = [
  { title: '任务', key: 'rule', width: 280 },
  { title: '范围', dataIndex: 'scope', key: 'scope', width: 100 },
  { title: '进度', key: 'progress', width: 280 },
  { title: '状态', key: 'status', width: 90 },
  { title: '创建时间', key: 'created_at', width: 180 },
  { title: '操作', key: 'actions', width: 170, fixed: 'right' },
]

let batchJobPollTimer: number | null = null

function stopBatchJobPolling() {
  if (batchJobPollTimer !== null) {
    window.clearInterval(batchJobPollTimer)
    batchJobPollTimer = null
  }
}

function startBatchJobPolling(jobId: string) {
  stopBatchJobPolling()
  batchJobPollTimer = window.setInterval(async () => {
    await Promise.all([fetchBatchJobDetail(jobId, true), loadBatchJobs()])
    const current = activeBatchJob.value
    if (!current || !['queued', 'running'].includes(current.status)) {
      stopBatchJobPolling()
    }
  }, JOB_POLL_INTERVAL_MS)
}

async function loadBatchJobs() {
  batchJobLoading.value = true
  try {
    const response = await listWorkspaceBatchJobs({
      q: batchJobQuery.keyword || undefined,
      status: batchJobQuery.status,
      scope: batchJobQuery.scope,
      page: batchJobPagination.current,
      page_size: batchJobPagination.pageSize,
    })
    if (!response.success || !response.data) {
      throw new Error(response.message || '获取批量任务失败')
    }
    batchJobs.value = response.data.items
    batchJobPagination.total = response.data.total
    if (activeBatchJobId.value) {
      const found = batchJobs.value.find((item) => item.id === activeBatchJobId.value)
      if (found) {
        activeBatchJob.value = {
          ...found,
          ...activeBatchJob.value,
        }
      }
    }
  } catch (error: any) {
    message.error(error?.message || '获取批量任务失败')
  } finally {
    batchJobLoading.value = false
  }
}

function searchBatchJobs() {
  batchJobPagination.current = 1
  void loadBatchJobs()
}

function handleBatchJobTableChange(pagination: { current?: number; pageSize?: number }) {
  batchJobPagination.current = pagination.current || 1
  batchJobPagination.pageSize = pagination.pageSize || 5
  void loadBatchJobs()
}

async function fetchBatchJobDetail(jobId: string, silent = false) {
  try {
    const response = await getWorkspaceBatchJob(jobId)
    if (!response.success || !response.data) {
      throw new Error(response.message || '获取任务详情失败')
    }
    activeBatchJob.value = response.data
    activeBatchJobId.value = response.data.id
    return response.data
  } catch (error: any) {
    if (!silent) {
      message.error(error?.message || '获取任务详情失败')
    }
    return null
  }
}

async function openBatchJob(job: CustomRuleBatchJob) {
  activeBatchJobId.value = job.id
  const detail = await fetchBatchJobDetail(job.id)
  if (detail && ['queued', 'running'].includes(detail.status)) {
    startBatchJobPolling(job.id)
  } else {
    stopBatchJobPolling()
  }
}

async function cancelBatchJob(jobId: string) {
  if (isBusinessReadOnly.value) return
  if (!jobId || cancellingBatchJobId.value) return
  cancellingBatchJobId.value = jobId
  try {
    const response = await cancelWorkspaceBatchJob(jobId)
    if (!response.success || !response.data) {
      throw new Error(response.message || '取消任务失败')
    }
    message.success('任务已取消')
    await Promise.all([loadBatchJobs(), fetchBatchJobDetail(jobId, true)])
    stopBatchJobPolling()
  } catch (error: any) {
    message.error(error?.message || '取消任务失败')
  } finally {
    cancellingBatchJobId.value = ''
  }
}

async function retryBatchJob(jobId: string) {
  if (isBusinessReadOnly.value) return
  if (!jobId || retryingBatchJobId.value) return
  retryingBatchJobId.value = jobId
  try {
    const response = await retryWorkspaceBatchJob(jobId)
    if (!response.success || !response.data) {
      throw new Error(response.message || '重试任务失败')
    }
    message.success('任务已重新入队')
    await Promise.all([loadBatchJobs(), fetchBatchJobDetail(jobId, true)])
    startBatchJobPolling(jobId)
  } catch (error: any) {
    message.error(error?.message || '重试任务失败')
  } finally {
    retryingBatchJobId.value = ''
  }
}

async function refreshActiveBatchJob() {
  if (!activeBatchJobId.value) {
    message.info('请先在任务列表选择一个任务')
    return
  }
  await Promise.all([fetchBatchJobDetail(activeBatchJobId.value), loadBatchJobs()])
}

async function exportActiveBatchJob(format: 'xlsx' | 'csv') {
  if (!activeBatchJob.value) {
    message.info('请先选择任务')
    return
  }
  const response = await exportWorkspaceBatchJob({
    job_id: activeBatchJob.value.id,
    format,
  })
  if (!response.success || !response.data) {
    message.error(response.message || '导出任务失败')
    return
  }
  const blob = response.data
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `custom-rule-batch-${activeBatchJob.value.id}.${format}`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  window.URL.revokeObjectURL(url)
  message.success('导出任务已开始下载')
}

function jobStatusText(status?: string): string {
  if (status === 'queued') return '排队中'
  if (status === 'running') return '执行中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '已失败'
  if (status === 'canceled') return '已取消'
  return status || '未知'
}

function formatJobProgress(job: Partial<CustomRuleBatchJob> & Record<string, any>): string {
  const progress = (job.progress ||
    job.summary?.progress ||
    {}) as Partial<CustomRuleBatchJobProgress>
  const stepKey = String(progress.step_key || 'queued')
  const stepLabelMap: Record<string, string> = {
    queued: '排队',
    prepare: '准备',
    filter: '筛选',
    run: '执行',
    aggregate: '汇总',
    completed: '完成',
    failed: '失败',
    canceled: '取消',
  }
  const ruleIndex = Number(progress.rule_index || 0)
  const ruleCount = Number(progress.rule_count || job.rule_count || 1)
  const processed = Number(progress.processed_records || 0)
  const total = Number(
    progress.total_records || job.summary?.total_records || job.total_records || 0,
  )
  return `${stepLabelMap[stepKey] || stepKey} · 规则 ${Math.min(ruleIndex, ruleCount)}/${ruleCount} · 病历 ${processed}/${total}`
}

const canRunBatchJob = computed(() => {
  if (selectedRecordKeys.value.length === 0) return false
  if (!promptReady.value) return false
  return effectiveExecutionDraftIds.value.length > 0
})

const executionTipText = computed(() => {
  if (executionMode.value === 'single') {
    return selectedDraft.value
      ? `当前执行草稿：${selectedDraft.value.rule_code} ${selectedDraft.value.name}`
      : '请先选择一个草稿作为编辑与执行目标。'
  }
  return effectiveExecutionDraftIds.value.length > 0
    ? `当前执行集共 ${effectiveExecutionDraftIds.value.length} 条规则，后端按串行依次执行。`
    : '请在步骤1勾选至少一条规则加入执行集。'
})

async function runBatchJob() {
  if (isBusinessReadOnly.value) return
  if (!canRunBatchJob.value) {
    message.warning('请先补全 Prompt、选择病历并确定执行规则')
    return
  }
  if (!selectedDraft.value) {
    message.warning('请先选择编辑草稿')
    return
  }

  const selectedRecordRefs = buildSelectedRecordRefs()
  if ('message' in selectedRecordRefs) {
    message.error(selectedRecordRefs.message)
    return
  }

  const saved = await saveDraftEditor()
  if (!saved) return

  runningBatchJob.value = true
  try {
    const draftIds = effectiveExecutionDraftIds.value
    if (executionMode.value === 'single' && draftIds.length !== 1) {
      message.warning('单规则模式需要且仅需要 1 条规则')
      return
    }

    const response = await createWorkspaceBatchJob({
      draft_id: executionMode.value === 'single' ? draftIds[0] : undefined,
      draft_ids: executionMode.value === 'multi' ? draftIds : undefined,
      execution_mode: executionMode.value,
      run_mode: 'serial',
      scope: recordFilters.scope,
      department: recordFilters.department,
      doctor: recordFilters.doctor,
      date_field: recordFilters.date_field,
      start_date: recordFilters.dateRange?.[0]?.format('YYYY-MM-DD'),
      end_date: recordFilters.dateRange?.[1]?.format('YYYY-MM-DD'),
      keyword: recordFilters.keyword || undefined,
      record_refs: selectedRecordRefs.recordRefs,
      temperature: advancedParams.temperature,
      top_p: advancedParams.top_p,
      max_tokens: advancedParams.max_tokens,
    })

    if (!response.success || !response.data) {
      throw new Error(response.message || '创建任务失败')
    }

    message.success('批量任务已创建并开始执行')
    activeBatchJob.value = response.data
    activeBatchJobId.value = response.data.id
    await loadBatchJobs()
    startBatchJobPolling(response.data.id)
  } catch (error: any) {
    message.error(error?.message || '创建任务失败')
  } finally {
    runningBatchJob.value = false
  }
}

const stepItems = computed(() => {
  const running =
    activeBatchJob.value && ['queued', 'running'].includes(activeBatchJob.value.status)
  const done =
    activeBatchJob.value &&
    ['completed', 'failed', 'canceled'].includes(activeBatchJob.value.status)

  const steps: Array<{
    index: string
    label: string
    anchor: string
    status: StepStatus
    statusLabel: string
  }> = [
    {
      index: '1',
      label: '规则列表',
      anchor: 'step-rules',
      status: selectedDraftIds.value.length > 0 ? 'ready' : 'pending',
      statusLabel: selectedDraftIds.value.length > 0 ? '可执行' : '未就绪',
    },
    {
      index: '2',
      label: '规则创建',
      anchor: 'step-create',
      status: selectedDraft.value ? 'ready' : 'pending',
      statusLabel: selectedDraft.value ? '可编辑' : '未就绪',
    },
    {
      index: '3',
      label: 'Prompt 编辑',
      anchor: 'step-prompt',
      status: promptReady.value ? 'ready' : 'pending',
      statusLabel: promptReady.value ? '可执行' : '待补全',
    },
    {
      index: '4',
      label: '筛选与执行',
      anchor: 'step-records',
      status: running ? 'running' : done ? 'done' : canRunBatchJob.value ? 'ready' : 'pending',
      statusLabel: running
        ? '执行中'
        : done
          ? '已完成'
          : canRunBatchJob.value
            ? '可执行'
            : '未就绪',
    },
  ]
  return steps
})

// 批量执行视图按步骤分屏：步骤导航切换当前步骤；设计视图仍全部展示
const activeStep = ref('step-rules')

function isStepVisible(anchor: string): boolean {
  return workspaceMode.value !== 'batch' || activeStep.value === anchor
}

function scrollToStep(anchor: string) {
  activeStep.value = anchor
  if (typeof window !== 'undefined') window.scrollTo?.({ top: 0, behavior: 'smooth' })
}

const ruleResultRows = computed(() => {
  if (!activeBatchJob.value) return []
  const rows = activeBatchJob.value.rule_results || activeBatchJob.value.summary?.rule_results || []
  return rows as CustomRuleBatchJobRuleResult[]
})

const recordResultRows = computed(() => activeBatchJob.value?.items || [])
const failedResultRows = computed(() => activeBatchJob.value?.failed_records || [])

const ruleResultColumns: TableColumnsType<CustomRuleBatchJobRuleResult> = [
  { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 120 },
  { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', width: 200 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '成功', dataIndex: 'success_count', key: 'success_count', width: 90 },
  { title: '失败', dataIndex: 'failed_count', key: 'failed_count', width: 90 },
  { title: '命中', dataIndex: 'issue_records', key: 'issue_records', width: 90 },
]

const recordResultColumns: TableColumnsType<Record<string, unknown>> = [
  { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 110 },
  { title: '患者', dataIndex: 'patient_name', key: 'patient_name', width: 100 },
  { title: 'visit', dataIndex: 'visit_id', key: 'visit_id', width: 120 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '结论', dataIndex: 'findings', key: 'findings' },
]

const failedResultColumns: TableColumnsType<Record<string, unknown>> = [
  { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 110 },
  { title: '患者', dataIndex: 'patient_name', key: 'patient_name', width: 100 },
  { title: 'visit', dataIndex: 'visit_id', key: 'visit_id', width: 120 },
  { title: '错误', dataIndex: 'error', key: 'error' },
]

watch(
  () => selectedDraftId.value,
  () => {
    const draft = selectedDraft.value
    if (draft) {
      hydrateEditorFromDraft(draft)
    }
  },
)

watch(
  () => recordFilters.scope,
  async () => {
    recordFilters.department = undefined
    recordFilters.doctor = undefined
    await searchRecords()
  },
)

watch(
  () => executionMode.value,
  (mode) => {
    if (mode === 'single' && selectedDraftId.value) {
      selectedDraftIds.value = [selectedDraftId.value]
    }
  },
)

onMounted(async () => {
  await Promise.all([loadDrafts(), searchRecords(), loadBatchJobs()])
})

onBeforeUnmount(() => {
  stopBatchJobPolling()
})
</script>
<style scoped>
.custom-rule-workspace {
  --workstation-font:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  --panel-bg: rgba(255, 255, 255, 0.86);
  --panel-border: rgba(0, 0, 0, 0.08);
  --panel-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 10px 30px rgba(0, 0, 0, 0.06);
  --panel-hover-shadow: 0 2px 12px rgba(0, 0, 0, 0.1), 0 6px 22px rgba(0, 0, 0, 0.075);
  --ink-strong: #1d1d1f;
  --ink-main: rgba(29, 29, 31, 0.78);
  --ink-muted: rgba(29, 29, 31, 0.6);
  --ink-subtle: rgba(29, 29, 31, 0.38);
  --brand-blue: #0a6cff;
  --brand-soft: rgba(10, 108, 255, 0.08);
  --surface-muted: rgba(0, 0, 0, 0.03);
  min-height: 100%;
  padding: 14px;
  font-family: var(--workstation-font);
  color: var(--ink-main);
  background: #f5f5f7;
}

.ops-overview {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  border: 1px solid var(--panel-border);
  border-radius: 20px;
  background: var(--panel-bg);
  backdrop-filter: blur(18px);
  box-shadow: var(--panel-shadow);
  padding: 16px 18px;
  transition:
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.ops-overview:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow: var(--panel-hover-shadow);
  transform: translateY(-2px);
}

.view-mode-shell {
  margin-top: 12px;
  border: 1px solid var(--panel-border);
  border-radius: 16px;
  background: var(--panel-bg);
  backdrop-filter: blur(18px);
  box-shadow: var(--panel-shadow);
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.view-mode-tip {
  margin: 0;
  font-size: 12px;
  color: var(--ink-muted);
}

.ops-eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  letter-spacing: 0;
  text-transform: uppercase;
  color: var(--brand-blue);
  font-weight: 600;
}

.ops-title {
  margin: 0;
  font-size: 28px;
  line-height: 31px;
  font-weight: 700;
  color: var(--ink-strong);
}

.ops-subtitle {
  margin: 8px 0 0;
  color: var(--ink-muted);
  font-size: 13px;
}

.ops-kpis {
  display: grid;
  grid-template-columns: repeat(2, minmax(108px, 1fr));
  gap: 10px;
  width: min(420px, 100%);
}

.kpi-card {
  border-radius: 12px;
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.72);
  padding: 10px 12px;
}

.kpi-label {
  display: block;
  font-size: 11px;
  color: var(--ink-muted);
}

.kpi-value {
  margin-top: 3px;
  display: block;
  color: var(--brand-blue);
  font-size: 18px;
  line-height: 1.1;
  font-weight: 700;
}

.step-nav-shell {
  position: sticky;
  top: 8px;
  z-index: 15;
  margin-top: 12px;
}

.step-nav {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  padding: 8px;
  border: 1px solid var(--panel-border);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(18px);
}

.step-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: 10px;
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.72);
  padding: 8px 10px;
  cursor: pointer;
  color: rgba(29, 29, 31, 0.72);
  text-align: left;
  transition:
    background 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.step-pill:hover {
  border-color: rgba(10, 108, 255, 0.18);
  background: rgba(10, 108, 255, 0.06);
  transform: translateY(-1px);
}

.step-index {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e5efff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--brand-blue);
}

.step-label {
  font-size: 12px;
  font-weight: 600;
}

.step-state {
  margin-left: auto;
  font-size: 11px;
}

.step-pill--pending {
  border-color: var(--panel-border);
}

.step-pill--ready {
  border-color: rgba(10, 108, 255, 0.22);
  background: rgba(10, 108, 255, 0.08);
  color: var(--brand-blue);
}

.step-pill--running {
  border-color: rgba(245, 158, 11, 0.22);
  background: rgba(245, 158, 11, 0.1);
}

.step-pill--done {
  border-color: rgba(16, 185, 129, 0.22);
  background: rgba(16, 185, 129, 0.1);
}

.workspace-grid {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.workspace-grid-half {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.workspace-panel {
  border-radius: 20px;
  border: 1px solid var(--panel-border);
  background: var(--panel-bg);
  backdrop-filter: blur(18px);
  box-shadow: var(--panel-shadow);
  padding: 14px;
  margin-top: 12px;
  transition:
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.workspace-panel:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow: var(--panel-hover-shadow);
  transform: translateY(-2px);
}

.step-inline-panel {
  padding-top: 12px;
  padding-bottom: 12px;
}

.step-inline-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.step-inline-card {
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  background: var(--surface-muted);
  padding: 8px 10px;
}

.step-inline-label {
  margin: 0;
  font-size: 11px;
  color: var(--ink-muted);
}

.step-inline-value {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--ink-strong);
  line-height: 1.6;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-eyebrow {
  margin: 0;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--brand-blue);
  font-weight: 600;
}

.panel-title {
  margin: 2px 0 0;
  font-size: 17px;
  line-height: 22px;
  color: var(--ink-strong);
  font-weight: 600;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.draft-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 130px;
  gap: 8px;
  margin-bottom: 10px;
}

.rule-code-pill {
  min-width: 88px;
  padding: 4px 10px;
  border-radius: 10px;
  border: 1px solid rgba(10, 108, 255, 0.16);
  background: rgba(10, 108, 255, 0.08);
  color: var(--brand-blue);
  font-size: 12px;
  font-weight: 600;
}

.rule-code-pill.active {
  border-color: rgba(10, 108, 255, 0.28);
  box-shadow: 0 0 0 3px rgba(10, 108, 255, 0.08);
}

.draft-title {
  font-size: 13px;
  color: var(--ink-strong);
  font-weight: 600;
  line-height: 1.45;
}

.draft-subtitle {
  margin-top: 2px;
  font-size: 11px;
  color: var(--ink-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.draft-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}

:deep(.draft-row-active > td) {
  background: rgba(10, 108, 255, 0.06) !important;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.prompt-compact {
  margin-top: 8px;
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  background: var(--surface-muted);
  padding: 8px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.prompt-compact-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.prompt-compact-points {
  display: flex;
  align-items: center;
  gap: 6px;
}

.prompt-compact-text {
  color: var(--ink-muted);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.prompt-summary {
  margin-top: 8px;
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  background: var(--surface-muted);
  padding: 10px 12px;
}

.prompt-summary-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-strong);
}

.prompt-summary-text {
  margin: 6px 0 0;
  color: var(--ink-muted);
  line-height: 1.7;
  font-size: 12px;
  white-space: pre-wrap;
}

.prompt-summary-points {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.design-meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.design-meta-item {
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  padding: 8px 10px;
  background: var(--surface-muted);
}

.design-meta-label {
  display: block;
  font-size: 11px;
  color: var(--ink-muted);
}

.design-meta-value {
  margin-top: 4px;
  display: block;
  color: var(--ink-strong);
  font-size: 13px;
  font-weight: 600;
}

.check-point-list {
  margin-top: 10px;
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  background: var(--surface-muted);
  padding: 10px 12px;
}

.check-point-title {
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-strong);
}

.check-point-item {
  font-size: 12px;
  color: var(--ink-muted);
  line-height: 1.7;
}

.execution-tips {
  margin-bottom: 10px;
}

.record-filter-grid {
  display: grid;
  grid-template-columns: 140px 150px 150px 120px 260px minmax(200px, 1fr) 94px;
  gap: 8px;
  margin-bottom: 10px;
}
.record-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--ink-muted);
}

.advanced-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 8px;
}

.advanced-grid :deep(.ant-form-item) {
  margin-bottom: 0;
}

.batch-shell {
  margin-top: 12px;
  border: 1px solid var(--panel-border);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.7);
}

.batch-shell-head {
  padding: 12px 14px;
  border-bottom: 1px solid var(--panel-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.batch-shell-title {
  margin: 2px 0 0;
  font-size: 14px;
  color: var(--ink-strong);
  font-weight: 600;
}

.batch-filters {
  display: flex;
  gap: 8px;
  padding: 10px 12px 0;
}

.batch-rule-name {
  font-size: 12px;
  color: var(--ink-strong);
  font-weight: 600;
}

.batch-rule-meta {
  margin-top: 2px;
  font-size: 11px;
  color: var(--ink-muted);
}

.batch-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.job-progress-text {
  font-size: 12px;
  color: var(--ink-muted);
}

.cell-muted {
  color: var(--ink-muted);
}

.job-status {
  border: none;
  font-size: 11px;
}

.job-status--queued {
  background: rgba(10, 108, 255, 0.08);
  color: var(--brand-blue);
}

.job-status--running {
  background: #fff7e8;
  color: #ad6800;
}

.job-status--completed {
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.job-status--failed {
  background: #fff1f0;
  color: #b3261e;
}

.job-status--canceled {
  background: rgba(0, 0, 0, 0.04);
  color: var(--ink-muted);
}

.result-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 12px;
}

.result-panel {
  border-radius: 12px;
  border: 1px solid var(--panel-border);
  background: rgba(255, 255, 255, 0.72);
  padding: 10px;
}

.result-panel h3 {
  margin: 0 0 8px;
  color: var(--ink-strong);
  font-size: 13px;
  font-weight: 600;
}

.result-kpis {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
}

.result-kpi {
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  padding: 8px;
  background: var(--surface-muted);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result-kpi span {
  font-size: 11px;
  color: var(--ink-muted);
}

.result-kpi strong {
  font-size: 14px;
  color: var(--brand-blue);
}

.result-text {
  margin-top: 6px;
  margin-bottom: 0;
  font-size: 12px;
  color: var(--ink-muted);
  line-height: 1.6;
}

.result-text--danger {
  color: #b3261e;
}

.mt-10 {
  margin-top: 10px;
}

.mb-10 {
  margin-bottom: 10px;
}

.w-full {
  width: 100%;
}

:deep(.ant-table-thead > tr > th) {
  background: rgba(255, 255, 255, 0.88) !important;
  color: rgba(29, 29, 31, 0.6) !important;
  font-size: 12px;
  font-weight: 600 !important;
  border-bottom: 1px solid var(--panel-border) !important;
}

:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.06) !important;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background: rgba(0, 0, 0, 0.03) !important;
}

:deep(.ant-btn) {
  border-radius: 8px;
  font-family: var(--workstation-font);
  font-weight: 600;
  transition:
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    background 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

:deep(.ant-btn-primary) {
  background: var(--brand-blue);
  border-color: var(--brand-blue);
  box-shadow: 0 4px 12px rgba(10, 108, 255, 0.18);
}

:deep(.ant-btn-primary:not(:disabled):hover) {
  background: #0057b8;
  border-color: #0057b8;
  box-shadow: 0 6px 16px rgba(10, 108, 255, 0.22);
  transform: translateY(-1px);
}

:deep(.ant-btn-default:not(:disabled):hover),
:deep(.ant-btn-text:not(:disabled):hover),
:deep(.ant-btn-link:not(:disabled):hover) {
  color: var(--brand-blue);
  border-color: rgba(10, 108, 255, 0.22);
  background: rgba(10, 108, 255, 0.06);
}

:deep(.ant-radio-button-wrapper) {
  border-color: var(--panel-border);
  color: var(--ink-muted);
  font-family: var(--workstation-font);
}

:deep(.ant-radio-button-wrapper-checked:not(.ant-radio-button-wrapper-disabled)) {
  color: var(--brand-blue);
  border-color: var(--brand-blue);
  background: rgba(10, 108, 255, 0.08);
  box-shadow: none;
}

:deep(.ant-radio-button-wrapper-checked:not(.ant-radio-button-wrapper-disabled)::before) {
  background-color: var(--brand-blue);
}

:deep(.ant-input),
:deep(.ant-input-number),
:deep(.ant-picker),
:deep(.ant-select-selector) {
  border-radius: 8px !important;
  border-color: var(--panel-border) !important;
  font-family: var(--workstation-font);
}

:deep(.ant-input:hover),
:deep(.ant-input-number:hover),
:deep(.ant-picker:hover),
:deep(.ant-select:not(.ant-select-disabled):hover .ant-select-selector) {
  border-color: rgba(10, 108, 255, 0.22) !important;
}

:deep(.ant-input:focus),
:deep(.ant-input-focused),
:deep(.ant-picker-focused),
:deep(.ant-select-focused .ant-select-selector) {
  border-color: var(--brand-blue) !important;
  box-shadow: 0 0 0 3px rgba(10, 108, 255, 0.08) !important;
}

:deep(.ant-tag) {
  border: 0;
  border-radius: 999px;
  font-family: var(--workstation-font);
  font-size: 11px;
  font-weight: 600;
}

:deep(.ant-table),
:deep(.ant-table-wrapper),
:deep(.ant-pagination),
:deep(.ant-form),
:deep(.ant-alert) {
  font-family: var(--workstation-font);
}

@media (max-width: 1440px) {
  .record-filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .workspace-grid-half {
    grid-template-columns: minmax(0, 1fr);
  }

  .ops-overview {
    flex-direction: column;
  }

  .ops-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }

  .view-mode-shell {
    flex-direction: column;
    align-items: flex-start;
  }

  .step-nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .result-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .batch-filters {
    flex-wrap: wrap;
  }

  .step-inline-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .design-meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* ===== v7.1 液态玻璃覆盖：本页变量改指 --mq-* Token，面板统一玻璃卡 ===== */
.custom-rule-workspace {
  --workstation-font: var(--mq-font-family);
  --panel-bg: var(--mq-glass-bg);
  --panel-border: var(--mq-glass-border);
  --panel-shadow: var(--mq-glass-shadow);
  --panel-hover-shadow: var(--mq-glass-shadow);
  --ink-strong: var(--mq-text-primary);
  --ink-main: var(--mq-text-secondary);
  --ink-muted: var(--mq-text-tertiary);
  --ink-subtle: var(--mq-text-disabled);
  --brand-blue: var(--mq-brand-600);
  --brand-soft: var(--mq-info-bg);
  --surface-muted: rgba(118, 128, 160, 0.07);
  padding: 8px 28px 32px 22px;
  background: transparent;
}

.crw-head__desc {
  margin: 2px 0 0;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
}

.ops-overview {
  display: block;
  padding: 0;
  overflow: hidden;
}

.ops-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  width: 100%;
}

.kpi-card {
  padding: 18px 22px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.kpi-card + .kpi-card {
  border-left: 0.5px solid var(--mq-border);
}

.kpi-label {
  color: var(--mq-text-primary);
  font-size: var(--mq-font-14);
  font-weight: 600;
}

.kpi-value {
  color: var(--mq-text-primary);
  font-family: var(--mq-font-display);
  font-size: 36px;
  font-weight: 600;
  letter-spacing: -0.03em;
  white-space: nowrap;
}

/* 步骤导航：分段切换外观，当前步骤白色浮起 */
.step-nav-shell {
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.step-nav {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 3px;
  border-radius: 13px;
  background: var(--mq-bg-muted);
}

.step-pill {
  min-height: 34px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  box-shadow: none;
  cursor: pointer;
}

.step-pill.is-active {
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(10, 55, 115, 0.12);
}

.step-pill.is-active .step-label {
  color: var(--mq-text-primary);
  font-weight: 600;
}

.workspace-panel {
  border-radius: var(--mq-radius-card);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
}

.custom-rule-workspace :deep(.ant-btn) {
  border-radius: 999px;
}

.custom-rule-workspace :deep(.ant-table-thead > tr > th) {
  background: rgba(118, 128, 160, 0.06);
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-weight: 600;
}

.custom-rule-workspace :deep(.ant-table),
.custom-rule-workspace :deep(.ant-table-container),
.custom-rule-workspace :deep(.ant-table-tbody > tr > td) {
  background: transparent;
}

@media (max-width: 1100px) {
  .ops-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
/* 字重收敛：Windows 下中文走微软雅黑，600 及以上都会渲染成粗黑体。
   KPI 条与统计分析页保持一致不动；只保留面板标题、当前步骤用 600，其余标签、行名、按钮、标签一律 500 */
.step-index {
  font-weight: 600;
}

.step-label,
.panel-eyebrow,
.rule-code-pill,
.draft-title,
.prompt-summary-title,
.design-meta-value,
.check-point-title,
.batch-rule-name {
  font-weight: 500;
}

.step-pill.is-active .step-label {
  font-weight: 600;
}

.custom-rule-workspace :deep(.ant-btn),
.custom-rule-workspace :deep(.ant-tag) {
  font-weight: 500;
}

.custom-rule-workspace :deep(.ant-table-thead > tr > th) {
  font-weight: 500 !important;
}
</style>
