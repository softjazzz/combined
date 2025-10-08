<template>
  <div class="semantic-rules-manager">
    <a-card :bordered="false">
      <template #title>
        <div class="card-title">
          <span class="title-icon">🏥</span>
          四川省住院病历语义质控规则
          <a-tag color="blue" style="margin-left: 8px">68条规则</a-tag>
        </div>
      </template>
      <template #extra>
        <a-space>
          <a-radio-group v-model:value="currentSource" size="small">
            <a-radio-button value="platform">平台规则</a-radio-button>
            <a-radio-button value="sichuan">四川规则</a-radio-button>
          </a-radio-group>
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

          <a-button @click="showSystemStats = true">
            <template #icon><BarChartOutlined /></template>
            系统统计
          </a-button>
        </a-space>
      </template>

      <!-- 平台规则筛选（仅 platform 显示） -->
      <div v-if="currentSource === 'platform'" style="margin: 12px 0;">
        <a-space>
          <a-input v-model:value="filters.q" allowClear placeholder="搜索名称/描述" style="width: 220px" />
          <a-select v-model:value="filters.category" allowClear placeholder="分类" style="width: 140px">
            <a-select-option v-for="c in platformCategories" :key="c" :value="c">{{ c }}</a-select-option>
          </a-select>
          <a-select v-model:value="filters.defect_level" allowClear placeholder="缺陷级别" style="width: 140px">
            <a-select-option value="critical">critical</a-select-option>
            <a-select-option value="major">major</a-select-option>
            <a-select-option value="minor">minor</a-select-option>
          </a-select>
          <a-select v-model:value="filters.is_enabled" allowClear placeholder="启用状态" style="width: 120px">
            <a-select-option :value="true">启用</a-select-option>
            <a-select-option :value="false">停用</a-select-option>
          </a-select>
          <a-button type="primary" :loading="loading" @click="refreshPlatformRules">查询</a-button>
        </a-space>
      </div>

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
        :dataSource="currentSource === 'platform' ? platformRules : sichuanRules"
        :columns="currentSource === 'platform' ? platformColumns : sichuanColumns"
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
                  {{ docType || '未知类型' }}
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
                  {{ docType }}
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
            {{ docType }}
          </a-tag>
        </div>

        <a-divider>四川省质控标准</a-divider>
        <a-alert
          message="基于《四川省住院病历质量评定标准（2023年版）》"
          description="该规则严格按照四川省卫健委发布的最新住院病历质量评定标准制定，确保质控评估的权威性和准确性。"
          type="info"
          show-icon
        />
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
  BarChartOutlined
} from '@ant-design/icons-vue'

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
  title: any
  dataIndex?: string
  key: string
  width?: number
  fixed?: string
  ellipsis?: boolean
  // antd-vue 列筛选可选属性（为简化类型，这里使用 any）
  filters?: any[]
  onFilter?: (value: any, record: any) => boolean
  filteredValue?: any[] | null
}

// 四川省规则相关数据
const loading = ref(false)
const currentSource = ref<'platform' | 'sichuan'>('platform')
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

const platformRules = ref<PlatformRule[]>([])
const platformCategories = ref<string[]>([])
const filters = ref<{ q?: string; category?: string; defect_level?: string; is_enabled?: boolean | null; page?: number; page_size?: number }>({
  q: '',
  category: undefined,
  defect_level: undefined,
  is_enabled: null,
  page: 1,
  page_size: 15,
})
const tablePagination = ref({ current: 1, total: 0, pageSize: 15, showSizeChanger: true, showQuickJumper: true, pageSizeOptions: ['15', '20', '50', '100'] })

// 规则详情
const showRuleDetail = ref(false)
const selectedRule = ref<SichuanQCRule | null>(null)

// 质控评估和系统统计
const showQCEvaluation = ref(false)
const showSystemStats = ref(false)

// 四川省规则表格列定义
// 表头筛选选中项（受控）
const headerSelected = ref<Record<string, any[] | null>>({})

// 动态列（四川）
const sichuanColumns = computed<TableColumn[]>(() => [
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
    dataIndex: 'category',
    key: 'category',
    width: 120,
    filters: Array.from(new Set(sichuanRules.value.map(r => r.category).filter(Boolean))).map(c => ({ text: c, value: c })),
    filteredValue: headerSelected.value.category ?? null,
    onFilter: (value, record) => String(record.category) === String(value)
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '复杂度'),
    dataIndex: 'complexity',
    key: 'complexity',
    width: 100
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '缺陷级别'),
    dataIndex: 'defect_level',
    key: 'defect_level',
    width: 120,
    filters: Array.from(new Set(sichuanRules.value.map(r => r.defect_level).filter(Boolean))).map(s => ({ text: s, value: s })),
    filteredValue: headerSelected.value.defect_level ?? null,
    onFilter: (value, record) => String(record.defect_level) === String(value)
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '文书类别（标准化）'),
    dataIndex: 'applicable_documents',
    key: 'applicable_documents',
    width: 180,
    ellipsis: true,
    filters: Array.from(new Set(
      (sichuanRules.value || [])
        .flatMap(r => r.applicable_documents || [])
        .map(mapDocTypeToCanonical)
        .filter((x: any) => !!x)
    ) as Set<string>).map((code: any) => ({ text: CANONICAL_LABEL_ZH[String(code)], value: String(code) })),
    filteredValue: headerSelected.value.applicable_documents ?? null,
    onFilter: (value, record) => {
      const mapped = (record.applicable_documents || []).map((d: any) => mapDocTypeToCanonical(d)).filter((x: any) => !!x)
      return mapped.includes(String(value))
    }
  },
  {
    title: () => h('span', { class: 'th-enlarge' }, '医疗领域'),
    dataIndex: 'medical_domain',
    key: 'medical_domain',
    width: 120
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
      .filter((x: any) => !!x)))
    console.log('🧪 平台规则 applicable_documents 原始值 count=', rawPlatformDocs.length, rawPlatformDocs)
    console.log('✅ 平台规则 文书类别过滤项(标准6类)=', canonicalPlatformDocs.map((code: any) => ({ code, label: CANONICAL_LABEL_ZH[String(code)] })))
  } catch {}

  return [
    { title: () => h('span', { class: 'th-enlarge' }, '编号'), key: 'rule_id', dataIndex: 'rule_id', width: 120, fixed: 'left' },
    { title: () => h('span', { class: 'th-enlarge' }, '名称'), key: 'rule_name', dataIndex: 'rule_name', width: 220, ellipsis: true },
    {
      title: () => h('span', { class: 'th-enlarge' }, '分类'),
      key: 'category',
      dataIndex: 'category',
      width: 120,
      filters: categoryFilters,
      filteredValue: headerSelected.value.category ?? null,
      onFilter: (value, record) => String(record.category) === String(value)
    },
    {
      title: () => h('span', { class: 'th-enlarge' }, '缺陷级别'),
      key: 'defect_level',
      dataIndex: 'defect_level',
      width: 120,
      filters: defectFilters,
      filteredValue: headerSelected.value.defect_level ?? null,
      onFilter: (value, record) => String(record.defect_level) === String(value)
    },
    {
      title: () => h('span', { class: 'th-enlarge' }, '文书类别（标准化）'),
      key: 'applicable_documents',
      dataIndex: 'applicable_documents',
      width: 200,
      filters: Array.from(new Set((platformRules.value || [])
        .flatMap(r => r.applicable_documents || [])
        .map(mapDocTypeToCanonical)
        .filter((x: any) => !!x)
      ) as Set<string>).map((code: any) => ({ text: CANONICAL_LABEL_ZH[String(code)], value: String(code) })),
      filteredValue: headerSelected.value.applicable_documents ?? null,
      onFilter: (value, record) => {
        const mapped = (record.applicable_documents || []).map((d: any) => mapDocTypeToCanonical(d)).filter((x: any) => !!x)
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

// 四川省规则相关方法
const refreshSichuanRules = async () => {
  loading.value = true
  try {
    console.log('🔄 开始加载四川省质控规则...')

    const response = await fetch('/api/qc/sichuan/rules')
    if (response.ok) {
      const data = await response.json()
      // 后端返回的字段可能为英文或缺失，这里做一次规范化
      const normalizeRule = (r: any): SichuanQCRule => {
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
      sichuanRules.value = rawRules.map((r: any) => normalizeRule(r))
      sichuanStats.value = {
        total_rules: data.total_rules || 68,
        rule_categories: data.rule_categories || [],
        complexity_distribution: data.complexity_distribution || {},
        defect_level_distribution: data.defect_level_distribution || {}
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
    params.set('page_size', String(tablePagination.value.pageSize || 15))

    const resp = await fetch(`/api/semantic-rules?${params.toString()}`)
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    platformRules.value = (data.rules || [])
    tablePagination.value = {
      ...tablePagination.value,
      total: Number(data.count || 0),
    }
    // 简单推断分类列表
    platformCategories.value = Array.from(new Set(platformRules.value.map(r => r.category).filter(Boolean) as string[]))
  } catch (e: any) {
    message.error('加载平台规则失败: ' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

// 本地受控筛选：结合分页事件获取 filters
const handleTableChange = (pagination: any, tableFilters?: Record<string, any[]>) => {
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
}

// 开始质控评估
const startQCWithRule = (rule: SichuanQCRule) => {
  message.info(`准备使用规则 ${rule.rule_id} 进行质控评估`)
  showQCEvaluation.value = true
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
const getDisplayId = (record: any): string => {
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

// 文书类别标准化（Plan A）：将一切映射到 6 个标准大类，并去除“急诊记录”
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
  '输血记录': 'progress_note',
  '治疗记录': 'progress_note',
  '医嘱记录': 'progress_note',
  // ‘急诊记录’不保留，直接剔除
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



// 组件挂载时加载数据
onMounted(() => {
  if (currentSource.value === 'platform') {
    refreshPlatformRules()
  } else {
    refreshSichuanRules()
  }
})

// 切换来源时重置表头筛选选择，避免交叉污染
watch(currentSource, () => {
  headerSelected.value = {}
})

// 启用/停用平台规则（乐观更新，失败回滚）
const onTogglePlatformRule = async (record: PlatformRule, checked: boolean) => {
  const old = !!record.is_enabled
  // 乐观更新
  record.is_enabled = checked
  try {
    const ruleId = String(record.rule_id || record.rule_code || '')
    if (!ruleId) throw new Error('缺少规则ID')
    const resp = await fetch(`/api/semantic-rules/${ruleId}`, {
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
  } catch (e: any) {
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
