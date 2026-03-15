<template>
  <div class="page-container min-h-screen bg-slate-50 p-4 lg:p-8 font-sans">
    <!-- 页面头部 -->
    <div class="flex flex-col sm:flex-row justify-between items-end sm:items-center mb-8">
      <div>
        <h2 class="text-2xl font-bold text-slate-800 flex items-center gap-2 tracking-tight">
          质控规则管理
          <span class="px-2 py-1 rounded text-xs font-normal bg-blue-50 text-blue-600 border border-blue-100">v2.4</span>
        </h2>
        <p class="text-slate-500 text-sm mt-1 font-medium">{{ activeTabDescription }}</p>
      </div>
      <div class="flex items-center gap-3 mt-4 sm:mt-0">
        <button
          @click="showAICreator = true"
          class="group relative inline-flex items-center justify-center px-5 py-2.5 text-sm font-medium text-white transition-all duration-200 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-full shadow-lg hover:shadow-blue-500/30 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 cursor-pointer"
        >
          <RobotOutlined class="mr-2" />
          AI 创建规则
        </button>
        <button
          @click="showLLMSettings"
          class="group relative inline-flex items-center justify-center px-5 py-2.5 text-sm font-medium text-white transition-all duration-200 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-full shadow-lg hover:shadow-indigo-500/30 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-600 cursor-pointer"
        >
          <ThunderboltOutlined class="mr-2 animate-pulse" />
          LLM 模型配置
        </button>
      </div>
    </div>

    <!-- Tab 导航 -->
    <div class="mb-8">
      <nav class="-mb-px flex space-x-8 overflow-x-auto no-scrollbar border-b border-slate-200" aria-label="Tabs">
        <a
          href="#"
          @click.prevent="handleTabClick('coding')"
          :class="[
            activeTab === 'coding'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300',
            'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center transition-colors'
          ]"
        >
          <MedicineBoxOutlined class="mr-2" />
          编码质控规则
          <span v-if="activeTab === 'coding'" class="ml-2 bg-emerald-100 text-emerald-600 py-0.5 px-2 rounded-full text-xs font-bold">18</span>
        </a>
        <a
          href="#"
          @click.prevent="handleTabClick('semantic')"
          :class="[
            activeTab === 'semantic'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300',
            'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center transition-colors'
          ]"
        >
          <BranchesOutlined class="mr-2" />
          四川省质控规则
          <span v-if="activeTab === 'semantic'" class="ml-2 bg-blue-100 text-blue-600 py-0.5 px-2 rounded-full text-xs font-bold">179</span>
        </a>
        <a
          href="#"
          @click.prevent="handleTabClick('custom')"
          :class="[
            activeTab === 'custom'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300',
            'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center transition-colors'
          ]"
        >
          <AppstoreOutlined class="mr-2" />
          泸县33条规则
        </a>
        <a
          href="#"
          @click.prevent="handleTabClick('lx_legacy')"
          :class="[
            activeTab === 'lx_legacy'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300',
            'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center transition-colors'
          ]"
        >
          <AppstoreOutlined class="mr-2" />
          泸县存量规则
        </a>
        <a
          href="#"
          @click.prevent="handleTabClick('department')"
          :class="[
            activeTab === 'department'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300',
            'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center transition-colors'
          ]"
        >
          <ApartmentOutlined class="mr-2" />
          科室规则管理
        </a>
        <a
          href="#"
          @click.prevent="handleTabClick('traditional')"
          :class="[
            activeTab === 'traditional'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300',
            'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center transition-colors'
          ]"
        >
          <SettingOutlined class="mr-2" />
          传统质控规则
        </a>
      </nav>
    </div>

    <!-- 标签页内容 -->
    <div class="tab-content">
      <!-- 传统质控规则标签页 -->
      <div v-if="activeTab === 'traditional'" class="space-y-8">
        <!-- 统计卡片 -->
        <RuleStatsCards :statistics="statistics" />

        <!-- 列表操作栏 (搜索 + 筛选) -->
        <div class="flex flex-col sm:flex-row justify-between items-center gap-4">
          <div class="relative w-full sm:w-96 group">
            <SearchOutlined class="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 text-base group-hover:text-blue-500 transition-colors" />
            <input
              v-model="searchText"
              @input="handleSearch"
              type="text"
              placeholder="搜索规则编号、名称..."
              class="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all shadow-sm placeholder-slate-400 hover:border-slate-300"
            />
          </div>
          <div class="flex gap-3 w-full sm:w-auto">
            <a-dropdown>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="import" @click="importRules">
                    <ImportOutlined /> 导入规则
                  </a-menu-item>
                  <a-menu-item key="export" @click="exportRules">
                    <ExportOutlined /> 导出规则
                  </a-menu-item>
                </a-menu>
              </template>
              <button class="flex items-center justify-center px-4 py-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg text-sm transition-all">
                <EllipsisOutlined class="mr-2" />
                更多操作
              </button>
            </a-dropdown>

            <button
              @click="showFilters = !showFilters"
              :class="[showFilters ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100']"
              class="flex items-center justify-center px-4 py-2 rounded-lg text-sm transition-all"
            >
              <FilterOutlined class="w-4 h-4 mr-2" />
              筛选
            </button>

            <button
              @click="showCreateModal"
              class="flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 hover:shadow-lg hover:shadow-blue-500/30 transition-all shadow-md shadow-blue-500/20 font-medium"
            >
              <PlusOutlined class="w-4 h-4 mr-2" />
              新增规则
            </button>
          </div>
        </div>

        <!-- 筛选区域 (Collapsible) -->
        <div v-show="showFilters" class="bg-white rounded-xl shadow-sm border border-slate-100 p-5 animate-fade-in-down">
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div>
              <a-select
                v-model:value="filterDocumentCategory"
                placeholder="文书类别"
                allowClear
                @change="handleFilter"
                class="w-full"
                :options="documentCategoryOptions"
              />
            </div>
            <div>
              <a-select
                v-model:value="filterCategory"
                placeholder="规则分类"
                allowClear
                @change="handleFilter"
                class="w-full"
              >
                <a-select-option value="completeness">完整性</a-select-option>
                <a-select-option value="consistency">一致性</a-select-option>
                <a-select-option value="rationality">合理性</a-select-option>
                <a-select-option value="timeliness">及时性</a-select-option>
              </a-select>
            </div>
            <div>
              <a-select
                v-model:value="filterSeverity"
                placeholder="严重程度"
                allowClear
                @change="handleFilter"
                class="w-full"
              >
                <a-select-option value="critical">严重</a-select-option>
                <a-select-option value="major">重要</a-select-option>
                <a-select-option value="minor">轻微</a-select-option>
              </a-select>
            </div>
            <div>
              <a-select
                v-model:value="filterStatus"
                placeholder="状态"
                allowClear
                @change="handleFilter"
                class="w-full"
              >
                <a-select-option value="active">激活</a-select-option>
                <a-select-option value="inactive">停用</a-select-option>
              </a-select>
            </div>
          </div>

          <!-- 快速筛选标签 -->
          <div class="flex flex-wrap gap-2 pt-2 border-t border-slate-50">
            <span class="text-xs font-medium text-slate-500 py-1">快速筛选：</span>
            <div
              v-for="cat in documentCategoryOptions.slice(0, 6)"
              :key="cat.value"
              @click="filterDocumentCategory === cat.value ? filterDocumentCategory = undefined : filterDocumentCategory = cat.value; handleFilter()"
              :class="[
                filterDocumentCategory === cat.value
                  ? 'bg-blue-50 text-blue-600 border-blue-200'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300',
                'cursor-pointer border px-3 py-1 rounded-lg text-xs font-medium transition-all duration-200 select-none'
              ]"
            >
              {{ cat.label }}
            </div>
          </div>
        </div>

        <!-- 批量操作区域 -->
        <div v-if="selectedRowKeys.length > 0" class="bg-blue-50 border border-blue-100 rounded-xl p-4 flex items-center justify-between animate-fade-in shadow-sm">
          <div class="flex items-center gap-3">
            <div class="bg-blue-100 p-2 rounded-lg">
                <CheckSquareOutlined class="text-blue-600 text-lg" />
            </div>
            <div>
                <span class="text-blue-900 font-bold text-base block">已选择 {{ selectedRowKeys.length }} 条规则</span>
                <span class="text-blue-600/80 text-xs">您可以对选中的规则进行批量操作</span>
            </div>
          </div>
          <div class="flex gap-3">
            <a-button size="middle" @click="batchActivate(true)" type="primary" ghost class="bg-white border-blue-200 hover:bg-blue-50">
              批量激活
            </a-button>
            <a-button size="middle" @click="batchActivate(false)" class="bg-white border-slate-200 hover:bg-slate-50">
              批量停用
            </a-button>
            <a-button size="middle" danger @click="batchDelete" class="bg-white border-red-200 hover:bg-red-50 text-red-600">
              批量删除
            </a-button>
            <a-button size="middle" type="text" @click="selectedRowKeys = []" class="text-slate-500 hover:text-slate-700">取消</a-button>
          </div>
        </div>

        <!-- 规则列表 -->
        <div class="bg-white rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 overflow-hidden">

          <a-table
            :columns="columns"
            :data-source="rules"
            :loading="loading"
            :pagination="pagination"
            :row-selection="rowSelection"
            row-key="id"
            @change="handleTableChange"
            class="ant-table-striped"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'rule_code'">
                <span class="font-mono text-blue-600 bg-blue-50 px-2 py-1 rounded text-xs font-medium border border-blue-100">
                  {{ record.rule_code }}
                </span>
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
                <div class="flex items-center justify-end gap-2">
                  <a-tooltip title="查看详情">
                    <a-button type="text" size="small" @click="viewRule(record)" class="text-slate-400 hover:text-blue-600">
                      <template #icon><EyeOutlined /></template>
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="编辑规则">
                    <a-button type="text" size="small" @click="editRule(record)" class="text-slate-400 hover:text-blue-600">
                      <template #icon><EditOutlined /></template>
                    </a-button>
                  </a-tooltip>
                  <a-popconfirm
                    title="确定要删除这条规则吗？"
                    @confirm="deleteRule(record)"
                  >
                    <a-tooltip title="删除规则">
                      <a-button type="text" size="small" danger class="text-slate-400 hover:text-red-600">
                        <template #icon><DeleteOutlined /></template>
                      </a-button>
                    </a-tooltip>
                  </a-popconfirm>
                  <a-button 
                    size="small" 
                    @click="testRule(record)" 
                    class="text-blue-600 hover:text-blue-700 font-medium text-xs border border-blue-200 hover:border-blue-300 bg-white hover:bg-blue-50 px-3 rounded-lg ml-1 flex items-center gap-1 h-7"
                  >
                    <span>评估</span>
                  </a-button>
                </div>
              </template>
            </template>
            </a-table>
        </div>
        </div>

      <!-- 编码质控规则标签页 -->
      <div v-if="activeTab === 'coding'">
        <CodingRulesTab />
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

    <!-- 规则详情抽屉 -->
    <RuleDetailDrawer
      v-model:open="detailDrawerOpen"
      :rule="detailRule"
      @edit="handleDrawerEdit"
      @test="handleDrawerTest"
    />

    <!-- 规则导入模态框 -->
    <RuleImportModal
      v-model:open="importModalOpen"
      @imported="handleImported"
    />

    <!-- 规则测试抽屉 -->
    <RuleTestDrawer
      v-model:open="testDrawerOpen"
      :rule="testRule_target"
    />

    <!-- AI 智能创建规则抽屉 -->
    <AIRuleCreatorDrawer
      v-model:visible="showAICreator"
      @saved="onAIRuleSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import {
  PlusOutlined,
  MedicineBoxOutlined,
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
  ApiOutlined,
  FilterOutlined,
  EllipsisOutlined,
  CheckSquareOutlined,
  PieChartOutlined,
  EyeOutlined,
  EditOutlined,
  PlayCircleOutlined,
  RobotOutlined
} from '@ant-design/icons-vue'
import SemanticRulesView from './SemanticRulesView.vue'
import DepartmentRulesTab from '@/components/rules/DepartmentRulesTab.vue'
import CustomRulesManager from '@/components/CustomRulesManager.vue'
import RuleDetailDrawer from '@/components/rules/RuleDetailDrawer.vue'
import RuleImportModal from '@/components/rules/RuleImportModal.vue'
import RuleTestDrawer from '@/components/rules/RuleTestDrawer.vue'
import RuleStatsCards from '@/components/rules/RuleStatsCards.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'
import AIRuleCreatorDrawer from '@/components/rules/AIRuleCreatorDrawer.vue'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'
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
const activeTab = ref('coding') // 默认显示编码质控规则
const TAB_DESCRIPTIONS: Record<string, string> = {
  coding: '编码质控规则：基于ICD编码规范的18类质控规则，覆盖4万+条编码数据。',
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

    // console.log('📄 已加载文书类别选项:', documentCategoryOptions.value.map(o => o.label).join(', '))
  } catch (error) {
    console.error('加载文书类别失败:', error)
    categoriesLoaded.value = false
    throw error // 重新抛出错误，让调用方处理
  }
}

// LLM 设置相关
const llmSettingsVisible = ref(false)

// 规则详情抽屉
const detailDrawerOpen = ref(false)
const detailRule = ref<ResolvedRule | null>(null)

// 规则导入模态框
const importModalOpen = ref(false)

// 规则测试抽屉
const testDrawerOpen = ref(false)
const testRule_target = ref<ResolvedRule | null>(null)

// AI 创建规则抽屉
const showAICreator = ref(false)
const onAIRuleSaved = () => {
  showAICreator.value = false
  // 刷新当前 Tab 的规则列表
  fetchRules()
  message.success('新规则已添加，规则列表已刷新')
}

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
    // console.warn('获取文书类别显示配置失败:', category, error)
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

    // 调试日志已移除

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
    // console.log('📊 [RulesView] 文书类别统计数据:', stats)
    // console.log('📊 [RulesView] 统计数据的键:', Object.keys(stats))
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

const viewRule = (rule: ResolvedRule) => {
  detailRule.value = rule
  detailDrawerOpen.value = true
}

const testRule = (rule: ResolvedRule) => {
  testRule_target.value = rule
  testDrawerOpen.value = true
}

const handleDrawerEdit = (rule: Record<string, any>) => {
  detailDrawerOpen.value = false
  editRule(rule as ResolvedRule)
}

const handleDrawerTest = (rule: Record<string, any>) => {
  detailDrawerOpen.value = false
  testRule(rule as ResolvedRule)
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
  importModalOpen.value = true
}

const handleImported = async () => {
  await reloadRulesSafely()
  message.success('规则已导入，列表已刷新')
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
  if (tabFromQuery && ['coding', 'traditional', 'semantic', 'custom', 'lx_legacy', 'department', 'frontpage', 'settlement'].includes(tabFromQuery)) {
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

const showFilters = ref(false)

// 监听标签页切换，更新 URL query 参数
watch(activeTab, (newTab) => {
  if (route.query.tab !== newTab) {
    router.replace({ query: { ...route.query, tab: newTab } })
  }
})

const handleTabClick = (tabKey: string) => {
  activeTab.value = tabKey
}
</script>

<style scoped>
/* Custom Tabs Styling */
.custom-tabs :deep(.ant-tabs-nav::before) {
  border-bottom: 1px solid #e2e8f0;
}

.custom-tabs :deep(.ant-tabs-tab) {
  border: 1px solid transparent !important;
  background: transparent !important;
  margin-right: 4px !important;
  border-radius: 6px 6px 0 0 !important;
  padding: 8px 16px !important;
  transition: all 0.2s ease;
  color: #64748b; /* Slate-500 */
}

.custom-tabs :deep(.ant-tabs-tab:hover) {
  color: #2563eb;
  background: #f1f5f9 !important; /* Slate-100 */
}

.custom-tabs :deep(.ant-tabs-tab-active) {
  background: #fff !important;
  color: #2563eb !important; /* Blue-600 */
  border-color: #e2e8f0 !important;
  border-bottom-color: #fff !important;
  font-weight: 600;
  position: relative;
}

.custom-tabs :deep(.ant-tabs-tab-active::after) {
  content: '';
  position: absolute;
  top: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: #2563eb;
  border-radius: 2px 2px 0 0;
}

/* Table Styles */
:deep(.ant-table-striped) .ant-table-tbody > tr:nth-child(even) {
  background-color: #f8fafc; /* Slate-50 */
}

:deep(.ant-table-thead > tr > th) {
  background: #f1f5f9 !important; /* Slate-100 (Darker header) */
  color: #1e293b !important; /* Slate-800 (Darker text) */
  font-weight: 600 !important;
  border-bottom: 1px solid #cbd5e1 !important; /* Slate-300 (Darker border) */
  padding: 16px 16px !important;
}

:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #f1f5f9 !important;
  padding: 16px 16px !important;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background: #eff6ff !important; /* Blue-50 (Theme matching hover) */
}

/* Button overrides */
:deep(.ant-btn) {
  border-radius: 6px;
}

/* Input overrides */
:deep(.ant-input),
:deep(.ant-select-selector) {
  border-radius: 6px !important;
}

/* Tag overrides */
:deep(.ant-tag) {
  border-radius: 4px;
}

/* Additional styles for compact layout */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

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

.filter-tag-compact.filter-tag-danger-active {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
  border-color: #dc2626;
}

.filter-tag-compact.filter-tag-success {
  background: rgba(240, 253, 244, 0.8);
  color: #16a34a;
  border-color: #bbf7d0;
}

.filter-tag-compact.filter-tag-success-active {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: white;
  border-color: #16a34a;
}

.rule-source, .rule-name {
  font-size: 12px;
}

/* 动画效果 */
.animate-fade-in-down {
  animation: fadeInDown 0.3s ease-out;
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
