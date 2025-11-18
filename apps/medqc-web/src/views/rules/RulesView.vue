<template>
  <div class="page-container min-h-screen bg-gray-50 p-2 lg:p-3">
    <!-- 页面头部 + Tab 导航 -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-3 lg:p-4 mb-3">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div class="flex flex-1 items-start gap-3">
          <div class="p-2 bg-blue-100 rounded-md">
            <SettingOutlined class="text-lg text-blue-600" />
          </div>
          <div class="space-y-1">
            <h1 class="text-xl font-bold text-gray-900">质控规则管理</h1>
            <p class="text-sm text-gray-600 leading-relaxed">
              {{ activeTabDescription }}
            </p>
          </div>
        </div>
        <!-- 通用操作按钮区域 - 所有标签页都显示 -->
        <div class="flex flex-wrap gap-1.5">
          <!-- LLM 设置按钮 - 所有标签页都显示 -->
          <a-button
            @click="showLLMSettings"
            size="large"
            class="llm-settings-button"
          >
            <template #icon><ApiOutlined /></template>
            <span>LLM 设置</span>
          </a-button>

          <!-- 传统规则标签页特有的操作按钮 -->
          <template v-if="activeTab === 'traditional'">
            <a-button
              @click="refreshRules"
              :loading="loading"
              size="small"
              class="flex items-center space-x-1"
            >
              <template #icon><ReloadOutlined /></template>
              <span>刷新</span>
            </a-button>
            <a-button
              @click="importRules"
              size="small"
              class="flex items-center space-x-1"
            >
              <template #icon><ImportOutlined /></template>
              <span>导入规则</span>
            </a-button>
            <a-button
              type="primary"
              ghost
              @click="showCustomRuleModal"
              size="small"
              class="flex items-center space-x-1 border-blue-600 text-blue-600"
            >
              <template #icon><ThunderboltOutlined /></template>
              <span>新增自定义质控点</span>
            </a-button>
            <a-button
              type="primary"
              @click="showCreateModal"
              size="small"
              class="flex items-center space-x-1 bg-blue-600 hover:bg-blue-700"
            >
              <template #icon><PlusOutlined /></template>
              <span>新增规则</span>
            </a-button>
          </template>
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

    <!-- 标签页内容 -->
    <div class="tab-content">
      <!-- 传统质控规则标签页 -->
      <div v-if="activeTab === 'traditional'">
        <!-- 统计卡片 - 更紧凑 -->
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-2 mb-2">
          <div class="flex items-center justify-between mb-1">
            <h2 class="text-sm font-semibold text-gray-900">规则统计</h2>
            <a-tag color="blue" class="px-1.5 py-0.5 text-xs">
              传统规则模式
            </a-tag>
          </div>
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-2">
            <div class="bg-gradient-to-br from-blue-50 to-blue-100 rounded-md p-2 border border-blue-200">
              <a-statistic
                title="总规则数"
                :value="statistics.total"
                :value-style="{ color: '#1890ff', fontSize: '16px', fontWeight: '600' }"
              >
                <template #prefix>
                  <div class="p-1 bg-blue-500 rounded-md inline-block">
                    <FileTextOutlined class="text-white text-xs" />
                  </div>
                </template>
              </a-statistic>
            </div>
            <div class="bg-gradient-to-br from-green-50 to-green-100 rounded-md p-2 border border-green-200">
              <a-statistic
                title="激活规则"
                :value="statistics.active"
                :value-style="{ color: '#16a34a', fontSize: '14px', fontWeight: '600' }"
              >
                <template #prefix>
                  <div class="p-1 bg-green-500 rounded-md inline-block">
                    <CheckCircleOutlined class="text-white text-xs" />
                  </div>
                </template>
              </a-statistic>
            </div>
            <div class="bg-gradient-to-br from-red-50 to-red-100 rounded-md p-2 border border-red-200">
              <a-statistic
                title="严重规则"
                :value="statistics.critical"
                :value-style="{ color: '#dc2626', fontSize: '14px', fontWeight: '600' }"
              >
                <template #prefix>
                  <div class="p-1 bg-red-500 rounded-md inline-block">
                    <ExclamationCircleOutlined class="text-white text-xs" />
                  </div>
                </template>
              </a-statistic>
            </div>
            <div class="bg-gradient-to-br from-purple-50 to-purple-100 rounded-md p-2 border border-purple-200">
              <a-statistic
                title="规则分类"
                :value="statistics.categories"
                :value-style="{ color: '#9333ea', fontSize: '14px', fontWeight: '600' }"
              >
                <template #prefix>
                  <div class="p-1 bg-purple-500 rounded-md inline-block">
                    <TagsOutlined class="text-white text-xs" />
                  </div>
                </template>
              </a-statistic>
            </div>
          </div>
        </div>

        <!-- 筛选和搜索 - 更紧凑 -->
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-2 mb-2">
          <div class="flex items-center justify-between mb-1">
            <h2 class="text-sm font-semibold text-gray-900">筛选条件</h2>
            <a-button
              size="small"
              @click="resetFilters"
              class="text-gray-500 hover:text-gray-700"
            >
              <template #icon><ClearOutlined /></template>
              清空筛选
            </a-button>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 mb-2">
            <div class="space-y-1">
              <label class="text-xs font-medium text-gray-700">搜索</label>
              <a-input-search
                v-model:value="searchText"
                placeholder="搜索规则"
                @search="handleSearch"
                allow-clear
                size="small"
                class="w-full"
              />
            </div>

            <div class="space-y-1">
              <label class="text-xs font-medium text-gray-700">文书类别</label>
              <a-select
                v-model:value="filterDocumentCategory"
                placeholder="文书类别"
                allowClear
                @change="handleFilter"
                size="small"
                class="w-full"
              >
                <a-select-option
                  v-for="option in documentCategoryOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  <div class="flex items-center space-x-1">
                    <a-tag :color="option.color" class="text-xs">
                      {{ option.label }}
                    </a-tag>
                  </div>
                </a-select-option>
              </a-select>
            </div>

            <div class="space-y-1">
              <label class="text-xs font-medium text-gray-700">规则分类</label>
              <a-select
                v-model:value="filterCategory"
                placeholder="分类"
                allowClear
                @change="handleFilter"
                size="small"
                class="w-full"
              >
                <a-select-option value="completeness">完整性</a-select-option>
                <a-select-option value="consistency">一致性</a-select-option>
                <a-select-option value="rationality">合理性</a-select-option>
                <a-select-option value="timeliness">及时性</a-select-option>
              </a-select>
            </div>

            <div class="space-y-1">
              <label class="text-xs font-medium text-gray-700">严重程度</label>
              <a-select
                v-model:value="filterSeverity"
                placeholder="严重程度"
                allowClear
                @change="handleFilter"
                size="small"
                class="w-full"
              >
                <a-select-option value="critical">严重</a-select-option>
                <a-select-option value="major">重要</a-select-option>
                <a-select-option value="minor">轻微</a-select-option>
              </a-select>
            </div>

            <div class="space-y-1">
              <label class="text-xs font-medium text-gray-700">规则类型</label>
              <a-select
                v-model:value="filterType"
                placeholder="类型"
                allowClear
                @change="handleFilter"
                size="small"
                class="w-full"
              >
                <a-select-option value="logical">逻辑规则</a-select-option>
                <a-select-option value="semantic">语义规则</a-select-option>
                <a-select-option value="hybrid">混合规则</a-select-option>
              </a-select>
            </div>

            <div class="space-y-1">
              <label class="text-xs font-medium text-gray-700">状态</label>
              <a-select
                v-model:value="filterStatus"
                placeholder="状态"
                allowClear
                @change="handleFilter"
                size="small"
                class="w-full"
              >
                <a-select-option value="active">激活</a-select-option>
                <a-select-option value="inactive">停用</a-select-option>
              </a-select>
            </div>
          </div>

          <!-- 快速筛选标签 - 紧凑化 -->
          <div class="space-y-2">
            <!-- 文书类别快速筛选 -->
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs font-semibold text-gray-800">文书类别：</span>
              <div
                :class="['filter-tag-compact', { 'filter-tag-compact-active': !filterDocumentCategory }]"
                @click="clearDocumentCategoryFilter"
              >
                <span class="filter-tag-text">全部文书</span>
                <span class="filter-tag-count">({{ statistics.total }})</span>
              </div>
              <div
                v-for="option in documentCategoryOptions"
                :key="option.value"
                :class="['filter-tag-compact', { 'filter-tag-compact-active': filterDocumentCategory === option.value }]"
                @click="quickFilterDocumentCategory(option.value)"
                :style="{ borderColor: option.color }"
              >
                <span class="filter-tag-text">{{ option.label }}</span>
                <span class="filter-tag-count">({{ documentCategoryStats[option.value] || 0 }})</span>
              </div>
            </div>

            <!-- 其他快速筛选 -->
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs font-semibold text-gray-800">快速筛选：</span>
              <div
                :class="['filter-tag-compact', { 'filter-tag-compact-active': !filterCategory && !filterSeverity && !filterType && !filterStatus && !filterDocumentCategory }]"
                @click="clearAllFilters"
              >
                <span class="filter-tag-text">全部规则</span>
                <span class="filter-tag-count">({{ statistics.total }})</span>
              </div>
              <div
                :class="['filter-tag-compact', { 'filter-tag-compact-active': filterCategory === 'completeness' }]"
                @click="quickFilterCategory('completeness')"
              >
                <span class="filter-tag-text">完整性</span>
              </div>
              <div
                :class="['filter-tag-compact', { 'filter-tag-compact-active': filterCategory === 'consistency' }]"
                @click="quickFilterCategory('consistency')"
              >
                <span class="filter-tag-text">一致性</span>
              </div>
              <div
                :class="['filter-tag-compact', { 'filter-tag-compact-active': filterCategory === 'rationality' }]"
                @click="quickFilterCategory('rationality')"
              >
                <span class="filter-tag-text">合理性</span>
              </div>
              <div
                :class="['filter-tag-compact filter-tag-danger', { 'filter-tag-danger-active': filterSeverity === 'critical' }]"
                @click="quickFilterSeverity('critical')"
              >
                <span class="filter-tag-text">严重缺陷</span>
              </div>
              <div
                :class="['filter-tag-compact filter-tag-success', { 'filter-tag-success-active': filterStatus === 'active' }]"
                @click="quickFilterStatus('active')"
              >
                <span class="filter-tag-text">已激活</span>
              </div>
            </div>
          </div>

            <!-- 操作按钮 - 紧凑化 -->
            <div class="ml-auto flex items-center gap-1.5 flex-shrink-0">
              <a-button type="primary" @click="handleFilter" size="small" class="bg-blue-600 hover:bg-blue-700">
                <template #icon><SearchOutlined /></template>
                查询
              </a-button>
              <a-button @click="resetFilters" size="small">
                <template #icon><ClearOutlined /></template>
                重置
              </a-button>
            </div>
        </div>

        <!-- 批量操作区域 - 紧凑化 -->
        <div class="batch-actions" v-if="selectedRowKeys.length > 0">
          <a-alert
            :message="`已选择 ${selectedRowKeys.length} 条规则`"
            type="info"
            show-icon
            class="selection-alert mb-2"
          >
            <template #action>
              <a-space size="small">
                <a-button size="small" @click="batchActivate(true)">
                  <template #icon><CheckCircleOutlined /></template>
                  批量激活
                </a-button>
                <a-button size="small" @click="batchActivate(false)">
                  <template #icon><StopOutlined /></template>
                  批量停用
                </a-button>
                <a-button size="small" danger @click="batchDelete">
                  <template #icon><DeleteOutlined /></template>
                  批量删除
                </a-button>
                <a-button size="small" @click="selectedRowKeys = []">
                  取消选择
                </a-button>
              </a-space>
            </template>
          </a-alert>
        </div>

        <!-- 规则列表 - 更紧凑 -->
        <div class="rules-table-section">
          <a-card class="table-card compact-card" size="small">
            <template #title>
              <div class="table-header">
                <span class="table-title text-sm">
                  <FileTextOutlined class="table-icon text-sm" />
                  规则列表
                </span>
                <span class="table-count text-xs">共 {{ statistics.total }} 条规则</span>
              </div>
            </template>
            <template #extra>
              <a-space size="small">
                <a-button size="small" @click="exportRules">
                  <template #icon><ExportOutlined /></template>
                  导出规则
                </a-button>
              </a-space>
            </template>

            <a-table
            :columns="columns"
            :data-source="rules"
            :loading="loading"
            :pagination="pagination"
            :row-selection="rowSelection"
            row-key="id"
            @change="handleTableChange"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'rule_code'">
                <a-tag color="blue">{{ record.rule_code }}</a-tag>
              </template>

              <template v-else-if="column.key === 'source'">
                <div class="rule-source">
                  {{ record.name }}
                </div>
              </template>

              <template v-else-if="column.key === 'name'">
                <div class="rule-name">
                  {{ record.description }}
                </div>
              </template>

              <template v-else-if="column.key === 'primary_document_category'">
                <!-- 强制使用中文显示，优先使用resolvedPrimary，否则使用原始字段 -->
                <template v-if="record.resolvedPrimary || record.primary_document_category">
                  <a-tag :color="getDocumentCategoryDisplay(record.resolvedPrimary || record.primary_document_category)!.color">
                    {{ getDocumentCategoryDisplay(record.resolvedPrimary || record.primary_document_category)!.label }}
                  </a-tag>
                </template>
                <span v-else>-</span>
              </template>

              <template v-else-if="column.key === 'category'">
                <a-tag :color="getCategoryColor(record.category)">
                  {{ getCategoryLabel(record.category) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'severity'">
                <a-tag :color="getSeverityColor(record.severity)">
                  {{ getSeverityLabel(record.severity) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'rule_type'">
                <a-tag :color="getTypeColor(record.rule_type)">
                  {{ getTypeLabel(record.rule_type) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'is_active'">
                <a-switch
                  v-model:checked="record.is_active"
                  @change="(checked: boolean) => toggleRuleStatus(record, checked)"
                  :loading="record.updating"
                />
              </template>

              <template v-else-if="column.key === 'max_score'">
                <a-tag v-if="record.max_score === 0" color="red">单否</a-tag>
                <span v-else>{{ record.max_score }}分</span>
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-space>
                  <a-button type="link" size="small" @click="viewRule()">
                    查看
                  </a-button>
                  <a-button type="link" size="small" @click="editRule(record)">
                    编辑
                  </a-button>
                  <a-button type="link" size="small" @click="testRule()">
                    测试
                  </a-button>
                  <a-popconfirm
                    title="确定要删除这条规则吗？"
                    @confirm="deleteRule(record)"
                  >
                    <a-button type="link" size="small" danger>
                      删除
                    </a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
            </a-table>
          </a-card>
        </div>
        </div>

      <!-- 四川省质控规则标签页 -->
      <div v-else-if="activeTab === 'semantic'">
        <SemanticRulesView :show-header="false" />
      </div>

      <!-- 泸县33条规则标签页 -->
      <div v-else-if="activeTab === 'custom'">
        <CustomRulesManager />
      </div>

      <!-- 泸县存量质控规则标签页 -->
      <div v-else-if="activeTab === 'lx_legacy'">
        <CustomRulesManager mode="lx-legacy" />
      </div>

      <!-- 科室规则管理标签页 -->
      <div v-else-if="activeTab === 'department'">
        <DepartmentRulesTab />
      </div>
    </div>

    <!-- 创建/编辑规则模态框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="modalTitle"
      width="800px"
      @ok="handleModalOk"
      @cancel="handleModalCancel"
      :confirm-loading="modalLoading"
    >
      <div v-if="isCustomRule" class="mb-4">
        <a-steps size="small" :current="customStepCurrent">
          <a-step title="选择文书" :status="customStepStatuses[0]" />
          <a-step title="填写质控点" :status="customStepStatuses[1]" />
          <a-step title="生成Prompt" :status="customStepStatuses[2]" />
        </a-steps>
        <a-alert
          type="info"
          show-icon
          class="mt-3"
          message="先选择病历文书类型，再填写质控点内容，最后一键生成Prompt即可保存。"
        />
      </div>
      <a-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        layout="vertical"
      >
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="规则编码" name="rule_code">
              <a-input
                v-model:value="formData.rule_code"
                :placeholder="isCustomRule ? '系统自动生成' : '如: 1.1.1'"
                :disabled="isCustomRule"
              />
              <template v-if="isCustomRule" #extra>
                <span class="text-gray-500 text-xs">选择文书后将自动生成规则编号</span>
              </template>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="规则名称" name="name">
              <a-input v-model:value="formData.name" placeholder="输入规则名称" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="质控点内容" name="description">
          <a-textarea
            v-model:value="formData.description"
            placeholder="详细描述规则内容和检查要点"
            :rows="3"
          />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="病历文书类型" name="primary_document_category">
              <a-select
                v-model:value="formData.primary_document_category"
                placeholder="请选择文书类别"
                allowClear
              >
                <a-select-option
                  v-for="option in documentCategoryOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  <span>{{ option.label }}</span>
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="分类" name="category">
              <a-select v-model:value="formData.category" placeholder="选择分类">
                <a-select-option value="completeness">完整性</a-select-option>
                <a-select-option value="consistency">一致性</a-select-option>
                <a-select-option value="rationality">合理性</a-select-option>
                <a-select-option value="timeliness">及时性</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="严重程度" name="severity">
              <a-select v-model:value="formData.severity" placeholder="选择严重程度">
                <a-select-option value="critical">严重</a-select-option>
                <a-select-option value="major">重要</a-select-option>
                <a-select-option value="minor">轻微</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="规则类型" name="rule_type">
              <a-select v-model:value="formData.rule_type" placeholder="选择规则类型">
                <a-select-option value="logical">逻辑规则</a-select-option>
                <a-select-option value="semantic">语义规则</a-select-option>
                <a-select-option value="hybrid">混合规则</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="最大扣分" name="max_score">
              <a-input-number
                v-model:value="formData.max_score"
                :min="0"
                :max="100"
                placeholder="0表示单否"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="权重" name="weight">
              <a-input-number
                v-model:value="formData.weight"
                :min="0.1"
                :max="5.0"
                :step="0.1"
                placeholder="1.0"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="状态" name="is_active">
              <a-switch
                v-model:checked="formData.is_active"
                checked-children="激活"
                un-checked-children="停用"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="检查逻辑配置" name="check_logic">
          <a-textarea
            v-model:value="checkLogicText"
            placeholder="JSON格式的检查逻辑配置"
            :rows="4"
          />
        </a-form-item>

        <a-form-item label="提示模板" name="prompt_template">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm text-gray-500">生成后可根据需要微调Prompt模板</span>
            <a-button
              size="small"
              type="primary"
              @click="handleAutoGeneratePrompt"
              :loading="promptGenerating"
              :disabled="!formData.primary_document_category || !(formData.description && formData.description.trim())"
            >
              <ThunderboltOutlined />
              <span class="ml-1">一键生成Prompt</span>
            </a-button>
          </div>
          <a-textarea
            v-model:value="formData.prompt_template"
            placeholder="AI分析时使用的提示模板"
            :rows="6"
          />
        </a-form-item>
      </a-form>
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
import { ref, reactive, computed, onMounted, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import {
  PlusOutlined,
  ReloadOutlined,
  ImportOutlined,
  ExportOutlined,
  ClearOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  TagsOutlined,
  SettingOutlined,
  BranchesOutlined,
  ApartmentOutlined,
  AppstoreOutlined,
  SearchOutlined,
  StopOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
  ApiOutlined
} from '@ant-design/icons-vue'
import SemanticRulesView from './SemanticRulesView.vue'
import DepartmentRulesTab from '@/components/rules/DepartmentRulesTab.vue'
import CustomRulesManager from '@/components/CustomRulesManager.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'
import { DocumentCategoryService } from '@/services/document-category-service'
import { DocumentCategory } from '@/types/medical'
import { RulesService } from '@/services/rules-service'
import { lookupRuleCategories, normalizeCategories } from '@/qc/ruleDocumentMapping'
import type { EnhancedQCRule, QCRuleFilterParams } from '@/types/quality-control'
// import { RulesService } from '@/services/rules-service'
// import { RulesValidator } from '@/utils/rules-validator'
// import { RULES_CONFIG } from '@/config/rules-config'

// 模拟配置
const RULES_CONFIG = {
  categories: {
    completeness: { label: '完整性', color: 'blue' },
    consistency: { label: '一致性', color: 'green' },
    rationality: { label: '合理性', color: 'orange' },
    timeliness: { label: '及时性', color: 'purple' }
  },
  severities: {
    critical: { label: '严重', color: 'red' },
    major: { label: '重要', color: 'orange' },
    minor: { label: '轻微', color: 'blue' }
  },
  types: {
    logical: { label: '逻辑规则', color: 'cyan' },
    semantic: { label: '语义规则', color: 'magenta' },
    hybrid: { label: '混合规则', color: 'geekblue' }
  }
}

// 接口定义
interface QCRule {
  id: string
  rule_code: string
  name: string
  description: string
  primary_document_category?: DocumentCategory
  document_categories?: DocumentCategory[]
  category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
  rule_type: 'logical' | 'semantic' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  max_score: number
  weight: number
  is_active: boolean
  check_logic: Record<string, unknown>
  prompt_template?: string
  version: string
  created_at: string
  updated_at: string
  updating?: boolean
}

// 路由
const route = useRoute()
const router = useRouter()

// 响应式数据
const activeTab = ref('semantic') // 默认显示四川省质控规则
const TAB_DESCRIPTIONS: Record<string, string> = {
  semantic: '四川省住院病历语义质控规则：支持规则管理、导入与语义质控评估。',
  custom: '泸县33条质控规则：维护本地自定义质控点，支持批量评估与测试。',
  department: '科室级规则管理：配置覆盖策略、科室维度的质控规则及状态。',
  traditional: '传统质控规则：统一创建、导入、维护医院通用质控规则，并支持测试。'
}
const activeTabDescription = computed(() => TAB_DESCRIPTIONS[activeTab.value] || TAB_DESCRIPTIONS.traditional)
const loading = ref(false)
type ResolvedRule = EnhancedQCRule & {
  resolvedPrimary?: DocumentCategory
  normalizedCategories: DocumentCategory[]
}

const rules = ref<ResolvedRule[]>([])
const selectedRowKeys = ref<string[]>([])
const searchText = ref('')
const filterCategory = ref<string>()
const filterDocumentCategory = ref<DocumentCategory>()
const filterSeverity = ref<string>()
const filterType = ref<string>()
const filterStatus = ref<string>()

// 文书类别相关数据（仅来源于数据库，不再回退到内置配置）
const documentCategoryOptions = ref<Array<{ value: DocumentCategory; label: string; description?: string; color?: string; icon?: string }>>([])
const documentCategoryStats = ref<Record<string, number>>({})
const categoriesLoaded = ref(false)

// 仅从数据库加载文书类别，失败则抛出错误，不使用硬编码回退
const loadDocumentCategoryOptions = async () => {
  try {
    const categories = await DocumentCategoryService.getDocumentCategories()
    if (!categories || categories.length === 0) {
      throw new Error('未找到文书类别配置，请检查数据库中的 document_category_config 表')
    }

    // 验证只包含6个标准类别
    const canonical = new Set([
      'admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'
    ])
    const nonCanonical = categories.filter((c: unknown) => !canonical.has(c.category_code))
    if (nonCanonical.length > 0) {
      console.warn('⚠️ 发现非标准文书类别，将被过滤:', nonCanonical.map((c: unknown) => c.category_code))
    }

    // 只使用6个标准类别
    const validCategories = categories.filter((c: unknown) => canonical.has(c.category_code))
    if (validCategories.length === 0) {
      throw new Error('未找到有效的标准文书类别配置')
    }

    documentCategoryOptions.value = validCategories
      .sort((a: unknown, b: unknown) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
      .map((cfg: unknown) => {
        const disp = DocumentCategoryService.getDocumentCategoryDisplayConfig(cfg.category_code as DocumentCategory)
        return {
          value: cfg.category_code as DocumentCategory,
          label: cfg.category_name,
          description: cfg.category_description || cfg.description,
          color: disp.color,
          icon: disp.icon
        }
      })
    categoriesLoaded.value = true

    console.log('📄 已加载文书类别选项:', documentCategoryOptions.value.map(o => o.label).join(', '))
  } catch (error) {
    console.error('加载文书类别失败:', error)
    categoriesLoaded.value = false
    throw error // 重新抛出错误，让调用方处理
  }
}

// LLM 设置相关
const llmSettingsVisible = ref(false)

// 模态框相关
const modalVisible = ref(false)
const modalLoading = ref(false)
const modalTitle = ref('')
const formRef = ref()
const isEditing = ref(false)
const editingId = ref<string>()
const isCustomRule = ref(false)

// 表单数据
const formData = reactive({
  rule_code: '',
  name: '',
  description: '',
  primary_document_category: '' as DocumentCategory | '',
  document_categories: [] as DocumentCategory[],
  category: 'completeness' as const,
  rule_type: 'logical' as const,
  severity: 'minor' as const,
  max_score: 0,
  weight: 1.0,
  is_active: true,
  check_logic: {},
  prompt_template: '',
  version: '1.0'
})

const checkLogicText = ref('')
const promptGenerating = ref(false)

const customStepCurrent = computed(() => {
  if (!isCustomRule.value) return 0
  if (!formData.primary_document_category) return 0
  if (!formData.description.trim()) return 1
  return 2
})

const customStepStatuses = computed(() => {
  if (!isCustomRule.value) {
    return ['process', 'wait', 'wait'] as Array<'wait' | 'process' | 'finish'>
  }

  const docSelected = Boolean(formData.primary_document_category)
  const contentFilled = docSelected && Boolean(formData.description.trim())
  const promptReady = contentFilled && Boolean(formData.prompt_template.trim())

  return [
    docSelected ? 'finish' : 'process',
    contentFilled ? (promptReady ? 'finish' : 'process') : docSelected ? 'process' : 'wait',
    promptReady ? 'finish' : 'wait'
  ] as Array<'wait' | 'process' | 'finish'>
})

const collectRuleCodesByCategory = () => {
  const map = new Map<string, string[]>()
  const pushCode = (categoryKey: string | undefined, code?: string | null) => {
    if (!categoryKey || !code) return
    if (!map.has(categoryKey)) {
      map.set(categoryKey, [])
    }
    map.get(categoryKey)!.push(code)
  }

  rules.value.forEach(rule => {
    const resolved = rule.primary_document_category || (rule as ResolvedRule).resolvedPrimary
    pushCode(resolved as string | undefined, rule.rule_code)
  })

  mockRules.forEach(rule => {
    pushCode(rule.primary_document_category as string | undefined, rule.rule_code)
  })

  return map
}

const formatRuleCode = (prefix: string, number: number) => {
  const normalizedPrefix = prefix.endsWith('-') ? prefix : `${prefix}-`
  return `${normalizedPrefix}${String(number).padStart(3, '0')}`
}

const extractCodeInfo = (code: string) => {
  const match = code.trim().match(/^([A-Za-z]+-?)(\d{1,})$/)
  if (match) {
    const [, rawPrefix, rawNumber] = match
    const prefix = rawPrefix
    const number = parseInt(rawNumber, 10)
    if (!Number.isNaN(number)) {
      return { prefix, number }
    }
  }
  return null
}

const generateNextRuleCode = (category?: DocumentCategory | '') => {
  const codeBuckets = collectRuleCodesByCategory()
  const searchOrder: Array<string | undefined> = []
  if (category) {
    searchOrder.push(category)
  }
  searchOrder.push(undefined)

  for (const key of searchOrder) {
    const codes = key ? codeBuckets.get(key) : Array.from(codeBuckets.values()).flat()
    if (!codes || codes.length === 0) continue

    let candidatePrefix = 'SC-'
    let maxNumber = 0

    codes.forEach(code => {
      if (!code) return
      const info = extractCodeInfo(code)
      if (!info) return
      const { prefix, number } = info
      if (number >= maxNumber) {
        maxNumber = number
        candidatePrefix = prefix
      }
    })

    if (maxNumber > 0) {
      return formatRuleCode(candidatePrefix, maxNumber + 1)
    }
  }

  return formatRuleCode('SC-', 1)
}

const assignRuleCodeForCustomRule = () => {
  if (!isCustomRule.value) return
  const nextCode = generateNextRuleCode(formData.primary_document_category)
  formData.rule_code = nextCode
}

watch(() => formData.primary_document_category, () => {
  if (isCustomRule.value) {
    assignRuleCodeForCustomRule()
  }
})

watch(rules, () => {
  if (isCustomRule.value) {
    assignRuleCodeForCustomRule()
  }
})

// 表单验证规则
const formRules = {
  rule_code: [
    { required: true, message: '请输入规则编码' },
    { pattern: /^\d+(\.\d+)*$/, message: '规则编码格式不正确，如: 1.1.1' }
  ],
  name: [
    { required: true, message: '请输入规则名称' },
    { min: 2, max: 100, message: '规则名称长度在2-100个字符' }
  ],
  description: [
    { required: true, message: '请输入质控点内容' },
    { min: 10, max: 500, message: '质控点内容长度在10-500个字符' }
  ],
  primary_document_category: [
    { required: true, message: '请选择病历文书类型' }
  ],
  category: [{ required: true, message: '请选择规则分类' }],
  rule_type: [{ required: true, message: '请选择规则类型' }],
  severity: [{ required: true, message: '请选择严重程度' }],
  max_score: [{ required: true, type: 'number', min: 0, max: 100, message: '最大扣分范围0-100' }],
  weight: [{ required: true, type: 'number', min: 0.1, max: 5.0, message: '权重范围0.1-5.0' }]
}

// 分页配置 - 增加每页显示数量，提高空间利用率
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  pageSizeOptions: ['10', '20', '50', '100'],
  showTotal: (total: number, range: [number, number]) =>
    `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
  size: 'small'
})

// 表格列配置 - 紧凑化宽度
const columns: TableColumnsType = [
  {
    title: '编码',
    dataIndex: 'rule_code',
    key: 'rule_code',
    width: 70,
    sorter: true
  },
  {
    title: '质控点来源',
    dataIndex: 'name',
    key: 'source',
    width: 150
  },
  {
    title: '质控点名称',
    dataIndex: 'description',
    key: 'name',
    width: 180
  },
  {
    title: '文书类别',
    key: 'primary_document_category',
    width: 90,
    // 暂时禁用表格列筛选器，只使用顶部的筛选器
    // filters: documentCategoryOptions.value.map(option => ({
    //   text: option.label,
    //   value: option.value
    // }))
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    width: 70,
    filters: [
      { text: '完整性', value: 'completeness' },
      { text: '一致性', value: 'consistency' },
      { text: '合理性', value: 'rationality' },
      { text: '及时性', value: 'timeliness' }
    ]
  },
  {
    title: '严重程度',
    dataIndex: 'severity',
    key: 'severity',
    width: 75,
    filters: [
      { text: '严重', value: 'critical' },
      { text: '重要', value: 'major' },
      { text: '轻微', value: 'minor' }
    ]
  },
  {
    title: '类型',
    dataIndex: 'rule_type',
    key: 'rule_type',
    width: 70,
    filters: [
      { text: '逻辑规则', value: 'logical' },
      { text: '语义规则', value: 'semantic' },
      { text: '混合规则', value: 'hybrid' }
    ]
  },
  {
    title: '扣分',
    dataIndex: 'max_score',
    key: 'max_score',
    width: 60,
    sorter: true
  },
  {
    title: '权重',
    dataIndex: 'weight',
    key: 'weight',
    width: 50,
    sorter: true
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    key: 'is_active',
    width: 50
  },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    fixed: 'right'
  }
]

// 行选择配置
const rowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  }
}))
// 让表头“文书类别”筛选项跟随选项变化而更新
// 暂时禁用表格列筛选器的动态更新，只使用顶部筛选器
// watch(documentCategoryOptions, (opts) => {
//   const col = (columns as any[]).find(c => c.key === 'primary_document_category')
//   if (col) {
//     col.filters = (opts || []).map((o: unknown) => ({ text: o.label, value: o.value }))
//   }
// }, { immediate: true })


// 计算属性
const statistics = computed(() => {
  const total = rules.value.length
  const active = rules.value.filter(r => r.is_active).length
  const critical = rules.value.filter(r => r.severity === 'critical').length
  const categories = new Set(rules.value.map(r => r.category)).size

  return { total, active, critical, categories }
})



// 工具函数
const getCategoryColor = (category: string) => {
  return RULES_CONFIG.categories[category as keyof typeof RULES_CONFIG.categories]?.color || 'default'
}

const getCategoryLabel = (category: string) => {
  return RULES_CONFIG.categories[category as keyof typeof RULES_CONFIG.categories]?.label || category
}

const getSeverityColor = (severity: string) => {
  return RULES_CONFIG.severities[severity as keyof typeof RULES_CONFIG.severities]?.color || 'default'
}

const getSeverityLabel = (severity: string) => {
  return RULES_CONFIG.severities[severity as keyof typeof RULES_CONFIG.severities]?.label || severity
}

const getTypeColor = (type: string) => {
  return RULES_CONFIG.types[type as keyof typeof RULES_CONFIG.types]?.color || 'default'
}

const getTypeLabel = (type: string) => {
  return RULES_CONFIG.types[type as keyof typeof RULES_CONFIG.types]?.label || type
}

// 文书类别显示函数

const getDocumentCategoryDisplay = (category?: DocumentCategory) => {
  if (!category) return undefined

  try {
    const config = DocumentCategoryService.getDocumentCategoryDisplayConfig(category)
    // 确保返回中文标签而不是英文代码
    if (config.label === category) {
      return { label: '未分类', color: '#666666' }
    }
    return { label: config.label, color: config.color }
  } catch (error) {
    console.warn('获取文书类别显示配置失败:', category, error)
    return { label: '未分类', color: '#666666' }
  }
}

// 标准文书类别集合
const CANONICAL_CATEGORIES = new Set([
  'admission_record', 'progress_note', 'discharge_record',
  'operation_record', 'examination_report', 'consent_form'
])

// 过滤并保留标准类别
const filterCanonicalCategories = (categories: string[]): DocumentCategory[] => {
  return categories.filter(cat => CANONICAL_CATEGORIES.has(cat)) as DocumentCategory[]
}

const augmentRuleWithDocumentCategories = (rule: EnhancedQCRule): ResolvedRule => {
  const clone: ResolvedRule = { ...rule, normalizedCategories: [] }

  // 获取各种来源的类别
  const primaryCandidates = filterCanonicalCategories(normalizeCategories(
    rule.primary_document_category ? [rule.primary_document_category] : []
  ))
  const directCategories = filterCanonicalCategories(normalizeCategories((rule as any).document_categories))
  const checkLogicCategories = filterCanonicalCategories(normalizeCategories((rule as any)?.check_logic?.applicable_documents))
  const inferredCategories = filterCanonicalCategories(lookupRuleCategories(rule))

  // 合并所有类别
  const allCategories = [
    ...primaryCandidates,
    ...directCategories,
    ...checkLogicCategories,
    ...inferredCategories
  ]
  clone.normalizedCategories = Array.from(new Set(allCategories))

  // 按优先级选择主要类别
  clone.resolvedPrimary = primaryCandidates[0] ||
                          directCategories[0] ||
                          checkLogicCategories[0] ||
                          inferredCategories[0]

  return clone
}


// 模拟数据
const mockRules: QCRule[] = [
  {
    id: '1',
    rule_code: '1.1.1',
    name: '入院记录完整性检查',
    description: '检查入院记录是否包含必要的基本信息，包括患者基本信息、主诉、现病史、既往史等',
    primary_document_category: 'admission_record',
    category: 'completeness',
    rule_type: 'logical',
    severity: 'critical',
    max_score: 0,
    weight: 2.0,
    is_active: true,
    check_logic: {
      required_fields: ['patient_name', 'admission_date', 'chief_complaint', 'present_illness']
    },
    prompt_template: '请检查入院记录是否包含以下必要信息：患者姓名、入院日期、主诉、现病史',
    version: '1.0',
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z'
  },
  {
    id: '2',
    rule_code: '1.2.1',
    name: '诊断一致性检查',
    description: '检查入院诊断与出院诊断的一致性，确保诊断变更有合理依据',
    primary_document_category: 'discharge_record',
    category: 'consistency',
    rule_type: 'hybrid',
    severity: 'major',
    max_score: 5,
    weight: 1.5,
    is_active: true,
    check_logic: {
      compare_fields: ['admission_diagnosis', 'discharge_diagnosis'],
      tolerance: 0.8
    },
    prompt_template: '请分析入院诊断与出院诊断的一致性，如有变更请说明理由',
    version: '1.0',
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:30:00Z'
  },
  {
    id: '3',
    rule_code: '2.1.1',
    name: '用药合理性检查',
    description: '检查药物使用是否符合适应症，剂量是否合理，是否存在禁忌症',
    primary_document_category: 'progress_note',
    category: 'rationality',
    rule_type: 'semantic',
    severity: 'critical',
    max_score: 0,
    weight: 3.0,
    is_active: true,
    check_logic: {
      drug_interaction_check: true,
      dosage_check: true,
      contraindication_check: true
    },
    prompt_template: '请评估患者的用药方案是否合理，包括适应症、剂量、禁忌症等方面',
    version: '1.0',
    created_at: '2024-01-15T11:00:00Z',
    updated_at: '2024-01-15T11:00:00Z'
  },
  {
    id: '4',
    rule_code: '3.1.1',
    name: '手术记录及时性检查',
    description: '检查手术记录是否在规定时间内完成，确保医疗文书的及时性',
    primary_document_category: 'operation_record',
    category: 'timeliness',
    rule_type: 'logical',
    severity: 'major',
    max_score: 3,
    weight: 1.0,
    is_active: true,
    check_logic: {
      time_limit: 24,
      time_unit: 'hours'
    },
    prompt_template: '请检查手术记录是否在术后24小时内完成',
    version: '1.0',
    created_at: '2024-01-15T11:30:00Z',
    updated_at: '2024-01-15T11:30:00Z'
  },
  {
    id: '5',
    rule_code: '1.1.2',
    name: '病程记录完整性检查',
    description: '检查病程记录是否按规定频次记录，内容是否完整',
    primary_document_category: 'progress_note',
    category: 'completeness',
    rule_type: 'logical',
    severity: 'minor',
    max_score: 2,
    weight: 1.0,
    is_active: false,
    check_logic: {
      frequency_check: true,
      content_completeness: ['symptoms', 'treatment', 'response']
    },
    prompt_template: '请检查病程记录的频次和内容完整性',
    version: '1.0',
    created_at: '2024-01-15T12:00:00Z',
    updated_at: '2024-01-15T12:00:00Z'
  },
  {
    id: '6',
    rule_code: '2.2.1',
    name: '检查结果合理性分析',
    description: '分析检查结果是否与临床表现相符，是否需要进一步检查',
    primary_document_category: 'examination_report',
    category: 'rationality',
    rule_type: 'hybrid',
    severity: 'major',
    max_score: 4,
    weight: 1.8,
    is_active: true,
    check_logic: {
      clinical_correlation: true,
      reference_range_check: true
    },
    prompt_template: '请分析检查结果与临床表现的相关性，评估是否需要进一步检查',
    version: '1.0',
    created_at: '2024-01-15T12:30:00Z',
    updated_at: '2024-01-15T12:30:00Z'
  }
]

// 模拟服务
const fallbackRulesService = {
  getAllRules: async () => {
    await new Promise(resolve => setTimeout(resolve, 500)) // 模拟网络延迟
    return mockRules
  },
  createRule: async (ruleData: unknown) => {
    await new Promise(resolve => setTimeout(resolve, 300))
    const newRule = {
      ...ruleData,
      id: Date.now().toString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    mockRules.push(newRule)
    return newRule
  },
  updateRule: async (id: string, ruleData: unknown) => {
    await new Promise(resolve => setTimeout(resolve, 300))
    const index = mockRules.findIndex(r => r.id === id)
    if (index !== -1) {
      mockRules[index] = { ...mockRules[index], ...ruleData, updated_at: new Date().toISOString() }
    }
    return mockRules[index]
  },
  deleteRule: async (id: string) => {
    await new Promise(resolve => setTimeout(resolve, 300))
    const index = mockRules.findIndex(r => r.id === id)
    if (index !== -1) {
      mockRules.splice(index, 1)
    }
  },
  toggleRuleStatus: async (id: string, isActive: boolean) => {
    await new Promise(resolve => setTimeout(resolve, 200))
    const rule = mockRules.find(r => r.id === id)
    if (rule) {
      rule.is_active = isActive
      rule.updated_at = new Date().toISOString()
    }
  },
  batchUpdateRuleStatus: async (ids: string[], isActive: boolean) => {
    await new Promise(resolve => setTimeout(resolve, 500))
    ids.forEach(id => {
      const rule = mockRules.find(r => r.id === id)
      if (rule) {
        rule.is_active = isActive
        rule.updated_at = new Date().toISOString()
      }
    })
  },
  deleteRules: async (ids: string[]) => {
    await new Promise(resolve => setTimeout(resolve, 500))
    ids.forEach(id => {
      const index = mockRules.findIndex(r => r.id === id)
      if (index !== -1) {
        mockRules.splice(index, 1)
      }
    })
  },
  exportRules: async () => {
    await new Promise(resolve => setTimeout(resolve, 300))
    return JSON.stringify(mockRules, null, 2)
  }
}

// 模拟验证器
const buildSupabaseRulePayload = (ruleData: unknown) => {
  const payload: unknown = {
    ...ruleData,
    check_logic: ruleData.check_logic || {},
    prompt_template: ruleData.prompt_template || null
  }

  if (payload.primary_document_category) {
    const docCategories = Array.isArray(ruleData.document_categories) ? ruleData.document_categories : []
    payload.document_categories = docCategories.length > 0
      ? docCategories
      : [payload.primary_document_category]
  } else {
    delete payload.primary_document_category
    delete payload.document_categories
  }

  // Supabase 列没有 updating 字段，确保不传临时属性
  delete payload.updating

  return payload
}

const rulesRepository = {
  async createRule(ruleData: unknown) {
    const payload = buildSupabaseRulePayload(ruleData)
    try {
      return await RulesService.createRule(payload)
    } catch (error) {
      console.error('Supabase 创建规则失败，降级到本地模拟:', error)
      message.warning('Supabase 未连接，已使用本地模拟创建规则')
      return fallbackRulesService.createRule(ruleData)
    }
  },
  async updateRule(id: string, ruleData: unknown) {
    const payload = buildSupabaseRulePayload(ruleData)
    try {
      return await RulesService.updateRule(id, payload)
    } catch (error) {
      console.error('Supabase 更新规则失败，降级到本地模拟:', error)
      message.warning('Supabase 未连接，已使用本地模拟更新规则')
      return fallbackRulesService.updateRule(id, ruleData)
    }
  },
  async deleteRule(id: string) {
    try {
      await RulesService.deleteRule(id)
    } catch (error) {
      console.error('Supabase 删除规则失败，降级到本地模拟:', error)
      message.warning('Supabase 未连接，已在本地模拟删除规则')
      await fallbackRulesService.deleteRule(id)
    }
  },
  async toggleRuleStatus(id: string, isActive: boolean) {
    try {
      return await RulesService.toggleRuleStatus(id, isActive)
    } catch (error) {
      console.error('Supabase 更新规则状态失败，降级到本地模拟:', error)
      message.warning('Supabase 未连接，已在本地模拟更新规则状态')
      return fallbackRulesService.toggleRuleStatus(id, isActive)
    }
  },
  async batchUpdateRuleStatus(ids: string[], isActive: boolean) {
    try {
      await RulesService.batchUpdateRuleStatus(ids, isActive)
    } catch (error) {
      console.error('Supabase 批量更新规则状态失败，降级到本地模拟:', error)
      message.warning('Supabase 未连接，已在本地模拟批量更新状态')
      await fallbackRulesService.batchUpdateRuleStatus(ids, isActive)
    }
  },
  async deleteRules(ids: string[]) {
    try {
      await RulesService.deleteRules(ids)
    } catch (error) {
      console.error('Supabase 批量删除规则失败，降级到本地模拟:', error)
      message.warning('Supabase 未连接，已在本地模拟批量删除')
      await fallbackRulesService.deleteRules(ids)
    }
  },
  async exportRules() {
    try {
      const supabaseRules = await RulesService.getAllRules()
      return JSON.stringify(supabaseRules, null, 2)
    } catch (error) {
      console.error('Supabase 导出规则失败，使用本地模拟数据:', error)
      message.warning('Supabase 未连接，导出内容来自本地模拟数据')
      return fallbackRulesService.exportRules()
    }
  }
}

const mockRulesValidator = {
  validateRule: (ruleData: unknown) => {
    const errors: string[] = []
    const warnings: string[] = []

    if (!ruleData.rule_code) errors.push('规则编码不能为空')
    if (!ruleData.name) errors.push('规则名称不能为空')
    if (!ruleData.description) errors.push('质控点内容不能为空')
    if (!ruleData.primary_document_category) errors.push('文书类型不能为空')

    if (ruleData.max_score < 0 || ruleData.max_score > 100) {
      errors.push('最大扣分必须在0-100之间')
    }

    if (ruleData.weight < 0.1 || ruleData.weight > 5.0) {
      warnings.push('权重建议在0.1-5.0之间')
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings
    }
  }
}

// 数据加载（严格依赖数据库的文书类别和规则数据，不再回退到本地/模拟数据）
const loadRules = async () => {
  loading.value = true
  try {
    if (!categoriesLoaded.value) {
      throw new Error('Document categories not loaded')
    }
    const filters: QCRuleFilterParams = {
      keyword: searchText.value,
      category: filterCategory.value,
      document_category: filterDocumentCategory.value,
      rule_type: filterType.value as any,
      severity: filterSeverity.value as any,
      is_active: filterStatus.value === 'active' ? true : filterStatus.value === 'inactive' ? false : undefined,
      page: pagination.current,
      pageSize: pagination.pageSize
    }
    const result = await DocumentCategoryService.getEnhancedQCRules(filters)
    rules.value = (result.data || []).map(r => augmentRuleWithDocumentCategories(r))

    // 调试输出
    console.log(`📘 [RulesView] 已加载 ${rules.value.length} 条规则`)

    // 调试：检查规则中的文书类别值
    const categoryValues = new Set()
    rules.value.forEach(rule => {
      if (rule.primary_document_category) categoryValues.add(rule.primary_document_category)
      if (rule.resolvedPrimary) categoryValues.add(rule.resolvedPrimary)
    })
    console.log('📋 [RulesView] 规则中的文书类别值:', Array.from(categoryValues))
    console.log('📋 [RulesView] documentCategoryOptions:', documentCategoryOptions.value.map(o => `${o.value}:${o.label}`))

    pagination.total = result.total
  } finally {
    loading.value = false
  }
}

const reloadRulesSafely = async () => {
  try {
    await loadRules()
  } catch (error) {
    console.error('刷新规则失败:', error)
  }
}

// LLM 设置相关方法
const showLLMSettings = () => {
  llmSettingsVisible.value = true
}

// 事件处理
const handleTabChange = (key: string) => {
  activeTab.value = key
  // 可以在这里添加标签页切换时的逻辑
  console.log('切换到标签页:', key)
}

const refreshRules = async () => {
  try {
    await loadDocumentCategoryOptions()
    await loadRules()
    await loadDocumentCategoryStats()
  } catch (e) {
    console.error('刷新失败:', e)
    const errorMsg = e instanceof Error ? e.message : '未知错误'
    message.error(`加载失败: ${errorMsg}`)
    // 不显示任何数据，确保用户看到错误而不是不一致的数据
    documentCategoryOptions.value = []
    rules.value = []
  }
}

const handleSearch = () => {
  pagination.current = 1
  reloadRulesSafely()
}

const handleFilter = () => {
  // 重置分页到第一页并重新加载数据
  pagination.current = 1
  reloadRulesSafely()
}

const resetFilters = () => {
  searchText.value = ''
  filterCategory.value = undefined
  filterDocumentCategory.value = undefined
  filterSeverity.value = undefined
  filterType.value = undefined
  filterStatus.value = undefined
  handleFilter()
}

const clearAllFilters = resetFilters

// 通用快速筛选函数
const createQuickFilter = <T>(filterRef: Ref<T | undefined>, needsHandleFilter = true) => {
  return (value: T) => {
    filterRef.value = filterRef.value === value ? undefined : value
    if (needsHandleFilter) handleFilter()
  }
}

// 文书类别相关方法
const clearDocumentCategoryFilter = () => {
  filterDocumentCategory.value = undefined
  handleFilter()
}

const quickFilterDocumentCategory = createQuickFilter(filterDocumentCategory, true)
const quickFilterCategory = createQuickFilter(filterCategory)
const quickFilterSeverity = createQuickFilter(filterSeverity)
const quickFilterStatus = createQuickFilter(filterStatus)

// 加载文书类别统计
const loadDocumentCategoryStats = async () => {
  try {
    const stats = await DocumentCategoryService.getDocumentCategoryStats()
    documentCategoryStats.value = stats

    // 调试输出
    console.log('📊 [RulesView] 文书类别统计数据:', stats)
    console.log('📊 [RulesView] 统计数据的键:', Object.keys(stats))
  } catch (error) {
    console.error('加载文书类别统计失败:', error)
  }
}

const batchActivate = async (isActive: boolean) => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先选择要操作的规则')
    return
  }

  try {
    loading.value = true
    await rulesRepository.batchUpdateRuleStatus(selectedRowKeys.value, isActive)
    message.success(`批量${isActive ? '激活' : '停用'}成功`)
    selectedRowKeys.value = []
    await reloadRulesSafely()
  } catch (error) {
    console.error('批量操作失败:', error)
    message.error(error instanceof Error ? error.message : '批量操作失败')
  } finally {
    loading.value = false
  }
}

const batchDelete = async () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先选择要删除的规则')
    return
  }

  try {
    loading.value = true
    await rulesRepository.deleteRules(selectedRowKeys.value)
    message.success(`批量删除 ${selectedRowKeys.value.length} 条规则成功`)
    selectedRowKeys.value = []
    await reloadRulesSafely()
  } catch (error) {
    console.error('批量删除失败:', error)
    message.error(error instanceof Error ? error.message : '批量删除失败')
  } finally {
    loading.value = false
  }
}

const handleTableChange: TableProps['onChange'] = (pag) => {
  if (pag) {
    pagination.current = pag.current || 1
    pagination.pageSize = pag.pageSize || pagination.pageSize
    reloadRulesSafely()
  }
}

// 规则操作
const showCreateModal = () => {
  isEditing.value = false
  isCustomRule.value = false
  modalTitle.value = '新增规则'
  resetFormData()
  modalVisible.value = true
}

const showCustomRuleModal = () => {
  isEditing.value = false
  isCustomRule.value = true
  modalTitle.value = '新增自定义质控点'
  resetFormData()
  formData.rule_type = 'semantic'
  modalVisible.value = true
}

const editRule = (rule: ResolvedRule) => {
  isEditing.value = true
  editingId.value = rule.id
  isCustomRule.value = false
  modalTitle.value = '编辑规则'

  // 填充表单数据
  Object.assign(formData, {
    rule_code: rule.rule_code,
    name: rule.name,
    description: rule.description,
    primary_document_category: (rule.primary_document_category || (rule as ResolvedRule).resolvedPrimary || '') as DocumentCategory | '',
    document_categories: ((rule as any).document_categories || (rule as ResolvedRule).normalizedCategories || []) as DocumentCategory[],
    category: rule.category,
    rule_type: rule.rule_type,
    severity: rule.severity,
    max_score: rule.max_score,
    weight: rule.weight,
    is_active: rule.is_active,
    check_logic: rule.check_logic,
    prompt_template: rule.prompt_template || '',
    version: rule.version
  })

  checkLogicText.value = JSON.stringify(rule.check_logic, null, 2)
  modalVisible.value = true
}

const viewRule = () => {
  // 可以打开详情页面或模态框
  message.info('查看规则详情功能待实现')
}

const testRule = () => {
  // 可以打开测试页面
  message.info('规则测试功能待实现')
}

const deleteRule = async (rule: QCRule) => {
  try {
    await rulesRepository.deleteRule(rule.id)
    message.success('删除成功')
    await reloadRulesSafely()
  } catch (error) {
    console.error('删除规则失败:', error)
    message.error(error instanceof Error ? error.message : '删除规则失败')
  }
}

const toggleRuleStatus = async (rule: QCRule, checked: boolean) => {
  try {
    rule.updating = true
    await rulesRepository.toggleRuleStatus(rule.id, checked)
    rule.is_active = checked
    message.success(checked ? '规则已激活' : '规则已停用')
  } catch (error) {
    console.error('更新规则状态失败:', error)
    message.error(error instanceof Error ? error.message : '更新规则状态失败')
    rule.is_active = !checked // 回滚状态
  } finally {
    rule.updating = false
  }
}


// 模态框操作
const handleModalOk = async () => {
  try {
    if (isCustomRule.value) {
      assignRuleCodeForCustomRule()
    }
    await formRef.value.validate()
    modalLoading.value = true

    // 解析检查逻辑JSON
    let checkLogic = {}
    if (checkLogicText.value.trim()) {
      try {
        checkLogic = JSON.parse(checkLogicText.value)
      } catch (e) {
        message.error('检查逻辑JSON格式不正确')
        return
      }
    }

    const ruleData = {
      ...formData,
      check_logic: checkLogic
    }

    if (isCustomRule.value && !(formData.prompt_template && formData.prompt_template.trim())) {
      message.error('请先点击“一键生成Prompt”生成提示模板')
      return
    }

    // 验证规则数据
    const validation = mockRulesValidator.validateRule(ruleData)
    if (!validation.isValid) {
      message.error(`规则验证失败: ${validation.errors.join(', ')}`)
      return
    }

    if (validation.warnings.length > 0) {
      console.warn('规则验证警告:', validation.warnings)
    }

    if (isEditing.value && editingId.value) {
      // 更新规则
      await rulesRepository.updateRule(editingId.value, ruleData)
      message.success('更新规则成功')
    } else {
      // 创建规则
      await rulesRepository.createRule(ruleData)
      message.success('创建规则成功')
    }

    modalVisible.value = false
    isCustomRule.value = false
    await reloadRulesSafely()
  } catch (error) {
    console.error('保存规则失败:', error)
    message.error(error instanceof Error ? error.message : '保存规则失败')
  } finally {
    modalLoading.value = false
  }
}

const handleModalCancel = () => {
  modalVisible.value = false
  isCustomRule.value = false
  resetFormData()
}

const resetFormData = () => {
  Object.assign(formData, {
    rule_code: '',
    name: '',
    description: '',
    primary_document_category: '' as DocumentCategory | '',
    document_categories: [] as DocumentCategory[],
    category: 'completeness',
    rule_type: 'logical',
    severity: 'minor',
    max_score: 0,
    weight: 1.0,
    is_active: true,
    check_logic: {},
    prompt_template: '',
    version: '1.0'
  })
  checkLogicText.value = ''
  formRef.value?.resetFields()
}

const handleAutoGeneratePrompt = async () => {
  if (!formData.primary_document_category) {
    message.warning('请先选择病历文书类型')
    return
  }

  const trimmedDescription = (formData.description || '').trim()
  if (!trimmedDescription) {
    message.warning('请先填写质控点的具体要求')
    return
  }

  promptGenerating.value = true
  try {
    const display = DocumentCategoryService.getDocumentCategoryDisplayConfig(
      formData.primary_document_category as DocumentCategory
    )
    const ruleName = (formData.name || '').trim() || '自定义质控点'
    const docLabel = display.label || '医疗文书'

    const promptLines = [
      `你是一名专业的${docLabel}质控专家，熟悉国内医疗质量控制标准。`,
      `请阅读一份${docLabel}，并围绕以下自定义质控点进行审核：`,
      `【质控点名称】${ruleName}`,
      `【质控点要求】${trimmedDescription}`,
      '请按照质控规范判断文书是否达标，并以JSON格式返回：',
      '{',
      '  "is_compliant": true | false,',
      '  "issues": [',
      '    {',
      '      "description": "问题描述",',
      '      "evidence": "相关原文",',
      '      "suggestion": "整改建议",',
      '      "severity": "critical | major | minor"',
      '    }',
      '  ],',
      '  "summary": "总体评价和提醒"',
      '}',
      '如不存在问题，请返回 is_compliant 为 true，issues 为空数组，summary 说明符合要求。'
    ]

    formData.prompt_template = promptLines.join('\n')
    message.success('已为该质控点生成Prompt模板')
  } catch (error) {
    console.error('自动生成Prompt失败:', error)
    message.error('自动生成Prompt失败，请稍后重试')
  } finally {
    promptGenerating.value = false
  }
}

// 导入导出
const importRules = () => {
  message.info('规则导入功能待实现')
}

const exportRules = async () => {
  try {
    const exportData = await rulesRepository.exportRules()
    const blob = new Blob([exportData], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `qc-rules-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    message.success('规则导出成功')
  } catch (error) {
    console.error('导出规则失败:', error)
    message.error('导出规则失败')
  }
}

// 生命周期
onMounted(async () => {
  // 从 query 参数中读取标签页
  const tabFromQuery = route.query.tab as string
  if (tabFromQuery && ['traditional', 'semantic', 'department'].includes(tabFromQuery)) {
    activeTab.value = tabFromQuery
  }

  try {
    await loadDocumentCategoryOptions()
    await loadRules()
    await loadDocumentCategoryStats()
  } catch (e) {
    console.error('初始化数据失败:', e)
    const errorMsg = e instanceof Error ? e.message : '未知错误'
    message.error(`初始化失败: ${errorMsg}`)
    // 确保不显示任何可能不一致的数据
    documentCategoryOptions.value = []
    rules.value = []
  }
})

// 监听标签页切换，更新 URL query 参数
watch(activeTab, (newTab) => {
  if (route.query.tab !== newTab) {
    router.replace({ query: { ...route.query, tab: newTab } })
  }
})
</script>

<style scoped>
/* 主容器样式 */
.page-container {
  padding: 0;
  background: transparent;
  min-height: auto;
}

/* 标签页样式 - 更紧凑 */
.rules-tabs {
  @apply mb-1;
}

:deep(.rules-tabs .ant-tabs-nav) {
  @apply mb-1;
}

:deep(.rules-tabs .ant-tabs-tab) {
  @apply px-3 py-1;
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
  @apply mr-1;
  font-size: 16px;
}

/* 自定义Tab标题（覆盖之前的 text-xs 小号样式） */
:deep(.qc-tab-title) {
  font-size: 16px !important;
  font-weight: 700;
  color: #1f2937;
  line-height: 1.2;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* 确保图标随字号放大 */
:deep(.qc-tab-title .anticon) {
  font-size: 1.1em;
}

.tab-content {
  @apply min-h-80;
}

/* 统计卡片内部样式优化 */
:deep(.ant-statistic-title) {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
}

:deep(.ant-statistic-content) {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

/* 表格相关样式 */
.rules-table-section {
  background: white;
  border-radius: 12px;
  margin: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  border: 1px solid #e2e8f0;
}

.table-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.table-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #1e293b;
}

.table-icon {
  color: #3b82f6;
}

.table-count {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
}

/* 批量操作样式 */
.batch-actions {
  margin-bottom: 16px;
}

.selection-alert {
  border-radius: 8px;
  border: 1px solid #bfdbfe;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
}

/* 快速筛选标签样式 */
.filter-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
  border: 2px solid transparent;

  /* 未选中状态 */
  background: rgba(248, 250, 252, 0.8);
  color: #64748b;
  border-color: #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.filter-tag:hover {
  background: rgba(241, 245, 249, 1);
  color: #475569;
  border-color: #cbd5e1;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 选中状态 - 主要筛选 */
.filter-tag-active {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  color: white;
  border-color: #2563eb;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
}

.filter-tag-active:hover {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
}

/* 危险类型筛选 */
.filter-tag-danger {
  background: rgba(254, 242, 242, 0.8);
  color: #dc2626;
  border-color: #fecaca;
}

.filter-tag-danger:hover {
  background: rgba(254, 226, 226, 1);
  color: #b91c1c;
  border-color: #fca5a5;
}

.filter-tag-danger-active {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
  border-color: #dc2626;
  box-shadow: 0 4px 16px rgba(239, 68, 68, 0.3);
}

.filter-tag-danger-active:hover {
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
  box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
}

/* 成功类型筛选 */
.filter-tag-success {
  background: rgba(240, 253, 244, 0.8);
  color: #16a34a;
  border-color: #bbf7d0;
}

.filter-tag-success:hover {
  background: rgba(220, 252, 231, 1);
  color: #15803d;
  border-color: #86efac;
}

.filter-tag-success-active {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: white;
  border-color: #16a34a;
  box-shadow: 0 4px 16px rgba(34, 197, 94, 0.3);
}

.filter-tag-success-active:hover {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  box-shadow: 0 6px 20px rgba(34, 197, 94, 0.4);
}

/* 筛选标签文本 */
.filter-tag-text {
  font-weight: 500;
  letter-spacing: 0.025em;
}

/* 筛选标签计数 */
.filter-tag-count {
  font-size: 11px;
  opacity: 0.8;
  font-weight: 600;
  margin-left: 2px;
}

.filter-tag-active .filter-tag-count {
  opacity: 0.9;
}

/* 按钮样式优化 */
:deep(.ant-btn) {
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.2s ease;
}

:deep(.ant-btn-primary) {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  border: none;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.2);
  color: #ffffff !important; /* 确保文字为白色 */
}

:deep(.ant-btn-primary:hover) {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
  color: #ffffff !important; /* 确保悬停时文字也为白色 */
}

:deep(.ant-btn-primary span) {
  color: #ffffff !important; /* 确保按钮内的span文字为白色 */
}

:deep(.ant-btn-primary:hover span) {
  color: #ffffff !important; /* 确保悬停时按钮内的span文字也为白色 */
}

/* 卡片样式优化 */
:deep(.ant-card) {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

:deep(.ant-card-head) {
  border-bottom: 1px solid #f1f5f9;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

/* 标签样式优化 */
:deep(.ant-tag) {
  border-radius: 6px;
  font-weight: 500;
  padding: 4px 12px;
  font-size: 12px;
  border: none;
}

/* 焦点状态（键盘导航） */
.filter-tag:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* 活跃状态增强 */
.filter-tag:active {
  transform: translateY(0);
  transition-duration: 0.1s;
}

.rule-source {
  @apply font-medium text-gray-900;
  font-size: 12px !important;  /* 从 11px 恢复到 12px，提升可读性 */
  line-height: 1.3 !important;  /* 从 1.1 增加到 1.3，提升可读性 */
  padding: 1px 0 !important;  /* 适当增加内边距 */
  margin: 0 !important;
}

.rule-name {
  @apply text-gray-700;
  font-size: 11px !important;  /* 从 10px 恢复到 11px，提升可读性 */
  line-height: 1.3 !important;  /* 从 1.1 增加到 1.3，提升可读性 */
  padding: 1px 0 !important;  /* 适当增加内边距 */
  margin: 0 !important;
  word-break: break-word !important;
}

/* 表格标题行 - 进一步压缩高度 */
:deep(.ant-table-thead > tr > th) {
  @apply bg-gray-50 font-semibold;
  font-size: 11px !important;
  padding: 4px 3px !important;  /* 从 6px 4px 进一步减少到 4px 3px */
  white-space: nowrap !important;
  font-weight: 600 !important;
  height: 28px !important;  /* 明确设置标题行高度 */
  line-height: 1.1 !important;  /* 紧凑的行高 */
}

/* 表格行优化 - 平衡紧凑性与可读性 */
:deep(.ant-table-tbody > tr > td) {
  font-size: 13px !important;
  padding: 4px 6px !important;  /* 从 2px 4px 适当增加到 4px 6px，提升可读性 */
  vertical-align: middle !important;
  line-height: 1.2 !important;  /* 从 1.1 增加到 1.2，提升文字可读性 */
}

/* 特殊调整质控点来源和名称列的单元格 */
:deep(.ant-table-tbody > tr > td:nth-child(2)),
:deep(.ant-table-tbody > tr > td:nth-child(3)) {
  padding: 3px 5px !important;  /* 从 1px 3px 适当增加到 3px 5px */
  font-size: 11px !important;
}

:deep(.ant-table-tbody > tr:hover > td) {
  @apply bg-blue-50;
}

/* 表格行高调整 - 平衡紧凑性与可读性 */
:deep(.ant-table-tbody > tr) {
  height: 30px !important;  /* 从 26px 适当增加到 30px，提升可读性 */
}

/* 表格内容垂直居中 - 平衡间距与可读性 */
:deep(.ant-table-tbody > tr > td .ant-space) {
  align-items: center !important;
  gap: 3px !important;  /* 从 1px 适当增加到 3px，提升视觉分离度 */
}

:deep(.ant-table-tbody > tr > td .ant-space-item) {
  display: flex !important;
  align-items: center !important;
}

/* 表格整体紧凑化 */
:deep(.ant-table) {
  font-size: 11px !important;  /* 从 12px 减少到 11px */
}

:deep(.ant-table-container) {
  border-radius: 4px !important;
}

/* 表格外层容器优化 */
:deep(.ant-table-wrapper) {
  margin: 0 !important;
}

/* 表格内标签优化 */
:deep(.ant-table-tbody .ant-tag) {
  font-size: 10px !important;
  height: 16px !important;  /* 从默认高度减少 */
  line-height: 14px !important;
  padding: 0 4px !important;
  margin: 0 1px !important;
}

/* 表格内开关优化 */
:deep(.ant-table-tbody .ant-switch) {
  height: 14px !important;  /* 从默认高度减少 */
  min-width: 24px !important;
  font-size: 9px !important;
}

/* 表格分页器优化 */
:deep(.ant-pagination) {
  margin-top: 8px !important;  /* 减少分页器上边距 */
  margin-bottom: 0 !important;
}

/* 表格滚动条优化 */
:deep(.ant-table-body) {
  scrollbar-width: thin;
}

/* 表格边框优化 */
:deep(.ant-table-thead > tr > th),
:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #f0f0f0 !important;
}

/* 表格行间距最小化 */
:deep(.ant-table-tbody > tr > td) {
  border-spacing: 0 !important;
}

/* 确保表格内数字垂直居中 */
:deep(.ant-table-tbody > tr > td .ant-statistic-content-value) {
  font-size: 12px !important;
  line-height: 1.1 !important;
}

/* 统计卡片标题 - 优化间距提高紧凑性 */
:deep(.ant-statistic-title) {
  @apply text-gray-700 font-bold;
  font-size: 15px !important;
  font-weight: 700 !important;
  margin-bottom: 4px !important;  /* 从 8px 减少到 4px */
}

:deep(.ant-statistic-content) {
  @apply font-bold;
  font-size: 20px !important;
}

:deep(.ant-statistic-content-value) {
  font-size: 20px !important;
}

:deep(.ant-form-item-label > label) {
  @apply font-medium text-gray-700;
  font-size: 14px !important;
}

:deep(.ant-modal-header) {
  @apply border-b border-gray-200;
}

:deep(.ant-modal-footer) {
  @apply border-t border-gray-200;
}

/* 统一按钮尺寸和字体 - 调小筛选区域按钮 */
:deep(.ant-btn) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 12px !important;
  line-height: 1.4 !important;
}

/* 表格内小按钮 - 进一步压缩 */
:deep(.ant-btn-sm) {
  font-size: 11px !important;  /* 从 12px 减少到 11px */
  height: 20px !important;     /* 从 22px 减少到 20px */
  padding: 0px 5px !important; /* 从 0px 6px 减少到 0px 5px */
  line-height: 1.1 !important;
}

/* 头部操作按钮保持稍大尺寸 */
:deep(.header-actions .ant-btn) {
  font-size: 13px !important;
  height: 30px !important;
  padding: 4px 14px !important;
}

/* LLM 设置按钮 - 大尺寸突出显示 */
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

/* 统一输入框尺寸 - 调小筛选区域输入框 */
:deep(.ant-input) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 8px !important;
}

:deep(.ant-input-search .ant-input) {
  font-size: 12px !important;
  height: 28px !important;
}

:deep(.ant-input-search .ant-input-search-button) {
  font-size: 12px !important;
  height: 28px !important;
}

/* 统一下拉菜单尺寸 - 调小筛选区域下拉菜单 */
:deep(.ant-select) {
  font-size: 12px !important;
}

:deep(.ant-select-selector) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 0 8px !important;
}

:deep(.ant-select-selection-item) {
  font-size: 12px !important;
  line-height: 26px !important;
}

:deep(.ant-select-selection-placeholder) {
  font-size: 12px !important;
  line-height: 26px !important;
}

/* 统一标签尺寸 - 调整为更小尺寸与表格内容一致 */
:deep(.ant-tag) {
  font-size: 11px !important;
  height: 18px !important;
  line-height: 16px !important;
  padding: 0 5px !important;
  margin: 0 2px 0 0 !important;
  border-radius: 2px !important;
}

/* 表格内标签特殊调整 */
:deep(.ant-table-tbody .ant-tag) {
  font-size: 11px !important;
  height: 18px !important;
  line-height: 16px !important;
  padding: 0 5px !important;
  margin: 0 2px 2px 0 !important;
  display: inline-block !important;
  vertical-align: middle !important;
}

/* 统一开关尺寸 - 调整为与标签一致的小尺寸 */
:deep(.ant-switch) {
  font-size: 10px !important;
  height: 16px !important;
  min-width: 28px !important;
  line-height: 14px !important;
}

:deep(.ant-switch-inner) {
  font-size: 10px !important;
  line-height: 14px !important;
}

:deep(.ant-switch-handle) {
  width: 12px !important;
  height: 12px !important;
  top: 2px !important;
}

:deep(.ant-switch-handle::before) {
  border-radius: 6px !important;
}

:deep(.ant-switch-checked .ant-switch-handle) {
  left: calc(100% - 12px - 2px) !important;
}

/* 统一表格操作按钮 - 调整为更小尺寸 */
:deep(.ant-btn-link) {
  font-size: 12px !important;
  height: auto !important;
  padding: 0 4px !important;
  line-height: 1.4 !important;
  min-height: 20px !important;
}

/* 表格内的按钮间距调整 */
:deep(.ant-table-tbody .ant-space-item) {
  margin-right: 4px !important;
}

:deep(.ant-table-tbody .ant-space) {
  gap: 4px !important;
}

/* 统一卡片标题 */
:deep(.ant-card-head-title) {
  font-size: 14px !important;
  font-weight: 600 !important;
}

/* 统一表单输入框 */
:deep(.ant-form-item-control-input .ant-input) {
  font-size: 14px !important;
  height: 32px !important;
}

:deep(.ant-form-item-control-input .ant-select-selector) {
  font-size: 14px !important;
  height: 32px !important;
}

:deep(.ant-form-item-control-input .ant-input-number) {
  font-size: 14px !important;
  height: 32px !important;
  width: 100% !important;
}

:deep(.ant-form-item-control-input .ant-input-number-input) {
  font-size: 14px !important;
  height: 30px !important;
}

/* 统一文本域 */
:deep(.ant-input) {
  font-size: 14px !important;
}

/* 统一分页器 */
:deep(.ant-pagination) {
  font-size: 14px !important;
}

:deep(.ant-pagination-item) {
  font-size: 14px !important;
}

:deep(.ant-pagination-item a) {
  font-size: 14px !important;
}

:deep(.ant-pagination-prev .ant-pagination-item-link),
:deep(.ant-pagination-next .ant-pagination-item-link) {
  font-size: 14px !important;
}

/* 统一下拉菜单项 */
:deep(.ant-dropdown-menu-item) {
  font-size: 14px !important;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 新增紧凑样式 */
/* 紧凑筛选标签样式 */
.filter-tag-compact {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
  border: 1px solid transparent;
  background: rgba(248, 250, 252, 0.8);
  color: #64748b;
  border-color: #e2e8f0;
}

.filter-tag-compact:hover {
  background: rgba(239, 246, 255, 1);
  color: #3b82f6;
  border-color: #93c5fd;
  transform: translateY(-1px);
}

.filter-tag-compact-active {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  border-color: #2563eb;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.filter-tag-compact.filter-tag-danger {
  background: rgba(254, 242, 242, 0.8);
  color: #dc2626;
  border-color: #fecaca;
}

.filter-tag-compact.filter-tag-danger:hover {
  background: rgba(254, 226, 226, 1);
  color: #b91c1c;
  border-color: #fca5a5;
}

.filter-tag-compact.filter-tag-danger-active {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
  border-color: #dc2626;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
}

.filter-tag-compact.filter-tag-success {
  background: rgba(240, 253, 244, 0.8);
  color: #16a34a;
  border-color: #bbf7d0;
}

.filter-tag-compact.filter-tag-success:hover {
  background: rgba(220, 252, 231, 1);
  color: #15803d;
  border-color: #86efac;
}

.filter-tag-compact.filter-tag-success-active {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: white;
  border-color: #16a34a;
  box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);
}

/* 紧凑卡片样式 */
.compact-card :deep(.ant-card-head) {
  padding: 8px 16px !important;
  min-height: auto !important;
}

.compact-card :deep(.ant-card-body) {
  padding: 12px !important;
}

/* 紧凑标签页样式 - 更紧凑 */
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

/* 表格行高进一步优化 */
:deep(.ant-table-small .ant-table-tbody > tr > td) {
  padding: 2px 4px !important;
  font-size: 12px !important;
  line-height: 1.2 !important;
}

/* 页面整体间距优化 */
.page-container {
  padding: 8px !important;
}

/* 卡片间距优化 */
.page-container > div {
  margin-bottom: 8px !important;
}

.page-container > div:last-child {
  margin-bottom: 0 !important;
}

/* 统计卡片标题优化 */
:deep(.ant-statistic-title) {
  font-size: 11px !important;
  margin-bottom: 2px !important;
}

:deep(.ant-statistic-content) {
  font-size: 14px !important;
}

:deep(.ant-table-small .ant-table-thead > tr > th) {
  padding: 4px 4px !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  height: 24px !important;
}

:deep(.ant-table-small .ant-table-tbody > tr) {
  height: 24px !important;
}

/* 紧凑分页器 */
:deep(.ant-pagination-small) {
  font-size: 12px !important;
}

:deep(.ant-pagination-small .ant-pagination-item) {
  min-width: 24px !important;
  height: 24px !important;
  line-height: 22px !important;
}
</style>
