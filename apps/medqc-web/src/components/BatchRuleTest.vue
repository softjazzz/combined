<template>
  <div :class="['batch-rule-test', isDemoMode ? 'demo-mode' : 'page-container min-h-screen bg-gray-50 p-2 lg:p-3']">
    <!-- 页面头部 + Tab 导航 (仅在非演示模式下显示) -->
    <div v-if="!isDemoMode" class="bg-white rounded-lg shadow-sm border border-gray-200 p-3 lg:p-4 mb-3">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div class="flex flex-1 items-start gap-3">
          <div class="p-2 bg-blue-100 rounded-md">
            <SettingOutlined class="text-lg text-blue-600" />
          </div>
          <div class="space-y-1">
            <h1 class="text-xl font-bold text-gray-900">质控规则管理</h1>
            <p class="text-sm text-gray-600 leading-relaxed">
              {{ batchDescription }}
            </p>
          </div>
        </div>
        <!-- 通用操作按钮区域 -->
        <div class="flex flex-wrap gap-1.5">
          <!-- LLM 设置按钮 -->
          <a-button
            @click="showLLMSettings"
            size="large"
            class="llm-settings-button"
          >
            <template #icon><ApiOutlined /></template>
            <span>LLM 设置</span>
          </a-button>
        </div>
      </div>

      <a-tabs
        v-model:activeKey="activeTab"
        type="card"
        class="rules-tabs compact-tabs mt-3"
        @change="handleTabChange"
        size="small"
      >
        <a-tab-pane key="semantic" tab="四川省质控规则">
          <template #tab>
            <span class="qc-tab-title">
              <BranchesOutlined />
              四川省质控规则
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="custom" tab="泸县33条规则">
          <template #tab>
            <span class="qc-tab-title">
              <AppstoreOutlined />
              泸县33条规则
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="lx_legacy" tab="泸县存量质控规则">
          <template #tab>
            <span class="qc-tab-title">
              <AppstoreOutlined />
              泸县存量质控规则
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="department" tab="科室规则管理">
          <template #tab>
            <span class="qc-tab-title">
              <ApartmentOutlined />
              科室规则管理
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="traditional" tab="传统质控规则">
          <template #tab>
            <span class="qc-tab-title">
              <SettingOutlined />
              传统质控规则
            </span>
          </template>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 批量质控评估内容区域 -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-3 lg:p-4">
      <div v-if="!isDemoMode" class="flex justify-between items-center mb-4">
        <h2 class="text-lg font-semibold text-gray-900">批量质控评估</h2>
        <a-button @click="goBack">
          <template #icon><ArrowLeftOutlined /></template>
          返回列表
        </a-button>
      </div>
      <div v-else class="flex justify-between items-center mb-4">
        <h2 class="text-lg font-semibold text-gray-900">批量质控评估</h2>
      </div>

      <!-- 主体内容区域 -->
      <div class="batch-test-content">
      <!-- 文书类型选择器 - 紧凑标签页样式 -->
      <div class="document-type-selector-compact">
        <div class="selector-header">
          <h3 class="selector-title">文书类型</h3>
          <span class="selector-hint">选择要测试的病历类型</span>
        </div>
        <div class="document-type-tabs">
          <div
            v-for="config in documentTypeConfigsWithCount"
            :key="config.key"
            :class="['document-tab', {
              active: currentDocumentType === config.key,
              disabled: isTesting
            }]"
            @click="handleCardClick(config.key)"
          >
            <component :is="iconComponents[config.icon]" class="tab-icon" />
            <div class="tab-content">
              <div class="tab-label">{{ config.label }}</div>
              <div class="tab-count">{{ config.ruleCount }} 条</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 左右分栏内容 -->
      <div class="content-main">
        <!-- 左侧：病历摘要 -->
        <div class="left-panel">
          <!-- 标题和操作按钮（左对齐，同一行） -->
          <div class="panel-header">
            <h3>{{ currentConfig.label }}</h3>
            <a-button size="small" @click="showMedicalTextModal = true" type="link">
              <template #icon><FileTextOutlined /></template>
              查看完整病历
            </a-button>
          </div>

          <!-- 病历摘要卡片 -->
          <div class="medical-summary-cards" v-if="medicalSummary">
            <div class="summary-card-grid">
              <div class="summary-card">
                <div class="card-label">患者信息</div>
                <div class="card-value">{{ medicalSummary.patientInfo }}</div>
              </div>
              <div class="summary-card">
                <div class="card-label">年龄/性别</div>
                <div class="card-value">{{ medicalSummary.age }} / {{ medicalSummary.gender }}</div>
              </div>
              <div class="summary-card">
                <div class="card-label">入院科室</div>
                <div class="card-value">{{ medicalSummary.department }}</div>
              </div>
              <div class="summary-card">
                <div class="card-label">主诉</div>
                <div class="card-value">{{ medicalSummary.chiefComplaint }}</div>
              </div>
              <div class="summary-card full-width">
                <div class="card-label">入院诊断</div>
                <div class="card-value">{{ medicalSummary.diagnosis }}</div>
              </div>
            </div>
          </div>
      </div>

      <!-- 右侧：质控点选择与结果 -->
      <div class="right-panel">
        <!-- 质控点选择区域 -->
        <div class="rule-selection-section">
          <div class="section-header">
            <h3>
              <span>选择质控点</span>
              <a-tag :color="currentConfig.tagColor" class="document-tag" style="margin-left: 8px">
                <component :is="iconComponents[currentConfig.icon]" class="document-tag__icon" :style="{ color: '#fff' }" />
                {{ currentConfig.label }}
              </a-tag>
            </h3>
          </div>

          <!-- 搜索和筛选工具栏 -->
          <div class="filter-toolbar">
            <a-input-search
              v-model:value="searchText"
              placeholder="搜索规则ID或名称..."
              :disabled="isTesting"
              allowClear
            >
              <template #prefix>
                <SearchOutlined />
              </template>
            </a-input-search>
            <a-select
              v-model:value="filterDefectLevel"
              placeholder="缺陷等级"
              :disabled="isTesting"
              allowClear
              style="width: 120px"
            >
              <a-select-option value="严重缺陷">🔴 严重</a-select-option>
              <a-select-option value="一般缺陷">🟡 一般</a-select-option>
              <a-select-option value="轻微缺陷">🟢 轻微</a-select-option>
            </a-select>
            <a-select
              v-model:value="filterComplexity"
              placeholder="复杂度"
              :disabled="isTesting"
              allowClear
              style="width: 110px"
            >
              <a-select-option value="高复杂度">🟠 高</a-select-option>
              <a-select-option value="中复杂度">🟢 中</a-select-option>
              <a-select-option value="低复杂度">🔵 低</a-select-option>
            </a-select>
          </div>

          <!-- 选择摘要 -->
          <div class="selection-summary">
            <a-checkbox
              :checked="isAllSelected"
              :indeterminate="isIndeterminate"
              @change="toggleSelectAll"
              :disabled="isTesting || filteredRules.length === 0"
            >
              全选
            </a-checkbox>
            <span class="summary-text">
              已选 {{ selectedRuleIds.length }}/{{ filteredRules.length }} 条
              <span v-if="searchText || filterDefectLevel || filterComplexity" class="filter-hint">
                (已过滤)
              </span>
            </span>
          </div>

          <!-- 分类折叠面板 -->
          <div class="rules-categorized-list">
            <a-collapse v-model:activeKey="expandedCategories" ghost>
              <a-collapse-panel
                v-for="[categoryKey, categoryRules] in categorizedRulesArray"
                :key="categoryKey"
                :header="getCategoryHeaderText(categoryKey, categoryRules.length)"
              >
                <template #extra>
                  <span class="category-icon">{{ getCategoryIcon(categoryKey) }}</span>
                </template>
                <div class="category-rules-table">
                  <div class="rules-table-header">
                    <div class="col-checkbox"></div>
                    <div class="col-id">规则ID</div>
                    <div class="col-name">规则名称</div>
                    <div class="col-level">缺陷等级</div>
                  </div>
                  <div class="rules-table-body">
                    <div
                      v-for="rule in categoryRules"
                      :key="rule.rule_id"
                      :class="['rule-row', {
                        selected: selectedRuleIds.includes(rule.rule_id),
                        disabled: isTesting
                      }]"
                      @click="toggleRuleSelection(rule.rule_id)"
                    >
                      <div class="col-checkbox">
                        <a-checkbox
                          :checked="selectedRuleIds.includes(rule.rule_id)"
                          :disabled="isTesting"
                          @click.stop
                          @change="() => toggleRuleSelection(rule.rule_id)"
                        />
                      </div>
                      <div class="col-id">{{ rule.rule_id }}</div>
                      <div class="col-name" :title="rule.name">{{ rule.name }}</div>
                      <div class="col-level">
                        <span class="status-tag" :class="getDefectLevelClass(rule.defect_level)">
                          {{ normalizeDefectLevel(rule.defect_level) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </a-collapse-panel>
            </a-collapse>
          </div>
        </div>

      </div>
    </div>

    <!-- 主操作按钮区域（页面底部中间，水平并排） -->
    <div class="main-actions-section-bottom">
      <div class="actions-row">
        <!-- 开始批量测试按钮 -->
        <a-button
          type="primary"
          size="large"
          :loading="isTesting"
          :disabled="selectedRuleIds.length === 0 || !medicalText.trim()"
          @click="startBatchTest"
          class="primary-action-button"
        >
          <template #icon><ThunderboltOutlined /></template>
          {{ isTesting ? `正在测试 ${testProgress.completed}/${testProgress.total}` : '开始批量测试' }}
        </a-button>

        <!-- 启动快速质控评估按钮 -->
        <a-button
          type="primary"
          size="large"
          :loading="isProductionTesting"
          :disabled="selectedRuleIds.length === 0 || !medicalText.trim() || isTesting"
          @click="startProductionBatchQC"
          class="primary-action-btn"
        >
          <template #icon><ThunderboltOutlined /></template>
          {{ isProductionTesting ? '正在快速质控...' : '启动快速质控评估' }}
        </a-button>

        <!-- 查看质控结果按钮 -->
        <a-button
          type="default"
          size="large"
          @click="handleViewResults"
          class="secondary-action-btn"
        >
          <template #icon><HistoryOutlined /></template>
          查看质控结果
          <span v-if="testResults.length > 0 || productionResult" style="margin-left: 4px; opacity: 0.7;">
            ({{ getResultsCountText }})
          </span>
        </a-button>
      </div>

      <!-- 高级选项（折叠） -->
      <a-collapse ghost class="advanced-options-collapse">
        <a-collapse-panel key="1">
          <template #header>
            <span class="advanced-options-header">
              <SettingOutlined /> 高级选项
              <a-tag :color="promptModeConfig[selectedPromptMode].color" size="small" style="margin-left: 8px">
                {{ promptModeConfig[selectedPromptMode].tag }}
              </a-tag>
            </span>
          </template>
          <div class="advanced-options-content">
            <div class="option-item">
              <label class="option-label">提示词优化方案</label>
              <a-select v-model:value="selectedPromptMode" style="width: 100%">
                <a-select-option value="plan_a">
                  <span class="option-name">{{ promptModeConfig.plan_a.tag }}</span>
                </a-select-option>
                <a-select-option value="plan_b">
                  <span class="option-name">{{ promptModeConfig.plan_b.tag }}</span>
                </a-select-option>
                <a-select-option value="plan_c">
                  <span class="option-name">{{ promptModeConfig.plan_c.tag }}</span>
                </a-select-option>
              </a-select>
              <div class="mode-description">
                {{ promptModeConfig[selectedPromptMode].description }}
              </div>
            </div>
          </div>
        </a-collapse-panel>
      </a-collapse>
      </div>
      <!-- 结束 batch-test-content -->
    </div>
    <!-- 结束批量质控评估内容区域 -->
  </div>
  <!-- 结束 page-container -->

  <!-- 质控结果详情弹窗 -->
  <a-modal
    v-model:open="showResultsModal"
    width="900px"
    :footer="null"
    centered
    :class="{ 'qc-loading-modal': isProductionTesting }"
  >
    <template #title>
      <div style="display: flex; align-items: center; justify-content: space-between; width: calc(100% - 50px); padding-right: 10px;">
        <span>质控结果详情</span>
        <a-button
          v-if="isProductionTesting"
          danger
          size="small"
          @click="stopProductionQC"
        >
          <template #icon><StopOutlined /></template>
          停止分析
        </a-button>
      </div>
    </template>

    <!-- 科技感边框进度指示器 -->
    <div v-if="isProductionTesting" class="border-progress-indicator">
      <div class="progress-line progress-top"></div>
      <div class="progress-line progress-right"></div>
      <div class="progress-line progress-bottom"></div>
      <div class="progress-line progress-left"></div>
      <div class="progress-glow"></div>
    </div>

    <!-- 分析中提示 -->
    <div v-if="isProductionTesting" class="analyzing-overlay">
      <div class="analyzing-content">
        <a-spin size="large">
          <template #indicator>
            <LoadingOutlined style="font-size: 48px; color: #1890ff;" spin />
          </template>
        </a-spin>
        <div class="analyzing-text">正在进行质控分析...</div>
        <div class="analyzing-tip">AI 正在深度分析病历内容，请稍候</div>
        <a-button
          danger
          size="large"
          @click="stopProductionQC"
          style="margin-top: 24px;"
        >
          <template #icon><StopOutlined /></template>
          停止分析
        </a-button>
      </div>
    </div>

    <div class="results-modal-content">
      <!-- 统计摘要 -->
      <div class="modal-summary">
        <a-statistic
          title="合规率"
          :value="productionResult?.data?.evaluation_summary?.compliance_rate"
          suffix="%"
          :value-style="{ color: '#16a34a' }"
        />
        <a-statistic
          title="符合要求"
          :value="productionEvaluationStats.passed"
          suffix="条"
          :value-style="{ color: '#16a34a' }"
        />
        <a-statistic
          title="不适用"
          :value="productionEvaluationStats.notApplicable"
          suffix="条"
          :value-style="{ color: '#0ea5e9' }"
        />
        <a-statistic
          title="发现问题"
          :value="productionEvaluationStats.issues"
          suffix="条"
          :value-style="{ color: '#ea580c' }"
        />
        <a-statistic
          title="评估规则"
          :value="productionEvaluationStats.total"
          suffix="条"
        />
      </div>

      <!-- 性能指标卡片（生产/快速评估结果） -->
      <div v-if="productionResult?.data" class="summary-metrics compact">
        <div class="metric-item">
          <div class="metric-label">累计耗时</div>
          <div class="metric-value">{{ formatSeconds(productionPerformanceMetrics.totalTime) }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">平均耗时</div>
          <div class="metric-value">{{ formatSeconds(productionAverageTime) }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">Token 消耗</div>
          <div class="metric-value">{{ formatTokens(productionPerformanceMetrics.totalTokens) }}</div>
        </div>
      </div>

      <!-- 模型和提示词方案信息 -->
      <div v-if="productionResult?.data" class="modal-info-tags">
        <a-space>
          <a-tag
            v-if="productionResult.data.evaluation_summary?.model || productionResult.data.llm_info?.model"
            color="purple"
            class="model-tag"
          >
            <template #icon><RobotOutlined /></template>
            {{ productionResult.data.evaluation_summary?.model || productionResult.data.llm_info?.model }}
          </a-tag>
          <a-tag
            :color="getPromptModeColor(productionResult.data.prompt_mode)"
            class="prompt-mode-tag"
          >
            {{ getPromptModeLabel(productionResult.data.prompt_mode) }}
          </a-tag>
        </a-space>
      </div>

      <!-- 结果列表 -->
      <div class="modal-results-list">
        <div
          v-for="result in productionResult?.data?.evaluation_results"
          :key="result.rule_id"
          :class="[
            'modal-result-item',
            getResultStatusValue(result as any) === 'error' ? 'error' : (isResultNotApplicable(result) ? 'neutral' : (isResultCompliant(result) ? 'compliant' : 'non-compliant'))
          ]"
        >
          <div class="result-item-header">
            <span :class="['result-icon', getStatusPillClass(result as any)]">
              <CheckCircleOutlined v-if="isResultCompliant(result) && !isResultNotApplicable(result)" />
              <CloseCircleOutlined v-else-if="isResultNonCompliant(result)" />
              <ExclamationCircleOutlined v-else />
            </span>
            <span class="result-rule-id">{{ result.rule_id }}</span>
            <span class="result-rule-name">{{ result.rule_name }}</span>
            <a-tag
              :color="getStatusPillClass(result as any) === 'danger' ? 'error' : (getStatusPillClass(result as any) === 'success' ? 'success' : 'default')"
              size="small"
            >
              {{ getResultStatusText(result as any) }}
            </a-tag>
          </div>
          <div v-if="isResultNotApplicable(result)" class="not-applicable-banner">
            {{ getApplicabilityReason(result as any) || '该规则不适用于当前病历。' }}
          </div>
          <div v-if="hasEvidenceWarning(result as any)" class="evidence-warning inline-warning">
            <WarningOutlined /> 证据未在病历原文中匹配，建议复核。
          </div>
          <div v-else-if="!isResultCompliant(result) && result.findings" class="result-findings">
            <div class="findings-label">发现问题:</div>
            <div class="findings-content">{{ result.findings }}</div>
          </div>
          <div v-if="result.evidence" class="result-evidence">
            <span class="evidence-label">证据:</span>
            <span class="evidence-content">{{ result.evidence }}</span>
          </div>
        </div>
      </div>
    </div>
  </a-modal>

  <!-- 完整病历文本弹窗 -->
  <a-modal
    v-model:open="showMedicalTextModal"
    title="完整病历文本"
    width="900px"
    centered
    :body-style="{ maxHeight: '70vh', overflowY: 'auto', padding: '24px' }"
  >
    <template #footer>
      <a-space>
        <a-button @click="resetMedicalText" :disabled="isTesting">
          <template #icon><ReloadOutlined /></template>
          重置文本
        </a-button>
        <a-button type="primary" @click="showMedicalTextModal = false">
          确定
        </a-button>
      </a-space>
    </template>

    <div class="medical-text-modal-content">
      <!-- 导入提示和操作区域 -->
      <div class="import-section">
        <div class="import-hint">
          <span class="hint-icon">💡</span>
          <span class="hint-text">提示：可直接粘贴病历文本，或使用下方按钮导入</span>
        </div>
        <div class="import-actions">
          <a-space>
            <!-- 从文件导入按钮 -->
            <a-upload
              :before-upload="handleFileUpload"
              :show-upload-list="false"
              accept=".txt"
            >
              <a-button :disabled="isTesting">
                <template #icon><FileTextOutlined /></template>
                从文件导入
              </a-button>
            </a-upload>

            <!-- 选择示例病历下拉菜单 -->
            <a-select
              v-model:value="selectedSampleRecord"
              placeholder="选择示例病历"
              style="width: 240px"
              :disabled="isTesting"
              @change="handleSampleRecordChange"
              allow-clear
            >
              <a-select-option
                v-for="sample in availableSampleRecords"
                :key="sample.id"
                :value="sample.id"
              >
                {{ sample.name }}
              </a-select-option>
            </a-select>
          </a-space>
        </div>
      </div>

      <!-- 病历文本编辑区域 -->
      <a-textarea
        v-model:value="medicalText"
        :disabled="isTesting"
        :placeholder="`请输入或编辑${currentConfig.label}...`"
        :auto-size="{ minRows: 20, maxRows: 40 }"
        class="medical-textarea"
      />
    </div>
  </a-modal>

  <!-- 批量测试结果悬浮窗 -->
  <a-modal
    v-model:open="showTestResultsDrawer"
    title="批量测试结果"
    width="900px"
    :footer="null"
    centered
    :body-style="{ maxHeight: '70vh', overflowY: 'auto', padding: '24px' }"
  >
    <!-- 统计摘要 -->
    <div v-if="testResults.length > 0" class="modal-test-summary">
      <div class="production-summary-tag">
        {{ batchEvaluationStats.total }} 个质控点，
        {{ batchEvaluationStats.passed }} 个符合，
        {{ batchEvaluationStats.notApplicable }} 个不适用，
        {{ batchEvaluationStats.issues }} 个发现问题
      </div>
      <div class="summary-overview">
        <div class="summary-item">
          <span class="summary-label">合规率</span>
          <span class="summary-value success">{{ batchComplianceRate }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">符合要求</span>
          <span class="summary-value success">{{ batchEvaluationStats.passed }} 条</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">不适用</span>
          <span class="summary-value neutral">{{ batchEvaluationStats.notApplicable }} 条</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">发现问题</span>
          <span class="summary-value warning">{{ batchEvaluationStats.issues }} 条</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">评估规则</span>
          <span class="summary-value">{{ batchEvaluationStats.total }} 条</span>
        </div>
      </div>
      <div class="summary-metrics compact">
        <div class="metric-item">
          <div class="metric-label">累计耗时</div>
          <div class="metric-value">{{ formatSeconds(batchPerformanceMetrics.totalTime) }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">平均耗时</div>
          <div class="metric-value">{{ formatSeconds(batchPerformanceMetrics.avgTime) }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">Token 消耗</div>
          <div class="metric-value">{{ formatTokens(batchPerformanceMetrics.totalTokens) }}</div>
        </div>
      </div>
    </div>

    <div class="modal-results-controls">
      <a-segmented v-model:value="resultFilter" :options="resultFilterOptions" size="middle" />
      <span class="results-count">共 {{ visibleTestResults.length }} 条结果</span>
    </div>

    <!-- 测试中状态 -->
    <div v-if="isTesting" class="testing-indicator">
      <a-spin size="large" />
      <p class="testing-text">
        正在测试 {{ testProgress.currentRuleName || '...' }}
        ({{ testProgress.completed }}/{{ testProgress.total }})
      </p>
    </div>

    <!-- 测试结果列表 -->
    <div class="modal-test-results-list">
      <a-empty v-if="!isTesting && visibleTestResults.length === 0" description="暂无结果" />
      <a-collapse
        v-else
        ghost
        :bordered="false"
        :activeKey="expandedResultKeys"
        expand-icon-position="end"
        class="results-collapse"
        @update:activeKey="handleCollapseChange"
      >
        <a-collapse-panel
          v-for="result in visibleTestResults"
          :key="result.ruleId"
          :class="[
            'result-panel',
            result.error ? 'error' : (isResultNotApplicable(result) ? 'neutral' : (isResultCompliant(result) ? 'compliant' : 'non-compliant'))
          ]"
        >
          <template #header>
            <div class="result-panel-header">
              <div class="header-left">
                <span class="result-icon">
                  <CheckCircleOutlined v-if="isResultCompliant(result) && !isResultNotApplicable(result) && !result.error" />
                  <CloseCircleOutlined v-else-if="isResultNonCompliant(result) && !result.error" />
                  <ExclamationCircleOutlined v-else />
                </span>
                <div class="result-info">
                  <div class="result-rule-id">{{ result.ruleId }}</div>
                  <div class="result-rule-name">{{ result.ruleName }}</div>
                </div>
              </div>
              <div class="header-right">
                <span :class="['status-pill', getStatusPillClass(result as any)]">
                  {{ getResultStatusText(result) }}
                </span>
                <span v-if="!result.error" class="confidence-chip">
                  置信度 {{ formatConfidence(result) }}
                </span>
                <a-tag v-else color="warning">测试失败</a-tag>
              </div>
            </div>
          </template>

          <div class="result-panel-body">
            <div v-if="isResultNotApplicable(result)" class="not-applicable-banner">
              {{ getApplicabilityReason(result) || '本规则不适用于该病历。' }}
            </div>
            <div v-if="hasEvidenceWarning(result)" class="evidence-warning">
              <WarningOutlined /> 证据未在病历原文中匹配，建议人工复核。
            </div>

            <div v-if="result.error" class="result-error">
              <a-alert type="error" :message="result.error" show-icon />
            </div>

            <template v-else>
              <div class="result-issues">
                <div class="issues-title">{{ getIssuesTitle(result) }}</div>
                <template v-if="result.issues && result.issues.length > 0">
                  <div v-for="(issue, idx) in result.issues" :key="idx" class="issue-item">
                    <div class="issue-description">
                      <span class="issue-number">{{ idx + 1 }}.</span>
                      {{ issue.description }}
                    </div>
                    <div v-if="issue.evidence" class="issue-evidence">
                      <span class="evidence-label">证据:</span>
                      {{ issue.evidence }}
                    </div>
                  </div>
                </template>
                <div v-else class="issues-empty">
                  {{ getIssuesEmptyText(result) }}
                </div>
              </div>

              <div v-if="result.llmRawOutput" class="llm-output-section">
                <a-collapse ghost>
                  <a-collapse-panel key="1" header="查看LLM原始输出">
                    <pre class="llm-output">{{ result.llmRawOutput }}</pre>
                  </a-collapse-panel>
                </a-collapse>
              </div>
            </template>
          </div>
        </a-collapse-panel>
      </a-collapse>
    </div>
  </a-modal>

  <!-- 质控结果历史弹窗 -->
  <a-modal
    v-model:open="showHistoryModal"
    title="质控结果"
    width="1200px"
    :footer="null"
    centered
    class="history-modal"
  >
    <a-tabs v-model:activeKey="currentTab" class="history-tabs">
      <!-- 本次质控结果 Tab -->
      <a-tab-pane key="current" tab="本次质控结果">
        <!-- 加载中状态 -->
        <div v-if="isProductionTesting" class="current-result-loading">
          <!-- 实时统计摘要（批量测试时显示） -->
          <div v-if="isTesting && testProgress.total > 0" class="modal-summary" style="margin-bottom: 24px;">
            <a-statistic
              title="合规率"
              :value="realtimeBatchStats.complianceRate"
              suffix="%"
              :value-style="{ color: realtimeBatchStats.complianceRate >= 70 ? '#16a34a' : '#dc2626' }"
            />
            <a-statistic
              title="符合要求"
              :value="realtimeBatchStats.passed"
              suffix="条"
              :value-style="{ color: '#16a34a' }"
            />
            <a-statistic
              title="不适用"
              :value="realtimeBatchStats.notApplicable"
              suffix="条"
              :value-style="{ color: '#0ea5e9' }"
            />
            <a-statistic
              title="发现问题"
              :value="realtimeBatchStats.issues"
              suffix="条"
              :value-style="{ color: '#ea580c' }"
            />
            <a-statistic
              title="评估规则"
              :value="`${realtimeBatchStats.completed}/${testProgress.total}`"
              :value-style="{ color: '#666' }"
            />
          </div>

          <a-spin size="large">
            <template #indicator>
              <LoadingOutlined style="font-size: 48px; color: #1890ff;" spin />
            </template>
          </a-spin>
          <div class="loading-text">
            {{ isTesting ? '正在批量测试质控点...' : '正在进行质控分析...' }}
          </div>
          <div class="loading-tip">
            <template v-if="isTesting && testProgress.total > 0">
              已完成 {{ testProgress.completed }}/{{ testProgress.total }} 条
              <span v-if="testProgress.currentRuleName" style="margin-left: 8px; opacity: 0.7;">
                ({{ testProgress.currentRuleName }})
              </span>
            </template>
            <template v-else>
              AI 正在深度分析病历内容，请稍候
            </template>
          </div>

          <!-- 实时问题流（在批量测试过程中逐条展示已发现的问题） -->
          <div v-if="realtimeIssueResults.length > 0" class="current-result-stream">
            <h3 class="stream-title">已发现的问题</h3>
            <a-collapse
              ghost
              :bordered="false"
              class="stream-results-collapse"
            >
              <a-collapse-panel
                v-for="result in realtimeIssueResults"
                :key="result.ruleId"
                :header="`${result.ruleId} · ${result.ruleName}`"
                class="stream-result-panel"
              >
                <div class="stream-result-body">
                  <p class="stream-result-findings">
                    {{ result.findings || '发现问题，但模型未提供详细说明。' }}
                  </p>
                  <p v-if="result.evidence" class="stream-result-evidence">
                    <span class="label">证据：</span>
                    <span>{{ result.evidence }}</span>
                  </p>
                </div>
              </a-collapse-panel>
            </a-collapse>
          </div>

          <a-button
            danger
            size="large"
            @click="isTesting ? stopBatchTest() : stopProductionQC()"
            style="margin-top: 24px;"
          >
            <template #icon><StopOutlined /></template>
            停止分析
          </a-button>
        </div>

        <!-- 结果内容 -->
        <div v-else-if="productionResult && productionResult.data" class="current-result-content">
          <!-- 统计摘要 -->
          <div class="modal-summary">
            <a-statistic
              title="合规率"
              :value="productionResult.data.evaluation_summary?.compliance_rate || 0"
              suffix="%"
              :value-style="{ color: (productionResult.data.evaluation_summary?.compliance_rate || 0) >= 70 ? '#16a34a' : '#dc2626' }"
            />
            <a-statistic
              title="符合要求"
              :value="productionEvaluationStats.passed"
              suffix="条"
              :value-style="{ color: '#16a34a' }"
            />
            <a-statistic
              title="不适用"
              :value="productionEvaluationStats.notApplicable"
              suffix="条"
              :value-style="{ color: '#0ea5e9' }"
            />
            <a-statistic
              title="发现问题"
              :value="productionEvaluationStats.issues"
              suffix="条"
              :value-style="{ color: '#ea580c' }"
            />
            <a-statistic
              title="评估规则"
              :value="productionEvaluationStats.total"
              suffix="条"
            />
          </div>

          <!-- 性能指标卡片 -->
          <div v-if="productionPerformanceMetrics.totalTime > 0 || productionPerformanceMetrics.totalTokens > 0" class="summary-metrics compact">
            <div class="metric-item">
              <div class="metric-label">累计耗时</div>
              <div class="metric-value">{{ formatSeconds(productionPerformanceMetrics.totalTime) }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">平均耗时</div>
              <div class="metric-value">{{ formatSeconds(productionAverageTime) }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">Token 消耗</div>
              <div class="metric-value">{{ formatTokens(productionPerformanceMetrics.totalTokens) }}</div>
            </div>
          </div>

          <!-- 模型和提示词方案信息 -->
          <div class="modal-info-tags">
            <a-space>
              <!-- 模式标签 -->
              <a-tag
                v-if="productionResult.data.prompt_mode"
                :color="getModeTagColor(productionResult.data.prompt_mode === 'sequential_batch' ? 'sequential_batch' : 'optimized_batch')"
                style="font-weight: 600;"
              >
                <template #icon>
                  <ThunderboltOutlined v-if="productionResult.data.prompt_mode !== 'sequential_batch'" />
                  <AppstoreOutlined v-else />
                </template>
                {{ productionResult.data.prompt_mode === 'sequential_batch' ? '批量测试' : '快速质控' }}
              </a-tag>

              <a-tag
                v-if="productionResult.data.evaluation_summary?.model || productionResult.data.llm_info?.model"
                color="purple"
                class="model-tag"
              >
                <template #icon><RobotOutlined /></template>
                {{ productionResult.data.evaluation_summary?.model || productionResult.data.llm_info?.model }}
              </a-tag>
              <a-tag
                v-if="productionResult.data.prompt_mode && productionResult.data.prompt_mode !== 'sequential_batch'"
                :color="getPromptModeColor(productionResult.data.prompt_mode)"
                class="prompt-mode-tag"
              >
                {{ getPromptModeLabel(productionResult.data.prompt_mode) }}
              </a-tag>
            </a-space>
          </div>

          <!-- 筛选控件 -->
          <div class="modal-filter-controls">
            <a-select v-model:value="currentResultFilter" style="width: 150px">
              <a-select-option value="all">全部</a-select-option>
              <a-select-option value="issues">仅异常</a-select-option>
              <a-select-option value="compliant">仅合规</a-select-option>
            </a-select>
          </div>

          <!-- 质控结果列表（使用折叠面板） -->
          <div class="detail-results">
            <h3 class="results-title">质控结果详情</h3>
            <a-collapse class="results-collapse">
              <a-collapse-panel
                v-for="result in filteredProductionResults"
                :key="result.rule_id"
                :header="getRuleHeader(result)"
              >
                <div class="result-detail">
                  <!-- 不适用提示 -->
                  <div v-if="isResultNotApplicable(result)" class="not-applicable-banner">
                    {{ getApplicabilityReason(result as any) || '该规则不适用于当前病历。' }}
                  </div>

                  <!-- 证据警告 -->
                  <div v-if="hasEvidenceWarning(result as any)" class="evidence-warning inline-warning">
                    <WarningOutlined /> 证据未在病历原文中匹配，建议复核。
                  </div>

                  <!-- 检查发现 -->
                  <div class="result-section">
                    <h4 class="section-title">
                      <ExclamationCircleOutlined />
                      检查发现
                    </h4>
                    <p class="section-content">{{ result.findings || '无' }}</p>
                  </div>

                  <!-- 证据引用 -->
                  <div v-if="result.evidence" class="result-section">
                    <h4 class="section-title">
                      <FileTextOutlined />
                      证据引用
                    </h4>
                    <p class="section-content evidence-text">{{ result.evidence }}</p>
                  </div>

                  <!-- 改进建议 -->
                  <div v-if="result.suggestion" class="result-section">
                    <h4 class="section-title">
                      <CheckCircleOutlined />
                      改进建议
                    </h4>
                    <p class="section-content">{{ result.suggestion }}</p>
                  </div>

                  <!-- 元数据 -->
                  <div class="result-meta">
                    <a-space>
                      <a-tag v-if="result.confidence !== undefined && result.confidence !== null">
                        置信度: {{ formatConfidence(result as any) }}
                      </a-tag>
                      <a-tag v-if="result.metadata?.tokens_used || result.metadata?.token_usage">
                        Token: {{ result.metadata.tokens_used || result.metadata.token_usage }}
                      </a-tag>
                      <a-tag v-if="result.metadata?.api_time || result.metadata?.duration">
                        耗时: {{ (result.metadata.api_time || result.metadata.duration).toFixed(2) }}s
                      </a-tag>
                    </a-space>
                  </div>
                </div>
              </a-collapse-panel>
            </a-collapse>
          </div>
        </div>
        <a-empty v-else description="暂无质控结果" />
      </a-tab-pane>

      <!-- 历史质控结果 Tab -->
      <a-tab-pane key="history" tab="历史质控结果">
        <div class="history-content">
          <!-- 筛选控件 -->
          <div class="history-filters">
            <a-space wrap>
              <a-select
                v-model:value="historyFilters.documentType"
                placeholder="文书类型"
                style="width: 150px"
                allowClear
              >
                <a-select-option value="入院记录">入院记录</a-select-option>
                <a-select-option value="病程记录">病程记录</a-select-option>
                <a-select-option value="手术记录">手术记录</a-select-option>
                <a-select-option value="出院记录">出院记录</a-select-option>
              </a-select>

              <a-select
                v-model:value="historyFilters.mode"
                placeholder="质控模式"
                style="width: 150px"
                allowClear
              >
                <a-select-option value="sequential_batch">
                  <AppstoreOutlined style="margin-right: 4px;" />
                  批量测试
                </a-select-option>
                <a-select-option value="optimized_batch">
                  <ThunderboltOutlined style="margin-right: 4px;" />
                  快速质控
                </a-select-option>
              </a-select>

              <a-select
                v-model:value="historyFilters.hasIssues"
                placeholder="合规状态"
                style="width: 150px"
                allowClear
              >
                <a-select-option :value="false">全部合规</a-select-option>
                <a-select-option :value="true">存在异常</a-select-option>
              </a-select>

              <a-button type="primary" @click="loadHistoryRecords">
                <template #icon><SearchOutlined /></template>
                查询
              </a-button>

              <a-button @click="resetHistoryFilters">
                <template #icon><ReloadOutlined /></template>
                重置
              </a-button>
            </a-space>
          </div>

          <!-- 历史记录列表 -->
          <a-list
            :loading="historyLoading"
            :data-source="historyRecords"
            :pagination="{
              current: historyPagination.current,
              pageSize: historyPagination.pageSize,
              total: historyPagination.total,
              showSizeChanger: true,
              showTotal: (total: number) => `共 ${total} 条记录`,
              onChange: handleHistoryPageChange,
              onShowSizeChange: handleHistoryPageChange
            }"
            class="history-list"
          >
            <template #renderItem="{ item }">
              <a-list-item class="history-list-item" @click="viewHistoryDetail(item)">
                <div class="history-item-content">
                  <div class="history-item-header">
                    <div class="history-item-time">
                      <ClockCircleOutlined />
                      <span>{{ formatDateTime(item.created_at) }}</span>
                    </div>
                    <a-space :size="8">
                      <!-- 批量/快速标识 -->
                      <a-tag
                        :color="getModeTagColor(item.mode)"
                        style="margin: 0; font-weight: 600;"
                      >
                        <template #icon>
                          <ThunderboltOutlined v-if="item.mode === 'optimized_batch'" />
                          <AppstoreOutlined v-else />
                        </template>
                        {{ getModeTagText(item.mode) }}
                      </a-tag>
                      <a-tag color="blue">{{ item.document_type }}</a-tag>
                    </a-space>
                  </div>

                  <div class="history-item-stats">
                    <div class="stat-item">
                      <span class="stat-label">合规率:</span>
                      <span :class="['stat-value', item.compliance_rate >= 70 ? 'success' : 'error']">
                        {{ item.compliance_rate }}%
                      </span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">异常数量:</span>
                      <span :class="['stat-value', item.issues_count > 0 ? 'error' : 'success']">
                        {{ item.issues_count }}条
                      </span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">质控规则:</span>
                      <span class="stat-value">{{ item.total_rules }}条</span>
                    </div>
                    <div v-if="item.model" class="stat-item">
                      <a-tag color="purple" size="small">
                        <template #icon><RobotOutlined /></template>
                        {{ item.model }}
                      </a-tag>
                    </div>
                    <div v-if="item.prompt_mode" class="stat-item">
                      <a-tag :color="promptModeConfig[item.prompt_mode]?.color || 'default'" size="small">
                        {{ promptModeConfig[item.prompt_mode]?.tag || item.prompt_mode }}
                      </a-tag>
                    </div>
                  </div>
                </div>
              </a-list-item>
            </template>
          </a-list>
        </div>
      </a-tab-pane>
    </a-tabs>
  </a-modal>

  <!-- 历史记录详情弹窗 -->
  <a-modal
    v-model:open="showHistoryDetail"
    title="质控结果详情"
    width="1200px"
    :footer="null"
    centered
    class="history-detail-modal"
  >
    <div v-if="selectedHistoryRecord" class="history-detail-content">
      <!-- 基本信息 -->
      <div class="detail-header">
        <div class="header-content">
          <div class="header-left">
            <div class="detail-info-item">
              <ClockCircleOutlined class="info-icon" />
              <span class="info-label">质控时间：</span>
              <span class="info-value">
                {{ formatDateTime(selectedHistoryRecord.created_at || selectedHistoryRecord.saved_at) }}
              </span>
            </div>
            <div class="detail-info-item">
              <FileTextOutlined class="info-icon" />
              <span class="info-label">文书类型：</span>
              <span class="info-value">{{ selectedHistoryRecord.document_type }}</span>
            </div>
            <div class="detail-info-item">
              <template v-if="selectedHistoryRecord.mode">
                <a-tag
                  :color="getModeTagColor(selectedHistoryRecord.mode)"
                  style="font-weight: 600; margin-right: 8px;"
                >
                  <template #icon>
                    <ThunderboltOutlined v-if="selectedHistoryRecord.mode === 'optimized_batch'" />
                    <AppstoreOutlined v-else />
                  </template>
                  {{ getModeTagText(selectedHistoryRecord.mode) }}
                </a-tag>
              </template>
              <template v-if="selectedHistoryRecord.model">
                <a-tag color="purple" class="model-tag" style="margin-right: 8px;">
                  <template #icon><RobotOutlined /></template>
                  {{ selectedHistoryRecord.model }}
                </a-tag>
              </template>
              <template v-if="selectedHistoryRecord.metadata?.prompt_mode || selectedHistoryRecord.prompt_mode">
                <a-tag
                  :color="getPromptModeColor(selectedHistoryRecord.metadata?.prompt_mode || selectedHistoryRecord.prompt_mode)"
                  class="prompt-mode-tag"
                >
                  {{ getPromptModeLabel(selectedHistoryRecord.metadata?.prompt_mode || selectedHistoryRecord.prompt_mode) }}
                </a-tag>
              </template>
            </div>
          </div>
          <div class="header-right">
            <a-button
              type="primary"
              @click="showOriginalMedicalText"
              class="view-original-btn"
            >
              <template #icon><FileTextOutlined /></template>
              查看原始病历
            </a-button>
            <a-button size="small" type="link" @click="showDebugInfo = !showDebugInfo">
              {{ showDebugInfo ? '隐藏调试信息' : '显示调试信息' }}
            </a-button>
          </div>
      <!-- 调试信息面板（历史记录详情） -->
      <div v-if="showDebugInfo" class="rounded-lg border border-sky-500/40 bg-sky-500/10 p-3 mb-4">
        <div class="text-sky-300 font-medium mb-2">📊 性能指标（历史记录）</div>
        <pre class="bg-slate-900/60 border border-sky-500/30 rounded p-2 text-xs text-slate-200 overflow-x-auto">{{ JSON.stringify(historyPerformance, null, 2) }}</pre>
        <div class="text-sky-300 font-medium mt-3 mb-2">🔍 后端 performance_metrics</div>
        <pre class="bg-slate-900/60 border border-sky-500/30 rounded p-2 text-xs text-slate-200 overflow-x-auto">{{ JSON.stringify(selectedHistoryRecord.payload?.performance_metrics || selectedHistoryRecord.performance || '无', null, 2) }}</pre>
        <div class="text-sky-300 font-medium mt-3 mb-2">📝 第一条规则 metadata</div>
        <pre class="bg-slate-900/60 border border-sky-500/30 rounded p-2 text-xs text-slate-200 overflow-x-auto">{{ JSON.stringify((selectedHistoryRecord.payload?.evaluation_results || [])[0]?.metadata || '无', null, 2) }}</pre>
      </div>

      <!-- 性能指标卡片（历史记录详情） -->
      <div v-if="historyPerformance" class="summary-metrics compact">
        <div class="metric-item">
          <div class="metric-label">累计耗时</div>
          <div class="metric-value">{{ formatSeconds(historyPerformance.totalTime) }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">平均耗时</div>
          <div class="metric-value">{{ formatSeconds(historyPerformance.averageTime) }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">Token 消耗</div>
          <div class="metric-value">{{ formatTokens(historyPerformance.totalTokens) }}</div>
        </div>
      </div>

        </div>
      </div>

      <!-- 统计摘要 -->
      <div class="detail-summary">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic
              title="合规率"
              :value="(selectedHistoryRecord.payload?.evaluation_summary?.compliance_rate || selectedHistoryRecord.stats?.compliance_rate || 0)"
              suffix="%"
              :value-style="{ color: (selectedHistoryRecord.payload?.evaluation_summary?.compliance_rate || 0) >= 80 ? '#52c41a' : (selectedHistoryRecord.payload?.evaluation_summary?.compliance_rate || 0) >= 60 ? '#faad14' : '#f5222d' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="异常数量"
              :value="selectedHistoryRecord.payload?.evaluation_summary?.issues_found || selectedHistoryRecord.stats?.issues || 0"
              suffix="条"
              :value-style="{ color: '#f5222d' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="质控规则"
              :value="selectedHistoryRecord.payload?.evaluation_summary?.total_rules || selectedHistoryRecord.stats?.total || 0"
              suffix="条"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="处理耗时"
              :value="(selectedHistoryRecord.performance?.totalTime || selectedHistoryRecord.performance?.processing_time || 0).toFixed(2)"
              suffix="秒"
            />
          </a-col>
        </a-row>
      </div>

      <!-- 质控结果列表 -->
      <div class="detail-results">
        <h3 class="results-title">质控结果详情</h3>
        <a-collapse v-if="selectedHistoryRecord.payload?.evaluation_results" class="results-collapse">
          <a-collapse-panel
            v-for="result in selectedHistoryRecord.payload.evaluation_results"
            :key="result.rule_id"
            :header="getRuleHeader(result)"
          >
            <div class="result-detail">
              <div class="result-section">
                <h4 class="section-title">
                  <ExclamationCircleOutlined />
                  检查发现
                </h4>
                <p class="section-content">{{ result.findings || '无' }}</p>
              </div>

              <div v-if="result.evidence" class="result-section">
                <h4 class="section-title">
                  <FileTextOutlined />
                  证据引用
                </h4>
                <p class="section-content evidence-text">{{ result.evidence }}</p>
              </div>

              <div v-if="result.suggestion" class="result-section">
                <h4 class="section-title">
                  <CheckCircleOutlined />
                  改进建议
                </h4>
                <p class="section-content">{{ result.suggestion }}</p>
              </div>

              <div class="result-meta">
                <a-space>
                  <a-tag>置信度: {{ (result.confidence * 100).toFixed(0) }}%</a-tag>
                  <a-tag v-if="result.metadata?.tokens_used">Token: {{ result.metadata.tokens_used }}</a-tag>
                  <a-tag v-if="result.metadata?.api_time">耗时: {{ result.metadata.api_time.toFixed(2) }}s</a-tag>
                </a-space>
              </div>
            </div>
          </a-collapse-panel>
        </a-collapse>
        <a-empty v-else description="暂无详细结果数据" />
      </div>
    </div>
  </a-modal>

  <!-- 原始病历文本弹窗 -->
  <a-modal
    v-model:open="showOriginalText"
    title="原始病历原文"
    width="800px"
    :footer="null"
    centered
    class="original-text-modal"
  >
    <div class="original-text-content">
      <a-textarea
        v-model:value="originalMedicalTextContent"
        :rows="20"
        readonly
        class="original-text-area"
      />
      <div class="text-info">
        <span>字数：{{ originalMedicalTextContent.length }} 字</span>
      </div>
    </div>
  </a-modal>

  <!-- LLM 设置抽屉 -->
  <a-drawer
    v-model:open="llmSettingsVisible"
    title="LLM 配置"
    width="80%"
    placement="right"
    :destroyOnClose="true"
  >
    <template #extra>
      <a-space>
        <a-button @click="llmSettingsVisible = false">关闭</a-button>
      </a-space>
    </template>
    <LLMApiConfig />
  </a-drawer>
</div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  SettingOutlined,
  BranchesOutlined,
  AppstoreOutlined,
  ApartmentOutlined,
  SolutionOutlined,
  FileTextOutlined,
  ScissorOutlined,
  HomeOutlined,
  SearchOutlined,
  EyeOutlined,
  QuestionCircleOutlined,
  ClockCircleOutlined,
  ApiOutlined,
  RobotOutlined,
  DownOutlined,
  UpOutlined,
  ReloadOutlined,
  HistoryOutlined,
  StopOutlined,
  LoadingOutlined
} from '@ant-design/icons-vue'
import {
  PRESET_ADMISSION_RECORD,
  filterAdmissionRecordRules,
  filterRulesByDocumentType,
  DOCUMENT_TYPE_CONFIGS,
  RULE_CATEGORIES,
  categorizeRules,
  filterRules,
  type BatchTestResult,
  type BatchTestProgress,
  type DocumentTypeConfig,
  type RuleCategory,
  type RuleSeries
} from '@/utils/batchTestHelpers'
import { testQCRule, batchEvaluateQC, getQCHistoryList, getQCHistoryDetail, getLatestQCResult } from '@/api/qc'
import type { TestQCRuleData, BatchQCEvaluateResponse, QCHistoryRecord } from '@/api/qc'
import customRules from '../../backend/app/data/custom_rules_33.json'
import { SAMPLE_MEDICAL_RECORDS, getSampleRecordById, type SampleMedicalRecord } from '@/utils/sampleMedicalRecords'
import LLMApiConfig from '@/components/LLMApiConfig.vue'

// Props
interface Props {
  demoMode?: boolean  // 演示模式（隐藏导航栏和标签页）
}

const props = withDefaults(defineProps<Props>(), {
  demoMode: false
})

const router = useRouter()
const route = useRoute()

// 检测是否在演示模式下运行（通过URL参数或props）
const isDemoMode = ref(props.demoMode || route.query.demo === 'true')

// 批量质控来源：泸县33条规则 / 泸县存量质控规则
const batchSource = computed(() => (route.query.source as string | undefined) || 'custom')
const batchSeries = computed<RuleSeries>(() => (batchSource.value === 'lx_legacy' ? 'lxe' : 'lx'))
const batchDescription = computed(() =>
  batchSource.value === 'lx_legacy'
    ? '泸县存量质控规则：基于存量质控点（LXE 扩展规则）进行批量质控评估。'
    : '泸县33条质控规则：维护本地自定义质控点，支持批量评估与测试。'
)

// API端点配置
const apiEndpoints = computed(() => {
  if (isDemoMode.value) {
    return {
      save: '/api/v1/demo/qc-results/save',
      history: '/api/v1/demo/qc-results/history',
      detail: '/api/v1/demo/qc-results',
      latest: '/api/v1/demo/qc-results/latest'
    }
  } else {
    return {
      save: '/api/v1/qc/sichuan/results/save',
      history: '/api/v1/qc/sichuan/results/history',
      detail: '/api/v1/qc/sichuan/results',
      latest: '/api/v1/qc/sichuan/results/latest'
    }
  }
})

// LLM 设置相关
const llmSettingsVisible = ref(false)

// Tab 导航状态：根据来源设置默认高亮
const activeTab = ref(batchSource.value === 'lx_legacy' ? 'lx_legacy' : 'custom')

// 数据状态
const currentDocumentType = ref<string>('admission_record') // 当前选中的病历类型
const documentTypeConfigs = ref<DocumentTypeConfig[]>(DOCUMENT_TYPE_CONFIGS)
const iconComponents: Record<string, any> = {
  admission: SolutionOutlined,
  course: FileTextOutlined,
  operation: ScissorOutlined,
  discharge: HomeOutlined
}
const iconColors: Record<string, string> = {
  admission: '#2563eb',
  course: '#16a34a',
  operation: '#f97316',
  discharge: '#7c3aed'
}
const iconBgColors: Record<string, string> = {
  admission: 'rgba(37, 99, 235, 0.12)',
  course: 'rgba(22, 163, 74, 0.12)',
  operation: 'rgba(249, 115, 22, 0.12)',
  discharge: 'rgba(124, 58, 237, 0.12)'
}
const medicalText = ref(PRESET_ADMISSION_RECORD)
const originalMedicalText = ref(PRESET_ADMISSION_RECORD) // 保存原始文本用于检测修改
const admissionRules = ref<any[]>([])
const selectedRuleIds = ref<string[]>([])
const isTesting = ref(false)
const testResults = ref<BatchTestResult[]>([])
const testProgress = ref<BatchTestProgress>({
  total: 0,
  completed: 0
})

// 快速质控评估状态
const isProductionTesting = ref(false)
const productionResult = ref<BatchQCEvaluateResponse | null>(null)
const showResultsModal = ref(false)
const showTestResultsDrawer = ref(false) // 控制批量测试结果抽屉
const productionAbortController = ref<AbortController | null>(null) // 用于取消请求
type ResultFilter = 'all' | 'issues' | 'compliant'
const resultFilter = ref<ResultFilter>('all')
const currentResultFilter = ref<ResultFilter>('all') // 用于"本次质控结果"标签页的筛选
const resultFilterOptions: { label: string; value: ResultFilter }[] = [
  { label: '全部', value: 'all' },
  { label: '仅异常', value: 'issues' },
  { label: '仅合规', value: 'compliant' }
]
const expandedResultKeys = ref<string[]>([])

// 提示词优化方案选择
const selectedPromptMode = ref<string>('plan_a') // 默认使用方案A
const promptModeConfig: Record<string, { tag: string; description: string; color: string }> = {
  current: {
    tag: '当前模式',
    description: '只使用 rule_id + name + description，Token消耗最低但准确率较低（0%）',
    color: 'default'
  },
  plan_a: {
    tag: '高效模式',
    description: '采用优化提示词设计，仅提取检查要点进行批量评估，相比传统方式可节省80%的Token消耗和成本（准确率67%）',
    color: 'green'
  },
  plan_b: {
    tag: '标准模式',
    description: '使用完整 custom_prompt，包含所有质控指导信息，Token消耗最高（准确率56%）',
    color: 'blue'
  },
  plan_c: {
    tag: '平衡模式',
    description: '提取检查要点和判定逻辑，在Token消耗和准确率之间取得平衡（准确率44%）',
    color: 'orange'
  }
}

// 新增：搜索和筛选状态
const searchText = ref('')
const filterDefectLevel = ref<string | undefined>(undefined)
const filterComplexity = ref<string | undefined>(undefined)

// 质控结果历史记录状态
const showHistoryModal = ref(false)
const currentTab = ref<'current' | 'history'>('current')
const historyRecords = ref<QCHistoryRecord[]>([])
const historyLoading = ref(false)
const historyPagination = ref({
  current: 1,
  pageSize: 20,
  total: 0
})
const historyFilters = ref<{
  documentType?: string
  mode?: string
  dateRange?: [string, string]
  hasIssues?: boolean

}>({})

// 调试信息开关（历史详情）
const showDebugInfo = ref(false)

// 历史记录的性能指标（后端优先，缺失则用 metadata 聚合）
const historyPerformance = computed(() => {
  const record = selectedHistoryRecord.value
  if (!record) return null
  const perf = record.payload?.performance_metrics || record.performance
  const results = record.payload?.evaluation_results || []
  const num = (v: any) => Number(v ?? 0) || 0

  if (perf) {
    const totalTime = num((perf as any).totalTime ?? (perf as any).processing_time ?? (perf as any).total_time)
    const totalTokens = num((perf as any).totalTokens ?? (perf as any).token_usage ?? (perf as any).tokens_used)
    const n = results.length
    return {
      source: 'backend',
      n,
      totalTime,
      totalTokens,
      averageTime: n ? totalTime / n : totalTime
    }
  }

  const totalTime = results.reduce((s: number, r: any) => s + num(r?.metadata?.api_time ?? r?.metadata?.duration), 0)
  const totalTokens = results.reduce((s: number, r: any) => s + num(r?.metadata?.tokens_used ?? r?.metadata?.token_usage), 0)
  const n = results.length
  return { source: 'aggregated', n, totalTime, totalTokens, averageTime: n ? totalTime / n : 0 }
})


const selectedHistoryRecord = ref<any>(null)
const showHistoryDetail = ref(false)
const expandedCategories = ref<string[]>([]) // 默认展开的分类

// 新增：病历摘要显示控制
const showFullMedicalText = ref(false) // 默认不展开完整病历
const showMedicalTextModal = ref(false) // 病历文本弹窗控制

// 原始病历文本显示
const showOriginalText = ref(false)
const originalMedicalTextContent = ref('')

// 新增：示例病历相关
const selectedSampleRecord = ref<string | undefined>(undefined) // 当前选中的示例病历ID
const availableSampleRecords = computed(() => {
  // 根据当前文书类型过滤示例病历
  return SAMPLE_MEDICAL_RECORDS.filter(record => {
    // 如果是入院记录，显示入院记录示例
    if (currentDocumentType.value === 'admission_record') {
      return record.type === 'admission_record'
    }
    // 如果是手术记录，显示手术记录示例
    if (currentDocumentType.value === 'operation_record') {
      return record.type === 'operation_record'
    }
    // 其他类型显示所有示例
    return true
  })
})

// 新增：病历摘要信息提取
const medicalSummary = computed(() => {
  const text = medicalText.value
  if (!text) return null

  // 提取关键信息
  const patientInfoMatch = text.match(/患者信息[：:]\s*([^，,]+)/)
  const ageMatch = text.match(/(\d+)岁/)
  const genderMatch = text.match(/([男女])/)
  const departmentMatch = text.match(/入院科室[：:]\s*([^，,。\n]+)/)
  const chiefComplaintMatch = text.match(/主诉[：:]\s*([^。\n]+)/)
  const diagnosisMatch = text.match(/入院诊断[：:]\s*(.+?)(?:\n|$)/)

  return {
    patientInfo: patientInfoMatch ? patientInfoMatch[1].trim() : '未知',
    age: ageMatch ? ageMatch[1] + '岁' : '未知',
    gender: genderMatch ? genderMatch[1] : '未知',
    department: departmentMatch ? departmentMatch[1].trim() : '未知',
    chiefComplaint: chiefComplaintMatch ? chiefComplaintMatch[1].trim() : '未记录',
    diagnosis: diagnosisMatch ? diagnosisMatch[1].trim() : '未记录'
  }
})

// 检查文本是否被修改
const hasUnsavedChanges = computed(() => {
  return medicalText.value.trim() !== originalMedicalText.value.trim()
})

// 当前选中的病历类型配置
const currentConfig = computed(() => {
  return documentTypeConfigs.value.find(c => c.key === currentDocumentType.value) || documentTypeConfigs.value[0]
})

// 为每个类型计算质控点数量
const documentTypeConfigsWithCount = computed(() => {
  return documentTypeConfigs.value.map(config => ({
    ...config,
    ruleCount: filterRulesByDocumentType(customRules, config.key, batchSeries.value).length
  }))
})

// 新增：过滤后的质控规则
const filteredRules = computed(() => {
  return filterRules(
    admissionRules.value,
    searchText.value,
    filterDefectLevel.value,
    filterComplexity.value
  )
})

// 新增：分类后的质控规则
const categorizedRulesMap = computed(() => {
  return categorizeRules(filteredRules.value)
})

// 新增：转换为数组格式用于 v-for
const categorizedRulesArray = computed(() => {
  const entries = Array.from(categorizedRulesMap.value.entries())
  // 按照分类顺序排序
  return entries.sort((a, b) => {
    const categoryA = RULE_CATEGORIES.find(c => c.key === a[0])
    const categoryB = RULE_CATEGORIES.find(c => c.key === b[0])
    return (categoryA?.order || 999) - (categoryB?.order || 999)
  })
})

// 新增：全选状态
const isAllSelected = computed(() => {
  return filteredRules.value.length > 0 &&
         filteredRules.value.every(rule => selectedRuleIds.value.includes(rule.rule_id))
})

// 新增：半选状态
const isIndeterminate = computed(() => {
  const selectedCount = filteredRules.value.filter(rule =>
    selectedRuleIds.value.includes(rule.rule_id)
  ).length
  return selectedCount > 0 && selectedCount < filteredRules.value.length
})

const visibleTestResults = computed(() => {
  return testResults.value.filter(result => {
    if (resultFilter.value === 'issues') {
      return result.error || isResultNonCompliant(result)
    }
    if (resultFilter.value === 'compliant') {
      return !result.error && isResultCompliant(result)
    }
    return true
  })
})

const batchPerformanceMetrics = computed(() => {
  if (testResults.value.length === 0) {
    return {
      totalTokens: 0,
      totalTime: 0,
      avgTime: 0
    }
  }

  const totalTokens = testResults.value.reduce((sum, result) => {
    const meta = result.metadata || {}
    return sum + Number(meta.tokens_used ?? meta.token_usage ?? 0)
  }, 0)

  const totalTime = testResults.value.reduce((sum, result) => {
    const meta = result.metadata || {}
    return sum + Number(meta.api_time ?? 0)
  }, 0)

  return {
    totalTokens,
    totalTime,
    avgTime: totalTime / Math.max(testResults.value.length, 1)
  }
})

const batchEvaluationStats = computed(() => {
  const results = testResults.value
  if (!results.length) {
    return {
      total: 0,
      compliant: 0,
      passed: 0,
      notApplicable: 0,
      issues: 0,
      errors: 0
    }
  }

  let compliant = 0
  let notApplicable = 0
  let issues = 0
  let errors = 0

  results.forEach(result => {
    if (getResultStatusValue(result as any) === 'error') {
      errors++
      return
    }
    if (isResultNotApplicable(result)) {
      notApplicable++
      compliant++
      return
    }
    if (isResultCompliant(result)) {
      compliant++
    } else {
      issues++
    }
  })

  const passed = Math.max(compliant - notApplicable, 0)

  return {
    total: results.length,
    compliant,
    passed,
    notApplicable,
    issues,
    errors
  }
})

// 实时批量测试统计（用于加载过程中显示）
const realtimeBatchStats = computed(() => {
  const stats = batchEvaluationStats.value
  const complianceRate = stats.total > 0 ? Math.round((stats.compliant / stats.total) * 100) : 0

  return {
    completed: stats.total,
    passed: stats.passed,
    notApplicable: stats.notApplicable,
    issues: stats.issues,
    complianceRate: complianceRate
  }
})

const batchComplianceRate = computed(() => {
  const stats = batchEvaluationStats.value
  if (!stats.total) return '0.00 %'
  const rate = (stats.compliant / stats.total) * 100
  return `${rate.toFixed(2)} %`
})

// 批量测试过程中的“实时问题列表”（仅包含已完成规则中的异常项）
const realtimeIssueResults = computed(() => {
  return testResults.value.filter(result => !result.error && isResultNonCompliant(result))
})

const productionPerformanceMetrics = computed(() => {
  const data = productionResult.value?.data
  const num = (v: any) => Number(v ?? 0) || 0
  if (!data) return { totalTokens: 0, totalTime: 0 }

  const metrics = (data as any).performance_metrics
  if (metrics) {
    return {
      totalTokens: num((metrics as any).token_usage ?? (metrics as any).tokens_used),
      totalTime: num((metrics as any).processing_time ?? (metrics as any).total_time)
    }
  }

  const results = (data as any).evaluation_results || []
  const totalTokens = results.reduce((s: number, r: any) => s + num(r?.metadata?.tokens_used ?? r?.metadata?.token_usage), 0)
  const totalTime = results.reduce((s: number, r: any) => s + num(r?.metadata?.api_time ?? r?.metadata?.duration), 0)
  return { totalTokens, totalTime }
})

const productionAverageTime = computed(() => {
  const n = productionResult.value?.data?.evaluation_results?.length || 0
  const total = productionPerformanceMetrics.value.totalTime
  return n ? total / n : total
})

// 筛选后的快速质控结果
const filteredProductionResults = computed(() => {
  const results = productionResult.value?.data?.evaluation_results || []
  if (currentResultFilter.value === 'all') {
    return results
  }
  if (currentResultFilter.value === 'issues') {
    return results.filter(r => !isResultCompliant(r) && !isResultNotApplicable(r))
  }
  if (currentResultFilter.value === 'compliant') {
    return results.filter(r => isResultCompliant(r) || isResultNotApplicable(r))
  }
  return results
})

const productionEvaluationStats = computed(() => {
  const results = productionResult.value?.data?.evaluation_results || []
  if (!results.length) {
    return {
      total: 0,
      compliant: 0,
      passed: 0,
      notApplicable: 0,
      issues: 0,
      errors: 0
    }
  }

  let compliant = 0
  let notApplicable = 0
  let issues = 0
  let errors = 0

  results.forEach(result => {
    if (getResultStatusValue(result as any) === 'error') {
      errors++
      return
    }
    if (isResultNotApplicable(result)) {
      notApplicable++
      compliant++
      return
    }
    if (isResultCompliant(result)) {
      compliant++
    } else {
      issues++
    }
  })

  const passed = Math.max(compliant - notApplicable, 0)

  return {
    total: results.length,
    compliant,
    passed,
    notApplicable,
    issues,
    errors
  }
})
const formatSeconds = (value?: number) => {
  if (!value || Number.isNaN(value)) return '--'
  if (value < 0.1) {
    return `${Math.round(value * 1000)} ms`
  }
  return `${value.toFixed(2)} s`
}

const formatTokens = (value?: number) => {
  if (!value || Number.isNaN(value)) return '--'
  return value.toLocaleString()
}

const normalizeIssues = (data?: TestQCRuleData): BatchTestResult['issues'] => {
  if (!data) return []
  if (Array.isArray(data.issues) && data.issues.length > 0) {
    return data.issues.map(issue => ({
      description: issue.description || (issue as any).title || '',
      evidence: issue.evidence || (issue as any).reference || ''
    }))
  }

  const status = data.status || (data.is_compliant === false ? 'non_compliant' : 'compliant')
  if (status !== 'compliant' && data.findings) {
    return [
      {
        description: data.findings,
        evidence: data.evidence
      }
    ]
  }

  return []
}

// 新增：切换全选
const toggleSelectAll = () => {
  if (isAllSelected.value) {
    // 取消选择所有过滤后的规则
    const filteredRuleIds = filteredRules.value.map(r => r.rule_id)
    selectedRuleIds.value = selectedRuleIds.value.filter(id => !filteredRuleIds.includes(id))
  } else {
    // 选择所有过滤后的规则（合并到已选列表）
    const filteredRuleIds = filteredRules.value.map(r => r.rule_id)
    selectedRuleIds.value = [...new Set([...selectedRuleIds.value, ...filteredRuleIds])]
  }
}

// 新增：切换单个规则选择
const toggleRuleSelection = (ruleId: string) => {
  if (isTesting.value) return

  const index = selectedRuleIds.value.indexOf(ruleId)
  if (index > -1) {
    selectedRuleIds.value.splice(index, 1)
  } else {
    selectedRuleIds.value.push(ruleId)
  }
}

// 新增：获取分类标题文本
const getCategoryHeaderText = (categoryKey: string, count: number): string => {
  const category = RULE_CATEGORIES.find(c => c.key === categoryKey)
  return category ? `${category.label} (${count}条)` : `未分类 (${count}条)`
}

// 新增：获取分类图标
const getCategoryIcon = (categoryKey: string): string => {
  const category = RULE_CATEGORIES.find(c => c.key === categoryKey)
  return category?.icon || '📌'
}

// 新增：规范化缺陷等级（移除"缺陷"后缀）
const normalizeDefectLevel = (level?: string): string => {
  if (!level) return '一般'
  return level.replace('缺陷', '')
}

// 新增：规范化复杂度（移除"复杂度"后缀）
const normalizeComplexity = (complexity?: string): string => {
  if (!complexity) return '中'
  return complexity.replace('复杂度', '')
}

// 新增：获取缺陷等级颜色
const getDefectLevelColor = (level?: string): string => {
  const normalized = normalizeDefectLevel(level)
  const levelMap: Record<string, string> = {
    '严重': 'error',
    '一般': 'warning',
    '轻微': 'success'
  }
  return levelMap[normalized] || 'default'
}

// 新增：获取缺陷等级图标
const getDefectLevelIcon = (level?: string): string => {
  const normalized = normalizeDefectLevel(level)
  const iconMap: Record<string, string> = {
    '严重': '🔴',
    '一般': '🟡',
    '轻微': '🟢'
  }
  return iconMap[normalized] || '🟡'
}

// 新增：获取缺陷等级CSS类名
const getDefectLevelClass = (level?: string): string => {
  const normalized = normalizeDefectLevel(level)
  const classMap: Record<string, string> = {
    '一级': 'level-high',
    '二级': 'level-medium',
    '三级': 'level-low'
  }
  return classMap[normalized] || 'level-low'
}

// 新增：获取复杂度CSS类名
const getComplexityClass = (complexity?: string): string => {
  const normalized = normalizeComplexity(complexity)
  const classMap: Record<string, string> = {
    '高': 'complexity-high',
    '中': 'complexity-medium',
    '低': 'complexity-low'
  }
  return classMap[normalized] || 'complexity-low'
}

// 保留旧的颜色函数（用于其他地方）
const getComplexityColor = (complexity?: string): string => {
  const normalized = normalizeComplexity(complexity)
  const complexityMap: Record<string, string> = {
    '高': 'orange',
    '中': 'green',
    '低': 'blue'
  }
  return complexityMap[normalized] || 'default'
}

// 保留旧的图标函数（用于其他地方）
const getComplexityIcon = (complexity?: string): string => {
  const normalized = normalizeComplexity(complexity)
  const iconMap: Record<string, string> = {
    '高': '🟠',
    '中': '🟢',
    '低': '🔵'
  }
  return iconMap[normalized] || '🟢'
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.ctrlKey && event.key === 'Enter') {
    event.preventDefault()
    if (!isTesting.value) {
      startBatchTest()
    }
  }
}

// 监听病历类型切换
watch(currentDocumentType, (newType, oldType) => {
  // 如果正在测试中，不允许切换
  if (isTesting.value) {
    message.warning('正在测试中，无法切换病历类型')
    currentDocumentType.value = oldType
    return
  }

  // 如果有未保存的修改，弹出确认框
  if (hasUnsavedChanges.value && oldType) {
    Modal.confirm({
      title: '确认切换病历类型？',
      content: '当前病历文本已修改，切换后将加载新的预置文本，未保存的修改将丢失',
      okText: '确认切换',
      cancelText: '取消',
      onOk: () => {
        loadDocumentType(newType)
      },
      onCancel: () => {
        // 取消切换，恢复到原来的类型
        currentDocumentType.value = oldType
      }
    })
  } else {
    loadDocumentType(newType)
  }
})

// 加载指定病历类型的数据
const loadDocumentType = (documentType: string) => {
  const config = documentTypeConfigs.value.find(c => c.key === documentType)
  if (!config) return

  // 1. 加载预置文本
  medicalText.value = config.presetText
  originalMedicalText.value = config.presetText

  // 2. 筛选质控点
  admissionRules.value = filterRulesByDocumentType(customRules, documentType, batchSeries.value)
  selectedRuleIds.value = admissionRules.value.map(r => r.rule_id)

  // 3. 清空测试结果
  testResults.value = []
  testProgress.value = { total: 0, completed: 0 }
  productionResult.value = null

  // 4. 清空搜索和筛选条件
  searchText.value = ''
  filterDefectLevel.value = undefined
  filterComplexity.value = undefined

  // 5. 默认折叠所有分类
  expandedCategories.value = []

  message.success(`已切换到${config.label}`)
}

// 卡片点击处理
const handleCardClick = (documentType: string) => {
  if (isTesting.value) {
    message.warning('正在测试中，无法切换文书类型')
    return
  }
  if (documentType === currentDocumentType.value) return
  currentDocumentType.value = documentType // 触发 watch
}

// 处理来自父窗口的消息（用于iframe嵌入场景）
const handleParentMessage = (event: MessageEvent) => {
  if (event.origin !== window.location.origin) return

  if (event.data.type === 'BATCH_TEST_CONFIG') {
    const config = event.data.config
    if (config.useDemoApi !== undefined) {
      isDemoMode.value = config.useDemoApi
    }
    if (config.preselectedRules && config.preselectedRules.length > 0) {
      // 预选规则
      selectedRuleIds.value = config.preselectedRules.map((r: any) => r.rule_id)
    }
  }
}

// 初始化
onMounted(() => {
  // 加载默认的入院记录类型
  loadDocumentType(currentDocumentType.value)
  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('message', handleParentMessage)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('message', handleParentMessage)
})

watch(testResults, (newResults) => {
  const existingIds = newResults.map(r => r.ruleId)
  expandedResultKeys.value = expandedResultKeys.value.filter(key => existingIds.includes(key))
  const latest = newResults[newResults.length - 1]
  if (latest && (latest.error || isResultNonCompliant(latest))) {
    if (!expandedResultKeys.value.includes(latest.ruleId)) {
      expandedResultKeys.value = [...expandedResultKeys.value, latest.ruleId]
    }
  }
}, { deep: true })

watch(visibleTestResults, (list) => {
  const visibleIds = list.map(r => r.ruleId)
  expandedResultKeys.value = expandedResultKeys.value.filter(key => visibleIds.includes(key))
})

// 计算属性
const testSummary = computed(() => {
  const stats = batchEvaluationStats.value
  if (stats.total === 0) return ''

  const parts = [
    `${stats.total}个质控点`,
    `${stats.passed}个符合`
  ]

  if (stats.notApplicable > 0) {
    parts.push(`${stats.notApplicable}个不适用`)
  }
  parts.push(`${stats.issues}个发现问题`)
  if (stats.errors > 0) {
    parts.push(`${stats.errors}个测试失败`)
  }

  return parts.join('，')
})

const summaryColor = computed(() => {
  const nonCompliantCount = testResults.value.filter(r => !r.error && isResultNonCompliant(r)).length
  return nonCompliantCount === 0 ? 'success' : 'warning'
})

// LLM 设置相关方法
const showLLMSettings = () => {
  llmSettingsVisible.value = true
}

// Tab 切换处理
const handleTabChange = (key: string) => {
  if (key === 'custom') {
    // 当前页面，不需要跳转
    return
  }
  // 跳转到质控规则管理页面的对应标签页
  router.push({ name: 'Rules', query: { tab: key } })
}

// 方法
const goBack = () => {
  const tab = batchSource.value === 'lx_legacy' ? 'lx_legacy' : 'custom'
  router.push({ name: 'Rules', query: { tab } })
}

const resetMedicalText = () => {
  medicalText.value = currentConfig.value.presetText
  originalMedicalText.value = currentConfig.value.presetText
  selectedSampleRecord.value = undefined // 清空示例选择
  message.success(`已重置为${currentConfig.value.label}预置病历文本`)
}

// 新增：处理文件上传
const handleFileUpload = (file: File) => {
  // 检查文件类型
  if (!file.name.endsWith('.txt')) {
    message.error('仅支持 .txt 文本文件')
    return false
  }

  // 检查文件大小（限制为 5MB）
  const maxSize = 5 * 1024 * 1024
  if (file.size > maxSize) {
    message.error('文件大小不能超过 5MB')
    return false
  }

  // 读取文件内容
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target?.result as string
    if (content) {
      medicalText.value = content
      selectedSampleRecord.value = undefined // 清空示例选择
      message.success(`已成功导入文件：${file.name}`)
    }
  }
  reader.onerror = () => {
    message.error('文件读取失败，请重试')
  }
  reader.readAsText(file, 'UTF-8')

  // 阻止默认上传行为
  return false
}

// 新增：处理示例病历选择
const handleSampleRecordChange = (sampleId: string | undefined) => {
  if (!sampleId) {
    // 清空选择
    return
  }

  const sample = getSampleRecordById(sampleId)
  if (sample) {
    medicalText.value = sample.content
    message.success(`已加载示例病历：${sample.name}`)
  }
}

const selectAll = () => {
  selectedRuleIds.value = admissionRules.value.map(rule => rule.rule_id)
}

const deselectAll = () => {
  selectedRuleIds.value = []
}

// 格式化日期时间
const formatDateTime = (dateStr: string) => {
  if (!dateStr) return '--'
  try {
    const date = new Date(dateStr)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  } catch (error) {
    return dateStr
  }
}

// 获取提示词方案标签
const getPromptModeLabel = (mode: string | null | undefined) => {
  if (!mode) return '未知'
  const modeConfig: Record<string, string> = {
    'plan_a': '高效模式',
    'plan_b': '标准模式',
    'plan_c': '平衡模式',
    'current': '当前模式'
  }
  return modeConfig[mode] || mode
}

// 获取提示词方案颜色
const getPromptModeColor = (mode: string | null | undefined) => {
  if (!mode) return 'default'
  const colorConfig: Record<string, string> = {
    'plan_a': 'green',
    'plan_b': 'blue',
    'plan_c': 'orange',
    'current': 'default'
  }
  return colorConfig[mode] || 'default'
}

// 获取规则标题（用于历史详情）
const getRuleHeader = (result: any) => {
  const statusIcon = result.is_compliant || result.status === 'compliant' ? '✅' :
                     result.status === 'not_applicable' ? '⊘' : '❌'
  return `${statusIcon} ${result.rule_id} - ${result.rule_name}`
}

type ResultLike = {
  status?: 'compliant' | 'non_compliant' | 'not_applicable' | 'uncertain'
  isCompliant?: boolean
  is_compliant?: boolean
  notApplicable?: boolean
  not_applicable?: boolean
  applicability?: {
    is_applicable?: boolean
    reason?: string
  }
  error?: string
  [key: string]: any
}

const getResultStatusValue = (result: ResultLike): string => {
  if (result.error) return 'error'
  if (result.status) return result.status
  if (result.notApplicable || result.not_applicable) return 'not_applicable'
  if (result.applicability && result.applicability.is_applicable === false) return 'not_applicable'
  const compliantFlag = result.isCompliant ?? result.is_compliant
  return compliantFlag === false ? 'non_compliant' : 'compliant'
}

const isResultCompliant = (result: ResultLike): boolean => {
  const status = getResultStatusValue(result)
  if (status === 'non_compliant' || status === 'error') return false
  if (status === 'uncertain') return false
  return true
}

const isResultNonCompliant = (result: ResultLike): boolean => getResultStatusValue(result) === 'non_compliant'

const isResultNotApplicable = (result: ResultLike): boolean => {
  const status = getResultStatusValue(result)
  return status === 'not_applicable'
}

const getApplicabilityReason = (result: ResultLike): string => {
  if (result.notApplicableReason) return result.notApplicableReason
  if (result.not_applicable_reason) return result.not_applicable_reason
  if (result.applicability?.reason) return result.applicability.reason
  return result.notApplicable ? '本规则不适用于该病历' : ''
}

const hasEvidenceWarning = (result: ResultLike): boolean => {
  if (result.evidenceVerified === false) return true
  if (result.evidence_verified === false) return true
  return false
}

const getResultStatusText = (result: ResultLike) => {
  if (result.error) return '测试失败'
  const status = getResultStatusValue(result)
  switch (status) {
    case 'compliant':
      return '符合要求'
    case 'not_applicable':
      return '不适用'
    case 'non_compliant':
      return '发现问题'
    case 'uncertain':
      return '结果不确定'
    default:
      return result.isCompliant ? '符合要求' : '发现问题'
  }
}

const getStatusPillClass = (result: ResultLike) => {
  const status = getResultStatusValue(result)
  if (result.error) return 'warning'
  if (status === 'non_compliant') return 'danger'
  if (status === 'not_applicable') return 'neutral'
  if (status === 'uncertain') return 'warning'
  return 'success'
}

const getIssuesTitle = (result: ResultLike) => {
  if (result.error) return '错误详情'
  if (isResultNotApplicable(result)) return '不适用原因'
  return isResultCompliant(result) ? '合规依据' : '问题列表'
}

const getIssuesEmptyText = (result: ResultLike) => {
  if (result.error) return '无更多错误详情'
  if (isResultNotApplicable(result)) {
    return getApplicabilityReason(result) || '该规则不适用于当前病历。'
  }
  return isResultCompliant(result)
    ? '系统未检测到问题，病历内容符合规则要求。'
    : '暂无详细问题描述。'
}

const formatConfidence = (result: ResultLike) => {
  if (result.error || result.confidence === undefined || result.confidence === null) return '--'
  if (getResultStatusValue(result) === 'uncertain') return '--'
  return `${Math.round(result.confidence * 100)}%`
}

const handleCollapseChange = (keys: string[] | string) => {
  if (Array.isArray(keys)) {
    expandedResultKeys.value = keys
  } else if (typeof keys === 'string') {
    expandedResultKeys.value = keys ? [keys] : []
  } else {
    expandedResultKeys.value = []
  }
}

// 合规率徽章样式
const getComplianceBadgeClass = (rate: number) => {
  if (rate >= 90) return 'excellent'
  if (rate >= 70) return 'good'
  if (rate >= 50) return 'fair'
  return 'poor'
}

const saveQCResultToServer = async (payload: Record<string, any>) => {
  try {
    const response = await fetch(apiEndpoints.value.save, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      throw new Error(await response.text())
    }
  } catch (error) {
    console.warn('自动保存质控结果失败', error)
  }
}

// 加载质控历史记录
const loadHistoryRecords = async () => {
  historyLoading.value = true
  try {
    const params: any = {
      page: historyPagination.value.current,
      page_size: historyPagination.value.pageSize
    }

    if (historyFilters.value.documentType) {
      params.document_type = historyFilters.value.documentType
    }

    if (historyFilters.value.mode) {
      params.mode = historyFilters.value.mode
    }

    if (historyFilters.value.dateRange && historyFilters.value.dateRange.length === 2) {
      params.start_date = historyFilters.value.dateRange[0]
      params.end_date = historyFilters.value.dateRange[1]
    }

    if (historyFilters.value.hasIssues !== undefined) {
      params.has_issues = historyFilters.value.hasIssues
    }

    // Demo 模式使用演示接口，其返回结构为 { success, data }
    if (isDemoMode.value) {
      const queryString = new URLSearchParams(params).toString()
      const fetchResponse = await fetch(`${apiEndpoints.value.history}?${queryString}`)
      const response = await fetchResponse.json()

      if (response.success && response.data) {
        historyRecords.value = response.data.records
        historyPagination.value.total = response.data.total
      } else {
        message.error(response.message || '加载历史记录失败')
      }
    } else {
      // 正式接口直接返回 {records, total, ...}，使用封装的 API 适配
      const resp = await getQCHistoryList(params)
      if (resp.success && resp.data) {
        // 按来源过滤：泸县33条 vs 泸县存量质控规则
        const allRecords = resp.data.records || []
        const filtered = allRecords.filter((record: any) => {
          const source = record.metadata?.source
          if (batchSource.value === 'lx_legacy') {
            return source === 'lx_legacy'
          }
          // 默认视为泸县33条规则：排除明确标记为 lx_legacy 的记录
          return source !== 'lx_legacy'
        })

        historyRecords.value = filtered
        historyPagination.value.total = filtered.length
      } else {
        message.error(resp.message || '加载历史记录失败')
      }
    }
  } catch (error: any) {
    message.error(error?.message || '加载历史记录失败')
  } finally {
    historyLoading.value = false
  }
}

// 查看历史记录详情
const viewHistoryDetail = async (record: QCHistoryRecord) => {
  try {
    // 使用动态API端点
    const fetchResponse = await fetch(`${apiEndpoints.value.detail}/${record.id}`)
    const response = await fetchResponse.json()
    if (response.success && response.data) {
      selectedHistoryRecord.value = response.data
      showHistoryDetail.value = true
    } else {
      message.error(response.message || '加载详情失败')
    }
  } catch (error: any) {
    message.error(error?.message || '加载详情失败')
  }
}

// 查看原始病历文本
const showOriginalMedicalText = () => {
  if (selectedHistoryRecord.value) {
    // 从历史记录中提取原始病历文本（多个可能的字段位置）
    const medicalText = selectedHistoryRecord.value.medical_text ||
                       selectedHistoryRecord.value.payload?.medical_text ||
                       selectedHistoryRecord.value.payload?.document?.medical_text ||
                       selectedHistoryRecord.value.payload?.document?.content ||
                       ''

    if (medicalText) {
      originalMedicalTextContent.value = medicalText
      showOriginalText.value = true
    } else {
      message.warning('该历史记录未保存原始病历文本，请重新执行质控以保存完整数据')
    }
  } else {
    message.warning('无法获取原始病历文本')
  }
}

// 处理历史记录分页变化
const handleHistoryPageChange = (page: number, pageSize: number) => {
  historyPagination.value.current = page
  historyPagination.value.pageSize = pageSize
  loadHistoryRecords()
}

// 重置历史记录筛选
const resetHistoryFilters = () => {
  historyFilters.value = {}
  historyPagination.value.current = 1
  loadHistoryRecords()
}

// 监听历史弹窗打开，自动加载数据
watch(showHistoryModal, (newVal) => {
  if (newVal && currentTab.value === 'history') {
    loadHistoryRecords()
  }
})

// 监听Tab切换
watch(currentTab, (newVal) => {
  if (newVal === 'history' && showHistoryModal.value) {
    loadHistoryRecords()
  }
})

const startBatchTest = async () => {
  if (selectedRuleIds.value.length === 0) {
    message.warning('请至少选择一个质控点')
    return
  }

  if (!medicalText.value.trim()) {
    message.warning('请输入病历文本')
    return
  }

  isTesting.value = true
  isProductionTesting.value = true
  productionResult.value = null

  // 打开质控结果弹窗，显示加载状态
  showHistoryModal.value = true
  currentTab.value = 'current'

  testResults.value = []
  expandedResultKeys.value = []
  resultFilter.value = 'all'
  testProgress.value = {
    total: selectedRuleIds.value.length,
    completed: 0
  }

  // 获取当前LLM配置信息（包含模型名称）
  let currentModel: string | null = null
  try {
    const configResponse = await fetch('/api/v1/qc/sichuan/current-config', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    if (configResponse.ok) {
      const configResult = await configResponse.json()
      if (configResult.success && configResult.data?.model) {
        currentModel = configResult.data.model
      }
    }
  } catch (error) {
    console.warn('获取当前LLM配置失败:', error)
  }

  // 串行测试每个质控点
  for (const ruleId of selectedRuleIds.value) {
    // 检查是否被停止
    if (!isTesting.value) {
      message.info('批量测试已停止')
      break
    }

    const rule = admissionRules.value.find(r => r.rule_id === ruleId)
    if (!rule) continue

    testProgress.value.currentRuleId = ruleId
    testProgress.value.currentRuleName = rule.name

    try {
      const response = await testQCRule({
        rule_id: ruleId,
        medical_text: medicalText.value
      })

      if (response.success && response.data) {
        const data = response.data
        testResults.value.push({
          ruleId: data.rule_id || ruleId,
          ruleName: data.rule_name || rule.name,
          isCompliant: data.is_compliant ?? true,
          status: data.status,
          findings: data.findings,
          issues: normalizeIssues(data),
          applicability: data.applicability,
          notApplicable: data.not_applicable ?? data.applicability?.is_applicable === false,
          notApplicableReason: data.not_applicable_reason ?? data.applicability?.reason,
          evidence: data.evidence,
          suggestion: data.suggestion,
          evidenceVerified: data.evidence_verified ?? true,
          confidence: data.confidence ?? 0,
          llmRawOutput: data.llm_raw_output,
          metadata: data.metadata
        })
      } else {
        testResults.value.push({
          ruleId: ruleId,
          ruleName: rule.name,
          isCompliant: false,
          status: 'uncertain',
          findings: undefined,
          issues: [],
          confidence: 0,
          error: response.message || '测试失败'
        })
      }
    } catch (error: any) {
      testResults.value.push({
        ruleId: ruleId,
        ruleName: rule.name,
        isCompliant: false,
         status: 'uncertain',
        findings: undefined,
        issues: [],
        confidence: 0,
        error: error?.message || '网络错误或服务异常'
      })
    }

    testProgress.value.completed++
  }

  isTesting.value = false
  isProductionTesting.value = false
  testProgress.value.currentRuleId = undefined
  testProgress.value.currentRuleName = undefined

  // 如果没有任何结果，直接返回
  if (testResults.value.length === 0) {
    message.warning('未完成任何测试')
    return
  }

  // 结果按规则ID排序，便于浏览
  testResults.value = [...testResults.value].sort((a, b) => a.ruleId.localeCompare(b.ruleId, 'zh-Hans-CN', { numeric: true }))

  // 转换为 productionResult 格式，以便在统一UI中显示
  const document_id = `batch_${Date.now()}`
  const stats = batchEvaluationStats.value
  const performance = batchPerformanceMetrics.value

  // 转换 testResults 为 BatchQCResult[] 格式
  const evaluation_results = testResults.value.map(result => ({
    rule_id: result.ruleId,
    rule_name: result.ruleName,
    is_compliant: result.isCompliant,
    status: result.status,
    applicability: result.applicability,
    not_applicable: result.notApplicable,
    not_applicable_reason: result.notApplicableReason,
    evidence_verified: result.evidenceVerified,
    findings: result.findings,
    evidence: result.evidence,
    suggestion: result.suggestion,
    confidence: result.confidence,
    metadata: result.metadata
  }))

  // 构建 productionResult
  productionResult.value = {
    success: true,
    data: {
      document_id: document_id,
      evaluation_summary: {
        compliance_rate: stats.total > 0 ? Math.round((stats.passed / stats.total) * 100) : 0,
        issues_found: stats.issues,
        total_rules: stats.total,
        compliant_rules: stats.passed,
        not_applicable: stats.notApplicable,
        model: currentModel || undefined  // 添加模型信息
      },
      evaluation_results: evaluation_results,
      performance_metrics: {
        processing_time: performance.totalTime,
        token_usage: performance.totalTokens,
        estimated_cost: 0
      },
      prompt_mode: 'sequential_batch', // 标记为批量测试模式
      llm_info: currentModel ? {
        model: currentModel
      } : undefined
    }
  }

  message.success('批量测试完成!')

  // 保存到服务器
  if (testResults.value.length > 0) {
    saveQCResultToServer({
      mode: 'sequential_batch',
      document_type: currentConfig.value.label,
      document_id: document_id,
      rule_ids: [...selectedRuleIds.value],
      medical_text: medicalText.value,
      medical_text_length: medicalText.value.length,
      stats: stats,
      performance: performance,
      payload: productionResult.value.data,
      results: testResults.value,
      model: currentModel || null,  // 保存使用的模型名称
      metadata: {
        trigger: 'batch_test_ui',
        source: batchSource.value
      }
    })
  }
}

const startProductionBatchQC = async () => {
  if (selectedRuleIds.value.length === 0) {
    message.warning('请至少选择一个质控点')
    return
  }

  if (!medicalText.value.trim()) {
    message.warning('请输入病历文本')
    return
  }

  isProductionTesting.value = true
  productionResult.value = null

  // 打开质控结果弹窗，显示加载状态
  showHistoryModal.value = true
  currentTab.value = 'current'

  // 创建 AbortController 用于取消请求
  productionAbortController.value = new AbortController()

  try {
    const response = await batchEvaluateQC({
      document_id: `test_${Date.now()}`,
      document_content: medicalText.value,
      document_type: currentConfig.value.label,
      rule_ids: selectedRuleIds.value,
      persist: false,
      prompt_mode: selectedPromptMode.value  // 传递选中的提示词优化方案
    })

    productionResult.value = response
    message.success(`快速质控评估完成！使用方案：${promptModeConfig[selectedPromptMode.value].tag}`)
    if (response.success && response.data) {
      saveQCResultToServer({
        mode: 'optimized_batch',
        document_type: currentConfig.value.label,
        document_id: response.data.document_id,
        rule_ids: [...selectedRuleIds.value],
        medical_text: medicalText.value,
        medical_text_length: medicalText.value.length,
        stats: productionEvaluationStats.value,
        performance: productionPerformanceMetrics.value,
        payload: response.data,
        model: response.data.evaluation_summary?.model || null,  // 保存使用的模型名称
        metadata: {
          trigger: 'quick_qc_ui',
          prompt_mode: selectedPromptMode.value,  // 记录使用的方案
          source: batchSource.value
        }
      })
    }
  } catch (error: any) {
    if (error?.name === 'AbortError' || error?.message?.includes('abort')) {
      // 用户主动取消，不显示错误
      return
    }
    message.error(error?.message || '批量质控失败')
    productionResult.value = null
  } finally {
    isProductionTesting.value = false
    productionAbortController.value = null
  }
}

// 停止批量测试（注意：这只是设置标志，实际停止在循环中处理）
const stopBatchTest = () => {
  isTesting.value = false
  // 不立即设置 isProductionTesting = false，让循环自然结束后再处理结果
}

// 停止快速质控分析
const stopProductionQC = () => {
  if (productionAbortController.value) {
    productionAbortController.value.abort()
    isProductionTesting.value = false
    message.info('已停止质控分析')
  }
}

// 查看质控结果
const handleViewResults = () => {
  showHistoryModal.value = true

  // 如果有本次质控结果，显示本次结果tab；否则显示历史记录tab
  if (productionResult.value !== null) {
    currentTab.value = 'current'
  } else {
    currentTab.value = 'history'
  }
}

// 计算结果数量文本
const getResultsCountText = computed(() => {
  if (productionResult.value !== null) {
    const total = productionResult.value?.data?.evaluation_summary?.total_rules || 0
    return `${total}条`
  }
  return ''
})

// 获取模式标签文本
const getModeTagText = (mode: string) => {
  const modeMap: Record<string, string> = {
    'optimized_batch': '快速',
    'sequential_batch': '批量',
    'single': '单条'
  }
  return modeMap[mode] || '未知'
}

// 获取模式标签颜色
const getModeTagColor = (mode: string) => {
  const colorMap: Record<string, string> = {
    'optimized_batch': 'cyan',      // 快速质控 - 青色
    'sequential_batch': 'geekblue', // 批量测试 - 蓝色
    'single': 'default'
  }
  return colorMap[mode] || 'default'
}
</script>

<style scoped lang="less">
// 导入设计系统
@import '@/styles/design-tokens.less';

.batch-rule-test {
  min-height: 100vh;
  background: #f5f7fa;
}

// 标签页样式 - 与 RulesView 一致
.rules-tabs {
  margin-bottom: 0.25rem;
}

:deep(.rules-tabs .ant-tabs-nav) {
  margin-bottom: 0.25rem;
}

:deep(.rules-tabs .ant-tabs-tab) {
  padding: 0.25rem 0.75rem;
  border-radius: 8px;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  margin-right: 8px;
}

:deep(.rules-tabs .ant-tabs-tab:hover) {
  background: #f0f7ff;
  border-color: rgba(59, 130, 246, 0.25);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.12);
}

:deep(.rules-tabs .ant-tabs-tab-active) {
  background: #ffffff;
  border-color: rgba(59, 130, 246, 0.35);
  box-shadow: 0 3px 12px rgba(59, 130, 246, 0.18);
}

:deep(.rules-tabs .ant-tabs-tab .ant-tabs-tab-btn) {
  display: flex;
  align-items: center;
  font-size: 16px !important;
  font-weight: 700 !important;
}

:deep(.rules-tabs .ant-tabs-tab .anticon) {
  margin-right: 0.25rem;
  font-size: 16px;
}

// 自定义Tab标题
:deep(.qc-tab-title) {
  font-size: 16px !important;
  font-weight: 700;
  color: #1f2937;
  line-height: 1.2;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

:deep(.qc-tab-title .anticon) {
  font-size: 1.1em;
}

// 紧凑标签页样式
.compact-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 4px !important;
}

.compact-tabs :deep(.ant-tabs-tab) {
  padding: 4px 8px !important;
  font-size: 12px !important;
}

.compact-tabs :deep(.ant-tabs-content-holder) {
  padding-top: 4px !important;
}

.batch-test-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  overflow: hidden;
}

/* 文书类型选择器 - 紧凑标签页样式 */
.document-type-selector-compact {
  background: @color-bg-container;
  border-radius: @radius-md;
  padding: @spacing-4;
  border: 1px solid @color-border-light;

  .selector-header {
    display: flex;
    align-items: center;
    gap: @spacing-3;
    margin-bottom: @spacing-3;

    .selector-title {
      margin: 0;
      font-size: @font-size-h4;
      font-weight: @font-weight-semibold;
      color: @color-text-primary;
    }

    .selector-hint {
      font-size: @font-size-caption;
      color: @color-text-tertiary;
    }
  }

  .document-type-tabs {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: @spacing-2;

    @media (max-width: 1199px) {
      grid-template-columns: repeat(2, 1fr);
    }

    @media (max-width: 767px) {
      grid-template-columns: 1fr;
    }

    .document-tab {
      display: flex;
      align-items: center;
      gap: @spacing-3;
      padding: @spacing-3;
      border: 2px solid @color-border-base;
      border-radius: @radius-sm;
      background: @color-bg-container;
      cursor: pointer;
      transition: all @duration-base @ease-out;

      &:hover:not(.disabled) {
        border-color: @color-primary;
        background: @color-primary-lighter;
        transform: translateY(-1px);
      }

      &.active {
        border-color: @color-primary;
        background: @color-primary-lighter;
        box-shadow: @shadow-sm;

        .tab-icon {
          color: @color-primary;
        }

        .tab-label {
          color: @color-primary;
          font-weight: @font-weight-semibold;
        }

        .tab-count {
          color: @color-primary;
        }
      }

      &.disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .tab-icon {
        font-size: 20px;
        color: @color-text-secondary;
        transition: color @duration-base @ease-out;
      }

      .tab-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 2px;

        .tab-label {
          font-size: @font-size-body;
          font-weight: @font-weight-medium;
          color: @color-text-primary;
          transition: all @duration-base @ease-out;
        }

        .tab-count {
          font-size: @font-size-caption;
          color: @color-text-tertiary;
          transition: color @duration-base @ease-out;
        }
      }
    }
  }
}

/* 左右分栏内容 */
.content-main {
  flex: 1;
  display: flex;
  gap: 16px;
  overflow: hidden;
}

/* 左侧面板 */
.left-panel {
  flex: 0 0 40%;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 8px;
  padding: 16px;
  overflow: hidden;
  max-height: 400px; // 限制最大高度，让卡片更紧凑

  .panel-header {
    display: flex;
    justify-content: flex-start;  // 改为左对齐
    align-items: center;
    gap: 12px;  // 标题和按钮之间的间距
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid @color-border-light;  // 底部边框代替背景

    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: @font-weight-semibold;
      color: @color-text-primary;
    }

    // 查看完整病历按钮样式
    :deep(.ant-btn-link) {
      padding: 0 8px;
      height: auto;
      font-size: 14px;
      color: @color-primary;

      &:hover {
        color: @color-primary-hover;
      }

      .anticon {
        font-size: 14px;
      }
    }
  }

  // 病历摘要卡片（新增）
  .medical-summary-cards {
    margin-bottom: @spacing-4;
    padding: @spacing-4;
    background: @color-bg-container;
    border-radius: @radius-md;
    border: 1px solid @color-border-light;

    .summary-card-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: @spacing-3;
      margin-bottom: @spacing-3;

      @media (max-width: 767px) {
        grid-template-columns: 1fr;
      }

      .summary-card {
        padding: @spacing-3;
        background: @color-bg-layout;
        border-radius: @radius-sm;
        border: 1px solid @color-border-light;
        transition: all @duration-base @ease-out;

        &:hover {
          border-color: @color-primary;
          box-shadow: @shadow-sm;
        }

        &.full-width {
          grid-column: 1 / -1;
        }

        .card-label {
          font-size: 15px;  // 加大标题字体，和"基础信息"、"辅助检查"一样
          font-weight: @font-weight-bold;  // 黑体（700）
          color: @color-text-primary;  // 改为主色调，更突出
          margin-bottom: @spacing-2;  // 增加底部间距
          letter-spacing: 0.5px;
        }

        .card-value {
          font-size: 12px;  // 调小内容字体，和原来的"患者信息"标题一样
          font-weight: @font-weight-normal;  // 使用常规字重（400）
          color: @color-text-secondary;  // 使用次要文字颜色
          line-height: 1.8;  // 增加行高，提高可读性
        }
      }
    }

    .expand-toggle {
      text-align: center;
      padding-top: @spacing-2;
      border-top: 1px solid @color-border-light;

      :deep(.ant-btn-link) {
        color: @color-primary;
        font-weight: @font-weight-medium;

        &:hover {
          color: @color-primary-hover;
        }
      }
    }
  }

  .medical-text-container {
    flex: 1;
    overflow: hidden;

    .medical-textarea {
      height: 100%;
      font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
      font-size: 14px;
      font-weight: 400;
      line-height: 1.6;
    }
  }
}

/* 右侧面板 */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

/* 质控点选择区域 */
.rule-selection-section {
  background: white;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 360px;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
    }

    .selection-actions {
      display: flex;
      gap: 8px;
      align-items: center;
    }

    .document-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-weight: 600;
    }

    .document-tag__icon {
      font-size: 16px;
    }
  }

  // 搜索和筛选工具栏
  .filter-toolbar {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;

    :deep(.ant-input-search) {
      flex: 1;
    }
  }

  // 选择摘要
  .selection-summary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: #f5f5f5;
    border-radius: 4px;
    margin-bottom: 12px;

    .summary-text {
      font-size: 14px;
      font-weight: 400;
      color: #333;

      .filter-hint {
        color: #1890ff;
        font-weight: 500;
      }
    }
  }

  // 分类规则列表
  .rules-categorized-list {
    flex: 1;
    overflow-y: auto;
    border: 1px solid #e8e8e8;
    border-radius: 4px;
    margin-bottom: 12px;

    :deep(.ant-collapse) {
      background: transparent;
      border: none;
    }

    :deep(.ant-collapse-item) {
      border-bottom: 1px solid #e8e8e8;

      &:last-child {
        border-bottom: none;
      }
    }

    :deep(.ant-collapse-header) {
      padding: 12px 16px !important;
      font-size: 14px;
      font-weight: 600;
      color: #333;
      background: #fafafa;

      &:hover {
        background: #f0f0f0;
      }
    }

    :deep(.ant-collapse-content-box) {
      padding: 12px !important;
      background: white;
    }

    .category-icon {
      font-size: 18px;
      margin-right: 8px;
    }
  }

  // 主操作按钮样式 - 简洁版
  .test-action {
    margin-top: @spacing-4;

    .primary-action-button {
      height: 48px !important;
      font-size: 15px !important;
      font-weight: @font-weight-medium !important;
      border-radius: @radius-button !important; // 20px 胶囊风格

      :deep(.anticon) {
        font-size: 16px;
      }
    }
  }

  .production-qc-section {
    margin-top: @spacing-4;
    padding: @spacing-4;
    background: @color-bg-container;
    border-radius: @radius-md;
    border: 1px solid @color-border-base;

    .production-header {
      margin-bottom: @spacing-3;

      h4 {
        margin: 0;
        font-size: @font-size-h4;
        font-weight: @font-weight-semibold;
        color: @color-text-primary;
        display: flex;
        align-items: center;
        gap: @spacing-2;

        .help-icon {
          font-size: @font-size-body;
          color: @color-text-tertiary;
          cursor: help;
        }
      }
    }

    .primary-action-btn {
      height: 48px !important;
      font-size: 15px !important;
      font-weight: @font-weight-medium !important;
      border-radius: @radius-button !important; // 20px 胶囊风格

      :deep(.anticon) {
        font-size: 16px;
      }
    }
  }

  // 分类内的规则表格 - 优化版
  .category-rules-table {
    width: 100%;
    border-radius: @radius-md;
    overflow: hidden;
    background: @color-bg-container;
    box-shadow: @shadow-sm;

    .rules-table-header {
      display: grid;
      grid-template-columns: 40px 100px 1fr 120px;
      gap: @spacing-3;
      padding: @spacing-3 @spacing-4;
      background: @color-table-header-bg;
      border-bottom: 2px solid @color-border-base;
      font-size: @font-size-caption;
      font-weight: @font-weight-semibold;
      color: @color-text-secondary;
      text-transform: uppercase;
      letter-spacing: 0.5px;

      @media (max-width: 767px) {
        grid-template-columns: 40px 80px 1fr;

        .col-level {
          display: none;
        }
      }
    }

    .rules-table-body {
      .rule-row {
        display: grid;
        grid-template-columns: 40px 100px 1fr 120px;
        gap: @spacing-3;
        padding: @spacing-3 @spacing-4;
        min-height: @table-row-height-default; // 48px 行高
        border-bottom: 1px solid @color-border-light;
        cursor: pointer;
        transition: all @duration-base @ease-out;
        align-items: center;
        user-select: none;

        // 斑马纹效果
        &:nth-child(even) {
          background: @color-table-row-striped;
        }

        @media (max-width: 767px) {
          grid-template-columns: 40px 80px 1fr;

          .col-level {
            display: none;
          }
        }

        // 悬停效果 - 使用浅蓝色
        &:hover:not(.disabled):not(.selected) {
          background: @color-table-row-hover;
          transform: translateX(2px);
        }

        // 选中状态
        &.selected {
          background: @color-table-row-selected;
          border-left: 3px solid @color-primary;
          padding-left: calc(@spacing-4 - 3px);
          box-shadow: @shadow-xs;

          .col-id {
            color: @color-primary;
            font-weight: @font-weight-bold;
          }
        }

        // 禁用状态
        &.disabled {
          opacity: 0.5;
          cursor: not-allowed;
          background: @color-bg-disabled;
        }

        // 最后一行无边框
        &:last-child {
          border-bottom: none;
        }

        .col-checkbox {
          .flex-center();
        }

        .col-id {
          font-size: @font-size-body-sm;
          font-weight: @font-weight-semibold;
          color: @color-primary;
          letter-spacing: 0.3px;
        }

        .col-name {
          font-size: @font-size-body-sm;
          font-weight: @font-weight-normal;
          color: @color-text-primary;
          .text-ellipsis();
          padding-right: @spacing-2;
        }

        .col-level {
          .flex-center();

          // 状态标签样式（替代彩色圆点）
          .status-tag {
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            border-radius: @radius-full;
            font-size: @font-size-caption;
            font-weight: @font-weight-semibold;
            line-height: 1;
            border: 1px solid;
            transition: all @duration-base @ease-out;

            // 一级缺陷 - 红色
            &.level-high {
              background: @tag-error-bg;
              color: @tag-error-color;
              border-color: @tag-error-border;
            }

            // 二级缺陷 - 橙色
            &.level-medium {
              background: @tag-warning-bg;
              color: @tag-warning-color;
              border-color: @tag-warning-border;
            }

            // 三级缺陷 - 蓝色
            &.level-low {
              background: @tag-info-bg;
              color: @tag-info-color;
              border-color: @tag-info-border;
            }
          }
        }
      }
    }
  }
}

/* 质控结果区域 */
.test-results-section {
  flex: 1;
  background: white;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
    }
  }

  .results-container {
    flex: 1;
    overflow-y: auto;
  }
}

/* 测试中状态 */
.testing-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;

  .testing-text {
    margin-top: 16px;
    font-size: 14px;
    font-weight: 400;
    color: #666;
  }
}

/* 结果列表 */
.results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 结果卡片 */
.result-card {
  border: 2px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  transition: all 0.3s;

  &.compliant {
    border-color: #52c41a;
    background: #f6ffed;
  }

  &.non-compliant {
    border-color: #ff4d4f;
    background: #fff1f0;
  }

  &.error {
    border-color: #faad14;
    background: #fffbe6;
  }

  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .result-title {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 1;

      .result-icon {
        font-size: 20px;
      }

      .result-rule-id {
        font-size: 14px;
        font-weight: 600;
        color: #1890ff;
      }

      .result-rule-name {
        font-size: 14px;
        font-weight: 500;
        color: #333;
      }
    }

    .result-meta {
      display: flex;
      align-items: center;
      gap: 8px;

      .confidence {
        font-size: 12px;
        font-weight: 400;
        color: #8c8c8c;
      }
    }
  }

  .result-error {
    margin-bottom: 12px;
  }

  .result-issues {
    .issues-title {
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 8px;
      color: #333;
    }

    .issue-item {
      margin-bottom: 12px;
      padding-left: 8px;

      .issue-description {
        font-size: 14px;
        font-weight: 400;
        color: #333;
        margin-bottom: 4px;

        .issue-number {
          font-weight: 600;
          margin-right: 4px;
        }
      }

      .issue-evidence {
        font-size: 13px;
        font-weight: 400;
        color: #666;
        padding-left: 16px;
        border-left: 3px solid #e8e8e8;
        margin-left: 12px;

        .evidence-label {
          font-weight: 600;
          margin-right: 4px;
        }
      }
    }
  }

  .llm-output-section {
    margin-top: 12px;

    .llm-output {
      max-height: 200px;
      overflow-y: auto;
      background: #f5f5f5;
      padding: 12px;
      border-radius: 4px;
      font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
      font-size: 12px;
      font-weight: 400;
      line-height: 1.5;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
  }
}

/* 快速质控评估区域 - 优化版 */
.production-qc-section {
  margin-top: @spacing-5;
  padding: @spacing-5;
  background: linear-gradient(135deg, @color-primary-lighter 0%, @color-primary-light 100%);
  border: 2px solid @color-primary;
  border-radius: @radius-lg;
  box-shadow: @shadow-card;

  .production-header {
    margin-bottom: @spacing-4;

    h4 {
      margin: 0;
      font-size: @font-size-h3;
      font-weight: @font-weight-semibold;
      color: @color-primary-dark;
      display: flex;
      align-items: center;
      gap: @spacing-2;

      .help-icon {
        font-size: @font-size-body;
        color: @color-text-secondary;
        cursor: help;
        transition: color @duration-base;

        &:hover {
          color: @color-primary;
        }
      }
    }
  }

  /* 主操作按钮 */
  .primary-action-btn {
    height: @height-lg;
    font-size: @font-size-h3;
    font-weight: @font-weight-semibold;
    margin-bottom: @spacing-3;
    box-shadow: @shadow-card;
    transition: all @duration-base @ease-out;

    &:hover:not(:disabled) {
      transform: translateY(-1px);
      box-shadow: @shadow-card-hover;
    }

    &:active:not(:disabled) {
      transform: translateY(0);
    }
  }

  /* 高级选项折叠面板 */
  .advanced-options-collapse {
    margin-bottom: @spacing-3;

    :deep(.ant-collapse-header) {
      padding: @spacing-2 @spacing-3 !important;
      background: rgba(255, 255, 255, 0.6);
      border-radius: @radius-sm;
      transition: all @duration-base @ease-out;

      &:hover {
        background: rgba(255, 255, 255, 0.9);
      }
    }

    :deep(.ant-collapse-content-box) {
      padding: @spacing-3 !important;
    }

    .advanced-options-header {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: #475569;
      font-weight: 500;
    }
  }

  /* 提示词选择器（紧凑版） */
  .prompt-mode-selector-compact {
    .selector-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;

      .selector-label {
        font-size: 13px;
        font-weight: 600;
        color: #0c4a6e;
        margin: 0;
      }

      .help-icon-small {
        font-size: 14px;
        color: #64748b;
        cursor: help;
        transition: color 0.2s;

        &:hover {
          color: #0ea5e9;
        }
      }
    }

    .option-name-simple {
      font-size: 14px;
      color: #1e293b;
      }

    }

    .mode-description {
      margin-top: 8px;
      padding: 8px 12px;
      background: rgba(14, 165, 233, 0.05);
      border-left: 3px solid #0ea5e9;
      border-radius: 4px;
      font-size: 12px;
      color: #475569;
      line-height: 1.5;
    }
  }

  /* 快速统计 */
  .quick-stats {
    display: flex;
    gap: 12px;
    padding: 10px 12px;
    background: rgba(255, 255, 255, 0.7);
    border-radius: 6px;
    margin-bottom: 12px;
    flex-wrap: wrap;

    .stat-item {
      font-size: 13px;
      font-weight: 500;
      padding: 4px 10px;
      border-radius: 4px;
      white-space: nowrap;

      &.stat-total {
        background: #e0f2fe;
        color: #0c4a6e;
      }

      &.stat-passed {
        background: #dcfce7;
        color: #166534;
      }

      &.stat-issues {
        background: #fee2e2;
        color: #991b1b;
      }
    }
  }

  .production-results {
    margin-top: 16px;
    padding: 16px;
    background: white;
    border-radius: 8px;
    border: 1px solid #bae6fd;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);

    /* 核心指标卡片 */
    .results-header {
      display: flex;
      gap: 16px;
      margin-bottom: 16px;
      padding-bottom: 16px;
      border-bottom: 1px solid #e2e8f0;

      @media (max-width: 767px) {
        flex-direction: column;
      }

      .compliance-badge {
        flex-shrink: 0;
        width: 120px;
        height: 120px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

        &.excellent {
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        }

        &.good {
          background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        }

        &.fair {
          background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        }

        &.poor {
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        }

        .badge-label {
          font-size: 12px;
          color: rgba(255, 255, 255, 0.9);
          margin-bottom: 4px;
          font-weight: 500;
        }

        .badge-value {
          font-size: 32px;
          font-weight: 700;
          color: white;
          line-height: 1;
        }
      }

      .results-stats {
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 8px;

        .stat-row {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 15px;

          .stat-icon {
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            font-weight: 700;
            font-size: 14px;

            &.success {
              background: #dcfce7;
              color: #16a34a;
            }

            &.warning {
              background: #fef3c7;
              color: #d97706;
            }

            &.neutral {
              background: #f1f5f9;
              color: #64748b;
            }
          }

          .stat-text {
            color: #1e293b;
            font-weight: 500;
          }
        }
      }
    }

    /* 性能指标（紧凑） */
    .performance-metrics-compact {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      padding: 12px;
      background: #f8fafc;
      border-radius: 6px;
      margin-bottom: 12px;

      .metric-compact {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #475569;
        padding: 4px 10px;
        background: white;
        border-radius: 4px;
        border: 1px solid #e2e8f0;

        .anticon {
          color: #0ea5e9;
        }
      }
    }

    .view-details-action {
      margin: 16px 0;

      :deep(.ant-btn) {
        height: 40px;
        font-size: 14px;
        font-weight: 500;
      }
    }

    .production-results-preview {
      max-height: 300px;
      overflow-y: auto;

      &::-webkit-scrollbar {
        width: 6px;
      }

      &::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 3px;
      }

      &::-webkit-scrollbar-thumb {
        background: #0ea5e9;
        border-radius: 3px;

        &:hover {
          background: #0284c7;
        }
      }
    }

    .production-results-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 12px;

      .production-result-item {
        padding: 12px;
        border-radius: 6px;
        border: 1px solid #e5e7eb;
        background: white;

        &.compliant {
          background: #f0fdf4;
          border-color: #86efac;
        }

        &.non-compliant {
          background: #fef2f2;
          border-color: #fca5a5;
        }

        &.neutral {
          background: #f8fafc;
          border-color: #cbd5f5;
        }

        &.error {
          background: #fff7ed;
          border-color: #fed7aa;
        }

        .result-item-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;

          .result-icon {
            font-size: 16px;

            &.success {
              color: #16a34a;
            }

            &.error {
              color: #dc2626;
            }

            &.neutral {
              color: #475569;
            }
          }

          .result-rule-id {
            font-size: 13px;
            font-weight: 600;
            color: #0ea5e9;
          }

          .result-rule-name {
            flex: 1;
            font-size: 13px;
            color: #374151;
          }
        }

        .result-findings {
          margin-top: 8px;
          padding: 8px;
          background: #fef3c7;
          border-left: 3px solid #f59e0b;
          border-radius: 4px;

          .findings-label {
            font-size: 15px;
            font-weight: 700;
            color: #92400e;
            margin-bottom: 6px;
          }

          .findings-content {
            font-size: 13px;
            color: #451a03;
            line-height: 1.5;
          }
        }

        .result-evidence {
          margin-top: 6px;
          font-size: 12px;
          color: #6b7280;
          padding-left: 12px;
          border-left: 2px solid #d1d5db;

          .evidence-label {
            font-weight: 600;
            margin-right: 4px;
          }

          .evidence-content {
            font-style: italic;
          }
        }
      }
    }
  }

/* 质控结果详情弹窗 */
.results-modal-content {
  .modal-summary {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    padding: 20px;
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    border-radius: 8px;
    margin-bottom: 16px;

    :deep(.ant-statistic) {
      text-align: center;

      .ant-statistic-title {
        font-size: 13px;
        color: #64748b;
        margin-bottom: 8px;
      }

      .ant-statistic-content {
        font-size: 24px;
        font-weight: 700;
      }
    }
  }

  .modal-info-tags {
    display: flex;
    justify-content: center;
    padding: 12px 20px;
    background: #fafafa;
    border-radius: 8px;
    margin-bottom: 20px;

    .model-tag {
      font-size: 14px;
      font-weight: 600;
      padding: 4px 12px;
    }

    .prompt-mode-tag {
      font-size: 14px;
      font-weight: 600;
      padding: 4px 12px;
    }
  }

  .modal-results-list {
    max-height: 500px;
    overflow-y: auto;
    padding-right: 8px;

    &::-webkit-scrollbar {
      width: 8px;
    }

    &::-webkit-scrollbar-track {
      background: #f1f1f1;
      border-radius: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: #0ea5e9;
      border-radius: 4px;

      &:hover {
        background: #0284c7;
      }
    }

    .modal-result-item {
      padding: 16px;
      border-radius: 8px;
      border: 2px solid #e5e7eb;
      background: white;
      margin-bottom: 12px;
      transition: all 0.3s;

      &:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
      }

      &.compliant {
        background: #f0fdf4;
        border-color: #86efac;
      }

      &.non-compliant {
        background: #fef2f2;
        border-color: #fca5a5;
      }

      &.neutral {
        background: #f8fafc;
        border-color: #cbd5f5;
      }

      &.error {
        background: #fff7ed;
        border-color: #fed7aa;
      }

      .result-item-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;

        .result-icon {
          font-size: 22px;

          &.success {
            color: #16a34a;
          }

          &.error {
            color: #dc2626;
          }

          &.neutral {
            color: #475569;
          }
        }

        .result-rule-id {
          font-size: 16px;
          font-weight: 800;
          color: #0ea5e9;
          padding: 4px 8px;
          background: white;
          border-radius: 4px;
        }

        .result-rule-name {
          flex: 1;
          font-size: 16px;
          font-weight: 700;
          color: #1f2937;
        }
      }

      .result-findings {
        margin-top: 12px;
        padding: 12px;
        background: #fef3c7;
        border-left: 4px solid #f59e0b;
        border-radius: 6px;

        .findings-label {
          font-size: 16px;
          font-weight: 800;
          color: #92400e;
          margin-bottom: 8px;
        }

        .findings-content {
          font-size: 14px;
          color: #451a03;
          line-height: 1.6;
        }
      }

      .result-evidence {
        margin-top: 10px;
        font-size: 13px;
        color: #6b7280;
        padding: 10px;
        background: #f8fafc;
        border-left: 3px solid #cbd5e1;
        border-radius: 4px;

        .evidence-label {
          font-weight: 700;
          color: #475569;
          margin-right: 6px;
        }

        .evidence-content {
          font-style: italic;
          line-height: 1.5;
        }
      }

      .result-suggestion {
        margin-top: 10px;
        font-size: 13px;
        color: #059669;
        padding: 10px;
        background: #f0fdf4;
        border-left: 3px solid #86efac;
        border-radius: 4px;

        .suggestion-label {
          font-weight: 700;
          color: #047857;
          margin-right: 6px;
        }

        .suggestion-content {
          line-height: 1.5;
        }
      }

      .result-confidence {
        margin-top: 8px;
        font-size: 12px;
        color: #6b7280;
        display: flex;
        align-items: center;
        gap: 4px;

        .confidence-label {
          font-weight: 600;
        }

        .confidence-value {
          font-weight: 700;
          color: #1890ff;
        }
      }
    }
  }
}

.not-applicable-banner {
  padding: 12px;
  border-left: 4px solid #94a3b8;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 13px;
  color: #475569;
  margin-bottom: 12px;
  line-height: 1.5;
}

.evidence-warning {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #9a3412;
  font-size: 13px;
  margin-bottom: 12px;

  &.inline-warning {
    margin-bottom: 8px;
  }
}

/* 查看结果按钮样式 */
.view-test-results-action {
  margin-top: 16px;
  padding: 16px;
  background: #f0f9ff;
  border: 1px solid #bae7ff;
  border-radius: 8px;

  .results-quick-summary {
    margin-top: 12px;
    text-align: center;
  }
}

/* 批量测试结果悬浮窗样式 */
.modal-test-summary {
  margin-bottom: 24px;

  .production-summary-tag {
    display: inline-block;
    padding: 8px 16px;
    border-radius: 999px;
    background: #fef9c3;
    border: 1px solid #fde68a;
    color: #a16207;
    font-size: 14px;
  }

  .summary-overview {
    margin-top: 16px;
    background: #e0f2fe;
    border: 1px solid #bae6fd;
    border-radius: 10px;
    padding: 16px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;

    .summary-item {
      display: flex;
      flex-direction: column;
      text-align: center;

      .summary-label {
        font-size: 13px;
        color: #475569;
        margin-bottom: 4px;
      }

      .summary-value {
        font-size: 20px;
        font-weight: 700;
        color: #0f172a;

        &.success {
          color: #16a34a;
        }

        &.warning {
          color: #ea580c;
        }

        &.neutral {
          color: #0ea5e9;
        }
      }
    }
  }
}

.summary-metrics {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;

  &.compact {
    justify-content: flex-start;
  }

  .metric-item {
    min-width: 140px;
    padding: 10px 14px;
    border-radius: 8px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    text-align: left;

    .metric-label {
      font-size: 12px;
      color: #64748b;
      margin-bottom: 4px;
    }

    .metric-value {
      font-size: 16px;
      font-weight: 600;
      color: #0f172a;
    }
  }
}

.testing-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;

  .testing-text {
    margin-top: 16px;
    font-size: 14px;
    color: #595959;
  }
}

.modal-results-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;

  .results-count {
    font-size: 13px;
    color: #6b7280;
  }
}

.modal-test-results-list {
  .results-collapse {
    background: transparent;

    :deep(.ant-collapse-item) {
      margin-bottom: 12px;
      border: none;
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
    }

    :deep(.ant-collapse-content-box) {
      background: #fff;
    }
  }

  .result-panel {
    &.compliant :deep(.ant-collapse-header) {
      background: #f0fdf4;
    }

    &.non-compliant :deep(.ant-collapse-header) {
      background: #fef2f2;
    }

    &.error :deep(.ant-collapse-header) {
      background: #fff7ed;
    }
  }

  .result-panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;

      .result-icon {
        font-size: 20px;
        display: inline-flex;
        align-items: center;

        .anticon-check-circle {
          color: #22c55e;
        }

        .anticon-close-circle {
          color: #ef4444;
        }

        .anticon-exclamation-circle {
          color: #f59e0b;
        }
      }

      .result-info {
        display: flex;
        flex-direction: column;
        gap: 2px;

        .result-rule-id {
          font-size: 13px;
          font-weight: 700;
          color: #1d4ed8;
        }

        .result-rule-name {
          font-size: 13px;
          color: #1f2937;
          font-weight: 500;
        }
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 8px;

      .status-pill {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 15px;
        font-weight: 700;

        &.success {
          background: #dcfce7;
          color: #15803d;
        }

        &.danger {
          background: #fee2e2;
          color: #b91c1c;
        }

        &.warning {
          background: #fef3c7;
          color: #b45309;
        }
      }

      .confidence-chip {
        font-size: 12px;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 999px;
        background: #e0f2fe;
        color: #0369a1;
      }
    }
  }

  .result-panel-body {
    padding: 16px;
    background: #fff;
  }

  .result-error {
    margin-top: 8px;
  }

  .result-issues {
    margin-top: 8px;

    .issues-title {
      font-size: 14px;
      font-weight: 700;
      color: #111827;
      margin-bottom: 8px;
    }

    .issues-empty {
      font-size: 13px;
      color: #6b7280;
      background: #f8fafc;
      border-radius: 6px;
      padding: 12px;
    }
  }

  .issue-item {
    padding: 12px;
    border-radius: 8px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    margin-bottom: 10px;

    .issue-description {
      font-size: 14px;
      color: #111827;
      line-height: 1.5;

      .issue-number {
        font-weight: 700;
        color: #2563eb;
        margin-right: 4px;
      }
    }

    .issue-evidence {
      margin-top: 8px;
      font-size: 13px;
      color: #4b5563;

      .evidence-label {
        font-weight: 600;
        margin-right: 4px;
      }
    }
  }

  .llm-output-section {
    margin-top: 12px;

    .llm-output {
      font-size: 12px;
      line-height: 1.5;
      background: #f5f5f5;
      padding: 12px;
      border-radius: 4px;
      max-height: 300px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
  }
}

/* 底部主操作按钮区域（水平并排，无卡片效果） */
.main-actions-section-bottom {
  margin: 24px auto;
  padding: 0;
  max-width: 900px;

  .actions-row {
    display: flex;
    gap: 16px;
    justify-content: center;
    align-items: center;
    margin-bottom: 16px;

    .primary-action-button,
    .primary-action-btn {
      flex: 0 0 auto;
      min-width: 280px;
      height: 48px;
      font-size: 15px;
      font-weight: 600;
      border-radius: 20px;
      box-shadow: 0 2px 8px rgba(11, 100, 212, 0.2);
      transition: all 0.3s ease;

      &:hover:not(:disabled) {
        box-shadow: 0 4px 12px rgba(11, 100, 212, 0.3);
        transform: translateY(-1px);
      }

      &:active:not(:disabled) {
        transform: translateY(0);
      }
    }
  }

  .advanced-options-collapse {
    margin-top: 12px;

    .advanced-options-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: #595959;
    }

    .advanced-options-content {
      padding: 16px;
      background: #f5f7fb;
      border-radius: 8px;

      .option-item {
        .option-label {
          display: block;
          font-size: 13px;
          font-weight: 600;
          color: #1f1f1f;
          margin-bottom: 8px;
        }

        .mode-description {
          margin-top: 8px;
          font-size: 12px;
          color: #8c8c8c;
          line-height: 1.5;
        }
      }
    }
  }
}

/* 病历文本弹窗样式 */
.medical-text-modal-content {
  .import-section {
    margin-bottom: 16px;

    .import-hint {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      background: linear-gradient(135deg, #E6F4FF 0%, #F0F9FF 100%);
      border-left: 4px solid @color-primary;
      border-radius: 8px;
      margin-bottom: 12px;

      .hint-icon {
        font-size: 18px;
      }

      .hint-text {
        font-size: 14px;
        color: @color-text-secondary;
        line-height: 1.5;
      }
    }

    .import-actions {
      display: flex;
      justify-content: flex-start;
      padding: 0 4px;

      :deep(.ant-btn) {
        border-radius: 20px;
        font-weight: 500;
        transition: all 0.3s ease;

        &:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 2px 8px rgba(11, 100, 212, 0.2);
        }
      }

      :deep(.ant-select) {
        .ant-select-selector {
          border-radius: 20px;
          transition: all 0.3s ease;

          &:hover {
            border-color: @color-primary;
          }
        }
      }
    }
  }

  .medical-textarea {
    margin-top: 8px;
    font-family: 'Courier New', monospace;
    font-size: 14px;
    line-height: 1.6;
    border-radius: 8px;

    :deep(textarea) {
      border-radius: 8px;
    }
  }
}

/* 历史记录弹窗样式 */
.history-modal {
  :deep(.ant-modal-body) {
    padding: 0;
  }

  .history-tabs {
    :deep(.ant-tabs-nav) {
      padding: 0 24px;
      margin-bottom: 0;
    }

    :deep(.ant-tabs-content) {
      padding: 24px;
    }
  }

  .current-result-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 40px 80px 40px;
    min-height: 400px;

    .modal-summary {
      width: 100%;
      max-width: 1000px;
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 16px;
      margin-bottom: 32px;
      padding: 20px;
      background: linear-gradient(135deg, #F0F9FF 0%, #E6F4FF 100%);
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

      :deep(.ant-statistic) {
        text-align: center;

        .ant-statistic-title {
          font-size: 13px;
          color: #64748b;
          margin-bottom: 8px;
          font-weight: 500;
        }

        .ant-statistic-content {
          font-size: 24px;
          font-weight: 700;
        }
      }
    }

    .loading-text {
      margin-top: 24px;
      font-size: 18px;
      font-weight: 600;
      color: #1890ff;
    }

    .loading-tip {
      margin-top: 12px;
      font-size: 14px;
      color: #8c8c8c;
    }
  }

  .current-result-content {
    .modal-summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
      padding: 20px;
      background: linear-gradient(135deg, #F0F9FF 0%, #E6F4FF 100%);
      border-radius: 12px;

      :deep(.ant-statistic) {
        .ant-statistic-title {
          font-size: 14px;
          color: #64748b;
          margin-bottom: 8px;
        }

        .ant-statistic-content {
          font-size: 24px;
          font-weight: 700;
        }
      }
    }

    .summary-metrics {
      margin-bottom: 20px;
    }

    .modal-info-tags {
      margin-bottom: 20px;
    }

    .modal-filter-controls {
      margin-bottom: 16px;
      display: flex;
      justify-content: flex-end;
    }

    .modal-results-list {
      max-height: 500px;
      overflow-y: auto;

      &::-webkit-scrollbar {
        width: 8px;
      }

      &::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: #0ea5e9;
        border-radius: 4px;

        &:hover {
          background: #0284c7;
        }
      }

      :deep(.ant-statistic) {
        .ant-statistic-title {
          font-size: 14px;
          color: @color-text-secondary;
          margin-bottom: 8px;
        }

        .ant-statistic-content {
          font-size: 24px;
          font-weight: @font-weight-semibold;
        }
      }
    }

    .modal-filter-controls {
      margin-bottom: 16px;
      display: flex;
      justify-content: flex-end;
    }
  }

  .history-content {
    .history-filters {
      margin-bottom: 24px;
      padding: 16px;
      background: #fafafa;
      border-radius: 8px;
    }

    .history-list {
      .history-list-item {
        cursor: pointer;
        transition: all 0.3s ease;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        background: #fff;
        border: 1px solid #f0f0f0;

        &:hover {
          background: #fafafa;
          border-color: @color-primary;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(11, 100, 212, 0.1);
        }

        .history-item-content {
          width: 100%;

          .history-item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;

            .history-item-time {
              display: flex;
              align-items: center;
              gap: 8px;
              font-size: 14px;
              color: @color-text-secondary;

              :deep(.anticon) {
                color: @color-primary;
              }
            }
          }

          .history-item-stats {
            display: flex;
            gap: 24px;
            flex-wrap: wrap;

            .stat-item {
              display: flex;
              align-items: center;
              gap: 8px;

              .stat-label {
                font-size: 13px;
                color: @color-text-secondary;
              }

              .stat-value {
                font-size: 14px;
                font-weight: @font-weight-semibold;

                &.success {
                  color: #16a34a;
                }

                &.error {
                  color: #dc2626;
                }
              }
            }
          }
        }
      }
    }
  }
}

/* 次要操作按钮样式 */
.secondary-action-btn {
  border-radius: @radius-button;
  font-weight: @font-weight-medium;
  transition: all 0.3s ease;
  border-color: @color-primary;
  color: @color-primary;

  &:hover:not(:disabled) {
    background: @color-primary;
    color: #fff;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(11, 100, 212, 0.3);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

/* 历史记录详情弹窗样式 */
.history-detail-modal {
  :deep(.ant-modal-body) {
    padding: 24px;
    max-height: 70vh;
    overflow-y: auto;
  }

  .history-detail-content {
    .detail-header {
      padding: 16px;
      background: linear-gradient(135deg, #F0F9FF 0%, #E6F4FF 100%);
      border-radius: 8px;
      margin-bottom: 24px;
      .header-content {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        flex-wrap: wrap;
      }

      .header-left {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .header-right {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-left: auto;
      }

      .detail-info-item {
        display: flex;
        align-items: center;
        gap: 8px;

        .info-icon {
          color: @color-primary;
          font-size: 16px;
        }

        .info-label {
          color: @color-text-secondary;
          font-size: 14px;
        }

        .info-value {
          color: @color-text-primary;
          font-size: 14px;
          font-weight: @font-weight-medium;
        }

        .model-tag {
          font-size: 15px;
          font-weight: @font-weight-bold;
          padding: 6px 14px;
          border-radius: 6px;
        }

        .prompt-mode-tag {
          font-size: 15px;
          font-weight: @font-weight-bold;
          padding: 6px 14px;
          border-radius: 6px;
        }
      }
    }

    /* 本次质控结果 Tab 中，批量测试加载状态下的实时问题流样式 */
    .current-result-loading {
      .current-result-stream {
        margin-top: 24px;
        padding: 16px;
        background: #f9fafb;
        border-radius: 8px;

        .stream-title {
          font-size: 14px;
          font-weight: @font-weight-bold;
          color: @color-text-primary;
          margin-bottom: 8px;
        }

        .stream-result-panel {
          border-radius: 6px;
          margin-bottom: 8px;

          :deep(.ant-collapse-header) {
            padding: 8px 12px !important;
            font-size: 13px;
          }
        }

        .stream-result-body {
          padding: 8px 12px 12px;
          font-size: 13px;
          color: @color-text-primary;
        }

        .stream-result-findings {
          margin: 0 0 4px;
          line-height: 1.6;
        }

        .stream-result-evidence {
          margin: 0;
          font-size: 12px;
          color: @color-text-secondary;

          .label {
            font-weight: 600;
            margin-right: 4px;
          }
        }
      }
    }

    .detail-summary {
      padding: 20px;
      background: #fafafa;
      border-radius: 8px;
      margin-bottom: 24px;

      :deep(.ant-statistic-title) {
        font-size: 13px;
        color: @color-text-secondary;
      }

      :deep(.ant-statistic-content) {
        font-size: 24px;
        font-weight: @font-weight-bold;
      }
    }

    .detail-results {
      .results-title {
        font-size: 16px;
        font-weight: @font-weight-semibold;
        color: @color-text-primary;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 2px solid #f0f0f0;
      }

      .results-collapse {
        :deep(.ant-collapse-header) {
          font-weight: @font-weight-medium;
          font-size: 14px;
        }

        .result-status-tag {
          font-size: 15px !important;
          font-weight: 700 !important;
          padding: 4px 12px !important;
        }

        .result-detail {
          .result-section {
            margin-bottom: 16px;

            .section-title {
              display: flex;
              align-items: center;
              gap: 8px;
              font-size: 14px;
              font-weight: @font-weight-semibold;
              color: @color-text-primary;
              margin-bottom: 8px;

              .anticon {
                color: @color-primary;
              }
            }

            .section-content {
              font-size: 14px;
              color: @color-text-secondary;
              line-height: 1.6;
              padding-left: 24px;
              margin: 0;

              &.evidence-text {
                background: #f5f5f5;
                padding: 12px;
                border-radius: 4px;
                border-left: 3px solid @color-primary;
                font-family: monospace;
                white-space: pre-wrap;
              }
            }
          }

          .result-meta {
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px dashed #e0e0e0;
          }
        }
      }
    }
  }

  .view-original-btn {
    border-radius: @radius-button;
    font-weight: @font-weight-medium;
    box-shadow: 0 2px 8px rgba(11, 100, 212, 0.2);

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(11, 100, 212, 0.3);
    }
  }
}

/* 原始病历文本弹窗样式 */
.original-text-modal {
  :deep(.ant-modal-body) {
    padding: 24px;
  }

  .original-text-content {
    .original-text-area {
      font-family: 'Courier New', Consolas, monospace;
      font-size: 14px;
      line-height: 1.6;
      background: #f5f5f5;
      border: 1px solid #d9d9d9;
      border-radius: 4px;

      &:focus {
        border-color: @color-primary;
        box-shadow: 0 0 0 2px rgba(11, 100, 212, 0.1);
      }
    }

    .text-info {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid #f0f0f0;
      color: @color-text-secondary;
      font-size: 13px;
      text-align: right;
    }
  }
}

/* 质控加载中的Modal边框进度条 - 科技感增强版 */
.qc-loading-modal {
  :deep(.ant-modal-content) {
    position: relative;
    overflow: hidden;
  }

  .border-progress-indicator {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    pointer-events: none;
    z-index: 1000;

    .progress-line {
      position: absolute;
      background: #1890ff;
      opacity: 0.9;
      box-shadow: 0 0 10px rgba(24, 144, 255, 0.8),
                  0 0 20px rgba(24, 144, 255, 0.5),
                  0 0 30px rgba(24, 144, 255, 0.3);
    }

    .progress-glow {
      position: absolute;
      top: -2px;
      left: -2px;
      right: -2px;
      bottom: -2px;
      background: rgba(24, 144, 255, 0.05);
      border-radius: 8px;
      animation: pulse-glow 2s ease-in-out infinite;
    }

    .progress-top {
      top: 0;
      left: 0;
      height: 4px;
      width: 0;
      animation: progress-width 2s linear infinite;
      border-radius: 2px;
    }

    .progress-right {
      top: 0;
      right: 0;
      width: 4px;
      height: 0;
      animation: progress-height 2s linear infinite;
      animation-delay: 0.5s;
      border-radius: 2px;
    }

    .progress-bottom {
      bottom: 0;
      right: 0;
      height: 4px;
      width: 0;
      animation: progress-width 2s linear infinite;
      animation-delay: 1s;
      border-radius: 2px;
    }

    .progress-left {
      bottom: 0;
      left: 0;
      width: 4px;
      height: 0;
      animation: progress-height 2s linear infinite;
      animation-delay: 1.5s;
      border-radius: 2px;
    }
  }

  .analyzing-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 999;
    animation: fade-in 0.3s ease-in-out;
  }

  .analyzing-content {
    text-align: center;
    padding: 40px;
  }

  .analyzing-text {
    margin-top: 24px;
    font-size: 18px;
    font-weight: 600;
    color: #1890ff;
  }

  .analyzing-tip {
    margin-top: 12px;
    font-size: 14px;
    color: #8c8c8c;
  }
}

@keyframes progress-width {
  0% {
    width: 0;
  }
  25% {
    width: 100%;
  }
  100% {
    width: 100%;
  }
}

@keyframes progress-height {
  0% {
    height: 0;
  }
  25% {
    height: 100%;
  }
  100% {
    height: 100%;
  }
}

@keyframes pulse-glow {
  0%, 100% {
    opacity: 0.3;
  }
  50% {
    opacity: 0.6;
  }
}

@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

// LLM 设置按钮样式
.llm-settings-button {
  height: 48px !important;
  font-size: 15px !important;
  font-weight: 500 !important;
  padding: 0 24px !important;
  border-radius: 20px !important;
  border: 2px solid #3b82f6 !important;
  color: #3b82f6 !important;
  background: white !important;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15) !important;
  transition: all 0.3s ease !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.llm-settings-button:hover {
  background: #3b82f6 !important;
  color: white !important;
  border-color: #3b82f6 !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3) !important;
}

.llm-settings-button :deep(.anticon) {
  font-size: 18px !important;
}

.llm-settings-button span {
  font-weight: 500 !important;
}

// 演示模式样式
.batch-rule-test.demo-mode {
  background: transparent;
  padding: 0;
  min-height: auto;
  height: 100%;
  overflow: auto;
}
</style>
