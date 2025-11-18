<template>
  <div class="semantic-rules-manager">
    <a-card :bordered="false">
      <template #title>
        <div class="card-title">
          <MedicineBoxOutlined class="title-icon" />
          四川省住院病历语义质控规则
          <a-tag color="blue" style="margin-left: 8px">
            {{ sichuanRules.length }}条规则
          </a-tag>
        </div>
      </template>
      <template #extra>
        <a-space>
          <!-- 四川省质控系统状态 -->
          <a-tooltip title="四川省质控系统状态">
            <a-badge
              :status="sichuanQCStatus.healthy ? 'processing' : 'error'"
              :text="sichuanQCStatus.healthy ? '系统正常' : '系统异常'"
            />
          </a-tooltip>

          <a-button @click="refreshSichuanRules" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            刷新规则
          </a-button>

          <a-button type="primary" @click="showQCEvaluation = true">
            <template #icon><PlayCircleOutlined /></template>
            开始质控评估
          </a-button>
        </a-space>
      </template>

      <!-- 统计汇总行已按要求移除以获得更紧凑的布局 -->

      <!-- 四川省规则分类统计 -->
      <a-row :gutter="16" style="margin-top: 16px;">
        <a-col :span="8">
          <a-card size="small" title="复杂度分布">
            <div class="category-stats">
              <div class="stat-item">
                <span class="label">高复杂度:</span>
                <a-tag color="red">{{ sichuanStats.complexity_distribution?.高复杂度 || 28 }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">中复杂度:</span>
                <a-tag color="orange">{{ sichuanStats.complexity_distribution?.中复杂度 || 27 }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">低复杂度:</span>
                <a-tag color="green">{{ sichuanStats.complexity_distribution?.低复杂度 || 13 }}条</a-tag>
              </div>
            </div>
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card size="small" title="缺陷级别分布">
            <div class="category-stats">
              <div class="stat-item">
                <span class="label">严重缺陷:</span>
                <a-tag color="red">{{ sichuanStats.defect_level_distribution?.严重缺陷 || 8 }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">一般缺陷:</span>
                <a-tag color="orange">{{ sichuanStats.defect_level_distribution?.一般缺陷 || 12 }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">轻微缺陷:</span>
                <a-tag color="green">{{ sichuanStats.defect_level_distribution?.轻微缺陷 || 40 }}条</a-tag>
              </div>
            </div>
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card size="small" title="规则分类">
            <div class="category-stats">
              <div class="stat-item">
                <span class="label">诊断一致性:</span>
                <a-tag color="blue">{{ getCategoryCount('诊断一致性') }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">病史完整性:</span>
                <a-tag color="cyan">{{ getCategoryCount('病史完整性') }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">诊疗合理性:</span>
                <a-tag color="purple">{{ getCategoryCount('诊疗合理性') }}条</a-tag>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 规则列表（根据来源切换数据与列） -->
      <a-table
        :dataSource="sichuanRules"
        :columns="sichuanColumns"
        :loading="loading"
        :pagination="tablePagination"
        class="rules-table"
        :scroll="{ x: 1400 }"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <!-- 平台规则特有列渲染 -->
          <template v-if="currentSource === 'platform'">
            <template v-if="column.key === 'rule_id'">
              <a-tooltip :title="record.rule_code || record.rule_id">
                <a-tag color="blue">{{ getDisplayId(record) }}</a-tag>
              </a-tooltip>
            </template>
            <template v-if="column.key === 'rule_name'">
              <a-tooltip :title="record.description">
                <span class="rule-name">{{ record.rule_name }}</span>
              </a-tooltip>
            </template>
            <template v-if="column.key === 'is_enabled'">
              <a-switch
                :checked="!!record.is_enabled"
                size="small"
                checked-children="启用"
                un-checked-children="停用"
                @change="(checked: boolean) => onTogglePlatformRule(record, checked)"
              />
            </template>
            <template v-if="column.key === 'defect_level'">
              <a-tag :color="getSichuanDefectLevelColor(record.defect_level)">{{ getSeverityZh(record.defect_level) }}</a-tag>
            </template>
            <template v-if="column.key === 'applicable_documents'">
              <div class="document-types">
                <a-tag
                  v-for="docType in (record.applicable_documents || [])"
                  :key="docType"
                  size="small"
                  color="blue"
                >
                  {{ getDocTypeZh(docType) || (() => { console.warn('⚠️ 未映射的文书类型:', docType, '规则:', record.rule_id || record.rule_code); return '未知类型'; })() }}
                </a-tag>
              </div>
            </template>
            <template v-if="column.key === 'category'">
              <a-tag :color="getCategoryColor(getCategoryZh(record.category))">{{ getCategoryZh(record.category) }}</a-tag>
            </template>
          </template>

          <template v-else>
            <template v-if="column.key === 'rule_id'">
              <a-tooltip :title="record.rule_code || record.rule_id">
                <a-tag color="blue">{{ getDisplayId(record) }}</a-tag>
              </a-tooltip>
            </template>

            <template v-if="column.key === 'name'">
              <a-tooltip :title="record.description">
                <span class="rule-name">{{ record.name }}</span>
              </a-tooltip>
            </template>

            <template v-if="column.key === 'complexity'">
              <a-tag :color="getSichuanComplexityColor(record.complexity)">
                {{ record.complexity }}
              </a-tag>
            </template>

            <template v-if="column.key === 'defect_level'">
              <a-tag :color="getSichuanDefectLevelColor(record.defect_level)">
                {{ getSeverityZh(record.defect_level) }}
              </a-tag>
            </template>

            <template v-if="column.key === 'category'">
              <a-tag :color="getCategoryColor(record.category)">
                {{ getCategoryZh(record.category) }}
              </a-tag>
            </template>

            <template v-if="column.key === 'applicable_documents'">
              <div class="document-types">
                <a-tag
                  v-for="docType in record.applicable_documents"
                  :key="docType"
                  size="small"
                  color="geekblue"
                >
                  {{ getDocTypeZh(docType) || (() => { console.warn('⚠️ 未映射的文书类型:', docType, '规则:', record.rule_id || record.rule_code); return '未知类型'; })() }}
                </a-tag>
              </div>
            </template>

            <template v-if="column.key === 'actions'">
              <a-space>
                <a-button size="small" @click="viewSichuanRuleDetail(record)">
                  详情
                </a-button>
                <a-button size="small" type="primary" @click="startQCWithRule(record)">
                  质控评估
                </a-button>
              </a-space>
            </template>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 四川省规则详情模态框 -->
    <a-modal
      v-model:open="showRuleDetail"
      title="四川省住院病历质控规则详情"
      width="900px"
      :footer="null"
      centered
    >
      <div v-if="selectedRule" class="rule-detail">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="规则ID">
            <a-tag color="blue">{{ selectedRule.rule_id }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="规则名称">
            {{ selectedRule.name }}
          </a-descriptions-item>
          <a-descriptions-item label="规则分类">
            <a-tag :color="getCategoryColor(selectedRule.category)">
              {{ selectedRule.category }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="复杂度">
            <a-tag :color="getSichuanComplexityColor(selectedRule.complexity)">
              {{ selectedRule.complexity }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="缺陷级别">
            <a-tag :color="getSichuanDefectLevelColor(selectedRule.defect_level)">
              {{ selectedRule.defect_level }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="扣分">
            {{ selectedRule.score_deduction || 0 }}分
          </a-descriptions-item>
          <a-descriptions-item label="医疗领域">
            {{ selectedRule.medical_domain }}
          </a-descriptions-item>
          <a-descriptions-item label="需要RAG">
            <a-tag :color="selectedRule.requires_rag ? 'green' : 'default'">
              {{ selectedRule.requires_rag ? '是' : '否' }}
            </a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>规则描述</a-divider>
        <p>{{ selectedRule.description }}</p>

        <a-divider>适用文档类型</a-divider>
        <div class="document-types">
          <a-tag
            v-for="docType in selectedRule.applicable_documents"
            :key="docType"
            color="geekblue"
          >
            {{ getDocTypeZh(docType) || docType }}
          </a-tag>
        </div>

        <a-divider>四川省质控标准</a-divider>
        <a-alert
          message="基于《四川省住院病历质量评定标准（2023年版）》"
          description="该规则严格按照四川省卫健委发布的最新住院病历质量评定标准制定，确保质控评估的权威性和准确性。"
          type="info"
          show-icon
        />

        <!-- 提示词管理（仅系统管理员可见） -->
        <template v-if="isAdmin">
          <a-divider>
            <CodeOutlined />
            提示词管理
            <a-tag size="small" color="orange" style="margin-left: 8px;">仅管理员可见</a-tag>
          </a-divider>

          <a-spin :spinning="promptLoading">
            <div class="prompt-management">
              <!-- 操作按钮 -->
              <div class="prompt-actions">
                <a-button
                  v-if="!isEditingPrompt"
                  type="link"
                  @click="startEditPrompt"
                >
                  <CodeOutlined /> 编辑提示词
                </a-button>
                <a-space v-else>
                  <a-button type="primary" size="small" @click="savePrompt">
                    保存
                  </a-button>
                  <a-button size="small" @click="cancelEditPrompt">
                    取消
                  </a-button>
                  <a-button
                    size="small"
                    danger
                    @click="resetToDefault"
                  >
                    恢复默认
                  </a-button>
                </a-space>
              </div>

              <!-- 提示词显示/编辑区域 -->
              <div v-if="!isEditingPrompt" class="prompt-display">
                <pre>{{ currentPrompt }}</pre>
              </div>
              <a-textarea
                v-else
                v-model:value="editingPrompt"
                :rows="15"
                placeholder="请输入自定义提示词..."
                class="prompt-editor"
              />

              <!-- 提示信息 -->
              <a-alert
                v-if="isEditingPrompt"
                message="提示"
                description="提示词中可以使用以下变量：{rule_id}, {name}, {description}, {applicable_documents}, {defect_level}, {complexity}, {medical_text}"
                type="info"
                show-icon
                style="margin-top: 12px;"
              />
            </div>
          </a-spin>
        </template>
      </div>
    </a-modal>

    <!-- 质控评估模态框 -->
    <a-modal
      v-model:open="showQCEvaluation"
      title="四川省住院病历质控评估"
      width="600px"
      :footer="null"
      centered
    >
      <a-alert
        message="质控评估功能"
        description="请前往质控评估页面进行完整的四川省住院病历质控评估"
        type="info"
        show-icon
        style="margin-bottom: 16px"
      />
      <div style="text-align: center;">
        <a-button type="primary" size="large" @click="showQCEvaluation = false">
          前往质控评估页面
        </a-button>
      </div>
    </a-modal>

    <!-- 系统统计模态框 -->
    <a-modal
      v-model:open="showSystemStats"
      title="四川省质控系统统计"
      width="600px"
      :footer="null"
      centered
    >
      <a-alert
        message="系统统计信息"
        description="请前往统计页面查看详细的四川省质控系统运行统计"
        type="info"
        show-icon
        style="margin-bottom: 16px"
      />
      <div style="text-align: center;">
        <a-button type="primary" size="large" @click="showSystemStats = false">
          前往统计页面
        </a-button>
      </div>
    </a-modal>

    <!-- 规则测试对话框 -->
    <a-modal
      v-model:open="showRuleTest"
      :title="`质控规则测试 · ${testingRule?.rule_id || ''}`"
      width="900px"
      :footer="null"
      centered
      :destroyOnClose="true"
      class="rule-test-modal"
    >
      <div v-if="testingRule" class="rule-test-container">
        <!-- 规则信息展示区 -->
        <div class="rule-info-card">
          <div class="card-header">
            <h3 class="card-title">规则信息</h3>
          </div>
          <div class="card-body">
            <a-row :gutter="[16, 12]">
              <a-col :span="12">
                <div class="info-item">
                  <span class="info-label">规则名称</span>
                  <span class="info-value">{{ testingRule.name }}</span>
                </div>
              </a-col>
              <a-col :span="6">
                <div class="info-item">
                  <span class="info-label">缺陷级别</span>
                  <span :class="['status-pill', `status-pill--${getDefectTone(testingRule.defect_level)}`]">
                    <component
                      :is="statusToneIcons[getDefectTone(testingRule.defect_level)]"
                      class="status-pill__icon"
                    />
                    <span class="status-pill__text">{{ testingRule.defect_level }}</span>
                  </span>
                </div>
              </a-col>
              <a-col :span="6">
                <div class="info-item">
                  <span class="info-label">复杂度</span>
                  <span :class="['status-pill', `status-pill--${getComplexityTone(testingRule.complexity)}`]">
                    <component
                      :is="statusToneIcons[getComplexityTone(testingRule.complexity)]"
                      class="status-pill__icon"
                    />
                    <span class="status-pill__text">{{ testingRule.complexity }}</span>
                  </span>
                </div>
              </a-col>
              <a-col :span="24">
                <div class="info-item">
                  <span class="info-label">适用文书</span>
                  <a-space :size="4" wrap>
                    <a-tag v-for="doc in testingRule.applicable_documents" :key="doc" class="doc-tag">
                      {{ getDocTypeZh(doc) || doc }}
                    </a-tag>
                  </a-space>
                </div>
              </a-col>
              <a-col :span="24">
                <div class="info-item">
                  <span class="info-label">规则描述</span>
                  <p class="info-description">{{ testingRule.description }}</p>
                </div>
              </a-col>
            </a-row>
          </div>
        </div>

        <!-- 病历输入区 -->
        <div class="medical-text-card">
          <div class="card-header">
            <h3 class="card-title">病历文本</h3>
            <a-radio-group
              v-model:value="testExampleType"
              button-style="solid"
              size="small"
              @change="switchExampleType(testExampleType)"
              class="example-type-selector"
            >
              <a-radio-button value="negative" class="negative-btn">
                <CloseCircleOutlined class="radio-icon" />
                <span>反例</span>
              </a-radio-button>
              <a-radio-button value="positive" class="positive-btn">
                <CheckCircleOutlined class="radio-icon" />
                <span>正例</span>
              </a-radio-button>
            </a-radio-group>
          </div>
          <div class="card-body">
            <a-alert
              :message="testExampleType === 'negative' ? '当前示例：不符合规则要求的病历（用于测试规则识别能力）' : '当前示例：符合规则要求的病历（用于测试误报率）'"
              :type="testExampleType === 'negative' ? 'warning' : 'success'"
              show-icon
              :banner="true"
              style="margin-bottom: 12px; border-radius: 8px;"
            />

            <!-- 示例说明折叠面板 -->
            <a-collapse
              v-if="currentCaseExample && (currentHints.length > 0 || currentFocusPoints.length > 0)"
              v-model:activeKey="showExampleInfo"
              class="example-info-collapse"
              style="margin-bottom: 12px;"
            >
              <a-collapse-panel key="1" class="example-info-panel">
                <template #header>
                  <div class="panel-header">
                    <InfoCircleOutlined style="margin-right: 8px;" />
                    <span class="panel-title">示例说明</span>
                    <span class="panel-subtitle">（仅供参考，不会提交给 LLM）</span>
                  </div>
                </template>

                <div class="example-info-content">
                  <!-- 示例标题和摘要 -->
                  <div class="info-section info-section--primary">
                    <div class="section-title">
                      <FileTextOutlined class="section-title__icon" />
                      <span>{{ currentCaseExample.title }}</span>
                    </div>
                    <div class="section-content">{{ currentCaseExample.summary }}</div>
                  </div>

                  <!-- 质控分析（合并质控缺陷和详细分析） -->
                  <div v-if="currentFocusPoints.length > 0 || currentHints.length > 0" class="info-section info-section--analysis">
                    <div class="section-title">
                      <SearchOutlined v-if="testExampleType === 'negative'" class="section-title__icon" />
                      <HighlightOutlined v-else class="section-title__icon" />
                      <span>质控分析</span>
                    </div>
                    <div class="section-content">
                      <!-- 核心缺陷/关注点（简短结论） -->
                      <div v-if="currentFocusPoints.length > 0" class="analysis-summary">
                        <div class="analysis-summary__title">
                          {{ testExampleType === 'negative' ? '❌ 核心缺陷' : '✅ 质控要点' }}
                        </div>
                        <div
                          v-for="(point, index) in currentFocusPoints"
                          :key="index"
                          class="focus-point-item"
                        >
                          <span class="point-index">{{ index + 1 }}.</span>
                          <span class="point-text">{{ point }}</span>
                        </div>
                      </div>

                      <!-- 详细分析（可展开/折叠） -->
                      <div v-if="currentHints.length > 0" class="analysis-details">
                        <a-collapse v-model:activeKey="showDetailedAnalysis" ghost>
                          <a-collapse-panel key="1">
                            <template #header>
                              <div class="analysis-details__header">
                                <FundOutlined class="analysis-details__icon" />
                                <span>详细分析</span>
                                <a-tag size="small" color="blue" style="margin-left: 8px;">展开查看</a-tag>
                              </div>
                            </template>
                            <div class="analysis-details__content">
                              <div
                                v-for="(hint, index) in currentHints"
                                :key="index"
                                class="analysis-detail-item"
                              >
                                {{ hint }}
                              </div>
                            </div>
                          </a-collapse-panel>
                        </a-collapse>
                      </div>
                    </div>
                  </div>
                </div>
              </a-collapse-panel>
            </a-collapse>

            <a-textarea
              v-model:value="testMedicalText"
              placeholder="请输入或粘贴病历文本片段（500-2000字）"
              :rows="10"
              :maxlength="2000"
              showCount
              class="medical-textarea"
            />
            <div class="action-bar">
              <span class="hint-text">
                <BulbOutlined class="hint-icon" />
                提示：可以修改示例文本或输入自己的病历
              </span>
              <a-button type="primary" :loading="testLoading" @click="executeRuleTest" class="test-btn">
                <template #icon><ThunderboltOutlined /></template>
                开始测试
              </a-button>
            </div>
          </div>
        </div>

        <!-- 结果展示区 -->
        <div v-if="testResult" class="result-card">
          <div class="card-header">
            <h3 class="card-title">测试结果</h3>
          </div>
          <div class="card-body">
            <div class="result-status" :class="testResult.is_compliant ? 'result-status--success' : 'result-status--warning'">
              <div class="status-icon">
                <CheckCircleTwoTone
                  v-if="testResult.is_compliant"
                  two-tone-color="#52C41A"
                  class="status-icon__graphic"
                />
                <ExclamationCircleTwoTone
                  v-else
                  two-tone-color="#FAAD14"
                  class="status-icon__graphic"
                />
              </div>
              <div class="status-text">
                <h4>{{ testResult.is_compliant ? '符合规则要求' : '不符合规则要求' }}</h4>
                <a-progress
                  class="result-progress"
                  :percent="Math.round(testResult.confidence * 100)"
                  :stroke-color="testResult.is_compliant ? '#52C41A' : '#FAAD14'"
                  :show-info="false"
                />
                <p class="confidence-text">
                  置信度 {{ (testResult.confidence * 100).toFixed(1) }}%
                </p>
              </div>
            </div>

            <div class="result-details">
              <div class="detail-item">
                <div class="detail-label">发现的问题</div>
                <div class="detail-content">{{ testResult.findings }}</div>
              </div>

              <div class="detail-item">
                <div class="detail-label">证据引用</div>
                <div class="detail-content evidence-box">{{ testResult.evidence }}</div>
              </div>

              <div v-if="testResult.suggestion" class="detail-item">
                <div class="detail-label">改进建议</div>
                <div class="detail-content suggestion-box">{{ testResult.suggestion }}</div>
              </div>
            </div>

            <div class="result-actions">
              <a-space :size="8">
                <a-button @click="testResult = null" class="secondary-btn">清除结果</a-button>
                <a-button type="primary" @click="executeRuleTest" :loading="testLoading" class="primary-btn">
                  重新测试
                </a-button>
              </a-space>
            </div>
          </div>
        </div>
      </div>
    </a-modal>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  InfoCircleOutlined,
  CloseCircleOutlined,
  HighlightOutlined,
  SearchOutlined,
  ExclamationCircleFilled,
  CheckCircleFilled,
  CloseCircleFilled,
  InfoCircleFilled,
  CheckCircleTwoTone,
  ExclamationCircleTwoTone,
  FundOutlined,
  CodeOutlined,
  MedicineBoxOutlined,
  BulbOutlined
} from '@ant-design/icons-vue'
import {
  qcRuleCaseMap,
  buildCaseText,
  extractHints,
  extractFocusPoints,
  type QCRuleCaseExample
} from '@/data/qcRuleCases'
import { ApiService } from '@/services/apiService'
import type { User } from '@/types/auth'
import { UserRole } from '@/types/auth'

type StatusTone = 'success' | 'warning' | 'error' | 'info'

const statusToneIcons: Record<StatusTone, any> = {
  success: CheckCircleFilled,
  warning: ExclamationCircleFilled,
  error: CloseCircleFilled,
  info: InfoCircleFilled
}

const getDefectTone = (level: string): StatusTone => {
  const normalized = String(level || '').trim()
  const map: Record<string, StatusTone> = {
    '严重缺陷': 'error',
    '一般缺陷': 'warning',
    '轻微缺陷': 'success',
    '提示缺陷': 'info'
  }
  return map[normalized] ?? 'warning'
}

const getComplexityTone = (complexity: string): StatusTone => {
  const normalized = String(complexity || '').trim()
  const map: Record<string, StatusTone> = {
    '高复杂度': 'error',
    '中复杂度': 'warning',
    '一般复杂度': 'info',
    '低复杂度': 'success'
  }
  return map[normalized] ?? 'info'
}

// 四川省规则接口定义
interface SichuanQCRule {
  rule_id: string
  name: string
  description: string
  category: string
  complexity: string
  defect_level: string
  score_deduction: number
  applicable_documents: string[]
  medical_domain: string
  requires_rag: boolean
  requires_cot: boolean
}

interface SichuanQCStats {
  total_rules: number
  rule_categories: string[]
  complexity_distribution: Record<string, number>
  defect_level_distribution: Record<string, number>
}

interface SichuanQCStatus {
  healthy: boolean
  api_endpoint: string
}

interface TableColumn {
  title: string
  dataIndex?: string
  key: string
  width?: number
  fixed?: string
  ellipsis?: boolean
  // antd-vue 列筛选可选属性（为简化类型，这里使用 any）
  filters?: unknown[]
  onFilter?: (value: unknown, record: unknown) => boolean
  filteredValue?: unknown[] | null
}

// 用户相关
const currentUser = ref<User | null>(null)
const isAdmin = computed(() => {
  return currentUser.value?.roles?.includes(UserRole.ADMIN) || false
})

// 提示词管理相关
const currentPrompt = ref<string>('')
const isEditingPrompt = ref<boolean>(false)
const editingPrompt = ref<string>('')
const promptLoading = ref<boolean>(false)

// 四川省规则相关数据
const loading = ref(false)
const currentSource = ref<'platform' | 'sichuan'>('sichuan')
const sichuanRules = ref<SichuanQCRule[]>([])
const sichuanStats = ref<SichuanQCStats>({
  total_rules: 68,
  rule_categories: [],
  complexity_distribution: {},
  defect_level_distribution: {}
})
const sichuanQCStatus = ref<SichuanQCStatus>({
  healthy: true,
  api_endpoint: 'http://localhost:8001'
})

// 兼容原有数据结构
const rules = ref<SichuanQCRule[]>([])

// 平台规则数据模型
interface PlatformRule {
  rule_id: string
  rule_name: string
  description?: string
  category?: string
  defect_level?: string
  applicable_documents?: string[]
  is_enabled?: boolean
  version?: number | string
  updated_at?: string
}

const tablePagination = ref({ current: 1, total: 0, pageSize: 20, showSizeChanger: true, showQuickJumper: true, pageSizeOptions: ['20', '50', '100'], showTotal: (total: number, range: [number, number]) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条` })

// 规则详情
const showRuleDetail = ref(false)
const selectedRule = ref<SichuanQCRule | null>(null)

// 质控评估和系统统计
const showQCEvaluation = ref(false)
const showSystemStats = ref(false)

// 规则测试对话框
const showRuleTest = ref(false)
const testingRule = ref<SichuanQCRule | null>(null)
const testMedicalText = ref('')
const testLoading = ref(false)
const testExampleType = ref<'positive' | 'negative'>('negative') // 默认显示反例（不符合规则）
const testResult = ref<{
  rule_id: string
  rule_name: string
  is_compliant: boolean
  findings: string
  evidence: string
  suggestion: string
  confidence: number
  llm_raw_output?: string
} | null>(null)

const currentCaseExample = computed<QCRuleCaseExample | null>(() => {
  if (!testingRule.value) return null
  const ruleCase = qcRuleCaseMap[testingRule.value.rule_id]
  if (!ruleCase) return null
  return testExampleType.value === 'positive' ? ruleCase.positive : ruleCase.negative
})

// 当前示例的提示信息
const currentHints = computed<string[]>(() => {
  if (!currentCaseExample.value) return []
  return extractHints(currentCaseExample.value)
})

// 当前示例的质控关注点
const currentFocusPoints = computed<string[]>(() => {
  if (!currentCaseExample.value) return []
  return extractFocusPoints(currentCaseExample.value)
})

// 是否显示示例说明面板（Collapse activeKey 需要数组）
const showExampleInfo = ref<string[]>(['1']) // 默认展开，包含 key='1' 的面板

// 是否展开详细分析（默认折叠，用户可展开查看）
const showDetailedAnalysis = ref<string[]>([])

// 文书类别映射：标准化中英文映射
const CANONICAL_LABEL_ZH: Record<string, string> = {
  admission_record: '入院记录',
  progress_note: '病程记录',
  discharge_record: '出院记录',
  operation_record: '手术相关记录',
  examination_report: '辅助检查',
  consent_form: '知情同意书'
}
const ALIAS_TO_CANONICAL: Record<string, string> = {
  '手术记录': 'operation_record',
  '检查记录': 'examination_report',
  '检验检查': 'examination_report',
  '输血记录': 'progress_note',
  '治疗记录': 'progress_note',
  '医嘱记录': 'progress_note',
  'medical_order': 'progress_note',
  'medication_record': 'progress_note',
  // 兼容更多文书别名
  '出院医嘱': 'progress_note',
  '输血同意书': 'consent_form',
  // '急诊记录'不保留，直接剔除
}
const mapDocTypeToCanonical = (raw: string | undefined | null): string | null => {
  const s = String(raw || '').trim()
  if (!s) return null
  // 已是标准 code
  if (s in CANONICAL_LABEL_ZH) return s
  // 中文别名
  if (s in ALIAS_TO_CANONICAL) return ALIAS_TO_CANONICAL[s]
  // 其他英文别名（兼容部分来源）
  const key = s.toLowerCase()
  if (key === 'emergency') return null // 去掉急诊
  if (key === 'operation' || key === 'operation_record') return 'operation_record'
  if (key === 'examination' || key === 'examination_report') return 'examination_report'
  if (key === 'admission' || key === 'admission_record') return 'admission_record'
  if (key === 'progress' || key === 'progress_note') return 'progress_note'
  if (key === 'discharge' || key === 'discharge_record') return 'discharge_record'
  if (key === 'consent' || key === 'consent_form') return 'consent_form'
  return null
}
const getDocTypeZh = (value: string | undefined | null) => {
  const code = mapDocTypeToCanonical(value)
  return code ? CANONICAL_LABEL_ZH[code] : ''
}

// 四川省规则表格列定义
// 表头筛选选中项（受控）
const headerSelected = ref<Record<string, any[] | null>>({})

// 动态列（四川）
const sichuanColumns = computed<TableColumn[]>(() => [
  {
    title: () => h('span', { class: 'th-enlarge' }, '序号'),
    key: 'index',
    width: 70,
    fixed: 'left',
    customRender: ({ index }: { index: number }) => {
      const page = tablePagination.value.current || 1
      const pageSize = tablePagination.value.pageSize || 20
      return (page - 1) * pageSize + index + 1
    }
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '编号'),
    dataIndex: 'rule_id',
    key: 'rule_id',
    width: 100,
    fixed: 'left'
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '规则名称'),
    dataIndex: 'name',
    key: 'name',
    width: 200,
    ellipsis: true
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '分类'),
    key: 'category',
    dataIndex: 'category',
    width: 60,
    filters: Array.from(new Set(sichuanRules.value.map(r => r.category).filter(Boolean))).map(c => ({ text: c, value: c })),
    filteredValue: headerSelected.value.category ?? null,
    onFilter: (value, record) => String(record.category) === String(value)
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '复杂度'),
    dataIndex: 'complexity',
    key: 'complexity',
    width: 60,
    filters: Array.from(new Set(sichuanRules.value.map(r => r.complexity).filter(Boolean))).map(s => ({ text: s, value: s })),
    filteredValue: headerSelected.value.complexity ?? null,
    onFilter: (value, record) => String(record.complexity) === String(value)
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '缺陷级别'),
    dataIndex: 'defect_level',
    key: 'defect_level',
    width: 60,
    filters: Array.from(new Set(sichuanRules.value.map(r => r.defect_level).filter(Boolean))).map(s => ({ text: s, value: s })),
    filteredValue: headerSelected.value.defect_level ?? null,
    onFilter: (value, record) => String(record.defect_level) === String(value)
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '文书类别'),
    key: 'applicable_documents',
    dataIndex: 'applicable_documents',
    width: 60,
    ellipsis: true,
    customRender: ({ text }: { text: any }) => {
      console.log('🎯 [四川] customRender 被调用!', 'text=', text, 'type=', typeof text, 'isArray=', Array.isArray(text))
      const docs = Array.isArray(text) ? text : []
      const codes = docs.map((d: any) => mapDocTypeToCanonical(d)).filter((code: any) => !!code)
      const zhLabels = codes.map((code: string) => CANONICAL_LABEL_ZH[code]).filter((label: any) => !!label)
      const result = zhLabels.join(', ') || '-'
      console.log('🎯 [四川] customRender 返回:', result)
      return result
    },
    filters: Array.from(new Set(
      (sichuanRules.value || [])
        .flatMap(r => r.applicable_documents || [])
        .map(mapDocTypeToCanonical)
        .filter((x: unknown) => !!x)
    ) as Set<string>).map((code: unknown) => ({ text: CANONICAL_LABEL_ZH[String(code)], value: String(code) })),
    filteredValue: headerSelected.value.applicable_documents ?? null,
    onFilter: (value, record) => {
      const mapped = (record.applicable_documents || []).map((d: unknown) => mapDocTypeToCanonical(d)).filter((x: unknown) => !!x)
      return mapped.includes(String(value))
    }
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '医疗领域'),
    dataIndex: 'medical_domain',
    key: 'medical_domain',
    width: 60
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '操作'),
    key: 'actions',
    width: 180,
    fixed: 'right'
  }
])

// 平台规则列
const platformColumns = computed<TableColumn[]>(() => {
  const categoryFilters = Array.from(new Set(platformRules.value.map(r => r.category).filter(Boolean) as string[]))
    .map(c => ({ text: getCategoryZh(c), value: c }))
  const defectFilters = Array.from(new Set(platformRules.value.map(r => String(r.defect_level || '')).filter(Boolean)))
    .map(d => ({ text: getSeverityZh(d), value: d }))
  const docFilters = Array.from(new Set((platformRules.value || []).flatMap(r => r.applicable_documents || []).filter(Boolean)))
    .map(d => ({ text: getDocTypeZh(d), value: d }))

  // Debug: show where non-standard labels may come from (platform)
  try {
    const rawPlatformDocs = Array.from(new Set((platformRules.value || [])
      .flatMap(r => r.applicable_documents || [])
      .filter(Boolean)))
    const canonicalPlatformDocs = Array.from(new Set(rawPlatformDocs
      .map(mapDocTypeToCanonical)
      .filter((x: unknown) => !!x)))
    console.log('🧪 平台规则 applicable_documents 原始值 count=', rawPlatformDocs.length, rawPlatformDocs)
    console.log('✅ 平台规则 文书类别过滤项(标准6类)=', canonicalPlatformDocs.map((code: unknown) => ({ code, label: CANONICAL_LABEL_ZH[String(code)] })))
  } catch {}

  return [
    {
      title: () => h('span', { class: 'th-enlarge' }, '序号'),
      key: 'index',
      width: 70,
      fixed: 'left',
      customRender: ({ index }: { index: number }) => {
        const page = tablePagination.value.current || 1
        const pageSize = tablePagination.value.pageSize || 20
        return (page - 1) * pageSize + index + 1
      }
    },
    { title: () => h('span', { class: 'th-enlarge' }, '编号'), key: 'rule_id', dataIndex: 'rule_id', width: 120, fixed: 'left' },
    { title: () => h('span', { class: 'th-enlarge' }, '名称'), key: 'rule_name', dataIndex: 'rule_name', width: 220, ellipsis: true },
    {
      title: () => h('span', { class: 'th-enlarge' }, '分类'),
      key: 'category',
      dataIndex: 'category',
      width: 60,
      filters: categoryFilters,
      filteredValue: headerSelected.value.category ?? null,
      onFilter: (value, record) => String(record.category) === String(value)
    },
    {
      title: () => h('span', { class: 'th-enlarge' }, '缺陷级别'),
      key: 'defect_level',
      dataIndex: 'defect_level',
      width: 60,
      filters: defectFilters,
      filteredValue: headerSelected.value.defect_level ?? null,
      onFilter: (value, record) => String(record.defect_level) === String(value)
    },
    {
      title: () => h('span', { class: 'th-enlarge' }, '文书类别'),
      key: 'applicable_documents',
      dataIndex: 'applicable_documents',
      width: 60,
      customRender: ({ text }: { text: any }) => {
        console.log('🎯 [平台] customRender 被调用!', 'text=', text, 'type=', typeof text, 'isArray=', Array.isArray(text))
        const docs = Array.isArray(text) ? text : []
        const codes = docs.map((d: any) => mapDocTypeToCanonical(d)).filter((code: any) => !!code)
        const zhLabels = codes.map((code: string) => CANONICAL_LABEL_ZH[code]).filter((label: any) => !!label)
        const result = zhLabels.join(', ') || '-'
        console.log('🎯 [平台] customRender 返回:', result)
        return result
      },
      filters: Array.from(new Set((platformRules.value || [])
        .flatMap(r => r.applicable_documents || [])
        .map(mapDocTypeToCanonical)
        .filter((x: unknown) => !!x)
      ) as Set<string>).map((code: unknown) => ({ text: CANONICAL_LABEL_ZH[String(code)], value: String(code) })),
      filteredValue: headerSelected.value.applicable_documents ?? null,
      onFilter: (value, record) => {
        const mapped = (record.applicable_documents || []).map((d: unknown) => mapDocTypeToCanonical(d)).filter((x: unknown) => !!x)
        return mapped.includes(String(value))
      }
    },
    {
      title: () => h('span', { class: 'th-enlarge' }, '启用'),
      key: 'is_enabled',
      dataIndex: 'is_enabled',
      width: 100,
      filters: [
        { text: '启用', value: true },
        { text: '停用', value: false },
      ],
      filteredValue: headerSelected.value.is_enabled ?? null,
      onFilter: (value, record) => Boolean(record.is_enabled) === Boolean(value)
    },
    { title: '版本', key: 'version', dataIndex: 'version', width: 80 },
    { title: '更新时间', key: 'updated_at', dataIndex: 'updated_at', width: 180 },
  ]
})

// 用户相关方法
const fetchCurrentUser = async () => {
  try {
    const result = await ApiService.getCurrentUser()
    if (result.success && result.data) {
      currentUser.value = result.data
      console.log('✅ 当前用户信息:', {
        email: result.data.email,
        roles: result.data.roles,
        isAdmin: result.data.roles?.includes(UserRole.ADMIN)
      })
    } else {
      console.warn('⚠️ 获取用户信息失败或无数据')
    }
  } catch (error) {
    console.error('❌ 获取用户信息失败:', error)
  }
}

// 提示词管理方法
const fetchRulePrompt = async (ruleId: string) => {
  console.log('🔍 准备获取提示词:', {
    ruleId,
    isAdmin: isAdmin.value,
    currentUser: currentUser.value?.email,
    roles: currentUser.value?.roles
  })

  if (!isAdmin.value) {
    console.warn('⚠️ 非管理员用户，跳过获取提示词')
    return
  }

  try {
    promptLoading.value = true
    const token = localStorage.getItem('medqc_access_token')
    console.log('🔑 Token信息:', {
      hasToken: !!token,
      tokenLength: token?.length,
      tokenPrefix: token?.substring(0, 20) + '...'
    })

    const response = await fetch(`/api/v1/qc/sichuan/rules/${ruleId}/prompt`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    console.log('📡 API响应:', {
      status: response.status,
      ok: response.ok
    })

    if (response.ok) {
      const data = await response.json()
      currentPrompt.value = data.data?.prompt || ''
      console.log('✅ 成功获取提示词，长度:', currentPrompt.value.length)
    } else {
      const errorData = await response.json().catch(() => ({}))
      console.error('❌ 获取提示词失败:', response.status, errorData)
      message.error(errorData.error || errorData.message || '获取提示词失败')
    }
  } catch (error) {
    console.error('❌ 获取提示词异常:', error)
    message.error('获取提示词失败')
  } finally {
    promptLoading.value = false
  }
}

const startEditPrompt = () => {
  editingPrompt.value = currentPrompt.value
  isEditingPrompt.value = true
}

const cancelEditPrompt = () => {
  isEditingPrompt.value = false
  editingPrompt.value = ''
}

const savePrompt = async () => {
  if (!selectedRule.value) return

  try {
    promptLoading.value = true
    const response = await fetch(
      `/api/v1/qc/sichuan/rules/${selectedRule.value.rule_id}/prompt`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('medqc_access_token')}`
        },
        body: JSON.stringify({
          custom_prompt: editingPrompt.value
        })
      }
    )

    if (response.ok) {
      currentPrompt.value = editingPrompt.value
      isEditingPrompt.value = false
      message.success('提示词保存成功')
    } else {
      const error = await response.json()
      message.error(error.message || '保存失败')
    }
  } catch (error) {
    console.error('保存提示词失败:', error)
    message.error('保存提示词失败')
  } finally {
    promptLoading.value = false
  }
}

const resetToDefault = async () => {
  if (!selectedRule.value) return

  try {
    promptLoading.value = true
    const response = await fetch(
      `/api/v1/qc/sichuan/rules/${selectedRule.value.rule_id}/prompt`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('medqc_access_token')}`
        },
        body: JSON.stringify({
          custom_prompt: null
        })
      }
    )

    if (response.ok) {
      await fetchRulePrompt(selectedRule.value.rule_id)
      isEditingPrompt.value = false
      message.success('已恢复为默认提示词')
    } else {
      const error = await response.json()
      message.error(error.message || '恢复失败')
    }
  } catch (error) {
    console.error('恢复默认提示词失败:', error)
    message.error('恢复失败')
  } finally {
    promptLoading.value = false
  }
}

// 四川省规则相关方法
const refreshSichuanRules = async () => {
  loading.value = true
  try {
    console.log('🔄 开始加载四川省质控规则...')

    const response = await fetch(`/api/v1/qc/sichuan/rules?_ts=${Date.now()}` , { cache: 'no-store' })
    console.log('📡 调用API:', '/api/v1/qc/sichuan/rules')
    if (response.ok) {
      const data = await response.json()
      // 后端返回的字段可能为英文或缺失，这里做一次规范化
      const normalizeRule = (r: unknown): SichuanQCRule => {
        return {
          rule_id: r.rule_id || r.id || '',
          name: r.name || r.rule_name || '未命名规则',
          description: r.description || r.desc || '',
          category: r.category || r.rule_category || '基础',
          complexity: r.complexity || r.rule_complexity || '中复杂度',
          defect_level: r.defect_level || r.severity || '一般缺陷',
          score_deduction: r.score_deduction ?? r.deduction_score ?? 0,
          applicable_documents: r.applicable_documents || r.document_types || [],
          medical_domain: r.medical_domain || r.domain || '通用',
          requires_rag: Boolean(r.requires_rag ?? r.need_rag ?? false),
          requires_cot: Boolean(r.requires_cot ?? r.need_cot ?? false)
        }
      }

      const rawRules = data.rules || []
      sichuanRules.value = rawRules.map((r: unknown) => normalizeRule(r))
      sichuanStats.value = {
        total_rules: data.total_rules || 68,
        rule_categories: data.rule_categories || [],
        complexity_distribution: data.complexity_distribution || {},
        defect_level_distribution: data.defect_level_distribution || {}
      }

      // 更新分页总数
      tablePagination.value = {
        ...tablePagination.value,
        total: sichuanRules.value.length,
      }

      // 同步到兼容数据结构
      rules.value = sichuanRules.value

      console.log('✅ 四川省规则加载成功:', sichuanRules.value.length, '条规则')
      message.success(`成功加载 ${sichuanRules.value.length} 条四川省质控规则`)
    } else {
      const error = await response.text()
      console.error('❌ 四川省规则加载失败:', error)
      message.error('加载四川省规则失败: ' + error)
    }
  } catch (error: unknown) {
    console.error('❌ 四川省规则加载异常:', error)
    message.error('加载四川省规则异常: ' + (error instanceof Error ? error.message : '未知错误'))
  } finally {
    loading.value = false
  }
}

// 平台规则：加载与筛选
const refreshPlatformRules = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (filters.value.q) params.set('q', String(filters.value.q))
    if (filters.value.category) params.set('category', String(filters.value.category))
    if (filters.value.defect_level) params.set('defect_level', String(filters.value.defect_level))
    if (filters.value.is_enabled !== null && filters.value.is_enabled !== undefined) params.set('is_enabled', String(filters.value.is_enabled))
    params.set('page', String(tablePagination.value.current || 1))
    params.set('page_size', String(tablePagination.value.pageSize || 20))

    const resp = await fetch(`/api/v1/semantic-rules?${params.toString()}`)
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    platformRules.value = (data.rules || [])
    tablePagination.value = {
      ...tablePagination.value,
      total: Number(data.count || 0),
    }
    // 简单推断分类列表
    platformCategories.value = Array.from(new Set(platformRules.value.map(r => r.category).filter(Boolean) as string[]))
  } catch (e: unknown) {
    message.error('加载平台规则失败: ' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

// 本地受控筛选：结合分页事件获取 filters
const handleTableChange = (pagination: unknown, tableFilters?: Record<string, any[]>) => {
  tablePagination.value = {
    ...tablePagination.value,
    current: pagination?.current || 1,
    pageSize: pagination?.pageSize || tablePagination.value.pageSize,
  }
  if (tableFilters) {
    headerSelected.value = {
      ...headerSelected.value,
      ...tableFilters,
    }
  }
  // 平台规则仍走远端查询（顶部筛选），表头筛选用于前端快速筛选当前页
  if (currentSource.value === 'platform') {
    refreshPlatformRules()
  }
}

// 四川省规则详情查看
const viewSichuanRuleDetail = (rule: SichuanQCRule) => {
  selectedRule.value = rule
  showRuleDetail.value = true
  // 如果是管理员，获取提示词
  if (isAdmin.value) {
    fetchRulePrompt(rule.rule_id)
  }
}

// 开始质控评估（改为打开测试对话框）
const startQCWithRule = (rule: SichuanQCRule) => {
  testingRule.value = rule
  testResult.value = null
  testExampleType.value = 'negative' // 默认显示反例
  // 预置示例病历文本
  testMedicalText.value = getExampleMedicalText(rule, testExampleType.value)
  showRuleTest.value = true
}

// 切换示例类型
const switchExampleType = (type: 'positive' | 'negative') => {
  testExampleType.value = type
  if (testingRule.value) {
    testMedicalText.value = getExampleMedicalText(testingRule.value, type)
    testResult.value = null // 清除之前的测试结果
  }
}

// 获取示例病历文本（仅从示例库读取，未配置则给出提示）
const getExampleMedicalText = (rule: SichuanQCRule, type: 'positive' | 'negative'): string => {
  const ruleId = rule.rule_id
  const ruleCase = qcRuleCaseMap[ruleId]
  if (ruleCase) {
    const example = type === 'positive' ? ruleCase.positive : ruleCase.negative
    return buildCaseText(example, {
      includeHints: false,
      includeFocusPoints: false,
      includeAnalysis: false,
      includeTitle: false
    })
  }
  return '该规则暂无示例病历，请手动输入测试文本。'
}

// 执行规则测试
const executeRuleTest = async () => {
  if (!testingRule.value || !testMedicalText.value.trim()) {
    message.warning('请输入病历文本')
    return
  }

  testLoading.value = true
  testResult.value = null

  try {
    const response = await fetch('/api/v1/qc/sichuan/test-rule', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        rule_id: testingRule.value.rule_id,
        medical_text: testMedicalText.value,
      }),
    })

    const result = await response.json()

    if (result.success) {
      testResult.value = result.data
      message.success('规则测试完成')
    } else {
      message.error(result.message || '规则测试失败')
    }
  } catch (error) {
    console.error('规则测试失败:', error)
    message.error('规则测试失败，请检查网络连接')
  } finally {
    testLoading.value = false
  }
}

// 删除不需要的测试和自定义规则创建方法
// 四川省规则是预定义的，不需要创建自定义规则

// 四川省规则相关辅助方法
const getSichuanComplexityColor = (complexity: string) => {
  switch (complexity) {
    case '高复杂度': return 'red'
    case '中复杂度': return 'orange'
    case '低复杂度': return 'green'
    default: return 'default'
  }
}

const getSichuanDefectLevelColor = (level: string | undefined | null) => {
  if (!level) return 'default'
  const text = String(level)
  // 兼容英文 severities
  if (/(critical|major|严重|否决)/i.test(text)) return 'red'
  if (/(minor|一般)/i.test(text)) return 'orange'
  if (/(low|轻微)/i.test(text)) return 'green'
  return 'default'
}

const getCategoryColor = (category: string) => {
  const colors: Record<string, string> = {
    // 中文分类名称
    '诊断一致性': 'blue',
    '病史完整性': 'cyan',
    '诊疗合理性': 'purple',
    '专科判断': 'magenta',
    '内容完整性': 'geekblue',
    '术语规范性': 'gold',
    '知情同意': 'lime',
    '基础语义检查': 'volcano',
    // 标准分类名称（中文）
    '一致性': 'blue',
    '完整性': 'cyan',
    '合理性': 'purple',
    '及时性': 'orange',
    '合规性': 'red',
    '准确性': 'green',
    // 英文分类名称
    'consistency': 'blue',
    'completeness': 'cyan',
    'rationality': 'purple',
    'timeliness': 'orange',
    'compliance': 'red',
    'accuracy': 'green'
  }
  return colors[category] || 'default'
}

const getCategoryCount = (category: string) => {
  return sichuanRules.value.filter(rule => rule.category === category).length
}

// 短编号显示：优先使用平台的 rule_code；否则显示 UUID 前 8 位
const getDisplayId = (record: unknown): string => {
  const code = (record.rule_code || '').toString().trim()
  if (code) return code
  const id = (record.rule_id || record.id || '').toString()
  return id ? id.substring(0, 8) : ''
}

// 英文到中文映射
const getCategoryZh = (value: string | undefined | null) => {
  const m: Record<string, string> = {
    'consistency': '一致性',
    'completeness': '完整性',
    'rationality': '合理性',
    'timeliness': '及时性',
    'compliance': '合规性',
    'accuracy': '准确性'
  }
  const key = String(value || '').toLowerCase()
  return m[key] || value || ''
}

const getSeverityZh = (value: string | undefined | null) => {
  const m: Record<string, string> = {
    'critical': '严重',
    'major': '一般',
    'minor': '轻微'
  }
  const key = String(value || '').toLowerCase()
  return m[key] || value || ''
}


// 组件挂载时加载数据
onMounted(() => {
  // 获取当前用户信息
  fetchCurrentUser()

  if (currentSource.value === 'platform') {
    refreshPlatformRules()
  } else {
    refreshSichuanRules()
  }
})

// 切换来源时重置表头筛选选择，避免交叉污染
watch(currentSource, () => {
  headerSelected.value = {}
  // 切换数据源时更新分页总数
  if (currentSource.value === 'sichuan') {
    tablePagination.value = {
      ...tablePagination.value,
      total: sichuanRules.value.length,
      current: 1, // 重置到第一页
    }
  } else {
    tablePagination.value = {
      ...tablePagination.value,
      total: platformRules.value.length,
      current: 1, // 重置到第一页
    }
  }
})

// 启用/停用平台规则（乐观更新，失败回滚）
const onTogglePlatformRule = async (record: PlatformRule, checked: boolean) => {
  const old = !!record.is_enabled
  // 乐观更新
  record.is_enabled = checked
  try {
    const ruleId = String(record.rule_id || record.rule_code || '')
    if (!ruleId) throw new Error('缺少规则ID')
    const resp = await fetch(`/api/v1/semantic-rules/${ruleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_enabled: checked })
    })
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    // 用后端回传结果刷新该条（保证与后端一致）
    const updated = data.rule || {}
    record.is_enabled = !!updated.is_enabled
    message.success(checked ? '规则已启用' : '规则已停用')
  } catch (e: unknown) {
    // 回滚
    record.is_enabled = old
    message.error('更新启用状态失败: ' + (e?.message || e))
  }
}
</script>

<style scoped>
.semantic-rules-manager {
  padding: 12px;
}

.stats-cards {
  display: none;
}

.rules-table {
  margin-top: 8px;
}

/* 表格区域整体字体放大一号 */
:deep(.rules-table .ant-table) {
  font-size: 13px;
}

:deep(.rules-table .ant-table-thead > tr > th) {
  font-size: 13px;
}

:deep(.rules-table .ant-table-tbody > tr > td) {
  font-size: 13px;
  border: none !important;
}

/* 商务风格表格行悬停效果 */
:deep(.rules-table .ant-table-tbody > tr) {
  position: relative;
  transition: all 0.2s ease;
}

:deep(.rules-table .ant-table-tbody > tr:hover > td) {
  background: #E6F7FF !important;
  cursor: pointer;
  border-top: none !important;
  border-bottom: none !important;
}

/* 悬停行的左边框指示 */
:deep(.rules-table .ant-table-tbody > tr:hover > td:first-child) {
  border-left: 3px solid #1890FF !important;
}

/* 简洁阴影效果 */
:deep(.rules-table .ant-table-tbody > tr:hover) {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

/* 操作列按钮保持可点击 */
:deep(.rules-table .ant-table-tbody > tr:hover > td:last-child .ant-space) {
  pointer-events: auto;
}

:deep(.rules-table .ant-table-tbody > tr:hover > td:last-child .ant-btn) {
  pointer-events: auto;
}

:deep(.rules-table .ant-tag) {
  font-size: 13px;
}

.rule-name {
  font-size: 13px;
}

/* 让筛选按钮紧挨标题文本（表头） */
:deep(.rules-table .ant-table-thead > tr > th .ant-table-filter-column) {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px; /* 文本与按钮之间的距离 */
  width: auto;
}

/* 收紧筛选图标的外边距，避免靠右 */
:deep(.rules-table .ant-table-filter-trigger) {
  margin: 0; /* 覆盖 antd 默认的 margin-left: 8px */
  padding: 0;
}

/* 兼容有固定列/滚动时的表头布局 */
:deep(.rules-table .ant-table-thead > tr > th) {
  white-space: nowrap;
}

/* 表头选择性放大两号 */
:deep(.th-enlarge) {
  font-size: 15px;
  font-weight: 600;
}

/* 规则测试对话框 */
.rule-test-modal :deep(.ant-modal-content) {
  border-radius: 8px;
}

.rule-test-modal :deep(.ant-modal-header) {
  background: #1890FF;
  border-bottom: 1px solid #E8E8E8;
  padding: 16px 24px;
  border-radius: 8px 8px 0 0;
}

.rule-test-modal :deep(.ant-modal-title) {
  font-size: 16px;
  font-weight: 600;
  color: #FFFFFF;
}

.rule-test-modal :deep(.ant-modal-body) {
  padding: 24px;
  max-height: 75vh;
  overflow-y: auto;
  position: relative;
  z-index: 1;
}

/* 容器 */
.rule-test-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 卡片通用样式 */
.rule-info-card,
.medical-text-card,
.result-card {
  background: #FFFFFF;
  border-radius: 12px;
  border: 1px solid #E5E7EB;
  box-shadow: 0 6px 18px rgba(14, 110, 209, 0.08);
  overflow: hidden;
  position: relative;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

.rule-info-card:hover,
.medical-text-card:hover,
.result-card:hover {
  box-shadow: 0 10px 24px rgba(14, 110, 209, 0.12);
  transform: translateY(-2px);
}


/* 卡片标题 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #FFFFFF;
  border-bottom: 1px solid #E5E7EB;
}

.card-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1F1F1F;
  line-height: 24px;
}

.card-body {
  padding: 20px;
}

/* ========== 🎮 交互元素科技感增强 ========== */

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid transparent;
  letter-spacing: 0.2px;
}

.status-pill__icon {
  font-size: 16px;
}

.status-pill__text {
  line-height: 1;
}

.status-pill--success {
  background: #E8F8E5;
  border-color: rgba(82, 196, 26, 0.25);
  color: #389E0D;
}

.status-pill--warning {
  background: #FFF7E6;
  border-color: rgba(250, 173, 20, 0.25);
  color: #D48806;
}

.status-pill--error {
  background: #FFF1F0;
  border-color: rgba(245, 34, 45, 0.25);
  color: #CF1322;
}

.status-pill--info {
  background: #E6F7FF;
  border-color: rgba(24, 119, 255, 0.25);
  color: #1677FF;
}

.doc-tag {
  border-radius: 999px;
  font-size: 12px;
  padding: 4px 10px;
  background: #E6F4FF;
  color: #0B64D4;
  border: 1px solid rgba(11, 100, 212, 0.25);
  font-weight: 500;
}

/* 示例类型切换按钮 */
.example-type-selector {
  display: inline-flex;
  background: #F5F7FB;
  padding: 4px;
  border-radius: 24px;
  gap: 4px;
}

.rule-test-modal .example-type-selector :deep(.ant-radio-button-wrapper) {
  border-radius: 20px;
  border: 1px solid transparent;
  padding: 4px 14px;
  font-size: 12px;
  height: 32px;
  line-height: 22px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #595959;
  transition: all 0.2s ease;
  background: transparent;
}

/* 反例按钮 */
.rule-test-modal .example-type-selector :deep(.ant-radio-button-wrapper-checked.negative-btn) {
  background: #FFF1F0 !important;
  border-color: rgba(245, 34, 45, 0.3) !important;
  color: #CF1322 !important;
}

/* 正例按钮 */
.rule-test-modal .example-type-selector :deep(.ant-radio-button-wrapper-checked.positive-btn) {
  background: #E8F8E5 !important;
  border-color: rgba(82, 196, 26, 0.3) !important;
  color: #389E0D !important;
}

.radio-icon {
  font-size: 14px;
}

/* 病历文本输入框 */
.rule-test-modal .medical-textarea {
  background: #FFFFFF;
  border: 1px solid #CFD8E6 !important;
  border-radius: 12px;
  color: #2F3A4F;
  font-family: 'Source Han Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  font-weight: 400;
  letter-spacing: 0.1px;
  line-height: 24px;
  padding: 16px 18px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.rule-test-modal .medical-textarea:focus {
  border-color: #0B64D4 !important;
  box-shadow: 0 0 0 3px rgba(11, 100, 212, 0.12) !important;
}

.rule-test-modal .medical-textarea::placeholder {
  color: #8A97AC;
}

/* 开始测试按钮 */
.rule-test-modal .test-btn {
  background: #1890FF;
  border: none !important;
  transition: all 0.2s ease;
}

.rule-test-modal .test-btn:hover {
  background: #40A9FF;
}

.rule-test-modal .test-btn:active {
  background: #0050B3;
}

/* 警告提示框 */
.rule-test-modal :deep(.ant-alert) {
  border-radius: 4px;
}


/* 结果状态卡片 */
.result-status {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid transparent;
  box-shadow: inset 0 0 0 1px rgba(229, 231, 235, 0.6);
}

.result-status--success {
  background: #E8F8E5;
  border-color: rgba(82, 196, 26, 0.35);
}

.result-status--warning {
  background: #FFF7E6;
  border-color: rgba(250, 173, 20, 0.35);
}

.status-icon__graphic {
  font-size: 36px !important;
}

.status-text h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1F1F1F;
  line-height: 24px;
}

.result-progress {
  margin: 4px 0 8px;
}

.result-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-label {
  font-size: 12px;
  font-weight: 600;
  color: #8C8C8C;
  line-height: 18px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-content {
  font-size: 14px;
  font-weight: 400;
  color: #1F1F1F;
  line-height: 22px;
}

.rule-test-modal .evidence-box {
  background: #F5F5F5 !important;
  color: #262626 !important;
  border: 1px solid #D9D9D9 !important;
  border-left: 3px solid #1890FF !important;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace !important;
  padding: 12px !important;
}

/* 详情标签 */
.example-info-collapse {
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  overflow: hidden;
}

.example-info-collapse :deep(.ant-collapse-item) {
  border-bottom: none;
}

.example-info-collapse :deep(.ant-collapse-header) {
  padding: 12px 20px !important;
  background: #F4F7FB;
  border-radius: 12px;
  font-weight: 600;
  color: #334155;
}

.example-info-collapse :deep(.ant-collapse-content) {
  background: #FFFFFF;
  border-top: 1px solid #E2E8F0;
}

.example-info-collapse :deep(.ant-collapse-content-box) {
  padding: 20px;
}

.panel-header {
  display: flex;
  align-items: center;
  color: #475569;
  font-weight: 600;
  gap: 8px;
}

.panel-title {
  font-size: 14px;
}

.panel-subtitle {
  font-size: 12px;
  color: #94A3B8;
  font-weight: 400;
}

.example-info-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (min-width: 992px) {
  .example-info-content {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 16px;
  }
}

.info-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #DEE5EF;
  background: #FFFFFF;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.info-section--primary {
  background: #F7FAFF;
  border-color: rgba(30, 136, 255, 0.2);
}

.info-section--warning {
  background: #FFF8EB;
  border-color: rgba(250, 173, 20, 0.22);
}

.info-section--info {
  background: #F0F7FF;
  border-color: rgba(11, 100, 212, 0.22);
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #384A69;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.section-title__icon {
  font-size: 16px;
}

.section-content {
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
}

.hint-tag {
  margin: 4px 6px 4px 0;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(245, 34, 45, 0.08);
  color: #B4231A;
  border: 1px solid rgba(245, 34, 45, 0.16);
}

.focus-point-item {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.35);
}

.focus-point-item:last-child {
  border-bottom: none;
}

.point-index {
  flex-shrink: 0;
  font-weight: 600;
  color: #64748B;
}

.point-text {
  flex: 1;
  color: #475569;
  line-height: 1.6;
}

/* 质控分析样式 */
.info-section--analysis {
  background: linear-gradient(135deg, #F0F7FF 0%, #F7FAFF 100%);
  border-color: rgba(24, 144, 255, 0.25);
}

.analysis-summary {
  margin-bottom: 12px;
}

.analysis-summary__title {
  font-size: 13px;
  font-weight: 600;
  color: #0B64D4;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 2px solid rgba(24, 144, 255, 0.15);
}

.analysis-details {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed rgba(148, 163, 184, 0.25);
}

.analysis-details__header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #1890FF;
}

.analysis-details__icon {
  font-size: 14px;
}

.analysis-details__content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 0;
}

.analysis-detail-item {
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 6px;
  border-left: 3px solid #1890FF;
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.suggestion-box {
  background: #F4F8FF;
  padding: 12px;
  border-radius: 8px;
  border-left: 3px solid #0B64D4;
}

.result-actions {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #E5E7EB;
  display: flex;
  justify-content: flex-end;
}

.secondary-btn,
.primary-btn {
  border-radius: 20px;
  padding: 8px 16px;
  height: auto;
  font-size: 14px;
  font-weight: 600;
}

.secondary-btn {
  background: #FFFFFF;
  color: #0B64D4;
  border: 1px solid #0B64D4;
}

.secondary-btn:hover {
  background: #E6F4FF;
  border-color: #0B64D4;
  color: #0B64D4;
}

.primary-btn {
  background: #0B64D4;
  border-color: #0B64D4;
}

.primary-btn:hover {
  background: #1E88FF;
  border-color: #1E88FF;
}

.primary-btn:active {
  background: #084C9E;
  border-color: #084C9E;
}

/* 规则信息卡片 */
.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  font-weight: 400;
  color: #8C8C8C;
  line-height: 18px;
}

.info-value {
  font-size: 14px;
  font-weight: 400;
  color: #1F1F1F;
  line-height: 22px;
}

.info-description {
  margin: 0;
  font-size: 14px;
  font-weight: 400;
  color: #595959;
  line-height: 22px;
}

.medical-textarea {
  border-radius: 12px;
  font-size: 14px;
  line-height: 24px;
  font-family: 'Source Han Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-weight: 400;
  color: #2F3A4F;
  letter-spacing: 0.1px;
  padding: 16px 18px;
}

.medical-textarea:focus {
  border-color: #0B64D4;
  box-shadow: 0 0 0 3px rgba(11, 100, 212, 0.12);
}

.medical-textarea::placeholder {
  color: #8A97AC;
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  gap: 12px;
}

.hint-text {
  font-size: 14px;
  font-weight: 500;
  color: #595959;
  line-height: 20px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.hint-icon {
  font-size: 14px;
  color: #faad14;
}

.test-btn {
  border-radius: 20px;
  padding: 8px 16px;
  height: auto;
  font-size: 14px;
  font-weight: 600;
  background: #0B64D4;
  border-color: #0B64D4;
}

.test-btn:hover {
  background: #1E88FF;
  border-color: #1E88FF;
}

.test-btn:active {
  background: #084C9E;
  border-color: #084C9E;
}

@media (max-width: 768px) {
  .action-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .action-bar .hint-text {
    display: block;
  }
}

.rule-detail {
  max-height: 600px;
  overflow-y: auto;
}

.card-title {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.title-icon {
  margin-right: 8px;
  font-size: 18px;
  color: #2563eb;
}

.category-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-item .label {
  font-size: 12px;
  color: #666;
}

.rule-name {
  cursor: pointer;
  color: #1890ff;
}

.rule-name:hover {
  text-decoration: underline;
}

.document-types {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.ant-descriptions-item-label {
  font-weight: 600;
}

.ant-statistic-content {
  font-size: 20px;
}

.ant-badge-status-text {
  font-size: 12px;
}

/* 提示词管理样式 */
.prompt-management {
  margin-top: 16px;
}

.prompt-actions {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
}

.prompt-display {
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.prompt-display pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
}

.prompt-editor {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .semantic-rules-manager {
    padding: 12px;
  }

  .stats-cards .ant-col {
    margin-bottom: 12px;
  }

  .rules-table {
    font-size: 12px;
  }
}
</style>
